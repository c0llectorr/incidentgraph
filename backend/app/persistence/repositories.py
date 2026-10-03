"""Per-aggregate repositories. Focused query/update methods only —
use-case orchestration lives in services/ (PRD §8.2)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.persistence.models import (
    CodeChunkRow,
    ConversationMessageRow,
    FileRecordRow,
    HypothesisRow,
    IncidentArtifactRow,
    IncidentRow,
    IngestionJobRow,
    RepositoryRow,
)


class RepositoryRepository:
    def add(self, session: Session, row: RepositoryRow) -> None:
        session.add(row)

    def get(self, session: Session, repository_id: str) -> RepositoryRow | None:
        return session.get(RepositoryRow, repository_id)

    def update_index_state(
        self,
        session: Session,
        repository_id: str,
        *,
        index_version: str | None = None,
        status: str | None = None,
        file_count: int | None = None,
        commit_sha: str | None = None,
    ) -> RepositoryRow | None:
        row = session.get(RepositoryRow, repository_id)
        if row is None:
            return None
        if index_version is not None:
            row.index_version = index_version
        if status is not None:
            row.status = status
        if file_count is not None:
            row.file_count = file_count
        if commit_sha is not None:
            row.commit_sha = commit_sha
        row.updated_at = datetime.now(UTC)
        return row

    def delete(self, session: Session, repository_id: str) -> bool:
        row = session.get(RepositoryRow, repository_id)
        if row is None:
            return False
        session.delete(row)
        return True


class JobRepository:
    def add(self, session: Session, row: IngestionJobRow) -> None:
        session.add(row)

    def get(self, session: Session, job_id: str) -> IngestionJobRow | None:
        return session.get(IngestionJobRow, job_id)

    def list_by_repository(self, session: Session, repository_id: str) -> list[IngestionJobRow]:
        stmt = (
            select(IngestionJobRow)
            .where(IngestionJobRow.repository_id == repository_id)
            .order_by(IngestionJobRow.created_at.desc())
        )
        return list(session.scalars(stmt))

    def delete_by_repository(self, session: Session, repository_id: str) -> int:
        result = session.execute(
            delete(IngestionJobRow).where(IngestionJobRow.repository_id == repository_id)
        )
        return int(result.rowcount or 0)


class FileRecordRepository:
    def add_many(self, session: Session, rows: list[FileRecordRow]) -> None:
        session.add_all(rows)

    def by_version(self, session: Session, repository_id: str, index_version: str) -> list[FileRecordRow]:
        stmt = select(FileRecordRow).where(
            FileRecordRow.repository_id == repository_id,
            FileRecordRow.index_version == index_version,
        )
        return list(session.scalars(stmt))

    def delete_by_repository(self, session: Session, repository_id: str) -> int:
        result = session.execute(
            delete(FileRecordRow).where(FileRecordRow.repository_id == repository_id)
        )
        return int(result.rowcount or 0)


class ChunkRepository:
    def add_many(self, session: Session, rows: list[CodeChunkRow]) -> None:
        session.add_all(rows)

    def get_many(self, session: Session, chunk_ids: list[str]) -> list[CodeChunkRow]:
        if not chunk_ids:
            return []
        stmt = select(CodeChunkRow).where(CodeChunkRow.chunk_id.in_(chunk_ids))
        return list(session.scalars(stmt))

    def by_version(self, session: Session, repository_id: str, index_version: str) -> list[CodeChunkRow]:
        stmt = select(CodeChunkRow).where(
            CodeChunkRow.repository_id == repository_id,
            CodeChunkRow.index_version == index_version,
        )
        return list(session.scalars(stmt))

    def count(self, session: Session, repository_id: str, index_version: str) -> int:
        rows = self.by_version(session, repository_id, index_version)
        return len(rows)

    def search_lexical(
        self, session: Session, repository_id: str, index_version: str, patterns: list[str], limit: int
    ) -> list[CodeChunkRow]:
        """P1 lexical support (FR-18): exact substring matching over content
        and path for identifiers, exception strings, and file names."""
        if not patterns:
            return []
        conditions = [
            or_(
                CodeChunkRow.content.contains(pattern),
                CodeChunkRow.path.contains(pattern),
            )
            for pattern in patterns
        ]
        stmt = (
            select(CodeChunkRow)
            .where(
                CodeChunkRow.repository_id == repository_id,
                CodeChunkRow.index_version == index_version,
                or_(*conditions),
            )
            .limit(limit)
        )
        return list(session.scalars(stmt))

    def delete_by_repository(self, session: Session, repository_id: str) -> int:
        result = session.execute(
            delete(CodeChunkRow).where(CodeChunkRow.repository_id == repository_id)
        )
        return int(result.rowcount or 0)


class IncidentRepository:
    def add(self, session: Session, row: IncidentRow) -> None:
        session.add(row)

    def get(self, session: Session, incident_id: str) -> IncidentRow | None:
        return session.get(IncidentRow, incident_id)

    def list_by_repository(self, session: Session, repository_id: str) -> list[IncidentRow]:
        stmt = select(IncidentRow).where(IncidentRow.repository_id == repository_id)
        return list(session.scalars(stmt))

    def add_artifact(self, session: Session, row: IncidentArtifactRow) -> None:
        session.add(row)

    def artifacts_for(self, session: Session, incident_id: str) -> list[IncidentArtifactRow]:
        stmt = select(IncidentArtifactRow).where(IncidentArtifactRow.incident_id == incident_id)
        return list(session.scalars(stmt))

    def add_hypothesis(self, session: Session, row: HypothesisRow) -> None:
        session.add(row)

    def hypotheses_for(self, session: Session, incident_id: str) -> list[HypothesisRow]:
        stmt = select(HypothesisRow).where(HypothesisRow.incident_id == incident_id)
        return list(session.scalars(stmt))

    def get_hypothesis(self, session: Session, hypothesis_id: str) -> HypothesisRow | None:
        return session.get(HypothesisRow, hypothesis_id)

    def delete_by_repository(self, session: Session, repository_id: str) -> tuple[int, int, int]:
        incident_ids = list(
            session.scalars(select(IncidentRow.id).where(IncidentRow.repository_id == repository_id))
        )
        if not incident_ids:
            return (0, 0, 0)
        artifacts = session.execute(
            delete(IncidentArtifactRow).where(IncidentArtifactRow.incident_id.in_(incident_ids))
        ).rowcount or 0
        hypotheses = session.execute(
            delete(HypothesisRow).where(HypothesisRow.incident_id.in_(incident_ids))
        ).rowcount or 0
        incidents = session.execute(
            delete(IncidentRow).where(IncidentRow.id.in_(incident_ids))
        ).rowcount or 0
        return (int(incidents), int(artifacts), int(hypotheses))


class MessageRepository:
    def add(self, session: Session, row: ConversationMessageRow) -> None:
        session.add(row)

    def recent(
        self, session: Session, conversation_id: str, limit: int
    ) -> list[ConversationMessageRow]:
        stmt = (
            select(ConversationMessageRow)
            .where(ConversationMessageRow.conversation_id == conversation_id)
            .order_by(ConversationMessageRow.created_at.desc())
            .limit(limit)
        )
        rows = list(session.scalars(stmt))
        rows.reverse()  # chronological order
        return rows

    def delete_by_repository(self, session: Session, repository_id: str) -> int:
        result = session.execute(
            delete(ConversationMessageRow).where(
                ConversationMessageRow.repository_id == repository_id
            )
        )
        return int(result.rowcount or 0)
