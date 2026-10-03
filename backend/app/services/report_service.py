"""Investigation report assembly and Markdown export (PRD FR-39..FR-42).

Observed facts, model interpretations, and user-verified outcomes are kept
in separate sections (FR-40); unknown fields render as visibly unknown."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.models import (
    Hypothesis,
    InvestigationReport,
    SourceCitation,
    VerificationStep,
)
from app.persistence.models import (
    HypothesisRow,
    IncidentArtifactRow,
    IncidentRow,
)

_UNKNOWN = "Unknown (not established by the available evidence)"


class ReportService:
    def build(
        self,
        incident: IncidentRow,
        hypotheses: list[HypothesisRow],
        artifacts: list[IncidentArtifactRow],
        *,
        is_partial: bool = False,
    ) -> InvestigationReport:
        user_verified: list[str] = []
        for step in incident.verification_plan or []:
            if step.get("outcome"):
                user_verified.append(
                    f"{step['description']} → {step['outcome']}"
                    + (f" ({step['notes']})" if step.get("notes") else "")
                )

        model_interpretations = [row.explanation for row in hypotheses]

        return InvestigationReport(
            incident_id=incident.id,
            repository_id=incident.repository_id,
            index_version=incident.index_version,
            title=incident.title,
            summary=incident.title + " — " + (incident.description[:400]),
            observed_facts=[str(item) for item in (incident.observed_facts or [])],
            model_interpretations=model_interpretations,
            user_verified_outcomes=user_verified,
            hypotheses=[self._hypothesis_from_row(row) for row in hypotheses],
            missing_evidence=[item for row in hypotheses for item in (row.missing_evidence or [])],
            verification_plan=[
                VerificationStep(**step) for step in (incident.verification_plan or [])
            ],
            unresolved_questions=[
                f"Affected endpoint/service: {_UNKNOWN}"
                if not incident.affected_endpoint and not incident.affected_service
                else f"Affected endpoint: {incident.affected_endpoint or 'unknown'}"
            ]
            if not incident.affected_endpoint and not incident.affected_service
            else [],
            evidence_gaps=[str(item) for item in (incident.evidence_gaps or [])],
            generated_at=datetime.now(timezone.utc),
            is_partial=is_partial,
            postmortem=self.postmortem_draft(incident, hypotheses),
        )

    def postmortem_draft(
        self, incident: IncidentRow, hypotheses: list[HypothesisRow]
    ) -> dict[str, object]:
        supported = [row for row in hypotheses if row.status in {"supported", "user_verified"}]
        return {
            "impact": _UNKNOWN,
            "timeline": self._timeline(incident),
            "contributing_factors": [row.title for row in supported] or [_UNKNOWN],
            "resolution": _UNKNOWN,
            "follow_up_actions": [
                f"Verify: {step['description']}"
                for step in (incident.verification_plan or [])
                if not step.get("outcome")
            ]
            or [_UNKNOWN],
        }

    @staticmethod
    def _timeline(incident: IncidentRow) -> list[str]:
        entries: list[str] = []
        if incident.time_start:
            entries.append(f"Impact window start (user-supplied): {incident.time_start.isoformat()}")
        if incident.time_end:
            entries.append(f"Impact window end (user-supplied): {incident.time_end.isoformat()}")
        for signal in incident.normalized_signals or []:
            if signal.get("kind") == "timestamp":
                entries.append(f"Observed in evidence: {signal.get('value')}")
        return entries or [_UNKNOWN]

    @staticmethod
    def _hypothesis_from_row(row: HypothesisRow) -> Hypothesis:
        return Hypothesis(
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
        )

    def to_markdown(self, report: InvestigationReport) -> str:
        lines: list[str] = []
        lines.append(f"# Incident report: {report.title}")
        lines.append("")
        lines.append(f"- Incident ID: `{report.incident_id}`")
        lines.append(f"- Repository: `{report.repository_id}` (index `{report.index_version}`)")
        lines.append(
            f"- Generated: {report.generated_at.isoformat() if report.generated_at else 'unknown'}"
        )
        if report.is_partial:
            lines.append("- **Note: partial report — some workflow steps did not complete.**")
        lines.append("")
        lines.append("## Summary")
        lines.append(report.summary)
        lines.append("")

        def section(title: str, items: list[str], unknown_note: str) -> None:
            lines.append(f"## {title}")
            if items:
                lines.extend(f"- {item}" for item in items)
            else:
                lines.append(f"- _{unknown_note}_")
            lines.append("")

        section("Observed facts", report.observed_facts, "No observed facts recorded.")
        section("Model interpretations (unverified)", report.model_interpretations, "None generated.")
        section(
            "User-verified outcomes", report.user_verified_outcomes, "No user-verified outcomes yet."
        )

        lines.append("## Hypotheses")
        if not report.hypotheses:
            lines.append("- _None generated (insufficient evidence)._")
        for hypothesis in report.hypotheses:
            lines.append(f"### {hypothesis.title} — status: {hypothesis.status}")
            lines.append(hypothesis.explanation)
            if hypothesis.supporting_evidence:
                lines.append("Supporting evidence:")
                lines.extend(
                    f"- `{citation.source_id}` {citation.path}"
                    + (
                        f":{citation.start_line}-{citation.end_line}"
                        if citation.start_line is not None
                        else ""
                    )
                    for citation in hypothesis.supporting_evidence
                )
            if hypothesis.contradicting_evidence:
                lines.append("Contradicting evidence:")
                lines.extend(
                    f"- `{citation.source_id}` {citation.path}" for citation in hypothesis.contradicting_evidence
                )
            if hypothesis.missing_evidence:
                lines.append("Missing evidence:")
                lines.extend(f"- {item}" for item in hypothesis.missing_evidence)
            lines.append("")

        section("Missing evidence", report.missing_evidence, "None flagged.")
        section("Evidence gaps", report.evidence_gaps, "None.")
        section("Unresolved questions", report.unresolved_questions, "None recorded.")

        lines.append("## Verification plan")
        if not report.verification_plan:
            lines.append("- _No verification steps generated._")
        for step in report.verification_plan:
            outcome = step.outcome or "pending (user runs this check independently)"
            lines.append(f"- [ ] {step.description}")
            lines.append(f"  - If supported: {step.expected_if_supported}")
            lines.append(f"  - If weakened: {step.expected_if_weakened}")
            lines.append(f"  - Outcome: {outcome}")
        lines.append("")

        lines.append(
            "_This report was generated with model assistance. Hypotheses are "
            "unverified until a user records a test outcome; the system does not "
            "certify root causes._"
        )
        return "\n".join(lines)
