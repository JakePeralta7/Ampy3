import { Pause, Pencil, Play, RotateCw, Trash2 } from "lucide-react";
import { useMemo } from "react";
import type { ScheduledSync } from "../../api/schedules";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { CopyButton } from "../ui/CopyButton";
import { type Column, DataTable } from "../ui/DataTable";

interface SchedulesListProps {
  syncs: ScheduledSync[];
  loading: boolean;
  error?: string | null;
  onEdit: (sync: ScheduledSync) => void;
  onDelete: (sync: ScheduledSync) => void;
  onToggleActive: (sync: ScheduledSync) => void;
  onSyncNow: (sync: ScheduledSync) => void;
  onViewDetails: (sync: ScheduledSync) => void;
  refreshing?: boolean;
}

const INTERVAL_LABELS: Record<string, string> = {
  every_6h: "Every 6h",
  every_12h: "Every 12h",
  every_24h: "Every 24h",
  daily: "Daily",
  weekly: "Weekly",
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "Never";
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function SchedulesList({
  syncs,
  loading,
  error,
  onEdit,
  onDelete,
  onToggleActive,
  onSyncNow,
  onViewDetails,
  refreshing = false,
}: SchedulesListProps) {
  const columns: Column<ScheduledSync>[] = useMemo(
    () => [
      {
        id: "title",
        header: "Title",
        sortable: true,
        filterable: true,
        cell: (sync: ScheduledSync) => (
          <div className="text-fg">
            <div className="font-medium hover:text-accent-500 flex items-center gap-1.5 group">
              {sync.plex_playlist_name}
              <CopyButton value={sync.plex_playlist_name} label="playlist name" />
            </div>
          </div>
        ),
      },
      {
        id: "source",
        header: "Source",
        sortable: true,
        filterable: true,
        cell: (sync: ScheduledSync) => (
          <span className="text-fg-muted inline-flex items-center gap-1.5 group">
            <span>{sync.source === "youtube_music" ? "YouTube Music" : sync.source}</span>
            <CopyButton value={sync.source} label="source" />
          </span>
        ),
      },
      {
        id: "schedule",
        header: "Schedule",
        sortable: true,
        filterable: true,
        sortValue: (sync: ScheduledSync) =>
          INTERVAL_LABELS[sync.schedule_interval] || sync.schedule_interval,
        cell: (sync: ScheduledSync) => (
          <span className="text-fg-muted">
            {INTERVAL_LABELS[sync.schedule_interval] || sync.schedule_interval}
          </span>
        ),
      },
      {
        id: "last_sync",
        header: "Last Sync",
        sortable: true,
        sortValue: (sync: ScheduledSync) => sync.last_synced_at || "",
        cell: (sync: ScheduledSync) => (
          <span className="text-fg-muted">{formatDate(sync.last_synced_at)}</span>
        ),
      },
      {
        id: "next_sync",
        header: "Next Sync",
        sortable: true,
        sortValue: (sync: ScheduledSync) => sync.next_sync_at,
        cell: (sync: ScheduledSync) => (
          <span className="text-fg-muted">{formatDate(sync.next_sync_at)}</span>
        ),
      },
      {
        id: "status",
        header: "Status",
        sortable: true,
        filterable: true,
        sortValue: (sync: ScheduledSync) => (sync.is_active ? "Active" : "Paused"),
        cell: (sync: ScheduledSync) => (
          <div className="flex items-center gap-2">
            <Badge variant={sync.is_active ? "success" : "neutral"}>
              {sync.is_active ? "Active" : "Paused"}
            </Badge>
            {sync.error_message && (
              <span className="text-danger-500 cursor-help" title={sync.error_message}>
                ⚠️
              </span>
            )}
          </div>
        ),
      },
      {
        id: "actions",
        header: "Actions",
        cell: (sync: ScheduledSync) => (
          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
            <Button
              variant="ghost"
              size="xs"
              icon={<RotateCw size={14} />}
              onClick={() => onSyncNow(sync)}
              title="Sync now"
            />
            <Button
              variant="ghost"
              size="xs"
              icon={sync.is_active ? <Pause size={14} /> : <Play size={14} />}
              onClick={() => onToggleActive(sync)}
              title={sync.is_active ? "Pause" : "Resume"}
            />
            <Button
              variant="ghost"
              size="xs"
              icon={<Pencil size={14} />}
              onClick={() => onEdit(sync)}
              title="Edit"
            />
            <Button
              variant="ghost"
              size="xs"
              icon={<Trash2 size={14} />}
              onClick={() => onDelete(sync)}
              title="Delete"
              className="text-danger-500 hover:bg-danger-500/10"
            />
          </div>
        ),
      },
    ],
    [onEdit, onDelete, onToggleActive, onSyncNow],
  );

  if (error && syncs.length === 0) {
    return (
      <Card padding="md">
        <div className="p-3 bg-danger-500/10 text-danger-500 border border-danger-500/20 rounded-md">
          {error}
        </div>
      </Card>
    );
  }

  return (
    <Card padding="none">
      {refreshing && <div className="h-1 bg-accent-500/50 animate-pulse rounded-t" />}
      <div className="p-4 pb-0">
        <DataTable
          columns={columns}
          data={syncs}
          keyExtractor={(sync) => sync.id}
          onRowClick={onViewDetails}
          loading={loading}
        />
      </div>
    </Card>
  );
}
