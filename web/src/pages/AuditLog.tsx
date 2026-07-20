import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { type AuditLogEntry, auditLogsAPI } from "../api/audit";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { type Column, DataTable } from "../components/ui/DataTable";

const EVENT_LABELS: Record<
  string,
  { label: string; variant: "success" | "danger" | "neutral" | "warning" }
> = {
  "schedule.created": { label: "Schedule Created", variant: "success" },
  "schedule.updated": { label: "Schedule Updated", variant: "neutral" },
  "schedule.deleted": { label: "Schedule Deleted", variant: "danger" },
  "sync.manually_triggered": { label: "Manual Sync", variant: "warning" },
  "sync.started": { label: "Sync Started", variant: "neutral" },
  "sync.completed": { label: "Sync Completed", variant: "success" },
  "sync.failed": { label: "Sync Failed", variant: "danger" },
  "track.rematched": { label: "Track Rematched", variant: "warning" },
  "scheduler.reloaded": { label: "Scheduler Reloaded", variant: "neutral" },
  "plex.playlist_created": { label: "Plex Playlist Created", variant: "success" },
  "plex.playlist_deleted": { label: "Plex Playlist Deleted", variant: "danger" },
  "plex.playlist_items_added": { label: "Tracks Added to Plex", variant: "success" },
  "chat.history_cleared": { label: "Chat History Cleared", variant: "danger" },
};

function formatTimestamp(ts: string): string {
  return new Date(ts).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

interface AuditLogPageProps {
  limit?: number;
}

export function AuditLogPage({ limit = 100 }: AuditLogPageProps) {
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

  const columns: Column<AuditLogEntry>[] = useMemo(
    () => [
      {
        id: "created_at",
        header: "Time",
        sortable: true,
        sortValue: (r) => r.created_at,
        cell: (r) => (
          <span className="text-fg-muted text-xs whitespace-nowrap font-mono">
            {formatTimestamp(r.created_at)}
          </span>
        ),
      },
      {
        id: "event_type",
        header: "Event",
        sortable: true,
        filterable: true,
        filterValue: (r) => EVENT_LABELS[r.event_type]?.label || r.event_type,
        sortValue: (r) => EVENT_LABELS[r.event_type]?.label || r.event_type,
        cell: (r) => {
          const info = EVENT_LABELS[r.event_type];
          return <Badge variant={info?.variant || "neutral"}>{info?.label || r.event_type}</Badge>;
        },
      },
      {
        id: "summary",
        header: "Summary",
        sortable: true,
        filterable: true,
        cell: (r) => <span className="text-fg text-sm">{r.summary}</span>,
      },
    ],
    [],
  );

  return (
    <div className="flex-1">
      <div className="max-w-7xl mx-auto p-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold mb-2 text-fg">Audit Log</h1>
            <p className="text-fg-muted">Track of all important operations in the system</p>
          </div>
          <Button onClick={fetchLogs} icon={<RefreshCw size={14} />} variant="secondary" size="sm">
            Refresh
          </Button>
        </div>

        <Card padding="none">
          <div className="p-4 pb-0">
            <DataTable columns={columns} data={logs} keyExtractor={(r) => r.id} loading={loading} />
          </div>
        </Card>

        {!loading && (
          <p className="text-xs text-fg-subtle mt-3 text-center">
            {total} total entries (showing last {Math.min(limit, total)})
          </p>
        )}
      </div>
    </div>
  );
}
