from __future__ import annotations

from dataclasses import dataclass

from core.media import MediaRef


def _require_easyocr():
    try:
        import easyocr  # type: ignore
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "OCR engine requires optional deps. Install with: pip install -r requirements-ml.txt"
        ) from e
    return easyocr, np, Image


@dataclass
class EasyOcrV1:
    languages: list[str]
    gpu: bool = True
    model_storage_directory: str | None = None

    def __post_init__(self) -> None:
        easyocr, _, _ = _require_easyocr()
        # Reader init can download weights on first run.
        kwargs = {}
        if self.model_storage_directory:
            kwargs["model_storage_directory"] = self.model_storage_directory
        self.reader = easyocr.Reader(self.languages, gpu=bool(self.gpu), **kwargs)

    def extract(self, *, media: MediaRef) -> list[dict]:
        _, np, Image = _require_easyocr()
        im_raw = Image.open(media.path)
        im = im_raw.convert("RGB")
        im.load()  # Load pixel data into memory
        im_raw.close()  # Close the file handle
        arr = np.array(im)
        results = self.reader.readtext(arr)

        out: list[dict] = []
        for bbox, text, conf in results:
            # bbox is 4 points [[x,y], ...]
            flat = [float(x) for pt in bbox for x in pt]
            out.append({"text": str(text), "confidence": float(conf), "bbox": flat})
        return out
