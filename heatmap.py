import time
import os
from datetime import datetime, timedelta, timezone
from aqt import mw
from . import config
from .config import DEFAULTS

def get_heatmap_data():
    """
    Fetches review data and calculates daily counts and the current streak.
    Counts TOTAL REVIEWS per day (matching Anki's Stats calendar).
    Excludes filtered/cram deck reviews (type 3).
    """
    if not mw.col:
        return {"calendar": {}, "streak": 0}

    # Rollover hour from config, default to 4am
    rollover_hour = mw.col.conf.get("rollover", 4)
    offset_seconds = rollover_hour * 3600

    # Count total reviews per day, excluding filtered deck reviews (type 3)
    # This matches Anki's Stats calendar behavior
    query = """
        SELECT 
            id
        FROM revlog
        WHERE type IN (0, 1, 2)
        ORDER BY id
    """
    
    all_reviews = mw.col.db.list(query)
    
    # Group by day and count reviews
    reviews_by_day = {}
    
    for review_timestamp_ms in all_reviews:
        # Convert milliseconds to seconds
        timestamp_seconds = review_timestamp_ms / 1000.0
        
        # Adjust for rollover
        adjusted_timestamp = timestamp_seconds - offset_seconds
        
        # Calculate day number (days since Unix epoch)
        day_number = int(adjusted_timestamp // 86400)
        
        # Count reviews per day
        reviews_by_day[day_number] = reviews_by_day.get(day_number, 0) + 1
    
    # DEBUG: Write to file
    debug_file = os.path.join(os.path.dirname(__file__), "heatmap_debug.txt")
    try:
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write("=== ONIGIRI HEATMAP DEBUG (COUNTING REVIEWS) ===\n")
            f.write(f"Rollover hour: {rollover_hour}\n")
            f.write(f"Offset seconds: {offset_seconds}\n")
            f.write(f"Total days with reviews: {len(reviews_by_day)}\n\n")
            
            # Calculate Nov 12, 2024 day number properly
            nov12 = datetime(2024, 11, 12, rollover_hour, 0, 0)
            nov12_timestamp = nov12.timestamp()
            nov12_adjusted = nov12_timestamp - offset_seconds
            nov12_day = int(nov12_adjusted // 86400)
            
            f.write(f"Nov 12, 2024 day number: {nov12_day}\n\n")
            
            # Detailed breakdown for Nov 12
            nov12_start = int((nov12_adjusted * 1000))
            nov12_end = int(((nov12_adjusted + 86400) * 1000))
            
            f.write("Nov 12, 2024 breakdown:\n")
            
            # Count by type
            type_query = """
                SELECT type, COUNT(DISTINCT cid), COUNT(*)
                FROM revlog
                WHERE id >= ? AND id < ?
                GROUP BY type
            """
            type_counts = mw.col.db.all(type_query, nov12_start, nov12_end)
            
            type_names = {0: "Learn", 1: "Review", 2: "Relearn", 3: "Filtered/Cram"}
            for review_type, unique_cards, total_reviews in type_counts:
                type_name = type_names.get(review_type, f"Type {review_type}")
                f.write(f"  {type_name}: {unique_cards} unique cards, {total_reviews} reviews\n")
            
            total_reviews_all = sum(count[2] for count in type_counts)
            f.write(f"  TOTAL (all types): {total_reviews_all} reviews\n")
            
            # Excluding type 3
            excluding_filtered = [count for count in type_counts if count[0] in (0, 1, 2)]
            if excluding_filtered:
                total_reviews_no_filtered = sum(count[2] for count in excluding_filtered)
                f.write(f"  TOTAL (excl. filtered): {total_reviews_no_filtered} reviews\n\n")
            
            f.write("Days around Nov 12, 2024:\n")
            for day_num in range(nov12_day - 2, nov12_day + 3):
                if day_num in reviews_by_day:
                    date_timestamp = (day_num * 86400) + offset_seconds
                    date_obj = datetime.fromtimestamp(date_timestamp)
                    f.write(f"  Day {day_num} ({date_obj.strftime('%Y-%m-%d')}): {reviews_by_day[day_num]} reviews\n")
            
            f.write("\n=== END DEBUG ===\n")
    except Exception as e:
        pass
    
    # Use a set for fast checking of days with reviews
    review_days_epoch = set(reviews_by_day.keys())

    # Calculate streak
    streak = 0
    if review_days_epoch:
        # Get current time and adjust for rollover
        now = datetime.now()
        current_timestamp = now.timestamp() - offset_seconds
        today_epoch = int(current_timestamp // 86400)
        
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

    heatmap_config = {
        "heatmapSvgContent": svg_content,
        "heatmapShowStreak": conf.get("heatmapShowStreak", DEFAULTS["heatmapShowStreak"]),
        "heatmapShowMonths": conf.get("heatmapShowMonths", DEFAULTS["heatmapShowMonths"]),
        "heatmapShowWeekdays": conf.get("heatmapShowWeekdays", DEFAULTS["heatmapShowWeekdays"]),
        "heatmapShowWeekHeader": conf.get("heatmapShowWeekHeader", DEFAULTS["heatmapShowWeekHeader"]),
    }
    return heatmap_data, heatmap_config
