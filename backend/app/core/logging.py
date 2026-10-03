"""Structured logging with secret redaction (PRD §6.1, observability row).

Never log raw user evidence, full prompts, or credentials: a redaction filter
scrubs known secret shapes from every record before it is emitted.
"""

from __future__ import annotations

import contextvars
import logging
import re
import sys

_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

# Shapes we must never emit: Groq keys, bearer tokens, AWS access keys,
# private key blocks, GitHub tokens, generic api_key assignments.
_SECRET_PATTERNS = [
    re.compile(r"gsk_[A-Za-z0-9]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)(api[_-]?key|secret|password|token)(\s*[=:]\s*)['\"][^'\"]{8,}['\"]"),
]

_REDACTED = "[REDACTED]"


def redact_secrets(text: str) -> str:
    result = text
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(_REDACTED, result)
    return result


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            record.args = tuple(
                redact_secrets(arg) if isinstance(arg, str) else arg for arg in record.args
            )
        record.request_id = _request_id_var.get() or "-"
        return True


_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s",
            "%Y-%m-%dT%H:%M:%S",
        )
    )
    handler.addFilter(SecretRedactionFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def set_request_id(request_id: str) -> contextvars.Token[str]:
    return _request_id_var.set(request_id)


def get_request_id() -> str:
    return _request_id_var.get()
