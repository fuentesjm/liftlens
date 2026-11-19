"""Server settings, read from environment variables (or a local .env file).

Nothing secret lives in the code. Copy .env.example to .env to change these.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from backend.analysis.pose import DEFAULT_MODEL_PATH

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")  # no-op if the file doesn't exist


@dataclass(frozen=True)
class Settings:
    model_path: Path = DEFAULT_MODEL_PATH
    data_dir: Path = REPO_ROOT / "data"          # saved session reports go here
    max_upload_mb: float = 200.0
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000"])

    @classmethod
    def from_env(cls) -> "Settings":
        default = cls()
        origins = os.getenv("LIFTLENS_CORS_ORIGINS")
        return cls(
            model_path=Path(os.getenv("LIFTLENS_MODEL_PATH", default.model_path)),
            data_dir=Path(os.getenv("LIFTLENS_DATA_DIR", default.data_dir)),
            max_upload_mb=float(os.getenv("LIFTLENS_MAX_UPLOAD_MB", default.max_upload_mb)),
            cors_origins=[o.strip() for o in origins.split(",") if o.strip()] if origins
            else default.cors_origins,
        )
