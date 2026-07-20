import { type LucideIcon, Search } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

interface PaletteItem {
  to: string;
  label: string;
  icon: LucideIcon;
  parentLabel?: string;
}

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: PaletteItem[];
}

export function CommandPalette({ open, onOpenChange, items }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const filtered = items.filter((item) => {
    const search = `${item.parentLabel ?? ""} ${item.label}`.toLowerCase();
    return search.includes(query.toLowerCase());
  });

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  const handleNavigate = useCallback(
    (to: string) => {
      navigate(to);
      onOpenChange(false);
    },
    [navigate, onOpenChange],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => (i + 1) % filtered.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => (i - 1 + filtered.length) % filtered.length);
      } else if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        handleNavigate(filtered[selectedIndex].to);
      }
    },
    [filtered, selectedIndex, handleNavigate],
  );

  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0"
        onClick={() => onOpenChange(false)}
      />
      <div
        className="fixed left-1/2 top-[15vh] z-50 w-full max-w-xl -translate-x-1/2 rounded-lg border border-border bg-bg-surface shadow-lg focus:outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0 data-[state=open]:zoom-in-95 data-[state=closed]:zoom-out-95"
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
      >
        <div className="flex items-center gap-3 border-b border-border px-4">
          <Search size={18} className="shrink-0 text-fg-muted" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Go to..."
            className="h-12 w-full border-none bg-transparent text-fg placeholder:text-fg-subtle focus-visible:outline-none focus-visible:ring-0"
          />
        </div>

        {filtered.length > 0 && (
          <div className="border-t border-border pb-2 pt-1">
            <div role="listbox" className="max-h-80 overflow-y-auto">
              {filtered.map((item, index) => {
                const Icon = item.icon;
                const isSelected = index === selectedIndex;
                return (
                  <div
                    key={`${item.parentLabel ?? ""}-${item.label}`}
                    role="option"
                    aria-selected={isSelected}
                    tabIndex={-1}
                    onMouseEnter={() => setSelectedIndex(index)}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      handleNavigate(item.to);
                    }}
                    className={`mx-2 flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-sm ${
                      isSelected
                        ? "bg-accent-50 text-accent-700"
                        : "text-fg-muted hover:bg-bg-muted hover:text-fg"
                    }`}
                  >
                    <Icon size={18} className="shrink-0" />
                    {item.parentLabel && (
                      <>
                        <span className="text-fg-muted">{item.parentLabel}</span>
                        <span className="mx-1 text-fg-muted">&rarr;</span>
                      </>
                    )}
                    <span>{item.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {filtered.length === 0 && query && (
          <div className="border-t border-border px-6 py-8 text-center text-sm text-fg-muted">
            No results found.
          </div>
        )}
      </div>
    </>
  );
}
