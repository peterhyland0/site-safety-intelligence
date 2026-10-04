import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage, isSubCard } from "../api/client";
import type { SubCard } from "../api/types";

const CONCURRENCY = 4;
// One request at a time resolves a sub on the server. When another page or tab is already at it, the server returns
// the card unchanged (still "needs_adjudication") and the sub is asked about again after a pause, until that request
// finishes. A dead request's claim lapses after 15 minutes, so the asking stops a little after that.
export const POLL_MS = 4000;
const MAX_POLLS = 250;

/**
 * Runs POST /adjudicate once for every card whose match_status is "needs_adjudication".
 * Calls are queued (max 4 at a time: each is AI calls server-side, and a new sub's company is looked up on the web
 * first, so a call can take ~30 s). When the server
 * returns the refreshed SubCard it is applied immediately; once the queue drains and no sub is waiting on another
 * request, onDone() lets the page refetch so ordering and summary counts are right.
 */
export function useAdjudication(
  projectId: string | undefined,
  cards: SubCard[] | undefined,
  applyCard: (card: SubCard) => void,
  onDone: () => void,
) {
  const started = useRef(new Set<string>());
  const queue = useRef<string[]>([]);
  const running = useRef(0);
  const polls = useRef(new Map<string, number>());
  const timers = useRef(new Set<ReturnType<typeof setTimeout>>());
  const alive = useRef(true);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const applyRef = useRef(applyCard);
  const doneRef = useRef(onDone);
  applyRef.current = applyCard;
  doneRef.current = onDone;

  useEffect(() => {
    alive.current = true;
    const pending = timers.current;
    return () => {
      alive.current = false;
      for (const t of pending) clearTimeout(t);
      pending.clear();
    };
  }, []);

  const pump = useCallback(() => {
    if (!projectId || !alive.current) return;
    while (running.current < CONCURRENCY && queue.current.length) {
      const subId = queue.current.shift()!;
      running.current++;
      api
        .adjudicate(projectId, subId)
        .then((res) => {
          if (!isSubCard(res)) return;
          applyRef.current(res);
          if (res.match_status !== "needs_adjudication" || !alive.current) {
            polls.current.delete(subId);
            return;
          }
          // another request is resolving this sub: ask again shortly
          const n = (polls.current.get(subId) ?? 0) + 1;
          if (n > MAX_POLLS) {
            setErrors((e) => ({ ...e, [subId]: "It's still being resolved in another window." }));
            return;
          }
          polls.current.set(subId, n);
          const t = setTimeout(() => {
            timers.current.delete(t);
            queue.current.push(subId);
            pump();
          }, POLL_MS);
          timers.current.add(t);
        })
        .catch((err) => {
          setErrors((e) => ({ ...e, [subId]: errorMessage(err) }));
        })
        .finally(() => {
          running.current--;
          if (running.current === 0 && queue.current.length === 0 && timers.current.size === 0) doneRef.current();
          pump();
        });
    }
  }, [projectId]);

  useEffect(() => {
    if (!cards) return;
    for (const c of cards) {
      if (c.match_status === "needs_adjudication" && !started.current.has(c.sub_id)) {
        started.current.add(c.sub_id);
        queue.current.push(c.sub_id);
      }
    }
    pump();
  }, [cards, pump]);

  const retry = useCallback(
    (subId: string) => {
      setErrors(({ [subId]: _drop, ...rest }) => rest);
      polls.current.delete(subId);
      queue.current.push(subId);
      pump();
    },
    [pump],
  );

  return { errors, retry };
}
