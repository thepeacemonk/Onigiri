"""
Native PyQt widgets for Prep Station — Onigiri's study planner.

Everything here themes off Onigiri's own light/dark palette (not the OS palette)
so it stays visually consistent with the rest of the add-on.
"""

from __future__ import annotations

import os
import uuid
from datetime import date

from aqt import mw
from aqt.theme import theme_manager
from aqt.qt import (
    QWidget, QFrame, QLabel, QPushButton, QToolButton, QLineEdit, QTextEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QApplication,
    QDialog, QSizePolicy, QCheckBox,
    Qt, QSize, QRectF, QPointF, QColor, QPainter, QPainterPath, QPen, QBrush,
    QPropertyAnimation, QEasingCurve, QIcon, QPixmap, QFont,
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import pyqtSignal, pyqtProperty, QDate, QTimer
from PyQt6.QtGui import QImage, QLinearGradient, QConicalGradient, QFontMetrics, QFontDatabase, QCursor
from PyQt6.QtSvg import QSvgRenderer

from . import config
from .translations import tr, current_locale
from .onigiri_color_picker import OnigiriColorDialog
from .ui_widgets import AnimatedToggleButton, MainBackgroundEffectSlider

PLAN_COLORS = ["#3B82F6", "#10B981", "#FBBF24", "#a855f7", "#F472B6", "#F97316", "#EF4444"]
DEFAULT_ICON = "emoji:📚"
DEFAULT_PLAN_LIGHT_COLOR = "#60A5FA"
DEFAULT_PLAN_DARK_COLOR = "#1E3A8A"


def weekday_letters() -> list:
    """Locale-aware, Monday-first single-letter weekday header (e.g. calendar grids)."""
    from PyQt6.QtCore import QLocale
    locale = current_locale()
    return [locale.dayName(d, QLocale.FormatType.NarrowFormat) for d in range(1, 8)]


# ─── Theming ──────────────────────────────────────────────────────────────────

def _accent() -> str:
    conf = config.get_config()
    mode = "dark" if theme_manager.night_mode else "light"
    try:
        default = config.DEFAULTS["colors"][mode]["--accent-color"]
    except Exception:
        default = "#00A982"
    return conf.get("colors", {}).get(mode, {}).get("--accent-color", default)


def palette(dark: bool | None = None) -> dict:
    if dark is None:
        dark = theme_manager.night_mode
    accent = _accent()
    if dark:
        return {
            "bg": "#161616", "surface": "#1f1f1f", "surface2": "#2a2a2a",
            "hover": "#343434", "fg": "#f4f4f5", "fg2": "#b6b6b8", "fg3": "#7c7c80",
            "border": "#343434", "border2": "#454545", "accent": accent,
        }
    return {
        "bg": "#f5f5f4", "surface": "#ffffff", "surface2": "#f1f1f0",
        "hover": "#e8e8e7", "fg": "#1d1d1f", "fg2": "#6a6a6e", "fg3": "#9a9a9e",
        "border": "#e4e4e2", "border2": "#d4d4d2", "accent": accent,
    }


def small_title_font_css(dark: bool | None = None) -> str:
    """CSS font declaration matching the user's configured "Small Titles" font
    (Settings → Fonts), used for compact labels/section headings across the add-on."""
    if dark is None:
        dark = theme_manager.night_mode
    mode = "dark" if dark else "light"
    conf = config.get_config()
    default_color = config.DEFAULTS["colors"][mode].get("--font-small-title-color", "#212121")
    color = conf.get("colors", {}).get(mode, {}).get("--font-small-title-color", default_color)

    col_conf = mw.col.conf if mw.col and mw.col else {}
    font_key = col_conf.get("onigiri_font_small_title", "system")
    size = col_conf.get("onigiri_font_size_small_title", 15)

    family = None
    if font_key != "system":
        from .fonts import get_all_fonts
        addon_path = os.path.dirname(__file__)
        info = get_all_fonts(addon_path).get(font_key)
        if info and info.get("file"):
            if info.get("user"):
                font_path = os.path.join(addon_path, "user_files", "fonts", info["file"])
            else:
                font_path = os.path.join(addon_path, "system_files", "fonts", "system_fonts", info["file"])
            if os.path.exists(font_path):
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    if families:
                        family = families[0]

    family_css = f"'{family}', " if family else ""
    return f"font-family: {family_css}-apple-system, 'Segoe UI', sans-serif; font-size: {size}px; color: {color};"


def with_alpha(hex_color: str, alpha: int) -> QColor:
    c = QColor(hex_color)
    c.setAlpha(max(0, min(255, alpha)))
    return c


def _write_qss_icon(svg: str, name: str) -> str:
    """Caches a small SVG to disk and returns its path for use in a QSS
    `image: url(...)`. Qt's stylesheet engine doesn't reliably rasterize
    data: URIs for ::indicator/::branch images across platforms, so these
    need to be real files (content-hashed, so theme/color changes just add
    a new small file instead of overwriting stale ones)."""
    import hashlib
    cache_dir = os.path.join(os.path.dirname(__file__), "user_files", "_qss_icon_cache")
    os.makedirs(cache_dir, exist_ok=True)
    digest = hashlib.md5(svg.encode("utf-8")).hexdigest()[:10]
    path = os.path.join(cache_dir, f"{name}_{digest}.svg")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
    return path.replace(os.sep, "/")


def _checkmark_icon_path() -> str:
    """The app's own check-simple.svg (tinted white), used to modernize
    the checkbox indicators (deck picker) with a filled, rounded,
    accent-colored checked state — instead of a one-off hand-drawn path."""
    icon_path = os.path.join(
        os.path.dirname(__file__), "system_files", "system_icons",
        "unavailable_for_users", "check-simple.svg",
    )
    with open(icon_path, "r", encoding="utf-8") as f:
        svg = f.read().replace("currentColor", "white")
    return _write_qss_icon(svg, "checkmark")


_CHECKMARK_URI = _checkmark_icon_path()


def _chevron_icon_path(color: str, expanded: bool) -> str:
    """SVG expand/collapse chevron for the deck picker's row toggle label,
    matching the app's line weight instead of an OS-native arrow."""
    path = "M3 4.5l3 3 3-3" if expanded else "M4.5 3l3 3-3 3"
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        f'<path d="{path}" fill="none" stroke="{color}" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )
    return _write_qss_icon(svg, f"chevron_{'open' if expanded else 'closed'}_{color.lstrip('#')}")


def readable_on(color: str) -> str:
    c = QColor(color)
    lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
    return "#ffffff" if lum < 150 else "#1a1a1a"


def build_qss(p: dict) -> str:
    accent = p["accent"]
    return f"""
    QWidget {{ font-family: 'DM Sans', -apple-system, 'Segoe UI', sans-serif; color: {p['fg']}; }}
    QLabel {{ background: transparent; }}
    QLineEdit, QTextEdit, QAbstractSpinBox {{
        background: {p['surface']};
        border: 1px solid {p['border2']};
        border-radius: 10px;
        padding: 8px 12px;
        color: {p['fg']};
        selection-background-color: {accent};
        selection-color: #ffffff;
    }}
    QLineEdit:focus, QTextEdit:focus {{ border: 1px solid {accent}; }}
    QLineEdit::placeholder {{ color: {p['fg3']}; }}
    QPushButton {{
        background: {p['surface2']};
        border: 1px solid {p['border2']};
        border-radius: 10px;
        padding: 8px 16px;
        color: {p['fg']};
        font-weight: 600;
    }}
    QPushButton:hover {{ background: {p['hover']}; }}
    QPushButton[psPrimary="true"] {{ background: {accent}; border: 1px solid {accent}; color: #ffffff; }}
    QPushButton[psPrimary="true"]:hover {{ background: {QColor(accent).lighter(112).name()}; }}
    QPushButton[psDanger="true"] {{ background: transparent; border: 1px solid transparent; color: #ef4444; }}
    QPushButton[psDanger="true"]:hover {{ background: rgba(239,68,68,0.12); }}
    QPushButton[psGhost="true"] {{ background: transparent; border: 1px solid transparent; color: {p['fg2']}; }}
    QPushButton[psGhost="true"]:hover {{ background: {p['surface2']}; color: {p['fg']}; }}
    QCheckBox {{ spacing: 8px; color: {p['fg']}; }}
    QCheckBox::indicator {{
        width: 17px; height: 17px;
        margin: 0;
        border: 2px solid {p['border2']};
        border-radius: 6px;
        background: {p['surface']};
    }}
    QCheckBox::indicator:hover {{ border-color: {accent}; }}
    QCheckBox::indicator:checked {{
        border: 2px solid {accent};
        background: {accent};
        image: url("{_CHECKMARK_URI}");
    }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {p['border2']}; border-radius: 4px; min-height: 24px; }}
    QScrollBar::handle:vertical:hover {{ background: {p['fg3']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {p['border2']}; border-radius: 4px; min-width: 24px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ height: 0; width: 0; }}
    """


# ─── Window sizing ────────────────────────────────────────────────────────────

def fit_dialog_to_screen(dialog: QWidget, target_w: int, target_h: int,
                          min_w: int, min_h: int, margin: int = 80) -> None:
    """Resizes a dialog toward (target_w, target_h) but never larger than the
    available screen geometry (minus a margin for the OS dock/menu bar/title
    bar), so it can't get clipped or spawn taller than the display."""
    screen = dialog.screen()
    if screen is None:
        app = QApplication.instance()
        screen = app.primaryScreen() if app else None
    if screen is not None:
        avail = screen.availableGeometry()
        max_w = max(min_w, avail.width() - margin)
        max_h = max(min_h, avail.height() - margin)
    else:
        max_w, max_h = target_w, target_h
    width = min(target_w, max_w)
    height = min(target_h, max_h)
    dialog.setMinimumSize(min(min_w, max_w), min(min_h, max_h))
    dialog.resize(width, height)


# ─── Image helpers ────────────────────────────────────────────────────────────

def circular_pixmap(source_image: QImage, size: int) -> QPixmap:
    if source_image.isNull():
        return QPixmap()
    render_size = size * 2
    if source_image.width() > source_image.height():
        scaled = source_image.scaledToHeight(render_size, Qt.TransformationMode.SmoothTransformation)
    else:
        scaled = source_image.scaledToWidth(render_size, Qt.TransformationMode.SmoothTransformation)
    x = (scaled.width() - render_size) / 2
    y = (scaled.height() - render_size) / 2
    cropped = scaled.copy(int(x), int(y), render_size, render_size)
    target = QPixmap(render_size, render_size)
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    path = QPainterPath()
    path.addEllipse(0, 0, render_size, render_size)
    painter.setClipPath(path)
    painter.drawImage(0, 0, cropped)
    painter.end()
    target.setDevicePixelRatio(2.0)
    return target


def render_icon_pixmap(addon_path: str, icon_value: str, color: str, size: int) -> QPixmap:
    """Resolve a deck-icon-picker value (emoji:/system:/filename) into a pixmap.

    Emoji sprites stay full-color; monochrome system/custom icons get tinted.
    Mirrors settings/_infra.py:_render_icon_value_pixmap.
    """
    from .assets import system_icon_path, svg_contain_rect
    from .emoji_sprites import path_for_emoji

    size = max(1, int(size))
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.setDevicePixelRatio(2.0)
    pixmap.fill(Qt.GlobalColor.transparent)
    if not icon_value:
        return pixmap
    icon_value = str(icon_value)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    try:
        if icon_value.startswith("emoji:"):
            sprite_path = path_for_emoji(addon_path, icon_value[len("emoji:"):])
            if sprite_path:
                renderer = QSvgRenderer(sprite_path)
                if renderer.isValid():
                    renderer.render(painter, svg_contain_rect(renderer, size))
            else:
                font = QFont()
                font.setPointSize(max(8, int(size * 0.7)))
                painter.setFont(font)
                painter.setPen(QColor(color))
                painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, icon_value[len("emoji:"):])
        else:
            path = ""
            if icon_value.startswith("system:"):
                path = system_icon_path(icon_value[len("system:"):])
            else:
                for folder in ("custom_deck_icons", "icons"):
                    candidate = os.path.join(addon_path, "user_files", folder, icon_value)
                    if os.path.exists(candidate):
                        path = candidate
                        break
                if not path:
                    path = system_icon_path(icon_value)
            if path and path.lower().endswith(".svg") and os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    svg_xml = f.read()
                if "currentColor" in svg_xml:
                    svg_xml = svg_xml.replace("currentColor", color)
                renderer = QSvgRenderer(svg_xml.encode("utf-8"))
                if renderer.isValid():
                    renderer.render(painter, svg_contain_rect(renderer, size))
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(QRectF(0, 0, size, size), QColor(color))
            elif path and os.path.exists(path):
                source = QPixmap(path)
                if not source.isNull():
                    scaled = source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    painter.drawPixmap(int((size - scaled.width()) / 2), int((size - scaled.height()) / 2), scaled)
    except Exception:
        pass
    painter.end()
    return pixmap


