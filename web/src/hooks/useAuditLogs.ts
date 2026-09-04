import { useCallback, useEffect, useState } from "react";
import { type AuditLogEntry, auditLogsAPI } from "../api/audit";

export function useAuditLogs(limit = 100) {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await auditLogsAPI.list({ limit });
      setLogs(resp.logs);
      setTotal(resp.total);
    } catch {
      // handled by DataTable empty state
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  return { logs, loading, total, refresh: fetchLogs };
}
