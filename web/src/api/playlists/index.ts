/**
 * API client for playlist browsing operations (Plex/Jellyfin)
 */

import { apiGet } from "../client";

export interface PlaylistSearchResponse {
  message: string;
  playlists: unknown[];
}

export const playlistsAPI = {
  listPlaylists: (targetId: string = "Plex"): Promise<unknown[]> =>
    apiGet<unknown[]>(`/v1/playlists/?target_id=${targetId}`),

  searchPlaylists: (query: string, targetId: string = "Plex"): Promise<PlaylistSearchResponse> =>
    apiGet<PlaylistSearchResponse>(
      `/v1/playlists/search?query=${encodeURIComponent(query)}&target_id=${targetId}`,
    ),
};
