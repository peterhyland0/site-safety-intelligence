import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AskResponse, InspectionDetail } from "../api/types";
import { toProjectDetail } from "../mock/derive";
import { seedProjects } from "../mock/fixtures";
import { AskPage } from "../pages/AskPage";

const api = vi.hoisted(() => ({
  getProject: vi.fn(),
  health: vi.fn(),
  ask: vi.fn(),
  getInspection: vi.fn(),
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, MOCK_MODE: false, api };
});

const OSHA_URL = "https://www.osha.gov/ords/imis/establishment.inspection_detail?id=1598712.015";

const inspection: InspectionDetail = {
  activity_nr: 1598712,
  open_date: "2022-03-14",
  close_date: "2022-09-01",
  is_open: false,
  insp_type_label: "Fatality/catastrophe",
  site_city: "Nashville",
  site_state: "TN",
  jurisdiction: "state_plan",
  establishment_name: "SUMMIT RIDGE ROOFING LLC",
  citations: 1,
  serious_plus: 1,
  penalty_initial: 15625,
  penalty_current: 9375,
  fatality_status: "fatality_cited",
  shared_site_n: 0,
  dq_flags: [],
  url: OSHA_URL,
  citation_rows: [
    {
      citation_id: "01001",
      viol_type: "S",
      viol_type_label: "Serious",
      standard: "1926.501(b)(13)",
      hazard_label: "Fall protection",
      issued: "2022-08-20",
      penalty_initial: 15625,
      penalty_current: 9375,
      is_deleted: false,
      is_fta: false,
      contested: false,
    },
  ],
  accidents: [],
};

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
        citations: [{ activity_nr: 1598712, url: OSHA_URL }],
        coverage: "Checked all 9 subs, all years.",
      }),
    );

    expect(await screen.findByText("Summit Ridge Roofing")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inspection 1598712: show the record" })).toBeInTheDocument();
    expect(screen.getByText("Checked all 9 subs, all years.")).toBeInTheDocument();
    expect(screen.queryByText(/checking the records/)).not.toBeInTheDocument();
  });

  it("opens a cited inspection's record in the app, with osha.gov as a secondary link", async () => {
    const user = userEvent.setup();
    api.ask.mockResolvedValue(answer({ answer: "See the fatality.", citations: [{ activity_nr: 1598712, url: OSHA_URL }] }));
    api.getInspection.mockResolvedValue(inspection);
    renderChat();

    await user.click(screen.getByRole("button", { name: "Which subs had a fatality?" }));
    await user.click(await screen.findByRole("button", { name: "Inspection 1598712: show the record" }));

    expect(api.getInspection).toHaveBeenCalledWith(1598712);
    const sheet = await screen.findByRole("dialog", { name: "Inspection 1598712" });
    expect(await within(sheet).findByText(/Fall protection/)).toBeInTheDocument();
    expect(within(sheet).getByText("SUMMIT RIDGE ROOFING LLC")).toBeInTheDocument();
    expect(within(sheet).getByRole("link", { name: /Inspection 1598712 on osha.gov/ })).toHaveAttribute("href", OSHA_URL);

    await user.click(within(sheet).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
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
