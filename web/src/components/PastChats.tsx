import { useEffect, useId, useRef, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { ChatSummary } from "../api/types";
import { formatWhen, plural } from "../lib/format";
import { IconChevronRight, IconSpinner, IconTrash } from "./Icons";
import { InlineError } from "./ui";

const questions = (c: ChatSummary) => plural(Math.ceil(c.message_count / 2), "question");

/** The signed-in user's chats on this project, most recent first: open one, or delete it (asks first). */
export function PastChatsSheet({
  projectId,
  currentChatId,
  onOpen,
  onDeleted,
  onClose,
}: {
  projectId: string;
  currentChatId: string | null;
  onOpen: (chatId: string) => void;
  onDeleted: (chatId: string) => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });
  const [chats, setChats] = useState<ChatSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    // Esc and close() both fire "close"; the browser returns focus to the button that opened the sheet. The event
    // is queued, and in dev StrictMode's effect re-run closes and reopens the dialog, so a "close" can arrive while
    // it's open again: only a dialog that is still closed counts.
    const closed = () => !d.open && onCloseRef.current();
    d.addEventListener("close", closed);
    if (typeof d.showModal === "function") d.showModal();
    else d.setAttribute("open", ""); // jsdom
    return () => {
      d.removeEventListener("close", closed);
      if (d.open && typeof d.close === "function") d.close();
    };
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    api.listChats(projectId, ctrl.signal).then(setChats, (err) => !ctrl.signal.aborted && setError(errorMessage(err)));
    return () => ctrl.abort();
  }, [projectId]);

  function close() {
    const d = ref.current;
    if (d && typeof d.close === "function" && d.open) d.close();
    else onCloseRef.current();
  }

  async function remove(chatId: string) {
    setDeleting(chatId);
    setError(null);
    try {
      await api.deleteChat(chatId);
      setChats((cs) => (cs ?? []).filter((c) => c.chat_id !== chatId));
      onDeleted(chatId);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setDeleting(null);
      setConfirming(null);
    }
  }

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClick={(e) => e.target === e.currentTarget && close()} // a tap on the backdrop closes
      className="mx-0 mt-auto mb-0 max-h-[85dvh] w-full max-w-full overflow-hidden rounded-t-2xl border border-line bg-surface p-0 text-ink backdrop:bg-black/50 sm:m-auto sm:max-w-lg sm:rounded-2xl"
    >
      <div className="flex max-h-[calc(85dvh-2px)] flex-col">
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <h2 id={titleId} className="section-title">
            Past chats
          </h2>
          <button type="button" className="btn btn-ghost btn-sm shrink-0" onClick={close}>
            Close
          </button>
        </div>
        <div className="overflow-y-auto px-2 py-2">
          <div className="px-2">
            <InlineError message={error} />
          </div>
          {chats === null ? (
            error ? null : (
              <p role="status" className="flex items-center gap-2 px-2 py-3 text-sm text-muted">
                <IconSpinner size={16} /> Loading your chats…
              </p>
            )
          ) : chats.length === 0 ? (
            <p className="px-2 py-3 text-sm text-muted">No past chats on this project yet. Your questions are saved here.</p>
          ) : (
            <ul className="divide-y divide-line">
              {chats.map((c) => (
                <li key={c.chat_id} className="flex items-center gap-1 py-1">
                  {confirming === c.chat_id ? (
                    <div className="flex min-h-14 flex-1 flex-wrap items-center gap-2 px-2">
                      <p className="min-w-0 flex-1 text-sm text-ink">
                        Delete <span className="font-semibold">“{c.title}”</span>? This can't be undone.
                      </p>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => void remove(c.chat_id)}
                        disabled={deleting === c.chat_id}
                      >
                        {deleting === c.chat_id ? "Deleting…" : "Delete"}
                      </button>
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setConfirming(null)}>
                        Keep
                      </button>
                    </div>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="flex min-h-14 min-w-0 flex-1 items-center gap-2 rounded-xl px-2 py-2 text-left hover:bg-surface-2"
                        onClick={() => onOpen(c.chat_id)}
                        aria-current={c.chat_id === currentChatId ? "true" : undefined}
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium text-ink">{c.title}</span>
                          <span className="block text-xs text-muted">
                            {formatWhen(c.updated_at)} · {questions(c)}
                            {c.chat_id === currentChatId ? " · open now" : ""}
                          </span>
                        </span>
                        <IconChevronRight size={16} className="shrink-0 text-muted" />
                      </button>
                      <button
                        type="button"
                        className="grid min-h-11 min-w-11 place-items-center rounded-full text-muted hover:bg-surface-2 hover:text-ink"
                        onClick={() => setConfirming(c.chat_id)}
                        aria-label={`Delete chat: ${c.title}`}
                      >
                        <IconTrash size={16} />
                      </button>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </dialog>
  );
}
