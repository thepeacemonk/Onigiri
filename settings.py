import os
import copy
import shutil
import urllib.parse
import json
import functools
import time
from datetime import datetime
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QDialogButtonBox, QWidget, QTabWidget, QColorDialog, QColor, QCheckBox,
    QGroupBox, QRadioButton, QFileDialog, QSpinBox, QPlainTextEdit, QFormLayout, QScrollArea,
    QGridLayout, QPixmap, Qt, QEvent, QPainter, QPainterPath, QMessageBox,
    QListWidget, QStackedWidget, QListWidgetItem, QFrame, QSizePolicy,
    QComboBox,
    QIcon, QPen, QBrush, QInputDialog, QAbstractButton, QDoubleSpinBox,
    QButtonGroup, QAbstractSpinBox,
    QDrag, QMimeData, QPoint, 
    QMenu, QAction, QActionGroup,
    QListWidget, QListWidgetItem, QAbstractItemView, QDateEdit, QLayout
)
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtProperty, QPointF, QSignalBlocker, QSize, QTimer, QDate, QLocale
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QUrl, QPropertyAnimation, QEasingCurve, QRegularExpression
from PyQt6.QtGui import QDesktopServices, QLinearGradient, QRegularExpressionValidator, QMouseEvent, QRegion, QGuiApplication, QCursor, QIntValidator

from aqt import mw
from aqt import mw, gui_hooks   
from aqt.theme import theme_manager
from typing import Union
from . import config
from .gamification import restaurant_level
from .config import DEFAULTS
from .constants import COLOR_LABELS, ICON_DEFAULTS, DEFAULT_ICON_SIZES, ALL_THEME_KEYS, REVIEWER_THEME_KEYS
from .themes import THEMES 
from aqt.qt import QRectF
from PyQt6.QtGui import QImage
from aqt.utils import showInfo
from PyQt6.QtGui import QFontDatabase, QFont
from PyQt6.QtCore import QRect, QSize, QPoint
from .fonts import FONTS, get_all_fonts
from . import sidebar_api

THUMBNAIL_STYLE = "QLabel { border: 2px solid transparent; border-radius: 10px; } QLabel:hover { border: 2px solid #007bff; }"
THUMBNAIL_STYLE_SELECTED = "QLabel { border: 2px solid #007bff; border-radius: 10px; }"

CUSTOM_GOAL_COOLDOWN_SECONDS = 24 * 60 * 60

class FlowLayout(QLayout):
    """A responsive layout that arranges widgets horizontally when space permits, vertically otherwise."""
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self._do_layout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._item_list:
            widget = item.widget()
            if widget is None:
                continue
            
            space_x = spacing
            space_y = spacing
            next_x = x + item.sizeHint().width() + space_x
            
            # If this item doesn't fit and we're not at the start of a line, move to next line
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()

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
    painter.drawImage(0, 0, cropped_image)
    painter.end()

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

class ThumbnailWorker(QObject):
    thumbnail_ready = pyqtSignal(str, int, QPixmap, str)
    finished = pyqtSignal()

    def __init__(self, key, full_folder_path, image_files, shape='rounded'):
        super().__init__()
        self.key = key
        self.full_folder_path = full_folder_path
        self.image_files = image_files
        self.is_cancelled = False
        self.shape = shape

    def run(self):
        # --- MODIFIED: Reduced dimensions to create padding ---
        # Original was 110x62. New dimensions are 10px smaller.
        thumb_width = 100
        thumb_height = 55 # Kept aspect ratio close to 16:9

        for index, filename in enumerate(self.image_files):
            if self.is_cancelled:
                break
            try:
                pixmap_path = os.path.join(self.full_folder_path, filename)
                final_pixmap = QPixmap()

                if self.shape == 'circular':
                    source_image = QImage(pixmap_path)
                    if not source_image.isNull():
                        final_pixmap = create_circular_pixmap(source_image, 100)
                else: # 'rounded'
                    pixmap = QPixmap(pixmap_path)
                    if not pixmap.isNull():
                        # Scale the image to cover the smaller target rectangle
                        scaled_pixmap = pixmap.scaled(
                            thumb_width, thumb_height, 
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        # Crop from the center
                        crop_x = (scaled_pixmap.width() - thumb_width) / 2
                        crop_y = (scaled_pixmap.height() - thumb_height) / 2
                        
                        cropped_pixmap = scaled_pixmap.copy(int(crop_x), int(crop_y), thumb_width, thumb_height)
                        
                        final_pixmap = create_rounded_pixmap(cropped_pixmap, 10)
                
                if not final_pixmap.isNull():
                    self.thumbnail_ready.emit(self.key, index, final_pixmap, filename)
            except Exception as e:
                print(f"Onigiri ThumbnailWorker Error for '{filename}': {e}")
        self.finished.emit()

    def cancel(self):
        self.is_cancelled = True

class SelectionOverlay(QWidget):
    def __init__(self, parent=None, accent_color="#D65DB1"):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self._checked = False
        self.accent_color = QColor(accent_color)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) # Let clicks pass through

    def setChecked(self, checked):
        self._checked = checked
        self.update()

    def isChecked(self):
        return self._checked

    def paintEvent(self, event):
        if not self._checked:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw white circle
        painter.setBrush(Qt.GlobalColor.white)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self.rect())
        
        # Draw checkmark
        path = QPainterPath()
        path.moveTo(7, 12)
        path.lineTo(10, 15)
        path.lineTo(17, 8)
        
        # Use the accent color for the checkmark
        pen = QPen(self.accent_color) 
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)

class CircularColorButton(QPushButton):
    def __init__(self, color=QColor("white"), parent=None):
        super().__init__("", parent)
        self.setFixedSize(26, 26)
        self._color = QColor(color)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Choose Color")

    def color(self):
        return self._color

    def setColor(self, color):
        qcolor = QColor(color)
        if self._color != qcolor:
            self._color = qcolor
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QBrush(self._color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(rect)
        border_color = QColor("#888888")
        pen = QPen(border_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)

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

class ProfileBarWidget(QWidget):
    clicked = pyqtSignal()

    def __init__(self, user_name, pic_path, bg_mode, bg_config, accent_color, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(50)
        self.setToolTip("Open Profile Settings")

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

class SidebarToggleButton(QWidget):
    page_selected = pyqtSignal(str)

    def __init__(self, title, items, parent=None):
        super().__init__(parent)
        self.items = items
        self.title = title
        self.is_open = False
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.toggle_button = QPushButton(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setObjectName("mainItemButton")
        self.toggle_button.clicked.connect(self._toggle_content)
        main_layout.addWidget(self.toggle_button)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(15, 5, 0, 5)
        self.content_layout.setSpacing(4)
        
        self.sub_button_group = QButtonGroup()
        self.sub_button_group.setExclusive(True)

        self.sub_buttons = {}
        for item in items:
            button = QPushButton(item)
            button.setCheckable(True)
            button.setObjectName("subItemButton")
            button.clicked.connect(lambda _, name=item: self.page_selected.emit(name))
            self.sub_buttons[item] = button
            self.content_layout.addWidget(button)
            self.sub_button_group.addButton(button)

        main_layout.addWidget(self.content_widget)
        self.content_widget.hide()

    def _toggle_content(self, checked):
        self.is_open = checked
        self.content_widget.setVisible(checked)
        if not checked:
            if btn := self.sub_button_group.checkedButton():
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
                self.page_selected.emit("")

    def select_page(self, page_name):
        if page_name in self.sub_buttons:
            if not self.is_open:
                self.toggle_button.click()
            self.sub_buttons[page_name].setChecked(True)
            return True
        return False

    def deselect_all(self):
        self.toggle_button.setChecked(False)
        self.is_open = False
        self.content_widget.hide()
        if btn := self.sub_button_group.checkedButton():
             btn.blockSignals(True)
             btn.setChecked(False)
             btn.blockSignals(False)

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
        
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(10)
        main_layout.addWidget(self.content_area)

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)

class ColorSwatch(QWidget):
    """A simple widget to display a circle of a solid color."""
    def __init__(self, color_hex, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.color = QColor(color_hex)
        self.setToolTip(color_hex.upper())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self.color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self.rect())

class ThemeCardWidget(QFrame):
    """A clickable card widget to display and select a theme."""
    theme_selected = pyqtSignal(dict)
    delete_requested = pyqtSignal(str) # Signal to request deletion

    def __init__(self, theme_name, theme_data, parent=None, deletable=False, delete_icon=None):
        super().__init__(parent)
        self.theme_name = theme_name
        self.theme_data = theme_data

        self.setObjectName("themeCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        main_layout = QVBoxLayout(self)

        # --- Top row with title and delete button ---
        top_layout = QHBoxLayout()
        name_label = QLabel(theme_name)
        name_label.setStyleSheet("font-weight: bold; font-size: 14px; background: transparent;")
        top_layout.addWidget(name_label)
        top_layout.addStretch()

        if deletable:
            self.delete_button = QPushButton()
            self.delete_button.setFixedSize(30, 30)
            self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.delete_button.setToolTip("Delete this theme")
            if delete_icon:
                self.delete_button.setIcon(delete_icon)
                self.delete_button.setIconSize(self.delete_button.size() * 0.6)
            
            # Style it to be subtle
            self.delete_button.setStyleSheet("""
                QPushButton { background: transparent; border: none; border-radius: 4px; }
                QPushButton:hover { background: rgba(128, 128, 128, 0.2); }
            """)
            self.delete_button.clicked.connect(self._on_delete_clicked)
            top_layout.addWidget(self.delete_button)

        # --- Bottom row with color swatches ---
        swatch_layout = QHBoxLayout()
        swatch_layout.setSpacing(6)

        # 1. Colors
        preview_colors = theme_data['light']
        color_count = 0
        for key in ["--accent-color", "--fg", "--fg-subtle", "--border", "--canvas-inset", "--bg"]:
            if key in preview_colors:
                swatch_layout.addWidget(ColorSwatch(preview_colors[key]))
                color_count += 1
                if color_count >= 5: break # Limit to 5 colors
        swatch_layout.addStretch()

        main_layout.addLayout(top_layout)
        main_layout.addLayout(swatch_layout)

        # --- Asset Previews (New) ---
        assets = theme_data.get("assets", {})
        if assets:
            asset_layout = QHBoxLayout()
            asset_layout.setSpacing(8)
            
            # Images
            if "images" in assets:
                unique_paths = set()
                unique_images = []
                for img_path in assets["images"].values():
                    # Ensure path is valid before adding
                    if img_path and os.path.exists(img_path) and img_path not in unique_paths:
                        unique_paths.add(img_path)
                        unique_images.append(img_path)
                
                for img_path in unique_images[:3]: 
                    thumb = QLabel()
                    thumb.setFixedSize(26, 26)
                    thumb.setScaledContents(False) # We will scale manually
                    thumb.setStyleSheet(f"border: none; background-color: transparent;")
                    
                    pix = QPixmap(img_path)
                    if not pix.isNull():
                         # Scale to target size keeping usage of create_rounded_pixmap
                         # If we want 26x26
                         scaled = pix.scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                         # Crop center 26x26
                         x = (scaled.width() - 26) // 2
                         y = (scaled.height() - 26) // 2
                         cropped = scaled.copy(x, y, 26, 26)
                         
                         rounded = create_rounded_pixmap(cropped, 6)
                         thumb.setPixmap(rounded)
                         thumb.setToolTip(f"Image included: {os.path.basename(img_path)}")
                         asset_layout.addWidget(thumb)

            # Fonts - show configured fonts (from font_config) even if not portable files
            font_config = assets.get("font_config", {})
            fonts_dict = assets.get("fonts", {})
            
            # Combine both sources: portable files and configured selections
            all_fonts_to_show = set()
            if fonts_dict:
                all_fonts_to_show.update(fonts_dict.keys())
            if font_config:
                all_fonts_to_show.update(font_config.values())
            
            if all_fonts_to_show:
                # Import fonts module to access already-loaded fonts
                from .fonts import get_all_fonts
                all_available_fonts = get_all_fonts(os.path.dirname(__file__))
                
                font_count = 0
                for font_key in list(all_fonts_to_show)[:2]:
                    font_label = QLabel("Aa")
                    font_label.setFixedSize(26, 26)
                    font_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    
                    # Auto-detect theme mode
                    bg_color = preview_colors.get('--bg', '#ffffff')
                    try:
                        bg_hex = bg_color.lstrip('#')
                        r, g, b = int(bg_hex[0:2], 16), int(bg_hex[2:4], 16), int(bg_hex[4:6], 16)
                        brightness = (r * 299 + g * 587 + b * 114) / 1000
                        is_dark = brightness < 128
                    except:
                        is_dark = False
                    
                    if is_dark:
                        border_col = '#aaaaaa'
                        text_col = '#ffffff'
                        bg_col = '#3a3a3a'
                    else:
                        border_col = '#cccccc'
                        text_col = '#333333'
                        bg_col = '#f5f5f5'
                    
                    # Load font the same way FontCardWidget does
                    font_info = all_available_fonts.get(font_key)
                    if font_info and font_info.get("file"):
                        addon_path = os.path.dirname(__file__)
                        # Handle user-uploaded fonts
                        if font_info.get("user"):
                            font_path = os.path.join(addon_path, "user_files", "fonts", font_info["file"])
                        # Handle built-in system fonts
                        else:
                            font_path = os.path.join(addon_path, "system_files", "fonts", "system_fonts", font_info["file"])
                        
                        if os.path.exists(font_path):
                            font_id = QFontDatabase.addApplicationFont(font_path)
                            if font_id != -1:
                                font_families = QFontDatabase.applicationFontFamilies(font_id)
                                if font_families:
                                    # Apply the font to the label
                                    font_label.setFont(QFont(font_families[0], 13))
                    
                    # Set stylesheet (font is already set via setFont)
                    font_label.setStyleSheet(
                        f"border: 1px solid {border_col}; "
                        f"border-radius: 6px; "
                        f"color: {text_col}; "
                        f"background-color: {bg_col}; "
                        f"font-weight: bold;"
                    )
                    
                    font_label.setToolTip(f"Font: {font_key}")
                    asset_layout.addWidget(font_label)
                    font_count += 1
            
            # Icons - show all configured icons including defaults
            icons_dict = assets.get("icons", {})
            icon_config = assets.get("icon_config", {})
            
            # Use icons_dict primarily, fall back to icon_config
            icons_to_show = []
            if icons_dict:
                icons_to_show = list(icons_dict.items())[:2]
            elif icon_config:
                icons_to_show = list(icon_config.items())[:2]
            
            if icons_to_show:
                for icon_key, icon_value in icons_to_show:
                    # icon_value could be a filename or a path
                    # Try to find the icon file
                    possible_paths = [
                        os.path.join(os.path.dirname(__file__), "user_files", "icons", os.path.basename(icon_value)),
                        os.path.join(os.path.dirname(__file__), "user_files", "icons", icon_value),
                    ]
                    
                    full_path = None
                    for path in possible_paths:
                        if os.path.exists(path):
                            full_path = path
                            break
                    
                    # If not found in user_files, check if it's a default icon
                    if not full_path and icon_key in ICON_DEFAULTS:
                        # Use default icon data
                        default_svg_data = ICON_DEFAULTS[icon_key]
                        
                        thumb = QLabel()
                        thumb.setFixedSize(26, 26)
                        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        thumb.setStyleSheet("background: transparent; border: none;")
                        
                        icon_color = preview_colors.get("--icon-color", preview_colors.get("--fg", "#888"))
                        
                        try:
                            # Default icons are data URIs: "data:image/svg+xml,<svg>..."
                            if default_svg_data.startswith("data:image/svg+xml,"):
                                svg_xml = default_svg_data.replace("data:image/svg+xml,", "")
                                import urllib.parse
                                svg_xml = urllib.parse.unquote(svg_xml)
                                
                                # Color the SVG
                                if 'stroke="currentColor"' in svg_xml:
                                    colored_svg = svg_xml.replace('stroke="currentColor"', f'stroke="{icon_color}"')
                                elif 'fill="currentColor"' in svg_xml:
                                    colored_svg = svg_xml.replace('fill="currentColor"', f'fill="{icon_color}"')
                                else:
                                    colored_svg = svg_xml.replace('<svg', f'<svg fill="{icon_color}" stroke="{icon_color}"', 1)
                                
                                renderer = QSvgRenderer(colored_svg.encode('utf-8'))
                                pixmap = QPixmap(26, 26)
                                pixmap.fill(Qt.GlobalColor.transparent)
                                painter = QPainter(pixmap)
                                renderer.render(painter)
                                painter.end()
                                
                                thumb.setPixmap(pixmap)
                                thumb.setToolTip(f"Icon: {icon_key} (default)")
                                asset_layout.addWidget(thumb)
                        except Exception as e:
                            print(f"Default icon preview error for {icon_key}: {e}")
                        continue
                    
                    if full_path:
                        thumb = QLabel()
                        thumb.setFixedSize(26, 26)
                        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        thumb.setStyleSheet("background: transparent; border: none;")
                        
                        icon_color = preview_colors.get("--icon-color", preview_colors.get("--fg", "#888"))
                        
                        pixmap = QPixmap(26, 26)
                        pixmap.fill(Qt.GlobalColor.transparent)
                        
                        loaded = False
                        if full_path.lower().endswith(".svg"):
                            try:
                                with open(full_path, 'r', encoding='utf-8') as f: svg_xml = f.read()
                                
                                if 'stroke="currentColor"' in svg_xml:
                                    colored_svg = svg_xml.replace('stroke="currentColor"', f'stroke="{icon_color}"')
                                elif 'fill="currentColor"' in svg_xml:
                                    colored_svg = svg_xml.replace('fill="currentColor"', f'fill="{icon_color}"')
                                else:
                                    colored_svg = svg_xml.replace('<svg', f'<svg fill="{icon_color}" stroke="{icon_color}"', 1)
                                
                                renderer = QSvgRenderer(colored_svg.encode('utf-8'))
                                painter = QPainter(pixmap)
                                renderer.render(painter)
                                painter.end()
                                loaded = True
                            except Exception as e:
                                print(f"Icon preview error: {e}")
                        
                        if not loaded:
                            temp_pix = QPixmap(full_path)
                            if not temp_pix.isNull():
                                temp_pix = temp_pix.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                                painter = QPainter(pixmap)
                                x = (26 - temp_pix.width()) // 2
                                y = (26 - temp_pix.height()) // 2
                                painter.drawPixmap(x, y, temp_pix)
                                painter.end()
                                loaded = True
                        
                        if loaded:
                            thumb.setPixmap(pixmap)
                            thumb.setToolTip(f"Icon: {icon_key}")
                            asset_layout.addWidget(thumb)

            asset_layout.addStretch()
            if asset_layout.count() > 1: # Only add if we added widgets (stretch is 1)
                div = QFrame()
                div.setFrameShape(QFrame.Shape.HLine)
                div.setFrameShadow(QFrame.Shadow.Sunken)
                div.setStyleSheet("color: #ddd;")
                main_layout.addWidget(div)
                main_layout.addLayout(asset_layout)

    def _on_delete_clicked(self):
        # Stop the event from propagating to the mousePressEvent
        self.block_card_click = True
        self.delete_requested.emit(self.theme_name)

    def mousePressEvent(self, event):
        # A small mechanism to prevent card selection when delete is clicked
        if hasattr(self, 'block_card_click') and self.block_card_click:
            self.block_card_click = False
            return
            
        self.theme_selected.emit(self.theme_data)
        super().mousePressEvent(event)

class BirthdayWidget(QWidget):
    def __init__(self, accent_color="#007bff", parent=None):
        super().__init__(parent)
        
        # Resolve real accent color from theme to match accurately
        current_theme = mw.col.conf.get("modern_menu_theme", "Tokyo Drift")
        if current_theme in THEMES:
            mode = "dark" if theme_manager.night_mode else "light"
            accent_color = THEMES[current_theme][mode].get("--accent-color", accent_color)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self.accent_color = accent_color

        # Common style for input fields
        if theme_manager.night_mode:
            bg_color = "#3a3a3a"
            text_color = "#e0e0e0"
            border_color = "#555"
            hover_border_color = "#777"
        else:
            bg_color = "white"
            text_color = "#333"
            border_color = "#e0e0e0"
            hover_border_color = "#b0b0b0"

        input_style = f"""
            QLineEdit {{
                padding: 7px 11px;
                border: 2px solid {border_color};
                border-radius: 8px;
                background-color: {bg_color};
                color: {text_color};
                font-size: 13px;
                selection-background-color: {accent_color};
                outline: none;
            }}
            QLineEdit:hover {{
                border-color: {hover_border_color};
            }}
            QLineEdit:focus {{
                border: 2px solid {accent_color};
                background-color: {bg_color};
            }}
        """

        # Day Input
        self.day_input = QLineEdit()
        self.day_input.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.day_input.setPlaceholderText("Day")
        self.day_input.setValidator(QIntValidator(1, 31))
        self.day_input.setFixedWidth(70)
        self.day_input.setStyleSheet(input_style)
        self.day_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Month Input
        self.month_input = QLineEdit()
        self.month_input.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.month_input.setPlaceholderText("Month")
        self.month_input.setValidator(QIntValidator(1, 12))
        self.month_input.setFixedWidth(70)
        self.month_input.setStyleSheet(input_style)
        self.month_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Year Input
        self.year_input = QLineEdit()
        self.year_input.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.year_input.setPlaceholderText("Year")
        self.year_input.setValidator(QIntValidator(1900, 2100))
        self.year_input.setFixedWidth(80)
        self.year_input.setStyleSheet(input_style)
        self.year_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.day_input)
        layout.addWidget(self.month_input)
        layout.addWidget(self.year_input)
        layout.addStretch()

    def setDate(self, date):
        if not date.isValid():
            return
        
        # Set Day
        self.day_input.setText(str(date.day()))
        
        # Set Month
        self.month_input.setText(str(date.month()))
        
        # Set Year
        self.year_input.setText(str(date.year()))

    def date(self):
        try:
            if not self.day_input.text() or not self.month_input.text() or not self.year_input.text():
                return QDate()
            
            day = int(self.day_input.text())
            month = int(self.month_input.text())
            year = int(self.year_input.text())
            
            return QDate(year, month, day)
        except:
            return QDate()


class FontCardWidget(QPushButton):
    """A custom button widget to display and select a font."""
    # <<< START NEW CODE >>>
    delete_requested = pyqtSignal(str) # Signal with font_key (filename)
    # <<< END NEW CODE >>>

    def __init__(self, font_key, accent_color, parent=None, is_system_card=False, delete_icon=None):
        super().__init__(parent)
        self.font_key = font_key
        all_fonts = get_all_fonts(os.path.dirname(__file__))
        font_info = all_fonts.get(font_key)
        
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        if is_system_card:
            self.setFixedHeight(50)
            layout = QHBoxLayout(self) # Horizontal layout
            layout.setContentsMargins(15, 10, 15, 10)
            
            name_label = QLabel(font_info["name"])
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(name_label)
        else:
            self.setFixedSize(140, 80)
            layout = QVBoxLayout(self) # Vertical layout
            layout.setContentsMargins(10, 10, 10, 10)

            aa_label = QLabel("Aa")
            aa_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            name_label = QLabel(font_info["name"])
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            layout.addWidget(aa_label, 1)
            layout.addWidget(name_label, 0)
        
        if font_info and font_info.get("file"):
            addon_path = os.path.dirname(__file__)
            # Correctly handles user-uploaded fonts
            if font_info.get("user"):
                font_path = os.path.join(addon_path, "user_files", "fonts", font_info["file"])
            # Correctly handles the built-in system fonts
            else:
                # FIX: Corrected the path to the system_fonts subfolder
                font_path = os.path.join(addon_path, "system_files", "fonts", "system_fonts", font_info["file"])

            if os.path.exists(font_path):
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    font_families = QFontDatabase.applicationFontFamilies(font_id)
                    if font_families:
                        font_size = 14 if is_system_card else 12
                        name_label.setFont(QFont(font_families[0], font_size))
                        if not is_system_card:
                            aa_label.setFont(QFont(font_families[0], 20))

        self.delete_button = None
        if font_info.get("user"):
            self.delete_button = QPushButton(self)
            self.delete_button.setFixedSize(22, 22)
            if delete_icon:
                self.delete_button.setIcon(delete_icon)
                self.delete_button.setIconSize(QSize(14, 14))
            else:
                self.delete_button.setText("✕")
            self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.delete_button.setToolTip("Delete this font")
            self.delete_button.clicked.connect(self._on_delete_clicked)
            self.delete_button.setStyleSheet(f"""
                QPushButton {{
                    font-size: 14px;
                    font-weight: bold;
                    color: hsl(0, 0, 63, 0.5);
                    background: transparent; 
                    border: none;
                    border-radius: 11px;
                }}
                QPushButton:hover {{ 
                    background: transparent; 
                    color: hsl(0, 0, 63);
                }}
            """)

        if theme_manager.night_mode:
            self.setStyleSheet(f"""
                QPushButton {{ background-color: #3a3a3a; border: 2px solid #4a4a4a; border-radius: 12px; color: #e0e0e0; }}
                QPushButton:hover {{ border-color: #5a5a5a; }}
                QPushButton:checked {{ border-color: {accent_color}; }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{ background-color: #e9e9e9; border: 2px solid #e0e0e0; border-radius: 12px; color: #212121; }}
                QPushButton:hover {{ border-color: #d0d0d0; }}
                QPushButton:checked {{ border-color: {accent_color}; }}
            """)
    
    # <<< START NEW CODE >>>
    def _on_delete_clicked(self):
        self.delete_requested.emit(self.font_key)

    def resizeEvent(self, event):
        """Ensure the delete button stays in the top-right corner."""
        super().resizeEvent(event)
        if self.delete_button:
            self.delete_button.move(self.width() - self.delete_button.width() - 5, 5)
    # <<< END NEW CODE >>>

class ColorMapWidget(QWidget):
    colorChanged = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 150)
        self._hue = 0.0
        self._sat = 0.0
        self._val = 0.0
        self._cursor_pos = QPoint(0, 0)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def setHue(self, hue):
        self._hue = hue
        self.update()
        self._emit_color()

    def setColor(self, color):
        self._hue = color.hueF()
        self._sat = color.saturationF()
        self._val = color.valueF()
        if self._hue == -1: self._hue = 0
        self._update_cursor_from_color()
        self.update()

    def _update_cursor_from_color(self):
        x = int(self._sat * self.width())
        y = int((1 - self._val) * self.height())
        self._cursor_pos = QPoint(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._hue == -1: hue_color = QColor(255, 255, 255)
        else: hue_color = QColor.fromHsvF(max(0, self._hue), 1.0, 1.0)
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 12, 12)
        painter.setClipPath(path)
        
        painter.setBrush(hue_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

        sat_grad = QLinearGradient(0, 0, self.width(), 0)
        sat_grad.setColorAt(0, QColor(255, 255, 255, 255))
        sat_grad.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(self.rect(), sat_grad)

        val_grad = QLinearGradient(0, 0, 0, self.height())
        val_grad.setColorAt(0, QColor(0, 0, 0, 0))
        val_grad.setColorAt(1, QColor(0, 0, 0, 255))
        painter.fillRect(self.rect(), val_grad)


        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(self._cursor_pos, 6, 6)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawEllipse(self._cursor_pos, 6, 6)

    def mousePressEvent(self, event):
        self._update_color(event.pos())

    def mouseMoveEvent(self, event):
        self._update_color(event.pos())

    def _update_color(self, pos):
        x = max(0, min(pos.x(), self.width()))
        y = max(0, min(pos.y(), self.height()))
        self._cursor_pos = QPoint(x, y)
        
        self._sat = x / self.width()
        self._val = 1.0 - (y / self.height())
        
        self._emit_color()
        self.update()

    def _emit_color(self):
        color = QColor.fromHsvF(max(0, self._hue), self._sat, self._val)
        self.colorChanged.emit(color)

class GradientSlider(QWidget):
    valueChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 12)
        self._value = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setValue(self, value):
        self._value = max(0.0, min(1.0, value))
        self.update()

    def mousePressEvent(self, event):
        self._update_value(event.pos())

    def mouseMoveEvent(self, event):
        self._update_value(event.pos())

    def _update_value(self, pos):
        val = pos.x() / self.width()
        self._value = max(0.0, min(1.0, val))
        self.valueChanged.emit(self._value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.draw_track(painter)
        thumb_x = int(self._value * self.width())
        thumb_x = max(6, min(thumb_x, self.width() - 6))
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setBrush(Qt.GlobalColor.transparent)
        painter.drawEllipse(QPoint(thumb_x, self.height() // 2), 5, 5)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawEllipse(QPoint(thumb_x, self.height() // 2), 5, 5)

    def draw_track(self, painter):
        pass

class HueSlider(GradientSlider):
    def draw_track(self, painter):
        grad = QLinearGradient(0, 0, self.width(), 0)
        for i in range(7):
            grad.setColorAt(i / 6.0, QColor.fromHsvF(i / 6.0, 1.0, 1.0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 6, 6)

class AlphaSlider(GradientSlider):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._color = QColor(255, 0, 0)

    def setColor(self, color):
        self._color = color
        self.update()

    def draw_track(self, painter):
        painter.save()
        painter.setClipRect(self.rect())
        check_size = 4
        for y in range(0, self.height(), check_size):
            for x in range(0, self.width(), check_size):
                if (x // check_size + y // check_size) % 2 == 0:
                    painter.fillRect(x, y, check_size, check_size, QColor(200, 200, 200))
                else:
                    painter.fillRect(x, y, check_size, check_size, QColor(255, 255, 255))
        painter.restore()
        grad = QLinearGradient(0, 0, self.width(), 0)
        c1 = QColor(self._color); c1.setAlpha(0)
        c2 = QColor(self._color); c2.setAlpha(255)
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 6, 6)

class FavoriteColorButton(QWidget):
    def __init__(self, color_hex, on_select, on_remove, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.color_hex = color_hex
        self.on_select = on_select
        self.on_remove = on_remove
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Long click to delete")
        
        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.setInterval(800) 
        self._long_press_timer.timeout.connect(self._handle_long_press)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(self.color_hex))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._long_press_timer.start()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._long_press_timer.isActive():
                self._long_press_timer.stop()
                self.on_select(self.color_hex)

    def _handle_long_press(self):
        self.on_remove(self.color_hex)





class ModernColorPickerDialog(QDialog):
    colorSelected = pyqtSignal(QColor)

    def __init__(self, initial_color=QColor("white"), parent=None, favorite_colors=None):
        super().__init__(parent)
        self.setWindowTitle("Select Color")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._color = QColor(initial_color)
        self.favorite_colors = favorite_colors[:] if favorite_colors else []
        self._drag_pos = None

        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.container = QFrame()
        self.container.setObjectName("ColorPickerContainer")
        if theme_manager.night_mode:
             self.container.setStyleSheet("QFrame#ColorPickerContainer { background-color: #2c2c2c; border-radius: 12px; border: 1px solid #4a4a4a; }")
        else:
             self.container.setStyleSheet("QFrame#ColorPickerContainer { background-color: #ffffff; border-radius: 12px; border: 1px solid #e0e0e0; }")

        container_layout = QVBoxLayout(self.container)
        container_layout.setSpacing(15)
        
        # --- Header with Close Button ---
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("Select Color")
        
        close_btn = QPushButton()
        close_btn.setFixedSize(24, 24)
        close_btn.setMaximumSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        
        icon_path = os.path.join(os.path.dirname(__file__), "system_files", "system_icons", "xmark-simple.svg")
        
        # Style the close button and title to be adapted to the theme
        if theme_manager.night_mode:
            title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #d0d0d0;")
            close_btn.setStyleSheet("""
                QPushButton { 
                    background-color: transparent; 
                    border: none; 
                    border-radius: 12px; 
                    padding: 0px;
                    margin: 0px;
                    min-width: 24px; 
                    min-height: 24px;
                    max-width: 24px;
                    max-height: 24px;
                }
                QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }
            """)
            icon_color = QColor("#ffffff")
        else:
            title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #333333;")
            close_btn.setStyleSheet("""
                QPushButton { 
                    background-color: transparent; 
                    border: none; 
                    border-radius: 12px; 
                    padding: 0px;
                    margin: 0px;
                    min-width: 24px; 
                    min-height: 24px;
                    max-width: 24px;
                    max-height: 24px;
                }
                QPushButton:hover { background-color: rgba(0, 0, 0, 0.05); }
            """)
            icon_color = QColor("#555555")

            
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                # Colorize the icon
                painter = QPainter(pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), icon_color)
                painter.end()
                
                close_btn.setIcon(QIcon(pixmap))
                close_btn.setIconSize(QSize(12, 12))
            else:
                close_btn.setText("x")
                close_btn.setStyleSheet(close_btn.styleSheet() + f"color: {icon_color.name()}; font-weight: bold; font-size: 16px; font-family: Arial, sans-serif; padding-bottom: 2px;")
        else:
            close_btn.setText("x")
            close_btn.setStyleSheet(close_btn.styleSheet() + f"color: {icon_color.name()}; font-weight: bold; font-size: 16px; font-family: Arial, sans-serif; padding-bottom: 2px;")
            
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        container_layout.addLayout(header_layout)
        # --------------------------------
        
        self.color_map = ColorMapWidget()
        self.color_map.colorChanged.connect(self._on_map_color_changed)
        container_layout.addWidget(self.color_map, 0, Qt.AlignmentFlag.AlignCenter)
        
        sliders_layout = QVBoxLayout()
        sliders_layout.setSpacing(8)
        self.hue_slider = HueSlider()
        self.hue_slider.valueChanged.connect(self._on_hue_changed)
        sliders_layout.addWidget(self.hue_slider, 0, Qt.AlignmentFlag.AlignCenter)
        # Alpha slider removed
        container_layout.addLayout(sliders_layout)
        
        input_layout = QHBoxLayout()
        self.preview_circle = QLabel()
        self.preview_circle.setFixedSize(32, 32)
        
        self.hex_input = QLineEdit(self._color.name())
        self.hex_input.setFixedWidth(100)
        self.hex_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if theme_manager.night_mode:
            self.hex_input.setStyleSheet("QLineEdit { background-color: #333; color: #fff; border: 1px solid #555; border-radius: 12px; padding: 4px; }")
        else:
            self.hex_input.setStyleSheet("QLineEdit { background-color: #fff; color: #000; border: 1px solid #ccc; border-radius: 12px; padding: 4px; }")
        self.hex_input.textChanged.connect(self._on_hex_changed)

        
        input_layout.addWidget(self.preview_circle)
        input_layout.addWidget(self.hex_input)
        input_layout.addStretch()
        container_layout.addLayout(input_layout)
        
        # --- Favorites Section ---
        fav_header = QHBoxLayout()
        fav_label = QLabel("Favorite Colors")
        if theme_manager.night_mode:
            fav_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #888;")
        else:
            fav_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #666;")
            
        add_fav_btn = QPushButton()
        add_fav_btn.setFixedSize(24, 24)
        add_fav_btn.setMaximumSize(24, 24)
        add_fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_fav_btn.setToolTip("Add current color to favorites")
        add_fav_btn.clicked.connect(self.add_current_to_favorites)
        
        add_icon_path = os.path.join(os.path.dirname(__file__), "system_files", "system_icons", "add.svg")
        
        if theme_manager.night_mode:
            add_fav_btn.setStyleSheet("""
                QPushButton { 
                    background-color: #3a3a3a; 
                    border: 1px solid #555; 
                    border-radius: 12px; 
                    padding: 0px;
                    margin: 0px;
                    min-width: 24px; 
                    min-height: 24px;
                    max-width: 24px;
                    max-height: 24px;
                }
                QPushButton:hover { background-color: #4a4a4a; }
            """)
            add_icon_color = QColor("#cccccc")
        else:
            add_fav_btn.setStyleSheet("""
                QPushButton { 
                    background-color: #f0f0f0; 
                    border: 1px solid #ccc; 
                    border-radius: 12px; 
                    padding: 0px;
                    margin: 0px;
                    min-width: 24px; 
                    min-height: 24px;
                    max-width: 24px;
                    max-height: 24px;
                }
                QPushButton:hover { background-color: #e0e0e0; }
            """)
            add_icon_color = QColor("#555555")

            
        if os.path.exists(add_icon_path):
            pixmap = QPixmap(add_icon_path)
            if not pixmap.isNull():
                painter = QPainter(pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), add_icon_color)
                painter.end()
                add_fav_btn.setIcon(QIcon(pixmap))
                add_fav_btn.setIconSize(QSize(12, 12))
            else:
                add_fav_btn.setText("+")
        else:
            add_fav_btn.setText("+")
            
        fav_header.addWidget(fav_label)
        fav_header.addStretch()
        fav_header.addWidget(add_fav_btn)
        container_layout.addLayout(fav_header)
        
        self.favorites_grid = QGridLayout()
        self.favorites_grid.setSpacing(8)
        container_layout.addLayout(self.favorites_grid)
        
        self.refresh_favorites()
        
        layout.addWidget(self.container)
        self.setColor(self._color)



    def refresh_favorites(self):
        # Clear grid
        while self.favorites_grid.count():
            child = self.favorites_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        for i, color_hex in enumerate(self.favorite_colors):
            btn = FavoriteColorButton(
                color_hex, 
                lambda c: self.setColor(QColor(c)), 
                self.remove_favorite
            )
            
            row, col = divmod(i, 8)
            self.favorites_grid.addWidget(btn, row, col)
            
    def add_current_to_favorites(self):
        color_hex = self._color.name()
        if color_hex not in self.favorite_colors:
            self.favorite_colors.append(color_hex)
            self.refresh_favorites()
            
    def show_context_menu(self, pos, color_hex, btn):
        menu = QMenu(self)
        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self.remove_favorite(color_hex))
        menu.addAction(remove_action)
        menu.exec(btn.mapToGlobal(pos))
        
    def remove_favorite(self, color_hex):
        if color_hex in self.favorite_colors:
            self.favorite_colors.remove(color_hex)
            self.refresh_favorites()

    def setColor(self, color):
        self._color = color
        self.color_map.setColor(color)
        self.hue_slider.setValue(max(0, color.hueF()))
        # Alpha slider update removed
        self.preview_circle.setStyleSheet(f"background-color: {color.name(QColor.NameFormat.HexArgb)}; border-radius: 16px; border: 1px solid #888;")
        self.hex_input.blockSignals(True)
        self.hex_input.setText(color.name())
        self.hex_input.blockSignals(False)
        self.colorSelected.emit(self._color)

    def _on_map_color_changed(self, color):
        # Preserve existing alpha if needed, though slider is gone
        alpha = self._color.alpha()
        self._color = color
        self._color.setAlpha(alpha)
        self._update_ui_from_internal()

    def _on_hue_changed(self, hue):
        self.color_map.setHue(hue)

    def _on_hex_changed(self, text):
        if QColor.isValidColor(text):
            self.setColor(QColor(text))

    def _update_ui_from_internal(self):
        # Alpha slider update removed
        self.preview_circle.setStyleSheet(f"background-color: {self._color.name(QColor.NameFormat.HexArgb)}; border-radius: 16px; border: 1px solid #888;")
        self.hex_input.blockSignals(True)
        self.hex_input.setText(self._color.name())
        self.hex_input.blockSignals(False)
        self.colorSelected.emit(self._color)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None




class IconPickerDialog(QDialog):
    iconSelected = pyqtSignal(str)

    def __init__(self, current_filename, addon_path, parent=None):
        super().__init__(parent)
        self.addon_path = addon_path
        self.current_filename = current_filename
        self.setWindowTitle("Select Icon")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setFixedSize(400, 500)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.container = QFrame()
        self.container.setObjectName("IconPickerContainer")
        if theme_manager.night_mode:
             self.container.setStyleSheet("QFrame#IconPickerContainer { background-color: #2c2c2c; border-radius: 12px; border: 1px solid #4a4a4a; }")
        else:
             self.container.setStyleSheet("QFrame#IconPickerContainer { background-color: #ffffff; border-radius: 12px; border: 1px solid #e0e0e0; }")

        container_layout = QVBoxLayout(self.container)
        container_layout.setSpacing(15)
        
        # --- Header ---
        header_layout = QHBoxLayout()
        title_label = QLabel("Select Icon")
        if theme_manager.night_mode:
            title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #e0e0e0;")
        else:
            title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #212121;")
            
        close_btn = QPushButton()
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        
        # Load xmark.svg
        xmark_path = os.path.join(os.path.dirname(__file__), "system_files", "system_icons", "xmark.svg")
        
        if theme_manager.night_mode:
            close_btn.setStyleSheet("""
                QPushButton { background-color: transparent; border: none; border-radius: 12px; }
                QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }
            """)
            icon_color = "#e0e0e0"
        else:
            close_btn.setStyleSheet("""
                QPushButton { background-color: transparent; border: none; border-radius: 12px; }
                QPushButton:hover { background-color: rgba(0, 0, 0, 0.05); }
            """)
            icon_color = "#555555"

        if os.path.exists(xmark_path):
            self._render_svg_to_icon(xmark_path, close_btn, icon_color)
        else:
            close_btn.setText("x")
            close_btn.setStyleSheet(close_btn.styleSheet() + f"color: {icon_color}; font-weight: bold; font-size: 16px;")

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        container_layout.addLayout(header_layout)
        
        # --- Search & Add ---
        tools_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search icons...")
        self.search_input.textChanged.connect(self._filter_icons)
        if theme_manager.night_mode:
            self.search_input.setStyleSheet("QLineEdit { background-color: #3a3a3a; border: 1px solid #555; border-radius: 6px; padding: 4px; color: #e0e0e0; } QLineEdit:focus { border-color: #777; }")
        else:
            self.search_input.setStyleSheet("QLineEdit { background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 6px; padding: 4px; color: #212121; } QLineEdit:focus { border-color: #aaa; }")
            
        add_btn = QPushButton("Add Icon")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_icon_from_file)
        if theme_manager.night_mode:
            add_btn.setStyleSheet("QPushButton { background-color: #3a3a3a; border: 1px solid #555; border-radius: 6px; padding: 4px 10px; color: #e0e0e0; } QPushButton:hover { background-color: #4a4a4a; }")
        else:
            add_btn.setStyleSheet("QPushButton { background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 6px; padding: 4px 10px; color: #212121; } QPushButton:hover { background-color: #e0e0e0; }")
            
        tools_layout.addWidget(self.search_input)
        tools_layout.addWidget(add_btn)

        # Use Default Button
        default_btn = QPushButton("Use Default")
        default_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        default_btn.clicked.connect(lambda: (self.iconSelected.emit(""), self.close()))
        if theme_manager.night_mode:
            default_btn.setStyleSheet("QPushButton { background-color: transparent; border: 1px solid #555; border-radius: 6px; padding: 4px 10px; color: #e0e0e0; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.05); }")
        else:
            default_btn.setStyleSheet("QPushButton { background-color: transparent; border: 1px solid #ccc; border-radius: 6px; padding: 4px 10px; color: #212121; } QPushButton:hover { background-color: rgba(0, 0, 0, 0.02); }")
        
        tools_layout.addWidget(default_btn)
        container_layout.addLayout(tools_layout)
        
        # --- Icon Grid ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; } QWidget { background: transparent; }")
        
        self.grid_content = QWidget()
        self.grid_layout = QGridLayout(self.grid_content)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        scroll_area.setWidget(self.grid_content)
        container_layout.addWidget(scroll_area)
        
        self.icons = [] # List of (filename, widget)
        self._load_icons()
        
        layout.addWidget(self.container)

    def _render_svg_to_icon(self, filepath, button, color_hex):
        try:
            with open(filepath, 'r', encoding='utf-8') as f: svg_xml = f.read()
            if 'stroke="currentColor"' in svg_xml: colored_svg = svg_xml.replace('stroke="currentColor"', f'stroke="{color_hex}"')
            elif 'fill="currentColor"' in svg_xml: colored_svg = svg_xml.replace('fill="currentColor"', f'fill="{color_hex}"')
            else: colored_svg = svg_xml.replace('<svg', f'<svg fill="{color_hex}" stroke="{color_hex}"', 1)
            
            renderer = QSvgRenderer(colored_svg.encode('utf-8'))
            pixmap = QPixmap(renderer.defaultSize())
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            
            # Simple scaling if needed, but for icon button usually best to let QIcon handle or pre-scale
            scaled = pixmap.scaled(12, 12, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            button.setIcon(QIcon(scaled))
            button.setIconSize(QSize(12, 12))
        except:
             button.setText("x")

    def _load_icons(self):
        # Clear existing
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.icons = []

        icons_dir = os.path.join(self.addon_path, "user_files/icons")
        if not os.path.exists(icons_dir):
            os.makedirs(icons_dir)
            
        files = sorted([f for f in os.listdir(icons_dir) if f.lower().endswith(".svg")])
        
        row, col = 0, 0
        num_cols = 4
        
        for filename in files:
            container = QWidget()
            container.setFixedSize(70, 70)
            container.setObjectName("IconItem")
            
            # Highlight if selected
            is_selected = (filename == self.current_filename)
            
            # Style
            bg_normal = "transparent"
            bg_hover = "rgba(255,255,255,0.1)" if theme_manager.night_mode else "rgba(0,0,0,0.05)"
            bg_selected = "rgba(255,255,255,0.2)" if theme_manager.night_mode else "rgba(0,0,0,0.1)"
            border_selected = "#777" if theme_manager.night_mode else "#aaa"
            
            container.setStyleSheet(f"""
                QWidget#IconItem {{
                    background-color: {bg_selected if is_selected else bg_normal};
                    border-radius: 8px;
                    border: {("1px solid " + border_selected) if is_selected else "1px solid transparent"};
                }}
                QWidget#IconItem:hover {{
                    background-color: {bg_hover};
                    border: 1px solid {border_selected};
                }}
            """)
            
            # Image
            layout = QVBoxLayout(container)
            layout.setContentsMargins(5, 5, 5, 5)
            
            preview = QLabel()
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Load SVG
            filepath = os.path.join(icons_dir, filename)
            # Render SVG
            self._render_svg_to_label(filepath, preview)
            
            layout.addWidget(preview)
            
            # Clickable overlay for selection
            btn = QPushButton(container)
            btn.setStyleSheet("background: transparent; border: none;")
            btn.setFixedSize(70, 70)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, f=filename: self._select_icon(f))
            btn.move(0, 0)
            
            # Delete Button (Top Right)
            del_btn = QPushButton(container)
            del_btn.setFixedSize(20, 20)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setToolTip("Delete Icon")
            del_btn.move(45, 5) # Position top-right
            
            # Load xmark icon
            xmark_path = os.path.join(os.path.dirname(__file__), "system_files", "system_icons", "xmark.svg")
            
            # Style for delete button: No background, no hover effect as requested
            btn_style = "QPushButton { background-color: transparent; border: none; }"
            
            if theme_manager.night_mode:
                del_btn.setStyleSheet(btn_style)
                icon_color = "#e0e0e0"
            else:
                del_btn.setStyleSheet(btn_style)
                icon_color = "#555555"

            if os.path.exists(xmark_path):
                self._render_svg_to_icon(xmark_path, del_btn, icon_color)
            else:
                del_btn.setText("×")
                del_btn.setStyleSheet(del_btn.styleSheet() + f"color: {icon_color}; font-weight: bold; padding-bottom: 2px;")

            del_btn.clicked.connect(lambda _, f=filename: self._delete_icon_file(f))
            del_btn.raise_() # Ensure it's on top of the selection buttton
            
            self.grid_layout.addWidget(container, row, col)
            self.icons.append((filename, container))
            
            col += 1
            if col >= num_cols:
                col = 0
                row += 1

    def _delete_icon_file(self, filename):
        confirm = QMessageBox.question(self, "Delete Icon", f"Are you sure you want to delete '{filename}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                os.remove(os.path.join(self.addon_path, "user_files/icons", filename))
                self._load_icons() # Reload grid
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not delete file: {e}")

    def _render_svg_to_label(self, filepath, label):
        color = "#e0e0e0" if theme_manager.night_mode else "#212121"
        try:
            with open(filepath, 'r', encoding='utf-8') as f: svg_xml = f.read()
            if 'stroke="currentColor"' in svg_xml: colored_svg = svg_xml.replace('stroke="currentColor"', f'stroke="{color}"')
            elif 'fill="currentColor"' in svg_xml: colored_svg = svg_xml.replace('fill="currentColor"', f'fill="{color}"')
            else: colored_svg = svg_xml.replace('<svg', f'<svg fill="{color}" stroke="{color}"', 1)
            
            renderer = QSvgRenderer(colored_svg.encode('utf-8'))
            pixmap = QPixmap(renderer.defaultSize())
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            label.setPixmap(pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except:
             label.setText("?")

    def _filter_icons(self, text):
        text = text.lower()
        # Simple hide/show logic. Since it's a grid, hiding items leaves gaps in QGridLayout.
        # We should probably clear and rebuild grid if we want to remove gaps, or use a FlowLayout.
        # For simplicity/speed: Rebuild grid.
        
        # Clear grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        files = [f for f, _ in self.icons] # We are effectively just using self.icons as a cache of available files + widgets? 
        # Re-read files probably easier or reuse logic.
        
        icons_dir = os.path.join(self.addon_path, "user_files/icons")
        all_files = sorted([f for f in os.listdir(icons_dir) if f.lower().endswith(".svg")])
        filtered_files = [f for f in all_files if text in f.lower()]
        
        row, col = 0, 0
        num_cols = 4
        
        for filename in filtered_files:
            container = QWidget()
            container.setFixedSize(70, 70)
            is_selected = (filename == self.current_filename)
            
            bg_normal = "transparent"
            bg_hover = "rgba(255,255,255,0.1)" if theme_manager.night_mode else "rgba(0,0,0,0.05)"
            bg_selected = "rgba(255,255,255,0.2)" if theme_manager.night_mode else "rgba(0,0,0,0.1)"
            border_selected = "#777" if theme_manager.night_mode else "#aaa"
            
            container.setStyleSheet(f"QWidget {{ background-color: {bg_selected if is_selected else bg_normal}; border-radius: 8px; border: {('1px solid ' + border_selected) if is_selected else '1px solid transparent'}; }} QWidget:hover {{ background-color: {bg_hover}; border: 1px solid {border_selected}; }}")
            
            layout = QVBoxLayout(container); layout.setContentsMargins(5, 5, 5, 5)
            preview = QLabel(); preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._render_svg_to_label(os.path.join(icons_dir, filename), preview)
            layout.addWidget(preview)
            
            btn = QPushButton(container)
            btn.setStyleSheet("background: transparent; border: none;")
            btn.setFixedSize(70, 70); btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, f=filename: self._select_icon(f))
            btn.move(0, 0)
            
            self.grid_layout.addWidget(container, row, col)
            col += 1
            if col >= num_cols: col = 0; row += 1

    def _select_icon(self, filename):
        self.iconSelected.emit(filename)
        self.close()

    def _add_icon_from_file(self):
        icons_dir = os.path.join(self.addon_path, "user_files/icons")
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Icon", os.path.expanduser("~"), "SVG Files (*.svg)")
        if filepath:
            filename = os.path.basename(filepath)
            dest_path = os.path.join(icons_dir, filename)
            if not os.path.exists(dest_path) or not os.path.samefile(filepath, dest_path):
                try: shutil.copy(filepath, dest_path)
                except Exception as e: QMessageBox.warning(self, "Error", f"Could not copy icon: {e}"); return
            
            self._load_icons() # Reload grid
            # self.search_input.setText("")

    def focusOutEvent(self, event):
        self.close()

class SearchResultWidget(QPushButton):
    def __init__(self, title, subtitle, target_page, parent=None):
        super().__init__(parent)
        self.target_page = target_page
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(70)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(4)
        
        # Determine colors based on theme
        if theme_manager.night_mode:
            bg_color = "#3a3a3a"
            text_color = "#e0e0e0"
            sub_text_color = "#aaaaaa"
            hover_bg = "#4a4a4a"
            border_color = "#3a3a3a"
        else:
            bg_color = "#dddddd"
            text_color = "#212121"
            sub_text_color = "#555555"
            hover_bg = "#e0e0e0"
            border_color = "#dddddd"

        # Resolve real accent color from theme
        current_theme = mw.col.conf.get("modern_menu_theme", "Tokyo Drift")
        accent_color = "#007bff"
        if current_theme in THEMES:
            mode = "dark" if theme_manager.night_mode else "light"
            accent_color = THEMES[current_theme][mode].get("--accent-color", accent_color)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {text_color}; background: transparent;")
        layout.addWidget(title_label)
        
        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setStyleSheet(f"font-size: 12px; color: {sub_text_color}; background: transparent;")
            layout.addWidget(sub_label)
            
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                border-radius: 12px;
                border: 2px solid {border_color};
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                border: 2px solid {accent_color};
            }}
        """)

class SettingsSearchPage(QWidget):
    page_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(20)

        # --- Search Bar ---
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search settings...")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border-radius: 15px;
                border: 1px solid #ccc;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #007bff;
            }
        """)
        self.search_bar.textChanged.connect(self._filter_cards)
        self.layout.addWidget(self.search_bar)

        # --- Scroll Area for Cards ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")
        
        self.content_wrapper = QWidget()
        self.wrapper_layout = QVBoxLayout(self.content_wrapper)
        self.wrapper_layout.setContentsMargins(0, 0, 0, 0)
        self.wrapper_layout.setSpacing(0)

        # Cards Container (List)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(10)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.wrapper_layout.addWidget(self.cards_container)

        # Results Container (List)
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setSpacing(10)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.wrapper_layout.addWidget(self.results_container)
        self.results_container.hide()
        
        self.scroll_area.setWidget(self.content_wrapper)
        self.layout.addWidget(self.scroll_area)

        self.cards = []
        self._create_cards()

    def _create_cards(self):
        # Format: (Title, Description, [Pages], [Keywords])
        sections = [
            ("Profile", "Manage your profile settings.", ["Profile"], 
             ["User Details", "Profile Picture", "Profile Bar Background"]),
            ("General", "Customize appearance, fonts, and themes.", ["Modes", "Fonts", "Palette", "Themes", "Gallery"], 
             ["Modes", "Gamification Mode", "Hide", "Pro", "Max", "Fonts", "Accent Color", "General Palette", "Boxes Color Effect", "Light Mode", "Dark Mode", "Official Themes", "Your Themes", "Gallery", "Colors Gallery", "Images Gallery"]),
            ("Menu", "Configure main menu and sidebar options.", ["Main menu", "Sidebar"], 
             ["Organize", "Main Background", "Heatmap", "Visibility", "Congratulations", "Sidebar Customization", "Organize Sidebar", "Sidebar Background", "Action Buttons", "Deck", "Icon Sizing"]),
            ("Study Pages", "Settings for Overviewer and Reviewer.", ["Overviewer", "Reviewer"], 
             ["Overviewer Background", "Overview Style", "Congratulations", "Reviewer Background", "Bottom Bar Background"]),
            ("Gamification", "Manage games and more.", ["Onigiri Games", "Restaurant Level", "Mr. Taiyaki Store", "Mochi Messages", "Focus Dango"], 
             ["Onigiri Games", "Restaurant Level", "Mochi Messages", "Focus Dango", "Custom Goals", "Notifications & Visibility", "Reset Progress", "Mr. Taiyaki Store", "Reset Coins", "Reset Purchases", "Settings", "Focus Dango Messages"])
        ]

        for title, desc, pages, settings in sections:
            card = self._create_card_widget(title, desc, pages)
            self.cards.append((card, title, desc, pages, settings))
            self.cards_layout.addWidget(card)
        
        self.cards_layout.addStretch()

    def _create_card_widget(self, title, desc, pages):
        card = QFrame()
        card.setObjectName("searchCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setFixedHeight(80)
        
        # Determine background color based on theme
        if theme_manager.night_mode:
            bg_color = "#3a3a3a"
            text_color = "#e0e0e0"
            desc_color = "#aaaaaa"
            hover_bg = "#4a4a4a"
            match_text_color = "#bbbbbb"
        else:
            bg_color = "#dddddd"
            text_color = "#212121"
            desc_color = "#555555"
            hover_bg = "#e0e0e0"
            match_text_color = "#555555"

        # Resolve real accent color from theme
        current_theme = mw.col.conf.get("modern_menu_theme", "Tokyo Drift")
        accent_color = "#007bff"
        if current_theme in THEMES:
            mode = "dark" if theme_manager.night_mode else "light"
            accent_color = THEMES[current_theme][mode].get("--accent-color", accent_color)

        card.setStyleSheet(f"""
            QFrame#searchCard {{
                background-color: {bg_color};
                border-radius: 12px;
                border: 2px solid transparent;
            }}
            QFrame#searchCard:hover {{
                background-color: {hover_bg};
                border: 2px solid {accent_color};
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(5)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {text_color}; background: transparent;")
        layout.addWidget(title_lbl)
        
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(f"font-size: 12px; color: {desc_color}; background: transparent;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # Container for matches (initially hidden)
        matches_container = QWidget()
        matches_layout = QVBoxLayout(matches_container)
        matches_layout.setContentsMargins(0, 5, 0, 0)
        matches_layout.setSpacing(2)
        matches_container.hide()
        layout.addWidget(matches_container)
        
        # Store references for dynamic updates
        card.title_label = title_lbl
        card.desc_label = desc_lbl
        card.matches_container = matches_container
        card.matches_layout = matches_layout
        card.match_text_color = match_text_color
        card.current_target_page = pages[0]
        
        # Use a method for the click handler to access the current target
        card.mousePressEvent = lambda event: self.page_requested.emit(card.current_target_page)
        
        return card

    def _filter_cards(self, text):
        text = text.lower().strip()
        
        if not text:
            self.results_container.hide()
            self.cards_container.show()
            
            # Clear results to free memory
            while self.results_layout.count():
                child = self.results_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            return

        self.cards_container.hide()
        self.results_container.show()
        
        # Clear previous results
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        results_found = False
        
        for card, title, desc, pages, settings in self.cards:
            # Check for Title/Desc match
            if text in title.lower() or text in desc.lower():
                # Add the main section as a result
                widget = SearchResultWidget(title, desc, pages[0])
                widget.clicked.connect(lambda _, p=pages[0]: self.page_requested.emit(p))
                self.results_layout.addWidget(widget)
                results_found = True

            # Check for Settings match
            for setting in settings:
                if text in setting.lower():
                    # Add the setting as a result
                    # Try to map setting to a specific page if possible, otherwise default to first page
                    target_page = pages[0]
                    # Simple heuristic: if setting name contains page name
                    for p in pages:
                        if p.lower() in setting.lower():
                            target_page = p
                            break
                    
                    widget = SearchResultWidget(setting, f"In {title}", target_page)
                    widget.clicked.connect(lambda _, p=target_page: self.page_requested.emit(p))
                    self.results_layout.addWidget(widget)
                    results_found = True

        if not results_found:
            no_results = QLabel("No results found.")
            no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_results.setStyleSheet("color: #888; font-size: 14px; margin-top: 20px;")
            self.results_layout.addWidget(no_results)
        
        self.results_layout.addStretch()

class DonationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Support Onigiri")
        self.setFixedWidth(300)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel("Choose a donation platform:")
        title.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # --- Theme Detection for Base Button Style ---
        is_dark = theme_manager.night_mode
        
        if is_dark:
            btn_bg = "#3a3a3a"
            btn_text = "white"
            btn_border = "#555"
        else:
            btn_bg = "#f0f0f0"
            btn_text = "black"
            btn_border = "#ccc"

        base_style = f"""
            QPushButton {{
                padding: 12px;
                border-radius: 20px;
                background-color: {btn_bg};
                color: {btn_text};
                border: 1px solid {btn_border};
                font-weight: bold;
                font-size: 13px;
            }}
        """

        # BMC Button
        self.bmc_button = QPushButton("Buy Me A Coffee")
        self.bmc_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bmc_button.setStyleSheet(base_style + """
            QPushButton:hover {
                background-color: #FFDD04;
                border: 1px solid #FFDD04;
                color: black;
            }
        """)
        self.bmc_button.clicked.connect(lambda: self._open_url("https://buymeacoffee.com/peacemonk"))
        layout.addWidget(self.bmc_button)

        # Ko-Fi Button
        self.kofi_button = QPushButton("Ko-Fi")
        self.kofi_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.kofi_button.setStyleSheet(base_style + """
            QPushButton:hover {
                background-color: #FF5A16;
                border: 1px solid #FF5A16;
                color: white;
            }
        """)
        self.kofi_button.clicked.connect(lambda: self._open_url("https://ko-fi.com/peacemonk"))
        layout.addWidget(self.kofi_button)

    def _open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))
        self.accept()

class SettingsDialog(QDialog):
    def __init__(self, parent=None, addon_path=None, initial_page_index=0):
        super().__init__(parent)
        self.addon_path = addon_path
        # <<< IMPORT/EXPORT THEMES >>>
        self.user_themes_path = os.path.join(self.addon_path, "user_files", "user_themes")
        os.makedirs(self.user_themes_path, exist_ok=True)
        self.block_card_click = False
        self.setWindowTitle("Onigiri Settings")
        self.setWindowTitle("Onigiri Settings")
        
        # --- Screen Proportional Sizing ---
        screen = mw.app.primaryScreen()
        if screen:
            available_geometry = screen.availableGeometry()
            screen_width = available_geometry.width()
            screen_height = available_geometry.height()
            
            # Calculate dimensions
            # Min: ~30% width, ~50% height (but at least 600px height if possible)
            min_w = int(screen_width * 0.3)
            min_h = int(screen_height * 0.5)
            
            # Default: ~45% width, ~60% height (Smaller default as requested)
            default_w = int(screen_width * 0.55)
            default_h = int(screen_height * 0.6)

            # Ensure reasonable minimums (don't go too small on very small screens, 
            # but respect the screen size if it's tiny)
            min_w = max(600, min(min_w, screen_width)) 
            min_h = max(600, min(min_h, screen_height))
            
            self.setMinimumWidth(min_w)
            self.setMinimumHeight(min_h)
            self.resize(default_w, default_h)
            
            # Set maximum height to avoid going off-screen
            self.setMaximumHeight(screen_height)
        else:
            # Fallback if screen detection fails
            self.setMinimumWidth(600)
            self.setMinimumHeight(600)
            self.resize(900, 700)
        
        self.current_config = config.get_config()

        # --- RESTORE WINDOW SIZE ---
        window_settings = self.current_config.get("window_settings", {})
        if window_settings:
            w = window_settings.get("width")
            h = window_settings.get("height")
            if w and h:
                # Basic validation
                w = max(self.minimumWidth(), w)
                h = max(self.minimumHeight(), h)
                if screen:
                     w = min(w, screen.availableGeometry().width())
                     h = min(h, screen.availableGeometry().height())
                self.resize(w, h)
        # ---------------------------
        self.custom_goal_cooldown_label = None

        achievements_conf = self.current_config.get("achievements")
        if not isinstance(achievements_conf, dict):
            achievements_conf = copy.deepcopy(config.DEFAULTS["achievements"])
            self.current_config["achievements"] = achievements_conf
        else:
            defaults = config.DEFAULTS["achievements"]
            for key, value in defaults.items():
                if isinstance(value, dict):
                    achievements_conf.setdefault(key, copy.deepcopy(value))
                else:
                    achievements_conf.setdefault(key, value)

        custom_goal_defaults = config.DEFAULTS["achievements"].get("custom_goals", {})
        custom_goals_conf = achievements_conf.setdefault("custom_goals", copy.deepcopy(custom_goal_defaults))
        custom_goals_conf.setdefault("last_modified_at", custom_goal_defaults.get("last_modified_at"))
        for goal_key, goal_defaults in custom_goal_defaults.items():
            if not isinstance(goal_defaults, dict):
                continue
            goal_conf = custom_goals_conf.setdefault(goal_key, {})
            for sub_key, default_value in goal_defaults.items():
                if isinstance(default_value, dict):
                    goal_conf.setdefault(sub_key, copy.deepcopy(default_value))
                else:
                    goal_conf.setdefault(sub_key, default_value)

        self.achievements_config = achievements_conf
        mochi_defaults = config.DEFAULTS.get("mochi_messages", {})
        self.mochi_messages_config = self.current_config.setdefault("mochi_messages", copy.deepcopy(mochi_defaults))
        for key, value in mochi_defaults.items():
            if key not in self.mochi_messages_config:
                self.mochi_messages_config[key] = copy.deepcopy(value)
        light_bg = mw.col.conf.get("modern_menu_bg_color_light")
        dark_bg = mw.col.conf.get("modern_menu_bg_color_dark")

        # --- ADD THIS LINE ---
        self.reviewer_bottom_bar_mode = self.current_config.get("onigiri_reviewer_bottom_bar_bg_mode", "match_reviewer_bg")
        # --- END OF ADDITION ---

        self.color_widgets = {"light": {}, "dark": {}}
        self.icon_assignment_widgets = []
        self.icon_size_widgets = {}
        self.galleries = {}
        self.tabs_loaded = {}

        conf = config.get_config()
        if theme_manager.night_mode:
            self.accent_color = conf.get("colors", {}).get("dark", {}).get("--accent-color", DEFAULTS["colors"]["dark"]["--accent-color"])
        else:
            self.accent_color = conf.get("colors", {}).get("light", {}).get("--accent-color", DEFAULTS["colors"]["light"]["--accent-color"])

        self.mochi_messages_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.mochi_messages_toggle.setChecked(bool(self.mochi_messages_config.get("enabled", False)))

        # Retrieve restaurant_level from top-level config
        restaurant_conf = self.current_config.get("restaurant_level", {})
        if not restaurant_conf:
            # Fallback for safety, though migration should have handled this
            restaurant_conf = self.achievements_config.get("restaurant_level", {})
        self.restaurant_level_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.restaurant_level_toggle.setChecked(bool(restaurant_conf.get("enabled", False)))

        self.restaurant_notifications_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.restaurant_notifications_toggle.setChecked(bool(restaurant_conf.get("notifications_enabled", True)))

        self.restaurant_bar_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.restaurant_bar_toggle.setChecked(bool(restaurant_conf.get("show_profile_bar_progress", True)))
        
        # self.restaurant_profile_toggle moved to Profile Page settings
        
        self.restaurant_reviewer_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.restaurant_reviewer_toggle.setChecked(bool(restaurant_conf.get("show_reviewer_header", True)))

        # Focus Dango toggle
        self.focus_dango_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        focus_dango_conf = self.achievements_config.get("focusDango", {})
        self.focus_dango_toggle.setChecked(bool(focus_dango_conf.get("enabled", False)))

        # Focus Dango messages editor
        dango_defaults = DEFAULTS["achievements"].get("focusDango", {})
        
        # --- START NEW CODE ---
        dango_messages_list = focus_dango_conf.get("messages") # Try new plural key first

        # If plural key doesn't exist, check for old singular "message" key
        if not dango_messages_list:
            old_message = focus_dango_conf.get("message")
            if isinstance(old_message, str) and old_message:
                dango_messages_list = [old_message] # Convert old string to list
            else:
                # Fallback to new default "messages" key
                dango_messages_list = copy.deepcopy(dango_defaults.get("messages", []))
                
                # If new default is also missing, check old default "message" key
                if not dango_messages_list:
                     old_default_message = dango_defaults.get("message")
                     if isinstance(old_default_message, str) and old_default_message:
                         dango_messages_list = [old_default_message]
        
        if not isinstance(dango_messages_list, list):
            dango_messages_list = [str(dango_messages_list)]
        
        # If all else fails and list is empty, provide a hardcoded default
        if not dango_messages_list:
            dango_messages_list = ["Don't give up!", "Stay focused!", "Almost there!"]

        dango_messages_text = "\n".join([str(item).strip() for item in dango_messages_list if str(item).strip()])
        self.focus_dango_message_editor = QPlainTextEdit(dango_messages_text)
        self.focus_dango_message_editor.setPlaceholderText("One message per line. Dango-san will pick one randomly.")
        self.focus_dango_message_editor.setMinimumHeight(80)
        # --- END NEW CODE ---

        self.mochi_interval_spinbox = QSpinBox()
        self.mochi_interval_spinbox.setMinimum(1)
        self.mochi_interval_spinbox.setMaximum(1000)
        self.mochi_interval_spinbox.setSingleStep(1)
        self.mochi_interval_spinbox.setSuffix(" cards")
        self.mochi_interval_spinbox.setValue(int(self.mochi_messages_config.get("cards_interval", 15) or 1))

        messages_list = self.mochi_messages_config.get("messages") or []
        if not isinstance(messages_list, list):
            messages_list = [str(messages_list)]
        messages_text = "\n".join([str(item).strip() for item in messages_list if str(item).strip()])
        self.mochi_messages_editor = QPlainTextEdit(messages_text)
        self.mochi_messages_editor.setPlaceholderText("One message per line. Mochi will pick from this list when cheering you on.")
        self.mochi_messages_editor.setMinimumHeight(120)

        self.mochi_messages_toggle.toggled.connect(self._on_mochi_messages_toggled)
        self._on_mochi_messages_toggled(self.mochi_messages_toggle.isChecked())

        custom_goals_conf = self.achievements_config.get("custom_goals", {})
        daily_conf = custom_goals_conf.get("daily", {})
        weekly_conf = custom_goals_conf.get("weekly", {})

        self.daily_goal_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.daily_goal_toggle.setChecked(bool(daily_conf.get("enabled", False)))

        self.daily_goal_spinbox = QSpinBox()
        self.daily_goal_spinbox.setMinimum(0)
        self.daily_goal_spinbox.setMaximum(5000)
        self.daily_goal_spinbox.setSingleStep(10)
        self.daily_goal_spinbox.setSuffix(" cards")
        self.daily_goal_spinbox.setValue(int(daily_conf.get("target", 100) or 0))
        self.daily_goal_spinbox.setToolTip("Cards to review each day to hit your personal goal.")
        self.daily_goal_spinbox.setEnabled(self.daily_goal_toggle.isChecked())
        self.daily_goal_toggle.toggled.connect(self.daily_goal_spinbox.setEnabled)

        self.weekly_goal_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.weekly_goal_toggle.setChecked(bool(weekly_conf.get("enabled", False)))

        self.weekly_goal_spinbox = QSpinBox()
        self.weekly_goal_spinbox.setMinimum(0)
        self.weekly_goal_spinbox.setMaximum(50000)
        self.weekly_goal_spinbox.setSingleStep(50)
        self.weekly_goal_spinbox.setSuffix(" cards")
        self.weekly_goal_spinbox.setValue(int(weekly_conf.get("target", 700) or 0))
        self.weekly_goal_spinbox.setToolTip("Cards to review across the current calendar week.")
        self.weekly_goal_spinbox.setEnabled(self.weekly_goal_toggle.isChecked())
        self.weekly_goal_toggle.toggled.connect(self.weekly_goal_spinbox.setEnabled)

        # Initialize widgets that have been moved so they are always available for saving
        self.hide_native_header_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_native_header_checkbox.setChecked(self.current_config.get("hideNativeHeaderAndBottomBar", True))
        
        self.max_hide_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.max_hide_checkbox.setChecked(self.current_config.get("maxHide", False))
        self.max_hide_checkbox.setToolTip("Hides the bottom toolbar on the reviewer screen for the most immersive experience.")

        self.flow_mode_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.flow_mode_checkbox.setChecked(self.current_config.get("flowMode", False))
        self.flow_mode_checkbox.setToolTip("Enables 'Flow Mode' which hides the bottom toolbar on the reviewer screen until you hover over it.")

        self.gamification_mode_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.gamification_mode_checkbox.setChecked(self.current_config.get("gamificationMode", False))
        self.gamification_mode_checkbox.setToolTip("Enable mini-games like Restaurant Level, Mochi Messages, and Focus Dango.")

        self.full_hide_mode_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.full_hide_mode_checkbox.setChecked(self.current_config.get("fullHideMode", False))
        self.full_hide_mode_checkbox.setToolTip("Hides the top menu bar (File, Edit, View, Tools, Help) on Windows and Linux for the most immersive experience.")

        self.hide_native_header_checkbox.toggled.connect(self._on_hide_toggled)
        self.flow_mode_checkbox.toggled.connect(self._on_flow_toggled)
        self.max_hide_checkbox.toggled.connect(self._on_max_hide_toggled)
        self.full_hide_mode_checkbox.toggled.connect(self._on_full_hide_toggled)

        self.stats_title_input = QLineEdit(mw.col.conf.get("modern_menu_statsTitle", DEFAULTS["statsTitle"]))

        self.hide_welcome_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_welcome_checkbox.setChecked(self.current_config.get("hideWelcomeMessage", False))

        self.hide_deck_counts_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_deck_counts_checkbox.setChecked(self.current_config.get("hideDeckCounts", True))

        self.hide_all_deck_counts_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_all_deck_counts_checkbox.setChecked(self.current_config.get("hideAllDeckCounts", False))

        self.study_now_input = QLineEdit(mw.col.conf.get("modern_menu_studyNowText", DEFAULTS["studyNowText"]))
        self.show_congrats_profile_bar_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.show_congrats_profile_bar_checkbox.setChecked(self.current_config.get("showCongratsProfileBar", True))
        self.congrats_message_input = QLineEdit(self.current_config.get("congratsMessage", DEFAULTS["congratsMessage"]))

        self.action_button_icon_widgets = []
        self.retention_star_widget = None

        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0)
        
        content_area_layout = QHBoxLayout()
        content_area_layout.setSpacing(5)
        content_area_layout.setContentsMargins(0, 0, 0, 0)
        
        # This is the new wrapper that provides the margin/spacing
        # This is the wrapper that provides margin and has a fixed width
        sidebar_wrapper = QWidget()
        sidebar_wrapper.setFixedWidth(215) # 185px sidebar + 15px left margin + 15px for scrollbar
        sidebar_wrapper_layout = QVBoxLayout(sidebar_wrapper)
        sidebar_wrapper_layout.setContentsMargins(15, 15, 15, 15) # 15px margins, right margin for scrollbar

        # This is the actual visible sidebar widget, which will be styled
        sidebar_widget = QWidget()
        sidebar_widget.setObjectName("sidebarContainer") # Name for the stylesheet
        # Set max width to available space: 200px wrapper - 15px left margin = 185px
        sidebar_widget.setMaximumWidth(185)

        # --- Search Button (Separated) ---
        self.search_button = QPushButton("Search")
        self.search_button.setCheckable(True)
        self.search_button.setObjectName("searchSidebarButton")
        self.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_button.clicked.connect(lambda: self.navigate_to_page("Search"))
        sidebar_wrapper_layout.addWidget(self.search_button)

        # Add spacing between Search button and the rest of the sidebar
        sidebar_wrapper_layout.addSpacing(10)

        # --- Scroll Area for Sidebar Content ---
        self.sidebar_scroll_area = QScrollArea()
        self.sidebar_scroll_area.setWidgetResizable(True)
        self.sidebar_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Style the scroll area to be transparent so the sidebar container style shows through if needed
        # Removed the child widget transparency rule to fix the sidebar background color issue
        self.sidebar_scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
        """)
        
        self.sidebar_scroll_area.setWidget(sidebar_widget)
        
        # Add the scroll area inside the wrapper instead of the raw widget
        sidebar_wrapper_layout.addWidget(self.sidebar_scroll_area)

        # The sidebar's internal content (buttons, etc.) goes into this layout
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(10, 20, 10, 10) # Balanced margins to center elements
        sidebar_layout.setSpacing(15)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentStack")
        self.content_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Add the final widgets to the main layout
        content_area_layout.addWidget(sidebar_wrapper)
        content_area_layout.addWidget(self.content_stack)
        content_area_layout.addSpacing(0) 

        self.pages = {
            "Search": self.create_search_page,
            "Profile": self.create_profile_tab,
            "Modes": self.create_hide_modes_page,

            "Fonts": self.create_fonts_page,
            "Themes": self.create_themes_page, 
            "Main menu": self.create_main_menu_page,
            "Sidebar": self.create_sidebar_page,
            "Overviewer": self.create_overviews_page,
            "Reviewer": self.create_reviewer_tab,
            "Onigiri Games": self.create_onigiri_games_page,
            "Restaurant Level": self.create_restaurant_level_page,
            "Mochi Messages": self.create_mochi_messages_page,
            "Focus Dango": self.create_focus_dango_page,
            "Mr. Taiyaki Store": self.create_mr_taiyaki_store_page,
            "Palette": self.create_colors_page,
            "Gallery": self.create_gallery_page,
        }
        self.page_order = list(self.pages.keys())

        for name in self.page_order:
            self.content_stack.addWidget(QWidget())

        user_name = self.current_config.get("userName", DEFAULTS["userName"])
        pic_filename = mw.col.conf.get("modern_menu_profile_picture", "")
        pic_path = os.path.join(self.addon_path, "user_files", "profile", pic_filename) if pic_filename else ""
        bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "accent")
        is_dark = theme_manager.night_mode
        bg_color = mw.col.conf.get(f"modern_menu_profile_bg_color_{'dark' if is_dark else 'light'}", "#555" if is_dark else "#EEE")
        bg_image_filename = mw.col.conf.get("modern_menu_profile_bg_image", "")
        bg_image_path = os.path.join(self.addon_path, "user_files", "profile_bg", bg_image_filename) if bg_image_filename else ""
        bg_config = {'color': bg_color, 'image': bg_image_path}
        


        self.profile_bar = ProfileBarWidget(user_name, pic_path, bg_mode, bg_config, self.accent_color, self)
        sidebar_layout.addWidget(self.profile_bar)



        self.sidebar_buttons = {}
        self.sidebar_buttons["Search"] = self.search_button
        self.general_toggle_widget = None

        self.sidebar_button_group = QButtonGroup()
        self.sidebar_button_group.setExclusive(True)

        general_items = ["Modes", "Fonts", "Palette", "Themes", "Gallery"]
        self.general_toggle_widget = SidebarToggleButton("General", general_items)
        self.general_toggle_widget.page_selected.connect(self.navigate_to_page)
        sidebar_layout.addWidget(self.general_toggle_widget)

        menu_items = ["Main menu", "Sidebar"]
        self.menu_toggle_widget = SidebarToggleButton("Menu", menu_items)
        self.menu_toggle_widget.page_selected.connect(self.navigate_to_page)
        sidebar_layout.addWidget(self.menu_toggle_widget)

        study_zone_items = ["Overviewer", "Reviewer"]
        self.study_zone_toggle_widget = SidebarToggleButton("Study Pages", study_zone_items)
        self.study_zone_toggle_widget.page_selected.connect(self.navigate_to_page)
        sidebar_layout.addWidget(self.study_zone_toggle_widget)

        # Gamification section with all items
        gamification_items = ["Onigiri Games", "Restaurant Level", "Mr. Taiyaki Store", "Mochi Messages", "Focus Dango"]
        self.gamification_toggle_widget = SidebarToggleButton("Gamification", gamification_items)
        self.gamification_toggle_widget.page_selected.connect(self.navigate_to_page)
        sidebar_layout.addWidget(self.gamification_toggle_widget)

        # Connect toggle buttons to enable accordion behavior
        self.general_toggle_widget.toggle_button.toggled.connect(
            lambda checked: self._on_section_toggled(self.general_toggle_widget, checked)
        )
        self.menu_toggle_widget.toggle_button.toggled.connect(
            lambda checked: self._on_section_toggled(self.menu_toggle_widget, checked)
        )
        self.study_zone_toggle_widget.toggle_button.toggled.connect(
            lambda checked: self._on_section_toggled(self.study_zone_toggle_widget, checked)
        )
        self.gamification_toggle_widget.toggle_button.toggled.connect(
            lambda checked: self._on_section_toggled(self.gamification_toggle_widget, checked)
        )

        self.donate_button = QPushButton("Donate")
        self.donate_button.clicked.connect(self._open_donate_link)
        self.report_bugs_button = QPushButton("Report Bugs")
        self.report_bugs_button.clicked.connect(self._open_bugs_link)

        self.save_button = QPushButton("Save"); self.save_button.clicked.connect(self.save_settings)
        self.cancel_button = QPushButton("Cancel"); self.cancel_button.clicked.connect(self.reject)
        
        sidebar_button_layout = QVBoxLayout()
        sidebar_button_layout.setSpacing(5)
        sidebar_button_layout.setContentsMargins(0, 5, 0, 0)

        sidebar_button_layout.addWidget(self.donate_button)
        sidebar_button_layout.addWidget(self.report_bugs_button)
        sidebar_button_layout.addWidget(self.save_button)
        sidebar_button_layout.addWidget(self.cancel_button)

        sidebar_layout.addStretch()
        sidebar_layout.addLayout(sidebar_button_layout)

        main_layout.addLayout(content_area_layout)
        self.apply_stylesheet()
        
        self.profile_bar.clicked.connect(self.show_profile_page)

        self.navigate_to_page("Search")
    
    def _open_donate_link(self):
        dialog = DonationDialog(self)
        dialog.exec()

    def _open_bugs_link(self):
        QDesktopServices.openUrl(QUrl("https://github.com/thepeacemonk/Onigiri"))

    def create_search_page(self):
        page = SettingsSearchPage(self)
        page.page_requested.connect(self.navigate_to_page)
        return page

    def _create_font_selector_group(self, title, config_key):
        """Helper to create a font selection grid for a given config key."""
        group = SectionGroup(title, self, border=False)
        
        # --- NEW: Font Control Row (Size) ---
        control_widget = QWidget()
        control_layout = QHBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 0, 5) # Slight margin
        
        size_label = QLabel("Font Size:")
        size_label.setStyleSheet("color: var(--fg-subtle);")
        
        size_spinbox = QSpinBox()
        size_spinbox.setRange(8, 72)
        size_spinbox.setSuffix("px")
        size_spinbox.setFixedWidth(80)
        
        # Load saved size or default
        if config_key == "main":
            default_size = 14
        elif config_key == "subtle":
            default_size = 20
        else: # small_title
            default_size = 15
        # Check col.conf first
        saved_size = mw.col.conf.get(f"onigiri_font_size_{config_key}", default_size)
        size_spinbox.setValue(int(saved_size))
        
        # Save reference
        setattr(self, f"font_size_{config_key}", size_spinbox)
        
        # Restore Button
        restore_btn = QPushButton("Restore Default")
        restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        restore_btn.setToolTip(f"Reset to {default_size}px")
        # Capture default_size and spinbox in lambda
        restore_btn.clicked.connect(lambda _, s=size_spinbox, d=default_size: s.setValue(d))
        
        control_layout.addWidget(size_label)
        control_layout.addWidget(size_spinbox)
        control_layout.addWidget(restore_btn)
        control_layout.addStretch()
        
        group.add_widget(control_widget)
        # ------------------------------------
        
        container_widget = QWidget()
        container_layout = QHBoxLayout(container_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)

        grid_layout = QGridLayout(); grid_layout.setSpacing(15)
        
        # <<< Store grid_layout and config_key for later refresh >>>
        if not hasattr(self, 'font_grids'):
            self.font_grids = {}
        self.font_grids[config_key] = grid_layout
        
        self._populate_font_grid(config_key)
        # <<< END MODIFICATION >>>

        container_layout.addLayout(grid_layout)
        container_layout.addStretch()

        group.add_widget(container_widget)
        
        return group
    
    def _populate_font_grid(self, config_key):
        grid_layout = self.font_grids[config_key]
        
        # Clear existing widgets
        while grid_layout.count():
            child = grid_layout.takeAt(0)
            if widget := child.widget():
                widget.deleteLater()
                
        all_fonts = get_all_fonts(self.addon_path)
        
        font_cards = []
        # Separate system and user fonts for ordering
        system_fonts = {k: v for k, v in all_fonts.items() if not v.get("user")}
        user_fonts = {k: v for k, v in all_fonts.items() if v.get("user")}
        
        font_order = ["instrument_serif", "nunito", "montserrat", "space_mono"]
        
        row, col, num_cols = 0, 0, 2

        # Add the "System" font card first, spanning the full width
        if "system" in system_fonts:
            system_card = FontCardWidget("system", self.accent_color, self, is_system_card=True)
            font_cards.append(system_card)
            grid_layout.addWidget(system_card, row, 0, 1, num_cols) # Add to grid, spanning 2 columns
            row += 1 # Move to the next row

        # <<< START MODIFICATION >>>
        # Move the "Add Your Own Font" button to be directly under the "System" button
        add_button = QPushButton("Add Your Own Font")
        add_button.setFixedHeight(50) # Match the height of the "System" button
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.clicked.connect(self._add_user_font)
        
        # Style it to look like a solid, non-dashed card
        if theme_manager.night_mode:
            add_button.setStyleSheet(f"""
                QPushButton {{ 
                    background-color: #3a3a3a; 
                    border: 2px solid #4a4a4a; 
                    border-radius: px; 
                    color: #e0e0e0; 
                }} 
                QPushButton:hover {{ 
                    border-color: #5a5a5a; 
                }}
            """)
        else:
            add_button.setStyleSheet(f"""
                QPushButton {{ 
                    background-color: #e9e9e9; 
                    border: 2px solid #e0e0e0; 
                    border-radius: 12px; 
                    color: #212121; 
                }} 
                QPushButton:hover {{ 
                    border-color: #d0d0d0; 
                }}
            """)
        
        grid_layout.addWidget(add_button, row, 0, 1, num_cols) # Add to grid, spanning 2 columns
        row += 1 # Move to the next row for the regular fonts
        # <<< END MODIFICATION >>>

        def add_card_to_grid(font_key):
            nonlocal row, col
            delete_icon = self._create_delete_icon()
            card = FontCardWidget(font_key, self.accent_color, self, delete_icon=delete_icon)
            if all_fonts[font_key].get("user"):
                card.delete_requested.connect(lambda key=font_key: self._delete_user_font(key))
            font_cards.append(card)
            grid_layout.addWidget(card, row, col)
            col += 1
            if col >= num_cols:
                col = 0
                row += 1

        # Add other system fonts in specified order
        for key in font_order:
            if key in system_fonts:
                add_card_to_grid(key)
        
        # Add user-installed fonts
        for key in sorted(user_fonts.keys()):
            add_card_to_grid(key)
            
        # <<< MODIFICATION: The old "Add Yours" button code has been removed from here >>>
            
        # Set the checked state
        saved_font = mw.col.conf.get(f"onigiri_font_{config_key}", "system")
        for card in font_cards:
            if card.font_key == saved_font:
                card.setChecked(True)
                break
        
        setattr(self, f"font_cards_{config_key}", font_cards)
        
    # <<< START NEW METHODS >>>
    def _add_user_font(self):
        user_fonts_dir = os.path.join(self.addon_path, "user_files", "fonts")
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Font File", "", "Font Files (*.ttf *.otf *.woff *.woff2)")
        
        if not filepath:
            return
            
        filename = os.path.basename(filepath)
        dest_path = os.path.join(user_fonts_dir, filename)
        
        try:
            shutil.copy(filepath, dest_path)
            showInfo(f"Font '{filename}' added successfully.")
            # Refresh both font grids
            self._populate_font_grid("main")
            self._populate_font_grid("subtle")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not copy font file: {e}")

    def _delete_user_font(self, font_key):
        reply = QMessageBox.question(self, "Confirm Delete", 
            f"Are you sure you want to delete the font '{font_key}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            
        if reply == QMessageBox.StandardButton.Yes:
            font_path = os.path.join(self.addon_path, "user_files", "fonts", font_key)
            try:
                if os.path.exists(font_path):
                    os.remove(font_path)
                    
                    # If the deleted font was selected, revert to system
                    for key in ["main", "subtle"]:
                        if mw.col.conf.get(f"onigiri_font_{key}") == font_key:
                            mw.col.conf[f"onigiri_font_{key}"] = "system"
                    
                    showInfo(f"Font '{font_key}' deleted.")
                    self._populate_font_grid("main")
                    self._populate_font_grid("subtle")
                else:
                    QMessageBox.warning(self, "Error", "Font file not found.")
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Could not delete font file: {e}")
    # <<< END NEW METHODS >>>

    def create_fonts_page(self):
        page, layout = self._create_scrollable_page()
    
        fonts_container = QWidget()
        fonts_layout = FlowLayout(fonts_container, spacing=20)
        fonts_layout.setContentsMargins(0, 0, 0, 0)
        
        text_group = self._create_font_selector_group("Text", "main")
        subtle_group = self._create_font_selector_group("Titles", "subtle")
        small_title_group = self._create_font_selector_group("Small Titles", "small_title")
        
        fonts_layout.addWidget(text_group)
        fonts_layout.addWidget(subtle_group)
        fonts_layout.addWidget(small_title_group)
        
        layout.addWidget(fonts_container)
        layout.addStretch()

        sections = {}
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections)

        return page


    def _save_fonts_settings(self):
        for card in self.font_cards_main:
            if card.isChecked():
                mw.col.conf["onigiri_font_main"] = card.font_key
                break
        for card in self.font_cards_subtle:
            if card.isChecked():
                mw.col.conf["onigiri_font_subtle"] = card.font_key
                break
        for card in getattr(self, "font_cards_small_title", []):
            if card.isChecked():
                mw.col.conf["onigiri_font_small_title"] = card.font_key
                break
        
        # Save Font Sizes
        if hasattr(self, "font_size_main"):
            mw.col.conf["onigiri_font_size_main"] = self.font_size_main.value()
        if hasattr(self, "font_size_subtle"):
            mw.col.conf["onigiri_font_size_subtle"] = self.font_size_subtle.value()
        if hasattr(self, "font_size_small_title"):
            mw.col.conf["onigiri_font_size_small_title"] = self.font_size_small_title.value()
    def closeEvent(self, event):
        # --- SAVE WINDOW SIZE ---
        try:
            if not self.isMaximized() and not self.isFullScreen():
                window_settings = {
                    "width": self.width(),
                    "height": self.height()
                }
                self.current_config["window_settings"] = window_settings
                config.write_config(self.current_config)
        except Exception as e:
            print(f"Error saving window settings: {e}")
        # ------------------------

        for gallery in self.galleries.values():
            if worker := gallery.get('worker'):
                worker.cancel()
            if thread := gallery.get('thread'):
                try:
                    if thread.isRunning():
                        thread.quit()
                        thread.wait(100)
                except RuntimeError:
                    pass
        super().closeEvent(event)
    
    def show_profile_page(self):
        if btn := self.sidebar_button_group.checkedButton():
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
        self.general_toggle_widget.deselect_all()
        self.menu_toggle_widget.deselect_all()
        self.study_zone_toggle_widget.deselect_all()
        self.gamification_toggle_widget.deselect_all()
        
        profile_index = self.page_order.index("Profile")
        
        if not self.tabs_loaded.get(profile_index):
            create_func = self.pages["Profile"]
            new_widget = create_func()
            
            old_widget = self.content_stack.widget(profile_index)
            self.content_stack.removeWidget(old_widget)
            self.content_stack.insertWidget(profile_index, new_widget)
            old_widget.deleteLater()
            self.tabs_loaded[profile_index] = True
            
        self.content_stack.setCurrentIndex(profile_index)

    def navigate_to_page(self, page_name):
        if not page_name: 
            return

        if page_name in self.sidebar_buttons:
            self.sidebar_buttons[page_name].setChecked(True)
            self.general_toggle_widget.deselect_all()
            self.menu_toggle_widget.deselect_all()
            self.study_zone_toggle_widget.deselect_all()
            self.gamification_toggle_widget.deselect_all()
        elif self.general_toggle_widget.select_page(page_name):
            if btn := self.sidebar_button_group.checkedButton():
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
            self.menu_toggle_widget.deselect_all()
            self.study_zone_toggle_widget.deselect_all()
            self.gamification_toggle_widget.deselect_all()
        elif self.menu_toggle_widget.select_page(page_name):
            if btn := self.sidebar_button_group.checkedButton():
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
            self.general_toggle_widget.deselect_all()
            self.study_zone_toggle_widget.deselect_all()
            self.gamification_toggle_widget.deselect_all()
        elif self.study_zone_toggle_widget.select_page(page_name):
            if btn := self.sidebar_button_group.checkedButton():
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
            self.general_toggle_widget.deselect_all()
            self.menu_toggle_widget.deselect_all()
            self.gamification_toggle_widget.deselect_all()
        elif self.gamification_toggle_widget.select_page(page_name):
            if btn := self.sidebar_button_group.checkedButton():
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
            self.general_toggle_widget.deselect_all()
            self.menu_toggle_widget.deselect_all()
            self.study_zone_toggle_widget.deselect_all()

        if page_name not in self.page_order:
            return
            
        stack_index = self.page_order.index(page_name)
        
        if not self.tabs_loaded.get(stack_index):
            create_func = self.pages[page_name]
            new_widget = create_func()
            
            old_widget = self.content_stack.widget(stack_index)
            self.content_stack.removeWidget(old_widget)
            self.content_stack.insertWidget(stack_index, new_widget)
            old_widget.deleteLater()
            self.tabs_loaded[stack_index] = True
        
        self.content_stack.setCurrentIndex(stack_index)
    
    def _on_section_toggled(self, toggled_widget, checked):
        """Handle accordion behavior: close other sections when one is opened."""
        if not checked:
            # If the section is being closed, don't do anything special
            return
        
        # Close all other sections when this one is opened
        all_toggles = [
            self.general_toggle_widget,
            self.menu_toggle_widget,
            self.study_zone_toggle_widget,
            self.gamification_toggle_widget,
        ]
        for toggle in all_toggles:
            if toggle is not toggled_widget and toggle.is_open:
                toggle.deselect_all()
        
    def _create_inner_group(self, title):
        container = QFrame()
        container.setObjectName("innerGroup")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 20px;")
        main_layout.addWidget(title_label)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 5, 0, 0)
        main_layout.addWidget(content_widget)

        return container, content_layout

    def apply_stylesheet(self):
        conf = config.get_config()
        if theme_manager.night_mode:
            bg, fg, border, input_bg, button_bg, sidebar_bg = "#2c2c2c", "#e0e0e0", "#4a4a4a", "#3a3a3a", "#4a4a4a", "#3a3a3a"
            separator_color, secondary_button_bg, secondary_button_fg = "#444444", "#555", "#e0e0e0"
            accent_color = conf.get("colors", {}).get("dark", {}).get("--accent-color", DEFAULTS["colors"]["dark"]["--accent-color"])
        else:
            bg, fg, border, input_bg, button_bg, sidebar_bg = "#f3f3f3", "#212121", "#e0e0e0", "#f5f5f5", "#f0f0f0", "#dddddd"
            separator_color, secondary_button_bg, secondary_button_fg = "#e0e0e0", "#c9c9c9", "#ffffff"
            accent_color = conf.get("colors", {}).get("light", {}).get("--accent-color", DEFAULTS["colors"]["light"]["--accent-color"])

        mode_key = "dark" if theme_manager.night_mode else "light"
        fg_subtle = conf.get("colors", {}).get(mode_key, {}).get("--fg-subtle", DEFAULTS["colors"][mode_key]["--fg-subtle"])

        hero_gradient_top = "#343a40" if theme_manager.night_mode else "#d9dee7"
        sidebar_selected_bg, primary_button_bg = accent_color, accent_color

        # Icons for spinbox
        up_icon_path = os.path.join(self.addon_path, "system_files", "system_icons", "up.svg").replace("\\", "/")
        down_icon_path = os.path.join(self.addon_path, "system_files", "system_icons", "down.svg").replace("\\", "/")

        self.setStyleSheet(f"""
            QFrame#MenuSeparator {{
                background-color: {border};
            }}

            QDialog {{ background-color: {bg}; color: {fg}; }}
            
            /* This rule gives the page a solid background to prevent flickering */
            #pageContainer {{
                background-color: {bg};
            }}

            #sidebarContainer {{
                background-color: {sidebar_bg};
                border-radius: 25px;
            }}
            #sidebarContainer QPushButton {{
                padding: 12px;
                border-radius: 20px;
                text-align: left;
                border: none;
                background-color: transparent;
            }}
            #sidebarContainer QPushButton:checked {{
                background-color: {sidebar_selected_bg};
                color: white;
            }}
            QPushButton#searchSidebarButton {{
                padding: 12px;
                border-radius: 20px;
                background-color: {sidebar_bg};
                color: {fg};
                text-align: center;
                margin-bottom: 0px; /* Spacing handled by layout now */
                border: none;
            }}
            QPushButton#searchSidebarButton:hover {{
                background-color: {border}; /* Slightly lighter/darker on hover */
            }}
            QPushButton#searchSidebarButton:checked {{
                background-color: {sidebar_bg};
                color: {fg};
            }}
            QPushButton#searchSidebarButton:pressed {{
                color: {sidebar_selected_bg};
            }}
            #sidebarContainer QPushButton#subItemButton {{
                background-color: transparent;
                color: {fg};
            }}
            #sidebarContainer QPushButton#subItemButton:checked {{
                background-color: transparent;
                font-weight: bold;
                color: {sidebar_selected_bg};
            }}
            #innerGroup {{ border: 1px solid {border}; border-radius: 12px; margin-top: 5px; }}
            QGroupBox {{ border-radius: 16px; margin-top: 8px; padding: 0px; }}
            
            QLabel, QRadioButton {{ color: {fg}; }}
            QRadioButton::indicator {{
                border: 2px solid {border};
                background-color: transparent;
                width: 16px;
                height: 16px;
                border-radius: 10px;
            }}
            QRadioButton::indicator:checked {{
                border: 2px solid {accent_color};
                background-color: {accent_color};
                image: url();
            }}
            QLineEdit, QSpinBox {{ background-color: {input_bg}; color: {fg}; border: 1px solid {border}; border-radius: 4px; padding: 5px; }}

            QPushButton {{ background-color: {button_bg}; color: {fg}; border: 1px solid {border}; padding: 8px 12px; border-radius: 4px; }}
            QPushButton:pressed {{ background-color: {border}; }}
        
            QFrame[frameShape="4"] {{ border: 1px solid {separator_color}; }}
            QTabBar::tab {{ background: transparent; border: none; padding: 8px 12px; border-radius: 4px; margin-right: 2px; }}
            QTabBar::tab:selected {{ background: {accent_color}; color: white; }}
            QTabBar::tab:!selected:hover {{ background: {border}; }}
            QTabWidget::pane {{ background-color: transparent; border: none; }}
            QTabBar {{ qproperty-drawBase: 0; }}
            QScrollBar:vertical {{ border: none; background: {bg}; width: 12px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {border}; min-height: 20px; border-radius: 6px; margin: 2px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                height: 0px;
                width: 0px;
                background: none;
                border: none;
            }}
            QScrollBar:horizontal {{ border: none; background: {bg}; height: 12px; margin: 0; }}
            QScrollBar::handle:horizontal {{ background: {border}; min-width: 20px; border-radius: 6px; margin: 2px; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                height: 0px;
                width: 0px;
                background: none;
                border: none;
            }}

            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid {border};
                image: url({up_icon_path});
                padding: 2px;
            }}
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left: 1px solid {border};
                image: url({down_icon_path});
                padding: 2px;
            }}
            #colorPill {{ background-color: {input_bg}; border: 1px solid {border}; border-radius: 18px; 
            }}
            QFrame#themeCard {{
                background-color: {input_bg};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 10px;
            }}
            QFrame#themeCard:hover {{
                border-color: {accent_color};
            }}

            /* <<< START NEW CODE >>> */
            QFrame#hideModeCard {{
                background-color: {sidebar_bg};
                border: 1px solid {border};
                border-radius: 16px;
                padding: 20px;
            }}
            QLabel#hideModeTitleLabel {{
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 5px;
            }}
            QLabel#hideModeDescLabel {{
                color: {fg};
                font-size: 12px;
            }}
            /* <<< END NEW CODE >>> */

            /* <<< START NEW CODE >>> */

            QGroupBox#LayoutGroup {{
                border: 1px solid {border};
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px 10px 10px 10px;
            }}
            QGroupBox#LayoutGroup::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                /* Use page BG to "cut out" the border */
                background-color: {bg};
                /* Make title visible again, overriding default */
                color: {fg};
            }}
            #DraggableItem {{
                background-color: {button_bg};
                border: 1px solid {border};
                border-radius: 4px;
                color: {fg};
                font-weight: 500;
                text-align: center;
            }}
            #DropZone {{
                background-color: {input_bg};
                border-radius: 6px;
                padding: 5px;
            }}
            #Shelf {{
                background-color: transparent;
                border: 2px dashed {border};
                border-radius: 10px;
            }}
            /* <<< START NEW CODE >>> */
            #Shelf[is_highlighted="true"] {{
                background-color: rgba(0, 123, 255, 0.3);
                border: 2px solid {accent_color};
            }}
            /* <<< START NEW CODE >>> */
            #MenuBackground {{
                background-color: {input_bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QPushButton#MenuButton {{
                background-color: transparent;
                color: {fg};
                border: none;
                padding: 8px 20px;
                text-align: center;
                border-radius: 6px;
            }}
            QPushButton#MenuButton:hover {{
                background-color: {border};
            }}
            QPushButton#MenuButton:checked {{
                background-color: {accent_color};
                color: white;
            }}
                border: 1px solid {border};
                border-radius: 4px;
            }}
        """)
        self.save_button.setStyleSheet(
            f"QPushButton{{background-color:{accent_color};color:white;border:none;padding:10px;border-radius:12px}}"
            f"QPushButton:pressed{{background-color:{border};color:white}}"
        )
        self.cancel_button.setStyleSheet(
            f"QPushButton{{background-color:{secondary_button_bg};color:{secondary_button_fg};border:none;padding:10px;border-radius:12px}}"
            f"QPushButton:pressed{{background-color:{border}}}"
        )
    
    def _create_toggle_row(self, toggle_widget, text_label, style_sheet=""):
        row = QWidget()
        if style_sheet:
            row.setStyleSheet(f"QWidget {{ {style_sheet} }}")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(QLabel(text_label))
        layout.addStretch()
        layout.addWidget(toggle_widget)
        return row

    def _create_goal_setting_row(self, title, description, spinbox, toggle_widget):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 600;")
        text_layout.addWidget(title_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #6b6b6b; font-size: 11px;")
            text_layout.addWidget(desc_label)

        text_layout.addStretch()
        layout.addWidget(text_container, 1)

        spinbox.setMaximumWidth(120)
        layout.addWidget(spinbox)
        layout.addSpacing(8)
        layout.addWidget(toggle_widget)

        return row

    def create_under_construction_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel("Under Construction")
        label.setStyleSheet("font-size: 20px; color: #888;")
        layout.addWidget(label)
        return page

    def _get_hook_name(self, hook):
        """Creates a unique, stable identifier for a hook function."""
        # Defer to the implementation in patcher.py to ensure consistency.
        from . import patcher
        return patcher._get_hook_name(hook)

    def _get_external_hooks(self):
        """
        Calls the hook-finding logic from patcher.py, which is known to work,
        to prevent issues from code duplication or timing.
        """
        from . import patcher
        # patcher._get_external_hooks() returns a list of FUNCTION objects.
        external_hook_functions = patcher._get_external_hooks()

        # We need a list of STRING identifiers for the settings dialog.
        return [patcher._get_hook_name(hook) for hook in external_hook_functions]

    # =================================================================
    # START: Main Menu Layout Editor Widgets (v5, Final Usability Fix)
    # =================================================================

    class CustomMenu(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            # Make it a frameless pop-up window
            self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

            # Main layout
            self.layout = QVBoxLayout(self)
            self.layout.setContentsMargins(0, 0, 0, 0)

            # Background frame that we can style
            self.background_frame = QFrame(self)
            self.background_frame.setObjectName("MenuBackground")
            self.layout.addWidget(self.background_frame)

            # Layout for the buttons inside the frame
            self.content_layout = QVBoxLayout(self.background_frame)
            self.content_layout.setContentsMargins(5, 5, 5, 5)
            self.content_layout.setSpacing(4)

        def add_action_button(self, text, data, group, is_checked):
            button = QPushButton(text)
            button.setObjectName("MenuButton")
            button.setCheckable(True)
            button.setChecked(is_checked)
            group.addButton(button)
            
            # Store data in the button itself
            button.setProperty("action_data", data)
            
            self.content_layout.addWidget(button)
            return button

        def add_separator(self):
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setObjectName("MenuSeparator")
            # Give it a fixed height and some margin
            sep.setFixedHeight(1)
            self.content_layout.addSpacing(4)
            self.content_layout.addWidget(sep)
            self.content_layout.addSpacing(4)
            
        def focusOutEvent(self, event):
            # Close the menu if the user clicks elsewhere
            self.close()

    class DraggableItem(QFrame):
        """A draggable QLabel that also stores its grid span and handles resizing."""
        archive_requested = pyqtSignal(object)
        
        # Constants for grid cell sizing
        CELL_WIDTH = 120
        CELL_HEIGHT = 60
        CELL_SPACING = 10

        def __init__(self, text, widget_id, style_colors, parent=None):
            super().__init__(parent)


            self.widget_id = widget_id
            self._col_span = 1
            self._row_span = 1
            self.display_name = text  # Store the display name
            self.grid_zone = None
            self.setObjectName("DraggableItem")
            
            # Initial size (will be updated when spans change)
            self._update_size()

            layout = QHBoxLayout(self)
            layout.setContentsMargins(5, 0, 5, 0)

            # Use a QStackedWidget to switch between label and line edit
            self.stack = QStackedWidget()
            self.label = QLabel(self.display_name)
            self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.line_edit = QLineEdit(self.display_name)
            self.line_edit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            self.stack.addWidget(self.label)
            self.stack.addWidget(self.line_edit)
            # FIX: Add stretch factor and alignment flag
            layout.addWidget(self.stack, 1)

            # Finish editing when Enter is pressed or focus is lost
            self.line_edit.editingFinished.connect(self._finish_editing)

            button_bg, border, fg = style_colors['button_bg'], style_colors['border'], style_colors['fg']
            self.setStyleSheet(f"""
                QFrame#DraggableItem {{
                    background-color: {button_bg};
                    border: 1px solid {border};
                    border-radius: 10px;
                }}
                QLabel, QLineEdit {{
                    color: {fg};
                    font-weight: 500;
                    background-color: transparent;
                    border: none;
                    padding-left: 5px; /* Add some padding for left alignment */
                }}
                QLineEdit {{
                    border: 1px solid {border};
                    border-radius: 4px;
                }}
            """)

            # Set tooltip and truncated label logic
            self._update_display()
        
        def resizeEvent(self, event):
            self._update_display()
            super().resizeEvent(event)

        def _update_display(self):
            """Updates the label and tooltip based on the current display_name."""
            if not self.label: return

            # Calculate available width (total width - margins/padding)
            # 20px buffer: 10px margins (5+5) + 5px padding + safe buffer
            available_width = self.width() - 25  
            if available_width <= 0:
                 # Fallback if width isn't ready yet (e.g. init)
                 if self.property("isOnGrid"):
                     available_width = (self.CELL_WIDTH * self._col_span) - 25
                 else:
                     available_width = 300 # Default/Archive width guess

            metrics = self.label.fontMetrics()
            elided = metrics.elidedText(self.display_name, Qt.TextElideMode.ElideRight, available_width)
            
            self.label.setText(elided)
            self.setToolTip(f"{self.display_name}\nID: {self.widget_id}\nDouble-click to rename.")
            
        def _update_size(self):
            """Update the widget's size based on its current spans.
            Uses minimum size with Expanding policy so QGridLayout can stretch it."""
            if self.property("isOnGrid"):
                width = self.CELL_WIDTH * self._col_span + self.CELL_SPACING * (self._col_span - 1)
                height = self.CELL_HEIGHT * self._row_span + self.CELL_SPACING * (self._row_span - 1)
                self.setMinimumSize(width, height)
                self.setMaximumSize(16777215, 16777215) # Reset max size
                self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            else:
                # Archived state: Compact size
                self.setMinimumSize(0, 45)
                self.setMaximumSize(16777215, 45) # Force fixed height
                self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        @property
        def col_span(self):
            return self._col_span
        
        @col_span.setter
        def col_span(self, value):
            self._col_span = value
            self._update_size()
        
        @property
        def row_span(self):
            return self._row_span
        
        @row_span.setter
        def row_span(self, value):
            self._row_span = value
            self._update_size()

        def set_display_name(self, name):
            """Updates the display name from outside the class."""
            self.display_name = name
            self.line_edit.setText(name)
            self._update_display()

        def _finish_editing(self):
            """Called when user finishes renaming."""
            new_name = self.line_edit.text()
            self.display_name = new_name
            self._update_display()
            self.stack.setCurrentIndex(0)  # Switch back to the label view

        def mouseDoubleClickEvent(self, event):
            """Switch to edit mode on double-click."""
            # FIX: Properly check button, state, and accept the event
            if self.stack.currentIndex() == 0 and event.button() == Qt.MouseButton.LeftButton:
                self.stack.setCurrentIndex(1)
                self.line_edit.selectAll()
                self.line_edit.setFocus()
                event.accept()
            else:
                super().mouseDoubleClickEvent(event)
        
        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                self.drag_start_position = event.pos()

        def mouseMoveEvent(self, event):
            if not (event.buttons() & Qt.MouseButton.LeftButton): return
            if (event.pos() - self.drag_start_position).manhattanLength() < 10: return

            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(f"{self.widget_id}|{self.col_span}|{self.row_span}")
            drag.setMimeData(mime_data)
            drag.setPixmap(self.grab())
            drag.setHotSpot(event.pos())
            
            # Make the widget semi-transparent using opacity effect instead of hiding
            # This maintains the widget's space in the layout
            from PyQt6.QtWidgets import QGraphicsOpacityEffect
            opacity_effect = QGraphicsOpacityEffect(self)
            opacity_effect.setOpacity(0.3)
            self.setGraphicsEffect(opacity_effect)
            
            result = drag.exec(Qt.DropAction.MoveAction)
            
            # Remove the opacity effect after drag
            self.setGraphicsEffect(None)
            
            # If the drop was cancelled, make sure the widget is visible
            if result == Qt.DropAction.IgnoreAction:
                self.show()
        
        def contextMenuEvent(self, event):
            if not self.property("isOnGrid") or not self.grid_zone: return

            custom_menu = SettingsDialog.CustomMenu(self.window())

            # --- Width Actions ---
            width_group = QButtonGroup(custom_menu)
            width_group.setExclusive(True)
            for i in range(1, 5):
                btn = custom_menu.add_action_button(f"{i} Column{'s' if i > 1 else ''}", i, width_group, self.col_span == i)

            custom_menu.add_separator()

            # --- Height Actions ---
            height_group = QButtonGroup(custom_menu)
            height_group.setExclusive(True)
            for i in range(1, 4):
                btn = custom_menu.add_action_button(f"{i} Row{'s' if i > 1 else ''}", i, height_group, self.row_span == i)
            
            # --- ADD THIS BLOCK ---
            custom_menu.add_separator()
            
            archive_button = QPushButton("Archive")
            archive_button.setObjectName("MenuButton")
            archive_button.clicked.connect(lambda: (self.archive_requested.emit(self), custom_menu.close()))
            custom_menu.content_layout.addWidget(archive_button)
            # --- END OF NEW BLOCK ---

            # --- Handle Clicks ---
            def on_menu_action():
                new_col_span = width_group.checkedButton().property("action_data") if width_group.checkedButton() else self.col_span
            
            # --- Handle Clicks ---
            def on_menu_action():
                new_col_span = width_group.checkedButton().property("action_data") if width_group.checkedButton() else self.col_span
                new_row_span = height_group.checkedButton().property("action_data") if height_group.checkedButton() else self.row_span

                if new_col_span != self.col_span or new_row_span != self.row_span:
                    self.grid_zone.request_resize(self, new_row_span, new_col_span)
                custom_menu.close()

            width_group.buttonClicked.connect(on_menu_action)
            height_group.buttonClicked.connect(on_menu_action)

            # Show the menu at the cursor position
            custom_menu.move(self.mapToGlobal(event.pos()))
            custom_menu.show()

    class DropZone(QFrame):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAcceptDrops(True)
            self.setObjectName("DropZone")

        def is_item_allowed(self, item):
            """
            Determines if a dragged item is allowed to be dropped in this zone.
            Default implementation allows DraggableItem but rejects OnigiriDraggableItem
            (matching the behavior for generic/external zones).
            """
            if isinstance(item, SettingsDialog.OnigiriDraggableItem):
                return False
            return isinstance(item, SettingsDialog.DraggableItem)

        def dragEnterEvent(self, event):
            source_widget = event.source()
            if event.mimeData().hasText() and self.is_item_allowed(source_widget):
                event.acceptProposedAction()
            else:
                event.ignore()

        def dropEvent(self, event):
            source_widget = event.source()
            if self.is_item_allowed(source_widget):
                event.acceptProposedAction()
                # --- FIX: Pass the event to _handle_drop for position info ---
                self._handle_drop(source_widget, event)
            else:
                event.ignore()
        
        def _handle_drop(self, widget, event): pass # Subclasses will implement this

    class VerticalDropZone(DropZone):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.layout = QVBoxLayout(self)
            self.layout.setContentsMargins(5, 5, 5, 5); self.layout.setSpacing(5); self.layout.addStretch()
            self.layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
            
            # Placeholder to open space during drag
            self.drop_placeholder = QWidget()
            self.drop_placeholder.setFixedHeight(45)
            # Fully transparent
            self.drop_placeholder.setStyleSheet("background-color: transparent;")
            self.drop_placeholder.hide()

        def update_drop_indicator(self, pos):
            # Calculate where the placeholder should be
            layout = self.layout
            
            # Get all widgets except placeholder and non-widgets (like stretch)
            widgets = []
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget() and item.widget() is not self.drop_placeholder:
                    widgets.append(item.widget())
            
            target_index = len(widgets) # Default to end
            
            for i, widget in enumerate(widgets):
                # If mouse is above the center of this widget
                if pos.y() < widget.y() + widget.height() // 2:
                    target_index = i
                    break
            
            # Check if placeholder is already at the right spot
            current_index = layout.indexOf(self.drop_placeholder)
            
            if current_index != target_index:
                if current_index != -1:
                    layout.removeWidget(self.drop_placeholder)
                    # When we remove it, indices shift. But target_index was calculated
                    # based on the "clean" list of widgets, so it represents the
                    # intended insertion point among them.
                
                layout.insertWidget(target_index, self.drop_placeholder)
                self.drop_placeholder.show()
            
            return target_index

        def dragEnterEvent(self, event):
            source_widget = event.source()
            if self.is_item_allowed(source_widget):
                 event.acceptProposedAction()
                 self.update_drop_indicator(event.position().toPoint())
            else:
                 event.ignore()

        def dragMoveEvent(self, event):
            source_widget = event.source()
            if self.is_item_allowed(source_widget):
                 event.acceptProposedAction()
                 self.update_drop_indicator(event.position().toPoint())
            else:
                 event.ignore()

        def dragLeaveEvent(self, event):
            self.drop_placeholder.hide()
            self.layout.removeWidget(self.drop_placeholder)
            event.accept()

        def dropEvent(self, event):
            # Find where the placeholder is, that's our drop spot
            index = self.layout.indexOf(self.drop_placeholder)
            
            self.drop_placeholder.hide()
            self.layout.removeWidget(self.drop_placeholder)
            
            # If placeholder wasn't there (fallback)
            if index == -1:
                 index = self.update_drop_indicator(event.position().toPoint())
                 self.drop_placeholder.hide()
                 self.layout.removeWidget(self.drop_placeholder)
            
            source_widget = event.source()
            if self.is_item_allowed(source_widget):
                 self._handle_drop(source_widget, event, insert_index=index)
                 event.acceptProposedAction()
            else:
                 event.ignore()

        def _handle_drop(self, widget, event, insert_index=-1):
            # If the widget came from a grid, tell the grid to release it
            if hasattr(widget, 'grid_zone') and widget.grid_zone:
                # Get a reference to the grid's layout before we change the parent
                grid_layout = widget.grid_zone.layout()

                # Remove the logical reference from all shelves
                for shelf in widget.grid_zone.shelves.values():
                    if shelf.child_widget is widget:
                        shelf.child_widget = None
                        shelf.show() # Make the shelf visible again
                
                # Explicitly remove the widget from the grid's layout
                grid_layout.removeWidget(widget)

            # This part handles items being reordered within the archive itself
            elif old_parent := widget.parent():
                if old_layout := old_parent.layout:
                    old_layout.removeWidget(widget)
            
            widget.row_span, widget.col_span = 1, 1
            widget.setProperty("isOnGrid", False)
            widget.grid_zone = None
            widget.setParent(self)
            widget._update_size() # Apply compact size
            
            if insert_index != -1:
                # insertWidget(index, widget)
                # Note: QVBoxLayout.insertWidget inserts at index. 
                # Be careful about the stretch item at the end.
                # If insert_index is larger than current count, it appends.
                self.layout.insertWidget(insert_index, widget)
            else:
                # Insert before the stretch (which is at count-1 normally)
                # But layout.count() includes the stretch.
                # Usually we want to append to the list of widgets.
                # The stretch is added at __init__.
                # So inserting at count()-1 puts it before the stretch.
                self.layout.insertWidget(self.layout.count() - 1, widget)
                
            widget.show()
            
        def get_item_order(self):
            return [self.layout.itemAt(i).widget().widget_id for i in range(self.layout.count()) if isinstance(self.layout.itemAt(i).widget(), SettingsDialog.DraggableItem)]
        
        def get_archive_config(self):
            config = {}
            for i in range(self.layout.count()):
                item = self.layout.itemAt(i)
                if item and (widget := item.widget()):
                    if isinstance(widget, SettingsDialog.DraggableItem):
                        config[widget.widget_id] = {"display_name": widget.display_name}
            return config

    class GridDropZone(DropZone):
        def __init__(self, main_editor, parent=None):
            super().__init__(parent)
            self.main_editor = main_editor
            self.grid_layout = QGridLayout(self)
            self.grid_layout.setSpacing(10)
            self.grid_layout.setContentsMargins(5, 5, 5, 5)
            # Adapt size to content
            self.grid_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.shelves = {}
            self.highlighted_shelf = None
            self.row_count = 6
            self.col_count = 4
            
            # Initialize grid
            self.update_grid_rows(self.row_count)

        def update_grid_rows(self, rows):
            # Save unique existing widgets to restore them later
            # Use a dict mapped by their primary (top-left) position to avoid duplicates
            current_widgets = {}
            processed_widgets = set()
            
            # Find all widgets currently on the grid
            for pos, shelf in self.shelves.items():
                widget = shelf.child_widget
                if widget and widget not in processed_widgets:
                    current_widgets[pos] = widget
                    processed_widgets.add(widget)
                    # Important: Hide widget before causing it to detach from layout
                    # otherwise it might flash as a separate window
                    widget.hide()
            
            # Detach widgets from shelves to avoid issues during shelf deletion
            for shelf in self.shelves.values():
                shelf.child_widget = None
            
            # Clear existing layout items (shelves and widgets)
            for i in reversed(range(self.grid_layout.count())): 
                item = self.grid_layout.itemAt(i)
                if item.widget():
                    # Hide and detach
                    item.widget().hide()
                    item.widget().setParent(None)
            self.shelves = {}
            
            self.row_count = rows
            
            # Create shelves
            for i in range(rows * self.col_count):
                shelf = SettingsDialog.Shelf(self)
                self.shelves[i] = shelf
                row, col = divmod(i, self.col_count)
                self.grid_layout.addWidget(shelf, row, col)
            
            # Set column sizing
            for col in range(self.col_count):
                self.grid_layout.setColumnMinimumWidth(col, 120)
                self.grid_layout.setColumnStretch(col, 1)
                
            # Set row sizing
            for row in range(rows):
                self.grid_layout.setRowMinimumHeight(row, 60)
                self.grid_layout.setRowStretch(row, 1)
            
            # Clear sizing for unused rows (up to a reasonable max)
            for row in range(rows, 20):
                self.grid_layout.setRowMinimumHeight(row, 0)
                self.grid_layout.setRowStretch(row, 0)

            # Restore widgets if they fit
            for pos, widget in current_widgets.items():
                if pos < rows * self.col_count:
                    # Check if it fits in new grid (simplified check)
                    row, col = divmod(pos, self.col_count)
                    if row + widget.row_span <= rows:
                        self.place_item(widget, pos, silent=True)
                    else:
                         widget.archive_requested.emit(widget) # Move to archive if it doesn't fit
                else:
                    widget.archive_requested.emit(widget) # Move to archive if pos is out of bounds



        def dragMoveEvent(self, event):
            # Check if the item is allowed before processing the move
            if not self.is_item_allowed(event.source()):
                event.ignore()
                return

            if self.highlighted_shelf:
                self.highlighted_shelf.set_highlight(False)
                self.highlighted_shelf = None
            
            for shelf in self.shelves.values():
                # --- FIX: Use event.position() instead of event.pos() ---
                if shelf.geometry().contains(event.position().toPoint()):
                    shelf.set_highlight(True)
                    self.highlighted_shelf = shelf
                    break
            event.acceptProposedAction()

        def dragLeaveEvent(self, event):
            if self.highlighted_shelf:
                self.highlighted_shelf.set_highlight(False)
                self.highlighted_shelf = None
            event.accept()

        def _handle_drop(self, widget, event):
            if self.highlighted_shelf:
                self.highlighted_shelf.set_highlight(False)
                self.highlighted_shelf = None

            target_pos = -1
            for pos, shelf in self.shelves.items():
                # --- FIX: Use event.position() instead of event.pos() ---
                if shelf.geometry().contains(event.position().toPoint()):
                    target_pos = pos
                    break
            
            if target_pos != -1:
                # <<< START NEW CODE >>>
                # If widget is coming from outside a grid (e.g., the archive), reset its size
                if not widget.property("isOnGrid"):
                    if isinstance(widget, SettingsDialog.OnigiriDraggableItem):
                        if widget.widget_id == "heatmap":
                            widget.row_span, widget.col_span = 2, 4
                        elif widget.widget_id == "restaurant_level":
                            widget.row_span, widget.col_span = 2, 2
                        else: # It's a stat card
                            widget.row_span, widget.col_span = 1, 1
                    else: # External add-on
                        # Default external widgets to 2 rows height as requested
                        widget.row_span, widget.col_span = 2, 1
                # <<< END NEW CODE >>>
                self.place_item(widget, target_pos)
            else:
                widget.show()
        
        def is_region_free(self, row, col, row_span, col_span, ignored_widget=None):
            if col + col_span > self.col_count or row + row_span > self.row_count: return False
            for r in range(row, row + row_span):
                for c in range(col, col + col_span):
                    pos = r * self.col_count + c
                    if pos not in self.shelves: return False
                    if self.shelves[pos].child_widget and self.shelves[pos].child_widget is not ignored_widget: return False
            return True

        def place_item(self, item, pos, silent=False):
            # First, uncover any shelves this item was previously covering
            for shelf_pos, shelf in self.shelves.items():
                if shelf.child_widget is item:
                    shelf.child_widget = None
                    shelf.show()  # Show the shelf again when item is removed
                    
            row, col = divmod(pos, self.col_count)
            if not self.is_region_free(row, col, item.row_span, item.col_span, ignored_widget=item):
                grid_size = self.row_count * self.col_count
                for i in range(grid_size):
                    r, c = divmod(i, self.col_count)
                    if self.is_region_free(r, c, item.row_span, item.col_span, ignored_widget=item):
                        row, col = r, c; break
                else:
                    if not silent:
                        QMessageBox.warning(self.window(), "Placement Error", "No available slot was found for this item.")
                    item.show() # Ensure the item reappears if the drop fails
                    return False
            
            item.setProperty("isOnGrid", True); item.grid_zone = self
            item.setParent(self)
            item._update_size() # Apply grid size
            self.grid_layout.addWidget(item, row, col, item.row_span, item.col_span)
            
            # Mark all covered shelves and hide them (except the first one which stays as anchor)
            for r in range(row, row + item.row_span):
                for c in range(col, col + item.col_span):
                    shelf_pos = r * self.col_count + c
                    if shelf_pos in self.shelves:
                        self.shelves[shelf_pos].child_widget = item
                        # Hide covered shelves so they don't show through the spanning widget
                        self.shelves[shelf_pos].hide()
            
            item.show()
            
            # Force layout update to ensure geometry is correct
            # This helps prevent floating window glitches or incorrect positioning
            self.grid_layout.update()
            
            return True
        
        def request_resize(self, item, new_row_span, new_col_span):
            new_pos = -1
            # Use dynamic range based on grid size
            grid_size = self.row_count * self.col_count
            for i in range(grid_size):
                r, c = divmod(i, self.col_count)
                if self.is_region_free(r, c, new_row_span, new_col_span, ignored_widget=item):
                    new_pos = i; break
            if new_pos == -1:
                QMessageBox.warning(self.window(), "Resize Error", f"No available {new_row_span}x{new_col_span} slot was found on the grid."); return
            
            # Show shelves that are about to be uncovered
            for shelf in self.shelves.values():
                if shelf.child_widget is item: 
                    shelf.child_widget = None
                    shelf.show()
                    
            new_row, new_col = divmod(new_pos, self.col_count)
            conflicting_widgets = set()
            for r in range(new_row, new_row + new_row_span):
                for c in range(new_col, new_col + new_col_span):
                    pos = r * self.col_count + c
                    if pos in self.shelves and self.shelves[pos].child_widget: 
                        conflicting_widgets.add(self.shelves[pos].child_widget)
            
            for conflicting_item in conflicting_widgets:
                for shelf in self.shelves.values():
                    if shelf.child_widget is conflicting_item: 
                        shelf.child_widget = None
                        shelf.show() # Show shelves for conflicting items too

                # Find the first available spot for it and place it there
                found_spot = False
                for i in range(grid_size):
                    r, c = divmod(i, self.col_count)
                    # Use the item's own size for finding a new spot, default to 1x1 if needed
                    r_span = getattr(conflicting_item, 'row_span', 1)
                    c_span = getattr(conflicting_item, 'col_span', 1)
                    if self.is_region_free(r, c, r_span, c_span):
                        self.place_item(conflicting_item, i)
                        found_spot = True
                        break
                if not found_spot:
                    # Fallback: if no space for its size is found, try to place as 1x1
                    for i in range(grid_size):
                        r, c = divmod(i, self.col_count)
                        if self.is_region_free(r, c, 1, 1):
                            conflicting_item.row_span = 1
                            conflicting_item.col_span = 1
                            self.place_item(conflicting_item, i)
                            break
            
            item.row_span, item.row_span = new_row_span, new_row_span # Wait, typo in original? No, item.row_span...
            # The replacement content has a typo, let me fix it
            item.row_span = new_row_span
            item.col_span = new_col_span
            self.place_item(item, new_pos)
        
        # settings.py

        def get_layout_config(self):
            layout, processed_widgets = {}, set()
            for pos, shelf in self.shelves.items():
                widget = shelf.child_widget
                if widget and widget not in processed_widgets:
                    layout[widget.widget_id] = { 
                        "grid_position": pos, 
                        "row_span": widget.row_span, 
                        "column_span": widget.col_span,
                        "display_name": widget.display_name
                    }
                    processed_widgets.add(widget)
            return layout

    class Shelf(QFrame):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName("Shelf")
            # Use minimum size but allow expansion to fill the grid cell
            # This ensures it matches the size of widgets which also expand
            self.setMinimumSize(120, 60)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.child_widget = None

        def set_highlight(self, highlighted):
            # --- FIX: Use setProperty to make the state visible to the stylesheet ---
            # Check the current property to avoid unnecessary style refreshes
            current_highlight = self.property("is_highlighted") or False
            if current_highlight != highlighted:
                self.setProperty("is_highlighted", highlighted)
                self.style().polish(self)

    # =================================================================
    # START: Onigiri Widget Layout Editor
    # =================================================================

    class OnigiriDraggableItem(DraggableItem):
        archive_requested = pyqtSignal(object)
        
        def contextMenuEvent(self, event):
            if not self.property("isOnGrid") or not self.grid_zone: return

            custom_menu = SettingsDialog.CustomMenu(self.window())
            is_heatmap = self.widget_id == 'heatmap'

            # --- Width Actions ---
            width_group = QButtonGroup(custom_menu)
            width_group.setExclusive(True)
            max_cols = 4
            for i in range(1, max_cols + 1):
                if is_heatmap and i < 2: continue # Heatmap min 2 cols
                if self.widget_id == 'restaurant_level':
                     if i != 2: continue # Restaurant Level exactly 2 cols
                btn = custom_menu.add_action_button(f"{i} Column{'s' if i > 1 else ''}", i, width_group, self.col_span == i)

            custom_menu.add_separator()

            # --- Height Actions ---
            height_group = QButtonGroup(custom_menu)
            height_group.setExclusive(True)
            # Set row constraints
            min_rows = 2 if (is_heatmap or self.widget_id == 'restaurant_level') else 1
            if is_heatmap:
                max_rows = 2  # Heatmap: exactly 2 rows
            elif self.widget_id == 'restaurant_level':
                max_rows = 2  # Restaurant Level: exactly 2 rows (for now)
            elif self.widget_id == 'favorites':
                max_rows = 3  # Favorites: up to 3 rows
            else:
                max_rows = 1  # Other widgets: 1 row
            for i in range(min_rows, max_rows + 1):
                btn = custom_menu.add_action_button(f"{i} Row{'s' if i > 1 else ''}", i, height_group, self.row_span == i)
            
            custom_menu.add_separator()
            
            # --- Archive Action ---
            archive_button = QPushButton("Archive")
            archive_button.setObjectName("MenuButton")
            archive_button.clicked.connect(lambda: (self.archive_requested.emit(self), custom_menu.close()))
            custom_menu.content_layout.addWidget(archive_button)

            def on_menu_action():
                new_col_span = width_group.checkedButton().property("action_data") if width_group.checkedButton() else self.col_span
                new_row_span = height_group.checkedButton().property("action_data") if height_group.checkedButton() else self.row_span

                if new_col_span != self.col_span or new_row_span != self.row_span:
                    self.grid_zone.request_resize(self, new_row_span, new_col_span)
                custom_menu.close()

            width_group.buttonClicked.connect(on_menu_action)
            height_group.buttonClicked.connect(on_menu_action)

            custom_menu.move(self.mapToGlobal(event.pos()))
            custom_menu.show()
    
    class UnifiedGridDropZone(GridDropZone):
        """A unified grid that accepts both Onigiri and External widgets."""
        def __init__(self, main_editor, parent=None):
            super().__init__(main_editor, parent)
            # Row count is controlled by the parent GridDropZone (default 6)

        def is_item_allowed(self, item):
            # Accept both Onigiri and External draggable items
            return isinstance(item, (SettingsDialog.OnigiriDraggableItem, SettingsDialog.DraggableItem))
    
    class OnigiriGridDropZone(GridDropZone):
        def __init__(self, main_editor, parent=None):
            super().__init__(main_editor, parent)
            # Override grid size to 3 rows, 4 columns
            for i in range(20, 24):
                if i in self.shelves:
                    self.shelves[i].setParent(None)
                    del self.shelves[i]

        def is_item_allowed(self, item):
            return isinstance(item, SettingsDialog.OnigiriDraggableItem)
        
        # Override region check for 3x4 grid
        def is_region_free(self, row, col, row_span, col_span, ignored_widget=None):
            if col + col_span > 4 or row + row_span > 5: return False
            for r in range(row, row + row_span):
                for c in range(col, col + col_span):
                    pos = r * 4 + c
                    if pos in self.shelves and self.shelves[pos].child_widget and self.shelves[pos].child_widget is not ignored_widget: return False
            return True

    class OnigiriArchiveZone(VerticalDropZone):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setMinimumHeight(80) # Make it a bit taller
        def is_item_allowed(self, item):
            return isinstance(item, SettingsDialog.OnigiriDraggableItem)
    
    class ExternalArchiveZone(VerticalDropZone):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setMinimumHeight(80) # Match OnigiriArchiveZone

        def is_item_allowed(self, item):
            if isinstance(item, SettingsDialog.OnigiriDraggableItem):
                return False
            return isinstance(item, SettingsDialog.DraggableItem)

    # --- START: New Draggable Item for Sidebar ---
    # This item is not resizeable
    class DraggableSidebarItem(DraggableItem):
        def __init__(self, text, widget_id, style_colors, is_external=False, parent=None):
            super().__init__(text, widget_id, style_colors, parent)
            self.setToolTip(f"ID: {self.widget_id}\nDouble-click to rename.")
            self.locked = False
            self.is_external = bool(is_external)

        def setLocked(self, locked: bool):
            """Sets the locked state of the item. Locked items handle events differently."""
            self.locked = locked
            if locked:
                # Visual indication of locked state
                self.setGraphicsEffect(None) # Clear any previous effects
                from PyQt6.QtWidgets import QGraphicsOpacityEffect
                opacity = QGraphicsOpacityEffect(self)
                opacity.setOpacity(0.6)
                self.setGraphicsEffect(opacity)
                self.setCursor(Qt.CursorShape.ForbiddenCursor)
                self.setToolTip(f"{self.display_name} (Fixed in Full Mode)")
            else:
                self.setGraphicsEffect(None)
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.setToolTip(f"ID: {self.widget_id}\nDouble-click to rename.")

        def mouseMoveEvent(self, event):
            if self.locked:
                return
            super().mouseMoveEvent(event)

        def contextMenuEvent(self, event):
            # Disable the right-click resize menu for sidebar items
            event.ignore()

    # --- END: New Draggable Item for Sidebar ---

    # --- START: New Drop Zones for Sidebar ---
    # These zones only accept DraggableSidebarItem
    class SidebarVisibleZone(VerticalDropZone):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.drop_indicator = QLabel(self)
            self.drop_indicator.setFixedHeight(2)
            self.drop_indicator.hide()
            
        def update_drop_indicator(self, pos):
            # Find the position to show the drop indicator
            layout = self.layout
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if not item or not item.widget():
                    continue
                widget = item.widget()
                if widget.y() + widget.height() // 2 > pos.y():
                    self.drop_indicator.move(5, widget.y())
                    self.drop_indicator.setFixedWidth(self.width() - 10)
                    return widget
            # If not found, put at the end
            last_widget = self.findChild(QWidget, "", Qt.FindChildOption.FindDirectChildrenOnly)
            if last_widget:
                self.drop_indicator.move(5, last_widget.y() + last_widget.height())
            else:
                self.drop_indicator.move(5, 5)
            self.drop_indicator.setFixedWidth(self.width() - 10)
            return None
            
        def is_item_allowed(self, source_widget):
            return isinstance(source_widget, SettingsDialog.DraggableSidebarItem)

        def dragEnterEvent(self, event):
            source_widget = event.source()
            if event.mimeData().hasText() and self.is_item_allowed(source_widget):
                self.drop_indicator.setStyleSheet("background-color: #0078d7;")
                self.drop_indicator.raise_()
                event.acceptProposedAction()
            else:
                event.ignore()
                
        def dragMoveEvent(self, event):
            if event.mimeData().hasText() and self.is_item_allowed(event.source()):
                self.drop_indicator.show()
                self.update_drop_indicator(event.position().toPoint())
                event.acceptProposedAction()
            else:
                event.ignore()
                
        def dragLeaveEvent(self, event):
            self.drop_indicator.hide()
            super().dragLeaveEvent(event)
            
        def dropEvent(self, event):
            self.drop_indicator.hide()
            pos = event.position().toPoint()
            source_widget = event.source()
            
            if self.is_item_allowed(source_widget):
                # Find the insert position
                insert_pos = self.layout.count() - 1  # Default to before the stretch
                for i in range(self.layout.count()):
                    item = self.layout.itemAt(i)
                    if item and item.widget():
                        widget = item.widget()
                        if widget.y() + widget.height() // 2 > pos.y():
                            insert_pos = i
                            break
                
                # Store the widget's state before removing it
                was_visible = source_widget.isVisible()
                
                # Remove from old position if needed
                if old_parent := source_widget.parent():
                    if old_parent is self:
                        old_pos = self.layout.indexOf(source_widget)
                        if old_pos < insert_pos:
                            insert_pos -= 1  # Adjust if moving down in the same list
                        self.layout.removeWidget(source_widget)
                    elif hasattr(old_parent, 'layout'):
                        if old_layout := old_parent.layout:
                            old_layout.removeWidget(source_widget)
                
                # Ensure the widget is properly reparented and shown
                source_widget.setParent(self)
                source_widget.show()
                
                # Insert at the new position
                self.layout.insertWidget(insert_pos, source_widget)
                event.acceptProposedAction()
            else:
                event.ignore()

    class SidebarArchiveZone(VerticalDropZone):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.drop_indicator = QLabel(self)
            self.drop_indicator.setFixedHeight(2)
            self.drop_indicator.hide()

        def is_item_allowed(self, source_widget):
            return (
                isinstance(source_widget, SettingsDialog.DraggableSidebarItem)
                and not getattr(source_widget, "is_external", False)
            )
            
        def update_drop_indicator(self, pos):
            # Find the position to show the drop indicator
            layout = self.layout
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if not item or not item.widget():
                    continue
                widget = item.widget()
                if widget.y() + widget.height() // 2 > pos.y():
                    self.drop_indicator.move(5, widget.y())
                    self.drop_indicator.setFixedWidth(self.width() - 10)
                    return widget
            # If not found, put at the end
            last_widget = self.findChild(QWidget, "", Qt.FindChildOption.FindDirectChildrenOnly)
            if last_widget:
                self.drop_indicator.move(5, last_widget.y() + last_widget.height())
            else:
                self.drop_indicator.move(5, 5)
            self.drop_indicator.setFixedWidth(self.width() - 10)
            return None
            
        def dragEnterEvent(self, event):
            source_widget = event.source()
            if event.mimeData().hasText() and self.is_item_allowed(source_widget):
                self.drop_indicator.setStyleSheet("background-color: #0078d7;")
                self.drop_indicator.raise_()
                event.acceptProposedAction()
            else:
                event.ignore()
                
        def dragMoveEvent(self, event):
            if event.mimeData().hasText() and self.is_item_allowed(event.source()):
                self.drop_indicator.show()
                self.update_drop_indicator(event.position().toPoint())
                event.acceptProposedAction()
            else:
                event.ignore()
                
        def dragLeaveEvent(self, event):
            self.drop_indicator.hide()
            super().dragLeaveEvent(event)
            
        def dropEvent(self, event):
            self.drop_indicator.hide()
            pos = event.position().toPoint()
            source_widget = event.source()
            
            if self.is_item_allowed(source_widget):
                # Find the insert position
                insert_pos = self.layout.count() - 1  # Default to before the stretch
                for i in range(self.layout.count()):
                    item = self.layout.itemAt(i)
                    if item and item.widget():
                        widget = item.widget()
                        if widget.y() + widget.height() // 2 > pos.y():
                            insert_pos = i
                            break
                
                # Store the widget's state before removing it
                was_visible = source_widget.isVisible()
                
                # Remove from old position if needed
                if old_parent := source_widget.parent():
                    if old_parent is self:
                        old_pos = self.layout.indexOf(source_widget)
                        if old_pos < insert_pos:
                            insert_pos -= 1  # Adjust if moving down in the same list
                        self.layout.removeWidget(source_widget)
                    elif hasattr(old_parent, 'layout'):
                        if old_layout := old_parent.layout:
                            old_layout.removeWidget(source_widget)
                
                # Ensure the widget is properly reparented and shown
                source_widget.setParent(self)
                source_widget.show()
                
                # Insert at the new position
                self.layout.insertWidget(insert_pos, source_widget)
                event.acceptProposedAction()
            else:
                event.ignore()

    class SidebarExternalArchiveZone(SidebarArchiveZone):
        def is_item_allowed(self, source_widget):
            return (
                isinstance(source_widget, SettingsDialog.DraggableSidebarItem)
                and getattr(source_widget, "is_external", False)
            )
    
    class SidebarLayoutEditor(QWidget):
        """
        A widget with three vertical drop zones for reordering and archiving sidebar buttons.
        """
        BASE_BUTTON_MAP = {
            "profile": "Profile Bar",
            "add": "Add Button",
            "browse": "Browse Button",
            "stats": "Stats Button",
            "sync": "Sync Button",
            "settings": "Settings Button",
            "more": "More Menu"
        }

        def __init__(self, settings_dialog, parent=None):
            super().__init__(parent)
            self.settings_dialog = settings_dialog
            self.config = settings_dialog.current_config.get("sidebarButtonLayout", copy.deepcopy(DEFAULTS["sidebarButtonLayout"]))
            self.all_sidebar_items = {}

            if theme_manager.night_mode:
                button_bg, border, fg = "#4a4a4a", "#4a4a4a", "#e0e0e0"
            else:
                button_bg, border, fg = "#f0f0f0", "#e0e0e0", "#212121"
            self.style_colors = {"button_bg": button_bg, "border": border, "fg": fg}
            
            self._init_ui() # Call _init_ui
            
        def _init_ui(self):
            if theme_manager.night_mode:
                button_bg, border, fg = "#4a4a4a", "#4a4a4a", "#e0e0e0"
            else:
                button_bg, border, fg = "#f0f0f0", "#e0e0e0", "#212121"
            self.style_colors = {"button_bg": button_bg, "border": border, "fg": fg}

            main_layout = QHBoxLayout(self)
            main_layout.setSpacing(15)
            main_layout.setContentsMargins(0, 0, 0, 0)

            # --- Visible Items Zone ---
            visible_group = QGroupBox("Visible Items")
            visible_group.setObjectName("LayoutGroup")
            visible_layout = QVBoxLayout(visible_group)
            visible_layout.setSpacing(5)
            visible_layout.setContentsMargins(10, 15, 10, 10)
            
            self.visible_zone = SettingsDialog.SidebarVisibleZone(self)
            visible_layout.addWidget(self.visible_zone)
            main_layout.addWidget(visible_group, stretch=1)

            # --- Archived Onigiri Items Zone ---
            archived_group = QGroupBox("Archived Onigiri Items")
            archived_group.setObjectName("LayoutGroup")
            archived_layout = QVBoxLayout(archived_group)
            archived_layout.setSpacing(5)
            archived_layout.setContentsMargins(10, 15, 10, 10)
            
            self.archive_zone = SettingsDialog.SidebarArchiveZone(self)
            archived_layout.addWidget(self.archive_zone)
            main_layout.addWidget(archived_group, stretch=1)

            # --- Archived External Items Zone ---
            external_archived_group = QGroupBox("Archived External Items")
            external_archived_group.setObjectName("LayoutGroup")
            external_archived_layout = QVBoxLayout(external_archived_group)
            external_archived_layout.setSpacing(5)
            external_archived_layout.setContentsMargins(10, 15, 10, 10)
            
            self.external_archive_zone = SettingsDialog.SidebarExternalArchiveZone(self)
            external_archived_layout.addWidget(self.external_archive_zone)
            main_layout.addWidget(external_archived_group, stretch=1)
            
            # Set minimum heights for the drop zones
            self.visible_zone.setMinimumHeight(200)
            self.archive_zone.setMinimumHeight(100)
            self.external_archive_zone.setMinimumHeight(100)
            
            # Apply styles
            self.setStyleSheet("""
                QGroupBox#LayoutGroup {
                    border: 1px solid %(border)s;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 15px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 3px;
                }
                QLabel#DropIndicator {
                    background-color: #0078d7;
                }
            """ % self.style_colors)
            
            self._populate_widgets()

        def _get_button_map(self) -> dict:
            button_map = dict(self.BASE_BUTTON_MAP)
            button_map.update(sidebar_api.get_sidebar_labels())
            return button_map

        def _populate_widgets(self):
            # Get the saved layout config
            visible_order = self.config.get("visible", [])
            archived = self.config.get("archived", [])
            external_ids = set(sidebar_api.get_sidebar_labels().keys())
            
            # Use defaults from the top-level DEFAULTS constant
            default_archived = list(DEFAULTS["sidebarButtonLayout"]["archived"])

            # Check if Full Mode is enabled
            is_full_mode = self.settings_dialog.current_config.get("fullHideMode", False)

            # Create all possible items
            for widget_id, text in self._get_button_map().items():
                is_external = widget_id in external_ids
                item = SettingsDialog.DraggableSidebarItem(
                    text, widget_id, self.style_colors, is_external=is_external
                )
                self.all_sidebar_items[widget_id] = item

            # If Full Mode is on, ensure "settings" is visible and not archived
            if is_full_mode:
                if "settings" in archived:
                    archived.remove("settings")
                if "settings" not in visible_order:
                    visible_order.append("settings")

            placed_items = set()
            
            # Place visible items
            for widget_id in visible_order:
                if item := self.all_sidebar_items.get(widget_id):
                    self.visible_zone.layout.insertWidget(self.visible_zone.layout.count() - 1, item)
                    placed_items.add(widget_id)
                    
                    # Lock settings button if in Full Mode
                    if is_full_mode and widget_id == "settings":
                        item.setLocked(True)
            
            # Place archived items
            for widget_id in archived:
                if item := self.all_sidebar_items.get(widget_id):
                    if widget_id not in placed_items: # Avoid duplicates
                        if widget_id in external_ids:
                            self.external_archive_zone.layout.insertWidget(
                                self.external_archive_zone.layout.count() - 1, item
                            )
                        else:
                            self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)
                        placed_items.add(widget_id)

            # Place any new/unconfigured items
            for widget_id, item in self.all_sidebar_items.items():
                if widget_id not in placed_items:
                    # External items default to archived
                    if widget_id in external_ids:
                        self.external_archive_zone.layout.insertWidget(
                            self.external_archive_zone.layout.count() - 1, item
                        )
                    # Check against the DEFAULTS to see where new items should go
                    elif widget_id in default_archived and not (is_full_mode and widget_id == "settings"):
                        self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)
                    else: # Default to visible if not in archived (or not in defaults at all)
                        self.visible_zone.layout.insertWidget(self.visible_zone.layout.count() - 1, item)
                         
                        # Lock settings button if in Full Mode (edge case where it wasn't in visible_order or archived)
                        if is_full_mode and widget_id == "settings":
                            item.setLocked(True)

        def get_layout_config(self) -> dict:
            # Get keys from the "Visible" zone
            visible = []
            for i in range(self.visible_zone.layout.count()):
                item = self.visible_zone.layout.itemAt(i)
                if item and (widget := item.widget()):
                    if isinstance(widget, SettingsDialog.DraggableSidebarItem):
                        visible.append(widget.widget_id)

            # Get keys from the "Archived" zone
            archived = []
            for i in range(self.archive_zone.layout.count()):
                item = self.archive_zone.layout.itemAt(i)
                if item and (widget := item.widget()):
                    if isinstance(widget, SettingsDialog.DraggableSidebarItem):
                        archived.append(widget.widget_id)
            for i in range(self.external_archive_zone.layout.count()):
                item = self.external_archive_zone.layout.itemAt(i)
                if item and (widget := item.widget()):
                    if isinstance(widget, SettingsDialog.DraggableSidebarItem):
                        archived.append(widget.widget_id)
                        
            return {"visible": visible, "archived": archived}
    
    class OnigiriLayoutEditor(QWidget):
        def __init__(self, settings_dialog):
            super().__init__()
            self.settings_dialog = settings_dialog
            main_layout = QVBoxLayout(self)
            main_layout.setSpacing(15)

            onigiri_group = QGroupBox("Onigiri Widgets")
            onigiri_group.setObjectName("LayoutGroup")
            self.grid_zone = SettingsDialog.OnigiriGridDropZone(self, onigiri_group)
            onigiri_group_layout = QVBoxLayout(onigiri_group)
            onigiri_group_layout.addWidget(self.grid_zone)
            main_layout.addWidget(onigiri_group)

            archive_group = QGroupBox("Archived Widgets")
            archive_group.setObjectName("LayoutGroup")
            self.archive_zone = SettingsDialog.OnigiriArchiveZone(archive_group)
            archive_group_layout = QVBoxLayout(archive_group)
            archive_group_layout.addWidget(self.archive_zone)
            main_layout.addWidget(archive_group)

            self.all_onigiri_items = {}
            self._populate_widgets()

        def _populate_widgets(self):
            if theme_manager.night_mode:
                button_bg, border, fg = "#4a4a4a", "#4a4a4a", "#e0e0e0"
            else:
                button_bg, border, fg = "#f0f0f0", "#e0e0e0", "#212121"
            style_colors = {"button_bg": button_bg, "border": border, "fg": fg}

            # Define default layout
            DEFAULTS = {
                "grid": {
                    "studied": {"pos": 0, "row": 1, "col": 1},
                    "time": {"pos": 1, "row": 1, "col": 1},
                    "pace": {"pos": 2, "row": 1, "col": 1},
                    "retention": {"pos": 3, "row": 1, "col": 1},
                    "heatmap": {"pos": 4, "row": 2, "col": 4},
                },
                "archive": ["favorites", "restaurant_level"] # <-- "favorites" and "restaurant_level" moved here
            }

            saved_layout = self.settings_dialog.current_config.get("onigiriWidgetLayout", DEFAULTS)
            
            # --- START: Robust config merging ---
            saved_grid_config = saved_layout.get("grid")
            
            # If we have a saved grid config, use it. Otherwise use defaults.
            if isinstance(saved_grid_config, dict):
                grid_config = copy.deepcopy(saved_grid_config)
            else:
                grid_config = copy.deepcopy(DEFAULTS["grid"])
            
            # Safely get archive_config, falling back to default if it's None or invalid
            archive_config = saved_layout.get("archive")
            if not isinstance(archive_config, (list, dict)):
                 archive_config = DEFAULTS["archive"]

            # Ensure any widgets in DEFAULTS["grid"] that are not in grid_config OR archive_config are added to grid_config
            # This handles new widgets added in updates
            
            # Helper to get list of archived IDs
            if isinstance(archive_config, dict):
                archived_ids = set(archive_config.keys())
            else:
                archived_ids = set(archive_config)
            
            # --- FIXED: Remove archived items from grid_config ---
            # The config.merge_config function might have re-inserted default grid positions 
            # for items that the user moved to the archive.
            for widget_id in archived_ids:
                if widget_id in grid_config:
                    del grid_config[widget_id]
            # -----------------------------------------------------

            for widget_id, default_pos in DEFAULTS["grid"].items():
                if widget_id not in grid_config and widget_id not in archived_ids:
                    grid_config[widget_id] = default_pos
            # --- END: Robust config merging ---

            widget_definitions = {
                "studied": "Studied Card", "time": "Time Card", 
                "pace": "Pace Card", "retention": "Retention Card", "heatmap": "Heatmap",
                "favorites": "Favorites Widget",
                "restaurant_level": "Restaurant Level"
            }

            placed_widgets = set()

            # Create all items
            for widget_id, text in widget_definitions.items():
                item = SettingsDialog.OnigiriDraggableItem(text, widget_id, style_colors)
                item.archive_requested.connect(self._archive_item)
                if widget_id == "restaurant_level":
                    item.row_span = 2
                    item.col_span = 2
                self.all_onigiri_items[widget_id] = item

            # Combine grid and archive configs to find all saved names
            all_saved_configs = grid_config.copy()
            if isinstance(archive_config, dict):
                all_saved_configs.update(archive_config)
            elif isinstance(archive_config, list):
                # Handle old list-based archive config
                for widget_id in archive_config:
                    all_saved_configs.setdefault(widget_id, {}) # Add it with no display name

            # Update display names from saved config
            for widget_id, item in self.all_onigiri_items.items():
                if saved_item_config := all_saved_configs.get(widget_id):
                    if custom_name := saved_item_config.get("display_name"):
                        item.set_display_name(custom_name)

            # Place items on grid
            for widget_id, config in grid_config.items():
                if item := self.all_onigiri_items.get(widget_id):
                    item.row_span = config.get("row", 1)
                    item.col_span = config.get("col", 1)
                    # Use a default 'pos' if missing (e.g., from old config)
                    if self.grid_zone.place_item(item, config.get("pos", 0), silent=True):
                        placed_widgets.add(widget_id)

            # Place items in archive (handle both list and dict for backward compatibility)
            archive_ids = []
            if isinstance(archive_config, list):
                archive_ids = archive_config
            elif isinstance(archive_config, dict):
                archive_ids = archive_config.keys()
            
            for widget_id in archive_ids:
                if item := self.all_onigiri_items.get(widget_id):
                    # Don't place in archive if it was already placed on the grid
                    if widget_id not in placed_widgets:
                        self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)
                        placed_widgets.add(widget_id)

            # Place any new/unconfigured items into the archive
            for widget_id, item in self.all_onigiri_items.items():
                if widget_id not in placed_widgets:
                    self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)

        def _archive_item(self, item):
            for shelf in self.grid_zone.shelves.values():
                if shelf.child_widget is item: shelf.child_widget = None
            self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)
            # Reset spans when archiving
            if item.widget_id == "heatmap":
                item.row_span, item.col_span = 2, 4
            else:
                item.row_span, item.col_span = 1, 1

        def get_layout_config(self):
            grid_config = {}
            processed_widgets = set()
            for pos, shelf in self.grid_zone.shelves.items():
                widget = shelf.child_widget
                if widget and widget not in processed_widgets:
                    grid_config[widget.widget_id] = {
                        "pos": pos, "row": widget.row_span, "col": widget.col_span,
                        "display_name": widget.display_name
                    }
                    processed_widgets.add(widget)

            archive_config = self.archive_zone.get_archive_config()
            return {"grid": grid_config, "archive": archive_config}
    
    class MainMenuLayoutEditor(QWidget):
        def __init__(self, settings_dialog):
            super().__init__()
            self.settings_dialog = settings_dialog
            main_layout = QVBoxLayout(self); main_layout.setSpacing(15)
            grid_group = QGroupBox("External Add-on Grid")
            grid_group.setObjectName("LayoutGroup")
            self.grid_zone = SettingsDialog.GridDropZone(self, grid_group)

            # Setup layout for grid group to hold the grid
            grid_group_layout = QVBoxLayout(grid_group)
            grid_group_layout.addWidget(self.grid_zone)

            main_layout.addWidget(grid_group)

            archive_group = QGroupBox("Archived External Add-ons")
            archive_group.setObjectName("LayoutGroup")
            self.archive_zone = SettingsDialog.ExternalArchiveZone(archive_group)
            archive_group_layout = QVBoxLayout(archive_group)
            archive_group_layout.addWidget(self.archive_zone)
            main_layout.addWidget(archive_group)

            self.all_external_items = {} # Will store all draggable items for external addons
            self._populate_widgets()

        def _populate_widgets(self):
            if theme_manager.night_mode:
                button_bg, border, fg = "#4a4a4a", "#4a4a4a", "#e0e0e0"
            else:
                button_bg, border, fg = "#f0f0f0", "#e0e0e0", "#212121"
            style_colors = {"button_bg": button_bg, "border": border, "fg": fg}

            saved_layout = self.settings_dialog.current_config.get("externalWidgetLayout", {})
            # Gracefully handle old config format
            if saved_layout and "grid" not in saved_layout:
                grid_config = saved_layout
                archive_config = {}
            else:
                grid_config = saved_layout.get("grid", {})
                archive_config = saved_layout.get("archive", {})

            external_hooks = self.settings_dialog._get_external_hooks()

            # Create and store all external addon items
            for hook_id in external_hooks:
                item = SettingsDialog.DraggableItem(hook_id.split('.')[0], hook_id, style_colors)
                item.archive_requested.connect(self._archive_item)
                self.all_external_items[hook_id] = item

            # Combine grid and archive configs to find all saved names
            all_saved_configs = {**grid_config, **archive_config}

            # Update display names from saved config
            for hook_id, item in self.all_external_items.items():
                if saved_item_config := all_saved_configs.get(hook_id):
                    if custom_name := saved_item_config.get("display_name"):
                        item.set_display_name(custom_name)

            placed_hooks = set()
            # Place items that have a saved position on the grid
            for hook_id, config in grid_config.items():
                if hook_id in self.all_external_items:
                    item = self.all_external_items[hook_id]
                    item.row_span = config.get("row_span", 1)
                    item.col_span = config.get("column_span", 1)
                    if self.grid_zone.place_item(item, config.get("grid_position", 0), silent=True):
                        placed_hooks.add(hook_id)
            
            # Place items that have a saved position in the archive
            for hook_id in archive_config.keys():
                if hook_id in self.all_external_items:
                    item = self.all_external_items[hook_id]
                    self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)
                    placed_hooks.add(hook_id)

            # Place any new/unplaced add-ons in the ARCHIVE
            for hook_id in external_hooks:
                if hook_id not in placed_hooks:
                    item = self.all_external_items[hook_id]
                    self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)
        
        def _archive_item(self, item):
            """Moves an item from the grid to the archive zone."""
            for shelf in self.grid_zone.shelves.values():
                if shelf.child_widget is item:
                    shelf.child_widget = None
            self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)
            
        def get_layout_config(self):
            """Retrieves the current layout from the grid and archive zones."""
            grid_config = self.grid_zone.get_layout_config()
            archive_config = self.archive_zone.get_archive_config()
            return {"grid": grid_config, "archive": archive_config}

    class UnifiedLayoutEditor(QWidget):
        """
        A unified layout editor that combines both Onigiri widgets and External add-on widgets
        in a single grid, with separate archive zones for each type.
        """
        
        # Default layout configuration for Onigiri widgets
        _ONIGIRI_DEFAULTS = {
            "grid": {
                "studied": {"pos": 0, "row": 1, "col": 1},
                "time": {"pos": 1, "row": 1, "col": 1},
                "pace": {"pos": 2, "row": 1, "col": 1},
                "retention": {"pos": 3, "row": 1, "col": 1},
                "heatmap": {"pos": 4, "row": 2, "col": 4},
            },
            "archive": ["favorites", "restaurant_level"]
        }

        # Default display names for Onigiri widgets
        _WIDGET_DEFINITIONS = {
            "studied": "Studied Card", "time": "Time Card", 
            "pace": "Pace Card", "retention": "Retention Card", "heatmap": "Heatmap",
            "favorites": "Favorites Widget",
            "restaurant_level": "Restaurant Level"
        }

        def __init__(self, settings_dialog):
            super().__init__()
            self.settings_dialog = settings_dialog
            main_layout = QVBoxLayout(self)
            main_layout.setSpacing(15)

            # --- Row Count Control ---
            row_control_layout = QHBoxLayout()
            row_label = QLabel("Grid Height (Rows):") # User friendly label
            row_control_layout.addWidget(row_label)
            self.row_spin = QSpinBox()
            self.row_spin.setRange(1, 20)
            # Get saved row count or default to 6
            current_rows = self.settings_dialog.current_config.get("unifiedGridRows", 6)
            self.row_spin.setValue(current_rows)
            self.row_spin.valueChanged.connect(self._on_row_count_changed)
            row_control_layout.addWidget(self.row_spin)
            row_control_layout.addStretch()
            main_layout.addLayout(row_control_layout)

            # --- Unified Grid ---
            grid_group = QGroupBox("Widget Grid")
            grid_group.setObjectName("LayoutGroup")
            self.grid_zone = SettingsDialog.UnifiedGridDropZone(self, grid_group)
            
            # Apply initial row count
            if current_rows != 6:
                self.grid_zone.update_grid_rows(current_rows)
                
            grid_group_layout = QVBoxLayout(grid_group)
            grid_group_layout.addWidget(self.grid_zone)
            main_layout.addWidget(grid_group)

            # --- Archive Zones Container (side by side) ---
            archives_container = QWidget()
            archives_layout = QHBoxLayout(archives_container)
            archives_layout.setContentsMargins(0, 0, 0, 0)
            archives_layout.setSpacing(15)

            # Scroll Area Stylesheet
            scroll_style = """
                QScrollArea { border: none; background: transparent; }
                QScrollBar:vertical { background: transparent; width: 10px; margin: 0px; }
                QScrollBar::handle:vertical { background: rgba(128, 128, 128, 0.5); min-height: 20px; border-radius: 5px; }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            """

            # Archived Onigiri Widgets
            onigiri_archive_group = QGroupBox("Archived Onigiri Widgets")
            onigiri_archive_group.setObjectName("LayoutGroup")
            
            # Wrap in ScrollArea
            self.onigiri_scroll = QScrollArea()
            self.onigiri_scroll.setWidgetResizable(True)
            self.onigiri_scroll.setFixedHeight(200)
            self.onigiri_scroll.setStyleSheet(scroll_style)
            
            self.onigiri_archive_zone = SettingsDialog.OnigiriArchiveZone(onigiri_archive_group)
            self.onigiri_scroll.setWidget(self.onigiri_archive_zone)
            
            onigiri_archive_layout = QVBoxLayout(onigiri_archive_group)
            onigiri_archive_layout.addWidget(self.onigiri_scroll)
            archives_layout.addWidget(onigiri_archive_group)

            # Archived External Widgets
            external_archive_group = QGroupBox("Archived External Widgets")
            external_archive_group.setObjectName("LayoutGroup")
            
            # Wrap in ScrollArea
            self.external_scroll = QScrollArea()
            self.external_scroll.setWidgetResizable(True)
            self.external_scroll.setFixedHeight(200)
            self.external_scroll.setStyleSheet(scroll_style)
            
            self.external_archive_zone = SettingsDialog.ExternalArchiveZone(external_archive_group)
            self.external_scroll.setWidget(self.external_archive_zone)

            external_archive_layout = QVBoxLayout(external_archive_group)
            external_archive_layout.addWidget(self.external_scroll)
            archives_layout.addWidget(external_archive_group)

            main_layout.addWidget(archives_container)
            
            # --- Reset Buttons ---
            reset_buttons_layout = QHBoxLayout()
            reset_buttons_layout.setSpacing(10)
            
            reset_names_btn = QPushButton("Reset Widget Names")
            reset_names_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            reset_names_btn.clicked.connect(self.reset_widget_names)
            reset_buttons_layout.addWidget(reset_names_btn)
            
            reset_layout_btn = QPushButton("Reset Layout to Default")
            reset_layout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            reset_layout_btn.clicked.connect(self.reset_layout)
            reset_buttons_layout.addWidget(reset_layout_btn)
            
            reset_buttons_layout.addStretch()
            main_layout.addLayout(reset_buttons_layout)

            # Push everything up
            main_layout.addStretch()

            self.all_onigiri_items = {}
            self.all_external_items = {}
            self._populate_widgets()
        
        def _on_row_count_changed(self, rows):
            self.grid_zone.update_grid_rows(rows)

        def _populate_widgets(self):
            if theme_manager.night_mode:
                button_bg, border, fg = "#4a4a4a", "#4a4a4a", "#e0e0e0"
            else:
                button_bg, border, fg = "#f0f0f0", "#e0e0e0", "#212121"
            style_colors = {"button_bg": button_bg, "border": border, "fg": fg}

            # --- Onigiri Widgets ---
            # --- Onigiri Widgets ---
            saved_onigiri_layout = self.settings_dialog.current_config.get("onigiriWidgetLayout", self._ONIGIRI_DEFAULTS)
            
            # Get grid and archive configs
            saved_grid_config = saved_onigiri_layout.get("grid")
            if isinstance(saved_grid_config, dict):
                onigiri_grid_config = copy.deepcopy(saved_grid_config)
            else:
                onigiri_grid_config = copy.deepcopy(self._ONIGIRI_DEFAULTS["grid"])
            
            onigiri_archive_config = saved_onigiri_layout.get("archive")
            if not isinstance(onigiri_archive_config, (list, dict)):
                onigiri_archive_config = self._ONIGIRI_DEFAULTS["archive"]

            # Get archived IDs
            if isinstance(onigiri_archive_config, dict):
                onigiri_archived_ids = set(onigiri_archive_config.keys())
            else:
                onigiri_archived_ids = set(onigiri_archive_config)
            
            # Remove archived items from grid config
            for widget_id in onigiri_archived_ids:
                if widget_id in onigiri_grid_config:
                    del onigiri_grid_config[widget_id]

            # Add missing widgets to grid
            for widget_id, default_pos in self._ONIGIRI_DEFAULTS["grid"].items():
                if widget_id not in onigiri_grid_config and widget_id not in onigiri_archived_ids:
                    onigiri_grid_config[widget_id] = default_pos

            placed_onigiri = set()

            # Create all Onigiri items
            for widget_id, text in self._WIDGET_DEFINITIONS.items():
                item = SettingsDialog.OnigiriDraggableItem(text, widget_id, style_colors)
                item.archive_requested.connect(self._archive_onigiri_item)
                if widget_id == "restaurant_level":
                    item.row_span = 2
                    item.col_span = 2
                self.all_onigiri_items[widget_id] = item

            # Update display names from saved config
            all_saved_onigiri = onigiri_grid_config.copy()
            if isinstance(onigiri_archive_config, dict):
                all_saved_onigiri.update(onigiri_archive_config)
            elif isinstance(onigiri_archive_config, list):
                for widget_id in onigiri_archive_config:
                    all_saved_onigiri.setdefault(widget_id, {})

            for widget_id, item in self.all_onigiri_items.items():
                if saved_item_config := all_saved_onigiri.get(widget_id):
                    if custom_name := saved_item_config.get("display_name"):
                        item.set_display_name(custom_name)

            # Place Onigiri items on unified grid
            for widget_id, config in onigiri_grid_config.items():
                if item := self.all_onigiri_items.get(widget_id):
                    item.row_span = config.get("row", 1)
                    item.col_span = config.get("col", 1)
                    if self.grid_zone.place_item(item, config.get("pos", 0), silent=True):
                        placed_onigiri.add(widget_id)

            # Place Onigiri items in archive
            archive_ids = []
            if isinstance(onigiri_archive_config, list):
                archive_ids = onigiri_archive_config
            elif isinstance(onigiri_archive_config, dict):
                archive_ids = onigiri_archive_config.keys()
            
            for widget_id in archive_ids:
                if item := self.all_onigiri_items.get(widget_id):
                    if widget_id not in placed_onigiri:
                        self.onigiri_archive_zone.layout.insertWidget(self.onigiri_archive_zone.layout.count() - 1, item)
                        placed_onigiri.add(widget_id)

            # Place any unconfigured Onigiri items into archive
            for widget_id, item in self.all_onigiri_items.items():
                if widget_id not in placed_onigiri:
                    self.onigiri_archive_zone.layout.insertWidget(self.onigiri_archive_zone.layout.count() - 1, item)

            # --- External Widgets ---
            saved_external_layout = self.settings_dialog.current_config.get("externalWidgetLayout", {})
            if saved_external_layout and "grid" not in saved_external_layout:
                external_grid_config = saved_external_layout
                external_archive_config = {}
            else:
                external_grid_config = saved_external_layout.get("grid", {})
                external_archive_config = saved_external_layout.get("archive", {})

            external_hooks = self.settings_dialog._get_external_hooks()

            # Create all external items
            debug_shown = False
            for hook_id in external_hooks:
                # Try to get friendly name from addonManager
                addon_id = hook_id.split('.')[0]
                try:
                    display_name = mw.addonManager.addonName(addon_id)
                except:
                    display_name = addon_id

                item = SettingsDialog.DraggableItem(display_name or addon_id, hook_id, style_colors)
                item.archive_requested.connect(self._archive_external_item)
                self.all_external_items[hook_id] = item

            # Combine grid and archive configs for display names
            all_saved_external = {**external_grid_config, **external_archive_config}

            for hook_id, item in self.all_external_items.items():
                if saved_item_config := all_saved_external.get(hook_id):
                    if custom_name := saved_item_config.get("display_name"):
                        # If the custom name is just the package ID, assume it was the old default
                        # and let the new friendly name take precedence.
                        package_id = hook_id.split('.')[0]
                        if custom_name != package_id:
                            item.set_display_name(custom_name)

            placed_external = set()
            
            # Place external items on unified grid
            for hook_id, config in external_grid_config.items():
                if hook_id in self.all_external_items:
                    item = self.all_external_items[hook_id]
                    item.row_span = config.get("row_span", 1)
                    item.col_span = config.get("column_span", 1)
                    if self.grid_zone.place_item(item, config.get("grid_position", 0), silent=True):
                        placed_external.add(hook_id)
            
            # Place external items in archive
            for hook_id in external_archive_config.keys():
                if hook_id in self.all_external_items:
                    item = self.all_external_items[hook_id]
                    self.external_archive_zone.layout.insertWidget(self.external_archive_zone.layout.count() - 1, item)
                    placed_external.add(hook_id)

            # Place any new/unplaced external add-ons in the archive
            for hook_id in external_hooks:
                if hook_id not in placed_external:
                    item = self.all_external_items[hook_id]
                    self.external_archive_zone.layout.insertWidget(self.external_archive_zone.layout.count() - 1, item)

        def _archive_onigiri_item(self, item):
            """Moves an Onigiri item from the grid to the Onigiri archive zone."""
            for shelf in self.grid_zone.shelves.values():
                if shelf.child_widget is item:
                    shelf.child_widget = None
                    shelf.show() # Make the shelf visible again
            self.onigiri_archive_zone.layout.insertWidget(self.onigiri_archive_zone.layout.count() - 1, item)
            # Reset properties and visibility
            item.setProperty("isOnGrid", False)
            item.grid_zone = None
            item._update_size() # Apply compact size
            item.show()
            
            # Reset spans when archiving
            if item.widget_id == "heatmap":
                item.row_span, item.col_span = 2, 4
            elif item.widget_id == "restaurant_level":
                item.row_span, item.col_span = 2, 2
            else:
                item.row_span, item.col_span = 1, 1

        def _archive_external_item(self, item):
            """Moves an external item from the grid to the external archive zone."""
            for shelf in self.grid_zone.shelves.values():
                if shelf.child_widget is item:
                    shelf.child_widget = None
                    shelf.show() # Make the shelf visible again
            self.external_archive_zone.layout.insertWidget(self.external_archive_zone.layout.count() - 1, item)
            item.setProperty("isOnGrid", False)
            item.grid_zone = None
            item._update_size() # Apply compact size
            item.show()

        def get_layout_config(self):
            """Returns separate configs for Onigiri and External layouts."""
            onigiri_grid_config = {}
            external_grid_config = {}
            processed_widgets = set()

            for pos, shelf in self.grid_zone.shelves.items():
                widget = shelf.child_widget
                if widget and widget not in processed_widgets:
                    # Check if it's an Onigiri widget
                    if isinstance(widget, SettingsDialog.OnigiriDraggableItem):
                        onigiri_grid_config[widget.widget_id] = {
                            "pos": pos, "row": widget.row_span, "col": widget.col_span,
                            "display_name": widget.display_name
                        }
                    else:
                        # External widget
                        external_grid_config[widget.widget_id] = {
                            "grid_position": pos, "row_span": widget.row_span, "column_span": widget.col_span,
                            "display_name": widget.display_name
                        }
                    processed_widgets.add(widget)

            onigiri_archive_config = self.onigiri_archive_zone.get_archive_config()
            external_archive_config = self.external_archive_zone.get_archive_config()
            
            return {
                "onigiri": {"grid": onigiri_grid_config, "archive": onigiri_archive_config},
                "external": {"grid": external_grid_config, "archive": external_archive_config}
            }

        def reset_widget_names(self):
            """Resets all widget display names to their defaults."""
            changes_made = False
            
            # Reset Onigiri widgets
            for widget_id, default_name in self._WIDGET_DEFINITIONS.items():
                if item := self.all_onigiri_items.get(widget_id):
                    # Check if name is different to avoid unnecessary updates? 
                    # Simpler to just reset.
                    if item.display_name != default_name:
                        item.set_display_name(default_name)
                        changes_made = True
            
            # Reset External widgets
            for hook_id, item in self.all_external_items.items():
                default_name = hook_id.split('.')[0]
                if item.display_name != default_name:
                    item.set_display_name(default_name)
                    changes_made = True
                    
            if changes_made:
                showInfo("Widget names have been reset to defaults.")
            else:
                showInfo("Widget names are already at defaults.")

        def reset_layout(self):
            """
            Resets everything to default:
            - Grid height = 6 rows
            - Onigiri widgets in default positions
            - All external widgets archived
            """
            # 1. Reset Row Count
            # Block signals to avoid triggering multiple layout updates
            self.row_spin.blockSignals(True)
            self.row_spin.setValue(6) 
            self.row_spin.blockSignals(False)
            
            # Re-initialize grid with 6 rows (this clears current shelves)
            self.grid_zone.row_count = 6
            # We need to manually clear items because update_grid_rows tries to restore them
            # So let's fully clear the grid first
            
            # Move all grid items to a temporary holding state (or just detach them)
            grid_items = []
            for shelf in self.grid_zone.shelves.values():
                if widget := shelf.child_widget:
                    grid_items.append(widget)
                    shelf.child_widget = None
                    widget.setParent(None)
                    widget.grid_zone = None
                    widget.setProperty("isOnGrid", False)
            
            # Also clear layouts of shelves, just in case
            for i in reversed(range(self.grid_zone.grid_layout.count())): 
                item = self.grid_zone.grid_layout.itemAt(i)
                if item.widget():
                    item.widget().setParent(None)
            self.grid_zone.shelves = {}
            
            # Re-create shelves structure for 6 rows
            self.grid_zone.update_grid_rows(6)

            # 2. Reset Onigiri Widgets
            placed_onigiri = set()
            
            # Place default items
            for widget_id, config in self._ONIGIRI_DEFAULTS["grid"].items():
                if item := self.all_onigiri_items.get(widget_id):
                    item.row_span = config.get("row", 1)
                    item.col_span = config.get("col", 1)
                    
                    # Ensure item is clean
                    item.grid_zone = None
                    item.setProperty("isOnGrid", False)
                    
                    if self.grid_zone.place_item(item, config.get("pos", 0), silent=True):
                        placed_onigiri.add(widget_id)
            
            # Archive remaining Onigiri widgets
            for widget_id, item in self.all_onigiri_items.items():
                if widget_id not in placed_onigiri:
                    # Move to archive if not already there
                    current_archive_items = self.onigiri_archive_zone.get_item_order()
                    # If it was on grid, it's now detached. If it was in archive, it might still be there.
                    # Safest is to remove from wherever it is and add to archive
                    if item.parent() == self.onigiri_archive_zone:
                         # Already in archive zone, but maybe we want to reorder? 
                         # Let's just ensure properties are correct
                         pass
                    else:
                        # Add to archive layout
                        self.onigiri_archive_zone.layout.insertWidget(self.onigiri_archive_zone.layout.count() - 1, item)
                    
                    item.setProperty("isOnGrid", False)
                    item.grid_zone = None
                    item._update_size() # Compact size
                    item.show()

            # 3. Archive ALL External Widgets
            for hook_id, item in self.all_external_items.items():
                # Move to archive if not already there
                if item.parent() != self.external_archive_zone:
                     self.external_archive_zone.layout.insertWidget(self.external_archive_zone.layout.count() - 1, item)
                
                item.setProperty("isOnGrid", False)
                item.grid_zone = None
                item.row_span = 1
                item.col_span = 1
                item._update_size() # Compact size
                item.show()

            showInfo("Layout has been reset to defaults.")



    # =================================================================
    # END: Main Menu Layout Editor Widgets
    # =================================================================

    def create_main_menu_page(self):
        page, layout = self._create_scrollable_page()

        # <<< START NEW CODE >>>

        organize_section = SectionGroup(
            "Organize", 
            self, 
            border=False, 
            description="Here you can edit the title of the stats grid, drag and drop to reorder Onigiri's widgets, and organize components from other add-ons into the grid. Right-click on a widget to resize or archive it."
        )
        
        # Add the stats title input to this section
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form_layout.setContentsMargins(15, 0, 15, 10) # Add some padding
        form_layout.addRow("Custom Stats Title:", self.stats_title_input)
    
        # Heatmap Default View - Modern Segmented Control
        self.heatmap_view_group = QButtonGroup(self)
        self.heatmap_view_group.setExclusive(True)
        
        view_container = QWidget()
        view_layout = QHBoxLayout(view_container)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(10)
        
        current_view = self.current_config.get("heatmapDefaultView", "year")
        
        for view_option in ["Year", "Month", "Week"]:
            btn = QPushButton(view_option)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.setProperty("view_mode", view_option.lower())
            
            # Modern styling mimicking a segmented control
            # Note: We use dynamic properties or just check state in styling if needed, 
            # but here we'll use a direct stylesheet for simplicity and consistency with the add-on's theme.
            # Using specific object name to target with stylesheet if possible, or inline styles.
            if theme_manager.night_mode:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #3a3a3a;
                        border: 1px solid #555;
                        border-radius: 6px;
                        color: #eee;
                        padding: 0 15px;
                        font-weight: normal;
                    }}
                    QPushButton:checked {{
                        background-color: {self.accent_color};
                        border: 1px solid {self.accent_color};
                        color: white;
                        font-weight: bold;
                    }}
                    QPushButton:hover:!checked {{
                        background-color: #454545;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #f5f5f5;
                        border: 1px solid #dcdcdc;
                        border-radius: 6px;
                        color: #333;
                        padding: 0 15px;
                        font-weight: normal;
                    }}
                    QPushButton:checked {{
                        background-color: {self.accent_color};
                        border: 1px solid {self.accent_color};
                        color: white;
                        font-weight: bold;
                    }}
                    QPushButton:hover:!checked {{
                        background-color: #e0e0e0;
                    }}
                """)
            
            if view_option.lower() == current_view:
                btn.setChecked(True)
                
            self.heatmap_view_group.addButton(btn)
            view_layout.addWidget(btn)
            
        view_layout.addStretch()
        form_layout.addRow("Default View:", view_container)
        
        organize_section.add_layout(form_layout)
        
        # Create and add the layout editor widget
        self.organize_widget_container = self._create_organize_layout_widget()
        organize_section.add_widget(self.organize_widget_container)
        layout.addWidget(organize_section)

        # --- Main Background Section ---
        user_files_path = os.path.join(self.addon_path, "user_files", "main_bg")
        os.makedirs(user_files_path, exist_ok=True)
        try:
            cached_user_files = sorted([f for f in os.listdir(user_files_path) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))])
        except OSError:
            cached_user_files = []

        mode_group, mode_layout_content = self._create_inner_group("Main Background")
        mode = mw.col.conf.get("modern_menu_background_mode", "color")
        # Fallback for users who have the old "image" mode saved
        if mode == "image":
            mode = "image_color"
            
        # Main mode selection
        mode_layout = QHBoxLayout()
        self.color_radio = QRadioButton("Solid Color")
        self.image_color_radio = QRadioButton("Image")
        self.slideshow_radio = QRadioButton("Slideshow")
        
        # Check the appropriate radio button
        # "Solid Color" covers both "color" and "accent" modes now
        self.color_radio.setChecked(mode == "color" or mode == "accent")
        self.image_color_radio.setChecked(mode == "image_color")
        self.slideshow_radio.setChecked(mode == "slideshow")
        
        mode_layout.addWidget(self.color_radio)
        mode_layout.addWidget(self.image_color_radio)
        mode_layout.addWidget(self.slideshow_radio)
        mode_layout.addStretch()
        mode_layout_content.addLayout(mode_layout)

        # --- Options Containers (Flat Layout) ---
        
        # 1. Color Options (Shared by Color and Image modes)
        self.main_bg_color_group = QWidget()
        main_bg_color_layout = QVBoxLayout(self.main_bg_color_group)
        main_bg_color_layout.setContentsMargins(15, 10, 0, 0)
        
        # Theme Mode Toggle for Colors
        self.color_theme_group = QButtonGroup()
        self.color_theme_single_radio = QRadioButton("One theme color")
        self.color_theme_separate_radio = QRadioButton("Different colors for light/dark themes")
        self.color_theme_accent_radio = QRadioButton("Accent Color") # New option
        
        self.color_theme_group.addButton(self.color_theme_single_radio)
        self.color_theme_group.addButton(self.color_theme_separate_radio)
        self.color_theme_group.addButton(self.color_theme_accent_radio)
        
        # Load saved preference for color theme mode
        # If mode is 'accent', check the accent radio
        if mode == "accent":
            self.color_theme_accent_radio.setChecked(True)
        else:
            color_theme_mode = mw.col.conf.get("modern_menu_bg_color_theme_mode", "single")
            self.color_theme_single_radio.setChecked(color_theme_mode == "single")
            self.color_theme_separate_radio.setChecked(color_theme_mode == "separate")
            # Fallback if somehow neither is checked (though defaults handle this)
            if not self.color_theme_single_radio.isChecked() and not self.color_theme_separate_radio.isChecked():
                 self.color_theme_single_radio.setChecked(True)
        
        color_theme_layout = QHBoxLayout()
        color_theme_layout.addWidget(self.color_theme_single_radio)
        color_theme_layout.addWidget(self.color_theme_separate_radio)
        color_theme_layout.addWidget(self.color_theme_accent_radio)
        color_theme_layout.addStretch()
        main_bg_color_layout.addLayout(color_theme_layout)
        
        current_light_bg = self.current_config.get("colors", {}).get("light", {}).get("--bg", "#FFFFFF")
        current_dark_bg = self.current_config.get("colors", {}).get("dark", {}).get("--bg", "#2C2C2C")
        
        # Single Color Container
        self.bg_color_single_container = QWidget()
        bg_color_single_layout = QVBoxLayout(self.bg_color_single_container)
        bg_color_single_layout.setContentsMargins(0, 0, 0, 0)
        self.bg_single_row = self._create_color_picker_row("Background Color", current_light_bg, "bg_single")
        bg_color_single_layout.addLayout(self.bg_single_row)
        main_bg_color_layout.addWidget(self.bg_color_single_container)
        
        # Separate Colors Container
        self.bg_color_separate_container = QWidget()
        bg_color_separate_layout = QVBoxLayout(self.bg_color_separate_container)
        bg_color_separate_layout.setContentsMargins(0, 0, 0, 0)
        self.bg_light_row = self._create_color_picker_row("Background (Light Mode)", current_light_bg, "bg_light")
        self.bg_dark_row = self._create_color_picker_row("Background (Dark Mode)", current_dark_bg, "bg_dark")
        bg_color_separate_layout.addLayout(self.bg_light_row)
        bg_color_separate_layout.addLayout(self.bg_dark_row)
        main_bg_color_layout.addWidget(self.bg_color_separate_container)
        
        mode_layout_content.addWidget(self.main_bg_color_group)
        
        # Connect color theme toggle
        self.color_theme_single_radio.toggled.connect(self._update_color_theme_visibility)
        self.color_theme_separate_radio.toggled.connect(self._update_color_theme_visibility)
        self.color_theme_accent_radio.toggled.connect(self._update_color_theme_visibility)
        self._update_color_theme_visibility() # Initial state

        # 2. Image Options
        self.main_bg_image_group = QWidget()
        main_bg_image_layout = QVBoxLayout(self.main_bg_image_group)
        main_bg_image_layout.setContentsMargins(15, 10, 0, 0)
        
        # Theme Mode Toggle for Images
        self.image_theme_group = QButtonGroup()
        self.image_theme_single_radio = QRadioButton("One image")
        self.image_theme_separate_radio = QRadioButton("Different images for light/dark themes")
        self.image_theme_group.addButton(self.image_theme_single_radio)
        self.image_theme_group.addButton(self.image_theme_separate_radio)
        
        # Load saved preference for image theme mode
        image_theme_mode = mw.col.conf.get("modern_menu_bg_image_theme_mode", "single")
        self.image_theme_single_radio.setChecked(image_theme_mode == "single")
        self.image_theme_separate_radio.setChecked(image_theme_mode == "separate")
        
        image_theme_layout = QHBoxLayout()
        image_theme_layout.addWidget(self.image_theme_single_radio)
        image_theme_layout.addWidget(self.image_theme_separate_radio)
        image_theme_layout.addStretch()
        main_bg_image_layout.addLayout(image_theme_layout)
        
        # Single Image Container
        self.bg_image_single_container = QWidget()
        bg_image_single_layout = QVBoxLayout(self.bg_image_single_container)
        bg_image_single_layout.setContentsMargins(0, 0, 0, 0)
        self.galleries["main_single"] = {}
        bg_image_single_layout.addWidget(self._create_image_gallery_group("main_single", "user_files/main_bg", "modern_menu_background_image", title="Background Image", image_files_cache=cached_user_files))
        main_bg_image_layout.addWidget(self.bg_image_single_container)
        
        # Separate Images Container (Side-by-Side)
        self.bg_image_separate_container = QWidget()
        bg_image_separate_layout = QHBoxLayout(self.bg_image_separate_container)
        bg_image_separate_layout.setContentsMargins(0, 0, 0, 0)
        bg_image_separate_layout.setSpacing(15)
        
        self.galleries["main_light"] = {}
        bg_image_separate_layout.addWidget(self._create_image_gallery_group("main_light", "user_files/main_bg", "modern_menu_background_image_light", title="Light Mode Background", image_files_cache=cached_user_files))
        
        self.galleries["main_dark"] = {}
        bg_image_separate_layout.addWidget(self._create_image_gallery_group("main_dark", "user_files/main_bg", "modern_menu_background_image_dark", title="Dark Mode Background", image_files_cache=cached_user_files))
        
        main_bg_image_layout.addWidget(self.bg_image_separate_container)
        
        # Connect image theme toggle
        self.image_theme_single_radio.toggled.connect(self._update_image_theme_visibility)
        self.image_theme_separate_radio.toggled.connect(self._update_image_theme_visibility)
        self._update_image_theme_visibility() # Initial state
        
        # Effects
        effects_layout = QHBoxLayout()
        self.bg_blur_label = QLabel("Background Blur:")
        self.bg_blur_spinbox = QSpinBox()
        self.bg_blur_spinbox.setMinimum(0)
        self.bg_blur_spinbox.setMaximum(100)
        self.bg_blur_spinbox.setSuffix(" %")
        self.bg_blur_spinbox.setValue(mw.col.conf.get("modern_menu_background_blur", 0))
        effects_layout.addWidget(self.bg_blur_label)
        effects_layout.addWidget(self.bg_blur_spinbox)
        
        self.bg_opacity_label = QLabel("Background Opacity:")
        self.bg_opacity_spinbox = QSpinBox()
        self.bg_opacity_spinbox.setMinimum(0)
        self.bg_opacity_spinbox.setMaximum(100)
        self.bg_opacity_spinbox.setSuffix(" %")
        self.bg_opacity_spinbox.setValue(mw.col.conf.get("modern_menu_background_opacity", 100))
        effects_layout.addWidget(self.bg_opacity_label)
        effects_layout.addWidget(self.bg_opacity_spinbox)
        effects_layout.addStretch()
        main_bg_image_layout.addLayout(effects_layout)
        
        mode_layout_content.addWidget(self.main_bg_image_group)

        # 3. Slideshow Options
        self.main_bg_slideshow_group = QWidget()
        slideshow_layout = QVBoxLayout(self.main_bg_slideshow_group)
        slideshow_layout.setContentsMargins(15, 10, 0, 0)
        
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Change image every:")
        self.slideshow_interval_spinbox = QSpinBox()
        self.slideshow_interval_spinbox.setMinimum(1)
        self.slideshow_interval_spinbox.setMaximum(3600)
        self.slideshow_interval_spinbox.setSuffix(" seconds")
        self.slideshow_interval_spinbox.setValue(mw.col.conf.get("modern_menu_slideshow_interval", 10))
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.slideshow_interval_spinbox)
        interval_layout.addStretch()
        slideshow_layout.addLayout(interval_layout)
        
        self.slideshow_images_widget = self._create_slideshow_images_selector(cached_user_files)
        slideshow_layout.addWidget(self.slideshow_images_widget)
        
        mode_layout_content.addWidget(self.main_bg_slideshow_group)

        layout.addWidget(mode_group)

        # Connect signals
        self.color_radio.toggled.connect(self.toggle_background_options)
        self.image_color_radio.toggled.connect(self.toggle_background_options)
        self.slideshow_radio.toggled.connect(self.toggle_background_options)
        
        # Initial state
        self.toggle_background_options()
        
        reset_bg_button = QPushButton("Reset Background to Default")
        reset_bg_button.clicked.connect(self.reset_background_to_default)
        layout.addWidget(reset_bg_button)

        


        # <<< END NEW CODE >>>

        heatmap_section = SectionGroup(
            "Heatmap", 
            self, 
            border=False,
            description="Here you can edit the shape of each day on the heatmap and change its color."
        )

        shape_section, shape_layout = self._create_inner_group("Shape")
        shape_selector = self._create_shape_selector()
        shape_layout.addWidget(shape_selector)
        heatmap_section.add_widget(shape_section)

        visibility_section, visibility_layout = self._create_inner_group("Visibility")
        self.heatmap_show_streak_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_streak_check.setChecked(self.current_config.get("heatmapShowStreak", True))
        visibility_layout.addWidget(self._create_toggle_row(self.heatmap_show_streak_check, "Show review streak counter"))
        self.heatmap_show_months_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_months_check.setChecked(self.current_config.get("heatmapShowMonths", True))
        visibility_layout.addWidget(self._create_toggle_row(self.heatmap_show_months_check, "Show month labels (Year view)"))
        self.heatmap_show_weekdays_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_weekdays_check.setChecked(self.current_config.get("heatmapShowWeekdays", True))
        visibility_layout.addWidget(self._create_toggle_row(self.heatmap_show_weekdays_check, "Show weekday labels (Year & Month view)"))
        self.heatmap_show_week_header_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_week_header_check.setChecked(self.current_config.get("heatmapShowWeekHeader", True))
        visibility_layout.addWidget(self._create_toggle_row(self.heatmap_show_week_header_check, "Show day labels (Week view)"))
        heatmap_section.add_widget(visibility_section)

        heatmap_color_modes_layout = QHBoxLayout()
        light_heatmap_group, light_heatmap_layout = self._create_inner_group("Light Mode")
        light_heatmap_layout.setSpacing(5)
        self._populate_pills_for_keys(light_heatmap_layout, "light", ["--heatmap-color", "--heatmap-color-zero"])
        heatmap_color_modes_layout.addWidget(light_heatmap_group)

        dark_heatmap_group, dark_heatmap_layout = self._create_inner_group("Dark Mode")
        dark_heatmap_layout.setSpacing(5)
        self._populate_pills_for_keys(dark_heatmap_layout, "dark", ["--heatmap-color", "--heatmap-color-zero"])
        heatmap_color_modes_layout.addWidget(dark_heatmap_group)
        heatmap_section.add_layout(heatmap_color_modes_layout)

        # Reset Heatmap Colors button
        reset_heatmap_layout = QHBoxLayout()
        reset_heatmap_layout.addStretch()
        reset_heatmap_button = QPushButton("Reset Heatmap Colors")
        reset_heatmap_button.clicked.connect(self.reset_heatmap_colors_to_default)
        reset_heatmap_layout.addWidget(reset_heatmap_button)
        heatmap_section.add_layout(reset_heatmap_layout)

        layout.addWidget(heatmap_section)

        divider2 = QFrame()
        divider2.setFrameShape(QFrame.Shape.HLine)
        divider2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider2)

        star_icon_section = SectionGroup(
            "Star Icon", 
            self, 
            border=False,
            description="Here you can change the star icon and its colors."
        )
        if self.retention_star_widget is None:
            self.retention_star_widget = self._create_icon_control_widget("retention_star")
        star_icon_section.add_widget(self.retention_star_widget)

        self.hide_retention_stars_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_retention_stars_check.setChecked(self.current_config.get("hideRetentionStars", False))
        star_icon_section.add_widget(self._create_toggle_row(self.hide_retention_stars_check, "Hide stars on Retention widget"))

        star_color_modes_layout = QHBoxLayout()
        light_star_group, light_star_layout = self._create_inner_group("Light Mode")
        light_star_layout.setSpacing(5)
        self._populate_pills_for_keys(light_star_layout, "light", ["--star-color", "--empty-star-color"])
        star_color_modes_layout.addWidget(light_star_group)

        dark_star_group, dark_star_layout = self._create_inner_group("Dark Mode")
        dark_star_layout.setSpacing(5)
        self._populate_pills_for_keys(dark_star_layout, "dark", ["--star-color", "--empty-star-color"])
        star_color_modes_layout.addWidget(dark_star_group)
        star_icon_section.add_layout(star_color_modes_layout)
        
        layout.addWidget(star_icon_section)

        reset_button = QPushButton("Reset Stats Colors")
        reset_button.clicked.connect(self.reset_stats_colors_to_default)
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        reset_layout.addWidget(reset_button)
        layout.addLayout(reset_layout)

        layout.addStretch()

        # Add navigation buttons
        sections = {
            "Organize": organize_section,
            "Main Background": mode_group,
            "Heatmap": heatmap_section,
            "Star Icon": star_icon_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections)

        return page

    def _create_organize_layout_widget(self):
        # This widget contains the unified layout editor
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # Use the new unified layout editor
        self.unified_layout_editor = self.UnifiedLayoutEditor(self)
        layout.addWidget(self.unified_layout_editor)
        
        return container
    
    class AdaptiveModeCard(QWidget):
        """A mode card that can switch between vertical and horizontal layouts."""
        def __init__(self, title, toggle_widget, items, addon_path, parent=None):
            super().__init__(parent)
            self.title = title
            self.toggle_widget = toggle_widget
            self.items = items
            self.addon_path = addon_path
            self.current_mode = "vertical"
            
            # Main layout that will hold either vertical or horizontal card
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            
            # Create both layouts
            self.vertical_card = self._create_vertical_layout()
            self.horizontal_card = self._create_horizontal_layout()
            
            # Start with vertical by default
            self.main_layout.addWidget(self.vertical_card)
            self.horizontal_card.hide()
            
        def _create_vertical_layout(self):
            """Create the vertical card layout (original style)."""
            card = QFrame()
            card.setObjectName("hideModeCard")
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            
            # Darker background to match user preference
            if theme_manager.night_mode:
                card.setStyleSheet("""
                    QFrame#hideModeCard {
                        background-color: #1e1e1e;
                        border-radius: 16px;
                        padding: 8px;
                    }
                """)
            else:
                card.setStyleSheet("""
                    QFrame#hideModeCard {
                        background-color: #e8e8e8;
                        border-radius: 16px;
                        padding: 8px;
                    }
                """)

            layout = QVBoxLayout(card)
            layout.setSpacing(12)
            layout.setContentsMargins(8, 15, 8, 20)

            # Title
            title_label = QLabel(self.title)
            title_label.setObjectName("hideModeTitleLabel")
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(title_label)

            # Separator line
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setFrameShadow(QFrame.Shadow.Sunken)
            separator.setStyleSheet("QFrame { background-color: rgba(128, 128, 128, 0.3); max-height: 1px; }")
            layout.addWidget(separator)
            layout.addSpacing(1)

            # Content area for items
            content_widget = QWidget()
            content_widget.setStyleSheet("QWidget { background: transparent; }")
            content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            content_layout = QVBoxLayout(content_widget)
            content_layout.setSpacing(7)
            content_layout.setContentsMargins(0, 0, 0, 0)

            # Add items
            for section_name, item_list in self.items:
                for item in item_list:
                    item_box = QFrame()
                    item_box.setObjectName("hideModeItemBox")
                    
                    is_warning = "Restart Anki" in item or "Windows and Linux" in item
                    
                    if is_warning:
                        if theme_manager.night_mode:
                            bg_color = "rgba(255, 235, 59, 0.15)"
                            text_color = "#fff9c4"
                        else:
                            bg_color = "#fff9c4"
                            text_color = "#665c00"
                        item_box.setStyleSheet(f"""
                            QFrame#hideModeItemBox {{
                                background-color: {bg_color};
                                border-radius: 10px;
                                padding: 12px 10px;
                                min-height: 20px;
                            }}
                        """)
                    else:
                        if theme_manager.night_mode:
                            item_box.setStyleSheet("""
                                QFrame#hideModeItemBox {
                                    background-color: #2c2c2c;
                                    border-radius: 10px;
                                    padding: 12px 10px;
                                    min-height: 20px;
                                }
                            """)
                        else:
                            item_box.setStyleSheet("""
                                QFrame#hideModeItemBox {
                                    background-color: #f2f2f2;
                                    border-radius: 10px;
                                    padding: 12px 10px;
                                    min-height: 20px;
                                }
                            """)
                    
                    box_layout = QHBoxLayout(item_box)
                    box_layout.setContentsMargins(0, 0, 0, 0)
                    
                    item_label = QLabel(item)
                    item_label.setWordWrap(True)
                    
                    if is_warning:
                        item_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        item_label.setStyleSheet(f"font-size: 11px; color: {text_color}; background: transparent; font-weight: bold;")
                    else:
                        item_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        if theme_manager.night_mode:
                            item_label.setStyleSheet("font-size: 11px; color: #f2f2f2; background: transparent;")
                        else:
                            item_label.setStyleSheet("font-size: 11px; color: #2c2c2c; background: transparent;")
                            
                    box_layout.addWidget(item_label)
                    content_layout.addWidget(item_box)

            content_layout.addStretch()
            layout.addWidget(content_widget)

            # Toggle button at bottom using simple alignment
            layout.addStretch()
            layout.addWidget(self.toggle_widget, 0, Qt.AlignmentFlag.AlignHCenter)

            return card
            
        def _create_horizontal_layout(self):
            """Create the horizontal hero-style card layout."""
            card = QFrame()
            card.setObjectName("hideModeHeroCard")
            card.setMinimumHeight(140)
            
            # Darker background to match user preference
            if theme_manager.night_mode:
                card.setStyleSheet("""
                    QFrame#hideModeHeroCard {
                        background-color: #1e1e1e;
                        border-radius: 16px;
                        padding: 20px;
                    }
                """)
            else:
                card.setStyleSheet("""
                    QFrame#hideModeHeroCard {
                        background-color: #e8e8e8;
                        border-radius: 16px;
                        padding: 20px;
                    }
                """)
            
            main_layout = QHBoxLayout(card)
            main_layout.setSpacing(20)
            main_layout.setContentsMargins(20, 20, 20, 20)
            main_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)  # Align all items vertically
            
            # Left side - Title as large text (no icon for modes)
            title_label = QLabel(self.title)
            title_label.setObjectName("hideModeHeroTitle")
            if theme_manager.night_mode:
                title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #e0e0e0; background: transparent;")
            else:
                title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #212121; background: transparent;")
            title_label.setMinimumWidth(80)
            title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            main_layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)
            
            # Center - Features with proper warning styling
            center_widget = QWidget()
            center_layout = QVBoxLayout(center_widget)
            center_layout.setSpacing(6)
            center_layout.setContentsMargins(0, 0, 0, 0)
            
            # Collect all features and check for warnings
            all_features = []
            for section_name, item_list in self.items:
                all_features.extend(item_list)
            
            # Display features, with warnings in yellow containers
            for feature in all_features:
                is_warning = "Restart Anki" in feature or "Windows and Linux" in feature
                
                if is_warning:
                    # Create compact yellow warning container
                    warning_container = QWidget()
                    warning_container_layout = QHBoxLayout(warning_container)
                    warning_container_layout.setContentsMargins(0, 0, 0, 0)
                    
                    warning_box = QFrame()
                    warning_box.setObjectName("hideModeWarningBox")
                    
                    if theme_manager.night_mode:
                        bg_color = "rgba(255, 235, 59, 0.15)"
                        text_color = "#fff9c4"
                    else:
                        bg_color = "#fff9c4"
                        text_color = "#665c00"
                    
                    warning_box.setStyleSheet(f"""
                        QFrame#hideModeWarningBox {{
                            background-color: {bg_color};
                            border-radius: 6px;
                            padding: 6px 12px;
                        }}
                    """)
                    
                    warning_layout = QHBoxLayout(warning_box)
                    warning_layout.setContentsMargins(0, 0, 0, 0)
                    
                    warning_label = QLabel(feature)
                    warning_label.setWordWrap(True)
                    warning_label.setStyleSheet(f"font-size: 10px; color: {text_color}; background: transparent; font-weight: bold;")
                    warning_layout.addWidget(warning_label)
                    
                    # Add warning box to container and align left
                    warning_container_layout.addWidget(warning_box)
                    warning_container_layout.addStretch()
                    
                    center_layout.addWidget(warning_container)
                else:
                    # Regular feature text
                    feature_label = QLabel(f"• {feature}")
                    feature_label.setWordWrap(True)
                    if theme_manager.night_mode:
                        feature_label.setStyleSheet("font-size: 12px; color: #b5bdc7; background: transparent;")
                    else:
                        feature_label.setStyleSheet("font-size: 12px; color: #6b6b6b; background: transparent;")
                    center_layout.addWidget(feature_label)
            
            center_layout.addStretch()
            
            main_layout.addWidget(center_widget, 1)
            
            # Right side - Toggle (aligned vertically with title)
            # Add directly to main layout for proper vertical centering
            main_layout.addWidget(self.toggle_widget, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            return card
            
        def set_layout_mode(self, mode):
            """Switch between vertical and horizontal layouts."""
            if mode == self.current_mode:
                return
                
            self.current_mode = mode
            
            # Remove toggle from current parent before switching
            if self.toggle_widget.parent():
                self.toggle_widget.setParent(None)
            
            if mode == "horizontal":
                self.vertical_card.hide()
                if self.horizontal_card.parent() is None:
                    self.main_layout.addWidget(self.horizontal_card)
                self.horizontal_card.show()
                # Re-add toggle to horizontal layout
                self.horizontal_card.layout().addWidget(self.toggle_widget, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            else:  # vertical
                self.horizontal_card.hide()
                if self.vertical_card.parent() is None:
                    self.main_layout.addWidget(self.vertical_card)
                self.vertical_card.show()
                # Re-add toggle to vertical layout
                self.vertical_card.layout().addWidget(self.toggle_widget, 0, Qt.AlignmentFlag.AlignHCenter)

    def _create_hide_mode_card(self, title, toggle_widget, items):
        """Wrapper method for backwards compatibility - creates AdaptiveModeCard."""
        return self.AdaptiveModeCard(title, toggle_widget, items, self.addon_path, self)
    # <<< END NEW CODE >>>

    def create_onigiri_games_page(self):
        page, layout = self._create_scrollable_page()

        title_label = QLabel("Onigiri Games")
        title_label.setObjectName("onigiriGamesTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(title_label)

        description_label = QLabel(
            "These mini-games are a playful way to make Onigiri more fun while keeping your study sessions feeling fresh."
        )
        description_label.setObjectName("onigiriGamesDescription")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

        # Warning message when gamification mode is disabled
        self.gamification_warning_label = QLabel(
            "⚠️ Gamification Mode is currently disabled. Enable it in Settings → Modes to unlock these mini-games."
        )
        self.gamification_warning_label.setObjectName("gamificationWarning")
        self.gamification_warning_label.setWordWrap(True)
        if theme_manager.night_mode:
            self.gamification_warning_label.setStyleSheet(
                "background-color: #4a3a2a; color: #ffcc80; padding: 12px; border-radius: 8px; font-size: 12px; margin: 10px 0;"
            )
        else:
            self.gamification_warning_label.setStyleSheet(
                "background-color: #fff3cd; color: #856404; padding: 12px; border-radius: 8px; font-size: 12px; margin: 10px 0;"
            )
        layout.addWidget(self.gamification_warning_label)
        
        # Initially hide/show based on gamification mode state
        self.gamification_warning_label.setVisible(not self.gamification_mode_checkbox.isChecked())

        layout.addSpacing(12)
        
        # Set custom color for Restaurant Level toggle
        self.restaurant_level_toggle.accent_color = QColor("#B94632")

        # Restaurant Level card
        restaurant_level_card = self._create_onigiri_game_hero_card(
            icon_filename="restaurant_folder/restaurant_level.png",
            emoji_fallback="\U0001F35F",
            title="Restaurant Level",
            subtitle="Grow your restaurant by completing reviews!",
            background_light="restaurant_lvl_bg.png",
            background_dark="restaurant_lvl_bg_night.png",
            text_color="#B94632",
        )
        
        self._attach_hero_toggle_section(
            restaurant_level_card,
            toggle_widget=self.restaurant_level_toggle,
        )
        
        layout.addWidget(restaurant_level_card)
        layout.addSpacing(16)

        # Mochi Messages card
        mochi_card = self._create_onigiri_game_hero_card(
            icon_filename="mochi_messenger.png",
            emoji_fallback="\U0001F95F",
            title="Mochi Messages",
            subtitle="Let Mochi cheer you on during your review sessions.",
            background_light="mochi_messages_bg.png",
            background_dark="mochi_messages_bg_night.png",
            text_color="#35421C",
        )

        mochi_toggle = AnimatedToggleButton(accent_color="#35421C")
        mochi_toggle.setChecked(self.mochi_messages_toggle.isChecked())

        def handle_games_toggle(checked: bool) -> None:
            if self.mochi_messages_toggle.isChecked() == checked:
                return
            blocker = QSignalBlocker(self.mochi_messages_toggle)
            self.mochi_messages_toggle.setChecked(checked)
            self._on_mochi_messages_toggled(checked)

        def sync_from_settings(checked: bool) -> None:
            if mochi_toggle.isChecked() == checked:
                return
            blocker = QSignalBlocker(mochi_toggle)
            mochi_toggle.setChecked(checked)

        mochi_toggle.toggled.connect(handle_games_toggle)
        self.mochi_messages_toggle.toggled.connect(sync_from_settings)

        def cleanup(_=None, s=self, sync=sync_from_settings) -> None:
            try:
                s.mochi_messages_toggle.toggled.disconnect(sync)
            except (TypeError, RuntimeError):
                # Disconnect might fail if the signal was already disconnected
                pass
            
            # Add stretch if layout is still available
            if hasattr(s, 'layout') and s.layout is not None:
                try:
                    s.layout.addStretch()
                except (RuntimeError, AttributeError):
                    # Layout might be already deleted or in an invalid state
                    pass

        mochi_toggle.destroyed.connect(cleanup)

        self._attach_hero_toggle_section(
            mochi_card,
            toggle_widget=mochi_toggle,
        )

        layout.addWidget(mochi_card)
        layout.addSpacing(16)

        # Focus Dango card
        # Set custom color for Focus Dango toggle
        self.focus_dango_toggle.accent_color = QColor("#61252D")

        focus_dango_card = self._create_onigiri_game_hero_card(
            icon_filename="dango.png",
            emoji_fallback="\U0001F369",
            title="Focus Dango",
            subtitle="Dango-san will prevent you from leaving Reviewer before you're done!",
            background_light="dango_bg.png",
            background_dark="dango_bg.png",
            text_color="#f1aeca",
        )

        self._attach_hero_toggle_section(
            focus_dango_card,
            toggle_widget=self.focus_dango_toggle,
        )

        layout.addWidget(focus_dango_card)
        
        # Store reference to the mochi_toggle for gamification mode control
        self.mochi_toggle_games_page = mochi_toggle
        
        # Initialize the enabled state based on gamification mode
        self._update_gamification_toggles_state()
        
        # Connect gamification mode toggle to update game toggles
        self.gamification_mode_checkbox.toggled.connect(self._update_gamification_toggles_state)
        
        layout.addStretch()
        return page
    
    def _update_gamification_toggles_state(self):
        """Enable/disable and reset Onigiri Games toggles based on Gamification Mode"""
        is_gamification_enabled = self.gamification_mode_checkbox.isChecked()
        
        # Update warning message visibility
        if hasattr(self, 'gamification_warning_label'):
            self.gamification_warning_label.setVisible(not is_gamification_enabled)
        
        # List of all game toggles
        game_toggles = [
            self.restaurant_level_toggle,
            self.mochi_messages_toggle,  # Main mochi toggle
            self.mochi_toggle_games_page if hasattr(self, 'mochi_toggle_games_page') else None,
            self.focus_dango_toggle
        ]
        
        for toggle in game_toggles:
            if toggle is not None:
                toggle.setEnabled(is_gamification_enabled)
                
                # If gamification mode is being disabled, turn off all game toggles
                if not is_gamification_enabled and toggle.isChecked():
                    toggle.setChecked(False)

    def create_restaurant_level_page(self):
        page, layout = self._create_scrollable_page()
        

        
        
        # Restaurant Level Hero
        restaurant_level_card = self._create_onigiri_game_hero_card(
            icon_filename="restaurant_folder/restaurant_level.png",
            emoji_fallback="\U0001F35F",
            title="Restaurant Level",
            subtitle="Grow your restaurant by completing reviews!",
            background_light="restaurant_lvl_bg.png",
            background_dark="restaurant_lvl_bg_night.png",
            text_color="#B94632",
        )
        layout.addWidget(restaurant_level_card)
        layout.addSpacing(16)

        # Restaurant Name Section
        name_group, name_layout = self._create_inner_group("Restaurant Name")
        
        # Check level
        progress = restaurant_level.manager.get_progress()
        
        if progress.level >= 5:
            self.restaurant_name_input = QLineEdit(progress.name)
            self.restaurant_name_input.setPlaceholderText("Enter restaurant name")
            name_layout.addWidget(QLabel("Custom Name:"))
            name_layout.addWidget(self.restaurant_name_input)
            
            help_label = QLabel("Visible on the restaurant level widget.")
            help_label.setStyleSheet("color: #888; font-size: 11px;")
            name_layout.addWidget(help_label)
        else:
            lock_layout = QHBoxLayout()
            lock_icon = QLabel("🔒")
            lock_label = QLabel(f"Reach Level 5 to unlock custom restaurant names. (Current Level: {progress.level})")
            lock_label.setStyleSheet("color: #888; font-style: italic;")
            lock_layout.addWidget(lock_icon)
            lock_layout.addWidget(lock_label)
            lock_layout.addStretch()
            name_layout.addLayout(lock_layout)
            
        layout.addWidget(name_group)

        settings_group, settings_layout = self._create_inner_group("Notifications & Visibility")
        settings_layout.addWidget(self._create_toggle_row(self.restaurant_notifications_toggle, "Show level-up notifications"))
        settings_layout.addWidget(self._create_toggle_row(self.restaurant_bar_toggle, "Show progress on sidebar profile bar"))
        # Removed: settings_layout.addWidget(self._create_toggle_row(self.restaurant_profile_toggle, "Show progress on profile page"))
        settings_layout.addWidget(self._create_toggle_row(self.restaurant_reviewer_toggle, "Show level in reviewer header"))


        layout.addWidget(settings_group)

        reset_group, reset_layout = self._create_inner_group("Reset Progress")
        reset_button = QPushButton("Reset Restaurant Level")
        reset_button.setProperty("onigiri-role", "danger")
        reset_button.clicked.connect(self._confirm_reset_restaurant_level)
        reset_layout.addWidget(reset_button)

        notice_label = QLabel("Resetting clears Restaurant Level XP, level, and related achievements. This cannot be undone.")
        notice_label.setWordWrap(True)
        notice_label.setStyleSheet("color: #6b6b6b; font-size: 11px;")
        reset_layout.addWidget(notice_label)
        layout.addWidget(reset_group)

        layout.addStretch()



        return page

    def _create_onigiri_game_hero_card(
        self,
        *,
        icon_filename: str,
        emoji_fallback: str,
        title: str,
        subtitle: str,
        background_light: str,
        background_dark: str,
        text_color: str,
    ) -> QWidget:
        hero_card = QFrame()
        hero_card.setObjectName("achievementsHeroCard")
        hero_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        hero_card.setMinimumHeight(170)
        hero_card.setProperty("hasBackgroundImage", False)
        hero_card.setStyleSheet("QFrame#achievementsHeroCard { border-radius: 24px; }")

        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(24, 16, 24, 16)
        hero_layout.setSpacing(24)
        hero_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        icon_label = QLabel()
        icon_label.setObjectName("achievementsHeroIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        # Check if the icon is in gamification_images, otherwise use system_files
        gamification_icon_path = os.path.join(self.addon_path, "system_files", "gamification_images", icon_filename)
        if os.path.exists(gamification_icon_path):
            icon_path = gamification_icon_path
        else:
            icon_path = os.path.join(self.addon_path, "system_files", icon_filename)
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon_label.setPixmap(
                pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        else:
            icon_label.setText(emoji_fallback)
        hero_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        copy_container = QWidget()
        copy_container_layout = QVBoxLayout(copy_container)
        copy_container_layout.setContentsMargins(0, 12, 0, 12)
        copy_container_layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("achievementsHeroTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title_label.setStyleSheet(f"color: {text_color}; font-weight: bold;")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("achievementsHeroSubtitle")
        subtitle_label.setWordWrap(True)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        subtitle_label.setStyleSheet(f"color: {text_color};")

        copy_container_layout.addWidget(title_label)
        copy_container_layout.addWidget(subtitle_label)

        hero_layout.addWidget(copy_container, 1, Qt.AlignmentFlag.AlignVCenter)

        # Always use background_light as requested, regardless of theme mode
        background_filename = background_light
        # Check if the background is in gamification_images, otherwise use system_files
        gamification_bg_path = os.path.join(self.addon_path, "system_files", "gamification_images", background_filename)
        if os.path.exists(gamification_bg_path):
            background_path = gamification_bg_path
        else:
            background_path = os.path.join(self.addon_path, "system_files", background_filename)
        if os.path.exists(background_path):
            # Convert backslashes to forward slashes for CSS
            css_path = background_path.replace('\\', '/')
            hero_card.setStyleSheet(
                f"QFrame#achievementsHeroCard {{"
                f"    border-radius: 24px;"
                f"    background-image: url('{css_path}');"
                f"    background-position: left center;"
                f"    background-repeat: repeat-x;"
                f"    background-size: auto 100%;"
                f"}}"
            )
            hero_card.setProperty("hasBackgroundImage", True)

        return hero_card

    def _attach_hero_toggle_section(
        self,
        hero_card: QWidget,
        *,
        toggle_widget: AnimatedToggleButton,
    ) -> None:
        toggle_container = QWidget(hero_card)
        toggle_container.setObjectName("achievementsHeroToggleArea")
        toggle_layout = QVBoxLayout(toggle_container)
        toggle_layout.setContentsMargins(12, 0, 12, 0)
        toggle_layout.setSpacing(4)

        toggle_layout.addWidget(toggle_widget, alignment=Qt.AlignmentFlag.AlignRight)

        hero_card.layout().addWidget(toggle_container, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def _create_section_divider(self) -> QFrame:
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setStyleSheet("QFrame { color: rgba(0, 0, 0, 0.08); margin: 0 12px; }")
        return divider

    def _create_mochi_messages_settings_section(self) -> QWidget:
        section = SectionGroup(
            "Mochi Messages",
            self,
            border=True,
            description="Personalize Mochi's encouragements during your review sessions.",
        )

        interval_row = QWidget()
        interval_layout = QHBoxLayout(interval_row)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        interval_layout.setSpacing(12)

        interval_label = QLabel("Show a Mochi message every")
        interval_label.setWordWrap(True)
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.mochi_interval_spinbox, 0, Qt.AlignmentFlag.AlignLeft)
        interval_layout.addStretch()

        section.add_widget(interval_row)

        messages_label = QLabel("Custom messages")
        messages_label.setStyleSheet("font-weight: bold;")
        section.add_widget(messages_label)

        helper_label = QLabel("Enter one message per line. Mochi will randomly choose from this list when it's time to cheer you on.")
        helper_label.setWordWrap(True)
        helper_color = "#6b6b6b" if not theme_manager.night_mode else "#b5bdc7"
        helper_label.setStyleSheet(f"color: {helper_color}; font-size: 11px;")
        section.add_widget(helper_label)

        section.add_widget(self.mochi_messages_editor)

        return section

    def _on_mochi_messages_toggled(self, enabled: bool) -> None:
        self.mochi_interval_spinbox.setEnabled(enabled)
        self.mochi_messages_editor.setReadOnly(not enabled)
        self.mochi_messages_editor.setEnabled(enabled)
        if not enabled:
            if theme_manager.night_mode:
                disabled_style = (
                    "QPlainTextEdit { background-color: rgba(255, 255, 255, 0.06);"
                    " color: rgba(255, 255, 255, 0.6); }"
                )
            else:
                disabled_style = (
                    "QPlainTextEdit { background-color: rgba(0, 0, 0, 0.04);"
                    " color: rgba(0, 0, 0, 0.55); }"
                )
            self.mochi_messages_editor.setStyleSheet(disabled_style)
        else:
            self.mochi_messages_editor.setStyleSheet("")

    def create_mochi_messages_page(self):
        page, layout = self._create_scrollable_page()

        intro_section = SectionGroup(
            "Mochi Messages",
        self,
            border=False,
            description="Configure how often Mochi appears and what encouragements are shown.",
        )
        info_color = "#6b6b6b" if not theme_manager.night_mode else "#b5bdc7"
        info_label = QLabel(
            "Enable Mochi in Onigiri Settings → Onigiri Games, then customize the cadence and messages here."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"color: {info_color}; font-size: 11px;")
        intro_section.add_widget(info_label)
        
        # Mochi Messages Hero
        mochi_card = self._create_onigiri_game_hero_card(
            icon_filename="mochi_messenger.png",
            emoji_fallback="\U0001F95F",
            title="Mochi Messages",
            subtitle="Let Mochi cheer you on during your review sessions.",
            background_light="mochi_messages_bg.png",
            background_dark="mochi_messages_bg_night.png",
            text_color="#35421C",
        )
        layout.addWidget(mochi_card)
        layout.addSpacing(16)
        
        layout.addWidget(intro_section)

        settings_section = self._create_mochi_messages_settings_section()
        layout.addWidget(settings_section)

        layout.addStretch()

        sections = {
            "Mochi Messages": intro_section,
            "Settings": settings_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections)

        return page

    def create_focus_dango_page(self):
        page, layout = self._create_scrollable_page()

        intro_section = SectionGroup(
            "Focus Dango",
            self,
            border=False,
            description="Dango-san will help you stay focused during your review sessions.",
        )
        info_color = "#6b6b6b" if not theme_manager.night_mode else "#b5bdc7"
        info_label = QLabel(
            "Enable Focus Dango from the Onigiri Games tab, then customize the message here."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"color: {info_color}; font-size: 11px;")
        intro_section.add_widget(info_label)

        # Focus Dango Hero
        focus_dango_card = self._create_onigiri_game_hero_card(
            icon_filename="dango.png",
            emoji_fallback="\U0001F369",
            title="Focus Dango",
            subtitle="Dango-san will prevent you from leaving Reviewer before you're done!",
            background_light="dango_bg.png",
            background_dark="dango_bg.png",
            text_color="#f1aeca",
        )
        layout.addWidget(focus_dango_card)
        layout.addSpacing(16)
        
        layout.addWidget(intro_section)

        # --- Message Editor Section ---
        messages_section = SectionGroup(
            "Focus Dango Messages",
            self,
            border=True,
            description="Personalize Dango-san's encouragements.",
        )

        messages_label = QLabel("Custom messages")
        messages_label.setStyleSheet("font-weight: bold;")
        messages_section.add_widget(messages_label)

        helper_label = QLabel("Enter one message per line. Dango-san will randomly choose from this list.")
        helper_label.setWordWrap(True)
        helper_color = "#6b6b6b" if not theme_manager.night_mode else "#b5bdc7"
        helper_label.setStyleSheet(f"color: {helper_color}; font-size: 11px;")
        messages_section.add_widget(helper_label)

        messages_section.add_widget(self.focus_dango_message_editor)
        
        # Initialize state based on toggle
        self._on_focus_dango_toggled(self.focus_dango_toggle.isChecked())
        self.focus_dango_toggle.toggled.connect(self._on_focus_dango_toggled)
        
        layout.addWidget(messages_section)
        layout.addStretch()

        sections = {
            "Focus Dango": intro_section,
            "Focus Dango Messages": messages_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections)

        return page

    def _on_focus_dango_toggled(self, enabled: bool) -> None:
        self.focus_dango_message_editor.setReadOnly(not enabled)
        self.focus_dango_message_editor.setEnabled(enabled)
        if not enabled:
            if theme_manager.night_mode:
                disabled_style = (
                    "QPlainTextEdit { background-color: rgba(255, 255, 255, 0.06);"
                    " color: rgba(255, 255, 255, 0.6); }"
                )
            else:
                disabled_style = (
                    "QPlainTextEdit { background-color: rgba(0, 0, 0, 0.04);"
                    " color: rgba(0, 0, 0, 0.55); }"
                )
            self.focus_dango_message_editor.setStyleSheet(disabled_style)
        else:
            self.focus_dango_message_editor.setStyleSheet("")

    def create_mr_taiyaki_store_page(self):
        page, layout = self._create_scrollable_page()

        intro_section = SectionGroup(
            "Mr. Taiyaki Store",
            self,
            border=False,
            description="Manage your Mr. Taiyaki Store settings.",
        )
        intro_section.content_area.hide()

        # Mr. Taiyaki Store Hero
        taiyaki_card = self._create_onigiri_game_hero_card(
            icon_filename="mr_taiyaki.png",
            emoji_fallback="\U0001F41F",
            title="Mr. Taiyaki Store",
            subtitle="Manage your Mr. Taiyaki Store settings.",
            background_light="restaurant_folder/wooden_bg.png",
            background_dark="restaurant_folder/wooden_bg.png",
            text_color="#ffffff",
        )
        layout.addWidget(taiyaki_card)
        layout.addSpacing(16)

        layout.addWidget(intro_section)

        # Reset Coins Group
        coins_group, coins_layout = self._create_inner_group("Reset Coins")
        reset_coins_btn = QPushButton("Reset Coins")
        reset_coins_btn.setProperty("onigiri-role", "danger")
        reset_coins_btn.setStyleSheet("QPushButton:hover { color: #ff6b6b; }")
        reset_coins_btn.clicked.connect(self._reset_coins)
        coins_layout.addWidget(reset_coins_btn)
        
        coins_notice = QLabel("Resetting clears your Taiyaki Coins. This cannot be undone.")
        coins_notice.setWordWrap(True)
        coins_notice.setStyleSheet("color: #6b6b6b; font-size: 11px;")
        coins_layout.addWidget(coins_notice)
        layout.addWidget(coins_group)

        # Reset Purchases Group
        purchases_group, purchases_layout = self._create_inner_group("Reset Purchases")
        reset_purchases_btn = QPushButton("Reset Purchases")
        reset_purchases_btn.setProperty("onigiri-role", "danger")
        reset_purchases_btn.setStyleSheet("QPushButton:hover { color: #ff6b6b; }")
        reset_purchases_btn.clicked.connect(self._reset_purchases)
        purchases_layout.addWidget(reset_purchases_btn)
        
        purchases_notice = QLabel("Resetting clears all your purchased items and upgrades. This cannot be undone.")
        purchases_notice.setWordWrap(True)
        purchases_notice.setStyleSheet("color: #6b6b6b; font-size: 11px;")
        purchases_layout.addWidget(purchases_notice)
        layout.addWidget(purchases_group)

        layout.addStretch()



        return page

    def _reset_coins(self):
        reply = QMessageBox.warning(
            self,
            "Reset Coins",
            "Are you sure you want to reset your coins? There is no return nor refund.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Update gamification.json (Source of Truth)
            manager = restaurant_level.RestaurantLevelManager()
            manager.reset_coins()

            # Update local config copy for immediate UI consistency if needed
            if 'restaurant_level' not in self.achievements_config:
                self.achievements_config['restaurant_level'] = {}
            self.achievements_config['restaurant_level']['taiyaki_coins'] = 0
            
            showInfo("Coins have been reset to 0.")

    def _reset_purchases(self):
        reply = QMessageBox.warning(
            self,
            "Reset Purchases",
            "Are you sure you want to reset all purchases? There is no return nor refund.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Update gamification.json (Source of Truth)
            manager = restaurant_level.RestaurantLevelManager()
            manager.reset_purchases()

            # Update local config copy for immediate UI consistency if needed
            if 'restaurant_level' not in self.achievements_config:
                self.achievements_config['restaurant_level'] = {}
            self.achievements_config['restaurant_level']['owned_items'] = ['default']
            self.achievements_config['restaurant_level']['current_theme_id'] = 'default'
            
            showInfo("All purchases have been reset.")
    def _confirm_reset_restaurant_level(self):
        response = QMessageBox.question(
            self,
            "Reset Restaurant Level",
            "Are you sure you want to reset your Restaurant Level? This will clear all XP and reset your level to 0.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if response == QMessageBox.StandardButton.Yes:
            restaurant_level.manager.reset_progress()
            
            # Show success message
            QMessageBox.information(
                self,
                "Reset Complete",
                "Your Restaurant Level has been reset to 0. All XP has been cleared.\n\nThe settings dialog will now close to refresh the UI."
            )
            
            # Trigger a UI refresh by resetting the main window
            if mw:
                mw.reset()
            
            # Close the settings dialog to force a complete refresh
            # When the user reopens it, all values will be reloaded from the config
            self.close()


    class ResponsiveModeCardsContainer(QWidget):
        """Container that switches mode cards between horizontal and vertical layouts based on width."""
        def __init__(self, parent=None):
            super().__init__(parent)
            self.mode_cards = []
            self.current_layout_mode = "vertical"
            self.threshold_width = 900  # Width below which cards switch to horizontal
            
            # Main layout
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            
            # Create initial layout container with horizontal layout
            self.layout_container = QWidget()
            self.current_cards_layout = QHBoxLayout(self.layout_container)
            self.current_cards_layout.setSpacing(20)
            self.current_cards_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.addWidget(self.layout_container)
            
        def add_mode_card(self, card):
            """Add a mode card to the container."""
            self.mode_cards.append(card)
            self.current_cards_layout.addWidget(card)
            
        def resizeEvent(self, event):
            """Handle resize events to switch layouts."""
            super().resizeEvent(event)
            new_width = event.size().width()
            
            # Determine which mode we should be in
            should_be_horizontal = new_width < self.threshold_width
            
            # Switch layouts if needed
            if should_be_horizontal and self.current_layout_mode == "vertical":
                self._switch_to_horizontal_mode()
            elif not should_be_horizontal and self.current_layout_mode == "horizontal":
                self._switch_to_vertical_mode()
                
        def _switch_to_horizontal_mode(self):
            """Switch all cards to horizontal hero-style layout and stack them vertically."""
            self.current_layout_mode = "horizontal"
            
            # Remove all cards from current layout
            while self.current_cards_layout.count():
                item = self.current_cards_layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            
            # Remove and delete old layout container
            self.main_layout.removeWidget(self.layout_container)
            self.layout_container.deleteLater()
            
            # Create new layout container with vertical layout
            self.layout_container = QWidget()
            self.current_cards_layout = QVBoxLayout(self.layout_container)
            self.current_cards_layout.setSpacing(15)
            self.current_cards_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.addWidget(self.layout_container)
            
            # Add cards back in vertical layout and switch card mode
            for card in self.mode_cards:
                card.set_layout_mode("horizontal")
                self.current_cards_layout.addWidget(card)
                
        def _switch_to_vertical_mode(self):
            """Switch all cards to vertical layout and arrange them horizontally."""
            self.current_layout_mode = "vertical"
            
            # Remove all cards from current layout
            while self.current_cards_layout.count():
                item = self.current_cards_layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            
            # Remove and delete old layout container
            self.main_layout.removeWidget(self.layout_container)
            self.layout_container.deleteLater()
            
            # Create new layout container with horizontal layout
            self.layout_container = QWidget()
            self.current_cards_layout = QHBoxLayout(self.layout_container)
            self.current_cards_layout.setSpacing(20)
            self.current_cards_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.addWidget(self.layout_container)
            
            # Add cards back in horizontal layout and switch card mode
            for card in self.mode_cards:
                card.set_layout_mode("vertical")
                self.current_cards_layout.addWidget(card)

    def create_hide_modes_page(self):
        page, layout = self._create_scrollable_page()

        title = QLabel("Modes")
        title.setObjectName("hideModePageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        if theme_manager.night_mode:
            title.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 20px; margin-bottom: 5px; color: #e0e0e0; background-color: #2c2c2c; padding: 0 5px;")
        else:
            title.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 20px; margin-bottom: 5px; color: #212121; background-color: #f3f3f3; padding: 0 5px;")
        layout.addWidget(title)

        description = QLabel(
            "Choose either Focus or Zen Mode to hide elements of the interface for a more immersive experience, "
            "you can also enable Gamification Mode to track achievements and level up, making it fun to study."
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 12px; color: #666; margin-bottom: 8px; padding: 10px;")
        layout.addWidget(description)

        layout.addSpacing(20)

        # Gamification Mode - Horizontal hero card (before the three columns)
        gamification_container = QWidget()
        gamification_container_layout = QHBoxLayout(gamification_container)
        gamification_container_layout.setContentsMargins(0, 0, 0, 0)
        gamification_container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        gamification_card = self._create_gamification_mode_card()
        # gamification_card.setMaximumWidth(650)  # Removed max width constraint
        gamification_container_layout.addWidget(gamification_card)
        
        layout.addWidget(gamification_container)
        layout.addSpacing(20)
        
        # Create responsive container for mode cards
        cards_container = self.ResponsiveModeCardsContainer(self)

        # Define what each mode hides - simplified flat structure
        # Focus mode - Basic hiding
        focus_items = [
            ("", [
                "Hide Anki's native bars",
                "Replaces top bar for a modern one"
            ])
        ]

        # Flow mode - Includes everything from Focus + hides onigiri header
        flow_items = [
            ("", [
                "Everything in Focus",
                "Hides Onigiri's modern top bar",
                "Restart Anki when applying this mode"
            ])
        ]

        # Zen mode - Includes everything from Flow + even more
        zen_items = [
            ("", [
                "Everything in Flow",
                "Hides the bottom bar on Reviewer",
                "(Button only navigation)",
                "Restart Anki when applying this mode"
            ])
        ]

        # Full mode - Hides the top menu bar (File, Edit, View, Tools, Help)
        full_items = [
            ("", [
                "Hide the top menu bar",
                "(File, Edit, View, Tools, Help)",
                "Works on Windows and Linux only",
                "Restart Anki when applying this mode"
            ])
        ]

        # Create mode cards using AdaptiveModeCard
        card1 = self._create_hide_mode_card("Focus", self.hide_native_header_checkbox, focus_items)
        card4 = self._create_hide_mode_card("Flow", self.flow_mode_checkbox, flow_items)
        card3 = self._create_hide_mode_card("Zen", self.max_hide_checkbox, zen_items)
        card_full = self._create_hide_mode_card("Full", self.full_hide_mode_checkbox, full_items)

        # Add cards to responsive container
        cards_container.add_mode_card(card1)
        cards_container.add_mode_card(card4)
        cards_container.add_mode_card(card3)
        cards_container.add_mode_card(card_full)

        layout.addWidget(cards_container)
        
        layout.addStretch()


        
        return page

    def _create_gamification_mode_card(self):
        """Create a horizontal hero card for Gamification Mode"""
        card = QFrame()
        card.setObjectName("gamificationModeCard")
        card.setMinimumHeight(140)
        
        # Style the card
        if theme_manager.night_mode:
            card.setStyleSheet("""
                QFrame#gamificationModeCard {
                    background-color: #3a3a3a;
                    border-radius: 16px;
                    padding: 20px;
                }
            """)
        else:
            card.setStyleSheet("""
                QFrame#gamificationModeCard {
                    background-color: #f9f9f9;
                    border-radius: 16px;
                    padding: 20px;
                }
            """)
        
        main_layout = QHBoxLayout(card)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Icon on the left
        icon_label = QLabel()
        icon_label.setObjectName("gamificationModeIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        
        icon_path = os.path.join(self.addon_path, "system_files", "gamification_images", "gamification.png")
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon_label.setPixmap(
                pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        
        main_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # Center - Title and description
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setSpacing(8)
        center_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("Gamification Mode")
        title_label.setObjectName("gamificationModeTitle")
        if theme_manager.night_mode:
            title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #e0e0e0; background: transparent;")
        else:
            title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #212121; background: transparent;")
        center_layout.addWidget(title_label)
        
        description_label = QLabel("Level up your restaurant, unlock new themes, enjoy Mochi's encouragements, and stay focused with Dango.")
        description_label.setObjectName("gamificationModeDescription")
        description_label.setWordWrap(True)
        if theme_manager.night_mode:
            description_label.setStyleSheet("font-size: 13px; color: #b5bdc7; background: transparent;")
        else:
            description_label.setStyleSheet("font-size: 13px; color: #6b6b6b; background: transparent;")
        center_layout.addWidget(description_label)
        center_layout.addStretch()
        
        main_layout.addWidget(center_widget, 1)
        
        # Right side - Toggle
        toggle_container = QWidget()
        toggle_layout = QVBoxLayout(toggle_container)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        toggle_layout.addWidget(self.gamification_mode_checkbox, alignment=Qt.AlignmentFlag.AlignRight)
        
        main_layout.addWidget(toggle_container, 0, Qt.AlignmentFlag.AlignVCenter)
        
        return card

    def _create_overview_bg_custom_options(self):
        """Create custom background options for the overview screen."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        
        # Color options
        self.overview_bg_color_group = QWidget()
        color_layout = QVBoxLayout(self.overview_bg_color_group)
        color_layout.setContentsMargins(0, 0, 0, 0)
        
        conf = config.get_config()
        
        # Single color container
        self.overview_bg_single_color_container = QWidget()
        single_color_layout = QVBoxLayout(self.overview_bg_single_color_container)
        self.overview_bg_single_color_row = self._create_color_picker_row(
            "Background Color", conf.get("onigiri_overview_bg_light_color", "#FFFFFF"), "overview_bg_single"
        )
        single_color_layout.addLayout(self.overview_bg_single_color_row)
        
        # Separate colors container
        self.overview_bg_separate_colors_container = QWidget()
        separate_colors_layout = QVBoxLayout(self.overview_bg_separate_colors_container)
        self.overview_bg_light_color_row = self._create_color_picker_row(
            "Background (Light Mode)", conf.get("onigiri_overview_bg_light_color", "#FFFFFF"), "overview_bg_light"
        )
        self.overview_bg_dark_color_row = self._create_color_picker_row(
            "Background (Dark Mode)", conf.get("onigiri_overview_bg_dark_color", "#2C2C2C"), "overview_bg_dark"
        )
        separate_colors_layout.addLayout(self.overview_bg_light_color_row)
        separate_colors_layout.addLayout(self.overview_bg_dark_color_row)
        
        # Add both containers to the layout
        color_layout.addWidget(self.overview_bg_single_color_container)
        color_layout.addWidget(self.overview_bg_separate_colors_container)
        
        # Add theme mode toggle for color selection
        self.overview_bg_color_theme_mode_group = QButtonGroup()
        self.overview_bg_color_theme_mode_single = QRadioButton("Use same color for both themes")
        self.overview_bg_color_theme_mode_separate = QRadioButton("Use different colors for light/dark themes")
        self.overview_bg_color_theme_mode_group.addButton(self.overview_bg_color_theme_mode_single)
        self.overview_bg_color_theme_mode_group.addButton(self.overview_bg_color_theme_mode_separate)
        
        # Load saved theme mode or default to single
        # Load saved theme mode or default to single
        overview_bg_color_theme_mode = conf.get("onigiri_overview_bg_color_theme_mode", "single")
        self.overview_bg_color_theme_mode_single.setChecked(overview_bg_color_theme_mode == "single")
        self.overview_bg_color_theme_mode_separate.setChecked(overview_bg_color_theme_mode == "separate")
        
        color_theme_mode_layout = QHBoxLayout()
        color_theme_mode_layout.addWidget(self.overview_bg_color_theme_mode_single)
        color_theme_mode_layout.addWidget(self.overview_bg_color_theme_mode_separate)
        color_theme_mode_layout.addStretch()
        color_theme_mode_container = QWidget()
        color_theme_mode_container.setLayout(color_theme_mode_layout)
        color_theme_mode_container.setContentsMargins(15, 5, 0, 5)
        color_layout.insertWidget(0, color_theme_mode_container)
        
        # Set initial visibility based on theme mode
        self._update_overview_bg_color_theme_mode_visibility()
        
        # Connect theme mode signals for color selection
        self.overview_bg_color_theme_mode_single.toggled.connect(self._update_overview_bg_color_theme_mode_visibility)
        self.overview_bg_color_theme_mode_separate.toggled.connect(self._update_overview_bg_color_theme_mode_visibility)
        
        layout.addWidget(self.overview_bg_color_group)
        
        # Image galleries (only for Image mode)
        self.overview_bg_image_group = QWidget()
        image_layout = QVBoxLayout(self.overview_bg_image_group)
        image_layout.setContentsMargins(0, 10, 0, 0)
        
        # Add theme mode toggle for image selection
        self.overview_bg_image_theme_mode_group = QButtonGroup()
        self.overview_bg_image_theme_mode_single = QRadioButton("Use same image for both themes")
        self.overview_bg_image_theme_mode_separate = QRadioButton("Use different images for light/dark themes")
        self.overview_bg_image_theme_mode_group.addButton(self.overview_bg_image_theme_mode_single)
        self.overview_bg_image_theme_mode_group.addButton(self.overview_bg_image_theme_mode_separate)
        
        # Load saved theme mode or default to single
        # Load saved theme mode or default to single
        overview_bg_image_theme_mode = conf.get("onigiri_overview_bg_image_theme_mode", "single")
        self.overview_bg_image_theme_mode_single.setChecked(overview_bg_image_theme_mode == "single")
        self.overview_bg_image_theme_mode_separate.setChecked(overview_bg_image_theme_mode == "separate")
        
        image_theme_mode_layout = QHBoxLayout()
        image_theme_mode_layout.addWidget(self.overview_bg_image_theme_mode_single)
        image_theme_mode_layout.addWidget(self.overview_bg_image_theme_mode_separate)
        image_theme_mode_layout.addStretch()
        image_theme_mode_container = QWidget()
        image_theme_mode_container.setLayout(image_theme_mode_layout)
        image_theme_mode_container.setContentsMargins(15, 5, 0, 5)
        image_layout.addWidget(image_theme_mode_container)
        
        # Single image container
        self.overview_bg_single_image_container = QWidget()
        single_image_layout = QVBoxLayout(self.overview_bg_single_image_container)
        single_image_layout.setContentsMargins(0, 10, 0, 0)
        self.galleries["overview_bg_single"] = {}
        single_image_layout.addWidget(self._create_image_gallery_group(
            "overview_bg_single", "user_files/main_bg", "onigiri_overview_bg_image", 
            title="Background Image", is_sub_group=True
        ))
        
        # Separate images container
        self.overview_bg_separate_images_container = QWidget()
        sep_layout = QHBoxLayout(self.overview_bg_separate_images_container)
        sep_layout.setContentsMargins(0, 10, 0, 0)
        self.galleries["overview_bg_light"] = {}
        sep_layout.addWidget(self._create_image_gallery_group(
            "overview_bg_light", "user_files/main_bg", "onigiri_overview_bg_image_light", 
            title="Light Mode Background", is_sub_group=True
        ))
        self.galleries["overview_bg_dark"] = {}
        sep_layout.addWidget(self._create_image_gallery_group(
            "overview_bg_dark", "user_files/main_bg", "onigiri_overview_bg_image_dark", 
            title="Dark Mode Background", is_sub_group=True
        ))
        
        # Add both containers to the layout
        image_layout.addWidget(self.overview_bg_single_image_container)
        image_layout.addWidget(self.overview_bg_separate_images_container)
        
        # Set initial visibility based on theme mode
        self._update_overview_bg_image_theme_mode_visibility()
        
        # Connect theme mode signals for image selection
        self.overview_bg_image_theme_mode_single.toggled.connect(self._update_overview_bg_image_theme_mode_visibility)
        self.overview_bg_image_theme_mode_separate.toggled.connect(self._update_overview_bg_image_theme_mode_visibility)
        
        layout.addWidget(self.overview_bg_image_group)
        
        # Effects (blur and opacity)
        self.overview_bg_effects_container = QWidget()
        effects_layout = QHBoxLayout(self.overview_bg_effects_container)
        effects_layout.setContentsMargins(0, 10, 0, 0)
        
        self.overview_bg_blur_label = QLabel("Blur:")
        self.overview_bg_blur_spinbox = QSpinBox()
        self.overview_bg_blur_spinbox.setMinimum(0)
        self.overview_bg_blur_spinbox.setMaximum(100)
        self.overview_bg_blur_spinbox.setSuffix(" %")
        self.overview_bg_blur_spinbox.setValue(conf.get("onigiri_overview_bg_blur", 0))
        
        self.overview_bg_opacity_label = QLabel("Opacity:")
        self.overview_bg_opacity_spinbox = QSpinBox()
        self.overview_bg_opacity_spinbox.setMinimum(0)
        self.overview_bg_opacity_spinbox.setMaximum(100)
        self.overview_bg_opacity_spinbox.setSuffix(" %")
        self.overview_bg_opacity_spinbox.setValue(conf.get("onigiri_overview_bg_opacity", 100))
        
        effects_layout.addWidget(self.overview_bg_blur_label)
        effects_layout.addWidget(self.overview_bg_blur_spinbox)
        effects_layout.addSpacing(20)
        effects_layout.addWidget(self.overview_bg_opacity_label)
        effects_layout.addWidget(self.overview_bg_opacity_spinbox)
        effects_layout.addStretch()
        layout.addWidget(self.overview_bg_effects_container)
        
        # Initially hide image options (only show for Image mode)
        self.overview_bg_image_group.setVisible(False)
        
        return widget
        
    def _update_overview_bg_color_theme_mode_visibility(self):
        """Update visibility of single/separate color pickers for overview background based on theme mode selection."""
        is_single = self.overview_bg_color_theme_mode_single.isChecked()
        self.overview_bg_single_color_container.setVisible(is_single)
        self.overview_bg_separate_colors_container.setVisible(not is_single)
        
        # If switching to single theme mode, update the single color picker with light mode color
        if is_single and hasattr(self, 'overview_bg_light_color_row'):
            light_color = self.overview_bg_light_color_row.itemAt(1).widget().text()
            self.overview_bg_single_color_row.itemAt(1).widget().setText(light_color)
    
    def _update_overview_bg_image_theme_mode_visibility(self):
        """Update visibility of single/separate image galleries for overview background based on theme mode selection."""
        is_single = self.overview_bg_image_theme_mode_single.isChecked()
        self.overview_bg_single_image_container.setVisible(is_single)
        self.overview_bg_separate_images_container.setVisible(not is_single)
        
        # If switching to single theme mode, update the single gallery with light mode image
        if is_single and 'overview_bg_light' in self.galleries and 'overview_bg_single' in self.galleries:
            light_image = self.galleries['overview_bg_light'].get('selected', '')
            if light_image and 'path_input' in self.galleries['overview_bg_single']:
                self.galleries['overview_bg_single']['selected'] = light_image
                self.galleries['overview_bg_single']['path_input'].setText(light_image)
    
    def _toggle_overview_bg_options(self):
        """Toggle visibility of overview background options based on selected mode."""
        is_main = self.overview_bg_main_radio.isChecked()
        self.overview_bg_main_group.setVisible(is_main)
        self.overview_bg_custom_group.setVisible(not is_main)
        
        # Control visibility of color and image options within custom group
        if not is_main:
            is_color = self.overview_bg_color_radio.isChecked()
            is_image_color = self.overview_bg_image_color_radio.isChecked()
            
            # Show color options for both 'Solid Color' and 'Image'
            self.overview_bg_color_group.setVisible(is_color or is_image_color)
            
            # Show image options and effects only for 'Image'
            self.overview_bg_image_group.setVisible(is_image_color)
            self.overview_bg_effects_container.setVisible(is_image_color)
            
            # If this is the first time showing the color group, ensure theme mode visibility is set
            if (is_color or is_image_color) and hasattr(self, 'overview_bg_color_theme_mode_single'):
                self._update_overview_bg_color_theme_mode_visibility()
                
            # If this is the first time showing the image group, ensure theme mode visibility is set
            if is_image_color and hasattr(self, 'overview_bg_image_theme_mode_single'):
                self._update_overview_bg_image_theme_mode_visibility()

    def create_overviews_page(self):
        page, layout = self._create_scrollable_page()
        
        # --- Overviewer Background Section ---
        overview_bg_section = SectionGroup("Overviewer Background", self)
        layout.addWidget(overview_bg_section)
        
        overview_bg_content = overview_bg_section.content_layout
        
        # Background mode radio buttons
        overview_bg_mode_layout = QHBoxLayout()
        overview_bg_button_group = QButtonGroup(overview_bg_section)
        
        self.overview_bg_main_radio = QRadioButton("Use Main Background")
        self.overview_bg_color_radio = QRadioButton("Solid Color")
        self.overview_bg_image_color_radio = QRadioButton("Image")
        
        overview_bg_button_group.addButton(self.overview_bg_main_radio)
        overview_bg_button_group.addButton(self.overview_bg_color_radio)
        overview_bg_button_group.addButton(self.overview_bg_image_color_radio)
        
        conf = config.get_config()
        overview_bg_mode = conf.get("onigiri_overview_bg_mode", "main")
        self.overview_bg_main_radio.setChecked(overview_bg_mode == "main")
        self.overview_bg_color_radio.setChecked(overview_bg_mode == "color")
        self.overview_bg_image_color_radio.setChecked(overview_bg_mode == "image_color")
        
        overview_bg_mode_layout.addWidget(self.overview_bg_main_radio)
        overview_bg_mode_layout.addWidget(self.overview_bg_color_radio)
        overview_bg_mode_layout.addWidget(self.overview_bg_image_color_radio)
        overview_bg_mode_layout.addStretch()
        overview_bg_content.addLayout(overview_bg_mode_layout)
        
        # Main background options (blur and opacity when using main background)
        self.overview_bg_main_group = QWidget()
        main_effects_layout = QHBoxLayout(self.overview_bg_main_group)
        main_effects_layout.setContentsMargins(0, 10, 0, 0)
        
        main_blur_label = QLabel("Background Blur:")
        self.overview_bg_main_blur_spinbox = QSpinBox()
        self.overview_bg_main_blur_spinbox.setMinimum(0)
        self.overview_bg_main_blur_spinbox.setMaximum(100)
        self.overview_bg_main_blur_spinbox.setSuffix(" %")
        self.overview_bg_main_blur_spinbox.setValue(conf.get("onigiri_overview_bg_main_blur", 0))
        
        main_opacity_label = QLabel("Background Opacity:")
        self.overview_bg_main_opacity_spinbox = QSpinBox()
        self.overview_bg_main_opacity_spinbox.setMinimum(0)
        self.overview_bg_main_opacity_spinbox.setMaximum(100)
        self.overview_bg_main_opacity_spinbox.setSuffix(" %")
        self.overview_bg_main_opacity_spinbox.setValue(conf.get("onigiri_overview_bg_main_opacity", 100))
        
        main_effects_layout.addWidget(main_blur_label)
        main_effects_layout.addWidget(self.overview_bg_main_blur_spinbox)
        main_effects_layout.addSpacing(20)
        main_effects_layout.addWidget(main_opacity_label)
        main_effects_layout.addWidget(self.overview_bg_main_opacity_spinbox)
        main_effects_layout.addStretch()
        overview_bg_content.addWidget(self.overview_bg_main_group)
        
        # Custom background options
        self.overview_bg_custom_group = self._create_overview_bg_custom_options()
        overview_bg_content.addWidget(self.overview_bg_custom_group)
        
        # Connect signals
        self.overview_bg_main_radio.toggled.connect(self._toggle_overview_bg_options)
        self.overview_bg_color_radio.toggled.connect(self._toggle_overview_bg_options)
        self.overview_bg_image_color_radio.toggled.connect(self._toggle_overview_bg_options)
        self._toggle_overview_bg_options()

        # Reset button
        reset_btn = QPushButton("Reset to Default Overviewer Background")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(lambda: self.overview_bg_main_radio.setChecked(True))
        overview_bg_content.addWidget(reset_btn)

        overview_section = SectionGroup(
            "",
            self,
            border=False,
            description="Customize the appearance of the deck overview screen."
        )

        # --- NEW: Section for Overview Style ---
        style_section = SectionGroup(
            "Overview Style",
            self,
            border=True,
            description="Choose between a detailed or a compact overview screen."
        )
        style_layout = QHBoxLayout()
        self.overview_pro_radio = QRadioButton("Pro Overview")
        self.overview_pro_radio.setToolTip("The default, detailed overview with large stats and buttons.")
        self.overview_mini_radio = QRadioButton("Mini Overview")
        self.overview_mini_radio.setToolTip("A compact overview, like the one in your provided image.")
        
        current_style = mw.col.conf.get("onigiri_overview_style", "pro")
        if current_style == "mini":
            self.overview_mini_radio.setChecked(True)
        else:
            self.overview_pro_radio.setChecked(True)

        style_layout.addWidget(self.overview_pro_radio)
        style_layout.addWidget(self.overview_mini_radio)
        style_layout.addStretch()
        style_section.add_layout(style_layout)
        overview_section.add_widget(style_section)
        # --- END NEW SECTION ---

        overview_layout = QFormLayout()
        overview_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        overview_layout.addRow("Custom 'Study Now' Text:", self.study_now_input)
        
        overview_color_modes_layout = QHBoxLayout()
        light_overview_colors_group, light_overview_colors_layout = self._create_inner_group("Light Mode Colors")
        light_overview_colors_layout.setSpacing(5)
        overview_color_keys = [
            "--button-primary-bg", "--button-primary-gradient-start", "--button-primary-gradient-end",
            "--new-count-bubble-bg", "--new-count-bubble-fg", "--learn-count-bubble-bg",
            "--learn-count-bubble-fg", "--review-count-bubble-bg", "--review-count-bubble-fg"
        ]
        self._populate_pills_for_keys(light_overview_colors_layout, "light", overview_color_keys)
        overview_color_modes_layout.addWidget(light_overview_colors_group)

        dark_overview_colors_group, dark_overview_colors_layout = self._create_inner_group("Dark Mode Colors")
        dark_overview_colors_layout.setSpacing(5)
        self._populate_pills_for_keys(dark_overview_colors_layout, "dark", overview_color_keys)
        overview_color_modes_layout.addWidget(dark_overview_colors_group)
        
        overview_section.add_layout(overview_color_modes_layout)
        overview_section.add_layout(overview_layout)
        layout.addWidget(overview_section)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider)

        congrats_section = SectionGroup(
            "Congratulations",
            self,
            border=False,
            description="Customize the 'Congratulations, you finished!' screen."
        )
        congrats_layout = QFormLayout()
        congrats_layout.addRow(self._create_toggle_row(self.show_congrats_profile_bar_checkbox, "Show profile bar on congrats screen"))
        congrats_layout.addRow("Custom Message:", self.congrats_message_input)
        congrats_section.add_layout(congrats_layout)
        layout.addWidget(congrats_section)

        layout.addStretch()

        sections = {

            "Overview Style": style_section,
            "Congratulations": congrats_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections)

        return page

    def create_sidebar_page(self):
        page, layout = self._create_scrollable_page()
        sidebar_section = SectionGroup(
            "Sidebar Customization", 
            self, 
            border=False,
            description="Customize general visibility options for the sidebar."
        )
        
        sidebar_section.add_widget(self._create_toggle_row(self.hide_welcome_checkbox, "Hide 'Welcome' message"))
        sidebar_section.add_widget(self._create_toggle_row(self.hide_deck_counts_checkbox, "Hide 0 counts on sidebar"))
        sidebar_section.add_widget(self._create_toggle_row(self.hide_all_deck_counts_checkbox, "Hide deck counts entirely"))

        layout.addWidget(sidebar_section)

        # --- ADD THIS NEW SECTION ---
        organize_section = SectionGroup(
            "Organize Sidebar",
            self,
            border=False,
            description="Drag and drop to re-order or archive sidebar buttons. Changes will apply after restarting Anki."
        )
        self.sidebar_layout_editor = self.SidebarLayoutEditor(self)
        organize_section.add_widget(self.sidebar_layout_editor)
        layout.addWidget(organize_section)
        # --- END NEW SECTION ---

        divider1 = QFrame()
        divider1.setFrameShape(QFrame.Shape.HLine)
        divider1.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider1)

        # --- Sidebar Background Section ---
        sidebar_group, sidebar_layout = self._create_inner_group("Sidebar Background")
        sidebar_mode = mw.col.conf.get("modern_menu_sidebar_bg_mode", "main"); sidebar_mode_layout = QHBoxLayout()
        self.sidebar_bg_main_radio = QRadioButton("Use Main Background Settings"); self.sidebar_bg_custom_radio = QRadioButton("Use Custom Sidebar Background")
        self.sidebar_bg_main_radio.setChecked(sidebar_mode == "main"); self.sidebar_bg_custom_radio.setChecked(sidebar_mode == "custom"); sidebar_mode_layout.addWidget(self.sidebar_bg_main_radio); sidebar_mode_layout.addWidget(self.sidebar_bg_custom_radio); sidebar_layout.addLayout(sidebar_mode_layout)
        
        self.sidebar_main_options_group = QWidget()
        sidebar_main_layout = QVBoxLayout(self.sidebar_main_options_group)
        sidebar_main_layout.setContentsMargins(15, 10, 0, 0)
        
        effect_mode = mw.col.conf.get("onigiri_sidebar_main_bg_effect_mode", "opaque")
        effect_mode_layout = QHBoxLayout()
        self.sidebar_effect_overlay_radio = QRadioButton("Color Overlay")
        self.sidebar_effect_glass_radio = QRadioButton("Glassmorphism")
        self.sidebar_effect_overlay_radio.setChecked(effect_mode == "opaque")
        self.sidebar_effect_glass_radio.setChecked(effect_mode == "glassmorphism")
        effect_mode_layout.addWidget(self.sidebar_effect_overlay_radio)
        effect_mode_layout.addWidget(self.sidebar_effect_glass_radio)
        effect_mode_layout.addStretch()
        sidebar_main_layout.addLayout(effect_mode_layout)

        self.sidebar_overlay_options_group = QWidget()
        overlay_options_layout = QVBoxLayout(self.sidebar_overlay_options_group)
        overlay_options_layout.setContentsMargins(0, 5, 0, 0)

        intensity_layout = QHBoxLayout()
        intensity_label = QLabel("Overlay Opacity:")
        self.sidebar_overlay_intensity_spinbox = QSpinBox()
        self.sidebar_overlay_intensity_spinbox.setMinimum(0)
        self.sidebar_overlay_intensity_spinbox.setMaximum(100)
        self.sidebar_overlay_intensity_spinbox.setSuffix(" %")
        self.sidebar_overlay_intensity_spinbox.setValue(mw.col.conf.get("onigiri_sidebar_opaque_tint_intensity", 30))
        intensity_layout.addWidget(intensity_label)
        intensity_layout.addWidget(self.sidebar_overlay_intensity_spinbox)
        intensity_layout.addStretch()
        

        overlay_options_layout.addLayout(intensity_layout)
        
        self.sidebar_overlay_light_color_row = self._create_color_picker_row("Overlay Color (Light Mode)", mw.col.conf.get("onigiri_sidebar_opaque_tint_color_light", "#FFFFFF"), "overlay_light_color")
        self.sidebar_overlay_dark_color_row = self._create_color_picker_row("Overlay Color (Dark Mode)", mw.col.conf.get("onigiri_sidebar_opaque_tint_color_dark", "#2C2C2C"), "overlay_dark_color")
        overlay_options_layout.addLayout(self.sidebar_overlay_light_color_row)
        overlay_options_layout.addLayout(self.sidebar_overlay_dark_color_row)
        sidebar_main_layout.addWidget(self.sidebar_overlay_options_group)

        self.sidebar_effect_intensity_group = QWidget()
        glass_intensity_layout = QHBoxLayout(self.sidebar_effect_intensity_group)
        glass_intensity_layout.setContentsMargins(0, 5, 0, 0)
        glass_intensity_label = QLabel("Effect Intensity:")
        self.sidebar_effect_intensity_spinbox = QSpinBox()
        self.sidebar_effect_intensity_spinbox.setMinimum(0)
        self.sidebar_effect_intensity_spinbox.setMaximum(100)
        self.sidebar_effect_intensity_spinbox.setSuffix(" %")
        self.sidebar_effect_intensity_spinbox.setValue(mw.col.conf.get("onigiri_sidebar_main_bg_effect_intensity", 50))
        glass_intensity_layout.addWidget(glass_intensity_label)
        glass_intensity_layout.addWidget(self.sidebar_effect_intensity_spinbox)
        glass_intensity_layout.addStretch()
        sidebar_main_layout.addWidget(self.sidebar_effect_intensity_group)
        
        self.sidebar_effect_overlay_radio.toggled.connect(self._toggle_sidebar_effect_options)
        self.sidebar_effect_glass_radio.toggled.connect(self._toggle_sidebar_effect_options)
        self._toggle_sidebar_effect_options()

        sidebar_layout.addWidget(self.sidebar_main_options_group)
        self.sidebar_custom_options_group = self.create_sidebar_custom_options()
        sidebar_layout.addWidget(self.sidebar_custom_options_group)
        
        layout.addWidget(sidebar_group)

        self.sidebar_bg_main_radio.toggled.connect(self.toggle_sidebar_background_options)
        self.toggle_sidebar_background_options()
        
        reset_sidebar_button = QPushButton("Reset Sidebar to Default")
        reset_sidebar_button.clicked.connect(self.reset_sidebar_to_default)
        layout.addWidget(reset_sidebar_button)



        action_buttons_section = SectionGroup(
            "Action Buttons",
            self,
            border=False,
            description="Customize the main action buttons."
        )

        action_buttons_layout = QGridLayout()
        action_buttons_layout.setSpacing(15)
        
        action_icons_to_configure = {
            "add": "Add", "browse": "Browser", "stats": "Stats", 
            "sync": "Sync", "settings": "Settings", "more": "More", 
            "get_shared": "Get Shared", "create_deck": "Create Deck", "import_file": "Import File"
        }
        row, col, num_cols = 0, 0, 3
        for key, label_text in action_icons_to_configure.items():
            card = QWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0,0,0,0)
            card_layout.setSpacing(5)
            
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            
            control_widget = self._create_icon_control_widget(key)
            self.action_button_icon_widgets.append(control_widget)
            
            card_layout.addWidget(label)
            card_layout.addWidget(control_widget)
            action_buttons_layout.addWidget(card, row, col)
            
            col += 1
            if col >= num_cols:
                col = 0
                row += 1
        
        action_buttons_section.add_layout(action_buttons_layout)
        
        layout.addWidget(action_buttons_section)

        divider2 = QFrame()
        divider2.setFrameShape(QFrame.Shape.HLine)
        divider2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider2)
        
        deck_section = SectionGroup(
            "Deck",
            self,
            border=False,
            description="Customize the deck list appearance."
        )

        indentation_group, indentation_layout_content = self._create_inner_group("Decks Indentation")
        
        # --- Modern Button Group UI ---
        # Main layout for the indentation section
        indent_main_layout = QVBoxLayout()
        indentation_layout_content.addLayout(indent_main_layout)
        
        # Create a container for the buttons
        mode_btn_container = QWidget()
        mode_btn_layout = QHBoxLayout(mode_btn_container)
        mode_btn_layout.setContentsMargins(0, 0, 0, 0)
        mode_btn_layout.setSpacing(10)
        
        self.indentation_mode_group = QButtonGroup(self)
        self.indentation_mode_group.setExclusive(True)
        
        modes = [
            ("default", "Default"),
            ("smaller", "Smaller"),
            ("bigger", "Bigger"),
            ("custom", "Custom")
        ]
        
        current_mode = self.current_config.get("deck_indentation_mode", "default")
        
        for key, label in modes:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("indent_mode", key)
            
            # Dynamic styling based on theme
            if theme_manager.night_mode:
                border_color = "#555555"
                text_color = "#eeeeee"
                hover_bg = "rgba(255, 255, 255, 0.1)"
            else:
                border_color = "#cccccc"
                text_color = "#333333"
                hover_bg = "rgba(0, 0, 0, 0.05)"

            btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 8px 15px;
                    border: 1px solid {border_color};
                    border-radius: 6px;
                    background-color: transparent;
                    color: {text_color};
                }}
                QPushButton:checked {{
                    background-color: {self.accent_color};
                    color: white;
                    border-color: {self.accent_color};
                }}
                QPushButton:hover:!checked {{
                    background-color: {hover_bg};
                }}
            """)
            
            if key == current_mode:
                btn.setChecked(True)
                
            self.indentation_mode_group.addButton(btn)
            mode_btn_layout.addWidget(btn)
            
        # Add the button row
        indent_main_layout.addWidget(mode_btn_container)
        
        # Connect signal
        self.indentation_mode_group.buttonClicked.connect(self._on_indentation_mode_btn_clicked)

        # Custom Spinbox Row
        self.indentation_custom_row_widget = QWidget()
        custom_layout = QHBoxLayout(self.indentation_custom_row_widget)
        custom_layout.setContentsMargins(5, 0, 0, 0)
        custom_layout.setSpacing(10)
        
        custom_label = QLabel("Custom Indentation (px):")
        self.indentation_custom_spin = QSpinBox()
        self.indentation_custom_spin.setRange(0, 100)
        self.indentation_custom_spin.setValue(self.current_config.get("deck_indentation_custom_px", 20))
        self.indentation_custom_spin.setSuffix(" px")
        self.indentation_custom_spin.setFixedWidth(120)
        
        custom_layout.addWidget(custom_label)
        custom_layout.addWidget(self.indentation_custom_spin)
        custom_layout.addStretch()
        
        indent_main_layout.addWidget(self.indentation_custom_row_widget)

        # Initial visibility check
        self._on_indentation_mode_btn_clicked(self.indentation_mode_group.checkedButton())

        deck_section.add_widget(indentation_group)
        
        # Custom creation of deck_icons_group to add info button
        deck_icons_group = QFrame()
        deck_icons_group.setObjectName("innerGroup")
        deck_icons_main_layout = QVBoxLayout(deck_icons_group)
        deck_icons_main_layout.setContentsMargins(10, 10, 10, 10)
        deck_icons_main_layout.setSpacing(8)
        
        # Title with info button
        title_row = QHBoxLayout()
        title_label = QLabel("Deck Icons")
        title_label.setStyleSheet("font-weight: bold; font-size: 20px;")
        title_row.addWidget(title_label)
        
        # Info button
        # Info button
        info_button = QPushButton()
        info_button.setFixedSize(24, 24)
        info_button.setCursor(Qt.CursorShape.PointingHandCursor)
        info_button.setToolTip("Click to learn about deck icon types")
        
        info_icon_path = os.path.join(mw.addonManager.addonsFolder(mw.addonManager.addonFromModule(__name__)), 
                                    "system_files", "system_icons", "info-circle.svg")
        
        if os.path.exists(info_icon_path):
            pixmap = QPixmap(info_icon_path)
            if not pixmap.isNull():
                # Color the icon
                painter = QPainter(pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                # Use accent color or text color based on theme
                icon_color = QColor(self.accent_color)
                painter.fillRect(pixmap.rect(), icon_color)
                painter.end()
                info_button.setIcon(QIcon(pixmap))
                info_button.setIconSize(QSize(20, 20))
            
        info_button.setStyleSheet("QPushButton { border: none; background: transparent; }")
        info_button.clicked.connect(self._show_deck_icon_info)
        title_row.addWidget(info_button)
        title_row.addStretch()
        
        deck_icons_main_layout.addLayout(title_row)
        
        # Content area
        deck_icons_content_widget = QWidget()
        deck_icons_layout_content = QVBoxLayout(deck_icons_content_widget)
        deck_icons_layout_content.setContentsMargins(0, 5, 0, 0)
        deck_icons_main_layout.addWidget(deck_icons_content_widget)
        
        deck_icons_layout = QGridLayout(); deck_icons_layout.setSpacing(15)
        deck_icons_layout_content.addLayout(deck_icons_layout)
        deck_icons_to_configure = {"folder": "Folder Icon", "deck": "Deck Icon", "subdeck": "Subdeck Icon", "filtered_deck": "Filtered Deck Icon", "options": "Options Icon", "collapse_closed": "Collapsed Icon (+)", "collapse_open": "Expanded Icon (-)"}
        row, col, num_cols = 0, 0, 3
        for key, label_text in deck_icons_to_configure.items():
            card = QWidget(); card_layout = QVBoxLayout(card); card_layout.setContentsMargins(0,0,0,0); card_layout.setSpacing(5)
            label = QLabel(label_text); label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            control_widget = self._create_icon_control_widget(key); self.icon_assignment_widgets.append(control_widget)
            card_layout.addWidget(label); card_layout.addWidget(control_widget); deck_icons_layout.addWidget(card, row, col)
            col += 1
            if col >= num_cols: col = 0; row += 1
        
        deck_section.add_widget(deck_icons_group)

        sizing_section, sizing_layout_content = self._create_inner_group("Deck Icon Settings")
        sizing_layout = QFormLayout(); sizing_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        sizing_layout_content.addLayout(sizing_layout)
        
        # --- Add Hide Icon Toggles ---
        # Note: Using mw.col.conf.get directly to ensure we load the saved state correctly
        self.hide_folder_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_folder_cb.setChecked(mw.col.conf.get("modern_menu_hide_folder_icon", False))
        self.hide_folder_cb.toggled.connect(self._update_deck_icon_state)
        sizing_layout.addRow("Hide Folder Icon:", self.hide_folder_cb)
        
        self.hide_subdeck_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_subdeck_cb.setChecked(mw.col.conf.get("modern_menu_hide_subdeck_icon", False))
        self.hide_subdeck_cb.toggled.connect(self._update_deck_icon_state)
        sizing_layout.addRow("Hide Subdeck Icon:", self.hide_subdeck_cb)
        
        self.hide_deck_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_deck_cb.setChecked(mw.col.conf.get("modern_menu_hide_deck_icon", False))
        self.hide_deck_cb.toggled.connect(self._update_deck_icon_state)
        sizing_layout.addRow("Hide Deck Icon:", self.hide_deck_cb)

        self.hide_filtered_deck_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_filtered_deck_cb.setChecked(mw.col.conf.get("modern_menu_hide_filtered_deck_icon", False))
        self.hide_filtered_deck_cb.toggled.connect(self._update_deck_icon_state)
        sizing_layout.addRow("Hide Filtered Deck Icon:", self.hide_filtered_deck_cb)

        # [NEW] Hide default, show custom setting
        self.hide_default_custom_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_default_custom_cb.setChecked(mw.col.conf.get("modern_menu_hide_default_icons", False))
        self.hide_default_custom_cb.toggled.connect(self._update_deck_icon_state)
        self.hide_default_custom_cb.setToolTip("If enabled, default icons will be hidden, but custom deck icons will still be shown.")
        sizing_layout.addRow("Hide default, show custom:", self.hide_default_custom_cb)
        
        icon_sizes_to_configure = {"deck_folder": "Deck/Folder Icons (px):", "action_button": "Action Button Icons (px):", "collapse": "Expand/Collapse Icons (px):", "options_gear": "Deck Options Gear Icon (px):"}
        for key, label in icon_sizes_to_configure.items(): sizing_layout.addRow(label, self.create_icon_size_spinbox(key, DEFAULT_ICON_SIZES[key]))
        reset_sizes_button = QPushButton("Reset Sizes to Default"); reset_sizes_button.clicked.connect(self.reset_icon_sizes_to_default); sizing_layout.addRow(reset_sizes_button)
        
        # Initial State Update
        self._update_deck_icon_state()
        
        deck_section.add_widget(sizing_section)

        deck_color_modes_layout = QHBoxLayout()
        light_deck_colors_group, light_deck_colors_layout = self._create_inner_group("Light Mode Colors")
        light_deck_colors_layout.setSpacing(5)
        self._populate_pills_for_keys(light_deck_colors_layout, "light", ["--deck-list-bg", "--highlight-bg", "--highlight-fg", "--icon-color", "--icon-color-filtered"])
        deck_color_modes_layout.addWidget(light_deck_colors_group)

        dark_deck_colors_group, dark_deck_colors_layout = self._create_inner_group("Dark Mode Colors")
        dark_deck_colors_layout.setSpacing(5)
        self._populate_pills_for_keys(dark_deck_colors_layout, "dark", ["--deck-list-bg", "--highlight-bg", "--highlight-fg", "--icon-color", "--icon-color-filtered"])
        deck_color_modes_layout.addWidget(dark_deck_colors_group)
        deck_section.add_layout(deck_color_modes_layout)

        layout.addWidget(deck_section)

        layout.addStretch()
        
        sections = {
            "Sidebar Customization": sidebar_section,
            "Organize Sidebar": organize_section,
            "Sidebar Background": sidebar_group,
            "Action Buttons": action_buttons_section,
            "Deck": deck_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections, buttons_per_row=3)

        return page
    
    def create_profile_tab(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(15)
        
        details_section = SectionGroup("User Details", self)
        form_layout = QFormLayout()
        self.name_input = QLineEdit(self.current_config.get("userName", DEFAULTS["userName"]))
        form_layout.addRow("User Name:", self.name_input)
        
        # Birthday date picker
        accent_color = mw.col.conf.get("modern_menu_accent_color", "#007bff")
        self.birthday_input = BirthdayWidget(accent_color=accent_color)
        birthday_str = self.current_config.get("userBirthday", "")
        if birthday_str:
            try:
                birthday_date = QDate.fromString(birthday_str, "yyyy-MM-dd")
                if birthday_date.isValid():
                    self.birthday_input.setDate(birthday_date)
            except:
                pass

        form_layout.addRow("Birthday:", self.birthday_input)
        
        details_section.add_layout(form_layout)
        layout.addWidget(details_section)

        pic_section = SectionGroup("Profile Picture", self)
        self.galleries["profile_pic"] = {} 
        pic_section.add_widget(self._create_image_gallery_group("profile_pic", "user_files/profile", "modern_menu_profile_picture"))
        layout.addWidget(pic_section)
        
        # --- REBUILT PROFILE BAR BACKGROUND SECTION ---
        bg_section = SectionGroup("Profile Bar Background", self)
        
        # 1. Create Radio Buttons
        bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "accent")
        mode_layout = QHBoxLayout()
        self.profile_bg_accent_radio = QRadioButton("Accent Color")
        self.profile_bg_custom_radio = QRadioButton("Custom Color")
        self.profile_bg_image_radio = QRadioButton("Image")
        mode_layout.addWidget(self.profile_bg_accent_radio)
        mode_layout.addWidget(self.profile_bg_custom_radio)
        mode_layout.addWidget(self.profile_bg_image_radio)
        mode_layout.addStretch()
        bg_section.add_layout(mode_layout)

        # 2. Create the panels for each radio button option
        # Panel for "Custom Color"
        self.profile_bg_color_group = QWidget()
        custom_color_layout = QVBoxLayout(self.profile_bg_color_group)
        custom_color_layout.setContentsMargins(0, 10, 0, 0)
        self.profile_bg_light_row = self._create_color_picker_row("Light Mode", mw.col.conf.get("modern_menu_profile_bg_color_light", "#EEEEEE"), "profile_bg_light")
        self.profile_bg_dark_row = self._create_color_picker_row("Dark Mode", mw.col.conf.get("modern_menu_profile_bg_color_dark", "#3C3C3C"), "profile_bg_dark")
        custom_color_layout.addLayout(self.profile_bg_light_row)
        custom_color_layout.addLayout(self.profile_bg_dark_row)
        custom_color_layout.addStretch(1)


        # Panel for "Image"
        self.galleries["profile_bg"] = {}
        self.profile_bg_image_group = self._create_image_gallery_group("profile_bg", "user_files/profile_bg", "modern_menu_profile_bg_image", is_sub_group=True)

        # 3. Use a QStackedWidget for flicker-free switching
        options_stack = QStackedWidget()
        options_stack.addWidget(QWidget()) # Index 0: A blank widget for "Accent Color"
        options_stack.addWidget(self.profile_bg_color_group)  # Index 1: Custom color panel
        options_stack.addWidget(self.profile_bg_image_group)   # Index 2: Image gallery panel
        bg_section.add_widget(options_stack)

        # 4. Connect radio buttons to the QStackedWidget
        self.profile_bg_accent_radio.clicked.connect(lambda: options_stack.setCurrentIndex(0))
        self.profile_bg_custom_radio.clicked.connect(lambda: options_stack.setCurrentIndex(1))
        self.profile_bg_image_radio.clicked.connect(lambda: options_stack.setCurrentIndex(2))

        # 5. Set the initial state
        if bg_mode == "custom":
            self.profile_bg_custom_radio.setChecked(True)
            options_stack.setCurrentIndex(1)
        elif bg_mode == "image":
            self.profile_bg_image_radio.setChecked(True)
            options_stack.setCurrentIndex(2)
        else: # accent
            self.profile_bg_accent_radio.setChecked(True)
            options_stack.setCurrentIndex(0)

        layout.addWidget(bg_section)
        # --- END OF REBUILT SECTION ---

        page_bg_section = SectionGroup("Profile Page Background", self)
        page_bg_mode = mw.col.conf.get("onigiri_profile_page_bg_mode", "color")
        page_mode_layout = QHBoxLayout()
        self.profile_page_bg_color_radio = QRadioButton("Solid Color"); self.profile_page_bg_gradient_radio = QRadioButton("Gradient")
        self.profile_page_bg_color_radio.setChecked(page_bg_mode == "color"); self.profile_page_bg_gradient_radio.setChecked(page_bg_mode == "gradient")
        page_mode_layout.addWidget(self.profile_page_bg_color_radio); page_mode_layout.addWidget(self.profile_page_bg_gradient_radio); page_mode_layout.addStretch(); page_bg_section.add_layout(page_mode_layout)

        self.profile_page_color_group = QWidget(); page_color_layout = QVBoxLayout(self.profile_page_color_group); page_color_layout.setContentsMargins(0, 10, 0, 0)
        self.profile_page_light_color_row = self._create_color_picker_row("Light Mode Color", mw.col.conf.get("onigiri_profile_page_bg_light_color1", "#F5F5F5"), "profile_page_light_color1"); page_color_layout.addLayout(self.profile_page_light_color_row)
        self.profile_page_dark_color_row = self._create_color_picker_row("Dark Mode Color", mw.col.conf.get("onigiri_profile_page_bg_dark_color1", "#2c2c2c"), "profile_page_dark_color1"); page_color_layout.addLayout(self.profile_page_dark_color_row); page_bg_section.add_widget(self.profile_page_color_group)

        self.profile_page_gradient_group = QWidget(); page_gradient_layout = QVBoxLayout(self.profile_page_gradient_group); page_gradient_layout.setContentsMargins(0, 10, 0, 0)
        self.profile_page_light_gradient1_row = self._create_color_picker_row("Light Mode From", mw.col.conf.get("onigiri_profile_page_bg_light_color1", "#FFFFFF"), "profile_page_light_gradient1"); page_gradient_layout.addLayout(self.profile_page_light_gradient1_row)
        self.profile_page_light_gradient2_row = self._create_color_picker_row("Light Mode To", mw.col.conf.get("onigiri_profile_page_bg_light_color2", "#E0E0E0"), "profile_page_light_gradient2"); page_gradient_layout.addLayout(self.profile_page_light_gradient2_row)
        self.profile_page_dark_gradient1_row = self._create_color_picker_row("Dark Mode From", mw.col.conf.get("onigiri_profile_page_bg_dark_color1", "#424242"), "profile_page_dark_gradient1"); page_gradient_layout.addLayout(self.profile_page_dark_gradient1_row)
        self.profile_page_dark_gradient2_row = self._create_color_picker_row("Dark Mode To", mw.col.conf.get("onigiri_profile_page_bg_dark_color2", "#212121"), "profile_page_dark_gradient2"); page_gradient_layout.addLayout(self.profile_page_dark_gradient2_row); page_bg_section.add_widget(self.profile_page_gradient_group)
        
        self.profile_page_bg_color_radio.toggled.connect(self.toggle_profile_page_bg_options); self.toggle_profile_page_bg_options(); layout.addWidget(page_bg_section)

        visibility_section = SectionGroup("Profile Page Sections Visibility", self)
        self.profile_show_theme_light_check = AnimatedToggleButton(accent_color=self.accent_color); self.profile_show_theme_light_check.setChecked(mw.col.conf.get("onigiri_profile_show_theme_light", True)); visibility_section.add_widget(self._create_toggle_row(self.profile_show_theme_light_check, "Show 'Theme Colors (Light)' Section"))
        self.profile_show_theme_dark_check = AnimatedToggleButton(accent_color=self.accent_color); self.profile_show_theme_dark_check.setChecked(mw.col.conf.get("onigiri_profile_show_theme_dark", True)); visibility_section.add_widget(self._create_toggle_row(self.profile_show_theme_dark_check, "Show 'Theme Colors (Dark)' Section"))
        self.profile_show_backgrounds_check = AnimatedToggleButton(accent_color=self.accent_color); self.profile_show_backgrounds_check.setChecked(mw.col.conf.get("onigiri_profile_show_backgrounds", True)); visibility_section.add_widget(self._create_toggle_row(self.profile_show_backgrounds_check, "Show 'Background Images' Section"))
        self.profile_show_stats_check = AnimatedToggleButton(accent_color=self.accent_color); self.profile_show_stats_check.setChecked(mw.col.conf.get("onigiri_profile_show_stats", True)); visibility_section.add_widget(self._create_toggle_row(self.profile_show_stats_check, "Show 'Daily Stats' Section"))
        
        # Restaurant Level visibility
        self.profile_show_restaurant_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.profile_show_restaurant_check.setChecked(restaurant_level.manager.get_progress().show_profile_page_progress)
        visibility_section.add_widget(self._create_toggle_row(self.profile_show_restaurant_check, "Show 'Restaurant Level' Section"))

        layout.addWidget(visibility_section)
        
        layout.addStretch()
        sections = {
            "User Details": details_section,
            "Profile Picture": pic_section,
            "Profile Bar Background": bg_section,
            "Profile Page Background": page_bg_section,
            "Profile Page Sections Visibility": visibility_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections, buttons_per_row=3)

        return page

    def create_colors_page(self):
        page, layout = self._create_scrollable_page()
        
        # --- Create the Accent Color group first, but don't add it to the main layout yet ---
        accent_group, accent_layout = self._create_inner_group("Accent Color")
        light_accent = self.current_config.get("colors", {}).get("light", {}).get("--accent-color", DEFAULTS["colors"]["light"]["--accent-color"])
        dark_accent = self.current_config.get("colors", {}).get("dark", {}).get("--accent-color", DEFAULTS["colors"]["dark"]["--accent-color"])
        accent_layout.addLayout(self._create_color_picker_row("Light Mode Accent", light_accent, "light_accent", tooltip_text="The main color for buttons and selections in light mode."))
        accent_layout.addLayout(self._create_color_picker_row("Dark Mode Accent", dark_accent, "dark_accent", tooltip_text="The main color for buttons and selections in dark mode."))
        
        # --- Create the General Palette section ---
        general_colors_section = SectionGroup(
            "General Palette", 
            self,
            description="Here you can customize colors that affect more than one space of the add-on"
        )

        # --- Add the Accent Color group to the General Palette section ---
        general_colors_section.add_widget(accent_group)

        # --- START: New Boxes Color Effect Section ---
        canvas_effect_group, canvas_effect_layout = self._create_inner_group("Boxes Color Effect")
        canvas_effect_group.setToolTip("Apply a visual effect to the 'Boxes Color' background color.")

        # Radio buttons for mode selection
        mode_layout = QHBoxLayout()
        self.canvas_effect_none_radio = QRadioButton("None")
        self.canvas_effect_opacity_radio = QRadioButton("Opacity")
        self.canvas_effect_glass_radio = QRadioButton("Glassmorphism")
        mode_layout.addWidget(self.canvas_effect_none_radio)
        mode_layout.addWidget(self.canvas_effect_opacity_radio)
        mode_layout.addWidget(self.canvas_effect_glass_radio)
        mode_layout.addStretch()
        canvas_effect_layout.addLayout(mode_layout)

        # Intensity control
        intensity_layout = QHBoxLayout()
        intensity_label = QLabel("Effect Intensity:")
        self.canvas_effect_intensity_spinbox = QSpinBox()
        self.canvas_effect_intensity_spinbox.setMinimum(0)
        self.canvas_effect_intensity_spinbox.setMaximum(100)
        self.canvas_effect_intensity_spinbox.setSuffix(" %")
        intensity_layout.addWidget(intensity_label)
        intensity_layout.addWidget(self.canvas_effect_intensity_spinbox)
        intensity_layout.addStretch()
        canvas_effect_layout.addLayout(intensity_layout)

        # Load saved settings for canvas effects
        saved_mode = mw.col.conf.get("onigiri_canvas_inset_effect_mode", "none")
        if saved_mode == "opacity":
            self.canvas_effect_opacity_radio.setChecked(True)
        elif saved_mode == "glassmorphism":
            self.canvas_effect_glass_radio.setChecked(True)
        else:
            self.canvas_effect_none_radio.setChecked(True)

        saved_intensity = mw.col.conf.get("onigiri_canvas_inset_effect_intensity", 50)
        self.canvas_effect_intensity_spinbox.setValue(saved_intensity)

        # Connect signals
        self.canvas_effect_none_radio.toggled.connect(self._toggle_canvas_intensity_spinbox)
        self._toggle_canvas_intensity_spinbox() # Set initial state

        general_colors_section.add_widget(canvas_effect_group)
        # --- END: New Boxes Color Effect Section ---
                
        general_modes_layout = QHBoxLayout()

        light_colors_group, light_colors_layout = self._create_inner_group("Light Mode")
        self._build_color_sections(light_colors_layout, "light")
        general_modes_layout.addWidget(light_colors_group)

        dark_colors_group, dark_colors_layout = self._create_inner_group("Dark Mode")
        self._build_color_sections(dark_colors_layout, "dark")
        general_modes_layout.addWidget(dark_colors_group)
        
        general_colors_section.add_layout(general_modes_layout)
        
        # --- Add the combined section to the main page layout ---
        layout.addWidget(general_colors_section)

        reset_button_layout = QHBoxLayout()
        reset_colors_button = QPushButton("Reset Colors to Default")
        reset_colors_button.setToolTip("Resets only the theme colors (accent, text, etc.) to default.")
        reset_colors_button.clicked.connect(self.reset_colors_to_default)

        reset_button_layout.addStretch()
        reset_button_layout.addWidget(reset_colors_button)
        layout.addLayout(reset_button_layout)
        layout.addStretch()
        return page
    
    def create_gallery_page(self):
        """Create a Gallery page showing all applied colors and user images."""
        page, layout = self._create_scrollable_page()
        
        # === COLORS GALLERY SECTION ===
        colors_section = SectionGroup(
            "Colors Gallery",
            self,
            description="All colors currently applied in the add-on, organized by section, to change them, visit the specific page."
        )
        
        # Define color categories with their keys (from colors dict)
        color_categories = {
            "Palette": [
                "--accent-color", "--bg", "--fg", "--fg-subtle", 
                "--border", "--canvas-inset", "--icon-color"
            ],
            "Main Menu": [
                "--heatmap-color", "--heatmap-color-zero", 
                "--star-color", "--empty-star-color", "--highlight-bg"
            ],
            "Sidebar": [
                "--deck-hover-bg", "--deck-dragging-bg", "--deck-edit-mode-bg"
            ],
            "Overviewer": [
                "--button-primary-bg", "--button-primary-gradient-start", 
                "--button-primary-gradient-end",
                "--new-count-bubble-bg", "--new-count-bubble-fg",
                "--learn-count-bubble-bg", "--learn-count-bubble-fg",
                "--review-count-bubble-bg", "--review-count-bubble-fg"
            ],
        }
        
        # Answer button colors (stored in config, not colors dict)
        answer_button_colors = {
            "light": {
                "Again BG": "onigiri_reviewer_btn_again_bg_light",
                "Again Text": "onigiri_reviewer_btn_again_text_light",
                "Hard BG": "onigiri_reviewer_btn_hard_bg_light",
                "Hard Text": "onigiri_reviewer_btn_hard_text_light",
                "Good BG": "onigiri_reviewer_btn_good_bg_light",
                "Good Text": "onigiri_reviewer_btn_good_text_light",
                "Easy BG": "onigiri_reviewer_btn_easy_bg_light",
                "Easy Text": "onigiri_reviewer_btn_easy_text_light",
            },
            "dark": {
                "Again BG": "onigiri_reviewer_btn_again_bg_dark",
                "Again Text": "onigiri_reviewer_btn_again_text_dark",
                "Hard BG": "onigiri_reviewer_btn_hard_bg_dark",
                "Hard Text": "onigiri_reviewer_btn_hard_text_dark",
                "Good BG": "onigiri_reviewer_btn_good_bg_dark",
                "Good Text": "onigiri_reviewer_btn_good_text_dark",
                "Easy BG": "onigiri_reviewer_btn_easy_bg_dark",
                "Easy Text": "onigiri_reviewer_btn_easy_text_dark",
            }
        }
        
        # Get current colors based on theme mode
        mode = "dark" if theme_manager.night_mode else "light"
        current_colors = self.current_config.get("colors", {}).get(mode, {})
        default_colors = DEFAULTS["colors"][mode]
        
        # Create a VERTICAL layout for Light and Dark mode sections (stacked for smaller windows)
        modes_layout = QVBoxLayout()
        modes_layout.setSpacing(15)
        
        # Determine label color based on current theme
        label_color = "#ffffff" if theme_manager.night_mode else "#888"
        
        for display_mode, mode_name in [("light", "Light Mode"), ("dark", "Dark Mode")]:
            mode_colors = self.current_config.get("colors", {}).get(display_mode, {})
            mode_defaults = DEFAULTS["colors"][display_mode]
            
            mode_group, mode_layout = self._create_inner_group(mode_name)
            
            for category_name, color_keys in color_categories.items():
                # Category title
                cat_label = QLabel(category_name)
                cat_label.setStyleSheet("font-weight: bold; margin-top: 10px; margin-bottom: 5px;")
                mode_layout.addWidget(cat_label)
                
                # Create a layout for color swatches, aligned to the left
                swatches_widget = QWidget()
                swatches_layout = QHBoxLayout(swatches_widget)
                swatches_layout.setContentsMargins(0, 0, 0, 5)
                swatches_layout.setSpacing(6)
                
                for color_key in color_keys:
                    color_value = mode_colors.get(color_key, mode_defaults.get(color_key, "#888888"))
                    label_info = COLOR_LABELS.get(color_key, {"label": color_key.replace("--", "").replace("-", " ").title()})
                    
                    # Create swatch widget
                    swatch_container = QWidget()
                    swatch_container.setFixedSize(55, 50)
                    swatch_container.setToolTip(f"{label_info['label']}\n{color_value}")
                    swatch_v_layout = QVBoxLayout(swatch_container)
                    swatch_v_layout.setContentsMargins(2, 2, 2, 2)
                    swatch_v_layout.setSpacing(3)
                    
                    # Color circle
                    swatch = ColorSwatch(color_value)
                    swatch.setFixedSize(22, 22)
                    swatch_v_layout.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignCenter)
                    
                    # Color label (abbreviated) - larger font
                    abbrev_label = label_info['label'][:7] + ".." if len(label_info['label']) > 9 else label_info['label']
                    name_label = QLabel(abbrev_label)
                    name_label.setStyleSheet(f"font-size: 10px; color: {label_color};")
                    name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    swatch_v_layout.addWidget(name_label)
                    
                    swatches_layout.addWidget(swatch_container)
                
                swatches_layout.addStretch()  # Keep swatches aligned left
                mode_layout.addWidget(swatches_widget)
            
            # Add Reviewer Answer Button Colors section
            reviewer_label = QLabel("Reviewer")
            reviewer_label.setStyleSheet("font-weight: bold; margin-top: 10px; margin-bottom: 5px;")
            mode_layout.addWidget(reviewer_label)
            
            btn_swatches_widget = QWidget()
            btn_swatches_layout = QHBoxLayout(btn_swatches_widget)
            btn_swatches_layout.setContentsMargins(0, 0, 0, 5)
            btn_swatches_layout.setSpacing(6)
            
            for label_name, config_key in answer_button_colors[display_mode].items():
                color_value = self.current_config.get(config_key, DEFAULTS.get(config_key, "#888888"))
                
                swatch_container = QWidget()
                swatch_container.setFixedSize(55, 50)
                swatch_container.setToolTip(f"{label_name}\n{color_value}")
                swatch_v_layout = QVBoxLayout(swatch_container)
                swatch_v_layout.setContentsMargins(2, 2, 2, 2)
                swatch_v_layout.setSpacing(3)
                
                swatch = ColorSwatch(color_value)
                swatch.setFixedSize(22, 22)
                swatch_v_layout.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignCenter)
                
                name_label = QLabel(label_name)
                name_label.setStyleSheet(f"font-size: 10px; color: {label_color};")
                name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                swatch_v_layout.addWidget(name_label)
                
                btn_swatches_layout.addWidget(swatch_container)
            
            btn_swatches_layout.addStretch()  # Keep swatches aligned left
            mode_layout.addWidget(btn_swatches_widget)
            
            modes_layout.addWidget(mode_group)
        
        colors_section.add_layout(modes_layout)
        layout.addWidget(colors_section)
        
        # === IMAGES GALLERY SECTION ===
        images_section = SectionGroup(
            "Images Gallery",
            self,
            description="All images uploaded to the add-on, organized by location."
        )
        
        # Define image directories
        image_directories = [
            ("Profile Pictures", "user_files/profile"),
            ("Profile Backgrounds", "user_files/profile_bg"),
            ("Main Menu Backgrounds", "user_files/main_bg"),
            ("Sidebar Backgrounds", "user_files/sidebar_bg"),
            ("Reviewer Backgrounds", "user_files/reviewer_bg"),
            ("Reviewer Bar Backgrounds", "user_files/reviewer_bar_bg"),
        ]
        
        extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp")
        
        for title, folder_path in image_directories:
            full_path = os.path.join(self.addon_path, folder_path)
            
            # Get image files
            try:
                if os.path.exists(full_path):
                    image_files = sorted([f for f in os.listdir(full_path) if f.lower().endswith(extensions)])
                else:
                    image_files = []
            except OSError:
                image_files = []
            
            # Create subsection
            subsection_group, subsection_layout = self._create_inner_group(f"{title} ({len(image_files)})")
            
            if image_files:
                # Create a scroll area for thumbnails
                scroll_area = QScrollArea()
                scroll_area.setWidgetResizable(True)
                scroll_area.setFixedHeight(80)  # Reduced height for smaller windows
                scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
                
                content_widget = QWidget()
                grid_layout = QHBoxLayout(content_widget)
                grid_layout.setSpacing(6)  # Reduced spacing
                grid_layout.setContentsMargins(4, 4, 4, 4)
                grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                
                for filename in image_files[:20]:  # Limit to 20 images per section
                    img_path = os.path.join(full_path, filename)
                    
                    thumb_label = QLabel()
                    thumb_label.setFixedSize(64, 48)  # Smaller thumbnails
                    thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    thumb_label.setToolTip(filename)
                    
                    # Load and scale thumbnail
                    pixmap = QPixmap(img_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(
                            60, 44,  # Slightly smaller for padding
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        # Center crop
                        x = (scaled.width() - 60) // 2
                        y = (scaled.height() - 44) // 2
                        cropped = scaled.copy(x, y, 60, 44)
                        rounded = create_rounded_pixmap(cropped, 6)
                        thumb_label.setPixmap(rounded)
                    else:
                        thumb_label.setText("?")
                        thumb_label.setStyleSheet("background: rgba(128,128,128,0.2); border-radius: 6px;")
                    
                    grid_layout.addWidget(thumb_label)
                
                if len(image_files) > 20:
                    more_label = QLabel(f"+{len(image_files) - 20} more")
                    more_label.setStyleSheet("color: #888; font-size: 11px;")
                    grid_layout.addWidget(more_label)
                
                grid_layout.addStretch()
                scroll_area.setWidget(content_widget)
                subsection_layout.addWidget(scroll_area)
            else:
                no_files = QLabel("No images uploaded")
                no_files.setStyleSheet("color: #888; font-style: italic; padding: 10px;")
                subsection_layout.addWidget(no_files)
            
            images_section.add_widget(subsection_group)
        
        layout.addWidget(images_section)
        layout.addStretch()
        
        # Add navigation buttons
        sections_map = {
            "Colors": colors_section,
            "Images": images_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections_map)
        
        return page


    
    def _toggle_canvas_intensity_spinbox(self):
        is_disabled = self.canvas_effect_none_radio.isChecked()
        self.canvas_effect_intensity_spinbox.setEnabled(not is_disabled)



    def _toggle_sidebar_effect_options(self):
        is_overlay = self.sidebar_effect_overlay_radio.isChecked()
        self.sidebar_overlay_options_group.setVisible(is_overlay)
        self.sidebar_effect_intensity_group.setVisible(not is_overlay)
        
    def _build_color_sections(self, parent_layout, mode):
        sections = {
            "General": ["--fg", "--fg-subtle", "--border", "--canvas-inset"],
        }
        
        handled_keys = {key for keys in sections.values() for key in keys}

        for title, keys in sections.items():
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)

            title_label = QLabel(title)
            title_label.setStyleSheet("font-weight: bold; margin-top: 10px; margin-bottom: 5px;")
            layout.addWidget(title_label)
            
            self._populate_pills_for_keys(layout, mode, keys)
            parent_layout.addWidget(container)

    def _populate_pills_for_keys(self, layout, mode, keys):
        local_color_labels = COLOR_LABELS.copy()
        local_color_labels["--star-color"] = {
            "label": "Star Color",
            "tooltip": "Color for the filled stars in the Retention stat card."
        }
        local_color_labels["--empty-star-color"] = {
            "label": "Empty Star Color",
            "tooltip": "Color for the empty stars in the Retention stat card."
        }
        
        local_defaults = {
            "--star-color": "#FFD700",
            "--empty-star-color": "#e0e0e0" if mode == 'light' else '#4a4a4a'
        }

        colors = self.current_config.get("colors", {}).get(mode, {})
        
        for name in keys:
            if name not in local_color_labels:
                continue

            label_info = local_color_labels[name]
            default_value = DEFAULTS["colors"][mode].get(name, local_defaults.get(name))
            
            if default_value is not None:
                value = colors.get(name, default_value)
                pill_widget = self._create_color_pill(name, value, mode, label_info)
                layout.addWidget(pill_widget)

    def _create_color_pill(self, name, default_value, mode, label_info):
        widget = QFrame()
        widget.setObjectName("colorPill")
        widget.setFixedHeight(36)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        tooltip = label_info.get("tooltip", "")
        widget.setToolTip(f"{label_info['label']}: {tooltip}")
        widget.setMouseTracking(True)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 15, 5)
        layout.setSpacing(10)

        color_swatch = CircularColorButton(default_value)

        text_stack = QStackedWidget()
        text_stack.setStyleSheet("background: transparent;")

        name_label = QLabel(label_info['label'])
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("background: transparent;")

        hex_input = QLineEdit(default_value)
        hex_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if theme_manager.night_mode:
            text_color = "#e0e0e0"
            border_color = "#AAAAAA"
            focus_bg = "rgba(255, 255, 255, 0.1)"
        else:
            text_color = "#212121"
            border_color = "#888888"
            focus_bg = "rgba(0, 0, 0, 0.05)"

        hex_input.setStyleSheet(f"""
            QLineEdit {{ 
                font-family: monospace; 
                background: transparent; 
                border: none; 
                color: {text_color};
                padding: 1px;
            }}
            QLineEdit:focus {{
                border: 1px solid {border_color};
                border-radius: 3px;
                background: {focus_bg};
            }}
        """)
        
        hex_input.textChanged.connect(color_swatch.setColor)
        hex_input.returnPressed.connect(hex_input.clearFocus)
        color_swatch.clicked.connect(lambda _, le=hex_input, btn=color_swatch: self.open_color_picker(le, btn))

        min_width = max(name_label.fontMetrics().horizontalAdvance(label_info['label']), hex_input.fontMetrics().horizontalAdvance("#" + "W"*6)) + 12
        text_stack.setMinimumWidth(min_width)
        
        text_stack.addWidget(name_label)
        text_stack.addWidget(hex_input)

        widget.setProperty("text_stack", text_stack)
        widget.installEventFilter(self)

        layout.addWidget(color_swatch)
        layout.addWidget(text_stack)

        if mode in ["light", "dark"]:
            self.color_widgets[mode][name] = hex_input
        return widget

    def create_sidebar_custom_options(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        
        type_mode = mw.col.conf.get("modern_menu_sidebar_bg_type", "color")
        # If the old 'image' mode was saved, default to 'Image' to prevent a blank state
        if type_mode == 'image':
            type_mode = 'image_color'
            
        type_layout = QHBoxLayout()
        self.sidebar_bg_type_color_radio = QRadioButton("Solid Color")
        self.sidebar_bg_type_accent_radio = QRadioButton("Accent Color")
        self.sidebar_bg_type_image_color_radio = QRadioButton("Image")
        
        self.sidebar_bg_type_color_radio.setChecked(type_mode == "color")
        self.sidebar_bg_type_accent_radio.setChecked(type_mode == "accent")
        self.sidebar_bg_type_image_color_radio.setChecked(type_mode == "image_color")
        
        type_layout.addWidget(self.sidebar_bg_type_color_radio)
        type_layout.addWidget(self.sidebar_bg_type_image_color_radio)
        type_layout.addWidget(self.sidebar_bg_type_accent_radio)
        type_layout.addStretch()
        layout.addLayout(type_layout)

        self.sidebar_color_group = QWidget()
        sidebar_color_layout = QVBoxLayout(self.sidebar_color_group)
        sidebar_color_layout.setContentsMargins(0, 10, 0, 0)
        self.sidebar_bg_light_row = self._create_color_picker_row("Color (Light Mode)", mw.col.conf.get("modern_menu_sidebar_bg_color_light", "#F3F3F3"), "sidebar_bg_light")
        sidebar_color_layout.addLayout(self.sidebar_bg_light_row)
        self.sidebar_bg_dark_row = self._create_color_picker_row("Color (Dark Mode)", mw.col.conf.get("modern_menu_sidebar_bg_color_dark", "#3C3C3C"), "sidebar_bg_dark")
        sidebar_color_layout.addLayout(self.sidebar_bg_dark_row)
        layout.addWidget(self.sidebar_color_group)

        self.galleries["sidebar_bg"] = {}
        self.sidebar_image_group = self._create_image_gallery_group("sidebar_bg", "user_files/sidebar_bg", "modern_menu_sidebar_bg_image", is_sub_group=True)
        layout.addWidget(self.sidebar_image_group)

        self.sidebar_effects_container = QWidget()
        effects_layout = QHBoxLayout(self.sidebar_effects_container)
        effects_layout.setContentsMargins(0, 10, 0, 0)
        
        self.sidebar_bg_blur_label = QLabel("Blur:")
        self.sidebar_bg_blur_spinbox = QSpinBox()
        self.sidebar_bg_blur_spinbox.setMinimum(0)
        self.sidebar_bg_blur_spinbox.setMaximum(100)
        self.sidebar_bg_blur_spinbox.setSuffix(" %")
        self.sidebar_bg_blur_spinbox.setValue(mw.col.conf.get("modern_menu_sidebar_bg_blur", 0))
        effects_layout.addWidget(self.sidebar_bg_blur_label)
        effects_layout.addWidget(self.sidebar_bg_blur_spinbox)

        # ðŸ”½ Opacity and Transparency ðŸ”½
        self.sidebar_bg_opacity_label = QLabel("Image Opacity:")
        self.sidebar_bg_opacity_spinbox = QSpinBox()
        self.sidebar_bg_opacity_spinbox.setMinimum(0)
        self.sidebar_bg_opacity_spinbox.setMaximum(100)
        self.sidebar_bg_opacity_spinbox.setSuffix(" %")
        self.sidebar_bg_opacity_spinbox.setValue(mw.col.conf.get("modern_menu_sidebar_bg_opacity", 100))
        effects_layout.addWidget(self.sidebar_bg_opacity_label)
        effects_layout.addWidget(self.sidebar_bg_opacity_spinbox)

        self.sidebar_bg_transparency_label = QLabel("Transparency:")
        self.sidebar_bg_transparency_spinbox = QSpinBox()
        self.sidebar_bg_transparency_spinbox.setMinimum(0)
        self.sidebar_bg_transparency_spinbox.setMaximum(100)
        self.sidebar_bg_transparency_spinbox.setSuffix(" %")
        self.sidebar_bg_transparency_spinbox.setValue(mw.col.conf.get("modern_menu_sidebar_bg_transparency", 0))
        effects_layout.addWidget(self.sidebar_bg_transparency_label)
        effects_layout.addWidget(self.sidebar_bg_transparency_spinbox)
        # ðŸ”¼ Opacity and Transparency ðŸ”¼

        effects_layout.addStretch()
        layout.addWidget(self.sidebar_effects_container)

        self.sidebar_bg_type_color_radio.toggled.connect(self.toggle_sidebar_bg_type_options)
        self.sidebar_bg_type_image_color_radio.toggled.connect(self.toggle_sidebar_bg_type_options)
        self.sidebar_bg_type_accent_radio.toggled.connect(self.toggle_sidebar_bg_type_options)
        
        self.toggle_sidebar_bg_type_options()
        return widget

    def _create_slideshow_images_selector(self, image_files_cache):
        """Creates a gallery widget for selecting multiple images for slideshow mode."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        
        # Instructions label
        instructions = QLabel("Select images to include in the slideshow (click on images to toggle selection):")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Scroll area for image gallery
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(400)
        
        scroll_content = QWidget()
        scroll_layout = QGridLayout(scroll_content)
        scroll_layout.setSpacing(10)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        
        # Get saved slideshow images
        saved_images = mw.col.conf.get("modern_menu_slideshow_images", [])
        
        # Get the user files path - CORRECTED PATH
        addon_path = os.path.dirname(__file__)
        user_bg_folder = os.path.join(addon_path, "user_files", "main_bg")
        
        # Create gallery items for each image
        self.slideshow_image_items = []
        row, col = 0, 0
        max_cols = 4  # 4 images per row
        
        for img_file in image_files_cache:
            # Create container for image + checkbox
            item_widget = QWidget()
            item_widget.setObjectName("galleryItem")
            item_widget.setFixedSize(120, 90)
            item_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Store the filename and checked state
            item_widget.img_filename = img_file
            item_widget.is_checked = img_file in saved_images
            
            # Create the image label
            img_path = os.path.join(user_bg_folder, img_file)
            img_label = QLabel(item_widget)
            img_label.setFixedSize(120, 90)
            img_label.setScaledContents(False)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Load and display the image with rounded corners
            if os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                if not pixmap.isNull():
                    # Scale to fit while maintaining aspect ratio
                    scaled_pixmap = pixmap.scaled(
                        120, 90,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    # Crop from center
                    crop_x = (scaled_pixmap.width() - 120) / 2
                    crop_y = (scaled_pixmap.height() - 90) / 2
                    cropped_pixmap = scaled_pixmap.copy(int(crop_x), int(crop_y), 120, 90)
                    
                    # Apply rounded corners
                    rounded_pixmap = create_rounded_pixmap(cropped_pixmap, 10)
                    img_label.setPixmap(rounded_pixmap)
            
            # Create custom selection overlay using accent color
            overlay = SelectionOverlay(item_widget, accent_color=self.accent_color)
            overlay.setChecked(item_widget.is_checked)
            overlay.move(90, 5)  # Top-right corner (120 - 24 - 6 padding)
            
            # Store overlay reference
            item_widget.overlay = overlay
            
            # Apply border styling based on selection
            self._update_slideshow_item_border(item_widget)
            
            # Connect click events
            def make_click_handler(widget):
                def handler(event):
                    widget.is_checked = not widget.is_checked
                    widget.overlay.setChecked(widget.is_checked)
                    self._update_slideshow_item_border(widget)
                return handler
            
            item_widget.mousePressEvent = make_click_handler(item_widget)
            
            # Add to grid
            scroll_layout.addWidget(item_widget, row, col)
            self.slideshow_image_items.append(item_widget)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Add/Remove buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._toggle_all_slideshow_images(True))
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self._toggle_all_slideshow_images(False))
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        return widget
    
    def _update_slideshow_item_border(self, item_widget):
        """Update the border style of a slideshow gallery item based on selection state."""
        if item_widget.is_checked:
            item_widget.setStyleSheet(f"""
                #galleryItem {{
                    border: 3px solid {self.accent_color};
                    border-radius: 10px;
                    background: transparent;
                }}
            """)
        else:
            item_widget.setStyleSheet("""
                #galleryItem {
                    border: 2px solid transparent;
                    border-radius: 10px;
                    background: transparent;
                }
                #galleryItem:hover {
                    border: 2px solid #888888;
                }
            """)
    
    def _on_slideshow_checkbox_toggled(self, item_widget, checked):
        """Handle checkbox toggle for slideshow gallery items."""
        item_widget.is_checked = checked
        item_widget.overlay.setChecked(checked)
        self._update_slideshow_item_border(item_widget)
    
    def _toggle_all_slideshow_images(self, checked):
        """Toggle all slideshow image gallery items."""
        for item in self.slideshow_image_items:
            item.is_checked = checked
            item.overlay.setChecked(checked)
            self._update_slideshow_item_border(item)


    def _get_svg_icon(self, path: str) -> Union[QIcon, None]:
        if not os.path.exists(path):
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                svg_data = f.read()

            icon_color = "#e0e0e0" if theme_manager.night_mode else "#212121"
            if 'currentColor' in svg_data:
                colored_svg = svg_data.replace('currentColor', icon_color)
            else:
                colored_svg = svg_data.replace('<svg', f'<svg fill="{icon_color}"', 1)

            renderer = QSvgRenderer(colored_svg.encode('utf-8'))
            pixmap = QPixmap(renderer.defaultSize())
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return QIcon(pixmap)
        except Exception as e:
            print(f"Onigiri: Error rendering SVG icon at {path}: {e}")
            return None
    
    def _create_delete_icon(self) -> Union[QIcon, None]:
        """Loads and colors the xmark.svg icon for the delete button."""
        icon_path = os.path.join(self.addon_path, "system_files", "system_icons", "xmark.svg")
        if not os.path.exists(icon_path):
            return None

        # Use a subtle text color for the icon
        conf = config.get_config()
        if theme_manager.night_mode:
            icon_color = conf.get("colors", {}).get("dark", {}).get("--fg-subtle", "#908caa")
        else:
            icon_color = conf.get("colors", {}).get("light", {}).get("--fg-subtle", "#797593")

        try:
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_data = f.read()

            # Replace currentColor if it exists, otherwise add a fill attribute
            if 'currentColor' in svg_data:
                colored_svg = svg_data.replace('currentColor', icon_color)
            else:
                colored_svg = svg_data.replace('<svg', f'<svg fill="{icon_color}"', 1)

            renderer = QSvgRenderer(colored_svg.encode('utf-8'))
            pixmap = QPixmap(renderer.defaultSize())
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return QIcon(pixmap)
        except Exception as e:
            print(f"Onigiri: Error rendering SVG icon at {icon_path}: {e}")
            return None
        
    def _on_shape_selected(self):
        sender = self.sender()
        if sender and sender.isChecked():
            self.selected_heatmap_shape = sender.property("shape_filename")

    def _reflow_shape_icons(self, width=0):
        # Use a fixed horizontal layout instead of dynamic resizing
        if not hasattr(self, 'shape_buttons') or not self.shape_buttons:
            return
        
        if not hasattr(self, 'shapes_grid_layout') or self.shapes_grid_layout is None:
            return
        
        # Clear layout but keep widgets in self.shape_buttons
        while item := self.shapes_grid_layout.takeAt(0):
            if item.widget():
                item.widget().setParent(None)

        # Use a fixed number of columns for horizontal layout (6 icons per row)
        num_cols = 6
        
        # Repopulate the grid from the master list of buttons
        for i, button in enumerate(self.shape_buttons):
            if button is not None:
                row, col = divmod(i, num_cols)
                self.shapes_grid_layout.addWidget(button, row, col)

    def _create_shape_selector(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setFixedHeight(250)
        
        self.shape_scroll_content = QWidget()
        self.shapes_grid_layout = QGridLayout(self.shape_scroll_content)
        self.shapes_grid_layout.setSpacing(10)
        self.shapes_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll_area.setWidget(self.shape_scroll_content)
        # Event filter removed - using fixed horizontal layout instead of dynamic resize
        
        layout.addWidget(scroll_area)
        
        if theme_manager.night_mode:
            input_bg, border, accent_color = "#3a3a3a", "#4a4a4a", self.accent_color
        else:
            input_bg, border, accent_color = "#f5f5f5", "#e0e0e0", self.accent_color
            
        button_style = f"""
            QPushButton {{
                background-color: {input_bg};
                border: 2px solid transparent;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                border-color: {border};
            }}
            QPushButton:checked {{
                border-color: {accent_color};
                background-color: {border};
            }}
        """

        icons_path = os.path.join(self.addon_path, "system_files", "heatmap_system_icons")
        self.shape_buttons = []
        
        if os.path.isdir(icons_path):
            for filename in sorted(os.listdir(icons_path)):
                if filename.lower().endswith(".svg"):
                    shape_name = os.path.splitext(filename)[0].replace("_", " ").title()

                    card = QPushButton()
                    card.setCheckable(True)
                    card.setAutoExclusive(True)
                    card.setProperty("shape_filename", filename)
                    card.setFixedSize(80, 80)
                    card.setToolTip(shape_name)
                    card.setStyleSheet(button_style)

                    icon = self._get_svg_icon(os.path.join(icons_path, filename))
                    if icon:
                        card.setIcon(icon)
                        card.setIconSize(card.size() * 0.6)

                    card.clicked.connect(self._on_shape_selected)
                    self.shape_buttons.append(card)

        # Perform initial layout with default columns
        self._reflow_shape_icons()
                    
        self.selected_heatmap_shape = self.current_config.get("heatmapShape", "square.svg")
        for btn in self.shape_buttons:
            if btn.property("shape_filename") == self.selected_heatmap_shape:
                btn.setChecked(True)
                break
            
        return widget


    def create_reviewer_buttons_section(self):
        section = SectionGroup("Answer Buttons", self)
        layout = section.content_layout

        # --- General Button Settings ---
        general_group = QGroupBox("General Button settings")
        general_layout = QVBoxLayout(general_group)
        general_layout.setSpacing(10)

        # Enable Toggle and other global settings
        # Row 1: Enable & Radius
        row1 = QHBoxLayout()
        
        enable_label = QLabel("Enable Custom Buttons:")
        self.reviewer_btn_custom_enable_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.reviewer_btn_custom_enable_toggle.setChecked(self.current_config.get("onigiri_reviewer_btn_custom_enabled", False))
        row1.addWidget(enable_label)
        row1.addWidget(self.reviewer_btn_custom_enable_toggle)
        row1.addSpacing(20)
        
        radius_label = QLabel("Border Radius:")
        self.reviewer_btn_radius_spin = QSpinBox()
        self.reviewer_btn_radius_spin.setRange(0, 50)
        self.reviewer_btn_radius_spin.setSuffix(" px")
        self.reviewer_btn_radius_spin.setValue(self.current_config.get("onigiri_reviewer_btn_radius", 12))
        row1.addWidget(radius_label)
        row1.addWidget(self.reviewer_btn_radius_spin)
        row1.addStretch()
        general_layout.addLayout(row1)

        # Row 2: Padding, Button Height, Bar Height
        row2 = QHBoxLayout()
        
        padding_label = QLabel("Button Padding:")
        self.reviewer_btn_padding_spin = QSpinBox()
        self.reviewer_btn_padding_spin.setRange(0, 30)
        self.reviewer_btn_padding_spin.setSuffix(" px")
        self.reviewer_btn_padding_spin.setValue(self.current_config.get("onigiri_reviewer_btn_padding", 5))
        row2.addWidget(padding_label)
        row2.addWidget(self.reviewer_btn_padding_spin)
        row2.addSpacing(20)

        btn_height_label = QLabel("Min Height:")
        self.reviewer_btn_height_spin = QSpinBox()
        self.reviewer_btn_height_spin.setRange(20, 100)
        self.reviewer_btn_height_spin.setSuffix(" px")
        self.reviewer_btn_height_spin.setValue(self.current_config.get("onigiri_reviewer_btn_height", 40))
        row2.addWidget(btn_height_label)
        row2.addWidget(self.reviewer_btn_height_spin)
        row2.addSpacing(20)

        bar_height_label = QLabel("Bar Height:")
        self.reviewer_bar_height_spin = QSpinBox()
        self.reviewer_bar_height_spin.setRange(30, 200)
        self.reviewer_bar_height_spin.setSuffix(" px")
        self.reviewer_bar_height_spin.setValue(self.current_config.get("onigiri_reviewer_bar_height", 60))
        row2.addWidget(bar_height_label)
        row2.addWidget(self.reviewer_bar_height_spin)
        row2.addStretch()
        general_layout.addLayout(row2)

        layout.addWidget(general_group)

        # --- Two Column Layout for Light/Dark Mode ---
        modes_layout = QHBoxLayout()
        modes_layout.setSpacing(15)

        self.preview_buttons = {"light": {}, "dark": {}}
        
        # Define button data for iteration
        # (Label, key, default_bg, default_text)
        # We'll split defaults for light/dark later
        button_defs = [
            ("Again", "again", 
             ("#ffb3b3", "#4d0000"), ("#ffcccb", "#4a0000")), # (light_bg, light_text), (dark_bg, dark_text)
            ("Hard", "hard", 
             ("#ffe0b3", "#4d2600"), ("#ffd699", "#4d1d00")),
            ("Good", "good", 
             ("#b3ffb3", "#004d00"), ("#90ee90", "#004000")),
            ("Easy", "easy", 
             ("#b3d9ff", "#00264d"), ("#add8e6", "#002952")),
            ("Show Answer", "other",
             ("#ffffff", "#2c2c2c"), ("#3a3a3a", "#e0e0e0")) # Special handling for other
        ]

        # Mode loop to create columns
        for mode_name, mode_key, bg_color in [("Light Mode", "light", "#FFFFFF"), ("Dark Mode", "dark", "#2C2C2C")]:
            column_widget = QWidget()
            column_widget.setObjectName(f"column_{mode_key}")
            
            # Determine text color based on background
            text_col = "black" if mode_key == "light" else "white"
            sub_text_col = "#555" if mode_key == "light" else "#ccc"
            
            column_widget.setStyleSheet(f"""
                QWidget#column_{mode_key} {{
                    background-color: {bg_color}; 
                    border-radius: 10px;
                }}
                QLabel {{ color: {text_col}; }}
                QGroupBox {{ color: {text_col}; font-weight: bold; }}
                QGroupBox::title {{ color: {text_col}; }}
                QCheckBox {{ color: {text_col}; }}
                QRadioButton {{ color: {text_col}; }}
                QLineEdit {{ color: {text_col}; background-color: {'#fff' if mode_key == 'light' else '#444'}; border: 1px solid {'#ccc' if mode_key == 'light' else '#555'}; border-radius: 4px; }}
            """)
            
            col_layout = QVBoxLayout(column_widget)
            col_layout.setContentsMargins(15, 15, 15, 15)
            col_layout.setSpacing(15)
            # Ensure columns don't shrink too much
            column_widget.setMinimumWidth(350) 

            # Header
            header = QLabel(mode_name)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Force style again just in case, though the parent stylesheet should handle it
            header.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {text_col};")
            col_layout.addWidget(header)

            # --- Preview Box for this mode ---
            preview_frame = QFrame()
            preview_frame.setStyleSheet(f"background-color: {bg_color}; border: 1px solid {'#444' if mode_key == 'dark' else '#ddd'}; border-radius: 8px;")
            p_layout = QHBoxLayout(preview_frame)
            p_layout.setContentsMargins(10, 10, 10, 10)
            p_layout.addStretch() # Add stretch to center buttons
            
            # Create preview buttons
            for label, key, light_defaults, dark_defaults in button_defs:
                btn = QPushButton(label)
                if key == "other":
                     # Show Answer button usually auto-hides other buttons in real Anki, 
                     # but here we show them all side-by-side or just show answer?
                     # Mimicking the screenshot: All buttons visible.
                     pass
                
                # Store for live updates
                self.preview_buttons[mode_key][key] = btn
                p_layout.addWidget(btn)
            
            p_layout.addStretch()
            col_layout.addWidget(preview_frame)

            # --- Settings List for this mode ---
            # REMOVED QScrollArea to fix visibility issues
            settings_content = QWidget()
            settings_content.setStyleSheet("background: transparent;")
            settings_layout = QVBoxLayout(settings_content)
            settings_layout.setContentsMargins(0, 0, 0, 0)
            settings_layout.setSpacing(10)

            # Add Color Pickers for each button
            for label, key, (l_bg, l_text), (d_bg, d_text) in button_defs:
                # Group for the button
                btn_group = QGroupBox(f"{label} Button")
                btn_group.setStyleSheet(f"QGroupBox::title {{ color: {'#ddd' if mode_key == 'dark' else '#333'}; }}")
                g_layout = QVBoxLayout(btn_group)
                
                # Determine keys and defaults based on mode
                if mode_key == "light":
                    bg_config_key = f"onigiri_reviewer_btn_{key}_bg_light" if key != "other" else "onigiri_reviewer_other_btn_bg_light"
                    text_config_key = f"onigiri_reviewer_btn_{key}_text_light" if key != "other" else "onigiri_reviewer_other_btn_text_light"
                    bg_default = l_bg
                    text_default = l_text
                    # Specific input names for connection later
                    bg_input_name = f"btn_{key}_bg_light" if key != "other" else "other_btn_bg_light"
                    text_input_name = f"btn_{key}_text_light" if key != "other" else "other_btn_text_light"
                else: # dark
                    bg_config_key = f"onigiri_reviewer_btn_{key}_bg_dark" if key != "other" else "onigiri_reviewer_other_btn_bg_dark"
                    text_config_key = f"onigiri_reviewer_btn_{key}_text_dark" if key != "other" else "onigiri_reviewer_other_btn_text_dark"
                    bg_default = d_bg
                    text_default = d_text
                    bg_input_name = f"btn_{key}_bg_dark" if key != "other" else "other_btn_bg_dark"
                    text_input_name = f"btn_{key}_text_dark" if key != "other" else "other_btn_text_dark"

                # Add rows
                bg_row = self._create_color_picker_row(
                    "Background", 
                    self.current_config.get(bg_config_key, bg_default), 
                    bg_input_name
                )
                text_row = self._create_color_picker_row(
                    "Text", 
                    self.current_config.get(text_config_key, text_default), 
                    text_input_name
                )
                g_layout.addLayout(bg_row)
                g_layout.addLayout(text_row)
                
                # Special case: Hover for "Other" button
                if key == "other":
                    hover_label = QLabel("Hover State")
                    g_layout.addWidget(hover_label)
                    
                    if mode_key == "light":
                        h_bg_key = "onigiri_reviewer_other_btn_hover_bg_light"
                        h_txt_key = "onigiri_reviewer_other_btn_hover_text_light"
                        h_bg_def, h_txt_def = "#2c2c2c", "#f0f0f0"
                        h_bg_name, h_txt_name = "other_btn_hover_bg_light", "other_btn_hover_text_light"
                    else:
                        h_bg_key = "onigiri_reviewer_other_btn_hover_bg_dark"
                        h_txt_key = "onigiri_reviewer_other_btn_hover_text_dark"
                        h_bg_def, h_txt_def = "#e0e0e0", "#3a3a3a"
                        h_bg_name, h_txt_name = "other_btn_hover_bg_dark", "other_btn_hover_text_dark"
                        
                    h_bg_row = self._create_color_picker_row(
                        "Hover Bg", self.current_config.get(h_bg_key, h_bg_def), h_bg_name
                    )
                    h_txt_row = self._create_color_picker_row(
                        "Hover Text", self.current_config.get(h_txt_key, h_txt_def), h_txt_name
                    )
                    g_layout.addLayout(h_bg_row)
                    g_layout.addLayout(h_txt_row)

                settings_layout.addWidget(btn_group)
            
            # Stat Text Color (One per mode)
            stattxt_group = QGroupBox("Stat Text Color (.stattxt)")
            stattxt_group.setStyleSheet(f"QGroupBox::title {{ color: {'#ddd' if mode_key == 'dark' else '#333'}; }}")
            s_layout = QVBoxLayout(stattxt_group)
            if mode_key == "light":
                 stattxt_row = self._create_color_picker_row(
                    "Color", self.current_config.get("onigiri_reviewer_stattxt_color_light", "#666666"), "stattxt_color_light"
                 )
            else:
                 stattxt_row = self._create_color_picker_row(
                    "Color", self.current_config.get("onigiri_reviewer_stattxt_color_dark", "#aaaaaa"), "stattxt_color_dark"
                 )
            s_layout.addLayout(stattxt_row)
            settings_layout.addWidget(stattxt_group)

            settings_layout.addStretch()
            
            col_layout.addWidget(settings_content) # Directly add widget to column layout
            modes_layout.addWidget(column_widget)

        layout.addLayout(modes_layout)

        # Connect signals for preview updates
        # We need to collect all inputs to connect them
        all_inputs = [
            self.reviewer_btn_radius_spin, self.reviewer_btn_padding_spin, self.reviewer_btn_height_spin
        ]
        
        # Collect all dynamic inputs
        # We need to find them via their attribute names we assigned in _create_color_picker_row
        # Helper list of attributes to check
        attr_to_check = []
        for key in ["again", "hard", "good", "easy"]:
            attr_to_check.extend([
                f"btn_{key}_bg_light_color_input", f"btn_{key}_bg_dark_color_input",
                f"btn_{key}_text_light_color_input", f"btn_{key}_text_dark_color_input"
            ])
        attr_to_check.extend([
            "other_btn_bg_light_color_input", "other_btn_bg_dark_color_input",
            "other_btn_text_light_color_input", "other_btn_text_dark_color_input",
            "other_btn_hover_bg_light_color_input", "other_btn_hover_bg_dark_color_input",
            "other_btn_hover_text_light_color_input", "other_btn_hover_text_dark_color_input",
            "stattxt_color_light_color_input", "stattxt_color_dark_color_input"
        ])

        for attr in attr_to_check:
            if hasattr(self, attr):
                all_inputs.append(getattr(self, attr))

        for widget in all_inputs:
            if isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self._update_reviewer_button_previews)
            elif isinstance(widget, QLineEdit):
                # Using textChanged instead of editingFinished for live preview
                widget.textChanged.connect(self._update_reviewer_button_previews)
        
        # Initial update
        self._update_reviewer_button_previews()

        # Reset Button (specific to this section)
        reset_btn_layout = QHBoxLayout()
        reset_btn = QPushButton("Reset Answer Buttons to Default")
        reset_btn.clicked.connect(self.reset_reviewer_buttons_to_default)
        reset_btn_layout.addWidget(reset_btn)
        reset_btn_layout.addStretch()
        layout.addLayout(reset_btn_layout)

        return section

    def _update_reviewer_button_previews(self):
        if not hasattr(self, 'preview_buttons'):
            return

        radius = self.reviewer_btn_radius_spin.value()
        padding = self.reviewer_btn_padding_spin.value()
        height = self.reviewer_btn_height_spin.value()

        buttons = ["again", "hard", "good", "easy"]
        
        for mode in ["light", "dark"]:
            for key in buttons:
                btn = self.preview_buttons[mode][key]
                
                # Get colors using getattr to avoid KeyError
                if mode == "light":
                    bg = getattr(self, f"btn_{key}_bg_light_color_input").text()
                    text = getattr(self, f"btn_{key}_text_light_color_input").text()
                else:
                    bg = getattr(self, f"btn_{key}_bg_dark_color_input").text()
                    text = getattr(self, f"btn_{key}_text_dark_color_input").text()
                
                if not self.reviewer_btn_custom_enable_toggle.isChecked():
                     btn.setStyleSheet("")
                     continue

                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg} !important;
                        color: {text};
                        border-radius: {radius}px;
                        padding: {padding}px;
                        height: {height}px;
                        border: none;
                        font-weight: bold;
                    }}
                """)
                
            # Update "Other" button preview
            other_btn = self.preview_buttons[mode]["other"]
            if mode == "light":
                bg = getattr(self, "other_btn_bg_light_color_input").text()
                text = getattr(self, "other_btn_text_light_color_input").text()
            else:
                bg = getattr(self, "other_btn_bg_dark_color_input").text()
                text = getattr(self, "other_btn_text_dark_color_input").text()
                
            other_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg} !important;
                    color: {text};
                    border-radius: {radius}px;
                    padding: {padding}px;
                    height: {height}px;
                    border: none;
                    font-weight: bold;
                }}
            """)

    def reset_reviewer_buttons_to_default(self):
        # Reset Global Settings
        self.reviewer_btn_custom_enable_toggle.setChecked(True)
        self.reviewer_btn_radius_spin.setValue(12)
        self.reviewer_btn_padding_spin.setValue(5)
        self.reviewer_btn_height_spin.setValue(40)
        self.reviewer_bar_height_spin.setValue(60)

        getattr(self, "stattxt_color_light_color_input").setText("#666666")
        if hasattr(self, "stattxt_color_light_circular_button"): getattr(self, "stattxt_color_light_circular_button").setColor("#666666")
        
        getattr(self, "stattxt_color_dark_color_input").setText("#aaaaaa")
        if hasattr(self, "stattxt_color_dark_circular_button"): getattr(self, "stattxt_color_dark_circular_button").setColor("#aaaaaa")
        
        # Reset Other Buttons
        getattr(self, "other_btn_bg_light_color_input").setText("#ffffff")
        if hasattr(self, "other_btn_bg_light_circular_button"): getattr(self, "other_btn_bg_light_circular_button").setColor("#ffffff")
        
        getattr(self, "other_btn_text_light_color_input").setText("#2c2c2c")
        if hasattr(self, "other_btn_text_light_circular_button"): getattr(self, "other_btn_text_light_circular_button").setColor("#2c2c2c")
        
        getattr(self, "other_btn_bg_dark_color_input").setText("#3a3a3a")
        if hasattr(self, "other_btn_bg_dark_circular_button"): getattr(self, "other_btn_bg_dark_circular_button").setColor("#3a3a3a")
        
        getattr(self, "other_btn_text_dark_color_input").setText("#e0e0e0")
        if hasattr(self, "other_btn_text_dark_circular_button"): getattr(self, "other_btn_text_dark_circular_button").setColor("#e0e0e0")
        
        getattr(self, "other_btn_hover_bg_light_color_input").setText("#2c2c2c")
        if hasattr(self, "other_btn_hover_bg_light_circular_button"): getattr(self, "other_btn_hover_bg_light_circular_button").setColor("#2c2c2c")
        
        getattr(self, "other_btn_hover_text_light_color_input").setText("#f0f0f0")
        if hasattr(self, "other_btn_hover_text_light_circular_button"): getattr(self, "other_btn_hover_text_light_circular_button").setColor("#f0f0f0")
        
        getattr(self, "other_btn_hover_bg_dark_color_input").setText("#e0e0e0")
        if hasattr(self, "other_btn_hover_bg_dark_circular_button"): getattr(self, "other_btn_hover_bg_dark_circular_button").setColor("#e0e0e0")
        
        getattr(self, "other_btn_hover_text_dark_color_input").setText("#3a3a3a")
        if hasattr(self, "other_btn_hover_text_dark_circular_button"): getattr(self, "other_btn_hover_text_dark_circular_button").setColor("#3a3a3a")

        # Reset Per Button Settings
        defaults = [
            ("again", "#ffb3b3", "#4d0000", "#ffcccb", "#4a0000"),
            ("hard", "#ffe0b3", "#4d2600", "#ffd699", "#4d1d00"),
            ("good", "#b3ffb3", "#004d00", "#90ee90", "#004000"),
            ("easy", "#b3d9ff", "#00264d", "#add8e6", "#002952")
        ]
        
        for key, def_bg_l, def_txt_l, def_bg_d, def_txt_d in defaults:
            getattr(self, f"btn_{key}_bg_light_color_input").setText(def_bg_l)
            if hasattr(self, f"btn_{key}_bg_light_circular_button"): getattr(self, f"btn_{key}_bg_light_circular_button").setColor(def_bg_l)
            
            getattr(self, f"btn_{key}_text_light_color_input").setText(def_txt_l)
            if hasattr(self, f"btn_{key}_text_light_circular_button"): getattr(self, f"btn_{key}_text_light_circular_button").setColor(def_txt_l)
            
            getattr(self, f"btn_{key}_bg_dark_color_input").setText(def_bg_d)
            if hasattr(self, f"btn_{key}_bg_dark_circular_button"): getattr(self, f"btn_{key}_bg_dark_circular_button").setColor(def_bg_d)
            
            getattr(self, f"btn_{key}_text_dark_color_input").setText(def_txt_d)
            if hasattr(self, f"btn_{key}_text_dark_circular_button"): getattr(self, f"btn_{key}_text_dark_circular_button").setColor(def_txt_d)
        
        showInfo("Answer buttons have been reset to default values.")

    def create_reviewer_tab(self):
        page, layout = self._create_scrollable_page()

        # --- Reviewer Background Section ---
        reviewer_bg_section = SectionGroup("Reviewer Background", self)
        layout.addWidget(reviewer_bg_section)
        
        reviewer_bg_content = reviewer_bg_section.content_layout
        
        # Background mode radio buttons
        reviewer_bg_mode_layout = QHBoxLayout()
        reviewer_bg_button_group = QButtonGroup(reviewer_bg_section)
        
        self.reviewer_bg_main_radio = QRadioButton("Use Main Background")
        self.reviewer_bg_color_radio = QRadioButton("Solid Color")
        self.reviewer_bg_image_color_radio = QRadioButton("Image")
        
        reviewer_bg_button_group.addButton(self.reviewer_bg_main_radio)
        reviewer_bg_button_group.addButton(self.reviewer_bg_color_radio)
        reviewer_bg_button_group.addButton(self.reviewer_bg_image_color_radio)
        
        conf = config.get_config()
        reviewer_bg_mode = conf.get("onigiri_reviewer_bg_mode", "main")
        self.reviewer_bg_main_radio.setChecked(reviewer_bg_mode == "main")
        self.reviewer_bg_color_radio.setChecked(reviewer_bg_mode == "color")
        self.reviewer_bg_image_color_radio.setChecked(reviewer_bg_mode == "image_color")
        
        reviewer_bg_mode_layout.addWidget(self.reviewer_bg_main_radio)
        reviewer_bg_mode_layout.addWidget(self.reviewer_bg_color_radio)
        reviewer_bg_mode_layout.addWidget(self.reviewer_bg_image_color_radio)
        reviewer_bg_mode_layout.addStretch()
        reviewer_bg_content.addLayout(reviewer_bg_mode_layout)
        
        # Main background options (blur and opacity when using main background)
        self.reviewer_bg_main_group = QWidget()
        main_effects_layout = QHBoxLayout(self.reviewer_bg_main_group)
        main_effects_layout.setContentsMargins(0, 10, 0, 0)
        
        main_blur_label = QLabel("Background Blur:")
        self.reviewer_bg_main_blur_spinbox = QSpinBox()
        self.reviewer_bg_main_blur_spinbox.setMinimum(0)
        self.reviewer_bg_main_blur_spinbox.setMaximum(100)
        self.reviewer_bg_main_blur_spinbox.setSuffix(" %")
        self.reviewer_bg_main_blur_spinbox.setValue(conf.get("onigiri_reviewer_bg_main_blur", 0))
        
        main_opacity_label = QLabel("Background Opacity:")
        self.reviewer_bg_main_opacity_spinbox = QSpinBox()
        self.reviewer_bg_main_opacity_spinbox.setMinimum(0)
        self.reviewer_bg_main_opacity_spinbox.setMaximum(100)
        self.reviewer_bg_main_opacity_spinbox.setSuffix(" %")
        self.reviewer_bg_main_opacity_spinbox.setValue(conf.get("onigiri_reviewer_bg_main_opacity", 100))
        
        main_effects_layout.addWidget(main_blur_label)
        main_effects_layout.addWidget(self.reviewer_bg_main_blur_spinbox)
        main_effects_layout.addSpacing(20)
        main_effects_layout.addWidget(main_opacity_label)
        main_effects_layout.addWidget(self.reviewer_bg_main_opacity_spinbox)
        main_effects_layout.addStretch()
        reviewer_bg_content.addWidget(self.reviewer_bg_main_group)
        
        # Custom background options
        self.reviewer_bg_custom_group = self._create_reviewer_bg_custom_options()
        reviewer_bg_content.addWidget(self.reviewer_bg_custom_group)
        
        # Connect signals
        self.reviewer_bg_main_radio.toggled.connect(self._toggle_reviewer_bg_options)
        self.reviewer_bg_color_radio.toggled.connect(self._toggle_reviewer_bg_options)
        self.reviewer_bg_image_color_radio.toggled.connect(self._toggle_reviewer_bg_options)
        self._toggle_reviewer_bg_options()

        bottom_bar_section = SectionGroup("Bottom Bar Background", self)
        layout.addWidget(bottom_bar_section)

        # --- Notification Position Section ---
        notification_pos_section = self.create_notification_position_section()
        layout.addWidget(notification_pos_section)

        # --- Answer Buttons Section ---
        reviewer_buttons_section = self.create_reviewer_buttons_section()
        layout.addWidget(reviewer_buttons_section)

        mode_layout_content = bottom_bar_section.content_layout
        mode_layout = QHBoxLayout()

        bottom_bar_button_group = QButtonGroup(bottom_bar_section)

        self.reviewer_bar_main_radio = QRadioButton("Match Main Background")
        self.reviewer_bar_color_radio = QRadioButton("Solid Color")
        self.reviewer_bar_image_color_radio = QRadioButton("Image")

        bottom_bar_button_group.addButton(self.reviewer_bar_main_radio)
        bottom_bar_button_group.addButton(self.reviewer_bar_color_radio)
        bottom_bar_button_group.addButton(self.reviewer_bar_image_color_radio)

        self.reviewer_bar_main_radio.setChecked(self.reviewer_bottom_bar_mode == "main")
        self.reviewer_bar_color_radio.setChecked(self.reviewer_bottom_bar_mode == "color")
        self.reviewer_bar_image_color_radio.setChecked(self.reviewer_bottom_bar_mode == "image_color")

        mode_layout.addWidget(self.reviewer_bar_main_radio)
        
        self.reviewer_bar_match_reviewer_bg_radio = QRadioButton("Match Reviewer Background")
        bottom_bar_button_group.addButton(self.reviewer_bar_match_reviewer_bg_radio)
        self.reviewer_bar_match_reviewer_bg_radio.setChecked(self.reviewer_bottom_bar_mode == "match_reviewer_bg")
        mode_layout.addWidget(self.reviewer_bar_match_reviewer_bg_radio)

        mode_layout.addWidget(self.reviewer_bar_color_radio)
        mode_layout.addWidget(self.reviewer_bar_image_color_radio)
        mode_layout.addStretch()
        mode_layout_content.addLayout(mode_layout)

        self.reviewer_bar_match_main_group = QWidget()
        match_main_layout = QVBoxLayout(self.reviewer_bar_match_main_group)
        match_main_layout.setContentsMargins(0, 10, 0, 0)

        match_effects_layout = QHBoxLayout()
        blur_label = QLabel("Background Blur:")
        self.reviewer_bar_match_main_blur_spinbox = QSpinBox()
        self.reviewer_bar_match_main_blur_spinbox.setMinimum(0); self.reviewer_bar_match_main_blur_spinbox.setMaximum(100)
        self.reviewer_bar_match_main_blur_spinbox.setSuffix(" %")
        self.reviewer_bar_match_main_blur_spinbox.setValue(self.current_config.get("onigiri_reviewer_bottom_bar_match_main_blur", 5))

        opacity_label = QLabel("Bar Opacity:")
        self.reviewer_bar_match_main_opacity_spinbox = QSpinBox()
        self.reviewer_bar_match_main_opacity_spinbox.setMinimum(0); self.reviewer_bar_match_main_opacity_spinbox.setMaximum(100)
        self.reviewer_bar_match_main_opacity_spinbox.setSuffix(" %")
        self.reviewer_bar_match_main_opacity_spinbox.setValue(self.current_config.get("onigiri_reviewer_bottom_bar_match_main_opacity", 90))

        match_effects_layout.addWidget(blur_label)
        match_effects_layout.addWidget(self.reviewer_bar_match_main_blur_spinbox)
        match_effects_layout.addSpacing(20)
        match_effects_layout.addWidget(opacity_label)
        match_effects_layout.addWidget(self.reviewer_bar_match_main_opacity_spinbox)
        match_effects_layout.addStretch()
        match_main_layout.addLayout(match_effects_layout)
        mode_layout_content.addWidget(self.reviewer_bar_match_main_group)

        self.reviewer_bar_match_reviewer_bg_group = QWidget()
        match_reviewer_bg_layout = QVBoxLayout(self.reviewer_bar_match_reviewer_bg_group)
        match_reviewer_bg_layout.setContentsMargins(0, 10, 0, 0)

        match_reviewer_bg_effects_layout = QHBoxLayout()
        blur_label_2 = QLabel("Background Blur:")
        self.reviewer_bar_match_reviewer_bg_blur_spinbox = QSpinBox()
        self.reviewer_bar_match_reviewer_bg_blur_spinbox.setMinimum(0); self.reviewer_bar_match_reviewer_bg_blur_spinbox.setMaximum(100)
        self.reviewer_bar_match_reviewer_bg_blur_spinbox.setSuffix(" %")
        self.reviewer_bar_match_reviewer_bg_blur_spinbox.setValue(self.current_config.get("onigiri_reviewer_bottom_bar_match_reviewer_bg_blur", 5))

        opacity_label_2 = QLabel("Bar Opacity:")
        self.reviewer_bar_match_reviewer_bg_opacity_spinbox = QSpinBox()
        self.reviewer_bar_match_reviewer_bg_opacity_spinbox.setMinimum(0); self.reviewer_bar_match_reviewer_bg_opacity_spinbox.setMaximum(100)
        self.reviewer_bar_match_reviewer_bg_opacity_spinbox.setSuffix(" %")
        self.reviewer_bar_match_reviewer_bg_opacity_spinbox.setValue(self.current_config.get("onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity", 90))

        match_reviewer_bg_effects_layout.addWidget(blur_label_2)
        match_reviewer_bg_effects_layout.addWidget(self.reviewer_bar_match_reviewer_bg_blur_spinbox)
        match_reviewer_bg_effects_layout.addSpacing(20)
        match_reviewer_bg_effects_layout.addWidget(opacity_label_2)
        match_reviewer_bg_effects_layout.addWidget(self.reviewer_bar_match_reviewer_bg_opacity_spinbox)
        match_reviewer_bg_effects_layout.addStretch()
        match_reviewer_bg_layout.addLayout(match_reviewer_bg_effects_layout)
        mode_layout_content.addWidget(self.reviewer_bar_match_reviewer_bg_group)

        self.reviewer_bar_custom_group = self.create_reviewer_bar_custom_options()
        mode_layout_content.addWidget(self.reviewer_bar_custom_group)

        self.reviewer_bar_main_radio.toggled.connect(lambda checked: self._on_bottom_bar_mode_changed("main", checked))
        self.reviewer_bar_match_reviewer_bg_radio.toggled.connect(lambda checked: self._on_bottom_bar_mode_changed("match_reviewer_bg", checked))
        self.reviewer_bar_color_radio.toggled.connect(lambda checked: self._on_bottom_bar_mode_changed("color", checked))
        self.reviewer_bar_image_color_radio.toggled.connect(lambda checked: self._on_bottom_bar_mode_changed("image_color", checked))
        self.reviewer_bar_main_radio.toggled.connect(self.toggle_reviewer_bar_options)
        self.reviewer_bar_match_reviewer_bg_radio.toggled.connect(self.toggle_reviewer_bar_options)
        self.reviewer_bar_color_radio.toggled.connect(self.toggle_reviewer_bar_options)
        self.reviewer_bar_image_color_radio.toggled.connect(self.toggle_reviewer_bar_options)
        self.toggle_reviewer_bar_options()

        # --- RESET BUTTONS ---
        reset_buttons_layout = QHBoxLayout()
        reset_buttons_layout.addStretch()

        reset_reviewer_bg_button = QPushButton("Reset Reviewer Background to Default")
        reset_reviewer_bg_button.clicked.connect(self.reset_reviewer_bg_to_default)
        reset_buttons_layout.addWidget(reset_reviewer_bg_button)

        reset_bottom_bar_button = QPushButton("Reset Bottom Bar to Default")
        reset_bottom_bar_button.clicked.connect(self.reset_reviewer_bottom_bar_to_default)
        reset_buttons_layout.addWidget(reset_bottom_bar_button)

        layout.addLayout(reset_buttons_layout)
        # --- END OF RESET BUTTONS ---

        layout.addStretch()

        sections = {
            "Reviewer Background": reviewer_bg_section,
            "Bottom Bar Background": bottom_bar_section,
            "Notification Position": notification_pos_section,
            "Answer Buttons": reviewer_buttons_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections, buttons_per_row=2)

        return page

    def create_reviewer_bar_custom_options(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        self.reviewer_bar_color_group = QWidget()
        color_layout = QVBoxLayout(self.reviewer_bar_color_group)
        color_layout.setContentsMargins(0, 0, 0, 0)

        self.reviewer_bar_light_color_row = self._create_color_picker_row(
            "Color (Light Mode)", mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_light_color", "#EEEEEE"), "reviewer_bar_light"
        )
        self.reviewer_bar_dark_color_row = self._create_color_picker_row(
            "Color (Dark Mode)", mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_dark_color", "#3C3C3C"), "reviewer_bar_dark"
        )
        color_layout.addLayout(self.reviewer_bar_light_color_row)
        color_layout.addLayout(self.reviewer_bar_dark_color_row)
        layout.addWidget(self.reviewer_bar_color_group)

        self.galleries["reviewer_bar_bg"] = {}
        self.reviewer_bar_image_group = self._create_image_gallery_group(
            "reviewer_bar_bg", "user_files/reviewer_bar_bg", "onigiri_reviewer_bottom_bar_bg_image", is_sub_group=True
        )
        layout.addWidget(self.reviewer_bar_image_group)

        effects_container = QWidget()
        effects_layout = QHBoxLayout(effects_container)
        effects_layout.setContentsMargins(0, 10, 0, 0)
        self.reviewer_bar_blur_label = QLabel("Blur:")
        self.reviewer_bar_blur_spinbox = QSpinBox()
        self.reviewer_bar_blur_spinbox.setMinimum(0); self.reviewer_bar_blur_spinbox.setMaximum(100)
        self.reviewer_bar_blur_spinbox.setSuffix(" %")
        self.reviewer_bar_blur_spinbox.setValue(mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_blur", 0))

        self.reviewer_bar_opacity_label = QLabel("Opacity:")
        self.reviewer_bar_opacity_spinbox = QSpinBox()
        self.reviewer_bar_opacity_spinbox.setMinimum(0); self.reviewer_bar_opacity_spinbox.setMaximum(100)
        self.reviewer_bar_opacity_spinbox.setSuffix(" %")
        self.reviewer_bar_opacity_spinbox.setValue(mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_opacity", 100))

        effects_layout.addWidget(self.reviewer_bar_blur_label)
        effects_layout.addWidget(self.reviewer_bar_blur_spinbox)
        effects_layout.addSpacing(20)
        effects_layout.addWidget(self.reviewer_bar_opacity_label)
        effects_layout.addWidget(self.reviewer_bar_opacity_spinbox)
        effects_layout.addStretch()
        layout.addWidget(effects_container)

        if 'reviewer_bar_bg' in self.galleries:
            self.galleries['reviewer_bar_bg']['effects_widget'] = effects_container

        return widget

    def create_notification_position_section(self):
        section = SectionGroup("Reviewer Notification Widget Position", self)
        
        container = QWidget()
        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(40)
        
        # --- Left Side: Selection Grid ---
        grid_container = QWidget()
        grid_layout = QGridLayout(grid_container)
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
        current_pos = self.current_config.get("onigiri_reviewer_notification_position", "top-right")
        
        for pos_id, label, row, col in positions:
            btn = QPushButton(label)
            btn.setFixedSize(60, 45)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Style for buttons
            base_style = """
                QPushButton {
                    border: 1px solid #ccc;
                    border-radius: 8px;
                    background-color: transparent;
                    font-size: 20px;
                    color: #555;
                }
                QPushButton:hover {
                    background-color: rgba(0,0,0,0.05);
                }
                QPushButton:checked {
                    background-color: {self.accent_color.name()};
                    color: white;
                    border: 1px solid {self.accent_color.name()};
                }
            """
            
            if theme_manager.night_mode:
                base_style = """
                    QPushButton {
                        border: 1px solid #555;
                        border-radius: 8px;
                        background-color: transparent;
                        font-size: 20px;
                        color: #ccc;
                    }
                    QPushButton:hover {
                        background-color: rgba(255,255,255,0.05);
                    }
                    QPushButton:checked {
                    background-color: {self.accent_color.name()};
                    color: white;
                    border: 1px solid {self.accent_color.name()};
                }
    }
                """
            
            btn.setStyleSheet(base_style)
            
            if pos_id == current_pos:
                btn.setChecked(True)
                
            btn.clicked.connect(lambda checked, pid=pos_id: self._update_notification_position(pid))
            
            self.notification_pos_buttons[pos_id] = btn
            grid_layout.addWidget(btn, row, col)
            
        main_layout.addWidget(grid_container)
        
        # --- Right Side: Preview ---
        self.notif_preview_widget = QWidget()
        self.notif_preview_widget.setFixedSize(200, 120)
        # Style the preview container (screen representation)
        screen_border = "#ccc" if not theme_manager.night_mode else "#555"
        screen_bg = "transparent"
        self.notif_preview_widget.setStyleSheet(f"""
            QWidget {{
                border: 2px solid {screen_border};
                border-radius: 12px;
                background-color: {screen_bg};
            }}
        """)
        
        # The small notification rectangle
        self.notif_rect = QLabel(self.notif_preview_widget)
        self.notif_rect.setFixedSize(60, 30)
        self.notif_rect.setStyleSheet(f"""
            background-color: {self.accent_color};
            border-radius: 4px;
        """)
        
        self._position_preview_rect(current_pos)
        
        main_layout.addWidget(self.notif_preview_widget)
        main_layout.addStretch()
        
        section.content_layout.addWidget(container)
        return section

    def _update_notification_position(self, pos_id):
        # Update config
        self.current_config["onigiri_reviewer_notification_position"] = pos_id
        
        # Update buttons state (ensure exclusive check)
        for pid, btn in self.notification_pos_buttons.items():
            if pid != pos_id:
                btn.setChecked(False)
            else:
                btn.setChecked(True)
                
        # Update preview
        self._position_preview_rect(pos_id)

    def _position_preview_rect(self, pos_id):
        # Calculate position for the preview rect within the 200x120 container
        # Rect size: 60x30
        # Padding/Margin assumed: 10px from edges
        
        container_w, container_h = 200, 120
        rect_w, rect_h = 60, 30
        margin = 10
        
        x, y = 0, 0
        
        if "left" in pos_id:
            x = margin
        elif "right" in pos_id:
            x = container_w - rect_w - margin
        else: # center
            x = (container_w - rect_w) // 2
            
        if "top" in pos_id:
            y = margin
        elif "bottom" in pos_id:
            y = container_h - rect_h - margin
            
        self.notif_rect.move(x, y)

    def _create_reviewer_bg_custom_options(self):
        """Create custom background options for the reviewer screen."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        
        # Color options
        self.reviewer_bg_color_group = QWidget()
        color_layout = QVBoxLayout(self.reviewer_bg_color_group)
        color_layout.setContentsMargins(0, 0, 0, 0)
        
        conf = config.get_config()
        
        # Single color container
        self.reviewer_bg_single_color_container = QWidget()
        single_color_layout = QVBoxLayout(self.reviewer_bg_single_color_container)
        self.reviewer_bg_single_color_row = self._create_color_picker_row(
            "Background Color", conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF"), "reviewer_bg_single"
        )
        single_color_layout.addLayout(self.reviewer_bg_single_color_row)
        
        # Separate colors container
        self.reviewer_bg_separate_colors_container = QWidget()
        separate_colors_layout = QVBoxLayout(self.reviewer_bg_separate_colors_container)
        self.reviewer_bg_light_color_row = self._create_color_picker_row(
            "Background (Light Mode)", conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF"), "reviewer_bg_light"
        )
        self.reviewer_bg_dark_color_row = self._create_color_picker_row(
            "Background (Dark Mode)", conf.get("onigiri_reviewer_bg_dark_color", "#2C2C2C"), "reviewer_bg_dark"
        )
        separate_colors_layout.addLayout(self.reviewer_bg_light_color_row)
        separate_colors_layout.addLayout(self.reviewer_bg_dark_color_row)
        
        # Add both containers to the layout
        color_layout.addWidget(self.reviewer_bg_single_color_container)
        color_layout.addWidget(self.reviewer_bg_separate_colors_container)
        
        # Add theme mode toggle for color selection
        self.reviewer_bg_color_theme_mode_group = QButtonGroup()
        self.reviewer_bg_color_theme_mode_single = QRadioButton("Use same color for both themes")
        self.reviewer_bg_color_theme_mode_separate = QRadioButton("Use different colors for light/dark themes")
        self.reviewer_bg_color_theme_mode_group.addButton(self.reviewer_bg_color_theme_mode_single)
        self.reviewer_bg_color_theme_mode_group.addButton(self.reviewer_bg_color_theme_mode_separate)
        
        # Load saved theme mode or default to single
        reviewer_bg_color_theme_mode = mw.col.conf.get("onigiri_reviewer_bg_color_theme_mode", "single")
        self.reviewer_bg_color_theme_mode_single.setChecked(reviewer_bg_color_theme_mode == "single")
        self.reviewer_bg_color_theme_mode_separate.setChecked(reviewer_bg_color_theme_mode == "separate")
        
        color_theme_mode_layout = QHBoxLayout()
        color_theme_mode_layout.addWidget(self.reviewer_bg_color_theme_mode_single)
        color_theme_mode_layout.addWidget(self.reviewer_bg_color_theme_mode_separate)
        color_theme_mode_layout.addStretch()
        color_theme_mode_container = QWidget()
        color_theme_mode_container.setLayout(color_theme_mode_layout)
        color_theme_mode_container.setContentsMargins(15, 5, 0, 5)
        color_layout.insertWidget(0, color_theme_mode_container)
        
        # Set initial visibility based on theme mode
        self._update_reviewer_bg_color_theme_mode_visibility()
        
        # Connect theme mode signals for color selection
        self.reviewer_bg_color_theme_mode_single.toggled.connect(self._update_reviewer_bg_color_theme_mode_visibility)
        self.reviewer_bg_color_theme_mode_separate.toggled.connect(self._update_reviewer_bg_color_theme_mode_visibility)
        
        layout.addWidget(self.reviewer_bg_color_group)
        
        # Image galleries (only for Image mode)
        self.reviewer_bg_image_group = QWidget()
        image_layout = QVBoxLayout(self.reviewer_bg_image_group)
        image_layout.setContentsMargins(0, 10, 0, 0)
        
        # Add theme mode toggle for image selection
        self.reviewer_bg_image_theme_mode_group = QButtonGroup()
        self.reviewer_bg_image_theme_mode_single = QRadioButton("Use same image for both themes")
        self.reviewer_bg_image_theme_mode_separate = QRadioButton("Use different images for light/dark themes")
        self.reviewer_bg_image_theme_mode_group.addButton(self.reviewer_bg_image_theme_mode_single)
        self.reviewer_bg_image_theme_mode_group.addButton(self.reviewer_bg_image_theme_mode_separate)
        
        # Load saved theme mode or default to single
        reviewer_bg_image_theme_mode = mw.col.conf.get("onigiri_reviewer_bg_image_theme_mode", "single")
        self.reviewer_bg_image_theme_mode_single.setChecked(reviewer_bg_image_theme_mode == "single")
        self.reviewer_bg_image_theme_mode_separate.setChecked(reviewer_bg_image_theme_mode == "separate")
        
        image_theme_mode_layout = QHBoxLayout()
        image_theme_mode_layout.addWidget(self.reviewer_bg_image_theme_mode_single)
        image_theme_mode_layout.addWidget(self.reviewer_bg_image_theme_mode_separate)
        image_theme_mode_layout.addStretch()
        image_theme_mode_container = QWidget()
        image_theme_mode_container.setLayout(image_theme_mode_layout)
        image_theme_mode_container.setContentsMargins(15, 5, 0, 5)
        image_layout.addWidget(image_theme_mode_container)
        
        # Single image container
        self.reviewer_bg_single_image_container = QWidget()
        single_image_layout = QVBoxLayout(self.reviewer_bg_single_image_container)
        single_image_layout.setContentsMargins(0, 10, 0, 0)
        self.galleries["reviewer_bg_single"] = {}
        single_image_layout.addWidget(self._create_image_gallery_group(
            "reviewer_bg_single", "user_files/reviewer_bg", "onigiri_reviewer_bg_image", 
            title="Background Image", is_sub_group=True
        ))
        
        # Separate images container
        self.reviewer_bg_separate_images_container = QWidget()
        sep_layout = QHBoxLayout(self.reviewer_bg_separate_images_container)
        sep_layout.setContentsMargins(0, 10, 0, 0)
        self.galleries["reviewer_bg_light"] = {}
        sep_layout.addWidget(self._create_image_gallery_group(
            "reviewer_bg_light", "user_files/reviewer_bg", "onigiri_reviewer_bg_image_light", 
            title="Light Mode Background", is_sub_group=True
        ))
        self.galleries["reviewer_bg_dark"] = {}
        sep_layout.addWidget(self._create_image_gallery_group(
            "reviewer_bg_dark", "user_files/reviewer_bg", "onigiri_reviewer_bg_image_dark", 
            title="Dark Mode Background", is_sub_group=True
        ))
        
        # Add both containers to the layout
        image_layout.addWidget(self.reviewer_bg_single_image_container)
        image_layout.addWidget(self.reviewer_bg_separate_images_container)
        
        # Set initial visibility based on theme mode
        self._update_reviewer_bg_image_theme_mode_visibility()
        
        # Connect theme mode signals for image selection
        self.reviewer_bg_image_theme_mode_single.toggled.connect(self._update_reviewer_bg_image_theme_mode_visibility)
        self.reviewer_bg_image_theme_mode_separate.toggled.connect(self._update_reviewer_bg_image_theme_mode_visibility)
        
        layout.addWidget(self.reviewer_bg_image_group)
        
        # Effects (blur and opacity)
        self.reviewer_bg_effects_container = QWidget()
        effects_layout = QHBoxLayout(self.reviewer_bg_effects_container)
        effects_layout.setContentsMargins(0, 10, 0, 0)
        
        self.reviewer_bg_blur_label = QLabel("Blur:")
        self.reviewer_bg_blur_spinbox = QSpinBox()
        self.reviewer_bg_blur_spinbox.setMinimum(0)
        self.reviewer_bg_blur_spinbox.setMaximum(100)
        self.reviewer_bg_blur_spinbox.setSuffix(" %")
        self.reviewer_bg_blur_spinbox.setValue(conf.get("onigiri_reviewer_bg_blur", 0))
        
        self.reviewer_bg_opacity_label = QLabel("Opacity:")
        self.reviewer_bg_opacity_spinbox = QSpinBox()
        self.reviewer_bg_opacity_spinbox.setMinimum(0)
        self.reviewer_bg_opacity_spinbox.setMaximum(100)
        self.reviewer_bg_opacity_spinbox.setSuffix(" %")
        self.reviewer_bg_opacity_spinbox.setValue(conf.get("onigiri_reviewer_bg_opacity", 100))
        
        effects_layout.addWidget(self.reviewer_bg_blur_label)
        effects_layout.addWidget(self.reviewer_bg_blur_spinbox)
        effects_layout.addSpacing(20)
        effects_layout.addWidget(self.reviewer_bg_opacity_label)
        effects_layout.addWidget(self.reviewer_bg_opacity_spinbox)
        effects_layout.addStretch()
        layout.addWidget(self.reviewer_bg_effects_container)
        
        # Initially hide image options (only show for Image mode)
        self.reviewer_bg_image_group.setVisible(False)
        
        return widget
        
    def _update_reviewer_bg_color_theme_mode_visibility(self):
        """Update visibility of single/separate color pickers for reviewer background based on theme mode selection."""
        is_single = self.reviewer_bg_color_theme_mode_single.isChecked()
        self.reviewer_bg_single_color_container.setVisible(is_single)
        self.reviewer_bg_separate_colors_container.setVisible(not is_single)
        
        # If switching to single theme mode, update the single color picker with light mode color
        if is_single and hasattr(self, 'reviewer_bg_light_color_row'):
            light_color = self.reviewer_bg_light_color_row.itemAt(1).widget().text()
            self.reviewer_bg_single_color_row.itemAt(1).widget().setText(light_color)
    
    def _update_reviewer_bg_image_theme_mode_visibility(self):
        """Update visibility of single/separate image galleries for reviewer background based on theme mode selection."""
        is_single = self.reviewer_bg_image_theme_mode_single.isChecked()
        self.reviewer_bg_single_image_container.setVisible(is_single)
        self.reviewer_bg_separate_images_container.setVisible(not is_single)
        
        # If switching to single theme mode, update the single gallery with light mode image
        if is_single and 'reviewer_bg_light' in self.galleries and 'reviewer_bg_single' in self.galleries:
            light_image = self.galleries['reviewer_bg_light'].get('selected', '')
            if light_image and 'path_input' in self.galleries['reviewer_bg_single']:
                self.galleries['reviewer_bg_single']['selected'] = light_image
                self.galleries['reviewer_bg_single']['path_input'].setText(light_image)
    
    def _toggle_reviewer_bg_options(self):
        """Toggle visibility of reviewer background options based on selected mode."""
        is_main = self.reviewer_bg_main_radio.isChecked()
        self.reviewer_bg_main_group.setVisible(is_main)
        self.reviewer_bg_custom_group.setVisible(not is_main)
        
        # Control visibility of color and image options within custom group
        if not is_main:
            is_color = self.reviewer_bg_color_radio.isChecked()
            is_image_color = self.reviewer_bg_image_color_radio.isChecked()
            
            # Show color options for both 'Solid Color' and 'Image'
            self.reviewer_bg_color_group.setVisible(is_color or is_image_color)
            
            # Show image options and effects only for 'Image'
            self.reviewer_bg_image_group.setVisible(is_image_color)
            self.reviewer_bg_effects_container.setVisible(is_image_color)
            
            # If this is the first time showing the color group, ensure theme mode visibility is set
            if (is_color or is_image_color) and hasattr(self, 'reviewer_bg_color_theme_mode_single'):
                self._update_reviewer_bg_color_theme_mode_visibility()
                
            # If this is the first time showing the image group, ensure theme mode visibility is set
            if is_image_color and hasattr(self, 'reviewer_bg_image_theme_mode_single'):
                self._update_reviewer_bg_image_theme_mode_visibility()
    


    def _create_scrollable_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content_widget = QWidget()
        # This is the key fix: It tells Qt to efficiently handle filling the 
        # background, which prevents the flicker during redraws.
        content_widget.setAutoFillBackground(True)
        scroll.setWidget(content_widget)
        
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 20, 12, 20)  # Added 20px bottom padding
        
        page_container = QWidget()
        # We give the container a name so we can style it from the main stylesheet.
        page_container.setObjectName("pageContainer")
        
        page_layout = QVBoxLayout(page_container)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        
        return page_container, content_layout

    def _add_navigation_buttons(self, page_container, scroll_area, sections_map, buttons_per_row=None):
        """
        Adds a navigation bar at the top of the page container.
        sections_map: dict of {title: widget}
        buttons_per_row: int or None. If specified, buttons are arranged in a grid with this many columns.
                        If None, all buttons are placed in a single horizontal row.
        """
        if not sections_map:
            return

        nav_widget = QWidget()
        nav_widget.setObjectName("navBar")
        
        # Choose layout based on buttons_per_row parameter
        if buttons_per_row is not None:
            nav_layout = QGridLayout(nav_widget)
            nav_layout.setContentsMargins(10, 15, 10, 10)
            nav_layout.setSpacing(10)
            nav_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        else:
            nav_layout = QHBoxLayout(nav_widget)
            nav_layout.setContentsMargins(10, 15, 10, 10)
            nav_layout.setSpacing(10)
            nav_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        button_index = 0
        for title, target_widget in sections_map.items():
            btn = QPushButton(title)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # Style the button to look like a pill
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(128, 128, 128, 0.1) !important;
                    border: 1px solid rgba(128, 128, 128, 0.2) !important;
                    border-radius: 15px !important;
                    padding: 5px 15px !important;
                    font-size: 13px !important;
                    font-weight: bold !important;
                    min-height: 20px !important;
                }
                QPushButton:hover {
                    background-color: rgba(128, 128, 128, 0.2) !important;
                    border: 1px solid rgba(128, 128, 128, 0.4) !important;
                    border-radius: 15px !important;
                }
                QPushButton:pressed {
                    background-color: rgba(128, 128, 128, 0.3) !important;
                    border: 1px solid rgba(128, 128, 128, 0.5) !important;
                    border-radius: 15px !important;
                }
            """)
            
            # Use a closure to capture the target widget
            btn.clicked.connect(lambda checked, w=target_widget: self._scroll_to_widget(scroll_area, w))
            
            if buttons_per_row is not None:
                # Grid layout: calculate row and column
                row = button_index // buttons_per_row
                col = button_index % buttons_per_row
                nav_layout.addWidget(btn, row, col)
            else:
                # Horizontal layout
                nav_layout.addWidget(btn)
            
            button_index += 1
        
        if buttons_per_row is None:
            nav_layout.addStretch()
        
        # Insert at the top of the page container layout
        page_layout = page_container.layout()
        if page_layout:
            page_layout.insertWidget(0, nav_widget)

    def _scroll_to_widget(self, scroll_area, widget):
        # Get the y coordinate of the widget relative to the scroll area's content widget
        content_widget = scroll_area.widget()
        if content_widget:
            target_y = widget.mapTo(content_widget, QPoint(0, 0)).y()
            scroll_area.verticalScrollBar().setValue(target_y)
        

    
    def _on_bottom_bar_mode_changed(self, mode, is_checked):
        if is_checked:
            self.reviewer_bottom_bar_mode = mode

    def _create_image_gallery_group(self, key, folder, config_key, extensions=(".png", ".jpg", ".jpeg", ".gif", ".webp"), show_path=True, is_sub_group=False, title="", image_files_cache=None):
        group_container = QWidget()
        layout = QVBoxLayout(group_container)
        layout.setContentsMargins(0, 0 if is_sub_group else 10, 0, 0)
        
        if title: layout.addWidget(QLabel(title))

        scroll_area, grid_layout = self._create_gallery_ui()
        layout.addWidget(scroll_area)
        
        button_row = QHBoxLayout()
        choose_button = QPushButton("Choose Image..." if show_path else "Add Icon..."); choose_button.clicked.connect(lambda: self._choose_file_for_gallery(key)); button_row.addWidget(choose_button)
        delete_button = QPushButton("Delete Selected"); delete_button.clicked.connect(lambda: self._delete_from_gallery(key)); button_row.addWidget(delete_button)
        
        path_input = QLineEdit(); path_input.setPlaceholderText("No item selected"); path_input.setReadOnly(True)
        if show_path:
            layout.addWidget(QLabel("Selected File:")); layout.addWidget(path_input)

        # Determine which config source to use based on the config key pattern
        if config_key and config_key.startswith("onigiri_reviewer_bg_image"):
            # Reviewer background images are stored in the addon config
            selected_image = self.current_config.get(config_key, "")
        elif config_key:
            # Other images are stored in Anki's collection config
            selected_image = mw.col.conf.get(config_key, "")
        else:
            # Fallback for cases where config_key is empty
            selected_image = ""

        gallery_data = {
            'selected': selected_image,
            'folder': folder, 'extensions': extensions,
            'grid_layout': grid_layout, 'labels': [], 'thread': None, 'worker': None,
            'path_input': path_input if show_path else None, 'delete_button': delete_button
        }
        self.galleries[key].update(gallery_data)

        # Defer gallery population to avoid blocking UI
        self._defer_gallery_population(key)
        
        layout.addLayout(button_row)
        self._update_delete_button_state(key)
        return group_container

    def _create_gallery_ui(self):
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setFixedHeight(140)
        content_widget = QWidget(); grid_layout = QGridLayout(content_widget)
        grid_layout.setSpacing(10); grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll_area.setWidget(content_widget)
        return scroll_area, grid_layout

    def _defer_gallery_population(self, key):
        """Populate gallery after a short delay to avoid blocking UI"""
        QTimer.singleShot(100, lambda: self._populate_gallery_if_exists(key))
    
    def _populate_gallery_if_exists(self, key):
        """Populate gallery if it exists in the galleries dict"""
        if key in self.galleries:
            self._populate_gallery_placeholders(key)

    def _on_thumbnail_ready(self, key, index, pixmap, filename):
        gallery = self.galleries.get(key)
        if not gallery or index >= len(gallery['labels']): return
        
        label = gallery['labels'][index]
        label.setPixmap(pixmap)
        label.setToolTip(filename)
        label.setProperty("image_filename", filename)
        
        # Clear placeholder style
        label.setStyleSheet("background: transparent;")

        if 'overlays' not in gallery and gallery['selected'] == filename:
            label.setStyleSheet(THUMBNAIL_STYLE_SELECTED)

    def _populate_gallery_placeholders(self, key, image_files_cache=None):
        gallery = self.galleries[key]
        full_folder_path = os.path.join(self.addon_path, gallery['folder'])
        os.makedirs(full_folder_path, exist_ok=True)
        
        if image_files_cache is not None:
            image_files = image_files_cache
        else:
            try:
                image_files = sorted([f for f in os.listdir(full_folder_path) if f.lower().endswith(gallery['extensions'])])
            except OSError: image_files = []

        if not image_files:
            no_files_label = QLabel("No files here")
            no_files_label.setFixedSize(100, 100)
            no_files_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            bg = "rgba(255, 255, 255, 0.05)" if theme_manager.night_mode else "rgba(0, 0, 0, 0.05)"
            color = "#aaaaaa" if theme_manager.night_mode else "#666666"
            
            no_files_label.setStyleSheet(f"""
                background-color: {bg};
                border-radius: 10px;
                color: {color};
                font-size: 12px;
            """)
            gallery['grid_layout'].addWidget(no_files_label, 0, 0)
            return

        gallery['overlays'] = []
        
        # Determine sizes based on key
        if key == 'profile_pic':
            item_width, item_height = 110, 110
            img_width, img_height = 100, 100
            shape = 'circular'
        else: # profile_bg and others
            item_width, item_height = 120, 75
            img_width, img_height = 100, 55
            shape = 'rounded'

        for i, filename in enumerate(image_files):
            # Container
            container = QWidget()
            container.setFixedSize(item_width, item_height)
            container.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Image Label
            img_label = QLabel(container)
            img_label.setFixedSize(img_width, img_height)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            # Center the image in the container
            img_label.move((item_width - img_width) // 2, (item_height - img_height) // 2)
            
            # Placeholder content
            img_label.setText("⏳")
            img_label.setStyleSheet("background-color: rgba(128,128,128,0.1); border-radius: 10px;")

            # Selection Overlay
            overlay = SelectionOverlay(container, accent_color=self.accent_color)
            is_selected = (filename == gallery['selected'])
            overlay.setChecked(is_selected)
            
            # Position overlay (Top Right)
            overlay.move(item_width - 30, 5)
            overlay.setProperty("image_filename", filename)

            # Install event filter on container
            container.setProperty("gallery_key", key)
            container.setProperty("image_filename", filename)
            container.installEventFilter(self)

            gallery['grid_layout'].addWidget(container, i // 4, i % 4)
            gallery['labels'].append(img_label)
            gallery['overlays'].append(overlay)
        
        thread = QThread(); worker = ThumbnailWorker(key, full_folder_path, image_files, shape=shape)
        worker.moveToThread(thread)
        worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        
        gallery['thread'] = thread
        gallery['worker'] = worker

    def eventFilter(self, source, event):
        # Disabled dynamic resize for shape gallery - using fixed horizontal layout instead
        # if hasattr(self, 'shape_scroll_content') and source is self.shape_scroll_content and event.type() == QEvent.Type.Resize:
        #     try:
        #         self._reflow_shape_icons(event.size().width())
        #     except Exception as e:
        #         # Silently handle any reflow errors to prevent crashes
        #         print(f"Warning: Shape reflow error: {e}")
        #     return False

        if event.type() == QEvent.Type.MouseButtonPress:
            if source.property("gallery_key"):
                key = source.property("gallery_key")
                filename = source.property("image_filename")
                if filename:
                    gallery = self.galleries[key]
                    
                    # Toggle selection: if already selected, deselect it
                    if gallery['selected'] == filename:
                        gallery['selected'] = ""
                        if gallery.get('path_input'): 
                            gallery['path_input'].setText("")
                            gallery['path_input'].setPlaceholderText("No item selected")
                    else:
                        gallery['selected'] = filename
                        if gallery.get('path_input'): 
                            gallery['path_input'].setText(filename)
                    
                    if 'overlays' in gallery:
                        for overlay in gallery['overlays']:
                            overlay.setChecked(overlay.property("image_filename") == gallery['selected'])
                    else:
                        for label in gallery['labels']:
                            is_selected = label.property("image_filename") == gallery['selected']
                            label.setStyleSheet(THUMBNAIL_STYLE_SELECTED if is_selected else THUMBNAIL_STYLE)
                            
                    self._update_delete_button_state(key)
                    return True

            if source.property("icon_key"):
                self._change_icon(source)
                return True

        if source.property("text_stack"):
            text_stack = source.property("text_stack")
            hex_widget = text_stack.widget(1)

            if event.type() == QEvent.Type.Enter:
                text_stack.setCurrentIndex(1)
            elif event.type() == QEvent.Type.Leave:
                if not (hex_widget and hex_widget.hasFocus()):
                    text_stack.setCurrentIndex(0)
            return True
            
        return super().eventFilter(self, event)

    def _choose_file_for_gallery(self, key):
        gallery = self.galleries[key]
        ext_filter = f"Files (*{' *'.join(gallery['extensions'])})"; filepath, _ = QFileDialog.getOpenFileName(self, "Select File", "", ext_filter)
        if not filepath: return
        
        filename = os.path.basename(filepath)
        dest_path = os.path.join(self.addon_path, gallery['folder'], filename)
        
        try:
            shutil.copy(filepath, dest_path)
            self._refresh_gallery(key)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not copy file: {e}")

    def _delete_from_gallery(self, key):
        gallery = self.galleries[key]
        filename = gallery['selected']
        if not filename: return
        
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to permanently delete '{filename}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            filepath = os.path.join(self.addon_path, gallery['folder'], filename)
            try:
                os.remove(filepath)
                gallery['selected'] = ""
                if gallery.get('path_input'): gallery['path_input'].clear()
                self._refresh_gallery(key)
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Could not delete file: {e}")

    def _refresh_gallery(self, key):
        gallery = self.galleries[key]

        try:
            if gallery.get('thread') and gallery['thread'].isRunning():
                gallery['worker'].cancel()
                gallery['thread'].quit()
                gallery['thread'].wait()
        except RuntimeError:
            pass
        
        # Clear all items from the grid layout
        layout = gallery['grid_layout']
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        gallery['labels'] = []
        if 'overlays' in gallery:
            gallery['overlays'] = []
            
        self._populate_gallery_placeholders(key)
        self._update_delete_button_state(key)

    def _update_delete_button_state(self, key):
        gallery = self.galleries[key]
        if delete_button := gallery.get('delete_button'):
            delete_button.setEnabled(bool(gallery['selected']))

    def _create_icon_control_widget(self, key):
        # Modern Card-like widget for icon control
        control_widget = QWidget()
        control_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Determine background and border colors based on theme
        if theme_manager.night_mode:
            bg_color = "rgba(255, 255, 255, 0.05)"
            border_color = "rgba(255, 255, 255, 0.1)"
            hover_color = "rgba(255, 255, 255, 0.1)"
            text_color = "#e0e0e0"
        else:
            bg_color = "rgba(0, 0, 0, 0.03)"
            border_color = "rgba(0, 0, 0, 0.1)"
            hover_color = "rgba(0, 0, 0, 0.06)"
            text_color = "#212121"

        control_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QWidget:hover {{
                background-color: {hover_color};
                border-color: {text_color};
            }}
        """)
        
        layout = QHBoxLayout(control_widget)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        
        # Icon Preview
        preview_label = QLabel()
        preview_label.setFixedSize(32, 32)
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setStyleSheet("background: transparent; border: none;") # Reset style for label inside card
        
        # Info/Edit Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        name_label = QLabel(key.replace("_", " ").title())
        name_label.setStyleSheet(f"background: transparent; border: none; font-weight: bold; color: {text_color}; font-size: 13px;")
        
        sub_label = QLabel("Click to change")
        sub_label.setStyleSheet(f"background: transparent; border: none; color: {text_color}; opacity: 0.7; font-size: 10px;")
        
        text_layout.addWidget(name_label)
        text_layout.addWidget(sub_label)
        text_layout.addStretch()

        # Delete Button (Small trash icon or X)
        delete_btn = QPushButton()
        delete_btn.setFixedSize(24, 24)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setToolTip("Reset to Default")
        
        trash_icon_path = os.path.join(os.path.dirname(__file__), "system_files", "system_icons", "xmark-simple.svg") # Using xmark-simple.svg as delete icon
        
        if theme_manager.night_mode:
             delete_btn.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: rgba(255,0,0,0.2); }")
             trash_color = "#ff6b6b"
        else:
             delete_btn.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: rgba(255,0,0,0.1); }")
             trash_color = "#d32f2f"

        if os.path.exists(trash_icon_path):
            pixmap = QPixmap(trash_icon_path)
            if not pixmap.isNull():
                painter = QPainter(pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor(trash_color))
                painter.end()
                delete_btn.setIcon(QIcon(pixmap))
            else:
                delete_btn.setText("âœ•")
                delete_btn.setStyleSheet(delete_btn.styleSheet() + f"color: {trash_color}; font-weight: bold;")
        else:
            delete_btn.setText("âœ•")
            delete_btn.setStyleSheet(delete_btn.styleSheet() + f"color: {trash_color}; font-weight: bold;")

        delete_btn.clicked.connect(lambda: self._delete_icon(control_widget))

        layout.addWidget(preview_label)
        layout.addLayout(text_layout)
        layout.addStretch()
        layout.addWidget(delete_btn)
        
        # Properties
        control_widget.setProperty("icon_key", key)
        control_widget.setProperty("icon_filename", mw.col.conf.get(f"modern_menu_icon_{key}", ""))
        control_widget.setProperty("preview_label", preview_label)
        control_widget.setProperty("sub_label", sub_label) # To update text if needed
        
        # Make the whole widget clickable
        # We can't connect signals to QWidget directly, so we install an eventFilter or perform a trick.
        # But QWidget doesn't have clicked signal. 
        # Easier: wrap content in a transparent QPushButton overlay or use mousePressEvent.
        # Here we will use event filter in Settings class for simplicity as in original gallery:
        control_widget.installEventFilter(self)
        
        self._update_icon_preview_for_widget(control_widget)
        return control_widget

    def _update_icon_preview_for_widget(self, widget, size=24):
        key = widget.property("icon_key"); filename = widget.property("icon_filename"); preview_label = widget.property("preview_label")
        icon_color = "#e0e0e0" if theme_manager.night_mode else "#212121"; svg_xml = ""
        if filename:
            filepath = os.path.join(self.addon_path, "user_files/icons", filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f: svg_xml = f.read()
        if not svg_xml:
            default_key = 'star' if key == 'retention_star' else key
            data_uri = ICON_DEFAULTS.get(default_key, ""); 
            if data_uri.startswith("data:image/svg+xml,"): encoded_svg = data_uri.split(",", 1)[1]; svg_xml = urllib.parse.unquote(encoded_svg)
        if not svg_xml: preview_label.setPixmap(QPixmap()); return
        if 'stroke="currentColor"' in svg_xml: colored_svg = svg_xml.replace('stroke="currentColor"', f'stroke="{icon_color}"')
        elif 'fill="currentColor"' in svg_xml: colored_svg = svg_xml.replace('fill="currentColor"', f'fill="{icon_color}"')
        else: colored_svg = svg_xml.replace('<svg', f'<svg fill="{icon_color}" stroke="{icon_color}"', 1)
        renderer = QSvgRenderer(colored_svg.encode('utf-8')); pixmap = QPixmap(renderer.defaultSize()); pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap); renderer.render(painter); painter.end()
        preview_label.setPixmap(pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _change_icon(self, widget):
        if not widget: return
        
        current_filename = widget.property("icon_filename")
        
        picker = IconPickerDialog(current_filename, self.addon_path, self)
        
        def on_selected(filename):
            widget.setProperty("icon_filename", filename)
            self._update_icon_preview_for_widget(widget)
            
            # If this is part of the icon assignment widgets, confirm update? 
            # The original code just updated the property and waited for Save?
            # Yes, mw.col.conf is read in _update_icon_preview... wait.
            # _update_icon_preview uses: filename = widget.property("icon_filename")
            # But the SAVE function needs to know.
            # The properties are read back during save?
            # Actually, `self._save_config` probably iterates widgets.
            # Let's check how saving works later, but updating the property should be enough for now.
            
            # If we need to trigger immediate "apply" (like applying theme), we might need more.
            # But for Settings Dialog, changes usually apply on "Save" or "Apply".
            
            # Update the config key immediately for preview purposes if needed?
            # mw.col.conf[f"modern_menu_icon_{widget.property('icon_key')}"] = filename # This might be premature if user cancels settings.
            # But `_update_icon_preview_for_widget` reads from widget property primarily.
        
        picker.iconSelected.connect(on_selected)
        
        # Center picker
        parent_geo = self.geometry()
        picker_geo = picker.geometry()
        x = parent_geo.x() + (parent_geo.width() - picker_geo.width()) // 2
        y = parent_geo.y() + (parent_geo.height() - picker_geo.height()) // 2
        picker.move(x, y)
        picker.exec()

    def _delete_icon(self, widget): widget.setProperty("icon_filename", ""); self._update_icon_preview_for_widget(widget)
    def reset_icons_to_default(self):
        for widget in self.icon_assignment_widgets: self._delete_icon(widget)
        for widget in self.action_button_icon_widgets: self._delete_icon(widget)
        if hasattr(self, "retention_star_widget") and self.retention_star_widget:
            self._delete_icon(self.retention_star_widget)

    def create_icon_size_spinbox(self,key,default_value): spinbox=QSpinBox();spinbox.setMinimum(8);spinbox.setMaximum(48);spinbox.setSuffix(" px");spinbox.setValue(mw.col.conf.get(f"modern_menu_icon_size_{key}",default_value));self.icon_size_widgets[key]=spinbox;return spinbox
    def reset_icon_sizes_to_default(self):[widget.setValue(DEFAULT_ICON_SIZES[key])for key,widget in self.icon_size_widgets.items()]

    def _create_color_picker_row(self, name, default_value, mode, label_override=None, tooltip_text=None):
        row_layout=QHBoxLayout()
        display_name = label_override if label_override is not None else name
        label=QLabel(f"{display_name}:")
        if tooltip_text: label.setToolTip(tooltip_text)
        label.setFixedWidth(250)
        hex_input=QLineEdit(default_value)
        hex_input.setFixedWidth(100)
        color_button = CircularColorButton(default_value)
        
        color_button.clicked.connect(lambda _, le=hex_input, btn=color_button: self.open_color_picker(le, btn))
        hex_input.textChanged.connect(lambda txt, btn=color_button: btn.setColor(txt))
        
        row_layout.addWidget(label)
        row_layout.addWidget(hex_input)
        row_layout.addWidget(color_button)
        row_layout.addStretch()
        
        if mode in ["light", "dark"]: self.color_widgets[mode][name] = hex_input
        elif mode in ["light_accent", "dark_accent"]: setattr(self, f"{mode}_color_input", hex_input)
        else: setattr(self, f"{mode}_color_input", hex_input)
        return row_layout



    def open_color_picker(self, line_edit, button):
        initial_color = QColor(line_edit.text())
        
        # Load favorites from global config
        favorites = mw.col.conf.get("onigiri_favorites", [])
        if not isinstance(favorites, list):
            favorites = []
            
        picker = ModernColorPickerDialog(initial_color, self, favorite_colors=favorites)
        
        def on_color_selected(color):
            # Use HexArgb format if there is transparency, otherwise standard Hex
            if color.alpha() < 255:
                color_name = color.name(QColor.NameFormat.HexArgb)
            else:
                color_name = color.name()
                
            line_edit.setText(color_name)
            if isinstance(button, CircularColorButton):
                button.setColor(color_name)
                
        picker.colorSelected.connect(on_color_selected)
        
        # Center the picker over the settings dialog
        # Calculate center position relative to the parent (SettingsDialog)
        parent_geo = self.geometry()
        picker_geo = picker.geometry()
        x = parent_geo.x() + (parent_geo.width() - picker_geo.width()) // 2
        y = parent_geo.y() + (parent_geo.height() - picker_geo.height()) // 2
        picker.move(x, y)
        picker.raise_()
        
        picker.exec()
        
        # Save updated favorites to global config
        mw.col.conf["onigiri_favorites"] = picker.favorite_colors
        # We don't need to explicitly save mw.col.conf as Anki handles it, 
        # but if we wanted to be sure we could call mw.col.setMod() if available.
        # For settings like this, modifying the dict is usually sufficient in recent Anki versions 
        # as long as the collection is saved eventually.
    
    def _ensure_ui_for_theme_application(self):
        if not hasattr(self, 'light_accent_color_input'):
            dummy_colors_page = self.create_colors_page()
            dummy_colors_page.deleteLater()
        
        if not hasattr(self, 'color_radio'):
            dummy_bg_page = self.create_main_menu_page()
            dummy_bg_page.deleteLater()

    def reset_colors_to_default(self):
        default_colors=DEFAULTS["colors"]
        for mode in["light","dark"]:
            if hasattr(self,f"{mode}_accent_color_input"):getattr(self,f"{mode}_accent_color_input").setText(default_colors[mode]["--accent-color"])
            for name,widget in self.color_widgets[mode].items():
                if name in default_colors[mode]:widget.setText(default_colors[mode][name])

    def reset_stats_colors_to_default(self):
        stats_color_keys = ["--star-color", "--empty-star-color", "--heatmap-color", "--heatmap-color-zero"]
        default_colors = DEFAULTS["colors"]

        for mode in ["light", "dark"]:
            for key in stats_color_keys:
                if key in self.color_widgets[mode] and key in default_colors[mode]:
                    widget = self.color_widgets[mode][key]
                    default_value = default_colors[mode][key]
                    widget.setText(default_value)
        
        QMessageBox.information(self, "Colors Reset", "The stats colors have been reset to their default values.\nPress 'Save' to apply the changes.")

    def reset_heatmap_colors_to_default(self):
        """Reset only the heatmap-related colors to their default values."""
        heatmap_color_keys = ["--heatmap-color", "--heatmap-color-zero"]
        default_colors = DEFAULTS["colors"]

        for mode in ["light", "dark"]:
            for key in heatmap_color_keys:
                if key in self.color_widgets[mode] and key in default_colors[mode]:
                    widget = self.color_widgets[mode][key]
                    default_value = default_colors[mode][key]
                    widget.setText(default_value)
        
        QMessageBox.information(self, "Heatmap Colors Reset", "The heatmap colors have been reset to their default values.\nPress 'Save' to apply the changes.")


    def reset_background_to_default(self):
        self.color_radio.setChecked(True)
        if hasattr(self, 'bg_single_color_input'):
             self.bg_single_color_input.setText(DEFAULTS["colors"]["light"]["--bg"])
        self.bg_light_color_input.setText(DEFAULTS["colors"]["light"]["--bg"])
        self.bg_dark_color_input.setText(DEFAULTS["colors"]["dark"]["--bg"])
        
        for key in ['main_single', 'main_light', 'main_dark']:
            if key in self.galleries:
                self.galleries[key]['selected'] = ""
                if self.galleries[key].get('path_input'): 
                    self.galleries[key]['path_input'].setText("")
                self._refresh_gallery(key)
        
        self.bg_blur_spinbox.setValue(0)
        self.bg_opacity_spinbox.setValue(100)
    
    def reset_sidebar_to_default(self):
        # Set the main mode back to "Use Main Background Settings"
        self.sidebar_bg_main_radio.setChecked(True)
        
        # Reset the "Use Main" effect settings to "Color Overlay"
        self.sidebar_effect_overlay_radio.setChecked(True)
        self.sidebar_overlay_intensity_spinbox.setValue(30)
        self.overlay_light_color_color_input.setText("#FFFFFF")
        # Per your request, the dark mode default is #1D1D1D
        self.overlay_dark_color_color_input.setText("#1D1D1D")
        self.sidebar_effect_intensity_spinbox.setValue(50) # Also reset glassmorphism

        # Reset the "Custom" settings
        if 'sidebar_bg' in self.galleries:
            self.galleries['sidebar_bg']['selected'] = ""
            if self.galleries['sidebar_bg'].get('path_input'):
                self.galleries['sidebar_bg']['path_input'].setText("")
            self._refresh_gallery('sidebar_bg')
            
        self.sidebar_bg_type_color_radio.setChecked(True)
        self.sidebar_bg_light_color_input.setText("#F3F3F3")
        self.sidebar_bg_dark_color_input.setText("#2C2C2C")
        self.sidebar_bg_blur_spinbox.setValue(0)
        self.sidebar_bg_opacity_spinbox.setValue(100)

    def reset_reviewer_bg_to_default(self):
        """Reset reviewer background settings to defaults."""
        # Set mode to "Use Main Background"
        self.reviewer_bg_main_radio.setChecked(True)
        
        # Reset main background blur and opacity
        self.reviewer_bg_main_blur_spinbox.setValue(DEFAULTS["onigiri_reviewer_bg_main_blur"])
        self.reviewer_bg_main_opacity_spinbox.setValue(DEFAULTS["onigiri_reviewer_bg_main_opacity"])
        
        # Reset colors to defaults
        self.reviewer_bg_light_color_input.setText(DEFAULTS["onigiri_reviewer_bg_light_color"])
        self.reviewer_bg_dark_color_input.setText(DEFAULTS["onigiri_reviewer_bg_dark_color"])
        
        # Clear all reviewer background images
        for key in ['reviewer_bg_light', 'reviewer_bg_dark']:
            if key in self.galleries:
                self.galleries[key]['selected'] = ""
                if self.galleries[key].get('path_input'):
                    self.galleries[key]['path_input'].setText("")
                self._refresh_gallery(key)
        
        # Reset blur and opacity for custom mode
        self.reviewer_bg_blur_spinbox.setValue(DEFAULTS["onigiri_reviewer_bg_blur"])
        self.reviewer_bg_opacity_spinbox.setValue(DEFAULTS["onigiri_reviewer_bg_opacity"])
        
        QMessageBox.information(self, "Reviewer Background Reset", "The reviewer background settings have been reset to default values.\nPress 'Save' to apply the changes.")

    def reset_reviewer_bottom_bar_to_default(self):
        """Reset reviewer bottom bar background settings to defaults."""
        # Set mode to "Match Reviewer Background"
        self.reviewer_bar_match_reviewer_bg_radio.setChecked(True)
        
        # Reset match main settings
        self.reviewer_bar_match_main_blur_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_match_main_blur"])
        self.reviewer_bar_match_main_opacity_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_match_main_opacity"])

        # Reset match reviewer bg settings
        self.reviewer_bar_match_reviewer_bg_blur_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_match_reviewer_bg_blur"])
        self.reviewer_bar_match_reviewer_bg_opacity_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity"])
        
        # Reset custom colors
        self.reviewer_bar_light_color_input.setText(DEFAULTS["onigiri_reviewer_bottom_bar_bg_light_color"])
        self.reviewer_bar_dark_color_input.setText(DEFAULTS["onigiri_reviewer_bottom_bar_bg_dark_color"])
        
        # Clear bottom bar image
        if 'reviewer_bar_bg' in self.galleries:
            self.galleries['reviewer_bar_bg']['selected'] = ""
            if self.galleries['reviewer_bar_bg'].get('path_input'):
                self.galleries['reviewer_bar_bg']['path_input'].setText("")
            self._refresh_gallery('reviewer_bar_bg')
        
        # Reset blur and opacity
        self.reviewer_bar_blur_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_bg_blur"])
        self.reviewer_bar_opacity_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_bg_opacity"])
        
        QMessageBox.information(self, "Bottom Bar Reset", "The bottom bar background settings have been reset to default values.\nPress 'Save' to apply the changes.")


    def _animate_visibility(self, widget, should_be_visible, animate=True):
        """Animates the visibility of a widget by changing its height."""
        # If animation is disabled or dialog not visible, set state immediately
        if not animate or not self.isVisible():
            widget.setVisible(should_be_visible)
            if should_be_visible:
                widget.setMaximumHeight(16777215)
                widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            else:
                widget.setMaximumHeight(0)
                widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
            return

        # Stop any running animation
        if hasattr(widget, '_visibility_anim') and widget._visibility_anim.state() == QPropertyAnimation.State.Running:
            widget._visibility_anim.stop()
            widget._visibility_anim.deleteLater()

        if should_be_visible:
            # Already visible and expanded - nothing to do
            if widget.isVisible() and widget.maximumHeight() == 16777215:
                return

            # Make widget visible but collapsed before animating
            if not widget.isVisible():
                widget.setMaximumHeight(0)
                widget.setVisible(True)

            # Set size policy for animation
            widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            
            # Force layout update to get accurate size hint
            widget.adjustSize()
            widget.updateGeometry()
            QGuiApplication.processEvents()
            
            target_height = widget.sizeHint().height()
            
            # Create and configure animation
            anim = QPropertyAnimation(widget, b"maximumHeight", self)
            anim.setDuration(250)
            anim.setStartValue(0)
            anim.setEndValue(target_height)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            
            def on_show_finish():
                if widget.isVisible():
                    widget.setMaximumHeight(16777215)
                    widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
                    widget.updateGeometry()

            anim.finished.connect(on_show_finish)
            
            widget._visibility_anim = anim
            anim.start()
        else:
            # Already hidden - nothing to do
            if not widget.isVisible():
                return
            
            # Immediately hide the widget to prevent flickering
            widget.setVisible(False)
            widget.setMaximumHeight(0)
            widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
            widget.updateGeometry()

    def _update_color_theme_visibility(self):
        """Update visibility of single/separate color pickers with animation."""
        is_single = self.color_theme_single_radio.isChecked()
        is_separate = self.color_theme_separate_radio.isChecked()
        # is_accent = self.color_theme_accent_radio.isChecked() # Implicitly true if neither above is true

        target_widget = None
        if is_single:
            target_widget = self.bg_color_single_container
        elif is_separate:
            target_widget = self.bg_color_separate_container
        
        # Determine what to hide
        # We must NOT check isVisible() here, because during initialization (before dialog is shown),
        # isVisible() returns False for everything, causing nothing to be added to this list,
        # and thus nothing gets hidden.
        widgets_to_hide = []
        if self.bg_color_single_container is not target_widget:
            widgets_to_hide.append(self.bg_color_single_container)
        if self.bg_color_separate_container is not target_widget:
            widgets_to_hide.append(self.bg_color_separate_container)

        # Optimization: If dialog is not visible (initialization), just set visibility and return.
        # This prevents unnecessary animations and ensures correct initial state.
        if not self.isVisible():
            for w in widgets_to_hide:
                w.setVisible(False)
            if target_widget:
                target_widget.setVisible(True)
                target_widget.setMaximumHeight(16777215)
            return

        # If target is already visible and nothing to hide, we are done
        if target_widget and target_widget.isVisible() and not widgets_to_hide:
            return
        # If no target and nothing to hide (already in accent mode), done
        if not target_widget and not widgets_to_hide:
            return

        # Atomic update to prevent flickering
        self.setUpdatesEnabled(False)
        start_height = 0
        try:
            # Hide unwanted widgets and capture height
            for w in widgets_to_hide:
                if w.isVisible():
                    start_height = max(start_height, w.height())
                w.setVisible(False)
            
            if target_widget:
                # Prepare target widget
                # IMPORTANT: Set max height BEFORE showing to prevent flickering/jumping
                target_widget.setMaximumHeight(start_height)
                target_widget.setVisible(True)
                target_widget.updateGeometry()
                
                # Calculate target height
                target_height = target_widget.sizeHint().height()
                if target_height < 50: target_height = 100 # Fallback
        finally:
            self.setUpdatesEnabled(True)
        
        if target_widget:
            self.color_anim = QPropertyAnimation(target_widget, b"maximumHeight")
            self.color_anim.setDuration(250)
            self.color_anim.setStartValue(start_height)
            self.color_anim.setEndValue(target_height)
            self.color_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.color_anim.finished.connect(lambda: target_widget.setMaximumHeight(16777215))
            self.color_anim.start()

    def _update_image_theme_visibility(self):
        """Update visibility of single/separate image galleries with animation."""
        is_single = self.image_theme_single_radio.isChecked()
        target_widget = self.bg_image_single_container if is_single else self.bg_image_separate_container
        other_widget = self.bg_image_separate_container if is_single else self.bg_image_single_container
        
        if target_widget.isVisible():
            return

        # Atomic update to prevent flickering
        self.setUpdatesEnabled(False)
        try:
            # Capture start height from the currently visible widget
            start_height = other_widget.height() if other_widget.isVisible() else 0
            other_widget.setVisible(False)
            
            # Prepare target widget
            # IMPORTANT: Set max height BEFORE showing to prevent flickering/jumping
            target_widget.setMaximumHeight(start_height)
            target_widget.setVisible(True)
            target_widget.updateGeometry()
            
            target_height = target_widget.sizeHint().height()
            if target_height < 100: target_height = 300 # Fallback
        finally:
            self.setUpdatesEnabled(True)
        
        self.image_anim = QPropertyAnimation(target_widget, b"maximumHeight")
        self.image_anim.setDuration(250)
        self.image_anim.setStartValue(start_height)
        self.image_anim.setEndValue(target_height)
        self.image_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.image_anim.finished.connect(lambda: target_widget.setMaximumHeight(16777215))
        self.image_anim.start()

    def toggle_background_options(self, checked=None): 
        # Prevent flickering by ignoring the signal from the button being unchecked
        if isinstance(self.sender(), QRadioButton) and not self.sender().isChecked():
            return

        # Atomic update for initial visibility state
        self.setUpdatesEnabled(False)
        try:
            is_color = self.color_radio.isChecked()
            is_image = self.image_color_radio.isChecked()
            is_slideshow = self.slideshow_radio.isChecked()

            should_animate_color_group = False
            
            # Handle Accent Color radio button visibility
            # Show only when "Solid Color" is selected
            if hasattr(self, 'color_theme_accent_radio'):
                self.color_theme_accent_radio.setVisible(is_color)
                # If accent was selected but we're switching to Image/Slideshow, reset to "One theme color"
                if not is_color and self.color_theme_accent_radio.isChecked():
                    self.color_theme_single_radio.setChecked(True)
            
            # Handle Color Group Visibility
            if hasattr(self, 'main_bg_color_group'):
                should_be_visible = is_color or is_image or is_slideshow
                is_currently_visible = self.main_bg_color_group.isVisible()
                
                if should_be_visible and not is_currently_visible:
                    # Transitioning from Hidden -> Visible (e.g. Accent -> Color)
                    # Prepare for animation
                    self.main_bg_color_group.setMaximumHeight(0)
                    self.main_bg_color_group.setVisible(True)
                    should_animate_color_group = True
                elif not should_be_visible:
                    self.main_bg_color_group.setVisible(False)
                # If already visible and staying visible, do nothing

            # Handle Image/Slideshow Groups with Animation ("Enlarge First")
            target_widget = None
            start_height = 0
            
            if hasattr(self, 'main_bg_image_group') and hasattr(self, 'main_bg_slideshow_group'):
                if is_image:
                    target_widget = self.main_bg_image_group
                    if self.main_bg_slideshow_group.isVisible():
                        start_height = self.main_bg_slideshow_group.height()
                elif is_slideshow:
                    target_widget = self.main_bg_slideshow_group
                    if self.main_bg_image_group.isVisible():
                        start_height = self.main_bg_image_group.height()
                
                # Hide non-selected widgets immediately
                if not is_image:
                    self.main_bg_image_group.setVisible(False)
                if not is_slideshow:
                    self.main_bg_slideshow_group.setVisible(False)

                if target_widget:
                    # If widget is already visible, do nothing (or maybe just ensure it's fully visible)
                    if target_widget.isVisible() and target_widget.maximumHeight() > 0:
                        pass # Already visible
                    else:
                        # Prepare for animation
                        # IMPORTANT: Set max height BEFORE showing to prevent flickering/jumping
                        target_widget.setMaximumHeight(start_height)
                        target_widget.setVisible(True)
                        
                        # Calculate target height based on content
                        # We force the layout to calculate the size hint
                        target_widget.updateGeometry()
        finally:
            self.setUpdatesEnabled(True)

        # Start animations AFTER updates are re-enabled
        
        # 1. Animate Color Group if needed
        if should_animate_color_group:
            self.main_bg_color_group.updateGeometry()
            color_target_height = self.main_bg_color_group.sizeHint().height()
            if color_target_height < 50: color_target_height = 100
            
            self.color_group_anim = QPropertyAnimation(self.main_bg_color_group, b"maximumHeight")
            self.color_group_anim.setDuration(300)
            self.color_group_anim.setStartValue(0)
            self.color_group_anim.setEndValue(color_target_height)
            self.color_group_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.color_group_anim.finished.connect(lambda: self.main_bg_color_group.setMaximumHeight(16777215))
            self.color_group_anim.start()

        # 2. Animate Image/Slideshow Group if needed
        if hasattr(self, 'main_bg_image_group') and hasattr(self, 'main_bg_slideshow_group'):
             if target_widget:
                # Check if we need to animate (if max height is restricted or we are switching)
                # If start_height > 0 (switching) or max height is 0 (opening), we animate.
                # If it's already open and fully visible, we might skip, but re-animating is safer to ensure correct state.
                
                target_height = target_widget.sizeHint().height()
                if target_height < 100: target_height = 500
                
                # Animate height
                self.anim = QPropertyAnimation(target_widget, b"maximumHeight")
                self.anim.setDuration(300) # 300ms duration
                self.anim.setStartValue(start_height)
                self.anim.setEndValue(target_height)
                self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)
                
                # On finished, reset maximum height to allow dynamic resizing
                self.anim.finished.connect(lambda: target_widget.setMaximumHeight(16777215))
                self.anim.start()        
    def toggle_sidebar_background_options(self): 
        self.sidebar_main_options_group.setVisible(self.sidebar_bg_main_radio.isChecked())
        self.sidebar_custom_options_group.setVisible(self.sidebar_bg_custom_radio.isChecked())    
    def toggle_sidebar_bg_type_options(self):
        """Shows/hides options based on the selected sidebar background type."""
        try:
            is_color = self.sidebar_bg_type_color_radio.isChecked()
            is_accent = self.sidebar_bg_type_accent_radio.isChecked()
            is_image_color = self.sidebar_bg_type_image_color_radio.isChecked()

            if self.sidebar_color_group:
                self.sidebar_color_group.setVisible(is_color or is_image_color)

            if self.sidebar_image_group:
                self.sidebar_image_group.setVisible(is_image_color)

            if self.sidebar_effects_container:
                # Blur and Opacity are only for modes with an image
                self.sidebar_bg_blur_label.setVisible(is_image_color)
                self.sidebar_bg_blur_spinbox.setVisible(is_image_color)
                self.sidebar_bg_opacity_label.setVisible(is_image_color)
                self.sidebar_bg_opacity_spinbox.setVisible(is_image_color)

                # Transparency is only for modes without an image
                self.sidebar_bg_transparency_label.setVisible(is_color or is_accent)
                self.sidebar_bg_transparency_spinbox.setVisible(is_color or is_accent)

        except RuntimeError:
            # This error can occur if the widgets are accessed after they've been
            # deleted (e.g., when the settings dialog is closing).
            # We can safely ignore it to prevent a crash.
            pass
    def toggle_profile_page_bg_options(self): is_gradient = self.profile_page_bg_gradient_radio.isChecked(); self.profile_page_color_group.setVisible(not is_gradient); self.profile_page_gradient_group.setVisible(is_gradient)
    
    def toggle_reviewer_bar_options(self):
        is_main = self.reviewer_bar_main_radio.isChecked()
        is_match_reviewer_bg = self.reviewer_bar_match_reviewer_bg_radio.isChecked()
        is_custom = not (is_main or is_match_reviewer_bg)
        
        self.reviewer_bar_match_main_group.setVisible(is_main)
        self.reviewer_bar_match_reviewer_bg_group.setVisible(is_match_reviewer_bg)
        self.reviewer_bar_custom_group.setVisible(is_custom)

        if is_custom:
            is_color = self.reviewer_bar_color_radio.isChecked()
            is_image_color = self.reviewer_bar_image_color_radio.isChecked()

            # Show color picker for 'Solid Color' and 'Image'
            self.reviewer_bar_color_group.setVisible(is_color or is_image_color)

            # Show image gallery and effects (blur, opacity) for 'Image' and 'Image'
            image_options_visible = is_image_color
            self.reviewer_bar_image_group.setVisible(image_options_visible)

            if 'reviewer_bar_bg' in self.galleries and self.galleries['reviewer_bar_bg'].get('effects_widget'):
                self.galleries['reviewer_bar_bg']['effects_widget'].setVisible(image_options_visible)

    def _on_hide_all_stats_toggled(self, checked):
        self.hide_studied_stat_checkbox.setChecked(checked)
        self.hide_time_stat_checkbox.setChecked(checked)
        self.hide_pace_stat_checkbox.setChecked(checked)
        self.hide_retention_stat_checkbox.setChecked(checked)

    def create_themes_page(self):
        page, layout = self._create_scrollable_page()

        # --- Load Themes ---
        official_themes, user_themes = self._load_themes()

        # --- Section 1: Official Themes ---
        official_section = SectionGroup(
            "Official Themes",
            self,
            border=True,
            description="Choose from a selection of built-in color palettes."
        )
        # --- FIX START ---
        # Create the grid layout separately...
        self.official_themes_grid_layout = QGridLayout()
        self.official_themes_grid_layout.setSpacing(15)
        # ...and then add it to the section using its helper method.
        official_section.add_layout(self.official_themes_grid_layout)
        # --- FIX END ---
        self._populate_grid_with_themes(self.official_themes_grid_layout, official_themes, deletable=False)
        layout.addWidget(official_section)

        # --- Section 2: Your Themes ---
        user_section = SectionGroup(
            "Your Themes",
            self,
            border=True,
            description="Themes you have created or imported."
        )

        # Add navigation buttons
        sections = {
            "Official Themes": official_section,
            "Your Themes": user_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections)
        # --- FIX START ---
        # Do the same for the user themes section.
        self.user_themes_grid_layout = QGridLayout()
        self.user_themes_grid_layout.setSpacing(15)
        user_section.add_layout(self.user_themes_grid_layout)
        # --- FIX END ---
        self._populate_grid_with_themes(self.user_themes_grid_layout, user_themes, deletable=True)
        layout.addWidget(user_section)

        # --- Action Buttons (remain the same) ---
        button_layout = QHBoxLayout()
        import_button = QPushButton("Import Theme")
        import_button.clicked.connect(self._import_theme)

        export_button = QPushButton("Export Current Theme")
        export_button.setToolTip("Saves your current color settings as a new theme file.")
        export_button.clicked.connect(self._export_current_theme)

        reset_button = QPushButton("Reset Theme to Default")
        reset_button.setToolTip("Resets all theme and palette colors to the add-on's original defaults.")
        reset_button.clicked.connect(self.reset_theme_to_default)

        button_layout.addWidget(import_button)
        button_layout.addWidget(export_button)
        button_layout.addStretch()
        button_layout.addWidget(reset_button)

        layout.addLayout(button_layout)
        layout.addStretch()
        return page

    def _apply_theme(self, theme_data: dict):
        """Applies the selected theme's colors and assets to the config and live UI."""
        light_palette = theme_data.get("light", {})
        dark_palette = theme_data.get("dark", {})
        assets = theme_data.get("assets", {})

        # 1. Update the internal config dictionary
        self.current_config["colors"]["light"].update(light_palette)
        self.current_config["colors"]["dark"].update(dark_palette)
        
        # 1b. Apply Assets (Images and Icons)
        if "images" in assets:
            for config_key, path in assets["images"].items():
                if os.path.exists(path):
                    # Config expects filenames relative to their folders for most keys
                    # Theme data now holds absolute paths (for preview validation)
                    # So we convert to basename for config application
                    self.current_config[config_key] = os.path.basename(path)
                    
                    # For legacy keys in mw.col.conf, sync them too
                    if config_key.startswith("modern_menu_"):
                        mw.col.conf[config_key] = os.path.basename(path)
                        
                    # Also explicit sync for onigiri_ keys if needed? 
                    # usually self.current_config syncs back on save, but we are applying LIVE.
                    # _apply_theme usually updates widgets.
                    # We should probably update the radio buttons / widgets too?
                    # The original _apply_theme didn't do that for images.
                    # But if we want instant feedback, we might need to.
                    # However, simply setting config might trigger hooks if any?
                    # For now, ensuring config is correct is step 1.
                    
        if "icons" in assets:
            applied_icons = []
            for icon_key, icon_value in assets["icons"].items():
                # icon_value should be just the filename (from import)
                # But use basename to be safe
                filename = os.path.basename(icon_value) if icon_value else ""
                if filename:
                    conf_key = f"modern_menu_icon_{icon_key}"
                    mw.col.conf[conf_key] = filename
                    applied_icons.append(f"{icon_key}: {filename}")
            
            if applied_icons:
                icon_msg = f"\n\nApplied {len(applied_icons)} custom icon(s):\n" + "\n".join(applied_icons[:5])
            else:
                icon_msg = ""
        else:
            icon_msg = ""

        # 1c. Apply Fonts
        if "font_config" in assets:
            for type_key, font_key in assets["font_config"].items():
                if type_key in ["main", "subtle"]:
                    mw.col.conf[f"onigiri_font_{type_key}"] = font_key

        # 1c. Apply Fonts
        if "font_config" in assets:
            for type_key, font_key in assets["font_config"].items():
                if type_key in ["main", "subtle"]:
                    mw.col.conf[f"onigiri_font_{type_key}"] = font_key

        # 1d. Apply Reviewer Settings
        if "reviewer_settings" in theme_data:
            self.current_config.update(theme_data["reviewer_settings"])

        # 2. Update the UI widgets on other pages in real-time
        # This uses hasattr to avoid errors if a page hasn't been loaded yet
        
        # Update Palette page
        for mode, palette in [("light", light_palette), ("dark", dark_palette)]:
            if mode in self.color_widgets:
                for key, widget in self.color_widgets[mode].items():
                    if key in palette:
                        widget.setText(palette[key])
        
        # Update Accent colors
        if hasattr(self, "light_accent_color_input") and "--accent-color" in light_palette:
            self.light_accent_color_input.setText(light_palette["--accent-color"])
        if hasattr(self, "dark_accent_color_input") and "--accent-color" in dark_palette:
            self.dark_accent_color_input.setText(dark_palette["--accent-color"])
            
        # Update Backgrounds page
        if hasattr(self, "bg_light_color_input") and "--bg" in light_palette:
            self.bg_light_color_input.setText(light_palette["--bg"])
        if hasattr(self, "bg_dark_color_input") and "--bg" in dark_palette:
            self.bg_dark_color_input.setText(dark_palette["--bg"])
        
        # Update Icon previews after applying icons
        if "icons" in assets and hasattr(self, "icon_widgets"):
            for icon_key in assets["icons"].keys():
                if icon_key in self.icon_widgets:
                    control_widget = self.icon_widgets[icon_key]
                    preview_label = control_widget.property("preview_label")
                    if preview_label:
                        # Reload the icon preview
                        conf_key = f"modern_menu_icon_{icon_key}"
                        new_filename = mw.col.conf.get(conf_key, "")
                        if new_filename:
                            icon_path = os.path.join(self.addon_path, "user_files", "icons", new_filename)
                            if os.path.exists(icon_path):
                                # Update preview with new icon
                                pixmap = QPixmap(icon_path)
                                if not pixmap.isNull():
                                    scaled = pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                                    preview_label.setPixmap(scaled)
            
        showInfo(f"Theme applied! Press 'Save' to keep the changes.{icon_msg}")

    def _load_themes(self):
        """Loads built-in and custom themes, returning them as separate dictionaries."""
        official_themes = THEMES.copy()
        user_themes = {}

        # Load user themes from JSON files
        for filename in os.listdir(self.user_themes_path):
            if filename.lower().endswith(".json"):
                filepath = os.path.join(self.user_themes_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        theme_data = json.load(f)

                    # Basic validation
                    if isinstance(theme_data, dict) and "light" in theme_data and "dark" in theme_data:
                        theme_name = os.path.splitext(filename)[0].replace("_", " ").title()
                        user_themes[theme_name] = theme_data
                    else:
                        print(f"Onigiri: Invalid theme file format in {filename}")
                except (json.JSONDecodeError, OSError) as e:
                    print(f"Onigiri: Could not load theme file {filename}: {e}")

        return official_themes, user_themes

    def _populate_grid_with_themes(self, grid_layout, themes_dict, deletable=False):
        """Helper function to populate a given QGridLayout with theme cards."""
        while grid_layout.count():
            child = grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not themes_dict:
            if deletable:
                grid_layout.addWidget(QLabel("No custom themes have been imported yet."), 0, 0)
            return

        # Create the icon once, before the loop
        delete_icon = self._create_delete_icon() if deletable else None

        row, col = 0, 0
        num_cols = 2

        for name, data in sorted(themes_dict.items()):
            card = ThemeCardWidget(name, data, deletable=deletable, delete_icon=delete_icon)
            card.theme_selected.connect(self._apply_theme)
            if deletable:
                card.delete_requested.connect(self._delete_user_theme) # Connect the new signal
            
            grid_layout.addWidget(card, row, col)

            col += 1
            if col >= num_cols:
                col = 0; row += 1

    def _import_theme(self):
        """Opens a file dialog to import a theme from a JSON or .onigiri file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, 
            "Import Theme", 
            "", 
            "Onigiri Theme Files (*.json *.onigiri);;JSON Files (*.json);;Onigiri Files (*.onigiri)"
        )
        if not filepath:
            return

        try:
            filename = os.path.basename(filepath)
            
            # Handle .json files (legacy)
            if filename.lower().endswith(".json"):
                with open(filepath, 'r', encoding='utf-8') as f:
                    theme_data = json.load(f)
                
                # Validate
                if not isinstance(theme_data, dict) or "light" not in theme_data or "dark" not in theme_data:
                    QMessageBox.warning(self, "Import Error", "The selected file is not a valid Onigiri theme file.")
                    return

                # Copy
                dest_path = os.path.join(self.user_themes_path, filename)
                shutil.copy(filepath, dest_path)
            
            # Handle .onigiri files (zip)
            elif filename.lower().endswith(".onigiri"):
                import zipfile
                if not zipfile.is_zipfile(filepath):
                    QMessageBox.warning(self, "Import Error", "The selected file is not a valid zip archive.")
                    return

                with zipfile.ZipFile(filepath, 'r') as zf:
                    # 1. Read theme.json
                    try:
                        with zf.open('theme.json') as f:
                            theme_data = json.load(f)
                    except KeyError:
                        QMessageBox.warning(self, "Import Error", "The .onigiri file is missing 'theme.json'.")
                        return

                    # 2. Extract Assets
                    # We will modify theme_data to point to the new extracted locations
                    assets = theme_data.get("assets", {})
                    theme_name = os.path.splitext(filename)[0] # e.g. "My_Theme"
                    
                    # Prepare directories
                    images_dest_dir = os.path.join(self.addon_path, "user_files", "images", theme_name)
                    fonts_dest_dir = os.path.join(self.addon_path, "user_files", "fonts")
                    icons_dest_dir = os.path.join(self.addon_path, "user_files", "icons")
                    
                    os.makedirs(images_dest_dir, exist_ok=True)
                    os.makedirs(fonts_dest_dir, exist_ok=True)
                    os.makedirs(icons_dest_dir, exist_ok=True)

                    # Extract Images
                    if "images" in assets:
                        for config_key, archive_path in assets["images"].items():
                            try:
                                # archive_path is like "images/main_bg/bg.png" or "images/filename.png"
                                # We need to respect the subfolder if present
                                parts = archive_path.split("/")
                                if len(parts) >= 3 and parts[0] == "images":
                                    # images/subfolder/filename
                                    subfolder = parts[1]
                                    filename = parts[-1]
                                    dest_dir = os.path.join(self.addon_path, "user_files", subfolder)
                                else:
                                    # Fallback (old export or flat structure)
                                    subfolder = "images" # Should we dump to images? 
                                    # If legacy export didn't use subfolders, we might have issues.
                                    # But we just implemented the "new" export. Let's assume theme_name/images separation if needed.
                                    # But better to try to guess based on config_key? 
                                    # No, let's just use a generic 'imported_assets' if unsure or stick to 'images/{ThemeName}' logic from before?
                                    # The 'new' export I just wrote ALWAYS uses "images/subfolder/filename".
                                    # So we rely on that.
                                    # If not matching, we default to images/{ThemeName} from previous logic.
                                    dest_dir = images_dest_dir # defined earlier as user_files/images/{theme_name}
                                    filename = os.path.basename(archive_path)

                                os.makedirs(dest_dir, exist_ok=True)
                                target_path = os.path.join(dest_dir, filename)
                                
                                # Read from zip and write to target
                                with zf.open(archive_path) as source, open(target_path, "wb") as target:
                                    shutil.copyfileobj(source, target)
                                
                                # Update theme_data to point to absolute path
                                # This allows ThemeCardWidget to finding the preview image immediately
                                theme_data["assets"]["images"][config_key] = target_path
                            except KeyError:
                                print(f"Asset {archive_path} not found in zip.")

                    # Extract Fonts
                    if "fonts" in assets:
                         for font_key, archive_path in assets["fonts"].items():
                            try:
                                asset_filename = os.path.basename(archive_path)
                                target_path = os.path.join(fonts_dest_dir, asset_filename)
                                with zf.open(archive_path) as source, open(target_path, "wb") as target:
                                    shutil.copyfileobj(source, target)
                                # We don't need to update reference in theme_data if it uses filename as key
                                # But if we stored archive_path, we might? 
                                # Export stored key -> archive_path.
                                # Fonts.py loads all from user_files/fonts. 
                                # So by just placing it there, it becomes available.
                            except KeyError:
                                pass

                    # Extract Icons
                    if "icons" in assets:
                        for icon_key, archive_path in assets["icons"].items():
                            try:
                                asset_filename = os.path.basename(archive_path)
                                target_path = os.path.join(icons_dest_dir, asset_filename)
                                with zf.open(archive_path) as source, open(target_path, "wb") as target:
                                    shutil.copyfileobj(source, target)
                                
                                # Update theme data with just the filename
                                theme_data["assets"]["icons"][icon_key] = asset_filename
                            except KeyError:
                                pass
                    
                    # Preserve icon_config if it exists (for preview)
                    # icon_config contains all icon selections (including defaults)
                    # We don't need to modify it, just ensure it's in theme_data

                    # 3. Save the modified theme.json to user_themes
                    # We rename it to match the .onigiri filename
                    json_filename = theme_name + ".json"
                    json_dest_path = os.path.join(self.user_themes_path, json_filename)
                    
                    with open(json_dest_path, 'w', encoding='utf-8') as f:
                        json.dump(theme_data, f, indent=4)

            # Refresh the grid to show the new theme
            _, user_themes = self._load_themes()
            self._populate_grid_with_themes(self.user_themes_grid_layout, user_themes)
            showInfo("Theme imported successfully!")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Could not import the theme file:\n{e}")

    def _export_current_theme(self):
        """Gathers ALL current theme colors and assets, saving them to a .onigiri zip file."""
        name, ok = QInputDialog.getText(self, "Export Theme", "Enter a name for your theme:")
        if not ok or not name:
            return

        light_palette = {}
        dark_palette = {}

        # 1. Gather Colors
        for mode, palette in [("light", light_palette), ("dark", dark_palette)]:
            for key in ALL_THEME_KEYS:
                # Default to the value in the in-memory config
                value = self.current_config["colors"][mode].get(key)

                # Check UI widgets for latest values
                if key == "--accent-color" and hasattr(self, f"{mode}_accent_color_input"):
                    value = getattr(self, f"{mode}_accent_color_input").text()
                elif key == "--bg" and hasattr(self, f"bg_{mode}_color_input"):
                    value = getattr(self, f"bg_{mode}_color_input").text()
                elif key in self.color_widgets.get(mode, {}):
                    value = self.color_widgets[mode][key].text()
                
                if value is not None:
                    palette[key] = value

        # 1b. Gather Reviewer Settings
        reviewer_settings = {}
        for key in REVIEWER_THEME_KEYS:
            value = self.current_config.get(key)
            if value is not None:
                reviewer_settings[key] = value

        theme_data = {
            "light": light_palette, 
            "dark": dark_palette,
            "reviewer_settings": reviewer_settings,
            "assets": {
                "fonts": {}, # Map: local_filename -> archive_path
                "images": {},
                "icons": {},
                "font_config": {}, # Store which font key is selected for main/subtle
                "icon_config": {} # Store which icons are selected (even if defaults)
            }
        }

        # 2. Gather Assets
        assets_to_zip = [] # List of tuples: (source_path, archive_name)

        # Fonts
        # Check active fonts in config
        for font_type in ["main", "subtle"]:
            font_key = mw.col.conf.get(f"onigiri_font_{font_type}")
            if font_key:
                # Save the configuration selection
                theme_data["assets"]["font_config"][font_type] = font_key
                
                # If it's a user font, we assume the key is the filename (as per fonts.py: load_user_fonts)
                # We check if it exists in user_files/fonts
                font_path = os.path.join(self.addon_path, "user_files", "fonts", font_key)
                if os.path.exists(font_path) and os.path.isfile(font_path):
                    archive_path = f"fonts/{font_key}"
                    # Avoid adding duplicates
                    if not any(a[1] == archive_path for a in assets_to_zip):
                        assets_to_zip.append((font_path, archive_path))
                        # We list it in assets["fonts"] just to track what's included
                        theme_data["assets"]["fonts"][font_key] = archive_path
        
        # Images
        # Map config keys to their respective subfolders in user_files
        image_key_map = {
            "modern_menu_background_image": "main_bg",
            "modern_menu_background_image_light": "main_bg",
            "modern_menu_background_image_dark": "main_bg",
            "onigiri_overview_bg_image": "main_bg",
            "onigiri_overview_bg_image_light": "main_bg",
            "onigiri_overview_bg_image_dark": "main_bg",
            "modern_menu_profile_bg_image": "profile_bg",
            "modern_menu_profile_picture": "profile",
            "modern_menu_sidebar_bg_image": "sidebar_bg",
            "onigiri_reviewer_bg_image": "reviewer_bg", 
            "onigiri_reviewer_bg_image_light": "reviewer_bg",
            "onigiri_reviewer_bg_image_dark": "reviewer_bg",
            "onigiri_reviewer_bottom_bar_bg_image": "reviewer_bar_bg",
        }
        
        active_images = {}
        for key, subfolder in image_key_map.items():
            # config often holds just the filename
            # We try self.current_config first, then mw.col.conf
            filename = self.current_config.get(key) or mw.col.conf.get(key)
            
            if filename and isinstance(filename, str):
                # Construct possible full path
                full_path = os.path.join(self.addon_path, "user_files", subfolder, filename)
                
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    archive_path = f"images/{subfolder}/{filename}"
                    # Avoid duplicates
                    if not any(a[1] == archive_path for a in assets_to_zip):
                        assets_to_zip.append((full_path, archive_path))
                        
                    active_images[key] = archive_path # Store archive path in theme.json

        theme_data["assets"]["images"] = active_images

        # Icons
        # Similar logic for icons. 
        # We need to find which icons are customized. 
        # `settings.py` creates icon widgets based on `modern_menu_icon_{key}` in `mw.col.conf`.
        # Note: Icons seem to be stored in `mw.col.conf`, not `self.current_config` (which mimics the add-on config).
        # We should check `mw.col.conf` for `modern_menu_icon_*`.
        
        active_icons = {}
        icon_config = {}
        
        # Iterate over all possible icon keys (we can get them from ICON_DEFAULTS)
        for icon_key in ICON_DEFAULTS.keys():
            conf_key = f"modern_menu_icon_{icon_key}"
            filename = mw.col.conf.get(conf_key, "")
            
            # Always save the configuration (even if it's empty/default)
            # This allows preview to show defaults
            icon_config[icon_key] = filename if filename else icon_key  # Use key for defaults
            
            if filename:
                filepath = os.path.join(self.addon_path, "user_files/icons", filename)
                if os.path.exists(filepath):
                    archive_path = f"icons/{filename}"
                    assets_to_zip.append((filepath, archive_path))
                    active_icons[icon_key] = archive_path

        theme_data["assets"]["icons"] = active_icons
        theme_data["assets"]["icon_config"] = icon_config

        # 3. Create Zip
        suggested_filename = name.lower().replace(" ", "_") + ".onigiri"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Theme As",
            os.path.join(self.user_themes_path, suggested_filename),
            "Onigiri Theme Files (*.onigiri)"
        )

        if not save_path:
            return

        try:
            import zipfile
            with zipfile.ZipFile(save_path, 'w') as zf:
                # Write theme.json
                zf.writestr('theme.json', json.dumps(theme_data, indent=4))
                
                # Write assets
                for source, dest in assets_to_zip:
                    zf.write(source, dest)
            
            showInfo(f"Theme '{name}' exported successfully as .onigiri file!")

            # If saved in local themes folder, refresh? 
            # (Currently .onigiri files might not appear until we implement the import/view logic)
            # For now, standard JSON themes are loaded. 
            # We might want to auto-extract it back to be usable immediately if saved locally?
            # Or just leave it as an export file. The user said "Import, export".
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Could not save the theme file:\n{e}")

    def reset_theme_to_default(self):
        """Resets all theme-related colors to their default values."""
        # Use a deep copy to avoid modifying the DEFAULTS constant
        default_colors = json.loads(json.dumps(DEFAULTS["colors"]))

        # 1. Update the internal config dictionary with the defaults
        self.current_config["colors"] = default_colors

        # 2. Update all relevant UI widgets if they have been created
        for mode, palette in default_colors.items():
            if mode not in ["light", "dark"]:
                continue

            # Update general color inputs (Palette, Sidebar, Main Menu, etc.)
            if mode in self.color_widgets:
                for key, widget in self.color_widgets[mode].items():
                    if key in palette:
                        widget.setText(palette[key])

            # Update Accent Color inputs
            if hasattr(self, f"{mode}_accent_color_input") and "--accent-color" in palette:
                getattr(self, f"{mode}_accent_color_input").setText(palette["--accent-color"])

            # Update the main Background Color input on the Backgrounds page
            if hasattr(self, f"bg_{mode}_color_input") and "--bg" in palette:
                getattr(self, f"bg_{mode}_color_input").setText(palette["--bg"])

        # 3. Refresh the settings dialog's own appearance
        self.apply_stylesheet()

        # 4. Inform the user
        showInfo("Theme colors have been reset to default. Press 'Save' to keep the changes.")
    
    def _delete_user_theme(self, theme_name: str):
        """Prompts for confirmation and deletes a user theme file."""
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to permanently delete the theme '{theme_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Convert theme name to filename (e.g., "My Awesome Theme" -> "my_awesome_theme.json")
            filename = theme_name.lower().replace(" ", "_") + ".json"
            filepath = os.path.join(self.user_themes_path, filename)

            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    showInfo(f"Theme '{theme_name}' deleted.")
                    
                    # Refresh the user themes grid
                    _, user_themes = self._load_themes()
                    self._populate_grid_with_themes(self.user_themes_grid_layout, user_themes, deletable=True)
                else:
                    QMessageBox.warning(self, "Error", f"Could not find theme file: {filename}")
            except OSError as e:
                QMessageBox.critical(self, "Error", f"Could not delete theme file:\n{e}")

    # <<< START NEW CODE >>>
    def _on_hide_toggled(self, checked):
        """Handle Focus mode toggle - Focus is the child/base level"""
        if not checked:
            # When Focus is turned OFF, turn OFF both Flow and Zen
            # Turn OFF Flow
            self.flow_mode_checkbox.blockSignals(True)
            if self.flow_mode_checkbox.isChecked():
                self.flow_mode_checkbox.setChecked(False)
                self.flow_mode_checkbox._start_animation(False)
            self.flow_mode_checkbox.blockSignals(False)
            
            # Turn OFF Zen
            self.max_hide_checkbox.blockSignals(True)
            if self.max_hide_checkbox.isChecked():
                self.max_hide_checkbox.setChecked(False)
                self.max_hide_checkbox._start_animation(False)
            self.max_hide_checkbox.blockSignals(False)
        # When Focus is turned ON, Flow and Zen remain as-is (no action needed)

    def _on_max_hide_toggled(self, checked):
        """Handle Zen mode toggle - Zen is the parent/highest level"""
        if checked:
            # When Zen is turned ON, turn ON both Flow and Focus
            # Turn ON Flow
            self.flow_mode_checkbox.blockSignals(True)
            if not self.flow_mode_checkbox.isChecked():
                self.flow_mode_checkbox.setChecked(True)
                self.flow_mode_checkbox._start_animation(True)
            self.flow_mode_checkbox.blockSignals(False)
            
            # Turn ON Focus
            self.hide_native_header_checkbox.blockSignals(True)
            if not self.hide_native_header_checkbox.isChecked():
                self.hide_native_header_checkbox.setChecked(True)
                self.hide_native_header_checkbox._start_animation(True)
            self.hide_native_header_checkbox.blockSignals(False)
        # When Zen is turned OFF, Flow and Focus remain as-is (no action needed)

    def _on_flow_toggled(self, checked):
        """Handle Flow mode toggle - Flow is the middle level"""
        if checked:
            # When Flow is turned ON, turn ON Focus
            self.hide_native_header_checkbox.blockSignals(True)
            if not self.hide_native_header_checkbox.isChecked():
                self.hide_native_header_checkbox.setChecked(True)
                self.hide_native_header_checkbox._start_animation(True)
            self.hide_native_header_checkbox.blockSignals(False)
            # Zen remains as-is (no action needed)
        else:
            # When Flow is turned OFF, turn OFF Zen (but Focus stays as-is)
            self.max_hide_checkbox.blockSignals(True)
            if self.max_hide_checkbox.isChecked():
                self.max_hide_checkbox.setChecked(False)
                self.max_hide_checkbox._start_animation(False)
            self.max_hide_checkbox.blockSignals(False)
    # <<< END NEW CODE >>>

    def _on_full_hide_toggled(self, checked):
        """Handle Full Hide Mode toggle"""
        if checked:
            QMessageBox.information(
                self,
                "Restart Required",
                "Please restart Anki for the Full Hide Mode to take effect."
            )

    def _save_hide_modes_settings(self):
        self.current_config.update({
            "hideNativeHeaderAndBottomBar": self.hide_native_header_checkbox.isChecked(),
            # "proHide" removed from UI, but key might remain in config. No need to update it here.
            "maxHide": self.max_hide_checkbox.isChecked(),
            "flowMode": self.flow_mode_checkbox.isChecked(),
            "gamificationMode": self.gamification_mode_checkbox.isChecked(),
            "fullHideMode": self.full_hide_mode_checkbox.isChecked(),
        })

    def _save_overviews_settings(self):
        # --- NEW: Save the selected overview style ---
        if self.overview_mini_radio.isChecked():
            mw.col.conf["onigiri_overview_style"] = "mini"
        else:
            mw.col.conf["onigiri_overview_style"] = "pro"
        # --- END NEW ---
        
        # --- Overviewer Background ---
        if self.overview_bg_main_radio.isChecked():
            self.current_config["onigiri_overview_bg_mode"] = "main"
        elif self.overview_bg_color_radio.isChecked():
            self.current_config["onigiri_overview_bg_mode"] = "color"
        elif self.overview_bg_image_color_radio.isChecked():
            self.current_config["onigiri_overview_bg_mode"] = "image_color"
        
        # Save theme mode for colors and images
        color_theme_mode = "single" if hasattr(self, 'overview_bg_color_theme_mode_single') and self.overview_bg_color_theme_mode_single.isChecked() else "separate"
        image_theme_mode = "single" if hasattr(self, 'overview_bg_image_theme_mode_single') and self.overview_bg_image_theme_mode_single.isChecked() else "separate"
        
        self.current_config["onigiri_overview_bg_color_theme_mode"] = color_theme_mode
        self.current_config["onigiri_overview_bg_image_theme_mode"] = image_theme_mode
        
        # Main background blur and opacity
        self.current_config["onigiri_overview_bg_main_blur"] = self.overview_bg_main_blur_spinbox.value()
        self.current_config["onigiri_overview_bg_main_opacity"] = self.overview_bg_main_opacity_spinbox.value()
        
        # Save colors based on theme mode
        if color_theme_mode == "single" and hasattr(self, 'overview_bg_single_color_row'):
            # In single mode, use the single color for both themes
            single_color = self.overview_bg_single_color_row.itemAt(1).widget().text()
            self.current_config["onigiri_overview_bg_light_color"] = single_color
            self.current_config["onigiri_overview_bg_dark_color"] = single_color
        else:
            # In separate mode, use the individual colors
            if hasattr(self, 'overview_bg_light_color_row'):
                self.current_config["onigiri_overview_bg_light_color"] = self.overview_bg_light_color_row.itemAt(1).widget().text()
            if hasattr(self, 'overview_bg_dark_color_row'):
                self.current_config["onigiri_overview_bg_dark_color"] = self.overview_bg_dark_color_row.itemAt(1).widget().text()
        
        # Save blur and opacity
        self.current_config["onigiri_overview_bg_blur"] = self.overview_bg_blur_spinbox.value()
        self.current_config["onigiri_overview_bg_opacity"] = self.overview_bg_opacity_spinbox.value()
        
        # Save image selections based on theme mode
        if image_theme_mode == "single" and 'overview_bg_single' in self.galleries:
            # In single mode, use the single image for both themes
            single_image = self.galleries['overview_bg_single'].get('selected', '')
            self.current_config["onigiri_overview_bg_image"] = single_image
            self.current_config["onigiri_overview_bg_image_light"] = single_image
            self.current_config["onigiri_overview_bg_image_dark"] = single_image
        else:
            # In separate mode, use the individual images
            if 'overview_bg_light' in self.galleries:
                self.current_config["onigiri_overview_bg_image_light"] = self.galleries['overview_bg_light'].get('selected', '')
            if 'overview_bg_dark' in self.galleries:
                self.current_config["onigiri_overview_bg_image_dark"] = self.galleries['overview_bg_dark'].get('selected', '')

        self.current_config["showCongratsProfileBar"] = self.show_congrats_profile_bar_checkbox.isChecked()
        self.current_config["congratsMessage"] = self.congrats_message_input.text()
        mw.col.conf["modern_menu_studyNowText"] = self.study_now_input.text()
        
        overview_color_keys = [
            "--button-primary-bg", "--button-primary-gradient-start", "--button-primary-gradient-end",
            "--new-count-bubble-bg", "--new-count-bubble-fg", "--learn-count-bubble-bg",
            "--learn-count-bubble-fg", "--review-count-bubble-bg", "--review-count-bubble-fg"
        ]
        for mode in ["light", "dark"]:
            for key in overview_color_keys:
                if key in self.color_widgets[mode]:
                    widget = self.color_widgets[mode][key]
                    self.current_config["colors"][mode][key] = widget.text()

    def _save_sidebar_settings(self):
        self.current_config["hideWelcomeMessage"] = self.hide_welcome_checkbox.isChecked()
        self.current_config["hideDeckCounts"] = self.hide_deck_counts_checkbox.isChecked()
        self.current_config["hideAllDeckCounts"] = self.hide_all_deck_counts_checkbox.isChecked()
        
        # Save Deck Indentation Settings
        if hasattr(self, "indentation_mode_group"):
             if btn := self.indentation_mode_group.checkedButton():
                 self.current_config["deck_indentation_mode"] = btn.property("indent_mode")
             
        if hasattr(self, "indentation_custom_spin"):
             self.current_config["deck_indentation_custom_px"] = self.indentation_custom_spin.value()
        
        # Save Hide Icon Toggles
        if hasattr(self, "hide_folder_cb"):
            mw.col.conf["modern_menu_hide_folder_icon"] = self.hide_folder_cb.isChecked()
        if hasattr(self, "hide_subdeck_cb"):
            mw.col.conf["modern_menu_hide_subdeck_icon"] = self.hide_subdeck_cb.isChecked()
        if hasattr(self, "hide_deck_cb"):
            mw.col.conf["modern_menu_hide_deck_icon"] = self.hide_deck_cb.isChecked()
        if hasattr(self, "hide_default_custom_cb"):
            mw.col.conf["modern_menu_hide_default_icons"] = self.hide_default_custom_cb.isChecked()
        
        for widget in self.action_button_icon_widgets:
            key = widget.property("icon_key")
            value = widget.property("icon_filename")
            config_key = f"modern_menu_icon_{key}"
            if value:
                mw.col.conf[config_key] = value
            else:
                mw.col.conf[config_key] = ""

        for widget in self.icon_assignment_widgets:
            key = widget.property("icon_key")
            value = widget.property("icon_filename")
            config_key = f"modern_menu_icon_{key}"
            if value:
                mw.col.conf[config_key] = value
            else:
                mw.col.conf[config_key] = ""

        for key,widget in self.icon_size_widgets.items():
            mw.col.conf[f"modern_menu_icon_size_{key}"] = widget.value()
        
        sidebar_color_keys = [
            "--icon-color", "--icon-color-filtered", "--deck-list-bg",
            "--highlight-bg", "--highlight-fg"
        ]
        for mode in ["light", "dark"]:
            for key in sidebar_color_keys:
                if key in self.color_widgets[mode]:
                    widget = self.color_widgets[mode][key]
                    self.current_config["colors"][mode][key] = widget.text()

        # --- Sidebar Background Settings ---
        if self.sidebar_bg_custom_radio.isChecked(): mw.col.conf["modern_menu_sidebar_bg_mode"] = "custom"
        else: mw.col.conf["modern_menu_sidebar_bg_mode"] = "main"
        
        if self.sidebar_effect_glass_radio.isChecked():
            mw.col.conf["onigiri_sidebar_main_bg_effect_mode"] = "glassmorphism"
        else:
            mw.col.conf["onigiri_sidebar_main_bg_effect_mode"] = "opaque"
        
        mw.col.conf["onigiri_sidebar_main_bg_effect_intensity"] = self.sidebar_effect_intensity_spinbox.value()
        mw.col.conf["onigiri_sidebar_opaque_tint_intensity"] = self.sidebar_overlay_intensity_spinbox.value()
        mw.col.conf["onigiri_sidebar_opaque_tint_color_light"] = self.overlay_light_color_color_input.text()
        mw.col.conf["onigiri_sidebar_opaque_tint_color_dark"] = self.overlay_dark_color_color_input.text()

        if self.sidebar_bg_type_accent_radio.isChecked():
            mw.col.conf["modern_menu_sidebar_bg_type"] = "accent"
        elif self.sidebar_bg_type_image_color_radio.isChecked():
            mw.col.conf["modern_menu_sidebar_bg_type"] = "image_color"
        else:
            mw.col.conf["modern_menu_sidebar_bg_type"] = "color"
        
        mw.col.conf["modern_menu_sidebar_bg_color_light"] = self.sidebar_bg_light_color_input.text()
        mw.col.conf["modern_menu_sidebar_bg_color_dark"] = self.sidebar_bg_dark_color_input.text()
        mw.col.conf["modern_menu_sidebar_bg_blur"] = self.sidebar_bg_blur_spinbox.value()

        # Opacity and Transparency
        mw.col.conf["modern_menu_sidebar_bg_opacity"] = self.sidebar_bg_opacity_spinbox.value()
        mw.col.conf["modern_menu_sidebar_bg_transparency"] = self.sidebar_bg_transparency_spinbox.value()
        
        # Save sidebar background image if it exists
        if 'sidebar_bg' in self.galleries:
            mw.col.conf["modern_menu_sidebar_bg_image"] = self.galleries['sidebar_bg'].get('selected', '')

    def _save_main_menu_settings(self):
        mw.col.conf["modern_menu_statsTitle"] = self.stats_title_input.text()
        
        # Save Heatmap Default View
        if hasattr(self, "heatmap_view_group"):
            checked_btn = self.heatmap_view_group.checkedButton()
            if checked_btn:
                self.current_config["heatmapDefaultView"] = checked_btn.property("view_mode")
        
        if hasattr(self, "selected_heatmap_shape"):
            self.current_config["heatmapShape"] = self.selected_heatmap_shape
        
        self.current_config["heatmapShowStreak"] = self.heatmap_show_streak_check.isChecked()
        self.current_config["heatmapShowMonths"] = self.heatmap_show_months_check.isChecked()
        self.current_config["heatmapShowWeekdays"] = self.heatmap_show_weekdays_check.isChecked()
        self.current_config["heatmapShowWeekHeader"] = self.heatmap_show_week_header_check.isChecked()
        
        if hasattr(self, "hide_retention_stars_check"):
            self.current_config["hideRetentionStars"] = self.hide_retention_stars_check.isChecked()

        if hasattr(self, "retention_star_widget") and self.retention_star_widget:
            key = "retention_star"
            value = self.retention_star_widget.property("icon_filename")
            config_key = f"modern_menu_icon_{key}"
            if value:
                mw.col.conf[config_key] = value
            else:
                mw.col.conf[config_key] = ""

        stats_color_keys = ["--star-color", "--empty-star-color", "--heatmap-color", "--heatmap-color-zero"]
        for mode in ["light", "dark"]:
            for key in stats_color_keys:
                if key in self.color_widgets[mode]:
                    widget = self.color_widgets[mode][key]
                    self.current_config["colors"][mode][key] = widget.text()

        # --- Main Background Settings ---
        
        # Save the background mode (color/image_color/accent/slideshow)
        # Save the background mode (color/image_color/accent/slideshow)
        if self.image_color_radio.isChecked():
            mw.col.conf["modern_menu_background_mode"] = "image_color"
        elif self.slideshow_radio.isChecked():
            mw.col.conf["modern_menu_background_mode"] = "slideshow"
        else:
            # Solid Color is checked
            if self.color_theme_accent_radio.isChecked():
                mw.col.conf["modern_menu_background_mode"] = "accent"
            else:
                mw.col.conf["modern_menu_background_mode"] = "color"
        
        # Save slideshow settings
        if self.slideshow_radio.isChecked():
            # Save interval
            mw.col.conf["modern_menu_slideshow_interval"] = self.slideshow_interval_spinbox.value()
            
            # Save selected images
            selected_images = [item.img_filename for item in self.slideshow_image_items if item.is_checked]
            mw.col.conf["modern_menu_slideshow_images"] = selected_images
        
        # Save Color Theme Mode
        color_theme_mode = "single" if self.color_theme_single_radio.isChecked() else "separate"
        mw.col.conf["modern_menu_bg_color_theme_mode"] = color_theme_mode

        # Save Colors
        if color_theme_mode == "single":
            # In single mode, use the single color for both themes
            single_color = self.bg_single_row.itemAt(1).widget().text()
            mw.col.conf["modern_menu_bg_color_light"] = single_color
            mw.col.conf["modern_menu_bg_color_dark"] = single_color
            # Also update the config for immediate use
            self.current_config["colors"]["light"]["--bg"] = single_color
            self.current_config["colors"]["dark"]["--bg"] = single_color
        else:
            # In separate mode, use the individual colors
            light_bg_val = self.bg_light_row.itemAt(1).widget().text()
            dark_bg_val = self.bg_dark_row.itemAt(1).widget().text()
            mw.col.conf["modern_menu_bg_color_light"] = light_bg_val
            mw.col.conf["modern_menu_bg_color_dark"] = dark_bg_val
            # Also update the config for immediate use
            self.current_config["colors"]["light"]["--bg"] = light_bg_val
            self.current_config["colors"]["dark"]["--bg"] = dark_bg_val
        
        # Save Image Theme Mode
        image_theme_mode = "single" if self.image_theme_single_radio.isChecked() else "separate"
        mw.col.conf["modern_menu_bg_image_theme_mode"] = image_theme_mode

        # Save Images
        if image_theme_mode == "single" and 'main_single' in self.galleries:
            # In single mode, use the single image for both themes
            single_image = self.galleries['main_single'].get('selected', '')
            mw.col.conf["modern_menu_background_image"] = single_image
            mw.col.conf["modern_menu_background_image_light"] = single_image
            mw.col.conf["modern_menu_background_image_dark"] = single_image
        else:
            # In separate mode, use the individual images
            if 'main_light' in self.galleries:
                mw.col.conf["modern_menu_background_image_light"] = self.galleries['main_light'].get('selected', '')
            if 'main_dark' in self.galleries:
                mw.col.conf["modern_menu_background_image_dark"] = self.galleries['main_dark'].get('selected', '')
        
        mw.col.conf["modern_menu_background_blur"] = self.bg_blur_spinbox.value()
        mw.col.conf["modern_menu_background_opacity"] = self.bg_opacity_spinbox.value()

    def _save_organize_settings(self):
        """Saves the layout from the unified layout editor."""
        if hasattr(self, 'unified_layout_editor'):
            layout_config = self.unified_layout_editor.get_layout_config()
            self.current_config['onigiriWidgetLayout'] = layout_config['onigiri']
            self.current_config['externalWidgetLayout'] = layout_config['external']
            # Save the row count setting
            self.current_config['unifiedGridRows'] = self.unified_layout_editor.row_spin.value()

    def _save_profile_settings(self):
        self.current_config["userName"] = self.name_input.text()
        mw.col.conf["modern_menu_userName"] = self.name_input.text()
        
        # Save birthday in ISO format (YYYY-MM-DD)
        if hasattr(self, 'birthday_input'):
            birthday_date = self.birthday_input.date()
            if birthday_date.isValid():
                 self.current_config["userBirthday"] = birthday_date.toString("yyyy-MM-dd")
            else:
                 self.current_config["userBirthday"] = ""

        if 'profile_pic' in self.galleries:
            mw.col.conf["modern_menu_profile_picture"] = self.galleries['profile_pic']['selected']
        if 'profile_bg' in self.galleries:
            mw.col.conf["modern_menu_profile_bg_image"] = self.galleries['profile_bg']['selected']

        if self.profile_bg_image_radio.isChecked(): mw.col.conf["modern_menu_profile_bg_mode"] = "image"
        elif self.profile_bg_custom_radio.isChecked(): mw.col.conf["modern_menu_profile_bg_mode"] = "custom"
        else: mw.col.conf["modern_menu_profile_bg_mode"] = "accent"
        
        mw.col.conf["modern_menu_profile_bg_color_light"] = self.profile_bg_light_color_input.text()
        mw.col.conf["modern_menu_profile_bg_color_dark"] = self.profile_bg_dark_color_input.text()
        mw.col.conf["onigiri_profile_show_theme_light"] = self.profile_show_theme_light_check.isChecked()
        mw.col.conf["onigiri_profile_show_theme_dark"] = self.profile_show_theme_dark_check.isChecked()
        mw.col.conf["onigiri_profile_show_backgrounds"] = self.profile_show_backgrounds_check.isChecked()
        mw.col.conf["onigiri_profile_show_stats"] = self.profile_show_stats_check.isChecked()
        if self.profile_page_bg_gradient_radio.isChecked():
            mw.col.conf["onigiri_profile_page_bg_mode"] = "gradient"
            mw.col.conf["onigiri_profile_page_bg_light_color1"] = self.profile_page_light_gradient1_color_input.text()
            mw.col.conf["onigiri_profile_page_bg_light_color2"] = self.profile_page_light_gradient2_color_input.text()
            mw.col.conf["onigiri_profile_page_bg_dark_color1"] = self.profile_page_dark_gradient1_color_input.text()
            mw.col.conf["onigiri_profile_page_bg_dark_color2"] = self.profile_page_dark_gradient2_color_input.text()
            mw.col.conf["onigiri_profile_page_bg_mode"] = "color"
            mw.col.conf["onigiri_profile_page_bg_light_color1"] = self.profile_page_light_color1_color_input.text()
            mw.col.conf["onigiri_profile_page_bg_dark_color1"] = self.profile_page_dark_color1_color_input.text()
            
        # Save Restaurant Level visibility
        restaurant_level.manager.set_profile_page_visibility(self.profile_show_restaurant_check.isChecked())

    def _save_achievements_settings(self):
        # Save restaurant_level to top-level config
        restaurant_conf = self.current_config.setdefault("restaurant_level", {})
        # Also ensure it's removed from achievements if present (cleanup)
        if "restaurant_level" in self.achievements_config:
            # We might want to preserve it there for a moment or just rely on the top level
            # But let's just make sure we are editing the top level one
            pass

        restaurant_enabled = self.restaurant_level_toggle.isChecked()
        restaurant_conf["enabled"] = restaurant_enabled
        restaurant_conf["notifications_enabled"] = self.restaurant_notifications_toggle.isChecked()
        restaurant_conf["show_profile_bar_progress"] = self.restaurant_bar_toggle.isChecked()
        # show_profile_page_progress is now saved in _save_profile_settings
        restaurant_conf["show_reviewer_header"] = self.restaurant_reviewer_toggle.isChecked()
        
        # Save Focus Dango setting
        focus_dango_conf = self.achievements_config.setdefault("focusDango", {})
        focus_dango_conf["enabled"] = self.focus_dango_toggle.isChecked()

        from .gamification import focus_dango
        focus_dango.set_focus_dango_enabled(self.focus_dango_toggle.isChecked())
        

        
        # Save restaurant name if input exists
        if hasattr(self, 'restaurant_name_input'):
            new_name = self.restaurant_name_input.text().strip()
            if new_name:
                restaurant_level.manager.set_restaurant_name(new_name)
            else:
                restaurant_level.manager.set_restaurant_name("Restaurant Level")

        restaurant_level.manager.set_enabled(restaurant_enabled)
        restaurant_level.manager.set_notifications_enabled(restaurant_conf["notifications_enabled"])
        restaurant_level.manager.set_profile_bar_visibility(restaurant_conf["show_profile_bar_progress"])
        restaurant_level.manager.set_profile_page_visibility(restaurant_conf["show_profile_page_progress"])

        defaults = config.DEFAULTS["achievements"].get("custom_goals", {})
        custom_goals = self.achievements_config.setdefault(
            "custom_goals",
            copy.deepcopy(defaults),
        )
        custom_goals.setdefault("last_modified_at", defaults.get("last_modified_at"))

        previous_goals = copy.deepcopy(custom_goals)
        daily_prev = previous_goals.get("daily", {})
        weekly_prev = previous_goals.get("weekly", {})

        daily_enabled = self.daily_goal_toggle.isChecked()
        daily_target = self.daily_goal_spinbox.value()
        weekly_enabled = self.weekly_goal_toggle.isChecked()
        weekly_target = self.weekly_goal_spinbox.value()

        daily_changed = (
            bool(daily_prev.get("enabled", False)) != daily_enabled
            or int(daily_prev.get("target", 0)) != daily_target
        )
        weekly_changed = (
            bool(weekly_prev.get("enabled", False)) != weekly_enabled
            or int(weekly_prev.get("target", 0)) != weekly_target
        )
        changes_requested = daily_changed or weekly_changed

        if changes_requested:
            last_modified_at = previous_goals.get("last_modified_at")
            unlock_at = last_modified_at + CUSTOM_GOAL_COOLDOWN_SECONDS if last_modified_at else None
            remaining = (unlock_at - int(time.time())) if unlock_at else 0
            if remaining > 0:
                self._restore_custom_goal_inputs(previous_goals)
                self.achievements_config["custom_goals"] = previous_goals
                self._show_custom_goal_lock_warning(remaining, unlock_at)
                self._refresh_custom_goal_cooldown_label()
                return

        daily_conf = custom_goals.setdefault("daily", copy.deepcopy(defaults.get("daily", {})))
        daily_conf["enabled"] = daily_enabled
        daily_conf["target"] = daily_target
        daily_conf.setdefault("last_notified_day", daily_prev.get("last_notified_day"))
        daily_conf.setdefault("completion_count", daily_prev.get("completion_count", 0))

        weekly_conf = custom_goals.setdefault("weekly", copy.deepcopy(defaults.get("weekly", {})))
        weekly_conf["enabled"] = weekly_enabled
        weekly_conf["target"] = weekly_target
        weekly_conf.setdefault("last_notified_week", weekly_prev.get("last_notified_week"))
        weekly_conf.setdefault("completion_count", weekly_prev.get("completion_count", 0))

        if changes_requested:
            custom_goals["last_modified_at"] = int(time.time())
        else:
            custom_goals["last_modified_at"] = previous_goals.get("last_modified_at")

        self._refresh_custom_goal_cooldown_label()

    def _save_mochi_messages_settings(self) -> None:
        mochi_defaults = config.DEFAULTS.get("mochi_messages", {})
        mochi_conf = self.current_config.setdefault("mochi_messages", copy.deepcopy(mochi_defaults))

        mochi_conf["enabled"] = self.mochi_messages_toggle.isChecked()
        mochi_conf["cards_interval"] = max(1, int(self.mochi_interval_spinbox.value()))

        raw_text = self.mochi_messages_editor.toPlainText()
        messages = [line.strip() for line in raw_text.splitlines() if line.strip()]
        if not messages:
            messages = copy.deepcopy(mochi_defaults.get("messages", []))
        mochi_conf["messages"] = messages

    def _save_focus_dango_settings(self) -> None:
        if not hasattr(self, 'focus_dango_message_editor'):
            # Page was never loaded, so don't save
            return

        focus_dango_defaults = config.DEFAULTS.get("achievements", {}).get("focusDango", {})
        focus_dango_conf = self.achievements_config.setdefault("focusDango", copy.deepcopy(focus_dango_defaults))

        # --- START MODIFICATION ---
        raw_text = self.focus_dango_message_editor.toPlainText()
        messages = [line.strip() for line in raw_text.splitlines() if line.strip()]
        
        if not messages:
            # Fallback to new default "messages" list
            messages = copy.deepcopy(focus_dango_defaults.get("messages", []))
            # If that's empty, try old default "message" string
            if not messages:
                old_default_message = focus_dango_defaults.get("message")
                if isinstance(old_default_message, str) and old_default_message:
                    messages = [old_default_message]
            # If still empty, use hardcoded default
            if not messages:
                messages = ["Don't give up!", "Stay focused!", "Almost there!"]

        focus_dango_conf["messages"] = messages
        
        # Clean up old "message" key if it exists
        if "message" in focus_dango_conf:
            del focus_dango_conf["message"]
        # --- END MODIFICATION ---

    def _custom_goal_cooldown_state(self):
        custom_goals = self.achievements_config.get("custom_goals", {})
        last_modified = custom_goals.get("last_modified_at")
        if not last_modified:
            return 0, None
        unlock_at = last_modified + CUSTOM_GOAL_COOLDOWN_SECONDS
        remaining = max(0, unlock_at - int(time.time()))
        return remaining, unlock_at

    def _format_duration(self, seconds):
        total_seconds = max(0, int(seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if not parts:
            parts.append("less than a minute")
        return " ".join(parts)

    def _refresh_custom_goal_cooldown_label(self):
        label = getattr(self, "custom_goal_cooldown_label", None)
        if not label:
            return
        remaining, unlock_at = self._custom_goal_cooldown_state()
        if remaining <= 0 or not unlock_at:
            message = "You can update your Custom Goals right now."
        else:
            duration = self._format_duration(remaining)
            available_time = datetime.fromtimestamp(unlock_at).strftime("%b %d, %Y %I:%M %p")
            message = f"You can update your Custom Goals again in {duration} (after {available_time})."
        label.setText(message)

    def _restore_custom_goal_inputs(self, goals_conf):
        daily_conf = goals_conf.get("daily", {})
        weekly_conf = goals_conf.get("weekly", {})

        self.daily_goal_toggle.setChecked(bool(daily_conf.get("enabled", False)))
        self.daily_goal_spinbox.setValue(int(daily_conf.get("target", 0)))

        self.weekly_goal_toggle.setChecked(bool(weekly_conf.get("enabled", False)))
        self.weekly_goal_spinbox.setValue(int(weekly_conf.get("target", 0)))

    def _show_custom_goal_lock_warning(self, remaining_seconds, unlock_at):
        duration = self._format_duration(remaining_seconds)
        if unlock_at:
            available_time = datetime.fromtimestamp(unlock_at).strftime("%b %d, %Y %I:%M %p")
            message = (
                "Custom Goals can be updated once every 24 hours.\n"
                f"You can make adjustments again in {duration} (after {available_time})."
            )
        else:
            message = (
                "Custom Goals can be updated once every 24 hours.\n"
                "Please try again soon."
            )
        showInfo(message)

    def _save_colors_settings(self):
        # Save the accent colors, which are handled by dedicated widgets.
        self.current_config["colors"]["light"]["--accent-color"] = self.light_accent_color_input.text()
        self.current_config["colors"]["dark"]["--accent-color"] = self.dark_accent_color_input.text()

        # Explicitly define which color keys belong to the Palette page's "General Palette".
        palette_keys = {
            "--fg",
            "--fg-subtle",
            "--border",
            "--canvas-inset"
        }
        
        for mode in ["light", "dark"]:
            # Iterate only over the keys this page is responsible for.
            for key in palette_keys:
                # Check that the widget for this key has been loaded before trying to save it.
                if key in self.color_widgets[mode]:
                    widget = self.color_widgets[mode][key]
                    self.current_config["colors"][mode][key] = widget.text()

        # --- START: Save Boxes Color Effect Settings ---
        effect_mode = "none"
        if self.canvas_effect_opacity_radio.isChecked():
            effect_mode = "opacity"
        elif self.canvas_effect_glass_radio.isChecked():
            effect_mode = "glassmorphism"
        
        mw.col.conf["onigiri_canvas_inset_effect_mode"] = effect_mode
        mw.col.conf["onigiri_canvas_inset_effect_intensity"] = self.canvas_effect_intensity_spinbox.value()
        # --- END: Save Boxes Color Effect Settings ---



    def _save_reviewer_settings(self):
        # Save Answer Buttons Settings
        self.current_config["onigiri_reviewer_btn_custom_enabled"] = self.reviewer_btn_custom_enable_toggle.isChecked()
        self.current_config["onigiri_reviewer_btn_radius"] = self.reviewer_btn_radius_spin.value()
        self.current_config["onigiri_reviewer_btn_padding"] = self.reviewer_btn_padding_spin.value()
        self.current_config["onigiri_reviewer_btn_height"] = self.reviewer_btn_height_spin.value()
        self.current_config["onigiri_reviewer_bar_height"] = self.reviewer_bar_height_spin.value()
        self.current_config["onigiri_reviewer_stattxt_color_light"] = getattr(self, "stattxt_color_light_color_input").text()
        self.current_config["onigiri_reviewer_stattxt_color_dark"] = getattr(self, "stattxt_color_dark_color_input").text()
        
        # Save Other Buttons
        self.current_config["onigiri_reviewer_other_btn_bg_light"] = getattr(self, "other_btn_bg_light_color_input").text()
        self.current_config["onigiri_reviewer_other_btn_text_light"] = getattr(self, "other_btn_text_light_color_input").text()
        self.current_config["onigiri_reviewer_other_btn_bg_dark"] = getattr(self, "other_btn_bg_dark_color_input").text()
        self.current_config["onigiri_reviewer_other_btn_text_dark"] = getattr(self, "other_btn_text_dark_color_input").text()
        self.current_config["onigiri_reviewer_other_btn_hover_bg_light"] = getattr(self, "other_btn_hover_bg_light_color_input").text()
        self.current_config["onigiri_reviewer_other_btn_hover_text_light"] = getattr(self, "other_btn_hover_text_light_color_input").text()
        self.current_config["onigiri_reviewer_other_btn_hover_bg_dark"] = getattr(self, "other_btn_hover_bg_dark_color_input").text()
        self.current_config["onigiri_reviewer_other_btn_hover_text_dark"] = getattr(self, "other_btn_hover_text_dark_color_input").text()
        
        for key in ["again", "hard", "good", "easy"]:
            self.current_config[f"onigiri_reviewer_btn_{key}_bg_light"] = getattr(self, f"btn_{key}_bg_light_color_input").text()
            self.current_config[f"onigiri_reviewer_btn_{key}_bg_dark"] = getattr(self, f"btn_{key}_bg_dark_color_input").text()
            self.current_config[f"onigiri_reviewer_btn_{key}_text_light"] = getattr(self, f"btn_{key}_text_light_color_input").text()
            self.current_config[f"onigiri_reviewer_btn_{key}_text_dark"] = getattr(self, f"btn_{key}_text_dark_color_input").text()

        # --- Reviewer Background ---
        if self.reviewer_bg_main_radio.isChecked():
            self.current_config["onigiri_reviewer_bg_mode"] = "main"
        elif self.reviewer_bg_color_radio.isChecked():
            self.current_config["onigiri_reviewer_bg_mode"] = "color"
        elif self.reviewer_bg_image_color_radio.isChecked():
            self.current_config["onigiri_reviewer_bg_mode"] = "image_color"
        
        # Save theme mode for colors and images
        color_theme_mode = "single" if hasattr(self, 'reviewer_bg_color_theme_mode_single') and self.reviewer_bg_color_theme_mode_single.isChecked() else "separate"
        image_theme_mode = "single" if hasattr(self, 'reviewer_bg_image_theme_mode_single') and self.reviewer_bg_image_theme_mode_single.isChecked() else "separate"
        
        mw.col.conf["onigiri_reviewer_bg_color_theme_mode"] = color_theme_mode
        mw.col.conf["onigiri_reviewer_bg_image_theme_mode"] = image_theme_mode
        
        # Also save to addon config so patcher.py can read it
        self.current_config["onigiri_reviewer_bg_image_mode"] = image_theme_mode
        
        # Main background blur and opacity
        self.current_config["onigiri_reviewer_bg_main_blur"] = self.reviewer_bg_main_blur_spinbox.value()
        self.current_config["onigiri_reviewer_bg_main_opacity"] = self.reviewer_bg_main_opacity_spinbox.value()
        
        # Save colors based on theme mode
        if color_theme_mode == "single" and hasattr(self, 'reviewer_bg_single_color_row'):
            # In single mode, use the single color for both themes
            single_color = self.reviewer_bg_single_color_row.itemAt(1).widget().text()
            self.current_config["onigiri_reviewer_bg_light_color"] = single_color
            self.current_config["onigiri_reviewer_bg_dark_color"] = single_color
        else:
            # In separate mode, use the individual colors
            if hasattr(self, 'reviewer_bg_light_color_row'):
                self.current_config["onigiri_reviewer_bg_light_color"] = self.reviewer_bg_light_color_row.itemAt(1).widget().text()
            if hasattr(self, 'reviewer_bg_dark_color_row'):
                self.current_config["onigiri_reviewer_bg_dark_color"] = self.reviewer_bg_dark_color_row.itemAt(1).widget().text()
        
        # Save blur and opacity
        self.current_config["onigiri_reviewer_bg_blur"] = self.reviewer_bg_blur_spinbox.value()
        self.current_config["onigiri_reviewer_bg_opacity"] = self.reviewer_bg_opacity_spinbox.value()
        
        # Save image selections based on theme mode
        if image_theme_mode == "single" and 'reviewer_bg_single' in self.galleries:
            # In single mode, use the single image for both themes
            single_image = self.galleries['reviewer_bg_single'].get('selected', '')
            self.current_config["onigiri_reviewer_bg_image"] = single_image
            self.current_config["onigiri_reviewer_bg_image_light"] = single_image
            self.current_config["onigiri_reviewer_bg_image_dark"] = single_image
        else:
            # In separate mode, use the individual images
            if 'reviewer_bg_light' in self.galleries:
                self.current_config["onigiri_reviewer_bg_image_light"] = self.galleries['reviewer_bg_light'].get('selected', '')
            if 'reviewer_bg_dark' in self.galleries:
                self.current_config["onigiri_reviewer_bg_image_dark"] = self.galleries['reviewer_bg_dark'].get('selected', '')
        
        # --- Bottom Bar ---
        self.current_config["onigiri_reviewer_bottom_bar_bg_mode"] = self.reviewer_bottom_bar_mode
        self.current_config["onigiri_reviewer_bottom_bar_match_main_blur"] = self.reviewer_bar_match_main_blur_spinbox.value()
        self.current_config["onigiri_reviewer_bottom_bar_match_main_opacity"] = self.reviewer_bar_match_main_opacity_spinbox.value()
        self.current_config["onigiri_reviewer_bottom_bar_match_reviewer_bg_blur"] = self.reviewer_bar_match_reviewer_bg_blur_spinbox.value()
        self.current_config["onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity"] = self.reviewer_bar_match_reviewer_bg_opacity_spinbox.value()
        self.current_config["onigiri_reviewer_bottom_bar_bg_light_color"] = self.reviewer_bar_light_color_input.text()
        self.current_config["onigiri_reviewer_bottom_bar_bg_dark_color"] = self.reviewer_bar_dark_color_input.text()
        self.current_config["onigiri_reviewer_bottom_bar_bg_blur"] = self.reviewer_bar_blur_spinbox.value()
        self.current_config["onigiri_reviewer_bottom_bar_bg_opacity"] = self.reviewer_bar_opacity_spinbox.value()
        if 'reviewer_bar_bg' in self.galleries:
            self.current_config["onigiri_reviewer_bottom_bar_bg_image"] = self.galleries['reviewer_bar_bg']['selected']

    def _save_sidebar_layout_settings(self):
        """Saves the sidebar button layout from the editor."""
        if hasattr(self, 'sidebar_layout_editor'):
            self.current_config["sidebarButtonLayout"] = self.sidebar_layout_editor.get_layout_config()

    def _on_indentation_mode_btn_clicked(self, button):
        if not button: return
        mode = button.property("indent_mode")
        is_custom = (mode == "custom")
        if hasattr(self, 'indentation_custom_row_widget'):
            self.indentation_custom_row_widget.setVisible(is_custom)

    def _update_deck_icon_state(self):
        # Disable the deck_folder size spinbox if either hide toggle is ON
        if "deck_folder" in self.icon_size_widgets:
            should_disable = (self.hide_folder_cb.isChecked() or 
                            self.hide_subdeck_cb.isChecked() or 
                            self.hide_deck_cb.isChecked())
            self.icon_size_widgets["deck_folder"].setEnabled(not should_disable)

    def _show_deck_icon_info(self):
        """Display explanation of deck icon types."""
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Deck Icon Types")
        dialog.setTextFormat(Qt.TextFormat.RichText)
        dialog.setText("""
            <h3>Understanding Deck Icon Types</h3>
            <p><b>Folder:</b> A deck that contains subdecks inside it. Uses the folder icon.</p>
            <p><b>Deck:</b> A top-level deck that doesn't contain any subdecks. Uses the deck icon.</p>
            <p><b>Subdeck:</b> A deck that is nested inside a folder. Uses the subdeck icon.</p>
            <p><b>Filtered Deck:</b> A special deck type with dynamic cards based on search criteria. Uses the filtered deck icon.</p>
        """)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()

    def save_settings(self):
        page_indices = {name: i for i, name in enumerate(self.page_order)}

        self._save_achievements_settings()
        self._save_mochi_messages_settings()
        self._save_focus_dango_settings()

        # Always save hide mode settings
        self._save_hide_modes_settings()
        
        if self.tabs_loaded.get(page_indices.get("Main menu")):
            self._save_main_menu_settings()
            self._save_organize_settings()
        if self.tabs_loaded.get(page_indices.get("Sidebar")):
            self._save_sidebar_settings()
            self._save_sidebar_layout_settings()
        if self.tabs_loaded.get(page_indices.get("Overviewer")):
            self._save_overviews_settings()
        if self.tabs_loaded.get(page_indices.get("Fonts")): # <<< ADD THIS IF BLOCK
            self._save_fonts_settings()
        if self.tabs_loaded.get(page_indices.get("Profile")):
            self._save_profile_settings()
        if self.tabs_loaded.get(page_indices.get("Palette")):
            self._save_colors_settings()
        if self.tabs_loaded.get(page_indices.get("Reviewer")):
            self._save_reviewer_settings()

        # <<< THIS IS THE FIX: Manually save the theme's background color if the Main menu tab was never opened. >>>
        if not self.tabs_loaded.get(page_indices.get("Main menu")):
            light_bg_from_theme = self.current_config['colors']['light'].get('--bg')
            dark_bg_from_theme = self.current_config['colors']['dark'].get('--bg')
            
            if light_bg_from_theme:
                mw.col.conf["modern_menu_bg_color_light"] = light_bg_from_theme
            if dark_bg_from_theme:
                mw.col.conf["modern_menu_bg_color_dark"] = dark_bg_from_theme

        config.write_config(self.current_config)
        self.accept()

_settings_dialog = None

def open_settings(initial_page_index=0):
    """Opens the Onigiri settings dialog."""
    global _settings_dialog
    if _settings_dialog is not None:
        _settings_dialog.close()
    
    addon_path = os.path.dirname(__file__)
    
    _settings_dialog = SettingsDialog(
        parent=mw, 
        addon_path=addon_path, 
        initial_page_index=initial_page_index
    )
    _settings_dialog.show()
