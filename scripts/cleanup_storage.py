from __future__ import annotations

import argparse
import time
from pathlib import Path


def _iter_request_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    out: list[Path] = []
    for p in root.iterdir():
        if p.is_dir():
            out.append(p)
    return out


def _dir_mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except Exception:
        return 0.0


def _remove_tree(p: Path) -> None:
    # Avoid shutil.rmtree to keep behavior explicit and predictable.
    for child in sorted(p.rglob("*"), reverse=True):
        try:
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        except Exception:
            # Best effort; continue.
            pass
    try:
        p.rmdir()
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Delete stored uploads/artifacts older than a TTL")
    ap.add_argument("--uploads-dir", default="data/uploads")
    ap.add_argument("--artifacts-dir", default="data/artifacts")
    ap.add_argument("--ttl-hours", type=float, default=168.0, help="Age threshold in hours (default: 168h = 7 days)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    uploads_dir = Path(args.uploads_dir)
    artifacts_dir = Path(args.artifacts_dir)
    ttl_seconds = float(args.ttl_hours) * 3600.0
    now = time.time()

    targets: list[tuple[str, Path, float]] = []
    for root_name, root in (("uploads", uploads_dir), ("artifacts", artifacts_dir)):
        for d in _iter_request_dirs(root):
            age = now - _dir_mtime(d)
            if age >= ttl_seconds:
                targets.append((root_name, d, age))

    targets.sort(key=lambda x: x[2], reverse=True)

    if not targets:
        print("No expired request dirs found.")
        return 0

    for root_name, d, age in targets:
        hours = age / 3600.0
        if args.dry_run:
            print(f"DRY_RUN delete {root_name}: {d} (age_hours={hours:.1f})")
        else:
            _remove_tree(d)
            print(f"Deleted {root_name}: {d} (age_hours={hours:.1f})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
