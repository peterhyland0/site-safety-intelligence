import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useParams } from "react-router";
import { api, errorMessage } from "../api/client";
import type { AskResponse, ChatTurn } from "../api/types";
import { useApi } from "../api/useApi";
import { IconArrowLeft, IconInfo, IconSend, IconX } from "../components/Icons";
import { EvidenceChip } from "../components/InspectionSheet";
import { knownProjectName } from "../lib/chatPanel";
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

const MAX_HISTORY_TURNS = 12;
const storageKey = (projectId: string) => `ssi-chat-${projectId}`;

function loadMessages(projectId: string): Msg[] {
  try {
    const raw = sessionStorage.getItem(storageKey(projectId));
    return raw ? (JSON.parse(raw) as Msg[]) : [];
  } catch {
    return [];
  }
}

function saveMessages(projectId: string, msgs: Msg[]) {
  try {
    sessionStorage.setItem(storageKey(projectId), JSON.stringify(msgs.slice(-60)));
  } catch {
    /* storage unavailable: conversation just won't survive a reload */
  }
}

let seq = 0;
const newId = () => `m${Date.now().toString(36)}${seq++}`;

export function AskPage() {
  const { projectId = "" } = useParams();
  useTitle("Foreman assistant");
  // Keyed so switching projects starts from that project's own conversation.
  return <ForemanChat key={projectId} projectId={projectId} variant="page" />;
}

/**
 * The foreman's chat. "page" is the full-screen /ask route (phones, the foreman on site); "panel" docks beside the
 * scorecard on wide screens so the GC can check answers against the data. Both read and write the same conversation.
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
  const [messages, setMessages] = useState<Msg[]>(() => loadMessages(projectId));
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => saveMessages(projectId, messages), [projectId, messages]);

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

  function historyFrom(msgs: Msg[]): ChatTurn[] {
    const turns: ChatTurn[] = [];
    for (const m of msgs) {
      if (m.role === "user") turns.push({ role: "user", content: m.text });
      else if (m.role === "assistant") turns.push({ role: "assistant", content: m.response.answer });
    }
    return turns.slice(-MAX_HISTORY_TURNS);
  }

  async function send(question: string) {
    const q = question.trim();
    if (!q || pending) return;
    const history = historyFrom(messages);
    setMessages((m) => [...m, { id: newId(), role: "user", text: q }]);
    setInput("");
    setPending(true);
    try {
      const response = await api.ask(projectId, { question: q, history });
      setMessages((m) => [...m, { id: newId(), role: "assistant", response }]);
    } catch (err) {
      setMessages((m) => [...m, { id: newId(), role: "error", text: errorMessage(err), question: q }]);
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
        {messages.length ? (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setMessages([]);
              inputRef.current?.focus();
            }}
          >
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

        {messages.length === 0 ? (
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
            disabled={pending || !input.trim()}
            aria-label="Send question"
          >
            <IconSend size={20} />
          </button>
        </form>
      </div>
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
