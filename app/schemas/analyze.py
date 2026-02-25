from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import CategoryCandidate, OcrItem, PrioritySuggestion, Warning


class AnalyzeResponse(BaseModel):
    request_id: str
    media: dict = Field(default_factory=dict)

    generated_description: str
    tags: list[str] = Field(default_factory=list)
    ocr: list[OcrItem] = Field(default_factory=list)

    category_top_k: list[CategoryCandidate] = Field(default_factory=list)
    priority: PrioritySuggestion

    warnings: list[Warning] = Field(default_factory=list)

    mode: Literal["mvp"] = "mvp"
