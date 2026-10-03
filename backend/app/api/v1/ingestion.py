"""Ingestion endpoints (PRD §8.5): start job, read status, SSE event stream.

The SSE stream replays events from the in-memory manager, emits heartbeats,
and terminates after a terminal status. Polling `GET /jobs/{id}` is the
documented fallback (FR-44).
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_container
from app.schemas.ingestion import IngestionStartResponse, JobStatusOut
from app.jobs.events import TERMINAL_JOB_STATUSES

router = APIRouter()

_HEARTBEAT_SECONDS = 10.0
_POLL_SECONDS = 0.2


@router.post(
    "/repositories/{repository_id}/ingestions",
    response_model=IngestionStartResponse,
    status_code=202,
)
def start_ingestion(repository_id: str) -> IngestionStartResponse:
    container = get_container()
    assert container.repository_service is not None
    assert container.ingestion_service is not None
    repository_row = container.repository_service.get(repository_id)
    job_id = container.ingestion_service.start_ingestion(repository_id, repository_row=repository_row)
    return IngestionStartResponse(job_id=job_id, repository_id=repository_id)


@router.get("/jobs/{job_id}", response_model=JobStatusOut)
def job_status(job_id: str) -> JobStatusOut:
    service = get_container().ingestion_service
    assert service is not None
    return JobStatusOut(**service.job_status(job_id))


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    container = get_container()
    assert container.ingestion_service is not None
    service = container.ingestion_service

    async def stream():
        cursor = 0
        heartbeat_timer = 0.0
        # Replay from the beginning; if the manager no longer holds the job
        # (restart), the DB-backed /jobs/{id} polling fallback covers it.
        while True:
            events, terminal = service.events_after(job_id, cursor)
            for event in events:
                cursor += 1
                payload = {
                    "job_id": event.job_id,
                    "repository_id": "",
                    "stage": event.stage,
                    "status": event.status,
                    "percent": event.percent,
                    "indeterminate": event.indeterminate,
                    "completed_units": event.completed_units,
                    "total_units": event.total_units,
                    "message": event.message,
                    "error_code": event.error_code,
                    "updated_at": event.updated_at,
                }
                yield f"id: {cursor}\nevent: progress\ndata: {json.dumps(payload)}\n\n"
                if event.status in TERMINAL_JOB_STATUSES:
                    return
            if terminal and cursor == 0:
                # Unknown job: tell the client to fall back to polling.
                yield (
                    f"id: 0\nevent: progress\ndata: {json.dumps({'job_id': job_id, 'status': 'unknown'})}\n\n"
                )
                return
            await asyncio.sleep(_POLL_SECONDS)
            heartbeat_timer += _POLL_SECONDS
            if heartbeat_timer >= _HEARTBEAT_SECONDS:
                heartbeat_timer = 0.0
                yield ": heartbeat\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
