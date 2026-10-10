/**
 * Hook for managing WebSocket connections with automatic reconnection
 */

import { useCallback, useEffect, useRef, useState } from "react";

export interface WebSocketMessage {
  type: string;
  data: Record<string, unknown>;
}

export interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  retryAttempts?: number;
  retryDelay?: number;
  enabled?: boolean;
}

export interface UseWebSocketReturn {
  connected: boolean;
  error: string | null;
  lastMessage: WebSocketMessage | null;
  reconnecting: boolean;
}

const DEFAULT_RETRY_ATTEMPTS = 5;
const DEFAULT_RETRY_DELAY = 1000;
const MAX_RETRY_DELAY = 30000;

/**
 * Hook for managing WebSocket connections with automatic reconnection.
 *
 * Usage:
 * ```tsx
 * const { connected, lastMessage, error } = useWebSocket(
 *   '/api/v1/ws/syncs',
 *   {
 *     onMessage: (msg) => handleMessage(msg),
 *     retryAttempts: 5,
 *   }
 * );
 * ```
 *
 * @param endpoint - The WebSocket endpoint (e.g., '/api/v1/ws/syncs')
 * @param options - Configuration options
 * @returns Current connection state and last message
 */
export function useWebSocket(
  endpoint: string,
  options: UseWebSocketOptions = {},
): UseWebSocketReturn {
  const {
    onMessage,
    onOpen,
    onClose,
    onError,
    retryAttempts = DEFAULT_RETRY_ATTEMPTS,
    retryDelay = DEFAULT_RETRY_DELAY,
    enabled = true,
  } = options;

  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [reconnecting, setReconnecting] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!enabled) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      setReconnecting(true);
      setError(null);

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${protocol}//${window.location.host}${endpoint}`;

      const ws = new WebSocket(url);

      ws.onopen = () => {
        if (!isMountedRef.current) return;
        setConnected(true);
        setReconnecting(false);
        retryCountRef.current = 0;
        setError(null);
        onOpen?.();
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);
          onMessage?.(message);
        } catch (err) {
          console.error("Failed to parse WebSocket message:", err);
        }
      };

      ws.onerror = (event) => {
        if (!isMountedRef.current) return;
        console.error("WebSocket error:", event);
        setError("Connection error");
        onError?.(event);
      };

      ws.onclose = () => {
        if (!isMountedRef.current) return;
        setConnected(false);
        onClose?.();

        // Attempt to reconnect with exponential backoff
        if (retryCountRef.current < retryAttempts) {
          retryCountRef.current += 1;
          const delay = Math.min(retryDelay * 2 ** (retryCountRef.current - 1), MAX_RETRY_DELAY);
          retryTimeoutRef.current = setTimeout(() => {
            if (isMountedRef.current) {
              connect();
            }
          }, delay);
        } else {
          setError("Max reconnection attempts reached");
        }
      };

      wsRef.current = ws;
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Connection failed";
      setError(errorMsg);
      setReconnecting(false);
    }
  }, [endpoint, enabled, onMessage, onOpen, onClose, onError, retryAttempts, retryDelay]);

  // Connect on mount
  useEffect(() => {
    isMountedRef.current = true;
    if (enabled) {
      connect();
    }

    return () => {
      isMountedRef.current = false;
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, enabled]);

  return {
    connected,
    error,
    lastMessage,
    reconnecting,
  };
}
