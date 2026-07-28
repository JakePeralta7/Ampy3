import { AlertTriangle } from "lucide-react";
import type React from "react";
import { Link } from "react-router-dom";
import { useServerConfigured } from "../Auth/RequireServer";

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
  const configured = useServerConfigured();

  return (
    <div className="flex-1">
      <div className={`${maxWidthStyles[maxWidth]} mx-auto p-8`}>
        {configured === false && (
          <div className="mb-6 flex items-center gap-3 rounded-lg border border-warning-300 bg-warning-50 px-4 py-3 text-warning-800 dark:border-warning-700 dark:bg-warning-900/30 dark:text-warning-200">
            <AlertTriangle className="h-5 w-5 shrink-0" />
            <p className="text-sm">
              No media server configured.{" "}
              <Link
                to="/settings/targets"
                className="font-medium underline underline-offset-2 hover:text-warning-900 dark:hover:text-warning-100"
              >
                Set up a target
              </Link>{" "}
              to start syncing.
            </p>
          </div>
        )}
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
