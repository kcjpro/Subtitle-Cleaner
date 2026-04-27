"""Admin review dialog: table of flags with on/off + action toggles.

Shows: timestamp | category | word | context | action (mute/skip) | enabled
Includes category-wide bulk toggles and a save button. The dialog mutates
the supplied FilterProfile in place and exposes it via `.profile`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox, QComboBox, QWidget,
)

from core.filter_engine import CATEGORIES
from core.profile import FilterProfile


_CATEGORY_COLORS = {
    "blasphemy": QColor(255, 240, 200),
    "vulgarity": QColor(255, 220, 220),
    "sexual":    QColor(255, 200, 220),
    "slurs":     QColor(220, 200, 255),
}


class ReviewDialog(QDialog):
    def __init__(self, profile: FilterProfile, video_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Review filters — {video_path.name}")
        self.setModal(True)
        self.resize(960, 600)
        self.profile = profile

        # ---- header ----
        summary = self._summary_text(profile)
        header = QLabel(summary)
        header.setWordWrap(True)

        # ---- bulk category toggles ----
        bulk_row = QHBoxLayout()
        bulk_row.addWidget(QLabel("Bulk:"))
        self._cat_checks: dict[str, QCheckBox] = {}
        for cat in CATEGORIES:
            cb = QCheckBox(cat)
            cb.setTristate(False)
            cb.setChecked(self._all_enabled_in(cat))
            cb.stateChanged.connect(lambda _state, c=cat: self._toggle_category(c))
            self._cat_checks[cat] = cb
            bulk_row.addWidget(cb)
        bulk_row.addStretch(1)

        # ---- table ----
        self._table = QTableWidget(len(profile.flags), 6)
        self._table.setHorizontalHeaderLabels(
            ["Time", "Category", "Word", "Context", "Action", "On"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        for col in (0, 1, 2, 4, 5):
            self._table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self._populate_table()

        # ---- buttons ----
        btn_save = QPushButton("Save && Play")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)

        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addLayout(bulk_row)
        layout.addWidget(self._table, stretch=1)
        layout.addLayout(btn_row)

    # ---------- population ----------

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self.profile.flags))
        for row, flag in enumerate(self.profile.flags):
            color = _CATEGORY_COLORS.get(flag.category)
            brush = QBrush(color) if color else None

            time_item = QTableWidgetItem(_fmt_time(flag.start_ms))
            time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
            cat_item = QTableWidgetItem(flag.category)
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsEditable)
            word_item = QTableWidgetItem(flag.word)
            word_item.setFlags(word_item.flags() & ~Qt.ItemIsEditable)
            ctx_item = QTableWidgetItem(flag.context)
            ctx_item.setFlags(ctx_item.flags() & ~Qt.ItemIsEditable)

            for it in (time_item, cat_item, word_item, ctx_item):
                if brush is not None:
                    it.setBackground(brush)

            self._table.setItem(row, 0, time_item)
            self._table.setItem(row, 1, cat_item)
            self._table.setItem(row, 2, word_item)
            self._table.setItem(row, 3, ctx_item)

            action_combo = QComboBox()
            action_combo.addItems(["mute", "skip"])
            action_combo.setCurrentText(flag.action)
            action_combo.currentTextChanged.connect(
                lambda val, r=row: self._set_action(r, val)
            )
            self._table.setCellWidget(row, 4, _wrap_widget(action_combo))

            cb = QCheckBox()
            cb.setChecked(flag.enabled)
            cb.stateChanged.connect(lambda _s, r=row, w=cb: self._set_enabled(r, w.isChecked()))
            self._table.setCellWidget(row, 5, _wrap_widget(cb, center=True))

    # ---------- behavior ----------

    def _set_enabled(self, row: int, enabled: bool) -> None:
        self.profile.flags[row].enabled = enabled
        # Refresh bulk checkbox without firing infinite signal loop.
        cat = self.profile.flags[row].category
        cb = self._cat_checks.get(cat)
        if cb is not None:
            cb.blockSignals(True)
            cb.setChecked(self._all_enabled_in(cat))
            cb.blockSignals(False)

    def _set_action(self, row: int, value: str) -> None:
        self.profile.flags[row].action = value

    def _toggle_category(self, category: str) -> None:
        cb = self._cat_checks[category]
        new_state = cb.isChecked()
        for row, flag in enumerate(self.profile.flags):
            if flag.category != category:
                continue
            flag.enabled = new_state
            cell = self._table.cellWidget(row, 5)
            if cell is None:
                continue
            inner = cell.findChild(QCheckBox)
            if inner is not None:
                inner.blockSignals(True)
                inner.setChecked(new_state)
                inner.blockSignals(False)

    def _all_enabled_in(self, category: str) -> bool:
        flags = [f for f in self.profile.flags if f.category == category]
        return bool(flags) and all(f.enabled for f in flags)

    def _summary_text(self, profile: FilterProfile) -> str:
        if not profile.flags:
            return ("<b>No flagged content was detected.</b><br>"
                    "If you expected hits, check that subtitles or transcription "
                    "ran successfully and that your wordlists contain the words "
                    "you care about.")
        counts: dict[str, int] = {c: 0 for c in CATEGORIES}
        for f in profile.flags:
            counts[f.category] = counts.get(f.category, 0) + 1
        parts = [f"<b>{n}</b> {c}" for c, n in counts.items() if n]
        return ("Found " + ", ".join(parts) +
                f". Toggle anything you want left in, then click "
                f"<b>Save &amp; Play</b>.")


# ---------- helpers ----------

def _fmt_time(ms: int) -> str:
    s, ms_ = divmod(ms, 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}.{ms_:03d}"
    return f"{m:d}:{s:02d}.{ms_:03d}"


def _wrap_widget(w, center: bool = False) -> QWidget:
    """Wrap a widget so it sits nicely inside a QTableWidget cell."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(4, 0, 4, 0)
    if center:
        layout.addStretch(1)
    layout.addWidget(w)
    if center:
        layout.addStretch(1)
    return container
