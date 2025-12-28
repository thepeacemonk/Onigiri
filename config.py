import copy
from aqt import mw

# Default settings for the add-on
DEFAULTS = {
    "userName": "USER",
    "statsTitle": "Today's Stats",
    "studyNowText": "Study Now",
    "hideWelcomeMessage": False,
    "hideAllDeckCounts": False,
    "hideDeckCounts": True,
    "hideNativeHeaderAndBottomBar": True,
    "proHide": False,
    "maxHide": False,
    "flowMode": False,
    "gamificationMode": False, 
    "sidebarCollapsed": False,
    "showCongratsProfileBar": True,
    "congratsMessage": "Congratulations! You have finished this deck for now.",
    "showWelcomePopup": True,
    "hideRetentionStars": False,
    "showHeatmapOnProfile": True,
    "achievements": {
        "enabled": False,
        "earned": {},
        "history": [],
        "last_refresh": None,
        "snapshot": {},
        "custom_goals": {
            "last_modified_at": None,
            "daily": {
                "enabled": False,
                "target": 100,
                "last_notified_day": None,
                "completion_count": 0,
            },
            "weekly": {
                "enabled": False,
                "target": 700,
                "last_notified_week": None,
                "completion_count": 0,
            },
        },
        # --- ADDED: focusDango nested inside achievements ---
        "focusDango": {
            "enabled": False,
            "message": "Focus Dango wants you to focus!"
        },
        # --- END ADDITION ---
    },
    "restaurant_level": {
        "enabled": False,
        "name": "Restaurant Level",
        "total_xp": 0,
        "level": 0,
        "notifications_enabled": True,
        "show_profile_bar_progress": True,
        "show_profile_page_progress": True,
        "show_reviewer_header": True,
    },
    "daily_special": {
        "enabled": True,
        "current_progress": 0,
        "target": 100,  # Default target of 100 reviews for the daily special
        "last_updated": None,
        "last_notified_milestone": 0
    },
    "mochi_messages": {
        "enabled": False,
        "cards_interval": 15,
        "messages": [
            "Mochi is rooting for you — keep going!",
            "Great pace! Mochi loves your dedication.",
            "Deep breath. Mochi knows you've got this!",
            "Mochi is cheering for you! Keep it up!", 
            "Wow, look at you go! A true review master.",
            "Mochi is so proud of you! Keep it going!",
            "Each review is a step closer to your goal. You've got this!",
        ],
    },
    "heatmapShape": "square.svg",
    "heatmapShowStreak": True,
    "heatmapShowMonths": True,
    "heatmapShowWeekdays": True,
    "heatmapShowWeekHeader": True,
    "heatmapDefaultView": "year",
    "onigiriWidgetLayout": {
    "grid": {
        "studied": {"pos": 0, "row": 1, "col": 1},
        "time": {"pos": 1, "row": 1, "col": 1},
        "pace": {"pos": 2, "row": 1, "col": 1},
        "retention": {"pos": 3, "row": 1, "col": 1},
        "heatmap": {"pos": 4, "row": 2, "col": 4}
        },
    "archive": ["favorites"] 
    },
    "externalWidgetLayout": {}, 

    # --- ADDED: Sidebar Button Layout ---
    "sidebarButtonLayout": {
        "visible": [
            "profile",
            "add",
            "browse",
            "stats",
            "sync",
            "settings",
            "more"
        ],
        "archived": []
    },


    # --- NEW: Reviewer Background Settings ---
    "onigiri_reviewer_bg_mode": "main", # "main", "color", "image_color"
    "onigiri_reviewer_bg_main_blur": 0, # Blur when using main background
    "onigiri_reviewer_bg_main_opacity": 100, # Opacity when using main background
    "onigiri_reviewer_bg_light_color": "#f2f2f2",
    "onigiri_reviewer_bg_dark_color": "#2C2C2C",
    "onigiri_reviewer_bg_image_light": "",
    "onigiri_reviewer_bg_image_dark": "",
    "onigiri_reviewer_bg_image_mode": "single", # "single" or "separate"
    "onigiri_reviewer_bg_blur": 0,
    "onigiri_reviewer_bg_opacity": 100,
    # --- Reviewer Notification Position ---
    "onigiri_reviewer_notification_position": "top-right", # top-left, top-center, top-right, bottom-left, bottom-center, bottom-right
    # --- Reviewer Bottom Bar Settings ---
    "onigiri_reviewer_bottom_bar_bg_mode": "match_reviewer_bg", # "main", "color", "image", "image_color", "match_reviewer_bg"
    "onigiri_reviewer_bottom_bar_bg_light_color": "#f2f2f2",
    "onigiri_reviewer_bottom_bar_bg_dark_color": "#2C2C2C",
    "onigiri_reviewer_bottom_bar_bg_image": "",
    "onigiri_reviewer_bottom_bar_bg_blur": 0,
    "onigiri_reviewer_bottom_bar_bg_opacity": 100,
    "onigiri_reviewer_bottom_bar_match_main_blur": 0,
    "onigiri_reviewer_bottom_bar_match_main_opacity": 100,
    "onigiri_reviewer_bottom_bar_match_reviewer_bg_blur": 0,
    "onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity": 100,
    "restaurant_countdown_hour": 4,  # Default to 4 AM
    "restaurant_countdown_minute": 0,  # Default to 0 minutes
    
    # --- NEW: Overviewer Background Settings ---
    "onigiri_overview_bg_mode": "main", # "main", "color", "image_color"
    "onigiri_overview_bg_main_blur": 0,
    "onigiri_overview_bg_main_opacity": 100,
    "onigiri_overview_bg_light_color": "#f2f2f2",
    # The following lines appear to be UI setup code and cannot be directly inserted into a dictionary.
    # Assuming the intent was to add a default for 'onigiri_reviewer_btn_custom_enabled' if not already present.
    # The other lines are likely from a different context (e.g., a settings dialog setup).
    # "enable_label = QLabel("Enable Custom Buttons:")"
    # "self.reviewer_btn_custom_enable_toggle = AnimatedToggleButton()"
    # "self.reviewer_btn_custom_enable_toggle.setChecked(self.current_config.get("onigiri_reviewer_btn_custom_enabled", False))"
    # "enable_layout.addWidget(enable_label)"
    # "enable_layout.addWidget(self.reviewer_btn_custom_enable_toggle)ight": 60, # px (default height)
    "onigiri_reviewer_btn_border_size": 0,
    "onigiri_reviewer_btn_custom_enabled": True, # Global toggle (Default OFF)
    "onigiri_reviewer_btn_radius": 12, # px
    "onigiri_reviewer_btn_padding": 5, # px (affects size)
    "onigiri_reviewer_btn_height": 40, # px (button height)
    "onigiri_reviewer_bar_height": 60, # px (default height)
    "onigiri_reviewer_btn_interval_color_light": "#555555",
    "onigiri_reviewer_btn_interval_color_dark": "#dddddd",
    "onigiri_reviewer_btn_border_color_light": "#DBDBDB",
    "onigiri_reviewer_btn_border_color_dark": "#444444",
    "onigiri_reviewer_btn_again_bg_light": "#ffb3b3",
    "onigiri_reviewer_btn_again_text_light": "#4d0000",
    "onigiri_reviewer_btn_again_bg_dark": "#ffcccb",
    "onigiri_reviewer_btn_again_text_dark": "#4a0000",
    "onigiri_reviewer_btn_hard_bg_light": "#ffe0b3",
    "onigiri_reviewer_btn_hard_text_light": "#4d2600",
    "onigiri_reviewer_btn_hard_bg_dark": "#ffd699",
    "onigiri_reviewer_btn_hard_text_dark": "#4d1d00",
    "onigiri_reviewer_btn_good_bg_light": "#b3ffb3",
    "onigiri_reviewer_btn_good_text_light": "#004d00",
    "onigiri_reviewer_btn_good_bg_dark": "#90ee90",
    "onigiri_reviewer_btn_good_text_dark": "#004000",
    "onigiri_reviewer_btn_easy_bg_light": "#b3d9ff",
    "onigiri_reviewer_btn_easy_text_light": "#00264d",
    "onigiri_reviewer_btn_easy_bg_dark": "#add8e6",
    "onigiri_reviewer_btn_easy_text_dark": "#002952",
    
    # --- Other Bottom Bar Buttons (Show Answer, Edit, More, etc.) ---
    "onigiri_reviewer_other_btn_bg_light": "#ffffff",
    "onigiri_reviewer_other_btn_text_light": "#2c2c2c",
    "onigiri_reviewer_other_btn_bg_dark": "#3a3a3a",
    "onigiri_reviewer_other_btn_text_dark": "#e0e0e0",
    "onigiri_reviewer_other_btn_hover_bg_light": "#2c2c2c",
    "onigiri_reviewer_other_btn_hover_text_light": "#f0f0f0",
    "onigiri_reviewer_other_btn_hover_bg_dark": "#e0e0e0",
    "onigiri_reviewer_other_btn_hover_text_dark": "#3a3a3a",
    
    # --- Stat Text (.stattxt) Colors (intervals like "10m", "4d" and "+" signs) ---
    "onigiri_reviewer_stattxt_color_light": "#666666",
    "onigiri_reviewer_stattxt_color_dark": "#aaaaaa",

    "onigiri_overview_bg_dark_color": "#2C2C2C",
    "onigiri_overview_bg_image_light": "",
    "onigiri_overview_bg_image_dark": "",
    "onigiri_overview_bg_image": "",
    "onigiri_overview_bg_image_mode": "single",
    "onigiri_overview_bg_blur": 0,
    "onigiri_overview_bg_opacity": 100,
    "onigiri_overview_bg_color_theme_mode": "single",
    "onigiri_overview_bg_image_theme_mode": "single",
    # -----------------------------------------
    # --- REMOVED: Top-level focusDango was here ---
    "colors": {
        "light": {
            "--accent-color": "#007aff",
            "--bg": "#f3f3f3",
            "--fg": "#212121",
            "--icon-color": "#333333",
            "--icon-color-filtered": "#007AFF",
            "--fg-subtle": "#757575",
            "--border": "#e0e0e0",
            "--highlight-bg": "#eeeeee",
            "--canvas-inset": "#ffffff",
            "--button-primary-bg": "#007aff",
            "--button-primary-gradient-start": "#0088ff",
            "--button-primary-gradient-end": "#0065c7",
            "--new-count-bubble-bg": "#a3c5e8",
            "--new-count-bubble-fg": "#13375b",
            "--learn-count-bubble-bg": "#e8a3a3",
            "--learn-count-bubble-fg": "#731717",
            "--review-count-bubble-bg": "#a3e8b8",
            "--review-count-bubble-fg": "#1b7a38",
            "--heatmap-color": "#007aff",
            "--heatmap-color-zero": "#f0f0f0",
            "--star-color": "#FFD700",
            "--empty-star-color": "#e0e0e0",
            "--stats-fg": "#212121",
            # Shadow and overlay colors
            "--shadow-sm": "rgba(0, 0, 0, 0.1)",
            "--shadow-md": "rgba(0, 0, 0, 0.1)",
            "--shadow-lg": "rgba(0, 0, 0, 0.1)",
            "--overlay-dark": "rgba(0, 0, 0, 0.4)",
            "--overlay-light": "rgba(0, 0, 0, 0.4)",
            # Profile page specific colors
            "--profile-page-bg": "#d9d9d9",
            "--profile-card-bg": "#FFFFFF",
            "--profile-pill-placeholder-bg": "rgba(0, 0, 0, 0.2)",
            "--profile-export-btn-bg": "rgba(255, 255, 255, 1)",
            "--profile-export-btn-fg": "#374151",
            "--profile-export-btn-border": "rgba(0, 0, 0, 0.1)",
            "--overlay-close-btn-bg": "#e0e0e0",
            "--overlay-close-btn-fg": "#333333",
            # Deck list specific colors
            "--deck-hover-bg": "rgba(128, 128, 128, 0.1)",
            "--deck-dragging-bg": "#cde4f9",
            "--deck-edit-mode-bg": "rgba(128, 128, 128, 0.05)",
            # Text shadow colors
            "--text-shadow-light": "rgba(0, 0, 0, 0.5)",
            "--profile-pic-border": "rgba(255, 255, 255, 0.8)",
        },
        "dark": {
            "--accent-color": "#0a84ff",
            "--bg": "#2c2c2c",
            "--fg": "#e0e0e0",
            "--icon-color": "#E0E0E0",
            "--icon-color-filtered": "#0A84FF", 
            "--fg-subtle": "#9e9e9e",
            "--border": "#424242",
            "--highlight-bg": "#3c3c3c",
            "--canvas-inset": "#2c2c2c",
            "--button-primary-bg": "#0a84ff",
            "--button-primary-gradient-start": "#0a94ff",
            "--button-primary-gradient-end": "#0a74d9",
            "--new-count-bubble-bg": "#68a0d9",
            "--new-count-bubble-fg": "#13375b",
            "--learn-count-bubble-bg": "#d96868",
            "--learn-count-bubble-fg": "#731717",
            "--review-count-bubble-bg": "#68d98a",
            "--review-count-bubble-fg": "#1b7a38",
            "--heatmap-color": "#0a84ff",
            "--heatmap-color-zero": "#3a3a3a",
            "--star-color": "#FFD700",
            "--empty-star-color": "#4a4a4a",
            "--stats-fg": "#e0e0e0",
            # Shadow and overlay colors
            "--shadow-sm": "rgba(0, 0, 0, 0.1)",
            "--shadow-md": "rgba(0, 0, 0, 0.15)",
            "--shadow-lg": "rgba(0, 0, 0, 0.4)",
            "--overlay-dark": "rgba(0, 0, 0, 0.7)",
            "--overlay-light": "rgba(0, 0, 0, 0.4)",
            # Profile page specific colors
            "--profile-page-bg": "#1f1f1f",
            "--profile-card-bg": "#1e1e1e",
            "--profile-pill-placeholder-bg": "rgba(0, 0, 0, 0.2)",
            "--profile-export-btn-bg": "rgba(255, 255, 255, 1)",
            "--profile-export-btn-fg": "#374151",
            "--profile-export-btn-border": "rgba(0, 0, 0, 0.1)",
            "--overlay-close-btn-bg": "#e0e0e0",
            "--overlay-close-btn-fg": "#333333",
            # Deck list specific colors
            "--deck-hover-bg": "rgba(128, 128, 128, 0.1)",
            "--deck-dragging-bg": "#2c3e50",
            "--deck-edit-mode-bg": "rgba(128, 128, 128, 0.05)",
            # Text shadow colors
            "--text-shadow-light": "rgba(0, 0, 0, 0.5)",
            "--profile-pic-border": "rgba(255, 255, 255, 0.8)",
        }
    }
}


