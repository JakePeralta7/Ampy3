import { useParams } from "react-router-dom";
import { AgentChatUI } from "../components/Chat/AgentChatWrapper";

export function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>();

  return (
    <div className="flex-1 flex flex-col">
      <AgentChatUI key={sessionId} sessionId={sessionId} />
    </div>
  );
}
