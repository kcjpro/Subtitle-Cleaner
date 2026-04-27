"""High-level scan orchestrator.

Strategy (in order):
  1. Sidecar subtitle file next to the video.
  2. Embedded subtitle track (MKV) extracted via ffmpeg.
  3. Audio transcription with faster-whisper.

The caller can force which sources to use via ScanOptions.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import audio_extractor, subtitle_extractor, subtitle_parser, transcriber
from .filter_engine import Flag, TextSegment, load_wordlists, scan_segments
from .profile import FilterProfile

ProgressCb = Callable[[str, float], None]
"""Callback signature: (status_message, fraction_complete in 0..1)."""


@dataclass
class ScanOptions:
    use_sidecar_subtitles: bool = True
    use_embedded_subtitles: bool = True
    use_transcription: bool = True
    whisper_model: str = "base"
    language: Optional[str] = None  # None = auto-detect


def scan_video(
    video_path: Path,
    wordlist_dir: Path,
    options: Optional[ScanOptions] = None,
    progress: Optional[ProgressCb] = None,
) -> FilterProfile:
    """Scan one video and return a FilterProfile with detected flags.

    Never raises for missing optional dependencies; instead it skips that
    source and continues. If nothing is available, the returned profile
    will simply have an empty flag list.
    """
    options = options or ScanOptions()
    video_path = Path(video_path)
    wordlist_dir = Path(wordlist_dir)
    _emit(progress, "Loading wordlists…", 0.02)
    wordlists = load_wordlists(wordlist_dir)

    duration_ms = audio_extractor.probe_duration_ms(video_path)
    profile = FilterProfile(
        video_path=str(video_path.resolve()),
        video_size=_safe_size(video_path),
        duration_ms=duration_ms,
    )

    segments: list[TextSegment] = []
    used_source: Optional[str] = None

    # --- 1. Sidecar subtitles ---
    if options.use_sidecar_subtitles:
        sidecar = subtitle_parser.find_sidecar_subtitle(video_path)
        if sidecar is not None:
            _emit(progress, f"Reading sidecar subtitles ({sidecar.name})…", 0.1)
            segments = subtitle_parser.parse_subtitle_file(sidecar)
            used_source = f"sidecar:{sidecar.name}"

    # --- 2. Embedded subtitles ---
    if not segments and options.use_embedded_subtitles:
        if subtitle_extractor.has_ffmpeg():
            _emit(progress, "Looking for embedded subtitle tracks…", 0.15)
            extracted = subtitle_extractor.extract_first_text_subtitle(
                video_path,
                out_dir=Path(tempfile.gettempdir()) / "subtitle_cleaner",
            )
            if extracted is not None:
                _emit(progress, "Parsing embedded subtitles…", 0.25)
                segments = subtitle_parser.parse_subtitle_file(extracted)
                used_source = f"embedded:{extracted.name}"

    # --- 3. Audio transcription ---
    if not segments and options.use_transcription:
        if not transcriber.is_available():
            _emit(progress,
                  "faster-whisper not installed; skipping transcription.", 0.3)
        elif not audio_extractor.has_ffmpeg():
            _emit(progress, "ffmpeg not found; cannot extract audio.", 0.3)
        else:
            _emit(progress, "Extracting audio…", 0.3)
            wav = audio_extractor.extract_wav(
                video_path,
                out_dir=Path(tempfile.gettempdir()) / "subtitle_cleaner",
            )
            if wav is not None:
                _emit(progress, "Transcribing audio (this can take a while)…", 0.4)

                def _whisper_progress(frac: float) -> None:
                    # Map 0..1 transcription progress into 0.4..0.9 overall.
                    _emit(progress,
                          "Transcribing audio…",
                          0.4 + frac * 0.5)

                segments = list(
                    transcriber.transcribe(
                        wav,
                        model_name=options.whisper_model,
                        language=options.language,
                        progress_cb=_whisper_progress,
                    )
                )
                used_source = "whisper"

    _emit(progress, "Matching against wordlists…", 0.92)
    flags = scan_segments(segments, wordlists)
    profile.flags = flags
    profile.notes = f"Scanned via {used_source or 'no source'}; "\
                    f"{len(segments)} segments, {len(flags)} flags."
    _emit(progress, profile.notes, 1.0)
    return profile


def _emit(progress: Optional[ProgressCb], msg: str, frac: float) -> None:
    if progress is not None:
        try:
            progress(msg, frac)
        except Exception:
            pass


def _safe_size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0
