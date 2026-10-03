import { ApiError } from "../api/client";
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
  /** set when the name seems to end with a city and state: the form offers to move them into their fields */
  place?: PlaceSplit | null;
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

export interface PlaceSplit {
  /** the name without the place, as typed ("COLMEX CONTRACTING LLC.") */
  name: string;
  city: string;
  /** 2-letter code */
  state: string;
}

// a legal form ends the company name, so whatever follows it is the city: "... LLC. BUNNELL FL"
const LEGAL_FORM = /^(inc|incorporated|llc|corp|corporation|co|company|ltd|limited|lp|llp|pllc|pc)$/i;
// first words of multi-word cities, so "FORT WORTH TX" moves as one city rather than "WORTH"
const CITY_START = new Set(
  "FORT FT SAINT ST PORT NEW NORTH SOUTH EAST WEST LAKE MOUNT MT SAN SANTA LOS LAS EL PALM BATON CORPUS SALT LITTLE GRAND CEDAR COLLEGE BOWLING OKLAHOMA KANSAS JERSEY SIOUX ROUND WINSTON".split(" "),
);

/**
 * "COLMEX CONTRACTING LLC. BUNNELL FL": a name that seems to end with a city and state. Returns the name and
 * place split apart, or null. "CO" is left alone: it's usually "Company". The GC sees the split before using it.
 */
export function placeInName(name: string): PlaceSplit | null {
  const tokens = [...name.matchAll(/[^\s,]+/g)].map((m) => ({ text: m[0], at: m.index ?? 0 }));
  if (tokens.length < 3) return null;
  const last = tokens[tokens.length - 1].text.replace(/\.$/, "");
  const state = /^[A-Za-z]{2}$/.test(last) && last.toUpperCase() !== "CO" ? normaliseState(last) : null;
  if (!state) return null;
  const bare = (i: number) => tokens[i].text.replace(/\.$/, "");
  let start = tokens.length - 2; // the city's first word
  const legal = tokens.findLastIndex((_, i) => i < tokens.length - 1 && LEGAL_FORM.test(bare(i)));
  if (legal > 0 && tokens.length - 1 - legal - 1 >= 1 && tokens.length - 1 - legal - 1 <= 3) start = legal + 1;
  else if (LEGAL_FORM.test(bare(start))) return null; // "ABC ROOFING LLC TX": a state but no city
  else while (start > 1 && CITY_START.has(bare(start - 1).toUpperCase())) start--;
  const rest = name.slice(0, tokens[start].at).replace(/[\s,]+$/, "");
  const city = name.slice(tokens[start].at, tokens[tokens.length - 1].at).replace(/[\s,]+$/, "");
  return rest && city ? { name: rest, city, state } : null;
}

/** Rows the server turned away as already on the project (a 409 from POST /subs): index into the rows sent. */
export function duplicatesFrom(err: unknown): { row: number; message: string }[] {
  if (!(err instanceof ApiError) || err.status !== 409) return [];
  const detail = (err.detail as { detail?: { duplicates?: unknown } } | undefined)?.detail;
  const dups = detail?.duplicates;
  if (!Array.isArray(dups)) return [];
  return dups.filter(
    (d): d is { row: number; message: string } => typeof d?.row === "number" && typeof d?.message === "string",
  );
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

/**
 * Check every row; blank rows are ignored. Returns per-row results, the inputs ready to send and, for each
 * input, the id of the row it came from (so a server answer about input i can be shown on its row).
 */
export function checkRows(
  rows: SubRow[],
  defaultState: string | null,
): { checks: RowCheck[]; valid: SubInput[]; validIds: number[] } {
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
    if (place) warnings.push(`The name seems to end with a place ("${place.city}, ${place.state}").`);
    else if (!r.city.trim()) warnings.push("No city: common names may not match.");
    if (!state) warnings.push("No state: matching works best with a city and state.");
    return { empty: false, errors, warnings, place };
  });
  const sent = rows.filter((_, i) => !checks[i].empty && checks[i].errors.length === 0);
  const valid = sent.map((r) => ({
    name: r.name.trim(),
    city: r.city.trim() || null,
    state: r.state || defaultState || null,
    trade: r.trade.trim() || null,
    licence: r.licence.trim() || null,
  }));
  return { checks, valid, validIds: sent.map((r) => r.id) };
}
