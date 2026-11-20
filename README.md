# LiftLens

AI workout planning with video-based form review. Team: Jose Fuentes, Perry Wang, Ari Montes.

A user uploads a side-view video of a set of squats; LiftLens counts the reps, checks each rep's form, and returns a per-rep report. Later stages use that report to adapt the next workout.

## Status

| Component | Status |
|---|---|
| Squat analysis pipeline (pose → angles → reps → form rules → JSON report) | **Done** (unit-tested on synthetic data; checked on 2 sample clips) |
| FastAPI backend: upload a video, get the report, list saved sessions | **Done** (API-tested) |
| Accuracy evaluation on real recorded clips | Planned |
| Skeleton overlay on the replay video (results page already replays each rep in sync with the chart) | Planned |
| Push-up analysis | Planned |
| Adaptation engine (next-session load and reps) | **Done** (rule-based; scenario-tested) |
| LLM feedback writer and plan generator (Gemini, safety-checked, template fallback) | **Done** (tested with a fake LLM; see `docs/llm.md`) |
| Next.js frontend: today's set, record/upload, per-rep results with chart and replay, plan, history | **Done** |

## How it works

```
video ──► MediaPipe Pose Landmarker ──► joint angles ──► smoothing ──► rep segmentation ──► form rules ──► JSON report
          (pretrained model)            (our code from here on)
```

1. **Pose estimation** (`pose.py`): the pretrained MediaPipe Pose Landmarker finds 33 body landmarks per frame. This is the only pretrained model.
2. **Joint angles** (`angles.py`): picks the body side facing the camera, then computes the knee angle (hip–knee–ankle) and torso lean (shoulder–hip line vs. vertical) for every frame.
3. **Smoothing** (`smoothing.py`): fills frames where the body wasn't visible (linear interpolation) and smooths with a centered moving average.
4. **Rep segmentation** (`reps.py`): a two-threshold state machine on the knee angle. A rep starts when the angle drops below the *down* threshold and ends when it rises above the *up* threshold, so jitter between them can't count as extra reps. The thresholds adapt to each clip: the person's standing angle is the 95th percentile of their knee angle, *up* is 10° below that (at most 160°) and *down* is 15° below *up* (at most 140°). This handles people who stand with soft knees or a camera that isn't perfectly side-on.
5. **Form rules** (`form_rules.py`): a rep fails *depth* if its lowest knee angle is above 100°, and fails *forward lean* if the torso is more than 50° from vertical at the bottom. Thresholds live in `config.py`.
6. **Report** (`report.py`): rep count, per-rep times and angles, errors, form score (fraction of reps passed), coaching cues, warnings, and the thresholds actually used. It also warns when the person seems turned toward the camera (the two shoulders appear far apart relative to torso length).

### Adaptation engine (`backend/planning/adaptation.py`)

After each uploaded set, the engine decides the next session from the saved history for that exercise. The inputs are the form score and rep count from the video, plus the load, target reps, and RPE the user enters at upload.

| Situation (latest set) | Decision |
|---|---|
| No reps detected | **retest**: re-record the set |
| Form score below 0.5 in the last two sessions | **deload**: 90% of the load (rounded down to a plate step), reset to 8 reps |
| Missed target reps, or form score below 0.5 | **reduce**: one weight step down (bodyweight: aim for the reps actually done) |
| Form score 0.5–0.8 | **hold**: same load and reps, repeat the form cue |
| Good form and all reps, but RPE 9–10 | **hold** until it feels easier |
| Good form and all reps | **increase** by double progression: +1 rep up to 12, then +1 weight step (5 lb / 2.5 kg) and back to 8 reps. Bodyweight: +2 reps up to 20 |

Every decision comes with a plain-language reason. The thresholds are in `AdaptConfig`. Rules are used here on purpose, so that safety-related decisions are predictable and testable.

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/download_model.py   # downloads the pose model into models/
```

Settings are environment variables listed in `.env.example`. Copy it to `.env` and edit; `.env` is gitignored and must never be committed.

**LLM key (optional):** for AI-written feedback and plans, get a free Gemini key at Google AI Studio and set `GEMINI_API_KEY` in `.env`. Without a key, everything still runs and uses template text instead. Prompts, inputs and outputs, and limitations are documented in [`docs/llm.md`](docs/llm.md).

## Run

Record a squat set **from the side**, with your whole body in frame, then:

```bash
python -m backend.analysis.analyze samples/squat_side.mp4
python -m backend.analysis.analyze samples/squat_side.mp4 --out report.json
```

### Run the web app

The app needs two terminals: the API server and the frontend.

```bash
# Terminal 1 (project folder, venv active)
uvicorn backend.api.main:app --reload

