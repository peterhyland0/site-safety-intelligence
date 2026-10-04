import type { HazardRow, ItaYear, Licence, MatchedEstablishment, MatchQuestion, RedFlag } from "../api/types";
import { formatDate, formatInt, formatMoney, formatRate, plural, yearRange } from "../lib/format";
import { IconFlag, IconOctagonAlert } from "./Icons";
import { EvidenceChip } from "./InspectionSheet";

// --- Match questions ---------------------------------------------------------------------------------
const SUGGESTION: Record<NonNullable<MatchQuestion["ai_suggestion"]>, string> = {
  same: "AI read: probably the same company",
  different: "AI read: probably a different company",
  unsure: "AI read: unsure",
};

// a question built from a company profile: the suggestion comes from the company's own pages, not the AI's read
function profileSuggestion(s: NonNullable<MatchQuestion["ai_suggestion"]>, several: boolean): string {
  const these = several ? "these addresses" : "this address";
  if (s === "same") return `The company's website lists ${these}`;
  if (s === "different") return `The company's website doesn't list ${these}`;
  return `The company lists the city, but not ${these}`;
}

// a question from the web check: the suggestion is what a web page says about whose record it is
function webSuggestion(s: NonNullable<MatchQuestion["ai_suggestion"]>, several: boolean): string {
  const lead = several ? "Web pages tie these records" : "A web page ties this record";
  if (s === "same") return `${lead} to your sub`;
  if (s === "different") return `${lead} to another company`;
  return "The web search didn't settle it";
}

function host(url: string): string {
  return url.replace(/^https?:\/\/(www\.)?/, "").split("/")[0];
}

