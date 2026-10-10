import { useCallback, useEffect, useRef, useState } from "react";
import { type AuditLogEntry, auditLogsAPI } from "../api/audit";
import { POLLING_CONFIG } from "../lib/pollingConfig";

export interface UseAuditLogsReturn {
  logs: AuditLogEntry[];
  loading: boolean;
  total: number;
  refresh: () => Promise<void>;
  lastUpdated: Date | null;
}

export function useAuditLogs(limit = 100): UseAuditLogsReturn {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);

  const fetchLogs = useCallback(async () => {
    if (!isMountedRef.current) return;
    try {
      const resp = await auditLogsAPI.list({ limit });
      if (isMountedRef.current) {
        setLogs(resp.logs);
        setTotal(resp.total);
        setLastUpdated(new Date());
      }
    } catch {
      // handled by DataTable empty state
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [limit]);

  useEffect(() => {
    isMountedRef.current = true;

    // Initial fetch
    fetchLogs();

    // Set up polling
    pollIntervalRef.current = setInterval(() => {
      fetchLogs();
    }, POLLING_CONFIG.DEFAULT_INTERVAL);

    return () => {
      isMountedRef.current = false;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [fetchLogs]);

  return { logs, loading, total, refresh: fetchLogs, lastUpdated };
}
