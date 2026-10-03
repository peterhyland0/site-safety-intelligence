"""Named queries: the only code that reads OSHA facts for a sub. The GC view and the foreman's tools call
the same functions, so a business term ("serious", "fall protection", "open case") means the same thing
everywhere, and every figure carries the inspection IDs behind it."""
from __future__ import annotations

from collections import Counter
from datetime import date

from ssi import config
from ssi.api import schemas as S
from ssi.matching.trades import NAICS4_LABELS, trade_naics4
from ssi.scoring.verdict import VERDICT_LABELS, Facts, HazardFact, RedFlagFact, evaluate
from ssi.store import pg, warehouse

HAZARD_FALLBACK = {"other": "Other / unmapped"}
INSP_TYPE_FALLBACK = {
    "A": "Accident", "B": "Complaint", "C": "Referral", "D": "Monitoring", "E": "Variance", "F": "Follow-up",
    "G": "Unprogrammed related", "H": "Planned (programmed)", "I": "Programmed related", "J": "Unprogrammed other",
    "K": "Programmed other", "L": "Other", "M": "Fatality/catastrophe", "N": "Other",
}
VIOL_TYPE_FALLBACK = {"S": "Serious", "W": "Willful", "R": "Repeat", "O": "Other-than-serious", "U": "Unclassified",
                      "P": "Undocumented type 'P'"}
RED_FLAG_LABELS = {
    "fatality_cited": "Fatality, employer cited",
    "fatality_inspected_not_cited": "Fatality on site, employer not cited for serious violations",
    "fatcat_cited": "Fatality/catastrophe investigation, cited (details not yet published)",
    "willful": "Willful violation",
    "repeat": "Repeat violation",
    "fta": "Failure to abate",
}


def url(activity_nr: int) -> str:
    return S.OSHA_INSPECTION_URL.format(activity_nr=activity_nr)


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
    out = {"matched": [], "possible": [], "excluded": [], "note": None, "rows": {}, "questions": qs}
    for r in rows:
        if r["establishment_key"] == "__note__":
            out["note"] = r["rationale"]
            continue
        out[r["bucket"]].append(r["establishment_key"])
        out["rows"][r["establishment_key"]] = r
    out["needs_adjudication"] = any(r["needs_adjudication"] for r in rows)
    out["pending_questions"] = [q for q in qs if q["answer"] is None]
    return out


def _in(keys: list[str]) -> str:
    return "(SELECT unnest(?::VARCHAR[]))"


# --- facts -----------------------------------------------------------------------------------------
def year_rows(keys: list[str]) -> list[dict]:
    if not keys:
        return []
    return warehouse.rows(f"SELECT * FROM mart.establishment_year WHERE establishment_key IN {_in(keys)}", [keys])


def red_flags(keys: list[str]) -> list[S.RedFlag]:
    if not keys:
        return []
    hl = hazard_labels()
    rs = warehouse.rows(
        f"""SELECT r.*, i.estab_name_raw AS establishment_name
            FROM mart.red_flag r JOIN osha.inspection i USING (activity_nr)
            WHERE r.establishment_key IN {_in(keys)} ORDER BY r.event_date DESC NULLS LAST""", [keys])
    return [S.RedFlag(kind=r["kind"], label=RED_FLAG_LABELS.get(r["kind"], r["kind"]),
                      event_date=str(r["event_date"]) if r["event_date"] else None, activity_nr=r["activity_nr"],
                      citation_id=r["citation_id"], standard=r["standard_cite"],
                      hazard_label=hl.get(r["hazard_code"], r["hazard_code"]) if r["hazard_code"] else None,
                      penalty_initial=float(r["penalty_initial"]) if r["penalty_initial"] is not None else None,
                      penalty_current=float(r["penalty_current"]) if r["penalty_current"] is not None else None,
                      case_open=bool(r["case_open"]), shared_site_n=r["shared_site_n"] or 1,
                      establishment_name=r["establishment_name"], url=url(r["activity_nr"])) for r in rs]


