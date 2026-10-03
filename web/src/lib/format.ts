/** Formatting helpers. Dates in the API are ISO strings ("2024-03-12" or full timestamps). */

const dateFmt = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
});

const monthFmt = new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric", timeZone: "UTC" });

function parseIso(value: string): Date | null {
  // Treat bare dates as UTC so they never shift a day in US time zones.
  const d = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00Z`) : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = parseIso(value);
  return d ? dateFmt.format(d) : value;
}

export function formatMonth(value: string | null | undefined): string {
  if (!value) return "—";
  const d = parseIso(value);
  return d ? monthFmt.format(d) : value;
}

export function yearOf(value: string | null | undefined): number | null {
  if (!value) return null;
  const d = parseIso(value);
  return d ? d.getUTCFullYear() : null;
}

const intFmt = new Intl.NumberFormat("en-US");

export function formatInt(n: number | null | undefined): string {
  return n == null ? "—" : intFmt.format(n);
}

const moneyFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

/** Blank penalties are "not recorded", never $0. */
export function formatMoney(n: number | null | undefined): string {
  return n == null ? "not recorded" : moneyFmt.format(n);
}

export function formatRate(n: number | null | undefined, digits = 2): string {
  return n == null ? "—" : n.toFixed(digits);
}

export function plural(n: number, one: string, many?: string): string {
  return `${intFmt.format(n)} ${n === 1 ? one : (many ?? `${one}s`)}`;
}

export function yearRange(first: number | null | undefined, last: number | null | undefined): string | null {
  if (first == null && last == null) return null;
  if (first == null) return String(last);
  if (last == null || first === last) return String(first);
  return `${first}–${last}`;
}

export function formatPercent(n: number | null | undefined, digits = 0): string {
  return n == null ? "—" : `${(n * 100).toFixed(digits)}%`;
}
