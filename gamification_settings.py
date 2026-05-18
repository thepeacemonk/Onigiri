import os
import copy
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QWidget, QSpinBox, QPlainTextEdit, QScrollArea, QGridLayout, QPixmap, 
    Qt, QFrame, QSizePolicy, QButtonGroup, QAbstractButton, QSignalBlocker,
    QColor, QPointF, QRectF, QPainter, QPainterPath, QPropertyAnimation,
    QEasingCurve, QStackedWidget, QMessageBox, QComboBox, QIcon, QSize
)
from PyQt6.QtCore import pyqtSignal, pyqtProperty
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QImage
from aqt import mw
from aqt.theme import theme_manager
from aqt.utils import showInfo
from aqt.qt import (
    QDesktopServices, QUrl
)

from . import config
from .config import DEFAULTS
from .gamification import onigimon, restaurant_level
from .themes import THEMES
from .settings import FlowLayout
from .translations import tr

# --- UI COMPONENTS (Copied from settings.py for standalone functionality) ---

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
        
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(10)
        main_layout.addWidget(self.content_area)

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)

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

        # Each item has (display_name, key, bg_color, text_color)
        gamification_items = [
            (tr("general"),             "General",           "",         ""),
            (tr("restaurant_level"),   "Restaurant Level",  "#ffbd59",  "#000000"),
            ("Onigimon",               "Onigimon",          "#70c6a6",  "#10231b"),
            (tr("focus_dango"),         "Focus Dango",       "#9d3d64",  "#ffffff"),
            (tr("mochi_messages_title"), "Mochi Messages",    "#00bf63",  "#000000"),
            (tr("coming_soon"),         "Coming Soon",       "",         ""),
        ]
        self._item_colors = {key: (bg, fg_c) for (_, key, bg, fg_c) in gamification_items}

        for label, key, bg_color, text_color in gamification_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setAutoDefault(False)
            btn.setObjectName("sidebarButton")
            btn.setProperty("gameBgColor", bg_color)
            btn.setProperty("gameTextColor", text_color)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, name=key: self.navigate_to_page(name))
            self.sidebar_buttons[key] = btn
            self.sidebar_button_group.addButton(btn)
            sidebar_layout.addWidget(btn)

        # Stretch pushes Save to the bottom
        sidebar_layout.addStretch()

        # Save button at the bottom
        self.save_button = QPushButton(tr("save"))
        self.save_button.setObjectName("saveButton")
        self.save_button.setAutoDefault(False)
        self.save_button.clicked.connect(self.save_settings)
        sidebar_layout.addWidget(self.save_button)

        self.sidebar_scroll_area.setWidget(sidebar_widget)
        sidebar_wrapper_layout.addWidget(self.sidebar_scroll_area, alignment=Qt.AlignmentFlag.AlignLeft)

        # Content Stack
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentStack")

        self.pages = {
            "General": self.create_general_page,
            "Restaurant Level": self.create_restaurant_level_page,
            "Onigimon": self.create_onigimon_page,
            "Focus Dango": self.create_focus_dango_page,
            "Mochi Messages": self.create_mochi_messages_page,
            "Coming Soon": self.create_coming_soon_page
        }
        self.page_order = list(self.pages.keys())

        for name in self.page_order:
            self.content_stack.addWidget(QWidget())

        # Wrap content in a rounded container so it paints its own background
        content_container = QWidget()
        content_container.setObjectName("contentContainer")
        content_container_layout = QVBoxLayout(content_container)
        content_container_layout.setContentsMargins(0, 0, 0, 0)
        content_container_layout.addWidget(self.content_stack)

        content_outer = QWidget()
        content_outer.setObjectName("contentOuter")
        content_outer_layout = QVBoxLayout(content_outer)
        content_outer_layout.setContentsMargins(0, 14, 14, 0)
        content_outer_layout.setSpacing(0)
        content_outer_layout.addWidget(content_container)

        content_area_layout.addWidget(sidebar_wrapper)
        content_area_layout.addWidget(content_outer)

        main_layout.addLayout(content_area_layout)
        self.apply_stylesheet()
        self._apply_pill_button_styles()

        # Default page
        self.navigate_to_page("General")

    def _theme_tokens(self):
        mode_key = "dark" if theme_manager.night_mode else "light"
        palette = self.current_config.get("colors", {}).get(mode_key, {})
        defaults = DEFAULTS["colors"][mode_key]
        if theme_manager.night_mode:
            return {
                "bg": palette.get("--bg", "#111827"),
                "panel": palette.get("--canvas-inset", "#1f2937"),
                "surface": palette.get("--highlight-bg", "#263040"),
                "fg": palette.get("--fg", "#f9fafb"),
                "muted": palette.get("--fg-subtle", "#d1d5db"),
                "border": palette.get("--border", "#374151"),
                "accent": palette.get("--accent-color", defaults["--accent-color"]),
            }
        return {
            "bg": palette.get("--bg", "#f0f0f0"),
            "panel": palette.get("--canvas-inset", "#ffffff"),
            "surface": palette.get("--highlight-bg", "#f3f4f6"),
            "fg": palette.get("--fg", "#111827"),
            "muted": palette.get("--fg-subtle", "#4b5563"),
            "border": palette.get("--border", "#e5e7eb"),
            "accent": palette.get("--accent-color", defaults["--accent-color"]),
        }

    def _apply_pill_button_styles(self):
        """Apply individual colored pill styles to each sidebar button."""
        tokens = self._theme_tokens()
        neutral_bg = tokens["surface"]
        neutral_fg = tokens["fg"]
        border = tokens["border"]
        accent = tokens["accent"]

        for key, btn in self.sidebar_buttons.items():
            bg = btn.property("gameBgColor")
            fg_c = btn.property("gameTextColor")
            if not bg:
                bg, fg_c = neutral_bg, neutral_fg

            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {fg_c};
                    border: 1px solid transparent;
                    border-radius: 19px;
                    min-height: 38px;
                    max-height: 38px;
                    padding: 0px 14px;
                    font-size: 13px;
                    font-weight: bold;
                    text-align: center;
                }}
                QPushButton:hover {{
                    border: 1px solid {accent};
                }}
                QPushButton:checked {{
                    background-color: {bg};
                    color: {fg_c};
                    border: 2px solid {accent if not btn.property("gameBgColor") else "rgba(255,255,255,0.85)"};
                    border-radius: 19px;
                }}
            """)


    def _setup_gamification_widgets(self):
        # General / Master Toggle
        self.gamification_mode_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.gamification_mode_toggle.setChecked(bool(self.current_config.get("gamificationMode", True)))
        
        # Focused Gaming Toggle
        self.focused_gaming_toggle = AnimatedToggleButton(accent_color="#5b8dee")
        self.focused_gaming_toggle.setChecked(bool(self.current_config.get("focusedGaming", False)))

        restaurant_conf = self.current_config.get("restaurant_level", {})
        self.restaurant_level_toggle = AnimatedToggleButton(accent_color="#B94632")
        self.restaurant_level_toggle.setChecked(bool(restaurant_conf.get("enabled", False)))
        self.restaurant_notifications_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.restaurant_notifications_toggle.setChecked(bool(restaurant_conf.get("notifications_enabled", True)))
        self.restaurant_bar_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.restaurant_bar_toggle.setChecked(bool(restaurant_conf.get("show_profile_bar_progress", True)))
        self.restaurant_reviewer_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.restaurant_reviewer_toggle.setChecked(bool(restaurant_conf.get("show_reviewer_header", True)))

        # Onigimon
        self.onigimon_config = self.current_config.get("onigimon", {})
        if not isinstance(self.onigimon_config, dict):
            self.onigimon_config = {}
        self.onigimon_toggle = AnimatedToggleButton(accent_color="#70c6a6")
        self.onigimon_toggle.setChecked(bool(self.onigimon_config.get("enabled", False)))
        self.onigimon_notifications_toggle = AnimatedToggleButton(accent_color="#70c6a6")
        self.onigimon_notifications_toggle.setChecked(bool(self.onigimon_config.get("notifications_enabled", True)))
        self.onigimon_daily_toggle = AnimatedToggleButton(accent_color="#70c6a6")
        self.onigimon_daily_toggle.setChecked(bool(self.onigimon_config.get("daily_surprise_enabled", True)))
        self.onigimon_ankimon_updates_toggle = AnimatedToggleButton(accent_color="#70c6a6")
        self.onigimon_ankimon_updates_toggle.setChecked(bool(self.onigimon_config.get("allow_ankimon_updates", False)))
        self.onigimon_reward_interval_spinbox = QSpinBox()
        self.onigimon_reward_interval_spinbox.setRange(1, 50)
        self.onigimon_reward_interval_spinbox.setSuffix(" cards")
        self.onigimon_reward_interval_spinbox.setValue(int(self.onigimon_config.get("reward_interval", 4) or 4))
        self.onigimon_widget_style_combo = QComboBox()
        self.onigimon_widget_style_combo.addItems(["compact", "care", "detailed"])
        current_style = str(self.onigimon_config.get("widget_style", "care"))
        self.onigimon_widget_style_combo.setCurrentText(current_style if current_style in {"compact", "care", "detailed"} else "care")
        self.onigimon_sprite_motion_combo = QComboBox()
        self.onigimon_sprite_motion_combo.addItem("Static sprites", "static")
        self.onigimon_sprite_motion_combo.addItem("GIF sprites", "gif")
        current_motion = str(self.onigimon_config.get("sprite_motion", "static"))
        self.onigimon_sprite_motion_combo.setCurrentIndex(1 if current_motion == "gif" else 0)
        self.onigimon_selected_companion_id = onigimon.manager.load().active_companion_id
        active_companion = onigimon.manager.active_companion()
        self.onigimon_name_input = QLineEdit(onigimon.manager.companion_display_name(active_companion) if active_companion else "")
        self.onigimon_name_input.setPlaceholderText("Nickname")
        self.onigimon_companion_buttons = QButtonGroup(self)
        self.onigimon_companion_buttons.setExclusive(True)
        self.onigimon_companion_grid = QWidget()
        self.onigimon_companion_grid.setObjectName("onigimonCompanionGrid")
        self.onigimon_companion_grid_layout = QGridLayout(self.onigimon_companion_grid)
        self.onigimon_companion_grid_layout.setContentsMargins(8, 8, 8, 8)
        self.onigimon_companion_grid_layout.setSpacing(8)
        self.onigimon_companion_status_label = QLabel("")
        self.onigimon_companion_status_label.setWordWrap(True)
        self._populate_onigimon_companion_combo()
        
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
        self.mochi_messages_toggle = AnimatedToggleButton(accent_color="#35421C")
        self.mochi_messages_toggle.setChecked(bool(self.mochi_messages_config.get("enabled", False)))
        self.mochi_interval_spinbox = QSpinBox()
        self.mochi_interval_spinbox.setRange(1, 1000)
        self.mochi_interval_spinbox.setSuffix(tr("mochi_interval_suffix"))
        self.mochi_interval_spinbox.setValue(int(self.mochi_messages_config.get("cards_interval", 15) or 1))
        
        messages_list = self.mochi_messages_config.get("messages") or [
            tr("mochi_msg_1"), tr("mochi_msg_2"), tr("mochi_msg_3"),
            tr("mochi_msg_4"), tr("mochi_msg_5"), tr("mochi_msg_6"),
            tr("mochi_msg_7")
        ]
        messages_text = "\n".join([str(item).strip() for item in messages_list if str(item).strip()])
        self.mochi_messages_editor = QPlainTextEdit(messages_text)
        self.mochi_messages_editor.setMinimumHeight(120)

        # Focus Dango
        focus_dango_conf = self.achievements_config.get("focusDango", {})
        self.focus_dango_toggle = AnimatedToggleButton(accent_color="#61252D")
        self.focus_dango_toggle.setChecked(bool(focus_dango_conf.get("enabled", False)))
        
        dango_messages = focus_dango_conf.get("messages") or [tr("dont_give_up"), tr("stay_focused")]
        dango_text = "\n".join([str(item).strip() for item in dango_messages if str(item).strip()])
        self.focus_dango_message_editor = QPlainTextEdit(dango_text)
        self.focus_dango_message_editor.setMinimumHeight(80)

    def navigate_to_page(self, name):
        if not name: return
        if name in self.pages:
            index = self.page_order.index(name)
            if self.content_stack.widget(index).layout() is None:
                new_page = self.pages[name]()
                old_widget = self.content_stack.widget(index)
                self.content_stack.removeWidget(old_widget)
                self.content_stack.insertWidget(index, new_page)
                old_widget.deleteLater()
            self.content_stack.setCurrentIndex(index)
            
            # Update sidebar button state
            if name in self.sidebar_buttons:
                self.sidebar_buttons[name].setChecked(True)

    def _open_donate_link(self):
        dialog = DonationDialog(self)
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

    def _create_toggle_row(self, toggle_widget, text_label):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(text_label))
        layout.addStretch()
        layout.addWidget(toggle_widget)
        return row

    def _render_system_icon(self, filename, size=44, color=None):
        icon_path = os.path.join(self.addon_path, "system_files", "system_icons", filename)
        device_ratio = 1.0
        screen = self.screen() if hasattr(self, "screen") else None
        if screen:
            device_ratio = max(device_ratio, float(screen.devicePixelRatio()))
        elif mw and mw.app and mw.app.primaryScreen():
            device_ratio = max(device_ratio, float(mw.app.primaryScreen().devicePixelRatio()))
        if hasattr(self, "devicePixelRatioF"):
            device_ratio = max(device_ratio, float(self.devicePixelRatioF()))
        render_size = max(1, int(round(size * device_ratio)))

        pixmap = QPixmap(render_size, render_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        if not os.path.exists(icon_path):
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
            icon_label.setPixmap(pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
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

    # --- PAGES ---

    def create_general_page(self):
        page, layout = self._create_scrollable_page()
        
        # ---- Hero 1: Gamification Mode ----
        hero_card = QWidget()
        hero_card.setObjectName("gamificationModeHero")
        hero_card.setFixedHeight(120)
        
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setSpacing(20)
        hero_layout.setContentsMargins(20, 20, 20, 20)
        
        icon_label = self._create_general_hero_icon("game-mode.svg")
        hero_layout.addWidget(icon_label)
        
        # Text
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel(tr("gamification_mode"))
        title.setStyleSheet("font-size: 18px; font-weight: bold; background: transparent;")
        text_layout.addWidget(title)
        
        desc = QLabel(tr("gamification_mode_desc"))
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 13px; color: #888; background: transparent;")
        text_layout.addWidget(desc)
        
        hero_layout.addWidget(text_container, 1)
        hero_layout.addWidget(self.gamification_mode_toggle)
        
        layout.addWidget(hero_card)
        
        # ---- Hero 2: Focused Gaming ----
        focused_card = QWidget()
        focused_card.setObjectName("focusedGamingHero")
        focused_card.setFixedHeight(120)
        
        focused_layout = QHBoxLayout(focused_card)
        focused_layout.setSpacing(20)
        focused_layout.setContentsMargins(20, 20, 20, 20)
        
        focus_icon_label = self._create_general_hero_icon("circle-book.svg")
        focused_layout.addWidget(focus_icon_label)
        
        focus_text = QWidget()
        focus_text_layout = QVBoxLayout(focus_text)
        focus_text_layout.setContentsMargins(0, 0, 0, 0)
        
        focus_title = QLabel(tr("focused_gaming"))
        focus_title.setStyleSheet("font-size: 18px; font-weight: bold; background: transparent;")
        focus_text_layout.addWidget(focus_title)
        
        focus_desc = QLabel(tr("focused_gaming_desc"))
        focus_desc.setWordWrap(True)
        focus_desc.setStyleSheet("font-size: 13px; color: #888; background: transparent;")
        focus_text_layout.addWidget(focus_desc)
        
        focused_layout.addWidget(focus_text, 1)
        focused_layout.addWidget(self.focused_gaming_toggle)
        
        layout.addWidget(focused_card)

        layout.addWidget(self.create_notification_position_section())
        
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

    def create_restaurant_level_page(self):
        page, layout = self._create_scrollable_page()
        
        hero = self._create_onigiri_game_hero_card(
            tr("restaurant_level"), 
            tr("grow_restaurant_desc"),
            "restaurant_folder/restaurant_level.png",
            "restaurant_lvl_bg.png",
            "#B94632"
        )
        self._attach_hero_toggle(hero, self.restaurant_level_toggle)
        layout.addWidget(hero)

        # Name settings
        name_group, name_layout = self._create_inner_group(tr("restaurant_name"))
        progress = restaurant_level.manager.get_progress()
        if progress.level >= 5:
            self.restaurant_name_input = QLineEdit(progress.name)
            name_layout.addWidget(QLabel(tr("custom_name")))
            name_layout.addWidget(self.restaurant_name_input)
        else:
            name_layout.addWidget(QLabel(tr("reach_level_5").format(level=progress.level)))
        layout.addWidget(name_group)

        # Notifications & Visibility
        vis_group, vis_layout = self._create_inner_group(tr("notifications_visibility"))
        vis_layout.addWidget(self._create_toggle_row(self.restaurant_notifications_toggle, tr("show_levelup_notifications")))
        vis_layout.addWidget(self._create_toggle_row(self.restaurant_bar_toggle, tr("show_progress_sidebar")))
        vis_layout.addWidget(self._create_toggle_row(self.restaurant_reviewer_toggle, tr("show_level_reviewer")))
        layout.addWidget(vis_group)
        
        # Difficulty
        diff_group, diff_layout = self._create_inner_group(tr("difficulty_level"))
        
        vertical_layout = QVBoxLayout()
        vertical_layout.setSpacing(10)
        for data, btn in self.difficulty_widgets.items():
            vertical_layout.addWidget(btn)
            
        diff_layout.addLayout(vertical_layout)
        layout.addWidget(diff_group)

        # Reset
        reset_group, reset_layout = self._create_inner_group(tr("reset_progress_title"))
        reset_btn = QPushButton(tr("reset_restaurant_level"))
        reset_btn.setObjectName("dangerButton")
        reset_btn.clicked.connect(self._confirm_reset_restaurant_level)
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
        onigimon.manager.bridge.clear_cache()
        while self.onigimon_companion_grid_layout.count():
            item = self.onigimon_companion_grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for button in list(self.onigimon_companion_buttons.buttons()):
            self.onigimon_companion_buttons.removeButton(button)

        status = onigimon.manager.bridge.status()
        companions = onigimon.manager.get_available_companions() if status == "ready" else []
        active_id = self.onigimon_selected_companion_id or onigimon.manager.load().active_companion_id

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

        self.onigimon_companion_status_label.setText("Select your Onigimon companion.")
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

    def _select_onigimon_companion(self, ankimon_id):
        self.onigimon_selected_companion_id = str(ankimon_id)
        for pokemon in onigimon.manager.get_available_companions():
            if str(pokemon.get("ankimon_id")) == self.onigimon_selected_companion_id:
                current = onigimon.manager.load().companions.get(self.onigimon_selected_companion_id, {})
                self.onigimon_name_input.setText(str(current.get("display_name") or pokemon.get("name") or ""))
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
            icon_label.setPixmap(pixmap.scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
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
        desc = QLabel("Choose a Pokémon from Ankimon's Collection PC, then feed, play, and grow your companion while you study.")
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

        layout.addWidget(self._create_onigimon_hero())

        companion_group, companion_layout = self._create_inner_group("Companion")
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
        starter_note = QLabel("If Ankimon was just installed, finish choosing your first Pokémon there before selecting an Onigimon companion.")
        starter_note.setWordWrap(True)
        starter_note.setMinimumWidth(0)
        companion_layout.addWidget(starter_note)
        layout.addWidget(companion_group)

        rewards_group, rewards_layout = self._create_inner_group("Rewards")
        rewards_layout.addWidget(self._create_toggle_row(self.onigimon_notifications_toggle, "Show Onigimon notifications"))
        rewards_layout.addWidget(self._create_toggle_row(self.onigimon_daily_toggle, "Daily surprise item"))
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Reward item every"))
        interval_row.addWidget(self.onigimon_reward_interval_spinbox)
        interval_row.addStretch()
        rewards_layout.addLayout(interval_row)
        layout.addWidget(rewards_group)

        widget_group, widget_layout = self._create_inner_group("Widget")
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

        bridge_group, bridge_layout = self._create_inner_group("Ankimon Bridge")
        bridge_layout.addWidget(self._create_toggle_row(self.onigimon_ankimon_updates_toggle, "Allow Onigimon items to update Ankimon data"))
        bridge_note = QLabel("Keep this off if you only want Onigiri to track companion care. EXP Candy and medicine can be connected to Ankimon later through this bridge.")
        bridge_note.setWordWrap(True)
        bridge_layout.addWidget(bridge_note)
        layout.addWidget(bridge_group)

        credits_group, credits_layout = self._create_inner_group("Sprite Credits")
        credit = QLabel("PokéSprite sprite images are © Nintendo/Creatures Inc./GAME FREAK Inc. PokéSprite project code/data by msikma, MIT licensed.")
        credit.setWordWrap(True)
        credits_layout.addWidget(credit)
        layout.addWidget(credits_group)

        layout.addStretch()
        return page

    def create_focus_dango_page(self):
        page, layout = self._create_scrollable_page()
        hero = self._create_onigiri_game_hero_card(
            tr("focus_dango"),
            tr("dango_help_focus"),
            "dango.png",
            "dango_bg.png",
            "#f1aeca"
        )
        self._attach_hero_toggle(hero, self.focus_dango_toggle)
        layout.addWidget(hero)

        msg_group, msg_layout = self._create_inner_group(tr("focus_dango_messages"))
        msg_layout.addWidget(QLabel(tr("custom_messages_one_per_line")))
        msg_layout.addWidget(self.focus_dango_message_editor)
        layout.addWidget(msg_group)

        layout.addStretch()
        return page

    def create_mochi_messages_page(self):
        page, layout = self._create_scrollable_page()
        hero = self._create_onigiri_game_hero_card(
            tr("mochi_messages_title"),
            tr("mochi_cheer_on"),
            "mochi_messenger.png",
            "mochi_messages_bg.png",
            "#35421C"
        )
        self._attach_hero_toggle(hero, self.mochi_messages_toggle)
        layout.addWidget(hero)

        settings_group, settings_layout = self._create_inner_group(tr("settings"))
        
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel(tr("show_message_every")))
        interval_row.addWidget(self.mochi_interval_spinbox)
        interval_row.addStretch()
        settings_layout.addLayout(interval_row)
        
        settings_layout.addWidget(QLabel(tr("custom_messages_one_per_line")))
        settings_layout.addWidget(self.mochi_messages_editor)
        layout.addWidget(settings_group)

        layout.addStretch()
        return page

    def create_coming_soon_page(self):
        page, layout = self._create_scrollable_page()
        
        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.setSpacing(20)

        icon_label = QLabel("🎮")
        icon_label.setStyleSheet("font-size: 64px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(icon_label)

        title = QLabel(tr("coming_soon"))
        title.setStyleSheet("font-size: 32px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(title)

        desc = QLabel(tr("coming_soon_desc"))
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #888; font-size: 16px; max-width: 400px;")
        c_layout.addWidget(desc)

        layout.addStretch()
        layout.addWidget(container)
        layout.addStretch()
        return page

    # --- Actions ---

    def _confirm_reset_restaurant_level(self):
        if QMessageBox.question(self, tr("reset"), tr("reset_restaurant_confirm"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            restaurant_level.manager.reset_progress()
            showInfo(tr("restaurant_level_reset_info"))

    def _reset_coins(self):
        if QMessageBox.question(self, tr("reset"), tr("reset_coins_confirm"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            restaurant_level.manager.reset_coins()
            showInfo(tr("coins_reset_info"))

    def _reset_purchases(self):
        if QMessageBox.question(self, tr("reset"), tr("reset_purchases_confirm"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            restaurant_level.manager.reset_purchases()
            showInfo(tr("purchases_reset_info"))

    def save_settings(self):
        # Master Toggle
        self.current_config["gamificationMode"] = self.gamification_mode_toggle.isChecked()
        
        # Focused Gaming — if enabled, force restaurant notifications off
        focused = self.focused_gaming_toggle.isChecked()
        self.current_config["focusedGaming"] = focused
        
        # Update current_config from widgets
        # Restaurant Level
        res_conf = self.current_config.setdefault("restaurant_level", {})
        res_conf["enabled"] = self.restaurant_level_toggle.isChecked()
        res_conf["notifications_enabled"] = self.restaurant_notifications_toggle.isChecked()
        res_conf["show_profile_bar_progress"] = self.restaurant_bar_toggle.isChecked()
        res_conf["show_reviewer_header"] = self.restaurant_reviewer_toggle.isChecked()
        
        selected_diff = "Apprendice"
        for data, btn in self.difficulty_widgets.items():
            if btn.isChecked():
                selected_diff = data
                break
        res_conf["difficulty"] = selected_diff
        
        if hasattr(self, "restaurant_name_input"):
            restaurant_level.manager.set_restaurant_name(self.restaurant_name_input.text())

        # Onigimon
        oni_conf = self.current_config.setdefault("onigimon", {})
        oni_conf["enabled"] = self.onigimon_toggle.isChecked()
        oni_conf["notifications_enabled"] = self.onigimon_notifications_toggle.isChecked()
        oni_conf["daily_surprise_enabled"] = self.onigimon_daily_toggle.isChecked()
        oni_conf["allow_ankimon_updates"] = self.onigimon_ankimon_updates_toggle.isChecked()
        oni_conf["reward_interval"] = self.onigimon_reward_interval_spinbox.value()
        oni_conf["widget_style"] = self.onigimon_widget_style_combo.currentText()
        oni_conf["sprite_motion"] = self.onigimon_sprite_motion_combo.currentData()
        if self.onigimon_selected_companion_id:
            onigimon.manager.set_active_companion(str(self.onigimon_selected_companion_id))
            onigimon.manager.rename_active_companion(self.onigimon_name_input.text().strip())
        
        # Mochi
        mochi_conf = self.current_config.setdefault("mochi_messages", {})
        mochi_conf["enabled"] = self.mochi_messages_toggle.isChecked()
        mochi_conf["cards_interval"] = self.mochi_interval_spinbox.value()
        mochi_conf["messages"] = [l.strip() for l in self.mochi_messages_editor.toPlainText().split("\n") if l.strip()]

        # Focus Dango
        dango_conf = self.achievements_config.setdefault("focusDango", {})
        dango_conf["enabled"] = self.focus_dango_toggle.isChecked()
        dango_conf["messages"] = [l.strip() for l in self.focus_dango_message_editor.toPlainText().split("\n") if l.strip()]

        # Save config
        config.write_config(self.current_config)
        self.accept()
        if mw:
            mw.reset()

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

        self.setStyleSheet(f"""
            QDialog {{ background-color: {bg}; color: {fg}; }}
            QWidget#settingsSidebarWrapper {{
                background-color: transparent;
                border: none;
            }}
            #sidebarContainer {{ 
                background-color: transparent;
                border: none;
            }}
            QScrollArea#sidebarNavScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollArea#sidebarNavScrollArea QScrollBar:vertical {{
                border: none;
                background-color: {surface_bg};
                width: 8px;
                margin: 6px 0px 6px 6px;
                border-radius: 4px;
            }}
            QScrollArea#sidebarNavScrollArea QScrollBar::handle:vertical {{
                background-color: {muted};
                min-height: 38px;
                border-radius: 4px;
            }}
            QScrollArea#sidebarNavScrollArea QScrollBar::handle:vertical:hover {{
                background-color: {accent};
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
            /* Content container - same bg as dialog so only sidebar is distinct */
            QWidget#contentContainer {{
                background-color: {content_bg};
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
                border-radius: 16px;
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

            QWidget#gamificationModeHero, QWidget#focusedGamingHero {{ 
                background-color: {surface_bg}; 
                border: 1px solid {border}; 
                border-radius: 20px; 
            }}
            
            QWidget#innerGroup {{ background-color: {inner_group_bg}; border: 1px solid {border}; border-radius: 12px; }}
            
            /* General QPushButton fallback (for content area buttons only) */
            QPushButton {{ background-color: {surface_bg}; color: {fg}; border: 1px solid {border}; padding: 8px 12px; border-radius: 18px; }}
            QPushButton:pressed {{ background-color: {border}; }}
            
            QPushButton#dangerButton {{ color: #ff6b6b; font-weight: bold; border: 1px solid #ff6b6b; border-radius: 6px; padding: 8px; }}
            QPushButton#dangerButton:hover {{ background-color: #ff6b6b; color: white; }}
            
            QComboBox {{ background-color: {inner_group_bg}; color: {fg}; border: 1px solid {border}; border-radius: 4px; padding: 5px; }}
            QComboBox QAbstractItemView {{ background-color: {inner_group_bg}; color: {fg}; selection-background-color: {border}; }}
            
            QPushButton#difficultyCard {{
                background-color: {inner_group_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 8px;
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
                border-radius: 8px;
                padding: 4px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton#onigimonCompanionTile:hover {{
                border: 1px solid #70c6a6;
                background-color: {hover_bg};
            }}
            QPushButton#onigimonCompanionTile:checked {{
                border: 2px solid #70c6a6;
                background-color: rgba(112, 198, 166, 0.18);
            }}

            QPushButton#notificationPositionButton {{
                background-color: transparent;
                color: {fg};
                border: 1px solid {border};
                border-radius: 8px;
                font-size: 20px;
                padding: 0;
            }}
            QPushButton#notificationPositionButton:hover {{
                background-color: {hover_bg};
            }}
            QPushButton#notificationPositionButton:checked {{
                background-color: {accent};
                color: #ffffff;
                border: 1px solid {accent};
            }}
            QWidget#notificationPositionPreview {{
                border: 2px solid {border};
                border-radius: 12px;
                background-color: transparent;
            }}
            QLabel#notificationPositionPreviewRect {{
                background-color: {accent};
                border-radius: 4px;
            }}
            
            QLabel, QRadioButton {{ color: {fg}; }}
            QLineEdit, QSpinBox {{ background-color: {inner_group_bg}; color: {fg}; border: 1px solid {border}; border-radius: 4px; padding: 5px; }}
            QScrollBar:vertical {{ border: none; background: transparent; width: 8px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {border}; min-height: 20px; border-radius: 4px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                height: 0px; background: none; border: none;
            }}
        """)

_gamification_dialog = None

def open_gamification_settings():
    global _gamification_dialog
    if _gamification_dialog is not None:
        _gamification_dialog.close()
    
    addon_path = os.path.dirname(__file__)
    _gamification_dialog = GamificationSettingsDialog(
        parent=mw,
        addon_path=addon_path
    )
    _gamification_dialog.show()
