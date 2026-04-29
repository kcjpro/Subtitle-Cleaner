"""Application preferences dialog.

Four tabs:
  * Scan              — Whisper model, LLM context backend + key, NudeNet options
  * Player            — default volume, etc.
  * Appearance        — theme picker
  * Optional Features — install/uninstall the heavy ML/AI deps on demand
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QObject, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QProgressDialog, QPushButton, QSizePolicy, QSpinBox,
    QTabWidget, QVBoxLayout, QWidget,
)

from core.settings import AppSettings
from core import feature_installer
from core.feature_installer import FeaturePack, FeatureInstallError


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.resize(640, 560)
        self._settings = settings

        tabs = QTabWidget()
        tabs.addTab(self._build_scan_tab(), "Scan")
        tabs.addTab(self._build_player_tab(), "Player")
        tabs.addTab(self._build_appearance_tab(), "Appearance")
        tabs.addTab(self._build_features_tab(), "Optional Features")

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # ---------- tabs ----------

    def _build_scan_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setLabelAlignment(Qt.AlignRight)

        self._whisper_model = QComboBox()
        self._whisper_model.addItems(
            ["tiny", "base", "small", "medium", "large-v3"]
        )
        self._whisper_model.setCurrentText(self._settings.whisper_model)
        form.addRow("Whisper model:", self._whisper_model)

        self._language = QLineEdit(self._settings.language or "")
        self._language.setPlaceholderText("blank = auto-detect (e.g. \"en\")")
        form.addRow("Language hint:", self._language)

        form.addRow(_section_label("LLM context analysis"))

        self._use_llm = QCheckBox(
            "Use an LLM to flag implied sexual situations / innuendo"
        )
        self._use_llm.setChecked(self._settings.use_llm_context)
        form.addRow("", self._use_llm)

        self._llm_backend = QComboBox()
        self._llm_backend.addItems(["ollama", "gemini", "groq"])
        self._llm_backend.setCurrentText(self._settings.llm_backend)
        form.addRow("Backend:", self._llm_backend)

        self._llm_model = QLineEdit(self._settings.llm_model)
        self._llm_model.setPlaceholderText("blank = backend default")
        form.addRow("Model:", self._llm_model)

        self._llm_base_url = QLineEdit(self._settings.llm_base_url)
        self._llm_base_url.setPlaceholderText(
            "Ollama only: http://localhost:11434"
        )
        form.addRow("Ollama URL:", self._llm_base_url)

        self._gemini_key = QLineEdit(self._settings.gemini_api_key)
        self._gemini_key.setEchoMode(QLineEdit.Password)
        self._gemini_key.setPlaceholderText("or set GEMINI_API_KEY env var")
        form.addRow("Gemini API key:", self._gemini_key)

        self._groq_key = QLineEdit(self._settings.groq_api_key)
        self._groq_key.setEchoMode(QLineEdit.Password)
        self._groq_key.setPlaceholderText("or set GROQ_API_KEY env var")
        form.addRow("Groq API key:", self._groq_key)

        self._llm_min_conf = QDoubleSpinBox()
        self._llm_min_conf.setRange(0.0, 1.0)
        self._llm_min_conf.setSingleStep(0.05)
        self._llm_min_conf.setDecimals(2)
        self._llm_min_conf.setValue(self._settings.llm_min_confidence)
        form.addRow("Min confidence:", self._llm_min_conf)

        form.addRow(_section_label("Visual nudity scan (NudeNet)"))

        self._use_visual = QCheckBox("Sample frames and run NudeNet")
        self._use_visual.setChecked(self._settings.use_visual_scan)
        form.addRow("", self._use_visual)

        self._visual_fps = QDoubleSpinBox()
        self._visual_fps.setRange(0.1, 8.0)
        self._visual_fps.setSingleStep(0.5)
        self._visual_fps.setDecimals(2)
        self._visual_fps.setValue(self._settings.visual_fps)
        form.addRow("Frames per second:", self._visual_fps)

        self._visual_conf = QDoubleSpinBox()
        self._visual_conf.setRange(0.0, 1.0)
        self._visual_conf.setSingleStep(0.05)
        self._visual_conf.setDecimals(2)
        self._visual_conf.setValue(self._settings.visual_min_confidence)
        form.addRow("Min confidence:", self._visual_conf)

        return page

    def _build_player_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setLabelAlignment(Qt.AlignRight)

        self._default_volume = QSpinBox()
        self._default_volume.setRange(0, 200)
        self._default_volume.setValue(self._settings.default_volume)
        self._default_volume.setSuffix("  %")
        form.addRow("Default volume:", self._default_volume)

        return page

    def _build_appearance_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setLabelAlignment(Qt.AlignRight)

        self._theme = QComboBox()
        self._theme.addItems(["dark", "light", "system"])
        self._theme.setCurrentText(self._settings.theme)
        form.addRow("Theme:", self._theme)

        note = QLabel(
            "Theme changes take effect on next launch."
        )
        note.setWordWrap(True)
        form.addRow("", note)

        return page

    def _build_features_tab(self) -> QWidget:
        """One row per FeaturePack: name, status badge, Install/Uninstall."""
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setSpacing(12)

        intro = QLabel(
            "These are heavy machine-learning add-ons that we don't bundle "
            "into the click-to-run app to keep the download small. Install "
            "them on demand here. After install, restart Subtitle Cleaner "
            "for the new packages to be picked up."
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        if feature_installer.is_frozen():
            sys_py = feature_installer.find_system_python()
            if sys_py is None:
                warn = QLabel(
                    "<b>Warning:</b> No system Python (3.10+) was found on PATH. "
                    "The Install buttons will not work until you install Python "
                    "from <a href=\"https://www.python.org/\">python.org</a> and "
                    "re-launch Subtitle Cleaner. On Windows, tick "
                    "&quot;Add Python to PATH&quot; in the installer."
                )
            else:
                env_label = str(feature_installer.extras_env_dir())
                warn = QLabel(
                    f"<small>Optional packages will be installed into a "
                    f"sibling environment at:<br/><code>{env_label}</code><br/>"
                    f"using <code>{' '.join(sys_py)}</code>.</small>"
                )
            warn.setWordWrap(True)
            warn.setOpenExternalLinks(True)
            warn.setTextInteractionFlags(Qt.TextBrowserInteraction)
            outer.addWidget(warn)
        else:
            note = QLabel(
                "<small>Running from source — packages will be installed into "
                "the active Python environment.</small>"
            )
            note.setWordWrap(True)
            outer.addWidget(note)

        for pack in feature_installer.PACKS:
            outer.addWidget(_FeatureRow(pack, self))

        outer.addStretch(1)
        return page

    # ---------- save ----------

    def _on_save(self) -> None:
        s = self._settings
        s.whisper_model = self._whisper_model.currentText()
        s.language = self._language.text().strip() or None
        s.use_llm_context = self._use_llm.isChecked()
        s.llm_backend = self._llm_backend.currentText()
        s.llm_model = self._llm_model.text().strip()
        s.llm_base_url = self._llm_base_url.text().strip() or "http://localhost:11434"
        s.gemini_api_key = self._gemini_key.text().strip()
        s.groq_api_key = self._groq_key.text().strip()
        s.llm_min_confidence = float(self._llm_min_conf.value())
        s.use_visual_scan = self._use_visual.isChecked()
        s.visual_fps = float(self._visual_fps.value())
        s.visual_min_confidence = float(self._visual_conf.value())
        s.default_volume = int(self._default_volume.value())
        s.theme = self._theme.currentText()
        self.accept()

    # Convenience: outsiders read the (mutated) settings via this property.
    @property
    def settings(self) -> AppSettings:
        return self._settings


def _section_label(text: str) -> QLabel:
    lbl = QLabel(f"<b>{text}</b>")
    lbl.setContentsMargins(0, 12, 0, 0)
    return lbl


# ---------- Optional Features helpers ----------

class _FeatureRow(QFrame):
    """A single FeaturePack row: title + status + description + buttons."""

    def __init__(self, pack: FeaturePack, parent: QWidget) -> None:
        super().__init__(parent)
        self._pack = pack
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame { background: #1f232c; border: 1px solid #2c313a; "
            "border-radius: 6px; padding: 10px; }"
        )

        outer = QVBoxLayout(self)
        outer.setSpacing(6)

        # Top row: name + status badge + buttons.
        top = QHBoxLayout()
        title = QLabel(f"<b>{pack.name}</b>")
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top.addWidget(title)

        self._status = QLabel()
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setMinimumWidth(110)
        self._status.setStyleSheet(
            "padding: 2px 8px; border-radius: 9px; font-weight: 600;"
        )
        top.addWidget(self._status)

        self._install_btn = QPushButton("Install")
        self._install_btn.clicked.connect(self._on_install)
        top.addWidget(self._install_btn)

        self._uninstall_btn = QPushButton("Uninstall")
        self._uninstall_btn.clicked.connect(self._on_uninstall)
        top.addWidget(self._uninstall_btn)

        outer.addLayout(top)

        desc = QLabel(pack.description)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #a8b0bf;")
        outer.addWidget(desc)

        self._refresh_status()

    # ---------- behaviour ----------

    def _refresh_status(self) -> None:
        installed = feature_installer.is_installed(self._pack)
        if installed:
            self._status.setText("Installed")
            self._status.setStyleSheet(
                self._status.styleSheet() + "background: #14532d; color: white;"
            )
            self._install_btn.setText("Reinstall")
            self._uninstall_btn.setEnabled(True)
        else:
            self._status.setText("Not installed")
            self._status.setStyleSheet(
                self._status.styleSheet() + "background: #3a3f4b; color: #d6dae4;"
            )
            self._install_btn.setText("Install")
            self._uninstall_btn.setEnabled(False)

    def _on_install(self) -> None:
        if feature_installer.is_frozen():
            sys_py = feature_installer.find_system_python()
            if sys_py is None:
                QMessageBox.warning(
                    self,
                    "System Python required",
                    "No system Python (3.10 or newer) was found on PATH.\n\n"
                    "Install Python 3.12 from python.org first, then "
                    "re-launch Subtitle Cleaner.",
                )
                return

        run_pip_with_dialog(self, "Installing " + self._pack.name,
                            install=True, pack=self._pack)
        self._refresh_status()

    def _on_uninstall(self) -> None:
        if QMessageBox.question(
            self,
            "Uninstall " + self._pack.name + "?",
            "Remove this optional feature from Subtitle Cleaner?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        run_pip_with_dialog(self, "Uninstalling " + self._pack.name,
                            install=False, pack=self._pack)
        self._refresh_status()


class _PipWorker(QObject):
    """Runs feature_installer.install / uninstall on a worker thread."""

    progressed = Signal(str)
    finished = Signal(bool, str)        # success, error_message

    def __init__(self, pack: FeaturePack, install: bool) -> None:
        super().__init__()
        self._pack = pack
        self._install = install

    def run(self) -> None:
        cb = lambda line: self.progressed.emit(line)  # noqa: E731
        try:
            if self._install:
                feature_installer.install(self._pack, cb)
            else:
                feature_installer.uninstall(self._pack, cb)
        except FeatureInstallError as e:
            self.finished.emit(False, str(e))
            return
        except Exception as e:  # noqa: BLE001
            self.finished.emit(False, f"{type(e).__name__}: {e}")
            return
        self.finished.emit(True, "")


def run_pip_with_dialog(parent: QWidget, title: str, *,
                        install: bool, pack: FeaturePack) -> None:
    """Spin up a modal dialog with a live log of pip output."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setModal(True)
    dlg.resize(720, 420)

    layout = QVBoxLayout(dlg)
    msg = QLabel(f"{title}... this can take a few minutes for large packages.")
    msg.setWordWrap(True)
    layout.addWidget(msg)

    log = QPlainTextEdit()
    log.setReadOnly(True)
    log.setStyleSheet(
        "QPlainTextEdit { font-family: 'Consolas', 'Menlo', monospace; "
        "font-size: 11px; background: #0d0f13; color: #cfd6e2; }"
    )
    layout.addWidget(log, stretch=1)

    btn_box = QDialogButtonBox(QDialogButtonBox.Close)
    close_btn = btn_box.button(QDialogButtonBox.Close)
    close_btn.setEnabled(False)
    btn_box.rejected.connect(dlg.reject)
    layout.addWidget(btn_box)

    # ---- Worker thread setup ----
    thread = QThread()
    worker = _PipWorker(pack, install=install)
    worker.moveToThread(thread)

    state = {"ok": False, "err": ""}

    def on_progress(line: str) -> None:
        log.appendPlainText(line)

    def on_finished(ok: bool, err: str) -> None:
        state["ok"] = ok
        state["err"] = err
        thread.quit()
        close_btn.setEnabled(True)
        if ok:
            log.appendPlainText("")
            log.appendPlainText("[done] Restart Subtitle Cleaner to load the new packages.")
        else:
            log.appendPlainText("")
            log.appendPlainText(f"[failed] {err}")

    worker.progressed.connect(on_progress)
    worker.finished.connect(on_finished)
    thread.started.connect(worker.run)
    thread.finished.connect(worker.deleteLater)
    thread.start()

    dlg.exec()

    # If the user closes mid-install we just let the thread drain on its
    # own. The pip subprocess is short-lived enough that this is fine.
    if not thread.isFinished():
        thread.quit()
        thread.wait(2000)

    if state["ok"]:
        QMessageBox.information(
            parent, "Restart required",
            "The optional feature was installed.\n\n"
            "Close and reopen Subtitle Cleaner to enable it.",
        )
