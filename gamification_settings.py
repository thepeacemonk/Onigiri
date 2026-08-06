import os
import copy
import re
import shutil
import tempfile
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QWidget, QSpinBox, QPlainTextEdit, QScrollArea, QGridLayout, QPixmap, 
    Qt, QFrame, QSizePolicy, QButtonGroup, QAbstractButton, QSignalBlocker,
    QColor, QPointF, QPen, QRectF, QPainter, QPainterPath, QPropertyAnimation,
    QEasingCurve, QStackedWidget, QMessageBox, QComboBox, QIcon, QSize,
    QFileDialog
)
from PyQt6.QtCore import pyqtSignal, pyqtProperty, QEvent, QTimer
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QImage, QFont, QFontDatabase
from PyQt6.QtWidgets import QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene, QGraphicsDropShadowEffect
from aqt import mw
from aqt.theme import theme_manager
from aqt.qt import (
    QDesktopServices, QUrl
)

from . import config
from .api import bento as bento_api
from .config import DEFAULTS
from .themes import THEMES
from .settings import FlowLayout
from .settings._widgets import MainBackgroundEffectSlider
from .settings._font_picker import FontPickerDialog
from .fonts import get_all_fonts, register_poppins_qt
from .translations import tr
from .onigiri_notifications import notify_info as showInfo
from .onigiri_color_picker import OnigiriColorDialog

# --- UI COMPONENTS (Copied from settings.py for standalone functionality) ---

def _hexagon_land_module():
    from .gamification import hexagon_land
    return hexagon_land

def _onigimon_module():
    from .gamification import onigimon
    return onigimon

def _nook_level_module():
    from .gamification import nook_level
    return nook_level

def _safe_device_pixel_ratio(widget=None) -> float:
    """Return a conservative DPR without depending on a transient Qt screen."""
    candidates = []
    if widget is not None:
        try:
            candidates.append(widget.devicePixelRatioF())
        except Exception:
            pass
        try:
            screen = widget.screen()
            if screen is not None:
                candidates.append(screen.devicePixelRatio())
        except Exception:
            pass
    try:
        app = getattr(mw, "app", None)
        screen = app.primaryScreen() if app else None
        if screen is not None:
            candidates.append(screen.devicePixelRatio())
    except Exception:
        pass

    for value in candidates:
        try:
            ratio = float(value)
        except (TypeError, ValueError):
            continue
        if ratio > 0:
            return max(1.0, min(ratio, 4.0))
    return 1.0

# Key glyph for the Hexagon Land "Keys of the Island" card. Kept inline (rather
# than as a file under system_icons/) so it never shows up in the user-facing
# icon pickers — it belongs to this one card.
ISLAND_KEY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
    <path d="M0 0h24v24H0z" fill="none" />
    <g fill="none" stroke="{color}" stroke-linecap="round" stroke-linejoin="round" stroke-width="2">
        <path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z" />
        <circle cx="16.5" cy="7.5" r=".5" fill="{color}" />
    </g>
</svg>"""

CHIP_PREVIEW_DEFAULTS = {
    "chip_bg":       "#29ffffff",
    "chip_progress": "#ffb347",
    "chip_text":     "",
    "chip_level":    2,
}

class RestaurantLevelChipPreviewLabel(QWidget):
    """Small interactive preview of the restaurant-level chip."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(220, 60)
        self.chip_bg       = CHIP_PREVIEW_DEFAULTS["chip_bg"]
        self.chip_progress = CHIP_PREVIEW_DEFAULTS["chip_progress"]
        self.chip_text     = CHIP_PREVIEW_DEFAULTS["chip_text"]
        self.chip_level    = CHIP_PREVIEW_DEFAULTS["chip_level"]
        self.chip_progress_fraction = 0.65

    def set_chip_colors(self, bg, progress, text=""):
        self.chip_bg       = bg or self.chip_bg
        self.chip_progress = progress or self.chip_progress
        self.chip_text     = text or ""
        self.update()

    def paintEvent(self, event):
        width  = max(1, self.width())
        height = max(1, self.height())

        painter = QPainter(self)
        if not painter.isActive():
            return
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

            is_dark = False
            try:
                from aqt.theme import theme_manager as _tm
                is_dark = bool(_tm.night_mode)
            except Exception:
                pass

            try:
                if getattr(mw, "col", None) and hasattr(mw.col, "conf"):
                    bg_color_str = mw.col.conf.get(
                        f"modern_menu_profile_bg_color_{'dark' if is_dark else 'light'}",
                        "#555" if is_dark else "#EEE",
                    )
                else:
                    bg_color_str = "#555555" if is_dark else "#EEEEEE"
            except Exception:
                bg_color_str = "#555555" if is_dark else "#EEEEEE"

            bg_rect = QRectF(0, 0, width, height)
            bg_path = QPainterPath()
            bg_path.addRoundedRect(bg_rect, 8, 8)
            painter.fillPath(bg_path, QColor(bg_color_str))

            painter.save()
            try:
                scale_factor = 1.8
                painter.translate(width / 2, height / 2)
                painter.scale(scale_factor, scale_factor)

                chip_w, chip_h = 100, 24
                chip_rect = QRectF(-chip_w / 2, -chip_h / 2, chip_w, chip_h)
                chip_path = QPainterPath()
                chip_path.addRoundedRect(chip_rect, 12, 12)
                chip_bg_color = QColor(self.chip_bg)
                if not chip_bg_color.isValid():
                    chip_bg_color = QColor(255, 255, 255, 41)
                painter.fillPath(chip_path, chip_bg_color)
                painter.setPen(QPen(QColor(255, 255, 255, 40 if not is_dark else 20), 1))
                painter.drawPath(chip_path)

                if self.chip_text and QColor(self.chip_text).isValid():
                    text_color = QColor(self.chip_text)
                else:
                    text_color = QColor("#111827") if chip_bg_color.lightness() > 150 else QColor("#ffffff")

                level_font = painter.font()
                level_font.setPointSize(8)
                level_font.setWeight(QFont.Weight.Medium)
                painter.setFont(level_font)
                painter.setPen(text_color)
                painter.drawText(
                    QRectF(chip_rect.x() + 8, chip_rect.y(), 34, chip_rect.height()),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    f"Lv {self.chip_level}",
                )

                track_rect = QRectF(chip_rect.x() + 40, chip_rect.y() + 9, 52, 6)
                track_path = QPainterPath()
                track_path.addRoundedRect(track_rect, 3, 3)
                track_color = QColor(255, 255, 255, 60) if not is_dark else QColor(0, 0, 0, 90)
                painter.fillPath(track_path, track_color)

                fill_width = max(0, int(track_rect.width() * self.chip_progress_fraction))
                if fill_width > 0:
                    fill_rect = QRectF(track_rect.x(), track_rect.y(), fill_width, track_rect.height())
                    fill_path = QPainterPath()
                    fill_path.addRoundedRect(fill_rect, 3, 3)
                    prog_color = QColor(self.chip_progress)
                    if not prog_color.isValid():
                        prog_color = QColor("#ffb347")
                    painter.fillPath(fill_path, prog_color)
            finally:
                painter.restore()
        except Exception as exc:
            print(f"[Onigiri] Restaurant chip preview paint failed: {exc}")
        finally:
            painter.end()

def create_circular_pixmap(source_image, size):
    """
    Scales, center-crops, and clips a QImage into a circular QPixmap.
    """
    if source_image.isNull(): 
        return QPixmap()

    if source_image.width() > source_image.height():
        scaled_image = source_image.scaledToHeight(size, Qt.TransformationMode.SmoothTransformation)
    else:
        scaled_image = source_image.scaledToWidth(size, Qt.TransformationMode.SmoothTransformation)
    
    x = (scaled_image.width() - size) / 2
    y = (scaled_image.height() - size) / 2
    cropped_image = scaled_image.copy(int(x), int(y), size, size)

    target_pixmap = QPixmap(size, size)
    target_pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(target_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, QPixmap.fromImage(cropped_image))
    painter.end()
    
    return target_pixmap

class ProfileBarWidget(QWidget):
    clicked = pyqtSignal()

    def __init__(self, user_name, pic_path, bg_mode, bg_config, accent_color, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(50)
        self.setToolTip(tr("open_profile_settings"))

        self._bg_mode = bg_mode
        self._bg_image_path = bg_config.get('image')
        self._bg_color = QColor(bg_config.get('color', '#555555'))
        self._accent_color = QColor(accent_color)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 15, 5)
        layout.setSpacing(10)

        self.pic_label = QLabel()
        self.pic_label.setStyleSheet("background: transparent;")
        self.pic_label.setFixedSize(40, 40)
        
        if pic_path and os.path.exists(pic_path):
            source_image = QImage(pic_path)
        else:
            # Use default profile image
            default_pic = os.path.join(os.path.dirname(__file__), "system_files", "profile_default", "onigiri-san.png")
            source_image = QImage(default_pic)
            
        if not source_image.isNull():
            circular_pixmap = create_circular_pixmap(source_image, 40)
            self.pic_label.setPixmap(circular_pixmap)

        self.name_label = QLabel(user_name)
        self.name_label.setStyleSheet("font-weight: 500; font-size: 14px; color: white; background: transparent;")

        layout.addWidget(self.pic_label)
        layout.addWidget(self.name_label)
        layout.addStretch()

    def paintEvent(self, event):
        painter = QPainter()
        if not painter.begin(self):
            return

        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            path = QPainterPath()
            rect = self.rect().adjusted(0, 0, -1, -1)
            rect_f = QRectF(rect)
            path.addRoundedRect(rect_f, 24, 24)

            paint_color = self._accent_color
            if self._bg_mode == 'custom':
                paint_color = self._bg_color
            elif self._bg_mode == 'image':
                paint_color = QColor("#333333") 
            
            painter.fillPath(path, paint_color)

            if self._bg_mode == 'image':
                bg_image_path = self._bg_image_path
                if not bg_image_path or not os.path.exists(bg_image_path):
                    # Use default background image
                    bg_image_path = os.path.join(os.path.dirname(__file__), "system_files", "profile_default", "onigiri-bg.png")
                
                if os.path.exists(bg_image_path):
                    image = QImage(bg_image_path)
                    if not image.isNull():
                        source_pixmap = QPixmap.fromImage(image)
                        scaled_pixmap = source_pixmap.scaled(
                            self.size(), 
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
                            Qt.TransformationMode.SmoothTransformation
                        )
                        x_pos = (self.width() - scaled_pixmap.width()) / 2
                        y_pos = (self.height() - scaled_pixmap.height()) / 2
                        painter.setClipPath(path)
                        painter.drawPixmap(int(x_pos), int(y_pos), scaled_pixmap)
                        overlay_color = QColor(0, 0, 0, 100)
                        painter.fillRect(self.rect(), overlay_color)
        finally:
            painter.end()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

class DonationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("support_onigiri_title"))
        self.setFixedWidth(500)
        # Simplified for this context, just a simple message box to minimize copying
        layout = QVBoxLayout(self)
        msg = QLabel(tr("support_onigiri_desc"))
        msg.setWordWrap(True)
        layout.addWidget(msg)
        
        paypal_btn = QPushButton(tr("paypal"))
        paypal_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.paypal.com/donate/?hosted_button_id=HQUK49H7DEDF8")))
        layout.addWidget(paypal_btn)
        
        pix_btn = QPushButton(tr("pix_brazil"))
        pix_label = QLabel(f"{tr('pix_key')}: gabrielcarusbr16@gmail.com")
        layout.addWidget(pix_btn)
        layout.addWidget(pix_label)
        
        close_btn = QPushButton(tr("close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

class AnimatedToggleButton(QAbstractButton):
    def __init__(self, parent=None, accent_color="#007bff"):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.accent_color = QColor(accent_color)
        self.track_color_off = QColor("#cccccc") if not theme_manager.night_mode else QColor("#555555")
        self.thumb_color = QColor("#ffffff")
        
        self.setFixedSize(38, 20)
        
        self._thumb_x_pos = 3.0

        self.animation = QPropertyAnimation(self, b"thumb_x_pos", self)
        self.animation.setDuration(150)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.toggled.connect(self._start_animation)

    @pyqtProperty(float)
    def thumb_x_pos(self):
        return self._thumb_x_pos

    @thumb_x_pos.setter
    def thumb_x_pos(self, value):
        self._thumb_x_pos = value
        self.update()

    def _start_animation(self, checked):
        end_pos = self.width() - self.height() + 3 if checked else 3
        self.animation.setStartValue(self.thumb_x_pos)
        self.animation.setEndValue(end_pos)
        self.animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        height = self.height()
        radius = height / 2.0
        
        painter.setPen(Qt.PenStyle.NoPen)
        track_color = self.accent_color if self.isChecked() else self.track_color_off
        painter.setBrush(track_color)
        painter.drawRoundedRect(self.rect(), radius, radius)

        thumb_radius = radius - 3
        painter.setBrush(self.thumb_color)
        painter.setPen(Qt.PenStyle.NoPen)
        
        thumb_y = radius
        painter.drawEllipse(QPointF(self._thumb_x_pos + thumb_radius, thumb_y), thumb_radius, thumb_radius)

    def showEvent(self, event):
        super().showEvent(event)
        self._thumb_x_pos = self.width() - self.height() + 3 if self.isChecked() else 3
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._thumb_x_pos = self.width() - self.height() + 3 if self.isChecked() else 3
        self.update()

class GooeyPillSwitch(QWidget):
    """Two-option pill switch with a sliding indicator that squashes and
    stretches mid-travel and overshoots on arrival, for a soft 'gooey' feel."""

    modeChanged = pyqtSignal(str)

    def __init__(self, left_value, right_value, left_label="", right_label="", accent_color="#F2B705", parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._left_value = left_value
        self._right_value = right_value
        self._labels = [left_label, right_label]
        self._value = left_value
        self._accent_color = QColor(accent_color)
        self._track_color = QColor(120, 120, 120, 38)
        self._text_color_on = QColor("#ffffff")
        self._text_color_off = QColor("#888888")
        self._indicator_frac = 0.0
        self.setFixedHeight(34)
        self.setMinimumWidth(160)

        self._anim = QPropertyAnimation(self, b"indicator_frac", self)
        self._anim.setDuration(360)
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)

    def setLabels(self, left_label, right_label):
        self._labels = [left_label, right_label]
        self.update()

    def setTextColors(self, on_color, off_color):
        self._text_color_on = QColor(on_color)
        self._text_color_off = QColor(off_color)
        self.update()

    @pyqtProperty(float)
    def indicator_frac(self):
        return self._indicator_frac

    @indicator_frac.setter
    def indicator_frac(self, value):
        self._indicator_frac = value
        self.update()

    def setValue(self, value, animate=True):
        target = 1.0 if value == self._right_value else 0.0
        self._value = self._right_value if value == self._right_value else self._left_value
        if animate and self.isVisible():
            self._anim.stop()
            self._anim.setStartValue(self._indicator_frac)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._anim.stop()
            self._indicator_frac = target
            self.update()

    def value(self):
        return self._value

    def mousePressEvent(self, event):
        half = self.width() / 2.0
        new_value = self._right_value if event.position().x() >= half else self._left_value
        if new_value != self._value:
            self.setValue(new_value, animate=True)
            self.modeChanged.emit(new_value)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        radius = rect.height() / 2.0

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._track_color)
        painter.drawRoundedRect(rect, radius, radius)

        pad = 3.0
        half_w = (rect.width() - pad * 2) / 2.0
        frac = self._indicator_frac
        clamped_frac = max(0.0, min(1.0, frac))
        x = pad + half_w * clamped_frac
        # Squash/stretch peaks mid-travel to read as a soft, gooey blob.
        stretch = 1.0 + 0.22 * (1.0 - abs(clamped_frac * 2.0 - 1.0)) + 0.35 * max(0.0, abs(frac - clamped_frac))
        ind_w = half_w * stretch
        overflow = ind_w - half_w
        ind_x = x - overflow / 2.0
        ind_x = max(pad, min(ind_x, rect.width() - pad - ind_w))
        indicator_rect = QRectF(ind_x, pad, ind_w, rect.height() - pad * 2)
        painter.setBrush(self._accent_color)
        painter.drawRoundedRect(indicator_rect, indicator_rect.height() / 2.0, indicator_rect.height() / 2.0)

        # Label size scales with the pill's height so a taller switch gets
        # proportionally bigger text instead of a fixed 9pt label floating in it.
        font = painter.font()
        font.setFamily("Poppins")
        font.setWeight(QFont.Weight.Medium)
        font.setPixelSize(max(11, int(rect.height() * 0.38)))
        painter.setFont(font)
        for i, text in enumerate(self._labels):
            seg_rect = QRectF(pad + half_w * i, 0, half_w, rect.height())
            is_active = (i == 0 and clamped_frac < 0.5) or (i == 1 and clamped_frac >= 0.5)
            painter.setPen(self._text_color_on if is_active else self._text_color_off)
            painter.drawText(seg_rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.end()

class SectionGroup(QWidget):
    def __init__(self, title="", parent=None, border=True, description=""):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(0, 5, 0, 0)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 500; font-size: 20px; margin-bottom: 5px;")
        main_layout.addWidget(title_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setStyleSheet("font-size: 11px; color: #888; margin-bottom: 5px;")
            desc_label.setWordWrap(True)
            main_layout.addWidget(desc_label)

        self.content_area = QWidget()
        if border:
            self.content_area.setObjectName("innerGroup")
            self.content_area.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(10)
        main_layout.addWidget(self.content_area)

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)

class StudyZoneMessageListEditor(QWidget):
    messagesChanged = pyqtSignal()

    def __init__(self, messages, accent_color, icon_provider, parent=None):
        super().__init__(parent)
        self.setObjectName("studyZoneMessageListEditor")
        self._accent_color = accent_color
        self._icon_provider = icon_provider
        self._rows = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        self.rows_widget = QWidget()
        self.rows_widget.setObjectName("studyZoneMessageRows")
        self.rows_layout = QVBoxLayout(self.rows_widget)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(8)
        main_layout.addWidget(self.rows_widget)

        self.add_button = QPushButton(tr("add_message", "Add message"))
        self.add_button.setObjectName("studyZoneAddMessageButton")
        self.add_button.setIcon(self._icon("add.svg", 14))
        self.add_button.setIconSize(QSize(14, 14))
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.clicked.connect(lambda: self.add_message("", focus=True))
        main_layout.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignLeft)

        initial_messages = [str(item).strip() for item in (messages or []) if str(item).strip()]
        if not initial_messages:
            initial_messages = [""]
        for message in initial_messages:
            self.add_message(message, focus=False, emit_change=False)
        self._refresh_row_buttons()

    def _icon(self, filename, size=14):
        if callable(self._icon_provider):
            return self._icon_provider(filename, size)
        return QIcon()

    def _make_icon_button(self, filename, tooltip, callback):
        button = QPushButton()
        button.setObjectName("studyZoneMessageIconButton")
        # 34px box against the 17px QSS radius = a perfect circle.
        button.setFixedSize(34, 34)
        button.setIcon(self._icon(filename, 15))
        button.setIconSize(QSize(15, 15))
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def add_message(self, text="", focus=False, emit_change=True):
        row = QFrame()
        row.setObjectName("studyZoneMessageRow")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 8, 8, 8)
        row_layout.setSpacing(6)

        input_widget = QLineEdit(str(text or ""))
        input_widget.setObjectName("studyZoneMessageInput")
        input_widget.setPlaceholderText(tr("message_placeholder", "Write a message..."))
        input_widget.textChanged.connect(self._emit_messages_changed)

        up_button = self._make_icon_button("up.svg", tr("move_up", "Move up"), lambda _=False, r=row: self._move_row(r, -1))
        down_button = self._make_icon_button("down.svg", tr("move_down", "Move down"), lambda _=False, r=row: self._move_row(r, 1))
        delete_button = self._make_icon_button("trash.svg", tr("delete", "Delete"), lambda _=False, r=row: self._remove_row(r))

        row_layout.addWidget(input_widget, 1)
        row_layout.addWidget(up_button)
        row_layout.addWidget(down_button)
        row_layout.addWidget(delete_button)

        row_data = {
            "widget": row,
            "input": input_widget,
            "up": up_button,
            "down": down_button,
            "delete": delete_button,
        }
        self._rows.append(row_data)
        self.rows_layout.addWidget(row)
        self._refresh_row_buttons()

        if focus:
            input_widget.setFocus()
        if emit_change:
            self._emit_messages_changed()

    def _row_index(self, row_widget):
        for index, row_data in enumerate(self._rows):
            if row_data["widget"] is row_widget:
                return index
        return -1

    def _move_row(self, row_widget, direction):
        index = self._row_index(row_widget)
        new_index = index + int(direction)
        if index < 0 or new_index < 0 or new_index >= len(self._rows):
            return

        row_data = self._rows.pop(index)
        self._rows.insert(new_index, row_data)
        self.rows_layout.removeWidget(row_widget)
        self.rows_layout.insertWidget(new_index, row_widget)
        row_data["input"].setFocus()
        self._refresh_row_buttons()
        self._emit_messages_changed()

    def _remove_row(self, row_widget):
        index = self._row_index(row_widget)
        if index < 0:
            return

        row_data = self._rows.pop(index)
        self.rows_layout.removeWidget(row_data["widget"])
        row_data["widget"].deleteLater()
        if not self._rows:
            self.add_message("", focus=True, emit_change=False)
        else:
            focus_index = min(index, len(self._rows) - 1)
            self._rows[focus_index]["input"].setFocus()
        self._refresh_row_buttons()
        self._emit_messages_changed()

    def _refresh_row_buttons(self):
        last_index = len(self._rows) - 1
        for index, row_data in enumerate(self._rows):
            row_data["up"].setEnabled(index > 0)
            row_data["down"].setEnabled(index < last_index)
            row_data["delete"].setEnabled(len(self._rows) > 1 or bool(row_data["input"].text().strip()))

    def _emit_messages_changed(self, *args):
        self._refresh_row_buttons()
        self.messagesChanged.emit()

    def messages(self):
        return [row["input"].text().strip() for row in self._rows if row["input"].text().strip()]

class StudyZonePinInput(QWidget):
    def __init__(self, value="", parent=None):
        super().__init__(parent)
        self.setObjectName("studyZonePinInput")
        self._boxes = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        digits = "".join(ch for ch in str(value or "") if ch.isdigit())[:6]
        digits = digits.ljust(6)
        for index in range(6):
            box = QLineEdit(digits[index].strip())
            box.setObjectName("studyZonePinDigit")
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.setMaxLength(1)
            box.setFixedSize(36, 42)
            box.setTextMargins(0, 0, 0, 0)
            box.setFont(QFont(box.font().family(), 15, QFont.Weight.Medium))
            box.textEdited.connect(lambda text, i=index: self._handle_text_edited(i, text))
            layout.addWidget(box)
            self._boxes.append(box)

    def _handle_text_edited(self, index, text):
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) > 1:
            self.set_pin(digits)
            focus_index = min(len(digits), 5)
            self._boxes[focus_index].setFocus()
            return

        box = self._boxes[index]
        if box.text() != digits:
            box.setText(digits)
        if digits and index < 5:
            self._boxes[index + 1].setFocus()
            self._boxes[index + 1].selectAll()

    def keyPressEvent(self, event):
        focused = self.focusWidget()
        if focused in self._boxes:
            index = self._boxes.index(focused)
            if event.key() == Qt.Key.Key_Backspace and not focused.text() and index > 0:
                previous = self._boxes[index - 1]
                previous.clear()
                previous.setFocus()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Left and index > 0:
                self._boxes[index - 1].setFocus()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Right and index < 5:
                self._boxes[index + 1].setFocus()
                event.accept()
                return
        super().keyPressEvent(event)

    def set_pin(self, value):
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())[:6]
        for index, box in enumerate(self._boxes):
            box.setText(digits[index] if index < len(digits) else "")

    def pin(self):
        return "".join(box.text() for box in self._boxes)

