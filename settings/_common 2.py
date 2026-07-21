# Auto-split shared base: imports, constants, helper widgets/functions for the settings package.

import os
import copy
import shutil
import urllib.parse
import json
import functools
import time
import math
import base64
import unicodedata
from datetime import datetime
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QDialogButtonBox, QWidget, QTabWidget, QColor, QCheckBox,
    QGroupBox, QRadioButton, QFileDialog, QSpinBox, QPlainTextEdit, QFormLayout, QScrollArea,
    QGridLayout, QPixmap, Qt, QEvent, QPainter, QPainterPath, QMessageBox,
    QListWidget, QStackedWidget, QListWidgetItem, QFrame, QSizePolicy,
    QComboBox, QSlider,
    QIcon, QPen, QBrush, QInputDialog, QAbstractButton, QDoubleSpinBox,
    QButtonGroup, QAbstractSpinBox,
    QDrag, QMimeData, QPoint, 
    QMenu, QAction, QActionGroup,
    QListWidget, QListWidgetItem, QAbstractItemView, QDateEdit, QLayout,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect
)
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtProperty, QPointF, QSignalBlocker, QSize, QTimer, QDate, QLocale, QByteArray
try:
    from PyQt6 import sip
except ImportError:
    try:
        import sip  # PyQt5 fallback
    except ImportError:
        sip = None
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QUrl, QPropertyAnimation, QEasingCurve, QRegularExpression, QEventLoop
from PyQt6.QtGui import QDesktopServices, QLinearGradient, QRegularExpressionValidator, QMouseEvent, QRegion, QGuiApplication, QCursor, QIntValidator, QFontMetrics
try:
    from PyQt6.QtGui import QColorSpace
except Exception:
    QColorSpace = None
from aqt import mw
from aqt import mw, gui_hooks   
from aqt.theme import theme_manager
from typing import Union
from .. import config
from ..config import DEFAULTS
from ..constants import COLOR_LABELS, ICON_DEFAULTS, DEFAULT_ICON_SIZES, ALL_THEME_KEYS, REVIEWER_THEME_KEYS
from ..themes import THEMES 
from aqt.qt import QRectF
from PyQt6.QtGui import QImage, QBitmap, QPainter as _QPainter
from PyQt6.QtWidgets import QApplication, QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene, QListView, QGraphicsColorizeEffect, QGraphicsOpacityEffect
from ..onigiri_notifications import notify_info as showInfo
from ..onigiri_color_picker import OnigiriColorDialog, _contrast_icon_color
from PyQt6.QtGui import QFontDatabase, QFont
from PyQt6.QtCore import QRect, QSize, QPoint
from ..fonts import FONTS, get_all_fonts
from ..api import sidebar as sidebar_api
from ..translations import tr, LANGUAGES, TRANSLATIONS
THUMBNAIL_STYLE = "QLabel { border: 2px solid transparent; border-radius: 10px; } QLabel:hover { border: 2px solid #00A982; }"
THUMBNAIL_STYLE_SELECTED = "QLabel { border: 2px solid #00A982; border-radius: 10px; }"
TEARDOWN_EVENT_TYPES = {
    t for t in (
        getattr(QEvent.Type, name, None)
        for name in ("Destroy", "Hide", "Close", "ParentChange", "ParentAboutToChange")
    )
    if t is not None
}
ADDON_ROOT = os.path.dirname(os.path.dirname(__file__))
SYSTEM_ICONS_AVAILABLE_DIR = os.path.join(ADDON_ROOT, "system_files", "system_icons", "available_for_users")
SYSTEM_ICONS_UNAVAILABLE_DIR = os.path.join(ADDON_ROOT, "system_files", "system_icons", "unavailable_for_users")
def system_icon_path(filename, users_only=False):
    if not filename:
        return ""
    filename = os.path.basename(str(filename))
    search_dirs = [SYSTEM_ICONS_AVAILABLE_DIR] if users_only else [SYSTEM_ICONS_UNAVAILABLE_DIR, SYSTEM_ICONS_AVAILABLE_DIR]
    for directory in search_dirs:
        path = os.path.join(directory, filename)
        if os.path.exists(path):
            return path
    legacy_path = os.path.join(ADDON_ROOT, "system_files", "system_icons", filename)
    return legacy_path if os.path.exists(legacy_path) else os.path.join(search_dirs[0], filename)

def native_safe_pixmap(source_pixmap):
    """Return a Cocoa-friendly ARGB pixmap for Qt cursors/drag previews."""
    if source_pixmap is None or source_pixmap.isNull():
        return QPixmap()

    dpr = source_pixmap.devicePixelRatio()
    image = source_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    if QColorSpace is not None:
        try:
            image.setColorSpace(QColorSpace(QColorSpace.NamedColorSpace.SRgb))
        except Exception:
            pass

    safe = QPixmap.fromImage(image)
    safe.setDevicePixelRatio(dpr)
    return safe

def svg_contain_rect(renderer, size, padding=0):
    """Return a centered render rect that preserves the SVG viewBox aspect ratio."""
    size = max(1, float(size))
    padding = max(0, float(padding))
    target = max(1.0, size - padding * 2)
    view_box = renderer.viewBoxF()
    width = view_box.width()
    height = view_box.height()
    if width <= 0 or height <= 0:
        default_size = renderer.defaultSize()
        width = default_size.width() or target
        height = default_size.height() or target
    ratio = width / height if height else 1.0
    if ratio >= 1:
        render_w = target
        render_h = target / ratio
    else:
        render_h = target
        render_w = target * ratio
    return QRectF(
        padding + (target - render_w) / 2,
        padding + (target - render_h) / 2,
        render_w,
        render_h,
    )
