"""WP-1 gate: app skeleton, health route, error envelope, CORS."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import AppContainer
from app.core.config import Settings
from app.core.errors import InvalidSourceError
from app.main import create_app


def make_settings(tmp_path) -> Settings:
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{tmp_path/'test.db'}",
        data_dir=tmp_path / "data",
        upload_dir=tmp_path / "data" / "uploads",
        tmp_dir=tmp_path / "data" / "tmp",
        chroma_persist_dir=tmp_path / "data" / "chroma",
        frontend_origin="http://localhost:5173",
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture()
def app(tmp_path) -> FastAPI:
    settings = make_settings(tmp_path)
    return create_app(settings=settings, container=AppContainer(settings=settings))


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_health_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_leak_configuration(client: TestClient) -> None:
    body = client.get("/api/v1/health").json()
    assert set(body.keys()) == {"status"}


def test_unknown_route_leaks_no_internals(client: TestClient) -> None:
    response = client.get("/api/v1/definitely-not-here")
    assert response.status_code == 404
    assert "traceback" not in response.text.lower()
    assert "site-packages" not in response.text


def test_incidentgraph_error_uses_envelope(app: FastAPI) -> None:
    @app.get("/api/v1/boom", include_in_schema=False)
    def boom() -> None:
        raise InvalidSourceError("Bad source.")

    client = TestClient(app)
    response = client.get("/api/v1/boom")
    assert response.status_code == 400
    payload = response.json()
    assert set(payload.keys()) == {"error"}
    error = payload["error"]
    assert error["code"] == "INVALID_SOURCE"
    assert error["message"] == "Bad source."
    assert error["retryable"] is False
    assert error["request_id"].startswith("req_")


def test_request_id_header_roundtrip(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "req_custom123"})
    assert response.headers["X-Request-ID"] == "req_custom123"


def test_cors_allows_configured_origin_only(client: TestClient) -> None:
    allowed = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    denied = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in denied.headers


def test_unhandled_exception_returns_safe_500(tmp_path) -> None:
    settings = make_settings(tmp_path)
    app = create_app(settings=settings, container=AppContainer(settings=settings))

    @app.get("/api/v1/boom500", include_in_schema=False)
    def boom500() -> None:
        raise RuntimeError("secret internal detail / C:\\Users\\secret")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/boom500")
    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in response.text
