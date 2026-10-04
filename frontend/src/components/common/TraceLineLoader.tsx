import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { stageLabel } from "../../lib/format";
import { useIngestionEvents } from "../../features/ingestion/hooks";

/** The pipeline stages (PRD FR-45). */
const STAGES = [
  "validating_source",
  "fetching_repository",
  "extracting_files",
  "filtering_files",
  "parsing_and_chunking",
  "embedding",
  "persisting_index",
  "verifying_index",
  "ready",
] as const;

interface TraceLineLoaderProps {
  jobId: string;
  onComplete?: (finalStatus: string) => void;
}

/**
 * The custom "trace-line" loader (PRD §12.5): a thin path through the
 * pipeline nodes; the active node expands subtly and a soft blue/green
 * segment advances as the backend reports REAL stage progress. Animation
 * indicates activity only — percentage and stage text come from backend
 * events; nothing is simulated on a timer. Reduced motion shows a static
 * line (globals.css collapses transitions), and status text is exposed via
 * a polite live region.
 */
export default function TraceLineLoader({ jobId, onComplete }: TraceLineLoaderProps) {
  const { latest, done, failed } = useIngestionEvents(jobId);
  const [completed, setCompleted] = useState(false);
  const completedRef = useRef(false);
  const activeIndex = latest ? STAGES.indexOf(latest.stage as (typeof STAGES)[number]) : -1;
  const percent = latest?.percent ?? null;
  const indeterminate = latest?.indeterminate ?? false;

  useEffect(() => {
    if (done && !completedRef.current) {
      completedRef.current = true;
      setCompleted(true);
      onComplete?.(latest?.status ?? "unknown");
    }
  }, [done, latest?.status, onComplete]);

  return (
    <section aria-label="Ingestion progress" className="rounded-lg border border-ig-border bg-ig-surface p-6">
      <div
        role="status"
        aria-live="polite"
        className="mb-5 flex items-baseline justify-between gap-4"
      >
        <p className="text-sm font-medium text-ig-navy">
          {latest?.message ?? "Waiting for the ingestion job…"}
        </p>
        <span className="text-sm tabular-nums text-ig-muted">
          {indeterminate || percent === null ? "working…" : `${Math.round(percent)}%`}
        </span>
      </div>

      {/* trace line: a thin path through the pipeline nodes */}
      <div className="relative mx-1 flex items-center justify-between" aria-hidden>
        <div className="absolute left-0 right-0 top-1/2 h-px -translate-y-1/2 bg-ig-border" />
        <div
          className="absolute left-0 top-1/2 h-[2px] -translate-y-1/2 bg-ig-green transition-[width] duration-300 ease-out"
          style={{
            width:
              activeIndex <= 0
                ? failed
                  ? "0%"
                  : "2%"
                : `${(activeIndex / (STAGES.length - 1)) * 100}%`,
          }}
        />
        {/* live runner: a pulse that repeatedly travels from the start of the
            line to the currently executing stage (PRD §12.5 — "evidence
            moving through a pipeline"). Everything else stays as-is. */}
        {!failed && !done && activeIndex >= 0 ? (
          <span
            className="trace-runner absolute top-1/2 z-20 h-2.5 w-2.5 -translate-y-1/2 rounded-full bg-ig-blue/90 shadow-[0_0_10px_2px_rgba(61,81,133,0.30)]"
            style={
              {
                "--trace-target": `${(activeIndex / (STAGES.length - 1)) * 100}%`,
              } as CSSProperties
            }
          />
        ) : null}
        {STAGES.map((stage, index) => {
          const isPast = activeIndex > index;
          const isActive = index === activeIndex;
          return (
            <div key={stage} className="relative z-10 flex flex-col items-center">
              <span
                className={`block rounded-full border-2 transition-all duration-300 ${
                  failed && isActive
                    ? "h-3.5 w-3.5 border-ig-danger bg-ig-danger/20"
                    : isPast || (latest?.stage === "ready" && !failed)
                      ? "h-3 w-3 border-ig-green bg-ig-green/30"
                      : isActive
                        ? "h-4 w-4 border-ig-blue bg-ig-blue/25 shadow-[0_0_0_4px_rgba(61,81,133,0.08)]"
                        : "h-2.5 w-2.5 border-ig-border bg-ig-surface"
                }`}
              />
            </div>
          );
        })}
      </div>

      <ol className="mt-5 grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-4">
        {STAGES.filter((stage) => stage !== "ready").map((stage, index) => {
          const state =
            latest?.stage === "ready" && latest.status === "succeeded"
              ? "done"
              : index < activeIndex
                ? "done"
                : index === activeIndex
                  ? "active"
                  : "todo";
          return (
            <li
              key={stage}
              className={
                state === "done"
                  ? "text-ig-green"
                  : state === "active"
                    ? "font-medium text-ig-blue"
                    : "text-ig-muted"
              }
            >
              {stageLabel(stage)}
              {state === "done" ? " ✓" : ""}
            </li>
          );
        })}
      </ol>

      {latest?.error_code ? (
        <p role="alert" className="mt-4 rounded-md border border-ig-danger/40 bg-ig-danger/5 px-3 py-2 text-xs text-ig-danger">
          {latest.error_code.replaceAll("_", " ").toLowerCase()} — {latest.message}
        </p>
      ) : null}
      {completed && !failed ? (
        <p className="mt-4 text-xs text-ig-green">Repository ready for questions.</p>
      ) : null}
    </section>
  );
}
