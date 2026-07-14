import copy
import json
import os
from aqt import mw


def effective_night_mode(conf=None):
    """
    Return the active dark/light mode for Onigiri previews and rendered UI.

    The add-on can force a theme via ``onigiriThemeMode``; when it is set to
    ``system`` we follow Anki's current night-mode state.
    """
    mode = "system"
    if isinstance(conf, dict):
        mode = str(conf.get("onigiriThemeMode", "system")).lower()

    if mode in {"dark", "night", "night_mode"}:
        return True
    if mode in {"light", "day", "day_mode"}:
        return False

    try:
        from aqt.theme import theme_manager

        return bool(theme_manager.night_mode)
    except Exception:
        pass

    try:
        return bool(mw and mw.pm and mw.pm.night_mode())
    except Exception:
        return False

# Default settings for the add-on
DEFAULTS = {
    # ... (content remains same, will be merged by tool if unreferenced, but I should be careful not to delete DEFAULTS content if I can help it. 
    # Actually wait, replace_file_content replaces the WHOLE chunk. I need to keep DEFAULTS intact. 
    # I will target the imports and the functions at the end, leaving DEFAULTS in the middle untouched if possible.
    # Ah, I cannot "leave in the middle untouched" easily with one chunk if I want to wrap everything.
    # I will use multiple chunks.)
}

# ... (I will use multi_replace to target specific areas)

