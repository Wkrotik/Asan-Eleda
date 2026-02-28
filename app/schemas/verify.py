from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Warning


class VerifyDecision(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    decision: Literal["match", "mismatch", "needs_review"]
    rationale: str


class ReviewReason(BaseModel):
    """Structured explanation for why a verify decision is 'needs_review'."""

    code: str = Field(description="Machine-readable reason code, e.g. 'low_location_confidence'")
    signal: str = Field(description="Which signal triggered this, e.g. 'same_location' or 'resolved'")
    detail: str = Field(description="Human-readable explanation with specifics")


class VerifyResponse(BaseModel):
    request_id: str
    before: dict = Field(default_factory=dict)
    after: dict = Field(default_factory=dict)

    same_location: VerifyDecision
    resolved: VerifyDecision

    warnings: list[Warning] = Field(default_factory=list)
    review_reasons: list[ReviewReason] = Field(
        default_factory=list,
        description="Structured reasons when either decision is 'needs_review'; empty if both are 'match'",
    )
    evidence: list[dict] = Field(default_factory=list)
