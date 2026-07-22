import { createContext, type ReactNode, useContext, useEffect, useState } from "react";
import { apiPost } from "../api/client";

export interface AuthUser {
  plex_user_id: string;
  username: string;
  email: string | null;
  thumb: string | null;
}

interface AuthContextValue {
  user: AuthUser | null;
  requireAuth: boolean;
  loading: boolean;
  login: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  requireAuth: true,
  loading: true,
  login: () => {},
  logout: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [requireAuth, setRequireAuth] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/auth/me", { credentials: "include" })
      .then((res) => {
        if (res.ok) return res.json();
        throw new Error("unauthenticated");
      })
      .then((data) => {
        setUser(data);
        setRequireAuth(data.require_auth ?? true);
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = () => {
    window.location.href = "/api/auth/plex/login";
  };

  const logout = async () => {
    try {
      await apiPost("/auth/logout");
    } catch {
      // cookie may already be cleared
    }
    setUser(null);
    window.location.href = "/login";
  };

  return (
    <AuthContext.Provider value={{ user, requireAuth, loading, login, logout }}>{children}</AuthContext.Provider>
  );
}
