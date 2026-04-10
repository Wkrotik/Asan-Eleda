# ASAN Appeal AI

Offline AI system for automated analysis and verification of citizen appeals for the ASAN platform.

## Overview

This system provides two core capabilities for the ASAN Appeal platform:

1. **Analyze** - Automatically process citizen-submitted photos/videos to generate:
   - Suggested title and description
   - Category classification (from ASAN's 7 official categories)
   - Priority level (High/Medium/Low)
   - OCR text extraction (Azerbaijani + English)

2. **Verify** - Compare "before" (citizen) and "after" (authority) images to:
   - Confirm same location
   - Verify issue resolution
   - Flag cases needing human review

**Key Feature:** Fully offline - no external cloud APIs. All ML models run locally on-premises.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install -r requirements-ml.txt

# 2. (Optional) Pre-download model weights
python scripts/warmup_all.py

# 3. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. Open demo UI
open http://localhost:8000/demo
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analyze` | POST | Analyze citizen media (image/video) |
| `/verify` | POST | Compare before/after images |
| `/demo` | GET | Interactive demo UI |
| `/healthz` | GET | Health check |

### POST /analyze

Upload an image or video to get automated analysis.

**Request:**
```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@pothole.jpg"
```

**Response:**
```json
{
  "request_id": "abc123",
  "suggested_title": "Road problems - Pothole",
  "generated_description": "A pothole in the road surface causing damage...",
  "tags": ["pothole", "road", "damage"],
  "ocr": [],
  "category_top_k": [
    {"id": "road_problems", "label": "Road problems", "confidence": 0.85},
    {"id": "infrastructure_repair", "label": "Infrastructure repair", "confidence": 0.10},
    {"id": "other", "label": "Other", "confidence": 0.05}
  ],
  "priority": {
    "level": "high",
    "confidence": 0.9,
    "rationale": "Road damage poses safety risk to vehicles"
  },
  "warnings": []
}
```

### POST /verify

Upload before and after images to verify resolution.

**Request:**
```bash
curl -X POST http://localhost:8000/verify \
  -F "before=@pothole_before.jpg" \
  -F "after=@pothole_after.jpg"
```

**Response:**
```json
{
  "request_id": "def456",
  "same_location": {
    "score": 0.92,
    "decision": "match",
    "rationale": "High visual similarity and geometric match"
  },
  "resolved": {
    "score": 0.88,
    "decision": "match",
    "rationale": "Issue no longer visible in after image"
  },
  "warnings": [],
  "review_reasons": []
}
```

## Categories

The system uses ASAN's 7 official categories:

| ID | English | Azerbaijani |
|----|---------|-------------|
| `utilities` | Utilities | Kommunal |
| `road_problems` | Road problems | Yol problemləri |
| `transport_problems` | Transport problems | Nəqliyyat problemləri |
| `infrastructure_repair` | Infrastructure repair | İnfrastrukturun təmiri |
| `infrastructure_improvement` | Infrastructure improvement | İnfrastrukturun abadlaşdırılması |
| `infrastructure_cleanliness` | Infrastructure cleanliness | İnfrastrukturun təmizliyi |
| `other` | Other | Digər |

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | NVIDIA with 4GB VRAM | RTX 4050 (6GB VRAM) |
| RAM | 8GB | 16GB |
| Storage | 5GB (models) | 10GB |
| Python | 3.11+ | 3.11.9 |

The system can also run on CPU-only, but inference will be slower.

## Project Structure

```
├── app/                    # FastAPI application
│   ├── main.py            # App entry point
│   ├── routes.py          # API endpoints
│   ├── schemas/           # Request/response models
│   └── ui.py              # Demo UI
├── core/                   # ML pipeline
│   ├── pipeline.py        # Main orchestrator
│   ├── title.py           # Title generation
│   ├── description.py     # Description formatting
│   └── engines/           # ML model implementations
│       ├── captioning.py
│       ├── openclip.py
│       ├── ocr.py
│       └── verify_hybrid.py
├── config/                 # Configuration
│   ├── categories.yaml    # ASAN 7 categories
│   ├── pipeline.yaml      # Engine selection
│   ├── priority_rules.yaml
│   └── thresholds.yaml    # Verification thresholds
├── scripts/               # Utilities
│   ├── warmup_all.py      # Pre-download models
│   ├── eval_api.py        # Evaluation harness
│   └── profile_pipeline.py
└── tests/                 # 180 unit tests
```

## ML Stack

| Component | Model | Purpose |
|-----------|-------|---------|
| Captioning | BLIP | Generate image descriptions |
| Embeddings | OpenCLIP ViT-B/32 | Zero-shot classification, similarity |
| OCR | EasyOCR (az, en) | Text extraction |
| Verification | CLIP + ORB | Hybrid similarity + geometric matching |

All models are chosen to fit within 6GB VRAM.

## Deployment

1. Native: use the Quick Start instructions above.
2. Docker and production notes: see `docs/DEPLOYMENT.md`.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov=app

# Run specific test file
pytest tests/test_title.py -v
```

180 unit tests covering:
- Title generation (38 tests)
- Description formatting (24 tests)
- Verification edge cases (19 tests)
- Core utilities (99 tests)

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PIPELINE_CONFIG` | Pipeline config path | `config/pipeline.yaml` |
| `CATEGORIES_CONFIG` | Categories config path | `config/categories.yaml` |
| `MAX_CONCURRENT_INFERENCE` | Concurrent ML operations | `2` |

### Verification Thresholds

Configured in `config/thresholds.yaml`:

```yaml
verification:
  match_threshold: 0.75    # Score >= 0.75 = "match"
  warn_threshold: 0.60     # Score 0.60-0.75 = "needs_review"
                           # Score < 0.60 = "mismatch"
```

Conservative thresholds minimize false positives - we prefer "needs_review" over incorrect "resolved" claims.

## Development Setup

```bash
# Using pyenv (recommended)
pyenv install 3.11.9
pyenv local 3.11.9

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-ml.txt
```

## Evaluation

Run evaluation against test assets:

```bash
# Start server
uvicorn app.main:app --port 8000

# Run evaluation
python scripts/eval_api.py \
  --manifest eval/testing_assets_manifest.jsonl \
  --base-url http://127.0.0.1:8000
```

## License

Proprietary - ASAN AI Hub Challenge Submission

## Documentation

- [API Reference](docs/API.md) - Detailed endpoint documentation
- [Architecture](docs/ARCHITECTURE.md) - System design and ML pipeline
- [Deployment](docs/DEPLOYMENT.md) - Installation and Docker setup
