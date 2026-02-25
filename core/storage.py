from __future__ import annotations

import hashlib
import os
from pathlib import Path

from fastapi import UploadFile

from core.media import MediaRef


def _safe_ext(filename: str | None) -> str:
    if not filename:
        return ""
    base = os.path.basename(filename)
    _, ext = os.path.splitext(base)
    ext = ext.lower()
    if len(ext) > 10:
        return ""
    return ext


class LocalStorage:
    def __init__(self, *, uploads_dir: Path, artifacts_dir: Path):
        self.uploads_dir = uploads_dir
        self.artifacts_dir = artifacts_dir
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, *, request_id: str, field: str, upload: UploadFile) -> MediaRef:
        req_dir = self.uploads_dir / request_id
        req_dir.mkdir(parents=True, exist_ok=True)

        ext = _safe_ext(upload.filename)
        out_path = req_dir / f"{field}{ext}"

        h = hashlib.sha256()
        size = 0

        with out_path.open("wb") as f:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                size += len(chunk)

        await upload.close()
        return MediaRef(
            path=out_path,
            sha256=h.hexdigest(),
            original_filename=upload.filename,
            content_type=upload.content_type,
            size_bytes=size,
        )
