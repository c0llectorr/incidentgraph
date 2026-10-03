"""Use case: start an ingestion job and report its status (PRD §8.2/§8.5)."""

from __future__ import annotations

from collections.abc import Callable

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationError
from app.core.ids import new_job_id
from app.core.logging import get_logger
from app.domain.enums import JobStatus
from app.ingestion.pipeline import IngestionPipeline
from app.jobs.events import TERMINAL_JOB_STATUSES, JobEvent
from app.jobs.manager import JobManager
from app.persistence.models import IngestionJobRow
from app.persistence.repositories import JobRepository
from app.persistence.unit_of_work import UnitOfWork

logger = get_logger(__name__)


class IngestionService:
    def __init__(
        self,
        settings: Settings,
        uow: UnitOfWork,
        pipeline_factory: Callable[[str], IngestionPipeline],
        job_manager: JobManager,
    ) -> None:
        self._settings = settings
        self._uow = uow
        self._pipeline_factory = pipeline_factory
        self._job_manager = job_manager

    def start_ingestion(self, repository_id: str, *, repository_row) -> str:
        if repository_row.status == "indexing":
            raise ValidationError("An ingestion is already running for this repository.")

        job_id = new_job_id()
        with self._uow.begin() as session:
            JobRepository().add(
                session,
                IngestionJobRow(id=job_id, repository_id=repository_id, status=JobStatus.QUEUED.value),
            )

        # Fresh pipeline instance per job: a private UoW/session so the
        # background thread never shares a request-scoped session.
        pipeline = self._pipeline_factory(job_id)
        self._job_manager.register(job_id, repository_id)
        self._job_manager.submit(
            job_id,
            lambda: pipeline.execute(job_id=job_id, repository=repository_row),
        )
        logger.info("Ingestion job %s started for %s", job_id, repository_id)
        return job_id

    def job_status(self, job_id: str) -> dict:
        with self._uow.begin() as session:
            row = JobRepository().get(session, job_id)
            if row is None:
                raise NotFoundError("Job not found.")
            payload = {
                "job_id": row.id,
                "repository_id": row.repository_id,
                "stage": row.stage,
                "status": row.status,
                "percent": row.percent,
                "indeterminate": False,
                "completed_units": row.completed_units,
                "total_units": row.total_units,
                "message": row.message,
                "error_code": row.error_code,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        # Live events (if the manager still holds this job) are more current
        # than the DB row.
        events, _ = self._job_manager.events_after(job_id, 0)
        if events:
            latest = events[-1]
            payload.update(
                {
                    "stage": latest.stage,
                    "status": latest.status,
                    "percent": latest.percent,
                    "indeterminate": latest.indeterminate,
                    "completed_units": latest.completed_units,
                    "total_units": latest.total_units,
                    "message": latest.message,
                    "error_code": latest.error_code,
                    "updated_at": latest.updated_at,
                }
            )
        return payload

    def events_after(self, job_id: str, after_index: int) -> tuple[list[JobEvent], bool]:
        """Public event-cursor access for the SSE stream."""
        return self._job_manager.events_after(job_id, after_index)

    def wait_until_terminal(self, job_id: str, timeout: float = 120.0) -> bool:
        """Test helper: block until the background job finishes."""
        return self._job_manager.wait_for_terminal(job_id, timeout=timeout)


__all__ = ["IngestionService", "TERMINAL_JOB_STATUSES", "JobEvent"]
