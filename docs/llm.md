# LLM features: prompts, API workflow, and limitations

LiftLens uses an external LLM (Google Gemini, free tier, default model `gemini-3.5-flash-lite`) for two jobs: writing coaching feedback and generating weekly plans. Everything that decides something (rep counts, pass/fail, next-session load, safety limits) is done by our own code. The LLM only writes text or proposes a plan that our code then checks.

## Setup and credentials

1. Get a free key from Google AI Studio (aistudio.google.com → Get API key).
2. Copy `.env.example` to `.env` and set `GEMINI_API_KEY=...`. `.env` is gitignored and must never be committed.
3. Optional settings in `.env`: `LLM_PROVIDER` (`gemini` or `none`), `GEMINI_MODEL`, `GEMINI_THINKING_LEVEL` (default `low`), `LLM_TIMEOUT_SECONDS` (default 20).

The key is read only from the environment (`backend/llm/client.py`). It is never logged, stored, or included in error messages. With no key, or with `LLM_PROVIDER=none`, the app uses rule-based template text instead, so the whole app still runs end to end.

`GET /health` shows which LLM is active (`"llm": "gemini:gemini-3.5-flash-lite"` or `null`).

## API workflow

```
POST /analyze ─► pose + rules (our code) ─► report ─► adaptation engine (our code) ─► decision
                                                │                                     │
                                                └──────── numbers only ───────────────┤
                                                                                      ▼
                                                      Gemini (JSON mode, Feedback schema)
                                                                                      │
                                                    validate with Pydantic ◄──────────┘
                                                      ok ─► feedback (source: "llm")
                                                      fail ─► template text (source: "template")

POST /plan ─► profile ─► Gemini (JSON mode, WeeklyPlan schema) ─► Pydantic ─► check_plan (our safety bounds)
                                  ▲                                               │
                                  └──── retry once, listing every violation ◄─────┤ violations
                                                                                  │ still failing / error
                                                                                  ▼
                                                                    template plan (always passes)
```

**Model choice (measured with `scripts/check_llm.py`):** `gemini-3.8-flash` on the free tier answered the plan request once in 7.1 s but otherwise ran into the server deadline (HTTP 504 after about 58 s) on both requests. `gemini-3.5-flash-lite` answered feedback in 1.3 s and the plan in 1.7 s, both valid on the first attempt, so it is the default. Thinking is set to `low` because these short tasks don't need deep reasoning. Requests time out after 20 s and temporary errors (429, 500, 503) are retried once, so a slow LLM falls back to template text instead of stalling an upload.

Every call uses Gemini's JSON mode (`response_mime_type="application/json"` plus `response_json_schema` built from our Pydantic models). Replies are still validated in our code, because JSON mode can return truncated or off-schema output.

## 1. Feedback writer (`backend/llm/feedback.py`)

**Input sent to the LLM:** only numbers and error codes, built by `feedback_input()`: rep count, reps passed, form score, per-rep thigh angle above parallel / torso lean / error codes, the pass limits, warnings, and the next-session decision with its reason. No video, no video file name, no user identity. A test checks this (`test_feedback_prompt_has_numbers_only_no_video_name`).

**System prompt:**

```
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
```

**User prompt:** `Write feedback for this set.` followed by the input JSON.

**Output schema (`Feedback`):**

```json
{"summary": "1-2 sentences",
  "tips": ["up to 3 short tips"],
  "next_session": "1-2 sentences explaining the decision"}
```

Length limits are enforced by our code after the reply (`check_feedback`: extra tips dropped, any field over 400 characters → template fallback), not in the schema sent to Gemini. Keeping the schema free of length constraints also keeps constrained decoding simple.

**Returned by the API** (in `POST /analyze` under `feedback`): the fields above plus `source` (`llm` or `template`), `model`, and `fallback_reason` when the template was used. The LLM is skipped when no reps were detected.

**Example (template mode, no key):**

```json
{"summary": "2 of 3 reps passed the depth and torso checks.",
  "tips": ["Rep 2: Squat deeper: lower until your thighs are about parallel to the floor."],
  "next_session": "67% of reps had good form. Keep the same load and reps and work on the form cue before progressing.",
  "source": "template", "model": null, "fallback_reason": "no LLM configured"}
```

## 2. Plan generator (`backend/llm/plan.py`)

**Input:** a profile with only structured fields (no free text, no health information): `goal` (strength / muscle / general_fitness), `experience` (beginner / intermediate), `days_per_week` (2-5), `equipment` (bodyweight / dumbbells / full_gym), `session_minutes` (20-90).

