interface ExploreSkeletonProps {
  sections?: number;
}

export function ExploreSkeleton({ sections = 3 }: ExploreSkeletonProps) {
  return (
    <div className="space-y-10">
      {Array.from({ length: sections }, (_, i) => i).map((i) => (
        <div key={i} className="animate-pulse">
          <div className="mb-4 h-6 w-44 rounded bg-bg-muted" />
          <div className="flex gap-3 overflow-hidden">
            {Array.from({ length: 5 }, (_, j) => j).map((j) => (
              <div key={j} className="w-44 shrink-0">
                <div className="aspect-square w-full rounded-lg bg-bg-muted" />
                <div className="mt-2 h-4 w-3/4 rounded bg-bg-muted" />
                <div className="mt-1 h-3 w-1/2 rounded bg-bg-muted" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
