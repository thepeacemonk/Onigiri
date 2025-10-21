import os
import shutil
import urllib.parse
import json
import functools
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QDialogButtonBox, QWidget, QTabWidget, QColorDialog, QColor, QCheckBox,
    QGroupBox, QRadioButton, QFileDialog, QSpinBox, QFormLayout, QScrollArea,
    QGridLayout, QPixmap, Qt, QEvent, QPainter, QPainterPath, QMessageBox,
    QListWidget, QStackedWidget, QListWidgetItem, QFrame, QSizePolicy,
    QIcon, QPen, QBrush, QInputDialog, QAbstractButton, QDoubleSpinBox,
    QButtonGroup, QAbstractSpinBox,
    QDrag, QMimeData, QPoint, 
    QMenu, QAction, QActionGroup
)
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtProperty, QPointF
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl, QPropertyAnimation, QEasingCurve

from aqt import mw
from aqt import mw, gui_hooks   
from aqt.theme import theme_manager
from typing import Union
from . import config
from .config import DEFAULTS
from .constants import COLOR_LABELS, ICON_DEFAULTS, DEFAULT_ICON_SIZES, ALL_THEME_KEYS
from .themes import THEMES 
from aqt.qt import QRectF
from PyQt6.QtGui import QImage
from aqt.utils import showInfo
from PyQt6.QtGui import QFontDatabase, QFont
from .fonts import FONTS, get_all_fonts

THUMBNAIL_STYLE = "QLabel { border: 2px solid transparent; border-radius: 10px; } QLabel:hover { border: 2px solid #007bff; }"
THUMBNAIL_STYLE_SELECTED = "QLabel { border: 2px solid #007bff; border-radius: 10px; }"

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
            if not source_image.isNull():
                circular_pixmap = create_circular_pixmap(source_image, 40)
                self.pic_label.setPixmap(circular_pixmap)
        else:
            self.pic_label.setStyleSheet("background-color: #888; border-radius: 20px;")

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

            if self._bg_mode == 'image' and self._bg_image_path and os.path.exists(self._bg_image_path):
                image = QImage(self._bg_image_path)
                
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
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
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

        preview_colors = theme_data['light']
        for key in ["--accent-color", "--fg", "--fg-subtle", "--border", "--canvas-inset", "--bg"]:
            if key in preview_colors:
                swatch_layout.addWidget(ColorSwatch(preview_colors[key]))
        swatch_layout.addStretch()

        main_layout.addLayout(top_layout)
        main_layout.addLayout(swatch_layout)

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
                font_path = os.path.join(addon_path, "user_files", "fonts", "system_fonts", font_info["file"])

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
            if delete_icon:
                self.delete_button.setIcon(delete_icon)
                self.delete_button.setIconSize(self.delete_button.size() * 0.7)
            else:
                self.delete_button.setText("âœ•")
            self.delete_button.setFixedSize(22, 22)
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

