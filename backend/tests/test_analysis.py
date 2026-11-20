import numpy as np
import pytest

from backend.analysis.analyze import analyze_sequence
from backend.analysis.angles import angle_at, torso_lean
from backend.analysis.config import SquatConfig
from backend.analysis.pose import Landmark
from backend.analysis.reps import segment_reps
from backend.analysis.smoothing import centered_moving_average, interpolate_missing
from backend.tests.synthetic import figure, squat_sequence, thigh_above_parallel

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
    seq = squat_sequence([60, 120, 62])  # rep 2 stops with the thigh 48 deg above parallel
    report = analyze_sequence(seq, "synthetic.mp4", CFG)
    assert report["rep_count"] == 3
    assert [r["errors"] for r in report["reps"]] == [[], ["shallow_depth"], []]
    assert report["form_score"] == pytest.approx(0.67)
    assert report["cues"][0].startswith("Rep 2:")


def test_flags_forward_lean():
    seq = squat_sequence([60, 60], leans=[25.0, 65.0])
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


# --- Adaptive thresholds and camera check --------------------------------------
def test_thresholds_unchanged_for_straight_standing():
    report = analyze_sequence(squat_sequence([90, 90]), "synthetic.mp4", CFG)
    assert report["thresholds_used"]["up"] == pytest.approx(160.0)
    assert report["thresholds_used"]["down"] == pytest.approx(140.0)


def test_soft_knee_standing_still_counts_reps():
    # Standing never gets above 158 deg, so a fixed 160 deg "standing" cutoff
    # would never finish a rep. The adaptive cutoff should.
    seq = squat_sequence([100, 100], stand_angle=158.0)
    assert segment_reps(np.full(10, 158.0), 30.0, CFG) == []  # sanity: flat line is no rep
    report = analyze_sequence(seq, "synthetic.mp4", CFG)
    assert report["rep_count"] == 2
    assert report["thresholds_used"]["up"] < 160.0


def test_side_view_has_no_camera_warning():
    report = analyze_sequence(squat_sequence([90]), "synthetic.mp4", CFG)
    assert report["camera"]["shoulder_width_ratio"] < CFG.max_shoulder_width_ratio
    assert not any("turned toward the camera" in w for w in report["warnings"])


def test_facing_camera_warns():
    report = analyze_sequence(squat_sequence([90], other_offset=180.0), "synthetic.mp4", CFG)
    assert report["camera"]["shoulder_width_ratio"] > CFG.max_shoulder_width_ratio
    assert any("turned toward the camera" in w for w in report["warnings"])


def test_report_includes_downsampled_trace():
    report = analyze_sequence(squat_sequence([90]), "synthetic.mp4", CFG)  # 30 fps, 3 s
    trace = report["trace"]
    assert len(trace["t"]) == len(trace["knee"]) == len(trace["lean"])
    assert trace["t"][1] - trace["t"][0] == pytest.approx(0.1, abs=0.01)  # ~10 per second
    assert min(trace["knee"]) == pytest.approx(90.0, abs=2.0)



# --- Depth from heights, setup movements, tracking check ---------------------------
def test_thigh_angle_matches_geometry():
    rep = analyze_sequence(squat_sequence([60]), "s.mp4", CFG)["reps"][0]
    assert rep["bottom_thigh_angle"] == pytest.approx(thigh_above_parallel(60), abs=1.5)  # 6 deg
    assert rep["errors"] == []


def _squeeze_x(seq, factor):
    """Simulate turning the camera around the person: horizontal distances shrink."""
    for frame in seq.frames:
        for name, lm in frame.items():
            frame[name] = type(lm)(500 + (lm.x - 500) * factor, lm.y, lm.visibility)
    return seq


def test_depth_check_survives_angled_camera():
    side_on = analyze_sequence(squat_sequence([60, 95]), "s.mp4", CFG)
    angled = analyze_sequence(_squeeze_x(squat_sequence([60, 95]), 0.6), "s.mp4", CFG)
    for a, b in zip(side_on["reps"], angled["reps"]):
        assert b["bottom_thigh_angle"] == pytest.approx(a["bottom_thigh_angle"], abs=1.0)
        assert b["errors"] == a["errors"]
    assert [r["errors"] for r in angled["reps"]] == [[], ["shallow_depth"]]
    # The on-screen knee angle, by contrast, is distorted by the angle.
    assert abs(angled["reps"][1]["bottom_knee_angle"] - 95) > 5


def test_rack_setup_movements_are_not_reps():
    # Unrack (hands on the racked bar), two squats, re-rack.
    seq = squat_sequence([100, 60, 60, 125], hands_up=[True, False, False, True])
    report = analyze_sequence(seq, "s.mp4", CFG)
    assert report["rep_count"] == 2
    assert len(report["ignored_movements"]) == 2
    assert all("setup" in m["reason"] for m in report["ignored_movements"])


def test_unsteady_tracking_warns():
    steady = analyze_sequence(squat_sequence([60, 60]), "s.mp4", CFG)
    wobbly = analyze_sequence(squat_sequence([60, 60], foot_wobble=120.0), "s.mp4", CFG)
    assert not any("unsteady" in w for w in steady["warnings"])
    assert any("unsteady" in w for w in wobbly["warnings"])
    assert wobbly["camera"]["foot_travel"] > CFG.max_foot_travel
