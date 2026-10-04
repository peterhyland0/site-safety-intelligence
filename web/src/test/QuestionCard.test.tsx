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

  it("shows a profile question's pages and says the suggestion comes from the company's site", () => {
    render(
      <QuestionCard
        question={{
          ...question(["a"]),
          kind: "profile",
          ai_suggestion: "same",
          ai_rationale: "Listed on tindallcorp.com: “Georgia Division 3361 Grant Road Conley, GA 30288”",
          sources: [{ url: "https://tindallcorp.com/contact/", title: "Contact", quote: "Georgia Division 3361 Grant Road" }],
        }}
        establishments={[est("a", "CONLEY")]}
        onAnswer={vi.fn()}
        busy={false}
      />,
    );
    expect(screen.getByText(/The company's website lists this address/)).toBeInTheDocument();
    expect(screen.queryByText(/AI read/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Contact" })).toHaveAttribute("href", "https://tindallcorp.com/contact/");
    expect(screen.getByText(/aren't counted until you answer/)).toBeInTheDocument();
  });

  it("shows a web question's quotes under the records they're about", () => {
    render(
      <QuestionCard
        question={{
          ...question(["a", "b"]),
          kind: "web",
          ai_suggestion: "different",
          ai_rationale: "From a web search: “Tindall Concrete, Conley, GA”",
          sources: [
            { url: "https://tindallconcrete.example/about", title: "About", quote: "Tindall Concrete, Conley, GA",
              owner: "Tindall Concrete", keys: ["a"] },
            { url: "https://other.example/x", title: null, quote: "Tindall Pipe, Petersburg", owner: "Tindall Pipe",
              keys: ["gone"] },
          ],
        }}
        establishments={[est("a", "CONLEY"), est("b", "PETERSBURG")]}
        onAnswer={vi.fn()}
        onRecord={vi.fn()}
        busy={false}
      />,
    );
    expect(screen.getByText(/Web pages tie these records to another company/)).toBeInTheDocument();
    expect(screen.queryByText(/AI read/)).not.toBeInTheDocument();
    // under the first record only (the second has no page)
    const [first, second] = screen.getAllByRole("listitem").filter((li) => li.textContent?.startsWith("TINDALL CORPORATION"));
    expect(first).toHaveTextContent("Tindall Concrete: “Tindall Concrete, Conley, GA”");
    expect(second).not.toHaveTextContent("“");
    expect(screen.getByRole("link", { name: "tindallconcrete.example" })).toHaveAttribute(
      "href",
      "https://tindallconcrete.example/about",
    );
    // a page about a record no longer in the question isn't shown, and there's no separate source list
    expect(screen.queryByText(/Tindall Pipe/)).not.toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Sources" })).not.toBeInTheDocument();
    expect(screen.getByText(/From a web search: nothing is counted or dropped until you answer/)).toBeInTheDocument();
  });
});
