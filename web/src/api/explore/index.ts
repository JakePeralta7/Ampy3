import { apiGet } from "../client";

export interface ExploreItemOut {
  id: string;
  title: string;
  subtitle: string;
  item_type: "album" | "playlist" | "artist" | "song" | "video";
  thumbnail_url: string | null;
  url: string | null;
  source_id: string;
}

export interface ExploreSectionOut {
  title: string;
  items: ExploreItemOut[];
  see_all_link: string | null;
}

export interface ExploreHomeOut {
  sections: ExploreSectionOut[];
}

export interface ChartsBundleOut {
  top_songs: ExploreItemOut[];
  top_artists: ExploreItemOut[];
  top_videos: ExploreItemOut[];
}

export interface MoodCategoryOut {
  id: string;
  name: string;
  icon: string | null;
  playlist_count: number | null;
}

export interface ExploreProviderOut {
  provider_id: string;
  display_name: string;
}

export const exploreAPI = {
  listProviders: () => apiGet<ExploreProviderOut[]>("/v1/explore/providers"),

  getHome: (provider = "youtube_music") =>
    apiGet<ExploreHomeOut>(`/v1/explore/home?provider=${encodeURIComponent(provider)}`),

  getCharts: (provider = "youtube_music") =>
    apiGet<ChartsBundleOut>(`/v1/explore/charts?provider=${encodeURIComponent(provider)}`),

  getMoods: (provider = "youtube_music") =>
    apiGet<MoodCategoryOut[]>(`/v1/explore/moods?provider=${encodeURIComponent(provider)}`),

  getMoodPlaylists: (moodId: string, provider = "youtube_music") =>
    apiGet<ExploreItemOut[]>(
      `/v1/explore/moods/${encodeURIComponent(moodId)}/playlists?provider=${encodeURIComponent(provider)}`,
    ),
};
