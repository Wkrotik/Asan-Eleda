# ASAN Appeal AI (Offline) - Submission Summary

GitHub repository: https://github.com/Wkrotik/Asan-Eleda

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

## Integration Approach

The solution is designed for API-based integration:

1. ASAN Appeal platform uploads citizen media to `POST /analyze` to obtain structured fields (title, description, category, priority, OCR).
2. After a responsible authority provides “after” media, ASAN Appeal calls `POST /verify` (before+after) to obtain same-location and resolved decisions.

The pipeline is config-driven (`config/pipeline.yaml`) and can also be embedded as a module if ASAN prefers in-process integration.

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

## Pilot Implementation Plan (Proposed)

1. Week 1: Deploy to staging on-prem node (CPU or GPU), validate offline model caching, connect to a staging ASAN endpoint.
2. Week 2: Run pilot on a small subset of appeals, measure categorization accuracy and verification reliability, tune thresholds/keywords.
3. Week 3: Expand pilot volume, add monitoring/logging/cleanup schedule aligned with retention requirements.
4. Week 4: Production hardening, documentation handoff, and rollout plan.

Timeline can be shortened/expanded depending on ASAN infrastructure readiness.

## Team, Experience, Legal Status

Add the following to match the ASAN AI Hub application form:

1. Team members: names, roles (ML/CV, backend, DevOps), contact emails.
2. Previous experience: relevant projects in computer vision, offline/on-prem deployments, public sector integrations.
3. Legal status: individual / company name and registration details (if applicable).

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
