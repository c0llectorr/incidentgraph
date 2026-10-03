"""Repository intake endpoints (PRD §8.5): POST /repositories (GitHub URL or
ZIP upload) and GET /repositories/{id}. No business logic lives here."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.dependencies import get_container
from app.core.errors import InvalidSourceError
from app.schemas.repository import RepositoryCreateFromUrl, RepositoryDeleted, RepositoryOut

router = APIRouter()


@router.post("/repositories", response_model=RepositoryOut, status_code=201)
async def create_repository(request: Request) -> RepositoryOut:
    service = get_container().repository_service
    assert service is not None
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        payload = RepositoryCreateFromUrl.model_validate(await request.json())
        row = service.create_from_github_url(payload.github_url)
    elif content_type.startswith("multipart/form-data"):
        form = await request.form()
        github_url = form.get("github_url")
        upload = form.get("file")
        if isinstance(github_url, str) and github_url.strip():
            row = service.create_from_github_url(github_url)
        elif upload is not None and hasattr(upload, "read"):
            # FR-02/FR-03: enforce the upload limit before anything else.
            limited_file = upload  # type: ignore[union-attr]
            content = await limited_file.read()
            if len(content) > get_container().settings.max_upload_bytes:
                from app.core.errors import LimitExceededError

                raise LimitExceededError(
                    "ZIP upload exceeds the configured limit of "
                    f"{get_container().settings.max_upload_bytes} bytes."
                )
            filename = getattr(upload, "filename", None) or "upload.zip"
            row = service.create_from_zip(filename, content)
        else:
            raise InvalidSourceError(
                "Provide either a github_url form field or a ZIP file upload."
            )
    else:
        raise InvalidSourceError(
            "Send application/json with a github_url, or multipart/form-data with a ZIP file."
        )

    return RepositoryOut.model_validate(row, from_attributes=True)


@router.get("/repositories/{repository_id}", response_model=RepositoryOut)
def get_repository(repository_id: str) -> RepositoryOut:
    service = get_container().repository_service
    assert service is not None
    return RepositoryOut.model_validate(service.get(repository_id), from_attributes=True)


@router.delete("/repositories/{repository_id}", response_model=RepositoryDeleted)
def delete_repository(repository_id: str) -> RepositoryDeleted:
    service = get_container().repository_service
    assert service is not None
    counts = service.delete_everything(repository_id)
    return RepositoryDeleted(repository_id=repository_id, **counts)
