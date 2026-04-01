# API Reference

Complete API documentation for the ASAN Appeal AI system.

## Base URL

```
http://localhost:8000
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analyze` | POST | Analyze citizen media |
| `/verify` | POST | Verify issue resolution |
| `/demo` | GET | Interactive demo UI |
| `/healthz` | GET | Health check |

---

## POST /analyze

Analyze a citizen-submitted image or video to generate title, description, category, and priority.

### Request

**Content-Type:** `multipart/form-data`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | file | Yes | Image (JPEG, PNG, WebP) or video (MP4, MOV) |

**Supported formats:**
- Images: JPEG, PNG, WebP, GIF, BMP
- Videos: MP4, MOV, AVI, MKV, WebM

**Size limits:**
- Images: 20MB
- Videos: 100MB

### Example Request

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@pothole.jpg"
```

### Response

```json
{
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "media": {
    "filename": "pothole.jpg",
    "content_type": "image/jpeg",
    "size_bytes": 245678
  },
  "suggested_title": "Road problems - Pothole",
  "generated_description": "A large pothole in the asphalt road surface, approximately 30cm in diameter, with crumbling edges and standing water.",
  "tags": ["pothole", "road damage", "asphalt", "water"],
  "ocr": [],
  "category_top_k": [
    {
      "id": "road_problems",
      "label": "Road problems",
      "confidence": 0.847
    },
    {
      "id": "infrastructure_repair",
      "label": "Infrastructure repair",
      "confidence": 0.098
    },
    {
      "id": "transport_problems",
      "label": "Transport problems",
      "confidence": 0.032
    }
  ],
  "priority": {
    "level": "high",
    "confidence": 0.85,
    "rationale": "Road damage poses immediate safety risk to vehicles and pedestrians"
  },
  "warnings": [],
  "evidence": []
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Unique identifier for this request |
| `media` | object | Metadata about the uploaded file |
| `suggested_title` | string | Auto-generated title (format: `[Category] - [Issue]`) |
| `generated_description` | string | AI-generated description of the image/video |
| `tags` | string[] | Visual concepts detected in the media |
| `ocr` | OcrItem[] | Text extracted from the image (if any) |
| `category_top_k` | CategoryCandidate[] | Top 3 category predictions with confidence |
| `priority` | PrioritySuggestion | Suggested priority level |
| `warnings` | Warning[] | Any warnings (low confidence, etc.) |
| `evidence` | object[] | Additional evidence (GPS, etc.) |

### Types

**OcrItem:**
```json
{
  "text": "STOP",
  "confidence": 0.95,
  "bbox": [100, 200, 150, 250]
}
```

**CategoryCandidate:**
```json
{
  "id": "road_problems",
  "label": "Road problems",
  "confidence": 0.85
}
```

**PrioritySuggestion:**
```json
{
  "level": "high",
  "confidence": 0.85,
  "rationale": "Explanation for the priority level"
}
```
- `level`: One of `"high"`, `"medium"`, `"low"`

**Warning:**
```json
{
  "code": "low_category_confidence",
  "message": "Top category confidence is below 0.5"
}
```

### Error Responses

| Status | Description |
|--------|-------------|
| 413 | File too large |
| 415 | Unsupported media type |
| 422 | Validation error (missing file, etc.) |

---

## POST /verify

Compare "before" (citizen-submitted) and "after" (authority-submitted) images to verify:
1. Same location - Are both images of the same place?
2. Resolved - Has the issue been fixed?

### Request

**Content-Type:** `multipart/form-data`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `before` | file | Yes | Original citizen image |
| `after` | file | Yes | Follow-up authority image |

### Example Request

```bash
curl -X POST http://localhost:8000/verify \
  -F "before=@pothole_before.jpg" \
  -F "after=@pothole_after.jpg"
```

### Response

```json
{
  "request_id": "f1e2d3c4-b5a6-7890-fedc-ba0987654321",
  "before": {
    "filename": "pothole_before.jpg",
    "content_type": "image/jpeg"
  },
  "after": {
    "filename": "pothole_after.jpg",
    "content_type": "image/jpeg"
  },
  "same_location": {
    "score": 0.92,
    "decision": "match",
    "rationale": "High visual similarity (0.92) with strong geometric correspondence (47 keypoint matches)"
  },
  "resolved": {
    "score": 0.88,
    "decision": "match",
    "rationale": "Original issue (pothole) no longer visible in after image; road surface appears repaired"
  },
  "warnings": [],
  "review_reasons": [],
  "evidence": []
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Unique identifier for this request |
| `before` | object | Metadata about the before image |
| `after` | object | Metadata about the after image |
| `same_location` | VerifyDecision | Location matching result |
| `resolved` | VerifyDecision | Resolution verification result |
| `warnings` | Warning[] | Any warnings |
| `review_reasons` | ReviewReason[] | Detailed reasons when `needs_review` |
| `evidence` | object[] | Additional evidence |

### VerifyDecision

```json
{
  "score": 0.92,
  "decision": "match",
  "rationale": "Explanation of the decision"
}
```

- `score`: 0.0 to 1.0
- `decision`: One of:
  - `"match"` - Confirmed (score >= 0.75)
  - `"needs_review"` - Uncertain, requires human review (score 0.60-0.75)
  - `"mismatch"` - Not a match (score < 0.60)

### ReviewReason

When either decision is `needs_review`, detailed reasons are provided:

```json
{
  "code": "location_needs_review",
  "signal": "same_location",
  "detail": "Score 0.68 is between warn (0.60) and match (0.75) thresholds"
}
```

| Field | Description |
|-------|-------------|
| `code` | Machine-readable reason code |
| `signal` | Which check triggered this (`same_location` or `resolved`) |
| `detail` | Human-readable explanation |

### Common Review Reason Codes

| Code | Signal | Description |
|------|--------|-------------|
| `location_needs_review` | same_location | Score in uncertain range |
| `location_mismatch` | same_location | Images appear to be different locations |
| `low_keypoint_matches` | same_location | Insufficient geometric correspondence |
| `resolution_unclear` | resolved | Cannot determine if issue was fixed |
| `issue_still_visible` | resolved | Original problem appears unchanged |

---

## GET /healthz

Health check endpoint for monitoring and load balancers.

### Response

```json
{
  "ok": true
}
```

---

## GET /demo

Serves an interactive HTML demo UI for testing the API.

Open in browser: `http://localhost:8000/demo`

---

## Categories

The system classifies appeals into ASAN's 7 official categories:

| ID | Label (EN) | Label (AZ) |
|----|------------|------------|
| `utilities` | Utilities | Kommunal |
| `road_problems` | Road problems | Yol problemləri |
| `transport_problems` | Transport problems | Nəqliyyat problemləri |
| `infrastructure_repair` | Infrastructure repair | İnfrastrukturun təmiri |
| `infrastructure_improvement` | Infrastructure improvement | İnfrastrukturun abadlaşdırılması |
| `infrastructure_cleanliness` | Infrastructure cleanliness | İnfrastrukturun təmizliyi |
| `other` | Other | Digər |

---

## Priority Levels

| Level | Azerbaijani | Description |
|-------|-------------|-------------|
| `high` | Yuxarı | Safety hazards, urgent issues |
| `medium` | Orta | Significant but not urgent |
| `low` | Aşağı | Minor issues, cosmetic |

---

## Error Handling

All errors return JSON with a `detail` field:

```json
{
  "detail": "File size exceeds maximum allowed (20MB for images)"
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 413 | Payload too large |
| 415 | Unsupported media type |
| 422 | Validation error |
| 500 | Internal server error |

---

## Rate Limiting

The API uses a concurrency limiter to prevent GPU memory exhaustion:
- Default: 2 concurrent ML inference operations
- Configure via `MAX_CONCURRENT_INFERENCE` environment variable

Requests exceeding the limit will queue, not fail.

---

## OpenAPI Documentation

Interactive API docs are available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
