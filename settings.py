import os
import shutil
import urllib.parse
import json
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QDialogButtonBox, QWidget, QTabWidget, QColorDialog, QColor, QCheckBox,
    QGroupBox, QRadioButton, QFileDialog, QSpinBox, QFormLayout, QScrollArea,
    QGridLayout, QPixmap, Qt, QEvent, QPainter, QPainterPath, QMessageBox,
    QListWidget, QStackedWidget, QListWidgetItem, QFrame, QSizePolicy,
    QIcon, QPen, QBrush, QInputDialog, QAbstractButton
)
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtProperty, QPointF
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl, QPropertyAnimation, QEasingCurve
from aqt import mw
from aqt.theme import theme_manager

from . import config
from .config import DEFAULTS
from .constants import COLOR_LABELS, CATPPUCCIN_THEMES, COMMUNITY_THEMES, ICON_DEFAULTS, DEFAULT_ICON_SIZES

THUMBNAIL_STYLE = "QLabel { border: 2px solid transparent; border-radius: 10px; } QLabel:hover { border: 2px solid #007bff; }"
THUMBNAIL_STYLE_SELECTED = "QLabel { border: 2px solid #007bff; border-radius: 10px; }"

def create_rounded_pixmap(source_pixmap, radius):
    if source_pixmap.isNull(): return QPixmap()
    rounded = QPixmap(source_pixmap.size()); rounded.fill(Qt.GlobalColor.transparent)
    painter = QPainter(rounded); painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath(); path.addRoundedRect(0, 0, source_pixmap.width(), source_pixmap.height(), radius, radius)
    painter.setClipPath(path); painter.drawPixmap(0, 0, source_pixmap); painter.end()
    return rounded

