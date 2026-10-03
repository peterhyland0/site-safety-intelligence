import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ProjectDetail, SubCard } from "../api/types";
import { toProjectDetail } from "../mock/derive";
import { seedProjects } from "../mock/fixtures";
import { ProjectPage } from "../pages/ProjectPage";

const api = vi.hoisted(() => ({
  getProject: vi.fn(),
  updateProject: vi.fn(),
  addSubs: vi.fn(),
  adjudicate: vi.fn(),
  exportCsvUrl: (id: string) => `/api/projects/${id}/export.csv`,
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, MOCK_MODE: false, api };
});

function detail(): ProjectDetail {
  return toProjectDetail(structuredClone(seedProjects()[0]));
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/projects/demo-riverside"]}>
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("GC scorecard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

  it("previews pasted subs before adding them", async () => {
    const user = userEvent.setup();
    api.getProject.mockResolvedValue({ ...detail(), subs: [] });
    api.addSubs.mockResolvedValue([]);
    renderPage();

    const box = await screen.findByLabelText(/Subs to add/);
    await user.type(box, "ABC Roofing, Dallas, TX, roofing{enter}Bad Co, Nowhere, ZZ");
    expect(screen.getByText(/1 sub ready/)).toBeInTheDocument();
    expect(screen.getByText(/1 line will be skipped/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add 1 sub" }));
    expect(api.addSubs).toHaveBeenCalledWith("demo-riverside", [
      { name: "ABC Roofing", city: "Dallas", state: "TX", trade: "roofing", licence: null },
    ]);
  });

  it("shows an access message on 401", async () => {
    const { ApiError, friendlyMessage } = await import("../api/client");
    api.getProject.mockRejectedValue(new ApiError(401, friendlyMessage(401)));
    renderPage();
    expect(await screen.findByText("Access required")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });
});
