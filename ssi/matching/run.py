"""Match a GC's sub to OSHA establishments and persist the decisions (rules first; AI later, on demand)."""
from __future__ import annotations

import json
from dataclasses import asdict

from ssi.matching import candidates as C
from ssi.matching.rules import (
    EXCLUDED,
    MATCHED,
    UNCERTAIN,
    Candidate,
    Decision,
    Query,
    decide,
    typo_equal,
)
from ssi.store import pg, warehouse

EXCLUDED_KEEP = 25      # show the closest lookalikes, not hundreds
UNCERTAIN_KEEP = 200
# Adopt OSHA's spelling only when it clearly dominates: COLMEX (1 inspection) is a real company, not a
# slip of COMEX (5); BRASFEILD (1) is a slip of BRASFIELD (hundreds).
SPELLING_MIN_INSPECTIONS = 10
SPELLING_RATIO = 10


def _candidate(r: dict, at_address: bool = False) -> Candidate:
    return Candidate(
        establishment_key=r["establishment_key"], clean_name=r["clean_name"], name_core=r["name_core"] or "",
        legal_name=r["legal_name"], dba_name=r["dba_name"], state=r["state"], city=r["city"], zip5=r["zip5"],
        addr_key=r["addr_key"], primary_naics4=r["primary_naics4"], sibling_suffix=r["sibling_suffix"],
        initials_only=bool(r["initials_only"]), at_matched_address=at_address,
        related_only=bool(r.get("related_only")),
    )


def build_query(name: str, city: str | None, state: str | None, trade: str | None) -> tuple[Query, dict]:
    d = C.describe_query(name)
    aliases = {a for a in (d["clean"], d["legal"], d["dba"]) if a}
    q = Query(clean=d["clean"], core=d["core"] or "", state=(state or "").upper() or None, city=city, trade=trade,
              tier=C.core_tier(d["core"] or "", bool(d["initials_only"])), initials_only=bool(d["initials_only"]),
              sibling=d["sibling"], aliases=aliases)
    return q, d


def correct_spelling(q: Query, rows: list[dict]) -> tuple[Query, str | None]:
    """Adopt OSHA's dominant spelling when the GC's spelling is a slip of a distinctive name.

    Triggers when a near-identical distinctive core (BRASFIELD GORRIE vs BRASFEILD GORRIE) carries at
    least SPELLING_MIN_INSPECTIONS inspections and SPELLING_RATIO times those of the GC's spelling,
    including when OSHA's data contains the same slip on a stray record. Returns the note shown to the GC."""
    if not q.core:
        return q, None
    totals: dict[str, int] = {}
    sample: dict[str, dict] = {}
    for r in rows:
        core = r["name_core"] or ""
        if core and (r["sim"] or 0) >= 0.9 and typo_equal(q.core, core):
            totals[core] = totals.get(core, 0) + (r["insp_n"] or 0)
            if core not in sample or r["clean_name"] == core or (r["insp_n"] or 0) > (sample[core]["insp_n"] or 0):
                sample[core] = r
    if not totals:
        return q, None
    best = max(totals, key=totals.get)
    if best == q.core or totals[best] < max(SPELLING_MIN_INSPECTIONS, SPELLING_RATIO * max(totals.get(q.core, 0), 1)):
        return q, None
    r = sample[best]
    tier = C.core_tier(best, bool(r["initials_only"]))
    if tier != "distinctive":
        return q, None
    clean = r["clean_name"] if r["name_core"] == best else best
    q2 = Query(clean=clean, core=best, state=q.state, city=q.city, trade=q.trade, tier=tier, initials_only=False,
               sibling=r["sibling_suffix"], aliases={clean, q.clean})
    return q2, f"Searched OSHA's usual spelling '{best}' ({totals[best]} inspections) for '{q.core}'"


