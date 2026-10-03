import { useState } from "react";
import { api, errorMessage } from "../api/client";
import type { FatalityStatus, InspectionDetail, InspectionRow } from "../api/types";
import { formatDate, formatMoney, plural } from "../lib/format";
import { IconChevronDown, IconSpinner } from "./Icons";
import { InlineError, OshaLink } from "./ui";

const FATALITY_LABEL: Record<FatalityStatus, string | null> = {
  fatality_cited: "Fatality investigation, citations issued",
  fatality_inspected_not_cited: "Fatality investigation, no citations",
  fatality_pending: "Fatality/catastrophe investigation open, outcome not yet published",
  fatcat_cited: "Fatality/catastrophe investigation, citations issued",
  fatcat_not_cited: "Fatality/catastrophe investigation, no serious citations",
  fatcat_site_cited: "Cited on a site where a fatality/catastrophe is under investigation",
  catastrophe_cited: "Catastrophe investigation (serious injuries), citations issued",
  accident_outcome_unknown: "Accident inspection, outcome not in OSHA's accident data",
  none: null,
};

export function InspectionBadges({ row }: { row: InspectionRow }) {
  const fat = FATALITY_LABEL[row.fatality_status];
  return (
    <span className="flex flex-wrap gap-1.5">
      {row.is_open ? (
        <span className="pill border-review-line bg-review-bg text-review-fg" title="Case still open: citations and penalties may change">
          Open case · provisional
        </span>
      ) : null}
      {fat ? (
        <span
          className={`pill ${
            row.fatality_status === "fatality_cited" || row.fatality_status === "fatcat_cited"
              ? "border-high-line bg-high-bg text-high-fg"
              : row.fatality_status === "fatality_pending"
                ? "border-review-line bg-review-bg text-review-fg"
                : "border-line-strong bg-surface-2 text-ink-2"
          }`}
        >
          {fat}
        </span>
      ) : null}
      {row.jurisdiction === "state_plan" ? (
        <span className="pill border-line-strong bg-surface text-ink-2" title="Inspected by a state-plan OSHA program">
          State plan{row.site_state ? ` (${row.site_state})` : ""}
        </span>
      ) : null}
      {row.shared_site_n > 0 ? (
        <span className="pill border-line-strong bg-surface text-ink-2" title="Other employers were inspected on the same site and date">
          Shared site: +{plural(row.shared_site_n, "employer")}
        </span>
      ) : null}
    </span>
  );
}

