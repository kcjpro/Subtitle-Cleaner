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

    Frozen one-folder build (Windows / Linux):
        <dist>/SubtitleCleaner/
            SubtitleCleaner.exe              <-- sys.executable
            data/...
            bin/...
        => return the .exe's directory.

    Frozen .app bundle (macOS):
        SubtitleCleaner.app/Contents/
            MacOS/SubtitleCleaner            <-- sys.executable
            Resources/data/...
            Resources/bin/...
            Frameworks/libmpv.2.dylib
        => return Contents/Resources/ so data and bin paths line up
        with the Windows layout.

    Source mode:
        return the project root (parent of this file's core/ folder).
    """
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        # Mac .app bundle: MacOS/.. = Contents/, then Contents/Resources/.
        if sys.platform == "darwin" and exe_dir.name == "MacOS":
            resources = exe_dir.parent / "Resources"
            if resources.exists():
                return resources
        return exe_dir
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


# ---------- libmpv resolution ----------

_MPV_DLL_NAMES = (
    "libmpv-2.dll", "mpv-2.dll", "libmpv-1.dll", "mpv-1.dll",
    "libmpv.so.2", "libmpv.so.1", "libmpv.dylib",
)


# Common Mac libmpv install locations (Homebrew on Apple Silicon vs Intel,
# MacPorts). Searched only as a fallback when nothing is bundled in bin/.
_MAC_LIBMPV_FALLBACKS = (
    "/opt/homebrew/lib/libmpv.2.dylib",      # Apple Silicon brew
    "/opt/homebrew/lib/libmpv.dylib",
    "/usr/local/lib/libmpv.2.dylib",         # Intel brew
    "/usr/local/lib/libmpv.dylib",
    "/opt/local/lib/libmpv.2.dylib",         # MacPorts
    "/opt/local/lib/libmpv.dylib",
)


def _get_mac_frameworks_dir() -> Optional[Path]:
    """If we're running inside a Mac .app bundle, return Contents/Frameworks/."""
    if sys.platform != "darwin" or not is_frozen():
        return None
    exe_dir = Path(sys.executable).resolve().parent
    if exe_dir.name != "MacOS":
        return None
    fw = exe_dir.parent / "Frameworks"
    return fw if fw.exists() else None


def get_libmpv_path() -> Optional[str]:
    """Return the path to a bundled libmpv shared library if present."""
    # 1. Check the bundle's bin/ folder (Windows + the source-mode Mac).
    bin_dir = get_bin_dir()
    for name in _MPV_DLL_NAMES:
        candidate = bin_dir / name
        if candidate.exists():
            return str(candidate)

    # 2. On a frozen Mac .app, libmpv lives in Contents/Frameworks/.
    fw = _get_mac_frameworks_dir()
    if fw is not None:
        for name in _MPV_DLL_NAMES:
            candidate = fw / name
            if candidate.exists():
                return str(candidate)

    # 3. Mac fallback: look for a system-installed libmpv (brew/MacPorts).
    if sys.platform == "darwin":
        for fallback in _MAC_LIBMPV_FALLBACKS:
            if os.path.exists(fallback):
                return fallback

    return None


def setup_mpv_dll_path() -> None:
    """Ensure the bundled libmpv-2.dll / libmpv.dylib can be located by
    python-mpv. Must be called BEFORE `import mpv`.
    """
    bin_dir = get_bin_dir()

    if os.name == "nt":
        if bin_dir.exists():
            try:
                os.add_dll_directory(str(bin_dir))
            except (OSError, AttributeError):
                pass
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
        return

    if sys.platform == "darwin":
        # python-mpv reads $MPV_DYLIB_PATH (if set) before falling back
        # to dlopen's normal search. Point it at the bundled dylib when
        # we have one, otherwise at a known brew/MacPorts location.
        bundled = get_libmpv_path()
        if bundled and "MPV_DYLIB_PATH" not in os.environ:
            os.environ["MPV_DYLIB_PATH"] = bundled

        # Ensure the dynamic loader can find libmpv's transitive dylibs
        # next to it (Frameworks/ inside an .app bundle, bin/ otherwise).
        extra_dirs = []
        fw = _get_mac_frameworks_dir()
        if fw is not None:
            extra_dirs.append(str(fw))
        if bin_dir.exists():
            extra_dirs.append(str(bin_dir))
        if extra_dirs:
            os.environ["DYLD_LIBRARY_PATH"] = (
                os.pathsep.join(extra_dirs)
                + os.pathsep + os.environ.get("DYLD_LIBRARY_PATH", "")
            )
        return

    # Linux / other unix.
    if bin_dir.exists():
        os.environ["LD_LIBRARY_PATH"] = (
            str(bin_dir) + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
        )
