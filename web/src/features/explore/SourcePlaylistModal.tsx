import { ExternalLink } from "lucide-react";
import { useState } from "react";
import type { ExploreItemOut } from "../../api/explore";
import { type CreateScheduledSyncInput, scheduledSyncsAPI } from "../../api/schedules";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { getSourceLabel, SOURCE_YOUTUBE_MUSIC } from "../../lib/constants";
import { getErrorMessage } from "../../lib/utils";
import { ScheduleFormModal } from "../playlists/ScheduleFormModal";

interface SourcePlaylistModalProps {
  item: ExploreItemOut | null;
  isOpen: boolean;
  onClose: () => void;
  onSyncCreated: () => void;
}

export function SourcePlaylistModal({
  item,
  isOpen,
  onClose,
  onSyncCreated,
}: SourcePlaylistModalProps) {
  const [showScheduleForm, setShowScheduleForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreateSync = async (input: CreateScheduledSyncInput) => {
    setSaving(true);
    setError(null);
    try {
      await scheduledSyncsAPI.createScheduledSync(input);
      setShowScheduleForm(false);
      onClose();
      onSyncCreated();
    } catch (e) {
      setError(getErrorMessage(e, "Failed to create sync"));
    } finally {
      setSaving(false);
    }
  };

  if (!item) return null;

  return (
    <>
      <Modal isOpen={isOpen && !showScheduleForm} onClose={onClose} title={item.title} size="md">
        <div className="flex flex-col gap-5">
          <div className="flex gap-4">
            <div className="relative w-32 h-32 shrink-0 overflow-hidden rounded-lg bg-bg-muted">
              {item.thumbnail_url ? (
                <img
                  src={item.thumbnail_url}
                  alt={item.title}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-fg-subtle text-3xl">
                  🎵
                </div>
              )}
            </div>

            <div className="flex flex-col justify-center gap-1 min-w-0">
              <h3 className="text-lg font-semibold text-fg truncate">{item.title}</h3>
              <p className="text-sm text-fg-muted truncate">{item.subtitle}</p>
              <span className="text-xs text-fg-subtle uppercase tracking-wider">
                {getSourceLabel(item.source_id)}
              </span>
            </div>
          </div>

          {error && <Alert>{error}</Alert>}

          <div className="flex gap-2">
            <Button onClick={() => setShowScheduleForm(true)} variant="primary">
              Create Sync
            </Button>
            {item.url && (
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-bg-surface px-4 py-2 text-sm font-medium text-fg-muted hover:bg-bg-muted hover:text-fg transition-colors duration-fast"
              >
                <ExternalLink size={14} />
                Open in {getSourceLabel(item.source_id)}
              </a>
            )}
          </div>
        </div>
      </Modal>

      <ScheduleFormModal
        isOpen={showScheduleForm}
        onClose={() => setShowScheduleForm(false)}
        onSubmit={handleCreateSync}
        prefill={{
          sourceUrl: item.url || "",
          playlistName: item.title,
          source: item.source_id || SOURCE_YOUTUBE_MUSIC,
        }}
        isLoading={saving}
        error={error}
      />
    </>
  );
}
