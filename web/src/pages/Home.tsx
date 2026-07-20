import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import type { CreateScheduledSyncInput, ScheduledSync } from "../api/schedules";
import { PlaylistDetails } from "../components/Playlists/PlaylistDetails";
import { ScheduleFormModal } from "../components/Playlists/ScheduleFormModal";
import { SchedulesList } from "../components/Playlists/SchedulesList";
import { Button } from "../components/ui/Button";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { usePlaylistDetails } from "../hooks/usePlaylistDetails";
import { useScheduledSyncs } from "../hooks/useScheduledSyncs";
import { getErrorMessage } from "../lib/utils";

export function HomePage() {
  const { syncs, loading, error, refreshing, createSync, updateSync, deleteSync, triggerSyncNow } =
    useScheduledSyncs();
  const {
    playlistDetails,
    loading: detailsLoading,
    error: detailsError,
    rematchingTracks,
    fetchPlaylistTracks,
    rematchTrack,
    clearPlaylistDetails,
  } = usePlaylistDetails();

  const [searchParams, setSearchParams] = useSearchParams();

  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [editingSync, setEditingSync] = useState<ScheduledSync | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteConfirmSync, setDeleteConfirmSync] = useState<ScheduledSync | null>(null);

  // Derive slideover state from URL params so back button navigates states
  const syncIdParam = searchParams.get("sync");
  const selectedSync = useMemo(() => {
    if (!syncIdParam || syncs.length === 0) return null;
    return syncs.find((s) => String(s.id) === syncIdParam) ?? null;
  }, [syncIdParam, syncs]);

  const trackIndex = useMemo(() => {
    if (!searchParams.has("track")) return null;
    const idx = Number(searchParams.get("track"));
    if (!Number.isInteger(idx) || idx < 0) return null;
    if (playlistDetails && idx >= playlistDetails.track_details.length) return null;
    return idx;
  }, [searchParams, playlistDetails]);

  // Fetch playlist tracks when a sync is selected (from URL or user action)
  useEffect(() => {
    if (selectedSync) {
      fetchPlaylistTracks(selectedSync.id);
    }
  }, [selectedSync, fetchPlaylistTracks]);

  // Clean up details when slideover closes (e.g. via back button)
  useEffect(() => {
    if (!selectedSync) {
      clearPlaylistDetails();
    }
  }, [selectedSync, clearPlaylistDetails]);

  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  const handleFormSubmit = async (input: CreateScheduledSyncInput) => {
    setFormLoading(true);
    setFormError(null);
    try {
      if (editingSync) {
        const updateInput = {
          plex_playlist_name:
            input.plex_playlist_name !== editingSync.plex_playlist_name
              ? input.plex_playlist_name
              : undefined,
          schedule_interval:
            input.schedule_interval !== editingSync.schedule_interval
              ? input.schedule_interval
              : undefined,
          replace_existing:
            input.replace_existing !== editingSync.replace_existing
              ? input.replace_existing
              : undefined,
        };
        await updateSync(editingSync.id, updateInput);
        toast.success(`Updated "${editingSync.plex_playlist_name}"`);
      } else {
        await createSync(input);
        toast.success("Schedule created");
      }
      setEditingSync(null);
      setIsFormModalOpen(false);
    } catch (err) {
      const msg = getErrorMessage(err);
      setFormError(msg);
      toast.error(msg);
    } finally {
      setFormLoading(false);
    }
  };

  const handleEdit = (sync: ScheduledSync) => {
    setEditingSync(sync);
    setIsFormModalOpen(true);
  };

  const handleDelete = useCallback((sync: ScheduledSync) => {
    setDeleteConfirmSync(sync);
  }, []);

  const confirmDelete = useCallback(async () => {
    if (!deleteConfirmSync) return;
    try {
      await deleteSync(deleteConfirmSync.id);
      toast.success(`Deleted "${deleteConfirmSync.plex_playlist_name}"`);
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to delete sync"));
    } finally {
      setDeleteConfirmSync(null);
    }
  }, [deleteConfirmSync, deleteSync]);

  const handleToggleActive = async (sync: ScheduledSync) => {
    try {
      await updateSync(sync.id, { is_active: !sync.is_active });
      toast.success(
        sync.is_active
          ? `Paused "${sync.plex_playlist_name}"`
          : `Resumed "${sync.plex_playlist_name}"`,
      );
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to toggle sync"));
    }
  };

  const handleSyncNow = async (sync: ScheduledSync) => {
    try {
      await triggerSyncNow(sync.id);
      toast.success(`Sync triggered for "${sync.plex_playlist_name}"`);
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to trigger sync"));
    }
  };

  const handleViewDetails = (sync: ScheduledSync) => {
    setSearchParams({ sync: String(sync.id) });
  };

  const handleCloseDetailsModal = () => {
    setSearchParams({});
  };

  const handleTrackSelect = (index: number) => {
    const current = searchParams.get("sync");
    if (current) {
      setSearchParams({ sync: current, track: String(index) });
    }
  };

  const handleTrackClose = () => {
    const current = searchParams.get("sync");
    if (current) {
      setSearchParams({ sync: current });
    }
  };

  const handleCloseFormModal = () => {
    setIsFormModalOpen(false);
    setEditingSync(null);
    setFormError(null);
  };

  return (
    <div className="flex-1">
      <div className="max-w-7xl mx-auto p-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold mb-2 text-fg">Ampy3</h1>
            <p className="text-fg-muted">
              Keep your Plex playlists synced with YouTube Music and other sources
            </p>
          </div>
          <Button
            onClick={() => {
              setEditingSync(null);
              setIsFormModalOpen(true);
            }}
            icon={<span>+</span>}
          >
            Add Schedule
          </Button>
        </div>

        <div>
          <h2 className="text-2xl font-bold mb-6 text-fg">Scheduled Syncs</h2>
          <SchedulesList
            syncs={syncs}
            loading={loading}
            error={error}
            refreshing={refreshing}
            onEdit={handleEdit}
            onDelete={handleDelete}
            onToggleActive={handleToggleActive}
            onSyncNow={handleSyncNow}
            onViewDetails={handleViewDetails}
          />
        </div>
      </div>

      {/* Modals */}
      <ScheduleFormModal
        isOpen={isFormModalOpen}
        onClose={handleCloseFormModal}
        onSubmit={handleFormSubmit}
        editingSync={editingSync}
        isLoading={formLoading}
        error={formError}
      />

      <PlaylistDetails
        sync={selectedSync}
        isOpen={selectedSync !== null}
        onClose={handleCloseDetailsModal}
        playlistDetails={playlistDetails}
        loading={detailsLoading}
        error={detailsError}
        onRematchTrack={rematchTrack}
        rematchingTracks={rematchingTracks}
        selectedTrackIndex={trackIndex}
        onTrackSelect={handleTrackSelect}
        onTrackClose={handleTrackClose}
      />

      <ConfirmDialog
        open={deleteConfirmSync !== null}
        title={`Delete "${deleteConfirmSync?.plex_playlist_name ?? ""}"`}
        message="This cannot be undone."
        confirmLabel="Delete"
        variant="danger"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteConfirmSync(null)}
      />
    </div>
  );
}
