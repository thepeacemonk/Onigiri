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
    QFileDialog, QSlider
)
from PyQt6.QtCore import pyqtSignal, pyqtProperty, QEvent, QTimer
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene
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
                level_font.setBold(True)
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
        self.name_label.setStyleSheet("font-weight: bold; font-size: 14px; color: white; background: transparent;")

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

class SectionGroup(QWidget):
    def __init__(self, title="", parent=None, border=True, description=""):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(0, 5, 0, 0)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 20px; margin-bottom: 5px;")
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
        button.setFixedSize(30, 30)
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
        row_layout.setContentsMargins(10, 8, 8, 8)
        row_layout.setSpacing(8)

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
            box.setFixedSize(34, 38)
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
    def __init__(self, title, description, emoji):
        super().__init__()
        self.setCheckable(True)
        self.setObjectName("difficultyCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(100)
        self.setMinimumWidth(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        self.icon_label = QLabel(emoji)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.icon_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: inherit;
                border-radius: 20px;
                font-size: 24px;
                min-width: 40px;
                max-width: 40px;
                min-height: 40px;
                max-height: 40px;
            }
        """)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        self.title_label = QLabel(title)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; background: transparent;")
        
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
        self.addon_path = addon_path
        self.current_config = config.get_config()
        self.setWindowTitle(tr("gamification_settings_title"))
        self._loaded_pages = set()
        self._is_saving = False

        # --- Screen Proportional Sizing ---
        screen = mw.app.primaryScreen()
        if screen:
            self.resize(int(screen.availableGeometry().width() * 0.45), 
                        int(screen.availableGeometry().height() * 0.55))
        else:
            self.resize(800, 600)

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
        content_outer_layout.setContentsMargins(8, 10, 8, 10)
        content_outer_layout.setSpacing(0)
        content_outer_layout.addWidget(content_container)

        content_area_layout.addWidget(sidebar_wrapper)
        content_area_layout.addWidget(content_outer)

        main_layout.addLayout(content_area_layout)
        self.apply_stylesheet()

        # Default page
        self.navigate_to_page("General")

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
                        font-weight: 600;
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

        # Onigimon
        self.onigimon_config = self.current_config.get("onigimon", {})
        if not isinstance(self.onigimon_config, dict):
            self.onigimon_config = {}
        self.onigimon_toggle = AnimatedToggleButton(accent_color="#F2B705")
        self.onigimon_toggle.setChecked(bool(self.onigimon_config.get("enabled", False)))
        self.onigimon_notifications_toggle = AnimatedToggleButton(accent_color="#F2B705")
        self.onigimon_notifications_toggle.setChecked(bool(self.onigimon_config.get("notifications_enabled", True)))
        self.onigimon_daily_toggle = AnimatedToggleButton(accent_color="#F2B705")
        self.onigimon_daily_toggle.setChecked(bool(self.onigimon_config.get("daily_surprise_enabled", True)))
        self.onigimon_ankimon_updates_toggle = AnimatedToggleButton(accent_color="#F2B705")
        self.onigimon_ankimon_updates_toggle.setChecked(bool(self.onigimon_config.get("allow_ankimon_updates", True)))
        self.onigimon_reward_interval_spinbox = QSpinBox()
        self.onigimon_reward_interval_spinbox.setRange(1, 50)
        self.onigimon_reward_interval_spinbox.setSuffix(" correct cards")
        self.onigimon_reward_interval_spinbox.setValue(int(self.onigimon_config.get("reward_interval", 4) or 4))
        self.onigimon_difficulty_group = QButtonGroup()
        self.onigimon_difficulty_group.setExclusive(True)
        self.onigimon_difficulty_widgets = {}
        def _get_sprite(name):
            path = os.path.join(os.path.dirname(__file__), "system_files", "gamification_images", "onigimon", name)
            url = QUrl.fromLocalFile(path).toString()
            return f'<img src="{url}" width="32" height="32">'

        onigimon_difficulties = [
            ("bulbassaur", "Bulbassaur", "More frequent rewards with softer miss penalties and missed-day decay.", _get_sprite("bulbasaur_pixel.png")),
            ("pikachu", "Pikachu", "Balanced rewards, miss penalties, and care pacing.", _get_sprite("pikachu_pixel.png")),
            ("charizard", "Charizard", "Slower rewards with stronger miss penalties and missed-day decay.", _get_sprite("charizard_pixel.png")),
        ]
        for data, title, description, badge in onigimon_difficulties:
            btn = DifficultyCardWidget(title, description, badge)
            self.onigimon_difficulty_group.addButton(btn)
            self.onigimon_difficulty_widgets[data] = btn
        current_onigimon_difficulty = str(self.onigimon_config.get("difficulty", "pikachu") or "pikachu").lower()
        if current_onigimon_difficulty not in self.onigimon_difficulty_widgets:
            current_onigimon_difficulty = "pikachu"
        self.onigimon_difficulty_widgets[current_onigimon_difficulty].setChecked(True)
        self.onigimon_widget_style_combo = QComboBox()
        self.onigimon_widget_style_combo.addItems(["compact", "care", "detailed"])
        current_style = str(self.onigimon_config.get("widget_style", "care"))
        self.onigimon_widget_style_combo.setCurrentText(current_style if current_style in {"compact", "care", "detailed"} else "care")
        self.onigimon_sprite_motion_combo = QComboBox()
        self.onigimon_sprite_motion_combo.addItem("Static sprites", "static")
        self.onigimon_sprite_motion_combo.addItem("GIF sprites", "gif")
        current_motion = str(self.onigimon_config.get("sprite_motion", "static"))
        self.onigimon_sprite_motion_combo.setCurrentIndex(1 if current_motion == "gif" else 0)
        self.onigimon_scene_color = str(self.onigimon_config.get("scene_background_color", "#e8f4ff") or "#e8f4ff")
        if not re.match(r"^#[0-9a-fA-F]{6}$", self.onigimon_scene_color):
            self.onigimon_scene_color = "#e8f4ff"
        self.onigimon_scene_image = str(self.onigimon_config.get("scene_background_image", "") or "")
        self.onigimon_scene_color_button = QPushButton("Scene color")
        self.onigimon_scene_color_button.setObjectName("onigimonSceneButton")
        self.onigimon_scene_color_button.clicked.connect(self._choose_onigimon_scene_color)
        self.onigimon_scene_import_button = QPushButton("Import image")
        self.onigimon_scene_import_button.setObjectName("onigimonSceneButton")
        self.onigimon_scene_import_button.clicked.connect(self._import_onigimon_scene_background)
        self.onigimon_scene_clear_button = QPushButton("Clear image")
        self.onigimon_scene_clear_button.setObjectName("onigimonSceneButton")
        self.onigimon_scene_clear_button.clicked.connect(self._clear_onigimon_scene_background)
        blur_value = int(self.onigimon_config.get("scene_background_blur", 9) or 0)
        self.onigimon_scene_blur_slider = QSlider(Qt.Orientation.Horizontal)
        self.onigimon_scene_blur_slider.setObjectName("onigimonSceneSlider")
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
        self.onigimon_scene_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.onigimon_scene_opacity_slider.setObjectName("onigimonSceneSlider")
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
        self.onigimon_name_input.setPlaceholderText("Nickname")
        self.onigimon_companion_buttons = QButtonGroup(self)
        self.onigimon_companion_buttons.setExclusive(True)
        self.onigimon_companion_grid = QWidget()
        self.onigimon_companion_grid.setObjectName("onigimonCompanionGrid")
        self.onigimon_companion_grid_layout = QGridLayout(self.onigimon_companion_grid)
        self.onigimon_companion_grid_layout.setContentsMargins(8, 8, 8, 8)
        self.onigimon_companion_grid_layout.setSpacing(8)
        self.onigimon_companion_status_label = QLabel("Open this page to load Ankimon companions.")
        self.onigimon_companion_status_label.setWordWrap(True)
        
        # Difficulty Setting
        self.restaurant_difficulty_group = QButtonGroup()
        self.restaurant_difficulty_group.setExclusive(True)
        
        self.difficulty_widgets = {}
        diffs = [
            ("Apprendice", tr("apprentice") + " (1x)", tr("apprentice_desc"), "Apprendice", "🧑‍🍳"),
            ("Cook", tr("cook") + " (2x)", tr("cook_desc"), "Cook", "🍳"),
            ("Chef", tr("chef") + " (4x)", tr("chef_desc"), "Chef", "🔪")
        ]
        
        for name, title, description, data, emoji in diffs:
            btn = DifficultyCardWidget(title, description, emoji)
            
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

        # Focus Dango
        focus_dango_conf = self.achievements_config.get("focusDango", {})
        self.focus_dango_toggle = AnimatedToggleButton(accent_color="#9D3D64")
        self.focus_dango_toggle.setChecked(bool(focus_dango_conf.get("enabled", False)))
        self.focus_dango_self_sabotage_toggle = AnimatedToggleButton(accent_color="#9D3D64")
        self.focus_dango_self_sabotage_toggle.setChecked(bool(focus_dango_conf.get("self_sabotage", False)))
        dango_pin = "".join(ch for ch in str(focus_dango_conf.get("unlock_pin", "000000") or "") if ch.isdigit())
        if len(dango_pin) != 6:
            dango_pin = "000000"
        self.focus_dango_pin_input = StudyZonePinInput(dango_pin, self)
        
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
        self.hexagon_widget_display_combo = QComboBox()
        self.hexagon_widget_display_combo.addItem("Land + information", "land_info")
        self.hexagon_widget_display_combo.addItem("Land only", "land_only")
        current_display = str(self.hexagon_land_config.get("widget_display", "land_info") or "land_info")
        display_index = self.hexagon_widget_display_combo.findData(current_display)
        self.hexagon_widget_display_combo.setCurrentIndex(display_index if display_index >= 0 else 0)

        self.hexagon_survival_toggle = AnimatedToggleButton(accent_color="#e53e3e")
        self.hexagon_survival_toggle.setChecked(bool(self.hexagon_land_config.get("survival_mode", False)))

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
                font-weight: 600;
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
                    font-weight: bold;
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
        t_label.setStyleSheet(f"font-weight: bold; font-size: 24px; color: {text_color}; background: transparent;")
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

    def create_notification_position_section(self):
        section = SectionGroup(tr("reviewer_notification_pos_title"), self)

        container = QWidget()
        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(8, 8, 8, 8)
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

        section.add_widget(container)
        return section

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

    def create_notification_duration_section(self):
        section = SectionGroup("Notification Display Time", self)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 8, 8, 8)
        row_layout.setSpacing(12)
        row_layout.addWidget(QLabel("Show notifications for"))
        row_layout.addStretch()
        row_layout.addWidget(self.notification_duration_spinbox)
        section.add_widget(row)
        return section

    # --- PAGES ---

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

        layout.addWidget(self.create_notification_position_section())
        layout.addWidget(self.create_notification_duration_section())
        
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
        
        layout.addStretch()
        
        return page

    def create_nook_level_page(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(16)
        nook_level = _nook_level_module()
        
        hero = self._create_study_zone_header(
            tr("restaurant_level"),
            tr("grow_restaurant_desc"),
            "nook.png",
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
        
        # Level Chip Appearance
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
                border-radius: 14px;
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
                padding: 6px 16px;
                font-weight: 600;
                font-size: 12px;
                color: #888888;
                border-radius: 10px;
            }}
            QPushButton#dynamicThemeButton:hover  {{ color: #aaaaaa; }}
            QPushButton#dynamicThemeButton:checked {{
                background-color: {self.accent_color};
                color: white;
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
        dynamic_row.addStretch()
        dynamic_row.addWidget(self.rl_dynamic_chip_theme_widget)
        chip_layout.addLayout(dynamic_row)

        chip_layout.addWidget(self._create_restaurant_chip_bg_control(tr("level_chip_bg_color"), self.rl_chip_bg_button))
        chip_layout.addWidget(self._create_restaurant_chip_color_card(tr("level_chip_progress_color"), self.rl_chip_progress_button))
        chip_layout.addWidget(self._create_restaurant_chip_color_card(tr("level_chip_text_color"), self.rl_chip_text_button))

        reset_row = QHBoxLayout()
        reset_row.addWidget(self.rl_chip_reset_colors_button)
        reset_row.addStretch()
        chip_layout.addLayout(reset_row)
        layout.addWidget(chip_group)
        self._update_restaurant_chip_preview()

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
            "from the Apps Script for today - today's card progress is kept.",
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
        self.onigimon_companion_status_label.setText("Loading Ankimon companions...")
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
            self.onigimon_companion_status_label.setText("Ankimon is not installed.")
            return
        if status == "starter_needed":
            self.onigimon_companion_status_label.setText("Choose your first Ankimon Pokémon first.")
            return
        if status == "no_collection":
            self.onigimon_companion_status_label.setText("No Pokémon in Ankimon Collection PC yet.")
            return
        if not companions:
            self.onigimon_companion_status_label.setText("No Ankimon Pokémon found.")
            return

        self.onigimon_companion_status_label.setText("The active Pokémon in Ankimon's PC is your Onigimon companion. Picking a tile here also makes it active in Ankimon.")
        columns = 4
        for index, pokemon in enumerate(companions):
            ankimon_id = str(pokemon.get("ankimon_id", ""))
            label = f"{pokemon.get('name', 'Pokemon')} · Lv. {pokemon.get('level', 1)}"
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
        color = self.onigimon_scene_color if re.match(r"^#[0-9a-fA-F]{6}$", self.onigimon_scene_color) else "#e8f4ff"
        self.onigimon_scene_color_button.setStyleSheet(
            f"QPushButton#onigimonSceneButton {{ background-color: {color}; color: #111111; border: 1px solid rgba(0,0,0,0.18); border-radius: 15px; padding: 4px 14px; min-height: 28px; }}"
        )

        if hasattr(self, "onigimon_scene_preview"):
            self.onigimon_scene_preview.setStyleSheet(
                "QFrame#onigimonScenePreview {"
                "border: 1px solid rgba(120,120,120,0.42);"
                "border-radius: 14px;"
                f"background-color: {color};"
                "}"
            )
            self._update_onigimon_scene_preview_background()
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
                self.onigimon_scene_preview_sprite.setPixmap(
                    self._scaled_for_display(pixmap, 74, 74)
                )
                self.onigimon_scene_preview_sprite.setText("")
            else:
                self.onigimon_scene_preview_sprite.setPixmap(QPixmap())
                self.onigimon_scene_preview_sprite.setText("Onigimon")

    def _choose_onigimon_scene_color(self):
        chosen, ok = OnigiriColorDialog.getColor(self.onigimon_scene_color, self)
        if ok:
            self.onigimon_scene_color = chosen
            self._update_onigimon_scene_controls()

    def _import_onigimon_scene_background(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Onigimon background",
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
        icon_path = os.path.join(self.addon_path, "system_files", "gamification_images", "pokemon_pikachu.png")
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
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white; background: transparent;")
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
            "Use Ankimon's Pokemon PC to choose the active Pokemon, then feed, clean, train, and play while Onigimon updates Ankimon.",
            "pokemon_pikachu.png",
            "#F2B705",
            self.onigimon_toggle
        ))

        companion_group, companion_layout = self._create_study_zone_card("Companion")
        companion_layout.addWidget(self.onigimon_companion_status_label)
        companion_layout.addWidget(QLabel("Companion nickname"))
        companion_layout.addWidget(self.onigimon_name_input)
        tile_scroll = QScrollArea()
        tile_scroll.setWidgetResizable(True)
        tile_scroll.setMinimumHeight(92)
        tile_scroll.setMaximumHeight(170)
        tile_scroll.setFrameShape(QFrame.Shape.NoFrame)
        tile_scroll.setStyleSheet("background: transparent;")
        tile_scroll.setWidget(self.onigimon_companion_grid)
        companion_layout.addWidget(tile_scroll)
        refresh_btn = QPushButton("Refresh Ankimon PC")
        refresh_btn.clicked.connect(self._populate_onigimon_companion_combo)
        companion_layout.addWidget(refresh_btn)
        starter_note = QLabel("Changing the active Pokémon in Ankimon's PC changes the Onigimon companion automatically.")
        starter_note.setWordWrap(True)
        starter_note.setMinimumWidth(0)
        companion_layout.addWidget(starter_note)
        layout.addWidget(companion_group)

        scene_group, scene_layout = self._create_study_zone_card("Scene")
        self.onigimon_scene_preview = QFrame()
        self.onigimon_scene_preview.setObjectName("onigimonScenePreview")
        self.onigimon_scene_preview.setMinimumHeight(128)
        self.onigimon_scene_preview.installEventFilter(self)
        self.onigimon_scene_preview_bg = QLabel(self.onigimon_scene_preview)
        self.onigimon_scene_preview_bg.setObjectName("onigimonScenePreviewBackground")
        self.onigimon_scene_preview_bg.setScaledContents(False)
        self.onigimon_scene_preview_bg.lower()
        preview_layout = QVBoxLayout(self.onigimon_scene_preview)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.addStretch()
        self.onigimon_scene_preview_sprite = QLabel()
        self.onigimon_scene_preview_sprite.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.onigimon_scene_preview_sprite.setFixedHeight(82)
        self.onigimon_scene_preview_sprite.setStyleSheet("font-weight: 700; background: transparent; color: rgba(0,0,0,0.58);")
        preview_layout.addWidget(self.onigimon_scene_preview_sprite)
        preview_layout.addStretch()
        scene_layout.addWidget(self.onigimon_scene_preview)
        image_row = QHBoxLayout()
        image_row.addWidget(self.onigimon_scene_import_button)
        image_row.addWidget(self.onigimon_scene_clear_button)
        image_row.addStretch()
        scene_layout.addLayout(image_row)
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Background color"))
        color_row.addWidget(self.onigimon_scene_color_button)
        color_row.addStretch()
        scene_layout.addLayout(color_row)
        blur_row = QHBoxLayout()
        blur_row.addWidget(QLabel("Blur intensity"))
        blur_row.addWidget(self.onigimon_scene_blur_slider, 1)
        blur_row.addWidget(self.onigimon_scene_blur_value_label)
        blur_row.addStretch()
        scene_layout.addLayout(blur_row)
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Background opacity"))
        opacity_row.addWidget(self.onigimon_scene_opacity_slider, 1)
        opacity_row.addWidget(self.onigimon_scene_opacity_value_label)
        opacity_row.addStretch()
        scene_layout.addLayout(opacity_row)
        self._update_onigimon_scene_controls()
        layout.addWidget(scene_group)

        rewards_group, rewards_layout = self._create_study_zone_card("Rewards")
        rewards_layout.addWidget(self._create_toggle_row(self.onigimon_notifications_toggle, "Show Onigimon notifications"))
        rewards_layout.addWidget(self._create_toggle_row(self.onigimon_daily_toggle, "Daily surprise item"))
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Reward item every"))
        interval_row.addWidget(self.onigimon_reward_interval_spinbox)
        interval_row.addStretch()
        rewards_layout.addLayout(interval_row)
        layout.addWidget(rewards_group)

        difficulty_group, difficulty_layout = self._create_study_zone_card("Difficulty")
        difficulty_note = QLabel("Difficulty changes how often correct-answer rewards appear, how much mistakes hurt, and how much care stats drop after missed study days.")
        difficulty_note.setWordWrap(True)
        difficulty_layout.addWidget(difficulty_note)
        difficulty_cards = QVBoxLayout()
        difficulty_cards.setSpacing(10)
        for data in ("bulbassaur", "pikachu", "charizard"):
            difficulty_cards.addWidget(self.onigimon_difficulty_widgets[data])
        difficulty_layout.addLayout(difficulty_cards)
        layout.addWidget(difficulty_group)

        widget_group, widget_layout = self._create_study_zone_card("Widget")
        widget_row = QHBoxLayout()
        widget_row.addWidget(QLabel("Widget style"))
        widget_row.addWidget(self.onigimon_widget_style_combo)
        widget_row.addStretch()
        widget_layout.addLayout(widget_row)
        sprite_row = QHBoxLayout()
        sprite_row.addWidget(QLabel("Sprite mode"))
        sprite_row.addWidget(self.onigimon_sprite_motion_combo)
        sprite_row.addStretch()
        widget_layout.addLayout(sprite_row)
        layout.addWidget(widget_group)

        bridge_group, bridge_layout = self._create_study_zone_card("Ankimon Bridge")
        bridge_layout.addWidget(self._create_toggle_row(self.onigimon_ankimon_updates_toggle, "Allow Onigimon items to update Ankimon data"))
        bridge_note = QLabel("Onigimon reads Ankimon's database and writes care rewards back to the active Pokémon's HP, Attack, Defense, and XP.")
        bridge_note.setWordWrap(True)
        bridge_layout.addWidget(bridge_note)
        layout.addWidget(bridge_group)

        credits_group, credits_layout = self._create_study_zone_card("Sprite Credits")
        credit = QLabel("PokéSprite sprite images are © Nintendo/Creatures Inc./GAME FREAK Inc. PokéSprite project code/data by msikma, MIT licensed.")
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
            "dango.png",
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

        pin_row = QHBoxLayout()
        pin_row.setContentsMargins(0, 0, 0, 0)
        pin_row.setSpacing(12)

        pin_text = QWidget()
        pin_text_layout = QVBoxLayout(pin_text)
        pin_text_layout.setContentsMargins(0, 0, 0, 0)
        pin_text_layout.setSpacing(4)

        pin_title = QLabel(tr("focus_dango_pin", "Unlock PIN"))
        pin_title.setObjectName("studyZoneCardTitle")
        pin_title.setStyleSheet("font-size: 13px;")
        pin_desc = QLabel(tr(
            "focus_dango_pin_desc",
            "Six digits required to leave Focus Dango while Self-Sabotage Mode is active."
        ))
        pin_desc.setObjectName("studyZoneCardDescription")
        pin_desc.setWordWrap(True)
        pin_text_layout.addWidget(pin_title)
        pin_text_layout.addWidget(pin_desc)

        pin_row.addWidget(pin_text, 1)
        pin_row.addWidget(self.focus_dango_pin_input, 0, Qt.AlignmentFlag.AlignVCenter)
        mode_layout.addLayout(pin_row)
        layout.addWidget(mode_card)

        layout.addStretch()
        return page

    def create_mochi_messages_page(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(16)
        header = self._create_study_zone_header(
            tr("mochi_messages_title"),
            tr("mochi_cheer_on"),
            "mochi_messenger.png",
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

        layout.addWidget(self._create_study_zone_message_card(
            tr("mochi_messages_title"),
            tr("message_editor_desc", "Create one message per card. Add, reorder, or remove them without worrying about line breaks."),
            self.mochi_messages_editor,
            "#00935C"
        ))

        layout.addStretch()
        return page

    def create_hexagon_land_page(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(16)
        hexagon_land = _hexagon_land_module()

        layout.addWidget(self._create_study_zone_header(
            "Hexagon Land",
            "Build an island while you study: earn Hex Coins and materials, expand tile by tile, grow trees, invite inhabitants, and raise castles.",
            "Hexagon_world.png",
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

        keys_group, keys_layout = self._create_study_zone_card("Keys of the Island")
        keys_note = QLabel(f"Buy the Keys of the Island for {hexagon_land.KEYS_OF_THE_ISLAND_COST} Hex Coins to name your island.")
        keys_note.setWordWrap(True)
        keys_layout.addWidget(keys_note)

        self.hexagon_keys_status_label = QLabel()
        self.hexagon_keys_status_label.setWordWrap(True)
        keys_layout.addWidget(self.hexagon_keys_status_label)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Island name"))
        self.hexagon_island_name_input = QLineEdit()
        self.hexagon_island_name_input.setMaxLength(40)
        name_row.addWidget(self.hexagon_island_name_input, 1)
        self.hexagon_island_name_save_btn = QPushButton("Save Name")
        self.hexagon_island_name_save_btn.clicked.connect(self._save_hexagon_island_name)
        name_row.addWidget(self.hexagon_island_name_save_btn)
        keys_layout.addLayout(name_row)

        self.hexagon_keys_button = QPushButton("Buy Keys of the Island")
        self.hexagon_keys_button.clicked.connect(self._buy_hexagon_keys)
        keys_layout.addWidget(self.hexagon_keys_button)
        layout.addWidget(keys_group)

        widget_group, widget_layout = self._create_study_zone_card("Widget")
        display_row = QHBoxLayout()
        display_row.addWidget(QLabel("Display"))
        display_row.addWidget(self.hexagon_widget_display_combo)
        display_row.addStretch()
        widget_layout.addLayout(display_row)
        layout.addWidget(widget_group)

        survival_group, survival_layout = self._create_study_zone_card("Survival Mode")
        survival_desc = QLabel("If enabled, the larger your streak, the more land tiles you will lose if you miss a study day.")
        survival_desc.setWordWrap(True)
        survival_desc.setStyleSheet("color: #888;")
        survival_layout.addWidget(survival_desc)
        survival_row = QHBoxLayout()
        survival_row.addWidget(QLabel("Survival Mode"))
        survival_row.addStretch()
        survival_row.addWidget(self.hexagon_survival_toggle)
        survival_layout.addLayout(survival_row)
        layout.addWidget(survival_group)

        self._refresh_hexagon_island_controls()

        layout.addStretch()
        return page

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
        if owns_keys:
            self.hexagon_keys_status_label.setText("Keys owned. Your island name appears on the Hexagon Land widget.")
        else:
            self.hexagon_keys_status_label.setText("Current balance: ∞ Hex Coins.")

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
                "Pick a fresh Nook Rush from the Apps Script for the currently equipped Nook, "
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
                font-weight: 700;
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
        opacity_label.setStyleSheet(f"color: {tokens['fg']}; font-size: 13px; font-weight: 700;")

        slider_track = tokens["surface"]
        slider_border = tokens["border"]
        self.rl_chip_bg_opacity_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.rl_chip_bg_opacity_slider.setRange(0, 100)
        self.rl_chip_bg_opacity_value_label = QLabel("100%")
        self.rl_chip_bg_opacity_value_label.setFixedWidth(48)
        self.rl_chip_bg_opacity_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.rl_chip_bg_opacity_value_label.setStyleSheet(f"color: {tokens['fg']}; font-size: 13px; font-weight: 700;")

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
                font-weight: 700;
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
        
        selected_diff = "Apprendice"
        for data, btn in self.difficulty_widgets.items():
            if btn.isChecked():
                selected_diff = data
                break
        res_conf["difficulty"] = selected_diff
        
        if "Nook Level" in self._loaded_pages:
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
        oni_conf["notifications_enabled"] = self.onigimon_notifications_toggle.isChecked()
        oni_conf["daily_surprise_enabled"] = self.onigimon_daily_toggle.isChecked()
        oni_conf["allow_ankimon_updates"] = self.onigimon_ankimon_updates_toggle.isChecked()
        selected_onigimon_difficulty = "pikachu"
        for data, btn in self.onigimon_difficulty_widgets.items():
            if btn.isChecked():
                selected_onigimon_difficulty = data
                break
        oni_conf["difficulty"] = selected_onigimon_difficulty
        oni_conf["reward_interval"] = self.onigimon_reward_interval_spinbox.value()
        oni_conf["widget_style"] = self.onigimon_widget_style_combo.currentText()
        oni_conf["sprite_motion"] = self.onigimon_sprite_motion_combo.currentData()
        oni_conf["scene_background_color"] = self.onigimon_scene_color
        oni_conf["scene_background_image"] = self.onigimon_scene_image
        oni_conf["scene_background_blur"] = self.onigimon_scene_blur_slider.value()
        oni_conf["scene_background_opacity"] = self.onigimon_scene_opacity_slider.value()
        if "Onigimon" in self._loaded_pages and self.onigimon_selected_companion_id:
            onigimon = _onigimon_module()
            onigimon.manager.set_active_companion(str(self.onigimon_selected_companion_id))
            onigimon.manager.rename_active_companion(self.onigimon_name_input.text().strip())
        
        # Mochi
        mochi_conf = self.current_config.setdefault("mochi_messages", {})
        mochi_conf["enabled"] = self.mochi_messages_toggle.isChecked()
        mochi_conf["cards_interval"] = self.mochi_interval_spinbox.value()
        mochi_conf["messages"] = self.mochi_messages_editor.messages()

        # Focus Dango
        dango_conf = self.achievements_config.setdefault("focusDango", {})
        dango_conf["enabled"] = self.focus_dango_toggle.isChecked()
        dango_conf["messages"] = self.focus_dango_message_editor.messages()
        dango_conf["self_sabotage"] = self.focus_dango_self_sabotage_toggle.isChecked()
        dango_pin = self.focus_dango_pin_input.pin()
        dango_conf["unlock_pin"] = dango_pin if len(dango_pin) == 6 else "000000"

        # Hexagon Land
        hex_conf = self.current_config.setdefault("hexagon_land", {})
        hex_conf["enabled"] = self.hexagon_land_toggle.isChecked()
        hex_conf["theme"] = "island"
        hex_conf["widget_display"] = self.hexagon_widget_display_combo.currentData() or "land_info"
        hex_conf["survival_mode"] = self.hexagon_survival_toggle.isChecked()
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
                font-weight: 700;
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
                font-weight: 700;
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
                font-weight: 600;
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
            QFrame#contentContainer {{
                background-color: {content_bg};
                border: none;
                border-radius: 28px;
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
                font-weight: bold;
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
                font-weight: bold;
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
                font-weight: 800;
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
                font-weight: 600;
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
                font-weight: 600;
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
                font-weight: 700;
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
            QFrame#studyZoneMessageRow {{
                background-color: {surface_bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            QLineEdit#studyZoneMessageInput {{
                background-color: transparent;
                color: {fg};
                border: none;
                padding: 5px 2px;
                selection-background-color: {accent};
                font-size: 13px;
            }}
            QLineEdit#studyZoneMessageInput:focus {{
                border: none;
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
                font-size: 16px;
                font-weight: 700;
                selection-background-color: {accent};
            }}
            QLineEdit#studyZonePinDigit:focus {{
                border-color: {accent};
            }}
            QPushButton#studyZoneMessageIconButton {{
                background-color: transparent;
                color: {muted};
                border: none;
                border-radius: 15px;
                padding: 0px;
            }}
            QPushButton#studyZoneMessageIconButton:hover {{
                background-color: {hover_bg};
                color: {fg};
            }}
            QPushButton#studyZoneMessageIconButton:disabled {{
                background-color: transparent;
                color: {border};
            }}
            QPushButton#studyZoneAddMessageButton {{
                background-color: {surface_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 16px;
                padding: 6px 14px;
                min-height: 32px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton#studyZoneAddMessageButton:hover {{
                border: 1px solid {accent};
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
            
            QWidget#innerGroup {{ background-color: {inner_group_bg}; border: 1px solid {border}; border-radius: 24px; }}
            
            /* General QPushButton fallback (for content area buttons only) */
            QPushButton {{ background-color: {surface_bg}; color: {fg}; border: 1px solid {border}; padding: 8px 12px; border-radius: 18px; }}
            QPushButton:pressed {{ background-color: {border}; }}
            
            QPushButton#dangerButton {{ color: #ff6b6b; font-weight: bold; border: 1px solid #ff6b6b; border-radius: 16px; padding: 8px; }}
            QPushButton#dangerButton:hover {{ background-color: #ff6b6b; color: white; }}
            
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
                font-weight: 700;
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
                border-radius: 15px;
                padding: 4px 14px;
                min-height: 28px;
            }}
            QPushButton#onigimonSceneButton:hover {{
                border: 1px solid #F2B705;
                background-color: {hover_bg};
            }}
            QLabel#onigimonSceneBlurValue {{
                color: {fg};
                min-width: 42px;
            }}
            QSlider#onigimonSceneSlider {{
                min-width: 180px;
            }}
            QSlider#onigimonSceneSlider::groove:horizontal {{
                height: 6px;
                border-radius: 3px;
                background-color: {border};
            }}
            QSlider#onigimonSceneSlider::sub-page:horizontal {{
                border-radius: 3px;
                background-color: #F2B705;
            }}
            QSlider#onigimonSceneSlider::handle:horizontal {{
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
                background-color: #F2B705;
                border: 1px solid rgba(0,0,0,0.16);
            }}

            QPushButton#notificationPositionButton {{
                background-color: transparent;
                color: {fg};
                border: 1px solid {border};
                border-radius: 16px;
                font-size: 20px;
                padding: 0;
            }}
            QPushButton#notificationPositionButton:hover {{
                background-color: {hover_bg};
            }}
            QPushButton#notificationPositionButton:checked {{
                background-color: {notification_checked_bg};
                color: {fg};
                border: 1px solid {accent};
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
