"""Command-line entry point: analyze one squat video and print/save a JSON report.

Usage:
    python -m backend.analysis.analyze samples/squat_side.mp4
    python -m backend.analysis.analyze samples/squat_side.mp4 --out report.json
    python -m backend.analysis.analyze samples/squat_side.mp4 --debug
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .angles import compute_series
from .config import DEFAULT_SQUAT_CONFIG, SquatConfig
from .form_rules import evaluate_reps
from .pose import DEFAULT_MODEL_PATH, PoseSequence, extract_pose
from .report import build_report
from .reps import adaptive_thresholds, segment_reps, split_setup_movements


class NoPersonDetected(ValueError):
    """No frame had a clearly visible person, so there is nothing to analyze."""


def analyze_sequence(seq: PoseSequence, video: str, cfg: SquatConfig = DEFAULT_SQUAT_CONFIG) -> dict:
    """Everything after pose extraction (pure Python; unit-tested without a model)."""
    series = compute_series(seq, cfg)
    if series.valid_ratio == 0:
        raise NoPersonDetected("No person was clearly visible in any frame.")
    baseline, up, down = adaptive_thresholds(series.knee_angle, cfg)
    candidates = segment_reps(series.knee_angle, seq.fps, cfg, up=up, down=down)
    reps, setup = split_setup_movements(candidates, series.wrist_over_nose, series.thigh_angle, cfg)
    results = evaluate_reps(reps, series, cfg)
    used = {"standing_baseline": round(baseline, 1), "up": round(up, 1), "down": round(down, 1)}
    ignored = [{"start_time": round(float(series.timestamps[r.start]), 2),
                "end_time": round(float(series.timestamps[r.end]), 2),
                "reason": "setup movement (hands up on a racked bar)"} for r in setup]
    report = build_report(results, series, cfg, video, used,
                          ignored=ignored, foot_travel=foot_travel(reps, series))
    report["trace"] = downsample_trace(series, seq.fps)
    return report


def foot_travel(reps, series) -> float | None:
    """Median distance the ankle appears to move during a rep, in thigh lengths.

    Feet stay planted in a real squat, so a large value means unreliable
    tracking (body partly blocked) or stepping.
    """
    travel = [float(np.nanmax(w) - np.nanmin(w)) for r in reps
              if np.isfinite(w := series.ankle_x[r.start:r.end + 1]).any()]
    return float(np.median(travel)) if travel else None


def downsample_trace(series, fps: float, hz: float = 10.0) -> dict:
    """Knee angle and torso lean at ~10 samples per second, for charts in the app.

    Not sent to the LLM. Small enough to store with every session.
    """
    step = max(1, int(round(fps / hz)))
    return {
        "t": [round(float(x), 2) for x in series.timestamps[::step]],
        "knee": [round(float(x), 1) for x in series.knee_angle[::step]],
        "thigh": [round(float(x), 1) for x in series.thigh_angle[::step]],
        "lean": [round(float(x), 1) for x in series.torso_lean[::step]],
    }


def analyze_video(video_path: str, model_path: str = str(DEFAULT_MODEL_PATH),
                  cfg: SquatConfig = DEFAULT_SQUAT_CONFIG, debug: bool = False) -> dict:
    seq = extract_pose(video_path, model_path)
    if debug:
        print_debug(seq, cfg)
    return analyze_sequence(seq, Path(video_path).name, cfg)


def print_debug(seq: PoseSequence, cfg: SquatConfig, step_seconds: float = 0.2) -> None:
    """Print the angle time series so thresholds can be checked against the video."""
    series = compute_series(seq, cfg)
    knee = series.knee_angle
    baseline, up, down = adaptive_thresholds(knee, cfg)
    print(f"side={series.side}  frames={len(knee)}  fps={seq.fps:.1f}  "
          f"valid_frames={series.valid_ratio:.0%}  shoulder_ratio={series.shoulder_ratio:.2f}")
    print(f"knee angle: min={knee.min():.1f}  max={knee.max():.1f}  standing baseline={baseline:.1f}   "
          f"(a rep needs < {down:.0f} then > {up:.0f})")
    print(f"{'time(s)':>8} {'knee':>7} {'thigh':>6} {'lean':>6}  state")
    step = max(1, int(round(step_seconds * seq.fps)))
    for i in range(0, len(knee), step):
        k = knee[i]
        state = ("standing" if k >= up else "in squat" if k < down else "between")
        visible = seq.frames[i] is not None
        print(f"{series.timestamps[i]:8.2f} {k:7.1f} {series.thigh_angle[i]:6.1f} {series.torso_lean[i]:6.1f}  "
              f"{state}{'' if visible else '  (no person found)'}")
    print("-" * 40)


def main() -> None:
    parser = argparse.ArgumentParser(description="LiftLens squat form analysis")
    parser.add_argument("video", help="path to a side-view squat video")
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH), help="pose model .task file")
    parser.add_argument("--out", help="write the JSON report to this file")
    parser.add_argument("--debug", action="store_true", help="print knee angle and lean over time")
    args = parser.parse_args()

    try:
        report = analyze_video(args.video, args.model, debug=args.debug)
    except (FileNotFoundError, NoPersonDetected) as e:
        raise SystemExit(f"Error: {e}")
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text)


if __name__ == "__main__":
    main()
