"""Synthetic side-view squat generator for tests (no video or pose model needed).

Builds stick-figure landmarks whose knee angle follows a chosen curve, so the
expected rep count, depth, and lean are known exactly.
"""

from __future__ import annotations

import numpy as np

from backend.analysis.pose import Landmark, PoseSequence

SHIN, THIGH, TORSO = 200.0, 200.0, 250.0  # pixel lengths
ANKLE = (500.0, 900.0)


THIGH_SHARE = 0.7  # share of the knee bend taken by the thigh (shins stay more upright)


def thigh_above_parallel(knee_angle: float) -> float:
    """Expected thigh angle above parallel for a given knee angle in this figure."""
    return 90.0 - THIGH_SHARE * (180.0 - knee_angle)


def figure(knee_angle: float, lean: float, visibility: float = 0.99, side: str = "right",
           other_offset: float = 5.0, hands_up: bool = False, ankle_shift: float = 0.0) -> dict:
    """Landmarks for one frame, with an exact knee angle.

    The thigh takes 70% of the knee bend and the shin 30%, like a real squat
    (a knee angle of about 60 deg puts the thigh near parallel).
    other_offset is how far (pixels) the far-side joints sit from the near side:
    small = true side view, large (e.g. 180) = person turned toward the camera.
    hands_up puts the wrists above the head (ducking under a racked bar).
    ankle_shift moves the whole figure sideways (simulates unsteady tracking).
    """
    bend = 180.0 - knee_angle
    thigh_tilt = np.radians(THIGH_SHARE * bend)
    shin_tilt = np.radians((1 - THIGH_SHARE) * bend)
    ax, ay = ANKLE[0] + ankle_shift, ANKLE[1]
    kx, ky = ax + SHIN * np.sin(shin_tilt), ay - SHIN * np.cos(shin_tilt)
    hx, hy = kx - THIGH * np.sin(thigh_tilt), ky - THIGH * np.cos(thigh_tilt)
    lr = np.radians(lean)
    sx, sy = hx + TORSO * np.sin(lr), hy - TORSO * np.cos(lr)
    nose = (sx + 30.0, sy - 70.0)
    wrist = (sx + 40.0, sy - 160.0) if hands_up else (sx - 10.0, sy + 10.0)  # bar on the back

    pts = {"shoulder": (sx, sy), "hip": (hx, hy), "knee": (kx, ky), "ankle": (ax, ay), "wrist": wrist}
    other = "left" if side == "right" else "right"
    frame = {}
    for joint, (x, y) in pts.items():
        frame[f"{side}_{joint}"] = Landmark(x, y, visibility)
        frame[f"{other}_{joint}"] = Landmark(x + other_offset, y, 0.2)  # hidden far side
    frame["nose"] = Landmark(*nose, visibility)
    return frame


def squat_sequence(bottoms: list[float], leans: list[float] | None = None,
                   fps: float = 30.0, rep_seconds: float = 2.0, pause_seconds: float = 0.5,
                   stand_angle: float = 175.0, other_offset: float = 5.0,
                   hands_up: list[bool] | None = None, foot_wobble: float = 0.0) -> PoseSequence:
    """Standing at stand_angle, then one smooth (cosine) dip per rep down to each bottom angle.

    hands_up[i] makes dip i a rack setup movement (hands above the head).
    foot_wobble (pixels) makes the ankle drift sideways during each dip.
    """
    leans = leans or [25.0] * len(bottoms)
    hands_up = hands_up or [False] * len(bottoms)
    knee, lean, up, shift = [], [], [], []
    stand = int(pause_seconds * fps)
    for bottom, max_lean, h in zip(bottoms, leans, hands_up):
        knee += [stand_angle] * stand
        lean += [10.0] * stand
        up += [False] * stand
        shift += [0.0] * stand
        n = int(rep_seconds * fps)
        phase = (1 - np.cos(np.linspace(0, 2 * np.pi, n))) / 2  # 0 -> 1 -> 0
        knee += list(stand_angle - (stand_angle - bottom) * phase)
        lean += list(10.0 + (max_lean - 10.0) * phase)
        up += [h] * n
        shift += list(foot_wobble * phase)
    knee += [stand_angle] * stand
    lean += [10.0] * stand
    up += [False] * stand
    shift += [0.0] * stand

    seq = PoseSequence(fps=fps, width=1000, height=1000)
    for i, (k, l, h, a) in enumerate(zip(knee, lean, up, shift)):
        seq.timestamps.append(i / fps)
        seq.frames.append(figure(k, l, other_offset=other_offset, hands_up=h, ankle_shift=a))
    return seq
