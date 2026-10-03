import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import { MOCK_MODE } from "../api/client";
import { IconShield } from "./Icons";
import { ThemeToggle } from "./ThemeToggle";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `inline-flex min-h-10 items-center rounded-lg px-2.5 text-sm font-medium sm:px-3 ${
    isActive ? "bg-surface-2 text-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink"
  }`;

export function Layout() {
  const { pathname } = useLocation();
  const isChat = /\/ask$/.test(pathname);

  // Move focus to the top of the page on navigation so screen readers announce the new page.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <div className={`flex flex-col ${isChat ? "h-dvh" : "min-h-dvh"}`}>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b border-line bg-page/95 backdrop-blur supports-[backdrop-filter]:bg-page/80">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-2 px-4">
          <Link to="/" className="mr-auto flex min-h-10 items-center gap-2 font-semibold text-ink">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-accent text-accent-ink">
              <IconShield size={16} />
            </span>
            <span className="text-[15px] leading-tight whitespace-nowrap">
              Site Safety<span className="hidden sm:inline"> Intelligence</span>
            </span>
          </Link>
          {MOCK_MODE ? (
            <span
              className="pill border-review-line bg-review-bg whitespace-nowrap text-review-fg"
              title="Showing demo fixtures (VITE_MOCK=1)"
            >
              Demo<span className="hidden sm:inline">&nbsp;data</span>
            </span>
          ) : null}
          <nav aria-label="Main" className="flex items-center gap-1">
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
      <main id="main" className={`mx-auto w-full max-w-5xl flex-1 ${isChat ? "flex min-h-0 flex-col" : "px-4 pt-4 pb-16 sm:pt-6"}`}>
        <Outlet />
      </main>
    </div>
  );
}
