"""LangGraph node implementations (PRD §11.3, FR-32).

Each node has ONE responsibility and explicit inputs/outputs. Nodes never
raise for expected investigation outcomes — conditional transitions
(transitions.py) route empty-evidence and repair paths."""

from __future__ import annotations

import json
from typing import Any

from app.agents.state import InvestigationState
from app.core.ids import new_verification_id
from app.domain.enums import InvestigationStatus
from app.domain.models import RetrievedChunk, Signal, VerificationStep
from app.llm.output_parsers import (
    HypothesisSet,
    QAAnswer,
)
from app.llm.prompts import (
    RCA_HYPOTHESES_SYSTEM_PROMPT,
    RCA_NORMALIZE_SYSTEM_PROMPT,
    RCA_REVIEW_SYSTEM_PROMPT,
    build_rca_evidence_block,
)
from app.retrieval.context_builder import ContextBuilder, ContextBundle
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.query_rewriter import QueryPlan, build_query_plan

_MAX_NORMALIZE_EVIDENCE_CHARS = 6_000


class NodeSet:
    def __init__(
        self,
        *,
        chat_model,
        signal_extractor,
        dense_retriever,
        lexical_retriever,
        context_builder: ContextBuilder,
        artifact_contents,
    ) -> None:
        """*artifact_contents* is a callable(incident_id) -> list[(type, content)]
        so nodes stay free of persistence concerns."""
        self._chat = chat_model
        self._signals = signal_extractor
        self._dense = dense_retriever
        self._lexical = lexical_retriever
        self._context_builder = context_builder
        self._artifact_contents = artifact_contents

    # -- normalize: concise structured summary, no unsupported facts (§11.3) ----

    def normalize_incident(self, state: InvestigationState) -> dict[str, Any]:
        if state.get("resume") and state.get("incident_summary"):
            return {}
        contents = self._artifact_contents(state["incident_id"])
        excerpts: list[str] = []
        total = 0
        for evidence_type, content in contents:
            piece = f"--- {evidence_type} ---\n{content[:2_000]}"
            total += len(piece)
            if total > _MAX_NORMALIZE_EVIDENCE_CHARS:
                break
            excerpts.append(piece)
        user_prompt = (
            f"Incident title: {state.get('incident_title', '')}\n"
            f"Description: {state.get('incident_description', '')}\n"
            "Supplied evidence:\n" + ("\n".join(excerpts) or "(none)")
        )
        result: QAAnswer = self._chat.generate_structured(
            system_prompt=RCA_NORMALIZE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=QAAnswer,
            max_output_tokens=800,
        )
        summary = result.answer or state.get("incident_description", "")
        observed = [claim.text for claim in result.claims if claim.source_ids] or (
            [claim.text for claim in result.claims]
        )
        return {
            "incident_summary": summary,
            "observed_facts": observed,
        }

    # -- extract: deterministic parsers only (§11.3) -----------------------------

    def extract_signals(self, state: InvestigationState) -> dict[str, Any]:
        if state.get("resume") and state.get("normalized_signals"):
            return {}
        contents = self._artifact_contents(state["incident_id"])
        signals = self._signals.extract(contents)
        return {"normalized_signals": [signal.model_dump() for signal in signals]}

    # -- retrieve: source + incident chunks via identifiers + semantic query -----

    def retrieve_evidence(self, state: InvestigationState) -> dict[str, Any]:
        signals = [Signal(**item) for item in state.get("normalized_signals", [])]
        question_parts = [state.get("incident_title", ""), state.get("incident_summary", "")]
        plan: QueryPlan = build_query_plan(" ".join(part for part in question_parts if part))
        # Signals sharpen the lexical channel: file paths and exception names
        # from the traceback are the strongest anchors into the code index.
        plan.identifiers.extend(
            dict.fromkeys(
                [signal.value for signal in signals if signal.kind == "exception"]
                + [signal.value for signal in signals if signal.kind == "file_path"]
            )
        )
        dense = self._dense.retrieve(
            repository_id=state["repository_id"],
            index_version=state["index_version"],
            plan=plan,
        )
        lexical = self._lexical.retrieve(
            repository_id=state["repository_id"],
            index_version=state["index_version"],
            plan=plan,
        )
        fused = reciprocal_rank_fusion([dense, lexical])
        return {"retrieved_evidence": [chunk.model_dump() for chunk in fused]}

    # -- generate: at most three validated hypotheses (FR-33) ----------------------

    def generate_hypotheses(self, state: InvestigationState) -> dict[str, Any]:
        evidence = [RetrievedChunk(**item) for item in state.get("retrieved_evidence", [])]
        bundle: ContextBundle = self._context_builder.build(evidence)
        signals_text = "\n".join(
            f"- {signal.kind}: {signal.value}" + (f" ({signal.detail})" if signal.detail else "")
            for signal in (Signal(**item) for item in state.get("normalized_signals", []))
        )
        user_prompt = (
            f"Incident summary: {state.get('incident_summary', '')}\n\n"
            + build_rca_evidence_block(signals_text, bundle, artifacts_text="")
        )
        hypotheses: HypothesisSet = self._chat.generate_structured(
            system_prompt=RCA_HYPOTHESES_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=HypothesisSet,
            max_output_tokens=2_000,
        )
        capped = hypotheses.hypotheses[:3]
        return {"hypotheses": [hypothesis.model_dump() for hypothesis in capped]}

    def repair_hypotheses(self, state: InvestigationState) -> dict[str, Any]:
        """One bounded repair attempt when citations were invalid (§11.1)."""
        evidence_ids = {item["chunk_id"] for item in state.get("retrieved_evidence", [])}
        invalid = sorted(
            {
                item["source_id"]
                for hypothesis in state.get("hypotheses", [])
                for item in hypothesis.get("supporting", []) + hypothesis.get("contradicting", [])
                if item["source_id"] not in evidence_ids
            }
        )
        regenerated = self.generate_hypotheses(state)
        notes = list(state.get("review_notes", []))
        notes.append(f"Repair attempt: previous output cited missing sources: {invalid}")
        return {
            "hypotheses": regenerated["hypotheses"],
            "repair_attempted": True,
            "review_notes": notes,
        }

    # -- validate: mechanical citation check (FR-34 mechanical half) ----------------

    def validate_citations(self, state: InvestigationState) -> dict[str, Any]:
        evidence_ids = {item["chunk_id"] for item in state.get("retrieved_evidence", [])}
        hypotheses = HypothesisSet.model_validate({"hypotheses": state.get("hypotheses", [])})
        dropped: list[str] = []
        for hypothesis in hypotheses.hypotheses:
            for field_name in ("supporting", "contradicting"):
                items = getattr(hypothesis, field_name)
                setattr(
                    hypothesis,
                    field_name,
                    [item for item in items if item.source_id in evidence_ids],
                )
        # Hypotheses stripped of ALL supporting evidence are marked honestly.
        for hypothesis in hypotheses.hypotheses:
            if not hypothesis.supporting:
                hypothesis.missing_evidence = list(
                    dict.fromkeys(
                        hypothesis.missing_evidence
                        + ["supporting citation was not in the retrieved evidence set"]
                    )
                )
        updates: dict[str, Any] = {
            "hypotheses": [hypothesis.model_dump() for hypothesis in hypotheses.hypotheses]
        }
        notes = list(state.get("review_notes", []))
        if dropped:
            notes.append(f"Dropped fabricated/out-of-scope citations: {sorted(set(dropped))}")
        updates["review_notes"] = notes
        return updates

    # -- review: LLM guardrail (FR-34; a guardrail, not a proof) --------------------

    def review_evidence(self, state: InvestigationState) -> dict[str, Any]:
        hypotheses = state.get("hypotheses", [])
        listing = json.dumps(hypotheses, indent=1)[:6_000]
        evidence_listing = "\n".join(
            f"- {item['chunk_id']} {item['path']}:{item.get('start_line')}-{item.get('end_line')}"
            for item in state.get("retrieved_evidence", [])
        )
        notes: list[str]
        try:
            review: QAAnswer = self._chat.generate_structured(
                system_prompt=RCA_REVIEW_SYSTEM_PROMPT,
                user_prompt=f"Hypotheses:\n{listing}\n\nEvidence set:\n{evidence_listing}",
                schema=QAAnswer,
                max_output_tokens=800,
            )
            notes = [claim.text for claim in review.claims] or (
                [review.answer] if review.answer else []
            )
        except Exception:  # noqa: BLE001 - reviewer must not sink the workflow
            notes = ["Evidence review step could not run; mechanical validation only."]
        merged = list(state.get("review_notes", [])) + [f"Reviewer: {note}" for note in notes]
        return {"review_notes": merged}

    # -- plan + report ------------------------------------------------------------------

    def build_verification_plan(self, state: InvestigationState) -> dict[str, Any]:
        steps: list[VerificationStep] = []
        for hypothesis in state.get("hypotheses", []):
            verification = hypothesis.get("verification")
            if not verification:
                continue
            steps.append(
                VerificationStep(
                    step_id=new_verification_id(),
                    description=verification["step"],
                    expected_if_supported=verification["expect_if_supported"],
                    expected_if_weakened=verification["expect_if_weakened"],
                )
            )
        return {"verification_plan": [step.model_dump() for step in steps]}

    def build_report(self, state: InvestigationState) -> dict[str, Any]:
        # Hypotheses without surviving support are honestly downgraded.
        hypotheses = []
        for hypothesis in state.get("hypotheses", []):
            if not hypothesis.get("supporting"):
                hypothesis["status"] = "insufficient_evidence"
            hypotheses.append(hypothesis)
        return {
            "hypotheses": hypotheses,
            "status": InvestigationStatus.COMPLETED.value,
        }

    # -- evidence-gap / await paths ------------------------------------------------------

    def evidence_gap(self, state: InvestigationState) -> dict[str, Any]:
        return {
            "status": InvestigationStatus.COMPLETED.value,
            "evidence_gaps": [
                "No useful repository evidence was retrieved for this incident; "
                "hypotheses were not generated to avoid speculation."
            ],
        }

    def await_evidence(self, state: InvestigationState) -> dict[str, Any]:
        return {"status": InvestigationStatus.AWAITING_EVIDENCE.value}
