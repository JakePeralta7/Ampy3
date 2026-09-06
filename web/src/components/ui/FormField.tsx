import { useState } from "react";
import { INPUT_STYLES } from "../../lib/styles";

interface FormFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: "text" | "password" | "number" | "textarea";
  placeholder?: string;
  secretSet?: boolean;
  rows?: number;
}

export function FormField({
  id,
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  secretSet,
  rows = 3,
}: FormFieldProps) {
  const [focused, setFocused] = useState(false);
  const masked = secretSet && !value && !focused;

  const inputProps = {
    id,
    value: masked ? "••••••••••••••••••••" : value,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      onChange(e.target.value),
    onFocus: () => setFocused(true),
    onBlur: () => setFocused(false),
    placeholder,
    className: `${INPUT_STYLES} ${type === "textarea" ? "font-mono resize-y" : ""} ${
      masked ? "text-fg-subtle" : ""
    }`,
  };

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-fg-muted">
        {label}
      </label>
      {type === "textarea" ? (
        <textarea {...inputProps} rows={rows} />
      ) : (
        <input type={type === "password" ? (masked ? "text" : "password") : type} {...inputProps} />
      )}
    </div>
  );
}
