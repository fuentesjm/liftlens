# LiftLens

AI workout planning with video-based form review. Team: Jose Fuentes, Perry Wang.

A user films a set of squats from the side and uploads it. LiftLens counts the reps, checks each rep's depth and torso lean, writes coaching feedback, and decides the weight and reps for the next session. It also generates a weekly plan from the user's goal and equipment.

## Status

| Component | Status |
|---|---|
| Squat analysis pipeline (pose → angles → reps → form rules → JSON report) | **Done.** Unit-tested on synthetic data; checked on 2 sample clips |
| FastAPI backend (upload, saved sessions, next workout, plan) | **Done.** API-tested |
| Adaptation engine (next-session load and reps) | **Done.** Rule-based; scenario-tested |
| LLM feedback writer and plan generator (Gemini, safety-checked, template fallback) | **Done.** Tested with a fake LLM and live with Gemini; see [`docs/llm.md`](docs/llm.md) |
| Next.js frontend (Today, Record a set, per-rep results with chart and replay, Plan, History) | **Done** |
| Accuracy evaluation on the team's own labeled clips | Planned |
| Skeleton overlay on the replay video | Planned (the results page already replays each rep in sync with the chart) |
| Push-up analysis | Planned |
| User accounts | Planned |

## Setup

Requires Python 3.10+ and Node.js 20+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/download_model.py   # downloads the pose model into models/
cp .env.example .env               # then edit .env (see below)
```

Settings are environment variables listed in `.env.example`. `.env` is gitignored and must never be committed.

**LLM key (optional):** for AI-written feedback and plans, get a free Gemini key at Google AI Studio and set `GEMINI_API_KEY` in `.env`. Without a key, everything still runs and uses template text instead. To check the key, run `python scripts/check_llm.py`; it should end with `LLM OK`. Prompts, inputs and outputs, and limitations are documented in [`docs/llm.md`](docs/llm.md).

## Run the web app

The app needs two terminals: the API server and the frontend.

```bash
# Terminal 1 (project folder, venv active)
uvicorn backend.api.main:app --reload

# Terminal 2
cd frontend
npm install        # first time only
npm run dev
```

Open http://localhost:3000 and follow the full flow:

1. **Plan:** pick a goal, experience, equipment, and days, then **Create plan**.
2. **Record a set:** choose a side-view squat video, enter the weight and target reps (and optionally RPE), then **Analyze set**.
3. **Results:** the verdict, a knee-angle chart with each rep marked passed (green) or failed (red), the depth line, per-rep angles, coach notes, and the next set. Click a rep on the chart or **Replay** to jump the video to it.
4. **Today:** shows the next set, the last set's chart, form over time, and the week's plan. **Record this set** pre-fills the upload form.
5. **History:** every set, newest first.

**Videos to use:** the team's sample clips are in `samples/`. To try your own, film from the side, with the phone at hip height and your whole body in frame.

**Start over:** stop the API server, rename or delete the `data/` folder, and start it again. The app then shows the first-visit page.

If the API runs somewhere other than `http://127.0.0.1:8000`, copy `frontend/.env.local.example` to `frontend/.env.local` and change `NEXT_PUBLIC_API_URL`.

## Reproduce a sample result

No video, pose model, or API key needed:

```bash
python scripts/sample_result.py           # add --json for the full API-style output
```

This builds a synthetic side-view squat set with known knee angles (rep bottoms at 86°, 118°, 89°). It then runs the set through the same analysis, adaptation, and feedback code the app uses. Expected output:

```
Reps detected: 3   passed: 2   form score: 67%
  Rep 1: bottom at 1.67 s, knee 86.6 deg, lean 43.8 deg -> PASS
  Rep 2: bottom at 4.37 s, knee 118.4 deg, lean 37.8 deg -> FAIL shallow_depth
  Rep 3: bottom at 7.07 s, knee 89.5 deg, lean 46.8 deg -> PASS

Next set: HOLD -> 95 lb x 3
  67% of reps had good form. Keep the same load and reps and work on the form cue before progressing.
```

Run the full test suite:

```bash
python -m pytest -q backend/tests
```

All tests run without a video, the pose model, or an API key:

- `test_analysis.py` generates synthetic side-view squats with known knee angles (`backend/tests/synthetic.py`). It checks rep counting, depth and lean detection, jitter rejection, timing, visibility warnings, soft-knee standing, the camera-angle warning, and the chart trace.
- `test_api.py` swaps the pose model for the same generator. It checks uploads, saved sessions, plans, workout fields, and every error response.
- `test_adaptation.py` runs the adaptation rules on fake session histories: progress, hold, reduce, deload, retest, kg vs. lb, bodyweight, and old sessions without workout fields.
- `test_llm.py` checks the LLM features with a fake client: feedback and plan parsing, the numbers-only prompt, length limits, retry on unsafe plans, every fallback, and that the template plan passes the safety checks for all profile combinations. No test calls the real API.

