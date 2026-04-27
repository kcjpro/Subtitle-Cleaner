"""Main application window: open / scan / review / play."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QFileDialog, QMessageBox, QToolBar, QStatusBar, QStyle,
)

from core import paths
from core.profile import FilterProfile, load_profile, save_profile
from core.scanner import ScanOptions
from .player_widget import PlayerWidget
from .review_dialog import ReviewDialog
from .scan_dialog import ScanDialog


VIDEO_FILTERS = (
    "Video files (*.mp4 *.mkv *.avi *.mov *.m4v *.webm *.wmv *.mpg *.mpeg *.ts);;"
    "All files (*.*)"
)


class MainWindow(QMainWindow):
    def __init__(self, project_root: Optional[Path] = None) -> None:
        super().__init__()
        self.setWindowTitle("Subtitle Cleaner")
        self.resize(1100, 720)

        # Resolve resource locations via the central paths module so source
        # mode and a frozen PyInstaller bundle behave identically.
        self._project_root = project_root or paths.get_app_root()
        self._wordlist_dir = paths.get_wordlist_dir()
        self._profiles_dir = paths.get_profiles_dir()

        self._video_path: Optional[Path] = None
        self._profile: Optional[FilterProfile] = None

        self._player = PlayerWidget()
        self.setCentralWidget(self._player)
        self.setStatusBar(QStatusBar())

        self._build_toolbar()
        self._update_actions()

    # ---------- toolbar / actions ----------

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        style = self.style()
        self.act_open = QAction(
            style.standardIcon(QStyle.SP_DialogOpenButton),
            "Open video…", self,
        )
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(self.open_video)
        tb.addAction(self.act_open)

        self.act_scan = QAction(
            style.standardIcon(QStyle.SP_BrowserReload),
            "Scan", self,
        )
        self.act_scan.setShortcut(QKeySequence("Ctrl+S"))
        self.act_scan.triggered.connect(self.scan_video)
        tb.addAction(self.act_scan)

        self.act_review = QAction(
            style.standardIcon(QStyle.SP_FileDialogDetailedView),
            "Review filters", self,
        )
        self.act_review.setShortcut(QKeySequence("Ctrl+R"))
        self.act_review.triggered.connect(self.review_filters)
        tb.addAction(self.act_review)

        self.act_play = QAction(
            style.standardIcon(QStyle.SP_MediaPlay),
            "Play", self,
        )
        self.act_play.setShortcut(QKeySequence("Space"))
        self.act_play.triggered.connect(self._player.toggle_play)
        tb.addAction(self.act_play)

        tb.addSeparator()
        self.act_about = QAction("About", self)
        self.act_about.triggered.connect(self._show_about)
        tb.addAction(self.act_about)

    def _update_actions(self) -> None:
        has_video = self._video_path is not None
        has_profile = self._profile is not None
        self.act_scan.setEnabled(has_video)
        self.act_review.setEnabled(has_video and has_profile)
        self.act_play.setEnabled(has_video)

    # ---------- handlers ----------

    def open_video(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open video", "", VIDEO_FILTERS,
        )
        if not path_str:
            return
        path = Path(path_str)
        self._video_path = path

        # Auto-load any existing filter profile.
        self._profile = load_profile(path, self._profiles_dir)
        self._player.load(path, self._profile)
        self._update_actions()

        if self._profile is None:
            self.statusBar().showMessage(
                f"Loaded {path.name}. Click Scan to detect content.", 8000,
            )
        else:
            n = sum(1 for f in self._profile.flags if f.enabled)
            self.statusBar().showMessage(
                f"Loaded {path.name}. Existing profile: "
                f"{n}/{len(self._profile.flags)} flags enabled.",
                8000,
            )

    def scan_video(self) -> None:
        if self._video_path is None:
            return
        dlg = ScanDialog(
            self._video_path,
            self._wordlist_dir,
            options=ScanOptions(),
            parent=self,
        )
        if dlg.exec() != ScanDialog.Accepted or dlg.profile is None:
            return
        self._profile = dlg.profile
        save_profile(self._profile, self._video_path, self._profiles_dir)
        self._player.set_profile(self._profile)
        self._update_actions()
        self.statusBar().showMessage(self._profile.notes, 10000)
        # Open review automatically after a fresh scan.
        self.review_filters()

    def review_filters(self) -> None:
        if self._video_path is None or self._profile is None:
            return
        dlg = ReviewDialog(self._profile, self._video_path, self)
        if dlg.exec() == ReviewDialog.Accepted:
            self._profile = dlg.profile
            save_profile(self._profile, self._video_path, self._profiles_dir)
            self._player.set_profile(self._profile)
            n = sum(1 for f in self._profile.flags if f.enabled)
            self.statusBar().showMessage(
                f"Saved profile: {n}/{len(self._profile.flags)} flags enabled.",
                6000,
            )

    def _show_about(self) -> None:
        QMessageBox.about(
            self, "About Subtitle Cleaner",
            "<b>Subtitle Cleaner</b><br>"
            "Standalone video player that mutes or skips flagged content.<br><br>"
            "Edit wordlists in <code>data/wordlists/</code>.<br>"
            "Filter profiles are stored in <code>data/profiles/</code>.",
        )
