from __future__ import annotations

import uuid
from functools import lru_cache

from fastapi import UploadFile

from app.schemas.analyze import AnalyzeResponse
from app.schemas.common import CategoryCandidate, OcrItem, PrioritySuggestion, Warning
from app.schemas.verify import VerifyDecision, VerifyResponse
from core.config import (
    load_categories_config,
    load_pipeline_config,
    load_priority_rules_config,
    load_thresholds_config,
)
from core.engines.mock import MockCaptioner, MockCategorizer, MockEmbedder, MockOcr, MockVerifier
from core.engines.captioning import BlipCaptioner
from core.engines.ocr import EasyOcrV1
from core.engines.openclip_engines import OpenClipSimilarityVerifier, OpenClipZeroShotCategorizer
from core.priority import RulesPrioritizerV1
from core.storage import LocalStorage
from core.video import extract_keyframes_ffmpeg, is_video_path


class Pipeline:
    def __init__(self):
        self.pipeline_cfg = load_pipeline_config()
        self.categories_cfg = load_categories_config()
        self.thresholds_cfg = load_thresholds_config()
        self.priority_rules_cfg = load_priority_rules_config()

        # Storage
        self.storage = LocalStorage(
            uploads_dir=self.pipeline_cfg.storage.uploads_dir,
            artifacts_dir=self.pipeline_cfg.storage.artifacts_dir,
        )

        # Engines (MVP default is mock; can be swapped by config/pipeline.yaml)
        engines = self.pipeline_cfg.engines

        captioner_kind = engines.get("captioner", "mock")
        ocr_kind = engines.get("ocr", "mock")

        self.captioner = MockCaptioner()
        if captioner_kind == "blip_base":
            cache_dir = str(self.pipeline_cfg.storage.model_cache_dir) if self.pipeline_cfg.storage.model_cache_dir else None
            model_id = str(self.pipeline_cfg.captioning.get("model_id", "Salesforce/blip-image-captioning-base"))
            max_new_tokens = int(self.pipeline_cfg.captioning.get("max_new_tokens", 40))
            self.captioner = BlipCaptioner(model_id=model_id, max_new_tokens=max_new_tokens, cache_dir=cache_dir)

        self.ocr = MockOcr()
        if ocr_kind == "easyocr_v1":
            langs = list(self.pipeline_cfg.ocr.get("languages") or ["en"])
            gpu = bool(self.pipeline_cfg.ocr.get("gpu", True))
            cache_dir = str(self.pipeline_cfg.storage.model_cache_dir) if self.pipeline_cfg.storage.model_cache_dir else None
            self.ocr = EasyOcrV1(languages=[str(x) for x in langs], gpu=gpu, model_storage_directory=cache_dir)

        embedder_kind = engines.get("embedder", "mock")
        categorizer_kind = engines.get("categorizer", "mock")
        verifier_kind = engines.get("verifier", "mock")

        self.embedder = MockEmbedder()
        self.categorizer = MockCategorizer()
        self.verifier = MockVerifier()

        if embedder_kind.startswith("openclip") or categorizer_kind.startswith("openclip") or verifier_kind.startswith("openclip"):
            # Lazy imports are inside engines; config toggles enable OpenCLIP.
            if categorizer_kind == "openclip_zeroshot":
                self.categorizer = OpenClipZeroShotCategorizer()
            if verifier_kind == "openclip_similarity":
                self.verifier = OpenClipSimilarityVerifier()

        self.prioritizer = RulesPrioritizerV1(self.priority_rules_cfg.raw)

    async def analyze_upload(self, upload: UploadFile) -> AnalyzeResponse:
        request_id = uuid.uuid4().hex
        stored = await self.storage.save_upload(request_id=request_id, field="media", upload=upload)

        # Video support (MVP): extract a small number of frames and aggregate.
        media_refs = [stored]
        if stored.content_type and stored.content_type.startswith("video/"):
            frames_dir = self.pipeline_cfg.storage.artifacts_dir / request_id / "frames"
            fps = float(self.pipeline_cfg.media.get("video_fps", 0.5))
            max_frames = int(self.pipeline_cfg.media.get("max_video_frames", 8))
            extracted = extract_keyframes_ffmpeg(video_path=stored.path, out_dir=frames_dir, fps=fps, max_frames=max_frames)
            media_refs = [
                stored.__class__(
                    path=f,
                    sha256=stored.sha256,
                    original_filename=stored.original_filename,
                    content_type="image/jpeg",
                    size_bytes=f.stat().st_size,
                )
                for f in extracted.frames
            ]
        elif is_video_path(stored.path):
            # Fallback for unknown content_type.
            frames_dir = self.pipeline_cfg.storage.artifacts_dir / request_id / "frames"
            fps = float(self.pipeline_cfg.media.get("video_fps", 0.5))
            max_frames = int(self.pipeline_cfg.media.get("max_video_frames", 8))
            extracted = extract_keyframes_ffmpeg(video_path=stored.path, out_dir=frames_dir, fps=fps, max_frames=max_frames)
            media_refs = [
                stored.__class__(
                    path=f,
                    sha256=stored.sha256,
                    original_filename=stored.original_filename,
                    content_type="image/jpeg",
                    size_bytes=f.stat().st_size,
                )
                for f in extracted.frames
            ]

        # Use first frame for caption; aggregate categories by max confidence.
        description, tags = self.captioner.caption(media=media_refs[0])

        ocr_items: list[dict] = []
        # OCR only on first frame for now (keeps it fast).
        ocr_items = self.ocr.extract(media=media_refs[0])

        top_k = self.pipeline_cfg.api.category_top_k
        # Aggregate category predictions across frames by max confidence per id.
        pooled: dict[str, dict] = {}
        for m in media_refs:
            preds = self.categorizer.top_k(categories=self.categories_cfg.categories, top_k=top_k, media=m)
            for p in preds:
                cid = p["id"]
                cur = pooled.get(cid)
                if cur is None or float(p["confidence"]) > float(cur["confidence"]):
                    pooled[cid] = p
        cats = sorted(pooled.values(), key=lambda x: float(x["confidence"]), reverse=True)[:top_k]

        pr = self.prioritizer.suggest(tags=tags, text=description)

        warnings: list[Warning] = []
        warnings.append(
            Warning(
                code="taxonomy_placeholder",
                message="Category taxonomy is a placeholder; replace config/categories.yaml with official taxonomy when available.",
            )
        )

        if stored.content_type and stored.content_type.startswith("video/"):
            warnings.append(Warning(code="video_frame_sampling", message="Video analyzed via sampled keyframes (MVP)."))

        return AnalyzeResponse(
            request_id=request_id,
            media={
                "sha256": stored.sha256,
                "content_type": stored.content_type,
                "original_filename": stored.original_filename,
                "size_bytes": stored.size_bytes,
            },
            generated_description=description,
            tags=tags,
            ocr=[OcrItem(**x) for x in ocr_items],
            category_top_k=[CategoryCandidate(**x) for x in cats],
            priority=PrioritySuggestion(level=pr.level, confidence=pr.confidence, rationale=pr.rationale),
            warnings=warnings,
        )

    async def verify_uploads(self, *, before: UploadFile, after: UploadFile) -> VerifyResponse:
        request_id = uuid.uuid4().hex
        b = await self.storage.save_upload(request_id=request_id, field="before", upload=before)
        a = await self.storage.save_upload(request_id=request_id, field="after", upload=after)

        # If videos: compare representative frames (first extracted frame) for MVP.
        b_ref = b
        a_ref = a

        if (b.content_type and b.content_type.startswith("video/")) or is_video_path(b.path):
            frames_dir = self.pipeline_cfg.storage.artifacts_dir / request_id / "before_frames"
            fps = float(self.pipeline_cfg.media.get("video_fps", 0.5))
            max_frames = 1
            extracted = extract_keyframes_ffmpeg(video_path=b.path, out_dir=frames_dir, fps=fps, max_frames=max_frames)
            if extracted.frames:
                f = extracted.frames[0]
                b_ref = b.__class__(
                    path=f,
                    sha256=b.sha256,
                    original_filename=b.original_filename,
                    content_type="image/jpeg",
                    size_bytes=f.stat().st_size,
                )

        if (a.content_type and a.content_type.startswith("video/")) or is_video_path(a.path):
            frames_dir = self.pipeline_cfg.storage.artifacts_dir / request_id / "after_frames"
            fps = float(self.pipeline_cfg.media.get("video_fps", 0.5))
            max_frames = 1
            extracted = extract_keyframes_ffmpeg(video_path=a.path, out_dir=frames_dir, fps=fps, max_frames=max_frames)
            if extracted.frames:
                f = extracted.frames[0]
                a_ref = a.__class__(
                    path=f,
                    sha256=a.sha256,
                    original_filename=a.original_filename,
                    content_type="image/jpeg",
                    size_bytes=f.stat().st_size,
                )

        same_score, same_rationale = self.verifier.same_location(before=b_ref, after=a_ref)
        res_score, res_rationale = self.verifier.resolved(same_location_score=same_score)

        th = self.thresholds_cfg.raw.get("verify") or {}
        same_th = (th.get("same_location") or {})
        res_th = (th.get("resolved") or {})

        same_match = float(same_th.get("match_threshold", 0.75))
        same_warn = float(same_th.get("warn_threshold", 0.60))
        res_ok = float(res_th.get("resolved_threshold", 0.70))
        res_warn = float(res_th.get("warn_threshold", 0.50))

        warnings: list[Warning] = []
        if same_score < same_warn:
            warnings.append(Warning(code="low_location_confidence", message="Low confidence that before/after are same location."))
        if res_score < res_warn:
            warnings.append(Warning(code="low_resolution_confidence", message="Low confidence that issue is resolved."))

        if (b.content_type and b.content_type.startswith("video/")) or (a.content_type and a.content_type.startswith("video/")):
            warnings.append(Warning(code="video_frame_sampling", message="Video verification uses representative keyframes (MVP)."))

        same_decision = "match" if same_score >= same_match else ("needs_review" if same_score >= same_warn else "mismatch")
        res_decision = "match" if res_score >= res_ok else ("needs_review" if res_score >= res_warn else "mismatch")

        return VerifyResponse(
            request_id=request_id,
            before={"sha256": b.sha256, "content_type": b.content_type, "original_filename": b.original_filename},
            after={"sha256": a.sha256, "content_type": a.content_type, "original_filename": a.original_filename},
            same_location=VerifyDecision(score=same_score, decision=same_decision, rationale=same_rationale),
            resolved=VerifyDecision(score=res_score, decision=res_decision, rationale=res_rationale),
            warnings=warnings,
            evidence=[],
        )


@lru_cache(maxsize=1)
def get_pipeline() -> Pipeline:
    return Pipeline()
