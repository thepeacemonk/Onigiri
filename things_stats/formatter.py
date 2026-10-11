"""
Studylytics — Assembles the final JSON data structure for the dashboard.

Single entry point: build_dashboard_data(col, period)
"""

from datetime import datetime

from . import analyzer
from . import metrics


def build_dashboard_data(
    col,
    period: str = "30d",
    custom_start_ms: int = 0,
    custom_end_ms: int = 0,
) -> dict:
    """Build the complete dashboard data dict matching window.__STUDYLYTICS__.

    Args:
        col: Anki collection object (mw.col)
        period: One of "1d", "7d", "30d", "90d", "12m", "all", "custom"
        custom_start_ms: Start epoch ms (only used when period="custom")
        custom_end_ms: End epoch ms (only used when period="custom")

    Returns:
        Dict matching the exact shape expected by the dashboard JS.
    """
    db = col.db
    offset_s = analyzer.get_rollover_offset(col)
    start_ms, end_ms = analyzer.get_time_range(period, custom_start_ms, custom_end_ms)

    # --- Contribution heatmap: always fetch 1 year for the calendar view ---
    now_ms = int(__import__('time').time() * 1000)
    contrib_start = now_ms - 365 * 86_400_000
    contrib_raw = analyzer.get_contribution_heatmap(db, contrib_start, now_ms, offset_s)
    contribution_heatmap = _build_contribution_heatmap(contrib_raw, contrib_start, now_ms)

    # --- Raw data extraction ---
    reviews = analyzer.get_reviews(db, start_ms, end_ms)
    all_review_days = analyzer.get_all_review_days(db, start_ms, end_ms, offset_s)
    daily_stats = analyzer.get_daily_review_stats(db, start_ms, end_ms, offset_s)
    hourly_data = analyzer.get_reviews_by_hour(db, start_ms, end_ms)
    heatmap_raw = analyzer.get_heatmap_data(db, start_ms, end_ms)
    retention_by_ivl = analyzer.get_retention_by_interval(db, start_ms, end_ms)
    review_timestamps = analyzer.get_review_timestamps(db, start_ms, end_ms)
    lapses_by_deck = analyzer.get_lapses_by_deck(db, start_ms, end_ms)
    velocity_data = analyzer.get_learning_velocity(db, start_ms, end_ms, offset_s)
    topic_raw = analyzer.get_topic_performance(db, start_ms, end_ms)
    tag_raw = analyzer.get_tag_performance(db, start_ms, end_ms)
    weekly_data = analyzer.get_weekly_metrics(db, start_ms, end_ms, offset_s)
    mature_stats = analyzer.get_mature_card_stats(db)
    deck_names = analyzer.get_deck_names(col)
    mature_correct, mature_total = analyzer.get_mature_retention(db, start_ms, end_ms)

    # --- Computed metrics ---
    # Day values from rollover-aware queries are epoch seconds at start-of-day
    start_day = all_review_days[0] if all_review_days else (start_ms // 1000)
    end_day = all_review_days[-1] if all_review_days else (end_ms // 1000)

    retention = metrics.compute_retention(reviews)
    consistency = metrics.compute_consistency(all_review_days, start_day, end_day)
    efficiency = metrics.compute_efficiency(reviews)
    usage_trends = metrics.compute_usage_trends(daily_stats, start_ms, end_ms, period)
    time_of_day = metrics.compute_time_of_day(hourly_data)
    sessions = metrics.compute_sessions(review_timestamps)
    heatmap = metrics.compute_heatmap(heatmap_raw)
    ret_by_interval = metrics.compute_retention_by_interval(retention_by_ivl)
    lapse_analysis = metrics.compute_lapse_analysis(reviews, lapses_by_deck, deck_names)
    mature_card_stats = metrics.compute_mature_retention(mature_correct, mature_total, mature_stats)
    learning_velocity = metrics.compute_learning_velocity(velocity_data, reviews, start_ms, end_ms)
    topics = metrics.compute_topic_performance(topic_raw, deck_names)
    tags = metrics.compute_tag_performance(tag_raw)
    metrics_over_time = metrics.compute_metrics_over_time(weekly_data)

    # --- Student info ---
    student = _build_student_info(col, all_review_days)

    # --- Activity summary ---
    activity = {
        "daysActive": consistency["daysActive"],
        "longestStreak": consistency["longestStreak"],
        "avgStreak": consistency["avgStreak"],
        "currentStreak": consistency["currentStreak"],
    }

    # --- Score distributions (placeholders for peer comparison) ---
    scores = _build_scores(retention, consistency, efficiency)

    # --- Cohort comparison (placeholders — use own values) ---
    cohort = _build_cohort_placeholder(usage_trends)

    return {
        "student": student,
        "contributionHeatmap": contribution_heatmap,
        "activity": activity,
        "scores": scores,
        "usageTrends": usage_trends,
        "cohort": cohort,
        "timeOfDay": time_of_day,
        "topics": topics,
        "tagPerformance": tags,
        "metricsOverTime": metrics_over_time,
        "sessionAnalysis": sessions,
        "weeklyHeatmap": heatmap,
        "retentionByInterval": ret_by_interval,
        "lapseAnalysis": lapse_analysis,
        "matureCardStats": mature_card_stats,
        "learningVelocity": learning_velocity,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_student_info(col, all_review_days: list[int]) -> dict:
    """Build student info from Anki profile."""
    from aqt import mw

    name = "Anki User"
    if mw and mw.pm:
        name = mw.pm.name or "Anki User"

    initials = "".join(w[0].upper() for w in name.split()[:2]) if name else "AU"

    last_used = "Never"
    if all_review_days:
        last_day = max(all_review_days)
        # Day values are epoch seconds (local start-of-day)
        last_date = datetime.fromtimestamp(last_day)
        last_used = last_date.strftime("%b %d, %Y")

    return {
        "name": name,
        "email": "",
        "cohort": "",
        "initials": initials,
        "status": "Active",
        "lastUsed": last_used,
    }


def _build_scores(retention: dict, consistency: dict, efficiency: dict) -> dict:
    """Build score section with placeholder peer comparison."""
    def _score_block(value: float) -> dict:
        return {
            "value": value,
            "percentile": 50,  # Placeholder
            "cohortAvg": value,  # Use own value as placeholder
            "distribution": {
                "min": max(value - 25, 0),
                "avg": value,
                "max": min(value + 25, 100),
                "studentPos": value,
            },
        }

    return {
        "retention": _score_block(retention["value"]),
        "consistency": _score_block(consistency["value"]),
        "efficiency": _score_block(efficiency["value"]),
    }


def _build_cohort_placeholder(usage_trends: dict) -> dict:
    """Build cohort comparison with placeholder values."""
    avg_dur = usage_trends["duration"]["avg"]
    avg_cards = usage_trends["cardsReviewed"]["avg"]
    avg_spc = usage_trends["secondsPerCard"]["avg"]

    def _cohort_block(value) -> dict:
        v = float(value)
        return {
            "value": v,
            "cohortAvg": v,  # Placeholder
            "percentile": 50,
            "min": max(v * 0.3, 0),
            "avg": v,
            "max": v * 2.5,
        }

    return {
        "avgDuration": _cohort_block(avg_dur),
        "avgCards": _cohort_block(avg_cards),
        "secPerCard": _cohort_block(avg_spc),
    }


def _build_contribution_heatmap(contrib_raw: list[tuple], start_ms: int, end_ms: int) -> dict:
    """Build GitHub-style contribution calendar data.

    contrib_raw rows are (day_epoch_seconds, count) where day_epoch_seconds
    is the Unix timestamp at local start-of-day (rollover-adjusted), as
    produced by the rollover-aware SQL expression in analyzer.py.

    Returns a list of {date, count} objects for every calendar day in the
    range, plus summary stats.
    """
    import time as _time

    # Build lookup: epoch-seconds-at-start-of-day → count
    day_counts: dict[int, int] = {}
    for day_epoch, cnt in contrib_raw:
        day_counts[day_epoch] = cnt

    # Generate every calendar day in the range using local dates
    # (this avoids UTC-vs-local drift for the grid itself)
    start_date = datetime.fromtimestamp(start_ms / 1000).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_date = datetime.fromtimestamp(end_ms / 1000).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    from datetime import timedelta
    days = []
    total_reviews = 0
    active_days = 0
    current = start_date

    while current <= end_date:
        iso = current.strftime("%Y-%m-%d")
        # Midnight epoch seconds for this local date
        local_epoch = int(current.timestamp())
        count = day_counts.get(local_epoch, 0)
        days.append({
            "date": iso,
            "count": count,
            "dow": current.weekday(),  # 0=Mon, 6=Sun
        })
        total_reviews += count
        if count > 0:
            active_days += 1
        current += timedelta(days=1)

    return {
        "days": days,
        "totalReviews": total_reviews,
        "activeDays": active_days,
        "totalDays": len(days),
    }
