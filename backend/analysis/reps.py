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


def segment_reps(knee_angle: np.ndarray, fps: float, cfg: SquatConfig) -> list[Rep]:
    """Hysteresis state machine on the knee angle.

    standing --(angle < down_threshold)--> descending/bottom
             <--(angle > up_threshold)---- completes one rep

    The gap between the two thresholds stops small jitter from counting as reps.
    """
    reps: list[Rep] = []
    min_frames = max(1, int(round(cfg.min_rep_seconds * fps)))

    in_rep = False
    last_standing = 0
    bottom = 0
    for i, angle in enumerate(knee_angle):
        if not in_rep:
            if angle >= cfg.up_threshold:
                last_standing = i
            elif angle < cfg.down_threshold:
                in_rep = True
                bottom = i
        else:
            if angle < knee_angle[bottom]:
                bottom = i
            if angle > cfg.up_threshold:
                if i - last_standing >= min_frames:
                    reps.append(Rep(start=last_standing, bottom=bottom, end=i))
                in_rep = False
                last_standing = i
    return reps
