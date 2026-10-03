/**
 * Yearly trend as three small-multiple column charts sharing one year axis:
 * inspections, citations, serious+ citations. One series per facet (slot-1 blue, no legend box;
 * each facet is titled). Citations and serious+ share a y-scale so the serious share reads honestly.
 *
 * Accessible: keyboard focus + arrow keys move the highlighted year (announced via a live
 * region), hover shows the same readout, and a table view carries every value.
 */
import { useId, useLayoutEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import type { YearRow } from "../api/types";
import { formatInt, formatMoney } from "../lib/format";

const MAX_YEARS = 20;
const ML = 30; // left margin for y labels
const MR = 6;
const FACET_H = 52; // plot height per facet
const FACET_TITLE = 20; // title band above each plot
const FACET_GAP = 14;
const AXIS_H = 22;

function niceMax(v: number): number {
  if (v <= 1) return 1;
  const pow = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * pow >= v) return m * pow;
  return 10 * pow;
}

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(640);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(el.clientWidth || 640);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) setWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

/** Column with a 4px rounded data-end and a square baseline. */
function barPath(x: number, y: number, w: number, h: number): string {
  const r = Math.min(4, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

type Facet = { key: "inspections" | "citations" | "serious_plus"; title: string; max: number };

export function TrendChart({ rows, windowYears, asOfYear }: { rows: YearRow[]; windowYears: number; asOfYear: number }) {
  const [wrapRef, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const ids = { desc: useId(), live: useId() };

  const data = rows.slice(-MAX_YEARS);
  const truncated = rows.length > data.length;
  const n = data.length;
  if (!n) return <p className="text-sm text-muted">No inspections to chart.</p>;

  const citMax = niceMax(Math.max(...data.map((r) => r.citations)));
  const facets: Facet[] = [
    { key: "inspections", title: "Inspections", max: niceMax(Math.max(...data.map((r) => r.inspections))) },
    { key: "citations", title: "Citations", max: citMax },
    { key: "serious_plus", title: "Serious, willful or repeat citations", max: citMax },
  ];

  const plotW = Math.max(120, width - ML - MR);
  const band = plotW / n;
  const barW = Math.max(3, Math.min(24, band - 4));
  const xOf = (i: number) => ML + i * band;
  const facetTop = (fi: number) => fi * (FACET_TITLE + FACET_H + FACET_GAP);
  const height = facetTop(facets.length) - FACET_GAP + AXIS_H;
  const windowStart = asOfYear - windowYears + 1;
  const winIdx = data.findIndex((r) => r.year >= windowStart);
  const shortYears = band < 36;
  const labelEvery = band < 20 ? 2 : 1;

  const activeRow = active != null ? data[active] : null;

  function indexFromPointer(e: PointerEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left - ML;
    return Math.max(0, Math.min(n - 1, Math.floor(x / band)));
  }

  function onKey(e: KeyboardEvent<SVGSVGElement>) {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft" || e.key === "Home" || e.key === "End") {
      e.preventDefault();
      setActive((cur) => {
        if (e.key === "Home") return 0;
        if (e.key === "End") return n - 1;
        const c = cur ?? n - 1;
        return e.key === "ArrowRight" ? Math.min(n - 1, c + 1) : Math.max(0, c - 1);
      });
    } else if (e.key === "Escape") {
      setActive(null);
    }
  }

  const tipLeft = active != null ? Math.min(Math.max(xOf(active) + band / 2, 90), width - 90) : 0;
  const totalInsp = data.reduce((a, r) => a + r.inspections, 0);
  const totalSp = data.reduce((a, r) => a + r.serious_plus, 0);

  return (
    <div>
      <div ref={wrapRef} className="relative w-full">
        <svg
          width={width}
          height={height}
          className="block touch-pan-y select-none"
          tabIndex={0}
          role="group"
          aria-roledescription="chart"
          aria-label={`Inspections and citations per year, ${data[0].year} to ${data[n - 1].year}. Use left and right arrow keys to read each year.`}
          aria-describedby={ids.desc}
          onPointerMove={(e) => setActive(indexFromPointer(e))}
          onPointerDown={(e) => setActive(indexFromPointer(e))}
          onPointerLeave={(e) => {
            if (e.pointerType === "mouse") setActive(null);
          }}
          onFocus={() => setActive((a) => a ?? n - 1)}
          onBlur={() => setActive(null)}
          onKeyDown={onKey}
        >
          {/* Lookback window band */}
          {winIdx >= 0 ? (
            <rect x={xOf(winIdx)} y={0} width={ML + plotW - xOf(winIdx)} height={height - AXIS_H} fill="var(--chart-band)" />
          ) : null}
          {/* Active-year highlight */}
          {active != null ? (
            <rect x={xOf(active)} y={0} width={band} height={height - AXIS_H} fill="var(--line)" opacity={0.6} />
          ) : null}

          {facets.map((f, fi) => {
            const top = facetTop(fi) + FACET_TITLE;
            const yOf = (v: number) => top + FACET_H - (v / f.max) * FACET_H;
            const values = data.map((r) => r[f.key]);
            const peak = Math.max(...values);
            const peakIdx = peak > 0 ? values.lastIndexOf(peak) : -1;
            return (
              <g key={f.key}>
                <text x={0} y={facetTop(fi) + 13} className="fill-ink-2" fontSize={12} fontWeight={600}>
                  {f.title}
                </text>
                {/* top gridline + tick */}
                <line x1={ML} x2={ML + plotW} y1={top} y2={top} stroke="var(--chart-grid)" strokeWidth={1} />
                <text x={ML - 6} y={top + 4} textAnchor="end" fontSize={11} className="fill-muted tabular-nums">
                  {formatInt(f.max)}
                </text>
                {/* baseline */}
                <line x1={ML} x2={ML + plotW} y1={top + FACET_H} y2={top + FACET_H} stroke="var(--chart-axis)" strokeWidth={1} />
                <text x={ML - 6} y={top + FACET_H + 4} textAnchor="end" fontSize={11} className="fill-muted tabular-nums">
                  0
                </text>
                {values.map((v, i) => {
                  if (v <= 0) return null;
                  const y = yOf(v);
                  const h = top + FACET_H - y;
                  const x = xOf(i) + (band - barW) / 2;
                  return <path key={i} d={barPath(x, y, barW, Math.max(h, 1.5))} fill="var(--chart-1)" opacity={active == null || active === i ? 1 : 0.55} />;
                })}
                {/* Direct label on the facet's peak only */}
                {peakIdx >= 0 && peak < f.max * 0.8 ? (
                  <text
                    x={xOf(peakIdx) + band / 2}
                    y={yOf(peak) - 4}
                    textAnchor="middle"
                    fontSize={11}
                    className="fill-ink-2 tabular-nums"
                  >
                    {peak}
                  </text>
                ) : null}
              </g>
            );
          })}

          {/* Year axis */}
          {data.map((r, i) =>
            i % labelEvery === (n - 1) % labelEvery ? (
              <text
                key={r.year}
                x={xOf(i) + band / 2}
                y={height - 6}
                textAnchor="middle"
                fontSize={11}
                className={`tabular-nums ${active === i ? "fill-ink" : "fill-muted"}`}
                fontWeight={active === i ? 600 : 400}
              >
                {shortYears ? `’${String(r.year).slice(2)}` : r.year}
              </text>
            ) : null,
          )}
        </svg>

        {activeRow ? (
          <div
            className="pointer-events-none absolute top-0 z-10 w-44 -translate-x-1/2 rounded-lg border border-line bg-surface p-2.5 text-xs shadow-lg"
            style={{ left: tipLeft }}
            aria-hidden="true"
          >
            <p className="mb-1 font-semibold text-ink">{activeRow.year}</p>
            <TipRow label="Inspections" value={activeRow.inspections} />
            <TipRow label="with citations" value={activeRow.inspections_with_citations} />
            <TipRow label="Citations" value={activeRow.citations} />
            <TipRow label="Serious+" value={activeRow.serious_plus} />
            {activeRow.willful ? <TipRow label="Willful" value={activeRow.willful} /> : null}
            {activeRow.repeat ? <TipRow label="Repeat" value={activeRow.repeat} /> : null}
            <p className="mt-1 flex justify-between gap-2 text-muted">
              <span>Penalties (current)</span>
              <span className="font-semibold text-ink tabular-nums">
                {activeRow.citations ? formatMoney(activeRow.penalty_current) : "—"}
              </span>
            </p>
          </div>
        ) : null}
      </div>

      <p id={ids.live} className="sr-only" aria-live="polite">
        {activeRow
          ? `${activeRow.year}: ${activeRow.inspections} inspections, ${activeRow.citations} citations, ${activeRow.serious_plus} serious or worse.`
          : ""}
      </p>
      <p id={ids.desc} className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="inline-block h-3 w-4 rounded-sm border border-line bg-chart-band" />
          Shaded: lookback window (last {windowYears} years)
        </span>
        <span>
          {totalInsp} inspections and {totalSp} serious+ citations shown{truncated ? `, most recent ${MAX_YEARS} years` : ""}.
        </span>
      </p>

      <details className="mt-2 text-sm">
        <summary className="inline-flex min-h-9 items-center text-accent hover:underline">Show as table</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[28rem] text-right text-sm tabular-nums">
            <caption className="sr-only">Inspections and citations per year</caption>
            <thead className="text-xs text-muted">
              <tr className="border-b border-line">
                <th scope="col" className="py-1.5 pr-2 text-left font-medium">
                  Year
                </th>
                <th scope="col" className="px-2 py-1.5 font-medium">
                  Inspections
                </th>
                <th scope="col" className="px-2 py-1.5 font-medium">
                  With citations
                </th>
                <th scope="col" className="px-2 py-1.5 font-medium">
                  Citations
                </th>
                <th scope="col" className="px-2 py-1.5 font-medium">
                  Serious+
                </th>
                <th scope="col" className="px-2 py-1.5 font-medium">
                  Willful
                </th>
                <th scope="col" className="px-2 py-1.5 font-medium">
                  Repeat
                </th>
                <th scope="col" className="py-1.5 pl-2 font-medium">
                  Penalties (current)
                </th>
              </tr>
            </thead>
            <tbody>
              {[...rows].reverse().map((r) => (
                <tr key={r.year} className="border-b border-line">
                  <th scope="row" className="py-1.5 pr-2 text-left font-medium text-ink">
                    {r.year}
                  </th>
                  <td className="px-2 py-1.5">{r.inspections}</td>
                  <td className="px-2 py-1.5">{r.inspections_with_citations}</td>
                  <td className="px-2 py-1.5">{r.citations}</td>
                  <td className="px-2 py-1.5">{r.serious_plus}</td>
                  <td className="px-2 py-1.5">{r.willful}</td>
                  <td className="px-2 py-1.5">{r.repeat}</td>
                  <td className="py-1.5 pl-2">{r.citations ? formatMoney(r.penalty_current) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

function TipRow({ label, value }: { label: string; value: number }) {
  return (
    <p className="flex justify-between gap-2 text-muted">
      <span>{label}</span>
      <span className="font-semibold text-ink tabular-nums">{value}</span>
    </p>
  );
}
