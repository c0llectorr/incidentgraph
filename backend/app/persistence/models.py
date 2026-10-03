"""SQL persistence models for the §13 minimum logical entities.

Vector data lives only in the vector store; this is the relational record of
chunks and everything else. API schemas stay separate from these models
(PRD §8.2 schemas/ row).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RepositoryRow(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(20))
    source_reference: Mapped[str] = mapped_column(Text)  # normalized URL or upload identifier
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    repo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(200), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    index_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="not_indexed")
    configuration_fingerprint: Mapped[str] = mapped_column(String(64))
    file_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class IngestionJobRow(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"))
    repository: Mapped["RepositoryRow"] = relationship()
    stage: Mapped[str] = mapped_column(String(40), default="validating_source")
    status: Mapped[str] = mapped_column(String(20), default="queued")
    percent: Mapped[float] = mapped_column(Float, default=0.0)
    completed_units: Mapped[int] = mapped_column(Integer, default=0)
    total_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class FileRecordRow(Base):
    __tablename__ = "file_records"
    __table_args__ = (
        Index("ix_file_records_repo_version", "repository_id", "index_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[str] = mapped_column(String(40))
    index_version: Mapped[str] = mapped_column(String(40))
    relative_path: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(40), default="text")
    content_hash: Mapped[str] = mapped_column(String(64))
    filter_status: Mapped[str] = mapped_column(String(20), default="included")
    filter_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CodeChunkRow(Base):
    __tablename__ = "code_chunks"
    __table_args__ = (Index("ix_code_chunks_repo_version", "repository_id", "index_version"),)

    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    repository_id: Mapped[str] = mapped_column(String(40))
    index_version: Mapped[str] = mapped_column(String(40))
    path: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(40))
    chunk_type: Mapped[str] = mapped_column(String(30))
    chunking_method: Mapped[str] = mapped_column(String(30))
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    symbol_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    parent_context: Mapped[str | None] = mapped_column(String(400), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IncidentRow(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"))
    repository: Mapped["RepositoryRow"] = relationship()
    index_version: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    affected_endpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_service: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    normalized_signals: Mapped[list | None] = mapped_column(JSON, nullable=True)
    observed_facts: Mapped[list | None] = mapped_column(JSON, nullable=True)
    verification_plan: Mapped[list | None] = mapped_column(JSON, nullable=True)
    evidence_gaps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class IncidentArtifactRow(Base):
    """Stored separately from repository chunks, linked by incident ID
    and repository/index version (PRD FR-29)."""

    __tablename__ = "incident_artifacts"

    artifact_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"))
    incident: Mapped["IncidentRow"] = relationship()
    repository_id: Mapped[str] = mapped_column(String(40))
    index_version: Mapped[str] = mapped_column(String(40))
    type: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HypothesisRow(Base):
    __tablename__ = "hypotheses"

    hypothesis_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"))
    incident: Mapped["IncidentRow"] = relationship()
    title: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    supporting_evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    contradicting_evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    missing_evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    verification_steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="unverified")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ConversationMessageRow(Base):
    __tablename__ = "conversation_messages"

    message_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(40))
    scope_type: Mapped[str] = mapped_column(String(20))  # repository | incident
    repository_id: Mapped[str] = mapped_column(String(40))
    incident_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