DEFAULTS = {
    "userName": "USER",
    "statsTitle": "Welcome to Onigiri!",
    "studyNowText": "Study Now",
    "hideWelcomeMessage": False,
    "hideAllDeckCounts": False,
    "hideDeckCounts": True,
    "hideNativeHeaderAndBottomBar": True,
    "proHide": False,
    "maxHide": False,
    "flowMode": False,
    "gamificationMode": False,
    "ankiweb_sync_enabled": False,
    "fullHideMode": False, 
    "hideSynapseProSidebar": False,
    "sidebarCollapsed": False,
    "sidebarPosition": "left",
    "showCongratsProfileBar": True,
    "showOverviewProfileBar": True,
    "congratsMessage": "Congratulations! You have finished this deck for now.",
    "showWelcomePopup": True,
    "onigiriThemeMode": "system",
    "prep_station": {
        "plans": [],
    },
    "hashi_notes": {
        "retention_default": 30,
        "custom_css": "",
        "default_sort": "age",
        "trash_grace_days": 7,
        "show_in_reviewer_header": True,
    },
    "onigiri_pomodoro_show_in_reviewer_header": True,
    "userBirthday": "",  # Format: YYYY-MM-DD, empty = not set
    "lastBirthdayShown": "",  # Year when birthday popup was last shown 
    "hideRetentionStars": False,
    "showHeatmapOnProfile": True,
    "onigiriProfile": {
        "bio": "",
        "status": "",
        "musicLink": "",
        "spotifyLink": ""
    },
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
            "message": "Focus Dango wants you to focus!",
            "messages": ["Focus Dango wants you to focus!"],
            "self_sabotage": False,
            "unlock_pin": "000000",
        },
        # --- END ADDITION ---
    },
    "restaurant_level": {
        "enabled": False,
        "name": "Nook Level",
        "total_xp": 0,
        "level": 0,
        "difficulty": "Apprendice",
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
    "onigimon": {
        "enabled": False,
        "difficulty": "pikachu",
        "reward_interval": 4,
        "reward_generosity": "normal",
        "sprite_source": "ankimon_then_pokesprite",
        "sprite_motion": "static",
        "scene_background_color": "#7FD179",
        "scene_background_image": "",
        "scene_background_blur": 9,
        "scene_background_opacity": 90,
        "allow_ankimon_updates": True,
    },
    "hexagon_land": {
        "enabled": False,
        "theme": "island",
        "sounds_enabled": True,
    },
    "heatmapShape": "square.svg",
    "heatmapStreakIcon": "system:fire.svg",
    "heatmapStreakIconColor": "#ff6b35",
    "heatmapStreakIconZeroColor": "#8f8f8f",
    "heatmapShowStreak": True,
    "heatmapShowMonths": True,
    "heatmapShowWeekdays": True,
    "heatmapShowWeekHeader": True,
    "heatmapDefaultView": "year",
    "heatmapWeekStart": "monday",
    "markerColors": {
        "red": "#FF4B4B",
        "blue": "#4488FF",
        "green": "#44BB66",
        "yellow": "#FFB800",
    },
    "onigiriWidgetLayout": {
    "grid": {
        "studied": {"pos": 0, "row": 1, "col": 1},
        "time": {"pos": 1, "row": 1, "col": 1},
        "pace": {"pos": 2, "row": 1, "col": 1},
        "retention": {"pos": 3, "row": 1, "col": 1},
        "heatmap": {"pos": 4, "row": 2, "col": 4}
        },
    "archive": ["favorites", "onigimon", "hexagon_land", "deck_stats", "prep_station"],
    "grid_width": 230,
    "grid_alignment": "center",
    "widget_height": 120,
    },
    "externalWidgetLayout": {}, 
    "onigiriDecklineAutoEmbed": True,

    # --- NEW: Sidebar Action Buttons Mode ---
    # "list" (default), "collapsed" (toolbar icons), "archived" (hidden)
    "sidebarActionsMode": "list",

    # --- ADDED: Sidebar Button Layout ---
    "sidebarButtonLayout": {
        "visible": [
            "profile",
            "add",
            "browse",
            "stats",
            "sync",
            "settings",
            "gamification",
            "more"
        ],
        "archived": []
    },


    # --- NEW: Reviewer Background Settings ---
    "onigiri_reviewer_bg_mode": "main", # "main", "color", "image_color"
    # --- Fonts ---
    "onigiri_font_main": "system",
    "onigiri_font_subtle": "system",
    "onigiri_font_small_title": "system",
    "onigiri_font_size_main": 14,
    "onigiri_font_size_subtle": 20,
    "onigiri_font_size_small_title": 15,
    # -------------
    "onigiri_reviewer_bg_main_blur": 0, # Blur when using main background
    "onigiri_reviewer_bg_main_opacity": 100, # Opacity when using main background
    "onigiri_reviewer_bg_light_color": "#f2f2f2",
    "onigiri_reviewer_bg_dark_color": "#2C2C2C",
    "onigiri_reviewer_bg_image": "",
    "onigiri_reviewer_bg_image_light": "",
    "onigiri_reviewer_bg_image_dark": "",
    "onigiri_reviewer_bg_image_mode": "single", # "single" or "separate"
    "onigiri_reviewer_bg_color_theme_mode": "separate",
    "onigiri_reviewer_bg_image_theme_mode": "separate",
    "onigiri_reviewer_bg_blur": 0,
    "onigiri_reviewer_bg_opacity": 100,
    "onigiri_reviewer_slideshow_images": [],
    "onigiri_reviewer_slideshow_interval": 10,
    # --- Reviewer Notification Position ---
    "onigiri_reviewer_notification_position": "top-center", # top-left, top-center, top-right, bottom-left, bottom-center, bottom-right
    "onigiri_reviewer_silent_notifications": False,
    "onigiri_notification_duration_ms": 5200,
    # --- Reviewer Bottom Bar Settings ---
    "onigiri_reviewer_bottom_bar_bg_mode": "match_reviewer_bg", # "main", "color", "image", "image_color", "match_overview_bg", "match_reviewer_bg"
    "onigiri_reviewer_bottom_bar_bg_light_color": "#f2f2f2",
    "onigiri_reviewer_bottom_bar_bg_dark_color": "#2C2C2C",
    "onigiri_reviewer_bottom_bar_bg_image": "",
    "onigiri_reviewer_bottom_bar_bg_blur": 0,
    "onigiri_reviewer_bottom_bar_bg_opacity": 100,
    "onigiri_reviewer_bottom_bar_match_main_blur": 0,
    "onigiri_reviewer_bottom_bar_match_main_opacity": 100,
    "onigiri_reviewer_bottom_bar_match_reviewer_bg_blur": 0,
    "onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity": 100,
    "onigiri_reviewer_bottom_bar_match_overview_bg_blur": 0,
    "onigiri_reviewer_bottom_bar_match_overview_bg_opacity": 100,
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
    "onigiri_reviewer_btn_border_size": 0,
    "onigiri_reviewer_btn_custom_enabled": True, # Global toggle (Default OFF)
    "language": "English (Default)",
    "deck_indentation_mode": "default", # default, smaller, bigger, custom
    "deck_indentation_custom_px": 20, # px per level
    "onigiri_reviewer_btn_radius": 12, # px
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

    # --- Stats Bar Background (timer + New/Learn/Review pills panel behind the
    # Show Answer button). Independent color, unless synced with the "Other"
    # hover background above. ---
    "onigiri_reviewer_show_answer_bar_bg_sync": True,
    "onigiri_reviewer_show_answer_bar_bg_light": "#2c2c2c",
    "onigiri_reviewer_show_answer_bar_bg_dark": "#e0e0e0",

    # --- Stat Text (.stattxt) Colors (intervals like "10m", "4d" and "+" signs) ---
    "onigiri_reviewer_stattxt_mode": "hover",  # "hover" | "fixed" | "off"
    "onigiri_reviewer_stattxt_color_light": "#666666",
    "onigiri_reviewer_stattxt_color_dark": "#aaaaaa",

    # --- Timer (deck options "Show answer timer") adaptation ---
    "onigiri_reviewer_timer_position": "right",  # "right" | "left" | "out"
    "onigiri_reviewer_timer_bg_light": "#e5e5e5",
    "onigiri_reviewer_timer_text_light": "#2c2c2c",
    "onigiri_reviewer_timer_bg_dark": "#3a3a3a",
    "onigiri_reviewer_timer_text_dark": "#e0e0e0",

    "onigiri_overview_bg_dark_color": "#2C2C2C",
    "onigiri_overview_bg_image_light": "",
    "onigiri_overview_bg_image_dark": "",
    "onigiri_overview_bg_image": "",
    "onigiri_overview_bg_image_mode": "single",
    "onigiri_overview_bg_blur": 0,
    "onigiri_overview_bg_opacity": 100,
    "onigiri_overview_bg_color_theme_mode": "separate",
    "onigiri_overview_bg_image_theme_mode": "separate",
    "onigiri_overview_slideshow_images": [],
    "onigiri_overview_slideshow_interval": 10,
    "overview_style": {
        "sync_box_effect": False,
        "dynamic": True,
        "blur": 0,
        "opacity": 100,
        "radius": 20,
        "stroke": 1,
        "study_button_opacity": 100,
        "study_button_stroke": 0,
        "study_button_dashed": False,
        "study_button_animated": True,
        "colors": {
            "light": {
                "box_bg": "#f3f3f3",
                "box_border": "#e0e0e0",
                "study_button": "#0077C8",
                "new_bubble": "#1e8cff",
                "new_text": "#ffffff",
                "learn_bubble": "#19c96b",
                "learn_text": "#ffffff",
                "review_bubble": "#ff5757",
                "review_text": "#ffffff",
            },
            "dark": {
                "box_bg": "#2c2c2c",
                "box_border": "#565656",
                "study_button": "#0077C8",
                "new_bubble": "#0077C8",
                "new_text": "#f7fbff",
                "learn_bubble": "#12b765",
                "learn_text": "#f4fff8",
                "review_bubble": "#ff453a",
                "review_text": "#fff5f5",
            },
        },
    },
    # -----------------------------------------
    # --- REMOVED: Top-level focusDango was here ---
    "colors": {
        "light": {
            "--accent-color": "#0077C8",
            "--bg": "#f3f3f3",
            "--fg": "#212121",
            "--icon-color": "#333333",
            "--icon-color-filtered": "#0077C8",
            "--fg-subtle": "#757575",
            "--font-small-title-color": "#212121",
            "--border": "#e0e0e0",
            "--highlight-bg": "#eeeeee",
            "--canvas-inset": "#ffffff",
            "--button-primary-bg": "#0077C8",
            "--button-primary-gradient-start": "#00C49A",
            "--button-primary-gradient-end": "#008E72",
            "--new-count-bubble-bg": "#a3c5e8",
            "--new-count-bubble-fg": "#13375b",
            "--learn-count-bubble-bg": "#e8a3a3",
            "--learn-count-bubble-fg": "#731717",
            "--review-count-bubble-bg": "#a3e8b8",
            "--review-count-bubble-fg": "#1b7a38",
            "--heatmap-color": "#0077C8",
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
            "--accent-color": "#0077C8",
            "--bg": "#2c2c2c",
            "--fg": "#e0e0e0",
            "--icon-color": "#E0E0E0",
            "--icon-color-filtered": "#0077C8",
            "--fg-subtle": "#9e9e9e",
            "--font-small-title-color": "#e0e0e0",
            "--border": "#424242",
            "--highlight-bg": "#3c3c3c",
            "--canvas-inset": "#2c2c2c",
            "--button-primary-bg": "#0077C8",
            "--button-primary-gradient-start": "#00C49A",
            "--button-primary-gradient-end": "#008E72",
            "--new-count-bubble-bg": "#68a0d9",
            "--new-count-bubble-fg": "#13375b",
            "--learn-count-bubble-bg": "#d96868",
            "--learn-count-bubble-fg": "#731717",
            "--review-count-bubble-bg": "#68d98a",
            "--review-count-bubble-fg": "#1b7a38",
            "--heatmap-color": "#0077C8",
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
            "--deck-dragging-bg": "#3a3a3a",
            "--deck-edit-mode-bg": "rgba(128, 128, 128, 0.05)",
            # Text shadow colors
            "--text-shadow-light": "rgba(0, 0, 0, 0.5)",
            "--profile-pic-border": "rgba(255, 255, 255, 0.8)",
        }
    }
}



