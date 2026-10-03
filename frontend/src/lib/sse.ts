import type { JobEventPayload } from "../types/api";

/**
 * Subscribes to the backend's SSE progress stream (PRD FR-44), falling back
 * to documented polling of GET /jobs/{id} when EventSource is unavailable
 * or the stream ends without a terminal event.
 */
export function subscribeToJobEvents(
  jobId: string,
  onEvent: (event: JobEventPayload) => void,
  onDone: () => void,
): () => void {
  let closed = false;
  let pollTimer: ReturnType<typeof setTimeout> | null = null;
  let source: EventSource | null = null;

  const cleanup = () => {
    closed = true;
    if (source) source.close();
    if (pollTimer) clearTimeout(pollTimer);
  };

  const isTerminal = (status: string) =>
    ["succeeded", "failed", "cancelled", "unknown"].includes(status);

  const startPolling = () => {
    if (closed) return;
    const poll = async () => {
      if (closed) return;
      try {
        const response = await fetch(`/api/v1/jobs/${jobId}`);
        if (response.ok) {
          const event = (await response.json()) as JobEventPayload;
          onEvent(event);
          if (isTerminal(event.status)) {
            cleanup();
            onDone();
            return;
          }
        }
      } catch {
        // transient; keep polling
      }
      pollTimer = setTimeout(poll, 1_000);
    };
    pollTimer = setTimeout(poll, 1_000);
  };

  try {
    source = new EventSource(`/api/v1/jobs/${jobId}/events`);
    source.addEventListener("progress", (message) => {
      try {
        const event = JSON.parse((message as MessageEvent<string>).data) as JobEventPayload;
        onEvent(event);
        if (isTerminal(event.status)) {
          cleanup();
          onDone();
        }
      } catch {
        // malformed event; ignore
      }
    });
    source.onerror = () => {
      source?.close();
      startPolling(); // documented polling fallback (FR-44)
    };
  } catch {
    startPolling();
  }

  return cleanup;
}
