import type { ReactNode } from "react";
import { VerdictChip } from "../components/VerdictChip";
import { useTitle } from "../lib/useTitle";
import { VERDICT_ORDER, VERDICTS } from "../lib/verdict";

const RULES: Record<(typeof VERDICT_ORDER)[number], string> = {
  high: "In the last 10 years: a fatality investigation where the sub was cited for serious violations, a willful violation, or a failure to fix a cited hazard. Or, inside the lookback window: repeat violations in two or more separate inspections, or a serious-citation rate in the top 10% of the trade (5+ inspections).",
  review:
    "Worth a conversation: any of the High events more than 10 years ago; being on a site where a fatality was investigated without being cited; one repeat violation in the window; the same hazard cited in 3+ inspections (or 2+ in the window); an open case with serious citations; a serious rate above the trade's 75th percentile; an unconfirmed possible match carrying red flags; a self-reported DART rate above most peers; or a lapsed licence.",
  no_record:
    "No inspections matched. OSHA inspects only a small share of workplaces, so this is unknown, not clean. Ask the sub for TRIR, EMR and their safety program.",
  no_recent: "Inspections exist, but none inside the lookback window, and nothing older met a concern rule.",
  no_flags: "Inspected inside the window and nothing met a concern rule. Still check TRIR and EMR.",
};

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="card p-4 sm:p-5">
      <h2 className="section-title mb-2">{title}</h2>
      <div className="space-y-2 text-[15px] leading-relaxed text-ink-2">{children}</div>
    </section>
  );
}

export function MethodologyPage() {
  useTitle("How it works");
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">How it works</h1>
        <p className="mt-1 text-ink-2">
          Site Safety Intelligence turns OSHA's public enforcement records into a prequalification view of the subs on a
          bid. It reports what the record shows, with links to every inspection. It does not rate companies' safety
          culture, and a missing record is never treated as a good one.
        </p>
      </div>

      <Block title="Verdicts">
        <p>Each sub gets one verdict from fixed, tested rules. Every reason links to the inspections behind it.</p>
        <ul className="mt-2 space-y-3">
          {VERDICT_ORDER.map((v) => (
            <li key={v} className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:gap-3">
              <span className="sm:w-44 sm:shrink-0">
                <VerdictChip verdict={v} label={VERDICTS[v].label} />
              </span>
              <span>{RULES[v]}</span>
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Lookback window and rates">
        <p>
          Rates, trends and repeat violations use the project's lookback window (3, 5 or 10 years). Cited fatalities,
          willful violations and failures to abate count as High concern for 10 years and are still flagged for review
          after that, because a GC wants to know about them however old they are. The red-flag table always lists every
          year.
        </p>
        <p>
          <strong className="font-semibold text-ink">Serious+ rate</strong> is serious, willful and repeat citations per
          inspection inside the window. It is compared with the median and 75th percentile for the sub's trade (its most
          frequent industry code), never the average, because one large contractor can skew an average. Counts are shown next
          to every rate; a rate from one or two inspections is labelled as a small sample.
        </p>
        <p>Deleted citations are excluded. Penalties show the current amount after any settlement, with the initial amount alongside.</p>
      </Block>

      <Block title="Finding a sub in OSHA's records">
        <p>
          OSHA has no company ID, so the same firm appears under many spellings and addresses. Records are first grouped
          into <em>establishments</em>: an exact cleaned name, mailing address and zip. Each establishment is then sorted
          into one of three buckets for the sub you entered:
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong className="font-semibold text-ink">Matched</strong>: same name in your state, the same address, or a
            distinctive name elsewhere. Counted.
          </li>
          <li>
            <strong className="font-semibold text-ink">Possible, not counted</strong>: a generic name in another state, or a
            similar name at a different address. Shown as "+N" so nothing is hidden.
          </li>
          <li>
            <strong className="font-semibold text-ink">Excluded lookalikes</strong>: a different company with a similar
            name. Collapsed, but listed.
          </li>
        </ul>
        <p>
          Rules decide most cases. Only the uncertain leftovers go to an AI adjudicator, which sees identity evidence only
          (names, addresses, trade, years) and never the safety history, and must give a one-line rationale. Any uncertain
          record carrying a red flag becomes a yes/no question for the GC instead: a serious record is never silently
          added or dropped. You can move any establishment between buckets, and the method (rule, AI or GC) is always
          shown.
        </p>
      </Block>

      <Block title="Foreman assistant">
        <p>
          The assistant answers from a fixed set of tested queries (summary, citations by hazard, fatality history, open
          cases, comparisons) rather than writing its own database queries. Every number in an answer must come from a
          query result and cite an inspection, and each answer ends with what was covered. It won't answer about a sub
          until that sub's uncertain matches are settled.
        </p>
      </Block>

      <Block title="Data sources">
        <ul className="list-disc space-y-1 pl-5">
          <li>
            OSHA enforcement data from the Department of Labor (inspections, citations, accidents and narratives), refreshed
            from the official bulk files. Federal and state-plan inspections are both included and labelled.
          </li>
          <li>OSHA Injury Tracking Application (Form 300A): TRIR and DART, self-reported; firms under 20 employees don't file.</li>
          <li>State contractor licence registries where available (WA L&I, OR CCB, CA CSLB).</li>
        </ul>
      </Block>

      <Block title="Known limits">
        <ul className="list-disc space-y-1 pl-5">
          <li>Most firms are never inspected. No record means unknown.</li>
          <li>Recent cases are often still open; their citations and penalties can change. They are marked provisional.</li>
          <li>OSHA's accident detail lags: coverage thins after 2023 and stops in early 2025, so recent fatality narratives may be missing.</li>
          <li>
            On shared sites, one accident is copied onto every employer inspected; the record can't say whose worker was
            hurt. These are flagged.
          </li>
          <li>Penalties before about 2010 are often blank (not $0), so older history is judged by citation type.</li>
          <li>Old records are less certain to belong to today's company; firms are sold and renamed.</li>
          <li>EMR (experience modifier) isn't public. Ask the sub for it.</li>
        </ul>
      </Block>
    </div>
  );
}
