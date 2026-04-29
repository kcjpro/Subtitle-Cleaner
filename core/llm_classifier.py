"""Orchestrate context classification across a full transcript.

Given a list of TextSegments and a ContextClassifier, slide a window
across the transcript, dispatch each window to the LLM, and merge the
returned ContextFlags into Flag objects ready for the FilterProfile.
"""

from __future__ import annotations

from typing import Callable, Optional

from .filter_engine import DEFAULT_ACTIONS, Flag, TextSegment
from .llm import ContextClassifier, ContextFlag, TextWindow

ProgressCb = Callable[[float], None]

# Defaults: 30s windows with 5s overlap. Long enough to give the LLM context,
# short enough to stay within free-tier token limits.
DEFAULT_WINDOW_MS = 30_000
DEFAULT_OVERLAP_MS = 5_000

# We discard low-confidence flags entirely so the user isn't drowned in noise.
DEFAULT_MIN_CONFIDENCE = 0.55


def make_windows(
    segments: list[TextSegment],
    window_ms: int = DEFAULT_WINDOW_MS,
    overlap_ms: int = DEFAULT_OVERLAP_MS,
) -> list[TextWindow]:
    if not segments:
        return []
    end_of_video = max(s.end_ms for s in segments)
    step = max(1000, window_ms - overlap_ms)
    windows: list[TextWindow] = []
    cursor = max(0, segments[0].start_ms - 1000)
    while cursor < end_of_video:
        win_start = cursor
        win_end = cursor + window_ms
        lines = [
            (s.start_ms, s.end_ms, s.text)
            for s in segments
            if s.text and s.end_ms > win_start and s.start_ms < win_end
        ]
        if lines:
            windows.append(TextWindow(
                start_ms=win_start, end_ms=win_end, lines=lines,
            ))
        cursor += step
    return windows


def classify_transcript(
    segments: list[TextSegment],
    classifier: ContextClassifier,
    *,
    progress_cb: Optional[ProgressCb] = None,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> list[Flag]:
    """Run the classifier over the full transcript, return Flag list."""
    windows = make_windows(segments)
    if not windows:
        return []

    raw_flags: list[ContextFlag] = []
    for i, w in enumerate(windows):
        try:
            raw_flags.extend(classifier.classify_window(w))
        except Exception:
            # One bad window should not fail the whole scan.
            pass
        if progress_cb is not None:
            try:
                progress_cb((i + 1) / len(windows))
            except Exception:
                pass

    # Merge overlapping flags from the sliding window before threshold filter.
    merged = _merge_overlaps(raw_flags)
    flags: list[Flag] = []
    for cf in merged:
        if cf.confidence < min_confidence:
            continue
        action = DEFAULT_ACTIONS.get(cf.category, "skip")
        flags.append(Flag(
            start_ms=cf.start_ms,
            end_ms=cf.end_ms,
            word=cf.quoted_text or cf.category,
            category=cf.category,
            context=cf.reason,
            source="llm_context",
            action=action,
            enabled=True,
            flag_type="audio",
            confidence=cf.confidence,
            reason=cf.reason,
        ))
    return flags


def _merge_overlaps(flags: list[ContextFlag]) -> list[ContextFlag]:
    """Coalesce overlapping flags of the same category (max conf wins)."""
    if not flags:
        return []
    flags = sorted(flags, key=lambda f: (f.category, f.start_ms))
    out: list[ContextFlag] = []
    for f in flags:
        if (
            out
            and out[-1].category == f.category
            and f.start_ms <= out[-1].end_ms + 1000
        ):
            prev = out[-1]
            prev.end_ms = max(prev.end_ms, f.end_ms)
            if f.confidence > prev.confidence:
                prev.confidence = f.confidence
                prev.reason = f.reason or prev.reason
                prev.quoted_text = f.quoted_text or prev.quoted_text
            continue
        out.append(f)
    return out
