"""Icon helpers backed by qtawesome (Font Awesome inside Qt).

Falls back gracefully to a plain QIcon() if qtawesome isn't installed —
the buttons still work, they just lose the glyph.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QIcon

try:
    import qtawesome as qta  # type: ignore
    _QTA_AVAILABLE = True
except ImportError:
    qta = None  # type: ignore
    _QTA_AVAILABLE = False


# Default icon foreground for our dark theme. Override per-call if needed.
DEFAULT_COLOR = "#e6e6e6"
ACCENT_COLOR = "#4ea1ff"


def _icon(name: str, color: str = DEFAULT_COLOR) -> QIcon:
    if _QTA_AVAILABLE:
        try:
            return qta.icon(name, color=color)
        except Exception:
            pass
    return QIcon()


def play() -> QIcon:
    return _icon("fa5s.play")


def pause() -> QIcon:
    return _icon("fa5s.pause")


def stop() -> QIcon:
    return _icon("fa5s.stop")


def cc_on() -> QIcon:
    return _icon("fa5s.closed-captioning", color=ACCENT_COLOR)


def cc_off() -> QIcon:
    return _icon("fa5s.closed-captioning", color="#666666")


def open_file() -> QIcon:
    return _icon("fa5s.folder-open")


def scan() -> QIcon:
    return _icon("fa5s.search")


def review() -> QIcon:
    return _icon("fa5s.list-ul")


def settings() -> QIcon:
    return _icon("fa5s.cog")


def info() -> QIcon:
    return _icon("fa5s.info-circle")


def nudity() -> QIcon:
    return _icon("fa5s.eye-slash")


def audio() -> QIcon:
    return _icon("fa5s.volume-up")


def visual() -> QIcon:
    return _icon("fa5s.video")


def category_color(category: str) -> str:
    """Hex color for a flag category, used as a left-edge accent in the table."""
    return _CATEGORY_COLORS.get(category, "#888888")


_CATEGORY_COLORS = {
    "blasphemy": "#e9c46a",
    "vulgarity": "#e76f51",
    "sexual": "#f4a4c0",
    "slurs": "#a586d8",
    "sexual_situation": "#d96bb1",
    "crude_innuendo": "#f1b07a",
    "disturbing_content": "#c44d58",
    "nudity": "#ff5f7e",
}
