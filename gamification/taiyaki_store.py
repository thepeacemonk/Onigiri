"""
Mr. Taiyaki Store - Pure PyQt Implementation
Maintains the exact visual style of the HTML/CSS version
"""

import json
import requests
import hashlib
from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, tooltip
import os

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


SHOP_API_URL = "https://script.google.com/macros/s/AKfycbwg5HMxT9FWQIbPIVRrI6u8k_JheZBRUWWI0q5Jcl-ecRrPB4L25FJDh65YFjv__i4k/exec"

# Anti-cheat: Secret salt for coin verification
COIN_SALT = "taiyaki_onigiri_secret_2024_v1"


def generate_coin_token(coins: int) -> str:
    """Generate a security token for the coin value to prevent cheating."""
    data = f"{coins}:{COIN_SALT}"
    return hashlib.sha256(data.encode()).hexdigest()


def verify_coin_data(coins: int, token: str) -> bool:
    """Verify that the coin value hasn't been tampered with."""
    expected_token = generate_coin_token(coins)
    return token == expected_token


class StoreItemCard(QWidget):
    """A single store item card widget with flip functionality"""
    
    def __init__(self, item_id, item_data, is_owned, is_equipped, coins, addon_path, store_window, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.item_data = item_data
        self.is_owned = is_owned
        self.is_equipped = is_equipped
        self.user_coins = coins
        self.addon_path = addon_path
        self.store_window = store_window # Reference to main window for callbacks
        self.is_night_mode = mw.pm.night_mode()
        self.is_flipped = False  # Track flip state
        
        self.setup_ui()
    
    def setup_ui(self):
        """Create the card UI with front and back sides"""
        # Main container for stacking front and back
        self.stack = QStackedWidget()
        
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
        
        # Card container styling
        card_bg = "#3F2B13" if self.is_night_mode else "#5F411C"
        border_color = "#2A1E0D" if self.is_night_mode else "#4A3015"
        
        self.setStyleSheet(f"""
            StoreItemCard {{
                background-color: {card_bg};
                border-radius: 20px;
                border: 2px solid {border_color};
            }}
        """)
    
    def create_front_side(self):
        """Create the front side of the card"""
        front = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Preview area (colored background + image)
        preview = QWidget()
        preview.setFixedHeight(150)
        theme_color = self.item_data.get('theme', '#eee')
        
        # Create a layout for the preview to center the image
        preview_layout = QGridLayout()
        preview_layout.setContentsMargins(5, 5, 5, 5)
        
        # Image
        image_name = self.item_data.get('image')
        if image_name:
            # Try to find the image in restaurant folder
            img_path = os.path.join(
                self.addon_path,
                "system_files/gamification_images/restaurant_folder",
                image_name
            )
            
            if os.path.exists(img_path):
                image_label = QLabel()
                pixmap = QPixmap(img_path)
                # Scale pixmap to fit
                scaled_pixmap = pixmap.scaled(130, 130, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                image_label.setPixmap(scaled_pixmap)
                image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                preview_layout.addWidget(image_label, 0, 0, Qt.AlignmentFlag.AlignCenter)
        
        # Info icon button (top-right corner) using SVG
        info_btn = QPushButton()
        info_btn.setFixedSize(30, 30)
        info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Load and color the SVG icon
        svg_path = os.path.join(self.addon_path, "system_files/system_icons/info-circle.svg")
        if os.path.exists(svg_path):
            # Read SVG content
            with open(svg_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            # Get the card background color for the icon
            card_bg = "#3F2B13" if self.is_night_mode else "#5F411C"
            
            # Replace the fill color in the SVG
            svg_colored = svg_content.replace('<path d=', f'<path fill="{card_bg}" d=')
            
            # Create an image from the SVG
            renderer = QSvgRenderer(svg_colored.encode('utf-8'))
            image = QImage(30, 30, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(image)
            renderer.render(painter)
            painter.end()
            
            # Set the icon
            info_btn.setIcon(QIcon(QPixmap.fromImage(image)))
            info_btn.setIconSize(QSize(24, 24))
        
        info_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 15px;
            }
        """)
        info_btn.clicked.connect(self.flip_card)
        
        # Add info button to preview at top-right
        preview_layout.addWidget(info_btn, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        
        preview.setLayout(preview_layout)
        preview.setStyleSheet(f"""
            QWidget {{
                background-color: {theme_color};
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
            }}
        """)
        
        layout.addWidget(preview)
        
        # Info section
        info_widget = QWidget()
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(15, 10, 15, 15)
        
        # Colors based on mode
        text_color = "#FFFFFF"
        
        # Item name
        name_label = QLabel(self.item_data['name'])
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: 600;
                color: {text_color};
                margin-bottom: 5px;
            }}
        """)
        info_layout.addWidget(name_label)
        
        # Price row
        price_widget = QWidget()
        price_layout = QHBoxLayout()
        price_layout.setContentsMargins(0, 0, 0, 0)
        price_layout.setSpacing(5)
        price_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        price_value = self.item_data['price']
        is_special_price = isinstance(price_value, str)
        
        price_label = QLabel(str(price_value))
        if is_special_price:
            price_label.setStyleSheet("""
                QLabel {
                    font-size: 11px;
                    font-weight: bold;
                    color: #CFA13D;
                }
            """)
            price_label.setWordWrap(True)
            price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            price_label.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    font-weight: bold;
                    color: #CFA13D;
                }
            """)
        
        price_layout.addWidget(price_label)
        
        # Coin Icon for Price (only if numeric)
        if not is_special_price:
            coin_label = QLabel()
            coin_label.setFixedSize(20, 20)
            coin_path = os.path.join(self.addon_path, "system_files/gamification_images/Tayaki_coin.png")
            if os.path.exists(coin_path):
                pixmap = QPixmap(coin_path)
                scaled = pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                coin_label.setPixmap(scaled)
            else:
                coin_label.setStyleSheet("background-color: #CFA13D; border-radius: 10px;")
            price_layout.addWidget(coin_label)
        
        price_widget.setLayout(price_layout)
        info_layout.addWidget(price_widget)
        info_layout.addStretch()
        
        # Action button (inside info section)
        self.action_btn = QPushButton()
        self.action_btn.setFixedHeight(44)
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        if self.is_equipped:
            self.action_btn.setText("Close restaurant")
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #8B6F47;
                    color: white;
                    border: none;
                    border-radius: 12px;
                    font-weight: 600;
                    font-size: 15px;
                    margin: 0 20px 20px 20px;
                }
                QPushButton:hover {
                    background-color: #6B5437;
                }
            """)
            self.action_btn.clicked.connect(lambda: self.store_window.equip_item('default'))
        elif self.is_owned:
            self.action_btn.setText("Open restaurant")
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #A0714F;
                    color: white;
                    border: none;
                    border-radius: 12px;
                    font-weight: 600;
                    font-size: 15px;
                    margin: 0 20px 20px 20px;
                }
                QPushButton:hover {
                    background-color: #8B5E3C;
                }
            """)
            self.action_btn.clicked.connect(lambda: self.store_window.equip_item(self.item_id))
        else:
            if is_special_price:
                self.action_btn.setText("Locked")
                self.action_btn.setEnabled(False)
                self.action_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #6B5437;
                        color: #A89080;
                        border: none;
                        border-radius: 12px;
                        font-weight: 600;
                        font-size: 15px;
                        margin: 0 20px 20px 20px;
                    }
                """)
            else:
                self.action_btn.setText("Buy")
                can_afford = self.user_coins >= price_value
                
                if can_afford:
                    self.action_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #CFA13D;
                            color: white;
                            border: none;
                            border-radius: 12px;
                            font-weight: 600;
                            font-size: 15px;
                            margin: 0 20px 20px 20px;
                        }
                        QPushButton:hover {
                            background-color: #e67e22;
                        }
                    """)
                    self.action_btn.clicked.connect(lambda: self.store_window.buy_item(self.item_id))
                else:
                    self.action_btn.setEnabled(False)
                    self.action_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #6B5437;
                            color: #A89080;
                            border: none;
                            border-radius: 12px;
                            font-weight: 600;
                            font-size: 15px;
                            margin: 0 20px 20px 20px;
                        }
                    """)
        
        info_layout.addWidget(self.action_btn)
        
        info_widget.setLayout(info_layout)
        # Set background for info section to match card
        info_bg = "#3F2B13" if self.is_night_mode else "#5F411C"
        info_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {info_bg};
                border-bottom-left-radius: 20px;
                border-bottom-right-radius: 20px;
            }}
        """)
        layout.addWidget(info_widget)
        
        front.setLayout(layout)
        return front
    
    def create_back_side(self):
        """Create the back side of the card with description"""
        back = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Back button to flip back
        back_btn = QPushButton("← Back")
        back_btn.setFixedHeight(30)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        back_btn.clicked.connect(self.flip_card)
        layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        # Title
        title = QLabel(self.item_data['name'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: 700;
                color: #FFFFFF;
                margin-bottom: 5px;
            }
        """)
        layout.addWidget(title)
        
        # Description
        description = self.item_data.get('description', 'No description available.')
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        desc_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: rgba(255, 255, 255, 0.9);
                line-height: 1.5;
            }
        """)
        layout.addWidget(desc_label)
        
        # Special note for Santa's Coffee
        if self.item_id == "santas_coffee":
            special_note = QLabel("❄️ Special Feature: It snows on this theme!")
            special_note.setWordWrap(True)
            special_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            special_note.setStyleSheet("""
                QLabel {
                    font-size: 13px;
                    color: #A8D8FF;
                    background-color: rgba(168, 216, 255, 0.15);
                    padding: 10px;
                    border-radius: 8px;
                    font-weight: 600;
                    margin-top: 10px;
                }
            """)
            layout.addWidget(special_note)
        
        layout.addStretch()
        
        back.setLayout(layout)
        
        # Set background for back side
        info_bg = "#3F2B13" if self.is_night_mode else "#5F411C"
        back.setStyleSheet(f"""
            QWidget {{
                background-color: {info_bg};
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
        
        # Update the action button
        if self.is_equipped:
            self.action_btn.setText("Close restaurant")
            self.action_btn.setEnabled(True)
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #8B6F47;
                    color: white;
                    border: none;
                    border-radius: 12px;
                    font-weight: 600;
                    font-size: 15px;
                    margin: 0 20px 20px 20px;
                }
                QPushButton:hover {
                    background-color: #6B5437;
                }
            """)
            # Reconnect the click handler
            try:
                self.action_btn.clicked.disconnect()
            except:
                pass
            self.action_btn.clicked.connect(lambda: self.store_window.equip_item('default'))
        elif self.is_owned:
            self.action_btn.setText("Open restaurant")
            self.action_btn.setEnabled(True)
            self.action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #A0714F;
                    color: white;
                    border: none;
                    border-radius: 12px;
                    font-weight: 600;
                    font-size: 15px;
                    margin: 0 20px 20px 20px;
                }
                QPushButton:hover {
                    background-color: #8B5E3C;
                }
            """)
            # Reconnect the click handler
            try:
                self.action_btn.clicked.disconnect()
            except:
                pass
            self.action_btn.clicked.connect(lambda: self.store_window.equip_item(self.item_id))
        else:
            price_value = self.item_data['price']
            is_special_price = isinstance(price_value, str)
            
            if is_special_price:
                self.action_btn.setText("Locked")
                self.action_btn.setEnabled(False)
                self.action_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #6B5437;
                        color: #A89080;
                        border: none;
                        border-radius: 12px;
                        font-weight: 600;
                        font-size: 15px;
                        margin: 0 20px 20px 20px;
                    }
                """)
            else:
                self.action_btn.setText("Buy")
                can_afford = self.user_coins >= price_value
                
                if can_afford:
                    self.action_btn.setEnabled(True)
                    self.action_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #CFA13D;
                            color: white;
                            border: none;
                            border-radius: 12px;
                            font-weight: 600;
                            font-size: 15px;
                            margin: 0 20px 20px 20px;
                        }
                        QPushButton:hover {
                            background-color: #e67e22;
                        }
                    """)
                    # Reconnect the click handler
                    try:
                        self.action_btn.clicked.disconnect()
                    except:
                        pass
                    self.action_btn.clicked.connect(lambda: self.store_window.buy_item(self.item_id))
                else:
                    self.action_btn.setEnabled(False)
                    self.action_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #6B5437;
                            color: #A89080;
                            border: none;
                            border-radius: 12px;
                            font-weight: 600;
                            font-size: 15px;
                            margin: 0 20px 20px 20px;
                        }
                    """)


class CoinRedemptionDialog(QDialog):
    """Custom dialog for coin redemption"""
    def __init__(self, parent=None, is_night_mode=False):
        super().__init__(parent)
        self.is_night_mode = is_night_mode
        self.setWindowTitle("Get More Coins")
        self.setFixedWidth(450)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Title (Top Right)
        title = QLabel("Get More Coins")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 22px;
                font-weight: 800;
                color: #CFA13D;
            }
        """)
        layout.addWidget(title)
        
        # Info Container
        info_container = QWidget()
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(15, 15, 15, 15)
        
        info_label = QLabel("Remember: You get 10 coins at each level up")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: 500;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        info_layout.addWidget(info_label)
        info_container.setLayout(info_layout)
        
        bg_color = "#5F411C" if not self.is_night_mode else "#3F2B13"
        info_container.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border-radius: 12px;
            }}
        """)
        layout.addWidget(info_container)
        
        # Support Container
        support_container = QWidget()
        support_layout = QVBoxLayout()
        support_layout.setContentsMargins(15, 15, 15, 15)
        support_layout.setSpacing(10)
        
        support_text = QLabel("You can support Onigiri by buying coin codes here:")
        support_text.setWordWrap(True)
        support_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        support_text.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-size: 14px;")
        support_layout.addWidget(support_text)
        
        # Link Container
        link_container = QWidget()
        link_layout = QHBoxLayout()
        link_layout.setContentsMargins(0, 0, 0, 0)
        link_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # We use a label with a link, styled to look nice
        link_label = QLabel('<a href="https://buymeacoffee.com/peacemonk/extras" style="color: #CFA13D; text-decoration: none; font-weight: bold; font-size: 15px;"> Buy Coin Codes on BuyMeACoffee</a>')
        link_label.setOpenExternalLinks(True)
        link_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bg_color = "#5F411C" if not self.is_night_mode else "#3F2B13"
        link_label.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                padding: 10px 20px;
                border-radius: 12px;
            }}
            QLabel:hover {{
                background-color: transparent;
                border-radius: 12px;
                border: 2px solid #CFA13D;
            }}
        """)
        
        link_layout.addWidget(link_label)
        link_container.setLayout(link_layout)
        support_layout.addWidget(link_container)
        
        support_container.setLayout(support_layout)
        
        support_bg = "#4A3215" if not self.is_night_mode else "#2A1E0D"
        support_container.setStyleSheet(f"""
            QWidget {{
                background-color: {support_bg};
                border-radius: 12px;
            }}
        """)
        layout.addWidget(support_container)
        
        # Input Section
        input_label = QLabel("Have a code?")
        input_label.setStyleSheet("color: #CFA13D; font-weight: 600; margin-top: 10px;")
        layout.addWidget(input_label)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Paste your code here (e.g. ONI-XXXX-YYY)")
        self.input_field.setFixedHeight(45)
        self.input_field.setStyleSheet("""
            QLineEdit {
                padding: 0 15px;
                border-radius: 10px;
                border: 2px solid #CFA13D;
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                background-color: rgba(255, 255, 255, 0.15);
            }
        """)
        layout.addWidget(self.input_field)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFixedHeight(40)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: none;
                border-radius: 12px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover {
                color: white;
            }
        """)
        
        redeem_btn = QPushButton("Redeem Code")
        redeem_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        redeem_btn.setFixedHeight(40)
        redeem_btn.clicked.connect(self.accept)
        redeem_btn.setStyleSheet("""
            QPushButton {
                background-color: #CFA13D;
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: 800;
                font-size: 15px;
                padding: 0 30px;
            }
            QPushButton:hover {
                border: 2px solid #CFA13D;
                background-color: transparent;
            }
        """)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(redeem_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # Dialog styling
        dialog_bg = "#623C1B" if self.is_night_mode else "#7D5524"
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {dialog_bg};
            }}
        """)

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
    def __init__(self, added_coins, new_total, addon_path, parent=None, is_night_mode=False):
        super().__init__(parent)
        self.added_coins = added_coins
        self.new_total = new_total
        self.addon_path = addon_path
        self.is_night_mode = is_night_mode
        self.setWindowTitle("Success!")
        self.setFixedWidth(400)
        self.setup_ui()
        
        # Setup rain animation
        coin_path = os.path.join(self.addon_path, "system_files/gamification_images/Tayaki_coin.png")
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
        title = QLabel("Coins Received!")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 800;
                color: #CFA13D;
            }
        """)
        layout.addWidget(title)
        
        # Added Coins Container
        coins_container = QWidget()
        coins_layout = QVBoxLayout()
        coins_layout.setContentsMargins(20, 20, 20, 20)
        
        amount_label = QLabel(f"+{self.added_coins}")
        amount_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        amount_label.setStyleSheet("""
            QLabel {
                font-size: 42px;
                font-weight: 900;
                color: #FFFFFF;
                border: none;
            }
        """)
        coins_layout.addWidget(amount_label)
        
        label_text = QLabel("COINS ADDED")
        label_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_text.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px; font-weight: 700; letter-spacing: 1px; border: none")
        coins_layout.addWidget(label_text)
        
        coins_container.setLayout(coins_layout)
        
        # Container styling
        bg_color = "#5F411C" if not self.is_night_mode else "#3F2B13"
        coins_container.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border-radius: 15px;
            }}
        """)
        layout.addWidget(coins_container)
        
        # New Balance
        balance_label = QLabel(f"New Balance: {self.new_total}")
        balance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        balance_label.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 15px; font-weight: 600; margin-top: 10px;")
        layout.addWidget(balance_label)
        
        # Close Button
        close_btn = QPushButton("Awesome!")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedHeight(45)
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #CFA13D;
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: 800;
                font-size: 16px;
                margin-top: 10px;
            }
            QPushButton:hover {
                border: 2px solid #CFA13D;
                background-color: transparent;
            }
        """)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
        
        # Dialog styling
        dialog_bg = "#623C1B" if self.is_night_mode else "#7D5524"
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {dialog_bg};
            }}
        """)


