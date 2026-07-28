import {
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  Loader2,
  RefreshCw,
  Send,
  Square,
  Trash2,
  User,
  Wrench,
  X,
} from "lucide-react";
import type { ComponentProps } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Components } from "react-markdown";
import Markdown from "react-markdown";
import { useNavigate } from "react-router-dom";
import { useChatSessions } from "../../contexts/ChatSessionContext";
import { type FlowItem, type Message, useAgentChat } from "../../hooks/useAgentChat";
import { generateId } from "../../lib/utils";
import { Button } from "../ui/Button";
import { ConfirmDialog } from "../ui/ConfirmDialog";

export interface AgentChatUIProps {
  title?: string;
  initialMessage?: string;
  sessionId?: string;
  onSessionChange?: (sessionId: string) => void;
  autoLoadHistory?: boolean;
  className?: string;
}

function MarkdownParagraph({ children }: ComponentProps<"p">) {
  return <p className="text-sm mb-2 last:mb-0">{children}</p>;
}

function MarkdownInlineCode({ children }: ComponentProps<"code">) {
  return (
    <code className="bg-bg-muted px-1.5 py-0.5 rounded-sm text-xs font-mono text-fg">
      {children}
    </code>
  );
}

function MarkdownCodeBlock({ children }: ComponentProps<"pre">) {
  return (
    <pre className="bg-bg-inset text-fg p-2 rounded-sm overflow-auto text-xs">
      <code>{children}</code>
    </pre>
  );
}

function MarkdownList({ children }: ComponentProps<"ul">) {
  return <ul className="list-disc list-inside text-sm space-y-1">{children}</ul>;
}

function MarkdownOrderedList({ children }: ComponentProps<"ol">) {
  return <ol className="list-decimal list-inside text-sm space-y-1">{children}</ol>;
}

function MarkdownListItem({ children }: ComponentProps<"li">) {
  return <li className="text-sm">{children}</li>;
}

function MarkdownBlockquote({ children }: ComponentProps<"blockquote">) {
  return (
    <blockquote className="border-l-4 border-fg-muted/30 pl-3 text-sm italic">
      {children}
    </blockquote>
  );
}

const markdownComponents: Components = {
  p: MarkdownParagraph,
  code: function Code({ className, children }: ComponentProps<"code">) {
    const isInline = !className;
    if (isInline) {
      return <MarkdownInlineCode>{children}</MarkdownInlineCode>;
    }
    return <MarkdownCodeBlock>{children}</MarkdownCodeBlock>;
  },
  ul: MarkdownList,
  ol: MarkdownOrderedList,
  li: MarkdownListItem,
  blockquote: MarkdownBlockquote,
};

function TypingIndicator() {
  return (
    <div className="flex items-center gap-2 text-fg-muted px-5">
      <div className="flex gap-1">
        <span className="h-2 w-2 rounded-full bg-fg-muted/40 animate-bounce [animation-delay:0ms]" />
        <span className="h-2 w-2 rounded-full bg-fg-muted/40 animate-bounce [animation-delay:150ms]" />
        <span className="h-2 w-2 rounded-full bg-fg-muted/40 animate-bounce [animation-delay:300ms]" />
      </div>
    </div>
  );
}

