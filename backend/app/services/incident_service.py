"""Use cases for incident intake and state (PRD §8.2 services/, FR-26..29)."""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationError
from app.core.ids import new_artifact_id, new_incident_id
from app.core.logging import get_logger
from app.domain.enums import EvidenceType
from app.persistence.models import (
    HypothesisRow,
    IncidentArtifactRow,
    IncidentRow,
    RepositoryRow,
)
from app.persistence.repositories import IncidentRepository, RepositoryRepository
from app.persistence.unit_of_work import UnitOfWork
from app.schemas.incident import IncidentCreate

logger = get_logger(__name__)

_MAX_ARTIFACT_BYTES = 200_000

_ALLOWED_EVIDENCE = {EvidenceType.LOG, EvidenceType.TRACEBACK, EvidenceType.DIFF, EvidenceType.NOTE}


class IncidentService:
    def __init__(self, settings: Settings, uow: UnitOfWork) -> None:
        self._settings = settings
        self._uow = uow

    def create(self, repository_id: str, payload: IncidentCreate) -> IncidentRow:
        with self._uow.begin() as session:
            repository = RepositoryRepository().get(session, repository_id)
            if repository is None:
                raise NotFoundError("Repository not found.")
            row = IncidentRow(
                id=new_incident_id(),
                repository_id=repository_id,
                # Anchor the incident to the index version it was created
                # against (FR-29); an unindexed repository records an empty
                # version and cannot be investigated until one is ready.
                index_version=repository.index_version or "",
                title=payload.title,
                description=payload.description,
                affected_endpoint=payload.affected_endpoint,
                affected_service=payload.affected_service,
                time_start=payload.time_start,
                time_end=payload.time_end,
                status="pending",
            )
            IncidentRepository().add(session, row)
            session.expunge(row)
        logger.info("Incident %s created for repository %s", row.id, repository_id)
        return row

    def add_artifact(self, incident_id: str, evidence_type: str, content: str) -> IncidentArtifactRow:
        if evidence_type not in {item.value for item in _ALLOWED_EVIDENCE}:
            raise ValidationError(
                f"Unsupported evidence type '{evidence_type}'; "
                "accepted: log, traceback, diff, note."
            )
        encoded = content.encode("utf-8")
        if len(encoded) > _MAX_ARTIFACT_BYTES:
            raise ValidationError(
                f"Evidence exceeds the size limit of {_MAX_ARTIFACT_BYTES} bytes."
            )
        with self._uow.begin() as session:
            incident = IncidentRepository().get(session, incident_id)
            if incident is None:
                raise NotFoundError("Incident not found.")
            row = IncidentArtifactRow(
                artifact_id=new_artifact_id(),
                incident_id=incident_id,
                repository_id=incident.repository_id,
                index_version=incident.index_version,
                type=evidence_type,
                content=content,
                size_bytes=len(encoded),
            )
            IncidentRepository().add_artifact(session, row)
            session.expunge(row)
        return row

    def get(self, incident_id: str) -> IncidentRow:
        with self._uow.begin() as session:
            row = IncidentRepository().get(session, incident_id)
            if row is None:
                raise NotFoundError("Incident not found.")
            session.expunge(row)
            return row

    def artifacts(self, incident_id: str) -> list[IncidentArtifactRow]:
        with self._uow.begin() as session:
            rows = IncidentRepository().artifacts_for(session, incident_id)
            for row in rows:
                session.expunge(row)
            return rows

    def hypotheses(self, incident_id: str) -> list[HypothesisRow]:
        with self._uow.begin() as session:
            rows = IncidentRepository().hypotheses_for(session, incident_id)
            for row in rows:
                session.expunge(row)
            return rows

    def update_state(self, incident_id: str, **fields) -> None:
        with self._uow.begin() as session:
            row = IncidentRepository().get(session, incident_id)
            if row is None:
                raise NotFoundError("Incident not found.")
            for key, value in fields.items():
                setattr(row, key, value)

    def artifact_contents(self, incident_id: str) -> list[tuple[str, str]]:
        return [(row.type, row.content) for row in self.artifacts(incident_id)]
