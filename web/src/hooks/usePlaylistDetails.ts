/**
 * Hook for managing playlist tracks and details
 */

import { useCallback, useState } from "react";
import {
  type PlaylistDetailsResponse,
  playlistsAPI,
  type RematchTrackInput,
} from "../api/playlists";
import { getErrorMessage } from "../lib/utils";

export function usePlaylistDetails() {
  const [playlistDetails, setPlaylistDetails] = useState<PlaylistDetailsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rematchingTracks, setRematchingTracks] = useState<Set<string>>(new Set());

  const fetchPlaylistTracks = useCallback(async (syncId: number) => {
    setLoading(true);
    setError(null);
    try {
      const details = await playlistsAPI.getSyncTracks(syncId);
      setPlaylistDetails(details);
    } catch (err) {
      const errorMessage = getErrorMessage(err, "Failed to load playlist tracks");
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  const rematchTrack = useCallback(
    async (syncId: number, trackKey: string, input: RematchTrackInput) => {
      setRematchingTracks((prev) => new Set(prev).add(trackKey));
      setError(null);
      try {
        const result = await playlistsAPI.rematchSyncTrack(syncId, input);
        if (result.matched) {
          await fetchPlaylistTracks(syncId);
        }
        return result;
      } catch (err) {
        const errorMessage = getErrorMessage(err, "Failed to rematch track");
        setError(errorMessage);
        return { matched: false, message: errorMessage };
      } finally {
        setRematchingTracks((prev) => {
          const next = new Set(prev);
          next.delete(trackKey);
          return next;
        });
      }
    },
    [fetchPlaylistTracks],
  );

  const clearPlaylistDetails = useCallback(() => {
    setPlaylistDetails(null);
    setError(null);
  }, []);

  return {
    playlistDetails,
    loading,
    error,
    rematchingTracks,
    fetchPlaylistTracks,
    rematchTrack,
    clearPlaylistDetails,
  };
}
