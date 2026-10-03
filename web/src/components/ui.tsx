import type { ReactNode } from "react";
import { Link } from "react-router";
import { IconExternal, IconInfo, IconSpinner } from "./Icons";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-10 text-muted justify-center">
      <IconSpinner />
      <span>{label}</span>
    </div>
  );
}

export function ErrorBanner({
  message,
  onRetry,
  status,
}: {
  message: string;
  onRetry?: () => void;
  status?: number | null;
}) {
  const isAuth = status === 401 || status === 403;
  return (
    <div role="alert" className="card flex flex-col gap-3 border-high-line p-4 sm:flex-row sm:items-center">
      <div className="flex-1">
        <p className="font-medium text-ink">{isAuth ? "Access required" : "Something went wrong"}</p>
        <p className="text-sm text-ink-2">{message}</p>
      </div>
      {isAuth ? (
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => window.location.reload()}>
          Reload and sign in
        </button>
      ) : onRetry ? (
        <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function InlineError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-sm text-high-fg">
      {message}
    </p>
  );
}

export function Note({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <p className={`flex gap-2 text-sm text-muted ${className}`}>
      <IconInfo size={16} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

export function Section({
  title,
  id,
  aside,
  children,
  className = "",
}: {
  title: ReactNode;
  id?: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const headingId = id ? `${id}-title` : undefined;
  return (
    <section id={id} aria-labelledby={headingId} className={`card p-4 sm:p-5 ${className}`}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 id={headingId} className="section-title">
          {title}
        </h2>
        {aside ? <div className="text-sm text-muted">{aside}</div> : null}
      </div>
      {children}
    </section>
  );
}

/** Link to the inspection on osha.gov (opens in a new tab). */
export function OshaLink({ url, activityNr, compact = false }: { url: string; activityNr: number; compact?: boolean }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="link inline-flex items-center gap-1 whitespace-nowrap tabular-nums"
      aria-label={`Inspection ${activityNr} on osha.gov (opens in a new tab)`}
    >
      {compact ? `#${activityNr}` : `Inspection ${activityNr}`}
      <IconExternal size={13} />
    </a>
  );
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="inline-flex min-h-9 items-center gap-1 text-sm font-medium text-accent hover:underline">
      <span aria-hidden="true">←</span>
      {children}
    </Link>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="text-base font-semibold text-ink">{value}</dd>
      {hint ? <dd className="text-xs text-muted">{hint}</dd> : null}
    </div>
  );
}
