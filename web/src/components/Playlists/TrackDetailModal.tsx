import { Album, ArrowRight, Clock, Hash, Music2, User } from "lucide-react";
import type { TrackDetail, TrackTargetInfo } from "../../api/syncs";
import { Badge } from "../ui/Badge";
import { CopyButton } from "../ui/CopyButton";
import { Modal } from "../ui/Modal";

interface TrackDetailModalProps {
  track: TrackDetail | null;
  index: number;
  isOpen: boolean;
  onClose: () => void;
  targetId?: string;
}

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatDurationMs(ms: number | null | undefined): string {
  if (!ms || ms <= 0) return "—";
  return formatDuration(Math.floor(ms / 1000));
}

function Field({
  icon,
  label,
  value,
  mono,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number | null | undefined;
  mono?: boolean;
}) {
  if (!value || value === "—") return null;
  const display = String(value);
  return (
    <div className="flex items-start gap-2.5 py-1.5">
      <div className="mt-0.5 text-fg-subtle shrink-0">{icon}</div>
      <div className="min-w-0 flex-1">
        <div className="text-xs text-fg-muted">{label}</div>
        <div className={`text-sm mt-0.5 ${mono ? "font-mono text-xs" : ""} text-fg`}>
          <span className="inline-flex items-center gap-1.5 group">
            {display}
            {mono && <CopyButton value={display} label={label} />}
          </span>
        </div>
      </div>
    </div>
  );
}

function SourcePanel({ track }: { track: TrackDetail["source"] }) {
  const hasData = track && (track.title || track.artist_name);
  if (!hasData) {
    return (
      <div className="flex-1 rounded-lg border-2 border-dashed border-border bg-bg-muted p-6 flex flex-col items-center justify-center min-h-[200px]">
        <div className="mb-3 text-fg-subtle">
          <Music2 size={40} />
        </div>
        <p className="text-sm font-medium text-fg-muted">No source data</p>
      </div>
    );
  }
  return (
    <div className="flex-1 rounded-lg border border-border bg-bg-surface p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-fg">Source</h3>
      </div>
      <div className="divide-y divide-border">
        <Field icon={<Music2 size={14} />} label="Title" value={track.title} />
        <Field icon={<User size={14} />} label="Artist" value={track.artist_name} />
        <Field icon={<Album size={14} />} label="Album" value={track.album_name} />
        <Field
          icon={<Clock size={14} />}
          label="Duration"
          value={formatDurationMs(track.duration_ms)}
        />
        <Field icon={<Hash size={14} />} label="Source ID" value={track.source_id} mono />
      </div>
    </div>
  );
}

function TargetPanel({ target }: { target: TrackTargetInfo | null }) {
  if (!target || (!target.title && !target.artist_name)) {
    return (
      <div className="flex-1 rounded-lg border-2 border-dashed border-danger-500/30 bg-danger-500/5 p-6 flex flex-col items-center justify-center min-h-[200px]">
        <div className="mb-3 text-danger-500/40">
          <Music2 size={40} />
        </div>
        <p className="text-sm font-medium text-fg-muted">No Match Found</p>
      </div>
    );
  }

  const hasMatch = !!target.item_id;

  return (
    <div
      className={`flex-1 rounded-lg border p-5 ${hasMatch ? "border-success-500/30 bg-bg-surface" : "border-border bg-bg-surface"}`}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-fg">{target.target_id} Match</h3>
        {hasMatch && <Badge variant="success">✓ Matched</Badge>}
      </div>
      <div className="divide-y divide-border">
        <Field icon={<Music2 size={14} />} label="Title" value={target.title} />
        <Field icon={<User size={14} />} label="Artist" value={target.artist_name} />
        <Field icon={<Album size={14} />} label="Album" value={target.album_name} />
        <Field
          icon={<Clock size={14} />}
          label="Duration"
          value={formatDuration(target.duration)}
        />
        <Field
          icon={<Hash size={14} />}
          label={`${target.target_id} ID`}
          value={target.item_id}
          mono
        />
      </div>
    </div>
  );
}

export function TrackDetailModal({
  track,
  index,
  isOpen,
  onClose,
  targetId,
}: TrackDetailModalProps) {
  if (!isOpen || !track) return null;

  const targets = track.targets || [];
  const active: TrackTargetInfo | null = targets.find((t) => t.target_id === targetId) || null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Track #${index + 1}`} size="md">
      <div className="flex flex-col md:flex-row gap-4">
        <SourcePanel track={track.source} />
        <div className="flex items-center justify-center text-fg-subtle shrink-0">
          <ArrowRight size={24} className="hidden md:block" />
          <ArrowRight size={20} className="md:hidden rotate-90" />
        </div>
        <TargetPanel target={active} />
      </div>
    </Modal>
  );
}
