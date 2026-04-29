"""Cross-platform helper to build Subtitle Cleaner via PyInstaller.

Run from anywhere:
    python build/build_exe.py

Same workflow as build.bat. See build/README.md for the full story.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
SPEC = HERE / "SubtitleCleaner.spec"


def run(cmd: list, cwd: Path | None = None) -> None:
    print("$", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None)


def main() -> int:
    print("=== Subtitle Cleaner build ===\n")

    run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    run([sys.executable, "-m", "pip", "install",
         "-r", str(PROJECT / "requirements.txt")])
    run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    print("\nNOTE: This build does NOT include faster-whisper, NudeNet, or the")
    print("      cloud LLM SDKs. The .exe scans subtitles only by default.")
    print("      To enable those features, run from source:")
    print("        pip install -r requirements-whisper.txt")
    print("        pip install -r requirements-llm.txt")
    print("        pip install -r requirements-visual.txt")
    print("        python main.py")

    bin_dir = HERE / "bin"
    bundled = [
        n for n in (
            "ffmpeg.exe", "ffprobe.exe", "ffmpeg", "ffprobe",
            "libmpv-2.dll", "mpv-2.dll", "libmpv-1.dll",
        ) if (bin_dir / n).exists()
    ]
    if bundled:
        print(f"\nBundling from build/bin/: {', '.join(bundled)}")
    else:
        print("\nNOTE: drop the following into build/bin/ to bundle them:")
        print("        ffmpeg(.exe), ffprobe(.exe)  <- audio + subtitle extraction")
        print("        libmpv-2.dll                <- video playback engine")
        print("      Otherwise the built app falls back to whatever's on PATH.")

    print("\nRunning PyInstaller...")
    run([sys.executable, "-m", "PyInstaller",
         "--noconfirm", "--clean", str(SPEC)],
        cwd=HERE)

    dist = HERE / "dist" / "SubtitleCleaner"
    profiles = dist / "data" / "profiles"
    profiles.mkdir(parents=True, exist_ok=True)

    # Make sure libmpv-2.dll lands next to the exe (PyInstaller's bin-bundle
    # path can miss raw .dll drops if not pinned in the .spec).
    dist_bin = dist / "bin"
    dist_bin.mkdir(exist_ok=True)
    for name in ("libmpv-2.dll", "mpv-2.dll", "libmpv-1.dll"):
        src = bin_dir / name
        if src.exists():
            shutil.copy2(src, dist_bin / name)

    exe_name = "SubtitleCleaner.exe" if sys.platform == "win32" else "SubtitleCleaner"
    print("\n" + "=" * 60)
    print("Build complete.")
    print(f"Open: {dist / exe_name}")
    print(f"Zip the {dist.name} folder to share the portable app.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed: command returned {e.returncode}")
        raise SystemExit(e.returncode)
