import type { WebCheckInfo, WebCheckResult } from "../api/types";
import { plural } from "../lib/format";
import { IconSpinner } from "./Icons";

/** One line on what a press found and what's left. */
export function webCheckSummary(r: WebCheckResult): string {
  const found = [
    r.same ? `${plural(r.same, "record")} tied to this sub` : null,
    r.different ? `${plural(r.different, "record")} to another company` : null,
    r.unsure ? `${plural(r.unsure, "record")} not settled` : null,
  ].filter(Boolean);
  const out = [found.length ? `Checked on the web: ${found.join(", ")}.` : "Nothing new found."];
  if (r.questions) out.push(`${r.questions === 1 ? "A question about them is" : "Questions about them are"} at the top of the page.`);
  if (r.limit_reached) out.push("Today's web-check limit is reached; the rest can be checked tomorrow.");
  else if (r.left) out.push(`${plural(r.left, "record")} still to check: press the button again.`);
  return out.join(" ");
}

/**
 * The web check, above the match buckets: a web search on each undecided possible or excluded record says whose it
 * is, and what it finds comes back as a question. It only suggests; nothing is counted or dropped until the GC
 * answers.
 */
export function WebCheck({
  info,
  busy,
  result,
  onCheck,
}: {
  info: WebCheckInfo;
  busy: boolean;
  result: WebCheckResult | null;
  onCheck: () => void;
}) {
  return (
    <div className="mb-4 rounded-xl border border-line bg-surface px-3.5 py-3">
      <p className="text-sm text-ink-2">
        {info.unchecked
          ? `${plural(info.unchecked, "possible or excluded record")} below ${info.unchecked === 1 ? "hasn't" : "haven't"} been checked on the web. `
          : "Every possible and excluded record below has been checked on the web. "}
        A web search on each says whose record it is; what it finds comes back as a question, and nothing is counted or
        dropped without your answer.
      </p>
      {info.unchecked ? (
        <button type="button" className="btn btn-secondary btn-sm mt-3" disabled={busy} onClick={onCheck}>
          {busy ? (
            <>
              <IconSpinner size={14} /> Checking records on the web (up to a minute)…
            </>
          ) : (
            `Check ${plural(info.unchecked, "record")} on the web`
          )}
        </button>
      ) : null}
      {result ? (
        <p role="status" className="mt-2 text-sm text-ink-2">
          {webCheckSummary(result)}
        </p>
      ) : null}
    </div>
  );
}
