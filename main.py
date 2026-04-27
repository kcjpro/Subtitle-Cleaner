"""Subtitle Cleaner — entry point.

Launch with:  python main.py
Or run the built SubtitleCleaner.exe (see build/README.md).
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from core import paths
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Subtitle Cleaner")
    app.setOrganizationName("SubtitleCleaner")

    # paths.get_app_root() handles both source layout and frozen builds.
    win = MainWindow(project_root=paths.get_app_root())
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
