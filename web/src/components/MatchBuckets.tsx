import { useState } from "react";
import type { Bucket, MatchedEstablishment, Method } from "../api/types";
import { formatMonth, plural, yearOf, yearRange } from "../lib/format";
import { IconChevronDown, IconFlag } from "./Icons";

const METHOD_LABEL: Record<Method, string> = {
  rule: "Rule",
  llm: "AI",
  gc: "GC",
  llm_rejected: "AI (rejected)",
};

const METHOD_HINT: Record<Method, string> = {
  rule: "Decided by a deterministic matching rule",
  llm: "Decided by the AI adjudicator from identity evidence only (it never sees safety history)",
  gc: "Decided by the GC",
  llm_rejected: "The AI's answer failed validation, so the rules' default applies",
};

const BUCKET_LABEL: Record<Bucket, string> = {
  matched: "Matched",
  possible: "Possible",
  excluded: "Excluded",
};

export function EstablishmentItem({
  est,
  onMove,
  busy,
}: {
  est: MatchedEstablishment;
  onMove?: (bucket: Bucket) => void;
  busy?: boolean;
}) {
  const address = [est.address, est.city, [est.state, est.zip].filter(Boolean).join(" ")].filter(Boolean).join(", ");
  const years = yearRange(yearOf(est.first_seen), yearOf(est.last_seen));
  const otherVariants = est.name_variants.filter((v) => v !== est.display_name);
  return (
    <li className="py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p id={`est-${est.establishment_key}`} className="font-medium break-words text-ink">
            {est.display_name}
            {est.has_red_flags ? (
              <span className="ml-2 inline-flex items-center gap-1 align-middle text-xs font-medium text-high-fg">
                <IconFlag size={13} /> red flags
              </span>
            ) : null}
          </p>
          {address ? <p className="text-sm text-ink-2">{address}</p> : null}
          <p className="text-sm text-muted">
            {[est.trade_label, plural(est.inspections, "inspection"), years ? `seen ${years}` : null].filter(Boolean).join(" · ")}
          </p>
          {otherVariants.length ? (
            <p className="mt-1 text-xs text-muted">
              Also filed as: {otherVariants.map((v) => `“${v}”`).join(", ")}
            </p>
          ) : null}
        </div>
      </div>
      <p className="mt-2 text-sm text-ink-2">
        <span
          className="mr-1.5 inline-flex items-center rounded border border-line-strong px-1.5 text-xs font-medium text-ink-2"
          title={METHOD_HINT[est.method]}
        >
          {METHOD_LABEL[est.method]}
          {est.confidence != null ? ` · ${Math.round(est.confidence * 100)}%` : ""}
        </span>
        <span className="sr-only">{METHOD_HINT[est.method]}. </span>
        {est.rationale ?? "No rationale recorded."}
        {est.rule_id ? <span className="ml-1 font-mono text-xs text-muted">{est.rule_id}</span> : null}
      </p>
      {onMove ? (
        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-xs text-muted" id={`move-${est.establishment_key}`}>
            {busy ? "Saving…" : "Bucket"}
          </span>
          <div
            className="inline-flex rounded-lg border border-line-strong bg-surface p-0.5"
            role="group"
            aria-labelledby={`move-${est.establishment_key}`}
            aria-describedby={`est-${est.establishment_key}`}
          >
            {(["matched", "possible", "excluded"] as Bucket[]).map((b) => {
              const current = b === est.bucket;
              return (
                <button
                  key={b}
                  type="button"
                  className={`min-h-9 rounded-md px-3 text-sm font-medium ${
                    current ? "bg-accent text-accent-ink" : "text-ink-2 hover:bg-surface-2"
                  } disabled:cursor-not-allowed`}
                  aria-pressed={current}
                  disabled={busy}
                  onClick={() => {
                    if (!current) onMove(b);
                  }}
                >
                  {BUCKET_LABEL[b]}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
    </li>
  );
}

function BucketGroup({
  title,
  hint,
  items,
  onMove,
  busyKey,
  collapsed = false,
}: {
  title: string;
  hint: string;
  items: MatchedEstablishment[];
  onMove: (key: string, bucket: Bucket) => void;
  busyKey: string | null;
  collapsed?: boolean;
}) {
  const [open, setOpen] = useState(!collapsed);
  const inspections = items.reduce((a, e) => a + e.inspections, 0);
  return (
    <div className="border-t border-line pt-3 first:border-t-0 first:pt-0">
      <button
        type="button"
        className="flex min-h-11 w-full items-center gap-2 text-left"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <IconChevronDown size={18} className={`shrink-0 text-muted transition-transform ${open ? "rotate-180" : ""}`} />
        <span className="flex-1">
          <span className="font-semibold text-ink">
            {title} <span className="font-normal text-muted">({items.length})</span>
          </span>
          <span className="block text-sm text-muted">
            {hint}
            {items.length ? ` · ${plural(inspections, "inspection")}` : ""}
          </span>
        </span>
      </button>
      {open ? (
        items.length ? (
          <ul className="divide-y divide-line pl-7">
            {items.map((e) => (
              <EstablishmentItem
                key={e.establishment_key}
                est={e}
                busy={busyKey === e.establishment_key}
                onMove={(b) => onMove(e.establishment_key, b)}
              />
            ))}
          </ul>
        ) : (
          <p className="pb-2 pl-7 text-sm text-muted">None.</p>
        )
      ) : null}
    </div>
  );
}

export function MatchBuckets({
  matched,
  possible,
  excluded,
  onMove,
  busyKey,
  asOf,
}: {
  matched: MatchedEstablishment[];
  possible: MatchedEstablishment[];
  excluded: MatchedEstablishment[];
  onMove: (key: string, bucket: Bucket) => void;
  busyKey: string | null;
  asOf: string;
}) {
  return (
    <div className="space-y-3">
      <BucketGroup
        title="Matched"
        hint="Counted in the scorecard"
        items={matched}
        onMove={onMove}
        busyKey={busyKey}
      />
      <BucketGroup
        title="Possible — not counted"
        hint="Might be this company; shown, never counted"
        items={possible}
        onMove={onMove}
        busyKey={busyKey}
      />
      <BucketGroup
        title="Excluded lookalikes"
        hint="Different companies with similar names"
        items={excluded}
        onMove={onMove}
        busyKey={busyKey}
        collapsed
      />
      <p className="text-xs text-muted">
        An establishment is one exact name + mailing address + zip in OSHA's records (as of {formatMonth(asOf)}). Moving one
        re-scores this sub.
      </p>
    </div>
  );
}
