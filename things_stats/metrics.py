"""
Studylytics — Pure computation functions.

Each function takes raw data (lists/tuples from analyzer.py) and returns
dicts matching the JSON shape expected by the dashboard JS.
No database access in this module.
"""

import math
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Core scores
# ---------------------------------------------------------------------------

def compute_retention(reviews: list[tuple]) -> dict:
    """Retention rate from mature reviews.

    A review is "mature" if type == 1 (review) and lastIvl >= 21.
    Correct = ease >= 2.
    """
    total = 0
    correct = 0
    for _id, _cid, ease, _ivl, lastIvl, _factor, _time, rtype in reviews:
        if rtype == 1 and lastIvl >= 21:
            total += 1
            if ease >= 2:
                correct += 1
    value = round((correct / total) * 100, 1) if total > 0 else 0.0
    return {"value": value, "total": total, "correct": correct}


def compute_consistency(all_review_days: list[int], start_day: int, end_day: int) -> dict:
    """Consistency score: percentage of days studied in the range.

    Day values are epoch seconds at local start-of-day (rollover-adjusted).
    One calendar day = 86400 seconds apart.

    Also computes current streak, longest streak, and average streak
    within the selected time range.
    """
    ONE_DAY = 86400  # seconds
    # Convert to day indices for easier streak math
    days_in_range = sorted(set(all_review_days))

    if days_in_range and start_day and end_day:
        total_days = max((end_day - start_day) // ONE_DAY + 1, 1)
    elif days_in_range:
        total_days = max((days_in_range[-1] - days_in_range[0]) // ONE_DAY + 1, 1)
    else:
        total_days = 1

    days_active = len(days_in_range)
    value = round(min((days_active / total_days) * 100, 100), 1)

    # Streak calculations within the selected time range
    streaks = []
    current_streak = 0
    if days_in_range:
        streak_len = 1
        for i in range(1, len(days_in_range)):
            diff = days_in_range[i] - days_in_range[i - 1]
            if diff == ONE_DAY:
                streak_len += 1
            else:
                streaks.append(streak_len)
                streak_len = 1
        streaks.append(streak_len)

        # Current streak: count backwards from end_day (or last active day)
        current_streak = 0
        ref_day = end_day if end_day else days_in_range[-1]
        for d in reversed(days_in_range):
            if d == ref_day - current_streak * ONE_DAY:
                current_streak += 1
            else:
                break

    longest = max(streaks) if streaks else 0
    avg = round(sum(streaks) / len(streaks), 1) if streaks else 0

    return {
        "value": value,
        "daysActive": days_active,
        "totalDays": total_days,
        "currentStreak": current_streak,
        "longestStreak": longest,
        "avgStreak": avg,
    }


def compute_efficiency(reviews: list[tuple]) -> dict:
    """Efficiency score combining accuracy and speed.

    Formula: (accuracy * 0.6 + speed_factor * 0.4) * 100
    speed_factor = min(15 / avg_time_sec, 1.0)
    Answer time capped at 60s to avoid outlier skew.
    """
    if not reviews:
        return {"value": 0.0, "avgTimePerCard": 0.0, "accuracy": 0.0}

    total = 0
    correct = 0
    total_time_ms = 0
    for _id, _cid, ease, _ivl, _lastIvl, _factor, answer_time, _rtype in reviews:
        total += 1
        if ease >= 2:
            correct += 1
        # Cap at 60 seconds
        total_time_ms += min(answer_time, 60000)

    accuracy = correct / total if total > 0 else 0
    avg_time_sec = (total_time_ms / total / 1000) if total > 0 else 60
    speed_factor = min(15.0 / max(avg_time_sec, 1), 1.0)
    value = round((accuracy * 0.6 + speed_factor * 0.4) * 100, 1)

    return {
        "value": value,
        "avgTimePerCard": round(avg_time_sec, 1),
        "accuracy": round(accuracy * 100, 1),
    }


# ---------------------------------------------------------------------------
# Usage trends
# ---------------------------------------------------------------------------

def compute_usage_trends(daily_stats: list[tuple], start_ms: int, end_ms: int, period: str) -> dict:
    """Build usage trend arrays (labels, duration, cardsReviewed, secondsPerCard).

    Daily granularity for periods <= 30d, weekly for longer.
    """
    if not daily_stats:
        return {
            "labels": [],
            "duration": {"avg": 0, "data": []},
            "cardsReviewed": {"avg": 0, "data": []},
            "secondsPerCard": {"avg": 0, "data": []},
        }

    # Use weekly granularity for ranges over 30 days (covers custom ranges too)
    span_days = (end_ms - start_ms) / 86_400_000
    use_weekly = span_days > 30

    if use_weekly:
        # Group by week (day values are epoch seconds)
        weekly: dict[int, dict] = {}
        for day_epoch, cnt, total_time in daily_stats:
            week = day_epoch // (86400 * 7)
            if week not in weekly:
                weekly[week] = {"cnt": 0, "time": 0, "first_epoch": day_epoch}
            weekly[week]["cnt"] += cnt
            weekly[week]["time"] += total_time

        sorted_weeks = sorted(weekly.keys())
        labels = []
        durations = []
        cards = []
        spc = []
        for w in sorted_weeks:
            # Use the first day in the week for the label
            d = datetime.fromtimestamp(weekly[w]["first_epoch"])
            labels.append(d.strftime("%b %d"))
            mins = round(weekly[w]["time"] / 60000, 1)
            durations.append(mins)
            cards.append(weekly[w]["cnt"])
            avg_sec = round(weekly[w]["time"] / max(weekly[w]["cnt"], 1) / 1000, 1)
            spc.append(avg_sec)
    else:
        labels = []
        durations = []
        cards = []
        spc = []
        for day_epoch, cnt, total_time in daily_stats:
            # day_epoch is Unix epoch seconds at local start-of-day
            d = datetime.fromtimestamp(day_epoch)
            labels.append(d.strftime("%b %d"))
            mins = round(total_time / 60000, 1)
            durations.append(mins)
            cards.append(cnt)
            avg_sec = round(total_time / max(cnt, 1) / 1000, 1)
            spc.append(avg_sec)

    avg_dur = round(sum(durations) / len(durations), 1) if durations else 0
    avg_cards = round(sum(cards) / len(cards)) if cards else 0
    avg_spc = round(sum(spc) / len(spc), 1) if spc else 0

    return {
        "labels": labels,
        "duration": {"avg": avg_dur, "data": durations},
        "cardsReviewed": {"avg": avg_cards, "data": cards},
        "secondsPerCard": {"avg": avg_spc, "data": spc},
    }


# ---------------------------------------------------------------------------
# Time of day
# ---------------------------------------------------------------------------

def compute_time_of_day(hourly_data: list[tuple]) -> list[dict]:
    """Aggregate hourly data into 4 time-of-day buckets."""
    buckets = {
        "Morning": {"range": "6 AM - 12 PM", "icon": "morning", "hours": range(6, 12)},
        "Afternoon": {"range": "12 PM - 6 PM", "icon": "afternoon", "hours": range(12, 18)},
        "Evening": {"range": "6 PM - 12 AM", "icon": "evening", "hours": range(18, 24)},
        "Night": {"range": "12 AM - 6 AM", "icon": "night", "hours": range(0, 6)},
    }
    totals = {name: {"cnt": 0, "correct": 0, "time": 0} for name in buckets}

    for hour, cnt, correct, total_time in hourly_data:
        for name, info in buckets.items():
            if hour in info["hours"]:
                totals[name]["cnt"] += cnt
                totals[name]["correct"] += correct
                totals[name]["time"] += total_time
                break

    grand_total = sum(t["cnt"] for t in totals.values())
    result = []
    for name in ["Morning", "Afternoon", "Evening", "Night"]:
        info = buckets[name]
        t = totals[name]
        pct = round(t["cnt"] / grand_total * 100) if grand_total > 0 else 0
        retention = round(t["correct"] / t["cnt"] * 100, 1) if t["cnt"] > 0 else 0
        avg_time = t["time"] / max(t["cnt"], 1) / 1000  # seconds
        speed_factor = min(15.0 / max(avg_time, 1), 1.0)
        accuracy = t["correct"] / max(t["cnt"], 1)
        efficiency = round((accuracy * 0.6 + speed_factor * 0.4) * 100, 1)
        result.append({
            "period": name,
            "range": info["range"],
            "icon": info["icon"],
            "pct": pct,
            "retention": retention,
            "efficiency": efficiency,
        })
    return result


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def compute_sessions(review_timestamps: list[tuple]) -> dict:
    """Detect study sessions (30min gap = new session)."""
    if not review_timestamps:
        return {
            "avgSessionLength": 0,
            "medianSessionLength": 0,
            "sessionsPerDay": 0,
            "optimalSessionLength": "N/A",
            "distribution": [
                {"range": "0-15 min", "pct": 0},
                {"range": "15-30 min", "pct": 0},
                {"range": "30-45 min", "pct": 0},
                {"range": "45-60 min", "pct": 0},
                {"range": "60+ min", "pct": 0},
            ],
        }

    SESSION_GAP_MS = 30 * 60 * 1000  # 30 minutes
    sessions = []
    session_start = review_timestamps[0][0]
    session_end = review_timestamps[0][0]

    for ts, answer_time in review_timestamps[1:]:
        if ts - session_end > SESSION_GAP_MS:
            length_min = (session_end - session_start) / 60000
            sessions.append(length_min)
            session_start = ts
        session_end = ts

    # Last session
    length_min = (session_end - session_start) / 60000
    sessions.append(length_min)

    if not sessions:
        sessions = [0]

    avg_len = round(sum(sessions) / len(sessions))
    sorted_sessions = sorted(sessions)
    median_len = round(sorted_sessions[len(sorted_sessions) // 2])

    # Sessions per day
    days = set()
    for ts, _ in review_timestamps:
        days.add(ts // 86_400_000)
    sessions_per_day = round(len(sessions) / max(len(days), 1), 1)

    # Distribution buckets
    dist_buckets = [0, 0, 0, 0, 0]  # 0-15, 15-30, 30-45, 45-60, 60+
    for s in sessions:
        if s < 15:
            dist_buckets[0] += 1
        elif s < 30:
            dist_buckets[1] += 1
        elif s < 45:
            dist_buckets[2] += 1
        elif s < 60:
            dist_buckets[3] += 1
        else:
            dist_buckets[4] += 1
    total = len(sessions)
    distribution = [
        {"range": "0-15 min", "pct": round(dist_buckets[0] / total * 100)},
        {"range": "15-30 min", "pct": round(dist_buckets[1] / total * 100)},
        {"range": "30-45 min", "pct": round(dist_buckets[2] / total * 100)},
        {"range": "45-60 min", "pct": round(dist_buckets[3] / total * 100)},
        {"range": "60+ min", "pct": round(dist_buckets[4] / total * 100)},
    ]

    # Optimal session range: bucket with highest retention isn't available here,
    # so just report mode range
    mode_idx = dist_buckets.index(max(dist_buckets))
    ranges = ["0-15 min", "15-30 min", "25-35 min", "35-50 min", "45-60 min"]
    optimal = ranges[min(mode_idx, len(ranges) - 1)]

    return {
        "avgSessionLength": avg_len,
        "medianSessionLength": median_len,
        "sessionsPerDay": sessions_per_day,
        "optimalSessionLength": optimal,
        "distribution": distribution,
    }


# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------

def compute_heatmap(heatmap_raw: list[tuple]) -> dict:
    """Build 7×24 heatmap matrix.

    SQLite dow: 0=Sun. Dashboard expects Mon=0.
    Remap: Mon=0, Tue=1, ... Sun=6.
    """
    data = [[0] * 24 for _ in range(7)]
    # SQLite: 0=Sun, 1=Mon, ..., 6=Sat
    # Dashboard: 0=Mon, 1=Tue, ..., 6=Sun
    remap = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 0: 6}

    for dow, hour, cnt in heatmap_raw:
        mapped = remap.get(dow, 0)
        if 0 <= hour < 24:
            data[mapped][hour] = cnt

    return {
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "hours": list(range(24)),
        "data": data,
    }


# ---------------------------------------------------------------------------
# Retention by interval
# ---------------------------------------------------------------------------

def compute_retention_by_interval(retention_data: list[tuple]) -> dict:
    """Format interval-bucketed retention with placeholder cohort averages."""
    if not retention_data:
        return {"labels": [], "retention": [], "cohortAvg": []}
    labels = []
    retention = []
    cohort_avg = []
    for label, total, correct in retention_data:
        labels.append(label)
        rate = round(correct / total * 100, 1) if total > 0 else 0
        retention.append(rate)
        # Placeholder: cohort avg = user's own rate (no server yet)
        cohort_avg.append(rate)
    return {"labels": labels, "retention": retention, "cohortAvg": cohort_avg}


# ---------------------------------------------------------------------------
# Lapse analysis
# ---------------------------------------------------------------------------

def compute_lapse_analysis(reviews: list[tuple], lapses_by_deck: list[tuple],
                           deck_names: dict) -> dict:
    """Total lapses, lapse rate, and top 5 lapse topics."""
    total_reviews = len(reviews)
    total_lapses = sum(cnt for _, cnt in lapses_by_deck)
    lapse_rate = round(total_lapses / total_reviews * 100, 1) if total_reviews > 0 else 0

    topics = []
    for did, cnt in lapses_by_deck[:5]:
        name = deck_names.get(did, f"Deck {did}")
        # Use the leaf name of the deck hierarchy
        short_name = name.split("::")[-1] if "::" in name else name
        pct = round(cnt / max(total_lapses, 1) * 100, 1)
        topics.append({"topic": short_name, "lapses": cnt, "pct": pct})

    return {
        "totalLapses": total_lapses,
        "lapseRate": lapse_rate,
        "commonLapseTopics": topics,
    }


# ---------------------------------------------------------------------------
# Mature card stats
# ---------------------------------------------------------------------------

def compute_mature_retention(correct: int, total: int, mature_stats: dict) -> dict:
    """Combine mature card DB stats with retention from reviews."""
    retention = round(correct / total * 100, 1) if total > 0 else 0
    return {
        "totalMature": mature_stats.get("totalMature", 0),
        "matureRetention": retention,
        "avgInterval": mature_stats.get("avgInterval", 0),
        "longestInterval": mature_stats.get("longestInterval", 0),
    }


# ---------------------------------------------------------------------------
# Learning velocity
# ---------------------------------------------------------------------------

def compute_learning_velocity(velocity_data: list[tuple], reviews: list[tuple],
                              start_ms: int, end_ms: int) -> dict:
    """New cards/day, graduation rate, avg time to graduate."""
    total_days = max((end_ms - start_ms) / 86_400_000, 1)

    total_new = sum(cnt for _, cnt in velocity_data)
    new_per_day = round(total_new / total_days, 1)

    # Graduation: cards that went from learning (type=0) to having ivl > 0
    # Approximation: count reviews with type=0 that eventually have ivl >= 1
    learn_reviews = [r for r in reviews if r[7] == 0]  # type=0
    graduated = [r for r in reviews if r[7] == 1 and r[4] == 0]  # first review after learning
    grad_rate = round(len(graduated) / max(len(learn_reviews), 1) * 100) if learn_reviews else 0

    # Avg time to graduate: hard to compute precisely, estimate from data
    avg_time_to_grad = 0
    if velocity_data and total_new > 0:
        # Rough estimate: total learning time / new cards
        learn_time = sum(min(r[6], 60000) for r in reviews if r[7] == 0)
        avg_time_to_grad = round(learn_time / max(total_new, 1) / 1000 / 60, 1)  # minutes

    labels = []
    velocity = []
    for week, cnt in velocity_data:
        # week = (day_epoch_seconds / 86400 / 7); recover epoch seconds
        try:
            d = datetime.fromtimestamp(week * 7 * 86400)
            labels.append(d.strftime("W%U"))
        except (OSError, ValueError):
            labels.append(f"W{week}")
        velocity.append(cnt)

    # Trim to last 12 weeks max
    if len(labels) > 12:
        labels = labels[-12:]
        velocity = velocity[-12:]

    return {
        "newCardsPerDay": new_per_day,
        "graduationRate": min(grad_rate, 100),
        "avgTimeToGraduate": avg_time_to_grad,
        "labels": labels,
        "velocity": velocity,
    }


# ---------------------------------------------------------------------------
# Topic performance
# ---------------------------------------------------------------------------

def compute_tag_performance(tag_rows: list[tuple]) -> list[dict]:
    """Per-tag retention and efficiency, organized hierarchically.

    Each row is (tags_string, ease, time_ms).
    Tags are space-separated on the notes table.  We aggregate per
    full tag path, then group leaf tags under their parent category.

    Returns a list of group dicts:
      { "category": "Biology", "fullCategory": "..::Biology",
        "retention": .., "efficiency": .., "reviews": ..,
        "children": [ { "name": "Cells", ... }, ... ] }
    """
    # Aggregate stats per full tag path
    tag_stats: dict[str, dict] = {}
    for tags_str, ease, answer_time in tag_rows:
        if not tags_str or not tags_str.strip():
            continue
        tags = tags_str.strip().split()
        for tag in tags:
            if tag not in tag_stats:
                tag_stats[tag] = {"total": 0, "correct": 0, "time": 0}
            tag_stats[tag]["total"] += 1
            if ease >= 2:
                tag_stats[tag]["correct"] += 1
            tag_stats[tag]["time"] += min(answer_time, 60000)

    def _calc_metrics(s: dict) -> dict:
        retention = round(s["correct"] / s["total"] * 100, 1)
        avg_time = s["time"] / s["total"] / 1000
        accuracy = s["correct"] / s["total"]
        speed_factor = min(15.0 / max(avg_time, 1), 1.0)
        efficiency = round((accuracy * 0.6 + speed_factor * 0.4) * 100, 1)
        return {"retention": retention, "efficiency": efficiency, "reviews": s["total"]}

    # Find the common prefix depth to skip (e.g., "#AK_MCAT_v2::#KahnAcademy::")
    # by finding the longest shared prefix among all tags with ::
    hierarchical_tags = [t for t in tag_stats if "::" in t and tag_stats[t]["total"] >= 5]

    # Determine how many prefix segments to skip
    skip_depth = 0
    if hierarchical_tags:
        split_tags = [t.split("::") for t in hierarchical_tags]
        min_len = min(len(parts) for parts in split_tags)
        for depth in range(min_len - 1):  # Keep at least 1 segment
            if len(set(parts[depth] for parts in split_tags)) == 1:
                skip_depth = depth + 1
            else:
                break

    # Group tags: category = first meaningful segment, children = rest
    groups: dict[str, dict] = {}
    ungrouped = []

    for tag, s in tag_stats.items():
        if s["total"] < 5:
            continue
        parts = tag.split("::")
        meaningful = parts[skip_depth:]  # Strip common prefix

        if len(meaningful) <= 1:
            # Top-level tag or flat tag — goes into ungrouped
            name = meaningful[0] if meaningful else parts[-1]
            m = _calc_metrics(s)
            ungrouped.append({
                "name": name, "fullTag": tag, **m,
            })
        else:
            category = meaningful[0]
            child_name = "::".join(meaningful[1:])
            leaf_name = meaningful[-1]

            if category not in groups:
                groups[category] = {
                    "category": category,
                    "fullCategory": "::".join(parts[:skip_depth + 1]),
                    "total": 0, "correct": 0, "time": 0,
                    "children": [],
                }

            # Aggregate into category totals
            groups[category]["total"] += s["total"]
            groups[category]["correct"] += s["correct"]
            groups[category]["time"] += s["time"]

            m = _calc_metrics(s)
            groups[category]["children"].append({
                "name": leaf_name,
                "path": child_name,
                "fullTag": tag,
                **m,
            })

    # Build final result
    result = []
    for cat_name, g in sorted(groups.items(), key=lambda x: x[0]):
        cat_metrics = _calc_metrics({"total": g["total"], "correct": g["correct"], "time": g["time"]})
        children = sorted(g["children"], key=lambda c: c["retention"])
        result.append({
            "category": g["category"],
            "fullCategory": g["fullCategory"],
            **cat_metrics,
            "children": children,
        })

    # Sort categories by retention
    result.sort(key=lambda g: g["retention"])

    # Add ungrouped tags as single-item groups
    for item in sorted(ungrouped, key=lambda x: x["retention"]):
        result.append({
            "category": item["name"],
            "fullCategory": item["fullTag"],
            **{k: item[k] for k in ("retention", "efficiency", "reviews")},
            "children": [],
        })

    return result


def compute_topic_performance(topic_raw: list[tuple], deck_names: dict) -> list[dict]:
    """Per-deck retention and efficiency, sorted by retention ascending."""
    topics = []
    for did, total, correct, total_time in topic_raw:
        if total < 5:
            continue  # Skip decks with very few reviews
        name = deck_names.get(did, f"Deck {did}")
        short_name = name.split("::")[-1] if "::" in name else name
        retention = round(correct / total * 100, 1)
        avg_time = total_time / max(total, 1) / 1000
        accuracy = correct / max(total, 1)
        speed_factor = min(15.0 / max(avg_time, 1), 1.0)
        efficiency = round((accuracy * 0.6 + speed_factor * 0.4) * 100, 1)
        topics.append({
            "name": short_name,
            "retention": retention,
            "efficiency": efficiency,
        })
    topics.sort(key=lambda t: t["retention"])
    return topics


# ---------------------------------------------------------------------------
# Metrics over time
# ---------------------------------------------------------------------------

def compute_metrics_over_time(weekly_data: list[tuple]) -> dict:
    """Weekly retention, consistency, and efficiency trend series."""
    labels = []
    retention = []
    consistency = []
    efficiency = []

    for week, total, correct, total_time, active_days in weekly_data:
        try:
            d = datetime.fromtimestamp(week * 7 * 86400)
            labels.append(d.strftime("%b %d"))
        except (OSError, ValueError):
            labels.append(f"W{week}")

        # Retention: correct / total
        ret = round(correct / total * 100, 1) if total > 0 else 0
        retention.append(ret)

        # Consistency: active_days / 7
        cons = round(active_days / 7 * 100, 1)
        consistency.append(cons)

        # Efficiency
        avg_time = total_time / max(total, 1) / 1000
        acc = correct / max(total, 1)
        spd = min(15.0 / max(avg_time, 1), 1.0)
        eff = round((acc * 0.6 + spd * 0.4) * 100, 1)
        efficiency.append(eff)

    # Trim to last 12 weeks
    if len(labels) > 12:
        labels = labels[-12:]
        retention = retention[-12:]
        consistency = consistency[-12:]
        efficiency = efficiency[-12:]

    return {
        "labels": labels,
        "retention": retention,
        "consistency": consistency,
        "efficiency": efficiency,
    }
