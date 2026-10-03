"""URL and upload security helpers (PRD §6.1, FR-01, §8.3).

Fail closed: anything not explicitly recognized is rejected. No user-controlled
fetch targets are ever returned — callers fetch only through the constrained
GitHubRepositoryClient using values produced here.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from app.core.errors import InvalidSourceError
from app.domain.interfaces import NormalizedGitHubSource

GITHUB_HTML_HOSTS = {"github.com", "www.github.com"}
GITHUB_FETCH_HOSTS = {
    "github.com",
    "www.github.com",
    "api.github.com",
    "codeload.github.com",
    "objects.githubusercontent.com",
}

_OWNER_REPO_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,198}$")


def _reject(message: str) -> None:
    raise InvalidSourceError(message)


def normalize_github_url(raw_url: str) -> NormalizedGitHubSource:
    """Normalize a public GitHub URL to owner/repo plus branch or commit.

    Accepts: https://github.com/{owner}/{repo}[/tree/<ref>][.git]
    Rejects every other host, scheme, userinfo, or malformed shape with an
    actionable error (FR-01).
    """
    if not raw_url or not raw_url.strip():
        _reject("Provide a public GitHub repository URL.")
    candidate = raw_url.strip()

    parsed = urlparse(candidate)
    if parsed.scheme != "https":
        _reject("Only https:// GitHub URLs are accepted.")
    host = (parsed.hostname or "").lower()
    if host not in GITHUB_HTML_HOSTS:
        _reject("Only public github.com repository URLs are supported.")
    if parsed.username or parsed.password:
        _reject("Credentials in the URL are not accepted.")
    if parsed.port is not None:
        _reject("Custom ports are not accepted.")
    if parsed.query or parsed.fragment:
        _reject("Query strings and fragments are not accepted.")

    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 2:
        _reject("URL must include both owner and repository, e.g. https://github.com/owner/repo")

    owner, repo = segments[0], segments[1]
    for label, value in (("owner", owner), ("repository", repo)):
        if value.endswith(".git"):
            value = value[: -len(".git")]
        if not _OWNER_REPO_PATTERN.match(value) or value in {".", ".."}:
            _reject(f"The URL {label} segment is not a valid GitHub name.")
        if label == "owner":
            owner = value
        else:
            repo = value

    branch: str | None = None
    commit: str | None = None
    if len(segments) >= 4 and segments[2] == "tree":
        ref = "/".join(segments[3:])
        if not ref or len(ref) > 200:
            _reject("The branch or commit reference in the URL is invalid.")
        if len(ref) == 40 and all(character in "0123456789abcdef" for character in ref.lower()):
            commit = ref.lower()
        else:
            branch = ref
    elif len(segments) > 2:
        _reject("Unsupported GitHub URL shape; use github.com/owner/repo[/tree/branch].")

    return NormalizedGitHubSource(owner=owner, repo=repo, branch=branch, commit=commit)


def assert_safe_fetch_url(url: str) -> None:
    """Fail-closed check for any server-side fetch target (SSRF prevention)."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise InvalidSourceError("Fetch targets must use https.")
    host = (parsed.hostname or "").lower()
    if host not in GITHUB_FETCH_HOSTS:
        raise InvalidSourceError("Fetch target host is not allowed.")
    if parsed.port not in (None, 443):
        raise InvalidSourceError("Fetch target port is not allowed.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        # Host names in the allowlist are never IP literals; belt-and-braces.
        raise InvalidSourceError("IP-address fetch targets are not allowed.")
