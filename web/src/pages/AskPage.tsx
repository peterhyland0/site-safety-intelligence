import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useParams } from "react-router";
import { ApiError, api, errorMessage } from "../api/client";
import type { AskResponse, ChatMessage, ChatSummary } from "../api/types";
import { useApi } from "../api/useApi";
import { IconArrowLeft, IconChevronRight, IconHistory, IconInfo, IconSend, IconX } from "../components/Icons";
import { EvidenceChip } from "../components/InspectionSheet";
import { PastChatsSheet } from "../components/PastChats";
import { Loading } from "../components/ui";
import { knownProjectName, openChatId, rememberOpenChat } from "../lib/chatPanel";
import { formatWhen } from "../lib/format";
import { Markdown } from "../lib/markdown";
import { useTitle } from "../lib/useTitle";

export const SUGGESTIONS = [
  "Which subs had a fatality?",
  "Has the roofer had fall protection citations?",
  "Who has open cases?",
  "Compare everyone on serious citations",
];

type Msg =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; response: AskResponse }
  | { id: string; role: "error"; text: string; question: string };

function toMsg(m: ChatMessage): Msg {
  if (m.role === "user") return { id: `m${m.message_id}`, role: "user", text: m.content };
  const response = m.response ?? { status: "answered", answer: m.content, citations: [], coverage: null, clarify_options: [], tools_used: [] };
  return { id: `m${m.message_id}`, role: "assistant", response };
}

let seq = 0;
const tempId = () => `t${Date.now().toString(36)}${seq++}`;

export function AskPage() {
  const { projectId = "" } = useParams();
  useTitle("Foreman assistant");
  // Keyed so switching projects starts from that project's own conversation.
  return <ForemanChat key={projectId} projectId={projectId} variant="page" />;
}

/**
 * The foreman's chat. "page" is the full-screen /ask route (phones, the foreman on site); "panel" docks beside the
 * scorecard on wide screens so the GC can check answers against the data. Chats are saved on the server, one per
 * conversation; both variants reopen the chat this tab last had open on the project.
 */
