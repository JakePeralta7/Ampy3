import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { chatClient } from "../api/chat";

export interface ChatSessionEntry {
  id: string;
  preview: string;
  created_at: number;
  updatedAt: number;
}

interface ChatSessionContextValue {
  sessions: ChatSessionEntry[];
  addOrUpdateSession: (id: string, preview: string) => void;
  removeSession: (id: string) => void;
  loading: boolean;
}

const ChatSessionContext = createContext<ChatSessionContextValue | null>(null);

export function ChatSessionProvider({ children }: { children: ReactNode }) {
  const [sessions, setSessions] = useState<ChatSessionEntry[]>([]);
  const [loading, setLoading] = useState(true);

  // Load sessions from backend on mount
  useEffect(() => {
    const loadSessions = async () => {
      try {
        setLoading(true);
        const response = await chatClient.listSessions();
        const entries: ChatSessionEntry[] = response.sessions.map((s) => ({
          id: s.id,
          preview: s.preview,
          created_at: new Date(s.created_at).getTime(),
          updatedAt: new Date(s.updated_at).getTime(),
        }));
        setSessions(entries.sort((a, b) => b.created_at - a.created_at));
      } catch (error) {
        console.error("Failed to load chat sessions:", error);
        setSessions([]);
      } finally {
        setLoading(false);
      }
    };

    loadSessions();
  }, []);

  const addOrUpdateSession = useCallback(
    async (id: string, preview: string) => {
      try {
        const existing = sessions.find((s) => s.id === id);
        if (!existing) {
          // Create new session
          const response = await chatClient.createSession({ id, preview });
          const entry: ChatSessionEntry = {
            id: response.id,
            preview: response.preview,
            created_at: new Date(response.created_at).getTime(),
            updatedAt: new Date(response.updated_at).getTime(),
          };
          setSessions((prev) => [entry, ...prev].slice(0, 20));
        } else {
          // Update existing session (update preview)
          const now = Date.now();
          const updated: ChatSessionEntry = {
            ...existing,
            preview,
            updatedAt: now,
          };
          setSessions((prev) => {
            const filtered = prev.filter((s) => s.id !== id);
            return [updated, ...filtered].sort((a, b) => b.updatedAt - a.updatedAt);
          });
        }
      } catch (error) {
        console.error("Failed to add/update session:", error);
      }
    },
    [sessions],
  );

  const removeSession = useCallback(async (id: string) => {
    try {
      await chatClient.deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
    } catch (error) {
      console.error("Failed to delete session:", error);
    }
  }, []);

  return (
    <ChatSessionContext.Provider value={{ sessions, addOrUpdateSession, removeSession, loading }}>
      {children}
    </ChatSessionContext.Provider>
  );
}

export function useChatSessions() {
  const ctx = useContext(ChatSessionContext);
  if (!ctx) throw new Error("useChatSessions must be used within ChatSessionProvider");
  return ctx;
}
