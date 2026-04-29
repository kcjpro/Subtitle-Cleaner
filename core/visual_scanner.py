"""Visual nudity scanning via NudeNet, isolated in a subprocess.

Why a subprocess:
  * NudeNet uses ONNX Runtime which (on GPU) holds CUDA context state that
    can interfere with mpv's renderer if loaded in the main process.
  * Heavy memory use (especially with onnxruntime-gpu) is freed cleanly when
    the child exits.

Pipeline:
  1. Use ffmpeg to dump frames at a fixed rate (default 1 fps) to a temp dir.
  2. Run NudeDetector.detect() on each frame.
  3. Coalesce consecutive flagged frames into Flag ranges.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

from . import paths
from .filter_engine import DEFAULT_ACTIONS, Flag


# NudeNet v3 class names that we treat as flag-worthy. The "_COVERED" classes
# are intentionally excluded — covered breasts/buttocks are common in PG-13
# fare and we don't want false positives swarming the review list.
DEFAULT_FLAG_CLASSES = (
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "BUTTOCKS_EXPOSED",
    "ANUS_EXPOSED",
)

DEFAULT_FPS = 1.0
DEFAULT_CONFIDENCE = 0.55
DEFAULT_MERGE_GAP_S = 1.5  # if two hits are within this gap, merge them


def is_available() -> bool:
    """True if both NudeNet and ffmpeg appear ready to use."""
    if not paths.has_ffmpeg():
        return False
    try:
        import nudenet  # noqa: F401
        return True
    except ImportError:
        return False


def scan_video(
    video_path: Path,
    *,
    fps: float = DEFAULT_FPS,
    min_confidence: float = DEFAULT_CONFIDENCE,
    flag_classes: tuple[str, ...] = DEFAULT_FLAG_CLASSES,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> list[Flag]:
    """Return a list of visual Flags for a single video file."""
    if not is_available():
        return []

    workdir = Path(tempfile.gettempdir()) / "subtitle_cleaner" / "frames"
    if workdir.exists():
        shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True, exist_ok=True)

    out_file = workdir.parent / "_visual_result.json"
    if out_file.exists():
        out_file.unlink()

    if not _extract_frames(video_path, workdir, fps):
        return []

    cmd = [
        sys.executable, "-u", "-c", _SUBPROCESS_SCRIPT,
        str(workdir),
        str(out_file),
        f"{fps:.4f}",
        f"{min_confidence:.4f}",
        ",".join(flag_classes),
    ]
    env = os.environ.copy()
    proc = subprocess.Popen(
        cmd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    for line in proc.stdout:
        line = line.strip()
        if line.startswith("PROGRESS:") and progress_cb is not None:
            try:
                progress_cb(float(line.split(":", 1)[1]))
            except ValueError:
                pass
    proc.wait()
    if proc.returncode != 0 or not out_file.exists():
        shutil.rmtree(workdir, ignore_errors=True)
        return []

    try:
        data = json.loads(out_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        shutil.rmtree(workdir, ignore_errors=True)
        return []
    shutil.rmtree(workdir, ignore_errors=True)

    return _coalesce_to_flags(data, fps=fps)


def _extract_frames(video_path: Path, out_dir: Path, fps: float) -> bool:
    """Use ffmpeg to dump JPEG frames at `fps` to out_dir/frame_%06d.jpg."""
    ffmpeg = paths.get_ffmpeg_path()
    if ffmpeg is None:
        return False
    pattern = out_dir / "frame_%06d.jpg"
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", str(video_path),
        "-vf", f"fps={fps}",
        "-q:v", "5",  # decent JPEG quality, small files
        str(pattern),
    ]
    try:
        subprocess.run(
            cmd, check=True, timeout=3600,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return False
    return any(out_dir.glob("frame_*.jpg"))


def _coalesce_to_flags(
    detections: list[dict],
    *,
    fps: float,
    merge_gap_s: float = DEFAULT_MERGE_GAP_S,
) -> list[Flag]:
    """Merge consecutive flagged frames into time ranges.

    `detections` is a list of {frame_idx, class, score} entries; one entry
    per detection (a frame may contribute multiple).
    """
    if not detections:
        return []
    frame_step_ms = int(round(1000.0 / fps))
    # Group detections by frame index, keep the highest-scoring class per frame.
    by_frame: dict[int, dict] = {}
    for det in detections:
        idx = int(det["frame_idx"])
        score = float(det["score"])
        if idx not in by_frame or score > by_frame[idx]["score"]:
            by_frame[idx] = det
    ordered = sorted(by_frame.values(), key=lambda d: int(d["frame_idx"]))

    flags: list[Flag] = []
    cur: Optional[dict] = None
    cur_start_idx = 0
    cur_last_idx = 0
    cur_max_score = 0.0
    cur_class = ""
    merge_gap_frames = max(1, int(merge_gap_s * fps))

    def _flush() -> None:
        nonlocal cur, cur_max_score, cur_class
        if cur is None:
            return
        start_ms = cur_start_idx * frame_step_ms
        end_ms = (cur_last_idx + 1) * frame_step_ms
        flags.append(Flag(
            start_ms=start_ms,
            end_ms=end_ms,
            word=cur_class.replace("_", " ").title(),
            category="nudity",
            context=f"{cur_class} (score {cur_max_score:.2f})",
            source="visual",
            action=DEFAULT_ACTIONS.get("nudity", "skip"),
            enabled=True,
            flag_type="visual",
            confidence=cur_max_score,
            reason=cur_class,
        ))
        cur = None
        cur_max_score = 0.0
        cur_class = ""

    for det in ordered:
        idx = int(det["frame_idx"])
        score = float(det["score"])
        klass = str(det["class"])
        if cur is None:
            cur = det
            cur_start_idx = idx
            cur_last_idx = idx
            cur_max_score = score
            cur_class = klass
            continue
        if idx - cur_last_idx <= merge_gap_frames:
            cur_last_idx = idx
            if score > cur_max_score:
                cur_max_score = score
                cur_class = klass
        else:
            _flush()
            cur = det
            cur_start_idx = idx
            cur_last_idx = idx
            cur_max_score = score
            cur_class = klass
    _flush()
    return flags


# The subprocess loads NudeNet, walks the frames directory, and emits one
# JSON list of detections at the end. Stdout PROGRESS:0..1 lines drive the UI.
_SUBPROCESS_SCRIPT = r'''
import json, os, sys, glob

frames_dir = sys.argv[1]
out_file = sys.argv[2]
fps = float(sys.argv[3])
min_conf = float(sys.argv[4])
flag_classes = set(sys.argv[5].split(","))

try:
    from nudenet import NudeDetector
except ImportError:
    sys.exit(2)

detector = NudeDetector()

frames = sorted(glob.glob(os.path.join(frames_dir, "frame_*.jpg")))
if not frames:
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump([], f)
    sys.exit(0)

results = []
last_pct = -1
for i, frame_path in enumerate(frames):
    try:
        dets = detector.detect(frame_path) or []
    except Exception:
        dets = []
    for d in dets:
        klass = d.get("class") or d.get("label")
        try:
            score = float(d.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        if klass in flag_classes and score >= min_conf:
            results.append({
                "frame_idx": i,
                "class": klass,
                "score": score,
            })
    pct = int((i + 1) / len(frames) * 100)
    if pct != last_pct:
        last_pct = pct
        print("PROGRESS:" + str((i + 1) / len(frames)), flush=True)

with open(out_file, "w", encoding="utf-8") as f:
    json.dump(results, f)
'''
