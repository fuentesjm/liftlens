"""Turn rep results into the JSON report the app (and the LLM writer) consumes."""

from __future__ import annotations

from dataclasses import asdict

from .angles import SquatSeries
from .config import SquatConfig
from .form_rules import CUES, RepResult


def build_report(results: list[RepResult], series: SquatSeries, cfg: SquatConfig, video: str) -> dict:
    total = len(results)
    passed = sum(r.passed for r in results)

    warnings = []
    if series.valid_ratio < cfg.min_valid_frame_ratio:
        warnings.append(
            f"Body was clearly visible in only {series.valid_ratio:.0%} of frames. "
            "Record from the side with your whole body in frame."
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
        "thresholds": asdict(cfg),
    }
