"""Deterministic hashing embedder — no network, no model download.

Used by the test suite and as an offline dev fallback. Bag-of-words hashing
into a fixed dimension gives real cosine similarity for shared tokens, so
retrieval tests exercise actual ranking behavior (never used in production
config; PRD FR-14 requires Qwen embeddings behind the same interface).
"""

from __future__ import annotations

import hashlib
import math
import re

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class HashingEmbeddingProvider:
    model_id = "hashing-embedder-v1"
    dimension = 256

    def _vectorize(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in _TOKEN.findall(text.lower()):
            digest = hashlib.sha1(token.encode("utf-8")).hexdigest()
            index = int(digest[:8], 16) % self.dimension
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vectorize(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vectorize(text)
