from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaRef:
    path: Path
    sha256: str
    original_filename: str | None
    content_type: str | None
    size_bytes: int
