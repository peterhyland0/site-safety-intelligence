"""Carry a sub's decisions to new establishment keys after a rebuild with changed cleaning rules.

Keys are md5(clean_name|addr_key|zip5|state), so a cleaning-rule change gives some records new keys (the name-matching
audit merged ADELPHI CONSTRUCTION LC into ADELPHI CONSTRUCTION, and split J B T C VENTURES off JB TC VENTURES).
app.sub_match has no foreign key into the warehouse, so its decisions would stay on keys the new build doesn't have.
OSHA's activity numbers never change, so a decision follows its record's inspections: every current key holding any
of them (entity.establishment_member) gets it. A key that's gone moves there; a key that's still there keeps its
decision and passes it on to records that took some of its inspections. The old inspections come from the row
(sub_match.activity_nrs, stored when the row is written) or, for rows saved before that, from the build they were
decided on if data/build still has it (Modal keeps two builds). A gone key whose inspections can't be found, or have
all left the data, stays as it is.

Where records land on one new record, with any row the sub already has for it:
- the GC's decisions win. GC decisions that disagree become a question to the GC instead of one being picked; the
  record waits as possible (method 'remap'), and a re-match keeps it, as it keeps every GC decision. An open
  question about a record that lands on one the GC decided is settled by that decision;
- the AI's decisions and the holds from a company profile or the web check (methods 'profile' and 'web') carry over
  when every record landing there was decided the same way. If not, they're dropped and the rules (then the AI)
  decide the merged record again. Either way the re-match replaces one when a rule now matches its record
  (run.gives_way);
- rule decisions aren't carried: the re-match that follows runs the rules on the new keys.

Every build does this for every sub (follow_all, from the build and from Modal's refresh, once the new build is live):
the decisions move and the rules run again, in one transaction a sub, with no model calls. Newly uncertain records
wait for the adjudicator, which the app runs; red-flagged ones become GC questions there. scripts/rematch.py does the
same with a dry run, the M3 web check and the adjudicator. Until a sub's decisions have moved, the app counts nothing
from a record the build doesn't have and shows the sub as Review, never as clean (queries.core.compute)."""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from pathlib import Path

import duckdb

from ssi import config
from ssi.matching import adjudicate as ADJ
from ssi.matching import candidates as C
from ssi.store import pg, warehouse

log = logging.getLogger(__name__)
GC_LIKE = ("gc", "remap")  # 'remap': GC decisions that disagree, waiting for the GC's answer
GC_SAID = {"matched": "you confirmed {} as your sub", "excluded": "you marked {} as a different company",
           "possible": "you left {} as possible"}


