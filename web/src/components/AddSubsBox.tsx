import { useEffect, useId, useMemo, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { SubCard } from "../api/types";
import { plural } from "../lib/format";
import { US_STATES } from "../lib/parseSubs";
import { checkRows, emptyRow, rowsFromPaste, TRADE_SUGGESTIONS, type RowCheck, type SubRow } from "../lib/subRows";
import { IconPlus, IconTrash } from "./Icons";
import { InlineError } from "./ui";

const PASTE_PLACEHOLDER = `ABC Roofing, Dallas, TX, roofing
Lone Star Framing, Fort Worth, TX, framing
Cascade Steel Erectors, Tacoma, WA, steel, CASCASE871NM`;

const STATE_CODES = Object.keys(US_STATES);
// name · city · state · trade · licence · remove
const GRID = "sm:grid-cols-[minmax(0,2.4fr)_minmax(0,1.3fr)_5.5rem_minmax(0,1.1fr)_minmax(0,0.9fr)_2.75rem]";

/**
 * Add subs as rows of fields: company name (required), city, state, trade, licence. "Paste a list" fills
 * the rows from a spreadsheet or bid list using the same parser as before, so the GC reviews every row
 * before anything is sent.
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
  const [rows, setRows] = useState<SubRow[]>(() => [emptyRow()]);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ids = { title: useId(), help: useId(), paste: useId(), trades: useId() };

  const { checks, valid } = useMemo(() => checkRows(rows, defaultState), [rows, defaultState]);
  const needFixing = checks.filter((c) => c.errors.length).length;

  useEffect(() => {
    if (focusId != null) document.getElementById(`sub-${focusId}-name`)?.focus();
  }, [focusId]);

  function update(id: number, patch: Partial<SubRow>) {
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  function addRow() {
    const r = emptyRow();
    setRows((rs) => [...rs, r]);
    setFocusId(r.id);
  }

  function removeRow(id: number) {
    setRows((rs) => (rs.length > 1 ? rs.filter((r) => r.id !== id) : [emptyRow()]));
  }

  function fillFromPaste() {
    const pasted = rowsFromPaste(pasteText);
    if (!pasted.length) return;
    setRows((rs) => [...rs.filter((_, i) => !checks[i]?.empty), ...pasted]);
    setNotice(`Filled in ${plural(pasted.length, "row")} from your list. Check them below, then add.`);
    setPasteText("");
    setPasteOpen(false);
  }

  async function submit() {
    if (!valid.length || needFixing) return;
    setBusy(true);
    setError(null);
    try {
      const cards = await api.addSubs(projectId, valid);
      setRows([emptyRow()]);
      setNotice(null);
      onAdded(cards ?? []);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card p-4 sm:p-5" aria-labelledby={ids.title}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={ids.title} className="section-title">
          Add subs
        </h2>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => setPasteOpen((o) => !o)}
          aria-expanded={pasteOpen}
          aria-controls={ids.paste}
        >
          {pasteOpen ? "Close the list box" : "Paste a list"}
        </button>
      </div>
      <p id={ids.help} className="mt-1 text-sm text-ink-2">
        Company name is required. A city and state help find the right company in OSHA's records
        {defaultState ? `; the state defaults to ${defaultState}` : ""}. Trade and licence number are optional.
      </p>

      {pasteOpen ? (
        <div id={ids.paste} className="mt-3 rounded-xl bg-surface-2 p-3">
          <label htmlFor={`${ids.paste}-text`} className="label">
            Paste from a spreadsheet or bid list
          </label>
          <p className="text-xs text-muted">
            One sub per line: name, city, state, trade, licence. Spreadsheet columns work too. Nothing is added until you
            check the rows.
          </p>
          <textarea
            id={`${ids.paste}-text`}
            className="field mt-2 min-h-28 font-mono text-sm leading-6"
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            placeholder={PASTE_PLACEHOLDER}
            rows={4}
            spellCheck={false}
          />
          <button
            type="button"
            className="btn btn-secondary btn-sm mt-2"
            onClick={fillFromPaste}
            disabled={!pasteText.trim()}
          >
            Fill in the rows
          </button>
        </div>
      ) : null}

      {notice ? (
        <p role="status" className="mt-3 text-sm font-medium text-accent">
          {notice}
        </p>
      ) : null}

      <div className={`mt-4 hidden gap-2 px-0.5 text-xs font-semibold text-muted sm:grid ${GRID}`} aria-hidden="true">
        <span>Company name</span>
        <span>City</span>
        <span>State</span>
        <span>Trade</span>
        <span>Licence #</span>
        <span />
      </div>
      <ol className="mt-3 space-y-4 sm:mt-1.5 sm:space-y-2" aria-describedby={ids.help}>
        {rows.map((r, i) => (
          <RowFields
            key={r.id}
            row={r}
            index={i}
            check={checks[i]}
            defaultState={defaultState}
            tradesId={ids.trades}
            onChange={(patch) => update(r.id, patch)}
            onRemove={rows.length > 1 || !checks[i]?.empty ? () => removeRow(r.id) : undefined}
          />
        ))}
      </ol>
      <datalist id={ids.trades}>
        {TRADE_SUGGESTIONS.map((t) => (
          <option key={t} value={t} />
        ))}
      </datalist>
      <button type="button" className="btn btn-ghost btn-sm mt-2 -ml-2" onClick={addRow}>
        <IconPlus size={16} />
        Add another sub
      </button>

      <InlineError message={error} />
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="btn btn-primary"
          onClick={submit}
          disabled={busy || valid.length === 0 || needFixing > 0}
        >
          {busy ? "Adding and matching…" : valid.length ? `Add ${plural(valid.length, "sub")}` : "Add subs"}
        </button>
        {onCancel ? (
          <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
        ) : null}
        {needFixing ? (
          <p className="text-sm text-high-fg" role="status">
            Fix {plural(needFixing, "highlighted row")} first.
          </p>
        ) : null}
      </div>
    </section>
  );
}

function RowFields({
  row: r,
  index,
  check,
  defaultState,
  tradesId,
  onChange,
  onRemove,
}: {
  row: SubRow;
  index: number;
  check: RowCheck;
  defaultState: string | null;
  tradesId: string;
  onChange: (patch: Partial<SubRow>) => void;
  onRemove?: () => void;
}) {
  const n = index + 1;
  const id = (f: string) => `sub-${r.id}-${f}`;
  const bad = check.errors.length > 0;
  const msgId = id("msg");
  const described = check.errors.length || check.warnings.length ? msgId : undefined;
  const label = (text: string) => (
    <>
      <span className="sr-only">Sub {n}: </span>
      {text}
    </>
  );
  return (
    <li className={`rounded-xl ${bad ? "bg-high-bg/50 p-2 ring-1 ring-high-line" : ""}`}>
      {/* phones: a small header per sub, with Remove beside it */}
      <div className="mb-1 flex min-h-9 items-center justify-between sm:hidden">
        <span className="eyebrow">Sub {n}</span>
        {onRemove ? (
          <button type="button" className="btn btn-ghost btn-sm -mr-2" onClick={onRemove} aria-label={`Remove sub ${n}`}>
            Remove
          </button>
        ) : null}
      </div>
      <div className={`grid grid-cols-2 gap-2 ${GRID}`}>
        <div className="col-span-2 sm:col-span-1">
          <label htmlFor={id("name")} className="label sm:sr-only">
            {label("Company name")}
          </label>
          <input
            id={id("name")}
            className="field"
            value={r.name}
            onChange={(e) => onChange({ name: e.target.value })}
            placeholder="e.g. ABC Roofing LLC"
            autoComplete="off"
            autoCapitalize="words"
            aria-invalid={bad && !r.name.trim() ? true : undefined}
            aria-describedby={described}
          />
        </div>
        <div>
          <label htmlFor={id("city")} className="label sm:sr-only">
            {label("City")}
          </label>
          <input
            id={id("city")}
            className="field"
            value={r.city}
            onChange={(e) => onChange({ city: e.target.value })}
            placeholder="City"
            autoComplete="off"
            autoCapitalize="words"
          />
        </div>
        <div>
          <label htmlFor={id("state")} className="label sm:sr-only">
            {label("State")}
          </label>
          <select
            id={id("state")}
            className="field pr-8"
            value={r.state}
            onChange={(e) => onChange({ state: e.target.value, badState: null })}
            aria-invalid={r.badState && !r.state ? true : undefined}
          >
            <option value="">{defaultState ?? "—"}</option>
            {STATE_CODES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={id("trade")} className="label sm:sr-only">
            {label("Trade")}
          </label>
          <input
            id={id("trade")}
            className="field"
            value={r.trade}
            onChange={(e) => onChange({ trade: e.target.value })}
            placeholder="Trade"
            list={tradesId}
            autoComplete="off"
          />
        </div>
        <div>
          <label htmlFor={id("licence")} className="label sm:sr-only">
            {label("Licence # (optional)")}
          </label>
          <input
            id={id("licence")}
            className="field"
            value={r.licence}
            onChange={(e) => onChange({ licence: e.target.value })}
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        <div className="hidden items-center justify-end sm:flex">
          {onRemove ? (
            <button
              type="button"
              className="grid min-h-11 min-w-11 place-items-center rounded-full text-muted hover:bg-surface-2 hover:text-ink"
              onClick={onRemove}
              aria-label={`Remove sub ${n}`}
              title="Remove"
            >
              <IconTrash size={17} />
            </button>
          ) : null}
        </div>
      </div>
      {described ? (
        <div id={msgId} className="mt-1 px-0.5">
          {check.errors.map((e) => (
            <p key={e} className="text-xs font-medium text-high-fg">
              {e}
            </p>
          ))}
          {check.warnings.map((w) => (
            <p key={w} className="text-xs text-muted">
              {w}
            </p>
          ))}
        </div>
      ) : null}
    </li>
  );
}
