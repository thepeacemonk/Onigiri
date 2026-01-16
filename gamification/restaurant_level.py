from __future__ import annotations

import copy
import hashlib
import json
import os
import time
import re
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from aqt import mw

from .. import config


XP_PER_REVIEW = 5
XP_PER_ACHIEVEMENT = 10
XP_PER_CUSTOM_GOAL = 20




MOTIVATIONAL_PHRASES = (
    "The next level awaits — make your restaurant legendary!",
    "Keep the kitchen busy and the XP flowing!",
    "Every serving of study brings new patrons to your restaurant.",
    "Your crew is cheering — plate up more reviews!",
    "Tonight's special: one more level up!",
    "Customers are lining up; keep the knowledge coming!",
)

RESTAURANTS = {
    "focus_dango": {
        "name": "Focus Dango", 
        "price": 0, 
        "theme": "#DC90B8", 
        "image": "focus_dango_restaurant.png",
        "description": "A cozy pink haven where soft melodies and the gentle aroma of sweet dango help you find your flow. Perfect for deep study sessions!"
    },
    "motivated_mochi": {
        "name": "Motivated Mochi", 
        "price": 0, 
        "theme": "#6EC170", 
        "image": "mochi_msg_restaurant.png",
        "description": "A cheerful green café where adorable mochi friends cheer you on with every review! Their little motivational notes will keep your spirits high!"
    },
    "macha_delights": {
        "name": "Macha Delights", 
        "price": 400, 
        "theme": "#517C58", 
        "image": "Macha Delights.png",
        "description": "A serene tea house specializing in premium matcha creations. Perfect for those who appreciate the subtle, earthy flavors of green tea paired with delicate pastries."
    },
    "macaron_maison": {
        "name": "Macaron Maison", 
        "price": 500, 
        "theme": "#AFC3D6", 
        "image": "Macaron Maison.png",
        "description": "An elegant French patisserie known for its colorful, delicate macarons. Each bite is a perfect balance of crispy shell and smooth, flavorful filling."
    },
    "coffee_co": {
        "name": "Coffee & Co", 
        "price": 600, 
        "theme": "#98693A", 
        "image": "CoffeeAndCake.png",
        "description": "A cozy coffee shop where the aroma of freshly brewed coffee fills the air. Enjoy artisan coffee paired with homemade cakes and pastries."
    },
    "grocery_store": {
        "name": "Grocery Store", 
        "price": 700, 
        "theme": "#AD6131", 
        "image": "Grocery Store.png",
        "description": "Your friendly neighborhood market stocked with fresh produce, pantry essentials, and daily necessities. A warm, welcoming place for all your shopping needs."
    },
    "bakery_heaven": {
        "name": "Bakery Heaven", 
        "price": 800, 
        "theme": "#CD9C57", 
        "image": "Bakery.png",
        "description": "A traditional bakery where the scent of freshly baked bread greets you every morning. From crusty baguettes to soft croissants, every item is made with love."
    },
    "awesome_boba": {
        "name": "Awesome Boba", 
        "price": 850, 
        "theme": "#CD8DCA", 
        "image": "Awesome Boba.png",
        "description": "A vibrant bubble tea shop offering creative flavors and toppings. Customize your drink with chewy tapioca pearls, fruit jellies, and more!"
    },
    "awesome_shiny_boba": {
        "name": "Awesome Shiny Boba", 
        "price": 1000, 
        "theme": "#41A59D", 
        "image": "Awesome Boba (Shiny).png",
        "description": "The premium evolution of Awesome Boba! This exclusive location features rare ingredients and limited-edition flavors with a stunning aesthetic."
    },
    "santas_coffee": {
        "name": "Santa's Coffee", 
        "price": 1025, 
        "theme": "#CA4D44", 
        "image": "Santa's Coffee.png",
        "description": "A magical winter wonderland café where holiday cheer meets exceptional coffee. Warm up with seasonal drinks while enjoying the festive atmosphere."
    },
}