class TaiyakiStoreWindow(QDialog):
    """Pure PyQt implementation of Mr. Taiyaki Store"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mr. Taiyaki Store")
        self.resize(1050, 700)
        self.setFixedWidth(1050)
        
        # Get addon path for images
        self.addon_package = mw.addonManager.addonFromModule(__name__)
        self.addon_path = os.path.dirname(os.path.dirname(__file__))
        self.is_night_mode = mw.pm.night_mode()
        
        # Load data
        self.load_store_data()
        
        # Setup UI
        self.setup_ui()
        
    def load_store_data(self):
        """Load store data from config"""
        # Try to read from gamification.json first as it's the source of truth
        coins = 0
        owned_items = ['default']
        current_theme_id = 'default'
        security_token = None
        
        try:
            gamification_file = os.path.join(self.addon_path, 'user_files', 'gamification.json')
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
            config = mw.addonManager.getConfig(self.addon_package)
            # Check top level first (new structure)
            restaurant_data = config.get('restaurant_level', {})
            if not restaurant_data:
                # Fallback to old structure
                achievements = config.get('achievements', {})
                restaurant_data = achievements.get('restaurant_level', {})
            # Coins are 0 if gamification.json fails - they are not in config anymore
            coins = 0 
            owned_items = restaurant_data.get('owned_items', ['default'])
            current_theme_id = restaurant_data.get('current_theme_id', 'default')
            security_token = None
        
        # Anti-cheat: Verify the security token
        if security_token is None:
            # First time or old data - generate token
            print("[ONIGIRI SECURITY] No security token found, generating new one")
            self.coins = coins
            self._sync_to_gamification_json()  # This will generate and save the token
        elif not verify_coin_data(coins, security_token):
            # Token mismatch - coins were manually edited!
            print("[ONIGIRI SECURITY] ⚠️ TAMPERING DETECTED! Resetting coins to 0")
            self.coins = 0
            self._sync_to_gamification_json()  # Save with new token
            showInfo("⚠️ Coin tampering detected!\n\nYour coins have been reset to 0.\nPlease earn coins legitimately through gameplay.")
        else:
            # Valid token - all good
            self.coins = coins
        
        # Check settings for special unlocks
        config = mw.addonManager.getConfig(self.addon_package)
        
        # Focus Dango
        focus_enabled = config.get('achievements', {}).get('focusDango', {}).get('enabled', False)
        if focus_enabled:
            if 'focus_dango' not in owned_items:
                owned_items.append('focus_dango')
        elif 'focus_dango' in owned_items:
            owned_items.remove('focus_dango')
            
        # Mochi Messages
        mochi_enabled = config.get('mochi_messages', {}).get('enabled', False)
        if mochi_enabled:
            if 'motivated_mochi' not in owned_items:
                owned_items.append('motivated_mochi')
        elif 'motivated_mochi' in owned_items:
            owned_items.remove('motivated_mochi')

        self.owned_items = owned_items
        self.current_theme_id = current_theme_id
        
        # Store items data with correct image filenames
        self.restaurants = {
            "focus_dango": {
                "name": "Focus Dango", 
                "price": "Check info", 
                "theme": "#DC90B8", 
                "image": "focus_dango_restaurant.png",
                "description": "A focused environment for deep work. Unlock this by enabling Focus Dango in settings."
            },
            "motivated_mochi": {
                "name": "Motivated Mochi", 
                "price": "Check info", 
                "theme": "#6EC170", 
                "image": "mochi_msg_restaurant.png",
                "description": "Stay motivated with Mochi! Unlock this by enabling Mochi Messages in settings."
            },
            "macha_delights": {
                "name": "Macha Delights", 
                "price": 400, 
                "theme": "#517C58", 
                "image": "Macha Delights.png",
                "description": "A serene tea house specializing in premium matcha creations. Perfect for those who appreciate the subtle, earthy flavors of green tea paired with delicate pastries."
            },
            "macaron_maison": {
                "name": "Macaron Maison", 
                "price": 500, 
                "theme": "#AFC3D6", 
                "image": "Macaron Maison.png",
                "description": "An elegant French patisserie known for its colorful, delicate macarons. Each bite is a perfect balance of crispy shell and smooth, flavorful filling."
            },
            "coffee_co": {
                "name": "Coffee & Co", 
                "price": 600, 
                "theme": "#98693A", 
                "image": "CoffeeAndCake.png",
                "description": "A cozy coffee shop where the aroma of freshly brewed coffee fills the air. Enjoy artisan coffee paired with homemade cakes and pastries."
            },
            "grocery_store": {
                "name": "Grocery Store", 
                "price": 700, 
                "theme": "#AD6131", 
                "image": "Grocery Store.png",
                "description": "Your friendly neighborhood market stocked with fresh produce, pantry essentials, and daily necessities. A warm, welcoming place for all your shopping needs."
            },
            "bakery_heaven": {
                "name": "Bakery Heaven", 
                "price": 800, 
                "theme": "#CD9C57", 
                "image": "Bakery.png",
                "description": "A traditional bakery where the scent of freshly baked bread greets you every morning. From crusty baguettes to soft croissants, every item is made with love."
            },
            "awesome_boba": {
                "name": "Awesome Boba", 
                "price": 850, 
                "theme": "#CD8DCA", 
                "image": "Awesome Boba.png",
                "description": "A vibrant bubble tea shop offering creative flavors and toppings. Customize your drink with chewy tapioca pearls, fruit jellies, and more!"
            },
            "awesome_shiny_boba": {
                "name": "Awesome Shiny Boba", 
                "price": 1000, 
                "theme": "#41A59D", 
                "image": "Awesome Boba (Shiny).png",
                "description": "The premium evolution of Awesome Boba! This exclusive location features rare ingredients and limited-edition flavors with a stunning aesthetic."
            },
            "santas_coffee": {
                "name": "Santa's Coffee", 
                "price": 1225, 
                "theme": "#CA4D44", 
                "image": "Santa's Coffee.png",
                "description": "A magical winter wonderland café where holiday cheer meets exceptional coffee. Warm up with seasonal drinks while enjoying the festive atmosphere."
            },
        }
        
        self.evolutions = {
            "restaurant_evo_i": {
                "name": "Restaurant I Star", 
                "price": 700, 
                "theme": "#D07A5F", 
                "image": "Restaurant Evo I.png",
                "description": "The first evolution of your restaurant journey. A charming establishment that shows your dedication to growth and improvement."
            },
            "restaurant_evo_ii": {
                "name": "Restaurant II Star", 
                "price": 800, 
                "theme": "#D07A5F", 
                "image": "Restaurant Evo II.png",
                "description": "Your restaurant continues to evolve! Enhanced decor and expanded menu options attract more customers and showcase your progress."
            },
            "restaurant_evo_iii": {
                "name": "Restaurant III Star", 
                "price": 900, 
                "theme": "#D07A5F", 
                "image": "Restaurant Evo III.png",
                "description": "A significant milestone in your culinary journey. Your restaurant now features premium amenities and a reputation for excellence."
            },
            "restaurant_evo_iv": {
                "name": "Restaurant IV Star", 
                "price": 1000, 
                "theme": "#D07A5F", 
                "image": "Restaurant Evo IV.png",
                "description": "Near the peak of perfection! Your establishment has become a local landmark, known for its exceptional service and quality."
            },
            "restaurant_evo_legendary": {
                "name": "Restaurant Legendary", 
                "price": 2000, 
                "theme": "#445A78", 
                "image": "Restaurant Evo Legendary.png",
                "description": "The ultimate achievement! A legendary restaurant that stands as a testament to your dedication and hard work. Only the most committed reach this level."
            },
            "restaurant_evo_garden": {
                "name": "Restaurant Garden Palace", 
                "price": 3000, 
                "theme": "#2F553D", 
                "image": "Restaurant Evo Garden Palace.png",
                "description": "The pinnacle of culinary prestige! This deluxe establishment radiates luxury and sophistication, offering a world-class dining experience that is truly second to none."
            }
        }
    
    def setup_ui(self):
        """Create the main UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Navigation tabs
        nav = self.create_navigation()
        main_layout.addWidget(nav)
        
        # Content area (stacked widget for tabs)
        self.content_stack = QStackedWidget()
        
        # Restaurants tab
        restaurants_scroll = self.create_items_grid(self.restaurants)
        self.content_stack.addWidget(restaurants_scroll)
        
        # Evolutions tab
        evolutions_scroll = self.create_items_grid(self.evolutions)
        self.content_stack.addWidget(evolutions_scroll)
        
        main_layout.addWidget(self.content_stack)
        
        # Set main layout
        self.setLayout(main_layout)
        
        # Overall window styling
        bg_color = "#623C1B" if self.is_night_mode else "#7D5524"
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
            }}
        """)
    
    def create_header(self):
        """Create the wooden header with title and wallet"""
        header = QWidget()
        header.setFixedHeight(170)
        
        # Load wooden background
        wooden_bg_path = os.path.join(
            self.addon_path,
            "system_files/gamification_images/restaurant_folder/wooden_bg.png"
        )
        
        if os.path.exists(wooden_bg_path):
            # We need to escape the path for CSS
            wooden_bg_path = wooden_bg_path.replace('\\', '/')
            header.setStyleSheet(f"""
                QWidget {{
                    background-image: url("{wooden_bg_path}");
                    background-position: center;
                    background-repeat: no-repeat;
                    background-size: cover;
                    border-radius: 20px;
                }}
            """)
        else:
            header.setStyleSheet("""
                QWidget {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #8B4513, stop:1 #A0522D);
                    border-radius: 20px;
                }
            """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title group - horizontal layout with image on left, text stack on right
        title_widget = QWidget()
        # Make transparent
        title_widget.setStyleSheet("background: transparent;")
        
        title_main_layout = QHBoxLayout()
        title_main_layout.setContentsMargins(0, 0, 0, 0)
        title_main_layout.setSpacing(-10)  # Negative spacing to pull text closer
        
        # Mr. Taiyaki image
        mr_taiyaki_label = QLabel()
        mr_taiyaki_label.setStyleSheet("background: transparent;")
        mr_taiyaki_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mr_taiyaki_path = os.path.join(self.addon_path, "system_files/gamification_images/mr_taiyaki.png")
        if os.path.exists(mr_taiyaki_path):
            pixmap = QPixmap(mr_taiyaki_path)
            scaled_pixmap = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            mr_taiyaki_label.setPixmap(scaled_pixmap)
            mr_taiyaki_label.setFixedSize(100, 100)
        
        # Text stack (title + subtitle)
        text_stack = QWidget()
        text_stack.setStyleSheet("background: transparent;")
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        
        title = QLabel("Mr. Taiyaki Store")
        title.setContentsMargins(0, 0, 0, 0)
        title.setIndent(0)  # Remove any text indentation
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 36px;
                font-weight: 800;
                color: white;
                background: transparent;
                padding: 0px;
                margin: 0px;
            }
        """)
        
        subtitle = QLabel("Upgrade your restaurant with premium themes!")
        subtitle.setContentsMargins(0, 0, 0, 0)
        subtitle.setIndent(0)  # Remove any text indentation
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: rgba(255, 255, 255, 0.9);
                background: transparent;
                padding: 0px;
                margin: 0px;
            }
        """)
        
        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)
        # Don't add stretch - we want text to be compact
        text_stack.setLayout(text_layout)
        
        # Add image and text stack to main layout with vertical centering
        title_main_layout.addWidget(mr_taiyaki_label, 0, Qt.AlignmentFlag.AlignVCenter)
        title_main_layout.addWidget(text_stack, 0, Qt.AlignmentFlag.AlignVCenter)
        title_main_layout.addStretch()
        title_widget.setLayout(title_main_layout)
        
        layout.addWidget(title_widget)
        layout.addStretch()
        
        # Wallet display
        wallet = self.create_wallet_widget()
        layout.addWidget(wallet)
        
        header.setLayout(layout)
        return header
    
    def create_wallet_widget(self):
        """Create the wallet display with coins and button"""
        wallet = QWidget()
        # Transparent background as requested
        wallet.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        wallet.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border-radius: 15px;
            }
        """)
        wallet.setMinimumWidth(220)
        wallet.setFixedHeight(100)  # Fixed height to ensure space
        
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Coin balance row
        balance_widget = QWidget()
        balance_widget.setStyleSheet("background: transparent;")
        balance_widget.setFixedHeight(40)
        
        balance_layout = QHBoxLayout()
        balance_layout.setContentsMargins(0, 0, 0, 0)
        balance_layout.setSpacing(10)
        balance_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Coin Icon
        coin_icon = QLabel()
        coin_icon.setStyleSheet("background: transparent;")
        coin_icon.setFixedSize(36, 36)
        
        coin_path = os.path.join(self.addon_path, "system_files/gamification_images/Tayaki_coin.png")
        if os.path.exists(coin_path):
            pixmap = QPixmap(coin_path)
            scaled = pixmap.scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            coin_icon.setPixmap(scaled)
        
        self.balance_label = QLabel(str(self.coins))
        self.balance_label.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: 800;
                color: #CFA13D;
                background: transparent;
            }
        """)
        self.balance_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        balance_layout.addStretch()
        balance_layout.addWidget(coin_icon)
        balance_layout.addWidget(self.balance_label)
        balance_layout.addStretch()
        
        balance_widget.setLayout(balance_layout)
        layout.addWidget(balance_widget)
        
        # Get More Coins button container for centering
        btn_container = QWidget()
        btn_container.setStyleSheet("background: transparent;")
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Use QToolButton instead of QPushButton for better styling control on macOS
        self.coins_btn = QToolButton()
        self.coins_btn.setText("Get More Coins")
        self.coins_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.coins_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.coins_btn.setFixedSize(160, 34)
        self.coins_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        self.coins_btn.setStyleSheet("""
            QToolButton {
                background-color: #523112;
                color: #D4AE5E;
                border: 2px solid #523112;
                border-radius: 17px;
                font-weight: 800;
                font-size: 14px;
                padding: 0px;
            }
            QToolButton:hover {
                background-color: #523112;
                color: #D4AE5E;
            }
            QToolButton:pressed {
                background-color: #523112;
                color: #D4AE5E;
            }
        """)
        self.coins_btn.clicked.connect(self.redeem_code)
        
        btn_layout.addWidget(self.coins_btn)
        btn_container.setLayout(btn_layout)
        
        layout.addWidget(btn_container)
        
        wallet.setLayout(layout)
        return wallet
    
    def create_navigation(self):
        """Create the navigation tabs"""
        nav = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(20)
        
        text_color = "#ecf0f1" if self.is_night_mode else "#7f8c8d"
        
        # Restaurants button
        self.restaurants_btn = QPushButton("Restaurants")
        self.restaurants_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restaurants_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 159, 67, 0.1);
                color: #CFA13D;
                border: none;
                padding: 10px 20px;
                border-radius: 10px;
                font-size: 18px;
                font-weight: 600;
            }
        """)
        self.restaurants_btn.clicked.connect(lambda: self.switch_tab(0))
        
        # Evolutions button
        self.evolutions_btn = QPushButton("Evolutions")
        self.evolutions_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.evolutions_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {text_color};
                border: none;
                padding: 10px 20px;
                border-radius: 10px;
                font-size: 18px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: rgba(0, 0, 0, 0.03);
                color: #CFA13D;
            }}
        """)
        self.evolutions_btn.clicked.connect(lambda: self.switch_tab(1))
        
        layout.addStretch()
        layout.addWidget(self.restaurants_btn)
        layout.addWidget(self.evolutions_btn)
        layout.addStretch()
        
        nav.setLayout(layout)
        return nav
    
    def switch_tab(self, index):
        """Switch between tabs"""
        self.content_stack.setCurrentIndex(index)
        
        text_color = "#ecf0f1" if self.is_night_mode else "#7f8c8d"
        
        if index == 0:
            # Restaurants active
            self.restaurants_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 159, 67, 0.1);
                    color: #CFA13D;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 10px;
                    font-size: 18px;
                    font-weight: 600;
                }
            """)
            self.evolutions_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {text_color};
                    border: none;
                    padding: 10px 20px;
                    border-radius: 10px;
                    font-size: 18px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: rgba(0, 0, 0, 0.03);
                    color: #CFA13D;
                }}
            """)
        else:
            # Evolutions active
            self.evolutions_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 159, 67, 0.1);
                    color: #CFA13D;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 10px;
                    font-size: 18px;
                    font-weight: 600;
                }
            """)
            self.restaurants_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {text_color};
                    border: none;
                    padding: 10px 20px;
                    border-radius: 10px;
                    font-size: 18px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: rgba(0, 0, 0, 0.03);
                    color: #CFA13D;
                }}
            """)
    
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
        
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        
        grid = QGridLayout()
        grid.setSpacing(25)
        grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        row = 0
        col = 0
        max_cols = 3
        
        for item_id, item_data in items_dict.items():
            is_owned = item_id in self.owned_items
            is_equipped = item_id == self.current_theme_id
            
            # Pass self (the store window) to the card
            card = StoreItemCard(item_id, item_data, is_owned, is_equipped, self.coins, self.addon_path, self)
            card.setFixedSize(280, 300)
            
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
        # Find item in either category
        item = self.restaurants.get(item_id) or self.evolutions.get(item_id)
        
        if not item:
            showInfo("Item not found.")
            return
        
        price = item['price']
        
        if item_id in self.owned_items:
            showInfo("You already own this!")
            return
        
        if self.coins >= price:
            # Deduct coins
            self.coins -= price
            self.owned_items.append(item_id)
            
            # Save items to config (but NOT coins)
            config = mw.addonManager.getConfig(self.addon_package)
            if 'restaurant_level' not in config:
                config['restaurant_level'] = {}
                
            config['restaurant_level']['owned_items'] = self.owned_items
            mw.addonManager.writeConfig(self.addon_package, config)
            
            # Sync to gamification.json
            self._sync_to_gamification_json()
            
            # Refresh UI
            self.refresh_store()
            
            # Refresh manager state
            from .restaurant_level import manager
            manager.refresh_state()
            
            tooltip(f"Successfully bought {item['name']}!")
        else:
            showInfo("Not enough coins.")
    
    def equip_item(self, item_id):
        """Handle item equipping"""
        self.current_theme_id = item_id
        
        # Save to config
        config = mw.addonManager.getConfig(self.addon_package)
        if 'restaurant_level' not in config:
            config['restaurant_level'] = {}
            
        config['restaurant_level']['current_theme_id'] = item_id
        mw.addonManager.writeConfig(self.addon_package, config)
        
        # Sync to gamification.json
        self._sync_to_gamification_json()
        
        # Refresh UI
        self.refresh_store()
        
        # Refresh manager state
        from .restaurant_level import manager
        manager.refresh_state()
        
        if item_id == 'default':
            tooltip("Restaurant closed!")
        else:
            item = self.restaurants.get(item_id) or self.evolutions.get(item_id)
            tooltip(f"Opened {item['name']}!")
        
        # Refresh the main window (deck browser) to update the widget
        mw.reset()
    
    def redeem_code(self):
        """Handle code redemption"""
        # Use custom dialog for code redemption
        dialog = CoinRedemptionDialog(self, self.is_night_mode)
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
        
        try:
            payload = {"code": code}
            print(f"[ONIGIRI DEBUG] Sending payload: {payload}")
            
            response = requests.post(SHOP_API_URL, json=payload, timeout=10)
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
                from .restaurant_level import manager
                manager.refresh_state()
                
                self.reset_coins_button()
                # Show success dialog
                CoinSuccessDialog(added_coins, self.coins, self.addon_path, self, self.is_night_mode).exec()
            else:
                error_msg = data.get("message", "Invalid Code")
                print(f"[ONIGIRI DEBUG] Redemption failed: {error_msg}")
                self.reset_coins_button()
                showInfo(f"Redemption Failed:\n{error_msg}")
                
        except requests.exceptions.Timeout:
            print("[ONIGIRI DEBUG] Request timed out")
            self.reset_coins_button()
            showInfo("Request timed out. Please check your internet connection.")
        except requests.exceptions.ConnectionError as ce:
            print(f"[ONIGIRI DEBUG] Connection error: {str(ce)}")
            self.reset_coins_button()
            showInfo("Could not connect to server. Please check your internet connection.")
        except Exception as e:
            print(f"[ONIGIRI DEBUG] Unexpected error: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            self.reset_coins_button()
            showInfo(f"Error: {str(e)}")
    
    def _sync_to_gamification_json(self):
        """Sync current store data to gamification.json"""
        try:
            gamification_file = os.path.join(self.addon_path, 'user_files', 'gamification.json')
            if os.path.exists(gamification_file):
                with open(gamification_file, 'r+', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'restaurant_level' not in data:
                        data['restaurant_level'] = {}
                    
                    # Generate security token for anti-cheat
                    security_token = generate_coin_token(self.coins)
                    
                    # Update the restaurant_level data
                    data['restaurant_level']['taiyaki_coins'] = self.coins
                    data['restaurant_level']['owned_items'] = self.owned_items
                    data['restaurant_level']['current_theme_id'] = self.current_theme_id
                    data['restaurant_level']['_security_token'] = security_token
                    
                    # Write back
                    f.seek(0)
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.truncate()
                    print(f"[ONIGIRI DEBUG] Synced to gamification.json: {self.coins} coins (token: {security_token[:16]}...)")
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
