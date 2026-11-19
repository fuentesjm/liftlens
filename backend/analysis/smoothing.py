"""Signal cleanup for joint-angle time series."""

from __future__ import annotations

import numpy as np


def interpolate_missing(values: np.ndarray) -> np.ndarray:
    """Fill NaN gaps (frames where the joint wasn't visible) by linear interpolation."""
    values = np.asarray(values, dtype=float)
    valid = ~np.isnan(values)
    if not valid.any():
        return values
    idx = np.arange(len(values))
    return np.interp(idx, idx[valid], values[valid])


def centered_moving_average(values: np.ndarray, window: int) -> np.ndarray:
    """Smooth with a centered window (uses frames before AND after each point).

    Possible because the whole recorded clip is available (offline analysis).
    Edges use a shrinking window so the output has the same length as the input.
    """
    values = np.asarray(values, dtype=float)
    if window <= 1 or len(values) == 0:
        return values.copy()
    half = window // 2
    out = np.empty_like(values)
    for i in range(len(values)):
        lo, hi = max(0, i - half), min(len(values), i + half + 1)
        out[i] = values[lo:hi].mean()
    return out
