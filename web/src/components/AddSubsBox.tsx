import { useId, useMemo, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { SubCard } from "../api/types";
import { parseSubs } from "../lib/parseSubs";
import { plural } from "../lib/format";
import { InlineError } from "./ui";

const PLACEHOLDER = `ABC Roofing, Dallas, TX, roofing
Lone Star Framing, Fort Worth, TX, framing
Cascade Steel Erectors, Tacoma, WA, steel, CASCASE871NM`;

/**
 * Bulk paste box: one sub per line (name, city, state, trade, licence). Parsed client-side and
 * previewed before anything is sent.
 */
export function AddSubsBox({
  projectId,
  defaultState,
  onAdded,
  onCancel,
}: {
  projectId: string;
  defaultState: string | null;
  onAdded: (cards: SubCard[]) => void;
  onCancel?: () => void;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ids = { text: useId(), help: useId(), preview: useId() };

  const parsed = useMemo(() => parseSubs(text, defaultState), [text, defaultState]);
  const hasInput = parsed.rows.length > 0;

  async function submit() {
    if (!parsed.valid.length) return;
    setBusy(true);
    setError(null);
    try {
      const cards = await api.addSubs(projectId, parsed.valid);
      setText("");
      onAdded(cards ?? []);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card p-4 sm:p-5" aria-labelledby={`${ids.text}-title`}>
      <h2 id={`${ids.text}-title`} className="section-title">
        Add subs
      </h2>
      <p id={ids.help} className="mt-1 text-sm text-ink-2">
        One sub per line: <span className="font-medium">name, city, state, trade</span> (trade and licence optional). Paste
        from a spreadsheet or bid list.
        {defaultState ? ` Lines without a state use ${defaultState}.` : ""}
      </p>
      <label htmlFor={ids.text} className="sr-only">
        Subs to add, one per line
      </label>
      <textarea
        id={ids.text}
        className="field mt-3 min-h-32 font-mono text-sm leading-6"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={PLACEHOLDER}
        rows={5}
        spellCheck={false}
        autoCapitalize="words"
        aria-describedby={`${ids.help} ${ids.preview}`}
      />

      <div id={ids.preview} aria-live="polite">
        {hasInput ? (
          <div className="mt-4">
            <p className="text-sm font-medium text-ink">
              Preview: {plural(parsed.valid.length, "sub")} ready
              {parsed.skipped ? <span className="text-high-fg">, {plural(parsed.skipped, "line")} will be skipped</span> : null}
            </p>
            <ol className="mt-2 divide-y divide-line rounded-lg border border-line" aria-label="Parsed subs">
              {parsed.rows.map((r) => {
                const place = [r.input.city, r.input.state].filter(Boolean).join(", ");
                const details = [
                  place ? `${place}${r.stateDefaulted ? " (project default state)" : ""}` : null,
                  r.input.trade,
                  r.input.licence ? `Licence ${r.input.licence}` : null,
                ].filter(Boolean);
                const bad = r.errors.length > 0;
                return (
                  <li key={r.line} className={`px-3 py-2 text-sm ${bad ? "bg-high-bg/60" : ""}`}>
                    <span className="mr-2 text-xs text-muted tabular-nums">{r.line}.</span>
                    <span className={bad ? "font-medium text-ink-2 line-through" : "font-medium text-ink"}>
                      {r.input.name || "(no name)"}
                    </span>
                    {bad ? <span className="sr-only"> (will be skipped)</span> : null}
                    {details.length ? <span className="block text-ink-2 sm:ml-2 sm:inline">{details.join(" · ")}</span> : null}
                    {r.errors.map((e) => (
                      <span key={e} className="block text-xs font-medium text-high-fg">
                        Skipped: {e}
                      </span>
                    ))}
                    {r.warnings.map((w) => (
                      <span key={w} className="block text-xs text-muted">
                        {w}
                      </span>
                    ))}
                  </li>
                );
              })}
            </ol>
          </div>
        ) : null}
      </div>

      <InlineError message={error} />
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" className="btn btn-primary" onClick={submit} disabled={busy || parsed.valid.length === 0}>
          {busy ? "Adding and matching…" : parsed.valid.length ? `Add ${plural(parsed.valid.length, "sub")}` : "Add subs"}
        </button>
        {onCancel ? (
          <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
        ) : null}
      </div>
    </section>
  );
}
