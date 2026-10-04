import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { MatchedEstablishment } from "../api/types";
import { EstablishmentItem } from "../components/MatchBuckets";

const est = (over: Partial<MatchedEstablishment> = {}): MatchedEstablishment => ({
  establishment_key: "k1",
  display_name: "CLARK CONSTRUCTION GROUP, LLC",
  name_variants: [],
  address: "7900 WESTPARK DR",
  city: "MCLEAN",
  state: "VA",
  zip: "22102",
  trade_label: null,
  first_seen: "2022-09-16",
  last_seen: "2026-03-27",
  inspections: 18,
  bucket: "matched",
  method: "rule",
  rule_id: "M1",
  confidence: null,
  rationale: "Same name in the same state",
  has_red_flags: false,
  ...over,
});

const item = (over: Partial<MatchedEstablishment>) => render(<ul><EstablishmentItem est={est(over)} /></ul>);

describe("A record's decision", () => {
  it("says a record matched from the company's website is matched, with its rule, not held for an answer", () => {
    item({
      method: "profile",
      rule_id: "M4",
      rationale: "Your sub's name at an address Clark Construction lists on clarkconstruction.com (7900 Westpark Drive Suite T300, McLean VA)",
    });
    expect(screen.getByText(/Your sub's name at an address Clark Construction lists/)).toBeInTheDocument();
    expect(screen.getByText("M4")).toBeInTheDocument();
    expect(screen.getByText("Company's website")).toHaveAttribute("title", expect.stringMatching(/^Matched: your sub's own name/));
  });

  it("keeps a held profile record's hint", () => {
    item({ bucket: "possible", method: "profile", rule_id: "PROFILE", rationale: "At an address … waiting for your answer" });
    expect(screen.getByText("Company's website")).toHaveAttribute("title", expect.stringMatching(/^Held for your answer/));
    expect(screen.queryByText("PROFILE")).not.toBeInTheDocument();
  });

  it("shows where an answer carried from, and the GC's own answer in plain words", () => {
    item({
      method: "gc",
      rule_id: "C1",
      rationale: "Carried from your answer about 'GUY F ATKINSON CONSTRUCTION' (Costa Mesa, CA): the same company name",
    });
    expect(screen.getByText(/Carried from your answer about 'GUY F ATKINSON CONSTRUCTION'/)).toBeInTheDocument();
    expect(screen.getByText("Your decision")).toHaveAttribute("title", expect.stringMatching(/^Carried from your answer/));

    item({ establishment_key: "k2", method: "gc", rule_id: null, rationale: "Set by the GC" });
    expect(screen.getByText("You confirmed this record is your sub.")).toBeInTheDocument();
  });
});
