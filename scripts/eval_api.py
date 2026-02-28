from __future__ import annotations

import argparse
import json
import sys
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


def _post_multipart(url: str, files: dict, retries: int = 2, retry_delay: float = 1.0):
    """POST with optional retry on transient failures."""
    last_exc = None
    for attempt in range(retries + 1):
        try:
            t0 = time.time()
            r = requests.post(url, files=files, timeout=300)
            dt_ms = int((time.time() - t0) * 1000)
            return r, dt_ms
        except requests.exceptions.RequestException as e:
            last_exc = e
            if attempt < retries:
                time.sleep(retry_delay)
    raise RuntimeError(f"Request failed after {retries + 1} attempts: {last_exc}")


def _decision_is_match(decision: dict) -> bool:
    return str(decision.get("decision")) == "match"


def _has_warning(data: dict, code: str) -> bool:
    for w in (data.get("warnings") or []):
        if isinstance(w, dict) and str(w.get("code")) == code:
            return True
    return False


def _extract_gps_distance_m(data: dict) -> float | None:
    # verify response: evidence -> verify_signals -> payload -> metadata -> gps_distance_m
    try:
        for ev in (data.get("evidence") or []):
            if isinstance(ev, dict) and ev.get("type") == "verify_signals":
                md = (ev.get("payload") or {}).get("metadata") or {}
                val = md.get("gps_distance_m")
                return None if val is None else float(val)
    except Exception:
        return None
    return None


