"""Named queries: the only code that reads OSHA facts for a sub. The GC view and the foreman's tools call
the same functions, so a business term ("serious", "fall protection", "open case") means the same thing
everywhere, and every figure carries the inspection IDs behind it."""
from __future__ import annotations

import re
from collections import Counter
from datetime import date
from urllib.parse import quote, urlencode

from ssi import config
from ssi.api import schemas as S
from ssi.matching import candidates as C
from ssi.matching import verify as V
from ssi.matching.trades import NAICS4_LABELS, trade_naics4
from ssi.scoring.verdict import (
    VERDICT_LABELS,
    Facts,
    HazardFact,
    RedFlagFact,
    evaluate,
    one_event_per_visit,
    years_before,
)
from ssi.store import pg, warehouse

HAZARD_FALLBACK = {"other": "Other / unmapped"}
INSP_TYPE_FALLBACK = {
    "A": "Accident", "B": "Complaint", "C": "Referral", "D": "Monitoring", "E": "Variance", "F": "Follow-up",
    "G": "Unprogrammed related", "H": "Planned (programmed)", "I": "Programmed related", "J": "Unprogrammed other",
    "K": "Programmed other", "L": "Other", "M": "Fatality/catastrophe", "N": "Other",
}
VIOL_TYPE_FALLBACK = {"S": "Serious", "W": "Willful", "R": "Repeat", "O": "Other-than-serious", "U": "Unclassified",
                      "P": "Undocumented type 'P'"}
# OSHA fatality/catastrophe investigations of this employer (not another employer's site, not a catastrophe
# whose published detail shows no death): a self-reported death in the same year is already on record
OSHA_FATALITY_KINDS = {"fatality_cited", "fatality_inspected_not_cited", "fatality_pending", "fatcat_cited",
                       "fatcat_not_cited", "fatcat_no_inspection"}
RED_FLAG_LABELS = {
    "fatality_cited": "Fatality, employer cited",
    "fatality_inspected_not_cited": "Fatality on site, employer not cited for serious violations",
    "fatcat_cited": "Fatality/catastrophe investigation, cited (details not yet published)",
    "fatcat_not_cited": "Fatality/catastrophe investigation, not cited (details not published)",
    "fatality_pending": "Fatality/catastrophe investigation still open, outcome not yet published",
    "fatcat_site_cited": "Cited on a site where a fatality/catastrophe is under investigation",
    "catastrophe_cited": "Catastrophe investigation (serious injuries, no death), cited",
    "fatcat_no_inspection": "Fatality/catastrophe reported, OSHA did not inspect this employer",
    "willful": "Willful violation",
    "repeat": "Repeat violation",
    "fta": "Failure to abate",
}


def osha_search_url(name: str | None, state: str | None, open_date) -> str:
    """osha.gov search for one inspection: employer name as OSHA recorded it, site state, opening day."""
    if not name or not open_date:
        return S.OSHA_SEARCH_PAGE
    y, m, d = str(open_date)[:10].split("-")
    q = {"establishment": name, **({"state": state} if state else {}), "officetype": "all", "office": "all",
         "sitezip": "100000", "startmonth": m, "startday": d, "startyear": y, "endmonth": m, "endday": d,
         "endyear": y, "p_case": "all", "p_violations_exist": "both"}
    return f"{S.OSHA_SEARCH_URL}?{urlencode(q, quote_via=quote)}"


def url(activity_nr: int) -> str:
    r = warehouse.one("SELECT estab_name_raw, site_state, open_date FROM osha.inspection WHERE activity_nr = ?",
                      [activity_nr])
    return osha_search_url(r["estab_name_raw"], r["site_state"], r["open_date"]) if r else S.OSHA_SEARCH_PAGE


def _labels(table: str, key: str, value: str, fallback: dict) -> dict:
    try:
        rs = warehouse.rows(f"SELECT {key} AS k, {value} AS v FROM ref.{table}")
        d = {r["k"]: r["v"] for r in rs}
        return {**fallback, **d} if d else fallback
    except Exception:
        return fallback


def hazard_labels() -> dict:
    return _labels("hazard_category", "hazard_code", "label", HAZARD_FALLBACK)


def insp_type_labels() -> dict:
    return _labels("inspection_type", "code", "label", INSP_TYPE_FALLBACK)


def viol_type_labels() -> dict:
    return _labels("violation_type", "code", "label", VIOL_TYPE_FALLBACK)


def as_of() -> date:
    return date.fromisoformat(warehouse.meta()["data_as_of"])


