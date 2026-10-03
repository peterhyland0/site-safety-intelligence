/**
 * Mock foreman assistant: keyword routing over the fixture state, standing in for the
 * backend's named queries + LLM phrasing. Answers are grounded in the same derived data
 * the scorecard shows, and cite inspections.
 *
 * Test hooks: include "#nokey" in a question to see the no_api_key state, "#guard" for guard_failed.
 */
import { oshaInspectionUrl, type AskRequest, type AskResponse, type Citation } from "../api/types";
import { toCard, toDetail } from "./derive";
import type { FxProject, FxSub } from "./model";

const fmtDay = (iso: string) =>
  new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(
    new Date(`${iso}T00:00:00Z`),
  );
const money = (n: number | null) =>
  n == null ? "not recorded" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

function cites(nrs: number[]): Citation[] {
  return [...new Set(nrs)].map((n) => ({ activity_nr: n, url: oshaInspectionUrl(n) }));
}

function reply(partial: Partial<AskResponse> & Pick<AskResponse, "status" | "answer">): AskResponse {
  return { citations: [], coverage: null, clarify_options: [], tools_used: [], ...partial };
}

const words = (s: string) => s.toLowerCase().replace(/[^a-z0-9 ]/g, " ");

function findSubsNamed(p: FxProject, q: string): FxSub[] {
  const text = words(q);
  return p.subs.filter((s) => {
    const first = words(s.entered_name).split(" ").filter((w) => w.length > 2 && !["the", "and", "inc", "llc"].includes(w));
    return first.length > 0 && first.slice(0, 2).every((w) => text.includes(w));
  });
}

const TRADE_WORDS: Record<string, string[]> = {
  roofer: ["roof"],
  roofing: ["roof"],
  framer: ["fram"],
  framing: ["fram"],
  electrician: ["electric"],
  electrical: ["electric"],
  concrete: ["concrete"],
  drywall: ["drywall"],
  steel: ["steel"],
  plumber: ["mechanical", "plumb"],
  mechanical: ["mechanical"],
  hvac: ["mechanical"],
  mason: ["mason"],
  masonry: ["mason"],
  glazier: ["glaz"],
  glazing: ["glaz"],
};

function findSubsByTrade(p: FxProject, q: string): FxSub[] {
  const text = words(q);
  for (const [word, stems] of Object.entries(TRADE_WORDS)) {
    if (new RegExp(`\\b${word}s?\\b`).test(text)) {
      return p.subs.filter((s) => stems.some((st) => `${s.trade ?? ""} ${s.entered_name}`.toLowerCase().includes(st)));
    }
  }
  return [];
}

function pendingGuard(s: FxSub): AskResponse | null {
  if (s.needs_adjudication || s.questions.length) {
    return reply({
      status: "needs_confirmation",
      answer: `**${s.entered_name}** has ${s.questions.length || "some"} unconfirmed record${s.questions.length === 1 ? "" : "s"} that could change the answer. Confirm ${s.questions.length === 1 ? "it" : "them"} on the sub's page first, then ask again.`,
      clarify_options: [{ sub_id: s.sub_id, name: s.entered_name }],
      tools_used: ["match_status"],
    });
  }
  return null;
}

function subSummary(p: FxProject, s: FxSub): AskResponse {
  const guard = pendingGuard(s);
  if (guard) return guard;
  const d = toDetail(s, p.lookback_years);
  const c = d.card;
  if (c.verdict === "no_record") {
    return reply({
      status: "answered",
      answer: `OSHA has **no inspection record** for ${s.entered_name}. That means unknown, not clean: ask them for their TRIR, EMR and safety program.`,
      coverage: d.coverage.sentence,
      tools_used: ["sub_summary"],
    });
  }
  const lines = [`**${s.entered_name}**: ${c.verdict_label}.`];
  for (const r of d.reasons.filter((r) => r.severity !== "info").slice(0, 3)) lines.push(`- ${r.label}`);
  lines.push(
    `- ${c.inspections_in_window} inspection${c.inspections_in_window === 1 ? "" : "s"} in the last ${c.window_years} years` +
      (c.serious_plus_rate != null ? `; serious+ rate ${c.serious_plus_rate.toFixed(2)} per inspection (trade median ${c.trade_p50?.toFixed(2) ?? "n/a"})` : ""),
  );
  if (d.open_cases.length) lines.push(`- ${d.open_cases.length} open case${d.open_cases.length > 1 ? "s" : ""}; those citations may change`);
  return reply({
    status: "answered",
    answer: lines.join("\n"),
    citations: cites(d.reasons.flatMap((r) => r.evidence).slice(0, 6)),
    coverage: d.coverage.sentence,
    tools_used: ["sub_summary"],
  });
}