# A unique ID for our add-on's configuration
config_id = None
def get_config_id():
    global config_id
    if config_id is None:
        config_id = mw.addonManager.addonFromModule(__name__)
    return config_id


def get_config():
    """
    Loads the add-on's configuration from Anki's settings,
    providing defaults for any missing values and cleaning out obsolete keys.
    """
    # mw.col might not be available during early startup.
    if not mw.col:
        return copy.deepcopy(DEFAULTS)

    user_config = mw.addonManager.getConfig(get_config_id())
    # Start with a clean copy of the defaults
    clean_config = copy.deepcopy(DEFAULTS)

    if not user_config:
        return clean_config

    # Iterate through the default keys to safely populate from the user's config
    for key, default_value in DEFAULTS.items():
        if key in user_config:
            # Handle the nested 'colors' dictionary specifically
            if key == "colors" and isinstance(default_value, dict):
                for mode, default_mode_colors in default_value.items():
                    if mode in user_config.get(key, {}) and isinstance(user_config[key][mode], dict):
                        for sub_key, _ in default_mode_colors.items():
                            if sub_key in user_config[key][mode]:
                                clean_config[key][mode][sub_key] = user_config[key][mode][sub_key]
            # Handle other top-level keys
            else:
                clean_config[key] = user_config[key]
    
    # Compatibility migrations
    custom_goals_conf = clean_config.get("achievements", {}).get("custom_goals", {})
    if "last_modified_at" not in custom_goals_conf:
        custom_goals_conf["last_modified_at"] = None
        if "achievements" in clean_config:
            clean_config["achievements"].setdefault("custom_goals", custom_goals_conf)

    if "gamification" in user_config and "achievements" not in user_config:
        clean_config["achievements"] = copy.deepcopy(user_config["gamification"])

    # Compatibility: Check for old profile page visibility settings and migrate them
    # This ensures users updating the addon don't lose their settings
    # OPTIMIZATION: Check if key exists in user_config FIRST to avoid backend call
    if "showHeatmapOnProfile" not in user_config:
         if "onigiri_profile_show_stats" in mw.col.conf:
            clean_config["showHeatmapOnProfile"] = mw.col.conf.get("onigiri_profile_show_stats", True)
        
    # Compatibility: Migrate restaurant_level and daily_special from achievements to top-level
    if "achievements" in clean_config:
        achievements_conf = clean_config["achievements"]
        
        # Migrate restaurant_level
        if "restaurant_level" in achievements_conf:
            # Only migrate if top-level doesn't exist or we want to preserve old data
            # Since clean_config has defaults, we should overwrite with old data if it exists
            clean_config["restaurant_level"] = achievements_conf["restaurant_level"]
            del achievements_conf["restaurant_level"]
            
        # Migrate daily_special
        if "daily_special" in achievements_conf:
            clean_config["daily_special"] = achievements_conf["daily_special"]
            del achievements_conf["daily_special"]

    # FORCE CLEANUP: Remove taiyaki_coins from config if present
    # It is now stored exclusively in gamification.json
    if "restaurant_level" in clean_config:
        if "taiyaki_coins" in clean_config["restaurant_level"]:
            del clean_config["restaurant_level"]["taiyaki_coins"]

    return clean_config


def write_config(config):
    """
    Saves the provided configuration dictionary to Anki's settings.
    """
    mw.addonManager.writeConfig(get_config_id(), config)