def plan(sub: dict, build_dir: Path | None = None) -> dict:
    """What remapping this sub's rows to the current build would do. Read-only.

    {"moves": {gone key: {"row", "targets": {new key: inspections shared}, "size": its inspections,
                          "via": where they came from}},
     "splits": {current key: the same, for the other keys that took some of its inspections},
     "lost": gone keys' rows whose inspections all left the data, "unknown": gone keys' rows whose inspections
     can't be found,
     "targets": {new key: {"action": carry | ask | release | rules, "decision": the row carried or None,
                           "kept": the sub's row for that key or None, "sources": [(old key, row, shared)]}},
     "after": {key: row}: the sub's rows once applied, which the re-match's dry run compares against}"""
    with pg.conn() as c:
        rows = {r["establishment_key"]: r for r in c.execute(
            "SELECT * FROM app.sub_match WHERE sub_id = %s AND establishment_key <> '__note__'",
            [str(sub["sub_id"])]).fetchall()}
    out = {"moves": {}, "splits": {}, "lost": [], "unknown": [], "targets": {}, "after": dict(rows)}
    if not rows:
        return out
    present = {r["establishment_key"] for r in warehouse.rows(
        "SELECT establishment_key FROM entity.establishment WHERE establishment_key IN (SELECT unnest(?::VARCHAR[]))",
        [list(rows)])}
    old = old_members(list(rows.values()), sub.get("matched_build"), build_dir or config.BUILD_DIR)
    found = new_keys({k: nrs for k, (nrs, _) in old.items()})
    for k, r in rows.items():
        targets = found.get(k) or {}
        if k in present:
            if set(targets) - {k}:
                out["splits"][k] = {"row": r, "targets": {t: n for t, n in targets.items() if t != k},
                                    "size": len(old[k][0]), "via": old[k][1]}
        elif k not in old:
            out["unknown"].append(r)
        elif not targets:
            out["lost"].append(r)
        else:
            out["moves"][k] = {"row": r, "targets": targets, "size": len(old[k][0]), "via": old[k][1]}
    landing: dict[str, list] = defaultdict(list)
    for k, m in {**out["moves"], **out["splits"]}.items():
        for t, shared in m["targets"].items():
            landing[t].append((k, m["row"], shared))
    after = {k: r for k, r in rows.items() if k not in out["moves"]}
    for t, sources in landing.items():
        kept = rows.get(t)
        action, decision = resolve(kept, [r for _, r, _ in sources], {k: n for k, _, n in sources})
        out["targets"][t] = {"action": action, "decision": decision, "kept": kept, "sources": sources}
        if action == "carry":
            after[t] = {**decision, "establishment_key": t}
        elif action == "ask":
            after[t] = {**(kept or sources[0][1]), "establishment_key": t, "bucket": "possible", "method": "remap",
                        "rule_id": None}
        else:  # the rules decide; the dry run shows the record's old rule decision, if it had one
            after.pop(t, None)
            rule_rows = [(n, r) for _, r, n in sources if r["method"] == "rule"]
            if kept and kept["method"] == "rule":
                after[t] = kept
            elif not kept and rule_rows:
                after[t] = {**max(rule_rows, key=lambda x: x[0])[1], "establishment_key": t}
    out["after"] = after
    return out


def resolve(kept: dict | None, landing: list[dict], shared: dict[str, int]) -> tuple[str, dict | None]:
    """The decision a new record inherits from the rows landing on it and the sub's own row for it (`kept`).
    carry: this row's decision · ask: GC decisions disagree · release: AI decisions disagree, so the rules and the AI
    decide again · rules: nothing but rule decisions, which the re-match re-runs."""
    rows = landing + ([kept] if kept else [])
    gc = [r for r in rows if r["method"] in GC_LIKE]
    if gc:
        return ("carry", _best(gc, kept, shared)) if len({r["bucket"] for r in gc}) == 1 else ("ask", None)
    held = [r for r in rows if r["method"] != "rule"]
    if not held:
        return "rules", None
    # a rule decision on a record now merged with this one disagrees too: the merged record is a new question
    return ("carry", _best(held, kept, shared)) if len({r["bucket"] for r in rows}) == 1 else ("release", None)


def _best(rows: list[dict], kept: dict | None, shared: dict[str, int]) -> dict:
    """The sub's own row for the new key, else the row sharing most inspections with it (the latest on a tie)."""
    if kept is not None and any(r is kept for r in rows):
        return kept
    return max(rows, key=lambda r: (shared.get(r["establishment_key"], 0), r["decided_at"]))


def old_members(rows: list[dict], matched_build: str | None, build_dir: Path) -> dict[str, tuple[list[int], str]]:
    """{key: (its inspections when decided, where they came from)}: stored on the row, else from a kept build other
    than the current one that has the key (the sub's matched build first, then each row's own build)."""
    out = {r["establishment_key"]: (list(r["activity_nrs"]), "stored") for r in rows if r.get("activity_nrs")}
    current = warehouse.meta()["build_id"]
    for build_id in dict.fromkeys([matched_build] + [r.get("build_id") for r in rows]):
        need = [r["establishment_key"] for r in rows if r["establishment_key"] not in out]
        if not need:
            break
        path = build_dir / f"warehouse-{build_id}.duckdb"
        if not build_id or build_id == current or not path.exists():
            continue
        with duckdb.connect(str(path), read_only=True) as con:
            for k, nrs in con.execute("""SELECT establishment_key, list(activity_nr ORDER BY activity_nr)
                                         FROM entity.establishment_member
                                         WHERE establishment_key IN (SELECT unnest(?::VARCHAR[])) GROUP BY 1""",
                                      [need]).fetchall():
                out[k] = (list(nrs), f"build {build_id}")
    return out


