import { Loader2, RefreshCw, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import type { ExploreItemOut } from "../../api/explore";
import { settingsAPI } from "../../api/settings";
import { PageLayout } from "../../components/layout/PageLayout";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { DeezerIcon, YouTubeMusicIcon } from "../../components/ui/SourceIcon";
import { useExplore } from "../../hooks/useExplore";
import { SOURCE_YOUTUBE_MUSIC } from "../../lib/constants";
import { INPUT_STYLES } from "../../lib/styles";
import { AuthNotice } from "./AuthNotice";
import { ExploreHero } from "./ExploreHero";
import { ExploreSection } from "./ExploreSection";
import { ExploreSkeleton } from "./ExploreSkeleton";
import { MoodGrid } from "./MoodGrid";
import { SourcePlaylistModal } from "./SourcePlaylistModal";

export function ExploreView({
  provider,
  title,
  subtitle,
}: {
  provider: string;
  title: string;
  subtitle: string;
}) {
  const {
    moods,
    moodPlaylists,
    selectedMoodId,
    home,
    charts,
    providers,
    searchResults,
    searchQuery,
    loading,
    error,
    selectMood,
    runSearch,
    clearSearch,
    refresh,
  } = useExplore({ initialProvider: provider });

  const [query, setQuery] = useState("");
  const [selectedItem, setSelectedItem] = useState<ExploreItemOut | null>(null);
  const [ytmusicAuthSet, setYtmusicAuthSet] = useState(true);

  useEffect(() => {
    let cancelled = false;
    settingsAPI
      .getSettings()
      .then((settings) => {
        if (!cancelled) setYtmusicAuthSet(settings.ytmusic_auth_set);
      })
      .catch(() => {
        if (!cancelled) setYtmusicAuthSet(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runSearch(query);
  };

  const currentProvider = providers.find((p) => p.provider_id === provider);
  const showAuthNotice =
    provider === SOURCE_YOUTUBE_MUSIC && Boolean(currentProvider?.auth_required) && !ytmusicAuthSet;

  const chartSections: { title: string; items: ExploreItemOut[] }[] = [];
  if (charts?.top_songs.length) {
    chartSections.push({ title: "Top Songs", items: charts.top_songs });
  }
  if (charts?.top_artists.length) {
    chartSections.push({ title: "Top Artists", items: charts.top_artists });
  }
  if (charts?.top_videos.length) {
    chartSections.push({ title: "Top Videos", items: charts.top_videos });
  }

  const heroItem = charts?.top_songs[0] ?? home?.sections[0]?.items[0];

  const initialLoading = loading && !moods && !home && !charts && searchResults === null;

  return (
    <PageLayout
      title={title}
      subtitle={subtitle}
      icon={provider === "deezer" ? <DeezerIcon size={28} /> : <YouTubeMusicIcon size={28} />}
      actions={
        <Button
          onClick={refresh}
          icon={<RefreshCw size={14} />}
          variant="secondary"
          size="sm"
          loading={loading}
        >
          Refresh
        </Button>
      }
    >
      <div className="flex flex-col gap-10">
        <form
          onSubmit={handleSubmit}
          className="flex gap-2 rounded-xl border border-border bg-bg-surface p-3 shadow-sm"
        >
          <div className="relative flex-1">
            <Search
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-subtle"
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search playlists…"
              className={`${INPUT_STYLES} pl-9`}
            />
          </div>
          <Button type="submit" variant="primary" disabled={!query.trim()}>
            Search
          </Button>
          {searchQuery && (
            <Button type="button" variant="secondary" onClick={clearSearch} icon={<X size={14} />}>
              Clear
            </Button>
          )}
        </form>

        {error && (
          <Alert variant="error" className="mb-2">
            {error}
          </Alert>
        )}

        {showAuthNotice && <AuthNotice />}

        {initialLoading ? (
          <ExploreSkeleton />
        ) : searchResults !== null ? (
          searchResults.length > 0 ? (
            <ExploreSection
              title={`Results for "${searchQuery}"`}
              items={searchResults}
              onSelect={setSelectedItem}
              isSearchResults
            />
          ) : (
            <p className="text-sm text-fg-muted">No playlists found for "{searchQuery}".</p>
          )
        ) : (
          <>
            {moods && moods.length > 0 && (
              <MoodGrid 
                moods={moods} 
                selectedMoodId={selectedMoodId} 
                onSelect={selectMood}
                isCompact={!!selectedMoodId}
              />
            )}

            {selectedMoodId && loading && moodPlaylists === null && (
              <div className="flex items-center gap-2 text-sm text-fg-muted">
                <Loader2 size={16} className="animate-spin" />
                Loading playlists…
              </div>
            )}

            {selectedMoodId &&
              moodPlaylists &&
              (moodPlaylists.length > 0 ? (
                <ExploreSection
                  title="Playlists"
                  items={moodPlaylists}
                  onSelect={setSelectedItem}
                />
              ) : (
                <p className="text-sm text-fg-muted">No playlists found for this mood/genre.</p>
              ))}

            {!selectedMoodId && (
              <>
                {heroItem && <ExploreHero item={heroItem} onSelect={setSelectedItem} />}

                {chartSections.length > 0 && (
                  <div className="flex flex-col gap-10">
                    {chartSections.map((s) => (
                      <ExploreSection
                        key={s.title}
                        title={s.title}
                        items={s.items}
                        onSelect={setSelectedItem}
                      />
                    ))}
                  </div>
                )}

                {home && home.sections.length > 0 && (
                  <div className="flex flex-col gap-10">
                    {home.sections.map((s) => (
                      <ExploreSection
                        key={s.title}
                        title={s.title}
                        items={s.items}
                        onSelect={setSelectedItem}
                        seeAllLink={s.see_all_link}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>

      <SourcePlaylistModal
        item={selectedItem}
        isOpen={selectedItem !== null}
        onClose={() => setSelectedItem(null)}
        onSyncCreated={refresh}
      />
    </PageLayout>
  );
}
