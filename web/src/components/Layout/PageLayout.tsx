import type React from "react";

interface PageLayoutProps {
  title: string;
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
  subtitle,
  actions,
  maxWidth = "lg",
  children,
}: PageLayoutProps) {
  return (
    <div className="flex-1">
      <div className={`${maxWidthStyles[maxWidth]} mx-auto p-8`}>
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold mb-2 text-fg">{title}</h1>
            {subtitle && <p className="text-fg-muted">{subtitle}</p>}
          </div>
          {actions}
        </div>
        {children}
      </div>
    </div>
  );
}
