"""WP-3 gate: persistence round-trips for the §13 entities."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.persistence.database import create_engine_from_settings, create_session_factory
from app.persistence.models import (
    CodeChunkRow,
    ConversationMessageRow,
    FileRecordRow,
    HypothesisRow,
    IncidentArtifactRow,
    IncidentRow,
    IngestionJobRow,
    RepositoryRow,
)
from app.persistence.repositories import (
    ChunkRepository,
    IncidentRepository,
    JobRepository,
    MessageRepository,
    RepositoryRepository,
)
from app.persistence.unit_of_work import UnitOfWork


@pytest.fixture()
def uow(tmp_path) -> UnitOfWork:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite:///{tmp_path/'p.db'}",
        data_dir=tmp_path,
        upload_dir=tmp_path / "u",
        tmp_dir=tmp_path / "t",
        chroma_persist_dir=tmp_path / "c",
        _env_file=None,  # type: ignore[call-arg]
    )
    engine = create_engine_from_settings(settings)
    from app.persistence.models import Base

    Base.metadata.create_all(engine)
    factory: sessionmaker = create_session_factory(engine)
    return UnitOfWork(factory)


def test_repository_and_job_round_trip(uow: UnitOfWork) -> None:
    repo = RepositoryRow(
        id="rep_1",
        source_type="github",
        source_reference="https://github.com/acme/widget",
        owner="acme",
        repo="widget",
        branch="main",
        configuration_fingerprint="fp123",
    )
    job = IngestionJobRow(id="job_1", repository_id="rep_1")
    with uow.begin() as session:
        RepositoryRepository().add(session, repo)
        JobRepository().add(session, job)

    with uow.begin() as session:
        found = RepositoryRepository().get(session, "rep_1")
        assert found is not None
        assert found.status == "not_indexed"
        jobs = JobRepository().list_by_repository(session, "rep_1")
        assert [j.id for j in jobs] == ["job_1"]

        updated = RepositoryRepository().update_index_state(
            session, "rep_1", index_version="idx_1", status="ready", file_count=12
        )
        assert updated is not None
        assert updated.status == "ready"


def test_chunk_round_trip_and_lexical_search(uow: UnitOfWork) -> None:
    rows = [
        CodeChunkRow(
            chunk_id="chk_1",
            repository_id="rep_1",
            index_version="idx_1",
            path="app/auth.py",
            language="python",
            chunk_type="function",
            chunking_method="python_ast",
            start_line=1,
            end_line=10,
            symbol_name="authenticate",
            content="def authenticate(user): ...",
            content_hash="h1",
        ),
        CodeChunkRow(
            chunk_id="chk_2",
            repository_id="rep_1",
            index_version="idx_1",
            path="app/db.py",
            language="python",
            chunk_type="function",
            chunking_method="python_ast",
            start_line=1,
            end_line=5,
            symbol_name="create_connection",
            content="def create_connection(): ...",
            content_hash="h2",
        ),
    ]
    with uow.begin() as session:
        ChunkRepository().add_many(session, rows)

    with uow.begin() as session:
        repo = ChunkRepository()
        assert repo.count(session, "rep_1", "idx_1") == 2
        hits = repo.search_lexical(session, "rep_1", "idx_1", ["create_connection"], limit=5)
        assert [r.chunk_id for r in hits] == ["chk_2"]
        assert repo.get_many(session, ["chk_1", "chk_missing"])[0].chunk_id == "chk_1"


def test_incident_artifact_separation_and_cascade(uow: UnitOfWork) -> None:
    with uow.begin() as session:
        RepositoryRepository().add(
            session,
            RepositoryRow(
                id="rep_1",
                source_type="zip",
                source_reference="uploads/rep_1/source.zip",
                configuration_fingerprint="fp",
            ),
        )
        IncidentRepository().add(
            session,
            IncidentRow(
                id="inc_1",
                repository_id="rep_1",
                index_version="idx_1",
                title="Checkout 500s",
                description="POST /orders/checkout returns 500",
            ),
        )
        IncidentRepository().add_artifact(
            session,
            IncidentArtifactRow(
                artifact_id="art_1",
                incident_id="inc_1",
                repository_id="rep_1",
                index_version="idx_1",
                type="traceback",
                content="Traceback ...",
                size_bytes=14,
            ),
        )
        IncidentRepository().add_hypothesis(
            session,
            HypothesisRow(
                hypothesis_id="hyp_1",
                incident_id="inc_1",
                title="Regression in discount handling",
                explanation="...",
            ),
        )
        MessageRepository().add(
            session,
            ConversationMessageRow(
                message_id="msg_1",
                conversation_id="conv_1",
                scope_type="incident",
                repository_id="rep_1",
                incident_id="inc_1",
                role="user",
                content="what happened?",
            ),
        )

    with uow.begin() as session:
        incident_repo = IncidentRepository()
        artifacts = incident_repo.artifacts_for(session, "inc_1")
        assert len(artifacts) == 1
        assert artifacts[0].type == "traceback"
        hypotheses = incident_repo.hypotheses_for(session, "inc_1")
        assert hypotheses[0].status == "unverified"

        # FK from artifact → incident prevents orphan artifacts on delete.
        deleted = incident_repo.delete_by_repository(session, "rep_1")
        assert deleted == (1, 1, 1)
        from sqlalchemy import select as _select

        assert len(list(session.scalars(_select(FileRecordRow.id)))) == 0
