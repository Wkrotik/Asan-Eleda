#!/usr/bin/env python3
"""
Performance Profiling Script

Measures inference times for each component of the pipeline:
- BLIP captioning
- OpenCLIP categorization
- EasyOCR text extraction
- Hybrid verification

Usage:
    python scripts/profile_pipeline.py --image path/to/image.jpg
    python scripts/profile_pipeline.py --image path/to/image.jpg --iterations 5
    python scripts/profile_pipeline.py --verify path/to/before.jpg path/to/after.jpg
"""

from __future__ import annotations

import argparse
import time
import statistics
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TimingResult:
    name: str
    times_ms: list[float] = field(default_factory=list)
    
    def add(self, duration_ms: float) -> None:
        self.times_ms.append(duration_ms)
    
    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.times_ms) if self.times_ms else 0.0
    
    @property
    def std_ms(self) -> float:
        return statistics.stdev(self.times_ms) if len(self.times_ms) > 1 else 0.0
    
    @property
    def min_ms(self) -> float:
        return min(self.times_ms) if self.times_ms else 0.0
    
    @property
    def max_ms(self) -> float:
        return max(self.times_ms) if self.times_ms else 0.0
    
    def __str__(self) -> str:
        if not self.times_ms:
            return f"{self.name}: no data"
        if len(self.times_ms) == 1:
            return f"{self.name}: {self.times_ms[0]:.1f}ms"
        return (
            f"{self.name}: {self.mean_ms:.1f}ms "
            f"(std={self.std_ms:.1f}, min={self.min_ms:.1f}, max={self.max_ms:.1f}, n={len(self.times_ms)})"
        )


def time_function(func, *args, **kwargs) -> tuple[any, float]:
    """Execute function and return (result, duration_ms)."""
    start = time.perf_counter()
    result = func(*args, **kwargs)
    duration_ms = (time.perf_counter() - start) * 1000
    return result, duration_ms


def profile_analyze(image_path: Path, iterations: int = 1, warmup: bool = True) -> dict:
    """Profile the analyze pipeline components."""
    from core.media import MediaRef
    
    # Import components
    print("Loading models (this may take a while on first run)...")
    
    load_start = time.perf_counter()
    
    from core.engines.captioning import BlipCaptioner
    from core.engines.openclip_engines import OpenClipZeroShotCategorizer
    from core.engines.ocr import EasyOcrV1
    from core.config import load_categories_config, load_pipeline_config
    
    cfg = load_pipeline_config()
    categories = load_categories_config().categories
    
    # Initialize engines
    captioner = BlipCaptioner(
        model_id=cfg.captioning.get("model_id", "Salesforce/blip-image-captioning-base"),
        max_new_tokens=int(cfg.captioning.get("max_new_tokens", 40)),
    )
    
    categorizer = OpenClipZeroShotCategorizer(
        confidence_method="softmax",
        softmax_temperature=0.25,
    )
    
    ocr_langs = list(cfg.ocr.get("languages") or ["en"])
    ocr = EasyOcrV1(languages=ocr_langs, gpu=cfg.ocr.get("gpu", True))
    
    load_time_ms = (time.perf_counter() - load_start) * 1000
    print(f"Models loaded in {load_time_ms:.0f}ms")
    
    media = MediaRef(path=image_path, sha256="", content_type="image/jpeg", original_filename=image_path.name, size_bytes=0)
    
    # Warmup run (first inference is slower due to JIT compilation, CUDA init, etc.)
    if warmup:
        print("Warmup run...")
        captioner.caption(media=media)
        categorizer.top_k(categories=categories, top_k=3, media=media)
        ocr.extract(media=media)
    
    # Profile each component
    caption_timing = TimingResult("BLIP Captioning")
    categorize_timing = TimingResult("OpenCLIP Categorization")
    ocr_timing = TimingResult("EasyOCR Extraction")
    total_timing = TimingResult("Total Pipeline")
    
    print(f"\nProfiling {iterations} iteration(s)...")
    
    for i in range(iterations):
        total_start = time.perf_counter()
        
        # Caption
        _, dt = time_function(captioner.caption, media=media)
        caption_timing.add(dt)
        
        # Categorize
        _, dt = time_function(categorizer.top_k, categories=categories, top_k=3, media=media)
        categorize_timing.add(dt)
        
        # OCR
        _, dt = time_function(ocr.extract, media=media)
        ocr_timing.add(dt)
        
        total_ms = (time.perf_counter() - total_start) * 1000
        total_timing.add(total_ms)
        
        if iterations > 1:
            print(f"  Iteration {i + 1}: {total_ms:.1f}ms")
    
    return {
        "model_load_ms": load_time_ms,
        "captioning": caption_timing,
        "categorization": categorize_timing,
        "ocr": ocr_timing,
        "total": total_timing,
    }


