from __future__ import annotations

import asyncio
import logging
import uuid
from functools import lru_cache

from fastapi import UploadFile

from app.schemas.analyze import AnalyzeResponse
from app.schemas.common import CategoryCandidate, OcrItem, PrioritySuggestion, Warning
from app.schemas.verify import ReviewReason, VerifyDecision, VerifyResponse
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
from core.video import extract_keyframes_ffmpeg, is_video_path, probe_video_metadata
from core.media import MediaRef
from core.metadata import extract_image_metadata, haversine_m

logger = logging.getLogger(__name__)


def _extract_video_frames(
    *,
    stored: MediaRef,
    frames_dir,
    fps: float,
    max_frames: int,
    min_frames: int,
) -> list[MediaRef]:
    """Extract keyframes from a video and return MediaRef list.

    Returns a list with the extracted frame MediaRefs, or [stored] as fallback
    if extraction fails or yields no frames.
    """
    extracted = extract_keyframes_ffmpeg(
        video_path=stored.path,
        out_dir=frames_dir,
        fps=fps,
        max_frames=max_frames,
        min_frames=min_frames,
    )
    if not extracted.frames:
        logger.warning("Video frame extraction yielded no frames; falling back to stored ref")
        return [stored]
    return [
        MediaRef(
            path=f,
            sha256=stored.sha256,
            original_filename=stored.original_filename,
            content_type="image/jpeg",
            size_bytes=f.stat().st_size,
        )
        for f in extracted.frames
    ]


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
            except (TypeError, ValueError):
                logger.warning("Invalid max_upload_mb config value: %s; disabling upload limit", max_mb)
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
                cat_cfg = self.pipeline_cfg.categorization or {}
                confidence_method = str(cat_cfg.get("confidence_method", "softmax"))
                softmax_temperature = float(cat_cfg.get("softmax_temperature", 0.25))
                self.categorizer = OpenClipZeroShotCategorizer(
                    confidence_method=confidence_method,
                    softmax_temperature=softmax_temperature,
                )
            if verifier_kind == "openclip_similarity":
                self.verifier = OpenClipSimilarityVerifier()

        if verifier_kind == "hybrid_v1":
            self.verifier = HybridVerifierV1()

        self.prioritizer = RulesPrioritizerV1(self.priority_rules_cfg.raw)

    async def analyze_upload(self, upload: UploadFile) -> AnalyzeResponse:
        request_id = uuid.uuid4().hex
        stored = await self.storage.save_upload(request_id=request_id, field="media", upload=upload)

        include_gps = bool(self.pipeline_cfg.privacy.get("include_gps_evidence", True))
        gps_round = int(self.pipeline_cfg.privacy.get("gps_round_decimals", 5))
        meta = None
        if stored.content_type and stored.content_type.startswith("image/"):
            meta = await asyncio.to_thread(
                extract_image_metadata, path=stored.path, gps_round_decimals=gps_round, include_gps=include_gps
            )
        elif stored.content_type and stored.content_type.startswith("video/"):
            meta = await asyncio.to_thread(probe_video_metadata, stored.path)
            # Optional rounding for GPS.
            if include_gps and isinstance(meta, dict) and isinstance(meta.get("gps"), dict):
                meta["gps"]["lat"] = round(float(meta["gps"]["lat"]), gps_round)
                meta["gps"]["lon"] = round(float(meta["gps"]["lon"]), gps_round)
            if not include_gps and isinstance(meta, dict):
                meta.pop("gps", None)

        # Video support (MVP): extract a small number of frames and aggregate.
        media_refs: list[MediaRef] = [stored]
        is_video = (stored.content_type and stored.content_type.startswith("video/")) or is_video_path(stored.path)
        if is_video:
            frames_dir = self.pipeline_cfg.storage.artifacts_dir / request_id / "frames"
            fps = float(self.pipeline_cfg.media.get("video_fps", 0.5))
            max_frames = int(self.pipeline_cfg.media.get("max_video_frames", 8))
            min_frames = int(self.pipeline_cfg.media.get("min_video_frames", 0))
            media_refs = await asyncio.to_thread(
                _extract_video_frames,
                stored=stored,
                frames_dir=frames_dir,
                fps=fps,
                max_frames=max_frames,
                min_frames=min_frames,
            )

        # Use first frame for caption; for video also sample OCR on multiple frames.
        description, tags = await asyncio.to_thread(self.captioner.caption, media=media_refs[0])

        # OCR: for images use first (only) ref; for videos, aggregate OCR across sampled frames.
        ocr_items: list[dict] = []
        ocr_per_frame: list[dict] = []
        if len(media_refs) <= 1:
            ocr_raw = await asyncio.to_thread(self.ocr.extract, media=media_refs[0])
            ocr_items = ocr_raw if isinstance(ocr_raw, list) else []
        else:
            # Bound compute: OCR on up to N frames spaced across the clip.
            max_ocr_frames = int(self.pipeline_cfg.media.get("max_video_ocr_frames", 4))
            max_ocr_frames = max(1, min(max_ocr_frames, len(media_refs)))
            if max_ocr_frames >= len(media_refs):
                idxs = list(range(len(media_refs)))
            else:
                # Evenly spaced indices including first and last.
                step = (len(media_refs) - 1) / float(max_ocr_frames - 1) if max_ocr_frames > 1 else 0.0
                idxs = sorted({int(round(i * step)) for i in range(max_ocr_frames)})
            seen_text: set[str] = set()
            for i in idxs:
                items_raw = await asyncio.to_thread(self.ocr.extract, media=media_refs[i])
                items = items_raw if isinstance(items_raw, list) else []
                ocr_per_frame.append({"frame_index": i, "frame_path": str(media_refs[i].path), "items": items})
                for it in items:
                    t = str(it.get("text", "")).strip()
                    if not t:
                        continue
                    key = " ".join(t.lower().split())
                    if key in seen_text:
                        continue
                    seen_text.add(key)
                    ocr_items.append(it)

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
                dbg_out = await asyncio.to_thread(
                    top_k_debug, categories=self.categories_cfg.categories, top_k=top_k, media=m
                )
                preds, debug = dbg_out  # type: ignore[misc]
            else:
                preds = await asyncio.to_thread(
                    self.categorizer.top_k, categories=self.categories_cfg.categories, top_k=top_k, media=m
                )

            if not isinstance(preds, list):
                preds = []

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

        # Priority: include OCR text as additional signal.
        ocr_text = " ".join([str(x.get("text", "")) for x in ocr_items if isinstance(x, dict)])
        pr = self.prioritizer.suggest(tags=tags, text=(description + " " + ocr_text).strip())

        warnings: list[Warning] = []
        warnings.append(
            Warning(
                code="taxonomy_placeholder",
                message="Category taxonomy is a placeholder; replace config/categories.yaml (or CATEGORIES_CONFIG) with official taxonomy when available.",
            )
        )

        if stored.content_type and stored.content_type.startswith("video/"):
            warnings.append(Warning(code="video_frame_sampling", message="Video analyzed via sampled keyframes (MVP)."))

        evidence: list[dict] = []
        if meta is not None:
            evidence.append({"type": "media_metadata", "payload": meta})
        if ocr_per_frame:
            evidence.append(
                {
                    "type": "ocr_aggregation",
                    "payload": {
                        "frames_used": len(ocr_per_frame),
                        "per_frame": ocr_per_frame,
                    },
                }
            )

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

        include_gps = bool(self.pipeline_cfg.privacy.get("include_gps_evidence", True))
        gps_round = int(self.pipeline_cfg.privacy.get("gps_round_decimals", 5))
        gps_warn_m = float(self.pipeline_cfg.privacy.get("gps_mismatch_warn_m", 250))

        b_meta = None
        a_meta = None
        if b.content_type and b.content_type.startswith("image/"):
            b_meta = await asyncio.to_thread(
                extract_image_metadata, path=b.path, gps_round_decimals=gps_round, include_gps=include_gps
            )
        elif (b.content_type and b.content_type.startswith("video/")) or is_video_path(b.path):
            b_meta = await asyncio.to_thread(probe_video_metadata, b.path)
            if include_gps and isinstance(b_meta, dict) and isinstance(b_meta.get("gps"), dict):
                b_meta["gps"]["lat"] = round(float(b_meta["gps"]["lat"]), gps_round)
                b_meta["gps"]["lon"] = round(float(b_meta["gps"]["lon"]), gps_round)
            if not include_gps and isinstance(b_meta, dict):
                b_meta.pop("gps", None)

        if a.content_type and a.content_type.startswith("image/"):
            a_meta = await asyncio.to_thread(
                extract_image_metadata, path=a.path, gps_round_decimals=gps_round, include_gps=include_gps
            )
        elif (a.content_type and a.content_type.startswith("video/")) or is_video_path(a.path):
            a_meta = await asyncio.to_thread(probe_video_metadata, a.path)
            if include_gps and isinstance(a_meta, dict) and isinstance(a_meta.get("gps"), dict):
                a_meta["gps"]["lat"] = round(float(a_meta["gps"]["lat"]), gps_round)
                a_meta["gps"]["lon"] = round(float(a_meta["gps"]["lon"]), gps_round)
            if not include_gps and isinstance(a_meta, dict):
                a_meta.pop("gps", None)

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
            min_frames = int(self.pipeline_cfg.media.get("min_video_frames", 0))
            b_refs = await asyncio.to_thread(
                _extract_video_frames,
                stored=b,
                frames_dir=frames_dir,
                fps=fps,
                max_frames=max_frames,
                min_frames=min_frames,
            )

        if a_is_video:
            frames_dir = self.pipeline_cfg.storage.artifacts_dir / request_id / "after_frames"
            min_frames = int(self.pipeline_cfg.media.get("min_video_frames", 0))
            a_refs = await asyncio.to_thread(
                _extract_video_frames,
                stored=a,
                frames_dir=frames_dir,
                fps=fps,
                max_frames=max_frames,
                min_frames=min_frames,
            )

        # same_location may return (score, rationale) or (score, rationale, evidence)
        best_same_score = -1.0
        best_same_rationale = ""
        best_same_ev = None
        best_pair = (0, 0)

        pair_scores: list[dict] = []
        pair_search_meta: dict = {"strategy": "exhaustive"}

        total_pairs = len(b_refs) * len(a_refs)
        is_video_case = (b_is_video or a_is_video) and total_pairs > 1

        # Coarse-to-fine video pairing for HybridVerifierV1: use OpenCLIP similarity to shortlist pairs,
        # then run expensive ORB/homography only on a capped set.
        if is_video_case and isinstance(self.verifier, HybridVerifierV1):
            max_evals = int(self.pipeline_cfg.media.get("max_video_pair_evals_verify", 24))
            max_evals = max(1, min(max_evals, total_pairs))
            tw = int(self.pipeline_cfg.media.get("video_pair_temporal_window", 2))
            tw = max(0, tw)

            # Precompute embeddings once per frame.
            b_vecs = [await asyncio.to_thread(self.verifier.clip_embed, media=ref) for ref in b_refs]
            a_vecs = [await asyncio.to_thread(self.verifier.clip_embed, media=ref) for ref in a_refs]

            clip_pairs: list[dict] = []
            for bi, bv in enumerate(b_vecs):
                for ai, av in enumerate(a_vecs):
                    clip_sim, clip_score = await asyncio.to_thread(
                        self.verifier.clip_similarity, before_vec=bv, after_vec=av
                    )
                    clip_pairs.append(
                        {
                            "before_index": bi,
                            "after_index": ai,
                            "clip_score": float(clip_score),
                            "clip_sim": float(clip_sim),
                        }
                    )
            clip_pairs_sorted = sorted(clip_pairs, key=lambda x: float(x.get("clip_score", 0.0)), reverse=True)

            # Build a lookup dict for O(1) access to clip stats by (before_index, after_index)
            clip_pairs_lookup: dict[tuple[int, int], dict] = {
                (int(item["before_index"]), int(item["after_index"])): item for item in clip_pairs
            }

            candidates: list[tuple[int, int]] = []
            seen = set()

            # Add time-aligned candidates first.
            if tw > 0:
                m = min(len(b_refs), len(a_refs))
                for i in range(m):
                    for d in range(-tw, tw + 1):
                        j = i + d
                        if 0 <= j < len(a_refs):
                            k = (i, j)
                            if k in seen:
                                continue
                            seen.add(k)
                            candidates.append(k)

            # Fill remaining slots by best clip-only pairs.
            for item in clip_pairs_sorted:
                if len(candidates) >= max_evals:
                    break
                k = (int(item["before_index"]), int(item["after_index"]))
                if k in seen:
                    continue
                seen.add(k)
                candidates.append(k)

            # Evaluate shortlisted pairs with ORB and blended score.
            best_clip = clip_pairs_sorted[0] if clip_pairs_sorted else None
            for (bi, ai) in candidates:
                # O(1) lookup for cached clip stats.
                cs = clip_pairs_lookup.get((bi, ai))
                clip_sim = float(cs["clip_sim"]) if cs else 0.0
                clip_score = float(cs["clip_score"]) if cs else 0.0
                same_score, same_rationale, same_ev = await asyncio.to_thread(
                    self.verifier.same_location_with_clip,
                    before=b_refs[bi],
                    after=a_refs[ai],
                    clip_sim=clip_sim,
                    clip_score=clip_score,
                )

                pair_scores.append({"before_index": bi, "after_index": ai, "score": float(same_score)})
                if float(same_score) > best_same_score:
                    best_same_score = float(same_score)
                    best_same_rationale = str(same_rationale)
                    best_same_ev = same_ev
                    best_pair = (bi, ai)

            pair_search_meta = {
                "strategy": "coarse_to_fine_clip",
                "total_pairs": int(total_pairs),
                "evaluated_pairs": int(len(pair_scores)),
                "max_evals": int(max_evals),
                "temporal_window": int(tw),
                "clip_best_pair": {
                    "before_index": int(best_clip["before_index"]),
                    "after_index": int(best_clip["after_index"]),
                    "clip_score": float(best_clip["clip_score"]),
                }
                if best_clip is not None
                else None,
                "clip_top_pairs": [
                    {
                        "before_index": int(x["before_index"]),
                        "after_index": int(x["after_index"]),
                        "clip_score": float(x["clip_score"]),
                    }
                    for x in clip_pairs_sorted[: min(6, len(clip_pairs_sorted))]
                ],
            }
        else:
            # Exhaustive evaluation (images or non-hybrid verifier).
            for bi, b_ref in enumerate(b_refs):
                for ai, a_ref in enumerate(a_refs):
                    same_score, same_rationale, same_ev = await asyncio.to_thread(
                        self.verifier.same_location, before=b_ref, after=a_ref
                    )

                    pair_scores.append({"before_index": bi, "after_index": ai, "score": float(same_score)})
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

        # Call resolved with full signature (both verifiers now support it).
        res_score, res_rationale, res_ev = await asyncio.to_thread(
            self.verifier.resolved,
            same_location_score=same_score,
            before=b_ref,
            after=a_ref,
            same_location_evidence=same_ev if isinstance(same_ev, dict) else None,
        )

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

        # If we had many possible pairs but only evaluated a few, surface a gentle warning when confidence is low.
        if is_video_case and pair_search_meta.get("strategy") != "exhaustive" and same_score < same_warn:
            warnings.append(
                Warning(
                    code="insufficient_video_evidence",
                    message="Video verification evaluated a capped set of frame pairs; result likely needs review.",
                )
            )

        gps_distance_m = None
        try:
            if include_gps and isinstance(b_meta, dict) and isinstance(a_meta, dict):
                bg = b_meta.get("gps") if isinstance(b_meta.get("gps"), dict) else None
                ag = a_meta.get("gps") if isinstance(a_meta.get("gps"), dict) else None
                if isinstance(bg, dict) and isinstance(ag, dict):
                    gps_distance_m = haversine_m(
                        lat1=float(bg["lat"]),
                        lon1=float(bg["lon"]),
                        lat2=float(ag["lat"]),
                        lon2=float(ag["lon"]),
                    )
                    if gps_distance_m > gps_warn_m:
                        warnings.append(
                            Warning(
                                code="gps_mismatch",
                                message=f"GPS metadata differs by ~{gps_distance_m:.0f}m; same-location may be incorrect.",
                            )
                        )
        except Exception as exc:
            logger.warning("GPS distance calculation failed: %s", exc)
            gps_distance_m = None

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
                    "metadata": {
                        "before": b_meta,
                        "after": a_meta,
                        "gps_distance_m": gps_distance_m,
                    },
                    "pair_search": {
                        "before_frames": [str(x.path) for x in b_refs] if len(b_refs) > 1 else [],
                        "after_frames": [str(x.path) for x in a_refs] if len(a_refs) > 1 else [],
                        "evaluated_pairs": len(pair_scores),
                        "best_pair": {"before_index": best_pair[0], "after_index": best_pair[1], "score": same_score},
                        "top_pairs": top_pairs,
                        "stats": stats,
                        "fps": fps if (b_is_video or a_is_video) else None,
                        "max_frames": max_frames if (b_is_video or a_is_video) else None,
                        "search": pair_search_meta,
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

        # Build structured review_reasons for operator clarity.
        review_reasons: list[ReviewReason] = []

        # same_location reasons
        if same_decision == "needs_review":
            review_reasons.append(
                ReviewReason(
                    code="location_needs_review",
                    signal="same_location",
                    detail=f"Score {same_score:.2f} is between warn ({same_warn:.2f}) and match ({same_match:.2f}) thresholds.",
                )
            )
        elif same_decision == "mismatch":
            review_reasons.append(
                ReviewReason(
                    code="location_mismatch",
                    signal="same_location",
                    detail=f"Score {same_score:.2f} is below warn threshold ({same_warn:.2f}); likely different locations.",
                )
            )

        # resolved reasons
        if res_decision == "needs_review":
            review_reasons.append(
                ReviewReason(
                    code="resolution_needs_review",
                    signal="resolved",
                    detail=f"Score {res_score:.2f} is between warn ({res_warn:.2f}) and resolved ({res_ok:.2f}) thresholds.",
                )
            )
        elif res_decision == "mismatch":
            review_reasons.append(
                ReviewReason(
                    code="resolution_uncertain",
                    signal="resolved",
                    detail=f"Score {res_score:.2f} is below warn threshold ({res_warn:.2f}); issue may not be resolved.",
                )
            )

        # GPS mismatch reason (if warning was added)
        if gps_distance_m is not None and gps_distance_m > gps_warn_m:
            review_reasons.append(
                ReviewReason(
                    code="gps_mismatch",
                    signal="same_location",
                    detail=f"GPS coordinates differ by ~{gps_distance_m:.0f}m (threshold: {gps_warn_m:.0f}m).",
                )
            )

        # Video-specific reasons
        if is_video_case and same_decision != "match":
            if pair_search_meta.get("strategy") != "exhaustive":
                review_reasons.append(
                    ReviewReason(
                        code="video_partial_search",
                        signal="same_location",
                        detail=f"Only {len(pair_scores)} of {total_pairs} frame pairs were evaluated (coarse-to-fine search).",
                    )
                )
            if len(b_refs) * len(a_refs) > 1 and same_score < same_warn:
                review_reasons.append(
                    ReviewReason(
                        code="video_no_strong_pair",
                        signal="same_location",
                        detail="No frame pair reached the same-location confidence threshold.",
                    )
                )

        return VerifyResponse(
            request_id=request_id,
            before={"sha256": b.sha256, "content_type": b.content_type, "original_filename": b.original_filename},
            after={"sha256": a.sha256, "content_type": a.content_type, "original_filename": a.original_filename},
            same_location=VerifyDecision(score=same_score, decision=same_decision, rationale=same_rationale),
            resolved=VerifyDecision(score=res_score, decision=res_decision, rationale=res_rationale),
            warnings=warnings,
            review_reasons=review_reasons,
            evidence=evidence,
        )


@lru_cache(maxsize=1)
def get_pipeline() -> Pipeline:
    return Pipeline()
