"""Match a GC's sub to OSHA establishments and persist the decisions (rules first; AI later, on demand)."""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, replace

from ssi.matching import adjudicate as ADJ
from ssi.matching import candidates as C
from ssi.matching.rules import (
    EXCLUDED,
    MATCHED,
    UNCERTAIN,
    Candidate,
    Decision,
    Query,
    decide,
    home_office,
    m3_collides,
    norm_city,
    one_slip,
    only_descriptor_difference,
    tokens,
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
        related_only=bool(r.get("related_only")), is_jv=bool(r.get("is_jv")),
        incorporated=bool(r.get("incorporated")),
    )


def build_query(name: str, city: str | None, state: str | None, trade: str | None) -> tuple[Query, dict]:
    d = C.describe_query(name)
    aliases = {a for a in (d["clean"], d["legal"], d["dba"]) if a}
    q = Query(clean=d["clean"], core=d["core"] or "", state=(state or "").upper() or None, city=city, trade=trade,
              tier=C.core_tier(d["core"] or "", bool(d["initials_only"])), initials_only=bool(d["initials_only"]),
              sibling=d["sibling"], aliases=aliases)
    return q, d


def alias_queries(q: Query) -> dict[str, Query]:
    """The sub's other names (legal name, DBA, licence names), each described on its own: a generic DBA (QUALITY
    ROOFING) mustn't borrow the legal name's distinctiveness and match every QUALITY ROOFING in the country."""
    out = {}
    for a in sorted(q.aliases - {q.clean}):
        d = C.describe_clean(a)
        core = d["core"] or ""
        out[a] = replace(q, clean=a, core=core, tier=C.core_tier(core, bool(d["initials_only"])),
                         initials_only=bool(d["initials_only"]), sibling=d["sibling"], aliases={a}, alias_queries={})
    return out


def correct_spelling(q: Query, rows: list[dict]) -> tuple[Query, str | None]:
    """Search OSHA's spelling when the GC's spelling is a slip of a distinctive name. Either test is enough, and
    the place is tried first:

    - place: the GC's spelling has no records of its own, and exactly one name a single slip away
      (rules.one_slip: MCKENNYS vs MCKENNEYS, 9 inspections) has a record in the GC's city. A local company
      beats a bigger one elsewhere: "Brinkmman Construction, Wheat Ridge" is BRINKMAN (a record in Wheat
      Ridge), not BRINKMANN (25 inspections, a St. Louis builder);
    - volume: a near-identical core (BRASFIELD GORRIE vs BRASFEILD GORRIE) carries at least
      SPELLING_MIN_INSPECTIONS inspections and SPELLING_RATIO times those of the GC's spelling, including
      when OSHA's data contains the same slip on a stray record.

    Only the misspelt word changes. The GC's other words stay, so the rules still compare trades:
    "Aboe Board Contracting" is searched as ABOVE BOARD CONTRACTING, not as the most-inspected ABOVE
    BOARD record (a roofer in another state). Returns the note shown to the GC."""
    if not q.core:
        return q, None
    best, note = _spelling_in_city(q, rows)
    if not best:
        best, note = _dominant_spelling(q, rows)
    if not best:
        return q, None
    clean = respell(q.clean, q.core, best) or best
    # the sub's other names (legal name, DBA, licence names) stay searchable, with the slip fixed where they have it
    fixed = {respell(a, q.core, best) or a for a in q.aliases} | {part.strip() for part in clean.split(" DBA ")}
    return replace(q, clean=clean, core=best, tier="distinctive", initials_only=False,
                   aliases=q.aliases | fixed | {clean, q.clean}), note


def respell(clean: str, core: str, best: str) -> str | None:
    """The name with its core's words spelt as OSHA spells them, word for word ("SERVICES ICE" with core ICE -> ACE
    is "SERVICES ACE", not "SERVACES ICE"). A core whose word count changed (NORTH CREEK / NORTHCREEK) is replaced
    where its words stand together; None when they don't."""
    ct, kt, bt = tokens(clean), tokens(core), tokens(best)
    if len(kt) == len(bt):
        swap = dict(zip(kt, bt))
        return " ".join(swap.get(t, t) for t in ct)
    i = next((i for i in range(len(ct) - len(kt) + 1) if ct[i:i + len(kt)] == kt), None)
    return " ".join(ct[:i] + bt + ct[i + len(kt):]) if i is not None else None


