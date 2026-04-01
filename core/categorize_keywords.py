"""Keyword-based category classification from text descriptions.

This module classifies BLIP-generated descriptions into ASAN categories
by matching keywords. This approach yields higher confidence scores than
direct CLIP image-to-label matching because:

1. BLIP generates concrete visual descriptions ("broken wooden pole with wires")
2. Keywords are specific and visual, not abstract ("pole", "wire" vs "Utilities")
3. Multiple keyword matches boost confidence naturally
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
import math


# Keywords for each ASAN category
# These are visual/descriptive terms that appear in BLIP captions
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "utilities": [
        # Electrical
        "wire", "wires", "cable", "cables", "electricity", "electrical", "power line",
        "power lines", "transformer", "electric pole", "utility pole",
        # Water/Gas/Sewage
        "pipe", "pipes", "water", "leak", "leaking", "gas", "sewage", "sewer",
        "hydrant", "fire hydrant", "manhole",
        # General utility
        "utility", "utilities", "meter", "generator",
    ],
    "road_problems": [
        # Road surface
        "pothole", "potholes", "crack", "cracks", "cracked", "asphalt",
        # Drainage
        "drain", "drainage", "flooded", "flooding", "puddle", "water on road",
        "standing water",
        # Road features
        "curb", "kerb", "manhole", "gutter",
    ],
    "transport_problems": [
        # Traffic infrastructure
        "traffic light", "traffic signal", "stop light", "red light", "green light",
        "traffic sign", "road sign", "stop sign", "yield sign", "sign post",
        # Vehicles / traffic management
        "abandoned car", "abandoned vehicle",
        "parking", "illegal parking",
        # Public transport
        "bus stop", "bus station", "metro", "tram", "train",
    ],
    "infrastructure_repair": [
        # Sidewalks
        "sidewalk", "walkway", "footpath", "pedestrian",
        # Lighting
        "street light", "streetlight", "lamp", "lamp post", "light pole",
        "street lamp", "lantern",
        # Poles and structures
        "pole", "post", "broken pole", "fallen pole", "leaning pole",
        "wooden pole", "metal pole",
        # Buildings/structures
        "fence", "railing", "barrier", "bridge",
        "bench", "broken bench",
        # Construction
        "construction", "repair", "maintenance", "scaffolding",
    ],
    "infrastructure_improvement": [
        # Parks and green spaces
        "park", "garden", "playground", "green space", "lawn", "grass",
        # Trees and vegetation
        "tree", "trees", "branch", "branches", "fallen tree", "dead tree",
        "bush", "bushes", "vegetation", "overgrown", "leaves",
        # Public spaces
        "square", "plaza", "fountain", "statue", "monument",
        # Note: Avoid generic obstruction terms (too broad)
    ],
    "infrastructure_cleanliness": [
        # Trash
        "trash", "garbage", "rubbish", "waste", "litter", "debris",
        "trash can", "trash bin", "dumpster", "bin",
        # Dumping
        "dumped", "dumping", "pile", "heap",
        # Graffiti/vandalism
        "graffiti", "spray paint", "vandalism", "vandalized", "tagged",
        # Furniture
        "mattress", "couch", "sofa", "furniture", "abandoned furniture",
        # General cleanliness (kept minimal; too generic otherwise)
        "dirty street", "dirty area",
    ],
    "other": [
        # Catch-all - low priority keywords
        "other", "unknown", "unclear",
    ],
}

# Optional weights for particularly diagnostic keywords/phrases.
# Defaults to 1.0 when not specified.
KEYWORD_WEIGHTS: dict[str, float] = {
    # Utilities
    "wire": 2.0,
    "wires": 2.0,
    "cable": 2.0,
    "cables": 2.0,
    "electricity": 2.0,
    "electrical": 2.0,
    "power line": 2.0,
    "power lines": 2.0,
    "utility pole": 1.5,
    "pipe": 2.0,
    "pipes": 2.0,
    "gas": 2.0,
    "sewage": 2.0,
    "sewer": 2.0,
    "leak": 2.0,
    "leaking": 2.0,
    "fire hydrant": 2.0,
    "hydrant": 1.5,

    # Roads
    "pothole": 2.0,
    "potholes": 2.0,
    "crack": 1.5,
    "cracks": 1.5,
    "cracked": 1.5,
    "asphalt": 1.5,
    "manhole": 1.5,
    "drain": 1.5,
    "drainage": 1.5,
    "flooded": 1.5,
    "flooding": 1.5,

    # Repair
    "street light": 1.5,
    "lamp post": 1.5,
    "light pole": 1.5,
    "sidewalk": 1.5,
    "broken pole": 1.5,
    "fallen pole": 1.5,
    "leaning pole": 1.5,
    "pole": 1.2,
}


@dataclass
class CategoryMatch:
    """Result of matching a description to a category."""
    category_id: str
    category_label: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)


def normalize_text(text: str) -> str:
    """Normalize text for keyword matching."""
    return text.lower().strip()


def find_keywords_in_text(text: str, keywords: list[str]) -> list[str]:
    """Find which keywords appear in the text."""
    normalized = normalize_text(text)
    matched = []
    for keyword in keywords:
        # Use word boundary matching for single words, substring for phrases
        if " " in keyword:
            # Phrase - simple substring match
            if keyword.lower() in normalized:
                matched.append(keyword)
        else:
            # Single word - word boundary match to avoid partial matches
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            if re.search(pattern, normalized):
                matched.append(keyword)
    return matched


def score_matched_keywords(matched_keywords: list[str]) -> float:
    """Compute a weighted score from matched keywords."""
    s = 0.0
    for kw in matched_keywords:
        s += float(KEYWORD_WEIGHTS.get(kw, 1.0))
    return s


def classify_description(
    description: str,
    categories: list[dict],
    *,
    top_k: int = 3,
    temperature: float = 0.5,
) -> list[CategoryMatch]:
    """Classify a text description into categories based on keyword matching.
    
    Args:
        description: The BLIP-generated description to classify
        categories: List of category dicts with 'id' and 'label' keys
        top_k: Number of top categories to return
        temperature: Softmax temperature over integer match scores. Lower values
            produce peakier confidence scores.
        
    Returns:
        List of CategoryMatch objects sorted by confidence (descending)
    """
    if not description or not categories:
        return []
    
    # Build category lookup
    cat_lookup = {c["id"]: c.get("label", c["id"]) for c in categories}
    
    # Score each category
    scores: list[tuple[str, str, float, list[str]]] = []
    
    for cat_id, cat_label in cat_lookup.items():
        keywords = CATEGORY_KEYWORDS.get(cat_id, [])
        matched = find_keywords_in_text(description, keywords)
        score = score_matched_keywords(matched)
        scores.append((cat_id, cat_label, score, matched))
    
    # Sort by score descending (stable tie-breaker by category id)
    scores.sort(key=lambda x: (-x[2], x[0]))

    # Convert integer scores to confidence via softmax.
    # If nothing matches, bias toward "other".
    ids = [s[0] for s in scores]
    raw = [float(s[2]) for s in scores]
    t = max(1e-6, float(temperature))
    m = max(raw) if raw else 0.0

    if m <= 0.0:
        n = max(1, len(raw))
        other_idx = ids.index("other") if "other" in ids else 0
        probs = [0.5 / float(n - 1) for _ in range(n)] if n > 1 else [1.0]
        if n > 1:
            probs[other_idx] = 0.5
    else:
        exps = [math.exp((r - m) / t) for r in raw]
        z = float(sum(exps))
        probs = [float(e / z) for e in exps] if z > 0.0 else [1.0 / float(len(exps)) for _ in exps]

    # Return top_k by probability (not just raw score)
    combined = list(zip(scores, probs))
    combined.sort(key=lambda x: float(x[1]), reverse=True)

    out: list[CategoryMatch] = []
    for (cat_id, cat_label, _score, matched), p in combined[: max(1, int(top_k))]:
        out.append(
            CategoryMatch(
                category_id=cat_id,
                category_label=cat_label,
                confidence=round(float(p), 3),
                matched_keywords=matched,
            )
        )

    return out


class KeywordCategorizer:
    """Categorizer that uses keyword matching on text descriptions."""
    
    def __init__(self, *, categories: list[dict] | None = None):
        self.categories = categories or []
    
    def set_categories(self, categories: list[dict]) -> None:
        """Update the category list."""
        self.categories = categories
    
    def classify(
        self,
        description: str,
        *,
        top_k: int = 3,
    ) -> list[dict]:
        """Classify a description into categories.
        
        Args:
            description: Text description to classify
            top_k: Number of top results to return
            
        Returns:
            List of dicts with 'id', 'label', 'confidence' keys
        """
        matches = classify_description(
            description,
            self.categories,
            top_k=top_k,
        )
        
        return [
            {
                "id": m.category_id,
                "label": m.category_label,
                "confidence": m.confidence,
            }
            for m in matches
        ]
    
    def classify_with_debug(
        self,
        description: str,
        *,
        top_k: int = 3,
    ) -> tuple[list[dict], dict]:
        """Classify with debug information about matched keywords."""
        matches = classify_description(
            description,
            self.categories,
            top_k=top_k,
        )
        
        results = [
            {
                "id": m.category_id,
                "label": m.category_label,
                "confidence": m.confidence,
            }
            for m in matches
        ]
        
        debug = {
            "description": description,
            "matches": [
                {
                    "category": m.category_id,
                    "keywords_matched": m.matched_keywords,
                    "match_count": len(m.matched_keywords),
                }
                for m in matches
            ],
        }
        
        return results, debug
