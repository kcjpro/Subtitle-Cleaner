"""Filter profile persistence.

A profile is a JSON file describing the scan results for one video, including
each Flag and its enabled/action state. Profiles live in data/profiles/ and
are keyed by a hash of the video file path + size so renaming the video
doesn't break the link.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .filter_engine import Flag


PROFILE_SCHEMA_VERSION = 2


@dataclass
class FilterProfile:
    video_path: str           # absolute path at time of scan (informational)
    video_size: int           # bytes (used in the key)
    duration_ms: int = 0
    flags: list[Flag] = field(default_factory=list)
    padding_ms: int = 250     # padding added around each flag during playback
    notes: str = ""
    version: int = PROFILE_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "video_path": self.video_path,
            "video_size": self.video_size,
            "duration_ms": self.duration_ms,
            "padding_ms": self.padding_ms,
            "notes": self.notes,
            "flags": [f.to_dict() for f in self.flags],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FilterProfile":
        return cls(
            version=int(d.get("version", 1)),
            video_path=d.get("video_path", ""),
            video_size=int(d.get("video_size", 0)),
            duration_ms=int(d.get("duration_ms", 0)),
            padding_ms=int(d.get("padding_ms", 250)),
            notes=d.get("notes", ""),
            flags=[Flag.from_dict(f) for f in d.get("flags", [])],
        )


def profile_key(video_path: Path) -> str:
    """Stable per-video key based on absolute path + file size.

    Using size guards against the same filename pointing at a different file.
    Hashing keeps filenames safe across operating systems.
    """
    p = Path(video_path).resolve()
    try:
        size = p.stat().st_size
    except OSError:
        size = 0
    raw = f"{str(p).lower()}|{size}"
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    # Include a short slug for human eyeballs.
    safe_name = "".join(c for c in p.stem if c.isalnum() or c in ("_", "-"))[:40]
    return f"{safe_name}__{h}.json"


def profile_path(video_path: Path, profiles_dir: Path) -> Path:
    profiles_dir.mkdir(parents=True, exist_ok=True)
    return profiles_dir / profile_key(video_path)


def load_profile(video_path: Path, profiles_dir: Path) -> Optional[FilterProfile]:
    path = profile_path(video_path, profiles_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return FilterProfile.from_dict(data)
    except (OSError, json.JSONDecodeError):
        return None


def save_profile(profile: FilterProfile, video_path: Path, profiles_dir: Path) -> Path:
    path = profile_path(video_path, profiles_dir)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path
