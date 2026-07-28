import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import type { CreateScheduledSyncInput, ScheduledSync } from "../api/schedules";
import { PageLayout } from "../components/Layout/PageLayout";
import { PlaylistDetails } from "../components/Playlists/PlaylistDetails";
import { ScheduleFormModal } from "../components/Playlists/ScheduleFormModal";
import { SchedulesList } from "../components/Playlists/SchedulesList";
import { Button } from "../components/ui/Button";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { usePlaylistDetails } from "../hooks/usePlaylistDetails";
import { useScheduledSyncs } from "../hooks/useScheduledSyncs";
import { getErrorMessage } from "../lib/utils";

export function SyncsPage() {
  const {
    syncs,
    loading,
    error,
    refreshing,
    createSync,
    updateSync,
    deleteSync,
    triggerSyncNow,
    bulkSyncNow,
    bulkToggleActive,
    bulkDelete,
  } = useScheduledSyncs();
  const {
    playlistDetails,
    loading: detailsLoading,
    error: detailsError,
    matchingTracks,
    fetchPlaylistTracks,
    matchTrack,
    clearPlaylistDetails,
  } = usePlaylistDetails();

  const [searchParams, setSearchParams] = useSearchParams();

  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [editingSync, setEditingSync] = useState<ScheduledSync | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteConfirmSync, setDeleteConfirmSync] = useState<ScheduledSync | null>(null);

  const syncIdParam = searchParams.get("sync");
  const tabParam = searchParams.get("tab");
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

  const selectedSyncId = selectedSync?.id;

  useEffect(() => {
    if (selectedSyncId) {
      fetchPlaylistTracks(selectedSyncId);
    }
  }, [selectedSyncId, fetchPlaylistTracks]);

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
        const targetIdsChanged =
          JSON.stringify(input.target_ids) !== JSON.stringify(editingSync.target_ids);
        const updateInput = {
          target_ids: targetIdsChanged ? input.target_ids : undefined,
          target_playlist_name:
            input.target_playlist_name !== editingSync.target_playlist_name
              ? input.target_playlist_name
              : undefined,
          schedule_interval:
            input.schedule_interval !== editingSync.schedule_interval
              ? input.schedule_interval
              : undefined,
        };
        await updateSync(editingSync.id, updateInput);
        toast.success(`Updated "${editingSync.target_playlist_name}"`);
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
      toast.success(`Deleted "${deleteConfirmSync.target_playlist_name}"`);
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
          ? `Paused "${sync.target_playlist_name}"`
          : `Resumed "${sync.target_playlist_name}"`,
      );
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to toggle sync"));
    }
  };

  const handleSyncNow = async (sync: ScheduledSync) => {
    try {
      await triggerSyncNow(sync.id);
      toast.success(`Sync triggered for "${sync.target_playlist_name}"`);
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to trigger sync"));
    }
  };

  const handleBulkSyncNow = async (ids: number[]) => {
    try {
      await bulkSyncNow(ids);
      toast.success(`Sync triggered for ${ids.length} schedule(s)`);
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to trigger bulk sync"));
    }
  };

  const handleBulkToggleActive = async (ids: number[], isActive: boolean) => {
    try {
      await bulkToggleActive(ids, isActive);
      const action = isActive ? "Resumed" : "Paused";
      toast.success(`${action} ${ids.length} schedule(s)`);
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to toggle schedules"));
    }
  };

  const handleBulkDelete = async (ids: number[]) => {
    try {
      await bulkDelete(ids);
      toast.success(`Deleted ${ids.length} schedule(s)`);
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to delete schedules"));
    }
  };

  const handleViewDetails = (sync: ScheduledSync) => {
    const defaultTab = sync.target_ids[0] ?? "history";
    setSearchParams({ sync: String(sync.id), tab: defaultTab });
  };

  const handleCloseDetailsModal = () => {
    setSearchParams({});
  };

  const handleTrackSelect = (index: number) => {
    const current = searchParams.get("sync");
    if (current) {
      setSearchParams({
        sync: current,
        tab: searchParams.get("tab") ?? "history",
        track: String(index),
      });
    }
  };

  const handleTrackClose = () => {
    const current = searchParams.get("sync");
    if (current) {
      setSearchParams({ sync: current, tab: searchParams.get("tab") ?? "history" });
    }
  };

  const handleTabChange = (tabId: string) => {
    const current = searchParams.get("sync");
    if (current) {
      setSearchParams({ sync: current, tab: tabId });
    }
  };

  const handleCloseFormModal = () => {
    setIsFormModalOpen(false);
    setEditingSync(null);
    setFormError(null);
  };

  return (
    <PageLayout
      title="Syncs"
      subtitle="Manage your scheduled playlist syncs"
      actions={
        <Button
          onClick={() => {
            setEditingSync(null);
            setIsFormModalOpen(true);
          }}
          icon={<span>+</span>}
        >
          Add Schedule
        </Button>
      }
    >
      <div>
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
          onBulkSyncNow={handleBulkSyncNow}
          onBulkToggleActive={handleBulkToggleActive}
          onBulkDelete={handleBulkDelete}
        />
      </div>

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
        onMatchTrack={matchTrack}
        matchingTracks={matchingTracks}
        selectedTrackIndex={trackIndex}
        onTrackSelect={handleTrackSelect}
        onTrackClose={handleTrackClose}
        activeTab={tabParam ?? selectedSync?.target_ids[0] ?? "history"}
        onTabChange={handleTabChange}
      />

      <ConfirmDialog
        open={deleteConfirmSync !== null}
        title={`Delete "${deleteConfirmSync?.target_playlist_name ?? ""}"`}
        message="This cannot be undone."
        confirmLabel="Delete"
        variant="danger"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteConfirmSync(null)}
      />
    </PageLayout>
  );
}
