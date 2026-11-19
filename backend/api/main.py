"""LiftLens HTTP API.

Run locally:
    uvicorn backend.api.main:app --reload
Then open http://127.0.0.1:8000/docs to try the endpoints in the browser.

Endpoints
    GET  /health                 server is up; is the pose model downloaded?
    POST /analyze                upload a video (+ load, target reps, RPE) -> per-rep form
                                 report and next-session decision (saved as a session)
    GET  /sessions               list saved sessions (newest first)
    GET  /sessions/{session_id}  one saved session with its full report
    GET  /next-workout           next-session load and reps from the saved history
    POST /plan                   profile -> weekly plan (LLM, safety-checked; template fallback)
    GET  /plan                   the saved weekly plan
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.analysis.analyze import NoPersonDetected, analyze_sequence
from backend.analysis.pose import extract_pose
from backend.llm.client import LLMClient, get_llm_client
from backend.llm.feedback import write_feedback
from backend.llm.plan import Profile, generate_plan
from backend.planning.adaptation import next_workout

from .settings import Settings
from .storage import SessionStore

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".webm"}
SUPPORTED_EXERCISES = {"squat"}  # push-ups are planned
CHUNK = 1024 * 1024  # copy uploads 1 MB at a time


_FROM_ENV = object()


def create_app(settings: Settings | None = None, llm: LLMClient | None | object = _FROM_ENV) -> FastAPI:
    """`llm` defaults to the client configured in .env (None = template text only)."""
    settings = settings or Settings.from_env()
    store = SessionStore(settings.data_dir)
    llm = get_llm_client() if llm is _FROM_ENV else llm

    app = FastAPI(title="LiftLens API", version="0.1.0")
    # Lets the Next.js frontend (another port) call this API from the browser.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model_ready": settings.model_path.exists(),
                "llm": llm.name if llm else None}

    # A plain `def` (not `async def`) so FastAPI runs it in a worker thread:
    # pose extraction takes seconds and would otherwise block the server.
    @app.post("/analyze")
    def analyze(
        file: UploadFile = File(...),
        exercise: str = Form("squat"),
        load: float = Form(0.0, ge=0, le=2000, description="weight used; 0 = bodyweight"),
        unit: Literal["lb", "kg"] = Form("lb"),
        target_reps: Optional[int] = Form(None, ge=1, le=100, description="reps you planned to do"),
        rpe: Optional[int] = Form(None, ge=1, le=10, description="how hard it felt, 1-10"),
    ) -> dict:
        if exercise not in SUPPORTED_EXERCISES:
            raise HTTPException(400, f"Unsupported exercise '{exercise}'. Supported: squat.")
        name = Path(file.filename or "").name  # drop any folder part of the name
        suffix = Path(name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"Unsupported file type '{suffix or '?'}'. "
                                     f"Use one of: {', '.join(sorted(ALLOWED_EXTENSIONS))}.")
        if not settings.model_path.exists():
            raise HTTPException(503, "Pose model not downloaded. Run: python scripts/download_model.py")

        # Save the upload to a temporary file (OpenCV needs a path), then always delete it.
        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / f"upload{suffix}"
            _save_upload(file, video_path, max_bytes=int(settings.max_upload_mb * 1024 * 1024))
            try:
                seq = extract_pose(video_path, settings.model_path)
            except ValueError:
                raise HTTPException(400, "Could not read the video file.")

        if not seq.frames:
            raise HTTPException(400, "The video has no frames.")
        try:
            report = analyze_sequence(seq, name)
        except NoPersonDetected:
            raise HTTPException(422, "No person was detected in the video. Record from the side "
                                     "with your whole body in frame.")
        workout = {"load": load, "unit": unit, "target_reps": target_reps, "rpe": rpe}
        session = store.save(report, workout)
        decision = next_workout(store.history(exercise))
        return {**session, "next_workout": decision,
                "feedback": write_feedback(report, decision, llm)}

    @app.get("/sessions")
    def list_sessions() -> list[dict]:
        return store.list()

    @app.get("/sessions/{session_id}")
    def get_session(session_id: str) -> dict:
        session = store.get(session_id)
        if session is None:
            raise HTTPException(404, "Session not found.")
        return session

    @app.get("/next-workout")
    def get_next_workout(exercise: str = Query("squat")) -> dict:
        history = store.history(exercise)
        if not history:
            raise HTTPException(404, f"No saved {exercise} sessions yet. Upload a set first.")
        return next_workout(history)

    @app.post("/plan")
    def create_plan(profile: Profile) -> dict:
        return store.save_plan(generate_plan(profile, llm))

    @app.get("/plan")
    def get_plan() -> dict:
        plan = store.get_plan()
        if plan is None:
            raise HTTPException(404, "No plan yet. Create one with POST /plan.")
        return plan

    return app


def _save_upload(upload: UploadFile, dest: Path, max_bytes: int) -> None:
    """Copy the upload to disk in chunks, stopping if it's over the size limit."""
    written = 0
    with dest.open("wb") as out:
        while chunk := upload.file.read(CHUNK):
            written += len(chunk)
            if written > max_bytes:
                raise HTTPException(413, f"Video is larger than {max_bytes // (1024 * 1024)} MB.")
            out.write(chunk)
    if written == 0:
        raise HTTPException(400, "The uploaded file is empty.")


app = create_app()
