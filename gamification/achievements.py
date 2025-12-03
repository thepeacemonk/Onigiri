import calendar
import copy
import json
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from aqt import gui_hooks, mw

from .. import config, heatmap
from .. import config, heatmap

SECONDS_IN_DAY = 86400
ANCIENT_GRAIN_THRESHOLD = 365 * SECONDS_IN_DAY
HOLIDAY_MONTH_DAY = {(1, 1), (12, 25)}


@dataclass(frozen=True)
class AchievementDefinition:
    id: str
    name: str
    description: str
    category: str
    metric: str
    threshold: int = 1
    repeatable: bool = False
    icon: Optional[str] = None


ACHIEVEMENTS: List[AchievementDefinition] = [
    AchievementDefinition("streak_bronze", "The Streak (Bronze)", "Maintain a 3-day streak.", "streak_medals", "max_streak", 3, icon="/_addons/1011095603/system_files/gamification_images/achievements_folder/bronze_onigiri.png"),
    AchievementDefinition("streak_silver", "The Streak (Silver)", "Maintain a 7-day streak.", "streak_medals", "max_streak", 7, icon="/_addons/1011095603/system_files/gamification_images/achievements_folder/silver_onigiri.png"),
    AchievementDefinition("streak_gold", "The Streak (Gold)", "Maintain a 30-day streak.", "streak_medals", "max_streak", 30, icon="/_addons/1011095603/system_files/gamification_images/achievements_folder/gold_onigiri.png"),
    AchievementDefinition("streak_diamond", "The Streak (Diamond)", "Maintain a 100-day streak.", "streak_medals", "max_streak", 100, icon="/_addons/1011095603/system_files/gamification_images/achievements_folder/diamond_onigiri.png"),
    AchievementDefinition("streak_vibranium", "The Streak (Vibranium)", "Maintain a 200-day streak.", "streak_medals", "max_streak", 200, icon="/_addons/1011095603/system_files/gamification_images/achievements_folder/vibranium_onigiri.png"),
    AchievementDefinition("streak_master", "Onigiri Master", "Maintain a 365-day streak.", "streak_medals", "max_streak", 365, icon="/_addons/1011095603/system_files/gamification_images/achievements_folder/golden_onigiri.png"),
    AchievementDefinition("perfect_week", "Perfect Week", "Study all 7 days in a single week.", "perfection", "perfect_week_count", 1, repeatable=True, icon="📆"),
    AchievementDefinition("perfect_month", "Perfect Month", "Study every day for a full calendar month.", "perfection", "perfect_month_count", 1, repeatable=True, icon="🗓️"),
    AchievementDefinition("snack_time", "Snack Time", "Complete 50 reviews in a single day.", "culinary_master", "max_daily_reviews", 50, icon="🥟"),
    AchievementDefinition("full_meal", "Full Meal", "Complete 100 reviews in a single day.", "culinary_master", "max_daily_reviews", 100, icon="🍱"),
    AchievementDefinition("buffet", "The Buffet", "Complete 250 reviews in a single day.", "culinary_master", "max_daily_reviews", 250, icon="🍣"),
    AchievementDefinition("rice_farmer", "Rice Farmer", "Reach 1,000 total reviews.", "culinary_master", "total_reviews", 1_000, icon="🌱"),
    AchievementDefinition("harvest_king", "Harvest King", "Reach 10,000 total reviews.", "culinary_master", "total_reviews", 10_000, icon="👑"),
    AchievementDefinition("shogun", "Shogun", "Reach 50,000 total reviews.", "culinary_master", "total_reviews", 50_000, icon="⚔️"),
    AchievementDefinition("emperor", "Emperor", "Reach 100,000 total reviews.", "culinary_master", "total_reviews", 100_000, icon="👘"),
    AchievementDefinition("new_recipe", "New Recipe", "Add your first new card.", "new_ingredients", "total_new_cards", 1, icon="📗"),
    AchievementDefinition("sous_chef", "Sous Chef", "Learn 20 new cards in a single day.", "new_ingredients", "max_new_cards_day", 20, icon="🍳"),
    AchievementDefinition("head_chef", "Head Chef", "Learn 50 new cards in a single day.", "new_ingredients", "max_new_cards_day", 50, icon="👩‍🍳"),
    AchievementDefinition("first_grain", "First Grain", "Have your first card become mature.", "onigiri_restaurant", "mature_cards", 1, icon="🌿"),
    AchievementDefinition("full_pantry", "Full Pantry", "Reach 100 mature cards.", "onigiri_restaurant", "mature_cards", 100, icon="🧺"),
    AchievementDefinition("rice_stockpile", "Rice Stockpile", "Reach 1,000 mature cards.", "onigiri_restaurant", "mature_cards", 1_000, icon="🥢"),
    AchievementDefinition("world_class_restaurant", "World-Class Restaurant", "Reach 10,000 mature cards.", "onigiri_restaurant", "mature_cards", 10_000, icon="🏯"),
    AchievementDefinition("ancient_grain", "Ancient Grain", "Review a card you haven't seen in over 1 year.", "special_recipes", "ancient_grain_count", 1, icon="📜"),
    AchievementDefinition("holiday_meal", "Holiday Meal", "Study on a major holiday.", "special_recipes", "holiday_days", 1, repeatable=True, icon="🎄"),
    AchievementDefinition("the_onigiri", "The Onigiri", "Thanks for installing the add-on!", "special_recipes", "addon_installed", 1, icon="🍙"),
    AchievementDefinition("deck_collector", "Deck Collector", "Have 10 or more decks in your collection.", "special_recipes", "deck_count", 10, icon="🗂️"),
]

