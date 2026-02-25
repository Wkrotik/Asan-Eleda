from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests


def _read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                out.append(json.loads(line))
            except Exception as e:
                raise RuntimeError(f"Invalid JSONL at {path}:{i}: {e}")
    return out


def _post_multipart(url: str, files: dict):
    t0 = time.time()
    r = requests.post(url, files=files, timeout=300)
    dt_ms = int((time.time() - t0) * 1000)
    return r, dt_ms


def _decision_is_match(decision: dict) -> bool:
    return str(decision.get("decision")) == "match"


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline evaluation harness for /analyze and /verify")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--manifest", required=True, help="Path to JSONL manifest")
    ap.add_argument("--out", default="reports/eval_results.jsonl")
    ap.add_argument("--metrics-out", default="reports/metrics.json")
    args = ap.parse_args()

    base_url = str(args.base_url).rstrip("/")
    manifest_path = Path(args.manifest)
    out_path = Path(args.out)
    metrics_path = Path(args.metrics_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    cases = _read_jsonl(manifest_path)
    if not cases:
        raise RuntimeError("Manifest is empty")

    verify_total = 0
    verify_same_correct = 0
    verify_res_correct = 0
    verify_has_labels = 0

    analyze_total = 0
    analyze_top1_correct = 0
    analyze_top3_correct = 0
    analyze_has_labels = 0

    with out_path.open("w", encoding="utf-8") as outf:
        for idx, case in enumerate(cases):
            ctype = str(case.get("type", "")).strip()
            if ctype not in {"analyze", "verify"}:
                raise RuntimeError(f"Case {idx}: unknown type: {ctype}")

            record = {"case_index": idx, "type": ctype, "ok": False}

            if ctype == "analyze":
                media = Path(str(case.get("media")))
                if not media.exists():
                    raise RuntimeError(f"Case {idx}: media not found: {media}")

                with media.open("rb") as f:
                    r, dt_ms = _post_multipart(f"{base_url}/analyze", files={"file": (media.name, f)})

                record["latency_ms"] = dt_ms
                record["status_code"] = r.status_code
                if r.status_code != 200:
                    record["error"] = r.text[:2000]
                    outf.write(json.dumps(record) + "\n")
                    continue

                data = r.json()
                record["ok"] = True
                record["response"] = {
                    "request_id": data.get("request_id"),
                    "category_top_k": data.get("category_top_k"),
                    "priority": data.get("priority"),
                    "warnings": data.get("warnings"),
                }

                analyze_total += 1
                exp_cat = case.get("expect_category_id")
                if exp_cat is not None:
                    analyze_has_labels += 1
                    exp_cat = str(exp_cat)
                    top = data.get("category_top_k") or []
                    got_ids = [str(x.get("id")) for x in top if isinstance(x, dict)]
                    if got_ids:
                        if got_ids[0] == exp_cat:
                            analyze_top1_correct += 1
                        if exp_cat in got_ids[:3]:
                            analyze_top3_correct += 1

                outf.write(json.dumps(record) + "\n")
                continue

            # verify
            before = Path(str(case.get("before")))
            after = Path(str(case.get("after")))
            if not before.exists():
                raise RuntimeError(f"Case {idx}: before not found: {before}")
            if not after.exists():
                raise RuntimeError(f"Case {idx}: after not found: {after}")

            with before.open("rb") as fb, after.open("rb") as fa:
                r, dt_ms = _post_multipart(
                    f"{base_url}/verify",
                    files={
                        "before": (before.name, fb),
                        "after": (after.name, fa),
                    },
                )

            record["latency_ms"] = dt_ms
            record["status_code"] = r.status_code
            if r.status_code != 200:
                record["error"] = r.text[:2000]
                outf.write(json.dumps(record) + "\n")
                continue

            data = r.json()
            record["ok"] = True
            record["response"] = {
                "request_id": data.get("request_id"),
                "same_location": data.get("same_location"),
                "resolved": data.get("resolved"),
                "warnings": data.get("warnings"),
            }

            verify_total += 1
            exp_same = case.get("expect_same_location")
            exp_res = case.get("expect_resolved")
            if exp_same is not None or exp_res is not None:
                verify_has_labels += 1

            if exp_same is not None:
                got_same = _decision_is_match(data.get("same_location") or {})
                if bool(exp_same) == bool(got_same):
                    verify_same_correct += 1

            if exp_res is not None:
                got_res = _decision_is_match(data.get("resolved") or {})
                if bool(exp_res) == bool(got_res):
                    verify_res_correct += 1

            outf.write(json.dumps(record) + "\n")

    metrics = {
        "analyze": {
            "total": analyze_total,
            "labeled": analyze_has_labels,
            "top1_accuracy": (analyze_top1_correct / analyze_has_labels) if analyze_has_labels else None,
            "top3_accuracy": (analyze_top3_correct / analyze_has_labels) if analyze_has_labels else None,
        },
        "verify": {
            "total": verify_total,
            "labeled": verify_has_labels,
            "same_location_accuracy": (verify_same_correct / verify_has_labels) if verify_has_labels else None,
            "resolved_accuracy": (verify_res_correct / verify_has_labels) if verify_has_labels else None,
        },
        "outputs": {
            "results_jsonl": str(out_path),
        },
    }

    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