EVOLUTIONS = {
    "onigiri_ii": {"name": "Onigiri II Restaurant", "price": 200, "theme": None, "description": "The upgrade is here!"},
    "onigiri_iii": {"name": "Onigiri III Restaurant", "price": 300, "theme": None, "description": "Even better!"},
    "onigiri_iv": {"name": "Onigiri IV Restaurant", "price": 400, "theme": None, "description": "Superb!"},
    "onigiri_v": {"name": "Onigiri V Restaurant", "price": 500, "theme": None, "description": "Masterpiece!"},
    "prev_onigiri_heaven": {"name": "Onigiri Heaven Restaurant", "price": 750, "theme": "#445b76", "description": "Heavenly!"},
    "restaurant_evo_i": {
        "name": "Restaurant I Star", 
        "price": 700, 
        "theme": "#D07A5F", 
        "image": "Restaurant Evo I.png",
        "description": "The first evolution of your restaurant journey. A charming establishment that shows your dedication to growth and improvement."
    },
    "restaurant_evo_ii": {
        "name": "Restaurant II Star", 
        "price": 800, 
        "theme": "#D07A5F", 
        "image": "Restaurant Evo II.png",
        "description": "Your restaurant continues to evolve! Enhanced decor and expanded menu options attract more customers and showcase your progress."
    },
    "restaurant_evo_iii": {
        "name": "Restaurant III Star", 
        "price": 900, 
        "theme": "#D07A5F", 
        "image": "Restaurant Evo III.png",
        "description": "A significant milestone in your culinary journey. Your restaurant now features premium amenities and a reputation for excellence."
    },
    "restaurant_evo_iv": {
        "name": "Restaurant IV Star", 
        "price": 1000, 
        "theme": "#D07A5F", 
        "image": "Restaurant Evo IV.png",
        "description": "Near the peak of perfection! Your establishment has become a local landmark, known for its exceptional service and quality."
    },
    "restaurant_evo_legendary": {
        "name": "Restaurant Legendary", 
        "price": 1500, 
        "theme": "#445A78", 
        "image": "Restaurant Evo Legendary.png",
        "description": "The ultimate achievement! A legendary restaurant that stands as a testament to your dedication and hard work. Only the most committed reach this level."
    },
    "restaurant_evo_garden": {
        "name": "Restaurant Garden Palace", 
        "price": 3000, 
        "theme": "#2F553D", 
        "image": "Restaurant Evo Garden Palace.png",
        "description": "The pinnacle of culinary prestige! This deluxe establishment radiates luxury and sophistication, offering a world-class dining experience that is truly second to none."
    },
}


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


