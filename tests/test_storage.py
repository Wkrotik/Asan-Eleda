"""Unit tests for core/storage.py functions."""
from __future__ import annotations

import pytest

from core.storage import _safe_ext, _is_allowed_content_type, _infer_content_type


class TestSafeExt:
    """Tests for _safe_ext safe filename extension extraction."""

    def test_normal_extension(self):
        """Normal file extension should be extracted."""
        assert _safe_ext("photo.jpg") == ".jpg"

    def test_uppercase_extension(self):
        """Uppercase extension should be lowercased."""
        assert _safe_ext("PHOTO.JPG") == ".jpg"

    def test_mixed_case_extension(self):
        """Mixed case extension should be lowercased."""
        assert _safe_ext("Photo.JpG") == ".jpg"

    def test_no_extension(self):
        """File without extension should return empty string."""
        assert _safe_ext("noextension") == ""

    def test_none_input(self):
        """None input should return empty string."""
        assert _safe_ext(None) == ""

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert _safe_ext("") == ""

    def test_hidden_file_with_extension(self):
        """Hidden file with extension should work correctly."""
        assert _safe_ext(".hidden.jpg") == ".jpg"

    def test_hidden_file_without_extension(self):
        """Hidden file without extension should return empty string."""
        # Note: .hidden is considered the name with no extension by os.path.splitext
        # and _safe_ext also returns empty string for this case
        assert _safe_ext(".hidden") == ""

    def test_multiple_dots(self):
        """Multiple dots should return last extension."""
        assert _safe_ext("file.tar.gz") == ".gz"
        assert _safe_ext("my.video.file.mp4") == ".mp4"

    def test_long_extension_rejected(self):
        """Extensions longer than 10 chars should be rejected."""
        assert _safe_ext("file.verylongextension") == ""

    def test_exactly_10_char_extension(self):
        """Extension of exactly 10 chars is rejected (len > 10 means ext without dot > 9)."""
        # _safe_ext rejects extensions where len(ext) > 10 (including the dot)
        # ".1234567890" has len=11, so it's rejected
        assert _safe_ext("file.1234567890") == ""

    def test_11_char_extension_rejected(self):
        """Extension of 11 chars should be rejected."""
        assert _safe_ext("file.12345678901") == ""

    def test_path_traversal_attack(self):
        """Path traversal attempts should be sanitized."""
        # The extension of "../../../etc/passwd" is ""
        result = _safe_ext("../../../etc/passwd")
        assert result == ""

    def test_path_with_directory(self):
        """Full path should extract extension from basename."""
        assert _safe_ext("/home/user/photos/image.png") == ".png"

    def test_dot_only(self):
        """Filename that is just a dot should return empty."""
        assert _safe_ext(".") == ""

    def test_double_dot(self):
        """Filename that is double dot should return empty."""
        # os.path.splitext("..") returns ("..", ""), and _safe_ext returns ""
        assert _safe_ext("..") == ""

    def test_extension_with_numbers(self):
        """Extension with numbers should work."""
        assert _safe_ext("file.mp4") == ".mp4"
        assert _safe_ext("file.h264") == ".h264"