PREP_THUMBNAIL_DIR = "prep_station_thumbnails"


def plan_thumbnail_path(addon_path: str, plan: dict) -> str:
    filename = (plan or {}).get("thumbnail", "")
    if not filename:
        return ""
    path = os.path.join(addon_path, "user_files", PREP_THUMBNAIL_DIR, filename)
    return path if os.path.exists(path) else ""


def load_cover_pixmap(path: str, target_w: int, target_h: int) -> QPixmap | None:
    """Load an image scaled+center-cropped to fill a target_w x target_h box."""
    if not path or target_w <= 0 or target_h <= 0:
        return None
    source = QPixmap(path)
    if source.isNull():
        return None
    scaled = source.scaled(target_w, target_h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation)
    x = max(0, (scaled.width() - target_w) // 2)
    y = max(0, (scaled.height() - target_h) // 2)
    return scaled.copy(x, y, target_w, target_h)


def resolve_plan_color(plan: dict, dark: bool | None = None) -> str:
    """Resolves the plan's single effective accent color, honoring Dynamic
    Mode (separate light/dark colors) when enabled. With Dynamic Mode off,
    the Light Color doubles as the default color."""
    if dark is None:
        dark = theme_manager.night_mode
    if plan.get("color_dynamic") and dark:
        return plan.get("color_dark") or plan.get("color_light") or plan.get("color", "#3B82F6")
    return plan.get("color_light") or plan.get("color", "#3B82F6")


def blur_pixmap(pixmap: QPixmap, radius: float) -> QPixmap:
    """Gaussian-ish blur via QGraphicsBlurEffect, mirroring
    settings/_widgets.py's _blur_pixmap for the main background preview."""
    if pixmap.isNull() or radius <= 0:
        return pixmap
    from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(pixmap)
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(radius)
    item.setGraphicsEffect(effect)
    scene.addItem(item)
    scene.setSceneRect(QRectF(0, 0, pixmap.width(), pixmap.height()))
    blurred = QPixmap(pixmap.size())
    blurred.fill(Qt.GlobalColor.transparent)
    painter = QPainter(blurred)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    scene.render(painter)
    painter.end()
    return blurred


def paint_plan_band(painter: "QPainter", band_rect: QRectF, plan: dict, addon_path: str) -> str:
    """Fills band_rect with the plan's thumbnail photo (cover-fit, blurred
    and faded per its opacity/blur settings, over its accent color) or just
    the flat color when "Color only" is on or no photo is set. Caller must
    have already clipped to the card's rounded path. Returns the readable
    foreground color for text/icons drawn on top."""
    color = QColor(resolve_plan_color(plan))
    painter.fillRect(band_rect, QBrush(color))

    thumb_path = "" if plan.get("color_only") else plan_thumbnail_path(addon_path, plan)
    thumb = load_cover_pixmap(thumb_path, int(band_rect.width()), int(band_rect.height())) if thumb_path else None
    if thumb is not None:
        blur = max(0, min(100, plan.get("thumbnail_blur", 0)))
        if blur:
            thumb = blur_pixmap(thumb, blur * 0.3)
        opacity = max(0, min(100, plan.get("thumbnail_opacity", 100))) / 100.0
        painter.save()
        painter.setOpacity(opacity)
        painter.drawPixmap(band_rect.topLeft().toPoint(), thumb)
        painter.restore()
        grad = QLinearGradient(band_rect.left(), band_rect.top(), band_rect.left(), band_rect.bottom())
        grad.setColorAt(0.0, QColor(0, 0, 0, 50))
        grad.setColorAt(1.0, QColor(0, 0, 0, 165))
        painter.fillRect(band_rect, QBrush(grad))
        return "#ffffff" if opacity > 0.35 else readable_on(color.name())

    return readable_on(color.name())


def deck_icon_value(name: str, has_children: bool) -> str:
    """Resolve the icon_value (as consumed by render_icon_pixmap) for a deck,
    honoring per-deck custom icons and the Modern Menu icon-set overrides.
    Mirrors learner_stats_widget.py:_get_deck_icon_data (native-Qt variant)."""
    if not mw or not mw.col:
        return "deck.svg"
    did = mw.col.decks.id_for_name(name)
    custom_icons = mw.col.conf.get("onigiri_custom_deck_icons", {})
    custom_data = custom_icons.get(str(did), {}) if did is not None else {}
    icon_file = custom_data.get("icon")
    if icon_file:
        # Custom deck icons may be stored as a bare emoji glyph (no "emoji:"
        # prefix) — same heuristic as learner_stats_widget.py's mirror, so
        # those decks don't silently render blank in render_icon_pixmap.
        if (not icon_file.startswith("emoji:") and not icon_file.startswith("system:")
                and len(icon_file) <= 8 and "." not in icon_file):
            return f"emoji:{icon_file}"
        return icon_file

    is_filtered = False
    if did is not None:
        deck = mw.col.decks.get(did)
        if deck:
            is_filtered = deck.get("dyn", 0) != 0

    icon_key = "deck"
    if is_filtered:
        icon_key = "filtered_deck"
    elif has_children:
        icon_key = "folder"
    elif "::" in name:
        icon_key = "subdeck"

    filename = mw.col.conf.get(f"modern_menu_icon_{icon_key}", "")
    if filename:
        return filename

    system_filename = f"{icon_key}.svg"
    if icon_key == "filtered_deck":
        system_filename = "filtered-deck.svg"
    return system_filename


def emoji_char(icon_value: str) -> str:
    """Plain emoji char for HTML contexts; falls back to a generic glyph."""
    if icon_value and icon_value.startswith("emoji:"):
        return icon_value[len("emoji:"):]
    return "📘"


# ─── Weekly review chart ──────────────────────────────────────────────────────

class WeeklyChart(QWidget):
    """Smooth QPainter area+line chart of cards reviewed per day for the last 7 days."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values = [0] * 7
        self._labels = [""] * 7
        self._line_color = QColor("#3B82F6")
        self._fill_top = QColor(59, 130, 246, 80)
        self._fill_bottom = QColor(59, 130, 246, 0)
        self._label_color = QColor(255, 255, 255, 180)
        self.setMinimumSize(220, 72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

    def set_opacity(self, percent: int) -> None:
        self._opacity_effect.setOpacity(max(0, min(100, percent)) / 100.0)

    def set_data(self, values: list, labels: list) -> None:
        self._values = list(values) if values else [0] * 7
        self._labels = list(labels) if labels else [""] * len(self._values)
        self.update()

    def set_colors(self, line_color: str, label_color: str, fill_intensity: int = 50) -> None:
        self._line_color = QColor(line_color)
        top = QColor(line_color)
        top.setAlpha(max(0, min(255, int(fill_intensity * 2.2))))
        self._fill_top = top
        bottom = QColor(line_color)
        bottom.setAlpha(0)
        self._fill_bottom = bottom
        self._label_color = QColor(label_color)
        self.update()

    @staticmethod
    def _smooth_path(points: list) -> QPainterPath:
        path = QPainterPath()
        if not points:
            return path
        path.moveTo(points[0])
        for i in range(len(points) - 1):
            p0 = points[i]
            p1 = points[i + 1]
            mid_x = (p0.x() + p1.x()) / 2
            c1 = QPointF(mid_x, p0.y())
            c2 = QPointF(mid_x, p1.y())
            path.cubicTo(c1, c2, p1)
        return path

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pad_top, pad_bottom, pad_side = 8, 20, 8
        w = self.width() - pad_side * 2
        h = self.height() - pad_top - pad_bottom
        if w <= 0 or h <= 0 or not self._values:
            return

        max_val = max(max(self._values), 1)
        n = len(self._values)
        step = w / max(n - 1, 1)
        points = [
            QPointF(pad_side + i * step, pad_top + h - (v / max_val) * h)
            for i, v in enumerate(self._values)
        ]

        line_path = self._smooth_path(points)

        # Gradient fill below the curve
        fill_path = QPainterPath(line_path)
        fill_path.lineTo(points[-1].x(), pad_top + h)
        fill_path.lineTo(points[0].x(), pad_top + h)
        fill_path.closeSubpath()
        grad = QLinearGradient(0, pad_top, 0, pad_top + h)
        grad.setColorAt(0.0, self._fill_top)
        grad.setColorAt(1.0, self._fill_bottom)
        painter.fillPath(fill_path, QBrush(grad))

        # Line
        pen = QPen(self._line_color, 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(line_path)

        # End dot (today)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._line_color))
        painter.drawEllipse(points[-1], 3.2, 3.2)
        painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
        painter.drawEllipse(points[-1], 1.4, 1.4)

        # Labels
        painter.setPen(QPen(self._label_color))
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        for i, pt in enumerate(points):
            label = self._labels[i] if i < len(self._labels) else ""
            rect = QRectF(pt.x() - step / 2, pad_top + h + 3, step, pad_bottom - 2)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)


# ─── Settings live previews ───────────────────────────────────────────────────

class BgBarPreview(QWidget):
    """Rounded preview of the Prep Station header background (color or image)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(74)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._color = QColor("#3B82F6")
        self._image: QPixmap | None = None
        self._opacity = 1.0

    def set_background(self, color_hex: str, image: QPixmap | None, opacity: int) -> None:
        self._color = QColor(color_hex or "#3B82F6")
        self._image = image
        self._opacity = max(0, min(100, opacity)) / 100.0
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        painter.fillPath(path, QBrush(self._color))
        if self._image and not self._image.isNull():
            painter.save()
            painter.setClipPath(path)
            scaled = self._image.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                        Qt.TransformationMode.SmoothTransformation)
            x = (self.width() - scaled.width()) / 2
            y = (self.height() - scaled.height()) / 2
            painter.setOpacity(self._opacity)
            painter.drawPixmap(int(x), int(y), scaled)
            painter.restore()


class ChartPreview(QFrame):
    """A live WeeklyChart preview painted over the real Prep Station header
    background (color or image) so users see exactly how the chart will look."""

    SAMPLE = [4, 7, 5, 9, 6, 11, 8]

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self._band_color = QColor(pal["accent"])
        self._band_image: QPixmap | None = None
        self._band_opacity = 1.0
        self._line = "#ffffff"
        self._fill = 50
        self.setFixedHeight(88)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 6)
        self.chart = WeeklyChart(self)
        self.chart.set_data(self.SAMPLE, weekday_letters())
        lay.addWidget(self.chart)

    def set_band(self, color_hex: str, image: QPixmap | None, opacity: int) -> None:
        self._band_color = QColor(color_hex or self.pal["accent"])
        self._band_image = image
        self._band_opacity = max(0, min(100, opacity)) / 100.0
        self._apply_chart_colors()
        self.update()

    def set_colors(self, line_color: str, fill_intensity: int, chart_opacity: int) -> None:
        self._line = line_color
        self._fill = fill_intensity
        self.chart.set_opacity(chart_opacity)
        self._apply_chart_colors()

    def _apply_chart_colors(self) -> None:
        on_image = self._band_image is not None and not self._band_image.isNull()
        light_band = (not on_image) and readable_on(self._band_color.name()) == "#1a1a1a"
        label = "#1a1a1a" if light_band else "#ffffff"
        self.chart.set_colors(self._line, label, self._fill)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        painter.fillPath(path, QBrush(self._band_color))
        if self._band_image and not self._band_image.isNull():
            painter.save()
            painter.setClipPath(path)
            scaled = self._band_image.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                             Qt.TransformationMode.SmoothTransformation)
            x = (self.width() - scaled.width()) / 2
            y = (self.height() - scaled.height()) / 2
            painter.setOpacity(self._band_opacity)
            painter.drawPixmap(int(x), int(y), scaled)
            painter.restore()
            painter.setOpacity(1.0)
            overlay = QLinearGradient(0, 0, self.width(), 0)
            overlay.setColorAt(0.0, QColor(0, 0, 0, 90))
            overlay.setColorAt(1.0, QColor(0, 0, 0, 20))
            painter.fillPath(path, QBrush(overlay))


# ─── Header bar ───────────────────────────────────────────────────────────────