# Terminal 2 (needs Node.js 20 or newer)
cd frontend
npm install        # first time only
npm run dev
```

Open http://localhost:3000. The full flow:

1. **Plan:** pick a goal, experience, equipment, and days, then **Create plan**.
2. **Record a set:** choose a side-view squat video, enter the weight and target reps (and optionally RPE), then **Analyze set**.
3. **Results:** the verdict, a knee-angle chart with each rep marked passed (green) or failed (red), the depth line, per-rep angles, coach notes, and the next set. Click a rep on the chart or **Replay** to jump the video to it.
4. **Today:** shows the next set. **Record this set** pre-fills the upload form with it.
5. **History:** every set, newest first.

If the API runs somewhere other than `http://127.0.0.1:8000`, copy `frontend/.env.local.example` to `frontend/.env.local` and change `NEXT_PUBLIC_API_URL`.

### Run the API server

```bash
uvicorn backend.api.main:app --reload
```

Open http://127.0.0.1:8000/docs to try every endpoint in the browser (click **POST /analyze → Try it out**, choose a video, **Execute**). Or from a terminal:

```bash
curl -F "file=@samples/squat_side.mp4" -F "exercise=squat" \
     -F "load=95" -F "unit=lb" -F "target_reps=10" -F "rpe=7" \
     http://127.0.0.1:8000/analyze
```

| Endpoint | What it does |
|---|---|
| `GET /health` | server is up; `model_ready` = pose model downloaded; `llm` = active LLM (or `null` = template text) |
| `POST /analyze` | form fields `file` (video: mp4, mov, m4v, avi, webm), `exercise` (`squat`), and optional `load` (0 = bodyweight), `unit` (`lb`/`kg`), `target_reps`, `rpe` (1–10). Saves the session and returns `{session_id, created_at, workout, report, next_workout, feedback}` |
| `GET /sessions` | saved sessions, newest first (id, date, rep count, form score) |
| `GET /sessions/{session_id}` | one saved session with its full report |
| `GET /next-workout?exercise=squat` | the next-session decision from the saved history |
| `POST /plan` | JSON profile `{goal, experience, days_per_week, equipment, session_minutes}` → safety-checked weekly plan (saved) |
| `GET /plan` | the saved weekly plan |

Uploaded videos are written to a temporary folder only while they're analyzed, then deleted. Reports are saved as JSON in `data/sessions/` (gitignored).

Errors: `400` wrong file type, empty or unreadable video, or unsupported exercise; `413` file over the size limit; `422` no person detected or an invalid workout field (e.g. RPE 11); `404` no saved sessions for `/next-workout`; `503` pose model not downloaded.

## Reproduce a sample result

```bash
python -m pytest -q backend/tests
```

`test_analysis.py` and `test_api.py` generate synthetic side-view squats with known knee angles (`backend/tests/synthetic.py`) and check rep counting, depth and lean detection, jitter rejection, timing, visibility warnings, soft-knee standing, and the camera-angle warning, with no video or model needed. The API tests swap the pose model for the same generator and check uploads, saved sessions, and every error response. `test_llm.py` checks the LLM features with a fake client: feedback and plan parsing, the numbers-only prompt, retry on unsafe plans, every fallback, and that the template plan passes the safety checks for all profile combinations. No test calls the real API. `test_adaptation.py` runs the adaptation rules on fake session histories (progress, hold, reduce, deload, retest, kg vs lb, bodyweight, old sessions without workout fields).

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
| `backend/api/main.py` | FastAPI app and endpoints |
| `backend/api/storage.py` | saves and loads session reports (JSON files) |
| `backend/api/settings.py` | server settings from environment variables |
| `backend/planning/adaptation.py` | adaptation engine: next-session load and reps |
| `backend/llm/client.py` | Gemini wrapper (JSON mode, key from env, errors → fallback) |
| `backend/llm/feedback.py` | feedback writer: prompt, schema, template fallback |
| `backend/llm/plan.py` | plan generator: prompt, schema, safety checks, retry, template plan |
| `docs/llm.md` | LLM prompts, API workflow, inputs and outputs, limitations, team contribution |
| `frontend/app/` | Next.js pages: Today (`page.jsx`), `record/`, `sessions/[id]/` (results), `plan/`, `history/` |
| `frontend/components/KneeTrace.jsx` | knee-angle chart with rep bands, depth line, and video playhead |
| `frontend/lib/api.js` | all calls to the API (upload with progress) |
| `backend/tests/` | unit and API tests, and the synthetic squat generator |
| `scripts/download_model.py` | downloads the pose model |

## Known limitations

- Side view only; knee cave-in (valgus) needs a front view and isn't checked.
- Thresholds are starting values and still need calibrating on real labeled clips.
- Accuracy on real videos has not been measured yet.
