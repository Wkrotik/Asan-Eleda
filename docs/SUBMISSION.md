# ASAN Appeal AI (Offline) - Submission Summary

## Problem

ASAN receives citizen appeals with photos/videos describing municipal issues. Manual triage is slow and inconsistent, and resolution verification (before/after) is time-consuming.

## Solution

ASAN Appeal AI is an **offline, on-premises** service that automates two tasks:

1. **Analyze** citizen-submitted media (image/video):
   - Suggested title
   - Generated description
   - Category (ASAN official 7 categories)
   - Priority (High/Medium/Low)
   - OCR (Azerbaijani + English)

2. **Verify** authority “after” media against the citizen “before” media:
   - Same location decision
   - Resolved decision
   - Conservative “needs_review” path when uncertain

The system runs fully offline: **no cloud APIs** and no external data transfer.

## API

1. `POST /analyze` accepts one file (`multipart/form-data`, field `file`).
2. `POST /verify` accepts two files (`multipart/form-data`, fields `before`, `after`).
3. `GET /demo` provides a no-build HTML UI.
4. `GET /healthz` provides a health check.

See `docs/API.md` for full request/response schemas.

## Categories

The categorizer outputs the official ASAN 7 categories:

1. `utilities`
2. `road_problems`
3. `transport_problems`
4. `infrastructure_repair`
5. `infrastructure_improvement`
6. `infrastructure_cleanliness`
7. `other`

The taxonomy is configurable via `config/categories.yaml`.

## Architecture

The service is a FastAPI app with a config-driven pipeline:

1. Media ingest (image/video)
2. Video keyframes extraction (FFmpeg)
3. Captioning (BLIP)
4. OCR (EasyOCR)
5. Categorization (default: keyword matching over the caption)
6. Title/description generation
7. Priority suggestion (rules)
8. Verification (hybrid similarity + geometric matching)

See `docs/ARCHITECTURE.md` for details.

## Offline / On-Prem Notes

1. Model weights are cached to `data/model-cache/`.
2. Uploads and artifacts are stored under `data/uploads/` and `data/artifacts/`.
3. For privacy, stored uploads should be cleaned periodically (script: `scripts/cleanup_storage.py`).
4. Concurrency is limited to avoid GPU OOM via `MAX_CONCURRENT_INFERENCE`.

## Deployment

Supported deployment modes:

1. **Native Python** (dev or on-prem without containers)
2. **Docker CPU** (`Dockerfile.cpu`)
3. **Docker GPU** (`Dockerfile.gpu`, NVIDIA Container Toolkit required)

See `docs/DEPLOYMENT.md` for the full guide.

## How To Run (Quick)

```bash
pip install -r requirements.txt
pip install -r requirements-ml.txt
python scripts/warmup_all.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open demo UI: `http://localhost:8000/demo`
