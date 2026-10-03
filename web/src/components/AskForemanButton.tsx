import { Link } from "react-router";
import { ASK_TOGGLE_ID, CHAT_PANEL_ID, useChatPanel } from "../lib/chatPanel";
import { IconChat } from "./Icons";

/** Opens the foreman chat: docked beside the page on wide screens, the full-page /ask route otherwise. */
export function AskForemanButton({
  projectId,
  label = "Ask the foreman assistant",
  className = "btn btn-primary btn-sm",
}: {
  projectId: string;
  label?: string;
  className?: string;
}) {
  const panel = useChatPanel();
  const content = (
    <>
      <IconChat size={16} />
      {label}
    </>
  );

  if (!panel?.canDock) {
    return (
      <Link to={`/projects/${encodeURIComponent(projectId)}/ask`} className={className}>
        {content}
      </Link>
    );
  }

  const open = panel.openProjectId === projectId;
  return (
    <button
      id={ASK_TOGGLE_ID}
      type="button"
      className={className}
      aria-expanded={open}
      aria-controls={open ? CHAT_PANEL_ID : undefined}
      onClick={() => (open ? document.getElementById("ask-input")?.focus() : panel.open(projectId))}
    >
      {content}
    </button>
  );
}
