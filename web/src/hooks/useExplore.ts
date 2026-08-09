import { useCallback, useEffect, useState } from "react";
import {
  type ChartsBundleOut,
  type ExploreHomeOut,
  type ExploreItemOut,
  type ExploreProviderOut,
  exploreAPI,
  type MoodCategoryOut,
} from "../api/explore";

interface ExploreState {
  providers: ExploreProviderOut[];
  activeProvider: string;
  moods: MoodCategoryOut[] | null;
  moodPlaylists: ExploreItemOut[] | null;
  selectedMoodId: string | null;
  home: ExploreHomeOut | null;
  charts: ChartsBundleOut | null;
  searchResults: ExploreItemOut[] | null;
  searchQuery: string;
  loading: boolean;
  error: string | null;
}

const initialState: ExploreState = {
  providers: [],
  activeProvider: "youtube_music",
  moods: null,
  moodPlaylists: null,
  selectedMoodId: null,
  home: null,
  charts: null,
  searchResults: null,
  searchQuery: "",
  loading: true,
  error: null,
};

export function useExplore() {
  const [state, setState] = useState<ExploreState>(initialState);

  const fetchProviderContent = useCallback(async (provider: string) => {
    setState((s) => ({
      ...initialState,
      activeProvider: provider,
      providers: s.providers,
      loading: true,
    }));

    const [moodsRes, homeRes, chartsRes] = await Promise.allSettled([
      exploreAPI.getMoods(provider),
      exploreAPI.getHome(provider),
      exploreAPI.getCharts(provider),
    ]);

    setState((s) => {
      const errors: string[] = [];
      const moods = moodsRes.status === "fulfilled" ? moodsRes.value : null;
      const home = homeRes.status === "fulfilled" ? homeRes.value : null;
      const charts = chartsRes.status === "fulfilled" ? chartsRes.value : null;
      if (moodsRes.status === "rejected")
        errors.push(moodsRes.reason?.message ?? "Failed to load moods");
      if (homeRes.status === "rejected")
        errors.push(homeRes.reason?.message ?? "Failed to load home");
      if (chartsRes.status === "rejected")
        errors.push(chartsRes.reason?.message ?? "Failed to load charts");
      return {
        ...s,
        moods,
        home,
        charts,
        moodPlaylists: null,
        selectedMoodId: null,
        loading: false,
        error: errors.length ? errors[0] : null,
      };
    });
  }, []);

  const selectMood = useCallback(async (moodId: string | null) => {
    if (!moodId) {
      setState((s) => ({ ...s, selectedMoodId: null, moodPlaylists: null }));
      return;
    }
    setState((s) => ({ ...s, loading: true }));
    try {
      const playlists = await exploreAPI.getMoodPlaylists(moodId);
      setState((s) => ({
        ...s,
        selectedMoodId: moodId,
        moodPlaylists: playlists,
        loading: false,
      }));
    } catch (e) {
      setState((s) => ({
        ...s,
        loading: false,
        error: e instanceof Error ? e.message : "Failed to load playlists",
      }));
    }
  }, []);

  const runSearch = useCallback(async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) {
      setState((s) => ({ ...s, searchResults: null, searchQuery: "" }));
      return;
    }
    setState((s) => ({ ...s, loading: true, searchQuery: trimmed }));
    try {
      const results = await exploreAPI.searchPlaylists(trimmed);
      setState((s) => ({ ...s, searchResults: results, loading: false, error: null }));
    } catch (e) {
      setState((s) => ({
        ...s,
        searchResults: [],
        loading: false,
        error: e instanceof Error ? e.message : "Failed to search playlists",
      }));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    exploreAPI.listProviders().then((providers) => {
      if (cancelled) return;
      setState((s) => ({ ...s, providers }));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    fetchProviderContent(state.activeProvider);
  }, [fetchProviderContent, state.activeProvider]);

  const setProvider = useCallback(
    (provider: string) => {
      if (provider !== state.activeProvider) {
        fetchProviderContent(provider);
      }
    },
    [fetchProviderContent, state.activeProvider],
  );

  return {
    ...state,
    selectMood,
    setProvider,
    runSearch,
    clearSearch: () => setState((s) => ({ ...s, searchResults: null, searchQuery: "" })),
    refresh: () => fetchProviderContent(state.activeProvider),
  };
}
