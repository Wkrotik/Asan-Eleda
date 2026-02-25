# API Usage (MVP)

Run the dev server:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Analyze an image/video:

```bash
curl -s -X POST \
  -F "file=@/path/to/media.jpg" \
  http://127.0.0.1:8000/analyze | jq
```

Verify before vs after:

```bash
curl -s -X POST \
  -F "before=@/path/to/before.jpg" \
  -F "after=@/path/to/after.jpg" \
  http://127.0.0.1:8000/verify | jq
```

Notes:
- Engines are selected via `config/pipeline.yaml` (or `PIPELINE_CONFIG=...`).
- The JSON shapes are intended to stay stable as we swap/upgrade engines.

Retention cleanup (recommended for privacy):

```bash
python scripts/cleanup_storage.py --ttl-hours 168 --dry-run
python scripts/cleanup_storage.py --ttl-hours 168
```

Evaluation harness:

```bash
python scripts/eval_api.py --manifest eval/sample_manifest.jsonl --base-url http://127.0.0.1:8000
```