def profile_verify(before_path: Path, after_path: Path, iterations: int = 1, warmup: bool = True) -> dict:
    """Profile the verification pipeline components."""
    from core.media import MediaRef
    
    print("Loading models...")
    
    load_start = time.perf_counter()
    
    from core.engines.verify_hybrid import HybridVerifierV1
    from core.engines.openclip_engines import OpenClipSimilarityVerifier
    
    hybrid_verifier = HybridVerifierV1()
    clip_verifier = OpenClipSimilarityVerifier()
    
    load_time_ms = (time.perf_counter() - load_start) * 1000
    print(f"Models loaded in {load_time_ms:.0f}ms")
    
    before = MediaRef(path=before_path, sha256="", content_type="image/jpeg", original_filename=before_path.name, size_bytes=0)
    after = MediaRef(path=after_path, sha256="", content_type="image/jpeg", original_filename=after_path.name, size_bytes=0)
    
    # Warmup
    if warmup:
        print("Warmup run...")
        hybrid_verifier.verify(before=before, after=after)
    
    # Profile
    clip_timing = TimingResult("CLIP Similarity")
    hybrid_timing = TimingResult("Hybrid Verification")
    
    print(f"\nProfiling {iterations} iteration(s)...")
    
    for i in range(iterations):
        # CLIP only
        _, dt = time_function(clip_verifier.same_location, before=before, after=after)
        clip_timing.add(dt)
        
        # Full hybrid
        _, dt = time_function(hybrid_verifier.verify, before=before, after=after)
        hybrid_timing.add(dt)
        
        if iterations > 1:
            print(f"  Iteration {i + 1}: hybrid={hybrid_timing.times_ms[-1]:.1f}ms")
    
    return {
        "model_load_ms": load_time_ms,
        "clip_similarity": clip_timing,
        "hybrid_verification": hybrid_timing,
    }


def print_results(results: dict, title: str) -> None:
    """Print profiling results in a formatted table."""
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print('=' * 60)
    
    print(f"\nModel Load Time: {results['model_load_ms']:.0f}ms")
    print("\nComponent Timings:")
    print("-" * 60)
    
    for key, value in results.items():
        if isinstance(value, TimingResult):
            print(f"  {value}")
    
    print("-" * 60)
    
    # Calculate percentage breakdown
    total = results.get("total") or results.get("hybrid_verification")
    if total and total.mean_ms > 0:
        print("\nTime Breakdown (% of total):")
        for key, value in results.items():
            if isinstance(value, TimingResult) and key not in ("total", "hybrid_verification"):
                pct = (value.mean_ms / total.mean_ms) * 100
                print(f"  {value.name}: {pct:.1f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile pipeline component performance")
    parser.add_argument("--image", type=Path, help="Image to analyze")
    parser.add_argument("--verify", nargs=2, type=Path, metavar=("BEFORE", "AFTER"), help="Before/after images to verify")
    parser.add_argument("--iterations", "-n", type=int, default=3, help="Number of iterations (default: 3)")
    parser.add_argument("--no-warmup", action="store_true", help="Skip warmup run")
    parser.add_argument("--device", default=None, help="Device to use (cuda/cpu)")
    args = parser.parse_args()
    
    if not args.image and not args.verify:
        parser.error("Either --image or --verify must be specified")
    
    if args.device:
        import os
        if args.device == "cpu":
            os.environ["CUDA_VISIBLE_DEVICES"] = ""
    
    try:
        if args.image:
            if not args.image.exists():
                print(f"Error: Image not found: {args.image}")
                return 1
            
            results = profile_analyze(
                args.image,
                iterations=args.iterations,
                warmup=not args.no_warmup,
            )
            print_results(results, f"Analyze Profile: {args.image.name}")
        
        if args.verify:
            before, after = args.verify
            if not before.exists():
                print(f"Error: Before image not found: {before}")
                return 1
            if not after.exists():
                print(f"Error: After image not found: {after}")
                return 1
            
            results = profile_verify(
                before, after,
                iterations=args.iterations,
                warmup=not args.no_warmup,
            )
            print_results(results, f"Verify Profile: {before.name} vs {after.name}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