class HeaderBar(QWidget):
    """Top header: avatar + name on the left, weekly chart on the right, themed bg."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(108)
        self._bg_color = QColor("#3B82F6")
        self._bg_image: QPixmap | None = None
        self._bg_opacity = 1.0
        self._on_image = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 0, 24, 0)
        layout.setSpacing(16)

        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(54, 54)
        layout.addWidget(self.avatar_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.name_label = QLabel("")
        self.name_label.setStyleSheet("font-size: 21px; font-weight: 700; background: transparent;")
        layout.addWidget(self.name_label, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch(1)

        self.chart = WeeklyChart(self)
        self.chart.setFixedWidth(320)
        layout.addWidget(self.chart, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_profile(self, name: str, avatar_pixmap: QPixmap | None) -> None:
        self.name_label.setText(name or "")
        if avatar_pixmap and not avatar_pixmap.isNull():
            self.avatar_label.setPixmap(avatar_pixmap)
        else:
            self.avatar_label.clear()

    def set_background(self, color_hex: str, image: QPixmap | None, opacity: int) -> None:
        self._bg_color = QColor(color_hex or "#3B82F6")
        self._bg_image = image
        self._bg_opacity = max(0, min(100, opacity)) / 100.0
        self._on_image = bool(image and not image.isNull())
        # text color: white over images, contrast-aware over solid color
        fg = "#ffffff" if self._on_image else readable_on(self._bg_color.name())
        chart_label = QColor(255, 255, 255, 200) if fg == "#ffffff" else QColor(0, 0, 0, 150)
        self.name_label.setStyleSheet(f"font-size: 21px; font-weight: 700; color: {fg}; background: transparent;")
        self._chart_label_color = chart_label
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 20, 20)

        painter.fillPath(path, QBrush(self._bg_color))
        if self._on_image:
            painter.save()
            painter.setClipPath(path)
            scaled = self._bg_image.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) / 2
            y = (self.height() - scaled.height()) / 2
            painter.setOpacity(self._bg_opacity)
            painter.drawPixmap(int(x), int(y), scaled)
            painter.restore()
            painter.setOpacity(1.0)
            overlay = QLinearGradient(0, 0, self.width(), 0)
            overlay.setColorAt(0.0, QColor(0, 0, 0, 105))
            overlay.setColorAt(1.0, QColor(0, 0, 0, 25))
            painter.fillPath(path, QBrush(overlay))
        else:
            sheen = QLinearGradient(0, 0, self.width(), self.height())
            sheen.setColorAt(0.0, QColor(255, 255, 255, 30))
            sheen.setColorAt(1.0, QColor(0, 0, 0, 30))
            painter.fillPath(path, QBrush(sheen))


# ─── Exam card ────────────────────────────────────────────────────────────────

class ExamCard(QWidget):
    clicked = pyqtSignal(str)

    CARD_W = 232
    CARD_H = 206
    LONG_PRESS_MS = 380

    def __init__(self, plan: dict, pace: dict, addon_path: str, pal: dict, parent=None):
        super().__init__(parent)
        self.plan = plan
        self.pace = pace or {}
        self.addon_path = addon_path
        self.pal = pal
        self._hover = 0.0
        self._press_pos = None
        self._dragging = False
        self._reorder_container = None
        self.setFixedSize(self.CARD_W, self.CARD_H + 10)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_pix = render_icon_pixmap(addon_path, plan.get("icon", DEFAULT_ICON), "#ffffff", 26)
        self._anim = QPropertyAnimation(self, b"hoverProgress", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._longpress_timer = QTimer(self)
        self._longpress_timer.setSingleShot(True)
        self._longpress_timer.setInterval(self.LONG_PRESS_MS)
        self._longpress_timer.timeout.connect(self._maybe_start_reorder)

    def _get_hover(self):
        return self._hover

    def _set_hover(self, value):
        self._hover = value
        self.update()

    hoverProgress = pyqtProperty(float, _get_hover, _set_hover)

    def enterEvent(self, event):
        self._anim.stop(); self._anim.setStartValue(self._hover); self._anim.setEndValue(1.0); self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._anim.stop(); self._anim.setStartValue(self._hover); self._anim.setEndValue(0.0); self._anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            self._dragging = False
            self._longpress_timer.start()
        super().mousePressEvent(event)

    def _maybe_start_reorder(self) -> None:
        if self._press_pos is None or self._dragging:
            return
        if not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            return
        container = self._find_cards_container()
        if container is None:
            return
        self._dragging = True
        self._reorder_container = container
        container.begin_reorder(self, QCursor.pos())

    def _find_cards_container(self) -> "PlanCardsContainer | None":
        w = self.parentWidget()
        while w is not None and not isinstance(w, PlanCardsContainer):
            w = w.parentWidget()
        return w

    def mouseMoveEvent(self, event):
        if self._dragging and self._reorder_container is not None:
            self._reorder_container.update_drag(event.globalPosition().toPoint())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._longpress_timer.isActive():
            self._longpress_timer.stop()
        if event.button() == Qt.MouseButton.LeftButton:
            if self._dragging:
                container = self._reorder_container
                self._dragging = False
                self._reorder_container = None
                self._press_pos = None
                if container is not None:
                    container.end_reorder(event.globalPosition().toPoint())
                # `self` may have just been deleted (the container's commit
                # rebuilds the whole grid) — do not touch it beyond this point.
                return
            if self._press_pos is not None:
                self._press_pos = None
                self.clicked.emit(self.plan.get("id", ""))
                return
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        p = self.pal
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = QRectF(3, 7, self.CARD_W - 6, self.CARD_H)
        radius = 18

        scale = 1.0 + self._hover * 0.02
        painter.save()
        center = rect.center()
        painter.translate(center)
        painter.scale(scale, scale)
        painter.translate(-center)

        full_path = QPainterPath()
        full_path.addRoundedRect(rect, radius, radius)
        painter.fillPath(full_path, QBrush(QColor(p["surface"])))

        band_h = 92
        band_rect = QRectF(rect.left(), rect.top(), rect.width(), band_h)
        painter.save()
        painter.setClipPath(full_path)
        fg_on_band = paint_plan_band(painter, band_rect, self.plan, self.addon_path)
        painter.restore()

        # Icon (top-left)
        if not self._icon_pix.isNull():
            icon = self._icon_pix
            if fg_on_band != "#ffffff":
                icon = render_icon_pixmap(self.addon_path, self.plan.get("icon", DEFAULT_ICON), fg_on_band, 26)
            painter.drawPixmap(int(rect.left() + 16), int(rect.top() + 16), 26, 26, icon)

        # Days-left pill (top-right)
        days_left = self.pace.get("days_left")
        if days_left is not None:
            if days_left == 0:
                badge_text = tr("prep_today_badge")
            elif days_left > 0:
                badge_text = tr("prep_days_left_badge").format(days_left)
            else:
                badge_text = tr("prep_past_badge")
            badge_font = QFont(); badge_font.setPointSize(8); badge_font.setBold(True)
            painter.setFont(badge_font)
            fm = QFontMetrics(badge_font)
            bw = fm.horizontalAdvance(badge_text) + 18
            badge_rect = QRectF(rect.right() - bw - 14, rect.top() + 15, bw, 20)
            bpath = QPainterPath(); bpath.addRoundedRect(badge_rect, 10, 10)
            painter.fillPath(bpath, QBrush(QColor(0, 0, 0, 75) if fg_on_band == "#ffffff" else QColor(255, 255, 255, 120)))
            painter.setPen(QPen(QColor(fg_on_band)))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        # Plan name (bottom of band)
        name_font = QFont(); name_font.setPointSize(13); name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QPen(QColor(fg_on_band)))
        fm = QFontMetrics(name_font)
        name = fm.elidedText(self.plan.get("name", tr("prep_default_exam_name")), Qt.TextElideMode.ElideRight, int(rect.width() - 32))
        painter.drawText(QRectF(rect.left() + 16, rect.top() + band_h - 32, rect.width() - 32, 26),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        # Body: pace number
        body_top = rect.top() + band_h
        req = self.pace.get("required_per_day")
        status = self.pace.get("status", "")
        if status == "expired":
            big, small = "—", tr("prep_exam_has_passed")
        elif req is None:
            big, small = "—", tr("prep_set_date_and_decks")
        elif status == "done":
            big, small = "✓", tr("prep_all_caught_up")
        else:
            big, small = f"{req:.0f}", tr("prep_cards_per_day_unit")

        num_font = QFont(); num_font.setPointSize(26); num_font.setBold(True)
        painter.setFont(num_font)
        painter.setPen(QPen(QColor(resolve_plan_color(self.plan) or p["accent"])))
        painter.drawText(QRectF(rect.left() + 16, body_top + 12, rect.width() - 32, 36),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, big)
        fm_num = QFontMetrics(num_font)
        num_w = fm_num.horizontalAdvance(big)
        unit_font = QFont(); unit_font.setPointSize(9)
        painter.setFont(unit_font)
        painter.setPen(QPen(QColor(p["fg3"])))
        painter.drawText(QRectF(rect.left() + 16 + num_w + 7, body_top + 12, rect.width() - 32 - num_w, 36),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, small)

        painter.restore()


class AddExamCard(QWidget):
    clicked = pyqtSignal()

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self._hover = False
        self.setFixedSize(ExamCard.CARD_W, ExamCard.CARD_H + 10)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event):
        self._hover = True; self.update(); super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False; self.update(); super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        p = self.pal
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(3, 7, ExamCard.CARD_W - 6, ExamCard.CARD_H)
        path = QPainterPath(); path.addRoundedRect(rect, 18, 18)
        accent = QColor(p["accent"])
        painter.fillPath(path, QBrush(with_alpha(p["accent"], 22 if self._hover else 10)))
        pen = QPen(accent if self._hover else QColor(p["border2"]), 1.6, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawPath(path)
        painter.setPen(QPen(accent))
        plus_font = QFont(); plus_font.setPointSize(30); plus_font.setWeight(QFont.Weight.Light)
        painter.setFont(plus_font)
        painter.drawText(QRectF(rect.left(), rect.center().y() - 34, rect.width(), 50),
                         Qt.AlignmentFlag.AlignCenter, "+")
        label_font = QFont(); label_font.setPointSize(10); label_font.setBold(True)
        painter.setFont(label_font)
        painter.setPen(QPen(accent if self._hover else QColor(p["fg2"])))
        painter.drawText(QRectF(rect.left(), rect.center().y() + 14, rect.width(), 24),
                         Qt.AlignmentFlag.AlignCenter, tr("prep_new_plan"))


class _PlaceholderCard(QWidget):
    """Dashed rounded slot shown in the grid at the spot the dragged card
    would land, while the real card is dimmed to nothing and floats as a
    ghost preview under the cursor."""

    def __init__(self, size, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.setFixedSize(size)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(3, 7, self.width() - 6, self.height() - 10)
        path = QPainterPath()
        path.addRoundedRect(rect, 18, 18)
        painter.fillPath(path, QBrush(with_alpha(self.pal["accent"], 20)))
        painter.setPen(QPen(QColor(self.pal["accent"]), 2, Qt.PenStyle.DashLine))
        painter.drawPath(path)


class _DragGhost(QWidget):
    """Floating rounded preview of the card being reordered; follows the cursor."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self.resize(pixmap.size())
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(3, 7, self.width() - 6, self.height() - 10), 18, 18)
        painter.setOpacity(0.97)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, self._pixmap)


