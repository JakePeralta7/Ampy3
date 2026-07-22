import {
  Activity,
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Clock,
  ListMusic,
  Pause,
  Play,
  RefreshCw,
} from "lucide-react";
import { useMemo } from "react";
import { Card } from "../components/ui/Card";
import { useScheduledSyncs } from "../hooks/useScheduledSyncs";

function formatRelativeTime(iso: string | null): string {
  if (!iso) return "Never";
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

function formatNextSync(iso: string | null): string {
  if (!iso) return "N/A";
  const date = new Date(iso);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  if (diffMs < 0) return "Overdue";
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 60) return `in ${diffMin}m`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `in ${diffHr}h`;
  const diffDay = Math.floor(diffHr / 24);
  return `in ${diffDay}d`;
}

export function HomePage() {
  const { syncs, loading } = useScheduledSyncs();

  const stats = useMemo(() => {
    const active = syncs.filter((s) => s.is_active).length;
    const paused = syncs.length - active;
    const lastSynced = syncs
      .map((s) => s.last_synced_at)
      .filter((t): t is string => t !== null)
      .sort()
      .pop();
    const errored = syncs.filter((s) => s.error_message).length;
    const withErrors = syncs.filter((s) => s.error_message);
    const nextUpcoming = syncs
      .filter((s) => s.is_active && s.next_sync_at)
      .map((s) => s.next_sync_at)
      .sort()
      .find((t) => new Date(t) > new Date());
    const sources = syncs.reduce(
      (acc, s) => {
        const label = s.source === "youtube_music" ? "YouTube Music" : s.source;
        acc[label] = (acc[label] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>,
    );
    return {
      total: syncs.length,
      active,
      paused,
      errored,
      withErrors,
      lastSyncTime: formatRelativeTime(lastSynced ?? null),
      nextSyncTime: formatNextSync(nextUpcoming ?? null),
      sources,
    };
  }, [syncs]);

  return (
    <div className="flex-1">
      <div className="max-w-7xl mx-auto p-8">
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2 text-fg">Dashboard</h1>
          <p className="text-fg-muted">
            Keep your Plex playlists synced with YouTube Music and other sources
          </p>
        </div>

        {loading && syncs.length === 0 ? (
          <div className="text-fg-muted py-12 text-center">Loading...</div>
        ) : (
          <div className="space-y-6">
            {/* Primary metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card variant="bordered">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-accent-50 text-accent-700">
                    <ListMusic className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm text-fg-muted">Total Syncs</p>
                    <p className="text-2xl font-bold text-fg">{stats.total}</p>
                  </div>
                </div>
              </Card>

              <Card variant="bordered">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-success-500/10 text-success-500">
                    <Play className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm text-fg-muted">Active</p>
                    <p className="text-2xl font-bold text-fg">{stats.active}</p>
                  </div>
                </div>
              </Card>

              <Card variant="bordered">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-warn-500/10 text-warn-500">
                    <Pause className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm text-fg-muted">Paused</p>
                    <p className="text-2xl font-bold text-fg">{stats.paused}</p>
                  </div>
                </div>
              </Card>

              <Card variant="bordered">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-danger-500/10 text-danger-500">
                    <AlertTriangle className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm text-fg-muted">Errors</p>
                    <p className="text-2xl font-bold text-fg">{stats.errored}</p>
                  </div>
                </div>
              </Card>
            </div>

            {/* Secondary metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <Card variant="bordered">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-bg-muted text-fg-muted">
                    <Clock className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm text-fg-muted">Last Sync</p>
                    <p className="text-lg font-bold text-fg">{stats.lastSyncTime}</p>
                  </div>
                </div>
              </Card>

              <Card variant="bordered">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-bg-muted text-fg-muted">
                    <CalendarClock className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm text-fg-muted">Next Sync</p>
                    <p className="text-lg font-bold text-fg">{stats.nextSyncTime}</p>
                  </div>
                </div>
              </Card>

              <Card variant="bordered">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-bg-muted text-fg-muted">
                    <RefreshCw className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm text-fg-muted">Sources</p>
                    <div className="flex flex-wrap gap-1.5 mt-0.5">
                      {Object.entries(stats.sources).map(([source, count]) => (
                        <span
                          key={source}
                          className="inline-flex items-center gap-1 text-xs bg-accent-50 text-accent-700 rounded px-1.5 py-0.5"
                        >
                          {source}
                          <span className="text-accent-500">({count})</span>
                        </span>
                      ))}
                      {Object.keys(stats.sources).length === 0 && (
                        <span className="text-sm text-fg-muted">None</span>
                      )}
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            {/* Error summary */}
            {stats.withErrors.length > 0 && (
              <Card variant="bordered">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-danger-500/10 text-danger-500 mt-0.5">
                    <AlertTriangle className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-fg mb-1">Sync Errors</p>
                    <div className="space-y-1">
                      {stats.withErrors.map((s) => (
                        <div
                          key={s.id}
                          className="flex items-center gap-2 text-xs text-fg-muted"
                        >
                          <span className="font-medium text-fg">{s.target_playlist_name}</span>
                          <span className="truncate">— {s.error_message}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
