"""Groq chat provider behind the ChatModel interface (PRD §14.1/§14.3).

Encapsulates SDK calls, model ID, timeouts, output limits, and provider error
normalization. The API key never leaves the server. Only transient failures
are retried; permanent validation/auth errors propagate immediately."""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import ProviderError
from app.core.retry import retry_transient
from app.llm.output_parsers import parse_structured

from pydantic import BaseModel as PydanticBaseModel


class GroqChatProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.model_id = settings.groq_chat_model
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self._settings.groq_api_key:
                raise ProviderError(
                    "GROQ_API_KEY is not configured; set it in the environment.",
                    retryable=False,
                )
            from groq import Groq

            self._client = Groq(
                api_key=self._settings.groq_api_key,
                timeout=self._settings.llm_timeout_seconds,
            )
        return self._client

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[PydanticBaseModel],
        max_output_tokens: int,
    ) -> PydanticBaseModel:
        client = self._get_client()

        def _call() -> str:
            try:
                response = client.chat.completions.create(
                    model=self.model_id,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=max_output_tokens,
                    response_format={"type": "json_object"},
                )
            except Exception as exc:  # classified below
                raise _classify_provider_error(exc) from exc
            content = response.choices[0].message.content or ""
            if not content.strip():
                raise ProviderError("Model returned an empty response.", retryable=True)
            return content

        def _is_transient(exc: Exception) -> bool:
            target = getattr(exc, "__cause__", None) or exc
            if isinstance(target, ProviderError):
                return target.retryable
            status = getattr(target, "status_code", None)
            if isinstance(status, int):
                return status in {408, 429, 500, 502, 503, 504}
            return type(target).__name__.lower() in {
                "apitimeouterror",
                "apiconnectionerror",
                "ratelimiterror",
                "internalservererror",
            }

        try:
            raw = retry_transient(
                _call,
                is_transient=_is_transient,
                max_retries=3,
                base_delay_seconds=1.0,
                max_delay_seconds=10.0,
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise _classify_provider_error(exc) from exc

        try:
            return parse_structured(raw, schema)
        except Exception as exc:
            raise ProviderError(
                "Model output did not match the required schema.", retryable=False
            ) from exc


def _classify_provider_error(exc: Exception) -> ProviderError:
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__.lower()
    if "authentication" in name or "permission" in name or status in {401, 403}:
        return ProviderError("Model provider rejected the credentials.", retryable=False)
    if "ratelimit" in name or status == 429:
        return ProviderError("Model provider rate limit reached.", retryable=True)
    if "timeout" in name or "connection" in name or status in {408, 500, 502, 503, 504}:
        return ProviderError("Model provider is temporarily unavailable.", retryable=True)
    return ProviderError("A model provider request failed.", retryable=False)
