interface SkeletonProps {
  lines?: number;
  height?: string;
  className?: string;
}

export function Skeleton({ lines = 2, height = "h-8", className = "" }: SkeletonProps) {
  return (
    <div className={`animate-pulse space-y-4 ${className}`}>
      <div className={`${height} w-48 bg-bg-muted rounded`} />
      {lines > 0 &&
        Array.from({ length: lines }, (_, i) => i).map((i) => (
          <div key={i} className="h-32 bg-bg-muted rounded-lg" />
        ))}
    </div>
  );
}
