"""Integration fixtures: real app + fake embeddings + in-memory vector store."""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import AppContainer
from app.core.config import Settings
from app.embeddings.fake import HashingEmbeddingProvider
from app.main import create_app
from tests.fixtures.in_memory_store import InMemoryVectorStore


def make_settings(tmp_path, **overrides) -> Settings:
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{tmp_path/'test.db'}",
        data_dir=tmp_path / "data",
        upload_dir=tmp_path / "data" / "uploads",
        tmp_dir=tmp_path / "data" / "tmp",
        chroma_persist_dir=tmp_path / "data" / "chroma",
        frontend_origin="http://localhost:5173",
        _env_file=None,  # type: ignore[call-arg]
        **overrides,
    )


@pytest.fixture()
def container(tmp_path):
    settings = make_settings(tmp_path)
    instance = AppContainer(settings=settings)
    instance._embedder_override = HashingEmbeddingProvider()
    instance._vector_store_override = InMemoryVectorStore()
    from app.persistence.models import Base

    Base.metadata.create_all(instance.engine)
    return instance


@pytest.fixture()
def app(container) -> FastAPI:
    return create_app(settings=container.settings, container=container)


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


def build_zip(entries: dict[str, str | bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


SAMPLE_REPO_FILES = {
    "widget-main/app/main.py": (
        "from fastapi import FastAPI\n"
        "from app.auth import authenticate\n"
        "app = FastAPI()\n"
        "@app.post('/login')\n"
        "def login(username: str, password: str):\n"
        "    user = authenticate(username, password)\n"
        "    return {'ok': user is not None}\n"
    ),
    "widget-main/app/auth.py": (
        "import hashlib\n"
        "\n"
        "def authenticate(username: str, password: str):\n"
        '    """Verify credentials against the user store."""\n'
        "    digest = hashlib.sha256(password.encode()).hexdigest()\n"
        "    return USERS.get(username) == digest\n"
        "\n"
        "USERS = {'alice': 'e3b0c44298fc1c149afbf4c8996fb924'}\n"
    ),
    "widget-main/app/db.py": (
        "import sqlite3\n"
        "\n"
        "def create_connection(path='app.db'):\n"
        '    """Create a SQLite database connection."""\n'
        "    return sqlite3.connect(path)\n"
    ),
    "widget-main/README.md": (
        "# Widget\n\nA small FastAPI service.\n\n## Setup\n\npip install -r requirements.txt\n"
    ),
    "widget-main/requirements.txt": "fastapi>=0.100\nuvicorn>=0.23\n",
    "widget-main/.env": "SECRET_KEY=should-never-be-embedded\n",
}


@pytest.fixture()
def uploaded_repository(client: TestClient) -> dict:
    zip_bytes = build_zip(SAMPLE_REPO_FILES)
    response = client.post(
        "/api/v1/repositories",
        files={"file": ("widget.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def ingest_and_wait(client: TestClient, repository_id: str) -> dict:
    response = client.post(f"/api/v1/repositories/{repository_id}/ingestions")
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    deadline = 120.0
    import time

    started = time.monotonic()
    while time.monotonic() - started < deadline:
        status = client.get(f"/api/v1/jobs/{job_id}").json()
        if status["status"] in {"succeeded", "failed", "cancelled"}:
            return status
        time.sleep(0.1)
    raise AssertionError("Ingestion job did not finish in time")