export const AgentChatUI: React.FC<AgentChatUIProps> = ({
  title = "Ampy3 Assistant",
  initialMessage = "How can I help you with your music playlists?",
  sessionId: propSessionId,
  onSessionChange,
  autoLoadHistory = true,
  className = "",
}) => {
  const {
    messages,
    sessionId,
    isLoading,
    error,
    sendMessage,
    clearHistory,
    stopStreaming,
    sessionTitle,
  } = useAgentChat({ autoLoadHistory, sessionId: propSessionId });

  const navigate = useNavigate();
  const { addOrUpdateSession, removeSession: removeChatSession } = useChatSessions();
  const [input, setInput] = useState("");
  const [expandedFlowItems, setExpandedFlowItems] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const hasTrackedRef = useRef(false);

  // Track this session in the nav sidebar
  useEffect(() => {
    if (sessionId && (sessionTitle || messages.length > 0) && !hasTrackedRef.current) {
      hasTrackedRef.current = true;
      const preview =
        sessionTitle || messages.find((m) => m.role === "user")?.content.slice(0, 60) || "New chat";
      addOrUpdateSession(sessionId, preview);
    }
  }, [sessionId, sessionTitle, messages, addOrUpdateSession]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    onSessionChange?.(sessionId);
  }, [sessionId, onSessionChange]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      await sendMessage(input);
      setInput("");
      inputRef.current?.focus();
      // Reset textarea height
      if (inputRef.current) {
        inputRef.current.style.height = "auto";
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(e);
    }
  };

  const autoResize = useCallback(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  const handleNewSession = () => {
    const newId = generateId();
    navigate(`/chat/${newId}`);
  };

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleDeleteSession = async () => setShowDeleteConfirm(true);
  const confirmDeleteSession = async () => {
    setShowDeleteConfirm(false);
    await clearHistory();
    removeChatSession(sessionId);
    navigate("/chat");
  };

  const toggleFlowItemExpanded = (id: string) => {
    setExpandedFlowItems((prev) => {
      const updated = new Set(prev);
      if (updated.has(id)) {
        updated.delete(id);
      } else {
        updated.add(id);
      }
      return updated;
    });
  };

  return (
    <div className={`flex flex-col h-full bg-gradient-to-b from-bg-app to-bg-muted ${className}`}>
      <div className="border-b border-border bg-bg-surface shadow-sm">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Bot size={24} className="text-accent-500" />
              <div>
                <h1 className="text-xl font-bold text-fg">{sessionTitle || title}</h1>
                <p className="text-xs text-fg-muted">{sessionId.substring(0, 8)}...</p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                icon={<Trash2 size={16} />}
                onClick={handleDeleteSession}
              >
                Delete
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<RefreshCw size={16} />}
                onClick={handleNewSession}
              >
                New
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto" aria-live="polite" aria-relevant="additions text">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
          {messages.length === 0 && !isLoading ? (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <Bot size={48} className="text-accent-500/30 mb-4" />
              <p className="text-fg-muted text-lg">{initialMessage}</p>
              <p className="text-fg-subtle text-sm mt-2">
                Ask me about your playlists, or type a command to get started.
              </p>
            </div>
          ) : (
            messages.map((message) => (
              <div key={message.id}>
                {message.role === "assistant" &&
                  message.flowItems &&
                  message.flowItems.length > 0 && (
                    <div className="mb-3 space-y-2 ml-12">
                      {message.flowItems.map((item) => (
                        <FlowItemDisplay
                          key={item.id}
                          item={item}
                          isExpanded={expandedFlowItems.has(item.id)}
                          onToggle={() => toggleFlowItemExpanded(item.id)}
                        />
                      ))}
                    </div>
                  )}
                <MessageBubble message={message} />
              </div>
            ))
          )}

          {isLoading && !messages[messages.length - 1]?.content && (
            <div className="flex items-start gap-3">
              <div className="h-8 w-8 rounded-full bg-accent-500/10 flex items-center justify-center shrink-0 mt-0.5">
                <Bot size={16} className="text-accent-500" />
              </div>
              <div className="bg-bg-surface border border-border rounded-lg rounded-bl-none p-4">
                <TypingIndicator />
              </div>
            </div>
          )}

          {error && (
            <div
              className="bg-danger-500/10 border border-danger-500/30 rounded-lg p-4 text-danger-500 text-sm"
              role="alert"
            >
              <p className="font-medium">Error</p>
              <p>{error}</p>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="border-t border-border bg-bg-surface shrink-0">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <form onSubmit={handleSendMessage} className="flex gap-3 items-end">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  autoResize();
                }}
                onKeyDown={handleKeyDown}
                placeholder="Type a message..."
                className="w-full px-4 py-2.5 pr-10 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-border-focus focus:border-transparent resize-none bg-bg-surface text-fg placeholder-fg-subtle text-sm leading-relaxed"
                rows={1}
                disabled={isLoading}
              />
            </div>
            {isLoading ? (
              <Button
                type="button"
                variant="secondary"
                icon={<Square size={16} />}
                onClick={stopStreaming}
                className="shrink-0"
              >
                Stop
              </Button>
            ) : (
              <Button
                type="submit"
                disabled={!input.trim()}
                icon={<Send size={16} />}
                className="shrink-0"
              >
                Send
              </Button>
            )}
          </form>
        </div>
      </div>

      <ConfirmDialog
        open={showDeleteConfirm}
        title="Delete chat session"
        message="Are you sure you want to delete this chat session? This cannot be undone."
        confirmLabel="Delete"
        variant="danger"
        onConfirm={confirmDeleteSession}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </div>
  );
};

