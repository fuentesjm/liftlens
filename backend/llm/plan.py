"""Plan generator: user profile -> weekly workout plan (validated JSON).

Flow:
  1. Ask the LLM for a plan in a fixed JSON schema (Gemini JSON mode).
  2. Validate it against safety bounds in our own code (check_plan).
  3. If it breaks any bound, retry once, telling the LLM exactly what was wrong.
  4. If it still fails (or there is no LLM), use the rule-based template plan.

Exercises must come from a fixed library for the user's equipment, so the LLM
can't suggest unsafe or unknown movements. Whether an exercise can be form-
checked by video is decided by our code, not by the LLM.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from .client import LLMClient, LLMError

# --- Exercise library ---------------------------------------------------------------
BODYWEIGHT = ["Bodyweight squat", "Push-up", "Incline push-up", "Reverse lunge",
              "Glute bridge", "Split squat", "Calf raise", "Bird dog"]
DUMBBELLS = BODYWEIGHT + ["Goblet squat", "Dumbbell row", "Dumbbell bench press",
                          "Dumbbell Romanian deadlift", "Dumbbell shoulder press"]
FULL_GYM = DUMBBELLS + ["Barbell back squat", "Bench press", "Barbell row", "Deadlift",
                        "Lat pulldown", "Leg press", "Overhead press", "Seated cable row"]
LIBRARY = {"bodyweight": BODYWEIGHT, "dumbbells": DUMBBELLS, "full_gym": FULL_GYM}

# Exercises the video analyzer can check today (push-ups are planned).
FORM_CHECKABLE = {"Bodyweight squat", "Goblet squat", "Barbell back squat"}

# --- Safety bounds (checked in code, not trusted to the LLM) -----------------------
BOUNDS = {
    "exercises_per_day": (3, 6),
    "sets": (1, 5),
    "reps": (5, 20),
    "rest_seconds": (30, 240),
    "max_sets_per_day": {"beginner": 16, "intermediate": 22},
}


class Profile(BaseModel):
    goal: Literal["strength", "muscle", "general_fitness"] = "general_fitness"
    experience: Literal["beginner", "intermediate"] = "beginner"
    days_per_week: int = Field(3, ge=2, le=5)
    equipment: Literal["bodyweight", "dumbbells", "full_gym"] = "bodyweight"
    session_minutes: int = Field(45, ge=20, le=90)


class PlanExercise(BaseModel):
    name: str
    sets: int
    reps: int
    rest_seconds: int


class PlanDay(BaseModel):
    day: int = Field(description="1-based training day number")
    focus: str = Field(description="short label, e.g. 'Full body A'")
    exercises: list[PlanExercise]


class WeeklyPlan(BaseModel):
    days: list[PlanDay]
    rationale: str = Field(description="2-3 sentences on why this plan fits the profile")


PLAN_SYSTEM_PROMPT = """\
You are a certified strength coach designing a safe weekly plan for a
beginner-to-intermediate lifter. Reply with JSON only, matching the schema.

Rules:
- Exactly the requested number of training days, numbered 1..N.
- Use ONLY exercise names from the allowed list, spelled exactly as given.
- Every day: {ex_min}-{ex_max} exercises; sets {s_min}-{s_max}; reps {r_min}-{r_max};
  rest {rest_min}-{rest_max} seconds; at most {max_sets} total sets per day.
- Include a squat pattern at least twice a week (the app can video-check squats).
- Balance lower body, upper-body push, and upper-body pull across the week.
- Fit each session in the given minutes (roughly 2-3 minutes per set incl. rest).
- Strength goal: fewer reps (5-8), longer rest. Muscle: 8-12 reps.
  General fitness: 10-15 reps, shorter rest.
