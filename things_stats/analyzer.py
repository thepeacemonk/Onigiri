"""
Studylytics — SQL data extraction from Anki's SQLite database.

All time parameters are epoch milliseconds (matching revlog.id).

Day boundaries honour Anki's "next day starts at" rollover hour
(default 4 AM local time).  Every query that groups by calendar day
uses the same SQL expression the official Review Heatmap add-on does:

    CAST(STRFTIME('%s', id/1000 - {offset_s}, 'unixepoch',
                  'localtime', 'start of day') AS int) AS day

where {offset_s} = rollover_hour * 3600.  This guarantees our per-day
counts match the user's Anki experience exactly.
"""

import time
import math
import datetime


# ---------------------------------------------------------------------------
# Rollover / day-boundary helpers
# ---------------------------------------------------------------------------

def get_rollover_offset(col) -> int:
    """Return the rollover offset in seconds.

    Anki v2 scheduler stores 'rollover' in collection conf (default 4).
    Older scheduler derives it from the collection creation timestamp.
    """
    try:
        rollover = col.conf.get("rollover", 4)
    except Exception:
        try:
            crt = col.crt
            start_date = datetime.datetime.fromtimestamp(crt)
            rollover = start_date.hour
        except Exception:
            rollover = 4
    return int(rollover) * 3600


_DAY_SQL = (
    "CAST(STRFTIME('%s', id/1000 - {offset}, 'unixepoch', "
    "'localtime', 'start of day') AS int)"
)


def _day_expr(offset_s: int) -> str:
    """Return the SQL expression that maps a revlog.id to a day integer
    (Unix epoch seconds at start-of-day, local time, rollover-adjusted)."""
    return _DAY_SQL.format(offset=offset_s)


# ---------------------------------------------------------------------------
# Time-range helpers
# ---------------------------------------------------------------------------

def get_time_range(
    period: str,
    custom_start_ms: int = 0,
    custom_end_ms: int = 0,
) -> tuple[int, int]:
    """Convert a period string to (start_ms, end_ms) epoch milliseconds."""
    now_ms = int(time.time() * 1000)
    if period == "custom" and custom_start_ms and custom_end_ms:
        return (custom_start_ms, custom_end_ms)
    if period == "all":
        return (0, now_ms)
    days_map = {
        "1d": 1,
        "today": 1,
        "7d": 7,
        "30d": 30,
        "90d": 90,
        "12m": 365,
    }
    days = days_map.get(period, 30)
    start_ms = now_ms - days * 86_400_000
    return (start_ms, now_ms)


# ---------------------------------------------------------------------------
# Raw review data
# ---------------------------------------------------------------------------

def get_reviews(db, start_ms: int, end_ms: int) -> list[tuple]:
    """All revlog rows in the time range.

    Returns list of (id, cid, ease, ivl, lastIvl, factor, time, type).
    """
    return db.all(
        "SELECT id, cid, ease, ivl, lastIvl, factor, time, type "
        "FROM revlog WHERE id BETWEEN ? AND ? ORDER BY id",
        start_ms,
        end_ms,
    )


def get_all_review_days(db, start_ms: int, end_ms: int, offset_s: int = 0) -> list[int]:
    """Sorted list of distinct study day-numbers in time range.

    Uses rollover-adjusted local day boundaries so days match Anki's
    own "day starts at" setting.
    """
    day = _day_expr(offset_s)
    rows = db.all(
        f"SELECT DISTINCT {day} AS day FROM revlog "
        "WHERE id BETWEEN ? AND ? ORDER BY day",
        start_ms,
        end_ms,
    )
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Aggregated queries
# ---------------------------------------------------------------------------

def get_daily_review_stats(db, start_ms: int, end_ms: int, offset_s: int = 0) -> list[tuple]:
    """(day_number, review_count, total_time_ms) grouped by day."""
    day = _day_expr(offset_s)
    return db.all(
        f"SELECT {day} AS day, COUNT(*) AS cnt, SUM(time) AS total_time "
        "FROM revlog WHERE id BETWEEN ? AND ? GROUP BY day ORDER BY day",
        start_ms,
        end_ms,
    )


