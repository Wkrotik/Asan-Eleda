"""
Title Generation Module

Generates suggested titles for citizen appeals based on:
- Detected category
- BLIP-generated caption/description
- OCR extracted text (optional)
- GPS location (optional)

Title format: "[Category] - [Key Issue]"
Example: "Road problems - Pothole on main street"
"""

from __future__ import annotations

from typing import Optional


# Issue keywords mapped to concise descriptions for title generation
# These help extract the key issue from verbose BLIP captions
# IMPORTANT: Order matters! More specific keywords should come before general ones
# (e.g., "manhole" before "hole", "street light" before "light")
ISSUE_KEYWORDS = [
    # Multi-word patterns (check first)
    ("street light", "Street light issue"),
    ("traffic light", "Traffic light issue"),
    ("traffic signal", "Traffic signal issue"),
    ("road sign", "Road sign issue"),
    ("light out", "Light out"),
    ("broken road", "Broken road"),
    ("damaged road", "Damaged road"),
    ("road damage", "Road damage"),
    ("water leak", "Water leak"),
    ("water main", "Water main issue"),
    
    # Single-word patterns (check after multi-word)
    # Road issues - specific first
    ("pothole", "Pothole"),
    ("manhole", "Manhole issue"),
    ("crack", "Cracked surface"),
    ("asphalt", "Asphalt damage"),
    ("hole in", "Hole in road"),  # After manhole/pothole
    
    # Water/drainage
    ("flood", "Flooding"),
    ("leak", "Leak"),
    ("drain", "Drainage problem"),
    ("sewage", "Sewage issue"),
    ("pipe", "Pipe problem"),
    ("water", "Water issue"),
    
    # Lighting
    ("lamp", "Lamp post issue"),
    ("dark", "Lighting issue"),
    
    # Traffic
    ("sign", "Sign issue"),
    
    # Trash/cleanliness
    ("trash", "Trash issue"),
    ("garbage", "Garbage issue"),
    ("litter", "Litter"),
    ("dump", "Illegal dumping"),
    ("overflowing", "Overflowing bin"),
    ("graffiti", "Graffiti"),
    
    # Vegetation
    ("tree", "Tree issue"),
    ("branch", "Fallen branch"),
    ("overgrown", "Overgrown vegetation"),
    ("bush", "Overgrown bush"),
    ("weed", "Overgrown weeds"),
    
    # Infrastructure
    ("sidewalk", "Sidewalk issue"),
    ("pavement", "Pavement issue"),
    ("bench", "Damaged bench"),
    ("fence", "Fence issue"),
    ("railing", "Railing issue"),
    ("construction", "Construction hazard"),
    ("curb", "Curb damage"),
    
    # Vehicles
    ("abandoned", "Abandoned item"),
    ("vehicle", "Vehicle issue"),
    ("car", "Abandoned vehicle"),
    ("parking", "Parking issue"),
    
    # General (check last)
    ("damage", "Damage"),
    ("broken", "Broken fixture"),
    ("hazard", "Hazard"),
    ("obstruction", "Obstruction"),
]


def extract_key_issue(caption: str, ocr_text: str = "") -> str:
    """
    Extract the most relevant issue phrase from caption and OCR text.
    Returns a concise issue description for the title.
    """
    if not caption:
        return ""
    
    combined = (caption + " " + ocr_text).lower()
    
    # Check for known issue keywords (order matters!)
    for keyword, issue_name in ISSUE_KEYWORDS:
        if keyword in combined:
            return issue_name
    
    # Fallback: extract first noun phrase from caption
    # Simple heuristic: take first 3-5 meaningful words after "a photo of"
    cleaned = caption.lower()
    
    # Remove common BLIP prefixes
    prefixes = [
        "a photo of ",
        "an image of ",
        "a picture of ",
        "a photograph of ",
        "this is ",
        "there is ",
    ]
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    
    # Take first meaningful part (up to 6 words)
    words = cleaned.split()[:6]
    if words:
        # Capitalize first letter
        result = " ".join(words)
        return result.capitalize()
    
    return "Issue reported"


def generate_title(
    *,
    category_label: str,
    caption: str = "",
    ocr_text: str = "",
    location: Optional[str] = None,
    max_length: int = 80,
) -> str:
    """
    Generate a suggested title for the appeal.
    
    Format: "[Category] - [Key Issue]"
    With location: "[Category] - [Key Issue] at [Location]"
    
    Args:
        category_label: The detected category label (e.g., "Road problems")
        caption: BLIP-generated image description
        ocr_text: Text extracted via OCR (optional)
        location: Location string if available (optional)
        max_length: Maximum title length
    
    Returns:
        Generated title string
    """
    if not category_label:
        category_label = "Issue"
    
    # Extract key issue from caption
    key_issue = extract_key_issue(caption, ocr_text)
    
    if key_issue:
        title = f"{category_label} - {key_issue}"
    else:
        title = f"{category_label} - Issue reported"
    
    # Add location if provided and fits
    if location:
        location_suffix = f" at {location}"
        if len(title) + len(location_suffix) <= max_length:
            title += location_suffix
    
    # Truncate if too long
    if len(title) > max_length:
        title = title[:max_length - 3].rstrip() + "..."
    
    return title


def generate_title_from_analysis(
    *,
    categories: list[dict],
    caption: str = "",
    ocr_text: str = "",
    gps: Optional[dict] = None,
) -> str:
    """
    Convenience function to generate title from analysis results.
    
    Args:
        categories: List of category candidates [{"id": ..., "label": ..., "confidence": ...}]
        caption: BLIP-generated description
        ocr_text: Combined OCR text
        gps: GPS coordinates dict {"lat": ..., "lon": ...} (optional)
    
    Returns:
        Generated title string
    """
    # Get top category label
    category_label = "Issue"
    if categories:
        category_label = categories[0].get("label", "Issue")
    
    # Format location from GPS if available
    location = None
    if gps and gps.get("lat") is not None and gps.get("lon") is not None:
        # Note: In production, this could be reverse geocoded to a street address
        # For now, we don't include raw GPS in the title
        pass
    
    return generate_title(
        category_label=category_label,
        caption=caption,
        ocr_text=ocr_text,
        location=location,
    )