export function QuestionCard({
  question,
  establishments,
  onAnswer,
  onRecord,
  busy,
}: {
  question: MatchQuestion;
  establishments: MatchedEstablishment[];
  onAnswer: (answer: "yes" | "no") => void;
  /** a grouped question can be answered record by record (the record then leaves the question) */
  onRecord?: (establishmentKey: string, bucket: "matched" | "excluded") => void;
  busy: boolean;
}) {
  const ests = establishments.filter((e) => question.establishment_keys.includes(e.establishment_key));
  const grouped = ests.length > 1;
  const fromProfile = question.kind === "profile";
  const fromWeb = question.kind === "web";
  const sources = question.sources ?? [];
  // the web check keys each page to its records: the quote is shown under the record it's about
  const sourceFor = (key: string) => (fromWeb ? sources.find((s) => s.keys?.includes(key)) : undefined);
  return (
    <li className="rounded-xl border-2 border-accent/40 bg-accent-soft p-4">
      <p className="text-[17px] leading-snug font-semibold text-ink">{question.text}</p>
      {ests.length ? (
        <ul className="mt-2 space-y-1 text-sm text-ink-2">
          {ests.map((e) => (
            <li
              key={e.establishment_key}
              className={grouped ? "flex flex-wrap items-center justify-between gap-2 py-1" : undefined}
            >
              <span>
                {e.display_name}
                {e.address ? ` · ${[e.address, e.city, e.state].filter(Boolean).join(", ")}` : ""}
                {` · ${plural(e.inspections, "inspection")}`}
                {e.has_red_flags ? (
                  <span className="ml-1 inline-flex items-center gap-1 font-medium text-high-fg">
                    <IconFlag size={13} /> carries red flags
                  </span>
                ) : null}
                {sourceFor(e.establishment_key) ? <WebQuote source={sourceFor(e.establishment_key)!} /> : null}
              </span>
              {grouped && onRecord ? (
                <span className="flex gap-1.5" role="group" aria-label={`Is the record in ${e.city ?? "this place"} your sub?`}>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={busy}
                    onClick={() => onRecord(e.establishment_key, "matched")}
                  >
                    Mine
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={busy}
                    onClick={() => onRecord(e.establishment_key, "excluded")}
                  >
                    Not mine
                  </button>
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {question.ai_suggestion || question.ai_rationale ? (
        <p className="mt-2 text-sm text-ink-2">
          {question.ai_suggestion ? (
            <span className="font-medium">
              {fromWeb
                ? webSuggestion(question.ai_suggestion, question.establishment_keys.length > 1)
                : fromProfile || sources.length
                  ? profileSuggestion(question.ai_suggestion, question.establishment_keys.length > 1)
                  : SUGGESTION[question.ai_suggestion]}
              .{" "}
            </span>
          ) : null}
          {fromWeb ? null : question.ai_rationale /* a web question's quotes are under their records */}
        </p>
      ) : null}
      {sources.length && !fromWeb ? (
        <ul className="mt-2 space-y-1 text-sm" aria-label="Sources">
          {sources.map((s) => (
            <li key={s.url} className="min-w-0 text-ink-2">
              <a href={s.url} target="_blank" rel="noreferrer" className="font-medium break-all text-ink underline underline-offset-2">
                {s.title || s.url.replace(/^https?:\/\/(www\.)?/, "")}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="mt-2 text-xs text-muted">
        {fromWeb
          ? "From a web search: nothing is counted or dropped until you answer. Each quote is copied from the page linked."
          : fromProfile
          ? "These records aren't counted until you answer. The locations come from the company's own pages, quoted above."
          : "Records with red flags are never counted or dropped without your answer. The AI only sees names, addresses, trades and years, not safety history."}
      </p>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <button
          type="button"
          className="btn btn-primary min-h-14 text-base"
          onClick={() => onAnswer("yes")}
          disabled={busy}
        >
          {grouped ? "All of these are my sub" : "Yes, same company"}
        </button>
        <button
          type="button"
          className="btn min-h-14 border-2 border-line-strong bg-surface text-base text-ink hover:bg-surface-2"
          onClick={() => onAnswer("no")}
          disabled={busy}
        >
          {grouped ? "None of these" : "No, different"}
        </button>
      </div>
    </li>
  );
}

// what a web page says about one record: whose it is, the quote, and the page
function WebQuote({ source }: { source: NonNullable<MatchQuestion["sources"]>[number] }) {
  return (
    <span className="mt-0.5 block text-[13px] text-muted">
      {source.owner ? <span className="font-medium text-ink-2">{source.owner}: </span> : null}“{source.quote}” ·{" "}
      <a href={source.url} target="_blank" rel="noreferrer" className="break-all underline underline-offset-2">
        {host(source.url)}
      </a>
    </span>
  );
}

// --- Red flags -----------------------------------------------------------------------------------------
const KIND_LABEL: Record<RedFlag["kind"], string> = {
  fatality_cited: "Fatality, cited",
  fatality_inspected_not_cited: "Fatality, not cited",
  fatality_pending: "Fatality/catastrophe, investigation open",
  fatcat_cited: "Fatality/catastrophe, cited",
  fatcat_not_cited: "Fatality/catastrophe, not cited",
  fatcat_site_cited: "Cited at a fatality/catastrophe site",
  catastrophe_cited: "Catastrophe, cited",
  fatcat_no_inspection: "Fatality/catastrophe, not inspected",
  willful: "Willful",
  repeat: "Repeat",
  fta: "Failure to abate",
};

function penalty(f: RedFlag) {
  if (f.penalty_current == null && f.penalty_initial == null) return "not recorded";
  if (f.penalty_initial != null && f.penalty_current != null && f.penalty_initial !== f.penalty_current) {
    return `${formatMoney(f.penalty_current)} (initially ${formatMoney(f.penalty_initial)})`;
  }
  return formatMoney(f.penalty_current ?? f.penalty_initial);
}

export function RedFlagsTable({ flags }: { flags: RedFlag[] }) {
  if (!flags.length) {
    return <p className="text-sm text-ink-2">No fatalities, willful, repeat or failure-to-abate citations in any year.</p>;
  }
  return (
    <>
      {/* Phone: stacked list */}
      <ul className="divide-y divide-line md:hidden">
        {flags.map((f, i) => (
          <li key={`${f.activity_nr}-${f.kind}-${f.citation_id ?? i}`} className="py-3 text-sm">
            <p className="flex items-center gap-1.5 font-semibold text-ink">
              <IconOctagonAlert size={15} className="text-high-fg" />
              {KIND_LABEL[f.kind]}
              {f.bucket === "possible" ? <span className="pill border-line-strong text-ink-2">possible match, not counted</span> : null}
            </p>
            <p className="text-ink-2">{f.label}</p>
            <p className="text-ink-2">
              {formatDate(f.event_date)} · {f.standard ? <span className="font-mono text-[13px]">{f.standard}</span> : "—"} ·{" "}
              {penalty(f)}
            </p>
            <p className="text-xs text-muted">
              {f.establishment_name}
              {f.case_provisional ? " · open case, provisional" : ""}
              {f.shared_site_n ? ` · ${plural(f.shared_site_n, "other employer")} on site` : ""}
            </p>
            <p className="mt-1">
              <EvidenceChip activityNr={f.activity_nr} />
            </p>
          </li>
        ))}
      </ul>
      {/* Desktop: table */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-muted">
            <tr className="border-b border-line">
              <th scope="col" className="py-2 pr-3 font-medium">Kind</th>
              <th scope="col" className="py-2 pr-3 font-medium">Date</th>
              <th scope="col" className="py-2 pr-3 font-medium">Detail</th>
              <th scope="col" className="py-2 pr-3 font-medium">Standard</th>
              <th scope="col" className="py-2 pr-3 font-medium">Penalty</th>
              <th scope="col" className="py-2 font-medium">Inspection</th>
            </tr>
          </thead>
          <tbody>
            {flags.map((f, i) => (
              <tr key={`${f.activity_nr}-${f.kind}-${f.citation_id ?? i}`} className="border-b border-line align-top">
                <td className="py-2 pr-3 font-medium whitespace-nowrap text-ink">
                  {KIND_LABEL[f.kind]}
                  {f.bucket === "possible" ? <span className="block text-xs font-normal text-muted">possible match, not counted</span> : null}
                </td>
                <td className="py-2 pr-3 whitespace-nowrap text-ink-2">{formatDate(f.event_date)}</td>
                <td className="py-2 pr-3 text-ink-2">
                  {f.label}
                  <span className="block text-xs text-muted">
                    {f.establishment_name}
                    {f.case_provisional ? " · open case, provisional" : ""}
                    {f.shared_site_n ? ` · ${plural(f.shared_site_n, "other employer")} on site` : ""}
                  </span>
                </td>
                <td className="py-2 pr-3 font-mono text-[13px] whitespace-nowrap text-ink-2">{f.standard ?? "—"}</td>
                <td className="py-2 pr-3 text-ink-2 tabular-nums">{penalty(f)}</td>
                <td className="py-2">
                  <EvidenceChip activityNr={f.activity_nr} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// --- Hazards -------------------------------------------------------------------------------------------
export function HazardBreakdown({ hazards }: { hazards: HazardRow[] }) {
  if (!hazards.length) return <p className="text-sm text-ink-2">No citations to break down.</p>;
  const max = Math.max(...hazards.map((h) => h.citations));
  return (
    <ul className="space-y-3" aria-label="Citations by hazard">
      {hazards.map((h) => (
        <li key={h.hazard_code}>
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="font-medium text-ink">{h.label}</span>
            <span className="shrink-0 text-ink-2 tabular-nums">
              {plural(h.citations, "citation")}
              <span className="text-muted"> · {h.serious_plus} serious+</span>
            </span>
          </div>
          <div className="mt-1 h-2 w-full rounded-full bg-surface-2" aria-hidden="true">
            <div className="h-2 rounded-full bg-chart-1" style={{ width: `${Math.max(4, (h.citations / max) * 100)}%` }} />
          </div>
          <p className="mt-1 text-xs text-muted">
            {plural(h.inspections, "inspection")}
            {yearRange(h.first_year, h.last_year) ? ` · ${yearRange(h.first_year, h.last_year)}` : ""}
            {h.top_standards.length ? (
              <>
                {" · "}
                <span className="font-mono">{h.top_standards.join(", ")}</span>
              </>
            ) : null}
          </p>
        </li>
      ))}
    </ul>
  );
}

// --- Injury rates (OSHA ITA / Form 300A) ----------------------------------------------------------------
export function InjuryRates({ rows }: { rows: ItaYear[] }) {
  const sorted = [...rows].sort((a, b) => b.year - a.year);
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[20rem] text-right text-sm tabular-nums">
          <caption className="sr-only">Injury rates by year</caption>
          <thead className="text-xs text-muted">
            <tr className="border-b border-line">
              <th scope="col" className="py-2 pr-2 text-left font-medium">Year</th>
              <th scope="col" className="px-2 py-2 font-medium">TRIR</th>
              <th scope="col" className="px-2 py-2 font-medium">DART</th>
              <th scope="col" className="px-2 py-2 font-medium">
                <abbr title="Pooled TRIR for the sub's trade: all filers' cases divided by all filers' hours" className="no-underline">
                  Industry rate
                </abbr>
              </th>
              <th scope="col" className="py-2 pl-2 font-medium">Hours</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={`${r.year}-${r.establishment_name}`} className={`border-b border-line ${r.flagged ? "text-muted" : "text-ink-2"}`}>
                <th scope="row" className="py-2 pr-2 text-left font-medium text-ink">
                  {r.year}
                  {r.flagged ? <span className="block text-xs font-normal text-muted">implausible, not compared</span> : null}
                </th>
                <td className="px-2 py-2 font-semibold">{formatRate(r.trir, 1)}</td>
                <td className="px-2 py-2">{formatRate(r.dart, 1)}</td>
                <td className="px-2 py-2">{formatRate(r.peer_trir, 1)}</td>
                <td className="py-2 pl-2">{formatInt(r.hours)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-muted">
        Self-reported to OSHA on Form 300A (cases per 100 full-time workers). Firms under 20 employees don't file, so a
        missing rate says nothing about safety. Industry rate is the trade's pooled TRIR: all filers' cases divided by all
        filers' hours, the way BLS reports industry rates.
      </p>
    </div>
  );
}

export function LicenceCard({ licence }: { licence: Licence }) {
  const active = licence.status?.toLowerCase() === "active";
  return (
    <div className="rounded-lg border border-line p-3 text-sm">
      <p className="font-semibold text-ink">
        {licence.source} · <span className="font-mono">{licence.number}</span>
      </p>
      <p className="text-ink-2">{licence.name}</p>
      <dl className="mt-2 grid grid-cols-2 gap-2">
        <div>
          <dt className="text-xs text-muted">Status</dt>
          <dd className={active ? "font-medium text-clear-fg" : "font-medium text-ink"}>{licence.status ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Expires</dt>
          <dd className="text-ink">{formatDate(licence.expires)}</dd>
        </div>
        {licence.specialty ? (
          <div className="col-span-2">
            <dt className="text-xs text-muted">Specialty</dt>
            <dd className="text-ink">{licence.specialty}</dd>
          </div>
        ) : null}
      </dl>
    </div>
  );
}

