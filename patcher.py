import os
import re
import json
import base64
import html
from anki.hooks import wrap
from . import webview_handlers

# Default configuration values
DEFAULTS = {
    "congratsMessage": "Congratulations! You have finished this deck for now."
}

# Import after DEFAULTS to avoid circular imports
from aqt import mw, gui_hooks
from aqt.qt import *
import aqt
from aqt import mw, gui_hooks
from aqt.utils import showInfo, tooltip
from aqt.webview import AnkiWebView
from aqt.deckbrowser import DeckBrowser
from aqt.main import MainWebView
from aqt.utils import tr
from aqt.overview import Overview
from aqt.reviewer import Reviewer
import os
import json
import time
import re
import html
import base64
import random
import math
import webbrowser
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, urlencode, unquote, quote_plus
from typing import Optional, Dict, List, Tuple, Any, Callable, Union
from . import config
from . import onigiri_renderer
from . import deck_tree_updater
from .gamification import restaurant_level
from . import menu_buttons, settings, heatmap, fonts
from .gamification.gamification import get_gamification_manager
from .fonts import get_all_fonts
from . import deck_tree_updater
from .gamification import focus_dango
from .constants import COLOR_LABELS

# --- Toolbar Patching ---
_managed_hooks = []
_toolbar_patched = False
_original_MainWebView_eventFilter = None


def get_sync_status():
    """
    Determines the current sync status of the collection.
    Returns 'sync' if any sync is needed, 'none' if no sync needed.
    """
    try:
        # Check if collection is available
        if not mw.col:
            return 'none'
        
        # Get last sync timestamp and modification time from database
        try:
            # Get last sync timestamp from database
            ls = mw.col.db.scalar("select ls from col")
            mod = mw.col.mod if hasattr(mw.col, 'mod') else 0
            
            # If ls is None or 0, we've never synced - no indicator needed yet
            if ls is None or ls == 0:
                return 'none'
            
            # Show sync needed if mod > ls (changes since last sync)
            if mod > ls:
                return 'sync'
        except:
            pass
        
        # No sync needed
        return 'none'
    except:
        return 'none'


def _get_profile_pic_html(user_name: str, addon_package: str, css_class: str = "profile-pic") -> str:    
    """Generates profile picture HTML (img or default) based on user settings."""
    profile_pic_filename = mw.col.conf.get("modern_menu_profile_picture", "")
    if profile_pic_filename and os.path.exists(os.path.join(mw.addonManager.addonsFolder(addon_package), "user_files", "profile", profile_pic_filename)):
        pic_url = f"/_addons/{addon_package}/user_files/profile/{profile_pic_filename}"
        return f'<img src="{pic_url}" class="{css_class}">'
    else:
        # Use default profile picture when none is selected or file doesn't exist
        default_pic = "onigiri-san.png"
        pic_url = f"/_addons/{addon_package}/system_files/profile_default/{default_pic}"
        return f'<img src="{pic_url}" class="{css_class}">'


def take_control_of_deck_browser_hook():
    """
    Finds external hooks, removes them from the main hook,
    and stores them for Onigiri to manage, preventing duplication.
    """
    global _managed_hooks
    if _managed_hooks: # Ensure this runs only once
        return

    onigiri_module_name = config.__name__.split('.')[0]
    # Make a copy of the list to modify it safely
    original_hooks = list(gui_hooks.deck_browser_will_render_content._hooks)

    for hook in original_hooks:
        hook_id = _get_hook_name(hook)
        if onigiri_module_name not in hook_id:
            _managed_hooks.append(hook)
            # Remove the hook so it doesn't run on its own
            gui_hooks.deck_browser_will_render_content.remove(hook)

def _render_background_css(selector, mode, light_color, dark_color, light_image_path, dark_image_path, blur_val, addon_path, style_id, opacity_val=100, background_position="center"):
	"""Internal helper to generate a complete <style> block for a given background configuration."""
	blur_px = blur_val * 0.2
	addon_name = os.path.basename(addon_path)

	def get_img_url(image_path):
		if not image_path:
			return None
		if image_path.startswith("user_files/"):
			return f"/_addons/{addon_name}/{image_path}"
		else:
			return f"/_addons/{addon_name}/user_files/{image_path}"

	if mode == "accent":
		return f"""<style id="{style_id}">{selector} {{ background: var(--accent-color) !important; }}</style>"""

	if mode == "color":
		return f"""<style id="{style_id}">
			{selector} {{ background-color: {light_color} !important; }}
			.night-mode {selector} {{ background-color: {dark_color} !important; }}
		</style>"""

	# --- START OF REVISED LOGIC ---

	elif mode == "image":
		light_img_url = get_img_url(light_image_path)
		dark_img_url = get_img_url(dark_image_path) if dark_image_path else light_img_url
		if not light_img_url: return ""

		opacity_float = opacity_val / 100.0
		# Scale factor to prevent white borders when blur is applied
		scale = 1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0
		if 'body' in selector:
			base_before_css = f"""
				content: ''; position: fixed;
				top: 50%; left: 50%;
				width: 100vw; height: 100vh;
				transform: translate(-50%, -50%) scale({scale});
				-webkit-transform: translateZ(0);
				background-size: cover; background-position: {background_position};
				background-repeat: no-repeat; filter: blur({blur_px}px);
				image-rendering: -webkit-optimize-contrast; image-rendering: crisp-edges;
				-webkit-backface-visibility: hidden; will-change: transform;
				opacity: {opacity_float}; z-index: -1;
				pointer-events: none;
			"""
		else:
			base_before_css = f"""
				content: ''; position: absolute;
				top: 50%; left: 50%;
				width: 100%; height: 100%;
				transform: translate(-50%, -50%) scale({scale});
				-webkit-transform: translateZ(0);
				background-size: cover; background-position: {background_position};
				background-repeat: no-repeat; filter: blur({blur_px}px);
				image-rendering: -webkit-optimize-contrast; image-rendering: crisp-edges;
				-webkit-backface-visibility: hidden; will-change: transform;
				opacity: {opacity_float}; z-index: -1;
			"""

		image_css = f"{selector}::before {{ {base_before_css} background-image: url('{light_img_url}'); }}"
		if dark_img_url and dark_img_url != light_img_url:
			image_css += f"\n.night-mode {selector}::before {{ background-image: url('{dark_img_url}'); }}"

		container_css = ""
		if "body" in selector:
			container_css += f"html {{ background: transparent !important; overflow: hidden !important; }} {selector} {{ background: transparent !important; overflow: hidden !important; }}"
		else:
			container_css += f"{selector} {{ background: transparent; overflow: hidden; }}"

		if "container" in selector or ".sidebar-left" in selector or "#outer" in selector:
			container_css += f"{selector} {{ position: relative; z-index: 1; overflow: hidden; }}"
		elif "body" in selector:
			container_css += f"{selector} {{ position: relative; z-index: 1; overflow: hidden; }}"

		return f"<style id='{style_id}'>{container_css}\n{image_css}</style>"

    # Located in patcher.py

	elif mode == "image_color":
		light_img_url = get_img_url(light_image_path)
		dark_img_url = get_img_url(dark_image_path) if dark_image_path else light_img_url

		# If no image, fallback to solid color
		if not light_img_url:
				return f"""<style id="{style_id}">
					{selector} {{ background-color: {light_color} !important; }}
					.night-mode {selector} {{ background-color: {dark_color} !important; }}
				</style>"""

		# --- START OF FIX ---
		image_opacity = opacity_val / 100.0
		blur_px = blur_val * 0.2
		# Scale factor to prevent white borders when blur is applied
		scale = 1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0

		# This pseudo-element holds the background image with its effects.
		if 'body' in selector:
			base_before_css = f"""
				content: ''; position: fixed;
				top: 50%; left: 50%;
				width: 100vw; height: 100vh;
				transform: translate(-50%, -50%) scale({scale});
				background-size: cover; background-position: {background_position};
				background-repeat: no-repeat;
				filter: blur({blur_px}px);
				opacity: {image_opacity};
				z-index: -1;
				pointer-events: none;
			"""
		else:
			base_before_css = f"""
				content: ''; position: absolute;
				top: 50%; left: 50%;
				width: 100%; height: 100%;
				transform: translate(-50%, -50%) scale({scale});
				background-size: cover; background-position: {background_position};
				background-repeat: no-repeat;
				filter: blur({blur_px}px);
				opacity: {image_opacity};
				z-index: -1;
			"""

		image_css = f"{selector}::before {{ {base_before_css} background-image: url('{light_img_url}'); }}"
		if dark_img_url and dark_img_url != light_img_url:
			image_css += f"\n.night-mode {selector}::before {{ background-image: url('{dark_img_url}'); }}"

		# The container gets the SOLID color and acts as a positioning context.
		if "body" in selector:
			container_css = f"""
				html {{ background: transparent !important; overflow: hidden !important; }}
				{selector} {{
					position: relative; z-index: 1; overflow: hidden !important;
					background-color: {light_color} !important;
				}}
				.night-mode {selector} {{
					background-color: {dark_color} !important;
				}}
			"""
		else:
			container_css = f"""
				{selector} {{
					position: relative; z-index: 1; overflow: hidden;
					background-color: {light_color} !important;
				}}
				.night-mode {selector} {{
					background-color: {dark_color} !important;
				}}
			"""

		return f"<style id='{style_id}'>{container_css}\n{image_css}</style>"
	# --- END OF REVISED LOGIC ---

	return ""

# --- Profile Page Generation ---

_profile_dialog = None
_restaurant_dialog = None


def _load_restaurant_html(enabled: bool, addon_package: str) -> str:
    addon_path = os.path.dirname(__file__)
    template_path = os.path.join(addon_path, "system_files", "gamification_images", "restaurant_folder", "restaurant_level.html")
    try:
        with open(template_path, "r", encoding="utf-8") as template_file:
            template = template_file.read()
    except FileNotFoundError:
        return "<body><div class='missing-template'>Restaurant Level template missing.</div></body>"

    return template.replace("__ENABLED__", "true" if enabled else "false").replace("__ADDON_PACKAGE__", addon_package)


def _load_mr_taiyaki_store_html() -> str:
    addon_path = os.path.dirname(__file__)
    template_path = os.path.join(addon_path, "web", "gamification", "mr_taiyaki_store", "mr_taiyaki_store.html")
    try:
        with open(template_path, "r", encoding="utf-8") as template_file:
            return template_file.read()
    except FileNotFoundError:
        return "<body><div class='missing-template'>Store template missing.</div></body>"


class RestaurantLevelDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Restaurant Level")
        
        # --- THESE ARE THE MODIFIED LINES ---
        # Sets the default size when the window opens
        self.resize(900, 750) 
        
        # Set new min/max sizes to allow resizing
        self.setMinimumSize(600, 750)
        self.setMaximumWidth(800)
        # --- END OF MODIFICATION ---

        self.web = AnkiWebView(self)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)

        conf = config.get_config()
        addon_package = mw.addonManager.addonFromModule(__name__)

        progress = restaurant_level.manager.get_progress_payload()
        
        # Compute date labels directly instead of using achievements.compute_metrics()
        from datetime import datetime, timedelta
        today = datetime.now()
        today_label = today.strftime("%b %d, %Y")  # e.g., "Dec 16, 2025"
        
        # Calculate week range (assuming week starts on Monday)
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        week_label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d')}"
        
        # Get week review count from database
        week_reviews = 0
        if mw.col and getattr(mw.col, "db", None):
            day_cutoff = mw.col.sched.dayCutoff
            week_start_ts = (day_cutoff - 86400 * 7) * 1000  # 7 days ago in ms
            week_reviews = mw.col.db.scalar(
                "SELECT COUNT() FROM revlog WHERE type IN (0,1,2,3) AND id >= ?",
                week_start_ts
            ) or 0

        # Get today's review count using direct database query
        # This correctly counts only actual reviews from today, not deck resets or other operations
        # type IN (0,1,2,3) filters out manual operations (type 4 = manual rescheduling/resets)
        today_reviews = 0

        if mw.col and getattr(mw.col, "db", None):
            day_cutoff = mw.col.sched.dayCutoff
            today_start = day_cutoff - 86400  # 24 hours before cutoff (start of today)
            today_reviews = mw.col.db.scalar(
                "SELECT COUNT() FROM revlog WHERE type IN (0,1,2,3) AND id >= ?",
                today_start * 1000
            ) or 0
        
        stats_payload = {
            "todayReviews": today_reviews,  # Today's review count from the database
            "todayLabel": today_label,
            "weekReviews": week_reviews,
            "weekLabel": week_label,
            "totalXp": int(progress.get("totalXp", 0) or 0),
        }

        # Get the countdown configuration
        conf = config.get_config()
        
        current_theme_color = restaurant_level.manager.get_current_theme_color()
        current_theme_image = restaurant_level.manager.get_current_theme_image()
        current_theme_id = restaurant_level.manager.get_current_theme_id()
        
        # Sync today's completed special to daily_specials if not already there
        daily_special_status = restaurant_level.manager.get_daily_special_status()
        if daily_special_status.get("enabled", False):
            current_progress = daily_special_status.get("current_progress", 0)
            target = daily_special_status.get("target", 100)
            
            if current_progress >= target:
                # Today's special is completed - ensure it's in daily_specials
                from datetime import datetime
                today = datetime.now().strftime('%Y-%m-%d')
                special_id = f"daily_{today}"
                
                gamification = get_gamification_manager()
                existing = next((s for s in gamification.daily_specials if s.id == special_id), None)
                
                if not existing:
                    # Calculate difficulty based on target
                    if target <= 50:
                        difficulty = "Common"
                    elif target <= 100:
                        difficulty = "Uncommon"
                    else:
                        difficulty = "Rare"
                    
                    # Calculate XP
                    xp_earned = target * 5
                    if difficulty == "Uncommon":
                        xp_earned = int(xp_earned * 1.5)
                    elif difficulty == "Rare":
                        xp_earned = xp_earned * 2
                    
                    # Add today's completed special to the list
                    gamification.add_daily_special(
                        special_id=special_id,
                        name=f"Daily Special - {today}",
                        description="Complete your daily review goal",
                        difficulty=difficulty,
                        target_cards=target,
                        completed=True,
                        cards_completed=current_progress,
                        xp_earned=xp_earned
                    )
        
        payload = {
            "progress": progress,
            "stats": stats_payload,
            "theme_color": current_theme_color,
            "theme_image": current_theme_image,
            "current_theme_id": current_theme_id,
            "image_base_path": f"/_addons/{addon_package}/system_files/gamification_images/restaurant_folder/",
            "config": {
                "restaurant_countdown_hour": mw.col.conf.get("rollover", 4),
                "restaurant_countdown_minute": 0
            },
            "daily_special": daily_special_status,
            "completed_specials": [
                {
                    "date": s.completed_date.split("T")[0] if s.completed_date else "",
                    "name": s.name,
                    "description": s.description,
                    "difficulty": s.difficulty.lower(),
                    "cardsCompleted": s.cards_completed,
                    "targetCards": s.target_cards,
                    "xpEarned": s.xp_earned
                }
                for s in get_gamification_manager().daily_specials
                if s.completed
            ]
        }

        data_script = f"<script>window.ONIGIRI_RESTAURANT_LEVEL = {json.dumps(payload, ensure_ascii=False)};</script>"
        head_html = generate_dynamic_css(conf) + data_script

        css_files = [
            f"/_addons/{addon_package}/web/gamification/restaurant_level/restaurant_level.css",
        ]
        js_files = [
            f"/_addons/{addon_package}/web/gamification/restaurant_level/special_dishes.js",
            f"/_addons/{addon_package}/web/gamification/restaurant_level/restaurant_level.js",
        ]

        body_html = _load_restaurant_html(progress.get("enabled", False), addon_package)
        self.web.stdHtml(body_html, css=css_files, js=js_files, head=head_html, context=self)

def open_restaurant_level_dialog():
    global _restaurant_dialog
    if _restaurant_dialog is not None:
        _restaurant_dialog.close()
    _restaurant_dialog = RestaurantLevelDialog(mw)
    _restaurant_dialog.show()


class MrTaiyakiStoreDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Mr. Taiyaki Store")
        self.resize(1000, 800)
        
        self.web = AnkiWebView(self)
        # Bridge for pycmd
        self.web.set_bridge_command(self._on_bridge_cmd, self)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)
        
        self.render()

    def render(self):
        conf = config.get_config()
        addon_package = mw.addonManager.addonFromModule(__name__)
        
        store_data = restaurant_level.manager.get_store_data()
        store_data["image_base_path"] = f"/_addons/{addon_package}/system_files/gamification_images/restaurant_folder/"
        store_data["coin_image_path"] = f"/_addons/{addon_package}/system_files/gamification_images/Tayaki_coin.png"
        
        data_script = f"<script>window.ONIGIRI_STORE_DATA = {json.dumps(store_data, ensure_ascii=False)};</script>"
        head_html = generate_dynamic_css(conf) + data_script
        
        css_files = [
            f"/_addons/{addon_package}/web/gamification/mr_taiyaki_store/mr_taiyaki_store.css",
        ]
        js_files = [
            f"/_addons/{addon_package}/web/gamification/mr_taiyaki_store/mr_taiyaki_store.js",
        ]
        
        body_html = _load_mr_taiyaki_store_html()
        self.web.stdHtml(body_html, css=css_files, js=js_files, head=head_html, context=self)

    def _on_bridge_cmd(self, cmd: str) -> Any:
        if cmd.startswith("buy_item:"):
            item_id = cmd.split(":", 1)[1]
            success, msg = restaurant_level.manager.buy_item(item_id)
            new_data = restaurant_level.manager.get_store_data()
            return {
                "success": success,
                "message": msg,
                "coins": new_data["coins"],
                "owned_items": new_data["owned_items"],
                "restaurants": new_data["restaurants"],
                "evolutions": new_data["evolutions"]
            }
        elif cmd.startswith("equip_item:"):
            item_id = cmd.split(":", 1)[1]
            success, msg = restaurant_level.manager.equip_item(item_id)
            return {"success": success, "message": msg}
            
        return None

_store_dialog = None

def open_mr_taiyaki_store_dialog():
    global _store_dialog
    if _store_dialog is not None:
        _store_dialog.close()
    _store_dialog = MrTaiyakiStoreDialog(mw)
    _store_dialog.show()

def generate_profile_page_background_css():
    """Generates the CSS for the profile page's main container background."""
    # Reads the mode ("color" or "gradient") you set in the settings
    mode = mw.col.conf.get("onigiri_profile_page_bg_mode", "color")

    if mode == "gradient":
        # Uses the correct "gradient" color keys
        light1 = mw.col.conf.get("onigiri_profile_page_bg_light_color1", "#FFFFFF")
        light2 = mw.col.conf.get("onigiri_profile_page_bg_light_color2", "#E0E0E0")
        dark1 = mw.col.conf.get("onigiri_profile_page_bg_dark_color1", "#424242")
        dark2 = mw.col.conf.get("onigiri_profile_page_bg_dark_color2", "#212121")
        return f"""
        <style id="onigiri-profile-page-bg">
            .onigiri-profile-page {{
                background-image: linear-gradient(to bottom, {light1}, {light2});
                background-attachment: fixed;
            }}
            .night-mode .onigiri-profile-page {{
                background-image: linear-gradient(to bottom, {dark1}, {dark2});
            }}
        </style>
        """
    else: # Solid color
        # Uses the correct "solid color" keys
        light_color = mw.col.conf.get("onigiri_profile_page_bg_light_color1", "#F5F5F5")
        dark_color = mw.col.conf.get("onigiri_profile_page_bg_dark_color1", "#2c2c2c")
        return f"""
        <style id="onigiri-profile-page-bg">
            .onigiri-profile-page {{ background-color: {light_color} !important; }}
            .night-mode .onigiri-profile-page {{ background-color: {dark_color} !important; }}
        </style>
        """

def _get_profile_pill_html(conf, addon_package):
    user_name = conf.get("userName", "USER")
    
    # Profile Picture
    pic_html = _get_profile_pic_html(user_name, addon_package, "profile-pic-pill")
    
    return f"""
    <div class="profile-pill">
        {pic_html}
        <span class="profile-name-pill">{user_name}</span>
    </div>
    """

def _get_theme_colors_html(mode, conf):
    colors = conf.get("colors", {}).get(mode, {})
    items_html = ""
    
    # Use COLOR_LABELS for ordering and friendly names
    for key, info in COLOR_LABELS.items():
        if key == "--shadow-sm":
            break
        if key in colors:
            hex_val = colors[key]
            items_html += f"""
            <div class="color-item">
                <div class="color-swatch" style="background-color: {hex_val};"></div>
                <div class="color-info">
                    <span class="color-name">{info['label']}</span>
                    <span class="color-code">{hex_val.upper()}</span>
                </div>
            </div>
            """
            
    return f"""
    <h2 class="section-title">Theme colors ({mode})</h2>
    <div class="color-list">{items_html}</div>
    """

def _get_backgrounds_html(addon_package):
    main_bg_style = ""
    main_text = ""
    sidebar_bg_style = ""
    sidebar_text = ""

    # --- 1. Process Main Background ---
    main_mode = mw.col.conf.get("modern_menu_background_mode", "color")

    if main_mode == "image" or main_mode == "image_color":
        if mw.col.conf.get("modern_menu_background_image_mode", "single") == "separate":
            main_img_file = mw.col.conf.get("modern_menu_background_image_light", "")
        else:
            main_img_file = mw.col.conf.get("modern_menu_background_image", "")
            
        if main_img_file:
            main_img_path = f"/_addons/{addon_package}/user_files/main_bg/{main_img_file}"
            main_bg_style = f"background-image: url('{main_img_path}');"
        else:
            main_bg_style = "" # Use default card color
            main_text = "Image mode selected, but no file chosen."
    
    if main_mode == "color" or main_mode == "image_color":
        # Use the correct color for the current theme in the preview swatch
        if mw.pm.night_mode():
            color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
        else:
            color = mw.col.conf.get("modern_menu_bg_color_light", "#FFFFFF")
        # In combo mode, color is applied first, then image style.
        main_bg_style = f"background-color: {color}; {main_bg_style}"

    elif main_mode == "accent":
        main_bg_style = "background-color: var(--accent-color);"

    # --- 2. Process Sidebar Background ---
    sidebar_mode = mw.col.conf.get("modern_menu_sidebar_bg_mode", "main")

    if sidebar_mode == "main":
        sidebar_bg_style = "" # Use default card color
    else: # custom
        sidebar_type = mw.col.conf.get("modern_menu_sidebar_bg_type", "color")
        if sidebar_type == "image" or sidebar_type == "image_color":
            sidebar_img_file = mw.col.conf.get("modern_menu_sidebar_bg_image", "")
            if sidebar_img_file:
                sidebar_img_path = f"/_addons/{addon_package}/user_files/sidebar_bg/{sidebar_img_file}"
                sidebar_bg_style = f"background-image: url('{sidebar_img_path}');"
            else:
                sidebar_bg_style = ""
                sidebar_text = "Image mode selected, but no file chosen."
        
        if sidebar_type == "color" or sidebar_type == "image_color":
            if mw.pm.night_mode():
                color = mw.col.conf.get("modern_menu_sidebar_bg_color_dark", "#3C3C3C")
            else:
                color = mw.col.conf.get("modern_menu_sidebar_bg_color_light", "#EEEEEE")
            sidebar_bg_style = f"background-color: {color}; {sidebar_bg_style}"

        elif sidebar_type == "accent":
            sidebar_bg_style = "background-color: var(--accent-color);"

    # --- 3. Construct Final HTML ---
    # The title is changed to "Backgrounds" to be more accurate
    return f"""
    <h2 class="section-title">Backgrounds</h2>
    <div class="background-previews">
        <div class="preview-card">
            <div class="preview-image" style="{main_bg_style}">
                <span>{main_text}</span>
            </div>
            <div class="preview-info">Main Background</div>
        </div>
        <div class="preview-card">
            <div class="preview-image" style="{sidebar_bg_style}">
                 <span>{sidebar_text}</span>
            </div>
            <div class="preview-info">Sidebar Background</div>
        </div>
    </div>
    """

def _get_heatmap_data_and_config_for_profile():
    """Helper that calls the main heatmap data provider."""
    return heatmap.get_heatmap_and_config()

# --- Caching for Profile Stats ---
_profile_stats_cache = {
    "html": "",
    "timestamp": 0,
    "timeout": 300  # 5 minutes
}

def _get_stats_html():
    global _profile_stats_cache
    import time
    
    # Return cached if valid
    if time.time() - _profile_stats_cache["timestamp"] < _profile_stats_cache["timeout"] and _profile_stats_cache["html"]:
        return _profile_stats_cache["html"]

    conf = config.get_config()
    show_heatmap = conf.get("showHeatmapOnProfile", True)

    # Calculate today's stats from the database directly
    # This correctly counts only actual reviews from today, not deck resets or other operations
    # type IN (0,1,2,3) filters out manual operations (type 4 = manual rescheduling/resets)
    cards_today, time_today_seconds = mw.col.db.first(
        "select count(), sum(time)/1000 from revlog where type IN (0,1,2,3) and id > ?", 
        (mw.col.sched.dayCutoff - 86400) * 1000
    ) or (0, 0)
    time_today_seconds = time_today_seconds if time_today_seconds is not None else 0
    cards_today = cards_today if cards_today is not None else 0

    time_today_minutes = time_today_seconds / 60
    seconds_per_card = time_today_seconds / cards_today if cards_today > 0 else 0
    
    # --- START: New Retention Calculation ---
    total_reviews, correct_reviews = mw.col.db.first(
        "select count(*), sum(case when ease > 1 then 1 else 0 end) from revlog where type = 1 and id > ?",
        (mw.col.sched.dayCutoff - 86400) * 1000
    ) or (0, 0)
    total_reviews = total_reviews or 0
    correct_reviews = correct_reviews or 0
    retention_percentage = (correct_reviews / total_reviews * 100) if total_reviews > 0 else 0

    if retention_percentage >= 90: stars = 5
    elif retention_percentage >= 70: stars = 4
    elif retention_percentage >= 50: stars = 3
    elif retention_percentage >= 30: stars = 2
    elif total_reviews > 0: stars = 1
    else: stars = 0
    
    star_html = "".join([f"<i class='star{' empty' if i >= stars else ''}'></i>" for i in range(5)])

    retention_stat_html = f"""
    <div class="stat-card retention-card">
        <h3>Retention</h3>
        <p>{retention_percentage:.0f}%</p>
        <div class="star-rating">{star_html}</div>
    </div>
    """
    # --- END: New Retention Calculation ---

    # 2. Generate the HTML for the stats grid
    stats_grid_parts = [] 
    if not conf.get("hideStudiedStat", False):
        stats_grid_parts.append(f"""<div class="stat-card studied-card"><h3>Studied</h3><p>{cards_today} cards</p></div>""")
    if not conf.get("hideTimeStat", False):
        stats_grid_parts.append(f"""<div class="stat-card time-card"><h3>Time</h3><p>{time_today_minutes:.1f} min</p></div>""")
    if not conf.get("hidePaceStat", False):
        stats_grid_parts.append(f"""<div class="stat-card pace-card"><h3>Pace</h3><p>{seconds_per_card:.1f} s/card</p></div>""")
    # Add the retention card to the grid
    if not conf.get("hideRetentionStat", False):
        stats_grid_parts.append(retention_stat_html)

    stats_grid_html = f"""<div class="stats-grid">{''.join(stats_grid_parts)}</div>""" if stats_grid_parts else ""

    heatmap_html = ""
    if show_heatmap:
        heatmap_html = "<div id='onigiri-profile-heatmap-container'></div>"

    # 3. Construct the final HTML for the stats section
    html_content = f"""
    {stats_grid_html}
    <div id='onigiri-profile-heatmap-wrapper' style='margin-top: 20px;'>
        {heatmap_html}
    </div>
    """
    
    # Update cache
    _profile_stats_cache["html"] = html_content
    _profile_stats_cache["timestamp"] = time.time()
    
    return html_content


def _get_restaurant_level_profile_html() -> str:
    payload = restaurant_level.manager.get_progress_payload()
    if not payload.get("enabled") or not payload.get("showProfilePage"):
        return ""

    level = int(payload.get("level", 0) or 0)
    total_xp = int(payload.get("totalXp", 0) or 0)
    xp_into = int(payload.get("xpIntoLevel", 0) or 0)
    xp_next = int(payload.get("xpToNextLevel", 0) or 0)
    progress_fraction = payload.get("progressFraction", 0.0)

    if not isinstance(progress_fraction, (int, float)):
        progress_fraction = 0.0
    progress_fraction = max(0.0, min(float(progress_fraction), 1.0))
    if xp_next <= 0:
        progress_fraction = 1.0

    percent = f"{progress_fraction * 100:.1f}%"
    if xp_next > 0:
        xp_label = f"{xp_into:,} / {xp_next:,} XP"
    else:
        xp_label = f"{total_xp:,} XP total"

    total_label = f"{total_xp:,} XP total"
    phrase = html.escape(payload.get("phrase") or "Keep serving knowledge!", quote=False)

    return f"""
    <section class="profile-restaurant-level" data-level="{level}">
        <header class="prl-header">
            <div class="prl-title-group">
                <span class="prl-title">Restaurant Level</span>
                <span class="prl-level">Lv {level}</span>
            </div>
            <span class="prl-total">{html.escape(total_label, quote=False)}</span>
        </header>
        <div class="prl-progress" role="presentation">
            <div class="prl-progress-fill" style="width: {percent};"></div>
        </div>
        <div class="prl-meta">
            <span class="prl-xp">{html.escape(xp_label, quote=False)}</span>
        </div>
        <p class="prl-phrase">{phrase}</p>
    </section>
    """


def _get_profile_header_html(conf, addon_package):
    # This function now ONLY creates the banner background
    bg_style = ""
    bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "accent")
    if bg_mode == "image":
        bg_image_file = mw.col.conf.get("modern_menu_profile_bg_image", "")
        if bg_image_file and os.path.exists(os.path.join(mw.addonManager.addonsFolder(addon_package), "user_files", "profile_bg", bg_image_file)):
            bg_url = f"/_addons/{addon_package}/user_files/profile_bg/{bg_image_file}"
        else:
            # Use default background image when none is selected or file doesn't exist
            bg_url = f"/_addons/{addon_package}/system_files/profile_default/onigiri-bg.png"
        bg_style = f"background-image: url('{bg_url}'); background-size: cover; background-position: center;"
    elif bg_mode == "custom":
        light_color = mw.col.conf.get("modern_menu_profile_bg_color_light", "#EEEEEE")
        dark_color = mw.col.conf.get("modern_menu_profile_bg_color_dark", "#3C3C3C")
        bg_style = f"background-color: {light_color};"
    else: # accent
        bg_style = "background-color: var(--accent-color);"

    return f'<div class="profile-header-banner" style="{bg_style}"></div>'

def _generate_profile_html_body():
    conf = config.get_config()
    addon_package = mw.addonManager.addonFromModule(__name__)

    # --- Page Components ---
    banner_html = _get_profile_header_html(conf, addon_package)
    profile_pill_html = _get_profile_pill_html(conf, addon_package)

    theme_page_content = ""
    stats_page_content = ""

    # These variable definitions were missing and have been restored.
    show_light = mw.col.conf.get("onigiri_profile_show_theme_light", True)
    show_dark = mw.col.conf.get("onigiri_profile_show_theme_dark", True)
    show_bgs = mw.col.conf.get("onigiri_profile_show_backgrounds", True)

    if show_light: theme_page_content += _get_theme_colors_html("light", conf)
    if show_dark: theme_page_content += _get_theme_colors_html("dark", conf)
    if show_bgs: theme_page_content += _get_backgrounds_html(addon_package)
    if not theme_page_content:
        theme_page_content = '<p class="empty-section">Theme sections are hidden in settings.</p>'

    if mw.col.conf.get("onigiri_profile_show_stats", True):
        stats_page_content = _get_stats_html()
    else:
        stats_page_content = '<p class="empty-section">Stats section is hidden in settings.</p>'

    restaurant_level_html = _get_restaurant_level_profile_html()
    if restaurant_level_html:
        rl_styles = """
        <style>
        .profile-restaurant-level {
            padding: 18px 20px;
            border-radius: 22px;
            background: linear-gradient(135deg, rgba(255, 226, 180, 0.6), rgba(255, 165, 122, 0.55));
            border: 1px solid rgba(255, 181, 118, 0.4);
            margin-bottom: 18px;
        }
        .night-mode .profile-restaurant-level {
            background: linear-gradient(135deg, rgba(79, 47, 23, 0.85), rgba(120, 54, 33, 0.75));
            border-color: rgba(255, 181, 118, 0.25);
        }
        .profile-restaurant-level .prl-header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 12px;
        }
        .profile-restaurant-level .prl-title {
            font-weight: 700;
            font-size: 16px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }
        .profile-restaurant-level .prl-level {
            font-weight: 800;
            font-size: 28px;
        }
        .profile-restaurant-level .prl-progress {
            position: relative;
            width: 100%;
            height: 12px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.35);
            margin: 10px 0;
        }
        .night-mode .profile-restaurant-level .prl-progress {
            background: rgba(0, 0, 0, 0.35);
        }
        .profile-restaurant-level .prl-progress-fill {
            position: absolute;
            top: 0;
            left: 0;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, #ffe29f, #ffa99f, #ff719a);
            transition: width 0.3s ease;
        }
        .profile-restaurant-level .prl-meta {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            opacity: 0.85;
        }
        .profile-restaurant-level .prl-phrase {
            margin: 6px 0 0;
            font-size: 13px;
        }
        </style>
        """
        stats_page_content = rl_styles + restaurant_level_html + stats_page_content

    share_svg_icon = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92s2.92-1.31 2.92-2.92-1.31-2.92-2.92-2.92z"/></svg>"""
    export_button_html = f"""
    <button id="export-btn" class="page-export-button" title="Share Profile">
        {share_svg_icon}
    </button>
    """
    
    return f"""
    <div class="onigiri-profile-page">
        {banner_html}

        <div class="profile-controls">
            <div class="controls-spacer"></div>
            {profile_pill_html}
            
            <button id="nav-theme" class="nav-button">Themes</button>
            <button id="nav-stats" class="nav-button">Stats</button>
            
            {export_button_html}
        </div>

        <div class="profile-content-wrapper">
            <main>
                <div id="page-theme">{theme_page_content}</div>
                <div id="page-stats">{stats_page_content}</div>
            </main>
        </div>
    </div>
    """

class ProfileDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Your Onigiri Profile")
        self.setMinimumSize(500, 600)
        self.setMaximumSize(700, 900)
        self.web = AnkiWebView(self)
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.web)
        self.setLayout(layout)

        addon_package = mw.addonManager.addonFromModule(__name__)
        body_html = _generate_profile_html_body()
        
        # Inject the dynamic theme CSS and the custom profile page BG CSS
        head_html = generate_dynamic_css(config.get_config())
        head_html += generate_profile_page_background_css()

        css_files = [
            f"/_addons/{addon_package}/web/profile.css",
            f"/_addons/{addon_package}/web/heatmap.css" # Add heatmap CSS
        ]
        
        js_files = [
            f"/_addons/{addon_package}/web/lib/html2canvas.min.js",
            f"/_addons/{addon_package}/web/profile_page.js",
            f"/_addons/{addon_package}/web/heatmap.js"
        ]

        self.web.stdHtml(body_html, css=css_files, js=js_files, head=head_html, context=self)
        
        # After webview is set up, run javascript to render heatmap
        heatmap_data, heatmap_config = _get_heatmap_data_and_config_for_profile()
        self.web.eval(f"""
            if (document.getElementById('onigiri-profile-heatmap-container')) {{
                OnigiriHeatmap.render('onigiri-profile-heatmap-container', {json.dumps(heatmap_data)}, {json.dumps(heatmap_config)});
            }}
        """)


def open_profile():
    """Wrapper function to open the profile page dialog."""
    global _profile_dialog
    if _profile_dialog is not None:
        _profile_dialog.close()
    _profile_dialog = ProfileDialog(mw)
    _profile_dialog.show()

show_profile_page = open_profile

def on_webview_js_message(handled, message, context):
    """
    Unified handler for messages from all webviews.
    """
    if isinstance(context, Reviewer):
        if focus_dango.is_focus_dango_enabled():
            exit_commands = ["decks", "add", "browse", "stats", "sync"]
            if message in exit_commands:
                if focus_dango.intercept_exit_attempt(message):
                    focus_dango.show_dango_dialog()
                    return (True, None)
    if message.startswith("saveImage:") and _profile_dialog and _profile_dialog.isVisible():
        try:
            header, data = message.split(",", 1)
            image_data = base64.b64decode(data)

            filename, _ = QFileDialog.getSaveFileName(
                _profile_dialog, "Save Profile Image", "onigiri-profile.png", "PNG Images (*.png)"
            )

            if filename:
                with open(filename, "wb") as f:
                    f.write(image_data)
        except Exception as e:
            print(f"Onigiri: An error occurred during image save: {e}")

        return (True, None)

    if isinstance(context, DeckBrowser):
        cmd = message
        
        # Let webview_handlers handle the command
        # if cmd.startswith("onigiri_"):
        #    return webview_handlers.handle_webview_cmd((False, None), cmd, context)
        
        if cmd == "showUserProfile":
            open_profile()
            return (True, None)
        if cmd == "openTaiyakiStore":
            from .gamification.taiyaki_store import open_taiyaki_store
            open_taiyaki_store()
            return (True, None)
        if cmd == "openRestaurantLevel":
            open_restaurant_level_dialog()
            return (True, None)
        if cmd == "showGamification":
            open_gamification_dialog()
            return (True, None)
        if cmd == "add":
            mw.onAddCard()
            return (True, None)
        if cmd == "browse":
            mw.onBrowse()
            return (True, None)
        if cmd == "stats":
            mw.onStats()
            return (True, None)
        if cmd == "sync":
            if hasattr(mw.deckBrowser, 'web') and mw.deckBrowser.web:
                mw.deckBrowser.web.eval("SyncStatusManager.setSyncing(true);")
            mw.onSync()
            return (True, None)
        if cmd == "onigiri_check_sync_status":
            sync_status = get_sync_status()
            if hasattr(mw.deckBrowser, 'web') and mw.deckBrowser.web:
                mw.deckBrowser.web.eval(f"SyncStatusManager.setSyncStatus('{sync_status}');")
            return (True, None)
        if cmd == "openOnigiriSettings":
            settings.open_settings(0)
            return (True, None)
        if cmd == "shared":
            QDesktopServices.openUrl(QUrl("https://ankiweb.net/shared/decks"))
            return (True, None)
        if cmd == "create":
            # Fix for duplicate dialog: Use QInputDialog directly and create deck manually
            # instead of calling _on_create() which was triggering the dialog twice
            name, ok = QInputDialog.getText(mw, "Create Deck", "Name:")
            if ok and name:
                # Create the deck
                mw.col.decks.id(name)
                # Refresh the deck browser to show the new deck
                mw.deckBrowser.refresh()
            return (True, None)
        if cmd.startswith("opts:"):
            try:
                deck_id = cmd.split(":")[1]
                # Call Anki's standard deck options functionality
                mw.deckBrowser._show_options_for_deck_id(int(deck_id))
                return (True, None)
            except (ValueError, IndexError, AttributeError):
                # If deck ID is invalid or deckBrowser doesn't have the method, fall through to default handler
                pass
        if cmd.startswith("saveSidebarWidth:"):
            try:
                width = int(cmd.split(":")[1])
                mw.col.conf["modern_menu_sidebar_width"] = width
                mw.col.setMod()
            except:
                pass
            return (True, None)
        if cmd.startswith("saveSidebarState:"):
            try:
                is_collapsed = cmd.split(":")[1] == 'true'
                mw.col.conf["onigiri_sidebar_collapsed"] = is_collapsed
                mw.col.setMod()
            except Exception as e:
                print(f"Onigiri: Error saving sidebar state: {e}")
            return (True, None)
        # --- Focus Mode ---
        if cmd.startswith("saveDeckFocusState:"):
            try:
                is_focused = cmd.split(":")[1] == 'true'
                mw.col.conf["onigiri_deck_focus_mode"] = is_focused
                mw.col.setMod()
            except Exception as e:
                print(f"Onigiri: Error saving deck focus state: {e}")
            return (True, None)
        # --- Focus Mode ---

    elif isinstance(context, Overview):
        cmd = message  # <-- This line must come FIRST
        
        # Focus Dango check for exit commands from overview
        exit_commands = ["add", "browse", "stats", "sync"]
        if cmd in exit_commands and focus_dango.is_focus_dango_enabled():
            if focus_dango.intercept_exit_attempt(cmd):
                focus_dango.show_dango_dialog()
                return (True, None)
        
        # Now handle the commands normally
        if cmd == "deckBrowser":
            mw.moveToState("deckBrowser")
            return (True, None)
        if cmd in ["study", "opts", "refresh", "empty", "studymore", "description"]:
            return handled
        if cmd == "showUserProfile":
            open_profile()
            return (True, None)
        if cmd == "decks":
            mw.moveToState("deckBrowser")
            return (True, None)
        if cmd == "add":
            mw.onAddCard()
            return (True, None)
        if cmd == "browse":
            mw.onBrowse()
            return (True, None)
        if cmd == "stats":
            mw.onStats()
            return (True, None)
        if cmd == "sync":
            context.web.eval("SyncStatusManager.setSyncing(true);")
            mw.onSync()
            return (True, None)
        if cmd == "onigiri_check_sync_status":
            sync_status = get_sync_status()
            context.web.eval(f"SyncStatusManager.setSyncStatus('{sync_status}');")
            return (True, None)

    elif isinstance(context, Reviewer):
        cmd = message  # <-- This line must come FIRST
        
        # Focus Dango check for exit commands
        exit_commands = ["decks", "add", "browse", "stats", "sync"]
        if cmd in exit_commands:
            if focus_dango.is_focus_dango_enabled():
                if focus_dango.intercept_exit_attempt(cmd):
                    focus_dango.show_dango_dialog()
                    return (True, None)
        
        # Now handle the commands normally
        if cmd == "decks":
            mw.moveToState("deckBrowser")
            return (True, None)
        if cmd == "add":
            mw.onAddCard()
            return (True, None)
        if cmd == "browse":
            mw.onBrowse()
            return (True, None)
        if cmd == "stats":
            mw.onStats()
            return (True, None)
        if cmd == "sync":
            context.web.eval("SyncStatusManager.setSyncing(true);")
            mw.onSync()
            return (True, None)
        if cmd == "onigiri_check_sync_status":
            sync_status = get_sync_status()
            context.web.eval(f"SyncStatusManager.setSyncStatus('{sync_status}');")
            return (True, None)

    return handled


def patch_overview():
	"""Replaces the HTML generation for the overview screen."""
	
	conf = config.get_config()
	show_toolbar_replacements = conf.get("hideNativeHeaderAndBottomBar", False)
	max_hide = conf.get("maxHide", False)
	flow_mode = conf.get("flowMode", False)
    
	overview_style = mw.col.conf.get("onigiri_overview_style", "pro")
	style_class = "mini-overview" if overview_style == "mini" else ""

	mini_css = ""
	if overview_style == "mini":
		mini_css = """
        <style id="onigiri-mini-overview-style">
            body.mini-overview {
                align-items: flex-start; /* Override the vertical centering */
                padding-top: 5vh;      /* Add space from the top */
            }

            /* --- The rest of the styling for the mini-overview components --- */
            .mini-overview .overview-title { font-size: 20px; font-weight: 600; margin-bottom: 10px; text-align: center; }
            .mini-overview .stats-container { width: 280px; margin: 0 auto 20px auto; background: var(--canvas-inset); padding: 6px; border: 1px solid var(--border); border-radius: 12px}
            .mini-overview .stats-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; font-size: 14px; }
            .mini-overview .stats-row span:first-child { color: var(--fg-subtle); }
            .mini-overview .new-count-bubble, .mini-overview .learn-count-bubble, .mini-overview .review-count-bubble { font-size: 12px; font-weight: bold; padding: 3px 10px; border-radius: 12px; min-width: 30px; text-align: center; }
            .mini-overview #study { width: 280px; margin: 0 auto; padding: 10px; font-size: 16px; border-radius: 9999px; box-shadow: none !important; }
            .mini-overview .overview-bottom-actions { 
                width: 280px; 
                margin: 15px auto 0 auto; 
                display: flex; 
                justify-content: center; 
                gap: 10px; 
                text-align: center;
            }
            .mini-overview .overview-bottom-actions .overview-button { 
                background: var(--button-bg, #f5f5f5) !important; 
                color: var(--button-fg, #333); 
                border: 1px solid var(--button-border, #d9d9d9); 
                border-radius: 8px; 
                text-decoration: none; 
                font-size: 13px; 
                padding: 5px 12px; 
                font-weight: 500; 
                transition: background-color 0.2s, border-color 0.2s, color 0.2s; 
                opacity: 1 !important; 
                box-shadow: none !important;
            }
            .mini-overview .overview-bottom-actions .overview-button:hover { 
                background-color: var(--button-hover-bg, #e6e6e6) !important; 
                border-color: var(--button-hover-border, #bfbfbf);
                color: var(--button-hover-fg, #000);
                box-shadow: none !important;
            }
            /* Dark mode overrides */
            .nightMode .mini-overview .overview-bottom-actions .overview-button {
                --button-bg: var(--window-bg, #2a2a2a);
                --button-fg: var(--fg, #e0e0e0);
                --button-border: var(--border, #3a3a3a);
                --button-hover-bg: var(--window-bg, #333333);
                --button-hover-border: var(--border, #4a4a4a);
                --button-hover-fg: var(--fg, #ffffff);
                box-shadow: none !important;
            }
        </style>
        """
    
	def new_table(self) -> str:
		counts = list(self.mw.col.sched.counts())
		
		count_data = [
			{"label": tr.actions_new(), "count": counts[0], "class": "new-count-bubble"},
			{"label": tr.scheduling_learning(), "count": counts[1], "class": "learn-count-bubble"},
			{"label": tr.studying_to_review(), "count": counts[2], "class": "review-count-bubble"},
		]

		rows_html = ""
		for item in count_data:
			rows_html += (
				'<div class="stats-row">'
				f"<span>{item['label']}</span>"
				f"<span class=\"{item['class']}\">{item['count']}</span>"
				'</div>'
			)
		
		study_now_text = mw.col.conf.get("modern_menu_studyNowText") or tr.studying_study_now()

		bottom_actions_html = ""
		if show_toolbar_replacements:
			# Check if current deck is filtered (dynamic)
			current_deck = self.mw.col.decks.current()
			is_filtered = current_deck and current_deck.get("dyn", False)
			
			if is_filtered:
				# Filtered deck buttons: Options, Rebuild, Empty
				bottom_actions_html = (
					'<div class="overview-bottom-actions">'
					'<a href="#" key=O onclick="pycmd(\'opts\'); return false;" class="overview-button">Options</a>'
					'<a href="#" key=R onclick="pycmd(\'refresh\'); return false;" class="overview-button">Rebuild</a>'
					'<a href="#" key=E onclick="pycmd(\'empty\'); return false;" class="overview-button">Empty</a>'
					'</div>'
				)
			else:
				# Non-filtered deck buttons: Options, Custom Study, Description
				bottom_actions_html = (
					'<div class="overview-bottom-actions">'
					'<a href="#" key=O onclick="pycmd(\'opts\'); return false;" class="overview-button overview-button-normal">Options</a>'
					'<a href="#" key=C onclick="pycmd(\'studymore\'); return false;" class="overview-button overview-button-normal">Custom Study</a>'
					'<a href="#" onclick="pycmd(\'description\'); return false;" class="overview-button overview-button-normal">Description</a>'
					'</div>'
				)

		return (
			'<div class="overview-container">'
				'<div class="stats-container">'
					f'{rows_html}'
				'</div>'
				f'<button id="study" class="add-button-dashed" onclick="pycmd(\'study\'); return false;" autofocus>'
					f'{study_now_text}'
				'</button>'
				f'{bottom_actions_html}'
				'<button id="onigiri-reveal-btn">Click to reveal</button>'
			'</div>'
		)

	Overview._table = new_table
	
	header_html = ""
	if show_toolbar_replacements and not flow_mode:
		header_html = """
    <div id="onigiri-overview-header" class="overview-header">
        <div class="onigiri-reviewer-header-buttons">
            <a href="#" onclick="pycmd('decks'); return false;" class="onigiri-reviewer-button">Decks</a>
            <a href="#" onclick="pycmd('add'); return false;" class="onigiri-reviewer-button">Add</a>
            <a href="#" onclick="pycmd('browse'); return false;" class="onigiri-reviewer-button">Browse</a>
            <a href="#" onclick="pycmd('stats'); return false;" class="onigiri-reviewer-button">Stats</a>
            <a href="#" onclick="pycmd('sync'); return false;" class="onigiri-reviewer-button">Sync</a>
        </div>
    </div>
"""

	js_code = """
    document.addEventListener("DOMContentLoaded", function() {
        // Onigiri Deck Title Fix
        const titleElement = document.querySelector('.overview-title');
        if (titleElement) {
            // Anki provides the full deck path, so we split it by "::" and take the last part.
            const fullTitle = titleElement.textContent;
            const shortTitle = fullTitle.split('::').pop();
            titleElement.textContent = shortTitle;
        }
        
        if (!document.getElementById('onigiri-background-div')) {
            const bgDiv = document.createElement('div');
            bgDiv.id = 'onigiri-background-div';
            document.body.prepend(bgDiv);
        } 

        // NEW SCRIPT TO ADD CLASS TO BODY
        // This allows our CSS to target the body tag and override the alignment
        if (document.querySelector('.overview-center-container.mini-overview')) { 
            document.body.classList.add('mini-overview');
        }
        
        // Collect all external content (anything not Onigiri)
        const container = document.querySelector('.overview-center-container');
        const onigiriHeader = document.getElementById('onigiri-overview-header');
        const onigiriTitle = document.querySelector('.overview-title');
        const onigiriContainer = document.querySelector('.overview-container');
        const revealBtn = document.getElementById('onigiri-reveal-btn');
        
        // Find all direct children of the container that are NOT Onigiri content
        const allExternalElements = [];
        if (container) {
            Array.from(container.children).forEach(function(child) {
                // Skip Onigiri elements and the reveal button
                if (child !== onigiriHeader &&
                    child !== onigiriTitle && 
                    child !== onigiriContainer && 
                    child !== revealBtn && 
                    child.id !== 'onigiri-overview-header' &&
                    child.id !== 'onigiri-reveal-btn' &&
                    !child.classList.contains('overview-header') &&
                    !child.classList.contains('overview-title') &&
                    !child.classList.contains('overview-container')) {
                    
                    // Check if element has visible content
                    const hasVisibleContent = function(el) {
                        // Skip if element is already hidden by CSS
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none') return false;
                        
                        // Check for visible children (excluding hidden elements)
                        const visibleChildren = Array.from(el.children).filter(function(c) {
                            const childStyle = window.getComputedStyle(c);
                            return childStyle.display !== 'none' && c.textContent.trim() !== '';
                        });
                        
                        if (visibleChildren.length > 0) return true;
                        
                        // Check for direct text content (not in child elements)
                        const textContent = Array.from(el.childNodes)
                            .filter(function(node) { return node.nodeType === 3; })
                            .map(function(node) { return node.textContent.trim(); })
                            .join('');
                        
                        return textContent !== '';
                    };
                    
                    if (hasVisibleContent(child)) {
                        allExternalElements.push(child);
                        child.style.display = 'none'; // Hide initially
                    }
                }
            });
        }
        
        // Hide reveal button if there are no external elements with content
        if (revealBtn && allExternalElements.length === 0) {
            revealBtn.style.display = 'none';
        }
        
        // Handle reveal button functionality
        if (revealBtn && allExternalElements.length > 0) {
            let isRevealed = false;
            revealBtn.addEventListener('click', function() {
                isRevealed = !isRevealed;
                
                if (isRevealed) {
                    // Show all external elements
                    allExternalElements.forEach(function(el) {
                        el.style.display = '';
                    });
                    revealBtn.innerHTML = 'Click to hide';
                } else {
                    // Hide all external elements
                    allExternalElements.forEach(function(el) {
                        el.style.display = 'none';
                    });
                    revealBtn.innerHTML = 'Click to reveal';
                }
            });
        }
    });
    """

	reveal_button_css = """
    <style id="onigiri-reveal-button-style">
        #onigiri-reveal-btn {
            display: block;
            margin: 20px auto;
            padding: 10px 20px;
            background: var(--button-primary-bg);
            color: white !important;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        #onigiri-reveal-btn:hover {
            transform: scale(1.05);
        }
        .night-mode #onigiri-reveal-btn {
            color: white !important;
        }
        .descfont.descmid.description.dyn {
            display: none !important;
        }
    </style>
    """

	Overview._body = f"""
{mini_css}
{reveal_button_css}
<div class="overview-center-container {style_class}">
	{header_html}
	<h3 class="overview-title">%(deck)s</h3>
	%(table)s
	<div>%(shareLink)s</div>
	<div>%(desc)s</div>
</div>
<script>{js_code}</script>
"""
    

