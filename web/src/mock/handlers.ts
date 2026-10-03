/**
 * In-memory mock backend for VITE_MOCK=1. Mirrors the FastAPI routes in the API contract.
 * State lives for the page session (reload resets it).
 */
import { ApiError, friendlyMessage, type HttpMethod } from "../api/client";
import type {
  Bucket,
  ChatAsk,
  ChatMessage,
  ChatSummary,
  Health,
  LoginRequest,
  ProjectCreate,
  ProjectUpdate,
  SubInput,
  User,
} from "../api/types";
import { answerQuestion as askAnswer } from "./ask";
import { matchedInspectionRows, toCard, toDetail, toInspectionDetail, toProject, toProjectDetail } from "./derive";
import { DATA_AS_OF, seedProjects } from "./fixtures";
import type { FxProject, FxSub } from "./model";

const projects: FxProject[] = seedProjects();
/** Catalogue of known companies: pasting one of these names into any project finds its record. */
const catalogue: FxSub[] = structuredClone(projects.flatMap((p) => p.subs));

/** Demo mode starts signed in; signing out shows the sign-in page, which accepts any email and password. */
const DEMO_USER: User = { user_id: "user-demo", email: "demo@example.com", name: "Demo GC" };
let signedIn = true;

type FxChat = ChatSummary & { messages: ChatMessage[] };
const chats: FxChat[] = [];
let messageSeq = 1;