def normalize_overview_style_defaults(conf):
    """Migrate legacy dynamic Overviewer colors whose dark defaults matched light."""
    overview_style = conf.get("overview_style")
    if not isinstance(overview_style, dict):
        return conf

    colors = overview_style.get("colors")
    if not isinstance(colors, dict):
        return conf

    light_colors = colors.get("light")
    dark_colors = colors.get("dark")
    if not isinstance(light_colors, dict) or not isinstance(dark_colors, dict):
        return conf

    defaults = DEFAULTS.get("overview_style", {}).get("colors", {})
    default_light = defaults.get("light", {})
    default_dark = defaults.get("dark", {})
    legacy_light_values = {
        key: {str(value).lower()}
        for key, value in default_light.items()
        if isinstance(value, str)
    }
    legacy_light_values.setdefault("box_bg", set()).add("#e0e0e0")

    for key, dark_default in default_dark.items():
        light_value = light_colors.get(key)
        dark_value = dark_colors.get(key)
        if not isinstance(light_value, str) or not isinstance(dark_value, str):
            continue
        if dark_value.lower() != light_value.lower():
            continue
        if light_value.lower() not in legacy_light_values.get(key, set()):
            continue
        if dark_value.lower() != str(dark_default).lower():
            dark_colors[key] = dark_default

    return conf


