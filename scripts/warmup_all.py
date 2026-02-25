from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Warm up / prefetch model weights for offline runs")
    ap.add_argument("--cache-dir", default=str(Path("data/model-cache").resolve()))
    ap.add_argument("--ocr-langs", default="en")
    ap.add_argument("--no-gpu", action="store_true")
    args = ap.parse_args()

    cache_dir = str(Path(args.cache_dir).resolve())
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    # OpenCLIP
    try:
        import open_clip

        open_clip.create_model_and_transforms(
            "ViT-B-32",
            pretrained="laion2b_s34b_b79k",
            device="cpu",
            cache_dir=cache_dir,
            pretrained_hf=True,
        )
        print("OK: OpenCLIP cached")
    except Exception as e:
        print(f"SKIP: OpenCLIP warmup failed: {e}")

    # BLIP captioning
    try:
        from transformers import BlipForConditionalGeneration, BlipProcessor

        model_id = "Salesforce/blip-image-captioning-base"
        BlipProcessor.from_pretrained(model_id, cache_dir=cache_dir)
        BlipForConditionalGeneration.from_pretrained(model_id, cache_dir=cache_dir)
        print("OK: BLIP cached")
    except Exception as e:
        print(f"SKIP: BLIP warmup failed: {e}")

    # EasyOCR
    try:
        import easyocr

        langs = [s.strip() for s in str(args.ocr_langs).split(",") if s.strip()]
        easyocr.Reader(langs or ["en"], gpu=not args.no_gpu, model_storage_directory=cache_dir)
        print("OK: EasyOCR cached")
    except Exception as e:
        print(f"SKIP: EasyOCR warmup failed: {e}")

    print(f"Done. Cache dir: {cache_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
