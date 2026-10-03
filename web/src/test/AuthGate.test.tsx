import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, friendlyMessage, request } from "../api/client";
import { AuthGate } from "../components/AuthGate";
import { Layout } from "../components/Layout";

const api = vi.hoisted(() => ({
  me: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, MOCK_MODE: false, api };
});

const PAT = { user_id: "u1", email: "pat@example.com", name: "Pat Lee" };

/** Stands in for any page: its button makes a real request through the client, which the test answers. */
function Projects() {
  return (
    <button type="button" onClick={() => void request("GET", "/api/projects").catch(() => {})}>
      Load projects
    </button>
  );
}

function renderApp() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <AuthGate>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Projects />} />
          </Route>
        </Routes>
      </AuthGate>
    </MemoryRouter>,
  );
}

describe("Sign-in", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.scrollTo = vi.fn() as typeof window.scrollTo;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("asks a signed-out visitor to sign in, then shows the app", async () => {
    const user = userEvent.setup();
    api.me.mockRejectedValue(new ApiError(401, friendlyMessage(401)));
    api.login.mockResolvedValue(PAT);
    renderApp();

    await user.type(await screen.findByLabelText("Email"), "  pat@example.com ");
    await user.type(screen.getByLabelText("Password"), "correct horse battery");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(api.login).toHaveBeenCalledWith({ email: "pat@example.com", password: "correct horse battery" });
    expect(await screen.findByRole("button", { name: "Load projects" })).toBeInTheDocument();
    expect(screen.getByText("Pat Lee")).toBeInTheDocument();
  });

  it("shows the server's reason when sign-in is refused", async () => {
    const user = userEvent.setup();
    api.me.mockRejectedValue(new ApiError(401, friendlyMessage(401)));
    const detail = { detail: "That email and password don't match an account." };
    api.login.mockRejectedValue(new ApiError(401, friendlyMessage(401, detail), detail));
    renderApp();

    await user.type(await screen.findByLabelText("Email"), "pat@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("That email and password don't match an account.");
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });

  it("goes back to sign-in when a request finds the session has ended", async () => {
    const user = userEvent.setup();
    api.me.mockResolvedValue(PAT);
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Sign in to continue." }), { status: 401 })));
    renderApp();

    await user.click(await screen.findByRole("button", { name: "Load projects" }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByText(/You've been signed out/)).toBeInTheDocument();
  });

  it("signs out from the header and forgets which chats were open", async () => {
    const user = userEvent.setup();
    api.me.mockResolvedValue(PAT);
    api.logout.mockResolvedValue(undefined);
    sessionStorage.setItem("ssi-chat-open-p1", "chat-1");
    sessionStorage.setItem("unrelated", "kept");
    renderApp();

    // the header's button (phones get the same button under the page; jsdom renders both)
    await user.click((await screen.findAllByRole("button", { name: "Sign out" }))[0]);
    expect(api.logout).toHaveBeenCalled();
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByText(/You've been signed out/)).not.toBeInTheDocument();
    expect(sessionStorage.getItem("ssi-chat-open-p1")).toBeNull();
    expect(sessionStorage.getItem("unrelated")).toBe("kept");
  });

  it("offers a retry when the server can't be reached", async () => {
    const user = userEvent.setup();
    api.me.mockRejectedValueOnce(new ApiError(0, "Can't reach the server.")).mockResolvedValueOnce(PAT);
    renderApp();

    await user.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("button", { name: "Load projects" })).toBeInTheDocument();
  });
});
