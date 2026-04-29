"""Apply the app theme.

The dark palette is hand-rolled in `ui/styles/dark.qss`; it covers every
widget we actually use and looks more cohesive than layering generic
qdarkstyle / qt-material sheets on top.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication


HERE = Path(__file__).resolve().parent
DARK_QSS = HERE / "styles" / "dark.qss"


def apply(app: QApplication, theme: str = "dark") -> None:
    if theme == "system" or theme == "light":
        # No light theme yet — fall back to system palette.
        app.setStyleSheet("")
        return

    app.setStyleSheet(_load(DARK_QSS))


def _load(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
