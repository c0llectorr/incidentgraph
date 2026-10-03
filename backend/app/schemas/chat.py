"""Chat schemas (PRD §8.5, FR-20..FR-25 contract for the frontend)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models import SourceCitation


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4_000)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    status: str
    answer: str
    citations: list[SourceCitation] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    clarifying_question: str | None = None
    dropped_citation_count: int = 0
