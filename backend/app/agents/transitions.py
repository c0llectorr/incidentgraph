"""Conditional transitions (PRD §11.1). Each encodes one graceful-degradation
rule; the graph wires them as conditional edges."""

from __future__ import annotations

from app.agents.state import InvestigationState


def route_after_normalize(state: InvestigationState) -> str:
    """Empty or missing evidence → stop and request clarification."""
    if state.get("resume"):
        return "extract_signals"  # resume keeps prior normalization
    # Evidence exists if the incident has any artifacts; the runner checks
    # that before invoking and seeds `has_evidence` accordingly.
    return "extract_signals" if state.get("has_evidence") else "await_evidence"


def route_after_retrieval(state: InvestigationState) -> str:
    """No useful evidence → evidence-gap report, never invented hypotheses."""
    return "generate_hypotheses" if state.get("retrieved_evidence") else "evidence_gap"


def route_after_validation(state: InvestigationState) -> str:
    """Invalid source IDs → ONE bounded repair attempt, then move on."""
    evidence_ids = {item["chunk_id"] for item in state.get("retrieved_evidence", [])}
    hypotheses = state.get("hypotheses", [])
    has_invalid = any(
        item["source_id"] not in evidence_ids
        for hypothesis in hypotheses
        for item in hypothesis.get("supporting", []) + hypothesis.get("contradicting", [])
    )
    all_unsupported = bool(hypotheses) and all(
        not hypothesis.get("supporting") for hypothesis in hypotheses
    )
    if (has_invalid or all_unsupported) and not state.get("repair_attempted"):
        return "repair_hypotheses"
    return "review_evidence"


def route_after_repair(state: InvestigationState) -> str:
    return "validate_citations"
