"""Synthetic side-view squat generator for tests (no video or pose model needed).

Builds stick-figure landmarks whose knee angle follows a chosen curve, so the
expected rep count, depth, and lean are known exactly.
"""

from __future__ import annotations

import numpy as np

from backend.analysis.pose import Landmark, PoseSequence

SHIN, THIGH, TORSO = 200.0, 200.0, 250.0  # pixel lengths
ANKLE = (500.0, 900.0)


def figure(knee_angle: float, lean: float, visibility: float = 0.99, side: str = "right") -> dict:
    """Landmarks for one frame. Shin and thigh tilt equally so the knee angle is exact."""
    tilt = np.radians((180.0 - knee_angle) / 2.0)
    ax, ay = ANKLE
    kx, ky = ax + SHIN * np.sin(tilt), ay - SHIN * np.cos(tilt)
    hx, hy = kx - THIGH * np.sin(tilt), ky - THIGH * np.cos(tilt)
    lr = np.radians(lean)
    sx, sy = hx + TORSO * np.sin(lr), hy - TORSO * np.cos(lr)

    pts = {"shoulder": (sx, sy), "hip": (hx, hy), "knee": (kx, ky), "ankle": (ax, ay)}
    other = "left" if side == "right" else "right"
    frame = {}
    for joint, (x, y) in pts.items():
        frame[f"{side}_{joint}"] = Landmark(x, y, visibility)
        frame[f"{other}_{joint}"] = Landmark(x + 5, y, 0.2)  # hidden far side
    return frame


def squat_sequence(bottoms: list[float], leans: list[float] | None = None,
                   fps: float = 30.0, rep_seconds: float = 2.0, pause_seconds: float = 0.5) -> PoseSequence:
    """Standing at 175 deg, then one smooth (cosine) dip per rep down to each bottom angle."""
    leans = leans or [25.0] * len(bottoms)
    knee, lean = [], []
    stand = int(pause_seconds * fps)
    for bottom, max_lean in zip(bottoms, leans):
        knee += [175.0] * stand
        lean += [10.0] * stand
        n = int(rep_seconds * fps)
        phase = (1 - np.cos(np.linspace(0, 2 * np.pi, n))) / 2  # 0 -> 1 -> 0
        knee += list(175.0 - (175.0 - bottom) * phase)
        lean += list(10.0 + (max_lean - 10.0) * phase)
    knee += [175.0] * stand
    lean += [10.0] * stand

    seq = PoseSequence(fps=fps, width=1000, height=1000)
    for i, (k, l) in enumerate(zip(knee, lean)):
        seq.timestamps.append(i / fps)
        seq.frames.append(figure(k, l))
    return seq
