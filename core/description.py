"""
Description Formatting Module

Transforms BLIP-generated captions into formal appeal descriptions
suitable for citizen submissions to government agencies.

The goal is to convert:
  "a photo of a pothole in the road"
  
Into a more formal appeal-style description:
  "This appeal reports a pothole observed in the road. The issue requires 
   attention from the relevant authorities."
"""

from __future__ import annotations

from typing import Optional


# Templates for different issue severities
APPEAL_TEMPLATES = {
    "high": (
        "URGENT: This appeal reports {issue_description}. "
        "This issue poses a significant safety hazard and requires immediate attention from the relevant authorities."
    ),
    "medium": (
        "This appeal reports {issue_description}. "
        "The issue requires attention from the relevant authorities in a timely manner."
    ),
    "low": (
        "This appeal reports {issue_description}. "
        "The issue should be addressed when resources are available."
    ),
    "default": (
        "This appeal reports {issue_description}. "
        "The issue requires attention from the relevant authorities."
    ),
}

# Category-specific additional context
CATEGORY_CONTEXT = {
    "utilities": "This may affect essential services for residents in the area.",
    "road_problems": "This may pose risks to vehicles and pedestrians.",
    "transport_problems": "This may affect traffic flow and public safety.",
    "infrastructure_repair": "This affects public infrastructure that requires maintenance.",
    "infrastructure_improvement": "This area could benefit from improvement or landscaping work.",
    "infrastructure_cleanliness": "This affects the cleanliness and appearance of public spaces.",
    "other": "",
}


def clean_caption(caption: str) -> str:
    """
    Clean BLIP caption by removing common prefixes and normalizing.
    
    Args:
        caption: Raw BLIP-generated caption
    
    Returns:
        Cleaned caption suitable for inclusion in appeal
    """
    if not caption:
        return "an issue"
    
    cleaned = caption.strip().lower()
    
    # Remove common BLIP prefixes
    prefixes = [
        "a photo of ",
        "an image of ",
        "a picture of ",
        "a photograph of ",
        "a close up of ",
        "a closeup of ",
        "this is ",
        "there is ",
        "image shows ",
        "photo shows ",
    ]
    
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    
    # Remove trailing punctuation
    cleaned = cleaned.rstrip(".,;:")
    
    # Ensure it doesn't start with articles if we removed a prefix
    # (e.g., avoid "a a pothole")
    if cleaned.startswith("a ") or cleaned.startswith("an "):
        pass  # Keep the article
    
    return cleaned if cleaned else "an issue"


def format_appeal_description(
    *,
    caption: str,
    category_id: str = "",
    priority_level: str = "",
    ocr_text: str = "",
    include_ocr: bool = True,
) -> str:
    """
    Format a BLIP caption into a formal appeal description.
    
    Args:
        caption: Raw BLIP-generated caption
        category_id: Category ID for context (e.g., "road_problems")
        priority_level: Priority level (high, medium, low)
        ocr_text: OCR-extracted text from the image
        include_ocr: Whether to include OCR text in description
    
    Returns:
        Formatted appeal description
    """
    # Clean the caption
    issue_description = clean_caption(caption)
    
    # Select appropriate template based on priority
    priority = priority_level.lower() if priority_level else "default"
    template = APPEAL_TEMPLATES.get(priority, APPEAL_TEMPLATES["default"])
    
    # Format the main description
    description = template.format(issue_description=issue_description)
    
    # Add category-specific context if available
    context = CATEGORY_CONTEXT.get(category_id, "")
    if context:
        description += f" {context}"
    
    # Add OCR text if present and requested
    if include_ocr and ocr_text and ocr_text.strip():
        ocr_clean = ocr_text.strip()
        if len(ocr_clean) > 200:
            ocr_clean = ocr_clean[:197] + "..."
        description += f' Text visible in image: "{ocr_clean}"'
    
    return description


def enhance_description(
    *,
    raw_caption: str,
    categories: list[dict],
    priority_level: str = "",
    ocr_items: list[dict] = None,
) -> str:
    """
    Convenience function to enhance a raw caption into an appeal description.
    
    Args:
        raw_caption: Raw BLIP-generated caption
        categories: List of category candidates
        priority_level: Priority level string
        ocr_items: List of OCR items [{"text": ..., "confidence": ...}]
    
    Returns:
        Enhanced appeal description
    """
    # Get top category ID
    category_id = ""
    if categories:
        category_id = categories[0].get("id", "")
    
    # Combine OCR text
    ocr_text = ""
    if ocr_items:
        texts = [str(item.get("text", "")).strip() for item in ocr_items if isinstance(item, dict)]
        ocr_text = " ".join(t for t in texts if t)
    
    return format_appeal_description(
        caption=raw_caption,
        category_id=category_id,
        priority_level=priority_level,
        ocr_text=ocr_text,
    )
