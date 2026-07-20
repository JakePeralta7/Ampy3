import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { apiGet } from "../../api/client";

export function RequireServer({ children }: { children: React.ReactNode }) {
  const [configured, setConfigured] = useState<boolean | null>(null);

  useEffect(() => {
    apiGet<{ server_url: string | null }>("/plex/server")
      .then((data) => setConfigured(!!data.server_url))
      .catch(() => setConfigured(false));
  }, []);

  if (configured === null) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-accent-500" />
      </div>
    );
  }

  if (!configured) {
    return <Navigate to="/setup" replace />;
  }

  return <>{children}</>;
}
