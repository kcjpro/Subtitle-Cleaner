"""Pluggable LLM-based context classifiers for sexual-situation / innuendo /
disturbing-content detection beyond keyword matching."""

from __future__ import annotations

from typing import Optional

from .base import ContextClassifier, ContextFlag, TextWindow


def make_classifier(
    backend: str,
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Optional[ContextClassifier]:
    """Factory: build a ContextClassifier for the named backend.

    Returns None if the backend isn't installed/configured. Never raises.
    """
    backend = (backend or "").lower().strip()
    try:
        if backend == "ollama":
            from .ollama_backend import OllamaClassifier
            return OllamaClassifier(model=model, base_url=base_url)
        if backend == "gemini":
            from .gemini_backend import GeminiClassifier
            return GeminiClassifier(api_key=api_key, model=model)
        if backend == "groq":
            from .groq_backend import GroqClassifier
            return GroqClassifier(api_key=api_key, model=model)
    except Exception:
        return None
    return None


__all__ = [
    "ContextClassifier",
    "ContextFlag",
    "TextWindow",
    "make_classifier",
]
