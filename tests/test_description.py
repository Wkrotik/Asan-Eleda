"""Tests for description formatting module."""

import pytest
from core.description import clean_caption, format_appeal_description, enhance_description


class TestCleanCaption:
    """Tests for clean_caption function."""

    def test_removes_photo_prefix(self):
        result = clean_caption("a photo of a pothole in the road")
        assert result == "a pothole in the road"
        assert not result.startswith("a photo of")

    def test_removes_image_prefix(self):
        result = clean_caption("an image of broken sidewalk")
        assert result == "broken sidewalk"

    def test_removes_close_up_prefix(self):
        result = clean_caption("a close up of a crack in the pavement")
        assert result == "a crack in the pavement"

    def test_handles_empty_string(self):
        result = clean_caption("")
        assert result == "an issue"

    def test_handles_none_like_empty(self):
        result = clean_caption("   ")
        assert result == "an issue"

    def test_removes_trailing_punctuation(self):
        result = clean_caption("a photo of a pothole.")
        assert not result.endswith(".")

    def test_preserves_content_without_prefix(self):
        result = clean_caption("pothole in the road")
        assert result == "pothole in the road"


class TestFormatAppealDescription:
    """Tests for format_appeal_description function."""

    def test_basic_formatting(self):
        result = format_appeal_description(
            caption="a photo of a pothole in the road"
        )
        assert "This appeal reports" in result
        assert "pothole in the road" in result
        assert "relevant authorities" in result

    def test_high_priority_template(self):
        result = format_appeal_description(
            caption="a damaged road",
            priority_level="high"
        )
        assert "URGENT" in result
        assert "significant safety hazard" in result
        assert "immediate attention" in result

    def test_medium_priority_template(self):
        result = format_appeal_description(
            caption="a damaged road",
            priority_level="medium"
        )
        assert "timely manner" in result
        assert "URGENT" not in result

    def test_low_priority_template(self):
        result = format_appeal_description(
            caption="minor issue",
            priority_level="low"
        )
        assert "when resources are available" in result

    def test_category_context_road_problems(self):
        result = format_appeal_description(
            caption="pothole",
            category_id="road_problems"
        )
        assert "vehicles and pedestrians" in result

    def test_category_context_utilities(self):
        result = format_appeal_description(
            caption="water leak",
            category_id="utilities"
        )
        assert "essential services" in result

    def test_category_context_cleanliness(self):
        result = format_appeal_description(
            caption="trash",
            category_id="infrastructure_cleanliness"
        )
        assert "cleanliness" in result

    def test_includes_ocr_text(self):
        result = format_appeal_description(
            caption="a sign",
            ocr_text="WARNING: DANGER",
            include_ocr=True
        )
        assert "WARNING: DANGER" in result
        assert "Text visible in image" in result

    def test_excludes_ocr_when_disabled(self):
        result = format_appeal_description(
            caption="a sign",
            ocr_text="WARNING: DANGER",
            include_ocr=False
        )
        assert "WARNING: DANGER" not in result

    def test_truncates_long_ocr_text(self):
        long_ocr = "A" * 300
        result = format_appeal_description(
            caption="a sign",
            ocr_text=long_ocr,
            include_ocr=True
        )
        assert len(result) < len(long_ocr) + 200  # Reasonable length
        assert "..." in result


class TestEnhanceDescription:
    """Tests for enhance_description convenience function."""

    def test_with_categories_and_priority(self):
        categories = [
            {"id": "road_problems", "label": "Road problems", "confidence": 0.85},
        ]
        result = enhance_description(
            raw_caption="a photo of a pothole",
            categories=categories,
            priority_level="high",
        )
        assert "URGENT" in result
        assert "pothole" in result
        assert "vehicles and pedestrians" in result

    def test_empty_categories(self):
        result = enhance_description(
            raw_caption="a photo of something",
            categories=[],
        )
        assert "This appeal reports" in result

    def test_with_ocr_items(self):
        categories = [{"id": "other", "label": "Other", "confidence": 0.5}]
        ocr_items = [
            {"text": "STOP", "confidence": 0.9},
            {"text": "SIGN", "confidence": 0.8},
        ]
        result = enhance_description(
            raw_caption="a sign",
            categories=categories,
            ocr_items=ocr_items,
        )
        assert "STOP" in result
        assert "SIGN" in result

    def test_handles_none_ocr_items(self):
        result = enhance_description(
            raw_caption="a photo",
            categories=[],
            ocr_items=None,
        )
        assert "This appeal reports" in result


class TestDescriptionQuality:
    """Tests for overall description quality."""

    def test_description_is_formal(self):
        """Description should be formal, not casual."""
        result = format_appeal_description(caption="a broken bench")
        # Should not contain casual language
        assert "looks like" not in result.lower()
        assert "i think" not in result.lower()
        # Should have formal structure
        assert "This appeal" in result

    def test_description_is_actionable(self):
        """Description should indicate action is needed."""
        result = format_appeal_description(caption="a pothole")
        assert "attention" in result.lower() or "authorities" in result.lower()

    def test_description_length_is_reasonable(self):
        """Description should not be too short or too long."""
        result = format_appeal_description(caption="a pothole")
        assert len(result) >= 50  # Not too short
        assert len(result) <= 500  # Not too long without OCR
