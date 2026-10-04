import type { JobEventPayload } from "../types/api";
import { API_BASE } from "./config";

/** Consecutive failed/malformed polls before giving up honestly (the stream
 * must not retry forever when the API is unreachable — PRD §6.3/§12.8). */
const MAX_FAILED_POLLS = 5;
const POLL_INTERVAL_MS = 1_000;

function unknownEvent(jobId: string, message: string): JobEventPayload {
  return {
    job_id: jobId,
    stage: "unknown",
    status: "unknown",
    percent: null,
    indeterminate: false,
    completed_units: 0,
    total_units: null,
    message,
    error_code: "NETWORK_ERROR",
    updated_at: new Date().toISOString(),
  };
}

function isTerminal(status: string | undefined): boolean {
  return ["succeeded", "failed", "cancelled", "unknown"].includes(status ?? "");
}

/**
 * Subscribes to the backend's SSE progress stream (PRD FR-44), falling back
 * to documented polling of GET /jobs/{id} when EventSource is unavailable
 * or the stream errors. The subscription always terminates: on a terminal
 * status, or after a bounded number of failed polls (surfaced as an
 * "unknown" event the UI renders as an actionable error).
 */
export function subscribeToJobEvents(
  jobId: string,
  onEvent: (event: JobEventPayload) => void,
  onDone: () => void,
): () => void {
  let closed = false;
  let pollTimer: ReturnType<typeof setTimeout> | null = null;
  let source: EventSource | null = null;
  let fellBack = false;

  const cleanup = () => {
    closed = true;
    if (source) source.close();
    if (pollTimer) clearTimeout(pollTimer);
  };

  const finish = (event: JobEventPayload) => {
    cleanup();
    onEvent(event);
    onDone();
  };

  const startPolling = () => {
    let failures = 0;

    const poll = async () => {
      if (closed) return;
      try {
        const response = await fetch(`${API_BASE}/jobs/${jobId}`);
        if (response.ok) {
          const event = (await response.json().catch(() => null)) as JobEventPayload | null;
          if (event && typeof event.status === "string") {
            failures = 0;
            onEvent(event);
            if (isTerminal(event.status)) {
              cleanup();
              onDone();
              return;
            }
          } else {
            failures += 1;
          }
        } else if (response.status === 404) {
          // A missing job is terminal: there is nothing left to follow.
          finish(unknownEvent(jobId, "This ingestion job is unknown to the server (it may have restarted)."));
          return;
        } else {
          failures += 1;
        }
      } catch {
        failures += 1;
      }

      if (failures >= MAX_FAILED_POLLS) {
        finish(
          unknownEvent(
            jobId,
            "Lost contact with the API server while monitoring the job. Check that the backend is running, then retry.",
          ),
        );
        return;
      }
      pollTimer = setTimeout(poll, POLL_INTERVAL_MS);
    };

    pollTimer = setTimeout(poll, POLL_INTERVAL_MS);
  };

  try {
    source = new EventSource(`${API_BASE}/jobs/${jobId}/events`);
    source.addEventListener("progress", (message) => {
      try {
        const event = JSON.parse((message as MessageEvent<string>).data) as JobEventPayload;
        onEvent(event);
        if (isTerminal(event.status)) {
          cleanup();
          onDone();
        }
      } catch {
        // malformed event; ignore and keep the stream open
      }
    });
    source.onerror = () => {
      // Fall back to polling exactly once; repeated errors must not spawn
      // additional poll chains.
      source?.close();
      if (!fellBack && !closed) {
        fellBack = true;
        startPolling();
      }
    };
  } catch {
    startPolling();
  }

  return cleanup;
}
