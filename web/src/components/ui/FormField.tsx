import { useState } from "react";
import { INPUT_STYLES } from "../../lib/styles";

interface FormFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: "text" | "password" | "number";
  placeholder?: string;
  secretSet?: boolean;
}

export function FormField({
  id,
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  secretSet,
}: FormFieldProps) {
  const [focused, setFocused] = useState(false);
  const masked = secretSet && !value && !focused;

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-fg-muted">
        {label}
      </label>
      <input
        id={id}
        type={type === "password" ? (masked ? "text" : "password") : type}
        value={masked ? "••••••••••••••••••••" : value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder={placeholder}
        className={`${INPUT_STYLES} ${masked ? "text-fg-subtle" : ""}`}
      />
    </div>
  );
}
