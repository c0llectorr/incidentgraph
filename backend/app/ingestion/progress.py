"""Monotonic, stage-aware progress from completed work units (PRD FR-46, §12.6).

The backend is the source of truth. Percentages are computed from completed
units with configurable stage weights; unknown totals render as indeterminate
rather than an invented percentage; 100% is only reachable when the caller
marks the final stage complete after verification.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import IngestionStage
from app.domain.policies import STAGE_WEIGHTS

_STAGE_ORDER: list[IngestionStage] = [
    IngestionStage.VALIDATING_SOURCE,
    IngestionStage.FETCHING_REPOSITORY,
    IngestionStage.EXTRACTING_FILES,
    IngestionStage.FILTERING_FILES,
    IngestionStage.PARSING_AND_CHUNKING,
    IngestionStage.EMBEDDING,
    IngestionStage.PERSISTING_INDEX,
    IngestionStage.VERIFYING_INDEX,
]


@dataclass
class StageProgress:
    completed: int = 0
    total: int | None = None

    @property
    def fraction(self) -> float | None:
        if self.total in (None, 0):
            return None
        return min(1.0, self.completed / self.total)  # type: ignore[operator]


class ProgressTracker:
    def __init__(self, weights: dict[IngestionStage, float] | None = None) -> None:
        self._weights = weights or STAGE_WEIGHTS
        self._stage_progress: dict[IngestionStage, StageProgress] = {}
        self._current_stage: IngestionStage | None = None
        self._last_percent = 0.0

    def start_stage(self, stage: IngestionStage, total: int | None = None) -> None:
        self._current_stage = stage
        self._stage_progress[stage] = StageProgress(completed=0, total=total)

    @property
    def current_stage(self) -> IngestionStage | None:
        return self._current_stage

    def stage_state(self, stage: IngestionStage) -> StageProgress | None:
        return self._stage_progress.get(stage)

    def advance(self, stage: IngestionStage, units: int = 1) -> None:
        progress = self._stage_progress.setdefault(stage, StageProgress())
        progress.completed += units

    def complete_stage(self, stage: IngestionStage) -> None:
        progress = self._stage_progress.setdefault(stage, StageProgress())
        if progress.total is not None:
            progress.completed = max(progress.completed, progress.total)
        else:
            progress.total = max(progress.completed, 1)
            progress.completed = progress.total

    def snapshot(self) -> tuple[float, bool]:
        """Returns (percent, indeterminate). Percent is monotonic across calls
        and only reaches 100.0 when every stage is fully complete."""
        percent = 0.0
        indeterminate = False
        for stage in _STAGE_ORDER:
            progress = self._stage_progress.get(stage)
            weight = self._weights.get(stage, 0.0)
            if progress is None or progress.total is None or progress.fraction is None:
                if stage == self._current_stage:
                    indeterminate = True
                    break
                continue
            percent += weight * progress.fraction
        percent = min(100.0, percent)
        self._last_percent = max(self._last_percent, percent)
        return round(self._last_percent, 2), indeterminate
