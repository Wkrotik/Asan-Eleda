from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
from pathlib import Path

from fastapi import UploadFile

from core.media import MediaRef

logger = logging.getLogger(__name__)

# Allowed MIME type prefixes for uploads.
ALLOWED_CONTENT_TYPE_PREFIXES = ("image/", "video/")


class UploadTooLargeError(RuntimeError):
    def __init__(self, *, size_bytes: int, max_bytes: int):
        super().__init__(f"Upload exceeds limit ({size_bytes} > {max_bytes} bytes)")
        self.size_bytes = int(size_bytes)
        self.max_bytes = int(max_bytes)


class UnsupportedMediaTypeError(RuntimeError):
    """Raised when the uploaded file has an unsupported content type."""

    def __init__(self, *, content_type: str | None):
        ct = content_type or "(unknown)"
        super().__init__(f"Unsupported media type: {ct}. Allowed: image/*, video/*")
        self.content_type = content_type


def _safe_ext(filename: str | None) -> str:
    if not filename:
        return ""
    base = os.path.basename(filename)
    _, ext = os.path.splitext(base)
    ext = ext.lower()
    if len(ext) > 10:
        return ""
    return ext


def _is_allowed_content_type(content_type: str | None) -> bool:
    """Check if content type is in the allowlist."""
    if not content_type:
        return False
    ct = content_type.lower().strip()
    return any(ct.startswith(prefix) for prefix in ALLOWED_CONTENT_TYPE_PREFIXES)


def _infer_content_type(filename: str | None, provided_content_type: str | None) -> str | None:
    """Infer content type from filename extension if not provided or invalid.

    Some HTTP clients (e.g., requests library without explicit content_type)
    don't send Content-Type headers for file parts in multipart uploads.
    This function uses the standard mimetypes module to guess from the
    filename extension as a fallback.
    """
    # If a valid content type was provided, use it
    if _is_allowed_content_type(provided_content_type):
        return provided_content_type

    # Try to infer from filename extension
    if filename:
        guessed, _ = mimetypes.guess_type(filename)
        if guessed and _is_allowed_content_type(guessed):
            logger.debug(
                "Inferred content_type=%s from filename=%s (provided=%s)",
                guessed,
                filename,
                provided_content_type,
            )
            return guessed

    # Return whatever was provided (validation will fail if invalid)
    return provided_content_type


class LocalStorage:
    def __init__(self, *, uploads_dir: Path, artifacts_dir: Path, max_upload_bytes: int | None = None):
        self.uploads_dir = uploads_dir
        self.artifacts_dir = artifacts_dir
        self.max_upload_bytes = max_upload_bytes
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, *, request_id: str, field: str, upload: UploadFile) -> MediaRef:
        # Infer content type from filename if not provided by client
        content_type = _infer_content_type(upload.filename, upload.content_type)

        # Validate content type before processing
        if not _is_allowed_content_type(content_type):
            raise UnsupportedMediaTypeError(content_type=upload.content_type)

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
            content_type=content_type,
            size_bytes=size,
        )
