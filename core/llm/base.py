"""Abstract context classifier interface and shared prompt template."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


CONTEXT_CATEGORIES = ("sexual_situation", "crude_innuendo", "disturbing_content")


@dataclass
class TextWindow:
    """A chunk of dialogue spanning a few seconds, ready for the LLM."""

    start_ms: int
    end_ms: int
    # List of (segment_start_ms, segment_end_ms, text) so the LLM can return
    # ranges aligned to the underlying segments instead of guessing offsets.
    lines: list[tuple[int, int, str]] = field(default_factory=list)

    def to_prompt_lines(self) -> str:
        return "\n".join(
            f"[{s}-{e}] {t}" for (s, e, t) in self.lines if t.strip()
        )


@dataclass
class ContextFlag:
    start_ms: int
    end_ms: int
    category: str        # one of CONTEXT_CATEGORIES
    confidence: float    # 0..1
    reason: str = ""
    quoted_text: str = ""


SYSTEM_PROMPT = """You are a strict content classifier for a family-safe \
video filter. Given a transcript window, identify time ranges in which the \
spoken dialogue describes, depicts, or strongly implies content in any of \
these categories:

- sexual_situation: dialogue describing or implying sex acts, foreplay, \
post-coital references, prostitution, etc., regardless of the words used.
- crude_innuendo: jokes, double entendres, or vulgar humor with a sexual \
or scatological subtext that wouldn't be caught by a profanity wordlist.
- disturbing_content: graphic descriptions of violence, torture, abuse, or \
self-harm.

Be conservative: only flag content where context makes the meaning clear. \
DO NOT flag clinical, educational, or news-style discussion. DO NOT flag \
single profanities (a separate filter handles those).

Return ONLY a JSON array (no prose, no markdown fences) with this schema:
[
  {
    "start_ms": <int>,
    "end_ms": <int>,
    "category": "sexual_situation" | "crude_innuendo" | "disturbing_content",
    "confidence": <number 0..1>,
    "reason": "<one short sentence>",
    "quoted_text": "<the relevant portion of dialogue>"
  }
]

The start_ms/end_ms MUST fall within one of the [start-end] ranges shown in \
the input. If nothing qualifies, return []."""


def build_user_prompt(window: TextWindow) -> str:
    return (
        "Window timestamps are in milliseconds. Transcript lines are formatted "
        "as `[start_ms-end_ms] text`.\n\n"
        f"{window.to_prompt_lines()}\n\n"
        "Return your JSON array now."
    )


_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def parse_response(text: str, window: TextWindow) -> list[ContextFlag]:
    """Best-effort JSON extraction. LLMs often wrap output in markdown."""
    if not text:
        return []
    candidate = text.strip()
    # Strip common ```json fences.
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)
    # Pull the first JSON array out if extra prose snuck in.
    if not candidate.startswith("["):
        m = _JSON_ARRAY_RE.search(candidate)
        if not m:
            return []
        candidate = m.group(0)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []

    out: list[ContextFlag] = []
    win_lo, win_hi = window.start_ms, window.end_ms
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            s = int(item.get("start_ms", 0))
            e = int(item.get("end_ms", 0))
        except (TypeError, ValueError):
            continue
        if e <= s:
            continue
        # Clamp to window bounds.
        s = max(win_lo, s)
        e = min(win_hi, e)
        if e <= s:
            continue
        cat = str(item.get("category", "")).strip()
        if cat not in CONTEXT_CATEGORIES:
            continue
        try:
            conf = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        conf = max(0.0, min(1.0, conf))
        out.append(ContextFlag(
            start_ms=s,
            end_ms=e,
            category=cat,
            confidence=conf,
            reason=str(item.get("reason", ""))[:200],
            quoted_text=str(item.get("quoted_text", ""))[:240],
        ))
    return out


class ContextClassifier(ABC):
    """Abstract base for LLM-backed classifiers."""

    name: str = "abstract"

    @abstractmethod
    def is_available(self) -> bool:
        """Quick check: SDK installed and credentials/server reachable."""

    @abstractmethod
    def classify_window(self, window: TextWindow) -> list[ContextFlag]:
        """Send one window to the LLM. Return flags or [] on any failure."""

    def close(self) -> None:
        """Optional cleanup. Default no-op."""
