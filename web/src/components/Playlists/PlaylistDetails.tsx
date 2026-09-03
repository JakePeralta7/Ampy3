import { ExternalLink, RotateCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import type { ScheduledSync } from "../../api/schedules";
import type { SyncTracksResponse, TrackDetail } from "../../api/syncs";
import { syncsAPI } from "../../api/syncs";
import { getSourceLabel } from "../../lib/constants";
import { CopyButton } from "../ui/CopyButton";
import { type Column, DataTable } from "../ui/DataTable";
import { Slideover } from "../ui/Slideover";
import { Tabs } from "../ui/Tabs";
import { SyncHistory } from "./SyncHistory";
import { TrackDetailModal } from "./TrackDetailModal";

interface TrackRow {
  _idx: number;
  _detail: TrackDetail | null;
  item_id?: string;
  source_item_id?: string;
  title: string;
  artist_name: string;
  album_name: string;
  duration: number;
  status: "matched" | "unmatched";
}

interface PlaylistDetailsProps {
  sync: ScheduledSync | null;
  isOpen: boolean;
  onClose: () => void;
  playlistDetails: SyncTracksResponse | null;
  loading: boolean;
  error: string | null;
  onMatchTrack: (
    syncId: number,
    trackKey: string,
    input: { title: string; artist_name?: string; album_name?: string },
    targetId?: string,
    sourceItemId?: string,
  ) => Promise<{ matched: boolean; message: string }>;
  matchingTracks?: Set<string>;
  selectedTrackIndex: number | null;
  onTrackSelect: (index: number) => void;
  onTrackClose: () => void;
  activeTab: string;
  onTabChange: (tabId: string) => void;
}

function deriveRows(playlistDetails: SyncTracksResponse, activeTargetId: string): TrackRow[] {
  return playlistDetails.tracks.map((track, idx) => {
    const detail = playlistDetails.track_details?.[idx] ?? null;
    const match = detail?.targets?.find((t) => t.target_id === activeTargetId);
    const source = detail?.source;
    return {
      _idx: idx,
      _detail: detail,
      item_id: match?.item_id,
      source_item_id: source?.item_id ?? undefined,
      title: match?.title ?? source?.title ?? track.title,
      artist_name: match?.artist_name ?? source?.artist_name ?? track.artist_name,
      album_name: match?.album_name ?? source?.album_name ?? track.album_name,
      duration:
        match?.duration ??
        (source?.duration_ms != null ? Math.round(source.duration_ms / 1000) : track.duration),
      status: match ? "matched" : "unmatched",
    };
  });
}

export function PlaylistDetails({
  sync,
  isOpen,
  onClose,
  playlistDetails,
  loading,
  error,
  onMatchTrack,
  matchingTracks = new Set(),
  selectedTrackIndex,
  onTrackSelect,
  onTrackClose,
  activeTab,
  onTabChange,
}: PlaylistDetailsProps) {
  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  const targetIds = sync?.target_ids ?? [];

  const [selectedTab, setSelectedTab] = useState<string>(
    () => activeTab ?? targetIds[0] ?? "history",
  );

  const [openUrl, setOpenUrl] = useState<string | null>(null);

  // Sync selectedTab changes to URL
  const handleTabChangeLocal = useCallback(
    (tabId: string) => {
      setSelectedTab(tabId);
      onTabChange(tabId);
    },
    [onTabChange],
  );

  // Fetch the open URL when tab changes (and it's not "history")
  useEffect(() => {
    if (!sync || selectedTab === "history") {
      setOpenUrl(null);
      return;
    }

    const fetchOpenUrl = async () => {
      try {
        const response = await syncsAPI.getSyncOpenUrl(sync.id, selectedTab);
        setOpenUrl(response.url);
      } catch (_err) {
        // Silently fail; if the URL fails to load, we just don't show the link
        setOpenUrl(null);
      }
    };

    fetchOpenUrl();
  }, [sync, selectedTab]);

  // Update local state when URL tab param changes (e.g., browser back/forward)
  useEffect(() => {
    setSelectedTab(activeTab ?? targetIds[0] ?? "history");
  }, [activeTab, targetIds]);

  const handleMatch = useCallback(
    async (
      trackKey: string,
      input: { title: string; artist_name?: string; album_name?: string },
      targetId?: string,
      sourceItemId?: string,
    ) => {
      if (!sync) return;
      const result = await onMatchTrack(sync.id, trackKey, input, targetId, sourceItemId);
      if (result.matched) {
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
    },
    [onMatchTrack, sync],
  );

  const rows: TrackRow[] = useMemo(() => {
    if (!playlistDetails || selectedTab === "history") return [];
    return deriveRows(playlistDetails, selectedTab);
  }, [playlistDetails, selectedTab]);

  const columns: Column<TrackRow>[] = useMemo(
    () => [
      {
        id: "num",
        header: "#",
        cell: (r: TrackRow) => <span>{r._idx + 1}</span>,
        className: "text-fg-muted text-center text-xs w-10",
        headerClassName: "w-10",
      },
      {
        id: "title",
        header: "Title",
        sortable: true,
        filterable: true,
        cell: (r: TrackRow) => (
          <div className="text-fg">
            <div className="font-medium flex items-center gap-1.5 group">
              {r.title}
              <CopyButton value={r.title} label="title" />
            </div>
            {r.item_id && (
              <div className="text-xs text-fg-muted flex items-center gap-1 group">
                {r.item_id}
                <CopyButton value={r.item_id} label="Library ID" />
              </div>
            )}
          </div>
        ),
      },
      {
        id: "artist",
        header: "Artist",
        sortable: true,
        filterable: true,
        sortValue: (r: TrackRow) => r.artist_name,
        cell: (r: TrackRow) => (
          <span className="text-fg-muted inline-flex items-center gap-1.5 group">
            {r.artist_name || "—"}
            {r.artist_name && <CopyButton value={r.artist_name} label="artist" />}
          </span>
        ),
      },
      {
        id: "album",
        header: "Album",
        sortable: true,
        filterable: true,
        sortValue: (r: TrackRow) => r.album_name,
        cell: (r: TrackRow) => (
          <span className="text-fg-muted inline-flex items-center gap-1.5 group">
            {r.album_name || "—"}
            {r.album_name && <CopyButton value={r.album_name} label="album" />}
          </span>
        ),
      },
      {
        id: "duration",
        header: "Duration",
        sortable: true,
        sortValue: (r: TrackRow) => r.duration,
        cell: (r: TrackRow) => (
          <span className="text-fg-muted">
            {r.duration > 0
              ? `${Math.floor(r.duration / 60)}:${String(r.duration % 60).padStart(2, "0")}`
              : "—"}
          </span>
        ),
      },
      {
        id: "status",
        header: "Status",
        sortable: true,
        filterable: true,
        sortValue: (r: TrackRow) => r.status,
        cell: (r: TrackRow) => {
          const trackKey = `${selectedTab}-${r.item_id || r.title}-${r._idx}`;
          const isMatching = matchingTracks.has(trackKey);
          return r.status === "matched" ? (
            <span className="text-success-500 font-bold">✓</span>
          ) : (
            <div className="flex items-center gap-1">
              <span className="text-danger-500 font-bold">✗</span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleMatch(
                    trackKey,
                    {
                      title: r.title,
                      artist_name: r.artist_name,
                      album_name: r.album_name || undefined,
                    },
                    selectedTab,
                    r.source_item_id,
                  );
                }}
                disabled={isMatching}
                title="Match"
                className="p-1 rounded text-warning-700 hover:bg-warning-50/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-fast"
              >
                <RotateCw size={12} className={isMatching ? "animate-spin" : ""} />
              </button>
            </div>
          );
        },
      },
    ],
    [handleMatch, matchingTracks, selectedTab],
  );

  if (!isOpen || !sync) {
    return null;
  }

  const tabs = [...targetIds.map((id) => ({ id, label: id })), { id: "history", label: "History" }];

  const subtitle = playlistDetails ? `Source: ${getSourceLabel(sync.source)}` : undefined;

  return (
    <>
      <Slideover
        isOpen={isOpen}
        onClose={onClose}
        title={sync.target_playlist_name}
        subtitle={subtitle}
        size="lg"
      >
        {loading && !playlistDetails && (
          <div className="flex items-center justify-center h-full min-h-[200px]">
            <p className="text-fg-muted">Loading tracks...</p>
          </div>
        )}

        {playlistDetails && (
          <>
            <Tabs tabs={tabs} activeTab={selectedTab} onChange={handleTabChangeLocal} />

            {selectedTab !== "history" && (
              <>
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <p className="text-sm text-fg-muted">
                      Click a track to see source and match details
                    </p>
                    <p className="text-sm text-fg-muted">
                      Matched: {rows.filter((r) => r.status === "matched").length} | Failed:{" "}
                      {rows.filter((r) => r.status === "unmatched").length} | Total: {rows.length}
                    </p>
                  </div>
                  {openUrl && (
                    <a
                      href={openUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-accent-500 text-white hover:bg-accent-600 transition-colors text-sm font-medium"
                      title={`Open in ${selectedTab}`}
                    >
                      Open in {selectedTab}
                      <ExternalLink size={16} />
                    </a>
                  )}
                </div>

                {playlistDetails.tracks.length === 0 ? (
                  <p className="text-fg-muted text-center py-8">No tracks in this playlist</p>
                ) : (
                  <>
                    {loading && <div className="h-1 bg-accent-500/50 animate-pulse rounded-t" />}
                    <DataTable
                      columns={columns}
                      data={rows}
                      keyExtractor={(r) => `${selectedTab}-${r.item_id || r.title}-${r._idx}`}
                      onRowClick={(r) => {
                        if (r._detail) onTrackSelect(r._idx);
                      }}
                      rowClassName={(r) => (r.status === "unmatched" ? "bg-danger-500/5" : "")}
                    />
                  </>
                )}
              </>
            )}

            {selectedTab === "history" && <SyncHistory syncId={sync.id} />}
          </>
        )}
      </Slideover>

      <TrackDetailModal
        track={
          selectedTrackIndex != null && playlistDetails?.track_details
            ? (playlistDetails.track_details[selectedTrackIndex] ?? null)
            : null
        }
        index={selectedTrackIndex ?? 0}
        isOpen={selectedTrackIndex != null}
        onClose={onTrackClose}
        targetId={selectedTab !== "history" ? selectedTab : undefined}
      />
    </>
  );
}
