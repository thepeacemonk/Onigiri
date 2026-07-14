from __future__ import annotations

import json
import os
import random
import re
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from html import escape
from math import exp
from typing import Any, Dict, List, Optional, Union

from aqt import gui_hooks, mw

from .. import config
from ..onigiri_notifications import notify as show_onigiri_notification
from ..translations import tr


ANKIMON_ADDON_IDS = ("1908235722", "Ankimon")

ONIGIMON_DIFFICULTY_SETTINGS = {
    "bulbassaur": {
        "label": "Bulbassaur",
        "reward_multiplier": 0.75,
        "missed_day_decay": 10,
        "wrong_answer_penalty": 2,
        "reward_setback": 1,
        "comet_interval": 5,
        "star_piece_chance": 0.18,
        "bonus_amount_chance": 0.35,
        "market_coin_chance": 0.7,
        "market_gift_bonus_chance": 0.4,
    },
    "pikachu": {
        "label": "Pikachu",
        "reward_multiplier": 1.0,
        "missed_day_decay": 15,
        "wrong_answer_penalty": 4,
        "reward_setback": 1,
        "comet_interval": 7,
        "star_piece_chance": 0.12,
        "bonus_amount_chance": 0.25,
        "market_coin_chance": 0.55,
        "market_gift_bonus_chance": 0.25,
    },
    "charizard": {
        "label": "Charizard",
        "reward_multiplier": 1.75,
        "missed_day_decay": 22,
        "wrong_answer_penalty": 7,
        "reward_setback": 2,
        "comet_interval": 10,
        "star_piece_chance": 0.06,
        "bonus_amount_chance": 0.12,
        "market_coin_chance": 0.35,
        "market_gift_bonus_chance": 0.12,
    },
}


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
    "play_action": {
        "label": "Play",
        "icon_path": "system_files/pokesprite/items/fluffy-tail.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/other-item/fluffy-tail.png",
    },
    "train_action": {
        "label": "Train",
        "icon_path": "system_files/pokesprite/items/hold-item-muscle-band.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/hold-item/muscle-band.png",
    },
    "daily_gift_action": {
        "label": "Daily Gift",
        "icon_path": "system_files/pokesprite/items/relic-copper.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/relic-copper.png",
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
        "hp": 5,
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
        "hp": 5,
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
        "hp": 8,
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
        "hp": 8,
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
        "hp": 10,
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
        "hp": 15,
    },
    "berry_oran": {
        "label": "Oran Berry",
        "icon_path": "system_files/pokesprite/items/berry-oran.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/berry/oran.png",
        "favored_types": ("fighting", "normal", "rock"),
        "effect": "Reliable hunger care",
        "hunger": 25,
        "happiness": 3,
        "hp": 20,
    },
    "berry_sitrus": {
        "label": "Sitrus Berry",
        "icon_path": "system_files/pokesprite/items/berry-sitrus.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/berry/sitrus.png",
        "favored_types": ("grass", "ground", "water"),
        "effect": "Hunger and HP",
        "hunger": 30,
        "happiness": 5,
        "hp": 30,
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
        "hp": 50,
    },
}
ONIGIMON_EXTRA_ITEMS = {
    "medicine": {
        "label": "Potion",
        "icon_path": "system_files/pokesprite/items/medicine-potion.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/medicine/potion.png",
        "effect": "Restores health",
        "hp": 50,
        "cleanliness": 4,
    },
    "mint_attack_food": {
        "label": "Attack Mint",
        "icon_path": "system_files/pokesprite/items/mint-attack.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/mint/attack.png",
        "effect": "Fresh food",
        "hunger": 18,
        "happiness": 6,
        "xp": 8,
    },
    "petal_red": {
        "label": "Red Petal",
        "icon_path": "system_files/pokesprite/items/petal-red.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/petal/red.png",
        "effect": "Gentle medicine",
        "hp": 18,
        "happiness": 5,
    },
    "held_macho_brace": {
        "label": "Muscle Band",
        "icon_path": "system_files/pokesprite/items/hold-item-muscle-band.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/hold-item/muscle-band.png",
        "effect": "Training item",
        "attack": 1,
        "bond_xp": 12,
    },
    "held_power_weight": {
        "label": "Power Herb",
        "icon_path": "system_files/pokesprite/items/hold-item-power-herb.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/hold-item/power-herb.png",
        "effect": "Training item",
        "defense": 1,
        "bond_xp": 10,
    },
    "play_fluffy_tail": {
        "label": "Fluffy Tail",
        "icon_path": "system_files/pokesprite/items/fluffy-tail.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/other-item/fluffy-tail.png",
        "effect": "Play item",
        "happiness": 18,
        "defense": 1,
    },
    "battle_x_attack": {
        "label": "X Attack",
        "icon_path": "system_files/pokesprite/items/battle-item-x-attack.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/battle-item/x-attack.png",
        "effect": "Exciting play",
        "happiness": 12,
        "attack": 1,
    },
    "ball_great": {
        "label": "Great Ball",
        "icon_path": "system_files/pokesprite/items/ball-great.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/ball/great.png",
        "effect": "Play item",
        "happiness": 14,
    },
    "valuable_star_piece": {
        "label": "Star Piece",
        "icon_path": "system_files/pokesprite/items/valuable-item-star-piece.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/valuable-item/star-piece.png",
        "effect": "Worth 10 comet shards",
    },
    "valuable_comet_shard": {
        "label": "Comet Shard",
        "icon_path": "system_files/pokesprite/items/valuable-item-comet-shard.png",
        "icon_url": "https://raw.githubusercontent.com/msikma/pokesprite/master/items/valuable-item/comet-shard.png",
        "effect": "Onigimon coin",
    },
}
ITEMS.update(BERRY_ITEMS)
ITEMS.update(ONIGIMON_EXTRA_ITEMS)


def _onigimon_item_label(item_key: str) -> str:
    item = ITEMS.get(item_key, {})
    fallback = str(item.get("label") or item_key)
    return tr(f"onigimon_item_{item_key}", fallback)


def _onigimon_item_effect(item_key: str) -> str:
    item = ITEMS.get(item_key, {})
    fallback = str(item.get("effect") or item.get("label") or item_key)
    key = re.sub(r"[^a-z0-9]+", "_", fallback.lower()).strip("_")
    return tr(f"onigimon_effect_{key}", fallback)


