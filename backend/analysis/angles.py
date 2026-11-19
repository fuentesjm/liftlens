"""Joint-angle geometry and per-frame angle series for a squat."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import SquatConfig
from .pose import Landmark, PoseSequence
from .smoothing import centered_moving_average, interpolate_missing


def angle_at(a: Landmark, b: Landmark, c: Landmark) -> float:
    """Interior angle ABC in degrees (angle at point b between rays b->a and b->c)."""
    ba = np.array([a.x - b.x, a.y - b.y])
    bc = np.array([c.x - b.x, c.y - b.y])
    denom = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denom == 0:
        return float("nan")
    cos = np.clip(np.dot(ba, bc) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos)))


def torso_lean(shoulder: Landmark, hip: Landmark) -> float:
    """Angle in degrees between the hip->shoulder line and straight up (0 = upright)."""
    dx = shoulder.x - hip.x
    dy = hip.y - shoulder.y  # image y grows downward; flip so "up" is positive
    return float(np.degrees(np.arctan2(abs(dx), dy)))


@dataclass
class SquatSeries:
    side: str                 # "left" or "right" (the side facing the camera)
    timestamps: np.ndarray    # seconds
    knee_angle: np.ndarray    # degrees, smoothed
    torso_lean: np.ndarray    # degrees, smoothed
    valid_ratio: float        # fraction of frames with trustworthy landmarks
    shoulder_ratio: float     # median shoulder separation / torso length (0 = perfect side view)


def _choose_side(seq: PoseSequence) -> str:
    """Pick the body side the camera sees best (side-view recording)."""
    totals = {"left": 0.0, "right": 0.0}
    for frame in seq.frames:
        if frame is None:
            continue
        for side in totals:
            totals[side] += sum(frame[f"{side}_{j}"].visibility for j in ("hip", "knee", "ankle"))
    return max(totals, key=totals.get)


def shoulder_width_ratio(seq: PoseSequence, side: str) -> float:
    """How far apart the two shoulders appear, relative to torso length.

    Filmed exactly side-on, the shoulders overlap (ratio near 0). Facing the
    camera, they are spread apart (ratio around 0.6-0.9). Uses the median over
    frames so a few bad detections don't matter. MediaPipe still estimates the
    hidden shoulder's position, so visibility is not required here.
    """
    ratios = []
    for frame in seq.frames:
        if frame is None:
            continue
        ls, rs, hip = frame["left_shoulder"], frame["right_shoulder"], frame[f"{side}_hip"]
        near = frame[f"{side}_shoulder"]
        torso = np.hypot(near.x - hip.x, near.y - hip.y)
        if torso > 0:
            ratios.append(abs(ls.x - rs.x) / torso)
    return float(np.median(ratios)) if ratios else float("nan")


def compute_series(seq: PoseSequence, cfg: SquatConfig) -> SquatSeries:
    side = _choose_side(seq)
    joints = [f"{side}_{j}" for j in ("shoulder", "hip", "knee", "ankle")]

    knee, lean = [], []
    valid = 0
    for frame in seq.frames:
        ok = frame is not None and all(frame[j].visibility >= cfg.min_landmark_visibility for j in joints)
        if ok:
            s, h, k, a = (frame[j] for j in joints)
            knee.append(angle_at(h, k, a))
            lean.append(torso_lean(s, h))
            valid += 1
        else:
            knee.append(np.nan)
            lean.append(np.nan)

    n = len(seq.frames)
    return SquatSeries(
        side=side,
        timestamps=np.asarray(seq.timestamps, dtype=float),
        knee_angle=centered_moving_average(interpolate_missing(np.array(knee)), cfg.smoothing_window),
        torso_lean=centered_moving_average(interpolate_missing(np.array(lean)), cfg.smoothing_window),
        valid_ratio=valid / n if n else 0.0,
        shoulder_ratio=shoulder_width_ratio(seq, side),
    )
