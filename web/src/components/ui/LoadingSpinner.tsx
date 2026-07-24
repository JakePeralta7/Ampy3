import { Loader2 } from "lucide-react";

interface LoadingSpinnerProps {
  fullPage?: boolean;
  text?: string;
}

export function LoadingSpinner({ fullPage = false, text }: LoadingSpinnerProps) {
  if (fullPage) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg-app">
        <div className="flex flex-col items-center gap-3">
          <Loader2 size={32} className="animate-spin text-accent-500" />
          {text && <p className="text-sm text-fg-muted">{text}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center h-full min-h-[200px]">
      <div className="flex items-center gap-3">
        <Loader2 size={16} className="animate-spin text-fg-muted" />
        {text && <p className="text-sm text-fg-muted">{text}</p>}
      </div>
    </div>
  );
}
