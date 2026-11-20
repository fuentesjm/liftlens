"""Pose extraction: video file -> per-frame body landmarks (pixel coordinates).

Uses the pretrained MediaPipe Pose Landmarker (Tasks API) in VIDEO mode.
This is the only place the project uses a pretrained model; everything after
this module (angles, reps, form rules) is the team's own algorithm.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions

# MediaPipe landmark indices for the joints the squat analysis needs.
LANDMARK_IDS = {
    "nose": 0,
    "left_shoulder": 11, "right_shoulder": 12,
    "left_wrist": 15, "right_wrist": 16,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
}

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "pose_landmarker_full.task"


@dataclass
class Landmark:
    x: float           # pixels
    y: float           # pixels (grows downward, like image rows)
    visibility: float  # 0..1, MediaPipe's confidence the point is visible


@dataclass
class PoseSequence:
    fps: float
    width: int
    height: int
    timestamps: list[float] = field(default_factory=list)  # seconds
    # One entry per frame: joint name -> Landmark, or None if no person found.
    frames: list[dict[str, Landmark] | None] = field(default_factory=list)


def extract_pose(video_path: str | Path, model_path: str | Path = DEFAULT_MODEL_PATH) -> PoseSequence:
    """Run the pose model on every frame of a video file."""
    video_path, model_path = Path(video_path), Path(model_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not model_path.exists():
        raise FileNotFoundError(
            f"Pose model not found: {model_path}. Run: python scripts/download_model.py"
        )

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    seq = PoseSequence(fps=fps, width=width, height=height)

    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
    )
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        frame_index = 0
        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break
            timestamp_ms = int(frame_index * 1000 / fps)
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect_for_video(image, timestamp_ms)

            seq.timestamps.append(timestamp_ms / 1000.0)
            if result.pose_landmarks:
                pose = result.pose_landmarks[0]  # first (only) person
                seq.frames.append({
                    name: Landmark(
                        x=pose[i].x * width,   # normalized -> pixels so angles
                        y=pose[i].y * height,  # are correct for any aspect ratio
                        visibility=pose[i].visibility or 0.0,
                    )
                    for name, i in LANDMARK_IDS.items()
                })
            else:
                seq.frames.append(None)
            frame_index += 1
    cap.release()
    return seq