# --- scope: which establishments count for a sub ---------------------------------------------------
def scope(sub_id: str) -> dict:
    with pg.conn() as c:
        rows = c.execute("SELECT * FROM app.sub_match WHERE sub_id = %s", [sub_id]).fetchall()
        qs = c.execute("SELECT * FROM app.match_question WHERE sub_id = %s ORDER BY created_at", [sub_id]).fetchall()
        # other subs on the project with a matched record in common (likely the same company entered twice)
        same = c.execute("""SELECT o.sub_id::text AS sub_id, o.entered_name AS name
                            FROM app.project_sub me
                            JOIN app.project_sub o ON o.project_id = me.project_id AND o.sub_id <> me.sub_id
                            WHERE me.sub_id = %s AND EXISTS (
                              SELECT 1 FROM app.sub_match a
                              JOIN app.sub_match b ON b.sub_id = o.sub_id AND b.establishment_key = a.establishment_key
                              WHERE a.sub_id = me.sub_id AND a.bucket = 'matched' AND b.bucket = 'matched')
                            ORDER BY o.position, o.created_at""", [sub_id]).fetchall()
    out = {"matched": [], "possible": [], "excluded": [], "note": None, "rows": {}, "questions": qs, "same_records_as": same}
    for r in rows:
        if r["establishment_key"] == "__note__":
            out["note"] = r["rationale"]
            continue
        out[r["bucket"]].append(r["establishment_key"])
        out["rows"][r["establishment_key"]] = r
    out["needs_adjudication"] = any(r["needs_adjudication"] for r in rows)
    out["pending_questions"] = [q for q in qs if q["answer"] is None]
    return out


def red_flag_questions(questions: list[dict]) -> list[dict]:
    """The open match questions whose answer can add a red flag: a red-flag question (kind 'red_flag', or NULL), or any
    other with a red-flagged record. Never the web check's: its questions are suggestions about records that don't
    count yet."""
    questions = [q for q in questions if q.get("kind") != "web"]
    other = [q for q in questions if (q.get("kind") or "red_flag") != "red_flag"]
    flagged = C.red_flag_counts(sorted({k for q in other for k in q["establishment_keys"]}))
    return [q for q in questions if (q.get("kind") or "red_flag") == "red_flag"
            or any(flagged.get(k) for k in q["establishment_keys"])]


def question_facts(questions: list[dict]) -> dict[str, int]:
    """Open match questions as verdict facts, by what an answer can change: the ones that can add a red flag
    (red_flag_questions) make it Review. The rest hold records that are possible, counted neither way: records at
    locations a company profile lists, and others (a data update regrouped records). The web check's count for nothing."""
    at_stake = red_flag_questions(questions)
    rest = [q for q in questions if q.get("kind") != "web" and q not in at_stake]
    return {"pending_questions": len(at_stake),
            "pending_profile_records": sum(len(q["establishment_keys"]) for q in rest if q["kind"] == "profile"),
            "pending_other_questions": sum(1 for q in rest if q["kind"] != "profile")}


_KEY_RE = re.compile(r"^[0-9a-f]{32}$")


def _in(keys: list[str]) -> str:
    """Literal IN-list of establishment keys (md5 hex, validated, so inlining is injection-safe).
    DuckDB filters a literal list ~2.5x faster than an IN (SELECT unnest(?)) subquery."""
    safe = [k for k in keys if _KEY_RE.match(k)]
    return "(" + ",".join(f"'{k}'" for k in safe) + ")" if safe else "(NULL)"


# --- facts -----------------------------------------------------------------------------------------
def year_rows(keys: list[str]) -> list[dict]:
    if not keys:
        return []
    return warehouse.rows(f"SELECT * FROM mart.establishment_year WHERE establishment_key IN {_in(keys)}")


def red_flags(keys: list[str]) -> list[S.RedFlag]:
    if not keys:
        return []
    hl = hazard_labels()
    rs = warehouse.rows(
        f"""SELECT r.*, i.estab_name_raw AS establishment_name, i.site_state AS insp_state, i.open_date AS insp_open
            FROM mart.red_flag r JOIN osha.inspection i USING (activity_nr)
            WHERE r.establishment_key IN {_in(keys)}
            ORDER BY r.event_date DESC NULLS LAST, r.activity_nr, r.citation_id NULLS FIRST""")
    return [S.RedFlag(kind=r["kind"], label=RED_FLAG_LABELS.get(r["kind"], r["kind"]),
                      event_date=str(r["event_date"]) if r["event_date"] else None, activity_nr=r["activity_nr"],
                      citation_id=r["citation_id"], standard=r["standard_cite"],
                      hazard_label=hl.get(r["hazard_code"], r["hazard_code"]) if r["hazard_code"] else None,
                      penalty_initial=float(r["penalty_initial"]) if r["penalty_initial"] is not None else None,
                      penalty_current=float(r["penalty_current"]) if r["penalty_current"] is not None else None,
                      case_open=bool(r["case_open"]), case_provisional=bool(r["case_provisional"]),
                      shared_site_n=max((r["shared_site_n"] or 1) - 1, 0),
                      establishment_name=r["establishment_name"],
                      url=osha_search_url(r["establishment_name"], r["insp_state"], r["insp_open"])) for r in rs]


