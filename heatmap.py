import time
import os
from datetime import datetime
from aqt import mw
from . import config
from .config import DEFAULTS

def get_heatmap_data():
    """
    Fetches review data (past) and due card data (today/future),
    and calculates the current streak.
    All date/day calculations are done in Python using Anki's
    local timezone settings to ensure accuracy.
    """
    if not mw.col:
        return {"calendar": {}, "streak": 0, "due_calendar": {}}

    # Rollover hour from config, default to 4am
    rollover_hour = mw.col.conf.get("rollover", 4)
    offset_seconds = rollover_hour * 3600

    # Get Anki's dayCutoff (timestamp for start of *next* day in local time)
    day_cutoff_seconds = mw.col.sched.day_cutoff
    
    # Calculate the timestamp for the *start of today*
    today_start_seconds = day_cutoff_seconds - 86400
    today_start_ms = today_start_seconds * 1000
    
    # Get the local date string for today (e.g., "2025-10-23")
    today_date_key = datetime.fromtimestamp(today_start_seconds).strftime('%Y-%m-%d')

    # --- 1. Fetch Past Reviews (excluding today) ---
    # Use STRFTIME with 'localtime' and the offset to correctly group reviews
    # by the local day, just like the reference add-on.
    # type IN (0,1,2,3) filters out manual operations (type 4 = manual rescheduling/resets)
    query_past = """
        SELECT 
            STRFTIME('%Y-%m-%d', id / 1000 - ?, 'unixepoch', 'localtime', 'start of day') as day_key,
            COUNT()
        FROM revlog
        WHERE type IN (0,1,2,3) AND id < ? -- Only actual reviews *before* the start of today
        GROUP BY day_key
    """
    reviews_by_day = dict(mw.col.db.all(query_past, offset_seconds, today_start_ms))

    # --- 2. Fetch Today's Review Count ---
    # Get a precise count for reviews *since* the start of today
    # type IN (0,1,2,3) filters out manual operations (type 4 = manual rescheduling/resets)
    today_count = mw.col.db.scalar(
        "SELECT COUNT() FROM revlog WHERE type IN (0,1,2,3) AND id >= ?",
        today_start_ms
    ) or 0
    reviews_by_day[today_date_key] = today_count

    # --- 3. Fetch Future Due Cards ---
    due_by_day = {}
    today_anki_day = mw.col.sched.today
    
    query_due = """
        SELECT due, COUNT(*)
        FROM cards
        WHERE queue = 2 AND due > ?
        GROUP BY due
    """
    due_counts = mw.col.db.all(query_due, today_anki_day)
    
    # Convert Anki's relative due days (e.g., 5) into
    # absolute local date strings (e.g., "2025-10-28")
    for anki_due_day, count in due_counts:
        days_from_today = anki_due_day - today_anki_day
        
        # Add the day offset to today's start timestamp
        future_timestamp_s = today_start_seconds + (days_from_today * 86400)
        
        # Convert to local date string
        future_date_key = datetime.fromtimestamp(future_timestamp_s).strftime('%Y-%m-%d')
        due_by_day[future_date_key] = count

    # --- 4. Calculate Streak ---
    # We must use the same date logic for all review days
    # type IN (0,1,2,3) filters out manual operations (type 4 = manual rescheduling/resets)
    all_review_days_query = """
        SELECT DISTINCT STRFTIME('%Y-%m-%d', id / 1000 - ?, 'unixepoch', 'localtime', 'start of day')
        FROM revlog
        WHERE type IN (0,1,2,3)
    """
    review_days_set = set(mw.col.db.list(all_review_days_query, offset_seconds))
    
    streak = 0
    yesterday_key = datetime.fromtimestamp(today_start_seconds - 86400).strftime('%Y-%m-%d')

    if today_date_key in review_days_set or yesterday_key in review_days_set:
        current_day_check_ts = today_start_seconds
        # If no reviews today, start checking from yesterday
        if today_date_key not in review_days_set:
            current_day_check_ts -= 86400
            
        while True:
            check_key = datetime.fromtimestamp(current_day_check_ts).strftime('%Y-%m-%d')
            if check_key in review_days_set:
                streak += 1
                current_day_check_ts -= 86400  # Move to the previous day
            else:
                break  # Streak broken

    return {
        "calendar": reviews_by_day, 
        "streak": streak, 
        "due_calendar": due_by_day,
        "today_date_key": today_date_key,
        "rollover_hour": rollover_hour # Still useful for JS, though not for date math
    }

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
        "heatmapDefaultView": conf.get("heatmapDefaultView", DEFAULTS["heatmapDefaultView"]),
    }
    return heatmap_data, heatmap_config