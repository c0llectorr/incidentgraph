import { useEffect, useRef } from "react";
import type { ChatMessage } from "./MessageBubble";
import MessageBubble from "./MessageBubble";

interface MessageListProps {
  messages: ChatMessage[];
  pending: boolean;
  onOpenCitation: (citation: import("../../types/api").SourceCitation) => void;
}

export default function MessageList({ messages, pending, onOpenCitation }: MessageListProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, pending]);

  return (
    <div className="flex flex-col gap-5 overflow-y-auto px-1 py-2" aria-live="polite">
      {messages.map((message, index) => (
        <MessageBubble key={index} message={message} onOpenCitation={onOpenCitation} />
      ))}
      {pending ? (
        <div className="flex items-center gap-2 text-xs text-ig-muted" role="status">
          <span className="h-2 w-2 animate-pulse rounded-full bg-ig-blue" aria-hidden />
          Retrieving evidence and composing an answer…
        </div>
      ) : null}
      <div ref={endRef} />
    </div>
  );
}
