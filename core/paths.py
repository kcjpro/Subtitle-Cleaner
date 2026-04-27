"""Path resolution that works in both source mode and a frozen PyInstaller bundle.

Layout when frozen (one-folder build):

    SubtitleCleaner/
        SubtitleCleaner.exe
        _internal/...               # PyInstaller's bundled libraries
        bin/
            ffmpeg.exe              # if bundled at build time
            ffprobe.exe
        data/
            wordlists/*.txt         # editable in place
            profiles/*.json         # auto-created on first save

Layout in source mode:

    <repo>/
        main.py
        core/paths.py               # this file
        bin/                        # optional, mirrors frozen layout
        data/wordlists/*.txt
        data/profiles/*.json
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def get_app_root() -> Path:
    """Folder that holds editable resources (data/, bin/) next to the entry point.

    Frozen: the directory containing the .exe (NOT sys._MEIPASS, which is the
    temporary extraction folder for one-file builds).
    Source: the project root (parent of this file's `core/` folder).
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_data_dir() -> Path:
    return get_app_root() / "data"


def get_wordlist_dir() -> Path:
    p = get_data_dir() / "wordlists"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_profiles_dir() -> Path:
    p = get_data_dir() / "profiles"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_bin_dir() -> Path:
    return get_app_root() / "bin"


# ---------- ffmpeg / ffprobe resolution ----------

def _find_local_binary(name: str) -> Optional[Path]:
    """Look for `name` (with .exe on Windows) inside the app's bin/ folder."""
    candidates = [name]
    if os.name == "nt" and not name.lower().endswith(".exe"):
        candidates.insert(0, f"{name}.exe")
    bin_dir = get_bin_dir()
    for c in candidates:
        p = bin_dir / c
        if p.exists():
            return p
    return None


def get_ffmpeg_path() -> Optional[str]:
    """Return the path to ffmpeg, preferring the bundled copy."""
    local = _find_local_binary("ffmpeg")
    if local is not None:
        return str(local)
    on_path = shutil.which("ffmpeg")
    return on_path


def get_ffprobe_path() -> Optional[str]:
    local = _find_local_binary("ffprobe")
    if local is not None:
        return str(local)
    on_path = shutil.which("ffprobe")
    return on_path


def has_ffmpeg() -> bool:
    return get_ffmpeg_path() is not None


def has_ffprobe() -> bool:
    return get_ffprobe_path() is not None
