"""Deterministic incident signal extraction (PRD FR-28, §8.3).

Pure parsing — no LLM. Traceback frames, exception types, timestamps, HTTP
status codes, request IDs, file paths, and error signatures are extracted
with regexes so results are reproducible and cheap (§10.3)."""

from __future__ import annotations

import re
from collections import Counter

from app.domain.models import Signal

_TRACEBACK_FRAME = re.compile(r'File "([^"]+)", line (\d+), in (\S+)')
_EXCEPTION_LINE = re.compile(
    r"^(?:[\w.]+\.)?([A-Za-z_][\w]*(?:Error|Exception|Warning|Interrupt|Exit))\s*:\s*(.+)$",
    re.MULTILINE,
)
_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
)
_HTTP_STATUS = re.compile(r"\b(?:HTTP|status|code)[\"'= :]+(\d{3})\b", re.IGNORECASE)
_REQUEST_ID = re.compile(
    r"(?i)(?:request[_-]?id|req[_-]?id|trace[_-]?id|x-request-id)[\"'= :]+([A-Za-z0-9_.-]{6,64})"
)
_FILE_PATH = re.compile(r"(?:[A-Za-z]:)?[/\\]?[\w./\\-]+\.(?:py|toml|ya?ml|json|ini|cfg)\b")
_ENDPOINT = re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE)\s+(/\S+)")

_MAX_SIGNALS = 200


class IncidentSignalExtractor:
    def extract(self, artifacts: list[tuple[str, str]]) -> list[Signal]:
        """*artifacts* is a list of (evidence_type, content) pairs."""
        signals: list[Signal] = []
        for evidence_type, content in artifacts:
            if evidence_type in {"traceback", "log"}:
                signals.extend(self._from_traceback(content))
                signals.extend(self._from_log(content))
        return signals[:_MAX_SIGNALS]

    def _from_traceback(self, content: str) -> list[Signal]:
        signals: list[Signal] = []
        for path, line, function in _TRACEBACK_FRAME.findall(content):
            signals.append(
                Signal(
                    kind="traceback_frame",
                    value=f"{path}:{line} in {function}",
                    file_path=path,
                    line_number=int(line),
                    detail=f"frame in {function}",
                )
            )
        exceptions = _EXCEPTION_LINE.findall(content)
        if exceptions:
            exception_type, message = exceptions[-1]
            signals.append(
                Signal(kind="exception", value=exception_type, detail=message.strip()[:200])
            )
        return signals

    def _from_log(self, content: str) -> list[Signal]:
        signals: list[Signal] = []
        for match in _TIMESTAMP.findall(content)[:20]:
            signals.append(Signal(kind="timestamp", value=match))
        for match in _HTTP_STATUS.findall(content)[:20]:
            signals.append(Signal(kind="http_status", value=match))
        for match in _REQUEST_ID.findall(content)[:20]:
            signals.append(Signal(kind="request_id", value=match))
        for match in _ENDPOINT.findall(content)[:20]:
            signals.append(Signal(kind="endpoint", value=match))
        for path, count in Counter(_FILE_PATH.findall(content)).most_common(10):
            signals.append(Signal(kind="file_path", value=path, detail=f"mentioned {count}x"))
        return signals
