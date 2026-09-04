import {
  AlertTriangle,
  CalendarClock,
  Clock,
  ListMusic,
  Pause,
  Play,
  RefreshCw,
} from "lucide-react";
import { useMemo } from "react";
import { PageLayout } from "../components/layout/PageLayout";
import { Card } from "../components/ui/Card";
import { StatCard } from "../components/ui/StatCard";
import { useScheduledSyncs } from "../hooks/useScheduledSyncs";
import { getSourceLabel } from "../lib/constants";
import { formatNextSync, formatRelativeTime } from "../lib/utils";

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
      .find((t) => t !== null && new Date(t) > new Date());
    const sources = syncs.reduce(
      (acc, s) => {
        const label = getSourceLabel(s.source);
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
    <PageLayout
      title="Dashboard"
      subtitle="Keep your target playlists synced with YouTube Music and other sources"
    >
      {loading && syncs.length === 0 ? (
        <div className="text-fg-muted py-12 text-center">Loading...</div>
      ) : (
        <div className="space-y-6">
          {/* Primary metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card variant="bordered">
              <StatCard
                icon={<ListMusic className="h-5 w-5" />}
                iconClassName="bg-accent-50 text-accent-700"
                label="Total Syncs"
              >
                {stats.total}
              </StatCard>
            </Card>

            <Card variant="bordered">
              <StatCard
                icon={<Play className="h-5 w-5" />}
                iconClassName="bg-success-500/10 text-success-500"
                label="Active"
              >
                {stats.active}
              </StatCard>
            </Card>

            <Card variant="bordered">
              <StatCard
                icon={<Pause className="h-5 w-5" />}
                iconClassName="bg-warning-50/10 text-warning-700"
                label="Paused"
              >
                {stats.paused}
              </StatCard>
            </Card>

            <Card variant="bordered">
              <StatCard
                icon={<AlertTriangle className="h-5 w-5" />}
                iconClassName="bg-danger-500/10 text-danger-500"
                label="Errors"
              >
                {stats.errored}
              </StatCard>
            </Card>
          </div>

          {/* Secondary metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <Card variant="bordered">
              <StatCard
                icon={<Clock className="h-5 w-5" />}
                label="Last Sync"
                valueClassName="text-lg font-bold text-fg"
              >
                {stats.lastSyncTime}
              </StatCard>
            </Card>

            <Card variant="bordered">
              <StatCard
                icon={<CalendarClock className="h-5 w-5" />}
                label="Next Sync"
                valueClassName="text-lg font-bold text-fg"
              >
                {stats.nextSyncTime}
              </StatCard>
            </Card>

            <Card variant="bordered">
              <StatCard
                icon={<RefreshCw className="h-5 w-5" />}
                label="Sources"
                valueClassName="text-lg font-bold text-fg"
              >
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
              </StatCard>
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
                      <div key={s.id} className="flex items-center gap-2 text-xs text-fg-muted">
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
    </PageLayout>
  );
}
