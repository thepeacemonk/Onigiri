import time
import os
import base64
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

    # --- 5. Calculate Longest Streak Ever ---
    longest_streak = 0
    if review_days_set:
        longest_streak = 1
        current_run = 1
        sorted_days = sorted(
            datetime.strptime(day_key, "%Y-%m-%d").date()
            for day_key in review_days_set
        )
        for previous_day, current_day in zip(sorted_days, sorted_days[1:]):
            if (current_day - previous_day).days == 1:
                current_run += 1
            else:
                current_run = 1
            longest_streak = max(longest_streak, current_run)
    longest_streak = max(longest_streak, streak)

    # --- 6. Calculate Daily Average ---
    # Total reviews / Days since first review
    # We use the count of all reviews in history (no date limit)
    total_reviews_all_time = mw.col.db.scalar("SELECT COUNT() FROM revlog WHERE type IN (0,1,2,3)") or 0
    
    daily_average = 0
    if total_reviews_all_time > 0:
        # distinct days
        first_review_ts = mw.col.db.scalar("SELECT min(id) FROM revlog WHERE type IN (0,1,2,3)")
        if first_review_ts:
            # Calculate days elapsed
            first_review_date = datetime.fromtimestamp(first_review_ts / 1000).date()
            today_date = datetime.fromtimestamp(today_start_seconds).date()
            days_elapsed = (today_date - first_review_date).days + 1
            if days_elapsed < 1: 
                days_elapsed = 1
                
            daily_average = total_reviews_all_time / days_elapsed

    first_year = datetime.now().year
    first_review_ts = mw.col.db.scalar("SELECT min(id) FROM revlog WHERE type IN (0,1,2,3)")
    if first_review_ts:
        first_year = datetime.fromtimestamp(first_review_ts / 1000).year

    return {
        "calendar": reviews_by_day, 
        "streak": streak, 
        "longest_streak": longest_streak,
        "due_calendar": due_by_day,
        "today_date_key": today_date_key,
        "rollover_hour": rollover_hour, # Still useful for JS, though not for date math
        "daily_average": daily_average,
        "firstYear": first_year,
    }

def get_heatmap_and_config():
    """Helper to bundle heatmap data and configuration together for JavaScript."""
    conf = config.get_config()
    heatmap_data = get_heatmap_data()

    addon_path = os.path.dirname(__file__)
    shape_filename = conf.get("heatmapShape", DEFAULTS["heatmapShape"])

    def system_icon_path(filename):
        filename = os.path.basename(str(filename or ""))
        for folder in ("available_for_users", "unavailable_for_users"):
            path = os.path.join(addon_path, "system_files", "system_icons", folder, filename)
            if os.path.exists(path):
                return path
        return ""

    def shape_file_path(value):
        value = str(value or "")
        if value.startswith("system:"):
            return system_icon_path(value[len("system:"):])
        for folder in ("custom_deck_icons", "icons"):
            path = os.path.join(addon_path, "user_files", folder, value)
            if os.path.exists(path):
                return path
        return system_icon_path(value)

    def icon_svg_content(icon_value, fallback_filename):
        icon_value = str(icon_value or "")
        icon_path = shape_file_path(icon_value)
        svg = ""
        if icon_value.startswith("emoji:"):
            emoji = icon_value[len("emoji:"):]
            svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><text x="16" y="24" text-anchor="middle" font-size="24">{emoji}</text></svg>'
        elif icon_path and icon_path.lower().endswith(".png"):
            try:
                with open(icon_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("ascii")
                svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><image href="data:image/png;base64,{encoded}" width="32" height="32" preserveAspectRatio="xMidYMid meet"/></svg>'
            except (FileNotFoundError, IOError):
                svg = ""
        elif icon_path:
            try:
                with open(icon_path, 'r', encoding='utf-8') as f:
                    svg = f.read()
            except (FileNotFoundError, IOError):
                svg = ""
        if not svg:
            fallback_path = system_icon_path(fallback_filename)
            try:
                with open(fallback_path, 'r', encoding='utf-8') as f:
                    svg = f.read()
            except (FileNotFoundError, IOError):
                svg = '<svg viewBox="0 0 10 10"><rect width="10" height="10" /></svg>'
        return svg

    svg_content = icon_svg_content(shape_filename, "square.svg")
    streak_icon_filename = conf.get("heatmapStreakIcon", DEFAULTS.get("heatmapStreakIcon", "system:fire.svg"))
    if str(streak_icon_filename).startswith("emoji:"):
        streak_icon_filename = DEFAULTS.get("heatmapStreakIcon", "system:fire.svg")
    streak_svg_content = icon_svg_content(streak_icon_filename, "fire.svg")

    from .translations import tr
    heatmap_config = {
        "heatmapSvgContent": svg_content,
        "heatmapStreakIconSvgContent": streak_svg_content,
        "heatmapStreakIconColor": conf.get("heatmapStreakIconColor", DEFAULTS.get("heatmapStreakIconColor", "#ff6b35")),
        "heatmapStreakIconZeroColor": conf.get("heatmapStreakIconZeroColor", DEFAULTS.get("heatmapStreakIconZeroColor", "#8f8f8f")),
        "heatmapShowStreak": conf.get("heatmapShowStreak", DEFAULTS["heatmapShowStreak"]),
        "heatmapShowMonths": conf.get("heatmapShowMonths", DEFAULTS["heatmapShowMonths"]),
        "heatmapShowWeekdays": conf.get("heatmapShowWeekdays", DEFAULTS["heatmapShowWeekdays"]),
        "heatmapShowWeekHeader": conf.get("heatmapShowWeekHeader", DEFAULTS["heatmapShowWeekHeader"]),
        "heatmapDefaultView": conf.get("heatmapDefaultView", DEFAULTS["heatmapDefaultView"]),
        "heatmapWeekStart": conf.get("heatmapWeekStart", DEFAULTS.get("heatmapWeekStart", "monday")),
        "i18n": {
            "activity": tr("heatmap_activity_label"),
            "year": tr("view_year"),
            "month": tr("view_month"),
            "week": tr("view_week"),
            "day_streak": tr("heatmap_day_streak"),
        }
    }
    return heatmap_data, heatmap_config
