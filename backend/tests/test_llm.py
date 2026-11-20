"""LLM feature tests with a fake client (no network, no API key)."""

import json

import pytest

from backend.llm.client import LLMError, get_llm_client
from backend.llm.feedback import Feedback, feedback_input, write_feedback
from backend.llm.plan import (FORM_CHECKABLE, PlanDay, PlanExercise, Profile, WeeklyPlan,
                              check_plan, generate_plan, template_plan)


class FakeLLM:
    """Returns queued replies in order; an Exception in the queue is raised."""
    name = "fake:test"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def generate_json(self, system, prompt, schema):
        self.calls.append({"system": system, "prompt": prompt, "schema": schema})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


REPORT = {
    "exercise": "squat", "video": "my_private_clip.mov", "rep_count": 3, "reps_passed": 2,
    "form_score": 0.67,
    "reps": [{"number": i, "bottom_thigh_angle": a, "torso_lean_at_bottom": 30.0,
              "errors": e} for i, a, e in [(1, 6.0, []), (2, 28.0, ["shallow_depth"]), (3, 8.0, [])]],
    "cues": ["Rep 2: Squat deeper: lower until your thighs are about parallel to the floor."],
    "warnings": [],
    "thresholds": {"max_thigh_above_parallel": 15.0, "max_torso_lean": 50.0},
}
DECISION = {"decision": "hold", "next": {"load": 0.0, "unit": "lb", "target_reps": 3},
            "reason": "67% of reps had good form. Keep the same load and reps."}


# --- Client configuration ----------------------------------------------------------------
@pytest.mark.parametrize("env", [{"LLM_PROVIDER": "none"}, {"GEMINI_API_KEY": ""},
                                 {"GEMINI_API_KEY": "your-key-here"}])
def test_no_client_without_key_or_when_disabled(monkeypatch, env):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert get_llm_client() is None


def test_unknown_provider_is_an_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mystery")
    with pytest.raises(ValueError):
        get_llm_client()


# --- Feedback writer -----------------------------------------------------------------------
def test_feedback_uses_llm_reply():
    llm = FakeLLM(Feedback(summary="Solid set.", tips=["Go a bit deeper on every rep."],
                           next_session="Repeat the same set."))
    fb = write_feedback(REPORT, DECISION, llm)
    assert fb["source"] == "llm" and fb["model"] == "fake:test" and fb["summary"] == "Solid set."


def test_feedback_prompt_has_numbers_only_no_video_name():
    llm = FakeLLM(Feedback(summary="ok", tips=[], next_session="ok"))
    write_feedback(REPORT, DECISION, llm)
    prompt = llm.calls[0]["prompt"]
    assert "my_private_clip" not in prompt
    sent = json.loads(prompt.split("\n\n", 1)[1])
    assert sent == feedback_input(REPORT, DECISION)
    assert sent["reps"][1]["errors"] == ["shallow_depth"]


def test_feedback_schema_sent_to_llm_has_no_length_constraints():
    schema = json.dumps(Feedback.model_json_schema())
    assert "maxLength" not in schema and "maxItems" not in schema


def test_feedback_extra_tips_are_dropped():
    llm = FakeLLM(Feedback(summary="ok", tips=["a", "b", "c", "d", " "], next_session="ok"))
    assert write_feedback(REPORT, DECISION, llm)["tips"] == ["a", "b", "c"]


def test_feedback_too_long_falls_back():
    llm = FakeLLM(Feedback(summary="x" * 500, tips=[], next_session="ok"))
    fb = write_feedback(REPORT, DECISION, llm)
    assert fb["source"] == "template" and "too long" in fb["fallback_reason"]


def test_feedback_falls_back_on_llm_error():
    fb = write_feedback(REPORT, DECISION, FakeLLM(LLMError("ClientError (429)")))
    assert fb["source"] == "template" and fb["fallback_reason"] == "ClientError (429)"
    assert fb["tips"] == REPORT["cues"] and fb["next_session"] == DECISION["reason"]


