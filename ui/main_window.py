"""Main application window: open / scan / review / play."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog, QMainWindow, QMessageBox, QStatusBar, QStyle, QToolBar,
)

from core import paths, settings as app_settings
from core.profile import FilterProfile, load_profile, save_profile
from core.scanner import ScanOptions
from . import icons
from .player_widget import PlayerWidget
from .review_dialog import ReviewDialog
from .scan_dialog import ScanDialog
from .settings_dialog import SettingsDialog


VIDEO_FILTERS = (
    "Video files (*.mp4 *.mkv *.avi *.mov *.m4v *.webm *.wmv *.mpg *.mpeg *.ts);;"
    "All files (*.*)"
)


class MainWindow(QMainWindow):
    def __init__(self, project_root: Optional[Path] = None) -> None:
        super().__init__()
        self.setWindowTitle("Subtitle Cleaner")
        self.resize(1180, 760)

        self._project_root = project_root or paths.get_app_root()
        self._wordlist_dir = paths.get_wordlist_dir()
        self._profiles_dir = paths.get_profiles_dir()
        self._settings = app_settings.load()

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
        tb.setIconSize(self.style().standardIcon(QStyle.SP_DialogOpenButton).availableSizes()[0]
                       if self.style().standardIcon(QStyle.SP_DialogOpenButton).availableSizes()
                       else tb.iconSize())
        self.addToolBar(tb)

        style = self.style()

        self.act_open = QAction(_icon_or_default(icons.open_file, style, QStyle.SP_DialogOpenButton),
                                "Open video\u2026", self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(self.open_video)
        tb.addAction(self.act_open)

        self.act_scan = QAction(_icon_or_default(icons.scan, style, QStyle.SP_BrowserReload),
                                "Scan", self)
        self.act_scan.setShortcut(QKeySequence("Ctrl+S"))
        self.act_scan.triggered.connect(self.scan_video)
        tb.addAction(self.act_scan)

        self.act_review = QAction(
            _icon_or_default(icons.review, style, QStyle.SP_FileDialogDetailedView),
            "Review", self)
        self.act_review.setShortcut(QKeySequence("Ctrl+R"))
        self.act_review.triggered.connect(self.review_filters)
        tb.addAction(self.act_review)

        self.act_play = QAction(
            _icon_or_default(icons.play, style, QStyle.SP_MediaPlay),
            "Play", self)
        self.act_play.setShortcut(QKeySequence("Space"))
        self.act_play.triggered.connect(self._player.toggle_play)
        tb.addAction(self.act_play)

        tb.addSeparator()

        self.act_settings = QAction(
            _icon_or_default(icons.settings, style, QStyle.SP_FileDialogDetailedView),
            "Preferences\u2026", self)
        self.act_settings.setShortcut(QKeySequence("Ctrl+,"))
        self.act_settings.triggered.connect(self.show_settings)
        tb.addAction(self.act_settings)

        self.act_about = QAction(
            _icon_or_default(icons.info, style, QStyle.SP_MessageBoxInformation),
            "About", self)
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
        opts = self._scan_options_from_settings()
        dlg = ScanDialog(
            self._video_path,
            self._wordlist_dir,
            options=opts,
            parent=self,
        )
        if dlg.exec() != ScanDialog.Accepted or dlg.profile is None:
            return
        self._profile = dlg.profile
        save_profile(self._profile, self._video_path, self._profiles_dir)
        self._player.set_profile(self._profile)
        self._update_actions()
        self.statusBar().showMessage(self._profile.notes, 10000)
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
            self._player.play()

    def show_settings(self) -> None:
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec() == SettingsDialog.Accepted:
            self._settings = dlg.settings
            app_settings.save(self._settings)
            self.statusBar().showMessage("Preferences saved.", 4000)

    def closeEvent(self, event):  # type: ignore[override]
        try:
            self._player.shutdown()
        finally:
            super().closeEvent(event)

    # ---------- helpers ----------

    def _scan_options_from_settings(self) -> ScanOptions:
        s = self._settings
        return ScanOptions(
            whisper_model=s.whisper_model,
            language=s.language,
            use_llm_context=s.use_llm_context,
            llm_backend=s.llm_backend,
            llm_model=s.llm_model or None,
            llm_api_key=(
                s.gemini_key() if s.llm_backend == "gemini"
                else s.groq_key() if s.llm_backend == "groq"
                else None
            ),
            llm_base_url=s.llm_base_url or None,
            llm_min_confidence=s.llm_min_confidence,
            use_visual_scan=s.use_visual_scan,
            visual_fps=s.visual_fps,
            visual_min_confidence=s.visual_min_confidence,
        )

    def _show_about(self) -> None:
        QMessageBox.about(
            self, "About Subtitle Cleaner",
            "<b>Subtitle Cleaner</b><br>"
            "Standalone video player that mutes or skips flagged content.<br><br>"
            "Audio: faster-whisper word-level transcription + wordlists.<br>"
            "Context: pluggable LLM (Ollama / Gemini / Groq).<br>"
            "Visual: NudeNet frame sampling.<br>"
            "Player: mpv (libmpv).<br><br>"
            "Edit wordlists in <code>data/wordlists/</code>.<br>"
            "Filter profiles are stored in <code>data/profiles/</code>.",
        )


def _icon_or_default(icon_factory, style, fallback_pixmap):
    """Use a qtawesome icon if available, else fall back to a Qt builtin."""
    icon = icon_factory()
    if icon.isNull():
        return style.standardIcon(fallback_pixmap)
    return icon
