import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { apiGet } from "../../api/client";

interface ServerSettings {
  jellyfin_server_url: string;
  jellyfin_api_key: string;
  jellyfin_user_id: string;
}

export function RequireServer({ children }: { children: React.ReactNode }) {
  const [configured, setConfigured] = useState<boolean | null>(null);

  useEffect(() => {
    Promise.allSettled([
      apiGet<{ server_url: string | null }>("/plex/server"),
      apiGet<ServerSettings>("/v1/settings/"),
    ])
      .then(([plexResult, settingsResult]) => {
        const hasPlexServer =
          plexResult.status === "fulfilled" && Boolean(plexResult.value.server_url);
        const hasJellyfin =
          settingsResult.status === "fulfilled" &&
          Boolean(settingsResult.value.jellyfin_server_url?.trim()) &&
          Boolean(settingsResult.value.jellyfin_api_key?.trim()) &&
          Boolean(settingsResult.value.jellyfin_user_id?.trim());
        setConfigured(hasPlexServer || hasJellyfin);
      })
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
