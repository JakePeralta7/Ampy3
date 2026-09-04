export function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function getErrorMessage(err: unknown, fallback = "An error occurred"): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  if (
    typeof err === "object" &&
    err !== null &&
    "message" in err &&
    typeof (err as Record<string, unknown>).message === "string"
  ) {
    return (err as Record<string, string>).message;
  }
  return fallback;
}

export function formatNextSync(nextSyncAt: string | null): string {
  if (!nextSyncAt) return "N/A";
  const now = new Date();
  const next = new Date(nextSyncAt);
  const diffMs = next.getTime() - now.getTime();
  if (diffMs <= 0) return "Due now";
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 60) return `in ${diffMin}m`;
  const diffHr = Math.floor(diffMin / 60);
  const remMin = diffMin % 60;
  if (diffHr < 24) return `in ${diffHr}h${remMin > 0 ? ` ${remMin}m` : ""}`;
  const diffDay = Math.floor(diffHr / 24);
  return `in ${diffDay}d`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatDurationMs(ms: number | null | undefined): string {
  if (!ms || ms <= 0) return "—";
  return formatDuration(Math.floor(ms / 1000));
}

export function formatRelativeTime(iso: string | null): string {
  if (!iso) return "Never";
  const now = new Date();
  const then = new Date(iso);
  const diffMs = now.getTime() - then.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}
