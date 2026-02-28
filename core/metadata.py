from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GpsFix:
    lat: float
    lon: float


def _require_pillow():
    try:
        from PIL import Image, ExifTags  # type: ignore
    except Exception:
        return None
    return Image, ExifTags


def _rational_to_float(x) -> float | None:
    # Pillow may return either (num, den) tuples or Rational-like objects.
    try:
        if isinstance(x, tuple) and len(x) == 2:
            a, b = x
            return float(a) / float(b) if float(b) != 0.0 else None
        return float(x)
    except Exception:
        return None


def _dms_to_deg(dms, ref: str | None) -> float | None:
    try:
        deg = _rational_to_float(dms[0])
        mins = _rational_to_float(dms[1])
        secs = _rational_to_float(dms[2])
        if deg is None or mins is None or secs is None:
            return None
        out = deg + (mins / 60.0) + (secs / 3600.0)
        if ref and str(ref).upper() in {"S", "W"}:
            out = -out
        return out
    except Exception:
        return None


def extract_image_metadata(*, path: Path, gps_round_decimals: int = 5, include_gps: bool = True) -> dict:
    """Extract minimal privacy-conscious metadata from an image.

    Returns a small dict containing only fields we may use for location refinement/audit.
    """

    pillow = _require_pillow()
    if pillow is None:
        return {"available": False, "error": "pillow_not_installed"}

    Image, ExifTags = pillow
    try:
        im = Image.open(path)
    except Exception as exc:
        logger.debug("Failed to open image for metadata extraction: %s - %s", path, exc)
        return {"available": False, "error": "image_open_failed"}

    exif = None
    try:
        exif = im.getexif()
    except Exception:
        exif = None

    if not exif:
        im.close()
        return {"available": True, "has_exif": False}

    # Map numeric EXIF tag ids to names.
    tag_names = getattr(ExifTags, "TAGS", {})

    # DateTimeOriginal is common; keep it as a string.
    capture_time = None
    for k, v in exif.items():
        if str(tag_names.get(k, "")) == "DateTimeOriginal":
            try:
                capture_time = str(v)
            except Exception:
                capture_time = None
            break

    out: dict = {"available": True, "has_exif": True}
    if capture_time:
        out["capture_time"] = capture_time

    if include_gps:
        try:
            gps_ifd = exif.get_ifd(34853)  # GPSInfo
        except Exception:
            gps_ifd = None

        if isinstance(gps_ifd, dict) and gps_ifd:
            gps_tag_names = getattr(ExifTags, "GPSTAGS", {})
            gps_named = {str(gps_tag_names.get(k, k)): v for k, v in gps_ifd.items()}

            lat = _dms_to_deg(gps_named.get("GPSLatitude"), gps_named.get("GPSLatitudeRef"))
            lon = _dms_to_deg(gps_named.get("GPSLongitude"), gps_named.get("GPSLongitudeRef"))
            if lat is not None and lon is not None:
                out["gps"] = {
                    "lat": round(float(lat), int(gps_round_decimals)),
                    "lon": round(float(lon), int(gps_round_decimals)),
                    "source": "exif",
                }

    im.close()
    return out


def haversine_m(*, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * (math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return float(r * c)