def new_keys(old: dict[str, list[int]]) -> dict[str, dict[str, int]]:
    """{old key: {current key: inspections they share}} in the current build."""
    pairs = [(k, nr) for k, nrs in old.items() for nr in nrs]
    if not pairs:
        return {}
    out: dict[str, dict[str, int]] = defaultdict(dict)
    for r in warehouse.rows("""SELECT o.k, m.establishment_key, count(*) AS n
                               FROM (SELECT unnest(?::VARCHAR[]) AS k, unnest(?::BIGINT[]) AS nr) o
                               JOIN entity.establishment_member m ON m.activity_nr = o.nr GROUP BY 1, 2""",
                            [[k for k, _ in pairs], [nr for _, nr in pairs]]):
        out[r["k"]][r["establishment_key"]] = r["n"]
    return out


def moved_to(p: dict) -> dict[str, list[str]]:
    """{old key: the keys its inspections are on once the plan is applied}, for keys the plan moves or splits."""
    return {k: list(m["targets"]) for k, m in p["moves"].items()} | {k: [k, *m["targets"]] for k, m in p["splits"].items()}


def changes(p: dict) -> bool:
    """Whether the plan moves any decision."""
    return bool(p["moves"] or p["splits"])


def apply(sub: dict, p: dict, conn=None) -> dict:
    """Write the plan, before the re-match's run.persist: decisions onto their new keys, a question for each record
    whose GC decisions disagree, open questions pointed at the new keys, the gone keys' rows deleted. Every non-rule
    row left on a current key gets its inspections stored, so a later remap doesn't need this build to be kept.
    The gone keys' rule rows are deleted here and only written again by run.persist, so pass the transaction (`conn`)
    that persist runs in: a failure between the two would otherwise leave the sub with its rule matches gone."""
    sub_id = str(sub["sub_id"])
    targets = p["targets"]
    stats = {"moved": len(p["moves"]), "split": len(p["splits"]), "carried": 0, "questions": 0, "released": 0}
    stuck = {r["establishment_key"] for r in p["lost"] + p["unknown"]}
    held = [k for k, r in p["after"].items() if r["method"] != "rule" and k not in targets and k not in stuck]
    nrs = C.members(list(targets) + held)
    ests = {e["establishment_key"]: e for e in C.establishments(list(targets))}
    build_id = warehouse.meta()["build_id"]
    with pg.conn(conn) as c:
        for t, x in targets.items():
            if x["action"] == "carry":
                d = x["decision"]
                _upsert(c, sub_id, t, d, _evidence(ests[t], d, x["sources"]), nrs.get(t), build_id)
                stats["carried"] += 1
            elif x["action"] == "ask":
                d = {**(x["kept"] or x["sources"][0][1]), "bucket": "possible", "method": "remap", "rule_id": None,
                     "confidence": None, "needs_adjudication": False, "decided_by": "remap", "decided_at": None,
                     "rationale": "Records you decided differently are now one OSHA record; waiting for your answer"}
                _upsert(c, sub_id, t, d, _evidence(ests[t], d, x["sources"]), nrs.get(t), build_id)
                stats["questions"] += _ask(c, sub, t, ests[t], x)
            elif x["action"] == "release":
                # rows that leave: the gone keys' and the new key's own (a split record keeps its row on its key)
                dropped = [r for k, r, _ in x["sources"] if k in p["moves"]] + ([x["kept"]] if x["kept"] else [])
                stats["released"] += sum(r["method"] != "rule" for r in dropped)
                if x["kept"] and x["kept"]["method"] != "rule":
                    c.execute("DELETE FROM app.sub_match WHERE sub_id = %s AND establishment_key = %s", [sub_id, t])
        if changes(p):
            c.execute("DELETE FROM app.sub_match WHERE sub_id = %s AND establishment_key = ANY(%s)",
                      [sub_id, list(p["moves"])])
            # an open question about a record asks about wherever its inspections are now
            now = moved_to(p)
            for q in c.execute("SELECT * FROM app.match_question WHERE sub_id = %s AND answer IS NULL",
                               [sub_id]).fetchall():
                keys = list(dict.fromkeys(t for k in q["establishment_keys"] for t in now.get(k, [k])))
                if keys != q["establishment_keys"]:
                    c.execute("UPDATE app.match_question SET establishment_keys = %s WHERE question_id = %s",
                              [keys, q["question_id"]])
            # ... unless it's now part of a record the GC decided: the GC's decision wins (as for the AI's), so it
            # settles the question, which would otherwise ask about a record that's counted or dropped
            for r in c.execute("""SELECT establishment_key, bucket FROM app.sub_match WHERE sub_id = %s AND method = 'gc'
                                  AND bucket <> 'possible' AND establishment_key = ANY(%s)""",
                               [sub_id, list(targets)]).fetchall():
                ADJ.settle(c, sub_id, r["establishment_key"], r["bucket"])
        for k in held:
            if k in nrs and list(p["after"][k].get("activity_nrs") or []) != nrs[k]:
                c.execute("UPDATE app.sub_match SET activity_nrs = %s WHERE sub_id = %s AND establishment_key = %s",
                          [nrs[k], sub_id, k])
    return stats


