import { useParams } from "react-router-dom";
import { AgentChatUI } from "../components/Chat/AgentChatWrapper";

export function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>();

  return (
    <div className="h-full flex flex-col">
      <AgentChatUI key={sessionId} sessionId={sessionId} />
    </div>
  );
}
