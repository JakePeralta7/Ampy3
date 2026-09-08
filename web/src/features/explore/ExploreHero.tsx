import { ArrowUpRight } from "lucide-react";
import type { ExploreItemOut } from "../../api/explore";
import { itemTypeLabel } from "./ExploreCard";

interface ExploreHeroProps {
  item: ExploreItemOut;
  onSelect: (item: ExploreItemOut) => void;
}

export function ExploreHero({ item, onSelect }: ExploreHeroProps) {
  return (
    <button
      onClick={() => onSelect(item)}
      className="group relative block w-full overflow-hidden rounded-xl text-left shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus focus-visible:ring-offset-2 focus-visible:ring-offset-bg-app"
    >
      <div className="relative aspect-[21/9] w-full sm:aspect-[24/9]">
        {item.thumbnail_url ? (
          <img
            src={item.thumbnail_url}
            alt={item.title}
            className="h-full w-full object-cover transition-transform duration-base group-hover:scale-105"
          />
        ) : (
          <div className="h-full w-full bg-gradient-to-br from-accent-600 to-accent-700" />
        )}
      </div>

      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent" />

      <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-4 p-6">
        <div className="min-w-0">
          <span className="mb-2 inline-block rounded-md bg-white/20 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-white backdrop-blur-sm">
            {itemTypeLabel(item.item_type)}
          </span>
          <h2 className="truncate text-2xl font-bold text-white sm:text-3xl">{item.title}</h2>
          {item.subtitle && <p className="mt-1 truncate text-sm text-white/80">{item.subtitle}</p>}
        </div>
        <span className="hidden shrink-0 items-center gap-2 rounded-lg bg-white/20 px-4 py-2 text-sm font-semibold text-white backdrop-blur-sm transition-colors duration-fast group-hover:bg-white/30 sm:inline-flex">
          Explore
          <ArrowUpRight size={16} />
        </span>
      </div>
    </button>
  );
}
