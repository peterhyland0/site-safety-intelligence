import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AskResponse, ChatDetail, ChatReply, ChatSummary, InspectionDetail } from "../api/types";
import { toProjectDetail } from "../mock/derive";
import { seedProjects } from "../mock/fixtures";
import { AskPage } from "../pages/AskPage";

const api = vi.hoisted(() => ({
  getProject: vi.fn(),
  health: vi.fn(),
  getInspection: vi.fn(),
  listChats: vi.fn(),
  getChat: vi.fn(),
  createChat: vi.fn(),
  sendMessage: vi.fn(),
  deleteChat: vi.fn(),
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, MOCK_MODE: false, api };
});

const OSHA_URL = "https://www.osha.gov/ords/imis/establishment.search?establishment=SUMMIT%20RIDGE%20ROOFING%20LLC&state=TN&startmonth=03&startday=14&startyear=2022";

const inspection: InspectionDetail = {
  activity_nr: 1598712,
  open_date: "2022-03-14",
  close_date: "2022-09-01",
  is_open: false,
  is_provisional: false,
  no_inspection: false,
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

const NOW = new Date().toISOString();
let messageSeq = 0;

const summary = (chatId: string, title: string, messageCount = 2): ChatSummary => ({
  chat_id: chatId,
  project_id: "demo-riverside",
  title,
  created_at: NOW,
  updated_at: NOW,
  message_count: messageCount,
});

/** What the server returns for one question: the chat and the stored question and answer. */
function reply(question: string, response: AskResponse, chatId = "chat-1"): ChatReply {
  return {
    chat: summary(chatId, question),
    messages: [
      { message_id: ++messageSeq, role: "user", content: question, response: null, created_at: NOW },
      { message_id: ++messageSeq, role: "assistant", content: response.answer, response, created_at: NOW },
    ],
  };
}

function detail(chatId: string, turns: [string, AskResponse][]): ChatDetail {
  return {
    ...summary(chatId, turns[0][0], turns.length * 2),
    messages: turns.flatMap(([q, r]) => reply(q, r, chatId).messages),
  };
}

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
    api.listChats.mockResolvedValue([]);
  });

  it("sends a suggested question, shows a typing indicator, then the answer with citations and coverage", async () => {
    const user = userEvent.setup();
    let resolve!: (r: ChatReply) => void;
    api.createChat.mockImplementation(() => new Promise<ChatReply>((r) => (resolve = r)));
    renderChat();

    await user.click(screen.getByRole("button", { name: "Which subs had a fatality?" }));
    expect(api.createChat).toHaveBeenCalledWith("demo-riverside", { question: "Which subs had a fatality?" });
    expect(screen.getByText(/checking the records/)).toBeInTheDocument();

    resolve(
      reply(
        "Which subs had a fatality?",
        answer({
          answer: "**Summit Ridge Roofing**: fatality investigation with 3 serious citations, Mar 14, 2022.",
          citations: [{ activity_nr: 1598712, url: OSHA_URL }],
          coverage: "Checked all 9 subs, all years.",
        }),
      ),
    );

    expect(await screen.findByText("Summit Ridge Roofing")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inspection 1598712: show the record" })).toBeInTheDocument();
    expect(screen.getByText("Checked all 9 subs, all years.")).toBeInTheDocument();
    expect(screen.queryByText(/checking the records/)).not.toBeInTheDocument();
  });

  it("opens a cited inspection's record in the app, with osha.gov as a secondary link", async () => {
    const user = userEvent.setup();
    api.createChat.mockResolvedValue(
      reply("Which subs had a fatality?", answer({ answer: "See the fatality.", citations: [{ activity_nr: 1598712, url: OSHA_URL }] })),
    );
    api.getInspection.mockResolvedValue(inspection);
    renderChat();

    await user.click(screen.getByRole("button", { name: "Which subs had a fatality?" }));
    await user.click(await screen.findByRole("button", { name: "Inspection 1598712: show the record" }));

    expect(api.getInspection).toHaveBeenCalledWith(1598712);
    const sheet = await screen.findByRole("dialog", { name: "Inspection 1598712" });
    expect(await within(sheet).findByText(/Fall protection/)).toBeInTheDocument();
    expect(within(sheet).getByText("SUMMIT RIDGE ROOFING LLC")).toBeInTheDocument();
    expect(within(sheet).getByRole("link", { name: /Find inspection 1598712 on osha.gov/ })).toHaveAttribute("href", OSHA_URL);

    await user.click(within(sheet).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("turns clarify options into tap buttons that ask 'I mean <name>' in the same chat", async () => {
    const user = userEvent.setup();
    api.createChat.mockResolvedValueOnce(
      reply(
        "How is the Dallas sub doing?",
        answer({
          status: "clarify",
          answer: "Which one do you mean?",
          clarify_options: [
            { sub_id: "sub-summit", name: "Summit Ridge Roofing" },
            { sub_id: "sub-trinity", name: "Trinity Concrete" },
          ],
        }),
      ),
    );
    api.sendMessage.mockResolvedValueOnce(reply("I mean Trinity Concrete", answer({ answer: "Trinity Concrete: Review." })));
    renderChat();

    const input = screen.getByLabelText("Your question");
    await user.type(input, "How is the Dallas sub doing?{enter}");
    await user.click(await screen.findByRole("button", { name: "I mean Trinity Concrete" }));

    // the server holds the history: the browser sends only the question, to the chat it belongs to
    expect(api.sendMessage).toHaveBeenCalledWith("chat-1", { question: "I mean Trinity Concrete" });
    expect(api.createChat).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Trinity Concrete: Review.")).toBeInTheDocument();
    expect(sessionStorage.getItem("ssi-chat-open-demo-riverside")).toBe("chat-1");
  });

  it("explains no_api_key and needs_confirmation in plain words", async () => {
    const user = userEvent.setup();
    api.createChat.mockResolvedValueOnce(reply("Who is worst?", answer({ status: "no_api_key", answer: "" })));
    api.sendMessage.mockResolvedValueOnce(
      reply(
        "Tell me about Trinity",
        answer({
          status: "needs_confirmation",
          answer: "Trinity Concrete has 1 unconfirmed record.",
          clarify_options: [{ sub_id: "sub-trinity", name: "Trinity Concrete" }],
        }),
      ),
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

  it("reopens the chat this tab had open, from the server, and keeps asking in it", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("ssi-chat-open-demo-riverside", "chat-9");
    api.getChat.mockResolvedValue(detail("chat-9", [["Who has open cases?", answer({ answer: "Cooper Steel has one open case." })]]));
    api.sendMessage.mockResolvedValue(reply("Since when?", answer({ answer: "Opened Jan 2026." }), "chat-9"));
    renderChat();

    expect(await screen.findByText("Cooper Steel has one open case.")).toBeInTheDocument();
    expect(api.getChat).toHaveBeenCalledWith("chat-9");
    await user.type(screen.getByLabelText("Your question"), "Since when?{enter}");
    expect(api.sendMessage).toHaveBeenCalledWith("chat-9", { question: "Since when?" });
    expect(await screen.findByText("Opened Jan 2026.")).toBeInTheDocument();
    expect(api.createChat).not.toHaveBeenCalled();
  });

  it("starts fresh when the chat it had open was deleted elsewhere", async () => {
    const { ApiError } = await import("../api/client");
    sessionStorage.setItem("ssi-chat-open-demo-riverside", "chat-gone");
    api.getChat.mockRejectedValue(new ApiError(404, "Chat not found"));
    renderChat();

    expect(await screen.findByText("Ask about the subs on this job")).toBeInTheDocument();
    expect(sessionStorage.getItem("ssi-chat-open-demo-riverside")).toBeNull();
  });

  it("New chat clears the conversation, and the next question starts another chat", async () => {
    const user = userEvent.setup();
    api.createChat
      .mockResolvedValueOnce(reply("Who has open cases?", answer({ answer: "One open case." }), "chat-1"))
      .mockResolvedValueOnce(reply("Which subs had a fatality?", answer({ answer: "Summit Ridge." }), "chat-2"));
    renderChat();

    await user.type(screen.getByLabelText("Your question"), "Who has open cases?{enter}");
    expect(await screen.findByText("One open case.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "New chat" }));
    expect(screen.queryByText("One open case.")).not.toBeInTheDocument();
    expect(sessionStorage.getItem("ssi-chat-open-demo-riverside")).toBeNull();

    await user.click(await screen.findByRole("button", { name: "Which subs had a fatality?" }));
    expect(api.createChat).toHaveBeenCalledTimes(2);
    expect(await screen.findByText("Summit Ridge.")).toBeInTheDocument();
    expect(sessionStorage.getItem("ssi-chat-open-demo-riverside")).toBe("chat-2");
  });

  it("lists past chats to pick up, reopen or delete", async () => {
    const user = userEvent.setup();
    api.listChats.mockResolvedValue([summary("chat-a", "Who has open cases?", 4), summary("chat-b", "Compare everyone")]);
    api.getChat.mockResolvedValue(detail("chat-a", [["Who has open cases?", answer({ answer: "Cooper Steel has one." })]]));
    api.deleteChat.mockResolvedValue(undefined);
    renderChat();

    // an empty chat offers the recent ones under the suggestions
    const recent = await screen.findByRole("list", { name: "Pick up a past chat" });
    expect(within(recent).getAllByRole("button").map((b) => b.textContent)).toEqual([
      expect.stringContaining("Who has open cases?"),
      expect.stringContaining("Compare everyone"),
    ]);

    await user.click(screen.getByRole("button", { name: "Past chats" }));
    const sheet = await screen.findByRole("dialog", { name: "Past chats" });
    expect(within(sheet).getByText(/2 questions/)).toBeInTheDocument();

    await user.click(within(sheet).getByRole("button", { name: "Delete chat: Compare everyone" }));
    expect(api.deleteChat).not.toHaveBeenCalled(); // asks first
    await user.click(within(sheet).getByRole("button", { name: "Delete" }));
    expect(api.deleteChat).toHaveBeenCalledWith("chat-b");
    await waitFor(() => expect(within(sheet).queryByText("Compare everyone")).not.toBeInTheDocument());

    await user.click(within(sheet).getByRole("button", { name: /^Who has open cases\?/ }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(await screen.findByText("Cooper Steel has one.")).toBeInTheDocument();
    expect(api.getChat).toHaveBeenCalledWith("chat-a");
    expect(sessionStorage.getItem("ssi-chat-open-demo-riverside")).toBe("chat-a");
  });
});
