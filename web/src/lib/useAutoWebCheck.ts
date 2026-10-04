import { useEffect, useRef, useState } from "react";
import { ApiError, api, errorMessage } from "../api/client";
import type { SubCard, WebCheckResult } from "../api/types";
import { POLL_MS } from "./useAdjudication";

// A press elsewhere (the sub page, another window) holds the sub for up to ~80 s; past this many asks, it's let go.
const MAX_WAITS = 40;

/**
 * The project's automatic web check: presses POST /web-check, as the sub page's button does, for each resolved sub
 * with records left to check (card.web_unchecked), one sub at a time: a press is up to 25 web searches and about a
 * minute, and the day's searches are shared. A sub is pressed again while a press checks something and leaves some.
 * A press that checks nothing (its searches are running in another request) or fails stops that sub until the page
 * is loaded again; the day's limit stops them all. When another request holds the sub (it's being resolved, or
 * checked in another window), it's asked again shortly. onResult gets each press's result; onDone runs once the
 * presses stop, when any ran.
 */
export function useAutoWebCheck(
  projectId: string | undefined,
  cards: SubCard[] | undefined,
  enabled: boolean,
  onResult: (subId: string, result: WebCheckResult) => void,
  onDone: () => void = () => {},
) {
  const [checking, setChecking] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [limitReached, setLimitReached] = useState(false);
  const [tick, setTick] = useState(0); // a sub that waited on another request is due again
  const inFlight = useRef<string | null>(null); // the guard; `checking` is for the page
  const finished = useRef(new Set<string>());
  const paused = useRef(new Set<string>());
  const waits = useRef(new Map<string, number>());
  const timers = useRef(new Set<ReturnType<typeof setTimeout>>());
  const pressed = useRef(false); // a press ran since the last onDone
  const alive = useRef(true);
  const resultRef = useRef(onResult);
  const doneRef = useRef(onDone);
  resultRef.current = onResult;
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

  useEffect(() => {
    if (!enabled || !projectId || !cards || inFlight.current || limitReached) return;
    const next = cards.find(
      (c) =>
        c.match_status !== "needs_adjudication" &&
        (c.web_unchecked ?? 0) > 0 &&
        !finished.current.has(c.sub_id) &&
        !paused.current.has(c.sub_id),
    );
    if (!next) {
      if (pressed.current && !paused.current.size) {
        pressed.current = false;
        doneRef.current();
      }
      return;
    }
    const subId = next.sub_id;
    inFlight.current = subId;
    setChecking(subId);
    api
      .webCheck(projectId, subId)
      .then((res) => {
        if (!alive.current) return;
        pressed.current = true;
        waits.current.delete(subId);
        if (res.limit_reached) setLimitReached(true);
        if (!(res.left > 0 && (res.checked_groups > 0 || res.searched > 0))) finished.current.add(subId);
        resultRef.current(subId, res);
      })
      .catch((err) => {
        if (!alive.current) return;
        const n = (waits.current.get(subId) ?? 0) + 1;
        if (err instanceof ApiError && err.status === 409 && n <= MAX_WAITS) {
          waits.current.set(subId, n);
          paused.current.add(subId);
          const t = setTimeout(() => {
            timers.current.delete(t);
            paused.current.delete(subId);
            setTick((x) => x + 1);
          }, POLL_MS);
          timers.current.add(t);
          return;
        }
        finished.current.add(subId);
        setErrors((e) => ({ ...e, [subId]: errorMessage(err) }));
      })
      .finally(() => {
        inFlight.current = null;
        if (alive.current) setChecking(null);
      });
  }, [enabled, projectId, cards, limitReached, checking, tick]);

  return { checking, errors, limitReached };
}
