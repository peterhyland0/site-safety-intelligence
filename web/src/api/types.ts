/**
 * API contract: TypeScript mirror of ssi/api/schemas.py. Field names match exactly.
 * Change both files together.
 *
 * Python `X | None` maps to `X | null`. Fields with a Python default are still always
 * present in responses (Pydantic serialises defaults), so they are non-optional here;
 * request bodies mark defaulted fields optional.
 */

export type Verdict = "high" | "review" | "no_record" | "no_recent" | "no_flags";
export type Bucket = "matched" | "possible" | "excluded";
export type Method = "rule" | "llm" | "gc" | "llm_rejected";
export type Severity = "high" | "review" | "info";
export type MatchStatus = "resolved" | "needs_adjudication" | "questions_pending";
export type FatalityStatus =
  | "fatality_cited"
  | "fatality_inspected_not_cited"
  | "fatality_pending"
  | "fatcat_cited"
  | "fatcat_not_cited"
  | "fatcat_site_cited"
  | "catastrophe_cited"
  | "fatcat_no_inspection"
  | "accident_outcome_unknown"
  | "none";
export type AskStatus =
  | "answered"
  | "clarify"
  | "unanswerable"
  | "guard_failed"
  | "needs_confirmation"
  | "no_api_key";

export type LookbackYears = 3 | 5 | 10;

/**
 * osha.gov numbers inspections differently from the published data (activity 348557646 is inspection
 * 1395197.015 there), so the API links a search filtered to the employer, site state and opening day.
 * Mirrors osha_search_url in ssi/queries/core.py; used by the mock API and as a fallback.
 */
export const OSHA_SEARCH_PAGE = "https://www.osha.gov/ords/imis/establishment.html";

export function oshaSearchUrl(name: string | null, state: string | null, openDate: string | null): string {
  if (!name || !openDate) return OSHA_SEARCH_PAGE;
  const [y, m, d] = openDate.slice(0, 10).split("-");
  const q: [string, string][] = [
    ["establishment", name],
    ...(state ? ([["state", state]] as [string, string][]) : []),
    ["officetype", "all"],
    ["office", "all"],
    ["sitezip", "100000"],
    ["startmonth", m],
    ["startday", d],
    ["startyear", y],
    ["endmonth", m],
    ["endday", d],
    ["endyear", y],
    ["p_case", "all"],
    ["p_violations_exist", "both"],
  ];
  return `https://www.osha.gov/ords/imis/establishment.search?${q.map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&")}`;
}

// --- projects and subs ---------------------------------------------------------------------------
export interface ProjectCreate {
  name: string;
  /** Job-site state (2 letters); default state for subs */
  state?: string | null;
  lookback_years?: LookbackYears;
}

export interface ProjectUpdate {
  name?: string | null;
  lookback_years?: LookbackYears | null;
}

export interface Project {
  project_id: string;
  name: string;
  state: string | null;
  lookback_years: number;
  created_at: string;
  sub_count: number;
}

export interface SubInput {
  name: string;
  city?: string | null;
  state?: string | null;
  /** Free text or NAICS, e.g. 'roofing' or '238160' */
  trade?: string | null;
  /** State contractor licence number / UBI (WA, OR, CA) */
  licence?: string | null;
}

export interface SubsCreate {
  rows: SubInput[];
}

export interface Reason {
  /** e.g. H1_fatality_cited, R4_recurring_hazard */
  code: string;
  /** plain English, e.g. "Fatality investigation with serious citations (2021)" */
  label: string;
  severity: Severity;
  /** activity_nr list */
  evidence: number[];
  figures: Record<string, number | string | null>;
}

