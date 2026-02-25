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
from core.engines.verify_hybrid import HybridVerifierV1
from core.priority import RulesPrioritizerV1
from core.storage import LocalStorage
from core.video import extract_keyframes_ffmpeg, is_video_path
from core.media import MediaRef


class Pipeline:
    def __init__(self):
        self.pipeline_cfg = load_pipeline_config()
        self.categories_cfg = load_categories_config()
        self.thresholds_cfg = load_thresholds_config()
        self.priority_rules_cfg = load_priority_rules_config()

        # Storage
        max_mb = self.pipeline_cfg.api.raw.get("max_upload_mb")
        max_upload_bytes = None
        if max_mb is not None:
            try:
                max_upload_bytes = int(float(max_mb) * 1024 * 1024)
            except Exception:
                max_upload_bytes = None
        self.storage = LocalStorage(
            uploads_dir=self.pipeline_cfg.storage.uploads_dir,
            artifacts_dir=self.pipeline_cfg.storage.artifacts_dir,
            max_upload_bytes=max_upload_bytes,
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

        if verifier_kind == "hybrid_v1":
            self.verifier = HybridVerifierV1()

        self.prioritizer = RulesPrioritizerV1(self.priority_rules_cfg.raw)

    async def analyze_upload(self, upload: UploadFile) -> AnalyzeResponse:
        request_id = uuid.uuid4().hex
        stored = await self.storage.save_upload(request_id=request_id, field="media", upload=upload)

        # Video support (MVP): extract a small number of frames and aggregate.
        media_refs: list[MediaRef] = [stored]
        if stored.content_type and stored.content_type.startswith("video/"):
            frames_dir = self.pipeline_cfg.storage.artifacts_dir / request_id / "frames"
            fps = float(self.pipeline_cfg.media.get("video_fps", 0.5))
            max_frames = int(self.pipeline_cfg.media.get("max_video_frames", 8))
            extracted = extract_keyframes_ffmpeg(video_path=stored.path, out_dir=frames_dir, fps=fps, max_frames=max_frames)
            media_refs = [
                MediaRef(
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
                MediaRef(
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
        best_frame_for: dict[str, int] = {}
        per_frame: list[dict] = []

        for i, m in enumerate(media_refs):
            # If categorizer supports debug output, capture it.
            debug = None
            top_k_debug = getattr(self.categorizer, "top_k_debug", None)
            if callable(top_k_debug):
                dbg_out = top_k_debug(categories=self.categories_cfg.categories, top_k=top_k, media=m)
                preds, debug = dbg_out  # type: ignore[misc]
            else:
                preds = self.categorizer.top_k(categories=self.categories_cfg.categories, top_k=top_k, media=m)

            per_frame.append(
                {
                    "frame_index": i,
                    "frame_path": str(m.path),
                    "top_k": preds,
                    "debug": debug,
                }
            )

            for p in preds:
                cid = p["id"]
                cur = pooled.get(cid)
                if cur is None or float(p["confidence"]) > float(cur["confidence"]):
                    pooled[cid] = p
                    best_frame_for[cid] = i

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

        evidence: list[dict] = []
        evidence.append(
            {
                "type": "category_aggregation",
                "payload": {
                    "frames_used": len(media_refs),
                    "best_frame_for": best_frame_for,
                    "per_frame": per_frame,
                },
            }
        )

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
            evidence=evidence,
        )

    async def verify_uploads(self, *, before: UploadFile, after: UploadFile) -> VerifyResponse:
        request_id = uuid.uuid4().hex
        b = await self.storage.save_upload(request_id=request_id, field="before", upload=before)
        a = await self.storage.save_upload(request_id=request_id, field="after", upload=after)

        # Video support: extract multiple frames and search for best-matching pair.
        b_refs: list[MediaRef] = [b]
        a_refs: list[MediaRef] = [a]

        # Verification can tolerate a bit more compute; defaults are conservative.
        fps = float(self.pipeline_cfg.media.get("video_fps_verify", self.pipeline_cfg.media.get("video_fps", 0.5)))
        max_frames = int(self.pipeline_cfg.media.get("max_video_frames_verify", self.pipeline_cfg.media.get("max_video_frames", 8)))
        max_frames = max(1, min(max_frames, 24))

        b_is_video = (b.content_type and b.content_type.startswith("video/")) or is_video_path(b.path)
        a_is_video = (a.content_type and a.content_type.startswith("video/")) or is_video_path(a.path)

        if b_is_video:
            frames_dir = self.pipeline_cfg.storage.artifacts_dir / request_id / "before_frames"
            extracted = extract_keyframes_ffmpeg(video_path=b.path, out_dir=frames_dir, fps=fps, max_frames=max_frames)
            if extracted.frames:
                b_refs = [
                    MediaRef(
                        path=f,
                        sha256=b.sha256,
                        original_filename=b.original_filename,
                        content_type="image/jpeg",
                        size_bytes=f.stat().st_size,
                    )
                    for f in extracted.frames
                ]

        if a_is_video:
            frames_dir = self.pipeline_cfg.storage.artifacts_dir / request_id / "after_frames"
            extracted = extract_keyframes_ffmpeg(video_path=a.path, out_dir=frames_dir, fps=fps, max_frames=max_frames)
            if extracted.frames:
                a_refs = [
                    MediaRef(
                        path=f,
                        sha256=a.sha256,
                        original_filename=a.original_filename,
                        content_type="image/jpeg",
                        size_bytes=f.stat().st_size,
                    )
                    for f in extracted.frames
                ]

        # same_location may return (score, rationale) or (score, rationale, evidence)
        best_same_score = -1.0
        best_same_rationale = ""
        best_same_ev = None
        best_pair = (0, 0)

        pair_scores: list[dict] = []
        for bi, b_ref in enumerate(b_refs):
            for ai, a_ref in enumerate(a_refs):
                same_ev = None
                same_out = self.verifier.same_location(before=b_ref, after=a_ref)
                if isinstance(same_out, tuple) and len(same_out) == 3:
                    same_score, same_rationale, same_ev = same_out  # type: ignore[misc]
                else:
                    same_score, same_rationale = same_out  # type: ignore[misc]

                pair_scores.append(
                    {
                        "before_index": bi,
                        "after_index": ai,
                        "score": float(same_score),
                    }
                )
                if float(same_score) > best_same_score:
                    best_same_score = float(same_score)
                    best_same_rationale = str(same_rationale)
                    best_same_ev = same_ev
                    best_pair = (bi, ai)

        # Choose the best-matching pair for downstream resolved heuristics.
        b_ref = b_refs[best_pair[0]]
        a_ref = a_refs[best_pair[1]]
        same_score = max(0.0, min(1.0, float(best_same_score)))
        same_rationale = best_same_rationale or "Same-location score computed from best frame pair."
        same_ev = best_same_ev

        # Some verifiers use before/after for resolution heuristics.
        # Keep compatibility with verifiers that only accept same_location_score.
        resolved_fn = getattr(self.verifier, "resolved")

        res_ev = None
        try:
            res_out = resolved_fn(same_location_score=same_score, before=b_ref, after=a_ref)
        except TypeError:
            res_out = resolved_fn(same_location_score=same_score)

        if isinstance(res_out, tuple) and len(res_out) == 3:
            res_score, res_rationale, res_ev = res_out  # type: ignore[misc]
        else:
            res_score, res_rationale = res_out  # type: ignore[misc]

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
            warnings.append(Warning(code="video_frame_sampling", message="Video verification uses sampled keyframes (MVP)."))

        if len(b_refs) * len(a_refs) > 1 and same_score < same_warn:
            warnings.append(
                Warning(
                    code="video_no_strong_match",
                    message="No evaluated frame pair reached same-location warning threshold; result likely needs review.",
                )
            )

        evidence: list[dict] = []
        # Keep evidence bounded: include basic stats and top pairs.
        pair_scores_sorted = sorted(pair_scores, key=lambda x: float(x.get("score", 0.0)), reverse=True)
        top_pairs = pair_scores_sorted[: min(6, len(pair_scores_sorted))]
        stats = None
        if pair_scores_sorted:
            scores = [float(x["score"]) for x in pair_scores_sorted]
            stats = {
                "count": len(scores),
                "max": max(scores),
                "min": min(scores),
                "mean": sum(scores) / float(len(scores)),
            }

        evidence.append(
            {
                "type": "verify_signals",
                "payload": {
                    "same_location": same_ev,
                    "resolved": res_ev,
                    "pair_search": {
                        "before_frames": [str(x.path) for x in b_refs] if len(b_refs) > 1 else [],
                        "after_frames": [str(x.path) for x in a_refs] if len(a_refs) > 1 else [],
                        "evaluated_pairs": len(pair_scores),
                        "best_pair": {"before_index": best_pair[0], "after_index": best_pair[1], "score": same_score},
                        "top_pairs": top_pairs,
                        "stats": stats,
                        "fps": fps if (b_is_video or a_is_video) else None,
                        "max_frames": max_frames if (b_is_video or a_is_video) else None,
                    },
                    "thresholds": {
                        "same_location": {"match": same_match, "warn": same_warn},
                        "resolved": {"resolved": res_ok, "warn": res_warn},
                    },
                    "media": {
                        "before_used": str(b_ref.path),
                        "after_used": str(a_ref.path),
                    },
                },
            }
        )

        same_decision = "match" if same_score >= same_match else ("needs_review" if same_score >= same_warn else "mismatch")
        res_decision = "match" if res_score >= res_ok else ("needs_review" if res_score >= res_warn else "mismatch")

        return VerifyResponse(
            request_id=request_id,
            before={"sha256": b.sha256, "content_type": b.content_type, "original_filename": b.original_filename},
            after={"sha256": a.sha256, "content_type": a.content_type, "original_filename": a.original_filename},
            same_location=VerifyDecision(score=same_score, decision=same_decision, rationale=same_rationale),
            resolved=VerifyDecision(score=res_score, decision=res_decision, rationale=res_rationale),
            warnings=warnings,
            evidence=evidence,
        )


@lru_cache(maxsize=1)
def get_pipeline() -> Pipeline:
    return Pipeline()
