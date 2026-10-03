"""Secret safety before chunking/embedding (PRD FR-08).

Likely credentials, private keys, access tokens, and raw .env contents are
never embedded: files matching secret filename rules are excluded, and
content matches are redacted or cause exclusion. Detection is heuristic —
the system must never claim perfect secret detection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Filenames that are excluded outright, regardless of content.
SECRET_FILENAME_RULES = re.compile(
    r"(^|/)(\.env(\..+)?|.*\.pem|.*\.p12|.*\.pfx|id_rsa.*|id_dsa.*|id_ecdsa.*|"
    r".*_rsa|credentials?\.json|secrets?\.(ya?ml|json|txt)|\.npmrc|\.netrc)$",
    re.IGNORECASE,
)

_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL
)

# (name, pattern) — pattern match is replaced with a redaction marker.
CONTENT_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("groq_api_key", re.compile(r"gsk_[A-Za-z0-9]{16,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("private_key_block", _PRIVATE_KEY_BLOCK),
    (
        "credential_assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|password|passwd|access[_-]?token)\b"
            r"(\s*[:=]\s*)(['\"])[^'\"]{8,}\3"
        ),
    ),
    (
        "bearer_token",
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}"),
    ),
]

_EXCLUDE_FINDING_THRESHOLD = 25


@dataclass
class ScanVerdict:
    action: str  # "keep" | "redact" | "exclude"
    reason: str | None = None
    redacted_text: str | None = None
    findings: list[str] = field(default_factory=list)

    @property
    def is_included(self) -> bool:
        return self.action in {"keep", "redact"}


class SecretScanner:
    def verdict_for_filename(self, relative_path: str) -> ScanVerdict | None:
        if SECRET_FILENAME_RULES.search(relative_path):
            return ScanVerdict(
                action="exclude",
                reason="secret-bearing filename (contents never read or reported)",
            )
        return None

    def scan_text(self, text: str) -> ScanVerdict:
        if _PRIVATE_KEY_BLOCK.search(text):
            return ScanVerdict(action="exclude", reason="contains a private key block")

        findings: list[str] = []
        redacted = text
        for name, pattern in CONTENT_RULES:
            matches = pattern.findall(text)
            if not matches:
                continue
            findings.append(f"{name} x{len(matches)}")
            redacted = pattern.sub(f"[REDACTED:{name}]", redacted)

        if not findings:
            return ScanVerdict(action="keep")

        if len(findings) >= _EXCLUDE_FINDING_THRESHOLD:
            return ScanVerdict(
                action="exclude",
                reason="too many secret-pattern hits; file excluded entirely",
                findings=findings,
            )
        return ScanVerdict(action="redact", reason="secrets redacted", redacted_text=redacted, findings=findings)
