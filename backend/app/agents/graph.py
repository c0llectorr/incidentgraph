"""Graph wiring (PRD §11.1, FR-32): a small, finite, directed workflow.

Normalize → Extract signals → Retrieve → Generate → Validate → Review →
Verification plan → Report. Conditional edges per §11.1. No autonomous
agents; one generation step and one review step."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.nodes import NodeSet
from app.agents.state import InvestigationState
from app.agents.transitions import (
    route_after_normalize,
    route_after_repair,
    route_after_retrieval,
    route_after_validation,
)


class InvestigationGraphFactory:
    def __init__(self, nodes: NodeSet) -> None:
        self._nodes = nodes

    def build(self):
        graph = StateGraph(InvestigationState)
        nodes = self._nodes

        graph.add_node("normalize_incident", nodes.normalize_incident)
        graph.add_node("await_evidence", nodes.await_evidence)
        graph.add_node("extract_signals", nodes.extract_signals)
        graph.add_node("retrieve_evidence", nodes.retrieve_evidence)
        graph.add_node("generate_hypotheses", nodes.generate_hypotheses)
        graph.add_node("validate_citations", nodes.validate_citations)
        graph.add_node("repair_hypotheses", nodes.repair_hypotheses)
        graph.add_node("review_evidence", nodes.review_evidence)
        graph.add_node("build_verification_plan", nodes.build_verification_plan)
        graph.add_node("build_report", nodes.build_report)
        graph.add_node("evidence_gap", nodes.evidence_gap)

        graph.set_entry_point("normalize_incident")
        graph.add_conditional_edges(
            "normalize_incident",
            route_after_normalize,
            {"extract_signals": "extract_signals", "await_evidence": "await_evidence"},
        )
        graph.add_edge("await_evidence", END)
        graph.add_edge("extract_signals", "retrieve_evidence")
        graph.add_conditional_edges(
            "retrieve_evidence",
            route_after_retrieval,
            {"generate_hypotheses": "generate_hypotheses", "evidence_gap": "evidence_gap"},
        )
        graph.add_edge("evidence_gap", END)
        graph.add_edge("generate_hypotheses", "validate_citations")
        graph.add_conditional_edges(
            "validate_citations",
            route_after_validation,
            {"repair_hypotheses": "repair_hypotheses", "review_evidence": "review_evidence"},
        )
        graph.add_edge("repair_hypotheses", "validate_citations")
        graph.add_edge("review_evidence", "build_verification_plan")
        graph.add_edge("build_verification_plan", "build_report")
        graph.add_edge("build_report", END)

        return graph.compile()
