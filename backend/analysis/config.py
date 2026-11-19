"""Tunable thresholds for squat analysis.

All angles are in degrees. These are starting values: calibrate them on the
team's labeled test clips (see eval/) and record the final values in the report.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SquatConfig:
    # --- Rep segmentation (hysteresis on the knee angle) ---------------------
    # Standing is "knee angle above UP"; a rep starts when the angle drops below
    # DOWN and finishes when it rises above UP again. Using two thresholds
    # (instead of one) prevents jitter near a single threshold from counting
    # extra reps. DOWN is deliberately high so shallow reps are still counted
    # (and then flagged by the depth rule) rather than missed.
    # UP and DOWN are upper limits: the actual thresholds adapt to each
    # person's standing knee angle (see reps.adaptive_thresholds), because
    # soft knees or a slightly angled camera can keep "standing" below 160.
    up_threshold: float = 160.0
    down_threshold: float = 140.0
    standing_margin: float = 10.0   # "standing" = within this of the person's standing angle
    hysteresis_gap: float = 15.0    # minimum gap between UP and DOWN
    min_rep_seconds: float = 0.4    # ignore dips shorter than this (noise)

    # --- Form rules ------------------------------------------------------------
    # Depth: the smallest knee angle in the rep must be at or below this value.
    # Around 90-100 degrees corresponds to thighs roughly parallel to the floor.
    max_bottom_knee_angle: float = 100.0
    # Forward lean: torso angle from vertical (shoulder-hip line) at the bottom
    # of the rep must not exceed this value.
    max_torso_lean: float = 50.0

    # --- Signal quality --------------------------------------------------------
    min_landmark_visibility: float = 0.5  # per-landmark visibility to trust it
    min_valid_frame_ratio: float = 0.6    # below this, warn the user
    # Camera check: in a true side view the two shoulders overlap on screen.
    # Shoulder separation / torso length above this means the person is turned
    # toward the camera, which distorts the 2D angles. Calibrate on real clips.
    max_shoulder_width_ratio: float = 0.35
    smoothing_window: int = 5             # centered moving average (frames, odd)


DEFAULT_SQUAT_CONFIG = SquatConfig()
