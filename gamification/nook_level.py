from __future__ import annotations

import copy
import hashlib
import json
import time
import re
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

import requests
from aqt import mw

from .. import config
from ..translations import tr



XP_PER_REVIEW = 5
XP_PER_ACHIEVEMENT = 10
XP_PER_CUSTOM_GOAL = 20
RECIPE_RUSH_API_URL = "https://script.google.com/macros/s/AKfycbyQl6b_cPnXJEJeEJryvsuRzZYclfIt_LWN1Mqqf63FjzCbKdPKV_uHIgYtHIXmAbnB/exec"
# The Apps Script re-syncs every shop into a sheet on each call and regularly
# takes seconds. It is never called from the review loop any more - the fetch
# runs in the background and the ticket that is already saved is used until the
# answer arrives.
RECIPE_RUSH_TIMEOUT = 15
RECIPE_RUSH_CACHE_TTL = 600      # a ticket we got is reused for 10 minutes
RECIPE_RUSH_FAIL_RETRY = 1800    # after a failure, wait 30 minutes before asking again




def get_motivational_phrases():
    return [
        tr("motivational_phrase_1"),
        tr("motivational_phrase_2"),
        tr("motivational_phrase_3"),
        tr("motivational_phrase_4"),
        tr("motivational_phrase_5"),
        tr("motivational_phrase_6"),
    ]

# Image filenames are relative to system_files/gamification_images/nook_folder/,
# organized into subfolders that match the store's 3 tabs (restaurants/sushi/shops).
RESTAURANTS = {
    "focus_dango": {
        "name": "focus_dango_name",
        "price": 0,
        "theme": "#DC90B8",
        "image": "restaurants/focus_dango.webp",
        "description": "focus_dango_desc"
    },
    "motivated_mochi": {
        "name": "motivated_mochi_name",
        "price": 0,
        "theme": "#6EC170",
        "image": "restaurants/motivated_mochi.webp",
        "description": "motivated_mochi_desc"
    },
    "macha_delights": {
        "name": "macha_delights_name",
        "price": 400,
        "theme": "#517C58",
        "image": "restaurants/matcha_delights.webp",
        "description": "macha_delights_desc"
    },
    "macaron_maison": {
        "name": "macaron_maison_name",
        "price": 500,
        "theme": "#AFC3D6",
        "image": "restaurants/macaron_maison.webp",
        "description": "macaron_maison_desc"
    },
    "coffee_co": {
        "name": "coffee_co_name",
        "price": 600,
        "theme": "#98693A",
        "image": "restaurants/coffee_co.webp",
        "description": "coffee_co_desc"
    },
    "bakery_heaven": {
        "name": "bakery_heaven_name",
        "price": 800,
        "theme": "#CD9C57",
        "image": "restaurants/bakery_heaven.webp",
        "description": "bakery_heaven_desc"
    },
    "awesome_boba": {
        "name": "awesome_boba_name",
        "price": 850,
        "theme": "#CD8DCA",
        "image": "restaurants/awesome_boba.webp",
        "description": "awesome_boba_desc"
    },
    "awesome_shiny_boba": {
        "name": "awesome_shiny_boba_name",
        "price": 1000,
        "theme": "#41A59D",
        "image": "restaurants/shiny_awesome_boba.webp",
        "description": "awesome_shiny_boba_desc"
    },
    "santas_coffee": {
        "name": "santas_coffee_name",
        "price": 1225,
        "theme": "#CA4D44",
        "image": "restaurants/santas_coffee.webp",
        "description": "santas_coffee_desc"
    },
}

# "Sushi Evolutions": upgrade stages for the starting Onigiri Stand.
EVOLUTIONS = {
    "restaurant_evo_i": {
        "name": "restaurant_evo_i_name",
        "price": 700,
        "theme": "#D07A5F",
        "image": "sushi/restaurant_i.webp",
        "description": "restaurant_evo_i_desc"
    },
    "restaurant_evo_ii": {
        "name": "restaurant_evo_ii_name",
        "price": 800,
        "theme": "#D07A5F",
        "image": "sushi/restaurant_ii.webp",
        "description": "restaurant_evo_ii_desc"
    },
    "restaurant_evo_iii": {
        "name": "restaurant_evo_iii_name",
        "price": 900,
        "theme": "#D07A5F",
        "image": "sushi/restaurant_iii.webp",
        "description": "restaurant_evo_iii_desc"
    },
    "restaurant_evo_iv": {
        "name": "restaurant_evo_iv_name",
        "price": 1000,
        "theme": "#D07A5F",
        "image": "sushi/restaurant_iv.webp",
        "description": "restaurant_evo_iv_desc"
    },
    "restaurant_evo_legendary": {
        "name": "restaurant_evo_legendary_name",
        "price": 2000,
        "theme": "#445A78",
        "image": "sushi/legendary_restaurant.webp",
        "description": "restaurant_evo_legendary_desc"
    },
    "restaurant_evo_garden": {
        "name": "restaurant_evo_garden_name",
        "price": 3000,
        "theme": "#2F553D",
        "image": "sushi/garden_palace_restaurant.webp",
        "description": "restaurant_evo_garden_desc"
    },
    "restaurant_evo_heaven": {
        "name": "restaurant_evo_heaven_name",
        "price": 4000,
        "theme": "#E8D9A0",
        "image": "sushi/heaven_restaurant.webp",
        "description": "restaurant_evo_heaven_desc"
    },
    "restaurant_evo_paradise": {
        "name": "restaurant_evo_paradise_name",
        "price": 5000,
        "theme": "#3D9C8A",
        "image": "sushi/paradise_restaurant.webp",
        "description": "restaurant_evo_paradise_desc"
    },
}

# "Shops": special/seasonal venues, separate from the everyday restaurant themes.
SHOPS = {
    "grocery_store": {
        "name": "grocery_store_name",
        "price": 700,
        "theme": "#AD6131",
        "image": "shops/grocery_store.webp",
        "description": "grocery_store_desc"
    },
    "lunar_new_year": {
        "name": "lunar_new_year_name",
        "price": 888,
        "theme": "#D22B2B",
        "image": "shops/lunar_new_year_feast.webp",
        "description": "lunar_new_year_desc"
    },
    "astronigiri": {
        "name": "astronigiri_name",
        "price": 5000,
        "theme": "#74829B",
        "image": "shops/astronigiri.webp",
        "description": "astronigiri_desc"
    },
    "pokestore": {
        "name": "pokestore_name",
        "price": 950,
        "theme": "#E8B23D",
        "image": "shops/pokestore.webp",
        "description": "pokestore_desc"
    },
    "wizard_shop": {
        "name": "wizard_shop_name",
        "price": 1200,
        "theme": "#6A4C93",
        "image": None,
        "description": "wizard_shop_desc"
    },
    "onigilab": {
        "name": "onigilab_name",
        "price": 1300,
        "theme": "#3FA796",
        "image": "shops/onigi_lab.webp",
        "description": "onigilab_desc"
    },
    "paws_whiskers": {
        "name": "paws_whiskers_name",
        "price": 1100,
        "theme": "#E89CAE",
        "image": None,
        "description": "paws_whiskers_desc"
    },
    "dino_shop": {
        "name": "dino_shop_name",
        "price": 1400,
        "theme": "#7A8450",
        "image": None,
        "description": "dino_shop_desc"
    },
}

def get_localized_restaurants():
    localized = copy.deepcopy(RESTAURANTS)
    for key, data in localized.items():
        data["name"] = tr(data["name"])
        data["description"] = tr(data["description"])
    return localized

def get_localized_evolutions():
    localized = copy.deepcopy(EVOLUTIONS)
    for key, data in localized.items():
        data["name"] = tr(data["name"])
        data["description"] = tr(data["description"])
    return localized

def get_localized_shops():
    localized = copy.deepcopy(SHOPS)
    for key, data in localized.items():
        data["name"] = tr(data["name"])
        data["description"] = tr(data["description"])
    return localized


@dataclass(frozen=True)
class LevelProgress:
    enabled: bool
    name: str
    level: int
    total_xp: int
    xp_into_level: int
    xp_to_next_level: int
    notifications_enabled: bool
    show_profile_bar_progress: bool
    show_profile_page_progress: bool

    @property
    def progress_fraction(self) -> float:
        if self.xp_to_next_level <= 0:
            return 0.0
        return max(0.0, min(1.0, self.xp_into_level / self.xp_to_next_level))


