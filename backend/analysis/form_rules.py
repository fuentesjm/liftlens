"""Rule-based form checks for each squat rep (side view)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .angles import SquatSeries
from .config import SquatConfig
from .reps import Rep, deepest_frame

# Plain-language cue for each error code (shown to the user; also given to the
# LLM feedback writer later as structured input).
CUES = {
    "shallow_depth": "Squat deeper: lower until your thighs are about parallel to the floor.",
    "forward_lean": "Keep your chest up: your torso is leaning too far forward at the bottom.",
}


@dataclass
class RepResult:
    number: int
    start_time: float
    bottom_time: float
    end_time: float
    bottom_thigh_angle: float     # degrees above parallel at the deepest point (<0 = below)
    bottom_knee_angle: float      # on-screen knee angle at the deepest point (for reference)
    torso_lean_at_bottom: float
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors


def evaluate_reps(reps: list[Rep], series: SquatSeries, cfg: SquatConfig) -> list[RepResult]:
    results = []
    for n, rep in enumerate(reps, start=1):
        bottom = deepest_frame(rep, series.thigh_angle)
        thigh = float(series.thigh_angle[bottom])
        knee = float(series.knee_angle[bottom])
        lean = float(series.torso_lean[bottom])
        errors = []
        if thigh > cfg.max_thigh_above_parallel:
            errors.append("shallow_depth")
        if lean > cfg.max_torso_lean:
            errors.append("forward_lean")
        results.append(RepResult(
            number=n,
            start_time=round(float(series.timestamps[rep.start]), 2),
            bottom_time=round(float(series.timestamps[bottom]), 2),
            end_time=round(float(series.timestamps[rep.end]), 2),
            bottom_thigh_angle=round(thigh, 1),
            bottom_knee_angle=round(knee, 1),
            torso_lean_at_bottom=round(lean, 1),
            errors=errors,
        ))
    return results
