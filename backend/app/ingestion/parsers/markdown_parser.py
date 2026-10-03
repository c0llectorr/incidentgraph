"""Markdown section parsing: heading boundaries become chunk anchors."""

from __future__ import annotations

import re

from app.ingestion.parsers.base import MarkdownSection

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def parse_markdown(source: str, path: str) -> list[MarkdownSection]:
    lines = source.splitlines()
    sections: list[MarkdownSection] = []
    current_heading: str | None = None
    current_level = 0
    current_start = 1

    for line_number, line in enumerate(lines, start=1):
        match = _HEADING.match(line)
        if match:
            if current_heading is not None:
                sections.append(
                    MarkdownSection(
                        heading=current_heading,
                        level=current_level,
                        start_line=current_start,
                        end_line=line_number - 1,
                    )
                )
            current_heading = match.group(2).strip()
            current_level = len(match.group(1))
            current_start = line_number

    if current_heading is not None:
        sections.append(
            MarkdownSection(
                heading=current_heading,
                level=current_level,
                start_line=current_start,
                end_line=len(lines),
            )
        )
    return sections
