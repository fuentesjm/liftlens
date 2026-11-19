import numpy as np
import pytest

from backend.analysis.analyze import analyze_sequence
from backend.analysis.angles import angle_at, torso_lean
from backend.analysis.config import SquatConfig
from backend.analysis.pose import Landmark
from backend.analysis.reps import segment_reps
from backend.analysis.smoothing import centered_moving_average, interpolate_missing
from backend.tests.synthetic import figure, squat_sequence

CFG = SquatConfig()


# --- Geometry -----------------------------------------------------------------
def test_angle_at_right_angle():
    assert angle_at(Landmark(0, 0, 1), Landmark(0, 1, 1), Landmark(1, 1, 1)) == pytest.approx(90.0)


def test_angle_at_straight_line():
    assert angle_at(Landmark(0, 0, 1), Landmark(0, 1, 1), Landmark(0, 2, 1)) == pytest.approx(180.0)


def test_torso_lean_upright_and_tilted():
    hip = Landmark(0, 100, 1)
    assert torso_lean(Landmark(0, 0, 1), hip) == pytest.approx(0.0)
    assert torso_lean(Landmark(100, 0, 1), hip) == pytest.approx(45.0)


@pytest.mark.parametrize("knee", [90.0, 120.0, 170.0])
def test_synthetic_figure_has_exact_knee_angle(knee):
    f = figure(knee, lean=20.0)
    assert angle_at(f["right_hip"], f["right_knee"], f["right_ankle"]) == pytest.approx(knee)
    assert torso_lean(f["right_shoulder"], f["right_hip"]) == pytest.approx(20.0)


# --- Smoothing ------------------------------------------------------------------
def test_interpolate_missing_fills_gaps():
    out = interpolate_missing(np.array([0.0, np.nan, np.nan, 3.0]))
    assert out.tolist() == [0.0, 1.0, 2.0, 3.0]


def test_moving_average_keeps_length_and_flattens_spike():
    out = centered_moving_average(np.array([0, 0, 9, 0, 0], dtype=float), 3)
    assert len(out) == 5 and out[2] == pytest.approx(3.0)


# --- Rep segmentation -------------------------------------------------------------
def test_counts_three_reps():
    seq = squat_sequence([90, 90, 90])
    report = analyze_sequence(seq, "synthetic.mp4", CFG)
    assert report["rep_count"] == 3


def test_jitter_near_threshold_is_not_a_rep():
    # Wobbling around 150-158 deg (between the two thresholds) must not count.
    knee = np.array([175] * 20 + [158, 152, 157, 151, 158] * 6 + [175] * 20, dtype=float)
    assert segment_reps(knee, fps=30, cfg=CFG) == []


def test_too_quick_dip_is_ignored():
    knee = np.array([175] * 10 + [130] * 3 + [175] * 10, dtype=float)  # 0.1 s dip
    assert segment_reps(knee, fps=30, cfg=CFG) == []


# --- Form rules ---------------------------------------------------------------------
def test_flags_only_the_shallow_rep():
    seq = squat_sequence([90, 120, 88])  # rep 2 stops at 120 deg
    report = analyze_sequence(seq, "synthetic.mp4", CFG)
    assert report["rep_count"] == 3
    assert [r["errors"] for r in report["reps"]] == [[], ["shallow_depth"], []]
    assert report["form_score"] == pytest.approx(0.67)
    assert report["cues"][0].startswith("Rep 2:")


def test_flags_forward_lean():
    seq = squat_sequence([90, 90], leans=[25.0, 65.0])
    report = analyze_sequence(seq, "synthetic.mp4", CFG)
    assert report["reps"][0]["errors"] == []
    assert report["reps"][1]["errors"] == ["forward_lean"]


def test_bottom_time_is_middle_of_rep():
    seq = squat_sequence([90], fps=30, rep_seconds=2.0, pause_seconds=0.5)
    rep = analyze_sequence(seq, "s.mp4", CFG)["reps"][0]
    assert rep["bottom_time"] == pytest.approx(1.5, abs=0.1)  # 0.5 s pause + 1.0 s
    assert rep["bottom_knee_angle"] == pytest.approx(90.0, abs=2.0)


# --- Signal quality -------------------------------------------------------------------
def test_warns_when_body_mostly_hidden():
    seq = squat_sequence([90, 90])
    for i in range(0, len(seq.frames), 2):  # hide every other frame -> 50% valid
        seq.frames[i] = None
    report = analyze_sequence(seq, "s.mp4", CFG)
    assert report["rep_count"] == 2  # interpolation still recovers the reps
    assert any("visible" in w for w in report["warnings"])


def test_picks_visible_side():
    seq = squat_sequence([90])
    assert analyze_sequence(seq, "s.mp4", CFG)["side_analyzed"] == "right"
