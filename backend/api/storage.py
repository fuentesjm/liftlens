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

    def save(self, report: dict) -> dict:
        session = {
            "session_id": uuid.uuid4().hex,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "report": report,
        }
        self._path(session["session_id"]).write_text(json.dumps(session, indent=2))
        return session

    def get(self, session_id: str) -> dict | None:
        if not _ID_PATTERN.match(session_id):
            return None
        path = self._path(session_id)
        return json.loads(path.read_text()) if path.exists() else None

    def list(self) -> list[dict]:
        """Short summaries, newest first."""
        sessions = [json.loads(p.read_text()) for p in self.dir.glob("*.json")]
        sessions.sort(key=lambda s: s["created_at"], reverse=True)
        return [
            {
                "session_id": s["session_id"],
                "created_at": s["created_at"],
                "exercise": s["report"]["exercise"],
                "video": s["report"]["video"],
                "rep_count": s["report"]["rep_count"],
                "form_score": s["report"]["form_score"],
            }
            for s in sessions
        ]

    def _path(self, session_id: str) -> Path:
        return self.dir / f"{session_id}.json"
