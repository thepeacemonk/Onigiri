from __future__ import annotations

import json
import os
import random
import re
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from html import escape
from typing import Any, Dict, List, Optional, Union

from aqt import gui_hooks, mw

from .. import config


ANKIMON_ADDON_IDS = ("1908235722", "Ankimon")


ITEMS = {
    "berries": {
        "label": "Berries",
        "icon_path": "system_files/pokesprite/items/berry-cheri.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/berry/cheri.png",
    },
    "poke_candies": {
        "label": "Poké-candies",
        "icon_path": "system_files/pokesprite/items/poke-candy-pink.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/poke-candy/pink.png",
    },
    "curry_ingredients": {
        "label": "Curry ingredients",
        "icon_path": "system_files/pokesprite/items/curry-packaged.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/curry-ingredient/packaged-curry.png",
    },
    "exp_candy": {
        "label": "EXP Candy",
        "icon_path": "system_files/pokesprite/items/exp-candy-m.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/exp-candy/m.png",
    },
    "mints": {
        "label": "Mints",
        "icon_path": "system_files/pokesprite/items/mint-attack.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/mint/attack.png",
    },
    "pokeballs": {
        "label": "Pokéballs",
        "icon_path": "system_files/pokesprite/items/ball-poke.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/ball/poke.png",
    },
    "medicine": {
        "label": "Medicine",
        "icon_path": "system_files/pokesprite/items/medicine-potion.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/medicine/potion.png",
    },
}


BERRY_ITEMS = {
    "berry_cheri": {
        "label": "Cheri Berry",
        "icon_path": "system_files/pokesprite/items/berry-cheri.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/berry/cheri.png",
        "favored_types": ("electric", "fire"),
        "effect": "Energy and warmth",
        "hunger": 14,
        "happiness": 4,
        "energy": 10,
    },
    "berry_chesto": {
        "label": "Chesto Berry",
        "icon_path": "system_files/pokesprite/items/berry-chesto.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/berry/chesto.png",
        "favored_types": ("ghost", "psychic", "dark"),
        "effect": "Restores energy",
        "hunger": 12,
        "happiness": 3,
        "energy": 16,
    },
    "berry_pecha": {
        "label": "Pecha Berry",
        "icon_path": "system_files/pokesprite/items/berry-pecha.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/berry/pecha.png",
        "favored_types": ("fairy", "grass", "poison"),
        "effect": "Sweet happiness",
        "hunger": 14,
        "happiness": 10,
        "cleanliness": 4,
    },
    "berry_rawst": {
        "label": "Rawst Berry",
        "icon_path": "system_files/pokesprite/items/berry-rawst.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/berry/rawst.png",
        "favored_types": ("fire", "ice", "steel"),
        "effect": "Freshens and cools",
        "hunger": 14,
        "happiness": 4,
        "cleanliness": 12,
    },
    "berry_aspear": {
        "label": "Aspear Berry",
        "icon_path": "system_files/pokesprite/items/berry-aspear.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/berry/aspear.png",
        "favored_types": ("flying", "ice", "water"),
        "effect": "Crisp mood boost",
        "hunger": 16,
        "happiness": 7,
        "energy": 5,
    },
    "berry_leppa": {
        "label": "Leppa Berry",
        "icon_path": "system_files/pokesprite/items/berry-leppa.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/berry/leppa.png",
        "favored_types": ("dragon", "electric", "psychic"),
        "effect": "Bond XP and energy",
        "hunger": 14,
        "happiness": 5,
        "energy": 10,
        "bond_xp": 6,
    },
    "berry_oran": {
        "label": "Oran Berry",
        "icon_path": "system_files/pokesprite/items/berry-oran.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/berry/oran.png",
        "favored_types": ("fighting", "normal", "rock"),
        "effect": "Reliable hunger care",
        "hunger": 25,
        "happiness": 3,
    },
    "berry_sitrus": {
        "label": "Sitrus Berry",
        "icon_path": "system_files/pokesprite/items/berry-sitrus.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/berry/sitrus.png",
        "favored_types": ("grass", "ground", "water"),
        "effect": "Hunger and HP",
        "hunger": 30,
        "happiness": 5,
        "hp": 12,
    },
    "berry_lum": {
        "label": "Lum Berry",
        "icon_path": "system_files/pokesprite/items/berry-lum.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/berry/lum.png",
        "favored_types": ("bug", "dark", "dragon", "ghost"),
        "effect": "Balanced care",
        "hunger": 18,
        "happiness": 7,
        "cleanliness": 7,
        "energy": 7,
    },
}
ITEMS.update(BERRY_ITEMS)
BERRY_KEYS = tuple(BERRY_ITEMS.keys())
ITEM_COLORS = {
    "food": ("#4fbd73", "#e6f7ea", "#173824"),
    "treats": ("#ff6fc8", "#ffe0f3", "#4a1735"),
    "care": ("#d9575a", "#ffe5e5", "#461b1d"),
    "pokeballs": ("#f08d3c", "#ffead6", "#472815"),
    "berry_cheri": ("#d94b3d", "#ffe3df", "#451b17"),
    "berry_chesto": ("#7062d9", "#ebe7ff", "#211d48"),
    "berry_pecha": ("#ff83b7", "#ffe3ef", "#4b1b31"),
    "berry_rawst": ("#86c7ef", "#e3f4ff", "#183748"),
    "berry_aspear": ("#a7d86d", "#eff9dd", "#2c4218"),
    "berry_leppa": ("#f2a047", "#fff0dc", "#4a2d14"),
    "berry_oran": ("#4f93df", "#e0efff", "#18314d"),
    "berry_sitrus": ("#e6c742", "#fff7d7", "#44380e"),
    "berry_lum": ("#61c486", "#e3f8ea", "#173b27"),
    "poke_candies": ("#ff6fc8", "#ffe0f3", "#4a1735"),
    "curry_ingredients": ("#f08d3c", "#ffead6", "#472815"),
    "exp_candy": ("#69c7e8", "#dff7ff", "#143947"),
    "mints": ("#d9575a", "#ffe5e5", "#461b1d"),
    "medicine": ("#9f8ae8", "#eee8ff", "#30264d"),
}