def _dominant_spelling(q: Query, rows: list[dict]) -> tuple[str | None, str | None]:
    totals: dict[str, int] = {}
    sample: dict[str, dict] = {}
    for r in rows:
        core = r["name_core"] or ""
        if core and (r["sim"] or 0) >= 0.9 and typo_equal(q.core, core):
            totals[core] = totals.get(core, 0) + (r["insp_n"] or 0)
            if core not in sample or r["clean_name"] == core or (r["insp_n"] or 0) > (sample[core]["insp_n"] or 0):
                sample[core] = r
    if not totals:
        return None, None
    best = max(totals, key=totals.get)
    if best == q.core or totals[best] < max(SPELLING_MIN_INSPECTIONS, SPELLING_RATIO * max(totals.get(q.core, 0), 1)):
        return None, None
    if C.core_tier(best, bool(sample[best]["initials_only"])) != "distinctive":
        return None, None
    return best, f"Searched OSHA's usual spelling '{best}' ({totals[best]} inspections) for '{q.core}'"


def _spelling_in_city(q: Query, rows: list[dict]) -> tuple[str | None, str | None]:
    if not (q.city and q.state) or any((r["name_core"] or "") == q.core for r in rows):
        return None, None
    found = {r["name_core"] for r in rows
             if r["name_core"] and r["state"] == q.state and norm_city(r["city"]) == norm_city(q.city)
             and one_slip(q.core, r["name_core"])}
    if len(found) != 1:  # two names a slip away: no way to tell which one the GC meant
        return None, None
    best = found.pop()
    if C.core_tier(best, False) != "distinctive":
        return None, None
    return best, f"Searched OSHA's spelling '{best}' (a record in {q.city.title()}) for '{q.core}'"


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


def _rival(r: dict, own: list[dict], trade: frozenset[str]) -> bool:
    """Whether a record is under one of the `own` records' names spelt another way, or with a trade word more."""
    core, words = r["name_core"] or "", set(tokens(r["clean_name"]))
    return bool(core) and any((core != o["name_core"] and typo_equal(core, o["name_core"]))
                              or (core == o["name_core"] and set(tokens(o["clean_name"])) < words
                                  and bool((words - set(tokens(o["clean_name"]))) & trade)) for o in own)


def m3_rivals(q: Query, m3: dict[str, dict], generic: frozenset[str],
              descriptors: frozenset[str]) -> dict[str, tuple[str, int]]:
    """{key: (the other company's name, its inspections there)} for the M3 records (`m3`: key -> row) at another
    company's address. That's an address where records the rules don't tie to the sub (not matched, as at a matched
    address) outnumber the sub's own in inspections, under the M3 record's name spelt another way (BRINKMANN for
    BRINKMAN) or with a trade word more (ABOVE BOARD CONSTRUCTION ROOFING for ABOVE BOARD CONSTRUCTION). The M3
    record is most likely that company's name misspelt or cut short: BRINKMAN CONSTRUCTORS (2 inspections) at
    Brinkmann Constructors' St. Louis office, beside BRINKMANN CONSTRUCTORS (22); ABOVE BOARD CONSTRUCTION (1) beside
    ABOVE BOARD CONSTRUCTION & ROOFING (9), a Redding roofer. A company's other names at its own office are not
    rivals: SUNRUN, TUTOR PERINI and MASTEC SERVICES beside the sub's longer names were the sub's own in the per-rule
    eval. A shared office says nothing (C.at_addresses skips them)."""
    trade = generic - descriptors
    here: dict[tuple, list[dict]] = defaultdict(list)
    for r in C.at_addresses(list(m3), exclude=set()):
        here[(r["addr_key"], (r["zip5"] or "")[:3])].append(r)
    out = {}
    for rs in here.values():
        own = [r for r in rs if r["establishment_key"] in m3]
        others = [(r, decide(q, _candidate(r, at_address=True), generic, descriptors))
                  for r in rs if r["establishment_key"] not in m3]
        rivals = [r for r, d in others if d.bucket != MATCHED and _rival(r, own, trade)]
        ours = sum(r["insp_n"] or 0 for r in own) + sum(r["insp_n"] or 0 for r, d in others if d.bucket == MATCHED)
        theirs = sum(r["insp_n"] or 0 for r in rivals)
        if own and theirs > ours:
            top = max(rivals, key=lambda r: r["insp_n"] or 0)
            out |= {r["establishment_key"]: (top["clean_name"].title(), theirs) for r in own}
    return out