def window_since(window: int) -> date:
    """First day of "the last N years": N years before the data date (dates, not calendar years)."""
    return years_before(as_of(), window)


def hazards(keys: list[str], window: int) -> list[S.HazardRow]:
    if not keys:
        return []
    hl = hazard_labels()
    rs = warehouse.rows(
        f"""SELECT hazard_code, sum(viol_n) AS citations, sum(viol_serious_plus_n) AS serious_plus,
                   sum(insp_n) AS inspections, min(year) AS first_year, max(year) AS last_year
            FROM mart.establishment_hazard_year WHERE establishment_key IN {_in(keys)}
            GROUP BY 1 ORDER BY citations DESC""")
    tops = warehouse.rows(
        f"""SELECT v.hazard_code, v.section_key, count(*) AS n
            FROM osha.violation v JOIN osha.inspection i USING (activity_nr)
            WHERE i.establishment_key IN {_in(keys)} AND NOT v.is_deleted AND v.section_key IS NOT NULL
            GROUP BY 1, 2 ORDER BY 3 DESC""")
    top_by: dict[str, list[str]] = {}
    for t in tops:
        top_by.setdefault(t["hazard_code"], [])
        if len(top_by[t["hazard_code"]]) < 3:
            top_by[t["hazard_code"]].append(t["section_key"])
    return [S.HazardRow(hazard_code=r["hazard_code"], label=hl.get(r["hazard_code"], r["hazard_code"]),
                        citations=int(r["citations"]), serious_plus=int(r["serious_plus"]),
                        inspections=int(r["inspections"]), first_year=r["first_year"], last_year=r["last_year"],
                        top_standards=top_by.get(r["hazard_code"], [])) for r in rs]


def hazard_evidence(keys: list[str], hazard_code: str, limit: int = 20) -> list[int]:
    rs = warehouse.rows(
        f"""SELECT DISTINCT v.activity_nr, i.open_date FROM osha.violation v JOIN osha.inspection i USING (activity_nr)
            WHERE i.establishment_key IN {_in(keys)} AND v.hazard_code = ? AND NOT v.is_deleted
            ORDER BY i.open_date DESC LIMIT {limit}""", [hazard_code])
    return [r["activity_nr"] for r in rs]


def trend(keys: list[str]) -> list[S.YearRow]:
    rs = year_rows(keys)
    by: dict[int, Counter] = {}
    pen: dict[int, float] = {}
    for r in rs:
        c = by.setdefault(r["year"], Counter())
        for k in ("insp_conducted_n", "insp_with_cit_n", "viol_n", "viol_serious_plus_n", "viol_w_n", "viol_r_n"):
            c[k] += r[k] or 0
        if r["penalty_current_sum"] is not None:
            pen[r["year"]] = pen.get(r["year"], 0.0) + float(r["penalty_current_sum"])
    return [S.YearRow(year=y, inspections=c["insp_conducted_n"], inspections_with_citations=c["insp_with_cit_n"],
                      citations=c["viol_n"], serious_plus=c["viol_serious_plus_n"], willful=c["viol_w_n"],
                      repeat=c["viol_r_n"], penalty_current=pen.get(y)) for y, c in sorted(by.items())]


INSPECTION_COLS = """i.activity_nr, i.open_date::VARCHAR AS open_date, i.close_date::VARCHAR AS close_date, i.is_open,
    i.is_provisional, i.no_inspection,
    i.insp_type, i.site_city, i.site_state, i.jurisdiction, i.estab_name_raw, i.citation_n, i.serious_plus_n,
    i.penalty_initial, i.penalty_current, i.fatality_status, i.site_group_n, i.dq_flags"""


