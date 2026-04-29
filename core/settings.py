"""Persistent application settings.

Stored as JSON next to the profiles in `data/settings.json` so portable
deployments stay self-contained. API keys live here, with a clear warning
to the user — they can also be supplied via environment variables, in which
case they don't need to be saved.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from . import paths


SETTINGS_FILENAME = "settings.json"


@dataclass
class AppSettings:
    # ---------- Scan ----------
    whisper_model: str = "medium"
    language: Optional[str] = None

    # LLM context classification
    use_llm_context: bool = False
    llm_backend: str = "ollama"           # ollama | gemini | groq
    llm_model: str = ""                   # blank => backend default
    llm_base_url: str = "http://localhost:11434"
    llm_min_confidence: float = 0.55

    # API keys (kept blank by default; env vars take priority at runtime)
    gemini_api_key: str = ""
    groq_api_key: str = ""

    # Visual scan
    use_visual_scan: bool = False
    visual_fps: float = 1.0
    visual_min_confidence: float = 0.55

    # ---------- Player ----------
    default_volume: int = 100

    # ---------- Appearance ----------
    theme: str = "dark"  # dark | light | system

    # Bookkeeping
    version: int = 1

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AppSettings":
        defaults = cls()
        for key in defaults.__dataclass_fields__:
            if key in d:
                setattr(defaults, key, d[key])
        return defaults

    # ---------- API key helpers ----------

    def gemini_key(self) -> str:
        return (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or self.gemini_api_key
        )

    def groq_key(self) -> str:
        return os.environ.get("GROQ_API_KEY") or self.groq_api_key


def settings_path() -> Path:
    return paths.get_data_dir() / SETTINGS_FILENAME


def load() -> AppSettings:
    p = settings_path()
    if not p.exists():
        return AppSettings()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return AppSettings.from_dict(data)
    except (OSError, json.JSONDecodeError):
        return AppSettings()


def save(s: AppSettings) -> Path:
    p = settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(s.to_dict(), indent=2), encoding="utf-8")
    os.replace(tmp, p)
    return p