def match(name: str, city: str | None, state: str | None, trade: str | None, licence: str | None = None) -> dict:
    """Run the rules. Returns {query, note, decisions: [{row, decision}]}."""
    q, described = build_query(name, city, state, trade)
    lic_names, lic_keys = licence_links(licence)
    q.aliases |= lic_names
    if described["placeholder"] or not q.clean:
        return {"query": q, "note": "Name is empty or a placeholder", "decisions": []}
    q.alias_queries = alias_queries(q)
    generic = C.generic_tokens()
    descriptors = C.descriptor_tokens()
    rows = C.search(q.clean, q.core, q.state, sorted(q.aliases))
    q, note = correct_spelling(q, rows)
    if q.tier == "person":
        # a person's name with a legal form, typed and on the record, is a registered company's (ROBERT J DEVEREAUX
        # CORP), not a sole proprietor's: rule P3 doesn't throw away its other offices. Only the records that carry
        # the person's name are checked
        q.incorporated = bool(C.with_legal_form([name]))
        if q.incorporated:
            same = [r for r in rows if r["name_core"] == q.core or r["clean_name"] in q.aliases | {q.clean}]
            legal = C.with_legal_form([n for r in same for n in (r["display_name"], *(r["name_variants"] or []))])
            for r in same:
                r["incorporated"] = any(n in legal for n in (r["display_name"], *(r["name_variants"] or [])))
    decided: dict[str, tuple[dict, object]] = {}
    for r in rows:
        decided[r["establishment_key"]] = (r, decide(q, _candidate(r), generic, descriptors))
    # M1s: the sub's own OF <PLACE> companies at its office in the GC's city (rules.home_office), before the address
    # expansion so that, matched, they pull in its other records there
    s1 = [_candidate(r) for r, d in decided.values() if d.rule_id == "S1"]
    for k, d in home_office(q, s1, descriptors).items():
        decided[k] = (decided[k][0], d)
    # M3 guards, before the address expansion so a doubtful match can't pull in records at its address. Both go to
    # the adjudicator. M3u: a same-name record in another state whose trade code none of the sub's in-state matches
    # have, under a colliding "<word> CONSTRUCTION|ELECTRIC" name, is often another company (rules.m3_collides).
    # M3a: one at another company's address (m3_rivals).
    own_trades = {r["primary_naics4"] for r, d in decided.values()
                  if d.bucket == MATCHED and d.rule_id != "M3" and r.get("primary_naics4")}
    for k, (r, d) in list(decided.items()):
        if d.rule_id == "M3" and m3_collides(r["clean_name"], r.get("primary_naics4"), own_trades):
            decided[k] = (r, Decision(UNCERTAIN, "M3u", (
                f"Same name in another state ({r['state']}), but under a trade code the sub's records here don't have; "
                f"a '<name> {r['clean_name'].split()[-1]}' name in another state is often another company")))
    for k, (rival, n) in m3_rivals(q, {k: r for k, (r, d) in decided.items() if d.rule_id == "M3"},
                                   generic, descriptors).items():
        r = decided[k][0]
        decided[k] = (r, Decision(UNCERTAIN, "M3a", (
            f"Same name in another state ({r['state']}), but at the address of {rival} ({n} inspections there), "
            "a name the rules don't tie to the sub: likely that company's record")))
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
            # the address is evidence the name-only decision didn't have: it raises a record to matched, or an
            # excluded one to uncertain (a JV, a relative or a sister company at this company's own address), the
            # same whether or not the name search had found the record first
            if d.bucket == MATCHED or (d.bucket == UNCERTAIN and (not prev or prev[1].bucket == EXCLUDED)):
                decided[k] = (prev[0] if prev else r, d)
                changed = changed or d.bucket == MATCHED
        if not changed:
            break
    # S3 at a shared office: a building with many companies pulls nothing in, except a record under the sub's own
    # distinctive name plus a word, and only as a question. D.R. Horton's head office houses ten of its companies'
    # names (so it counts as shared), among them D R HORTON INC PORTLAND, 17 inspections
    matched = [k for k, (_, d) in decided.items() if d.bucket == MATCHED] if q.tier == "distinctive" else []
    for r in C.at_addresses(matched, exclude=set(), extending=sorted({q.clean, q.core, *q.aliases} - {""})):
        k = r["establishment_key"]
        prev = decided.get(k)
        if prev and prev[1].bucket != EXCLUDED:
            continue
        d = decide(q, _candidate(r, at_address=True), generic, descriptors)
        if d.rule_id in ("S3", "J1"):
            decided[k] = (prev[0] if prev else r, d)
    # M2 at a shared office: the sub's own name, or it with a word like GROUP or CONTRACTORS added or dropped, in the
    # building (and suite) of a matched record. Clark's head office houses seven names, five of them Clark companies
    # and joint ventures, so it counts as shared, and its CLARK CONSTRUCTION records (no GROUP) were left as "related".
    # Not one such word swapped for another: ABC SERVICES and ABC CONSTRUCTION at a registered agent's office may be two
    own = {q.clean, *q.aliases} - {""}
    matched = [k for k, (_, d) in decided.items() if d.bucket == MATCHED]
    cores = sorted({q.core, *(a.core for a in q.alias_queries.values())} - {""})

    def own_name_give_or_take(name: str) -> bool:
        return name in own or any(only_descriptor_difference(name, n, descriptors) and (
            set(tokens(name)) <= set(tokens(n)) or set(tokens(n)) <= set(tokens(name))) for n in own)
    for r in C.at_addresses(matched, exclude=set(), cores=cores) if cores else []:
        k = r["establishment_key"]
        prev = decided.get(k)
        if (prev and prev[1].bucket == MATCHED) or not own_name_give_or_take(r["clean_name"]):
            continue
        d = decide(q, _candidate(r, at_address=True), generic, descriptors)
        if d.bucket == MATCHED:
            decided[k] = (prev[0] if prev else r, Decision(MATCHED, d.rule_id, (
                "Same address as a matched record, in a building several companies use; the name differs only by "
                "words like GROUP or CONTRACTORS") if d.rule_id == "M2" else d.reason))
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


