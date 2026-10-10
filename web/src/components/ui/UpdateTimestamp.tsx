/**
 * Component for displaying the last update time
 */

interface UpdateTimestampProps {
  lastUpdated: Date | null;
  className?: string;
}

/**
 * Displays when data was last updated, e.g., "Last updated: 2 minutes ago"
 */
export function UpdateTimestamp({ lastUpdated, className }: UpdateTimestampProps) {
  if (!lastUpdated) {
    return <span className={className}>Not updated yet</span>;
  }

  const now = new Date();
  const diffMs = now.getTime() - lastUpdated.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  let timeAgo: string;
  if (diffSecs < 60) {
    timeAgo = "just now";
  } else if (diffMins < 60) {
    timeAgo = `${diffMins} minute${diffMins > 1 ? "s" : ""} ago`;
  } else if (diffHours < 24) {
    timeAgo = `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
  } else {
    timeAgo = `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
  }

  return (
    <span className={className} title={lastUpdated.toLocaleString()}>
      Last updated: {timeAgo}
    </span>
  );
}
