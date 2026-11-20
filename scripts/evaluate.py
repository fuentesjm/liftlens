"""Evaluate the squat analyzer on the team's labeled clips.

Labels live in samples/labels.csv, one row per clip:

    file,true_reps,shallow_reps,lean_reps,notes
    demo_bad_form.mov,5,1 2 3,4 5,too shallow on reps 1-3; leaning on 4-5

- true_reps:    how many reps were actually done
- shallow_reps: which reps (1-based, space separated) did NOT reach parallel
- lean_reps:    which reps had the chest dropping too far forward
Leave a fault column empty if no rep had that fault.

    python scripts/evaluate.py                      # uses samples/labels.csv
    python scripts/evaluate.py --labels other.csv --out eval_results.json

Faults are compared rep by rep (rep 1 with rep 1, ...) only for clips where the
rep count matches; other clips count toward rep-count accuracy only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.analysis.analyze import NoPersonDetected, analyze_sequence  # noqa: E402
from backend.analysis.pose import DEFAULT_MODEL_PATH, extract_pose  # noqa: E402

FAULTS = {"shallow_depth": "shallow_reps", "forward_lean": "lean_reps"}
SHORT = {"shallow_depth": "shallow", "forward_lean": "lean"}


def parse_reps(text: str) -> set[int]:
    return {int(x) for x in (text or "").replace(",", " ").split()}


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p and r else (0.0 if p == 0 or r == 0 else None)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f1}


def fmt(x) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate LiftLens on labeled clips")
    ap.add_argument("--labels", default="samples/labels.csv")
    ap.add_argument("--model", default=str(DEFAULT_MODEL_PATH))
    ap.add_argument("--out", help="write detailed results as JSON")
    args = ap.parse_args()

    labels_path = Path(args.labels)
    rows = list(csv.DictReader(labels_path.open()))
    counts = {f: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for f in FAULTS}
    clips, exact, abs_err, total_true = [], 0, 0, 0

    print(f"{'clip':<26}{'true':>5}{'found':>6}  {'faults (predicted vs labeled)':<40}{'time':>7}")
    for row in rows:
        video = labels_path.parent / row["file"]
        true_reps = int(row["true_reps"])
        start = time.time()
        try:
            seq = extract_pose(video, args.model)
            report = analyze_sequence(seq, video.name)
        except (FileNotFoundError, NoPersonDetected) as e:
            print(f"{row['file']:<26} ERROR: {e}")
            continue
        seconds = time.time() - start
        found = report["rep_count"]
        exact += found == true_reps
        abs_err += abs(found - true_reps)
        total_true += true_reps

        per_fault = {}
        for fault, column in FAULTS.items():
            labeled = parse_reps(row[column])
            predicted = {r["number"] for r in report["reps"] if fault in r["errors"]}
            per_fault[fault] = {"labeled": sorted(labeled), "predicted": sorted(predicted)}
            if found == true_reps:  # rep-by-rep comparison only when counts match
                for n in range(1, true_reps + 1):
                    key = ("tp" if n in labeled else "fp") if n in predicted else ("fn" if n in labeled else "tn")
                    counts[fault][key] += 1

        summary = "; ".join(
            f"{SHORT[f]} {v['predicted'] or '-'} vs {v['labeled'] or '-'}" for f, v in per_fault.items())
        print(f"{row['file']:<26}{true_reps:>5}{found:>6}  {summary:<40}{seconds:>6.1f}s")
        clips.append({
            "file": row["file"], "notes": row.get("notes", ""), "true_reps": true_reps, "found_reps": found,
            "faults": per_fault, "processing_seconds": round(seconds, 2),
            "video_seconds": round(seq.timestamps[-1], 2) if seq.timestamps else None,
            "reps": [{k: r[k] for k in ("number", "bottom_knee_angle", "torso_lean_at_bottom", "errors")}
                     for r in report["reps"]],
            "warnings": report["warnings"],
            "shoulder_width_ratio": report["camera"]["shoulder_width_ratio"],
        })

    if not clips:
        sys.exit("No clips could be analyzed.")
    n = len(clips)
    summary = {
        "clips": n,
        "reps_labeled": total_true,
        "rep_count_exact_clips": f"{exact}/{n}",
        "rep_count_mae_per_clip": round(abs_err / n, 2),
        "faults": {f: {**prf(c["tp"], c["fp"], c["fn"]), "tn": c["tn"]} for f, c in counts.items()},
        "mean_processing_seconds": round(sum(c["processing_seconds"] for c in clips) / n, 2),
    }
    print("\nRep count: exact on", summary["rep_count_exact_clips"], "clips; mean absolute error",
          summary["rep_count_mae_per_clip"], "reps per clip")
    for f, m in summary["faults"].items():
        print(f"{f:<14} TP {m['tp']}  FP {m['fp']}  FN {m['fn']}  TN {m['tn']}   "
              f"precision {fmt(m['precision'])}  recall {fmt(m['recall'])}  F1 {fmt(m['f1'])}")
    print("Mean processing time:", summary["mean_processing_seconds"], "s per clip")
    if args.out:
        Path(args.out).write_text(json.dumps({"summary": summary, "clips": clips}, indent=2))
        print("Details written to", args.out)


if __name__ == "__main__":
    main()
