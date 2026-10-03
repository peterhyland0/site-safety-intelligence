import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AskResponse } from "../api/types";
import { toProjectDetail } from "../mock/derive";
import { seedProjects } from "../mock/fixtures";
import { AskPage } from "../pages/AskPage";

const api = vi.hoisted(() => ({
  getProject: vi.fn(),
  health: vi.fn(),
  ask: vi.fn(),
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, MOCK_MODE: false, api };
});

const answer = (r: Partial<AskResponse>): AskResponse => ({
  status: "answered",
  answer: "",
  citations: [],
  coverage: null,
  clarify_options: [],
  tools_used: [],
  ...r,
});

function renderChat() {
  return render(
    <MemoryRouter initialEntries={["/projects/demo-riverside/ask"]}>
      <Routes>
        <Route path="/projects/:projectId/ask" element={<AskPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Foreman chat", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getProject.mockResolvedValue(toProjectDetail(structuredClone(seedProjects()[0])));
    api.health.mockResolvedValue({ status: "ok", data_as_of: "2026-10-02", build_id: null, llm_enabled: true, db_ok: true });
  });

  it("sends a suggested question, shows a typing indicator, then the answer with citations and coverage", async () => {
    const user = userEvent.setup();
    let resolve!: (r: AskResponse) => void;
    api.ask.mockImplementation(() => new Promise<AskResponse>((r) => (resolve = r)));
    renderChat();

    await user.click(screen.getByRole("button", { name: "Which subs had a fatality?" }));
    expect(api.ask).toHaveBeenCalledWith("demo-riverside", { question: "Which subs had a fatality?", history: [] });
    expect(screen.getByText(/checking the records/)).toBeInTheDocument();

    resolve(
      answer({
        answer: "**Summit Ridge Roofing**: fatality investigation with 3 serious citations, Mar 14, 2022.",
        citations: [{ activity_nr: 1598712, url: "https://www.osha.gov/ords/imis/establishment.inspection_detail?id=1598712" }],
        coverage: "Checked all 9 subs, all years.",
      }),
    );

    expect(await screen.findByText("Summit Ridge Roofing")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Inspection 1598712 on osha.gov/ })).toHaveAttribute(
      "href",
      "https://www.osha.gov/ords/imis/establishment.inspection_detail?id=1598712",
    );
    expect(screen.getByText("Checked all 9 subs, all years.")).toBeInTheDocument();
    expect(screen.queryByText(/checking the records/)).not.toBeInTheDocument();
  });

  it("turns clarify options into tap buttons that send 'I mean <name>' with history", async () => {
    const user = userEvent.setup();
    api.ask
      .mockResolvedValueOnce(
        answer({
          status: "clarify",
          answer: "Which one do you mean?",
          clarify_options: [
            { sub_id: "sub-summit", name: "Summit Ridge Roofing" },
            { sub_id: "sub-trinity", name: "Trinity Concrete" },
          ],
        }),
      )
      .mockResolvedValueOnce(answer({ answer: "Trinity Concrete: Review." }));
    renderChat();

    const input = screen.getByLabelText("Your question");
    await user.type(input, "How is the Dallas sub doing?{enter}");
    await user.click(await screen.findByRole("button", { name: "I mean Trinity Concrete" }));

    expect(api.ask).toHaveBeenLastCalledWith("demo-riverside", {
      question: "I mean Trinity Concrete",
      history: [
        { role: "user", content: "How is the Dallas sub doing?" },
        { role: "assistant", content: "Which one do you mean?" },
      ],
    });
    expect(await screen.findByText("Trinity Concrete: Review.")).toBeInTheDocument();
  });

  it("explains no_api_key and needs_confirmation in plain words", async () => {
    const user = userEvent.setup();
    api.ask
      .mockResolvedValueOnce(answer({ status: "no_api_key", answer: "" }))
      .mockResolvedValueOnce(
        answer({
          status: "needs_confirmation",
          answer: "Trinity Concrete has 1 unconfirmed record.",
          clarify_options: [{ sub_id: "sub-trinity", name: "Trinity Concrete" }],
        }),
      );
    renderChat();
    const input = screen.getByLabelText("Your question");

    await user.type(input, "Who is worst?{enter}");
    expect(await screen.findByText(/isn't switched on for this deployment/)).toBeInTheDocument();

    await user.type(input, "Tell me about Trinity{enter}");
    expect(await screen.findByRole("link", { name: /Answer the match question for Trinity Concrete/ })).toHaveAttribute(
      "href",
      "/projects/demo-riverside/subs/sub-trinity#questions",
    );
  });
});