def licence_links(licence: str | None) -> tuple[set[str], set[str]]:
    """Names and linked establishments for a licence number / UBI the GC entered."""
    if not licence or not licence.strip():
        return set(), set()
    lic = licence.strip().upper()
    rows = warehouse.rows("SELECT * FROM ref_ext.licence WHERE upper(number) = ? OR upper(entity_id) = ?", [lic, lic])
    names = {n for r in rows for n in (r["clean_name"], r["dba_clean"]) if n}
    keys = {r["establishment_key"] for r in warehouse.rows(
        """SELECT DISTINCT k.establishment_key FROM entity.ref_link k JOIN ref_ext.licence l
           ON k.source = 'licence:' || l.source AND k.ref_id = l.number
           WHERE k.method IN ('M1', 'M2') AND (upper(l.number) = ? OR upper(l.entity_id) = ?)""", [lic, lic])}
    return names, keys


def match(name: str, city: str | None, state: str | None, trade: str | None, licence: str | None = None) -> dict:
    """Run the rules. Returns {query, note, decisions: [{row, decision}]}."""
    q, described = build_query(name, city, state, trade)
    lic_names, lic_keys = licence_links(licence)
    q.aliases |= lic_names
    if described["placeholder"] or not q.clean:
        return {"query": q, "note": "Name is empty or a placeholder", "decisions": []}
    generic = C.generic_tokens()
    descriptors = C.descriptor_tokens()
    rows = C.search(q.clean, q.core, q.state, sorted(q.aliases))
    q, note = correct_spelling(q, rows)
    decided: dict[str, tuple[dict, object]] = {}
    for r in rows:
        decided[r["establishment_key"]] = (r, decide(q, _candidate(r), generic, descriptors))
    # address expansion (two passes): records at a matched address whose name differs only by spelling
    excluded_at_address: dict[str, dict] = {}
    for _ in range(2):
        matched = [k for k, (_, d) in decided.items() if d.bucket == MATCHED]
        new = C.at_addresses(matched, exclude=set())
        changed = False
        for r in new:
            k = r["establishment_key"]
            prev = decided.get(k)
            if prev and prev[1].bucket == MATCHED:
                continue
            d = decide(q, _candidate(r, at_address=True), generic, descriptors)
            if d.bucket == EXCLUDED:
                excluded_at_address[k] = prev[0] if prev else r
            if d.bucket == MATCHED or not prev:
                if d.bucket == MATCHED or d.bucket == UNCERTAIN:
                    decided[k] = (prev[0] if prev else r, d)
                    changed = changed or d.bucket == MATCHED
        if not changed:
            break
    # Red-flag safety net: a rule may not throw away a red-flagged record at an address this company uses
    # (a branch filed under another name, e.g. Barnhart's Oklahoma City fatality). It goes to the GC instead.
    still_excluded = [k for k in excluded_at_address if k not in decided or decided[k][1].bucket == EXCLUDED]
    for k, n in C.red_flag_counts(still_excluded).items():
        if n:
            decided[k] = (excluded_at_address[k], Decision(
                UNCERTAIN, "R1", "Red flags at an address this company uses; needs your confirmation"))
    if lic_keys:  # records linked (exact name + zip/address) to the licence the GC entered
        missing = [k for k in lic_keys if k not in decided]
        if missing:
            for r in C.establishments(missing):
                decided[r["establishment_key"]] = (r, None)
        for k in lic_keys:
            if k in decided:
                decided[k] = (decided[k][0], Decision(MATCHED, "L1", "Linked to the licence number you entered"))
        note = (note + "; " if note else "") + f"Licence {licence.strip()} linked {len(lic_keys)} OSHA record(s)"
    out = [{"row": r, "decision": d} for r, d in decided.values()]
    return {"query": q, "note": note, "decisions": out}


