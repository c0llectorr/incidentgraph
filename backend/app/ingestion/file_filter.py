"""Configurable exclusion rules (PRD FR-07). Decisions are pure functions of
(path, size, content head) so they are fully unit-testable."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings

EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "htmlcov",
    ".eggs",
}

EXCLUDED_SUFFIXES = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".bin",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".svgz",
    ".zip", ".gz", ".tgz", ".tar", ".bz2", ".7z", ".rar",
    ".whl", ".egg", ".pdf", ".doc", ".docx", ".woff", ".woff2", ".ttf", ".eot",
    ".db", ".sqlite", ".sqlite3", ".class", ".jar", ".o", ".a", ".obj",
    # Trained-model / tensor artifacts (PRD FR-07: large binaries — never
    # chunked or embedded; they are opaque bytes, not code).
    ".pt", ".pth", ".ckpt", ".onnx", ".h5", ".hdf5", ".keras", ".tflite",
    ".pb", ".safetensors", ".gguf", ".ggml", ".mlmodel", ".engine",
    ".pkl", ".pickle", ".msgpack", ".npz", ".npy", ".parquet", ".arrow",
    ".weights", ".data", ".index", ".graph", ".mlpackage",
}

# Lockfiles excluded "where not useful" (PRD FR-07): dependency-resolution
# noise rather than semantic content.
LOCKFILE_NAMES = {
    "poetry.lock",
    "Pipfile.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "uv.lock",
    "composer.lock",
}

_BINARY_SNIFF_BYTES = 8_192


@dataclass(frozen=True)
class FilterDecision:
    status: str  # "included" | "excluded"
    reason: str | None = None


class FileFilter:
    def __init__(self, settings: Settings, extra_excluded_dirs: set[str] | None = None) -> None:
        self._settings = settings
        self._excluded_dirs = set(EXCLUDED_DIR_NAMES) | (extra_excluded_dirs or set())

    def decide(self, relative_path: str, size_bytes: int, content_head: bytes) -> FilterDecision:
        parts = relative_path.split("/")
        if any(part in self._excluded_dirs for part in parts[:-1]):
            return FilterDecision("excluded", "excluded directory")
        if parts[-1] in LOCKFILE_NAMES:
            return FilterDecision("excluded", "lockfile not useful")
        suffix = ("." + parts[-1].rsplit(".", 1)[-1].lower()) if "." in parts[-1] else ""
        if suffix in EXCLUDED_SUFFIXES:
            return FilterDecision("excluded", "compiled or binary artifact")
        if size_bytes > self._settings.max_file_bytes:
            return FilterDecision("excluded", "file exceeds per-file size limit")
        if b"\x00" in content_head[:_BINARY_SNIFF_BYTES]:
            return FilterDecision("excluded", "binary content")
        return FilterDecision("included")
