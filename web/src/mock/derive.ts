/**
 * Computes every API shape from the mock fixtures with a simplified version of the
 * backend's verdict rules (see /methodology). Only used when VITE_MOCK=1.
 */
import {
  oshaSearchUrl,
  type CitationRow,
  type Coverage,
  type HazardRow,
  type InspectionDetail,
  type InspectionRow,
  type MatchedEstablishment,
  type Project,
  type ProjectDetail,
  type Reason,
  type RedFlag,
  type SubCard,
  type SubDetail,
  type Verdict,
  type YearRow,
} from "../api/types";
import { ACCIDENT_DETAIL_THROUGH, DATA_AS_OF } from "./fixtures";
import { HAZARD_LABELS, VIOL_LABELS, type FxCitation, type FxInspection, type FxProject, type FxSub, type HazardKey } from "./model";

const AS_OF_YEAR = Number(DATA_AS_OF.slice(0, 4));

const VERDICT_LABELS: Record<Verdict, string> = {
  high: "High concern",
  review: "Review",
  no_record: "No OSHA record",
  no_recent: "No recent record",
  no_flags: "No flags",
};

// Unknowns sort above clean records: the GC should follow up on them (ask for EMR / TRIR).
const VERDICT_RANK: Record<Verdict, number> = { high: 0, review: 1, no_record: 2, no_recent: 3, no_flags: 4 };

