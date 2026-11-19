"""Adaptation-engine scenarios built from fake session histories (newest first)."""

import pytest

from backend.planning.adaptation import AdaptConfig, next_workout

CFG = AdaptConfig()


def session(rep_count, form_score, load=100.0, target_reps=10, rpe=None, unit="lb", sid="s"):
    return {
        "session_id": sid,
        "workout": {"load": load, "unit": unit, "target_reps": target_reps, "rpe": rpe},
        "report": {"exercise": "squat", "rep_count": rep_count, "form_score": form_score,
                   "cues": ["Rep 2: Squat deeper."] if form_score and form_score < 1 else []},
    }


def decide(*history):
    return next_workout(list(history), CFG)


# --- Progress -----------------------------------------------------------------------
def test_good_form_all_reps_adds_a_rep():
    d = decide(session(10, 1.0, load=100, target_reps=10))
    assert d["decision"] == "increase"
    assert d["next"] == {"load": 100.0, "unit": "lb", "target_reps": 11}


def test_top_of_rep_range_adds_weight_and_resets_reps():
    d = decide(session(12, 0.92, load=100, target_reps=12))
    assert d["decision"] == "increase"
    assert d["next"] == {"load": 105.0, "unit": "lb", "target_reps": 8}


def test_kg_uses_smaller_increment():
    d = decide(session(12, 1.0, load=60, target_reps=12, unit="kg"))
    assert d["next"]["load"] == 62.5


def test_bodyweight_progresses_by_reps_then_caps():
    assert decide(session(10, 1.0, load=0, target_reps=10))["next"]["target_reps"] == 12
    capped = decide(session(20, 1.0, load=0, target_reps=20))
    assert capped["decision"] == "hold" and "adding weight" in capped["reason"]


def test_no_target_given_judges_against_reps_done():
    d = decide(session(9, 1.0, load=100, target_reps=None))
    assert d["decision"] == "increase" and d["next"]["target_reps"] == 10


# --- Hold -------------------------------------------------------------------------
def test_form_breakdown_holds_and_keeps_cue():
    d = decide(session(10, 0.7))
    assert d["decision"] == "hold"
    assert d["next"] == {"load": 100.0, "unit": "lb", "target_reps": 10}
    assert d["cues"] == ["Rep 2: Squat deeper."]


def test_good_form_but_very_hard_rpe_holds():
    d = decide(session(10, 1.0, rpe=9))
    assert d["decision"] == "hold" and "RPE 9" in d["reason"]


def test_rpe_8_still_progresses():
    assert decide(session(10, 1.0, rpe=8))["decision"] == "increase"


# --- Reduce and deload -------------------------------------------------------------------
def test_missed_reps_reduces_load():
    d = decide(session(7, 1.0, load=100, target_reps=10))
    assert d["decision"] == "reduce"
    assert d["next"] == {"load": 95.0, "unit": "lb", "target_reps": 10}
    assert "7 of 10" in d["reason"]


def test_poor_form_reduces_load():
    assert decide(session(10, 0.4))["decision"] == "reduce"


def test_bodyweight_missed_reps_aims_for_what_was_done():
    d = decide(session(7, 1.0, load=0, target_reps=10))
    assert d["decision"] == "reduce" and d["next"]["target_reps"] == 7


def test_poor_form_twice_deloads():
    d = decide(session(10, 0.3, load=100, sid="new"), session(10, 0.4, load=100, sid="old"))
    assert d["decision"] == "deload"
    assert d["next"] == {"load": 90.0, "unit": "lb", "target_reps": 8}
    assert d["based_on"] == ["new", "old"]


def test_deload_rounds_down_to_plate_increment():
    d = decide(session(10, 0.3, load=135), session(10, 0.2, load=135))
    assert d["next"]["load"] == 120.0  # 90% of 135 = 121.5 -> 120


def test_poor_form_once_after_good_session_only_reduces():
    assert decide(session(10, 0.3), session(10, 1.0))["decision"] == "reduce"


def test_load_never_goes_negative():
    assert decide(session(5, 1.0, load=2.5, target_reps=10))["next"]["load"] == 0.0


# --- Edge cases ------------------------------------------------------------------------
def test_no_reps_detected_asks_to_retest():
    d = decide(session(0, None))
    assert d["decision"] == "retest"
    assert d["next"] == {"load": 100.0, "unit": "lb", "target_reps": 10}


def test_old_session_without_workout_fields_is_bodyweight():
    old = {"session_id": "x", "report": {"exercise": "squat", "rep_count": 3, "form_score": 1.0}}
    d = next_workout([old], CFG)
    assert d["decision"] == "increase" and d["next"] == {"load": 0.0, "unit": "lb", "target_reps": 5}


def test_empty_history_raises():
    with pytest.raises(ValueError):
        next_workout([], CFG)
