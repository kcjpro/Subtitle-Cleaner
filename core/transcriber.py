"""Speech-to-text transcription via faster-whisper.

This module is *optional*. If faster-whisper isn't installed, `is_available()`
returns False and the rest of the app falls back to subtitle-only scanning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional

from .filter_engine import TextSegment, WordTiming


# Default model size. Tradeoff:
#   tiny    -  ~75 MB,   fastest, weakest
#   base    - ~140 MB,   default
#   small   - ~460 MB,   noticeably better
#   medium  - ~1.5 GB,   strong
#   large-v3 - ~3 GB,    best (requires GPU for tolerable speed)
DEFAULT_MODEL = "base"


def is_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def transcribe(
    audio_path: Path,
    model_name: str = DEFAULT_MODEL,
    language: Optional[str] = None,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> Iterator[TextSegment]:
    """Yield TextSegments with word-level timings as Whisper produces them.

    `progress_cb`, if given, is called with a float in [0.0, 1.0] roughly
    representing how much of the audio has been transcribed.
    """
    from faster_whisper import WhisperModel  # type: ignore

    # Pick a reasonable default device. CPU is fine but slow on long videos.
    # int8 quantization is much faster on CPU with minimal quality loss.
    try:
        model = WhisperModel(model_name, device="cuda", compute_type="float16")
    except Exception:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")

    segments_iter, info = model.transcribe(
        str(audio_path),
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )
    duration = float(getattr(info, "duration", 0.0)) or 0.0

    for seg in segments_iter:
        words: list[WordTiming] = []
        if getattr(seg, "words", None):
            for w in seg.words:
                if w.start is None or w.end is None:
                    continue
                words.append(
                    WordTiming(
                        word=str(w.word).strip(),
                        start_ms=int(w.start * 1000),
                        end_ms=int(w.end * 1000),
                    )
                )
        ts = TextSegment(
            start_ms=int(seg.start * 1000),
            end_ms=int(seg.end * 1000),
            text=str(seg.text).strip(),
            source="transcript",
            words=words,
        )
        if progress_cb and duration > 0:
            progress_cb(min(1.0, seg.end / duration))
        yield ts