const yearOf = (iso: string) => Number(iso.slice(0, 4));
const live = (c: FxCitation) => !c.deleted;
const isSeriousPlus = (c: FxCitation) => live(c) && (c.type === "S" || c.type === "W" || c.type === "R");
const sumOrNull = (vals: (number | null)[]) => (vals.every((v) => v == null) ? null : vals.reduce<number>((a, v) => a + (v ?? 0), 0));
const fmtMonth = (iso: string) =>
  new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${iso}T00:00:00Z`));
const fmtDay = (iso: string) =>
  new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(new Date(`${iso}T00:00:00Z`));

function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function estOf(sub: FxSub, key: string) {
  return sub.establishments.find((e) => e.key === key);
}

function inBucket(sub: FxSub, bucket: "matched" | "possible" | "excluded"): FxInspection[] {
  return sub.inspections
    .filter((i) => estOf(sub, i.est)?.bucket === bucket)
    .sort((a, b) => b.open.localeCompare(a.open));
}

function windowStart(lookback: number) {
  return AS_OF_YEAR - lookback + 1;
}

export function toInspectionRow(sub: FxSub, i: FxInspection): InspectionRow {
  const cits = i.cits.filter(live);
  return {
    activity_nr: i.nr,
    open_date: i.open,
    close_date: i.close,
    is_open: i.close == null,
    is_provisional: i.close == null, // the fixtures' open cases are all recent, so none is final yet
    no_inspection: false,
    insp_type_label: i.type,
    site_city: i.city,
    site_state: i.state,
    jurisdiction: i.jurisdiction,
    establishment_name: estOf(sub, i.est)?.display_name ?? "Unknown establishment",
    citations: cits.length,
    serious_plus: cits.filter(isSeriousPlus).length,
    penalty_initial: cits.length ? sumOrNull(cits.map((c) => c.initial)) : null,
    penalty_current: cits.length ? sumOrNull(cits.map((c) => c.current)) : null,
    fatality_status: i.fatality,
    shared_site_n: i.shared,
    dq_flags: i.dq ?? [],
    url: oshaSearchUrl(estOf(sub, i.est)?.display_name ?? null, i.state, i.open),
  };
}

export function toInspectionDetail(sub: FxSub, i: FxInspection): InspectionDetail {
  const citation_rows: CitationRow[] = i.cits.map((c) => ({
    citation_id: c.id,
    viol_type: c.type,
    viol_type_label: VIOL_LABELS[c.type],
    standard: c.standard,
    hazard_label: HAZARD_LABELS[c.hazard],
    issued: addDays(i.open, 58),
    penalty_initial: c.initial,
    penalty_current: c.current,
    is_deleted: !!c.deleted,
    is_fta: !!c.fta,
    contested: !!c.contested,
  }));
  return { ...toInspectionRow(sub, i), citation_rows, accidents: i.accidents ?? [] };
}

function redFlagsFor(sub: FxSub, inspections: FxInspection[], bucket: "matched" | "possible"): RedFlag[] {
  const out: RedFlag[] = [];
  for (const i of inspections) {
    const base = {
      event_date: i.open,
      activity_nr: i.nr,
      case_open: i.close == null,
      case_provisional: i.close == null,
      shared_site_n: i.shared,
      establishment_name: estOf(sub, i.est)?.display_name ?? "",
      bucket,
      url: oshaSearchUrl(estOf(sub, i.est)?.display_name ?? null, i.state, i.open),
    };
    const cits = i.cits.filter(live);
    if (i.fatality === "fatality_cited" || i.fatality === "fatality_inspected_not_cited") {
      const pi = sumOrNull(cits.map((c) => c.initial));
      const pc = sumOrNull(cits.map((c) => c.current));
      out.push({
        ...base,
        kind: i.fatality,
        label:
          i.fatality === "fatality_cited"
            ? `Fatality investigation with ${cits.filter(isSeriousPlus).length} serious citations`
            : "Fatality investigation, no citations issued",
        citation_id: null,
        standard: cits[0]?.standard ?? null,
        hazard_label: cits[0] ? HAZARD_LABELS[cits[0].hazard] : null,
        penalty_initial: pi,
        penalty_current: pc,
      });
    }
    for (const c of cits) {
      const kind = c.type === "W" ? "willful" : c.type === "R" ? "repeat" : c.fta ? "fta" : null;
      if (!kind) continue;
      out.push({
        ...base,
        kind,
        label: `${kind === "fta" ? "Failure to abate" : VIOL_LABELS[c.type]} citation: ${HAZARD_LABELS[c.hazard].toLowerCase()}`,
        citation_id: c.id,
        standard: c.standard,
        hazard_label: HAZARD_LABELS[c.hazard],
        penalty_initial: c.initial,
        penalty_current: c.current,
      });
    }
  }
  return out;
}

function hazardsFor(inspections: FxInspection[]): HazardRow[] {
  type Acc = { cits: FxCitation[]; insp: Set<number>; years: number[]; std: Map<string, number> };
  const map = new Map<HazardKey, Acc>();
  for (const i of inspections) {
    for (const c of i.cits.filter(live)) {
      const h: Acc = map.get(c.hazard) ?? { cits: [], insp: new Set<number>(), years: [], std: new Map<string, number>() };
      h.cits.push(c);
      h.insp.add(i.nr);
      h.years.push(yearOf(i.open));
      const stdKey = c.standard.replace(/\(.*$/, "");
      h.std.set(stdKey, (h.std.get(stdKey) ?? 0) + 1);
      map.set(c.hazard, h);
    }
  }
  return [...map.entries()]
    .map(([key, h]) => ({
      hazard_code: key,
      label: HAZARD_LABELS[key],
      citations: h.cits.length,
      serious_plus: h.cits.filter(isSeriousPlus).length,
      inspections: h.insp.size,
      first_year: Math.min(...h.years),
      last_year: Math.max(...h.years),
      top_standards: [...h.std.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3).map(([s]) => s),
    }))
    .sort((a, b) => b.citations - a.citations);
}

function trendFor(inspections: FxInspection[]): YearRow[] {
  if (!inspections.length) return [];
  const first = Math.min(...inspections.map((i) => yearOf(i.open)));
  const rows: YearRow[] = [];
  for (let y = first; y <= AS_OF_YEAR; y++) {
    const ins = inspections.filter((i) => yearOf(i.open) === y);
    const cits = ins.flatMap((i) => i.cits.filter(live));
    rows.push({
      year: y,
      inspections: ins.length,
      inspections_with_citations: ins.filter((i) => i.cits.some(live)).length,
      citations: cits.length,
      serious_plus: cits.filter(isSeriousPlus).length,
      willful: cits.filter((c) => c.type === "W").length,
      repeat: cits.filter((c) => c.type === "R").length,
      penalty_current: cits.length ? sumOrNull(cits.map((c) => c.current)) : null,
    });
  }
  return rows;
}

/** "2025, 2022, 2019, 2017 and 2 earlier": most recent first, like the backend. */
function yearsList(nums: number[]): string {
  const ys = [...new Set(nums)].sort((a, b) => b - a);
  return ys.slice(0, 4).join(", ") + (ys.length > 4 ? ` and ${ys.length - 4} earlier` : "");
}

// Mirrors ssi/scoring/verdict.py (simplified: no p90 "top 10%" rate rule, ITA or licence rules).
const RED_FLAG_RECENCY_YEARS = 10;
const BENCHMARK_MIN_RATED_INSPECTIONS = 3;
const HIGH_KINDS = {
  fatality_cited: "Fatality investigation where this employer was cited for serious violations",
  willful: "Willful violation",
  fta: "Failed to fix a cited hazard (failure to abate)",
} as const;

type FlagFact = { kind: keyof typeof HIGH_KINDS | "repeat" | "fatality_inspected_not_cited"; year: number; nr: number };

function flagFacts(inspections: FxInspection[]): FlagFact[] {
  const out: FlagFact[] = [];
  for (const i of inspections) {
    const year = yearOf(i.open);
    if (i.fatality === "fatality_cited" || i.fatality === "fatality_inspected_not_cited") out.push({ kind: i.fatality, year, nr: i.nr });
    const cits = i.cits.filter(live);
    if (cits.some((c) => c.type === "W")) out.push({ kind: "willful", year, nr: i.nr });
    if (cits.some((c) => c.type === "R")) out.push({ kind: "repeat", year, nr: i.nr });
    if (cits.some((c) => c.fta)) out.push({ kind: "fta", year, nr: i.nr });
  }
  return out;
}

function reasonsFor(sub: FxSub, lookback: number): { verdict: Verdict; reasons: Reason[] } {
  const matched = inBucket(sub, "matched");
  const reasons: Reason[] = [];
  const add = (code: string, label: string, severity: Reason["severity"], evidence: number[], figures: Reason["figures"] = {}) =>
    reasons.push({ code, label, severity, evidence: [...new Set(evidence)].sort((a, b) => a - b).slice(0, 20), figures });

  const recentCutoff = AS_OF_YEAR - RED_FLAG_RECENCY_YEARS;
  const windowCutoff = AS_OF_YEAR - lookback;
  const inWindow = matched.filter((i) => yearOf(i.open) > windowCutoff);
  const flags = flagFacts(matched);

  // High: catastrophic events within the recency window
  for (const [kind, text] of Object.entries(HIGH_KINDS)) {
    const recent = flags.filter((f) => f.kind === kind && f.year > recentCutoff);
    if (recent.length) add(`H_${kind}`, `${text} (${yearsList(recent.map((f) => f.year))})`, "high", recent.map((f) => f.nr), { count: recent.length });
  }
  const repeatWindow = flags.filter((f) => f.kind === "repeat" && f.year > windowCutoff);
  if (repeatWindow.length >= 2) {
    add("H_repeat", `Repeat violations in ${repeatWindow.length} separate inspections in the last ${lookback} years`, "high",
      repeatWindow.map((f) => f.nr), { inspections: repeatWindow.length });
  }

  // Review
  for (const [kind, text] of Object.entries(HIGH_KINDS)) {
    const old = flags.filter((f) => f.kind === kind && f.year <= recentCutoff);
    if (old.length) add(`R_old_${kind}`, `${text}, over ${RED_FLAG_RECENCY_YEARS} years ago (${yearsList(old.map((f) => f.year))})`, "review", old.map((f) => f.nr));
  }
  const notCited = flags.filter((f) => f.kind === "fatality_inspected_not_cited");
  if (notCited.length) {
    add("R_fatality_site", `On a site where a fatality was investigated, but not cited for serious violations (${yearsList(notCited.map((f) => f.year))})`,
      "review", notCited.map((f) => f.nr));
  }
  if (repeatWindow.length === 1) add("R_repeat", `Repeat violation in the last ${lookback} years`, "review", repeatWindow.map((f) => f.nr));
  const oldRepeat = flags.filter((f) => f.kind === "repeat" && f.year <= windowCutoff);
  if (oldRepeat.length && repeatWindow.length === 0) {
    add("R_old_repeat", `Repeat violations before the last ${lookback} years (${yearsList(oldRepeat.map((f) => f.year))})`, "info", oldRepeat.map((f) => f.nr));
  }
  const sp = inWindow.reduce((a, i) => a + i.cits.filter(isSeriousPlus).length, 0);
  const rate = inWindow.length ? sp / inWindow.length : null;
  if (rate != null && sub.trade_p75 != null && inWindow.length >= BENCHMARK_MIN_RATED_INSPECTIONS && rate >= sub.trade_p75) {
    add("R_rate", `Serious citations per inspection (${rate.toFixed(2)}) above most ${(sub.trade_label ?? "firms in this trade").replace(/ \(\d+\)$/, "").toLowerCase()}`,
      "review", [], { rate: Number(rate.toFixed(2)), p75: sub.trade_p75 });
  }
  const byHazard = new Map<HazardKey, FxInspection[]>();
  for (const i of matched) {
    for (const h of new Set(i.cits.filter(live).map((c) => c.hazard))) byHazard.set(h, [...(byHazard.get(h) ?? []), i]);
  }
  for (const [h, ins] of byHazard) {
    if (h === "other") continue;
    const inWin = ins.filter((i) => yearOf(i.open) > windowCutoff).length;
    if (ins.length >= 3 || inWin >= 2) {
      const ys = ins.map((i) => yearOf(i.open));
      add(`R_recurring_${h}`, `${HAZARD_LABELS[h]} cited in ${ins.length} separate inspections (${Math.min(...ys)}–${Math.max(...ys)})`,
        "review", ins.map((i) => i.nr), { inspections: ins.length, in_window: inWin });
    }
  }
  const openSerious = matched.filter((i) => i.close == null && i.cits.some(isSeriousPlus));
  if (openSerious.length) {
    add("R_open", `${openSerious.length} open case(s) with serious citations not yet final (still provisional)`, "review", openSerious.map((i) => i.nr), { count: openSerious.length });
  }
  if (sub.questions.length) {
    add("R_questions", `${sub.questions.length} possible match(es) with red flags need your confirmation`, "review", [], { count: sub.questions.length });
  }

  let verdict: Verdict;
  if (reasons.some((r) => r.severity === "high")) verdict = "high";
  else if (reasons.some((r) => r.severity === "review")) verdict = "review";
  else if (!matched.length) verdict = "no_record";
  else if (!inWindow.length) verdict = "no_recent";
  else verdict = "no_flags";
  const order = { high: 0, review: 1, info: 2 } as const;
  reasons.sort((a, b) => order[a.severity] - order[b.severity]);
  return { verdict, reasons };
}

function coverageFor(sub: FxSub, lookback: number): Coverage {
  const matched = inBucket(sub, "matched");
  const possible = inBucket(sub, "possible");
  const years = matched.map((i) => yearOf(i.open));
  const first = years.length ? Math.min(...years) : null;
  const last = years.length ? Math.max(...years) : null;
  const ests = sub.establishments.filter((e) => e.bucket === "matched").length;
  const open = matched.filter((i) => i.close == null).length;
  const asOf = fmtDay(DATA_AS_OF);
  let sentence: string;
  if (!matched.length) {
    const where = [sub.entered_city, sub.entered_state].filter(Boolean).join(", ");
    sentence = `No OSHA inspections found for ${sub.entered_name}${where ? ` (${where})` : ""} in records through ${asOf}. That means unknown, not clean.`;
  } else {
    const range = first === last ? `in ${first}` : `${first}–${last}`;
    sentence = `Based on ${matched.length} OSHA inspection${matched.length > 1 ? "s" : ""} at ${ests} matched establishment${ests > 1 ? "s" : ""}, ${range}`;
    sentence += open ? `; ${open} case${open > 1 ? "s" : ""} still open, so recent citations may change.` : ".";
    sentence += ` Accident detail runs through ${fmtMonth(ACCIDENT_DETAIL_THROUGH)}. Data as of ${asOf}.`;
  }
  if (possible.length) sentence += ` ${possible.length} inspections at possible matches are not counted.`;
  return {
    as_of: DATA_AS_OF,
    window_years: lookback,
    establishments_matched: ests,
    possible_not_counted: possible.length,
    inspections_all_time: matched.length,
    first_year: first,
    last_year: last,
    open_cases: open,
    visits_without_inspection: 0,
    accident_detail_through: ACCIDENT_DETAIL_THROUGH,
    sentence,
  };
}

export function toCard(sub: FxSub, lookback: number): SubCard {
  const matched = inBucket(sub, "matched");
  const possible = inBucket(sub, "possible");
  const ws = windowStart(lookback);
  const inWindow = matched.filter((i) => yearOf(i.open) >= ws);
  const sp = inWindow.reduce((a, i) => a + i.cits.filter(isSeriousPlus).length, 0);
  const { verdict, reasons } = reasonsFor(sub, lookback);
  const years = matched.map((i) => yearOf(i.open));
  const states = [...new Set(matched.map((i) => i.state))].sort();
  return {
    sub_id: sub.sub_id,
    entered_name: sub.entered_name,
    entered_city: sub.entered_city,
    entered_state: sub.entered_state,
    trade: sub.trade,
    display_name: matched.length ? sub.display_name : null,
    verdict,
    verdict_label: VERDICT_LABELS[verdict],
    reasons: reasons.slice(0, 3), // backend sends the top 3
    match_status: sub.needs_adjudication ? "needs_adjudication" : sub.questions.length ? "questions_pending" : "resolved",
    matched_establishments: sub.establishments.filter((e) => e.bucket === "matched").length,
    matched_inspections: matched.length,
    possible_inspections: possible.length,
    pending_questions: sub.questions.length,
    red_flag_count: redFlagsFor(sub, matched, "matched").filter((f) => f.kind !== "fatality_inspected_not_cited").length,
    window_years: lookback,
    inspections_in_window: inWindow.length,
    serious_plus_rate: inWindow.length ? Number((sp / inWindow.length).toFixed(2)) : null,
    trade_label: sub.trade_label,
    trade_p50: sub.trade_p50,
    trade_p75: sub.trade_p75,
    states,
    first_year: years.length ? Math.min(...years) : null,
    last_year: years.length ? Math.max(...years) : null,
    trir_latest: sub.injury_rates.find((r) => !r.flagged)?.trir ?? null,
    licence_status: sub.licence_status,
    profile_status: sub.profile_status ?? null,
  };
}

function toEstablishments(sub: FxSub, bucket: "matched" | "possible" | "excluded"): MatchedEstablishment[] {
  return sub.establishments
    .filter((e) => e.bucket === bucket)
    .map((e) => {
      const ins = sub.inspections.filter((i) => i.est === e.key);
      const dates = ins.map((i) => i.open).sort();
      return {
        establishment_key: e.key,
        display_name: e.display_name,
        name_variants: e.name_variants,
        address: e.address,
        city: e.city,
        state: e.state,
        zip: e.zip,
        trade_label: e.trade_label,
        first_seen: dates[0] ?? null,
        last_seen: dates[dates.length - 1] ?? null,
        inspections: ins.length,
        bucket: e.bucket,
        method: e.method,
        rule_id: e.rule_id,
        confidence: e.confidence,
        rationale: e.rationale,
        has_red_flags: redFlagsFor(sub, ins, "matched").length > 0,
      };
    });
}

export const FIRST_PAGE = 5;

export function toDetail(sub: FxSub, lookback: number): SubDetail {
  const card = toCard(sub, lookback);
  const { reasons } = reasonsFor(sub, lookback);
  const matched = inBucket(sub, "matched");
  const possible = inBucket(sub, "possible");
  return {
    card,
    reasons,
    coverage: coverageFor(sub, lookback),
    questions: sub.questions,
    matched: toEstablishments(sub, "matched"),
    possible: toEstablishments(sub, "possible"),
    excluded: toEstablishments(sub, "excluded"),
    red_flags: [...redFlagsFor(sub, matched, "matched"), ...redFlagsFor(sub, possible, "possible")],
    trend: trendFor(matched),
    hazards: hazardsFor(matched),
    open_cases: matched.filter((i) => i.close == null).map((i) => toInspectionRow(sub, i)),
    inspections: matched.slice(0, FIRST_PAGE).map((i) => toInspectionRow(sub, i)),
    injury_rates: sub.injury_rates,
    licences: sub.licences,
    dq_warnings: sub.dq_warnings,
    profile: sub.profile ?? null,
  };
}

export function matchedInspectionRows(sub: FxSub): InspectionRow[] {
  return inBucket(sub, "matched").map((i) => toInspectionRow(sub, i));
}

export function toProject(p: FxProject): Project {
  return {
    project_id: p.project_id,
    name: p.name,
    state: p.state,
    lookback_years: p.lookback_years,
    created_at: p.created_at,
    sub_count: p.subs.length,
  };
}

export function toProjectDetail(p: FxProject): ProjectDetail {
  const cards = p.subs.map((s) => toCard(s, p.lookback_years));
  cards.sort(
    (a, b) =>
      VERDICT_RANK[a.verdict] - VERDICT_RANK[b.verdict] ||
      b.red_flag_count - a.red_flag_count ||
      (b.serious_plus_rate ?? -1) - (a.serious_plus_rate ?? -1) ||
      a.entered_name.localeCompare(b.entered_name),
  );
  return { project: toProject(p), subs: cards, data_as_of: DATA_AS_OF, history_since: "2016-09-23" };
}
