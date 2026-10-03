import { apiGet, apiPost } from "../../lib/http";
import type { Incident, IncidentDetail } from "../../types/api";

export function createIncident(
  repositoryId: string,
  payload: {
    title: string;
    description: string;
    affected_endpoint?: string | null;
    affected_service?: string | null;
    time_start?: string | null;
    time_end?: string | null;
  },
): Promise<Incident> {
  return apiPost<Incident>(`/repositories/${repositoryId}/incidents`, payload);
}

export function addEvidence(
  incidentId: string,
  type: "log" | "traceback" | "diff" | "note",
  content: string,
): Promise<{ artifact_id: string; type: string; size_bytes: number }> {
  return apiPost(`/incidents/${incidentId}/evidence`, { type, content });
}

export function getIncident(incidentId: string): Promise<IncidentDetail> {
  return apiGet<IncidentDetail>(`/incidents/${incidentId}`);
}

export function getIncidentReportMarkdown(incidentId: string): Promise<string> {
  return apiGet<string>(`/incidents/${incidentId}/report?format=markdown`);
}
