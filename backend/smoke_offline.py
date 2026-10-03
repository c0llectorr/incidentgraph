"""Offline full-stack smoke test (WP-21 gate).

Boots the REAL app — real HTTP server, real SQLite, real pipeline, real
chunking — with two deterministic substitutes: the hashing embedder and the
in-memory vector store. Verifies upload → ingest → ready → evidence retrieval
works end to end without any provider credentials or model downloads.

Run:  python smoke_offline.py   (from backend/)
"""

from __future__ import annotations

import io
import sys
import tempfile
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.dependencies import AppContainer  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.embeddings.fake import HashingEmbeddingProvider  # noqa: E402
from app.main import create_app  # noqa: E402
from app.persistence.models import Base  # noqa: E402
from tests.fixtures.in_memory_store import InMemoryVectorStore  # noqa: E402

FILES = {
    "widget-main/app/auth.py": (
        "import hashlib\n\n"
        "def authenticate(username: str, password: str):\n"
        '    """Verify credentials against the user store."""\n'
        "    return hashlib.sha256(password.encode()).hexdigest() == STORE[username]\n"
    ),
    "widget-main/app/db.py": (
        "import sqlite3\n\n"
        "def create_connection(path='app.db'):\n"
        '    """Create a SQLite database connection."""\n'
        "    return sqlite3.connect(path)\n"
    ),
    "widget-main/README.md": "# Widget\n\nA demo service.\n",
}


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="ig-smoke-"))
    settings = Settings(
        app_env="development",
        database_url=f"sqlite:///{tmp/'smoke.db'}",
        data_dir=tmp / "data",
        upload_dir=tmp / "data" / "uploads",
        tmp_dir=tmp / "data" / "tmp",
        chroma_persist_dir=tmp / "data" / "chroma",
        _env_file=None,
    )
    container = AppContainer(settings=settings)
    container._embedder_override = HashingEmbeddingProvider()
    container._vector_store_override = InMemoryVectorStore()
    Base.metadata.create_all(container.engine)
    client = TestClient(create_app(settings=settings, container=container))

    print("[1/5] health……", end=" ")
    assert client.get("/api/v1/health").status_code == 200
    print("ok")

    print("[2/5] upload zip…", end=" ")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in FILES.items():
            archive.writestr(name, content)
    created = client.post(
        "/api/v1/repositories",
        files={"file": ("widget.zip", buffer.getvalue(), "application/zip")},
    )
    assert created.status_code == 201, created.text
    repository_id = created.json()["id"]
    print(f"ok ({repository_id})")

    print("[3/5] ingest…", end=" ")
    job_id = client.post(f"/api/v1/repositories/{repository_id}/ingestions").json()["job_id"]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        status = client.get(f"/api/v1/jobs/{job_id}").json()
        if status["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.1)
    assert status["status"] == "succeeded", status
    print(f"ok ({status['percent']}%)")

    print("[4/5] index queryable…", end=" ")
    repository = client.get(f"/api/v1/repositories/{repository_id}").json()
    assert repository["status"] == "ready"
    store = container.build_vector_store()
    assert store.count(
        repository_id=repository_id, index_version=repository["index_version"]
    ) > 0
    print("ok")

    print("[5/5] weak-retrieval honesty…", end=" ")
    # Tokens don't overlap the indexed code, so retrieval is weak: the system
    # must answer with an explicit insufficiency — never a fabricated answer
    # and never a fabricated citation (FR-24).
    chat = client.post(
        f"/api/v1/repositories/{repository_id}/chat",
        json={"question": "zzzqqx kafka consumer group rebalancing offsets qwzzz"},
    )
    assert chat.status_code == 200, chat.text
    body = chat.json()
    assert body["status"] == "insufficient_evidence", body
    assert body["citations"] == []
    assert body["clarifying_question"]
    print("ok (honest insufficiency, no fabrication)")

    print("\nSmoke passed: the full stack is wired and honest without provider keys.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
