import { describe, expect, it } from "vitest";
import { normaliseState, parseSubs } from "../lib/parseSubs";

describe("parseSubs", () => {
  it("parses comma-separated lines into SubInput rows", () => {
    const r = parseSubs("ABC Roofing, Dallas, TX, roofing\nLone Star Framing, Fort Worth, tx, framing, 123456");
    expect(r.valid).toEqual([
      { name: "ABC Roofing", city: "Dallas", state: "TX", trade: "roofing", licence: null },
      { name: "Lone Star Framing", city: "Fort Worth", state: "TX", trade: "framing", licence: "123456" },
    ]);
    expect(r.skipped).toBe(0);
  });

  it("accepts tabs from spreadsheet paste, a header row, blank lines and comments", () => {
    const r = parseSubs("Name\tCity\tState\n\n# comment\nCascade Steel\tTacoma\tWashington\tsteel");
    expect(r.valid).toEqual([{ name: "Cascade Steel", city: "Tacoma", state: "WA", trade: "steel", licence: null }]);
  });

  it("keeps legal suffixes with the name", () => {
    const r = parseSubs("ABC Roofing, Inc., Dallas, TX");
    expect(r.valid[0]).toMatchObject({ name: "ABC Roofing, Inc.", city: "Dallas", state: "TX" });
  });

  it("splits 'City ST' written in one field", () => {
    expect(parseSubs("ABC Roofing, Dallas TX, roofing").valid[0]).toMatchObject({ city: "Dallas", state: "TX", trade: "roofing" });
    expect(parseSubs("ABC Roofing, Dallas TX").valid[0]).toMatchObject({ city: "Dallas", state: "TX" });
  });

  it("treats a lone two-letter state after the name as the state (CO is Colorado, not Co.)", () => {
    expect(parseSubs("Front Range Paving, CO").valid[0]).toMatchObject({ name: "Front Range Paving", city: null, state: "CO" });
  });

  it("falls back to the project state and says so", () => {
    const r = parseSubs("ABC Roofing, Dallas", "TX");
    expect(r.valid[0].state).toBe("TX");
    expect(r.rows[0].stateDefaulted).toBe(true);
  });

  it("flags bad states and duplicates instead of sending them", () => {
    const r = parseSubs("ABC Roofing, Dallas, Texass\nBrazos Electric, Austin, TX\nbrazos electric, Austin, TX");
    expect(r.valid).toHaveLength(1);
    expect(r.skipped).toBe(2);
    expect(r.rows[0].errors[0]).toMatch(/not recognised/);
    expect(r.rows[2].errors[0]).toMatch(/Duplicate/);
  });

  it("normalises state names and codes", () => {
    expect(normaliseState("tx")).toBe("TX");
    expect(normaliseState("New Mexico")).toBe("NM");
    expect(normaliseState("ZZ")).toBeNull();
  });
});
