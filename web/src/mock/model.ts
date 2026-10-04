/**
 * Mock-mode data model. Fixtures describe raw-ish facts (establishments, inspections,
 * citations); derive.ts computes every API shape from them, so the scorecard, sub detail,
 * inspection drill-down and foreman answers always agree.
 */
import type {
  AccidentInfo,
  Bucket,
  CompanyProfile,
  FatalityStatus,
  ItaYear,
  Licence,
  MatchQuestion,
  ProfileStatus,
  Method,
} from "../api/types";

export type HazardKey =
  | "fall"
  | "ladder"
  | "scaffold"
  | "electrical"
  | "hazcom"
  | "ppe"
  | "excavation"
  | "struck"
  | "crane"
  | "silica"
  | "other";

export const HAZARD_LABELS: Record<HazardKey, string> = {
  fall: "Fall protection",
  ladder: "Ladders",
  scaffold: "Scaffolding",
  electrical: "Electrical",
  hazcom: "Hazard communication",
  ppe: "Eye, face and head protection",
  excavation: "Excavation and trenching",
  struck: "Struck-by and materials handling",
  crane: "Cranes and rigging",
  silica: "Silica and respirable dust",
  other: "Other / unmapped",
};

export type ViolType = "S" | "W" | "R" | "O" | "U";

export const VIOL_LABELS: Record<ViolType, string> = {
  S: "Serious",
  W: "Willful",
  R: "Repeat",
  O: "Other-than-serious",
  U: "Unclassified",
};

export interface FxCitation {
  id: string;
  type: ViolType;
  standard: string;
  hazard: HazardKey;
  initial: number | null;
  current: number | null;
  deleted?: boolean;
  fta?: boolean;
  contested?: boolean;
}

export interface FxInspection {
  nr: number;
  open: string;
  close: string | null;
  type: string;
  city: string;
  state: string;
  jurisdiction: "federal" | "state_plan";
  est: string; // establishment_key
  fatality: FatalityStatus;
  shared: number;
  dq?: string[];
  cits: FxCitation[];
  accidents?: AccidentInfo[];
}

export interface FxEstablishment {
  key: string;
  display_name: string;
  name_variants: string[];
  address: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
  trade_label: string | null;
  bucket: Bucket;
  method: Method;
  rule_id: string | null;
  confidence: number | null;
  rationale: string | null;
  /** the web check has looked this record up (mock of sub_match.evidence.web_check) */
  web_checked?: boolean;
}

/** What the web check finds for a record when /web-check (the button) runs: who a web page says it belongs to. */
export interface FxWebResult {
  key: string;
  verdict: "same" | "different" | "unsure";
  owner: string;
  url: string;
  title: string | null;
  quote: string;
  rationale: string;
}

/** What the adjudicator decides for an establishment when /adjudicate runs. */
export interface FxAdjudication {
  key: string;
  bucket: Bucket;
  method: Method;
  confidence: number | null;
  rationale: string;
}

/** What a company-profile lookup finds when /adjudicate (a new sub) or /profile (the button) runs. */
export interface FxProfileLookup {
  profile: CompanyProfile;
  /** establishments at locations it lists: held for the GC (possible, method "profile") and asked about */
  holds: { key: string; rationale: string }[];
  question: Omit<MatchQuestion, "question_id">;
}

export interface FxSub {
  sub_id: string;
  entered_name: string;
  entered_city: string | null;
  entered_state: string | null;
  trade: string | null;
  display_name: string | null;
  trade_label: string | null;
  trade_p50: number | null;
  trade_p75: number | null;
  licence_status: string | null;
  needs_adjudication: boolean;
  adjudication: FxAdjudication[];
  establishments: FxEstablishment[];
  inspections: FxInspection[];
  questions: MatchQuestion[];
  injury_rates: ItaYear[];
  licences: Licence[];
  dq_warnings: string[];
  /** null/undefined: added before profiles (the sub page offers a button); new subs start "pending" */
  profile_status?: ProfileStatus | null;
  profile?: CompanyProfile | null;
  profile_lookup?: FxProfileLookup;
  /** the web check's findings, by record; a record without one comes back unsure */
  web_lookup?: FxWebResult[];
}

export interface FxProject {
  project_id: string;
  name: string;
  state: string | null;
  lookback_years: number;
  created_at: string;
  subs: FxSub[];
  /** the web check's settings (Project.auto_web_check, auto_web_match) */
  auto_web_check?: boolean;
  auto_web_match?: boolean;
}
