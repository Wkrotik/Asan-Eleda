from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}, got {type(data).__name__}")
    return data


@dataclass(frozen=True)
class StorageConfig:
    type: str
    uploads_dir: Path
    artifacts_dir: Path
    model_cache_dir: Path | None = None


@dataclass(frozen=True)
class ApiConfig:
    category_top_k: int


@dataclass(frozen=True)
class PipelineConfig:
    engines: dict[str, str]
    storage: StorageConfig
    api: ApiConfig
    media: dict[str, Any]
    captioning: dict[str, Any]
    ocr: dict[str, Any]


@dataclass(frozen=True)
class CategoriesConfig:
    version: int
    categories: list[dict[str, Any]]


@dataclass(frozen=True)
class ThresholdsConfig:
    raw: dict[str, Any]


@dataclass(frozen=True)
class PriorityRulesConfig:
    raw: dict[str, Any]


def load_pipeline_config() -> PipelineConfig:
    p = ROOT / "config" / "pipeline.yaml"
    raw = _read_yaml(p)
    storage = raw.get("storage") or {}
    api = raw.get("api") or {}
    media = raw.get("media") or {}
    captioning = raw.get("captioning") or {}
    ocr = raw.get("ocr") or {}
    return PipelineConfig(
        engines=dict(raw.get("engines") or {}),
        storage=StorageConfig(
            type=str(storage.get("type", "local")),
            uploads_dir=ROOT / str(storage.get("uploads_dir", "data/uploads")),
            artifacts_dir=ROOT / str(storage.get("artifacts_dir", "data/artifacts")),
            model_cache_dir=(ROOT / str(storage.get("model_cache_dir"))) if storage.get("model_cache_dir") else None,
        ),
        api=ApiConfig(category_top_k=int(api.get("category_top_k", 3))),
        media=dict(media),
        captioning=dict(captioning),
        ocr=dict(ocr),
    )


def load_categories_config() -> CategoriesConfig:
    p = ROOT / "config" / "categories.yaml"
    raw = _read_yaml(p)
    return CategoriesConfig(version=int(raw.get("version", 1)), categories=list(raw.get("categories") or []))


def load_thresholds_config() -> ThresholdsConfig:
    p = ROOT / "config" / "thresholds.yaml"
    return ThresholdsConfig(raw=_read_yaml(p))


def load_priority_rules_config() -> PriorityRulesConfig:
    p = ROOT / "config" / "priority_rules.yaml"
    return PriorityRulesConfig(raw=_read_yaml(p))
