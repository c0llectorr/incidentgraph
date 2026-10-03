"""Deterministic file enumeration (PRD FR-06)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiscoveredFile:
    relative_path: str
    absolute_path: Path
    size_bytes: int


def discover_files(root: Path) -> list[DiscoveredFile]:
    """Recursively enumerate files preserving relative paths, sorted by POSIX
    relative path so the same revision always produces the same order."""
    discovered: list[DiscoveredFile] = []
    for path in root.rglob("*"):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            discovered.append(
                DiscoveredFile(
                    relative_path=relative,
                    absolute_path=path,
                    size_bytes=path.stat().st_size,
                )
            )
    discovered.sort(key=lambda item: item.relative_path)
    return discovered