def hazards(keys: list[str], window: int) -> list[S.HazardRow]:
    if not keys:
        return []
    cutoff = as_of().year - window
    hl = hazard_labels()
    rs = warehouse.rows(
        f"""SELECT hazard_code, sum(viol_n) AS citations, sum(viol_serious_plus_n) AS serious_plus,
                   sum(insp_n) AS inspections, sum(insp_n) FILTER (WHERE year > ?) AS insp_window,
                   min(year) AS first_year, max(year) AS last_year
            FROM mart.establishment_hazard_year WHERE establishment_key IN {_in(keys)}
            GROUP BY 1 ORDER BY citations DESC""", [cutoff, keys])
    tops = warehouse.rows(
        f"""SELECT v.hazard_code, v.section_key, count(*) AS n
            FROM osha.violation v JOIN osha.inspection i USING (activity_nr)
            WHERE i.establishment_key IN {_in(keys)} AND NOT v.is_deleted AND v.section_key IS NOT NULL
            GROUP BY 1, 2 ORDER BY 3 DESC""", [keys])
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
            ORDER BY i.open_date DESC LIMIT {limit}""", [keys, hazard_code])
    return [r["activity_nr"] for r in rs]


def trend(keys: list[str]) -> list[S.YearRow]:
    rs = year_rows(keys)
    by: dict[int, Counter] = {}
    pen: dict[int, float] = {}
    for r in rs:
        c = by.setdefault(r["year"], Counter())
        for k in ("insp_n", "insp_with_cit_n", "viol_n", "viol_serious_plus_n", "viol_w_n", "viol_r_n"):
            c[k] += r[k] or 0
        if r["penalty_current_sum"] is not None:
            pen[r["year"]] = pen.get(r["year"], 0.0) + float(r["penalty_current_sum"])
    return [S.YearRow(year=y, inspections=c["insp_n"], inspections_with_citations=c["insp_with_cit_n"],
                      citations=c["viol_n"], serious_plus=c["viol_serious_plus_n"], willful=c["viol_w_n"],
                      repeat=c["viol_r_n"], penalty_current=pen.get(y)) for y, c in sorted(by.items())]


INSPECTION_COLS = """i.activity_nr, i.open_date::VARCHAR AS open_date, i.close_date::VARCHAR AS close_date, i.is_open,
    i.insp_type, i.site_city, i.site_state, i.jurisdiction, i.estab_name_raw, i.citation_n, i.serious_plus_n,
    i.penalty_initial, i.penalty_current, i.fatality_status, i.site_group_n, i.dq_flags"""


def _inspection_row(r: dict, itl: dict) -> S.InspectionRow:
    return S.InspectionRow(
        activity_nr=r["activity_nr"], open_date=r["open_date"] or "", close_date=r["close_date"], is_open=bool(r["is_open"]),
        insp_type_label=itl.get(r["insp_type"], r["insp_type"] or "Unknown"), site_city=r["site_city"],
        site_state=r["site_state"], jurisdiction=r["jurisdiction"], establishment_name=r["estab_name_raw"],
        citations=r["citation_n"] or 0, serious_plus=r["serious_plus_n"] or 0,
        penalty_initial=float(r["penalty_initial"]) if r["penalty_initial"] is not None else None,
        penalty_current=float(r["penalty_current"]) if r["penalty_current"] is not None else None,
        fatality_status=r["fatality_status"] if r["fatality_status"] in
        ("fatality_cited", "fatality_inspected_not_cited", "fatcat_cited", "accident_outcome_unknown") else "none",
        shared_site_n=r["site_group_n"] or 1, dq_flags=list(r["dq_flags"] or []), url=url(r["activity_nr"]))


def inspections(keys: list[str], offset: int = 0, limit: int = 25, open_only: bool = False,
                hazard: str | None = None, since_year: int | None = None) -> list[S.InspectionRow]:
    if not keys:
        return []
    where, params = [f"i.establishment_key IN {_in(keys)}"], [keys]
    if open_only:
        where.append("i.is_open")
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
                                GROUP BY 1 ORDER BY 2 DESC LIMIT 1""", [keys])
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