@dataclass
class OnigimonCompanion:
    ankimon_id: str
    name: str = "Companion"
    display_name: str = ""
    pokedex_id: int = 0
    level: int = 1
    hp: int = 0
    max_hp: int = 0
    sprite_url: str = ""
    types: List[str] = field(default_factory=list)
    hunger: int = 70
    happiness: int = 50
    cleanliness: int = 60
    bond_xp: int = 0
    bond_level: int = 1
    energy: int = 70
    last_cared_at: str = ""


@dataclass
class OnigimonState:
    active_companion_id: str = ""
    companions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    inventory: Dict[str, int] = field(default_factory=dict)
    last_study_day: str = ""
    current_streak: int = 0
    last_daily_gift_day: str = ""
    reviews_since_reward: int = 0
    today_review_count: int = 0
    plays_used_today: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.companions, dict):
            self.companions = {}
        if not isinstance(self.inventory, dict):
            self.inventory = {}
        for key in ITEMS:
            self.inventory.setdefault(key, 0)
        old_generic_berries = int(self.inventory.get("berries", 0) or 0)
        if old_generic_berries > 0:
            self.inventory["berry_oran"] = self.inventory.get("berry_oran", 0) + old_generic_berries
            self.inventory["berries"] = 0


class AnkimonBridge:
    def __init__(self) -> None:
        self.addon_id = ""
        self.addon_path = ""
        self._collection_cache: List[Dict[str, Any]] = []
        self._collection_cache_time = 0.0

    def detect(self) -> bool:
        try:
            addons_folder = mw.addonManager.addonsFolder()
        except Exception:
            return False

        for addon_id in ANKIMON_ADDON_IDS:
            path = os.path.join(addons_folder, addon_id)
            if os.path.isdir(path):
                self.addon_id = addon_id
                self.addon_path = path
                return True
        self.addon_id = ""
        self.addon_path = ""
        return False

    def status(self) -> str:
        if not self.detect():
            return "missing"
        if self.get_collection():
            return "ready"
        if self._has_main_pokemon():
            return "no_collection"
        return "starter_needed"

    def get_collection(self) -> List[Dict[str, Any]]:
        if not self.detect():
            return []
        now = time.time()
        if now - self._collection_cache_time < 10:
            return self._collection_cache
        self._collection_cache = self._read_db_collection() or self._read_json_collection()
        self._collection_cache_time = now
        return self._collection_cache

    def clear_cache(self) -> None:
        self._collection_cache = []
        self._collection_cache_time = 0.0

    def _db_path(self) -> str:
        return os.path.join(self.addon_path, "user_files", "ankimon.db")

    def _has_main_pokemon(self) -> bool:
        db_path = self._db_path()
        if os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as conn:
                    tables = {
                        row[0]
                        for row in conn.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        ).fetchall()
                    }
                    for table in ("main_pokemon", "mainpokemon", "selected_pokemon"):
                        if table in tables:
                            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                            if count:
                                return True
            except Exception:
                pass

        path = os.path.join(self.addon_path, "user_files", "mainpokemon.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                return bool(data)
            except Exception:
                return False
        return False

    def _read_db_collection(self) -> List[Dict[str, Any]]:
        db_path = self._db_path()
        if not os.path.exists(db_path):
            return []
        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                table = "captured_pokemon" if "captured_pokemon" in tables else ""
                if not table and "pokemon" in tables:
                    table = "pokemon"
                if not table:
                    return []
                rows = conn.execute(f"SELECT * FROM {table} LIMIT 500").fetchall()
                return [self._normalize_pokemon(dict(row)) for row in rows]
        except Exception as exc:
            print(f"Onigimon: Could not read Ankimon database: {exc}")
            return []

    def _read_json_collection(self) -> List[Dict[str, Any]]:
        path = os.path.join(self.addon_path, "user_files", "mypokemon.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                values = list(data.values())
            elif isinstance(data, list):
                values = data
            else:
                values = []
            return [self._normalize_pokemon(item) for item in values if isinstance(item, dict)]
        except Exception as exc:
            print(f"Onigimon: Could not read Ankimon JSON collection: {exc}")
            return []

    def _normalize_pokemon(self, data: Dict[str, Any]) -> Dict[str, Any]:
        raw_id = (
            data.get("individual_id")
            or data.get("uuid")
            or data.get("id_in_collection")
            or data.get("caught_id")
            or data.get("id")
            or data.get("pokedex_id")
            or data.get("name")
        )
        pokedex_id = self._safe_int(data.get("pokedex_id") or data.get("pokemon_id") or data.get("species_id") or data.get("id"), 0)
        name = str(data.get("nickname") or data.get("name") or f"Pokemon {pokedex_id}")
        max_hp = self._safe_int(data.get("max_hp") or data.get("maxhp") or data.get("hp"), 0)
        hp = self._safe_int(data.get("current_hp") or data.get("hp") or max_hp, 0)
        pokemon = {
            "ankimon_id": str(raw_id),
            "name": name,
            "pokedex_id": pokedex_id,
            "level": self._safe_int(data.get("level"), 1),
            "hp": hp,
            "max_hp": max_hp,
            "sprite_url": self.sprite_url(pokedex_id, name, bool(data.get("shiny", False))),
            "types": self._normalize_types(data),
        }
        return pokemon

    def _normalize_types(self, data: Dict[str, Any]) -> List[str]:
        values: List[Any] = []
        for key in ("types", "type", "pokemon_types"):
            raw = data.get(key)
            if isinstance(raw, list):
                values.extend(raw)
            elif isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        values.extend(parsed)
                        continue
                except Exception:
                    pass
                values.extend(re.split(r"[,/| ]+", raw))
        for key in ("type_1", "type_2", "type1", "type2", "primary_type", "secondary_type"):
            if data.get(key):
                values.append(data.get(key))
        normalized = []
        for value in values:
            text = str(value).strip().lower()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def sprite_url(self, pokedex_id: int, name: str = "", shiny: bool = False) -> str:
        if not pokedex_id or not self.addon_id:
            return ""
        motion = str(config.get_config().get("onigimon", {}).get("sprite_motion", "static"))
        preferred = "front_shiny" if shiny else "front_default"
        extensions = ("gif", "png") if motion == "gif" else ("png", "gif")
        candidates = [
            (folder, f"{pokedex_id}.{ext}")
            for folder in (preferred, "front_default")
            for ext in extensions
        ]
        for folder, filename in candidates:
            rel = f"user_files/sprites/{folder}/{filename}"
            if os.path.exists(os.path.join(self.addon_path, rel)):
                return f"/_addons/{self.addon_id}/{rel}"
        return self._pokesprite_url(name, shiny)

    def animated_sprite_url(self, pokedex_id: int, shiny: bool = False) -> str:
        if not pokedex_id or not self.detect():
            return ""
        preferred = "front_shiny" if shiny else "front_default"
        for folder in (preferred, "front_default"):
            rel = f"user_files/sprites/{folder}/{pokedex_id}.gif"
            if os.path.exists(os.path.join(self.addon_path, rel)):
                return f"/_addons/{self.addon_id}/{rel}"
        shiny_part = "shiny/" if shiny else ""
        return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-v/black-white/animated/{shiny_part}{pokedex_id}.gif"

    def _pokesprite_url(self, name: str, shiny: bool = False) -> str:
        slug = re.sub(r"[^a-z0-9-]+", "-", str(name).strip().lower().replace(" ", "-")).strip("-")
        if not slug:
            return ""

        onigiri_path = os.path.dirname(os.path.dirname(__file__))
        variant = "shiny" if shiny else "regular"
        local_rel = f"system_files/pokesprite/pokemon-gen8/{variant}/{slug}.png"
        if os.path.exists(os.path.join(onigiri_path, local_rel)):
            try:
                addon_package = mw.addonManager.addonFromModule(__name__)
                return f"/_addons/{addon_package}/{local_rel}"
            except Exception:
                pass
        return f"https://raw.githubusercontent.com/msikma/pokesprite/master/pokemon-gen8/{variant}/{slug}.png"


class OnigimonManager:
    def __init__(self) -> None:
        self.bridge = AnkimonBridge()
        self._state: Optional[OnigimonState] = None
        self.last_action: Optional[str] = None

    def config(self) -> Dict[str, Any]:
        conf = config.get_config().get("onigimon", {})
        return conf if isinstance(conf, dict) else {}

    def is_enabled(self) -> bool:
        return bool(self.config().get("enabled", False))

    def _profile_name(self) -> str:
        try:
            return mw.pm.name or "default"
        except Exception:
            return "default"

    def _data_path(self) -> str:
        addon_path = os.path.dirname(os.path.dirname(__file__))
        user_files = os.path.join(addon_path, "user_files")
        os.makedirs(user_files, exist_ok=True)
        return os.path.join(user_files, f"onigimon_{self._profile_name()}.json")

    def load(self) -> OnigimonState:
        if self._state is not None:
            return self._state
        path = self._data_path()
        if not os.path.exists(path):
            self._state = OnigimonState()
            return self._state
        try:
            with open(path, "r", encoding="utf-8") as fh:
                self._state = OnigimonState(**json.load(fh))
        except Exception as exc:
            print(f"Onigimon: Could not load state: {exc}")
            self._state = OnigimonState()
        return self._state

    def save(self) -> None:
        state = self.load()
        try:
            with open(self._data_path(), "w", encoding="utf-8") as fh:
                json.dump(asdict(state), fh, indent=2, ensure_ascii=False)
        except Exception as exc:
            print(f"Onigimon: Could not save state: {exc}")

    def get_available_companions(self) -> List[Dict[str, Any]]:
        return self.bridge.get_collection()

    def set_active_companion(self, ankimon_id: str) -> bool:
        state = self.load()
        found = None
        for pokemon in self.get_available_companions():
            if str(pokemon.get("ankimon_id")) == str(ankimon_id):
                found = pokemon
                break
        if not found:
            return False
        existing = state.companions.get(str(ankimon_id), {})
        companion = OnigimonCompanion(**{**found, **existing, **{"ankimon_id": str(ankimon_id)}})
        state.companions[str(ankimon_id)] = asdict(companion)
        state.active_companion_id = str(ankimon_id)
        self.save()
        return True

    def rename_active_companion(self, display_name: str) -> bool:
        companion = self.active_companion()
        if companion is None:
            return False
        state = self.load()
        companion.display_name = display_name.strip()[:40]
        state.companions[companion.ankimon_id] = asdict(companion)
        self.save()
        self.notify("Onigimon renamed", f"{self.companion_display_name(companion)} is ready to study with you.", companion.sprite_url)
        return True

    @staticmethod
    def companion_display_name(companion: Union[OnigimonCompanion, Dict[str, Any]]) -> str:
        if isinstance(companion, dict):
            return str(companion.get("display_name") or companion.get("name") or "Companion")
        return companion.display_name or companion.name or "Companion"

    def active_companion(self) -> Optional[OnigimonCompanion]:
        state = self.load()
        if not state.active_companion_id:
            return None
        data = state.companions.get(state.active_companion_id)
        if not data:
            return None
        refreshed = self._refreshed_companion_data(state.active_companion_id)
        if refreshed:
            data.update(refreshed)
            state.companions[state.active_companion_id] = data
            self.save()
        return OnigimonCompanion(**data)

    def _refreshed_companion_data(self, ankimon_id: str) -> Dict[str, Any]:
        for pokemon in self.get_available_companions():
            if str(pokemon.get("ankimon_id")) == str(ankimon_id):
                return pokemon
        return {}

    def modal_sprite_url(self, companion: Dict[str, Any]) -> str:
        pokedex_id = AnkimonBridge._safe_int(companion.get("pokedex_id"), 0)
        animated = self.bridge.animated_sprite_url(pokedex_id)
        return animated or str(companion.get("sprite_url") or "")

    def status(self) -> str:
        if not self.is_enabled():
            return "disabled"
        return self.bridge.status()

    def widget_payload(self) -> Dict[str, Any]:
        state = self.load()
        companion = self.active_companion()
        payload = {
            "status": self.status(),
            "companion": asdict(companion) if companion else None,
            "inventory": state.inventory,
            "streak": state.current_streak,
            "playAllowance": self.play_allowance(state),
            "playsAvailable": self.plays_available(state),
            "dailyGiftReady": state.last_daily_gift_day != date.today().isoformat(),
            "lastAction": getattr(self, "last_action", None),
        }
        self.last_action = None
        return payload

    def on_answer(self, reviewer=None, card=None, ease: int = 0) -> None:
        if not self.is_enabled():
            return
        if self.status() != "ready":
            return
        companion = self.active_companion()
        if companion is None:
            return

        state = self.load()
        today = date.today().isoformat()
        if state.last_study_day != today:
            self._advance_streak(state, today)
        state.today_review_count += 1

        interval = max(1, int(self.config().get("reward_interval", 4) or 4))
        state.reviews_since_reward += 1

        if state.reviews_since_reward >= interval:
            state.reviews_since_reward = 0
            item_key = self._choose_reward(ease, state.current_streak)
            amount = self._reward_amount(item_key, state.current_streak)
            state.inventory[item_key] = state.inventory.get(item_key, 0) + amount
            self.save()
            self.notify(
                "Onigimon found an item",
                f"{self.companion_display_name(companion)} brought you {amount} {ITEMS[item_key]['label']}.",
                companion.sprite_url,
            )
            return
        self.save()

    def _advance_streak(self, state: OnigimonState, today: str) -> None:
        previous = state.last_study_day
        yesterday = date.fromordinal(date.today().toordinal() - 1).isoformat()
        state.current_streak = state.current_streak + 1 if previous == yesterday else 1
        state.last_study_day = today
        state.today_review_count = 0
        state.plays_used_today = 0

    def play_allowance(self, state: Optional[OnigimonState] = None) -> int:
        state = state or self.load()
        return max(0, int(state.today_review_count) // 10)

    def plays_available(self, state: Optional[OnigimonState] = None) -> int:
        state = state or self.load()
        return max(0, self.play_allowance(state) - int(state.plays_used_today))

    def _nudge_companion(self, companion: OnigimonCompanion, ease: int) -> None:
        companion.hunger = max(0, companion.hunger - 1)
        companion.energy = max(0, companion.energy - 1)
        companion.happiness = min(100, companion.happiness + (2 if ease >= 3 else 1))
        companion.bond_xp += 2 if ease >= 3 else 1
        next_level_xp = companion.bond_level * 40
        if companion.bond_xp >= next_level_xp:
            companion.bond_xp -= next_level_xp
            companion.bond_level += 1
            self.notify("Bond level up", f"{self.companion_display_name(companion)}'s Onigimon bond grew to level {companion.bond_level}.", companion.sprite_url)

    def _choose_reward(self, ease: int, streak: int) -> str:
        pool = [
            self._choose_berry_reward(),
            self._choose_berry_reward(),
            "poke_candies",
            "curry_ingredients",
            "mints",
        ]
        if ease >= 3:
            pool.extend(["poke_candies", "medicine"])
        if streak >= 7:
            pool.extend(["exp_candy", "pokeballs", self._choose_berry_reward()])
        if streak >= 14:
            pool.extend(["exp_candy", "pokeballs", "medicine"])
        return random.choice(pool)

    def _choose_berry_reward(self) -> str:
        return random.choice(BERRY_KEYS)

    def _reward_amount(self, item_key: str, streak: int) -> int:
        if item_key in {"exp_candy", "pokeballs"}:
            return 1
        return 1 + (1 if streak >= 7 and random.random() < 0.35 else 0)

    def claim_daily_gift(self) -> Optional[str]:
        if self.status() != "ready":
            return None
        if not bool(self.config().get("daily_surprise_enabled", True)):
            return None
        companion = self.active_companion()
        if companion is None:
            return None
        state = self.load()
        today = date.today().isoformat()
        if state.last_daily_gift_day == today:
            return None
        item_key = self._choose_daily_reward(state.current_streak)
        amount = self._reward_amount(item_key, state.current_streak) + 1
        state.inventory[item_key] = state.inventory.get(item_key, 0) + amount
        state.last_daily_gift_day = today
        self.last_action = "gift"
        self.save()
        message = f"{self.companion_display_name(companion)}'s daily surprise: {amount} {ITEMS[item_key]['label']}."
        self.notify("Daily Onigimon surprise", message, companion.sprite_url)
        return message

    def _choose_daily_reward(self, streak: int) -> str:
        pool = [self._choose_berry_reward(), "poke_candies", "curry_ingredients", "medicine"]
        if streak >= 7:
            pool.extend(["exp_candy", "mints", "pokeballs", self._choose_berry_reward()])
        if streak >= 30:
            pool.extend(["pokeballs", "exp_candy"])
        return random.choice(pool)

    def use_item(self, item_key: str) -> Optional[str]:
        companion = self.active_companion()
        if companion is None or item_key not in ITEMS:
            return None
        state = self.load()
        if state.inventory.get(item_key, 0) <= 0:
            return None
        if item_key in BERRY_ITEMS and companion.hunger >= 100:
            return f"{self.companion_display_name(companion)} is already full."
        if item_key == "pokeballs":
            return f"{self.companion_display_name(companion)} is saving Pokéballs for future Pokémon."
        state.inventory[item_key] -= 1

        name = self.companion_display_name(companion)
        if item_key in BERRY_ITEMS:
            item = BERRY_ITEMS[item_key]
            type_bonus = self._berry_type_bonus(companion, item)
            companion.hunger = min(100, companion.hunger + int(item.get("hunger", 0)) + type_bonus)
            companion.happiness = min(100, companion.happiness + int(item.get("happiness", 0)) + type_bonus)
            companion.energy = min(100, companion.energy + int(item.get("energy", 0)))
            companion.cleanliness = min(100, companion.cleanliness + int(item.get("cleanliness", 0)))
            companion.bond_xp += int(item.get("bond_xp", 0)) + type_bonus
            if companion.max_hp:
                companion.hp = min(companion.max_hp, companion.hp + int(item.get("hp", 0)) + type_bonus)
            message = f"{name} enjoyed a {item['label']}."
            if type_bonus:
                message = f"{message} It suited {self._type_label(companion.types)} well."
        elif item_key == "curry_ingredients":
            companion.hunger = min(100, companion.hunger + 35)
            companion.happiness = min(100, companion.happiness + 8)
            message = f"{name} loved the curry."
        elif item_key == "poke_candies":
            companion.happiness = min(100, companion.happiness + 15)
            companion.bond_xp += 8
            message = f"{name} looks happier."
        elif item_key == "mints":
            companion.cleanliness = min(100, companion.cleanliness + 30)
            message = f"{name} smells fresh."
        elif item_key == "medicine":
            companion.hp = min(companion.max_hp or companion.hp, companion.hp + max(10, companion.max_hp // 4))
            message = f"{name} recovered some HP."
        elif item_key == "exp_candy":
            companion.bond_xp += 20
            message = f"{name} gained Onigimon bond XP."
        else:
            message = f"{name} is saving that for later."

        self.last_action = item_key
        companion.last_cared_at = datetime.now().isoformat()
        state.companions[companion.ankimon_id] = asdict(companion)
        self.save()
        self.notify("Onigimon care", message, companion.sprite_url)
        return message

    def _berry_type_bonus(self, companion: OnigimonCompanion, berry: Dict[str, Any]) -> int:
        raw_types = companion.types if isinstance(companion.types, list) else [companion.types]
        companion_types = {str(t).lower() for t in raw_types}
        favored = {str(t).lower() for t in berry.get("favored_types", ())}
        return 6 if companion_types.intersection(favored) else 0

    @staticmethod
    def _type_label(types: Any) -> str:
        if not isinstance(types, list):
            types = [types]
        if not types:
            return "this Pokémon"
        return "/".join(t.title() for t in types[:2])

    def play(self) -> Optional[str]:
        companion = self.active_companion()
        if companion is None:
            return None
        state = self.load()
        if self.plays_available(state) <= 0:
            return f"Study 10 cards to earn a play."
        if companion.energy <= 0:
            return f"{self.companion_display_name(companion)} needs a little rest."
        state.plays_used_today += 1
        companion.energy = max(0, companion.energy - 10)
        companion.happiness = min(100, companion.happiness + 10)
        companion.bond_xp += 5
        companion.last_cared_at = datetime.now().isoformat()
        state.companions[companion.ankimon_id] = asdict(companion)
        self.last_action = "play"
        self.save()
        message = f"{self.companion_display_name(companion)} played with you."
        self.notify("Onigimon playtime", message, companion.sprite_url)
        return message

    def notify(self, title: str, description: str, icon_image: str = "") -> None:
        if not bool(self.config().get("notifications_enabled", True)):
            return
        payload = json.dumps(
            {
                "id": "onigimon",
                "variant": "onigimon",
                "name": title,
                "description": description,
                "icon": "Onigimon",
                "iconImage": icon_image,
            },
            ensure_ascii=False,
        )
        script = f"if(window.OnigiriNotifications){{window.OnigiriNotifications.show({payload});}}"
        for web in self._candidate_webviews():
            try:
                web.eval(script)
                return
            except Exception:
                continue

    def _candidate_webviews(self):
        seen = []
        for owner in (getattr(mw, "reviewer", None), getattr(mw, "overview", None), getattr(mw, "deckBrowser", None)):
            web = owner and getattr(owner, "web", None)
            if web and web not in seen:
                seen.append(web)
                yield web


def render_widget_html() -> str:
    payload = manager.widget_payload()
    status = payload["status"]
    inventory = payload["inventory"]
    companion = payload["companion"]
    try:
        addon_package = mw.addonManager.addonFromModule(__name__)
    except Exception:
        addon_package = "1011095603"
    pokeball_icon = f"/_addons/{addon_package}/system_files/system_icons/pokeball.svg"

    if status == "disabled":
        body = "<p>Enable Onigimon in Gamification Settings.</p>"
    elif status == "missing":
        body = "<p>Install Ankimon to choose a Pokémon companion.</p>"
    elif status == "starter_needed":
        body = "<p>Finish choosing your first Ankimon Pokémon, then come back to Onigimon.</p>"
    elif status == "no_collection":
        body = "<p>Your Ankimon starter is ready. Add Pokémon to your Collection PC to choose a companion.</p>"
    elif not companion:
        body = "<p>Choose a Pokémon from Ankimon's Collection PC in Gamification Settings.</p>"
    else:
        name = escape(manager.companion_display_name(companion))
        sprite = companion.get("sprite_url") or ""
        img = f'<img src="{escape(sprite)}" alt="">' if sprite else f'<img class="onigimon-placeholder" src="{escape(pokeball_icon)}" alt="">'
        body = f"""
            <div class="onigimon-main">
                <div class="onigimon-sprite">{img}</div>
                <div class="onigimon-info">
                    <strong>{name}</strong>
                    <span>Lv. {int(companion.get("level") or 1)} · Bond {int(companion.get("bond_level") or 1)}</span>
                </div>
            </div>
            {_meter("Hunger", int(companion.get("hunger", 0)), "#ef8f46")}
            {_meter("Happy", int(companion.get("happiness", 0)), "#f2c94c")}
            {_meter("Fresh", int(companion.get("cleanliness", 0)), "#70c6a6")}
        """

    berry_total = sum(int(inventory.get(key, 0)) for key in BERRY_KEYS)
    widget_counts = (
        ("berry_cheri", berry_total, "Berries"),
        ("poke_candies", int(inventory.get("poke_candies", 0)), ITEMS["poke_candies"]["label"]),
        ("curry_ingredients", int(inventory.get("curry_ingredients", 0)), ITEMS["curry_ingredients"]["label"]),
        ("exp_candy", int(inventory.get("exp_candy", 0)), ITEMS["exp_candy"]["label"]),
        ("medicine", int(inventory.get("medicine", 0)), ITEMS["medicine"]["label"]),
        ("pokeballs", int(inventory.get("pokeballs", 0)), ITEMS["pokeballs"]["label"]),
    )
    item_bits = "".join(
        f"<span title=\"{escape(label)}\">{_item_icon(key)} {count}</span>"
        for key, count, label in widget_counts
    )
    modal = _care_modal_html(payload, companion)
    return f"""
    <div class="onigimon-widget" onclick="pycmd('openGamificationSettings')">
        <div class="onigimon-header">
            <h3>Onigimon</h3>
            <button class="onigimon-ball-btn" title="Open Onigimon care" onclick="event.stopPropagation(); document.getElementById('onigimon-care-modal').classList.add('is-open');">
                <i class="onigimon-ball-icon" style="mask-image: url('{escape(pokeball_icon)}'); -webkit-mask-image: url('{escape(pokeball_icon)}');"></i>
            </button>
        </div>
        <div class="onigimon-body">{body}</div>
        <div class="onigimon-inventory">{item_bits}</div>
    </div>
    {modal}
    """


def _meter(label: str, value: int, color: str) -> str:
    value = max(0, min(100, value))
    return f"""
    <div class="onigimon-meter">
        <span>{escape(label)}</span>
        <div><i style="width:{value}%; background:{color};"></i></div>
    </div>
    """


def _item_icon(item_key: str) -> str:
    item = ITEMS.get(item_key, {})
    url = _item_asset_url(item)
    label = escape(str(item.get("label") or item_key))
    if not url:
        return f"<b>{label[:1]}</b>"
    return f'<img class="onigimon-item-icon" src="{escape(url)}" alt="{label}">'


def _item_asset_url(item: Dict[str, Any]) -> str:
    rel_path = str(item.get("icon_path") or "")
    if rel_path:
        local_url = _addon_asset_url(rel_path)
        if local_url:
            return local_url
    return str(item.get("icon_url") or "")


def _addon_asset_url(rel_path: str) -> str:
    addon_path = os.path.dirname(os.path.dirname(__file__))
    if os.path.exists(os.path.join(addon_path, rel_path)):
        try:
            addon_package = mw.addonManager.addonFromModule(__name__)
        except Exception:
            addon_package = "1011095603"
        return f"/_addons/{addon_package}/{rel_path}"
    return ""


def _care_modal_html(payload: Dict[str, Any], companion: Optional[Dict[str, Any]]) -> str:
    if not companion:
        return ""

    name = escape(manager.companion_display_name(companion))
    inventory = payload.get("inventory", {})
    plays_available = int(payload.get("playsAvailable") or 0)
    play_allowance = int(payload.get("playAllowance") or 0)
    gift_ready = bool(payload.get("dailyGiftReady"))
    last_action = payload.get("lastAction")
    modal_class = "is-open has-reaction" if last_action else ""
    action_key = last_action if last_action in ITEMS else {"play": "poke_candies", "gift": "pokeballs"}.get(str(last_action), "berries")
    flow_item_html = _item_icon(action_key)
    close_icon = _addon_asset_url("system_files/system_icons/xmark-simple.svg")
    modal_sprite = manager.modal_sprite_url(companion)
    sprite_img = f'<img src="{escape(modal_sprite)}" alt="{name}">' if modal_sprite else ""
    categories = (
        ("food", "Food", "berry_cheri", BERRY_KEYS + ("curry_ingredients",), "feed"),
        ("treats", "Treats", "poke_candies", ("poke_candies", "exp_candy"), "gift"),
        ("care", "Care", "mints", ("mints", "medicine"), "gift"),
        ("pokeballs", "Pokéballs", "pokeballs", ("pokeballs",), "none"),
    )
    category_bits = "".join(
        _category_button_html(category_id, label, icon_key, keys, inventory)
        for category_id, label, icon_key, keys, _action in categories
    )
    category_panel_bits = "".join(
        _category_panel_html(category_id, keys, action, inventory, companion)
        for category_id, _label, _icon_key, keys, action in categories
    )
    gift_disabled = "" if gift_ready else "disabled"
    gift_small = "daily ready" if gift_ready else "select gift"
    gift_onclick = "onigimonTriggerReaction('pokeballs'); pycmd('onigimon_daily_gift');" if gift_ready else ""

    return f"""
    <div id="onigimon-care-modal" class="onigimon-care-modal {modal_class}" onclick="event.stopPropagation(); this.classList.remove('is-open'); this.classList.remove('has-reaction');">
        <div class="onigimon-care-dialog" onclick="event.stopPropagation();">
            <button class="onigimon-modal-close" title="Close" onclick="var modal=document.getElementById('onigimon-care-modal'); modal.classList.remove('is-open'); modal.classList.remove('has-reaction');">
                <i class="onigimon-close-icon" aria-label="Close" style="mask-image: url('{escape(close_icon)}'); -webkit-mask-image: url('{escape(close_icon)}');"></i>
            </button>
            <h3>{name}</h3>

            <div class="onigimon-care-display">
                <div class="onigimon-care-item-flow">
                    {flow_item_html}
                </div>
                <div class="onigimon-care-sprite">
                    {sprite_img}
                </div>
            </div>

            <div class="onigimon-care-actions">
                <button id="onigimon-feed-action" disabled onclick="event.stopPropagation();">
                    {_item_icon('berry_cheri')}
                    <span>Feed</span>
                    <small>select food</small>
                </button>
                <button {'disabled' if plays_available <= 0 else ''} onclick="event.stopPropagation(); onigimonTriggerReaction('poke_candies'); pycmd('onigimon_play');">
                    {_item_icon('poke_candies')}
                    <span>Play</span>
                    <small>{plays_available}/{play_allowance} plays</small>
                </button>
                <button id="onigimon-gift-action" {gift_disabled} onclick="event.stopPropagation(); {gift_onclick}">
                    {_item_icon('pokeballs')}
                    <span>Gift</span>
                    <small>{gift_small}</small>
                </button>
            </div>
            <div class="onigimon-modal-inventory">
                <div class="onigimon-modal-inventory-title">Items</div>
                <div class="onigimon-category-grid">{category_bits}</div>
                <div class="onigimon-category-panels">{category_panel_bits}</div>
            </div>
            <script>
            (function(){{
                var modal = document.getElementById('onigimon-care-modal');
                if (!modal) return;
                window.onigimonShowCategory = function(category){{
                    modal.querySelectorAll('.onigimon-category-panel').forEach(function(panel){{
                        panel.classList.toggle('is-open', panel.dataset.category === category);
                    }});
                    modal.querySelectorAll('.onigimon-category-chip').forEach(function(chip){{
                        chip.classList.toggle('is-selected', chip.dataset.category === category);
                    }});
                }};
                window.onigimonSelectCareItem = function(key, action, label){{
                    modal.dataset.selectedItem = key;
                    modal.querySelectorAll('.onigimon-inventory-choice').forEach(function(choice){{
                        choice.classList.toggle('is-selected', choice.dataset.item === key);
                    }});
                    var feed = document.getElementById('onigimon-feed-action');
                    var gift = document.getElementById('onigimon-gift-action');
                    if (feed) {{
                        feed.disabled = action !== 'feed';
                        feed.querySelector('small').textContent = action === 'feed' ? label : 'select food';
                        feed.onclick = function(event) {{
                            event.stopPropagation();
                            if (action === 'feed') {{
                                onigimonTriggerReaction(key);
                                pycmd('onigimon_feed:' + key);
                            }}
                        }};
                    }}
                    if (gift) {{
                        gift.disabled = action !== 'gift';
                        gift.querySelector('small').textContent = action === 'gift' ? label : 'select gift';
                        gift.onclick = function(event) {{
                            event.stopPropagation();
                            if (action === 'gift') {{
                                onigimonTriggerReaction(key);
                                pycmd('onigimon_feed:' + key);
                            }}
                        }};
                    }}
                }};
                window.onigimonTriggerReaction = function(key){{
                    var flow = modal.querySelector('.onigimon-care-item-flow');
                    var source = modal.querySelector('[data-item="' + key + '"] .onigimon-item-icon') ||
                        modal.querySelector('.onigimon-category-chip[data-category="' + key + '"] .onigimon-item-icon');
                    if (flow && source) {{
                        flow.innerHTML = '';
                        flow.appendChild(source.cloneNode(true));
                    }}
                    modal.classList.remove('has-reaction');
                    void modal.offsetWidth;
                    modal.classList.add('has-reaction');
                }};
            }})();
            </script>
        </div>
    </div>
    """


def _category_button_html(category_id: str, label: str, icon_key: str, keys: tuple, inventory: Dict[str, int]) -> str:
    count = sum(int(inventory.get(key, 0)) for key in keys)
    disabled = "disabled" if count <= 0 else ""
    return f"""
    <button class="onigimon-category-chip" data-category="{escape(category_id)}" {_item_color_style(category_id)} {disabled} onclick="event.stopPropagation(); onigimonShowCategory('{escape(category_id)}');">
        {_item_icon(icon_key)}
        <span>{escape(label)}</span>
        <b>{count}</b>
    </button>
    """


def _category_panel_html(category_id: str, keys: tuple, action: str, inventory: Dict[str, int], companion: Dict[str, Any]) -> str:
    available = [key for key in keys if int(inventory.get(key, 0)) > 0]
    if not available:
        item_bits = '<div class="onigimon-empty-category">Nothing here yet.</div>'
    else:
        item_bits = "".join(
            _inventory_choice_html(key, action, int(inventory.get(key, 0)), companion)
            for key in available
        )
    return f"""
    <div class="onigimon-category-panel" data-category="{escape(category_id)}">
        {item_bits}
    </div>
    """


def _inventory_choice_html(item_key: str, action: str, count: int, companion: Dict[str, Any]) -> str:
    label = str(ITEMS[item_key]["label"])
    hint = _inventory_item_hint(item_key, companion)
    if action == "none":
        return f"""
        <div class="onigimon-inventory-choice is-passive" {_item_color_style(item_key)} title="{escape(hint)}">
            {_item_icon(item_key)}
            <span>{escape(label)}</span>
            <small>{escape(hint)} · {count}</small>
        </div>
        """
    return f"""
    <button class="onigimon-inventory-choice" data-item="{escape(item_key)}" {_item_color_style(item_key)} title="{escape(hint)}" onclick="event.stopPropagation(); onigimonSelectCareItem({json.dumps(item_key)}, {json.dumps(action)}, {json.dumps(label)});">
        {_item_icon(item_key)}
        <span>{escape(label)}</span>
        <small>{escape(hint)} · {count}</small>
    </button>
    """


def _item_color_style(key: str) -> str:
    border, light_bg, dark_bg = ITEM_COLORS.get(key, ("#70c6a6", "#e1f5ec", "#183b2c"))
    return (
        'style="'
        f"--onigimon-item-color: {border}; "
        f"--onigimon-item-bg-light: {light_bg}; "
        f"--onigimon-item-bg-dark: {dark_bg};"
        '"'
    )


def _inventory_item_hint(item_key: str, companion: Dict[str, Any]) -> str:
    item = ITEMS.get(item_key, {})
    if item_key in BERRY_ITEMS:
        favored = tuple(str(t).title() for t in item.get("favored_types", ()))
        companion_types = {str(t).lower() for t in companion.get("types", [])}
        match = companion_types.intersection({str(t).lower() for t in item.get("favored_types", ())})
        prefix = "Best for " + "/".join(favored[:3]) if favored else "Berry"
        suffix = "type bonus" if match else str(item.get("effect", "Care"))
        return f"{prefix}; {suffix}"
    return str(item.get("effect") or item.get("label") or item_key)


manager = OnigimonManager()


def register_hooks() -> None:
    gui_hooks.reviewer_did_answer_card.append(manager.on_answer)


register_hooks()
