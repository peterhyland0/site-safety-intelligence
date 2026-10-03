import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, api, errorMessage, setSignedOutHandler } from "../api/client";
import type { User } from "../api/types";
import { AuthContext, type Auth } from "../lib/auth";
import { forgetOpenChats } from "../lib/chatPanel";
import { LoginPage } from "../pages/LoginPage";
import { ErrorBanner, Loading } from "./ui";

type State =
  | { status: "checking" }
  | { status: "signed_out"; ended: boolean }
  | { status: "signed_in"; user: User }
  | { status: "unreachable"; message: string };

/** The app for a signed-in user, the sign-in page for everyone else. */
export function AuthGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ status: "checking" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    // A 401 from any request means the session ended: expired, signed out elsewhere, or the account was disabled.
    setSignedOutHandler(() => setState((s) => (s.status === "signed_in" ? { status: "signed_out", ended: true } : s)));
    return () => setSignedOutHandler(null);
  }, []);

  useEffect(() => {
    let live = true;
    api.me().then(
      (user) => live && setState({ status: "signed_in", user }),
      (err) => {
        if (!live) return;
        setState(
          err instanceof ApiError && err.status === 401
            ? { status: "signed_out", ended: false }
            : { status: "unreachable", message: errorMessage(err) },
        );
      },
    );
    return () => {
      live = false;
    };
  }, [attempt]);

  const auth = useMemo<Auth | null>(
    () =>
      state.status === "signed_in"
        ? {
            user: state.user,
            signOut: async () => {
              try {
                await api.logout();
              } catch {
                /* the cookie is cleared server-side; signed out here either way */
              }
              forgetOpenChats();
              setState({ status: "signed_out", ended: false });
            },
          }
        : null,
    [state],
  );

  if (state.status === "checking") {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Loading />
      </div>
    );
  }
  if (state.status === "unreachable") {
    return (
      <div className="mx-auto max-w-lg px-4 pt-16">
        <ErrorBanner
          message={state.message}
          onRetry={() => {
            setState({ status: "checking" });
            setAttempt((a) => a + 1);
          }}
        />
      </div>
    );
  }
  if (state.status === "signed_out") {
    return <LoginPage ended={state.ended} onSignedIn={(user) => setState({ status: "signed_in", user })} />;
  }
  return <AuthContext value={auth}>{children}</AuthContext>;
}
