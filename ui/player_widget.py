"""VLC-backed video player widget with mute/skip scheduling.

The widget polls the current playback time every ~80 ms and consults the
profile's enabled flags. When playback enters a flag's padded range it either:
  * mutes the audio for the duration (action="mute"), or
  * seeks past the end of the range (action="skip").
When it leaves the range, audio is restored.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import vlc
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel,
    QFrame,
)

from core.profile import FilterProfile
from core.filter_engine import Flag


class PlayerWidget(QWidget):
    timeChanged = Signal(int)         # current playback ms
    durationChanged = Signal(int)
    stateChanged = Signal(str)        # "playing" / "paused" / "stopped"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._instance = vlc.Instance("--no-xlib") if sys.platform.startswith("linux") \
            else vlc.Instance()
        self._player = self._instance.media_player_new()

        # Video surface — a black widget VLC will paint into.
        self._video_frame = QFrame()
        self._video_frame.setFrameShape(QFrame.NoFrame)
        pal = self._video_frame.palette()
        pal.setColor(QPalette.Window, QColor(0, 0, 0))
        self._video_frame.setPalette(pal)
        self._video_frame.setAutoFillBackground(True)
        self._video_frame.setMinimumHeight(360)

        # Controls
        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedWidth(40)
        self._play_btn.clicked.connect(self.toggle_play)

        self._stop_btn = QPushButton("■")
        self._stop_btn.setFixedWidth(40)
        self._stop_btn.clicked.connect(self.stop)

        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setMinimumWidth(120)

        self._position_slider = QSlider(Qt.Horizontal)
        self._position_slider.setRange(0, 1000)
        self._position_slider.sliderMoved.connect(self._on_slider_moved)
        self._position_slider.sliderReleased.connect(self._on_slider_released)
        self._scrubbing = False

        self._sub_btn = QPushButton("CC")
        self._sub_btn.setFixedWidth(40)
        self._sub_btn.setCheckable(True)
        self._sub_btn.setChecked(True)
        self._sub_btn.setToolTip("Toggle subtitles")
        self._sub_btn.clicked.connect(self._toggle_subtitles)
        self._subs_enabled = True

        self._mute_indicator = QLabel("")
        self._mute_indicator.setStyleSheet(
            "color: white; background: #b00020; padding: 2px 8px; border-radius: 4px;"
        )
        self._mute_indicator.setVisible(False)

        controls = QHBoxLayout()
        controls.addWidget(self._play_btn)
        controls.addWidget(self._stop_btn)
        controls.addWidget(self._time_label)
        controls.addWidget(self._position_slider, stretch=1)
        controls.addWidget(self._mute_indicator)
        controls.addWidget(self._sub_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._video_frame, stretch=1)
        layout.addLayout(controls)

        # Filter scheduling state
        self._profile: Optional[FilterProfile] = None
        self._user_muted = False    # admin's manual mute (TODO: hook a button)
        self._filter_muted = False  # set when an active flag is muting
        self._active_flag: Optional[Flag] = None
        self._saved_volume: int = 100  # volume to restore after mute
        # VLC's reported time runs slightly ahead of speaker output, which
        # naturally gives us a small lead on muting. No artificial pre-roll needed.
        self._audio_preroll_ms: int = 0

        # Poll playback position
        self._poll = QTimer(self)
        self._poll.setInterval(80)
        self._poll.timeout.connect(self._tick)
        self._poll.start()

    # ---------- public API ----------

    def attach_video_surface(self) -> None:
        """Bind VLC's output to our video frame. Call after the widget is shown."""
        win_id = int(self._video_frame.winId())
        if sys.platform.startswith("win"):
            self._player.set_hwnd(win_id)
        elif sys.platform == "darwin":
            self._player.set_nsobject(win_id)
        else:
            self._player.set_xwindow(win_id)

    def load(self, video_path: Path, profile: Optional[FilterProfile]) -> None:
        media = self._instance.media_new(str(video_path))
        self._player.set_media(media)
        self._profile = profile
        self.attach_video_surface()
        # Parse media so duration is available (asynchronously, but quick).
        media.parse_with_options(vlc.MediaParseFlag.local, 2000)
        self.durationChanged.emit(self._duration_ms())
        self._update_time_label()

    def play(self) -> None:
        self._player.play()
        self._play_btn.setText("⏸")
        self.stateChanged.emit("playing")

    def pause(self) -> None:
        self._player.pause()
        self._play_btn.setText("▶")
        self.stateChanged.emit("paused")

    def stop(self) -> None:
        self._player.stop()
        self._play_btn.setText("▶")
        self._restore_audio()
        self.stateChanged.emit("stopped")

    def toggle_play(self) -> None:
        if self._player.is_playing():
            self.pause()
        else:
            self.play()

    def _toggle_subtitles(self) -> None:
        self._subs_enabled = self._sub_btn.isChecked()
        if self._subs_enabled:
            # Re-enable first subtitle track.
            count = self._player.video_get_spu_count()
            if count > 0:
                descs = self._player.video_get_spu_description()
                if descs and len(descs) > 1:
                    self._player.video_set_spu(descs[1][0])
        else:
            self._player.video_set_spu(-1)

    # ---------- internal ----------

    def _duration_ms(self) -> int:
        d = self._player.get_length()
        return max(0, int(d))

    def _current_ms(self) -> int:
        t = self._player.get_time()
        return max(0, int(t))

    def _on_slider_moved(self, value: int) -> None:
        self._scrubbing = True
        # Show the would-be time live in the label.
        dur = self._duration_ms()
        if dur > 0:
            target = int(dur * (value / 1000.0))
            self._time_label.setText(f"{_fmt(target)} / {_fmt(dur)}")

    def _on_slider_released(self) -> None:
        dur = self._duration_ms()
        if dur > 0:
            value = self._position_slider.value()
            self._player.set_time(int(dur * (value / 1000.0)))
        self._scrubbing = False

    def _tick(self) -> None:
        cur = self._current_ms()
        dur = self._duration_ms()
        if dur > 0 and not self._scrubbing:
            self._position_slider.blockSignals(True)
            self._position_slider.setValue(int(1000 * cur / dur))
            self._position_slider.blockSignals(False)
        self._update_time_label()
        self.timeChanged.emit(cur)
        self._apply_filters(cur)

    def _update_time_label(self) -> None:
        self._time_label.setText(f"{_fmt(self._current_ms())} / {_fmt(self._duration_ms())}")

    # ---------- filter scheduling ----------

    def _apply_filters(self, cur_ms: int) -> None:
        if self._profile is None:
            return
        if not self._player.is_playing():
            return
        # Look ahead to compensate for audio output buffer latency.
        check_ms = cur_ms + self._audio_preroll_ms
        active = self._find_active_flag(check_ms)
        if active is None:
            if self._filter_muted:
                self._restore_audio()
            self._active_flag = None
            return
        if active.action == "skip":
            s, e = active.padded(self._profile.padding_ms)
            self._player.set_time(int(e + 50))
            self._active_flag = None
        elif active is not self._active_flag:
            self._active_flag = active
            vol = self._player.audio_get_volume()
            if vol > 0:
                self._saved_volume = vol
            self._player.audio_set_volume(0)
            self._filter_muted = True
            self._mute_indicator.setText(f"MUTED ({active.category})")
            self._mute_indicator.setVisible(True)

    def _find_active_flag(self, cur_ms: int) -> Optional[Flag]:
        if self._profile is None:
            return None
        for f in self._profile.flags:
            if not f.enabled:
                continue
            s, e = f.padded(self._profile.padding_ms)
            if s <= cur_ms < e:
                return f
        return None

    def _restore_audio(self) -> None:
        if self._user_muted:
            return
        self._player.audio_set_volume(self._saved_volume)
        self._filter_muted = False
        self._mute_indicator.setVisible(False)

    # ---------- profile updates ----------

    def set_profile(self, profile: Optional[FilterProfile]) -> None:
        self._profile = profile


def _fmt(ms: int) -> str:
    if ms <= 0:
        return "0:00"
    s, _ = divmod(ms, 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
