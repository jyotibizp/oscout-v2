import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

/** Fetch + optional polling. `deps` change -> refetch. */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[] = [], pollMs?: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const { autoRefresh, tick } = useRefresh();

  const load = useCallback(async () => {
    try {
      const d = await fnRef.current();
      setData(d);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  useEffect(() => {
    if (!pollMs || !autoRefresh) return;
    const id = setInterval(load, pollMs);
    return () => clearInterval(id);
  }, [pollMs, autoRefresh, load]);

  return { data, error, loading, reload: load, setData };
}

/** App-wide auto-refresh switch + a "tick" to force reloads (e.g. after SCAN NOW). */
export const RefreshContext = createContext<{ autoRefresh: boolean; setAutoRefresh: (v: boolean) => void; tick: number; bump: () => void }>({
  autoRefresh: true,
  setAutoRefresh: () => {},
  tick: 0,
  bump: () => {},
});
export const useRefresh = () => useContext(RefreshContext);
