/**
 * Typed fetch wrapper for the FastAPI backend (same origin, relative /api URLs).
 *
 * With VITE_MOCK=1 every call is answered by the in-memory fixtures in src/mock/ instead,
 * so the UI can be developed and demoed without the backend.
 */
import type {
  AskRequest,
  AskResponse,
  Bucket,
  Health,
  InspectionDetail,
  InspectionRow,
  Project,
  ProjectCreate,
  ProjectDetail,
  ProjectUpdate,
  SubCard,
  SubDetail,
  SubInput,
} from "./types";

export const MOCK_MODE = import.meta.env.VITE_MOCK === "1";

export type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE";

/** Error with a message that is safe to show to the user as-is. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }

  get isAuth(): boolean {
    return this.status === 401 || this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

/** Pull a readable message out of a FastAPI error body ({detail: string | [{msg}]}). */
function detailMessage(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d && typeof d === "object" ? (d as { msg?: unknown }).msg : null))
      .filter((m): m is string => typeof m === "string");
    if (msgs.length) return msgs.join("; ");
  }
  return null;
}

export function friendlyMessage(status: number, body?: unknown): string {
  if (status === 401 || status === 403) {
    return "Access required. This deployment is password-protected: reload the page and sign in, then try again.";
  }
  if (status === 404) return detailMessage(body) ?? "Not found. It may have been removed.";
  if (status === 409) return detailMessage(body) ?? "That conflicts with a change someone else just made. Refresh and try again.";
  if (status === 422 || status === 400) {
    const msg = detailMessage(body);
    return msg ? `Please check the input: ${msg}` : "Please check the input and try again.";
  }
  if (status === 429) return "Too many requests right now. Wait a moment and try again.";
  if (status === 503) return "The service is starting up or temporarily unavailable. Try again in a moment.";
  if (status >= 500) return `The server had a problem (${status}). Try again in a moment.`;
  return detailMessage(body) ?? `Request failed (${status}).`;
}

/** Turn anything thrown by a request into a user-facing message. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error && err.name === "AbortError") return "Request cancelled.";
  return "Can't reach the server. Check your connection and try again.";
}

type MockHandler = (method: HttpMethod, path: string, body: unknown) => Promise<unknown>;
let mockHandler: MockHandler | null = null;

async function getMockHandler(): Promise<MockHandler> {
  if (!mockHandler) {
    const mod = await import("../mock/handlers");
    mockHandler = mod.handle;
  }
  return mockHandler;
}

export async function request<T>(
  method: HttpMethod,
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  if (MOCK_MODE) {
    const handle = await getMockHandler();
    return (await handle(method, path, body)) as T;
  }

  let res: Response;
  try {
    res = await fetch(path, {
      method,
      signal,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") throw err;
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let parsed: unknown = undefined;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!res.ok) throw new ApiError(res.status, friendlyMessage(res.status, parsed), parsed);
  return parsed as T;
}

const enc = encodeURIComponent;

/** Defensive check before applying a mutation response to the scorecard in place. */
export function isSubCard(x: unknown): x is SubCard {
  return !!x && typeof x === "object" && "sub_id" in x && "verdict" in x;
}

export const api = {
  health: () => request<Health>("GET", "/api/health"),

  listProjects: () => request<Project[]>("GET", "/api/projects"),
  createProject: (body: ProjectCreate) => request<Project>("POST", "/api/projects", body),
  getProject: (projectId: string, signal?: AbortSignal) =>
    request<ProjectDetail>("GET", `/api/projects/${enc(projectId)}`, undefined, signal),
  /** Returns the updated Project; callers refetch the detail because the lookback re-scores every card. */
  updateProject: (projectId: string, body: ProjectUpdate) =>
    request<Project>("PATCH", `/api/projects/${enc(projectId)}`, body),

  addSubs: (projectId: string, rows: SubInput[]) =>
    request<SubCard[]>("POST", `/api/projects/${enc(projectId)}/subs`, { rows }),
  deleteSub: (projectId: string, subId: string) =>
    request<{ ok: boolean }>("DELETE", `/api/projects/${enc(projectId)}/subs/${enc(subId)}`),
  getSub: (projectId: string, subId: string, signal?: AbortSignal) =>
    request<SubDetail>("GET", `/api/projects/${enc(projectId)}/subs/${enc(subId)}`, undefined, signal),
  getInspections: (projectId: string, subId: string, offset: number, limit: number) =>
    request<InspectionRow[]>(
      "GET",
      `/api/projects/${enc(projectId)}/subs/${enc(subId)}/inspections?offset=${offset}&limit=${limit}`,
    ),
  /** Runs the LLM adjudicator on the sub's uncertain candidates; returns the re-scored SubCard. */
  adjudicate: (projectId: string, subId: string) =>
    request<SubCard>("POST", `/api/projects/${enc(projectId)}/subs/${enc(subId)}/adjudicate`),
  /** GC moves an establishment between buckets; returns the re-scored SubCard. */
  overrideMatch: (projectId: string, subId: string, establishmentKey: string, bucket: Bucket) =>
    request<SubCard>(
      "POST",
      `/api/projects/${enc(projectId)}/subs/${enc(subId)}/matches/${enc(establishmentKey)}`,
      { bucket },
    ),
  /** Yes/no on a match question; returns the re-scored SubCard of the sub it belongs to. */
  answerQuestion: (questionId: string, answer: "yes" | "no") =>
    request<SubCard>("POST", `/api/questions/${enc(questionId)}/answer`, { answer }),

  getInspection: (activityNr: number) =>
    request<InspectionDetail>("GET", `/api/inspections/${activityNr}`),

  ask: (projectId: string, body: AskRequest) =>
    request<AskResponse>("POST", `/api/projects/${enc(projectId)}/ask`, body),

  exportCsvUrl: (projectId: string) => `/api/projects/${enc(projectId)}/export.csv`,
};
