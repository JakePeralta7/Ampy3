import { ArrowRight, Search } from "lucide-react";
import type { ExploreItemOut } from "../../api/explore";
import { ExploreCard } from "./ExploreCard";

interface ExploreSectionProps {
  title: string;
  items: ExploreItemOut[];
  onSelect: (item: ExploreItemOut) => void;
  seeAllLink?: string | null;
  isSearchResults?: boolean;
}

export function ExploreSection({
  title,
  items,
  onSelect,
  seeAllLink,
  isSearchResults = false,
}: ExploreSectionProps) {
  if (items.length === 0) return null;

  return (
    <section>
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 className="flex items-center gap-2 text-xl font-bold text-fg">
          {isSearchResults && <Search size={18} className="text-fg-muted" />}
          {title}
        </h2>
        {seeAllLink && (
          <a
            href={seeAllLink}
            target="_blank"
            rel="noopener noreferrer"
            className="group inline-flex shrink-0 items-center gap-1 text-sm font-medium text-fg-muted transition-colors duration-fast hover:text-accent-500"
          >
            See all
            <ArrowRight
              size={14}
              className="transition-transform duration-fast group-hover:translate-x-0.5"
            />
          </a>
        )}
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent">
        {items.map((item) => (
          <ExploreCard key={item.id} item={item} onSelect={onSelect} />
        ))}
      </div>
    </section>
  );
}
