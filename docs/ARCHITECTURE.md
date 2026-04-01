# Architecture

System design and technical architecture for the ASAN Appeal AI system.

## Overview

The system is designed as a **modular, config-driven pipeline** where each component (captioning, OCR, classification, verification) can be swapped without changing the API contract.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                         │
├─────────────────────────────────────────────────────────────────────┤
│  POST /analyze                           POST /verify               │
│       │                                       │                     │
│       ▼                                       ▼                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                        Pipeline                              │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────────┐   │   │
│  │  │Captioner│ │   OCR   │ │Embedder │ │    Categorizer   │   │   │
│  │  │  (BLIP) │ │(EasyOCR)│ │(OpenCLIP)│ │(Zero-shot CLIP) │   │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └──────────────────┘   │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────────────────────────┐    │   │
│  │  │  Title  │ │Priority │ │         Verifier            │    │   │
│  │  │Generator│ │ (Rules) │ │   (Hybrid: CLIP + ORB)      │    │   │
│  │  └─────────┘ └─────────┘ └─────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Design Principles

### 1. Offline-Only
No external API calls. All ML models run locally on-premises. This is critical for government deployment where data cannot leave the local network.

### 2. Config-Driven
Engines are selected via YAML configuration, not hardcoded:

```yaml
# config/pipeline.yaml
engines:
  captioner: blip_base      # Can swap to: mock, other_model
  ocr: easyocr_v1           # Can swap to: tesseract, mock
  categorizer: openclip_zeroshot
  verifier: hybrid_v1
```

### 3. Conservative Verification
We prefer "needs_review" over false "resolved" claims. Thresholds are intentionally conservative:
- `>= 0.75` → match (confident)
- `0.60 - 0.75` → needs_review (uncertain)
- `< 0.60` → mismatch

### 4. Replaceable Taxonomy
Categories are loaded from `config/categories.yaml` and can be updated without code changes.

---

## ML Pipeline Components

### 1. Media Ingestor

**Purpose:** Load images/videos, extract keyframes, metadata.

| Type | Handler |
|------|---------|
| Images | Direct loading via PIL |
| Videos | FFmpeg keyframe extraction |

For videos, we extract multiple keyframes and aggregate results:
- Default: 8 frames max, 0.5 fps sampling
- Minimum: 3 frames (ensures short clips get coverage)

### 2. Captioner (BLIP)

**Model:** `Salesforce/blip-image-captioning-base`  
**Purpose:** Generate natural language descriptions of images.

```python
# Input: image
# Output: "a pothole in the road with water"
```

BLIP was chosen for:
- Good accuracy on diverse scenes
- Reasonable size (~990MB)
- Fits in 6GB VRAM alongside other models

### 3. OCR (EasyOCR)

**Languages:** Azerbaijani (`az`), English (`en`)  
**Purpose:** Extract text from images (signs, graffiti, notices).

```python
# Input: image with "STOP" sign
# Output: [{"text": "STOP", "confidence": 0.95, "bbox": [...]}]
```

EasyOCR was chosen for:
- Native Azerbaijani (Latin script) support
- Offline operation
- Good accuracy on scene text

### 4. Embedder (OpenCLIP)

**Model:** `ViT-B/32`  
**Purpose:** Generate image/text embeddings for similarity matching.

Used for:
- Zero-shot category classification
- Before/after image similarity

### 5. Categorizer (Zero-Shot CLIP)

**Method:** Compare image embedding to category label embeddings.

```python
categories = ["pothole", "graffiti", "fallen tree", ...]
similarities = cosine_similarity(image_embedding, text_embeddings)
top_k = sorted(similarities)[:3]
```

**Confidence Calibration:**
- Softmax over similarities with temperature=0.25
- Lower temperature → more confident top-1 predictions

### 6. Title Generator

**Method:** Template-based extraction from caption.

```
Input caption: "a pothole in the road surface"
Output title: "Road problems - Pothole"
```

Uses keyword matching to identify issue type, then formats as:
`[Category] - [Key Issue]`

### 7. Prioritizer (Rules-Based)

**Method:** Rule evaluation based on detected issues.

| Rule | Priority |
|------|----------|
| Safety hazard (exposed wires, open manhole) | High |
| Road damage (pothole, crack) | High |
| Cleanliness (litter, graffiti) | Low |
| Default | Medium |

### 8. Verifier (Hybrid)

**Method:** Combines CLIP similarity (70%) + ORB geometric matching (30%).

```
same_location_score = 0.7 * clip_similarity + 0.3 * orb_match_score
```

**CLIP Component:**
- Semantic similarity of scene content
- Robust to lighting/weather changes

**ORB Component:**
- Geometric keypoint matching
- Detects same physical structures

**Why hybrid?**
- CLIP alone can match "similar" scenes that aren't the same location
- ORB alone fails with viewpoint/zoom changes
- Combined approach handles both cases

---

## Data Flow

### Analyze Endpoint