class PlanCardsContainer(QWidget):
    """Hosts the ExamCard flow layout. Long-pressing a card enters a reorder
    mode: the other cards dim, the pressed card lifts into a floating rounded
    preview that follows the cursor, and a dashed placeholder in the grid
    shows exactly where it will land. Releasing commits the new order;
    Escape (or releasing over nothing useful) restores the original order."""

    orderCommitted = pyqtSignal(str, int)

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self._dragged_card = None
        self._origin_index = -1
        self._placeholder = None
        self._ghost = None
        self._dim_effects = {}

    def is_reordering(self) -> bool:
        return self._dragged_card is not None

    def begin_reorder(self, card: "ExamCard", global_pos) -> None:
        if self._dragged_card is not None:
            return
        layout = self.layout()
        origin_index = layout.indexOf(card)
        if origin_index < 0:
            return
        self._dragged_card = card
        self._origin_index = origin_index
        card_pixmap = card.grab()

        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if w is None or w is card:
                continue
            effect = QGraphicsOpacityEffect(w)
            effect.setOpacity(0.35)
            w.setGraphicsEffect(effect)
            self._dim_effects[w] = effect

        # Keep the real card alive and receiving mouse events (Qt keeps
        # delivering them to whatever widget took the initial press) but
        # fully transparent and out of the layout, so only the ghost is seen.
        dragged_effect = QGraphicsOpacityEffect(card)
        dragged_effect.setOpacity(0.0)
        card.setGraphicsEffect(dragged_effect)
        layout.takeAt(origin_index)

        self._placeholder = _PlaceholderCard(card.size(), self.pal, self)
        layout.insertWidget(origin_index, self._placeholder)
        self._placeholder.show()

        self._ghost = _DragGhost(card_pixmap, self)
        self._ghost.show()
        self._ghost.raise_()
        self._move_ghost(global_pos)
        layout.invalidate()

    def update_drag(self, global_pos) -> None:
        if self._dragged_card is None:
            return
        self._move_ghost(global_pos)
        target_index = self._plan_index_for_pos(self.mapFromGlobal(global_pos))
        if target_index == self._placeholder_plan_index():
            return
        layout = self.layout()
        raw = layout.indexOf(self._placeholder)
        if raw >= 0:
            layout.takeAt(raw)
        layout.insertWidget(self._raw_insert_index(target_index), self._placeholder)
        layout.invalidate()

    def end_reorder(self, global_pos) -> None:
        if self._dragged_card is None:
            return
        plan_id = self._dragged_card.plan.get("id", "")
        final_index = self._placeholder_plan_index()
        self._teardown(delete_card=True)
        self.orderCommitted.emit(plan_id, final_index)

    def cancel_reorder(self) -> None:
        if self._dragged_card is None:
            return
        card = self._dragged_card
        origin_index = self._origin_index
        self._teardown(delete_card=False)
        layout = self.layout()
        layout.insertWidget(min(origin_index, layout.count()), card)
        card.setGraphicsEffect(None)
        layout.invalidate()

    def _teardown(self, delete_card: bool) -> None:
        layout = self.layout()
        if self._placeholder is not None:
            idx = layout.indexOf(self._placeholder)
            if idx >= 0:
                layout.takeAt(idx)
            self._placeholder.deleteLater()
            self._placeholder = None
        if self._ghost is not None:
            self._ghost.deleteLater()
            self._ghost = None
        for w, effect in self._dim_effects.items():
            try:
                w.setGraphicsEffect(None)
            except RuntimeError:
                pass
        self._dim_effects.clear()
        if self._dragged_card is not None and delete_card:
            self._dragged_card.deleteLater()
        self._dragged_card = None
        self._origin_index = -1

    def _move_ghost(self, global_pos) -> None:
        if self._ghost is None:
            return
        local = self.mapFromGlobal(global_pos)
        self._ghost.move(local.x() - self._ghost.width() // 2, local.y() - self._ghost.height() // 2)

    def _plan_index_for_pos(self, pos) -> int:
        layout = self.layout()
        cards = [layout.itemAt(i).widget() for i in range(layout.count())] if layout else []
        cards = [w for w in cards if isinstance(w, ExamCard)]
        if not cards:
            return 0
        best_index = len(cards)
        best_dist = None
        for i, w in enumerate(cards):
            center = w.geometry().center()
            dist = (center.x() - pos.x()) ** 2 + (center.y() - pos.y()) ** 2
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_index = i if pos.x() < center.x() else i + 1
        return best_index

    def _placeholder_plan_index(self) -> int:
        layout = self.layout()
        idx = layout.indexOf(self._placeholder) if self._placeholder is not None else -1
        if idx < 0:
            return 0
        count = 0
        for i in range(idx):
            if isinstance(layout.itemAt(i).widget(), ExamCard):
                count += 1
        return count

    def _raw_insert_index(self, plan_index: int) -> int:
        layout = self.layout()
        seen = 0
        add_card_raw = layout.count()
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if isinstance(w, AddExamCard):
                add_card_raw = i
            elif isinstance(w, ExamCard):
                if seen == plan_index:
                    return i
                seen += 1
        return add_card_raw


# ─── Plan detail view ──────────────────────────────────────────────────────────

class PlanDetailBanner(QFrame):
    """Larger, full-width variant of ExamCard's band: thumbnail/color, icon,
    plan name, exam date and days-left badge."""

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.addon_path = ""
        self.plan = {}
        self.pace = {}
        self.setFixedHeight(132)
        self.setMinimumWidth(200)

    def set_plan(self, plan: dict, pace: dict, addon_path: str) -> None:
        self.plan = plan or {}
        self.pace = pace or {}
        self.addon_path = addon_path
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = QRectF(0, 0, self.width(), self.height())
        radius = 18
        path = QPainterPath(); path.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(path)
        fg = paint_plan_band(painter, rect, self.plan, self.addon_path)
        painter.restore()

        icon_pix = render_icon_pixmap(self.addon_path, self.plan.get("icon", DEFAULT_ICON), fg, 30)
        if not icon_pix.isNull():
            painter.drawPixmap(int(rect.left() + 20), int(rect.top() + 18), 30, 30, icon_pix)

        days_left = self.pace.get("days_left")
        if days_left is not None:
            if days_left == 0:
                badge_text = tr("prep_today_badge")
            elif days_left > 0:
                badge_text = tr("prep_days_left_badge").format(days_left)
            else:
                badge_text = tr("prep_past_badge")
            badge_font = QFont(); badge_font.setPointSize(9); badge_font.setBold(True)
            painter.setFont(badge_font)
            fm = QFontMetrics(badge_font)
            bw = fm.horizontalAdvance(badge_text) + 20
            badge_rect = QRectF(rect.right() - bw - 18, rect.top() + 18, bw, 24)
            bpath = QPainterPath(); bpath.addRoundedRect(badge_rect, 12, 12)
            painter.fillPath(bpath, QBrush(QColor(0, 0, 0, 75) if fg == "#ffffff" else QColor(255, 255, 255, 120)))
            painter.setPen(QPen(QColor(fg)))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        name_font = QFont(); name_font.setPointSize(17); name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QPen(QColor(fg)))
        fm = QFontMetrics(name_font)
        name = fm.elidedText(self.plan.get("name", tr("prep_default_exam_name")), Qt.TextElideMode.ElideRight, int(rect.width() - 40))
        painter.drawText(QRectF(rect.left() + 20, rect.bottom() - 50, rect.width() - 40, 30),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        exam_date = self.plan.get("exam_date", "")
        if exam_date:
            sub_font = QFont(); sub_font.setPointSize(10)
            painter.setFont(sub_font)
            painter.setPen(QPen(QColor(fg)))
            painter.drawText(QRectF(rect.left() + 20, rect.bottom() - 22, rect.width() - 40, 18),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, exam_date)


class _DetailStatTile(QFrame):
    def __init__(self, pal: dict, sub_text: str, parent=None):
        super().__init__(parent)
        self.pal = pal
        self._color = pal["accent"]
        self.setObjectName("psDetailStatTile")
        self.setStyleSheet(
            f"QFrame#psDetailStatTile {{ background: {pal['surface']}; border: 1px solid {pal['border']}; border-radius: 16px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(2)
        self.value_label = QLabel("—")
        self.value_label.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {self._color}; background: transparent;")
        layout.addWidget(self.value_label)
        self.sub_label = QLabel(sub_text)
        self.sub_label.setWordWrap(True)
        self.sub_label.setStyleSheet(f"font-size: 11px; color: {pal['fg3']}; background: transparent;")
        layout.addWidget(self.sub_label)

    def set_value(self, value_text: str, sub_text: str) -> None:
        self.value_label.setText(value_text)
        self.sub_label.setText(sub_text)

    def set_color(self, color: str) -> None:
        self._color = color
        self.value_label.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {self._color}; background: transparent;")


class _StackedBar(QWidget):
    """Tiny rounded horizontal bar: a solid 'due' segment (pressing work) plus a
    translucent 'new' segment, both tinted with the plan colour, over a track."""

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self._due = 0
        self._new = 0
        self._color = pal["accent"]
        self.setFixedHeight(6)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, new: int, due: int, color: str) -> None:
        self._new, self._due, self._color = max(0, new), max(0, due), color
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        r = rect.height() / 2
        track = QPainterPath(); track.addRoundedRect(rect, r, r)
        painter.fillPath(track, QBrush(QColor(self.pal["surface2"])))
        total = self._new + self._due
        if total <= 0 or rect.width() <= 0:
            return
        painter.setClipPath(track)
        due_w = rect.width() * (self._due / total)
        painter.fillRect(QRectF(0, 0, due_w, rect.height()), QBrush(QColor(self._color)))
        soft = QColor(self._color); soft.setAlpha(95)
        painter.fillRect(QRectF(due_w, 0, rect.width() - due_w, rect.height()), QBrush(soft))


class _RatioBar(QWidget):
    """Single rounded progress bar (recent pace ÷ target), with a subtle marker
    at the 100% target line so 'behind' vs 'ahead' reads at a glance."""

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self._frac = 0.0
        self._color = pal["accent"]
        self.setFixedHeight(8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_fraction(self, frac: float, color: str) -> None:
        self._frac = max(0.0, min(1.0, frac))
        self._color = color
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        r = rect.height() / 2
        track = QPainterPath(); track.addRoundedRect(rect, r, r)
        painter.fillPath(track, QBrush(QColor(self.pal["surface2"])))
        if rect.width() <= 0:
            return
        painter.setClipPath(track)
        fill_w = rect.width() * self._frac
        if fill_w > 0:
            painter.fillRect(QRectF(0, 0, fill_w, rect.height()), QBrush(QColor(self._color)))


class _DeckBreakdownCard(QFrame):
    """Per-deck workload: each assigned deck's pending new/due counts with a
    stacked mini bar, sorted by how much work is left. Fills the detail page
    with the plan's actual composition instead of a single aggregate number."""

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.setObjectName("psDeckCard")
        self.setStyleSheet(
            f"QFrame#psDeckCard {{ background: {pal['surface']}; border: 1px solid {pal['border']}; border-radius: 16px; }}"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 16)
        outer.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(8)
        tag = QLabel(tr("prep_deck_breakdown", "DECK BREAKDOWN"))
        tag.setStyleSheet(f"font-size: 9px; font-weight: 800; letter-spacing: 1.5px; color: {pal['fg3']}; background: transparent;")
        header.addWidget(tag)
        header.addStretch(1)
        self.legend = QLabel()
        self.legend.setStyleSheet("background: transparent;")
        header.addWidget(self.legend)
        outer.addLayout(header)

        self.rows_holder = QVBoxLayout()
        self.rows_holder.setSpacing(12)
        outer.addLayout(self.rows_holder)
        outer.addStretch(1)

    def set_decks(self, deck_counts: dict, color: str) -> None:
        p = self.pal
        while self.rows_holder.count():
            it = self.rows_holder.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        qc = QColor(color)
        soft_rgba = f"rgba({qc.red()},{qc.green()},{qc.blue()},0.42)"
        self.legend.setText(
            f'<span style="color:{color};">&#9679;</span> '
            f'<span style="color:{p["fg3"]};">{tr("prep_legend_due", "due")}</span>'
            f'&nbsp;&nbsp;<span style="color:{soft_rgba};">&#9679;</span> '
            f'<span style="color:{p["fg3"]};">{tr("prep_legend_new", "new")}</span>'
        )

        if not deck_counts:
            empty = QLabel(tr("prep_no_decks", "No decks assigned to this plan yet."))
            empty.setStyleSheet(f"font-size: 12px; color: {p['fg3']}; background: transparent;")
            self.rows_holder.addWidget(empty)
            return

        items = sorted(
            deck_counts.items(),
            key=lambda kv: -((kv[1].get("new", 0)) + (kv[1].get("due", 0))),
        )
        for name, c in items[:8]:
            new_n = int(c.get("new", 0))
            due_n = int(c.get("due", 0))
            pending = new_n + due_n

            row = QWidget()
            rl = QVBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(5)

            top = QHBoxLayout()
            top.setSpacing(8)
            leaf = str(name).split("::")[-1]
            if len(leaf) > 30:
                leaf = leaf[:29] + "…"
            name_label = QLabel(leaf)
            dim = pending == 0
            name_label.setStyleSheet(
                f"font-size: 12.5px; font-weight: 600; color: {p['fg3'] if dim else p['fg']}; background: transparent;"
            )
            top.addWidget(name_label, 1)
            if pending == 0:
                count_label = QLabel(tr("prep_deck_done", "done ✓"))
                count_label.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {p['fg3']}; background: transparent;")
            else:
                count_label = QLabel(tr("prep_new_due_split", "{0} new · {1} due").format(new_n, due_n))
                count_label.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {p['fg2']}; background: transparent;")
            top.addWidget(count_label, 0)
            rl.addLayout(top)

            bar = _StackedBar(p)
            bar.set_data(new_n, due_n, color)
            rl.addWidget(bar)

            self.rows_holder.addWidget(row)

        extra = len(items) - 8
        if extra > 0:
            more = QLabel(tr("prep_more_decks", "+{0} more").format(extra))
            more.setStyleSheet(f"font-size: 11px; color: {p['fg3']}; background: transparent;")
            self.rows_holder.addWidget(more)


class _PaceInsightCard(QFrame):
    """Turns the raw pace number into a verdict: compares the last 7 days' actual
    review pace against the required pace and projects finishing early or late."""

    GOOD = "#10B981"
    WARN = "#F59E0B"

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.setObjectName("psPaceCard")
        self.setStyleSheet(
            f"QFrame#psPaceCard {{ background: {pal['surface']}; border: 1px solid {pal['border']}; border-radius: 16px; }}"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 16)
        outer.setSpacing(8)

        tag = QLabel(tr("prep_pace_check", "PACE CHECK"))
        tag.setStyleSheet(f"font-size: 9px; font-weight: 800; letter-spacing: 1.5px; color: {pal['fg3']}; background: transparent;")
        outer.addWidget(tag)

        self.status_label = QLabel("—")
        self.status_label.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {pal['fg']}; background: transparent;")
        outer.addWidget(self.status_label)

        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet(f"font-size: 11.5px; font-weight: 600; color: {pal['fg2']}; background: transparent;")
        outer.addWidget(self.detail_label)

        self.bar = _RatioBar(pal)
        outer.addSpacing(2)
        outer.addWidget(self.bar)

        self.proj_label = QLabel("")
        self.proj_label.setWordWrap(True)
        self.proj_label.setStyleSheet(f"font-size: 11.5px; color: {pal['fg3']}; background: transparent;")
        outer.addSpacing(2)
        outer.addWidget(self.proj_label)
        outer.addStretch(1)

    def set_data(self, pace: dict, weekly_counts: list, color: str) -> None:
        p = self.pal
        status = pace.get("status", "")
        days_left = pace.get("days_left")
        total_pending = int(pace.get("total_pending", 0) or 0)
        required = pace.get("required_per_day")
        recent = (sum(weekly_counts) / 7.0) if weekly_counts else 0.0

        accent_status = p["fg"]
        detail = ""
        proj = ""
        frac = 0.0
        bar_color = color

        if status == "expired":
            head = tr("prep_pace_expired", "Exam has passed")
            accent_status = p["fg3"]
            proj = tr("prep_pace_proj_expired", "This plan's exam date is in the past.")
        elif status == "done" or total_pending == 0:
            head = tr("prep_pace_caughtup", "All caught up")
            accent_status = self.GOOD
            frac = 1.0
            bar_color = self.GOOD
            proj = tr("prep_pace_proj_done", "Nothing left to review — nicely done. 🎉")
        else:
            target = float(required or 0)
            detail = tr("prep_pace_target_recent", "Target {0}/day · Recent {1}/day").format(
                f"{target:.0f}", f"{recent:.0f}"
            )
            frac = (recent / target) if target > 0 else 0.0
            if recent <= 0:
                head = tr("prep_pace_notstarted", "Not started yet")
                accent_status = p["fg3"]
                proj = tr("prep_pace_proj_none", "No reviews in the last 7 days — start today.")
            else:
                days_to_finish = total_pending / recent
                margin = (days_left if days_left is not None else 0) - days_to_finish
                if margin >= 0:
                    if recent >= target * 1.15:
                        head = tr("prep_pace_ahead", "Ahead of pace")
                    else:
                        head = tr("prep_pace_ontrack", "On track")
                    accent_status = self.GOOD
                    bar_color = self.GOOD
                    proj = tr(
                        "prep_pace_proj_early",
                        "At ~{0}/day you'll finish about {1}d before the exam.",
                    ).format(f"{recent:.0f}", f"{margin:.0f}")
                else:
                    head = tr("prep_pace_behind", "Falling behind")
                    accent_status = self.WARN
                    bar_color = self.WARN
                    proj = tr(
                        "prep_pace_proj_late",
                        "At ~{0}/day you'd finish ~{1}d late — aim for {2}/day.",
                    ).format(f"{recent:.0f}", f"{abs(margin):.0f}", f"{target:.0f}")

        self.status_label.setText(head)
        self.status_label.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {accent_status}; background: transparent;")
        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))
        self.bar.set_fraction(frac, bar_color)
        self.proj_label.setText(proj)


