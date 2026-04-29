"""Google Gemini backend (free tier — gemini-2.0-flash).

Free-tier quota at the time of writing: 15 RPM, 1M TPM, 1500 RPD. We respect
that with a token-bucket rate limiter so longer movies still finish without
hitting 429s.
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


DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_RPM = 14  # one under the free quota for headroom


class _RateLimiter:
    """Sliding-window RPM limiter shared across calls."""

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


class GeminiClassifier(ContextClassifier):
    name = "gemini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        rpm: int = DEFAULT_RPM,
    ) -> None:
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "google-generativeai is not installed. Install with: "
                "pip install google-generativeai"
            ) from e
        self._genai = genai
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get(
            "GOOGLE_API_KEY"
        )
        if not key:
            raise RuntimeError("Gemini API key not provided.")
        self._genai.configure(api_key=key)
        self.model_name = model or DEFAULT_MODEL
        self._model = self._genai.GenerativeModel(
            self.model_name,
            system_instruction=SYSTEM_PROMPT,
        )
        self._limiter = _RateLimiter(rpm=rpm)

    # --- ContextClassifier ---

    def is_available(self) -> bool:
        return self._model is not None

    def classify_window(self, window: TextWindow) -> list[ContextFlag]:
        self._limiter.acquire()
        try:
            resp = self._model.generate_content(
                build_user_prompt(window),
                generation_config={
                    "temperature": 0.1,
                    "response_mime_type": "application/json",
                },
            )
        except Exception:
            return []
        text = getattr(resp, "text", None)
        if not text:
            try:
                # SDK sometimes hides text behind candidates[].content.parts[].text
                parts = resp.candidates[0].content.parts  # type: ignore
                text = "".join(getattr(p, "text", "") for p in parts)
            except Exception:
                text = ""
        return parse_response(text or "", window)
