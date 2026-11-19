"""LiftLens HTTP API.

Run locally:
    uvicorn backend.api.main:app --reload
Then open http://127.0.0.1:8000/docs to try the endpoints in the browser.

Endpoints
    GET  /health                 server is up; is the pose model downloaded?
    POST /analyze                upload a video -> per-rep form report (saved as a session)
    GET  /sessions               list saved sessions (newest first)
    GET  /sessions/{session_id}  one saved session with its full report
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.analysis.analyze import NoPersonDetected, analyze_sequence
from backend.analysis.pose import extract_pose

from .settings import Settings
from .storage import SessionStore

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".webm"}
SUPPORTED_EXERCISES = {"squat"}  # push-ups are planned
CHUNK = 1024 * 1024  # copy uploads 1 MB at a time


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = SessionStore(settings.data_dir)

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
        return {"status": "ok", "model_ready": settings.model_path.exists()}

    # A plain `def` (not `async def`) so FastAPI runs it in a worker thread:
    # pose extraction takes seconds and would otherwise block the server.
    @app.post("/analyze")
    def analyze(file: UploadFile = File(...), exercise: str = Form("squat")) -> dict:
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
        return store.save(report)

    @app.get("/sessions")
    def list_sessions() -> list[dict]:
        return store.list()

    @app.get("/sessions/{session_id}")
    def get_session(session_id: str) -> dict:
        session = store.get(session_id)
        if session is None:
            raise HTTPException(404, "Session not found.")
        return session

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
