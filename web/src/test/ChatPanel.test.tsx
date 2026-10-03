import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Layout } from "../components/Layout";
import { toProjectDetail } from "../mock/derive";
import { seedProjects } from "../mock/fixtures";
import { AskPage } from "../pages/AskPage";
import { ProjectPage } from "../pages/ProjectPage";

const api = vi.hoisted(() => ({
  getProject: vi.fn(),
  updateProject: vi.fn(),
  addSubs: vi.fn(),
  adjudicate: vi.fn(),
  health: vi.fn(),
  ask: vi.fn(),
  exportCsvUrl: (id: string) => `/api/projects/${id}/export.csv`,
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, MOCK_MODE: false, api };
});

function setScreen(wide: boolean) {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (media: string) => ({ matches: wide, media, addEventListener: () => {}, removeEventListener: () => {} }),
  });
}

function renderApp() {
  return render(
    <MemoryRouter initialEntries={["/projects/demo-riverside"]}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="projects/:projectId" element={<ProjectPage />} />
          <Route path="projects/:projectId/ask" element={<AskPage />} />
          <Route path="methodology" element={<p>How it works</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("Foreman chat docked beside the scorecard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.scrollTo = vi.fn() as typeof window.scrollTo;
    api.getProject.mockResolvedValue(toProjectDetail(structuredClone(seedProjects()[0])));
    api.adjudicate.mockImplementation(() => new Promise(() => {}));
    api.health.mockResolvedValue({ status: "ok", data_as_of: "2026-10-02", build_id: null, llm_enabled: true, db_ok: true });
  });

  afterEach(() => {
    delete (window as Partial<Window>).matchMedia;
  });

  it("opens beside the scorecard on wide screens, and closing it returns focus to the button", async () => {
    setScreen(true);
    const user = userEvent.setup();
    api.ask.mockImplementation(() => new Promise(() => {}));
    renderApp();

    const toggle = await screen.findByRole("button", { name: /Ask the foreman assistant/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    api.getProject.mockImplementation(() => new Promise(() => {})); // the panel's own fetch never lands
    await user.click(toggle);

    const panel = screen.getByRole("complementary", { name: "Foreman assistant" });
    // the scorecard already knows the project, so the panel names it at once instead of "Loading project…"
    expect(within(panel).getByText("Riverside Medical Office Building")).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("heading", { name: "Riverside Medical Office Building" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Your question" })).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Which subs had a fatality?" }));
    expect(api.ask).toHaveBeenCalledWith("demo-riverside", { question: "Which subs had a fatality?", history: [] });

    await user.click(screen.getByRole("button", { name: "Close the foreman assistant" }));
    expect(panel).not.toBeInTheDocument();
    expect(toggle).toHaveFocus();
  });

  it("closes on Escape and when the user leaves the project", async () => {
    setScreen(true);
    const user = userEvent.setup();
    renderApp();

    await user.click(await screen.findByRole("button", { name: /Ask the foreman assistant/ }));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("complementary", { name: "Foreman assistant" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Ask the foreman assistant/ }));
    await user.click(screen.getByRole("link", { name: "Method" }));
    expect(await screen.findByText("How it works")).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "Foreman assistant" })).not.toBeInTheDocument();
  });

  it("links to the full-page chat on narrower screens", async () => {
    setScreen(false);
    renderApp();

    const link = await screen.findByRole("link", { name: /Ask the foreman assistant/ });
    expect(link).toHaveAttribute("href", "/projects/demo-riverside/ask");
  });
});