export function ForemanChat({
  projectId,
  variant,
  onClose,
}: {
  projectId: string;
  variant: "page" | "panel";
  onClose?: () => void;
}) {
  const project = useApi((signal) => api.getProject(projectId, signal), [projectId]);
  const health = useApi(() => api.health(), []);
  // null: a new chat, created on the server by its first question
  const [chatId, setChatId] = useState<string | null>(() => openChatId(projectId));
  const [messages, setMessages] = useState<Msg[]>([]);
  const [loadingChat, setLoadingChat] = useState(() => openChatId(projectId) !== null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [showPast, setShowPast] = useState(false);
  const loadSeq = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  function selectChat(id: string | null) {
    setChatId(id);
    rememberOpenChat(projectId, id);
  }

  async function loadChat(id: string) {
    const n = ++loadSeq.current;
    selectChat(id);
    setMessages([]);
    setLoadError(null);
    setLoadingChat(true);
    try {
      const chat = await api.getChat(id);
      if (n === loadSeq.current) setMessages(chat.messages.map(toMsg));
    } catch (err) {
      if (n !== loadSeq.current) return;
      if (err instanceof ApiError && err.isNotFound) selectChat(null); // deleted elsewhere: start a new one
      else setLoadError(errorMessage(err));
    } finally {
      if (n === loadSeq.current) setLoadingChat(false);
    }
  }

  function newChat() {
    loadSeq.current++;
    selectChat(null);
    setMessages([]);
    setLoadError(null);
    setLoadingChat(false);
    inputRef.current?.focus();
  }

  // Reopen the chat this tab last had open on this project (the component is keyed by project).
  useEffect(() => {
    const id = openChatId(projectId);
    if (id) void loadChat(id);
    return () => {
      // eslint-disable-next-line react-hooks/exhaustive-deps
      loadSeq.current++;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, pending]);

  // Auto-grow the input up to ~5 lines.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    el.style.overflowY = el.scrollHeight > 160 ? "auto" : "hidden";
  }, [input]);

  async function send(question: string) {
    const q = question.trim();
    if (!q || pending || loadingChat) return;
    const temp = tempId();
    setMessages((m) => [...m, { id: temp, role: "user", text: q }]);
    setInput("");
    setPending(true);
    try {
      // the server adds the chat's earlier messages as context; the browser sends only the question
      const reply = chatId ? await api.sendMessage(chatId, { question: q }) : await api.createChat(projectId, { question: q });
      selectChat(reply.chat.chat_id);
      setMessages((m) => [...m.filter((x) => x.id !== temp), ...reply.messages.map(toMsg)]);
    } catch (err) {
      const gone = chatId !== null && err instanceof ApiError && err.isNotFound;
      if (gone) selectChat(null); // deleted in another tab: trying again starts a new chat
      const text = gone ? "This chat was deleted, so that question wasn't saved. Try again to start a new chat with it." : errorMessage(err);
      setMessages((m) => [...m, { id: tempId(), role: "error", text, question: q }]);
    } finally {
      setPending(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(input);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send(input);
    }
  }

  const scorecardHref = `/projects/${encodeURIComponent(projectId)}`;
  const projectName = project.data?.project.name ?? knownProjectName(projectId);
  const llmOff = health.data && !health.data.llm_enabled;
  const Heading = variant === "page" ? "h1" : "h2";
  const empty = messages.length === 0 && !loadingChat && !loadError;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-2 border-b border-line px-4 py-2">
        {variant === "page" ? (
          <Link to={scorecardHref} className="btn btn-ghost btn-sm -ml-2 px-2" aria-label="Back to scorecard">
            <IconArrowLeft size={20} />
          </Link>
        ) : null}
        <div className="min-w-0 flex-1">
          <Heading className="text-base leading-tight font-extrabold tracking-[-0.02em] text-ink">Foreman assistant</Heading>
          <p className="truncate text-xs text-muted">{projectName ?? (project.error ? "Project unavailable" : "Loading project…")}</p>
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-sm px-2"
          onClick={() => setShowPast(true)}
          disabled={pending}
          aria-label="Past chats"
          title="Past chats"
        >
          <IconHistory size={20} />
        </button>
        {chatId || messages.length ? (
          <button type="button" className="btn btn-ghost btn-sm" onClick={newChat} disabled={pending}>
            New chat
          </button>
        ) : null}
        {onClose ? (
          <button type="button" className="btn btn-ghost btn-sm -mr-2 px-2" onClick={onClose} aria-label="Close the foreman assistant">
            <IconX size={20} />
          </button>
        ) : null}
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {llmOff ? (
          <p className="mb-4 flex gap-2 rounded-xl border border-line bg-surface p-3 text-sm text-ink-2">
            <IconInfo size={16} className="mt-0.5 shrink-0" />
            The assistant's AI is switched off on this deployment, so questions can't be answered here. The scorecard and sub
            pages still have every figure.
          </p>
        ) : null}

        {loadingChat ? <Loading label="Opening your chat…" /> : null}

        {loadError ? (
          <div role="alert" className="mx-auto max-w-xl rounded-xl border border-high-line bg-high-bg p-4 text-sm text-ink">
            <p className="font-medium">Couldn't open this chat.</p>
            <p className="text-ink-2">{loadError}</p>
            <div className="mt-3 flex gap-2">
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => chatId && void loadChat(chatId)}>
                Try again
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={newChat}>
                Start a new chat
              </button>
            </div>
          </div>
        ) : null}

        {empty ? (
          <div className="mx-auto max-w-xl py-4">
            <p className="text-lg font-semibold text-ink">Ask about the subs on this job</p>
            <p className="mt-1 text-ink-2">
              Answers come only from OSHA records for this project's subs, with links to every inspection cited.
            </p>
            <ul className="mt-4 space-y-2" aria-label="Suggested questions">
              {SUGGESTIONS.map((s) => (
                <li key={s}>
                  <button
                    type="button"
                    className="card flex min-h-12 w-full items-center px-4 py-3 text-left text-[16px] text-ink hover:border-accent hover:bg-accent-soft"
                    onClick={() => void send(s)}
                    disabled={pending}
                  >
                    {s}
                  </button>
                </li>
              ))}
            </ul>
            <RecentChats projectId={projectId} onOpen={(id) => void loadChat(id)} onShowAll={() => setShowPast(true)} />
          </div>
        ) : null}

        <ol className="mx-auto max-w-2xl space-y-4" role="log" aria-live="polite" aria-relevant="additions" aria-label="Conversation">
          {messages.map((m) => (
            <li key={m.id}>
              {m.role === "user" ? (
                <UserBubble text={m.text} />
              ) : m.role === "assistant" ? (
                <AssistantBubble response={m.response} projectId={projectId} onSend={send} disabled={pending} />
              ) : (
                <div className="max-w-[90%] rounded-2xl rounded-bl-md border border-high-line bg-high-bg px-4 py-3 text-[15px] text-ink">
                  <p>{m.text}</p>
                  <button type="button" className="btn btn-secondary btn-sm mt-2" onClick={() => void send(m.question)} disabled={pending}>
                    Try again
                  </button>
                </div>
              )}
            </li>
          ))}
          {pending ? (
            <li>
              <div role="status" className="inline-flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-line bg-surface px-4 py-3">
                <span className="sr-only">Assistant is checking the records…</span>
                <span aria-hidden="true" className="typing-dot h-2 w-2 rounded-full bg-muted" />
                <span aria-hidden="true" className="typing-dot h-2 w-2 rounded-full bg-muted" />
                <span aria-hidden="true" className="typing-dot h-2 w-2 rounded-full bg-muted" />
              </div>
            </li>
          ) : null}
        </ol>
      </div>

      <div className="border-t border-line bg-page px-4 pt-2 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        {messages.length > 0 ? (
          <div className="no-scrollbar -mx-4 mb-2 overflow-x-auto px-4">
            <ul className="flex gap-2" aria-label="Suggested questions">
              {SUGGESTIONS.map((s) => (
                <li key={s}>
                  <button
                    type="button"
                    className="pill min-h-9 border-transparent bg-surface px-3.5 text-sm whitespace-nowrap text-ink-2 shadow-[var(--shadow-card)] hover:bg-accent-soft hover:text-ink"
                    onClick={() => void send(s)}
                    disabled={pending}
                  >
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <form onSubmit={onSubmit} className="mx-auto flex max-w-2xl items-end gap-2">
          <label htmlFor="ask-input" className="sr-only">
            Your question
          </label>
          <textarea
            id="ask-input"
            ref={inputRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask about a sub's safety record…"
            className="field min-h-12 flex-1 resize-none py-3 text-[17px] leading-6"
            enterKeyHint="send"
            autoComplete="off"
            autoFocus={variant === "panel"}
            maxLength={500}
          />
          <button
            type="submit"
            className="btn btn-primary h-12 w-12 shrink-0 px-0"
            disabled={pending || loadingChat || !input.trim()}
            aria-label="Send question"
          >
            <IconSend size={20} />
          </button>
        </form>
      </div>

      {showPast ? (
        <PastChatsSheet
          projectId={projectId}
          currentChatId={chatId}
          onOpen={(id) => {
            setShowPast(false);
            if (id !== chatId || loadError) void loadChat(id);
          }}
          onDeleted={(id) => id === chatId && newChat()}
          onClose={() => setShowPast(false)}
        />
      ) : null}
    </div>
  );
}

/** The three most recent chats on the project, under the suggestions of an empty chat. */
function RecentChats({
  projectId,
  onOpen,
  onShowAll,
}: {
  projectId: string;
  onOpen: (chatId: string) => void;
  onShowAll: () => void;
}) {
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const labelId = useId();

  useEffect(() => {
    const ctrl = new AbortController();
    // optional: an empty chat works without it, so a failed load just shows nothing
    api.listChats(projectId, ctrl.signal).then(setChats, () => {});
    return () => ctrl.abort();
  }, [projectId]);

  if (!chats.length) return null;
  return (
    <div className="mt-6">
      <div className="flex items-baseline justify-between gap-2">
        <p id={labelId} className="eyebrow">
          Pick up a past chat
        </p>
        {chats.length > 3 ? (
          <button type="button" className="link text-sm" onClick={onShowAll}>
            All {chats.length} chats
          </button>
        ) : null}
      </div>
      <ul className="mt-2 space-y-2" aria-labelledby={labelId}>
        {chats.slice(0, 3).map((c) => (
          <li key={c.chat_id}>
            <button
              type="button"
              className="card flex min-h-12 w-full items-center gap-2 px-4 py-3 text-left hover:border-accent hover:bg-accent-soft"
              onClick={() => onOpen(c.chat_id)}
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] text-ink">{c.title}</span>
                <span className="block text-xs text-muted">{formatWhen(c.updated_at)}</span>
              </span>
              <IconChevronRight size={16} className="shrink-0 text-muted" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] rounded-2xl rounded-br-md bg-bubble px-4 py-2.5 text-[16px] whitespace-pre-wrap text-bubble-ink">
        <span className="sr-only">You: </span>
        {text}
      </p>
    </div>
  );
}

const STATUS_COPY: Partial<Record<AskResponse["status"], string>> = {
  unanswerable: "That's outside what I can answer from these records.",
  guard_failed: "I couldn't verify that answer against the records, so I'm not showing it. Try asking more specifically, or check the scorecard.",
  no_api_key: "The assistant isn't switched on for this deployment (no AI key is configured). The scorecard and sub pages still show everything.",
  needs_confirmation: "A match question needs your answer first, because it could change this answer.",
};

function AssistantBubble({
  response: r,
  projectId,
  onSend,
  disabled,
}: {
  response: AskResponse;
  projectId: string;
  onSend: (q: string) => void;
  disabled: boolean;
}) {
  const muted = r.status === "unanswerable" || r.status === "guard_failed" || r.status === "no_api_key";
  // no_api_key carries the server's own explanation (no key, or today's budget used up) when it sends one.
  const copy = r.status === "no_api_key" ? r.answer.trim() || STATUS_COPY.no_api_key : STATUS_COPY[r.status];
  return (
    <div className="max-w-[95%] sm:max-w-[85%]">
      <div
        className={`rounded-2xl rounded-bl-md border px-4 py-3 text-[16px] leading-relaxed ${
          muted ? "border-line-strong bg-surface text-ink-2" : "border-line bg-surface text-ink"
        }`}
      >
        <span className="sr-only">Assistant: </span>
        {copy ? (
          <p className="mb-2 flex gap-2 text-[15px] font-medium text-ink">
            <IconInfo size={18} className="mt-0.5 shrink-0 text-muted" />
            <span>{copy}</span>
          </p>
        ) : null}
        {r.answer && r.status !== "no_api_key" ? <Markdown text={r.answer} /> : null}

        {r.status === "clarify" && r.clarify_options.length ? (
          <div className="mt-3 flex flex-col gap-2" role="group" aria-label="Which sub do you mean?">
            {r.clarify_options.map((o) => (
              <button
                key={o.sub_id}
                type="button"
                className="btn btn-secondary justify-start text-left"
                onClick={() => onSend(`I mean ${o.name}`)}
                disabled={disabled}
              >
                I mean {o.name}
              </button>
            ))}
          </div>
        ) : null}

        {r.status === "needs_confirmation" && r.clarify_options.length ? (
          <ul className="mt-3 space-y-2">
            {r.clarify_options.map((o) => (
              <li key={o.sub_id}>
                <Link
                  to={`/projects/${encodeURIComponent(projectId)}/subs/${encodeURIComponent(o.sub_id)}#questions`}
                  className="btn btn-primary btn-sm"
                >
                  Answer the match question for {o.name}
                </Link>
              </li>
            ))}
          </ul>
        ) : null}

        {r.status === "no_api_key" || r.status === "guard_failed" ? (
          <p className="mt-2">
            <Link to={`/projects/${encodeURIComponent(projectId)}`} className="link text-[15px]">
              Open the scorecard
            </Link>
          </p>
        ) : null}

        {r.citations.length ? (
          <div className="mt-3">
            <p className="mb-1 text-xs text-muted">Inspections cited (osha.gov)</p>
            <div className="flex flex-wrap gap-1.5">
              {r.citations.map((c) => (
                <EvidenceChip key={c.activity_nr} activityNr={c.activity_nr} />
              ))}
            </div>
          </div>
        ) : null}
      </div>
      {r.coverage ? <p className="mt-1 px-1 text-xs leading-snug text-muted">{r.coverage}</p> : null}
    </div>
  );
}
