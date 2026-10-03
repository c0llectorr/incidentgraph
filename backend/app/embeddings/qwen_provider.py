"""Qwen3-Embedding adapter (PRD FR-14, §14.2).

Two transports behind one interface:
- local: sentence-transformers loading e.g. Qwen/Qwen3-Embedding-0.6B
- remote: any configured OpenAI-compatible /embeddings endpoint

Groq is deliberately NOT assumed to serve embeddings just because it serves
Qwen chat models (§14.2). Model ID, dimension, and revision are exposed for
index metadata.
"""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.core.errors import ProviderError
from app.core.logging import get_logger

logger = get_logger(__name__)

_LOCAL_MODEL_CACHE: dict[str, object] = {}


class QwenEmbeddingProvider:
    def __init__(self, settings: Settings, *, dimension: int | None = None) -> None:
        self._settings = settings
        self._model_id = (
            settings.qwen_embedding_model
            if settings.embedding_provider == "local"
            else (settings.embedding_remote_model or settings.qwen_embedding_model)
        )
        self._dimension = dimension
        self._model: object | None = None

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            if self._settings.embedding_provider == "local":
                self._load_local()
            else:
                # Remote dimension is discovered from the first response.
                sample = self._embed_remote(["dimension probe"])
                self._dimension = len(sample[0])
        assert self._dimension is not None
        return self._dimension

    # -- local transport ----------------------------------------------------

    def _load_local(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ProviderError(
                "sentence-transformers is not installed; install it or set "
                "EMBEDDING_PROVIDER=remote with a compatible endpoint."
            ) from exc
        logger.info("Loading local embedding model %s (first run downloads it)", self._model_id)
        self._model = SentenceTransformer(self._settings.qwen_embedding_model)
        self._dimension = int(self._model.get_sentence_embedding_dimension())

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        self._load_local()
        assert self._model is not None
        vectors = self._model.encode(texts, show_progress_bar=False)  # type: ignore[attr-defined]
        return [list(map(float, vector)) for vector in vectors]

    # -- remote transport ---------------------------------------------------

    def _embed_remote(self, texts: list[str]) -> list[list[float]]:
        base_url = self._settings.embedding_remote_base_url.rstrip("/")
        if not base_url:
            raise ProviderError(
                "EMBEDDING_PROVIDER=remote requires EMBEDDING_REMOTE_BASE_URL."
            )
        headers = {"Authorization": f"Bearer {self._settings.embedding_remote_api_key}"}
        try:
            with httpx.Client(timeout=self._settings.llm_timeout_seconds) as client:
                response = client.post(
                    f"{base_url}/embeddings",
                    json={"model": self._model_id, "input": texts},
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Embedding endpoint returned status {exc.response.status_code}."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Embedding endpoint is unreachable.") from exc
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise ProviderError("Embedding endpoint returned an unexpected payload.")
        ordered = sorted(data, key=lambda item: item.get("index", 0))
        return [list(map(float, item["embedding"])) for item in ordered]

    # -- EmbeddingProvider interface ----------------------------------------

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._settings.embedding_provider == "local":
            return self._embed_local(texts)
        return self._embed_remote(texts)

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_documents([text])
        return vectors[0]