def normalize_accent_color_defaults(conf):
    """Move saved legacy blue defaults to the current default accent."""
    legacy_color_defaults = {
        "light": {
            "--accent-color": "#007aff",
            "--icon-color-filtered": "#007aff",
            "--button-primary-bg": "#007aff",
            "--button-primary-gradient-start": "#0088ff",
            "--button-primary-gradient-end": "#0065c7",
            "--heatmap-color": "#007aff",
        },
        "dark": {
            "--accent-color": "#0a84ff",
            "--icon-color-filtered": "#0a84ff",
            "--button-primary-bg": "#0a84ff",
            "--button-primary-gradient-start": "#0a94ff",
            "--button-primary-gradient-end": "#0a74d9",
            "--heatmap-color": "#0a84ff",
        },
    }
    colors = conf.get("colors")
    if isinstance(colors, dict):
        for mode, legacy_values in legacy_color_defaults.items():
            palette = colors.get(mode)
            defaults = DEFAULTS.get("colors", {}).get(mode, {})
            if not isinstance(palette, dict):
                continue
            for key, legacy_value in legacy_values.items():
                value = palette.get(key)
                default_value = defaults.get(key)
                if (
                    isinstance(value, str)
                    and isinstance(default_value, str)
                    and value.lower() == legacy_value.lower()
                ):
                    palette[key] = default_value

    legacy_overview_defaults = {
        ("light", "study_button"): "#007aff",
        ("dark", "study_button"): "#0a84ff",
        ("dark", "new_bubble"): "#0a84ff",
    }
    overview_colors = conf.get("overview_style", {}).get("colors", {})
    if isinstance(overview_colors, dict):
        overview_defaults = DEFAULTS.get("overview_style", {}).get("colors", {})
        for (mode, key), legacy_value in legacy_overview_defaults.items():
            palette = overview_colors.get(mode)
            default_value = overview_defaults.get(mode, {}).get(key)
            if not isinstance(palette, dict) or not isinstance(default_value, str):
                continue
            value = palette.get(key)
            if isinstance(value, str) and value.lower() == legacy_value.lower():
                palette[key] = default_value

    return conf


