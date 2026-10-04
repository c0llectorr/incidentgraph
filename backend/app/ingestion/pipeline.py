"""The 11-stage ingestion pipeline (PRD §9.1).

Runs in a background thread. Publishes honest progress events, persists a
repository index, and only marks it ready after the verify stage confirms
chunks and vectors are queryable (§9.1 step 11, §6.2).
"""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

from app.core.config import Settings
from app.core.errors import (
    IncidentGraphError,
    IndexNotReadyError,
    InvalidSourceError,
    LimitExceededError,
    ProviderError,
)
from app.core.ids import new_index_version
from app.core.logging import get_logger
from app.domain.enums import (
    IndexStatus,
    IngestionStage,
    JobStatus,
)
from app.domain.interfaces import NormalizedGitHubSource
from app.domain.models import CodeChunk
from app.embeddings.batching import embed_in_batches
from app.ingestion.archive_extractor import ArchiveExtractor
from app.ingestion.chunkers.ast_chunker import AstChunker
from app.ingestion.chunkers.heading_chunker import HeadingChunker
from app.ingestion.chunkers.line_chunker import LineChunker
from app.ingestion.file_discovery import DiscoveredFile, discover_files
from app.ingestion.file_filter import FileFilter
from app.ingestion.github_client import GitHubRepositoryClient
from app.ingestion.parsers.base import detect_language
from app.ingestion.parsers.python_ast_parser import parse_python
from app.ingestion.progress import ProgressTracker
from app.ingestion.secret_scanner import SecretScanner
from app.jobs.events import JobEvent
from app.persistence.models import (
    CodeChunkRow,
    FileRecordRow,
    RepositoryRow,
)
from app.persistence.repositories import (
    ChunkRepository,
    FileRecordRepository,
    JobRepository,
    RepositoryRepository,
)
from app.persistence.unit_of_work import UnitOfWork

logger = get_logger(__name__)

_STAGE_MESSAGES = {
    IngestionStage.VALIDATING_SOURCE: "Validating repository source…",
    IngestionStage.FETCHING_REPOSITORY: "Fetching repository files…",
    IngestionStage.EXTRACTING_FILES: "Extracting archive members…",
    IngestionStage.FILTERING_FILES: "Filtering generated files and sensitive content…",
    IngestionStage.PARSING_AND_CHUNKING: "Parsing Python syntax trees and preserving code boundaries…",
    IngestionStage.EMBEDDING: "Creating embeddings in batches…",
    IngestionStage.PERSISTING_INDEX: "Persisting the searchable index…",
    IngestionStage.VERIFYING_INDEX: "Checking index integrity…",
}

_TEXT_ENCODING = "utf-8"


@dataclass
class PreparedFile:
    relative_path: str
    language: str
    text: str


@dataclass
class PipelineOutcome:
    repository_id: str
    index_version: str
    status: str  # JobStatus value
    file_count: int = 0
    chunk_count: int = 0
    error_code: str | None = None


