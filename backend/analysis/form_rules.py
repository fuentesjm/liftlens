"""Rule-based form checks for each squat rep (side view)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .angles import SquatSeries
from .config import SquatConfig
from .reps import Rep

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
    bottom_knee_angle: float
    torso_lean_at_bottom: float
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors


def evaluate_reps(reps: list[Rep], series: SquatSeries, cfg: SquatConfig) -> list[RepResult]:
    results = []
    for n, rep in enumerate(reps, start=1):
        knee = float(series.knee_angle[rep.bottom])
        lean = float(series.torso_lean[rep.bottom])
        errors = []
        if knee > cfg.max_bottom_knee_angle:
            errors.append("shallow_depth")
        if lean > cfg.max_torso_lean:
            errors.append("forward_lean")
        results.append(RepResult(
            number=n,
            start_time=round(float(series.timestamps[rep.start]), 2),
            bottom_time=round(float(series.timestamps[rep.bottom]), 2),
            end_time=round(float(series.timestamps[rep.end]), 2),
            bottom_knee_angle=round(knee, 1),
            torso_lean_at_bottom=round(lean, 1),
            errors=errors,
        ))
    return results
