"""Markdown chunking by headings (PRD FR-11); oversized sections split at
line boundaries. Never claims AST chunking for Markdown."""

from __future__ import annotations

from app.core.config import Settings
from app.domain.enums import ChunkType, ChunkingMethod
from app.domain.models import CodeChunk
from app.domain.policies import estimate_tokens
from app.ingestion.chunkers.base import build_chunk, split_bounded_lines
from app.ingestion.parsers.base import MarkdownSection
from app.ingestion.parsers.markdown_parser import parse_markdown


class HeadingChunker:
    def __init__(self, settings: Settings) -> None:
        self._max_tokens = settings.chunk_token_limit

    def chunk_markdown(
        self,
        source: str,
        path: str,
        *,
        repository_id: str,
        index_version: str,
    ) -> list[CodeChunk]:
        lines = source.splitlines()
        sections: list[MarkdownSection] = parse_markdown(source, path)
        chunks: list[CodeChunk] = []

        if not sections:
            chunks.extend(self._line_chunks(source, path, repository_id, index_version, start=1))
            return chunks

        for section in sections:
            text = "\n".join(lines[section.start_line - 1 : section.end_line])
            if estimate_tokens(text) <= self._max_tokens:
                chunks.append(self._chunk(text, section.start_line, section.end_line, path, repository_id, index_version, section))
                continue
            for piece, line_start, line_end in split_bounded_lines(
                text, section.start_line, self._max_tokens
            ):
                chunks.append(self._chunk(piece, line_start, line_end, path, repository_id, index_version, section))
        return chunks

    def _chunk(
        self,
        content: str,
        start_line: int,
        end_line: int,
        path: str,
        repository_id: str,
        index_version: str,
        section: MarkdownSection,
    ) -> CodeChunk:
        return build_chunk(
            repository_id=repository_id,
            index_version=index_version,
            path=path,
            language="markdown",
            chunk_type=ChunkType.HEADING_SECTION,
            chunking_method=ChunkingMethod.MARKDOWN_HEADING,
            start_line=start_line,
            end_line=end_line,
            content=content,
            symbol_name=section.heading or None,
            parent_context=f"#{section.level}",
        )

    def _line_chunks(self, source, path, repository_id, index_version, *, start) -> list[CodeChunk]:
        pieces = split_bounded_lines(source, start, self._max_tokens)
        return [
            build_chunk(
                repository_id=repository_id,
                index_version=index_version,
                path=path,
                language="markdown",
                chunk_type=ChunkType.HEADING_SECTION,
                chunking_method=ChunkingMethod.MARKDOWN_HEADING,
                start_line=line_start,
                end_line=line_end,
                content=piece_text,
                symbol_name=None,
                parent_context=None,
            )
            for piece_text, line_start, line_end in pieces
        ]
