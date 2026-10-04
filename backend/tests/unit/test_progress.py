"""ProgressTracker unit tests (PRD FR-46, §12.6).

Percentages are on a 0–100 scale (§12.6 examples: "fetch 5%, chunk 29%,
embed 80%"), monotonic, work-unit based, and indeterminate when totals are
unknown. The 0–100 scale is a regression guard: fractions (0–1) rendered by
the frontend once showed as a frozen "1%".
"""

from __future__ import annotations

import pytest

from app.domain.enums import IngestionStage
from app.ingestion.progress import ProgressTracker

_STAGES = [
    IngestionStage.VALIDATING_SOURCE,
    IngestionStage.FETCHING_REPOSITORY,
    IngestionStage.EXTRACTING_FILES,
    IngestionStage.FILTERING_FILES,
    IngestionStage.PARSING_AND_CHUNKING,
    IngestionStage.EMBEDDING,
    IngestionStage.PERSISTING_INDEX,
    IngestionStage.VERIFYING_INDEX,
]


def complete_through(tracker: ProgressTracker, stage: IngestionStage, total: int = 1) -> None:
    for current in _STAGES:
        tracker.start_stage(current, total=total)
        tracker.complete_stage(current)
        if current is stage:
            return


def test_percent_is_on_zero_to_hundred_scale() -> None:
    tracker = ProgressTracker()
    tracker.start_stage(IngestionStage.VALIDATING_SOURCE, total=1)
    tracker.complete_stage(IngestionStage.VALIDATING_SOURCE)
    percent, _ = tracker.snapshot()
    assert percent == 2.0  # stage weight 0.02 → "2%", not 0.02


def test_embedding_stage_reports_mid_scale_percent() -> None:
    """Regression for the frozen '1%': at the start of embedding the overall
    percent must be ~50 (all prior weights), and the UI renders it as 50%."""
    tracker = ProgressTracker()
    complete_through(tracker, IngestionStage.PARSING_AND_CHUNKING)
    tracker.start_stage(IngestionStage.EMBEDDING, total=10)
    percent, indeterminate = tracker.snapshot()
    assert percent == pytest.approx(50.0)
    assert indeterminate is False

    tracker.advance(IngestionStage.EMBEDDING, 5)
    percent, _ = tracker.snapshot()
    assert percent == pytest.approx(67.5)  # 50 + 0.35 * 0.5 → 67.5


def test_all_stages_complete_reaches_exactly_100() -> None:
    tracker = ProgressTracker()
    for stage in _STAGES:
        tracker.start_stage(stage, total=1)
        tracker.complete_stage(stage)
    percent, indeterminate = tracker.snapshot()
    assert percent == 100.0
    assert indeterminate is False


def test_unknown_totals_are_indeterminate_without_invented_percent() -> None:
    tracker = ProgressTracker()
    tracker.start_stage(IngestionStage.VALIDATING_SOURCE, total=1)
    tracker.complete_stage(IngestionStage.VALIDATING_SOURCE)
    tracker.start_stage(IngestionStage.FETCHING_REPOSITORY, total=None)
    percent, indeterminate = tracker.snapshot()
    assert indeterminate is True
    assert percent == 2.0  # completed prefix only — nothing invented


def test_percent_is_monotonic() -> None:
    tracker = ProgressTracker()
    tracker.start_stage(IngestionStage.EMBEDDING, total=4)
    seen = []
    for _ in range(4):
        tracker.advance(IngestionStage.EMBEDDING)
        seen.append(tracker.snapshot()[0])
    assert seen == sorted(seen)
    assert seen[-1] == pytest.approx(35.0)
