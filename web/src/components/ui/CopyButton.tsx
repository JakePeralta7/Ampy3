import { Check, Copy } from "lucide-react";
import { useCallback, useState } from "react";

interface CopyButtonProps {
  value: string;
  label?: string;
}

export function CopyButton({ value, label }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      try {
        await navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      } catch {
        // clipboard not available
      }
    },
    [value],
  );

  if (!value) return null;

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1 text-xs text-fg-subtle hover:text-fg-muted transition-all shrink-0 opacity-0 group-hover:opacity-100"
      title={`Copy ${label || value}`}
    >
      {copied ? <Check size={14} className="text-success-500" /> : <Copy size={14} />}
    </button>
  );
}
