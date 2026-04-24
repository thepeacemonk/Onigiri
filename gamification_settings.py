import os
import copy
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QWidget, QSpinBox, QPlainTextEdit, QScrollArea, QGridLayout, QPixmap, 
    Qt, QFrame, QSizePolicy, QButtonGroup, QAbstractButton, QSignalBlocker,
    QColor, QPointF, QRectF, QPainter, QPainterPath, QPropertyAnimation,
    QEasingCurve, QStackedWidget, QMessageBox, QComboBox
)
from PyQt6.QtCore import pyqtSignal, pyqtProperty
from PyQt6.QtGui import QImage
from aqt import mw
from aqt.theme import theme_manager
from aqt.utils import showInfo
from aqt.qt import (
    QDesktopServices, QUrl
)

from . import config
from .config import DEFAULTS
from .gamification import restaurant_level
from .themes import THEMES
from .settings import FlowLayout

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

class DonationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Support Onigiri Development")
        self.setFixedWidth(500)
        # Simplified for this context, just a simple message box to minimize copying
        layout = QVBoxLayout(self)
        msg = QLabel("Onigiri is free and open-source. Your support helps me keep it update and better!\nChoose your preferred method below:")
        msg.setWordWrap(True)
        layout.addWidget(msg)
        
        paypal_btn = QPushButton("PayPal")
        paypal_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.paypal.com/donate/?hosted_button_id=HQUK49H7DEDF8")))
        layout.addWidget(paypal_btn)
        
        pix_btn = QPushButton("Pix (Brazil)")
        pix_label = QLabel("Chave Pix: gabrielcarusbr16@gmail.com")
        layout.addWidget(pix_btn)
        layout.addWidget(pix_label)
        
        close_btn = QPushButton("Close")
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
        self.setWindowTitle("Gamification Settings")

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
        content_area_layout.setSpacing(5)
        content_area_layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar setup - new colorful pill design
        sidebar_wrapper = QWidget()
        sidebar_wrapper.setFixedWidth(210)
        sidebar_wrapper_layout = QVBoxLayout(sidebar_wrapper)
        sidebar_wrapper_layout.setContentsMargins(15, 15, 15, 15)
        sidebar_wrapper_layout.setSpacing(8)

        # Main Sidebar Widget (the rounded container)
        sidebar_widget = QWidget()
        sidebar_widget.setObjectName("sidebarContainer")
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(10, 14, 10, 14)
        sidebar_layout.setSpacing(8)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Colored pill buttons
        self.sidebar_buttons = {}
        self.sidebar_button_group = QButtonGroup()
        self.sidebar_button_group.setExclusive(True)

        # Each item has (display_name, key, bg_color, text_color)
        gamification_items = [
            ("General",                "General",           "",         ""),
            ("Restaurant Level",       "Restaurant Level",  "#ffbd59",  "#000000"),
            ("Mr. Taiyaki Store",      "Mr. Taiyaki Store", "#a83e25",  "#ffffff"),
            ("Focus Dango",            "Focus Dango",       "#9d3d64",  "#ffffff"),
            ("Mochi Messages",         "Mochi Messages",    "#00bf63",  "#000000"),
            ("Coming Soon",            "Coming Soon",       "",         ""),
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
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("saveButton")
        self.save_button.setAutoDefault(False)
        self.save_button.clicked.connect(self.save_settings)
        sidebar_layout.addWidget(self.save_button)

        sidebar_wrapper_layout.addWidget(sidebar_widget)

        # Content Stack
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentStack")

        self.pages = {
            "General": self.create_general_page,
            "Restaurant Level": self.create_restaurant_level_page,
            "Mr. Taiyaki Store": self.create_mr_taiyaki_store_page,
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

        content_area_layout.addWidget(sidebar_wrapper)
        content_area_layout.addWidget(content_container)

        main_layout.addLayout(content_area_layout)
        self.apply_stylesheet()
        self._apply_pill_button_styles()

        # Default page
        self.navigate_to_page("General")

    def _apply_pill_button_styles(self):
        """Apply individual colored pill styles to each sidebar button."""
        is_dark = theme_manager.night_mode
        neutral_bg = "#3c3c3c" if is_dark else "#ffffff"
        neutral_fg = "#e0e0e0" if is_dark else "#000000"

        for key, btn in self.sidebar_buttons.items():
            bg = btn.property("gameBgColor")
            fg_c = btn.property("gameTextColor")
            if not bg:
                bg, fg_c = neutral_bg, neutral_fg

            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {fg_c};
                    border: none;
                    border-radius: 19px;
                    min-height: 38px;
                    max-height: 38px;
                    padding: 0px 14px;
                    font-size: 13px;
                    font-weight: bold;
                    text-align: center;
                }}
                QPushButton:checked {{
                    background-color: {bg};
                    color: {fg_c};
                    border: 3px solid rgba(255,255,255,0.85);
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

        # Onigiri Sync Toggle
        self.ankiweb_sync_toggle = AnimatedToggleButton(accent_color="#27ae60")
        self.ankiweb_sync_toggle.setChecked(bool(self.current_config.get("ankiweb_sync_enabled", False)))
        
        restaurant_conf = self.current_config.get("restaurant_level", {})
        self.restaurant_level_toggle = AnimatedToggleButton(accent_color="#B94632")
        self.restaurant_level_toggle.setChecked(bool(restaurant_conf.get("enabled", False)))
        self.restaurant_notifications_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.restaurant_notifications_toggle.setChecked(bool(restaurant_conf.get("notifications_enabled", True)))
        self.restaurant_bar_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.restaurant_bar_toggle.setChecked(bool(restaurant_conf.get("show_profile_bar_progress", True)))
        self.restaurant_reviewer_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.restaurant_reviewer_toggle.setChecked(bool(restaurant_conf.get("show_reviewer_header", True)))
        
        # Difficulty Setting
        self.restaurant_difficulty_group = QButtonGroup()
        self.restaurant_difficulty_group.setExclusive(True)
        
        self.difficulty_widgets = {}
        diffs = [
            ("Apprendice", "Apprentice (1x)", "The journey begins! Start learning the ropes of the kitchen.", "Apprendice", "🧑‍🍳"),
            ("Cook", "Cook (2x)", "You know your way around. Things are heating up!", "Cook", "🍳"),
            ("Chef", "Chef (4x)", "You've become a master of your craft, and now the challenge is here.", "Chef", "🔪")
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
        self.mochi_interval_spinbox.setSuffix(" cards")
        self.mochi_interval_spinbox.setValue(int(self.mochi_messages_config.get("cards_interval", 15) or 1))
        
        messages_list = self.mochi_messages_config.get("messages") or []
        messages_text = "\n".join([str(item).strip() for item in messages_list if str(item).strip()])
        self.mochi_messages_editor = QPlainTextEdit(messages_text)
        self.mochi_messages_editor.setMinimumHeight(120)

        # Focus Dango
        focus_dango_conf = self.achievements_config.get("focusDango", {})
        self.focus_dango_toggle = AnimatedToggleButton(accent_color="#61252D")
        self.focus_dango_toggle.setChecked(bool(focus_dango_conf.get("enabled", False)))
        
        dango_messages = focus_dango_conf.get("messages") or ["Don't give up!", "Stay focused!"]
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
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
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

        text_layout = QVBoxLayout()
        t_label = QLabel(title)
        t_label.setStyleSheet(f"font-weight: bold; font-size: 24px; color: {text_color}; background: transparent;")
        s_label = QLabel(subtitle)
        s_label.setWordWrap(True)
        s_label.setStyleSheet(f"color: {text_color}; background: transparent;")
        text_layout.addWidget(t_label)
        text_layout.addWidget(s_label)
        layout.addLayout(text_layout, 1)

        bg_path = os.path.join(self.addon_path, "system_files", "gamification_images", background_filename)
        if not os.path.exists(bg_path):
            bg_path = os.path.join(self.addon_path, "system_files", background_filename)
        
        if os.path.exists(bg_path):
            css_path = bg_path.replace('\\', '/')
            card.setStyleSheet(card.styleSheet() + f"QFrame#achievementsHeroCard {{ background-image: url('{css_path}'); background-position: left center; background-repeat: repeat-x; background-size: auto 100%; }}")
        
        return card

    def _attach_hero_toggle(self, card, toggle):
        card.layout().addWidget(toggle, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

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
        
        # Icon
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(__file__), "system_files", "gamification_images", "gamification.png")
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon_label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        hero_layout.addWidget(icon_label)
        
        # Text
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("Gamification Mode")
        title.setStyleSheet("font-size: 18px; font-weight: bold; background: transparent;")
        text_layout.addWidget(title)
        
        desc = QLabel("Level up your restaurant, unlock new themes, enjoy Mochi's encouragements, and stay focused with Dango.")
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
        
        # Icon - emoji fallback if no image found
        focus_icon_label = QLabel()
        focus_icon_path = os.path.join(os.path.dirname(__file__), "system_files", "gamification_images", "focused_gaming.png")
        if os.path.exists(focus_icon_path):
            focus_pixmap = QPixmap(focus_icon_path)
            if not focus_pixmap.isNull():
                focus_icon_label.setPixmap(focus_pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            focus_icon_label.setText("🎯")
            focus_icon_label.setStyleSheet("font-size: 40px; background: transparent;")
        focused_layout.addWidget(focus_icon_label)
        
        focus_text = QWidget()
        focus_text_layout = QVBoxLayout(focus_text)
        focus_text_layout.setContentsMargins(0, 0, 0, 0)
        
        focus_title = QLabel("Focused Gaming")
        focus_title.setStyleSheet("font-size: 18px; font-weight: bold; background: transparent;")
        focus_text_layout.addWidget(focus_title)
        
        focus_desc = QLabel("Hide all gamification notifications during reviews. Restaurant Level notifications will be turned off and locked while active.")
        focus_desc.setWordWrap(True)
        focus_desc.setStyleSheet("font-size: 13px; color: #888; background: transparent;")
        focus_text_layout.addWidget(focus_desc)
        
        focused_layout.addWidget(focus_text, 1)
        focused_layout.addWidget(self.focused_gaming_toggle)
        
        layout.addWidget(focused_card)
        
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
        
        # ---- Hero 3: AnkiWeb Sync ----
        sync_card = QWidget()
        sync_card.setObjectName("ankiwebSyncHero")
        sync_card.setFixedHeight(120)
        
        sync_layout = QHBoxLayout(sync_card)
        sync_layout.setSpacing(20)
        sync_layout.setContentsMargins(20, 20, 20, 20)
        
        sync_icon_label = QLabel()
        sync_icon_label.setText("☁️")
        sync_icon_label.setStyleSheet("font-size: 40px; background: transparent;")
        sync_layout.addWidget(sync_icon_label)
        
        sync_text = QWidget()
        sync_text_layout = QVBoxLayout(sync_text)
        sync_text_layout.setContentsMargins(0, 0, 0, 0)
        
        sync_title = QLabel("AnkiWeb Cloud Sync")
        sync_title.setStyleSheet("font-size: 18px; font-weight: bold; background: transparent;")
        sync_text_layout.addWidget(sync_title)
        
        sync_desc = QLabel("Synchronize your Onigiri progress, custom icons, and themes across all your devices using Anki's media sync.")
        sync_desc.setWordWrap(True)
        sync_desc.setStyleSheet("font-size: 13px; color: #888; background: transparent;")
        sync_text_layout.addWidget(sync_desc)
        
        sync_layout.addWidget(sync_text, 1)
        sync_layout.addWidget(self.ankiweb_sync_toggle)
        
        layout.addWidget(sync_card)
        
        layout.addStretch()
        
        return page

    def create_restaurant_level_page(self):
        page, layout = self._create_scrollable_page()
        
        hero = self._create_onigiri_game_hero_card(
            "Restaurant Level", 
            "Grow your restaurant by completing reviews!",
            "restaurant_folder/restaurant_level.png",
            "restaurant_lvl_bg.png",
            "#B94632"
        )
        self._attach_hero_toggle(hero, self.restaurant_level_toggle)
        layout.addWidget(hero)

        # Name settings
        name_group, name_layout = self._create_inner_group("Restaurant Name")
        progress = restaurant_level.manager.get_progress()
        if progress.level >= 5:
            self.restaurant_name_input = QLineEdit(progress.name)
            name_layout.addWidget(QLabel("Custom Name:"))
            name_layout.addWidget(self.restaurant_name_input)
        else:
            name_layout.addWidget(QLabel(f"🔒 Reach Level 5 to unlock custom names. (Current: {progress.level})"))
        layout.addWidget(name_group)

        # Notifications & Visibility
        vis_group, vis_layout = self._create_inner_group("Notifications & Visibility")
        vis_layout.addWidget(self._create_toggle_row(self.restaurant_notifications_toggle, "Show level-up notifications"))
        vis_layout.addWidget(self._create_toggle_row(self.restaurant_bar_toggle, "Show progress on sidebar"))
        vis_layout.addWidget(self._create_toggle_row(self.restaurant_reviewer_toggle, "Show level in reviewer header"))
        layout.addWidget(vis_group)
        
        # Difficulty
        diff_group, diff_layout = self._create_inner_group("Difficulty Level")
        
        vertical_layout = QVBoxLayout()
        vertical_layout.setSpacing(10)
        for data, btn in self.difficulty_widgets.items():
            vertical_layout.addWidget(btn)
            
        diff_layout.addLayout(vertical_layout)
        layout.addWidget(diff_group)

        # Reset
        reset_group, reset_layout = self._create_inner_group("Reset Progress")
        reset_btn = QPushButton("Reset Restaurant Level")
        reset_btn.setObjectName("dangerButton")
        reset_btn.clicked.connect(self._confirm_reset_restaurant_level)
        reset_layout.addWidget(reset_btn)
        layout.addWidget(reset_group)
        
        layout.addStretch()
        return page

    def create_mr_taiyaki_store_page(self):
        page, layout = self._create_scrollable_page()
        hero = self._create_onigiri_game_hero_card(
            "Mr. Taiyaki Store",
            "Manage your Mr. Taiyaki Store settings.",
            "mr_taiyaki.png",
            "restaurant_folder/wooden_bg.png",
            "#ffffff"
        )
        layout.addWidget(hero)

        coins_group, coins_layout = self._create_inner_group("Reset Coins")
        reset_coins_btn = QPushButton("Reset Coins")
        reset_coins_btn.clicked.connect(self._reset_coins)
        coins_layout.addWidget(reset_coins_btn)
        layout.addWidget(coins_group)

        purchases_group, purchases_layout = self._create_inner_group("Reset Purchases")
        reset_purchases_btn = QPushButton("Reset Purchases")
        reset_purchases_btn.clicked.connect(self._reset_purchases)
        purchases_layout.addWidget(reset_purchases_btn)
        layout.addWidget(purchases_group)

        layout.addStretch()
        return page

    def create_focus_dango_page(self):
        page, layout = self._create_scrollable_page()
        hero = self._create_onigiri_game_hero_card(
            "Focus Dango",
            "Dango-san will help you stay focused!",
            "dango.png",
            "dango_bg.png",
            "#f1aeca"
        )
        self._attach_hero_toggle(hero, self.focus_dango_toggle)
        layout.addWidget(hero)

        msg_group, msg_layout = self._create_inner_group("Focus Dango Messages")
        msg_layout.addWidget(QLabel("Custom messages (one per line):"))
        msg_layout.addWidget(self.focus_dango_message_editor)
        layout.addWidget(msg_group)

        layout.addStretch()
        return page

    def create_mochi_messages_page(self):
        page, layout = self._create_scrollable_page()
        hero = self._create_onigiri_game_hero_card(
            "Mochi Messages",
            "Let Mochi cheer you on during reviews.",
            "mochi_messenger.png",
            "mochi_messages_bg.png",
            "#35421C"
        )
        self._attach_hero_toggle(hero, self.mochi_messages_toggle)
        layout.addWidget(hero)

        settings_group, settings_layout = self._create_inner_group("Settings")
        
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Show message every"))
        interval_row.addWidget(self.mochi_interval_spinbox)
        interval_row.addStretch()
        settings_layout.addLayout(interval_row)
        
        settings_layout.addWidget(QLabel("Custom messages (one per line):"))
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

        title = QLabel("Coming Soon")
        title.setStyleSheet("font-size: 32px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(title)

        desc = QLabel("We're working on new mini-games to make your study sessions even more fun. Stay tuned!")
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
        if QMessageBox.question(self, "Reset", "Reset Restaurant Level progress?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            restaurant_level.manager.reset_progress()
            showInfo("Restaurant Level reset.")

    def _reset_coins(self):
        if QMessageBox.question(self, "Reset", "Reset Taiyaki Coins?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            restaurant_level.manager.reset_coins()
            showInfo("Coins reset.")

    def _reset_purchases(self):
        if QMessageBox.question(self, "Reset", "Reset all purchases?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            restaurant_level.manager.reset_purchases()
            showInfo("Purchases reset.")

    def save_settings(self):
        # Master Toggle
        self.current_config["gamificationMode"] = self.gamification_mode_toggle.isChecked()
        self.current_config["ankiweb_sync_enabled"] = self.ankiweb_sync_toggle.isChecked()
        
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
        is_dark = theme_manager.night_mode
        if is_dark:
            # Dialog bg matches content panel bg — only 2 visible layers: sidebar + content
            bg = "#2e2e2e"
            content_bg = "#2e2e2e"
            fg = "#e0e0e0"
            sidebar_bg = "#1a1a1a"
            inner_group_bg = "#252525"
            border = "#444444"
            hover_bg = "#333333"
        else:
            bg = "#f0f0f0"
            content_bg = "#f0f0f0"
            fg = "#212121"
            sidebar_bg = "#d5d5d5"
            inner_group_bg = "#ffffff"
            border = "#d0d0d0"
            hover_bg = "#e8e8e8"

        self.setStyleSheet(f"""
            QDialog {{ background-color: {bg}; color: {fg}; }}
            #sidebarContainer {{ 
                background-color: {sidebar_bg}; 
                border-radius: 20px; 
            }}
            /* Content container - same bg as dialog so only sidebar is distinct */
            QWidget#contentContainer {{
                background-color: {content_bg};
                border-radius: 16px;
            }}
            QStackedWidget#contentStack {{
                background-color: transparent;
            }}
            
            /* Save button - always white pill with fixed height */
            QPushButton#saveButton {{
                background-color: #ffffff;
                color: #000000;
                border: none;
                border-radius: 19px;
                min-height: 38px;
                max-height: 38px;
                padding: 0px 14px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton#saveButton:hover {{
                background-color: #f0f0f0;
            }}
            QPushButton#saveButton:pressed {{
                background-color: #dddddd;
            }}

            QWidget#gamificationModeHero, QWidget#focusedGamingHero {{ 
                background-color: {'#353535' if is_dark else '#ffffff'}; 
                border: 1px solid {border}; 
                border-radius: 20px; 
            }}
            
            QWidget#innerGroup {{ background-color: {inner_group_bg}; border: 1px solid {border}; border-radius: 12px; }}
            
            /* General QPushButton fallback (for content area buttons only) */
            QPushButton {{ background-color: {'#4a4a4a' if is_dark else '#e8e8e8'}; color: {fg}; border: 1px solid {border}; padding: 8px 12px; border-radius: 6px; }}
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