- The rationale explains the choices in plain language. No medical advice.
"""


def _system_prompt(profile: Profile) -> str:
    return PLAN_SYSTEM_PROMPT.format(
        ex_min=BOUNDS["exercises_per_day"][0], ex_max=BOUNDS["exercises_per_day"][1],
        s_min=BOUNDS["sets"][0], s_max=BOUNDS["sets"][1],
        r_min=BOUNDS["reps"][0], r_max=BOUNDS["reps"][1],
        rest_min=BOUNDS["rest_seconds"][0], rest_max=BOUNDS["rest_seconds"][1],
        max_sets=BOUNDS["max_sets_per_day"][profile.experience],
    )


def _user_prompt(profile: Profile, problems: list[str] | None = None) -> str:
    text = ("Create a weekly plan for this profile:\n"
            + json.dumps(profile.model_dump(), indent=2)
            + "\n\nAllowed exercises:\n" + "\n".join(f"- {n}" for n in LIBRARY[profile.equipment]))
    if problems:
        text += ("\n\nYour previous plan broke these rules. Fix all of them:\n"
                 + "\n".join(f"- {p}" for p in problems))
    return text


def check_plan(plan: WeeklyPlan, profile: Profile) -> list[str]:
    """Return every safety-bound violation (empty list = plan is OK)."""
    problems = []
    allowed = set(LIBRARY[profile.equipment])
    if len(plan.days) != profile.days_per_week:
        problems.append(f"plan has {len(plan.days)} days; needs exactly {profile.days_per_week}")
    if [d.day for d in plan.days] != list(range(1, len(plan.days) + 1)):
        problems.append("days must be numbered 1..N in order")
    squat_days = 0
    for d in plan.days:
        lo, hi = BOUNDS["exercises_per_day"]
        if not lo <= len(d.exercises) <= hi:
            problems.append(f"day {d.day}: {len(d.exercises)} exercises (allowed {lo}-{hi})")
        total_sets = sum(e.sets for e in d.exercises)
        cap = BOUNDS["max_sets_per_day"][profile.experience]
        if total_sets > cap:
            problems.append(f"day {d.day}: {total_sets} total sets (max {cap})")
        if any(e.name in FORM_CHECKABLE or "squat" in e.name.lower() for e in d.exercises):
            squat_days += 1
        for e in d.exercises:
            if e.name not in allowed:
                problems.append(f"day {d.day}: '{e.name}' is not in the allowed exercise list")
            for field in ("sets", "reps", "rest_seconds"):
                lo, hi = BOUNDS[field]
                value = getattr(e, field)
                if not lo <= value <= hi:
                    problems.append(f"day {d.day}, {e.name}: {field}={value} (allowed {lo}-{hi})")
    if squat_days < min(2, profile.days_per_week):
        problems.append(f"squat pattern on {squat_days} days; needs at least 2")
    return problems


# --- Template fallback ----------------------------------------------------------------
_TEMPLATES = {
    # (squat, push, pull, hinge/extra lower, accessory) per equipment
    "bodyweight": [["Bodyweight squat", "Push-up", "Glute bridge", "Reverse lunge", "Bird dog"],
                   ["Bodyweight squat", "Incline push-up", "Split squat", "Calf raise", "Bird dog"]],
    "dumbbells": [["Goblet squat", "Dumbbell bench press", "Dumbbell row", "Glute bridge"],
                  ["Goblet squat", "Dumbbell shoulder press", "Dumbbell row",
                   "Dumbbell Romanian deadlift"]],
    "full_gym": [["Barbell back squat", "Bench press", "Barbell row", "Calf raise"],
                 ["Barbell back squat", "Overhead press", "Lat pulldown", "Deadlift"]],
}
_REPS = {"strength": (6, 180), "muscle": (10, 90), "general_fitness": (12, 60)}


def template_plan(profile: Profile) -> WeeklyPlan:
    """Deterministic full-body A/B plan that always passes check_plan."""
    reps, rest = _REPS[profile.goal]
    sets = 3
    days = []
    for i in range(profile.days_per_week):
        names = _TEMPLATES[profile.equipment][i % 2]
        days.append(PlanDay(
            day=i + 1, focus=f"Full body {'AB'[i % 2]}",
            exercises=[PlanExercise(name=n, sets=sets, reps=reps, rest_seconds=rest) for n in names],
        ))
    return WeeklyPlan(days=days, rationale=(
        f"A simple full-body plan alternating two workouts, {profile.days_per_week} days a week, "
        f"with {sets} sets of {reps} reps to match a {profile.goal.replace('_', ' ')} goal. "
        "Every day starts with a squat so you can record it for form review."))


def _with_form_check(plan: WeeklyPlan) -> dict:
    data = plan.model_dump()
    for day in data["days"]:
        for e in day["exercises"]:
            e["form_check"] = e["name"] in FORM_CHECKABLE  # decided by our code, not the LLM
    return data


def generate_plan(profile: Profile, client: LLMClient | None, max_attempts: int = 2) -> dict:
    """LLM plan that passes every safety bound, or the template plan."""
    problems: list[str] | None = None
    fallback_reason = "no LLM configured"
    if client is not None:
        for attempt in range(1, max_attempts + 1):
            try:
                plan = client.generate_json(_system_prompt(profile),
                                            _user_prompt(profile, problems), WeeklyPlan)
            except LLMError as e:
                fallback_reason = str(e)
                break
            problems = check_plan(plan, profile)
            if not problems:
                return {"profile": profile.model_dump(), "plan": _with_form_check(plan),
                        "source": "llm", "model": client.name, "attempts": attempt}
            fallback_reason = f"plan failed safety checks: {'; '.join(problems[:3])}"
    plan = template_plan(profile)
    return {"profile": profile.model_dump(), "plan": _with_form_check(plan),
            "source": "template", "model": None, "fallback_reason": fallback_reason}