def compute(sub: dict, project: dict) -> dict:
    """Everything the card, the detail page and the foreman need for one sub."""
    sc = scope(str(sub["sub_id"]))
    keys = sc["matched"]
    window = int(project["lookback_years"])
    aof = as_of()
    cutoff = aof.year - window
    yrs = year_rows(keys)
    tot = Counter()
    for r in yrs:
        for k in ("insp_n", "insp_rated_n", "viol_serious_plus_n", "open_insp_n"):
            tot[k] += r[k] or 0
        if r["year"] > cutoff:
            for k in ("insp_n", "insp_rated_n", "viol_serious_plus_n"):
                tot["w_" + k] += r[k] or 0
    flags = red_flags(keys)
    hz = hazards(keys, window)
    open_serious = [i.activity_nr for i in inspections(keys, limit=50, open_only=True) if i.serious_plus > 0]
    n4 = primary_trade(keys, sub.get("trade"))
    bm = benchmark(n4, window)
    hfacts = [HazardFact(h.hazard_code, h.label, h.inspections, 0, h.first_year, h.last_year) for h in hz]
    if hfacts:  # window counts and evidence for recurring hazards only
        hw = warehouse.rows(f"""SELECT hazard_code, sum(insp_n) AS n FROM mart.establishment_hazard_year
                                WHERE establishment_key IN {_in(keys)} AND year > ? GROUP BY 1""", [keys, cutoff])
        wmap = {r["hazard_code"]: int(r["n"]) for r in hw}
        for h in hfacts:
            h.insp_window = wmap.get(h.hazard_code, 0)
            if h.hazard_code != "other" and (h.insp_all >= 3 or h.insp_window >= 2):
                h.evidence = hazard_evidence(keys, h.hazard_code)
    facts = Facts(
        as_of_year=aof.year, window_years=window, matched_establishments=len(keys),
        inspections_all=tot["insp_n"], inspections_window=tot["w_insp_n"], rated_window=tot["w_insp_rated_n"],
        serious_plus_window=tot["w_viol_serious_plus_n"],
        red_flags=[RedFlagFact(f.kind, int(f.event_date[:4]) if f.event_date else None, f.activity_nr, f.case_open) for f in flags],
        hazards=hfacts, open_serious_cases=open_serious, pending_questions=len(sc["pending_questions"]),
        benchmark_p75=bm["serious_plus_rate_p75"] if bm else None, benchmark_p90=bm["serious_plus_rate_p90"] if bm else None,
        benchmark_peers=bm["peer_n"] if bm else 0, benchmark_label=bm["label"] if bm else None,
    )
    verdict, reasons = evaluate(facts)
    est = warehouse.rows(f"""SELECT establishment_key, display_name, state, insp_n, first_seen, last_seen
                             FROM entity.establishment WHERE establishment_key IN {_in(keys + sc['possible'])}""",
                         [keys + sc["possible"]]) if (keys or sc["possible"]) else []
    est_by = {e["establishment_key"]: e for e in est}
    matched_est = [est_by[k] for k in keys if k in est_by]
    display = max(matched_est, key=lambda e: e["insp_n"])["display_name"] if matched_est else None
    years = [y.year for y in trend(keys)]
    rate = (tot["w_viol_serious_plus_n"] / tot["w_insp_rated_n"]) if tot["w_insp_rated_n"] else None
    return {"scope": sc, "keys": keys, "facts": facts, "verdict": verdict, "reasons": reasons, "flags": flags,
            "hazards": hz, "benchmark": bm, "naics4": n4, "display_name": display, "est_by": est_by,
            "rate": rate, "years": years, "window": window, "as_of": aof,
            "possible_inspections": sum(est_by[k]["insp_n"] for k in sc["possible"] if k in est_by),
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
    )


def coverage(d: dict) -> S.Coverage:
    meta = warehouse.meta()
    open_n = sum(1 for _ in inspections(d["keys"], limit=500, open_only=True)) if d["keys"] else 0
    first = min(d["years"]) if d["years"] else None
    last = max(d["years"]) if d["years"] else None
    if d["keys"]:
        sentence = (f"Based on {d['facts'].inspections_all} OSHA inspections ({first}–{last}) across "
                    f"{len(d['keys'])} matched record(s), data as of {meta['data_as_of']}"
                    + (f"; {open_n} case(s) still open, so their citations may change" if open_n else "")
                    + (f"; {d['possible_inspections']} inspection(s) under similar names not counted" if d["possible_inspections"] else "")
                    + f"; accident details published through {meta['accident_detail_through']}.")
    else:
        sentence = (f"No matching OSHA inspections found (data as of {meta['data_as_of']}). No record is not a clean "
                    "record: OSHA inspects a small share of employers. Ask the sub for its EMR, TRIR and OSHA 300 logs.")
    return S.Coverage(as_of=meta["data_as_of"], window_years=d["window"], establishments_matched=len(d["keys"]),
                      possible_not_counted=d["possible_inspections"], inspections_all_time=d["facts"].inspections_all,
                      first_year=first, last_year=last, open_cases=open_n,
                      accident_detail_through=meta["accident_detail_through"] or "", sentence=sentence)
