import { Bot, CircleHelp } from "lucide-react";
import type { SourceCitation } from "../../types/api";
import CitationChip from "./CitationChip";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations: SourceCitation[];
  status?: string;
  clarifyingQuestion?: string | null;
  uncertainty?: string[];
}

interface MessageBubbleProps {
  message: ChatMessage;
  onOpenCitation: (citation: SourceCitation) => void;
}

export default function MessageBubble({ message, onOpenCitation }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const insufficient = message.status === "insufficient_evidence";

  return (
    <article
      className={`flex gap-3 ${isUser ? "justify-end" : ""}`}
      aria-label={isUser ? "Your question" : "Assistant answer"}
    >
      {isUser ? (
        <div className="flex max-w-[85%] flex-col items-end gap-1.5">
          <div className="rounded-lg rounded-br-sm bg-ig-blue px-4 py-2.5 text-sm text-white">
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
        </div>
      ) : (
        <div className="flex max-w-[85%] flex-col gap-1.5">
          <div
            className={`rounded-lg rounded-bl-sm border px-4 py-2.5 text-sm ${
              insufficient
                ? "border-ig-border bg-ig-bg text-ig-muted"
                : "border-ig-border bg-ig-surface text-ig-navy"
            }`}
          >
            <div className="flex items-center gap-2">
              <Bot size={14} aria-hidden className={insufficient ? "text-ig-muted" : "text-ig-blue"} />
              <span className="sr-only">{isUser ? "You asked" : "Assistant answered"}</span>
              <p className="whitespace-pre-wrap">{message.content}</p>
            </div>
            {insufficient ? (
              <p className="mt-2 border-t border-ig-border pt-2 text-xs text-ig-muted">
                The assistant did not fabricate an answer: the indexed repository does
                not establish this.
              </p>
            ) : null}
            {message.uncertainty && message.uncertainty.length > 0 ? (
              <ul className="mt-2 list-disc border-t border-ig-border pt-2 pl-5 text-xs text-ig-muted">
                {message.uncertainty.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            ) : null}
            {message.clarifyingQuestion ? (
              <p className="mt-2 flex items-start gap-1.5 border-t border-ig-border pt-2 text-xs text-ig-blue">
                <CircleHelp size={13} className="mt-0.5 shrink-0" aria-hidden />
                {message.clarifyingQuestion}
              </p>
            ) : null}
          </div>
          {message.citations.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 pl-6">
              {message.citations.map((citation) => (
                <CitationChip key={citation.source_id} citation={citation} onOpen={onOpenCitation} />
              ))}
            </div>
          ) : null}
        </div>
      )}
    </article>
  );
}