def _inspection_row(r: dict, itl: dict) -> S.InspectionRow:
    return S.InspectionRow(
        activity_nr=r["activity_nr"], open_date=r["open_date"] or "", close_date=r["close_date"], is_open=bool(r["is_open"]),
        is_provisional=bool(r["is_provisional"]), no_inspection=bool(r["no_inspection"]),
        insp_type_label=itl.get(r["insp_type"], r["insp_type"] or "Unknown"), site_city=r["site_city"],
        site_state=r["site_state"], jurisdiction=r["jurisdiction"], establishment_name=r["estab_name_raw"],
        citations=r["citation_n"] or 0, serious_plus=r["serious_plus_n"] or 0,
        penalty_initial=float(r["penalty_initial"]) if r["penalty_initial"] is not None else None,
        penalty_current=float(r["penalty_current"]) if r["penalty_current"] is not None else None,
        fatality_status=r["fatality_status"] if r["fatality_status"] in
        ("fatality_cited", "fatality_inspected_not_cited", "fatality_pending", "fatcat_cited", "fatcat_not_cited",
         "fatcat_site_cited", "catastrophe_cited", "fatcat_no_inspection", "accident_outcome_unknown") else "none",
        shared_site_n=max((r["site_group_n"] or 1) - 1, 0), dq_flags=list(r["dq_flags"] or []),
        url=osha_search_url(r["estab_name_raw"], r["site_state"], r["open_date"]))


def inspections(keys: list[str], offset: int = 0, limit: int = 25, provisional_only: bool = False,
                hazard: str | None = None, since_year: int | None = None) -> list[S.InspectionRow]:
    """provisional_only: open cases with a citation that isn't final yet (an open case whose citations are all
    final orders is only waiting on penalties, so nothing about it can change)."""
    if not keys:
        return []
    where, params = [f"i.establishment_key IN {_in(keys)}"], []
    if provisional_only:
        where.append("i.is_provisional")
    if since_year:
        where.append("year(i.open_date) >= ?")
        params.append(since_year)
    if hazard:
        where.append("EXISTS (SELECT 1 FROM osha.violation v WHERE v.activity_nr = i.activity_nr AND v.hazard_code = ? AND NOT v.is_deleted)")
        params.append(hazard)
    rs = warehouse.rows(f"""SELECT {INSPECTION_COLS} FROM osha.inspection i WHERE {' AND '.join(where)}
                            ORDER BY i.open_date DESC NULLS LAST LIMIT {int(limit)} OFFSET {int(offset)}""", params)
    itl = insp_type_labels()
    return [_inspection_row(r, itl) for r in rs]


def inspection_detail(activity_nr: int) -> S.InspectionDetail | None:
    r = warehouse.one(f"SELECT {INSPECTION_COLS} FROM osha.inspection i WHERE i.activity_nr = ?", [activity_nr])
    if not r:
        return None
    hl, vtl = hazard_labels(), viol_type_labels()
    cits = warehouse.rows("""SELECT * FROM osha.violation WHERE activity_nr = ? ORDER BY citation_id""", [activity_nr])
    accs = warehouse.rows("""SELECT a.* FROM osha.accident a JOIN osha.accident_inspection l USING (summary_nr)
                             WHERE l.activity_nr = ?""", [activity_nr])
    base = _inspection_row(r, insp_type_labels()).model_dump()
    return S.InspectionDetail(
        **base,
        citation_rows=[S.CitationRow(
            citation_id=v["citation_id"], viol_type=v["viol_type"], viol_type_label=vtl.get(v["viol_type"], "Unknown"),
            standard=v["standard_cite"] or v["standard_raw"], hazard_label=hl.get(v["hazard_code"], v["hazard_code"]),
            issued=str(v["issued_on"]) if v["issued_on"] else None,
            penalty_initial=float(v["penalty_initial"]) if v["penalty_initial"] is not None else None,
            penalty_current=float(v["penalty_current"]) if v["penalty_current"] is not None else None,
            is_deleted=bool(v["is_deleted"]), is_fta=bool(v["is_fta"]), contested=bool(v["contested"])) for v in cits],
        accidents=[S.AccidentInfo(summary_nr=a["summary_nr"], event_date=str(a["event_date"]) if a["event_date"] else None,
                                  description=a["description"], narrative=a["narrative"], fatal_n=a["fatal_n"],
                                  injured_n=a["injured_n"], employers_on_site=a["employers_on_site"]) for a in accs],
    )


def primary_trade(keys: list[str], entered_trade: str | None) -> str | None:
    if keys:
        rs = warehouse.rows(f"""SELECT primary_naics4 AS n4, sum(insp_n) AS w FROM entity.establishment
                                WHERE establishment_key IN {_in(keys)} AND primary_naics4 LIKE '23%'
                                GROUP BY 1 ORDER BY 2 DESC LIMIT 1""")
        if rs:
            return rs[0]["n4"]
    t = sorted(trade_naics4(entered_trade))
    return t[0] if t else None


