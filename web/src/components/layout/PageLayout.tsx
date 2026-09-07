import type React from "react";

interface PageLayoutProps {
  title: string;
  icon?: React.ReactNode;
  subtitle?: string;
  actions?: React.ReactNode;
  maxWidth?: "md" | "lg";
  children: React.ReactNode;
}

const maxWidthStyles = {
  md: "max-w-3xl",
  lg: "max-w-7xl",
};

export function PageLayout({
  title,
  icon,
  subtitle,
  actions,
  maxWidth = "lg",
  children,
}: PageLayoutProps) {
  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="border-b border-border bg-bg-surface shrink-0">
        <div className={`${maxWidthStyles[maxWidth]} mx-auto px-8 pt-6 pb-4`}>
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              {icon}
              <div className="min-w-0">
                <h1 className="text-3xl font-bold text-fg truncate">{title}</h1>
                {subtitle && <p className="text-fg-muted">{subtitle}</p>}
              </div>
            </div>
            {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
          </div>
        </div>
      </div>
      <div className="flex-1 flex flex-col min-h-0">
        <div className={`${maxWidthStyles[maxWidth]} mx-auto p-8 w-full`}>{children}</div>
      </div>
    </div>
  );
}
