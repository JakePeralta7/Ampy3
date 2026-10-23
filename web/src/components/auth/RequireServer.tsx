import { createContext } from "react";

interface ServerContextValue {
  configured: boolean | null;
}

const ServerContext = createContext<ServerContextValue>({ configured: null });

export function RequireServer({ children }: { children: React.ReactNode }) {
  // All protected routes are now guarded by CheckSetup at a higher level
  // This component is kept for future extensibility
  return <ServerContext.Provider value={{ configured: true }}>{children}</ServerContext.Provider>;
}
