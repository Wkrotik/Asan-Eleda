from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def is_video_path(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS


@dataclass(frozen=True)
class ExtractedFrames:
    frames: list[Path]
    fps: float


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def probe_fps(video_path: Path) -> float:
    # Returns 0.0 if unknown.
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=r_frame_rate",
        "-of",
        "json",
        str(video_path),
    ]
    p = _run(cmd)
    if p.returncode != 0:
        return 0.0
    try:
        data = json.loads(p.stdout)
        rr = data["streams"][0]["r_frame_rate"]
        if isinstance(rr, str) and "/" in rr:
            a, b = rr.split("/", 1)
            return float(a) / float(b)
        return float(rr)
    except Exception:
        return 0.0


def extract_keyframes_ffmpeg(
    *,
    video_path: Path,
    out_dir: Path,
    fps: float = 0.5,
    max_frames: int = 8,
) -> ExtractedFrames:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Extract at a fixed FPS to keep compute bounded.
    # Use JPEG to keep file sizes down.
    out_pattern = out_dir / "frame_%03d.jpg"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps}",
        "-q:v",
        "3",
        str(out_pattern),
    ]
    p = _run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {p.stderr.strip()}")

    frames = sorted(out_dir.glob("frame_*.jpg"))
    if max_frames > 0 and len(frames) > max_frames:
        frames = frames[:max_frames]
    return ExtractedFrames(frames=[f for f in frames], fps=fps)