BERRY_KEYS = tuple(BERRY_ITEMS.keys())
FOOD_ITEM_KEYS = BERRY_KEYS + ("poke_candies", "exp_candy", "curry_ingredients", "mint_attack_food")
MEDICINE_ITEM_KEYS = ("medicine", "petal_red", "mints")
HYGIENE_ITEM_KEYS = ("mints", "medicine")
TRAINING_ITEM_KEYS = ("held_macho_brace", "held_power_weight", "exp_candy")
HAPPINESS_ITEM_KEYS = ("play_fluffy_tail", "battle_x_attack", "ball_great", "pokeballs", "poke_candies")
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
    "play_action": ("#ff6fc8", "#ffe0f3", "#4a1735"),
    "train_action": ("#f08d3c", "#ffead6", "#472815"),
    "daily_gift_action": ("#61c486", "#e3f8ea", "#173b27"),
    "medicine": ("#08c46b", "#dff8e9", "#12391f"),
    "mint_attack_food": ("#7fd36c", "#e8f9df", "#1f4018"),
    "petal_red": ("#ed6f89", "#ffe4ea", "#471722"),
    "held_macho_brace": ("#c866e5", "#f5ddff", "#371544"),
    "held_power_weight": ("#4da1dd", "#e0f1ff", "#15344a"),
    "play_fluffy_tail": ("#ffbc52", "#fff0d7", "#4a3114"),
    "battle_x_attack": ("#ff9a3e", "#ffe9d4", "#4a2914"),
    "ball_great": ("#4f9ee8", "#e2f0ff", "#16364f"),
    "valuable_star_piece": ("#ffc247", "#fff1cf", "#49340e"),
    "valuable_comet_shard": ("#5bb5ef", "#dff3ff", "#14384b"),
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
    hp_stat: int = 0
    attack: int = 0
    defense: int = 0
    speed: int = 0
    friendship: int = 0
    xp: int = 0
    sprite_url: str = ""
    sprite_fallbacks: List[str] = field(default_factory=list)
    types: List[str] = field(default_factory=list)
    hunger: int = 70
    happiness: int = 50
    cleanliness: int = 60
    bond_xp: int = 0
    bond_level: int = 1
    energy: int = 70
    training: int = 50
    last_cared_at: str = ""
    is_favorite: bool = False
    is_main: bool = False
    shiny: bool = False


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
    comet_shards: int = 120
    star_pieces: int = 2
    market_day: str = ""
    market_items: List[Dict[str, Any]] = field(default_factory=list)
    market_purchased: List[str] = field(default_factory=list)
    last_market_gift_day: str = ""
    last_decay_processed_day: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.companions, dict):
            self.companions = {}
        if not isinstance(self.inventory, dict):
            self.inventory = {}
        try:
            self.comet_shards = int(self.comet_shards or 0)
        except Exception:
            self.comet_shards = 0
        try:
            self.star_pieces = int(self.star_pieces or 0)
        except Exception:
            self.star_pieces = 0
        if not isinstance(self.market_items, list):
            self.market_items = []
        if not isinstance(self.market_purchased, list):
            self.market_purchased = []
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

    def _has_main_pokemon(self) -> bool:
        try:
            return bool(self.get_main_pokemon())
        except Exception:
            return False

    def get_collection(self) -> List[Dict[str, Any]]:
        if not self.detect():
            return []
        now = time.time()
        if now - self._collection_cache_time < 10:
            return self._collection_cache

        db = getattr(mw, "ankimon_db", None)
        if db and hasattr(db, "get_all_pokemon"):
            try:
                res = []
                for p in db.get_all_pokemon():
                    if isinstance(p, dict):
                        res.append(self._normalize_pokemon(p))
                self._collection_cache = res
                self._collection_cache_time = now
                return res
            except Exception:
                pass
        
        self._collection_cache = []
        self._collection_cache_time = now
        return self._collection_cache

    def clear_cache(self) -> None:
        self._collection_cache = []
        self._collection_cache_time = 0.0

    def update_ankimon_stat(self, ankimon_id: str, updates: Dict[str, int]) -> bool:
        if not self.detect():
            return False

        db = getattr(mw, "ankimon_db", None)
        if db:
            try:
                pokemon = db.get_pokemon(str(ankimon_id)) if hasattr(db, "get_pokemon") else None
                main = db.get_main_pokemon() if hasattr(db, "get_main_pokemon") else None
                is_main = bool(main and self._pokemon_identity(main) == str(ankimon_id))
                if not pokemon and is_main:
                    pokemon = main
                if not isinstance(pokemon, dict):
                    return False

                self._apply_stat_updates(pokemon, updates)

                if is_main and hasattr(db, "save_main_pokemon"):
                    db.save_main_pokemon(pokemon)
                elif hasattr(db, "save_pokemon"):
                    db.save_pokemon(pokemon)
                else:
                    return False

                self._update_runtime_main_object(pokemon)
                self.clear_cache()
                return True
            except Exception as e:
                print(f"Onigimon: Error in update_ankimon_stat (runtime): {e}")
                import traceback
                traceback.print_exc()
                # Fall through to direct-DB fallback

        # Fallback: write directly to ankimon.db on disk
        try:
            pokemon = self._read_main_pokemon_raw()
            if not isinstance(pokemon, dict):
                return False
            if self._pokemon_identity(pokemon) != str(ankimon_id):
                return False
            self._apply_stat_updates(pokemon, updates)
            if self._write_main_to_db(pokemon):
                self._update_runtime_main_object(pokemon)
                self.clear_cache()
                return True
        except Exception as e:
            print(f"Onigimon: Error in update_ankimon_stat (direct DB): {e}")
            import traceback
            traceback.print_exc()
        return False

    def set_main_pokemon(self, ankimon_id: str) -> bool:
        if not self.detect():
            return False

        db = getattr(mw, "ankimon_db", None)
        if db and hasattr(db, "set_main_pokemon"):
            try:
                if db.set_main_pokemon(str(ankimon_id)):
                    pokemon = db.get_pokemon(str(ankimon_id)) if hasattr(db, "get_pokemon") else None
                    if pokemon:
                        self._update_runtime_main_object(pokemon)
                    self.clear_cache()
                    return True
            except Exception:
                pass
        return False

    def get_main_pokemon(self) -> Dict[str, Any]:
        """Returns the main Pokémon as a normalised dict.

        HP source-of-truth priority:
          1. Live runtime PokemonObject (most accurate – reflects battle damage)
          2. ankimon.db via mw.ankimon_db runtime API
          3. ankimon.db read directly from disk (fallback when Ankimon not loaded)
        """
        if not self.detect():
            return {}

        # Fetch raw data from DB (used for all fields except hp / max_hp)
        raw: Dict[str, Any] = {}
        db = getattr(mw, "ankimon_db", None)
        if db and hasattr(db, "get_main_pokemon"):
            try:
                main = db.get_main_pokemon()
                if isinstance(main, dict):
                    raw = {**main, "is_main": 1}
            except Exception:
                pass
        if not raw:
            raw = self._read_main_pokemon_raw()
        if not raw:
            return {}

        # Inject authoritative HP values from the live runtime object.
        # This ensures current_hp reflects in-battle damage not yet saved to DB,
        # and max_hp uses Ankimon’s canonical calculation (from Pokédex base_stats).
        hp_info = self._get_main_runtime_hp()
        if hp_info:
            raw["current_hp"] = hp_info["current_hp"]
            raw["hp"] = hp_info["current_hp"]
            raw["max_hp"] = hp_info["max_hp"]

        return self._normalize_pokemon(raw)

    def _get_main_runtime_hp(self) -> Dict[str, int]:
        """Returns {'current_hp': int, 'max_hp': int} from the live Ankimon
        PokemonObject, or {} if the runtime is unavailable.

        This is the single authoritative source for HP values inside Onigimon.
        Falls back to computing max_hp from the DB formula when runtime is absent.
        """
        try:
            singletons = sys.modules.get("Ankimon.singletons")
            if singletons is not None:
                main = getattr(singletons, "main_pokemon", None)
                if main is not None:
                    current_hp = int(getattr(main, "hp", 0) or 0)
                    max_hp = int(getattr(main, "max_hp", 0) or 0)
                    if max_hp > 0:
                        return {"current_hp": current_hp, "max_hp": max_hp}
        except Exception as e:
            print(f"Onigimon: _get_main_runtime_hp (runtime) failed: {e}")

        # Fallback: compute max_hp from DB data using Ankimon's formula.
        try:
            db = getattr(mw, "ankimon_db", None)
            raw = None
            if db and hasattr(db, "get_main_pokemon"):
                raw = db.get_main_pokemon()
            if not raw:
                raw = self._read_main_pokemon_raw()
            if isinstance(raw, dict):
                stats = raw.get("base_stats") if isinstance(raw.get("base_stats"), dict) else {}
                hp_stat = int(stats.get("hp", 0) or 0)
                level = int(raw.get("level", 1) or 1)
                iv_hp = int((raw.get("iv") or {}).get("hp", 0) or 0)
                ev_hp = int((raw.get("ev") or {}).get("hp", 0) or 0)
                if hp_stat > 0:
                    max_hp = 10 + level + int((2 * hp_stat + iv_hp + int(ev_hp / 4)) * level / 100)
                    current_hp = int(raw.get("current_hp") or raw.get("hp") or max_hp)
                    return {"current_hp": current_hp, "max_hp": max_hp}
        except Exception as e:
            print(f"Onigimon: _get_main_runtime_hp (DB fallback) failed: {e}")
        return {}

    def _update_runtime_main_object(self, pokemon_data: Dict[str, Any]) -> None:
        """Pushes stat changes from Onigimon back into Ankimon's live PokemonObject."""
        if not isinstance(pokemon_data, dict):
            return
        try:
            ankimon_singletons = sys.modules.get("Ankimon.singletons")
            if ankimon_singletons is None:
                return
            main_pokemon = getattr(ankimon_singletons, "main_pokemon", None)
            if not main_pokemon or self._pokemon_identity(pokemon_data) != str(getattr(main_pokemon, "individual_id", "")):
                return

            if "base_stats" in pokemon_data and hasattr(main_pokemon, "base_stats"):
                main_pokemon.base_stats.update(pokemon_data["base_stats"])

            if "xp" in pokemon_data and hasattr(main_pokemon, "xp"):
                main_pokemon.xp = pokemon_data["xp"]

            # Update both hp fields that Ankimon uses.
            # main_pokemon.hp  = the current HP value shown in the tracker bar.
            # main_pokemon.current_hp = secondary reference used in battle hooks.
            new_hp = pokemon_data.get("current_hp", pokemon_data.get("hp"))
            if new_hp is not None:
                new_hp = int(new_hp)
                if hasattr(main_pokemon, "hp"):
                    main_pokemon.hp = new_hp
                if hasattr(main_pokemon, "current_hp"):
                    main_pokemon.current_hp = new_hp

            # Recompute max_hp from canonical base_stats (Ankimon’s own formula).
            if hasattr(main_pokemon, "calculate_max_hp"):
                main_pokemon.max_hp = main_pokemon.calculate_max_hp()

            tracker = getattr(ankimon_singletons, "ankimon_tracker_obj", None)
            if tracker and hasattr(tracker, "update_gui"):
                tracker.update_gui()
        except Exception as e:
            print(f"Onigimon: _update_runtime_main_object failed: {e}")

    def _apply_stat_updates(self, pokemon_data: Dict[str, Any], updates: Dict[str, int]) -> None:
        stat_aliases = {
            "attack": "atk",
            "atk": "atk",
            "defense": "def",
            "def": "def",
            "special_attack": "spa",
            "special-attack": "spa",
            "spa": "spa",
            "special_defense": "spd",
            "special-defense": "spd",
            "spd": "spd",
            "speed": "spe",
            "spe": "spe",
            "exp": "xp",
            "experience": "xp",
            "xp": "xp",
        }
        for stat, raw_change in updates.items():
            change = self._safe_int(raw_change, 0)
            key = stat_aliases.get(str(stat).lower(), str(stat).lower())
            if key == "hp":
                # Use the live runtime HP as the authoritative source so that
                # heals/damage respect the same current and max values Ankimon uses.
                hp_info = self._get_main_runtime_hp()
                if hp_info:
                    current_hp = hp_info["current_hp"]
                    max_hp = hp_info["max_hp"]
                else:
                    # Fallback: read from the pokemon_data dict and compute max_hp
                    # using the same formula as Ankimon’s calculate_max_hp().
                    current_hp = self._safe_int(
                        self._first_present(pokemon_data, ("current_hp", "currenthp", "hp"), 0), 0
                    )
                    stats = (
                        pokemon_data.get("base_stats")
                        if isinstance(pokemon_data.get("base_stats"), dict)
                        else pokemon_data.get("stats")
                        if isinstance(pokemon_data.get("stats"), dict)
                        else {}
                    )
                    hp_stat = self._safe_int(stats.get("hp"), 0)
                    level = self._safe_int(pokemon_data.get("level"), 1)
                    iv_dict = pokemon_data.get("iv") or pokemon_data.get("ivs") or {}
                    ev_dict = pokemon_data.get("ev") or pokemon_data.get("evs") or {}
                    if not isinstance(iv_dict, dict): iv_dict = {}
                    if not isinstance(ev_dict, dict): ev_dict = {}
                    iv_hp = self._safe_int(iv_dict.get("hp"), 0)
                    ev_hp = self._safe_int(ev_dict.get("hp"), 0)
                    # Ankimon formula: 10 + level + int((2*base + iv + int(ev/4)) * level / 100)
                    max_hp = (
                        10 + level + int((2 * hp_stat + iv_hp + int(ev_hp / 4)) * level / 100)
                        if hp_stat > 0 else 0
                    )
                new_hp = max(0, current_hp + change)
                if max_hp > 0:
                    new_hp = min(max_hp, new_hp)
                pokemon_data["current_hp"] = new_hp
                pokemon_data["hp"] = new_hp
            elif key == "xp":
                current_xp = self._safe_int(self._first_present(pokemon_data, ("xp",), 0), 0)
                pokemon_data["xp"] = max(0, current_xp + change)
            elif key in {"atk", "def", "spa", "spd", "spe"}:
                if "base_stats" not in pokemon_data or not isinstance(pokemon_data["base_stats"], dict):
                    pokemon_data["base_stats"] = {"hp": 1, "atk": 1, "def": 1, "spa": 1, "spd": 1, "spe": 1}
                pokemon_data["base_stats"][key] = self._safe_int(pokemon_data["base_stats"].get(key), 1) + change
            else:
                pokemon_data[key] = self._safe_int(pokemon_data.get(key), 0) + change

    def _explicit_max_hp(self, pokemon_data: Dict[str, Any]) -> int:
        return self._safe_int(
            self._first_present(pokemon_data, ("max_hp", "maxhp", "maximum_hp"), 0),
            0,
        )

    def _normalize_pokemon(self, data: Dict[str, Any]) -> Dict[str, Any]:
        raw_id = self._pokemon_identity(data)
        pokedex_id = self._safe_int(data.get("pokedex_id") or data.get("pokemon_id") or data.get("species_id") or data.get("id"), 0)
        name = str(data.get("nickname") or data.get("name") or f"Pokemon {pokedex_id}")
        stats = data.get("base_stats") if isinstance(data.get("base_stats"), dict) else data.get("stats") if isinstance(data.get("stats"), dict) else {}
        
        level = self._safe_int(data.get("level"), 1)
        max_hp = self._explicit_max_hp(data)
        hp_stat = self._safe_int(stats.get("hp"), 0)
        
        iv_dict = data.get("iv") or data.get("ivs") or {}
        ev_dict = data.get("ev") or data.get("evs") or {}
        if not isinstance(iv_dict, dict): iv_dict = {}
        if not isinstance(ev_dict, dict): ev_dict = {}
        
        if max_hp <= 0 and hp_stat > 0:
            iv_value = self._safe_number(iv_dict.get("hp"), 0)
            ev_value = self._safe_number(ev_dict.get("hp"), 0) / 4.0
            if hp_stat == 1:
                max_hp = 1
            else:
                max_hp = int(((hp_stat * 2 + iv_value + ev_value) * level) / 100) + level + 10

        nature = str(data.get("nature") or "serious").lower()
        
        def calc_stat_val(stat_key: str, fallback_key: str = "") -> int:
            base_val = self._safe_int(stats.get(stat_key) or stats.get(fallback_key), 0)
            if base_val <= 0: return 0
            iv_val = self._safe_number(iv_dict.get(stat_key) or iv_dict.get(fallback_key), 0)
            ev_val = self._safe_number(ev_dict.get(stat_key) or ev_dict.get(fallback_key), 0)
            
            mult = 1.0
            if stat_key == "atk":
                if nature in ("lonely", "brave", "adamant", "naughty"): mult = 1.1
                if nature in ("bold", "timid", "modest", "calm"): mult = 0.9
            elif stat_key == "def":
                if nature in ("bold", "relaxed", "impish", "lax"): mult = 1.1
                if nature in ("lonely", "hasty", "mild", "gentle"): mult = 0.9
            elif stat_key == "spe":
                if nature in ("timid", "hasty", "jolly", "naive"): mult = 1.1
                if nature in ("brave", "relaxed", "quiet", "sassy"): mult = 0.9
                
            return int((5 + int((2 * base_val + iv_val + int(ev_val / 4.0)) * level / 100)) * mult)


        xp = self._safe_int(self._first_present(data, ("xp",), stats.get("xp")), 0)

        hp = self._safe_int(self._first_present(data, ("current_hp", "currenthp", "hp"), 0), 0)

        shiny = bool(data.get("shiny", False))
        sprite_url = self.sprite_url(pokedex_id, name, shiny)
        pokemon = {
            "ankimon_id": str(raw_id),
            "name": name,
            "pokedex_id": pokedex_id,
            "level": level,
            "hp": hp,
            "max_hp": max_hp,
            "hp_stat": hp_stat,
            "attack": calc_stat_val("atk"),
            "defense": calc_stat_val("def"),
            "speed": calc_stat_val("spe", "speed"),
            "friendship": self._safe_int(data.get("friendship") or data.get("happiness") or 0, 0),
            "xp": xp,
            "sprite_url": sprite_url,
            "sprite_fallbacks": self.sprite_fallback_urls(pokedex_id, name, shiny, exclude=sprite_url),
            "types": self._normalize_types(data),
            "is_favorite": bool(data.get("is_favorite", False)),
            "is_main": bool(data.get("is_main", False)),
            "shiny": shiny,
        }
        return pokemon

    def _pokemon_identity(self, data: Dict[str, Any]) -> str:
        return str(
            data.get("individual_id")
            or data.get("uuid")
            or data.get("id_in_collection")
            or data.get("caught_id")
            or data.get("id")
            or data.get("pokedex_id")
            or data.get("name")
            or ""
        )

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

    @staticmethod
    def _safe_number(value: Any, default: Union[int, float] = 0) -> Union[int, float]:
        try:
            number = float(value)
        except Exception:
            return default
        return int(number) if number.is_integer() else number

    @staticmethod
    def _first_present(data: Dict[str, Any], keys: tuple, default: Any = None) -> Any:
        for key in keys:
            if key in data and data.get(key) is not None:
                return data.get(key)
        return default

    def sprite_url(self, pokedex_id: int, name: str = "", shiny: bool = False) -> str:
        urls = self.sprite_fallback_urls(pokedex_id, name, shiny)
        return urls[0] if urls else ""

    def sprite_fallback_urls(self, pokedex_id: int, name: str = "", shiny: bool = False, exclude: str = "") -> List[str]:
        if not pokedex_id:
            return []
        if not self.addon_id:
            self.detect()
        motion = str(config.get_config().get("onigimon", {}).get("sprite_motion", "static"))
        animated_first = motion == "gif"
        candidates: List[tuple[str, str]] = []
        if animated_first:
            candidates.extend((folder, f"{pokedex_id}.gif") for folder in ("front_shiny_gif", "front_default_gif"))
            candidates.extend((folder, f"{pokedex_id}.png") for folder in ("front_shiny", "front_default"))
        else:
            candidates.extend((folder, f"{pokedex_id}.png") for folder in ("front_shiny", "front_default"))
            candidates.extend((folder, f"{pokedex_id}.gif") for folder in ("front_shiny_gif", "front_default_gif"))

        urls: List[str] = []
        for folder, filename in candidates:
            if "shiny" in folder and not shiny:
                continue
            rel = f"user_files/sprites/{folder}/{filename}"
            if self.addon_path and os.path.exists(os.path.join(self.addon_path, rel)):
                urls.append(f"/_addons/{self.addon_id}/{rel}")

        pokesprite = self._pokesprite_url(name, shiny)
        if pokesprite:
            urls.append(pokesprite)
        shiny_part = "shiny/" if shiny else ""
        urls.append(f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{shiny_part}{pokedex_id}.png")

        seen = set()
        deduped = []
        for url in urls:
            if url and url != exclude and url not in seen:
                seen.add(url)
                deduped.append(url)
        return deduped

    def animated_sprite_url(self, pokedex_id: int, shiny: bool = False) -> str:
        urls = self.sprite_fallback_urls(pokedex_id, "", shiny)
        return urls[0] if urls else ""

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

    # ------------------------------------------------------------------
    # Direct ankimon.db access (fallback when mw.ankimon_db is absent)
    # ------------------------------------------------------------------

    def _db_path(self) -> str:
        """Returns the absolute path to ankimon.db, or '' if not found."""
        if not self.detect():
            return ""
        candidate = os.path.join(self.addon_path, "user_files", "ankimon.db")
        if os.path.isfile(candidate):
            return candidate
        return ""

    def _read_main_pokemon_raw(self) -> Dict[str, Any]:
        """Reads the raw main Pokémon dict directly from ankimon.db (read-only)."""
        path = self._db_path()
        if not path:
            return {}
        try:
            uri = f"file:{path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT data FROM captured_pokemon WHERE is_main = 1 LIMIT 1"
            )
            row = cur.fetchone()
            conn.close()
            if row:
                data = json.loads(row["data"])
                data["is_main"] = 1
                return data
        except Exception as e:
            print(f"Onigimon: direct DB read (raw) failed: {e}")
        return {}

    def _read_main_from_db(self) -> Dict[str, Any]:
        """Reads and normalises the main Pokémon from ankimon.db (read-only fallback)."""
        data = self._read_main_pokemon_raw()
        if data:
            return self._normalize_pokemon(data)
        return {}

    def _write_main_to_db(self, pokemon_data: Dict[str, Any]) -> bool:
        """Writes updated pokemon_data back to ankimon.db (direct write, last-resort fallback)."""
        path = self._db_path()
        if not path:
            return False
        try:
            individual_id = self._pokemon_identity(pokemon_data)
            if not individual_id:
                return False
            data_str = json.dumps(pokemon_data, ensure_ascii=False)
            conn = sqlite3.connect(path, check_same_thread=False)
            cursor = conn.execute(
                "UPDATE captured_pokemon SET data = ? WHERE individual_id = ? AND is_main = 1",
                (data_str, individual_id),
            )
            conn.commit()
            changed = cursor.rowcount > 0
            conn.close()
            if not changed:
                print(f"Onigimon: direct DB write – no row updated for id={individual_id}")
            return changed
        except Exception as e:
            print(f"Onigimon: direct DB write failed: {e}")
        return False


