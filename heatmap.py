import time
import os
from datetime import datetime, timedelta, timezone
from aqt import mw
from . import config
from .config import DEFAULTS

def get_heatmap_data():
    """
    Fetches review data (past) and due card data (today/future),
    and calculates the current streak.
    """
    if not mw.col:
        return {"calendar": {}, "streak": 0, "due_calendar": {}}

    # Rollover hour from config, default to 4am
    rollover_hour = mw.col.conf.get("rollover", 4)
    offset_seconds = rollover_hour * 3600

    # Count total past reviews per day, excluding filtered deck reviews (type 3)
    query = """
        SELECT 
            id
        FROM revlog
        WHERE type IN (0, 1, 2)
        ORDER BY id
    """
    
    all_reviews = mw.col.db.list(query)
    
    reviews_by_day = {}
    for review_timestamp_ms in all_reviews:
        timestamp_seconds = review_timestamp_ms / 1000.0
        adjusted_timestamp = timestamp_seconds - offset_seconds
        day_number = int(adjusted_timestamp // 86400)
        reviews_by_day[day_number] = reviews_by_day.get(day_number, 0) + 1
    
    # --- NEW: Fetch future due cards ---
    due_by_day = {}
    today_anki_day = mw.col.sched.today
    
    query_due = """
        SELECT due, COUNT(*)
        FROM cards
        WHERE queue = 2 AND due >= ?
        GROUP BY due
    """
    due_counts = mw.col.db.all(query_due, today_anki_day)
    
    now = datetime.now()
    current_timestamp = now.timestamp() - offset_seconds
    today_epoch_day = int(current_timestamp // 86400)
    
    for anki_due_day, count in due_counts:
        days_from_today = anki_due_day - today_anki_day
        future_epoch_day = today_epoch_day + days_from_today
        due_by_day[future_epoch_day] = count
    # --- END NEW ---

    # Calculate streak
    streak = 0
    review_days_epoch = set(reviews_by_day.keys())
    if review_days_epoch:
        if today_epoch_day in review_days_epoch or (today_epoch_day - 1) in review_days_epoch:
            current_day_check = today_epoch_day
            if today_epoch_day not in review_days_epoch:
                current_day_check -= 1
            
            while current_day_check in review_days_epoch:
                streak += 1
                current_day_check -= 1

    return {"calendar": reviews_by_day, "streak": streak, "due_calendar": due_by_day}

def get_heatmap_and_config():
    """Helper to bundle heatmap data and configuration together for JavaScript."""
    conf = config.get_config()
    heatmap_data = get_heatmap_data()

    # Read selected SVG shape file
    addon_path = os.path.dirname(__file__)
    shape_filename = conf.get("heatmapShape", DEFAULTS["heatmapShape"])
    shape_path = os.path.join(addon_path, "system_files", "heatmap_system_icons", shape_filename)

    svg_content = ""
    try:
        with open(shape_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
    except (FileNotFoundError, IOError):
        fallback_path = os.path.join(addon_path, "system_files", "heatmap_system_icons", "square.svg")
        try:
            with open(fallback_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
        except (FileNotFoundError, IOError):
            svg_content = '<svg viewBox="0 0 10 10"><rect width="10" height="10" /></svg>'

    heatmap_config = {
        "heatmapSvgContent": svg_content,
        "heatmapShowStreak": conf.get("heatmapShowStreak", DEFAULTS["heatmapShowStreak"]),
        "heatmapShowMonths": conf.get("heatmapShowMonths", DEFAULTS["heatmapShowMonths"]),
        "heatmapShowWeekdays": conf.get("heatmapShowWeekdays", DEFAULTS["heatmapShowWeekdays"]),
        "heatmapShowWeekHeader": conf.get("heatmapShowWeekHeader", DEFAULTS["heatmapShowWeekHeader"]),
    }
    return heatmap_data, heatmap_config
