import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";

export interface ChatSessionEntry {
  id: string;
  preview: string;
  updatedAt: number;
}

interface ChatSessionContextValue {
  sessions: ChatSessionEntry[];
  addOrUpdateSession: (id: string, preview: string) => void;
  removeSession: (id: string) => void;
}

const STORAGE_KEY = "ampy3:chat-sessions";

function loadSessions(): ChatSessionEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as ChatSessionEntry[];
  } catch {
    return [];
  }
}

const ChatSessionContext = createContext<ChatSessionContextValue | null>(null);

export function ChatSessionProvider({ children }: { children: ReactNode }) {
  const [sessions, setSessions] = useState<ChatSessionEntry[]>(loadSessions);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch {
      /* ignore */
    }
  }, [sessions]);

  const addOrUpdateSession = useCallback((id: string, preview: string) => {
    setSessions((prev) => {
      const filtered = prev.filter((s) => s.id !== id);
      return [{ id, preview, updatedAt: Date.now() }, ...filtered].slice(0, 20);
    });
  }, []);

  const removeSession = useCallback((id: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  return (
    <ChatSessionContext.Provider value={{ sessions, addOrUpdateSession, removeSession }}>
      {children}
    </ChatSessionContext.Provider>
  );
}

export function useChatSessions() {
  const ctx = useContext(ChatSessionContext);
  if (!ctx) throw new Error("useChatSessions must be used within ChatSessionProvider");
  return ctx;
}
