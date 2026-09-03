/**
 * API client for sync operations
 */

import { apiPost, apiRequest } from "../client";

export interface PlaylistTrack {
  item_id?: string;
  title: string;
  artist_name: string;
  album_name: string;
  duration: number;
  status: "matched" | "unmatched";
  match_rate?: string;
}

export interface TrackSourceInfo {
  source_id: string | null;
  item_id: string | null;
  title: string | null;
  artist_name: string | null;
  album_name: string | null;
  duration_ms: number | null;
}

export interface TrackTargetInfo {
  target_id: string;
  item_id: string;
  title: string | null;
  artist_name: string | null;
  album_name: string | null;
  duration: number | null;
}

export interface TrackDetail {
  source: TrackSourceInfo | null;
  targets: TrackTargetInfo[];
}

export interface SyncTracksResponse {
  playlist_id: string;
  source: string;
  tracks: PlaylistTrack[];
  matched_tracks: PlaylistTrack[];
  unmatched_tracks: PlaylistTrack[];
  track_details: TrackDetail[];
  total_count: number;
  matched_count: number;
  failed_count: number;
  total_source_tracks: number;
  match_rate: string;
  match_percentage: number;
}

export interface MatchTrackInput {
  title: string;
  artist_name?: string;
  album_name?: string;
}

export interface MatchTrackResponse {
  matched: boolean;
  message: string;
  track?: {
    item_id?: string;
    title?: string;
    artist_name?: string;
    album_name?: string;
  };
  task_id?: string;
}

export interface UnmatchedTrack {
  sync_id: number;
  sync_name: string;
  source_title: string | null;
  source_artist: string | null;
  source_album: string | null;
  source_duration_ms: number | null;
}

export interface SyncRun {
  id: number;
  sync_id: number;
  target_id: string;
  matched_count: number;
  failed_count: number;
  created_at: string | null;
}

export interface SyncDiffItem {
  source_title: string | null;
  source_artist: string | null;
  source_album: string | null;
  targets: TrackTargetInfo[];
}

export interface SyncDiffResponse {
  added: SyncDiffItem[];
  removed: SyncDiffItem[];
  unchanged: SyncDiffItem[];
  from_run_id: number;
  to_run_id: number;
}

export interface TargetOpenUrlResponse {
  url: string | null;
}

export const syncsAPI = {
  getSyncTracks: (syncId: number): Promise<SyncTracksResponse> =>
    apiRequest<SyncTracksResponse>(`/v1/syncs/${syncId}/tracks`, {
      method: "GET",
    }),

  matchTrack: (
    syncId: number,
    input: MatchTrackInput,
    targetId?: string,
    itemId?: string,
  ): Promise<MatchTrackResponse> => {
    const params = new URLSearchParams();
    if (targetId) params.set("target_id", targetId);
    if (itemId) params.set("item_id", itemId);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return apiPost<MatchTrackResponse>(`/v1/syncs/${syncId}/match-track${qs}`, input);
  },

  getUnmatchedTracks: (limit: number = 50): Promise<UnmatchedTrack[]> =>
    apiRequest<UnmatchedTrack[]>(`/v1/syncs/unmatched-tracks?limit=${limit}`, {
      method: "GET",
    }),

  getSyncHistory: (syncId: number): Promise<SyncRun[]> =>
    apiRequest<SyncRun[]>(`/v1/syncs/${syncId}/history`, {
      method: "GET",
    }),

  getSyncDiff: (syncId: number, fromRun: number, toRun: number): Promise<SyncDiffResponse> =>
    apiRequest<SyncDiffResponse>(`/v1/syncs/${syncId}/diff?from_run=${fromRun}&to_run=${toRun}`, {
      method: "GET",
    }),

  getTaskStatus: (
    taskId: string,
  ): Promise<{ task_id: string; status: string; ready: boolean; result: unknown }> =>
    apiRequest(`/v1/syncs/status/${taskId}`, { method: "GET" }),

  getSyncOpenUrl: (syncId: number, targetId: string): Promise<TargetOpenUrlResponse> =>
    apiRequest<TargetOpenUrlResponse>(`/v1/syncs/${syncId}/open-url?target_id=${targetId}`, {
      method: "GET",
    }),
};
