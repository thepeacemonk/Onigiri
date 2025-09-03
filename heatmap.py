import time
import os
from datetime import datetime, timedelta
from aqt import mw
from . import config
from .config import DEFAULTS

def get_heatmap_data():
    """
    Fetches review data and calculates daily counts and the current streak.
    The data format is compatible with the heatmap.js renderer.
    """
    if not mw.col:
        return {"calendar": {}, "streak": 0}

    # Rollover hour from config, default to 4am
    rollover_hour = mw.col.conf.get("rollover", 4)

    # Fetch all review timestamps in seconds
    query = "SELECT id / 1000 FROM revlog"
    timestamps = mw.col.db.list(query)

    reviews_by_day = {}
    # Use a set for fast checking of days with reviews
    review_days_epoch = set()

    for ts in timestamps:
        # Adjust for rollover: subtract rollover hours to get the "Anki day"
        dt_obj = datetime.fromtimestamp(ts) - timedelta(hours=rollover_hour)
        # Convert to days since epoch
        day_epoch = (dt_obj - datetime(1970, 1, 1)).days
        
        reviews_by_day[day_epoch] = reviews_by_day.get(day_epoch, 0) + 1
        review_days_epoch.add(day_epoch)

    # Calculate streak
    streak = 0
    if review_days_epoch:
        today_dt = datetime.now() - timedelta(hours=rollover_hour)
        today_epoch = (today_dt - datetime(1970, 1, 1)).days
        
        # Check if today or yesterday has reviews to start the streak count
        if today_epoch in review_days_epoch or (today_epoch - 1) in review_days_epoch:
            current_day_check = today_epoch
            # If today has no reviews, start checking from yesterday
            if today_epoch not in review_days_epoch:
                current_day_check -= 1
            
            while current_day_check in review_days_epoch:
                streak += 1
                current_day_check -= 1

    return {"calendar": reviews_by_day, "streak": streak}

def get_heatmap_and_config():
    """Helper to bundle heatmap data and configuration together for JavaScript."""
    conf = config.get_config()
    heatmap_data = get_heatmap_data()

    # Read selected SVG shape file
    addon_path = os.path.dirname(__file__)
    shape_filename = conf.get("heatmapShape", DEFAULTS["heatmapShape"])
    shape_path = os.path.join(addon_path, "user_files", "heatmap_icons", "heatmap_system_icons", shape_filename)

    svg_content = ""
    try:
        with open(shape_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
    except (FileNotFoundError, IOError):
        # Fallback to square.svg if the configured shape is not found
        fallback_path = os.path.join(addon_path, "user_files", "heatmap_icons", "heatmap_system_icons", "square.svg")
        try:
            with open(fallback_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
        except (FileNotFoundError, IOError):
            # Absolute fallback if even square.svg is missing
            svg_content = '<svg viewBox="0 0 10 10"><rect width="10" height="10" /></svg>'

    # The config passed to JS no longer needs specific color values.
    # JS will read the theme-appropriate CSS variables directly.
    heatmap_config = {
        "heatmapSvgContent": svg_content,
        "heatmapShowStreak": conf.get("heatmapShowStreak", DEFAULTS["heatmapShowStreak"]),
        "heatmapShowMonths": conf.get("heatmapShowMonths", DEFAULTS["heatmapShowMonths"]),
        "heatmapShowWeekdays": conf.get("heatmapShowWeekdays", DEFAULTS["heatmapShowWeekdays"]),
        "heatmapShowWeekHeader": conf.get("heatmapShowWeekHeader", DEFAULTS["heatmapShowWeekHeader"]),
    }
    return heatmap_data, heatmap_config

