/**
 * Base hook for polling data with consistent patterns
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { POLLING_CONFIG } from "../lib/pollingConfig";

export interface PolledDataReturn<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  refetch: () => Promise<void>;
  isRefreshing: boolean;
}

export interface UsePolledDataOptions<T = unknown> {
  interval?: number;
  enabled?: boolean;
  onError?: (error: Error) => void;
  initialData?: T;
}

/**
 * Base hook for polling data at regular intervals.
 *
 * Usage:
 * ```tsx
 * const { data, loading, error, lastUpdated, refetch } = usePolledData(
 *   async () => {
 *     const response = await fetch('/api/data');
 *     return response.json();
 *   },
 *   { interval: 30000 }
 * );
 * ```
 *
 * @param fetcher - Async function that fetches the data
 * @param options - Configuration options
 * @returns Current data state with metadata
 */
export function usePolledData<T>(
  fetcher: () => Promise<T>,
  options: UsePolledDataOptions = {},
): PolledDataReturn<T> {
  const {
    interval = POLLING_CONFIG.DEFAULT_INTERVAL,
    enabled = true,
    onError,
    initialData,
  } = options;

  const [data, setData] = useState<T | null>((initialData as T) ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);

  const refetch = useCallback(async () => {
    if (!isMountedRef.current) return;
    setIsRefreshing(true);
    setError(null);

    try {
      const result = await fetcher();
      if (isMountedRef.current) {
        setData(result);
        setLastUpdated(new Date());
      }
    } catch (err) {
      if (isMountedRef.current) {
        const errorMsg = err instanceof Error ? err.message : "Failed to fetch data";
        setError(errorMsg);
        onError?.(err instanceof Error ? err : new Error(errorMsg));
      }
    } finally {
      if (isMountedRef.current) {
        setIsRefreshing(false);
      }
    }
  }, [fetcher, onError]);

  // Initial fetch and polling setup
  useEffect(() => {
    isMountedRef.current = true;

    if (!enabled) {
      return;
    }

    // Initial fetch
    (async () => {
      setLoading(true);
      await refetch();
      setLoading(false);
    })();

    // Set up polling
    pollIntervalRef.current = setInterval(() => {
      refetch();
    }, interval);

    return () => {
      isMountedRef.current = false;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [enabled, interval, refetch]);

  return {
    data,
    loading,
    error,
    lastUpdated,
    refetch,
    isRefreshing,
  };
}