def gives_way(row: dict) -> bool:
    """Whether a saved decision gives way to a rule that now matches its record (persist, and scripts/rematch.py's dry
    run): a hold on web evidence (a company profile's or the web check's question, method 'profile' or 'web', still
    possible), or the AI's decision (method 'llm' or 'llm_rejected'). The AI is asked only about records the rules
    leave uncertain, so once a rule change matches one its answer is stale: Jev excluded Hoffman's OF OREGON records at
    its head office, which M1s now matches. Not the AI's decision after the M3 web check (rule M3w): the rules would
    match the record again as plain M3, without the other company's website the check found. The GC's decisions never
    give way, and the caller keeps any red-flagged record as it is: no machine settles a red flag."""
    if row["method"] in ("profile", "web"):
        return row["bucket"] == "possible"
    return row["method"] in ("llm", "llm_rejected") and row["rule_id"] != "M3w"


def persist(sub_id: str, result: dict, conn=None) -> None:
    """Replace this sub's rule decisions; the GC's decisions on the same records are kept, and so are the AI's, unless
    a rule now matches the record. In the caller's transaction when given one (`conn`): adding subs, and moving
    decisions after a rebuild, write all or nothing. Each row stores its record's inspections, so the decision can
    follow them if a cleaning-rule change moves the key (remap.py).
    A record in an open question waits as possible for the GC's answer, whatever the rules say now; its row stays if
    the rules no longer find it. A web-evidence hold or an AI decision (gives_way) with no red flags is replaced when
    the rules now match its record on OSHA's data alone, and the record leaves any question it was in (ADJ.unask).
    Clark's CLARK CONSTRUCTION records at its head office waited in the profile's question until the shared-office M2
    matched them."""
    q: Query = result["query"]
    build_id = warehouse.meta()["build_id"]
    decs = result["decisions"]
    matched = [x for x in decs if x["decision"].bucket == MATCHED]
    uncertain = sorted([x for x in decs if x["decision"].bucket == UNCERTAIN], key=lambda x: -(x["row"].get("sim") or 0))[:UNCERTAIN_KEEP]
    excluded = sorted([x for x in decs if x["decision"].bucket == EXCLUDED], key=lambda x: -(x["row"].get("sim") or 0))[:EXCLUDED_KEEP]
    found = [x["row"]["establishment_key"] for x in matched + uncertain + excluded]
    nrs = C.members(found)
    with pg.conn(conn) as c:
        asked = {k for qn in c.execute("SELECT establishment_keys FROM app.match_question WHERE sub_id = %s "
                                       "AND answer IS NULL", [sub_id]).fetchall() for k in qn["establishment_keys"]}
        # a web-evidence hold or an AI decision the rules now match, with no red flags, gives way to the rule and
        # leaves its question
        holds = [r["establishment_key"] for r in c.execute(
            """SELECT establishment_key, method, bucket, rule_id FROM app.sub_match WHERE sub_id = %s
               AND establishment_key = ANY(%s)""",
            [sub_id, [x["row"]["establishment_key"] for x in matched]]).fetchall() if gives_way(r)]
        flagged = C.red_flag_counts(holds)
        released = {k for k in holds if not flagged.get(k)}
        c.execute("DELETE FROM app.sub_match WHERE sub_id = %s AND establishment_key = ANY(%s)", [sub_id, list(released)])
        asked -= released
        # a record a question covers by company name (C1) waits as written, saying so, while its question is open
        c.execute("""DELETE FROM app.sub_match WHERE sub_id = %s AND method = 'rule'
                     AND (establishment_key = ANY(%s) OR NOT establishment_key = ANY(%s))
                     AND NOT (rule_id = 'C1' AND establishment_key = ANY(%s))""", [sub_id, found, list(asked), list(asked)])
        c.execute("""UPDATE app.sub_match SET bucket = 'possible', needs_adjudication = false
                     WHERE sub_id = %s AND method = 'rule' AND establishment_key = ANY(%s)""", [sub_id, list(asked)])
        kept = {r["establishment_key"] for r in c.execute(
            "SELECT establishment_key FROM app.sub_match WHERE sub_id = %s", [sub_id]).fetchall()}
        for group, bucket, needs in ((matched, "matched", False), (uncertain, "possible", True), (excluded, "excluded", False)):
            for x in group:
                r, d = x["row"], x["decision"]
                if r["establishment_key"] in kept:
                    continue
                held = r["establishment_key"] in asked  # not for the AI either: the question is the GC's
                c.execute(
                    """INSERT INTO app.sub_match (sub_id, establishment_key, bucket, method, rule_id, rationale,
                                                  evidence, needs_adjudication, decided_by, build_id, activity_nrs)
                       VALUES (%s, %s, %s, 'rule', %s, %s, %s, %s, 'rules', %s, %s)""",
                    [sub_id, r["establishment_key"], "possible" if held else bucket, d.rule_id,
                     f"{d.reason}; waiting for your answer to its question" if held else d.reason,
                     json.dumps(_evidence(r, d, q), default=str), needs and not held, build_id,
                     nrs.get(r["establishment_key"])])
        if released:
            ADJ.unask(c, c.execute("SELECT * FROM app.project_sub WHERE sub_id = %s", [sub_id]).fetchone(), released)
        c.execute("UPDATE app.project_sub SET matched_build = %s, adjudicated_at = NULL WHERE sub_id = %s",
                  [build_id, sub_id])
        if result.get("note"):
            c.execute("""INSERT INTO app.sub_match (sub_id, establishment_key, bucket, method, rule_id, rationale,
                                                    decided_by, build_id)
                         VALUES (%s, '__note__', 'excluded', 'rule', 'NOTE', %s, 'rules', %s)
                         ON CONFLICT (sub_id, establishment_key) DO UPDATE SET rationale = EXCLUDED.rationale""",
                      [sub_id, result["note"], build_id])


def match_sub(sub: dict, project_state: str | None) -> dict:
    """The rules for a saved sub (warehouse only; nothing written)."""
    return match(sub["entered_name"], sub.get("entered_city"), sub.get("entered_state") or project_state, sub.get("trade"),
                 sub.get("licence"))


def match_and_persist(sub: dict, project_state: str | None, conn=None) -> dict:
    result = match_sub(sub, project_state)
    persist(str(sub["sub_id"]), result, conn)
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
