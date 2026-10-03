import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { MatchedEstablishment, MatchQuestion } from "../api/types";
import { QuestionCard } from "../components/EvidenceSections";

const est = (key: string, city: string): MatchedEstablishment => ({
  establishment_key: key,
  display_name: "TINDALL CORPORATION",
  name_variants: [],
  address: null,
  city,
  state: "GA",
  zip: null,
  trade_label: null,
  first_seen: "2020-01-01",
  last_seen: "2026-08-09",
  inspections: 2,
  bucket: "possible",
  method: "llm",
  rule_id: "N1",
  confidence: 0.6,
  rationale: null,
  has_red_flags: true,
});

const question = (keys: string[]): MatchQuestion => ({
  question_id: "q1",
  text: "Are these the same company as your sub?",
  establishment_keys: keys,
  ai_suggestion: null,
  ai_rationale: null,
});

describe("Match question", () => {
  it("lets a grouped question be answered record by record", async () => {
    const user = userEvent.setup();
    const onRecord = vi.fn();
    render(
      <QuestionCard
        question={question(["a", "b"])}
        establishments={[est("a", "CONLEY"), est("b", "PETERSBURG")]}
        onAnswer={vi.fn()}
        onRecord={onRecord}
        busy={false}
      />,
    );
    expect(screen.getByRole("button", { name: "All of these are my sub" })).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Not mine" })[1]);
    expect(onRecord).toHaveBeenCalledWith("b", "excluded");
  });

  it("keeps a plain yes/no for a single record", () => {
    render(
      <QuestionCard question={question(["a"])} establishments={[est("a", "CONLEY")]} onAnswer={vi.fn()} busy={false} />,
    );
    expect(screen.getByRole("button", { name: "Yes, same company" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mine" })).not.toBeInTheDocument();
  });
});
