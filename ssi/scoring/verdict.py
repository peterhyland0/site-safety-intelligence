"""Verdict rules: flags with evidence, not a single score. A GC has to be able to defend a decision,
so every reason names the inspections behind it. Pure function over facts computed by the queries."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ssi import config
from ssi.api.schemas import Reason

VERDICT_LABELS = {
    "high": "High concern",
    "review": "Review",
    "no_record": "No OSHA record",
    "no_recent": "No recent record",
    "no_flags": "No flags",
}
VERDICT_ORDER = {"high": 0, "review": 1, "no_record": 2, "no_recent": 3, "no_flags": 4}

HIGH_KINDS = {
    "fatality_cited": "Fatality investigation where this employer was cited for serious violations",
    "fatcat_cited": "Fatality/catastrophe investigation with serious citations (details not yet published)",
    "willful": "Willful violation",
    "fta": "Failed to fix a cited hazard (failure to abate)",
}


# Fatality investigations this employer wasn't cited in (or not yet): they matter only while recent.
SITE_KINDS = {
    "fatality_inspected_not_cited": ("R_fatality_site", "On a site where a fatality was investigated, but not cited for serious violations"),
    "fatcat_not_cited": ("R_fatcat_site", "Fatality/catastrophe investigation, not cited for serious violations (details not published)"),
    "fatcat_site_cited": ("R_fatcat_site_cited", ("Cited for serious violations on a site where another employer's "
                                                  "fatality/catastrophe investigation is open or unpublished")),
}


def years_before(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # 29 February
        return d.replace(year=d.year - years, day=28)


@dataclass
class RedFlagFact:
    kind: str
    year: int | None
    activity_nr: int
    case_open: bool
    when: date | None = None  # event date; windows compare dates, not calendar years


@dataclass
class HazardFact:
    hazard_code: str
    label: str
    insp_all: int
    insp_window: int
    first_year: int | None
    last_year: int | None
    evidence: list[int] = field(default_factory=list)


@dataclass
class Facts:
    as_of_year: int  # kept for year-only facts (tests); as_of (the data date) is used when set
    window_years: int
    matched_establishments: int
    inspections_all: int
    inspections_window: int
    rated_window: int
    serious_plus_window: int
    red_flags: list[RedFlagFact]
    hazards: list[HazardFact]
    open_serious_cases: list[int]  # activity_nr of open inspections with serious+ citations
    pending_questions: int
    benchmark_p75: float | None = None
    benchmark_p90: float | None = None
    benchmark_peers: int = 0
    benchmark_label: str | None = None
    ita_dart_above_p75_years: list[int] = field(default_factory=list)
    licence_lapsed: str | None = None
    as_of: date | None = None


def _years(flags: list[RedFlagFact]) -> str:
    """Most recent first: "2008, 2000, 1996, 1990 and 2 earlier"."""
    ys = sorted({f.year for f in flags if f.year}, reverse=True)
    shown = ", ".join(str(y) for y in ys[:4])
    return shown + (f" and {len(ys) - 4} earlier" if len(ys) > 4 else "")


def _since(f: Facts, years: int) -> date:
    """First day inside "the last N years": N years before the data date (Sep 23 2026 -> Sep 23 2016).
    Year-only facts fall back to calendar years."""
    return years_before(f.as_of, years) if f.as_of else date(f.as_of_year - years + 1, 1, 1)


def _day(x: RedFlagFact) -> date:
    return x.when or (date(x.year, 7, 1) if x.year else date.min)


def evaluate(f: Facts) -> tuple[str, list[Reason]]:
    reasons: list[Reason] = []
    recent_since = _since(f, config.RED_FLAG_RECENCY_YEARS)
    window_since = _since(f, f.window_years)

    def recent(x: RedFlagFact) -> bool:
        return _day(x) >= recent_since

    def in_window(x: RedFlagFact) -> bool:
        return _day(x) >= window_since

    def add(code, label, severity, flags=(), **figures):
        reasons.append(Reason(code=code, label=label, severity=severity,
                              evidence=sorted({x.activity_nr for x in flags})[:20] if flags else figures.pop("evidence", []),
                              figures=figures))

    # High: catastrophic events within the recency window
    for kind, text in HIGH_KINDS.items():
        hits = [x for x in f.red_flags if x.kind == kind and recent(x)]
        if hits:
            add(f"H_{kind}", f"{text} ({_years(hits)})", "high", hits, count=len(hits))
    repeat_window = [x for x in f.red_flags if x.kind == "repeat" and in_window(x)]
    repeat_insp = {x.activity_nr for x in repeat_window}
    if len(repeat_insp) >= 2:
        add("H_repeat", f"Repeat violations in {len(repeat_insp)} separate inspections in the last {f.window_years} years",
            "high", repeat_window, inspections=len(repeat_insp))
    rate = (f.serious_plus_window / f.rated_window) if f.rated_window else None
    peer_ok = f.benchmark_peers >= config.BENCHMARK_MIN_PEERS
    if rate is not None and peer_ok and f.benchmark_p90 is not None and f.rated_window >= 5 and rate >= f.benchmark_p90:
        add("H_rate", f"Serious citations per inspection ({rate:.2f}) in the top 10% of {f.benchmark_label}",
            "high", rate=round(rate, 2), p90=round(f.benchmark_p90, 2))

    # Review
    for kind, text in HIGH_KINDS.items():
        old = [x for x in f.red_flags if x.kind == kind and not recent(x)]
        if old:
            add(f"R_old_{kind}", f"{text}, over {config.RED_FLAG_RECENCY_YEARS} years ago ({_years(old)})",
                "review", old, count=len(old))
    # An open fatality/catastrophe investigation: OSHA hasn't published the outcome or issued serious
    # citations yet. Not High (we can't say whose worker it was), but never silent.
    pending = [x for x in f.red_flags if x.kind == "fatality_pending"]
    if pending:
        add("R_fatality_pending", f"Fatality/catastrophe investigation still open; outcome not yet published ({_years(pending)})",
            "review", pending, count=len(pending))
    # Not this sub's offence, so it only matters while recent (cited fatalities keep the unlimited lookback)
    for kind, (code, text) in SITE_KINDS.items():
        hits = [x for x in f.red_flags if x.kind == kind and recent(x)]
        if hits:
            add(code, f"{text} ({_years(hits)})", "review", hits, count=len(hits))
    if len(repeat_insp) == 1:
        add("R_repeat", f"Repeat violation in the last {f.window_years} years", "review", repeat_window)
    old_repeat = [x for x in f.red_flags if x.kind == "repeat" and not in_window(x)]
    if old_repeat and len(repeat_insp) == 0:
        add("R_old_repeat", f"Repeat violations before the last {f.window_years} years ({_years(old_repeat)})",
            "info", old_repeat)
    if (rate is not None and peer_ok and f.benchmark_p75 is not None and f.rated_window >= config.BENCHMARK_MIN_RATED_INSPECTIONS
            and rate >= f.benchmark_p75 and not any(r.code == "H_rate" for r in reasons)):
        add("R_rate", f"Serious citations per inspection ({rate:.2f}) above most {f.benchmark_label}",
            "review", rate=round(rate, 2), p75=round(f.benchmark_p75, 2))
    for h in f.hazards:
        if h.hazard_code == "other" or not (h.insp_all >= 3 or h.insp_window >= 2):
            continue
        short = h.label.split(" (")[0]
        if h.insp_window >= 1:  # an active pattern: still being cited inside the project window
            add(f"R_recurring_{h.hazard_code}",
                f"{short} cited in {h.insp_all} separate inspections ({h.first_year}–{h.last_year})",
                "review", evidence=h.evidence[:20], inspections=h.insp_all, in_window=h.insp_window)
        else:  # a pattern that has stopped: shown, but doesn't drive the verdict
            add(f"I_past_{h.hazard_code}",
                f"{short} cited in {h.insp_all} separate inspections ({h.first_year}–{h.last_year}), none in the last {f.window_years} years",
                "info", evidence=h.evidence[:20], inspections=h.insp_all)
    if f.open_serious_cases:
        add("R_open", f"{len(f.open_serious_cases)} open case(s) with serious citations (still provisional)",
            "review", evidence=f.open_serious_cases[:20], count=len(f.open_serious_cases))
    if f.pending_questions:
        add("R_questions", f"{f.pending_questions} possible match(es) with red flags need your confirmation", "review",
            count=f.pending_questions)
    if f.ita_dart_above_p75_years:
        add("R_ita", "Self-reported injury rate (DART) above most peers in " +
            ", ".join(map(str, f.ita_dart_above_p75_years)), "review")
    if f.licence_lapsed:
        add("R_licence", f"Contractor licence {f.licence_lapsed}", "review")

    if any(r.severity == "high" for r in reasons):
        verdict = "high"
    elif any(r.severity == "review" for r in reasons):
        verdict = "review"
    elif f.matched_establishments == 0:
        verdict = "no_record"
    elif f.inspections_window == 0:
        verdict = "no_recent"
    else:
        verdict = "no_flags"
    order = {"high": 0, "review": 1, "info": 2}
    reasons.sort(key=lambda r: order[r.severity])
    return verdict, reasons
