import { useCallback, useEffect, useState } from "react";
import {
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
  loading: boolean;
  error: string | null;
}

export function useExplore() {
  const [state, setState] = useState<ExploreState>({
    providers: [],
    activeProvider: "youtube_music",
    moods: null,
    moodPlaylists: null,
    selectedMoodId: null,
    loading: true,
    error: null,
  });

  const fetchMoods = useCallback(async (provider: string) => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const moods = await exploreAPI.getMoods(provider);
      setState((s) => ({
        ...s,
        activeProvider: provider,
        moods,
        moodPlaylists: null,
        selectedMoodId: null,
        loading: false,
        error: null,
      }));
    } catch (e) {
      setState((s) => ({
        ...s,
        loading: false,
        error: e instanceof Error ? e.message : "Failed to load moods",
      }));
    }
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

  useEffect(() => {
    exploreAPI.listProviders().then((providers) => {
      setState((s) => ({ ...s, providers }));
    });
  }, []);

  useEffect(() => {
    fetchMoods(state.activeProvider);
  }, [fetchMoods, state.activeProvider]);

  const setProvider = useCallback(
    (provider: string) => {
      if (provider !== state.activeProvider) {
        fetchMoods(provider);
      }
    },
    [fetchMoods, state.activeProvider],
  );

  return {
    ...state,
    selectMood,
    setProvider,
    refresh: () => fetchMoods(state.activeProvider),
  };
}
