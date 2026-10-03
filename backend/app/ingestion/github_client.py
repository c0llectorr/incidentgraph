"""Constrained GitHub access (PRD §8.3 GitHubRepositoryClient row).

Only allow-listed hosts are ever contacted (assert_safe_fetch_url at every
request), timeouts and byte caps are enforced, and only transient failures
are retried with capped backoff (§6.2).
"""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.core.errors import LimitExceededError, RepositoryFetchFailedError
from app.core.logging import get_logger
from app.core.retry import retry_transient
from app.core.security import assert_safe_fetch_url
from app.domain.interfaces import NormalizedGitHubSource, RepositoryMetadata

logger = get_logger(__name__)

_USER_AGENT = "IncidentGraph-MVP/0.1 (+repository-ingestion)"

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class GitHubRepositoryClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._timeout = settings.github_timeout_seconds

    # -- internals ---------------------------------------------------------

    def _request(self, url: str, *, stream_cap: int | None = None) -> httpx.Response:
        assert_safe_fetch_url(url)

        def _send() -> httpx.Response:
            with httpx.Client(timeout=self._timeout, follow_redirects=False) as client:
                response = client.get(url, headers={"User-Agent": _USER_AGENT})
            if response.status_code in _RETRYABLE_STATUS:
                raise RepositoryFetchFailedError(
                    f"GitHub returned a transient status {response.status_code}."
                )
            if response.status_code == 404:
                raise RepositoryFetchFailedError(
                    "The public repository could not be fetched (not found or private)."
                )
            response.raise_for_status()
            return response

        def _is_transient(exc: Exception) -> bool:
            if isinstance(exc, RepositoryFetchFailedError):
                message = str(exc)
                return "transient" in message
            if isinstance(exc, httpx.HTTPStatusError):
                return exc.response.status_code in _RETRYABLE_STATUS
            return isinstance(exc, (httpx.TimeoutException, httpx.TransportError))

        try:
            return retry_transient(
                _send,
                is_transient=_is_transient,
                max_retries=3,
                base_delay_seconds=0.5,
                max_delay_seconds=6.0,
            )
        except RepositoryFetchFailedError:
            raise
        except Exception as exc:
            logger.warning("GitHub fetch failed for %s: %s", url, type(exc).__name__)
            raise RepositoryFetchFailedError(
                "The public repository could not be fetched."
            ) from exc

    # -- public interface --------------------------------------------------

    def resolve_metadata(self, source: NormalizedGitHubSource) -> RepositoryMetadata:
        url = f"https://api.github.com/repos/{source.slug}"
        payload = self._request(url).json()
        default_branch = payload.get("default_branch") or "main"
        if source.commit:
            sha = source.commit
        else:
            ref = source.branch or default_branch
            commit_url = f"https://api.github.com/repos/{source.slug}/commits/{ref}"
            sha = self._request(commit_url).json().get("sha")
            if not sha:
                raise RepositoryFetchFailedError("Could not resolve the requested revision.")
        return RepositoryMetadata(
            slug=source.slug,
            default_branch=default_branch,
            commit_sha=sha,
            html_url=payload.get("html_url") or f"https://github.com/{source.slug}",
        )

    def fetch_archive(self, source: NormalizedGitHubSource, *, commit_sha: str | None) -> bytes:
        ref = commit_sha or source.commit or source.branch or "HEAD"
        url = f"https://codeload.github.com/{source.slug}/zip/{ref}"
        cap = self._settings.max_total_extracted_bytes

        with httpx.Client(timeout=self._timeout, follow_redirects=False) as client:
            try:
                with client.stream("GET", url, headers={"User-Agent": _USER_AGENT}) as response:
                    if response.status_code in _RETRYABLE_STATUS:
                        raise RepositoryFetchFailedError(
                            "GitHub returned a transient status while fetching the archive."
                        )
                    if response.status_code == 404:
                        raise RepositoryFetchFailedError(
                            "The repository archive could not be fetched (not found or private)."
                        )
                    response.raise_for_status()
                    buffer = bytearray()
                    for chunk in response.iter_bytes(chunk_size=64 * 1024):
                        buffer.extend(chunk)
                        if len(buffer) > cap:
                            raise LimitExceededError(
                                "Repository archive exceeds the configured download limit."
                            )
                    return bytes(buffer)
            except LimitExceededError:
                raise
            except RepositoryFetchFailedError:
                raise
            except Exception as exc:
                logger.warning("Archive fetch failed for %s: %s", source.slug, type(exc).__name__)
                raise RepositoryFetchFailedError(
                    "The repository archive could not be fetched."
                ) from exc