let idSeq = 1;
const newId = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${idSeq++}`;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function fail(status: number, detail: string): never {
  throw new ApiError(status, friendlyMessage(status, { detail }), { detail });
}

function findProject(id: string): FxProject {
  const p = projects.find((x) => x.project_id === id);
  if (!p) fail(404, "Project not found.");
  return p;
}

function findSub(p: FxProject, subId: string): FxSub {
  const s = p.subs.find((x) => x.sub_id === subId);
  if (!s) fail(404, "Sub not found in this project.");
  return s;
}

function findChat(id: string): FxChat {
  const c = chats.find((x) => x.chat_id === id);
  if (!c) fail(404, "Chat not found");
  return c;
}

const summary = ({ messages, ...c }: FxChat): ChatSummary => ({ ...c, message_count: messages.length });

async function askInChat(chat: FxChat, body: unknown) {
  const question = ((body as ChatAsk)?.question ?? "").trim();
  if (!question) fail(422, "Question is required.");
  const p = findProject(chat.project_id);
  await sleep(900 + Math.random() * 700);
  const now = new Date().toISOString();
  const response = askAnswer(p, question);
  const added: ChatMessage[] = [
    { message_id: messageSeq++, role: "user", content: question, response: null, created_at: now },
    { message_id: messageSeq++, role: "assistant", content: response.answer, response, created_at: now },
  ];
  chat.messages.push(...added);
  chat.updated_at = now;
  return { chat: summary(chat), messages: added };
}

function allSubs(): FxSub[] {
  return projects.flatMap((p) => p.subs);
}

const normName = (s: string) =>
  s
    .toUpperCase()
    .replace(/[^A-Z0-9 ]/g, " ")
    .replace(/\b(INC|LLC|CO|CORP|COMPANY|LTD|LP)\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();

function subFromInput(row: SubInput, project: FxProject): FxSub {
  const known = catalogue.find((c) => normName(c.entered_name) === normName(row.name));
  const base: FxSub = known
    ? structuredClone(known)
    : {
        sub_id: "",
        entered_name: row.name,
        entered_city: null,
        entered_state: null,
        trade: null,
        display_name: null,
        trade_label: null,
        trade_p50: null,
        trade_p75: null,
        licence_status: null,
        needs_adjudication: false,
        adjudication: [],
        establishments: [],
        inspections: [],
        questions: [],
        injury_rates: [],
        licences: [],
        dq_warnings: [],
      };
  base.sub_id = newId("sub");
  base.entered_name = row.name;
  base.entered_city = row.city ?? null;
  base.entered_state = row.state ?? project.state ?? null;
  base.trade = row.trade ?? base.trade;
  base.questions = base.questions.map((q) => ({ ...q, question_id: newId("q") }));
  return base;
}

function csvFor(p: FxProject): string {
  const detail = toProjectDetail(p);
  const head = ["sub", "city", "state", "trade", "verdict", "top_reason", "inspections_in_window", "serious_plus_rate", "trade_median", "red_flags", "possible_inspections_not_counted"];
  const esc = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = detail.subs.map((c) =>
    [c.entered_name, c.entered_city, c.entered_state, c.trade, c.verdict_label, c.reasons[0]?.label, c.inspections_in_window, c.serious_plus_rate, c.trade_p50, c.red_flag_count, c.possible_inspections]
      .map(esc)
      .join(","),
  );
  return [head.join(","), ...lines].join("\n");
}

/** Mock-only: CSV text for the export link (the real server streams /export.csv). */
export function exportCsv(projectId: string): string {
  return csvFor(findProject(projectId));
}

type Route = {
  method: HttpMethod;
  pattern: RegExp;
  run: (m: RegExpExecArray, body: unknown, query: URLSearchParams) => Promise<unknown> | unknown;
};

const routes: Route[] = [
  {
    method: "GET",
    pattern: /^\/api\/me$/,
    run: () => (signedIn ? DEMO_USER : fail(401, "Sign in to continue.")),
  },
  {
    method: "POST",
    pattern: /^\/api\/auth\/login$/,
    run: (_m, body) => {
      const email = (body as LoginRequest)?.email?.trim();
      signedIn = true;
      return { ...DEMO_USER, email: email || DEMO_USER.email };
    },
  },
  {
    method: "POST",
    pattern: /^\/api\/auth\/logout$/,
    run: () => {
      signedIn = false;
      return undefined;
    },
  },
  {
    method: "GET",
    pattern: /^\/api\/health$/,
    run: (): Health => ({ status: "ok", data_as_of: DATA_AS_OF, build_id: "mock", llm_enabled: true, db_ok: true }),
  },
  {
    method: "GET",
    pattern: /^\/api\/projects$/,
    run: () => [...projects].sort((a, b) => b.created_at.localeCompare(a.created_at)).map(toProject),
  },
  {
    method: "POST",
    pattern: /^\/api\/projects$/,
    run: (_m, body) => {
      const b = body as ProjectCreate;
      if (!b?.name?.trim()) fail(422, "Project name is required.");
      const p: FxProject = {
        project_id: newId("proj"),
        name: b.name.trim(),
        state: b.state ?? null,
        lookback_years: b.lookback_years ?? 5,
        created_at: new Date().toISOString(),
        subs: [],
      };
      projects.push(p);
      return toProject(p);
    },
  },
  {
    method: "GET",
    pattern: /^\/api\/projects\/([^/]+)$/,
    run: (m) => toProjectDetail(findProject(decodeURIComponent(m[1]))),
  },
  {
    method: "PATCH",
    pattern: /^\/api\/projects\/([^/]+)$/,
    run: (m, body) => {
      const p = findProject(decodeURIComponent(m[1]));
      const b = body as ProjectUpdate;
      if (b.name != null) p.name = b.name;
      if (b.lookback_years != null) p.lookback_years = b.lookback_years;
      return toProject(p);
    },
  },
  {
    method: "POST",
    pattern: /^\/api\/projects\/([^/]+)\/subs$/,
    run: async (m, body) => {
      const p = findProject(decodeURIComponent(m[1]));
      const rows = (body as { rows?: SubInput[] })?.rows ?? [];
      if (!rows.length) fail(422, "No rows to add.");
      await sleep(500);
      const created = rows.map((r) => subFromInput(r, p));
      p.subs.push(...created);
      return created.map((s) => toCard(s, p.lookback_years));
    },
  },
  {
    method: "DELETE",
    pattern: /^\/api\/projects\/([^/]+)\/subs\/([^/]+)$/,
    run: (m) => {
      const p = findProject(decodeURIComponent(m[1]));
      const s = findSub(p, decodeURIComponent(m[2]));
      p.subs = p.subs.filter((x) => x !== s);
      return { ok: true };
    },
  },
  {
    method: "GET",
    pattern: /^\/api\/projects\/([^/]+)\/subs\/([^/]+)$/,
    run: (m) => {
      const p = findProject(decodeURIComponent(m[1]));
      return toDetail(findSub(p, decodeURIComponent(m[2])), p.lookback_years);
    },
  },
  {
    method: "GET",
    pattern: /^\/api\/projects\/([^/]+)\/subs\/([^/]+)\/inspections$/,
    run: (m, _b, q) => {
      const p = findProject(decodeURIComponent(m[1]));
      const s = findSub(p, decodeURIComponent(m[2]));
      const offset = Number(q.get("offset") ?? 0);
      const limit = Number(q.get("limit") ?? 20);
      return matchedInspectionRows(s).slice(offset, offset + limit);
    },
  },
  {
    method: "POST",
    pattern: /^\/api\/projects\/([^/]+)\/subs\/([^/]+)\/adjudicate$/,
    run: async (m) => {
      const p = findProject(decodeURIComponent(m[1]));
      const s = findSub(p, decodeURIComponent(m[2]));
      await sleep(2200); // the adjudicator is an LLM call per uncertain candidate
      for (const a of s.adjudication) {
        const e = s.establishments.find((x) => x.key === a.key);
        if (e) Object.assign(e, { bucket: a.bucket, method: a.method, confidence: a.confidence, rationale: a.rationale, rule_id: null });
      }
      s.needs_adjudication = false;
      return toCard(s, p.lookback_years);
    },
  },
  {
    method: "POST",
    pattern: /^\/api\/projects\/([^/]+)\/subs\/([^/]+)\/matches\/([^/]+)$/,
    run: (m, body) => {
      const p = findProject(decodeURIComponent(m[1]));
      const s = findSub(p, decodeURIComponent(m[2]));
      const key = decodeURIComponent(m[3]);
      const bucket = (body as { bucket?: Bucket })?.bucket;
      if (bucket !== "matched" && bucket !== "possible" && bucket !== "excluded") fail(422, "bucket must be matched, possible or excluded.");
      const e = s.establishments.find((x) => x.key === key);
      if (!e) fail(404, "Establishment not found for this sub.");
      const was = e.bucket;
      Object.assign(e, { bucket, method: "gc", confidence: null, rule_id: null, rationale: `Moved by the GC from ${was} to ${bucket}.` });
      s.questions = s.questions.filter((q) => !q.establishment_keys.includes(key));
      return toCard(s, p.lookback_years);
    },
  },
  {
    method: "POST",
    pattern: /^\/api\/questions\/([^/]+)\/answer$/,
    run: (m, body) => {
      const qid = decodeURIComponent(m[1]);
      const answer = (body as { answer?: string })?.answer;
      if (answer !== "yes" && answer !== "no") fail(422, "answer must be yes or no.");
      const project = projects.find((p) => p.subs.some((s) => s.questions.some((q) => q.question_id === qid)));
      const sub = project?.subs.find((s) => s.questions.some((q) => q.question_id === qid));
      if (!project || !sub) fail(404, "Question not found");
      const q = sub.questions.find((x) => x.question_id === qid)!;
      for (const key of q.establishment_keys) {
        const e = sub.establishments.find((x) => x.key === key);
        if (e)
          Object.assign(e, {
            bucket: answer === "yes" ? "matched" : "excluded",
            method: "gc",
            confidence: null,
            rule_id: null,
            rationale: answer === "yes" ? "Confirmed by the GC as the same company." : "The GC says this is a different company.",
          });
      }
      sub.questions = sub.questions.filter((x) => x !== q);
      return toCard(sub, project.lookback_years);
    },
  },
  {
    method: "GET",
    pattern: /^\/api\/inspections\/(\d+)$/,
    run: (m) => {
      const nr = Number(m[1]);
      for (const s of allSubs().concat(catalogue)) {
        const i = s.inspections.find((x) => x.nr === nr);
        if (i) return toInspectionDetail(s, i);
      }
      fail(404, "Inspection not found.");
    },
  },
  {
    method: "GET",
    pattern: /^\/api\/projects\/([^/]+)\/chats$/,
    run: (m) => {
      const p = findProject(decodeURIComponent(m[1]));
      return chats
        .filter((c) => c.project_id === p.project_id)
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
        .map(summary);
    },
  },
  {
    method: "POST",
    pattern: /^\/api\/projects\/([^/]+)\/chats$/,
    run: (m, body) => {
      const p = findProject(decodeURIComponent(m[1]));
      const question = ((body as ChatAsk)?.question ?? "").trim();
      const now = new Date().toISOString();
      const title = question.length > 80 ? `${question.slice(0, 79).replace(/\s+\S*$/, "")}…` : question;
      const chat: FxChat = { chat_id: newId("chat"), project_id: p.project_id, title, created_at: now, updated_at: now, message_count: 0, messages: [] };
      const reply = askInChat(chat, body);
      if (question) chats.push(chat);
      return reply;
    },
  },
  {
    method: "GET",
    pattern: /^\/api\/chats\/([^/]+)$/,
    run: (m) => {
      const c = findChat(decodeURIComponent(m[1]));
      return { ...summary(c), messages: c.messages };
    },
  },
  {
    method: "POST",
    pattern: /^\/api\/chats\/([^/]+)\/messages$/,
    run: (m, body) => askInChat(findChat(decodeURIComponent(m[1])), body),
  },
  {
    method: "DELETE",
    pattern: /^\/api\/chats\/([^/]+)$/,
    run: (m) => {
      const i = chats.indexOf(findChat(decodeURIComponent(m[1])));
      chats.splice(i, 1);
      return undefined;
    },
  },
];

export async function handle(method: HttpMethod, rawPath: string, body: unknown): Promise<unknown> {
  const url = new URL(rawPath, "http://mock.local");
  await sleep(120 + Math.random() * 180);
  for (const r of routes) {
    if (r.method !== method) continue;
    const m = r.pattern.exec(url.pathname);
    if (m) {
      const result = await r.run(m, body, url.searchParams);
      return structuredClone(result);
    }
  }
  fail(404, `No mock route for ${method} ${url.pathname}`);
}
