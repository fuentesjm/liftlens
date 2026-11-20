"""Check that the LLM key in .env works: sends one sample feedback request
and one plan request, and prints what comes back.

    python scripts/check_llm.py
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.llm.client import get_llm_client  # noqa: E402
from backend.llm.feedback import write_feedback  # noqa: E402
from backend.llm.plan import Profile, generate_plan  # noqa: E402

REPORT = {
    "exercise": "squat", "video": "sample", "rep_count": 3, "reps_passed": 2, "form_score": 0.67,
    "reps": [{"number": 1, "bottom_thigh_angle": 6.0, "torso_lean_at_bottom": 38.0, "errors": []},
             {"number": 2, "bottom_thigh_angle": 28.0, "torso_lean_at_bottom": 35.0,
              "errors": ["shallow_depth"]},
             {"number": 3, "bottom_thigh_angle": 8.0, "torso_lean_at_bottom": 40.0, "errors": []}],
    "cues": ["Rep 2: Squat deeper: lower until your thighs are about parallel to the floor."],
    "warnings": [], "thresholds": {"max_thigh_above_parallel": 15.0, "max_torso_lean": 50.0},
}
DECISION = {"decision": "hold", "next": {"load": 0.0, "unit": "lb", "target_reps": 3},
            "reason": "67% of reps had good form. Keep the same load and reps and work on the cue."}

client = get_llm_client()
if client is None:
    sys.exit("No LLM configured: set GEMINI_API_KEY in .env (see .env.example).")
print(f"Using {client.name}\n\n--- Feedback ---")
t = time.time()
fb = write_feedback(REPORT, DECISION, client)
print(json.dumps(fb, indent=2))
print(f"({time.time() - t:.1f} s)")
print("\n--- Plan (muscle, beginner, 3 days, dumbbells) ---")
t = time.time()
plan = generate_plan(Profile(goal="muscle", days_per_week=3, equipment="dumbbells"), client)
print(json.dumps(plan, indent=2))
print(f"({time.time() - t:.1f} s)")
ok = fb["source"] == "llm" and plan["source"] == "llm"
print("\nLLM OK" if ok else "\nFell back to templates: see fallback_reason above.")
