import type { LucideIcon } from "lucide-react";
import { Disc3, ListMusic, Mic2, Music2, Play, Video } from "lucide-react";
import type { ExploreItemOut } from "../../api/explore";
import { getSourceLabel } from "../../lib/constants";

const typeIcons = {
  album: Disc3,
  playlist: ListMusic,
  artist: Mic2,
  song: Music2,
  video: Video,
} as const satisfies Record<ExploreItemOut["item_type"], LucideIcon>;

export function itemTypeLabel(itemType: ExploreItemOut["item_type"]): string {
  return `${itemType.charAt(0).toUpperCase()}${itemType.slice(1)}`;
}

interface ExploreCardProps {
  item: ExploreItemOut;
  onSelect: (item: ExploreItemOut) => void;
}

export function ExploreCard({ item, onSelect }: ExploreCardProps) {
  const ItemIcon = typeIcons[item.item_type] ?? Music2;

  return (
    <button
      onClick={() => onSelect(item)}
      className="group flex w-44 shrink-0 flex-col gap-2 rounded-lg p-2 text-left transition-colors duration-fast hover:bg-bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
    >
      <div className="relative aspect-square w-full overflow-hidden rounded-lg bg-bg-muted shadow-sm">
        {item.thumbnail_url ? (
          <img
            src={item.thumbnail_url}
            alt={item.title}
            className="h-full w-full object-cover transition-transform duration-base group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-fg-subtle">
            <ItemIcon size={40} />
          </div>
        )}

        <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition-opacity duration-base group-hover:opacity-100">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-fg text-bg-app shadow-lg transition-transform duration-base group-hover:scale-105">
            <Play size={20} className="ml-0.5" fill="currentColor" />
          </span>
        </div>

        <span className="absolute left-2 top-2 rounded-md bg-black/50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-white backdrop-blur-sm">
          {itemTypeLabel(item.item_type)}
        </span>
      </div>

      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-sm font-semibold text-fg">{item.title}</span>
        <span className="truncate text-xs text-fg-muted">{item.subtitle}</span>
        {item.source_id && (
          <span className="text-[10px] uppercase tracking-wider text-fg-subtle">
            {getSourceLabel(item.source_id)}
          </span>
        )}
      </div>
    </button>
  );
}
