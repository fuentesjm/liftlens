"""Command-line entry point: analyze one squat video and print/save a JSON report.

Usage:
    python -m backend.analysis.analyze samples/squat_side.mp4
    python -m backend.analysis.analyze samples/squat_side.mp4 --out report.json
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
from .reps import segment_reps


def analyze_sequence(seq: PoseSequence, video: str, cfg: SquatConfig = DEFAULT_SQUAT_CONFIG) -> dict:
    """Everything after pose extraction (pure Python; unit-tested without a model)."""
    series = compute_series(seq, cfg)
    reps = segment_reps(series.knee_angle, seq.fps, cfg)
    results = evaluate_reps(reps, series, cfg)
    return build_report(results, series, cfg, video)


def analyze_video(video_path: str, model_path: str = str(DEFAULT_MODEL_PATH),
                  cfg: SquatConfig = DEFAULT_SQUAT_CONFIG) -> dict:
    seq = extract_pose(video_path, model_path)
    return analyze_sequence(seq, Path(video_path).name, cfg)


def main() -> None:
    parser = argparse.ArgumentParser(description="LiftLens squat form analysis")
    parser.add_argument("video", help="path to a side-view squat video")
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH), help="pose model .task file")
    parser.add_argument("--out", help="write the JSON report to this file")
    args = parser.parse_args()

    report = analyze_video(args.video, args.model)
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text)


if __name__ == "__main__":
    main()
