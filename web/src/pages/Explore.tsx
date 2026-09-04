import { RefreshCw, Search, X } from "lucide-react";
import { useState } from "react";
import type { ExploreItemOut } from "../api/explore";
import { PageLayout } from "../components/layout/PageLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { ExploreSection } from "../features/explore/ExploreSection";
import { MoodGrid } from "../features/explore/MoodGrid";
import { SourcePlaylistModal } from "../features/explore/SourcePlaylistModal";
import { useExplore } from "../hooks/useExplore";
import { INPUT_STYLES } from "../lib/styles";

export function ExplorePage() {
  const {
    providers,
    activeProvider,
    moods,
    moodPlaylists,
    selectedMoodId,
    home,
    charts,
    searchResults,
    searchQuery,
    loading,
    error,
    selectMood,
    setProvider,
    runSearch,
    clearSearch,
    refresh,
  } = useExplore();

  const [query, setQuery] = useState("");
  const [selectedItem, setSelectedItem] = useState<ExploreItemOut | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runSearch(query);
  };

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

  return (
    <PageLayout
      title="Explore"
      subtitle="Discover new music from your connected sources"
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
      {providers.length > 0 && (
        <div className="mb-6 flex gap-1 border-b border-border pb-3">
          {providers.map((p) => (
            <button
              key={p.provider_id}
              onClick={() => setProvider(p.provider_id)}
              className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors duration-fast focus-visible:ring-2 focus-visible:ring-border-focus focus-visible:outline-none ${
                p.provider_id === activeProvider
                  ? "bg-accent-500 text-accent-fg"
                  : "text-fg-muted hover:bg-bg-muted hover:text-fg"
              }`}
            >
              {p.display_name}
            </button>
          ))}
        </div>
      )}

      <Card variant="bordered" padding="md" className="mb-6">
        <form onSubmit={handleSubmit} className="flex gap-2">
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
      </Card>

      {loading && !moods && !home && !charts && <LoadingSpinner fullPage />}

      {error && (
        <Card variant="bordered" padding="md" className="mb-6">
          <p className="text-sm text-danger-500">{error}</p>
        </Card>
      )}

      {searchResults !== null ? (
        searchResults.length > 0 ? (
          <Card variant="bordered" padding="md" className="mb-6">
            <ExploreSection
              title={`Results for “${searchQuery}”`}
              items={searchResults}
              onSelect={setSelectedItem}
            />
          </Card>
        ) : (
          <Card variant="bordered" padding="md" className="mb-6">
            <p className="text-sm text-fg-muted">No playlists found for “{searchQuery}”.</p>
          </Card>
        )
      ) : (
        <>
          {chartSections.length > 0 && (
            <Card variant="bordered" padding="md" className="mb-6">
              <div className="space-y-6">
                {chartSections.map((s) => (
                  <ExploreSection
                    key={s.title}
                    title={s.title}
                    items={s.items}
                    onSelect={setSelectedItem}
                  />
                ))}
              </div>
            </Card>
          )}

          {moods && (
            <Card variant="bordered" padding="md" className="mb-6">
              <MoodGrid moods={moods} selectedMoodId={selectedMoodId} onSelect={selectMood} />
            </Card>
          )}

          {loading && moodPlaylists === null && selectedMoodId && (
            <Card variant="bordered" padding="md" className="mb-6">
              <LoadingSpinner />
            </Card>
          )}

          {moodPlaylists && selectedMoodId && (
            <Card variant="bordered" padding="md" className="mb-6">
              <ExploreSection title="Playlists" items={moodPlaylists} onSelect={setSelectedItem} />
            </Card>
          )}

          {home && home.sections.length > 0 && (
            <div className="space-y-6">
              {home.sections.map((s) => (
                <ExploreSection
                  key={s.title}
                  title={s.title}
                  items={s.items}
                  onSelect={setSelectedItem}
                />
              ))}
            </div>
          )}
        </>
      )}

      <SourcePlaylistModal
        item={selectedItem}
        isOpen={selectedItem !== null}
        onClose={() => setSelectedItem(null)}
        onSyncCreated={refresh}
      />
    </PageLayout>
  );
}
