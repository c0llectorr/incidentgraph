import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, FileText, Play } from "lucide-react";
import Button from "../../components/common/Button";
import EmptyState from "../../components/common/EmptyState";
import ErrorPanel from "../../components/common/ErrorPanel";
import StatusBadge from "../../components/common/StatusBadge";
import HypothesisCard from "../../components/incidents/HypothesisCard";
import InvestigationSummary from "../../components/incidents/InvestigationSummary";
import VerificationChecklist from "../../components/incidents/VerificationChecklist";
import EvidenceAttach from "../../components/incidents/EvidenceAttach";
import SourceDrawer from "../../components/chat/SourceDrawer";
import type { IncidentDetail, SourceCitation } from "../../types/api";
import { getIncident } from "../../features/incidents/api";
import { investigateIncident } from "../../features/chat/api";

export default function InvestigationPage() {
  const { incidentId = "" } = useParams();
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [investigating, setInvestigating] = useState(false);
  const [citation, setCitation] = useState<SourceCitation | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDetail(await getIncident(incidentId));
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  }, [incidentId]);

  useEffect(() => {
    void load();
  }, [load]);

  const investigate = async () => {
    setInvestigating(true);
    setError(null);
    try {
      setDetail(await investigateIncident(incidentId));
    } catch (caught) {
      setError(caught);
    } finally {
      setInvestigating(false);
    }
  };

  if (loading && detail === null) {
    return (
      <p role="status" className="text-sm text-ig-muted">
        Loading incident…
      </p>
    );
  }
  if (error && detail === null) {
    return <ErrorPanel error={error} onRetry={load} />;
  }
  if (!detail) {
    return <EmptyState title="Not found" body="This incident does not exist." />;
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            to={`/repositories/${detail.repository_id}`}
            className="inline-flex items-center gap-1 text-xs text-ig-muted hover:text-ig-blue"
          >
            <ArrowLeft size={13} aria-hidden /> Back to repository
          </Link>
          <h1 className="mt-1 flex items-center gap-2 text-xl font-semibold text-ig-navy">
            {detail.title}
            <StatusBadge status={detail.status} />
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-ig-muted">{detail.description}</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={investigate} disabled={investigating}>
            <Play size={14} aria-hidden />
            {investigating
              ? "Investigating…"
              : detail.hypotheses.length > 0
                ? "Re-run investigation"
                : "Run investigation"}
          </Button>
          <Link to={`/incidents/${incidentId}/report`}>
            <Button variant="secondary">
              <FileText size={14} aria-hidden />
              Report
            </Button>
          </Link>
        </div>
      </header>

      {error ? <ErrorPanel error={error} onRetry={investigate} /> : null}

      {detail.status === "awaiting_evidence" ? (
        <div
          role="alert"
          className="rounded-lg border border-ig-border bg-ig-bg p-4 text-sm text-ig-navy"
        >
          <p className="font-medium">No incident evidence attached yet.</p>
          <p className="mt-1 text-ig-muted">
            The workflow stopped before generating hypotheses — by design it never
            invents them without evidence. Paste the failing traceback or logs
            below, attach them, then run the investigation again.
          </p>
        </div>
      ) : null}

      <EvidenceAttach incidentId={incidentId} onAttached={() => void load()} />

      <InvestigationSummary
        signals={detail.normalized_signals}
        evidenceGaps={detail.evidence_gaps}
        observedFacts={detail.observed_facts ?? []}
      />

      <section aria-label="Competing hypotheses" className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-ig-navy">
          Competing hypotheses {detail.hypotheses.length > 0 ? `(${detail.hypotheses.length})` : ""}
        </h2>
        {detail.hypotheses.length === 0 ? (
          <EmptyState
            title="No hypotheses yet"
            body="Run the investigation to generate up to three competing hypotheses, each with supporting evidence and a discriminating check."
          />
        ) : (
          detail.hypotheses.map((hypothesis) => (
            <HypothesisCard
              key={hypothesis.hypothesis_id}
              hypothesis={hypothesis}
              onOpenCitation={setCitation}
            />
          ))
        )}
      </section>

      <section aria-label="Verification checklist" className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-ig-navy">Verification checklist</h2>
        <VerificationChecklist
          incidentId={incidentId}
          steps={detail.verification_plan}
          onChanged={() => void load()}
        />
      </section>

      <SourceDrawer citation={citation} onClose={() => setCitation(null)} />
    </div>
  );
}
