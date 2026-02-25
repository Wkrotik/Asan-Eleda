from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Warning(BaseModel):
    code: str
    message: str


class OcrItem(BaseModel):
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: list[float] | None = None


class CategoryCandidate(BaseModel):
    id: str
    label: str
    confidence: float = Field(ge=0.0, le=1.0)


class PrioritySuggestion(BaseModel):
    level: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
