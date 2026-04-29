"""In-app installer for the heavy optional features (Whisper, NudeNet,
cloud LLM SDKs).

Why not bundle them?
    Bundling faster-whisper + onnxruntime + NudeNet weights + the LLM
    SDKs would push the .exe / .app from ~150 MB to ~2 GB and trip
    constant PyInstaller fragility around dynamic loading (ctranslate2,
    onnxruntime). Instead we ship a slim app and let the user opt in.

How does it work?
    Source mode (running ``python main.py``):
        We install into the *currently active* Python environment with
        ``pip install -r <reqs>``.

    Frozen mode (running the bundled .exe / .app):
        The bundle's Python is sealed (no pip), so we set up a sibling
        virtualenv at::

            Windows: %LOCALAPPDATA%\\SubtitleCleaner\\extras-env\\
            macOS:   ~/Library/Application Support/SubtitleCleaner/extras-env/
            Linux:   ~/.local/share/SubtitleCleaner/extras-env/

        and ``pip install -r <reqs>`` into it. ``main.py`` prepends that
        venv's ``site-packages`` to ``sys.path`` on startup so the
        optional packages become importable.

    Either way, after a successful install we tell the user to restart.

System Python discovery
    To create a venv we need a real Python interpreter. We probe (in
    order)::

        py -3.12, py -3.11, py -3.10, python3.12, python3.11, python3.10,
        python3, python

    If none is found the install button shows a dialog with the
    python.org download link.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from . import paths


# ---------------------------------------------------------------------
# Feature packs
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class FeaturePack:
    key: str               # stable id used in settings/UI
    name: str              # human label
    description: str
    requirements_file: str
    probe_imports: tuple   # importing any of these means the pack is installed


PACKS: List[FeaturePack] = [
    FeaturePack(
        key="whisper",
        name="Audio transcription (Whisper)",
        description=(
            "faster-whisper for word-level timestamps when a video has "
            "no subtitle track. ~350 MB on disk, ~1.5 GB extra for the "
            "'medium' model on first scan."
        ),
        requirements_file="requirements-whisper.txt",
        probe_imports=("faster_whisper",),
    ),
    FeaturePack(
        key="llm",
        name="LLM context analysis",
        description=(
            "Cloud SDKs for Gemini and Groq. Lets the LLM context "
            "classifier flag implied sexual / disturbing content beyond "
            "wordlist matches. ~30 MB. Ollama works without this pack."
        ),
        requirements_file="requirements-llm.txt",
        probe_imports=("google.generativeai", "groq"),
    ),
    FeaturePack(
        key="visual",
        name="Visual nudity scanning (NudeNet)",
        description=(
            "NudeNet + onnxruntime to flag nude/sexual frames that have "
            "no dialogue. ~250 MB on disk plus ~80 MB of model weights "
            "downloaded on first scan."
        ),
        requirements_file="requirements-visual.txt",
        probe_imports=("nudenet",),
    ),
]


def get_pack(key: str) -> Optional[FeaturePack]:
    for p in PACKS:
        if p.key == key:
            return p
    return None


# ---------------------------------------------------------------------
# Status detection
# ---------------------------------------------------------------------

def is_installed(pack: FeaturePack) -> bool:
    """True if any of pack.probe_imports can be imported right now."""
    import importlib.util as _u
    for mod in pack.probe_imports:
        if _u.find_spec(mod) is not None:
            return True
    return False


# ---------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------

def is_frozen() -> bool:
    return paths.is_frozen()


def user_data_dir() -> Path:
    """Per-user, per-platform location for the extras venv + state.

    Mirrors ``core.paths.get_user_data_root()`` but always returns the
    OS-specific path even in source mode (so a developer running from
    source still installs extras into a clean per-user location instead
    of polluting the project tree).
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "SubtitleCleaner"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "SubtitleCleaner"
    return Path.home() / ".local" / "share" / "SubtitleCleaner"


def extras_env_dir() -> Path:
    return user_data_dir() / "extras-env"


