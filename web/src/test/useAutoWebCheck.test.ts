import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import type { SubCard, WebCheckResult } from "../api/types";
import { POLL_MS } from "../lib/useAdjudication";
import { useAutoWebCheck } from "../lib/useAutoWebCheck";
import { toProjectDetail } from "../mock/derive";
import { seedProjects } from "../mock/fixtures";

const api = vi.hoisted(() => ({ webCheck: vi.fn() }));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, MOCK_MODE: false, api };
});

const base = (): SubCard => toProjectDetail(structuredClone(seedProjects()[0])).subs[0];
const card = (sub_id: string, over: Partial<SubCard> = {}): SubCard => ({
  ...base(),
  sub_id,
  match_status: "resolved",
  web_unchecked: 3,
  ...over,
});
const result = (sub_id: string, over: Partial<WebCheckResult> = {}): WebCheckResult => ({
  card: card(sub_id, { web_unchecked: 0 }),
  searched: 3,
  checked_groups: 3,
  same: 1,
  different: 1,
  unsure: 1,
  left: 0,
  limit_reached: false,
  questions: 0,
  matched: 1,
  excluded: 1,
  ...over,
});

describe("useAutoWebCheck", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("checks each resolved sub with records left, one at a time, and refetches once they're done", async () => {
    api.webCheck.mockImplementation(async (_p: string, subId: string) => result(subId));
    const onResult = vi.fn();
    const onDone = vi.fn();
    const cards = [
      card("waiting", { match_status: "needs_adjudication" }), // still being resolved: not yet
      card("none", { web_unchecked: 0 }), // nothing to check
      card("a"),
      card("b"),
    ];
    const { result: hook } = renderHook(() => useAutoWebCheck("p1", cards, true, onResult, onDone));
    expect(hook.current.checking).toBe("a");
    await act(async () => {});
    await act(async () => {});
    expect(api.webCheck.mock.calls.map((c) => c[1])).toEqual(["a", "b"]);
    expect(onResult.mock.calls.map((c) => c[0])).toEqual(["a", "b"]);
    expect(onDone).toHaveBeenCalledTimes(1);
    expect(hook.current.checking).toBeNull();
  });

  it("does nothing while it's off", async () => {
    renderHook(() => useAutoWebCheck("p1", [card("a")], false, vi.fn()));
    await act(async () => {});
    expect(api.webCheck).not.toHaveBeenCalled();
  });

  it("presses again while a press makes progress and leaves records, and stops when one checks nothing", async () => {
    api.webCheck
      .mockResolvedValueOnce(result("a", { left: 30 }))
      .mockResolvedValueOnce(result("a", { left: 5, searched: 0, checked_groups: 0 })); // searching elsewhere
    const cards = [card("a", { web_unchecked: 40 })];
    renderHook(() => useAutoWebCheck("p1", cards, true, vi.fn()));
    await act(async () => {});
    await act(async () => {});
    await act(async () => {});
    expect(api.webCheck).toHaveBeenCalledTimes(2);
  });

  it("stops every sub at the day's limit", async () => {
    api.webCheck.mockResolvedValueOnce(result("a", { left: 30, limit_reached: true }));
    const { result: hook } = renderHook(() => useAutoWebCheck("p1", [card("a"), card("b")], true, vi.fn()));
    await act(async () => {});
    await act(async () => {});
    expect(api.webCheck).toHaveBeenCalledTimes(1);
    expect(hook.current.limitReached).toBe(true);
  });

  it("waits while another request holds the sub, and reports a failure on the sub", async () => {
    api.webCheck
      .mockRejectedValueOnce(new ApiError(409, "This sub's records are being resolved right now."))
      .mockRejectedValueOnce(new ApiError(503, "The web check isn't set up on this server."))
      .mockResolvedValueOnce(result("a"));
    const { result: hook } = renderHook(() => useAutoWebCheck("p1", [card("a"), card("b")], true, vi.fn()));
    await act(async () => {});
    expect(api.webCheck.mock.calls.map((c) => c[1])).toEqual(["a", "b"]); // b goes while a waits
    await act(async () => {});
    expect(hook.current.errors.b).toMatch(/isn't set up/);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });
    expect(api.webCheck.mock.calls.map((c) => c[1])).toEqual(["a", "b", "a"]);
    expect(hook.current.errors.a).toBeUndefined();
  });
});
