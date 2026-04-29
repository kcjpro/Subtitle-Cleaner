"""mpv-backed video player widget with mute/skip scheduling.

Replaces the older VLC implementation. mpv gives us:
  * Frame-accurate seeks (`seek <time> exact`)
  * Sub-frame `time-pos` property updates pushed on every frame
  * Buffer-aware muting via the `mute` property
  * Better embedded-subtitle handling

Filter scheduling is *reactive* via a property observer (no polling QTimer)
plus *predictive* via single-shot QTimers for the next entry/exit. The two
together give us very tight muting latency without busy-waiting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QObject, Signal, Slot
from PySide6.QtGui import QPalette, QColor, QMouseEvent
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSlider, QToolButton,
    QVBoxLayout, QWidget,
)

from core import paths
from core.profile import FilterProfile
from core.filter_engine import Flag
from . import icons

# python-mpv looks for libmpv on the loader path; make sure our bundled
# copy is discoverable before we import the binding.
paths.setup_mpv_dll_path()

try:
    import mpv  # type: ignore
    _MPV_AVAILABLE = True
    _MPV_IMPORT_ERROR: Optional[Exception] = None
except Exception as e:  # noqa: BLE001
    mpv = None  # type: ignore
    _MPV_AVAILABLE = False
    _MPV_IMPORT_ERROR = e


class _MpvBridge(QObject):
    """Marshal property updates from mpv's thread to the Qt main thread."""
    timePosUpdated = Signal(float)
    durationUpdated = Signal(float)
    pauseUpdated = Signal(bool)
    seekingUpdated = Signal(bool)
    eofReached = Signal()