# --- Congrats Page Patcher ---

def patch_congrats_page():
    """Replaces the default congratulations screen with a custom, stylable one."""
    
    def new_show_finished_screen(self: Overview, _old):
        addon_path = os.path.dirname(__file__)
        conf = config.get_config()
        addon_package = mw.addonManager.addonFromModule(__name__)

        # Check for hide mode to determine if the header should be shown
        show_toolbar_replacements = conf.get("hideNativeHeaderAndBottomBar", False)
        max_hide = conf.get("maxHide", False)

        header_html = ""
        if show_toolbar_replacements and not max_hide:
            header_html = """
            <div class="overview-header">
                <div class="onigiri-reviewer-header-buttons">
                    <a href="#" onclick="pycmd('decks'); return false;" class="onigiri-reviewer-button">Decks</a>
                    <a href="#" onclick="pycmd('add'); return false;" class="onigiri-reviewer-button">Add</a>
                    <a href="#" onclick="pycmd('browse'); return false;" class="onigiri-reviewer-button">Browse</a>
                    <a href="#" onclick="pycmd('stats'); return false;" class="onigiri-reviewer-button">Stats</a>
                    <a href="#" onclick="pycmd('sync'); return false;" class="onigiri-reviewer-button">Sync</a>
                </div>
            </div>
            """

        # 1. Build Profile Bar HTML (if enabled)
        profile_bar_html = ""
        if conf.get("showCongratsProfileBar", True):
            user_name = conf.get("userName", "USER")
            profile_pic_html = _get_profile_pic_html(user_name, addon_package, "profile-pic")

            profile_bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "accent")
            profile_bg_image = mw.col.conf.get("modern_menu_profile_bg_image", "")
            bg_style_str = ""
            bg_class_str = ""

            if profile_bg_mode == "image":
                if profile_bg_image and os.path.exists(os.path.join(mw.addonManager.addonsFolder(addon_package), "user_files", "profile_bg", profile_bg_image)):
                    bg_image_url = f"/_addons/{addon_package}/user_files/profile_bg/{profile_bg_image}"
                else:
                    # Use default background image when none is selected or file doesn't exist
                    bg_image_url = f"/_addons/{addon_package}/system_files/profile_default/onigiri-bg.png"
                bg_style_str = f"background-image: url('{bg_image_url}'); background-size: cover; background-position: center;"
                bg_class_str = "with-image-bg"
            elif profile_bg_mode == "custom":
                bg_style_str = "background-color: var(--profile-bg-custom-color);"
            else: # accent
                bg_style_str = "background-color: var(--accent-color);"
            
            profile_bar_html = f"""
            <div class="profile-bar {bg_class_str}" style="{bg_style_str}" onclick="pycmd('showUserProfile')">
                {profile_pic_html}
                <span class="profile-name">{user_name}</span>
            </div>
            """

        # 2. Get Custom Message with fallback to default
        message = conf.get("congratsMessage", DEFAULTS["congratsMessage"])

        # 3. Build Bottom Actions HTML
        bottom_actions_html = ""
        if show_toolbar_replacements:
            current_deck = self.mw.col.decks.current()
            is_filtered = current_deck and current_deck.get("dyn", False)
            
            if is_filtered:
                # Filtered deck buttons: Options, Rebuild, Empty
                bottom_actions_html = """
                <div class="congrats-bottom-actions">
                    <a href="#" key=O onclick="pycmd('opts'); return false;" class="overview-button">Options</a>
                    <a href="#" key=R onclick="pycmd('refresh'); return false;" class="overview-button">Rebuild</a>
                    <a href="#" key=E onclick="pycmd('empty'); return false;" class="overview-button">Empty</a>
                </div>
                """
            else:
                # Non-filtered deck buttons: Options, Custom Study, Description
                bottom_actions_html = """
                <div class="congrats-bottom-actions">
                    <a href="#" key=O onclick="pycmd('opts'); return false;" class="overview-button">Options</a>
                    <a href="#" key=C onclick="pycmd('studymore'); return false;" class="overview-button">Custom Study</a>
                    <a href="#" onclick="pycmd('description'); return false;" class="overview-button">Description</a>
                </div>
                """

        # 4. Construct Final HTML Body
        body_html = f"""
        <div class="congrats-container">
            {header_html}
            {profile_bar_html}
            <div class="congrats-card">
                <h1>{message}</h1>
            </div>
            {bottom_actions_html}
        </div>
        """
        
        # 5. Generate Head Content (CSS)
        head_html = generate_dynamic_css(conf)
        head_html += generate_overview_background_css(addon_path)
        
        # 6. Render the page
        self.web.stdHtml(
            body_html,
            css=[f"/_addons/{addon_package}/web/congrats.css"],
            js=[], # JS messages are handled by the hook, no need to inject a file
            head=head_html,
            context=self,
        )
        # Manually run JS to create the background div after the page is loaded.
        self.web.eval("""
            if (!document.getElementById('onigiri-background-div')) {
                const bgDiv = document.createElement('div');
                bgDiv.id = 'onigiri-background-div';
                document.body.prepend(bgDiv);
            }
        """)

    Overview._show_finished_screen = wrap(Overview._show_finished_screen, new_show_finished_screen, "around")


def generate_deck_browser_backgrounds(addon_path):
    """Generates CSS for the main container background and sidebar."""
    conf = config.get_config()
    
    main_mode = mw.col.conf.get("modern_menu_background_mode", "color")
    main_image_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
    main_light_color = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
    main_dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
    main_blur = mw.col.conf.get("modern_menu_background_blur", 0)
    main_opacity = mw.col.conf.get("modern_menu_background_opacity", 100)

    # Handle slideshow mode
    if main_mode == "slideshow":
        slideshow_images = mw.col.conf.get("modern_menu_slideshow_images", [])
        slideshow_interval = mw.col.conf.get("modern_menu_slideshow_interval", 10)
        
        if slideshow_images:
            addon_name = os.path.basename(addon_path)
            image_urls = [f"/_addons/{addon_name}/user_files/main_bg/{img}" for img in slideshow_images]
            
            blur_px = main_blur * 0.2
            scale = 1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0
            opacity_float = main_opacity / 100.0
            
            # Generate CSS for slideshow with smooth crossfade effect
            first_image_url = image_urls[0]
            main_container_css = f"""
            <style id='modern-menu-main-background-style'>
                .container.modern-main-menu {{
                    position: relative;
                    z-index: 1;
                    overflow: hidden;
                    background-color: {main_light_color} !important;
                }}
                .night-mode .container.modern-main-menu {{
                    background-color: {main_dark_color} !important;
                }}
                /* Base layer - always visible */
                .container.modern-main-menu::before {{
                    content: '';
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    width: 100%;
                    height: 100%;
                    transform: translate(-50%, -50%) scale({scale});
                    background-image: url('{first_image_url}');
                    background-size: cover;
                    background-position: center;
                    background-repeat: no-repeat;
                    filter: blur({blur_px}px);
                    opacity: {opacity_float};
                    z-index: -2;
                }}
                /* Transition layer - fades in/out */
                .container.modern-main-menu::after {{
                    content: '';
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    width: 100%;
                    height: 100%;
                    transform: translate(-50%, -50%) scale({scale});
                    background-size: cover;
                    background-position: center;
                    background-repeat: no-repeat;
                    filter: blur({blur_px}px);
                    opacity: 0;
                    z-index: -1;
                    transition: opacity 1.2s cubic-bezier(0.4, 0, 0.2, 1);
                }}
                .container.modern-main-menu.slideshow-transitioning::after {{
                    opacity: {opacity_float};
                }}
            </style>
            <script>
                (function() {{
                    const images = {json.dumps(image_urls)};
                    const interval = {slideshow_interval * 1000};
                    let currentIndex = 0;
                    let nextIndex = 1;
                    
                    function updateBackground() {{
                        const container = document.querySelector('.container.modern-main-menu');
                        if (!container) return;
                        
                        // Set the next image on the ::after layer
                        let afterStyleTag = document.getElementById('slideshow-after-image');
                        if (!afterStyleTag) {{
                            afterStyleTag = document.createElement('style');
                            afterStyleTag.id = 'slideshow-after-image';
                            document.head.appendChild(afterStyleTag);
                        }}
                        afterStyleTag.textContent = `.container.modern-main-menu::after {{ background-image: url('${{images[nextIndex]}}'); }}`;
                        
                        // Trigger the fade-in transition
                        setTimeout(() => {{
                            container.classList.add('slideshow-transitioning');
                        }}, 50);
                        
                        // After transition completes, swap layers
                        setTimeout(() => {{
                            // Update the ::before layer with the new image
                            let beforeStyleTag = document.getElementById('slideshow-before-image');
                            if (!beforeStyleTag) {{
                                beforeStyleTag = document.createElement('style');
                                beforeStyleTag.id = 'slideshow-before-image';
                                document.head.appendChild(beforeStyleTag);
                            }}
                            beforeStyleTag.textContent = `.container.modern-main-menu::before {{ background-image: url('${{images[nextIndex]}}'); }}`;
                            
                            // Reset the transition
                            container.classList.remove('slideshow-transitioning');
                            
                            // Update indices
                            currentIndex = nextIndex;
                            nextIndex = (nextIndex + 1) % images.length;
                        }}, 1250); // Slightly longer than transition duration
                    }}
                    
                    // Start slideshow only if there are multiple images
                    if (images.length > 1) {{
                        setInterval(updateBackground, interval);
                    }}
                }})();
            </script>
            """
            main_container_css += "<style>.main-content { background: transparent !important; }</style>"
        else:
            # No images selected, fallback to color mode
            main_container_css = f"""
            <style id='modern-menu-main-background-style'>
                .container.modern-main-menu {{ background-color: {main_light_color} !important; }}
                .night-mode .container.modern-main-menu {{ background-color: {main_dark_color} !important; }}
            </style>
            """
            main_container_css += "<style>.main-content { background: transparent !important; }</style>"
    else:
        # Original image mode handling
        if main_image_mode == "separate":
            main_light_img_filename = mw.col.conf.get("modern_menu_background_image_light", "")
            main_dark_img_filename = mw.col.conf.get("modern_menu_background_image_dark", "")
        else:
            main_light_img_filename = mw.col.conf.get("modern_menu_background_image", "")
            main_dark_img_filename = main_light_img_filename

        main_light_img = f"user_files/main_bg/{main_light_img_filename}" if main_light_img_filename else ""
        main_dark_img = f"user_files/main_bg/{main_dark_img_filename}" if main_dark_img_filename else ""
    
        main_container_css = _render_background_css(
            ".container.modern-main-menu", main_mode, main_light_color, main_dark_color, 
            main_light_img, main_dark_img, main_blur, addon_path, "modern-menu-main-background-style", main_opacity
        )
        main_container_css += "<style>.main-content { background: transparent !important; }</style>"

    sidebar_mode = mw.col.conf.get("modern_menu_sidebar_bg_mode", "main")
    sidebar_css = ""
    if sidebar_mode == 'custom':
        side_mode = mw.col.conf.get("modern_menu_sidebar_bg_type", "color")
        side_light_color = mw.col.conf.get("modern_menu_sidebar_bg_color_light", "#F3F3F3")
        side_dark_color = mw.col.conf.get("modern_menu_sidebar_bg_color_dark", "#2C2C2C")
        side_blur = mw.col.conf.get("modern_menu_sidebar_bg_blur", 0)
        side_img_filename = mw.col.conf.get("modern_menu_sidebar_bg_image", "")
        side_img = f"user_files/sidebar_bg/{side_img_filename}" if side_img_filename else ""
        
        side_opacity = mw.col.conf.get("modern_menu_sidebar_bg_opacity", 100)
        side_transparency = mw.col.conf.get("modern_menu_sidebar_bg_transparency", 0)
        addon_name = os.path.basename(addon_path)

        if side_mode == "color" or side_mode == "accent":
            alpha = (100 - side_transparency) / 100.0
            
            if side_mode == "accent":
                 sidebar_css = f"""<style id='modern-menu-sidebar-background-style'>
                    .sidebar-left {{ position: relative; background: transparent !important; }}
                    .sidebar-left::before {{
                        content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
                        background: var(--accent-color);
                        opacity: {alpha};
                        z-index: -1;
                    }}
                </style>"""
            else: # solid color
                if side_transparency > 0:
                    light_rgba = _hex_to_rgba(side_light_color, alpha)
                    dark_rgba = _hex_to_rgba(side_dark_color, alpha)
                    sidebar_css = f"""<style id='modern-menu-sidebar-background-style'>
                        .sidebar-left {{ background-color: {light_rgba} !important; }}
                        .night-mode .sidebar-left {{ background-color: {dark_rgba} !important; }}
                    </style>"""
                else: # No transparency
                    sidebar_css = f"""<style id='modern-menu-sidebar-background-style'>
                        .sidebar-left {{ background-color: {side_light_color} !important; }}
                        .night-mode .sidebar-left {{ background-color: {side_dark_color} !important; }}
                    </style>"""

        elif side_mode == "image_color" and side_img:
            img_url = f"/_addons/{addon_name}/{side_img}"
            opacity_float = side_opacity / 100.0
            blur_px = side_blur * 0.2

            sidebar_css = f"""
            <style id='modern-menu-sidebar-background-style'>
                .sidebar-left {{
                    position: relative;
                    background-color: {side_light_color} !important;
                    overflow: hidden;
                    z-index: 1;
                }}
                .night-mode .sidebar-left {{
                    background-color: {side_dark_color} !important;
                }}
                .sidebar-left::before {{
                    content: '';
                    position: absolute;
                    top: 50%; left: 50%;
                    width: 100%; height: 100%;
                    transform: translate(-50%, -50%) scale({1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0});
                    background-image: url('{img_url}');
                    background-size: cover;
                    background-position: center;
                    background-repeat: no-repeat;
                    opacity: {opacity_float};
                    filter: blur({blur_px}px);
                    z-index: -1;
                }}
            </style>
            """
    else: # sidebar_mode == 'main'
        effect_mode = mw.col.conf.get("onigiri_sidebar_main_bg_effect_mode", "opaque")
        
        if effect_mode == "glassmorphism":
            intensity = mw.col.conf.get("onigiri_sidebar_main_bg_effect_intensity", 50)
            blur_px = (intensity / 100.0) * 15.0
            alpha = (intensity / 100.0) * 0.3
            
            sidebar_css = f"""
            <style id='modern-menu-sidebar-background-style'>
                .sidebar-left {{
                    background-color: rgba(255, 255, 255, {alpha}) !important;
                    backdrop-filter: blur({blur_px}px);
                    -webkit-backdrop-filter: blur({blur_px}px);
                }}
                .night-mode .sidebar-left {{
                    background-color: rgba(0, 0, 0, {alpha}) !important;
                }}
            </style>
            """
        else: # opaque color overlay
            intensity = mw.col.conf.get("onigiri_sidebar_opaque_tint_intensity", 30)
            alpha = intensity / 100.0
            
            light_color_hex = mw.col.conf.get("onigiri_sidebar_opaque_tint_color_light", "#FFFFFF")
            dark_color_hex = mw.col.conf.get("onigiri_sidebar_opaque_tint_color_dark", "#1D1D1D")
            
            light_rgba = _hex_to_rgba(light_color_hex, alpha)
            dark_rgba = _hex_to_rgba(dark_color_hex, alpha)

            sidebar_css = f"""
            <style id='modern-menu-sidebar-background-style'>
                .sidebar-left {{
                    background-color: {light_rgba} !important;
                }}
                .night-mode .sidebar-left {{
                    background-color: {dark_rgba} !important;
                }}
            </style>
            """
        
    return main_container_css + sidebar_css

