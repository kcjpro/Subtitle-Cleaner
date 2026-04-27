"""Parse subtitle files into TextSegments.

Supports SRT and WebVTT. For SRT we use pysrt if available; otherwise we
fall back to a small built-in parser.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from .filter_engine import TextSegment

_SUPPORTED_EXTS = {".srt", ".vtt"}


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in _SUPPORTED_EXTS


def parse_subtitle_file(path: Path) -> List[TextSegment]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".srt":
        return _parse_srt(text)
    if suffix == ".vtt":
        return _parse_vtt(text)
    return []


def find_sidecar_subtitle(video_path: Path) -> Path | None:
    """Look for `<video>.srt` or `<video>.vtt` next to the video."""
    base = video_path.with_suffix("")
    for ext in (".srt", ".vtt"):
        candidate = Path(str(base) + ext)
        if candidate.exists():
            return candidate
    return None


# ---------- SRT ----------

_SRT_TIME = re.compile(
    r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)"
)


def _parse_srt(text: str) -> List[TextSegment]:
    segments: list[TextSegment] = []
    blocks = re.split(r"\r?\n\r?\n+", text.strip())
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        # Find the timestamp line (often line 1 after the index).
        time_line_idx = None
        for i, ln in enumerate(lines):
            if _SRT_TIME.search(ln):
                time_line_idx = i
                break
        if time_line_idx is None:
            continue
        m = _SRT_TIME.search(lines[time_line_idx])
        if not m:
            continue
        start_ms = _to_ms(*map(int, m.group(1, 2, 3, 4)))
        end_ms = _to_ms(*map(int, m.group(5, 6, 7, 8)))
        cue_text = " ".join(lines[time_line_idx + 1 :])
        cue_text = _strip_tags(cue_text)
        if cue_text:
            segments.append(
                TextSegment(start_ms=start_ms, end_ms=end_ms,
                            text=cue_text, source="subtitle")
            )
    return segments


# ---------- WebVTT ----------

_VTT_TIME = re.compile(
    r"(\d+):(\d+):(\d+)\.(\d+)\s*-->\s*(\d+):(\d+):(\d+)\.(\d+)"
)
_VTT_TIME_SHORT = re.compile(
    r"(\d+):(\d+)\.(\d+)\s*-->\s*(\d+):(\d+)\.(\d+)"
)


def _parse_vtt(text: str) -> List[TextSegment]:
    segments: list[TextSegment] = []
    # Strip BOM and the "WEBVTT" header line.
    text = text.lstrip("﻿")
    if text.startswith("WEBVTT"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    blocks = re.split(r"\r?\n\r?\n+", text.strip())
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        time_line_idx = None
        m = None
        for i, ln in enumerate(lines):
            m = _VTT_TIME.search(ln) or _VTT_TIME_SHORT.search(ln)
            if m:
                time_line_idx = i
                break
        if time_line_idx is None or m is None:
            continue
        if m.re is _VTT_TIME:
            start_ms = _to_ms(*map(int, m.group(1, 2, 3, 4)))
            end_ms = _to_ms(*map(int, m.group(5, 6, 7, 8)))
        else:
            start_ms = _to_ms(0, *map(int, m.group(1, 2, 3)))
            end_ms = _to_ms(0, *map(int, m.group(4, 5, 6)))
        cue_text = " ".join(lines[time_line_idx + 1 :])
        cue_text = _strip_tags(cue_text)
        if cue_text:
            segments.append(
                TextSegment(start_ms=start_ms, end_ms=end_ms,
                            text=cue_text, source="subtitle")
            )
    return segments


# ---------- helpers ----------

def _to_ms(h: int, m: int, s: int, frac: int) -> int:
    # `frac` is interpreted as milliseconds (3 digits). If 2 digits given, scale.
    if frac < 10:
        frac *= 100
    elif frac < 100:
        frac *= 10
    return ((h * 3600) + (m * 60) + s) * 1000 + frac


_TAG_RE = re.compile(r"<[^>]+>")
_BRACE_RE = re.compile(r"\{[^}]+\}")


def _strip_tags(text: str) -> str:
    text = _TAG_RE.sub("", text)
    text = _BRACE_RE.sub("", text)
    return text.strip()
