import { Album, ArrowRight, Clock, Hash, Music2, User, XCircle } from "lucide-react";
import type { TrackDetail } from "../../api/playlists";
import { Badge } from "../ui/Badge";
import { CopyButton } from "../ui/CopyButton";
import { Modal } from "../ui/Modal";

function formatSourceName(source: string): string {
  return source.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

interface TrackDetailModalProps {
  track: TrackDetail | null;
  index: number;
  isOpen: boolean;
  onClose: () => void;
  source: string;
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

function DetailPanel({
  label,
  track,
  type,
}: {
  label: string;
  track: TrackDetail["source"] | TrackDetail["match"];
  type: "source" | "match";
}) {
  const isMatch = type === "match";
  const hasData = track && (track.title || track.artist_name);

  if (!hasData) {
    return (
      <div
        className={`flex-1 rounded-lg border-2 border-dashed p-6 flex flex-col items-center justify-center min-h-[200px] ${isMatch ? "bg-danger-500/5 border-danger-500/30" : "bg-bg-muted border-border"}`}
      >
        <div className={`mb-3 ${isMatch ? "text-danger-500/40" : "text-fg-subtle"}`}>
          {isMatch ? <XCircle size={40} /> : <Music2 size={40} />}
        </div>
        <p className="text-sm font-medium text-fg-muted">
          {isMatch ? "No Match Found" : "No source data"}
        </p>
        {isMatch && (
          <p className="text-xs text-fg-subtle mt-1 text-center">
            This track could not be matched to any item in your Plex library
          </p>
        )}
      </div>
    );
  }

  const hasMatch =
    isMatch && "plex_id" in (track || {}) && (track as TrackDetail["match"])?.plex_id;
  const src =
    type === "source" ? (track as TrackDetail["source"]) : (track as TrackDetail["match"]);

  return (
    <div
      className={`flex-1 rounded-lg border p-5 ${hasMatch ? "bg-bg-surface border-success-500/30" : "bg-bg-surface border-border"}`}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-fg">{label}</h3>
        {hasMatch && <Badge variant="success">✓ Matched</Badge>}
      </div>

      <div className="divide-y divide-border">
        <Field icon={<Music2 size={14} />} label="Title" value={src?.title} />
        <Field icon={<User size={14} />} label="Artist" value={src?.artist_name} />
        <Field icon={<Album size={14} />} label="Album" value={src?.album_name} />
        <Field
          icon={<Clock size={14} />}
          label="Duration"
          value={
            type === "source"
              ? formatDurationMs((track as TrackDetail["source"])?.duration_ms)
              : formatDuration((track as TrackDetail["match"])?.duration)
          }
        />
        {!isMatch && (
          <Field
            icon={<Hash size={14} />}
            label="Source ID"
            value={(track as TrackDetail["source"])?.source_id}
            mono
          />
        )}
        {isMatch && (
          <Field
            icon={<Hash size={14} />}
            label="Plex ID"
            value={(track as TrackDetail["match"])?.plex_id}
            mono
          />
        )}
      </div>
    </div>
  );
}

export function TrackDetailModal({ track, index, isOpen, onClose, source }: TrackDetailModalProps) {
  if (!isOpen || !track) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Track #${index + 1}`} size="md">
      <div className="flex flex-col md:flex-row gap-4">
        <DetailPanel label={formatSourceName(source)} track={track.source} type="source" />
        <div className="flex items-center justify-center text-fg-subtle shrink-0">
          <ArrowRight size={24} className="hidden md:block" />
          <ArrowRight size={20} className="md:hidden rotate-90" />
        </div>
        <DetailPanel label="Plex Match" track={track.match} type="match" />
      </div>
    </Modal>
  );
}
