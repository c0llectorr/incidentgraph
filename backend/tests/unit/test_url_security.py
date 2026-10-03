"""WP-4 gate: GitHub URL normalization + SSRF fail-closed matrix (FR-01)."""

from __future__ import annotations

import pytest

from app.core.errors import InvalidSourceError
from app.core.security import assert_safe_fetch_url, normalize_github_url


@pytest.mark.parametrize(
    ("raw", "expected_slug", "expected_branch", "expected_commit"),
    [
        ("https://github.com/acme/widget", "acme/widget", None, None),
        ("https://github.com/acme/widget.git", "acme/widget", None, None),
        ("https://github.com/acme/widget/", "acme/widget", None, None),
        ("https://github.com/acme/widget/tree/develop", "acme/widget", "develop", None),
        ("https://github.com/acme/widget/tree/feature/deep-branch", "acme/widget", "feature/deep-branch", None),
        (
            "https://github.com/acme/widget/tree/1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b",
            "acme/widget",
            None,
            "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b",
        ),
    ],
)
def test_valid_urls_normalize(
    raw: str, expected_slug: str, expected_branch: str | None, expected_commit: str | None
) -> None:
    source = normalize_github_url(raw)
    assert source.slug == expected_slug
    assert source.branch == expected_branch
    assert source.commit == expected_commit


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "github.com/acme/widget",  # no scheme
        "http://github.com/acme/widget",  # not https
        "https://gitlab.com/acme/widget",  # unsupported host
        "https://evil.github.com.example.com/acme/widget",
        "https://user:pass@github.com/acme/widget",  # credentials
        "https://127.0.0.1/acme/widget",  # SSRF target
        "https://localhost/acme/widget",
        "https://github.com/acme/widget?x=1",  # query
        "https://github.com/acme",  # missing repo
        "https://github.com/acme/widget/extra/deep/path",
        "https://github.com/acme/../secret",
        "ftp://github.com/acme/widget",
        "https://github.com/acme/widget/blob/main/file.py",  # unsupported shape
    ],
)
def test_invalid_urls_rejected_with_actionable_error(raw: str) -> None:
    with pytest.raises(InvalidSourceError) as excinfo:
        normalize_github_url(raw)
    assert excinfo.value.message  # every rejection carries a human-readable reason


@pytest.mark.parametrize(
    "url",
    [
        "http://api.github.com/repos/a/b",  # not https
        "https://evil.example.com/a.zip",  # non-allowlisted host
        "https://169.254.169.254/latest",  # link-local metadata
        "https://10.0.0.5/repo.zip",  # private range
        "https://codeload.github.com:8443/a/b/zip/main",  # odd port
    ],
)
def test_fetch_targets_fail_closed(url: str) -> None:
    with pytest.raises(InvalidSourceError):
        assert_safe_fetch_url(url)


def test_fetch_targets_allow_approved_hosts() -> None:
    assert_safe_fetch_url("https://api.github.com/repos/acme/widget")
    assert_safe_fetch_url("https://codeload.github.com/acme/widget/zip/refs/heads/main")