def benchmark(naics4: str | None, window: int) -> dict | None:
    rs = warehouse.rows(
        """SELECT * FROM mart.trade_benchmark
           WHERE window_years = ? AND peer_n >= ? AND
                 ((level = 'naics4' AND trade_code = ?) OR (level = 'naics3' AND trade_code = left(?, 3)) OR level = 'all')
           ORDER BY CASE level WHEN 'naics4' THEN 0 WHEN 'naics3' THEN 1 ELSE 2 END LIMIT 1""",
        [window, config.BENCHMARK_MIN_PEERS, naics4 or "", naics4 or ""])
    if not rs:
        return None
    b = rs[0]
    b["label"] = (NAICS4_LABELS.get(b["trade_code"], "construction firms") if b["level"] == "naics4"
                  else "construction firms" if b["level"] == "all" else f"NAICS {b['trade_code']} firms").lower()
    return b


def unmoved(sc: dict) -> tuple[list[str], set[str]]:
    """(stale, present). stale: the sub's matched and asked-about records whose inspections this build has under a key
    the sub isn't counting: decisions made on an earlier build whose records a rebuild regrouped (re-keyed, split),
    not moved onto this one yet (ssi/matching/remap.py follow_all). Their history isn't counted until they are, so
    the sub is Review meanwhile, never clean. Not a record whose inspections have all left the data (older than the
    history window: nothing to count), nor one merged into a record the sub has matched. A row saved without its
    inspections counts when its key is gone (can't tell). present: those of the keys this build has."""
    rows = sc["rows"]
    check = [k for k in dict.fromkeys(sc["matched"] + [k for q in sc["pending_questions"] for k in q["establishment_keys"]])
             if k in rows]
    if not check:
        return [], set()
    present = {r["establishment_key"] for r in warehouse.rows(
        "SELECT establishment_key FROM entity.establishment WHERE establishment_key IN (SELECT unnest(?::VARCHAR[]))",
        [check])}
    counted = {k for k in sc["matched"] if k in present}
    stored = {k: set(rows[k].get("activity_nrs") or []) for k in check}
    nrs = sorted({n for s in stored.values() for n in s})
    now = {r["activity_nr"]: r["establishment_key"] for r in warehouse.rows(
        """SELECT activity_nr, establishment_key FROM entity.establishment_member
           WHERE activity_nr IN (SELECT unnest(?::BIGINT[]))""", [nrs])} if nrs else {}
    stale = [k for k in check
             if (k not in present and not stored[k])
             or any(n in now and now[n] != k and now[n] not in counted for n in stored[k])]
    return stale, present


def unresolved_red_flags(sc: dict) -> int:
    """Possible records with red flags still waiting for the adjudicator. Each becomes a GC question whichever way the
    AI leans, so until then the sub is Review, as with an open red-flag question: a sub added and never resolved (the
    page closed before the adjudicator ran) mustn't read as clean."""
    waiting = [k for k in sc["possible"] if sc["rows"][k]["needs_adjudication"]]
    return sum(1 for n in C.red_flag_counts(waiting).values() if n) if waiting else 0


