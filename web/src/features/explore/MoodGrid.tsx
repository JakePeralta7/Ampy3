import type { MoodCategoryOut } from "../../api/explore";

interface MoodGridProps {
  moods: MoodCategoryOut[];
  selectedMoodId: string | null;
  onSelect: (moodId: string | null) => void;
  isCompact?: boolean;
}

const gradients = [
  "from-blue-600 to-indigo-700",
  "from-emerald-600 to-teal-700",
  "from-purple-600 to-fuchsia-700",
  "from-amber-500 to-orange-600",
  "from-rose-600 to-red-700",
  "from-cyan-500 to-sky-600",
  "from-pink-500 to-rose-600",
  "from-lime-600 to-green-700",
  "from-violet-600 to-purple-700",
  "from-orange-500 to-amber-600",
];

function gradientFor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  }
  return gradients[hash % gradients.length];
}

export function MoodGrid({ moods, selectedMoodId, onSelect, isCompact }: MoodGridProps) {
  if (moods.length === 0) return null;

  if (isCompact) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        {moods.map((mood) => {
          const selected = mood.id === selectedMoodId;
          return (
            <button
              key={mood.id}
              onClick={() => onSelect(selected ? null : mood.id)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                selected
                  ? "border-accent-500 bg-accent-500 text-white"
                  : "border-border bg-bg-surface text-fg-muted hover:border-accent-500 hover:text-fg"
              }`}
            >
              {mood.name}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <section>
      <h2 className="mb-4 text-xl font-bold text-fg">Moods & Genres</h2>
      <div className="flex flex-wrap gap-3">
        {moods.map((mood) => {
          const selected = mood.id === selectedMoodId;
          return (
            <button
              key={mood.id}
              onClick={() => onSelect(selected ? null : mood.id)}
              className={`relative flex h-24 w-40 shrink-0 flex-col justify-end overflow-hidden rounded-lg bg-gradient-to-br p-3 text-left text-white transition-transform duration-fast hover:scale-[1.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus ${gradientFor(
                mood.name,
              )} ${selected ? "ring-2 ring-accent-500 ring-offset-2 ring-offset-bg-app" : ""}`}
            >
              {mood.icon && (
                <img
                  src={mood.icon}
                  alt=""
                  className="absolute inset-0 h-full w-full object-cover opacity-30"
                />
              )}
              <span className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
              <span className="relative text-sm font-semibold drop-shadow-sm">{mood.name}</span>
              {mood.playlist_count != null && (
                <span className="relative text-xs text-white/80">
                  {mood.playlist_count} playlists
                </span>
              )}
            </button>
          );
        })}
      </div>
    </section>
  );
}
