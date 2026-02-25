# ASAN Appeal AI (Offline MVP)

This repo contains the plan and implementation skeleton for an offline (on-device/on-prem) MVP for the ASAN AI Hub challenge:
"Intelligent Analysis of Visual Content and Automated Compliance Verification".

Goal: reduce manual workload by automatically analyzing citizen-submitted images/videos, suggesting a category + priority, and verifying whether institution-provided "after" media matches the original appeal and indicates resolution.

## What We Are Building (MVP)

Two core capabilities exposed via an API:

1) Analyze (citizen media)
- Input: image or video
- Output:
  - generated textual description
  - tags (visual concepts)
  - OCR text snippets (if any)
  - category prediction (top_k=3 with confidences)
  - priority suggestion (with rationale)
  - warnings when confidence is low or taxonomy is placeholder

2) Verify (before vs after)
- Input: citizen "before" media + institution "after" media
- Output:
  - same-location score/decision (match vs mismatch)
  - resolved score/decision (resolved vs needs_review)
  - warnings when evidence is weak or contradictory
  - evidence artifacts (optional): representative frames, similarity numbers, OCR overlap

Important: Category is treated as a backend routing hint even if the UI does not show it.

## Key Constraints / Assumptions

- Offline-only: no external hosted AI APIs.
- Replaceable taxonomy: we do not hardcode the official ASAN category list. We start with a placeholder taxonomy and swap it later by editing config.
- Conservative verification: we prefer "needs_review" over false "resolved" claims.
- GPU available: RTX 4050 Laptop (6GB VRAM). We choose model sizes that fit.

## Replaceable-by-Design Architecture

Core idea: stable interfaces + config-driven implementations.

Pipeline calls these engines (each is swappable):
- MediaIngestor: image/video loading, metadata, keyframes
- Captioner: short description + tags
- OcrExtractor: text + bounding boxes + confidence
- Embedder: vector embeddings for matching + label similarity
- Categorizer: label bank -> top_k=3
- Prioritizer: rules-first -> High/Medium/Low (+ rationale)
- Verifier:
  - same_location_score (embedding similarity + keypoints + OCR overlap + optional GPS)
  - resolved_score (issue-type-dependent checks when confident)
- Storage: local filesystem now; can be swapped to object storage later

### Why this structure

When ASAN provides:
- an official category taxonomy
- institution routing mapping
- priority definition rules
- sample datasets

...we update YAML config and (optionally) swap model backends without breaking the API or rewriting orchestration logic.

## Planned Model Stack (fits 6GB VRAM)

- Embeddings / zero-shot label matching: OpenCLIP ViT-B/32
- Captioning: lightweight offline image captioner (engine is swappable)
- OCR: EasyOCR or Tesseract (swappable)
- Optional detection cues: YOLOv8n/s (small)
- Video: keyframe extraction (scene cut + periodic sampling) + aggregation

## API Contract (stable)

`POST /analyze`
- returns (conceptually):
  - `generated_description: str`
  - `tags: str[]`
  - `ocr: {text, confidence, bbox}[]`
  - `category_top_k: {id, label, confidence}[]` (length 3)
  - `priority: {level, confidence, rationale}`
  - `warnings: {code, message}[]`

`POST /verify`
- returns (conceptually):
  - `same_location: {score, decision, rationale}`
  - `resolved: {score, decision, rationale}`
  - `warnings: {code, message}[]`
  - `evidence: {type, payload}[]` (optional)

## Config-Driven Pieces

All items below are intended to be edited without code changes:

- `config/categories.yaml`
  - placeholder category list now
  - later replace with official ASAN taxonomy
- `config/priority_rules.yaml`
  - rules and thresholds
- `config/thresholds.yaml`
  - warning thresholds for verification
- `config/pipeline.yaml`
  - which engine implementation to use (embedder/captioner/ocr/etc.)

## Project Timeline (50 days / ~7 weeks)

Week 1
- lock response schemas + engine interfaces
- scaffold FastAPI service, configs, storage layout

Week 2
- image analyze pipeline: caption/tags + OCR + embeddings
- category v0 (placeholder taxonomy) + priority v0 (rules)

Week 3
- video support: keyframes + aggregation
- performance pass (batching, caching)

Week 4
- verification v1: same-location scoring + warnings
- add conservative resolved logic (only when confident)

Week 5
- security basics: retention knobs, access patterns, safe logging
- packaging docs and integration notes

Week 6
- evaluation harness + threshold calibration
- iterate with any provided sample dataset

Week 7
- demo polish + submission pack write-up (architecture, integration, pilot plan)
- optional Docker packaging (CPU + GPU-capable)

## Development Setup (pyenv)

We develop with Python 3.11.x (recommended for PyTorch/CUDA wheel compatibility).

1) Install Python

```bash
pyenv install 3.11.9
pyenv local 3.11.9
python -V
```

2) Create venv

```bash
python -m venv .venv
source .venv/bin/activate
python -V
```

3) Install dependencies

```bash
pip install -r requirements.txt
```

Optional ML dependencies (OpenCLIP etc.):

```bash
pip install -r requirements-ml.txt
```

If you want to prefetch model weights (helpful for offline demos):

```bash
python scripts/warmup_all.py
```

## Delivery / Packaging

We will likely ship:
- a CPU-only Docker image (runs anywhere)
- an optional GPU image/target (runs with NVIDIA runtime)

Development does not require Docker; we add it near the end as a packaging artifact.

## Documentation Sources

- Challenge brief: `challange-rules/ASAN müraciət (ENG).pdf`
- General terms: `challange-rules/Şərtlər və qaydalar.docx`
- Email questions sent to ASAN: `docs/asan-email-questions.txt`

## Open Questions (waiting on organizer response)

- Official category taxonomy and/or institution routing targets
- Priority definition criteria
- Dataset availability (size, labels, GPS metadata)
- Exact verification expectations (location only vs resolved)
- Deployment constraints (CPU-only vs GPU allowed in pilot)

Until then, we build with placeholder taxonomy and conservative verification decisions.