def compute(sub: dict, project: dict) -> dict:
    """Everything the card, the detail page and the foreman need for one sub."""
    sc = scope(str(sub["sub_id"]))
    # a matched or asked-about record a rebuild regrouped counts nothing until it's moved: Review meanwhile
    stale, present = unmoved(sc)
    keys = [k for k in sc["matched"] if k in present]
    window = int(project["lookback_years"])
    aof = as_of()
    since = window_since(window)
    yrs = year_rows(keys)
    tot = Counter()
    for r in yrs:  # files where OSHA conducted no inspection are not inspections (insp_n - insp_conducted_n)
        for k in ("insp_n", "insp_conducted_n", "insp_rated_n", "viol_serious_plus_n"):
            tot[k] += r[k] or 0
    if keys:  # the window is dates (the last N years before the data date), so count from the inspections
        w = warehouse.one(
            f"""SELECT count(*) FILTER (WHERE NOT no_inspection) AS insp_n,
                       count(*) FILTER (WHERE coalesce(insp_type, '') NOT IN ('F', 'D', 'E') AND NOT no_inspection)
                         AS insp_rated_n,
                       coalesce(sum(serious_plus_n), 0) AS viol_serious_plus_n
                FROM osha.inspection WHERE establishment_key IN {_in(keys)} AND open_date >= ?""", [since])
        for k in ("insp_n", "insp_rated_n", "viol_serious_plus_n"):
            tot["w_" + k] = int(w[k] or 0)
    flags = red_flags(keys)
    # the visit of each flagged inspection (same site and day): a safety and a health inspection of one visit are
    # one visit, for repeat patterns and for fatality/catastrophe events
    flagged = {f.activity_nr for f in flags}
    visit = {r["activity_nr"]: r["visit_id"] for r in warehouse.rows(
        f"SELECT activity_nr, visit_id FROM osha.inspection WHERE activity_nr IN ({','.join(map(str, flagged))})")
    } if flagged else {}
    flags = one_event_per_visit(flags, visit)
    hz = hazards(keys, window)
    open_serious = [i.activity_nr for i in inspections(keys, limit=50, provisional_only=True) if i.serious_plus > 0]
    n4 = primary_trade(keys, sub.get("trade"))
    bm = benchmark(n4, window)
    hfacts = [HazardFact(h.hazard_code, h.label, h.inspections, 0, h.first_year, h.last_year) for h in hz]
    if hfacts:  # patterns count separate visits (a safety and a health inspection of one visit are one visit)
        hv = warehouse.rows(f"""SELECT v.hazard_code, count(DISTINCT i.visit_id) AS n_all,
                                       count(DISTINCT i.visit_id) FILTER (WHERE i.open_date >= ?) AS n_window
                                FROM osha.violation v JOIN osha.inspection i USING (activity_nr)
                                WHERE i.establishment_key IN {_in(keys)} AND NOT v.is_deleted
                                GROUP BY 1""", [since])
        vmap = {r["hazard_code"]: r for r in hv}
        for h in hfacts:
            h.insp_all = int(vmap[h.hazard_code]["n_all"]) if h.hazard_code in vmap else h.insp_all
            h.insp_window = int(vmap[h.hazard_code]["n_window"]) if h.hazard_code in vmap else 0
            if h.hazard_code != "other" and (h.insp_all >= 3 or h.insp_window >= 2):
                h.evidence = hazard_evidence(keys, h.hazard_code)
    rates = injury_rates(keys, n4)
    lics = licences(keys)
    # deaths the company reported on its 300A summaries, in years with no OSHA fatality investigation (±1 year)
    osha_fatal_years = {int(f.event_date[:4]) for f in flags if f.event_date and f.kind in OSHA_FATALITY_KINDS}
    ita_deaths = [(r.year, r.deaths) for r in rates
                  if r.deaths and not any(abs(r.year - y) <= 1 for y in osha_fatal_years)]
    facts = Facts(
        as_of_year=aof.year, as_of=aof, window_years=window, matched_establishments=len(keys),
        inspections_all=tot["insp_conducted_n"], inspections_window=tot["w_insp_n"], rated_window=tot["w_insp_rated_n"],
        serious_plus_window=tot["w_viol_serious_plus_n"],
        red_flags=[RedFlagFact(f.kind, int(f.event_date[:4]) if f.event_date else None, f.activity_nr, f.case_open,
                               date.fromisoformat(f.event_date[:10]) if f.event_date else None,
                               visit.get(f.activity_nr)) for f in flags],
        hazards=hfacts, open_serious_cases=open_serious, **question_facts(sc["pending_questions"]),
        benchmark_p75=bm["serious_plus_rate_p75"] if bm else None, benchmark_p90=bm["serious_plus_rate_p90"] if bm else None,
        benchmark_peers=bm["peer_n"] if bm else 0, benchmark_label=bm["label"] if bm else None,
        ita_dart_above_p75_years=dart_above_p75_years(rates, n4), licence_lapsed=licence_lapsed(lics),
        visits_without_inspection=tot["insp_n"] - tot["insp_conducted_n"], ita_deaths=ita_deaths,
        stale_records=len(stale), unresolved_red_flags=unresolved_red_flags(sc),
    )
    verdict, reasons = evaluate(facts)
    est = warehouse.rows(f"""SELECT establishment_key, display_name, state, insp_n, insp_conducted_n, first_seen, last_seen
                             FROM entity.establishment WHERE establishment_key IN {_in(keys + sc['possible'])}""") if (keys or sc["possible"]) else []
    est_by = {e["establishment_key"]: e for e in est}
    matched_est = [est_by[k] for k in keys if k in est_by]
    display = max(matched_est, key=lambda e: e["insp_n"])["display_name"] if matched_est else None
    years = [y.year for y in trend(keys)]
    rate = (tot["w_viol_serious_plus_n"] / tot["w_insp_rated_n"]) if tot["w_insp_rated_n"] else None
    return {"scope": sc, "keys": keys, "stale": stale, "facts": facts, "verdict": verdict, "reasons": reasons, "flags": flags,
            "hazards": hz, "benchmark": bm, "naics4": n4, "display_name": display, "est_by": est_by,
            "rate": rate, "years": years, "window": window, "as_of": aof, "rates": rates, "licences": lics,
            "possible_inspections": sum(est_by[k]["insp_conducted_n"] for k in sc["possible"] if k in est_by),
            "visits_without_inspection": facts.visits_without_inspection,
            "states": sorted({e["state"] for e in matched_est if e["state"]})}


