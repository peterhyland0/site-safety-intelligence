import type { SubInput } from "../api/types";
import { MAX_ROWS, normaliseState, parseSubs } from "./parseSubs";

/** One editable row of the Add subs form. All fields are plain strings; "" means not given. */
export interface SubRow {
  id: number;
  name: string;
  city: string;
  /** 2-letter code, or "" to use the project's default state */
  state: string;
  trade: string;
  licence: string;
  /** state text from a pasted list that isn't a recognised state; cleared when a state is picked */
  badState?: string | null;
}

export interface RowCheck {
  empty: boolean;
  errors: string[];
  warnings: string[];
}

let nextId = 1;
export function emptyRow(): SubRow {
  return { id: nextId++, name: "", city: "", state: "", trade: "", licence: "" };
}

const blank = (r: SubRow) => !r.name.trim() && !r.city.trim() && !r.state && !r.trade.trim() && !r.licence.trim();

/** Trade words the matcher understands (ssi/matching/trades.py), offered as suggestions. */
export const TRADE_SUGGESTIONS = [
  "roofing",
  "framing",
  "concrete",
  "masonry",
  "structural steel",
  "glazing",
  "siding",
  "electrical",
  "plumbing",
  "HVAC / mechanical",
  "fire protection",
  "elevator",
  "drywall",
  "insulation",
  "painting",
  "flooring",
  "carpentry",
  "excavation",
  "demolition",
  "paving",
  "landscaping",
  "general contractor",
];

/**
 * "COLMEX CONTRACTING LLC. BUNNELL FL": a name that seems to end with a city and state.
 * Returns the place it found ("BUNNELL FL") or null. "CO" is left alone: it's usually "Company".
 */
export function placeInName(name: string): string | null {
  const tokens = name.trim().split(/[\s,]+/).filter(Boolean);
  if (tokens.length < 3) return null;
  const last = tokens[tokens.length - 1].replace(/\.$/, "");
  if (!/^[A-Za-z]{2}$/.test(last) || last.toUpperCase() === "CO" || !normaliseState(last)) return null;
  return `${tokens[tokens.length - 2]} ${last.toUpperCase()}`;
}

/** Turn a pasted list into rows, using the same parser as before; nothing is sent until the GC reviews them. */
export function rowsFromPaste(text: string): SubRow[] {
  return parseSubs(text, null).rows.map((r) => ({
    ...emptyRow(),
    name: r.input.name,
    city: r.input.city ?? "",
    state: r.input.state ?? "",
    trade: r.input.trade ?? "",
    licence: r.input.licence ?? "",
    badState: r.badState,
  }));
}

/** Check every row; blank rows are ignored. Returns per-row results and the inputs ready to send. */
export function checkRows(rows: SubRow[], defaultState: string | null): { checks: RowCheck[]; valid: SubInput[] } {
  const seen = new Map<string, number>();
  let count = 0;
  const checks = rows.map((r, i): RowCheck => {
    if (blank(r)) return { empty: true, errors: [], warnings: [] };
    const errors: string[] = [];
    const warnings: string[] = [];
    const name = r.name.trim();
    const state = r.state || defaultState || "";
    if (!name) errors.push("Add the company name.");
    if (r.badState && !r.state) errors.push(`"${r.badState}" from your list isn't a state: pick one.`);
    const key = `${name.toUpperCase()}|${state}`;
    if (name && seen.has(key)) errors.push(`Same name and state as sub ${seen.get(key)! + 1}.`);
    if (name) seen.set(key, seen.get(key) ?? i);
    if (++count > MAX_ROWS) errors.push(`Over the ${MAX_ROWS}-sub limit for one batch.`);
    const place = name && !r.city.trim() ? placeInName(name) : null;
    if (place) warnings.push(`The name seems to end with a place ("${place}"). Put the city and state in their own fields.`);
    else if (!r.city.trim()) warnings.push("No city: common names may not match.");
    if (!state) warnings.push("No state: matching works best with a city and state.");
    return { empty: false, errors, warnings };
  });
  const valid = rows
    .filter((_, i) => !checks[i].empty && checks[i].errors.length === 0)
    .map((r) => ({
      name: r.name.trim(),
      city: r.city.trim() || null,
      state: r.state || defaultState || null,
      trade: r.trade.trim() || null,
      licence: r.licence.trim() || null,
    }));
  return { checks, valid };
}
