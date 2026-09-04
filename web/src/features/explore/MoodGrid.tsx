import type { MoodCategoryOut } from "../../api/explore";

interface MoodGridProps {
  moods: MoodCategoryOut[];
  selectedMoodId: string | null;
  onSelect: (moodId: string | null) => void;
}

const moodColors = [
  "bg-blue-500/10 text-blue-400 border-blue-500/30 hover:bg-blue-500/20",
  "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20",
  "bg-purple-500/10 text-purple-400 border-purple-500/30 hover:bg-purple-500/20",
  "bg-amber-500/10 text-amber-400 border-amber-500/30 hover:bg-amber-500/20",
  "bg-rose-500/10 text-rose-400 border-rose-500/30 hover:bg-rose-500/20",
  "bg-cyan-500/10 text-cyan-400 border-cyan-500/30 hover:bg-cyan-500/20",
  "bg-pink-500/10 text-pink-400 border-pink-500/30 hover:bg-pink-500/20",
  "bg-lime-500/10 text-lime-400 border-lime-500/30 hover:bg-lime-500/20",
];

export function MoodGrid({ moods, selectedMoodId, onSelect }: MoodGridProps) {
  if (moods.length === 0) return null;

  return (
    <div>
      <h2 className="mb-3 text-lg font-semibold text-fg">Moods & Genres</h2>
      <div className="flex flex-wrap gap-2">
        {moods.map((mood, i) => {
          const selected = mood.id === selectedMoodId;
          return (
            <button
              key={mood.id}
              onClick={() => onSelect(selected ? null : mood.id)}
              className={`rounded-full border px-4 py-1.5 text-sm transition-colors duration-fast focus-visible:ring-2 focus-visible:ring-border-focus focus-visible:outline-none ${
                selected
                  ? "bg-accent-500 text-accent-fg border-accent-500"
                  : moodColors[i % moodColors.length]
              }`}
            >
              {mood.name}
            </button>
          );
        })}
      </div>
    </div>
  );
}
