import { useEffect, useState } from "react";
import { getConfiguredTargets } from "../../api/settings";
import { TARGET_LABELS } from "../../lib/constants";
import { SELECT_STYLES } from "../../lib/styles";

interface TargetSelectProps {
  value: string[];
  onChange: (values: string[]) => void;
  disabled?: boolean;
  multi?: boolean;
  required?: boolean;
}

export function TargetSelect({
  value,
  onChange,
  disabled = false,
  multi = false,
  required = false,
}: TargetSelectProps) {
  const [availableTargets, setAvailableTargets] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    if (multi) {
      const selectedOptions = Array.from(e.target.selectedOptions, (option) => option.value);
      if (selectedOptions.length > 0 || !required) {
        onChange(selectedOptions);
      }
    } else {
      onChange([e.target.value]);
    }
  };

  if (loading) {
    return (
      <select disabled className={SELECT_STYLES}>
        <option>Loading targets...</option>
      </select>
    );
  }

  if (error || availableTargets.length === 0) {
    return (
      <div className="text-sm text-danger-500">
        {error || "No targets configured. Please set up at least one in Settings."}
      </div>
    );
  }

  const selectedValue = multi ? value : value[0] || "";

  return (
    <select
      multiple={multi}
      value={selectedValue}
      onChange={handleChange}
      disabled={disabled}
      className={`${SELECT_STYLES} ${multi ? "min-h-24" : ""}`}
    >
      {!multi && <option value="">Select a target...</option>}
      {availableTargets.map((target) => (
        <option key={target} value={target}>
          {TARGET_LABELS[target] || target}
        </option>
      ))}
    </select>
  );
}
