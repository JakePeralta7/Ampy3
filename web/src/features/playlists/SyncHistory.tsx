import { ChevronDown, ChevronRight, GitCompare, Loader2 } from "lucide-react";
import { Alert } from "../../components/ui/Alert";
import { Badge } from "../../components/ui/Badge";
import { LoadingSpinner } from "../../components/ui/LoadingSpinner";
import { useSyncHistory } from "../../hooks/useSyncHistory";
import { formatTimestamp } from "../../lib/utils";

interface SyncHistoryProps {
  syncId: number;
}

export function SyncHistory({ syncId }: SyncHistoryProps) {
  const { runs, loading, error, selectedRunId, diff, diffLoading, selectRun } =
    useSyncHistory(syncId);

  if (loading) {
    return <LoadingSpinner text="Loading history..." />;
  }

  if (error) {
    return <Alert>{error}</Alert>;
  }

  if (runs.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-fg-muted">No sync history yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-fg-subtle uppercase tracking-wider">
        Sync History ({runs.length} run{runs.length !== 1 ? "s" : ""})
      </div>

      <div className="space-y-1">
        {runs.map((run) => {
          const isSelected = selectedRunId === run.id;
          return (
            <div
              key={run.id}
              className="bg-bg-surface rounded-lg border border-border overflow-hidden"
            >
              <button
                onClick={() => selectRun(run)}
                disabled={run.status === "running"}
                aria-disabled={run.status === "running"}
                className="w-full flex items-center justify-between px-3 py-2.5 text-left hover:bg-bg-muted transition-colors duration-fast disabled:cursor-default"
              >
                <div className="flex items-center gap-2">
                  {run.status === "running" ? (
                    <span className="text-fg-subtle shrink-0">•</span>
                  ) : isSelected ? (
                    <ChevronDown size={12} className="text-fg-subtle shrink-0" />
                  ) : (
                    <ChevronRight size={12} className="text-fg-subtle shrink-0" />
                  )}
                  <Badge variant="neutral">{run.target_id}</Badge>
                  <span className="text-xs text-fg-muted">
                    {run.created_at ? formatTimestamp(run.created_at) : "Unknown date"}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {run.status === "running" ? (
                    <Badge variant="warning">
                      <span className="inline-flex items-center gap-1">
                        <Loader2 size={10} className="animate-spin" /> running
                      </span>
                    </Badge>
                  ) : (
                    <>
                      <Badge variant="success">{run.matched_count} matched</Badge>
                      {run.failed_count > 0 && (
                        <Badge variant="danger">{run.failed_count} failed</Badge>
                      )}
                    </>
                  )}
                </div>
              </button>

              {run.status !== "running" && isSelected && (
                <div className="border-t border-border px-3 py-3">
                  {diffLoading ? (
                    <p className="text-xs text-fg-muted">Loading diff...</p>
                  ) : diff ? (
                    <DiffView diff={diff} />
                  ) : (
                    <p className="text-xs text-fg-muted">
                      First sync run — no previous run to diff against.
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DiffView({ diff }: { diff: import("../../api/syncs").SyncDiffResponse }) {
  const hasChanges = diff.added.length > 0 || diff.removed.length > 0;

  if (!hasChanges) {
    return (
      <div className="flex items-center gap-2 text-xs text-fg-muted">
        <GitCompare size={12} />
        <span>No changes since previous run.</span>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 text-xs text-fg-muted">
        <GitCompare size={12} />
        <span>
          {diff.added.length} added, {diff.removed.length} removed, {diff.unchanged.length}{" "}
          unchanged
        </span>
      </div>

      {diff.added.length > 0 && (
        <div>
          <div className="text-xs font-medium text-success-500 mb-1">Added</div>
          <div className="space-y-0.5">
            {diff.added.map((item) => (
              <DiffTrackRow
                key={`added-${item.source_title ?? "unknown"}-${item.source_artist ?? "unknown"}`}
                item={item}
                variant="added"
              />
            ))}
          </div>
        </div>
      )}

      {diff.removed.length > 0 && (
        <div>
          <div className="text-xs font-medium text-danger-500 mb-1">Removed</div>
          <div className="space-y-0.5">
            {diff.removed.map((item) => (
              <DiffTrackRow
                key={`removed-${item.source_title ?? "unknown"}-${item.source_artist ?? "unknown"}`}
                item={item}
                variant="removed"
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function DiffTrackRow({
  item,
  variant,
}: {
  item: import("../../api/syncs").SyncDiffItem;
  variant: "added" | "removed";
}) {
  const bgClass = variant === "added" ? "bg-success-500/5" : "bg-danger-500/5";
  const borderClass = variant === "added" ? "border-success-500/20" : "border-danger-500/20";

  return (
    <div
      className={`flex items-center gap-2 px-2 py-1 rounded-sm border text-xs ${bgClass} ${borderClass}`}
    >
      <span className="text-fg truncate flex-1">{item.source_title || "Unknown"}</span>
      <span className="text-fg-muted truncate">{item.source_artist || "Unknown"}</span>
    </div>
  );
}