ACHIEVEMENTS_BY_ID = {definition.id: definition for definition in ACHIEVEMENTS}


def _local_datetime(ts_ms: int) -> datetime:
    return datetime.fromtimestamp(ts_ms / 1000)


def _baseline_metrics() -> Dict[str, Any]:
    return {
        "max_streak": 0,
        "perfect_week_count": 0,
        "perfect_month_count": 0,
        "max_daily_reviews": 0,
        "total_reviews": 0,
        "umeboshi_count": 0,
        "ancient_grain_count": 0,
        "holiday_days": 0,
        "total_new_cards": 0,
        "max_new_cards_day": 0,
        "mature_cards": 0,
        "deck_count": 0,
        "addon_installed": 1,
        "today_review_count": 0,
        "current_week_review_count": 0,
        "today_label": "",
        "current_week_label": "",
    }


def _compute_revlog_metrics() -> Dict[str, Any]:
    metrics: Dict[str, Any] = _baseline_metrics()
    if not mw.col or not getattr(mw.col, "db", None):
        return metrics
    day_counts: Dict[str, int] = defaultdict(int)
    week_map: Dict[Tuple[int, int], set] = defaultdict(set)
    week_review_counts: Dict[Tuple[int, int], int] = defaultdict(int)
    month_map: Dict[Tuple[int, int], set] = defaultdict(set)
    days_with_reviews: set = set()

    revlog_rows = mw.col.db.all("SELECT id, cid, ease, time FROM revlog ORDER BY id")
    if not revlog_rows:
        return metrics

    # Get rollover offset to align reviews with Anki days
    rollover_hour = mw.col.conf.get("rollover", 4)
    offset_seconds = rollover_hour * 3600

    card_fail_streak: Dict[int, int] = defaultdict(int)
    card_last_review: Dict[int, float] = {}
    umeboshi_found = False
    ancient_grain_found = False
    holiday_days: set = set()

    for row in revlog_rows:
        ts_ms, cid, ease, time_ms = row
        ts = ts_ms / 1000
        
        # Adjust timestamp by rollover offset
        adjusted_ts = ts - offset_seconds
        dt = datetime.fromtimestamp(adjusted_ts)
        
        day_key = dt.strftime("%Y-%m-%d")
        days_with_reviews.add(day_key)
        day_counts[day_key] += 1
        metrics["total_reviews"] += 1

        if (dt.month, dt.day) in HOLIDAY_MONTH_DAY:
            holiday_days.add(day_key)

        iso_year, iso_week, iso_weekday = dt.isocalendar()
        week_map[(iso_year, iso_week)].add(iso_weekday)
        week_review_counts[(iso_year, iso_week)] += 1
        month_map[(dt.year, dt.month)].add(dt.day)

        if ease == 1:
            card_fail_streak[cid] = card_fail_streak.get(cid, 0) + 1
            if card_fail_streak[cid] >= 5:
                umeboshi_found = True
        else:
            card_fail_streak[cid] = 0

        previous_ts = card_last_review.get(cid)
        if previous_ts is not None and ts - previous_ts > ANCIENT_GRAIN_THRESHOLD:
            ancient_grain_found = True
        card_last_review[cid] = ts

    # Streak calculations
    if days_with_reviews:
        ordered_dates = sorted(datetime.strptime(day, "%Y-%m-%d").date() for day in days_with_reviews)
        max_streak = current_streak = 1
        for prev, curr in zip(ordered_dates, ordered_dates[1:]):
            if (curr - prev).days == 1:
                current_streak += 1
            else:
                max_streak = max(max_streak, current_streak)
                current_streak = 1
        max_streak = max(max_streak, current_streak)
    else:
        max_streak = 0

    perfect_week_count = sum(1 for days in week_map.values() if len(days) == 7)
    perfect_month_count = 0
    for (year, month), days in month_map.items():
        _, month_days = calendar.monthrange(year, month)
        if len(days) == month_days:
            perfect_month_count += 1

    # Get Anki's day cutoff in seconds since epoch
    day_cutoff = mw.col.sched.dayCutoff
    today_start = day_cutoff - 86400  # 24 hours before cutoff (start of today)
    
    # Use Anki's day definition for "now"
    now_dt = datetime.fromtimestamp(today_start)
    today_key = now_dt.strftime("%Y-%m-%d")
    
    # Get the start of the week (Monday) in local time
    week_start = now_dt - timedelta(days=now_dt.weekday())  # Monday
    week_start_ts = int(week_start.timestamp())
    
    # Query for this week's reviews
    week_reviews = 0
    if mw.col and getattr(mw.col, "db", None):
        week_reviews = mw.col.db.scalar(
            "SELECT COUNT() FROM revlog WHERE id >= ?", 
            week_start_ts * 1000
        ) or 0
    
    try:
        week_end = week_start + timedelta(days=6)  # Sunday
        week_label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d')}"
    except ValueError:
        week_label = ""

    metrics.update({
        "max_streak": max_streak,
        "perfect_week_count": perfect_week_count,
        "perfect_month_count": perfect_month_count,
        "max_daily_reviews": max(day_counts.values()) if day_counts else 0,
        "umeboshi_count": 1 if umeboshi_found else 0,
        "ancient_grain_count": 1 if ancient_grain_found else 0,
        "holiday_days": len(holiday_days),
        "today_review_count": day_counts.get(today_key, 0),  # This is updated by _apply_heatmap_counts
        "current_week_review_count": week_reviews,
        "today_label": now_dt.strftime("%b %d, %Y"),
        "current_week_label": week_label,
    })

    return metrics


