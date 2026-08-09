import { Play } from "lucide-react";
import type { ExploreItemOut } from "../../api/explore";
import { getSourceLabel } from "../../lib/constants";

interface ExploreCardProps {
  item: ExploreItemOut;
  onSelect: (item: ExploreItemOut) => void;
}

export function ExploreCard({ item, onSelect }: ExploreCardProps) {
  return (
    <button
      onClick={() => onSelect(item)}
      className="group flex flex-col gap-2 w-44 shrink-0 rounded-lg p-2 transition-colors duration-fast hover:bg-bg-muted focus-visible:ring-2 focus-visible:ring-border-focus focus-visible:outline-none text-left"
    >
      <div className="relative aspect-square w-full overflow-hidden rounded-lg bg-bg-muted">
        {item.thumbnail_url ? (
          <img
            src={item.thumbnail_url}
            alt={item.title}
            className="h-full w-full object-cover transition-transform duration-base group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-fg-subtle">
            <Play size={32} />
          </div>
        )}
      </div>

      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="truncate text-sm font-medium text-fg">{item.title}</span>
        <span className="truncate text-xs text-fg-muted">{item.subtitle}</span>
        {item.source_id && (
          <span className="text-[10px] text-fg-subtle uppercase tracking-wider">
            {getSourceLabel(item.source_id)}
          </span>
        )}
      </div>
    </button>
  );
}
