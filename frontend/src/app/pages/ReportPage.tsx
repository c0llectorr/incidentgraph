import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ErrorPanel from "../../components/common/ErrorPanel";
import ReportView from "../../components/reports/ReportView";
import type { InvestigationReport } from "../../types/api";
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
    <ReportView
      report={report}
      markdownUrl={`/api/v1/incidents/${incidentId}/report?format=markdown`}
    />
  );
}
