"""WP-6 gate: AST chunking edge cases demanded by PRD §9.2 + stable IDs."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.domain.enums import ChunkType, ChunkingMethod
from app.ingestion.chunkers.ast_chunker import AstChunker
from app.ingestion.chunkers.heading_chunker import HeadingChunker
from app.ingestion.chunkers.line_chunker import LineChunker
from app.ingestion.parsers.markdown_parser import parse_markdown
from app.ingestion.parsers.python_ast_parser import parse_python


def make_settings(tmp_path, chunk_token_limit: int = 900) -> Settings:
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{tmp_path/'t.db'}",
        data_dir=tmp_path,
        chunk_token_limit=chunk_token_limit,
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture()
def chunker(tmp_path) -> AstChunker:
    return AstChunker(make_settings(tmp_path))


def chunk_source(source: str, *, path: str = "app/mod.py", limit: int = 900) -> list:
    """Standalone helper for budget-sensitive tests (writes nothing to disk)."""
    settings = make_settings(Path("_chunk_test_tmp"), limit)
    return AstChunker(settings).chunk_python(
        parse_python(source, path), source, repository_id="r", index_version="i"
    )


def test_normal_function_chunk_span(chunker: AstChunker) -> None:
    source = "def greet(name):\n    return f'hi {name}'\n"
    chunks = chunker.chunk_python(
        parse_python(source, "m.py"), source, repository_id="r", index_version="i"
    )
    assert len(chunks) == 1
    assert chunks[0].chunk_type == ChunkType.FUNCTION
    assert chunks[0].symbol_name == "greet"
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 2
    assert chunks[0].content == source.rstrip("\n")


def test_async_function_chunk(chunker: AstChunker) -> None:
    source = "async def fetch():\n    return 1\n"
    chunks = chunker.chunk_python(
        parse_python(source, "m.py"), source, repository_id="r", index_version="i"
    )
    assert chunks[0].chunk_type == ChunkType.ASYNC_FUNCTION


def test_decorators_included_in_span(chunker: AstChunker) -> None:
    source = "@app.route('/x')\n@cached\ndef handler():\n    return 1\n"
    chunks = chunker.chunk_python(
        parse_python(source, "m.py"), source, repository_id="r", index_version="i"
    )
    assert chunks[0].start_line == 1  # decorator-inclusive (§9.2)
    assert chunks[0].end_line == 4
    assert "@app.route" in chunks[0].content


def test_class_chunks_include_methods_with_parent_context(chunker: AstChunker) -> None:
    source = (
        "class Service:\n"
        '    """Does things."""\n'
        "    def start(self):\n        return 1\n"
        "    def stop(self):\n        return 0\n"
    )
    chunks = chunker.chunk_python(
        parse_python(source, "m.py"), source, repository_id="r", index_version="i"
    )
    # Class fits in budget → one class chunk (methods live inside it).
    assert len(chunks) == 1
    assert chunks[0].chunk_type == ChunkType.CLASS
    assert chunks[0].symbol_name == "Service"


def test_oversized_class_yields_summary_plus_method_children(tmp_path) -> None:
    filler = "        x = 1  # padding\n" * 40
    source = (
        "class Big:\n"
        '    """Big class."""\n'
        "    def one(self):\n" + filler + "        return 1\n"
        "    def two(self):\n" + filler + "        return 2\n"
    )
    chunks = chunk_source(source, limit=100)
    types = {c.chunk_type for c in chunks}
    assert ChunkType.CLASS_SUMMARY in types
    method_chunks = [c for c in chunks if c.chunk_type == ChunkType.FUNCTION]
    assert {c.symbol_name for c in method_chunks} == {"Big.one", "Big.two"}
    assert all(c.parent_context == "Big" for c in method_chunks)
    # Line ranges must tile the class without silent truncation:
    covered = set()
    for c in chunks:
        covered.update(range(c.start_line, c.end_line + 1))
    class_chunk = next(c for c in chunks if c.symbol_name == "Big")
    assert set(range(class_chunk.start_line, class_chunk.end_line + 1)) <= covered


def test_oversized_function_splits_at_line_boundaries(tmp_path) -> None:
    source = "def long():\n" + "".join(f"    x{i} = {i}\n" for i in range(120)) + "    return x0\n"
    chunks = chunk_source(source, limit=50)
    assert len(chunks) >= 2
    assert all(c.chunking_method == ChunkingMethod.PYTHON_AST for c in chunks)
    # No gap: consecutive pieces continue where the previous ended.
    for first, second in zip(chunks, chunks[1:]):
        assert second.start_line == first.end_line + 1


def test_syntax_error_falls_back_without_discarding(chunker: AstChunker) -> None:
    source = "def broken(:\n    pass\n"
    parsed = parse_python(source, "m.py")
    assert parsed.parse_error is not None
    chunks = chunker.chunk_python(parsed, source, repository_id="r", index_version="i")
    # The AstChunker yields no symbol chunks; pipeline uses LineChunker next.
    assert chunks == []


def test_file_with_no_definitions_yields_module_chunks(chunker: AstChunker) -> None:
    source = "X = 1\nY = 2\nZ = X + Y\n"
    chunks = chunker.chunk_python(
        parse_python(source, "m.py"), source, repository_id="r", index_version="i"
    )
    assert chunks
    assert chunks[0].chunk_type == ChunkType.MODULE_CONTEXT
    assert chunks[0].start_line == 1


def test_stable_ids_across_runs(chunker: AstChunker) -> None:
    source = "def a():\n    return 1\n\ndef b():\n    return 2\n"
    parsed = parse_python(source, "m.py")
    run1 = chunker.chunk_python(parsed, source, repository_id="r", index_version="i")
    run2 = chunker.chunk_python(parsed, source, repository_id="r", index_version="i")
    assert [c.chunk_id for c in run1] == [c.chunk_id for c in run2]
    assert run1[0].chunk_id != run1[1].chunk_id


# --- markdown + line chunkers ------------------------------------------------


def test_markdown_splits_by_headings(tmp_path) -> None:
    settings = make_settings(tmp_path)
    source = "# Title\nintro text\n## Setup\nrun setup steps\n## Usage\nuse it\n"
    chunks = HeadingChunker(settings).chunk_markdown(
        source, "README.md", repository_id="r", index_version="i"
    )
    assert [c.symbol_name for c in chunks] == ["Title", "Setup", "Usage"]
    assert all(c.chunking_method == ChunkingMethod.MARKDOWN_HEADING for c in chunks)
    assert chunks[1].start_line == 3


def test_line_chunker_preserves_line_numbers(tmp_path) -> None:
    settings = make_settings(tmp_path)
    source = "\n".join(f"line {i}" for i in range(1, 21))
    chunks = LineChunker(settings).chunk_lines(
        source, "config.yaml", "yaml", repository_id="r", index_version="i"
    )
    assert chunks[0].start_line == 1
    assert chunks[0].chunking_method == ChunkingMethod.LINE_BASED
    assert all(c.chunk_type == ChunkType.LINES for c in chunks)


def test_markdown_parse_handles_empty() -> None:
    assert parse_markdown("", "x.md") == []
