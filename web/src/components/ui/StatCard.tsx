import type React from "react";

interface StatCardProps {
  icon: React.ReactNode;
  iconClassName?: string;
  label: string;
  children: React.ReactNode;
  valueClassName?: string;
}

export function StatCard({
  icon,
  iconClassName = "bg-bg-muted text-fg-muted",
  label,
  children,
  valueClassName = "text-2xl font-bold text-fg",
}: StatCardProps) {
  return (
    <div className="flex items-center gap-3">
      <div className={`p-2 rounded-lg ${iconClassName}`}>{icon}</div>
      <div>
        <p className="text-sm text-fg-muted">{label}</p>
        <p className={valueClassName}>{children}</p>
      </div>
    </div>
  );
}
