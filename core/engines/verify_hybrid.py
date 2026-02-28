from __future__ import annotations

import logging
from dataclasses import dataclass

from core.engines.openclip import get_openclip_context, load_image
from core.media import MediaRef

logger = logging.getLogger(__name__)


def _require_cv2():
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Hybrid verifier requires optional deps. Install with: pip install -r requirements-ml.txt"
        ) from e
    return cv2, np


def _to_gray_np(path) -> "tuple[object, object]":
    cv2, np = _require_cv2()
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise RuntimeError(f"Failed to read image: {path}")
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return gray, bgr


def _orb_match_score(img1_gray, img2_gray) -> tuple[float, int, int, object | None]:
    """Return (score, num_matches, num_inliers, H) where H is homography or None."""
    cv2, _ = _require_cv2()

    orb = cv2.ORB_create(nfeatures=1500)
    kp1, des1 = orb.detectAndCompute(img1_gray, None)
    kp2, des2 = orb.detectAndCompute(img2_gray, None)
    if des1 is None or des2 is None or len(kp1) < 8 or len(kp2) < 8:
        return 0.0, 0, 0, None

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)
    matches = sorted(matches, key=lambda m: m.distance)
    if len(matches) < 12:
        return 0.0, len(matches), 0, None

    # Use top matches for homography.
    keep = matches[: min(120, len(matches))]
    src = [kp1[m.queryIdx].pt for m in keep]
    dst = [kp2[m.trainIdx].pt for m in keep]
    import numpy as np  # local

    src_pts = np.array(src, dtype=np.float32).reshape(-1, 1, 2)
    dst_pts = np.array(dst, dtype=np.float32).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
    inliers = int(mask.sum()) if mask is not None else 0

    # Normalize by the number of evaluated matches.
    denom = max(1, len(keep))
    score = max(0.0, min(1.0, inliers / float(denom)))
    # Some OpenCV builds return H as a list; normalize to ndarray-like or None.
    if H is None:
        return score, len(keep), inliers, None
    try:
        import numpy as np  # local

        H = np.asarray(H, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        logger.debug("Homography conversion failed: %s", exc)
        return score, len(keep), inliers, None
    return score, len(keep), inliers, H


def _difference_ratio_aligned(before_bgr, after_bgr, H: object | None) -> float:
    cv2, np = _require_cv2()
    if H is None:
        return 1.0

    h, w = before_bgr.shape[:2]
    warped = cv2.warpPerspective(after_bgr, H, (w, h))
    before_g = cv2.cvtColor(before_bgr, cv2.COLOR_BGR2GRAY)
    warped_g = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

    diff = cv2.absdiff(before_g, warped_g)
    # Threshold: ignore tiny noise.
    _, thr = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    changed = int(np.count_nonzero(thr))
    total = int(thr.size)
    return changed / float(total) if total else 1.0


@dataclass
class HybridVerifierV1:
    """Same-location: OpenCLIP similarity + ORB keypoint geometry.

    Resolved: conservative heuristic based on same-location confidence and visual change ratio.
    """

    model_name: str = "ViT-B-32"
    pretrained: str = "laion2b_s34b_b79k"
    device: str | None = None

    def clip_embed(self, *, media: MediaRef):
        ctx = get_openclip_context(self.model_name, self.pretrained, self.device)
        return ctx.encode_image(load_image(media.path))

    @staticmethod
    def _clip_score_from_sim(clip_sim: float) -> float:
        return max(0.0, min(1.0, (float(clip_sim) + 1.0) / 2.0))

    def clip_similarity(self, *, before_vec, after_vec) -> tuple[float, float]:
        clip_sim = float((before_vec @ after_vec).item())
        return clip_sim, self._clip_score_from_sim(clip_sim)

    def orb_signals(self, *, before: MediaRef, after: MediaRef) -> dict:
        b_gray, _ = _to_gray_np(before.path)
        a_gray, _ = _to_gray_np(after.path)
        orb_score, num_matches, inliers, H = _orb_match_score(b_gray, a_gray)
        return {"score": float(orb_score), "matches": int(num_matches), "inliers": int(inliers), "homography": H}

    @staticmethod
    def _blend(clip_score: float, orb_score: float) -> float:
        return max(0.0, min(1.0, 0.70 * float(clip_score) + 0.30 * float(orb_score)))

    def same_location_with_clip(
        self,
        *,
        before: MediaRef,
        after: MediaRef,
        clip_sim: float,
        clip_score: float,
    ) -> tuple[float, str, dict]:
        orb = self.orb_signals(before=before, after=after)
        orb_score = float(orb["score"])
        score = self._blend(clip_score, orb_score)
        rationale = (
            f"Hybrid same-location: clip={clip_score:.3f} (sim={float(clip_sim):.3f}), "
            f"orb={orb_score:.3f} (matches={orb['matches']}, inliers={orb['inliers']})."
        )
        ev = {
            "clip": {
                "similarity": float(clip_sim),
                "score": float(clip_score),
                "model": {"name": self.model_name, "pretrained": self.pretrained},
            },
            "orb": {
                "score": orb_score,
                "matches": orb["matches"],
                "inliers": orb["inliers"],
                "has_homography": bool(orb.get("homography") is not None),
            },
            "blend": {"score": score, "weights": {"clip": 0.70, "orb": 0.30}},
        }
        # Store homography as a small JSON-serializable 3x3 matrix when available.
        H = orb.get("homography")
        if H is not None:
            try:
                _cv2, np = _require_cv2()
                Hm = np.asarray(H, dtype=np.float32)
                if getattr(Hm, "shape", None) == (3, 3):
                    ev["orb"]["homography"] = [[float(x) for x in row] for row in Hm.tolist()]
            except (TypeError, ValueError) as exc:
                logger.debug("Homography serialization skipped: %s", exc)
        return score, rationale, ev

    def same_location(self, *, before: MediaRef, after: MediaRef) -> tuple[float, str, dict]:
        v1 = self.clip_embed(media=before)
        v2 = self.clip_embed(media=after)
        clip_sim, clip_score = self.clip_similarity(before_vec=v1, after_vec=v2)
        return self.same_location_with_clip(before=before, after=after, clip_sim=clip_sim, clip_score=clip_score)

    def resolved(
        self,
        *,
        same_location_score: float,
        before: MediaRef | None = None,
        after: MediaRef | None = None,
        same_location_evidence: dict | None = None,
    ) -> tuple[float, str, dict]:
        # Baseline conservative score.
        base = max(0.0, min(1.0, same_location_score - 0.25))
        if before is None or after is None:
            return base, "Resolved score derived conservatively from same-location confidence.", {"base": base}

        # If we can align and measure change, nudge slightly.
        try:
            _cv2, np = _require_cv2()
            b_gray, b_bgr = _to_gray_np(before.path)
            a_gray, a_bgr = _to_gray_np(after.path)

            orb_score = None
            H = None

            if isinstance(same_location_evidence, dict):
                orb_ev = same_location_evidence.get("orb") if isinstance(same_location_evidence.get("orb"), dict) else None
                if isinstance(orb_ev, dict):
                    score_val = orb_ev.get("score")
                    if score_val is not None:
                        try:
                            orb_score = float(score_val)  # type: ignore[arg-type]
                        except (TypeError, ValueError):
                            orb_score = None
                    hm = orb_ev.get("homography")
                    if isinstance(hm, list) and len(hm) == 3:
                        try:
                            Hm = np.asarray(hm, dtype=np.float32)
                            if getattr(Hm, "shape", None) == (3, 3):
                                H = Hm
                        except (TypeError, ValueError):
                            H = None

            if orb_score is None:
                orb_score, _nm, _inl, H = _orb_match_score(b_gray, a_gray)

            if H is None:
                return base, "Resolved score conservative (alignment unavailable).", {"base": base, "orb_score": float(orb_score)}

            change = _difference_ratio_aligned(b_bgr, a_bgr, H)
        except Exception as exc:
            logger.debug("Resolved alignment/diff computation failed: %s", exc)
            return base, "Resolved score conservative (alignment/diff unavailable).", {"base": base}

        score = base
        # Small-but-real change can indicate work completion; huge change is suspicious.
        orb_score_f = float(orb_score) if orb_score is not None else 0.0
        if orb_score_f >= 0.15 and 0.02 <= change <= 0.25:
            score = min(1.0, score + 0.10)
            rationale = f"Resolved heuristic: aligned change ratio={change:.3f} (notable change)."
        elif change >= 0.45:
            score = max(0.0, score - 0.15)
            rationale = f"Resolved heuristic: aligned change ratio={change:.3f} (very large change; suspicious)."
        else:
            rationale = f"Resolved heuristic: aligned change ratio={change:.3f}."
        ev = {
            "base": base,
            "aligned_change_ratio": float(change),
            "orb_score": float(orb_score_f),
            "score": float(score),
        }
        return score, rationale, ev
