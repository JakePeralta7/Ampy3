import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import type { PlaylistDetailsResponse, TrackDetail } from "../../api/playlists";
import type { ScheduledSync } from "../../api/schedules";
import { Badge } from "../ui/Badge";
import { CopyButton } from "../ui/CopyButton";
import { type Column, DataTable } from "../ui/DataTable";
import { Slideover } from "../ui/Slideover";
import { SyncHistory } from "./SyncHistory";
import { TrackDetailModal } from "./TrackDetailModal";

interface TrackRow {
  _idx: number;
  _detail: TrackDetail | null;
  plex_id?: string;
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
  playlistDetails: PlaylistDetailsResponse | null;
  loading: boolean;
  error: string | null;
  onRematchTrack: (
    syncId: number,
    trackKey: string,
    input: { title: string; artist_name?: string; album_name?: string },
  ) => Promise<{ matched: boolean; message: string }>;
  rematchingTracks?: Set<string>;
  selectedTrackIndex: number | null;
  onTrackSelect: (index: number) => void;
  onTrackClose: () => void;
}

export function PlaylistDetails({
  sync,
  isOpen,
  onClose,
  playlistDetails,
  loading,
  error,
  onRematchTrack,
  rematchingTracks = new Set(),
  selectedTrackIndex,
  onTrackSelect,
  onTrackClose,
}: PlaylistDetailsProps) {
  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  const [tab, setTab] = useState<"tracks" | "history">("tracks");

  const handleRematch = useCallback(
    async (
      trackKey: string,
      input: { title: string; artist_name?: string; album_name?: string },
    ) => {
      if (!sync) return;
      const result = await onRematchTrack(sync.id, trackKey, input);
      if (result.matched) {
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
    },
    [onRematchTrack, sync],
  );

  const rows: TrackRow[] = useMemo(
    () =>
      playlistDetails
        ? playlistDetails.tracks.map((track, idx) => ({
            _idx: idx,
            _detail: playlistDetails.track_details?.[idx] ?? null,
            ...track,
          }))
        : [],
    [playlistDetails?.tracks, playlistDetails?.track_details, playlistDetails],
  );

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
            {r.plex_id && (
              <div className="text-xs text-fg-muted flex items-center gap-1 group">
                {r.plex_id}
                <CopyButton value={r.plex_id} label="Plex ID" />
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
          const trackKey = `${r.plex_id || r.title}-${r._idx}`;
          const isRematching = rematchingTracks.has(trackKey);
          return r.status === "matched" ? (
            <Badge variant="success">✓ Matched</Badge>
          ) : (
            <div className="flex items-center gap-2">
              <Badge variant="danger">✗ Unmatched</Badge>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleRematch(trackKey, {
                    title: r.title,
                    artist_name: r.artist_name,
                    album_name: r.album_name || undefined,
                  });
                }}
                disabled={isRematching}
                className="px-2 py-1 rounded-sm text-xs font-medium bg-warn-500/10 text-warn-500 border border-warn-500/20 hover:bg-warn-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-fast"
              >
                {isRematching ? "..." : "Rematch"}
              </button>
            </div>
          );
        },
      },
    ],
    [handleRematch, rematchingTracks],
  );

  if (!isOpen || !sync) {
    return null;
  }

  const subtitle = playlistDetails ? (
    <span>
      Plex: {sync.target_playlist_name} • Source:{" "}
      {sync.source === "youtube_music" ? "YouTube Music" : sync.source}
      <span className="ml-2 text-success-500 font-semibold">
        Match Rate: {playlistDetails.match_rate} ({playlistDetails.match_percentage}%)
      </span>
    </span>
  ) : undefined;

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
            <div className="flex items-center gap-1 mb-4 border-b border-border">
              <button
                onClick={() => setTab("tracks")}
                className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors duration-fast ${
                  tab === "tracks"
                    ? "border-accent-500 text-accent-500"
                    : "border-transparent text-fg-muted hover:text-fg"
                }`}
              >
                Tracks
              </button>
              <button
                onClick={() => setTab("history")}
                className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors duration-fast ${
                  tab === "history"
                    ? "border-accent-500 text-accent-500"
                    : "border-transparent text-fg-muted hover:text-fg"
                }`}
              >
                History
              </button>
            </div>

            {tab === "tracks" && (
              <>
                <div className="mb-4">
                  <p className="text-sm text-fg-muted">
                    Click a track to see source and match details
                  </p>
                  <p className="text-sm text-fg-muted">
                    Matched: {playlistDetails.matched_count} | Failed:{" "}
                    {playlistDetails.failed_count} | Total:{" "}
                    {playlistDetails.total_source_tracks}
                  </p>
                </div>

                {playlistDetails.tracks.length === 0 ? (
                  <p className="text-fg-muted text-center py-8">
                    No tracks in this playlist
                  </p>
                ) : (
                  <>
                    {loading && (
                      <div className="h-1 bg-accent-500/50 animate-pulse rounded-t" />
                    )}
                    <DataTable
                      columns={columns}
                      data={rows}
                      keyExtractor={(r) => `${r.plex_id || r.title}-${r._idx}`}
                      onRowClick={(r) => {
                        if (r._detail) onTrackSelect(r._idx);
                      }}
                      rowClassName={(r) =>
                        r.status === "unmatched" ? "bg-danger-500/5" : ""
                      }
                    />
                  </>
                )}
              </>
            )}

            {tab === "history" && <SyncHistory syncId={sync.id} />}
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
        source={playlistDetails?.source ?? "unknown"}
      />
    </>
  );
}
