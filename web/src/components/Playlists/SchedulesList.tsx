import { Pause, Pencil, Play, RotateCw, Trash2 } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import type { ScheduledSync } from "../../api/schedules";
import { getSourceLabel } from "../../lib/constants";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { ConfirmDialog } from "../ui/ConfirmDialog";
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
  onBulkSyncNow: (ids: number[]) => Promise<void>;
  onBulkToggleActive: (ids: number[], isActive: boolean) => Promise<void>;
  onBulkDelete: (ids: number[]) => Promise<void>;
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
  onBulkSyncNow,
  onBulkToggleActive,
  onBulkDelete,
  refreshing = false,
}: SchedulesListProps) {
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkDeleteConfirm, setBulkDeleteConfirm] = useState(false);

  const toggleOne = useCallback((id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectedSyncs = useMemo(
    () => syncs.filter((s) => selectedIds.has(s.id)),
    [syncs, selectedIds],
  );
  const anyActive = selectedSyncs.some((s) => s.is_active);
  const anyPaused = selectedSyncs.some((s) => !s.is_active);

  const handleBulkSyncNow = async () => {
    const ids = Array.from(selectedIds);
    setSelectedIds(new Set());
    await onBulkSyncNow(ids);
  };

  const handleBulkToggleActive = async () => {
    const ids = Array.from(selectedIds);
    setSelectedIds(new Set());
    await onBulkToggleActive(ids, !anyActive);
  };

  const handleBulkDelete = async () => {
    const ids = Array.from(selectedIds);
    setSelectedIds(new Set());
    setBulkDeleteConfirm(false);
    await onBulkDelete(ids);
  };

  const columns: Column<ScheduledSync>[] = useMemo(
    () => [
      {
        id: "select",
        header: "",
        className: "w-10",
        headerClassName: "w-10",
        cell: (sync: ScheduledSync) => (
          <input
            type="checkbox"
            checked={selectedIds.has(sync.id)}
            onChange={() => toggleOne(sync.id)}
            onClick={(e) => e.stopPropagation()}
            className="h-4 w-4 rounded border-border text-accent-500 focus:ring-accent-500 bg-bg-surface cursor-pointer"
          />
        ),
      },
      {
        id: "title",
        header: "Title",
        sortable: true,
        filterable: true,
        sortValue: (sync: ScheduledSync) => sync.target_playlist_name,
        filterValue: (sync: ScheduledSync) => sync.target_playlist_name,
        cell: (sync: ScheduledSync) => (
          <div className="text-fg">
            <div className="font-medium hover:text-accent-500 flex items-center gap-1.5 group">
              {sync.target_playlist_name}
              <CopyButton value={sync.target_playlist_name} label="playlist name" />
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
            <span>{getSourceLabel(sync.source)}</span>
            <CopyButton value={sync.source} label="source" />
          </span>
        ),
      },
      {
        id: "target",
        header: "Target",
        sortable: true,
        filterable: true,
        sortValue: (sync: ScheduledSync) => sync.target_ids.join(", "),
        cell: (sync: ScheduledSync) => (
          <span className="text-fg-muted inline-flex items-center gap-1.5 group">
            <span className="inline-flex gap-1">
              {sync.target_ids.map((tid) => (
                <Badge key={tid} variant="neutral">
                  {tid}
                </Badge>
              ))}
            </span>
            <CopyButton value={sync.target_ids.join(", ")} label="targets" />
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
    [onEdit, onDelete, onToggleActive, onSyncNow, selectedIds, toggleOne],
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
    <div className="relative">
      <Card padding="none">
        {refreshing && <div className="h-1 bg-accent-500/50 animate-pulse rounded-t" />}

        {selectedIds.size > 0 && (
          <div className="flex items-center gap-3 px-4 py-2.5 bg-accent-500/10 border-b border-accent-500/20">
            <span className="text-sm font-medium text-accent-500">{selectedIds.size} selected</span>
            <div className="flex items-center gap-1.5">
              <Button
                variant="ghost"
                size="xs"
                icon={<RotateCw size={14} />}
                onClick={handleBulkSyncNow}
              >
                Sync Now
              </Button>
              {anyActive && (
                <Button
                  variant="ghost"
                  size="xs"
                  icon={<Pause size={14} />}
                  onClick={handleBulkToggleActive}
                >
                  Pause
                </Button>
              )}
              {anyPaused && (
                <Button
                  variant="ghost"
                  size="xs"
                  icon={<Play size={14} />}
                  onClick={handleBulkToggleActive}
                >
                  Resume
                </Button>
              )}
              <Button
                variant="ghost"
                size="xs"
                icon={<Trash2 size={14} />}
                onClick={() => setBulkDeleteConfirm(true)}
                className="text-danger-500 hover:bg-danger-500/10"
              >
                Delete
              </Button>
            </div>
            <button
              onClick={() => setSelectedIds(new Set())}
              className="ml-auto text-xs text-fg-muted hover:text-fg"
            >
              Clear selection
            </button>
          </div>
        )}

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

      <ConfirmDialog
        open={bulkDeleteConfirm}
        onCancel={() => setBulkDeleteConfirm(false)}
        onConfirm={handleBulkDelete}
        title="Delete Schedules"
        message={`Are you sure you want to delete ${selectedIds.size} schedule(s)? This will also delete their playlist tracks and history.`}
        confirmLabel="Delete All"
        variant="danger"
      />
    </div>
  );
}