### Accuracy on the team's clips

The team's own side-view clips are in `samples/`, with the true rep count and faulty reps for each clip in `samples/labels.csv`. To compare the analyzer against those labels (needs the pose model):

```bash
python scripts/evaluate.py --out eval_results.json
```

It prints, per clip, the reps found vs. labeled and the predicted vs. labeled faulty reps. It then prints rep-count accuracy, precision/recall/F1 for each fault, and the processing time.

### Analyze a single clip

To analyze one of your own clips from the command line and see the JSON report:

```bash
python -m backend.analysis.analyze path/to/your_squat_side.mp4
python -m backend.analysis.analyze path/to/your_squat_side.mp4 --debug        # knee angle and lean over time
python -m backend.analysis.analyze path/to/your_squat_side.mp4 --out report.json
```

## How it works

```
video ─► MediaPipe Pose Landmarker ─► joint angles ─► smoothing ─► rep segmentation ─► form rules ─► report
         (pretrained model)           (our code from here on)                                          │
                                                                                                       ▼
                      weekly plan ◄─ Gemini + safety checks      adaptation engine (rules) ─► next set
                                                                         │
                                                                         ▼
                                                    Gemini feedback writer (numbers only) ─► coach notes
```

### Video analysis (`backend/analysis/`)

1. **Pose estimation** (`pose.py`): the pretrained MediaPipe Pose Landmarker finds 33 body landmarks per frame. This is the only pretrained vision model.
2. **Joint angles** (`angles.py`): picks the body side facing the camera, then computes the knee angle (hip–knee–ankle) and torso lean (shoulder–hip line vs. vertical) for every frame.
3. **Smoothing** (`smoothing.py`): fills frames where the body wasn't visible (linear interpolation) and smooths with a centered moving average.
4. **Rep segmentation** (`reps.py`): a two-threshold state machine on the knee angle.
   - A rep starts when the angle drops below the *down* threshold and ends when it rises above the *up* threshold, so jitter between them can't count as extra reps.
   - The thresholds adapt to each clip. The person's standing angle is the 95th percentile of their knee angle. *Up* is 10° below that (at most 160°), and *down* is 15° below *up* (at most 140°).
   - This handles people who stand with soft knees, or a camera that isn't perfectly side-on.
5. **Form rules** (`form_rules.py`): a rep fails *depth* if its lowest knee angle is above 100°. It fails *forward lean* if the torso is more than 50° from vertical at the bottom. Thresholds live in `config.py`.
6. **Report** (`report.py`): rep count, per-rep times and angles, errors, form score (fraction of reps passed), coaching cues, warnings, the thresholds actually used, and a 10-per-second knee-angle trace for the chart. It warns when the person seems turned toward the camera, i.e. the two shoulders appear far apart relative to torso length.

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

### LLM features (`backend/llm/`)

- **Feedback writer:** turns the report and the decision into a summary, up to 3 tips, and an explanation of the next set. Only numbers and error codes are sent, never the video or file name.
- **Plan generator:** turns a structured profile into a weekly plan in a fixed JSON schema. Our code checks the plan against safety limits: allowed exercises for the equipment, sets, reps, rest, a daily set cap, and squats at least twice a week. If a check fails, the LLM gets one retry with the problems listed. If it still fails, the app uses a template plan.
- **Fallback:** any LLM failure (no key, timeout, rate limit, invalid reply) falls back to template text, so the app always works.

Full prompts, the API workflow, example inputs and outputs, test results, and the split between our code and the LLM's work are in [`docs/llm.md`](docs/llm.md).

## API reference

Start the server with `uvicorn backend.api.main:app --reload`. To try every endpoint in the browser, open http://127.0.0.1:8000/docs. Or from a terminal:

```bash
curl -F "file=@path/to/your_squat_side.mp4" -F "exercise=squat" \
     -F "load=95" -F "unit=lb" -F "target_reps=10" -F "rpe=7" \
     http://127.0.0.1:8000/analyze
```

