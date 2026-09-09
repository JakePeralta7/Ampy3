import { useCallback, useEffect, useRef, useState } from "react";
import {
  type PipelineStatusResponse,
  type SyncDiffResponse,
  type SyncRun,
  syncsAPI,
} from "../api/syncs";

export function useSyncHistory(syncId: number) {
  const [runs, setRuns] = useState<SyncRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const selectedRunRef = useRef<number | null>(null);
  const [diff, setDiff] = useState<SyncDiffResponse | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [pipeline, setPipeline] = useState<PipelineStatusResponse | null>(null);
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [livePipeline, setLivePipeline] = useState<PipelineStatusResponse | null>(null);

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

  const fetchPipeline = useCallback(
    async (runId: number) => {
      setPipelineLoading(true);
      setPipelineError(null);
      try {
        const result = await syncsAPI.getSyncPipeline(syncId, runId);
        if (selectedRunRef.current !== runId) return;
        setPipeline(result);
      } catch {
        if (selectedRunRef.current !== runId) return;
        setPipeline(null);
        setPipelineError("Failed to load pipeline");
      } finally {
        if (selectedRunRef.current === runId) {
          setPipelineLoading(false);
        }
      }
    },
    [syncId],
  );

  const pipelineRunning = pipeline?.targets.some((t) => t.status === "running") ?? false;

  useEffect(() => {
    if (!pipelineRunning || selectedRunId === null) return;
    const timer = setInterval(() => {
      syncsAPI
        .getSyncPipeline(syncId, selectedRunId)
        .then(setPipeline)
        .catch(() => {});
    }, 2000);
    return () => clearInterval(timer);
  }, [pipelineRunning, selectedRunId, syncId]);

  const pipelineActive =
    livePipeline !== null &&
    (livePipeline.orchestrator.status === "running" ||
      livePipeline.targets.some((t) => t.status === "running"));

  useEffect(() => {
    let cancelled = false;
    let timeout: number | undefined;

    const tick = async () => {
      if (cancelled) return;
      try {
        const current = await syncsAPI.getSyncPipeline(syncId);
        if (cancelled) return;
        setLivePipeline(current);
        try {
          const history = await syncsAPI.getSyncHistory(syncId);
          if (cancelled) return;
          setRuns(history);
        } catch {
          // ignore — pipeline poll continues; list refreshes on the next tick
        }
        const active =
          current.orchestrator.status === "running" ||
          current.targets.some((t) => t.status === "running");
        timeout = window.setTimeout(tick, active ? 2000 : 10000);
      } catch {
        if (!cancelled) setLivePipeline(null);
        timeout = window.setTimeout(tick, 10000);
      }
    };

    void tick();
    return () => {
      cancelled = true;
      if (timeout) window.clearTimeout(timeout);
    };
  }, [syncId]);

  const selectRun = useCallback(
    async (run: SyncRun) => {
      if (selectedRunId === run.id) {
        setSelectedRunId(null);
        selectedRunRef.current = null;
        setDiff(null);
        setPipeline(null);
        return;
      }

      setSelectedRunId(run.id);
      selectedRunRef.current = run.id;
      setDiff(null);
      setPipeline(null);
      void fetchPipeline(run.id);

      if (run.status === "running") {
        setDiffLoading(false);
        return;
      }

      const currentIndex = runs.findIndex((r) => r.id === run.id);
      const prevRun =
        runs.slice(currentIndex + 1).find((r) => r.target_id === run.target_id) || null;

      if (!prevRun) {
        setDiff(null);
        return;
      }

      setDiffLoading(true);
      try {
        const result = await syncsAPI.getSyncDiff(syncId, prevRun.id, run.id);
        if (selectedRunRef.current !== run.id) return;
        setDiff(result);
      } catch {
        if (selectedRunRef.current !== run.id) return;
        setDiff(null);
      } finally {
        if (selectedRunRef.current === run.id) {
          setDiffLoading(false);
        }
      }
    },
    [fetchPipeline, runs, selectedRunId, syncId],
  );

  return {
    runs,
    loading,
    error,
    selectedRunId,
    diff,
    diffLoading,
    pipeline,
    pipelineLoading,
    pipelineError,
    livePipeline,
    pipelineActive,
    selectRun,
  };
}