# A unique ID for our add-on's configuration
config_id = None
def get_config_id():
    global config_id
    if config_id is None:
        config_id = mw.addonManager.addonFromModule(__name__)
    return config_id

def _get_settings_path() -> str:
    """Get the path to the profile-specific settings file."""
    try:
        # Calculate addon_path dynamically
        current_dir = os.path.dirname(os.path.abspath(__file__))
        user_files = os.path.join(current_dir, 'user_files')
        os.makedirs(user_files, exist_ok=True)
        
        # Determine profile name
        if mw.col and mw.pm and mw.pm.name:
            profile_name = mw.pm.name
        else:
            profile_name = "default"
            
        return os.path.join(user_files, f'settings_{profile_name}.json')
    except Exception as e:
        print(f"Error determining settings path: {e}")
        return ""

def get_config():
    """
    Loads the add-on's configuration from the profile-specific JSON file,
    falling back to Anki's shared config for migration or defaults.
    """
    # Start with a clean copy of the defaults
    clean_config = copy.deepcopy(DEFAULTS)


    
    # helper to merge dictionaries
    def merge_config(target, source):
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                merge_config(target[key], value)
            else:
                target[key] = value

    user_config = {}
    settings_path = _get_settings_path()
    
    # Try to load from profile specific file
    loaded_from_file = False
    if settings_path and os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                loaded_from_file = True
        except Exception as e:
            print(f"Error loading settings from {settings_path}: {e}")
    
    # If not found (First run for this profile), try migration from legacy shared config
    if not loaded_from_file and mw.col:
        try:
            legacy_config = mw.addonManager.getConfig(get_config_id())
            if legacy_config:
                print(f"Migrating legacy settings to {settings_path}")
                user_config = legacy_config
                # Save immediately to establish the new file
                try:
                    with open(settings_path, 'w', encoding='utf-8') as f:
                        json.dump(user_config, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"Error saving migrated settings: {e}")
        except Exception as e:
            print(f"Error reading legacy config: {e}")

    # Merge user settings into defaults.
    if user_config:
        merge_config(clean_config, user_config)
    # These two are ONE-TIME legacy migrations (move old blue accent/light defaults
    # to the current dark defaults). Running them on every load also reverted a
    # user who *deliberately* sets e.g. dark "new_bubble" to the light color
    # (#1e8cff) or the legacy blue (#0a84ff) back to the dark default (#00A982).
    # Gate them so they run once; the flag rides along in current_config and is
    # persisted on the next save, after which user edits stick.
    if not clean_config.get("_legacy_color_defaults_migrated"):
        normalize_accent_color_defaults(clean_config)
        normalize_overview_style_defaults(clean_config)
        clean_config["_legacy_color_defaults_migrated"] = True

    # Main Background colors are stored in mw.col.conf and should not become the
    # add-on's global theme background. Older builds accidentally copied them
    # into colors[*]["--bg"], which made Anki flash/show the selected background
    # color as soon as the profile opened.
    try:
        if mw.col:
            bg_conf_by_mode = {
                "light": mw.col.conf.get("modern_menu_bg_color_light"),
                "dark": mw.col.conf.get("modern_menu_bg_color_dark"),
            }
            colors_conf = clean_config.get("colors", {})
            for mode, main_bg_color in bg_conf_by_mode.items():
                mode_colors = colors_conf.get(mode, {})
                current_bg = mode_colors.get("--bg")
                default_bg = DEFAULTS.get("colors", {}).get(mode, {}).get("--bg")
                if (
                    isinstance(current_bg, str)
                    and isinstance(main_bg_color, str)
                    and isinstance(default_bg, str)
                    and current_bg.lower() == main_bg_color.lower()
                    and current_bg.lower() != default_bg.lower()
                ):
                    mode_colors["--bg"] = default_bg
    except Exception as e:
        print(f"Error cleaning main background color from theme config: {e}")
    
    # Compatibility migrations (logic preserved from original)
    custom_goals_conf = clean_config.get("achievements", {}).get("custom_goals", {})
    if "last_modified_at" not in custom_goals_conf:
        custom_goals_conf["last_modified_at"] = None
        if "achievements" in clean_config:
            clean_config["achievements"].setdefault("custom_goals", custom_goals_conf)

    if "gamification" in user_config and "achievements" not in user_config:
        clean_config["achievements"] = copy.deepcopy(user_config["gamification"])

    if "hexagon_world" in user_config and "hexagon_land" not in user_config:
        clean_config["hexagon_land"] = copy.deepcopy(user_config.get("hexagon_world", {}))

    # Compatibility: Check for old profile page visibility settings and migrate them
    # This ensures users updating the addon don't lose their settings
    if "showHeatmapOnProfile" not in user_config:
         if mw.col and "onigiri_profile_show_stats" in mw.col.conf:
            clean_config["showHeatmapOnProfile"] = mw.col.conf.get("onigiri_profile_show_stats", True)
        
    # Compatibility: Migrate restaurant_level and daily_special from achievements to top-level
    if "achievements" in clean_config:
        achievements_conf = clean_config["achievements"]
        
        # Migrate restaurant_level
        if "restaurant_level" in achievements_conf:
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

    # --- NEW FIX: Enforce Archive Exclusivity ---
    # Ensure items in 'archive' are NOT in 'grid'. The merge process might have
    # kept default grid positions for items the user wanted to archive.
    layout_conf = clean_config.get("onigiriWidgetLayout", {})
    if "grid" in layout_conf and "archive" in layout_conf:
        grid_conf = layout_conf["grid"]
        archive_conf = layout_conf["archive"]
        
        # Get set of archived IDs
        if isinstance(archive_conf, dict):
            archived_ids = set(archive_conf.keys())
        elif isinstance(archive_conf, list):
            archived_ids = set(archive_conf)
        else:
            archived_ids = set()
            
        # Remove them from grid
        for widget_id in archived_ids:
            if widget_id in grid_conf:
                del grid_conf[widget_id]
    if isinstance(layout_conf, dict):
        grid_conf = layout_conf.setdefault("grid", {})
        archive_conf = layout_conf.get("archive", [])
        if isinstance(archive_conf, dict):
            archived_ids = set(archive_conf.keys())
        elif isinstance(archive_conf, list):
            archived_ids = set(archive_conf)
        else:
            archived_ids = set()
        for missing_widget_id in ("deck_stats",):
            if isinstance(grid_conf, dict) and missing_widget_id not in grid_conf and missing_widget_id not in archived_ids:
                if isinstance(archive_conf, list):
                    archive_conf.append(missing_widget_id)
                elif isinstance(archive_conf, dict):
                    archive_conf.setdefault(missing_widget_id, {"pos": 12, "row": 2, "col": 2})
                layout_conf["archive"] = archive_conf
        if isinstance(grid_conf, dict) and isinstance(grid_conf.get("deck_stats"), dict):
            deck_stats_conf = grid_conf["deck_stats"]
            try:
                deck_stats_conf["row"] = max(1, min(2, int(deck_stats_conf.get("row", 2))))
            except (TypeError, ValueError):
                deck_stats_conf["row"] = 2
            try:
                deck_stats_conf["col"] = max(1, min(2, int(deck_stats_conf.get("col", 1))))
            except (TypeError, ValueError):
                deck_stats_conf["col"] = 1

        try:
            widget_height = int(layout_conf.get("widget_height", 120))
        except (TypeError, ValueError):
            widget_height = 120
        layout_conf["widget_height"] = max(120, widget_height)
    # --------------------------------------------

    external_layout_conf = clean_config.get("externalWidgetLayout", {})
    if isinstance(external_layout_conf, dict):
        external_grid_conf = external_layout_conf.get("grid", external_layout_conf)
        if isinstance(external_grid_conf, dict):
            for widget_conf in external_grid_conf.values():
                if not isinstance(widget_conf, dict):
                    continue
                try:
                    row_span = int(widget_conf.get("row_span", 2))
                except (TypeError, ValueError):
                    row_span = 2
                widget_conf["row_span"] = max(2, row_span)

    # --- NEW: Sidebar Gamification Button Migration ---
    # Ensure "gamification" is in the visible list if not present anywhere
    sidebar_conf = clean_config.setdefault("sidebarButtonLayout", {"visible": [], "archived": []})
    visible_btns = sidebar_conf.get("visible", [])
    archived_btns = sidebar_conf.get("archived", [])
    
    if "gamification" not in visible_btns and "gamification" not in archived_btns:
        # Insert before "more" if more exists, else append
        if "more" in visible_btns:
            idx = visible_btns.index("more")
            visible_btns.insert(idx, "gamification")
        else:
            visible_btns.append("gamification")
    # --------------------------------------------------

    # Compatibility: the old "Show numbers" boolean toggle became a 3-way
    # "Stats Numbers" mode (hover / fixed / off).
    if "onigiri_reviewer_stattxt_mode" not in user_config and "onigiri_reviewer_stattxt_visible" in user_config:
        clean_config["onigiri_reviewer_stattxt_mode"] = "hover" if user_config["onigiri_reviewer_stattxt_visible"] else "off"

    return clean_config


def write_config(config):
    """
    Saves the provided configuration dictionary to the profile-specific JSON file.
    """
    settings_path = _get_settings_path()
    if settings_path:
        try:
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error writing settings to {settings_path}: {e}")
            
    # Optional: We could also write to Anki's config as a backup, 
    # but we want to simulate isolation, so maybe better not to, 
    # or obscure it to avoid confusion in the Add-on Config dialog.
    # For user clarity, let's NOT write to the shared config.
    # mw.addonManager.writeConfig(get_config_id(), config)


def log_perf(message: str):
    """
    Writes performance log messages with high precision to user_files/perf.log.
    """
    import datetime
    import time
    try:
        addon_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(addon_dir, "user_files")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "perf.log")

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        perf_t = time.perf_counter()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [Perf={perf_t:.6f}] {message}\n")
    except Exception as e:
        print(f"Error writing to perf.log: {e}")