def generate_reviewer_background_css(addon_path):
    """Generates CSS for the reviewer - exact copy of overview implementation with reviewer config keys."""
    conf = config.get_config()
    reviewer_mode = conf.get("onigiri_reviewer_bg_mode", "main")
    addon_name = os.path.basename(addon_path)
    
    if reviewer_mode == "main":
        # Use main background settings (like overview does)
        mode = mw.col.conf.get("modern_menu_background_mode", "color")
        light_color = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
        dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
        blur_val = conf.get("onigiri_reviewer_bg_main_blur", 0)
        opacity_val = conf.get("onigiri_reviewer_bg_main_opacity", 100)
        
        if mode not in ["image", "image_color"]:
            return f"""<style id="onigiri-reviewer-background-style">
                body {{ background-color: {light_color} !important; }}
                .night-mode body {{ background-color: {dark_color} !important; }}
            
                #qa, #_flag {{
                    font-family: revert !important;
                }}

                /* Reset background inheritance for card content areas to prevent interference with card templates */
                #qa, #qa *, #_flag, #_flag * {{
                    background-attachment: initial !important;
                    background-blend-mode: initial !important;
                    background-clip: initial !important;
                    background-origin: initial !important;
                }}

                body.card {{
                    isolation: isolate;
                }}
            </style>"""

        image_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
        if image_mode == "separate":
            light_img_file = mw.col.conf.get("modern_menu_background_image_light", "")
            dark_img_file = mw.col.conf.get("modern_menu_background_image_dark", "")
        else:
            light_img_file = mw.col.conf.get("modern_menu_background_image", "")
            dark_img_file = light_img_file

        light_img_url = f"/_addons/{addon_name}/user_files/main_bg/{light_img_file}" if light_img_file else "none"
        dark_img_url = f"/_addons/{addon_name}/user_files/main_bg/{dark_img_file}" if dark_img_file else "none"
        
    elif reviewer_mode == "color":
        # Solid color only
        light_color = conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF")
        dark_color = conf.get("onigiri_reviewer_bg_dark_color", "#2C2C2C")
        return f"""<style id="onigiri-reviewer-background-style">
            body {{ background-color: {light_color} !important; }}
            .night-mode body {{ background-color: {dark_color} !important; }}
            
            /* Ensure card content maintains complete independence from Onigiri's background system */
            #qa, #qa * {{
                background-attachment: initial !important;
                background-blend-mode: initial !important;
                background-clip: initial !important;
                background-origin: initial !important;
            }}
            
            body.card {{
                isolation: isolate;
            }}
        </style>"""
    
    else:  # image_color mode
        light_color = conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF")
        dark_color = conf.get("onigiri_reviewer_bg_dark_color", "#2C2C2C")
        blur_val = conf.get("onigiri_reviewer_bg_blur", 0)
        opacity_val = conf.get("onigiri_reviewer_bg_opacity", 100)
        
        image_mode = conf.get("onigiri_reviewer_bg_image_mode", "single")
        if image_mode == "separate":
            light_img_file = conf.get("onigiri_reviewer_bg_image_light", "")
            dark_img_file = conf.get("onigiri_reviewer_bg_image_dark", "")
        else:
            light_img_file = conf.get("onigiri_reviewer_bg_image_light", "")
            dark_img_file = light_img_file

        light_img_url = f"/_addons/{addon_name}/user_files/reviewer_bg/{light_img_file}" if light_img_file else "none"
        dark_img_url = f"/_addons/{addon_name}/user_files/reviewer_bg/{dark_img_file}" if dark_img_file else "none"

    # EXACT COPY of overview CSS generation
    blur_px = blur_val * 0.2
    opacity_float = opacity_val / 100.0

    return f"""
    <style id="onigiri-reviewer-background-style">
        /* Use body::before pseudo-element for instant background rendering - no JavaScript delay */
        body {{
            position: relative;
            background-color: {light_color} !important;
        }}
        .night-mode body {{
            background-color: {dark_color} !important;
        }}
        
        body::before {{
            content: '';
            position: fixed;
            top: 50%; left: 50%;
            width: 100vw; height: 100vh;
            transform: translate(-50%, -50%) scale({1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0});
            background-position: center;
            background-size: cover;
            background-repeat: no-repeat;
            z-index: -1;
            filter: blur({blur_px}px);
            opacity: {opacity_float};
            pointer-events: none;
            background-image: url('{light_img_url}');
        }}
        .night-mode body::before {{
            background-image: url('{dark_img_url}');
        }}
        
        html, .overview-center-container, .congrats-container {{
            background: transparent !important;
        }}
        
        /* Ensure card content maintains complete independence from Onigiri's background system */
        /* Reset background inheritance for card content areas to prevent interference with card templates */
        #qa, #qa * {{
            background-attachment: initial !important;
            background-blend-mode: initial !important;
            background-clip: initial !important;
            background-origin: initial !important;
        }}
        
        /* Prevent body::before from affecting card content rendering */
        body.card {{
            isolation: isolate;
        }}
    </style>
    """

def generate_overview_background_css(addon_path):
    """Generates CSS for the overview screen with instant background rendering using CSS pseudo-elements."""
    conf = config.get_config()
    overview_mode = conf.get("onigiri_overview_bg_mode", "main")
    
    # Defaults
    light_color = "#F5F5F5"
    dark_color = "#2C2C2C"
    blur_val = 0
    opacity_val = 100
    light_img_file = ""
    dark_img_file = ""
    is_image_mode = False

    if overview_mode == "main":
        # Use main menu background settings
        main_mode = mw.col.conf.get("modern_menu_background_mode", "color")
        light_color = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
        dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
        
        # Use overview-specific blur/opacity for main mode
        blur_val = conf.get("onigiri_overview_bg_main_blur", 0)
        opacity_val = conf.get("onigiri_overview_bg_main_opacity", 100)
        
        if main_mode in ["image", "image_color"]:
            is_image_mode = True
            image_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
            if image_mode == "separate":
                light_img_file = mw.col.conf.get("modern_menu_background_image_light", "")
                dark_img_file = mw.col.conf.get("modern_menu_background_image_dark", "")
            else:
                light_img_file = mw.col.conf.get("modern_menu_background_image", "")
                dark_img_file = light_img_file
                
    elif overview_mode == "color":
        # Solid color only
        light_color = conf.get("onigiri_overview_bg_light_color", "#FFFFFF")
        dark_color = conf.get("onigiri_overview_bg_dark_color", "#2C2C2C")
        is_image_mode = False
        
    elif overview_mode == "image_color":
        # Image + Color
        light_color = conf.get("onigiri_overview_bg_light_color", "#FFFFFF")
        dark_color = conf.get("onigiri_overview_bg_dark_color", "#2C2C2C")
        
        blur_val = conf.get("onigiri_overview_bg_blur", 0)
        opacity_val = conf.get("onigiri_overview_bg_opacity", 100)
        is_image_mode = True
        
        image_mode = conf.get("onigiri_overview_bg_image_theme_mode", "single")
        if image_mode == "separate":
            light_img_file = conf.get("onigiri_overview_bg_image_light", "")
            dark_img_file = conf.get("onigiri_overview_bg_image_dark", "")
        else:
            light_img_file = conf.get("onigiri_overview_bg_image", "")
            dark_img_file = light_img_file

    if not is_image_mode:
        return f"""<style>
            body {{ background-color: {light_color} !important; }}
            .night-mode body {{ background-color: {dark_color} !important; }}
        </style>"""

    addon_name = os.path.basename(addon_path)
    light_img_url = f"/_addons/{addon_name}/user_files/main_bg/{light_img_file}" if light_img_file else "none"
    dark_img_url = f"/_addons/{addon_name}/user_files/main_bg/{dark_img_file}" if dark_img_file else "none"

    blur_px = blur_val * 0.2
    opacity_float = opacity_val / 100.0

    return f"""
    <style id="onigiri-overview-background-style">
        /* Use body::before pseudo-element for instant background rendering - no JavaScript delay */
        body {{
            position: relative;
            background-color: {light_color} !important;
        }}
        .night-mode body {{
            background-color: {dark_color} !important;
        }}
        
        body::before {{
            content: '';
            position: fixed;
            top: 50%; left: 50%;
            width: 100vw; height: 100vh;
            transform: translate(-50%, -50%) scale({1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0});
            background-position: center;
            background-size: cover;
            background-repeat: no-repeat;
            z-index: -1;
            filter: blur({blur_px}px);
            opacity: {opacity_float};
            pointer-events: none;
            background-image: url('{light_img_url}');
        }}
        .night-mode body::before {{
            background-image: url('{dark_img_url}');
        }}
        
        /* Keep JavaScript-created div styling for backwards compatibility */
        #onigiri-background-div {{
            display: none !important;
        }}
        
        html, .overview-center-container, .congrats-container {{
            background: transparent !important;
        }}
    </style>
    """

def generate_toolbar_background_css(addon_path):
	"""Generates background CSS for the top and bottom toolbars based on user settings."""
	toolbar_mode = mw.col.conf.get("onigiri_toolbar_bg_mode", "main")

	if toolbar_mode == "main":
		# Use main background settings
		mode = mw.col.conf.get("modern_menu_background_mode", "color")
		light = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
		dark = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
		image = mw.col.conf.get("modern_menu_background_image", "")
		blur = mw.col.conf.get("modern_menu_background_blur", 0)
		opacity = 100 # Opacity not supported for toolbar custom bg yet
		image_path = f"user_files/{image}" if image else ""
	else:
		# Use toolbar-specific settings
		mode = toolbar_mode
		light = mw.col.conf.get("onigiri_toolbar_bg_color_light", "#FFFFFF")
		dark = mw.col.conf.get("onigiri_toolbar_bg_color_dark", "#2C2C2C")
		image = mw.col.conf.get("onigiri_toolbar_bg_image", "")
		blur = mw.col.conf.get("onigiri_toolbar_bg_blur", 0)
		opacity = 100 # Opacity not supported for toolbar custom bg yet
		image_path = f"user_files/toolbar_bg/{image}" if image else ""

	return _render_background_css("body", mode, light, dark, image_path, image_path, blur, addon_path, "onigiri-toolbar-bg-style", opacity)

def generate_reviewer_top_bar_html_and_css():
    """Generates the HTML and basic structural CSS for the new web-based reviewer top bar."""

    conf = config.get_config()
    is_base_hide_mode = (
        conf.get("hideNativeHeaderAndBottomBar", False)
        and not conf.get("flowMode", False)
    )
    if not is_base_hide_mode:
        return "", ""

    # Check if restaurant level should be shown in reviewer header
    show_restaurant_chip = False
    restaurant_chip_html = ""
    
    # Get restaurant level config
    restaurant_conf = conf.get("restaurant_level", {})
    if not restaurant_conf:
        achievements_conf = conf.get("achievements", {})
        restaurant_conf = achievements_conf.get("restaurant_level", {})
    
    if (restaurant_conf.get("enabled", False) and 
        restaurant_conf.get("show_reviewer_header", False)):
        try:
            from .gamification import restaurant_level
            progress = restaurant_level.manager.get_progress()
            if progress and progress.enabled:
                show_restaurant_chip = True
                # Get progress data using the correct property names
                current_level = getattr(progress, 'level', 0)
                xp_into_level = max(0, getattr(progress, 'xp_into_level', 0))
                xp_to_next_level = max(1, getattr(progress, 'xp_to_next_level', 100))
                progress_percent = min(100, max(0, (xp_into_level / xp_to_next_level) * 100))
                
                # Format the progress bar with proper escaping
                restaurant_chip_html = f"""
                <div class="restaurant-level-chip" onclick="pycmd('restaurant_level')">
                    <div class="level-progress-container">
                        <div class="level-progress-bar" style="width: {progress_percent:.2f}%"></div>
                        <div class="level-progress-text">
                            <span class="level-text">Lv. {current_level}</span>
                            <span class="xp-text">{xp_into_level}/{xp_to_next_level} XP</span>
                        </div>
                    </div>
                </div>
                """.format(
                    progress_percent=progress_percent,
                    current_level=current_level,
                    xp_into_level=xp_into_level,
                    xp_to_next_level=xp_to_next_level
                )
                
                # Register the hook if not already registered
                if not hasattr(mw, '_onigiri_restaurant_hook_registered'):
                    from aqt import gui_hooks
                    gui_hooks.reviewer_did_answer_card.append(on_reviewer_did_answer_card)
                    mw._onigiri_restaurant_hook_registered = True
                    
        except Exception as e:
            print(f"Error getting restaurant level: {e}")

    # Build the HTML with the restaurant chip if enabled
    header_buttons = """
    <div class="onigiri-reviewer-header-buttons">
        <a href="#" onclick="pycmd('decks'); return false;" class="onigiri-reviewer-button">Decks</a>
        <a href="#" onclick="pycmd('add'); return false;" class="onigiri-reviewer-button">Add</a>
        <a href="#" onclick="pycmd('browse'); return false;" class="onigiri-reviewer-button">Browse</a>
        <a href="#" onclick="pycmd('stats'); return false;" class="onigiri-reviewer-button">Stats</a>
        <a href="#" onclick="pycmd('sync'); return false;" class="onigiri-reviewer-button">Sync</a>
        {}
    </div>
    """.format(restaurant_chip_html if show_restaurant_chip else "")
    
    html = f"""
    <div id="onigiri-reviewer-header" class="header">
        {header_buttons}
    </div>
    """

    css = """
    <style id="onigiri-reviewer-top-bar-structure">
        :root {
            --onigiri-reviewer-header-offset: 65px;
        }
        
        html {
            scroll-padding-top: var(--onigiri-reviewer-header-offset);
        }

        #onigiri-reviewer-header, .overview-header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            width: 35%;
            margin: 10px auto;
            margin-top: 5px;
            border-radius: 12px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0 10px;
            box-sizing: border-box;
            -webkit-font-smoothing: antialiased;
            pointer-events: auto;
            z-index: 1000; /* Increased z-index */
        }
        
        /* Prevent content from going under the header */
        #qa {
            padding-top: 20px; /* Height of header + some margin */
            position: relative;
            z-index: 1; /* Lower than header */
        }
        
        .onigiri-reviewer-header-buttons {
            display: flex;
            gap: 10px;
        }

        .onigiri-reviewer-button {
            color: var(--fg);
            background: rgba(247, 247, 247);
            padding: 5px 12px;
            border-radius: 8px;
            border: 1px solid rgba(128, 128, 128, 0.2);
            font-size: 13px;
            text-decoration: none;
            transition: background-color 0.2s ease, border-color 0.2s ease;
        }

        .night_mode .onigiri-reviewer-button {
            color: var(--fg);
            background: rgba(42, 42, 42);
            padding: 5px 12px;
            border-radius: 8px;
            font-size: 13px;
            font-color: white;
            text-decoration: none;
            transition: background-color 0.2s ease, border-color 0.2s ease;
        }

        .onigiri-reviewer-button:hover {
            background: rgba(128, 128, 128, 0.25);
            color: white;
        }
        
        /* Restaurant level progress bar styles */
        .restaurant-level-chip {
            display: flex;
            align-items: center;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 12px;
            padding: 0;
            margin-left: 12px;
            width: 180px;
            height: 28px;
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .night_mode .restaurant-level-chip {
            background: rgba(0, 0, 0, 0.3);
            border-color: rgba(255, 255, 255, 0.05);
        }
        
        .level-progress-container {
            position: relative;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .level-progress-bar {
            position: absolute;
            left: 0;
            top: 0;
            height: 100%;
            background: linear-gradient(90deg, #ffb347, #ff6b6b);
            border-radius: 8px;
            transition: width 0.5s ease-out;
            z-index: 1;
            box-shadow: 0 0 10px rgba(76, 175, 80, 0.3);
        }
        
        .level-progress-text {
            position: relative;
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
            z-index: 2;
            font-size: 12px;
            font-weight: 600;
            color: white;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.7);
            padding: 0 12px;
            box-sizing: border-box;
            height: 100%;
        }
        
        .level-text {
            font-weight: 700;
            display: flex;
            align-items: center;
            text-shadow: none !important;
        }
        

        
        .xp-text {
            font-size: 11px;
            opacity: 0.95;
            background: rgba(0, 0, 0, 0.2);
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 500;
        }
        
        .restaurant-level-chip:hover {
            transform: translateY(-1px);
            box-shadow: 0 3px 6px rgba(0,0,0,0.15);
        }
        
        .restaurant-level-chip:hover .level-progress-bar {
            background: linear-gradient(90deg, #ff9a3c, #ff5e62);
            box-shadow: 0 0 15px rgba(255, 107, 107, 0.4);
        }

        /* Create space for the header and ensure proper stacking */
        body.card {
            --onigiri-reviewer-header-offset: 65px;
            padding-top: var(--onigiri-reviewer-header-offset) !important;
            box-sizing: border-box !important;
            min-height: 100vh !important;
        }
        
        /* Ensure card content stays below the header */
        #qa {
            position: relative !important;
            z-index: 1 !important;
            margin-top: 0 !important;
            scroll-margin-top: var(--onigiri-reviewer-header-offset) !important;
        }

        #question,
        #answer,
        #typeans,
        #typeans input,
        #answer .card,
        #question .card {
            scroll-margin-top: var(--onigiri-reviewer-header-offset) !important;
        }
    </style>
    """

    
    # Inject theme color CSS if a theme is active
    if show_restaurant_chip:
        theme_color = restaurant_level.manager.get_current_theme_color()
        if theme_color:
            # Convert hex to RGB for shadow
            r = int(theme_color[1:3], 16)
            g = int(theme_color[3:5], 16)
            b = int(theme_color[5:7], 16)
            css += f"""
    <style id="onigiri-reviewer-theme-colors">
        .onigiri-reviewer-header-buttons .level-progress-bar {{
            background: {theme_color} !important;
            box-shadow: 0 0 10px rgba({r}, {g}, {b}, 0.3) !important;
        }}
    </style>
    """
    
    return html, css

