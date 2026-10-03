"""WP-8 gate: end-to-end ingestion from ZIP upload with real pipeline stages,
fake embeddings, and an in-memory vector store. Verifies §9.1 ordering,
honest progress, secret exclusion, and the verify-before-ready gate."""

from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from tests.integration.conftest import (
    SAMPLE_REPO_FILES,
    build_zip,
    ingest_and_wait,
    make_settings,
)


def test_full_ingestion_reaches_ready(client: TestClient, uploaded_repository: dict) -> None:
    repository_id = uploaded_repository["id"]
    status = ingest_and_wait(client, repository_id)

    assert status["status"] == "succeeded", status
    assert status["stage"] == "ready"
    assert status["percent"] == 100.0
    assert status["error_code"] is None

    repository = client.get(f"/api/v1/repositories/{repository_id}").json()
    assert repository["status"] == "ready"
    assert repository["index_version"] is not None
    # 6 source files; .env excluded by the secret scanner, .pyc excluded by filter.
    assert repository["file_count"] == len(SAMPLE_REPO_FILES)


def test_secret_file_is_excluded_but_reported(
    client: TestClient, container, uploaded_repository: dict
) -> None:
    repository_id = uploaded_repository["id"]
    status = ingest_and_wait(client, repository_id)
    assert status["status"] == "succeeded"

    from sqlalchemy import select

    from app.persistence.models import FileRecordRow

    with container.uow.begin() as session:
        rows = list(
            session.scalars(
                select(FileRecordRow).where(FileRecordRow.repository_id == repository_id)
            )
        )
    env_rows = [row for row in rows if row.relative_path.endswith(".env")]
    assert len(env_rows) == 1
    assert env_rows[0].filter_status == "excluded"
    assert "secret" in (env_rows[0].filter_reason or "")
    # The excluded file's contents are never stored.
    assert "should-never-be-embedded" not in str(rows)


def test_chunk_content_contains_no_secret(
    client: TestClient, container, uploaded_repository: dict
) -> None:
    ingest_and_wait(client, uploaded_repository["id"])

    from sqlalchemy import select

    from app.persistence.models import CodeChunkRow

    with container.uow.begin() as session:
        rows = list(
            session.scalars(
                select(CodeChunkRow).where(CodeChunkRow.repository_id == uploaded_repository["id"])
            )
        )
    assert rows, "expected chunks to be persisted"
    joined = "\n".join(row.content for row in rows)
    assert "should-never-be-embedded" not in joined
    # AST chunking ran for Python: symbol names are recorded (FR-12).
    symbols = {row.symbol_name for row in rows if row.symbol_name}
    assert "authenticate" in symbols
    assert all(row.index_version for row in rows)


def test_sse_stream_replays_stages_in_order(client: TestClient, uploaded_repository: dict) -> None:
    repository_id = uploaded_repository["id"]
    status = ingest_and_wait(client, repository_id)
    assert status["status"] == "succeeded"

    with client.stream("GET", f"/api/v1/jobs/{list_jobs_helper(client, repository_id)}/events") as response:
        body = b"".join(response.iter_raw()).decode("utf-8")

    # Terminal event must terminate the stream: the request completed above.
    assert "event: progress" in body
    events = [json.loads(line.removeprefix("data: ")) for line in body.splitlines() if line.startswith("data: ")]
    # Each stage emits running + completed events; collapse consecutive
    # duplicates to get one entry per stage, in order.
    stages = [event["stage"] for event in events]
    stages = [stage for index, stage in enumerate(stages) if index == 0 or stages[index - 1] != stage]
    # FR-45 stage order for a ZIP source (subset, in order; there is no
    # GitHub fetch stage for an uploaded archive).
    expected_order = [
        "validating_source",
        "extracting_files",
        "filtering_files",
        "parsing_and_chunking",
        "embedding",
        "persisting_index",
        "verifying_index",
        "ready",
    ]
    assert stages == expected_order
    final = events[-1]
    assert final["status"] == "succeeded"
    assert final["percent"] == 100.0


