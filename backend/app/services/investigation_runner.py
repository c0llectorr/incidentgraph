"""Orchestrates the RCA graph and persists its results (PRD §11, FR-37/38).

The graph computes; this runner persists. Node failure returns a recoverable
error while preserving already-completed outputs (FR-38)."""

from __future__ import annotations

from typing import Any

from fastapi.responses import PlainTextResponse

from app.agents.graph import InvestigationGraphFactory
from app.agents.nodes import NodeSet
from app.agents.state import InvestigationState
from app.core.config import Settings
from app.core.errors import IndexNotReadyError, NotFoundError, WorkflowNodeFailedError
from app.core.ids import new_hypothesis_id
from app.core.logging import get_logger
from app.domain.enums import InvestigationStatus
from app.domain.policies import can_transition
from app.persistence.models import HypothesisRow
from app.persistence.repositories import IncidentRepository, RepositoryRepository
from app.persistence.unit_of_work import UnitOfWork
from app.retrieval.context_builder import ContextBuilder
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.lexical_retriever import LexicalRetriever
from app.services.report_service import ReportService
from app.services.signal_extractor import IncidentSignalExtractor

logger = get_logger(__name__)


class InvestigationRunner:
    def __init__(
        self,
        settings: Settings,
        uow: UnitOfWork,
        incident_service,
        signal_extractor: IncidentSignalExtractor,
        chat_model,
        embedder,
        vector_store,
    ) -> None:
        self._settings = settings
        self._uow = uow
        self._incidents = incident_service
        self._signals = signal_extractor
        self._chat = chat_model
        self._embedder = embedder
        self._store = vector_store
        self._reports = ReportService()

    # -- public API ----------------------------------------------------------

    def investigate(self, incident_id: str) -> dict[str, Any]:
        incident = self._incidents.get(incident_id)
        repository = self._repository(incident.repository_id)
        if repository.status != "ready" or not repository.index_version:
            raise IndexNotReadyError(
                "Investigation needs a completed repository index; ingest first."
            )

        artifact_pairs = self._incidents.artifact_contents(incident_id)
        resume = incident.status == InvestigationStatus.COMPLETED.value

        nodes = NodeSet(
            chat_model=self._chat,
            signal_extractor=self._signals,
            dense_retriever=DenseRetriever(
                self._embedder, self._store, self._settings.retrieval_top_k
            ),
            lexical_retriever=LexicalRetriever(
                self._uow, self._settings.retrieval_top_k
            ),
            context_builder=ContextBuilder(self._settings.max_context_tokens),
            artifact_contents=self._incidents.artifact_contents,
        )
        graph = InvestigationGraphFactory(nodes).build()

        initial: InvestigationState = {
            "incident_id": incident_id,
            "repository_id": incident.repository_id,
            "index_version": repository.index_version,
            "incident_title": incident.title,
            "incident_description": incident.description,
            "status": InvestigationStatus.RUNNING.value,
            "errors": [],
            "evidence_gaps": [],
            "review_notes": [],
            "hypotheses": [],
            "verification_plan": [],
            "normalized_signals": [],
            "retrieved_evidence": [],
            "observed_facts": [],
            "resume": resume,
            "repair_attempted": False,
            "has_evidence": bool(artifact_pairs),
        }
        self._incidents.update_state(incident_id, status=InvestigationStatus.RUNNING.value)

        try:
            final: InvestigationState = graph.invoke(initial, config={"recursion_limit": 25})
        except Exception as exc:
            logger.exception("Investigation workflow failed for %s", incident_id)
            node = getattr(exc, "node", "workflow")
            code = getattr(exc, "code", "WORKFLOW_NODE_FAILED")
            logger.error(
                "Workflow error at node=%s code=%s: %s", node, code, str(exc)[:300]
            )
            self._incidents.update_state(
                incident_id, status=InvestigationStatus.FAILED.value
            )
            # Partial outputs (signals, hypotheses gathered so far) are preserved.
            self._persist_workflow_outputs(incident_id, final_state=None)
            detail = self.detail(incident_id)
            detail["status"] = InvestigationStatus.FAILED.value
            return detail

        self._persist_workflow_outputs(incident_id, final_state=final)
        return self.detail(incident_id)

    def record_outcome(self, incident_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        incident = self._incidents.get(incident_id)
        step_id = str(payload.get("step_id", ""))
        outcome = payload.get("outcome")
        notes = payload.get("notes")
        if outcome not in {"supports", "weakens", "inconclusive", None}:
            from app.core.errors import ValidationError

            raise ValidationError("outcome must be supports | weakens | inconclusive.")

        plan = list(incident.verification_plan or [])
        for step in plan:
            if step.get("step_id") == step_id:
                if outcome is not None:
                    step["outcome"] = outcome
                if notes:
                    step["notes"] = str(notes)[:500]

        hypothesis_id = payload.get("hypothesis_id")
        hypothesis_status = payload.get("hypothesis_status")
        if hypothesis_id:
            with self._uow.begin() as session:
                row = IncidentRepository().get_hypothesis(session, str(hypothesis_id))
                if row is None or row.incident_id != incident_id:
                    raise NotFoundError("Hypothesis not found for this incident.")
                new_status = hypothesis_status or self._status_from_outcome(outcome)
                if new_status:
                    if not can_transition(row.status, new_status):
                        from app.core.errors import ValidationError

                        raise ValidationError(
                            f"Illegal hypothesis transition {row.status} → {new_status}."
                        )
                    row.status = new_status

        self._incidents.update_state(incident_id, verification_plan=plan)
        return self.detail(incident_id)

    def report(self, incident_id: str, *, output_format: str = "json"):
        incident = self._incidents.get(incident_id)
        hypotheses = self._incidents.hypotheses(incident_id)
        artifacts = self._incidents.artifacts(incident_id)
        is_partial = incident.status == InvestigationStatus.FAILED.value
        report = self._reports.build(
            incident, hypotheses, artifacts, is_partial=is_partial
        )
        if output_format == "markdown":
            return PlainTextResponse(
                self._reports.to_markdown(report),
                media_type="text/markdown; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="incident-{incident_id[:12]}-report.md"'
                },
            )
        return report.model_dump(mode="json")

    # -- internals -------------------------------------------------------------

    @staticmethod
    def _status_from_outcome(outcome: str | None) -> str | None:
        return {"supports": "supported", "weakens": "weakened"}.get(outcome or "")

    def _repository(self, repository_id: str):
        with self._uow.begin() as session:
            repository = RepositoryRepository().get(session, repository_id)
            if repository is None:
                raise NotFoundError("Repository not found for this incident.")
            session.expunge(repository)
            return repository

    def _persist_workflow_outputs(
        self,
        incident_id: str,
        *,
        final_state: InvestigationState | None,
    ) -> None:
        updates: dict[str, Any] = {}
        if final_state is not None:
            updates.update(
                {
                    "normalized_signals": final_state.get("normalized_signals", []),
                    "observed_facts": final_state.get("observed_facts", []),
                    "verification_plan": final_state.get("verification_plan", []),
                    "evidence_gaps": final_state.get("evidence_gaps", []),
                    "status": final_state.get("status", InvestigationStatus.COMPLETED.value),
                }
            )
        else:
            updates["status"] = InvestigationStatus.FAILED.value
        self._incidents.update_state(incident_id, **updates)

        if final_state is None:
            return

        evidence_by_id = {
            item["chunk_id"]: item for item in final_state.get("retrieved_evidence", [])
        }
        with self._uow.begin() as session:
            # Replace hypotheses from any previous run (re-analysis replaces,
            # it does not mix — FR-37 reruns produce a coherent new set).
            existing = IncidentRepository().hypotheses_for(session, incident_id)
            for row in existing:
                session.delete(row)
            for hypothesis in final_state.get("hypotheses", []):
                supporting = self._citations_for(hypothesis.get("supporting", []), evidence_by_id)
                contradicting = self._citations_for(
                    hypothesis.get("contradicting", []), evidence_by_id
                )
                status = "insufficient_evidence" if not supporting else "unverified"
                session.add(
                    HypothesisRow(
                        hypothesis_id=new_hypothesis_id(),
                        incident_id=incident_id,
                        title=hypothesis["title"][:200],
                        explanation=hypothesis["explanation"],
                        supporting_evidence=[citation.model_dump() for citation in supporting],
                        contradicting_evidence=[
                            citation.model_dump() for citation in contradicting
                        ],
                        missing_evidence=hypothesis.get("missing_evidence", []),
                        verification_steps=(
                            [hypothesis["verification"]["step"]]
                            if hypothesis.get("verification")
                            else []
                        ),
                        status=status,
                    )
                )

    @staticmethod
    def _citations_for(items: list[dict], evidence_by_id: dict[str, dict]):
        from app.domain.models import SourceCitation

        citations: list[SourceCitation] = []
        for item in items:
            evidence = evidence_by_id.get(item["source_id"])
            if evidence is None:
                continue
            citations.append(
                SourceCitation(
                    source_id=evidence["chunk_id"],
                    path=evidence["path"],
                    start_line=evidence.get("start_line"),
                    end_line=evidence.get("end_line"),
                )
            )
        return citations

    def detail(self, incident_id: str) -> dict[str, Any]:
        from app.api.v1.incidents import _incident_out
        from app.domain.models import Hypothesis, SourceCitation

        incident = self._incidents.get(incident_id)
        out = _incident_out(incident)
        hypotheses = [
            Hypothesis(
                hypothesis_id=row.hypothesis_id,
                title=row.title,
                explanation=row.explanation,
                supporting_evidence=[
                    SourceCitation(**item) for item in (row.supporting_evidence or [])
                ],
                contradicting_evidence=[
                    SourceCitation(**item) for item in (row.contradicting_evidence or [])
                ],
                missing_evidence=[str(item) for item in (row.missing_evidence or [])],
                verification_steps=[str(item) for item in (row.verification_steps or [])],
                status=row.status,  # type: ignore[arg-type]
            ).model_dump(mode="json")
            for row in self._incidents.hypotheses(incident_id)
        ]
        payload = out.model_dump(mode="json")
        payload["hypotheses"] = hypotheses
        payload["review_notes"] = []
        return payload


__all__ = ["InvestigationRunner", "WorkflowNodeFailedError"]