export interface SubCard {
  sub_id: string;
  entered_name: string;
  entered_city: string | null;
  entered_state: string | null;
  trade: string | null;
  /** best OSHA spelling of the matched company */
  display_name: string | null;
  verdict: Verdict;
  /** "High concern", "Review", "No OSHA record", "No recent record", "No flags" */
  verdict_label: string;
  /** top reasons (all in SubDetail) */
  reasons: Reason[];
  match_status: MatchStatus;
  matched_establishments: number;
  matched_inspections: number;
  /** shown as "+N if these are yours", not counted */
  possible_inspections: number;
  pending_questions: number;
  red_flag_count: number;
  window_years: number;
  inspections_in_window: number;
  /** serious+ citations per rated inspection, in window */
  serious_plus_rate: number | null;
  trade_label: string | null;
  trade_p50: number | null;
  trade_p75: number | null;
  states: string[];
  first_year: number | null;
  last_year: number | null;
  /** from OSHA ITA 300A if linked */
  trir_latest: number | null;
  licence_status: string | null;
  /** other subs on this project matched to the same OSHA record: probably the same company entered twice */
  same_records_as?: SubRef[];
}

export interface SubRef {
  sub_id: string;
  name: string;
}

export interface ProjectDetail {
  project: Project;
  /** sorted by concern */
  subs: SubCard[];
  data_as_of: string;
  /** first inspection date the data holds (the last 10 years by default); null = every year */
  history_since?: string | null;
}

// --- matching ------------------------------------------------------------------------------------
export interface MatchedEstablishment {
  establishment_key: string;
  display_name: string;
  name_variants: string[];
  address: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
  trade_label: string | null;
  first_seen: string | null;
  last_seen: string | null;
  inspections: number;
  bucket: Bucket;
  method: Method;
  rule_id: string | null;
  confidence: number | null;
  rationale: string | null;
  has_red_flags: boolean;
  /** in scope only by company name: a plant, yard or shop not coded as construction */
  related_only?: boolean;
  industry_code?: string | null;
}

export interface MatchQuestion {
  question_id: string;
  text: string;
  establishment_keys: string[];
  ai_suggestion: "same" | "different" | "unsure" | null;
  ai_rationale: string | null;
}

export interface MatchOverride {
  bucket: Bucket;
}

export interface QuestionAnswer {
  answer: "yes" | "no";
}

// --- evidence ------------------------------------------------------------------------------------
export interface RedFlag {
  kind:
    | "fatality_cited"
    | "fatality_inspected_not_cited"
    | "fatality_pending"
    | "fatcat_cited"
    | "fatcat_not_cited"
    | "fatcat_site_cited"
    | "catastrophe_cited"
    | "fatcat_no_inspection"
    | "willful"
    | "repeat"
    | "fta";
  label: string;
  event_date: string | null;
  activity_nr: number;
  citation_id: string | null;
  standard: string | null;
  hazard_label: string | null;
  penalty_initial: number | null;
  penalty_current: number | null;
  case_open: boolean; // OSHA's case status (stays open until penalties are paid)
  case_provisional: boolean; // open AND a citation isn't final yet
  shared_site_n: number; // OTHER employers inspected on the same site and day
  establishment_name: string;
  bucket: Bucket;
  url: string;
}

export interface YearRow {
  year: number;
  inspections: number;
  inspections_with_citations: number;
  citations: number;
  serious_plus: number;
  willful: number;
  repeat: number;
  penalty_current: number | null;
}

export interface HazardRow {
  hazard_code: string;
  label: string;
  citations: number;
  serious_plus: number;
  inspections: number;
  first_year: number | null;
  last_year: number | null;
  top_standards: string[];
}

export interface InspectionRow {
  activity_nr: number;
  open_date: string;
  close_date: string | null;
  is_open: boolean; // OSHA's case status (stays open until penalties are paid)
  is_provisional: boolean; // open AND a citation isn't final yet: citations and penalties may change
  no_inspection: boolean; // OSHA opened a file but conducted no inspection
  insp_type_label: string;
  site_city: string | null;
  site_state: string | null;
  jurisdiction: "federal" | "state_plan";
  establishment_name: string;
  citations: number;
  serious_plus: number;
  penalty_initial: number | null;
  penalty_current: number | null;
  fatality_status: FatalityStatus;
  shared_site_n: number;
  dq_flags: string[];
  url: string;
}

