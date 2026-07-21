"""
Mr. Taiyaki Store - Pure PyQt Implementation
Maintains the exact visual style of the HTML/CSS version
"""

import json
import requests
import hashlib
from aqt import mw
from aqt.qt import *
import os
import tempfile
from .. import config
from ..translations import tr
from ..onigiri_notifications import notify as tooltip
from ..onigiri_notifications import notify_info as showInfo
from . import redeem_net

# SVG rendering imports
try:
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtGui import QImage, QPainter, QPixmap, QIcon
    from PyQt6.QtCore import QTimer, QRectF
except ImportError:
    # Fallback for PyQt5
    from PyQt5.QtSvg import QSvgRenderer
    from PyQt5.QtGui import QImage, QPainter, QPixmap, QIcon
    from PyQt5.QtCore import QTimer, QRectF

import random


SHOP_API_URL = "https://script.google.com/macros/s/AKfycbyQl6b_cPnXJEJeEJryvsuRzZYclfIt_LWN1Mqqf63FjzCbKdPKV_uHIgYtHIXmAbnB/exec"

# Flat dark theme for the store window/cards (see Tayiaki Shop redesign mockup).
# True neutral grays (equal R/G/B) - the previous values had the blue channel
# running a few points hotter than red/green, giving everything a cool/bluish cast.
def get_store_theme():
    dark = bool(mw and getattr(mw, 'pm', None) and mw.pm.night_mode())
    return {
        "STORE_BG": "#1A1A1A" if dark else "#F4F6F8",
        "NAV_PILL_BG": "#2A2A2A" if dark else "#E2E6EA",
        "NAV_ACTIVE_BG": "#EAEAEA" if dark else "#FFFFFF",
        "NAV_ACTIVE_TEXT": "#1A1A1A" if dark else "#2C3E50",
        "NAV_INACTIVE_TEXT": "#A8A8A8" if dark else "#7F8C8D",
        "NAV_HOVER_BG": "rgba(255, 255, 255, 0.08)" if dark else "rgba(0, 0, 0, 0.05)",
        "NAV_HOVER_TEXT": "#FFFFFF" if dark else "#2C3E50",
        "CARD_BACK_BG": "#242424" if dark else "#FFFFFF",
        "PANEL_BG": "#242424" if dark else "#FFFFFF",
        "ACCENT_GOLD": "#E8B23D",
        "ACCENT_GOLD_HOVER": "#F0C463",
        "TEXT_PRIMARY": "#FFFFFF" if dark else "#2C3E50",
        "TEXT_SECONDARY": "rgba(255, 255, 255, 0.65)" if dark else "rgba(44, 62, 80, 0.65)",
        "WALLET_BG": "rgba(255, 255, 255, 0.07)" if dark else "rgba(0, 0, 0, 0.05)",
        "CARD_DESC_TEXT": "rgba(255, 255, 255, 0.85)" if dark else "#4A5568",
        "BACK_BTN_BG": "rgba(255, 255, 255, 0.1)" if dark else "rgba(0, 0, 0, 0.08)",
        "BACK_BTN_HOVER": "rgba(255, 255, 255, 0.18)" if dark else "rgba(0, 0, 0, 0.15)",
        "ACTION_LOCKED_BG": "rgba(255, 255, 255, 0.35)" if dark else "rgba(0, 0, 0, 0.1)",
        "ACTION_LOCKED_TEXT": "rgba(255, 255, 255, 0.8)" if dark else "rgba(0, 0, 0, 0.4)",
        "ACTION_CANNOT_AFFORD_BG": "rgba(255, 255, 255, 0.35)" if dark else "rgba(0, 0, 0, 0.1)",
        "ACTION_CANNOT_AFFORD_TEXT": "rgba(60, 60, 60, 0.7)" if dark else "rgba(0, 0, 0, 0.4)",
        "BTN_TEXT_ON_GOLD": "#1A1A1A" if dark else "#FFFFFF",
    }


def _styled(widget):
    """Plain QWidget/QStackedWidget instances ignore a stylesheet background-color
    (opaque or transparent) unless WA_StyledBackground is set - without this they
    fall back to painting Anki's native palette background, hiding whatever
    color/transparency the stylesheet asked for."""
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return widget