class OnigimonManager:
    def __init__(self) -> None:
        self.bridge = AnkimonBridge()
        self._state: Optional[OnigimonState] = None
        self.last_action: Optional[str] = None
        self.last_message: str = ""
        self.last_gift: Optional[Dict[str, Any]] = None

    def config(self) -> Dict[str, Any]:
        conf = config.get_config().get("onigimon", {})
        return conf if isinstance(conf, dict) else {}

    def is_enabled(self) -> bool:
        return bool(self.config().get("enabled", False))

    def difficulty_key(self) -> str:
        key = str(self.config().get("difficulty", "pikachu") or "pikachu").lower()
        return key if key in ONIGIMON_DIFFICULTY_SETTINGS else "pikachu"

    def effective_reward_interval(self) -> int:
        difficulty = self.difficulty_key()
        if difficulty == "bulbassaur":
            return 3
        elif difficulty == "pikachu":
            return 6
        elif difficulty == "charizard":
            return 12
        return 6

    def missed_day_decay_amount(self, missed_days: int) -> int:
        settings = ONIGIMON_DIFFICULTY_SETTINGS[self.difficulty_key()]
        return max(0, int(missed_days) * int(settings["missed_day_decay"]))

    def wrong_answer_penalty(self) -> int:
        settings = ONIGIMON_DIFFICULTY_SETTINGS[self.difficulty_key()]
        return max(1, int(settings["wrong_answer_penalty"]))

    def wrong_answer_reward_setback(self) -> int:
        settings = ONIGIMON_DIFFICULTY_SETTINGS[self.difficulty_key()]
        return max(0, int(settings["reward_setback"]))

    def difficulty_value(self, key: str, fallback: Any) -> Any:
        return ONIGIMON_DIFFICULTY_SETTINGS[self.difficulty_key()].get(key, fallback)

    def comet_reward_interval(self) -> int:
        return max(1, int(self.difficulty_value("comet_interval", 5)))

    def star_piece_chance(self) -> float:
        return max(0.0, min(1.0, float(self.difficulty_value("star_piece_chance", 0.12))))

    def bonus_amount_chance(self) -> float:
        return max(0.0, min(1.0, float(self.difficulty_value("bonus_amount_chance", 0.25))))

    def market_coin_chance(self) -> float:
        return max(0.0, min(1.0, float(self.difficulty_value("market_coin_chance", 0.55))))

    def market_gift_bonus_chance(self) -> float:
        return max(0.0, min(1.0, float(self.difficulty_value("market_gift_bonus_chance", 0.25))))

    @staticmethod
    def is_correct_answer(ease: int) -> bool:
        return int(ease or 0) > 1

    def item_icon_url(self, item_key: str) -> str:
        item = ITEMS.get(item_key, {})
        rel_path = str(item.get("icon_path") or "")
        if rel_path:
            try:
                addon_package = mw.addonManager.addonFromModule(__name__)
            except Exception:
                addon_package = "1011095603"
            return f"/_addons/{addon_package}/{rel_path}"
        return str(item.get("icon_url") or "")

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

    def set_active_companion(self, ankimon_id: str, update_ankimon_main: bool = True) -> bool:
        state = self.load()
        found = None
        for pokemon in self.get_available_companions():
            if str(pokemon.get("ankimon_id")) == str(ankimon_id):
                found = pokemon
                break
        if not found:
            return False
        existing = state.companions.get(str(ankimon_id), {})
        companion = OnigimonCompanion(**{**existing, **found, **{"ankimon_id": str(ankimon_id)}})
        state.companions[str(ankimon_id)] = asdict(companion)
        state.active_companion_id = str(ankimon_id)
        self.save()
        if update_ankimon_main:
            self.bridge.set_main_pokemon(str(ankimon_id))
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

    def decay_needs_if_missed_days(self, state: OnigimonState) -> None:
        today = date.today().isoformat()
        if state.last_decay_processed_day == today:
            return

        if state.last_study_day:
            try:
                last_date = date.fromisoformat(state.last_study_day)
                days_diff = (date.today() - last_date).days
                missed_days = max(0, days_diff - 1)
                if missed_days > 0:
                    decay_amount = self.missed_day_decay_amount(missed_days)
                    for companion_id, companion_dict in state.companions.items():
                        companion_dict["happiness"] = max(0, companion_dict.get("happiness", 50) - decay_amount)
                        companion_dict["cleanliness"] = max(0, companion_dict.get("cleanliness", 60) - decay_amount)
                        companion_dict["training"] = max(0, companion_dict.get("training", 50) - decay_amount)
                        companion_dict["hunger"] = max(0, companion_dict.get("hunger", 70) - decay_amount)
                    self.save()
            except Exception as e:
                print(f"Onigimon: Error in needs decay calculation: {e}")

        state.last_decay_processed_day = today
        self.save()

    def active_companion(self) -> Optional[OnigimonCompanion]:
        self.sync_active_companion_from_ankimon()
        state = self.load()
        self.decay_needs_if_missed_days(state)
        if not state.active_companion_id:
            return None
        data = state.companions.get(state.active_companion_id)
        if not data:
            return None
        refreshed = self._refreshed_companion_data(state.active_companion_id)
        if refreshed:
            updated = {**data, **refreshed}
            if updated != data:
                data = updated
                state.companions[state.active_companion_id] = data
                self.save()
        return OnigimonCompanion(**data)

    def sync_active_companion_from_ankimon(self) -> bool:
        main = self.bridge.get_main_pokemon()
        main_id = str(main.get("ankimon_id") or "")
        if not main_id:
            return False
        state = self.load()
        existing = state.companions.get(main_id, {})
        changed = state.active_companion_id != main_id or not existing
        companion = OnigimonCompanion(**{**existing, **main, **{"ankimon_id": main_id}})
        state.companions[main_id] = asdict(companion)
        state.active_companion_id = main_id
        if changed:
            self.save()
        return changed

    def _refreshed_companion_data(self, ankimon_id: str) -> Dict[str, Any]:
        """Fetches the latest Pokémon data from Ankimon and normalises it.

        HP values are always sourced from the live runtime object so they match
        Ankimon’s HP bar exactly (current_hp may differ from the DB if the
        Pokémon took battle damage between DB saves).
        """
        result: Dict[str, Any] = {}

        db = getattr(mw, "ankimon_db", None)
        if db and hasattr(db, "get_pokemon"):
            try:
                pokemon = db.get_pokemon(str(ankimon_id))
                if pokemon:
                    result = self.bridge._normalize_pokemon(pokemon)
            except Exception:
                pass

        if not result:
            for pokemon in self.get_available_companions():
                if str(pokemon.get("ankimon_id")) == str(ankimon_id):
                    result = pokemon
                    break

        if not result:
            return {}

        # Inject authoritative HP from the live runtime so that the HP bar
        # always matches Ankimon’s display, regardless of DB save timing.
        hp_info = self.bridge._get_main_runtime_hp()
        if hp_info:
            result["hp"] = hp_info["current_hp"]
            result["max_hp"] = hp_info["max_hp"]

        return result

    def modal_sprite_url(self, companion: Dict[str, Any]) -> str:
        pokedex_id = AnkimonBridge._safe_int(companion.get("pokedex_id"), 0)
        urls = self.sprite_urls_for_companion(companion)
        return urls[0] if urls else ""

    def sprite_urls_for_companion(self, companion: Dict[str, Any]) -> List[str]:
        pokedex_id = AnkimonBridge._safe_int(companion.get("pokedex_id"), 0)
        name = str(companion.get("name") or "")
        shiny = bool(companion.get("shiny", False))
        gender = str(companion.get("gender") or "M")

        urls = []
        if self.bridge.detect():
            try:
                import importlib
                sprite_module = importlib.import_module(f"{self.bridge.addon_id}.Ankimon.functions.sprite_functions")
                if hasattr(sprite_module, "get_sprite_path"):
                    try:
                        from .. import config as oni_config
                        oni_conf = oni_config.get_config().get("onigimon", {})
                        sprite_motion = str(oni_conf.get("sprite_motion", "static"))
                    except Exception:
                        sprite_motion = "static"
                    sprite_type = "gif" if sprite_motion == "gif" else "png"
                    
                    path = sprite_module.get_sprite_path("front", sprite_type, pokedex_id, shiny, gender)
                    if path:
                        addons_folder = mw.addonManager.addonsFolder()
                        path_str = str(path).replace("\\", "/")
                        add_str = str(addons_folder).replace("\\", "/")
                        if path_str.startswith(add_str):
                            urls.append(path_str.replace(add_str, "/_addons"))
            except Exception:
                pass

        urls.extend(self.bridge.sprite_fallback_urls(pokedex_id, name, shiny))
        
        stored = str(companion.get("sprite_url") or "")
        if stored:
            urls.append(stored)
        stored_fallbacks = companion.get("sprite_fallbacks", [])
        if isinstance(stored_fallbacks, list):
            urls.extend(str(url) for url in stored_fallbacks if url)
        try:
            addon_package = mw.addonManager.addonFromModule(__name__)
        except Exception:
            addon_package = "1011095603"
        urls.append(f"/_addons/{addon_package}/system_files/system_icons/available_for_users/circle.svg")

        seen = set()
        deduped = []
        for url in urls:
            if url and url not in seen:
                seen.add(url)
                deduped.append(url)
        return deduped

    def status(self) -> str:
        if not self.is_enabled():
            return "disabled"
        return self.bridge.status()

    def widget_payload(self, refresh_bridge: bool = True) -> Dict[str, Any]:
        state = self.load()
        if refresh_bridge:
            self.bridge.clear_cache()
        companion = self.active_companion()
        self._ensure_market(state)
        payload = {
            "status": self.status(),
            "companion": asdict(companion) if companion else None,
            "inventory": state.inventory,
            "streak": state.current_streak,
            "playAllowance": self.play_allowance(state),
            "playsAvailable": self.plays_available(state),
            "dailyGiftReady": state.last_daily_gift_day != date.today().isoformat(),
            "marketGiftReady": state.last_market_gift_day != date.today().isoformat(),
            "marketItems": state.market_items,
            "marketPurchased": state.market_purchased,
            "wallet": {
                "comet_shards": int(state.comet_shards),
                "star_pieces": int(state.star_pieces),
            },
            "needs": self.status_values(companion) if companion else {},
            "lastAction": getattr(self, "last_action", None),
            "lastMessage": getattr(self, "last_message", ""),
            "lastGift": getattr(self, "last_gift", None),
        }
        self.last_action = None
        self.last_message = ""
        self.last_gift = None
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
        if not self.is_correct_answer(ease):
            self._penalize_wrong_answer(state, companion)
            self.save()
            return

        if state.last_study_day != today:
            self._advance_streak(state, today)

        state.today_review_count += 1
        self._nudge_companion(companion, ease)
        state.companions[companion.ankimon_id] = asdict(companion)

        interval = self.effective_reward_interval()
        state.reviews_since_reward += 1
        if state.today_review_count % self.comet_reward_interval() == 0:
            state.comet_shards += 1

        if state.reviews_since_reward >= interval:
            state.reviews_since_reward = 0
            item_key = self._choose_reward(ease, state.current_streak)
            amount = self._reward_amount(item_key, state.current_streak)
            item_label = ITEMS.get(item_key, {}).get("label", item_key)
            state.inventory[item_key] = state.inventory.get(item_key, 0) + amount
            earned_star_piece = random.random() < self.star_piece_chance()
            if earned_star_piece:
                state.star_pieces += 1
            self.last_action = "study_reward"
            self.last_gift = {"item_key": item_key, "amount": amount, "label": item_label}
            message = f"{self.companion_display_name(companion)} found {amount} {item_label} while you studied."
            if earned_star_piece:
                message += " Bonus: 1 Star Piece."
            self.last_message = message
            self.save()
            self.notify(
                "Onigimon reward",
                message,
                self.item_icon_url(item_key) or companion.sprite_url,
            )
            self.notify_status_warning(companion)
            return
        self.save()
        self.notify_status_warning(companion)

    def _penalize_wrong_answer(self, state: OnigimonState, companion: OnigimonCompanion) -> None:
        penalty = self.wrong_answer_penalty()
        
        streak = state.reviews_since_reward
        state.reviews_since_reward = 0

        companion.happiness = max(0, int(companion.happiness or 0) - penalty)
        companion.hunger = max(0, int(companion.hunger or 0) - penalty)
        companion.energy = max(0, int(companion.energy or 0) - penalty)
        companion.cleanliness = max(0, int(companion.cleanliness or 0) - max(1, penalty // 2))
        companion.training = max(0, int(getattr(companion, "training", 50) or 0) - max(1, penalty // 2))
        companion.last_cared_at = datetime.now().isoformat()
        state.companions[companion.ankimon_id] = asdict(companion)

        self.last_action = "study_miss"
        self.last_gift = None
        name = self.companion_display_name(companion)
        
        if streak > 0:
            self.last_message = tr(
                "onigimon_streak_broken_body",
                "{streak}-answer streak broken! Answer cards correctly in a row for {name} to find items.",
            ).format(streak=streak, name=name)
            self.notify(tr("onigimon_streak_broken_title", "Streak broken"), self.last_message, companion.sprite_url)
        else:
            self.last_message = f"{name} missed that one. Reward progress moved back and care stats dropped."

        self.notify_status_warning(companion)

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

    def status_values(self, companion: Optional[OnigimonCompanion]) -> Dict[str, int]:
        if companion is None:
            return {}

        max_hp = companion.max_hp if (getattr(companion, "max_hp", 0) or 0) > 0 else getattr(companion, "hp_stat", 0) if (getattr(companion, "hp_stat", 0) or 0) > 0 else 100
        health = int(round(((companion.hp or 0) / max_hp) * 100))

        return {
            "health": max(0, min(100, health)),
            "happiness": max(0, min(100, int(companion.happiness or 0))),
            "hygiene": max(0, min(100, int(companion.cleanliness or 0))),
            "training": max(0, min(100, int(getattr(companion, "training", 50) or 0))),
            "hunger": max(0, min(100, int(companion.hunger or 0))),
        }

    def notify_status_warning(self, companion: Optional[OnigimonCompanion]) -> None:
        values = self.status_values(companion)
        if not values or companion is None:
            return

        critical = {key: value for key, value in values.items() if value < 25}
        low = {key: value for key, value in values.items() if 25 <= value < 50}
        if not critical and not low:
            return

        labels = {
            "health": tr("onigimon_status_health"),
            "happiness": tr("onigimon_status_happiness"),
            "hygiene": tr("onigimon_status_hygiene"),
            "training": tr("onigimon_status_training"),
            "hunger": tr("onigimon_status_hunger"),
        }

        if critical:
            title = tr("onigimon_status_critical_title")
            affected_values = {**low, **critical}
            affected = ", ".join(f"{labels.get(key, key)} {value}%" for key, value in affected_values.items())
            template = tr("onigimon_status_critical_body")
        else:
            title = tr("onigimon_status_low_title")
            affected = ", ".join(f"{labels.get(key, key)} {value}%" for key, value in low.items())
            template = tr("onigimon_status_low_body")

        try:
            message = template.format(
                name=self.companion_display_name(companion),
                statuses=affected,
            )
        except Exception:
            message = f"{self.companion_display_name(companion)} needs care: {affected}."
        self.notify(title, message, companion.sprite_url)

    @staticmethod
    def _ankimon_stat_bar_percent(value: int) -> int:
        value = max(0, int(value or 0))
        return int(round((1 - exp(-value / 200.0)) * 100))

    def biggest_need(self, companion: Optional[OnigimonCompanion]) -> str:
        values = self.status_values(companion)
        if not values:
            return "Choose an Ankimon companion to begin."
        status = min(values, key=values.get)
        labels = {
            "health": "medicine",
            "happiness": "playtime",
            "hygiene": "a bath",
            "training": "training",
            "hunger": "food",
        }
        name = self.companion_display_name(companion)
        return f"{name} needs {labels.get(status, status)} the most."

    def _ensure_market(self, state: Optional[OnigimonState] = None) -> None:
        state = state or self.load()
        today = date.today().isoformat()
        if state.market_day == today and state.market_items:
            return

        cheap_pool = list(FOOD_ITEM_KEYS[:]) + ["medicine", "play_fluffy_tail", "ball_great"]
        premium_pool = ["exp_candy", "held_macho_brace", "held_power_weight", "petal_red", "battle_x_attack", "medicine"]
        rng = random.Random(f"{self._profile_name()}:{today}:onigimon-market")
        cheap = rng.sample(cheap_pool, k=min(4, len(cheap_pool)))
        premium = rng.sample(premium_pool, k=min(4, len(premium_pool)))

        items: List[Dict[str, Any]] = []
        for idx, key in enumerate(cheap):
            items.append({
                "slot": f"cheap_{idx}",
                "item_key": key,
                "amount": 1 + (1 if key in BERRY_ITEMS and rng.random() < 0.35 else 0),
                "currency": "comet_shards",
                "price": rng.choice((35, 50, 65, 80)),
            })
        for idx, key in enumerate(premium):
            items.append({
                "slot": f"premium_{idx}",
                "item_key": key,
                "amount": 1,
                "currency": "star_pieces",
                "price": rng.choice((1, 2, 3, 4)),
            })

        state.market_day = today
        state.market_items = items
        state.market_purchased = []
        self.save()

    def purchase_market_item(self, slot: str) -> Optional[str]:
        state = self.load()
        self._ensure_market(state)
        if slot in state.market_purchased:
            self.last_message = "That market item was already purchased today."
            return self.last_message

        offer = next((item for item in state.market_items if str(item.get("slot")) == str(slot)), None)
        if not offer:
            self.last_message = "That market offer is no longer available."
            return self.last_message

        currency = str(offer.get("currency") or "comet_shards")
        price = int(offer.get("price") or 0)
        if not self._spend_market_currency(state, currency, price):
            self.last_message = "You do not have enough coins for that item."
            return self.last_message

        key = str(offer.get("item_key"))
        amount = int(offer.get("amount") or 1)
        state.inventory[key] = int(state.inventory.get(key, 0) or 0) + amount
        state.market_purchased.append(str(slot))
        self.last_action = key
        self.last_message = f"Purchased {amount} {ITEMS.get(key, {}).get('label', key)}."
        self.save()
        return self.last_message

    def interact_with_status(self, status: str) -> Optional[str]:
        status_items = {
            "health": MEDICINE_ITEM_KEYS,
            "happiness": HAPPINESS_ITEM_KEYS,
            "hygiene": HYGIENE_ITEM_KEYS,
            "training": TRAINING_ITEM_KEYS,
            "hunger": FOOD_ITEM_KEYS,
        }.get(status, ())
        state = self.load()
        for item_key in status_items:
            if int(state.inventory.get(item_key, 0) or 0) > 0:
                return self.use_item(item_key)
        labels = {
            "health": "medicine",
            "happiness": "play items",
            "hygiene": "hygiene items",
            "training": "training items",
            "hunger": "food",
        }
        self.last_message = f"No {labels.get(status, 'items')} in the backpack yet."
        return self.last_message

    def _spend_market_currency(self, state: OnigimonState, currency: str, price: int) -> bool:
        price = max(0, int(price))
        if currency == "star_pieces":
            if int(state.star_pieces) >= price:
                state.star_pieces -= price
                return True
            comet_cost = price * 10
            if int(state.comet_shards) >= comet_cost:
                state.comet_shards -= comet_cost
                return True
            return False

        if int(state.comet_shards) >= price:
            state.comet_shards -= price
            return True

        total_value = int(state.comet_shards) + int(state.star_pieces) * 10
        if total_value < price:
            return False
        while state.comet_shards < price and state.star_pieces > 0:
            state.star_pieces -= 1
            state.comet_shards += 10
        state.comet_shards -= price
        return True

    def claim_market_gift(self) -> Optional[str]:
        state = self.load()
        today = date.today().isoformat()
        if state.last_market_gift_day == today:
            self.last_message = "Today's gift was already opened."
            return self.last_message
        rng = random.Random(f"{self._profile_name()}:{today}:onigimon-gift")
        pool = list(FOOD_ITEM_KEYS) + ["medicine", "petal_red", "play_fluffy_tail", "held_macho_brace"]
        key = rng.choice(pool)
        amount = 1 + (1 if key in BERRY_ITEMS and rng.random() < self.market_gift_bonus_chance() else 0)
        state.inventory[key] = int(state.inventory.get(key, 0) or 0) + amount
        if rng.random() < self.market_coin_chance():
            state.comet_shards += rng.choice((5, 10, 15, 20))
        elif rng.random() < self.star_piece_chance():
            state.star_pieces += 1
        state.last_market_gift_day = today
        self.last_action = key
        self.last_gift = {"item_key": key, "amount": amount, "label": ITEMS.get(key, {}).get("label", key)}
        self.last_message = f"The daily gift revealed {amount} {ITEMS.get(key, {}).get('label', key)}."
        self.save()
        return self.last_message

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
            "play_fluffy_tail",
        ]
        if ease >= 3:
            pool.extend(["poke_candies", "medicine"])
        if streak >= 7:
            pool.extend(["exp_candy", "pokeballs", "held_macho_brace", self._choose_berry_reward()])
        if streak >= 14:
            pool.extend(["exp_candy", "pokeballs", "held_power_weight", "battle_x_attack"])
        return random.choice(pool)

    def _choose_berry_reward(self) -> str:
        return random.choice(BERRY_KEYS)

    def _reward_amount(self, item_key: str, streak: int) -> int:
        if item_key in {"exp_candy", "pokeballs"}:
            return 1
        return 1 + (1 if streak >= 7 and random.random() < self.bonus_amount_chance() else 0)

    def claim_daily_gift(self) -> Optional[str]:
        if self.status() != "ready":
            return None
        companion = self.active_companion()
        if companion is None:
            return None
        state = self.load()
        today = date.today().isoformat()
        if state.last_daily_gift_day == today:
            return None
        item_key = self._choose_daily_reward(state.current_streak)
        amount = self._reward_amount(item_key, state.current_streak)
        if random.random() < self.market_gift_bonus_chance():
            amount += 1
        state.inventory[item_key] = state.inventory.get(item_key, 0) + amount
        state.last_daily_gift_day = today
        self.last_action = "gift"
        self.save()
        message = f"{self.companion_display_name(companion)}'s daily surprise: {amount} {ITEMS[item_key]['label']}."
        self.last_message = message
        self.last_gift = {"item_key": item_key, "amount": amount, "label": ITEMS[item_key]["label"]}
        self.notify("Daily Onigimon surprise", message, companion.sprite_url)
        return message

    def _choose_daily_reward(self, streak: int) -> str:
        pool = [self._choose_berry_reward(), "poke_candies", "curry_ingredients", "medicine", "play_fluffy_tail"]
        if streak >= 7:
            pool.extend(["exp_candy", "mints", "pokeballs", "held_macho_brace", self._choose_berry_reward()])
        if streak >= 30:
            pool.extend(["pokeballs", "exp_candy", "held_power_weight", "battle_x_attack"])
        return random.choice(pool)

    def _update_stats(self, companion: OnigimonCompanion, updates: Dict[str, int]) -> None:
        stat_aliases = {
            "attack": "attack", "atk": "attack",
            "defense": "defense", "def": "defense",
            "speed": "speed", "spe": "speed",
            "hp": "hp", "xp": "xp"
        }
        for stat, val in updates.items():
            key = stat_aliases.get(str(stat).lower(), str(stat).lower())
            if key == "hp":
                # Use the authoritative runtime HP so we apply the delta against
                # the real current HP and cap against the real max HP.
                hp_info = self.bridge._get_main_runtime_hp()
                if hp_info:
                    real_current = hp_info["current_hp"]
                    real_max = hp_info["max_hp"]
                else:
                    real_current = companion.hp or 0
                    real_max = companion.max_hp or companion.hp_stat or 100
                companion.hp = max(0, min(real_max, real_current + val))
                companion.max_hp = real_max  # keep companion in sync with reality
            elif key == "attack":
                companion.attack = (companion.attack or 0) + val
            elif key == "defense":
                companion.defense = (companion.defense or 0) + val
            elif key == "speed":
                companion.speed = (companion.speed or 0) + val
            elif key == "xp":
                companion.xp = (companion.xp or 0) + val
        self.bridge.update_ankimon_stat(companion.ankimon_id, updates)

    def use_item(self, item_key: str) -> Optional[str]:
        if item_key == "play_action":
            return self.play()
        if item_key == "train_action":
            return self.train()
        if item_key == "daily_gift_action":
            return self.claim_daily_gift()
            
        companion = self.active_companion()
        if companion is None or item_key not in ITEMS:
            return None
        state = self.load()
        if state.inventory.get(item_key, 0) <= 0:
            self.last_message = "That item is not in your backpack yet."
            return self.last_message
        if (item_key in BERRY_ITEMS or item_key == "curry_ingredients") and companion.hunger >= 100:
            self.last_message = f"{self.companion_display_name(companion)} is already full."
            return self.last_message
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
            
            heal_amount = int(item.get("hp", 0)) + type_bonus
            stat_updates = {"defense": 1, "exp": 3 + type_bonus}
            if heal_amount > 0:
                stat_updates["hp"] = heal_amount
            self._update_stats(companion, stat_updates)

            message = f"{name} enjoyed a {item['label']} and gained Defense."
            if type_bonus:
                message = f"{message} It suited {self._type_label(companion.types)} well."
        elif item_key == "curry_ingredients":
            companion.hunger = min(100, companion.hunger + 35)
            companion.happiness = min(100, companion.happiness + 8)
            self._update_stats(companion, {"defense": 1, "exp": 15})
            message = f"{name} loved the curry and gained Defense."
        elif item_key == "poke_candies":
            companion.hunger = min(100, companion.hunger + 10)
            companion.happiness = min(100, companion.happiness + 15)
            companion.bond_xp += 8
            self._update_stats(companion, {"defense": 1, "exp": 5})
            message = f"{name} looks happier and gained Defense."
        elif item_key == "mints":
            self._update_stats(companion, {"hp": 10, "exp": 8})
            companion.cleanliness = min(100, companion.cleanliness + 30)
            message = f"{name} smells fresh, feels clean, and gained XP."
        elif item_key == "mint_attack_food":
            companion.hunger = min(100, companion.hunger + 18)
            companion.happiness = min(100, companion.happiness + 6)
            self._update_stats(companion, {"defense": 1, "exp": 8})
            message = f"{name} munched on an Attack Mint and gained Defense."
        elif item_key in {"medicine", "petal_red"}:
            item = ITEMS[item_key]
            heal_amount = int(item.get("hp", 0) or 0)
            companion.happiness = min(100, companion.happiness + int(item.get("happiness", 0) or 0))
            companion.cleanliness = min(100, companion.cleanliness + int(item.get("cleanliness", 0) or 0))
            if heal_amount > 0:
                self._update_stats(companion, {"hp": heal_amount})
            message = f"{name} recovered with {item['label']}."
        elif item_key in {"held_macho_brace", "held_power_weight"}:
            item = ITEMS[item_key]
            companion.energy = max(0, companion.energy - 8)
            companion.training = min(100, int(getattr(companion, "training", 50) or 0) + 18)
            companion.hunger = max(0, companion.hunger - 6)
            companion.bond_xp += int(item.get("bond_xp", 0) or 0)
            updates = {}
            for stat in ("attack", "defense", "speed"):
                if int(item.get(stat, 0) or 0):
                    updates[stat] = int(item.get(stat, 0) or 0)
            if updates:
                self._update_stats(companion, updates)
            message = f"{name} trained with {item['label']}."
        elif item_key in {"play_fluffy_tail", "battle_x_attack", "ball_great", "pokeballs"}:
            item = ITEMS[item_key]
            companion.happiness = min(100, companion.happiness + int(item.get("happiness", 12) or 12))
            companion.energy = max(0, companion.energy - 5)
            companion.bond_xp += 6
            updates = {}
            for stat in ("attack", "defense"):
                if int(item.get(stat, 0) or 0):
                    updates[stat] = int(item.get(stat, 0) or 0)
            if updates:
                self._update_stats(companion, updates)
            message = f"{name} played with {item['label']}."
        elif item_key == "exp_candy":
            companion.hunger = min(100, companion.hunger + 8)
            companion.training = min(100, int(getattr(companion, "training", 50) or 0) + 10)
            companion.bond_xp += 20
            self._update_stats(companion, {"exp": 50})
            message = f"{name} gained Onigimon bond XP and Ankimon XP."
        else:
            message = f"{name} is saving that for later."

        self.last_action = item_key
        companion.last_cared_at = datetime.now().isoformat()
        state.companions[companion.ankimon_id] = asdict(companion)
        self.save()
        self.last_message = message
        self.notify("Onigimon care", message, companion.sprite_url)
        self.notify_status_warning(companion)
        return message

    def category_status_message(self, category_id: str) -> Optional[str]:
        companion = self.active_companion()
        if companion is None:
            return None
        if category_id == "food":
            if companion.hunger >= 100:
                return f"{self.companion_display_name(companion)} is already full."
            return "Choose a food item below to feed your Onigimon."
        return None

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
            self.last_message = "Answer 10 cards correctly to earn a play."
            return self.last_message
        if companion.energy <= 0:
            self.last_message = f"{self.companion_display_name(companion)} needs a little rest."
            return self.last_message
        state.plays_used_today += 1
        companion.energy = max(0, companion.energy - 10)
        companion.happiness = min(100, companion.happiness + 10)
        companion.bond_xp += 5
        self._update_stats(companion, {"defense": 1})
        companion.last_cared_at = datetime.now().isoformat()
        state.companions[companion.ankimon_id] = asdict(companion)
        self.last_action = "play"
        self.save()
        message = f"{self.companion_display_name(companion)} played with you and gained Defense."
        self.last_message = message
        self.notify("Onigimon playtime", message, companion.sprite_url)
        self.notify_status_warning(companion)
        return message

    def train(self) -> Optional[str]:
        companion = self.active_companion()
        if companion is None:
            return None
        state = self.load()
        if self.plays_available(state) <= 0:
            self.last_message = "Answer 10 cards correctly to earn a play/training session."
            return self.last_message
        if companion.energy <= 0:
            self.last_message = f"{self.companion_display_name(companion)} is too tired to train."
            return self.last_message
        state.plays_used_today += 1
        companion.energy = max(0, companion.energy - 15)
        companion.hunger = max(0, companion.hunger - 10)
        companion.training = min(100, int(getattr(companion, "training", 50) or 0) + 15)
        companion.bond_xp += 8
        self._update_stats(companion, {"attack": 1})
        companion.last_cared_at = datetime.now().isoformat()
        state.companions[companion.ankimon_id] = asdict(companion)
        self.last_action = "train"
        self.save()
        message = f"{self.companion_display_name(companion)} trained hard and gained Attack."
        self.last_message = message
        self.notify("Onigimon training", message, companion.sprite_url)
        self.notify_status_warning(companion)
        return message

    def notify(self, title: str, description: str, icon_image: str = "") -> None:
        if title not in ("Onigimon reward", "Daily Onigimon surprise", tr("onigimon_streak_broken_title", "Streak broken")):
            return
        try:
            context = None
            if getattr(mw, "state", "") == "review":
                context = getattr(mw, "reviewer", None)
            show_onigiri_notification(
                description,
                title=title,
                context=context,
                variant="onigimon",
                icon="On",
                icon_image=icon_image,
                duration=5200,
                gamification=True,
            )
        except Exception as exc:
            print(f"Onigimon: Could not show notification: {exc}")

    def _candidate_webviews(self):
        seen = []
        for owner in (getattr(mw, "overview", None), getattr(mw, "deckBrowser", None)):
            web = owner and getattr(owner, "web", None)
            if web and web not in seen:
                seen.append(web)
                yield web


def render_widget_html(row_span: int = 2, col_span: int = 1) -> str:
    payload = manager.widget_payload()
    status = payload["status"]
    inventory = payload["inventory"]
    companion = payload["companion"]
    try:
        addon_package = mw.addonManager.addonFromModule(__name__)
    except Exception:
        addon_package = "1011095603"
    pokeball_icon = f"/_addons/{addon_package}/system_files/system_icons/available_for_users/circle.svg"

    if companion and row_span <= 1:
        name = escape(manager.companion_display_name(companion))
        sprite_urls = manager.sprite_urls_for_companion(companion)
        img = _sprite_img_html(sprite_urls, name, fallback_class="onigimon-placeholder")
        return f"""
        <div class="onigimon-widget onigimon-widget-compact" role="button" tabindex="0" onclick="pycmd('openOnigimonCare')" onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();pycmd('openOnigimonCare');}}">
            <div class="onigimon-main onigimon-scene onigimon-scene-compact" {_onigimon_scene_style_attr()}>
                {_onigimon_scene_background_layer("onigimon-scene-bg")}
                <div class="onigimon-sprite">{img}</div>
            </div>
        </div>
        """

    if status == "disabled":
        body = f"<p>{escape(tr('onigimon_enable_settings'))}</p>"
    elif status == "missing":
        body = f"<p>{escape(tr('onigimon_install_ankimon'))}</p>"
    elif status == "starter_needed":
        body = f"<p>{escape(tr('onigimon_choose_starter'))}</p>"
    elif status == "no_collection":
        body = f"<p>{escape(tr('onigimon_collection_needed'))}</p>"
    elif not companion:
        body = f"<p>{escape(tr('onigimon_choose_companion_settings'))}</p>"
    else:
        name = escape(manager.companion_display_name(companion))
        sprite_urls = manager.sprite_urls_for_companion(companion)
        img = _sprite_img_html(sprite_urls, name, fallback_class="onigimon-placeholder")
        health_value = manager.status_values(OnigimonCompanion(**companion)).get("health", 0)
        status_values = manager.status_values(OnigimonCompanion(**companion))
        current_hp = int(companion.get("hp") or 0)
        max_hp = int(companion.get("max_hp") or 0)
        hp_stat = int(companion.get("hp_stat") or 0)
        hp_bits = []
        if hp_stat:
            hp_bits.append(f"HP {hp_stat}")
        if max_hp:
            hp_bits.append(f"{tr('onigimon_current_hp')} {current_hp}/{max_hp}")
        elif current_hp:
            hp_bits.append(f"{tr('onigimon_current_hp')} {current_hp}")
        hp_line = " · ".join(hp_bits)
        hp_line_html = f"<span>{escape(hp_line)}</span>" if hp_line else ""

        body = f"""
            <div class="onigimon-main onigimon-scene" {_onigimon_scene_style_attr()}>
                {_onigimon_scene_background_layer("onigimon-scene-bg")}
                <div class="onigimon-sprite">{img}</div>
                <div class="onigimon-info">
                    <strong>{name}</strong>
                    <span>{escape(tr("onigimon_level"))} {int(companion.get("level") or 1)}</span>
                </div>
            </div>
            {_meter("HP", health_value, "#08c46b", str(current_hp))}
            {_meter(tr("onigimon_status_happiness"), int(status_values.get("happiness", 0)), "#ffbd55", str(int(companion.get("happiness", 0) or 0)))}
            {_meter(tr("onigimon_status_hygiene"), int(status_values.get("hygiene", 0)), "#21b7d6", str(int(companion.get("cleanliness", 0) or 0)))}
            {_meter(tr("onigimon_status_training"), int(status_values.get("training", 0)), "#c866e5", str(int(companion.get("training", 0) or 0)))}
            {_meter(tr("onigimon_status_hunger"), int(status_values.get("hunger", 0)), "#f45bb3", str(int(companion.get("hunger", 0) or 0)))}
        """

    return f"""
    <div class="onigimon-widget" role="button" tabindex="0" onclick="pycmd('openOnigimonCare')" onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();pycmd('openOnigimonCare');}}">
        <div class="onigimon-header">
            <h3>Onigimon</h3>
        </div>
        <div class="onigimon-body">{body}</div>
    </div>
    """


def _meter(label: str, value: int, color: str, detail: str = "") -> str:
    value = max(0, min(100, value))
    detail_html = f"<b>{escape(str(detail))}</b>" if str(detail).strip() else "<b></b>"
    return f"""
    <div class="onigimon-meter">
        <span>{escape(label)}</span>
        {detail_html}
        <div><i style="width:{value}%; background:{color};"></i></div>
    </div>
    """


def _sprite_img_html(urls: List[str], label: str, fallback_class: str = "") -> str:
    cleaned: List[str] = []
    for url in urls:
        text = str(url or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    if not cleaned:
        return ""
    class_attr = f' class="{escape(fallback_class)}"' if fallback_class else ""
    fallback_json = escape(json.dumps(cleaned[1:]), quote=True)
    onerror = (
        "var f=JSON.parse(this.dataset.fallbacks||'[]');"
        "if(f.length){this.dataset.fallbacks=JSON.stringify(f.slice(1));this.src=f[0];}"
        "else{this.onerror=null;this.style.display='none';}"
    )
    return (
        f'<img{class_attr} src="{escape(cleaned[0], quote=True)}" '
        f'data-fallbacks="{fallback_json}" onerror="{escape(onerror, quote=True)}" '
        f'alt="{escape(label, quote=True)}">'
    )


def _item_icon(item_key: str) -> str:
    item = ITEMS.get(item_key, {})
    url = _item_asset_url(item)
    label = escape(_onigimon_item_label(item_key))
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


def _normalize_scene_color(value: Any) -> str:
    text = str(value or "").strip()
    if re.match(r"^#[0-9a-fA-F]{6}$", text):
        return text
    return "#7FD179"


def _onigimon_scene_image_url() -> str:
    image_path = str(manager.config().get("scene_background_image", "") or "").strip()
    if not image_path:
        return ""
    if image_path.startswith("/_addons/") or image_path.startswith("http://") or image_path.startswith("https://"):
        return image_path
    if os.path.isabs(image_path):
        addon_path = os.path.dirname(os.path.dirname(__file__))
        try:
            rel_path = os.path.relpath(image_path, addon_path)
        except Exception:
            return ""
    else:
        rel_path = image_path
    return _addon_asset_url(rel_path)


def _onigimon_scene_style_attr() -> str:
    color = _normalize_scene_color(manager.config().get("scene_background_color", "#7FD179"))
    image_url = _onigimon_scene_image_url()
    try:
        blur = max(0, min(40, int(manager.config().get("scene_background_blur", 9) or 0)))
    except Exception:
        blur = 9
    try:
        opacity = max(0, min(100, int(manager.config().get("scene_background_opacity", 90) or 0))) / 100.0
    except Exception:
        opacity = 0.9
    parts = [
        f"background-color: {color}",
        "--onigimon-scene-image: none",
        f"--onigimon-scene-blur: {blur}px",
        f"--onigimon-scene-opacity: {opacity:.2f}",
    ]
    if image_url:
        parts.extend([
            f"--onigimon-scene-image: url('{escape(image_url)}')",
        ])
    return f'style="{"; ".join(parts)};"'


def _onigimon_scene_background_style_attr() -> str:
    color = _normalize_scene_color(manager.config().get("scene_background_color", "#7FD179"))
    image_url = _onigimon_scene_image_url()
    try:
        blur = max(0, min(40, int(manager.config().get("scene_background_blur", 9) or 0)))
    except Exception:
        blur = 9
    try:
        opacity = max(0, min(100, int(manager.config().get("scene_background_opacity", 90) or 0))) / 100.0
    except Exception:
        opacity = 0.9
    parts = [
        "background-color: transparent",
        "background-image: none",
        "background-size: cover",
        "background-position: center",
        "background-repeat: no-repeat",
        f"filter: blur({blur}px)",
        f"opacity: {opacity:.2f}",
    ]
    if image_url:
        parts[1] = f"background-image: url('{escape(image_url)}')"
    return f'style="{"; ".join(parts)};"'


def _onigimon_scene_background_layer(class_name: str) -> str:
    return f'<div class="{escape(class_name)}" {_onigimon_scene_background_style_attr()}></div>'


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
    close_icon = _addon_asset_url("system_files/system_icons/unavailable_for_users/cancel.svg")
    sprite_urls = manager.sprite_urls_for_companion(companion)
    
    hp = companion.get("hp", 0)
    max_hp = companion.get("max_hp", 0)
    sick_indicator = ""
    if max_hp and hp < max_hp * 0.3:
        sick_indicator = f'<div style="position:absolute; top: 10px; right: 10px; background: rgba(220, 53, 69, 0.9); color: white; padding: 4px 8px; border-radius: 6px; font-weight: bold; font-size: 13px; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">🤒 {escape(tr("onigimon_sick_low_hp"))}</div>'
    
    sprite_img = _sprite_img_html(sprite_urls, name)
    categories = (
        ("food", tr("onigimon_category_food"), "berry_cheri", BERRY_KEYS + ("curry_ingredients",), "feed"),
        ("treats", tr("onigimon_category_treats"), "poke_candies", ("poke_candies", "exp_candy"), "feed"),
        ("activities", tr("onigimon_category_activities"), "play_action", ("play_action", "train_action"), "feed"),
        ("care", tr("onigimon_category_clean"), "mints", ("mints",), "feed"),
        ("pokeballs", tr("onigimon_category_gift"), "daily_gift_action", ("daily_gift_action", "pokeballs"), "feed"),
    )
    category_bits = "".join(
        _category_button_html(category_id, label, icon_key, keys, inventory)
        for category_id, label, icon_key, keys, _action in categories
    )
    category_panel_bits = "".join(
        _category_panel_html(category_id, keys, action, inventory, companion)
        for category_id, _label, _icon_key, keys, action in categories
    )

    return f"""
    <div id="onigimon-care-modal" class="onigimon-care-modal {modal_class}" onclick="event.stopPropagation(); this.classList.remove('is-open'); this.classList.remove('has-reaction');">
        <div class="onigimon-care-dialog" onclick="event.stopPropagation();">
            <button class="onigimon-modal-close" onclick="var modal=document.getElementById('onigimon-care-modal'); modal.classList.remove('is-open'); modal.classList.remove('has-reaction');">
                <i class="onigimon-close-icon" aria-label="{escape(tr('close'))}" style="mask-image: url('{escape(close_icon)}'); -webkit-mask-image: url('{escape(close_icon)}');"></i>
            </button>
            <h3>{name}</h3>

            <div class="onigimon-care-display" {_onigimon_scene_style_attr()}>
                {_onigimon_scene_background_layer("onigimon-care-bg")}
                {sick_indicator}
                <div class="onigimon-care-item-flow">
                    {flow_item_html}
                </div>
                <div class="onigimon-care-sprite">
                    {sprite_img}
                </div>
            </div>

            <div class="onigimon-modal-inventory">
                <div class="onigimon-modal-inventory-title">{escape(tr("onigimon_items"))}</div>
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
                        feed.querySelector('small').textContent = action === 'feed' ? label : {json.dumps(tr("onigimon_select_food"))};
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
                        gift.querySelector('small').textContent = action === 'gift' ? label : {json.dumps(tr("onigimon_select_gift"))};
                        gift.onclick = function(event) {{
                            event.stopPropagation();
                            if (action === 'gift') {{
                                onigimonTriggerReaction(key);
                                pycmd('onigimon_feed:' + key);
                            }}
                        }};
                    }}
                    if (action === 'feed') {{
                        onigimonTriggerReaction(key);
                        pycmd('onigimon_feed:' + key);
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
    is_action = category_id in ("activities", "pokeballs")
    count = sum(int(inventory.get(key, 0)) for key in keys if key not in ("play_action", "train_action", "daily_gift_action"))
    disabled = "disabled" if count <= 0 and not is_action else ""
    count_html = f"<b>{count}</b>" if not is_action else ""
    status_cmd = f" pycmd('onigimon_category:{escape(category_id)}');" if category_id == "food" else ""
    return f"""
    <button class="onigimon-category-chip" data-category="{escape(category_id)}" {_item_color_style(category_id)} {disabled} onclick="event.stopPropagation(); onigimonShowCategory('{escape(category_id)}');{status_cmd}">
        {_item_icon(icon_key)}
        <span>{escape(label)}</span>
        {count_html}
    </button>
    """


def _category_panel_html(category_id: str, keys: tuple, action: str, inventory: Dict[str, int], companion: Dict[str, Any]) -> str:
    available = [key for key in keys if int(inventory.get(key, 0)) > 0 or key in ("play_action", "train_action", "daily_gift_action")]
    if not available:
        item_bits = f'<div class="onigimon-empty-category">{escape(tr("onigimon_empty_generic"))}</div>'
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
    label = _onigimon_item_label(item_key)
    hint = _inventory_item_hint(item_key, companion)
    if action == "none":
        return f"""
        <div class="onigimon-inventory-choice is-passive" {_item_color_style(item_key)}>
            {_item_icon(item_key)}
            <span>{escape(label)}</span>
            <small>{escape(hint)} · {count}</small>
        </div>
        """
    if action == "feed":
        onclick = (
            "event.stopPropagation(); "
            f"onigimonTriggerReaction({json.dumps(item_key)}); "
            f"pycmd('onigimon_feed:' + {json.dumps(item_key)});"
        )
    else:
        onclick = (
            "event.stopPropagation(); "
            f"onigimonSelectCareItem({json.dumps(item_key)}, {json.dumps(action)}, {json.dumps(label)});"
        )
    return f"""
    <button class="onigimon-inventory-choice" data-item="{escape(item_key)}" {_item_color_style(item_key)} onclick="{escape(onclick)}">
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
        prefix = tr("onigimon_hint_best_for").format(types="/".join(favored[:3])) if favored else tr("onigimon_hint_berry")
        suffix = tr("onigimon_hint_type_bonus") if match else _onigimon_item_effect(item_key)
        return f"{prefix}; {suffix}"
    if item.get("effect"):
        return _onigimon_item_effect(item_key)
    return _onigimon_item_label(item_key)


manager = OnigimonManager()


def register_hooks() -> None:
    gui_hooks.reviewer_did_answer_card.append(manager.on_answer)


register_hooks()
