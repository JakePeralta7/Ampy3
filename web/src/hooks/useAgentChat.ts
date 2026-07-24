import { useCallback, useEffect, useRef, useState } from "react";
import { chatClient } from "../api/chat";
import { generateId, getErrorMessage } from "../lib/utils";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  thinking?: string;
  flowItems?: FlowItem[];
}

export interface FlowItem {
  id: string;
  type: "tool_call";
  name?: string;
  args?: Record<string, unknown>;
  result?: unknown;
  status?: "pending" | "completed" | "failed";
  content?: string;
}

export interface UseAgentChatOptions {
  sessionId?: string;
  autoLoadHistory?: boolean;
}

interface HistoryMessage {
  role: string;
  content: string;
  flow_items?: { name?: string; args?: Record<string, unknown>; result?: string; status?: string }[];
}

interface StreamEvent {
  event: string;
  data?: Record<string, unknown>;
  run_id?: string;
  name?: string;
}

interface ChainEndOutput {
  messages?: { type: string; content: string }[];
}

const isChainEndOutput = (output: unknown): output is ChainEndOutput =>
  typeof output === "object" && output !== null && "messages" in output;

const isStreamEventWithData = (
  event: StreamEvent,
): event is StreamEvent & { data: Record<string, unknown> } => event.data !== undefined;

const getRunId = (event: StreamEvent): string => {
  if (event.run_id) return event.run_id;
  if (
    isStreamEventWithData(event) &&
    event.data.metadata &&
    typeof event.data.metadata === "object"
  ) {
    const metadata = event.data.metadata as Record<string, unknown>;
    if (typeof metadata.run_id === "string") return metadata.run_id;
  }
  return generateId();
};

const getToolName = (event: StreamEvent): string => {
  if (event.name) return event.name;
  if (isStreamEventWithData(event) && event.data.input && typeof event.data.input === "object") {
    const input = event.data.input as Record<string, unknown>;
    if (typeof input.name === "string") return input.name;
  }
  return "unknown";
};

const getToolInput = (event: StreamEvent): Record<string, unknown> => {
  if (isStreamEventWithData(event) && event.data.input && typeof event.data.input === "object") {
    return event.data.input as Record<string, unknown>;
  }
  return {};
};