class DifficultyCardWidget(QPushButton):
    def __init__(self, title, description, emoji, accent_color=None, icon_size=40):
        super().__init__()
        self.setCheckable(True)
        self.setObjectName("difficultyCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(100)
        self.setMinimumWidth(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        if accent_color:
            qcolor = QColor(accent_color)
            tint = f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, 0.14)"
            self.setStyleSheet(f"""
                QPushButton#difficultyCard:checked {{
                    border: 2px solid {accent_color};
                    background-color: {tint};
                }}
            """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        self.icon_label = QLabel(emoji)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: transparent;
                color: inherit;
                border-radius: {icon_size // 2}px;
                font-size: 24px;
                min-width: {icon_size}px;
                max-width: {icon_size}px;
                min-height: {icon_size}px;
                max-height: {icon_size}px;
            }}
        """)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        self.title_label = QLabel(title)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.title_label.setStyleSheet("font-weight: 500; font-size: 14px; background: transparent;")
        
        self.desc_label = QLabel(description)
        self.desc_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("font-size: 12px; color: #888; background: transparent;")

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.desc_label)
        text_layout.addStretch()

        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(text_layout)


# --- DIALOG CLASS ---

class GamificationSettingsDialog(QDialog):
    def __init__(self, parent=None, addon_path=None):
        super().__init__(parent)
        # Do NOT force WindowStaysOnTopHint: the Gamification Settings window must
        # only appear while Anki itself is the active app. With the on-top hint it
        # floated over every other application on the computer; without it the
        # window tracks Anki's normal stacking and hides behind other apps.
        self.addon_path = addon_path
        # Poppins is the dialog's only typeface (weights capped at 500). Qt only
        # resolves `font-family: 'Poppins'` in QSS once the .ttf files are in the
        # application font database, so register them before any stylesheet runs.
        try:
            register_poppins_qt(addon_path)
        except Exception as exc:
            print(f"Onigiri: Could not register Poppins for gamification settings: {exc}")
        self.current_config = config.get_config()
        self.setWindowTitle(tr("gamification_settings_title"))
        self._loaded_pages = set()
        self._is_saving = False

        self._apply_default_geometry()

        # Initialize achievement config for reference
        self.achievements_config = self.current_config.get("achievements", {})
        
        # Determine accent color
        is_dark = theme_manager.night_mode
        conf = config.get_config()
        mode_key = "dark" if is_dark else "light"
        self.accent_color = conf.get("colors", {}).get(mode_key, {}).get("--accent-color", DEFAULTS["colors"][mode_key]["--accent-color"])

        # Setup Widgets for various pages (Replicated from settings.py)
        self._setup_gamification_widgets()

        # Layout Setup
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_area_layout = QHBoxLayout()
        content_area_layout.setSpacing(0)
        content_area_layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar setup - new colorful pill design
        sidebar_wrapper = QWidget()
        sidebar_wrapper.setObjectName("settingsSidebarWrapper")
        sidebar_wrapper.setMinimumWidth(188)
        sidebar_wrapper.setMaximumWidth(240)
        sidebar_wrapper_layout = QVBoxLayout(sidebar_wrapper)
        sidebar_wrapper_layout.setContentsMargins(12, 16, 12, 12)
        sidebar_wrapper_layout.setSpacing(4)

        self.sidebar_scroll_area = QScrollArea()
        self.sidebar_scroll_area.setObjectName("sidebarNavScrollArea")
        self.sidebar_scroll_area.setWidgetResizable(True)
        self.sidebar_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar_scroll_area.viewport().setObjectName("sidebarNavViewport")
        self.sidebar_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sidebar_scroll_area.setMinimumWidth(164)
        self.sidebar_scroll_area.setMaximumWidth(216)
        self.sidebar_scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Main Sidebar Widget (the rounded container)
        sidebar_widget = QWidget()
        sidebar_widget.setObjectName("sidebarContainer")
        sidebar_widget.setMinimumWidth(164)
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 12, 16)
        sidebar_layout.setSpacing(6)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Colored pill buttons
        self.sidebar_buttons = {}
        self.sidebar_button_group = QButtonGroup()
        self.sidebar_button_group.setExclusive(True)

        # Each item has (display_name, key, icon_filename)
        general_item = (tr("general"), "General", "settings.svg")
        games_items = [
            (tr("restaurant_level"),     "Nook Level", "nook.svg"),
            ("Onigimon",                 "Onigimon",         "pokeball.svg"),
            ("Hexagon Land",             "Hexagon Land",     "hexagon_land.svg"),
            ("Bento Games",              "Bento Games",      "bento.svg"),
        ]
        study_zone_items = [
            (tr("focus_dango"),          "Focus Dango",      "dango.svg"),
            (tr("mochi_messages_title"), "Mochi Messages",   "mochi.svg"),
        ]

        # Per-game accent colours used to tint the selected nav button's icon
        # and label. (light_mode_color, dark_mode_color) — the dark variants are
        # brighter so they stay legible on the dark sidebar surface.
        self._nav_colors = {
            "General":          (self.accent_color, self.accent_color),
            "Nook Level": ("#B94632", "#E8836F"),
            "Onigimon":         ("#F2B705", "#FFD45A"),
            "Hexagon Land":     ("#1F6FE0", "#5BA8FF"),
            "Bento Games":      ("#6A40E0", "#B49CFF"),
            "Focus Dango":      ("#9D3D64", "#E78BAC"),
            "Mochi Messages":   ("#00935C", "#2FD787"),
        }

        self._add_sidebar_nav_button(sidebar_layout, *general_item)
        self._add_sidebar_nav_section(sidebar_layout, "Games", games_items)
        self._add_sidebar_nav_section(sidebar_layout, "Study Zone", study_zone_items)

        # Stretch pushes buttons to the bottom
        sidebar_layout.addStretch()

        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self.reject)

        # Save button
        self.save_button = QPushButton(tr("save"))
        self.save_button.setObjectName("saveButton")
        self.save_button.setAutoDefault(False)
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.clicked.connect(self.save_settings)

        save_cancel_layout = QHBoxLayout()
        save_cancel_layout.setSpacing(4)
        save_cancel_layout.setContentsMargins(0, 0, 0, 0)
        save_cancel_layout.addWidget(self.save_button)
        save_cancel_layout.addWidget(self.cancel_button)
        
        sidebar_layout.addLayout(save_cancel_layout)

        self.sidebar_scroll_area.setWidget(sidebar_widget)
        sidebar_wrapper_layout.addWidget(self.sidebar_scroll_area, alignment=Qt.AlignmentFlag.AlignLeft)

        # Content Stack
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentStack")

        self.pages = {
            "General": self.create_general_page,
            "Nook Level": self.create_nook_level_page,
            "Onigimon": self.create_onigimon_page,
            "Focus Dango": self.create_focus_dango_page,
            "Mochi Messages": self.create_mochi_messages_page,
            "Hexagon Land": self.create_hexagon_land_page,
            "Bento Games": self.create_bento_games_page,
        }
        self.page_order = list(self.pages.keys())

        for name in self.page_order:
            self.content_stack.addWidget(QWidget())

        # Wrap content in a rounded shell (QFrame) that paints its own
        # background. A QFrame reliably renders the QSS background + border-radius
        # (a plain QWidget needs WA_StyledBackground and is flaky across Qt
        # versions), giving each page the same rounded shape as Onigiri Settings.
        content_container = QFrame()
        content_container.setObjectName("contentContainer")
        content_container.setFrameShape(QFrame.Shape.NoFrame)
        content_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        content_container_layout = QVBoxLayout(content_container)
        content_container_layout.setContentsMargins(0, 0, 0, 0)
        content_container_layout.addWidget(self.content_stack)

        # Outer margins inset the shell from the window edges (matches Onigiri
        # Settings) so the rounded corners read as a distinct shape.
        content_outer = QWidget()
        content_outer.setObjectName("contentOuter")
        content_outer_layout = QVBoxLayout(content_outer)
        # No bottom margin: the page shell runs into the window edge so its two
        # square bottom corners are invisible and only the top ones read as round.
        content_outer_layout.setContentsMargins(8, 10, 8, 0)
        content_outer_layout.setSpacing(0)
        content_outer_layout.addWidget(content_container)

        content_area_layout.addWidget(sidebar_wrapper)
        content_area_layout.addWidget(content_outer)

        main_layout.addLayout(content_area_layout)
        self.apply_stylesheet()

        # Default page
        self.navigate_to_page("General")

    def _apply_default_geometry(self):
        """Size the dialog so no page is ever clipped, on any display.

        A purely proportional size (the old 45% x 55%) cropped the wider pages on
        small laptops — the notification position picker and the Onigimon scene
        rows have fixed-width controls that simply do not fit in ~570px. So the
        proportional size is treated as a *floor-checked* preference: it is
        raised to MIN_DIALOG_* when the screen is big enough, and clamped back
        down when it is not (page scroll areas cover that last case).
        """
        # Sidebar at its widest (240) plus its 12/12 margins, beside a content
        # column that fits the widest fixed-size control on any page.
        MIN_SIDEBAR_WIDTH = 264
        MIN_CONTENT_WIDTH = 600
        MIN_DIALOG_WIDTH = MIN_SIDEBAR_WIDTH + MIN_CONTENT_WIDTH
        MIN_DIALOG_HEIGHT = 560

        screen = None
        parent = self.parentWidget()
        if parent is not None:
            try:
                screen = parent.screen()
            except Exception:
                screen = None
        if screen is None:
            try:
                app = getattr(mw, "app", None)
                screen = app.primaryScreen() if app else None
            except Exception:
                screen = None

        if screen is None:
            self.setMinimumSize(MIN_DIALOG_WIDTH, MIN_DIALOG_HEIGHT)
            self.resize(MIN_DIALOG_WIDTH, MIN_DIALOG_HEIGHT)
            return

        available = screen.availableGeometry()
        # Never demand more than the screen offers: on a display too small for
        # the ideal minimum, the minimum shrinks to fit and the scroll areas
        # take over rather than the window opening off-screen.
        max_w = max(320, int(available.width() * 0.96))
        max_h = max(320, int(available.height() * 0.96))
        min_w = min(MIN_DIALOG_WIDTH, max_w)
        min_h = min(MIN_DIALOG_HEIGHT, max_h)
        self.setMinimumSize(min_w, min_h)

        width = min(max_w, max(min_w, int(available.width() * 0.45)))
        height = min(max_h, max(min_h, int(available.height() * 0.55)))
        self.resize(width, height)

    def _theme_tokens(self):
        # Mirror Onigiri Settings' neutral palette (hardcoded high-contrast
        # values) so the gamification dialog looks identical — in particular so
        # the rounded content shell (panel) clearly stands out from the darker
        # window background, the same way it does on Onigiri Settings.
        # The accent colour still follows the user's configured theme.
        mode_key = "dark" if theme_manager.night_mode else "light"
        palette = self.current_config.get("colors", {}).get(mode_key, {})
        defaults = DEFAULTS["colors"][mode_key]
        accent = palette.get("--accent-color", defaults["--accent-color"])

        if theme_manager.night_mode:
            return {
                "bg": "#181818",
                "panel": "#242424",
                "surface": "#303030",
                "fg": "#f4f4f5",
                "muted": "#c4c4c4",
                "border": "#454545",
                "accent": accent,
            }
        return {
            "bg": "#f7f7f7",
            "panel": "#ffffff",
            "surface": "#f2f2f2",
            "fg": "#202124",
            "muted": "#6f7177",
            "border": "#dcdde1",
            "accent": accent,
        }

    def _settings_icon_color(self):
        return self._theme_tokens()["fg"]

    def _message_values(self, value, fallback=None):
        if isinstance(value, list):
            messages = value
        elif isinstance(value, str):
            messages = value.splitlines()
        else:
            messages = []
        cleaned = [str(item).strip() for item in messages if str(item).strip()]
        if cleaned:
            return cleaned
        return [str(item).strip() for item in (fallback or []) if str(item).strip()]

    def _study_zone_message_icon(self, filename, size=15):
        return self._themed_icon(filename, self._theme_tokens()["muted"], size)

    def _themed_icon(self, filename, color=None, size=18):
        from .settings._common import system_icon_path
        icon_path = system_icon_path(filename)
        if not icon_path or not os.path.exists(icon_path):
            return QIcon()

        icon = QIcon(icon_path)
        pixmap = icon.pixmap(size, size)
        if pixmap.isNull():
            return icon

        tint = QColor(color or self._settings_icon_color())
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), tint)
        painter.end()
        return QIcon(pixmap)

    def _tinted_stylesheet_svg_path(self, filename, color):
        from .settings._common import system_icon_path
        icon_path = system_icon_path(filename)
        if not icon_path or not os.path.exists(icon_path):
            return ""

        color_name = QColor(color or self._settings_icon_color()).name()
        icon_name = os.path.splitext(os.path.basename(filename))[0]
        cache_dir = os.path.join(tempfile.gettempdir(), "onigiri_theme_icons")
        out_path = os.path.join(cache_dir, f"{icon_name}_{color_name.lstrip('#')}.svg")

        try:
            os.makedirs(cache_dir, exist_ok=True)
            if not os.path.exists(out_path):
                with open(icon_path, "r", encoding="utf-8") as src:
                    svg = src.read()
                if "currentColor" in svg:
                    svg = svg.replace("currentColor", color_name)
                else:
                    svg = svg.replace("<svg", f'<svg fill="{color_name}" stroke="{color_name}"', 1)
                with open(out_path, "w", encoding="utf-8") as dst:
                    dst.write(svg)
            return out_path.replace("\\", "/")
        except Exception as exc:
            print(f"Onigiri: Error tinting icon {filename}: {exc}")
            return icon_path.replace("\\", "/")

    def _decorate_button(self, button, icon_filename=None, icon_size=18):
        if icon_filename:
            button.setIcon(self._themed_icon(icon_filename, self._settings_icon_color(), icon_size))
            button.setIconSize(QSize(icon_size, icon_size))
            button.setProperty("onigiri_icon_filename", icon_filename)
            button.setProperty("onigiri_icon_size", icon_size)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAutoDefault(False)

    def _set_sidebar_section_toggle_icon(self, button, expanded):
        icon_filename = "down.svg" if expanded else "right.svg"
        button.setIcon(self._themed_icon(icon_filename, self._theme_tokens()["muted"], 12))
        button.setIconSize(QSize(12, 12))

    def _toggle_sidebar_nav_section(self, toggle_button, content_widget, expanded):
        content_widget.setVisible(expanded)
        self._set_sidebar_section_toggle_icon(toggle_button, expanded)

    def _nav_color(self, key):
        """Theme-aware accent colour for a given mini-game nav item."""
        light, dark = self._nav_colors.get(key, (self.accent_color, self.accent_color))
        return dark if theme_manager.night_mode else light

    def _apply_sidebar_button_colors(self, active_key):
        """Tint the selected nav button (icon + label) with its mini-game colour;
        reset every other nav button to the neutral muted style."""
        tokens = self._theme_tokens()
        surface = tokens["surface"]
        muted = tokens["muted"]
        for key, btn in self.sidebar_buttons.items():
            filename = btn.property("onigiri_icon_filename")
            size = btn.property("onigiri_icon_size") or 16
            if key == active_key:
                color = self._nav_color(key)
                if filename:
                    btn.setIcon(self._themed_icon(filename, color, size))
                btn.setStyleSheet(f"""
                    QPushButton#sidebarNavButton,
                    QPushButton#sidebarNavButton:hover,
                    QPushButton#sidebarNavButton:checked {{
                        min-height: 28px;
                        padding: 4px 10px;
                        border-radius: 18px;
                        background-color: {surface};
                        border: 1px solid transparent;
                        text-align: left;
                        font-size: 13px;
                        font-weight: 500;
                        color: {color};
                    }}
                """)
            else:
                if filename:
                    btn.setIcon(self._themed_icon(filename, muted, size))
                btn.setStyleSheet("")


    def _setup_gamification_widgets(self):
        # General / Master Toggle
        self.gamification_mode_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.gamification_mode_toggle.setChecked(bool(self.current_config.get("gamificationMode", True)))
        
        # Focused Gaming Toggle
        self.focused_gaming_toggle = AnimatedToggleButton(accent_color="#5b8dee")
        self.focused_gaming_toggle.setChecked(bool(self.current_config.get("focusedGaming", False)))
        self.notification_duration_spinbox = QSpinBox()
        self.notification_duration_spinbox.setObjectName("notificationDurationSpinBox")
        self.notification_duration_spinbox.setRange(1, 30)
        self.notification_duration_spinbox.setSuffix(" sec")
        try:
            notification_duration_seconds = int(self.current_config.get("onigiri_notification_duration_ms", 5200)) // 1000
        except (TypeError, ValueError):
            notification_duration_seconds = 5
        self.notification_duration_spinbox.setValue(max(1, min(30, notification_duration_seconds)))

        current_mode = self.current_config.get("onigiri_reviewer_notification_mode", "classic")
        self.notification_mode_widget = GooeyPillSwitch(
            "classic", "mini",
            tr("notification_mode_classic", "Classic"), tr("notification_mode_mini", "Mini"),
            accent_color=self.accent_color,
        )
        self.notification_mode_widget.setFixedHeight(44)
        self.notification_mode_widget.setMinimumWidth(300)
        self.notification_mode_widget.setValue(current_mode, animate=False)

        restaurant_conf = self.current_config.get("restaurant_level", {})
        self.nook_level_toggle = AnimatedToggleButton(accent_color="#B94632")
        self.nook_level_toggle.setChecked(bool(restaurant_conf.get("enabled", False)))
        self.restaurant_notifications_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.restaurant_notifications_toggle.setChecked(bool(restaurant_conf.get("notifications_enabled", True)))
        self.restaurant_bar_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.restaurant_bar_toggle.setChecked(bool(restaurant_conf.get("show_profile_bar_progress", True)))
        self.restaurant_reviewer_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.restaurant_reviewer_toggle.setChecked(bool(restaurant_conf.get("show_reviewer_header", True)))

        # Chip colour state
        self.rl_chip_bg_color       = str(restaurant_conf.get("chip_bg_color", ""))
        self.rl_chip_progress_color = str(restaurant_conf.get("chip_progress_color", ""))
        self.rl_chip_text_color     = str(restaurant_conf.get("chip_text_color", ""))
        self.rl_dynamic_chip_colors        = bool(restaurant_conf.get("dynamic_chip_colors", False))
        self.rl_chip_bg_color_light        = str(restaurant_conf.get("chip_bg_color_light", ""))
        self.rl_chip_bg_color_dark         = str(restaurant_conf.get("chip_bg_color_dark", ""))
        self.rl_chip_progress_color_light  = str(restaurant_conf.get("chip_progress_color_light", ""))
        self.rl_chip_progress_color_dark   = str(restaurant_conf.get("chip_progress_color_dark", ""))
        self.rl_chip_text_color_light      = str(restaurant_conf.get("chip_text_color_light", ""))
        self.rl_chip_text_color_dark       = str(restaurant_conf.get("chip_text_color_dark", ""))

        self.rl_chip_bg_button = QPushButton()
        self.rl_chip_bg_button.setObjectName("restaurantChipColorButton")
        self.rl_chip_bg_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rl_chip_bg_button.clicked.connect(lambda: self._choose_restaurant_chip_color("bg"))

        self.rl_chip_progress_button = QPushButton()
        self.rl_chip_progress_button.setObjectName("restaurantChipColorButton")
        self.rl_chip_progress_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rl_chip_progress_button.clicked.connect(lambda: self._choose_restaurant_chip_color("progress"))

        self.rl_chip_text_button = QPushButton()
        self.rl_chip_text_button.setObjectName("restaurantChipColorButton")
        self.rl_chip_text_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rl_chip_text_button.clicked.connect(lambda: self._choose_restaurant_chip_color("text"))

        self.rl_chip_reset_colors_button = QPushButton(tr("reset_colors"))
        self.rl_chip_reset_colors_button.clicked.connect(self._reset_restaurant_chip_colors)

        # Which game drives the profile Level chip: nook | onigimon | hexagon
        self.profile_level_game = str(self.current_config.get("profile_level_game", "nook") or "nook").lower()
        if self.profile_level_game not in ("nook", "onigimon", "hexagon"):
            self.profile_level_game = "nook"

        # Onigimon
        self.onigimon_config = self.current_config.get("onigimon", {})
        if not isinstance(self.onigimon_config, dict):
            self.onigimon_config = {}
        self.onigimon_toggle = AnimatedToggleButton(accent_color="#F2B705")
        self.onigimon_toggle.setChecked(bool(self.onigimon_config.get("enabled", False)))
        self.onigimon_ankimon_updates_toggle = AnimatedToggleButton(accent_color="#F2B705")
        self.onigimon_ankimon_updates_toggle.setChecked(bool(self.onigimon_config.get("allow_ankimon_updates", True)))
        self.onigimon_streak_warning_toggle = AnimatedToggleButton(accent_color="#F2B705")
        self.onigimon_streak_warning_toggle.setChecked(bool(self.onigimon_config.get("show_streak_broken_warning", True)))
        self.onigimon_difficulty_group = QButtonGroup()
        self.onigimon_difficulty_group.setExclusive(True)
        self.onigimon_difficulty_widgets = {}
        def _get_sprite(name):
            # 48px = the previous 32px bumped by 50%.
            path = os.path.join(os.path.dirname(__file__), "system_files", "gamification_images", "onigimon", name)
            url = QUrl.fromLocalFile(path).toString()
            return f'<img src="{url}" width="48" height="48">'

        onigimon_difficulties = [
            ("bulbassaur", "Bulbassaur", tr("onigimon_diff_easy_desc"), _get_sprite("bulbasaur_pixel.webp"), "#4CAF50"),
            ("pikachu", "Pikachu", tr("onigimon_diff_normal_desc"), _get_sprite("pikachu_pixel.webp"), "#F2B705"),
            ("charizard", "Charizard", tr("onigimon_diff_hard_desc"), _get_sprite("charizard_pixel.webp"), "#E8562F"),
        ]
        for data, title, description, badge, accent in onigimon_difficulties:
            # icon_size 60 = the shared 40px badge box scaled up 50% to fit the
            # larger Onigimon sprites.
            btn = DifficultyCardWidget(title, description, badge, accent_color=accent, icon_size=60)
            self.onigimon_difficulty_group.addButton(btn)
            self.onigimon_difficulty_widgets[data] = btn
        current_onigimon_difficulty = str(self.onigimon_config.get("difficulty", "pikachu") or "pikachu").lower()
        if current_onigimon_difficulty not in self.onigimon_difficulty_widgets:
            current_onigimon_difficulty = "pikachu"
        self.onigimon_difficulty_widgets[current_onigimon_difficulty].setChecked(True)
        self.onigimon_sprite_motion = "gif" if str(self.onigimon_config.get("sprite_motion", "static")) == "gif" else "static"
        self.onigimon_sprite_mode_widget = GooeyPillSwitch(
            "static", "gif",
            tr("onigimon_sprite_static"), tr("onigimon_sprite_animated"),
            accent_color="#F2B705",
        )
        self.onigimon_sprite_mode_widget.setValue(self.onigimon_sprite_motion, animate=False)
        def _on_onigimon_sprite_mode_changed(value):
            self.onigimon_sprite_motion = "gif" if value == "gif" else "static"
        self.onigimon_sprite_mode_widget.modeChanged.connect(_on_onigimon_sprite_mode_changed)
        self.onigimon_scene_color = str(self.onigimon_config.get("scene_background_color", "#6ea96a") or "#6ea96a")
        if not re.match(r"^#[0-9a-fA-F]{6}$", self.onigimon_scene_color):
            self.onigimon_scene_color = "#6ea96a"
        self.onigimon_scene_image = str(self.onigimon_config.get("scene_background_image", "") or "")
        self.onigimon_scene_color_button = QPushButton(tr("onigimon_scene_color_button"))
        self.onigimon_scene_color_button.setObjectName("onigimonSceneButton")
        self.onigimon_scene_color_button.clicked.connect(self._choose_onigimon_scene_color)
        self.onigimon_scene_import_button = QPushButton(tr("onigimon_import_image_button"))
        self.onigimon_scene_import_button.setObjectName("onigimonSceneButton")
        self.onigimon_scene_import_button.clicked.connect(self._import_onigimon_scene_background)
        self.onigimon_scene_clear_button = QPushButton(tr("onigimon_clear_image_button"))
        self.onigimon_scene_clear_button.setObjectName("onigimonSceneButton")
        self.onigimon_scene_clear_button.clicked.connect(self._clear_onigimon_scene_background)
        # Stats panel (.onigimon-bottom) colour — empty means "use the widget's
        # own light/dark default".
        self.onigimon_bottom_color = str(self.onigimon_config.get("scene_bottom_color", "") or "")
        if self.onigimon_bottom_color and not re.match(r"^#[0-9a-fA-F]{6}$", self.onigimon_bottom_color):
            self.onigimon_bottom_color = ""
        self.onigimon_bottom_color_button = QPushButton(tr("onigimon_stats_panel_color", "Panel color"))
        self.onigimon_bottom_color_button.setObjectName("onigimonSceneButton")
        self.onigimon_bottom_color_button.clicked.connect(self._choose_onigimon_bottom_color)
        self.onigimon_bottom_reset_button = QPushButton(tr("reset", "Reset"))
        self.onigimon_bottom_reset_button.setObjectName("onigimonSceneButton")
        self.onigimon_bottom_reset_button.clicked.connect(self._reset_onigimon_bottom_color)
        scene_slider_tokens = self._theme_tokens()
        blur_value = int(self.onigimon_config.get("scene_background_blur", 9) or 0)
        self.onigimon_scene_blur_slider = MainBackgroundEffectSlider("#F2B705", scene_slider_tokens["surface"], scene_slider_tokens["border"])
        self.onigimon_scene_blur_slider.setRange(0, 40)
        self.onigimon_scene_blur_slider.setSingleStep(1)
        self.onigimon_scene_blur_slider.setPageStep(4)
        self.onigimon_scene_blur_slider.setValue(max(0, min(40, blur_value)))
        self.onigimon_scene_blur_slider.valueChanged.connect(self._on_onigimon_scene_blur_changed)
        self.onigimon_scene_blur_value_label = QLabel(f"{self.onigimon_scene_blur_slider.value()} px")
        self.onigimon_scene_blur_value_label.setObjectName("onigimonSceneBlurValue")
        self.onigimon_scene_blur_apply_timer = QTimer(self)
        self.onigimon_scene_blur_apply_timer.setSingleShot(True)
        self.onigimon_scene_blur_apply_timer.timeout.connect(self._persist_onigimon_scene_blur)
        opacity_value = int(self.onigimon_config.get("scene_background_opacity", 90) or 0)
        self.onigimon_scene_opacity_slider = MainBackgroundEffectSlider("#F2B705", scene_slider_tokens["surface"], scene_slider_tokens["border"])
        self.onigimon_scene_opacity_slider.setRange(0, 100)
        self.onigimon_scene_opacity_slider.setSingleStep(1)
        self.onigimon_scene_opacity_slider.setPageStep(10)
        self.onigimon_scene_opacity_slider.setValue(max(0, min(100, opacity_value)))
        self.onigimon_scene_opacity_slider.valueChanged.connect(self._on_onigimon_scene_opacity_changed)
        self.onigimon_scene_opacity_value_label = QLabel(f"{self.onigimon_scene_opacity_slider.value()}%")
        self.onigimon_scene_opacity_value_label.setObjectName("onigimonSceneBlurValue")
        self.onigimon_selected_companion_id = ""
        self.onigimon_companions_loaded = False
        self.onigimon_name_input = QLineEdit("")
        self.onigimon_name_input.setPlaceholderText(tr("onigimon_nickname_placeholder"))
        self.onigimon_companion_buttons = QButtonGroup(self)
        self.onigimon_companion_buttons.setExclusive(True)
        self.onigimon_companion_grid = QWidget()
        self.onigimon_companion_grid.setObjectName("onigimonCompanionGrid")
        self.onigimon_companion_grid_layout = QGridLayout(self.onigimon_companion_grid)
        self.onigimon_companion_grid_layout.setContentsMargins(8, 8, 8, 8)
        self.onigimon_companion_grid_layout.setSpacing(8)
        self.onigimon_companion_status_label = QLabel(tr("onigimon_status_open_page"))
        self.onigimon_companion_status_label.setWordWrap(True)
        
        # Difficulty Setting
        self.restaurant_difficulty_group = QButtonGroup()
        self.restaurant_difficulty_group.setExclusive(True)
        
        self.difficulty_widgets = {}
        
        def _get_restaurant_svg(filename, color):
            import base64
            path = os.path.join(os.path.dirname(__file__), "system_files", "system_icons", "available_for_users", filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                content = content.replace("<path ", f'<path fill="{color}" ')
                b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
                return f'<img src="data:image/svg+xml;base64,{b64}" width="32" height="32">'
            except Exception:
                return ""
        
        diffs = [
            ("Apprendice", "Apprendice (1x)", tr("apprentice_desc"), "Apprendice", "seed.svg", "#4CAF50"),
            ("Experient", "Experient (2x)", tr("cook_desc"), "Experient", "tree.svg", "#F2B705"),
            ("Legend", "Legend (4x)", tr("chef_desc"), "Legend", "crown.svg", "#E8562F")
        ]
        
        for name, title, description, data, filename, accent in diffs:
            emoji = _get_restaurant_svg(filename, accent)
            btn = DifficultyCardWidget(title, description, emoji, accent_color=accent)
            
            self.restaurant_difficulty_group.addButton(btn)
            self.difficulty_widgets[data] = btn
            
        current_difficulty = restaurant_conf.get("difficulty", "Apprendice")
        if current_difficulty in self.difficulty_widgets:
            self.difficulty_widgets[current_difficulty].setChecked(True)
        else:
            self.difficulty_widgets["Apprendice"].setChecked(True)
        
        # Mochi Messages
        self.mochi_messages_config = self.current_config.get("mochi_messages", {})
        self.mochi_messages_toggle = AnimatedToggleButton(accent_color="#00935C")
        self.mochi_messages_toggle.setChecked(bool(self.mochi_messages_config.get("enabled", False)))
        self.mochi_interval_spinbox = QSpinBox()
        self.mochi_interval_spinbox.setObjectName("studyZoneSpinBox")
        self.mochi_interval_spinbox.setRange(1, 1000)
        mochi_interval_suffix = tr("mochi_interval_suffix")
        if mochi_interval_suffix and not str(mochi_interval_suffix).startswith(" "):
            mochi_interval_suffix = f" {mochi_interval_suffix}"
        self.mochi_interval_spinbox.setSuffix(mochi_interval_suffix)
        self.mochi_interval_spinbox.setValue(int(self.mochi_messages_config.get("cards_interval", 15) or 1))
        
        mochi_default_messages = [
            tr("mochi_msg_1"), tr("mochi_msg_2"), tr("mochi_msg_3"),
            tr("mochi_msg_4"), tr("mochi_msg_5"), tr("mochi_msg_6"),
            tr("mochi_msg_7")
        ]
        messages_list = self._message_values(self.mochi_messages_config.get("messages"), mochi_default_messages)
        self.mochi_messages_editor = StudyZoneMessageListEditor(
            messages_list,
            "#00935C",
            self._study_zone_message_icon,
            self,
        )
        self.mochi_icon_choice = str(self.mochi_messages_config.get("icon_choice", "mochi") or "mochi")
        if self.mochi_icon_choice not in ("mochi", "custom"):
            self.mochi_icon_choice = "mochi"
        self.mochi_custom_icon = str(self.mochi_messages_config.get("custom_icon", "") or "")
        self.mochi_text_color = str(self.mochi_messages_config.get("text_color", "") or "")
        self.mochi_font_key = str(self.mochi_messages_config.get("font", "system") or "system")
        self._mochi_font_family_cache = {}
        self.mochi_title_name_input = QLineEdit(str(self.mochi_messages_config.get("title_name", "") or ""))
        self.mochi_title_name_input.setPlaceholderText(tr("mochi_title_placeholder", "Mochi says…"))
        self.mochi_hide_title_toggle = AnimatedToggleButton(accent_color="#00935C")
        self.mochi_hide_title_toggle.setChecked(bool(self.mochi_messages_config.get("hide_title", False)))

        # Focus Dango
        focus_dango_conf = self.achievements_config.get("focusDango", {})
        self.focus_dango_toggle = AnimatedToggleButton(accent_color="#9D3D64")
        self.focus_dango_toggle.setChecked(bool(focus_dango_conf.get("enabled", False)))
        self.focus_dango_self_sabotage_toggle = AnimatedToggleButton(accent_color="#9D3D64")
        self.focus_dango_self_sabotage_toggle.setChecked(bool(focus_dango_conf.get("self_sabotage", False)))

        dango_fallback = self._message_values(
            focus_dango_conf.get("message"),
            [tr("dont_give_up"), tr("stay_focused")]
        )
        dango_messages = self._message_values(focus_dango_conf.get("messages"), dango_fallback)
        self.focus_dango_message_editor = StudyZoneMessageListEditor(
            dango_messages,
            "#9D3D64",
            self._study_zone_message_icon,
            self,
        )

        # Hexagon Land
        self.hexagon_land_config = self.current_config.get("hexagon_land", self.current_config.get("hexagon_world", {}))
        if not isinstance(self.hexagon_land_config, dict):
            self.hexagon_land_config = {}
        self.hexagon_land_toggle = AnimatedToggleButton(accent_color="#2D8CFF")
        self.hexagon_land_toggle.setChecked(bool(self.hexagon_land_config.get("enabled", False)))

        # Keep Gamification Mode and the individual games in sync: turning any
        # game or Study Zone game on auto-enables Gamification Mode (they're
        # gated behind it at runtime and would otherwise do nothing silently),
        # and turning Gamification Mode off turns every game off with it.
        self._game_toggles = (
            self.nook_level_toggle,
            self.onigimon_toggle,
            self.hexagon_land_toggle,
            self.focus_dango_toggle,
            self.mochi_messages_toggle,
        )

        def _auto_enable_gamification_mode(checked):
            if checked and not self.gamification_mode_toggle.isChecked():
                self.gamification_mode_toggle.setChecked(True)

        for game_toggle in self._game_toggles:
            game_toggle.toggled.connect(_auto_enable_gamification_mode)

        def _on_gamification_mode_toggled(checked):
            if checked:
                return
            for game_toggle in self._game_toggles:
                game_toggle.setChecked(False)

        self.gamification_mode_toggle.toggled.connect(_on_gamification_mode_toggled)

    def navigate_to_page(self, name):
        if not name: return
        if name in self.pages:
            index = self.page_order.index(name)
            if self.content_stack.widget(index).layout() is None:
                try:
                    new_page = self.pages[name]()
                except Exception as exc:
                    print(f"[Onigiri] Failed to build gamification page {name}: {exc}")
                    new_page = self._create_page_error_widget(name, exc)
                self._prepare_content_controls(new_page)
                old_widget = self.content_stack.widget(index)
                self.content_stack.removeWidget(old_widget)
                self.content_stack.insertWidget(index, new_page)
                old_widget.deleteLater()
            self._loaded_pages.add(name)
            self.content_stack.setCurrentIndex(index)
            
            # Update sidebar button state
            if name in self.sidebar_buttons:
                self.sidebar_buttons[name].setChecked(True)
            self._apply_sidebar_button_colors(name)

    def _create_page_error_widget(self, name, exc):
        page, layout = self._create_scrollable_page()
        group, group_layout = self._create_inner_group(f"{name} could not be opened")
        message = QLabel(
            "Onigiri could not build this settings page in the current Anki runtime. "
            "The rest of the settings dialog is still usable."
        )
        message.setWordWrap(True)
        detail = QLabel(str(exc))
        detail.setWordWrap(True)
        detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        group_layout.addWidget(message)
        group_layout.addWidget(detail)
        layout.addWidget(group)
        layout.addStretch()
        return page

    def _repolish_widget(self, widget):
        try:
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)
            widget.update()
        except Exception:
            pass

    def _content_rounded_button_stylesheet(self):
        tokens = self._theme_tokens()
        surface = tokens["surface"]
        fg = tokens["fg"]
        muted = tokens["muted"]
        border = tokens["border"]
        accent = tokens["accent"]
        return f"""
            QPushButton {{
                background-color: {surface};
                color: {fg};
                border: 1px solid {border};
                border-radius: 18px;
                padding: 8px 16px;
                min-height: 36px;
                font-weight: 500;
                outline: none;
            }}
            QPushButton:hover,
            QPushButton:focus {{
                border: 1px solid {accent};
                border-radius: 18px;
                outline: none;
            }}
            QPushButton:pressed {{
                background-color: {border};
                border-radius: 18px;
            }}
            QPushButton:disabled {{
                color: {muted};
                border-radius: 18px;
            }}
        """

    def _prepare_content_controls(self, root):
        button_skip_names = {
            "dangerButton",
            "difficultyCard",
            "onigimonSceneButton",
            "onigimonCompanionTile",
            "notificationPositionButton",
            "restaurantChipColorButton",
            "restaurantChipColorLabel",
            "sidebarNavButton",
            "sidebarSectionToggle",
            "saveButton",
            "cancelButton",
            "studyZoneAddMessageButton",
            "studyZoneMessageIconButton",
        }
        content_button_style = self._content_rounded_button_stylesheet()
        for button in root.findChildren(QPushButton):
            try:
                button.setAutoDefault(False)
                button.setDefault(False)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                if button.objectName() not in button_skip_names:
                    button.setProperty("contentRoundedButton", True)
                    managed_style = bool(button.property("contentRoundedButtonStyleManaged"))
                    if managed_style or not button.styleSheet().strip():
                        button.setStyleSheet(content_button_style)
                        button.setProperty("contentRoundedButtonStyleManaged", True)
                self._repolish_widget(button)
            except Exception:
                pass

        for widget_type in (QLineEdit, QSpinBox, QComboBox):
            for widget in root.findChildren(widget_type):
                try:
                    widget.setProperty("contentRoundedInput", True)
                    self._repolish_widget(widget)
                except Exception:
                    pass

    def _open_donate_link(self):
        from .donations_dialog import DonationsDialog
        dialog = DonationsDialog(self)
        dialog.exec()

    def _open_bugs_link(self):
        QDesktopServices.openUrl(QUrl("https://github.com/thepeacemonk/Onigiri"))

    def _create_scrollable_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 20)
        layout.setSpacing(20)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # AsNeeded, not AlwaysOff: with the bar forced off, a window narrower
        # than a page's fixed-width controls clipped them with no way to reach
        # them. The minimum window size means this bar normally never appears.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("background: transparent;")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 15, 0)
        scroll_layout.setSpacing(20)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        return page, scroll_layout

    def _create_inner_group(self, title):
        group = SectionGroup(title, self)
        return group, group.content_layout

    def _create_sidebar_section_toggle(self, title, content_widget):
        button = QPushButton(title.upper())
        button.setObjectName("sidebarSectionToggle")
        button.setCheckable(True)
        button.setChecked(True)
        button.setFixedHeight(24)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAutoDefault(False)
        button.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._set_sidebar_section_toggle_icon(button, True)
        button.clicked.connect(
            lambda checked, section=content_widget, toggle=button: self._toggle_sidebar_nav_section(toggle, section, checked)
        )
        return button

    def _add_sidebar_nav_button(self, layout, label, key, icon_filename=None):
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setObjectName("sidebarNavButton")
        btn.setMinimumWidth(0)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setFixedHeight(36)
        btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._decorate_button(btn, icon_filename, 16)
        btn.clicked.connect(lambda _, name=key: self.navigate_to_page(name))
        self.sidebar_buttons[key] = btn
        self.sidebar_button_group.addButton(btn)
        layout.addWidget(btn)
        return btn

    def _add_sidebar_nav_section(self, layout, title, items):
        section_content = QWidget()
        section_content.setObjectName("sidebarSectionContent")
        section_layout = QVBoxLayout(section_content)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        layout.addWidget(self._create_sidebar_section_toggle(title, section_content))
        for item in items:
            self._add_sidebar_nav_button(section_layout, *item)
        layout.addWidget(section_content)
        layout.addSpacing(10)

    def _create_toggle_row(self, toggle_widget, text_label):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(text_label))
        layout.addStretch()
        layout.addWidget(toggle_widget)
        return row

    def create_bento_games_page(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(16)
        tokens = self._theme_tokens()
        detected_games = bento_api.get_game_widgets()

        layout.addWidget(self._create_study_zone_header(
            "Bento Games",
            "Mini-games built for Onigiri can be managed here when their add-ons are enabled.",
            "bento.svg",
            "#6A40E0"
        ))

        for addon_id, fallback_name in bento_api.GAME_ADDONS.items():
            game = detected_games.get(addon_id)
            name = (game or {}).get("name") or fallback_name
            detected = game is not None

            card = QFrame()
            card.setObjectName("studyZoneCard")
            card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            accent_color = tokens["border"]
            logo_filename = ""
            
            if addon_id == "516325516":  # Focumon
                logo_filename = "Focumon.png"
                accent_color = "#F2B705"
            elif addon_id == "1799253175":  # lofi.town
                logo_filename = "lofi_town.png"
                accent_color = "#9EAC32"
            elif addon_id == "585575504":  # Senchado
                logo_filename = "Senchado.png"
                accent_color = "#58A866"
            
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(18, 16, 18, 16)
            card_layout.setSpacing(16)

            thumbnail_column = QWidget()
            thumbnail_column.setFixedWidth(54)
            thumbnail_layout = QVBoxLayout(thumbnail_column)
            thumbnail_layout.setContentsMargins(0, 0, 0, 0)
            thumbnail_layout.setSpacing(6)
            thumbnail_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            icon_label = QLabel()
            icon_label.setFixedSize(54, 54)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {self._rgba_from_hex(accent_color, 0.12)};
                    border: 1px solid {self._rgba_from_hex(accent_color, 0.24)};
                    border-radius: 16px;
                }}
            """)
            if logo_filename:
                logo_path = os.path.join(self.addon_path, "system_files", "peace_logos", logo_filename)
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    icon_label.setPixmap(self._scaled_for_display(pixmap, 38, 38))

            status = QLabel("Detected" if detected else "Not found")
            status.setObjectName("bentoGameStatusPill")
            status.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status.setFixedSize(54, 18)
            status_bg = self._rgba_from_hex(accent_color, 0.18) if detected else tokens["surface"]
            status_fg = tokens["fg"] if detected else tokens["muted"]
            status.setStyleSheet(f"""
                QLabel#bentoGameStatusPill {{
                    background-color: {status_bg};
                    color: {status_fg};
                    border: 1px solid {self._rgba_from_hex(accent_color, 0.28) if detected else tokens["border"]};
                    border-radius: 9px;
                    padding: 0px;
                    font-size: 8px;
                    font-weight: 400;
                }}
            """)
            thumbnail_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)
            thumbnail_layout.addWidget(status, 0, Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(thumbnail_column, 0, Qt.AlignmentFlag.AlignVCenter)

            content_layout = QVBoxLayout()
            content_layout.setSpacing(7)

            header = QHBoxLayout()
            title = QLabel(name)
            title.setObjectName("studyZoneCardTitle")
            header.addWidget(title)
            header.addStretch()
            content_layout.addLayout(header)

            desc = QLabel(
                "Available as an Onigiri mini-game/widget. Its native controls are surfaced here."
                if detected else
                "Install and enable this add-on to embed it as an Onigiri mini-game."
            )
            desc.setWordWrap(True)
            desc.setObjectName("studyZoneCardDescription")
            content_layout.addWidget(desc)

            actions = QHBoxLayout()
            actions.addStretch()
            settings_callback = (game or {}).get("settings_callback")
            open_callback = (game or {}).get("open_callback")

            btn_style = f"""
                QPushButton {{
                    border-radius: 18px;
                    min-height: 36px;
                    max-height: 36px;
                    min-width: 112px;
                    padding: 0px 22px;
                    background-color: {tokens["surface"]};
                    border: 1px solid {tokens["border"]};
                    font-weight: 500;
                    color: {tokens["fg"]};
                }}
                QPushButton:hover {{
                    border-radius: 18px;
                    border: 1px solid {accent_color};
                }}
                QPushButton:pressed {{
                    border-radius: 18px;
                    background-color: {tokens["border"]};
                }}
                QPushButton:disabled {{
                    border-radius: 18px;
                    color: {tokens["muted"]};
                }}
            """

            if callable(settings_callback):
                settings_btn = QPushButton("Settings")
                settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                settings_btn.setStyleSheet(btn_style)
                settings_btn.clicked.connect(lambda _, cb=settings_callback: cb())
                actions.addWidget(settings_btn)

            if callable(open_callback):
                open_btn = QPushButton("Open")
                open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                open_btn.setStyleSheet(btn_style)
                open_btn.clicked.connect(lambda _, cb=open_callback: cb())
                actions.addWidget(open_btn)

            if actions.count() > 1:
                content_layout.addLayout(actions)

            card_layout.addLayout(content_layout, 1)

            layout.addWidget(card)

        layout.addStretch()
        return page

    def _scaled_for_display(self, pixmap, width, height,
                            mode=Qt.AspectRatioMode.KeepAspectRatio):
        """Scale a pixmap crisply for high-DPI (Retina) screens.

        Renders at width*dpr × height*dpr with smooth filtering and tags the
        result with the device pixel ratio, so Qt paints it at the requested
        logical size without the upscaling blur a plain .scaled() produces."""
        if pixmap.isNull():
            return pixmap
        dpr = _safe_device_pixel_ratio(self)
        target_w = max(1, int(round(width * dpr)))
        target_h = max(1, int(round(height * dpr)))
        scaled = pixmap.scaled(target_w, target_h, mode,
                               Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(dpr)
        return scaled

    def _render_system_icon(self, filename, size=44, color=None):
        # Icons live in system_icons/{unavailable,available}_for_users — resolve
        # via the shared helper instead of assuming they sit in system_icons/ root.
        from .settings._common import system_icon_path
        icon_path = system_icon_path(filename)
        device_ratio = _safe_device_pixel_ratio(self)
        render_size = max(1, int(round(size * device_ratio)))

        pixmap = QPixmap(render_size, render_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        if not icon_path or not os.path.exists(icon_path):
            pixmap.setDevicePixelRatio(device_ratio)
            return pixmap

        renderer = QSvgRenderer(icon_path)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        renderer.render(painter, QRectF(0, 0, render_size, render_size))
        painter.end()

        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color or self._theme_tokens()["muted"]))
        painter.end()
        pixmap.setDevicePixelRatio(device_ratio)
        return pixmap

    def _create_general_hero_icon(self, filename):
        label = QLabel()
        label.setFixedSize(64, 64)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("background: transparent; border: none;")
        label.setPixmap(self._render_system_icon(filename, 54, self._theme_tokens()["muted"]))
        return label

    def _create_onigiri_game_hero_card(self, title, subtitle, icon_filename, background_filename, text_color):
        card = QFrame()
        card.setObjectName("achievementsHeroCard")
        card.setMinimumHeight(170)
        card.setStyleSheet(f"QFrame#achievementsHeroCard {{ border-radius: 24px; color: {text_color}; }}")
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(24)
        
        icon_label = QLabel()
        icon_path = os.path.join(self.addon_path, "system_files", "gamification_images", icon_filename)
        if not os.path.exists(icon_path):
            icon_path = os.path.join(self.addon_path, "system_files", icon_filename)
        
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon_label.setPixmap(self._scaled_for_display(pixmap, 100, 100))
        layout.addWidget(icon_label)

        text_container = QWidget()
        text_container.setStyleSheet("background: transparent;")
        text_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)
        text_layout.addStretch()
        t_label = QLabel(title)
        t_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        t_label.setStyleSheet(f"font-weight: 500; font-size: 24px; color: {text_color}; background: transparent;")
        s_label = QLabel(subtitle)
        s_label.setWordWrap(True)
        s_label.setMinimumHeight(46)
        s_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        s_label.setStyleSheet(f"color: {text_color}; background: transparent;")
        text_layout.addWidget(t_label, 0, Qt.AlignmentFlag.AlignLeft)
        text_layout.addWidget(s_label, 0, Qt.AlignmentFlag.AlignLeft)
        text_layout.addStretch()
        layout.addWidget(text_container, 1)

        bg_path = os.path.join(self.addon_path, "system_files", "gamification_images", background_filename)
        if not os.path.exists(bg_path):
            bg_path = os.path.join(self.addon_path, "system_files", background_filename)
        
        if os.path.exists(bg_path):
            css_path = bg_path.replace('\\', '/')
            card.setStyleSheet(card.styleSheet() + f"QFrame#achievementsHeroCard {{ background-image: url('{css_path}'); background-position: left center; background-repeat: repeat-x; background-size: auto 100%; }}")
        
        return card

    def _attach_hero_toggle(self, card, toggle):
        card.layout().addWidget(toggle, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def create_notifications_section(self):
        """Notification Style plus every other notification setting in one card:
        style switch, position picker (hidden in Mini mode) and display time."""
        card, layout = self._create_study_zone_card(tr("notifications", "Notifications"))

        style_row = QHBoxLayout()
        style_row.setContentsMargins(0, 4, 0, 4)
        style_row.setSpacing(10)
        style_row.addStretch()
        style_row.addWidget(self.notification_mode_widget)
        style_row.addStretch()
        layout.addLayout(style_row)

        self.notification_pos_section = QWidget()
        pos_section_layout = QVBoxLayout(self.notification_pos_section)
        pos_section_layout.setContentsMargins(0, 0, 0, 0)
        pos_section_layout.setSpacing(8)
        pos_caption = QLabel(tr("reviewer_notification_pos_title", "Notification Position"))
        pos_caption.setObjectName("studyZoneCardDescription")
        pos_section_layout.addWidget(pos_caption)
        pos_section_layout.addWidget(self._create_notification_position_widget())
        layout.addWidget(self.notification_pos_section)

        duration_row = QHBoxLayout()
        duration_row.setContentsMargins(0, 0, 0, 0)
        duration_row.setSpacing(12)
        duration_row.addWidget(QLabel(tr("notification_display_time", "Show notifications for")))
        duration_row.addStretch()
        duration_row.addWidget(self.notification_duration_spinbox)
        layout.addLayout(duration_row)

        return card

    def _create_notification_position_widget(self):
        container = QWidget()
        container.setObjectName("notificationPositionSection")
        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 4, 0, 4)
        main_layout.setSpacing(28)

        grid_container = QWidget()
        grid_layout = QGridLayout(grid_container)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(10)

        positions = [
            ("top-left", "↖", 0, 0),
            ("top-center", "↑", 0, 1),
            ("top-right", "↗", 0, 2),
            ("bottom-left", "↙", 1, 0),
            ("bottom-center", "↓", 1, 1),
            ("bottom-right", "↘", 1, 2),
        ]

        self.notification_pos_buttons = {}
        current_pos = self.current_config.get("onigiri_reviewer_notification_position", "top-center")

        for pos_id, label, row, col in positions:
            btn = QPushButton(label)
            btn.setObjectName("notificationPositionButton")
            btn.setFixedSize(60, 45)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setChecked(pos_id == current_pos)
            btn.clicked.connect(lambda checked, pid=pos_id: self._update_notification_position(pid))
            self.notification_pos_buttons[pos_id] = btn
            grid_layout.addWidget(btn, row, col)

        main_layout.addWidget(grid_container)

        self.notif_preview_widget = QWidget()
        self.notif_preview_widget.setObjectName("notificationPositionPreview")
        self.notif_preview_widget.setFixedSize(200, 120)

        self.notif_rect = QLabel(self.notif_preview_widget)
        self.notif_rect.setObjectName("notificationPositionPreviewRect")
        self.notif_rect.setFixedSize(60, 30)
        self.notif_rect.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.notif_rect.setStyleSheet(f"""
            QLabel#notificationPositionPreviewRect {{
                background-color: {self.accent_color};
                border: 1px solid {self.accent_color};
                border-radius: 4px;
            }}
        """)
        self._position_preview_rect(current_pos)

        main_layout.addWidget(self.notif_preview_widget)
        main_layout.addStretch()

        return container

    def _update_notification_position(self, pos_id):
        self.current_config["onigiri_reviewer_notification_position"] = pos_id

        for pid, btn in self.notification_pos_buttons.items():
            btn.setChecked(pid == pos_id)

        self._position_preview_rect(pos_id)

    def _position_preview_rect(self, pos_id):
        container_w, container_h = 200, 120
        rect_w, rect_h = 60, 30
        margin = 10

        if "left" in pos_id:
            x = margin
        elif "right" in pos_id:
            x = container_w - rect_w - margin
        else:
            x = (container_w - rect_w) // 2

        if "top" in pos_id:
            y = margin
        else:
            y = container_h - rect_h - margin

        self.notif_rect.move(x, y)
        self.notif_rect.raise_()
        self.notif_rect.show()

    # --- PAGES ---

    def _create_profile_level_selector_card(self):
        """Segmented Nook / Onigimon XP / Hexagon Land selector picking which
        game's level the profile Level chip shows."""
        group, group_layout = self._create_study_zone_card(tr("profile_level_title", "Profile Level"))
        note = QLabel(tr("profile_level_desc", "Choose which game's level is shown on your profile."))
        note.setWordWrap(True)
        group_layout.addWidget(note)

        container = QWidget()
        container.setObjectName("profileLevelSegment")
        seg_layout = QHBoxLayout(container)
        seg_layout.setContentsMargins(4, 4, 4, 4)
        seg_layout.setSpacing(0)
        container.setStyleSheet("""
            QWidget#profileLevelSegment {
                background-color: rgba(120, 120, 120, 0.15);
                border-radius: 21px;
            }
        """)
        # Pill track (21px radius on a ~42px box) with pill thumbs (17px radius
        # on a ~34px button), restated per state so the selected option never
        # renders with square corners.
        btn_style = f"""
            QPushButton#profileLevelButton {{
                background-color: transparent;
                border: none;
                padding: 8px 16px;
                min-height: 34px;
                font-weight: 500;
                font-size: 12px;
                color: #888888;
                border-radius: 17px;
            }}
            QPushButton#profileLevelButton:hover {{ color: #aaaaaa; border-radius: 17px; }}
            QPushButton#profileLevelButton:checked {{
                background-color: {self.accent_color};
                color: white;
                border-radius: 17px;
            }}
        """
        self.profile_level_game_group = QButtonGroup(self)
        options = [
            ("nook", tr("profile_level_opt_nook", "Nook")),
            ("onigimon", tr("profile_level_opt_onigimon", "Onigimon XP")),
            ("hexagon", tr("profile_level_opt_hexagon", "Hexagon Land")),
        ]
        for idx, (key, label) in enumerate(options):
            btn = QPushButton(label)
            btn.setObjectName("profileLevelButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(btn_style)
            btn.setProperty("gameKey", key)
            if key == self.profile_level_game:
                btn.setChecked(True)
            seg_layout.addWidget(btn)
            self.profile_level_game_group.addButton(btn, idx)

        def _on_game_changed(button, checked):
            if checked:
                self.profile_level_game = str(button.property("gameKey") or "nook")

        self.profile_level_game_group.buttonToggled.connect(_on_game_changed)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(container)
        row.addStretch()
        group_layout.addLayout(row)
        return group

    def _create_level_chip_card(self):
        """Level Chip Appearance card (colors + light/dark dynamic theme).
        Shared across games; lives on the General page."""
        chip_group, chip_layout = self._create_study_zone_card(tr("level_chip_appearance"))
        chip_note = QLabel(tr("level_chip_appearance_desc"))
        chip_note.setWordWrap(True)
        chip_layout.addWidget(chip_note)

        self.rl_chip_preview = RestaurantLevelChipPreviewLabel()
        chip_layout.addWidget(self.rl_chip_preview, 0, Qt.AlignmentFlag.AlignHCenter)

        # Dynamic mode toggle row
        dynamic_row = QHBoxLayout()
        dynamic_row.addWidget(QLabel(tr("dynamic_chip_colors")))
        self.rl_dynamic_chip_colors_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.rl_dynamic_chip_colors_toggle.setChecked(self.rl_dynamic_chip_colors)

        self.rl_dynamic_chip_theme_widget = QWidget()
        self.rl_dynamic_chip_theme_widget.setObjectName("dynamicChipThemeContainer")
        self.rl_dynamic_chip_theme_widget.setVisible(self.rl_dynamic_chip_colors)
        segment_layout = QHBoxLayout(self.rl_dynamic_chip_theme_widget)
        segment_layout.setContentsMargins(4, 4, 4, 4)
        segment_layout.setSpacing(0)
        self.rl_dynamic_chip_theme_widget.setStyleSheet("""
            QWidget#dynamicChipThemeContainer {
                background-color: rgba(120, 120, 120, 0.15);
                border-radius: 21px;
            }
        """)

        import os as _os
        _addon_dir = _os.path.dirname(_os.path.abspath(__file__))
        _sun_path  = _os.path.join(_addon_dir, "system_files", "system_icons", "available_for_users", "sun.svg")
        _moon_path = _os.path.join(_addon_dir, "system_files", "system_icons", "available_for_users", "moon.svg")

        def _adaptive_icon(svg_path):
            try:
                with open(svg_path, "r", encoding="utf-8") as _f:
                    _content = _f.read()
                def _make_pixmap(color):
                    _colored = _content.replace("<path ", f'<path fill="{color}" ')
                    _px = QPixmap()
                    _px.loadFromData(_colored.encode("utf-8"))
                    return _px.scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                _icon = QIcon()
                _icon.addPixmap(_make_pixmap("#888888"), QIcon.Mode.Normal, QIcon.State.Off)
                _icon.addPixmap(_make_pixmap("#ffffff"), QIcon.Mode.Normal, QIcon.State.On)
                return _icon
            except Exception:
                return QIcon()

        _btn_style = f"""
            QPushButton#dynamicThemeButton {{
                background-color: transparent;
                border: none;
                padding: 8px 16px;
                min-height: 34px;
                font-weight: 500;
                font-size: 12px;
                color: #888888;
                border-radius: 17px;
            }}
            QPushButton#dynamicThemeButton:hover  {{ color: #aaaaaa; border-radius: 17px; }}
            QPushButton#dynamicThemeButton:checked {{
                background-color: {self.accent_color};
                color: white;
                border-radius: 17px;
            }}
        """
        self.rl_theme_light_btn = QPushButton(f" {tr('light_mode')}")
        self.rl_theme_light_btn.setIcon(_adaptive_icon(_sun_path))
        self.rl_theme_light_btn.setObjectName("dynamicThemeButton")
        self.rl_theme_light_btn.setCheckable(True)
        self.rl_theme_light_btn.setChecked(True)
        self.rl_theme_light_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rl_theme_light_btn.setStyleSheet(_btn_style)

        self.rl_theme_dark_btn = QPushButton(f" {tr('dark_mode')}")
        self.rl_theme_dark_btn.setIcon(_adaptive_icon(_moon_path))
        self.rl_theme_dark_btn.setObjectName("dynamicThemeButton")
        self.rl_theme_dark_btn.setCheckable(True)
        self.rl_theme_dark_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rl_theme_dark_btn.setStyleSheet(_btn_style)

        segment_layout.addWidget(self.rl_theme_light_btn)
        segment_layout.addWidget(self.rl_theme_dark_btn)

        self.rl_theme_btn_group = QButtonGroup(self)
        self.rl_theme_btn_group.addButton(self.rl_theme_light_btn, 0)
        self.rl_theme_btn_group.addButton(self.rl_theme_dark_btn, 1)

        def on_dynamic_toggled(checked):
            self.rl_dynamic_chip_colors = checked
            self.rl_dynamic_chip_theme_widget.setVisible(checked)
            self._update_restaurant_chip_preview()

        self.rl_dynamic_chip_colors_toggle.toggled.connect(on_dynamic_toggled)
        self.rl_theme_btn_group.idToggled.connect(
            lambda _id, checked: self._update_restaurant_chip_preview() if checked else None
        )

        dynamic_row.addWidget(self.rl_dynamic_chip_colors_toggle)
        chip_layout.addLayout(dynamic_row)

        theme_row = QHBoxLayout()
        theme_row.addStretch()
        theme_row.addWidget(self.rl_dynamic_chip_theme_widget)
        chip_layout.addLayout(theme_row)

        chip_layout.addWidget(self._create_restaurant_chip_bg_control(tr("level_chip_bg_color"), self.rl_chip_bg_button))
        chip_layout.addWidget(self._create_restaurant_chip_color_card(tr("level_chip_progress_color"), self.rl_chip_progress_button))
        chip_layout.addWidget(self._create_restaurant_chip_color_card(tr("level_chip_text_color"), self.rl_chip_text_button))

        reset_row = QHBoxLayout()
        reset_row.addWidget(self.rl_chip_reset_colors_button)
        reset_row.addStretch()
        chip_layout.addLayout(reset_row)
        self._update_restaurant_chip_preview()
        return chip_group

    def create_general_page(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(16)

        layout.addWidget(self._create_study_zone_header(
            tr("gamification_mode"),
            tr("gamification_mode_desc"),
            "gamepad.svg",
            self.accent_color,
            self.gamification_mode_toggle
        ))

        layout.addWidget(self._create_study_zone_header(
            tr("focused_gaming"),
            tr("focused_gaming_desc"),
            "arrow.svg",
            "#5b8dee",
            self.focused_gaming_toggle
        ))

        self.notification_mode_section = self.create_notifications_section()
        layout.addWidget(self.notification_mode_section)


        def _on_notification_mode_changed(value):
            is_mini = (value == "mini")
            self.notification_pos_section.setVisible(not is_mini)
        
        self.notification_mode_widget.modeChanged.connect(_on_notification_mode_changed)
        _on_notification_mode_changed(self.notification_mode_widget.value())
        
        # Lock logic: disable Restaurant Level notifications when Focused Gaming is on
        # Only locks notifications_enabled - the reviewer header/progress bar is unaffected
        def _on_focused_gaming_changed(checked):
            if checked:
                # Force notifications OFF and lock the toggle
                self.restaurant_notifications_toggle.setChecked(False)
            # Always update enabled state (locked when focused gaming is on)
            self.restaurant_notifications_toggle.setEnabled(not checked)
        
        self.focused_gaming_toggle.toggled.connect(_on_focused_gaming_changed)
        # Apply initial state
        _on_focused_gaming_changed(self.focused_gaming_toggle.isChecked())

        # Profile Level: which game drives the profile chip + its shared styling
        layout.addWidget(self._create_profile_level_selector_card())
        layout.addWidget(self._create_level_chip_card())

        layout.addStretch()

        return page

    def create_nook_level_page(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(16)
        nook_level = _nook_level_module()
        
        hero = self._create_study_zone_header(
            tr("restaurant_level"),
            tr("grow_restaurant_desc"),
            "nook.webp",
            "#B94632",
            self.nook_level_toggle
        )
        layout.addWidget(hero)

        # Name settings
        name_group, name_layout = self._create_study_zone_card(tr("restaurant_name"))
        try:
            progress = nook_level.manager.get_progress()
            progress_level = int(getattr(progress, "level", 0) or 0)
            progress_name = str(getattr(progress, "name", "Nook Level") or "Nook Level")
        except Exception as exc:
            print(f"[Onigiri] Could not load Nook Level progress: {exc}")
            progress_level = 0
            progress_name = "Nook Level"
        if progress_level >= 5:
            self.restaurant_name_input = QLineEdit(progress_name)
            name_layout.addWidget(QLabel(tr("custom_name")))
            name_layout.addWidget(self.restaurant_name_input)
        else:
            name_layout.addWidget(QLabel(tr("reach_level_5").format(level=progress_level)))
        layout.addWidget(name_group)

        # Notifications & Visibility
        vis_group, vis_layout = self._create_study_zone_card(tr("notifications_visibility"))
        vis_layout.addWidget(self._create_toggle_row(self.restaurant_notifications_toggle, tr("show_levelup_notifications")))
        vis_layout.addWidget(self._create_toggle_row(self.restaurant_bar_toggle, tr("show_progress_sidebar")))
        vis_layout.addWidget(self._create_toggle_row(self.restaurant_reviewer_toggle, tr("show_level_reviewer")))
        layout.addWidget(vis_group)

        # (The Level Chip Appearance card now lives on the General page, shared
        #  across games via the Profile Level selector.)

        # Difficulty

        diff_group, diff_layout = self._create_study_zone_card(tr("difficulty_level"))
        
        vertical_layout = QVBoxLayout()
        vertical_layout.setSpacing(10)
        for data, btn in self.difficulty_widgets.items():
            vertical_layout.addWidget(btn)
            
        diff_layout.addLayout(vertical_layout)
        layout.addWidget(diff_group)

        # Nook Rush sync
        sync_group, sync_layout = self._create_study_zone_card(tr("recipe_rush_sync_title", "Nook Rush Sync"))
        sync_note = QLabel(tr(
            "recipe_rush_sync_desc",
            "If the equipped Nook's Rush still shows a generic ticket, force a fresh pick "
            "for today - today's card progress is kept.",
        ))
        sync_note.setWordWrap(True)
        sync_layout.addWidget(sync_note)

        sync_btn = QPushButton(tr("recipe_rush_sync_button", "Sync Rush Now"))
        sync_btn.clicked.connect(self._confirm_sync_recipe_rush)
        sync_layout.addWidget(sync_btn)
        layout.addWidget(sync_group)

        # Reset
        reset_group, reset_layout = self._create_study_zone_card(tr("reset_progress_title"))
        reset_btn = QPushButton(tr("reset_restaurant_level"))
        reset_btn.setObjectName("dangerButton")
        reset_btn.clicked.connect(self._confirm_reset_nook_level)
        reset_layout.addWidget(reset_btn)

        reset_coins_btn = QPushButton(tr("reset_coins"))
        reset_coins_btn.clicked.connect(self._reset_coins)
        reset_layout.addWidget(reset_coins_btn)

        reset_purchases_btn = QPushButton(tr("reset_purchases"))
        reset_purchases_btn.clicked.connect(self._reset_purchases)
        reset_layout.addWidget(reset_purchases_btn)
        layout.addWidget(reset_group)
        
        layout.addStretch()
        return page

    def _populate_onigimon_companion_combo(self):
        self.onigimon_companion_status_label.setText(tr("onigimon_status_loading"))
        onigimon = _onigimon_module()
        onigimon.manager.bridge.clear_cache()
        while self.onigimon_companion_grid_layout.count():
            item = self.onigimon_companion_grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for button in list(self.onigimon_companion_buttons.buttons()):
            self.onigimon_companion_buttons.removeButton(button)

        onigimon.manager.sync_active_companion_from_ankimon()
        status = onigimon.manager.bridge.status()
        all_companions = onigimon.manager.get_available_companions() if status == "ready" else []
        self.onigimon_selected_companion_id = onigimon.manager.load().active_companion_id
        active_id = self.onigimon_selected_companion_id
        companions = list(all_companions)
        companions.sort(key=lambda p: (str(p.get("ankimon_id")) != str(active_id), not bool(p.get("is_favorite")), str(p.get("name", "")).lower()))

        if status == "missing":
            self.onigimon_companion_status_label.setText(tr("onigimon_status_missing"))
            return
        if status == "starter_needed":
            self.onigimon_companion_status_label.setText(tr("onigimon_status_starter_needed"))
            return
        if status == "no_collection":
            self.onigimon_companion_status_label.setText(tr("onigimon_status_no_collection"))
            return
        if not companions:
            self.onigimon_companion_status_label.setText(tr("onigimon_status_no_companions"))
            return

        self.onigimon_companion_status_label.setText(tr("onigimon_status_ready"))
        columns = 4
        for index, pokemon in enumerate(companions):
            ankimon_id = str(pokemon.get("ankimon_id", ""))
            label = f"{pokemon.get('name', 'Pokemon')} · {tr('onigimon_level_short')} {pokemon.get('level', 1)}"
            btn = QPushButton()
            btn.setObjectName("onigimonCompanionTile")
            btn.setCheckable(True)
            btn.setFixedSize(56, 56)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(label)
            btn.setProperty("companion_id", ankimon_id)
            sprite_path = self._onigimon_sprite_local_path(str(pokemon.get("sprite_url") or ""))
            if sprite_path and os.path.exists(sprite_path):
                btn.setIcon(QIcon(sprite_path))
                btn.setIconSize(QSize(44, 44))
            else:
                btn.setText(str(pokemon.get("name", "?"))[:2].upper())
            btn.clicked.connect(lambda checked, cid=ankimon_id: self._select_onigimon_companion(cid))
            self.onigimon_companion_buttons.addButton(btn)
            if ankimon_id == active_id:
                btn.setChecked(True)
                self.onigimon_selected_companion_id = ankimon_id
            row, col = divmod(index, columns)
            self.onigimon_companion_grid_layout.addWidget(btn, row, col)
        self.onigimon_companions_loaded = True
        self._update_onigimon_scene_controls()

    def _select_onigimon_companion(self, ankimon_id):
        onigimon = _onigimon_module()
        self.onigimon_selected_companion_id = str(ankimon_id)
        onigimon.manager.set_active_companion(self.onigimon_selected_companion_id)
        for pokemon in onigimon.manager.get_available_companions():
            if str(pokemon.get("ankimon_id")) == self.onigimon_selected_companion_id:
                current = onigimon.manager.load().companions.get(self.onigimon_selected_companion_id, {})
                self.onigimon_name_input.setText(str(current.get("display_name") or pokemon.get("name") or ""))
                self._update_onigimon_scene_controls()
                break

    def _onigimon_sprite_local_path(self, sprite_url):
        prefix = "/_addons/"
        if not sprite_url.startswith(prefix):
            return ""
        parts = sprite_url[len(prefix):].split("/", 1)
        if len(parts) != 2:
            return ""
        addon_id, rel_path = parts
        try:
            return os.path.join(mw.addonManager.addonsFolder(), addon_id, rel_path)
        except Exception:
            return ""

    def _onigimon_background_dir(self):
        path = os.path.join(self.addon_path, "user_files", "onigimon_backgrounds")
        os.makedirs(path, exist_ok=True)
        return path

    def _onigimon_scene_image_abs_path(self):
        if not self.onigimon_scene_image:
            return ""
        if os.path.isabs(self.onigimon_scene_image):
            return self.onigimon_scene_image
        return os.path.join(self.addon_path, self.onigimon_scene_image)

    def _unique_onigimon_background_path(self, source_path):
        directory = self._onigimon_background_dir()
        base, ext = os.path.splitext(os.path.basename(source_path))
        safe_base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip(".-") or "onigimon-background"
        ext = ext.lower() if ext else ".png"
        candidate = os.path.join(directory, safe_base + ext)
        index = 2
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{safe_base}-{index}{ext}")
            index += 1
        return candidate

    def eventFilter(self, obj, event):
        if obj is getattr(self, "onigimon_scene_preview", None) and event.type() == QEvent.Type.Resize:
            self._update_onigimon_scene_preview_background()
        return super().eventFilter(obj, event)

    def _scaled_onigimon_scene_background(self, image_path):
        pixmap = QPixmap(image_path)
        if pixmap.isNull() or not hasattr(self, "onigimon_scene_preview"):
            return QPixmap()

        # Render at the device pixel ratio so the preview stays crisp on Retina.
        dpr = _safe_device_pixel_ratio(self)
        size = self.onigimon_scene_preview.size()
        width = max(1, int(round(size.width() * dpr)))
        height = max(1, int(round(size.height() * dpr)))
        scaled = pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - width) // 2)
        y = max(0, (scaled.height() - height) // 2)
        cropped = scaled.copy(x, y, width, height)
        blur = self.onigimon_scene_blur_slider.value() if hasattr(self, "onigimon_scene_blur_slider") else 0
        if blur <= 0:
            result = self._apply_onigimon_scene_opacity(cropped)
        else:
            result = self._apply_onigimon_scene_opacity(
                self._blur_onigimon_scene_pixmap(cropped, float(blur) * dpr)
            )
        if not result.isNull():
            result.setDevicePixelRatio(dpr)
        return result

    def _apply_onigimon_scene_opacity(self, pixmap):
        if pixmap.isNull():
            return pixmap
        opacity = self.onigimon_scene_opacity_slider.value() if hasattr(self, "onigimon_scene_opacity_slider") else 90
        opacity = max(0.0, min(1.0, float(opacity) / 100.0))
        if opacity >= 1.0:
            return pixmap
        target = QPixmap(pixmap.size())
        target.fill(Qt.GlobalColor.transparent)
        painter = QPainter(target)
        painter.setOpacity(opacity)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        return target

    def _blur_onigimon_scene_pixmap(self, pixmap, radius):
        if pixmap.isNull() or radius <= 0:
            return pixmap

        pad = max(16, int(radius * 2.5))
        padded = QPixmap(pixmap.width() + pad * 2, pixmap.height() + pad * 2)
        padded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(padded)
        painter.drawPixmap(pad, pad, pixmap)
        painter.end()

        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(padded)
        effect = QGraphicsBlurEffect()
        effect.setBlurRadius(radius)
        item.setGraphicsEffect(effect)
        scene.addItem(item)
        scene.setSceneRect(QRectF(0, 0, padded.width(), padded.height()))

        blurred = QPixmap(padded.size())
        blurred.fill(Qt.GlobalColor.transparent)
        painter = QPainter(blurred)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        scene.render(
            painter,
            QRectF(0, 0, padded.width(), padded.height()),
            QRectF(0, 0, padded.width(), padded.height()),
        )
        painter.end()
        return blurred.copy(pad, pad, pixmap.width(), pixmap.height())

    def _update_onigimon_scene_preview_background(self):
        if not hasattr(self, "onigimon_scene_preview_bg"):
            return

        image_path = self._onigimon_scene_image_abs_path()
        self.onigimon_scene_preview_bg.setGeometry(self.onigimon_scene_preview.rect())
        if self.onigimon_scene_image and os.path.exists(image_path):
            self.onigimon_scene_preview_bg.setPixmap(self._scaled_onigimon_scene_background(image_path))
        else:
            self.onigimon_scene_preview_bg.setPixmap(QPixmap())

        self.onigimon_scene_preview_bg.lower()

    def _on_onigimon_scene_blur_changed(self, value):
        if hasattr(self, "onigimon_scene_blur_value_label"):
            self.onigimon_scene_blur_value_label.setText(f"{int(value)} px")
        self._update_onigimon_scene_preview_background()
        oni_conf = self.current_config.setdefault("onigimon", {})
        oni_conf["scene_background_blur"] = int(value)
        if hasattr(self, "onigimon_scene_blur_apply_timer"):
            self.onigimon_scene_blur_apply_timer.start(180)

    def _on_onigimon_scene_opacity_changed(self, value):
        if hasattr(self, "onigimon_scene_opacity_value_label"):
            self.onigimon_scene_opacity_value_label.setText(f"{int(value)}%")
        self._update_onigimon_scene_preview_background()
        oni_conf = self.current_config.setdefault("onigimon", {})
        oni_conf["scene_background_opacity"] = int(value)
        if hasattr(self, "onigimon_scene_blur_apply_timer"):
            self.onigimon_scene_blur_apply_timer.start(180)

    def _persist_onigimon_scene_blur(self):
        config.write_config(self.current_config)
        try:
            if mw and getattr(mw, "deckBrowser", None):
                mw.deckBrowser.refresh()
        except Exception as exc:
            print(f"Warning: Could not refresh Onigimon widget after blur change: {exc}")
        try:
            for widget in mw.app.topLevelWidgets():
                if widget.__class__.__name__ == "OnigimonCareDialog" and hasattr(widget, "refresh"):
                    widget.refresh()
        except Exception as exc:
            print(f"Warning: Could not refresh Onigimon care after blur change: {exc}")

    def _update_onigimon_scene_controls(self):
        color = self.onigimon_scene_color if re.match(r"^#[0-9a-fA-F]{6}$", self.onigimon_scene_color) else "#6ea96a"
        self.onigimon_scene_color_button.setStyleSheet(
            f"QPushButton#onigimonSceneButton {{ background-color: {color}; color: #111111;"
            " border: 1px solid rgba(0,0,0,0.18); border-radius: 18px; padding: 8px 16px;"
            " min-height: 36px; font-weight: 500; }"
        )

        if hasattr(self, "onigimon_scene_preview"):
            # Mirrors the live widget's CSS radial-gradient (onigiri_renderer.py,
            # ".onigimon-top.onigimon-scene") using Qt's own qradialgradient
            # syntax, since QSS has no color-mix() — the light/dark stops are
            # computed here instead.
            light = self._mix_hex_color(color, "#ffffff", 0.92)
            dark = self._mix_hex_color(color, "#000000", 0.90)
            gradient = (
                "qradialgradient(cx:0.22, cy:0.32, radius:1.05, fx:0.22, fy:0.32, "
                f"stop:0 {light}, stop:0.7 {color}, stop:1 {dark})"
            )
            # Top section: rounded on top only, flat seam into the stats panel —
            # exactly how `.onigimon-top` sits inside `.onigimon-card`.
            self.onigimon_scene_preview.setStyleSheet(
                "QFrame#onigimonScenePreview {"
                "border: 1px solid rgba(120,120,120,0.42);"
                "border-bottom: none;"
                "border-top-left-radius: 14px;"
                "border-top-right-radius: 14px;"
                "border-bottom-left-radius: 0px;"
                "border-bottom-right-radius: 0px;"
                f"background: {gradient};"
                "}"
            )
            self._update_onigimon_scene_preview_background()

        if hasattr(self, "onigimon_bottom_preview"):
            bottom_color = self.onigimon_bottom_color or self._default_onigimon_bottom_color()
            meter_fg = "#f0f0f0" if QColor(bottom_color).lightness() < 128 else "#222222"
            self.onigimon_bottom_preview.setStyleSheet(f"""
                QFrame#onigimonBottomPreview {{
                    background-color: {bottom_color};
                    border: 1px solid rgba(120,120,120,0.42);
                    border-top: none;
                    border-top-left-radius: 0px;
                    border-top-right-radius: 0px;
                    border-bottom-left-radius: 14px;
                    border-bottom-right-radius: 14px;
                }}
                QFrame#onigimonBottomPreview QLabel#onigimonPreviewMeterLabel,
                QFrame#onigimonBottomPreview QLabel#onigimonPreviewMeterValue {{
                    color: {meter_fg};
                    background: transparent;
                    font-size: 12px;
                }}
                QFrame#onigimonBottomPreview QLabel#onigimonPreviewMeterValue {{
                    font-weight: 500;
                }}
                QFrame#onigimonBottomPreview QFrame#onigimonPreviewMeterTrack {{
                    background-color: {self._rgba_from_hex(meter_fg, 0.14)};
                    border-radius: 3px;
                }}
            """)
            self._style_onigimon_bottom_color_button()

        if hasattr(self, "onigimon_preview_name_label"):
            # Name/level sit on the coloured scene, so they take the same fixed
            # per-mode colours as `.onigimon-top .onigimon-info`.
            info_fg = "#ffffff" if theme_manager.night_mode else "#000000"
            info_muted = "rgba(255,255,255,0.82)" if theme_manager.night_mode else "rgba(0,0,0,0.68)"
            self.onigimon_preview_name_label.setStyleSheet(
                f"color: {info_fg}; font-size: 16px; font-weight: 500; background: transparent;"
            )
            self.onigimon_preview_level_label.setStyleSheet(
                f"color: {info_muted}; font-size: 12px; background: transparent;"
            )
            companion_name = ""
            try:
                onigimon = _onigimon_module()
                companion = onigimon.manager.active_companion()
                if companion:
                    companion_name = str(onigimon.manager.companion_display_name(companion))
                    self.onigimon_preview_level_label.setText(
                        f"{tr('onigimon_level', 'Level')} {int(getattr(companion, 'level', 1) or 1)}"
                    )
            except Exception:
                companion_name = ""
            self.onigimon_preview_name_label.setText(companion_name or "Onigimon")
        if hasattr(self, "onigimon_scene_preview_sprite"):
            sprite_url = ""
            selected_id = str(getattr(self, "onigimon_selected_companion_id", "") or "")
            if self.onigimon_companions_loaded or selected_id:
                onigimon = _onigimon_module()
                for pokemon in onigimon.manager.get_available_companions():
                    if str(pokemon.get("ankimon_id")) == selected_id:
                        sprite_url = str(pokemon.get("sprite_url") or "")
                        break
                if not sprite_url:
                    companion = onigimon.manager.active_companion()
                    sprite_url = str(companion.sprite_url if companion else "")
            sprite_path = self._onigimon_sprite_local_path(sprite_url)
            pixmap = QPixmap(sprite_path) if sprite_path and os.path.exists(sprite_path) else QPixmap()
            if not pixmap.isNull():
                # 86px inside a 96px box — the live widget's
                # `.onigimon-top .onigimon-sprite img` size.
                self.onigimon_scene_preview_sprite.setPixmap(
                    self._scaled_for_display(pixmap, 86, 86)
                )
                self.onigimon_scene_preview_sprite.setText("")
            else:
                self.onigimon_scene_preview_sprite.setPixmap(QPixmap())
                self.onigimon_scene_preview_sprite.setText("Onigimon")
            # Mirrors the live widget's blurred drop-shadow ellipse under the
            # sprite (".onigimon-top .onigimon-sprite::before") using Qt's
            # native blur-capable shadow effect, since QSS has no filter/blur.
            shadow = QGraphicsDropShadowEffect(self.onigimon_scene_preview_sprite)
            shadow.setBlurRadius(18)
            shadow.setOffset(0, 10)
            shadow.setColor(QColor(0, 0, 0, 61))
            self.onigimon_scene_preview_sprite.setGraphicsEffect(shadow)

    def _choose_onigimon_scene_color(self):
        chosen, ok = OnigiriColorDialog.getColor(self.onigimon_scene_color, self)
        if ok:
            self.onigimon_scene_color = chosen
            self._update_onigimon_scene_controls()

    def _import_onigimon_scene_background(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("import_image"),
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.gif)"
        )
        if not path:
            return
        try:
            dest = self._unique_onigimon_background_path(path)
            shutil.copy2(path, dest)
            self.onigimon_scene_image = os.path.relpath(dest, self.addon_path)
            self._update_onigimon_scene_controls()
        except Exception as exc:
            showInfo(f"Could not import Onigimon background: {exc}")

    def _clear_onigimon_scene_background(self):
        self.onigimon_scene_image = ""
        self._update_onigimon_scene_controls()

    # --- Mochi messenger image -------------------------------------------------
    def _mochi_custom_icon_dir(self):
        path = os.path.join(self.addon_path, "user_files", "mochi_messenger")
        os.makedirs(path, exist_ok=True)
        return path

    def _mochi_custom_icon_abs_path(self):
        if not self.mochi_custom_icon:
            return ""
        if os.path.isabs(self.mochi_custom_icon):
            return self.mochi_custom_icon
        return os.path.join(self.addon_path, self.mochi_custom_icon)

    def _unique_mochi_custom_icon_path(self, source_path):
        directory = self._mochi_custom_icon_dir()
        base, ext = os.path.splitext(os.path.basename(source_path))
        safe_base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip(".-") or "mochi-messenger"
        ext = ext.lower() if ext else ".webp"
        candidate = os.path.join(directory, safe_base + ext)
        index = 2
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{safe_base}-{index}{ext}")
            index += 1
        return candidate

    def _import_mochi_custom_icon(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("mochi_import_image", "Choose a messenger image"),
            "",
            "Images (*.webp *.png *.jpg *.jpeg *.gif)"
        )
        if not path:
            return
        try:
            dest = self._unique_mochi_custom_icon_path(path)
            shutil.copy2(path, dest)
            self.mochi_custom_icon = os.path.relpath(dest, self.addon_path)
            self.mochi_icon_choice = "custom"
            self._update_mochi_icon_controls()
        except Exception as exc:
            showInfo(tr("mochi_import_failed", "Could not import the image: {error}").format(error=exc))

    def _clear_mochi_custom_icon(self):
        self.mochi_custom_icon = ""
        self.mochi_icon_choice = "mochi"
        self._update_mochi_icon_controls()

    def _set_mochi_icon_choice(self, choice):
        if choice == "custom" and not self._mochi_custom_icon_abs_path():
            # No image imported yet — prompt for one instead of selecting an empty
            # option. The refresh afterwards re-syncs the source switch if the
            # file dialog was cancelled.
            self._import_mochi_custom_icon()
            self._update_mochi_icon_controls()
            return
        self.mochi_icon_choice = "custom" if choice == "custom" else "mochi"
        self._update_mochi_icon_controls()

    def _update_mochi_icon_controls(self):
        has_custom = bool(self._mochi_custom_icon_abs_path()) and os.path.exists(self._mochi_custom_icon_abs_path())
        if self.mochi_icon_choice == "custom" and not has_custom:
            self.mochi_icon_choice = "mochi"
        active = self.mochi_icon_choice

        if hasattr(self, "mochi_icon_source_widget"):
            # Also snaps the pill back when "Custom" was picked but the import
            # dialog was cancelled, so the switch never lies about the source.
            with QSignalBlocker(self.mochi_icon_source_widget):
                self.mochi_icon_source_widget.setValue(active, animate=True)

        if hasattr(self, "mochi_custom_remove_btn"):
            self.mochi_custom_remove_btn.setVisible(has_custom)

        if hasattr(self, "mochi_icon_preview"):
            pixmap = QPixmap()
            if active == "custom" and has_custom:
                pixmap = QPixmap(self._mochi_custom_icon_abs_path())
            else:
                default_path = os.path.join(
                    self.addon_path, "system_files", "gamification_images", "mochi_messenger.webp"
                )
                if os.path.exists(default_path):
                    pixmap = QPixmap(default_path)
            if not pixmap.isNull():
                # Fit inside the 56px shell with breathing room, so the sprite
                # sits centred instead of overflowing and reading as off-centre.
                self.mochi_icon_preview.setPixmap(self._scaled_for_display(pixmap, 40, 40))
                self.mochi_icon_preview.setText("")
                self.mochi_icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                self.mochi_icon_preview.setPixmap(QPixmap())
                self.mochi_icon_preview.setText("🍡")

        if hasattr(self, "mochi_import_btn"):
            self.mochi_import_btn.setText(
                tr("mochi_replace_image", "Replace image") if has_custom
                else tr("mochi_choose_image", "Choose image…")
            )

    # --- Onigimon: Ankimon dependency status ---------------------------------
    def _ankimon_status(self):
        """(state, title, detail) for the Ankimon dependency banner.

        state is one of: ok | warn | error — it only drives the banner colour.
        """
        try:
            onigimon = _onigimon_module()
            status = onigimon.manager.bridge.status()
        except Exception as exc:
            return (
                "error",
                tr("ankimon_status_unknown", "Could not check Ankimon"),
                str(exc),
            )

        if status == "missing":
            return (
                "error",
                tr("ankimon_status_missing_title", "Ankimon is not installed"),
                tr(
                    "ankimon_status_missing_detail",
                    "Onigimon runs on top of Ankimon. Install the Ankimon add-on, restart "
                    "Anki, then choose a Pokémon in Ankimon's Pokémon PC.",
                ),
            )
        if status in ("starter_needed", "no_collection"):
            return (
                "warn",
                tr("ankimon_status_no_pokemon_title", "No Pokémon chosen yet"),
                tr(
                    "ankimon_status_no_pokemon_detail",
                    "Ankimon is installed. Open Ankimon's Pokémon PC and pick a Pokémon — "
                    "that Pokémon becomes your Onigimon companion.",
                ),
            )
        return (
            "ok",
            tr("ankimon_status_ready_title", "Ankimon is installed"),
            tr(
                "ankimon_status_ready_detail",
                "The active Pokémon in Ankimon's Pokémon PC is your Onigimon companion.",
            ),
        )

    def _create_ankimon_status_card(self):
        state, title, detail = self._ankimon_status()
        colors = {
            "ok": "#2FA36B",
            "warn": "#E0912F",
            "error": "#E05252",
        }
        color = colors.get(state, colors["warn"])

        card = QFrame()
        card.setObjectName("ankimonStatusCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setStyleSheet(f"""
            QFrame#ankimonStatusCard {{
                background-color: {self._rgba_from_hex(color, 0.10)};
                border: 1px solid {self._rgba_from_hex(color, 0.32)};
                border-radius: 18px;
            }}
        """)

        row = QHBoxLayout(card)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(12)

        # Centrado no bloco de texto inteiro (título + descrição), não na linha
        # do título.
        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        dot.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        row.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

        text_box = QWidget()
        text_box.setStyleSheet("background: transparent;")
        text_layout = QVBoxLayout(text_box)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 14px; font-weight: 500; color: {color}; background: transparent;")
        text_layout.addWidget(title_label)

        detail_label = QLabel(detail)
        detail_label.setObjectName("studyZoneCardDescription")
        detail_label.setWordWrap(True)
        detail_label.setMinimumWidth(0)
        text_layout.addWidget(detail_label)

        row.addWidget(text_box, 1)
        return card

    # --- Onigimon: scene card ------------------------------------------------
    def _create_onigimon_widget_preview(self):
        """A 1:1 mock of the real 2x3 Onigimon widget: title bar, coloured scene
        on top, neutral meter panel underneath, fused with a flat seam.

        Mirrors onigimon.py's `.onigimon-card` markup and onigiri_renderer.py's
        `.onigimon-top` / `.onigimon-bottom` rules so what the user styles here
        is what the deck browser shows.
        """
        tokens = self._theme_tokens()

        shell = QFrame()
        shell.setObjectName("onigimonWidgetPreview")
        shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        shell.setStyleSheet(f"""
            QFrame#onigimonWidgetPreview {{
                background-color: {tokens["panel"]};
                border: 1px solid {tokens["border"]};
                border-radius: 18px;
            }}
        """)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(14, 12, 14, 14)
        shell_layout.setSpacing(10)

        head = QLabel("ONIGIMON")
        head.setStyleSheet(
            f"color: {tokens['muted']}; font-size: 11px; font-weight: 500;"
            " letter-spacing: 1.2px; background: transparent;"
        )
        shell_layout.addWidget(head)

        # The card: top + bottom fused, card owns the outer corners.
        card = QFrame()
        card.setObjectName("onigimonPreviewCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # --- top (coloured scene) ---
        self.onigimon_scene_preview = QFrame()
        self.onigimon_scene_preview.setObjectName("onigimonScenePreview")
        self.onigimon_scene_preview.setMinimumHeight(112)
        self.onigimon_scene_preview.installEventFilter(self)
        self.onigimon_scene_preview_bg = QLabel(self.onigimon_scene_preview)
        self.onigimon_scene_preview_bg.setObjectName("onigimonScenePreviewBackground")
        self.onigimon_scene_preview_bg.setScaledContents(False)
        self.onigimon_scene_preview_bg.lower()

        top_layout = QHBoxLayout(self.onigimon_scene_preview)
        top_layout.setContentsMargins(14, 16, 14, 16)
        top_layout.setSpacing(14)

        self.onigimon_scene_preview_sprite = QLabel()
        self.onigimon_scene_preview_sprite.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.onigimon_scene_preview_sprite.setFixedSize(96, 96)
        self.onigimon_scene_preview_sprite.setStyleSheet(
            "font-weight: 500; background: transparent; color: rgba(0,0,0,0.58);"
        )
        top_layout.addWidget(self.onigimon_scene_preview_sprite, 0, Qt.AlignmentFlag.AlignVCenter)

        info_box = QWidget()
        info_box.setStyleSheet("background: transparent;")
        info_layout = QVBoxLayout(info_box)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(3)
        self.onigimon_preview_name_label = QLabel("Onigimon")
        self.onigimon_preview_level_label = QLabel(f"{tr('onigimon_level', 'Level')} 1")
        info_layout.addWidget(self.onigimon_preview_name_label)
        info_layout.addWidget(self.onigimon_preview_level_label)
        top_layout.addWidget(info_box, 1)

        card_layout.addWidget(self.onigimon_scene_preview)

        # --- bottom (meter panel) ---
        self.onigimon_bottom_preview = QFrame()
        self.onigimon_bottom_preview.setObjectName("onigimonBottomPreview")
        self.onigimon_bottom_preview.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bottom_layout = QVBoxLayout(self.onigimon_bottom_preview)
        bottom_layout.setContentsMargins(14, 12, 14, 12)
        bottom_layout.setSpacing(5)

        self.onigimon_preview_meters = []
        meters = [
            ("HP", 100, "#08c46b", "20"),
            (tr("onigimon_status_happiness", "Happiness"), 62, "#ffbd55", "31"),
            (tr("onigimon_status_hygiene", "Hygiene"), 80, "#21b7d6", "40"),
            (tr("onigimon_status_training", "Training"), 45, "#c866e5", "30"),
            (tr("onigimon_status_hunger", "Hunger"), 26, "#f45bb3", "26"),
        ]
        for label_text, fraction, color, value_text in meters:
            bottom_layout.addLayout(self._create_onigimon_preview_meter(label_text, fraction, color, value_text))

        card_layout.addWidget(self.onigimon_bottom_preview)
        shell_layout.addWidget(card)
        return shell

    def _create_onigimon_preview_meter(self, label_text, fraction, color, value_text):
        """One meter row, matching `.onigimon-meter`'s 68px / 34px / rest grid."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        name = QLabel(str(label_text).upper())
        name.setFixedWidth(68)
        name.setObjectName("onigimonPreviewMeterLabel")
        row.addWidget(name)

        value = QLabel(str(value_text))
        value.setFixedWidth(34)
        value.setObjectName("onigimonPreviewMeterValue")
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(value)

        track = QFrame()
        track.setObjectName("onigimonPreviewMeterTrack")
        track.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        track.setFixedHeight(7)
        track_layout = QHBoxLayout(track)
        track_layout.setContentsMargins(0, 0, 0, 0)
        track_layout.setSpacing(0)

        fill = QFrame()
        fill.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fill.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
        track_layout.addWidget(fill, max(1, int(fraction)))
        if fraction < 100:
            spacer = QWidget()
            spacer.setStyleSheet("background: transparent;")
            track_layout.addWidget(spacer, 100 - int(fraction))

        row.addWidget(track, 1)
        self.onigimon_preview_meters.append((name, value, track))
        return row

    def _create_onigimon_scene_card(self):
        """Scene settings, reorganised: one live widget preview on top, then a
        flat list of labelled setting rows instead of buttons scattered across
        the card. The two colour rows lead — they pair with the two halves of
        the preview above — and the effect controls follow."""
        card, layout = self._create_study_zone_card(
            tr("onigimon_scene_title", "Scene"),
            tr(
                "onigimon_scene_desc",
                "Everything below styles the deck-browser widget shown here.",
            ),
        )

        layout.addWidget(self._create_onigimon_widget_preview())

        # Rows 1/2 — the two colours, stacked: the scene on top of the card,
        # then the stats panel underneath it, same order as the preview.
        layout.addWidget(self._create_setting_row(
            tr("background_color", "Background"),
            [self.onigimon_scene_color_button,
             self.onigimon_scene_import_button,
             self.onigimon_scene_clear_button],
        ))
        layout.addWidget(self._create_setting_row(
            tr("onigimon_stats_panel", "Stats panel"),
            [self.onigimon_bottom_color_button, self.onigimon_bottom_reset_button],
        ))

        # Rows 3/4 — background effect sliders.
        layout.addWidget(self._create_slider_row(
            tr("onigimon_blur_intensity", "Blur"),
            self.onigimon_scene_blur_slider,
            self.onigimon_scene_blur_value_label,
        ))
        layout.addWidget(self._create_slider_row(
            tr("background_opacity", "Opacity"),
            self.onigimon_scene_opacity_slider,
            self.onigimon_scene_opacity_value_label,
        ))

        # Row 5 — sprite mode.
        layout.addWidget(self._create_setting_row(
            tr("onigimon_sprite_mode_label", "Sprite mode"),
            [self.onigimon_sprite_mode_widget],
        ))

        self._update_onigimon_scene_controls()
        return card

    def _create_setting_row(self, label_text, controls):
        """Label on the left, controls right-aligned — one consistent shape used
        by every settings card so no control floats loose."""
        row = QFrame()
        row.setObjectName("settingRow")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 8, 10, 8)
        layout.setSpacing(8)
        layout.addWidget(QLabel(label_text), 0)
        layout.addStretch(1)
        for control in controls:
            layout.addWidget(control, 0)
        return row

    def _create_slider_row(self, label_text, slider, value_label):
        row = QFrame()
        row.setObjectName("settingRow")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)
        label = QLabel(label_text)
        label.setMinimumWidth(110)
        layout.addWidget(label, 0)
        layout.addWidget(slider, 1)
        layout.addWidget(value_label, 0)
        return row

    def _style_onigimon_bottom_color_button(self):
        """Paint the panel swatch with the colour it applies, and hide the reset
        button while the widget default is still in use."""
        if not hasattr(self, "onigimon_bottom_color_button"):
            return
        color = self.onigimon_bottom_color or self._default_onigimon_bottom_color()
        text_color = "#f0f0f0" if QColor(color).lightness() < 128 else "#111111"
        self.onigimon_bottom_color_button.setStyleSheet(
            f"QPushButton#onigimonSceneButton {{ background-color: {color}; color: {text_color};"
            " border: 1px solid rgba(120,120,120,0.42); border-radius: 18px; padding: 8px 16px;"
            " min-height: 36px; font-weight: 500; }"
        )
        if hasattr(self, "onigimon_bottom_reset_button"):
            self.onigimon_bottom_reset_button.setVisible(bool(self.onigimon_bottom_color))

    def _choose_onigimon_bottom_color(self):
        current = self.onigimon_bottom_color or self._default_onigimon_bottom_color()
        chosen, ok = OnigiriColorDialog.getColor(current, self, anchor=self.onigimon_bottom_color_button)
        if ok:
            self.onigimon_bottom_color = chosen.name() if isinstance(chosen, QColor) else str(chosen)
            self._update_onigimon_scene_controls()

    def _reset_onigimon_bottom_color(self):
        self.onigimon_bottom_color = ""
        self._update_onigimon_scene_controls()

    def _default_onigimon_bottom_color(self):
        """The widget's built-in stats-panel shade (onigiri_renderer.py
        `.onigimon-bottom`), used when the user hasn't picked one."""
        return "#2e2e2d" if theme_manager.night_mode else "#efefec"

    def _create_onigimon_hero(self):
        hero = QFrame()
        hero.setObjectName("onigimonHero")
        hero.setMinimumHeight(132)
        hero.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        bg_path = os.path.join(self.addon_path, "system_files", "gamification_images", "pokemon_bg.png")
        css_bg = bg_path.replace("\\", "/")
        if os.path.exists(bg_path):
            hero.setStyleSheet(f"""
                QFrame#onigimonHero {{
                    border-radius: 18px;
                    background-image: url('{css_bg}');
                    background-position: center;
                    background-repeat: repeat-x;
                    background-size: auto 100%;
                }}
            """)
        else:
            hero.setStyleSheet("QFrame#onigimonHero { border-radius: 18px; background: #1e3c52; }")

        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setFixedSize(76, 76)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("background: transparent;")
        icon_path = os.path.join(self.addon_path, "system_files", "gamification_images", "pokemon_pikachu.webp")
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon_label.setPixmap(self._scaled_for_display(pixmap, 72, 72))
        hero_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        text_container = QWidget()
        text_container.setStyleSheet("background: transparent;")
        text_container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(5)

        title = QLabel("Onigimon")
        title.setStyleSheet("font-size: 20px; font-weight: 500; color: white; background: transparent;")
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        desc = QLabel("Use Ankimon's Pokémon PC to choose the active Pokémon, then feed, clean, train, and play while Onigimon updates Ankimon.")
        desc.setWordWrap(True)
        desc.setMinimumWidth(0)
        desc.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        desc.setStyleSheet("font-size: 12px; color: rgba(255,255,255,0.92); background: transparent;")
        text_layout.addStretch()
        text_layout.addWidget(title)
        text_layout.addWidget(desc)
        text_layout.addStretch()
        hero_layout.addWidget(text_container, 1)
        hero_layout.addWidget(self.onigimon_toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        return hero

    def create_onigimon_page(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(16)

        layout.addWidget(self._create_study_zone_header(
            "Onigimon",
            tr("onigimon_page_desc"),
            "pokemon_pikachu.webp",
            "#F2B705",
            self.onigimon_toggle
        ))

        layout.addWidget(self._create_ankimon_status_card())

        companion_group, companion_layout = self._create_study_zone_card(tr("onigimon_companion_title"))
        companion_layout.addWidget(self.onigimon_companion_status_label)
        companion_layout.addWidget(QLabel(tr("onigimon_nickname_label")))
        companion_layout.addWidget(self.onigimon_name_input)
        tile_scroll = QScrollArea()
        tile_scroll.setWidgetResizable(True)
        tile_scroll.setMinimumHeight(92)
        tile_scroll.setMaximumHeight(170)
        tile_scroll.setFrameShape(QFrame.Shape.NoFrame)
        tile_scroll.setStyleSheet("background: transparent;")
        tile_scroll.setWidget(self.onigimon_companion_grid)
        companion_layout.addWidget(tile_scroll)
        refresh_btn = QPushButton(tr("onigimon_refresh_button"))
        refresh_btn.clicked.connect(self._populate_onigimon_companion_combo)
        companion_layout.addWidget(refresh_btn)
        starter_note = QLabel(tr("onigimon_starter_note"))
        starter_note.setWordWrap(True)
        starter_note.setMinimumWidth(0)
        companion_layout.addWidget(starter_note)
        layout.addWidget(companion_group)

        layout.addWidget(self._create_onigimon_scene_card())

        difficulty_group, difficulty_layout = self._create_study_zone_card(tr("onigimon_difficulty_title"))
        difficulty_note = QLabel(tr("onigimon_difficulty_note"))
        difficulty_note.setWordWrap(True)
        difficulty_layout.addWidget(difficulty_note)
        difficulty_cards = QVBoxLayout()
        difficulty_cards.setSpacing(10)
        for data in ("bulbassaur", "pikachu", "charizard"):
            difficulty_cards.addWidget(self.onigimon_difficulty_widgets[data])
        difficulty_layout.addLayout(difficulty_cards)
        layout.addWidget(difficulty_group)

        bridge_group, bridge_layout = self._create_study_zone_card(tr("onigimon_bridge_title"))
        bridge_layout.addWidget(self._create_toggle_row(self.onigimon_ankimon_updates_toggle, tr("onigimon_bridge_toggle")))
        bridge_layout.addWidget(self._create_toggle_row(self.onigimon_streak_warning_toggle, tr("onigimon_streak_warning_toggle")))
        bridge_note = QLabel(tr("onigimon_bridge_note"))
        bridge_note.setWordWrap(True)
        bridge_layout.addWidget(bridge_note)
        layout.addWidget(bridge_group)

        credits_group, credits_layout = self._create_study_zone_card(tr("onigimon_credits_title"))
        credit = QLabel(tr("onigimon_credits_text"))
        credit.setWordWrap(True)
        credits_layout.addWidget(credit)
        layout.addWidget(credits_group)

        layout.addStretch()
        if not self.onigimon_companions_loaded:
            QTimer.singleShot(0, self._populate_onigimon_companion_combo)
        return page

    def _rgba_from_hex(self, color, alpha):
        qcolor = QColor(color)
        if not qcolor.isValid():
            return f"rgba(120, 120, 120, {alpha})"
        return f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {alpha})"

    def _mix_hex_color(self, color, other, self_pct):
        """Equivalent of CSS color-mix(in srgb, color self_pct%, other (100-self_pct)%)."""
        qcolor = QColor(color)
        qother = QColor(other)
        if not qcolor.isValid():
            qcolor = QColor("#6ea96a")
        if not qother.isValid():
            qother = QColor("#ffffff")
        other_pct = 1.0 - self_pct
        r = round(qcolor.red() * self_pct + qother.red() * other_pct)
        g = round(qcolor.green() * self_pct + qother.green() * other_pct)
        b = round(qcolor.blue() * self_pct + qother.blue() * other_pct)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _create_study_zone_header(self, title, description, image_filename, accent, toggle=None):
        header = QFrame()
        header.setObjectName("studyZoneHeader")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header.setMinimumHeight(118)
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(16)

        icon_shell = QLabel()
        icon_shell.setObjectName("studyZoneIconShell")
        icon_shell.setFixedSize(62, 62)
        icon_shell.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_shell.setStyleSheet(f"""
            QLabel#studyZoneIconShell {{
                background-color: {self._rgba_from_hex(accent, 0.14)};
                border: 1px solid {self._rgba_from_hex(accent, 0.26)};
                border-radius: 18px;
            }}
        """)
        icon_path = os.path.join(self.addon_path, "system_files", "gamification_images", image_filename)
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon_shell.setPixmap(self._scaled_for_display(pixmap, 44, 44))
        else:
            icon_shell.setPixmap(self._render_system_icon(image_filename, 38, accent))
        layout.addWidget(icon_shell, 0, Qt.AlignmentFlag.AlignVCenter)

        text_box = QWidget()
        text_box.setStyleSheet("background: transparent;")
        text_layout = QVBoxLayout(text_box)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setObjectName("studyZoneTitle")
        text_layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setObjectName("studyZoneDescription")
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)

        layout.addWidget(text_box, 1)
        if toggle is not None:
            layout.addWidget(toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        return header

    def _create_study_zone_card(self, title, description=""):
        card = QFrame()
        card.setObjectName("studyZoneCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("studyZoneCardTitle")
        layout.addWidget(title_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setObjectName("studyZoneCardDescription")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        return card, layout

    def _create_study_zone_message_card(self, title, description, editor, accent):
        card, layout = self._create_study_zone_card(title, description)
        layout.addWidget(editor)
        return card

    def create_focus_dango_page(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(16)
        header = self._create_study_zone_header(
            tr("focus_dango"),
            tr("dango_help_focus"),
            "dango.webp",
            "#9D3D64",
            self.focus_dango_toggle
        )
        layout.addWidget(header)
        layout.addWidget(self._create_study_zone_message_card(
            tr("focus_dango_messages"),
            tr("message_editor_desc", "Create one message per card. Add, reorder, or remove them without worrying about line breaks."),
            self.focus_dango_message_editor,
            "#9D3D64"
        ))

        mode_card, mode_layout = self._create_study_zone_card(
            tr("focus_dango_lock_mode", "Lock Mode"),
            tr(
                "focus_dango_lock_mode_desc",
                "Keep the default mode light, or make Focus Dango stricter during reviews."
            )
        )
        sabotage_row = QHBoxLayout()
        sabotage_row.setContentsMargins(0, 0, 0, 0)
        sabotage_row.setSpacing(12)

        sabotage_text = QWidget()
        sabotage_text_layout = QVBoxLayout(sabotage_text)
        sabotage_text_layout.setContentsMargins(0, 0, 0, 0)
        sabotage_text_layout.setSpacing(4)

        sabotage_title = QLabel(tr("focus_dango_self_sabotage", "Self-Sabotage Mode"))
        sabotage_title.setObjectName("studyZoneCardTitle")
        sabotage_title.setStyleSheet("font-size: 13px;")
        sabotage_desc = QLabel(tr(
            "focus_dango_self_sabotage_desc",
            "Aggressively blocks attempts to reach the rest of Anki while reviewing."
        ))
        sabotage_desc.setObjectName("studyZoneCardDescription")
        sabotage_desc.setWordWrap(True)
        sabotage_text_layout.addWidget(sabotage_title)
        sabotage_text_layout.addWidget(sabotage_desc)

        sabotage_row.addWidget(sabotage_text, 1)
        sabotage_row.addWidget(self.focus_dango_self_sabotage_toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        mode_layout.addLayout(sabotage_row)


        layout.addWidget(mode_card)

        layout.addStretch()
        return page

    def create_mochi_messages_page(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(16)
        header = self._create_study_zone_header(
            tr("mochi_messages_title"),
            tr("mochi_cheer_on"),
            "mochi_messenger.webp",
            "#00935C",
            self.mochi_messages_toggle
        )
        layout.addWidget(header)

        timing_card, timing_layout = self._create_study_zone_card(tr("settings"))
        interval_row = QHBoxLayout()
        interval_row.setContentsMargins(0, 0, 0, 0)
        interval_row.setSpacing(12)
        interval_row.addWidget(QLabel(tr("show_message_every")))
        interval_row.addStretch()
        interval_row.addWidget(self.mochi_interval_spinbox)
        timing_layout.addLayout(interval_row)
        layout.addWidget(timing_card)

        layout.addWidget(self._create_mochi_looks_card())

        layout.addWidget(self._create_study_zone_message_card(
            tr("mochi_messages_title"),
            tr("message_editor_desc", "Create one message per card. Add, reorder, or remove them without worrying about line breaks."),
            self.mochi_messages_editor,
            "#00935C"
        ))

        layout.addStretch()
        return page

    def _create_mochi_looks_card(self):
        """Messenger Looks — one card for everything visual about the Mochi
        notification: who sends it, and how its text and title read.

        A single tinted hero (preview + source switch) sits on top, then a flat
        run of identical setting rows. Previously this was two cards with two
        different internal layouts.
        """
        accent = "#00935C"
        tokens = self._theme_tokens()

        card, layout = self._create_study_zone_card(
            tr("mochi_looks_title", "Messenger Looks"),
            tr(
                "mochi_looks_desc",
                "Choose who delivers the messages, and how the notification text reads.",
            ),
        )

        # --- hero: the preview and who it is ------------------------------
        hero = QFrame()
        hero.setObjectName("mochiLooksHero")
        hero.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hero.setStyleSheet(f"""
            QFrame#mochiLooksHero {{
                background-color: {self._rgba_from_hex(accent, 0.08)};
                border: 1px solid {self._rgba_from_hex(accent, 0.22)};
                border-radius: 18px;
            }}
            QFrame#mochiLooksHero QLabel {{ background: transparent; }}
        """)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(14, 12, 14, 12)
        hero_layout.setSpacing(14)

        self.mochi_icon_preview = QLabel()
        self.mochi_icon_preview.setFixedSize(56, 56)
        self.mochi_icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mochi_icon_preview.setStyleSheet(
            "QLabel {"
            f"  border: 1px solid {self._rgba_from_hex(accent, 0.26)};"
            "  border-radius: 18px;"
            f"  background: {self._rgba_from_hex(accent, 0.10)};"
            "  font-size: 26px;"
            "}"
        )
        hero_layout.addWidget(self.mochi_icon_preview, 0, Qt.AlignmentFlag.AlignVCenter)

        hero_label = QLabel(tr("mochi_source_label", "Messenger"))
        hero_label.setStyleSheet(f"font-size: 13px; color: {tokens['fg']};")
        hero_layout.addWidget(hero_label, 0, Qt.AlignmentFlag.AlignVCenter)
        hero_layout.addStretch(1)

        self.mochi_icon_source_widget = GooeyPillSwitch(
            "mochi", "custom",
            tr("mochi_option_mochi", "Mochi"), tr("mochi_option_custom", "Custom"),
            accent_color=accent,
        )
        self.mochi_icon_source_widget.setFixedHeight(38)
        self.mochi_icon_source_widget.setMinimumWidth(180)
        self.mochi_icon_source_widget.setValue(self.mochi_icon_choice, animate=False)
        self.mochi_icon_source_widget.modeChanged.connect(self._set_mochi_icon_choice)
        hero_layout.addWidget(self.mochi_icon_source_widget, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(hero)

        # --- image ---------------------------------------------------------
        self.mochi_import_btn = QPushButton(tr("mochi_choose_image", "Choose image…"))
        self.mochi_import_btn.clicked.connect(self._import_mochi_custom_icon)
        self.mochi_custom_remove_btn = QPushButton(tr("mochi_remove_image", "Remove"))
        self.mochi_custom_remove_btn.clicked.connect(self._clear_mochi_custom_icon)
        layout.addWidget(self._create_setting_row(
            tr("mochi_custom_image_label", "Custom image"),
            [self.mochi_import_btn, self.mochi_custom_remove_btn],
        ))

        hint = QLabel(tr(
            "mochi_image_hint_short",
            "WebP, PNG, JPG or GIF — a square ~256×256 px image with a transparent "
            "background looks best.",
        ))
        hint.setObjectName("studyZoneCardDescription")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # --- text ----------------------------------------------------------
        self.mochi_color_reset_btn = QPushButton(tr("mochi_color_default", "Default"))
        self.mochi_color_reset_btn.clicked.connect(self._reset_mochi_text_color)
        self.mochi_color_swatch = QPushButton()
        self.mochi_color_swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        # No fixed size and no stylesheet of its own: it takes the same chrome as
        # "Choose image…" and the font button next to it, and shows the colour as
        # a dot icon instead of being one big coloured slab.
        self.mochi_color_swatch.setIconSize(QSize(14, 14))
        self.mochi_color_swatch.clicked.connect(self._choose_mochi_text_color)
        layout.addWidget(self._create_setting_row(
            tr("mochi_message_color", "Message color"),
            [self.mochi_color_reset_btn, self.mochi_color_swatch],
        ))

        self.mochi_font_button = QPushButton()
        self.mochi_font_button.setMinimumWidth(150)
        self.mochi_font_button.clicked.connect(self._open_mochi_font_picker)
        layout.addWidget(self._create_setting_row(
            tr("mochi_message_font", "Message font"),
            [self.mochi_font_button],
        ))

        self.mochi_title_name_input.setFixedWidth(180)
        self.mochi_title_row = self._create_setting_row(
            tr("mochi_title_label", "Title text"),
            [self.mochi_title_name_input],
        )
        layout.addWidget(self.mochi_title_row)
        layout.addWidget(self._create_setting_row(
            tr("mochi_hide_title", "Hide notification title"),
            [self.mochi_hide_title_toggle],
        ))

        # Dim the title field while the title is hidden — it has no effect then.
        self.mochi_hide_title_toggle.toggled.connect(self._update_mochi_title_row_state)
        self._update_mochi_title_row_state(self.mochi_hide_title_toggle.isChecked())

        self._update_mochi_icon_controls()
        self._update_mochi_style_controls()
        return card

    def _update_mochi_title_row_state(self, hidden):
        if hasattr(self, "mochi_title_row"):
            self.mochi_title_row.setEnabled(not hidden)

    def _mochi_font_family(self, font_key):
        if not font_key or font_key == "system":
            return ""
        cache = self._mochi_font_family_cache
        if font_key in cache:
            return cache[font_key]
        info = get_all_fonts(self.addon_path).get(font_key, {})
        font_file = info.get("file")
        if not font_file:
            cache[font_key] = info.get("family", "")
            return cache[font_key]
        if info.get("user"):
            path = os.path.join(self.addon_path, "user_files", "fonts", font_file)
        else:
            path = os.path.join(self.addon_path, "system_files", "fonts", "system_fonts", font_file)
        if not os.path.exists(path):
            cache[font_key] = info.get("family", "")
            return cache[font_key]
        font_id = QFontDatabase.addApplicationFont(path)
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id != -1 else []
        cache[font_key] = families[0] if families else info.get("family", "")
        return cache[font_key]

    def _update_mochi_style_controls(self):
        if hasattr(self, "mochi_color_swatch"):
            # A normal row button — same fill, border and radius as the buttons
            # around it — carrying a colour dot plus the hex, rather than being
            # one big coloured slab. When nothing is configured this shows the
            # notification's own default colour (web/notifications.css).
            is_custom = bool(self.mochi_text_color) and QColor(self.mochi_text_color).isValid()
            color = self.mochi_text_color if is_custom else self._mochi_default_text_color()
            qcolor = QColor(color)
            self.mochi_color_swatch.setIcon(QIcon(self._color_dot_pixmap(qcolor)))
            self.mochi_color_swatch.setText(qcolor.name().upper())
            self.mochi_color_reset_btn.setVisible(is_custom)

        if hasattr(self, "mochi_font_button"):
            key = self.mochi_font_key or "system"
            info = get_all_fonts(self.addon_path).get(key, {})
            display = tr("system") if key == "system" else info.get("name", key)
            # Just the family name — the row's own label already says what it is,
            # so the old "… · click to change" suffix was noise.
            self.mochi_font_button.setText(display)
            font = QFont()
            family = self._mochi_font_family(key)
            if family:
                font.setFamily(family)
            self.mochi_font_button.setFont(font)

    def _color_dot_pixmap(self, color, size=14):
        """A filled circle with a hairline ring, for use as a button icon."""
        device_ratio = _safe_device_pixel_ratio(self)
        render = max(1, int(round(size * device_ratio)))
        pixmap = QPixmap(render, render)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(QColor(color))
        painter.setPen(QPen(QColor(0, 0, 0, 60), max(1.0, device_ratio)))
        inset = device_ratio
        painter.drawEllipse(QRectF(inset, inset, render - inset * 2, render - inset * 2))
        painter.end()
        pixmap.setDevicePixelRatio(device_ratio)
        return pixmap

    def _mochi_default_text_color(self):
        """The colour the notification uses when none is configured — mirrors
        --onigiri-notification-text-{light,dark} in web/notifications.css."""
        return "#ffffff" if theme_manager.night_mode else "#2c2c2c"

    def _choose_mochi_text_color(self):
        current = self.mochi_text_color or self._mochi_default_text_color()
        chosen, ok = OnigiriColorDialog.getColor(current, self, anchor=self.mochi_color_swatch)
        if ok:
            color = chosen.name() if isinstance(chosen, QColor) else str(chosen)
            self.mochi_text_color = color
            self._update_mochi_style_controls()

    def _reset_mochi_text_color(self):
        self.mochi_text_color = ""
        self._update_mochi_style_controls()

    def _open_mochi_font_picker(self):
        dialog = FontPickerDialog(
            self.mochi_font_key or "system",
            self.addon_path,
            self,
            sample_text=tr("mochi_font_sample", "Keep going!"),
            title=tr("mochi_message_font", "Message font"),
        )

        def on_selected(font_key):
            self.mochi_font_key = font_key or "system"
            self._update_mochi_style_controls()

        dialog.fontSelected.connect(on_selected)
        dialog.exec()

    def create_hexagon_land_page(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(16)
        hexagon_land = _hexagon_land_module()

        layout.addWidget(self._create_study_zone_header(
            "Hexagon Land",
            "Build an island while you study: earn Hex Coins and materials, expand tile by tile, grow trees, invite inhabitants, and raise castles.",
            "Hexagon_world.webp",
            "#1F6FE0",
            self.hexagon_land_toggle
        ))

        settings_group, settings_layout = self._create_study_zone_card("Island Builder")
        note = QLabel("Cards studied grant Hex Coins. Trees and flowers increase the Hex Coins earned per card, and longer study history unlocks sand, stone, snow, and magic tiles.")
        note.setWordWrap(True)
        settings_layout.addWidget(note)
        open_btn = QPushButton("Open Hexagon Land")
        open_btn.clicked.connect(hexagon_land.open_hexagon_land_dialog)
        settings_layout.addWidget(open_btn)
        buy_btn = QPushButton("Get Hex Coins")
        buy_btn.clicked.connect(hexagon_land.open_buy_hex_coins)
        settings_layout.addWidget(buy_btn)
        layout.addWidget(settings_group)

        layout.addWidget(self._create_hexagon_keys_card(hexagon_land))

        self._refresh_hexagon_island_controls()

        layout.addStretch()
        return page

    def _render_island_key_pixmap(self, size=28, color="#FFFFFF"):
        """Render ISLAND_KEY_SVG at the screen's pixel ratio in the given tint."""
        device_ratio = _safe_device_pixel_ratio(self)
        render_size = max(1, int(round(size * device_ratio)))
        pixmap = QPixmap(render_size, render_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        try:
            renderer = QSvgRenderer(ISLAND_KEY_SVG.format(color=color).encode("utf-8"))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            renderer.render(painter)
            painter.end()
        except Exception as exc:
            print(f"Onigiri: Could not render island key icon: {exc}")
        pixmap.setDevicePixelRatio(device_ratio)
        return pixmap

    def _create_hexagon_keys_card(self, hexagon_land):
        """Keys of the Island.

        Uses the same card shell as every other settings card — the only thing
        setting it apart is an accent-tinted key banner, matching how the page
        heroes tint their icon shell. Everything below that is a standard row
        so it reads as part of the same dialog.
        """
        tokens = self._theme_tokens()
        accent = "#1F6FE0"

        card, layout = self._create_study_zone_card(
            tr("hexagon_keys_title", "Keys of the Island"),
            tr(
                "hexagon_keys_desc",
                "Buy the keys to name your island. The name appears on the Hexagon Land widget.",
            ),
        )

        # Accent banner: key glyph, cost, and the live balance on the right.
        banner = QFrame()
        banner.setObjectName("hexagonKeysBanner")
        banner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        banner.setStyleSheet(f"""
            QFrame#hexagonKeysBanner {{
                background-color: {self._rgba_from_hex(accent, 0.10)};
                border: 1px solid {self._rgba_from_hex(accent, 0.26)};
                border-radius: 18px;
            }}
            QFrame#hexagonKeysBanner QLabel {{ background: transparent; }}
        """)
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(14, 12, 16, 12)
        banner_layout.setSpacing(12)

        key_shell = QLabel()
        key_shell.setFixedSize(40, 40)
        key_shell.setAlignment(Qt.AlignmentFlag.AlignCenter)
        key_shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        key_shell.setStyleSheet(
            f"background-color: {self._rgba_from_hex(accent, 0.16)};"
            f" border: 1px solid {self._rgba_from_hex(accent, 0.30)};"
            " border-radius: 13px;"
        )
        key_shell.setPixmap(self._render_island_key_pixmap(20, accent))
        banner_layout.addWidget(key_shell, 0, Qt.AlignmentFlag.AlignVCenter)

        cost_label = QLabel(
            tr("hexagon_keys_cost", "{cost} Hex Coins").format(
                cost=f"{hexagon_land.KEYS_OF_THE_ISLAND_COST:,}"
            )
        )
        cost_label.setStyleSheet(f"font-size: 14px; font-weight: 500; color: {tokens['fg']};")
        banner_layout.addWidget(cost_label, 0, Qt.AlignmentFlag.AlignVCenter)
        banner_layout.addStretch(1)

        self.hexagon_keys_status_label = QLabel()
        self.hexagon_keys_status_label.setStyleSheet(f"font-size: 13px; color: {tokens['muted']};")
        self.hexagon_keys_status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        banner_layout.addWidget(self.hexagon_keys_status_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(banner)

        # Island name — a standard setting row, styled by the dialog stylesheet.
        self.hexagon_island_name_input = QLineEdit()
        self.hexagon_island_name_input.setMaxLength(40)
        self.hexagon_island_name_input.setMinimumWidth(180)
        self.hexagon_island_name_input.setPlaceholderText(tr("hexagon_island_name", "Island name"))
        self.hexagon_island_name_save_btn = QPushButton(tr("save", "Save"))
        self.hexagon_island_name_save_btn.clicked.connect(self._save_hexagon_island_name)
        layout.addWidget(self._create_setting_row(
            tr("hexagon_island_name", "Island name"),
            [self.hexagon_island_name_input, self.hexagon_island_name_save_btn],
        ))

        self.hexagon_keys_button = QPushButton(tr("hexagon_keys_buy", "Buy Keys of the Island"))
        self.hexagon_keys_button.setIcon(QIcon(self._render_island_key_pixmap(16, tokens["fg"])))
        self.hexagon_keys_button.setIconSize(QSize(16, 16))
        self.hexagon_keys_button.clicked.connect(self._buy_hexagon_keys)
        layout.addWidget(self.hexagon_keys_button)

        return card

    def create_coming_soon_page(self):
        return self.create_hexagon_land_page()

    def _refresh_hexagon_island_controls(self):
        if not hasattr(self, "hexagon_island_name_input"):
            return
        hexagon_land = _hexagon_land_module()
        state = hexagon_land.manager.load()
        owns_keys = bool(getattr(state, "keys_of_the_island", False))
        self.hexagon_island_name_input.setText(hexagon_land.manager.island_display_name(state))
        self.hexagon_island_name_input.setEnabled(owns_keys)
        self.hexagon_island_name_save_btn.setEnabled(owns_keys)
        self.hexagon_keys_button.setVisible(not owns_keys)
        # Short, because this now sits right-aligned on one meta line beside the
        # cost rather than on its own wrapped row.
        if owns_keys:
            self.hexagon_keys_status_label.setText(tr("hexagon_keys_owned", "owned"))
        else:
            self.hexagon_keys_status_label.setText(
                f"{state.hex_coins:,} / {hexagon_land.KEYS_OF_THE_ISLAND_COST:,}"
            )
            self.hexagon_keys_button.setEnabled(
                state.hex_coins >= hexagon_land.KEYS_OF_THE_ISLAND_COST
            )

    def _buy_hexagon_keys(self):
        hexagon_land = _hexagon_land_module()
        message = hexagon_land.manager.buy_keys_of_the_island()
        showInfo(message)
        self._refresh_hexagon_island_controls()

    def _save_hexagon_island_name(self):
        hexagon_land = _hexagon_land_module()
        message = hexagon_land.manager.set_island_name(self.hexagon_island_name_input.text())
        showInfo(message)
        self._refresh_hexagon_island_controls()

    # --- Actions ---

    def _confirm_sync_recipe_rush(self):
        if QMessageBox.question(
            self,
            tr("recipe_rush_sync_title", "Nook Rush Sync"),
            tr(
                "recipe_rush_sync_confirm",
                "Pick a fresh Nook Rush for the currently equipped Nook, "
                "replacing today's ticket? Today's card progress is kept.",
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            nook_level = _nook_level_module()
            success, message = nook_level.manager.force_resync_recipe_rush()
            if success:
                showInfo(tr("recipe_rush_sync_success", "Synced! New Rush: {name}").format(name=message))
            else:
                showInfo(message)

    def _confirm_reset_nook_level(self):
        if QMessageBox.question(self, tr("reset"), tr("reset_restaurant_confirm"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            nook_level = _nook_level_module()
            nook_level.manager.reset_progress()
            showInfo(tr("restaurant_level_reset_info"))

    def _reset_coins(self):
        if QMessageBox.question(self, tr("reset"), tr("reset_coins_confirm"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            nook_level = _nook_level_module()
            nook_level.manager.reset_coins()
            showInfo(tr("coins_reset_info"))

    def _reset_purchases(self):
        if QMessageBox.question(self, tr("reset"), tr("reset_purchases_confirm"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            nook_level = _nook_level_module()
            nook_level.manager.reset_purchases()
            showInfo(tr("purchases_reset_info"))

    # ------------------------------------------------------------------ #
    # Chip colour helpers                                                  #
    # ------------------------------------------------------------------ #

    def _style_restaurant_chip_color_label_button(self, button):
        tokens = self._theme_tokens()
        button.setObjectName("restaurantChipColorLabel")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(36)
        button.setStyleSheet(f"""
            QPushButton#restaurantChipColorLabel {{
                background-color: transparent;
                color: {tokens["fg"]};
                border: none;
                text-align: left;
                padding: 0px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton#restaurantChipColorLabel:hover,
            QPushButton#restaurantChipColorLabel:pressed {{
                background-color: transparent;
                border: none;
            }}
        """)

    def _create_restaurant_chip_color_card(self, label_text, button):
        tokens = self._theme_tokens()
        label_button = QPushButton(label_text)
        self._style_restaurant_chip_color_label_button(label_button)
        label_button.clicked.connect(button.click)
        button.setProperty("settingsColorSelector", True)
        button.setMinimumWidth(140)

        card = QFrame()
        card.setObjectName("restaurantChipColorCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setStyleSheet(f"""
            QFrame#restaurantChipColorCard {{
                background-color: {tokens["panel"]};
                border: 1px solid {tokens["border"]};
                border-radius: 16px;
            }}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 8, 10, 8)
        layout.setSpacing(12)
        layout.addWidget(label_button, 0)
        layout.addStretch(1)
        layout.addWidget(button, 0)
        return card

    def _create_restaurant_chip_bg_control(self, label_text, button):
        tokens = self._theme_tokens()
        control = QWidget()
        layout = QVBoxLayout(control)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        opacity_row = QWidget()
        opacity_layout = QHBoxLayout(opacity_row)
        opacity_layout.setContentsMargins(16, 0, 10, 0)
        opacity_layout.setSpacing(12)
        opacity_label = QLabel("Opacity")
        opacity_label.setStyleSheet(f"color: {tokens['fg']}; font-size: 13px; font-weight: 500;")

        slider_track = tokens["surface"]
        slider_border = tokens["border"]
        self.rl_chip_bg_opacity_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.rl_chip_bg_opacity_slider.setRange(0, 100)
        self.rl_chip_bg_opacity_value_label = QLabel("100%")
        self.rl_chip_bg_opacity_value_label.setFixedWidth(48)
        self.rl_chip_bg_opacity_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.rl_chip_bg_opacity_value_label.setStyleSheet(f"color: {tokens['fg']}; font-size: 13px; font-weight: 500;")

        current_alpha = 100
        cur_color = self._current_chip_bg_color
        if cur_color:
            _qc = QColor(cur_color)
            if _qc.isValid():
                current_alpha = int(_qc.alphaF() * 100)
        self.rl_chip_bg_opacity_slider.setValue(current_alpha)
        self.rl_chip_bg_opacity_value_label.setText(f"{current_alpha}%")

        def on_opacity_changed(val):
            self.rl_chip_bg_opacity_value_label.setText(f"{val}%")
            is_dark = config.effective_night_mode(self.current_config)
            base = self._current_chip_bg_color if self._current_chip_bg_color else ("#000000" if is_dark else "#ffffff")
            curr_color = QColor(base)
            curr_color.setAlphaF(val / 100.0)
            self._current_chip_bg_color = curr_color.name(QColor.NameFormat.HexArgb)
            self._update_restaurant_chip_preview()

        self.rl_chip_bg_opacity_slider.valueChanged.connect(on_opacity_changed)
        opacity_layout.addWidget(opacity_label, 0)
        opacity_layout.addWidget(self.rl_chip_bg_opacity_slider, 1)
        opacity_layout.addWidget(self.rl_chip_bg_opacity_value_label, 0)

        layout.addWidget(opacity_row)
        layout.addWidget(self._create_restaurant_chip_color_card(label_text, button))
        return control

    @property
    def _current_chip_bg_color(self):
        if not getattr(self, "rl_dynamic_chip_colors", False):
            return self.rl_chip_bg_color
        return self.rl_chip_bg_color_dark if getattr(self, "rl_theme_btn_group", None) and self.rl_theme_btn_group.checkedId() == 1 else self.rl_chip_bg_color_light

    @_current_chip_bg_color.setter
    def _current_chip_bg_color(self, value):
        if not getattr(self, "rl_dynamic_chip_colors", False):
            self.rl_chip_bg_color = value
        elif getattr(self, "rl_theme_btn_group", None) and self.rl_theme_btn_group.checkedId() == 1:
            self.rl_chip_bg_color_dark = value
        else:
            self.rl_chip_bg_color_light = value

    @property
    def _current_chip_progress_color(self):
        if not getattr(self, "rl_dynamic_chip_colors", False):
            return self.rl_chip_progress_color
        return self.rl_chip_progress_color_dark if getattr(self, "rl_theme_btn_group", None) and self.rl_theme_btn_group.checkedId() == 1 else self.rl_chip_progress_color_light

    @_current_chip_progress_color.setter
    def _current_chip_progress_color(self, value):
        if not getattr(self, "rl_dynamic_chip_colors", False):
            self.rl_chip_progress_color = value
        elif getattr(self, "rl_theme_btn_group", None) and self.rl_theme_btn_group.checkedId() == 1:
            self.rl_chip_progress_color_dark = value
        else:
            self.rl_chip_progress_color_light = value

    @property
    def _current_chip_text_color(self):
        if not getattr(self, "rl_dynamic_chip_colors", False):
            return self.rl_chip_text_color
        return self.rl_chip_text_color_dark if getattr(self, "rl_theme_btn_group", None) and self.rl_theme_btn_group.checkedId() == 1 else self.rl_chip_text_color_light

    @_current_chip_text_color.setter
    def _current_chip_text_color(self, value):
        if not getattr(self, "rl_dynamic_chip_colors", False):
            self.rl_chip_text_color = value
        elif getattr(self, "rl_theme_btn_group", None) and self.rl_theme_btn_group.checkedId() == 1:
            self.rl_chip_text_color_dark = value
        else:
            self.rl_chip_text_color_light = value

    def _resolved_restaurant_chip_colors(self):
        try:
            nook_level = _nook_level_module()
            preview_conf = copy.deepcopy(self.current_config)
            preview_conf.setdefault("restaurant_level", {})
            is_dark_preview = config.effective_night_mode(self.current_config)
            if getattr(self, "rl_dynamic_chip_colors", False):
                is_dark_preview = getattr(self, "rl_theme_btn_group", None) and self.rl_theme_btn_group.checkedId() == 1
                preview_conf["restaurant_level"]["dynamic_chip_colors"]       = True
                preview_conf["restaurant_level"]["chip_bg_color_light"]       = self.rl_chip_bg_color_light
                preview_conf["restaurant_level"]["chip_bg_color_dark"]        = self.rl_chip_bg_color_dark
                preview_conf["restaurant_level"]["chip_progress_color_light"] = self.rl_chip_progress_color_light
                preview_conf["restaurant_level"]["chip_progress_color_dark"]  = self.rl_chip_progress_color_dark
                preview_conf["restaurant_level"]["chip_text_color_light"]     = self.rl_chip_text_color_light
                preview_conf["restaurant_level"]["chip_text_color_dark"]      = self.rl_chip_text_color_dark
            else:
                preview_conf["restaurant_level"]["dynamic_chip_colors"]   = False
                preview_conf["restaurant_level"]["chip_bg_color"]         = self.rl_chip_bg_color
                preview_conf["restaurant_level"]["chip_progress_color"]   = self.rl_chip_progress_color
                preview_conf["restaurant_level"]["chip_text_color"]       = self.rl_chip_text_color
            return nook_level.get_chip_style_values(conf=preview_conf, is_dark=is_dark_preview)
        except Exception as exc:
            print(f"[Onigiri] Could not resolve Nook Level chip colors: {exc}")
            return {"bg": CHIP_PREVIEW_DEFAULTS["chip_bg"], "progress": CHIP_PREVIEW_DEFAULTS["chip_progress"], "text": "#ffffff"}

    def _style_restaurant_chip_color_button(self, button, color_value, fallback="#888888"):
        color      = color_value if color_value and QColor(color_value).isValid() else fallback
        qcolor     = QColor(color)
        text_color = "#111827" if qcolor.lightness() > 150 else "#ffffff"
        settings_selector = bool(button.property("settingsColorSelector"))
        radius = 12 if settings_selector else 21
        height = 36 if settings_selector else 42
        padding = "0px 18px" if settings_selector else "0px 16px"
        button.setText(qcolor.name(QColor.NameFormat.HexRgb).upper())
        button.setStyleSheet(f"""
            QPushButton#restaurantChipColorButton {{
                background-color: {color};
                color: {text_color};
                border: 1px solid rgba(128,128,128,0.4);
                border-radius: {radius}px;
                min-height: {height}px;
                max-height: {height}px;
                padding: {padding};
                font-size: 13px;
                font-weight: 500;
                letter-spacing: 0.2px;
            }}
            QPushButton#restaurantChipColorButton:hover,
            QPushButton#restaurantChipColorButton:pressed {{
                border-radius: {radius}px;
            }}
        """)

    def _update_restaurant_chip_preview(self):
        if not hasattr(self, "rl_chip_preview"):
            return
        colors = self._resolved_restaurant_chip_colors()
        self._style_restaurant_chip_color_button(self.rl_chip_bg_button,       self._current_chip_bg_color,       colors["bg"])
        self._style_restaurant_chip_color_button(self.rl_chip_progress_button, self._current_chip_progress_color, colors["progress"])
        self._style_restaurant_chip_color_button(
            self.rl_chip_text_button,
            self._current_chip_text_color,
            colors["text"] or ("#ffffff" if config.effective_night_mode(self.current_config) else "#111827"),
        )
        self.rl_chip_preview.set_chip_colors(colors["bg"], colors["progress"], colors["text"])
        if hasattr(self, "rl_chip_bg_opacity_slider"):
            self.rl_chip_bg_opacity_slider.blockSignals(True)
            qcolor = QColor(self._current_chip_bg_color if self._current_chip_bg_color else colors["bg"])
            if qcolor.isValid():
                self.rl_chip_bg_opacity_slider.setValue(int(qcolor.alphaF() * 100))
                self.rl_chip_bg_opacity_value_label.setText(f"{self.rl_chip_bg_opacity_slider.value()}%")
            self.rl_chip_bg_opacity_slider.blockSignals(False)

    def _choose_restaurant_chip_color(self, target):
        from .onigiri_color_picker import OnigiriColorDialog
        colors  = self._resolved_restaurant_chip_colors()
        current = {
            "bg":       self._current_chip_bg_color       or colors["bg"],
            "progress": self._current_chip_progress_color or colors["progress"],
            "text":     self._current_chip_text_color     or colors["text"] or "#ffffff",
        }.get(target, "#ffffff")
        chosen, ok = OnigiriColorDialog.getColor(current, self)
        if not ok:
            return
        if target == "bg":
            c = QColor(chosen)
            if hasattr(self, "rl_chip_bg_opacity_slider"):
                c.setAlphaF(self.rl_chip_bg_opacity_slider.value() / 100.0)
            self._current_chip_bg_color = c.name(QColor.NameFormat.HexArgb)
        elif target == "progress":
            self._current_chip_progress_color = chosen
        else:
            self._current_chip_text_color = chosen
        self._update_restaurant_chip_preview()

    def _reset_restaurant_chip_colors(self):
        if getattr(self, "rl_dynamic_chip_colors", False):
            self.rl_chip_bg_color_light = self.rl_chip_bg_color_dark = ""
            self.rl_chip_progress_color_light = self.rl_chip_progress_color_dark = ""
            self.rl_chip_text_color_light = self.rl_chip_text_color_dark = ""
        else:
            self.rl_chip_bg_color = self.rl_chip_progress_color = self.rl_chip_text_color = ""
        self._update_restaurant_chip_preview()

    def save_settings(self):
        if getattr(self, "_is_saving", False):
            return
        self._is_saving = True
        self.save_button.setEnabled(False)

        # Master Toggle
        self.current_config["gamificationMode"] = self.gamification_mode_toggle.isChecked()
        self.current_config["onigiri_notification_duration_ms"] = self.notification_duration_spinbox.value() * 1000
        
        self.current_config["onigiri_reviewer_notification_mode"] = self.notification_mode_widget.value()
        
        # Focused Gaming — if enabled, force restaurant notifications off
        focused = self.focused_gaming_toggle.isChecked()
        self.current_config["focusedGaming"] = focused
        
        # Update current_config from widgets
        # Nook Level
        res_conf = self.current_config.setdefault("restaurant_level", {})
        res_conf["enabled"] = self.nook_level_toggle.isChecked()
        res_conf["notifications_enabled"] = self.restaurant_notifications_toggle.isChecked()
        res_conf["show_profile_bar_progress"] = self.restaurant_bar_toggle.isChecked()
        res_conf["show_reviewer_header"] = self.restaurant_reviewer_toggle.isChecked()

        # Keep the persisted gamification state in sync with the config toggles above.
        # get_progress() only pulls from config on first migration; after that it trusts
        # this state, so without these calls the chip stays stuck at its first-ever value.
        nook_level = _nook_level_module()
        nook_level.manager.set_enabled(res_conf["enabled"])
        nook_level.manager.set_notifications_enabled(res_conf["notifications_enabled"])
        nook_level.manager.set_profile_bar_visibility(res_conf["show_profile_bar_progress"])

        selected_diff = "Apprendice"
        for data, btn in self.difficulty_widgets.items():
            if btn.isChecked():
                selected_diff = data
                break
        res_conf["difficulty"] = selected_diff
        
        # Profile Level chip: which game it reflects (General page selector)
        self.current_config["profile_level_game"] = getattr(self, "profile_level_game", "nook")

        # Level Chip Appearance colors now live on the always-loaded General page.
        if "General" in self._loaded_pages:
            res_conf["chip_bg_color"]              = getattr(self, "rl_chip_bg_color",              "") or ""
            res_conf["chip_progress_color"]        = getattr(self, "rl_chip_progress_color",        "") or ""
            res_conf["chip_text_color"]            = getattr(self, "rl_chip_text_color",            "") or ""
            res_conf["dynamic_chip_colors"]        = getattr(self, "rl_dynamic_chip_colors",        False)
            res_conf["chip_bg_color_light"]        = getattr(self, "rl_chip_bg_color_light",        "") or ""
            res_conf["chip_bg_color_dark"]         = getattr(self, "rl_chip_bg_color_dark",         "") or ""
            res_conf["chip_progress_color_light"]  = getattr(self, "rl_chip_progress_color_light",  "") or ""
            res_conf["chip_progress_color_dark"]   = getattr(self, "rl_chip_progress_color_dark",   "") or ""
            res_conf["chip_text_color_light"]      = getattr(self, "rl_chip_text_color_light",      "") or ""
            res_conf["chip_text_color_dark"]       = getattr(self, "rl_chip_text_color_dark",       "") or ""

        if "Nook Level" in self._loaded_pages and hasattr(self, "restaurant_name_input"):
            nook_level = _nook_level_module()
            nook_level.manager.set_restaurant_name(self.restaurant_name_input.text())

        # Onigimon
        oni_conf = self.current_config.setdefault("onigimon", {})
        oni_conf["enabled"] = self.onigimon_toggle.isChecked()
        oni_conf["allow_ankimon_updates"] = self.onigimon_ankimon_updates_toggle.isChecked()
        oni_conf["show_streak_broken_warning"] = self.onigimon_streak_warning_toggle.isChecked()
        selected_onigimon_difficulty = "pikachu"
        for data, btn in self.onigimon_difficulty_widgets.items():
            if btn.isChecked():
                selected_onigimon_difficulty = data
                break
        oni_conf["difficulty"] = selected_onigimon_difficulty
        oni_conf["sprite_motion"] = self.onigimon_sprite_motion
        oni_conf["scene_background_color"] = self.onigimon_scene_color
        oni_conf["scene_background_image"] = self.onigimon_scene_image
        oni_conf["scene_background_blur"] = self.onigimon_scene_blur_slider.value()
        oni_conf["scene_background_opacity"] = self.onigimon_scene_opacity_slider.value()
        oni_conf["scene_bottom_color"] = getattr(self, "onigimon_bottom_color", "") or ""
        if "Onigimon" in self._loaded_pages and self.onigimon_selected_companion_id:
            onigimon = _onigimon_module()
            onigimon.manager.set_active_companion(str(self.onigimon_selected_companion_id))
            onigimon.manager.rename_active_companion(self.onigimon_name_input.text().strip())
        
        # Mochi
        mochi_conf = self.current_config.setdefault("mochi_messages", {})
        mochi_conf["enabled"] = self.mochi_messages_toggle.isChecked()
        mochi_conf["cards_interval"] = self.mochi_interval_spinbox.value()
        mochi_conf["messages"] = self.mochi_messages_editor.messages()
        # Fall back to Mochi if the custom image is missing/removed.
        if self.mochi_icon_choice == "custom" and self._mochi_custom_icon_abs_path() \
                and os.path.exists(self._mochi_custom_icon_abs_path()):
            mochi_conf["icon_choice"] = "custom"
            mochi_conf["custom_icon"] = self.mochi_custom_icon
        else:
            mochi_conf["icon_choice"] = "mochi"
            mochi_conf["custom_icon"] = self.mochi_custom_icon
        mochi_conf["text_color"] = self.mochi_text_color or ""
        mochi_conf["font"] = self.mochi_font_key or "system"
        mochi_conf["title_name"] = self.mochi_title_name_input.text().strip()
        mochi_conf["hide_title"] = self.mochi_hide_title_toggle.isChecked()

        # Focus Dango
        dango_conf = self.achievements_config.setdefault("focusDango", {})
        dango_conf["enabled"] = self.focus_dango_toggle.isChecked()
        dango_conf["messages"] = self.focus_dango_message_editor.messages()
        dango_conf["self_sabotage"] = self.focus_dango_self_sabotage_toggle.isChecked()


        # Hexagon Land
        hex_conf = self.current_config.setdefault("hexagon_land", {})
        hex_conf["enabled"] = self.hexagon_land_toggle.isChecked()
        hex_conf["theme"] = "island"
        if "Hexagon Land" in self._loaded_pages and hasattr(self, "hexagon_island_name_input"):
            hexagon_land = _hexagon_land_module()
            state = hexagon_land.manager.load()
            if getattr(state, "keys_of_the_island", False):
                hexagon_land.manager.set_island_name(self.hexagon_island_name_input.text())

        # Save config
        config.write_config(self.current_config)

        try:
            from .refresh import schedule_ui_refresh

            schedule_ui_refresh()
        except Exception:
            pass
        self.accept()
        QTimer.singleShot(300, self._initialize_enabled_hooks_after_save)

    def _initialize_enabled_hooks_after_save(self):
        try:
            restaurant_conf = self.current_config.get("restaurant_level", {})
            if restaurant_conf.get("enabled", False):
                from .gamification import nook_level as _nook_level  # noqa: F401
            if self.current_config.get("onigimon", {}).get("enabled", False):
                from .gamification import onigimon as _onigimon  # noqa: F401
            if self.current_config.get("mochi_messages", {}).get("enabled", False):
                from .gamification import mochi_messages as _mochi_messages  # noqa: F401
            focus_conf = self.current_config.get("achievements", {}).get("focusDango", {})
            if focus_conf.get("enabled", False):
                from .gamification import focus_dango

                focus_dango.setup_focus_dango()
        except Exception as e:
            print(f"Onigiri: Error refreshing gamification hooks after save: {e}")

    def apply_stylesheet(self):
        tokens = self._theme_tokens()
        bg = tokens["bg"]
        content_bg = tokens["panel"]
        fg = tokens["fg"]
        muted = tokens["muted"]
        inner_group_bg = tokens["panel"]
        surface_bg = tokens["surface"]
        border = tokens["border"]
        hover_bg = tokens["surface"]
        accent = tokens["accent"]
        scrollbar_thumb = "rgba(255, 255, 255, 0.20)" if theme_manager.night_mode else "rgba(17, 24, 39, 0.16)"
        scrollbar_thumb_hover = "rgba(255, 255, 255, 0.34)" if theme_manager.night_mode else "rgba(17, 24, 39, 0.28)"
        notification_checked_bg = self._rgba_from_hex(accent, 0.16)
        notification_spinbox_up_icon = self._tinted_stylesheet_svg_path("up.svg", fg)
        notification_spinbox_down_icon = self._tinted_stylesheet_svg_path("down.svg", fg)
        study_zone_spinbox_up_icon = self._tinted_stylesheet_svg_path("up.svg", fg)
        study_zone_spinbox_down_icon = self._tinted_stylesheet_svg_path("down.svg", fg)

        self.setStyleSheet(f"""
            /* Poppins everywhere, never heavier than Medium (500). Registered
               into Qt in __init__ via register_poppins_qt(). */
            * {{
                font-family: 'Poppins';
                font-weight: 400;
            }}
            QDialog {{ background-color: {bg}; color: {fg}; }}
            QWidget#settingsSidebarWrapper {{
                background-color: {bg};
                border: none;
            }}
            #sidebarContainer {{ 
                background-color: {bg};
                border: none;
            }}
            QScrollArea#sidebarNavScrollArea {{
                background-color: {bg};
                border: none;
            }}
            QWidget#sidebarNavViewport {{
                background-color: {bg};
            }}
            /* Minimal sidebar — section headers (collapsible) */
            QPushButton#sidebarSectionToggle {{
                color: {muted};
                background: transparent;
                border: none;
                border-radius: 12px;
                font-size: 10px;
                font-weight: 500;
                letter-spacing: 0.7px;
                padding: 4px 8px;
                text-align: left;
            }}
            QPushButton#sidebarSectionToggle:hover {{
                color: {fg};
                background-color: {surface_bg};
            }}
            QPushButton#sidebarSectionToggle:checked {{
                color: {muted};
                background: transparent;
                font-weight: 500;
            }}
            QWidget#sidebarSectionContent {{
                background: transparent;
                border: none;
            }}
            /* Minimal sidebar — nav buttons */
            QPushButton#sidebarNavButton {{
                min-height: 28px;
                padding: 4px 10px;
                border-radius: 18px;
                background-color: transparent;
                border: 1px solid transparent;
                text-align: left;
                font-size: 13px;
                font-weight: 500;
                color: {muted};
            }}
            QPushButton#sidebarNavButton:hover {{
                background-color: {surface_bg};
                color: {fg};
                border-color: transparent;
            }}
            QPushButton#sidebarNavButton:checked {{
                background-color: {surface_bg};
                color: {fg};
                border-color: transparent;
                font-weight: 500;
            }}
            QScrollArea#sidebarNavScrollArea QScrollBar:vertical {{
                border: none;
                background-color: transparent;
                width: 6px;
                margin: 12px 2px 12px 2px;
                border-radius: 3px;
            }}
            QScrollArea#sidebarNavScrollArea QScrollBar::handle:vertical {{
                background-color: {scrollbar_thumb};
                min-height: 38px;
                border-radius: 3px;
            }}
            QScrollArea#sidebarNavScrollArea QScrollBar::handle:vertical:hover {{
                background-color: {scrollbar_thumb_hover};
            }}
            QScrollArea#sidebarNavScrollArea QScrollBar::add-line:vertical,
            QScrollArea#sidebarNavScrollArea QScrollBar::sub-line:vertical,
            QScrollArea#sidebarNavScrollArea QScrollBar::add-page:vertical,
            QScrollArea#sidebarNavScrollArea QScrollBar::sub-page:vertical {{
                height: 0;
                width: 0;
                background: none;
                border: none;
            }}
            /* Rounded content shell around each page (matches Onigiri) */
            /* Only the top corners are rounded — the two bottom edges stay
               square so each settings page reads as a sheet rising from the
               bottom of the window. */
            QFrame#contentContainer {{
                background-color: {content_bg};
                border: none;
                border-top-left-radius: 28px;
                border-top-right-radius: 28px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }}
            QStackedWidget#contentStack {{
                background-color: transparent;
            }}
            
            /* Save button - always white pill with fixed height */
            QPushButton#saveButton {{
                background-color: {accent};
                color: #ffffff;
                border: none;
                border-radius: 19px;
                min-height: 38px;
                max-height: 38px;
                padding: 0px 14px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton#saveButton:hover {{
                background-color: {accent};
            }}
            QPushButton#saveButton:pressed {{
                background-color: {accent};
            }}
            QPushButton#cancelButton {{
                background-color: {surface_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 19px;
                min-height: 38px;
                max-height: 38px;
                padding: 0px 14px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton#cancelButton:hover {{
                background-color: {hover_bg};
            }}
            QPushButton#cancelButton:pressed {{
                background-color: {border};
            }}

            QWidget#gamificationModeHero, QWidget#focusedGamingHero {{ 
                background-color: {surface_bg}; 
                border: 1px solid {border}; 
                border-radius: 20px; 
            }}

            QFrame#studyZoneHeader {{
                background-color: {surface_bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QLabel#studyZoneTitle {{
                color: {fg};
                background: transparent;
                font-size: 22px;
                font-weight: 500;
            }}
            QLabel#studyZoneDescription {{
                color: {muted};
                background: transparent;
                font-size: 13px;
                line-height: 18px;
            }}
            QFrame#studyZoneCard {{
                background-color: {inner_group_bg};
                border: 1px solid {border};
                border-radius: 24px;
            }}
            QFrame#studyZoneCard QPushButton {{
                background-color: {surface_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 18px;
                padding: 8px 16px;
                font-weight: 500;
            }}
            QFrame#studyZoneCard QPushButton:hover {{
                border: 1px solid {accent};
            }}
            QFrame#studyZoneCard QLineEdit {{
                background-color: {inner_group_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 5px 12px;
            }}
            QPushButton[contentRoundedButton="true"] {{
                background-color: {surface_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 18px;
                padding: 8px 16px;
                min-height: 36px;
                font-weight: 500;
                outline: none;
            }}
            QPushButton[contentRoundedButton="true"]:hover,
            QPushButton[contentRoundedButton="true"]:focus {{
                border: 1px solid {accent};
                border-radius: 18px;
                outline: none;
            }}
            QPushButton[contentRoundedButton="true"]:pressed {{
                background-color: {border};
                border-radius: 18px;
            }}
            QPushButton[contentRoundedButton="true"]:disabled {{
                color: {muted};
                border-radius: 18px;
            }}
            QLineEdit[contentRoundedInput="true"],
            QSpinBox[contentRoundedInput="true"],
            QComboBox[contentRoundedInput="true"] {{
                background-color: {inner_group_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 16px;
                padding: 5px 12px;
            }}
            QLineEdit[contentRoundedInput="true"]:focus,
            QSpinBox[contentRoundedInput="true"]:focus,
            QComboBox[contentRoundedInput="true"]:focus {{
                border: 1px solid {accent};
                border-radius: 16px;
                outline: none;
            }}
            QLabel#studyZoneCardTitle {{
                color: {fg};
                background: transparent;
                font-size: 15px;
                font-weight: 500;
            }}
            QLabel#studyZoneCardDescription {{
                color: {muted};
                background: transparent;
                font-size: 12px;
            }}
            QWidget#studyZoneMessageListEditor,
            QWidget#studyZoneMessageRows {{
                background: transparent;
                border: none;
            }}
            /* Message rows are fully pill-shaped, and every pseudo-state
               restates the radius so the corners never snap back to square
               on hover/focus/disabled. */
            QFrame#studyZoneMessageRow {{
                background-color: {surface_bg};
                border: 1px solid {border};
                border-radius: 25px;
            }}
            QFrame#studyZoneMessageRow:hover {{
                border: 1px solid {border};
                border-radius: 25px;
            }}
            /* Scoped twin for the same specificity reason as the icon buttons:
               `QFrame#studyZoneCard QLineEdit` would otherwise impose its own
               12px radius on the message inputs. */
            QFrame#studyZoneCard QLineEdit#studyZoneMessageInput,
            QLineEdit#studyZoneMessageInput {{
                background-color: {inner_group_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 17px;
                padding: 6px 14px;
                min-height: 22px;
                selection-background-color: {accent};
                font-size: 13px;
            }}
            QFrame#studyZoneCard QLineEdit#studyZoneMessageInput:focus,
            QLineEdit#studyZoneMessageInput:focus {{
                border: 1px solid {accent};
                border-radius: 17px;
                padding: 6px 14px;
            }}
            QFrame#studyZoneCard QLineEdit#studyZoneMessageInput:hover,
            QLineEdit#studyZoneMessageInput:hover {{
                border-radius: 17px;
                padding: 6px 14px;
            }}
            QWidget#studyZonePinInput {{
                background: transparent;
                border: none;
            }}
            QLineEdit#studyZonePinDigit {{
                background-color: {surface_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 9px;
                padding: 0px;
                selection-background-color: {accent};
            }}
            QLineEdit#studyZonePinDigit:focus {{
                border-color: {accent};
            }}
            /* Circular icon buttons (34px box, 17px radius) in every state.
               Each selector is repeated in a `QFrame#studyZoneCard ...` form:
               Qt ranks `QFrame#studyZoneCard QPushButton` (1 id + 2 type names)
               ABOVE a plain `QPushButton#studyZoneMessageIconButton` (1 id +
               1 type name), so without the scoped twin the card's generic
               `padding: 8px 16px` won on a 34px-wide button, collapsed the
               content box and made Qt drop the rounded corners. Only the
               disabled state escaped, which is why the buttons rendered round
               when greyed out and square when active. `padding` is restated in
               every state for the same reason. */
            QFrame#studyZoneCard QPushButton#studyZoneMessageIconButton,
            QPushButton#studyZoneMessageIconButton {{
                background-color: {inner_group_bg};
                color: {muted};
                border: 1px solid {border};
                border-radius: 17px;
                padding: 0px;
                min-height: 0px;
                min-width: 0px;
            }}
            QFrame#studyZoneCard QPushButton#studyZoneMessageIconButton:hover,
            QPushButton#studyZoneMessageIconButton:hover {{
                background-color: {hover_bg};
                color: {fg};
                border: 1px solid {accent};
                border-radius: 17px;
                padding: 0px;
            }}
            QFrame#studyZoneCard QPushButton#studyZoneMessageIconButton:pressed,
            QPushButton#studyZoneMessageIconButton:pressed {{
                background-color: {border};
                border-radius: 17px;
                padding: 0px;
            }}
            QFrame#studyZoneCard QPushButton#studyZoneMessageIconButton:disabled,
            QPushButton#studyZoneMessageIconButton:disabled {{
                background-color: {inner_group_bg};
                color: {border};
                border: 1px solid {border};
                border-radius: 17px;
                padding: 0px;
            }}
            QFrame#studyZoneCard QPushButton#studyZoneAddMessageButton,
            QPushButton#studyZoneAddMessageButton {{
                background-color: {surface_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 18px;
                padding: 8px 16px;
                min-height: 36px;
                font-size: 13px;
                font-weight: 500;
            }}
            QFrame#studyZoneCard QPushButton#studyZoneAddMessageButton:hover,
            QPushButton#studyZoneAddMessageButton:hover {{
                border: 1px solid {accent};
                border-radius: 18px;
            }}
            QFrame#studyZoneCard QPushButton#studyZoneAddMessageButton:pressed,
            QPushButton#studyZoneAddMessageButton:pressed {{
                background-color: {border};
                border-radius: 18px;
            }}
            QSpinBox#studyZoneSpinBox {{
                background-color: {surface_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 14px;
                padding: 5px 34px 5px 12px;
                min-height: 28px;
                min-width: 126px;
            }}
            QSpinBox#studyZoneSpinBox:focus {{
                border: 1px solid {accent};
            }}
            QSpinBox#studyZoneSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 28px;
                height: 16px;
                right: 5px;
                top: 2px;
                border: none;
                background: transparent;
            }}
            QSpinBox#studyZoneSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 28px;
                height: 16px;
                right: 5px;
                bottom: 2px;
                border: none;
                background: transparent;
            }}
            QSpinBox#studyZoneSpinBox::up-arrow {{
                width: 16px;
                height: 16px;
                image: url("{study_zone_spinbox_up_icon}");
            }}
            QSpinBox#studyZoneSpinBox::down-arrow {{
                width: 16px;
                height: 16px;
                image: url("{study_zone_spinbox_down_icon}");
            }}
            
            /* Shared "label left, controls right" row used by every card. */
            QFrame#settingRow {{
                background-color: {surface_bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QFrame#settingRow QLabel {{
                background: transparent;
                font-size: 13px;
            }}
            /* Explicit disabled colours: the blanket `QLabel {{ color: fg }}`
               rule below beats Qt's disabled palette, so a row switched off with
               setEnabled(False) would otherwise look fully active. */
            QFrame#settingRow QLabel:disabled {{
                color: {muted};
            }}
            QFrame#settingRow QLineEdit:disabled {{
                color: {muted};
                border: 1px solid {border};
            }}

            QWidget#innerGroup {{ background-color: {inner_group_bg}; border: 1px solid {border}; border-radius: 24px; }}
            
            /* General QPushButton fallback (for content area buttons only).
               Every content button shares this one geometry — radius 18,
               36px tall, 8/16 padding — so no button ever reads as a
               different shape from its neighbours. */
            QPushButton {{
                background-color: {surface_bg};
                color: {fg};
                border: 1px solid {border};
                padding: 8px 16px;
                min-height: 36px;
                border-radius: 18px;
            }}
            QPushButton:pressed {{ background-color: {border}; }}

            /* Danger buttons differ only in colour, never in shape. */
            QPushButton#dangerButton {{
                background-color: {surface_bg};
                color: #ff6b6b;
                font-weight: 500;
                border: 1px solid #ff6b6b;
                border-radius: 18px;
                padding: 8px 16px;
                min-height: 36px;
            }}
            QPushButton#dangerButton:hover {{ background-color: #ff6b6b; color: white; border-radius: 18px; }}
            QPushButton#dangerButton:pressed {{ background-color: #e85c5c; color: white; border-radius: 18px; }}
            
            QComboBox {{ background-color: {inner_group_bg}; color: {fg}; border: 1px solid {border}; border-radius: 12px; padding: 5px 12px; }}
            QComboBox QAbstractItemView {{ background-color: {inner_group_bg}; color: {fg}; selection-background-color: {border}; }}
            
            QPushButton#difficultyCard {{
                background-color: {inner_group_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 16px;
                padding: 15px;
                text-align: left;
            }}
            QPushButton#difficultyCard:hover {{
                border: 1px solid {hover_bg};
                background-color: {hover_bg};
            }}
            QPushButton#difficultyCard:checked {{
                border: 2px solid {self.accent_color};
                background-color: {inner_group_bg};
            }}

            QWidget#onigimonCompanionGrid {{
                background-color: transparent;
            }}
            QPushButton#onigimonCompanionTile {{
                background-color: {surface_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 4px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton#onigimonCompanionTile:hover {{
                border: 1px solid #F2B705;
                background-color: {hover_bg};
            }}
            QPushButton#onigimonCompanionTile:checked {{
                border: 2px solid #F2B705;
                background-color: rgba(242, 183, 5, 0.18);
            }}
            QPushButton#onigimonSceneButton {{
                background-color: {surface_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 18px;
                padding: 8px 16px;
                min-height: 36px;
                font-weight: 500;
            }}
            QPushButton#onigimonSceneButton:hover {{
                border: 1px solid #F2B705;
                background-color: {hover_bg};
                border-radius: 18px;
            }}
            QPushButton#onigimonSceneButton:pressed {{
                background-color: {border};
                border-radius: 18px;
            }}
            QLabel#onigimonSceneBlurValue {{
                color: {fg};
                min-width: 42px;
            }}

            QPushButton#notificationPositionButton {{
                background-color: {surface_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 18px;
                font-size: 20px;
                padding: 0;
                min-height: 0px;
            }}
            QPushButton#notificationPositionButton:hover {{
                background-color: {hover_bg};
                border-radius: 18px;
            }}
            QPushButton#notificationPositionButton:checked {{
                background-color: {notification_checked_bg};
                color: {fg};
                border: 1px solid {accent};
                border-radius: 18px;
            }}
            QWidget#notificationPositionPreview {{
                border: 2px solid {border};
                border-radius: 20px;
                background-color: transparent;
            }}
            QLabel#notificationPositionPreviewRect {{
                background-color: {accent};
                border-radius: 8px;
            }}
            
            QLabel, QRadioButton {{ color: {fg}; }}
            QLineEdit, QSpinBox {{ background-color: {inner_group_bg}; color: {fg}; border: 1px solid {border}; border-radius: 12px; padding: 5px 12px; }}
            QSpinBox#notificationDurationSpinBox {{
                min-height: 44px;
                min-width: 148px;
                padding: 5px 36px 5px 14px;
                font-size: 16px;
            }}
            QSpinBox#notificationDurationSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 30px;
                height: 22px;
                right: 6px;
                top: 3px;
                border: none;
                background: transparent;
            }}
            QSpinBox#notificationDurationSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 30px;
                height: 22px;
                right: 6px;
                bottom: 3px;
                border: none;
                background: transparent;
            }}
            QSpinBox#notificationDurationSpinBox::up-arrow {{
                width: 18px;
                height: 18px;
                image: url("{notification_spinbox_up_icon}");
            }}
            QSpinBox#notificationDurationSpinBox::down-arrow {{
                width: 18px;
                height: 18px;
                image: url("{notification_spinbox_down_icon}");
            }}
            QScrollBar:vertical {{ border: none; background: transparent; width: 8px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {border}; min-height: 20px; border-radius: 8px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                height: 0px; background: none; border: none;
            }}
            /* Horizontal twin, for the rare window too narrow for a page. */
            QScrollBar:horizontal {{ border: none; background: transparent; height: 8px; margin: 0; }}
            QScrollBar::handle:horizontal {{ background: {border}; min-width: 20px; border-radius: 8px; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                width: 0px; background: none; border: none;
            }}
        """)
        self._prepare_content_controls(self.content_stack)

_gamification_dialog = None

def open_gamification_settings(page_name=None):
    global _gamification_dialog
    if _gamification_dialog is not None:
        _gamification_dialog.close()
    
    addon_path = os.path.dirname(__file__)
    _gamification_dialog = GamificationSettingsDialog(
        parent=mw,
        addon_path=addon_path
    )
    _gamification_dialog.show()
    _gamification_dialog.raise_()
    _gamification_dialog.activateWindow()
    if page_name:
        _gamification_dialog.navigate_to_page(page_name)
