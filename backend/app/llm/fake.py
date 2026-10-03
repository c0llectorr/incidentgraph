"""Deterministic chat-model test double implementing the ChatModel interface.

Records every prompt it receives (for prompt-contract assertions) and returns
canned structured results provided by the test."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class ChatCall:
    system_prompt: str
    user_prompt: str
    schema_name: str


class FakeChatModel:
    model_id = "fake-chat-model"

    def __init__(
        self,
        responder: Callable[[ChatCall], object] | None = None,
        default_responses: dict[str, object] | None = None,
    ) -> None:
        self.calls: list[ChatCall] = []
        self._responder = responder
        self._defaults = default_responses or {}

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type,
        max_output_tokens: int,
    ) -> object:
        call = ChatCall(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_name=schema.__name__,
        )
        self.calls.append(call)
        if self._responder is not None:
            return self._responder(call)
        if schema.__name__ in self._defaults:
            return self._defaults[schema.__name__]
        raise AssertionError(f"No canned response registered for {schema.__name__}")
