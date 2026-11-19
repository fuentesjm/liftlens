"""Adaptation engine: decide the next session's load and reps from past sessions.

Rule-based on purpose: progression decisions affect safety, so they should be
predictable, explainable, and testable. The rules (from the Phase 1 plan):

    good form + all target reps  -> progress (double progression, see below)
    form breakdown               -> hold load and reps, repeat the form cue
    missed reps or poor form     -> reduce
    poor form twice in a row     -> deload (bigger reduction, reset reps)
    no reps detected             -> retest (re-record; nothing to judge)

Double progression: within a rep range (default 8-12), first add one rep per
session at the same load. Once the top of the range is reached with good form,
add one weight increment and drop back to the bottom of the range.
Bodyweight sets (load 0) progress by reps only, up to a cap.

Each session is a dict as saved by the API: {"session_id", "created_at",
"workout": {"load", "unit", "target_reps", "rpe"}, "report": {...}}.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class AdaptConfig:
    good_form_score: float = 0.8     # at or above: good form
    poor_form_score: float = 0.5     # below: poor form; in between: form breakdown
    rep_min: int = 8                 # double-progression rep range (weighted sets)
    rep_max: int = 12
    bodyweight_rep_max: int = 20     # bodyweight sets progress by reps up to this
    bodyweight_rep_step: int = 2     # bodyweight reps added/removed per decision
    max_rpe_to_progress: int = 8     # RPE 9-10 = near failure: don't add more yet
    deload_factor: float = 0.9       # deload to 90% of the load
    increments: tuple = (("lb", 5.0), ("kg", 2.5))  # smallest load step per unit

    def increment(self, unit: str) -> float:
        return dict(self.increments).get(unit, 5.0)


DEFAULT_ADAPT_CONFIG = AdaptConfig()


def _round_down(value: float, step: float) -> float:
    return max(0.0, math.floor(value / step + 1e-9) * step)


def _workout(session: dict) -> dict:
    """Workout fields with defaults (sessions saved before these existed have none)."""
    w = session.get("workout") or {}
    return {
        "load": float(w.get("load") or 0.0),
        "unit": w.get("unit") or "lb",
        "target_reps": w.get("target_reps"),
        "rpe": w.get("rpe"),
    }


def next_workout(history: list[dict], cfg: AdaptConfig = DEFAULT_ADAPT_CONFIG) -> dict:
    """Decide the next session for one exercise. `history` is newest first."""
    if not history:
        raise ValueError("No sessions to base a decision on.")

    last = history[0]
    report, w = last["report"], _workout(last)
    load, unit, rpe = w["load"], w["unit"], w["rpe"]
    done = report["rep_count"]
    target = w["target_reps"] or done      # no target given: judge against what was done
    score = report["form_score"]
    bodyweight = load == 0
    step = cfg.increment(unit)

    def result(decision: str, new_load: float, new_reps: int, reason: str) -> dict:
        return {
            "exercise": report["exercise"],
            "decision": decision,
            "next": {"load": round(new_load, 2), "unit": unit, "target_reps": int(new_reps)},
            "previous": {"load": load, "unit": unit, "target_reps": target,
                         "reps_done": done, "form_score": score, "rpe": rpe},
            "reason": reason,
            "cues": report.get("cues", []),
            "based_on": [s["session_id"] for s in history[:2]],
        }

    # 0. Nothing detected: the video can't tell us anything about the set.
    if done == 0 or score is None:
        return result("retest", load, target,
                      "No reps were detected, so the set can't be judged. Re-record it "
                      "from the side with your whole body in frame.")

    poor = score < cfg.poor_form_score
    good = score >= cfg.good_form_score
    missed = done < target

    # 1. Poor form two sessions in a row: deload.
    prev = history[1]["report"] if len(history) > 1 else None
    if poor and prev and prev["form_score"] is not None and prev["form_score"] < cfg.poor_form_score:
        if bodyweight:
            return result("deload", 0.0, cfg.rep_min,
                          f"Form was poor in your last two sessions. Drop to {cfg.rep_min} reps "
                          "and focus on clean technique.")
        new_load = _round_down(load * cfg.deload_factor, step)
        return result("deload", new_load, cfg.rep_min,
                      f"Form was poor in your last two sessions. Deload to {new_load:g} {unit} "
                      f"for {cfg.rep_min} reps and focus on clean technique.")

    # 2. Missed reps or poor form: reduce.
    if missed or poor:
        why = (f"You completed {done} of {target} target reps" if missed
               else f"Only {score:.0%} of reps had good form")
        if bodyweight:
            new_reps = done if missed else max(1, target - cfg.bodyweight_rep_step)
            return result("reduce", 0.0, new_reps, f"{why}. Next time aim for {new_reps} reps.")
        new_load = max(0.0, load - step)
        return result("reduce", new_load, target,
                      f"{why}. Reduce to {new_load:g} {unit} and keep {target} reps.")

    # 3. Form breakdown (between poor and good): hold.
    if not good:
        return result("hold", load, target,
                      f"{score:.0%} of reps had good form. Keep the same load and reps "
                      "and work on the cue below before progressing.")

    # 4. Good form and all reps, but the set felt near-maximal: hold.
    if rpe is not None and rpe > cfg.max_rpe_to_progress:
        return result("hold", load, target,
                      f"Good form and all reps, but you rated it RPE {rpe}. Repeat it until "
                      "it feels easier before progressing.")

    # 5. Good form and all reps: progress (double progression).
    if bodyweight:
        if target >= cfg.bodyweight_rep_max:
            return result("hold", 0.0, target,
                          f"You've reached {target} bodyweight reps with good form. "
                          "Consider adding weight (log it as the load) to keep progressing.")
        new_reps = min(cfg.bodyweight_rep_max, target + cfg.bodyweight_rep_step)
        return result("increase", 0.0, new_reps,
                      f"Good form on all {done} reps. Next time aim for {new_reps} reps.")
    if target < cfg.rep_max:
        return result("increase", load, target + 1,
                      f"Good form on all {done} reps. Add one rep: {target + 1} reps "
                      f"at {load:g} {unit}.")
    new_load = load + step
    return result("increase", new_load, cfg.rep_min,
                  f"Good form on all {done} reps at the top of the {cfg.rep_min}-{cfg.rep_max} "
                  f"range. Add {step:g} {unit} ({new_load:g} {unit}) and restart at {cfg.rep_min} reps.")