class NookLevelManager:
    """Tracks the Nook Level system (XP, levels, and notifications)."""

    def __init__(self) -> None:
        self._addon_package: str | None = None
        self._daily_target_cache: Dict[str, Any] = {}
        self._recipe_rush_ticket_cache: Dict[str, Any] = {}
        self._recipe_rush_fetch_inflight: bool = False
        self._last_recipe_rush_error: str = ""
        self._last_daily_sync_time: float = 0
        self._cached_daily_count: int = -1
        self._xp_history: List[int] = []
        
    @property
    def _gamification_manager(self):
        from .gamification import get_gamification_manager
        return get_gamification_manager()

    def invalidate_daily_cache(self) -> None:
        """Invalidate the daily progress cache to force fresh data retrieval."""
        self._last_daily_sync_time = 0
        self._cached_daily_count = -1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_review_xp(self, xp_amount: int, count: int = 1) -> List[Dict[str, Any]]:
        """Grant XP for completed reviews and update daily special progress."""
        from aqt import mw
        
        xp_amount = int(xp_amount)
        if xp_amount == 0:
            return []

            
        # Get notifications from _add_xp first
        notifications = self._add_xp(xp_amount, reason="review", review_count=count)
        
        # If we have notifications, dispatch them using the achievement manager's method
        # Notifications are returned and handled by the caller or displayed via other means if necessary
        # We no longer dispatch via achievement_manager to avoid coupling
        
        return notifications

    # handle_achievement_unlocks removed to decouple from achievements

    def handle_custom_goal_completion(self, goal_key: str) -> List[Dict[str, Any]]:
        """Grant XP when a custom goal is completed."""
        return self._add_xp(XP_PER_CUSTOM_GOAL, reason=f"custom_goal:{goal_key}")

    def handle_achievement_unlock(self, achievement_id: str) -> List[Dict[str, Any]]:
        """Grant XP when an achievement is unlocked."""
        # Gift 50 XP as requested
        return self._add_xp(50, reason=f"achievement:{achievement_id}")

    def reset_progress(self) -> None:
        """Reset Nook Level progress back to level 0."""
        from aqt import mw
        
        # Reset XP and level in gamification.json (Source of Truth)
        # Also ensure we mark as migrated so we don't re-import from legacy config
        updates = {
            "total_xp": 0,
            "level": 0,
            "migrated": True
        }
        self._update_gamification_data(updates, immediate=True)
        
        # Force Anki to mark the collection as modified so it saves
        if mw and mw.col:
            mw.col.setMod()
            mw.col.setMod()

        


    def reset_coins(self) -> None:
        """Reset Taiyaki Coins to 0."""
        self._update_gamification_data({"taiyaki_coins": 0}, immediate=True)


    def reset_purchases(self) -> None:
        """Reset owned items and current theme to default."""
        self._update_gamification_data({
            "owned_items": ["default"],
            "current_theme_id": "default"
        }, immediate=True)




    def set_enabled(self, enabled: bool) -> None:
        self._update_gamification_data({"enabled": bool(enabled)}, immediate=True)

    def set_notifications_enabled(self, enabled: bool) -> None:
        self._update_gamification_data({"notifications_enabled": bool(enabled)}, immediate=True)

    def set_profile_bar_visibility(self, show: bool) -> None:
        self._update_gamification_data({"show_profile_bar_progress": bool(show)}, immediate=True)

    def set_profile_page_visibility(self, show: bool) -> None:
        self._update_gamification_data({"show_profile_page_progress": bool(show)}, immediate=True)

    def set_restaurant_name(self, name: str) -> None:
        """Set the custom name for the restaurant."""
        self._update_gamification_data({"name": str(name)}, immediate=True)

    def get_progress(self) -> LevelProgress:
        conf = config.get_config_readonly()
        # Check top level first
        restaurant_conf = conf.get("restaurant_level", {})
        
        # Fallback to old location if not found at root
        if not restaurant_conf and "achievements" in conf:
            restaurant_conf = conf["achievements"].get("restaurant_level", {})
        
        # Read game state from gamification manager
        game_state = self._get_gamification_state()
        
        # MIGRATION: Check settings and XP
        updates = {}
        
        # 1. Settings Migration
        # If setting is None (fresh load with new schema), migrate from config or default to True
        def check_migrate(key, default):
            val = game_state.get(key)
            if val is None:
                conf_val = restaurant_conf.get(key, default)
                updates[key] = conf_val
                return conf_val
            return val
            
        enabled = check_migrate("enabled", True)
        notifications_enabled = check_migrate("notifications_enabled", True)
        show_profile_bar_progress = check_migrate("show_profile_bar_progress", True)
        show_profile_page_progress = check_migrate("show_profile_page_progress", True)

        # 2. XP/Level Migration (Legacy check)
        # Only run this once per profile
        migrated = game_state.get("migrated", False)
        
        if not migrated:
            # Mark as migrated so we don't check again (unless we fail to save?)
            updates["migrated"] = True
            
            # If config has higher XP/Level than gamification.json, migrate it.
            conf_xp = int(restaurant_conf.get("total_xp", 0))
            json_xp = int(game_state.get("total_xp", 0))
            
            if conf_xp > json_xp:
                updates["total_xp"] = conf_xp
                updates["level"] = int(restaurant_conf.get("level", 0))
                
                # Also migrate items if needed
                conf_owned = restaurant_conf.get("owned_items", [])
                json_owned = game_state.get("owned_items", ["default"])
                merged_owned = list(set(conf_owned + json_owned))
                if len(merged_owned) > len(json_owned):
                     updates["owned_items"] = merged_owned
                     
                # Migrate theme
                conf_theme = restaurant_conf.get("current_theme_id", "default")
                json_theme = game_state.get("current_theme_id", "default")
                if conf_theme != "default" and json_theme == "default":
                    updates["current_theme_id"] = conf_theme

        # Apply migrations if any
        if updates:
            self._update_gamification_data(updates)
            # Refresh state
            game_state = self._get_gamification_state()
        
        # Fallback to config if gamification.json is empty (rare now due to defaults)
        total_xp = int(game_state.get("total_xp", restaurant_conf.get("total_xp", 0)))
        # level = int(game_state.get("level", restaurant_conf.get("level", 0)))
        name = game_state.get("name", restaurant_conf.get("name", "Nook Level"))
        # The original name is stored in existing profiles as an English
        # default.  Keep user-renamed Nooks intact, but localize that default.
        if name == "Nook Level":
            name = tr("restaurant_level_title", "Nook Level")

        # Recalculate level from XP to be safe
        calc_level, xp_into_level, xp_to_next = self._collapse_xp(total_xp)
        level = calc_level

        return LevelProgress(
            enabled=bool(enabled),
            name=name,
            level=level,
            total_xp=total_xp,
            xp_into_level=xp_into_level,
            xp_to_next_level=xp_to_next,
            notifications_enabled=bool(notifications_enabled),
            show_profile_bar_progress=bool(show_profile_bar_progress),
            show_profile_page_progress=bool(show_profile_page_progress),
        )

    def get_progress_payload(self) -> Dict[str, Any]:
        progress = self.get_progress()
        xp_to_next = max(progress.xp_to_next_level, 0)
        xp_into_level = max(progress.xp_into_level, 0)
        remaining = max(xp_to_next - xp_into_level, 0)
        if xp_to_next <= 0:
            percent = 1.0
        else:
            percent = min(1.0, xp_into_level / xp_to_next)

        return {
            "enabled": progress.enabled,
            "name": progress.name,
            "level": progress.level,
            "totalXp": progress.total_xp,
            "xpIntoLevel": xp_into_level,
            "xpToNextLevel": xp_to_next,
            "xpRemaining": remaining,
            "progressFraction": percent,
            "notificationsEnabled": progress.notifications_enabled and not bool(config.get_config().get("onigiri_reviewer_silent_notifications", False)),
            "showProfileBar": progress.show_profile_bar_progress,
            "showProfilePage": progress.show_profile_page_progress,
            "phrase": self._get_motivational_phrase(progress.level),
        }

    def _get_motivational_phrase(self, level: int) -> str:
        phrases = get_motivational_phrases()
        return phrases[level % len(phrases)]

    def get_daily_special_status(self) -> Dict[str, Any]:
        """Get daily special data, resetting it if it's a new day."""
        conf = config.get_config()
        # Get settings from config
        daily_special_conf = conf.get("daily_special", {})
        
        # Fallback to old location
        if not daily_special_conf and "achievements" in conf:
            daily_special_conf = conf["achievements"].get("daily_special", {})
            
        # Get state from gamification.json
        state = self._get_gamification_state()
        daily_special_state = state.get("daily_special", {})
        
        # Merge config (settings) and state (progress). Preserve Nook Rush ticket metadata.
        daily_special = dict(daily_special_state) if isinstance(daily_special_state, dict) else {}
        daily_special.update({
            "enabled": daily_special_conf.get("enabled", daily_special.get("enabled", False)),
            "target": daily_special.get("target", daily_special_conf.get("target", 100)),
            "current_progress": daily_special.get("current_progress", 0),
            "last_updated": daily_special.get("last_updated"),
            "last_notified_milestone": daily_special.get("last_notified_milestone", 0),
            "last_notified_percent": daily_special.get("last_notified_percent", 0),
        })
        
        reset_occurred = self._check_and_reset_daily_special(daily_special)
        sync_occurred = self._sync_daily_progress_with_db(daily_special)
        
        if reset_occurred or sync_occurred:
            # Update state in gamification.json
            self._update_gamification_daily_special(daily_special)
            
        return daily_special

    def _get_anki_today_date(self) -> str:
        """Get today's date string based on Anki's rollover time, not calendar midnight.
        
        This ensures consistency with Anki's review counting which respects the rollover hour.
        """
        if not mw.col or not hasattr(mw.col, 'sched'):
            return datetime.now().strftime('%Y-%m-%d')
        
        try:
            # day_cutoff is the Unix timestamp of when the current Anki day ends
            # Subtracting 1 second gives us a time within the current Anki day
            day_cutoff = mw.col.sched.day_cutoff
            # Get a timestamp that's definitely within the current Anki day
            current_anki_day = datetime.fromtimestamp(day_cutoff - 1)
            return current_anki_day.strftime('%Y-%m-%d')
        except Exception:
            return datetime.now().strftime('%Y-%m-%d')

    def _recipe_rush_restaurants_payload(self) -> List[Dict[str, Any]]:
        restaurants = [{
            "id": "default",
            "name": tr("onigiri_stand_name", "Onigiri Stand"),
            "type": "restaurant",
            "price": 0,
        }]

        for item_id, item in RESTAURANTS.items():
            restaurants.append({
                "id": item_id,
                "name": tr(item.get("name", item_id), item_id.replace("_", " ").title()),
                "type": "restaurant",
                "price": int(item.get("price", 0) or 0),
            })

        for item_id, item in EVOLUTIONS.items():
            restaurants.append({
                "id": item_id,
                "name": tr(item.get("name", item_id), item_id.replace("_", " ").title()),
                "type": "evolution",
                "price": int(item.get("price", 0) or 0),
            })

        for item_id, item in SHOPS.items():
            restaurants.append({
                "id": item_id,
                "name": tr(item.get("name", item_id), item_id.replace("_", " ").title()),
                "type": "shop",
                "price": int(item.get("price", 0) or 0),
            })

        return restaurants

    def _normalize_ingredient_cards(self, ingredients: Any, target: int) -> List[Dict[str, Any]]:
        if isinstance(ingredients, str):
            raw_names = [part.strip() for part in re.split(r"[,;|]", ingredients) if part.strip()]
            ingredients = [{"name": name} for name in raw_names]

        if not isinstance(ingredients, list):
            ingredients = []

        normalized = []
        names = [item for item in ingredients if isinstance(item, (dict, str))]
        count = max(1, len(names))
        fallback_cards = max(1, int(target * 0.7) // count) if target > 0 else 1

        for item in names:
            if isinstance(item, str):
                name = item.strip()
                cards = fallback_cards
            else:
                name = str(item.get("name") or item.get("ingredient") or "").strip()
                try:
                    cards = int(item.get("cards") or item.get("required_cards") or fallback_cards)
                except (TypeError, ValueError):
                    cards = fallback_cards
            if name:
                normalized.append({"name": name, "cards": max(1, cards)})

        if not normalized:
            normalized = [
                {"name": tr("recipe_rush_default_ingredient_1", "Rice"), "cards": max(1, int(target * 0.35) or 1)},
                {"name": tr("recipe_rush_default_ingredient_2", "Filling"), "cards": max(1, int(target * 0.35) or 1)},
            ]

        return normalized

    def _normalize_recipe_rush_ticket(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ticket = data.get("ticket", data) if isinstance(data, dict) else {}
        if not isinstance(ticket, dict):
            return None

        try:
            target = int(ticket.get("target_cards") or ticket.get("targetCards") or ticket.get("target") or 0)
        except (TypeError, ValueError):
            target = 0

        try:
            prep_cards = int(ticket.get("prep_cards") or ticket.get("prepCards") or 0)
        except (TypeError, ValueError):
            prep_cards = 0

        try:
            delivery_cards = int(ticket.get("delivery_cards") or ticket.get("deliveryCards") or 0)
        except (TypeError, ValueError):
            delivery_cards = 0

        ingredients = self._normalize_ingredient_cards(ticket.get("ingredients"), max(target, 1))
        ingredient_total = sum(int(item.get("cards", 0) or 0) for item in ingredients)

        if target <= 0:
            target = ingredient_total + max(0, prep_cards) + max(0, delivery_cards)
        if target <= 0:
            return None

        if prep_cards <= 0:
            prep_cards = max(1, int(target * 0.2))
        if delivery_cards <= 0:
            delivery_cards = max(1, target - ingredient_total - prep_cards)
        if ingredient_total + prep_cards + delivery_cards != target:
            delivery_cards = max(1, target - ingredient_total - prep_cards)
            if ingredient_total + prep_cards + delivery_cards <= 0:
                delivery_cards = 1

        difficulty = str(ticket.get("difficulty") or "common").strip().lower()
        if difficulty not in {"common", "uncommon", "rare", "epic", "legendary"}:
            difficulty = "common"

        return {
            "recipe_id": str(ticket.get("recipe_id") or ticket.get("recipeId") or ticket.get("id") or "").strip(),
            "name": str(ticket.get("name") or ticket.get("recipe_name") or ticket.get("recipeName") or tr("recipe_rush_title", "Nook Rush")).strip(),
            "description": str(ticket.get("description") or "").strip(),
            "difficulty": difficulty,
            "target": max(1, int(target)),
            "target_cards": max(1, int(target)),
            "ingredients": ingredients,
            "prep_cards": max(1, int(prep_cards)),
            "delivery_cards": max(1, int(delivery_cards)),
            "preparation": str(ticket.get("preparation") or ticket.get("prep") or "").strip(),
            "delivery": str(ticket.get("delivery") or ticket.get("deliver_to") or ticket.get("deliverTo") or "").strip(),
            "restaurant_id": str(ticket.get("restaurant_id") or ticket.get("restaurantId") or self.get_current_theme_id()).strip() or "default",
            "restaurant_name": str(ticket.get("restaurant_name") or ticket.get("restaurantName") or "").strip(),
            "rush_name": str(ticket.get("rush_name") or ticket.get("rushName") or "").strip(),
            "ingredients_label": str(ticket.get("ingredients_label") or ticket.get("ingredientsLabel") or "").strip(),
            "stage_collect_label": str(ticket.get("stage_collect_label") or ticket.get("stageCollectLabel") or "").strip(),
            "stage_prepare_label": str(ticket.get("stage_prepare_label") or ticket.get("stagePrepareLabel") or "").strip(),
            "stage_deliver_label": str(ticket.get("stage_deliver_label") or ticket.get("stageDeliverLabel") or "").strip(),
            "stage_completed_label": str(ticket.get("stage_completed_label") or ticket.get("stageCompletedLabel") or "").strip(),
            "xp_reward": int(ticket.get("xp_reward") or ticket.get("xpReward") or 0) if str(ticket.get("xp_reward") or ticket.get("xpReward") or "0").isdigit() else 0,
            "source": str(ticket.get("source") or "apps_script"),
        }

    def _fetch_recipe_rush_ticket(
        self, today: str, restaurant_id: str, blocking: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Today's Rush ticket for ``restaurant_id``.

        Called from the answer hook, so it must never touch the network: a
        request to the Apps Script takes seconds and used to freeze the card
        being answered. Unless ``blocking`` is set (the manual "resync now"
        button), a stale/missing ticket only schedules a background fetch and
        whatever is cached is returned straight away.
        """
        cache = self._recipe_rush_ticket_cache
        cache_matches = (
            cache.get("date") == today and cache.get("restaurant_id") == restaurant_id
        )
        if cache_matches:
            age = time.time() - float(cache.get("checked_at", 0) or 0)
            # Hold on to a failure longer than a success so an unreachable
            # server cannot turn into a request per screen change.
            ttl = RECIPE_RUSH_CACHE_TTL if cache.get("ticket") else RECIPE_RUSH_FAIL_RETRY
            if age < ttl:
                return cache.get("ticket")

        if not blocking:
            self._schedule_recipe_rush_fetch(today, restaurant_id)
            return cache.get("ticket") if cache_matches else None

        ticket = self._ticket_from_response(
            self._request_recipe_rush(self._recipe_rush_payload(today, restaurant_id))
        )
        self._store_recipe_rush_ticket(today, restaurant_id, ticket)
        return ticket

    def _recipe_rush_payload(self, today: str, restaurant_id: str) -> Dict[str, Any]:
        """Build the request body. Runs on the main thread - it reads config."""
        restaurant_conf = self._restaurant_conf_readonly()
        return {
            "action": "recipeRushToday",
            "anki_day": today,
            "restaurant_id": restaurant_id,
            "difficulty": restaurant_conf.get("difficulty", "Apprendice"),
            "restaurants": self._recipe_rush_restaurants_payload(),
        }

    @staticmethod
    def _request_recipe_rush(payload: Dict[str, Any]) -> Dict[str, Any]:
        """The network call itself. Safe to run on a worker thread."""
        try:
            response = requests.post(
                RECIPE_RUSH_API_URL, json=payload, timeout=RECIPE_RUSH_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {"__error__": "Malformed response."}
        except Exception as exc:
            return {"__error__": str(exc)}

    def _ticket_from_response(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Turn a raw response into a ticket, recording why it failed."""
        if not isinstance(data, dict):
            self._last_recipe_rush_error = "Malformed response."
            return None
        error = data.get("__error__")
        if error:
            print(f"Onigiri: Nook Rush server unavailable: {error}")
            self._last_recipe_rush_error = str(error)
            return None
        if str(data.get("result", "")).lower() != "success":
            self._last_recipe_rush_error = str(
                data.get("message") or "Apps Script returned an error."
            )
            return None
        self._last_recipe_rush_error = ""
        return self._normalize_recipe_rush_ticket(data)

    def _store_recipe_rush_ticket(
        self, today: str, restaurant_id: str, ticket: Optional[Dict[str, Any]]
    ) -> None:
        self._recipe_rush_ticket_cache = {
            "date": today,
            "restaurant_id": restaurant_id,
            "checked_at": time.time(),
            "ticket": ticket,
        }

    def _schedule_recipe_rush_fetch(self, today: str, restaurant_id: str) -> None:
        """Ask the Apps Script for a ticket without blocking the UI."""
        if self._recipe_rush_fetch_inflight:
            return

        try:
            payload = self._recipe_rush_payload(today, restaurant_id)
        except Exception as exc:
            print(f"Onigiri: could not build Nook Rush request: {exc}")
            return

        request = self._request_recipe_rush

        def work() -> Dict[str, Any]:
            return request(payload)

        def done(future: Any) -> None:
            self._recipe_rush_fetch_inflight = False
            try:
                data = future.result()
            except Exception as exc:
                data = {"__error__": str(exc)}
            ticket = self._ticket_from_response(data)
            self._store_recipe_rush_ticket(today, restaurant_id, ticket)
            if ticket:
                self._apply_fetched_recipe_rush_ticket(today, ticket)

        self._recipe_rush_fetch_inflight = True
        try:
            mw.taskman.run_in_background(work, done)
        except Exception as exc:
            self._recipe_rush_fetch_inflight = False
            print(f"Onigiri: could not start Nook Rush fetch: {exc}")

    def _apply_fetched_recipe_rush_ticket(self, today: str, ticket: Dict[str, Any]) -> None:
        """Install a ticket that arrived from the background fetch."""
        state = self._get_gamification_state()
        daily_special_state = state.get("daily_special", {})
        daily_special = dict(daily_special_state) if isinstance(daily_special_state, dict) else {}

        # "enabled" is a setting, not part of the saved Rush state, so it has
        # to be read from the config the way _add_xp does.
        conf = config.get_config_readonly()
        daily_special_conf = conf.get("daily_special", {})
        if not daily_special_conf and isinstance(conf.get("achievements"), dict):
            daily_special_conf = conf["achievements"].get("daily_special", {})
        if not daily_special_conf.get("enabled", False):
            return
        daily_special["enabled"] = True

        new_target = int(ticket.get("target", 0) or 0)
        if not new_target:
            return

        already_current = (
            daily_special.get("last_updated") == today
            and daily_special.get("source") not in (None, "", "fallback")
            and daily_special.get("recipe_id") == ticket.get("recipe_id")
        )
        if already_current:
            return

        daily_special["last_updated"] = today
        daily_special["current_progress"] = daily_special.get("current_progress", 0)
        self._apply_recipe_rush_ticket_data(daily_special, ticket, new_target, today)
        self._update_gamification_daily_special(daily_special)
        self.invalidate_daily_cache()

    def _recipe_rush_stage(self, daily_special: Dict[str, Any]) -> str:
        if daily_special.get("completed"):
            return "completed"

        current = max(0, int(daily_special.get("current_progress", 0) or 0))
        target = max(1, int(daily_special.get("target", 1) or 1))
        ingredients = daily_special.get("ingredients") or []
        ingredient_total = sum(int(item.get("cards", 0) or 0) for item in ingredients if isinstance(item, dict))
        if ingredient_total <= 0:
            ingredient_total = max(1, int(target * 0.7))

        prep_cards = max(1, int(daily_special.get("prep_cards", max(1, int(target * 0.2))) or 1))
        if current < ingredient_total:
            return "collect"
        if current < min(target, ingredient_total + prep_cards):
            return "prepare"
        if current < target:
            return "deliver"
        return "completed"

    def _update_recipe_rush_stage(self, daily_special: Dict[str, Any]) -> None:
        daily_special["mode"] = "recipe_rush"
        daily_special["stage"] = self._recipe_rush_stage(daily_special)
        if daily_special["stage"] == "completed":
            daily_special["completed"] = True
            daily_special["status"] = "delivered"
        else:
            daily_special["completed"] = False
            daily_special["status"] = daily_special["stage"]

    def _total_xp_for_level(self, level: int) -> int:
        level = max(0, int(level or 0))
        return sum(self._xp_for_next(lvl) for lvl in range(level))

    def _apply_recipe_rush_missed_penalty(self, daily_special: Dict[str, Any]) -> List[Dict[str, Any]]:
        missed_day = daily_special.get("last_updated")
        if not missed_day or daily_special.get("completed") or daily_special.get("penalty_applied_for") == missed_day:
            return []

        conf, restaurant_conf = self._config_bundle()
        difficulty = restaurant_conf.get("difficulty", "Apprendice")
        if difficulty == "Cook":
            level_loss = 1
            coins_lost = 25
        elif difficulty == "Chef":
            level_loss = 2
            coins_lost = 75
        else:
            daily_special["penalty_applied_for"] = missed_day
            return []

        progress = self.get_progress()
        current_coins = self._get_coins_from_json()
        new_level = max(0, progress.level - level_loss)
        new_total_xp = min(progress.total_xp, self._total_xp_for_level(new_level))
        new_coins = current_coins - coins_lost

        self._update_gamification_data({
            "total_xp": new_total_xp,
            "level": new_level,
            "taiyaki_coins": new_coins,
        })

        rush_name = daily_special.get("rush_name") or tr("recipe_rush_title", "Nook Rush")
        penalty_msg = f'{rush_name} {tr("recipe_rush_penalty_suffix", "missed")}'

        daily_special["penalty_applied_for"] = missed_day
        return [{
            "id": f"recipe_rush_missed_{missed_day}",
            "name": penalty_msg,
            "description": tr(
                "recipe_rush_penalty_desc",
                "The order expired: restaurant level and Taiyaki Coins were reduced."
            ),
            "iconImage": f"{self._addon_prefix}/system_files/gamification_images/Tayaki_coin.webp",
            "iconAlt": penalty_msg,
            "textColorLight": "#2c2c2c",
            "textColorDark": "#ffffff",
            "duration": 5000,
        }]

    def _check_and_reset_daily_special(self, daily_special: Dict[str, Any]) -> bool:
        """Check if Nook Rush needs reset and update it in-place. Returns True if reset occurred."""
        if not daily_special.get("enabled", False):
            return False
            
        # Use Anki's day calculation to match the database query in _sync_daily_progress_with_db
        today = self._get_anki_today_date()
        last_updated = daily_special.get("last_updated")
        
        target = daily_special.get("target", 100)
        
        needs_reset = False
        
        if last_updated != today:
            penalty_notifications = self._apply_recipe_rush_missed_penalty(daily_special)
            if penalty_notifications:
                self._dispatch_notifications(penalty_notifications)

            daily_special["current_progress"] = 0
            daily_special["last_updated"] = today
            daily_special["last_notified_milestone"] = 0
            daily_special["last_notified_percent"] = 0
            daily_special["completed"] = False
            daily_special["status"] = "collect"
            daily_special.pop("penalty_applied_for", None)
            needs_reset = True
            
        # Recalculate if reset happened OR if target is the default 100 OR legacy state has no recipe ticket
        # OR the equipped Nook/shop changed since today's ticket was generated.
        if (
            needs_reset
            or target == 100
            or daily_special.get("mode") != "recipe_rush"
            or daily_special.get("restaurant_id") != self.get_current_theme_id()
            or daily_special.get("source") == "fallback"
        ):
            # Non-blocking: returns the cached ticket and asks the Apps Script
            # in the background when the cache is stale.
            recipe_data = self._get_daily_special_data()
            new_target = int(recipe_data.get("target", 0) or 0) if recipe_data else 0
            
            if not new_target:
                if needs_reset or target == 100 or not daily_special.get("target"):
                    # Nothing usable yet: keep the daily counter alive with a
                    # generic target/name instead of duplicating the Apps
                    # Script's recipe content here. The background fetch
                    # replaces it as soon as a real ticket arrives.
                    random.seed(today)
                    new_target = random.randint(50, 150)
                else:
                    # Already running on a fallback ticket for today - leave it
                    # alone rather than rewriting the same state on every card.
                    return needs_reset

            if new_target:
                self._apply_recipe_rush_ticket_data(daily_special, recipe_data, new_target, today)
                needs_reset = True

        return needs_reset

    def _apply_recipe_rush_ticket_data(
        self,
        daily_special: Dict[str, Any],
        recipe_data: Optional[Dict[str, Any]],
        new_target: int,
        today: str,
    ) -> None:
        """Write a (possibly fallback) Nook Rush ticket into daily_special in-place."""
        daily_special["target"] = new_target
        daily_special["mode"] = "recipe_rush"
        daily_special["recipe_id"] = (recipe_data or {}).get("recipe_id") or f"{self.get_current_theme_id()}_{today}"
        daily_special["name"] = (recipe_data or {}).get("name") or tr("recipe_rush_title", "Nook Rush")
        daily_special["description"] = (recipe_data or {}).get("description") or tr("complete_your_reviews")
        daily_special["difficulty"] = (recipe_data or {}).get("difficulty", "common")
        daily_special["ingredients"] = (recipe_data or {}).get("ingredients", [])
        daily_special["prep_cards"] = (recipe_data or {}).get("prep_cards", max(1, int(new_target * 0.2)))
        daily_special["delivery_cards"] = (recipe_data or {}).get("delivery_cards", max(1, int(new_target * 0.1)))
        daily_special["preparation"] = (recipe_data or {}).get("preparation", "")
        daily_special["delivery"] = (recipe_data or {}).get("delivery", "")
        # restaurant_id always reflects the equipped Nook/shop. A missing
        # ticket is marked through "source" below instead of by blanking this,
        # which used to make every answered card re-enter the fetch path.
        daily_special["restaurant_id"] = (
            recipe_data.get("restaurant_id", self.get_current_theme_id())
            if recipe_data
            else self.get_current_theme_id()
        )
        daily_special["source"] = (recipe_data or {}).get("source") or "fallback"
        daily_special["restaurant_name"] = (recipe_data or {}).get("restaurant_name", "")
        daily_special["rush_name"] = (recipe_data or {}).get("rush_name") or tr("recipe_rush_title", "Nook Rush")
        daily_special["ingredients_label"] = (recipe_data or {}).get("ingredients_label", "")
        daily_special["stage_collect_label"] = (recipe_data or {}).get("stage_collect_label", "")
        daily_special["stage_prepare_label"] = (recipe_data or {}).get("stage_prepare_label", "")
        daily_special["stage_deliver_label"] = (recipe_data or {}).get("stage_deliver_label", "")
        daily_special["stage_completed_label"] = (recipe_data or {}).get("stage_completed_label", "")
        daily_special["xp_reward"] = (recipe_data or {}).get("xp_reward", 0)
        self._update_recipe_rush_stage(daily_special)

    def force_resync_recipe_rush(self) -> Tuple[bool, str]:
        """Manually refetch today's Nook Rush ticket for the currently equipped Nook/shop.

        Bypasses the ticket cache and the "already have a ticket for today" guard, so it
        always asks the Apps Script for a fresh pick from the equipped shop's Rush group,
        even late in the Anki day. Keeps today's current_progress untouched.
        """
        self._recipe_rush_ticket_cache = {}

        today = self._get_anki_today_date()
        state = self._get_gamification_state()
        daily_special_state = state.get("daily_special", {})
        daily_special = dict(daily_special_state) if isinstance(daily_special_state, dict) else {}

        recipe_data = self._get_daily_special_data(blocking=True)
        new_target = int(recipe_data.get("target", 0) or 0) if recipe_data else 0
        if not new_target:
            reason = self._last_recipe_rush_error or "Unknown error."
            return False, tr(
                "recipe_rush_sync_failed",
                "Could not get a Rush from the Apps Script for the equipped Nook: {reason}",
            ).format(reason=reason)

        daily_special["last_updated"] = today
        daily_special["current_progress"] = daily_special.get("current_progress", 0)
        self._apply_recipe_rush_ticket_data(daily_special, recipe_data, new_target, today)
        self._update_gamification_daily_special(daily_special)
        self.invalidate_daily_cache()

        return True, daily_special.get("rush_name") or daily_special.get("name") or tr("recipe_rush_title", "Nook Rush")

    def _sync_daily_progress_with_db(self, daily_special: Dict[str, Any]) -> bool:
        """Syncs the daily special progress with the actual review count from the database."""
        if not daily_special.get("enabled", False):
            return False
            
        if not mw.col or not getattr(mw.col, "db", None):
            return False
            

        # Optimization: Check cache to avoid frequent DB hits
        # Only check once every 5 seconds for more responsive updates
        now = time.time()
        last_check = getattr(self, "_last_daily_sync_time", 0)
        cached_count = getattr(self, "_cached_daily_count", -1)
        
        # If cache is fresh (less than 5s), allow skipping DB check if we have a value
        if now - last_check < 5 and cached_count >= 0:
             # But if current_progress is less than cached, we might want to update it
             today_reviews = cached_count
        else:
            try:
                # Get today's review count using direct database query
                # This correctly counts only actual reviews from today, not deck resets or other operations
                # type IN (0,1,2,3) filters out manual operations (type 4 = manual rescheduling/resets)
                day_cutoff = mw.col.sched.day_cutoff
                today_start = day_cutoff - 86400  # 24 hours before cutoff (start of today)
                today_reviews = mw.col.db.scalar(
                    "SELECT COUNT() FROM revlog WHERE type IN (0,1,2,3) AND id >= ?",
                    today_start * 1000
                ) or 0
                
                # Update cache
                self._last_daily_sync_time = now
                self._cached_daily_count = today_reviews
            except Exception as e:
                # print(f"Onigiri: Error syncing daily progress: {e}")
                return False

        current_progress = daily_special.get("current_progress", 0)
        
        updated = False
        if current_progress != today_reviews:
            # Grant XP for synced reviews
            if today_reviews > current_progress:
                diff = today_reviews - current_progress
                xp_to_award = diff * XP_PER_REVIEW
                # Use reason='sync' to allow _add_xp to suppress notifications
                notifications = self._add_xp(xp_to_award, reason="sync", review_count=diff)
                self._dispatch_notifications(notifications)

            daily_special["current_progress"] = max(0, today_reviews)
            self._update_recipe_rush_stage(daily_special)
            
            # Silently update notified percent to avoid stale notifications
            target = daily_special.get("target", 100)
            if target > 0:
                percent = (today_reviews / target) * 100
                current_notified = daily_special.get("last_notified_percent", 0)
                for m in [25, 50, 75]:
                    if percent >= m and m > current_notified:
                        daily_special["last_notified_percent"] = m
            
            updated = True
            
        # Check for completion after sync (Always check if target met)
        target = daily_special.get("target", 100)
        if today_reviews >= target:
            notifications = self._handle_daily_special_completion(daily_special)
            self._dispatch_notifications(notifications)
            if notifications:
                updated = True
                
        return updated

    def _calculate_daily_target(self) -> Optional[int]:
        """
        Calculates the daily target using the centralized logic.
        """
        today = self._get_anki_today_date()
        restaurant_id = self.get_current_theme_id()
        
        # Check cache explicitly ensuring restaurant_id matches to support profile switching
        if (self._daily_target_cache.get('date') == today and 
            self._daily_target_cache.get('restaurant_id') == restaurant_id):
            return self._daily_target_cache.get('target')

        special_data = self._get_daily_special_data()
        if special_data:
            target = special_data.get('target', 100)
            
            # Update cache
            self._daily_target_cache = {
                'date': today,
                'target': target,
                'restaurant_id': restaurant_id
            }
            return target
            
        return None

    def get_store_data(self) -> Dict[str, Any]:
        """Get data for the store (coins, inventory, available items)."""
        # Try to read from gamification.json first as it's the source of truth for coins
        coins = 0
        owned = ["default"]
        current = "default"
        
        try:
            state = self._get_gamification_state()
            coins = int(state.get('taiyaki_coins', 0))
            owned = state.get('owned_items', ["default"])
            current = state.get('current_theme_id', "default")
            
            # Fallback to config if state is empty (migration)
            if not state:
                 conf = config.get_config()
                 restaurant_conf = conf.get("restaurant_level", {})
                 if not restaurant_conf:
                    restaurant_conf = conf.get("achievements", {}).get("restaurant_level", {})
                 owned = restaurant_conf.get("owned_items", ["default"])
                 current = restaurant_conf.get("current_theme_id", "default")
                 
        except Exception as e:
            print(f"Error reading gamification.json: {e}")
            coins = 0
            owned = ["default"]
            current = "default"
        
        # Ensure default is always owned
        if "default" not in owned:
            owned.append("default")

        # Focus Dango and Motivated Mochi are Settings rewards, never coin
        # purchases.  Keep their entitlement in the one store payload used by
        # both WebUI pages.
        conf = config.get_config()
        focus_enabled = bool(conf.get("achievements", {}).get("focusDango", {}).get("enabled", False))
        mochi_enabled = bool(conf.get("mochi_messages", {}).get("enabled", False))
        for item_id, enabled in (("focus_dango", focus_enabled), ("motivated_mochi", mochi_enabled)):
            if enabled and item_id not in owned:
                owned.append(item_id)
            elif not enabled and item_id in owned:
                owned.remove(item_id)

        # The old store adjusted prices by the selected Nook difficulty.  Do
        # that at the manager boundary so the displayed price and charged price
        # cannot drift apart between clients.
        difficulty = conf.get("restaurant_level", {}).get("difficulty", "Apprendice")
        multiplier = 4 if difficulty == "Chef" else 2 if difficulty == "Cook" else 1
        restaurants = get_localized_restaurants()
        evolutions = get_localized_evolutions()
        shops = get_localized_shops()
        for group in (restaurants, evolutions, shops):
            for item in group.values():
                if isinstance(item.get("price"), int):
                    item["price"] *= multiplier
            
        return {
            "coins": coins,
            "owned_items": owned,
            "current_theme_id": current,
            "restaurants": restaurants,
            "evolutions": evolutions,
            "shops": shops
        }

    def refresh_state(self) -> None:
        """Force a reload of the gamification state from disk."""
        if self._gamification_manager:
            self._gamification_manager.reload()

    def _get_gamification_state(self) -> Dict[str, Any]:
        """Read current state from GamificationManager."""
        return self._gamification_manager.get_restaurant_data()

    def _get_coins_from_json(self) -> int:
        """Read current coins from gamification.json."""
        state = self._get_gamification_state()
        return int(state.get('taiyaki_coins', 0))

    def buy_item(self, item_id: str) -> Tuple[bool, str]:
        """Buy an item from the store."""
        # Read current state from gamification.json (Source of Truth for BOTH coins and items)
        state = self._get_gamification_state()
        coins = self._get_coins_from_json()
        owned = state.get("owned_items", ["default"])
        
        # Ensure list is valid
        if not isinstance(owned, list):
            owned = ["default"]
        
        if item_id in owned:
            return False, "Item already owned."
            
        item = RESTAURANTS.get(item_id) or EVOLUTIONS.get(item_id) or SHOPS.get(item_id)
        if not item:
            return False, "Item not found."

        if item_id in {"focus_dango", "motivated_mochi"}:
            return False, "This Nook is unlocked from its matching setting."

        prerequisites = {
            "restaurant_evo_ii": "restaurant_evo_i",
            "restaurant_evo_iii": "restaurant_evo_ii",
            "restaurant_evo_iv": "restaurant_evo_iii",
            "restaurant_evo_legendary": "restaurant_evo_iv",
            "restaurant_evo_garden": "restaurant_evo_legendary",
            "restaurant_evo_heaven": "restaurant_evo_garden",
            "restaurant_evo_paradise": "restaurant_evo_heaven",
        }
        prerequisite = prerequisites.get(item_id)
        if prerequisite and prerequisite not in owned:
            return False, "Buy the previous Sushi Evolution first."

        conf = config.get_config()
        difficulty = conf.get("restaurant_level", {}).get("difficulty", "Apprendice")
        multiplier = 4 if difficulty == "Chef" else 2 if difficulty == "Cook" else 1
        price = int(item["price"]) * multiplier
        if coins < price:
            return False, "Not enough Taiyaki Coins."
            
        # Deduct coins
        new_coins = coins - price
        
        # Add to owned
        owned.append(item_id)
            
        # Update gamification.json directly (a purchase is written through,
        # never left sitting in the queued-write buffer)
        self._update_gamification_data({
            "owned_items": owned, 
            "taiyaki_coins": new_coins
        }, immediate=True)
        
        return True, "Purchase successful!"

    def equip_item(self, item_id: str) -> Tuple[bool, str]:
        """Equip a restaurant theme."""
        # Include Settings-granted themes (Focus Dango / Motivated Mochi) in
        # addition to the persisted coin-purchase inventory.
        owned = self.get_store_data().get("owned_items", ["default"])
        
        if item_id != "default" and item_id not in owned:
            return False, "Item not owned."
            
        # Sync to json
        self._update_gamification_data({"current_theme_id": item_id}, immediate=True)
        
        return True, "Theme equipped!"

    def get_current_theme_color(self) -> Optional[str]:
        """Get the hex color of the current theme."""
        state = self._get_gamification_state()
        current_id = state.get("current_theme_id", "default")
        
        if current_id == "default":
            return "#D49083"
            
        item = RESTAURANTS.get(current_id) or EVOLUTIONS.get(current_id) or SHOPS.get(current_id)
        if item:
            return item["theme"]
        return None

    def get_current_theme_image(self) -> Optional[str]:
        """Get the image filename of the current theme."""
        state = self._get_gamification_state()
        current_id = state.get("current_theme_id", "default")

        if current_id == "default":
            return "sushi/onigiri_stand.webp"

        item = RESTAURANTS.get(current_id) or EVOLUTIONS.get(current_id) or SHOPS.get(current_id)
        if item and item.get("image"):
            return item["image"]
        return "sushi/onigiri_stand.webp"

    def get_current_theme_id(self) -> str:
        """Get the ID of the current theme."""
        state = self._get_gamification_state()
        return state.get("current_theme_id", "default")

    def on_reviewer_did_answer(self, reviewer: Any, card: Any, ease: int) -> None:
        """Hook handler for review completion."""
        # Map ease to XP
        # 1: Again -> 1 XP
        # 2: Hard -> 3 XP
        # 3: Good -> 5 XP
        # 4: Easy -> 10 XP
        # xp_map = {1: 1, 2: 3, 3: 5, 4: 10}
        # xp = xp_map.get(ease, 5)
        # notifications = self.add_review_xp(xp, count=1)
        # self._dispatch_notifications(notifications)
        # OPTIMIZATION: Debounce or batch this?
        # Actually, for reviews, immediate feedback is good. 
        # But let's remove the print at least.
        xp_map = {1: 1, 2: 3, 3: 5, 4: 10}
        xp = xp_map.get(ease, 5)
        # print(f"Onigiri: Review completed. Ease: {ease}, XP to award: {xp}")
        self._xp_history.append(xp)
        notifications = self.add_review_xp(xp, count=1)
        self._dispatch_notifications(notifications)
        # The reviewer chip is refreshed by patcher.on_reviewer_did_answer_card,
        # which is registered on the same hook - doing it here as well meant
        # building the chip and evaluating JS twice per answered card.

    def on_state_did_undo(self, changes: Any = None) -> None:
        """Hook handler for undoing a review (state_did_undo)."""
        from aqt import mw
        if mw.state != "review":
            return
            
        if not self._xp_history:
            return

        xp_to_undo = self._xp_history.pop()
        
        # We pass -xp_to_undo. count=-1 ensures daily progress also subtracts 1.
        notifications = self.add_review_xp(-xp_to_undo, count=-1)
        self._dispatch_notifications(notifications)
        
        # Directly update the reviewer chip using patcher's function
        try:
            # Import patcher from parent package
            from .. import patcher
            if hasattr(patcher, 'update_reviewer_chip'):
                patcher.update_reviewer_chip()
        except Exception:
            pass  # Silently fail if patcher not available


    # Legacy/Fallback hook handler if needed, or alias for consistency
    def on_reviewer_did_undo_answer(self, *args: Any) -> None:
        self.on_state_did_undo()



    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _dispatch_notifications(self, notifications: List[Dict[str, Any]]) -> None:
        if notifications is None:
             notifications = []
        
        # Suppress popup notifications while Silent mode is on OR when the
        # user has explicitly disabled Nook Level notifications
        conf = config.get_config_readonly()
        silent_mode = conf.get("onigiri_reviewer_silent_notifications", False)
        restaurant_notifications_on = conf.get("restaurant_level", {}).get("notifications_enabled", True)
        if silent_mode or not restaurant_notifications_on:
            notifications = []
        
        # Always fetch latest progress to update UI, even if no notifications are present

            
        from aqt import mw
        
        state = getattr(mw, "state", None)
        webviews = []

        reviewer = getattr(mw, "reviewer", None)
        overview = getattr(mw, "overview", None)
        deck_browser = getattr(mw, "deckBrowser", None)

        if state == "overview" and overview and getattr(overview, "web", None):
            webviews.append(overview.web)
        elif state == "deckBrowser" and deck_browser and getattr(deck_browser, "web", None):
            webviews.append(deck_browser.web)

        # Fallbacks if state-based lookup failed
        for web in [overview and getattr(overview, "web", None), deck_browser and getattr(deck_browser, "web", None)]:
            if web and web not in webviews:
                webviews.append(web)

        # Serialize data
        payload = json.dumps(notifications, ensure_ascii=False)
        if notifications and state == "review":
            reviewer_web = reviewer and getattr(reviewer, "web", None)
            if reviewer_web:
                notification_script = (
                    "(function() {"
                    "if (window.OnigiriNotifications) {"
                    f"const items = {payload};"
                    "items.forEach(item => window.OnigiriNotifications.show(item));"
                    "}"
                    "})();"
                )
                try:
                    reviewer_web.eval(notification_script)
                except Exception:
                    pass
        
        # Get latest progress data
        progress = self.get_progress_payload()
        progress_json = json.dumps(progress, ensure_ascii=False)

        # Enhanced script to update UI widgets.
        # WRAPPED IN IIFE TO PREVENT "Identifier has already been declared" ERRORS
        script = (
            "(function() {"
            f"const progress = {progress_json};"
            "try {"
                # 1. Update Deck Browser Widget (Nook Level)
                # Update Progress Bar
                "const lpFill = document.querySelector('.level-progress-container .lp-fill');"
                "if (lpFill) lpFill.style.width = (progress.progressFraction * 100) + '%';"
                
                # Update XP Text
                "const lpText = document.querySelector('.level-progress-container .lp-text');"
                "if (lpText) {"
                    "if (progress.xpToNextLevel > 0) {"
                        # Format numbers with commas
                         "lpText.textContent = `${progress.xpIntoLevel.toLocaleString()} / ${progress.xpToNextLevel.toLocaleString()} XP`;"
                    "} else {"
                         "lpText.textContent = `${progress.totalXp.toLocaleString()} XP total`;"
                    "}"
                "}"
                
                # Update Level Number
                "const levelVal = document.querySelector('.level-value');"
                "if (levelVal) levelVal.textContent = progress.level;"
                
                # 3. Update Profile Page / Expanded View Elements
                # Update Profile Bar Fill
                "const prlFill = document.querySelector('.prl-progress-fill');"
                "if (prlFill) prlFill.style.width = (progress.progressFraction * 100) + '%';"
                
                # Update Restaurant Name (if changed, though unlikely on undo)
                "const nameHeader = document.querySelector('.rl-hero-copy h1');"
                "if (nameHeader && progress.name) nameHeader.textContent = progress.name;"
                
                # Update XP Detail on Profile Page
                "const xpDetail = document.querySelector('[data-bind=\"xp_detail\"]');"
                "if (xpDetail) {"
                     "if (progress.xpToNextLevel > 0) {"
                        "xpDetail.textContent = `${progress.xpIntoLevel.toLocaleString()} / ${progress.xpToNextLevel.toLocaleString()} XP`;"
                     "} else {"
                        "xpDetail.textContent = `${progress.totalXp.toLocaleString()} XP total`;"
                     "}"
                "}"
                
                # Update Total XP on Profile Page
                "const totalXp = document.querySelector('[data-bind=\"total_xp\"]');"
                "if (totalXp) totalXp.textContent = progress.totalXp.toLocaleString();"
                
                # Update Level on Profile Page
                "const levelBind = document.querySelector('[data-bind=\"level\"]');"
                "if (levelBind) levelBind.textContent = progress.level;"

            "} catch (e) { console.error('Onigiri UI Update Error:', e); }"
            "})();"
        )



        for web in webviews:
            if not web:
                continue
            try:
                web.eval(script)
                break
            except Exception:
                continue

    def _is_kitchen_closed(self, timestamp: Optional[float] = None) -> bool:
        """Check if the kitchen is closed based on the current time and configured closing time.
        
        Args:
            timestamp: Optional Unix timestamp to check. If None, uses current time.
            
        Returns:
            bool: True if the kitchen is closed (past the configured closing time), False otherwise.
        """
        from aqt import mw
        
        # Get the current time or use the provided timestamp
        now = time.localtime(timestamp if timestamp is not None else time.time())
        
        # Get the configured closing time (default to 4:00 AM)
        # Use Anki's native rollover setting
        close_hour = int(mw.col.conf.get("rollover", 4))
        close_minute = 0
        
        # Create a time object for the kitchen close time
        close_time = now.tm_hour * 60 + now.tm_min
        close_time_threshold = close_hour * 60 + close_minute
        
        # Kitchen is closed if current time is after the close time
        return close_time >= close_time_threshold

    def _handle_daily_special_completion(self, daily_special: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle completion of a Nook Rush ticket and update gamification data.
        
        Returns:
            List of notifications to display
        """
        if not daily_special or not daily_special.get("enabled", False):
            return []
            
        try:
            from .gamification import get_gamification_manager
            gamification = get_gamification_manager()
            
            # Use Anki's day calculation for consistency with _check_and_reset_daily_special
            today = self._get_anki_today_date()
            special_id = f"recipe_rush_{today}"
            
            # Check if already completed to prevent double-awarding
            existing = next((s for s in gamification.daily_specials if s.id == special_id and s.completed), None)
            if existing:
                return []

            self._update_recipe_rush_stage(daily_special)
            special_data = daily_special if daily_special.get("mode") == "recipe_rush" else self._get_daily_special_data()
            
            if special_data:
                special_name = special_data.get("name")
                special_desc = special_data.get("description")
                difficulty = special_data.get("difficulty", "Common").lower() # Backend seems to case-insensitively store it, but let's check
                # JS uses lowercase 'common', 'rare' in keys, but Titles in display.
                # Let's Capitalize for display/storage if that's the pattern.
                # Looking at original code: difficulty = "Common" (Capitalized)
                difficulty = difficulty.capitalize() 
                target = int(special_data.get("target", 100) or 100)
            else:
                # Fallback if something goes wrong
                rush_name = daily_special.get("rush_name") or tr("recipe_rush_title", "Nook Rush")
                special_name = f"{rush_name} - {today}"
                special_desc = "Complete your daily review goal"
                target = int(daily_special.get("target", 100) or 100)
                if target <= 50:
                    difficulty = "Common"
                elif target <= 100:
                    difficulty = "Uncommon"
                else:
                    difficulty = "Rare"
                
            # Calculate XP - 5 XP per card with a bonus for difficulty
            # Use the XP reward from special_data if available, otherwise calculate
            # JS logic: xp = target * 5 * multiplier. max(50, xp).
            xp_earned = 0
            
            # Re-calculate based on verified difficulty to ensure server-side trust
            base_xp = target * 5
            multiplier = 1.0
            
            diff_lower = difficulty.lower()
            if diff_lower == "common":
                multiplier = 1.0
            elif diff_lower == "uncommon":
                multiplier = 1.2
            elif diff_lower == "rare":
                multiplier = 1.5
            elif diff_lower == "epic":
                multiplier = 2.0
            elif diff_lower == "legendary":
                multiplier = 2.5
                
            xp_earned = int(special_data.get("xp_reward", 0) or 0) if special_data else 0
            if xp_earned <= 0:
                xp_earned = int(base_xp * multiplier)
                xp_earned = max(50, xp_earned)

            # Update gamification data
            gamification.add_daily_special(
                special_id=special_id,
                name=special_name,
                description=special_desc,
                difficulty=difficulty.lower(), # Store as lowercase in history for consistency with JS checks
                target_cards=target,
                completed=True,
                cards_completed=target,
                xp_earned=xp_earned
            )

            daily_special["completed"] = True
            daily_special["stage"] = "completed"
            daily_special["status"] = "delivered"
            daily_special["current_progress"] = max(int(daily_special.get("current_progress", 0) or 0), target)
            self._update_gamification_daily_special(daily_special)
            
            # Award XP and get notifications
            notifications = self._add_xp(xp_earned, reason="daily_special")
            
            # Add a specific notification for daily special completion
            notifications.append({
                'id': special_id,
                'name': f'{tr("recipe_rush_delivered", "Recipe delivered")}: {special_name}',
                'description': f"{special_desc} (+{xp_earned} XP)",
                'iconImage': f"{self._addon_prefix}/system_files/gamification_images/onigiri_trophy.webp",
                'iconAlt': "Nook Rush Trophy",
                'type': 'xp',
                'amount': xp_earned,
                'reason': 'recipe_rush',
                'special': {
                    'id': special_id,
                    'name': special_name,
                    'difficulty': difficulty,
                    'target': target,
                    'xp_earned': xp_earned
                }
            })
            
            return notifications
            
        except Exception as e:
            print(f"Error updating gamification data for daily special: {e}")
            return [{
                'id': 'daily_special_error',
                'name': 'Error',
                'description': f'Error processing daily special: {str(e)}',
                'type': 'error'
            }]

    def _get_daily_special_data(self, blocking: bool = False) -> Optional[Dict[str, Any]]:
        """
        Return today's Nook Rush ticket from the Apps Script.

        All recipe content (names, descriptions, ingredients, per-shop "Rush"
        names) lives in the Apps Script - the add-on has no local recipe list
        of its own. If the server is unreachable, callers fall back to a
        generic numeric target rather than a duplicated recipe database.
        """
        today = self._get_anki_today_date()
        current_restaurant_id = self.get_current_theme_id()
        return self._fetch_recipe_rush_ticket(today, current_restaurant_id, blocking=blocking)

    def _update_gamification_data(self, updates: Dict[str, Any], immediate: bool = False) -> None:
        """Update the gamification data via manager."""
        # Fix: Automatically update security token if coins are changed
        if "taiyaki_coins" in updates:
            # We don't generate security token anymore
            pass
            
        self._gamification_manager.update_restaurant_data(updates, immediate=immediate)

    def _update_gamification_daily_special(self, daily_special: Dict[str, Any]) -> None:
        """Update daily special state via manager."""
        state_keys = [
            "mode",
            "recipe_id",
            "name",
            "description",
            "difficulty",
            "target",
            "target_cards",
            "current_progress",
            "ingredients",
            "prep_cards",
            "delivery_cards",
            "preparation",
            "delivery",
            "restaurant_id",
            "restaurant_name",
            "rush_name",
            "ingredients_label",
            "stage_collect_label",
            "stage_prepare_label",
            "stage_deliver_label",
            "stage_completed_label",
            "stage",
            "status",
            "completed",
            "xp_reward",
            "source",
            "last_updated",
            "last_notified_milestone",
            "last_notified_percent",
            "penalty_applied_for",
        ]
        state_to_save = {key: daily_special.get(key) for key in state_keys if key in daily_special}
        self._gamification_manager.update_restaurant_data({"daily_special_update": state_to_save})

    def _add_xp(self, amount: int, *, reason: str, review_count: int = 0) -> List[Dict[str, Any]]:
        if amount == 0:
            return []


        conf = config.get_config_readonly()
        restaurant_conf = self._restaurant_conf_readonly()
        if not restaurant_conf.get("enabled", False):
            print("Onigiri: Nook Level disabled in config, not awarding XP.")
            return []

        # Read current state from gamification.json (source of truth for XP/level)
        game_state = self._get_gamification_state()
        previous_level = int(game_state.get("level", restaurant_conf.get("level", 0)))
        previous_total = int(game_state.get("total_xp", restaurant_conf.get("total_xp", 0)))
        new_total = previous_total + amount

        level, xp_into_level, xp_to_next = self._collapse_xp(new_total)
        
        # Store previous values for notification checks
        previous_xp_into_level = xp_into_level - amount
        if previous_level < level:
            previous_xp_into_level = self._xp_for_next(previous_level)
        
        # Check for level up notification
        notifications = []
        current_coins = self._get_coins_from_json() # Get current coins from JSON
        new_coins = current_coins
        
        if level > previous_level:
            notifications.extend(self._create_level_up_notification(level))
            # Award Taiyaki Coins
            coins_gained = 0
            for lvl in range(previous_level + 1, level + 1):
                coins_gained += lvl * 5
            new_coins = current_coins + coins_gained
            
            # Coins live in gamification.json only; nothing to strip from the
            # settings copy here (this config is read-only and never saved).
                
            notifications.append({
                "id": "taiyaki_coins_gained",
                "name": "Taiyaki Coins!",
                "description": f"You earned {coins_gained} Taiyaki Coins!",
                "iconImage": f"{self._addon_prefix}/system_files/gamification_images/Tayaki_coin.webp",
                "iconAlt": "Taiyaki Coins",
                "textColorLight": "#2c2c2c",
                "textColorDark": "#ffffff",
                "duration": 4000
            })
        elif level < previous_level:
            # Handle Level Down (Undo)
            coins_lost = 0
            for lvl in range(previous_level, level, -1):
                coins_lost += lvl * 5
            
            new_coins = current_coins - coins_lost
            # We allow negative coins as "debt" if they spent it already
            
            notifications.append({
                "id": "taiyaki_coins_lost",
                "name": "Level Lost",
                "description": f"Undoing review... {coins_lost} coins removed.",
                "iconImage": f"{self._addon_prefix}/system_files/gamification_images/Tayaki_coin.webp",
                "iconAlt": "Taiyaki Coins",
                "textColorLight": "#2c2c2c",
                "textColorDark": "#ffffff",
                "duration": 3000
            })

        
        # Update the Nook Level and total XP in gamification.json
        # We NO LONGER write this to config.json
        
        update_data = {
            "total_xp": new_total,
            "level": level,
        }
        
        if new_coins != current_coins:
            update_data["taiyaki_coins"] = new_coins
            
        self._update_gamification_data(update_data)
        # print(f"Onigiri: XP awarded. New Total: {new_total}, Level: {level}")
        
        # Handle daily special progress and notifications
        # Get settings from config
        daily_special_conf = conf.get("daily_special", {})
        if not daily_special_conf and "achievements" in conf:
            daily_special_conf = conf["achievements"].get("daily_special", {})
            
        if daily_special_conf.get("enabled", False):
            # Get state from gamification.json
            daily_special_state = game_state.get("daily_special", {})
            
            # Construct Nook Rush object while preserving ticket metadata.
            daily_special = dict(daily_special_state) if isinstance(daily_special_state, dict) else {}
            daily_special.update({
                "enabled": True,
                "target": daily_special.get("target", daily_special_conf.get("target", 100)),
                "current_progress": daily_special.get("current_progress", 0),
                "last_updated": daily_special.get("last_updated"),
                "last_notified_milestone": daily_special.get("last_notified_milestone", 0),
                "last_notified_percent": daily_special.get("last_notified_percent", 0),
            })
            
            # Ensure we're working with fresh daily stats
            self._check_and_reset_daily_special(daily_special)

            # If this is a daily special completion, we've already handled it
            if reason == "daily_special":
                pass  # We'll add the notification in _handle_daily_special_completion
            elif reason == "review":
                # For regular reviews, update progress
                current = daily_special.get("current_progress", 0)
                new_progress = current + review_count
                target = daily_special.get("target", 100)
                
                # Check for daily special completion
                # Ensure we only complete if we are making forward progress (review_count > 0)
                # This prevents Undo (-1) from triggering completion if we were already above target
                if new_progress >= target and review_count > 0:
                    # Daily special completed - handle it
                    special_notifications = self._handle_daily_special_completion(daily_special)
                    notifications.extend(special_notifications)
                
                # Update progress
                daily_special["current_progress"] = max(0, new_progress)
                self._update_recipe_rush_stage(daily_special)

                
                # Check for progress milestones (25%, 50%, 75%)
                progress_percent = (new_progress / target) * 100 if target > 0 else 0
                last_notified = daily_special.get("last_notified_percent", 0)
                
                for milestone in [25, 50, 75]:
                    if (last_notified < milestone <= progress_percent and 
                        current < target and 
                        new_progress < target):
                        rush_name = daily_special.get("rush_name") or tr("recipe_rush_title", "Nook Rush")
                        notifications.append({
                            'id': f"recipe_rush_progress_{milestone}",
                            'name': f'{rush_name}: {milestone}% complete!',
                            'description': f"You've reached {milestone}% of today's recipe ({new_progress}/{target}).",
                            'iconImage': f"{self._addon_prefix}/system_files/gamification_images/onigiri_trophy.webp",
                            'iconAlt': "Nook Rush Progress",
                            'type': 'info',
                            'progress': milestone,
                            'current': new_progress,
                            'target': target
                        })
                        daily_special["last_notified_percent"] = milestone
                        break
            
            # Save the updated daily special state to gamification.json
            self._update_gamification_daily_special(daily_special)
        
        # We NO LONGER write to config.json here!
        # config.write_config(conf)
        
        return notifications
    
    def _get_difficulty_multiplier(self) -> int:
        diff = self._restaurant_conf_readonly().get("difficulty", "Apprendice")
        if diff == "Cook": return 2
        if diff == "Chef": return 4
        return 1

    def _xp_for_next(self, level: int) -> int:
        return 50 * (2 * level + 1) * self._get_difficulty_multiplier()

    def _collapse_xp(self, total_xp: int) -> Tuple[int, int, int]:
        """Calculate level and XP progress based on total XP.
        
        Args:
            total_xp: Total XP earned by the user
            
        Returns:
            Tuple of (current_level, xp_into_level, xp_to_next_level)
        """
        level = 0
        xp_needed = 0
        # The multiplier is constant for the whole walk; reading it per level
        # made this loop cost one config lookup per level the user has.
        multiplier = self._get_difficulty_multiplier()
        
        while True:
            xp_for_next = 50 * (2 * level + 1) * multiplier
            if total_xp < xp_needed + xp_for_next:
                return level, total_xp - xp_needed, xp_for_next
            xp_needed += xp_for_next
            level += 1

    def _restaurant_conf_readonly(self) -> Dict[str, Any]:
        """Nook Level settings for read-only callers, with defaults filled in.

        get_config() deep-copies the whole settings file on every call, which
        the answer hook was paying dozens of times per card. This reads the
        shared cached config instead and never hands out a dict the caller may
        mutate - the returned mapping is a small merge, not the live config.
        """
        conf = config.get_config_readonly()
        restaurant_conf = conf.get("restaurant_level")
        if not restaurant_conf and isinstance(conf.get("achievements"), dict):
            restaurant_conf = conf["achievements"].get("restaurant_level")
        merged = dict(config.DEFAULTS.get("restaurant_level", {}))
        if isinstance(restaurant_conf, dict):
            merged.update(restaurant_conf)
        return merged

    def _config_bundle(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        conf = config.get_config()
        
        # Get restaurant_level from root, fallback to defaults if missing
        # We don't check achievements anymore as config.get_config handles migration
        defaults = config.DEFAULTS.get("restaurant_level", {})
        restaurant_conf = conf.get("restaurant_level")
        
        if restaurant_conf is None:
            # If not in root, check achievements just in case (double safety)
            if "achievements" in conf and "restaurant_level" in conf["achievements"]:
                restaurant_conf = conf["achievements"]["restaurant_level"]
            else:
                restaurant_conf = copy.deepcopy(defaults)
                conf["restaurant_level"] = restaurant_conf
        
        # Ensure defaults
        for key, value in defaults.items():
            if key not in restaurant_conf:
                restaurant_conf[key] = copy.deepcopy(value)
            
        return conf, restaurant_conf

    def _update_state(self, updates: Dict[str, Any]) -> None:
        conf, restaurant_conf = self._config_bundle()
        restaurant_conf.update(updates)
        conf["restaurant_level"] = restaurant_conf
        config.write_config(conf)

    def _create_level_up_notification(self, new_level: int) -> List[Dict[str, Any]]:
        """Create a notification for leveling up."""
        # Get the current theme image
        theme_image = self.get_current_theme_image()
        if theme_image:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/nook_folder/{theme_image}"
        else:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/nook_folder/sushi/onigiri_stand.webp"
        
        return [{
            "id": "restaurant_level_up",
            "name": tr("level_unlocked_msg").format(level=new_level),
            "description": tr("level_unlocked_desc").format(level=new_level),
            "iconImage": icon_path,
            "iconAlt": tr("level_unlocked_msg").format(level=new_level),
            "textColorLight": "#2c2c2c",
            "textColorDark": "#ffffff",
            "duration": 5000
        }]

    def _create_half_level_notification(self, level: int, xp_into_level: int, xp_to_next: int) -> List[Dict[str, Any]]:
        """Create a notification for reaching 50% of the current level."""
        # Get the current theme image
        theme_image = self.get_current_theme_image()
        if theme_image:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/nook_folder/{theme_image}"
        else:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/nook_folder/sushi/onigiri_stand.webp"
        
        progress = (xp_into_level / xp_to_next) * 100
        return [{
            "id": "restaurant_level_progress",
            "name": tr("level_progress_msg").format(level=level),
            "description": tr("level_progress_desc").format(percent=int(progress), next_level=level + 1),
            "iconImage": icon_path,
            "iconAlt": tr("level_progress_msg").format(level=level),
            "textColorLight": "#2c2c2c",
            "textColorDark": "#ffffff",
            "duration": 4000
        }]

    def _create_daily_special_complete_notification(self) -> List[Dict[str, Any]]:
        """Create a notification for completing the daily special."""
        # Get the current theme image
        theme_image = self.get_current_theme_image()
        if theme_image:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/nook_folder/{theme_image}"
        else:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/nook_folder/sushi/onigiri_stand.webp"
        
        return [{
            "id": "daily_special_complete",
            "name": tr("daily_special_complete_msg"),
            "description": tr("daily_special_complete_desc"),
            "iconImage": icon_path,
            "iconAlt": tr("daily_special_complete_msg"),
            "textColorLight": "#2c2c2c",
            "textColorDark": "#ffffff",
            "duration": 5000
        }]

    def _create_daily_special_75_notification(self, target: int, progress: int) -> List[Dict[str, Any]]:
        """Create a notification for reaching 75% of the daily special."""
        # Get the current theme image
        theme_image = self.get_current_theme_image()
        if theme_image:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/nook_folder/{theme_image}"
        else:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/nook_folder/sushi/onigiri_stand.webp"
        
        remaining = target - progress
        return [{
            "id": "daily_special_progress_75",
            "name": tr("daily_special_progress_msg"),
            "description": tr("daily_special_75_desc").format(remaining=remaining),
            "iconImage": icon_path,
            "iconAlt": tr("daily_special_progress_msg"),
            "textColorLight": "#2c2c2c",
            "textColorDark": "#ffffff",
            "duration": 4000
        }]

    def _create_daily_special_50_notification(self, target: int, progress: int) -> List[Dict[str, Any]]:
        """Create a notification for reaching 50% of the daily special."""
        # Get the current theme image
        theme_image = self.get_current_theme_image()
        if theme_image:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/nook_folder/{theme_image}"
        else:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/nook_folder/sushi/onigiri_stand.webp"
        
        remaining = target - progress
        return [{
            "id": "daily_special_progress_50",
            "name": tr("daily_special_progress_msg"),
            "description": tr("daily_special_50_desc").format(remaining=remaining),
            "iconImage": icon_path,
            "iconAlt": tr("daily_special_progress_msg"),
            "textColorLight": "#2c2c2c",
            "textColorDark": "#ffffff",
            "duration": 4000
        }]
        
    def _build_level_notifications(
        self,
        start_level: int,
        end_level: int,
        xp_into_level: int,
        xp_to_next: int,
        restaurant_conf: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Build notifications for level changes.
        
        This method is kept for backward compatibility but notifications are now
        handled in _add_xp for better timing.
        """
        return []
        
    def _get_daily_special_notifications(self, daily_special: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get notifications for daily special progress.
        
        This method is kept for backward compatibility but notifications are now
        handled in _add_xp for better timing.
        """
        return []

        
    @property
    def _addon_prefix(self) -> str:
        if not self._addon_package:
            self._addon_package = mw.addonManager.addonFromModule(__name__)
        return f"/_addons/{self._addon_package}"


# ---------------------------------------------------------------------------
# Chip colour helpers
# ---------------------------------------------------------------------------

def _valid_hex_color(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not text.startswith("#") and len(text) in (3, 6, 8):
        text = f"#{text}"
    from aqt.qt import QColor
    color = QColor(text)
    if color.isValid():
        if color.alpha() < 255:
            return color.name(QColor.NameFormat.HexArgb)
        return color.name(QColor.NameFormat.HexRgb)
    return ""


def default_chip_bg(is_dark: Optional[bool] = None) -> str:
    if is_dark is None:
        try:
            from aqt.theme import theme_manager
            is_dark = bool(theme_manager.night_mode)
        except Exception:
            is_dark = False
    if is_dark:
        return "#3d000000"   # ~24% black
    return "#29ffffff"       # ~16% white


def default_chip_progress_color() -> str:
    try:
        if getattr(mw, "col", None) and hasattr(mw.col, "conf"):
            custom = _valid_hex_color(
                mw.col.conf.get("onigiri_profile_level_bar_custom_color", "#4CAF50")
            )
            if custom:
                return custom
        theme_color = manager.get_current_theme_color()
        if theme_color:
            return _valid_hex_color(theme_color) or str(theme_color)
    except Exception:
        pass
    return "#ffb347"


def get_chip_style_values(
    conf: Optional[Dict[str, Any]] = None,
    is_dark: Optional[bool] = None,
) -> Dict[str, str]:
    if conf is None:
        # Read-only: this runs on the reviewer chip refresh after every
        # answered card, where a full config deep-copy is pure overhead.
        conf = config.get_config_readonly()
    if is_dark is None:
        is_dark = config.effective_night_mode(conf)

    restaurant_conf = conf.get("restaurant_level", {})

    is_dynamic = restaurant_conf.get("dynamic_chip_colors", False)
    if is_dynamic:
        bg_key       = "chip_bg_color_dark"       if is_dark else "chip_bg_color_light"
        text_key     = "chip_text_color_dark"     if is_dark else "chip_text_color_light"
        progress_key = "chip_progress_color_dark" if is_dark else "chip_progress_color_light"
    else:
        bg_key       = "chip_bg_color"
        text_key     = "chip_text_color"
        progress_key = "chip_progress_color"

    bg   = _valid_hex_color(restaurant_conf.get(bg_key))   or default_chip_bg(is_dark)
    text = _valid_hex_color(restaurant_conf.get(text_key))

    if not text and bg:
        from aqt.qt import QColor
        qcolor = QColor(bg)
        if qcolor.isValid():
            text = "#111827" if qcolor.lightness() > 150 else "#ffffff"

    progress = (
        _valid_hex_color(restaurant_conf.get(progress_key))
        or default_chip_progress_color()
    )
    return {"bg": bg, "progress": progress, "text": text}


def build_chip_style_attr(
    values: Optional[Dict[str, str]] = None,
    conf: Optional[Dict[str, Any]] = None,
    is_dark: Optional[bool] = None,
) -> str:
    resolved = values or get_chip_style_values(conf, is_dark)
    parts: List[str] = []

    def _to_css(c: str) -> str:
        """Convert Qt #AARRGGBB hex to CSS rgba(r,g,b,a)."""
        if c and c.startswith("#") and len(c) == 9:
            a = int(c[1:3], 16) / 255.0
            r = int(c[3:5], 16)
            g = int(c[5:7], 16)
            b = int(c[7:9], 16)
            return f"rgba({r}, {g}, {b}, {a:.3f})"
        return c

    if resolved.get("bg"):
        parts.append(f"--rl-chip-bg: {_to_css(resolved['bg'])}")
    if resolved.get("text"):
        parts.append(f"--rl-chip-text: {_to_css(resolved['text'])}")
    if resolved.get("progress"):
        parts.append(f"--profile-level-bar-bg: {_to_css(resolved['progress'])}")
        parts.append(f"--reviewer-level-bar-bg: {_to_css(resolved['progress'])}")
        parts.append(f"--reviewer-level-bar-hover-bg: {_to_css(resolved['progress'])}")
    return "; ".join(parts)


manager = NookLevelManager()

def register_hooks() -> None:
    from aqt import gui_hooks
    gui_hooks.reviewer_did_answer_card.append(manager.on_reviewer_did_answer)
    
    # reviewer_did_undo_answer was removed/not present in v3 scheduler or modern anki
    # Use state_did_undo instead
    if hasattr(gui_hooks, "state_did_undo"):
        gui_hooks.state_did_undo.append(manager.on_state_did_undo)
    elif hasattr(gui_hooks, "reviewer_did_undo_answer"):
        gui_hooks.reviewer_did_undo_answer.append(manager.on_reviewer_did_undo_answer)



register_hooks()
