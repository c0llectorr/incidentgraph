"""Domain interfaces (PRD §8.2 domain/, §14.3 provider abstraction).

Application services depend on these protocols only; infrastructure adapters
(Groq, Chroma, sentence-transformers, GitHub) implement them. Interface
segregation is intentional: each protocol is minimal (PRD §7.2 ISP).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.domain.enums import ChunkingMethod, ChunkType
from app.domain.models import CodeChunk, RetrievedChunk


@dataclass(frozen=True)
class NormalizedGitHubSource:
    owner: str
    repo: str
    branch: str | None = None
    commit: str | None = None

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"


@dataclass(frozen=True)
class RepositoryMetadata:
    slug: str
    default_branch: str
    commit_sha: str
    html_url: str


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Embeds a bounded list of texts, returning vectors in the same order."""

    model_id: str
    dimension: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@runtime_checkable
class VectorStore(Protocol):
    """Vector persistence behind an interface (PRD §8.3 VectorStore row)."""

    def upsert(
        self,
        chunks: list[CodeChunk],
        vectors: list[list[float]],
        *,
        dimension: int,
    ) -> None: ...

    def search(
        self,
        query_vector: list[float],
        *,
        repository_id: str,
        index_version: str,
        top_k: int,
    ) -> list[RetrievedChunk]: ...

    def delete_by_repository(self, repository_id: str) -> int: ...

    def count(self, *, repository_id: str, index_version: str) -> int: ...

    def get_vectors(self, chunk_ids: list[str]) -> dict[str, list[float]]:
        """Fetch stored vectors by chunk ID (FR-13 reuse on re-ingestion)."""
        ...


@runtime_checkable
class ChatModel(Protocol):
    """Structured generation behind an interface (PRD §14.3)."""

    model_id: str

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type,
        max_output_tokens: int,
    ) -> object:
        """Return an instance of *schema* validated from the model output."""
        ...


@runtime_checkable
class GitHubClient(Protocol):
    """Constrained GitHub access: no arbitrary URL fetching (PRD §8.3)."""

    def resolve_metadata(self, source: NormalizedGitHubSource) -> RepositoryMetadata: ...

    def fetch_archive(self, source: NormalizedGitHubSource, *, commit_sha: str | None) -> bytes: ...


# Re-exported so adapters can build chunks without importing deeper modules.
__all__ = [
    "ChatModel",
    "ChunkType",
    "ChunkingMethod",
    "CodeChunk",
    "EmbeddingProvider",
    "GitHubClient",
    "NormalizedGitHubSource",
    "RepositoryMetadata",
    "RetrievedChunk",
    "VectorStore",
]