function InspectionItem({ row }: { row: InspectionRow }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<InspectionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const panelId = `insp-${row.activity_nr}`;

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !detail && !loading) {
      setLoading(true);
      setError(null);
      try {
        setDetail(await api.getInspection(row.activity_nr));
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
  }

  const place = [row.site_city, row.site_state].filter(Boolean).join(", ");
  return (
    <li className="py-3">
      <div className="flex items-start gap-2">
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          aria-controls={panelId}
          className="-m-1 flex min-h-11 flex-1 items-start gap-2 rounded-lg p-1 text-left hover:bg-surface-2"
        >
          <IconChevronDown size={18} className={`mt-0.5 shrink-0 text-muted transition-transform ${open ? "rotate-180" : ""}`} />
          <span className="min-w-0 flex-1">
            <span className="block font-medium text-ink">
              {formatDate(row.open_date)} · {row.insp_type_label}
              {place ? <span className="font-normal text-ink-2"> · {place}</span> : null}
            </span>
            <span className="block text-sm text-ink-2">
              {row.citations ? (
                <>
                  {plural(row.citations, "citation")} ({row.serious_plus} serious+) · penalties {formatMoney(row.penalty_current)}
                  {row.penalty_initial != null && row.penalty_current != null && row.penalty_initial !== row.penalty_current ? (
                    <span className="text-muted"> (initially {formatMoney(row.penalty_initial)})</span>
                  ) : null}
                </>
              ) : (
                "No citations"
              )}
            </span>
            <span className="block text-xs text-muted">{row.establishment_name}</span>
          </span>
        </button>
        <span className="mt-1 text-sm">
          <OshaLink url={row.url} activityNr={row.activity_nr} compact />
        </span>
      </div>
      <div className="mt-1.5 pl-6">
        <InspectionBadges row={row} />
        {row.dq_flags.map((f) => (
          <p key={f} className="mt-1 text-xs text-muted">
            Data note: {f}
          </p>
        ))}
      </div>

      {open ? (
        <div id={panelId} className="mt-3 rounded-lg bg-surface-2 p-3 sm:ml-7">
          {loading ? (
            <p role="status" className="flex items-center gap-2 text-sm text-muted">
              <IconSpinner size={16} /> Loading citations…
            </p>
          ) : error ? (
            <InlineError message={error} />
          ) : detail ? (
            <InspectionDetailView detail={detail} />
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

export function InspectionDetailView({ detail }: { detail: InspectionDetail }) {
  return (
    <div className="space-y-3 text-sm">
      {detail.is_open ? (
        <p className="text-review-fg">This case is still open. Citations and penalties may change after settlement or contest.</p>
      ) : null}
      {detail.citation_rows.length ? (
        <ul className="divide-y divide-line" aria-label="Citations">
          {detail.citation_rows.map((c) => (
            <li key={c.citation_id} className={`py-2 ${c.is_deleted ? "text-muted" : ""}`}>
              <p className="font-medium text-ink">
                <span className={c.is_deleted ? "line-through" : ""}>
                  {c.viol_type_label} · {c.hazard_label}
                </span>
                {c.is_deleted ? <span className="ml-1 text-xs font-normal">(deleted, not counted)</span> : null}
              </p>
              <p className="text-ink-2">
                {c.standard ? <span className="font-mono text-[13px]">{c.standard}</span> : "Standard not recorded"}
                <span className="text-muted"> · citation {c.citation_id}</span>
                {c.issued ? <span className="text-muted"> · issued {formatDate(c.issued)}</span> : null}
              </p>
              <p className="text-ink-2">
                Penalty {formatMoney(c.penalty_current)}
                {c.penalty_initial != null && c.penalty_initial !== c.penalty_current ? (
                  <span className="text-muted"> (initially {formatMoney(c.penalty_initial)})</span>
                ) : null}
                {c.is_fta ? <span className="ml-2 pill border-high-line bg-high-bg text-high-fg">Failure to abate</span> : null}
                {c.contested ? <span className="ml-2 pill border-line-strong bg-surface text-ink-2">Contested</span> : null}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-ink-2">No citations were issued on this inspection.</p>
      )}

      {detail.accidents.map((a) => (
        <div key={a.summary_nr} className="rounded-lg border border-line bg-surface p-3">
          <p className="font-medium text-ink">
            Accident {a.event_date ? `on ${formatDate(a.event_date)}` : "(date not recorded)"}
            {a.description ? `: ${a.description}` : ""}
          </p>
          <p className="text-xs text-muted">
            {plural(a.fatal_n, "fatality", "fatalities")} · {plural(a.injured_n, "other injury", "other injuries")}
            {a.employers_on_site > 1
              ? ` · ${a.employers_on_site} employers were on site, so OSHA's record can't say whose worker was hurt`
              : ""}
          </p>
          {a.narrative ? <p className="mt-2 leading-relaxed text-ink-2">{a.narrative}</p> : null}
          <p className="mt-1 text-xs text-muted">OSHA accident summary {a.summary_nr}</p>
        </div>
      ))}
      {!detail.accidents.length && detail.fatality_status !== "none" ? (
        <p className="text-muted">No accident narrative in OSHA's accident tables for this inspection (they lag and thin out after 2023).</p>
      ) : null}

      <p>
        <OshaLink url={detail.url} activityNr={detail.activity_nr} />{" "}
        <span className="text-muted">
          for the official record. OSHA's site uses its own inspection numbers, so this opens its search for this
          employer on {formatDate(detail.open_date)}; it may ask you to confirm you're human first.
        </span>
      </p>
    </div>
  );
}

const PAGE = 25; // matches the API default page size

export function InspectionList({
  projectId,
  subId,
  initial,
  total,
}: {
  projectId: string;
  subId: string;
  initial: InspectionRow[];
  total: number;
}) {
  const [rows, setRows] = useState(initial);
  const [done, setDone] = useState(initial.length >= total);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function more() {
    setLoading(true);
    setError(null);
    try {
      const next = await api.getInspections(projectId, subId, rows.length, PAGE);
      const seen = new Set(rows.map((r) => r.activity_nr));
      const merged = [...rows, ...next.filter((r) => !seen.has(r.activity_nr))];
      setRows(merged);
      if (next.length < PAGE || merged.length >= total) setDone(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  if (!rows.length) return <p className="text-sm text-muted">No matched inspections.</p>;

  return (
    <div>
      <ul className="divide-y divide-line">
        {rows.map((r) => (
          <InspectionItem key={r.activity_nr} row={r} />
        ))}
      </ul>
      <InlineError message={error} />
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <p className="text-sm text-muted">
          Showing {rows.length} of {Math.max(total, rows.length)}
        </p>
        {!done ? (
          <button type="button" className="btn btn-secondary btn-sm" onClick={more} disabled={loading}>
            {loading ? "Loading…" : "Show more"}
          </button>
        ) : null}
      </div>
    </div>
  );
}
