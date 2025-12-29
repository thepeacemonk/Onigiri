import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any

@dataclass
class AchievementData:
    id: str
    name: str
    description: str
    category: str
    unlocked: bool
    unlocked_date: Optional[str] = None
    progress: int = 0
    threshold: int = 1
    repeatable: bool = False
    count: int = 0
    icon: Optional[str] = None

@dataclass
class DailySpecialData:
    id: str
    name: str
    difficulty: str
    target_cards: int
    completed: bool
    description: str = ""
    completed_date: Optional[str] = None
    cards_completed: int = 0
    xp_earned: int = 0

@dataclass
class RestaurantLevelData:
    daily_special: Dict[str, Any]
    taiyaki_coins: int = 0
    owned_items: List[str] = None
    current_theme_id: str = "default"
    _security_token: str = ""
    last_updated: str = ""
    level: int = 0
    total_xp: int = 0
    name: str = "Restaurant Level"
    # Settings
    enabled: Optional[bool] = None
    notifications_enabled: Optional[bool] = None
    show_profile_bar_progress: Optional[bool] = None
    show_profile_page_progress: Optional[bool] = None
    # Migration State
    migrated: bool = False
    
    def __post_init__(self):
        if self.owned_items is None:
            self.owned_items = ["default"]


class GamificationData:
    def __init__(self, addon_path: str):
        self.addon_path = addon_path
        self.achievements: Dict[str, AchievementData] = {}
        self.daily_specials: List[DailySpecialData] = []
        self.restaurant_data: RestaurantLevelData = RestaurantLevelData(daily_special={})
        self.last_updated: str = datetime.now().isoformat()
        self._load()

    def _get_data_path(self) -> str:
        """Get the path to the gamification.json file."""
        user_files = os.path.join(self.addon_path, 'user_files')
        os.makedirs(user_files, exist_ok=True)
        
        try:
            from aqt import mw
            profile_name = mw.pm.name
        except:
            profile_name = "default"
            
        return os.path.join(user_files, f'gamification_{profile_name}.json')

    def _load(self) -> None:
        """Load data from JSON file if it exists."""
        data_path = self._get_data_path()
        
        # Migration: Check for legacy file
        legacy_path = os.path.join(os.path.dirname(data_path), 'gamification.json')
        if os.path.exists(legacy_path) and not os.path.exists(data_path):
            try:
                os.rename(legacy_path, data_path)
                print(f"Migrated gamification data to {data_path}")
            except Exception as e:
                print(f"Error migrating gamification data: {e}")

        if not os.path.exists(data_path):
            return
            
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Load achievements
            self.achievements = {
                ach['id']: AchievementData(**ach) 
                for ach in data.get('achievements', [])
            }
            
            # Load daily specials
            self.daily_specials = [
                DailySpecialData(**special)
                for special in data.get('daily_specials', [])
            ]
            
            # Load restaurant level data
            r_data = data.get('restaurant_level', {})
            # Ensure fallback defaults if file has partial data
            self.restaurant_data = RestaurantLevelData(
                daily_special=r_data.get('daily_special', {}),
                taiyaki_coins=r_data.get('taiyaki_coins', 0),
                owned_items=r_data.get('owned_items', ["default"]),
                current_theme_id=r_data.get('current_theme_id', "default"),
                _security_token=r_data.get('_security_token', ""),
                last_updated=r_data.get('last_updated', ""),
                level=r_data.get('level', 0),
                total_xp=r_data.get('total_xp', 0),
                name=r_data.get('name', "Restaurant Level"),
                enabled=r_data.get('enabled', None),
                notifications_enabled=r_data.get('notifications_enabled', None),
                show_profile_bar_progress=r_data.get('show_profile_bar_progress', None),
                show_profile_page_progress=r_data.get('show_profile_page_progress', None),
                migrated=r_data.get('migrated', False)
            )
            
            self.last_updated = data.get('last_updated', self.last_updated)
            
        except Exception as e:
            print(f"Error loading gamification data: {e}")
            self.achievements = {}
            self.daily_specials = []
    def reload(self) -> None:
        """Reload data from disk."""
        self._load()
    def save(self) -> None:
        """Save data to JSON file."""
        self.last_updated = datetime.now().isoformat()
        
        # Prepare the new data for the keys we manage
        new_data = {
            'achievements': [asdict(ach) for ach in self.achievements.values()],
            'daily_specials': [asdict(special) for special in self.daily_specials],
            'restaurant_level': asdict(self.restaurant_data),
            'last_updated': self.last_updated
        }
        
        data_path = self._get_data_path()
        final_data = {}
        
        # Try to read existing data to preserve other keys
        if os.path.exists(data_path):
            try:
                with open(data_path, 'r', encoding='utf-8') as f:
                    final_data = json.load(f)
            except Exception as e:
                print(f"Error reading existing gamification data during save: {e}")
                # If read fails, we might lose data, but we have to save our current state
                # final_data remains {}
        
        # Update with our managed data
        final_data.update(new_data)
        
        try:
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving gamification data: {e}")

    def update_achievement(
        self, 
        achievement_id: str, 
        unlocked: bool, 
        progress: int = 0,
        **kwargs
    ) -> None:
        """Update an achievement's status."""
        if achievement_id in self.achievements:
            ach = self.achievements[achievement_id]
            ach.unlocked = unlocked
            ach.progress = progress
            if unlocked and not ach.unlocked_date:
                ach.unlocked_date = datetime.now().isoformat()
            if unlocked and ach.repeatable:
                ach.count += 1
        else:
            # Create a new achievement entry
            self.achievements[achievement_id] = AchievementData(
                id=achievement_id,
                unlocked=unlocked,
                progress=progress,
                unlocked_date=datetime.now().isoformat() if unlocked else None,
                **kwargs
            )
        self.save()

    def add_daily_special(
        self, 
        special_id: str,
        name: str,
        description: str,
        difficulty: str,
        target_cards: int,
        completed: bool,
        cards_completed: int = 0,
        xp_earned: int = 0
    ) -> None:
        """Add or update a daily special."""
        # Check if we already have this special
        existing = next(
            (s for s in self.daily_specials if s.id == special_id), 
            None
        )
        
        if existing:
            # Update existing special
            existing.completed = completed
            existing.cards_completed = cards_completed
            existing.xp_earned = xp_earned
            if completed and not existing.completed_date:
                existing.completed_date = datetime.now().isoformat()
        else:
            # Add new special
            self.daily_specials.append(DailySpecialData(
                id=special_id,
                name=name,
                description=description,
                difficulty=difficulty,
                target_cards=target_cards,
                completed=completed,
                completed_date=datetime.now().isoformat() if completed else None,
                cards_completed=cards_completed,
                xp_earned=xp_earned
            ))
            

                
        self.save()

    def update_restaurant_data(self, updates: Dict[str, Any]) -> None:
        """Update fields in restaurant data."""
        for key, value in updates.items():
            if hasattr(self.restaurant_data, key):
                setattr(self.restaurant_data, key, value)
            elif key == "daily_special_update": 
                # Special handling for nested daily_special updates to avoid overwriting the whole dict
                # Usage: updates={"daily_special_update": {"current_progress": 10}}
                self.restaurant_data.daily_special.update(value)
                
        self.save()
        
    def get_restaurant_data(self) -> Dict[str, Any]:
        """Return restaurant data as a dictionary."""
        return asdict(self.restaurant_data)

# Singleton instance
_gamification_data = None

def _reset_gamification_data(*args):
    """Reset the singleton instance when profile is loaded."""
    global _gamification_data
    _gamification_data = None

try:
    from aqt import gui_hooks
    gui_hooks.profile_did_open.append(_reset_gamification_data)
except:
    pass

def get_gamification_manager() -> GamificationData:
    """Get the singleton instance of GamificationData."""
    global _gamification_data
    if _gamification_data is None:
        # Calculate addon_path dynamically
        current_dir = os.path.dirname(os.path.abspath(__file__))
        addon_path = os.path.dirname(current_dir)
        _gamification_data = GamificationData(addon_path)
    return _gamification_data