def _evidence(r: dict, d, q: Query) -> dict:
    return {
        "rule": d.rule_id, "reason": d.reason, "similarity": round(r["sim"], 3) if r.get("sim") is not None else None,
        "name": r["clean_name"], "state": r["state"], "city": r["city"], "zip": r["zip5"], "address": r["address"],
        "years": [r["first_seen"], r["last_seen"]], "inspections": r["insp_n"], "naics4": r["primary_naics4"],
        "related_only": bool(r.get("related_only")),
        "query": {"clean": q.clean, "core": q.core, "tier": q.tier},
    }


def persist(sub_id: str, result: dict) -> None:
    """Replace this sub's rule decisions; GC overrides and AI decisions on the same records are kept."""
    q: Query = result["query"]
    build_id = warehouse.meta()["build_id"]
    decs = result["decisions"]
    matched = [x for x in decs if x["decision"].bucket == MATCHED]
    uncertain = sorted([x for x in decs if x["decision"].bucket == UNCERTAIN], key=lambda x: -(x["row"].get("sim") or 0))[:UNCERTAIN_KEEP]
    excluded = sorted([x for x in decs if x["decision"].bucket == EXCLUDED], key=lambda x: -(x["row"].get("sim") or 0))[:EXCLUDED_KEEP]
    with pg.conn() as c:
        c.execute("DELETE FROM app.sub_match WHERE sub_id = %s AND method = 'rule'", [sub_id])
        kept = {r["establishment_key"] for r in c.execute(
            "SELECT establishment_key FROM app.sub_match WHERE sub_id = %s", [sub_id]).fetchall()}
        for group, bucket, needs in ((matched, "matched", False), (uncertain, "possible", True), (excluded, "excluded", False)):
            for x in group:
                r, d = x["row"], x["decision"]
                if r["establishment_key"] in kept:
                    continue
                c.execute(
                    """INSERT INTO app.sub_match (sub_id, establishment_key, bucket, method, rule_id, rationale,
                                                  evidence, needs_adjudication, decided_by, build_id)
                       VALUES (%s, %s, %s, 'rule', %s, %s, %s, %s, 'rules', %s)""",
                    [sub_id, r["establishment_key"], bucket, d.rule_id, d.reason,
                     json.dumps(_evidence(r, d, q), default=str), needs, build_id])
        c.execute("UPDATE app.project_sub SET matched_build = %s, adjudicated_at = NULL WHERE sub_id = %s",
                  [build_id, sub_id])
        if result.get("note"):
            c.execute("""INSERT INTO app.sub_match (sub_id, establishment_key, bucket, method, rule_id, rationale,
                                                    decided_by, build_id)
                         VALUES (%s, '__note__', 'excluded', 'rule', 'NOTE', %s, 'rules', %s)
                         ON CONFLICT (sub_id, establishment_key) DO UPDATE SET rationale = EXCLUDED.rationale""",
                      [sub_id, result["note"], build_id])


def match_and_persist(sub: dict, project_state: str | None) -> dict:
    result = match(sub["entered_name"], sub.get("entered_city"), sub.get("entered_state") or project_state, sub.get("trade"),
                   sub.get("licence"))
    persist(str(sub["sub_id"]), result)
    return result


if __name__ == "__main__":  # quick manual check
    import sys
    res = match(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None, sys.argv[3] if len(sys.argv) > 3 else None, None)
    print("query:", asdict(res["query"]), "note:", res["note"])
    for b in (MATCHED, UNCERTAIN, EXCLUDED):
        xs = [x for x in res["decisions"] if x["decision"].bucket == b]
        print(f"\n{b.upper()} ({len(xs)}; inspections {sum(x['row']['insp_n'] for x in xs)})")
        for x in sorted(xs, key=lambda x: -x['row']['insp_n'])[:8]:
            r, d = x["row"], x["decision"]
            print(f"  {d.rule_id:7s} {r['clean_name'][:40]:40s} {r['city'] or '':14s} {r['state'] or ''} {r['zip5'] or ''} insp={r['insp_n']}")
