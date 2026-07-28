/**
 * Hook for managing playlist tracks and details
 */

import { useCallback, useState } from "react";
import { type MatchTrackInput, type SyncTracksResponse, syncsAPI } from "../api/syncs";
import { getErrorMessage } from "../lib/utils";

export function usePlaylistDetails() {
  const [playlistDetails, setPlaylistDetails] = useState<SyncTracksResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [matchingTracks, setMatchingTracks] = useState<Set<string>>(new Set());

  const fetchPlaylistTracks = useCallback(async (syncId: number) => {
    setLoading(true);
    setError(null);
    try {
      const details = await syncsAPI.getSyncTracks(syncId);
      setPlaylistDetails(details);
    } catch (err) {
      const errorMessage = getErrorMessage(err, "Failed to load playlist tracks");
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  const pollTask = useCallback(
    async (taskId: string, syncId: number, retries = 20, delayMs = 500) => {
      for (let i = 0; i < retries; i++) {
        await new Promise((r) => setTimeout(r, delayMs));
        try {
          const status = await syncsAPI.getTaskStatus(taskId);
          if (status.ready) {
            await fetchPlaylistTracks(syncId);
            return status.result as { matched: boolean; message: string } | null;
          }
        } catch {
          break;
        }
      }
      await fetchPlaylistTracks(syncId);
      return null;
    },
    [fetchPlaylistTracks],
  );

  const matchTrack = useCallback(
    async (
      syncId: number,
      trackKey: string,
      input: MatchTrackInput,
      targetId?: string,
      sourceItemId?: string,
    ) => {
      setMatchingTracks((prev) => new Set(prev).add(trackKey));
      setError(null);
      try {
        const result = await syncsAPI.matchTrack(syncId, input, targetId, sourceItemId);
        if (result.task_id) {
          const taskResult = await pollTask(result.task_id, syncId);
          return taskResult ?? { matched: false, message: "Match completed" };
        }
        return result;
      } catch (err) {
        const errorMessage = getErrorMessage(err, "Failed to match track");
        setError(errorMessage);
        return { matched: false, message: errorMessage };
      } finally {
        setMatchingTracks((prev) => {
          const next = new Set(prev);
          next.delete(trackKey);
          return next;
        });
      }
    },
    [pollTask],
  );

  const clearPlaylistDetails = useCallback(() => {
    setPlaylistDetails(null);
    setError(null);
  }, []);

  return {
    playlistDetails,
    loading,
    error,
    matchingTracks,
    fetchPlaylistTracks,
    matchTrack,
    clearPlaylistDetails,
  };
}
