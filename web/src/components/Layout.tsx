import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { Link, matchPath, NavLink, Outlet, useLocation } from "react-router";
import { MOCK_MODE } from "../api/client";
import { ASK_TOGGLE_ID, CHAT_PANEL_ID, ChatPanelContext, DOCK_QUERY, useMediaQuery, type ChatPanel } from "../lib/chatPanel";
import { ForemanChat } from "../pages/AskPage";
import { LogoMark } from "./Icons";
import { ThemeToggle } from "./ThemeToggle";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `inline-flex min-h-10 items-center rounded-full px-2.5 text-sm font-semibold sm:px-3.5 ${
    isActive ? "bg-surface-2 text-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink"
  }`;

export function Layout() {
  const { pathname } = useLocation();
  const isChat = /\/ask$/.test(pathname);
  const projectId = matchPath("/projects/:projectId/*", pathname)?.params.projectId ?? null;
  const canDock = useMediaQuery(DOCK_QUERY);
  const [openProjectId, setOpenProjectId] = useState<string | null>(null);

  // Leaving the project closes its panel; the conversation itself is kept for when it's reopened.
  const [shownFor, setShownFor] = useState(projectId);
  if (projectId !== shownFor) {
    setShownFor(projectId);
    if (projectId !== openProjectId) setOpenProjectId(null);
  }

  const chatPanel = useMemo<ChatPanel>(
    () => ({
      canDock,
      openProjectId,
      open: setOpenProjectId,
      close: () => {
        setOpenProjectId(null);
        document.getElementById(ASK_TOGGLE_ID)?.focus();
      },
    }),
    [canDock, openProjectId],
  );
  const panelProjectId = canDock && !isChat && openProjectId === projectId ? openProjectId : null;

  function onPanelKeyDown(e: KeyboardEvent) {
    // Escape inside an open inspection record closes the record, not the panel.
    if (e.key === "Escape" && !(e.target as Element).closest("dialog")) chatPanel.close();
  }

  // Move focus to the top of the page on navigation so screen readers announce the new page.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <ChatPanelContext value={chatPanel}>
      <div className={`flex flex-col ${isChat ? "h-dvh" : "min-h-dvh"}`}>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        {/* With the chat docked, the header's content lines up with the narrower page column. */}
        <header
          className={`sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur supports-[backdrop-filter]:bg-surface/90 ${
            panelProjectId ? "pr-[420px]" : ""
          }`}
        >
          <div className="mx-auto flex h-14 max-w-5xl items-center gap-2 px-4">
            {/* On phones the Demo pill sits under the name so it costs no width; under 360px only the mark shows. */}
            <Link to="/" className="mr-auto flex min-h-10 min-w-0 items-center gap-2.5 text-ink">
              <LogoMark size={32} className="shrink-0 rounded-lg dark:ring-1 dark:ring-white/10" />
              <span className="flex min-w-0 flex-col items-start gap-0.5 sm:flex-row sm:items-center sm:gap-2">
                <span className="max-w-full truncate text-[17px] leading-tight font-bold tracking-[-0.02em] max-[359px]:sr-only">
                  Site Safety<span className="hidden font-medium text-muted sm:inline"> Intelligence</span>
                </span>
                {MOCK_MODE ? (
                  <span
                    className="pill border-review-line bg-review-bg px-2 py-0 text-[11px] whitespace-nowrap text-review-fg sm:px-2.5 sm:py-0.5 sm:text-xs"
                    title="Showing demo fixtures (VITE_MOCK=1)"
                  >
                    Demo<span className="hidden sm:inline">&nbsp;data</span>
                  </span>
                ) : null}
              </span>
            </Link>
            <nav aria-label="Main" className="flex items-center sm:gap-1">
              <NavLink to="/" end className={navClass}>
                Projects
              </NavLink>
              <NavLink to="/methodology" className={navClass}>
                Method
              </NavLink>
              <ThemeToggle />
            </nav>
          </div>
        </header>
        <div className={`flex flex-1 ${isChat ? "min-h-0" : ""}`}>
          <main
            id="main"
            className={`mx-auto w-full max-w-5xl min-w-0 flex-1 ${isChat ? "flex min-h-0 flex-col" : "px-4 pt-4 pb-16 sm:pt-6"}`}
          >
            <Outlet />
          </main>
          {panelProjectId ? (
            <aside
              id={CHAT_PANEL_ID}
              aria-label="Foreman assistant"
              onKeyDown={onPanelKeyDown}
              className="sticky top-14 flex h-[calc(100dvh-3.5rem)] w-[420px] shrink-0 flex-col self-start border-l border-line bg-surface"
            >
              <ForemanChat key={panelProjectId} projectId={panelProjectId} variant="panel" onClose={chatPanel.close} />
            </aside>
          ) : null}
        </div>
      </div>
    </ChatPanelContext>
  );
}
