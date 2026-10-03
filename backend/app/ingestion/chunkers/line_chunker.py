"""Bounded line-based fallback chunking (PRD FR-10/FR-11).

Used for unparseable files and for YAML/JSON/TOML/requirements/plain text.
Line numbers are always preserved; the strategy is recorded in metadata and
is never presented as AST chunking."""

from __future__ import annotations

from app.core.config import Settings
from app.domain.enums import ChunkingMethod, ChunkType
from app.domain.models import CodeChunk
from app.ingestion.chunkers.base import build_chunk, split_bounded_lines


class LineChunker:
    def __init__(self, settings: Settings) -> None:
        self._max_tokens = settings.chunk_token_limit

    def chunk_lines(
        self,
        source: str,
        path: str,
        language: str,
        *,
        repository_id: str,
        index_version: str,
    ) -> list[CodeChunk]:
        pieces = split_bounded_lines(source, 1, self._max_tokens)
        return [
            build_chunk(
                repository_id=repository_id,
                index_version=index_version,
                path=path,
                language=language,
                chunk_type=ChunkType.LINES,
                chunking_method=ChunkingMethod.LINE_BASED,
                start_line=line_start,
                end_line=line_end,
                content=piece_text,
                symbol_name=None,
                parent_context=None,
            )
            for piece_text, line_start, line_end in pieces
        ]
