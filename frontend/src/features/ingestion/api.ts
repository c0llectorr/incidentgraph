import { api, apiGet, apiPost, apiPostForm } from "../../lib/http";
import type { JobEventPayload, Repository } from "./types";

export function getJobStatus(jobId: string): Promise<JobEventPayload> {
  return apiGet<JobEventPayload>(`/jobs/${jobId}`);
}

export function createRepositoryFromZip(file: File): Promise<Repository> {
  const form = new FormData();
  form.append("file", file);
  return apiPostForm<Repository>("/repositories", form);
}

export function createRepositoryFromUrl(githubUrl: string): Promise<Repository> {
  return apiPost<Repository>("/repositories", { github_url: githubUrl });
}

export function startIngestion(repositoryId: string): Promise<{ job_id: string }> {
  return api<{ job_id: string }>(`/repositories/${repositoryId}/ingestions`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}
