import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ProjectDetail, SubCard } from "../api/types";
import { toProjectDetail } from "../mock/derive";
import { seedProjects } from "../mock/fixtures";
import { ProjectPage } from "../pages/ProjectPage";

const api = vi.hoisted(() => ({
  getProject: vi.fn(),
  updateProject: vi.fn(),
  addSubs: vi.fn(),
  adjudicate: vi.fn(),
  deleteProject: vi.fn(),
  health: vi.fn(),
  exportCsvUrl: (id: string) => `/api/projects/${id}/export.csv`,
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, MOCK_MODE: false, api };
});

// Node's own experimental localStorage global shadows jsdom's here, so give the tests a plain one (as ThemeToggle.test)
function memoryStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() {
      return m.size;
    },
    clear: () => m.clear(),
    getItem: (k) => m.get(k) ?? null,
    key: (i) => [...m.keys()][i] ?? null,
    removeItem: (k) => void m.delete(k),
    setItem: (k, v) => void m.set(k, String(v)),
  };
}

function detail(): ProjectDetail {
  return toProjectDetail(structuredClone(seedProjects()[0]));
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/projects/demo-riverside"]}>
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectPage />} />
        <Route path="/" element={<h1>All projects</h1>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("GC scorecard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.health.mockResolvedValue({ status: "ok", data_as_of: null, build_id: null, llm_enabled: true, db_ok: true, profile_lookup: false });
    vi.stubGlobal("localStorage", memoryStorage());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("ranks subs with verdict chips that carry text, and keeps 'No OSHA record' distinct from 'No flags'", async () => {
    const d = detail();
    api.getProject.mockResolvedValue(d);
    api.adjudicate.mockImplementation(() => new Promise(() => {})); // stays "resolving"
    renderPage();

    expect(await screen.findByRole("heading", { name: "Riverside Medical Office Building" })).toBeInTheDocument();
    const cards = screen.getAllByRole("article");
    expect(cards).toHaveLength(9);
    expect(within(cards[0]).getByText("High concern")).toBeInTheDocument();
    expect(within(cards[0]).getByText(/Fatality investigation where this employer was cited/)).toBeInTheDocument();

    const noRecord = cards.find((c) => within(c).queryByText("No OSHA record"))!;
    expect(within(noRecord).getByText(/unknown, not clean/)).toBeInTheDocument();
    expect(noRecord.className).toContain("border-dashed");
    const noFlags = cards.find((c) => within(c).queryByText("No flags"))!;
    expect(noFlags.className).not.toContain("border-dashed");

    // pending question badge + export link
    expect(screen.getByRole("link", { name: /1 question to answer/ })).toHaveAttribute("href", "/projects/demo-riverside/subs/sub-trinity#questions");
    expect(screen.getByRole("link", { name: /Export CSV/ })).toHaveAttribute("href", "/api/projects/demo-riverside/export.csv");
    expect(screen.getByRole("link", { name: /Ask the foreman assistant/ })).toHaveAttribute("href", "/projects/demo-riverside/ask");
  });

  it("adjudicates subs that need it, shows progress, then applies the returned card", async () => {
    const d = detail();
    const abc = d.subs.find((s) => s.sub_id === "sub-abc")!;
    expect(abc.match_status).toBe("needs_adjudication");
    api.getProject.mockResolvedValue(d);
    let resolve!: (c: SubCard) => void;
    api.adjudicate.mockImplementation(() => new Promise<SubCard>((r) => (resolve = r)));
    renderPage();

    expect(await screen.findByText(/Resolving 7 uncertain records/)).toBeInTheDocument();
    expect(api.adjudicate).toHaveBeenCalledTimes(1);
    expect(api.adjudicate).toHaveBeenCalledWith("demo-riverside", "sub-abc");

    const resolved: SubCard = { ...abc, match_status: "resolved", possible_inspections: 4 };
    api.getProject.mockResolvedValue({ ...d, subs: d.subs.map((s) => (s.sub_id === "sub-abc" ? resolved : s)) });
    resolve(resolved);

    await waitFor(() => expect(screen.queryByText(/Resolving/)).not.toBeInTheDocument());
    expect(screen.getByText(/\+4 possible-match inspections, not counted/)).toBeInTheDocument();
    expect(api.adjudicate).toHaveBeenCalledTimes(1);
  });

  it("adds subs from fields: company name required, state defaults to the project's", async () => {
    const user = userEvent.setup();
    api.getProject.mockResolvedValue({ ...detail(), subs: [] });
    api.addSubs.mockResolvedValue([]);
    renderPage();

    await user.type(await screen.findByLabelText("Sub 1: Company name"), "ABC Roofing");
    await user.type(screen.getByLabelText("Sub 1: City"), "Dallas");
    await user.selectOptions(screen.getByLabelText("Sub 1: State"), "TX");
    await user.type(screen.getByLabelText("Sub 1: Trade"), "roofing");
    await user.click(screen.getByRole("button", { name: "Add another sub" }));
    await user.type(screen.getByLabelText("Sub 2: Company name"), "Lone Star Framing");
    await user.click(screen.getByRole("button", { name: "Add 2 subs" }));

    expect(api.addSubs).toHaveBeenCalledWith(
      "demo-riverside",
      [
        { name: "ABC Roofing", city: "Dallas", state: "TX", trade: "roofing", licence: null },
        { name: "Lone Star Framing", city: null, state: detail().project.state, trade: null, licence: null },
      ],
      false, // no web lookup unless the GC ticks it
    );
  });

  it("offers the web lookup when the server can do it, off until ticked, and remembers the choice", async () => {
    const user = userEvent.setup();
    api.health.mockResolvedValue({ status: "ok", data_as_of: null, build_id: null, llm_enabled: true, db_ok: true, profile_lookup: true });
    api.getProject.mockResolvedValue({ ...detail(), subs: [] });
    api.addSubs.mockResolvedValue([]);
    renderPage();

    const box = await screen.findByRole("checkbox", { name: "Look up each company on the web first" });
    expect(box).not.toBeChecked();
    await user.click(box);
    await user.type(screen.getByLabelText("Sub 1: Company name"), "Tindell Corporation");
    await user.click(screen.getByRole("button", { name: "Add 1 sub" }));
    expect(api.addSubs).toHaveBeenCalledWith("demo-riverside", [expect.objectContaining({ name: "Tindell Corporation" })], true);
    expect(window.localStorage.getItem("ssi-lookup-profiles")).toBe("1");
  });

  it("hides the web lookup when the server can't do it", async () => {
    api.getProject.mockResolvedValue({ ...detail(), subs: [] });
    renderPage();
    await screen.findByLabelText("Sub 1: Company name");
    expect(screen.queryByRole("checkbox", { name: /Look up each company/ })).not.toBeInTheDocument();
  });

  it("fills rows from a pasted list and holds back a row with an unrecognised state until it's fixed", async () => {
    const user = userEvent.setup();
    api.getProject.mockResolvedValue({ ...detail(), subs: [] });
    api.addSubs.mockResolvedValue([]);
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Paste a list" }));
    await user.type(screen.getByLabelText(/Paste from a spreadsheet/), "ABC Roofing, Dallas, TX, roofing{enter}Bad Co, Nowhere, ZZ");
    await user.click(screen.getByRole("button", { name: "Fill in the rows" }));

    expect(screen.getByText(/Filled in 2 rows from your list/)).toBeInTheDocument();
    expect(screen.getByLabelText("Sub 1: Company name")).toHaveValue("ABC Roofing");
    expect(screen.getByText(/"ZZ" from your list isn't a state/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add 1 sub" })).toBeDisabled();

    await user.selectOptions(screen.getByLabelText("Sub 2: State"), "NV");
    await user.click(screen.getByRole("button", { name: "Add 2 subs" }));
    expect(api.addSubs).toHaveBeenCalledWith(
      "demo-riverside",
      [
        { name: "ABC Roofing", city: "Dallas", state: "TX", trade: "roofing", licence: null },
        { name: "Bad Co", city: "Nowhere", state: "NV", trade: null, licence: null },
      ],
      false,
    );
  });

  it("deletes the project only after the GC confirms, then goes back to all projects", async () => {
    const user = userEvent.setup();
    api.getProject.mockResolvedValue(detail());
    api.adjudicate.mockImplementation(() => new Promise(() => {}));
    api.deleteProject.mockResolvedValue({ ok: true });
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Delete project" }));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("Delete Riverside Medical Office Building?"));
    expect(api.deleteProject).not.toHaveBeenCalled();

    confirm.mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: "Delete project" }));
    expect(api.deleteProject).toHaveBeenCalledWith("demo-riverside");
    expect(await screen.findByRole("heading", { name: "All projects" })).toBeInTheDocument();
  });

  it("shows an access message on 401", async () => {
    const { ApiError, friendlyMessage } = await import("../api/client");
    api.getProject.mockRejectedValue(new ApiError(401, friendlyMessage(401)));
    renderPage();
    expect(await screen.findByText("Access required")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });
});
