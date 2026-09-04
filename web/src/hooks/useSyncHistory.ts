import { useCallback, useEffect, useState } from "react";
import { type SyncDiffResponse, type SyncRun, syncsAPI } from "../api/syncs";

export function useSyncHistory(syncId: number) {
  const [runs, setRuns] = useState<SyncRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [diff, setDiff] = useState<SyncDiffResponse | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    syncsAPI
      .getSyncHistory(syncId)
      .then((data) => {
        if (!cancelled) setRuns(data);
      })
      .catch(() => {
        if (!cancelled) setError("Failed to load sync history");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [syncId]);

  const selectRun = useCallback(
    async (run: SyncRun) => {
      if (selectedRunId === run.id) {
        setSelectedRunId(null);
        setDiff(null);
        return;
      }

      if (run.status === "running") {
        setSelectedRunId(run.id);
        setDiff(null);
        setDiffLoading(false);
        return;
      }

      const currentIndex = runs.findIndex((r) => r.id === run.id);
      const prevRun =
        runs.slice(currentIndex + 1).find((r) => r.target_id === run.target_id) || null;

      if (!prevRun) {
        setSelectedRunId(run.id);
        setDiff(null);
        return;
      }

      setSelectedRunId(run.id);
      setDiffLoading(true);
      try {
        const result = await syncsAPI.getSyncDiff(syncId, prevRun.id, run.id);
        setDiff(result);
      } catch {
        setDiff(null);
      } finally {
        setDiffLoading(false);
      }
    },
    [runs, selectedRunId, syncId],
  );

  return { runs, loading, error, selectedRunId, diff, diffLoading, selectRun };
}
