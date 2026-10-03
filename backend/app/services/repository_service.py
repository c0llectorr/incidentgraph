"""Use cases for repository intake and deletion (PRD §8.2 services/; FR-01..04).

Provenance is recorded at creation (FR-04): source reference, branch/commit,
timestamp, and a configuration fingerprint covering every setting that would
change ingestion output.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from typing import Any

from app.core.config import Settings
from app.core.errors import LimitExceededError, NotFoundError
from app.core.ids import content_hash, new_repository_id
from app.core.logging import get_logger
from app.core.security import normalize_github_url
from app.persistence.models import RepositoryRow
from app.persistence.repositories import RepositoryRepository
from app.persistence.unit_of_work import UnitOfWork

logger = get_logger(__name__)

_UPLOAD_FILENAME = "source.zip"


def configuration_fingerprint(settings: Settings) -> str:
    material = json.dumps(
        {
            "max_upload_bytes": settings.max_upload_bytes,
            "max_repository_files": settings.max_repository_files,
            "max_file_bytes": settings.max_file_bytes,
            "max_total_extracted_bytes": settings.max_total_extracted_bytes,
            "chunk_token_limit": settings.chunk_token_limit,
            "embedding_provider": settings.embedding_provider,
            "embedding_model": (
                settings.qwen_embedding_model
                if settings.embedding_provider == "local"
                else settings.embedding_remote_model
            ),
            "vector_store": settings.vector_store,
        },
        sort_keys=True,
    )
    return content_hash(material)[:32]


class RepositoryService:
    def __init__(self, settings: Settings, uow: UnitOfWork) -> None:
        self._settings = settings
        self._uow = uow
        # Wired by the container as a lazy callable so test overrides apply.
        self.vector_store_provider: Callable[[], Any] | None = None

    def create_from_github_url(self, raw_url: str) -> RepositoryRow:
        source = normalize_github_url(raw_url)
        row = RepositoryRow(
            id=new_repository_id(),
            source_type="github",
            source_reference=f"https://github.com/{source.slug}",
            owner=source.owner,
            repo=source.repo,
            branch=source.branch,
            commit_sha=source.commit,
            configuration_fingerprint=configuration_fingerprint(self._settings),
        )
        with self._uow.begin() as session:
            RepositoryRepository().add(session, row)
        logger.info("Repository created %s from %s", row.id, source.slug)
        return row

    def create_from_zip(self, original_filename: str, content: bytes) -> RepositoryRow:
        if len(content) > self._settings.max_upload_bytes:
            raise LimitExceededError(
                "ZIP upload exceeds the configured limit of "
                f"{self._settings.max_upload_bytes} bytes."
            )
        if not content.startswith(b"PK"):
            raise LimitExceededError("The uploaded file is not a ZIP archive.")
        repository_id = new_repository_id()
        destination = self._settings.upload_dir / repository_id
        destination.mkdir(parents=True, exist_ok=True)
        (destination / _UPLOAD_FILENAME).write_bytes(content)
        row = RepositoryRow(
            id=repository_id,
            source_type="zip",
            source_reference=str(destination / _UPLOAD_FILENAME),
            branch=None,
            configuration_fingerprint=configuration_fingerprint(self._settings),
        )
        with self._uow.begin() as session:
            RepositoryRepository().add(session, row)
        logger.info("Repository created %s from upload %s", repository_id, original_filename)
        return row

    def get(self, repository_id: str) -> RepositoryRow:
        with self._uow.begin() as session:
            row = RepositoryRepository().get(session, repository_id)
            if row is None:
                raise NotFoundError("Repository not found.")
            session.expunge(row)
            return row

    def delete_everything(self, repository_id: str) -> dict[str, int]:
        """Delete a repository and ALL related data (PRD §6.1): chunks, file
        records, vectors, jobs, incidents, artifacts, messages, uploads."""
        from app.core.errors import DeletionFailedError
        from app.persistence.repositories import (
            ChunkRepository,
            FileRecordRepository,
            IncidentRepository,
            JobRepository,
            MessageRepository,
        )

        with self._uow.begin() as session:
            if RepositoryRepository().get(session, repository_id) is None:
                raise NotFoundError("Repository not found.")

        vectors_deleted = 0
        if self.vector_store_provider is not None:
            try:
                vectors_deleted = self.vector_store_provider().delete_by_repository(repository_id)
            except Exception as exc:  # noqa: BLE001 - surfaced as a failed op
                raise DeletionFailedError(
                    "Could not delete the repository's vectors; nothing was removed."
                ) from exc

        with self._uow.begin() as session:
            incidents, artifacts, _hypotheses = IncidentRepository().delete_by_repository(
                session, repository_id
            )
            jobs = JobRepository().delete_by_repository(session, repository_id)
            chunks = ChunkRepository().delete_by_repository(session, repository_id)
            FileRecordRepository().delete_by_repository(session, repository_id)
            messages = MessageRepository().delete_by_repository(session, repository_id)
            RepositoryRepository().delete(session, repository_id)

        shutil.rmtree(self._settings.upload_dir / repository_id, ignore_errors=True)
        logger.info(
            "Repository %s deleted: %d vectors, %d jobs, %d incidents, %d artifacts",
            repository_id,
            vectors_deleted,
            jobs,
            incidents,
            artifacts,
        )
        return {
            "deleted_chunks": chunks,
            "deleted_vectors": vectors_deleted,
            "deleted_jobs": jobs,
            "deleted_incidents": incidents,
            "deleted_artifacts": artifacts,
            "deleted_messages": messages,
        }