class ThumbnailWorker(QObject):
    thumbnail_ready = pyqtSignal(str, int, QPixmap, str)
    finished = pyqtSignal()

    def __init__(self, key, full_folder_path, image_files):
        super().__init__()
        self.key = key
        self.full_folder_path = full_folder_path
        self.image_files = image_files
        self.is_cancelled = False

    def run(self):
        for index, filename in enumerate(self.image_files):
            if self.is_cancelled:
                break
            try:
                pixmap_path = os.path.join(self.full_folder_path, filename)
                if filename.lower().endswith(".svg"):
                    renderer = QSvgRenderer(pixmap_path)
                    if not renderer.isValid(): continue
                    pixmap = QPixmap(renderer.defaultSize()); pixmap.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(pixmap); renderer.render(painter); painter.end()
                else:
                    pixmap = QPixmap(pixmap_path)
                
                if not pixmap.isNull():
                    final_pixmap = create_rounded_pixmap(pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation), 10)
                    self.thumbnail_ready.emit(self.key, index, final_pixmap, filename)
            except Exception:
                pass
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
    """
    A custom animated toggle button widget that mimics the appearance of modern UI toggles.
    It uses QPropertyAnimation for a smooth transition between on and off states.
    The 'on' state color is determined by the provided accent_color.
    """
    def __init__(self, parent=None, accent_color="#007bff"):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.accent_color = QColor(accent_color)
        self.track_color_off = QColor("#cccccc") if not theme_manager.night_mode else QColor("#555555")
        self.thumb_color = QColor("#ffffff")
        
        # Set fixed size for a consistent look
        self.setFixedSize(38, 20)
        
        # This property will be animated
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
        self.update() # Trigger a repaint on property change

    def _start_animation(self, checked):
        """Starts the thumb animation when the button is toggled."""
        # Calculate the end position for the thumb
        end_pos = self.width() - self.height() + 3 if checked else 3
        self.animation.setStartValue(self.thumb_x_pos)
        self.animation.setEndValue(end_pos)
        self.animation.start()

    def paintEvent(self, event):
        """Custom paint event to draw the toggle switch."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        height = self.height()
        radius = height / 2.0
        
        # 1. Paint Track
        painter.setPen(Qt.PenStyle.NoPen)
        track_color = self.accent_color if self.isChecked() else self.track_color_off
        painter.setBrush(track_color)
        painter.drawRoundedRect(self.rect(), radius, radius)

        # 2. Paint Thumb
        thumb_radius = radius - 3
        painter.setBrush(self.thumb_color)
        painter.setPen(Qt.PenStyle.NoPen)
        
        # The thumb's y-position is fixed in the center
        thumb_y = radius
        # The thumb's x-position is animated via self.thumb_x_pos
        painter.drawEllipse(QPointF(self._thumb_x_pos + thumb_radius, thumb_y), thumb_radius, thumb_radius)

    def showEvent(self, event):
        """Set the initial thumb position when the widget is first shown."""
        super().showEvent(event)
        # Set initial position without animation
        self._thumb_x_pos = self.width() - self.height() + 3 if self.isChecked() else 3
        self.update()

    def resizeEvent(self, event):
        """Recalculate thumb position on resize."""
        super().resizeEvent(event)
        self._thumb_x_pos = self.width() - self.height() + 3 if self.isChecked() else 3
        self.update()

class SectionGroup(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(0, 5, 0, 0) # Removed extra space between sections

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        main_layout.addWidget(title_label)

        self.content_area = QWidget()
        self.content_area.setObjectName("innerGroup") # Reuse styling for the bordered box
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(10)
        main_layout.addWidget(self.content_area)

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)

class SettingsDialog(QDialog):
    def __init__(self, parent=None, addon_path=None, initial_page_index=0):
        super().__init__(parent)
        self.addon_path = addon_path
        self.user_themes_path = os.path.join(self.addon_path, "user_files", "user_themes")
        os.makedirs(self.user_themes_path, exist_ok=True)
        self.block_card_click = False
        
        self.setWindowTitle("Onigiri Settings")
        self.setMinimumWidth(850)
        self.setMinimumHeight(self.parent().screen().availableGeometry().height() - 55)
        
        self.current_config = config.get_config()
        self.color_widgets = {"light": {}, "dark": {}}
        self.icon_assignment_widgets = []
        self.icon_size_widgets = {}
        self.galleries = {}
        self.tabs_loaded = {}

        # Calculate accent color for toggle buttons before creating pages
        conf = config.get_config()
        if theme_manager.night_mode:
            self.accent_color = conf.get("colors", {}).get("dark", {}).get("--accent-color", DEFAULTS["colors"]["dark"]["--accent-color"])
        else:
            self.accent_color = conf.get("colors", {}).get("light", {}).get("--accent-color", DEFAULTS["colors"]["light"]["--accent-color"])

        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0)
        
        content_area_layout = QHBoxLayout()
        content_area_layout.setSpacing(0)
        content_area_layout.setContentsMargins(0, 0, 0, 0)
        
        sidebar_container = QWidget(); sidebar_container.setObjectName("sidebarContainer")
        sidebar_container.setFixedWidth(160) # Fixed width, no more splitter
        sidebar_layout = QVBoxLayout(sidebar_container); sidebar_layout.setContentsMargins(0, 20, 0, 10); sidebar_layout.setSpacing(10); sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.sidebar = QListWidget(); self.content_stack = QStackedWidget(); self.content_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sidebar_layout.addWidget(self.sidebar)
        
        content_area_layout.addWidget(sidebar_container)
        content_area_layout.addWidget(self.content_stack)

        self.pages = {
            "General": self.create_general_tab, "Profile": self.create_profile_tab, "Colors": self.create_colors_page,
            "Background": self.create_background_page, "Heatmap": self.create_heatmap_tab, "Icons": self.create_icons_tab,
        }
        for name in self.pages.keys():
            self.content_stack.addWidget(QWidget())
            list_item = QListWidgetItem(name, self.sidebar)
            size = list_item.sizeHint(); size.setHeight(size.height() + 10); list_item.setSizeHint(size)

        self.sidebar.currentRowChanged.connect(self.on_sidebar_selection_changed)
        safe_index = initial_page_index if 0 <= initial_page_index < self.sidebar.count() else 0
        self.sidebar.setCurrentRow(safe_index)
        self.on_sidebar_selection_changed(safe_index)
        
        self.save_button = QPushButton("Save"); self.save_button.clicked.connect(self.save_settings)
        self.cancel_button = QPushButton("Cancel"); self.cancel_button.clicked.connect(self.reject)
        
        sidebar_button_layout = QVBoxLayout()
        sidebar_button_layout.setSpacing(5)
        sidebar_button_layout.setContentsMargins(8, 10, 8, 0)
        sidebar_button_layout.addWidget(self.save_button)
        sidebar_button_layout.addWidget(self.cancel_button)

        sidebar_layout.addStretch()
        sidebar_layout.addLayout(sidebar_button_layout)

        main_layout.addLayout(content_area_layout)
        self.apply_stylesheet()

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
    
    def on_sidebar_selection_changed(self, index):
        if not self.tabs_loaded.get(index):
            page_name = self.sidebar.item(index).text()
            create_func = self.pages[page_name]
            new_widget = create_func()
            
            old_widget = self.content_stack.widget(index)
            self.content_stack.removeWidget(old_widget)
            self.content_stack.insertWidget(index, new_widget)
            old_widget.deleteLater()
            self.tabs_loaded[index] = True
        
        self.content_stack.setCurrentIndex(index)

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
            bg, fg, border, input_bg, button_bg, sidebar_bg = "#ffffff", "#212121", "#e0e0e0", "#f5f5f5", "#f0f0f0", "#f0f0f0"
            separator_color, secondary_button_bg, secondary_button_fg = "#e0e0e0", "#c9c9c9", "#ffffff"
            accent_color = conf.get("colors", {}).get("light", {}).get("--accent-color", DEFAULTS["colors"]["light"]["--accent-color"])

        sidebar_selected_bg, primary_button_bg = accent_color, accent_color
        self.setStyleSheet(f"""
            QDialog {{ background-color: {bg}; color: {fg}; }}
            #sidebarContainer {{ background-color: {sidebar_bg}; }}
            #innerGroup {{ border: 1px solid {border}; border-radius: 12px; margin-top: 5px; }}
            QListWidget {{ background-color: {sidebar_bg}; border: none; padding-top: 10px; outline: 0; }}
            QListWidget::item {{ padding: 12px; margin: 4px 8px; border-radius: 6px; }}
            QListWidget::item:selected {{ background-color: {sidebar_selected_bg}; color: white; }}
            QGroupBox {{ border-radius: 16px; margin-top: 8px; padding: 0px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; color: transparent; }}
            QLabel, QRadioButton {{ color: {fg}; }}
            QLineEdit, QSpinBox {{ background-color: {input_bg}; color: {fg}; border: 1px solid {border}; border-radius: 4px; padding: 5px; }}
            QPushButton {{ background-color: {button_bg}; color: {fg}; border: 1px solid {border}; padding: 8px 12px; border-radius: 4px; }}
            QPushButton:pressed {{ background-color: {border}; }}
            QFrame[frameShape="4"] {{ border: 1px solid {separator_color}; }}
            QTabBar::tab {{ background: transparent; border: none; padding: 8px 12px; border-radius: 4px; margin-right: 2px; }}
            QTabBar::tab:selected {{ background: {accent_color}; color: white; }}
            QTabBar::tab:!selected:hover {{ background: {border}; }}
            QTabWidget::pane {{ background-color: transparent; border: none; }}
            QTabBar {{ qproperty-drawBase: 0; }}
            QScrollBar:vertical {{ border: none; background: {sidebar_bg}; width: 10px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {border}; min-height: 20px; border-radius: 5px; }}
            QScrollBar:horizontal {{ border: none; background: {sidebar_bg}; height: 10px; margin: 0; }}
            QScrollBar::handle:horizontal {{ background: {border}; min-width: 20px; border-radius: 5px; }}
            #colorPill {{ background-color: {input_bg}; border: 1px solid {border}; border-radius: 17px; padding: 0px; }}
        """)
        self.save_button.setStyleSheet(f"QPushButton{{background-color:{primary_button_bg};color:white;border:none;padding:10px;border-radius:6px;font-weight:bold}}QPushButton:pressed{{background-color:{sidebar_selected_bg}}}")
        self.cancel_button.setStyleSheet(f"QPushButton{{background-color:{secondary_button_bg};color:{secondary_button_fg};border:none;padding:10px;border-radius:6px}}QPushButton:pressed{{background-color:{border}}}")

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

    def create_general_tab(self):
        page = QWidget(); layout = QVBoxLayout(page)
        
        # Customize Names

        user_section = SectionGroup("User Settings", self)
        form_layout = QFormLayout(); form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.name_input = QLineEdit(self.current_config.get("userName", DEFAULTS["userName"])); form_layout.addRow("User Name:", self.name_input)
        self.stats_title_input = QLineEdit(mw.col.conf.get("modern_menu_statsTitle", DEFAULTS["statsTitle"])); form_layout.addRow("Custom Stats Title:", self.stats_title_input)
        self.study_now_input = QLineEdit(mw.col.conf.get("modern_menu_studyNowText", DEFAULTS["studyNowText"])); form_layout.addRow("Custom 'Study Now' Text:", self.study_now_input)
        user_section.add_layout(form_layout)
        
        display_section = SectionGroup("Display Options", self)
        
        # Hide Welcome, Profile, Studied Today Text

        self.hide_welcome_checkbox = AnimatedToggleButton(accent_color=self.accent_color); self.hide_welcome_checkbox.setChecked(self.current_config.get("hideWelcomeMessage", False)); display_section.add_widget(self._create_toggle_row(self.hide_welcome_checkbox, "Hide 'Welcome' message"))
        self.hide_profile_bar_checkbox = AnimatedToggleButton(accent_color=self.accent_color); self.hide_profile_bar_checkbox.setChecked(self.current_config.get("hideProfileBar", False)); display_section.add_widget(self._create_toggle_row(self.hide_profile_bar_checkbox, "Hide profile bar"))
        self.hide_studied_checkbox = AnimatedToggleButton(accent_color=self.accent_color); self.hide_studied_checkbox.setChecked(self.current_config.get("hideStudiedToday", False)); display_section.add_widget(self._create_toggle_row(self.hide_studied_checkbox, "Hide 'Studied Today' text on main screen"))

        # Hide Heatmap
        
        self.hide_heatmap_on_main_checkbox = AnimatedToggleButton(accent_color=self.accent_color)    
        self.hide_heatmap_on_main_checkbox.setChecked(self.current_config.get("hideHeatmapOnMain", False))
        display_section.add_widget(self._create_toggle_row(self.hide_heatmap_on_main_checkbox, "Hide heatmap on main screen"))
        
        # Hide Today's Stats 
        self.hide_stats_checkbox = AnimatedToggleButton(accent_color=self.accent_color); self.hide_stats_checkbox.setChecked(self.current_config.get("hideTodaysStats", False)); display_section.add_widget(self._create_toggle_row(self.hide_stats_checkbox, "Hide 'Today's Stats' grid on main screen"))
        self.hide_stats_checkbox.toggled.connect(self._on_hide_all_stats_toggled)

        # 'Studied' card toggle
        self.hide_studied_stat_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_studied_stat_checkbox.setChecked(self.current_config.get("hideStudiedStat", False))
        display_section.add_widget(self._create_toggle_row(self.hide_studied_stat_checkbox, "Hide 'Studied' card", "padding-left: 20px;"))

        # 'Time' card toggle
        self.hide_time_stat_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_time_stat_checkbox.setChecked(self.current_config.get("hideTimeStat", False))
        display_section.add_widget(self._create_toggle_row(self.hide_time_stat_checkbox, "Hide 'Time' card", "padding-left: 20px;"))

        # 'Pace' card toggle
        self.hide_pace_stat_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_pace_stat_checkbox.setChecked(self.current_config.get("hidePaceStat", False))
        display_section.add_widget(self._create_toggle_row(self.hide_pace_stat_checkbox, "Hide 'Pace' card", "padding-left: 20px;"))

        # 'Retention' card toggle
        self.hide_retention_stat_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_retention_stat_checkbox.setChecked(self.current_config.get("hideRetentionStat", False))
        display_section.add_widget(self._create_toggle_row(self.hide_retention_stat_checkbox, "Hide 'Retention' card", "padding-left: 20px;"))

        # Hide modes
        
        self.hide_native_header_checkbox = AnimatedToggleButton(accent_color=self.accent_color); self.hide_native_header_checkbox.setChecked(self.current_config.get("hideNativeHeaderAndBottomBar", False)); display_section.add_widget(self._create_toggle_row(self.hide_native_header_checkbox, "Hide mode"))
        desc_label = QLabel("Hides top and bottom toolbar completely on the main screen, on overview you have a modern toolbar and in reviewer you use Anki's native toolbar"); desc_label.setStyleSheet("font-size: 11px; color: #888; padding-left: 20px;"); display_section.add_widget(desc_label)
        self.ultra_hide_checkbox = AnimatedToggleButton(accent_color=self.accent_color); self.ultra_hide_checkbox.setChecked(self.current_config.get("UltraHide", False)); self.ultra_hide_checkbox.setToolTip("Hides the modern toolbar on overview and the native toolbar on reviewer."); display_section.add_widget(self._create_toggle_row(self.ultra_hide_checkbox, "Ultra hide mode", "padding-left: 20px;"))
        ultra_desc_label = QLabel("Hides the modern toolbar on the overview screen and the native toolbar on the reviewer screen, an absolute immersive experiense. You will need to use keyboard shortcuts to navigate, be advised!"); ultra_desc_label.setWordWrap(True); ultra_desc_label.setStyleSheet("font-size: 11px; color: #888; padding-left: 40px;"); display_section.add_widget(ultra_desc_label)
        
        self.hide_native_header_checkbox.toggled.connect(self.ultra_hide_checkbox.setEnabled); self.ultra_hide_checkbox.setEnabled(self.hide_native_header_checkbox.isChecked())

        congrats_section = SectionGroup("Congrats Page Options", self)
        congrats_form_layout = QFormLayout()
        self.show_congrats_profile_bar_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.show_congrats_profile_bar_checkbox.setChecked(self.current_config.get("showCongratsProfileBar", True))
        congrats_form_layout.addRow(self._create_toggle_row(self.show_congrats_profile_bar_checkbox, "Show profile bar on congrats screen"))
        
        self.congrats_message_input = QLineEdit(self.current_config.get("congratsMessage", DEFAULTS["congratsMessage"]))
        congrats_form_layout.addRow("Custom Message:", self.congrats_message_input)
        congrats_section.add_layout(congrats_form_layout)

        layout.addWidget(user_section); layout.addWidget(display_section); layout.addWidget(congrats_section); layout.addStretch(); return page

    def create_profile_tab(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(15)
        
        pic_section = SectionGroup("Profile Picture", self)
        pic_section.add_widget(self._create_image_gallery_placeholder("profile_pic", "user_files/profile", "modern_menu_profile_picture"))
        layout.addWidget(pic_section)
        
        bg_section = SectionGroup("Profile Bar Background", self)
        bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "accent")
        mode_layout = QHBoxLayout(); self.profile_bg_accent_radio = QRadioButton("Accent Color"); self.profile_bg_custom_radio = QRadioButton("Custom Color"); self.profile_bg_image_radio = QRadioButton("Image")
        self.profile_bg_accent_radio.setChecked(bg_mode == "accent"); self.profile_bg_custom_radio.setChecked(bg_mode == "custom"); self.profile_bg_image_radio.setChecked(bg_mode == "image")
        mode_layout.addWidget(self.profile_bg_accent_radio); mode_layout.addWidget(self.profile_bg_custom_radio); mode_layout.addWidget(self.profile_bg_image_radio); mode_layout.addStretch(); bg_section.add_layout(mode_layout)
        
        self.profile_bg_color_group = QWidget(); custom_color_layout = QVBoxLayout(self.profile_bg_color_group); custom_color_layout.setContentsMargins(0, 10, 0, 0)
        self.profile_bg_light_row = self._create_color_picker_row("Light Mode", mw.col.conf.get("modern_menu_profile_bg_color_light", "#EEEEEE"), "profile_bg_light"); custom_color_layout.addLayout(self.profile_bg_light_row)
        self.profile_bg_dark_row = self._create_color_picker_row("Dark Mode", mw.col.conf.get("modern_menu_profile_bg_color_dark", "#3C3C3C"), "profile_bg_dark"); custom_color_layout.addLayout(self.profile_bg_dark_row); bg_section.add_widget(self.profile_bg_color_group)

        self.profile_bg_image_group = self._create_image_gallery_placeholder("profile_bg", "user_files/profile_bg", "modern_menu_profile_bg_image", is_sub_group=True); bg_section.add_widget(self.profile_bg_image_group); layout.addWidget(bg_section)
        
        self.profile_bg_accent_radio.toggled.connect(self.toggle_profile_bg_options); self.profile_bg_custom_radio.toggled.connect(self.toggle_profile_bg_options); self.profile_bg_image_radio.toggled.connect(self.toggle_profile_bg_options)
        self.toggle_profile_bg_options()

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
        
        accent_group, accent_layout = self._create_inner_group("Accent Color")
        light_accent = self.current_config.get("colors", {}).get("light", {}).get("--accent-color", DEFAULTS["colors"]["light"]["--accent-color"])
        dark_accent = self.current_config.get("colors", {}).get("dark", {}).get("--accent-color", DEFAULTS["colors"]["dark"]["--accent-color"])
        accent_layout.addLayout(self._create_color_picker_row("Light Mode Accent", light_accent, "light_accent", tooltip_text="The main color for buttons and selections in light mode."))
        accent_layout.addLayout(self._create_color_picker_row("Dark Mode Accent", dark_accent, "dark_accent", tooltip_text="The main color for buttons and selections in dark mode."))
        layout.addWidget(accent_group)

        color_modes_layout = QHBoxLayout()
        light_colors_group, light_colors_layout = self._create_inner_group("Light Mode Colors")
        self._populate_color_section(light_colors_layout, "light")
        color_modes_layout.addWidget(light_colors_group)

        dark_colors_group, dark_colors_layout = self._create_inner_group("Dark Mode Colors")
        self._populate_color_section(dark_colors_layout, "dark")
        color_modes_layout.addWidget(dark_colors_group)
        layout.addLayout(color_modes_layout)

        # --- Catppuccin Themes Section ---
        catppuccin_group = QGroupBox()
        catppuccin_group.setToolTip("Click a theme name to apply it. Click the logo to visit the theme's website.")
        catppuccin_main_layout = QVBoxLayout(catppuccin_group)
        catppuccin_main_layout.setContentsMargins(10, 10, 10, 10)

        catppuccin_title_bar = QHBoxLayout()
        catppuccin_title = QLabel("Catppuccin Themes")
        catppuccin_title.setStyleSheet("font-weight: bold;")
        catppuccin_title_bar.addWidget(catppuccin_title)
        catppuccin_title_bar.addStretch()
        
        meta_data = CATPPUCCIN_THEMES.get("meta", {})
        if meta_data:
            logo_button = QPushButton()
            logo_button.setCursor(Qt.CursorShape.PointingHandCursor)
            logo_path = os.path.join(self.addon_path, "user_files/theme_logos", meta_data["logo_file"])
            
            icon = QIcon(logo_path)
            if not icon.isNull():
                logo_button.setIcon(icon)
            else:
                logo_button.setText("C")
                print(f"Onigiri settings: Could not find or load theme icon at '{logo_path}'")

            logo_button.setFixedSize(28, 28)
            logo_button.setIconSize(logo_button.size() * 0.85)
            logo_button.setToolTip("Visit the Catppuccin theme website")
            logo_button.setStyleSheet("QPushButton { border: none; border-radius: 14px; background-color: transparent; } QPushButton:hover { background-color: rgba(128, 128, 128, 0.2); }")
            logo_button.clicked.connect(lambda _, url=meta_data["url"]: self._open_external_link(url))
            catppuccin_title_bar.addWidget(logo_button)

        catppuccin_main_layout.addLayout(catppuccin_title_bar)
        
        catppuccin_grid_layout = QGridLayout()
        catppuccin_grid_layout.setSpacing(10)
        catppuccin_grid_layout.setContentsMargins(0, 10, 0, 0)
        row, col = 0, 0
        for theme_key, theme_data in CATPPUCCIN_THEMES.items():
            if theme_key == "meta":
                continue
            card = QPushButton(); card.setMinimumHeight(80)
            card_layout = QVBoxLayout(card)
            
            title_bar_card = QHBoxLayout()
            title_bar_card.setSpacing(6)
            title_bar_card.setAlignment(Qt.AlignmentFlag.AlignLeft)
            title_label_card = QLabel(theme_data["name"])
            title_label_card.setStyleSheet("font-weight: bold;")
            title_bar_card.addWidget(title_label_card)
            tags_widget = self._create_mode_tags(theme_data)
            title_bar_card.addWidget(tags_widget)
            card_layout.addLayout(title_bar_card)

            swatch_container = QWidget()
            swatch_layout = QHBoxLayout(swatch_container)
            swatch_layout.setContentsMargins(0, 5, 0, 0)
            swatch_layout.setSpacing(5)
            for color_hex in theme_data["preview"]:
                swatch = QFrame()
                swatch.setFixedSize(20, 20)
                swatch.setStyleSheet(f"background-color: {color_hex}; border-radius: 10px; border: 1px solid rgba(0,0,0,0.1);")
                swatch_layout.addWidget(swatch)
            swatch_layout.addStretch()
            card_layout.addWidget(swatch_container)
            card.clicked.connect(lambda _, name=theme_key: self.apply_catppuccin_theme(name))
            
            catppuccin_grid_layout.addWidget(card, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1
            
        catppuccin_main_layout.addLayout(catppuccin_grid_layout)
        layout.addWidget(catppuccin_group)

        # --- Community Themes Section ---
        community_group = QGroupBox()
        community_group.setToolTip("Click a theme name to apply it. Click a logo to visit the theme's website.")
        community_main_layout = QVBoxLayout(community_group)
        community_main_layout.setContentsMargins(10, 10, 10, 10)

        community_title_bar = QHBoxLayout()
        community_title = QLabel("Community Themes")
        community_title.setStyleSheet("font-weight: bold;")
        community_title_bar.addWidget(community_title)
        community_title_bar.addStretch()

        for theme_key, theme_data in COMMUNITY_THEMES.items():
            logo_button = QPushButton()
            logo_button.setCursor(Qt.CursorShape.PointingHandCursor)
            logo_path = os.path.join(self.addon_path, "user_files/theme_logos", theme_data["logo_file"])
            
            icon = QIcon(logo_path)
            if not icon.isNull():
                logo_button.setIcon(icon)
            else:
                logo_button.setText(theme_data["name"][0])
                print(f"Onigiri settings: Could not find or load theme icon at '{logo_path}'")
            
            logo_button.setFixedSize(28, 28)
            logo_button.setIconSize(logo_button.size() * 0.85)
            logo_button.setToolTip(f"Visit the {theme_data['name']} theme website")
            logo_button.setStyleSheet("QPushButton { border: none; border-radius: 14px; background-color: transparent; } QPushButton:hover { background-color: rgba(128, 128, 128, 0.2); }")
            logo_button.clicked.connect(lambda _, url=theme_data["url"]: self._open_external_link(url))
            community_title_bar.addWidget(logo_button)

        community_main_layout.addLayout(community_title_bar)
        
        community_grid_layout = QGridLayout()
        community_grid_layout.setSpacing(10)
        community_grid_layout.setContentsMargins(0, 10, 0, 0)
        row, col = 0, 0
        for theme_key, theme_data in COMMUNITY_THEMES.items():
            card = QPushButton(); card.setMinimumHeight(80)
            card_layout = QVBoxLayout(card)
            
            title_bar_card = QHBoxLayout()
            title_bar_card.setSpacing(6)
            title_bar_card.setAlignment(Qt.AlignmentFlag.AlignLeft)
            title_label_card = QLabel(theme_data["name"])
            title_label_card.setStyleSheet("font-weight: bold;")
            title_bar_card.addWidget(title_label_card)
            tags_widget = self._create_mode_tags(theme_data)
            title_bar_card.addWidget(tags_widget)
            card_layout.addLayout(title_bar_card)

            swatch_container = QWidget()
            swatch_layout = QHBoxLayout(swatch_container)
            swatch_layout.setContentsMargins(0, 5, 0, 0)
            swatch_layout.setSpacing(5)
            for color_hex in theme_data["preview"]:
                swatch = QFrame()
                swatch.setFixedSize(20, 20)
                swatch.setStyleSheet(f"background-color: {color_hex}; border-radius: 10px; border: 1px solid rgba(0,0,0,0.1);")
                swatch_layout.addWidget(swatch)
            swatch_layout.addStretch()
            card_layout.addWidget(swatch_container)
            card.clicked.connect(lambda _, name=theme_key: self.apply_community_theme(name))
            
            community_grid_layout.addWidget(card, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1
            
        community_main_layout.addLayout(community_grid_layout)
        layout.addWidget(community_group)

        # --- Your Themes Section ---
        self.your_themes_group = self._create_your_themes_section()
        layout.addWidget(self.your_themes_group)

        io_button_layout = QHBoxLayout()
        import_button = QPushButton("Import Theme...")
        import_button.clicked.connect(self.import_theme)
        export_button = QPushButton("Export Current Theme...")
        export_button.clicked.connect(self.export_theme)
        
        reset_theme_button = QPushButton("Reset Theme")
        reset_theme_button.setToolTip("Resets all colors and the background color to default, without changing the background image.")
        reset_theme_button.clicked.connect(self.reset_theme_to_default)

        reset_colors_button = QPushButton("Reset Colors to Default")
        reset_colors_button.setToolTip("Resets only the theme colors (accent, text, etc.) to default.")
        reset_colors_button.clicked.connect(self.reset_colors_to_default)

        io_button_layout.addWidget(import_button)
        io_button_layout.addWidget(export_button)
        io_button_layout.addStretch()
        io_button_layout.addWidget(reset_theme_button)
        io_button_layout.addWidget(reset_colors_button)
        layout.addLayout(io_button_layout)
        
        layout.addStretch()
        return page

    def _create_your_themes_section(self):
        group = QGroupBox()
        main_layout = QVBoxLayout(group)
        main_layout.setContentsMargins(10, 10, 10, 10)

        title_bar = QHBoxLayout()
        title = QLabel("Your Themes")
        title.setStyleSheet("font-weight: bold;")
        title_bar.addWidget(title)
        title_bar.addStretch()
        main_layout.addLayout(title_bar)

        self.your_themes_grid_layout = QGridLayout()
        self.your_themes_grid_layout.setSpacing(10)
        self.your_themes_grid_layout.setContentsMargins(0, 10, 0, 0)
        
        self._populate_your_themes()

        main_layout.addLayout(self.your_themes_grid_layout)
        return group

    def _populate_your_themes(self):
        # Clear existing widgets
        while self.your_themes_grid_layout.count():
            child = self.your_themes_grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        try:
            theme_files = [f for f in os.listdir(self.user_themes_path) if f.endswith('.json')]
        except OSError:
            theme_files = []

        if not theme_files:
            no_themes_label = QLabel("You haven't imported any themes yet.")
            no_themes_label.setStyleSheet("color: #888;")
            self.your_themes_grid_layout.addWidget(no_themes_label, 0, 0, 1, 2)
            return

        row, col = 0, 0
        for filename in sorted(theme_files):
            theme_path = os.path.join(self.user_themes_path, filename)
            try:
                with open(theme_path, 'r', encoding='utf-8') as f:
                    theme_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            card = QPushButton()
            card.setMinimumHeight(80)
            card.clicked.connect(lambda _, p=theme_path: self.apply_user_theme(p))
            
            card_outer_layout = QHBoxLayout(card)
            card_outer_layout.setContentsMargins(9,9,9,9)
            card_outer_layout.setSpacing(15)
            
            info_widget = QWidget()
            info_layout = QVBoxLayout(info_widget)
            info_layout.setContentsMargins(0,0,0,0)
            
            title_bar_card = QHBoxLayout()
            title_bar_card.setSpacing(6)
            title_bar_card.setAlignment(Qt.AlignmentFlag.AlignLeft)
            title_label = QLabel(theme_data.get("name", "Unnamed Theme"))
            title_label.setStyleSheet("font-weight: bold; background: transparent;")
            title_bar_card.addWidget(title_label)
            tags_widget = self._create_mode_tags(theme_data)
            title_bar_card.addWidget(tags_widget)
            info_layout.addLayout(title_bar_card)
            
            preview_colors = theme_data.get("preview", [])
            if preview_colors:
                swatch_container = QWidget()
                swatch_container.setStyleSheet("background: transparent;")
                swatch_layout = QHBoxLayout(swatch_container)
                swatch_layout.setContentsMargins(0, 5, 0, 0)
                swatch_layout.setSpacing(5)
                for color_hex in preview_colors[:7]: # Limit to 7 swatches
                    swatch = QFrame()
                    swatch.setFixedSize(20, 20)
                    swatch.setStyleSheet(f"background-color: {color_hex}; border-radius: 10px; border: 1px solid rgba(0,0,0,0.1);")
                    swatch_layout.addWidget(swatch)
                swatch_layout.addStretch()
                info_layout.addWidget(swatch_container)
            
            card_outer_layout.addWidget(info_widget)

            delete_btn_container = QWidget()
            delete_btn_container.setStyleSheet("background: transparent;")
            delete_btn_layout = QVBoxLayout(delete_btn_container)
            delete_btn_layout.setContentsMargins(0,0,0,0)
            delete_btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            
            delete_btn = QPushButton()
            delete_btn.setFixedSize(28, 28)
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.setToolTip("Delete this theme")
            delete_btn.setStyleSheet("QPushButton { background: transparent; border: none; }")

            icon_path = os.path.join(self.addon_path, "xmark.svg")
            if os.path.exists(icon_path):
                try:
                    with open(icon_path, 'r', encoding='utf-8') as f:
                        svg_data = f.read()
                    
                    if theme_manager.night_mode:
                        default_color = "#8e8e8e"
                        hover_color = "#e57373"
                    else:
                        default_color = "#555555"
                        hover_color = "#B71C1C"

                    delete_btn.setProperty("is_delete_theme_btn", True)
                    delete_btn.setProperty("svg_data", svg_data)
                    delete_btn.setProperty("default_color", default_color)
                    delete_btn.setProperty("hover_color", hover_color)
                    
                    self._update_delete_button_icon(delete_btn, default_color)
                    delete_btn.setIconSize(delete_btn.size() * 0.75)
                    delete_btn.installEventFilter(self)

                except Exception as e:
                    print(f"Onigiri: Failed to load or process xmark.svg: {e}")
                    delete_btn.setText("X") # Fallback
            else:
                delete_btn.setText("X") # Fallback

            delete_btn.clicked.connect(lambda _, p=theme_path: self.delete_user_theme(p))
            delete_btn_layout.addWidget(delete_btn)
            
            card_outer_layout.addWidget(delete_btn_container)

            self.your_themes_grid_layout.addWidget(card, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1

    def _update_delete_button_icon(self, button, color):
        svg_data = button.property("svg_data")
        if not svg_data: return
        
        if 'currentColor' in svg_data:
            colored_svg = svg_data.replace('currentColor', color)
        else:
            colored_svg = svg_data.replace('<svg', f'<svg fill="{color}"')
        
        icon = self._create_icon_from_svg(colored_svg)
        button.setIcon(icon)

    def _create_icon_from_svg(self, svg_data):
        renderer = QSvgRenderer(svg_data.encode('utf-8'))
        pixmap = QPixmap(renderer.defaultSize())
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def _open_external_link(self, url_string):
        """Opens a URL in the default web browser."""
        QDesktopServices.openUrl(QUrl(url_string))

    def create_background_page(self):
        page, layout = self._create_scrollable_page()
        
        user_files_path = os.path.join(self.addon_path, "user_files", "main_bg")
        os.makedirs(user_files_path, exist_ok=True)
        try:
            cached_user_files = sorted([f for f in os.listdir(user_files_path) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))])
        except OSError:
            cached_user_files = []

        mode_group, mode_layout_content = self._create_inner_group("Main Background Type")
        mode_layout = QHBoxLayout(); mode = mw.col.conf.get("modern_menu_background_mode", "color")
        self.color_radio = QRadioButton("Solid Color"); self.image_radio = QRadioButton("Image"); self.accent_radio = QRadioButton("Accent Color"); self.image_color_radio = QRadioButton("Color + Image")
        self.color_radio.setChecked(mode == "color"); self.image_radio.setChecked(mode == "image"); self.accent_radio.setChecked(mode == "accent"); self.image_color_radio.setChecked(mode == "image_color")
        mode_layout.addWidget(self.color_radio); mode_layout.addWidget(self.image_radio); mode_layout.addWidget(self.image_color_radio); mode_layout.addWidget(self.accent_radio); mode_layout.addStretch(); mode_layout_content.addLayout(mode_layout); layout.addWidget(mode_group)

        self.color_group, color_layout = self._create_inner_group("Main Color Options")
        self.bg_light_row = self._create_color_picker_row("Background (Light Mode)", mw.col.conf.get("modern_menu_bg_color_light", "#FFFFFF"), "bg_light"); color_layout.addLayout(self.bg_light_row)
        self.bg_dark_row = self._create_color_picker_row("Background (Dark Mode)", mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C"), "bg_dark"); color_layout.addLayout(self.bg_dark_row); layout.addWidget(self.color_group)

        self.image_group, image_options_layout = self._create_inner_group("Main Image Options")
        image_mode = mw.col.conf.get("modern_menu_background_image_mode", "single"); image_mode_layout = QHBoxLayout()
        self.bg_image_mode_single_radio = QRadioButton("Single Image for Both Modes"); self.bg_image_mode_separate_radio = QRadioButton("Separate Images for Light & Dark Mode")
        self.bg_image_mode_single_radio.setChecked(image_mode == "single"); self.bg_image_mode_separate_radio.setChecked(image_mode == "separate")
        image_mode_layout.addWidget(self.bg_image_mode_single_radio); image_mode_layout.addWidget(self.bg_image_mode_separate_radio); image_options_layout.addLayout(image_mode_layout)
        
        self.single_image_container = self._create_image_gallery_placeholder("main_single", "user_files/main_bg", "modern_menu_background_image", is_sub_group=True, image_files_cache=cached_user_files)
        image_options_layout.addWidget(self.single_image_container)
        
        self.separate_images_container = QWidget(); sep_layout = QHBoxLayout(self.separate_images_container); sep_layout.setContentsMargins(0, 10, 0, 0)
        sep_layout.addWidget(self._create_image_gallery_placeholder("main_light", "user_files/main_bg", "modern_menu_background_image_light", title="Light Mode Background", image_files_cache=cached_user_files))
        sep_layout.addWidget(self._create_image_gallery_placeholder("main_dark", "user_files/main_bg", "modern_menu_background_image_dark", title="Dark Mode Background", image_files_cache=cached_user_files))
        image_options_layout.addWidget(self.separate_images_container)

        effects_layout = QHBoxLayout(); self.bg_blur_label = QLabel("Background Blur:"); self.bg_blur_spinbox = QSpinBox(); self.bg_blur_spinbox.setMinimum(0); self.bg_blur_spinbox.setMaximum(100); self.bg_blur_spinbox.setSuffix(" %"); self.bg_blur_spinbox.setValue(mw.col.conf.get("modern_menu_background_blur", 0)); effects_layout.addWidget(self.bg_blur_label); effects_layout.addWidget(self.bg_blur_spinbox); self.bg_opacity_label = QLabel("Image Opacity:"); self.bg_opacity_spinbox = QSpinBox(); self.bg_opacity_spinbox.setMinimum(0); self.bg_opacity_spinbox.setMaximum(100); self.bg_opacity_spinbox.setSuffix(" %"); self.bg_opacity_spinbox.setValue(mw.col.conf.get("modern_menu_background_opacity", 100)); effects_layout.addWidget(self.bg_opacity_label); effects_layout.addWidget(self.bg_opacity_spinbox); effects_layout.addStretch(); image_options_layout.addLayout(effects_layout); layout.addWidget(self.image_group)

        sidebar_group, sidebar_layout = self._create_inner_group("Sidebar Background")
        sidebar_mode = mw.col.conf.get("modern_menu_sidebar_bg_mode", "main"); sidebar_mode_layout = QHBoxLayout()
        self.sidebar_bg_main_radio = QRadioButton("Use Main Background Settings"); self.sidebar_bg_custom_radio = QRadioButton("Use Custom Sidebar Background")
        self.sidebar_bg_main_radio.setChecked(sidebar_mode == "main"); self.sidebar_bg_custom_radio.setChecked(sidebar_mode == "custom"); sidebar_mode_layout.addWidget(self.sidebar_bg_main_radio); sidebar_mode_layout.addWidget(self.sidebar_bg_custom_radio); sidebar_layout.addLayout(sidebar_mode_layout)
        self.sidebar_custom_options_group = self.create_sidebar_custom_options(); sidebar_layout.addWidget(self.sidebar_custom_options_group); layout.addWidget(sidebar_group)

        self.color_radio.toggled.connect(self.toggle_background_options); self.image_radio.toggled.connect(self.toggle_background_options); self.accent_radio.toggled.connect(self.toggle_background_options); self.image_color_radio.toggled.connect(self.toggle_background_options)
        self.bg_image_mode_single_radio.toggled.connect(self.toggle_background_image_mode); self.sidebar_bg_main_radio.toggled.connect(self.toggle_sidebar_background_options)
        self.toggle_background_options(); self.toggle_background_image_mode(); self.toggle_sidebar_background_options()
        
        reset_bg_button = QPushButton("Reset Background to Default"); reset_bg_button.clicked.connect(self.reset_background_to_default); reset_bg_layout = QHBoxLayout(); reset_bg_layout.addStretch(); reset_bg_layout.addWidget(reset_bg_button); layout.addLayout(reset_bg_layout)
        
        layout.addStretch()
        return page

    def _populate_color_section(self, layout, mode):
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
        for name, label_info in local_color_labels.items():
            if name in ["--accent-color", "--bg"]: 
                continue

            default_value = DEFAULTS["colors"][mode].get(name, local_defaults.get(name))
            
            if default_value is not None:
                value = colors.get(name, default_value)
                pill_widget = self._create_color_pill(name, value, mode, label_info)
                layout.addWidget(pill_widget)
        layout.addStretch()

    def _create_color_pill(self, name, default_value, mode, label_info):
        widget = QFrame()
        widget.setObjectName("colorPill")
        widget.setToolTip(f"{label_info['label']}: {label_info['tooltip']}")
        # Mouse tracking is needed for the hover effect
        widget.setMouseTracking(True)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 15, 4)
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

        # Style the QLineEdit to look like a label, with a border on focus
        hex_input.setStyleSheet(f"""
            QLineEdit {{ 
                font-family: monospace; 
                background: transparent; 
                border: none; 
                color: {text_color};
                padding: 1px; /* Add padding to prevent text from being cut off with border */
            }}
            QLineEdit:focus {{
                border: 1px solid {border_color};
                border-radius: 3px;
                background: {focus_bg};
            }}
        """)
        
        # When user types in hex code, update the swatch
        hex_input.textChanged.connect(color_swatch.setColor)
        
        # When user is done editing, if they leave the widget, it should switch back to the label
        # The eventFilter handles this. We can also make it so pressing enter unfocuses.
        hex_input.returnPressed.connect(hex_input.clearFocus)
        
        # When swatch is clicked, open color picker
        color_swatch.clicked.connect(lambda _, le=hex_input, btn=color_swatch: self.open_color_picker(le, btn))

        min_width = max(name_label.fontMetrics().horizontalAdvance(label_info['label']), hex_input.fontMetrics().horizontalAdvance("#" + "W"*6)) + 12 # Add a bit more padding
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
        widget = QWidget(); layout = QVBoxLayout(widget); layout.setContentsMargins(0,10,0,0)
        type_mode = mw.col.conf.get("modern_menu_sidebar_bg_type", "color"); type_layout = QHBoxLayout()
        self.sidebar_bg_type_color_radio = QRadioButton("Solid Color"); self.sidebar_bg_type_image_radio = QRadioButton("Image"); self.sidebar_bg_type_accent_radio = QRadioButton("Accent Color"); self.sidebar_bg_type_image_color_radio = QRadioButton("Color + Image")
        self.sidebar_bg_type_color_radio.setChecked(type_mode == "color"); self.sidebar_bg_type_image_radio.setChecked(type_mode == "image"); self.sidebar_bg_type_accent_radio.setChecked(type_mode == "accent"); self.sidebar_bg_type_image_color_radio.setChecked(type_mode == "image_color")
        type_layout.addWidget(self.sidebar_bg_type_color_radio); type_layout.addWidget(self.sidebar_bg_type_image_radio); type_layout.addWidget(self.sidebar_bg_type_image_color_radio); type_layout.addWidget(self.sidebar_bg_type_accent_radio); type_layout.addStretch(); layout.addLayout(type_layout)

        self.sidebar_color_group = QWidget(); sidebar_color_layout = QVBoxLayout(self.sidebar_color_group); sidebar_color_layout.setContentsMargins(0, 10, 0, 0)
        self.sidebar_bg_light_row = self._create_color_picker_row("Color (Light Mode)", mw.col.conf.get("modern_menu_sidebar_bg_color_light", "#EEEEEE"), "sidebar_bg_light"); sidebar_color_layout.addLayout(self.sidebar_bg_light_row)
        self.sidebar_bg_dark_row = self._create_color_picker_row("Color (Dark Mode)", mw.col.conf.get("modern_menu_sidebar_bg_color_dark", "#3C3C3C"), "sidebar_bg_dark"); sidebar_color_layout.addLayout(self.sidebar_bg_dark_row); layout.addWidget(self.sidebar_color_group)

        self.sidebar_image_group = self._create_image_gallery_placeholder("sidebar_bg", "user_files/sidebar_bg", "modern_menu_sidebar_bg_image", is_sub_group=True)
        effects_layout = QHBoxLayout(); 
        self.sidebar_bg_blur_label = QLabel("Blur:"); self.sidebar_bg_blur_spinbox = QSpinBox(); self.sidebar_bg_blur_spinbox.setMinimum(0); self.sidebar_bg_blur_spinbox.setMaximum(100); self.sidebar_bg_blur_spinbox.setSuffix(" %"); self.sidebar_bg_blur_spinbox.setValue(mw.col.conf.get("modern_menu_sidebar_bg_blur", 0)); effects_layout.addWidget(self.sidebar_bg_blur_label); effects_layout.addWidget(self.sidebar_bg_blur_spinbox);
        self.sidebar_bg_opacity_label = QLabel("Opacity:"); self.sidebar_bg_opacity_spinbox = QSpinBox(); self.sidebar_bg_opacity_spinbox.setMinimum(0); self.sidebar_bg_opacity_spinbox.setMaximum(100); self.sidebar_bg_opacity_spinbox.setSuffix(" %"); self.sidebar_bg_opacity_spinbox.setValue(mw.col.conf.get("modern_menu_sidebar_bg_opacity", 100)); effects_layout.addWidget(self.sidebar_bg_opacity_label); effects_layout.addWidget(self.sidebar_bg_opacity_spinbox)
        effects_layout.addStretch()
        
        layout.addWidget(self.sidebar_image_group)

        image_options_container = QWidget()
        image_options_layout = QVBoxLayout(image_options_container)
        image_options_layout.addLayout(effects_layout)
        self.galleries['sidebar_bg']['effects_widget'] = image_options_container
        layout.addWidget(image_options_container)

        
        self.sidebar_box_options_group = QWidget()
        box_options_layout = QVBoxLayout(self.sidebar_box_options_group)
        box_options_layout.setContentsMargins(0, 15, 0, 0)
        
        separator = QFrame(); separator.setFrameShape(QFrame.Shape.HLine); separator.setFrameShadow(QFrame.Shadow.Sunken); box_options_layout.addWidget(separator)
        
        self.sidebar_content_box_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.sidebar_content_box_checkbox.setToolTip("Puts a rounded, semi-transparent box behind the profile bar, buttons, and deck list.")
        self.sidebar_content_box_checkbox.setChecked(mw.col.conf.get("modern_menu_sidebar_content_box_enabled", False))
        box_options_layout.addWidget(self._create_toggle_row(self.sidebar_content_box_checkbox, "Enable content box for sidebar elements"))
        
        opacity_layout = QHBoxLayout()
        opacity_label = QLabel("Box Opacity:")
        self.sidebar_content_box_opacity_spinbox = QSpinBox()
        self.sidebar_content_box_opacity_spinbox.setMinimum(0)
        self.sidebar_content_box_opacity_spinbox.setMaximum(100)
        self.sidebar_content_box_opacity_spinbox.setSuffix(" %")
        self.sidebar_content_box_opacity_spinbox.setValue(mw.col.conf.get("modern_menu_sidebar_content_box_opacity", 80))
        opacity_layout.addWidget(opacity_label)
        opacity_layout.addWidget(self.sidebar_content_box_opacity_spinbox)
        opacity_layout.addStretch()
        box_options_layout.addLayout(opacity_layout)

        self.sidebar_content_box_checkbox.toggled.connect(self.sidebar_content_box_opacity_spinbox.setEnabled)
        self.sidebar_content_box_opacity_spinbox.setEnabled(self.sidebar_content_box_checkbox.isChecked())

        layout.addWidget(self.sidebar_box_options_group)

        self.sidebar_bg_type_color_radio.toggled.connect(self.toggle_sidebar_bg_type_options); self.sidebar_bg_type_image_radio.toggled.connect(self.toggle_sidebar_bg_type_options); self.sidebar_bg_type_image_color_radio.toggled.connect(self.toggle_sidebar_bg_type_options); self.sidebar_bg_type_accent_radio.toggled.connect(self.toggle_sidebar_bg_type_options)
        self.toggle_sidebar_bg_type_options(); return widget

    def _get_svg_icon(self, path: str) -> QIcon | None:
        """Helper to load, color, and return a QIcon from an SVG file."""
        if not os.path.exists(path):
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                svg_data = f.read()

            # Color the SVG based on current theme
            icon_color = "#e0e0e0" if theme_manager.night_mode else "#212121"
            if 'currentColor' in svg_data:
                colored_svg = svg_data.replace('currentColor', icon_color)
            else:
                # Add fill attribute to the root SVG tag if not present
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

    def _on_shape_selected(self):
        """Slot to update the selected shape when a button is clicked."""
        sender = self.sender()
        if sender and sender.isChecked():
            self.selected_heatmap_shape = sender.property("shape_filename")

    def _create_shape_selector(self) -> QWidget:
        """Creates a widget with a grid of selectable SVG shapes."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setFixedHeight(100)
        
        scroll_content = QWidget()
        self.shapes_grid_layout = QGridLayout(scroll_content)
        self.shapes_grid_layout.setSpacing(10)
        self.shapes_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll_area.setWidget(scroll_content)
        
        layout.addWidget(scroll_area)
        
        # Define styles based on theme
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

        icons_path = os.path.join(self.addon_path, "user_files", "heatmap_icons", "heatmap_system_icons")
        self.shape_buttons = []
        
        if os.path.isdir(icons_path):
            row, col = 0, 0
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

                    self.shapes_grid_layout.addWidget(card, row, col)
                    self.shape_buttons.append(card)
                    
                    col += 1
                    if col >= 7: # Adjust number of icons per row if needed
                        col = 0
                        row += 1
                        
        self.selected_heatmap_shape = self.current_config.get("heatmapShape", "square.svg")
        for btn in self.shape_buttons:
            if btn.property("shape_filename") == self.selected_heatmap_shape:
                btn.setChecked(True)
                break
            
        return widget

    def create_heatmap_tab(self):
        page, layout = self._create_scrollable_page()
        
        # --- Shape Section ---
        shape_section = SectionGroup("Shape", self)
        shape_selector = self._create_shape_selector()
        shape_section.add_widget(shape_selector)
        layout.addWidget(shape_section)

        # --- Visibility Section ---
        visibility_section = SectionGroup("Visibility", self)
        
        self.heatmap_show_streak_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_streak_check.setChecked(self.current_config.get("heatmapShowStreak", True))
        visibility_section.add_widget(self._create_toggle_row(self.heatmap_show_streak_check, "Show review streak counter"))

        self.heatmap_show_months_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_months_check.setChecked(self.current_config.get("heatmapShowMonths", True))
        visibility_section.add_widget(self._create_toggle_row(self.heatmap_show_months_check, "Show month labels (Year view)"))

        self.heatmap_show_weekdays_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_weekdays_check.setChecked(self.current_config.get("heatmapShowWeekdays", True))
        visibility_section.add_widget(self._create_toggle_row(self.heatmap_show_weekdays_check, "Show weekday labels (Year & Month view)"))

        self.heatmap_show_week_header_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_week_header_check.setChecked(self.current_config.get("heatmapShowWeekHeader", True))
        visibility_section.add_widget(self._create_toggle_row(self.heatmap_show_week_header_check, "Show day labels (Week view)"))

        layout.addWidget(visibility_section)

        layout.addStretch()
        return page

    def create_icons_tab(self):
        page, layout = self._create_scrollable_page()
        
        assignment_section = SectionGroup("Assign Custom Icons", self)
        description = QLabel("Assign an SVG file from your library to a specific function. Use the library manager below to add or remove icons.")
        description.setWordWrap(True); assignment_section.add_widget(description)
        self.icon_assignment_widgets.clear()

        deck_icons_group, deck_icons_layout_content = self._create_inner_group("Deck")
        deck_icons_layout = QGridLayout(); deck_icons_layout.setSpacing(15)
        deck_icons_layout_content.addLayout(deck_icons_layout)
        deck_icons_to_configure = {"folder": "Deck List: Folder Icon", "deck_child": "Deck List: Child Deck Icon", "options": "Deck List: Options Icon", "collapse_closed": "Deck List: Collapsed Icon (+)", "collapse_open": "Deck List: Expanded Icon (⌄)"}
        row, col, num_cols = 0, 0, 3
        for key, label_text in deck_icons_to_configure.items():
            card = QWidget(); card_layout = QVBoxLayout(card); card_layout.setContentsMargins(0,0,0,0); card_layout.setSpacing(5)
            label = QLabel(label_text); label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            control_widget = self._create_icon_control_widget(key); self.icon_assignment_widgets.append(control_widget)
            card_layout.addWidget(label); card_layout.addWidget(control_widget); deck_icons_layout.addWidget(card, row, col)
            col += 1
            if col >= num_cols: col = 0; row += 1
        assignment_section.add_widget(deck_icons_group)

        action_buttons_group, action_buttons_layout_content = self._create_inner_group("Action Buttons")
        action_buttons_layout = QGridLayout(); action_buttons_layout.setSpacing(15)
        action_buttons_layout_content.addLayout(action_buttons_layout)
        action_icons_to_configure = {"add": "Action Button: Add", "browse": "Action Button: Browser", "stats": "Action Button: Stats", "sync": "Action Button: Sync", "settings": "Action Button: Settings", "more": "Action Button: More", "get_shared": "Action Button: Get Shared", "create_deck": "Action Button: Create Deck", "import_file": "Action Button: Import File"}
        row, col = 0, 0
        for key, label_text in action_icons_to_configure.items():
            card = QWidget(); card_layout = QVBoxLayout(card); card_layout.setContentsMargins(0,0,0,0); card_layout.setSpacing(5)
            label = QLabel(label_text); label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            control_widget = self._create_icon_control_widget(key); self.icon_assignment_widgets.append(control_widget)
            card_layout.addWidget(label); card_layout.addWidget(control_widget); action_buttons_layout.addWidget(card, row, col)
            col += 1
            if col >= num_cols: col = 0; row += 1
        assignment_section.add_widget(action_buttons_group)
        
        stats_icons_group, stats_icons_layout_content = self._create_inner_group("Stats Icons")
        stats_icons_layout = QGridLayout()
        stats_icons_layout.setSpacing(15)
        stats_icons_layout_content.addLayout(stats_icons_layout)
        card = QWidget(); card_layout = QVBoxLayout(card); card_layout.setContentsMargins(0,0,0,0); card_layout.setSpacing(5)
        label = QLabel("Retention Star"); label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        control_widget = self._create_icon_control_widget("retention_star"); self.icon_assignment_widgets.append(control_widget)
        card_layout.addWidget(label); card_layout.addWidget(control_widget); stats_icons_layout.addWidget(card, 0, 0)
        assignment_section.add_widget(stats_icons_group)

        reset_icons_button = QPushButton("Reset All Assignments to Default"); reset_icons_button.clicked.connect(self.reset_icons_to_default)
        reset_button_layout = QHBoxLayout(); reset_button_layout.addStretch(); reset_button_layout.addWidget(reset_icons_button); assignment_section.add_layout(reset_button_layout)
        layout.addWidget(assignment_section)
        
        sizing_section = SectionGroup("Icon Sizing (in pixels)", self)
        sizing_layout = QFormLayout(); sizing_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        sizing_section.add_layout(sizing_layout)
        icon_sizes_to_configure = {"deck_folder": "Deck/Folder Icons:", "action_button": "Action Button Icons:", "collapse": "Expand/Collapse Icons:", "options_gear": "Deck Options Gear Icon:"}
        for key, label in icon_sizes_to_configure.items(): sizing_layout.addRow(label, self.create_icon_size_spinbox(key, DEFAULT_ICON_SIZES[key]))
        reset_sizes_button = QPushButton("Reset Sizes to Default"); reset_sizes_button.clicked.connect(self.reset_icon_sizes_to_default); sizing_layout.addRow(reset_sizes_button)
        layout.addWidget(sizing_section)
        
        icon_lib_section = SectionGroup("Icon Library", self)
        icon_lib_section.add_widget(self._create_image_gallery_placeholder("icons", "user_files/icons", "", extensions=(".svg",), show_path=False))
        layout.addWidget(icon_lib_section)

        return page
        
    def _create_scrollable_page(self):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        content_widget = QWidget(); content_widget.setStyleSheet("QWidget { background: transparent; }"); scroll.setWidget(content_widget)
        content_layout = QVBoxLayout(content_widget)
        page_container = QWidget(); page_layout = QVBoxLayout(page_container); page_layout.setContentsMargins(0, 0, 0, 0); page_layout.addWidget(scroll);
        return page_container, content_layout

    def _create_mode_tags(self, theme_data):
        tags_container = QWidget()
        tags_layout = QHBoxLayout(tags_container)
        tags_layout.setContentsMargins(0, 0, 0, 0)
        tags_layout.setSpacing(4)
        tags_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        if theme_manager.night_mode:
            tag_bg = "rgba(255, 255, 255, 0.1)"
            tag_fg = "rgba(255, 255, 255, 0.7)"
        else:
            tag_bg = "rgba(0, 0, 0, 0.08)"
            tag_fg = "rgba(0, 0, 0, 0.6)"

        # --- MODIFIED ---
        # Stylesheet now ONLY handles appearance, not size or alignment.
        tag_style = f"""
            QLabel {{
                background-color: {tag_bg};
                color: {tag_fg};
                border-radius: 4px;
                font-weight: bold;
                font-size: 8pt;
            }}
        """

        is_light, is_dark = False, False

        if "colors" in theme_data and isinstance(theme_data.get("colors"), dict):
            colors_config = theme_data["colors"]
            if "light" in colors_config and isinstance(colors_config.get("light"), dict) and colors_config["light"]:
                is_light = True
            if "dark" in colors_config and isinstance(colors_config.get("dark"), dict) and colors_config["dark"]:
                is_dark = True

        if not is_light and not is_dark and "mode" in theme_data:
            if theme_data["mode"] == "light":
                is_light = True
            elif theme_data["mode"] == "dark":
                is_dark = True
        
        # --- MODIFIED ---
        # We now set a fixed size and alignment directly on the widget in Python.
        square_size = 16 # Change this value to make the square bigger or smaller

        if is_light:
            light_tag = QLabel("L")
            light_tag.setFixedSize(square_size, square_size)
            light_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
            light_tag.setStyleSheet(tag_style)
            tags_layout.addWidget(light_tag)

        if is_dark:
            dark_tag = QLabel("D")
            dark_tag.setFixedSize(square_size, square_size)
            dark_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dark_tag.setStyleSheet(tag_style)
            tags_layout.addWidget(dark_tag)
        
        return tags_container

    def _create_image_gallery_group(self, key, folder, config_key, extensions=(".png", ".jpg", ".jpeg", ".gif"), show_path=True, is_sub_group=False, title="", image_files_cache=None):
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

        gallery_data = {
            'selected': mw.col.conf.get(config_key, ""), 'folder': folder, 'extensions': extensions,
            'grid_layout': grid_layout, 'labels': [], 'thread': None, 'worker': None,
            'path_input': path_input if show_path else None, 'delete_button': delete_button
        }
        self.galleries[key].update(gallery_data)

        self._populate_gallery_placeholders(key, image_files_cache)
        layout.addLayout(button_row)
        self._update_delete_button_state(key)
        return group_container

    def _create_image_gallery_placeholder(self, key, folder, config_key, extensions=(".png", ".jpg", ".jpeg", ".gif"), show_path=True, is_sub_group=False, title="", image_files_cache=None):
        placeholder_container = QWidget()
        layout = QVBoxLayout(placeholder_container)
        layout.setContentsMargins(0, 0 if is_sub_group else 10, 0, 0)

        load_button = QPushButton("View Gallery to Make Changes")
        layout.addWidget(load_button)

        self.galleries[key] = {
            'placeholder_container': placeholder_container,
            'folder': folder,
            'config_key': config_key,
            'extensions': extensions,
            'show_path': show_path,
            'is_sub_group': is_sub_group,
            'title': title,
            'image_files_cache': image_files_cache,
            'loaded': False
        }
        
        load_button.clicked.connect(lambda: self._load_gallery_on_demand(key))
        return placeholder_container

    def _load_gallery_on_demand(self, key):
        gallery_info = self.galleries.get(key)
        if not gallery_info or gallery_info.get('loaded'):
            return

        gallery_widget = self._create_image_gallery_group(
            key,
            gallery_info['folder'],
            gallery_info['config_key'],
            gallery_info['extensions'],
            gallery_info['show_path'],
            gallery_info['is_sub_group'],
            gallery_info['title'],
            gallery_info['image_files_cache']
        )
        
        parent_layout = gallery_info['placeholder_container'].parentWidget().layout()
        parent_layout.replaceWidget(gallery_info['placeholder_container'], gallery_widget)
        gallery_info['placeholder_container'].deleteLater()
        
        gallery_info['loaded'] = True
        gallery_info['widget'] = gallery_widget

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
            placeholder = QLabel("⏳"); placeholder.setFixedSize(110, 110); placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("QLabel { background-color: rgba(128,128,128,0.1); border-radius: 10px; }")
            placeholder.setProperty("gallery_key", key)
            placeholder.installEventFilter(self)
            gallery['grid_layout'].addWidget(placeholder, i // 4, i % 4)
            gallery['labels'].append(placeholder)
        
        thread = QThread(); worker = ThumbnailWorker(key, full_folder_path, image_files)
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
        if source.property("is_delete_theme_btn"):
            if event.type() == QEvent.Type.Enter:
                self._update_delete_button_icon(source, source.property("hover_color"))
                return True
            elif event.type() == QEvent.Type.Leave:
                self._update_delete_button_icon(source, source.property("default_color"))
                return True

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
            
            if source.property("is_theme_card"):
                theme_key = source.property("theme_key")
                child_widget = source.childAt(event.pos())
                if theme_key and not isinstance(child_widget, QPushButton):
                    self.apply_community_theme(theme_key)
                    return True

        if source.property("text_stack"):
            text_stack = source.property("text_stack")
            hex_widget = text_stack.widget(1)

            if event.type() == QEvent.Type.Enter:
                text_stack.setCurrentIndex(1)
            elif event.type() == QEvent.Type.Leave:
                # Only switch back if the hex editor doesn't have focus
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
        if not gallery.get('loaded', True): return

        try:
            if gallery.get('thread') and gallery['thread'].isRunning():
                gallery['worker'].cancel()
                gallery['thread'].quit()
                gallery['thread'].wait()
        except RuntimeError:
            # This can happen if the thread has already finished and been deleted.
            # It's safe to ignore, as a deleted thread is definitely not running.
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
        if theme_manager.night_mode: btn_bg, btn_border, btn_fg = "#4a4a4a", "#5a5a5a", "#e0e0e0"
        else: btn_bg, btn_border, btn_fg = "#f0f0f0", "#c9c9c9", "#212121"
        button_style = f"QPushButton {{ background-color: {btn_bg}; color: {btn_fg}; border: 1px solid {btn_border}; padding: 5px 10px; border-radius: 4px; }} QPushButton:pressed {{ background-color: {btn_border}; }}"
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
            self._refresh_gallery("icons")

    def _delete_icon(self, widget): widget.setProperty("icon_filename", ""); self._update_icon_preview_for_widget(widget)
    def reset_icons_to_default(self):
        for widget in self.icon_assignment_widgets: self._delete_icon(widget)

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
    
    def apply_catppuccin_theme(self, theme_name):
        if theme_name not in CATPPUCCIN_THEMES: return
        theme_data = CATPPUCCIN_THEMES[theme_name]; mode = theme_data["mode"]; colors = theme_data["colors"]
        target_accent_input = self.light_accent_color_input if mode == 'light' else self.dark_accent_color_input
        target_widgets = self.color_widgets[mode]
        for name, value in colors.items():
            if name == "--accent-color": target_accent_input.setText(value)
            elif name in target_widgets: target_widgets[name].setText(value)
        if "backgrounds" in theme_data and self.tabs_loaded.get(3):
             backgrounds = theme_data["backgrounds"]; self.color_radio.setChecked(True)
             self.bg_light_color_input.setText(backgrounds["light"]); self.bg_dark_color_input.setText(backgrounds["dark"])
        QMessageBox.information(self, f"{theme_data['name']} Theme Applied", f"The {theme_data['name']} color palette has been loaded.\nBackground settings were also updated to match.\nPress 'Save' to apply the changes.")

    def apply_community_theme(self, theme_name):
        if theme_name not in COMMUNITY_THEMES: return
        theme_data = COMMUNITY_THEMES[theme_name]; mode = theme_data["mode"]; colors = theme_data["colors"]
        target_accent_input = self.light_accent_color_input if mode == 'light' else self.dark_accent_color_input
        target_widgets = self.color_widgets[mode]
        for name, value in colors.items():
            if name == "--accent-color": target_accent_input.setText(value)
            elif name in target_widgets: target_widgets[name].setText(value)
        if "backgrounds" in theme_data and self.tabs_loaded.get(3):
             backgrounds = theme_data["backgrounds"]; self.color_radio.setChecked(True)
             self.bg_light_color_input.setText(backgrounds["light"]); self.bg_dark_color_input.setText(backgrounds["dark"])
        QMessageBox.information(self, f"{theme_data['name']} Theme Applied", f"The {theme_data['name']} color palette has been loaded.\nBackground settings were also updated to match.\nPress 'Save' to apply the changes.")

    def apply_user_theme(self, theme_path):
        if self.block_card_click:
            self.block_card_click = False
            return
            
        try:
            with open(theme_path, 'r', encoding='utf-8') as f:
                theme_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            QMessageBox.warning(self, "Error", f"Could not load theme file:\n{e}")
            return
        
        mode = theme_data.get("mode", "dark")
        colors = theme_data.get("colors", {})

        for color_mode in ["light", "dark"]:
            if color_mode in colors:
                theme_colors = colors[color_mode]
                target_accent_input = self.light_accent_color_input if color_mode == 'light' else self.dark_accent_color_input
                target_widgets = self.color_widgets[color_mode]
                for name, value in theme_colors.items():
                    if name == "--accent-color": target_accent_input.setText(value)
                    elif name in target_widgets: target_widgets[name].setText(value)
        
        if "backgrounds" in theme_data and self.tabs_loaded.get(3): # Index for Background page
             backgrounds = theme_data["backgrounds"]
             self.color_radio.setChecked(True)
             self.bg_light_color_input.setText(backgrounds.get("light", DEFAULTS["colors"]["light"]["--bg"]))
             self.bg_dark_color_input.setText(backgrounds.get("dark", DEFAULTS["colors"]["dark"]["--bg"]))
        
        QMessageBox.information(self, f"{theme_data.get('name', 'Theme')} Applied", f"The {theme_data.get('name', 'Theme')} color palette has been loaded for all applicable modes.\nPress 'Save' to apply the changes.")

    def delete_user_theme(self, theme_path):
        self.block_card_click = True
        filename = os.path.basename(theme_path)
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to permanently delete the theme '{filename}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(theme_path)
                self._populate_your_themes()
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Could not delete theme file:\n{e}")

    def open_catppuccin_link(self): QDesktopServices.openUrl(QUrl("https://catppuccin.com/palette/"))
    
    def reset_theme_to_default(self):
        # Reset the theme colors on the current page
        self.reset_colors_to_default()

        # Find the index of the 'Background' page
        try:
            all_pages = [self.sidebar.item(i).text() for i in range(self.sidebar.count())]
            background_tab_index = all_pages.index("Background")
        except (ValueError, AttributeError):
            background_tab_index = -1

        if background_tab_index != -1:
            # Ensure the background page's widgets are loaded
            if not self.tabs_loaded.get(background_tab_index):
                page_name = self.sidebar.item(background_tab_index).text()
                create_func = self.pages[page_name]
                new_widget = create_func()
                
                old_widget = self.content_stack.widget(background_tab_index)
                self.content_stack.removeWidget(old_widget)
                self.content_stack.insertWidget(background_tab_index, new_widget)
                old_widget.deleteLater()
                self.tabs_loaded[background_tab_index] = True
            
            # Now that the tab is loaded, its widgets exist and can be modified
            self.bg_light_color_input.setText(DEFAULTS["colors"]["light"]["--bg"])
            self.bg_dark_color_input.setText(DEFAULTS["colors"]["dark"]["--bg"])

        QMessageBox.information(self, "Theme Reset", "The color theme and background colors have been reset to their default values.\nPress 'Save' to apply the changes.")

    def reset_colors_to_default(self):
        default_colors=DEFAULTS["colors"]
        for mode in["light","dark"]:
            if hasattr(self,f"{mode}_accent_color_input"):getattr(self,f"{mode}_accent_color_input").setText(default_colors[mode]["--accent-color"])
            for name,widget in self.color_widgets[mode].items():
                if name in default_colors[mode]:widget.setText(default_colors[mode][name])

    def import_theme(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Onigiri Theme", "", "JSON Files (*.json)")
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='utf-8') as f: data = json.load(f)

            if not isinstance(data, dict) or "colors" not in data or "name" not in data:
                raise ValueError("Invalid theme file. Must contain 'name' and 'colors' keys.")

            theme_name = data["name"]
            safe_filename = "".join(c for c in theme_name if c.isalnum() or c in (' ', '_')).rstrip()
            safe_filename = safe_filename.replace(' ', '_').lower() + ".json"
            
            dest_path = os.path.join(self.user_themes_path, safe_filename)

            if os.path.exists(dest_path):
                reply = QMessageBox.question(self, "Theme Exists", f"A theme named '{theme_name}' already exists. Overwrite it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    return

            shutil.copy(filepath, dest_path)
            self._populate_your_themes()
            QMessageBox.information(self, "Theme Imported", f"Successfully imported '{theme_name}'.\nIt has been added to 'Your Themes'.")

        except Exception as e:
            QMessageBox.warning(self, "Import Error", f"Could not import theme file:\n{e}")

    def export_theme(self):
        theme_name, ok = QInputDialog.getText(self, "Export Theme", "Enter a name for your theme:")
        if not ok or not theme_name:
            return

        theme_to_save = {
            "name": theme_name,
            "mode": "dark" if theme_manager.night_mode else "light",
            "colors": {"light": {}, "dark": {}},
            "preview": [],
            "backgrounds": {}
        }

        theme_to_save["colors"]["light"]["--accent-color"] = self.light_accent_color_input.text()
        for key, widget in self.color_widgets["light"].items(): theme_to_save["colors"]["light"][key] = widget.text()
        theme_to_save["colors"]["dark"]["--accent-color"] = self.dark_accent_color_input.text()
        for key, widget in self.color_widgets["dark"].items(): theme_to_save["colors"]["dark"][key] = widget.text()

        if self.tabs_loaded.get(3): # Index for Background page
             theme_to_save["backgrounds"]["light"] = self.bg_light_color_input.text()
             theme_to_save["backgrounds"]["dark"] = self.bg_dark_color_input.text()
        
        current_mode_colors = theme_to_save["colors"]["dark" if theme_manager.night_mode else "light"]
        preview_keys = ["--bg", "--fg", "--accent-color", "--button-primary-bg", "--highlight-bg", "--fg-subtle", "--border", "--icon-color"]
        theme_to_save["preview"] = [current_mode_colors.get(k, "#000000") for k in preview_keys]

        safe_filename = "".join(c for c in theme_name if c.isalnum() or c in (' ', '_')).rstrip()
        safe_filename = safe_filename.replace(' ', '_').lower() + ".json"
        
        home_dir = os.path.expanduser("~")
        suggested_path = os.path.join(home_dir, safe_filename)
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Onigiri Theme", suggested_path, "JSON Files (*.json)")
        if not filepath: return
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(theme_to_save, f, indent=4)
            QMessageBox.information(self, "Theme Exported", f"Theme saved successfully to:\n{filepath}")
        except Exception as e:
            QMessageBox.warning(self, "Export Error", f"Could not save theme file:\n{e}")

    def reset_background_to_default(self):
        self.color_radio.setChecked(True); self.bg_light_color_input.setText(DEFAULTS["colors"]["light"]["--bg"]); self.bg_dark_color_input.setText(DEFAULTS["colors"]["dark"]["--bg"])
        for key in ['main_single', 'main_light', 'main_dark', 'sidebar_bg']:
            if key in self.galleries:
                self.galleries[key]['selected'] = ""; 
                if self.galleries[key].get('path_input'): self.galleries[key]['path_input'].setText("")
                self._refresh_gallery(key)
        self.bg_blur_spinbox.setValue(0); self.bg_opacity_spinbox.setValue(100); self.sidebar_bg_main_radio.setChecked(True)
        self.sidebar_bg_type_color_radio.setChecked(True); self.sidebar_bg_light_color_input.setText("#EEEEEE"); self.sidebar_bg_dark_color_input.setText("#3C3C3C")
        self.sidebar_bg_blur_spinbox.setValue(0); self.sidebar_bg_opacity_spinbox.setValue(100)
    
    def toggle_profile_bg_options(self):
        try:
            self.profile_bg_color_group.setVisible(self.profile_bg_custom_radio.isChecked())
            self.profile_bg_image_group.setVisible(self.profile_bg_image_radio.isChecked())
        except RuntimeError:
            pass
    def toggle_background_options(self): is_color=self.color_radio.isChecked();is_image=self.image_radio.isChecked();is_image_color=self.image_color_radio.isChecked();self.color_group.setVisible(is_color or is_image_color);self.image_group.setVisible(is_image or is_image_color);self.bg_opacity_label.setVisible(is_image_color);self.bg_opacity_spinbox.setVisible(is_image_color)
    def toggle_background_image_mode(self): is_single = self.bg_image_mode_single_radio.isChecked(); self.single_image_container.setVisible(is_single); self.separate_images_container.setVisible(not is_single)
    def toggle_sidebar_background_options(self): self.sidebar_custom_options_group.setVisible(self.sidebar_bg_custom_radio.isChecked())
    def toggle_sidebar_bg_type_options(self): is_color=self.sidebar_bg_type_color_radio.isChecked();is_image=self.sidebar_bg_type_image_radio.isChecked();is_image_color=self.sidebar_bg_type_image_color_radio.isChecked();self.sidebar_color_group.setVisible(is_color or is_image_color);self.sidebar_image_group.setVisible(is_image or is_image_color);self.sidebar_bg_opacity_label.setVisible(is_image_color);self.sidebar_bg_opacity_spinbox.setVisible(is_image_color)
    def toggle_profile_page_bg_options(self): is_gradient = self.profile_page_bg_gradient_radio.isChecked(); self.profile_page_color_group.setVisible(not is_gradient); self.profile_page_gradient_group.setVisible(is_gradient)

    def _on_hide_all_stats_toggled(self, checked):
        """Toggles the individual stat card checkboxes when the main one is toggled."""
        self.hide_studied_stat_checkbox.setChecked(checked)
        self.hide_time_stat_checkbox.setChecked(checked)
        self.hide_pace_stat_checkbox.setChecked(checked)
        self.hide_retention_stat_checkbox.setChecked(checked)


    def _save_general_settings(self):
        self.current_config.update({
            "userName": self.name_input.text(),
            "hideStudiedToday": self.hide_studied_checkbox.isChecked(),
            "hideTodaysStats": self.hide_stats_checkbox.isChecked(),
            # --- Study Stats  ---
            "hideStudiedStat": self.hide_studied_stat_checkbox.isChecked(),
            "hideTimeStat": self.hide_time_stat_checkbox.isChecked(),
            "hidePaceStat": self.hide_pace_stat_checkbox.isChecked(),
            "hideRetentionStat": self.hide_retention_stat_checkbox.isChecked(),
            # -----------------------
            "hideWelcomeMessage": self.hide_welcome_checkbox.isChecked(),
            "hideProfileBar": self.hide_profile_bar_checkbox.isChecked(),
            "hideNativeHeaderAndBottomBar": self.hide_native_header_checkbox.isChecked(),
            "ultraHide": self.ultra_hide_checkbox.isChecked(),
            "showCongratsProfileBar": self.show_congrats_profile_bar_checkbox.isChecked(),
            "congratsMessage": self.congrats_message_input.text(),
            "hideHeatmapOnMain": self.hide_heatmap_on_main_checkbox.isChecked(),
        })
        mw.col.conf["modern_menu_userName"] = self.name_input.text()
        mw.col.conf["modern_menu_statsTitle"] = self.stats_title_input.text()
        mw.col.conf["modern_menu_studyNowText"] = self.study_now_input.text()

    def _save_profile_settings(self):
        if self.galleries.get('profile_pic', {}).get('loaded'):
            mw.col.conf["modern_menu_profile_picture"] = self.galleries['profile_pic']['selected']
        if self.galleries.get('profile_bg', {}).get('loaded'):
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
        self.current_config["colors"]["light"]["--accent-color"] = self.light_accent_color_input.text()
        self.current_config["colors"]["dark"]["--accent-color"] = self.dark_accent_color_input.text()
        for mode in ["light", "dark"]:
            for name, widget in self.color_widgets[mode].items():
                self.current_config["colors"][mode][name] = widget.text()

    def _save_background_settings(self):
        if self.image_radio.isChecked(): mw.col.conf["modern_menu_background_mode"] = "image"
        elif self.accent_radio.isChecked(): mw.col.conf["modern_menu_background_mode"] = "accent"
        elif self.image_color_radio.isChecked(): mw.col.conf["modern_menu_background_mode"] = "image_color"
        else: mw.col.conf["modern_menu_background_mode"] = "color"
        
        if self.bg_image_mode_separate_radio.isChecked(): mw.col.conf["modern_menu_background_image_mode"] = "separate"
        else: mw.col.conf["modern_menu_background_image_mode"] = "single"
        
        if self.galleries.get('main_single', {}).get('loaded'): mw.col.conf["modern_menu_background_image"] = self.galleries['main_single']['selected']
        if self.galleries.get('main_light', {}).get('loaded'): mw.col.conf["modern_menu_background_image_light"] = self.galleries['main_light']['selected']
        if self.galleries.get('main_dark', {}).get('loaded'): mw.col.conf["modern_menu_background_image_dark"] = self.galleries['main_dark']['selected']
        if self.galleries.get('sidebar_bg', {}).get('loaded'): mw.col.conf["modern_menu_sidebar_bg_image"] = self.galleries['sidebar_bg']['selected']

        mw.col.conf["modern_menu_bg_color_light"] = self.bg_light_color_input.text()
        mw.col.conf["modern_menu_bg_color_dark"] = self.bg_dark_color_input.text()
        mw.col.conf["modern_menu_background_blur"] = self.bg_blur_spinbox.value()
        mw.col.conf["modern_menu_background_opacity"] = self.bg_opacity_spinbox.value()
        
        if self.sidebar_bg_custom_radio.isChecked(): mw.col.conf["modern_menu_sidebar_bg_mode"] = "custom"
        else: mw.col.conf["modern_menu_sidebar_bg_mode"] = "main"
        
        if self.sidebar_bg_type_image_radio.isChecked(): mw.col.conf["modern_menu_sidebar_bg_type"] = "image"
        elif self.sidebar_bg_type_accent_radio.isChecked(): mw.col.conf["modern_menu_sidebar_bg_type"] = "accent"
        elif self.sidebar_bg_type_image_color_radio.isChecked(): mw.col.conf["modern_menu_sidebar_bg_type"] = "image_color"
        else: mw.col.conf["modern_menu_sidebar_bg_type"] = "color"
        
        mw.col.conf["modern_menu_sidebar_content_box_enabled"] = self.sidebar_content_box_checkbox.isChecked()
        mw.col.conf["modern_menu_sidebar_content_box_opacity"] = self.sidebar_content_box_opacity_spinbox.value()
        mw.col.conf["modern_menu_sidebar_bg_color_light"] = self.sidebar_bg_light_color_input.text()
        mw.col.conf["modern_menu_sidebar_bg_color_dark"] = self.sidebar_bg_dark_color_input.text()
        mw.col.conf["modern_menu_sidebar_bg_blur"] = self.sidebar_bg_blur_spinbox.value()
        mw.col.conf["modern_menu_sidebar_bg_opacity"] = self.sidebar_bg_opacity_spinbox.value()

    def _save_heatmap_settings(self):
        if hasattr(self, "selected_heatmap_shape"):
            self.current_config["heatmapShape"] = self.selected_heatmap_shape
        
        self.current_config["heatmapShowStreak"] = self.heatmap_show_streak_check.isChecked()
        self.current_config["heatmapShowMonths"] = self.heatmap_show_months_check.isChecked()
        self.current_config["heatmapShowWeekdays"] = self.heatmap_show_weekdays_check.isChecked()
        self.current_config["heatmapShowWeekHeader"] = self.heatmap_show_week_header_check.isChecked()

    def _save_icons_settings(self):
        for widget in self.icon_assignment_widgets:
            key = widget.property("icon_key"); value = widget.property("icon_filename"); config_key = f"modern_menu_icon_{key}"
            if value: mw.col.conf[config_key] = value
            elif config_key in mw.col.conf: del mw.col.conf[config_key]
        for key,widget in self.icon_size_widgets.items(): mw.col.conf[f"modern_menu_icon_size_{key}"] = widget.value()

    def save_settings(self):
        page_map = {self.sidebar.item(i).text(): i for i in range(self.sidebar.count())}

        self._save_general_settings()

        if self.tabs_loaded.get(page_map.get("Profile")): self._save_profile_settings()
        if self.tabs_loaded.get(page_map.get("Colors")): self._save_colors_settings()
        if self.tabs_loaded.get(page_map.get("Background")): self._save_background_settings()
        if self.tabs_loaded.get(page_map.get("Heatmap")): self._save_heatmap_settings()
        if self.tabs_loaded.get(page_map.get("Icons")): self._save_icons_settings()

        config.write_config(self.current_config)
        self.accept()

# --- FIX: Add the missing function to open the settings dialog ---
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
