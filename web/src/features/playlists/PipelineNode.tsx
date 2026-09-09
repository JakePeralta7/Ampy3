import { CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";
import type { ReactNode } from "react";

export type PipelineStatus = "pending" | "running" | "success" | "failed";

interface StatusStyle {
  icon: ReactNode;
  className: string;
  label: string;
}

const STATUS_STYLES: Record<PipelineStatus, StatusStyle> = {
  running: {
    icon: <Loader2 size={12} className="animate-spin" />,
    className: "text-warning-800",
    label: "Running",
  },
  success: {
    icon: <CheckCircle2 size={12} />,
    className: "text-success-500",
    label: "Completed",
  },
  failed: {
    icon: <XCircle size={12} />,
    className: "text-danger-500",
    label: "Failed",
  },
  pending: {
    icon: <Clock size={12} />,
    className: "text-fg-muted",
    label: "Pending",
  },
};

interface PipelineNodeProps {
  title: string;
  subtitle?: string;
  status: PipelineStatus;
  icon: ReactNode;
}

export function PipelineNode({ title, subtitle, status, icon }: PipelineNodeProps) {
  const style = STATUS_STYLES[status];
  return (
    <div className="flex items-center gap-2.5 px-3 py-2 bg-bg-surface border border-border rounded-lg">
      <span className="text-fg-muted shrink-0">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-fg truncate">{title}</div>
        {subtitle && <div className="text-xs text-fg-muted truncate">{subtitle}</div>}
      </div>
      <span
        className={`inline-flex items-center gap-1 text-xs font-medium shrink-0 ${style.className}`}
      >
        {style.icon}
        {style.label}
      </span>
    </div>
  );
}