class IngestionPipeline:
    def __init__(
        self,
        settings: Settings,
        uow: UnitOfWork,
        github_client: GitHubRepositoryClient,
        archive_extractor: ArchiveExtractor,
        file_filter: FileFilter,
        secret_scanner: SecretScanner,
        ast_chunker: AstChunker,
        heading_chunker: HeadingChunker,
        line_chunker: LineChunker,
        embedder,
        vector_store,
        publish: Callable[[JobEvent], None],
    ) -> None:
        self._settings = settings
        self._uow = uow
        self._github = github_client
        self._extractor = archive_extractor
        self._filter = file_filter
        self._scanner = secret_scanner
        self._ast_chunker = ast_chunker
        self._heading_chunker = heading_chunker
        self._line_chunker = line_chunker
        self._embedder = embedder
        self._vector_store = vector_store
        self._publish = publish
        # Console progress bars (developer-facing, tqdm on stderr). The
        # pipeline instance is per-job, so bars never collide across jobs.
        self._bars: dict[str, tqdm] = {}

    # -- event plumbing -------------------------------------------------------

    def _emit(
        self,
        job_id: str,
        progress: ProgressTracker,
        stage: IngestionStage,
        status: str,
        *,
        message: str = "",
        error_code: str | None = None,
    ) -> None:
        percent, indeterminate = progress.snapshot()
        stage_progress = progress.stage_state(stage)
        overall_bar = self._bars.get("overall")
        if overall_bar is not None and percent is not None:
            overall_bar.n = min(percent, 100.0)
            overall_bar.refresh()
        self._publish(
            JobEvent(
                job_id=job_id,
                stage=stage.value,
                status=status,
                completed_units=stage_progress.completed if stage_progress else 0,
                total_units=stage_progress.total if stage_progress else None,
                # Indeterminate stages never carry an invented percentage (§12.6).
                percent=None if indeterminate else percent,
                indeterminate=indeterminate and status == "running",
                message=message or _STAGE_MESSAGES.get(stage, stage.value.replace("_", " ")),
                updated_at=JobEvent.now_iso(),
                error_code=error_code,
            )
        )

    def _update_job_row(self, job_id: str, **fields) -> None:
        with self._uow.begin() as session:
            row = JobRepository().get(session, job_id)
            if row is None:
                return
            for key, value in fields.items():
                setattr(row, key, value)

    def _update_repository_row(self, repository_id: str, **fields) -> None:
        with self._uow.begin() as session:
            RepositoryRepository().update_index_state(session, repository_id, **fields)

    # -- entry point ----------------------------------------------------------

    def execute(
        self,
        *,
        job_id: str,
        repository: RepositoryRow,
    ) -> PipelineOutcome:
        repository_id = repository.id
        progress = ProgressTracker()
        index_version = new_index_version()
        workspace = self._settings.tmp_dir / job_id
        resolved_sha = repository.commit_sha

        # Developer-facing console bars (PRD goal: honest, detailed ingestion
        # progress). Overall 0-100 bar mirrors the SSE percentages.
        self._bars["overall"] = tqdm(
            total=100, desc="ingestion", unit="%", position=0, ncols=100, leave=True
        )

        try:
            self._update_repository_row(repository_id, status=IndexStatus.INDEXING.value)
            self._update_job_row(job_id, status=JobStatus.RUNNING.value)

            # 1. Validate source -------------------------------------------------
            progress.start_stage(IngestionStage.VALIDATING_SOURCE, total=1)
            self._emit(job_id, progress, IngestionStage.VALIDATING_SOURCE, "running")
            archive_bytes = self._load_source(repository)
            progress.complete_stage(IngestionStage.VALIDATING_SOURCE)
            self._emit(job_id, progress, IngestionStage.VALIDATING_SOURCE, "completed")

            # 2. Fetch (GitHub only) ----------------------------------------------
            if repository.source_type == "github":
                progress.start_stage(IngestionStage.FETCHING_REPOSITORY, total=1)
                self._emit(job_id, progress, IngestionStage.FETCHING_REPOSITORY, "running")
                source = self._source_from_reference(repository)
                metadata = self._github.resolve_metadata(source)
                resolved_sha = metadata.commit_sha
                archive_bytes = self._github.fetch_archive(source, commit_sha=resolved_sha)
                progress.complete_stage(IngestionStage.FETCHING_REPOSITORY)
                self._emit(job_id, progress, IngestionStage.FETCHING_REPOSITORY, "completed")

            # 3. Extract ------------------------------------------------------------
            progress.start_stage(IngestionStage.EXTRACTING_FILES, total=None)
            self._emit(job_id, progress, IngestionStage.EXTRACTING_FILES, "running")
            report = self._extractor.extract_zip_bytes(archive_bytes, workspace)
            progress.start_stage(IngestionStage.EXTRACTING_FILES, total=len(report.relative_paths))
            progress.complete_stage(IngestionStage.EXTRACTING_FILES)
            self._emit(job_id, progress, IngestionStage.EXTRACTING_FILES, "completed")

            # 4. Discover --------------------------------------------------------------
            files = discover_files(workspace)
            if len(files) > self._settings.max_repository_files:
                raise LimitExceededError(
                    f"Repository exceeds the configured file limit of "
                    f"{self._settings.max_repository_files}."
                )

            # 5. Filter (+ secret scan) --------------------------------------------------
            progress.start_stage(IngestionStage.FILTERING_FILES, total=len(files))
            self._emit(job_id, progress, IngestionStage.FILTERING_FILES, "running")
            included, excluded = self._filter_and_scan(files)
            progress.complete_stage(IngestionStage.FILTERING_FILES)
            self._emit(job_id, progress, IngestionStage.FILTERING_FILES, "completed")

            # 6. Parse & chunk --------------------------------------------------------------
            progress.start_stage(IngestionStage.PARSING_AND_CHUNKING, total=len(included) or 1)
            self._emit(job_id, progress, IngestionStage.PARSING_AND_CHUNKING, "running")
            self._bars["chunk"] = tqdm(
                total=len(included) or 1, desc="chunking", position=1, unit="file", ncols=100, leave=True
            )
            chunks, parse_statuses = self._parse_and_chunk(
                included, repository_id=repository_id, index_version=index_version
            )
            for _ in included:
                progress.advance(IngestionStage.PARSING_AND_CHUNKING)
            progress.complete_stage(IngestionStage.PARSING_AND_CHUNKING)
            self._emit(job_id, progress, IngestionStage.PARSING_AND_CHUNKING, "completed")

            # 7. Deduplicate (within this index version) --------------------------------------
            unique_texts: dict[str, str] = {}
            for chunk in chunks:
                unique_texts.setdefault(chunk.content_hash, chunk.content)

            # 8. Embed — reusing stored vectors for unchanged chunks (FR-13) ---------------
            progress.start_stage(IngestionStage.EMBEDDING, total=len(unique_texts) or 1)
            self._emit(job_id, progress, IngestionStage.EMBEDDING, "running")

            vectors_by_hash: dict[str, list[float]] = {}
            if chunks:
                existing_vectors = self._vector_store.get_vectors(
                    [chunk.chunk_id for chunk in chunks]
                )
                for chunk in chunks:
                    vector = existing_vectors.get(chunk.chunk_id)
                    if vector is not None:
                        vectors_by_hash.setdefault(chunk.content_hash, vector)

            missing_texts = [
                (content_hash, text)
                for content_hash, text in unique_texts.items()
                if content_hash not in vectors_by_hash
            ]

            def _on_batch_done(units: int) -> None:
                nonlocal batches_done
                batches_done += 1
                progress.advance(IngestionStage.EMBEDDING, units)
                self._emit(job_id, progress, IngestionStage.EMBEDDING, "running")
                stage_elapsed = time.monotonic() - embed_stage_started
                embed_bar = self._bars.get("embed")
                if embed_bar is not None:
                    embed_bar.set_postfix(batch=f"{batches_done}/{total_batches}", elapsed=f"{stage_elapsed:.0f}s")
                logger.info(
                    "Embedded batch %d/%d for %s (%d units, %.1fs into the embed stage)",
                    batches_done,
                    total_batches,
                    repository_id,
                    units,
                    stage_elapsed,
                )

            total_batches = (
                -(-len(missing_texts) // self._settings.embedding_batch_size)
                if missing_texts
                else 0
            )
            embed_stage_started = time.monotonic()
            batches_done = 0
            self._bars["embed"] = tqdm(
                total=len(missing_texts) or 1,
                desc="embedding",
                position=2,
                unit="chunk",
                ncols=100,
                leave=True,
            )
            logger.info(
                "Embedding %d unique chunks in %d batches (batch_size=%d) for %s "
                "(first call may load the local model)",
                len(missing_texts),
                total_batches,
                self._settings.embedding_batch_size,
                repository_id,
            )

            if missing_texts:
                batch_result = embed_in_batches(
                    self._embedder,
                    [text for _, text in missing_texts],
                    batch_size=self._settings.embedding_batch_size,
                    max_retries=self._settings.embedding_max_retries,
                    on_batch_done=_on_batch_done,
                )
                if not batch_result.ok:
                    raise ProviderError(
                        f"Embedding failed for {len(batch_result.failures)} batch(es); "
                        "the index was not completed."
                    )
                for (content_hash, _text), vector in zip(missing_texts, batch_result.vectors, strict=False):
                    vectors_by_hash[content_hash] = vector  # type: ignore[assignment]
                progress.advance(
                    IngestionStage.EMBEDDING,
                    max(0, len(missing_texts) - (len(missing_texts) % self._settings.embedding_batch_size)),
                )
            progress.complete_stage(IngestionStage.EMBEDDING)
            self._emit(job_id, progress, IngestionStage.EMBEDDING, "completed")

            # 9. Persist ----------------------------------------------------------------------------
            progress.start_stage(IngestionStage.PERSISTING_INDEX, total=len(chunks) or 1)
            self._emit(job_id, progress, IngestionStage.PERSISTING_INDEX, "running")
            self._persist(
                repository_id=repository_id,
                index_version=index_version,
                files=files,
                excluded=excluded,
                parse_statuses=parse_statuses,
                chunks=chunks,
                vectors_by_hash=vectors_by_hash,
            )
            progress.complete_stage(IngestionStage.PERSISTING_INDEX)
            self._emit(job_id, progress, IngestionStage.PERSISTING_INDEX, "completed")

            # 10. Verify -------------------------------------------------------------------------------
            progress.start_stage(IngestionStage.VERIFYING_INDEX, total=1)
            self._emit(job_id, progress, IngestionStage.VERIFYING_INDEX, "running")
            self._verify(repository_id, index_version, chunks)
            progress.complete_stage(IngestionStage.VERIFYING_INDEX)

            # Ready only after verify passes (§9.1 step 11).
            self._update_repository_row(
                repository_id,
                status=IndexStatus.READY.value,
                index_version=index_version,
                file_count=len(files),
                commit_sha=resolved_sha,
            )
            self._update_job_row(
                job_id,
                status=JobStatus.SUCCEEDED.value,
                stage=IngestionStage.READY.value,
                percent=100.0,
                message="Repository ready for questions.",
            )
            self._publish(
                JobEvent(
                    job_id=job_id,
                    stage=IngestionStage.READY.value,
                    status=JobStatus.SUCCEEDED.value,
                    completed_units=1,
                    total_units=1,
                    percent=100.0,
                    indeterminate=False,
                    message="Repository ready for questions.",
                    updated_at=JobEvent.now_iso(),
                )
            )
            return PipelineOutcome(
                repository_id=repository_id,
                index_version=index_version,
                status=JobStatus.SUCCEEDED.value,
                file_count=len(files),
                chunk_count=len(chunks),
            )

        except IncidentGraphError as exc:
            logger.warning("Ingestion failed for %s: %s", repository_id, exc.code)
            self._update_repository_row(repository_id, status=IndexStatus.FAILED.value)
            self._update_job_row(
                job_id,
                status=JobStatus.FAILED.value,
                error_code=exc.code,
                message=exc.message,
            )
            percent, _ = progress.snapshot()
            self._publish(
                JobEvent(
                    job_id=job_id,
                    stage=progress.current_stage.value if progress.current_stage else "unknown",
                    status=JobStatus.FAILED.value,
                    completed_units=0,
                    total_units=None,
                    percent=percent,
                    indeterminate=False,
                    message=exc.message,
                    updated_at=JobEvent.now_iso(),
                    error_code=exc.code,
                )
            )
            return PipelineOutcome(
                repository_id=repository_id,
                index_version=index_version,
                status=JobStatus.FAILED.value,
                error_code=exc.code,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Ingestion crashed for %s", repository_id)
            self._update_repository_row(repository_id, status=IndexStatus.FAILED.value)
            self._update_job_row(
                job_id,
                status=JobStatus.FAILED.value,
                error_code="INTERNAL_ERROR",
                message="Ingestion failed unexpectedly.",
            )
            self._publish(
                JobEvent(
                    job_id=job_id,
                    stage="unknown",
                    status=JobStatus.FAILED.value,
                    completed_units=0,
                    total_units=None,
                    percent=None,
                    indeterminate=False,
                    message="Ingestion failed unexpectedly.",
                    updated_at=JobEvent.now_iso(),
                    error_code="INTERNAL_ERROR",
                )
            )
            return PipelineOutcome(
                repository_id=repository_id,
                index_version=index_version,
                status=JobStatus.FAILED.value,
                error_code="INTERNAL_ERROR",
            )
        finally:
            for bar in self._bars.values():
                bar.close()
            self._bars.clear()
            shutil.rmtree(workspace, ignore_errors=True)

    # -- stage helpers ----------------------------------------------------------

    def _load_source(self, repository: RepositoryRow) -> bytes:
        if repository.source_type == "zip":
            path = Path(repository.source_reference)
            if not path.is_file():
                raise InvalidSourceError("The uploaded archive is no longer available.")
            size = path.stat().st_size
            if size > self._settings.max_total_extracted_bytes:
                raise LimitExceededError(
                    "Archive exceeds the configured size limit of "
                    f"{self._settings.max_total_extracted_bytes} bytes."
                )
            return path.read_bytes()
        if repository.source_type == "github":
            return b""  # fetched in stage 2
        raise InvalidSourceError("Unsupported repository source type.")

    @staticmethod
    def _source_from_reference(repository: RepositoryRow) -> NormalizedGitHubSource:
        parts = [part for part in repository.source_reference.split("/") if part]
        if len(parts) < 2:
            raise InvalidSourceError("The stored repository reference is malformed.")
        return NormalizedGitHubSource(
            owner=parts[-2], repo=parts[-1], branch=repository.branch, commit=repository.commit_sha
        )

    def _filter_and_scan(self, files: list[DiscoveredFile]):
        included: list[PreparedFile] = []
        excluded: list[tuple[str, str]] = []
        for file in files:
            decision = self._filter.decide(file.relative_path, file.size_bytes, self._head(file))
            if decision.status != "included":
                excluded.append((file.relative_path, decision.reason or "excluded"))
                continue
            filename_verdict = self._scanner.verdict_for_filename(file.relative_path)
            if filename_verdict is not None and not filename_verdict.is_included:
                excluded.append((file.relative_path, filename_verdict.reason or "secret filename"))
                continue
            try:
                text = file.absolute_path.read_text(encoding=_TEXT_ENCODING)
            except (UnicodeDecodeError, ValueError):
                excluded.append((file.relative_path, "not decodable as UTF-8 text"))
                continue
            scan = self._scanner.scan_text(text)
            if not scan.is_included:
                excluded.append((file.relative_path, scan.reason or "secret patterns"))
                continue
            included.append(
                PreparedFile(
                    relative_path=file.relative_path,
                    language=detect_language(file.relative_path),
                    text=scan.redacted_text if scan.action == "redact" else text,
                )
            )
        return included, excluded

    @staticmethod
    def _head(file: DiscoveredFile) -> bytes:
        try:
            with file.absolute_path.open("rb") as handle:
                return handle.read(8192)
        except OSError:
            return b""

    def _parse_and_chunk(self, included: list[PreparedFile], *, repository_id: str, index_version: str):
        chunks: list[CodeChunk] = []
        parse_statuses: dict[str, str] = {}
        chunk_bar = self._bars.get("chunk")
        for prepared in included:
            file_started = time.perf_counter()
            if prepared.language == "python":
                parsed = parse_python(prepared.text, prepared.relative_path)
                if parsed.parse_error is None:
                    file_chunks = self._ast_chunker.chunk_python(
                        parsed,
                        prepared.text,
                        repository_id=repository_id,
                        index_version=index_version,
                    )
                    parse_statuses[prepared.relative_path] = "ok"
                else:
                    file_chunks = self._line_chunker.chunk_lines(
                        prepared.text,
                        prepared.relative_path,
                        prepared.language,
                        repository_id=repository_id,
                        index_version=index_version,
                    )
                    parse_statuses[prepared.relative_path] = "failed_fallback"
            elif prepared.language == "markdown":
                file_chunks = self._heading_chunker.chunk_markdown(
                    prepared.text,
                    prepared.relative_path,
                    repository_id=repository_id,
                    index_version=index_version,
                )
                parse_statuses[prepared.relative_path] = "ok"
            else:
                file_chunks = self._line_chunker.chunk_lines(
                    prepared.text,
                    prepared.relative_path,
                    prepared.language,
                    repository_id=repository_id,
                    index_version=index_version,
                )
                parse_statuses[prepared.relative_path] = "plain"
            chunks.extend(file_chunks)
            elapsed_ms = (time.perf_counter() - file_started) * 1000
            logger.info(
                "Chunked %s into %d chunks in %.0f ms (%s)",
                prepared.relative_path,
                len(file_chunks),
                elapsed_ms,
                parse_statuses[prepared.relative_path],
            )
            if chunk_bar is not None:
                chunk_bar.set_description(f"chunking {prepared.relative_path[-52:]}")
                chunk_bar.update(1)
        return chunks, parse_statuses

    def _persist(
        self,
        *,
        repository_id: str,
        index_version: str,
        files: list[DiscoveredFile],
        excluded: list[tuple[str, str]],
        parse_statuses: dict[str, str],
        chunks: list[CodeChunk],
        vectors_by_hash: dict[str, list[float] | None],
    ) -> None:
        excluded_map = dict(excluded)
        file_rows: list[FileRecordRow] = []
        for file in files:
            is_excluded = file.relative_path in excluded_map
            file_rows.append(
                FileRecordRow(
                    repository_id=repository_id,
                    index_version=index_version,
                    relative_path=file.relative_path,
                    language=detect_language(file.relative_path),
                    content_hash="",
                    filter_status="excluded" if is_excluded else "included",
                    filter_reason=excluded_map.get(file.relative_path),
                    parse_status=(
                        "skipped" if is_excluded else parse_statuses.get(file.relative_path, "pending")
                    ),
                )
            )
        chunk_rows = [
            CodeChunkRow(
                chunk_id=chunk.chunk_id,
                repository_id=chunk.repository_id,
                index_version=chunk.index_version,
                path=chunk.path,
                language=chunk.language,
                chunk_type=chunk.chunk_type.value,
                chunking_method=chunk.chunking_method.value,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                symbol_name=chunk.symbol_name,
                parent_context=chunk.parent_context,
                content=chunk.content,
                content_hash=chunk.content_hash,
            )
            for chunk in chunks
        ]
        with self._uow.begin() as session:
            # Re-ingestion replaces the previous index rows (stable chunk IDs
            # mean unchanged content keeps its identity — FR-13).
            ChunkRepository().delete_by_repository(session, repository_id)
            FileRecordRepository().delete_by_repository(session, repository_id)
            FileRecordRepository().add_many(session, file_rows)
            ChunkRepository().add_many(session, chunk_rows)

        vectors = [vectors_by_hash.get(chunk.content_hash) for chunk in chunks]
        if any(vector is None for vector in vectors):
            raise ProviderError("Missing vectors for required chunks.")
        self._vector_store.upsert(
            chunks,
            [vector for vector in vectors if vector is not None],
            dimension=len(vectors[0]) if vectors else self._embedder.dimension,
        )

    def _verify(self, repository_id: str, index_version: str, chunks: list[CodeChunk]) -> None:
        expected = len(chunks)
        actual = self._vector_store.count(repository_id=repository_id, index_version=index_version)
        if actual != expected:
            raise IndexNotReadyError(
                f"Index integrity check failed: expected {expected} vectors, found {actual}."
            )
        if chunks:
            probe_vector = self._embedder.embed_query(chunks[0].content)
            results = self._vector_store.search(
                probe_vector,
                repository_id=repository_id,
                index_version=index_version,
                top_k=1,
            )
            if not results:
                raise IndexNotReadyError(
                    "Index integrity check failed: probe search returned nothing."
                )