def _generate_outer_background_css(mode, light_color, dark_color, light_img_path, dark_img_path, blur_val, opacity_val, addon_path, bg_position):
    """Generate CSS for #outer element with ::before pseudo-element for background.
    This ensures buttons are not affected by opacity/blur."""
    addon_name = os.path.basename(addon_path)
    blur_px = blur_val * 0.2
    opacity_float = opacity_val / 100.0
    
    # Base styling for #outer
    base_css = "<style id='onigiri-reviewer-bottom-bar-bg-style'>"
    base_css += "#outer { position: relative; border: none !important; border-top: none !important; outline: none !important; overflow: hidden; box-sizing: border-box; }"
    
    if mode == "color":
        # Solid color background - apply directly to #outer
        base_css += f"""
            #outer {{ background-color: {light_color} !important; }}
            .night-mode #outer {{ background-color: {dark_color} !important; }}
        """
    elif mode in ["image", "image_color"]:
        # Image background with ::before pseudo-element
        def get_img_url(img_path):
            if not img_path:
                return None
            if img_path.startswith("user_files/"):
                return f"/_addons/{addon_name}/{img_path}"
            else:
                return f"/_addons/{addon_name}/user_files/{img_path}"
        
        light_img_url = get_img_url(light_img_path)
        dark_img_url = get_img_url(dark_img_path) if dark_img_path else light_img_url
        
        if mode == "image_color":
            # Solid color as base layer on #outer
            base_css += f"""
                #outer {{ background-color: {light_color} !important; }}
                .night-mode #outer {{ background-color: {dark_color} !important; }}
            """
        else:
            # No color, transparent background
            base_css += "#outer { background: transparent !important; }"
        
        if light_img_url:
            # Add ::before pseudo-element for image on top of the color
            # Using z-index: 0 so it's above the background but below content
            # Apply slight scale even with no blur to prevent edge artifacts
            scale_factor = max(1.02, 1.0 + (blur_px / 50.0)) if blur_px > 0 else 1.02
            base_css += f"""
                #outer::before {{
                    content: '';
                    position: absolute;
                    top: 0; left: 0;
                    width: 100%; height: 100%;
                    transform: scale({scale_factor});
                    background-image: url('{light_img_url}');
                    background-size: cover;
                    background-position: {bg_position};
                    background-repeat: no-repeat;
                    filter: blur({blur_px}px);
                    opacity: {opacity_float};
                    z-index: 0;
                    pointer-events: none;
                    border: none !important;
                    outline: none !important;
                }}
                #outer > * {{
                    position: relative;
                    z-index: 1;
                }}
            """
            
            if dark_img_url and dark_img_url != light_img_url:
                base_css += f"""
                    .night-mode #outer::before {{
                        background-image: url('{dark_img_url}');
                    }}
                """
    
    base_css += "</style>"
    return base_css

def generate_reviewer_bottom_bar_background_css(addon_path: str) -> str:
    """Generates CSS for the reviewer's bottom bar background."""
    conf = config.get_config()
    # FIX: Read from conf, not mw.col.conf
    bar_mode = conf.get("onigiri_reviewer_bottom_bar_bg_mode", "match_reviewer_bg")

    bg_position = "center bottom"

    css = ""
    # We don't use 'selector' variable effectively in the original code's structure for this function, 
    # but we'll keep the structure clean.

    # Helper to get main window settings
    def get_main_bg_settings():
        # Main settings are in mw.col.conf
        main_mode = mw.col.conf.get("modern_menu_background_mode", "color")
        light_c = mw.col.conf.get("modern_menu_bg_color_light", "#FFFFFF")
        dark_c = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
        
        # Image handling for main
        img_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
        if img_mode == "separate":
            l_img = mw.col.conf.get("modern_menu_background_image_light", "")
            # If separate mode but no light image, fallback might be needed or it's just empty
            # But usually main bg logic handles this.
            # For main bg, the key 'modern_menu_background_image' is used for single mode.
        else:
            l_img = mw.col.conf.get("modern_menu_background_image", "")
        
        # For dark image in separate mode
        if img_mode == "separate":
            d_img = mw.col.conf.get("modern_menu_background_image_dark", "")
        else:
            d_img = l_img

        # Path adjustment for main images
        # Main images are in user_files/main_bg/
        l_img_path = f"user_files/main_bg/{l_img}" if l_img else ""
        d_img_path = f"user_files/main_bg/{d_img}" if d_img else ""

        return main_mode, light_c, dark_c, l_img_path, d_img_path

    # Helper to get reviewer settings
    def get_reviewer_bg_settings():
        # Reviewer settings are in conf
        rev_mode = conf.get("onigiri_reviewer_bg_mode", "main")
        
        if rev_mode == "main":
            return get_main_bg_settings()
            
        light_c = conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF")
        dark_c = conf.get("onigiri_reviewer_bg_dark_color", "#2C2C2C")
        
        img_mode = conf.get("onigiri_reviewer_bg_image_mode", "single")
        if img_mode == "separate":
            l_img = conf.get("onigiri_reviewer_bg_image_light", "")
            d_img = conf.get("onigiri_reviewer_bg_image_dark", "")
        else:
            l_img = conf.get("onigiri_reviewer_bg_image", "") # Fallback or same key? Settings saves to 'image' and 'image_light'/'image_dark'
            # Let's check settings.py saving logic. 
            # It saves to 'onigiri_reviewer_bg_image' for single, and 'onigiri_reviewer_bg_image_light'/'dark' for separate.
            # But let's be safe and check specific keys.
            if not l_img:
                 l_img = conf.get("onigiri_reviewer_bg_image_light", "")
            d_img = l_img

        # Reviewer images are in user_files/reviewer_bg/
        l_img_path = f"user_files/reviewer_bg/{l_img}" if l_img else ""
        d_img_path = f"user_files/reviewer_bg/{d_img}" if d_img else ""
        
        return rev_mode, light_c, dark_c, l_img_path, d_img_path


    if bar_mode == "main":
        # Match Main Background DIRECTLY
        mode, light_color, dark_color, light_img, dark_img = get_main_bg_settings()
        
        # Use bottom bar specific blur and opacity settings for "Match Main"
        blur_val = conf.get("onigiri_reviewer_bottom_bar_match_main_blur", 5)
        opacity_val = conf.get("onigiri_reviewer_bottom_bar_match_main_opacity", 90)

        css += _generate_outer_background_css(mode, light_color, dark_color, light_img, dark_img, blur_val, opacity_val, addon_path, bg_position)

    elif bar_mode == "match_reviewer_bg":
        # Match Reviewer Background (which might itself match Main)
        mode, light_color, dark_color, light_img, dark_img = get_reviewer_bg_settings()
        
        # Use bottom bar specific blur and opacity settings for "Match Reviewer"
        blur_val = conf.get("onigiri_reviewer_bottom_bar_match_reviewer_bg_blur", 5)
        opacity_val = conf.get("onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity", 90)

        css += _generate_outer_background_css(mode, light_color, dark_color, light_img, dark_img, blur_val, opacity_val, addon_path, bg_position)

    else: # Custom settings for the bar
        mode = bar_mode # "color" or "image_color" (mapped from radio buttons)
        
        # FIX: Read from conf, not mw.col.conf
        light_color = conf.get("onigiri_reviewer_bottom_bar_bg_light_color", "#FFFFFF")
        dark_color = conf.get("onigiri_reviewer_bottom_bar_bg_dark_color", "#2C2C2C")
        
        img_filename = conf.get("onigiri_reviewer_bottom_bar_bg_image", "")
        img = f"user_files/reviewer_bar_bg/{img_filename}" if img_filename else ""
        
        blur_val = conf.get("onigiri_reviewer_bottom_bar_bg_blur", 0)
        opacity_val = conf.get("onigiri_reviewer_bottom_bar_bg_opacity", 100)

        # Generate CSS for #outer with ::before pseudo-element for background
        css += _generate_outer_background_css(mode, light_color, dark_color, img, img, blur_val, opacity_val, addon_path, bg_position)

    return css

def generate_profile_bar_fix_css():
    """Generates responsive CSS to ensure the profile picture fits within the profile bar."""
    return """
<style id="onigiri-profile-bar-fix">
/* --- NEW RULES START --- */
.profile-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    overflow: hidden;
    box-sizing: border-box;
    
    position: relative; /* Establishes a positioning context for the picture */
    flex-shrink: 0;     /* Prevents the bar itself from shrinking vertically */
    
    /* Top, Right, Bottom, Left padding. Left padding makes space for the picture. */
    padding: 6px 8px 6px 50px; 
    min-height: 50px; /* Ensures the bar has a minimum size */
}

.profile-pic, .profile-pic-placeholder {
    position: absolute;   /* Positions the picture relative to the bar */
    top: 5px;             /* 5px from the top of the bar */
    left: 5px;            /* 5px from the left of the bar */
    
    /* Forces the height to be the container's height minus 10px (for padding) */
    height: calc(100% - 10px);
    width: auto;          /* Width will follow height due to aspect-ratio */
    aspect-ratio: 1 / 1;  /* Guarantees it is a perfect circle */
    
    border-radius: 50%;
}
/* --- NEW RULES END --- */

.profile-pic {
    object-fit: cover;
}

.profile-pic-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: clamp(14px, 4vw, 20px);
    background-color: rgba(0,0,0,0.1);
    border: 1px solid rgba(255,255,255,0.1);
}

.profile-name {
    font-weight: 500;
    font-size: 16px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
</style>
"""

def generate_icon_size_css():
    """
    Generates CSS to control the size of various icons based on user settings.
    """
    # These keys correspond to the settings in the "Icons" tab.
    icon_configs = {
        "deck_folder": {
            "selector": "a.deck::before",
            "default": 18,
        },
        "action_button": {
            "selector": ".menu-item .icon, .add-button-dashed .icon",
            "default": 16,
        },
        "collapse": {
            "selector": "a.collapse, span.collapse",
            "default": 16,
        },
        "options_gear": {
            "selector": "td.opts a",
            "default": 16,
        },
    }

    css_rules = []
    for key, config in icon_configs.items():
        config_key = f"modern_menu_icon_size_{key}"
        size = mw.col.conf.get(config_key, config["default"])
        selector = config["selector"]
        css_rules.append(f"{selector} {{ width: {size}px; height: {size}px; }}")

    return f"<style id='modern-menu-icon-size-styles'>{''.join(css_rules)}</style>"

def generate_icon_css(addon_package, conf):
    all_icon_selectors = {
        "options": "td.opts a", "folder": "tr.deck:has(a.collapse) a.deck::before",
        "deck_child": "tr.deck:has(span.collapse) a.deck::before", "add": ".action-add .icon",
        "browse": ".action-browse .icon", "stats": ".action-stats .icon", "sync": ".action-sync .icon",
        "settings": ".action-settings .icon", "more": ".action-more .icon",
        "get_shared": ".action-get-shared .icon", "create_deck": ".action-create-deck .icon",
        "import_file": ".action-import-file .icon",
        "retention_star": ".star",
        "focus": ".deck-focus-btn .icon",
        "edit": ".deck-edit-btn .icon",
    }
    
    css_rules = []
    for key, selector in all_icon_selectors.items():
        filename = mw.col.conf.get(f"modern_menu_icon_{key}", "")
        url = ""
        if filename:
            url = f"url('/_addons/{addon_package}/user_files/icons/{filename}')"
        else:
            system_icon_name = 'star' if key == 'retention_star' else key
            url = f"url('/_addons/{addon_package}/system_files/system_icons/{system_icon_name}.svg')"
        
        css_rules.append(f"{selector} {{ mask-image: {url}; -webkit-mask-image: {url}; }}")

    # --- Get URLs for collapse icons ---
    closed_icon_file = mw.col.conf.get("modern_menu_icon_collapse_closed", "")
    open_icon_file = mw.col.conf.get("modern_menu_icon_collapse_open", "")

    closed_icon_url = f"url('/_addons/{addon_package}/user_files/icons/{closed_icon_file}')" if closed_icon_file \
        else f"url('/_addons/{addon_package}/system_files/system_icons/collapse_closed.svg')"

    open_icon_url = f"url('/_addons/{addon_package}/user_files/icons/{open_icon_file}')" if open_icon_file \
        else f"url('/_addons/{addon_package}/system_files/system_icons/collapse_open.svg')"
        
    # Create a list of selectors for the background color, EXCLUDING the star
    bg_color_selectors = {k: v for k, v in all_icon_selectors.items() if k != "retention_star"}
    bg_selectors_str = ", ".join(bg_color_selectors.values())

    return f"""
<style id="modern-menu-icon-styles">
    /* Hide the original '+' or '-' text from the link. */
    a.collapse {{
        font-size: 0 !important;
    }}

    /* Create the icon using a pseudo-element on the link. */
    a.collapse::before {{
        content: '';
        display: inline-block;
        width: 100%;
        height: 100%;
        /* START FIX: Set background to transparent by default to prevent flash */
        background-color: transparent;
        transition: background-color 0.1s ease;
        /* END FIX */
        mask-size: contain;
        mask-repeat: no-repeat;
        mask-position: center;
        -webkit-mask-size: contain;
        -webkit-mask-repeat: no-repeat;
        -webkit-mask-position: center;
    }}

    /* Apply the correct SVG icon and background color only when the state class is present. */
    a.collapse.state-closed::before {{
        mask-image: {closed_icon_url};
        -webkit-mask-image: {closed_icon_url};
        background-color: var(--icon-color, #888888);
        /* END FIX */
    }}
    a.collapse.state-open::before {{
        mask-image: {open_icon_url};
        -webkit-mask-image: {open_icon_url};
        /* START FIX: Apply background color here */
        background-color: var(--icon-color, #888888);
        /* END FIX */
    }}

    /* General rules for other icons (Unchanged) */
    {bg_selectors_str} {{
        background-color: var(--icon-color, #888888);
        mask-size: contain;
        mask-repeat: no-repeat;
        mask-position: center;
        -webkit-mask-size: contain;
        -webkit-mask-repeat: no-repeat;
        -webkit-mask-position: center;
        display: inline-block;
    }}
    /* Individual mask images for other icons (Unchanged) */
    {''.join(css_rules)}
</style>
"""

