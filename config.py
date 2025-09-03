import copy
from aqt import mw

# Default settings for the add-on
DEFAULTS = {
    "userName": "USER",
    "hideStudiedToday": False,
    "hideTodaysStats": False,
    "statsTitle": "Today's Stats",
    "studyNowText": "Study Now",
    "hideProfileBar": False,
    "hideWelcomeMessage": False,
    "hideNativeHeaderAndBottomBar": False,
    "ultraHide": False,
    "sidebarCollapsed": False,
    "showCongratsProfileBar": True,
    "congratsMessage": "Congratulations! You have finished this deck for now.",
    "showHeatmapOnMain": True,
    "heatmapShape": "square.svg",
    "heatmapShowStreak": True,
    "heatmapShowMonths": True,
    "heatmapShowWeekdays": True,
    "heatmapShowWeekHeader": True,
    "colors": {
        "light": {
            "--accent-color": "#007aff",
            "--bg": "#f3f3f3",
            "--fg": "#212121",
            "--icon-color": "#333333",
            "--fg-subtle": "#757575",
            "--border": "#e0e0e0",
            "--highlight-bg": "#eeeeee",
            "--highlight-background": "#DDDDDD",
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
        },
        "dark": {
            "--accent-color": "#0a84ff",
            "--bg": "#2c2c2c",
            "--fg": "#e0e0e0",
            "--icon-color": "#E0E0E0",
            "--fg-subtle": "#9e9e9e",
            "--border": "#424242",
            "--highlight-bg": "#3c3c3c",
            "--highlight-background": "#444444",
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
    
    # Compatibility: Check for old profile page visibility settings and migrate them
    # This ensures users updating the addon don't lose their settings
    if "onigiri_profile_show_stats" in mw.col.conf:
        clean_config["showHeatmapOnProfile"] = mw.col.conf.get("onigiri_profile_show_stats", True)

    return clean_config


def write_config(config):
    """
    Saves the provided configuration dictionary to Anki's settings.
    """
    mw.addonManager.writeConfig(get_config_id(), config)