class TestIsAllowedContentType:
    """Tests for _is_allowed_content_type validation."""

    def test_image_jpeg(self):
        """image/jpeg should be allowed."""
        assert _is_allowed_content_type("image/jpeg") is True

    def test_image_png(self):
        """image/png should be allowed."""
        assert _is_allowed_content_type("image/png") is True

    def test_image_gif(self):
        """image/gif should be allowed."""
        assert _is_allowed_content_type("image/gif") is True

    def test_image_webp(self):
        """image/webp should be allowed."""
        assert _is_allowed_content_type("image/webp") is True

    def test_video_mp4(self):
        """video/mp4 should be allowed."""
        assert _is_allowed_content_type("video/mp4") is True

    def test_video_quicktime(self):
        """video/quicktime should be allowed."""
        assert _is_allowed_content_type("video/quicktime") is True

    def test_video_webm(self):
        """video/webm should be allowed."""
        assert _is_allowed_content_type("video/webm") is True

    def test_application_pdf_rejected(self):
        """application/pdf should be rejected."""
        assert _is_allowed_content_type("application/pdf") is False

    def test_application_json_rejected(self):
        """application/json should be rejected."""
        assert _is_allowed_content_type("application/json") is False

    def test_text_html_rejected(self):
        """text/html should be rejected."""
        assert _is_allowed_content_type("text/html") is False

    def test_text_plain_rejected(self):
        """text/plain should be rejected."""
        assert _is_allowed_content_type("text/plain") is False

    def test_none_rejected(self):
        """None content type should be rejected."""
        assert _is_allowed_content_type(None) is False

    def test_empty_string_rejected(self):
        """Empty string should be rejected."""
        assert _is_allowed_content_type("") is False

    def test_whitespace_only_rejected(self):
        """Whitespace-only string should be rejected."""
        assert _is_allowed_content_type("   ") is False

    def test_uppercase_image(self):
        """Uppercase content type should be handled (case-insensitive)."""
        assert _is_allowed_content_type("IMAGE/JPEG") is True

    def test_mixed_case(self):
        """Mixed case content type should be handled."""
        assert _is_allowed_content_type("Image/Jpeg") is True

    def test_with_charset_parameter(self):
        """Content type with parameters should work."""
        # Note: current implementation just checks prefix, so this should work
        assert _is_allowed_content_type("image/jpeg; charset=utf-8") is True

    def test_with_whitespace(self):
        """Content type with leading/trailing whitespace should work."""
        assert _is_allowed_content_type("  image/jpeg  ") is True

    def test_application_octet_stream_rejected(self):
        """Generic binary type should be rejected."""
        assert _is_allowed_content_type("application/octet-stream") is False

    def test_multipart_form_data_rejected(self):
        """Multipart form data should be rejected."""
        assert _is_allowed_content_type("multipart/form-data") is False

    def test_image_svg_xml(self):
        """SVG images should be allowed (starts with image/)."""
        assert _is_allowed_content_type("image/svg+xml") is True

    def test_audio_rejected(self):
        """Audio files should be rejected."""
        assert _is_allowed_content_type("audio/mpeg") is False
        assert _is_allowed_content_type("audio/wav") is False


class TestInferContentType:
    """Tests for _infer_content_type fallback logic."""

    def test_valid_provided_content_type_used(self):
        """When valid content_type is provided, use it."""
        assert _infer_content_type("photo.jpg", "image/jpeg") == "image/jpeg"
        assert _infer_content_type("video.mp4", "video/mp4") == "video/mp4"

    def test_infer_from_jpg_extension(self):
        """Infer image/jpeg from .jpg extension when no content_type."""
        assert _infer_content_type("photo.jpg", None) == "image/jpeg"
        assert _infer_content_type("photo.JPG", None) == "image/jpeg"

    def test_infer_from_png_extension(self):
        """Infer image/png from .png extension when no content_type."""
        assert _infer_content_type("image.png", None) == "image/png"

    def test_infer_from_mp4_extension(self):
        """Infer video/mp4 from .mp4 extension when no content_type."""
        assert _infer_content_type("video.mp4", None) == "video/mp4"

    def test_infer_from_mov_extension(self):
        """Infer video/quicktime from .mov extension when no content_type."""
        assert _infer_content_type("video.mov", None) == "video/quicktime"

    def test_infer_when_octet_stream_provided(self):
        """Infer from extension when application/octet-stream is provided."""
        assert _infer_content_type("photo.jpg", "application/octet-stream") == "image/jpeg"
        assert _infer_content_type("video.mp4", "application/octet-stream") == "video/mp4"

    def test_no_filename_returns_provided(self):
        """When no filename, return whatever was provided."""
        assert _infer_content_type(None, "application/octet-stream") == "application/octet-stream"
        assert _infer_content_type(None, None) is None

    def test_unknown_extension_returns_provided(self):
        """Unknown extension returns provided content_type."""
        assert _infer_content_type("data.xyz", "application/octet-stream") == "application/octet-stream"

    def test_non_media_extension_returns_provided(self):
        """Non-media extensions (pdf, txt) don't override."""
        # mimetypes.guess_type returns application/pdf for .pdf
        # but _infer_content_type only uses allowed types
        assert _infer_content_type("doc.pdf", None) is None
        assert _infer_content_type("file.txt", "text/plain") == "text/plain"

    def test_full_path_with_extension(self):
        """Full path should work - extension is extracted."""
        assert _infer_content_type("/home/user/photos/image.png", None) == "image/png"

    def test_empty_content_type_string(self):
        """Empty string content_type should trigger inference."""
        assert _infer_content_type("photo.jpg", "") == "image/jpeg"

    def test_whitespace_content_type(self):
        """Whitespace-only content_type should trigger inference."""
        assert _infer_content_type("photo.jpg", "   ") == "image/jpeg"
