"""Reproduce a sample result with no video, pose model, or API key.

Builds a synthetic side-view squat set with known geometry (3 reps; rep 2
stops with the thigh about 26 deg above parallel, too shallow), runs it through
the same analysis, adaptation, and feedback code the app uses, and prints the
result.

    python scripts/sample_result.py              # summary
    python scripts/sample_result.py --json       # full JSON (as the API returns it)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.analysis.analyze import analyze_sequence  # noqa: E402
from backend.llm.feedback import write_feedback  # noqa: E402
from backend.planning.adaptation import next_workout  # noqa: E402
from backend.tests.synthetic import squat_sequence  # noqa: E402

# 30 fps stick figure: knee angle at the bottom 62, 88, 60 deg (thigh about 7, 26,
# 6 deg above parallel); torso lean up to 44, 38, 47 deg.
seq = squat_sequence([62, 88, 60], leans=[44, 38, 47], pause_seconds=0.7)
report = analyze_sequence(seq, "synthetic_squat.mp4")
session = {"session_id": "sample", "workout": {"load": 95, "unit": "lb", "target_reps": 3, "rpe": 7},
           "report": report}
decision = next_workout([session])
feedback = write_feedback(report, decision, client=None)  # template text: no API key needed

if "--json" in sys.argv:
    report = {k: v for k, v in report.items() if k != "trace"}  # trace omitted for readability
    print(json.dumps({"report": report, "next_workout": decision, "feedback": feedback}, indent=2))
    sys.exit()

print(f"Reps detected: {report['rep_count']}   passed: {report['reps_passed']}   "
      f"form score: {report['form_score']:.0%}")
for r in report["reps"]:
    status = "PASS" if r["passed"] else "FAIL " + ", ".join(r["errors"])
    print(f"  Rep {r['number']}: bottom at {r['bottom_time']:.2f} s, thigh {r['bottom_thigh_angle']:.1f} deg above "
          f"parallel, lean {r['torso_lean_at_bottom']:.1f} deg -> {status}")
n = decision["next"]
print(f"\nNext set: {decision['decision'].upper()} -> {n['load']:g} {n['unit']} x {n['target_reps']}")
print(f"  {decision['reason']}")
print(f"\nFeedback ({feedback['source']}): {feedback['summary']}")
for tip in feedback["tips"]:
    print(f"  - {tip}")
