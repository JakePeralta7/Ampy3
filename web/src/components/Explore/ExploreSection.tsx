import type { ExploreItemOut } from "../../api/explore";
import { ExploreCard } from "./ExploreCard";

interface ExploreSectionProps {
  title: string;
  items: ExploreItemOut[];
  onSelect: (item: ExploreItemOut) => void;
}

export function ExploreSection({ title, items, onSelect }: ExploreSectionProps) {
  if (items.length === 0) return null;

  return (
    <div>
      <h2 className="mb-3 text-lg font-semibold text-fg">{title}</h2>
      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent">
        {items.map((item) => (
          <ExploreCard key={item.id} item={item} onSelect={onSelect} />
        ))}
      </div>
    </div>
  );
}
