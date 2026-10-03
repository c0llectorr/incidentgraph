import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Trash2 } from "lucide-react";
import EmptyState from "../common/EmptyState";
import ErrorPanel from "../common/ErrorPanel";
import StatusBadge from "../common/StatusBadge";
import ChatComposer from "./ChatComposer";
import MessageList from "./MessageList";
import type { ChatMessage } from "./MessageBubble";
import SourceDrawer from "./SourceDrawer";
import type { SourceCitation } from "../../types/api";
import { askIncident, askRepository } from "../../features/chat/api";
import { deleteRepository } from "../../features/repositories/api";

interface ChatPanelProps {
  repositoryId: string;
  repositoryStatus: string;
  incidentId?: string;
}

/** Screen 3 (PRD §12.4): repository workspace chat with the citation panel.
 * Duplicate submissions are prevented while a request is pending (FR-25). */
export default function ChatPanel({ repositoryId, repositoryStatus, incidentId }: ChatPanelProps) {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [activeCitation, setActiveCitation] = useState<SourceCitation | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const ask = async (question: string) => {
    if (pending) return; // FR-25: no duplicate submissions while pending
    setPending(true);
    setError(null);
    setMessages((previous) => [...previous, { role: "user", content: question, citations: [] }]);
    try {
      const response = incidentId
        ? await askIncident(incidentId, question, conversationId)
        : await askRepository(repositoryId, question, conversationId);
      setConversationId(response.conversation_id);
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: response.answer,
          citations: response.citations,
          status: response.status,
          clarifyingQuestion: response.clarifying_question,
          uncertainty: response.uncertainty,
        },
      ]);
    } catch (caught) {
      setError(caught);
    } finally {
      setPending(false);
    }
  };

  const ready = repositoryStatus === "ready";

  const onDelete = async () => {
    await deleteRepository(repositoryId);
    navigate("/");
  };

  return (
    <div className="flex h-[calc(100vh-9rem)] gap-4">
      <section
        aria-label="Repository conversation"
        className="flex min-w-0 flex-1 flex-col rounded-lg border border-ig-border bg-ig-surface p-4"
      >
        <div className="mb-2 flex items-center justify-between gap-2">
          <StatusBadge status={repositoryStatus} />
          {confirmingDelete ? (
            <div className="flex items-center gap-2 text-xs text-ig-danger">
              <span>Delete this repository and all its data?</span>
              <button
                type="button"
                onClick={onDelete}
                className="rounded border border-ig-danger/50 px-2 py-0.5 font-medium text-ig-danger hover:bg-ig-danger/10"
              >
                Confirm delete
              </button>
              <button
                type="button"
                onClick={() => setConfirmingDelete(false)}
                className="text-ig-muted hover:text-ig-navy"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmingDelete(true)}
              aria-label="Delete repository and all related data"
              className="rounded p-1.5 text-ig-muted hover:bg-ig-bg hover:text-ig-danger focus-visible:outline focus-visible:outline-2 focus-visible:outline-ig-danger"
            >
              <Trash2 size={15} aria-hidden />
            </button>
          )}
        </div>

        {messages.length === 0 ? (
          <EmptyState
            title={ready ? "Ask the repository anything" : "Index in progress"}
            body={
              ready
                ? "Answers cite the exact file and line range they come from — click a citation to inspect the excerpt."
                : "Once ingestion completes you can ask questions about the indexed code."
            }
          />
        ) : (
          <MessageList messages={messages} pending={pending} onOpenCitation={setActiveCitation} />
        )}

        {error ? <ErrorPanel error={error} onRetry={() => setError(null)} /> : null}

        <ChatComposer disabled={pending || !ready} onSubmit={ask} />
        {!ready ? (
          <p className="pt-2 text-xs text-ig-muted" role="status">
            The index is not ready yet; questions unlock when ingestion completes.
          </p>
        ) : null}
      </section>

      <SourceDrawer citation={activeCitation} onClose={() => setActiveCitation(null)} />
    </div>
  );
}
