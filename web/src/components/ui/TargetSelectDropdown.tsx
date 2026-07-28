import { useEffect, useRef, useState } from "react";
import { getConfiguredTargets } from "../../api/settings";
import { TARGET_LABELS } from "../../lib/constants";

interface TargetSelectDropdownProps {
  value: string[];
  onChange: (values: string[]) => void;
  disabled?: boolean;
}

export function TargetSelectDropdown({
  value,
  onChange,
  disabled = false,
}: TargetSelectDropdownProps) {
  const [availableTargets, setAvailableTargets] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchTargets = async () => {
      try {
        setLoading(true);
        const targets = await getConfiguredTargets();
        setAvailableTargets(targets);
        setError(null);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to load targets";
        setError(msg);
        setAvailableTargets([]);
      } finally {
        setLoading(false);
      }
    };

    fetchTargets();
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  const handleToggle = (target: string) => {
    if (value.includes(target)) {
      onChange(value.filter((v) => v !== target));
    } else {
      onChange([...value, target]);
    }
  };

  if (loading) {
    return (
      <div className="w-full rounded-lg border border-border bg-bg-surface px-3 py-2 text-sm text-fg-muted">
        Loading targets...
      </div>
    );
  }

  if (error || availableTargets.length === 0) {
    return (
      <div className="text-sm text-danger-500">
        {error || "No targets configured. Please set up at least one in Settings."}
      </div>
    );
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled}
        className={`w-full rounded-lg border border-border bg-bg-surface px-3 py-2 text-sm text-left text-fg focus:border-accent-500 focus:outline-none focus:ring-1 focus:ring-accent-500 transition-colors duration-fast cursor-pointer flex items-center justify-between ${
          disabled ? "opacity-50 cursor-not-allowed" : "hover:border-accent-500/50"
        } ${isOpen ? "border-accent-500 ring-1 ring-accent-500" : ""}`}
      >
        <span className="truncate">
          {value.length === 0 ? (
            <span className="text-fg-muted">Select targets...</span>
          ) : (
            value.map((v) => TARGET_LABELS[v] || v).join(", ")
          )}
        </span>
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 14l-7 7m0 0l-7-7m7 7V3"
          />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-bg-surface border border-border rounded-lg shadow-lg z-50">
          <div className="py-1 max-h-60 overflow-y-auto">
            {availableTargets.map((target) => (
              <label
                key={target}
                className="flex items-center gap-2 px-3 py-2 hover:bg-bg-elevated cursor-pointer transition-colors"
              >
                <input
                  type="checkbox"
                  checked={value.includes(target)}
                  onChange={() => handleToggle(target)}
                  disabled={disabled}
                  className="rounded border-border cursor-pointer"
                />
                <span className="text-sm text-fg">{TARGET_LABELS[target] || target}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