```
1. Upload received
2. Store file → data/uploads/{request_id}/
3. Extract metadata (EXIF GPS if available)
4. If video: extract keyframes
5. Run captioner → description
6. Run OCR → text snippets
7. Generate title from caption
8. Run embedder → image vector
9. Run categorizer → top-3 categories
10. Run prioritizer → priority level
11. Return AnalyzeResponse
```

### Verify Endpoint

```
1. Upload before + after images
2. Store files → data/uploads/{request_id}/
3. Extract metadata for both
4. If videos: extract keyframes for both
5. Run embedder on both → vectors
6. Compute CLIP similarity
7. Run ORB keypoint matching
8. Compute hybrid same_location score
9. Analyze if issue resolved (caption comparison)
10. Return VerifyResponse with decisions
```

---

## Configuration Files

| File | Purpose |
|------|---------|
| `config/pipeline.yaml` | Engine selection, storage paths |
| `config/categories.yaml` | Category taxonomy with synonyms |
| `config/priority_rules.yaml` | Priority rule definitions |
| `config/thresholds.yaml` | Verification score thresholds |

### Swapping Engines

To use a different captioner:

```yaml
# config/pipeline.yaml
engines:
  captioner: my_new_captioner  # Implement in core/engines/
```

Then implement the interface in `core/engines/`:

```python
class MyNewCaptioner:
    def caption(self, image_path: Path) -> str:
        # Your implementation
        return "description of image"
```

---

## Memory Management

### GPU Memory (6GB Target)

| Model | Approximate Size |
|-------|-----------------|
| BLIP (captioning) | ~990MB |
| OpenCLIP ViT-B/32 | ~350MB |
| EasyOCR (az+en) | ~200MB |
| **Total** | **~1.5GB** |

Leaves ~4.5GB headroom for inference batches.

### Concurrency Control

```python
# core/concurrency.py
INFERENCE_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_INFERENCE)
```

Limits concurrent ML operations to prevent OOM:
- Default: 2 concurrent operations
- Configure via `MAX_CONCURRENT_INFERENCE` env var

### Model Caching

Models are cached in `data/model-cache/` after first download:
- Prevents re-download on restart
- Pre-download with `python scripts/warmup_all.py`

---

## Storage Layout

```
data/
├── uploads/
│   └── {request_id}/
│       ├── original.jpg
│       └── frames/          # For videos
│           ├── frame_001.jpg
│           ├── frame_002.jpg
│           └── ...
├── artifacts/
│   └── {request_id}/
│       └── ...              # Processing artifacts
└── model-cache/
    ├── blip-image-captioning-base/
    └── clip-vit-b-32/
```

### Cleanup

For privacy, old requests should be cleaned up:

```bash
python scripts/cleanup_storage.py --ttl-hours 168
```

---

## Video Processing

### Keyframe Extraction

Uses FFmpeg for efficient frame extraction:

```bash
ffmpeg -i video.mp4 -vf "fps=0.5" -frames:v 8 frame_%03d.jpg
```

Parameters (configurable in `pipeline.yaml`):
- `video_fps: 0.5` - Sample every 2 seconds
- `max_video_frames: 8` - Maximum frames to extract
- `min_video_frames: 3` - Minimum for short videos

### Aggregation

For videos, results are aggregated across frames:
- **Caption:** Most informative frame's caption
- **Categories:** Weighted average of confidences
- **OCR:** Union of all text found
- **Verification:** Best-matching frame pair

---

## Error Handling

### Graceful Degradation

If a component fails, the pipeline continues:

```python
try:
    ocr_result = self.ocr.extract(image)
except Exception as e:
    logger.warning(f"OCR failed: {e}")
    ocr_result = []  # Continue without OCR
    warnings.append(Warning(code="ocr_failed", message=str(e)))
```

### Confidence Warnings

Low-confidence results are flagged:

```python
if top_category.confidence < 0.5:
    warnings.append(Warning(
        code="low_category_confidence",
        message="Top category confidence below threshold"
    ))
```

---

## Testing Strategy

### Unit Tests (180 tests)

| Component | Tests |
|-----------|-------|
| Title generation | 38 |
| Description formatting | 24 |
| Verification edge cases | 19 |
| Utilities & helpers | 99 |

### Integration Tests

```bash
# Start server
uvicorn app.main:app --port 8000

# Run evaluation
python scripts/eval_api.py \
  --manifest eval/testing_assets_manifest.jsonl
```

### Performance Profiling

```bash
python scripts/profile_pipeline.py
```

Measures per-component timing:
- Captioning: ~200-400ms
- OCR: ~100-300ms
- Embedding: ~50-100ms
- Verification: ~300-500ms

---

## Security Considerations

### Data Privacy

- All processing is local (no cloud APIs)
- GPS metadata can be disabled: `privacy.include_gps_evidence: false`
- Automatic cleanup script for old data

### Input Validation

- File size limits enforced at upload
- Content-type validation
- Filename sanitization

### Logging

- Structured logging with request IDs
- No PII in logs (filenames are anonymized)
