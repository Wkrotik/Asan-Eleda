Local test fixtures.

This folder contains small media samples used to manually test the API and to run the evaluation harness.

- These files may contain GPS EXIF metadata.
- Do not upload sensitive media here.
- If you need to share the repo, consider disabling GPS evidence in `config/pipeline.yaml` (`privacy.include_gps_evidence: false`).

Suggested quick checks:
1) Start the API: `uvicorn app.main:app --port 8000`
2) Run eval: `python scripts/eval_api.py --manifest eval/testing_assets_manifest.jsonl --base-url http://127.0.0.1:8000`
