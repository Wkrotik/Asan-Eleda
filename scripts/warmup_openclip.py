from __future__ import annotations

import argparse
from pathlib import Path

import open_clip


def main() -> int:
    ap = argparse.ArgumentParser(description="Warm up / prefetch OpenCLIP weights for offline runs")
    ap.add_argument("--model", default="ViT-B-32")
    ap.add_argument("--pretrained", default="laion2b_s34b_b79k")
    ap.add_argument("--cache-dir", default=str(Path("data/model-cache").resolve()))
    args = ap.parse_args()

    cache_dir = args.cache_dir
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    # This triggers download into cache_dir (HF hub by default in open_clip).
    model, _, _ = open_clip.create_model_and_transforms(
        args.model,
        pretrained=args.pretrained,
        device="cpu",
        cache_dir=cache_dir,
        pretrained_hf=True,
    )
    _ = model
    print(f"OK: cached {args.model} / {args.pretrained} in {cache_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