function hazardAnswer(p: FxProject, subs: FxSub[], hazardCode: string, hazardName: string): AskResponse {
  const parts: string[] = [];
  const nrs: number[] = [];
  const coverage: string[] = [];
  for (const s of subs) {
    const guard = pendingGuard(s);
    if (guard) return guard;
    const d = toDetail(s, p.lookback_years);
    coverage.push(d.coverage.sentence);
    const h = d.hazards.find((x) => x.hazard_code === hazardCode);
    if (!h) {
      parts.push(`**${s.entered_name}**: no ${hazardName.toLowerCase()} citations in the OSHA record.`);
      continue;
    }
    const insp = s.inspections.filter((i) => s.establishments.find((e) => e.key === i.est)?.bucket === "matched" && i.cits.some((c) => c.hazard === hazardCode));
    nrs.push(...insp.map((i) => i.nr));
    const repeats = insp.flatMap((i) => i.cits.filter((c) => c.hazard === hazardCode && c.type === "R"));
    parts.push(
      `**${s.entered_name}**: yes. ${h.citations} ${hazardName.toLowerCase()} citation${h.citations > 1 ? "s" : ""} (${h.serious_plus} serious or worse) across ${h.inspections} inspection${h.inspections > 1 ? "s" : ""}, ${h.first_year}–${h.last_year}.` +
        (repeats.length ? ` ${repeats.length} ${repeats.length > 1 ? "were" : "was"} cited as **repeat**.` : "") +
        ` Most cited: ${h.top_standards.join(", ")}.`,
    );
  }
  return reply({
    status: "answered",
    answer: parts.join("\n\n"),
    citations: cites(nrs),
    coverage: coverage.join(" "),
    tools_used: ["citations_by_hazard"],
  });
}

