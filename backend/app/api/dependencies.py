"""Composition root: builds the service container from Settings.

Domain and service layers never import this module — it exists so the API
layer can wire concrete adapters behind the domain interfaces (PRD §7.4).
Tests override parts of the container with deterministic fakes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.core.config import Settings, get_settings
from app.ingestion.archive_extractor import ArchiveExtractor
from app.ingestion.chunkers.ast_chunker import AstChunker
from app.ingestion.chunkers.heading_chunker import HeadingChunker
from app.ingestion.chunkers.line_chunker import LineChunker
from app.ingestion.file_filter import FileFilter
from app.ingestion.github_client import GitHubRepositoryClient
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.secret_scanner import SecretScanner
from app.jobs.manager import JobManager
from app.persistence.database import create_engine_from_settings, create_session_factory
from app.persistence.repositories import (
    ChunkRepository,
    FileRecordRepository,
    IncidentRepository,
    JobRepository,
    MessageRepository,
    RepositoryRepository,
)
from app.persistence.unit_of_work import UnitOfWork
from app.services.ingestion_service import IngestionService
from app.services.repository_service import RepositoryService

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import sessionmaker


@dataclass
class AppContainer:
    """Holds every concrete adapter/service instance for one app instance."""

    settings: Settings
    engine: Engine | None = None
    session_factory: sessionmaker | None = None  # type: ignore[type-arg]
    uow: UnitOfWork | None = None
    job_manager: JobManager | None = None
    repository_service: RepositoryService | None = None
    ingestion_service: IngestionService | None = None
    _rag: object | None = field(default=None, repr=False)
    _chat_override: object | None = field(default=None, repr=False)
    _embedder_override: object | None = field(default=None, repr=False)
    _vector_store_override: object | None = field(default=None, repr=False)
    # Wired in WP-11..13: incident_service, investigation graph.
    _extras: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.settings.ensure_dirs()
        if self.engine is None:
            self.engine = create_engine_from_settings(self.settings)
            self.session_factory = create_session_factory(self.engine)
            self.uow = UnitOfWork(self.session_factory)
        if self.job_manager is None:
            self.job_manager = JobManager()
        if self.repository_service is None:
            self.repository_service = RepositoryService(self.settings, self.uow)  # type: ignore[arg-type]
        if self.ingestion_service is None:
            self.ingestion_service = IngestionService(
                self.settings,
                self.uow,  # type: ignore[arg-type]
                pipeline_factory=self._build_pipeline,
                job_manager=self.job_manager,
            )
        if "incident_service" not in self._extras:
            from app.services.incident_service import IncidentService

            self._extras["incident_service"] = IncidentService(self.settings, self.uow)  # type: ignore[arg-type]
        if "signal_extractor" not in self._extras:
            from app.services.signal_extractor import IncidentSignalExtractor

            self._extras["signal_extractor"] = IncidentSignalExtractor()
        # Deletion needs the vector store, but lazily (test overrides).
        assert self.repository_service is not None
        self.repository_service.vector_store_provider = self.build_vector_store

    # -- adapter construction (overridable piece by piece in tests) ----------

    def build_github_client(self) -> GitHubRepositoryClient:
        return GitHubRepositoryClient(self.settings)

    def build_chat_model(self):
        if self._chat_override is not None:
            return self._chat_override
        from app.llm.groq_provider import GroqChatProvider

        return GroqChatProvider(self.settings)

    def build_embedder(self):
        if self._embedder_override is not None:
            return self._embedder_override
        from app.embeddings.qwen_provider import QwenEmbeddingProvider

        return QwenEmbeddingProvider(self.settings)

    def build_vector_store(self):
        if self._vector_store_override is not None:
            return self._vector_store_override
        from app.vectorstore.chroma_store import ChromaVectorStore

        return ChromaVectorStore(self.settings.chroma_persist_dir)

    def rag(self):
        """Lazily assembled RAG stack (overrides are honored on first use)."""
        if self._rag is None:
            from app.retrieval.context_builder import ContextBuilder
            from app.retrieval.dense_retriever import DenseRetriever
            from app.retrieval.lexical_retriever import LexicalRetriever
            from app.services.rag_service import RagService

            assert self.uow is not None
            embedder = self.build_embedder()
            store = self.build_vector_store()
            self._rag = RagService(
                settings=self.settings,
                uow=self.uow,
                dense_retriever=DenseRetriever(
                    embedder, store, self.settings.retrieval_top_k, self.settings.retrieval_min_score
                ),
                lexical_retriever=LexicalRetriever(self.uow, self.settings.retrieval_top_k),
                context_builder=ContextBuilder(self.settings.max_context_tokens),
                chat_model=self.build_chat_model(),
            )
        return self._rag

    def investigation_runner(self):
        """Lazily assembled RCA workflow runner (overrides honored on first use)."""
        if "investigation_runner" not in self._extras:
            from app.services.investigation_runner import InvestigationRunner

            assert self.uow is not None
            incident_service = self.get("incident_service")
            signal_extractor = self.get("signal_extractor")
            self._extras["investigation_runner"] = InvestigationRunner(
                settings=self.settings,
                uow=self.uow,
                incident_service=incident_service,
                signal_extractor=signal_extractor,
                chat_model=self.build_chat_model(),
                embedder=self.build_embedder(),
                vector_store=self.build_vector_store(),
            )
        return self._extras["investigation_runner"]

    def _build_pipeline(self, job_id: str) -> IngestionPipeline:
        assert self.uow is not None and self.job_manager is not None

        def publish(event) -> None:
            self.job_manager.publish(job_id, event)  # type: ignore[union-attr]

        return IngestionPipeline(
            settings=self.settings,
            uow=self.uow,
            github_client=self.build_github_client(),
            archive_extractor=ArchiveExtractor(self.settings),
            file_filter=FileFilter(self.settings),
            secret_scanner=SecretScanner(),
            ast_chunker=AstChunker(self.settings),
            heading_chunker=HeadingChunker(self.settings),
            line_chunker=LineChunker(self.settings),
            embedder=self.build_embedder(),
            vector_store=self.build_vector_store(),
            publish=publish,
        )

    # -- overrides (tests) -----------------------------------------------------

    def set(self, key: str, value: object) -> None:
        self._extras[key] = value

    def get(self, key: str) -> object:
        try:
            return self._extras[key]
        except KeyError as exc:  # pragma: no cover - wiring bug guard
            raise RuntimeError(f"Service '{key}' is not wired in the container") from exc


def build_container(settings: Settings | None = None) -> AppContainer:
    return AppContainer(settings=settings or get_settings())


_container: AppContainer | None = None


def init_container(container: AppContainer) -> None:
    global _container
    _container = container


def get_container() -> AppContainer:
    if _container is None:  # pragma: no cover - only when app not created
        init_container(build_container())
    assert _container is not None
    return _container


def close_container() -> None:
    global _container
    _container = None


__all__ = [
    "AppContainer",
    "ChunkRepository",
    "FileRecordRepository",
    "IncidentRepository",
    "JobRepository",
    "MessageRepository",
    "RepositoryRepository",
    "build_container",
    "close_container",
    "get_container",
    "init_container",
]