def _compute_collection_metrics(metrics: Dict[str, Any]) -> None:
    if not mw.col or not getattr(mw.col, "db", None):
        return
    rollover_hour = mw.col.conf.get("rollover", 4)
    offset_seconds = rollover_hour * 3600

    new_cards_rows = mw.col.db.all(
        """
        SELECT STRFTIME('%Y-%m-%d', id / 1000 - ?, 'unixepoch', 'localtime') as day_key,
               COUNT(*)
        FROM cards
        GROUP BY day_key
        """, offset_seconds
    )
    total_new_cards = sum(count for _day, count in new_cards_rows)
    max_new_cards_day = max((count for _day, count in new_cards_rows), default=0)

    mature_cards = mw.col.db.scalar("SELECT COUNT() FROM cards WHERE ivl >= 21") or 0
    deck_count = len(mw.col.decks.all_names_and_ids())

    metrics.update({
        "total_new_cards": total_new_cards,
        "max_new_cards_day": max_new_cards_day,
        "mature_cards": mature_cards,
        "deck_count": deck_count,
        "addon_installed": 1,
    })


def compute_metrics() -> Dict[str, Any]:
    if not mw.col or not getattr(mw.col, "db", None):
        return _baseline_metrics()
    metrics = _compute_revlog_metrics()
    _compute_collection_metrics(metrics)
    return metrics