def _latency_stats(latencies: list[int]) -> dict:
    """Compute min/max/mean/p95 latency in ms."""
    if not latencies:
        return {"min_ms": None, "max_ms": None, "mean_ms": None, "p95_ms": None}
    sorted_lats = sorted(latencies)
    n = len(sorted_lats)
    p95_idx = min(int(n * 0.95), n - 1)
    return {
        "min_ms": sorted_lats[0],
        "max_ms": sorted_lats[-1],
        "mean_ms": int(sum(sorted_lats) / n),
        "p95_ms": sorted_lats[p95_idx],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline evaluation harness for /analyze and /verify")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--manifest", required=True, help="Path to JSONL manifest")
    ap.add_argument("--out", default="reports/eval_results.jsonl")
    ap.add_argument("--metrics-out", default="reports/metrics.json")
    ap.add_argument("-v", "--verbose", action="store_true", help="Print progress for each case")
    args = ap.parse_args()

    base_url = str(args.base_url).rstrip("/")
    manifest_path = Path(args.manifest)
    out_path = Path(args.out)
    metrics_path = Path(args.metrics_out)
    verbose = args.verbose
    out_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    cases = _read_jsonl(manifest_path)
    if not cases:
        raise RuntimeError("Manifest is empty")

    verify_total = 0
    verify_same_correct = 0
    verify_res_correct = 0
    verify_same_labeled = 0
    verify_res_labeled = 0

    analyze_total = 0
    analyze_top1_correct = 0
    analyze_top3_correct = 0
    analyze_has_labels = 0

    # Track latencies and pass/fail counts
    analyze_latencies: list[int] = []
    verify_latencies: list[int] = []
    passed = 0
    failed = 0

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

                if verbose:
                    print(f"[{idx + 1}/{len(cases)}] analyze: {media.name} ...", end=" ", flush=True)

                with media.open("rb") as f:
                    r, dt_ms = _post_multipart(f"{base_url}/analyze", files={"file": (media.name, f)})

                analyze_latencies.append(dt_ms)
                record["latency_ms"] = dt_ms
                record["status_code"] = r.status_code
                if r.status_code != 200:
                    record["error"] = r.text[:2000]
                    outf.write(json.dumps(record) + "\n")
                    failed += 1
                    if verbose:
                        print(f"FAIL (HTTP {r.status_code})")
                    continue

                data = r.json()
                record["ok"] = True
                record["response"] = {
                    "request_id": data.get("request_id"),
                    "category_top_k": data.get("category_top_k"),
                    "priority": data.get("priority"),
                    "warnings": data.get("warnings"),
                }

                # Optional evidence checks (best-effort)
                exp_min_frames = case.get("expect_min_video_frames")
                if exp_min_frames is not None:
                    got_frames = None
                    try:
                        for ev in (data.get("evidence") or []):
                            if isinstance(ev, dict) and ev.get("type") == "category_aggregation":
                                frames_val = (ev.get("payload") or {}).get("frames_used")
                                got_frames = None if frames_val is None else int(frames_val)
                                break
                    except Exception:
                        got_frames = None

                    record["video_expectations"] = {
                        "expect_min_video_frames": int(exp_min_frames),
                        "got_frames_used": got_frames,
                    }
                    if got_frames is None or got_frames < int(exp_min_frames):
                        record["ok"] = False
                        record["error"] = "Video min-frames expectation failed"

                exp_ocr_agg = case.get("expect_ocr_aggregation")
                if exp_ocr_agg is not None:
                    got_ocr_agg = False
                    try:
                        for ev in (data.get("evidence") or []):
                            if isinstance(ev, dict) and ev.get("type") == "ocr_aggregation":
                                got_ocr_agg = True
                                break
                    except Exception:
                        got_ocr_agg = False

                    rec = record.get("video_expectations") or {}
                    if not isinstance(rec, dict):
                        rec = {}
                    rec["expect_ocr_aggregation"] = bool(exp_ocr_agg)
                    rec["got_ocr_aggregation"] = bool(got_ocr_agg)
                    record["video_expectations"] = rec
                    if bool(got_ocr_agg) != bool(exp_ocr_agg):
                        record["ok"] = False
                        record["error"] = "OCR aggregation expectation failed"

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

                    # Track labeled accuracy for this case even if API disagrees.
                    if exp_cat not in got_ids[:3]:
                        record.setdefault("label_mismatch", {})
                        record["label_mismatch"] = {"expect_category_id": exp_cat, "got_ids": got_ids[:3]}

                if record["ok"]:
                    passed += 1
                    if verbose:
                        print(f"OK ({dt_ms}ms)")
                else:
                    failed += 1
                    if verbose:
                        print(f"FAIL ({record.get('error', 'expectation failed')})")

                outf.write(json.dumps(record) + "\n")
                continue

            # verify
            before = Path(str(case.get("before")))
            after = Path(str(case.get("after")))
            if not before.exists():
                raise RuntimeError(f"Case {idx}: before not found: {before}")
            if not after.exists():
                raise RuntimeError(f"Case {idx}: after not found: {after}")

            if verbose:
                print(f"[{idx + 1}/{len(cases)}] verify: {before.name} vs {after.name} ...", end=" ", flush=True)

            with before.open("rb") as fb, after.open("rb") as fa:
                r, dt_ms = _post_multipart(
                    f"{base_url}/verify",
                    files={
                        "before": (before.name, fb),
                        "after": (after.name, fa),
                    },
                )

            verify_latencies.append(dt_ms)
            record["latency_ms"] = dt_ms
            record["status_code"] = r.status_code
            if r.status_code != 200:
                record["error"] = r.text[:2000]
                outf.write(json.dumps(record) + "\n")
                failed += 1
                if verbose:
                    print(f"FAIL (HTTP {r.status_code})")
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

            if exp_same is not None:
                verify_same_labeled += 1
                got_same = _decision_is_match(data.get("same_location") or {})
                if bool(exp_same) == bool(got_same):
                    verify_same_correct += 1

            if exp_res is not None:
                verify_res_labeled += 1
                got_res = _decision_is_match(data.get("resolved") or {})
                if bool(exp_res) == bool(got_res):
                    verify_res_correct += 1

            # Optional GPS expectations (verify only)
            exp_gps_mismatch = case.get("expect_gps_mismatch")
            if exp_gps_mismatch is not None:
                got = _has_warning(data, "gps_mismatch")
                record["gps_expectations"] = {
                    "expect_gps_mismatch": bool(exp_gps_mismatch),
                    "got_gps_mismatch": bool(got),
                    "gps_distance_m": _extract_gps_distance_m(data),
                }
                if bool(got) != bool(exp_gps_mismatch):
                    record["ok"] = False
                    record["error"] = "GPS expectation failed"

            if record["ok"]:
                passed += 1
                if verbose:
                    print(f"OK ({dt_ms}ms)")
            else:
                failed += 1
                if verbose:
                    print(f"FAIL ({record.get('error', 'expectation failed')})")

            outf.write(json.dumps(record) + "\n")

    metrics = {
        "summary": {
            "total_cases": len(cases),
            "passed": passed,
            "failed": failed,
        },
        "analyze": {
            "total": analyze_total,
            "labeled": analyze_has_labels,
            "top1_accuracy": (analyze_top1_correct / analyze_has_labels) if analyze_has_labels else None,
            "top3_accuracy": (analyze_top3_correct / analyze_has_labels) if analyze_has_labels else None,
            "latency": _latency_stats(analyze_latencies),
        },
        "verify": {
            "total": verify_total,
            "labeled_same_location": verify_same_labeled,
            "labeled_resolved": verify_res_labeled,
            "same_location_accuracy": (verify_same_correct / verify_same_labeled) if verify_same_labeled else None,
            "resolved_accuracy": (verify_res_correct / verify_res_labeled) if verify_res_labeled else None,
            "latency": _latency_stats(verify_latencies),
        },
        "outputs": {
            "results_jsonl": str(out_path),
        },
    }

    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))

    # Print summary to stderr for quick visibility
    print(f"\n=== Evaluation Summary ===", file=sys.stderr)
    print(f"Total: {len(cases)} | Passed: {passed} | Failed: {failed}", file=sys.stderr)
    if analyze_has_labels:
        t1 = analyze_top1_correct / analyze_has_labels * 100
        t3 = analyze_top3_correct / analyze_has_labels * 100
        print(f"Analyze accuracy: top1={t1:.1f}% top3={t3:.1f}% (n={analyze_has_labels})", file=sys.stderr)
    if verify_same_labeled:
        acc = verify_same_correct / verify_same_labeled * 100
        print(f"Verify same_location accuracy: {acc:.1f}% (n={verify_same_labeled})", file=sys.stderr)
    if verify_res_labeled:
        acc = verify_res_correct / verify_res_labeled * 100
        print(f"Verify resolved accuracy: {acc:.1f}% (n={verify_res_labeled})", file=sys.stderr)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
