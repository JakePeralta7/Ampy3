import type React from "react";
import { useCallback, useEffect, useState } from "react";
import type { CreateScheduledSyncInput, ScheduledSync } from "../../api/schedules";
import { SOURCE_DEEZER, SOURCE_YOUTUBE_MUSIC, TARGET_PLEX } from "../../lib/constants";
import { INPUT_STYLES, SELECT_STYLES } from "../../lib/styles";
import { Button } from "../ui/Button";
import { TargetSelectDropdown } from "../ui/TargetSelectDropdown";

export interface ScheduleFormPrefill {
  sourceUrl: string;
  playlistName: string;
  source?: string;
}

interface ScheduleFormProps {
  onSubmit: (input: CreateScheduledSyncInput) => Promise<void>;
  editingSync?: ScheduledSync | null;
  prefill?: ScheduleFormPrefill;
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

const SOURCES = [
  { value: SOURCE_YOUTUBE_MUSIC, label: "YouTube Music" },
  { value: SOURCE_DEEZER, label: "Deezer" },
];

export function ScheduleForm({
  onSubmit,
  editingSync,
  prefill,
  onCancel,
  isLoading = false,
  error,
}: ScheduleFormProps) {
  const [source, setSource] = useState(SOURCE_YOUTUBE_MUSIC);
  const [targetIds, setTargetIds] = useState<string[]>([TARGET_PLEX]);
  const [sourceUrl, setSourceUrl] = useState("");
  const [targetPlaylistName, setTargetPlaylistName] = useState("");
  const [scheduleInterval, setScheduleInterval] = useState("daily");
  const [formError, setFormError] = useState<string | null>(null);

  const resetForm = useCallback(() => {
    setSource(SOURCE_YOUTUBE_MUSIC);
    setTargetIds([TARGET_PLEX]);
    setSourceUrl("");
    setTargetPlaylistName("");
    setScheduleInterval("daily");
    setFormError(null);
  }, []);

  useEffect(() => {
    if (editingSync) {
      setSource(editingSync.source);
      setTargetIds(editingSync.target_ids || [TARGET_PLEX]);
      setSourceUrl(editingSync.source_url);
      setTargetPlaylistName(editingSync.target_playlist_name);
      setScheduleInterval(editingSync.schedule_interval);
    } else if (prefill) {
      setSource(prefill.source ?? SOURCE_YOUTUBE_MUSIC);
      setTargetIds([TARGET_PLEX]);
      setSourceUrl(prefill.sourceUrl);
      setTargetPlaylistName(prefill.playlistName);
      setScheduleInterval("daily");
      setFormError(null);
    } else {
      resetForm();
    }
  }, [editingSync, prefill, resetForm]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!sourceUrl.trim()) {
      setFormError("Playlist URL is required");
      return;
    }
    if (!targetPlaylistName.trim()) {
      setFormError("Playlist name is required");
      return;
    }
    if (targetIds.length === 0) {
      setFormError("At least one target is required");
      return;
    }

    try {
      const input: CreateScheduledSyncInput = {
        source,
        target_ids: targetIds,
        source_url: sourceUrl.trim(),
        target_playlist_name: targetPlaylistName.trim(),
        schedule_interval: scheduleInterval,
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
            className={SELECT_STYLES}
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
          <label className="block text-sm font-medium text-fg-muted mb-2">
            Targets * (select multiple)
          </label>
          <TargetSelectDropdown value={targetIds} onChange={setTargetIds} disabled={isLoading} />
        </div>

        <div>
          <label className="block text-sm font-medium text-fg-muted mb-1">Playlist URL *</label>
          <input
            type="url"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            placeholder="https://music.youtube.com/playlist?list=..."
            className={INPUT_STYLES}
            disabled={isLoading}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-fg-muted mb-1">Playlist Name *</label>
          <input
            type="text"
            value={targetPlaylistName}
            onChange={(e) => setTargetPlaylistName(e.target.value)}
            placeholder="e.g., Synced Playlist"
            className={INPUT_STYLES}
            disabled={isLoading}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-fg-muted mb-1">Sync Frequency *</label>
          <select
            value={scheduleInterval}
            onChange={(e) => setScheduleInterval(e.target.value)}
            className={SELECT_STYLES}
            disabled={isLoading}
          >
            {SCHEDULE_INTERVALS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
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
