import os
import copy
import shutil
import urllib.parse
import json
import functools
import time
import base64
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
from .. import config
from ..gamification import restaurant_level
from ..config import DEFAULTS
from ..constants import COLOR_LABELS, ICON_DEFAULTS, DEFAULT_ICON_SIZES, ALL_THEME_KEYS, REVIEWER_THEME_KEYS
from ..themes import THEMES
from aqt.qt import QRectF
from PyQt6.QtGui import QImage, QBitmap, QPainter as _QPainter
from aqt.utils import showInfo
from PyQt6.QtGui import QFontDatabase, QFont
from PyQt6.QtCore import QRect, QSize, QPoint
from ..fonts import FONTS, get_all_fonts
from .. import sidebar_api


from ._widgets import (
    THUMBNAIL_STYLE, THUMBNAIL_STYLE_SELECTED, CUSTOM_GOAL_COOLDOWN_SECONDS,
    FlowLayout, create_circular_pixmap, create_rounded_pixmap,
    ThumbnailWorker, SelectionOverlay, CircularColorButton, AnimatedToggleButton,
    ProfileBarWidget, RoundedScrollArea, SidebarToggleButton, SectionGroup,
    ColorSwatch, ThemeCardWidget, BirthdayWidget, FontCardWidget,
    SearchResultWidget, SettingsSearchPage, DonationDialog,
)
from ._color_picker import ModernColorPickerDialog
from ._icon_picker import IconPickerDialog
from ._layout_base import (
    CustomMenu, DraggableItem, DropZone, VerticalDropZone, GridDropZone, Shelf,
)
from ._layout_sidebar import (
    DraggableSidebarItem, SidebarVisibleZone, SidebarArchiveZone,
    SidebarExternalArchiveZone, SidebarLayoutEditor,
)
from ._layout_main import (
    OnigiriDraggableItem, UnifiedGridDropZone, OnigiriGridDropZone,
    OnigiriArchiveZone, ExternalArchiveZone, OnigiriLayoutEditor,
    MainMenuLayoutEditor, UnifiedLayoutEditor,
    AdaptiveModeCard, ResponsiveModeCardsContainer,
)
from ._page_fonts import FontsPageMixin
from ._page_hide_modes import HideModesPageMixin
from ._page_gallery import GalleryPageMixin
from ._page_overviews import OverviewsPageMixin
from ._page_colors import ColorsPageMixin
from ._page_profile import ProfilePageMixin
from ._page_sidebar import SidebarPageMixin
from ._page_themes import ThemesPageMixin
from ._page_main_menu import MainMenuPageMixin
from ._page_reviewer import ReviewerPageMixin
from ._infra import InfrastructureMixin


