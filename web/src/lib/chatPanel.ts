import { createContext, useContext, useSyncExternalStore } from "react";

/** Wide enough for the scorecard (~860px) and the chat panel side by side. Narrower screens use the full-page /ask route. */
export const DOCK_QUERY = "(min-width: 1280px)";
export const CHAT_PANEL_ID = "foreman-panel";
export const ASK_TOGGLE_ID = "ask-toggle";

export type ChatPanel = {
  /** True when the screen is wide enough to dock the chat beside the page. */
  canDock: boolean;
  /** The project whose chat is open in the panel, if any. */
  openProjectId: string | null;
  open: (projectId: string) => void;
  close: () => void;
};

/** Provided by Layout. Null outside it (tests that render a page alone), which falls back to the full-page chat. */
export const ChatPanelContext = createContext<ChatPanel | null>(null);

export function useChatPanel(): ChatPanel | null {
  return useContext(ChatPanelContext);
}

// Project names already loaded by the scorecard, so the chat can show its project at once instead of
// "Loading project…" while it fetches the project again.
const knownNames = new Map<string, string>();

export function rememberProjectName(projectId: string, name: string) {
  knownNames.set(projectId, name);
}

export function knownProjectName(projectId: string): string | null {
  return knownNames.get(projectId) ?? null;
}

// The chat each project had open in this tab, so a reload, the docked panel and the full-page /ask route all
// pick up the same conversation. Only the id: the messages themselves live on the server.
const OPEN_CHAT_PREFIX = "ssi-chat-open-";

export function openChatId(projectId: string): string | null {
  try {
    return sessionStorage.getItem(OPEN_CHAT_PREFIX + projectId);
  } catch {
    return null;
  }
}

export function rememberOpenChat(projectId: string, chatId: string | null) {
  try {
    if (chatId) sessionStorage.setItem(OPEN_CHAT_PREFIX + projectId, chatId);
    else sessionStorage.removeItem(OPEN_CHAT_PREFIX + projectId);
  } catch {
    /* storage unavailable: a reload just starts a new chat */
  }
}

/** On sign-out, so the next person in this tab doesn't reopen someone else's chat. */
export function forgetOpenChats() {
  try {
    for (const k of Object.keys(sessionStorage)) if (k.startsWith(OPEN_CHAT_PREFIX)) sessionStorage.removeItem(k);
  } catch {
    /* ignore */
  }
}

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      if (typeof window.matchMedia !== "function") return () => {};
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    () => typeof window.matchMedia === "function" && window.matchMedia(query).matches,
    () => false,
  );
}
