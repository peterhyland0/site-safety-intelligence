import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage, isSubCard } from "../api/client";
import type { SubCard } from "../api/types";

const CONCURRENCY = 4;

/**
 * Runs POST /adjudicate once for every card whose match_status is "needs_adjudication".
 * Calls are queued (max 4 at a time: each is AI calls server-side, and a new sub's company is looked up on the web
 * first, so a call can take ~30 s). When the server
 * returns the refreshed SubCard it is applied immediately; once the queue drains, onDone()
 * lets the page refetch so ordering and summary counts are right.
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
  const [errors, setErrors] = useState<Record<string, string>>({});
  const applyRef = useRef(applyCard);
  const doneRef = useRef(onDone);
  applyRef.current = applyCard;
  doneRef.current = onDone;

  const pump = useCallback(() => {
    if (!projectId) return;
    while (running.current < CONCURRENCY && queue.current.length) {
      const subId = queue.current.shift()!;
      running.current++;
      api
        .adjudicate(projectId, subId)
        .then((res) => {
          if (isSubCard(res)) applyRef.current(res);
        })
        .catch((err) => {
          setErrors((e) => ({ ...e, [subId]: errorMessage(err) }));
        })
        .finally(() => {
          running.current--;
          if (running.current === 0 && queue.current.length === 0) doneRef.current();
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
      queue.current.push(subId);
      pump();
    },
    [pump],
  );

  return { errors, retry };
}
