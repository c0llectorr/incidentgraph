import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import ErrorPanel from "../../components/common/ErrorPanel";
import ReportView from "../../components/reports/ReportView";
import type { InvestigationReport } from "../../types/api";
import { API_BASE } from "../../lib/config";
import { apiGet } from "../../lib/http";

export default function ReportPage() {
  const { incidentId = "" } = useParams();
  const [report, setReport] = useState<InvestigationReport | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setReport(
        await apiGet<InvestigationReport>(`/incidents/${incidentId}/report?format=json`),
      );
    } catch (caught) {
      setError(caught);
    }
  }, [incidentId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) return <ErrorPanel error={error} onRetry={load} />;
  if (!report) {
    return (
      <p role="status" className="text-sm text-ig-muted">
        Loading report…
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      {/* Return path: the report must never be a navigation dead end (§12.4). */}
      <Link
        to={`/incidents/${incidentId}`}
        className="inline-flex items-center gap-1 text-xs text-ig-muted hover:text-ig-blue"
      >
        <ArrowLeft size={13} aria-hidden /> Back to investigation
      </Link>
      <ReportView
        report={report}
        markdownUrl={`${API_BASE}/incidents/${incidentId}/report?format=markdown`}
      />
    </div>
  );
}
