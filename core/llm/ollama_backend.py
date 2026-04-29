"""Ollama backend — POSTs to a locally-running Ollama server.

No SDK is required; we use the standard library `urllib`. Default endpoint
is http://localhost:11434, default model `llama3.2:3b` which fits in ~3 GB
of VRAM and is fast enough for a movie's worth of windows.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from .base import (
    ContextClassifier, ContextFlag, SYSTEM_PROMPT, TextWindow,
    build_user_prompt, parse_response,
)


DEFAULT_MODEL = "llama3.2:3b"
DEFAULT_BASE_URL = "http://localhost:11434"
TIMEOUT_S = 90


class OllamaClassifier(ContextClassifier):
    name = "ollama"

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.model = model or DEFAULT_MODEL
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")

    # --- ContextClassifier ---

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=4) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def classify_window(self, window: TextWindow) -> list[ContextFlag]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(window)},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError, TimeoutError):
            return []
        try:
            obj = json.loads(body)
        except json.JSONDecodeError:
            return []
        # Ollama wraps the assistant text under message.content. With
        # format="json" the content is itself a JSON string. We pass the raw
        # text through parse_response which handles either a list or an
        # object that contains a list.
        msg = obj.get("message", {}) or {}
        content = msg.get("content", "")
        # Some Ollama models return an object like {"flags": [...]} when
        # given format="json". Try to unwrap that case.
        unwrapped = _maybe_unwrap_object(content)
        return parse_response(unwrapped, window)


def _maybe_unwrap_object(text: str) -> str:
    if not text:
        return text
    stripped = text.strip()
    if not stripped.startswith("{"):
        return text
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        return text
    if isinstance(obj, list):
        return text  # already a list
    if not isinstance(obj, dict):
        return text
    for key in ("flags", "results", "items", "data"):
        if isinstance(obj.get(key), list):
            return json.dumps(obj[key])
    return text
