"""RAG orchestration (PRD §10.1, FR-20..FR-24).

Retrieve → fuse → budget context → structured generation → validate citations
against the retrieved evidence set → honest statuses. Fabricated citations
are dropped; weak retrieval yields an explicit insufficiency answer, never a
fabricated citation."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import Settings
from app.core.errors import IndexNotReadyError, NotFoundError
from app.core.ids import new_message_id
from app.core.logging import get_logger
from app.domain.enums import ChatStatus, MessageRole
from app.domain.models import SourceCitation
from app.domain.policies import validate_citations
from app.llm.output_parsers import QAAnswer
from app.llm.prompts import QA_SYSTEM_PROMPT, build_qa_user_prompt
from app.persistence.models import ConversationMessageRow
from app.persistence.repositories import MessageRepository, RepositoryRepository
from app.persistence.unit_of_work import UnitOfWork
from app.retrieval.context_builder import ContextBundle, ContextBuilder
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.lexical_retriever import LexicalRetriever
from app.retrieval.query_rewriter import build_query_plan

logger = get_logger(__name__)

_EXCERPT_CHARS = 240


@dataclass
class ChatResult:
    conversation_id: str
    status: str  # ChatStatus value
    answer: str
    citations: list[SourceCitation] = field(default_factory=list)
    uncertainty: list[str] = field(default_factory=list)
    clarifying_question: str | None = None
    dropped_citation_count: int = 0


class RagService:
    def __init__(
        self,
        settings: Settings,
        uow: UnitOfWork,
        dense_retriever: DenseRetriever,
        lexical_retriever: LexicalRetriever,
        context_builder: ContextBuilder,
        chat_model,
    ) -> None:
        self._settings = settings
        self._uow = uow
        self._dense = dense_retriever
        self._lexical = lexical_retriever
        self._context_builder = context_builder
        self._chat = chat_model

    # -- public API ------------------------------------------------------------

    def answer(
        self,
        *,
        repository_id: str,
        question: str,
        conversation_id: str | None = None,
        scope_incident_id: str | None = None,
    ) -> ChatResult:
        repository = self._load_ready_repository(repository_id)
        index_version = repository.index_version
        conversation_id = conversation_id or f"conv_{repository_id[:12]}"

        plan = build_query_plan(question)
        dense_hits = self._dense.retrieve(
            repository_id=repository_id, index_version=index_version, plan=plan
        )
        lexical_hits = self._lexical.retrieve(
            repository_id=repository_id, index_version=index_version, plan=plan
        )
        fused = reciprocal_rank_fusion([dense_hits, lexical_hits])

        if not fused:
            result = self._insufficient_result(
                conversation_id,
                repository_id,
                scope_incident_id,
                question,
                reason="The indexed repository contains no material relevant to this question.",
            )
            self._persist_messages(conversation_id, repository_id, scope_incident_id, question, result)
            return result

        bundle = self._context_builder.build(fused)
        history_summary = self._history_summary(conversation_id)
        user_prompt = build_qa_user_prompt(question, bundle, history_summary)
        qa: QAAnswer = self._chat.generate_structured(
            system_prompt=QA_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=QAAnswer,
            max_output_tokens=self._settings.llm_max_output_tokens,
        )

        evidence_ids = {chunk.chunk_id for chunk in bundle.chunks}
        cited_ids = [source_id for claim in qa.claims for source_id in claim.source_ids]
        check = validate_citations(cited_ids, evidence_ids)

        chunk_by_id = {chunk.chunk_id: chunk for chunk in bundle.chunks}
        citations = [
            self._citation_for(chunk_by_id[source_id]) for source_id in dict.fromkeys(check.valid_ids)
        ]
        insufficient = qa.insufficient_evidence or not citations
        status = ChatStatus.INSUFFICIENT_EVIDENCE.value if insufficient else ChatStatus.OK.value

        result = ChatResult(
            conversation_id=conversation_id,
            status=status,
            answer=qa.answer if qa.answer or insufficient else "",
            citations=citations,
            uncertainty=qa.uncertainty,
            clarifying_question=qa.clarifying_question,
            dropped_citation_count=len(check.invalid_ids),
        )
        if check.has_invalid:
            logger.warning(
                "Dropped %d fabricated/out-of-scope citations", len(check.invalid_ids)
            )
        self._persist_messages(conversation_id, repository_id, scope_incident_id, question, result)
        return result

    # -- internals ---------------------------------------------------------------

    def _load_ready_repository(self, repository_id: str):
        with self._uow.begin() as session:
            repository = RepositoryRepository().get(session, repository_id)
            if repository is None:
                raise NotFoundError("Repository not found.")
            if repository.status != "ready" or not repository.index_version:
                raise IndexNotReadyError(
                    "This repository has no completed index yet; run ingestion first."
                )
            session.expunge(repository)
            return repository

    def _history_summary(self, conversation_id: str) -> str | None:
        window = self._settings.chat_history_window
        with self._uow.begin() as session:
            rows = MessageRepository().recent(session, conversation_id, limit=window)
            if not rows:
                return None
            lines = [f"{row.role}: {row.content[:160]}" for row in rows]
            return " | ".join(lines)

    def _citation_for(self, chunk) -> SourceCitation:
        excerpt = chunk.content[:_EXCERPT_CHARS] + ("…" if len(chunk.content) > _EXCERPT_CHARS else "")
        return SourceCitation(
            source_id=chunk.chunk_id,
            path=chunk.path,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            excerpt=excerpt,
        )

    def _insufficient_result(
        self,
        conversation_id: str,
        repository_id: str,
        scope_incident_id: str | None,
        question: str,
        *,
        reason: str,
    ) -> ChatResult:
        return ChatResult(
            conversation_id=conversation_id,
            status=ChatStatus.INSUFFICIENT_EVIDENCE.value,
            answer=reason,
            citations=[],
            uncertainty=[reason],
            clarifying_question=(
                f"Could you point to a related file, endpoint, or identifier in the repository "
                f"for '{question[:80]}'?"
            ),
            dropped_citation_count=0,
        )

    def _persist_messages(
        self,
        conversation_id: str,
        repository_id: str,
        scope_incident_id: str | None,
        question: str,
        result: ChatResult,
    ) -> None:
        scope_type = "incident" if scope_incident_id else "repository"
        with self._uow.begin() as session:
            MessageRepository().add(
                session,
                ConversationMessageRow(
                    message_id=new_message_id(),
                    conversation_id=conversation_id,
                    scope_type=scope_type,
                    repository_id=repository_id,
                    incident_id=scope_incident_id,
                    role=MessageRole.USER.value,
                    content=question,
                ),
            )
            MessageRepository().add(
                session,
                ConversationMessageRow(
                    message_id=new_message_id(),
                    conversation_id=conversation_id,
                    scope_type=scope_type,
                    repository_id=repository_id,
                    incident_id=scope_incident_id,
                    role=MessageRole.ASSISTANT.value,
                    content=result.answer or (result.clarifying_question or ""),
                    citations=[citation.model_dump() for citation in result.citations],
                    status=result.status,
                ),
            )
