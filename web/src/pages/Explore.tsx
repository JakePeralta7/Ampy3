import { RefreshCw } from "lucide-react";
import { useState } from "react";
import type { ExploreItemOut } from "../api/explore";
import { ExploreSection } from "../components/Explore/ExploreSection";
import { MoodGrid } from "../components/Explore/MoodGrid";
import { SourcePlaylistModal } from "../components/Explore/SourcePlaylistModal";
import { PageLayout } from "../components/Layout/PageLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { useExplore } from "../hooks/useExplore";

export function ExplorePage() {
  const {
    providers,
    activeProvider,
    moods,
    moodPlaylists,
    selectedMoodId,
    loading,
    error,
    selectMood,
    setProvider,
    refresh,
  } = useExplore();

  const [selectedItem, setSelectedItem] = useState<ExploreItemOut | null>(null);

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

      {loading && !moods && <LoadingSpinner fullPage />}

      {error && (
        <Card variant="bordered" padding="md" className="mb-6">
          <p className="text-sm text-danger-500">{error}</p>
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

      <SourcePlaylistModal
        item={selectedItem}
        isOpen={selectedItem !== null}
        onClose={() => setSelectedItem(null)}
        onSyncCreated={refresh}
      />
    </PageLayout>
  );
}