class PlanDetailView(QWidget):
    """Embedded (non-popup) detail page for a single plan: shown inside
    PrepStationDialog's stack when a card is clicked."""

    backRequested = pyqtSignal()
    editRequested = pyqtSignal(str)
    deleteRequested = pyqtSignal(str)

    def __init__(self, addon_path: str, pal: dict, parent=None):
        super().__init__(parent)
        self.addon_path = addon_path
        self.pal = pal
        self._plan_id = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        back_btn = QPushButton(f"←  {tr('prep_back')}")
        back_btn.setProperty("psGhost", True)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.backRequested.emit)
        top_row.addWidget(back_btn)
        top_row.addStretch(1)
        edit_btn = self._pill_button(tr("prep_edit"), "ghost")
        edit_btn.clicked.connect(lambda: self.editRequested.emit(self._plan_id))
        top_row.addWidget(edit_btn)
        del_btn = self._pill_button(tr("prep_delete"), "danger")
        del_btn.clicked.connect(lambda: self.deleteRequested.emit(self._plan_id))
        top_row.addWidget(del_btn)
        layout.addLayout(top_row)

        # Everything below the action row scrolls, so the page stays usable on
        # short windows even with the richer breakdown/pace content.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        content = QWidget()
        content.setAutoFillBackground(False)
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 4, 0)
        body.setSpacing(14)
        layout.addWidget(scroll, 1)
        scroll.setWidget(content)

        self.banner = PlanDetailBanner(pal)
        body.addWidget(self.banner)

        # ── Stat tiles: pace, days left, cards remaining, reviewed this week ──
        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)
        self.pace_tile = _DetailStatTile(pal, tr("prep_cards_per_day_unit"))
        self.days_tile = _DetailStatTile(pal, tr("prep_days_left_unit", "days left"))
        self.remaining_tile = _DetailStatTile(pal, tr("prep_cards_remaining", "cards remaining"))
        self.week_tile = _DetailStatTile(pal, tr("prep_reviewed_this_week", "reviewed this week"))
        for tile in (self.pace_tile, self.days_tile, self.remaining_tile, self.week_tile):
            stats_row.addWidget(tile, 1)
        body.addLayout(stats_row)

        # ── Deck breakdown (left) + pace insight (right) ──
        mid_row = QHBoxLayout()
        mid_row.setSpacing(14)
        self.deck_card = _DeckBreakdownCard(pal)
        self.pace_card = _PaceInsightCard(pal)
        mid_row.addWidget(self.deck_card, 3)
        mid_row.addWidget(self.pace_card, 2)
        body.addLayout(mid_row)

        chart_card = QFrame()
        chart_card.setObjectName("psDetailChartCard")
        chart_card.setStyleSheet(
            f"QFrame#psDetailChartCard {{ background: {pal['surface']}; border: 1px solid {pal['border']}; border-radius: 16px; }}"
        )
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(18, 14, 18, 10)
        chart_tag = QLabel(tr("prep_this_week"))
        chart_tag.setStyleSheet(f"font-size: 9px; font-weight: 800; letter-spacing: 1.5px; color: {pal['fg3']}; background: transparent;")
        chart_layout.addWidget(chart_tag)
        self.chart = WeeklyChart(chart_card)
        self.chart.setFixedHeight(74)
        self.chart.set_colors(pal["accent"], pal["fg3"], 45)
        chart_layout.addWidget(self.chart)
        body.addWidget(chart_card)
        body.addStretch(1)

    def _pill_button(self, text: str, kind: str) -> QPushButton:
        """Fully-rounded action button (Berry-style pill)."""
        pal = self.pal
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(34)
        if kind == "primary":
            accent = pal["accent"]
            hover = QColor(accent).lighter(112).name()
            btn.setStyleSheet(
                f"QPushButton {{ background: {accent}; color: #ffffff; border: none; "
                f"border-radius: 17px; padding: 0 18px; font-weight: 700; }}"
                f"QPushButton:hover {{ background: {hover}; }}"
            )
        elif kind == "danger":
            btn.setStyleSheet(
                "QPushButton { background: transparent; color: #ef4444; border: 1px solid rgba(239,68,68,0.45); "
                "border-radius: 17px; padding: 0 16px; font-weight: 600; }"
                "QPushButton:hover { background: rgba(239,68,68,0.14); }"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {pal['fg2']}; border: 1px solid {pal['border2']}; "
                f"border-radius: 17px; padding: 0 16px; font-weight: 600; }}"
                f"QPushButton:hover {{ background: {pal['hover']}; color: {pal['fg']}; }}"
            )
        return btn

    def set_plan(self, plan: dict, pace: dict, weekly_counts: list, weekly_labels: list) -> None:
        self._plan_id = plan.get("id", "")
        self.banner.set_plan(plan, pace, self.addon_path)

        plan_color = resolve_plan_color(plan) or self.pal["accent"]
        for tile in (self.pace_tile, self.days_tile, self.remaining_tile, self.week_tile):
            tile.set_color(plan_color)
        self.chart.set_colors(plan_color, self.pal["fg3"], 45)

        req = pace.get("required_per_day")
        status = pace.get("status", "")

        # Pace tile
        if status == "expired":
            self.pace_tile.set_value("—", tr("prep_exam_has_passed"))
        elif req is None:
            self.pace_tile.set_value("—", tr("prep_set_date_and_decks"))
        elif status == "done":
            self.pace_tile.set_value("✓", tr("prep_all_caught_up"))
        else:
            self.pace_tile.set_value(f"{req:.0f}", tr("prep_cards_per_day_unit"))

        # Days-left tile
        days_left = pace.get("days_left")
        if days_left is None:
            self.days_tile.set_value("—", tr("prep_days_left_unit", "days left"))
        elif days_left < 0:
            self.days_tile.set_value(str(abs(days_left)), tr("prep_days_over_unit", "days ago"))
        elif days_left == 0:
            self.days_tile.set_value("0", tr("prep_exam_is_today", "exam is today"))
        else:
            self.days_tile.set_value(str(days_left), tr("prep_days_left_unit", "days left"))

        # Cards-remaining tile (with new · due split as subtext)
        total_pending = int(pace.get("total_pending", 0) or 0)
        total_new = int(pace.get("total_new", 0) or 0)
        total_due = int(pace.get("total_due", 0) or 0)
        if req is None:
            self.remaining_tile.set_value("—", tr("prep_cards_remaining", "cards remaining"))
        elif total_pending == 0:
            self.remaining_tile.set_value("0", tr("prep_all_caught_up"))
        else:
            self.remaining_tile.set_value(
                f"{total_pending:,}".replace(",", " "),
                tr("prep_new_due_split", "{0} new · {1} due").format(total_new, total_due),
            )

        # Reviewed-this-week tile
        week_total = int(sum(weekly_counts)) if weekly_counts else 0
        self.week_tile.set_value(
            f"{week_total:,}".replace(",", " "),
            tr("prep_reviewed_this_week", "reviewed this week"),
        )

        # Deck breakdown + pace insight
        self.deck_card.set_decks(pace.get("deck_counts", {}) or {}, plan_color)
        self.pace_card.set_data(pace, weekly_counts, plan_color)

        self.chart.set_data(weekly_counts, weekly_labels)


# ─── Custom calendar ──────────────────────────────────────────────────────────

class CalendarGrid(QWidget):
    """Painted month grid with today highlight and exam-date dots."""

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self._year = date.today().year
        self._month = date.today().month
        self._marks = {}  # date -> [colors]
        self.setFixedHeight(192)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_month(self, year: int, month: int) -> None:
        self._year, self._month = year, month
        self.update()

    def set_marks(self, marks: dict) -> None:
        self._marks = marks or {}
        self.update()

    def _first_weekday_and_days(self):
        import calendar
        first_weekday, days_in_month = calendar.monthrange(self._year, self._month)  # Mon=0
        return first_weekday, days_in_month

    def paintEvent(self, event) -> None:
        p = self.pal
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        cols = 7
        cell_w = self.width() / cols
        header_h = 22
        first_weekday, days_in_month = self._first_weekday_and_days()
        total_cells = first_weekday + days_in_month
        rows = (total_cells + 6) // 7
        cell_h = (self.height() - header_h) / max(rows, 1)

        # Weekday header
        wd_font = QFont(); wd_font.setPointSize(8); wd_font.setBold(True)
        painter.setFont(wd_font)
        painter.setPen(QPen(QColor(p["fg3"])))
        for i, letter in enumerate(weekday_letters()):
            painter.drawText(QRectF(i * cell_w, 0, cell_w, header_h), Qt.AlignmentFlag.AlignCenter, letter)

        today = date.today()
        day_font = QFont(); day_font.setPointSize(10)
        for day in range(1, days_in_month + 1):
            idx = first_weekday + (day - 1)
            r, c = divmod(idx, 7)
            cx = c * cell_w + cell_w / 2
            cy = header_h + r * cell_h + cell_h / 2
            d = date(self._year, self._month, day)
            is_today = (d == today)

            if is_today:
                diameter = min(cell_w, cell_h) - 8
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(p["accent"])))
                painter.drawEllipse(QPointF(cx, cy - 2), diameter / 2, diameter / 2)
                painter.setPen(QPen(QColor("#ffffff")))
            else:
                painter.setPen(QPen(QColor(p["fg"])))

            day_font.setBold(is_today)
            painter.setFont(day_font)
            painter.drawText(QRectF(cx - cell_w / 2, cy - cell_h / 2 - 2, cell_w, cell_h),
                             Qt.AlignmentFlag.AlignCenter, str(day))

            marks = self._marks.get(d)
            if marks and not is_today:
                dot_n = min(len(marks), 3)
                spacing = 7
                start_x = cx - (dot_n - 1) * spacing / 2
                dot_y = cy + cell_h / 2 - 7
                painter.setPen(Qt.PenStyle.NoPen)
                for k in range(dot_n):
                    painter.setBrush(QBrush(QColor(marks[k])))
                    painter.drawEllipse(QPointF(start_x + k * spacing, dot_y), 2.4, 2.4)


