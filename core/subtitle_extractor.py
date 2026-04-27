"""Extract embedded subtitle tracks from video files (mostly MKV) using ffmpeg.

If the video has one or more text-based subtitle tracks (subrip/srt, ass, etc.)
we pull the first matching track to a temporary .srt file and return its path.

If ffmpeg/ffprobe aren't available or no subtitle track exists, returns None.
Prefers a bundled ffmpeg/ffprobe (in <app>/bin/) over the system one.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from . import paths


# Subtitle codecs we know how to convert directly to SRT.
_TEXT_SUB_CODECS = {"subrip", "srt", "ass", "ssa", "webvtt", "mov_text"}


def has_ffmpeg() -> bool:
    return paths.has_ffmpeg() and paths.has_ffprobe()


def list_subtitle_streams(video_path: Path) -> list[dict]:
    """Return ffprobe metadata for each subtitle stream in the file."""
    ffprobe = paths.get_ffprobe_path()
    if ffprobe is None:
        return []
    cmd = [
        ffprobe, "-v", "error",
        "-select_streams", "s",
        "-show_streams", "-of", "json",
        str(video_path),
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
    except (subprocess.SubprocessError, FileNotFoundError):
        return []
    try:
        data = json.loads(out.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    return data.get("streams", []) or []


def extract_first_text_subtitle(
    video_path: Path,
    out_dir: Optional[Path] = None,
    language_priority: tuple = ("eng", "en"),
) -> Optional[Path]:
    """Extract the first text-based subtitle stream as an .srt file.

    Picks an English track if available; otherwise the first text track.
    Returns the path to the extracted .srt, or None if nothing usable.
    """
    ffmpeg = paths.get_ffmpeg_path()
    if ffmpeg is None:
        return None

    streams = list_subtitle_streams(video_path)
    if not streams:
        return None

    text_streams = [
        s for s in streams
        if (s.get("codec_name") or "").lower() in _TEXT_SUB_CODECS
    ]
    if not text_streams:
        return None

    # Prefer language match.
    chosen = None
    for lang in language_priority:
        for s in text_streams:
            if (s.get("tags", {}) or {}).get("language", "").lower() == lang:
                chosen = s
                break
        if chosen:
            break
    if chosen is None:
        chosen = text_streams[0]

    stream_index = chosen.get("index")
    if stream_index is None:
        return None

    out_dir = out_dir or Path(tempfile.gettempdir())
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{video_path.stem}.extracted.srt"

    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", str(video_path),
        "-map", f"0:{stream_index}",
        "-c:s", "srt",
        str(out_path),
    ]
    try:
        subprocess.run(
            cmd, check=True, timeout=300,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path
    return None
