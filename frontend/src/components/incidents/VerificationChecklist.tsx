import { useState } from "react";
import { ClipboardCheck } from "lucide-react";
import type { VerificationStep } from "../../types/api";
import ErrorPanel from "../common/ErrorPanel";
import StatusBadge from "../common/StatusBadge";
import { recordOutcome } from "../../features/chat/api";

interface VerificationChecklistProps {
  incidentId: string;
  steps: VerificationStep[];
  onChanged: () => void;
}

/** FR-36/FR-37: the user runs each check independently and records the
 * outcome; the app never executes anything itself. */
export default function VerificationChecklist({ incidentId, steps, onChanged }: VerificationChecklistProps) {
  const [busyStep, setBusyStep] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const record = async (stepId: string, outcome: "supports" | "weakens" | "inconclusive") => {
    setBusyStep(stepId);
    setError(null);
    try {
      await recordOutcome(incidentId, { step_id: stepId, outcome });
      onChanged();
    } catch (caught) {
      setError(caught);
    } finally {
      setBusyStep(null);
    }
  };

  if (steps.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-ig-border px-4 py-6 text-center text-sm text-ig-muted">
        No verification steps yet — run an investigation to generate the checklist.
      </p>
    );
  }

  return (
    <section aria-label="Verification checklist" className="flex flex-col gap-3">
      {error ? <ErrorPanel error={error} /> : null}
      {steps.map((step) => (
        <article
          key={step.step_id}
          className="rounded-lg border border-ig-border bg-ig-surface p-4"
        >
          <header className="flex items-start justify-between gap-3">
            <p className="flex items-start gap-2 text-sm font-medium text-ig-navy">
              <ClipboardCheck size={15} className="mt-0.5 shrink-0 text-ig-blue" aria-hidden />
              {step.description}
            </p>
            <StatusBadge status={step.outcome ?? "pending"} />
          </header>
          <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
            <div className="rounded-md bg-ig-bg px-3 py-2">
              <dt className="font-medium text-ig-navy">If it supports the hypothesis</dt>
              <dd className="mt-0.5 text-ig-muted">{step.expected_if_supported}</dd>
            </div>
            <div className="rounded-md bg-ig-bg px-3 py-2">
              <dt className="font-medium text-ig-navy">If it weakens the hypothesis</dt>
              <dd className="mt-0.5 text-ig-muted">{step.expected_if_weakened}</dd>
            </div>
          </dl>
          {step.notes ? (
            <p className="mt-2 text-xs text-ig-muted">Your notes: {step.notes}</p>
          ) : null}
          <div className="mt-3 flex gap-2">
            {(["supports", "weakens", "inconclusive"] as const).map((outcome) => (
              <button
                key={outcome}
                type="button"
                disabled={busyStep === step.step_id}
                onClick={() => record(step.step_id, outcome)}
                className={`rounded-md border px-3 py-1 text-xs font-medium transition-colors duration-200 disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ig-blue ${
                  step.outcome === outcome
                    ? "border-ig-blue bg-ig-blue/10 text-ig-blue"
                    : "border-ig-border text-ig-muted hover:border-ig-blue hover:text-ig-blue"
                }`}
              >
                {outcome}
              </button>
            ))}
          </div>
        </article>
      ))}
    </section>
  );
}
