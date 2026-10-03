"""Python AST chunking (PRD FR-09, §9.2).

Chunks functions/async functions/classes at symbol boundaries; oversized
classes produce method child-chunks plus a smaller class-summary chunk;
oversized functions split at line boundaries. Nothing is silently truncated,
and files with no definitions fall back to bounded line chunks.
"""

from __future__ import annotations

from app.core.config import Settings
from app.domain.enums import ChunkingMethod, ChunkType
from app.domain.models import CodeChunk
from app.domain.policies import estimate_tokens
from app.ingestion.chunkers.base import build_chunk, split_bounded_lines
from app.ingestion.parsers.base import ParsedFile


class AstChunker:
    def __init__(self, settings: Settings) -> None:
        self._max_tokens = settings.chunk_token_limit

    def chunk_python(
        self,
        parsed: ParsedFile,
        source: str,
        *,
        repository_id: str,
        index_version: str,
    ) -> list[CodeChunk]:
        lines = source.splitlines()
        chunks: list[CodeChunk] = []

        if parsed.parse_error is not None:
            # Unparseable file: the pipeline falls back to line chunking; the
            # AST chunker produces nothing so spans are never fabricated.
            return []

        top_level = [symbol for symbol in parsed.symbols if symbol.parent is None]
        methods_by_class = {
            symbol.name: [
                child for child in parsed.symbols if child.parent == symbol.name
            ]
            for symbol in top_level
            if symbol.kind == "class"
        }

        for symbol in top_level:
            text = self._span(lines, symbol.start_line, symbol.end_line)
            if symbol.kind == "class":
                chunks.extend(
                    self._chunk_class(
                        symbol,
                        text,
                        methods_by_class.get(symbol.name, []),
                        lines,
                        parsed,
                        repository_id=repository_id,
                        index_version=index_version,
                    )
                )
            else:
                chunks.extend(
                    self._chunk_function(
                        symbol,
                        text,
                        parsed,
                        repository_id=repository_id,
                        index_version=index_version,
                    )
                )

        if not chunks:
            # Files with no function/class definitions: bounded line chunks so
            # module-level code stays queryable (§9.2 edge case).
            chunks.extend(
                self._bounded_pieces(
                    source if lines else "",
                    parsed,
                    symbol_name=None,
                    parent_context=None,
                    chunk_type=ChunkType.MODULE_CONTEXT,
                    repository_id=repository_id,
                    index_version=index_version,
                    start_offset=1,
                )
            )
        return chunks

    # -- internals ----------------------------------------------------------

    def _span(self, lines: list[str], start: int, end: int) -> str:
        return "\n".join(lines[start - 1 : end])

    def _chunk_function(
        self,
        symbol,
        text: str,
        parsed: ParsedFile,
        *,
        repository_id: str,
        index_version: str,
    ):
        chunk_type = (
            ChunkType.ASYNC_FUNCTION if symbol.kind == "async_function" else ChunkType.FUNCTION
        )
        if estimate_tokens(text) <= self._max_tokens:
            return [
                build_chunk(
                    repository_id=repository_id,
                    index_version=index_version,
                    path=parsed.path,
                    language=parsed.language,
                    chunk_type=chunk_type,
                    chunking_method=ChunkingMethod.PYTHON_AST,
                    start_line=symbol.start_line,
                    end_line=symbol.end_line,
                    content=text,
                    symbol_name=symbol.name,
                    parent_context=symbol.parent,
                )
            ]
        return self._bounded_pieces(
            text,
            parsed,
            symbol_name=symbol.name,
            parent_context=symbol.parent or symbol.name,
            chunk_type=chunk_type,
            repository_id=repository_id,
            index_version=index_version,
            start_offset=symbol.start_line,
        )

    def _chunk_class(
        self,
        symbol,
        text: str,
        methods: list,
        lines: list[str],
        parsed: ParsedFile,
        *,
        repository_id: str,
        index_version: str,
    ):
        chunks: list[CodeChunk] = []
        class_fits = estimate_tokens(text) <= self._max_tokens

        if class_fits or not methods:
            if class_fits:
                chunks.append(
                    build_chunk(
                        repository_id=repository_id,
                        index_version=index_version,
                        path=parsed.path,
                        language=parsed.language,
                        chunk_type=ChunkType.CLASS,
                        chunking_method=ChunkingMethod.PYTHON_AST,
                        start_line=symbol.start_line,
                        end_line=symbol.end_line,
                        content=text,
                        symbol_name=symbol.name,
                        parent_context=symbol.parent,
                    )
                )
            else:
                # Oversized class with no method structure to split on:
                # bounded pieces, never silent truncation (§9.2).
                chunks.extend(
                    self._bounded_pieces(
                        text,
                        parsed,
                        symbol_name=symbol.name,
                        parent_context=symbol.parent,
                        chunk_type=ChunkType.CLASS,
                        repository_id=repository_id,
                        index_version=index_version,
                        start_offset=symbol.start_line,
                    )
                )
            return chunks

        # Oversized class WITH methods: summary chunk + method children.
        summary_end = methods[0].start_line - 1 if methods else symbol.end_line
        summary_text = self._span(lines, symbol.start_line, max(summary_end, symbol.start_line))
        chunks.append(
            build_chunk(
                repository_id=repository_id,
                index_version=index_version,
                path=parsed.path,
                language=parsed.language,
                chunk_type=ChunkType.CLASS_SUMMARY,
                chunking_method=ChunkingMethod.PYTHON_AST,
                start_line=symbol.start_line,
                end_line=max(summary_end, symbol.start_line),
                content=summary_text,
                symbol_name=symbol.name,
                parent_context=symbol.parent,
            )
        )
        for method in methods:
            method_text = self._span(lines, method.start_line, method.end_line)
            chunks.extend(
                self._chunk_function(
                    method,
                    method_text,
                    parsed,
                    repository_id=repository_id,
                    index_version=index_version,
                )
            )
        return chunks

    def _bounded_pieces(
        self,
        text: str,
        parsed: ParsedFile,
        *,
        symbol_name: str | None,
        parent_context: str | None,
        chunk_type: ChunkType,
        repository_id: str,
        index_version: str,
        start_offset: int,
    ) -> list[CodeChunk]:
        pieces = split_bounded_lines(text, start_offset, self._max_tokens)
        return [
            build_chunk(
                repository_id=repository_id,
                index_version=index_version,
                path=parsed.path,
                language=parsed.language,
                chunk_type=chunk_type,
                chunking_method=ChunkingMethod.PYTHON_AST,
                start_line=line_start,
                end_line=line_end,
                content=piece_text,
                symbol_name=symbol_name,
                parent_context=parent_context,
            )
            for piece_text, line_start, line_end in pieces
        ]
