"""Context bundle assembly under a strict token budget (PRD FR-19, §10.1 step 7).

Prefers diverse evidence (bounded chunks per path, overlap suppression) over
near-duplicate pile-ups. Never sends the full repository."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models import RetrievedChunk
from app.domain.policies import estimate_tokens

_MAX_CHUNKS_PER_PATH = 3


@dataclass
class ContextBundle:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    total_tokens: int = 0
    truncated: bool = False

    def render(self) -> str:
        """The text block handed to the model: every chunk labeled with its
        source metadata so citations can reference source IDs."""
        parts: list[str] = []
        for chunk in self.chunks:
            location = f"{chunk.path}"
            if chunk.start_line is not None:
                location += f":{chunk.start_line}-{chunk.end_line}"
            header = f"[{chunk.chunk_id}] {location}"
            if chunk.symbol_name:
                header += f" ({chunk.symbol_name})"
            parts.append(f"{header}\n{chunk.content}")
        return "\n\n".join(parts)


class ContextBuilder:
    def __init__(self, max_tokens: int) -> None:
        self._max_tokens = max_tokens

    def build(self, ranked: list[RetrievedChunk]) -> ContextBundle:
        bundle = ContextBundle()
        spent = 0
        per_path_counts: dict[str, int] = {}
        covered: dict[str, list[tuple[int, int]]] = {}

        def overlaps(chunk: RetrievedChunk) -> bool:
            if chunk.start_line is None or chunk.end_line is None:
                return False
            for start, end in covered.get(chunk.path, []):
                if chunk.start_line <= end and start <= chunk.end_line:
                    return True
            return False

        def remember(chunk: RetrievedChunk) -> None:
            if chunk.start_line is not None and chunk.end_line is not None:
                covered.setdefault(chunk.path, []).append((chunk.start_line, chunk.end_line))

        # Pass 1: diversity-first — at most _MAX_CHUNKS_PER_PATH per file,
        # skipping line-range overlaps of already-selected chunks.
        deferred: list[RetrievedChunk] = []
        for chunk in ranked:
            if overlaps(chunk) or per_path_counts.get(chunk.path, 0) >= _MAX_CHUNKS_PER_PATH:
                deferred.append(chunk)
                continue
            tokens = estimate_tokens(chunk.content)
            if spent + tokens > self._max_tokens:
                bundle.truncated = True
                continue
            bundle.chunks.append(chunk)
            bundle.total_tokens += tokens
            spent += tokens
            per_path_counts[chunk.path] = per_path_counts.get(chunk.path, 0) + 1
            remember(chunk)

        # Pass 2: fill remaining budget with deferred chunks, still honoring
        # the per-path diversity cap and overlap suppression.
        for chunk in deferred:
            if bundle.total_tokens >= self._max_tokens:
                bundle.truncated = True
                break
            if overlaps(chunk) or per_path_counts.get(chunk.path, 0) >= _MAX_CHUNKS_PER_PATH:
                continue
            tokens = estimate_tokens(chunk.content)
            if spent + tokens > self._max_tokens:
                bundle.truncated = True
                continue
            bundle.chunks.append(chunk)
            bundle.total_tokens += tokens
            spent += tokens
            per_path_counts[chunk.path] = per_path_counts.get(chunk.path, 0) + 1
            remember(chunk)

        return bundle
