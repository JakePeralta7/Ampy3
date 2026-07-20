import type React from "react";
import { useCallback, useEffect, useState } from "react";
import type { CreateScheduledSyncInput, ScheduledSync } from "../../api/schedules";
import { Button } from "../ui/Button";

interface ScheduleFormProps {
  onSubmit: (input: CreateScheduledSyncInput) => Promise<void>;
  editingSync?: ScheduledSync | null;
  onCancel?: () => void;
  isLoading?: boolean;
  error?: string | null;
}

const SCHEDULE_INTERVALS = [
  { value: "every_6h", label: "Every 6 hours" },
  { value: "every_12h", label: "Every 12 hours" },
  { value: "every_24h", label: "Every 24 hours" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
];

const SOURCES = [{ value: "youtube_music", label: "YouTube Music" }];

export function ScheduleForm({
  onSubmit,
  editingSync,
  onCancel,
  isLoading = false,
  error,
}: ScheduleFormProps) {
  const [source, setSource] = useState("youtube_music");
  const [sourceUrl, setSourceUrl] = useState("");
  const [plexPlaylistName, setPlexPlaylistName] = useState("");
  const [scheduleInterval, setScheduleInterval] = useState("daily");
  const [replaceExisting, setReplaceExisting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const resetForm = useCallback(() => {
    setSource("youtube_music");
    setSourceUrl("");
    setPlexPlaylistName("");
    setScheduleInterval("daily");
    setReplaceExisting(false);
    setFormError(null);
  }, []);

  useEffect(() => {
    if (editingSync) {
      setSource(editingSync.source);
      setSourceUrl(editingSync.source_url);
      setPlexPlaylistName(editingSync.plex_playlist_name);
      setScheduleInterval(editingSync.schedule_interval);
      setReplaceExisting(editingSync.replace_existing);
    } else {
      resetForm();
    }
  }, [editingSync, resetForm]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!sourceUrl.trim()) {
      setFormError("Playlist URL is required");
      return;
    }
    if (!plexPlaylistName.trim()) {
      setFormError("Plex playlist name is required");
      return;
    }

    try {
      const input: CreateScheduledSyncInput = {
        source,
        source_url: sourceUrl.trim(),
        plex_playlist_name: plexPlaylistName.trim(),
        schedule_interval: scheduleInterval,
        replace_existing: replaceExisting,
      };

      await onSubmit(input);
      resetForm();
    } catch {
      // Error handled by parent component
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      onKeyDown={(e) => {
        if (e.key === "Escape") onCancel?.();
      }}
    >
      <div className="space-y-4">
        {(formError || error) && (
          <div className="p-3 bg-danger-500/10 text-danger-500 border border-danger-500/20 rounded-md text-sm">
            {formError || error}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-fg-muted mb-1">Source *</label>
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-border rounded-md bg-bg-surface text-fg disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-border-focus"
            disabled={isLoading}
          >
            {SOURCES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-fg-muted mb-1">Playlist URL *</label>
          <input
            type="url"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            placeholder="https://music.youtube.com/playlist?list=..."
            className="w-full px-3 py-2 text-sm border border-border rounded-md bg-bg-surface text-fg placeholder-fg-subtle disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-border-focus"
            disabled={isLoading}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-fg-muted mb-1">
            Plex Playlist Name *
          </label>
          <input
            type="text"
            value={plexPlaylistName}
            onChange={(e) => setPlexPlaylistName(e.target.value)}
            placeholder="e.g., Synced Playlist"
            className="w-full px-3 py-2 text-sm border border-border rounded-md bg-bg-surface text-fg placeholder-fg-subtle disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-border-focus"
            disabled={isLoading}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-fg-muted mb-1">Sync Frequency *</label>
          <select
            value={scheduleInterval}
            onChange={(e) => setScheduleInterval(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-border rounded-md bg-bg-surface text-fg disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-border-focus"
            disabled={isLoading}
          >
            {SCHEDULE_INTERVALS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="flex items-center text-sm font-medium text-fg-muted">
            <input
              type="checkbox"
              checked={replaceExisting}
              onChange={(e) => setReplaceExisting(e.target.checked)}
              className="w-4 h-4 rounded border-border mr-2 text-accent-500 focus:ring-border-focus disabled:opacity-50"
              disabled={isLoading}
            />
            Replace existing playlist on sync (otherwise merge)
          </label>
        </div>

        <div className="flex gap-2 pt-4">
          <Button type="submit" variant="primary" loading={isLoading}>
            {isLoading ? "Saving..." : editingSync ? "Update" : "Add"}
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={isLoading}
            onClick={() => {
              resetForm();
              onCancel?.();
            }}
          >
            Cancel
          </Button>
        </div>
      </div>
    </form>
  );
}
