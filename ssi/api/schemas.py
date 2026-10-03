"""API contract: request/response models shared by the FastAPI app, the named queries and the SPA.

The SPA (web/) mirrors these as TypeScript types in web/src/api/types.ts. Change both together.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["high", "review", "no_record", "no_recent", "no_flags"]
Bucket = Literal["matched", "possible", "excluded"]
Method = Literal["rule", "llm", "gc", "llm_rejected"]
Severity = Literal["high", "review", "info"]
MatchStatus = Literal["resolved", "needs_adjudication", "questions_pending"]
FatalityStatus = Literal["fatality_cited", "fatality_inspected_not_cited", "accident_outcome_unknown", "none"]
AskStatus = Literal["answered", "clarify", "unanswerable", "guard_failed", "needs_confirmation", "no_api_key"]

OSHA_INSPECTION_URL = "https://www.osha.gov/ords/imis/establishment.inspection_detail?id={activity_nr}"


# --- projects and subs ---------------------------------------------------------------------------
class ProjectCreate(BaseModel):
    name: str
    state: str | None = Field(None, description="Job-site state (2 letters); default state for subs")
    lookback_years: Literal[3, 5, 10] = 5


class ProjectUpdate(BaseModel):
    name: str | None = None
    lookback_years: Literal[3, 5, 10] | None = None


class Project(BaseModel):
    project_id: str
    name: str
    state: str | None
    lookback_years: int
    created_at: str
    sub_count: int = 0


class SubInput(BaseModel):
    name: str
    city: str | None = None
    state: str | None = None
    trade: str | None = Field(None, description="Free text or NAICS, e.g. 'roofing' or '238160'")
    licence: str | None = Field(None, description="State contractor licence number / UBI (WA, OR, CA)")


class SubsCreate(BaseModel):
    rows: list[SubInput]


class Reason(BaseModel):
    code: str  # e.g. H1_fatality_cited, R4_recurring_hazard
    label: str  # plain English, e.g. "Fatality investigation with serious citations (2021)"
    severity: Severity
    evidence: list[int] = []  # activity_nr list
    figures: dict[str, float | int | str | None] = {}


class SubCard(BaseModel):
    sub_id: str
    entered_name: str
    entered_city: str | None
    entered_state: str | None
    trade: str | None
    display_name: str | None  # best OSHA spelling of the matched company
    verdict: Verdict
    verdict_label: str  # "High concern", "Review", "No OSHA record", "No recent record", "No flags"
    reasons: list[Reason]  # top reasons (all in SubDetail)
    match_status: MatchStatus
    matched_establishments: int
    matched_inspections: int
    possible_inspections: int  # shown as "+N if these are yours", not counted
    pending_questions: int
    red_flag_count: int
    window_years: int
    inspections_in_window: int
    serious_plus_rate: float | None  # serious+ citations per rated inspection, in window
    trade_label: str | None
    trade_p50: float | None
    trade_p75: float | None
    states: list[str]
    first_year: int | None
    last_year: int | None
    trir_latest: float | None = None  # from OSHA ITA 300A if linked
    licence_status: str | None = None


class ProjectDetail(BaseModel):
    project: Project
    subs: list[SubCard]  # sorted by concern
    data_as_of: str


# --- matching ------------------------------------------------------------------------------------
class MatchedEstablishment(BaseModel):
    establishment_key: str
    display_name: str
    name_variants: list[str]
    address: str | None
    city: str | None
    state: str | None
    zip: str | None
    trade_label: str | None
    first_seen: str | None
    last_seen: str | None
    inspections: int
    bucket: Bucket
    method: Method
    rule_id: str | None
    confidence: float | None
    rationale: str | None
    has_red_flags: bool


class MatchQuestion(BaseModel):
    question_id: str
    text: str
    establishment_keys: list[str]
    ai_suggestion: Literal["same", "different", "unsure"] | None
    ai_rationale: str | None


class MatchOverride(BaseModel):
    bucket: Bucket


class QuestionAnswer(BaseModel):
    answer: Literal["yes", "no"]


# --- evidence ------------------------------------------------------------------------------------
class RedFlag(BaseModel):
    kind: Literal["fatality_cited", "fatality_inspected_not_cited", "willful", "repeat", "fta"]
    label: str
    event_date: str | None
    activity_nr: int
    citation_id: str | None
    standard: str | None
    hazard_label: str | None
    penalty_initial: float | None
    penalty_current: float | None
    case_open: bool
    shared_site_n: int
    establishment_name: str
    bucket: Bucket = "matched"
    url: str


class YearRow(BaseModel):
    year: int
    inspections: int
    inspections_with_citations: int
    citations: int
    serious_plus: int
    willful: int
    repeat: int
    penalty_current: float | None


class HazardRow(BaseModel):
    hazard_code: str
    label: str
    citations: int
    serious_plus: int
    inspections: int
    first_year: int | None
    last_year: int | None
    top_standards: list[str]


class InspectionRow(BaseModel):
    activity_nr: int
    open_date: str
    close_date: str | None
    is_open: bool
    insp_type_label: str
    site_city: str | None
    site_state: str | None
    jurisdiction: Literal["federal", "state_plan"]
    establishment_name: str
    citations: int
    serious_plus: int
    penalty_initial: float | None
    penalty_current: float | None
    fatality_status: FatalityStatus
    shared_site_n: int
    dq_flags: list[str]
    url: str


class CitationRow(BaseModel):
    citation_id: str
    viol_type: str | None
    viol_type_label: str
    standard: str | None
    hazard_label: str
    issued: str | None
    penalty_initial: float | None
    penalty_current: float | None
    is_deleted: bool
    is_fta: bool
    contested: bool


class AccidentInfo(BaseModel):
    summary_nr: int
    event_date: str | None
    description: str | None
    narrative: str | None
    fatal_n: int
    injured_n: int
    employers_on_site: int


class InspectionDetail(InspectionRow):
    citation_rows: list[CitationRow]
    accidents: list[AccidentInfo]


class Coverage(BaseModel):
    as_of: str
    window_years: int
    establishments_matched: int
    possible_not_counted: int
    inspections_all_time: int
    first_year: int | None
    last_year: int | None
    open_cases: int
    accident_detail_through: str
    sentence: str  # appended verbatim to foreman answers and shown under the scorecard


class ItaYear(BaseModel):
    year: int
    establishment_name: str
    hours: float | None
    employees: float | None
    trir: float | None
    dart: float | None
    deaths: int | None
    peer_trir: float | None  # pooled industry rate for the sub's trade (all filers' cases / hours)
    flagged: bool  # implausible hours etc.


class Licence(BaseModel):
    source: Literal["WA L&I", "OR CCB", "CA CSLB"]
    number: str
    name: str
    status: str | None
    expires: str | None
    specialty: str | None


class SubDetail(BaseModel):
    card: SubCard
    reasons: list[Reason]
    coverage: Coverage
    questions: list[MatchQuestion]
    matched: list[MatchedEstablishment]
    possible: list[MatchedEstablishment]
    excluded: list[MatchedEstablishment]
    red_flags: list[RedFlag]
    trend: list[YearRow]
    hazards: list[HazardRow]
    open_cases: list[InspectionRow]
    inspections: list[InspectionRow]  # first page, newest first; more via /inspections?offset=
    injury_rates: list[ItaYear]
    licences: list[Licence]
    dq_warnings: list[str]


# --- foreman -------------------------------------------------------------------------------------
class AskRequest(BaseModel):
    question: str
    history: list[dict] = []  # [{role, content}] prior turns (text only)


class Citation(BaseModel):
    activity_nr: int
    url: str


class ClarifyOption(BaseModel):
    sub_id: str
    name: str


class AskResponse(BaseModel):
    status: AskStatus
    answer: str  # markdown, phone-sized
    citations: list[Citation] = []
    coverage: str | None = None
    clarify_options: list[ClarifyOption] = []
    tools_used: list[str] = []


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    data_as_of: str | None
    build_id: str | None
    llm_enabled: bool
    db_ok: bool