class MiniCalendar(QFrame):
    """Themed calendar card: month nav + painted grid."""

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        today = date.today()
        self._year, self._month = today.year, today.month
        self.setObjectName("psCalCard")
        self.setStyleSheet(
            f"QFrame#psCalCard {{ background: {pal['surface']}; border: 1px solid {pal['border']}; border-radius: 16px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        nav = QHBoxLayout()
        nav.setSpacing(6)
        self.prev_btn = self._nav_button("‹")
        self.next_btn = self._nav_button("›")
        self.title = QLabel()
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {pal['fg']}; background: transparent;")
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.title, 1)
        nav.addWidget(self.next_btn)
        layout.addLayout(nav)

        self.grid = CalendarGrid(pal, self)
        layout.addWidget(self.grid)

        self.prev_btn.clicked.connect(lambda: self._shift(-1))
        self.next_btn.clicked.connect(lambda: self._shift(1))
        self._refresh()

    def _nav_button(self, text: str) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(26, 26)
        p = self.pal
        btn.setStyleSheet(
            f"QToolButton {{ background: transparent; border: none; border-radius: 8px; "
            f"color: {p['fg2']}; font-size: 16px; font-weight: 700; }}"
            f"QToolButton:hover {{ background: {p['surface2']}; color: {p['fg']}; }}"
        )
        return btn

    def _shift(self, delta: int) -> None:
        m = self._month - 1 + delta
        self._year += m // 12
        self._month = m % 12 + 1
        self._refresh()

    def _refresh(self) -> None:
        from PyQt6.QtCore import QLocale
        month_name = current_locale().monthName(self._month, QLocale.FormatType.LongFormat)
        self.title.setText(f"{month_name} {self._year}")
        self.grid.set_month(self._year, self._month)

    def set_marks(self, marks: dict) -> None:
        self.grid.set_marks(marks)


class UpcomingPlansCard(QFrame):
    """Compact list of each plan's exam date, soonest first — sits between
    the calendar and the daily-target stat in the dashboard sidebar."""

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.setObjectName("psUpcomingCard")
        self.setStyleSheet(
            f"QFrame#psUpcomingCard {{ background: {pal['surface']}; border: 1px solid {pal['border']}; border-radius: 16px; }}"
        )
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(8)
        tag = QLabel(tr("prep_upcoming_dates"))
        tag.setStyleSheet(f"font-size: 9px; font-weight: 800; letter-spacing: 1.5px; color: {pal['fg3']}; background: transparent;")
        self._layout.addWidget(tag)
        self.list_holder = QVBoxLayout()
        self.list_holder.setSpacing(7)
        self._layout.addLayout(self.list_holder)

    def set_items(self, items: list) -> None:
        """items: list of (plan_name, date_label, color), soonest first."""
        while self.list_holder.count():
            it = self.list_holder.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        p = self.pal
        if not items:
            empty = QLabel(tr("prep_no_upcoming_dates"))
            empty.setStyleSheet(f"font-size: 12px; color: {p['fg3']}; background: transparent;")
            self.list_holder.addWidget(empty)
            return
        for name, date_label, color in items[:6]:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(9)
            dot = QLabel("●")
            dot.setStyleSheet(f"font-size: 9px; color: {color}; background: transparent;")
            dot.setFixedWidth(10)
            name_label = QLabel(name)
            name_label.setStyleSheet(f"font-size: 12px; color: {p['fg2']}; background: transparent;")
            name_label.setWordWrap(False)
            date_label_w = QLabel(date_label)
            date_label_w.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {p['fg3']}; background: transparent;")
            rl.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
            rl.addWidget(name_label, 1)
            rl.addWidget(date_label_w, 0)
            self.list_holder.addWidget(row)


# ─── Dashboard side cards ─────────────────────────────────────────────────────

