"""In-process background job manager behind the JobRunner interface (§6.2).

Single-process MVP; the interface (submit + event stream + terminal query)
is what a durable-queue migration would implement later. Events are kept in
a bounded ring buffer per job; the DB row remains the durable status copy.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.jobs.events import TERMINAL_JOB_STATUSES, JobEvent

logger = get_logger(__name__)

_MAX_EVENTS_PER_JOB = 500


@dataclass
class JobState:
    job_id: str
    repository_id: str
    events: list[JobEvent] = field(default_factory=list)
    condition: threading.Condition = field(default_factory=threading.Condition)

    @property
    def terminal(self) -> bool:
        return bool(self.events) and self.events[-1].status in TERMINAL_JOB_STATUSES


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = threading.Lock()

    def register(self, job_id: str, repository_id: str) -> JobState:
        state = JobState(job_id=job_id, repository_id=repository_id)
        with self._lock:
            self._jobs[job_id] = state
        return state

    def publish(self, job_id: str, event: JobEvent) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                logger.warning("Event for unknown job %s dropped", job_id)
                return
            state.events.append(event)
            if len(state.events) > _MAX_EVENTS_PER_JOB:
                del state.events[: len(state.events) - _MAX_EVENTS_PER_JOB]
            with state.condition:
                state.condition.notify_all()

    def events_after(self, job_id: str, after_index: int) -> tuple[list[JobEvent], bool]:
        """Returns (new events beyond *after_index*, whether the job is over)."""
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                return [], True
            events = state.events[after_index:]
            return list(events), state.terminal

    def has_job(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._jobs

    def submit(self, job_id: str, target: Callable[[], None]) -> None:
        def _runner() -> None:
            try:
                target()
            except Exception:  # noqa: BLE001 - logged by the pipeline itself
                logger.exception("Background job %s crashed", job_id)

        thread = threading.Thread(target=_runner, name=f"ig-job-{job_id}", daemon=True)
        thread.start()

    def wait_for_terminal(self, job_id: str, timeout: float = 60.0) -> bool:
        """Test helper: block until the job publishes a terminal event."""
        with self._lock:
            state = self._jobs.get(job_id)
        if state is None:
            return False
        import time as _time

        end = _time.monotonic() + timeout
        with state.condition:
            while not state.terminal:
                remaining = end - _time.monotonic()
                if remaining <= 0:
                    return False
                state.condition.wait(remaining)
        return True