def match_status(sc: dict) -> str:
    if sc["pending_questions"]:
        return "questions_pending"
    if sc["needs_adjudication"]:
        return "needs_adjudication"
    return "resolved"


def card(sub: dict, project: dict, data: dict | None = None) -> S.SubCard:
    d = data or compute(sub, project)
    bm = d["benchmark"]
    web = V.info(list(d["scope"]["rows"].values()), d["scope"]["pending_questions"])
    return S.SubCard(
        sub_id=str(sub["sub_id"]), entered_name=sub["entered_name"], entered_city=sub.get("entered_city"),
        entered_state=sub.get("entered_state"), trade=sub.get("trade"), display_name=d["display_name"],
        verdict=d["verdict"], verdict_label=VERDICT_LABELS[d["verdict"]], reasons=d["reasons"][:3],
        match_status=match_status(d["scope"]), matched_establishments=len(d["keys"]),
        matched_inspections=d["facts"].inspections_all, possible_inspections=d["possible_inspections"],
        pending_questions=len(d["scope"]["pending_questions"]),
        red_flag_count=sum(1 for f in d["flags"] if f.kind != "fatality_inspected_not_cited"),
        window_years=d["window"], inspections_in_window=d["facts"].inspections_window,
        serious_plus_rate=round(d["rate"], 2) if d["rate"] is not None else None,
        trade_label=NAICS4_LABELS.get(d["naics4"] or "", None),
        trade_p50=round(bm["serious_plus_rate_p50"], 2) if bm else None,
        trade_p75=round(bm["serious_plus_rate_p75"], 2) if bm else None,
        states=d["states"], first_year=min(d["years"]) if d["years"] else None,
        last_year=max(d["years"]) if d["years"] else None,
        trir_latest=next((r.trir for r in reversed(d["rates"]) if r.trir is not None), None),
        licence_status=(f"{d['licences'][0].source}: {d['licences'][0].status}" if d["licences"] else None),
        same_records_as=[S.SubRef(**r) for r in d["scope"]["same_records_as"]],
        profile_status=sub.get("profile_status"),
        web_unchecked=web["unchecked"] if web["available"] else 0,
    )


def coverage(d: dict) -> S.Coverage:
    meta = warehouse.meta()
    open_n = sum(1 for _ in inspections(d["keys"], limit=500, provisional_only=True)) if d["keys"] else 0
    first = min(d["years"]) if d["years"] else None
    last = max(d["years"]) if d["years"] else None
    no_insp = d.get("visits_without_inspection", 0)
    if d["keys"] and d["facts"].inspections_all == 0:
        sentence = (f"Matched {len(d['keys'])} OSHA record(s), but they are {no_insp} file(s) where OSHA conducted no "
                    f"inspection (data as of {meta['data_as_of']}). No record is not a clean record: ask the sub for "
                    "its EMR, TRIR and OSHA 300 logs.")
    elif d["keys"]:
        sentence = (f"Based on {d['facts'].inspections_all} OSHA inspections ({first}–{last}) across "
                    f"{len(d['keys'])} matched record(s), data as of {meta['data_as_of']}"
                    + (f"; {open_n} case(s) with citations not yet final, so they may change" if open_n else "")
                    + (f"; {no_insp} OSHA file(s) with no inspection conducted, not counted" if no_insp else "")
                    + (f"; {d['possible_inspections']} inspection(s) under similar names not counted" if d["possible_inspections"] else "")
                    + f"; accident details published through {meta['accident_detail_through']}.")
    elif not d.get("stale"):
        sentence = (f"No matching OSHA inspections found (data as of {meta['data_as_of']}). No record is not a clean "
                    "record: OSHA inspects a small share of employers. Ask the sub for its EMR, TRIR and OSHA 300 logs.")
    else:
        sentence = f"Nothing counted yet (data as of {meta['data_as_of']})."
    if d.get("stale"):
        sentence += (f" {len(d['stale'])} OSHA record(s) matched or asked about for this sub aren't in this data update "
                     "(it regrouped them) and aren't counted until they're moved onto it.")
    return S.Coverage(as_of=meta["data_as_of"], window_years=d["window"], establishments_matched=len(d["keys"]),
                      possible_not_counted=d["possible_inspections"], inspections_all_time=d["facts"].inspections_all,
                      first_year=first, last_year=last, open_cases=open_n, visits_without_inspection=no_insp,
                      accident_detail_through=meta["accident_detail_through"] or "", sentence=sentence)


