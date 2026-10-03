"""Incident endpoints (PRD §8.5): create, evidence, state, investigate,
follow-up messages, outcomes, report. The investigation graph itself is
orchestrated in agents/ — this layer only wires HTTP."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import get_container
from app.domain.models import Hypothesis
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.incident import (
    EvidenceIn,
    IncidentArtifactOut,
    IncidentCreate,
    IncidentDetailOut,
    IncidentOut,
    OutcomesIn,
)

router = APIRouter()


@router.post(
    "/repositories/{repository_id}/incidents",
    response_model=IncidentOut,
    status_code=201,
)
def create_incident(repository_id: str, payload: IncidentCreate) -> IncidentOut:
    container = get_container()
    incident_service = container.get("incident_service")
    row = incident_service.create(repository_id, payload)  # type: ignore[attr-defined]
    return _incident_out(row)


@router.post("/incidents/{incident_id}/evidence", response_model=IncidentArtifactOut, status_code=201)
def add_evidence(incident_id: str, payload: EvidenceIn) -> IncidentArtifactOut:
    container = get_container()
    incident_service = container.get("incident_service")
    row = incident_service.add_artifact(incident_id, payload.type, payload.content)  # type: ignore[attr-defined]
    return IncidentArtifactOut(
        artifact_id=row.artifact_id,
        type=row.type,
        size_bytes=row.size_bytes,
        created_at=row.created_at,
    )


@router.get("/incidents/{incident_id}", response_model=IncidentDetailOut)
def get_incident(incident_id: str) -> IncidentDetailOut:
    container = get_container()
    incident_service = container.get("incident_service")
    row = incident_service.get(incident_id)  # type: ignore[attr-defined]
    artifacts = incident_service.artifacts(incident_id)  # type: ignore[attr-defined]
    hypotheses = incident_service.hypotheses(incident_id)  # type: ignore[attr-defined]
    out = _incident_out(row)
    return IncidentDetailOut(
        **out.model_dump(),
        artifacts=[
            IncidentArtifactOut(
                artifact_id=artifact.artifact_id,
                type=artifact.type,
                size_bytes=artifact.size_bytes,
                created_at=artifact.created_at,
            )
            for artifact in artifacts
        ],
        hypotheses=[
            Hypothesis(
                hypothesis_id=hyp.hypothesis_id,
                title=hyp.title,
                explanation=hyp.explanation,
                supporting_evidence=hyp.supporting_evidence or [],
                contradicting_evidence=hyp.contradicting_evidence or [],
                missing_evidence=hyp.missing_evidence or [],
                verification_steps=hyp.verification_steps or [],
                status=hyp.status,
            )
            for hyp in hypotheses
        ],
    )


@router.post("/incidents/{incident_id}/investigate", response_model=IncidentDetailOut)
def investigate_incident(incident_id: str) -> IncidentDetailOut:
    runner = get_container().investigation_runner()
    return IncidentDetailOut(**runner.investigate(incident_id))


@router.post("/incidents/{incident_id}/messages", response_model=ChatResponse)
def incident_followup(incident_id: str, payload: ChatRequest) -> ChatResponse:
    container = get_container()
    incident_service = container.get("incident_service")
    incident = incident_service.get(incident_id)  # type: ignore[attr-defined]
    result = container.rag().answer(
        repository_id=incident.repository_id,
        question=payload.question,
        conversation_id=payload.conversation_id,
        scope_incident_id=incident_id,
    )
    return ChatResponse(
        conversation_id=result.conversation_id,
        status=result.status,
        answer=result.answer,
        citations=result.citations,
        uncertainty=result.uncertainty,
        clarifying_question=result.clarifying_question,
        dropped_citation_count=result.dropped_citation_count,
    )


@router.post("/incidents/{incident_id}/outcomes", response_model=IncidentDetailOut)
def record_outcome(incident_id: str, payload: OutcomesIn) -> IncidentDetailOut:
    runner = get_container().investigation_runner()
    return IncidentDetailOut(
        **runner.record_outcome(
            incident_id,
            {
                "step_id": payload.step_id,
                "outcome": payload.outcome,
                "notes": payload.notes,
                "hypothesis_id": payload.hypothesis_id,
                "hypothesis_status": payload.hypothesis_status,
            },
        )
    )


@router.get("/incidents/{incident_id}/report")
def incident_report(incident_id: str, format: str = "json"):
    runner = get_container().investigation_runner()
    if format not in {"json", "markdown"}:
        from app.core.errors import ValidationError

        raise ValidationError("format must be 'json' or 'markdown'.")
    return runner.report(incident_id, output_format=format)


def _incident_out(row) -> IncidentOut:
    from app.domain.models import Signal, VerificationStep

    return IncidentOut(
        id=row.id,
        repository_id=row.repository_id,
        index_version=row.index_version,
        title=row.title,
        description=row.description,
        affected_endpoint=row.affected_endpoint,
        affected_service=row.affected_service,
        time_start=row.time_start,
        time_end=row.time_end,
        normalized_signals=[Signal(**item) for item in (row.normalized_signals or [])],
        verification_plan=[
            VerificationStep(**item) for item in (row.verification_plan or [])
        ],
        evidence_gaps=row.evidence_gaps or [],
        status=row.status,
        created_at=row.created_at,
    )
