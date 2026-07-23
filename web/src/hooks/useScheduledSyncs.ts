/**
 * Hook for managing scheduled playlist syncs
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  type CreateScheduledSyncInput,
  type ScheduledSync,
  scheduledSyncsAPI,
  type UpdateScheduledSyncInput,
} from "../api/schedules";
import { getErrorMessage } from "../lib/utils";

interface UseScheduledSyncsReturn {
  syncs: ScheduledSync[];
  loading: boolean;
  error: string | null;
  refreshing: boolean;
  refetch: () => Promise<void>;
  createSync: (input: CreateScheduledSyncInput) => Promise<ScheduledSync>;
  updateSync: (syncId: number, input: UpdateScheduledSyncInput) => Promise<ScheduledSync>;
  deleteSync: (syncId: number) => Promise<void>;
  triggerSyncNow: (syncId: number) => Promise<string>;
  bulkSyncNow: (ids: number[]) => Promise<void>;
  bulkToggleActive: (ids: number[], isActive: boolean) => Promise<void>;
  bulkDelete: (ids: number[]) => Promise<void>;
}

const POLL_INTERVAL_MS = 30000;

export function useScheduledSyncs(): UseScheduledSyncsReturn {
  const [syncs, setSyncs] = useState<ScheduledSync[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const fastPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopFastPoll = useCallback(() => {
    if (fastPollRef.current) {
      clearInterval(fastPollRef.current);
      fastPollRef.current = null;
      setRefreshing(false);
    }
  }, []);

  // Fetch syncs
  const refetch = useCallback(async (isBackground = false) => {
    if (isBackground) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    try {
      const data = await scheduledSyncsAPI.listScheduledSyncs();
      setSyncs(data);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load syncs"));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Create sync
  const createSync = useCallback(
    async (input: CreateScheduledSyncInput): Promise<ScheduledSync> => {
      try {
        const newSync = await scheduledSyncsAPI.createScheduledSync(input);
        setSyncs((prev) => [newSync, ...prev]);
        return newSync;
      } catch (err) {
        setError(getErrorMessage(err, "Failed to create sync"));
        throw err;
      }
    },
    [],
  );

  // Update sync
  const updateSync = useCallback(
    async (syncId: number, input: UpdateScheduledSyncInput): Promise<ScheduledSync> => {
      try {
        const updated = await scheduledSyncsAPI.updateScheduledSync(syncId, input);
        setSyncs((prev) => prev.map((s) => (s.id === syncId ? updated : s)));
        return updated;
      } catch (err) {
        setError(getErrorMessage(err, "Failed to update sync"));
        throw err;
      }
    },
    [],
  );

  // Delete sync
  const deleteSync = useCallback(async (syncId: number): Promise<void> => {
    try {
      await scheduledSyncsAPI.deleteScheduledSync(syncId);
      setSyncs((prev) => prev.filter((s) => s.id !== syncId));
    } catch (err) {
      setError(getErrorMessage(err, "Failed to delete sync"));
      throw err;
    }
  }, []);

  // Trigger immediate sync
  const triggerSyncNow = useCallback(
    async (syncId: number): Promise<string> => {
      try {
        const result = await scheduledSyncsAPI.triggerSyncNow(syncId);
        const syncBefore = syncs.find((s) => s.id === syncId);
        const lastSyncedBefore = syncBefore?.last_synced_at ?? null;

        stopFastPoll();
        setRefreshing(true);

        fastPollRef.current = setInterval(async () => {
          try {
            const data = await scheduledSyncsAPI.listScheduledSyncs();
            setSyncs(data);
            const updated = data.find((s) => s.id === syncId);
            if (updated && updated.last_synced_at !== lastSyncedBefore) {
              stopFastPoll();
            }
          } catch {
            stopFastPoll();
          }
        }, 3000);

        // Auto-stop fast poll after 60 seconds
        setTimeout(() => stopFastPoll(), 60000);

        return result.task_id;
      } catch (err) {
        setError(getErrorMessage(err, "Failed to trigger sync"));
        throw err;
      }
    },
    [syncs, stopFastPoll],
  );

  // Bulk: trigger sync now for multiple syncs
  const bulkSyncNow = useCallback(
    async (ids: number[]): Promise<void> => {
      try {
        await scheduledSyncsAPI.bulkSyncNow(ids);
        await refetch(true);
      } catch (err) {
        setError(getErrorMessage(err, "Failed to trigger bulk sync"));
        throw err;
      }
    },
    [refetch],
  );

  // Bulk: toggle active state for multiple syncs
  const bulkToggleActive = useCallback(
    async (ids: number[], isActive: boolean): Promise<void> => {
      try {
        await scheduledSyncsAPI.bulkToggleActive(ids, isActive);
        setSyncs((prev) =>
          prev.map((s) => (ids.includes(s.id) ? { ...s, is_active: isActive } : s)),
        );
      } catch (err) {
        setError(getErrorMessage(err, "Failed to toggle syncs"));
        throw err;
      }
    },
    [],
  );

  // Bulk: delete multiple syncs
  const bulkDelete = useCallback(
    async (ids: number[]): Promise<void> => {
      try {
        await scheduledSyncsAPI.bulkDelete(ids);
        setSyncs((prev) => prev.filter((s) => !ids.includes(s.id)));
      } catch (err) {
        setError(getErrorMessage(err, "Failed to delete syncs"));
        throw err;
      }
    },
    [],
  );

  // Initial fetch
  useEffect(() => {
    refetch();
  }, [refetch]);

  // Set up polling
  useEffect(() => {
    const interval = setInterval(() => refetch(true), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refetch]);

  // Cleanup fast poll on unmount
  useEffect(() => {
    return () => stopFastPoll();
  }, [stopFastPoll]);

  return {
    syncs,
    loading,
    error,
    refreshing,
    refetch,
    createSync,
    updateSync,
    deleteSync,
    triggerSyncNow,
    bulkSyncNow,
    bulkToggleActive,
    bulkDelete,
  };
}
