"""Word-list matching against transcript text or subtitle cues.

Produces a list of `Flag` records that downstream code (the review UI and
the player) consumes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Optional, Sequence

# Pad each flag by this many milliseconds on each side so cuts aren't audible
# at the edges. Tweak in the UI later if needed.
DEFAULT_PADDING_MS = 250

# Categories shipped by default. Each maps to a wordlist filename in data/wordlists/.
CATEGORIES = ("blasphemy", "vulgarity", "sexual", "slurs")

# Categories produced by the LLM context classifier (no wordlist file).
CONTEXT_CATEGORIES = ("sexual_situation", "crude_innuendo", "disturbing_content")

# Categories produced by the visual scanner (NudeNet).
VISUAL_CATEGORIES = ("nudity",)

ALL_CATEGORIES = CATEGORIES + CONTEXT_CATEGORIES + VISUAL_CATEGORIES

# Default mute/skip per category. Sexual + visual content defaults to "skip"
# because muting a love scene is pointless; the visual content keeps playing.
DEFAULT_ACTIONS: dict[str, str] = {
    "blasphemy": "mute",
    "vulgarity": "mute",
    "sexual": "skip",
    "slurs": "mute",
    "sexual_situation": "skip",
    "crude_innuendo": "mute",
    "disturbing_content": "skip",
    "nudity": "skip",
}


@dataclass
class Flag:
    """A single piece of objectionable content found in the video."""

    start_ms: int                # zero-based offset from start of video
    end_ms: int
    word: str                    # the matched word/phrase as it appears
    category: str                # one of CATEGORIES / CONTEXT_CATEGORIES / VISUAL_CATEGORIES
    context: str = ""            # surrounding sentence/cue, for admin review
    source: str = "transcript"   # "subtitle" | "transcript" | "llm_context" | "visual"
    action: str = "mute"         # "mute" | "skip"
    enabled: bool = True         # admin toggle

    # v2 fields ---
    flag_type: str = "audio"     # "audio" | "visual" — drives mute vs video-skip
    confidence: Optional[float] = None  # 0..1 (LLM, visual); None for keyword
    reason: str = ""             # why the LLM/visual scanner flagged it

    def padded(self, padding_ms: int = DEFAULT_PADDING_MS) -> tuple[int, int]:
        return (max(0, self.start_ms - padding_ms), self.end_ms + padding_ms)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Flag":
        # Accept old profiles missing the v2 fields and fill defaults.
        return cls(
            start_ms=int(d.get("start_ms", 0)),
            end_ms=int(d.get("end_ms", 0)),
            word=str(d.get("word", "")),
            category=str(d.get("category", "vulgarity")),
            context=str(d.get("context", "")),
            source=str(d.get("source", "transcript")),
            action=str(d.get("action", "mute")),
            enabled=bool(d.get("enabled", True)),
            flag_type=str(d.get("flag_type", "audio")),
            confidence=(
                float(d["confidence"]) if d.get("confidence") is not None else None
            ),
            reason=str(d.get("reason", "")),
        )


@dataclass
class Wordlist:
    category: str
    phrases: list[str] = field(default_factory=list)
    # compiled regex matches any of the phrases as a whole word/phrase
    _pattern: re.Pattern | None = None

    def compile(self) -> None:
        if not self.phrases:
            self._pattern = None
            return
        # Sort longest first so multi-word phrases ("god damn") win over "damn".
        ordered = sorted({p.strip() for p in self.phrases if p.strip()},
                         key=len, reverse=True)
        # Word boundaries on both sides; each phrase is escaped.
        # We allow internal whitespace flexibility (one or more whitespace).
        parts = []
        for phrase in ordered:
            tokens = re.split(r"\s+", phrase)
            escaped = r"\s+".join(re.escape(t) for t in tokens)
            parts.append(escaped)
        joined = "(" + "|".join(parts) + ")"
        # \b at both ends; (?i) for case-insensitive.
        self._pattern = re.compile(rf"(?i)\b{joined}\b")

    def find_all(self, text: str) -> list[tuple[re.Match, str]]:
        """Return (match, matched_phrase) pairs."""
        if self._pattern is None:
            return []
        return [(m, m.group(1)) for m in self._pattern.finditer(text)]


def load_wordlists(wordlist_dir: Path) -> dict[str, Wordlist]:
    """Load every <category>.txt under wordlist_dir into a Wordlist."""
    wordlists: dict[str, Wordlist] = {}
    for category in CATEGORIES:
        path = wordlist_dir / f"{category}.txt"
        phrases: list[str] = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                phrases.append(line)
        wl = Wordlist(category=category, phrases=phrases)
        wl.compile()
        wordlists[category] = wl
    return wordlists


@dataclass
class TextSegment:
    """A chunk of text with an associated time range.

    For subtitle cues, this is the cue's start/end and the cue's text.
    For Whisper output, this is a segment (or word, if you provide them
    individually) and its start/end timestamps.
    """

    start_ms: int
    end_ms: int
    text: str
    source: str = "transcript"   # "subtitle" or "transcript"

    # Optional word-level timing. If provided, we use these to make flags
    # tight on the actual word; otherwise we fall back to the segment range.
    words: list["WordTiming"] = field(default_factory=list)


@dataclass
class WordTiming:
    word: str
    start_ms: int
    end_ms: int


def scan_segments(
    segments: Iterable[TextSegment],
    wordlists: dict[str, Wordlist],
    default_action_by_category: dict[str, str] | None = None,
) -> list[Flag]:
    """Run wordlist matching across a stream of TextSegments.

    Returns a deduped, time-sorted list of Flag objects.
    """
    if default_action_by_category is None:
        default_action_by_category = DEFAULT_ACTIONS

    flags: list[Flag] = []
    for seg in segments:
        if not seg.text:
            continue
        for category, wl in wordlists.items():
            for match, phrase in wl.find_all(seg.text):
                start_ms, end_ms = _word_range(seg, match)
                context = _context_snippet(seg.text, match.start(), match.end())
                flags.append(
                    Flag(
                        start_ms=start_ms,
                        end_ms=end_ms,
                        word=phrase,
                        category=category,
                        context=context,
                        source=seg.source,
                        action=default_action_by_category.get(category, "mute"),
                    )
                )
    return _dedupe(sorted(flags, key=lambda f: (f.start_ms, f.end_ms)))


def _word_range(seg: TextSegment, match: re.Match) -> tuple[int, int]:
    """Map a regex match in seg.text to a millisecond range.

    Prefers word-level timing if available; otherwise interpolates linearly
    across the segment's character range.
    """
    if seg.words:
        # Find the first/last word objects whose token text overlaps the match.
        target = match.group(1).lower()
        target_tokens = re.split(r"\s+", target)
        for i in range(len(seg.words) - len(target_tokens) + 1):
            window = seg.words[i : i + len(target_tokens)]
            window_text = " ".join(w.word.lower().strip(".,!?;:'\"") for w in window)
            if window_text == " ".join(target_tokens):
                return window[0].start_ms, window[-1].end_ms
        # Fall through to interpolation if we couldn't align.

    if seg.end_ms <= seg.start_ms or not seg.text:
        return seg.start_ms, seg.end_ms

    total = len(seg.text)
    duration = seg.end_ms - seg.start_ms
    s_frac = match.start() / total
    e_frac = match.end() / total
    return (
        seg.start_ms + int(duration * s_frac),
        seg.start_ms + int(duration * e_frac),
    )


def _context_snippet(text: str, start: int, end: int, radius: int = 40) -> str:
    s = max(0, start - radius)
    e = min(len(text), end + radius)
    snippet = text[s:e].replace("\n", " ").strip()
    if s > 0:
        snippet = "…" + snippet
    if e < len(text):
        snippet = snippet + "…"
    return snippet


def _dedupe(flags: Sequence[Flag], merge_ms: int = 200) -> list[Flag]:
    """Merge near-duplicate flags (same word, overlapping or adjacent ranges)."""
    out: list[Flag] = []
    for f in flags:
        if (
            out
            and out[-1].word.lower() == f.word.lower()
            and out[-1].category == f.category
            and f.start_ms - out[-1].end_ms <= merge_ms
        ):
            # Extend the previous range
            out[-1].end_ms = max(out[-1].end_ms, f.end_ms)
            continue
        out.append(f)
    return out
