# Asan Eleda

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
  - evidence artifacts: signals, thresholds, frame selection (for audit/debug)

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
   - `evidence: {type, payload}[]`

`POST /verify`
- returns (conceptually):
  - `same_location: {score, decision, rationale}`
  - `resolved: {score, decision, rationale}`
  - `warnings: {code, message}[]`
  - `review_reasons: {code, signal, detail}[]` — structured reasons when decision is `needs_review` or `mismatch`
  - `evidence: {type, payload}[]` (optional)

Demo UI:
- `GET /demo` serves a simple single-page UI to upload media and call the API.

## Selecting A Pipeline Config

Default config is `config/pipeline.yaml`.

Category taxonomy config:
- Default is `config/categories.yaml` (v3 with ~28 categories)
- Legacy taxonomies available: `config/categories_basic_v2.yaml`, `config/categories_v3.yaml`
- Override with `CATEGORIES_CONFIG=path/to/categories.yaml`

To try a different engine mix without editing files, set `PIPELINE_CONFIG`:

```bash
PIPELINE_CONFIG=config/pipeline.openclip.yaml uvicorn app.main:app --reload
```

### Categorizer Confidence Calibration

When using `openclip_zeroshot`, the category `confidence` values are calibrated via a softmax over pooled similarities.
You can tune this in `config/pipeline.yaml` under `categorization`:

```yaml
categorization:
  confidence_method: softmax
  softmax_temperature: 0.25
```

Lower `softmax_temperature` makes the distribution peakier (more confident top-1), higher makes it flatter.

## Config-Driven Pieces

All items below are intended to be edited without code changes:

- `config/categories.yaml`
  - Default taxonomy with ~28 visually-distinguishable civic issue categories
  - Based on real-world 311 systems (NYC 311, Boston 311, FixMyStreet)
  - Override with `CATEGORIES_CONFIG` env var if needed
- `config/priority_rules.yaml`
  - rules and thresholds
- `config/thresholds.yaml`
  - warning thresholds for verification
- `config/pipeline.yaml`
  - which engine implementation to use (embedder/captioner/ocr/etc.)

### Category Taxonomy

The default taxonomy (`config/categories.yaml`) includes 28 categories across 6 groups:

| Group | Categories |
|-------|------------|
| Roads & Pavement | pothole, road_crack, manhole_cover, road_sign_damage, broken_sidewalk, sidewalk_obstruction, curb_damage |
| Lighting & Signals | street_light_out, damaged_light_pole, traffic_signal_malfunction |
| Water & Drainage | flooded_street, fire_hydrant_leak, clogged_drain, water_main_leak |
| Waste & Sanitation | overflowing_trash_bin, illegal_dumping, litter_debris, abandoned_furniture |
| Trees & Vegetation | fallen_tree, dead_tree, overgrown_vegetation, damaged_park |
| Property & Safety | graffiti, abandoned_vehicle, damaged_public_fixture, exposed_wiring, construction_hazard, hazardous_spill |

Plus `other` as a fallback category.

Each category includes synonyms to improve zero-shot classification accuracy.

### Review Reasons (Verify Endpoint)

When `/verify` returns `needs_review` or `mismatch` for either `same_location` or `resolved`, the response includes a `review_reasons` array explaining why:

```json
{
  "same_location": { "decision": "needs_review", ... },
  "resolved": { "decision": "needs_review", ... },
  "review_reasons": [
    {"code": "location_needs_review", "signal": "same_location", "detail": "Score 0.62 is between warn (0.60) and match (0.75) thresholds."},
    {"code": "gps_mismatch", "signal": "same_location", "detail": "GPS coordinates differ by ~312m (threshold: 250m)."}
  ]
}
```

This helps operators understand exactly why a case needs human review.

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

## Data Retention / Cleanup

Uploads and derived artifacts are stored under `data/uploads/` and `data/artifacts/`.

To delete old request directories (recommended for privacy), run:

```bash
python scripts/cleanup_storage.py --ttl-hours 168 --dry-run
python scripts/cleanup_storage.py --ttl-hours 168
```

## Evaluation Harness

You can evaluate the running API against a local manifest file (JSONL):

```bash
uvicorn app.main:app --port 8000
python scripts/eval_api.py --manifest eval/sample_manifest.jsonl --base-url http://127.0.0.1:8000
```

You can also run a local-only manifest against files in `testing-assets/`:

```bash
uvicorn app.main:app --port 8000
python scripts/eval_api.py --manifest eval/testing_assets_manifest.jsonl --base-url http://127.0.0.1:8000
```

Using the expanded basic taxonomy:

```bash
CATEGORIES_CONFIG=config/categories_basic_v2.yaml uvicorn app.main:app --port 8000
CATEGORIES_CONFIG=config/categories_basic_v2.yaml python scripts/eval_api.py --manifest eval/categories_basic_v2_manifest.jsonl --base-url http://127.0.0.1:8000
```

## Location Metadata (Optional)

When available, the API includes GPS metadata (EXIF for images, ffprobe tags for videos) in `evidence` for audit/location refinement.
This can be disabled or tuned in `config/pipeline.yaml` under `privacy`.

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
