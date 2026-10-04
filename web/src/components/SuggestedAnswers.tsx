import { useId, useState } from "react";
import { Link } from "react-router";
import { api, errorMessage } from "../api/client";
import type { ProjectQuestion } from "../api/types";
import { plural } from "../lib/format";
import { suggestionLabel } from "./EvidenceSections";
import { IconFlag, IconQuestion } from "./Icons";
import { InlineError } from "./ui";

const hasSuggestion = (q: ProjectQuestion) => q.ai_suggestion === "same" || q.ai_suggestion === "different";

/**
 * The project's open match questions that come with a suggestion, answered all at once with it. Every one starts
 * ticked; the GC unticks any they'd answer differently. Each counts as the GC's own answer, as on the sub's page, so a
 * red-flagged record is still only counted or dropped when the GC says so. Questions without a clear suggestion are
 * left for the sub's page.
 */
export function SuggestedAnswers({
  projectId,
  questions,
  onAnswered,
}: {
  projectId: string;
  questions: ProjectQuestion[];
  /** refetch the scorecard: answers move records, so verdicts and counts change */
  onAnswered: () => Promise<void> | void;
}) {
  const id = useId();
  const [unticked, setUnticked] = useState<Set<string>>(() => new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const withSuggestion = questions.filter(hasSuggestion);
  const picked = withSuggestion.filter((q) => !unticked.has(q.question_id));
  const rest = questions.length - withSuggestion.length;
  const several = withSuggestion.length > 1;

  const status = done ? (
    <p role="status" className="text-sm text-ink-2">
      {done}
    </p>
  ) : null;
  if (!withSuggestion.length) return status;

  function toggle(questionId: string, on: boolean) {
    setUnticked((prev) => {
      const next = new Set(prev);
      if (on) next.delete(questionId);
      else next.add(questionId);
      return next;
    });
  }

  async function answerAll() {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const { answered } = await api.answerQuestions(
        projectId,
        picked.map((q) => ({ question_id: q.question_id, answer: q.ai_suggestion === "same" ? "yes" : "no" })),
      );
      setDone(
        `Answered ${plural(answered, "question")}.` +
          (answered < picked.length ? " The rest had already been answered, or were settled by these answers." : ""),
      );
      await onAnswered();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby={`${id}-title`} className="card p-4">
      <h2 id={`${id}-title`} className="section-title flex items-center gap-2">
        <IconQuestion size={18} className="shrink-0 text-accent" aria-hidden="true" />
        {plural(withSuggestion.length, "match question")} with a suggestion
      </h2>
      <p className="mt-1 text-sm text-muted">
        {several
          ? "Answer them here in one go, or one at a time on each sub's page. Untick any you'd answer differently."
          : "Answer it here, or on the sub's page."}
      </p>
      <ul className="mt-3 divide-y divide-line border-t border-line">
        {withSuggestion.map((q) => {
          const records = q.establishment_keys.length;
          return (
            <li key={q.question_id} className="flex items-start gap-3 py-3">
              <input
                id={`${id}-${q.question_id}`}
                type="checkbox"
                className="mt-1 size-4 shrink-0 accent-[var(--accent)] disabled:cursor-not-allowed"
                checked={!unticked.has(q.question_id)}
                onChange={(e) => toggle(q.question_id, e.target.checked)}
                disabled={busy}
              />
              <div className="min-w-0 flex-1">
                <label htmlFor={`${id}-${q.question_id}`} className="text-sm font-semibold text-ink">
                  {q.sub_name}: {suggestionLabel(q)}
                </label>
                <p className="mt-0.5 text-xs text-muted">
                  {plural(records, "record")}
                  {q.has_red_flags ? (
                    <span className="ml-1.5 inline-flex items-center gap-1 font-medium text-high-fg">
                      <IconFlag size={12} aria-hidden="true" /> {records === 1 ? "carries red flags" : "some carry red flags"}
                    </span>
                  ) : null}
                </p>
                <details className="mt-1 text-sm text-ink-2">
                  <summary className="text-xs font-medium text-accent hover:underline">Read the question</summary>
                  <p className="mt-1">{q.text}</p>
                  <Link
                    to={`/projects/${encodeURIComponent(projectId)}/subs/${encodeURIComponent(q.sub_id)}#questions`}
                    className="link mt-1 inline-block text-xs"
                  >
                    Answer it record by record on {q.sub_name}'s page
                  </Link>
                </details>
              </div>
              <span className="pill shrink-0 border-line-strong bg-surface text-ink-2">
                {q.ai_suggestion === "same" ? "Mine" : "Not mine"}
              </span>
            </li>
          );
        })}
      </ul>
      {rest ? (
        <p className="border-t border-line pt-3 text-xs text-muted">
          {plural(rest, "more question")} without a clear suggestion: answer {rest === 1 ? "it" : "them"} on the sub's
          page.
        </p>
      ) : null}
      <InlineError message={error} />
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => void answerAll()}
          disabled={busy || !picked.length}
        >
          {busy
            ? "Answering…"
            : picked.length
              ? `Answer ${plural(picked.length, "question")} with the suggestions`
              : "Answer with the suggestions"}
        </button>
        <p className="text-xs text-muted">
          {several
            ? "Each counts as your answer. To change one later, move the record on the sub's page."
            : "It counts as your answer. To change it later, move the record on the sub's page."}
        </p>
      </div>
      {status ? <div className="mt-2">{status}</div> : null}
    </section>
  );
}