def _upsert(c, sub_id: str, key: str, d: dict, evidence: dict, nrs: list[int] | None, build_id: str) -> None:
    """The decision `d` on `key`, keeping when it was made (a new 'remap' row has none: now)."""
    c.execute("""INSERT INTO app.sub_match (sub_id, establishment_key, bucket, method, rule_id, confidence, rationale,
                                            evidence, needs_adjudication, decided_by, decided_at, build_id, activity_nrs)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()), %s, %s)
                 ON CONFLICT (sub_id, establishment_key) DO UPDATE SET
                   bucket = EXCLUDED.bucket, method = EXCLUDED.method, rule_id = EXCLUDED.rule_id,
                   confidence = EXCLUDED.confidence, rationale = EXCLUDED.rationale, evidence = EXCLUDED.evidence,
                   needs_adjudication = EXCLUDED.needs_adjudication, decided_by = EXCLUDED.decided_by,
                   decided_at = EXCLUDED.decided_at, build_id = EXCLUDED.build_id, activity_nrs = EXCLUDED.activity_nrs""",
              [sub_id, key, d["bucket"], d["method"], d["rule_id"], d["confidence"], d["rationale"],
               json.dumps(evidence, default=str), d["needs_adjudication"], d["decided_by"], d["decided_at"], build_id, nrs])


def _evidence(e: dict, d: dict, sources: list) -> dict:
    """The decision's evidence, describing the record as the current build has it, and the records it came from."""
    ev = d.get("evidence") or {}
    came = [{"key": k, "name": (r["evidence"] or {}).get("name"), "shared_inspections": n} for k, r, n in sources]
    return {**ev, "name": e["clean_name"], "state": e["state"], "city": e["city"], "zip": e["zip5"],
            "address": e["address"], "years": [e["first_seen"], e["last_seen"]], "inspections": e["insp_n"],
            "naics4": e["primary_naics4"], "related_only": bool(e["related_only"]),
            "remapped_from": (ev.get("remapped_from") or []) + came}


def _ask(c, sub: dict, key: str, e: dict, x: dict) -> int:
    sub_id = str(sub["sub_id"])
    if any(q["establishment_keys"] == [key] for q in c.execute(
            "SELECT establishment_keys FROM app.match_question WHERE sub_id = %s AND answer IS NULL", [sub_id])):
        return 0  # already waiting for the GC
    c.execute("INSERT INTO app.match_question (sub_id, establishment_keys, text, kind) VALUES (%s, %s, %s, 'remap')",
              [sub_id, [key], question_text(sub, e, x)])
    return 1