export interface CitationRow {
  citation_id: string;
  viol_type: string | null;
  viol_type_label: string;
  standard: string | null;
  hazard_label: string;
  issued: string | null;
  penalty_initial: number | null;
  penalty_current: number | null;
  is_deleted: boolean;
  is_fta: boolean;
  contested: boolean;
}

export interface AccidentInfo {
  summary_nr: number;
  event_date: string | null;
  description: string | null;
  narrative: string | null;
  fatal_n: number;
  injured_n: number;
  employers_on_site: number;
}

export interface InspectionDetail extends InspectionRow {
  citation_rows: CitationRow[];
  accidents: AccidentInfo[];
}

export interface Coverage {
  as_of: string;
  window_years: number;
  establishments_matched: number;
  possible_not_counted: number;
  inspections_all_time: number;
  first_year: number | null;
  last_year: number | null;
  open_cases: number; // provisional cases: open, with a citation that isn't final yet
  visits_without_inspection: number;
  accident_detail_through: string;
  /** appended verbatim to foreman answers and shown under the scorecard */
  sentence: string;
}

export interface ItaYear {
  year: number;
  establishment_name: string;
  hours: number | null;
  employees: number | null;
  trir: number | null;
  dart: number | null;
  deaths: number | null;
  /** pooled industry rate for the sub's trade (all filers' cases / hours), not a median */
  peer_trir: number | null;
  /** implausible hours etc. */
  flagged: boolean;
}

export interface Licence {
  source: "WA L&I" | "OR CCB" | "CA CSLB";
  number: string;
  name: string;
  status: string | null;
  expires: string | null;
  specialty: string | null;
}

export interface SubDetail {
  card: SubCard;
  reasons: Reason[];
  coverage: Coverage;
  questions: MatchQuestion[];
  matched: MatchedEstablishment[];
  possible: MatchedEstablishment[];
  excluded: MatchedEstablishment[];
  red_flags: RedFlag[];
  trend: YearRow[];
  hazards: HazardRow[];
  open_cases: InspectionRow[];
  /** first page, newest first; more via /inspections?offset= */
  inspections: InspectionRow[];
  injury_rates: ItaYear[];
  licences: Licence[];
  dq_warnings: string[];
}

// --- accounts ------------------------------------------------------------------------------------
export interface User {
  user_id: string;
  email: string;
  name: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

// --- foreman -------------------------------------------------------------------------------------
export interface Citation {
  activity_nr: number;
  url: string;
}

export interface ClarifyOption {
  sub_id: string;
  name: string;
}

export interface AskResponse {
  status: AskStatus;
  /** markdown, phone-sized */
  answer: string;
  citations: Citation[];
  coverage: string | null;
  clarify_options: ClarifyOption[];
  tools_used: string[];
}

export interface ChatAsk {
  question: string;
}

export interface ChatSummary {
  chat_id: string;
  project_id: string;
  /** the first question, shortened */
  title: string;
  created_at: string;
  /** last message */
  updated_at: string;
  message_count: number;
}

export interface ChatMessage {
  message_id: number;
  role: "user" | "assistant";
  /** the question, or the answer's markdown */
  content: string;
  /** assistant only */
  response: AskResponse | null;
  created_at: string;
}

export interface ChatDetail extends ChatSummary {
  /** oldest first */
  messages: ChatMessage[];
}

export interface ChatReply {
  chat: ChatSummary;
  /** the question and its answer, as stored */
  messages: ChatMessage[];
}

export interface Health {
  status: "ok" | "degraded";
  data_as_of: string | null;
  build_id: string | null;
  llm_enabled: boolean;
  db_ok: boolean;
}
