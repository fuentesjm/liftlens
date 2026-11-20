"""Rep segmentation: split the knee-angle series into individual squat reps."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import SquatConfig


@dataclass
class Rep:
    start: int   # frame index where the descent began (last standing frame)
    bottom: int  # frame index of the smallest knee angle (deepest point)
    end: int     # frame index where the lifter was standing again


def adaptive_thresholds(knee_angle: np.ndarray, cfg: SquatConfig) -> tuple[float, float, float]:
    """Set the rep thresholds from this person's own standing knee angle.

    People rarely measure a perfectly straight 175-180 deg when standing (soft
    knees, camera angle), so a fixed "standing = above 160 deg" can make a rep
    never finish. The standing baseline is the 95th percentile of the clip's
    knee angle; "standing" is anything within `standing_margin` of it. The
    configured up/down thresholds act as upper limits.

    Returns (standing_baseline, up_threshold, down_threshold).
    """
    baseline = float(np.percentile(knee_angle, 95))
    up = min(cfg.up_threshold, baseline - cfg.standing_margin)
    down = min(cfg.down_threshold, up - cfg.hysteresis_gap)
    return baseline, up, down


def segment_reps(knee_angle: np.ndarray, fps: float, cfg: SquatConfig,
                 up: float | None = None, down: float | None = None) -> list[Rep]:
    """Hysteresis state machine on the knee angle.

    standing --(angle < down)--> descending/bottom
             <--(angle > up)---- completes one rep

    The gap between the two thresholds stops small jitter from counting as reps.
    If up/down are not given, they are computed with adaptive_thresholds().
    """
    if len(knee_angle) == 0:
        return []
    if up is None or down is None:
        _, up, down = adaptive_thresholds(knee_angle, cfg)

    reps: list[Rep] = []
    min_frames = max(1, int(round(cfg.min_rep_seconds * fps)))

    in_rep = False
    last_standing = 0
    bottom = 0
    for i, angle in enumerate(knee_angle):
        if not in_rep:
            if angle >= up:
                last_standing = i
            elif angle < down:
                in_rep = True
                bottom = i
        else:
            if angle < knee_angle[bottom]:
                bottom = i
            if angle > up:
                if i - last_standing >= min_frames:
                    reps.append(Rep(start=last_standing, bottom=bottom, end=i))
                in_rep = False
                last_standing = i
    return reps


def deepest_frame(rep: Rep, thigh_angle: np.ndarray) -> int:
    """Frame where the hips are lowest (smallest thigh angle) within the rep."""
    window = thigh_angle[rep.start:rep.end + 1]
    if np.all(np.isnan(window)):
        return rep.bottom
    return rep.start + int(np.nanargmin(window))


def split_setup_movements(reps: list[Rep], wrist_over_nose: np.ndarray, thigh_angle: np.ndarray,
                          cfg: SquatConfig) -> tuple[list[Rep], list[Rep]]:
    """Separate real reps from setup movements (unracking / re-racking a bar).

    When you duck under a racked bar or put it back, your hands are on a bar
    that's fixed in the rack, so at the bottom of that knee bend they are up
    near or above your head. During a real squat the hands stay at shoulder
    height or lower. Returns (reps, ignored).
    """
    kept, ignored = [], []
    for rep in reps:
        gap = wrist_over_nose[deepest_frame(rep, thigh_angle)]
        (ignored if np.isfinite(gap) and gap > cfg.max_wrist_over_nose else kept).append(rep)
    return kept, ignored
