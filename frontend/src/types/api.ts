// API contract types mirrored from the backend schemas (PRD §12.8: types
// come from the API contract; no `any` anywhere).

export interface ErrorBody {
  code: string;
  message: string;
  request_id: string;
  retryable: boolean;
}

export interface Repository {
  id: string;
  source_type: string;
  source_reference: string;
  owner: string | null;
  repo: string | null;
  branch: string | null;
  commit_sha: string | null;
  status: string;
  index_version: string | null;
  file_count: number | null;
  created_at: string | null;
}

export interface JobEventPayload {
  job_id: string;
  repository_id?: string;
  stage: string;
  status: string;
  percent: number | null;
  indeterminate: boolean;
  completed_units: number;
  total_units: number | null;
  message: string | null;
  error_code: string | null;
  updated_at: string | null;
}

export interface SourceCitation {
  source_id: string;
  path: string;
  start_line: number | null;
  end_line: number | null;
  excerpt: string | null;
}

export interface ChatResponse {
  conversation_id: string;
  status: string;
  answer: string;
  citations: SourceCitation[];
  uncertainty: string[];
  clarifying_question: string | null;
  dropped_citation_count: number;
}

export interface Signal {
  kind: string;
  value: string;
  file_path: string | null;
  line_number: number | null;
  detail: string | null;
}

export interface VerificationStep {
  step_id: string;
  description: string;
  expected_if_supported: string;
  expected_if_weakened: string;
  outcome: "supports" | "weakens" | "inconclusive" | null;
  notes: string | null;
}

export interface Hypothesis {
  hypothesis_id: string;
  title: string;
  explanation: string;
  supporting_evidence: SourceCitation[];
  contradicting_evidence: SourceCitation[];
  missing_evidence: string[];
  verification_steps: string[];
  status: "unverified" | "supported" | "weakened" | "user_verified" | "insufficient_evidence";
}

export interface Incident {
  id: string;
  repository_id: string;
  index_version: string;
  title: string;
  description: string;
  affected_endpoint: string | null;
  affected_service: string | null;
  time_start: string | null;
  time_end: string | null;
  normalized_signals: Signal[];
  observed_facts?: string[];
  verification_plan: VerificationStep[];
  evidence_gaps: string[];
  status: string;
  created_at: string | null;
}

export interface IncidentDetail extends Incident {
  artifacts: { artifact_id: string; type: string; size_bytes: number; created_at: string | null }[];
  hypotheses: Hypothesis[];
}

export interface InvestigationReport {
  incident_id: string;
  repository_id: string;
  index_version: string;
  title: string;
  summary: string;
  observed_facts: string[];
  model_interpretations: string[];
  user_verified_outcomes: string[];
  hypotheses: Hypothesis[];
  missing_evidence: string[];
  verification_plan: VerificationStep[];
  unresolved_questions: string[];
  evidence_gaps: string[];
  generated_at: string | null;
  is_partial: boolean;
  postmortem: Record<string, unknown> | null;
}