**System prompt** (bounds filled in from `BOUNDS`; shown for a beginner):

```
You are a certified strength coach designing a safe weekly plan for a
beginner-to-intermediate lifter. Reply with JSON only, matching the schema.

Rules:
- Exactly the requested number of training days, numbered 1..N.
- Use ONLY exercise names from the allowed list, spelled exactly as given.
- Every day: 3-6 exercises; sets 1-5; reps 5-20;
  rest 30-240 seconds; at most 16 total sets per day.
- Include a squat pattern at least twice a week (the app can video-check squats).
- Balance lower body, upper-body push, and upper-body pull across the week.
- Fit each session in the given minutes (roughly 2-3 minutes per set incl. rest).
- Strength goal: fewer reps (5-8), longer rest. Muscle: 8-12 reps.
  General fitness: 10-15 reps, shorter rest.
- The rationale explains the choices in plain language. No medical advice.
```

**User prompt** (example for muscle / beginner / 3 days / dumbbells):

```
Create a weekly plan for this profile:
{
  "goal": "muscle",
  "experience": "beginner",
  "days_per_week": 3,
  "equipment": "dumbbells",
  "session_minutes": 45
}

Allowed exercises:
- Bodyweight squat
- Push-up
- Incline push-up
- Reverse lunge
- Glute bridge
- Split squat
- Calf raise
- Bird dog
- Goblet squat
- Dumbbell row
- Dumbbell bench press
- Dumbbell Romanian deadlift
- Dumbbell shoulder press
```

**Output schema (`WeeklyPlan`):** `days[]` with `day`, `focus`, and `exercises[]` (`name`, `sets`, `reps`, `rest_seconds`), plus a `rationale`.

**Safety checks in our code (`check_plan`):** exact number of days, numbered 1..N; 3-6 exercises per day; sets 1-5; reps 5-20; rest 30-240 s; at most 16 total sets per day for beginners (22 intermediate); only exercises from the fixed library for the user's equipment; a squat pattern on at least 2 days. If any check fails, the generator retries once with the list of violations added to the prompt, then falls back to the template plan.

**Our code adds** `form_check: true/false` to each exercise (true for squat variants the video analyzer supports). The LLM does not decide this.

**Returned by the API** (`POST /plan`, saved and returned by `GET /plan`): `profile`, `plan`, `source`, `model`, `attempts` (LLM) or `fallback_reason` (template).

## Limitations

- **Free-tier data use:** on Gemini's free tier, Google may use prompts and responses to improve its products. We only send numbers, error codes, and the structured profile, never video or personal details. A paid key avoids this.
- **Rate limits and outages:** free-tier quotas are small. A rate-limit error (HTTP 429), timeout, or bad key makes the app fall back to template text, with the reason in `fallback_reason`.
- **Wording can still be wrong:** the prompt tells the model to use only the given facts, and the decision itself comes from our code. But the free-text wording is not checked word by word: it could misstate a number or sound overconfident. The structured report is the source of truth.
- **Observed in testing:** with Flash-Lite, the feedback was accurate (2 of 3 reps passed, deepen the shallow rep) but added one generic tip ("keep your torso stable") that wasn't tied to an error. A plan rationale said "squat pattern twice a week" when the plan had squats on all 3 days. The plan itself passed every check; only the free-text rationale is unchecked.
- **Plans are not personalized coaching:** the library and bounds keep plans safe and generic. They don't account for injuries or medical conditions, and the app is not medical advice.
- **Latency:** `/analyze` waits for the feedback call (up to `LLM_TIMEOUT_SECONDS`, default 20 s; about 1-2 s with Flash-Lite in our tests) before responding.
- **Non-determinism:** the same input can give different wording or plans. Tests use a fake client, so they are deterministic and never call the API.

## What the team built vs. what the LLM does

| Our code | The LLM |
|---|---|
| Pose-based rep counting and form rules, form score, cues | Rewords the results as coaching text |
| Adaptation engine (next-session load and reps) | Explains the decision; cannot change it |
| JSON schemas, Pydantic validation, safety bounds, exercise library | Proposes a plan inside those limits |
| Retry with listed violations, template fallbacks, error handling | — |
| Deciding which exercises are video form-checkable | — |
| Prompt design and the data-minimizing input (numbers only) | — |
| Provider wrapper (swap providers via `.env`), key handling | — |
