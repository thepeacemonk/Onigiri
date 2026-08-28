import time
import os
import base64
from datetime import date, datetime
from aqt import mw
from . import config
from .config import DEFAULTS

# Cache to avoid re-scanning the whole revlog on every render frame
# (state_did_change + deck_browser_did_render + autoRender all fire in
# quick succession when returning to the main menu).
_HEATMAP_CACHE = None
_HEATMAP_CACHE_TIME = 0
_HEATMAP_CACHE_TTL = 5  # seconds

# Per-day review counts for every day BEFORE today. That grouped STRFTIME scan
# is the single most expensive thing the deck browser does (~39ms on a 100k-row
# revlog), and answering a card can only ever change *today's* number - so the
# past is cached for the session and only revalidated against the shape of the
# revlog, not re-aggregated. Deliberately not cleared by
# invalidate_heatmap_cache(): that fires after every answered card.
_PAST_DAYS_CACHE = None
_PAST_DAYS_KEY = None


def browser_search_for_date(date_key: str, today_date_key: str) -> str:
    """Build an exact-day Browser search for a heatmap date.

    Anki's ``prop:rated`` offsets use zero for today and negative values for
    earlier days, while ``prop:due`` uses positive values for future days.
    Working with calendar dates instead of seconds keeps the offset stable
    across daylight-saving changes.
    """
    try:
        selected_date = date.fromisoformat(date_key)
        today_date = date.fromisoformat(today_date_key)
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid heatmap date") from error

    # fromisoformat() has accepted a few non-canonical variants across Python
    # versions. The webview bridge deliberately accepts only YYYY-MM-DD.
    if (
        selected_date.isoformat() != date_key
        or today_date.isoformat() != today_date_key
    ):
        raise ValueError("Invalid heatmap date")

    day_offset = (selected_date - today_date).days
    if day_offset > 0:
        return f"prop:due={day_offset}"
    return f"prop:rated={day_offset}"


def invalidate_heatmap_cache():
    global _HEATMAP_CACHE, _HEATMAP_CACHE_TIME
    _HEATMAP_CACHE = None
    _HEATMAP_CACHE_TIME = 0

def _past_reviews_by_day(offset_seconds, today_start_ms):
    """(day_key, count) for every day before today, cached for the session.

    Revalidated with two rowid-indexed lookups (~2ms) instead of re-running the
    grouped STRFTIME scan (~39ms): the row count catches deletions and
    undo-past-rollover, the max id catches insertions. Both are cheap because
    revlog.id is the rowid.
    """
    global _PAST_DAYS_CACHE, _PAST_DAYS_KEY

    try:
        row_count = mw.col.db.scalar(
            "SELECT COUNT() FROM revlog WHERE id < ?", today_start_ms
        ) or 0
        last_id = mw.col.db.scalar(
            "SELECT max(id) FROM revlog WHERE id < ?", today_start_ms
        ) or 0
    except Exception:
        row_count = last_id = None

    # crt identifies the collection, so switching profiles cannot reuse another
    # profile's aggregate.
    try:
        collection_id = mw.col.crt
    except Exception:
        collection_id = None

    key = (collection_id, offset_seconds, today_start_ms, row_count, last_id)
    if _PAST_DAYS_CACHE is not None and key == _PAST_DAYS_KEY and row_count is not None:
        return _PAST_DAYS_CACHE

    query_past = """
        SELECT 
            STRFTIME('%Y-%m-%d', id / 1000 - ?, 'unixepoch', 'localtime', 'start of day') as day_key,
            COUNT()
        FROM revlog
        WHERE type IN (0,1,2,3) AND id < ? -- Only actual reviews *before* the start of today
        GROUP BY day_key
    """
    rows = mw.col.db.all(query_past, offset_seconds, today_start_ms)
    if row_count is not None:
        _PAST_DAYS_CACHE = rows
        _PAST_DAYS_KEY = key
    return rows


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
    reviews_by_day = dict(_past_reviews_by_day(offset_seconds, today_start_ms))

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
    # reviews_by_day already groups the whole revlog by the same STRFTIME
    # expression, so the day set is derivable from it. Running a second
    # DISTINCT STRFTIME query here meant a full extra revlog scan on every
    # deck browser render. Past groups always have a non-zero count; today is
    # the only key that can be present with zero reviews.
    review_days_set = {day for day, count in reviews_by_day.items() if count}
    
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
            date.fromisoformat(day_key) for day_key in review_days_set
        )
        for previous_day, current_day in zip(sorted_days, sorted_days[1:]):
            if (current_day - previous_day).days == 1:
                current_run += 1
            else:
                current_run = 1
            longest_streak = max(longest_streak, current_run)
    longest_streak = max(longest_streak, streak)

    # --- 6. Calculate Daily Average ---
    # Total reviews / Days since first review.
    # The per-day counts already cover the whole history, so summing them
    # avoids a third full revlog scan for the same number.
    total_reviews_all_time = sum(reviews_by_day.values())

    # One min(id) lookup, shared by the daily average and the calendar's
    # first year below.
    first_review_ts = None
    if total_reviews_all_time > 0:
        first_review_ts = mw.col.db.scalar("SELECT min(id) FROM revlog WHERE type IN (0,1,2,3)")

    daily_average = 0
    if total_reviews_all_time > 0:
        if first_review_ts:
            # Calculate days elapsed
            first_review_date = datetime.fromtimestamp(first_review_ts / 1000).date()
            today_date = datetime.fromtimestamp(today_start_seconds).date()
            days_elapsed = (today_date - first_review_date).days + 1
            if days_elapsed < 1: 
                days_elapsed = 1
                
            daily_average = total_reviews_all_time / days_elapsed

    first_year = datetime.now().year
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
    global _HEATMAP_CACHE, _HEATMAP_CACHE_TIME
    now = time.time()
    if _HEATMAP_CACHE is not None and (now - _HEATMAP_CACHE_TIME) < _HEATMAP_CACHE_TTL:
        return _HEATMAP_CACHE

    conf = config.get_config_readonly()
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

    from .translations import current_language, tr
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
        # The browser's locale can differ from the language chosen for Onigiri.
        "locale": current_language(),
        "i18n": {
            "activity": tr("heatmap_activity_label"),
            "year": tr("view_year"),
            "month": tr("view_month"),
            "week": tr("view_week"),
            "day_streak": tr("heatmap_day_streak"),
            "browse": tr("browse", "Browse"),
        }
    }
    _HEATMAP_CACHE = (heatmap_data, heatmap_config)
    _HEATMAP_CACHE_TIME = now
    return _HEATMAP_CACHE
