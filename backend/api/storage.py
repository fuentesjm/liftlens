"""Saves each analysis as a JSON file so later steps (progress tracking, the
adaptation engine) can read a user's past sessions.

One file per session: data/sessions/<session_id>.json. A JSON folder keeps the
MVP simple to run; it can be swapped for a database later without changing
the API.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")  # uuid4 hex; also blocks path tricks like "../"


class SessionStore:
    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir) / "sessions"
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, report: dict, workout: dict | None = None) -> dict:
        session = {
            "session_id": uuid.uuid4().hex,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            "workout": workout or {},
            "report": report,
        }
        self._path(session["session_id"]).write_text(json.dumps(session, indent=2))
        return session

    def get(self, session_id: str) -> dict | None:
        if not _ID_PATTERN.match(session_id):
            return None
        path = self._path(session_id)
        return json.loads(path.read_text()) if path.exists() else None

    def history(self, exercise: str | None = None) -> list[dict]:
        """Full sessions, newest first, optionally for one exercise."""
        sessions = [json.loads(p.read_text()) for p in self.dir.glob("*.json")]
        if exercise:
            sessions = [s for s in sessions if s["report"]["exercise"] == exercise]
        return sorted(sessions, key=lambda s: s["created_at"], reverse=True)

    def list(self) -> list[dict]:
        """Short summaries, newest first."""
        return [
            {
                "session_id": s["session_id"],
                "created_at": s["created_at"],
                "exercise": s["report"]["exercise"],
                "video": s["report"]["video"],
                "rep_count": s["report"]["rep_count"],
                "form_score": s["report"]["form_score"],
                "workout": s.get("workout", {}),
            }
            for s in self.history()
        ]

    # The current weekly plan (one per install for the MVP; no user accounts yet).
    def save_plan(self, plan: dict) -> dict:
        plan = {**plan, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        (self.dir.parent / "plan.json").write_text(json.dumps(plan, indent=2))
        return plan

    def get_plan(self) -> dict | None:
        path = self.dir.parent / "plan.json"
        return json.loads(path.read_text()) if path.exists() else None

    def _path(self, session_id: str) -> Path:
        return self.dir / f"{session_id}.json"