def generate_conditional_css(conf):
	styles = []
	styles.append("""
        body.deck-browser .sidebar-left.deck-focus-mode .sidebar-expanded-content > #deck-list-header {
            display: flex !important;
        }
    """)
	if conf.get("hideTodaysStats", False):
		styles.append(".stats-grid { display: none !important; }")
	if conf.get("hideDeckCounts", False):
		styles.append(".deck-counts .zero { display: none !important; }")
	if conf.get("hideAllDeckCounts", False):
		styles.append(".deck-counts { display: none !important; }")
	# -- The old, unreliable CSS rule for the header and bottom bar has been removed. --
	if not styles: return ""
	return f"<style id='modern-menu-conditional-styles'>{' '.join(styles)}</style>"

def generate_font_css(addon_package):
    """Generates @font-face rules and CSS variables for selected fonts."""
    main_font_key = mw.col.conf.get("onigiri_font_main", "system")
    subtle_font_key = mw.col.conf.get("onigiri_font_subtle", "system")
    
    # <<< MODIFIED: Use get_all_fonts to include user-added fonts >>>
    all_fonts = get_all_fonts(os.path.dirname(__file__))
    main_font_info = all_fonts.get(main_font_key)
    subtle_font_info = all_fonts.get(subtle_font_key)
    # <<< END MODIFIED >>>

    if not main_font_info or not subtle_font_info:
        return ""

    font_faces = ""
    # Use a set to avoid generating duplicate @font-face rules
    fonts_to_load = {main_font_key, subtle_font_key}
    
    # <<< MODIFIED: Loop through all fonts to generate @font-face rules >>>
    for font_key in fonts_to_load:
        font_info = all_fonts.get(font_key)
        if font_info and font_info.get("file"):
            # Handle different paths for user vs system fonts
            if font_info.get("user"):
                font_url = f"/_addons/{addon_package}/user_files/fonts/{font_info['file']}"
            else:
                font_url = f"/_addons/{addon_package}/system_files/fonts/system_fonts/{font_info['file']}"
            
            font_faces += f"""
                @font-face {{
                    font-family: '{font_info['family']}';
                    src: url('{font_url}');
                }}
            """
    # <<< END MODIFIED >>>

    # Generate the final CSS block
    font_css = f"""
    <style id="onigiri-font-styles">
        {font_faces}
        :root {{
            --font-main: {main_font_info['family']};
            --font-subtle: {subtle_font_info['family']};
        }}
        
        body:not(.card) {{
            font-family: var(--font-main), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        }}
        
        .sidebar-left h2, .stat-card h3 {{
            font-family: var(--font-subtle), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        }}
    </style>
    """
    
    return font_css

def _hex_to_rgba(hex_str: str, alpha: float) -> str:
	"""Converts a hex color string to an rgba string."""
	hex_str = hex_str.lstrip('#')
	if len(hex_str) != 6:
		return f"rgba(0,0,0,{alpha})" # Return a default for invalid hex
	try:
		r, g, b = tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
		return f"rgba({r}, {g}, {b}, {alpha})"
	except ValueError:
		return f"rgba(0,0,0,{alpha})"


def _mix_colors(c1, c2, ratio):
	"""Mixes two colors (hex or rgba) with a given ratio (0.0 to 1.0).
	ratio is the weight of c1.
	"""
	def parse_color(c):
		if not c: return (0, 0, 0, 1.0)
		if c.startswith('#'):
			c = c.lstrip('#')
			if len(c) == 6:
				return tuple(int(c[i:i+2], 16) for i in (0, 2, 4)) + (1.0,)
			elif len(c) == 3:
				return tuple(int(c[i]*2, 16) for i in (0, 1, 2)) + (1.0,)
		elif c.startswith('rgba'):
			parts = c[5:-1].split(',')
			return float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])
		elif c.startswith('rgb'):
			parts = c[4:-1].split(',')
			return float(parts[0]), float(parts[1]), float(parts[2]), 1.0
		return (0, 0, 0, 1.0) # Fallback

	r1, g1, b1, a1 = parse_color(c1)
	r2, g2, b2, a2 = parse_color(c2)

	r = r1 * ratio + r2 * (1 - ratio)
	g = g1 * ratio + g2 * (1 - ratio)
	b = b1 * ratio + b2 * (1 - ratio)
	a = a1 * ratio + a2 * (1 - ratio)

	return f"rgba({int(r)}, {int(g)}, {int(b)}, {a:.2f})"

def generate_dynamic_css(conf):
	# ADDED to get the add-on's path for font files
	addon_package = mw.addonManager.addonFromModule(__name__)
	# ADDED to generate the font-specific CSS
	font_css_block = generate_font_css(addon_package)

	effect_mode = mw.col.conf.get("onigiri_canvas_inset_effect_mode", "none")
	effect_intensity = mw.col.conf.get("onigiri_canvas_inset_effect_intensity", 50)

	def _apply_canvas_inset_effect(colors: dict):
		"""Applies opacity or glassmorphism effect to --canvas-inset color."""
		if "--canvas-inset" not in colors:
			return

		if effect_mode in ["opacity", "glassmorphism"]:
			original_hex = colors["--canvas-inset"]
			
			# Intensity to alpha mapping (0-100 -> 1.0-0.0)
			# For glassmorphism, higher intensity means more transparency.
			alpha = (100 - effect_intensity) / 100.0
			
			# For simple opacity, higher intensity means more opacity.
			if effect_mode == "opacity":
				alpha = effect_intensity / 100.0

			colors["--canvas-inset"] = _hex_to_rgba(original_hex, alpha)

	colors = conf.get("colors", {})
	light_colors = colors.get("light", {}).copy()
	dark_colors = colors.get("dark", {}).copy()

	# Apply effects if enabled
	_apply_canvas_inset_effect(light_colors)
	_apply_canvas_inset_effect(dark_colors)

	# --- START: Calculate Heatmap Colors (to avoid CSS color-mix) ---
	def _generate_heatmap_colors(colors_dict, is_night_mode):
		canvas_inset = colors_dict.get("--canvas-inset", "#ffffff")
		# Get user-defined heatmap colors
		heatmap_color = colors_dict.get("--heatmap-color", "#9be9a8")
		heatmap_color_zero = colors_dict.get("--heatmap-color-zero", "#f0f0f0" if not is_night_mode else "#3a3a3a")
		
		# Past/Due Level 0 - use the user-defined heatmap-color-zero
		colors_dict["--heatmap-level-0"] = heatmap_color_zero
		
		# Levels 1-4 (Past) - blend from heatmap_color to canvas_inset
		colors_dict["--heatmap-level-1"] = _mix_colors(heatmap_color, canvas_inset, 0.25)
		colors_dict["--heatmap-level-2"] = _mix_colors(heatmap_color, canvas_inset, 0.50)
		colors_dict["--heatmap-level-3"] = _mix_colors(heatmap_color, canvas_inset, 0.75)
		colors_dict["--heatmap-level-4"] = heatmap_color
		
		# Future Levels 0-4 - use heatmap_color_zero as base with intensity variations
		colors_dict["--heatmap-future-0"] = heatmap_color_zero
		
		if is_night_mode:
			 # Dark mode: more reviews = lighter shade (mix with white)
			 colors_dict["--heatmap-future-1"] = _mix_colors(heatmap_color_zero, "#ffffff", 0.80)
			 colors_dict["--heatmap-future-2"] = _mix_colors(heatmap_color_zero, "#ffffff", 0.60)
			 colors_dict["--heatmap-future-3"] = _mix_colors(heatmap_color_zero, "#ffffff", 0.40)
			 colors_dict["--heatmap-future-4"] = _mix_colors(heatmap_color_zero, "#ffffff", 0.20)
		else:
			 # Light mode: more reviews = darker shade (mix with black)
			 colors_dict["--heatmap-future-1"] = _mix_colors(heatmap_color_zero, "#000000", 0.88)
			 colors_dict["--heatmap-future-2"] = _mix_colors(heatmap_color_zero, "#000000", 0.76)
			 colors_dict["--heatmap-future-3"] = _mix_colors(heatmap_color_zero, "#000000", 0.64)
			 colors_dict["--heatmap-future-4"] = _mix_colors(heatmap_color_zero, "#000000", 0.52)

	_generate_heatmap_colors(light_colors, False)
	_generate_heatmap_colors(dark_colors, True)
	# --- END: Calculate Heatmap Colors ---

	# Keep all colors, we'll apply them with proper scoping
	light_rules = []
	dark_rules = []
	
	# Non-card related styles (applied globally)
	non_card_related = {
		"--bg", "--bg-elevated", "--bg-hover", "--bg-active",
		"--border", "--border-hover", "--border-active",
		"--shadow-small", "--shadow-medium", "shadow-large",
		"--canvas-inset"
	}
	
	# Add non-card related styles to global rules
	for key, value in light_colors.items():
		if key in non_card_related:
			light_rules.append(f"    {key}: {value} !important;")
		
	for key, value in dark_colors.items():
		if key in non_card_related:
			dark_rules.append(f"    {key}: {value} !important;")
	
	# Add scoped styles for Onigiri UI elements
	onigiri_ui_light = []
	onigiri_ui_dark = []
	
	text_related = {
		"--fg", "--fg-subtle", "--fg-faint", "--fg-on-accent",
		"--accent", "--accent-hover", "--accent-pressed",
		"--text-on-accent", "--text-on-accent-hover", "--text-on-accent-pressed",
		"--accent-light", "--accent-lighter", "--accent-dark", "--accent-darker"
	}
	
	for key, value in light_colors.items():
		if key in text_related:
			onigiri_ui_light.append(f"    {key}: {value} !important;")
			
	for key, value in dark_colors.items():
		if key in text_related:
			onigiri_ui_dark.append(f"    {key}: {value} !important;")
	
	# Convert lists to strings
	light_rules = "\n".join(light_rules)
	dark_rules = "\n".join(dark_rules)
	onigiri_ui_light = "\n".join(onigiri_ui_light)
	onigiri_ui_dark = "\n".join(onigiri_ui_dark)

	# Special case: One setting for two CSS variables
	if "--button-primary-bg" in light_colors:
		light_colors["--button-primary-bg"] = light_colors["--button-primary-bg"]
	if "--button-primary-bg" in dark_colors:
		dark_colors["--button-primary-bg"] = dark_colors["--button-primary-bg"]

	light_rules = "\n".join([f"    {key}: {value} !important;" for key, value in light_colors.items()])
	dark_rules = "\n".join([f"    {key}: {value} !important;" for key, value in dark_colors.items()])
	
	profile_light_color = mw.col.conf.get("modern_menu_profile_bg_color_light", "#EEEEEE")
	profile_dark_color = mw.col.conf.get("modern_menu_profile_bg_color_dark", "#3C3C3C")
	light_rules += f"\n    --profile-bg-custom-color: {profile_light_color} !important;"
	dark_rules += f"\n    --profile-bg-custom-color: {profile_dark_color} !important;"

	# --- New Glassmorphism Style Block ---
	glass_style_block = ""
	if effect_mode == "glassmorphism":
		# Map intensity (0-100) to blur radius (0-20px)
		blur_px = (effect_intensity / 100.0) * 20
		# --- FIX: Added heatmap container IDs to the selectors ---
		glass_selectors = ".stats-container, .congrats-card, .stat-card, #onigiri-heatmap-container, #onigiri-profile-heatmap-container"
		glass_style_block = f"""
        <style id="onigiri-glass-effect">
        {glass_selectors} {{
            backdrop-filter: blur({blur_px}px);
            -webkit-backdrop-filter: blur({blur_px}px);
        }}
        </style>
        """

	# MODIFIED to include scoped Onigiri UI styles and reset card styles
	return f"""
    {font_css_block}
    <style id="modern-menu-dynamic-styles">
    /* Global styles (non-text related) */
    :root {{ {light_rules} }}
    .night-mode {{ {dark_rules} }}
    
    /* Scoped Onigiri UI styles */
    .onigiri-ui, 
    [class*="onigiri-"],
    .modern-menu,
    .modern-menu *:not(.card, .card *),
    .onigiri-profile-page,
    .onigiri-profile-page *:not(.card, .card *),
    .onigiri-restaurant,
    .onigiri-restaurant *:not(.card, .card *) {{
        {onigiri_ui_light}
    }}
    
    .night-mode .onigiri-ui,
    .night-mode [class*="onigiri-"],
    .night-mode .modern-menu,
    .night-mode .modern-menu *:not(.card, .card *),
    .night-mode .onigiri-profile-page,
    .night-mode .onigiri-profile-page *:not(.card, .card *),
    .night-mode .onigiri-restaurant,
    .night-mode .onigiri-restaurant *:not(.card, .card *) {{
        {onigiri_ui_dark}
    }}
    </style>
    {glass_style_block}
    """

def _get_hook_name(hook):
    """Creates a unique, stable identifier for a hook function."""
    module_name = hook.__module__ if hasattr(hook, '__module__') else 'unknown_module'
    return f"{module_name}.{hook.__name__}"

def _get_external_hooks():
    """Returns the list of hooks that Onigiri is managing."""
    return _managed_hooks


def _new_MainWebView_eventFilter(self: MainWebView, obj: QObject, evt: QEvent) -> bool:
	"""Prevents Anki's default hover-to-show-toolbar behavior."""
	conf = config.get_config()
	should_hide_setting = conf.get("hideNativeHeaderAndBottomBar", False)

	screens_to_interfere = ["deckBrowser", "overview", "review"]
	
	should_interfere = should_hide_setting and mw.state in screens_to_interfere

	if should_interfere:
		# On deck browser/overview, prevent Anki's native hover logic from showing toolbars
		if super(MainWebView, self).eventFilter(obj, evt):
			return True
		if evt.type() == QEvent.Type.Leave and self.mw.fullscreen:
			self.mw.show_menubar()
			return True
		# Block other events from reaching the original handler, which would show the toolbars.
		return False
	else:
		# On all other screens (like reviewer), or if the setting is off, use Anki's original logic.
		if _original_MainWebView_eventFilter:
			return _original_MainWebView_eventFilter(self, obj, evt)
		return super(MainWebView, self).eventFilter(obj, evt)


def _update_toolbar_visibility(new_state: str, _old_state: str) -> None:
    """This function is called by a hook every time the screen changes."""
    conf = config.get_config()
    should_hide_setting = conf.get("hideNativeHeaderAndBottomBar", False)
    pro_hide = conf.get("proHide", False)
    max_hide = conf.get("maxHide", False)

    if not should_hide_setting:
        # If the feature is disabled in settings, ensure toolbars are always visible
        mw.toolbar.web.setVisible(True)
        mw.bottomWeb.setVisible(True)
        return

    # Handle reviewer state first with new priority
    if new_state == "review":
        # Always show bottom bar in reviewer, regardless of hide mode
        if max_hide:
            # Max hide: Hide only top toolbar, keep bottom bar visible
            mw.toolbar.web.setVisible(False)
            mw.bottomWeb.setVisible(True)
        elif pro_hide:
            # Pro hide: Hide only top toolbar
            mw.toolbar.web.setVisible(False)
            mw.bottomWeb.setVisible(True)
        else:
            # Base hide mode: Hide top toolbar but keep bottom bar visible
            mw.toolbar.web.setVisible(False)
            mw.bottomWeb.setVisible(True)
        return

    # General hiding logic for other screens
    states_to_hide = ["deckBrowser", "overview"]
    if new_state in states_to_hide:
        # Hide both toolbars on the main menu and deck overview
        mw.toolbar.web.setVisible(False)
        mw.bottomWeb.setVisible(False)
    else:
        # Show toolbars on ALL other screens (this will now exclude the 'review' case when pro_hide is on)
        mw.toolbar.web.setVisible(True)
        mw.bottomWeb.setVisible(True)

def on_reviewer_did_answer_card(reviewer, card, ease):
    """Update the level progress container when a card is answered."""
    try:
        from .gamification import restaurant_level
        
        # Get the latest progress data
        progress = restaurant_level.manager.get_progress()
        if not progress or not getattr(progress, 'enabled', False):
            return
            
        # Get the latest progress data
        xp_into_level = max(0, getattr(progress, 'xp_into_level', 0))
        xp_to_next_level = max(1, getattr(progress, 'xp_to_next_level', 100))
        current_level = getattr(progress, 'level', 0)
        progress_percent = min(100, max(0, (xp_into_level / xp_to_next_level) * 100))
        
        # Update the progress bar and text using f-strings for proper variable interpolation
        js = f"""
        (function() {{
            function updateProgress() {{
                const container = document.querySelector('.level-progress-container');
                if (!container) return false;
                
                // Update progress bar width
                const progressBar = container.querySelector('.level-progress-bar');
                if (progressBar) {{
                    progressBar.style.width = '{progress_percent:.2f}%';
                    progressBar.style.transition = 'width 0.5s ease-out';
                }}
                
                // Update level and XP text
                const levelText = container.querySelector('.level-text');
                if (levelText) {{
                    levelText.textContent = 'Lv. {current_level}';
                }}
                
                const xpText = container.querySelector('.xp-text');
                if (xpText) {{
                    xpText.textContent = '{xp_into_level}/{xp_to_next_level} XP';
                }}
                
                // Add a subtle animation
                container.style.transform = 'scale(1.03)';
                setTimeout(() => {{
                    container.style.transform = 'scale(1.0)';
                }}, 200);
                
                return true;
            }}
            
            // Try to update immediately
            if (!updateProgress()) {{
                // If container not found, wait a bit and try again
                setTimeout(updateProgress, 100);
            }}
        }})();
        """
        
        # Run the JavaScript in the reviewer webview
        from aqt import mw
        if mw and hasattr(mw, 'reviewer') and mw.reviewer and hasattr(mw.reviewer, 'web'):
            mw.reviewer.web.eval(js)
    except Exception as e:
        print(f"Error updating level progress: {e}")
        import traceback
        traceback.print_exc()