def list_jobs_helper(client: TestClient, repository_id: str) -> str:
    """Ingest again (idempotent path) to obtain a job id for the SSE test."""
    response = client.post(f"/api/v1/repositories/{repository_id}/ingestions")
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        status = client.get(f"/api/v1/jobs/{job_id}").json()
        if status["status"] in {"succeeded", "failed"}:
            return job_id
        time.sleep(0.1)
    raise AssertionError("second ingestion did not finish")


def test_percent_is_monotonic_across_events(client: TestClient, uploaded_repository: dict) -> None:
    repository_id = uploaded_repository["id"]
    job_id_response = client.post(f"/api/v1/repositories/{repository_id}/ingestions")
    job_id = job_id_response.json()["job_id"]

    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        status = client.get(f"/api/v1/jobs/{job_id}").json()
        if status["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.05)

    with client.stream("GET", f"/api/v1/jobs/{job_id}/events") as response:
        body = b"".join(response.iter_raw()).decode("utf-8")
    events = [json.loads(line.removeprefix("data: ")) for line in body.splitlines() if line.startswith("data: ")]
    percents = [event["percent"] for event in events if event["percent"] is not None]
    assert percents == sorted(percents), f"percent not monotonic: {percents}"
    assert percents[-1] == 100.0
    # Never 100% before the ready event (FR-46).
    non_final = [event for event in events if event["stage"] != "ready"]
    assert all((event["percent"] or 0) < 100.0 for event in non_final)


def test_idempotent_reingestion_reuses_unchanged_chunks(
    client: TestClient, container, uploaded_repository: dict
) -> None:
    """Same revision + config → identical chunk IDs (FR-13 groundwork)."""
    ingest_and_wait(client, uploaded_repository["id"])

    from sqlalchemy import select

    from app.persistence.models import CodeChunkRow

    with container.uow.begin() as session:
        first_ids = sorted(
            session.scalars(
                select(CodeChunkRow.chunk_id).where(
                    CodeChunkRow.repository_id == uploaded_repository["id"]
                )
            )
        )

    # No file changes: re-ingest produces the same stable IDs.
    client.query  # silence
    from app.services.repository_service import RepositoryService  # noqa: F401

    ingest_and_wait(client, uploaded_repository["id"])
    with container.uow.begin() as session:
        second_ids = sorted(
            session.scalars(
                select(CodeChunkRow.chunk_id).where(
                    CodeChunkRow.repository_id == uploaded_repository["id"]
                )
            )
        )
    assert first_ids == second_ids


def test_failed_ingestion_reports_safe_error(client: TestClient, tmp_path) -> None:
    """A corrupted archive at extraction time fails the job with a safe code."""
    from fastapi.testclient import TestClient as TC

    from app.api.dependencies import AppContainer
    from app.main import create_app
    from app.persistence.models import Base

    settings = make_settings(tmp_path, max_total_extracted_bytes=50)
    container = AppContainer(settings=settings)
    container._embedder_override = __import__(
        "app.embeddings.fake", fromlist=["HashingEmbeddingProvider"]
    ).HashingEmbeddingProvider()
    from tests.fixtures.in_memory_store import InMemoryVectorStore

    container._vector_store_override = InMemoryVectorStore()
    Base.metadata.create_all(container.engine)
    local_client = TC(create_app(settings=settings, container=container))

    big = build_zip({"w/huge.txt": "x" * 1000})
    created = local_client.post(
        "/api/v1/repositories", files={"file": ("big.zip", big, "application/zip")}
    )
    assert created.status_code == 201
    repository_id = created.json()["id"]

    status = ingest_and_wait(local_client, repository_id)
    assert status["status"] == "failed"
    assert status["error_code"] == "LIMIT_EXCEEDED"
    repository = local_client.get(f"/api/v1/repositories/{repository_id}").json()
    assert repository["status"] == "failed"
