"""Tests for title generation module."""

import pytest
from core.title import extract_key_issue, generate_title, generate_title_from_analysis


class TestExtractKeyIssue:
    """Tests for extract_key_issue function."""

    def test_pothole_detected(self):
        caption = "a photo of a pothole in the road"
        result = extract_key_issue(caption)
        assert result == "Pothole"

    def test_road_crack_detected(self):
        caption = "a photo of cracked asphalt on the street"
        result = extract_key_issue(caption)
        assert result == "Cracked surface"

    def test_trash_detected(self):
        caption = "garbage overflowing from bin"
        result = extract_key_issue(caption)
        assert result == "Garbage issue"

    def test_graffiti_detected(self):
        caption = "graffiti on a wall"
        result = extract_key_issue(caption)
        assert result == "Graffiti"

    def test_tree_detected(self):
        caption = "a fallen tree blocking the sidewalk"
        result = extract_key_issue(caption)
        assert result == "Tree issue"

    def test_flood_detected(self):
        caption = "flooded street with standing water"
        result = extract_key_issue(caption)
        assert result == "Flooding"

    def test_street_light_detected(self):
        caption = "broken street light not working"
        result = extract_key_issue(caption)
        assert result == "Street light issue"

    def test_ocr_text_helps_detection(self):
        caption = "a photo of an urban scene"
        ocr_text = "DANGER pothole ahead"
        result = extract_key_issue(caption, ocr_text)
        assert result == "Pothole"

    def test_empty_caption_returns_empty(self):
        result = extract_key_issue("")
        assert result == ""

    def test_fallback_extracts_first_words(self):
        caption = "a photo of an unknown urban issue"
        result = extract_key_issue(caption)
        assert result  # Should return something from the caption
        assert len(result) > 0

    def test_removes_blip_prefix(self):
        caption = "a photo of some random cityscape view"
        result = extract_key_issue(caption)
        assert not result.startswith("a photo of")


class TestGenerateTitle:
    """Tests for generate_title function."""

    def test_basic_title(self):
        result = generate_title(
            category_label="Road problems",
            caption="a photo of a pothole in the road",
        )
        assert result == "Road problems - Pothole"

    def test_title_with_category_and_issue(self):
        result = generate_title(
            category_label="Infrastructure cleanliness",
            caption="graffiti on a wall",
        )
        assert result == "Infrastructure cleanliness - Graffiti"

    def test_title_with_location(self):
        result = generate_title(
            category_label="Road problems",
            caption="pothole",
            location="Main Street",
        )
        assert result == "Road problems - Pothole at Main Street"

    def test_title_truncation(self):
        result = generate_title(
            category_label="Infrastructure improvement and landscaping",
            caption="overgrown vegetation blocking the entire sidewalk area",
            max_length=50,
        )
        assert len(result) <= 50
        assert result.endswith("...")

    def test_empty_category_defaults_to_issue(self):
        result = generate_title(
            category_label="",
            caption="pothole",
        )
        assert result.startswith("Issue")

    def test_empty_caption_defaults_to_issue_reported(self):
        result = generate_title(
            category_label="Road problems",
            caption="",
        )
        assert result == "Road problems - Issue reported"

    def test_location_not_added_if_too_long(self):
        result = generate_title(
            category_label="Infrastructure improvement",
            caption="overgrown vegetation",
            location="Very Long Street Name That Would Make Title Too Long",
            max_length=50,
        )
        assert "Very Long Street" not in result


class TestGenerateTitleFromAnalysis:
    """Tests for generate_title_from_analysis function."""

    def test_with_categories(self):
        categories = [
            {"id": "road_problems", "label": "Road problems", "confidence": 0.85},
            {"id": "other", "label": "Other", "confidence": 0.15},
        ]
        result = generate_title_from_analysis(
            categories=categories,
            caption="a photo of a pothole",
        )
        assert result.startswith("Road problems")
        assert "Pothole" in result

    def test_empty_categories(self):
        result = generate_title_from_analysis(
            categories=[],
            caption="pothole in the street",
        )
        assert result.startswith("Issue")

    def test_with_ocr_text(self):
        categories = [{"id": "utilities", "label": "Utilities", "confidence": 0.7}]
        result = generate_title_from_analysis(
            categories=categories,
            caption="a photo of pipes",
            ocr_text="WARNING: water leak",
        )
        assert "Utilities" in result
        # OCR should help detect "water leak" (matched as multi-word pattern)
        assert "Water leak" in result or "Leak" in result

    def test_with_gps_no_location_in_title(self):
        # GPS is available but we don't include raw coords in title (needs reverse geocoding)
        categories = [{"id": "road_problems", "label": "Road problems", "confidence": 0.8}]
        result = generate_title_from_analysis(
            categories=categories,
            caption="pothole",
            gps={"lat": 40.4093, "lon": 49.8671},
        )
        # Title should not contain raw coordinates
        assert "40.4" not in result
        assert "49.8" not in result


class TestIssueKeywordCoverage:
    """Tests to ensure all major issue types are covered."""

    @pytest.mark.parametrize("keyword,expected", [
        ("pothole", "Pothole"),
        ("crack", "Cracked surface"),
        ("manhole", "Manhole issue"),
        ("flood", "Flooding"),
        ("water", "Water issue"),
        ("leak", "Leak"),
        ("drain", "Drainage problem"),
        ("street light", "Street light issue"),
        ("traffic light", "Traffic light issue"),
        ("trash", "Trash issue"),
        ("garbage", "Garbage issue"),
        ("graffiti", "Graffiti"),
        ("tree", "Tree issue"),
        ("sidewalk", "Sidewalk issue"),
        ("construction", "Construction hazard"),
        ("abandoned", "Abandoned item"),
    ])
    def test_keyword_extraction(self, keyword, expected):
        caption = f"a photo of {keyword} in the city"
        result = extract_key_issue(caption)
        assert result == expected
