import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { SubCard, WebCheckResult } from "../api/types";
import { WebCheck, webCheckSummary } from "../components/WebCheck";

const result = (over: Partial<WebCheckResult> = {}): WebCheckResult => ({
  card: {} as SubCard,
  searched: 4,
  checked_groups: 4,
  same: 2,
  different: 1,
  unsure: 1,
  left: 0,
  limit_reached: false,
  questions: 2,
  ...over,
});

describe("Web check", () => {
  it("offers to check the undecided records and says nothing is decided without the GC", async () => {
    const user = userEvent.setup();
    const onCheck = vi.fn();
    render(<WebCheck info={{ available: true, unchecked: 12, checked: 0 }} busy={false} result={null} onCheck={onCheck} />);
    expect(screen.getByText(/nothing is counted or dropped without your answer/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Check 12 records on the web" }));
    expect(onCheck).toHaveBeenCalledOnce();
  });

  it("shows that it's working, and what a press found", () => {
    const { rerender } = render(
      <WebCheck info={{ available: true, unchecked: 3, checked: 0 }} busy={true} result={null} onCheck={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /Checking records on the web/ })).toBeDisabled();
    rerender(<WebCheck info={{ available: true, unchecked: 0, checked: 4 }} busy={false} result={result()} onCheck={vi.fn()} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Checked on the web: 2 records tied to this sub, 1 record to another company, 1 record not settled. Questions about them are at the top of the page.",
    );
  });

  it("says what's left, or that the day's limit is reached", () => {
    expect(webCheckSummary(result({ same: 0, different: 0, unsure: 0, left: 30, questions: 0 }))).toBe(
      "Nothing new found. 30 records still to check: press the button again.",
    );
    expect(webCheckSummary(result({ left: 5, limit_reached: true }))).toMatch(/Today's web-check limit is reached/);
    expect(webCheckSummary(result({ same: 0, different: 0, unsure: 0, left: 30, questions: 0 }), true)).toBe(
      "Nothing new found. 30 records still to check.",
    );
  });

  it("says what auto-match settled, and that red-flagged records still come back as a question", () => {
    expect(webCheckSummary(result({ matched: 2, excluded: 1, questions: 1 }))).toBe(
      "Checked on the web: 2 records tied to this sub, 1 record to another company, 1 record not settled. " +
        "Auto-match matched 2 records and excluded 1 record. A question about them is at the top of the page.",
    );
    render(
      <WebCheck
        info={{ available: true, unchecked: 3, checked: 0, auto_check: true, auto_match: true }}
        busy={true}
        result={null}
        onCheck={vi.fn()}
      />,
    );
    expect(screen.getByText(/auto-match takes its answer/)).toHaveTextContent("Records with red flags come back as a question.");
    expect(screen.getByRole("button", { name: /Checking records on the web automatically/ })).toBeDisabled();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument(); // the settings are in the Add subs box
  });
});
