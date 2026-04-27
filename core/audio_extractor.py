"""Pull a 16 kHz mono WAV from a video file using ffmpeg.

Whisper expects 16 kHz mono audio; ffmpeg handles the resample.
Prefers a bundled ffmpeg/ffprobe (in <app>/bin/) over the system one.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from . import paths


def has_ffmpeg() -> bool:
    return paths.has_ffmpeg()


def extract_wav(
    video_path: Path,
    out_dir: Optional[Path] = None,
    sample_rate: int = 16000,
) -> Optional[Path]:
    ffmpeg = paths.get_ffmpeg_path()
    if ffmpeg is None:
        return None
    out_dir = out_dir or Path(tempfile.gettempdir())
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{video_path.stem}.audio.wav"

    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", str(video_path),
        "-vn",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-f", "wav",
        str(out_path),
    ]
    try:
        subprocess.run(
            cmd, check=True, timeout=3600,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path
    return None


def probe_duration_ms(video_path: Path) -> int:
    """Return the video duration in milliseconds, or 0 if unknown."""
    ffprobe = paths.get_ffprobe_path()
    if ffprobe is None:
        return 0
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        out = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, timeout=15,
        ).decode().strip()
        return int(float(out) * 1000)
    except (subprocess.SubprocessError, ValueError, FileNotFoundError):
        return 0
