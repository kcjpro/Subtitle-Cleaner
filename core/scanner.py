"""High-level scan orchestrator.

Runs three independent detection passes and merges the results:

  1. Audio transcript (Whisper or subtitles) -> wordlist matching.
  2. LLM context classification (optional) -> implied/contextual flags.
  3. Visual NudeNet pass (optional) -> nudity flags.

Each step degrades gracefully if its dependency isn't installed/configured.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import (
    audio_extractor, llm_classifier, subtitle_extractor, subtitle_parser,
    transcriber, visual_scanner,
)
from .filter_engine import Flag, TextSegment, load_wordlists, scan_segments
from .llm import make_classifier
from .profile import FilterProfile

ProgressCb = Callable[[str, float], None]
"""Callback signature: (status_message, fraction_complete in 0..1)."""


@dataclass
class ScanOptions:
    # --- Audio source preferences ---
    use_sidecar_subtitles: bool = True
    use_embedded_subtitles: bool = True
    use_transcription: bool = True
    prefer_transcription: bool = True
    whisper_model: str = "medium"
    language: Optional[str] = None  # None = auto-detect

    # --- LLM context classification ---
    use_llm_context: bool = False
    llm_backend: str = "ollama"          # ollama | gemini | groq
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None   # for ollama
    llm_min_confidence: float = 0.55

    # --- Visual nudity detection ---
    use_visual_scan: bool = False
    visual_fps: float = 1.0
    visual_min_confidence: float = 0.55
    visual_classes: tuple[str, ...] = field(
        default_factory=lambda: visual_scanner.DEFAULT_FLAG_CLASSES
    )


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
    _emit(progress, "Loading wordlists\u2026", 0.02)
    wordlists = load_wordlists(wordlist_dir)

    duration_ms = audio_extractor.probe_duration_ms(video_path)
    profile = FilterProfile(
        video_path=str(video_path.resolve()),
        video_size=_safe_size(video_path),
        duration_ms=duration_ms,
    )

    all_flags: list[Flag] = []
    notes: list[str] = []

    # ----------------------------------------------------------- Audio pass
    segments, audio_source = _gather_audio_segments(video_path, options, progress)
    if segments:
        _emit(progress, "Matching wordlists\u2026", 0.62)
        wordlist_flags = scan_segments(segments, wordlists)
        all_flags.extend(wordlist_flags)
        notes.append(f"audio:{audio_source} ({len(segments)} seg, "
                     f"{len(wordlist_flags)} keyword flags)")

        # ------------------------------------------------------- LLM pass
        if options.use_llm_context:
            classifier = make_classifier(
                options.llm_backend,
                api_key=options.llm_api_key,
                model=options.llm_model,
                base_url=options.llm_base_url,
            )
            if classifier is None:
                _emit(progress,
                      f"LLM backend '{options.llm_backend}' not available; "
                      "skipping context analysis.", 0.65)
            elif not classifier.is_available():
                _emit(progress,
                      f"{options.llm_backend} not reachable; "
                      "skipping context analysis.", 0.65)
            else:
                _emit(progress,
                      f"Analysing dialogue context with {options.llm_backend}\u2026",
                      0.66)

                def _llm_prog(frac: float) -> None:
                    _emit(progress,
                          "Analysing dialogue context\u2026",
                          0.66 + frac * 0.14)

                ctx_flags = llm_classifier.classify_transcript(
                    segments,
                    classifier,
                    progress_cb=_llm_prog,
                    min_confidence=options.llm_min_confidence,
                )
                all_flags.extend(ctx_flags)
                notes.append(f"llm:{options.llm_backend} ({len(ctx_flags)} flags)")
    else:
        notes.append("audio:none")

    # --------------------------------------------------------- Visual pass
    if options.use_visual_scan:
        if not visual_scanner.is_available():
            _emit(progress,
                  "NudeNet or ffmpeg not available; skipping visual scan.",
                  0.82)
        else:
            _emit(progress, "Scanning frames for visual content\u2026", 0.83)

            def _vis_prog(frac: float) -> None:
                _emit(progress,
                      "Scanning frames\u2026",
                      0.83 + frac * 0.13)

            visual_flags = visual_scanner.scan_video(
                video_path,
                fps=options.visual_fps,
                min_confidence=options.visual_min_confidence,
                flag_classes=options.visual_classes,
                progress_cb=_vis_prog,
            )
            all_flags.extend(visual_flags)
            notes.append(f"visual ({len(visual_flags)} flags)")

    # --------------------------------------------------------- Merge & save
    _emit(progress, "Finalizing\u2026", 0.98)
    all_flags.sort(key=lambda f: (f.start_ms, f.end_ms))
    profile.flags = all_flags
    profile.notes = "; ".join(notes) if notes else "no source"
    _emit(progress, profile.notes, 1.0)
    return profile


# ---------- audio segment gathering ----------

def _gather_audio_segments(
    video_path: Path,
    options: ScanOptions,
    progress: Optional[ProgressCb],
) -> tuple[list[TextSegment], Optional[str]]:
    segments: list[TextSegment] = []
    used_source: Optional[str] = None

    if options.prefer_transcription and options.use_transcription:
        segments, used_source = _try_transcription(
            video_path, options, progress)

    if not segments and options.use_sidecar_subtitles:
        sidecar = subtitle_parser.find_sidecar_subtitle(video_path)
        if sidecar is not None:
            _emit(progress, f"Reading sidecar subtitles ({sidecar.name})\u2026", 0.1)
            segments = subtitle_parser.parse_subtitle_file(sidecar)
            used_source = f"sidecar:{sidecar.name}"

    if not segments and options.use_embedded_subtitles:
        if subtitle_extractor.has_ffmpeg():
            _emit(progress, "Looking for embedded subtitle tracks\u2026", 0.15)
            extracted = subtitle_extractor.extract_first_text_subtitle(
                video_path,
                out_dir=Path(tempfile.gettempdir()) / "subtitle_cleaner",
            )
            if extracted is not None:
                _emit(progress, "Parsing embedded subtitles\u2026", 0.25)
                segments = subtitle_parser.parse_subtitle_file(extracted)
                used_source = f"embedded:{extracted.name}"

    if (
        not segments
        and options.use_transcription
        and not options.prefer_transcription
    ):
        segments, used_source = _try_transcription(
            video_path, options, progress)

    return segments, used_source


def _try_transcription(
    video_path: Path,
    options: ScanOptions,
    progress: Optional[ProgressCb],
) -> tuple[list[TextSegment], Optional[str]]:
    """Attempt Whisper transcription. Returns (segments, source_label)."""
    if not transcriber.is_available():
        _emit(progress,
              "faster-whisper not installed; skipping transcription.", 0.3)
        return [], None
    if not audio_extractor.has_ffmpeg():
        _emit(progress, "ffmpeg not found; cannot extract audio.", 0.3)
        return [], None
    _emit(progress, "Extracting audio\u2026", 0.3)
    wav = audio_extractor.extract_wav(
        video_path,
        out_dir=Path(tempfile.gettempdir()) / "subtitle_cleaner",
    )
    if wav is None:
        return [], None
    _emit(progress, "Transcribing audio (this can take a while)\u2026", 0.4)

    def _whisper_progress(frac: float) -> None:
        _emit(progress, "Transcribing audio\u2026", 0.4 + frac * 0.2)

    segments = transcriber.transcribe(
        wav,
        model_name=options.whisper_model,
        language=options.language,
        progress_cb=_whisper_progress,
    )
    return segments, "whisper"


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