def get_reviews_by_hour(db, start_ms: int, end_ms: int) -> list[tuple]:
    """(hour, count, correct_count, total_time_ms) grouped by local hour of day."""
    return db.all(
        "SELECT CAST(strftime('%H', id/1000, 'unixepoch', 'localtime') AS int) AS hour, "
        "COUNT(*) AS cnt, "
        "SUM(CASE WHEN ease >= 2 THEN 1 ELSE 0 END) AS correct, "
        "SUM(time) AS total_time "
        "FROM revlog WHERE id BETWEEN ? AND ? GROUP BY hour ORDER BY hour",
        start_ms,
        end_ms,
    )


def get_heatmap_data(db, start_ms: int, end_ms: int) -> list[tuple]:
    """(day_of_week, hour, count) for the 7×24 heatmap.

    SQLite strftime %w: 0 = Sunday.
    """
    return db.all(
        "SELECT CAST(strftime('%w', id/1000, 'unixepoch', 'localtime') AS int) AS dow, "
        "CAST(strftime('%H', id/1000, 'unixepoch', 'localtime') AS int) AS hour, "
        "COUNT(*) AS cnt "
        "FROM revlog WHERE id BETWEEN ? AND ? GROUP BY dow, hour",
        start_ms,
        end_ms,
    )


def get_retention_by_interval(db, start_ms: int, end_ms: int) -> list[tuple]:
    """Per-interval-bucket retention for mature reviews.

    Returns (bucket_label, total, correct) for predefined interval ranges.
    """
    buckets = [
        ("1d", 0, 1),
        ("3d", 2, 3),
        ("7d", 4, 7),
        ("14d", 8, 14),
        ("30d", 15, 30),
        ("60d", 31, 60),
        ("90d", 61, 90),
        ("180d", 91, 180),
        ("365d", 181, 365),
    ]
    results = []
    for label, lo, hi in buckets:
        row = db.first(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN ease >= 2 THEN 1 ELSE 0 END) AS correct "
            "FROM revlog WHERE id BETWEEN ? AND ? AND type = 1 "
            "AND lastIvl >= ? AND lastIvl <= ?",
            start_ms,
            end_ms,
            lo,
            hi,
        )
        if row and row[0] > 0:
            results.append((label, row[0], row[1]))
    return results


def get_review_timestamps(db, start_ms: int, end_ms: int) -> list[tuple]:
    """(review_epoch_ms, answer_time_ms) for session detection."""
    return db.all(
        "SELECT id, time FROM revlog WHERE id BETWEEN ? AND ? ORDER BY id",
        start_ms,
        end_ms,
    )


def get_lapses_by_deck(db, start_ms: int, end_ms: int) -> list[tuple]:
    """(deck_id, lapse_count) for reviews where ease=1 and type=1."""
    return db.all(
        "SELECT c.did, COUNT(*) AS lapses "
        "FROM revlog r JOIN cards c ON r.cid = c.id "
        "WHERE r.id BETWEEN ? AND ? AND r.ease = 1 AND r.type = 1 "
        "GROUP BY c.did ORDER BY lapses DESC",
        start_ms,
        end_ms,
    )


def get_learning_velocity(db, start_ms: int, end_ms: int, offset_s: int = 0) -> list[tuple]:
    """(week_number, new_card_count) — new cards introduced per week.

    type=0 in revlog means a learning step (first introduction).
    """
    day = _day_expr(offset_s)
    return db.all(
        f"SELECT ({day} / 86400 / 7) AS week, COUNT(*) AS cnt "
        "FROM revlog WHERE id BETWEEN ? AND ? AND type = 0 "
        "GROUP BY week ORDER BY week",
        start_ms,
        end_ms,
    )


def get_topic_performance(db, start_ms: int, end_ms: int) -> list[tuple]:
    """(deck_id, total_reviews, correct, total_time_ms) per deck."""
    return db.all(
        "SELECT c.did, COUNT(*) AS total, "
        "SUM(CASE WHEN r.ease >= 2 THEN 1 ELSE 0 END) AS correct, "
        "SUM(r.time) AS total_time "
        "FROM revlog r JOIN cards c ON r.cid = c.id "
        "WHERE r.id BETWEEN ? AND ? "
        "GROUP BY c.did ORDER BY total DESC",
        start_ms,
        end_ms,
    )


