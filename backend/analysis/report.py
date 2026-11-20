"""Turn rep results into the JSON report the app (and the LLM writer) consumes."""

from __future__ import annotations

from dataclasses import asdict

from .angles import SquatSeries
from .config import SquatConfig
from .form_rules import CUES, RepResult


def build_report(results: list[RepResult], series: SquatSeries, cfg: SquatConfig, video: str,
                 thresholds_used: dict | None = None, ignored: list[dict] | None = None,
                 foot_travel: float | None = None) -> dict:
    total = len(results)
    passed = sum(r.passed for r in results)

    warnings = []
    if series.valid_ratio < cfg.min_valid_frame_ratio:
        warnings.append(
            f"Body was clearly visible in only {series.valid_ratio:.0%} of frames. "
            "Record from the side with your whole body in frame."
        )
    if series.shoulder_ratio > cfg.max_shoulder_width_ratio:
        warnings.append(
            "You seem to be turned toward the camera. Film from the side "
            "(camera at hip height, facing your side) for accurate angles."
        )
    if foot_travel is not None and foot_travel > cfg.max_foot_travel:
        warnings.append(
            "Tracking was unsteady: your feet seemed to move during reps, which usually means part of "
            "your body was blocked (by plates or the rack) or you stepped. Results may be inaccurate. "
            "Film from a spot where your hips, knees, and ankles stay visible."
        )
    if total == 0:
        warnings.append("No reps detected. Check camera angle and that full squats are in the clip.")

    # One cue per error type, listing the reps it applies to.
    cues = []
    for code, text in CUES.items():
        reps_with = [r.number for r in results if code in r.errors]
        if reps_with:
            label = "Rep" if len(reps_with) == 1 else "Reps"
            cues.append(f"{label} {', '.join(map(str, reps_with))}: {text}")

    return {
        "exercise": "squat",
        "video": video,
        "side_analyzed": series.side,
        "rep_count": total,
        "reps_passed": passed,
        "form_score": round(passed / total, 2) if total else None,
        "reps": [{**asdict(r), "passed": r.passed} for r in results],
        "cues": cues,
        "warnings": warnings,
        "ignored_movements": ignored or [],
        "camera": {"shoulder_width_ratio": round(series.shoulder_ratio, 2),
                   "foot_travel": None if foot_travel is None else round(foot_travel, 2)},
        "thresholds_used": thresholds_used,
        "thresholds": asdict(cfg),
    }