def _load_scaled_pixmap(path, width, height):
    """Load an image and scale it for display at the screen's actual device
    pixel ratio, so sprites stay crisp on HiDPI/Retina displays instead of
    rendering soft (scaling to literal width/height treats them as physical
    pixels, which is roughly half the needed resolution on a 2x screen)."""
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return pixmap
    screen = QApplication.primaryScreen()
    ratio = screen.devicePixelRatio() if screen else 1.0
    target = QSize(int(width * ratio), int(height * ratio))
    scaled = pixmap.scaled(target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    scaled.setDevicePixelRatio(ratio)
    return scaled


_COIN_SALT = "onigiri_secret_salt_2024"  # Simple salt for basic integrity

def generate_coin_token(coins: int) -> str:
    """Generate a security token for the coin amount."""
    data = f"{coins}:{_COIN_SALT}"
    return hashlib.sha256(data.encode()).hexdigest()

def verify_coin_data(coins: int, token: str) -> bool:
    """Verify that the coin amount matches the security token."""
    expected = generate_coin_token(coins)
    return token == expected


class StoreItemCard(QWidget):
    """A single store item card widget with flip functionality"""
    
    def __init__(self, item_id, item_data, is_owned, is_equipped, coins, addon_path, store_window, parent=None):
        super().__init__(parent)
        self.theme = get_store_theme()
        self.item_id = item_id
        self.item_data = item_data
        self.is_owned = is_owned
        self.is_equipped = is_equipped
        self.user_coins = coins
        self.addon_path = addon_path
        self.store_window = store_window # Reference to main window for callbacks
        self.theme_color = item_data.get('theme') or '#888888'
        self.is_flipped = False  # Track flip state

        self.setup_ui()

    def setup_ui(self):
        """Create the card UI with front and back sides"""
        _styled(self)

        # Main container for stacking front and back
        self.stack = _styled(QStackedWidget())
        self.stack.setStyleSheet("QStackedWidget { background: transparent; }")

        # Create front side
        self.front_widget = self.create_front_side()
        self.stack.addWidget(self.front_widget)

        # Create back side (description)
        self.back_widget = self.create_back_side()
        self.stack.addWidget(self.back_widget)

        # Set up main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.stack)

        self.setLayout(main_layout)

        # Card container styling: flat, fully colored with the restaurant's theme color
        self.setStyleSheet(f"""
            StoreItemCard {{
                background-color: {self.theme_color};
                border-radius: 20px;
            }}
        """)

    def create_front_side(self):
        """Create the front side of the card: name pill on top, image in the
        middle, and a price/action pill at the bottom (the mockup's flat-color
        card with white pill badges)."""
        front = _styled(QWidget())
        front.setStyleSheet("background: transparent;")
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 16)
        layout.setSpacing(10)

        # --- Top row: name pill + info button ---
        top_row = _styled(QWidget())
        top_row.setStyleSheet("background: transparent;")
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        name_pill = QLabel(self.item_data['name'])
        name_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_pill.setWordWrap(True)
        name_pill.setStyleSheet(f"""
            QLabel {{
                background-color: #FFFFFF;
                color: {self.theme_color};
                border-radius: 14px;
                font-size: 13px;
                font-weight: 700;
                padding: 7px 12px;
            }}
        """)
        top_layout.addWidget(name_pill, 1)

        # Info icon button using SVG, tinted white for visibility on any theme color
        info_btn = QPushButton()
        info_btn.setFixedSize(28, 28)
        info_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        svg_path = os.path.join(self.addon_path, "system_files/system_icons/unavailable_for_users/info-circle.svg")
        if os.path.exists(svg_path):
            with open(svg_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()

            # This icon is drawn with stroke="currentColor" (not fill) - recolor that,
            # since currentColor has no meaning outside a CSS context and renders invisible.
            svg_colored = svg_content.replace('currentColor', '#FFFFFF')

            renderer = QSvgRenderer(svg_colored.encode('utf-8'))
            image = QImage(28, 28, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)

            painter = QPainter(image)
            renderer.render(painter)
            painter.end()

            info_btn.setIcon(QIcon(QPixmap.fromImage(image)))
            info_btn.setIconSize(QSize(20, 20))

        info_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.25);
                border: none;
                border-radius: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.4);
            }
        """)
        info_btn.clicked.connect(self.flip_card)
        top_layout.addWidget(info_btn)

        top_row.setLayout(top_layout)
        layout.addWidget(top_row)

        # --- Middle: item image, sitting directly on the theme-colored card ---
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setStyleSheet("background: transparent;")
        image_name = self.item_data.get('image')
        if image_name:
            img_path = os.path.join(
                self.addon_path,
                "system_files/gamification_images/nook_folder",
                image_name
            )
            if os.path.exists(img_path):
                image_label.setPixmap(_load_scaled_pixmap(img_path, 150, 150))
        layout.addWidget(image_label, 1)

        # --- Bottom: price/action pill (also the click target) ---
        self.action_btn = QPushButton()
        self.action_btn.setFixedHeight(36)
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_action_button()
        layout.addWidget(self.action_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        front.setLayout(layout)
        return front

    def refresh_action_button(self):
        """(Re)style the bottom pill based on owned/equipped/affordability state."""
        price_value = self.item_data['price']
        is_special_price = isinstance(price_value, str)

        try:
            self.action_btn.clicked.disconnect()
        except TypeError:
            pass

        self.action_btn.setIcon(QIcon())

        pill_style = """
            QPushButton {{
                border: none;
                border-radius: 18px;
                font-weight: 700;
                font-size: 13px;
                padding: 0 18px;
                {extra}
            }}
        """

        if self.is_equipped:
            self.action_btn.setText(tr("close_restaurant"))
            self.action_btn.setEnabled(True)
            self.action_btn.setStyleSheet(pill_style.format(extra=f"background-color: {self.theme_color}; color: #FFFFFF; border: 2px solid #FFFFFF;"))
            self.action_btn.clicked.connect(lambda: self.store_window.equip_item('default'))
        elif self.is_owned:
            self.action_btn.setText(tr("open_restaurant"))
            self.action_btn.setEnabled(True)
            self.action_btn.setStyleSheet(pill_style.format(extra=f"background-color: #FFFFFF; color: {self.theme_color};"))
            self.action_btn.clicked.connect(lambda: self.store_window.equip_item(self.item_id))
        elif is_special_price:
            self.action_btn.setText(tr("locked"))
            self.action_btn.setEnabled(False)
            self.action_btn.setStyleSheet(pill_style.format(extra=f"background-color: {self.theme['ACTION_LOCKED_BG']}; color: {self.theme['ACTION_LOCKED_TEXT']};"))
        else:
            coin_path = os.path.join(self.addon_path, "system_files/gamification_images/Tayaki_coin.webp")
            if os.path.exists(coin_path):
                self.action_btn.setIcon(QIcon(coin_path))
                self.action_btn.setIconSize(QSize(16, 16))
            self.action_btn.setText(f" {price_value}")
            can_afford = self.user_coins >= price_value

            if can_afford:
                self.action_btn.setEnabled(True)
                self.action_btn.setStyleSheet(pill_style.format(extra="background-color: #FFFFFF; color: #2c2c2c;"))
                self.action_btn.clicked.connect(lambda: self.store_window.buy_item(self.item_id))
            else:
                self.action_btn.setEnabled(False)
                self.action_btn.setStyleSheet(pill_style.format(extra=f"background-color: {self.theme['ACTION_CANNOT_AFFORD_BG']}; color: {self.theme['ACTION_CANNOT_AFFORD_TEXT']};"))
    
    def _back_note(self, text, text_color, bg_rgba):
        """A small rounded note pill for the back of the card (flavor text,
        lock requirements, etc.) - same pill language as the front side."""
        note = QLabel(text)
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {text_color};
                background-color: {bg_rgba};
                padding: 10px 14px;
                border-radius: 14px;
                font-weight: 700;
            }}
        """)
        return note

    def create_back_side(self):
        """Create the back side of the card with the item's description."""
        back = _styled(QWidget())
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 18)
        layout.setSpacing(12)

        # Back button (mirrors the front side's circular info button)
        top_row = _styled(QWidget())
        top_row.setStyleSheet("background: transparent;")
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)

        back_btn = QPushButton("←")
        back_btn.setFixedSize(28, 28)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setToolTip(tr('back'))
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme['BACK_BTN_BG']};
                color: {self.theme_color};
                border: none;
                border-radius: 14px;
                font-size: 15px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                background-color: {self.theme['BACK_BTN_HOVER']};
            }}
        """)
        back_btn.clicked.connect(self.flip_card)
        top_layout.addWidget(back_btn)
        top_layout.addStretch()
        top_row.setLayout(top_layout)
        layout.addWidget(top_row)

        # Title, colored with the restaurant's own theme color so the back
        # side still reads as "the same card" rather than a generic panel
        title = QLabel(self.item_data['name'])
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: 800;
                color: {self.theme_color};
            }}
        """)
        layout.addWidget(title)

        # Description
        description = self.item_data.get('description', tr("no_description_available"))
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        desc_label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                color: {self.theme['CARD_DESC_TEXT']};
            }}
        """)
        layout.addWidget(desc_label, 1)

        # Special flavor note, one per item id that has one
        special_notes = {
            "santas_coffee": ("santas_coffee_special", "#A8D8FF", "rgba(168, 216, 255, 0.16)"),
            "focus_dango": ("focus_dango_special", "#DC90B8", "rgba(220, 144, 184, 0.16)"),
            "motivated_mochi": ("motivated_mochi_special", "#6EC170", "rgba(110, 193, 112, 0.16)"),
            "lunar_new_year": ("lunar_new_year_special", "#FFD166", "rgba(210, 43, 43, 0.22)"),
            "astronigiri": ("astronigiri_special", "#A8D8FF", "rgba(116, 130, 155, 0.22)"),
        }
        if self.item_id in special_notes:
            key, text_color, bg_rgba = special_notes[self.item_id]
            layout.addWidget(self._back_note(tr(key), text_color, bg_rgba))

        # Lock requirement note for evolutions with unmet prerequisites
        prerequisite_info = self.item_data.get('prerequisite_info')
        if prerequisite_info:
            layout.addWidget(self._back_note(prerequisite_info, "#FFB347", "rgba(255, 179, 71, 0.16)"))

        back.setLayout(layout)

        back.setStyleSheet(f"""
            QWidget {{
                background-color: {self.theme['CARD_BACK_BG']};
                border-radius: 20px;
            }}
        """)

        return back

    def flip_card(self):
        """Toggle between front and back of card"""
        self.is_flipped = not self.is_flipped
        if self.is_flipped:
            self.stack.setCurrentIndex(1)  # Show back
        else:
            self.stack.setCurrentIndex(0)  # Show front

    def update_state(self, is_owned, is_equipped, user_coins):
        """Update the card's state without recreating the widget"""
        self.is_owned = is_owned
        self.is_equipped = is_equipped
        self.user_coins = user_coins
        self.refresh_action_button()