def question_text(sub: dict, e: dict, x: dict) -> str:
    said = []
    for r in [r for _, r, _ in x["sources"]] + ([x["kept"]] if x["kept"] else []):
        if r["method"] not in GC_LIKE:
            continue
        ev = r["evidence"] or {}
        place = ", ".join(v for v in ((ev.get("city") or "").title(), ev.get("state")) if v)
        name = f"'{ev.get('name') or r['establishment_key'][:8]}'" + (f" ({place})" if place else "")
        said.append(f"{name} was waiting for your answer" if r["method"] == "remap" else GC_SAID[r["bucket"]].format(name))
    n = e.get("insp_n") or 0
    where = ", ".join(v for v in (e.get("address"), (e.get("city") or "").title(), e.get("state")) if v)
    return (f"After a data update, OSHA records you answered differently are one record: {'; '.join(said)}. "
            f"OSHA's records now group them as '{e['clean_name']}' ({where or 'no address on file'}, "
            f"{n} inspection{'s' if n != 1 else ''}). Is this record your sub '{sub['entered_name']}'?")


# --- after a build: every sub's decisions follow their records ---------------------------------------------------
FOLLOW_RETRY_SECONDS = 30  # a sub the app is resolving is tried once more after this


def follow(sub: dict, project_state: str | None, build_dir: Path | None = None) -> dict | None:
    """One sub after a rebuild, under its claim: its decisions moved to the keys now holding their inspections and the
    rules run again, in one transaction (a failure leaves the sub as it was, which the app shows as Review), then its
    company profile and company-name questions applied again (adjudicate.apply_profile, cover_company_names). No model
    calls. None when the app is resolving the sub right now."""
    from ssi.llm import profile as P  # imported here: the matching package doesn't otherwise need it
    from ssi.matching.run import match_sub, persist  # run imports this package's adjudicate, not this module
    with ADJ.claim(str(sub["sub_id"])) as claimed:
        if claimed is None:
            return None
        p = plan(claimed, build_dir)
        result = match_sub(claimed, project_state)
        with pg.conn() as c:
            stats = apply(claimed, p, c)
            persist(str(claimed["sub_id"]), result, c)
        prof = P.load(claimed.get("profile_id"))
        if prof:
            ADJ.apply_profile(claimed, prof)
        else:
            with pg.conn() as c:
                ADJ.cover_company_names(c, claimed)
        return stats


def follow_all(build_dir: Path | None = None, retry_after: float = FOLLOW_RETRY_SECONDS) -> dict:
    """Every sub's decisions onto the build the warehouse module has open (follow). A sub the app is resolving is tried
    again once after `retry_after` seconds; one that fails is logged and left as it was. Returns
    {subs, moved, questions, busy: [sub names], failed: [sub names]}."""
    with pg.conn() as c:
        subs = c.execute("""SELECT s.*, p.state AS project_state FROM app.project_sub s
                            JOIN app.project p USING (project_id) ORDER BY p.created_at, s.position""").fetchall()
    out = {"subs": len(subs), "moved": 0, "questions": 0, "busy": [], "failed": []}
    todo = subs
    for attempt in range(2):
        busy = []
        for s in todo:
            try:
                st = follow(s, s["project_state"], build_dir)
            except Exception:  # one sub's failure doesn't stop the others; it stays Review until rerun
                log.exception("decisions not moved for sub %s (%s)", s["sub_id"], s["entered_name"])
                out["failed"].append(s["entered_name"])
                continue
            if st is None:
                busy.append(s)
                continue
            out["moved"] += st["moved"] + st["split"]
            out["questions"] += st["questions"]
        todo = busy
        if not busy or attempt:
            break
        time.sleep(retry_after)
    out["busy"] = [s["entered_name"] for s in todo]
    return out


if __name__ == "__main__":  # move every sub's decisions onto the current build: after a failed or skipped step
    logging.basicConfig(level=logging.INFO)
    warehouse.open_warehouse()
    print(json.dumps(follow_all(), indent=2))
