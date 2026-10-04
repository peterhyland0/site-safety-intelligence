"""Re-run matching for existing subs after a rules or data change, keeping every GC and AI decision.

Dry run by default: shows, per sub, the decisions that move to new establishment keys (a cleaning-rule change
regroups records; ssi/matching/remap.py) and the records whose rule decision would change. --apply moves the
decisions (GC answers that now disagree about one record become a question to the GC), rewrites the rule
decisions (decisions made by the GC or the AI reviewer are kept), checks M3 matches against the sub's company
profile when it has one (adjudicate.check_m3: a re-match writes them as plain M3 again), then sends newly uncertain
records through the adjudicator, which turns red-flagged ones into GC questions.

    uv run python -m scripts.rematch                              # every project, dry run
    uv run python -m scripts.rematch --project "Demo: Hospital expansion, Nashville TN" --apply
"""
from __future__ import annotations

import argparse

from ssi.llm import profile as P
from ssi.matching import adjudicate as ADJ
from ssi.matching import candidates as C
from ssi.matching import remap
from ssi.matching.run import EXCLUDED, MATCHED, UNCERTAIN, match, match_and_persist
from ssi.store import pg, warehouse

BUCKET = {MATCHED: "matched", UNCERTAIN: "possible", EXCLUDED: "excluded"}


def plan(sub: dict, project_state: str | None, stored: dict[str, dict] | None = None) -> list[dict]:
    """Rule decisions that would change for this sub (GC and AI decisions are never touched). `stored`: the sub's
    rows to compare with, by key (default: as saved; rematch passes them as they'll be after remap.apply)."""
    if stored is None:
        with pg.conn() as c:
            stored = {r["establishment_key"]: r for r in c.execute(
                "SELECT * FROM app.sub_match WHERE sub_id = %s AND establishment_key <> '__note__'",
                [sub["sub_id"]]).fetchall()}
    res = match(sub["entered_name"], sub.get("entered_city"), sub.get("entered_state") or project_state,
                sub.get("trade"), sub.get("licence"))
    changes = []
    for x in res["decisions"]:
        k, d = x["row"]["establishment_key"], x["decision"]
        old = stored.get(k)
        if old and old["method"] != "rule":
            continue  # the GC's or the AI's decision stands
        new_bucket = BUCKET[d.bucket]
        if old and old["bucket"] == new_bucket and old["rule_id"] == d.rule_id:
            continue
        if not old and d.bucket == EXCLUDED:
            continue  # a new lookalike that stays out changes nothing the GC sees
        changes.append({"key": k, "name": x["row"]["display_name"], "place": f"{x['row']['city']}, {x['row']['state']}",
                        "old": f"{old['bucket']}/{old['rule_id']}" if old else "-", "new": f"{new_bucket}/{d.rule_id}"})
    # rule decisions that would disappear: the record left the data (scope change) or the search
    seen = {x["row"]["establishment_key"] for x in res["decisions"]}
    for k, old in stored.items():
        if old["method"] == "rule" and old["bucket"] != "excluded" and k not in seen:
            ev = old["evidence"] or {}
            changes.append({"key": k, "name": ev.get("name") or k[:8], "place": f"{ev.get('city')}, {ev.get('state')}",
                            "old": f"{old['bucket']}/{old['rule_id']}", "new": "removed"})
    flags = C.red_flag_counts([ch["key"] for ch in changes])
    for ch in changes:
        ch["red_flags"] = flags.get(ch["key"], 0)
    return changes


def _what(r: dict) -> str:
    ev = r["evidence"] or {}
    place = ", ".join(v for v in ((ev.get("city") or "").title(), ev.get("state")) if v)
    return f"'{ev.get('name') or r['establishment_key'][:8]}'" + (f" ({place})" if place else "")


