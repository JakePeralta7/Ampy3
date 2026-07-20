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

class PlaylistsAPI {
  async getPlaylistTracks(playlistId: string): Promise<PlaylistDetailsResponse> {
    return apiRequest<PlaylistDetailsResponse>(`/v1/playlists/${playlistId}/tracks`, {
      method: "GET",
    });
  }

  async getSyncTracks(syncId: number): Promise<PlaylistDetailsResponse> {
    return apiRequest<PlaylistDetailsResponse>(`/v1/playlists/by-sync/${syncId}/tracks`, {
      method: "GET",
    });
  }

  async rematchTrack(playlistId: string, input: RematchTrackInput): Promise<RematchTrackResponse> {
    return apiPost<RematchTrackResponse>(`/v1/playlists/${playlistId}/rematch-track`, input);
  }

  async rematchSyncTrack(syncId: number, input: RematchTrackInput): Promise<RematchTrackResponse> {
    return apiPost<RematchTrackResponse>(`/v1/playlists/by-sync/${syncId}/rematch-track`, input);
  }
}

export const playlistsAPI = new PlaylistsAPI();
