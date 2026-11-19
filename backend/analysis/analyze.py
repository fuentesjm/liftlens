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

from .angles import compute_series
from .config import DEFAULT_SQUAT_CONFIG, SquatConfig
from .form_rules import evaluate_reps
from .pose import DEFAULT_MODEL_PATH, PoseSequence, extract_pose
from .report import build_report
from .reps import adaptive_thresholds, segment_reps


def analyze_sequence(seq: PoseSequence, video: str, cfg: SquatConfig = DEFAULT_SQUAT_CONFIG) -> dict:
    """Everything after pose extraction (pure Python; unit-tested without a model)."""
    series = compute_series(seq, cfg)
    baseline, up, down = adaptive_thresholds(series.knee_angle, cfg)
    reps = segment_reps(series.knee_angle, seq.fps, cfg, up=up, down=down)
    results = evaluate_reps(reps, series, cfg)
    used = {"standing_baseline": round(baseline, 1), "up": round(up, 1), "down": round(down, 1)}
    return build_report(results, series, cfg, video, used)


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
    print(f"{'time(s)':>8} {'knee':>7} {'lean':>6}  state")
    step = max(1, int(round(step_seconds * seq.fps)))
    for i in range(0, len(knee), step):
        k = knee[i]
        state = ("standing" if k >= up else "in squat" if k < down else "between")
        visible = seq.frames[i] is not None
        print(f"{series.timestamps[i]:8.2f} {k:7.1f} {series.torso_lean[i]:6.1f}  "
              f"{state}{'' if visible else '  (no person found)'}")
    print("-" * 40)


def main() -> None:
    parser = argparse.ArgumentParser(description="LiftLens squat form analysis")
    parser.add_argument("video", help="path to a side-view squat video")
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH), help="pose model .task file")
    parser.add_argument("--out", help="write the JSON report to this file")
    parser.add_argument("--debug", action="store_true", help="print knee angle and lean over time")
    args = parser.parse_args()

    report = analyze_video(args.video, args.model, debug=args.debug)
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text)


if __name__ == "__main__":
    main()
