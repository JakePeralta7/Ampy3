import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { type AuditLogEntry, auditLogsAPI } from "../api/audit";
import { PageLayout } from "../components/Layout/PageLayout";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { type Column, DataTable } from "../components/ui/DataTable";
import { formatTimestamp } from "../lib/utils";

const EVENT_LABELS: Record<
  string,
  { label: string; variant: "success" | "danger" | "neutral" | "warning" }
> = {
  "schedule.created": { label: "Schedule Created", variant: "success" },
  "schedule.updated": { label: "Schedule Updated", variant: "neutral" },
  "schedule.deleted": { label: "Schedule Deleted", variant: "danger" },
  "schedule.bulk_updated": { label: "Schedules Bulk Updated", variant: "neutral" },
  "schedule.bulk_deleted": { label: "Schedules Bulk Deleted", variant: "danger" },
  "sync.manually_triggered": { label: "Manual Sync", variant: "warning" },
  "sync.bulk_triggered": { label: "Bulk Sync Triggered", variant: "warning" },
  "sync.started": { label: "Sync Started", variant: "neutral" },
  "sync.completed": { label: "Sync Completed", variant: "success" },
  "sync.failed": { label: "Sync Failed", variant: "danger" },
  "track.matched": { label: "Track Matched", variant: "warning" },
  "scheduler.reloaded": { label: "Scheduler Reloaded", variant: "neutral" },
  "plex.playlist_created": { label: "Plex Playlist Created", variant: "success" },
  "plex.playlist_deleted": { label: "Plex Playlist Deleted", variant: "danger" },
  "plex.playlist_items_added": { label: "Tracks Added to Plex", variant: "success" },
  "plex.server_saved": { label: "Plex Server Saved", variant: "success" },
  "settings.updated": { label: "Settings Updated", variant: "neutral" },
  owner_registered: { label: "Owner Registered", variant: "success" },
  login: { label: "Login", variant: "neutral" },
  login_rejected: { label: "Login Rejected", variant: "danger" },
  logout: { label: "Logout", variant: "neutral" },
  "match_rule.created": { label: "Match Rule Created", variant: "success" },
  "match_rule.updated": { label: "Match Rule Updated", variant: "neutral" },
  "match_rule.deleted": { label: "Match Rule Deleted", variant: "danger" },
  "match_rule.cloned": { label: "Match Rule Cloned", variant: "success" },
  "match_rule.reordered": { label: "Match Rules Reordered", variant: "neutral" },
};

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
    <PageLayout
      title="Audit Log"
      subtitle="Track of all important operations in the system"
      actions={
        <Button onClick={fetchLogs} icon={<RefreshCw size={14} />} variant="secondary" size="sm">
          Refresh
        </Button>
      }
    >
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
    </PageLayout>
  );
}
