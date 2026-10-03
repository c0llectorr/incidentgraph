"""Provider-independent enums (PRD §8.2 domain/ row)."""

from __future__ import annotations

from enum import StrEnum


class SourceType(StrEnum):
    GITHUB = "github"
    ZIP = "zip"


class IngestionStage(StrEnum):
    """Stages named in FR-45 plus the §9.1 verify gate before `ready`."""

    VALIDATING_SOURCE = "validating_source"
    FETCHING_REPOSITORY = "fetching_repository"
    EXTRACTING_FILES = "extracting_files"
    FILTERING_FILES = "filtering_files"
    PARSING_AND_CHUNKING = "parsing_and_chunking"
    EMBEDDING = "embedding"
    PERSISTING_INDEX = "persisting_index"
    VERIFYING_INDEX = "verifying_index"
    READY = "ready"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChunkType(StrEnum):
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    CLASS = "class"
    CLASS_SUMMARY = "class_summary"
    MODULE_CONTEXT = "module_context"
    HEADING_SECTION = "heading_section"
    LINES = "lines"


class ChunkingMethod(StrEnum):
    PYTHON_AST = "python_ast"
    MARKDOWN_HEADING = "markdown_heading"
    LINE_BASED = "line_based"


class IndexStatus(StrEnum):
    NOT_INDEXED = "not_indexed"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class InvestigationStatus(StrEnum):
    PENDING = "pending"
    AWAITING_EVIDENCE = "awaiting_evidence"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvidenceType(StrEnum):
    LOG = "log"
    TRACEBACK = "traceback"
    DIFF = "diff"
    NOTE = "note"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatStatus(StrEnum):
    OK = "ok"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ERROR = "error"
