from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class MockAnalyze:
    description: str
    tags: list[str]
    ocr: list[dict]


class MockCaptioner:
    def caption(self, *, sha256: str) -> tuple[str, list[str]]:
        # Deterministic placeholder text for demo wiring.
        desc = "A submitted image/video showing a public issue that may require municipal action."
        tags = ["public_space", "issue_report", "mvp"]
        if sha256.endswith("0") or sha256.endswith("1"):
            tags.append("roads")
        return desc, tags


class MockOcr:
    def extract(self, *, sha256: str) -> list[dict]:
        # No OCR by default; keep shape stable.
        if sha256.endswith("f"):
            return [{"text": "STOP", "confidence": 0.55, "bbox": None}]
        return []


class MockEmbedder:
    def embed(self, *, sha256: str) -> list[float]:
        # Produce a stable pseudo-embedding.
        h = hashlib.sha256(sha256.encode("utf-8")).digest()
        # 16-dim float-ish values in [0, 1]
        return [b / 255.0 for b in h[:16]]


class MockCategorizer:
    def top_k(self, *, categories: list[dict], top_k: int, sha256: str) -> list[dict]:
        # Deterministic selection based on hash suffix.
        if not categories:
            return []
        idx = int(sha256[-2:], 16) % len(categories)
        ordered = categories[idx:] + categories[:idx]
        out = []
        for i, c in enumerate(ordered[: max(top_k, 1)]):
            out.append(
                {
                    "id": str(c.get("id")),
                    "label": str(c.get("label", c.get("id"))),
                    "confidence": max(0.1, 0.85 - 0.15 * i),
                }
            )
        return out


class MockVerifier:
    def same_location(self, *, before_sha256: str, after_sha256: str) -> tuple[float, str]:
        # High score if hash prefixes match.
        common = 0
        for a, b in zip(before_sha256, after_sha256):
            if a != b:
                break
            common += 1
        score = min(1.0, common / 20.0)
        rationale = "Similarity estimated from deterministic embedding placeholder."
        return score, rationale

    def resolved(self, *, same_location_score: float) -> tuple[float, str]:
        # Conservative: resolved score capped by same-location score.
        score = max(0.0, min(1.0, same_location_score - 0.15))
        rationale = "Resolution estimated conservatively; requires strong same-location evidence."
        return score, rationale
