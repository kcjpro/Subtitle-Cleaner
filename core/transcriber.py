"""Speech-to-text transcription via faster-whisper.

This module is *optional*. If faster-whisper isn't installed, `is_available()`
returns False and the rest of the app falls back to subtitle-only scanning.

Transcription runs in a **subprocess** to fully isolate the CUDA context from
the main process (VLC + Qt). When the subprocess exits, all GPU memory is
truly released with no risk of corrupting VLC's rendering state.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

from .filter_engine import TextSegment, WordTiming


DEFAULT_MODEL = "medium"


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
) -> list[TextSegment]:
    """Transcribe audio in a subprocess and return TextSegments with word-level timings.

    Running in a subprocess ensures the CUDA context is fully destroyed when
    transcription finishes, preventing native crashes in VLC.
    """
    out_file = Path(tempfile.gettempdir()) / "subtitle_cleaner" / "_transcribe_result.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    if out_file.exists():
        out_file.unlink()

    # Build the subprocess command using the same Python interpreter.
    cmd = [
        sys.executable, "-u", "-c",
        _SUBPROCESS_SCRIPT,
        str(audio_path),
        model_name,
        language or "",
        str(out_file),
    ]

    # Add NVIDIA DLL paths to the subprocess environment, if the user
    # has installed faster-whisper's GPU stack. We import the nvidia.*
    # packages indirectly via importlib so PyInstaller's static analyzer
    # does NOT pull these (huge) CUDA wheels into the slim bundle.
    env = os.environ.copy()
    import importlib
    for pkg_name in ("nvidia.cublas", "nvidia.cudnn"):
        try:
            pkg = importlib.import_module(pkg_name)
        except ImportError:
            continue
        for base in getattr(pkg, "__path__", []):
            bin_dir = os.path.join(base, "bin")
            if os.path.isdir(bin_dir):
                env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")

    proc = subprocess.Popen(
        cmd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )

    # Read progress lines from the subprocess.
    for line in proc.stdout:
        line = line.strip()
        if line.startswith("PROGRESS:") and progress_cb:
            try:
                frac = float(line.split(":", 1)[1])
                progress_cb(frac)
            except ValueError:
                pass

    proc.wait()

    if proc.returncode != 0 or not out_file.exists():
        return []

    # Parse results from the JSON file written by the subprocess.
    data = json.loads(out_file.read_text(encoding="utf-8"))
    results: list[TextSegment] = []
    for seg in data:
        words = [
            WordTiming(word=w["word"], start_ms=w["start_ms"], end_ms=w["end_ms"])
            for w in seg.get("words", [])
        ]
        results.append(TextSegment(
            start_ms=seg["start_ms"],
            end_ms=seg["end_ms"],
            text=seg["text"],
            source="transcript",
            words=words,
        ))
    return results


_SUBPROCESS_SCRIPT = r'''
import sys, json

audio_path = sys.argv[1]
model_name = sys.argv[2]
language = sys.argv[3] or None
out_file = sys.argv[4]

from faster_whisper import WhisperModel

model = None
segments_iter = None
for device, compute in [("cuda", "float16"), ("cpu", "int8")]:
    try:
        model = WhisperModel(model_name, device=device, compute_type=compute)
        segments_iter, info = model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,
            vad_filter=False,
        )
        break
    except Exception:
        model = None
        segments_iter = None

if segments_iter is None:
    sys.exit(1)

duration = float(getattr(info, "duration", 0.0)) or 0.0
results = []
for seg in segments_iter:
    words = []
    if getattr(seg, "words", None):
        for w in seg.words:
            if w.start is None or w.end is None:
                continue
            words.append({"word": str(w.word).strip(), "start_ms": int(w.start * 1000), "end_ms": int(w.end * 1000)})
    results.append({"start_ms": int(seg.start * 1000), "end_ms": int(seg.end * 1000), "text": str(seg.text).strip(), "words": words})
    if duration > 0:
        print("PROGRESS:" + str(min(1.0, seg.end / duration)), flush=True)

with open(out_file, "w", encoding="utf-8") as f:
    json.dump(results, f)
'''
