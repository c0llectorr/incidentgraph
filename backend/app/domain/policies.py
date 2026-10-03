"""Pure policy logic: legal hypothesis transitions, stage weights, citation
validation, token estimation. Everything here is deterministic and side-effect
free (PRD §7.2 functional core; FR-35 qualitative statuses only)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.domain.enums import IngestionStage
from app.domain.models import HypothesisStatus

# Configurable presentation weights (PRD §12.6: monotonic, stage-aware,
# illustrative values — not hard-coded milestones in the UI).
STAGE_WEIGHTS: dict[IngestionStage, float] = {
    IngestionStage.VALIDATING_SOURCE: 0.02,
    IngestionStage.FETCHING_REPOSITORY: 0.08,
    IngestionStage.EXTRACTING_FILES: 0.10,
    IngestionStage.FILTERING_FILES: 0.05,
    IngestionStage.PARSING_AND_CHUNKING: 0.25,
    IngestionStage.EMBEDDING: 0.35,
    IngestionStage.PERSISTING_INDEX: 0.10,
    IngestionStage.VERIFYING_INDEX: 0.05,
}

# Legal hypothesis status transitions (FR-37; user_verified is terminal and
# can only be reached by a recorded user outcome, never by the model).
LEGAL_HYPOTHESIS_TRANSITIONS: dict[str, set[str]] = {
    "unverified": {"supported", "weakened", "insufficient_evidence"},
    "supported": {"weakened", "user_verified"},
    "weakened": {"supported", "user_verified"},
    "insufficient_evidence": {"supported", "weakened"},
    "user_verified": set(),
}


def can_transition(old: HypothesisStatus, new: HypothesisStatus) -> bool:
    return new in LEGAL_HYPOTHESIS_TRANSITIONS.get(old, set())


def estimate_tokens(text: str) -> int:
    """Cheap deterministic approximation (~4 chars/token) used for budgets.

    Real tokenizer tuning happens per selected model (PRD §17 note); this
    keeps budgets honest and stable across environments.
    """
    return max(1, len(text) // 4)


@dataclass(frozen=True)
class CitationCheck:
    valid_ids: tuple[str, ...]
    invalid_ids: tuple[str, ...]

    @property
    def has_invalid(self) -> bool:
        return bool(self.invalid_ids)


def validate_citations(
    cited_ids: Iterable[str], evidence_ids: set[str]
) -> CitationCheck:
    """A citation is valid only if its source ID exists in the retrieved
    evidence set (PRD FR-34, §10.1 step 9). Fabricated or out-of-scope IDs
    are reported for conservative handling."""
    valid: list[str] = []
    invalid: list[str] = []
    for cited in cited_ids:
        (valid if cited in evidence_ids else invalid).append(cited)
    return CitationCheck(valid_ids=tuple(valid), invalid_ids=tuple(invalid))


@dataclass
class BudgetAccount:
    """Tracks context token spend against a strict budget (FR-19)."""

    max_tokens: int
    spent: int = 0
    items: list[str] = field(default_factory=list)

    @property
    def remaining(self) -> int:
        return max(0, self.max_tokens - self.spent)

    def try_add(self, text: str, tokens: int) -> bool:
        if tokens > self.remaining:
            return False
        self.spent += tokens
        self.items.append(text)
        return True