def test_feedback_template_without_llm():
    fb = write_feedback(REPORT, DECISION, None)
    assert fb["source"] == "template" and fb["summary"] == "2 of 3 reps passed the depth and torso checks."


def test_feedback_skips_llm_when_no_reps():
    llm = FakeLLM()
    empty = {**REPORT, "rep_count": 0, "reps_passed": 0, "form_score": None, "reps": [],
             "cues": [], "warnings": ["No reps detected."]}
    fb = write_feedback(empty, DECISION, llm)
    assert llm.calls == [] and fb["source"] == "template"


# --- Plan generator ----------------------------------------------------------------------
PROFILE = Profile(goal="muscle", experience="beginner", days_per_week=3, equipment="dumbbells")


def day(n, names, sets=3, reps=10, rest=90):
    return PlanDay(day=n, focus="Full body",
                   exercises=[PlanExercise(name=x, sets=sets, reps=reps, rest_seconds=rest) for x in names])


GOOD = WeeklyPlan(rationale="Balanced.", days=[
    day(1, ["Goblet squat", "Dumbbell bench press", "Dumbbell row"]),
    day(2, ["Dumbbell Romanian deadlift", "Dumbbell shoulder press", "Dumbbell row"]),
    day(3, ["Goblet squat", "Push-up", "Glute bridge"]),
])


def test_good_llm_plan_is_accepted_and_form_check_marked():
    out = generate_plan(PROFILE, FakeLLM(GOOD))
    assert out["source"] == "llm" and out["attempts"] == 1
    flags = {e["name"]: e["form_check"] for d in out["plan"]["days"] for e in d["exercises"]}
    assert flags["Goblet squat"] is True and flags["Dumbbell row"] is False


def test_check_plan_catches_each_violation():
    bad = WeeklyPlan(rationale="x", days=[
        day(1, ["Goblet squat", "Barbell back squat", "Dumbbell row"], sets=6),  # not in library, too many sets
        day(2, ["Dumbbell row", "Push-up"], reps=30, rest=10),                     # too few exercises, reps, rest
    ])
    problems = " | ".join(check_plan(bad, PROFILE))
    for expected in ["2 days; needs exactly 3", "'Barbell back squat' is not in the allowed",
                     "sets=6", "2 exercises", "reps=30", "rest_seconds=10", "squat pattern on 1 days"]:
        assert expected in problems


def test_bad_plan_is_retried_with_the_problems_listed():
    bad = WeeklyPlan(rationale="x", days=GOOD.days[:2])  # one day short
    llm = FakeLLM(bad, GOOD)
    out = generate_plan(PROFILE, llm)
    assert out["source"] == "llm" and out["attempts"] == 2
    assert "needs exactly 3" in llm.calls[1]["prompt"]


def test_plan_falls_back_after_repeated_bad_plans():
    bad = WeeklyPlan(rationale="x", days=GOOD.days[:2])
    out = generate_plan(PROFILE, FakeLLM(bad, bad))
    assert out["source"] == "template" and "safety checks" in out["fallback_reason"]


def test_plan_falls_back_on_llm_error():
    out = generate_plan(PROFILE, FakeLLM(LLMError("timeout")))
    assert out["source"] == "template" and out["fallback_reason"] == "timeout"


@pytest.mark.parametrize("equipment", ["bodyweight", "dumbbells", "full_gym"])
@pytest.mark.parametrize("goal", ["strength", "muscle", "general_fitness"])
@pytest.mark.parametrize("days", [2, 3, 4, 5])
@pytest.mark.parametrize("experience", ["beginner", "intermediate"])
def test_template_plan_always_passes_safety_checks(equipment, goal, days, experience):
    profile = Profile(goal=goal, experience=experience, days_per_week=days, equipment=equipment)
    plan = template_plan(profile)
    assert check_plan(plan, profile) == []
    assert any(e.name in FORM_CHECKABLE for e in plan.days[0].exercises)
