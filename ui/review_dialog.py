"""Admin review dialog: searchable table of flags with on/off + action toggles.

Layout:
  +-------------------------------------------------------------+
  |  Header: "Found N flags across M categories"                |
  |  [card][card][card]  (one summary card per category w/ count)|
  |  [search] [bulk: cat1 cat2 cat3 ...]                        |
  |  +-------------------------------------------------------+  |
  |  | Time | Type | Category | Word | Context | Conf | Action | On |
  |  +-------------------------------------------------------+  |
  |  ... rows ...                                               |
  |                                                  [Cancel] [Save] |
  +-------------------------------------------------------------+
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core.filter_engine import ALL_CATEGORIES, Flag
from core.profile import FilterProfile
from . import icons


class ReviewDialog(QDialog):
    def __init__(self, profile: FilterProfile, video_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Review filters \u2014 {video_path.name}")
        self.setModal(True)
        self.resize(1080, 660)
        self.profile = profile

        # ---- header ----
        title = QLabel(self._title_html(profile))
        title.setWordWrap(True)
        title.setTextFormat(Qt.RichText)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)
        for cat in ALL_CATEGORIES:
            count = sum(1 for f in profile.flags if f.category == cat)
            if count == 0:
                continue
            cards_row.addWidget(_CategoryCard(cat, count))
        cards_row.addStretch(1)

        # ---- search + bulk ----
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search words / context\u2026")
        self._search.textChanged.connect(self._apply_filter_text)

        bulk_row = QHBoxLayout()
        bulk_row.addWidget(QLabel("Bulk:"))
        self._cat_checks: dict[str, QCheckBox] = {}
        present_cats = sorted({f.category for f in profile.flags})
        for cat in present_cats:
            cb = QCheckBox(cat)
            cb.setTristate(False)
            cb.setChecked(self._all_enabled_in(cat))
            cb.stateChanged.connect(lambda _s, c=cat: self._toggle_category(c))
            self._cat_checks[cat] = cb
            bulk_row.addWidget(cb)
        bulk_row.addStretch(1)

        search_row = QHBoxLayout()
        search_row.addWidget(self._search, stretch=1)

        # ---- table ----
        headers = ["Time", "Type", "Category", "Word", "Context", "Conf", "Action", "On"]
        self._table = QTableWidget(len(profile.flags), len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(4, QHeaderView.Stretch)  # Context
        for col in (0, 1, 2, 3, 5, 6, 7):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeToContents)

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
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addLayout(cards_row)
        layout.addLayout(search_row)
        layout.addLayout(bulk_row)
        layout.addWidget(self._table, stretch=1)
        layout.addLayout(btn_row)

    # ---------- title / cards ----------

    def _title_html(self, profile: FilterProfile) -> str:
        if not profile.flags:
            return ("<h3>No flagged content was detected.</h3>"
                    "<p>If you expected hits, check that subtitles or transcription "
                    "ran successfully and that your wordlists / LLM context are "
                    "configured the way you want.</p>")
        return (
            f"<h3 style='margin: 0;'>Found {len(profile.flags)} flag"
            f"{'s' if len(profile.flags) != 1 else ''}</h3>"
            "<p style='color:#b8c0cf; margin-top:2px;'>"
            "Toggle anything you want left in, then click <b>Save &amp; Play</b>.</p>"
        )

    # ---------- table population ----------

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self.profile.flags))
        for row, flag in enumerate(self.profile.flags):
            # Time
            time_item = QTableWidgetItem(_fmt_time(flag.start_ms))
            time_item.setData(Qt.UserRole, flag.start_ms)
            self._table.setItem(row, 0, time_item)

            # Type — audio / visual chip
            type_item = QTableWidgetItem(flag.flag_type)
            type_item.setForeground(
                QColor("#5eb1ff" if flag.flag_type == "audio" else "#ff8aa6")
            )
            type_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 1, type_item)

            # Category chip
            chip = _CategoryChip(flag.category)
            self._table.setCellWidget(row, 2, _wrap(chip, center=True))

            # Word
            word_item = QTableWidgetItem(flag.word)
            self._table.setItem(row, 3, word_item)

            # Context (with reason for LLM flags)
            ctx_text = flag.context
            if flag.reason and flag.source == "llm_context":
                ctx_text = f"{flag.context} \u2014 {flag.reason}"
            ctx_item = QTableWidgetItem(ctx_text)
            ctx_item.setToolTip(ctx_text)
            self._table.setItem(row, 4, ctx_item)

            # Confidence bar
            conf_widget = _ConfidenceBar(flag.confidence)
            self._table.setCellWidget(row, 5, _wrap(conf_widget, center=True))

            # Action combo
            action_combo = QComboBox()
            action_combo.addItems(["mute", "skip"])
            action_combo.setCurrentText(flag.action)
            # Visual flags must skip — disable the combo for them.
            if flag.flag_type == "visual":
                action_combo.setCurrentText("skip")
                action_combo.setEnabled(False)
                action_combo.setToolTip("Visual content can only be skipped.")
            action_combo.currentTextChanged.connect(
                lambda val, r=row: self._set_action(r, val)
            )
            self._table.setCellWidget(row, 6, _wrap(action_combo))

            # On/Off
            cb = QCheckBox()
            cb.setChecked(flag.enabled)
            cb.stateChanged.connect(
                lambda _s, r=row, w=cb: self._set_enabled(r, w.isChecked())
            )
            self._table.setCellWidget(row, 7, _wrap(cb, center=True))

    # ---------- behavior ----------

    def _apply_filter_text(self, query: str) -> None:
        q = query.strip().lower()
        for row, flag in enumerate(self.profile.flags):
            haystack = (
                f"{flag.word} {flag.context} {flag.category} {flag.reason}"
            ).lower()
            self._table.setRowHidden(row, bool(q) and q not in haystack)

    def _set_enabled(self, row: int, enabled: bool) -> None:
        self.profile.flags[row].enabled = enabled
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
            cell = self._table.cellWidget(row, 7)
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


# ---------- small composed widgets ----------

class _CategoryCard(QFrame):
    """Top-of-dialog summary chip with category + count."""
    def __init__(self, category: str, count: int) -> None:
        super().__init__()
        self.setFrameShape(QFrame.NoFrame)
        color = icons.category_color(category)
        self.setStyleSheet(
            f"background-color: {color}22; "
            f"border: 1px solid {color}66; "
            "border-radius: 8px; padding: 6px 10px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        cat_label = QLabel(category.replace("_", " "))
        cat_label.setStyleSheet(f"color: {color}; font-weight: 600;")

        count_label = QLabel(str(count))
        count_label.setStyleSheet("color: #ffffff; font-weight: 700;")

        layout.addWidget(cat_label)
        layout.addWidget(count_label)


class _CategoryChip(QLabel):
    def __init__(self, category: str) -> None:
        super().__init__(category.replace("_", " "))
        color = icons.category_color(category)
        self.setStyleSheet(
            f"background-color: {color}; color: white; "
            "border-radius: 9px; padding: 2px 10px; font-weight: 600;"
        )
        self.setAlignment(Qt.AlignCenter)


class _ConfidenceBar(QWidget):
    """Horizontal bar showing 0..1 confidence; '\u2014' for None."""
    def __init__(self, value: float | None) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if value is None:
            lbl = QLabel("\u2014")
            lbl.setStyleSheet("color: #5d6675;")
            lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl)
            return
        v = max(0.0, min(1.0, float(value)))
        track = QFrame()
        track.setObjectName("confidenceBar")
        track.setFixedSize(80, 6)
        track.setStyleSheet(
            "background-color: #2c313a; border-radius: 3px;"
        )
        fill = QFrame(track)
        fill.setGeometry(0, 0, int(80 * v), 6)
        fill.setStyleSheet(
            f"background-color: {_conf_color(v)}; border-radius: 3px;"
        )
        wrap = QHBoxLayout()
        wrap.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(track)
        pct = QLabel(f"{int(v * 100)}%")
        pct.setStyleSheet("color: #b8c0cf; min-width: 32px;")
        layout.addWidget(pct)


def _conf_color(v: float) -> str:
    if v >= 0.85:
        return "#e63946"
    if v >= 0.7:
        return "#f4a261"
    return "#4e83e8"


def _wrap(w, center: bool = False) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(4, 0, 4, 0)
    if center:
        layout.addStretch(1)
    layout.addWidget(w)
    if center:
        layout.addStretch(1)
    return container


def _fmt_time(ms: int) -> str:
    s, ms_ = divmod(ms, 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}.{ms_:03d}"
    return f"{m:d}:{s:02d}.{ms_:03d}"
