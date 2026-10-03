"""WP-5 gate: archive security, file filters, secret scanning (§15.1).

Malicious archives are built programmatically — no network, no repo content.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.errors import ArchiveUnsafeError, LimitExceededError
from app.ingestion.archive_extractor import ArchiveExtractor
from app.ingestion.file_filter import FileFilter
from app.ingestion.secret_scanner import SecretScanner


def make_settings(tmp_path, **overrides) -> Settings:
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{tmp_path/'t.db'}",
        data_dir=tmp_path,
        upload_dir=tmp_path / "u",
        tmp_dir=tmp_path / "t",
        chroma_persist_dir=tmp_path / "c",
        _env_file=None,  # type: ignore[call-arg]
        **overrides,
    )


def build_zip(entries: dict[str, bytes | str], *, symlink: dict[str, str] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
        for name, target in (symlink or {}).items():
            info = zipfile.ZipInfo(name)
            info.external_attr = (0o120777 << 16) | 0o777  # symlink mode
            archive.writestr(info, target)
    return buffer.getvalue()


@pytest.fixture()
def extractor(tmp_path) -> ArchiveExtractor:
    return ArchiveExtractor(make_settings(tmp_path))


def test_clean_zip_extracts_with_prefix_stripped(extractor: ArchiveExtractor, tmp_path) -> None:
    data = build_zip(
        {
            "widget-abc123/app/main.py": "print('hi')\n",
            "widget-abc123/README.md": "# Widget\n",
            "widget-abc123/app/utils.py": "def helper(): pass\n",
        }
    )
    destination = tmp_path / "workspace"
    report = extractor.extract_zip_bytes(data, destination)

    assert report.relative_paths == ["README.md", "app/main.py", "app/utils.py"]
    assert report.stripped_prefix == "widget-abc123/"
    assert (destination / "app" / "main.py").read_text() == "print('hi')\n"
    assert report.total_bytes > 0


def test_path_traversal_rejected(extractor: ArchiveExtractor, tmp_path) -> None:
    data = build_zip({"widget-1/../../evil.txt": "boom"})
    with pytest.raises(ArchiveUnsafeError):
        extractor.extract_zip_bytes(data, tmp_path / "w")


def test_absolute_path_rejected(extractor: ArchiveExtractor, tmp_path) -> None:
    data = build_zip({"/etc/passwd": "root:x:0:0"})
    with pytest.raises(ArchiveUnsafeError):
        extractor.extract_zip_bytes(data, tmp_path / "w")


def test_symlink_member_rejected(extractor: ArchiveExtractor, tmp_path) -> None:
    data = build_zip(
        {"widget-1/normal.txt": "ok"},
        symlink={"widget-1/link.txt": "/etc/passwd"},
    )
    with pytest.raises(ArchiveUnsafeError):
        extractor.extract_zip_bytes(data, tmp_path / "w")


def test_compression_bomb_rejected(tmp_path) -> None:
    # 10 MB of zeros compress to a few KB — extreme ratio.
    settings = make_settings(tmp_path)
    extractor = ArchiveExtractor(settings)
    data = build_zip({"widget-1/zeros.bin": b"0" * (10 * 1024 * 1024)})
    with pytest.raises(ArchiveUnsafeError):
        extractor.extract_zip_bytes(data, tmp_path / "w")


def test_excessive_entry_count_rejected(tmp_path) -> None:
    settings = make_settings(tmp_path, max_repository_files=5)
    extractor = ArchiveExtractor(settings)
    data = build_zip({f"widget-1/file_{i}.txt": "x" for i in range(10)})
    with pytest.raises(LimitExceededError):
        extractor.extract_zip_bytes(data, tmp_path / "w")


def test_oversized_member_rejected(tmp_path) -> None:
    settings = make_settings(tmp_path, max_file_bytes=100)
    extractor = ArchiveExtractor(settings)
    data = build_zip({"widget-1/big.txt": "a" * 500})
    with pytest.raises(LimitExceededError):
        extractor.extract_zip_bytes(data, tmp_path / "w")


def test_malformed_archive_rejected(extractor: ArchiveExtractor, tmp_path) -> None:
    with pytest.raises(ArchiveUnsafeError):
        extractor.extract_zip_bytes(b"this is not a zip", tmp_path / "w")


# --- file filter -----------------------------------------------------------


def test_file_filter_matrix(tmp_path) -> None:
    settings = make_settings(tmp_path, max_file_bytes=1000)
    file_filter = FileFilter(settings)

    assert file_filter.decide("app/main.py", 100, b"def f(): pass").status == "included"
    assert file_filter.decide("app/__pycache__/main.cpython-312.pyc", 10, b"").reason == "excluded directory"
    assert file_filter.decide("node_modules/react/index.js", 10, b"").status == "excluded"
    assert file_filter.decide("poetry.lock", 100, b"").status == "excluded"
    assert file_filter.decide("assets/logo.png", 10, b"\x89PNG").status == "excluded"
    assert file_filter.decide("blob.dat", 10, b"\x00\x01\x02").reason == "binary content"
    assert file_filter.decide("big.txt", 5000, b"ok").reason == "file exceeds per-file size limit"


# --- secret scanner --------------------------------------------------------


def test_secret_filename_excluded_without_reading_contents() -> None:
    scanner = SecretScanner()
    verdict = scanner.verdict_for_filename("config/.env.production")
    assert verdict is not None and verdict.action == "exclude"
    assert "contents" in (verdict.reason or "")


def test_private_key_block_excludes_file() -> None:
    scanner = SecretScanner()
    verdict = scanner.scan_text(
        "key here\n-----BEGIN RSA PRIVATE KEY-----\nMIIEow...\n-----END RSA PRIVATE KEY-----\n"
    )
    assert verdict.action == "exclude"


def test_inline_secrets_are_redacted() -> None:
    scanner = SecretScanner()
    source = (
        "AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n"
        "GROQ = 'gsk_Abcdef1234567890abcdef'\n"
        "GITHUB = 'ghp_16CharactersLongTokenHereXX'\n"
    )
    verdict = scanner.scan_text(source)
    assert verdict.action == "redact"
    assert verdict.redacted_text is not None
    assert "AKIAIOSFODNN7EXAMPLE" not in verdict.redacted_text
    assert "gsk_" not in verdict.redacted_text.replace("[REDACTED:", "")
    assert "ghp_" not in verdict.redacted_text.replace("[REDACTED:", "")


def test_clean_text_kept() -> None:
    scanner = SecretScanner()
    verdict = scanner.scan_text("def authenticate(user): return token_verify(user)\n")
    assert verdict.action == "keep"


def test_env_content_never_scanned_through_filters(tmp_path) -> None:
    """FR-08: raw .env contents must never reach chunks; the filename rule
    excludes them before content is read."""
    settings = make_settings(tmp_path)
    file_filter = FileFilter(settings)
    scanner = SecretScanner()
    # Even if the filter somehow passed it, the scanner excludes by name first.
    assert scanner.verdict_for_filename(".env") is not None
    assert file_filter.decide(".env", 10, b"").status == "included"  # filter is content-agnostic; scanner owns secrets
