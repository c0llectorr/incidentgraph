"""Parser contracts and language detection (PRD §8.2 ingestion/ row)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SymbolDef:
    name: str
    kind: str  # "function" | "async_function" | "class"
    start_line: int  # decorator-inclusive
    end_line: int
    parent: str | None = None
    docstring: str | None = None


@dataclass
class ParsedFile:
    path: str
    language: str
    total_lines: int
    symbols: list[SymbolDef] = field(default_factory=list)
    parse_error: str | None = None


@dataclass(frozen=True)
class MarkdownSection:
    heading: str
    level: int
    start_line: int
    end_line: int


_LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".pyw": "python",
    ".md": "markdown",
    ".markdown": "markdown",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".txt": "text",
    ".cfg": "ini",
    ".ini": "ini",
    ".cfg": "ini",
    ".rst": "text",
}


def detect_language(path: str) -> str:
    suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return _LANGUAGE_BY_SUFFIX.get(f".{suffix}", "text")


def is_supported(path: str) -> bool:
    return detect_language(path) != "text" or path.lower().endswith(
        (".txt", ".rst", ".cfg", ".ini")
    )