class StatCard(QFrame):
    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.setObjectName("psStatCard")
        self.setStyleSheet(
            f"QFrame#psStatCard {{ background: {pal['surface']}; border: 1px solid {pal['border']}; border-radius: 16px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(2)

        tag = QLabel(tr("prep_daily_target"))
        tag.setStyleSheet(f"font-size: 9px; font-weight: 800; letter-spacing: 1.5px; color: {pal['fg3']}; background: transparent;")
        layout.addWidget(tag)

        num_row = QHBoxLayout()
        num_row.setSpacing(6)
        num_row.setContentsMargins(0, 2, 0, 0)
        self.value_label = QLabel("0")
        self.value_label.setStyleSheet(f"font-size: 34px; font-weight: 800; color: {pal['accent']}; background: transparent;")
        unit = QLabel(tr("cards"))
        unit.setStyleSheet(f"font-size: 12px; color: {pal['fg2']}; background: transparent;")
        num_row.addWidget(self.value_label, 0, Qt.AlignmentFlag.AlignBottom)
        num_row.addWidget(unit, 0, Qt.AlignmentFlag.AlignBottom)
        num_row.addStretch(1)
        layout.addLayout(num_row)

        self.sub_label = QLabel(tr("prep_across_active_tpl").format(0, tr("prep_plans")))
        self.sub_label.setStyleSheet(f"font-size: 11px; color: {pal['fg3']}; background: transparent;")
        layout.addWidget(self.sub_label)

    def set_value(self, value_text: str, sub_text: str) -> None:
        self.value_label.setText(value_text)
        self.sub_label.setText(sub_text)


class QuoteCard(QFrame):
    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.setObjectName("psQuoteCard")
        self.setStyleSheet(
            f"QFrame#psQuoteCard {{ background: {with_alpha(pal['accent'], 18).name(QColor.NameFormat.HexArgb)}; "
            f"border: 1px solid {with_alpha(pal['accent'], 60).name(QColor.NameFormat.HexArgb)}; border-radius: 16px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(5)
        tag = QLabel(tr("prep_today_tag"))
        tag.setStyleSheet(f"font-size: 9px; font-weight: 800; letter-spacing: 1.5px; color: {pal['accent']}; background: transparent;")
        layout.addWidget(tag)
        self.quote_label = QLabel("")
        self.quote_label.setWordWrap(True)
        self.quote_label.setStyleSheet(f"font-size: 13px; font-style: italic; color: {pal['fg']}; background: transparent;")
        layout.addWidget(self.quote_label)

    def set_quote(self, text: str) -> None:
        self.quote_label.setText(text)


# ─── Deck tree picker ─────────────────────────────────────────────────────────

class _ClickableLabel(QLabel):
    """Plain, chrome-free click target — used for the expand/collapse chevron
    instead of QToolButton, which on some platforms still paints a faint
    native frame/arrow of its own even with no icon and disabled, which is
    what caused every row (leaves included) to show a phantom chevron."""

    clicked = pyqtSignal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class _DeckRowWidget(QFrame):
    """One self-contained pill per deck row: expand toggle, checkbox, icon and
    name all live inside the SAME frame/background, instead of Qt's native
    tree view splitting the branch (expand arrow) and item (checkbox/icon/
    text) into two separately-painted cells. Nesting depth is expressed as
    left padding inside this one frame, not as a second reserved column."""

    expandClicked = pyqtSignal()

    ROW_HEIGHT = 30
    TOGGLE_SIZE = 16
    CHEVRON_SIZE = 8

    def __init__(self, pal: dict, depth: int, has_children: bool, icon_pixmap: QPixmap, text: str, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.setObjectName("psDeckRow")
        self.setFixedHeight(self.ROW_HEIGHT)
        self.setStyleSheet(
            f"QFrame#psDeckRow {{ background: transparent; border-radius: 8px; }}"
            f"QFrame#psDeckRow:hover {{ background: {pal['surface2']}; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4 + depth * 16, 0, 8, 0)
        layout.setSpacing(8)

        self.toggle_lbl = None
        if has_children:
            self.toggle_lbl = _ClickableLabel()
            self.toggle_lbl.setFixedSize(self.TOGGLE_SIZE, self.TOGGLE_SIZE)
            self.toggle_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.toggle_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            self.toggle_lbl.clicked.connect(self.expandClicked.emit)
            layout.addWidget(self.toggle_lbl)
        else:
            spacer = QWidget()
            spacer.setFixedSize(self.TOGGLE_SIZE, self.TOGGLE_SIZE)
            layout.addWidget(spacer)

        self.checkbox = QCheckBox()
        layout.addWidget(self.checkbox)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon_pixmap)
        icon_lbl.setFixedSize(icon_pixmap.deviceIndependentSize().toSize())
        layout.addWidget(icon_lbl)

        name_lbl = QLabel(text)
        name_lbl.setStyleSheet(f"font-size: 13px; color: {pal['fg']}; background: transparent;")
        name_lbl.setMinimumWidth(0)
        layout.addWidget(name_lbl, 1)

    def set_expanded(self, expanded: bool) -> None:
        if self.toggle_lbl is None:
            return
        icon_path = _chevron_icon_path(self.pal.get("fg2", self.pal.get("fg", "#6a6a6e")), expanded)
        self.toggle_lbl.setPixmap(QPixmap(icon_path).scaled(
            self.CHEVRON_SIZE, self.CHEVRON_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
        ))


class _DeckNode(QWidget):
    """One deck row plus (if it has subdecks) a collapsible column of nested
    _DeckNode children underneath it — a plain widget tree built with normal
    layouts, not QTreeWidget. This sidesteps every native-tree-view quirk
    (branch/item painting split, itemWidget sizing, platform button chrome)
    that kept causing visual bugs when we tried to reskin QTreeWidget."""

    def __init__(self, pal: dict, addon_path: str, name: str, depth: int,
                 children_of: dict, icon_color: str, parent=None):
        super().__init__(parent)
        self.name = name
        self._expanded = True
        self._child_nodes: list = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        child_names = children_of.get(name, [])
        has_children = bool(child_names)
        leaf_text = name.split("::")[-1]
        icon_value = deck_icon_value(name, has_children)
        pixmap = render_icon_pixmap(addon_path, icon_value, icon_color, DeckTreePicker.ICON_SIZE)

        self.row = _DeckRowWidget(pal, depth, has_children, pixmap, leaf_text)
        self.row.expandClicked.connect(self._toggle_expanded)
        outer.addWidget(self.row)

        self.children_container = None
        if has_children:
            self.children_container = QWidget()
            child_layout = QVBoxLayout(self.children_container)
            child_layout.setContentsMargins(0, 0, 0, 0)
            child_layout.setSpacing(2)
            for child_name in child_names:
                node = _DeckNode(pal, addon_path, child_name, depth + 1, children_of, icon_color)
                self._child_nodes.append(node)
                child_layout.addWidget(node)
            outer.addWidget(self.children_container)
            self.row.set_expanded(True)

    def _toggle_expanded(self) -> None:
        self._expanded = not self._expanded
        self.children_container.setVisible(self._expanded)
        self.row.set_expanded(self._expanded)

    def get_selected(self, out: list) -> None:
        if self.row.checkbox.isChecked():
            out.append(self.name)
        for child in self._child_nodes:
            child.get_selected(out)

    def set_selected(self, wanted: set) -> None:
        self.row.checkbox.setChecked(self.name in wanted)
        for child in self._child_nodes:
            child.set_selected(wanted)

    def apply_filter(self, text: str) -> bool:
        self_visible = not text or text in self.name.lower()
        child_visible = False
        for child in self._child_nodes:
            if child.apply_filter(text):
                child_visible = True
        visible = self_visible or child_visible
        self.setVisible(visible)
        if self.children_container is not None:
            # Auto-reveal children while a search is narrowing the match,
            # without permanently changing the node's own expanded state.
            show_children = self._expanded or (bool(text) and child_visible)
            self.children_container.setVisible(show_children)
            self.row.set_expanded(show_children)
        return visible


class DeckTreePicker(QWidget):
    """Searchable, checkable deck tree with each deck's own icon (mirrors Deck Stats selection)."""

    ICON_SIZE = 16

    def __init__(self, deck_names: list, addon_path: str, pal: dict, parent=None):
        super().__init__(parent)
        self._deck_names = sorted(deck_names or [])
        self.addon_path = addon_path
        self.pal = pal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("prep_search_decks_placeholder"))
        layout.addWidget(self.search_input)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setMinimumHeight(210)
        self.scroll.setMaximumHeight(260)
        self.scroll.setObjectName("psDeckTreeScroll")
        self.scroll.setStyleSheet(
            f"QScrollArea#psDeckTreeScroll {{ background: {pal['surface']}; "
            f"border: 1px solid {pal['border2']}; border-radius: 10px; }}"
        )
        self._container = QWidget()
        self._container.setAutoFillBackground(False)
        self._col = QVBoxLayout(self._container)
        self._col.setContentsMargins(4, 4, 4, 4)
        self._col.setSpacing(2)
        self.scroll.setWidget(self._container)
        layout.addWidget(self.scroll)

        self._roots: list = []
        self._populate()
        self.search_input.textChanged.connect(self._filter)

    def _populate(self) -> None:
        children_of = {}
        for name in self._deck_names:
            parent_name = name.rsplit("::", 1)[0] if "::" in name else None
            children_of.setdefault(parent_name, []).append(name)

        icon_color = self.pal.get("fg2", self.pal.get("fg", "#6a6a6e"))
        for name in children_of.get(None, []):
            node = _DeckNode(self.pal, self.addon_path, name, 0, children_of, icon_color)
            self._roots.append(node)
            self._col.addWidget(node)
        self._col.addStretch(1)

    def _filter(self, text: str) -> None:
        text = text.lower().strip()
        for node in self._roots:
            node.apply_filter(text)

    def get_selected(self) -> list:
        out: list = []
        for node in self._roots:
            node.get_selected(out)
        return out

    def set_selected(self, names: list) -> None:
        wanted = set(names or [])
        for node in self._roots:
            node.set_selected(wanted)


# ─── Icon picker button ───────────────────────────────────────────────────────

class IconButton(QPushButton):
    """Shows the chosen plan icon; opens the shared DeckIconPickerDialog on click."""

    def __init__(self, addon_path: str, pal: dict, current_icon: str = DEFAULT_ICON, parent=None):
        super().__init__(parent)
        self.addon_path = addon_path
        self.pal = pal
        self._icon_value = current_icon or DEFAULT_ICON
        self.setFixedSize(48, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QPushButton {{ background: {pal['surface2']}; border: 1px solid {pal['border2']}; border-radius: 12px; }}"
            f"QPushButton:hover {{ border: 1px solid {pal['accent']}; }}"
        )
        self.clicked.connect(self._open_picker)
        self._refresh_icon()

    def _refresh_icon(self) -> None:
        pix = render_icon_pixmap(self.addon_path, self._icon_value, self.pal["fg"], 26)
        self.setIcon(QIcon(pix))
        self.setIconSize(QSize(26, 26))

    def _open_picker(self) -> None:
        try:
            from .icon_picker import DeckIconPickerDialog
            dlg = DeckIconPickerDialog(self._icon_value, self.addon_path, self.window(), allow_emoji=True)
            dlg.iconSelected.connect(self._on_selected)
            # The picker is frameless with no auto-placement. Center it on the
            # plan dialog (mirroring how Settings opens the same picker); an
            # unpositioned frameless dialog otherwise lands at the screen origin
            # or behind the modal edit dialog, so it looks like nothing opened.
            parent_win = self.window()
            if parent_win is not None:
                pg = parent_win.geometry()
                dg = dlg.frameGeometry()
                dlg.move(
                    pg.x() + (pg.width() - dg.width()) // 2,
                    pg.y() + (pg.height() - dg.height()) // 2,
                )
            dlg.exec()
        except Exception as e:
            try:
                from aqt.utils import tooltip
                tooltip(f"Icon picker error: {e}")
            except Exception:
                pass
            print(f"Prep Station: icon picker error: {e}")
        finally:
            # DeckIconPickerDialog is frameless + always-on-top; closing it can
            # drop the whole Prep Station window stack behind the main Anki
            # window (esp. on macOS). Explicitly reclaim focus for the plan
            # dialog and, one level up, the Prep Station window itself.
            top = self.window()
            top.raise_()
            top.activateWindow()
            try:
                from . import prep_station
                if prep_station._dialog is not None:
                    prep_station._dialog.raise_()
                    prep_station._dialog.activateWindow()
            except Exception:
                pass

    def _on_selected(self, value: str) -> None:
        self._icon_value = value or DEFAULT_ICON
        self._refresh_icon()

    def icon_value(self) -> str:
        return self._icon_value


# ─── Date picker button ───────────────────────────────────────────────────────

class DatePickerButton(QPushButton):
    """Shows the selected exam date; opens the shared modern date popup
    (OnigiriDateDialog — same rounded/shadowed look as the color picker)."""

    dateChanged = pyqtSignal(object)

    def __init__(self, pal: dict, initial_date: date, parent=None):
        super().__init__(parent)
        self.pal = pal
        self._date = initial_date
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(38)
        self.setStyleSheet(
            f"QPushButton {{ background: {pal['surface']}; border: 1px solid {pal['border2']}; "
            f"border-radius: 10px; padding: 0 12px; color: {pal['fg']}; text-align: left; font-size: 13px; font-weight: 500; }}"
            f"QPushButton:hover {{ border: 1px solid {pal['accent']}; }}"
        )
        self.clicked.connect(self._open_picker)
        self._refresh_text()

    def _refresh_text(self) -> None:
        locale = current_locale()
        qd = QDate(self._date.year, self._date.month, self._date.day)
        self.setText(locale.toString(qd, "dd MMM yyyy"))

    def _open_picker(self) -> None:
        from .onigiri_date_picker import OnigiriDateDialog
        chosen, ok = OnigiriDateDialog.getDate(
            self._date, self, anchor=self, accent=self.pal["accent"], min_date=date.today()
        )
        if ok and chosen:
            self._date = chosen
            self._refresh_text()
            self.dateChanged.emit(chosen)

    def date_value(self) -> date:
        return self._date


# ─── Plan background picker ──────────────────────────────────────────────────

class _ColorPillRow(QFrame):
    """Full-width color row matching Settings' Colors page pills: a label on
    the left and a rounded hex badge on the right that shows the current
    color and opens the shared custom color picker when clicked."""

    clicked = pyqtSignal()

    def __init__(self, pal: dict, label_text: str, color: str, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.setObjectName("psColorPillRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 10, 8)
        layout.setSpacing(10)

        self.label = QLabel(label_text)
        self.label.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {pal['fg2']}; background: transparent; border: none;")
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.label, 1, Qt.AlignmentFlag.AlignVCenter)

        self.badge = QLabel()
        self.badge.setFixedHeight(30)
        self.badge.setMinimumWidth(96)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.set_color(color)
        self._apply_frame_style()

    def _apply_frame_style(self) -> None:
        self.setStyleSheet(
            f"QFrame#psColorPillRow {{ background: transparent; border: 1px solid {self.pal['border2']}; border-radius: 12px; }}"
            f"QFrame#psColorPillRow:hover {{ background: {with_alpha(self.pal['fg'], 12).name(QColor.NameFormat.HexArgb)}; }}"
        )

    def set_color(self, color: str) -> None:
        self._color = color
        qcolor = QColor(color)
        if not qcolor.isValid():
            qcolor = QColor(self.pal["accent"])
        luminance = (0.299 * qcolor.red() + 0.587 * qcolor.green() + 0.114 * qcolor.blue()) / 255
        text_color = "#000000" if luminance > 0.5 else "#FFFFFF"
        self.badge.setText(qcolor.name().upper())
        self.badge.setStyleSheet(
            f"background-color: {qcolor.name()}; color: {text_color}; border: none; border-radius: 10px; "
            f"font-family: monospace; font-weight: bold; font-size: 12px;"
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class _PlanBgPreview(QFrame):
    """Live preview of the card band — renders with the exact same
    paint_plan_band() logic used by ExamCard/PlanDetailBanner."""

    def __init__(self, addon_path: str, parent=None):
        super().__init__(parent)
        self.addon_path = addon_path
        self._plan = {}
        self.setFixedHeight(96)
        self.setMinimumWidth(140)

    def set_plan(self, plan: dict) -> None:
        self._plan = plan
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = QRectF(0, 0, self.width(), self.height())
        path = QPainterPath(); path.addRoundedRect(rect, 14, 14)
        painter.setClipPath(path)
        paint_plan_band(painter, rect, self._plan, self.addon_path)


class PlanBackgroundPicker(QWidget):
    """Simplified variant of Settings' background designer: photo preview,
    opacity/blur sliders, Dynamic Mode + Color Only toggles, and either one
    color swatch or a light/dark pair depending on Dynamic Mode. Whatever
    color is picked here becomes the plan's accent color everywhere else
    (card icon, pace number, progress bar, calendar dots, etc.)."""

    changed = pyqtSignal()

    def __init__(self, addon_path: str, pal: dict, plan: dict, parent=None):
        super().__init__(parent)
        self.addon_path = addon_path
        self.pal = pal
        plan = plan or {}
        # Legacy plans only had a single "color" field; treat it as the
        # Light Color, since that's what's used when Dynamic Mode is off.
        legacy_color = plan.get("color")
        self._state = {
            "thumbnail": plan.get("thumbnail", ""),
            "thumbnail_opacity": int(plan.get("thumbnail_opacity", 100)),
            "thumbnail_blur": int(plan.get("thumbnail_blur", 0)),
            "color_only": bool(plan.get("color_only", not plan.get("thumbnail"))),
            "color_dynamic": bool(plan.get("color_dynamic", False)),
            "color_light": plan.get("color_light") or legacy_color or DEFAULT_PLAN_LIGHT_COLOR,
            "color_dark": plan.get("color_dark") or DEFAULT_PLAN_DARK_COLOR,
        }

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("psBgPickerCard")
        card.setStyleSheet(
            f"QFrame#psBgPickerCard {{ background: {pal['surface']}; border: 1px solid {pal['border2']}; border-radius: 14px; }}"
        )
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.preview = _PlanBgPreview(addon_path)
        layout.addWidget(self.preview)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.choose_btn = QPushButton(tr("prep_choose_photo"))
        self.choose_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.choose_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.choose_btn.setStyleSheet(
            f"QPushButton {{ background: {pal['surface2']}; color: {pal['fg']}; "
            f"border: 1.5px solid {pal['border2']}; border-radius: 10px; padding: 8px; font-weight: 600; }}"
            f"QPushButton:hover {{ border-color: {pal['accent']}; }}"
        )
        self.choose_btn.clicked.connect(self._choose_photo)
        btn_row.addWidget(self.choose_btn, 1)
        self.remove_btn = QPushButton(tr("prep_remove_photo"))
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.remove_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #ef4444; "
            "border: 1.5px solid #ef4444; border-radius: 10px; padding: 8px; font-weight: 600; }"
            "QPushButton:hover { background: rgba(239,68,68,0.12); }"
        )
        self.remove_btn.clicked.connect(self._remove_photo)
        btn_row.addWidget(self.remove_btn, 1)
        layout.addLayout(btn_row)

        self.opacity_row, self.opacity_slider, self.opacity_value_lbl = self._build_slider_row(tr("prep_opacity_label"))
        self.opacity_slider.setValue(self._state["thumbnail_opacity"])
        self.opacity_value_lbl.setText(f"{self._state['thumbnail_opacity']}%")
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        layout.addWidget(self.opacity_row)

        self.blur_row, self.blur_slider, self.blur_value_lbl = self._build_slider_row(tr("prep_blur_label"))
        self.blur_slider.setValue(self._state["thumbnail_blur"])
        self.blur_value_lbl.setText(str(self._state["thumbnail_blur"]))
        self.blur_slider.valueChanged.connect(self._on_blur_changed)
        layout.addWidget(self.blur_row)

        self.dynamic_toggle = AnimatedToggleButton(accent_color=pal["accent"])
        self.dynamic_toggle.setChecked(self._state["color_dynamic"])
        self.dynamic_toggle.toggled.connect(self._on_dynamic_toggled)
        layout.addWidget(self._toggle_row(tr("prep_dynamic_mode_label"), self.dynamic_toggle))

        self.color_only_toggle = AnimatedToggleButton(accent_color=pal["accent"])
        self.color_only_toggle.setChecked(self._state["color_only"])
        self.color_only_toggle.toggled.connect(self._on_color_only_toggled)
        layout.addWidget(self._toggle_row(tr("prep_color_only_label"), self.color_only_toggle))

        # Just two colors: Light Color (also the default, when Dynamic Mode
        # is off) and Dark Color (only used once Dynamic Mode is on).
        color_container = QWidget()
        color_row = QHBoxLayout(color_container)
        color_row.setContentsMargins(0, 0, 0, 0)
        color_row.setSpacing(20)
        self.light_color_row = self._build_color_row(tr("prep_color_row_label"), "color_light")
        self.dark_color_row = self._build_color_row(tr("prep_dark_color_label"), "color_dark")
        color_row.addWidget(self.light_color_row, 1)
        color_row.addWidget(self.dark_color_row, 1)
        layout.addWidget(color_container)

        self._sync_visibility()
        self._refresh_preview()

    # ── row builders ──────────────────────────────────────────────────────

    def _build_slider_row(self, label_text: str):
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(64)
        lbl.setStyleSheet(f"font-size: 12px; color: {self.pal['fg2']}; background: transparent;")
        slider = MainBackgroundEffectSlider(self.pal["accent"], self.pal["surface2"], self.pal["border2"])
        slider.setRange(0, 100)
        value_lbl = QLabel("0")
        value_lbl.setFixedWidth(34)
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value_lbl.setStyleSheet(f"font-size: 12px; color: {self.pal['fg3']}; background: transparent;")
        row.addWidget(lbl)
        row.addWidget(slider, 1)
        row.addWidget(value_lbl)
        return wrap, slider, value_lbl

    def _toggle_row(self, label_text: str, toggle: QWidget) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"font-size: 12px; color: {self.pal['fg2']}; background: transparent;")
        row.addWidget(lbl)
        row.addStretch(1)
        row.addWidget(toggle)
        return wrap

    def _build_color_row(self, label_text: str, state_key: str) -> QWidget:
        pill_row = _ColorPillRow(self.pal, label_text, self._state[state_key])
        pill_row.clicked.connect(lambda k=state_key, s=pill_row: self._pick_color(k, s))
        setattr(self, f"_swatch_{state_key}", pill_row)
        return pill_row

    # ── handlers ──────────────────────────────────────────────────────────

    def _thumb_dir(self) -> str:
        path = os.path.join(self.addon_path, "user_files", PREP_THUMBNAIL_DIR)
        os.makedirs(path, exist_ok=True)
        return path

    def _delete_file(self, filename: str) -> None:
        try:
            os.remove(os.path.join(self._thumb_dir(), filename))
        except Exception:
            pass

    def _choose_photo(self) -> None:
        from aqt.qt import QFileDialog
        source_path, _ = QFileDialog.getOpenFileName(
            self, tr("prep_choose_photo"), "", "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"
        )
        if not source_path:
            return
        ext = os.path.splitext(source_path)[1].lower() or ".png"
        new_name = f"{uuid.uuid4().hex}{ext}"
        try:
            import shutil
            shutil.copyfile(source_path, os.path.join(self._thumb_dir(), new_name))
        except Exception as e:
            print(f"Prep Station: thumbnail copy error: {e}")
            return
        old_name = self._state["thumbnail"]
        self._state["thumbnail"] = new_name
        self._state["color_only"] = False
        self.color_only_toggle.setChecked(False)
        self._sync_visibility()
        self._refresh_preview()
        self.changed.emit()
        if old_name:
            self._delete_file(old_name)

    def _remove_photo(self) -> None:
        if self._state["thumbnail"]:
            self._delete_file(self._state["thumbnail"])
        self._state["thumbnail"] = ""
        self._sync_visibility()
        self._refresh_preview()
        self.changed.emit()

    def _on_opacity_changed(self, value: int) -> None:
        self._state["thumbnail_opacity"] = value
        self.opacity_value_lbl.setText(f"{value}%")
        self._refresh_preview()
        self.changed.emit()

    def _on_blur_changed(self, value: int) -> None:
        self._state["thumbnail_blur"] = value
        self.blur_value_lbl.setText(str(value))
        self._refresh_preview()
        self.changed.emit()

    def _on_dynamic_toggled(self, checked: bool) -> None:
        self._state["color_dynamic"] = checked
        self._sync_visibility()
        self._refresh_preview()
        self.changed.emit()

    def _on_color_only_toggled(self, checked: bool) -> None:
        self._state["color_only"] = checked
        self._sync_visibility()
        self._refresh_preview()
        self.changed.emit()

    def _pick_color(self, state_key: str, swatch: "_ColorPillRow") -> None:
        chosen, ok = OnigiriColorDialog.getColor(self._state[state_key], self, anchor=swatch)
        if ok and chosen:
            self._state[state_key] = chosen
            swatch.set_color(chosen)
            self._refresh_preview()
            self.changed.emit()

    def _set_dimmed(self, widgets, dimmed: bool) -> None:
        for widget in widgets:
            widget.setEnabled(not dimmed)
            effect = widget.graphicsEffect()
            if dimmed:
                if not isinstance(effect, QGraphicsOpacityEffect):
                    effect = QGraphicsOpacityEffect(widget)
                    widget.setGraphicsEffect(effect)
                effect.setOpacity(0.4)
            elif isinstance(effect, QGraphicsOpacityEffect):
                widget.setGraphicsEffect(None)

    def _sync_visibility(self) -> None:
        has_photo = bool(self._state["thumbnail"])
        color_only = self._state["color_only"]
        # Choosing a photo is always available (and turns Color Only off);
        # controls that don't currently apply are dimmed rather than hidden,
        # matching the Main Background designer in Settings.
        self._set_dimmed([self.remove_btn], not has_photo)
        show_effects = has_photo and not color_only
        self._set_dimmed([self.opacity_row, self.blur_row], not show_effects)
        dynamic = self._state["color_dynamic"]
        self.light_color_row.label.setText(tr("prep_light_color_label") if dynamic else tr("prep_color_row_label"))
        self._set_dimmed([self.dark_color_row], not dynamic)

    def _refresh_preview(self) -> None:
        self.preview.set_plan(dict(self._state))

    def result(self) -> dict:
        return dict(self._state)


# ─── Floating footer pill ─────────────────────────────────────────────────────

class _FloatingFooterPill(QFrame):
    """Opaque, fully-rounded footer bar that floats (overlaps) above the
    scrolled form content, with a soft drop shadow for the "island" feel."""

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.setObjectName("psFooterPill")
        self.setStyleSheet(
            f"QFrame#psFooterPill {{ background: {pal['surface2']}; "
            f"border: 1px solid {pal['border2']}; border-radius: 30px; }}"
        )
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 45))
        self.setGraphicsEffect(shadow)