def evaluate_achievements(metrics: Dict[str, Any], stored: Dict[str, Any], history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    now = int(time.time())
    
    try:
        from .gamification import get_gamification_manager
        gamification = get_gamification_manager()
    except Exception as e:
        print(f"Failed to initialize gamification manager: {e}")
        gamification = None
    
    for definition in ACHIEVEMENTS:
        value = metrics.get(definition.metric, 0)
        meets_threshold = value >= definition.threshold
        stored_entry = stored.setdefault(definition.id, {"count": 0, "first": None})
        
        # Track if this is a new unlock
        was_unlocked = stored_entry.get("count", 0) >= (definition.threshold if definition.repeatable else 1)
        
        if meets_threshold:
            if definition.repeatable:
                if value > stored_entry.get("count", 0):
                    stored_entry["count"] = value
                    if stored_entry.get("first") is None:
                        stored_entry["first"] = now
                    history.append({"id": definition.id, "timestamp": now, "count": value})
            else:
                if stored_entry.get("count", 0) == 0:
                    stored_entry["count"] = 1
                    stored_entry["first"] = now
                    history.append({"id": definition.id, "timestamp": now, "count": 1})
        
        # Check if it's unlocked now
        unlocked = stored_entry.get("count", 0) >= (definition.threshold if definition.repeatable else 1)
        
        # Update gamification data if this is newly unlocked or progress changed
        if gamification:
            try:
                gamification.update_achievement(
                    achievement_id=definition.id,
                    name=definition.name,
                    description=definition.description,
                    category=definition.category,
                    unlocked=unlocked,
                    progress=value,
                    threshold=definition.threshold,
                    repeatable=definition.repeatable,
                    count=stored_entry.get("count", 0),
                    icon=definition.icon
                )
            except Exception as e:
                print(f"Error updating gamification data for {definition.id}: {e}")
        
        results.append({
            "id": definition.id,
            "name": definition.name,
            "description": definition.description,
            "category": definition.category,
            "threshold": definition.threshold,
            "repeatable": definition.repeatable,
            "unlocked": unlocked,
            "count": stored_entry.get("count", 0),
            "progress": value,
            "icon": definition.icon,
        })
    return results


def _prepare_upcoming_goals(achievements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    upcoming: List[Dict[str, Any]] = []
    for achievement in achievements:
        if achievement.get("unlocked"):
            continue
        progress = achievement.get("progress") or 0
        if progress <= 0:
            continue
        threshold = achievement.get("threshold") or 0
        remaining = max(threshold - progress, 0)
        upcoming.append(
            {
                "id": achievement.get("id"),
                "name": achievement.get("name"),
                "description": achievement.get("description"),
                "icon": achievement.get("icon") or "🍙",
                "progress": progress,
                "threshold": threshold,
                "remaining": remaining,
            }
        )

    upcoming.sort(key=lambda item: (item["remaining"], item["threshold"], item["name"] or ""))
    return upcoming


def _ensure_goals(snapshot: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    snapshot = snapshot or {}
    if "goals" not in snapshot:
        achievements = snapshot.get("achievements")
        if isinstance(achievements, list):
            snapshot["goals"] = _prepare_upcoming_goals(achievements)
        else:
            snapshot["goals"] = []
    return snapshot


def _apply_heatmap_counts(metrics: Dict[str, Any], heatmap_data: Dict[str, Any]) -> None:
    if not heatmap_data:
        return

    calendar = heatmap_data.get("calendar") or {}
    today_key = heatmap_data.get("today_date_key")
    if not today_key:
        return

    metrics["today_review_count"] = calendar.get(today_key, 0)

    try:
        today_dt = datetime.strptime(today_key, "%Y-%m-%d")
    except ValueError:
        return

    metrics["today_label"] = today_dt.strftime("%b %d, %Y")

    iso_year, iso_week, _ = today_dt.isocalendar()
    week_total = 0
    for date_str, count in calendar.items():
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if dt.isocalendar()[:2] == (iso_year, iso_week):
            week_total += int(count or 0)

    metrics["current_week_review_count"] = week_total

    try:
        week_start = datetime.fromisocalendar(iso_year, iso_week, 1)
        week_end = datetime.fromisocalendar(iso_year, iso_week, 7)
        metrics["current_week_label"] = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d')}"
    except ValueError:
        pass


def _ensure_custom_goals_config(achievements_conf: Dict[str, Any]) -> Dict[str, Any]:
    defaults = copy.deepcopy(config.DEFAULTS["achievements"].get("custom_goals", {}))
    goals_conf = achievements_conf.setdefault("custom_goals", {})

    for key, value in defaults.items():
        if isinstance(value, dict):
            goals_conf.setdefault(key, copy.deepcopy(value))
        else:
            goals_conf.setdefault(key, value)
    return goals_conf


class AchievementManager:
    def __init__(self) -> None:
        achievements_conf = self._config
        snapshot = copy.deepcopy(achievements_conf.get("snapshot", {}))
        self._snapshot: Dict[str, Any] = _ensure_goals(snapshot)
        self._pending_notifications: List[Dict[str, Any]] = []

    @property
    def _config(self) -> Dict[str, Any]:
        conf = config.get_config()
        achievements_conf = conf.get("achievements")
        if "achievements" not in conf or not isinstance(achievements_conf, dict):
            conf["achievements"] = config.DEFAULTS["achievements"].copy()
            achievements_conf = conf["achievements"]
        achievements_conf.setdefault("enabled", False)
        achievements_conf.setdefault("earned", {})
        achievements_conf.setdefault("history", [])
        achievements_conf.setdefault("last_refresh", None)
        achievements_conf.setdefault("snapshot", {})
        _ensure_custom_goals_config(achievements_conf)
        # defaults = config.DEFAULTS["achievements"].get("restaurant_level", {})
        # rl_conf = achievements_conf.setdefault("restaurant_level", {})
        # for key, value in defaults.items():
        #     if key not in rl_conf:
        #         rl_conf[key] = copy.deepcopy(value)
        return achievements_conf

    def is_enabled(self) -> bool:
        return bool(self._config.get("enabled", False))

    def refresh(self, force: bool = False) -> Optional[Dict[str, Any]]:
        if not self.is_enabled() and not force:
            return None
        if not mw.col or not getattr(mw.col, "db", None):
            return None
        metrics = compute_metrics()
        heatmap_snapshot = heatmap.get_heatmap_data() if mw.col else {}
        if heatmap_snapshot:
            _apply_heatmap_counts(metrics, heatmap_snapshot)
        achievements_conf = self._config
        history = achievements_conf.get("history", [])
        history_len_before = len(history)
        achievements = evaluate_achievements(metrics, achievements_conf.setdefault("earned", {}), history)
        new_entries: List[Dict[str, Any]] = []
        if len(history) > history_len_before:
            new_entries = history[history_len_before:]
            self._pending_notifications.extend(self._build_notifications(new_entries))
            
            # Gift XP for new achievements
            try:
                from . import restaurant_level
                for entry in new_entries:
                    achievement_id = entry.get("id")
                    if achievement_id:
                        xp_notifications = restaurant_level.manager.handle_achievement_unlock(achievement_id)
                        self._pending_notifications.extend(xp_notifications)
            except Exception as e:
                print(f"Error gifting XP for achievements: {e}")

        record_progress = self.is_enabled()
        custom_goals_snapshot, custom_goal_notifications = self._evaluate_custom_goals(metrics, achievements_conf, record_progress)
        if record_progress and custom_goal_notifications:
            self._pending_notifications.extend(custom_goal_notifications)
        achievements_conf["history"] = history
        achievements_conf["last_refresh"] = int(time.time())
        achievements_conf["snapshot"] = _ensure_goals({
            "metrics": metrics,
            "achievements": achievements,
            "heatmap": heatmap_snapshot,
            "custom_goals": custom_goals_snapshot,
            "goals": _prepare_upcoming_goals(achievements),
            "goals": _prepare_upcoming_goals(achievements),
        })
        conf = config.get_config()
        conf["achievements"] = achievements_conf
        config.write_config(conf)
        self._snapshot = achievements_conf["snapshot"]
        self._snapshot = achievements_conf["snapshot"]
        return self._snapshot

    def get_snapshot(self) -> Dict[str, Any]:
        if not self._snapshot:
            snapshot = self.refresh(force=True)
            if snapshot is None:
                achievements_conf = self._config
                baseline = _baseline_metrics()
                achievements = evaluate_achievements(
                    baseline,
                    copy.deepcopy(achievements_conf.get("earned", {})),
                    list(achievements_conf.get("history", [])),
                )
                custom_goals_snapshot, _ = self._evaluate_custom_goals(baseline, achievements_conf, record_progress=False)
                self._snapshot = _ensure_goals({
                    "metrics": baseline,
                    "achievements": achievements,
                    "custom_goals": custom_goals_snapshot,
                    "goals": _prepare_upcoming_goals(achievements),
                    "goals": _prepare_upcoming_goals(achievements),
                })
            else:
                if "custom_goals" not in snapshot:
                    custom_goals_snapshot, _ = self._evaluate_custom_goals(snapshot.get("metrics", _baseline_metrics()), achievements_conf, record_progress=False)
                    snapshot["custom_goals"] = custom_goals_snapshot
                self._snapshot = _ensure_goals(snapshot)
                self._snapshot = _ensure_goals(snapshot)
        return self._snapshot

    def _evaluate_custom_goals(
        self,
        metrics: Dict[str, Any],
        achievements_conf: Dict[str, Any],
        record_progress: bool,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        goals_conf = _ensure_custom_goals_config(achievements_conf)
        notifications: List[Dict[str, Any]] = []

        now_dt = datetime.now()
        today_key = now_dt.strftime("%Y-%m-%d")
        iso_year, iso_week, _ = now_dt.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"

        week_label = metrics.get("current_week_label") or ""
        today_label = metrics.get("today_label") or now_dt.strftime("%b %d, %Y")

        custom_goals_snapshot: List[Dict[str, Any]] = []

        def handle_goal(
            goal_key: str,
            label: str,
            icon: str,
            period_label: str,
            progress: int,
        ) -> None:
            goal_conf = goals_conf.get(goal_key, {})
            enabled = bool(goal_conf.get("enabled", False))
            target = max(int(goal_conf.get("target", 0)), 0)
            completed = enabled and target > 0 and progress >= target

            if goal_key == "daily":
                last_marker_key = "last_notified_day"
                current_marker = today_key
            else:
                last_marker_key = "last_notified_week"
                current_marker = week_key

            previous_target = int(goal_conf.get("last_target_value", target))
            if record_progress:
                if previous_target != target:
                    goal_conf[last_marker_key] = None
                    goal_conf["last_target_value"] = target
                else:
                    goal_conf.setdefault("last_target_value", target)

            last_marker = goal_conf.get(last_marker_key)
            completion_count = int(goal_conf.get("completion_count", 0))

            if record_progress and last_marker == current_marker and not completed:
                goal_conf[last_marker_key] = None
                last_marker = None

            if record_progress and completed and current_marker != last_marker:
                goal_conf[last_marker_key] = current_marker
                goal_conf["completion_count"] = completion_count + 1
                notifications.append({
                    "id": f"custom_goal_{goal_key}",
                    "name": f"{label} Complete!",
                    "description": f"You reached your {label.lower()} target of {target} cards.",
                    "icon": icon,
                })
            elif record_progress and not completed and current_marker != last_marker and last_marker:
                # Reset marker when entering a new period to allow future notifications.
                goal_conf[last_marker_key] = None

            remaining = max(target - progress, 0) if target else 0

            custom_goals_snapshot.append({
                "id": goal_key,
                "title": label,
                "icon": icon,
                "enabled": enabled,
                "target": target,
                "progress": progress,
                "remaining": remaining,
                "completed": completed,
                "period_label": period_label,
                "completion_count": goal_conf.get("completion_count", completion_count),
            })

        handle_goal(
            "daily",
            "Daily Goal",
            "🌅",
            today_label,
            int(metrics.get("today_review_count", 0)),
        )

        handle_goal(
            "weekly",
            "Weekly Goal",
            "📆",
            week_label,
            int(metrics.get("current_week_review_count", 0)),
        )

        return custom_goals_snapshot, notifications

    def _build_notifications(self, history_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        notifications: List[Dict[str, Any]] = []
        for entry in history_entries:
            definition = ACHIEVEMENTS_BY_ID.get(entry.get("id"))
            if not definition:
                continue
            notifications.append(
                {
                    "id": definition.id,
                    "name": definition.name,
                    "description": definition.description,
                    "icon": definition.icon or "🍙",
                }
            )
        return notifications

    def pop_pending_notifications(self) -> List[Dict[str, Any]]:
        pending = self._pending_notifications
        self._pending_notifications = []
        return pending

    def _dispatch_notifications(self, notifications: List[Dict[str, Any]]) -> None:
        if not notifications:
            return

        payload = json.dumps(notifications, ensure_ascii=False)
        state = getattr(mw, "state", None)
        webviews = []

        reviewer = getattr(mw, "reviewer", None)
        overview = getattr(mw, "overview", None)
        deck_browser = getattr(mw, "deckBrowser", None)

        if state == "review" and reviewer and getattr(reviewer, "web", None):
            webviews.append(reviewer.web)
        elif state == "overview" and overview and getattr(overview, "web", None):
            webviews.append(overview.web)
        elif state == "deckBrowser" and deck_browser and getattr(deck_browser, "web", None):
            webviews.append(deck_browser.web)

        # Fallbacks if state-based lookup failed
        for web in [reviewer and getattr(reviewer, "web", None), overview and getattr(overview, "web", None), deck_browser and getattr(deck_browser, "web", None)]:
            if web and web not in webviews:
                webviews.append(web)

        script = (
            "if (window.OnigiriNotifications) {"
            f"const items = {payload};"
            "items.forEach(item => window.OnigiriNotifications.show(item));"
            "}"
        )

        for web in webviews:
            if not web:
                continue
            try:
                web.eval(script)
                break
            except Exception:
                continue

    def on_reviewer_did_answer(self, *args, **kwargs) -> None:
        if self.is_enabled():
            self.refresh()
            pending = self.pop_pending_notifications()
            self._dispatch_notifications(pending)


manager = AchievementManager()

def register_hooks() -> None:
    gui_hooks.reviewer_did_answer_card.append(manager.on_reviewer_did_answer)


register_hooks()
