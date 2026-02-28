from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable


def _require_openclip():
    try:
        import open_clip  # type: ignore
        import torch  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "OpenCLIP engine requires optional deps. Install with: pip install -r requirements-ml.txt"
        ) from e
    return open_clip, torch, Image


@dataclass
class OpenClipContext:
    model_name: str
    pretrained: str
    device: str

    def __post_init__(self) -> None:
        open_clip, torch, _ = _require_openclip()
        model, _, preprocess = open_clip.create_model_and_transforms(self.model_name, pretrained=self.pretrained)
        model.eval()
        self._torch = torch
        self._open_clip = open_clip
        self.model = model.to(self.device)
        self.preprocess = preprocess
        self.tokenizer = open_clip.get_tokenizer(self.model_name)

    def encode_image(self, pil_image):
        torch = self._torch
        with torch.no_grad():
            x = self.preprocess(pil_image).unsqueeze(0).to(self.device)
            feat = self.model.encode_image(x)
            feat = feat / feat.norm(dim=-1, keepdim=True)
            return feat.squeeze(0).float().cpu()

    def encode_texts(self, texts: list[str]):
        torch = self._torch
        tokens = self.tokenizer(texts)
        with torch.no_grad():
            t = tokens.to(self.device)
            feat = self.model.encode_text(t)
            feat = feat / feat.norm(dim=-1, keepdim=True)
            return feat.float().cpu()


def _default_device() -> str:
    _, torch, _ = _require_openclip()
    return "cuda" if torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=4)
def get_openclip_context(
    model_name: str = "ViT-B-32",
    pretrained: str = "laion2b_s34b_b79k",
    device: str | None = None,
    cache_dir: str | None = None,
) -> OpenClipContext:
    # We create the context with a model already loaded; open_clip handles caching.
    # cache_dir is passed through via OpenClipContext post-init by re-calling create_model...
    ctx = OpenClipContext(model_name=model_name, pretrained=pretrained, device=device or _default_device())
    # NOTE: open_clip.create_model_and_transforms supports cache_dir, but OpenClipContext currently
    # uses defaults. We keep cache prefetch in scripts/warmup_openclip.py.
    _ = cache_dir
    return ctx


def load_image(path):
    _, _, Image = _require_openclip()
    im = Image.open(path)
    im_rgb = im.convert("RGB")
    # Load pixel data into memory so we can close the file handle
    im_rgb.load()
    im.close()
    return im_rgb


def cosine_similarity(vec_a, vec_b) -> float:
    # vec_a/vec_b are 1D torch CPU tensors; keep function import-light.
    import math

    a = vec_a.tolist()
    b = vec_b.tolist()
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(dot / (na * nb))


def build_label_texts(category: dict) -> list[str]:
    label = str(category.get("label") or category.get("id") or "")
    syn = category.get("synonyms") or []
    texts = [label]
    for s in syn:
        s = str(s).strip()
        if s and s.lower() not in {t.lower() for t in texts}:
            texts.append(s)
    return texts


def expand_category_prompts(categories: Iterable[dict]) -> tuple[list[str], list[tuple[str, str]]]:
    """Return (texts, mapping) where mapping[i] = (category_id, display_label)."""
    texts: list[str] = []
    mapping: list[tuple[str, str]] = []
    for c in categories:
        cid = str(c.get("id"))
        label = str(c.get("label", cid))
        for t in build_label_texts(c):
            # Simple prompt wrapper improves zero-shot stability.
            texts.append(f"a photo of {t}")
            mapping.append((cid, label))
    return texts, mapping
