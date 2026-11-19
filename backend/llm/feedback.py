"""Feedback writer: turn a form report + next-workout decision into coaching text.

Privacy: only numbers and error codes are sent to the LLM (no video, no file
name, no user identity). The LLM explains decisions; it never makes them:
the rep count, pass/fail, and next-session load all come from our own code.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from .client import LLMClient, LLMError

FEEDBACK_SYSTEM_PROMPT = """\
You are a supportive strength coach writing feedback for a beginner who just
recorded one set of squats. You receive measurements from a pose-analysis
system as JSON.

Rules:
- Use ONLY the facts in the JSON. Never invent reps, angles, or errors.
- Do not change the next-session decision; explain it in plain words.
- Plain language for a beginner: say "thighs parallel to the floor", not
  "knee flexion angle". Mention at most one number per sentence.
- summary and next_session: 1-2 sentences each. At most 3 tips, each one
  short actionable sentence (under 25 words). If every rep passed,
  give encouragement and one thing to keep doing.
- If there are warnings (camera angle, visibility), mention the most
  important one first, because the measurements may be less reliable.
- No medical advice or injury diagnosis. If something hurts, say to stop
  and consult a professional.
"""


# No max-length constraints in the schema sent to Gemini (keeps constrained
# decoding simple). Lengths are asked for in the prompt and enforced in
# check_feedback() instead.
class Feedback(BaseModel):
    summary: str = Field(description="1-2 sentences on how the set went")
    tips: list[str] = Field(description="up to 3 short actionable coaching tips")
    next_session: str = Field(description="1-2 sentences explaining the next-session decision")


MAX_TIPS = 3
MAX_CHARS = 400  # per text field


def check_feedback(fb: Feedback) -> Feedback:
    """Enforce length limits on the LLM reply (extra tips are dropped)."""
    fb = Feedback(summary=fb.summary.strip(), next_session=fb.next_session.strip(),
                  tips=[t.strip() for t in fb.tips if t.strip()][:MAX_TIPS])
    too_long = [len(fb.summary), len(fb.next_session), *map(len, fb.tips)]
    if not fb.summary or not fb.next_session:
        raise LLMError("feedback reply had an empty field")
    if max(too_long) > MAX_CHARS:
        raise LLMError(f"feedback reply too long ({max(too_long)} chars)")
    return fb


def feedback_input(report: dict, next_workout: dict) -> dict:
    """The exact data sent to the LLM: numbers and codes only."""
    return {
        "rep_count": report["rep_count"],
        "reps_passed": report["reps_passed"],
        "form_score": report["form_score"],
        "reps": [
            {"rep": r["number"], "bottom_knee_angle_deg": r["bottom_knee_angle"],
             "torso_lean_deg": r["torso_lean_at_bottom"], "errors": r["errors"]}
            for r in report["reps"]
        ],
        "limits": {
            "depth_pass_if_knee_angle_at_most_deg": report["thresholds"]["max_bottom_knee_angle"],
            "lean_pass_if_torso_lean_at_most_deg": report["thresholds"]["max_torso_lean"],
        },
        "warnings": report["warnings"],
        "next_session": {
            "decision": next_workout["decision"],
            "load": next_workout["next"]["load"],
            "unit": next_workout["next"]["unit"],
            "target_reps": next_workout["next"]["target_reps"],
            "reason": next_workout["reason"],
        },
    }


def template_feedback(report: dict, next_workout: dict) -> Feedback:
    """Rule-based fallback: same facts, fixed wording."""
    total, passed = report["rep_count"], report["reps_passed"]
    if total == 0:
        summary = "No reps were detected in this video."
    elif passed == total:
        summary = f"All {total} reps passed the depth and torso checks. Nice work."
    else:
        summary = f"{passed} of {total} reps passed the depth and torso checks."
    tips = (report["warnings"] + report["cues"])[:3]
    if not tips and total:
        tips = ["Keep the same controlled pace and depth on your next set."]
    return Feedback(summary=summary, tips=tips, next_session=next_workout["reason"])


def write_feedback(report: dict, next_workout: dict, client: LLMClient | None) -> dict:
    """LLM feedback if possible, otherwise template text. Always returns a result."""
    fallback_reason = "no LLM configured"
    if client is not None and report["rep_count"] > 0:
        prompt = ("Write feedback for this set.\n\n"
                  + json.dumps(feedback_input(report, next_workout), indent=2))
        try:
            fb = check_feedback(client.generate_json(FEEDBACK_SYSTEM_PROMPT, prompt, Feedback))
            return {**fb.model_dump(), "source": "llm", "model": client.name}
        except LLMError as e:
            fallback_reason = str(e)
    elif client is not None:
        fallback_reason = "no reps to describe"
    fb = template_feedback(report, next_workout)
    return {**fb.model_dump(), "source": "template", "model": None,
            "fallback_reason": fallback_reason}
