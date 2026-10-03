import { createContext, useContext } from "react";
import type { User } from "../api/types";

export type Auth = {
  user: User;
  signOut: () => Promise<void>;
};

/** Provided by AuthGate once someone is signed in. Null outside it (tests that render a page alone). */
export const AuthContext = createContext<Auth | null>(null);

export function useAuth(): Auth | null {
  return useContext(AuthContext);
}
