from __future__ import annotations

from dataclasses import dataclass

from core.engines.openclip import (
    cosine_similarity,
    expand_category_prompts,
    get_openclip_context,
    load_image,
)
from core.media import MediaRef


@dataclass
class OpenClipEmbedder:
    model_name: str = "ViT-B-32"
    pretrained: str = "laion2b_s34b_b79k"
    device: str | None = None

    def embed(self, *, media: MediaRef) -> list[float]:
        ctx = get_openclip_context(self.model_name, self.pretrained, self.device)
        im = load_image(media.path)
        vec = ctx.encode_image(im)
        return [float(x) for x in vec.tolist()]


class OpenClipZeroShotCategorizer:
    def __init__(self, *, model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k", device: str | None = None):
        self.model_name = model_name
        self.pretrained = pretrained
        self.device = device
        self._cache_key: tuple[int, int] | None = None
        self._text_feats = None
        self._mapping: list[tuple[str, str]] = []
        self._texts: list[str] = []

    def _ensure_text_features(self, *, categories: list[dict]) -> None:
        ctx = get_openclip_context(self.model_name, self.pretrained, self.device)
        texts, mapping = expand_category_prompts(categories)
        feats = ctx.encode_texts(texts)
        self._text_feats = feats
        self._mapping = mapping
        self._texts = texts

    def top_k(self, *, categories: list[dict], top_k: int, media: MediaRef) -> list[dict]:
        if not categories:
            return []
        if self._text_feats is None or len(self._mapping) == 0:
            self._ensure_text_features(categories=categories)

        ctx = get_openclip_context(self.model_name, self.pretrained, self.device)
        im = load_image(media.path)
        img_feat = ctx.encode_image(im)

        # Compute similarity to each prompt text, then pool per category by max.
        text_feats = self._text_feats
        sims = (text_feats @ img_feat).tolist()  # cosine similarity since both normalized

        pooled: dict[str, dict] = {}
        for sim, (cid, label) in zip(sims, self._mapping):
            cur = pooled.get(cid)
            if cur is None or sim > cur["_best"]:
                pooled[cid] = {"id": cid, "label": label, "_best": float(sim)}

        ranked = sorted(pooled.values(), key=lambda x: x["_best"], reverse=True)

        # Convert similarity [-1,1] to a pseudo-confidence [0,1] for MVP.
        out = []
        for item in ranked[: max(top_k, 1)]:
            s = float(item["_best"])
            conf = max(0.0, min(1.0, (s + 1.0) / 2.0))
            out.append({"id": item["id"], "label": item["label"], "confidence": conf})
        return out

    def top_k_debug(self, *, categories: list[dict], top_k: int, media: MediaRef) -> tuple[list[dict], dict]:
        """Return (top_k, debug) where debug includes best prompt per category."""
        if not categories:
            return [], {"prompts": [], "per_category": {}}
        if self._text_feats is None or len(self._mapping) == 0:
            self._ensure_text_features(categories=categories)

        ctx = get_openclip_context(self.model_name, self.pretrained, self.device)
        im = load_image(media.path)
        img_feat = ctx.encode_image(im)

        text_feats = self._text_feats
        sims = (text_feats @ img_feat).tolist()

        pooled: dict[str, dict] = {}
        per_cat: dict[str, dict] = {}
        for idx, (sim, (cid, label)) in enumerate(zip(sims, self._mapping)):
            s = float(sim)
            cur = pooled.get(cid)
            if cur is None or s > float(cur["_best"]):
                pooled[cid] = {"id": cid, "label": label, "_best": s, "_prompt_index": idx}
        ranked = sorted(pooled.values(), key=lambda x: float(x["_best"]), reverse=True)

        out = []
        for item in ranked[: max(top_k, 1)]:
            s = float(item["_best"])
            conf = max(0.0, min(1.0, (s + 1.0) / 2.0))
            out.append({"id": item["id"], "label": item["label"], "confidence": conf})
            idx = int(item["_prompt_index"])
            per_cat[item["id"]] = {
                "best_prompt_index": idx,
                "best_prompt_text": self._texts[idx] if 0 <= idx < len(self._texts) else None,
                "best_prompt_similarity": s,
                "best_prompt_confidence": conf,
            }

        debug = {
            "model": {"name": self.model_name, "pretrained": self.pretrained},
            "prompts_count": len(self._mapping),
            "per_category": per_cat,
        }
        return out, debug


class OpenClipSimilarityVerifier:
    def __init__(self, *, model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k", device: str | None = None):
        self.model_name = model_name
        self.pretrained = pretrained
        self.device = device

    def same_location(self, *, before: MediaRef, after: MediaRef) -> tuple[float, str]:
        ctx = get_openclip_context(self.model_name, self.pretrained, self.device)
        v1 = ctx.encode_image(load_image(before.path))
        v2 = ctx.encode_image(load_image(after.path))
        sim = float((v1 @ v2).item())
        score = max(0.0, min(1.0, (sim + 1.0) / 2.0))
        return score, "Image similarity via OpenCLIP embeddings."

    def resolved(self, *, same_location_score: float) -> tuple[float, str]:
        # Still conservative: without task-specific detectors, resolution cannot be asserted strongly.
        score = max(0.0, min(1.0, same_location_score - 0.25))
        return score, "Resolution is conservative and derived from same-location confidence (no domain detector yet)."
