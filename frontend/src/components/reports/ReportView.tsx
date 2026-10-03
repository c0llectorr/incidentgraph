import { CheckCircle2, Copy, Download } from "lucide-react";
import { useState } from "react";
import Button from "../common/Button";
import StatusBadge from "../common/StatusBadge";
import type { InvestigationReport } from "../../types/api";

interface ReportViewProps {
  report: InvestigationReport;
  markdownUrl: string;
}

/** Screen 6 (PRD §12.4): concise report with copy/export and explicit
 * unverified sections (FR-40/41). */
export default function ReportView({ report, markdownUrl }: ReportViewProps) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    const text = renderPlain(report);
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2_000);
  };

  return (
    <article className="flex flex-col gap-6" aria-label="Investigation report">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ig-navy">{report.title}</h1>
          <p className="mt-1 text-sm text-ig-muted">
            Generated {report.generated_at ? new Date(report.generated_at).toLocaleString() : "—"}
            {report.is_partial ? " · partial (a workflow step did not complete)" : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={copy}>
            {copied ? <CheckCircle2 size={15} aria-hidden /> : <Copy size={15} aria-hidden />}
            {copied ? "Copied" : "Copy report"}
          </Button>
          <a
            href={markdownUrl}
            className="inline-flex items-center gap-2 rounded-md bg-ig-blue px-4 py-2 text-sm font-medium text-white hover:bg-ig-navy focus-visible:outline focus-visible:outline-2 focus-visible:outline-ig-blue"
            download
          >
            <Download size={15} aria-hidden />
            Export Markdown
          </a>
        </div>
      </header>

      <section className="rounded-lg border border-ig-border bg-ig-surface p-5">
        <h2 className="text-sm font-semibold text-ig-navy">Summary</h2>
        <p className="mt-1.5 text-sm leading-relaxed text-ig-navy">{report.summary}</p>
      </section>

      <ReportSection
        title="Observed facts"
        items={report.observed_facts}
        emptyNote="No observed facts recorded."
      />
      <ReportSection
        title="Model interpretations — unverified"
        items={report.model_interpretations}
        emptyNote="None generated."
        tone="muted"
      />
      <ReportSection
        title="User-verified outcomes"
        items={report.user_verified_outcomes}
        emptyNote="No user-verified outcomes yet."
        tone="positive"
      />

      <section className="rounded-lg border border-ig-border bg-ig-surface p-5">
        <h2 className="text-sm font-semibold text-ig-navy">Hypotheses</h2>
        {report.hypotheses.length === 0 ? (
          <p className="mt-2 text-sm text-ig-muted">None generated (insufficient evidence).</p>
        ) : (
          <ul className="mt-3 flex flex-col gap-3">
            {report.hypotheses.map((hypothesis) => (
              <li key={hypothesis.hypothesis_id} className="rounded-md border border-ig-border p-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-medium text-ig-navy">{hypothesis.title}</h3>
                  <StatusBadge status={hypothesis.status} />
                </div>
                <p className="mt-1 text-xs leading-relaxed text-ig-muted">{hypothesis.explanation}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <ReportSection
        title="Missing evidence"
        items={report.missing_evidence}
        emptyNote="None flagged."
      />
      <ReportSection
        title="Unresolved questions"
        items={report.unresolved_questions}
        emptyNote="None recorded."
      />

      <section className="rounded-lg border border-ig-border bg-ig-surface p-5">
        <h2 className="text-sm font-semibold text-ig-navy">Verification plan</h2>
        {report.verification_plan.length === 0 ? (
          <p className="mt-2 text-sm text-ig-muted">No verification steps generated.</p>
        ) : (
          <ol className="mt-3 flex flex-col gap-2 text-sm text-ig-navy">
            {report.verification_plan.map((step) => (
              <li key={step.step_id} className="rounded-md border border-ig-border p-3">
                <p className="font-medium">{step.description}</p>
                <p className="mt-1 text-xs text-ig-muted">
                  If supported: {step.expected_if_supported} · If weakened: {step.expected_if_weakened}
                </p>
                <p className="mt-1 text-xs">
                  Outcome:{" "}
                  <span className={step.outcome ? "font-medium text-ig-blue" : "text-ig-muted"}>
                    {step.outcome ?? "pending — run this check yourself"}
                  </span>
                </p>
              </li>
            ))}
          </ol>
        )}
      </section>

      <p className="text-xs text-ig-muted">
        This report was generated with model assistance. Hypotheses are unverified until
        you record a test outcome; IncidentGraph does not certify root causes.
      </p>
    </article>
  );
}

function ReportSection({
  title,
  items,
  emptyNote,
  tone,
}: {
  title: string;
  items: string[];
  emptyNote: string;
  tone?: "muted" | "positive";
}) {
  return (
    <section className="rounded-lg border border-ig-border bg-ig-surface p-5">
      <h2 className={`text-sm font-semibold ${tone === "muted" ? "text-ig-muted" : "text-ig-navy"}`}>
        {title}
      </h2>
      {items.length === 0 ? (
        <p className="mt-2 text-sm italic text-ig-muted">{emptyNote}</p>
      ) : (
        <ul className="mt-2 list-disc pl-5 text-sm text-ig-navy">
          {items.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

function renderPlain(report: InvestigationReport): string {
  const lines: string[] = [
    `# Incident report: ${report.title}`,
    "",
    report.summary,
    "",
    "## Observed facts",
    ...report.observed_facts.map((item) => `- ${item}`),
    "",
    "## Model interpretations (unverified)",
    ...report.model_interpretations.map((item) => `- ${item}`),
    "",
    "## Hypotheses",
    ...report.hypotheses.map(
      (hypothesis) => `- [${hypothesis.status}] ${hypothesis.title}: ${hypothesis.explanation}`,
    ),
    "",
    "## Verification plan",
    ...report.verification_plan.map(
      (step) => `- [${step.outcome ?? "pending"}] ${step.description}`,
    ),
  ];
  return lines.join("\n");
}
