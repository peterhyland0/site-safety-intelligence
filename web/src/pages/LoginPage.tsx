import { useState, type FormEvent } from "react";
import { ApiError, api, errorMessage } from "../api/client";
import type { User } from "../api/types";
import { LogoMark } from "../components/Icons";
import { InlineError } from "../components/ui";
import { useTitle } from "../lib/useTitle";

/** The server's own words for a refused sign-in (wrong password, too many tries); generic copy for anything else. */
function signInError(err: unknown): string {
  if (err instanceof ApiError && (err.status === 401 || err.status === 429)) {
    const detail = (err.detail as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string") return detail;
  }
  return errorMessage(err);
}

export function LoginPage({ ended, onSignedIn }: { ended: boolean; onSignedIn: (user: User) => void }) {
  useTitle("Sign in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSignedIn(await api.login({ email: email.trim(), password }));
    } catch (err) {
      setError(signInError(err));
      setBusy(false);
    }
  }

  return (
    <main id="main" className="flex min-h-dvh flex-col items-center justify-center px-4 py-10">
      <div className="mb-6 flex items-center gap-2.5 text-ink">
        <LogoMark size={36} className="shrink-0" />
        <span className="text-[19px] leading-tight font-bold tracking-[-0.02em]">Site Safety Intelligence</span>
      </div>
      <form onSubmit={onSubmit} className="card w-full max-w-sm space-y-4 p-6" aria-labelledby="sign-in-title">
        <h1 id="sign-in-title" className="text-xl font-extrabold tracking-[-0.02em] text-ink">
          Sign in
        </h1>
        {ended ? (
          <p role="status" className="text-sm text-ink-2">
            You've been signed out. Sign in again to carry on.
          </p>
        ) : null}
        <div>
          <label htmlFor="sign-in-email" className="label">
            Email
          </label>
          <input
            id="sign-in-email"
            type="email"
            className="field"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoFocus
          />
        </div>
        <div>
          <label htmlFor="sign-in-password" className="label">
            Password
          </label>
          <input
            id="sign-in-password"
            type="password"
            className="field"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <InlineError message={error} />
        <button type="submit" className="btn btn-primary w-full" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="text-xs text-muted">Accounts are set up by your administrator.</p>
      </form>
    </main>
  );
}