export function useAgentChat(options: UseAgentChatOptions = {}) {
  const { sessionId: initialSessionId, autoLoadHistory = true } = options;

  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState(initialSessionId || generateId());
  const [sessionTitle, setSessionTitle] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const flowItemsRef = useRef<FlowItem[]>([]);
  const currentAssistantMessageIdRef = useRef<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Save/restore streaming content to sessionStorage for recovery on page refresh
  const saveStreamingContent = useCallback((content: string) => {
    try {
      sessionStorage.setItem(`streaming_${sessionId}`, content);
    } catch {
      // Ignore sessionStorage errors
    }
  }, [sessionId]);

  const getStreamingContent = useCallback((): string | null => {
    try {
      return sessionStorage.getItem(`streaming_${sessionId}`);
    } catch {
      return null;
    }
  }, [sessionId]);

  const clearStreamingContent = useCallback(() => {
    try {
      sessionStorage.removeItem(`streaming_${sessionId}`);
    } catch {
      // Ignore errors
    }
  }, [sessionId]);

  const loadHistory = useCallback(async () => {
    try {
      const history = await chatClient.getHistory(sessionId);
      const loadedMessages: Message[] = history.messages.map(
        (msg: HistoryMessage, idx: number) => ({
          id: `hist-${idx}`,
          role: msg.role === "user" ? ("user" as const) : ("assistant" as const),
          content: msg.content,
          timestamp: 0,
          flowItems:
            msg.flow_items && msg.flow_items.length > 0
              ? msg.flow_items.map((fi, fiIdx) => ({
                  id: `hist-fi-${idx}-${fiIdx}`,
                  type: "tool_call" as const,
                  name: fi.name,
                  args: fi.args,
                  result: fi.result,
                  status: fi.status as FlowItem["status"],
                }))
              : undefined,
        }),
      );

      // Check if there's streaming content that wasn't persisted yet
      const streamingContent = getStreamingContent();
      if (streamingContent && streamingContent.trim()) {
        const hasStreamingMessage = loadedMessages.some(
          (m) => m.role === "assistant" && m.content === streamingContent,
        );
        if (!hasStreamingMessage) {
          // Add the streaming content as if it was partially persisted
          loadedMessages.push({
            id: `streaming-${Date.now()}`,
            role: "assistant",
            content: streamingContent,
            timestamp: Date.now(),
          });
          console.debug(`Recovered streaming content from sessionStorage: ${streamingContent.length} chars`);
        }
      }

      setMessages(loadedMessages);
      if (history.title) {
        setSessionTitle(history.title);
      }
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load chat history"));
    }
  }, [sessionId, getStreamingContent]);

  useEffect(() => {
    if (autoLoadHistory && sessionId) {
      loadHistory();
    }
  }, [sessionId, autoLoadHistory, loadHistory]);

  const updateOrCreateAssistantMessage = useCallback((content: string = "") => {
    if (!currentAssistantMessageIdRef.current) {
      const messageId = generateId();
      currentAssistantMessageIdRef.current = messageId;
      const newMessage: Message = {
        id: messageId,
        role: "assistant",
        content,
        timestamp: Date.now(),
        flowItems: flowItemsRef.current.length > 0 ? [...flowItemsRef.current] : undefined,
      };
      setMessages((prev) => [...prev, newMessage]);
      // Save to sessionStorage for recovery
      if (content) {
        saveStreamingContent(content);
      }
    } else {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === currentAssistantMessageIdRef.current
            ? {
                ...msg,
                content: content || msg.content,
                flowItems: flowItemsRef.current.length > 0 ? [...flowItemsRef.current] : undefined,
              }
            : msg,
        ),
      );
      // Update sessionStorage
      if (content) {
        saveStreamingContent(content);
      }
    }
  }, [saveStreamingContent]);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim()) return;

      setError(null);
      setIsLoading(true);
      flowItemsRef.current = [];
      currentAssistantMessageIdRef.current = null;

      const userMessage: Message = {
        id: generateId(),
        role: "user",
        content,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMessage]);

      let assistantContent = "";

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      try {
        const eventStream = chatClient.streamEvents({
          messages: [{ role: "user", content }],
          thread_id: sessionId,
          session_id: sessionId,
        });

        for await (const event of eventStream) {
          if (abortControllerRef.current.signal.aborted) {
            break;
          }

          if (event.event === "on_tool_start") {
            const flowItem: FlowItem = {
              id: getRunId(event),
              type: "tool_call",
              name: getToolName(event),
              args: getToolInput(event),
              status: "pending",
            };

            flowItemsRef.current.push(flowItem);
            updateOrCreateAssistantMessage();
          }

          if (event.event === "on_tool_end") {
            const runId = getRunId(event);
            const result = event.data?.output;

            const toolItem = flowItemsRef.current.find((item) => item.id === runId);
            if (toolItem) {
              toolItem.status = "completed";
              toolItem.result = result;
              updateOrCreateAssistantMessage();
            }
          }

          if (event.event === "on_tool_error") {
            const runId = getRunId(event);

            const toolItem = flowItemsRef.current.find((item) => item.id === runId);
            if (toolItem) {
              toolItem.status = "failed";
              updateOrCreateAssistantMessage();
            }
          }

          if (event.event === "on_chat_model_stream") {
            const chunk = event.data?.chunk;
            if (typeof chunk === "string") {
              assistantContent += chunk;
            } else if (
              chunk &&
              typeof chunk === "object" &&
              typeof (chunk as Record<string, unknown>).content === "string"
            ) {
              assistantContent += (chunk as Record<string, unknown>).content;
            } else if (event.data?.output && typeof event.data.output === "string") {
              assistantContent += event.data.output;
            }
            if (assistantContent) {
              updateOrCreateAssistantMessage(assistantContent);
            }
          }

          if (event.event === "on_chain_end" && isChainEndOutput(event.data?.output)) {
            const output = event.data.output;
            if (output.messages && output.messages.length > 0) {
              const lastMessage = output.messages[output.messages.length - 1];
              if (lastMessage.type === "ai" && lastMessage.content) {
                assistantContent = lastMessage.content;
                updateOrCreateAssistantMessage(assistantContent);
              }
            }
          }

          if (event.event === "on_title") {
            const title = event.data?.title;
            if (typeof title === "string") {
              setSessionTitle(title);
            }
          }
        }

        if (assistantContent || flowItemsRef.current.length > 0) {
          updateOrCreateAssistantMessage(assistantContent);
        }

        // Clear streaming content from sessionStorage once successfully persisted
        clearStreamingContent();
      } catch (err) {
        if (!(err instanceof Error && err.name === "AbortError")) {
          setError(getErrorMessage(err, "Failed to send message"));
        }
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, updateOrCreateAssistantMessage, clearStreamingContent],
  );

  const clearHistory = useCallback(async () => {
    try {
      await chatClient.clearHistory(sessionId);
      setMessages([]);
      setError(null);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to clear history"));
    }
  }, [sessionId]);

  const resetSession = useCallback(() => {
    setSessionId(generateId());
    setMessages([]);
    setError(null);
    flowItemsRef.current = [];
    currentAssistantMessageIdRef.current = null;
  }, []);

  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsLoading(false);
    }
  }, []);

  return {
    messages,
    sessionId,
    isLoading,
    error,
    sendMessage,
    clearHistory,
    resetSession,
    setSessionId,
    stopStreaming,
    sessionTitle,
  };
}
