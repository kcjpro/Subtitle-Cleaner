"""Modal progress dialog driving a background scan in a worker thread."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QLabel, QProgressBar, QPushButton, QVBoxLayout, QHBoxLayout,
    QMessageBox,
)

from core.scanner import ScanOptions, scan_video
from core.profile import FilterProfile


class _ScanWorker(QObject):
    progressed = Signal(str, float)   # status_message, fraction
    finished = Signal(object)         # FilterProfile
    failed = Signal(str)              # error message

    def __init__(self, video_path: Path, wordlist_dir: Path,
                 options: ScanOptions) -> None:
        super().__init__()
        self.video_path = video_path
        self.wordlist_dir = wordlist_dir
        self.options = options

    def run(self) -> None:
        try:
            profile = scan_video(
                self.video_path,
                self.wordlist_dir,
                options=self.options,
                progress=lambda m, f: self.progressed.emit(m, f),
            )
            self.finished.emit(profile)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"{type(e).__name__}: {e}")


class ScanDialog(QDialog):
    """Runs the scan and exposes the resulting FilterProfile via .profile."""

    def __init__(self, video_path: Path, wordlist_dir: Path,
                 options: Optional[ScanOptions] = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Scanning…")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.profile: Optional[FilterProfile] = None
        self._error: Optional[str] = None

        self._label = QLabel("Preparing…")
        self._label.setWordWrap(True)
        self._bar = QProgressBar()
        self._bar.setRange(0, 1000)
        self._bar.setValue(0)

        self._cancel = QPushButton("Cancel")
        self._cancel.clicked.connect(self.reject)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self._cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{video_path.name}</b>"))
        layout.addWidget(self._label)
        layout.addWidget(self._bar)
        layout.addLayout(btn_row)

        self._thread = QThread(self)
        self._worker = _ScanWorker(video_path, wordlist_dir, options or ScanOptions())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progressed.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._thread.isRunning():
            self._thread.start()

    def _on_progress(self, msg: str, frac: float) -> None:
        self._label.setText(msg)
        self._bar.setValue(max(0, min(1000, int(frac * 1000))))

    def _on_finished(self, profile) -> None:
        self.profile = profile
        self._thread.quit()
        self._thread.wait()
        self.accept()

    def _on_failed(self, msg: str) -> None:
        self._error = msg
        self._thread.quit()
        self._thread.wait()
        QMessageBox.critical(self, "Scan failed", msg)
        self.reject()
