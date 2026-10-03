import type { Signal } from "../../types/api";

interface InvestigationSummaryProps {
  signals: Signal[];
  evidenceGaps: string[];
  observedFacts: string[];
}

/** Screen 5 header (PRD §12.4): observed facts and deterministic signals. */
export default function InvestigationSummary({
  signals,
  evidenceGaps,
  observedFacts,
}: InvestigationSummaryProps) {
  return (
    <section className="grid gap-4 sm:grid-cols-3" aria-label="Investigation summary">
      <div className="rounded-lg border border-ig-border bg-ig-surface p-4">
        <h3 className="text-xs font-medium uppercase tracking-wide text-ig-muted">Observed facts</h3>
        {observedFacts.length > 0 ? (
          <ul className="mt-2 list-disc pl-4 text-sm text-ig-navy">
            {observedFacts.map((fact, index) => (
              <li key={index}>{fact}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-ig-muted">None recorded yet.</p>
        )}
      </div>
      <div className="rounded-lg border border-ig-border bg-ig-surface p-4">
        <h3 className="text-xs font-medium uppercase tracking-wide text-ig-muted">
          Deterministic signals
        </h3>
        {signals.length > 0 ? (
          <ul className="mt-2 max-h-40 overflow-y-auto text-xs text-ig-navy">
            {signals.slice(0, 12).map((signal, index) => (
              <li key={index} className="mt-1 font-mono">
                <span className="text-ig-blue">{signal.kind}</span> {signal.value}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-ig-muted">No signals recognized in the evidence.</p>
        )}
      </div>
      <div className="rounded-lg border border-ig-border bg-ig-surface p-4">
        <h3 className="text-xs font-medium uppercase tracking-wide text-ig-muted">Evidence gaps</h3>
        {evidenceGaps.length > 0 ? (
          <ul className="mt-2 list-disc pl-4 text-sm text-ig-navy">
            {evidenceGaps.map((gap, index) => (
              <li key={index}>{gap}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-ig-muted">None flagged.</p>
        )}
      </div>
    </section>
  );
}