const MessageBubble: React.FC<{ message: Message }> = ({ message }) => {
  const isUser = message.role === "user";

  return (
    <div className={`flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`h-8 w-8 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
          isUser ? "bg-accent-500 text-accent-fg" : "bg-bg-muted text-fg-muted"
        }`}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>
      <div
        className={`max-w-2xl px-4 py-3 rounded-lg ${
          isUser
            ? "bg-accent-500 text-accent-fg rounded-tr-none"
            : "bg-bg-surface text-fg border border-border rounded-tl-none"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap text-sm">{message.content}</p>
        ) : (
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <Markdown components={markdownComponents}>{message.content}</Markdown>
          </div>
        )}
      </div>
    </div>
  );
};

const FlowItemDisplay: React.FC<{
  item: FlowItem;
  isExpanded: boolean;
  onToggle: () => void;
}> = ({ item, isExpanded, onToggle }) => {
  const statusStyles: Record<string, string> = {
    pending: "bg-warning-50/5 border-warning-300/30 text-warning-700",
    completed: "bg-success-500/5 border-success-500/30 text-success-500",
    failed: "bg-danger-500/5 border-danger-500/30 text-danger-500",
  };

  const statusIcons: Record<string, React.ReactNode> = {
    pending: <Loader2 size={14} className="animate-spin" />,
    completed: <Check size={14} />,
    failed: <X size={14} />,
  };

  const title = item.name || "Tool";

  const resultString =
    item.result && typeof item.result === "string"
      ? item.result
      : item.result
        ? JSON.stringify(item.result, null, 2)
        : "";

  return (
    <div
      className={`border rounded-lg overflow-hidden text-xs ${
        statusStyles[item.status || "pending"]
      }`}
    >
      <button
        onClick={onToggle}
        className="w-full px-3 py-1.5 flex items-center gap-2 hover:opacity-80 transition-opacity"
        aria-expanded={isExpanded}
      >
        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="shrink-0">{statusIcons[item.status || "pending"]}</span>
        <Wrench size={14} className="shrink-0" />
        <span className="font-medium flex-1 text-left">{title}</span>
      </button>

      {isExpanded && (
        <div className="border-t border-current/20 px-3 py-2 space-y-2">
          {item.type === "tool_call" && item.args && (
            <>
              <div>
                <p className="font-medium opacity-75 mb-1">Arguments:</p>
                <pre className="bg-bg-inset p-2 rounded-sm overflow-auto whitespace-pre-wrap break-words">
                  {JSON.stringify(item.args, null, 2)}
                </pre>
              </div>
              {resultString && (
                <div>
                  <p className="font-medium opacity-75 mb-1">Result:</p>
                  <pre className="bg-bg-inset p-2 rounded-sm overflow-auto whitespace-pre-wrap break-words max-h-48">
                    {resultString}
                  </pre>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default AgentChatUI;