class _FloatingFooterHost(QWidget):
    """Lets a footer pill float, overlapping, above a scroll area (rather
    than the two being stacked non-overlapping) for the "floating island"
    look. The scroll area itself is inset on the right by the same margin
    the pill uses, so the scrollbar lives in that shared gutter instead of
    poking out past the pill — and the pill lines up exactly with the
    content's width instead of running wider or narrower than it."""

    SIDE_MARGIN = 22
    BOTTOM_MARGIN = 18

    def __init__(self, scroll_area: QScrollArea, footer_pill: QWidget, parent=None):
        super().__init__(parent)
        self._scroll = scroll_area
        self._footer = footer_pill
        self._scroll.setParent(self)
        self._footer.setParent(self)
        self._footer.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        content_w = max(0, self.width() - self.SIDE_MARGIN)
        self._scroll.setGeometry(0, 0, content_w, self.height())
        full_content_w = max(0, content_w - self.SIDE_MARGIN)
        footer_h = self._footer.sizeHint().height()
        # Pill hugs its buttons' natural width (equal margins both sides)
        # instead of stretching to a fixed ratio, so there's no dead space.
        footer_w = min(full_content_w, self._footer.sizeHint().width())
        footer_x = self.SIDE_MARGIN + (full_content_w - footer_w) // 2
        self._footer.setGeometry(
            footer_x, self.height() - footer_h - self.BOTTOM_MARGIN, footer_w, footer_h,
        )


# ─── Plan edit dialog ─────────────────────────────────────────────────────────

class PlanEditDialog(QDialog):
    def __init__(self, addon_path: str, deck_names: list, plan: dict = None, parent=None):
        super().__init__(parent)
        self.addon_path = addon_path
        self.plan = dict(plan) if plan else None
        self.pal = palette()
        self.accent_color = self.pal["accent"]
        self._result = None
        self._delete_requested = False

        self.setWindowTitle(tr("prep_edit_plan_title") if self.plan else tr("prep_new_study_plan_title"))
        self.setStyleSheet(f"QDialog {{ background: {self.pal['bg']}; }}" + build_qss(self.pal))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        form_container = QWidget()
        form_container.setAutoFillBackground(False)
        form = QVBoxLayout(form_container)
        # No right-side margin here: _FloatingFooterHost already insets the
        # whole scroll area on the right by its SIDE_MARGIN, so the
        # scrollbar sits in that gutter and content lines up with the pill.
        form.setContentsMargins(22, 22, 0, 18)
        form.setSpacing(16)

        # Name + icon
        name_row = QHBoxLayout()
        name_row.setSpacing(12)
        self.icon_btn = IconButton(addon_path, self.pal, (self.plan or {}).get("icon", DEFAULT_ICON))
        self.name_input = QLineEdit((self.plan or {}).get("name", ""))
        self.name_input.setPlaceholderText(tr("prep_plan_name_placeholder"))
        self.name_input.setMinimumHeight(44)
        name_row.addWidget(self.icon_btn)
        name_row.addWidget(self.name_input, 1)
        form.addLayout(name_row)

        form.addWidget(self._field_label(tr("prep_background_label")))
        self.bg_picker = PlanBackgroundPicker(addon_path, self.pal, self.plan or {})
        form.addWidget(self.bg_picker)

        date_row = QHBoxLayout()
        date_row.setSpacing(12)
        date_lbl = self._field_label(tr("prep_exam_date_label"))
        existing = (self.plan or {}).get("exam_date", "")
        initial_date = date.today()
        if existing:
            try:
                initial_date = date.fromisoformat(existing)
            except Exception:
                initial_date = date.today()
        self.date_input = DatePickerButton(self.pal, initial_date)
        date_row.addWidget(date_lbl, 0)
        date_row.addWidget(self.date_input, 1)
        form.addLayout(date_row)

        form.addWidget(self._field_label(tr("prep_study_decks_label")))
        self.deck_picker = DeckTreePicker(deck_names, self.addon_path, self.pal)
        self.deck_picker.set_selected((self.plan or {}).get("decks", []))
        form.addWidget(self.deck_picker)

        form.addWidget(self._field_label(tr("prep_notes_label")))
        self.notes_input = QTextEdit((self.plan or {}).get("notes", ""))
        self.notes_input.setPlaceholderText(tr("prep_notes_placeholder"))
        self.notes_input.setMinimumHeight(64)
        self.notes_input.setMaximumHeight(80)
        form.addWidget(self.notes_input)

        # Reserves room so the last field can scroll clear of the floating
        # footer pill instead of staying permanently hidden behind it.
        footer_clearance = QWidget()
        footer_clearance.setFixedHeight(76)
        form.addWidget(footer_clearance)

        scroll.setWidget(form_container)

        footer_pill = _FloatingFooterPill(self.pal)
        footer = QHBoxLayout(footer_pill)
        footer.setContentsMargins(10, 10, 10, 10)
        footer.setSpacing(8)
        del_btn = self._pill_button(tr("prep_delete"), "danger")
        del_btn.clicked.connect(self._on_delete)
        del_btn.setEnabled(bool(self.plan))
        if not self.plan:
            del_btn.setToolTip(tr("prep_delete_unavailable"))
        footer.addWidget(del_btn)
        cancel_btn = self._pill_button(tr("cancel"), "ghost")
        cancel_btn.clicked.connect(self.reject)
        save_btn = self._pill_button(tr("prep_save_changes") if self.plan else tr("prep_create_plan"), "primary")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        footer.addWidget(cancel_btn)
        footer.addWidget(save_btn)

        host = _FloatingFooterHost(scroll, footer_pill)
        root.addWidget(host, 1)

        fit_dialog_to_screen(self, 560, 800, 460, 380)

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"{small_title_font_css(theme_manager.night_mode)} font-weight: 800; letter-spacing: 1.2px; background: transparent;")
        return lbl

    def _pill_button(self, text: str, kind: str) -> QPushButton:
        """Fully-rounded footer button (Berry-style pill bar)."""
        pal = self.pal
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(40)
        if kind == "primary":
            accent = pal["accent"]
            hover = QColor(accent).lighter(112).name()
            btn.setStyleSheet(
                f"QPushButton {{ background: {accent}; color: #ffffff; border: none; "
                f"border-radius: 20px; padding: 0 14px 0 20px; font-weight: 700; }}"
                f"QPushButton:hover {{ background: {hover}; }}"
            )
        elif kind == "danger":
            btn.setStyleSheet(
                "QPushButton { background: rgba(239,68,68,0.10); color: #ef4444; "
                "border: 1px solid rgba(239,68,68,0.45); "
                "border-radius: 20px; padding: 0 18px; font-weight: 600; }"
                "QPushButton:hover { background: rgba(239,68,68,0.18); }"
                "QPushButton:disabled { background: rgba(239,68,68,0.05); color: rgba(239,68,68,0.35); "
                "border: 1px solid rgba(239,68,68,0.18); }"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton {{ background: {pal['surface2']}; color: {pal['fg2']}; border: 1px solid {pal['border2']}; "
                f"border-radius: 20px; padding: 0 18px; font-weight: 600; }}"
                f"QPushButton:hover {{ background: {pal['hover']}; color: {pal['fg']}; }}"
            )
        return btn

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            self.name_input.setFocus()
            return
        exam_date = self.date_input.date_value()
        self._result = {
            "id": (self.plan or {}).get("id", ""),
            "name": name,
            "icon": self.icon_btn.icon_value(),
            **self.bg_picker.result(),
            "exam_date": exam_date.isoformat(),
            "decks": self.deck_picker.get_selected(),
            "notes": self.notes_input.toPlainText().strip(),
        }
        self.accept()

    def _on_delete(self) -> None:
        self._delete_requested = True
        self.accept()

    def get_result(self) -> dict:
        return self._result

    def was_delete_requested(self) -> bool:
        return self._delete_requested
