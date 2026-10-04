import { useState } from "react";
import type { Bucket, MatchedEstablishment, Method } from "../api/types";
import { formatMonth, plural, yearOf, yearRange } from "../lib/format";
import { IconChevronDown, IconFlag } from "./Icons";

const METHOD_LABEL: Record<Method, string> = {
  rule: "Rule",
  llm: "AI review",
  gc: "Your decision",
  llm_rejected: "Undecided",
  profile: "Company's website",
  remap: "Your answers differ",
  web: "Web check",
};

// The GC's own decision is shown in plain words; the AI's old confidence and rule codes don't apply to it.
const GC_DECISION: Record<Bucket, string> = {
  matched: "You confirmed this record is your sub.",
  possible: "You left this record as possible.",
  excluded: "You marked this record as a different company.",
};

const METHOD_HINT: Record<Method, string> = {
  rule: "Decided by a deterministic matching rule",
  llm: "Decided by the AI adjudicator from identity evidence only (it never sees safety history)",
  gc: "Decided by you (the GC). Your decision always wins, including after data refreshes",
  llm_rejected: "The AI's answer failed its checks, so the record stays possible until someone decides",
  profile: "Held for your answer: the company's own website lists this location (see the question above)",
  remap: "Held for your answer: a data update grouped records you answered differently into this one (see the question above)",
  web: "Held for your answer: a web search found whose record this is (see the question above)",
};

// A hint and label for the record itself where its method alone would mislead: a profile record that's matched
// (M4: the sub's own name at an address its website lists) isn't held, and a decision carried from the GC's answer
// about the same company name (C1) wasn't made on this record.
function methodHint(est: MatchedEstablishment): string {
  if (est.method === "profile" && est.bucket === "matched")
    return "Matched: your sub's own name at an address its website lists, with no red flags (rule M4)";
  if (est.method === "gc" && est.rule_id === "C1")
    return "Carried from your answer about another record under the same company name";
  return METHOD_HINT[est.method];
}

function decisionText(est: MatchedEstablishment): string {
  if (est.method === "gc" && est.rule_id !== "C1") return GC_DECISION[est.bucket];
  return est.rationale ?? "No rationale recorded.";
}

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
          {est.related_only ? (
            <p className="mt-0.5">
              <span
                className="pill border-review-line bg-review-bg text-review-fg"
                title="Found by company name: this facility isn't coded as construction, so it's only counted once confirmed"
              >
                Facility not coded as construction{est.industry_code ? ` (industry ${est.industry_code})` : ""}
              </span>
            </p>
          ) : null}
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
          title={methodHint(est)}
        >
          {METHOD_LABEL[est.method]}
          {est.method === "llm" && est.confidence != null ? ` · ${Math.round(est.confidence * 100)}%` : ""}
        </span>
        <span className="sr-only">{methodHint(est)}. </span>
        {decisionText(est)}
        {(est.method === "rule" || (est.method === "profile" && est.bucket === "matched")) && est.rule_id ? (
          <span className="ml-1 font-mono text-xs text-muted" title="Matching rule (see Method)">
            {est.rule_id}
          </span>
        ) : null}
      </p>
      {onMove ? (
        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-xs text-muted" id={`move-${est.establishment_key}`}>
            {busy ? "Saving…" : "Bucket"}
          </span>
          <div
            className="tabbar"
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
                  className={`tab px-2.5 sm:px-3.5 max-[359px]:text-xs ${current ? "tab-active" : ""} disabled:cursor-not-allowed`}
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
