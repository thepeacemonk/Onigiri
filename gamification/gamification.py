import json
import os
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..core import safe_storage

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

    last_updated: str = ""
    level: int = 0
    total_xp: int = 0
    name: str = "Nook Level"
    # Settings
    enabled: Optional[bool] = None
    notifications_enabled: Optional[bool] = None
    show_profile_bar_progress: Optional[bool] = None
    show_profile_page_progress: Optional[bool] = None
    # Migration State
    migrated: bool = False
    xp_multiplier: Optional[int] = None
    
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
        # Cache the profile name at construction time so that save() always
        # writes to the file that was loaded, regardless of later profile
        # switches or renames.
        self._profile_name: str = self._resolve_profile_name()
        self._load()

    @staticmethod
    def _resolve_profile_name() -> str:
        """Read the current profile name from Anki, falling back to 'default'."""
        try:
            from aqt import mw
            return mw.pm.name or "default"
        except Exception:
            return "default"

    def _get_data_path(self) -> str:
        """Get the path to the gamification.json file for this instance's profile."""
        user_files = os.path.join(self.addon_path, 'user_files')
        os.makedirs(user_files, exist_ok=True)
        return os.path.join(user_files, f'gamification_{self._profile_name}.json')

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        if value is None or isinstance(value, bool):
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _has_existing_or_backup(data_path: str) -> bool:
        if os.path.exists(data_path) or safe_storage.pending_payload(data_path) is not None:
            return True
        if os.path.exists(data_path + '.bak') or safe_storage._snapshots_for(data_path):
            return True
        mirrored = safe_storage._mirror_path_for(data_path)
        return bool(mirrored and os.path.exists(mirrored))

    def _load(self) -> None:
        """Load data from JSON file if it exists."""
        safe_storage.backup_before_upgrade()
        self.achievements = {}
        self.daily_specials = []
        self.restaurant_data = RestaurantLevelData(daily_special={})
        data_path = self._get_data_path()
        
        # Migration: Check for legacy file only when this profile has neither
        # a primary save nor any recoverable backup/mirror.
        legacy_path = os.path.join(os.path.dirname(data_path), 'gamification.json')
        if os.path.exists(legacy_path) and not self._has_existing_or_backup(data_path):
            try:
                shutil.copy2(legacy_path, data_path)
                print(f"Migrated gamification data to {data_path}")
            except Exception as e:
                print(f"Error migrating gamification data: {e}")

        try:
            data = safe_storage.read_json(
                data_path, default={}, label="Your Onigiri progress"
            )
            if not isinstance(data, dict) or not data:
                return
        except Exception as e:
            print(f"Error loading gamification data: {e}")
            return

        # Load restaurant level data independently so a malformed achievement
        # or daily special entry can never zero out coins, level, or XP.
        raw_restaurant = data.get('restaurant_level')
        r_data = raw_restaurant if isinstance(raw_restaurant, dict) else {}
        raw_daily_special = r_data.get('daily_special')
        raw_owned = r_data.get('owned_items')
        owned_items = list(raw_owned) if isinstance(raw_owned, list) else ["default"]
        self.restaurant_data = RestaurantLevelData(
            daily_special=dict(raw_daily_special) if isinstance(raw_daily_special, dict) else {},
            taiyaki_coins=self._safe_int(r_data.get('taiyaki_coins'), 0),
            owned_items=owned_items,
            current_theme_id=r_data.get('current_theme_id') or "default",

            last_updated=r_data.get('last_updated') or "",
            level=self._safe_int(r_data.get('level'), 0),
            total_xp=self._safe_int(r_data.get('total_xp'), 0),
            name=r_data.get('name') or "Nook Level",
            enabled=r_data.get('enabled', None),
            notifications_enabled=r_data.get('notifications_enabled', None),
            show_profile_bar_progress=r_data.get('show_profile_bar_progress', None),
            show_profile_page_progress=r_data.get('show_profile_page_progress', None),
            migrated=bool(r_data.get('migrated', False)),
            xp_multiplier=r_data.get('xp_multiplier'),
        )

        # Load achievements (skip only individual malformed entries)
        raw_achievements = data.get('achievements')
        if isinstance(raw_achievements, list):
            for ach in raw_achievements:
                if not isinstance(ach, dict) or not ach.get('id'):
                    continue
                try:
                    self.achievements[ach['id']] = safe_storage.dataclass_from_dict(AchievementData, ach)
                except Exception as e:
                    print(f"Error loading achievement entry: {e}")

        # Load daily specials (skip only individual malformed entries)
        raw_specials = data.get('daily_specials')
        if isinstance(raw_specials, list):
            for special in raw_specials:
                if not isinstance(special, dict):
                    continue
                try:
                    self.daily_specials.append(safe_storage.dataclass_from_dict(DailySpecialData, special))
                except Exception as e:
                    print(f"Error loading daily special entry: {e}")

        if data.get('last_updated'):
            self.last_updated = data['last_updated']
    def reload(self) -> None:
        """Reload data from disk."""
        self._load()
    def save(self, immediate: bool = False) -> bool:
        """Save data to JSON file.

        Every answered card updates XP and Nook Rush progress, so writing
        straight through meant an fsync plus two file copies per review. The
        write is queued instead and coalesced by safe_storage; pass
        ``immediate=True`` when the file has to be on disk right away (profile
        close, sync, handing the file to another reader).
        """
        self.last_updated = datetime.now().isoformat()
        
        # Prepare the new data for the keys we manage
        new_data = {
            'achievements': [safe_storage.dataclass_payload(ach) for ach in self.achievements.values()],
            'daily_specials': [safe_storage.dataclass_payload(special) for special in self.daily_specials],
            'restaurant_level': asdict(self.restaurant_data),
            'last_updated': self.last_updated
        }
        
        # Untouched legacy files keep their original shape until progression
        # is initialized by the Nook manager.
        if new_data['restaurant_level']['xp_multiplier'] is None:
            new_data['restaurant_level'].pop('xp_multiplier')

        data_path = self._get_data_path()
        final_data = {}
        
        # Try to read existing data to preserve other keys. A queued write is
        # newer than the file, so start from it when there is one; otherwise
        # going through read_json means a corrupt file falls back to its backup
        # instead of silently dropping every key we do not manage here.
        pending = safe_storage.pending_payload(data_path)
        if isinstance(pending, dict):
            final_data = dict(pending)
        elif os.path.exists(data_path):
            final_data = safe_storage.read_json(
                data_path, default={}, label="Your Onigiri progress"
            ) or {}

        # Preserve legacy nested metadata as well as top-level extension keys.
        # Keep the legacy coin integrity token synchronized whenever present so
        # older releases or synced devices can never treat a valid balance as stale.
        previous_restaurant = final_data.get('restaurant_level', {})
        if isinstance(previous_restaurant, dict):
            merged_restaurant = dict(previous_restaurant)
            merged_restaurant.update(new_data['restaurant_level'])
            if '_security_token' in merged_restaurant:
                import hashlib
                merged_restaurant['_security_token'] = hashlib.sha256(
                    f"{merged_restaurant['taiyaki_coins']}:onigiri_secret_salt_2024".encode()
                ).hexdigest()
            new_data['restaurant_level'] = merged_restaurant

        # Update with our managed data
        final_data.update(new_data)

        if immediate:
            if safe_storage.atomic_write_json(data_path, final_data):
                return True
            # Transient file lock (e.g. antivirus/cloud sync): queue a retry so
            # redeemed/earned coins are never silently dropped on disk.
            return safe_storage.schedule_write_json(data_path, final_data)
        return safe_storage.schedule_write_json(data_path, final_data)

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

    def update_restaurant_data(self, updates: Dict[str, Any], immediate: bool = False) -> None:
        """Update fields in restaurant data.

        ``immediate`` forces the write through instead of queueing it - use it
        for anything the user just paid for or explicitly changed.
        """
        for key, value in updates.items():
            if hasattr(self.restaurant_data, key):
                setattr(self.restaurant_data, key, value)
            elif key == "daily_special_update": 
                # Special handling for nested daily_special updates to avoid overwriting the whole dict
                # Usage: updates={"daily_special_update": {"current_progress": 10}}
                self.restaurant_data.daily_special.update(value)
                
        self.save(immediate=immediate)
        
    def get_restaurant_data(self) -> Dict[str, Any]:
        """Return restaurant data as a dictionary."""
        return asdict(self.restaurant_data)

    def progression_backups(self):
        """Read this profile's recovery evidence without restoring whole files."""
        path = self._get_data_path()
        sources = [path + '.bak', *safe_storage._snapshots_for(path)]
        mirrored = safe_storage._mirror_path_for(path)
        if mirrored:
            sources.append(mirrored)
        for source in sources:
            try:
                with open(source, encoding='utf-8') as handle:
                    data = json.load(handle)
                if isinstance(data, dict) and isinstance(data.get('restaurant_level'), dict):
                    yield data['restaurant_level']
            except (OSError, ValueError):
                continue
        import zipfile
        archive_path = os.path.join(safe_storage.external_backup_dir(), 'before_progress_upgrade_v2.zip')
        try:
            with zipfile.ZipFile(archive_path) as archive:
                data = json.loads(archive.read('user_files/' + os.path.basename(path)))
                if isinstance(data, dict) and isinstance(data.get('restaurant_level'), dict):
                    yield data['restaurant_level']
        except (OSError, ValueError, KeyError, zipfile.BadZipFile):
            pass

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
    """Get the singleton instance of GamificationData for the active profile."""
    global _gamification_data
    current_profile = GamificationData._resolve_profile_name()
    if _gamification_data is not None and _gamification_data._profile_name != current_profile:
        try:
            safe_storage.flush_pending(_gamification_data._get_data_path())
        except Exception:
            pass
        _gamification_data = None
    if _gamification_data is None:
        # Calculate addon_path dynamically
        current_dir = os.path.dirname(os.path.abspath(__file__))
        addon_path = os.path.dirname(current_dir)
        _gamification_data = GamificationData(addon_path)
    return _gamification_data
