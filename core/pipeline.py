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
from core.priority import RulesPrioritizerV1
from core.storage import LocalStorage


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

        # Engines (MVP uses mock implementations; swap via config later)
        self.captioner = MockCaptioner()
        self.ocr = MockOcr()
        self.embedder = MockEmbedder()
        self.categorizer = MockCategorizer()
        self.prioritizer = RulesPrioritizerV1(self.priority_rules_cfg.raw)
        self.verifier = MockVerifier()

    async def analyze_upload(self, upload: UploadFile) -> AnalyzeResponse:
        request_id = uuid.uuid4().hex
        stored = await self.storage.save_upload(request_id=request_id, field="media", upload=upload)

        description, tags = self.captioner.caption(sha256=stored.sha256)
        ocr_items = self.ocr.extract(sha256=stored.sha256)

        top_k = self.pipeline_cfg.api.category_top_k
        cats = self.categorizer.top_k(categories=self.categories_cfg.categories, top_k=top_k, sha256=stored.sha256)

        pr = self.prioritizer.suggest(tags=tags, text=description)

        warnings: list[Warning] = []
        warnings.append(
            Warning(
                code="taxonomy_placeholder",
                message="Category taxonomy is a placeholder; replace config/categories.yaml with official taxonomy when available.",
            )
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
        )

    async def verify_uploads(self, *, before: UploadFile, after: UploadFile) -> VerifyResponse:
        request_id = uuid.uuid4().hex
        b = await self.storage.save_upload(request_id=request_id, field="before", upload=before)
        a = await self.storage.save_upload(request_id=request_id, field="after", upload=after)

        same_score, same_rationale = self.verifier.same_location(before_sha256=b.sha256, after_sha256=a.sha256)
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
