"""Repository intake schemas (PRD §8.5 POST/GET /repositories)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RepositoryCreateFromUrl(BaseModel):
    github_url: str = Field(min_length=1, description="Public GitHub repository URL.")


class RepositoryOut(BaseModel):
    id: str
    source_type: str
    source_reference: str
    owner: str | None = None
    repo: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    status: str
    index_version: str | None = None
    file_count: int | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RepositoryDeleted(BaseModel):
    repository_id: str
    deleted_chunks: int
    deleted_vectors: int
    deleted_jobs: int
    deleted_incidents: int
    deleted_artifacts: int
    deleted_messages: int