class RestaurantLevelManager:
    """Tracks the Restaurant Level system (XP, levels, and notifications)."""

    def __init__(self) -> None:
        self._addon_package: str | None = None
        self._daily_target_cache: Dict[str, Any] = {}
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

    def refresh_state(self) -> None:
        """Force reload of gamification state from disk."""
        # GamificationManager handles reloading if needed, but for now we assume it's up to date
        # or we could add a reload method to it.
        self.invalidate_daily_cache()  # Also invalidate cache when refreshing state

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
        """Reset Restaurant Level progress back to level 0."""
        from aqt import mw
        
        # Reset XP and level in gamification.json (Source of Truth)
        # Also ensure we mark as migrated so we don't re-import from legacy config
        updates = {
            "total_xp": 0,
            "level": 0,
            "migrated": True
        }
        self._update_gamification_data(updates)
        
        # Force Anki to mark the collection as modified so it saves
        if mw and mw.col:
            mw.col.setMod()
            mw.col.setMod()

        


    def reset_coins(self) -> None:
        """Reset Taiyaki Coins to 0."""
        self._update_gamification_data({"taiyaki_coins": 0})


    def reset_purchases(self) -> None:
        """Reset owned items and current theme to default."""
        self._update_gamification_data({
            "owned_items": ["default"],
            "current_theme_id": "default"
        })




    def set_enabled(self, enabled: bool) -> None:
        self._update_gamification_data({"enabled": bool(enabled)})

    def set_notifications_enabled(self, enabled: bool) -> None:
        self._update_gamification_data({"notifications_enabled": bool(enabled)})

    def set_profile_bar_visibility(self, show: bool) -> None:
        self._update_gamification_data({"show_profile_bar_progress": bool(show)})

    def set_profile_page_visibility(self, show: bool) -> None:
        self._update_gamification_data({"show_profile_page_progress": bool(show)})

    def set_restaurant_name(self, name: str) -> None:
        """Set the custom name for the restaurant."""
        self._update_gamification_data({"name": str(name)})

    def get_progress(self) -> LevelProgress:
        conf = config.get_config()
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
        name = game_state.get("name", restaurant_conf.get("name", "Restaurant Level"))

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
            "notificationsEnabled": progress.notifications_enabled,
            "showProfileBar": progress.show_profile_bar_progress,
            "showProfilePage": progress.show_profile_page_progress,
            "phrase": self._get_motivational_phrase(progress.level),
        }

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
        
        # Merge config (settings) and state (progress)
        daily_special = {
            "enabled": daily_special_conf.get("enabled", False),
            "target": daily_special_state.get("target", daily_special_conf.get("target", 100)),
            "current_progress": daily_special_state.get("current_progress", 0),
            "last_updated": daily_special_state.get("last_updated"),
            "last_notified_milestone": daily_special_state.get("last_notified_milestone", 0),
            "last_notified_percent": daily_special_state.get("last_notified_percent", 0)
        }
        
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

    def _check_and_reset_daily_special(self, daily_special: Dict[str, Any]) -> bool:
        """Check if daily special needs reset and update it in-place. Returns True if reset occurred."""
        if not daily_special.get("enabled", False):
            return False
            
        # Use Anki's day calculation to match the database query in _sync_daily_progress_with_db
        today = self._get_anki_today_date()
        last_updated = daily_special.get("last_updated")
        
        target = daily_special.get("target", 100)
        
        needs_reset = False
        
        if last_updated != today:
            daily_special["current_progress"] = 0
            daily_special["last_updated"] = today
            daily_special["last_notified_milestone"] = 0
            daily_special["last_notified_percent"] = 0
            needs_reset = True
            
        # Recalculate if reset happened OR if target is the default 100
        if needs_reset or target == 100:
            # Calculate new target based on today's sushi special
            new_target = self._calculate_daily_target()
            
            # Fallback if calculation fails (e.g. JS file not found)
            if not new_target:
                # Generate a deterministic random target between 50 and 150 based on date
                # This ensures variety even without the JS file
                random.seed(today)
                new_target = random.randint(50, 150)
                
            if new_target:
                daily_special["target"] = new_target
                needs_reset = True
                
        return needs_reset

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
            daily_special["current_progress"] = today_reviews
            updated = True
            
        # Check for completion after sync (Always check if target met)
        target = daily_special.get("target", 100)
        if today_reviews >= target:
            notifications = self._handle_daily_special_completion(daily_special)
            self._dispatch_notifications(notifications)
                
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
            
        return {
            "coins": coins,
            "owned_items": owned,
            "current_theme_id": current,
            "restaurants": RESTAURANTS,
            "evolutions": EVOLUTIONS
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
            
        item = RESTAURANTS.get(item_id) or EVOLUTIONS.get(item_id)
        if not item:
            return False, "Item not found."
            
        price = item["price"]
        if coins < price:
            return False, "Not enough Taiyaki Coins."
            
        # Deduct coins
        new_coins = coins - price
        
        # Add to owned
        owned.append(item_id)
            
        # Update gamification.json directly
        self._update_gamification_data({
            "owned_items": owned, 
            "taiyaki_coins": new_coins
        })
        
        return True, "Purchase successful!"

    def equip_item(self, item_id: str) -> Tuple[bool, str]:
        """Equip a restaurant theme."""
        # Read owned items from Source of Truth
        state = self._get_gamification_state()
        owned = state.get("owned_items", ["default"])
        
        if item_id != "default" and item_id not in owned:
            return False, "Item not owned."
            
        # Sync to json
        self._update_gamification_data({"current_theme_id": item_id})
        
        return True, "Theme equipped!"

    def get_current_theme_color(self) -> Optional[str]:
        """Get the hex color of the current theme."""
        state = self._get_gamification_state()
        current_id = state.get("current_theme_id", "default")
        
        if current_id == "default":
            return "#D49083"
            
        item = RESTAURANTS.get(current_id) or EVOLUTIONS.get(current_id)
        if item:
            return item["theme"]
        return None

    def get_current_theme_image(self) -> Optional[str]:
        """Get the image filename of the current theme."""
        state = self._get_gamification_state()
        current_id = state.get("current_theme_id", "default")
        
        if current_id == "default":
            return "restaurant_level.png"
            
        item = RESTAURANTS.get(current_id) or EVOLUTIONS.get(current_id)
        if item and "image" in item:
            return item["image"]
        return "restaurant_level.png"

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
        
        # Always fetch latest progress to update UI, even if no notifications are present

            
        from aqt import mw
        
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

        # Serialize data
        payload = json.dumps(notifications, ensure_ascii=False)
        
        # Get latest progress data
        progress = self.get_progress_payload()
        progress_json = json.dumps(progress, ensure_ascii=False)

        # Enhanced script to update both notifications AND the UI widgets
        script = (
            f"const progress = {progress_json};"
            "try {"
                # 1. Dispatch Notifications
                "if (window.OnigiriNotifications) {"
                    f"const items = {payload};"
                    "items.forEach(item => window.OnigiriNotifications.show(item));"
                "}"
                
                # 2. Update Deck Browser Widget (Restaurant Level)
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

                # 4. Update Reviewer Header Chip (Reviewer Top Bar)
                # Update Progress Bar (Reviewer)
                "const chipProgressBar = document.querySelector('.restaurant-level-chip .level-progress-bar');"
                "if (chipProgressBar) chipProgressBar.style.width = (progress.progressFraction * 100) + '%';"
                
                # Update Level Text (Reviewer) - Format: "Lv. 5"
                "const chipLevelText = document.querySelector('.restaurant-level-chip .level-text');"
                "if (chipLevelText) chipLevelText.textContent = `Lv. ${progress.level}`;"
                
                # Update XP Text (Reviewer) - Format: "100/500 XP"
                "const chipXpText = document.querySelector('.restaurant-level-chip .xp-text');"
                "if (chipXpText) {"
                    "if (progress.xpToNextLevel > 0) {"
                         "chipXpText.textContent = `${progress.xpIntoLevel.toLocaleString()}/${progress.xpToNextLevel.toLocaleString()} XP`;"
                    "} else {"
                         "chipXpText.textContent = `${progress.totalXp.toLocaleString()} XP total`;"
                    "}"
                "}"

            "} catch (e) { console.error('Onigiri UI Update Error:', e); }"
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
        """Handle completion of a daily special and update gamification data.
        
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
            special_id = f"daily_{today}"
            
            # Check if already completed to prevent double-awarding
            existing = next((s for s in gamification.daily_specials if s.id == special_id and s.completed), None)
            if existing:
                return []

            
            # Get the actual daily special data
            special_data = self._get_daily_special_data()
            
            if special_data:
                special_name = special_data.get("name")
                special_desc = special_data.get("description")
                difficulty = special_data.get("difficulty", "Common").lower() # Backend seems to case-insensitively store it, but let's check
                # JS uses lowercase 'common', 'rare' in keys, but Titles in display.
                # Let's Capitalize for display/storage if that's the pattern.
                # Looking at original code: difficulty = "Common" (Capitalized)
                difficulty = difficulty.capitalize() 
                target = special_data.get("target", 100)
            else:
                # Fallback if something goes wrong
                special_name = f"Daily Special - {today}"
                special_desc = "Complete your daily review goal"
                target = daily_special.get("target", 100)
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
            
            # Award XP and get notifications
            notifications = self._add_xp(xp_earned, reason="daily_special")
            
            # Add a specific notification for daily special completion
            notifications.append({
                'id': special_id,
                'name': f'Completed: {special_name}',
                'description': f"You finished '{special_desc}' (+{xp_earned} XP)",
                'iconImage': f"{self._addon_prefix}/system_files/gamification_images/onigiri_trophy.png",
                'iconAlt': "Daily Special Trophy",
                'type': 'xp',
                'amount': xp_earned,
                'reason': 'daily_special',
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

    def _get_daily_special_data(self) -> Optional[Dict[str, Any]]:
        """
        Parses the special_dishes.js file and replicates the logic to find today's special dish.
        Returns a dictionary with name, description, target, difficulty, etc.
        """
        today = self._get_anki_today_date()
        
        # Check cache if we cached the full object? 
        # _daily_target_cache only has 'target'. Let's expand it or just re-parse (it's fast enough)
        
        try:
            # Find the sushi_dishes.js file
            addon_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            js_path = os.path.join(addon_path, "web", "gamification", "restaurant_level", "special_dishes.js")
            
            if not os.path.exists(js_path):
                return None
                
            # Read the JS file
            with open(js_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Get current restaurant ID
            restaurant_id = self.get_current_theme_id()
            
            # Handle evolution mapping (same as JS logic)
            if restaurant_id and restaurant_id.startswith('restaurant_evo_'):
                restaurant_id = 'default'
            
            # Find the array for the restaurant
            start_marker = f'"{restaurant_id}": ['
            start_idx = content.find(start_marker)
            
            # Fallback to default if not found
            if start_idx == -1:
                restaurant_id = 'default'
                start_marker = f'"{restaurant_id}": ['
                start_idx = content.find(start_marker)
                
            if start_idx == -1:
                return None
                
            # Extract the array content
            array_start = start_idx + len(start_marker) - 1 
            
            open_brackets = 0
            array_content = ""
            found_end = False
            
            for i in range(array_start, len(content)):
                char = content[i]
                if char == '[':
                    open_brackets += 1
                elif char == ']':
                    open_brackets -= 1
                    
                if open_brackets == 0:
                    array_content = content[array_start+1:i]
                    found_end = True
                    break
            
            if not found_end:
                return None

            # Parse the array content (simulated JS object parsing)
            dishes = []
            current_obj = {}
            lines = array_content.split('\n')
            
            for line in lines:
                line = line.strip()
                if line.startswith('{'):
                    current_obj = {}
                elif line.startswith('}'):
                    if current_obj:
                        dishes.append(current_obj)
                elif ':' in line:
                    parts = line.split(':', 1)
                    key = parts[0].strip()
                    # Strip quotes from key names (e.g., "name" -> name)
                    if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
                        key = key[1:-1]
                    
                    val = parts[1].strip().rstrip(',')
                    
                    # Clean up value quotes
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    elif val.isdigit():
                        val = int(val)
                        
                    current_obj[key] = val
            
            if not dishes:
                return None
                
            # Calculate day of year
            now = datetime.now()
            start_of_year = datetime(now.year, 1, 1)
            day_of_year = (now - start_of_year).days + 1
            
            index = day_of_year % len(dishes)
            special = dishes[index]
            
            min_cards = int(special.get('minCards', 10))
            max_cards = int(special.get('maxCards', 100))
            
            # PRNG logic matching JS:
            seed = day_of_year * 31 + index
            random_val = ((seed * 9301 + 49297) % 233280) / 233280
            
            target = int(random_val * (max_cards - min_cards + 1)) + min_cards
            
            result = {
                'name': special.get('name', 'Daily Special'),
                'description': special.get('description', ''),
                'difficulty': special.get('difficulty', 'common'),
                'target': target
            }
            return result
            
        except Exception as e:
            print(f"Onigiri: Error getting daily special data: {e}")
            return None

    def _update_gamification_data(self, updates: Dict[str, Any]) -> None:
        """Update the gamification data via manager."""
        # Fix: Automatically update security token if coins are changed
        if "taiyaki_coins" in updates:
            # We don't generate security token anymore
            pass
            
        self._gamification_manager.update_restaurant_data(updates)

    def _update_gamification_daily_special(self, daily_special: Dict[str, Any]) -> None:
        """Update daily special state via manager."""
        state_to_save = {
            "target": daily_special.get("target"),
            "current_progress": daily_special.get("current_progress"),
            "last_updated": daily_special.get("last_updated"),
            "last_notified_milestone": daily_special.get("last_notified_milestone"),
            "last_notified_percent": daily_special.get("last_notified_percent")
        }
        self._gamification_manager.update_restaurant_data({"daily_special_update": state_to_save})

    def _add_xp(self, amount: int, *, reason: str, review_count: int = 0) -> List[Dict[str, Any]]:
        if amount == 0:
            return []


        conf, restaurant_conf = self._config_bundle()
        if not restaurant_conf.get("enabled", False):
            print("Onigiri: Restaurant Level disabled in config, not awarding XP.")
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
            
            # Remove coins from config if present
            if "taiyaki_coins" in restaurant_conf:
                del restaurant_conf["taiyaki_coins"]
                
            notifications.append({
                "id": "taiyaki_coins_gained",
                "name": "Taiyaki Coins!",
                "description": f"You earned {coins_gained} Taiyaki Coins!",
                "iconImage": f"{self._addon_prefix}/system_files/gamification_images/Tayaki_coin.png",
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
                "iconImage": f"{self._addon_prefix}/system_files/gamification_images/Tayaki_coin.png",
                "iconAlt": "Taiyaki Coins",
                "textColorLight": "#2c2c2c",
                "textColorDark": "#ffffff",
                "duration": 3000
            })

        
        # Update the restaurant level and total XP in gamification.json
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
            
            # Construct daily special object
            daily_special = {
                "enabled": True,
                "target": daily_special_state.get("target", daily_special_conf.get("target", 100)),
                "current_progress": daily_special_state.get("current_progress", 0),
                "last_updated": daily_special_state.get("last_updated"),
                "last_notified_milestone": daily_special_state.get("last_notified_milestone", 0),
                "last_notified_percent": daily_special_state.get("last_notified_percent", 0)
            }
            
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
                if new_progress >= target:
                    # Daily special completed - handle it
                    special_notifications = self._handle_daily_special_completion(daily_special)
                    notifications.extend(special_notifications)
                
                # Update progress
                daily_special["current_progress"] = max(0, min(new_progress, target))

                
                # Check for progress milestones (25%, 50%, 75%)
                progress_percent = (new_progress / target) * 100 if target > 0 else 0
                last_notified = daily_special.get("last_notified_percent", 0)
                
                for milestone in [25, 50, 75]:
                    if (last_notified < milestone <= progress_percent and 
                        current < target and 
                        new_progress < target):
                        notifications.append({
                            'id': f"daily_special_progress_{milestone}",
                            'name': f'Daily Special: {milestone}% complete!',
                            'description': f"You've reached {milestone}% of your daily goal ({new_progress}/{target}).",
                            'iconImage': f"{self._addon_prefix}/system_files/gamification_images/onigiri_trophy.png",
                            'iconAlt': "Daily Special Progress",
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
    
    def _xp_for_next(self, level: int) -> int:
        return 50 * (2 * level + 1)

    def _collapse_xp(self, total_xp: int) -> Tuple[int, int, int]:
        """Calculate level and XP progress based on total XP.
        
        Args:
            total_xp: Total XP earned by the user
            
        Returns:
            Tuple of (current_level, xp_into_level, xp_to_next_level)
        """
        level = 0
        xp_needed = 0
        
        while True:
            xp_for_next = self._xp_for_next(level)
            if total_xp < xp_needed + xp_for_next:
                return level, total_xp - xp_needed, xp_for_next
            xp_needed += xp_for_next
            level += 1

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
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/restaurant_folder/{theme_image}"
        else:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/restaurant_folder/restaurant_level.png"
        
        return [{
            "id": "restaurant_level_up",
            "name": f"Level {new_level} Unlocked!",
            "description": f"Your restaurant has reached level {new_level}!",
            "iconImage": icon_path,
            "iconAlt": "Restaurant Level Up",
            "textColorLight": "#2c2c2c",
            "textColorDark": "#ffffff",
            "duration": 5000
        }]

    def _create_half_level_notification(self, level: int, xp_into_level: int, xp_to_next: int) -> List[Dict[str, Any]]:
        """Create a notification for reaching 50% of the current level."""
        # Get the current theme image
        theme_image = self.get_current_theme_image()
        if theme_image:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/restaurant_folder/{theme_image}"
        else:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/restaurant_folder/restaurant_level.png"
        
        progress = (xp_into_level / xp_to_next) * 100
        return [{
            "id": "restaurant_level_progress",
            "name": f"Level {level} Progress",
            "description": f"You're {int(progress)}% to level {level + 1}!",
            "iconImage": icon_path,
            "iconAlt": "Level Progress",
            "textColorLight": "#2c2c2c",
            "textColorDark": "#ffffff",
            "duration": 4000
        }]

    def _create_daily_special_complete_notification(self) -> List[Dict[str, Any]]:
        """Create a notification for completing the daily special."""
        # Get the current theme image
        theme_image = self.get_current_theme_image()
        if theme_image:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/restaurant_folder/{theme_image}"
        else:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/restaurant_folder/restaurant_level.png"
        
        return [{
            "id": "daily_special_complete",
            "name": "Daily Special Complete!",
            "description": "You've completed today's special! Great job!",
            "iconImage": icon_path,
            "iconAlt": "Daily Special Complete",
            "textColorLight": "#2c2c2c",
            "textColorDark": "#ffffff",
            "duration": 5000
        }]

    def _create_daily_special_75_notification(self, target: int, progress: int) -> List[Dict[str, Any]]:
        """Create a notification for reaching 75% of the daily special."""
        # Get the current theme image
        theme_image = self.get_current_theme_image()
        if theme_image:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/restaurant_folder/{theme_image}"
        else:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/restaurant_folder/restaurant_level.png"
        
        remaining = target - progress
        return [{
            "id": "daily_special_progress_75",
            "name": "Daily Special Progress",
            "description": f"You're 75% done! Just {remaining} more to go!",
            "iconImage": icon_path,
            "iconAlt": "Daily Special Progress",
            "textColorLight": "#2c2c2c",
            "textColorDark": "#ffffff",
            "duration": 4000
        }]

    def _create_daily_special_50_notification(self, target: int, progress: int) -> List[Dict[str, Any]]:
        """Create a notification for reaching 50% of the daily special."""
        # Get the current theme image
        theme_image = self.get_current_theme_image()
        if theme_image:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/restaurant_folder/{theme_image}"
        else:
            icon_path = f"{self._addon_prefix}/system_files/gamification_images/restaurant_folder/restaurant_level.png"
        
        remaining = target - progress
        return [{
            "id": "daily_special_progress_50",
            "name": "Daily Special Progress",
            "description": f"Halfway there! {remaining} more to complete today's special!",
            "iconImage": icon_path,
            "iconAlt": "Daily Special Progress",
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

    def _get_motivational_phrase(self, level: int) -> str:
        if not MOTIVATIONAL_PHRASES:
            return "Keep serving knowledge!"
        index = level % len(MOTIVATIONAL_PHRASES)
        return MOTIVATIONAL_PHRASES[index]
        
    @property
    def _addon_prefix(self) -> str:
        if not self._addon_package:
            self._addon_package = mw.addonManager.addonFromModule(__name__)
        return f"/_addons/{self._addon_package}"


manager = RestaurantLevelManager()

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
