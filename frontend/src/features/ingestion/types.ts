// Ingestion feature types (single source of truth stays in types/api.ts;
// this module re-exports the slices this feature owns — PRD §12.7/§12.8).
export type { JobEventPayload, Repository } from "../../types/api";
