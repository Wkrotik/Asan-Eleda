from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


_FFPROBE_TIMEOUT_S = 15
_FFMPEG_TIMEOUT_S = 60  # Longer timeout for ffmpeg frame extraction


VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def is_video_path(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS


@dataclass(frozen=True)
class ExtractedFrames:
    frames: list[Path]
    fps: float


def _run(cmd: list[str], timeout: int = _FFPROBE_TIMEOUT_S) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )


def probe_duration_s(video_path: Path) -> float:
    # Returns 0.0 if unknown.
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        p = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=_FFPROBE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        logger.debug("ffprobe duration timed out for %s", video_path)
        return 0.0
    except Exception as exc:
        logger.debug("ffprobe duration failed for %s: %s", video_path, exc)
        return 0.0

    if p.returncode != 0:
        return 0.0
    try:
        data = json.loads(p.stdout)
        dur = (data.get("format") or {}).get("duration")
        if dur is None:
            return 0.0
        d = float(dur)
        return d if d > 0 else 0.0
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.debug("ffprobe duration parse failed for %s: %s", video_path, exc)
        return 0.0


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
    try:
        p = _run(cmd)
    except subprocess.TimeoutExpired:
        logger.debug("ffprobe fps timed out for %s", video_path)
        return 0.0
    if p.returncode != 0:
        return 0.0
    try:
        data = json.loads(p.stdout)
        rr = data["streams"][0]["r_frame_rate"]
        if isinstance(rr, str) and "/" in rr:
            a, b = rr.split("/", 1)
            return float(a) / float(b)
        return float(rr)
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
        logger.debug("ffprobe fps parse failed for %s: %s", video_path, exc)
        return 0.0


def _parse_iso6709(s: str) -> tuple[float, float] | None:
    # Example: "+40.4096+049.8671/" or "+40.4096+049.8671+012.3/"
    s = s.strip()
    if not s or s[-1] != "/":
        return None
    s = s[:-1]
    # Find sign boundaries.
    if len(s) < 2:
        return None
    # Lat starts at 0.
    try:
        # Find start of lon sign after first char.
        lon_i = None
        for i in range(1, len(s)):
            if s[i] in {"+", "-"}:
                lon_i = i
                break
        if lon_i is None:
            return None
        lat = float(s[:lon_i])
        # Lon ends at next sign (alt) if present.
        alt_i = None
        for i in range(lon_i + 1, len(s)):
            if s[i] in {"+", "-"}:
                alt_i = i
                break
        lon = float(s[lon_i:alt_i] if alt_i is not None else s[lon_i:])
        return float(lat), float(lon)
    except Exception:
        return None


def probe_video_metadata(video_path: Path) -> dict:
    """Return minimal metadata from ffprobe format tags (best-effort)."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format_tags",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        p = _run(cmd)
    except subprocess.TimeoutExpired:
        return {"available": False, "error": "ffprobe_timeout"}
    if p.returncode != 0:
        return {"available": False, "error": "ffprobe_failed"}
    try:
        data = json.loads(p.stdout)
        tags = (data.get("format") or {}).get("tags") or {}
        if not isinstance(tags, dict):
            tags = {}
    except (json.JSONDecodeError, TypeError) as exc:
        logger.debug("ffprobe metadata parse failed for %s: %s", video_path, exc)
        return {"available": False, "error": "ffprobe_parse_failed"}

    out: dict = {"available": True}
    ct = tags.get("creation_time")
    if ct:
        out["creation_time"] = str(ct)

    # Location tags vary by device/container.
    loc = tags.get("location") or tags.get("location-eng") or tags.get("com.apple.quicktime.location.ISO6709")
    if loc:
        loc_s = str(loc)
        parsed = _parse_iso6709(loc_s)
        if parsed is not None:
            lat, lon = parsed
            out["gps"] = {"lat": float(lat), "lon": float(lon), "source": "ffprobe"}
        else:
            out["location_raw"] = loc_s

    return out


def extract_keyframes_ffmpeg(
    *,
    video_path: Path,
    out_dir: Path,
    fps: float = 0.5,
    max_frames: int = 8,
    min_frames: int = 0,
) -> ExtractedFrames:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Use both periodic sampling and scene-change sampling, then merge.
    # This helps short clips (fps may only yield 1 frame) and also catches meaningful changes.
    out_pattern_fps = out_dir / "fps_%03d.jpg"
    out_pattern_scene = out_dir / "scene_%03d.jpg"

    cmd_fps = [
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
        str(out_pattern_fps),
    ]

    # Scene threshold is conservative; we only need a few distinct frames.
    cmd_scene = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vf",
        "select='gt(scene,0.35)',showinfo",
        "-vsync",
        "vfr",
        "-q:v",
        "3",
        str(out_pattern_scene),
    ]
    p = _run(cmd_fps, timeout=_FFMPEG_TIMEOUT_S)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {p.stderr.strip()}")
    _ = _run(cmd_scene, timeout=_FFMPEG_TIMEOUT_S)

    frames = sorted(out_dir.glob("fps_*.jpg")) + sorted(out_dir.glob("scene_*.jpg"))

    # If the clip is short/static, fps+scene may yield too few frames.
    # Fall back to deterministic timestamp extraction to guarantee coverage.
    if min_frames and len(frames) < int(min_frames):
        dur_s = probe_duration_s(video_path)
        if dur_s > 0.0:
            target_n = int(min_frames)
            if max_frames > 0:
                target_n = min(target_n, int(max_frames))
            if target_n > 0:
                # Evenly spaced timestamps. Avoid exact 0 and exact end.
                eps = 0.01
                if dur_s <= 2 * eps:
                    ts = [0.0 for _ in range(target_n)]
                elif target_n == 1:
                    ts = [min(0.1, max(eps, dur_s / 2.0))]
                else:
                    step = dur_s / float(target_n - 1)
                    ts = [min(dur_s - eps, max(eps, i * step)) for i in range(target_n)]

                for i, t in enumerate(ts):
                    out_path = out_dir / f"ts_{i:03d}.jpg"
                    cmd_ts = [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-ss",
                        f"{t:.3f}",
                        "-i",
                        str(video_path),
                        "-frames:v",
                        "1",
                        "-q:v",
                        "3",
                        str(out_path),
                    ]
                    _ = _run(cmd_ts, timeout=_FFMPEG_TIMEOUT_S)

                frames = frames + sorted(out_dir.glob("ts_*.jpg"))

    # De-dupe and cap.
    seen: set[str] = set()
    uniq: list[Path] = []
    for f in frames:
        k = str(f)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(f)
    if max_frames > 0 and len(uniq) > max_frames:
        uniq = uniq[:max_frames]
    return ExtractedFrames(frames=uniq, fps=fps)
