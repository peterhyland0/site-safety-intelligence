import { describe, expect, it } from "vitest";
import type { MatchQuestion } from "../api/types";
import { answerQuestion } from "../mock/ask";
import { seedProjects } from "../mock/fixtures";

// The mock assistant mirrors the backend's precondition (ssi/agent/tools.py): only an open match question whose answer
// can add a red flag holds up an answer, as only those make the verdict Review. The others are noted instead.
describe("Mock assistant: open match questions", () => {
  const trinityAsked = (change: Partial<MatchQuestion>) => {
    const p = structuredClone(seedProjects()[0]); // the fixtures are shared module state
    const trinity = p.subs.find((s) => s.sub_id === "sub-trinity")!;
    trinity.questions = trinity.questions.map((q) => ({ ...q, ...change }));
    return answerQuestion(p, "Tell me about Trinity Concrete");
  };

  it("holds up the answer for a red-flag question", () => {
    const r = trinityAsked({});
    expect(r.status).toBe("needs_confirmation");
    expect(r.answer).toContain("1 unconfirmed record that could change the answer");
  });

  it("holds up the answer for a profile question about a record with a red flag", () => {
    expect(trinityAsked({ kind: "profile" }).status).toBe("needs_confirmation"); // e-trinity-ok: a willful citation
  });

  it("answers about a sub whose open question has no red flag at stake, and notes the question", () => {
    const r = trinityAsked({ kind: "profile", establishment_keys: ["e-trinity-x"] }); // no citations
    expect(r.status).toBe("answered");
    expect(r.answer).toContain(
      "Waiting for your answer, so not counted yet: 1 record(s) at locations the company lists need your confirmation.",
    );
    expect(trinityAsked({ kind: "remap", establishment_keys: ["e-trinity-x"] }).answer).toContain(
      "not counted yet: 1 possible match(es) need your confirmation.",
    );
    expect(trinityAsked({ kind: "web", establishment_keys: ["e-trinity-x"] }).answer).not.toContain("Waiting");
  });
});