class CoinRedemptionDialog(QDialog):
    """Custom dialog for coin redemption"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("get_more_coins"))
        self.setFixedWidth(420)
        self.addon_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.setup_ui()

    def setup_ui(self):
        dark = bool(mw and mw.pm and mw.pm.night_mode())
        theme = get_store_theme()
        bg = "#1b1f24" if dark else "#f4f6f8"
        panel = "#22272e" if dark else "#ffffff"
        border = "#33393f" if dark else "#e3e7ea"
        text = "#eef1f4" if dark else "#1c2530"
        muted = "#8b94a0" if dark else "#69727e"
        accent_bg = "rgba(232, 178, 61, 0.18)" if dark else "rgba(232, 178, 61, 0.12)"

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 22)
        layout.setSpacing(16)

        hero = _styled(QWidget())
        hero.setObjectName("coinHeroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        coin_icon = QLabel()
        coin_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        coin_icon.setFixedSize(40, 40)
        coin_path = os.path.join(self.addon_path, "system_files/gamification_images/Tayaki_coin.webp")
        if os.path.exists(coin_path):
            coin_icon.setPixmap(_load_scaled_pixmap(coin_path, 26, 26))
        coin_icon.setStyleSheet(f"""
            QLabel {{
                background: {accent_bg};
                border-radius: 10px;
            }}
        """)
        top_row.addWidget(coin_icon)

        title = QLabel(tr("get_more_coins"))
        title.setStyleSheet(f"color: {text}; font-size: 16px; font-weight: 600;")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(title, 1)
        hero_layout.addLayout(top_row)

        subtitle = QLabel(tr("coin_level_tip"))
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {muted}; font-size: 13px; font-weight: 400;")
        hero_layout.addWidget(subtitle)

        # Support tip, then the buy-codes button on its own row underneath,
        # both folded into the hero card so the dialog reads as two zones
        # (info card, then the code form) instead of loose floating lines.
        support_text = QLabel(tr("support_onigiri_coins"))
        support_text.setWordWrap(True)
        support_text.setStyleSheet(f"color: {muted}; font-size: 12px; font-weight: 400;")
        hero_layout.addWidget(support_text)

        buy_row = QHBoxLayout()
        buy_row.addStretch(1)
        buy_btn = QPushButton(tr("buy_coin_codes"))
        buy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        buy_btn.setFixedHeight(32)
        buy_btn.setMinimumWidth(220)
        buy_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://buymeacoffee.com/peacemonk/extras"))
        )
        buy_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {theme['ACCENT_GOLD']};
                border: 1px solid {border};
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{ background: {accent_bg}; }}
        """)
        buy_row.addWidget(buy_btn)
        buy_row.addStretch(1)
        hero_layout.addLayout(buy_row)

        hero.setStyleSheet(f"""
            QWidget#coinHeroCard {{
                background: {panel};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)
        layout.addWidget(hero)

        # Code controls
        code_label = QLabel(tr("have_a_code"))
        code_label.setStyleSheet(f"color: {text}; font-size: 13px; font-weight: 500;")
        layout.addWidget(code_label)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(tr("paste_code_here"))
        self.input_field.setFixedHeight(40)
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background: {panel};
                color: {text};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 0 12px;
                font-size: 14px;
                font-weight: 400;
            }}
            QLineEdit:focus {{
                border-color: {theme['ACCENT_GOLD']};
            }}
        """)
        layout.addWidget(self.input_field)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)

        cancel_btn = QPushButton(tr("cancel"))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFixedHeight(34)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {muted};
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
                padding: 0 12px;
            }}
            QPushButton:hover {{ color: {text}; }}
        """)

        redeem_btn = QPushButton(tr("redeem_code"))
        redeem_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        redeem_btn.setFixedHeight(34)
        redeem_btn.clicked.connect(self.accept)
        redeem_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme['ACCENT_GOLD']};
                color: {theme['BTN_TEXT_ON_GOLD']};
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background: {theme['ACCENT_GOLD_HOVER']}; }}
        """)

        buttons.addWidget(cancel_btn)
        buttons.addWidget(redeem_btn)
        layout.addLayout(buttons)

        self.setLayout(layout)
        self.setStyleSheet(f"QDialog {{ background: {bg}; }}")

    def get_code(self):
        return self.input_field.text().strip()


