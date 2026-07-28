import { createContext, useContext, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { getConfiguredTargets } from "../../api/settings";

interface ServerContextValue {
  configured: boolean | null;
}

const ServerContext = createContext<ServerContextValue>({ configured: null });

export function useServerConfigured() {
  return useContext(ServerContext).configured;
}

export function RequireServer({ children }: { children: React.ReactNode }) {
  const [configured, setConfigured] = useState<boolean | null>(null);

  useEffect(() => {
    getConfiguredTargets()
      .then((targets) => setConfigured(targets.length > 0))
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
    return <Navigate to="/plex-setup" replace />;
  }

  return <ServerContext.Provider value={{ configured }}>{children}</ServerContext.Provider>;
}
