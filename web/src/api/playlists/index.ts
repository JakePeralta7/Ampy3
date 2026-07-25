/**
 * API client for Plex playlist operations
 */

import { apiPost, apiRequest } from "../client";

export interface PlaylistTrack {
  plex_id?: string;
  title: string;
  artist_name: string;
  album_name: string;
  duration: number;
  status: "matched" | "unmatched";
  match_rate?: string;
}

export interface TrackSourceInfo {
  title: string | null;
  artist_name: string | null;
  album_name: string | null;
  duration_ms: number | null;
  source_id: string | null;
}

export interface TrackMatchInfo {
  plex_id: string;
  title: string;
  artist_name: string;
  album_name: string;
  duration: number;
}

export interface TrackDetail {
  source: TrackSourceInfo | null;
  match: TrackMatchInfo | null;
}

export interface PlaylistDetailsResponse {
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

export interface RematchTrackInput {
  title: string;
  artist_name?: string;
  album_name?: string;
}

export interface RematchTrackResponse {
  matched: boolean;
  message: string;
  track?: {
    plex_id?: string;
    title?: string;
    artist_name?: string;
    album_name?: string;
  };
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
  matched_count: number;
  failed_count: number;
  created_at: string | null;
}

export interface SyncDiffItem {
  source_title: string | null;
  source_artist: string | null;
  source_album: string | null;
  match_item_id: string | null;
  match_title: string | null;
  match_artist: string | null;
}

export interface SyncDiffResponse {
  added: SyncDiffItem[];
  removed: SyncDiffItem[];
  unchanged: SyncDiffItem[];
  from_run_id: number;
  to_run_id: number;
}

export const playlistsAPI = {
  getPlaylistTracks: (playlistId: string): Promise<PlaylistDetailsResponse> =>
    apiRequest<PlaylistDetailsResponse>(`/v1/playlists/${playlistId}/tracks`, {
      method: "GET",
    }),

  getSyncTracks: (syncId: number): Promise<PlaylistDetailsResponse> =>
    apiRequest<PlaylistDetailsResponse>(`/v1/playlists/by-sync/${syncId}/tracks`, {
      method: "GET",
    }),

  rematchTrack: (playlistId: string, input: RematchTrackInput): Promise<RematchTrackResponse> =>
    apiPost<RematchTrackResponse>(`/v1/playlists/${playlistId}/rematch-track`, input),

  rematchSyncTrack: (syncId: number, input: RematchTrackInput): Promise<RematchTrackResponse> =>
    apiPost<RematchTrackResponse>(`/v1/playlists/by-sync/${syncId}/rematch-track`, input),

  getUnmatchedTracks: (limit: number = 50): Promise<UnmatchedTrack[]> =>
    apiRequest<UnmatchedTrack[]>(`/v1/playlists/unmatched-tracks?limit=${limit}`, {
      method: "GET",
    }),

  getSyncHistory: (syncId: number): Promise<SyncRun[]> =>
    apiRequest<SyncRun[]>(`/v1/playlists/by-sync/${syncId}/history`, {
      method: "GET",
    }),

  getSyncDiff: (syncId: number, fromRun: number, toRun: number): Promise<SyncDiffResponse> =>
    apiRequest<SyncDiffResponse>(
      `/v1/playlists/by-sync/${syncId}/diff?from_run=${fromRun}&to_run=${toRun}`,
      { method: "GET" },
    ),
};