class CoinRainOverlay(QWidget):
    """Transparent overlay for coin rain animation"""
    def __init__(self, parent, coin_pixmap):
        super().__init__(parent)
        self.coin_pixmap = coin_pixmap
        self.coins = [] # List of dicts: x, y, speed, scale
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(parent.size())
        
        # Initialize coins with grid distribution to avoid clutter
        cols = 8
        rows = 5
        # Use fixed dimensions for generation to ensure good distribution
        # regardless of current widget size state
        gen_width = 400
        gen_height = 400
        cell_width = gen_width / cols
        cell_height = gen_height / rows
        
        for r in range(rows):
            for c in range(cols):
                # Add randomness but keep within cell
                # Ensure x fits in cell (coin is approx 30px)
                x = c * cell_width + random.uniform(0, max(0, cell_width - 35))
                
                # Y is negative to start above/at top
                # Distribute vertically
                y = -(r * cell_height + random.uniform(0, cell_height))
                
                self.coins.append({
                    'x': x,
                    'y': y,
                    'speed': random.randint(1, 3),
                    'scale': random.uniform(0.6, 1.0)
                })
        
        # Shuffle so they don't appear to fall in perfect rows
        random.shuffle(self.coins)
            
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_coins)
        self.timer.start(20) # ~50 FPS
        
    def update_coins(self):
        active_coins = False
        for coin in self.coins:
            coin['y'] += coin['speed']
            if coin['y'] < self.height():
                active_coins = True
        self.update()
        
        if not active_coins:
            self.timer.stop()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        for coin in self.coins:
            s = int(30 * coin['scale'])
            # Draw coin
            painter.drawPixmap(int(coin['x']), int(coin['y']), s, s, self.coin_pixmap)


