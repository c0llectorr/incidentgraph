"""Job progress events — the §12.6 backend-to-frontend contract."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from app.domain.enums import JobStatus


@dataclass(frozen=True)
class JobEvent:
    job_id: str
    stage: str
    status: str
    completed_units: int
    total_units: int | None
    percent: float | None
    indeterminate: bool
    message: str
    updated_at: str
    error_code: str | None = None

    def to_sse_payload(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def now_iso() -> str:
        return datetime.now(UTC).isoformat()


TERMINAL_JOB_STATUSES = {
    JobStatus.SUCCEEDED.value,
    JobStatus.FAILED.value,
    JobStatus.CANCELLED.value,
}
