"""Groq backend (free tier — Llama 3.3 70B versatile).

Groq's free tier is generous (30 RPM, 14,400 RPD on llama-3.3-70b at the
time of writing) and ridiculously fast. We rate-limit to 28 RPM for safety.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from typing import Optional

from .base import (
    ContextClassifier, ContextFlag, SYSTEM_PROMPT, TextWindow,
    build_user_prompt, parse_response,
)


DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_RPM = 28


class _RateLimiter:
    def __init__(self, rpm: int) -> None:
        self.rpm = max(1, rpm)
        self.times: deque[float] = deque()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                while self.times and now - self.times[0] > 60:
                    self.times.popleft()
                if len(self.times) < self.rpm:
                    self.times.append(now)
                    return
                wait = 60 - (now - self.times[0]) + 0.05
            time.sleep(max(0.05, wait))


class GroqClassifier(ContextClassifier):
    name = "groq"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        rpm: int = DEFAULT_RPM,
    ) -> None:
        try:
            from groq import Groq  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "groq SDK is not installed. Install with: pip install groq"
            ) from e
        key = api_key or os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("Groq API key not provided.")
        self._client = Groq(api_key=key)
        self.model_name = model or DEFAULT_MODEL
        self._limiter = _RateLimiter(rpm=rpm)

    def is_available(self) -> bool:
        return self._client is not None

    def classify_window(self, window: TextWindow) -> list[ContextFlag]:
        self._limiter.acquire()
        try:
            resp = self._client.chat.completions.create(
                model=self.model_name,
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT + (
                        "\n\nReturn the JSON array under the key `flags`, e.g. "
                        "{\"flags\": [...]}, since this API requires an object."
                    )},
                    {"role": "user", "content": build_user_prompt(window)},
                ],
            )
        except Exception:
            return []
        try:
            content = resp.choices[0].message.content or ""
        except (AttributeError, IndexError):
            return []
        # Groq's json_object mode wraps the array under our requested key.
        unwrapped = _unwrap_flags_object(content)
        return parse_response(unwrapped, window)


def _unwrap_flags_object(text: str) -> str:
    import json as _json
    s = text.strip()
    if not s.startswith("{"):
        return text
    try:
        obj = _json.loads(s)
    except _json.JSONDecodeError:
        return text
    if isinstance(obj, dict):
        for key in ("flags", "results", "items", "data"):
            if isinstance(obj.get(key), list):
                return _json.dumps(obj[key])
    return text