export function answerQuestion(p: FxProject, req: AskRequest): AskResponse {
  const q = req.question.trim();
  const lower = q.toLowerCase();

  if (lower.includes("#nokey")) {
    return reply({ status: "no_api_key", answer: "The assistant needs an Anthropic API key, and none is configured on this server." });
  }
  if (lower.includes("#guard")) {
    return reply({
      status: "guard_failed",
      answer: "The drafted answer included a figure that didn't match the query results, so it was withheld.",
      tools_used: ["sub_summary"],
    });
  }
  if (!p.subs.length) {
    return reply({ status: "unanswerable", answer: "This project has no subs yet. Add them on the scorecard, then ask again." });
  }

  // "I mean <name>" follow-up from a clarify tap.
  const mean = /^i mean (.+)$/i.exec(q);
  if (mean) {
    const s = p.subs.find((x) => x.entered_name.toLowerCase() === mean[1].trim().toLowerCase()) ?? findSubsNamed(p, mean[1])[0];
    if (s) return subSummary(p, s);
  }

  if (/fatal|died|death|killed/.test(lower)) {
    const nrs: number[] = [];
    const lines: string[] = [];
    for (const s of p.subs) {
      const d = toDetail(s, p.lookback_years);
      for (const f of d.red_flags.filter((x) => x.kind === "fatality_cited" || x.kind === "fatality_inspected_not_cited")) {
        nrs.push(f.activity_nr);
        const where = f.bucket === "possible" ? " _(possible match, not counted)_" : "";
        lines.push(
          `- **${s.entered_name}**: ${f.label.toLowerCase()}, ${f.event_date ? fmtDay(f.event_date) : "date unknown"}${where}. Current penalty ${money(f.penalty_current)}.` +
            (f.shared_site_n ? ` ${f.shared_site_n} other employer${f.shared_site_n > 1 ? "s were" : " was"} inspected on that site.` : ""),
        );
      }
    }
    const unknown = p.subs.filter((s) => s.inspections.some((i) => i.fatality === "accident_outcome_unknown"));
    if (unknown.length) lines.push(`- Accident inspections with no outcome detail: ${unknown.map((s) => s.entered_name).join(", ")}.`);
    return reply({
      status: "answered",
      answer: lines.length
        ? `OSHA records show fatality investigations for:\n${lines.join("\n")}`
        : "None of the subs on this project has a fatality investigation in the OSHA record.",
      citations: cites(nrs),
      coverage: `Checked all ${p.subs.length} subs, all years. Accident detail runs through Mar 2025, so recent accidents may be missing.`,
      tools_used: ["fatality_history"],
    });
  }

  if (/open case|open inspection|still open|pending case/.test(lower)) {
    const nrs: number[] = [];
    const lines: string[] = [];
    for (const s of p.subs) {
      const d = toDetail(s, p.lookback_years);
      for (const o of d.open_cases) {
        nrs.push(o.activity_nr);
        lines.push(`- **${s.entered_name}**: opened ${fmtDay(o.open_date)}, ${o.site_city}, ${o.site_state}; ${o.citations} citation${o.citations === 1 ? "" : "s"} so far (${o.serious_plus} serious+).`);
      }
    }
    return reply({
      status: "answered",
      answer: lines.length
        ? `${lines.length} open case${lines.length > 1 ? "s" : ""}. Citations and penalties on open cases are provisional:\n${lines.join("\n")}`
        : "No open OSHA cases for the subs on this project.",
      citations: cites(nrs),
      coverage: `Checked all ${p.subs.length} subs. Data as of Oct 2, 2026.`,
      tools_used: ["open_cases"],
    });
  }

  if (/compare|everyone|all (the )?subs|rank|who.*worst/.test(lower)) {
    const cards = p.subs.map((s) => toCard(s, p.lookback_years));
    cards.sort((a, b) => (b.serious_plus_rate ?? -1) - (a.serious_plus_rate ?? -1));
    const rows = cards.map(
      (c) =>
        `| ${c.entered_name} | ${c.serious_plus_rate != null ? c.serious_plus_rate.toFixed(2) : "—"} | ${c.trade_p50 != null ? c.trade_p50.toFixed(2) : "—"} | ${c.inspections_in_window} |`,
    );
    const noRecord = cards.filter((c) => c.verdict === "no_record").map((c) => c.entered_name);
    return reply({
      status: "answered",
      answer:
        `Serious+ citations per inspection, last ${p.lookback_years} years:\n\n| Sub | Rate | Trade median | Insp. |\n|---|---|---|---|\n${rows.join("\n")}` +
        (noRecord.length ? `\n\n${noRecord.join(", ")}: no OSHA record, so no rate (unknown, not clean).` : ""),
      coverage: `Rates count matched records only; possible matches are not counted. Small inspection counts make rates noisy.`,
      tools_used: ["compare_subs"],
    });
  }

  const named = findSubsNamed(p, q);
  const byTrade = named.length ? [] : findSubsByTrade(p, q);
  const targets = named.length ? named : byTrade;

  const hazard =
    /fall|harness|tie[- ]?off|guardrail/.test(lower)
      ? ["fall", "Fall protection"]
      : /ladder/.test(lower)
        ? ["ladder", "Ladders"]
        : /scaffold/.test(lower)
          ? ["scaffold", "Scaffolding"]
          : /trench|excavat/.test(lower)
            ? ["excavation", "Excavation and trenching"]
            : /electric/.test(lower) && !named.length && !byTrade.length
              ? ["electrical", "Electrical"]
              : null;

  if (/\bdallas\b/.test(lower) && !named.length) {
    const opts = p.subs.filter((s) => s.entered_city?.toLowerCase() === "dallas");
    if (opts.length > 1) {
      return reply({
        status: "clarify",
        answer: `${opts.length} subs on this project are based in Dallas. Which one do you mean?`,
        clarify_options: opts.map((s) => ({ sub_id: s.sub_id, name: s.entered_name })),
      });
    }
  }

  if (targets.length > 1 && !hazard) {
    return reply({
      status: "clarify",
      answer: "More than one sub fits that. Which one do you mean?",
      clarify_options: targets.map((s) => ({ sub_id: s.sub_id, name: s.entered_name })),
    });
  }

  if (hazard) {
    const subs = targets.length ? targets : p.subs;
    return hazardAnswer(p, subs, hazard[0], hazard[1]);
  }

  if (targets.length === 1) return subSummary(p, targets[0]);

  return reply({
    status: "unanswerable",
    answer:
      "I can only answer from the OSHA records of the subs on this project: fatalities, citations by hazard (falls, ladders, scaffolds, trenching), open cases, comparisons, or a summary of one sub by name.",
    tools_used: [],
  });
}