class SettingsDialog(QDialog):
    def __init__(self, parent=None, addon_path=None, initial_page_index=0):
        super().__init__(parent)
        self.addon_path = addon_path
        # <<< IMPORT/EXPORT THEMES >>>
        self.user_themes_path = os.path.join(self.addon_path, "user_files", "user_themes")
        os.makedirs(self.user_themes_path, exist_ok=True)
        self.block_card_click = False
        self.setWindowTitle("Onigiri Settings")
        self.setMinimumWidth(900)
        self.setMinimumHeight(700)
        
        self.current_config = config.get_config()
        light_bg = mw.col.conf.get("modern_menu_bg_color_light")
        dark_bg = mw.col.conf.get("modern_menu_bg_color_dark")

        # --- ADD THIS LINE ---
        self.reviewer_bottom_bar_mode = mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_mode", "main")
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

        # Initialize widgets that have been moved so they are always available for saving
        self.hide_native_header_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_native_header_checkbox.setChecked(self.current_config.get("hideNativeHeaderAndBottomBar", True))
        
        self.pro_hide_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.pro_hide_checkbox.setChecked(self.current_config.get("proHide", False))
        self.pro_hide_checkbox.setToolTip("Hides the modern toolbar on overview and the native toolbar on reviewer.")
        
        self.max_hide_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.max_hide_checkbox.setChecked(self.current_config.get("maxHide", False))
        self.max_hide_checkbox.setToolTip("Hides the bottom toolbar on the reviewer screen for the most immersive experience.")

        self.hide_native_header_checkbox.toggled.connect(self._on_hide_toggled)
        self.pro_hide_checkbox.toggled.connect(self._on_pro_hide_toggled)
        self.max_hide_checkbox.toggled.connect(self._on_max_hide_toggled)

        self.stats_title_input = QLineEdit(mw.col.conf.get("modern_menu_statsTitle", DEFAULTS["statsTitle"]))

        self.hide_welcome_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_welcome_checkbox.setChecked(self.current_config.get("hideWelcomeMessage", False))

        self.hide_profile_bar_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_profile_bar_checkbox.setChecked(self.current_config.get("hideProfileBar", False))

        self.hide_deck_counts_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_deck_counts_checkbox.setChecked(self.current_config.get("hideDeckCounts", False))

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
        sidebar_wrapper.setFixedWidth(200) # Prevents the wrapper from expanding
        sidebar_wrapper_layout = QVBoxLayout(sidebar_wrapper)
        sidebar_wrapper_layout.setContentsMargins(15, 15, 0, 15) # Sets top/bottom margin

        # This is the actual visible sidebar widget, which will be styled
        sidebar_widget = QWidget()
        sidebar_widget.setObjectName("sidebarContainer") # Name for the stylesheet

        # Add the styled widget inside the wrapper
        sidebar_wrapper_layout.addWidget(sidebar_widget)

        # The sidebar's internal content (buttons, etc.) goes into this layout
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(10, 20, 10, 10)
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
            "Profile": self.create_profile_tab,
            "Hide modes": self.create_hide_modes_page,
            "Backgrounds": self.create_background_page,
            "Fonts": self.create_fonts_page,
            "Themes": self.create_themes_page, 
            "Main menu": self.create_main_menu_page,
            "Sidebar": self.create_sidebar_page,
            "Overviews": self.create_overviews_page,
            "Reviewer": self.create_reviewer_tab,
            "Palette": self.create_colors_page,
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
        self.home_toggle_widget = None

        self.sidebar_button_group = QButtonGroup()
        self.sidebar_button_group.setExclusive(True)

        home_items = ["Hide modes", "Backgrounds", "Fonts", "Palette", "Themes"]
        self.home_toggle_widget = SidebarToggleButton("General", home_items)
        self.home_toggle_widget.page_selected.connect(self.navigate_to_page)
        sidebar_layout.addWidget(self.home_toggle_widget)

        menu_items = ["Main menu", "Sidebar"]
        self.menu_toggle_widget = SidebarToggleButton("Menu", menu_items)
        self.menu_toggle_widget.page_selected.connect(self.navigate_to_page)
        sidebar_layout.addWidget(self.menu_toggle_widget)

        study_zone_items = ["Overviews", "Reviewer"]
        self.study_zone_toggle_widget = SidebarToggleButton("Study zone", study_zone_items)
        self.study_zone_toggle_widget.page_selected.connect(self.navigate_to_page)
        sidebar_layout.addWidget(self.study_zone_toggle_widget)

        # Connect toggle buttons to enable accordion behavior
        self.home_toggle_widget.toggle_button.toggled.connect(
            lambda checked: self._on_section_toggled(self.home_toggle_widget, checked)
        )
        self.menu_toggle_widget.toggle_button.toggled.connect(
            lambda checked: self._on_section_toggled(self.menu_toggle_widget, checked)
        )
        self.study_zone_toggle_widget.toggle_button.toggled.connect(
            lambda checked: self._on_section_toggled(self.study_zone_toggle_widget, checked)
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

        self.navigate_to_page("Profile")
    
    def _open_donate_link(self):
        QDesktopServices.openUrl(QUrl("https://buymeacoffee.com/peacemonk"))

    def _open_bugs_link(self):
        QDesktopServices.openUrl(QUrl("https://github.com/thepeacemonk/Onigiri"))

    def _create_font_selector_group(self, title, config_key):
        """Helper to create a font selection grid for a given config key."""
        group = SectionGroup(title, self, border=False)
        
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
        layout.addWidget(self._create_font_selector_group("Text", "main"))
        layout.addWidget(self._create_font_selector_group("Subtle Text", "subtle"))
        layout.addStretch()
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
    def closeEvent(self, event):
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
        self.home_toggle_widget.deselect_all()
        self.menu_toggle_widget.deselect_all()
        self.study_zone_toggle_widget.deselect_all()
        
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
            self.home_toggle_widget.deselect_all()
            self.menu_toggle_widget.deselect_all()
            self.study_zone_toggle_widget.deselect_all()
        elif self.home_toggle_widget.select_page(page_name):
            if btn := self.sidebar_button_group.checkedButton():
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
            self.menu_toggle_widget.deselect_all()
            self.study_zone_toggle_widget.deselect_all()
        elif self.menu_toggle_widget.select_page(page_name):
            if btn := self.sidebar_button_group.checkedButton():
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
            self.home_toggle_widget.deselect_all()
            self.study_zone_toggle_widget.deselect_all()
        elif self.study_zone_toggle_widget.select_page(page_name):
            if btn := self.sidebar_button_group.checkedButton():
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
            self.home_toggle_widget.deselect_all()
            self.menu_toggle_widget.deselect_all()

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
        all_toggles = [self.home_toggle_widget, self.menu_toggle_widget, self.study_zone_toggle_widget]
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
        title_label.setStyleSheet("font-weight: bold;")
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

        sidebar_selected_bg, primary_button_bg = accent_color, accent_color
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
            QScrollBar:vertical {{ border: none; background: {bg}; width: 10px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {border}; min-height: 20px; border-radius: 5px; }}
            QScrollBar:horizontal {{ border: none; background: {bg}; height: 10px; margin: 0; }}
            QScrollBar::handle:horizontal {{ background: {border}; min-width: 20px; border-radius: 5px; }}
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
            QFrame#MenuSeparator {{
                background-color: {border};
            }}
            /* <<< END NEW CODE >>> */
        
        """)
        self.save_button.setStyleSheet(f"QPushButton{{background-color:{primary_button_bg};color:white;border:none;padding:10px;border-radius:12px;font-weight:bold}}QPushButton:pressed{{background-color:{sidebar_selected_bg}}}")
        self.cancel_button.setStyleSheet(f"QPushButton{{background-color:{secondary_button_bg};color:{secondary_button_fg};border:none;padding:10px;border-radius:12px}}QPushButton:pressed{{background-color:{border}}}")
    
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
        archive_requested = pyqtSignal(object) # ADD THIS LINE

        def __init__(self, text, widget_id, style_colors, parent=None):
            super().__init__(parent)
            self.widget_id, self.col_span, self.row_span = widget_id, 1, 1
            self.display_name = text  # Store the display name
            self.grid_zone = None
            self.setMinimumHeight(35)
            self.setObjectName("DraggableItem")

            layout = QHBoxLayout(self)
            layout.setContentsMargins(5, 0, 5, 0)

            # Use a QStackedWidget to switch between label and line edit
            self.stack = QStackedWidget()
            self.label = QLabel(self.display_name)
            self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.line_edit = QLineEdit(self.display_name)
            self.line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.stack.addWidget(self.label)
            self.stack.addWidget(self.line_edit)
            # FIX: Add stretch factor and alignment flag
            layout.addWidget(self.stack, 1, Qt.AlignmentFlag.AlignCenter)

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
                }}
                QLineEdit {{
                    border: 1px solid {border};
                    border-radius: 4px;
                }}
            """)

            self.setToolTip(f"ID: {self.widget_id}\nDouble-click to rename.\nRight-click to resize.")

        def set_display_name(self, name):
            """Updates the display name from outside the class."""
            self.display_name = name
            self.label.setText(name)
            self.line_edit.setText(name)

        def _finish_editing(self):
            """Called when user finishes renaming."""
            new_name = self.line_edit.text()
            self.display_name = new_name
            self.label.setText(new_name)
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
            
            self.hide()
            # --- FIX: If the drop is cancelled, show the widget again ---
            if drag.exec(Qt.DropAction.MoveAction) == Qt.DropAction.IgnoreAction:
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

        def dragEnterEvent(self, event):
            if event.mimeData().hasText(): event.acceptProposedAction()
            else: event.ignore()

        def dropEvent(self, event):
            source_widget = event.source()
            if isinstance(source_widget, SettingsDialog.DraggableItem):
                event.acceptProposedAction()
                # --- FIX: Pass the event to _handle_drop for position info ---
                self._handle_drop(source_widget, event)
            else:
                event.ignore()
        
        def _handle_drop(self, widget, event): pass # Subclasses will implement this

    class VerticalDropZone(DropZone):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setMinimumHeight(40)
            self.layout = QVBoxLayout(self)
            self.layout.setContentsMargins(5, 5, 5, 5); self.layout.setSpacing(5); self.layout.addStretch()

        def _handle_drop(self, widget, event):
            # If the widget came from a grid, tell the grid to release it
            if hasattr(widget, 'grid_zone') and widget.grid_zone:
                # Get a reference to the grid's layout before we change the parent
                grid_layout = widget.grid_zone.layout()

                # Remove the logical reference from all shelves
                for shelf in widget.grid_zone.shelves.values():
                    if shelf.child_widget is widget:
                        shelf.child_widget = None
                
                # Explicitly remove the widget from the grid's layout
                grid_layout.removeWidget(widget)

            # This part handles items being reordered within the archive itself
            elif old_parent := widget.parent():
                if old_layout := old_parent.layout():
                    old_layout.removeWidget(widget)
            
            widget.row_span, widget.col_span = 1, 1
            widget.setProperty("isOnGrid", False)
            widget.grid_zone = None
            widget.setParent(self)
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
            self.shelves = {}
            self.highlighted_shelf = None
            for i in range(24):
                shelf = SettingsDialog.Shelf(self)
                self.shelves[i] = shelf
                row, col = divmod(i, 4)
                self.grid_layout.addWidget(shelf, row, col)

        def dragMoveEvent(self, event):
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
                        else: # It's a stat card
                            widget.row_span, widget.col_span = 1, 1
                    else: # External add-on, default to 1x1
                        widget.row_span, widget.col_span = 1, 1
                # <<< END NEW CODE >>>
                self.place_item(widget, target_pos)
            else:
                widget.show()
        
        def is_region_free(self, row, col, row_span, col_span, ignored_widget=None):
            if col + col_span > 4 or row + row_span > 6: return False
            for r in range(row, row + row_span):
                for c in range(col, col + col_span):
                    pos = r * 4 + c
                    if self.shelves[pos].child_widget and self.shelves[pos].child_widget is not ignored_widget: return False
            return True

        def place_item(self, item, pos):
            for shelf in self.shelves.values():
                if shelf.child_widget is item: shelf.child_widget = None
            row, col = divmod(pos, 4)
            if not self.is_region_free(row, col, item.row_span, item.col_span, ignored_widget=item):
                for i in range(24):
                    r, c = divmod(i, 4)
                    if self.is_region_free(r, c, item.row_span, item.col_span, ignored_widget=item):
                        row, col = r, c; break
                else:
                    QMessageBox.warning(self.window(), "Placement Error", "No available slot was found for this item.")
                    item.show() # Ensure the item reappears if the drop fails
                    return
            
            item.setProperty("isOnGrid", True); item.grid_zone = self
            item.setParent(self)
            self.grid_layout.addWidget(item, row, col, item.row_span, item.col_span)
            for r in range(row, row + item.row_span):
                for c in range(col, col + item.col_span): self.shelves[r * 4 + c].child_widget = item
            item.show()
        
        def request_resize(self, item, new_row_span, new_col_span):
            new_pos = -1
            for i in range(24):
                r, c = divmod(i, 4)
                if self.is_region_free(r, c, new_row_span, new_col_span, ignored_widget=item):
                    new_pos = i; break
            if new_pos == -1:
                QMessageBox.warning(self.window(), "Resize Error", f"No available {new_row_span}x{new_col_span} slot was found on the grid."); return
            for shelf in self.shelves.values():
                if shelf.child_widget is item: shelf.child_widget = None
            new_row, new_col = divmod(new_pos, 4)
            conflicting_widgets = set()
            for r in range(new_row, new_row + new_row_span):
                for c in range(new_col, new_col + new_col_span):
                    if self.shelves[r * 4 + c].child_widget: conflicting_widgets.add(self.shelves[r * 4 + c].child_widget)
            for conflicting_item in conflicting_widgets:
                for shelf in self.shelves.values():
                    if shelf.child_widget is conflicting_item: shelf.child_widget = None
                # Clear its old position from the shelves
                for shelf in self.shelves.values():
                    if shelf.child_widget is conflicting_item:
                        shelf.child_widget = None

                # Find the first available 1x1 spot for it and place it there
                found_spot = False
                for i in range(24):
                    r, c = divmod(i, 4)
                    # Use the item's own size for finding a new spot, default to 1x1 if needed
                    r_span = getattr(conflicting_item, 'row_span', 1)
                    c_span = getattr(conflicting_item, 'col_span', 1)
                    if self.is_region_free(r, c, r_span, c_span):
                        self.place_item(conflicting_item, i)
                        found_spot = True
                        break
                if not found_spot:
                    # Fallback: if no space for its size is found, try to place as 1x1
                    for i in range(24):
                        r, c = divmod(i, 4)
                        if self.is_region_free(r, c, 1, 1):
                            conflicting_item.row_span = 1
                            conflicting_item.col_span = 1
                            self.place_item(conflicting_item, i)
                            break
            item.row_span, item.col_span = new_row_span, new_col_span
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
            self.setMinimumSize(120, 45)
            self.child_widget = None
            # The is_highlighted attribute is no longer needed here

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
                btn = custom_menu.add_action_button(f"{i} Column{'s' if i > 1 else ''}", i, width_group, self.col_span == i)

            custom_menu.add_separator()

            # --- Height Actions ---
            height_group = QButtonGroup(custom_menu)
            height_group.setExclusive(True)
            max_rows = 2 if is_heatmap else 1
            for i in range(1, max_rows + 1):
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
    
    class OnigiriGridDropZone(GridDropZone):
        def __init__(self, main_editor, parent=None):
            super().__init__(main_editor, parent)
            # Override grid size to 3 rows, 4 columns
            for i in range(12, 24):
                if i in self.shelves:
                    self.shelves[i].setParent(None)
                    del self.shelves[i]
        
        # Override region check for 3x4 grid
        def is_region_free(self, row, col, row_span, col_span, ignored_widget=None):
            if col + col_span > 4 or row + row_span > 3: return False
            for r in range(row, row + row_span):
                for c in range(col, col + col_span):
                    pos = r * 4 + c
                    if pos in self.shelves and self.shelves[pos].child_widget and self.shelves[pos].child_widget is not ignored_widget: return False
            return True

    class OnigiriArchiveZone(VerticalDropZone):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setMinimumHeight(80) # Make it a bit taller

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
                "archive": []
            }

            saved_layout = self.settings_dialog.current_config.get("onigiriWidgetLayout", DEFAULTS)
            grid_config = saved_layout.get("grid", DEFAULTS["grid"])
            archive_config = saved_layout.get("archive", DEFAULTS["archive"])

            widget_definitions = {
                "studied": "Studied Card", "time": "Time Card", 
                "pace": "Pace Card", "retention": "Retention Card", "heatmap": "Heatmap"
            }

            # Create all items
            for widget_id, text in widget_definitions.items():
                item = SettingsDialog.OnigiriDraggableItem(text, widget_id, style_colors)
                item.archive_requested.connect(self._archive_item)
                self.all_onigiri_items[widget_id] = item

            # Combine grid and archive configs to find all saved names
            all_saved_configs = grid_config.copy()
            if isinstance(archive_config, dict):
                all_saved_configs.update(archive_config)

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
                    self.grid_zone.place_item(item, config.get("pos", 0))

            # Place items in archive (handle both list and dict for backward compatibility)
            archive_ids = archive_config if isinstance(archive_config, list) else archive_config.keys()
            for widget_id in archive_ids:
                if item := self.all_onigiri_items.get(widget_id):
                    self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)

        def _archive_item(self, item):
            for shelf in self.grid_zone.shelves.values():
                if shelf.child_widget is item: shelf.child_widget = None
                self.archive_zone.layout.insertWidget(self.archive_zone.layout.count() - 1, item)

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
    
    # =================================================================
    # END: Onigiri Widget Layout Editor
    # =================================================================

    class MainMenuLayoutEditor(QWidget):
        def __init__(self, settings_dialog):
            super().__init__()
            self.settings_dialog = settings_dialog
            main_layout = QVBoxLayout(self); main_layout.setSpacing(15)
            grid_group = QGroupBox("External Add-on Grid")
            grid_group.setObjectName("LayoutGroup")
            self.grid_zone = SettingsDialog.GridDropZone(self, grid_group)

            # Setup layout for grid group to hold the grid and the new button
            grid_group_layout = QVBoxLayout(grid_group)
            grid_group_layout.addWidget(self.grid_zone)

            reset_button = QPushButton("Reset to Default Positions")
            reset_button.clicked.connect(self._reset_grid_layout)
            reset_button.setToolTip("Resets all external add-ons to a default 1x4 layout at the top of the grid.")
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            button_layout.addWidget(reset_button)
            grid_group_layout.addLayout(button_layout)

            main_layout.addWidget(grid_group)

            archive_group = QGroupBox("Archived External Add-ons")
            archive_group.setObjectName("LayoutGroup")
            self.archive_zone = SettingsDialog.OnigiriArchiveZone(archive_group)
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
                    self.grid_zone.place_item(item, config.get("grid_position", 0))
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

        def _reset_grid_layout(self):
            """Forcefully resets all external add-ons to a default layout."""
            all_items = list(self.all_external_items.values())

            # Detach all items from any parent
            for item in all_items:
                item.setParent(None)

            # Clear both grid and archive
            for shelf in self.grid_zone.shelves.values():
                shelf.child_widget = None
            while self.archive_zone.layout.count() > 1: # Keep the spacer
                widget = self.archive_zone.layout.takeAt(0).widget()
                if widget:
                    widget.setParent(None)

            # Get a consistently sorted list
            sorted_items = sorted(all_items, key=lambda x: x.widget_id)

            # Place items sequentially, giving each a full row
            current_row = 0
            for item in sorted_items:
                # Reset the display name to its default
                default_name = item.widget_id.split('.')[0]
                item.set_display_name(default_name)

                # Grid has 6 rows (0-5)
                if current_row < 6:
                    item.row_span = 1
                    item.col_span = 4
                    # Position is the top-left cell of the current row
                    position = current_row * 4
                    self.grid_zone.place_item(item, position)
                    current_row += 1
                else:
                    # If grid is full, put remaining items in archive
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
        organize_section.add_layout(form_layout)
        
        # Create and add the layout editor widget
        self.organize_widget_container = self._create_organize_layout_widget()
        organize_section.add_widget(self.organize_widget_container)
        layout.addWidget(organize_section)

        divider3 = QFrame()
        divider3.setFrameShape(QFrame.Shape.HLine)
        divider3.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider3)
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
        self._populate_pills_for_keys(light_heatmap_layout, "light", ["--heatmap-color"])
        heatmap_color_modes_layout.addWidget(light_heatmap_group)

        dark_heatmap_group, dark_heatmap_layout = self._create_inner_group("Dark Mode")
        dark_heatmap_layout.setSpacing(5)
        self._populate_pills_for_keys(dark_heatmap_layout, "dark", ["--heatmap-color"])
        heatmap_color_modes_layout.addWidget(dark_heatmap_group)
        heatmap_section.add_layout(heatmap_color_modes_layout)

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
        return page

    def _create_organize_layout_widget(self):
        # This widget will contain BOTH layout editors
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(20)

        # This editor widget will be stored so we can retrieve its data on save.
        self.onigiri_layout_editor = self.OnigiriLayoutEditor(self)
        self.external_layout_editor = self.MainMenuLayoutEditor(self)
        
        layout.addWidget(self.onigiri_layout_editor)
        layout.addWidget(self.external_layout_editor)
        
        return container
    
    def _create_hide_mode_card(self, title, toggle_widget, items):
        """
        Create a hide mode card with sections showing what gets hidden.
        
        Args:
            title: The mode title (Hide, Pro, or Max)
            toggle_widget: The toggle button widget
            items: List of tuples (section_name, item_list) where item_list is a list of feature strings
        """
        card = QFrame()
        card.setObjectName("hideModeCard")
        card.setFixedWidth(200)  # Back to original width
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 15, 8, 20)  # Extra bottom margin to prevent clipping

        # Title
        title_label = QLabel(title)
        title_label.setObjectName("hideModeTitleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("QFrame { background-color: rgba(128, 128, 128, 0.3); max-height: 1px; }")
        layout.addWidget(separator)
        layout.addSpacing(1)  # More space after separator for rounded corners

        # Content area for items (no scroll area to avoid scrollbars)
        content_widget = QWidget()
        content_widget.setStyleSheet("QWidget { background: transparent; }")
        content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(7)  # More spacing between items for rounded corners
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Add items - no section headers for minimal design
        for section_name, item_list in items:
            # Just add the items directly in rounded boxes
            for item in item_list:
                # Create a frame for the rounded box that fills width
                item_box = QFrame()
                item_box.setObjectName("hideModeItemBox")
                
                # Style the box with custom background colors
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
                if theme_manager.night_mode:
                    item_label.setStyleSheet("font-size: 11px; color: #f2f2f2; background: transparent;")
                else:
                    item_label.setStyleSheet("font-size: 11px; color: #2c2c2c; background: transparent;")
                box_layout.addWidget(item_label)
                
                content_layout.addWidget(item_box)

        content_layout.addStretch()
        layout.addWidget(content_widget)

        # Toggle button at bottom
        layout.addStretch()
        toggle_layout = QHBoxLayout()
        toggle_layout.addStretch()
        toggle_layout.addWidget(toggle_widget)
        toggle_layout.addStretch()
        layout.addLayout(toggle_layout)

        return card
    # <<< END NEW CODE >>>

    def create_hide_modes_page(self):
        page, layout = self._create_scrollable_page()
        
        # Add title at the top
        title = QLabel("Hide Modes")
        title.setObjectName("hideModePageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        if theme_manager.night_mode:
            title.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 20px; margin-bottom: 5px; color: #e0e0e0; background-color: #2c2c2c; padding: 0 5px;")
        else:
            title.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 20px; margin-bottom: 5px; color: #212121; background-color: #f3f3f3; padding: 0 5px;")
        layout.addWidget(title)

        # Add description at the top
        description = QLabel(
            "Choose how much of the interface you want to hide for a more immersive experience. "
            "Each mode builds upon the previous one, hiding progressively more elements."
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 12px; color: #666; margin-bottom: 8px; padding: 10px;")
        layout.addWidget(description)
        
        cards_container = QWidget()
        cards_layout = QHBoxLayout(cards_container)
        cards_layout.setSpacing(20)
        cards_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Define what each mode hides - simplified flat structure
        # Hide mode - Basic hiding
        hide_items = [
            ("", [
                "Native top toolbar (Main Menu)",
                "Native bottom toolbar (Main Menu & Overview)"
            ])
        ]

        # Pro mode - Includes everything from Hide + more
        pro_items = [
            ("", [
                "Everything in Hide",
                "Modern toolbar (Overview)",
                "Native top toolbar (Reviewer)",
                "⚠ Requires keyboard shortcuts"
            ])
        ]

        # Max mode - Includes everything from Pro + even more
        max_items = [
            ("", [
                "Everything in Pro.",
                "Bottom toolbar (Reviewer)",
                "No buttons are displayed",
                "⚠ Requires keyboard shortcuts"
            ])
        ]

        card1 = self._create_hide_mode_card("Hide", self.hide_native_header_checkbox, hide_items)
        card2 = self._create_hide_mode_card("Pro", self.pro_hide_checkbox, pro_items)
        card3 = self._create_hide_mode_card("Max", self.max_hide_checkbox, max_items)

        cards_layout.addWidget(card1)
        cards_layout.addWidget(card2)
        cards_layout.addWidget(card3)

        layout.addStretch()
        layout.addWidget(cards_container)
        layout.addStretch()
        
        return page

    def create_overviews_page(self):
        page, layout = self._create_scrollable_page()
        
        overview_section = SectionGroup(
            "Overview",
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
        sidebar_section.add_widget(self._create_toggle_row(self.hide_profile_bar_checkbox, "Hide Profile bar"))
        sidebar_section.add_widget(self._create_toggle_row(self.hide_deck_counts_checkbox, "Hide Deck Counts"))

        layout.addWidget(sidebar_section)

        divider1 = QFrame()
        divider1.setFrameShape(QFrame.Shape.HLine)
        divider1.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider1)

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
        
        deck_icons_group, deck_icons_layout_content = self._create_inner_group("Deck Icons")
        deck_icons_layout = QGridLayout(); deck_icons_layout.setSpacing(15)
        deck_icons_layout_content.addLayout(deck_icons_layout)
        deck_icons_to_configure = {"folder": "Folder Icon", "deck_child": "Child Deck Icon", "options": "Options Icon", "collapse_closed": "Collapsed Icon (+)", "collapse_open": "Expanded Icon (-)"}
        row, col, num_cols = 0, 0, 3
        for key, label_text in deck_icons_to_configure.items():
            card = QWidget(); card_layout = QVBoxLayout(card); card_layout.setContentsMargins(0,0,0,0); card_layout.setSpacing(5)
            label = QLabel(label_text); label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            control_widget = self._create_icon_control_widget(key); self.icon_assignment_widgets.append(control_widget)
            card_layout.addWidget(label); card_layout.addWidget(control_widget); deck_icons_layout.addWidget(card, row, col)
            col += 1
            if col >= num_cols: col = 0; row += 1
        deck_section.add_widget(deck_icons_group)

        sizing_section, sizing_layout_content = self._create_inner_group("Icon Sizing (in pixels)")
        sizing_layout = QFormLayout(); sizing_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        sizing_layout_content.addLayout(sizing_layout)
        icon_sizes_to_configure = {"deck_folder": "Deck/Folder Icons:", "action_button": "Action Button Icons:", "collapse": "Expand/Collapse Icons:", "options_gear": "Deck Options Gear Icon:"}
        for key, label in icon_sizes_to_configure.items(): sizing_layout.addRow(label, self.create_icon_size_spinbox(key, DEFAULT_ICON_SIZES[key]))
        reset_sizes_button = QPushButton("Reset Sizes to Default"); reset_sizes_button.clicked.connect(self.reset_icon_sizes_to_default); sizing_layout.addRow(reset_sizes_button)
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
        return page

    def create_profile_tab(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(15)
        
        details_section = SectionGroup("User Details", self)
        form_layout = QFormLayout()
        self.name_input = QLineEdit(self.current_config.get("userName", DEFAULTS["userName"]))
        form_layout.addRow("User Name:", self.name_input)
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
        layout.addWidget(visibility_section)
        
        layout.addStretch()
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

        # --- START: New Canvas Inset Effect Section ---
        canvas_effect_group, canvas_effect_layout = self._create_inner_group("Canvas Inset Effect")
        canvas_effect_group.setToolTip("Apply a visual effect to the 'Canvas Inset' background color.")

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
        # --- END: New Canvas Inset Effect Section ---
                
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
    
    def _toggle_canvas_intensity_spinbox(self):
        is_disabled = self.canvas_effect_none_radio.isChecked()
        self.canvas_effect_intensity_spinbox.setEnabled(not is_disabled)

    def create_background_page(self):
        page, layout = self._create_scrollable_page()
        
        user_files_path = os.path.join(self.addon_path, "user_files", "main_bg")
        os.makedirs(user_files_path, exist_ok=True)
        try:
            cached_user_files = sorted([f for f in os.listdir(user_files_path) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))])
        except OSError:
            cached_user_files = []

        mode_group, mode_layout_content = self._create_inner_group("Main Background Type")
        mode_layout = QHBoxLayout(); mode = mw.col.conf.get("modern_menu_background_mode", "color")
        # Fallback for users who have the old "image" mode saved
        if mode == "image":
            mode = "image_color"
            
        self.color_radio = QRadioButton("Solid Color"); self.accent_radio = QRadioButton("Accent Color"); self.image_color_radio = QRadioButton("Color + Image")
        self.color_radio.setChecked(mode == "color"); self.accent_radio.setChecked(mode == "accent"); self.image_color_radio.setChecked(mode == "image_color")
        mode_layout.addWidget(self.color_radio); mode_layout.addWidget(self.image_color_radio); mode_layout.addWidget(self.accent_radio); mode_layout.addStretch(); mode_layout_content.addLayout(mode_layout); layout.addWidget(mode_group)

        self.color_group, color_layout = self._create_inner_group("Main Color Options")

        # <<< THIS IS THE FIX: Load colors from the current session's config, not the old saved file. >>>
        current_light_bg = self.current_config.get("colors", {}).get("light", {}).get("--bg", "#FFFFFF")
        current_dark_bg = self.current_config.get("colors", {}).get("dark", {}).get("--bg", "#2C2C2C")
        self.bg_light_row = self._create_color_picker_row("Background (Light Mode)", current_light_bg, "bg_light")
        self.bg_dark_row = self._create_color_picker_row("Background (Dark Mode)", current_dark_bg, "bg_dark")
        
        color_layout.addLayout(self.bg_light_row)
        color_layout.addLayout(self.bg_dark_row)
        layout.addWidget(self.color_group)

        self.image_group, image_options_layout = self._create_inner_group("Main Image Options")
        
        self.separate_images_container = QWidget()
        sep_layout = QHBoxLayout(self.separate_images_container)
        sep_layout.setContentsMargins(0, 10, 0, 0)
        self.galleries["main_light"] = {}
        sep_layout.addWidget(self._create_image_gallery_group("main_light", "user_files/main_bg", "modern_menu_background_image_light", title="Light Mode Background", image_files_cache=cached_user_files))
        self.galleries["main_dark"] = {}
        sep_layout.addWidget(self._create_image_gallery_group("main_dark", "user_files/main_bg", "modern_menu_background_image_dark", title="Dark Mode Background", image_files_cache=cached_user_files))
        image_options_layout.addWidget(self.separate_images_container)

        effects_layout = QHBoxLayout(); self.bg_blur_label = QLabel("Background Blur:"); self.bg_blur_spinbox = QSpinBox(); self.bg_blur_spinbox.setMinimum(0); self.bg_blur_spinbox.setMaximum(100); self.bg_blur_spinbox.setSuffix(" %"); self.bg_blur_spinbox.setValue(mw.col.conf.get("modern_menu_background_blur", 0)); effects_layout.addWidget(self.bg_blur_label); effects_layout.addWidget(self.bg_blur_spinbox); self.bg_opacity_label = QLabel("Background Opacity:"); self.bg_opacity_spinbox = QSpinBox(); self.bg_opacity_spinbox.setMinimum(0); self.bg_opacity_spinbox.setMaximum(100); self.bg_opacity_spinbox.setSuffix(" %"); self.bg_opacity_spinbox.setValue(mw.col.conf.get("modern_menu_background_opacity", 100)); effects_layout.addWidget(self.bg_opacity_label); effects_layout.addWidget(self.bg_opacity_spinbox); effects_layout.addStretch(); image_options_layout.addLayout(effects_layout); layout.addWidget(self.image_group)

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

        self.color_radio.toggled.connect(self.toggle_background_options); self.accent_radio.toggled.connect(self.toggle_background_options); self.image_color_radio.toggled.connect(self.toggle_background_options)
        self.sidebar_bg_main_radio.toggled.connect(self.toggle_sidebar_background_options)
        self.toggle_background_options(); self.toggle_sidebar_background_options()
        
        # --- RESET BUTTONS ---
        reset_buttons_layout = QHBoxLayout()
        reset_buttons_layout.addStretch()

        reset_sidebar_button = QPushButton("Reset Sidebar to Default")
        reset_sidebar_button.clicked.connect(self.reset_sidebar_to_default)
        reset_buttons_layout.addWidget(reset_sidebar_button)

        reset_bg_button = QPushButton("Reset Background to Default")
        reset_bg_button.clicked.connect(self.reset_background_to_default)
        reset_buttons_layout.addWidget(reset_bg_button)

        layout.addLayout(reset_buttons_layout)
        # --- END OF MODIFIED BLOCK ---
        
        layout.addStretch()
        return page

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
        # If the old 'image' mode was saved, default to 'color + image' to prevent a blank state
        if type_mode == 'image':
            type_mode = 'image_color'
            
        type_layout = QHBoxLayout()
        self.sidebar_bg_type_color_radio = QRadioButton("Solid Color")
        self.sidebar_bg_type_accent_radio = QRadioButton("Accent Color")
        self.sidebar_bg_type_image_color_radio = QRadioButton("Color + Image")
        
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
        icon_path = os.path.join(self.addon_path, "user_files", "icons", "system_icons", "xmark.svg")
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
        if not hasattr(self, 'shape_buttons') or not self.shape_buttons:
            return

        # Clear layout but keep widgets in self.shape_buttons
        while item := self.shapes_grid_layout.takeAt(0):
            if item.widget():
                item.widget().setParent(None)

        if not width:
            # Default to 5 columns for initial layout
            num_cols = 5
        else:
            # Card width is 80px, spacing is 10px
            card_total_width = 80 + self.shapes_grid_layout.spacing()
            num_cols = max(1, int(width / card_total_width))
        
        # Repopulate the grid from the master list of buttons
        for i, button in enumerate(self.shape_buttons):
            row, col = divmod(i, num_cols)
            self.shapes_grid_layout.addWidget(button, row, col)

    def _create_shape_selector(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setFixedHeight(175)
        
        self.shape_scroll_content = QWidget()
        self.shapes_grid_layout = QGridLayout(self.shape_scroll_content)
        self.shapes_grid_layout.setSpacing(10)
        self.shapes_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll_area.setWidget(self.shape_scroll_content)
        self.shape_scroll_content.installEventFilter(self)
        
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
        self.reviewer_bg_image_color_radio = QRadioButton("Color + Image")
        
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

        mode_layout_content = bottom_bar_section.content_layout
        mode_layout = QHBoxLayout()

        bottom_bar_button_group = QButtonGroup(bottom_bar_section)

        self.reviewer_bar_main_radio = QRadioButton("Match Main Background")
        self.reviewer_bar_color_radio = QRadioButton("Solid Color")
        self.reviewer_bar_image_color_radio = QRadioButton("Color + Image")

        bottom_bar_button_group.addButton(self.reviewer_bar_main_radio)
        bottom_bar_button_group.addButton(self.reviewer_bar_color_radio)
        bottom_bar_button_group.addButton(self.reviewer_bar_image_color_radio)

        self.reviewer_bar_main_radio.setChecked(self.reviewer_bottom_bar_mode == "main")
        self.reviewer_bar_color_radio.setChecked(self.reviewer_bottom_bar_mode == "color")
        self.reviewer_bar_image_color_radio.setChecked(self.reviewer_bottom_bar_mode == "image_color")

        mode_layout.addWidget(self.reviewer_bar_main_radio)
        mode_layout.addWidget(self.reviewer_bar_color_radio)
        mode_layout.addWidget(self.reviewer_bar_image_color_radio)
        mode_layout.addStretch()
        mode_layout_content.addLayout(mode_layout)

        offset_layout = QHBoxLayout()
        offset_layout.setContentsMargins(0, 10, 0, 0)
        offset_label = QLabel("Image Horizontal Offset:")
        offset_label.setToolTip("Set a pixel offset for the background image's horizontal position.\nAccepts positive, negative, and decimal values.")

        self.reviewer_bar_offset_spinbox = QDoubleSpinBox()
        self.reviewer_bar_offset_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.reviewer_bar_offset_spinbox.setRange(-500.0, 500.0)
        self.reviewer_bar_offset_spinbox.setSingleStep(0.25)
        self.reviewer_bar_offset_spinbox.setDecimals(2)
        self.reviewer_bar_offset_spinbox.setSuffix(" px")

        if theme_manager.night_mode:
            border_color, bg_color = "#4a4a4a", "#3a3a3a"
        else:
            border_color, bg_color = "#e0e0e0", "#f5f5f5"

        self.reviewer_bar_offset_spinbox.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {bg_color}; border: 1px solid {border_color};
                border-radius: 8px; padding: 4px;
            }}
        """)

        offset_val_str = mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_offset_x", "-3.25")
        try:
            offset_val = float(offset_val_str)
        except (ValueError, TypeError):
            offset_val = -3.25
        self.reviewer_bar_offset_spinbox.setValue(offset_val)

        offset_layout.addWidget(offset_label)
        offset_layout.addWidget(self.reviewer_bar_offset_spinbox)
        offset_layout.addStretch()
        mode_layout_content.addLayout(offset_layout)

        self.reviewer_bar_match_main_group = QWidget()
        match_main_layout = QVBoxLayout(self.reviewer_bar_match_main_group)
        match_main_layout.setContentsMargins(0, 10, 0, 0)

        match_effects_layout = QHBoxLayout()
        blur_label = QLabel("Background Blur:")
        self.reviewer_bar_match_main_blur_spinbox = QSpinBox()
        self.reviewer_bar_match_main_blur_spinbox.setMinimum(0); self.reviewer_bar_match_main_blur_spinbox.setMaximum(100)
        self.reviewer_bar_match_main_blur_spinbox.setSuffix(" %")
        self.reviewer_bar_match_main_blur_spinbox.setValue(mw.col.conf.get("onigiri_reviewer_bottom_bar_match_main_blur", 5))

        opacity_label = QLabel("Bar Opacity:")
        self.reviewer_bar_match_main_opacity_spinbox = QSpinBox()
        self.reviewer_bar_match_main_opacity_spinbox.setMinimum(0); self.reviewer_bar_match_main_opacity_spinbox.setMaximum(100)
        self.reviewer_bar_match_main_opacity_spinbox.setSuffix(" %")
        self.reviewer_bar_match_main_opacity_spinbox.setValue(mw.col.conf.get("onigiri_reviewer_bottom_bar_match_main_opacity", 90))

        match_effects_layout.addWidget(blur_label)
        match_effects_layout.addWidget(self.reviewer_bar_match_main_blur_spinbox)
        match_effects_layout.addSpacing(20)
        match_effects_layout.addWidget(opacity_label)
        match_effects_layout.addWidget(self.reviewer_bar_match_main_opacity_spinbox)
        match_effects_layout.addStretch()
        match_main_layout.addLayout(match_effects_layout)
        mode_layout_content.addWidget(self.reviewer_bar_match_main_group)

        self.reviewer_bar_custom_group = self.create_reviewer_bar_custom_options()
        mode_layout_content.addWidget(self.reviewer_bar_custom_group)

        self.reviewer_bar_main_radio.toggled.connect(lambda checked: self._on_bottom_bar_mode_changed("main", checked))
        self.reviewer_bar_color_radio.toggled.connect(lambda checked: self._on_bottom_bar_mode_changed("color", checked))
        self.reviewer_bar_image_color_radio.toggled.connect(lambda checked: self._on_bottom_bar_mode_changed("image_color", checked))
        self.reviewer_bar_main_radio.toggled.connect(self.toggle_reviewer_bar_options)
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
        self.reviewer_bg_light_color_row = self._create_color_picker_row(
            "Color (Light Mode)", conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF"), "reviewer_bg_light"
        )
        self.reviewer_bg_dark_color_row = self._create_color_picker_row(
            "Color (Dark Mode)", conf.get("onigiri_reviewer_bg_dark_color", "#2C2C2C"), "reviewer_bg_dark"
        )
        color_layout.addLayout(self.reviewer_bg_light_color_row)
        color_layout.addLayout(self.reviewer_bg_dark_color_row)
        layout.addWidget(self.reviewer_bg_color_group)
        
        # Image galleries (only for Color + Image mode)
        self.reviewer_bg_image_group = QWidget()
        image_layout = QVBoxLayout(self.reviewer_bg_image_group)
        image_layout.setContentsMargins(0, 10, 0, 0)
        
        # Separate images galleries
        self.reviewer_bg_separate_container = QWidget()
        sep_layout = QHBoxLayout(self.reviewer_bg_separate_container)
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
        image_layout.addWidget(self.reviewer_bg_separate_container)
        
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
        
        # Initially hide image options (only show for Color + Image mode)
        self.reviewer_bg_image_group.setVisible(False)
        
        return widget
    
    def _toggle_reviewer_bg_options(self):
        """Toggle visibility of reviewer background options based on selected mode."""
        is_main = self.reviewer_bg_main_radio.isChecked()
        self.reviewer_bg_main_group.setVisible(is_main)
        self.reviewer_bg_custom_group.setVisible(not is_main)
        
        # Control visibility of color and image options within custom group
        if not is_main:
            is_color = self.reviewer_bg_color_radio.isChecked()
            is_image_color = self.reviewer_bg_image_color_radio.isChecked()
            
            # Show color options for both 'Solid Color' and 'Color + Image'
            self.reviewer_bg_color_group.setVisible(is_color or is_image_color)
            
            # Show image options only for 'Color + Image'
            self.reviewer_bg_image_group.setVisible(is_image_color)
            
            # Show effects (blur, opacity) only for 'Color + Image'
            self.reviewer_bg_effects_container.setVisible(is_image_color)
    


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
        
        page_container = QWidget()
        # We give the container a name so we can style it from the main stylesheet.
        page_container.setObjectName("pageContainer")
        
        page_layout = QVBoxLayout(page_container)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        
        return page_container, content_layout
    
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

        self._populate_gallery_placeholders(key, image_files_cache)
        layout.addLayout(button_row)
        self._update_delete_button_state(key)
        return group_container

    def _create_gallery_ui(self):
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setFixedHeight(140)
        content_widget = QWidget(); grid_layout = QGridLayout(content_widget)
        grid_layout.setSpacing(10); grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll_area.setWidget(content_widget)
        return scroll_area, grid_layout

    def _on_thumbnail_ready(self, key, index, pixmap, filename):
        gallery = self.galleries.get(key)
        if not gallery or index >= len(gallery['labels']): return
        
        label = gallery['labels'][index]
        label.setPixmap(pixmap)
        label.setToolTip(filename)
        label.setProperty("image_filename", filename)

        if gallery['selected'] == filename:
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
            gallery['grid_layout'].addWidget(QLabel(f"No files in '{os.path.basename(gallery['folder'])}' folder."), 0, 0)
            return

        for i, filename in enumerate(image_files):
            placeholder = QLabel("â³"); placeholder.setFixedSize(110, 110); placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("QLabel { background-color: rgba(128,128,128,0.1); border-radius: 10px; }")
            placeholder.setProperty("gallery_key", key)
            placeholder.installEventFilter(self)
            gallery['grid_layout'].addWidget(placeholder, i // 4, i % 4)
            gallery['labels'].append(placeholder)
        
        shape = 'circular' if key == 'profile_pic' else 'rounded'
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
        if hasattr(self, 'shape_scroll_content') and source is self.shape_scroll_content and event.type() == QEvent.Type.Resize:
            self._reflow_shape_icons(event.size().width())
            return False

        if event.type() == QEvent.Type.MouseButtonPress:
            if source.property("gallery_key"):
                key = source.property("gallery_key")
                filename = source.property("image_filename")
                if filename:
                    gallery = self.galleries[key]
                    gallery['selected'] = filename
                    if gallery.get('path_input'): gallery['path_input'].setText(filename)
                    for label in gallery['labels']:
                        label.setStyleSheet(THUMBNAIL_STYLE if label.property("image_filename") != filename else THUMBNAIL_STYLE_SELECTED)
                    self._update_delete_button_state(key)
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
        
        for label in gallery['labels']:
            label.deleteLater()
        
        gallery['labels'] = []
        self._populate_gallery_placeholders(key)
        self._update_delete_button_state(key)

    def _update_delete_button_state(self, key):
        gallery = self.galleries[key]
        if delete_button := gallery.get('delete_button'):
            delete_button.setEnabled(bool(gallery['selected']))

    def _create_icon_control_widget(self, key):
        control_widget = QWidget(); layout = QHBoxLayout(control_widget); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(10)
        preview_label = QLabel(); preview_label.setFixedSize(32, 32); preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        border_color = "#4a4a4a" if theme_manager.night_mode else "#e0e0e0"; preview_label.setStyleSheet(f"border: 1px solid {border_color}; border-radius: 4px;")
        if theme_manager.night_mode: btn_bg, btn_border, fg = "#4a4a4a", "#5a5a5a", "#e0e0e0"
        else: btn_bg, btn_border, fg = "#f0f0f0", "#c9c9c9", "#212121"
        button_style = f"QPushButton {{ background-color: {btn_bg}; color: {fg}; border: 1px solid {btn_border}; padding: 5px 10px; border-radius: 4px; }} QPushButton:pressed {{ background-color: {btn_border}; }}"
        change_button = QPushButton("Change"); change_button.setStyleSheet(button_style); change_button.clicked.connect(lambda: self._change_icon(control_widget))
        delete_button = QPushButton("Delete"); delete_button.setStyleSheet(button_style); delete_button.clicked.connect(lambda: self._delete_icon(control_widget))
        layout.addWidget(preview_label); layout.addWidget(change_button); layout.addWidget(delete_button); layout.addStretch()
        control_widget.setProperty("icon_key", key); control_widget.setProperty("icon_filename", mw.col.conf.get(f"modern_menu_icon_{key}", "")); control_widget.setProperty("preview_label", preview_label)
        self._update_icon_preview_for_widget(control_widget); return control_widget

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
        icons_dir = os.path.join(self.addon_path, "user_files/icons"); filepath, _ = QFileDialog.getOpenFileName(self, "Select Icon", icons_dir, "SVG Files (*.svg)")
        if filepath:
            filename = os.path.basename(filepath); dest_path = os.path.join(icons_dir, filename)
            if not os.path.abspath(filepath).startswith(os.path.abspath(icons_dir)):
                try: shutil.copy(filepath, dest_path)
                except Exception as e: QMessageBox.warning(self, "Error", f"Could not copy icon to library: {e}"); return
            widget.setProperty("icon_filename", filename); self._update_icon_preview_for_widget(widget)
            
            if "icons" in self.galleries:
                self._refresh_gallery("icons")

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
        color = QColorDialog.getColor(initial_color, self)
        
        if color.isValid():
            color_name = color.name()
            line_edit.setText(color_name)
            if isinstance(button, CircularColorButton):
                button.setColor(color_name)
    
    def _ensure_ui_for_theme_application(self):
        if not hasattr(self, 'light_accent_color_input'):
            dummy_colors_page = self.create_colors_page()
            dummy_colors_page.deleteLater()
        
        if not hasattr(self, 'color_radio'):
            dummy_bg_page = self.create_background_page()
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

    def reset_background_to_default(self):
        self.color_radio.setChecked(True); self.bg_light_color_input.setText(DEFAULTS["colors"]["light"]["--bg"]); self.bg_dark_color_input.setText(DEFAULTS["colors"]["dark"]["--bg"])
        for key in ['main_light', 'main_dark', 'sidebar_bg']:
            if key in self.galleries:
                self.galleries[key]['selected'] = ""; 
                if self.galleries[key].get('path_input'): self.galleries[key]['path_input'].setText("")
                self._refresh_gallery(key)
        self.bg_blur_spinbox.setValue(0); self.bg_opacity_spinbox.setValue(100); self.sidebar_bg_main_radio.setChecked(True)
        self.sidebar_bg_type_color_radio.setChecked(True); self.sidebar_bg_light_color_input.setText("#EEEEEE"); self.sidebar_bg_dark_color_input.setText("#3C3C3C")
        self.sidebar_bg_blur_spinbox.setValue(0); self.sidebar_bg_opacity_spinbox.setValue(100)
    
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
        # Set mode to "Match Main Background"
        self.reviewer_bar_main_radio.setChecked(True)
        
        # Reset match main settings
        self.reviewer_bar_match_main_blur_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_match_main_blur"])
        self.reviewer_bar_match_main_opacity_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_match_main_opacity"])
        
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
        
        # Reset offset
        self.reviewer_bar_offset_spinbox.setValue(-3.25)
        
        QMessageBox.information(self, "Bottom Bar Reset", "The bottom bar background settings have been reset to default values.\nPress 'Save' to apply the changes.")


    def toggle_background_options(self): 
        is_color=self.color_radio.isChecked()
        is_image_color=self.image_color_radio.isChecked()
        self.color_group.setVisible(is_color or is_image_color)
        self.image_group.setVisible(is_image_color)
        self.bg_opacity_label.setVisible(is_image_color)
        self.bg_opacity_spinbox.setVisible(is_image_color)        
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
        is_custom = not is_main
        self.reviewer_bar_match_main_group.setVisible(is_main)
        self.reviewer_bar_custom_group.setVisible(is_custom)

        if is_custom:
            is_color = self.reviewer_bar_color_radio.isChecked()
            is_image_color = self.reviewer_bar_image_color_radio.isChecked()

            # Show color picker for 'Solid Color' and 'Color + Image'
            self.reviewer_bar_color_group.setVisible(is_color or is_image_color)

            # Show image gallery and effects (blur, opacity) for 'Image' and 'Color + Image'
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
            description=f"Your own personal imported themes."
        )
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
        """Applies the selected theme's colors to the config and live UI."""
        light_palette = theme_data.get("light", {})
        dark_palette = theme_data.get("dark", {})

        # 1. Update the internal config dictionary
        self.current_config["colors"]["light"].update(light_palette)
        self.current_config["colors"]["dark"].update(dark_palette)

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
            
        showInfo("Theme applied! Press 'Save' to keep the changes.")

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
        """Opens a file dialog to import a theme from a JSON file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, 
            "Import Theme", 
            "", 
            "JSON Files (*.json)"
        )
        if not filepath:
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                theme_data = json.load(f)
            
            # Validate the theme file structure
            if not isinstance(theme_data, dict) or "light" not in theme_data or "dark" not in theme_data:
                QMessageBox.warning(self, "Import Error", "The selected file is not a valid Onigiri theme file.")
                return

            # Copy the valid theme file to the user_themes folder
            dest_filename = os.path.basename(filepath)
            dest_path = os.path.join(self.user_themes_path, dest_filename)
            shutil.copy(filepath, dest_path)
            
            # Refresh the grid to show the new theme
            _, user_themes = self._load_themes()
            self._populate_grid_with_themes(self.user_themes_grid_layout, user_themes)
            showInfo("Theme imported successfully!")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Could not import the theme file:\n{e}")

    def _export_current_theme(self):
        """Gathers ALL current theme colors and saves them to a JSON file."""
        name, ok = QInputDialog.getText(self, "Export Theme", "Enter a name for your theme:")
        if not ok or not name:
            return

        light_palette = {}
        dark_palette = {}

        # The new logic: Iterate through the canonical list of theme keys for both modes.
        for mode, palette in [("light", light_palette), ("dark", dark_palette)]:
            for key in ALL_THEME_KEYS:
                # Default to the value in the in-memory config.
                # This is the safe fallback if the UI widget hasn't been created yet.
                value = self.current_config["colors"][mode].get(key)

                # If a UI widget for this key exists, use its value to capture last-minute edits.
                # This checks both the general color pills and the special-cased inputs.
                if key == "--accent-color" and hasattr(self, f"{mode}_accent_color_input"):
                    value = getattr(self, f"{mode}_accent_color_input").text()
                elif key == "--bg" and hasattr(self, f"bg_{mode}_color_input"):
                    value = getattr(self, f"bg_{mode}_color_input").text()
                elif key in self.color_widgets.get(mode, {}):
                    value = self.color_widgets[mode][key].text()
                
                # Assign the definitive value to the palette.
                if value is not None:
                    palette[key] = value

        theme_data = {"light": light_palette, "dark": dark_palette}

        # --- The rest of the function remains the same ---
        suggested_filename = name.lower().replace(" ", "_") + ".json"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Theme As",
            os.path.join(self.user_themes_path, suggested_filename),
            "JSON Files (*.json)"
        )

        if not save_path:
            return

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(theme_data, f, indent=4)
            showInfo(f"Theme '{name}' exported successfully!")

            if os.path.dirname(save_path) == self.user_themes_path:
                _, user_themes = self._load_themes()
                self._populate_grid_with_themes(self.user_themes_grid_layout, user_themes)

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
        if not checked:
            # Unchecking "Hide" unchecks "Pro" and "Max"
            self.pro_hide_checkbox.blockSignals(True)
            if self.pro_hide_checkbox.isChecked():
                self.pro_hide_checkbox.setChecked(False)
                self.pro_hide_checkbox._start_animation(False)
            self.pro_hide_checkbox.blockSignals(False)

            self.max_hide_checkbox.blockSignals(True)
            if self.max_hide_checkbox.isChecked():
                self.max_hide_checkbox.setChecked(False)
                self.max_hide_checkbox._start_animation(False)
            self.max_hide_checkbox.blockSignals(False)

    def _on_pro_hide_toggled(self, checked):
        if checked:
            # Checking "Pro" checks "Hide"
            self.hide_native_header_checkbox.blockSignals(True)
            if not self.hide_native_header_checkbox.isChecked():
                self.hide_native_header_checkbox.setChecked(True)
                self.hide_native_header_checkbox._start_animation(True)
            self.hide_native_header_checkbox.blockSignals(False)
        else:
            # Unchecking "Pro" unchecks "Max"
            self.max_hide_checkbox.blockSignals(True)
            if self.max_hide_checkbox.isChecked():
                self.max_hide_checkbox.setChecked(False)
                self.max_hide_checkbox._start_animation(False)
            self.max_hide_checkbox.blockSignals(False)

    def _on_max_hide_toggled(self, checked):
        if checked:
            # Checking "Max" checks "Pro" and "Hide"
            self.pro_hide_checkbox.blockSignals(True)
            if not self.pro_hide_checkbox.isChecked():
                self.pro_hide_checkbox.setChecked(True)
                self.pro_hide_checkbox._start_animation(True)
            self.pro_hide_checkbox.blockSignals(False)
            
            self.hide_native_header_checkbox.blockSignals(True)
            if not self.hide_native_header_checkbox.isChecked():
                self.hide_native_header_checkbox.setChecked(True)
                self.hide_native_header_checkbox._start_animation(True)
            self.hide_native_header_checkbox.blockSignals(False)
    # <<< END NEW CODE >>>

    def _save_hide_modes_settings(self):
        self.current_config.update({
            "hideNativeHeaderAndBottomBar": self.hide_native_header_checkbox.isChecked(),
            "proHide": self.pro_hide_checkbox.isChecked(),
            "maxHide": self.max_hide_checkbox.isChecked(),
        })

    def _save_overviews_settings(self):
        # --- NEW: Save the selected overview style ---
        if self.overview_mini_radio.isChecked():
            mw.col.conf["onigiri_overview_style"] = "mini"
        else:
            mw.col.conf["onigiri_overview_style"] = "pro"
        # --- END NEW ---

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
        self.current_config["hideProfileBar"] = self.hide_profile_bar_checkbox.isChecked()
        self.current_config["hideDeckCounts"] = self.hide_deck_counts_checkbox.isChecked()
        
        for widget in self.action_button_icon_widgets:
            key = widget.property("icon_key")
            value = widget.property("icon_filename")
            config_key = f"modern_menu_icon_{key}"
            if value:
                mw.col.conf[config_key] = value
            elif config_key in mw.col.conf:
                del mw.col.conf[config_key]

        for widget in self.icon_assignment_widgets:
            key = widget.property("icon_key")
            value = widget.property("icon_filename")
            config_key = f"modern_menu_icon_{key}"
            if value:
                mw.col.conf[config_key] = value
            elif config_key in mw.col.conf:
                del mw.col.conf[config_key]

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

    def _save_main_menu_settings(self):
        mw.col.conf["modern_menu_statsTitle"] = self.stats_title_input.text()
        
        if hasattr(self, "selected_heatmap_shape"):
            self.current_config["heatmapShape"] = self.selected_heatmap_shape
        
        self.current_config["heatmapShowStreak"] = self.heatmap_show_streak_check.isChecked()
        self.current_config["heatmapShowMonths"] = self.heatmap_show_months_check.isChecked()
        self.current_config["heatmapShowWeekdays"] = self.heatmap_show_weekdays_check.isChecked()
        self.current_config["heatmapShowWeekHeader"] = self.heatmap_show_week_header_check.isChecked()

        if hasattr(self, "retention_star_widget") and self.retention_star_widget:
            key = "retention_star"
            value = self.retention_star_widget.property("icon_filename")
            config_key = f"modern_menu_icon_{key}"
            if value:
                mw.col.conf[config_key] = value
            elif config_key in mw.col.conf:
                del mw.col.conf[config_key]

        stats_color_keys = ["--star-color", "--empty-star-color", "--heatmap-color", "--heatmap-color-zero"]
        for mode in ["light", "dark"]:
            for key in stats_color_keys:
                if key in self.color_widgets[mode]:
                    widget = self.color_widgets[mode][key]
                    self.current_config["colors"][mode][key] = widget.text()

    def _save_organize_settings(self):
        """Saves the layout from both the Onigiri and External layout editors."""
        if hasattr(self, 'onigiri_layout_editor'):
            self.current_config['onigiriWidgetLayout'] = self.onigiri_layout_editor.get_layout_config()
            
        if hasattr(self, 'external_layout_editor'):
            self.current_config['externalWidgetLayout'] = self.external_layout_editor.get_layout_config()

    def _save_profile_settings(self):
        self.current_config["userName"] = self.name_input.text()
        mw.col.conf["modern_menu_userName"] = self.name_input.text()

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
        else:
            mw.col.conf["onigiri_profile_page_bg_mode"] = "color"
            mw.col.conf["onigiri_profile_page_bg_light_color1"] = self.profile_page_light_color1_color_input.text()
            mw.col.conf["onigiri_profile_page_bg_dark_color1"] = self.profile_page_dark_color1_color_input.text()

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

        # --- START: Save Canvas Inset Effect Settings ---
        effect_mode = "none"
        if self.canvas_effect_opacity_radio.isChecked():
            effect_mode = "opacity"
        elif self.canvas_effect_glass_radio.isChecked():
            effect_mode = "glassmorphism"
        
        mw.col.conf["onigiri_canvas_inset_effect_mode"] = effect_mode
        mw.col.conf["onigiri_canvas_inset_effect_intensity"] = self.canvas_effect_intensity_spinbox.value()
        # --- END: Save Canvas Inset Effect Settings ---

    def _save_background_settings(self):
        if self.accent_radio.isChecked(): mw.col.conf["modern_menu_background_mode"] = "accent"
        elif self.image_color_radio.isChecked(): mw.col.conf["modern_menu_background_mode"] = "image_color"
        else: mw.col.conf["modern_menu_background_mode"] = "color"
        
        # Always use separate images for light and dark modes
        mw.col.conf["modern_menu_background_image_mode"] = "separate"
        
        if 'main_light' in self.galleries: mw.col.conf["modern_menu_background_image_light"] = self.galleries['main_light']['selected']
        if 'main_dark' in self.galleries: mw.col.conf["modern_menu_background_image_dark"] = self.galleries['main_dark']['selected']
        if 'sidebar_bg' in self.galleries: mw.col.conf["modern_menu_sidebar_bg_image"] = self.galleries['sidebar_bg']['selected']

        # --- START OF FIX ---
        # Get the new values from the UI input fields.
        light_bg_val = self.bg_light_color_input.text()
        dark_bg_val = self.bg_dark_color_input.text()

        # Update both storage locations to keep them synchronized.
        # 1. Update Anki's config for immediate use.
        mw.col.conf["modern_menu_bg_color_light"] = light_bg_val
        mw.col.conf["modern_menu_bg_color_dark"] = dark_bg_val
        
        # 2. CRITICAL: Update the main config dictionary so the change is
        #    saved permanently to config.json. This was the missing step.
        self.current_config["colors"]["light"]["--bg"] = light_bg_val
        self.current_config["colors"]["dark"]["--bg"] = dark_bg_val
        # --- END OF FIX ---

        mw.col.conf["modern_menu_background_blur"] = self.bg_blur_spinbox.value()
        mw.col.conf["modern_menu_background_opacity"] = self.bg_opacity_spinbox.value()
        
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

        # ðŸ”½ Opacity and Transparency ðŸ”½
        mw.col.conf["modern_menu_sidebar_bg_opacity"] = self.sidebar_bg_opacity_spinbox.value()
        mw.col.conf["modern_menu_sidebar_bg_transparency"] = self.sidebar_bg_transparency_spinbox.value()

    def _save_reviewer_settings(self):
        # --- Reviewer Background ---
        if self.reviewer_bg_main_radio.isChecked():
            self.current_config["onigiri_reviewer_bg_mode"] = "main"
        elif self.reviewer_bg_color_radio.isChecked():
            self.current_config["onigiri_reviewer_bg_mode"] = "color"
        elif self.reviewer_bg_image_color_radio.isChecked():
            self.current_config["onigiri_reviewer_bg_mode"] = "image_color"
        
        # Main background blur and opacity
        self.current_config["onigiri_reviewer_bg_main_blur"] = self.reviewer_bg_main_blur_spinbox.value()
        self.current_config["onigiri_reviewer_bg_main_opacity"] = self.reviewer_bg_main_opacity_spinbox.value()
        
        self.current_config["onigiri_reviewer_bg_light_color"] = self.reviewer_bg_light_color_input.text()
        self.current_config["onigiri_reviewer_bg_dark_color"] = self.reviewer_bg_dark_color_input.text()
        self.current_config["onigiri_reviewer_bg_blur"] = self.reviewer_bg_blur_spinbox.value()
        self.current_config["onigiri_reviewer_bg_opacity"] = self.reviewer_bg_opacity_spinbox.value()
        
        # Image selections (always use separate images for light and dark modes)
        if 'reviewer_bg_light' in self.galleries:
            self.current_config["onigiri_reviewer_bg_image_light"] = self.galleries['reviewer_bg_light']['selected']
        if 'reviewer_bg_dark' in self.galleries:
            self.current_config["onigiri_reviewer_bg_image_dark"] = self.galleries['reviewer_bg_dark']['selected']
        
        # --- Bottom Bar ---
        mw.col.conf["onigiri_reviewer_bottom_bar_bg_mode"] = self.reviewer_bottom_bar_mode
        mw.col.conf["onigiri_reviewer_bottom_bar_match_main_blur"] = self.reviewer_bar_match_main_blur_spinbox.value()
        mw.col.conf["onigiri_reviewer_bottom_bar_match_main_opacity"] = self.reviewer_bar_match_main_opacity_spinbox.value()
        mw.col.conf["onigiri_reviewer_bottom_bar_bg_light_color"] = self.reviewer_bar_light_color_input.text()
        mw.col.conf["onigiri_reviewer_bottom_bar_bg_dark_color"] = self.reviewer_bar_dark_color_input.text()
        mw.col.conf["onigiri_reviewer_bottom_bar_bg_blur"] = self.reviewer_bar_blur_spinbox.value()
        mw.col.conf["onigiri_reviewer_bottom_bar_bg_opacity"] = self.reviewer_bar_opacity_spinbox.value()
        if 'reviewer_bar_bg' in self.galleries:
            mw.col.conf["onigiri_reviewer_bottom_bar_bg_image"] = self.galleries['reviewer_bar_bg']['selected']

        mw.col.conf["onigiri_reviewer_bottom_bar_bg_offset_x"] = str(self.reviewer_bar_offset_spinbox.value())

    def save_settings(self):
        page_indices = {name: i for i, name in enumerate(self.page_order)}

        if self.tabs_loaded.get(page_indices.get("Hide modes")):
            self._save_hide_modes_settings()
        if self.tabs_loaded.get(page_indices.get("Main menu")):
            self._save_main_menu_settings()
            self._save_organize_settings()
        if self.tabs_loaded.get(page_indices.get("Sidebar")):
            self._save_sidebar_settings()
        if self.tabs_loaded.get(page_indices.get("Overviews")):
            self._save_overviews_settings()
        if self.tabs_loaded.get(page_indices.get("Fonts")): # <<< ADD THIS IF BLOCK
            self._save_fonts_settings()
        if self.tabs_loaded.get(page_indices.get("Profile")):
            self._save_profile_settings()
        if self.tabs_loaded.get(page_indices.get("Palette")):
            self._save_colors_settings()
        if self.tabs_loaded.get(page_indices.get("Backgrounds")):
            self._save_background_settings()
        if self.tabs_loaded.get(page_indices.get("Reviewer")):
            self._save_reviewer_settings()

        # <<< THIS IS THE FIX: Manually save the theme's background color if the Backgrounds tab was never opened. >>>
        if not self.tabs_loaded.get(page_indices.get("Backgrounds")):
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
