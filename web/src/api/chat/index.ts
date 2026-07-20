/**
 * Chat API client for LangGraph agent communication.
 *
 * Provides endpoints for interacting with the LangGraph sync_agent,
 * including streaming support, history management, and message persistence.
 */
import { apiRequest } from "../client";

export interface ChatRequest {
  messages: Array<{ role: string; content: string }>;
  thread_id?: string;
  session_id?: string;
}

export interface ChatMessage {
  role: string;
  content: string;
}

export interface ChatResponse {
  role: string;
  content: string;
  thread_id: string;
  session_id: string;
}

export interface ChatHistoryResponse {
  messages: ChatMessage[];
  thread_id: string;
  session_id: string;
  title?: string;
}

export interface StreamEvent {
  event: string;
  data?: Record<string, unknown>;
  [key: string]: unknown;
}

export class ChatClient {
  private baseUrl: string;

  constructor(baseUrl: string = "/api") {
    this.baseUrl = baseUrl;
  }

  /**
   * Invoke the agent synchronously (single turn, no streaming).
   */
  async invoke(request: ChatRequest): Promise<ChatResponse> {
    return apiRequest<ChatResponse>("/v1/chat/invoke", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  /**
   * Stream agent events in real-time.
   * Yields JSON-parsed events as they are received.
   */
  async *streamEvents(request: ChatRequest): AsyncGenerator<StreamEvent, void, unknown> {
    const response = await fetch(`${this.baseUrl}/v1/chat/stream_events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Chat stream failed: ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error("Response body is not readable");
    }

    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete lines
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.trim()) {
            try {
              let jsonStr = line;
              // Handle both "data: " prefix and raw JSON formats
              if (line.startsWith("data: ")) {
                jsonStr = line.slice(6); // Remove "data: "
              }
              const event = JSON.parse(jsonStr);
              yield event;
            } catch (e) {
              console.error("Failed to parse event:", line, e);
            }
          }
        }
      }

      // Process remaining buffer
      if (buffer.trim()) {
        try {
          let jsonStr = buffer.trim();
          if (jsonStr.startsWith("data: ")) {
            jsonStr = jsonStr.slice(6);
          }
          const event = JSON.parse(jsonStr);
          yield event;
        } catch (e) {
          console.error("Failed to parse remaining event:", buffer, e);
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  /**
   * Get chat history for a session.
   */
  async getHistory(sessionId: string, limit: number = 50): Promise<ChatHistoryResponse> {
    return apiRequest<ChatHistoryResponse>(`/v1/chat/history/${sessionId}?limit=${limit}`, {
      method: "GET",
    });
  }

  /**
   * Clear chat history for a session.
   */
  async clearHistory(sessionId: string): Promise<void> {
    await apiRequest(`/v1/chat/history/${sessionId}`, {
      method: "DELETE",
    });
  }
}

export const chatClient = new ChatClient();
export default ChatClient;