def _onigiri_render_deck_node(self, node, ctx) -> str:
    """
    A patched version of DeckBrowser._render_deck_node that creates the
    HTML structure Onigiri's CSS and JS expect (e.g., td.collapse-cell).
    """
    buf = []  # Use a list for efficient string building

    if node.collapsed:
        prefix = "+"
        state_class = "state-closed"
    else:
        prefix = "-"
        state_class = "state-open"

    conf = getattr(ctx, "onigiri_conf", None)
    if conf is None:
        conf = config.get_config()
        setattr(ctx, "onigiri_conf", conf)

    # --- ADD THIS BLOCK ---
    # --- Onigiri Favorites ---
    favorites = mw.col.conf.get("onigiri_favorite_decks", [])
    did_str = str(node.deck_id)
    is_favorite = did_str in favorites
    fav_class = "is-favorite" if is_favorite else ""
    
    fav_star_html = f"""
    <span class="favorite-star-icon {fav_class}"
          onclick="event.stopPropagation(); pycmd('onigiri_toggle_favorite:{node.deck_id}')"
          title="Toggle favorite">
    </span>
    """
    # --- End Onigiri Favorites ---
    # --- END OF BLOCK ---

    hide_all_deck_counts = conf.get("hideAllDeckCounts", False)

    new_count = node.new_count
    learn_count = node.learn_count
    review_count = node.review_count

    # --- Counts HTML ---
    counts_html = ""
    if not hide_all_deck_counts:
        counts_html_parts = []
        # Always display all counts, even if they're 0
        counts_html_parts.append(f'<span class="new-count-bubble{" zero" if new_count == 0 else ""}">{new_count}</span>')
        counts_html_parts.append(f'<span class="learn-count-bubble{" zero" if learn_count == 0 else ""}">{learn_count}</span>')
        counts_html_parts.append(f'<span class="review-count-bubble{" zero" if review_count == 0 else ""}">{review_count}</span>')

        counts_html = '<div class="deck-counts">' + ''.join(counts_html_parts) + '</div>'
    # --- Counts HTML ---

    def indent():
        return "&nbsp;" * 6 * (node.level - 1)

    klass = "deck current" if node.deck_id == ctx.current_deck_id else "deck"
    deck_type_class = "is-folder" if node.children else "is-deck"

    buf.append(f"<tr class='{klass} {deck_type_class}' id='{node.deck_id}' data-did='{node.deck_id}'>")

    if node.children:
        collapse_link = f"<a class='collapse {state_class}' href=# onclick='return pycmd(\"onigiri_collapse:{node.deck_id}\")'>{prefix}</a>"
    else:
        collapse_link = "<span class=collapse></span>"

    deck_prefix = f"<span class='deck-prefix'>{indent()}{collapse_link}</span>"
    extraclass = "filtered" if node.filtered else ""

    # --- START MODIFICATION: Update colspan and add counts_html ---
    buf.append(f"""
    <td class=decktd colspan=7>
        {fav_star_html}
        <div class="deck-info">
            {deck_prefix}
            <a class="deck {extraclass}" href=# onclick="return pycmd('open:{node.deck_id}')">
                {node.name}
            </a>
        </div>
        {counts_html}
    </td>
    """)
    # --- END MODIFICATION ---

    # --- START MODIFICATION: Remove old count columns ---
    # The old count tds are removed from here.
    # --- END MODIFICATION ---

    buf.append(f"""
    <td align=center class=opts>
      <a onclick='return pycmd("opts:{node.deck_id}");'>
        <img src='/_anki/imgs/gears.svg' class=gears>
      </a>
    </td>
    </tr>""")

    if not node.collapsed:
        for child in node.children:
            buf.append(self._render_deck_node(child, ctx))

    return "".join(buf) # Join the list into a single string at the end
    
def _on_sync_did_finish():
    """Removes the syncing animation from the sync button."""
    try:
        if mw.state == "deckBrowser" and hasattr(mw.deckBrowser, 'web') and mw.deckBrowser.web:
            mw.deckBrowser.web.eval("SyncStatusManager.setSyncing(false);")
        elif mw.state == "overview" and hasattr(mw.overview, 'web') and mw.overview.web:
             mw.overview.web.eval("SyncStatusManager.setSyncing(false);")
        elif mw.state == "review" and hasattr(mw.reviewer, 'web') and mw.reviewer.web:
             mw.reviewer.web.eval("SyncStatusManager.setSyncing(false);")
    except Exception as e:
        print(f"Onigiri: Error stopping sync animation: {e}")

def apply_patches():
    """Apply all patches to Anki's UI."""
    # Register the reviewer_did_answer_card hook
    from aqt import gui_hooks
    gui_hooks.sync_did_finish.append(_on_sync_did_finish)
    gui_hooks.reviewer_did_answer_card.append(on_reviewer_did_answer_card)
    
    # Patch the deck browser's render method
    from aqt.deckbrowser import DeckBrowser
    DeckBrowser._render_deck_node = _onigiri_render_deck_node
    
    # Patch the overview page
    patch_overview()
    
    # Patch the congrats page
    # REMOVED: Called explicitly in __init__.py at top-level to ensure correct hook order
    # patch_congrats_page()
    
    # Patch the webview to handle our custom messages
    # REMOVED: This hook is already registered in __init__.py line 292
    # Keeping this line would cause double registration and duplicate dialogs
    # gui_hooks.webview_did_receive_js_message.append(on_webview_js_message)
    
    # Add hook for toolbar visibility changes
    gui_hooks.state_did_change.append(_update_toolbar_visibility)
    
    # Mark the hook as registered and update toolbar state
    mw._onigiri_restaurant_hook_registered = True
    mw.progress.single_shot(0, lambda: _update_toolbar_visibility(mw.state, "startup"))

def generate_reviewer_buttons_css(conf):
    """
    Generates CSS for the reviewer answer buttons based on user configuration.
    """
    css = []
    
    # Zen Mode: Hide the bottom bar (#outer) completely
    max_hide = conf.get("maxHide", False)
    if max_hide:
        css.append("""
        #outer {
            display: none !important;
        }
        """)
        # Return early since the bottom bar is hidden, no need for button styling
        return "<style>" + "\\n".join(css) + "</style>"
    
    # Global Settings
    border_color_light = conf.get("onigiri_reviewer_btn_border_color_light", "#DBDBDB")
    border_color_dark = conf.get("onigiri_reviewer_btn_border_color_dark", "#444444")
    
    # New Settings
    custom_enabled = conf.get("onigiri_reviewer_btn_custom_enabled", True)
    radius = conf.get("onigiri_reviewer_btn_radius", 12)
    padding = conf.get("onigiri_reviewer_btn_padding", 5)
    btn_height = conf.get("onigiri_reviewer_btn_height", 40)
    bar_height = conf.get("onigiri_reviewer_bar_height", 60)
    
    interval_color_light = conf.get("onigiri_reviewer_stattxt_color_light", "#666666")
    interval_color_dark = conf.get("onigiri_reviewer_stattxt_color_dark", "#aaaaaa")

    if custom_enabled:
        # Base button style (Applied to all buttons: Show Answer, Edit, More, and Answer Buttons)
        css.append(f"""
        /* Bottom Bar Height */
        #outer {{
             height: {bar_height}px !important;
             display: flex !important;
             align-items: center !important;
        }}
        
        /* Modernize ALL buttons in the bottom bar */
        button {{
            border: 2px solid transparent !important; /* Force transparent border */
            border-radius: {radius}px !important; /* Customizable radius */
            box-shadow: none !important; /* No shadow */
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important; /* Smooth transition */
            box-sizing: border-box !important;
            cursor: pointer !important;
            padding: {padding}px 15px !important; /* Customizable padding (size) */
            margin: 0 5px !important; /* Spacing between buttons */
            height: {btn_height}px !important; /* Customizable height */
            min-height: {btn_height}px !important;
        }}
        
        /* Hover effects for ease buttons only */
        button[onclick*="ease"]:hover {{
            transform: translateY(-2px);
            box-shadow: none !important;
        }}
        
        /* Other Buttons (Show Answer, Edit, More, etc.) - Explicit Colors with hover effects */
        #outer button:not([onclick*="ease"]):not([data-cmd*="ease"]) {{
            background: {conf.get("onigiri_reviewer_other_btn_bg_light", "#f0f0f0")} !important;
            background-color: {conf.get("onigiri_reviewer_other_btn_bg_light", "#f0f0f0")} !important;
            background-image: none !important;
            color: {conf.get("onigiri_reviewer_other_btn_text_light", "#2c2c2c")} !important;
        }}
        
        #outer button:not([onclick*="ease"]):not([data-cmd*="ease"]):hover {{
            background: {conf.get("onigiri_reviewer_other_btn_hover_bg_light", "#2c2c2c")} !important;
            background-color: {conf.get("onigiri_reviewer_other_btn_hover_bg_light", "#2c2c2c")} !important;
            background-image: none !important;
            color: {conf.get("onigiri_reviewer_other_btn_hover_text_light", "#f0f0f0")} !important;
            transform: translateY(-2px) !important;
            box-shadow: none !important;
        }}
        
        .nightMode #outer button:not([onclick*="ease"]):not([data-cmd*="ease"]) {{
            background: {conf.get("onigiri_reviewer_other_btn_bg_dark", "#3a3a3a")} !important;
            background-color: {conf.get("onigiri_reviewer_other_btn_bg_dark", "#3a3a3a")} !important;
            background-image: none !important;
            color: {conf.get("onigiri_reviewer_other_btn_text_dark", "#e0e0e0")} !important;
        }}
        
        .nightMode #outer button:not([onclick*="ease"]):not([data-cmd*="ease"]):hover {{
            background: {conf.get("onigiri_reviewer_other_btn_hover_bg_dark", "#e0e0e0")} !important;
            background-color: {conf.get("onigiri_reviewer_other_btn_hover_bg_dark", "#e0e0e0")} !important;
            background-image: none !important;
            color: {conf.get("onigiri_reviewer_other_btn_hover_text_dark", "#3a3a3a")} !important;
            transform: translateY(-2px) !important;
            box-shadow: none !important;
        }}
        
        button:active {{
            transform: translateY(0);
            box-shadow: none !important;
        }}
        
        .nightMode button {{
            box-shadow: none !important;
        }}
        
        .nightMode button:hover {{
            box-shadow: none !important;
        }}

        /* Specific Answer Buttons Colors */
        button[onclick*="ease"], button[data-cmd="ease"] {{
            overflow: visible !important; /* Ensure content isn't clipped */
            display: inline-flex !important; /* Align content nicely */
            flex-direction: column !important; /* Stack text and interval if needed */
            justify-content: center !important;
            align-items: center !important;
        }}

        /* Fix missing interval numbers */
        button[onclick*="ease"] table, button[onclick*="ease"] tr, button[onclick*="ease"] td,
        button[data-cmd="ease"] table, button[data-cmd="ease"] tr, button[data-cmd="ease"] td {{
            background: transparent !important;
            border: none !important;
            margin: 0 !important;
            padding: 0 !important;
            color: inherit !important;
        }}
        
        
        /* Stat Text (.stattxt and .nobold) - intervals and + signs */
        .stattxt, .nobold {{
            color: {interval_color_light} !important;
            opacity: 0.9 !important;
            font-weight: normal !important;
            display: inline-block !important;
            font-size: 0.9em !important;
        }}
        
        .nightMode .stattxt, .nightMode .nobold {{
             color: {interval_color_dark} !important;
        }}
        """)
    
        # Per-button settings
        buttons = {
            "1": "again",
            "2": "hard",
            "3": "good",
            "4": "easy"
        }
        
        defaults = {
            "again": ("#ffb3b3", "#4d0000", "#ffcccb", "#4a0000"),
            "hard": ("#ffe0b3", "#4d2600", "#ffd699", "#4d1d00"),
            "good": ("#b3ffb3", "#004d00", "#90ee90", "#004000"),
            "easy": ("#b3d9ff", "#00264d", "#add8e6", "#002952")
        }
        
        for ease, key in buttons.items():
            def_bg_l, def_txt_l, def_bg_d, def_txt_d = defaults[key]
            
            bg_light = conf.get(f"onigiri_reviewer_btn_{key}_bg_light", def_bg_l)
            text_light = conf.get(f"onigiri_reviewer_btn_{key}_text_light", def_txt_l)
            bg_dark = conf.get(f"onigiri_reviewer_btn_{key}_bg_dark", def_bg_d)
            text_dark = conf.get(f"onigiri_reviewer_btn_{key}_text_dark", def_txt_d)
            
            css.append(f"""
            #outer button[data-onigiri-ease="{ease}"],
            #outer button[onclick*="ease{ease}"], 
            #outer button[data-cmd="ease{ease}"], 
            #outer #ease{ease} {{
                background: {bg_light} !important;
                background-color: {bg_light} !important;
                background-image: none !important;
                color: {text_light} !important;
            }}
            #outer button[data-onigiri-ease="{ease}"]:hover,
            #outer button[onclick*="ease{ease}"]:hover, 
            #outer button[data-cmd="ease{ease}"]:hover, 
            #outer #ease{ease}:hover {{
                background: {text_light} !important;
                background-color: {text_light} !important;
                background-image: none !important;
                color: {bg_light} !important;
                cursor: pointer !important;
            }}

            .nightMode #outer button[data-onigiri-ease="{ease}"],
            .nightMode #outer button[onclick*="ease{ease}"], 
            .nightMode #outer button[data-cmd="ease{ease}"], 
            .nightMode #outer #ease{ease} {{
                background: {bg_dark} !important;
                background-color: {bg_dark} !important;
                background-image: none !important;
                color: {text_dark} !important;
            }}
            .nightMode #outer button[data-onigiri-ease="{ease}"]:hover,
            .nightMode #outer button[onclick*="ease{ease}"]:hover, 
            .nightMode #outer button[data-cmd="ease{ease}"]:hover, 
            .nightMode #outer #ease{ease}:hover {{
                background: {text_dark} !important;
                background-color: {text_dark} !important;
                background-image: none !important;
                color: {bg_dark} !important;
            }}
            """)

        # JS Injection for robust button detection
        css.append("""
        <script>
        (function() {
            function classifyButtons() {
                const buttons = document.querySelectorAll('#outer button, button');
                buttons.forEach(btn => {
                    // Check if already processed
                    if (btn.hasAttribute('data-onigiri-ease')) return;

                    const onclick = btn.getAttribute('onclick') || '';
                    const cmd = btn.getAttribute('data-cmd') || '';
                    const id = btn.id || '';
                    const text = btn.innerText.toLowerCase();

                    let ease = null;
                    
                    // Heuristic 1: Standard IDs or Attributes
                    if (onclick.includes('ease1') || cmd === 'ease1' || id === 'ease1') ease = "1";
                    else if (onclick.includes('ease2') || cmd === 'ease2' || id === 'ease2') ease = "2";
                    else if (onclick.includes('ease3') || cmd === 'ease3' || id === 'ease3') ease = "3";
                    else if (onclick.includes('ease4') || cmd === 'ease4' || id === 'ease4') ease = "4";

                    // Heuristic 2: Text Content (Fallback)
                    if (!ease) {
                        if (text.includes('again')) ease = "1";
                        else if (text.includes('hard')) ease = "2";
                        else if (text.includes('good')) ease = "3";
                        else if (text.includes('easy')) ease = "4";
                    }

                    if (ease) {
                        btn.setAttribute('data-onigiri-ease', ease);
                    } else {
                        btn.classList.add('onigiri-other-btn');
                    }
                });
            }

            // Run repeatedly to catch dynamic updates
            setInterval(classifyButtons, 100);
            
            // Also run on mutation
            const observer = new MutationObserver(classifyButtons);
            observer.observe(document.body, { childList: true, subtree: true });
        })();
        </script>
        """)
        
    return "<style>" + "\\n".join(css) + "</style>"