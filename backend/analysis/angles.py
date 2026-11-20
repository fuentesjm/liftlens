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
    thigh_angle: np.ndarray   # degrees above parallel (90 = standing, 0 = parallel, <0 = below)
    wrist_over_nose: np.ndarray  # (nose y - highest wrist y) / thigh length; NaN if not tracked
    ankle_x: np.ndarray       # near-side ankle x / thigh length (for the foot-travel check)
    thigh_length: float       # pixels: hip-to-knee height while standing


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


def _vertical_thigh_angle(hip_y: np.ndarray, knee_y: np.ndarray, knee_angle: np.ndarray) -> tuple[np.ndarray, float]:
    """Thigh angle above parallel, from heights only.

    While standing, the thigh is vertical, so its on-screen height equals its
    length L. At any moment, sin(angle above horizontal) = (knee y - hip y) / L.
    Turning the camera around the person (yaw) squeezes horizontal distances
    but leaves heights unchanged, so this stays accurate when the camera isn't
    exactly side-on.
    """
    standing = knee_angle >= np.nanpercentile(knee_angle, 80)
    length = float(np.nanmedian((knee_y - hip_y)[standing]))
    if not np.isfinite(length) or length <= 0:
        return np.full_like(hip_y, np.nan), float("nan")
    ratio = np.clip((knee_y - hip_y) / length, -1.0, 1.0)
    return np.degrees(np.arcsin(ratio)), length


def compute_series(seq: PoseSequence, cfg: SquatConfig) -> SquatSeries:
    side = _choose_side(seq)
    joints = [f"{side}_{j}" for j in ("shoulder", "hip", "knee", "ankle")]

    knee, lean, hip_y, knee_y, ankle_x, wrist_gap = [], [], [], [], [], []
    valid = 0
    for frame in seq.frames:
        ok = frame is not None and all(frame[j].visibility >= cfg.min_landmark_visibility for j in joints)
        if ok:
            s, h, k, a = (frame[j] for j in joints)
            knee.append(angle_at(h, k, a))
            lean.append(torso_lean(s, h))
            hip_y.append(h.y)
            knee_y.append(k.y)
            ankle_x.append(a.x)
            if all(j in frame for j in ("nose", "left_wrist", "right_wrist")):
                wrist_gap.append(frame["nose"].y - min(frame["left_wrist"].y, frame["right_wrist"].y))
            else:
                wrist_gap.append(np.nan)
            valid += 1
        else:
            for lst in (knee, lean, hip_y, knee_y, ankle_x, wrist_gap):
                lst.append(np.nan)

    def smooth(values: list[float]) -> np.ndarray:
        arr = np.array(values, dtype=float)
        if np.all(np.isnan(arr)):
            return arr
        return centered_moving_average(interpolate_missing(arr), cfg.smoothing_window)

    knee_s = smooth(knee)
    hip_s, knee_y_s = smooth(hip_y), smooth(knee_y)
    if valid:
        thigh, length = _vertical_thigh_angle(hip_s, knee_y_s, knee_s)
    else:
        thigh, length = np.full(len(seq.frames), np.nan), float("nan")
    scale = length if np.isfinite(length) and length > 0 else np.nan

    n = len(seq.frames)
    return SquatSeries(
        side=side,
        timestamps=np.asarray(seq.timestamps, dtype=float),
        knee_angle=knee_s,
        torso_lean=smooth(lean),
        valid_ratio=valid / n if n else 0.0,
        shoulder_ratio=shoulder_width_ratio(seq, side),
        thigh_angle=thigh,
        wrist_over_nose=smooth(wrist_gap) / scale,
        ankle_x=smooth(ankle_x) / scale,
        thigh_length=length,
    )
