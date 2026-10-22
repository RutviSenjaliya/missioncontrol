import { useCallback, useEffect, useRef, useState } from "react";

/** Load data; keep re-polling while `shouldPoll(data)` returns true (used for live mission timelines). */
export function usePoll<T>(load: () => Promise<T>, deps: unknown[], shouldPoll?: (d: T) => boolean, intervalMs = 900) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const loadRef = useRef(load);
  loadRef.current = load;
  const pollRef = useRef(shouldPoll);
  pollRef.current = shouldPoll;

  const refresh = useCallback(async () => {
    try {
      const d = await loadRef.current();
      setData(d);
      setError(null);
      return d;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let alive = true;
    let timer: number | undefined;
    setLoading(true);
    const tick = async () => {
      const d = await refresh();
      if (alive && d && pollRef.current?.(d)) timer = window.setTimeout(tick, intervalMs);
    };
    tick();
    return () => { alive = false; window.clearTimeout(timer); };
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, error, loading, refresh };
}
