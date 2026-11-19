# LiftLens

AI workout planning with video-based form review. Team: Jose Fuentes, Perry Wang, Ari Montes.

A user uploads a side-view video of a set of squats; LiftLens counts the reps, checks each rep's form, and returns a per-rep report. Later stages use that report to adapt the next workout.

## Status

| Component | Status |
|---|---|
| Squat analysis pipeline (pose → angles → reps → form rules → JSON report) | **Done** (unit-tested on synthetic data) |
| Accuracy evaluation on real recorded clips | Planned |
| Annotated replay video | Planned |
| Push-up analysis | Planned |
| Adaptation engine (next-session load) | Planned |
| LLM plan generator and feedback writer | Planned |
| FastAPI backend and Next.js frontend | Planned |

## How it works

```
video ──► MediaPipe Pose Landmarker ──► joint angles ──► smoothing ──► rep segmentation ──► form rules ──► JSON report
          (pretrained model)            (our code from here on)
```

1. **Pose estimation** (`pose.py`): the pretrained MediaPipe Pose Landmarker finds 33 body landmarks per frame. This is the only pretrained model.
2. **Joint angles** (`angles.py`): picks the body side facing the camera, then computes the knee angle (hip–knee–ankle) and torso lean (shoulder–hip line vs. vertical) for every frame.
3. **Smoothing** (`smoothing.py`): fills frames where the body wasn't visible (linear interpolation) and smooths with a centered moving average.
4. **Rep segmentation** (`reps.py`): a two-threshold state machine on the knee angle. A rep starts when the angle drops below 140° and ends when it rises above 160°, so jitter between the thresholds can't count as extra reps.
5. **Form rules** (`form_rules.py`): a rep fails *depth* if its lowest knee angle is above 100°, and fails *forward lean* if the torso is more than 50° from vertical at the bottom. Thresholds live in `config.py`.
6. **Report** (`report.py`): rep count, per-rep times and angles, errors, form score (fraction of reps passed), coaching cues, and warnings.

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/download_model.py   # downloads the pose model into models/
```

No API keys are needed yet. When the LLM features are added, copy `.env.example` to `.env` and add the key there.

## Run

Record a squat set **from the side**, with your whole body in frame, then:

```bash
python -m backend.analysis.analyze samples/squat_side.mp4
python -m backend.analysis.analyze samples/squat_side.mp4 --out report.json
```

## Reproduce a sample result

```bash
python -m pytest -q backend/tests
```

The tests generate synthetic side-view squats with known knee angles (`backend/tests/synthetic.py`) and check rep counting, depth and lean detection, jitter rejection, timing, and visibility warnings, with no video or model needed.

## Main files

| File | Purpose |
|---|---|
| `backend/analysis/analyze.py` | command-line entry point; runs the whole pipeline |
| `backend/analysis/pose.py` | MediaPipe pose extraction from a video file |
| `backend/analysis/angles.py` | knee angle and torso lean per frame |
| `backend/analysis/smoothing.py` | gap filling and smoothing |
| `backend/analysis/reps.py` | rep segmentation |
| `backend/analysis/form_rules.py` | per-rep form checks and cue text |
| `backend/analysis/report.py` | JSON report |
| `backend/analysis/config.py` | all thresholds in one place |
| `backend/tests/` | unit tests and the synthetic squat generator |
| `scripts/download_model.py` | downloads the pose model |

## Known limitations

- Side view only; knee cave-in (valgus) needs a front view and isn't checked.
- Thresholds are starting values and still need calibrating on real labeled clips.
- Accuracy on real videos has not been measured yet.