def get_tag_performance(db, start_ms: int, end_ms: int) -> list[tuple]:
    """(note_id, tags_string, ease, time_ms) for tag-level performance.

    Returns per-review rows with the note's tags so we can aggregate
    in Python (SQL can't split space-separated tags).
    """
    return db.all(
        "SELECT n.tags, r.ease, r.time "
        "FROM revlog r "
        "JOIN cards c ON r.cid = c.id "
        "JOIN notes n ON c.nid = n.id "
        "WHERE r.id BETWEEN ? AND ?",
        start_ms,
        end_ms,
    )


def get_weekly_metrics(db, start_ms: int, end_ms: int, offset_s: int = 0) -> list[tuple]:
    """(week_number, total, correct, total_time_ms, active_days) per week."""
    day = _day_expr(offset_s)
    return db.all(
        f"SELECT ({day} / 86400 / 7) AS week, "
        "COUNT(*) AS total, "
        "SUM(CASE WHEN ease >= 2 THEN 1 ELSE 0 END) AS correct, "
        "SUM(time) AS total_time, "
        f"COUNT(DISTINCT {day}) AS active_days "
        "FROM revlog WHERE id BETWEEN ? AND ? GROUP BY week ORDER BY week",
        start_ms,
        end_ms,
    )


# ---------------------------------------------------------------------------
# Card / deck helpers
# ---------------------------------------------------------------------------

def get_card_counts(db) -> dict:
    """Card counts by queue type."""
    rows = db.all("SELECT type, COUNT(*) FROM cards GROUP BY type")
    mapping = {0: "new", 1: "learning", 2: "review", 3: "relearning"}
    result = {"new": 0, "learning": 0, "review": 0, "relearning": 0}
    for t, cnt in rows:
        key = mapping.get(t, "new")
        result[key] = cnt
    return result


def get_mature_card_stats(db) -> dict:
    """Stats for mature cards (type=2 AND ivl >= 21)."""
    row = db.first(
        "SELECT COUNT(*), AVG(ivl), MAX(ivl) "
        "FROM cards WHERE type = 2 AND ivl >= 21"
    )
    if row and row[0]:
        return {
            "totalMature": row[0],
            "avgInterval": round(row[1], 1),
            "longestInterval": row[2],
        }
    return {"totalMature": 0, "avgInterval": 0, "longestInterval": 0}


def get_deck_names(col) -> dict:
    """Return {deck_id: full_deck_name} mapping."""
    result = {}
    for entry in col.decks.all_names_and_ids():
        result[entry.id] = entry.name
    return result


def get_contribution_heatmap(db, start_ms: int, end_ms: int, offset_s: int = 0) -> list[tuple]:
    """(day_epoch_seconds, review_count) for contribution heatmap.

    day values are Unix epoch seconds at local start-of-day, rollover-adjusted.
    """
    day = _day_expr(offset_s)
    return db.all(
        f"SELECT {day} AS day, COUNT(*) AS cnt "
        "FROM revlog WHERE id BETWEEN ? AND ? GROUP BY day ORDER BY day",
        start_ms,
        end_ms,
    )


def get_total_review_count(db, start_ms: int, end_ms: int) -> int:
    """Total number of reviews in the time range."""
    row = db.first(
        "SELECT COUNT(*) FROM revlog WHERE id BETWEEN ? AND ?",
        start_ms,
        end_ms,
    )
    return row[0] if row else 0


def get_mature_retention(db, start_ms: int, end_ms: int) -> tuple[int, int]:
    """(correct, total) for mature review cards in the time range."""
    row = db.first(
        "SELECT COUNT(*), SUM(CASE WHEN ease >= 2 THEN 1 ELSE 0 END) "
        "FROM revlog WHERE id BETWEEN ? AND ? AND type = 1 AND lastIvl >= 21",
        start_ms,
        end_ms,
    )
    if row and row[0]:
        return (row[1], row[0])
    return (0, 0)