| Endpoint | What it does |
|---|---|
| `GET /health` | server is up; `model_ready` = pose model downloaded; `llm` = active LLM (or `null` = template text) |
| `POST /analyze` | form fields `file` (video: mp4, mov, m4v, avi, webm), `exercise` (`squat`), and optional `load` (0 = bodyweight), `unit` (`lb`/`kg`), `target_reps`, `rpe` (1–10). Saves the session and returns `{session_id, created_at, workout, report, next_workout, feedback}` |
| `GET /sessions` | saved sessions, newest first (id, date, rep count, form score, workout) |
| `GET /sessions/{session_id}` | one saved session with its report, decision, and feedback |
| `GET /next-workout?exercise=squat` | the next-session decision from the saved history |
| `POST /plan` | JSON profile `{goal, experience, days_per_week, equipment, session_minutes}` → safety-checked weekly plan (saved) |
| `GET /plan` | the saved weekly plan |

Error codes:

| Code | Meaning |
|---|---|
| `400` | wrong file type, empty or unreadable video, or unsupported exercise |
| `404` | no saved sessions for `/next-workout`, or no plan yet |
| `413` | file over the size limit |
| `422` | no person detected, or an invalid field (e.g. RPE 11) |
| `503` | pose model not downloaded |

**Data and privacy:**
- Uploaded videos are written to a temporary folder only while they're analyzed, then deleted.
- Sessions are saved as JSON in `data/sessions/` and the plan in `data/plan.json`. Both are gitignored.

## Main files

| File | Purpose |
|---|---|
| `backend/analysis/analyze.py` | command-line entry point; runs the whole analysis pipeline |
| `backend/analysis/pose.py` | MediaPipe pose extraction from a video file |
| `backend/analysis/angles.py` | knee angle, torso lean, and camera-angle check per frame |
| `backend/analysis/smoothing.py` | gap filling and smoothing |
| `backend/analysis/reps.py` | adaptive thresholds and rep segmentation |
| `backend/analysis/form_rules.py` | per-rep form checks and cue text |
| `backend/analysis/report.py` | JSON report |
| `backend/analysis/config.py` | all analysis thresholds in one place |
| `backend/planning/adaptation.py` | adaptation engine: next-session load and reps |
| `backend/llm/client.py` | Gemini wrapper (JSON mode, key from env, errors → fallback) |
| `backend/llm/feedback.py` | feedback writer: prompt, schema, length checks, template fallback |
| `backend/llm/plan.py` | plan generator: prompt, schema, safety checks, retry, template plan |
| `backend/api/main.py` | FastAPI app and endpoints |
| `backend/api/storage.py` | saves and loads sessions and the plan (JSON files) |
| `backend/api/settings.py` | server settings from environment variables |
| `backend/tests/` | unit, API, adaptation, and LLM tests, and the synthetic squat generator |
| `frontend/app/` | Next.js pages: Today (`page.jsx`), `record/`, `sessions/[id]/` (results), `plan/`, `history/` |
| `frontend/components/KneeTrace.jsx` | knee-angle chart with rep bands, depth line, and video playhead |
| `frontend/components/MiniTrace.jsx`, `FormHistory.jsx` | home-page chart and form-over-time bars |
| `frontend/lib/api.js` | all calls to the API (upload with progress) |
| `docs/llm.md` | LLM prompts, API workflow, inputs and outputs, limitations, team contribution |
| `scripts/download_model.py` | downloads the pose model |
| `scripts/check_llm.py` | checks that the Gemini key works |
| `scripts/evaluate.py`, `samples/labels.csv` | accuracy evaluation on the team's labeled clips |
| `scripts/sample_result.py` | reproduces a sample result from a synthetic squat set (no video, model, or key) |

## Known limitations

- **Squats only.** Push-up analysis is planned.
- **Side view only.** Knee cave-in (valgus) needs a front view and isn't checked. Filming at an angle makes the measured angles less reliable; the app warns when the person seems turned toward the camera.
- **Not yet calibrated on real data.** Thresholds (100° depth, 50° lean, camera-angle ratio) are starting values. Accuracy on real labeled clips hasn't been measured yet. In the two sample clips we checked, rep counts were correct and the forward-lean mistake was caught. Depth calls near 100° are borderline.
- **No user accounts.** Everyone using one server shares the same history and plan.
- **Replay only right after upload.** The server doesn't keep videos, so replay works only in the browser tab that uploaded the clip. The chart and numbers are always available.
- **LLM limits.** On Gemini's free tier, Google may use prompts to improve its products; we send only numbers and the structured profile. Free-text wording isn't checked word by word and can be slightly off (examples in `docs/llm.md`). Every decision comes from our code, not the LLM.
- **Not medical advice.** Plans and feedback are general guidance for healthy adults.
