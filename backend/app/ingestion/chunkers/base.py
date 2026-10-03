"""Chunk assembly primitives shared by all chunkers: bounded line splitting,
content hashes, and stable deterministic IDs (PRD FR-12/FR-13, §9.2)."""

from __future__ import annotations

from app.core.ids import content_hash, stable_chunk_id
from app.domain.enums import ChunkType, ChunkingMethod
from app.domain.models import CodeChunk
from app.domain.policies import estimate_tokens


def split_bounded_lines(
    text: str, start_line: int, max_tokens: int
) -> list[tuple[str, int, int]]:
    """Split *text* at safe line boundaries so every piece fits the budget.
    Never drops lines; preserves absolute line numbers (PRD FR-10)."""
    lines = text.splitlines() or [""]
    pieces: list[tuple[str, int, int]] = []
    current: list[str] = []
    current_start = start_line

    def flush(end_line: int) -> None:
        if current:
            pieces.append(("\n".join(current), current_start, end_line))
            current.clear()

    for offset, line in enumerate(lines):
        candidate = current + [line]
        if estimate_tokens("\n".join(candidate)) > max_tokens and current:
            flush(start_line + offset - 1)
            current_start = start_line + offset
        current.append(line)
    flush(start_line + len(lines) - 1)
    return pieces


def build_chunk(
    *,
    repository_id: str,
    index_version: str,
    path: str,
    language: str,
    chunk_type: ChunkType,
    chunking_method: ChunkingMethod,
    start_line: int,
    end_line: int,
    content: str,
    symbol_name: str | None = None,
    parent_context: str | None = None,
) -> CodeChunk:
    digest = content_hash(content)
    return CodeChunk(
        chunk_id=stable_chunk_id(
            repository_id=repository_id,
            path=path,
            start_line=start_line,
            end_line=end_line,
            content_hash_value=digest,
        ),
        repository_id=repository_id,
        index_version=index_version,
        path=path,
        language=language,
        chunk_type=chunk_type,
        chunking_method=chunking_method,
        start_line=start_line,
        end_line=end_line,
        symbol_name=symbol_name,
        parent_context=parent_context,
        content=content,
        content_hash=digest,
    )
