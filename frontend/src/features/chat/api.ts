import { api } from "../../lib/http";
import type { ChatResponse, IncidentDetail } from "../../types/api";

export function askRepository(
  repositoryId: string,
  question: string,
  conversationId?: string | null,
): Promise<ChatResponse> {
  return api<ChatResponse>(`/repositories/${repositoryId}/chat`, {
    method: "POST",
    body: JSON.stringify({ question, conversation_id: conversationId ?? null }),
  });
}

export function askIncident(
  incidentId: string,
  question: string,
  conversationId?: string | null,
): Promise<ChatResponse> {
  return api<ChatResponse>(`/incidents/${incidentId}/messages`, {
    method: "POST",
    body: JSON.stringify({ question, conversation_id: conversationId ?? null }),
  });
}

export function investigateIncident(incidentId: string): Promise<IncidentDetail> {
  return api<IncidentDetail>(`/incidents/${incidentId}/investigate`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function recordOutcome(
  incidentId: string,
  payload: {
    step_id: string;
    outcome?: "supports" | "weakens" | "inconclusive" | null;
    notes?: string | null;
    hypothesis_id?: string | null;
    hypothesis_status?: "supported" | "weakened" | "user_verified" | null;
  },
): Promise<IncidentDetail> {
  return api<IncidentDetail>(`/incidents/${incidentId}/outcomes`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
