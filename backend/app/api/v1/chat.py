"""Repository Q&A endpoint (PRD §8.5). No business logic here."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies import get_container
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/repositories/{repository_id}/chat", response_model=ChatResponse)
def ask_repository_question(repository_id: str, payload: ChatRequest) -> ChatResponse:
    result = get_container().rag().answer(
        repository_id=repository_id,
        question=payload.question,
        conversation_id=payload.conversation_id,
    )
    return ChatResponse(
        conversation_id=result.conversation_id,
        status=result.status,
        answer=result.answer,
        citations=result.citations,
        uncertainty=result.uncertainty,
        clarifying_question=result.clarifying_question,
        dropped_citation_count=result.dropped_citation_count,
    )
