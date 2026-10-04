"""Safe ZIP extraction into an isolated workspace (PRD §9.1 step 3, FR-02).

Defends against path traversal, absolute paths, symlinks, archive bombs
(compression ratio), excessive entries, and per-entry/total size limits.
Extracted files are NEVER executed.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from app.core.config import Settings
from app.core.errors import ArchiveUnsafeError, LimitExceededError

_S_IFLNK = 0o120000  # symlink file type in the high 16 bits of external_attr
_MAX_COMPRESSION_RATIO = 500  # > this is treated as a decompression bomb
_TRAVERSAL_SEGMENTS = {"..", ""}


@dataclass
class ExtractionReport:
    relative_paths: list[str] = field(default_factory=list)
    total_bytes: int = 0
    stripped_prefix: str | None = None


class ArchiveExtractor:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def extract_zip_bytes(self, data: bytes, destination: Path) -> ExtractionReport:
        if len(data) > self._settings.max_total_extracted_bytes:
            raise LimitExceededError(
                "Archive exceeds the configured total extraction budget of "
                f"{self._settings.max_total_extracted_bytes} bytes."
            )
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise ArchiveUnsafeError("The uploaded file is not a readable ZIP archive.") from exc

        with archive:
            infos = archive.infolist()
            file_infos = [info for info in infos if not info.is_dir()]
            if len(file_infos) > self._settings.max_repository_files:
                raise LimitExceededError(
                    "Archive contains more files than the configured limit of "
                    f"{self._settings.max_repository_files}."
                )
            prefix = self._common_root(file_infos)
            report = ExtractionReport(stripped_prefix=prefix)
            destination.mkdir(parents=True, exist_ok=True)

            for info in file_infos:
                relative = self._safe_relative(info, prefix)
                self._guard_member(info, relative)
                target = (destination / relative).resolve()
                if not target.is_relative_to(destination.resolve()):
                    # Defense in depth behind the segment checks.
                    raise ArchiveUnsafeError("Archive member escapes the extraction workspace.")

                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as member, target.open("wb") as output:
                    written = 0
                    while chunk := member.read(64 * 1024):
                        written += len(chunk)
                        report.total_bytes += len(chunk)
                        if written > self._settings.max_file_bytes:
                            raise LimitExceededError(
                                f"Archive member '{relative}' exceeds the per-file limit of "
                                f"{self._settings.max_file_bytes} bytes."
                            )
                        if report.total_bytes > self._settings.max_total_extracted_bytes:
                            raise LimitExceededError(
                                "Archive exceeds the configured total extraction budget of "
                                f"{self._settings.max_total_extracted_bytes} bytes."
                            )
                        output.write(chunk)
                report.relative_paths.append(str(relative))

        report.relative_paths.sort()
        return report

    # -- guards -------------------------------------------------------------

    def _safe_relative(self, info: zipfile.ZipInfo, prefix: str | None) -> PurePosixPath:
        name = info.filename.replace("\\", "/")
        if len(name) > 400:
            # Absurdly long member names are an archive-flooding pattern.
            raise ArchiveUnsafeError("Archive member name is unreasonably long.")
        pure = PurePosixPath(name)
        if pure.is_absolute() or (len(name) > 1 and name[1] == ":"):
            raise ArchiveUnsafeError("Archive contains absolute paths.")
        if prefix and name.startswith(prefix):
            name = name[len(prefix) :]
            pure = PurePosixPath(name)
        if any(segment in _TRAVERSAL_SEGMENTS for segment in pure.parts):
            raise ArchiveUnsafeError("Archive contains path traversal segments.")
        return pure

    def _guard_member(self, info: zipfile.ZipInfo, relative: PurePosixPath) -> None:
        mode = (info.external_attr >> 16) & 0o170000
        if mode == _S_IFLNK:
            raise ArchiveUnsafeError("Archive contains symlinks, which are not allowed.")
        # Bomb check BEFORE the per-file size cap: a decompression bomb also
        # trips the size cap, but the bomb diagnosis is the actionable one.
        compress_size = max(1, info.compress_size)
        if info.file_size / compress_size > _MAX_COMPRESSION_RATIO:
            raise ArchiveUnsafeError(
                f"Archive member '{relative}' has an extreme compression ratio "
                "(decompression-bomb pattern)."
            )
        if info.file_size > self._settings.max_file_bytes:
            raise LimitExceededError(
                f"Archive member '{relative}' exceeds the per-file limit of "
                f"{self._settings.max_file_bytes} bytes."
            )

    @staticmethod
    def _common_root(infos: list[zipfile.ZipInfo]) -> str | None:
        """GitHub zipballs wrap everything in '{repo}-{sha}/'; strip it."""
        if not infos:
            return None
        first = infos[0].filename.replace("\\", "/")
        if "/" not in first:
            return None
        candidate = first.split("/", 1)[0] + "/"
        if all(info.filename.replace("\\", "/").startswith(candidate) for info in infos):
            return candidate
        return None
