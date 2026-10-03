"""Ingestion schemas (PRD §8.5, §12.6 event contract)."""

from __future__ import annotations

from pydantic import BaseModel


class IngestionStartResponse(BaseModel):
    job_id: str
    repository_id: str


class JobStatusOut(BaseModel):
    job_id: str
    repository_id: str
    stage: str
    status: str
    percent: float | None = None
    indeterminate: bool = False
    completed_units: int = 0
    total_units: int | None = None
    message: str | None = None
    error_code: str | None = None
    updated_at: str | None = None


class JobEventOut(JobStatusOut):
    pass
