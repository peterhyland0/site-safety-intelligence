import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { checkRows, duplicatesFrom, emptyRow, placeInName, rowsFromPaste, type SubRow } from "../lib/subRows";

const row = (patch: Partial<SubRow>): SubRow => ({ ...emptyRow(), ...patch });

describe("Add subs rows", () => {
  it("ignores blank rows and sends trimmed values with the default state", () => {
    const { checks, valid } = checkRows([row({ name: " ABC Roofing ", city: "Dallas " }), row({})], "TX");
    expect(checks[1].empty).toBe(true);
    expect(valid).toEqual([{ name: "ABC Roofing", city: "Dallas", state: "TX", trade: null, licence: null }]);
  });

  it("requires a company name once anything else is filled in", () => {
    const { checks, valid } = checkRows([row({ city: "Dallas" })], "TX");
    expect(checks[0].errors).toEqual(["Add the company name."]);
    expect(valid).toEqual([]);
  });

  it("flags the same name and state twice", () => {
    const { checks } = checkRows([row({ name: "ABC Roofing", state: "TX" }), row({ name: "abc roofing" })], "TX");
    expect(checks[1].errors).toEqual(["Same name and state as sub 1."]);
  });

  it("spots a city and state typed into the name (the 'COLMEX ... BUNNELL FL' case)", () => {
    expect(placeInName("COLMEX CONTRACTING LLC. BUNNELL FL")).toEqual({
      name: "COLMEX CONTRACTING LLC.",
      city: "BUNNELL",
      state: "FL",
    });
    expect(placeInName("Smith Roofing & Co")).toBeNull(); // CO is usually "Company"
    expect(placeInName("J & J Drywall")).toBeNull();
    expect(placeInName("ABC Roofing LLC TX")).toBeNull(); // a state but no city
    const { checks } = checkRows([row({ name: "COLMEX CONTRACTING LLC. BUNNELL FL" })], "TN");
    expect(checks[0].warnings[0]).toMatch(/seems to end with a place \("BUNNELL, FL"\)/);
    expect(checks[0].place?.city).toBe("BUNNELL");
  });

  it("keeps multi-word cities together", () => {
    expect(placeInName("Smith Roofing Fort Worth TX")).toEqual({ name: "Smith Roofing", city: "Fort Worth", state: "TX" });
    expect(placeInName("Acme Glass, Inc., West Palm Beach, FL")).toEqual({
      name: "Acme Glass, Inc.",
      city: "West Palm Beach",
      state: "FL",
    });
    expect(placeInName("Lone Star Framing Co San Antonio TX")?.city).toBe("San Antonio");
  });

  it("says which row each sent input came from", () => {
    const rows = [row({ name: "A Roofing" }), row({}), row({ city: "Dallas" }), row({ name: "B Electric" })];
    const { valid, validIds } = checkRows(rows, "TX");
    expect(valid.map((v) => v.name)).toEqual(["A Roofing", "B Electric"]);
    expect(validIds).toEqual([rows[0].id, rows[3].id]);
  });

  it("reads the rows the server turned away as already on the project", () => {
    const err = new ApiError(409, "1 of these is already on this project.", {
      detail: { message: "…", duplicates: [{ row: 1, name: "Colmex", message: 'Already on this project as "COLMEX".' }] },
    });
    expect(duplicatesFrom(err)).toEqual([{ row: 1, name: "Colmex", message: 'Already on this project as "COLMEX".' }]);
    expect(duplicatesFrom(new ApiError(500, "boom"))).toEqual([]);
  });

  it("warns, without blocking, when there's no city", () => {
    const { checks, valid } = checkRows([row({ name: "Quality Roofing", state: "TN" })], null);
    expect(checks[0].warnings).toEqual(["No city: common names may not match."]);
    expect(valid).toHaveLength(1);
  });

  it("fills rows from a pasted list and keeps an unrecognised state for the GC to fix", () => {
    const rows = rowsFromPaste("ABC Roofing, Inc., Dallas TX, roofing\nBad Co, Nowhere, ZZ");
    expect(rows.map((r) => [r.name, r.city, r.state, r.trade])).toEqual([
      ["ABC Roofing, Inc.", "Dallas", "TX", "roofing"],
      ["Bad Co", "Nowhere", "", ""],
    ]);
    expect(rows[1].badState).toBe("ZZ");
    expect(checkRows(rows, "TX").checks[1].errors).toEqual([`"ZZ" from your list isn't a state: pick one.`]);
  });
});
