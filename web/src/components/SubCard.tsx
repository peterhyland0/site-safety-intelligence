import { Link } from "react-router";
import type { Reason, SubCard as SubCardT } from "../api/types";
import { formatRate, plural, yearRange } from "../lib/format";
import { rateComparison, VERDICTS } from "../lib/verdict";
import { IconChevronRight, IconFlag, IconInfo, IconOctagonAlert, IconQuestion, IconSpinner, IconTriangleAlert } from "./Icons";
import { VerdictChip } from "./VerdictChip";

export function ReasonLine({ reason }: { reason: Reason }) {
  const Icon = reason.severity === "high" ? IconOctagonAlert : reason.severity === "review" ? IconTriangleAlert : IconInfo;
  const tone = reason.severity === "high" ? "text-high-fg" : reason.severity === "review" ? "text-review-fg" : "text-muted";
  return (
    <span className="flex gap-2">
      <Icon size={16} className={`mt-0.5 shrink-0 ${tone}`} />
      <span>
        <span className="sr-only">{reason.severity === "info" ? "Note" : reason.severity === "high" ? "High concern" : "Review"}: </span>
        {reason.label}
      </span>
    </span>
  );
}

export function SubCard({
  card,
  projectId,
  resolveError,
  onRetryResolve,
  webChecking = false,
  webCheckError,
}: {
  card: SubCardT;
  projectId: string;
  /** Set when the adjudicate call failed; the card offers a retry. */
  resolveError?: string | null;
  onRetryResolve?: () => void;
  /** The project's automatic web check is pressing this sub's button now, or its press failed. */
  webChecking?: boolean;
  webCheckError?: string | null;
}) {
  const meta = VERDICTS[card.verdict];
  const href = `/projects/${encodeURIComponent(projectId)}/subs/${encodeURIComponent(card.sub_id)}`;
  const where = [card.entered_city, card.entered_state].filter(Boolean).join(", ");
  const years = yearRange(card.first_year, card.last_year);
  const showOshaName =
    card.display_name && card.display_name.toUpperCase().replace(/[^A-Z0-9]/g, "") !== card.entered_name.toUpperCase().replace(/[^A-Z0-9]/g, "");
  const cmp = rateComparison(card);
  const adjudicating = card.match_status === "needs_adjudication";
  const smallSample = card.inspections_in_window > 0 && card.inspections_in_window < 3;

  return (
    <article
      className={`card relative border-l-4 p-4 transition-colors hover:border-line-strong sm:p-5 ${meta.accent} ${
        card.verdict === "no_record" ? "border-dashed" : ""
      }`}
      aria-labelledby={`sub-${card.sub_id}`}
    >
      {/* Phone: verdict chip sits above the name (DOM order keeps name first for screen readers). */}
      <div className="flex flex-col-reverse items-start gap-2 sm:flex-row sm:justify-between sm:gap-3">
        <div className="min-w-0 flex-1">
          <h3 id={`sub-${card.sub_id}`} className="text-lg leading-snug font-semibold text-ink">
            <Link to={href} className="after:absolute after:inset-0 after:rounded-xl hover:underline">
              {card.entered_name}
            </Link>
          </h3>
          <p className="text-sm text-muted">
            {[where, card.trade_label ?? card.trade].filter(Boolean).join(" · ")}
          </p>
          {showOshaName ? <p className="text-xs text-muted">OSHA name: {card.display_name}</p> : null}
          {card.same_records_as?.length ? (
            <p className="mt-1 flex gap-1.5 text-sm font-medium text-review-fg">
              <IconTriangleAlert size={16} className="mt-0.5 shrink-0" />
              <span>
                Same OSHA record as {card.same_records_as.map((s) => s.name).join(", ")}. Same company? Remove one.
              </span>
            </p>
          ) : null}
        </div>
        <VerdictChip verdict={card.verdict} label={card.verdict_label} />
      </div>

      {adjudicating && resolveError ? (
        <div role="alert" className="relative z-10 mt-3 flex flex-wrap items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm text-ink-2">
          <span className="flex-1">Couldn't resolve the uncertain records yet. {resolveError}</span>
          {onRetryResolve ? (
            <button type="button" className="btn btn-secondary btn-sm" onClick={onRetryResolve}>
              Try again
            </button>
          ) : null}
        </div>
      ) : adjudicating ? (
        <p role="status" className="mt-3 flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm text-ink-2">
          <IconSpinner size={16} />
          {card.profile_status === "pending" ? "Looking up the company, then resolving " : "Resolving "}
          {card.possible_inspections > 0 ? `${plural(card.possible_inspections, "uncertain record")}…` : "uncertain records…"}
        </p>
      ) : webChecking ? (
        <p role="status" className="mt-3 flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm text-ink-2">
          <IconSpinner size={16} />
          Checking {plural(card.web_unchecked ?? 0, "leftover record")} on the web…
        </p>
      ) : webCheckError ? (
        <p role="alert" className="mt-3 rounded-lg bg-surface-2 px-3 py-2 text-sm text-ink-2">
          Couldn't check the leftover records on the web. {webCheckError}
        </p>
      ) : null}

      {card.verdict === "no_record" ? (
        <p className="mt-3 text-sm text-ink-2">
          Not found in OSHA inspection records. That means <strong className="font-semibold">unknown, not clean</strong>: ask
          the sub for their TRIR, EMR and safety program.
        </p>
      ) : card.reasons.length ? (
        <ul className="mt-3 space-y-1.5 text-[15px] text-ink" aria-label="Top reasons">
          {card.reasons.slice(0, 2).map((r) => (
            <li key={`${r.code}-${r.label}`}>
              <ReasonLine reason={r} />
            </li>
          ))}
        </ul>
      ) : card.verdict === "no_recent" ? (
        <p className="mt-3 text-sm text-ink-2">
          No inspections in the last {card.window_years} years{card.last_year ? `; last inspected ${card.last_year}` : ""}.
        </p>
      ) : null}

      {card.verdict !== "no_record" ? (
        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs text-muted">Serious+ per inspection</dt>
            {card.serious_plus_rate != null ? (
              <dd className="font-semibold text-ink tabular-nums">
                {formatRate(card.serious_plus_rate)}
                {card.trade_p50 != null ? (
                  <span className="font-normal text-muted"> vs {formatRate(card.trade_p50)} median</span>
                ) : null}
              </dd>
            ) : (
              <dd className="text-muted">No inspections in window</dd>
            )}
            {cmp || smallSample ? (
              <dd className="text-xs text-muted">
                {[cmp, smallSample ? `only ${plural(card.inspections_in_window, "inspection")}` : null].filter(Boolean).join("; ")}
              </dd>
            ) : null}
          </div>
          <div>
            <dt className="text-xs text-muted">Inspections, last {card.window_years} yr</dt>
            <dd className="font-semibold text-ink tabular-nums">
              {card.inspections_in_window}
              <span className="font-normal text-muted"> of {card.matched_inspections} total</span>
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Red flags (all years)</dt>
            <dd className="flex items-center gap-1 font-semibold text-ink tabular-nums">
              {card.red_flag_count > 0 ? <IconFlag size={14} className="text-high-fg" /> : null}
              {card.red_flag_count}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Active</dt>
            <dd className="text-ink">
              {years ?? "—"}
              {card.states.length ? <span className="text-muted"> · {card.states.join(", ")}</span> : null}
            </dd>
          </div>
          {card.trir_latest != null ? (
            <div>
              <dt className="text-xs text-muted">TRIR (latest, self-reported)</dt>
              <dd className="font-semibold text-ink tabular-nums">{formatRate(card.trir_latest, 1)}</dd>
            </div>
          ) : null}
          {card.licence_status ? (
            <div>
              <dt className="text-xs text-muted">Licence</dt>
              <dd className="text-ink">{card.licence_status}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      {card.pending_questions > 0 || card.possible_inspections > 0 ? (
        <div className="relative z-10 mt-4 flex flex-wrap gap-2">
          {card.pending_questions > 0 ? (
            <Link
              to={`${href}#questions`}
              className="pill min-h-8 border-accent bg-accent-soft px-3 text-accent hover:underline"
            >
              <IconQuestion size={14} />
              {plural(card.pending_questions, "question")} to answer
            </Link>
          ) : null}
          {card.possible_inspections > 0 && !adjudicating ? (
            <span className="pill min-h-8 border-line-strong bg-surface px-3 text-ink-2">
              +{plural(card.possible_inspections, "possible-match inspection")}, not counted
            </span>
          ) : null}
        </div>
      ) : null}

      <IconChevronRight className="pointer-events-none absolute right-3 bottom-4 hidden text-muted sm:block" aria-hidden="true" />
    </article>
  );
}
