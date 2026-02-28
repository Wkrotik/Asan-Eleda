"""Unit tests for core/video.py functions."""
from __future__ import annotations

from pathlib import Path
import pytest

from core.video import is_video_path, _parse_iso6709


class TestIsVideoPath:
    """Tests for is_video_path extension detection."""

    def test_mp4_lowercase(self):
        """MP4 files should be detected as video."""
        assert is_video_path(Path("test.mp4")) is True

    def test_mp4_uppercase(self):
        """MP4 with uppercase extension should be detected."""
        assert is_video_path(Path("test.MP4")) is True

    def test_mov_file(self):
        """MOV files should be detected as video."""
        assert is_video_path(Path("test.mov")) is True

    def test_mkv_file(self):
        """MKV files should be detected as video."""
        assert is_video_path(Path("test.mkv")) is True

    def test_avi_file(self):
        """AVI files should be detected as video."""
        assert is_video_path(Path("test.avi")) is True

    def test_webm_file(self):
        """WebM files should be detected as video."""
        assert is_video_path(Path("test.webm")) is True

    def test_m4v_file(self):
        """M4V files should be detected as video."""
        assert is_video_path(Path("test.m4v")) is True

    def test_jpg_not_video(self):
        """JPG files should not be detected as video."""
        assert is_video_path(Path("photo.jpg")) is False

    def test_png_not_video(self):
        """PNG files should not be detected as video."""
        assert is_video_path(Path("image.png")) is False

    def test_no_extension(self):
        """Files without extension should not be detected as video."""
        assert is_video_path(Path("noextension")) is False

    def test_hidden_file(self):
        """Hidden files (starting with .) should be handled correctly."""
        assert is_video_path(Path(".hidden.mp4")) is True
        assert is_video_path(Path(".hidden")) is False

    def test_multiple_dots(self):
        """Files with multiple dots should use the last extension."""
        assert is_video_path(Path("my.video.file.mp4")) is True
        assert is_video_path(Path("my.mp4.jpg")) is False

    def test_path_with_directory(self):
        """Full paths should work correctly."""
        assert is_video_path(Path("/home/user/videos/test.mp4")) is True
        assert is_video_path(Path("/home/user/images/test.jpg")) is False


class TestParseIso6709:
    """Tests for _parse_iso6709 GPS coordinate parsing."""

    def test_standard_format(self):
        """Standard ISO 6709 format should parse correctly."""
        result = _parse_iso6709("+40.4096+049.8671/")
        assert result is not None
        lat, lon = result
        assert abs(lat - 40.4096) < 0.0001
        assert abs(lon - 49.8671) < 0.0001

    def test_with_altitude(self):
        """ISO 6709 with altitude component should parse lat/lon correctly."""
        result = _parse_iso6709("+40.4096+049.8671+012.3/")
        assert result is not None
        lat, lon = result
        assert abs(lat - 40.4096) < 0.0001
        assert abs(lon - 49.8671) < 0.0001

    def test_negative_latitude(self):
        """Negative latitude (southern hemisphere) should parse correctly."""
        result = _parse_iso6709("-34.5678+151.1234/")
        assert result is not None
        lat, lon = result
        assert abs(lat - (-34.5678)) < 0.0001
        assert abs(lon - 151.1234) < 0.0001

    def test_negative_longitude(self):
        """Negative longitude (western hemisphere) should parse correctly."""
        result = _parse_iso6709("+40.7128-074.0060/")
        assert result is not None
        lat, lon = result
        assert abs(lat - 40.7128) < 0.0001
        assert abs(lon - (-74.0060)) < 0.0001

    def test_both_negative(self):
        """Both negative coordinates (SW hemisphere) should parse correctly."""
        result = _parse_iso6709("-34.6037-058.3816/")
        assert result is not None
        lat, lon = result
        assert abs(lat - (-34.6037)) < 0.0001
        assert abs(lon - (-58.3816)) < 0.0001

    def test_missing_trailing_slash(self):
        """Missing trailing slash should return None."""
        result = _parse_iso6709("+40.4096+049.8671")
        assert result is None

    def test_empty_string(self):
        """Empty string should return None."""
        result = _parse_iso6709("")
        assert result is None

    def test_only_slash(self):
        """Just a slash should return None."""
        result = _parse_iso6709("/")
        assert result is None

    def test_whitespace_handling(self):
        """Leading/trailing whitespace should be handled."""
        result = _parse_iso6709("  +40.4096+049.8671/  ")
        assert result is not None
        lat, lon = result
        assert abs(lat - 40.4096) < 0.0001

    def test_invalid_format(self):
        """Invalid format should return None."""
        result = _parse_iso6709("invalid/")
        assert result is None

    def test_single_coordinate(self):
        """Single coordinate (no longitude) should return None."""
        result = _parse_iso6709("+40.4096/")
        assert result is None

    def test_zero_coordinates(self):
        """Zero coordinates (null island) should parse correctly."""
        result = _parse_iso6709("+00.0000+000.0000/")
        assert result is not None
        lat, lon = result
        assert lat == 0.0
        assert lon == 0.0

    def test_high_precision(self):
        """High precision coordinates should parse correctly."""
        result = _parse_iso6709("+40.409312345+049.867156789/")
        assert result is not None
        lat, lon = result
        assert abs(lat - 40.409312345) < 0.0000001
        assert abs(lon - 49.867156789) < 0.0000001