def remap_lines(rp: dict) -> list[str]:
    """The dry run's account of remap.plan: decisions moving to new keys, and those that can't."""
    targets, came = rp["targets"], {**rp["moves"], **rp["splits"]}
    ests = {e["establishment_key"]: e for e in C.establishments(list(targets))}
    out = []
    for t, x in targets.items():
        if x["action"] == "rules":
            continue  # rule decisions only: the rules run again on the new key (shown below)
        e = ests.get(t) or {}
        moved = " + ".join(("part of " if k in rp["splits"] else "") + _what(r) for k, r, _ in x["sources"])
        shared = ", ".join(f"{n} of {came[k]['size']}" for k, _, n in x["sources"])
        via = {came[k]["via"] for k, _, _ in x["sources"]} - {"stored"}
        line = (f"    {moved} -> '{e.get('clean_name')}' ({(e.get('city') or '').title()}, {e.get('state')}; "
                f"{shared} inspections{'; from ' + ', '.join(sorted(via)) if via else ''}): ")
        if x["action"] == "carry":
            d = x["decision"]
            line += f"{d['method']}/{d['bucket']} kept"
        else:
            rows = [r for _, r, _ in x["sources"]] + ([x["kept"]] if x["kept"] else [])
            decided = sorted({f"{r['method']}/{r['bucket']}" for r in rows if r["method"] != "rule"})
            line += (f"your answers differ ({', '.join(decided)}): a question to the GC" if x["action"] == "ask"
                     else f"decisions differ ({', '.join(decided)}): the rules and the AI decide again")
        out.append(line)
    for r in rp["lost"]:
        if r["method"] != "rule":
            out.append(f"    {_what(r)} {r['method']}/{r['bucket']}: kept on its old key; none of its inspections "
                       f"are in this build")
    for r in rp["unknown"]:
        if r["method"] != "rule":
            out.append(f"    {_what(r)} {r['method']}/{r['bucket']}: kept on its old key; its inspections weren't "
                       f"stored and its build ({r.get('build_id')}) isn't in data/build")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", help="project name (default: every project)")
    ap.add_argument("--apply", action="store_true", help="write the new decisions (default: dry run)")
    ap.add_argument("--retry-ai-rejections", action="store_true",
                    help="also re-check records whose AI answer was rejected (after a fix to the answer checks)")
    a = ap.parse_args()
    warehouse.open_warehouse()
    with pg.conn() as c:
        projects = c.execute("SELECT * FROM app.project WHERE %s::text IS NULL OR name = %s ORDER BY created_at",
                             [a.project, a.project]).fetchall()
    if not projects:
        raise SystemExit(f"No project named {a.project!r}")
    from ssi.llm import adjudicator  # optional: without a model, uncertain records stay 'possible'
    llm = adjudicator.decide if adjudicator.available() else None
    for p in projects:
        with pg.conn() as c:
            subs = c.execute("SELECT * FROM app.project_sub WHERE project_id = %s ORDER BY position", [p["project_id"]]).fetchall()
        print(f"\n== {p['name']} ({len(subs)} subs){'' if a.apply else '  [dry run]'}")
        for s in subs:
            rp = remap.plan(s)
            moves = remap_lines(rp)
            changes = plan(s, p["state"], rp["after"])
            retry = 0
            if a.retry_ai_rejections:
                with pg.conn() as c:
                    retry = c.execute("SELECT count(*) AS n FROM app.sub_match WHERE sub_id = %s AND method = 'llm_rejected'",
                                      [s["sub_id"]]).fetchone()["n"]
            if not changes and not retry and not remap.changes(rp):
                if a.apply:  # stores the inspections of decisions that predate activity_nrs
                    with ADJ.claim(str(s["sub_id"])) as claimed:
                        if claimed is not None:
                            remap.apply(claimed, remap.plan(claimed))
                if moves:
                    print(f"  {s['entered_name']}")
                    print("\n".join(moves))
                continue
            print(f"  {s['entered_name']}")
            if moves:
                print("\n".join(moves))
            for ch in changes:
                flag = f"  [{ch['red_flags']} red flags]" if ch["red_flags"] else ""
                print(f"    {ch['name'][:48]:48s} {ch['place'][:24]:24s} {ch['old']:>16s} -> {ch['new']}{flag}")
            if retry:
                print(f"    {retry} record(s) whose AI answer was rejected will be re-checked")
            if a.apply:
                with ADJ.claim(str(s["sub_id"])) as claimed:  # not while the app is resolving this sub
                    if claimed is None:
                        print("    skipped: the app is resolving this sub right now; run again in a few minutes")
                        continue
                    rp = remap.plan(claimed)  # again under the claim: the app may have moved records since the dry run
                    moved = remap.apply(claimed, rp)
                    if remap.changes(rp):
                        print(f"    {moved['moved']} record(s) moved to new keys, {moved['split']} split: "
                              f"{moved['carried']} decision(s) kept, {moved['questions']} new GC question(s), "
                              f"{moved['released']} decided again")
                    match_and_persist(claimed, p["state"])
                    if retry:
                        with pg.conn() as c:
                            c.execute("UPDATE app.sub_match SET needs_adjudication = true WHERE sub_id = %s AND method = 'llm_rejected'",
                                      [s["sub_id"]])
                    prof = P.load(claimed.get("profile_id")) if P.m3_check_enabled() else None
                    if prof:
                        m3 = ADJ.check_m3(claimed, prof, P.build)
                        if m3["moved"] or m3["confirmed"]:
                            print(f"    M3 web check: {m3['moved']} record(s) sent back, {m3['confirmed']} confirmed")
                    stats = ADJ.adjudicate(claimed, llm=llm, packet_fn=ADJ.evidence_packet)
                print(f"    applied; adjudicated {stats['clusters']} uncertain group(s), {stats['questions']} new GC question(s)")


if __name__ == "__main__":
    main()
