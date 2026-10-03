"""Deterministic query preparation (PRD §10.1 step 2).

Extracts exact identifiers, file paths, exception strings, and quoted phrases
from the question so lexical retrieval and context ranking can honor exact
matches — no LLM call needed for this step (§10.3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_DOTTED = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]+)+\b")
_SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_CAMEL = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b")
_PATH = re.compile(r"[\w./\\-]+\.(?:py|pyw|md|toml|ya?ml|json|txt|cfg|ini|env)\b")
_EXCEPTION = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:Error|Exception|Warning))\b")
_QUOTED = re.compile(r"['\"]([^'\"]{2,80})['\"]")

_QUESTION_STOPWORDS = {
    "what", "which", "where", "who", "how", "why", "the", "a", "an",
    "is", "are", "does", "do", "did", "can", "this", "that", "it",
}


@dataclass
class QueryPlan:
    question: str
    identifiers: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    error_strings: list[str] = field(default_factory=list)
    quoted_phrases: list[str] = field(default_factory=list)

    def semantic_query(self) -> str:
        parts = [self.question]
        parts.extend(self.identifiers[:8])
        return " ".join(parts)

    def lexical_patterns(self) -> list[str]:
        return (self.paths + self.identifiers + self.error_strings + self.quoted_phrases)[:12]


def build_query_plan(question: str) -> QueryPlan:
    plan = QueryPlan(question=question.strip())

    plan.paths = _dedupe(_PATH.findall(question))
    plan.error_strings = _dedupe(_EXCEPTION.findall(question))
    plan.quoted_phrases = _dedupe(_QUOTED.findall(question))

    identifiers: list[str] = []
    identifiers.extend(_dedupe(_DOTTED.findall(question)))
    for name in _dedupe(_SNAKE.findall(question)) + _dedupe(_CAMEL.findall(question)):
        base = name.split(".")[0]
        if base.lower() in _QUESTION_STOPWORDS:
            continue
        identifiers.append(name)
    plan.identifiers = _dedupe(identifiers)
    return plan


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
