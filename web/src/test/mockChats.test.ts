import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatDetail, ChatReply, ChatSummary, User } from "../api/types";
import { handle } from "../mock/handlers";

// The demo backend (VITE_MOCK=1) mirrors the chat and sign-in routes, so the deployed-without-API demo works too.
describe("Mock backend: sign-in and chats", () => {
  beforeEach(() => {
    vi.spyOn(Math, "random").mockReturnValue(0); // shortest simulated latency
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts signed in, and signing out makes /api/me a 401 until signing in again", async () => {
    expect(((await handle("GET", "/api/me", undefined)) as User).email).toBe("demo@example.com");
    await handle("POST", "/api/auth/logout", undefined);
    await expect(handle("GET", "/api/me", undefined)).rejects.toMatchObject({ status: 401 });
    await handle("POST", "/api/auth/login", { email: "pat@example.com", password: "x" });
    expect(((await handle("GET", "/api/me", undefined)) as User).email).toBe("demo@example.com");
  });

  it("creates, lists, continues and deletes a chat", async () => {
    const created = (await handle("POST", "/api/projects/demo-riverside/chats", {
      question: "Which subs had a fatality?",
    })) as ChatReply;
    expect(created.chat.title).toBe("Which subs had a fatality?");
    expect(created.messages.map((m) => m.role)).toEqual(["user", "assistant"]);
    expect(created.messages[1].response?.status).toBe("answered");

    const id = created.chat.chat_id;
    const next = (await handle("POST", `/api/chats/${id}/messages`, { question: "Who has open cases?" })) as ChatReply;
    expect(next.chat.message_count).toBe(4);

    const listed = (await handle("GET", "/api/projects/demo-riverside/chats", undefined)) as ChatSummary[];
    expect(listed[0]).toMatchObject({ chat_id: id, message_count: 4 });
    expect(((await handle("GET", `/api/chats/${id}`, undefined)) as ChatDetail).messages).toHaveLength(4);

    await handle("DELETE", `/api/chats/${id}`, undefined);
    await expect(handle("GET", `/api/chats/${id}`, undefined)).rejects.toMatchObject({ status: 404 });
    await expect(handle("POST", "/api/projects/demo-riverside/chats", { question: "  " })).rejects.toMatchObject({ status: 422 });
    expect((await handle("GET", "/api/projects/demo-riverside/chats", undefined)) as ChatSummary[]).toEqual([]);
  });
});
