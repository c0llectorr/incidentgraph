import { useEffect, useState } from "react";
import type { JobEventPayload } from "./types";
import { subscribeToJobEvents } from "../../lib/sse";

const TERMINAL = ["succeeded", "failed", "cancelled", "unknown"];

/** Subscribes to the backend's SSE progress stream with the documented
 * polling fallback (FR-44). Events are the ONLY source of progress —
 * nothing is simulated on a timer (PRD §12.5/§12.6). */
export function useIngestionEvents(jobId: string) {
  const [events, setEvents] = useState<JobEventPayload[]>([]);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const unsubscribe = subscribeToJobEvents(
      jobId,
      (event) => {
        setEvents((previous) => [...previous, event]);
        if (TERMINAL.includes(event.status)) {
          setDone(true);
        }
      },
      () => setDone(true),
    );
    return unsubscribe;
  }, [jobId]);

  const latest = events.length > 0 ? events[events.length - 1] : undefined;
  const failed = latest?.status === "failed" || latest?.status === "unknown";

  return { events, latest, done, failed };
}
