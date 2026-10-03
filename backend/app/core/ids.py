"""ID generation and content hashing. All IDs are prefixed and opaque."""

from __future__ import annotations

import hashlib
import uuid


def _short_uuid() -> str:
    return uuid.uuid4().hex[:20]


def new_request_id() -> str:
    return f"req_{_short_uuid()}"


def new_repository_id() -> str:
    return f"rep_{_short_uuid()}"


def new_job_id() -> str:
    return f"job_{_short_uuid()}"


def new_incident_id() -> str:
    return f"inc_{_short_uuid()}"


def new_artifact_id() -> str:
    return f"art_{_short_uuid()}"


def new_hypothesis_id() -> str:
    return f"hyp_{_short_uuid()}"


def new_message_id() -> str:
    return f"msg_{_short_uuid()}"


def new_verification_id() -> str:
    return f"vrf_{_short_uuid()}"


def new_index_version() -> str:
    return f"idx_{_short_uuid()}"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_chunk_id(
    *,
    repository_id: str,
    path: str,
    start_line: int,
    end_line: int,
    content_hash_value: str,
) -> str:
    """Deterministic chunk ID: identical inputs yield identical IDs, which
    makes chunking reproducible and deduplication possible (PRD FR-06/FR-13).
    Deliberately independent of index_version so unchanged chunks keep their
    identity across re-ingestions."""
    material = "|".join([repository_id, path, str(start_line), str(end_line), content_hash_value])
    return "chk_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
