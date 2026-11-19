"""LLM client: the one place that talks to an external LLM API.

The rest of the app only calls `generate_json(system, prompt, schema)` and gets
back a validated Pydantic object, so the provider can be swapped by changing
LLM_PROVIDER in .env without touching the feature code.

Credentials: the API key is read from the GEMINI_API_KEY environment variable
(or the gitignored .env file). It is never written to logs, reports, or errors.
If no key is set, get_llm_client() returns None and every feature falls back
to rule-based template text, so the app still runs end to end without a key.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

T = TypeVar("T", bound=BaseModel)

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"


class LLMError(Exception):
    """The LLM call failed or returned something unusable (callers fall back)."""


class LLMClient(Protocol):
    name: str  # e.g. "gemini:gemini-3.8-flash", shown in responses

    def generate_json(self, system: str, prompt: str, schema: type[T]) -> T: ...


class GeminiClient:
    """Google Gemini via the official google-genai SDK, in JSON mode.

    `response_json_schema` makes the model answer in the shape of `schema`;
    the reply is still validated with Pydantic because the API can return
    truncated or off-schema output.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL,
                 timeout_seconds: float = 30.0, temperature: float = 0.4):
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )
        self.model = model
        self.temperature = temperature
        self.name = f"gemini:{model}"

    def generate_json(self, system: str, prompt: str, schema: type[T]) -> T:
        config = self._types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=schema.model_json_schema(),
            temperature=self.temperature,
        )
        try:
            response = self._client.models.generate_content(
                model=self.model, contents=prompt, config=config)
        except Exception as e:  # network, quota (429), bad key, timeout...
            # Only the error type and status are kept, never request details.
            code = getattr(e, "code", None) or getattr(e, "status_code", None)
            raise LLMError(f"{type(e).__name__}{f' ({code})' if code else ''}") from None
        text = getattr(response, "text", None)
        if not text:
            raise LLMError("empty response")
        try:
            return schema.model_validate_json(text)
        except ValidationError as e:
            raise LLMError(f"response did not match the schema ({e.error_count()} errors)") from None


def get_llm_client() -> LLMClient | None:
    """Build the configured client, or None (template fallback) if not configured."""
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if provider in ("", "none", "off"):
        return None
    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key or key == "your-key-here":
            return None
        return GeminiClient(
            api_key=key,
            model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
        )
    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Supported: gemini, none.")