class CoinSuccessDialog(QDialog):
    """Custom dialog for successful coin redemption"""
    def __init__(self, added_coins, new_total, addon_path, parent=None):
        super().__init__(parent)
        self.theme = get_store_theme()
        self.added_coins = added_coins
        self.new_total = new_total
        self.addon_path = addon_path
        self.setWindowTitle(tr("success"))
        self.setFixedWidth(400)
        self.setup_ui()

        # Setup rain animation
        coin_path = os.path.join(self.addon_path, "system_files/gamification_images/Tayaki_coin.webp")
        if os.path.exists(coin_path):
            pixmap = QPixmap(coin_path)
            self.overlay = CoinRainOverlay(self, pixmap)
            self.overlay.raise_()

    def resizeEvent(self, event):
        if hasattr(self, 'overlay'):
            self.overlay.resize(self.size())
        super().resizeEvent(event)

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Spacer instead of celebration icon
        layout.addSpacing(20)

        # Title
        title = QLabel(tr("coins_received"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 24px;
                font-weight: 800;
                color: {self.theme['ACCENT_GOLD']};
            }}
        """)
        layout.addWidget(title)

        # Added Coins Container
        coins_container = _styled(QWidget())
        coins_layout = QVBoxLayout()
        coins_layout.setContentsMargins(20, 20, 20, 20)

        amount_label = QLabel(f"+{self.added_coins}")
        amount_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        amount_label.setStyleSheet(f"""
            QLabel {{
                font-size: 42px;
                font-weight: 900;
                color: {self.theme['ACCENT_GOLD']};
                border: none;
            }}
        """)
        coins_layout.addWidget(amount_label)

        label_text = QLabel(tr("coins_added"))
        label_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_text.setStyleSheet(f"color: {self.theme['TEXT_SECONDARY']}; font-size: 12px; font-weight: 700; letter-spacing: 1px; border: none")
        coins_layout.addWidget(label_text)

        coins_container.setLayout(coins_layout)
        coins_container.setStyleSheet(f"""
            QWidget {{
                background-color: {self.theme['PANEL_BG']};
                border-radius: 16px;
            }}
        """)
        layout.addWidget(coins_container)

        # New Balance
        balance_label = QLabel(f"{tr('new_balance')}: {self.new_total}")
        balance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        balance_label.setStyleSheet(f"color: {self.theme['TEXT_SECONDARY']}; font-size: 15px; font-weight: 600; margin-top: 10px;")
        layout.addWidget(balance_label)

        # Close Button
        close_btn = QPushButton(tr("awesome"))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedHeight(45)
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme['ACCENT_GOLD']};
                color: {self.theme['BTN_TEXT_ON_GOLD']};
                border: none;
                border-radius: 14px;
                font-weight: 800;
                font-size: 16px;
                margin-top: 10px;
            }}
            QPushButton:hover {{
                background-color: {self.theme['ACCENT_GOLD_HOVER']};
            }}
        """)
        layout.addWidget(close_btn)

        self.setLayout(layout)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.theme['STORE_BG']};
            }}
        """)


class TaiyakiStoreWindow(QDialog):
    """Pure PyQt implementation of Mr. Taiyaki Store"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = get_store_theme()
        self.setWindowTitle(tr("mr_taiyaki_store"))
        
        # Calculate adaptive window size based on screen geometry
        try:
            # Get the screen geometry where the parent window is located
            if parent:
                screen = parent.screen()
            else:
                screen = QApplication.primaryScreen()
            
            available_geometry = screen.availableGeometry()
            screen_width = available_geometry.width()
            screen_height = available_geometry.height()
            
            # Use 85% of available screen size, with maximum limits
            target_width = min(int(screen_width * 0.85), 1150)
            target_height = min(int(screen_height * 0.85), 700)

            # Ensure we don't go below minimum size (the header row - mascot,
            # title, 3 nav pills, and the wallet - needs ~1000px to never clip)
            target_width = max(target_width, 1100)
            target_height = max(target_height, 500)

            self.resize(target_width, target_height)
        except:
            # Fallback to default size if screen detection fails
            self.resize(1050, 700)

        # Allow resizing for smaller displays
        self.setMinimumSize(1100, 500)
        
        # Get addon path for images
        self.addon_package = mw.addonManager.addonFromModule(__name__)
        self.addon_path = os.path.dirname(os.path.dirname(__file__))
        
        # Load data
        self.load_store_data()
        
        # Setup UI
        self.setup_ui()
        
    def get_gamification_path(self):
        """Get the profile-specific gamification file path."""
        try:
            profile_name = mw.pm.name if mw.pm.name else "default"
        except:
            profile_name = "default"
        return os.path.join(self.addon_path, 'user_files', f'gamification_{profile_name}.json')

    def load_store_data(self):
        """Load store data from config"""
        # Try to read from gamification.json first as it's the source of truth
        coins = 0
        owned_items = ['default']
        current_theme_id = 'default'
        security_token = None
        
        try:
            gamification_file = self.get_gamification_path()
            if os.path.exists(gamification_file):
                with open(gamification_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    restaurant_data = data.get('restaurant_level', {})
                    coins = int(restaurant_data.get('taiyaki_coins', 0))
                    owned_items = restaurant_data.get('owned_items', ['default'])
                    current_theme_id = restaurant_data.get('current_theme_id', 'default')
                    security_token = restaurant_data.get('_security_token')
        except Exception as e:
            print(f"[ONIGIRI DEBUG] Error reading gamification.json: {e}")
            # Fallback to config for items/theme ONLY, not coins
            conf = config.get_config()
            # Check top level first (new structure)
            restaurant_data = conf.get('restaurant_level', {})
            if not restaurant_data:
                # Fallback to old structure
                achievements = conf.get('achievements', {})
                restaurant_data = achievements.get('restaurant_level', {})
            # Coins are 0 if gamification.json fails - they are not in config anymore
            coins = 0 
            owned_items = restaurant_data.get('owned_items', ['default'])
            current_theme_id = restaurant_data.get('current_theme_id', 'default')
            security_token = None
        
        
        # Anti-cheat: Removed
        self.coins = coins
        
        # Check settings for special unlocks
        conf = config.get_config()
        
        # Focus Dango
        focus_enabled = conf.get('achievements', {}).get('focusDango', {}).get('enabled', False)
        if focus_enabled:
            if 'focus_dango' not in owned_items:
                owned_items.append('focus_dango')
        elif 'focus_dango' in owned_items:
            owned_items.remove('focus_dango')
            
        # Mochi Messages
        mochi_enabled = conf.get('mochi_messages', {}).get('enabled', False)
        if mochi_enabled:
            if 'motivated_mochi' not in owned_items:
                owned_items.append('motivated_mochi')
        elif 'motivated_mochi' in owned_items:
            owned_items.remove('motivated_mochi')

        self.owned_items = owned_items
        self.current_theme_id = current_theme_id

        # Pull restaurant/sushi-evolution/shop data from the single source of
        # truth in nook_level.py (keeps the store, the level chip color,
        # and Nook Rush all in sync).
        from .nook_level import get_localized_restaurants, get_localized_evolutions, get_localized_shops
        self.restaurants = get_localized_restaurants()
        self.evolutions = get_localized_evolutions()
        self.shops = get_localized_shops()

        # Focus Dango / Motivated Mochi aren't bought with coins - they're
        # unlocked by enabling the matching toggle in Settings.
        for special_id in ("focus_dango", "motivated_mochi"):
            if special_id in self.restaurants:
                self.restaurants[special_id]["price"] = tr("check_info")

        # Apply difficulty multiplier to prices
        diff = conf.get("restaurant_level", {}).get("difficulty", "Apprendice")
        multiplier = 1
        if diff == "Cook":
            multiplier = 2
        elif diff == "Chef":
            multiplier = 4

        for items in (self.restaurants, self.evolutions, self.shops):
            for item_data in items.values():
                if isinstance(item_data.get("price"), int):
                    item_data["price"] *= multiplier

        # Evolution prerequisites: each evolution requires the previous one to be owned
        self.evolution_prerequisites = {
            "restaurant_evo_ii": "restaurant_evo_i",
            "restaurant_evo_iii": "restaurant_evo_ii",
            "restaurant_evo_iv": "restaurant_evo_iii",
            "restaurant_evo_legendary": "restaurant_evo_iv",
            "restaurant_evo_garden": "restaurant_evo_legendary",
            "restaurant_evo_heaven": "restaurant_evo_garden",
            "restaurant_evo_paradise": "restaurant_evo_heaven"
        }
    
    def check_evolution_unlocked(self, item_id):
        """Check if an evolution item is unlocked (prerequisites met)"""
        # If it's not an evolution item, it's always unlocked
        if item_id not in self.evolutions:
            return True
        
        # If there's no prerequisite, it's unlocked
        if item_id not in self.evolution_prerequisites:
            return True
        
        # Check if the prerequisite is owned
        prerequisite = self.evolution_prerequisites[item_id]
        return prerequisite in self.owned_items
    
    def setup_ui(self):
        """Create the main UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(24, 24, 24, 20)
        main_layout.setSpacing(16)

        main_layout.addWidget(self.create_header())

        # Content area (stacked widget for tabs)
        self.content_stack = _styled(QStackedWidget())
        self.content_stack.setStyleSheet("QStackedWidget { background: transparent; }")
        self.content_stack.addWidget(self.create_items_grid(self.restaurants))
        self.content_stack.addWidget(self.create_items_grid(self.evolutions))
        self.content_stack.addWidget(self.create_items_grid(self.shops))
        main_layout.addWidget(self.content_stack)

        self.setLayout(main_layout)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.theme['STORE_BG']};
            }}
        """)

    def create_header(self):
        """Single row: mascot+title on the left, nav pills + wallet on the right."""
        header = _styled(QWidget())
        header.setStyleSheet("background: transparent;")

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Mr. Taiyaki image
        mr_taiyaki_label = QLabel()
        mr_taiyaki_label.setStyleSheet("background: transparent;")
        mr_taiyaki_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mr_taiyaki_path = os.path.join(self.addon_path, "system_files/gamification_images/mr_taiyaki.webp")
        if os.path.exists(mr_taiyaki_path):
            mr_taiyaki_label.setPixmap(_load_scaled_pixmap(mr_taiyaki_path, 64, 64))
            mr_taiyaki_label.setFixedSize(64, 64)

        # Text stack (title + subtitle)
        text_stack = _styled(QWidget())
        text_stack.setStyleSheet("background: transparent;")
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        title = QLabel(tr("mr_taiyaki_store"))
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 30px;
                font-weight: 800;
                color: {self.theme['TEXT_PRIMARY']};
                background: transparent;
            }}
        """)

        subtitle = QLabel(tr("upgrade_restaurant_themes"))
        subtitle.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                color: {self.theme['TEXT_SECONDARY']};
                background: transparent;
            }}
        """)

        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)
        text_stack.setLayout(text_layout)

        layout.addWidget(mr_taiyaki_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(text_stack, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch()
        layout.addWidget(self.create_navigation(), 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.create_wallet_widget(), 0, Qt.AlignmentFlag.AlignVCenter)

        header.setLayout(layout)
        return header

    def create_wallet_widget(self):
        """Create the compact coin wallet chip (balance + get-more-coins button)"""
        wallet = _styled(QWidget())
        wallet.setStyleSheet(f"""
            QWidget {{
                background-color: {self.theme['WALLET_BG']};
                border-radius: 18px;
            }}
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(16, 6, 8, 6)
        layout.setSpacing(10)

        # Coin Icon
        coin_icon = QLabel()
        coin_icon.setStyleSheet("background: transparent;")
        coin_icon.setFixedSize(26, 26)

        coin_path = os.path.join(self.addon_path, "system_files/gamification_images/Tayaki_coin.webp")
        if os.path.exists(coin_path):
            coin_icon.setPixmap(_load_scaled_pixmap(coin_path, 26, 26))

        self.balance_label = QLabel(str(self.coins))
        self.balance_label.setStyleSheet(f"""
            QLabel {{
                font-size: 20px;
                font-weight: 800;
                color: {self.theme['ACCENT_GOLD']};
                background: transparent;
            }}
        """)

        # Use QToolButton instead of QPushButton for better styling control on macOS
        self.coins_btn = QToolButton()
        self.coins_btn.setText(tr("get_more_coins"))
        self.coins_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.coins_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.coins_btn.setFixedHeight(30)
        self.coins_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.coins_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: {self.theme['ACCENT_GOLD']};
                color: {self.theme['BTN_TEXT_ON_GOLD']};
                border: none;
                border-radius: 15px;
                font-weight: 800;
                font-size: 12px;
                padding: 0 14px;
            }}
            QToolButton:hover {{
                background-color: {self.theme['ACCENT_GOLD_HOVER']};
            }}
        """)
        self.coins_btn.clicked.connect(self.redeem_code)

        layout.addWidget(coin_icon)
        layout.addWidget(self.balance_label)
        layout.addSpacing(4)
        layout.addWidget(self.coins_btn)

        wallet.setLayout(layout)
        return wallet

    def create_navigation(self):
        """Segmented-pill nav with 3 tabs: Restaurants / Sushi Evolutions / Shops"""
        pill = _styled(QWidget())
        pill.setStyleSheet(f"""
            QWidget {{
                background-color: {self.theme['NAV_PILL_BG']};
                border-radius: 22px;
            }}
        """)
        pill_layout = QHBoxLayout()
        pill_layout.setContentsMargins(6, 6, 6, 6)
        pill_layout.setSpacing(4)

        nav_labels = [
            tr("restaurants_header"),
            tr("evolutions_header"),
            tr("shops_header"),
        ]
        # Match the font used in _apply_nav_styles so the measured width is accurate,
        # then lock it in as a minimum - so a growing coin balance (or a narrower
        # window) compresses elsewhere instead of ever clipping these labels.
        nav_font = QFont()
        nav_font.setPixelSize(14)
        nav_font.setWeight(QFont.Weight.Bold)
        nav_metrics = QFontMetrics(nav_font)

        self.nav_buttons = []
        for index, label in enumerate(nav_labels):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=index: self.switch_tab(i))
            btn.setMinimumWidth(nav_metrics.horizontalAdvance(label) + 40)
            pill_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        pill.setLayout(pill_layout)
        self._apply_nav_styles(0)

        return pill

    def _apply_nav_styles(self, active_index):
        """Highlight the active tab in the segmented pill control."""
        for i, btn in enumerate(self.nav_buttons):
            if i == active_index:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {self.theme['NAV_ACTIVE_BG']};
                        color: {self.theme['NAV_ACTIVE_TEXT']};
                        border: none;
                        padding: 9px 18px;
                        border-radius: 16px;
                        font-size: 14px;
                        font-weight: 700;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {self.theme['NAV_INACTIVE_TEXT']};
                        border: none;
                        padding: 9px 18px;
                        border-radius: 16px;
                        font-size: 14px;
                        font-weight: 700;
                    }}
                    QPushButton:hover {{
                        background-color: {self.theme['NAV_HOVER_BG']};
                        color: {self.theme['NAV_HOVER_TEXT']};
                    }}
                """)

    def switch_tab(self, index):
        """Switch between tabs"""
        self.content_stack.setCurrentIndex(index)
        self._apply_nav_styles(index)

    def create_items_grid(self, items_dict):
        """Create a scrollable grid of items"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)

        container = _styled(QWidget())
        container.setStyleSheet("background-color: transparent;")

        grid = QGridLayout()
        grid.setSpacing(22)
        grid.setAlignment(Qt.AlignmentFlag.AlignCenter)

        row = 0
        col = 0
        max_cols = 4

        for item_id, item_data in items_dict.items():
            is_owned = item_id in self.owned_items
            is_equipped = item_id == self.current_theme_id

            # Check if this is an evolution with unmet prerequisites
            is_unlocked = self.check_evolution_unlocked(item_id)

            # Create a copy of item_data to potentially modify
            display_data = item_data.copy()

            # If the evolution is locked, override the price to show "Check info"
            if not is_unlocked and not is_owned:
                prerequisite = self.evolution_prerequisites.get(item_id)
                if prerequisite:
                    prerequisite_name = self.evolutions[prerequisite]['name']
                    display_data['price'] = tr("check_info")
                    # Store the prerequisite info for the back of the card
                    display_data['prerequisite_info'] = f"{tr('requires_prefix', 'Requires')} {prerequisite_name}"

            # Pass self (the store window) to the card
            card = StoreItemCard(item_id, display_data, is_owned, is_equipped, self.coins, self.addon_path, self)
            card.setFixedSize(230, 300)

            grid.addWidget(card, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Add stretch to push items to top
        grid.setRowStretch(row + 1, 1)

        container.setLayout(grid)
        scroll.setWidget(container)

        return scroll

    def buy_item(self, item_id):
        """Handle item purchase"""
        # Find item in any of the 3 categories
        item = self.restaurants.get(item_id) or self.evolutions.get(item_id) or self.shops.get(item_id)

        if not item:
            showInfo("Item not found.")
            return
        
        price = item['price']
        
        if item_id in self.owned_items:
            showInfo("You already own this!")
            return
        
        # Check if evolution prerequisites are met
        if not self.check_evolution_unlocked(item_id):
            prerequisite = self.evolution_prerequisites.get(item_id)
            prerequisite_name = self.evolutions[prerequisite]['name']
            showInfo(f"This evolution is locked!\\n\\nYou must first purchase {prerequisite_name}.")
            return
        
        if self.coins >= price:
            # Deduct coins
            self.coins -= price
            self.owned_items.append(item_id)
            
            # Save items to config (but NOT coins)
            conf = config.get_config()
            if 'restaurant_level' not in conf:
                conf['restaurant_level'] = {}
                
            conf['restaurant_level']['owned_items'] = self.owned_items
            config.write_config(conf)
            
            # Sync to gamification.json
            self._sync_to_gamification_json()
            
            # Refresh UI
            self.refresh_store()
            
            # Refresh manager state
            from .nook_level import manager
            manager.refresh_state()
            
            tooltip(f"Successfully bought {item['name']}!")
        else:
            showInfo("Not enough coins.")
    
    def equip_item(self, item_id):
        """Handle item equipping"""
        self.current_theme_id = item_id
        
        # Save to config
        conf = config.get_config()
        if 'restaurant_level' not in conf:
            conf['restaurant_level'] = {}
            
        conf['restaurant_level']['current_theme_id'] = item_id
        config.write_config(conf)
        
        # Sync to gamification.json
        self._sync_to_gamification_json()
        
        # Refresh UI
        self.refresh_store()
        
        # Refresh manager state
        from .nook_level import manager
        manager.refresh_state()
        
        if item_id == 'default':
            tooltip("Restaurant closed!")
        else:
            item = self.restaurants.get(item_id) or self.evolutions.get(item_id) or self.shops.get(item_id)
            tooltip(f"Opened {item['name']}!")
        
        # Refresh the main window (deck browser) to update the widget
        mw.reset()
    
    def redeem_code(self):
        """Handle code redemption"""
        # Use custom dialog for code redemption
        dialog = CoinRedemptionDialog(self)
        if dialog.exec():
            code = dialog.get_code()
        else:
            return
        
        if not code:
            return
        
        # Show verifying state
        self.coins_btn.setText("Verifying...")
        self.coins_btn.setEnabled(False)
        QApplication.processEvents()

        print(f"[ONIGIRI DEBUG] Starting redemption for code: {code}")
        print(f"[ONIGIRI DEBUG] API URL: {SHOP_API_URL}")

        # The Apps Script backend can take a long time to answer (cold start
        # plus a full sheet scan). Run the request off the UI thread so Anki
        # never freezes, and let redeem_net own the timeout/retry policy.
        self._pending_code = code

        def _request():
            payload = {
                "code": code,
                # Stable across retries of the same code, so a lost response
                # can be replayed by the server instead of burning the code.
                "request_id": redeem_net.request_id_for_code(code),
            }
            print(f"[ONIGIRI DEBUG] Sending payload: {payload}")
            return redeem_net.post_redeem(SHOP_API_URL, payload)

        def _done(future):
            if not self._still_alive():
                return
            try:
                response = future.result()
            except Exception as exc:
                self._on_redeem_failed(exc)
                return
            self._on_redeem_response(response)

        mw.taskman.run_in_background(_request, _done)

    def _still_alive(self) -> bool:
        """False once the store window has been closed and the C++ side freed."""
        try:
            self.isVisible()
            return True
        except RuntimeError:
            return False

    def _on_redeem_response(self, response):
        """Handle a redemption response back on the UI thread."""
        try:
            print(f"[ONIGIRI DEBUG] Response status code: {response.status_code}")
            print(f"[ONIGIRI DEBUG] Response text: {response.text}")

            try:
                data = response.json()
                print(f"[ONIGIRI DEBUG] Parsed JSON data: {data}")
            except json.JSONDecodeError as je:
                print(f"[ONIGIRI DEBUG] JSON decode error: {str(je)}")
                self.reset_coins_button()
                showInfo(f"Server returned invalid response: {response.text[:100]}")
                return

            # The server answered, so this attempt is settled either way and
            # the retry id can be dropped.
            redeem_net.clear_request_id(getattr(self, "_pending_code", ""))

            if data.get("result") == "success":
                added_coins = int(data.get("coins", 0))
                print(f"[ONIGIRI DEBUG] Redemption successful! Adding {added_coins} coins")
                
                # Update coins
                self.coins += added_coins
                
                # Sync to gamification.json
                self._sync_to_gamification_json()
                
                print(f"[ONIGIRI DEBUG] Updated balance to {self.coins}")
                
                # Refresh UI
                self.refresh_store()
                
                # Refresh manager state
                from .nook_level import manager
                manager.refresh_state()
                
                self.reset_coins_button()
                # Show success dialog
                CoinSuccessDialog(added_coins, self.coins, self.addon_path, self).exec()
            else:
                error_msg = data.get("message", "Invalid Code")
                print(f"[ONIGIRI DEBUG] Redemption failed: {error_msg}")
                self.reset_coins_button()
                showInfo(f"Redemption Failed:\n{error_msg}")

        except Exception as e:
            print(f"[ONIGIRI DEBUG] Unexpected error: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            self.reset_coins_button()
            showInfo(f"Error: {str(e)}")

    def _on_redeem_failed(self, exc):
        """Handle a failed redemption request back on the UI thread."""
        self.reset_coins_button()

        if isinstance(exc, requests.exceptions.ReadTimeout):
            # The request did reach the server, so the code may well have been
            # consumed even though we never saw the answer. Say so instead of
            # blaming the connection - retrying would only report "already used".
            print("[ONIGIRI DEBUG] Read timed out")
            showInfo(
                "The server took too long to answer.\n\n"
                "Your code was not lost - just enter the same code again and "
                "the coins will be added."
            )
        elif isinstance(exc, requests.exceptions.Timeout):
            print("[ONIGIRI DEBUG] Connect timed out")
            showInfo("Could not reach the server. Please check your internet connection.")
        elif isinstance(exc, requests.exceptions.ConnectionError):
            print(f"[ONIGIRI DEBUG] Connection error: {str(exc)}")
            showInfo("Could not connect to server. Please check your internet connection.")
        else:
            print(f"[ONIGIRI DEBUG] Unexpected error: {type(exc).__name__}: {str(exc)}")
            showInfo(f"Error: {str(exc)}")


    def _sync_to_gamification_json(self):
        """Sync current store data to gamification.json using atomic write"""
        try:
            gamification_file = self.get_gamification_path()
            
            # 1. Read existing data
            data = {}
            if os.path.exists(gamification_file):
                try:
                    with open(gamification_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except json.JSONDecodeError:
                    print("[ONIGIRI DEBUG] Corrupt gamification.json, starting fresh for sync")
                    data = {}
            
            if 'restaurant_level' not in data:
                data['restaurant_level'] = {}
            
            # 2. Update data
            # 2. Update data
            # security_token = generate_coin_token(self.coins) - REMOVED
            data['restaurant_level']['taiyaki_coins'] = self.coins
            data['restaurant_level']['owned_items'] = self.owned_items
            data['restaurant_level']['current_theme_id'] = self.current_theme_id
            if '_security_token' in data['restaurant_level']:
                del data['restaurant_level']['_security_token']
            
            # 3. Write to temp file
            directory = os.path.dirname(gamification_file)
            if not os.path.exists(directory):
                os.makedirs(directory)
                
            # Create temp file in same directory to ensure atomic move works
            fd, tmp_path = tempfile.mkstemp(suffix='.tmp', dir=directory, text=True)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno()) # Ensure write hits disk
                
                # 4. Atomic rename
                os.replace(tmp_path, gamification_file)
                print(f"[ONIGIRI DEBUG] Atomic sync to gamification.json: {self.coins} coins")
                
            except Exception as e:
                # Clean up temp file if something went wrong
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise e
                
        except Exception as e:
            print(f"[ONIGIRI DEBUG] Error syncing to gamification.json: {e}")
    
    def reset_coins_button(self):
        """Reset the Get More Coins button to normal state"""
        self.coins_btn.setText("Get More Coins")
        self.coins_btn.setEnabled(True)
    
    def refresh_store(self):
        """Refresh the store UI by updating existing widgets in place"""
        # Update balance label
        self.balance_label.setText(str(self.coins))
        
        # Update all item cards in both tabs
        for i in range(self.content_stack.count()):
            scroll_area = self.content_stack.widget(i)
            if scroll_area:
                container = scroll_area.widget()
                if container:
                    layout = container.layout()
                    if layout:
                        # Iterate through all items in the grid
                        for j in range(layout.count()):
                            item = layout.itemAt(j)
                            if item and item.widget():
                                card = item.widget()
                                if isinstance(card, StoreItemCard):
                                    # Update the card's state
                                    card.update_state(
                                        is_owned=card.item_id in self.owned_items,
                                        is_equipped=card.item_id == self.current_theme_id,
                                        user_coins=self.coins
                                    )


def open_taiyaki_store():
    """Open the Mr. Taiyaki Store window"""
    mw.taiyaki_store = TaiyakiStoreWindow(mw)
    mw.taiyaki_store.show()
