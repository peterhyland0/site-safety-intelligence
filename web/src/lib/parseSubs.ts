import type { SubInput } from "../api/types";

export const US_STATES: Record<string, string> = {
  AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California", CO: "Colorado",
  CT: "Connecticut", DE: "Delaware", DC: "District of Columbia", FL: "Florida", GA: "Georgia",
  HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa", KS: "Kansas",
  KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland", MA: "Massachusetts",
  MI: "Michigan", MN: "Minnesota", MS: "Mississippi", MO: "Missouri", MT: "Montana",
  NE: "Nebraska", NV: "Nevada", NH: "New Hampshire", NJ: "New Jersey", NM: "New Mexico",
  NY: "New York", NC: "North Carolina", ND: "North Dakota", OH: "Ohio", OK: "Oklahoma",
  OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina", SD: "South Dakota",
  TN: "Tennessee", TX: "Texas", UT: "Utah", VT: "Vermont", VA: "Virginia", WA: "Washington",
  WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming", PR: "Puerto Rico", GU: "Guam",
  VI: "U.S. Virgin Islands", AS: "American Samoa", MP: "Northern Mariana Islands",
};

const STATE_BY_NAME: Record<string, string> = Object.fromEntries(
  Object.entries(US_STATES).map(([code, name]) => [name.toUpperCase(), code]),
);

/** Normalise "tx", "Texas", "TX." to "TX"; null if not a recognised state. */
export function normaliseState(raw: string): string | null {
  const s = raw.trim().replace(/\.$/, "").toUpperCase();
  if (US_STATES[s]) return s;
  return STATE_BY_NAME[s] ?? null;
}

// Legal suffixes that people paste after a comma: "ABC Roofing, Inc., Dallas, TX".
const LEGAL_SUFFIX = /^(inc|incorporated|llc|l\.l\.c|co|corp|corporation|company|ltd|lp|l\.p|llp|pllc|pc|p\.c)\.?$/i;

export const MAX_ROWS = 50;

export interface ParsedRow {
  /** 1-based line number in the pasted text */
  line: number;
  raw: string;
  input: SubInput;
  /** State came from the project default rather than the pasted line */
  stateDefaulted: boolean;
  /** The state text as pasted, when it isn't a recognised state */
  badState: string | null;
  errors: string[];
  warnings: string[];
}

export interface ParseResult {
  rows: ParsedRow[];
  valid: SubInput[];
  skipped: number;
}

function clean(s: string | undefined): string | null {
  if (s == null) return null;
  const t = s.trim().replace(/\s+/g, " ");
  return t ? t : null;
}

/**
 * Parse pasted lines like `ABC Roofing, Dallas, TX, roofing, 123456` into SubInput rows.
 *
 * Columns: name, city, state, trade (optional), licence (optional). Tabs (spreadsheet paste)
 * or commas separate fields. Also accepted: "Dallas TX" in one field, full state names,
 * a header row, blank lines and # comments.
 */
export function parseSubs(text: string, defaultState?: string | null): ParseResult {
  const rows: ParsedRow[] = [];
  const lines = text.split(/\r?\n/);
  const seen = new Set<string>();

  lines.forEach((rawLine, idx) => {
    const raw = rawLine.trim();
    if (!raw || raw.startsWith("#")) return;
    if (idx === 0 && /^name\s*(,|\t)/i.test(raw)) return; // header row

    const sep = raw.includes("\t") ? "\t" : ",";
    let parts = raw.split(sep).map((p) => p.trim());

    // Re-attach legal suffixes split off by a comma: "ABC Roofing, Inc." → one name.
    // ("CO" alone after the name is Colorado, not "Co.".)
    while (parts.length > 2 && LEGAL_SUFFIX.test(parts[1])) {
      parts = [`${parts[0]}, ${parts[1]}`, ...parts.slice(2)];
    }

    const errors: string[] = [];
    const warnings: string[] = [];
    const name = clean(parts[0]);
    let city = clean(parts[1]);
    let stateRaw = clean(parts[2]);
    let rest = parts.slice(3);

    // "ABC Roofing, TX": only a state after the name.
    if (city && !stateRaw && /^[A-Za-z]{2}\.?$/.test(city) && normaliseState(city)) {
      stateRaw = city;
      city = null;
    } else if (city && !stateRaw) {
      // "Dallas TX" written in the city slot.
      const m = /^(.*?)[\s,]+([A-Za-z]{2})\.?$/.exec(city);
      if (m && normaliseState(m[2])) {
        city = clean(m[1]);
        stateRaw = m[2];
      }
    } else if (city && stateRaw && !normaliseState(stateRaw)) {
      // "ABC, Dallas TX, roofing": state glued to the city, trade in the state slot.
      const m = /^(.*?)\s+([A-Za-z]{2})\.?$/.exec(city);
      if (m && normaliseState(m[2])) {
        rest = [stateRaw, ...rest];
        city = clean(m[1]);
        stateRaw = m[2];
      }
    }

    const trade = clean(rest[0]);
    const licence = clean(rest[1]);
    if (rest.length > 2 && rest.slice(2).some((p) => p.trim())) {
      warnings.push("Extra columns ignored (expected name, city, state, trade, licence).");
    }

    if (!name) errors.push("Missing company name.");

    let state: string | null = null;
    let stateDefaulted = false;
    let badState: string | null = null;
    if (stateRaw) {
      state = normaliseState(stateRaw);
      if (!state) {
        badState = stateRaw;
        errors.push(`State "${stateRaw}" not recognised. Use a 2-letter code like TX.`);
      }
    } else if (defaultState) {
      state = defaultState;
      stateDefaulted = true;
    } else {
      warnings.push("No state given. Matching works best with city and state.");
    }
    if (!city) warnings.push("No city given. Matching works best with city and state.");

    const key = `${(name ?? "").toUpperCase()}|${state ?? ""}`;
    if (name && seen.has(key)) errors.push("Duplicate of an earlier line.");
    if (name) seen.add(key);

    rows.push({
      line: idx + 1,
      raw,
      input: { name: name ?? "", city, state, trade, licence },
      stateDefaulted,
      badState,
      errors,
      warnings,
    });
  });

  let validCount = 0;
  for (const r of rows) {
    if (r.errors.length === 0) {
      validCount++;
      if (validCount > MAX_ROWS) r.errors.push(`Over the ${MAX_ROWS}-row limit for one paste.`);
    }
  }

  const valid = rows.filter((r) => r.errors.length === 0).map((r) => r.input);
  return { rows, valid, skipped: rows.length - valid.length };
}
