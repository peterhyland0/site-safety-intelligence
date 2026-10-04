import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SubCard } from "../api/types";
import { POLL_MS, useAdjudication } from "../lib/useAdjudication";
import { toProjectDetail } from "../mock/derive";
import { seedProjects } from "../mock/fixtures";

const api = vi.hoisted(() => ({ adjudicate: vi.fn() }));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, MOCK_MODE: false, api };
});

const base = (): SubCard => toProjectDetail(structuredClone(seedProjects()[0])).subs[0];
const waiting = (): SubCard => ({ ...base(), sub_id: "s1", match_status: "needs_adjudication" });
const resolved = (): SubCard => ({ ...base(), sub_id: "s1", match_status: "resolved" });

describe("useAdjudication", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("asks again while another request is resolving the sub, and refetches the page only once it's done", async () => {
    // the server answers with the card unchanged while another page or tab holds the sub, then with the result
    api.adjudicate.mockResolvedValueOnce(waiting()).mockResolvedValueOnce(waiting()).mockResolvedValueOnce(resolved());
    const applied: SubCard[] = [];
    const onDone = vi.fn();
    const cards = [waiting()];
    renderHook(() => useAdjudication("p1", cards, (c) => applied.push(c), onDone));

    await act(async () => {});
    expect(api.adjudicate).toHaveBeenCalledTimes(1);
    expect(onDone).not.toHaveBeenCalled(); // still waiting on the other request: no refetch yet

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });
    expect(api.adjudicate).toHaveBeenCalledTimes(2);
    expect(onDone).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });
    expect(api.adjudicate).toHaveBeenCalledTimes(3);
    expect(applied.at(-1)?.match_status).toBe("resolved");
    expect(onDone).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS * 5);
    });
    expect(api.adjudicate).toHaveBeenCalledTimes(3); // done: no more asking
  });

  it("stops asking when the page goes away", async () => {
    api.adjudicate.mockResolvedValue(waiting());
    const cards = [waiting()];
    const { unmount } = renderHook(() => useAdjudication("p1", cards, () => {}, () => {}));

    await act(async () => {});
    expect(api.adjudicate).toHaveBeenCalledTimes(1);
    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS * 5);
    });
    expect(api.adjudicate).toHaveBeenCalledTimes(1);
  });
});
