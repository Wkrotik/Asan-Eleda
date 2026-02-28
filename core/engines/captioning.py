from __future__ import annotations

from dataclasses import dataclass

from core.media import MediaRef


def _require_transformers():
    try:
        import torch  # type: ignore
        from PIL import Image  # type: ignore
        from transformers import BlipForConditionalGeneration, BlipProcessor  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Captioning engine requires optional deps. Install with: pip install -r requirements-ml.txt"
        ) from e
    return torch, Image, BlipForConditionalGeneration, BlipProcessor


@dataclass
class BlipCaptioner:
    model_id: str = "Salesforce/blip-image-captioning-base"
    max_new_tokens: int = 40
    device: str | None = None
    cache_dir: str | None = None

    def __post_init__(self) -> None:
        torch, _, BlipForConditionalGeneration, BlipProcessor = _require_transformers()
        self._torch = torch
        self.processor = BlipProcessor.from_pretrained(self.model_id, cache_dir=self.cache_dir)
        self.model = BlipForConditionalGeneration.from_pretrained(self.model_id, cache_dir=self.cache_dir)

        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        self.model.eval()

    def caption(self, *, media: MediaRef) -> tuple[str, list[str]]:
        torch, Image, _, _ = _require_transformers()
        im_raw = Image.open(media.path)
        im = im_raw.convert("RGB")
        im.load()  # Load pixel data into memory
        im_raw.close()  # Close the file handle

        inputs = self.processor(images=im, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=int(self.max_new_tokens))
        text = self.processor.decode(out[0], skip_special_tokens=True).strip()
        # Tags are intentionally lightweight; they can be replaced later.
        tags = ["captioned"]
        return text, tags