# --- public-data enrichment ------------------------------------------------------------------------
LICENCE_OK = {"ACTIVE", "CLEAR", "RE-LICENSED", "RELICENSED"}


def injury_rates(keys: list[str], naics4: str | None) -> list[S.ItaYear]:
    """Self-reported OSHA 300A summaries linked by exact name+zip/address (M1/M2) to the sub's records.
    Rates are summed across linked establishments per year; implausible filings are excluded and flagged."""
    if not keys:
        return []
    rs = warehouse.rows(f"""
        WITH ids AS (SELECT DISTINCT ref_id FROM entity.ref_link
                     WHERE source = 'ita' AND method IN ('M1', 'M2') AND establishment_key IN {_in(keys)})
        SELECT y.year,
               string_agg(DISTINCT coalesce(y.establishment_name, y.company_name), '; ') AS names,
               sum(y.hours) FILTER (WHERE len(y.dq_flags) = 0) AS hours,
               sum(y.employees) FILTER (WHERE len(y.dq_flags) = 0) AS employees,
               sum(y.dafw + y.djtr + y.other_cases) FILTER (WHERE len(y.dq_flags) = 0) AS cases,
               sum(y.dafw + y.djtr) FILTER (WHERE len(y.dq_flags) = 0) AS dart_cases,
               sum(y.deaths) AS deaths,
               bool_or(len(y.dq_flags) > 0) AS flagged
        FROM ref_ext.ita_establishment_year y JOIN ids ON ids.ref_id = y.establishment_id
        GROUP BY 1 ORDER BY 1""")
    bench = {}
    if naics4:
        bench = {b["year"]: b for b in warehouse.rows("SELECT * FROM mart.ita_benchmark WHERE naics4 = ? AND peer_n >= 30", [naics4])}
    out = []
    for r in rs:
        hours = float(r["hours"]) if r["hours"] else None
        ok = hours is not None and hours >= 20000
        out.append(S.ItaYear(
            year=r["year"], establishment_name=r["names"][:120] if r["names"] else "", hours=hours,
            employees=float(r["employees"]) if r["employees"] else None,
            trir=round(float(r["cases"]) * 200000 / hours, 2) if ok else None,
            dart=round(float(r["dart_cases"]) * 200000 / hours, 2) if ok else None,
            deaths=int(r["deaths"]) if r["deaths"] is not None else None,
            peer_trir=round(bench[r["year"]]["trir_pooled"], 2) if r["year"] in bench else None,
            flagged=bool(r["flagged"]) or not ok))
    return out


def dart_above_p75_years(rates: list[S.ItaYear], naics4: str | None) -> list[int]:
    if not naics4 or not rates:
        return []
    bench = {b["year"]: b for b in warehouse.rows("SELECT * FROM mart.ita_benchmark WHERE naics4 = ? AND peer_n >= 30", [naics4])}
    last3 = [r for r in rates if r.dart is not None][-3:]
    return [r.year for r in last3 if r.year in bench and (r.hours or 0) >= 50000 and r.dart >= bench[r.year]["dart_p75"]]


def licences(keys: list[str]) -> list[S.Licence]:
    if not keys:
        return []
    rs = warehouse.rows(f"""
        SELECT DISTINCT l.source, l.number, l.name, l.status, l.expires::VARCHAR AS expires, l.specialty
        FROM entity.ref_link k JOIN ref_ext.licence l
          ON k.source = 'licence:' || l.source AND k.ref_id = l.number
        WHERE k.method IN ('M1', 'M2') AND k.establishment_key IN {_in(keys)}
        ORDER BY l.expires DESC NULLS LAST LIMIT 10""")
    return [S.Licence(source=r["source"], number=r["number"], name=r["name"], status=r["status"],
                      expires=r["expires"], specialty=r["specialty"]) for r in rs]


def licence_lapsed(lics: list[S.Licence]) -> str | None:
    if not lics or any((l.status or "").upper() in LICENCE_OK for l in lics):
        return None
    latest = lics[0]
    return f"{(latest.status or 'not active').lower()} ({latest.source} {latest.number}, expires {latest.expires or 'unknown'})"
