"""Subtitle Cleaner — entry point.

Launch with:  python main.py
Or run the built SubtitleCleaner.exe (see build/README.md).
"""

from __future__ import annotations

import sys

# IMPORTANT: this must run BEFORE any optional-feature import (faster_whisper,
# nudenet, google.generativeai, groq) so the per-user extras venv's
# site-packages is on sys.path. When the user installs an optional pack
# from Settings -> Optional Features, it lands in that venv; activating it
# here makes those packages importable on the next launch.
from core import feature_installer
feature_installer.activate_extras_env()

from PySide6.QtWidgets import QApplication

from core import paths, settings as app_settings
from ui import theme
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Subtitle Cleaner")
    app.setOrganizationName("SubtitleCleaner")

    settings = app_settings.load()
    theme.apply(app, settings.theme)

    win = MainWindow(project_root=paths.get_app_root())
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
