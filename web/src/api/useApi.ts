import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "./client";

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  /** True for the first load only; reloads keep the previous data on screen. */
  loading: boolean;
  /** True while a background reload is in flight. */
  refreshing: boolean;
  reload: () => Promise<void>;
  setData: (updater: (prev: T | null) => T | null) => void;
  /** HTTP status of the last error, if any (401 → access required). */
  errorStatus: number | null;
}

/**
 * Minimal data-fetching hook: load on mount / when deps change, keep previous data during
 * reloads (no skeleton flash), ignore responses from stale requests.
 */
export function useApi<T>(fetcher: (signal: AbortSignal) => Promise<T>, deps: unknown[]): ApiState<T> {
  const [data, setDataState] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const seq = useRef(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const run = useCallback(async (initial: boolean) => {
    const id = ++seq.current;
    const ctrl = new AbortController();
    if (initial) setLoading(true);
    else setRefreshing(true);
    try {
      const result = await fetcherRef.current(ctrl.signal);
      if (id !== seq.current) return;
      setDataState(result);
      setError(null);
      setErrorStatus(null);
    } catch (err) {
      if (id !== seq.current) return;
      setError(errorMessage(err));
      setErrorStatus(err && typeof err === "object" && "status" in err ? Number((err as { status: unknown }).status) : null);
    } finally {
      if (id === seq.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    setDataState(null);
    void run(true);
    return () => {
      // Invalidate in-flight requests from the previous deps (intentionally reads the live ref).
      // eslint-disable-next-line react-hooks/exhaustive-deps
      seq.current++;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const reload = useCallback(() => run(false), [run]);
  const setData = useCallback((updater: (prev: T | null) => T | null) => setDataState(updater), []);

  return { data, error, loading, refreshing, reload, setData, errorStatus };
}