def extras_site_packages() -> Optional[Path]:
    """Where pip-installed optional packages land in the extras venv."""
    env = extras_env_dir()
    if not env.exists():
        return None
    if sys.platform == "win32":
        return env / "Lib" / "site-packages"
    # macOS / Linux: lib/pythonX.Y/site-packages
    lib = env / "lib"
    if not lib.exists():
        return None
    for child in lib.iterdir():
        if child.is_dir() and child.name.startswith("python"):
            sp = child / "site-packages"
            if sp.exists():
                return sp
    return None


def extras_python_exe() -> Optional[Path]:
    """The Python interpreter inside the extras venv, once created."""
    env = extras_env_dir()
    if sys.platform == "win32":
        candidate = env / "Scripts" / "python.exe"
    else:
        candidate = env / "bin" / "python3"
        if not candidate.exists():
            candidate = env / "bin" / "python"
    return candidate if candidate.exists() else None


# ---------------------------------------------------------------------
# System Python discovery (frozen mode only)
# ---------------------------------------------------------------------

def _try_python(cmd: List[str]) -> Optional[str]:
    """Return cmd's reported version string if it runs and is >= 3.10."""
    try:
        out = subprocess.run(
            cmd + ["-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    ver = out.stdout.strip()
    try:
        major, minor = map(int, ver.split(".")[:2])
    except ValueError:
        return None
    if (major, minor) < (3, 10):
        return None
    return ver


def find_system_python() -> Optional[List[str]]:
    """Best system Python to use for creating the extras venv. Returns
    the launch command as a list (e.g. ``['py', '-3.12']``), or None."""
    candidates: List[List[str]] = []

    if sys.platform == "win32":
        # py launcher (preferred)
        for ver in ("3.12", "3.11", "3.10"):
            candidates.append(["py", "-" + ver])
        candidates.append(["py", "-3"])

    for name in ("python3.12", "python3.11", "python3.10", "python3", "python"):
        full = shutil.which(name)
        if full:
            candidates.append([full])

    seen = set()
    for cmd in candidates:
        key = tuple(cmd)
        if key in seen:
            continue
        seen.add(key)
        if _try_python(cmd):
            return cmd
    return None


# ---------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------

def _bundled_requirements_path(req_filename: str) -> Optional[Path]:
    """Locate a requirements file shipped with the build.

    Both the Windows and Mac specs ship requirements-*.txt files at "."
    which lands in PyInstaller's ``sys._MEIPASS`` (i.e. ``_internal/`` on
    Windows or ``Contents/Resources/`` inside an .app on Mac). In source
    mode the files sit in the project root.
    """
    candidate = paths.get_bundle_resource_root() / req_filename
    if candidate.exists():
        return candidate
    return None


def _ensure_extras_env(progress_cb: Optional[Callable[[str], None]]) -> Path:
    """Create extras venv if missing. Returns the venv's python.exe path."""
    py = extras_python_exe()
    if py is not None:
        return py

    sys_py = find_system_python()
    if sys_py is None:
        raise FeatureInstallError(
            "No system Python (3.10 or newer) found on PATH. "
            "Install Python 3.12 from https://www.python.org/ and try again. "
            "On Windows, make sure to tick \"Add Python to PATH\" in the installer."
        )

    if progress_cb:
        progress_cb(f"Creating extras venv with {' '.join(sys_py)}...")

    extras_env_dir().parent.mkdir(parents=True, exist_ok=True)
    cmd = sys_py + ["-m", "venv", str(extras_env_dir())]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise FeatureInstallError(
            f"venv creation failed (code {proc.returncode}):\n{proc.stderr}"
        )

    py = extras_python_exe()
    if py is None:
        raise FeatureInstallError(
            f"Created venv at {extras_env_dir()} but could not locate its python."
        )
    return py


class FeatureInstallError(RuntimeError):
    pass


def install(pack: FeaturePack,
            progress_cb: Optional[Callable[[str], None]] = None) -> None:
    """Install the optional pack. Streams subprocess output to progress_cb.

    Raises FeatureInstallError on any failure.
    """
    req_path = _bundled_requirements_path(pack.requirements_file)
    if req_path is None:
        raise FeatureInstallError(
            f"Requirements file not found: {pack.requirements_file}"
        )

    if is_frozen():
        py = _ensure_extras_env(progress_cb)
        # First time: upgrade pip in the venv so wheels resolve cleanly.
        _run_pip([str(py), "-m", "pip", "install", "--upgrade", "pip"], progress_cb)
        _run_pip(
            [str(py), "-m", "pip", "install", "--upgrade",
             "-r", str(req_path)],
            progress_cb,
        )
    else:
        # Source mode: install into the active env.
        _run_pip(
            [sys.executable, "-m", "pip", "install", "--upgrade",
             "-r", str(req_path)],
            progress_cb,
        )


def uninstall(pack: FeaturePack,
              progress_cb: Optional[Callable[[str], None]] = None) -> None:
    """Pip-uninstall every package listed in pack's requirements file."""
    req_path = _bundled_requirements_path(pack.requirements_file)
    if req_path is None:
        raise FeatureInstallError(
            f"Requirements file not found: {pack.requirements_file}"
        )

    pkg_names = _parse_requirements_names(req_path)
    if not pkg_names:
        return

    if is_frozen():
        py = extras_python_exe()
        if py is None:
            return  # nothing to uninstall
        cmd = [str(py), "-m", "pip", "uninstall", "-y"] + pkg_names
    else:
        cmd = [sys.executable, "-m", "pip", "uninstall", "-y"] + pkg_names
    _run_pip(cmd, progress_cb, ignore_failure=True)


def _parse_requirements_names(req_path: Path) -> List[str]:
    """Extract the package names from a requirements file (no extras / version pins)."""
    names: List[str] = []
    for raw in req_path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        # Strip env markers (`pkg; sys_platform == "win32"`) and version specs.
        line = line.split(";", 1)[0]
        for sep in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            if sep in line:
                line = line.split(sep, 1)[0]
                break
        line = line.strip()
        if line:
            names.append(line)
    return names


def _run_pip(cmd: List[str],
             progress_cb: Optional[Callable[[str], None]],
             ignore_failure: bool = False) -> None:
    """Run a pip subprocess and stream every output line to progress_cb."""
    if progress_cb:
        progress_cb(f"$ {' '.join(cmd)}")

    env = os.environ.copy()
    # Encourage pip to give us readable line-by-line output.
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUNBUFFERED", "1")

    proc = subprocess.Popen(
        cmd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
        bufsize=1,
    )

    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if not line:
            continue
        if progress_cb:
            progress_cb(line)

    rc = proc.wait()
    if rc != 0 and not ignore_failure:
        raise FeatureInstallError(
            f"command exited with code {rc}: {' '.join(cmd)}"
        )


# ---------------------------------------------------------------------
# Startup hook
# ---------------------------------------------------------------------

def activate_extras_env() -> None:
    """Prepend the extras venv's site-packages to sys.path so optional
    packages installed there become importable. Safe to call from main.py
    on every startup; it's a no-op when the venv doesn't exist."""
    sp = extras_site_packages()
    if sp is None:
        return
    sp_str = str(sp)
    if sp_str not in sys.path:
        sys.path.insert(0, sp_str)


# ---------------------------------------------------------------------
# Status report (handy for the UI and for diagnostics)
# ---------------------------------------------------------------------

def status_report() -> dict:
    return {
        "frozen": is_frozen(),
        "platform": platform.platform(),
        "system_python": find_system_python(),
        "extras_env": str(extras_env_dir()),
        "extras_env_exists": extras_env_dir().exists(),
        "packs": [
            {
                "key": p.key,
                "name": p.name,
                "installed": is_installed(p),
                "requirements": p.requirements_file,
            }
            for p in PACKS
        ],
    }


def _main_cli() -> int:
    """Tiny CLI for diagnosing on a user's box."""
    print(json.dumps(status_report(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main_cli())
