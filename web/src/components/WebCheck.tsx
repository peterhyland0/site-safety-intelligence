import { useId } from "react";
import type { WebCheckInfo, WebCheckResult } from "../api/types";
import { plural } from "../lib/format";
import { IconSpinner } from "./Icons";

/** One line on what a press found and what's left. `auto`: the presses are automatic, so nobody presses again. */
export function webCheckSummary(r: WebCheckResult, auto = false): string {
  const found = [
    r.same ? `${plural(r.same, "record")} tied to this sub` : null,
    r.different ? `${plural(r.different, "record")} to another company` : null,
    r.unsure ? `${plural(r.unsure, "record")} not settled` : null,
  ].filter(Boolean);
  const out = [found.length ? `Checked on the web: ${found.join(", ")}.` : "Nothing new found."];
  const settled = [
    r.matched ? `matched ${plural(r.matched, "record")}` : null,
    r.excluded ? `excluded ${plural(r.excluded, "record")}` : null,
  ].filter(Boolean);
  if (settled.length) out.push(`Auto-match ${settled.join(" and ")}.`);
  if (r.questions) out.push(`${r.questions === 1 ? "A question about them is" : "Questions about them are"} at the top of the page.`);
  if (r.limit_reached) out.push("Today's web-check limit is reached; the rest can be checked tomorrow.");
  else if (r.left) out.push(`${plural(r.left, "record")} still to check${auto ? "." : ": press the button again."}`);
  return out.join(" ");
}

export type WebCheckSettingsPatch = { auto_web_check?: boolean; auto_web_match?: boolean };

/**
 * The project's web check settings, in the Add subs box: check each sub's leftover records on the web once it's
 * matched, without the button, and take the web's answer without asking. They save for the whole project at once.
 */
export function WebCheckSettings({
  autoCheck,
  autoMatch,
  onChange,
  busy = false,
}: {
  autoCheck: boolean;
  autoMatch: boolean;
  onChange: (patch: WebCheckSettingsPatch) => void;
  busy?: boolean;
}) {
  const id = useId();
  const options = [
    {
      key: "check",
      checked: autoCheck,
      patch: (on: boolean) => ({ auto_web_check: on }),
      label: "Check leftover records on the web automatically",
      hint:
        "Once each sub is matched, its possible and excluded records are looked up on the web while this project is " +
        "open, without pressing a button. For every sub on this project. Each search uses a web-search credit, within " +
        "the day's limit.",
    },
    {
      key: "match",
      checked: autoMatch,
      patch: (on: boolean) => ({ auto_web_match: on }),
      label: "Auto-match from the web check",
      hint:
        "A record the web ties to your sub is matched, and one it ties to another company excluded, without asking " +
        "you. Records with red flags still come to you as a question.",
    },
  ];
  return (
    <fieldset className="space-y-2.5" disabled={busy}>
      <legend className="sr-only">Web check settings for this project</legend>
      {options.map((o) => (
        <div key={o.key} className="flex items-start gap-2.5">
          <input
            id={`${id}-${o.key}`}
            type="checkbox"
            className="mt-1 size-4 shrink-0 accent-[var(--accent)] disabled:cursor-not-allowed"
            checked={o.checked}
            onChange={(e) => onChange(o.patch(e.target.checked))}
            aria-describedby={`${id}-${o.key}-hint`}
          />
          <div className="min-w-0">
            <label htmlFor={`${id}-${o.key}`} className="text-sm font-medium text-ink">
              {o.label}
            </label>
            <p id={`${id}-${o.key}-hint`} className="text-xs text-muted">
              {o.hint}
            </p>
          </div>
        </div>
      ))}
    </fieldset>
  );
}

/**
 * The web check, above the match buckets: a web search on each undecided possible or excluded record says whose it
 * is, and what it finds comes back as a question, or with the project's auto-match settles the record (never a
 * red-flagged one). With the project's automatic check on (set in the Add subs box), the page presses the button.
 */
export function WebCheck({
  info,
  busy,
  result,
  onCheck,
  error,
}: {
  info: WebCheckInfo;
  busy: boolean;
  result: WebCheckResult | null;
  onCheck: () => void;
  error?: string | null;
}) {
  const auto = !!info.auto_check;
  return (
    <div className="mb-4 rounded-xl border border-line bg-surface px-3.5 py-3">
      <p className="text-sm text-ink-2">
        {info.unchecked
          ? `${plural(info.unchecked, "possible or excluded record")} below ${info.unchecked === 1 ? "hasn't" : "haven't"} been checked on the web. `
          : info.checked
            ? "Every possible and excluded record below has been checked on the web. "
            : "No record below is waiting for a web check. "}
        {info.auto_match
          ? "A web search on each says whose record it is, and auto-match takes its answer: a record tied to your sub " +
            "is matched and one tied to another company excluded. Records with red flags come back as a question."
          : "A web search on each says whose record it is; what it finds comes back as a question, and nothing is " +
            "counted or dropped without your answer."}
      </p>
      {info.unchecked ? (
        <button type="button" className="btn btn-secondary btn-sm mt-3" disabled={busy} onClick={onCheck}>
          {busy ? (
            <>
              <IconSpinner size={14} /> Checking records on the web{auto ? " automatically" : ""} (up to a minute)…
            </>
          ) : (
            `Check ${plural(info.unchecked, "record")} on the web`
          )}
        </button>
      ) : null}
      {result ? (
        <p role="status" className="mt-2 text-sm text-ink-2">
          {webCheckSummary(result, auto)}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-2 text-sm text-high-fg">
          Couldn't check on the web: {error}
        </p>
      ) : null}
    </div>
  );
}
