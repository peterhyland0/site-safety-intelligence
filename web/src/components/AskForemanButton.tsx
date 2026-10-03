import { Link } from "react-router";
import { ASK_TOGGLE_ID, CHAT_PANEL_ID, useChatPanel } from "../lib/chatPanel";
import { IconChat } from "./Icons";

/** Opens the foreman chat: docked beside the page on wide screens, the full-page /ask route otherwise. */
export function AskForemanButton({ projectId }: { projectId: string }) {
  const panel = useChatPanel();
  const label = (
    <>
      <IconChat size={16} />
      Ask the foreman assistant
    </>
  );

  if (!panel?.canDock) {
    return (
      <Link to={`/projects/${encodeURIComponent(projectId)}/ask`} className="btn btn-primary btn-sm">
        {label}
      </Link>
    );
  }

  const open = panel.openProjectId === projectId;
  return (
    <button
      id={ASK_TOGGLE_ID}
      type="button"
      className="btn btn-primary btn-sm"
      aria-expanded={open}
      aria-controls={open ? CHAT_PANEL_ID : undefined}
      onClick={() => (open ? document.getElementById("ask-input")?.focus() : panel.open(projectId))}
    >
      {label}
    </button>
  );
}
