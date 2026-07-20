import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "ampy3:chat-sessions";

export interface ChatSessionEntry {
  id: string;
  preview: string;
  updatedAt: number;
}

function loadSessions(): ChatSessionEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as ChatSessionEntry[];
  } catch {
    return [];
  }
}

function saveSessions(sessions: ChatSessionEntry[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    /* ignore */
  }
}

export function useChatSessions() {
  const [sessions, setSessions] = useState<ChatSessionEntry[]>(loadSessions);

  useEffect(() => {
    saveSessions(sessions);
  }, [sessions]);

  const addSession = useCallback((id: string, preview: string) => {
    setSessions((prev) => {
      const filtered = prev.filter((s) => s.id !== id);
      return [{ id, preview, updatedAt: Date.now() }, ...filtered].slice(0, 20);
    });
  }, []);

  const removeSession = useCallback((id: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  return { sessions, addSession, removeSession };
}