class PlayerWidget(QWidget):
    timeChanged = Signal(int)         # current playback ms
    durationChanged = Signal(int)
    stateChanged = Signal(str)        # "playing" / "paused" / "stopped"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Black canvas mpv will paint into.
        self._video_frame = QFrame()
        self._video_frame.setFrameShape(QFrame.NoFrame)
        pal = self._video_frame.palette()
        pal.setColor(QPalette.Window, QColor(0, 0, 0))
        self._video_frame.setPalette(pal)
        self._video_frame.setAutoFillBackground(True)
        self._video_frame.setMinimumHeight(360)

        self._build_controls()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._video_frame, stretch=1)
        layout.addLayout(self._controls_layout)

        # Filter scheduling state.
        self._profile: Optional[FilterProfile] = None
        self._user_muted = False
        self._filter_muted = False
        self._active_flag: Optional[Flag] = None
        self._saved_volume: int = 100
        self._duration_cached_ms: int = 0
        self._cur_ms_cached: int = 0

        # Pending QTimer for the next anticipated flag transition. We always
        # cancel and re-arm this on every position update.
        self._next_event_timer: Optional[QTimer] = None

        # mpv lives here once attached.
        self._player: Optional["mpv.MPV"] = None
        self._bridge = _MpvBridge()
        self._bridge.timePosUpdated.connect(self._on_time_pos)
        self._bridge.durationUpdated.connect(self._on_duration)
        self._bridge.pauseUpdated.connect(self._on_pause)
        self._bridge.eofReached.connect(self._on_eof)

        # Lightweight UI tick (label + slider) — purely cosmetic, not used
        # for filter scheduling.
        self._ui_tick = QTimer(self)
        self._ui_tick.setInterval(120)
        self._ui_tick.timeout.connect(self._refresh_ui)
        self._ui_tick.start()

    # ---------- construction helpers ----------

    def _build_controls(self) -> None:
        self._play_btn = QToolButton()
        self._play_btn.setIcon(icons.play())
        self._play_btn.setText("Play")
        self._play_btn.setToolTip("Play / Pause (Space)")
        self._play_btn.setAutoRaise(True)
        self._play_btn.setFixedSize(40, 36)
        self._play_btn.clicked.connect(self.toggle_play)

        self._stop_btn = QToolButton()
        self._stop_btn.setIcon(icons.stop())
        self._stop_btn.setToolTip("Stop")
        self._stop_btn.setAutoRaise(True)
        self._stop_btn.setFixedSize(40, 36)
        self._stop_btn.clicked.connect(self.stop)

        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setMinimumWidth(120)
        self._time_label.setStyleSheet("color: #b8c0cf;")

        self._position_slider = _HoverSlider(Qt.Horizontal)
        self._position_slider.setRange(0, 10000)
        self._position_slider.sliderMoved.connect(self._on_slider_moved)
        self._position_slider.sliderReleased.connect(self._on_slider_released)
        self._position_slider.hoveredAt.connect(self._on_slider_hover)
        self._scrubbing = False

        self._sub_btn = QToolButton()
        self._sub_btn.setIcon(icons.cc_on())
        self._sub_btn.setCheckable(True)
        self._sub_btn.setChecked(True)
        self._sub_btn.setAutoRaise(True)
        self._sub_btn.setFixedSize(40, 36)
        self._sub_btn.setToolTip("Toggle subtitles")
        self._sub_btn.clicked.connect(self._toggle_subtitles)
        self._subs_enabled = True

        self._volume_slider = QSlider(Qt.Horizontal)
        self._volume_slider.setRange(0, 150)
        self._volume_slider.setValue(100)
        self._volume_slider.setFixedWidth(110)
        self._volume_slider.setToolTip("Volume")
        self._volume_slider.valueChanged.connect(self._on_volume_changed)

        self._mute_indicator = QLabel("")
        self._mute_indicator.setObjectName("muteIndicator")
        self._mute_indicator.setVisible(False)

        self._controls_layout = QHBoxLayout()
        self._controls_layout.setContentsMargins(8, 6, 8, 6)
        self._controls_layout.setSpacing(8)
        self._controls_layout.addWidget(self._play_btn)
        self._controls_layout.addWidget(self._stop_btn)
        self._controls_layout.addWidget(self._time_label)
        self._controls_layout.addWidget(self._position_slider, stretch=1)
        self._controls_layout.addWidget(self._mute_indicator)
        self._controls_layout.addWidget(self._sub_btn)
        self._controls_layout.addWidget(self._volume_slider)

    # ---------- public API ----------

    def attach_video_surface(self) -> None:
        """Bind the mpv video output to our embedded QFrame.

        Must be called after the widget is shown, since we need a real winId.
        Safe to call repeatedly.
        """
        if self._player is not None:
            return
        if not _MPV_AVAILABLE:
            err = _MPV_IMPORT_ERROR
            raise RuntimeError(
                "python-mpv could not be loaded. Install libmpv-2.dll into the "
                "app's bin/ folder or onto PATH. Original error: "
                f"{type(err).__name__}: {err}" if err else "python-mpv not installed."
            )
        wid = int(self._video_frame.winId())
        # `wid` must be passed as a string for embedding to work.
        self._player = mpv.MPV(
            wid=str(wid),
            input_default_bindings=False,
            input_vo_keyboard=False,
            osc=False,
            keep_open="yes",
            hr_seek="yes",
            log_handler=lambda *_a, **_kw: None,
        )

        # Property observers — mpv calls these from its event thread, so we
        # bounce through Qt signals into the GUI thread.
        @self._player.property_observer("time-pos")
        def _tp(_name, value):
            if value is not None:
                self._bridge.timePosUpdated.emit(float(value))

        @self._player.property_observer("duration")
        def _du(_name, value):
            if value is not None:
                self._bridge.durationUpdated.emit(float(value))

        @self._player.property_observer("pause")
        def _pa(_name, value):
            self._bridge.pauseUpdated.emit(bool(value))

        @self._player.property_observer("eof-reached")
        def _eo(_name, value):
            if value:
                self._bridge.eofReached.emit()

    def load(self, video_path: Path, profile: Optional[FilterProfile]) -> None:
        self.attach_video_surface()
        assert self._player is not None
        self._profile = profile
        self._duration_cached_ms = 0
        self._cur_ms_cached = 0
        self._cancel_pending_event()
        self._restore_audio()
        self._active_flag = None
        self._player.command("loadfile", str(video_path), "replace")
        self._player.pause = True
        self.durationChanged.emit(0)
        self._update_time_label()

    def play(self) -> None:
        if self._player is None:
            return
        self._player.pause = False
        self._play_btn.setIcon(icons.pause())
        self.stateChanged.emit("playing")

    def pause(self) -> None:
        if self._player is None:
            return
        self._player.pause = True
        self._play_btn.setIcon(icons.play())
        self.stateChanged.emit("paused")

    def stop(self) -> None:
        if self._player is None:
            return
        self._cancel_pending_event()
        self._player.command("stop")
        self._play_btn.setIcon(icons.play())
        self._restore_audio()
        self.stateChanged.emit("stopped")

    def toggle_play(self) -> None:
        if self._player is None:
            return
        if bool(self._player.pause):
            self.play()
        else:
            self.pause()

    def shutdown(self) -> None:
        """Cleanly destroy the mpv instance. Call from MainWindow.closeEvent."""
        try:
            if self._player is not None:
                self._player.terminate()
        except Exception:
            pass
        self._player = None

    # ---------- filter / profile API ----------

    def set_profile(self, profile: Optional[FilterProfile]) -> None:
        self._profile = profile
        self._cancel_pending_event()
        self._restore_audio()
        self._active_flag = None
        # Force a re-evaluation at the current position.
        if self._cur_ms_cached:
            self._evaluate(self._cur_ms_cached)

    # ---------- subtitle toggle ----------

    def _toggle_subtitles(self) -> None:
        if self._player is None:
            return
        self._subs_enabled = self._sub_btn.isChecked()
        self._sub_btn.setIcon(icons.cc_on() if self._subs_enabled else icons.cc_off())
        try:
            if self._subs_enabled:
                self._player.sub_visibility = True
                if not self._player.sid or self._player.sid in (False, "no"):
                    track_list = getattr(self._player, "track_list", []) or []
                    for t in track_list:
                        if t.get("type") == "sub":
                            self._player.sid = t.get("id")
                            break
            else:
                self._player.sub_visibility = False
        except Exception:
            pass

    # ---------- bridge handlers ----------

    @Slot(float)
    def _on_time_pos(self, seconds: float) -> None:
        ms = max(0, int(seconds * 1000))
        self._cur_ms_cached = ms
        self.timeChanged.emit(ms)
        self._evaluate(ms)

    @Slot(float)
    def _on_duration(self, seconds: float) -> None:
        ms = max(0, int(seconds * 1000))
        self._duration_cached_ms = ms
        self.durationChanged.emit(ms)

    @Slot(bool)
    def _on_pause(self, paused: bool) -> None:
        self._play_btn.setIcon(icons.play() if paused else icons.pause())
        self.stateChanged.emit("paused" if paused else "playing")
        if paused:
            self._cancel_pending_event()

    @Slot()
    def _on_eof(self) -> None:
        self._cancel_pending_event()
        self._restore_audio()
        self._active_flag = None
        self.stateChanged.emit("stopped")

    # ---------- slider ----------

    def _on_slider_moved(self, value: int) -> None:
        self._scrubbing = True
        if self._duration_cached_ms > 0:
            target = int(self._duration_cached_ms * (value / 10000.0))
            self._time_label.setText(f"{_fmt(target)} / {_fmt(self._duration_cached_ms)}")

    def _on_slider_released(self) -> None:
        if self._player is None or self._duration_cached_ms <= 0:
            self._scrubbing = False
            return
        value = self._position_slider.value()
        target_s = (self._duration_cached_ms * (value / 10000.0)) / 1000.0
        self._cancel_pending_event()
        self._restore_audio()
        self._active_flag = None
        try:
            self._player.command("seek", target_s, "absolute", "exact")
        except Exception:
            pass
        self._scrubbing = False

    @Slot(int, int)
    def _on_slider_hover(self, x_px: int, value: int) -> None:
        """Show a hover tooltip at the cursor with the would-be timestamp."""
        if self._duration_cached_ms <= 0:
            return
        target = int(self._duration_cached_ms * (value / 10000.0))
        from PySide6.QtGui import QCursor
        from PySide6.QtWidgets import QToolTip
        QToolTip.showText(QCursor.pos(), _fmt(target), self._position_slider)

    def _on_volume_changed(self, value: int) -> None:
        if self._player is None or self._filter_muted:
            return
        try:
            self._player.volume = int(value)
        except Exception:
            pass
        self._saved_volume = int(value)

    # ---------- ui refresh ----------

    def _refresh_ui(self) -> None:
        if self._scrubbing:
            return
        cur = self._cur_ms_cached
        dur = self._duration_cached_ms
        if dur > 0:
            self._position_slider.blockSignals(True)
            self._position_slider.setValue(int(10000 * cur / dur))
            self._position_slider.blockSignals(False)
        self._update_time_label()

    def _update_time_label(self) -> None:
        self._time_label.setText(
            f"{_fmt(self._cur_ms_cached)} / {_fmt(self._duration_cached_ms)}"
        )

    # ---------- filter scheduling ----------

    def _evaluate(self, cur_ms: int) -> None:
        """Apply mute/skip state for the current position and arm the next timer."""
        if self._profile is None or self._player is None:
            return
        active = self._find_active_flag(cur_ms)
        if active is None:
            if self._filter_muted:
                self._restore_audio()
            self._active_flag = None
            self._arm_next_timer(cur_ms)
            return
        # Visual flags ALWAYS skip the video — muting wouldn't help since the
        # nudity/violence is on screen, not in the audio.
        is_skip = active.action == "skip" or active.flag_type == "visual"
        if is_skip:
            _, e = active.padded(self._profile.padding_ms)
            try:
                self._player.command("seek", (e + 50) / 1000.0, "absolute", "exact")
            except Exception:
                pass
            self._active_flag = None
            return
        # Mute path.
        if active is not self._active_flag:
            self._enter_flag(active)
        # Always arm a timer for the unmute moment so we don't depend on the
        # next time-pos tick (which can lag).
        self._arm_unmute_timer(active)

    def _enter_flag(self, flag: Flag) -> None:
        if self._player is None or self._profile is None:
            return
        self._active_flag = flag
        try:
            cur_vol = int(self._player.volume or 0)
        except Exception:
            cur_vol = 100
        if cur_vol > 0:
            self._saved_volume = cur_vol
        try:
            self._player.mute = True
        except Exception:
            pass
        self._filter_muted = True
        self._mute_indicator.setText(f"MUTED ({flag.category})")
        self._mute_indicator.setVisible(True)

    def _restore_audio(self) -> None:
        if self._user_muted or self._player is None:
            return
        try:
            self._player.mute = False
        except Exception:
            pass
        self._filter_muted = False
        self._mute_indicator.setVisible(False)

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

    def _next_flag_after(self, cur_ms: int) -> Optional[Flag]:
        if self._profile is None:
            return None
        candidates = []
        for f in self._profile.flags:
            if not f.enabled:
                continue
            s, _ = f.padded(self._profile.padding_ms)
            if s > cur_ms:
                candidates.append((s, f))
        if not candidates:
            return None
        candidates.sort(key=lambda t: t[0])
        return candidates[0][1]

    def _arm_next_timer(self, cur_ms: int) -> None:
        """Schedule a single-shot QTimer to fire when the next flag begins.

        QTimer runs on real (wall-clock) time, so this is only a tight
        approximation while playback rate stays at 1.0x and the user doesn't
        seek. The time-pos observer also updates on every frame, so this is
        belt-and-suspenders.
        """
        self._cancel_pending_event()
        if self._profile is None or self._player is None:
            return
        try:
            paused = bool(self._player.pause)
        except Exception:
            paused = False
        if paused:
            return
        nxt = self._next_flag_after(cur_ms)
        if nxt is None:
            return
        s, _ = nxt.padded(self._profile.padding_ms)
        delay = max(0, s - cur_ms - 30)  # 30ms lead so we mute slightly early
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda f=nxt: self._on_anticipated_flag(f))
        timer.start(delay)
        self._next_event_timer = timer

    def _arm_unmute_timer(self, active: Flag) -> None:
        if self._player is None or self._profile is None:
            return
        _, e = active.padded(self._profile.padding_ms)
        cur = self._cur_ms_cached
        delay = max(0, e - cur)
        if self._next_event_timer is not None:
            self._next_event_timer.stop()
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._evaluate(self._cur_ms_cached))
        timer.start(delay + 5)
        self._next_event_timer = timer

    def _on_anticipated_flag(self, flag: Flag) -> None:
        """Fired by a pre-scheduled QTimer at the predicted entry moment."""
        if self._player is None or self._profile is None:
            return
        try:
            paused = bool(self._player.pause)
        except Exception:
            paused = False
        if paused:
            return
        self._evaluate(self._cur_ms_cached)

    def _cancel_pending_event(self) -> None:
        if self._next_event_timer is not None:
            try:
                self._next_event_timer.stop()
                self._next_event_timer.deleteLater()
            except Exception:
                pass
            self._next_event_timer = None


def _fmt(ms: int) -> str:
    if ms <= 0:
        return "0:00"
    s, _ = divmod(ms, 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class _HoverSlider(QSlider):
    """A QSlider that emits the slider value at the current cursor position
    on every mouse-move, plus jumps to the click position on a single press
    (default Qt behavior is to step toward the click)."""

    hoveredAt = Signal(int, int)  # cursor x in px, slider value

    def __init__(self, orientation, parent=None) -> None:
        super().__init__(orientation, parent)
        self.setMouseTracking(True)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton and self.orientation() == Qt.Horizontal:
            value = self._value_at(event.position().x())
            self.setValue(value)
            self.sliderMoved.emit(value)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self.orientation() == Qt.Horizontal:
            value = self._value_at(event.position().x())
            self.hoveredAt.emit(int(event.position().x()), value)
        super().mouseMoveEvent(event)

    def _value_at(self, x: float) -> int:
        if self.width() <= 0:
            return self.value()
        frac = max(0.0, min(1.0, x / float(self.width())))
        span = self.maximum() - self.minimum()
        return int(self.minimum() + frac * span)
