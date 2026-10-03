"""Typed error hierarchy and the stable error contract (PRD §8.6).

Every user-facing failure maps to one of these codes; handlers in app.main
render the `{error: {code, message, request_id, retryable}}` envelope and
never leak stack traces, environment variables, paths, or provider responses.
"""

from __future__ import annotations

from typing import Any


class IncidentGraphError(Exception):
    code = "INTERNAL_ERROR"
    http_status = 500
    retryable = False
    default_message = "An internal error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        http_status: int | None = None,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.default_message)
        self.message = message or self.default_message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        if retryable is not None:
            self.retryable = retryable
        self.details: dict[str, Any] = details or {}


class ValidationError(IncidentGraphError):
    code = "VALIDATION_ERROR"
    http_status = 422
    default_message = "The request payload is invalid."


class InvalidSourceError(IncidentGraphError):
    code = "INVALID_SOURCE"
    http_status = 400
    default_message = "The provided source is not supported."


class RepositoryFetchFailedError(IncidentGraphError):
    code = "REPOSITORY_FETCH_FAILED"
    http_status = 502
    retryable = True
    default_message = "The public repository could not be fetched."


class ArchiveUnsafeError(IncidentGraphError):
    code = "ARCHIVE_UNSAFE"
    http_status = 400
    default_message = "The archive was rejected by safety checks."


class LimitExceededError(IncidentGraphError):
    code = "LIMIT_EXCEEDED"
    http_status = 413
    default_message = "A configured size or count limit was exceeded."


class IndexNotReadyError(IncidentGraphError):
    code = "INDEX_NOT_READY"
    http_status = 409
    default_message = "The repository index is not ready for queries yet."


class ProviderError(IncidentGraphError):
    code = "PROVIDER_ERROR"
    http_status = 502
    retryable = True
    default_message = "A model provider request failed."


class EvidenceInsufficientError(IncidentGraphError):
    """Not an HTTP failure by itself: the RCA workflow converts this into an
    evidence-gap report and chat into an honest insufficiency answer."""

    code = "EVIDENCE_INSUFFICIENT"
    http_status = 422
    default_message = "The available evidence is insufficient."


class WorkflowNodeFailedError(IncidentGraphError):
    code = "WORKFLOW_NODE_FAILED"
    http_status = 500
    retryable = True
    default_message = "An investigation workflow step failed."


class NotFoundError(IncidentGraphError):
    code = "NOT_FOUND"
    http_status = 404
    default_message = "The requested resource does not exist."


class DeletionFailedError(IncidentGraphError):
    code = "DELETION_FAILED"
    http_status = 500
    default_message = "The deletion operation did not complete fully."
