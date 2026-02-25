from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Warning


class VerifyDecision(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    decision: Literal["match", "mismatch", "needs_review"]
    rationale: str


class VerifyResponse(BaseModel):
    request_id: str
    before: dict = Field(default_factory=dict)
    after: dict = Field(default_factory=dict)

    same_location: VerifyDecision
    resolved: VerifyDecision

    warnings: list[Warning] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)

    mode: Literal["mvp"] = "mvp"