class SettingsDialog(
    InfrastructureMixin,
    FontsPageMixin,
    HideModesPageMixin,
    GalleryPageMixin,
    OverviewsPageMixin,
    ColorsPageMixin,
    ProfilePageMixin,
    SidebarPageMixin,
    ThemesPageMixin,
    MainMenuPageMixin,
    ReviewerPageMixin,
    QDialog,
):
    def __init__(self, parent=None, addon_path=None, initial_page_index=0):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
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
        sidebar_wrapper_layout.setContentsMargins(15, 15, 0, 15) # 15px left margin, 0px right margin

        # --- Search Button (Separated) ---
        self.search_button = QPushButton("Search")
        self.search_button.setCheckable(True)
        self.search_button.setObjectName("searchSidebarButton")
        self.search_button.setFixedWidth(185) # Force fixed width
        self.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_button.setAutoDefault(False)
        self.search_button.clicked.connect(lambda: self.navigate_to_page("Search"))
        sidebar_wrapper_layout.addWidget(self.search_button, alignment=Qt.AlignmentFlag.AlignLeft)

        # Add spacing between Search button and the rest of the sidebar
        sidebar_wrapper_layout.addSpacing(10)

        # --- Scroll Area for Sidebar Content (rounded pill) ---
        self.sidebar_scroll_area = RoundedScrollArea(radius=25)
        self.sidebar_scroll_area.setWidgetResizable(True)
        self.sidebar_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sidebar_scroll_area.setFixedWidth(200) # 185px for content + 15px for scrollbar
        
        # Style the scroll area to be transparent
        self.sidebar_scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
        """)

        # This is the actual visible sidebar widget, which will be styled as the top floating pill
        sidebar_widget = QWidget()
        sidebar_widget.setObjectName("sidebarContainer") # Name for the stylesheet
        sidebar_widget.setFixedWidth(185) # Force fixed width so it doesn't shrink when scrollbar appears
        
        self.sidebar_scroll_area.setWidget(sidebar_widget)
        
        # Add the scroll area to the main wrapper
        sidebar_wrapper_layout.addWidget(self.sidebar_scroll_area, alignment=Qt.AlignmentFlag.AlignLeft)

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


        self.donate_button = QPushButton("Donate")
        self.donate_button.setAutoDefault(False)
        self.donate_button.clicked.connect(self._open_donate_link)
        self.report_bugs_button = QPushButton("Report Bugs")
        self.report_bugs_button.setAutoDefault(False)
        self.report_bugs_button.clicked.connect(self._open_bugs_link)

        self.save_button = QPushButton("Save"); self.save_button.clicked.connect(self.save_settings)
        
        # Second (bottom) floating pill for the save buttons
        bottom_widget = QWidget()
        bottom_widget.setObjectName("sidebarContainer")
        bottom_widget.setFixedWidth(185) # Force fixed width
        
        sidebar_button_layout = QVBoxLayout(bottom_widget)
        sidebar_button_layout.setSpacing(5)
        sidebar_button_layout.setContentsMargins(10, 10, 10, 10)

        sidebar_button_layout.addWidget(self.donate_button)
        sidebar_button_layout.addWidget(self.report_bugs_button)
        sidebar_button_layout.addWidget(self.save_button)

        # Add spacing and then the bottom pill outside the scroll area
        sidebar_wrapper_layout.addSpacing(10)
        sidebar_wrapper_layout.addWidget(bottom_widget, alignment=Qt.AlignmentFlag.AlignLeft)

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

    def closeEvent(self, event):
        if not getattr(self, "_is_saving", False):
            self.save_settings()
        
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
        elif self.general_toggle_widget.select_page(page_name):
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
            self.general_toggle_widget.deselect_all()
            self.study_zone_toggle_widget.deselect_all()
        elif self.study_zone_toggle_widget.select_page(page_name):
            if btn := self.sidebar_button_group.checkedButton():
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
            self.general_toggle_widget.deselect_all()
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
        all_toggles = [
            self.general_toggle_widget,
            self.menu_toggle_widget,
            self.study_zone_toggle_widget,
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
        from .. import patcher
        return patcher._get_hook_name(hook)

    def _get_external_hooks(self):
        """
        Calls the hook-finding logic from patcher.py, which is known to work,
        to prevent issues from code duplication or timing.
        """
        from .. import patcher
        # patcher._get_external_hooks() returns a list of FUNCTION objects.
        external_hook_functions = patcher._get_external_hooks()

        # We need a list of STRING identifiers for the settings dialog.
        return [patcher._get_hook_name(hook) for hook in external_hook_functions]

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

    def save_settings(self):
        if getattr(self, "_is_saving", False):
            return
        self._is_saving = True
        page_indices = {name: i for i, name in enumerate(self.page_order)}

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
        
        # Ensure Anki writes in-memory col.conf modifications to the database
        if hasattr(mw.col, "setMod"):
            mw.col.setMod()
        if hasattr(mw.col, "mark_changed"):
            mw.col.mark_changed()
            
        self.accept()
        mw.reset()

_settings_dialog = None

def open_settings(initial_page_index=0):
    """Opens the Onigiri settings dialog."""
    global _settings_dialog
    if _settings_dialog is not None:
        _settings_dialog.close()
    
    addon_path = os.path.dirname(os.path.dirname(__file__))
    
    _settings_dialog = SettingsDialog(
        parent=mw, 
        addon_path=addon_path, 
        initial_page_index=initial_page_index
    )
    _settings_dialog.show()