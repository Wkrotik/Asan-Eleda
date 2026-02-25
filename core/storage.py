from __future__ import annotations

import hashlib
import os
from pathlib import Path

from fastapi import UploadFile

from core.media import MediaRef


class UploadTooLargeError(RuntimeError):
    def __init__(self, *, size_bytes: int, max_bytes: int):
        super().__init__(f"Upload exceeds limit ({size_bytes} > {max_bytes} bytes)")
        self.size_bytes = int(size_bytes)
        self.max_bytes = int(max_bytes)


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
    def __init__(self, *, uploads_dir: Path, artifacts_dir: Path, max_upload_bytes: int | None = None):
        self.uploads_dir = uploads_dir
        self.artifacts_dir = artifacts_dir
        self.max_upload_bytes = max_upload_bytes
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, *, request_id: str, field: str, upload: UploadFile) -> MediaRef:
        req_dir = self.uploads_dir / request_id
        req_dir.mkdir(parents=True, exist_ok=True)

        ext = _safe_ext(upload.filename)
        out_path = req_dir / f"{field}{ext}"

        h = hashlib.sha256()
        size = 0

        try:
            with out_path.open("wb") as f:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    size += len(chunk)
                    if self.max_upload_bytes is not None and size > int(self.max_upload_bytes):
                        raise UploadTooLargeError(size_bytes=size, max_bytes=int(self.max_upload_bytes))
        except Exception:
            # Best-effort cleanup of partial files.
            try:
                if out_path.exists():
                    out_path.unlink()
            except Exception:
                pass
            raise

        await upload.close()
        return MediaRef(
            path=out_path,
            sha256=h.hexdigest(),
            original_filename=upload.filename,
            content_type=upload.content_type,
            size_bytes=size,
        )
