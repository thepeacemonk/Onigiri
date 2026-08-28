"""
Pomodoro — a minimal floating focus-timer island plus a stats dashboard.

The countdown lives in PomodoroTimer, a QObject singleton independent of any
window, so it keeps running while the floating island is closed. Settings and
completed-session history live in mw.col.conf (mirrors Prep Station's plan
storage), so they sync via AnkiWeb. They are also mirrored to
user_files/pomodoro/ (mirrors Hashi Notes' pattern), so they are safe on disk
too and ride the existing Onigiri media-zip sync (sync.py).
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone

from aqt import mw
from aqt.qt import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QIcon,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPainter,
    QPixmap,
    QPushButton,
    Qt,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import QLocale, QObject, QPoint, QRect, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFontDatabase, QPainterPath, QPen
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene

from . import config
from . import safe_storage
from .onigiri_notifications import notify as tooltip
from .prep_station_ui import WeeklyChart, render_icon_pixmap
from .translations import current_locale, tr

SETTINGS_CONF_KEY = "onigiri_pomodoro_settings"
SESSIONS_CONF_KEY = "onigiri_pomodoro_sessions"
MAX_HISTORY = 500
SOUNDS_SUBDIR = "pomodoro_sounds"
DEFAULT_ICON = "system:pomodoro.svg"

# Island size presets. "small" reproduces the original hard-coded island
# exactly; "medium"/"big" scale the same shell up and switch on extra rows
# ("progress" bar, "meta" line, "stats" tiles) - see PomodoroIslandView._build.
SIZE_PRESETS = {
    "small": {
        "window": (230, 200),
        "pad": (14, 10, 14, 14),
        "spacing": 8,
        "radius": 18,
        "topbar_h": 26,
        "icon": 16,
        "chip": 22,
        "phase_px": 11,
        "time_px": 40,
        "dot": 13,
        "btn": 30,
        "play": 38,
        "rows": (),
    },
    "medium": {
        "window": (270, 264),
        "pad": (16, 12, 16, 16),
        "spacing": 9,
        "radius": 20,
        "topbar_h": 28,
        "icon": 17,
        "chip": 24,
        "phase_px": 11,
        "time_px": 48,
        "dot": 14,
        "btn": 32,
        "play": 42,
        "rows": ("progress", "meta"),
    },
    "big": {
        "window": (330, 372),
        "pad": (20, 14, 20, 20),
        "spacing": 11,
        "radius": 24,
        "topbar_h": 30,
        "icon": 19,
        "chip": 26,
        "phase_px": 12,
        "time_px": 60,
        "dot": 16,
        "btn": 36,
        "play": 48,
        "rows": ("progress", "meta", "stats"),
    },
}
DEFAULT_SIZE = "small"

DEFAULT_SETTINGS = {
    "focus_minutes": 25,
    "short_break_minutes": 5,
    "long_break_minutes": 15,
    "sessions_until_long_break": 4,
    # When True (default), the next phase begins running automatically the
    # moment the current one ends. When False, the next phase is prepared but
    # left paused so the user must press play to continue (see _advance).
    "auto_start_next_phase": True,
    "icon": DEFAULT_ICON,
    "font_key": "system",
    # "small" (default) / "medium" / "big" - see SIZE_PRESETS.
    "size": DEFAULT_SIZE,
    "sound_enabled": True,
    "sound_file": "",
    # When True, the shell/accent/digits/icon roles switch between the
    # "light" and "dark" color sets automatically with Anki's theme. When
    # False, the "light" set is used everywhere (see _palette).
    "dynamic_mode": True,
    # 0-100: alpha transparency of the shell background.
    "shell_opacity": 100,
    # 0-100: real blur radius applied to a live capture of whatever is
    # behind the floating island (see PomodoroWidget._refresh_shell_backdrop
    # / blur_pixmap) - refreshed on open and continuously while dragging.
    "shell_blur": 0,
    # Empty string = inherit the built-in default for that role/mode (see
    # _palette); a non-empty hex means the user explicitly overrode it.
    "colors": {
        "light": {"shell": "", "accent": "", "digits": "", "icon": ""},
        "dark": {"shell": "", "accent": "", "digits": "", "icon": ""},
    },
}

_widget = None
_stats_dialog = None
_timer = None
_font_family_cache = {}


# ─── Small utilities (mirrors hashi_notes.py's helpers) ───────────────────────

def _addon_root():
    return os.path.dirname(__file__)


def _system_icon_path(filename):
    return os.path.join(_addon_root(), "system_files", "system_icons", "unavailable_for_users", filename)


def _tinted_icon(path, color, size=16):
    try:
        with open(path, "r", encoding="utf-8") as f:
            svg_xml = f.read().replace("currentColor", color)
        renderer = QSvgRenderer(svg_xml.encode("utf-8"))
        pixmap = QPixmap(size * 2, size * 2)
        pixmap.setDevicePixelRatio(2.0)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        return QIcon(pixmap)
    except Exception:
        return QIcon(path)


def _is_dark_mode(conf=None):
    try:
        from .config import effective_night_mode

        return effective_night_mode(conf or config.get_config())
    except Exception:
        return False


def _accent_color(conf=None):
    conf = conf or config.get_config()
    mode = "dark" if _is_dark_mode(conf) else "light"
    return conf.get("colors", {}).get(mode, {}).get("--accent-color", "#00A982")


def base_chrome_palette(dark):
    accent = _accent_color()
    if dark:
        return {
            "shell": "#1f1f1f", "surface": "#2a2a2a", "border": "#343434",
            "fg": "#f4f4f5", "fg2": "#b6b6b8", "fg3": "#7c7c80",
            "hover": "#343434", "accent": accent,
        }
    return {
        "shell": "#ffffff", "surface": "#f1f1f0", "border": "#e5e7eb",
        "fg": "#1f2933", "fg2": "#4b5563", "fg3": "#8a9099",
        "hover": "#f1f3f5", "accent": accent,
    }


def _palette(dark, settings=None):
    """Chrome colors (surfaces/borders/secondary text) stay fixed per theme;
    shell/accent/digits/icon are the four user-customizable roles (Settings ->
    Pomodoro -> Appearance) and fall back to the chrome defaults when the
    user hasn't overridden them (empty string = inherit). When Dynamic Mode
    is off, the "light" set is used regardless of the real theme."""
    base = base_chrome_palette(dark)
    settings = settings if settings is not None else get_settings()
    dynamic = settings.get("dynamic_mode", True)
    mode = "dark" if (dark and dynamic) else "light"
    custom = ((settings.get("colors") or {}).get(mode) or {})
    base["shell"] = custom.get("shell") or base["shell"]
    base["accent"] = custom.get("accent") or base["accent"]
    base["digits"] = custom.get("digits") or base["fg"]
    base["icon"] = custom.get("icon") or base["fg2"]
    return base


def shell_alpha_color(hex_color, opacity_pct):
    """Plain alpha transparency, no tint blending - used by the Settings
    preview, which blurs an actual (stand-in) backdrop layer behind the
    shell instead of approximating blur through color."""
    color = QColor(hex_color)
    if not color.isValid():
        color = QColor("#ffffff")
    a = round(255 * max(0.0, min(1.0, opacity_pct / 100.0)))
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {a})"


def shell_alpha_qcolor(hex_color, opacity_pct):
    """Same as shell_alpha_color but returns a QColor for custom painting
    (the real floating shell's paintEvent) instead of a CSS rgba() string."""
    color = QColor(hex_color)
    if not color.isValid():
        color = QColor("#ffffff")
    color.setAlpha(round(255 * max(0.0, min(1.0, opacity_pct / 100.0))))
    return color


def blur_pixmap(pixmap, radius):
    """Bakes a Gaussian blur into an offscreen copy of pixmap via a throwaway
    QGraphicsScene (QGraphicsBlurEffect only applies live to on-screen
    widgets/items, not to a QPixmap directly)."""
    if pixmap is None or pixmap.isNull() or radius <= 0:
        return pixmap
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(pixmap)
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(radius)
    item.setGraphicsEffect(effect)
    scene.addItem(item)

    result = QPixmap(pixmap.size())
    result.setDevicePixelRatio(pixmap.devicePixelRatio())
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    target_rect = QRectF(0, 0, pixmap.width(), pixmap.height())
    scene.render(painter, target_rect, target_rect)
    painter.end()
    return result


def get_preset(settings):
    """Layout metrics for the island size chosen in Settings -> Pomodoro ->
    Appearance. Both the real floating island and the Settings preview build
    themselves from this same dict (see PomodoroIslandView)."""
    key = (settings or {}).get("size") or DEFAULT_SIZE
    return SIZE_PRESETS.get(key, SIZE_PRESETS[DEFAULT_SIZE])


def format_minutes(total_minutes):
    h, m = divmod(int(round(total_minutes)), 60)
    return f"{h}h {m}m" if h else f"{m}m"


def session_stats(sessions=None):
    """Aggregates used by the medium/big island's extra rows."""
    sessions = get_sessions() if sessions is None else sessions
    today = date.today().isoformat()
    minutes_today = sum(s.get("actual_minutes", 0) for s in sessions if s.get("date") == today)
    count_today = sum(1 for s in sessions if s.get("date") == today)
    days = {s.get("date") for s in sessions if s.get("date")}
    streak = 0
    cursor = date.today()
    while cursor.isoformat() in days:
        streak += 1
        cursor -= timedelta(days=1)
    return {
        "minutes_today": minutes_today,
        "count_today": count_today,
        "streak": streak,
        "total_minutes": sum(s.get("actual_minutes", 0) for s in sessions),
    }


def _resolve_font_family(font_key):
    """Registers a bundled/user .ttf with Qt and returns its family name for
    use in native QSS (font-family:). Mirrors prep_station_ui.py's
    small_title_font_css() registration recipe. None means "system default"."""
    if not font_key or font_key == "system":
        return None
    if font_key in _font_family_cache:
        return _font_family_cache[font_key]
    family = None
    try:
        from .fonts import get_all_fonts

        info = get_all_fonts(_addon_root()).get(font_key)
        if info and info.get("file"):
            if info.get("user"):
                font_path = os.path.join(_addon_root(), "user_files", "fonts", info["file"])
            else:
                font_path = os.path.join(_addon_root(), "system_files", "fonts", "system_fonts", info["file"])
            if os.path.exists(font_path):
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    if families:
                        family = families[0]
    except Exception:
        family = None
    _font_family_cache[font_key] = family
    return family


def _sounds_dir():
    path = os.path.join(_addon_root(), "user_files", SOUNDS_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


def _default_chime_path():
    return os.path.join(_addon_root(), "system_files", "sounds", "pomodoro_chime.wav")


def _resolve_sound_path(settings):
    sound_file = (settings.get("sound_file") or "").strip()
    if sound_file:
        candidate = os.path.join(_sounds_dir(), sound_file)
        if os.path.exists(candidate):
            return candidate
    return _default_chime_path()


def import_sound_file(source_path):
    """Copies a user-picked audio file into user_files/pomodoro_sounds/ (so it
    rides the addon's media-zip sync, like Hashi Notes' note JSON mirrors) and
    returns the stored filename."""
    os.makedirs(_sounds_dir(), exist_ok=True)
    ext = os.path.splitext(source_path)[1].lower() or ".mp3"
    filename = f"{uuid.uuid4().hex}{ext}"
    shutil.copy(source_path, os.path.join(_sounds_dir(), filename))
    return filename


def _play_sound(settings):
    if not settings.get("sound_enabled", True):
        return
    path = _resolve_sound_path(settings)
    if not path or not os.path.exists(path):
        return
    try:
        from anki.sound import SoundOrVideoTag
        from aqt.sound import av_player

        av_player.play_tags([SoundOrVideoTag(filename=path)])
    except Exception as e:
        print(f"Pomodoro: sound playback error: {e}")


def play_test_sound(sound_file=None):
    """Plays the given (or currently saved) sound regardless of the
    sound_enabled toggle - used by the Settings page's "Test Sound" button."""
    settings = dict(get_settings())
    settings["sound_enabled"] = True
    if sound_file is not None:
        settings["sound_file"] = sound_file
    _play_sound(settings)


def _position_centered(dialog, anchor=None):
    from aqt.qt import QApplication

    screen = None
    try:
        if anchor is not None:
            screen = anchor.window().screen()
    except Exception:
        screen = None
    if screen is None:
        screen = dialog.screen() or (QApplication.instance() and QApplication.instance().primaryScreen())
    if screen is None:
        return
    avail = screen.availableGeometry()
    x = avail.left() + (avail.width() - dialog.width()) // 2
    y = avail.top() + (avail.height() - dialog.height()) // 2
    dialog.move(x, y)


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ─── Persistence ────────────────────────────────────────────────────────────

def _default_settings():
    import copy

    return copy.deepcopy(DEFAULT_SETTINGS)


def get_settings():
    if not mw or not mw.col:
        return _default_settings()
    try:
        saved = mw.col.conf.get(SETTINGS_CONF_KEY, {}) or {}
        merged = _default_settings()
        merged.update(saved)
        merged_colors = merged["colors"]
        saved_colors = saved.get("colors") or {}
        for mode in ("light", "dark"):
            merged_colors[mode].update(saved_colors.get(mode) or {})
        return merged
    except Exception:
        return _default_settings()


def save_settings(settings):
    if not mw or not mw.col:
        return
    try:
        mw.col.conf[SETTINGS_CONF_KEY] = settings
        mw.col.setMod()
    except Exception as e:
        print(f"Pomodoro: settings save error: {e}")
    _write_json_mirror("settings.json", settings)


def get_sessions():
    if not mw or not mw.col:
        return []
    try:
        return list(mw.col.conf.get(SESSIONS_CONF_KEY, []))
    except Exception:
        return []


def _log_session(started_at, planned_minutes, actual_minutes):
    sessions = get_sessions()
    sessions.append({
        "id": str(uuid.uuid4()),
        "date": date.today().isoformat(),
        "started_at": started_at,
        "completed_at": _now_iso(),
        "planned_minutes": planned_minutes,
        "actual_minutes": round(actual_minutes, 2),
        "type": "focus",
    })
    sessions = sessions[-MAX_HISTORY:]
    if not mw or not mw.col:
        return
    try:
        mw.col.conf[SESSIONS_CONF_KEY] = sessions
        mw.col.setMod()
    except Exception as e:
        print(f"Pomodoro: session log error: {e}")
    _write_json_mirror("sessions.json", sessions)


# ─── Persistence: user_files JSON mirror ──────────────────────────────────────

def _mirror_dir():
    path = os.path.join(_addon_root(), "user_files", "pomodoro")
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


def _write_json_mirror(filename, data):
    try:
        path = os.path.join(_mirror_dir(), filename)
        safe_storage.atomic_write_json(path, data)
    except Exception as e:
        print(f"Pomodoro: mirror write error: {e}")


# ─── Timer state machine (window-independent singleton) ───────────────────────

class PomodoroTimer(QObject):
    tick = pyqtSignal()
    phase_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self.session_type = "focus"
        self.focus_count = 0
        self._phase_started_at = None
        self.running = False
        self.remaining_seconds = self.phase_length_seconds()
        self._qtimer = QTimer(self)
        self._qtimer.setInterval(1000)
        self._qtimer.timeout.connect(self._on_tick)

    def phase_length_seconds(self):
        minutes = {
            "focus": self.settings["focus_minutes"],
            "short_break": self.settings["short_break_minutes"],
            "long_break": self.settings["long_break_minutes"],
        }[self.session_type]
        return max(1, int(minutes)) * 60

    def start(self):
        if self.running:
            return
        if self.session_type == "focus" and self._phase_started_at is None:
            self._phase_started_at = _now_iso()
        self.running = True
        self._qtimer.start()
        self.tick.emit()

    def pause(self):
        self.running = False
        self._qtimer.stop()
        self.tick.emit()

    def reset(self):
        self.running = False
        self._qtimer.stop()
        self.remaining_seconds = self.phase_length_seconds()
        self._phase_started_at = None
        self.tick.emit()

    def skip(self):
        # Skip is an explicit user action, so it always starts the next phase
        # immediately regardless of the auto-start-next preference.
        self._advance(auto_start=True)

    def _on_tick(self):
        self.remaining_seconds -= 1
        if self.remaining_seconds <= 0:
            self._complete_phase()
        else:
            self.tick.emit()

    def _complete_phase(self):
        if self.session_type == "focus":
            planned = self.settings["focus_minutes"]
            _log_session(self._phase_started_at or _now_iso(), planned, planned)
            tooltip(tr("pomodoro_focus_done", "Focus session complete! Time for a break."))
            _play_sound(self.settings)
        else:
            tooltip(tr("pomodoro_break_done", "Break's over. Ready to focus?"))
        self._advance(auto_start=self.settings.get("auto_start_next_phase", True))

    def _advance(self, auto_start=True):
        if self.session_type == "focus":
            self.focus_count += 1
            if self.focus_count >= self.settings["sessions_until_long_break"]:
                self.session_type = "long_break"
                self.focus_count = 0
            else:
                self.session_type = "short_break"
        else:
            self.session_type = "focus"
        self._phase_started_at = None
        self.remaining_seconds = self.phase_length_seconds()
        self.running = bool(auto_start)
        if self.running:
            self._qtimer.start()
        else:
            self._qtimer.stop()
        self.phase_changed.emit()


def get_timer():
    global _timer
    if _timer is None:
        _timer = PomodoroTimer()
    return _timer


# ─── Floating island ────────────────────────────────────────────────────────

class _PomoShellFrame(QFrame):
    """Paints its own background/border instead of relying on QSS, so a live
    blurred backdrop pixmap (captured from behind the window - see
    PomodoroWidget._refresh_shell_backdrop) can be layered under the
    translucent shell tint for a real frosted-glass look."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backdrop = None
        self._tint = QColor(255, 255, 255, 255)
        self._border = QColor("#e5e7eb")
        self._radius = 18.0

    def set_appearance(self, backdrop_pixmap, tint_color, border_color, radius=18.0):
        self._backdrop = backdrop_pixmap
        self._tint = tint_color
        self._border = border_color
        self._radius = radius
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)

        painter.save()
        painter.setClipPath(path)
        if self._backdrop is not None and not self._backdrop.isNull():
            painter.drawPixmap(self.rect(), self._backdrop, self._backdrop.rect())
        painter.fillPath(path, QBrush(self._tint))
        painter.restore()

        pen = QPen(self._border)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, self._radius, self._radius)


class _PomoProgressBar(QWidget):
    """Thin rounded phase-progress bar (medium/big islands only)."""

    def __init__(self, height, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._fraction = 0.0
        self._track = QColor(0, 0, 0, 40)
        self._fill = QColor("#00A982")

    def set_colors(self, track, fill):
        self._track = QColor(track)
        self._fill = QColor(fill)
        self.update()

    def set_fraction(self, fraction):
        fraction = max(0.0, min(1.0, float(fraction)))
        if abs(fraction - self._fraction) > 0.0005:
            self._fraction = fraction
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = self.height() / 2.0
        painter.setBrush(QBrush(self._track))
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)
        width = self.width() * self._fraction
        if width > 0:
            painter.setBrush(QBrush(self._fill))
            painter.drawRoundedRect(QRectF(0, 0, max(width, self.height()), self.height()), radius, radius)


class PomodoroIslandView(_PomoShellFrame):
    """The island's whole shell content, built purely from a settings dict.

    Both the real floating window (PomodoroWidget) and the Settings preview
    (settings/_page_pomodoro.py) instantiate this same class, so the preview
    is the real thing rather than a look-alike. `callbacks` is None in the
    preview, which also skips wiring the buttons."""

    def __init__(self, settings, dark, callbacks=None, parent=None):
        super().__init__(parent)
        self.callbacks = callbacks or {}
        self.settings = settings
        self.dark = dark
        self.pal = _palette(dark, settings)
        self.preset = get_preset(settings)
        self._state = {
            "phase": "focus",
            "remaining": 0,
            "total": 1,
            "focus_count": 0,
            "cycle_total": 4,
            "running": False,
        }
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._body = None
        self._build()

    # ─── Construction ────────────────────────────────────────────────────

    def _build(self):
        if self._body is not None:
            self._outer.removeWidget(self._body)
            # setParent(None) first: deleteLater alone leaves the old body
            # painted on top of the new one until the event loop runs.
            self._body.setParent(None)
            self._body.deleteLater()
        preset = self.preset
        # New child widgets, so every refresh() cache is stale.
        self._icon_sig = self._dots_sig = self._stats_sig = None
        # No stylesheet on the body: a selector-less rule here ("background:
        # transparent") would cascade to every child and beat the shell's
        # QToolButton#pomoPlay / QFrame#pomoIslandTile backgrounds. A plain
        # QWidget paints nothing anyway.
        self._body = body = QWidget(self)
        layout = QVBoxLayout(body)
        left, top, right, bottom = preset["pad"]
        layout.setContentsMargins(left, top, right, bottom)
        layout.setSpacing(preset["spacing"])

        layout.addWidget(self._build_topbar())

        self.time_label = QLabel()
        self.time_label.setObjectName("pomoTime")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.time_label)

        rows = preset["rows"]

        self.progress_bar = None
        if "progress" in rows:
            self.progress_bar = _PomoProgressBar(6 if preset["dot"] < 16 else 8)
            layout.addWidget(self.progress_bar)

        self.dots_row = QHBoxLayout()
        self.dots_row.setSpacing(5)
        self.dots_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(self.dots_row)

        self.meta_label = None
        if "meta" in rows:
            self.meta_label = QLabel()
            self.meta_label.setObjectName("pomoMeta")
            self.meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.meta_label)

        self.stat_values = {}
        if "stats" in rows:
            layout.addWidget(self._build_stats_row())

        layout.addLayout(self._build_controls())

        self._outer.addWidget(body)
        self.setStyleSheet(self._shell_qss())
        self.refresh()

    def _build_topbar(self):
        preset = self.preset
        self.topbar = QFrame()
        self.topbar.setObjectName("pomoTopbar")
        self.topbar.setFixedHeight(preset["topbar_h"])
        self.topbar.setCursor(
            Qt.CursorShape.SizeAllCursor if self.callbacks else Qt.CursorShape.ArrowCursor
        )
        top = QHBoxLayout(self.topbar)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)

        self.topbar_icon = QLabel()
        self.phase_label = QLabel()
        self.phase_label.setObjectName("pomoPhase")

        chip = preset["chip"]
        self.stats_btn = QToolButton()
        self.stats_btn.setFixedSize(chip, chip)
        self.stats_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self.stats_btn.setToolTip(tr("pomodoro_stats_title", "Pomodoro Stats"))

        self.close_btn = QToolButton()
        self.close_btn.setText("✕")
        self.close_btn.setFixedSize(chip, chip)
        self.close_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self.close_btn.setToolTip(tr("pomodoro_close", "Close"))

        self._connect(self.stats_btn, "stats")
        self._connect(self.close_btn, "close")

        top.addWidget(self.topbar_icon)
        top.addWidget(self.phase_label)
        top.addStretch()
        top.addWidget(self.stats_btn)
        top.addWidget(self.close_btn)
        return self.topbar

    def _build_stats_row(self):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        tiles = (
            ("minutes_today", tr("pomodoro_today", "Today")),
            ("count_today", tr("pomodoro_sessions", "Sessions")),
            ("streak", tr("pomodoro_streak_short", "Streak")),
        )
        for key, label_text in tiles:
            tile = QFrame()
            tile.setObjectName("pomoIslandTile")
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(8, 6, 8, 6)
            tile_layout.setSpacing(1)
            caption = QLabel(label_text.upper())
            caption.setObjectName("pomoTileCaption")
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value = QLabel("—")
            value.setObjectName("pomoTileValue")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tile_layout.addWidget(caption)
            tile_layout.addWidget(value)
            self.stat_values[key] = value
            layout.addWidget(tile, 1)
        return row

    def _build_controls(self):
        preset = self.preset
        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.reset_btn = QToolButton()
        self.reset_btn.setText("⟲")
        self.reset_btn.setFixedSize(preset["btn"], preset["btn"])
        self.reset_btn.setToolTip(tr("pomodoro_reset", "Reset"))
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.play_btn = QToolButton()
        self.play_btn.setObjectName("pomoPlay")
        self.play_btn.setFixedSize(preset["play"], preset["play"])
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.skip_btn = QToolButton()
        self.skip_btn.setText("⏭")
        self.skip_btn.setFixedSize(preset["btn"], preset["btn"])
        self.skip_btn.setToolTip(tr("pomodoro_skip", "Skip"))
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._connect(self.reset_btn, "reset")
        self._connect(self.play_btn, "play")
        self._connect(self.skip_btn, "skip")

        controls.addStretch()
        controls.addWidget(self.reset_btn)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.skip_btn)
        controls.addStretch()
        return controls

    def _connect(self, button, name):
        handler = self.callbacks.get(name)
        if handler is not None:
            button.clicked.connect(handler)
            return
        # No callbacks at all means this is the static Settings preview: kill
        # the hover states too (WA_TransparentForMouseEvents doesn't inherit,
        # so setting it on the island alone wouldn't cover the buttons).
        if not self.callbacks:
            button.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            button.setCursor(Qt.CursorShape.ArrowCursor)

    # ─── Styling ─────────────────────────────────────────────────────────

    def _shell_qss(self):
        pal = self.pal
        preset = self.preset
        family = _resolve_font_family(self.settings.get("font_key", "system"))
        # Poppins is the add-on default; use it unless a custom font is chosen.
        digits_font = f"font-family: '{family}';" if family else "font-family: 'Poppins';"
        tile_bg = shell_alpha_color(pal["icon"], 10)
        return f"""
            QFrame#pomoTopbar {{ background: transparent; font-family: 'Poppins'; }}
            QLabel#pomoPhase {{ color: {pal['icon']}; font-size: {preset['phase_px']}px; font-weight: 800;
                letter-spacing: 1px; text-transform: uppercase; background: transparent; font-family: 'Poppins'; }}
            QLabel#pomoTime {{ color: {pal['digits']}; font-size: {preset['time_px']}px; font-weight: 800; background: transparent; {digits_font} }}
            QLabel#pomoMeta {{ color: {pal['icon']}; font-size: {max(9, preset['phase_px'] - 1)}px; font-weight: 700;
                letter-spacing: 0.5px; background: transparent; font-family: 'Poppins'; }}
            QFrame#pomoIslandTile {{ background: {tile_bg}; border: 1px solid {shell_alpha_color(pal['icon'], 18)}; border-radius: 10px; }}
            QLabel#pomoTileCaption {{ color: {pal['icon']}; font-size: 8px; font-weight: 800; letter-spacing: 1px; background: transparent; font-family: 'Poppins'; }}
            QLabel#pomoTileValue {{ color: {pal['digits']}; font-size: 14px; font-weight: 800; background: transparent; {digits_font} }}
            QToolButton {{ background: transparent; border: none; border-radius: 8px; color: {pal['icon']}; font-size: {round(preset['btn'] / 2)}px; }}
            QToolButton:hover {{ background: {pal['hover']}; }}
            QToolButton#pomoPlay {{ background: {pal['accent']}; color: white; border-radius: {round(preset['play'] / 2)}px;
                font-size: {round(preset['play'] * 0.42)}px; font-weight: 700; }}
            QToolButton#pomoPlay:hover {{ background: {pal['accent']}; }}
        """

    def apply_settings(self, settings, dark, backdrop_pixmap=None):
        """Re-applies a (possibly edited) settings dict - rebuilds the whole
        body when the size preset changed, restyles in place otherwise."""
        size_changed = get_preset(settings) is not self.preset
        self.settings = settings
        self.dark = dark
        self.pal = _palette(dark, settings)
        self.preset = get_preset(settings)
        if size_changed:
            self._build()
        else:
            self.setStyleSheet(self._shell_qss())
            self.refresh()
        self.apply_shell_appearance(backdrop_pixmap)

    def apply_shell_appearance(self, backdrop_pixmap=None):
        tint = shell_alpha_qcolor(self.pal["shell"], self.settings.get("shell_opacity", 100))
        self.set_appearance(backdrop_pixmap, tint, QColor(self.pal["border"]), self.preset["radius"])

    # ─── State ───────────────────────────────────────────────────────────

    def set_state(self, phase, remaining, total, focus_count, cycle_total, running):
        self._state = {
            "phase": phase,
            "remaining": remaining,
            "total": max(1, total),
            "focus_count": focus_count,
            "cycle_total": max(1, cycle_total),
            "running": running,
        }
        self.refresh()

    @staticmethod
    def _format_time(total_seconds):
        total_seconds = max(0, int(total_seconds))
        m, s = divmod(total_seconds, 60)
        return f"{m:02d}:{s:02d}"

    @staticmethod
    def _phase_name(phase):
        return {
            "focus": tr("pomodoro_focus", "Focus"),
            "short_break": tr("pomodoro_short_break", "Short Break"),
            "long_break": tr("pomodoro_long_break", "Long Break"),
        }.get(phase, phase)

    def _next_phase(self):
        state = self._state
        if state["phase"] != "focus":
            return "focus"
        if state["focus_count"] + 1 >= state["cycle_total"]:
            return "long_break"
        return "short_break"

    def refresh(self):
        """Runs once per second while the timer ticks, so everything costly
        (icon rasterization, dot rebuilds, the collection read behind the stats
        tiles) is guarded by a signature and only redone when it changed."""
        state = self._state
        pal = self.pal
        icon_value = self.settings.get("icon") or DEFAULT_ICON

        icon_sig = (icon_value, pal["accent"], pal["icon"], self.preset["icon"])
        if icon_sig != getattr(self, "_icon_sig", None):
            self._icon_sig = icon_sig
            self.topbar_icon.setPixmap(render_icon_pixmap(_addon_root(), icon_value, pal["accent"], self.preset["icon"]))
            self.stats_btn.setIcon(_tinted_icon(_system_icon_path("stats.svg"), pal["icon"], self.preset["icon"] - 2))

        self.phase_label.setText(self._phase_name(state["phase"]))
        self.time_label.setText(self._format_time(state["remaining"]))
        self.play_btn.setText("⏸" if state["running"] else "▶")

        if self.progress_bar is not None:
            # QColor can't parse an "rgba(...)" string - the track needs the
            # QColor-returning helper, not the CSS one.
            self.progress_bar.set_colors(shell_alpha_qcolor(pal["icon"], 22), pal["accent"])
            self.progress_bar.set_fraction(1.0 - state["remaining"] / float(state["total"]))

        dots_sig = (icon_sig, state["focus_count"], state["cycle_total"])
        if dots_sig != getattr(self, "_dots_sig", None):
            self._dots_sig = dots_sig
            self._rebuild_dots()

        if self.meta_label is not None:
            self.meta_label.setText("{}  ·  {} {}".format(
                tr("pomodoro_session_of", "Session {n} of {total}")
                .replace("{n}", str(min(state["focus_count"] + 1, state["cycle_total"])))
                .replace("{total}", str(state["cycle_total"])),
                tr("pomodoro_next", "Next:"),
                self._phase_name(self._next_phase()),
            ))

        # Sessions are only ever logged when a focus phase completes, so the
        # tiles only need refreshing when the phase/cycle position moves.
        stats_sig = (state["phase"], state["focus_count"])
        if self.stat_values and stats_sig != getattr(self, "_stats_sig", None):
            self._stats_sig = stats_sig
            stats = session_stats()
            self.stat_values["minutes_today"].setText(format_minutes(stats["minutes_today"]))
            self.stat_values["count_today"].setText(str(stats["count_today"]))
            self.stat_values["streak"].setText("{}d".format(stats["streak"]))

    def _rebuild_dots(self):
        while self.dots_row.count():
            item = self.dots_row.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        state = self._state
        total = state["cycle_total"]
        filled = min(state["focus_count"], total)
        icon_value = self.settings.get("icon") or DEFAULT_ICON
        for i in range(total):
            label = QLabel()
            filled_slot = i < filled
            color = self.pal["accent"] if filled_slot else self.pal["icon"]
            label.setPixmap(render_icon_pixmap(_addon_root(), icon_value, color, self.preset["dot"]))
            if not filled_slot:
                effect = QGraphicsOpacityEffect(label)
                effect.setOpacity(0.35)
                label.setGraphicsEffect(effect)
            self.dots_row.addWidget(label)


class PomodoroWidget(QDialog):
    """Frameless floating timer. Copies HashiNotePopup's shell recipe from
    hashi_notes.py: a native Tool window with a slim draggable topbar, since
    the countdown itself owns no state — closing this just hides the view,
    PomodoroTimer keeps ticking underneath."""

    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.dark = _is_dark_mode()
        self.timer = get_timer()
        self.pal = _palette(self.dark, self.timer.settings)
        self._drag_pos = None
        self._drag_snapshot = None
        self._drag_snapshot_origin = None

        self.setWindowTitle(tr("pomodoro_window_title"))
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(*get_preset(self.timer.settings)["window"])

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        self.shell = shell = PomodoroIslandView(
            self.timer.settings,
            self.dark,
            callbacks={
                "stats": self._open_stats,
                "close": self.close,
                "play": self._on_play_pause,
                "reset": self._on_reset,
                "skip": self._on_skip,
            },
        )
        shell.setObjectName("pomoShell")
        outer.addWidget(shell)
        self.topbar = shell.topbar

        self.timer.tick.connect(self._refresh)
        self.timer.phase_changed.connect(self._refresh_full)

        self._apply_shell_appearance()
        self._refresh_full()

    def reload_appearance(self):
        """Re-reads the saved settings into the open island (called after the
        Settings dialog saves, so size/colors apply without reopening)."""
        self.timer.settings = get_settings()
        self.pal = _palette(self.dark, self.timer.settings)
        self.setFixedSize(*get_preset(self.timer.settings)["window"])
        self.shell.apply_settings(self.timer.settings, self.dark)
        self.topbar = self.shell.topbar
        self._refresh_full()
        self._refresh_static_backdrop()

    def _apply_shell_appearance(self, backdrop_pixmap=None):
        self.shell.apply_shell_appearance(backdrop_pixmap)

    def _grab_screen_pixmap(self):
        """Grabs the whole current screen, hiding this window (via full
        transparency, not hide()/show(), so an active drag's mouse grab
        isn't dropped) for the instant of the capture so it doesn't capture
        itself."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return None, None
        prior_opacity = self.windowOpacity()
        self.setWindowOpacity(0.0)
        QApplication.processEvents()
        QApplication.processEvents()
        try:
            pixmap = screen.grabWindow(0)
        finally:
            self.setWindowOpacity(prior_opacity)
        geo = screen.geometry()
        if pixmap is not None and not pixmap.isNull() and geo.width() > 0:
            ratio = pixmap.width() / geo.width()
            pixmap.setDevicePixelRatio(ratio if ratio > 0 else 1.0)
        return pixmap, geo.topLeft()

    def _refresh_shell_backdrop(self):
        """Crops+blurs the region of self._drag_snapshot currently behind the
        shell. Cheap (crop then blur a small region), so it can run on every
        mouseMoveEvent while dragging for a live frosted-glass effect."""
        blur_pct = self.timer.settings.get("shell_blur", 0)
        snapshot = self._drag_snapshot
        if blur_pct <= 0 or snapshot is None or snapshot.isNull():
            self._apply_shell_appearance(None)
            return
        ratio = snapshot.devicePixelRatio() or 1.0
        top_left = self.shell.mapToGlobal(QPoint(0, 0)) - self._drag_snapshot_origin
        crop_rect = QRect(
            round(top_left.x() * ratio),
            round(top_left.y() * ratio),
            round(self.shell.width() * ratio),
            round(self.shell.height() * ratio),
        )
        cropped = snapshot.copy(crop_rect)
        cropped.setDevicePixelRatio(ratio)
        blurred = blur_pixmap(cropped, blur_pct * 0.2 * ratio)
        self._apply_shell_appearance(blurred)

    def _refresh_static_backdrop(self):
        """One-off capture for when the island isn't being dragged (on open) -
        the big full-screen snapshot is discarded right after use."""
        if self.timer.settings.get("shell_blur", 0) <= 0:
            self._apply_shell_appearance(None)
            return
        pixmap, origin = self._grab_screen_pixmap()
        if pixmap is None or pixmap.isNull():
            self._apply_shell_appearance(None)
            return
        self._drag_snapshot = pixmap
        self._drag_snapshot_origin = origin
        self._refresh_shell_backdrop()
        self._drag_snapshot = None
        self._drag_snapshot_origin = None

    def present(self, anchor):
        _position_centered(self, anchor)
        self.show()
        self.raise_()
        self.activateWindow()
        self._refresh_static_backdrop()

    def _refresh(self):
        timer = self.timer
        self.shell.set_state(
            timer.session_type,
            timer.remaining_seconds,
            timer.phase_length_seconds(),
            timer.focus_count,
            max(1, timer.settings.get("sessions_until_long_break", 4)),
            timer.running,
        )

    def _refresh_full(self):
        self._refresh()

    def _on_play_pause(self):
        if self.timer.running:
            self.timer.pause()
        else:
            self.timer.start()

    def _on_reset(self):
        self.timer.reset()

    def _on_skip(self):
        self.timer.skip()

    def _open_stats(self):
        open_stats_dialog(self.parent())

    def _topbar_at(self, event):
        # mapFrom walks the whole ancestor chain (the topbar now lives inside
        # the island view's body widget, not directly under this dialog).
        pos = event.position().toPoint()
        return self.topbar.rect().contains(self.topbar.mapFrom(self, pos))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._topbar_at(event):
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            if self.timer.settings.get("shell_blur", 0) > 0:
                pixmap, origin = self._grab_screen_pixmap()
                if pixmap is not None and not pixmap.isNull():
                    self._drag_snapshot = pixmap
                    self._drag_snapshot_origin = origin
                    self._refresh_shell_backdrop()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            if self._drag_snapshot is not None:
                self._refresh_shell_backdrop()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._drag_snapshot = None
        self._drag_snapshot_origin = None
        super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        try:
            self.timer.tick.disconnect(self._refresh)
        except Exception:
            pass
        try:
            self.timer.phase_changed.disconnect(self._refresh_full)
        except Exception:
            pass
        global _widget
        if _widget is self:
            _widget = None
        super().closeEvent(event)


# ─── Stats dashboard ────────────────────────────────────────────────────────

def _modern_button(pal, text, primary=False):
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        bg, fg, border = pal["accent"], "#ffffff", pal["accent"]
        hover, pressed = shell_alpha_color(pal["accent"], 88), shell_alpha_color(pal["accent"], 76)
    else:
        bg, fg, border, hover, pressed = pal["surface"], pal["fg"], pal["border"], pal["hover"], pal["border"]
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {bg};
            color: {fg};
            border: 1px solid {border};
            border-radius: 9px;
            padding: 7px 16px;
            font-size: 12px;
            font-weight: 700;
        }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:pressed {{ background: {pressed}; }}
    """)
    return btn


def _stat_tile(pal, label, value):
    tile = QFrame()
    tile.setObjectName("pomoStatTile")
    tile.setStyleSheet(
        f"QFrame#pomoStatTile {{ background: {pal['surface']}; border: 1px solid {pal['border']}; border-radius: 14px; }}"
    )
    layout = QVBoxLayout(tile)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(2)
    lab = QLabel(label.upper())
    lab.setStyleSheet(f"font-size: 9px; font-weight: 800; letter-spacing: 1px; color: {pal['fg3']}; background: transparent;")
    val = QLabel(value)
    val.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {pal['fg']}; background: transparent;")
    layout.addWidget(lab)
    layout.addWidget(val)
    return tile


class PomodoroStatsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.dark = _is_dark_mode()
        self.pal = pal = _palette(self.dark)
        self.setWindowTitle(tr("pomodoro_stats_title", "Pomodoro Stats"))
        self.setMinimumSize(640, 580)
        self.resize(680, 640)
        self.setStyleSheet(f"QDialog {{ background: {pal['shell']}; }} QLabel {{ background: transparent; }}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel(tr("pomodoro_stats_title", "Pomodoro Stats"))
        title.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {pal['fg']};")
        settings_btn = _modern_button(pal, tr("pomodoro_open_settings", "Settings"), primary=True)
        settings_btn.clicked.connect(self._open_settings)
        open_btn = _modern_button(pal, tr("pomodoro_open_timer", "Open Timer"))
        open_btn.clicked.connect(lambda: toggle_widget(self.parent()))
        header.addWidget(title)
        header.addStretch()
        header.addWidget(settings_btn)
        header.addWidget(open_btn)
        outer.addLayout(header)

        sessions = get_sessions()

        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        tiles.addWidget(_stat_tile(pal, tr("pomodoro_total_focus", "Total Focus"), self._total_focus_text(sessions)))
        tiles.addWidget(_stat_tile(pal, tr("pomodoro_sessions_today", "Sessions Today"), str(self._sessions_today(sessions))))
        tiles.addWidget(_stat_tile(pal, tr("pomodoro_streak", "Current Streak"), self._streak_text(sessions)))
        tiles.addWidget(_stat_tile(pal, tr("pomodoro_best_day", "Most Studied Day"), self._most_studied_day(sessions)))
        outer.addLayout(tiles)

        chart_card = QFrame()
        chart_card.setObjectName("pomoChartCard")
        chart_card.setStyleSheet(
            f"QFrame#pomoChartCard {{ background: {pal['surface']}; border: 1px solid {pal['border']}; border-radius: 16px; }}"
        )
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(16, 12, 16, 12)
        chart_label = QLabel(tr("pomodoro_last_7_days", "Last 7 Days (focus minutes)"))
        chart_label.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {pal['fg3']};")
        chart_layout.addWidget(chart_label)
        self.chart = WeeklyChart()
        self.chart.set_colors(pal["accent"], pal["fg3"])
        values, labels = self._weekly_focus_minutes(sessions)
        self.chart.set_data(values, labels)
        chart_layout.addWidget(self.chart)
        outer.addWidget(chart_card)

        history_label = QLabel(tr("pomodoro_history", "Session History"))
        history_label.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {pal['fg3']};")
        outer.addWidget(history_label)
        self.history_list = QListWidget()
        self.history_list.setFrameShape(QFrame.Shape.NoFrame)
        self.history_list.setSpacing(6)
        self.history_list.setStyleSheet(f"""
            QListWidget {{ background: transparent; border: none; color: {pal['fg']}; outline: 0; }}
            QListWidget::item {{
                background: {pal['surface']};
                border: 1px solid {pal['border']};
                border-radius: 10px;
                padding: 10px 14px;
            }}
            QListWidget::item:hover {{ background: {pal['hover']}; }}
            QListWidget::item:selected {{ background: {shell_alpha_color(pal['accent'], 14)}; border-color: {pal['accent']}; color: {pal['fg']}; }}
        """)
        if sessions:
            for entry in reversed(sessions[-50:]):
                self.history_list.addItem(QListWidgetItem(self._history_row_text(entry)))
        else:
            empty = QListWidgetItem(tr("pomodoro_no_sessions", "No focus sessions yet."))
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.history_list.addItem(empty)
        outer.addWidget(self.history_list, 1)

    def _open_settings(self):
        from . import settings_web

        settings_web.open_settings(
            "Pomodoro", parent=self.parent() or mw, addon_path=_addon_root()
        )

    def _total_focus_text(self, sessions):
        total_minutes = sum(s.get("actual_minutes", 0) for s in sessions)
        h, m = divmod(int(round(total_minutes)), 60)
        return f"{h}h {m}m" if h else f"{m}m"

    def _sessions_today(self, sessions):
        today = date.today().isoformat()
        return sum(1 for s in sessions if s.get("date") == today)

    def _streak_text(self, sessions):
        days = {s.get("date") for s in sessions if s.get("date")}
        if not days:
            return "0"
        streak = 0
        cursor = date.today()
        while cursor.isoformat() in days:
            streak += 1
            cursor -= timedelta(days=1)
        return str(streak)

    def _most_studied_day(self, sessions):
        if not sessions:
            return "—"
        totals = {}
        for s in sessions:
            d = s.get("date")
            if not d:
                continue
            try:
                y, mo, da = (int(x) for x in d.split("-"))
                weekday = date(y, mo, da).isoweekday()
            except Exception:
                continue
            totals[weekday] = totals.get(weekday, 0) + s.get("actual_minutes", 0)
        if not totals:
            return "—"
        best = max(totals, key=totals.get)
        return current_locale().dayName(best, QLocale.FormatType.LongFormat)

    def _weekly_focus_minutes(self, sessions):
        today = date.today()
        locale = current_locale()
        by_date = {}
        for s in sessions:
            d = s.get("date")
            if d:
                by_date[d] = by_date.get(d, 0) + s.get("actual_minutes", 0)
        values, labels = [], []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            values.append(round(by_date.get(day.isoformat(), 0)))
            labels.append(locale.dayName(day.isoweekday(), QLocale.FormatType.ShortFormat))
        return values, labels

    def _history_row_text(self, entry):
        try:
            dt = datetime.fromisoformat(entry.get("started_at", ""))
            when = dt.strftime("%b %d, %H:%M")
        except Exception:
            when = entry.get("date", "")
        minutes = entry.get("actual_minutes", entry.get("planned_minutes", 0))
        return f"{when}   ·   {tr('pomodoro_focus', 'Focus')}   ·   {int(round(minutes))} min"


# ─── Entry points ─────────────────────────────────────────────────────────────

def toggle_widget(parent=None):
    global _widget
    if _widget is not None:
        try:
            _widget.close()
        except Exception:
            pass
        _widget = None
        return None
    anchor = parent or mw
    _widget = PomodoroWidget(anchor)
    _widget.present(anchor)
    return _widget


def reload_open_widget():
    """Pushes freshly saved settings into an island that is already on screen
    (called by the Settings page after it saves)."""
    if _widget is None:
        return
    try:
        _widget.reload_appearance()
    except Exception as e:
        print(f"Pomodoro: reload error: {e}")


def open_stats_dialog(parent=None):
    global _stats_dialog
    try:
        if _stats_dialog is not None:
            _stats_dialog.close()
    except Exception:
        pass
    _stats_dialog = PomodoroStatsDialog(parent or mw)
    _stats_dialog.show()
    _stats_dialog.raise_()
    _stats_dialog.activateWindow()
    return _stats_dialog
