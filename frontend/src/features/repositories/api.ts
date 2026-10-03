import { apiDelete, apiGet } from "../../lib/http";
import type { Repository } from "../../types/api";

export function getRepository(repositoryId: string): Promise<Repository> {
  return apiGet<Repository>(`/repositories/${repositoryId}`);
}

export function deleteRepository(repositoryId: string): Promise<Record<string, number>> {
  return apiDelete(`/repositories/${repositoryId}`);
}