CUSTOM_GOAL_COOLDOWN_SECONDS = 24 * 60 * 60
PROFILE_BAR_IMAGE_OVERLAY_ALPHA = 0
_QtQSpinBox = QSpinBox
_QtQDoubleSpinBox = QDoubleSpinBox
class TypingOnlySpinBox(_QtQSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(32)
        self.setMaximumHeight(32)

    def wheelEvent(self, event):
        event.ignore()

    def stepBy(self, steps):
        return
class TypingOnlyDoubleSpinBox(_QtQDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(32)
        self.setMaximumHeight(32)

    def wheelEvent(self, event):
        event.ignore()

    def stepBy(self, steps):
        return
QSpinBox = TypingOnlySpinBox
QDoubleSpinBox = TypingOnlyDoubleSpinBox
from ._flow_layout import FlowLayout
def create_circular_pixmap(source_image, size):
    """
    Scales, center-crops, and clips a QImage into a circular QPixmap.
    """
    if source_image.isNull(): 
        return QPixmap()

    render_size = size * 2
    if source_image.width() > source_image.height():
        scaled_image = source_image.scaledToHeight(render_size, Qt.TransformationMode.SmoothTransformation)
    else:
        scaled_image = source_image.scaledToWidth(render_size, Qt.TransformationMode.SmoothTransformation)
    
    x = (scaled_image.width() - render_size) / 2
    y = (scaled_image.height() - render_size) / 2
    cropped_image = scaled_image.copy(int(x), int(y), render_size, render_size)

    target_pixmap = QPixmap(render_size, render_size)
    target_pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(target_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    
    path = QPainterPath()
    path.addEllipse(0, 0, render_size, render_size)
    
    painter.setClipPath(path)
    painter.drawImage(0, 0, cropped_image)
    painter.end()
    target_pixmap.setDevicePixelRatio(2.0)

    return target_pixmap
def create_circular_contained_pixmap(source_image, size, bg_color=QColor("#e5e7eb"), cover=True):
    """
    Renders an image as a proper circular avatar.
    The image fills the circle, so square picture edges never show inside it.
    """
    if source_image.isNull():
        return QPixmap()

    render_size = size * 2
    target_pixmap = QPixmap(render_size, render_size)
    target_pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(target_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    path = QPainterPath()
    path.addEllipse(0, 0, render_size, render_size)
    painter.setClipPath(path)
    painter.fillRect(0, 0, render_size, render_size, bg_color)

    scaled_image = source_image.scaled(
        render_size,
        render_size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding if cover else Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = (render_size - scaled_image.width()) // 2
    y = (render_size - scaled_image.height()) // 2
    painter.drawImage(x, y, scaled_image)
    painter.end()
    target_pixmap.setDevicePixelRatio(2.0)

    return target_pixmap
def create_rounded_pixmap(source_pixmap, radius):
    if source_pixmap.isNull(): return QPixmap()
    rounded = QPixmap(source_pixmap.size())
    rounded.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath()
    path.addRoundedRect(QRectF(source_pixmap.rect()), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, source_pixmap)
    painter.end()
    return rounded
def create_circular_thumbnail_image(source_image, size, bg_color=QColor("#e5e7eb")):
    if source_image.isNull():
        return QImage()

    target_image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    target_image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(target_image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    painter.fillRect(0, 0, size, size, bg_color)

    scaled_image = source_image.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = (size - scaled_image.width()) // 2
    y = (size - scaled_image.height()) // 2
    painter.drawImage(x, y, scaled_image)
    painter.end()
    return target_image
def create_rounded_thumbnail_image(source_image, width, height, radius):
    if source_image.isNull():
        return QImage()

    scaled_image = source_image.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    crop_x = (scaled_image.width() - width) // 2
    crop_y = (scaled_image.height() - height) // 2
    cropped_image = scaled_image.copy(crop_x, crop_y, width, height)

    target_image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    target_image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(target_image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
    painter.setClipPath(path)
    painter.drawImage(0, 0, cropped_image)
    painter.end()
    return target_image
def _font_popup_svg_icon(path, color_hex, size=16):
    if not path or not os.path.exists(path):
        return QIcon()

    try:
        with open(path, "r", encoding="utf-8") as f:
            svg_data = f.read()
        if "currentColor" in svg_data:
            svg_data = svg_data.replace("currentColor", color_hex)
        else:
            svg_data = svg_data.replace("<svg", f'<svg fill="{color_hex}"', 1)

        renderer = QSvgRenderer(svg_data.encode("utf-8"))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)
    except Exception:
        return QIcon()
def _font_popup_svg_pixmap(path, color_hex, size=16, dpr=1.0):
    if not path or not os.path.exists(path):
        return QPixmap()

    try:
        with open(path, "r", encoding="utf-8") as f:
            svg_data = f.read()
        if "currentColor" in svg_data:
            svg_data = svg_data.replace("currentColor", color_hex)
        else:
            svg_data = svg_data.replace("<svg", f'<svg fill="{color_hex}"', 1)

        scale = max(float(dpr), 1.0)
        pixel_size = max(int(size * scale), size)
        renderer = QSvgRenderer(svg_data.encode("utf-8"))
        pixmap = QPixmap(pixel_size, pixel_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        pixmap.setDevicePixelRatio(scale)
        painter = QPainter(pixmap)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        return pixmap
    except Exception:
        return QPixmap()
