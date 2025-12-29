from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, 
    QScrollArea, QFrame, QPushButton, QGridLayout, QSizePolicy,
    QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont, QColor, QPainter, QPainterPath, QImage
import os
import random
from aqt import gui_hooks, mw
from . import restaurant_level
from .gamification import get_gamification_manager
from .. import config

class NavButton(QLabel):
    clicked = pyqtSignal()
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)
        self.setFixedWidth(120)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

class RoundedFrame(QFrame):
    def __init__(self, bg_color="white", radius=20, parent=None):
        super().__init__(parent)
        self.bg_color = bg_color
        self.radius = radius
        self.setStyleSheet(f"""
            RoundedFrame {{
                background-color: {bg_color};
                border-radius: {radius}px;
            }}
        """)

class SnowOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.snowflakes = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_snow)
        self.timer.start(50)  # ~20 FPS

    def resizeEvent(self, event):
        self.snowflakes = []  # Reset on resize
        super().resizeEvent(event)

    def update_snow(self):
        # Add new snowflakes randomly
        if random.random() < 0.3:  # Adjust density
            size = random.randint(2, 5)
            x = random.randint(0, self.width())
            speed = random.randint(2, 5)
            self.snowflakes.append({"x": x, "y": -10, "size": size, "speed": speed})

        # Update positions
        for flake in self.snowflakes:
            flake["y"] += flake["speed"]
            flake["x"] += random.randint(-1, 1)  # Drift

        # Remove snowflakes that are out of bounds
        self.snowflakes = [f for f in self.snowflakes if f["y"] < self.height()]
        
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 200))  # Semi-transparent white

        for flake in self.snowflakes:
            painter.drawEllipse(flake["x"], flake["y"], flake["size"], flake["size"])

class RestaurantLevelWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = restaurant_level.manager
        self.gamification = get_gamification_manager()
        self.addon_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.image_base = os.path.join(self.addon_path, "system_files", "gamification_images")
        
        # Theme handling
        self.is_night_mode = mw.pm.night_mode()
        self.colors = {
            "card_bg": "#454545" if self.is_night_mode else "#ffffff",
            "text_main": "#ffffff" if self.is_night_mode else "#000000",
            "text_sub": "#d0d0d0" if self.is_night_mode else "#666666",
            "recent_bg": "#454545" if self.is_night_mode else "#ffffff",
            "progress_bg": "#666666" if self.is_night_mode else "#E0E0E0"
        }

        self.setup_ui()
        self.refresh_data()
        
        # Connect to reset hook to update when store items change
        gui_hooks.state_did_reset.append(self.refresh_data)
        
        # Timer for countdown
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)

    def closeEvent(self, event):
        gui_hooks.state_did_reset.remove(self.refresh_data)
        super().closeEvent(event)

    def update_theme(self):
        self.is_night_mode = mw.pm.night_mode()
        self.colors = {
            "card_bg": "#454545" if self.is_night_mode else "#ffffff",
            "text_main": "#ffffff" if self.is_night_mode else "#000000",
            "text_sub": "#d0d0d0" if self.is_night_mode else "#666666",
            "recent_bg": "#454545" if self.is_night_mode else "#ffffff",
            "progress_bg": "#666666" if self.is_night_mode else "#E0E0E0"
        }

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # --- Navigation Bar ---
        nav_container = QWidget()
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(15)
        nav_layout.addStretch() 
        
        # Pill shaped container for buttons
        self.nav_pill = RoundedFrame(bg_color=self.colors["card_bg"], radius=25) 
        self.nav_pill.setFixedHeight(50)
        pill_layout = QHBoxLayout(self.nav_pill)
        pill_layout.setContentsMargins(5, 5, 5, 5)
        pill_layout.setSpacing(0)
        
        self.btn_restaurant = NavButton("Restaurant")
        self.btn_specials = NavButton("Specials")
        
        self.btn_restaurant.clicked.connect(lambda: self.switch_page(0))
        self.btn_specials.clicked.connect(lambda: self.switch_page(1))
        
        pill_layout.addWidget(self.btn_restaurant)
        pill_layout.addWidget(self.btn_specials)
        
        nav_layout.addWidget(self.nav_pill)
        nav_layout.addStretch()
        
        main_layout.addWidget(nav_container)

        # --- Content Stack ---
        self.stack = QStackedWidget()
        
        # Page 1: Restaurant
        self.page_restaurant = QWidget()
        self.page_restaurant_layout = QVBoxLayout(self.page_restaurant)
        self.page_restaurant_layout.setContentsMargins(0, 0, 0, 0)
        self.page_restaurant_layout.setSpacing(20)
        self.setup_restaurant_page()
        self.stack.addWidget(self.page_restaurant)
        
        # Page 2: Specials
        self.page_specials = QWidget()
        self.page_specials_layout = QVBoxLayout(self.page_specials)
        self.page_specials_layout.setContentsMargins(0, 0, 0, 0)
        self.page_specials_layout.setSpacing(20)
        self.setup_specials_page()
        self.stack.addWidget(self.page_specials)
        
        main_layout.addWidget(self.stack)
        
        # Initialize default page
        self.switch_page(0)

        # Snow Overlay
        self.snow_overlay = SnowOverlay(self)
        self.snow_overlay.hide()

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        self.update_nav_styles(index)

    def update_nav_styles(self, active_index):
        # Dynamically apply styles based on current theme
        # Using NavButton (which inherits QLabel) styling
        active_style = f"""
            QLabel {{
                background-color: {self.colors['text_main']};
                color: {self.colors['card_bg']};
                font-weight: 800;
                font-size: 16px;
                border-radius: 20px; 
            }}
        """
        inactive_style = f"""
            QLabel {{
                background: transparent;
                color: {self.colors['text_sub']};
                font-weight: 700;
                font-size: 16px;
                border-radius: 20px;
            }}
            QLabel:hover {{
                color: {self.colors['text_main']};
            }}
        """
        
        if active_index == 0:
            self.btn_restaurant.setStyleSheet(active_style)
            self.btn_specials.setStyleSheet(inactive_style)
        else:
            self.btn_restaurant.setStyleSheet(inactive_style)
            self.btn_specials.setStyleSheet(active_style)
            
        # Also update nav pill background
        self.nav_pill.setStyleSheet(f"""
            RoundedFrame {{
                background-color: {self.colors['card_bg']};
                border-radius: 25px;
            }}
        """)

    def setup_restaurant_page(self):
        # Scroll Area for Restaurant Page
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 0, 15, 0)
        layout.setSpacing(20)
        
        # --- Top Section (Two Containers) ---
        top_container = QWidget()
        top_layout = QHBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(20)

        # 1. Left Container (Stats)
        self.stats_card = RoundedFrame(bg_color=self.colors["card_bg"])
        stats_layout = QVBoxLayout(self.stats_card)
        stats_layout.setContentsMargins(30, 30, 30, 30)
        stats_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Title
        self.restaurant_title = QLabel("Restaurant Level")
        self.restaurant_title.setStyleSheet(f"font-size: 32px; font-weight: 800; color: {self.colors['text_main']};")
        self.restaurant_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_layout.addWidget(self.restaurant_title)
        
        # Subtitle
        subtitle = QLabel("Serve knowledge daily to grow your restaurant!")
        subtitle.setStyleSheet(f"font-size: 14px; color: {self.colors['text_sub']}; margin-bottom: 20px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_layout.addWidget(subtitle)
        
        # Level Badge (Pill)
        self.level_badge = QLabel("Level 0")
        self.level_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.level_badge.setFixedSize(140, 40)
        # Style will be set in refresh_data
        self.level_badge.setStyleSheet(f"""
            background-color: #A3EFE3; 
            color: #000; 
            border-radius: 20px; 
            font-weight: 800; 
            font-size: 20px;
        """)
        # Center the badge
        badge_container = QWidget()
        badge_layout = QHBoxLayout(badge_container)
        badge_layout.setContentsMargins(0,0,0,0)
        badge_layout.addWidget(self.level_badge)
        badge_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_layout.addWidget(badge_container)
        
        # XP Text
        self.xp_text = QLabel("0 / 0 XP")
        self.xp_text.setStyleSheet(f"color: {self.colors['text_sub']}; font-size: 14px; margin-top: 5px; margin-bottom: 10px;")
        self.xp_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_layout.addWidget(self.xp_text)
        
        # XP Bar
        self.xp_bar = QProgressBar()
        self.xp_bar.setFixedHeight(16)
        self.xp_bar.setTextVisible(False)
        # Style will be set in refresh_data, but good to have base
        self.xp_bar.setStyleSheet(f"""
            QProgressBar {{ border: none; background: {self.colors['progress_bg']}; border-radius: 8px; }}
            QProgressBar::chunk {{ background: #1DE9B6; border-radius: 8px; }}
        """)
        stats_layout.addWidget(self.xp_bar)
        
        top_layout.addWidget(self.stats_card, stretch=3) # 60%ish width

        # 2. Right Container (Image)
        # Color will be set in refresh_data
        self.image_card = RoundedFrame(bg_color="#A3EFE3") 
        image_layout = QVBoxLayout(self.image_card)
        image_layout.setContentsMargins(0, 0, 0, 0)
        
        self.restaurant_image = QLabel()
        self.restaurant_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.restaurant_image.setStyleSheet("background: transparent;")
        image_layout.addWidget(self.restaurant_image)
        
        top_layout.addWidget(self.image_card, stretch=2) # 40%ish width

        layout.addWidget(top_container)
        
        # --- Current Equipment Section ---
        self.equip_card = RoundedFrame(bg_color=self.colors["card_bg"])
        equip_layout = QVBoxLayout(self.equip_card)
        equip_layout.setContentsMargins(30, 30, 30, 30)
        equip_layout.setSpacing(10)
        
        # Header
        equip_header = QLabel("Current Restaurant")
        equip_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        equip_header.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {self.colors['text_main']};")
        equip_layout.addWidget(equip_header)
        
        # Equip Name
        self.equip_name = QLabel("Loading...")
        self.equip_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.equip_name.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {self.colors['text_main']}; margin-top: 5px;")
        equip_layout.addWidget(self.equip_name)
        
        # Equip Description
        self.equip_desc = QLabel("...")
        self.equip_desc.setWordWrap(True)
        self.equip_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.equip_desc.setStyleSheet(f"font-size: 16px; color: {self.colors['text_sub']};")
        equip_layout.addWidget(self.equip_desc)
        
        layout.addWidget(self.equip_card)
        
        # --- Collection Section ---
        self.collection_card = RoundedFrame(bg_color=self.colors["card_bg"])
        collection_layout = QVBoxLayout(self.collection_card)
        collection_layout.setContentsMargins(30, 30, 30, 30)
        collection_layout.setSpacing(20)
        
        # Main Header
        coll_header = QLabel("Restaurant Collection")
        coll_header.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {self.colors['text_main']};")
        collection_layout.addWidget(coll_header)
        
        # 1. Restaurants Subsection
        lbl_rest = QLabel("Restaurants")
        lbl_rest.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {self.colors['text_sub']};")
        collection_layout.addWidget(lbl_rest)
        
        self.restaurant_grid = QGridLayout()
        self.restaurant_grid.setSpacing(15)
        collection_layout.addLayout(self.restaurant_grid)
        
        # 2. Evolutions Subsection
        lbl_evo = QLabel("Evolutions")
        lbl_evo.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {self.colors['text_sub']}; margin-top: 10px;")
        collection_layout.addWidget(lbl_evo)
        
        self.evolution_grid = QGridLayout()
        self.evolution_grid.setSpacing(15)
        collection_layout.addLayout(self.evolution_grid)
        
        layout.addWidget(self.collection_card)

        layout.addStretch()
        scroll.setWidget(content)
        self.page_restaurant_layout.addWidget(scroll)

    def setup_specials_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        
        content = QWidget()
        self.specials_layout = QVBoxLayout(content)
        self.specials_layout.setContentsMargins(10, 0, 15, 0)
        self.specials_layout.setSpacing(20) # Match page spacing

        # --- Daily Special Section ---
        self.special_card = RoundedFrame(bg_color=self.colors["card_bg"])
        special_layout = QVBoxLayout(self.special_card)
        special_layout.setContentsMargins(30, 25, 30, 30)
        special_layout.setSpacing(10)
        
        # Header Row
        header_row = QHBoxLayout()
        ds_title = QLabel("Daily Special")
        ds_title.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {self.colors['text_main']};")
        
        self.countdown_label = QLabel("00:00:00 left")
        self.countdown_label.setStyleSheet(f"font-size: 24px; font-weight: 800; color: {self.colors['text_main']};")
        
        header_row.addWidget(ds_title)
        header_row.addStretch()
        header_row.addWidget(self.countdown_label)
        special_layout.addLayout(header_row)
        
        # Info Row (Name + badges)
        info_row = QHBoxLayout()
        info_row.setSpacing(15)
        
        # Left side: Name and Desc
        text_col = QVBoxLayout()
        self.special_name = QLabel("Loading...")
        self.special_name.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {self.colors['text_main']};")
        
        self.special_desc = QLabel("...")
        self.special_desc.setStyleSheet(f"font-size: 14px; color: {self.colors['text_sub']};")
        self.special_desc.setWordWrap(True)
        
        text_col.addWidget(self.special_name)
        text_col.addWidget(self.special_desc)
        
        info_row.addLayout(text_col, stretch=1)
        
        # Right side: Badges
        badges_col = QVBoxLayout()
        badges_col.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        badges_col.setSpacing(8)
        
        self.xp_badge = QLabel("0 XP")
        self.xp_badge.setFixedSize(120, 32)
        self.xp_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.xp_badge.setStyleSheet("""
            background-color: #FCD34D; color: #000; border-radius: 16px; font-weight: bold; font-size: 14px;
        """)
        
        self.rarity_badge = QLabel("Common")
        self.rarity_badge.setFixedSize(120, 32)
        self.rarity_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rarity_badge.setStyleSheet("""
            background-color: #00C853; color: white; border-radius: 16px; font-weight: bold; font-size: 14px;
        """)
        
        badges_col.addWidget(self.xp_badge)
        badges_col.addWidget(self.rarity_badge)
        
        info_row.addLayout(badges_col)
        special_layout.addLayout(info_row)
        
        special_layout.addSpacing(10)
        
        # Progress Bar
        self.special_progress_bar = QProgressBar()
        self.special_progress_bar.setFixedHeight(18)
        self.special_progress_bar.setTextVisible(False)
        self.special_progress_bar.setStyleSheet(f"""
            QProgressBar {{ border: none; background: {self.colors['progress_bg']}; border-radius: 9px; }}
            QProgressBar::chunk {{ background: #00C853; border-radius: 9px; }}
        """)
        special_layout.addWidget(self.special_progress_bar)
        
        # Footer Text
        footer_row = QHBoxLayout()
        self.progress_text = QLabel("0/0 cards")
        self.progress_text.setStyleSheet(f"font-size: 14px; color: {self.colors['text_sub']};")
        
        footer_row.addWidget(self.progress_text)
        footer_row.addStretch()
        special_layout.addLayout(footer_row)
        
        self.footer_msg = QLabel("To prepare, study X cards today before the restaurant closes.")
        self.footer_msg.setStyleSheet(f"font-size: 14px; color: {self.colors['text_sub']}; margin-top: 5px;")
        special_layout.addWidget(self.footer_msg)

        self.specials_layout.addWidget(self.special_card)


        # --- Recent Specials Section ---
        recent_title = QLabel("Recent Specials")
        recent_title.setStyleSheet(f"font-size: 20px; font-weight: bold; margin-top: 10px; color: {self.colors['text_main']};")
        self.specials_layout.addWidget(recent_title)

        self.recent_list = QVBoxLayout()
        self.recent_list.setSpacing(10)
        self.specials_layout.addLayout(self.recent_list)

        # --- Recipe Collection Section ---
        collection_title = QLabel("Recipe Collection")
        collection_title.setStyleSheet(f"font-size: 20px; font-weight: bold; margin-top: 10px; color: {self.colors['text_main']};")
        self.specials_layout.addWidget(collection_title)

        # Grid for Recipe Cards
        collection_grid = QGridLayout()
        collection_grid.setSpacing(15)
        
        # Helper to create recipe card
        def create_recipe_card(name, color, row, col, colspan=1):
            card = RoundedFrame(bg_color=self.colors["card_bg"], radius=15)
            # Add a colored border or accent
            card.setStyleSheet(f"""
                RoundedFrame {{
                    background-color: {self.colors['card_bg']};
                    border-radius: 15px;
                    border: 2px solid {color};
                }}
            """)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(15, 15, 15, 15)
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            lbl_count = QLabel("0")
            lbl_count.setStyleSheet(f"font-size: 24px; font-weight: 800; color: {self.colors['text_main']};")
            lbl_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            lbl_name = QLabel(name)
            lbl_name.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {color}; margin-top: 5px;")
            lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            cl.addWidget(lbl_count)
            cl.addWidget(lbl_name)
            
            collection_grid.addWidget(card, row, col, 1, colspan)
            return lbl_count

        self.common_count = create_recipe_card("Common", "#00C853", 0, 0)
        self.uncommon_count = create_recipe_card("Uncommon", "#2979FF", 0, 1)
        self.rare_count = create_recipe_card("Rare", "#D500F9", 1, 0)
        self.epic_count = create_recipe_card("Epic", "#FF6D00", 1, 1)
        
        # Legendary takes the whole bottom row
        self.legendary_count = create_recipe_card("Legendary", "#FFD600", 2, 0, colspan=2)


        self.specials_layout.addLayout(collection_grid)

        self.specials_layout.addStretch()

        scroll.setWidget(content)
        self.page_specials_layout.addWidget(scroll)

    def refresh_data(self):
        self.update_theme()
        conf = config.get_config()
        
        # Update nav styles with new colors
        self.update_nav_styles(self.stack.currentIndex())
        
        # Get Theme Color First
        theme_color = self.manager.get_current_theme_color() or "#A3EFE3"
        
        # 1. Update Header Stats
        progress = self.manager.get_progress()
        
        # Update Name
        self.restaurant_title.setText(progress.name)
        
        # Update Level (with theme color)
        self.level_badge.setText(f"Level {progress.level}")
        self.level_badge.setStyleSheet(f"""
            background-color: transparent; 
            color: {self.colors['text_main']}; 
            border: 3px solid {theme_color};
            border-radius: 20px; 
            font-weight: 800; 
            font-size: 20px;
        """)
        
        # Update XP
        xp_to_next = progress.xp_to_next_level
        xp_into = progress.xp_into_level
        
        # Calculate lighter color for XP bar background
        # Simple manual lightening logic or just keep fixed background
        # For simplicity and safety, let's just color the chunk for now, or use a fixed light grey for BG
        
        self.xp_bar.setStyleSheet(f"""
            QProgressBar {{ border: none; background: {self.colors['progress_bg']}; border-radius: 8px; }}
            QProgressBar::chunk {{ background: {theme_color}; border-radius: 8px; }}
        """)

        if xp_to_next > 0:
            self.xp_bar.setMaximum(xp_to_next)
            self.xp_bar.setValue(xp_into)
            self.xp_text.setText(f"{xp_into} / {xp_to_next} XP")
        else:
            self.xp_bar.setMaximum(100)
            self.xp_bar.setValue(100)
            self.xp_text.setText("Max Level")

        # 2. Update Header Image
        # Get equipped item image
        # Using manager's method
        img_name = self.manager.get_current_theme_image()
        # Full path
        img_path = os.path.join(self.addon_path, "system_files", "gamification_images", "restaurant_folder", img_name)
        
        if os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            # Scale lightly to fit container (approx height 180-200)
            # Handle High DPI scaling
            ratio = self.devicePixelRatio()
            target_w = int(360 * ratio)
            target_h = int(240 * ratio)
            
            scaled = pixmap.scaled(QSize(target_w, target_h), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            scaled.setDevicePixelRatio(ratio)
            self.restaurant_image.setPixmap(scaled)
            
        # Update Theme Color (Image Card)
        self.image_card.setStyleSheet(f"""
            RoundedFrame {{
                background-color: {theme_color};
                border-radius: 20px;
            }}
        """)
        
        # 3. Update Equipment Details
        current_id = self.manager.get_current_theme_id()
        store_data = self.manager.get_store_data() # This fetches data from restaurant_level.py which now has descriptions!
        
        # Find item data
        item_data = None
        if current_id == "default":
             # Should have a default entry or construct one? 
             # store_data["restaurants"] doesn't have "default" explicitly usually?
             # Let's check RESTRAURANTS in restaurant_level.py again. 
             # It does NOT have "default". 
             # Let's provide a fallback.
             item_data = {
                 "name": "Onigiri Stand",
                 "description": "A humble food cart serving fresh Onigiri. The start of something great."
             }
        else:
             restaurants = store_data.get("restaurants", {})
             evolutions = store_data.get("evolutions", {})
             item_data = restaurants.get(current_id) or evolutions.get(current_id)
             
        if item_data:
             self.equip_name.setText(item_data.get("name", "Unknown"))
             self.equip_desc.setText(item_data.get("description", "No description available."))
        
        
        # 4. Update Daily Special
        ds_status = self.manager.get_daily_special_status()
        from datetime import datetime, timedelta
        today = datetime.now().strftime('%Y-%m-%d')
        
        completed_today_special = next(
            (s for s in self.gamification.daily_specials if s.completed_date and s.completed_date.startswith(today)),
            None
        )
        
        target = ds_status.get("target", 100)
        current = ds_status.get("current_progress", 0)
        
        # Try to get metadata
        special_data = self.manager._get_daily_special_data() # Returns dict from JS/JSON logic usually, might need fallback
        
        name = "Daily Special"
        desc = "Complete your reviews"
        diff = "Common"
        xp_reward = target * 5 # Approximation
        
        if special_data:
            name = special_data.get("name", name)
            desc = special_data.get("description", desc)
            diff = special_data.get("difficulty", diff)
            
            # Simple XP calc logic if not available
            if diff == "Uncommon": xp_reward = int(xp_reward * 1.5)
            elif diff == "Rare": xp_reward = xp_reward * 2
        
        if completed_today_special:
             self.special_name.setText(completed_today_special.name)
             self.special_desc.setText(completed_today_special.description)
             self.rarity_badge.setText(completed_today_special.difficulty.capitalize())
             self.xp_badge.setText(f" {completed_today_special.xp_earned} XP")
             
             self.special_progress_bar.setMaximum(target)
             self.special_progress_bar.setValue(target)
             self.progress_text.setText(f"{target}/{target} cards")
             self.footer_msg.setText("All done for today! Great job!")
             self.update_badges(completed_today_special.difficulty)
             
        else:
            self.special_name.setText(name)
            self.special_desc.setText(desc)
            self.rarity_badge.setText(diff.capitalize())
            self.xp_badge.setText(f" {xp_reward} XP")
            self.update_badges(diff)
            
            self.special_progress_bar.setMaximum(target)
            self.special_progress_bar.setValue(current)
            self.progress_text.setText(f"{current}/{target} cards")
            
            needed = target - current
            if needed <= 0:
                 self.footer_msg.setText("Goal reached! Syncing...")
            else:
                 self.footer_msg.setText(f"To prepare, study {needed} cards today before the restaurant closes.")

        # 5. Update Recent List
        while self.recent_list.count():
            child = self.recent_list.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        # Filter for previous 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        recents = []
        for s in self.gamification.daily_specials:
            if s.completed and s.completed_date:
                try:
                    completed_dt = datetime.fromisoformat(s.completed_date)
                    if completed_dt >= thirty_days_ago:
                        recents.append(s)
                except ValueError:
                    continue

        recents.sort(key=lambda x: x.completed_date or "", reverse=True)
        
        for spec in recents:
            row = RoundedFrame(bg_color=self.colors["recent_bg"], radius=10)
            rl = QVBoxLayout(row)
            rl.setContentsMargins(15, 15, 15, 15)
            rl.setSpacing(5)
            
            # Row 1: Name and Difficulty
            r1 = QHBoxLayout()
            nm = QLabel(f"<b>{spec.name}</b>")
            nm.setStyleSheet(f"font-size: 16px; color: {self.colors['text_main']};")
            
            diff_text = spec.difficulty.capitalize()
            # Basic color map
            d_colors = {
                "Common": "#00C853",
                "Uncommon": "#2979FF",
                "Rare": "#D500F9",
                "Epic": "#FF6D00",
                "Legendary": "#FFD600"
            }
            d_col = d_colors.get(diff_text, "#9E9E9E")
            
            diff_lbl = QLabel(diff_text)
            diff_lbl.setStyleSheet(f"color: {d_col}; font-weight: bold; font-size: 12px; border: 1px solid {d_col}; border-radius: 4px; padding: 2px 6px;")
            
            r1.addWidget(nm)
            r1.addStretch()
            r1.addWidget(diff_lbl)
            rl.addLayout(r1)
            
            # Row 2: Description
            desc = QLabel(spec.description)
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color: {self.colors['text_sub']}; font-size: 13px; margin-top: 5px; margin-bottom: 5px;")
            rl.addWidget(desc)
            
            # Row 3: Target Cards (and Date)
            r3 = QHBoxLayout()
            target_lbl = QLabel(f"Target: {spec.target_cards} cards")
            target_lbl.setStyleSheet(f"color: {self.colors['text_main']}; font-weight: bold; font-size: 12px;")
            
            dt_str = spec.completed_date.split("T")[0] if spec.completed_date else "?"
            date_lbl = QLabel(dt_str)
            date_lbl.setStyleSheet(f"color: {self.colors['text_sub']}; font-size: 12px;")

            r3.addWidget(target_lbl)
            r3.addStretch()
            r3.addWidget(date_lbl)
            
            rl.addLayout(r3)
            
            self.recent_list.addWidget(row)
            
        # 6. Update Recipe Collection
        # Calculate counts
        counts = {"common": 0, "uncommon": 0, "rare": 0, "epic": 0, "legendary": 0}
        
        # Get all completed specials (recipes)
        completed_specials = [s for s in self.gamification.daily_specials if s.completed]
        
        for s in completed_specials:
            r = s.difficulty.lower()
            if r in counts:
                counts[r] += 1
                
        # Update UI
        self.common_count.setText(str(counts["common"]))
        self.uncommon_count.setText(str(counts["uncommon"]))
        self.rare_count.setText(str(counts["rare"]))
        self.epic_count.setText(str(counts["epic"]))
        self.legendary_count.setText(str(counts["legendary"]))


        # 7. Update Collection Grids
        self.update_collection_grids()
        
        # 8. Check for Snow Effect
        if current_id == "santas_coffee":
            self.snow_overlay.raise_()
            self.snow_overlay.resize(self.size())
            self.snow_overlay.show()
        else:
            self.snow_overlay.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.snow_overlay.resize(self.size())

    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def update_collection_grids(self):
        store_data = self.manager.get_store_data()
        owned_items = store_data.get("owned_items", [])
        
        # 1. Restaurants
        self.clear_layout(self.restaurant_grid)
        restaurants = store_data.get("restaurants", {})
        self._fill_grid(self.restaurant_grid, restaurants, owned_items)
        
        # 2. Evolutions
        self.clear_layout(self.evolution_grid)
        evolutions = store_data.get("evolutions", {})
        self._fill_grid(self.evolution_grid, evolutions, owned_items)

    def _fill_grid(self, grid, items_dict, owned_items):
        row, col = 0, 0
        cols_per_row = 4
        
        # Filter items with images
        valid_items = []
        for kid, data in items_dict.items():
            if data.get("image"):
                 valid_items.append((kid, data))
        
        # Sort by price
        valid_items.sort(key=lambda x: x[1].get("price", 0))

        for kid, data in valid_items:
            is_owned = kid in owned_items
            
            # Create widget
            container = QWidget()
            vbox = QVBoxLayout(container)
            vbox.setContentsMargins(0,0,0,0)
            vbox.setSpacing(8)
            
            # Image Frame
            # Use 'card_bg' for frame, but maybe slight contrast if needed. 
            # Using transparent or just the image might be cleaner, but user asked for "miniatures".
            # Let's use a frame to unify size.
            img_frame = RoundedFrame(bg_color=self.colors["recent_bg"], radius=12) # Use recent_bg for slight contrast
            img_frame.setFixedSize(80, 80)
            if_layout = QVBoxLayout(img_frame)
            if_layout.setContentsMargins(5,5,5,5)
            if_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            lbl_img = QLabel()
            lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Load Image
            img_name = data.get("image")
            img_path = os.path.join(self.addon_path, "system_files", "gamification_images", "restaurant_folder", img_name)
            
            if os.path.exists(img_path):
                image = QImage(img_path)
                
                # Pre-scale to efficient size first (optimization)
                image = image.scaled(70, 70, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                
                if not is_owned:
                    # Robust Grayscale with Transparency
                    
                    # 1. Create a grayscale version (opaque)
                    gray_opaque = image.convertToFormat(QImage.Format.Format_Grayscale8)
                    gray_opaque = gray_opaque.convertToFormat(QImage.Format.Format_ARGB32)
                    
                    # 2. Create destination image initialized with original (to have alpha)
                    final_image = QImage(image.size(), QImage.Format.Format_ARGB32)
                    final_image.fill(Qt.GlobalColor.transparent)
                    
                    painter = QPainter(final_image)
                    painter.drawImage(0, 0, image) # Draw original (Dest)
                    
                    # 3. Blend Gray (Source) into Original (Dest) keeping Dest Alpha using SourceIn
                    # SourceIn: Result = SourceColor * DestAlpha
                    
                    # Try to resolve CompositionMode robustly (PyQt6 naming variance)
                    mode = getattr(QPainter.CompositionMode, 'SourceIn', None)
                    if mode is None:
                        mode = getattr(QPainter.CompositionMode, 'CompositionMode_SourceIn', None)
                    
                    # Fallback to integer 5 (SourceIn) if enum resolution fails
                    if mode is None:
                         # QPainter::CompositionMode_SourceIn is typically 5
                         mode = QPainter.CompositionMode(5)
                    
                    painter.setCompositionMode(mode)
                    painter.drawImage(0, 0, gray_opaque)
                    
                    painter.end()
                    
                    image = final_image
                
                pix = QPixmap.fromImage(image)
                lbl_img.setPixmap(pix)
            else:
                lbl_img.setText("?")
            
            if_layout.addWidget(lbl_img)
            vbox.addWidget(img_frame) # , alignment=Qt.AlignmentFlag.AlignCenter
            
            # Label
            lbl_name = QLabel(data.get("name", "Unknown"))
            lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_name.setWordWrap(True)
            # Use slightly smaller font
            lbl_name.setStyleSheet(f"font-size: 10px; color: {self.colors['text_sub']}; font-weight: 600;")
            lbl_name.setFixedWidth(80) # Match frame width to wrap text nicely
            vbox.addWidget(lbl_name)
            
            grid.addWidget(container, row, col)
            
            col += 1
            if col >= cols_per_row:
                col = 0
                row += 1

    def update_badges(self, difficulty):
        diff = difficulty.lower()
        if diff == "common":
            color = "#00C853" # Green
        elif diff == "uncommon":
            color = "#2979FF" # Blue
        elif diff == "rare":
            color = "#D500F9" # Purple
        elif diff == "epic":
            color = "#FF6D00" # Deep Orange
        elif diff == "legendary":
            color = "#FFD600" # Gold
        else:
            color = "#9E9E9E"
            
        self.rarity_badge.setStyleSheet(f"""
            background-color: {color}; color: white; border-radius: 16px; font-weight: bold; font-size: 14px;
        """)

    def update_countdown(self):
        from aqt import mw
        import time
        now = time.localtime()
        if mw.col:
            close_hour = int(mw.col.conf.get("rollover", 4))
        else:
            close_hour = 4
        
        now_ts = time.time()
        today_4am = time.mktime(time.struct_time((now.tm_year, now.tm_mon, now.tm_mday, close_hour, 0, 0, 0, 0, -1)))
        
        if now_ts >= today_4am:
             target_ts = today_4am + 86400
        else:
             target_ts = today_4am
             
        diff = int(target_ts - now_ts)
        if diff < 0: diff = 0
        
        h = diff // 3600
        m = (diff % 3600) // 60
        s = diff % 60
        
        self.countdown_label.setText(f"{h:02d}:{m:02d}:{s:02d} left")
