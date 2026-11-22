"""Onigimon Reviewer HUD — minimal, battle, and war modes with Onigiri-aligned notifications & items."""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

try:
    from aqt import gui_hooks, mw
except Exception:  # pragma: no cover
    gui_hooks = None
    mw = None

from ..core import config
from ..core.translations import tr
from ..ui_kit.onigiri_notifications import notify as show_onigiri_notification


ANKIMON_ADDON_IDS = ("1908235722", "Ankimon")
_ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_HP_DELTA_RE = re.compile(r"^\s*([+-]\s*\d+)\s*HP\s*$", re.IGNORECASE)

VALID_HUD_MODES = ("minimal", "battle", "war")
VALID_HUD_MOTIONS = ("animated", "static")
_EXCLUDED_INVENTORY_KEYS = frozenset(
    {"berries", "play_action", "train_action", "daily_gift_action"}
)
_PASSIVE_INVENTORY_KEYS = frozenset({"pokeballs"})

_BOOST_MULTS = {
    1: "×1.5",
    2: "×2",
    3: "×2.5",
    4: "×3",
    5: "×3.5",
    6: "×4",
    -1: "×0.67",
    -2: "×0.5",
    -3: "×0.4",
    -4: "×0.33",
    -5: "×0.29",
    -6: "×0.25",
}

_BOOST_KEYS = (
    ("attack_boost", "ATK"),
    ("defense_boost", "DEF"),
    ("special_attack_boost", "SpA"),
    ("special_defense_boost", "SpD"),
    ("speed_boost", "SPE"),
    ("accuracy_boost", "ACC"),
    ("evasion_boost", "EVD"),
)

_cached_css_mtime: Optional[int] = None
_cached_css_text: str = ""
_hooks_registered: bool = False


def _onigiri_addon_package() -> str:
    try:
        if mw and hasattr(mw, "addonManager"):
            pkg = mw.addonManager.addonFromModule(__name__)
            if pkg:
                return str(pkg)
    except Exception:
        pass
    return os.path.basename(_ADDON_ROOT) or "1011095603"


def _normalize_hex(value: Any, fallback: str) -> str:
    raw = str(value or "").strip()
    if not _HEX_COLOR_RE.match(raw):
        return fallback
    if len(raw) == 4:
        return "#" + "".join(ch * 2 for ch in raw[1:]).lower()
    return raw.lower()


def _clamp_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        num = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, num))


def _normalize_position(raw: Any) -> Optional[Dict[str, float]]:
    if not isinstance(raw, dict):
        return None
    try:
        x = float(raw.get("x"))
        y = float(raw.get("y"))
    except (TypeError, ValueError):
        return None
    if not (0.0 <= x <= 100.0 and 0.0 <= y <= 100.0):
        x = max(0.0, min(100.0, x))
        y = max(0.0, min(100.0, y))
    return {"x": round(x, 2), "y": round(y, 2)}


def get_hud_style_settings(conf: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return normalized Onigimon Reviewer HUD customization settings."""
    if conf is None:
        try:
            conf = config.get_config_readonly()
        except Exception:
            conf = {}
    og = conf.get("onigimon", {}) if isinstance(conf, dict) else {}
    if not isinstance(og, dict):
        og = {}

    mode = str(og.get("reviewer_hud_mode", "battle") or "battle").strip().lower()
    if mode not in VALID_HUD_MODES:
        mode = "battle"

    motion = str(og.get("reviewer_hud_motion", "animated") or "animated").strip().lower()
    if motion not in VALID_HUD_MOTIONS:
        motion = "animated"

    return {
        "mode": mode,
        "motion": motion,
        "scale": _clamp_int(og.get("reviewer_hud_scale", 100), 75, 135, 100),
        "opacity": _clamp_int(og.get("reviewer_hud_opacity", 88), 0, 100, 88),
        "bg_color_light": _normalize_hex(og.get("reviewer_hud_bg_color_light", "#ffffff"), "#ffffff"),
        "bg_color_dark": _normalize_hex(og.get("reviewer_hud_bg_color_dark", "#202124"), "#202124"),
        "shadow": bool(og.get("reviewer_hud_shadow", True)),
        "position": _normalize_position(og.get("reviewer_hud_position")),
    }


def is_hud_enabled(conf: Optional[Dict[str, Any]] = None) -> bool:
    """Return True when Onigimon and its Reviewer HUD replacement are both enabled."""
    if conf is None:
        try:
            conf = config.get_config_readonly()
        except Exception:
            return False
    onigimon_conf = conf.get("onigimon", {}) if isinstance(conf, dict) else {}
    if not isinstance(onigimon_conf, dict):
        return False
    if not bool(onigimon_conf.get("enabled", False)):
        return False
    return bool(onigimon_conf.get("reviewer_hud_enabled", True))


def should_inject_reviewer_assets(conf: Optional[Dict[str, Any]] = None) -> bool:
    """Inject lightweight HUD assets when Onigimon is enabled or Ankimon is loaded so Settings toggles apply live."""
    if conf is None:
        try:
            conf = config.get_config_readonly()
        except Exception:
            conf = {}
    onigimon_conf = conf.get("onigimon", {}) if isinstance(conf, dict) else {}
    if isinstance(onigimon_conf, dict) and bool(onigimon_conf.get("enabled", False)):
        return True
    return _find_ankimon_package() is not None


def _read_hud_css_text() -> str:
    global _cached_css_mtime, _cached_css_text
    css_path = os.path.join(_ADDON_ROOT, "web", "onigimon_hud.css")
    try:
        mtime = os.stat(css_path).st_mtime_ns
        if _cached_css_mtime != mtime:
            with open(css_path, "r", encoding="utf-8") as handle:
                _cached_css_text = handle.read()
            _cached_css_mtime = mtime
    except OSError:
        return ""
    return _cached_css_text


def _hud_labels() -> Dict[str, str]:
    return {
        "catchLabel": tr("onigimon_hud_catch", "Catch"),
        "defeatLabel": tr("onigimon_hud_defeat", "Defeat"),
        "cycleTeam": tr("onigimon_hud_cycle_team", "Switch companion"),
        "hideHud": tr("onigimon_hud_hide", "Minimize HUD"),
        "showHud": tr("onigimon_hud_show", "Onigimon"),
        "fainted": tr("onigimon_hud_fainted", "Fainted"),
        "itemsTitle": tr("onigimon_hud_items", "Items"),
        "itemsEmpty": tr("onigimon_hud_items_empty", "No items in your bag yet."),
        "dragHint": tr("onigimon_hud_drag_hint", "Drag to move · Double-click to reset"),
        "roundLabel": tr("onigimon_hud_round", "Round"),
    }


def reviewer_head_assets(addon_package: str, conf: Optional[Dict[str, Any]] = None) -> str:
    """Return HTML head tags for the Onigimon Reviewer HUD."""
    if not should_inject_reviewer_assets(conf):
        return ""
    enabled = is_hud_enabled(conf)
    css_text = _read_hud_css_text()
    labels_json = json.dumps(_hud_labels(), ensure_ascii=False)
    js_path = os.path.join(_ADDON_ROOT, "web", "onigimon_hud.js")
    try:
        version = int(os.path.getmtime(js_path))
    except OSError:
        version = 1
    script_url = f"/_addons/{addon_package}/web/onigimon_hud.js?v={version}"
    return (
        "<script>"
        f"window.onigimonHudEnabled = {'true' if enabled else 'false'};"
        f"window.onigimonHudCssText = {json.dumps(css_text, ensure_ascii=False)};"
        f"window.onigimonHudLabels = {labels_json};"
        "</script>"
        f'<script src="{script_url}"></script>'
    )


def _find_ankimon_package() -> Optional[str]:
    for pkg in ANKIMON_ADDON_IDS:
        if f"{pkg}.services" in sys.modules or f"{pkg}.pyobj.reviewer_obj" in sys.modules:
            return pkg
    return None


def _get_ankimon_module(pkg: str, suffix: str) -> Any:
    return sys.modules.get(f"{pkg}.{suffix}")


def _anki_night_mode() -> bool:
    try:
        from aqt.theme import theme_manager

        return bool(theme_manager.night_mode)
    except Exception:
        return False


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_hp_pair(hp: Any, max_hp: Any) -> Tuple[int, int]:
    safe_max = max(1, _safe_int(max_hp, 1))
    safe_hp = min(max(0, _safe_int(hp, 0)), safe_max)
    return safe_hp, safe_max


def _extract_boosts(pokemon: Any) -> List[Dict[str, Any]]:
    boosts: List[Dict[str, Any]] = []
    if pokemon is None:
        return boosts
    try:
        engine_dict = pokemon.to_engine_format() if hasattr(pokemon, "to_engine_format") else {}
    except Exception:
        engine_dict = {}
    if not isinstance(engine_dict, dict):
        return boosts
    for key, abbr in _BOOST_KEYS:
        stage = _safe_int(engine_dict.get(key, 0), 0)
        if stage != 0 and stage in _BOOST_MULTS:
            boosts.append({"stat": abbr, "stage": stage, "label": f"{abbr} {_BOOST_MULTS[stage]}"})
    return boosts


def _extract_types(pokemon: Any) -> List[str]:
    if pokemon is None:
        return []
    raw = getattr(pokemon, "type", None)
    if isinstance(raw, str):
        return [part.strip().lower() for part in raw.split(",") if part.strip()]
    if isinstance(raw, (list, tuple)):
        return [str(part).strip().lower() for part in raw if str(part).strip()]
    return []


def _extract_combat_stats(pokemon: Any) -> Dict[str, int]:
    if pokemon is None:
        return {}
    stats: Dict[str, int] = {}
    try:
        engine_dict = pokemon.to_engine_format() if hasattr(pokemon, "to_engine_format") else {}
    except Exception:
        engine_dict = {}
    stat_map = (
        ("attack", "atk"),
        ("defense", "def"),
        ("special_attack", "spa"),
        ("special_defense", "spd"),
        ("speed", "spe"),
    )
    if isinstance(engine_dict, dict):
        for eng_key, out_key in stat_map:
            if eng_key in engine_dict and engine_dict[eng_key] is not None:
                stats[out_key] = _safe_int(engine_dict[eng_key], 0)
    if not stats:
        base = getattr(pokemon, "base_stats", None)
        if isinstance(base, dict):
            for out_key in ("atk", "def", "spa", "spd", "spe"):
                if out_key in base:
                    stats[out_key] = _safe_int(base[out_key], 0)
    return stats


def _resolve_sprite_url(
    pokemon: Any,
    side: str,
    image_format: str,
    addon_package: str,
    *,
    allow_png_fallback: bool = True,
) -> str:
    if pokemon is None:
        return ""
    formats = [image_format]
    if allow_png_fallback and image_format == "gif":
        formats.append("png")

    for fmt in formats:
        try:
            abs_path = pokemon.get_sprite_path(side, fmt)
            norm = str(abs_path).replace("\\", "/")
            # When checking for animated GIFs on disk, skip missing files and fall back to PNG.
            if fmt == "gif" and os.path.isabs(str(abs_path)) and not os.path.exists(str(abs_path)):
                if allow_png_fallback:
                    continue
            marker = "user_files/sprites/"
            idx = norm.find(marker)
            if idx != -1:
                return f"/_addons/{addon_package}/{norm[idx:]}"
        except Exception:
            continue
    return ""


def _setting(settings_obj: Any, key: str, default: Any = None) -> Any:
    if settings_obj is None:
        return default
    try:
        val = settings_obj.get(key, default)
        return default if val is None else val
    except TypeError:
        try:
            val = settings_obj.get(key)
            return default if val is None else val
        except Exception:
            return default
    except Exception:
        return default


def _compute_xp_next(pkg: Optional[str], main_pokemon: Any, settings_obj: Any) -> int:
    if main_pokemon is None:
        return 100
    try:
        if pkg:
            pf = _get_ankimon_module(pkg, "functions.pokemon_functions")
            if pf and hasattr(pf, "find_experience_for_level"):
                return max(
                    1,
                    _safe_int(
                        pf.find_experience_for_level(
                            getattr(main_pokemon, "growth_rate", "medium-fast"),
                            getattr(main_pokemon, "level", 1),
                            _setting(settings_obj, "misc.remove_level_cap", False),
                        ),
                        100,
                    ),
                )
    except Exception:
        pass
    return max(1, _safe_int(getattr(main_pokemon, "xp", 0), 0) or 100)


def build_inventory_snapshot(addon_package: Optional[str] = None) -> Dict[str, Any]:
    """Read Onigimon's live inventory & currencies for the HUD quick-items popover."""
    pkg = addon_package or _onigiri_addon_package()
    try:
        from . import onigimon as og_mod

        state = og_mod.manager.load()
        items_catalog = getattr(og_mod, "ITEMS", {})
        label_fn = getattr(og_mod, "_onigimon_item_label", lambda k: str(k))
        effect_fn = getattr(og_mod, "_onigimon_item_effect", lambda k: "")
    except Exception:
        return {"currencies": [], "items": [], "total_count": 0}

    def _icon_url_for(key: str) -> str:
        meta = items_catalog.get(key, {}) if isinstance(items_catalog, dict) else {}
        rel = str(meta.get("icon_path") or "").lstrip("/")
        if rel:
            return f"/_addons/{pkg}/{rel}"
        return str(meta.get("icon_url") or "")

    currencies = [
        {
            "key": "valuable_comet_shard",
            "label": label_fn("valuable_comet_shard"),
            "count": _safe_int(getattr(state, "comet_shards", 0), 0),
            "icon_url": _icon_url_for("valuable_comet_shard"),
        },
        {
            "key": "valuable_star_piece",
            "label": label_fn("valuable_star_piece"),
            "count": _safe_int(getattr(state, "star_pieces", 0), 0),
            "icon_url": _icon_url_for("valuable_star_piece"),
        },
    ]

    inv = getattr(state, "inventory", {}) or {}
    items: List[Dict[str, Any]] = []
    total_count = 0
    if isinstance(inv, dict):
        for key, raw_qty in inv.items():
            if key in _EXCLUDED_INVENTORY_KEYS:
                continue
            qty = _safe_int(raw_qty, 0)
            if qty <= 0:
                continue
            total_count += qty
            effect_text = ""
            meta = items_catalog.get(key, {}) if isinstance(items_catalog, dict) else {}
            if meta.get("effect"):
                effect_text = str(effect_fn(key) or "")
            items.append(
                {
                    "key": str(key),
                    "label": str(label_fn(key) or key),
                    "effect": effect_text,
                    "count": qty,
                    "icon_url": _icon_url_for(key),
                    "usable": key not in _PASSIVE_INVENTORY_KEYS,
                }
            )
    items.sort(key=lambda entry: (-int(entry["count"]), entry["label"].lower()))

    return {
        "currencies": currencies,
        "items": items,
        "total_count": total_count,
    }


def build_hud_payload(
    reviewer_mgr: Any,
    pkg: Optional[str] = None,
    conf: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a structured, JSON-serializable HUD state payload from Ankimon's Reviewer_Manager."""
    if reviewer_mgr is None:
        return {"hidden": True}

    enemy_pokemon = getattr(reviewer_mgr, "enemy_pokemon", None)
    main_pokemon = getattr(reviewer_mgr, "main_pokemon", None)
    settings_obj = getattr(reviewer_mgr, "settings", None)
    if enemy_pokemon is None or main_pokemon is None:
        return {"hidden": True}

    show_mode = _safe_int(_setting(settings_obj, "gui.show_mainpkmn_in_reviewer", 1), 1)
    if show_mode == 3:
        return {"hidden": True}

    style_cfg = get_hud_style_settings(conf)
    resolved_pkg = pkg or _find_ankimon_package()
    try:
        addon_package = (
            reviewer_mgr._resolve_addon_package()
            if hasattr(reviewer_mgr, "_resolve_addon_package")
            else (resolved_pkg or "1908235722")
        )
    except Exception:
        addon_package = resolved_pkg or "1908235722"

    services = getattr(_get_ankimon_module(resolved_pkg, "services"), "services", None) if resolved_pkg else None
    encounter_mod = _get_ankimon_module(resolved_pkg, "functions.encounter_functions") if resolved_pkg else None
    reviewer_ui_mod = _get_ankimon_module(resolved_pkg, "reviewer_ui") if resolved_pkg else None
    tracker = getattr(reviewer_mgr, "ankimon_tracker", None)

    enemy_hp, enemy_max_hp = _safe_hp_pair(
        getattr(enemy_pokemon, "hp", 0), getattr(enemy_pokemon, "max_hp", 1)
    )
    main_hp, main_max_hp = _safe_hp_pair(
        getattr(main_pokemon, "hp", 0), getattr(main_pokemon, "max_hp", 1)
    )

    ownership_cache = getattr(reviewer_mgr, "_ownership_cache", None)
    enemy_id = getattr(enemy_pokemon, "id", None)
    is_owned = ownership_cache.get(enemy_id) if isinstance(ownership_cache, dict) else None
    if is_owned is None:
        is_owned = False
        try:
            db = getattr(services, "db", None)
            if db is not None and hasattr(db, "get_caught_ids"):
                is_owned = enemy_id in db.get_caught_ids()
                if isinstance(ownership_cache, dict):
                    ownership_cache[enemy_id] = is_owned
        except Exception:
            pass

    image_format = "gif" if style_cfg["motion"] == "animated" else "png"
    enemy_sprite_url = _resolve_sprite_url(enemy_pokemon, "front", image_format, addon_package)

    show_main = show_mode > 0
    main_sprite_url = ""
    main_flip = False
    if show_main:
        side = "back"
        if image_format == "gif":
            try:
                if settings_obj and settings_obj.compute_special_variable("view_main_front") == -1:
                    side = "front"
                    main_flip = True
            except Exception:
                pass
        main_sprite_url = _resolve_sprite_url(main_pokemon, side, image_format, addon_package)
        if not main_sprite_url:
            main_sprite_url = _resolve_sprite_url(main_pokemon, "front", image_format, addon_package)
            main_flip = True
        elif side == "back":
            main_flip = False

    xp_current = max(0, _safe_int(getattr(main_pokemon, "xp", 0), 0))
    xp_next = _compute_xp_next(resolved_pkg, main_pokemon, settings_obj)

    auto_battle = _safe_int(_setting(settings_obj, "battle.automatic_battle", 0), 0)
    auto_override = None
    if encounter_mod and hasattr(encounter_mod, "get_auto_battle_override"):
        try:
            auto_override = encounter_mod.get_auto_battle_override()
        except Exception:
            auto_override = None

    can_cycle_team = False
    try:
        cycle_count = _safe_int(_setting(settings_obj, "controls.team_cycle_count", 3), 3)
        db = getattr(services, "db", None)
        if cycle_count > 1 and db is not None and hasattr(db, "get_team"):
            can_cycle_team = len(db.get_team() or []) >= 2
    except Exception:
        can_cycle_team = False

    current_keys = getattr(reviewer_ui_mod, "_current_keys", None)
    shortcuts = {
        "catch": str((current_keys or {}).get("catch", _setting(settings_obj, "controls.catch_key", "6") or "6")),
        "defeat": str((current_keys or {}).get("defeat", _setting(settings_obj, "controls.defeat_key", "5") or "5")),
        "team_cycle": str(
            (current_keys or {}).get("team_cycle", _setting(settings_obj, "controls.team_cycle_key", "9") or "9")
        ),
    }

    flags = {
        "show_hp_bars": bool(_setting(settings_obj, "gui.hud_hp_bars", True)),
        "show_hp_text": bool(_setting(settings_obj, "gui.hud_hp_text", True)),
        "show_xp_bar": bool(_setting(settings_obj, "gui.hud_xp_bar", True)),
        "show_xp_values": bool(_setting(settings_obj, "gui.hud_xp_values", False)),
        "show_id": bool(_setting(settings_obj, "gui.hud_pokemon_id", False)),
        "show_gen": bool(_setting(settings_obj, "gui.hud_pokemon_gen", False)),
        "show_level": bool(_setting(settings_obj, "gui.hud_pokemon_lvl", True)),
        "show_name": bool(_setting(settings_obj, "gui.hud_pokemon_name", True)),
        "show_status": bool(_setting(settings_obj, "gui.hud_status_badge", True)),
        "show_owned": bool(_setting(settings_obj, "gui.hud_owned_indicator", True)),
    }

    allow_shake = style_cfg["motion"] == "animated"
    main_data = {
        "name": str(getattr(main_pokemon, "display_name", None) or getattr(main_pokemon, "name", "")),
        "pokedex_id": getattr(main_pokemon, "pokedex_id", getattr(main_pokemon, "id", None)),
        "generation": getattr(main_pokemon, "generation", None),
        "types": _extract_types(main_pokemon),
        "level": _safe_int(getattr(main_pokemon, "level", 1), 1),
        "hp": main_hp,
        "max_hp": main_max_hp,
        "xp": xp_current,
        "xp_next": xp_next,
        "status": str(getattr(main_pokemon, "battle_status", "") or ""),
        "shiny": bool(getattr(main_pokemon, "shiny", False)),
        "show_shiny": bool(_setting(settings_obj, "gui.hud_player_shiny_indicator", True)),
        "show_sprite": bool(_setting(settings_obj, "gui.hud_player_sprite", True)),
        "sprite_url": main_sprite_url,
        "flip": main_flip,
        "shake": allow_shake and float(getattr(reviewer_mgr, "myseconds", 0) or 0) > 0,
        "boosts": _extract_boosts(main_pokemon),
    }

    enemy_data = {
        "name": str(getattr(enemy_pokemon, "display_name", None) or getattr(enemy_pokemon, "name", "")),
        "pokedex_id": getattr(enemy_pokemon, "pokedex_id", getattr(enemy_pokemon, "id", None)),
        "generation": getattr(enemy_pokemon, "generation", None),
        "types": _extract_types(enemy_pokemon),
        "level": _safe_int(getattr(enemy_pokemon, "level", 1), 1),
        "hp": enemy_hp,
        "max_hp": enemy_max_hp,
        "status": str(getattr(enemy_pokemon, "battle_status", "") or ""),
        "shiny": bool(getattr(enemy_pokemon, "shiny", False)),
        "show_shiny": bool(_setting(settings_obj, "gui.hud_enemy_shiny_indicator", True)),
        "show_sprite": bool(_setting(settings_obj, "gui.hud_enemy_sprite", True)),
        "sprite_url": enemy_sprite_url,
        "owned": bool(is_owned),
        "flip": False,
        "shake": allow_shake and float(getattr(reviewer_mgr, "seconds", 0) or 0) > 0,
        "boosts": _extract_boosts(enemy_pokemon),
    }

    # War mode telemetry
    cards_per_round = _safe_int(_setting(settings_obj, "battle.cards_per_round", 2), 2)
    if tracker is not None and hasattr(tracker, "_get_cards_per_round"):
        try:
            cards_per_round = max(1, _safe_int(tracker._get_cards_per_round(), cards_per_round))
        except Exception:
            pass
    war_info = {
        "cards_battle_round": _safe_int(getattr(tracker, "cards_battle_round", 0), 0) if tracker else 0,
        "cards_per_round": max(1, cards_per_round),
        "multiplier": float(getattr(tracker, "multiplier", 1.0) or 1.0) if tracker else 1.0,
        "main_stats": _extract_combat_stats(main_pokemon),
        "enemy_ability": str(getattr(enemy_pokemon, "ability", "") or ""),
        "enemy_tier": str(getattr(enemy_pokemon, "tier", "") or ""),
    }

    return {
        "hidden": False,
        "hidden_on_startup": bool(_setting(settings_obj, "gui.hud_hidden_on_startup", False)),
        "night_mode": _anki_night_mode(),
        "show_main": show_main,
        "automatic_battle": auto_battle,
        "auto_battle_override": auto_override,
        "can_cycle_team": can_cycle_team,
        "shortcuts": shortcuts,
        "flags": flags,
        "style": style_cfg,
        "war": war_info,
        "inventory": build_inventory_snapshot(),
        "main": main_data,
        "enemy": enemy_data,
    }


def classify_ankimon_tooltip(msg: Any, color: Any = "", x: int = 0) -> Dict[str, Any]:
    """Classify an Ankimon reviewer tooltip into either a HUD HP delta or an Onigiri notification."""
    raw = str(msg or "")
    delta_match = _HP_DELTA_RE.match(raw)
    if delta_match:
        compact = re.sub(r"\s+", "", delta_match.group(1))
        kind = "heal" if compact.startswith("+") else "damage"
        side = "main" if _safe_int(x, 0) < 0 else "enemy"
        return {
            "channel": "delta",
            "side": side,
            "kind": kind,
            "text": f"{compact} HP",
        }

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    clean_text = " · ".join(lines) if len(lines) > 1 else (lines[0] if lines else "")
    color_norm = str(color or "").strip().lower()
    if color_norm in ("#6a4dac", "#a17cf7", "#e12939"):
        icon_role = "main"
    else:
        icon_role = "auto"

    return {
        "channel": "toast",
        "text": clean_text,
        "icon_role": icon_role,
    }


def _notification_icon_for_role(pkg: Optional[str], icon_role: str) -> str:
    if not pkg:
        return ""
    services = getattr(_get_ankimon_module(pkg, "services"), "services", None)
    reviewer_mgr = getattr(services, "reviewer", None) if services else None
    if reviewer_mgr is None:
        singletons = _get_ankimon_module(pkg, "singletons")
        reviewer_mgr = getattr(singletons, "reviewer_obj", None) if singletons else None
    if reviewer_mgr is None:
        return ""

    style_cfg = get_hud_style_settings()
    image_format = "gif" if style_cfg["motion"] == "animated" else "png"
    try:
        addon_package = reviewer_mgr._resolve_addon_package()
    except Exception:
        addon_package = pkg

    if icon_role == "enemy":
        pokemon = getattr(reviewer_mgr, "enemy_pokemon", None)
    else:
        pokemon = getattr(reviewer_mgr, "main_pokemon", None) or getattr(reviewer_mgr, "enemy_pokemon", None)
    return _resolve_sprite_url(pokemon, "front", image_format, addon_package)


def _active_companion_sprite_urls(pkg: Optional[str] = None) -> Tuple[str, List[str]]:
    """Resolve the active companion's sprite URL + fallbacks for Onigimon notifications."""
    urls: List[str] = []
    resolved_pkg = pkg or _find_ankimon_package()
    live_url = _notification_icon_for_role(resolved_pkg, "main")
    if live_url:
        urls.append(live_url)

    try:
        from dataclasses import asdict, is_dataclass
        from . import onigimon as og_mod

        mgr = getattr(og_mod, "manager", None)
        if mgr is not None and hasattr(mgr, "active_companion") and hasattr(mgr, "sprite_urls_for_companion"):
            companion = mgr.active_companion(refresh_from_ankimon=False)
            if companion is not None:
                comp_dict = asdict(companion) if is_dataclass(companion) else (companion if isinstance(companion, dict) else {})
                motion = "gif" if get_hud_style_settings().get("motion") == "animated" else "static"
                for candidate in mgr.sprite_urls_for_companion(comp_dict, motion=motion) or []:
                    if candidate and candidate not in urls:
                        urls.append(str(candidate))
    except Exception:
        pass

    if not urls:
        return "", []
    return urls[0], urls[1:]


def _eval_on_reviewer_web(web: Any, script: str) -> None:
    if web is None or not hasattr(web, "eval"):
        return
    try:
        web.eval(script)
    except Exception:
        pass


def push_hud_to_reviewer(
    reviewer_mgr: Any,
    reviewer_web: Any,
    pkg: Optional[str] = None,
    conf: Optional[Dict[str, Any]] = None,
) -> None:
    payload = build_hud_payload(reviewer_mgr, pkg=pkg, conf=conf)
    payload_json = json.dumps(payload, ensure_ascii=False)
    script = (
        "(function(p){"
        "if(window.__ankimonHud && typeof window.__ankimonHud.clear==='function'){window.__ankimonHud.clear();}"
        "if(window.OnigimonHUD && typeof window.OnigimonHUD.update==='function'){window.OnigimonHUD.update(p);}"
        f"}})({payload_json});"
    )
    _eval_on_reviewer_web(reviewer_web, script)


def _dispatch_ankimon_notification(
    pkg: str,
    msg: Any,
    color: Any = "",
    x: int = 0,
    *,
    respect_message_box_setting: bool = True,
) -> None:
    services = getattr(_get_ankimon_module(pkg, "services"), "services", None)
    events_mod = _get_ankimon_module(pkg, "events")
    events = getattr(events_mod, "events", None) if events_mod else None
    if events is not None and hasattr(events, "emit"):
        try:
            events.emit("tooltip", message=msg, color=color)
        except Exception:
            pass

    settings_obj = getattr(services, "settings", None) if services else None
    msg_box_enabled = (
        bool(_setting(settings_obj, "gui.reviewer_text_message_box", True))
        if respect_message_box_setting
        else True
    )
    period_s = _setting(settings_obj, "gui.reviewer_text_message_box_time", 3)
    try:
        duration_ms = max(1600, min(12000, int(float(period_s) * 1000)))
    except (TypeError, ValueError):
        duration_ms = 3200

    classified = classify_ankimon_tooltip(msg, color=color, x=x)
    reviewer = getattr(mw, "reviewer", None) if mw else None
    reviewer_web = getattr(reviewer, "web", None) if reviewer else None

    if classified["channel"] == "delta":
        detail_json = json.dumps(
            {
                "side": classified["side"],
                "kind": classified["kind"],
                "text": classified["text"],
            },
            ensure_ascii=False,
        )
        _eval_on_reviewer_web(
            reviewer_web,
            f"if(window.OnigimonHUD && window.OnigimonHUD.showDelta){{window.OnigimonHUD.showDelta({detail_json});}}",
        )
        if msg_box_enabled:
            logger = getattr(services, "logger", None) if services else None
            if logger is not None and hasattr(logger, "log_and_showinfo"):
                try:
                    logger.log_and_showinfo("game", str(msg))
                except Exception:
                    pass
        return

    if not msg_box_enabled:
        return

    logger = getattr(services, "logger", None) if services else None
    if logger is not None and hasattr(logger, "log_and_showinfo"):
        try:
            logger.log_and_showinfo("game", str(msg))
        except Exception:
            pass

    clean_text = classified.get("text", "")
    if not clean_text:
        return

    icon_image = _notification_icon_for_role(pkg, classified.get("icon_role", "auto"))
    icon_fallbacks: List[str] = []
    if not icon_image:
        icon_image, icon_fallbacks = _active_companion_sprite_urls(pkg)
    show_onigiri_notification(
        clean_text,
        title="",
        context=reviewer,
        variant="onigimon",
        icon="On",
        icon_image=icon_image,
        icon_fallbacks=icon_fallbacks,
        duration=duration_ms,
        hide_title=True,
        gamification=True,
    )


def ensure_ankimon_hooks() -> bool:
    """Idempotently wrap Ankimon's reviewer HUD & reviewer tooltips so Onigimon HUD takes over cleanly."""
    pkg = _find_ankimon_package()
    if not pkg:
        return False

    wrapped_any = False

    # 1. Wrap Reviewer_Manager.update_life_bar
    reviewer_mod = _get_ankimon_module(pkg, "pyobj.reviewer_obj")
    reviewer_cls = getattr(reviewer_mod, "Reviewer_Manager", None) if reviewer_mod else None
    if reviewer_cls is not None:
        current_fn = getattr(reviewer_cls, "update_life_bar", None)
        if current_fn is not None and not getattr(current_fn, "_onigimon_hud_wrapped", False):
            orig_update = current_fn
            setattr(reviewer_cls, "_onigimon_orig_update_life_bar", orig_update)

            def _wrapped_update_life_bar(self, reviewer, card, ease, _orig=orig_update, _pkg=pkg):
                if not is_hud_enabled():
                    return _orig(self, reviewer, card, ease)
                if isinstance(ease, int) and ease != 0:
                    return None
                if card is not None and not isinstance(card, int):
                    return None
                web = getattr(reviewer, "web", None)
                push_hud_to_reviewer(self, web, pkg=_pkg)
                return None

            _wrapped_update_life_bar._onigimon_hud_wrapped = True
            reviewer_cls.update_life_bar = _wrapped_update_life_bar
            wrapped_any = True

    # 2. Wrap tooltipWithColour across Ankimon modules that import it by reference
    drawing_mod = _get_ankimon_module(pkg, "functions.drawing_utils")
    if drawing_mod is not None:
        current_twc = getattr(drawing_mod, "tooltipWithColour", None)
        if current_twc is not None and not getattr(current_twc, "_onigimon_hud_wrapped", False):
            orig_twc = current_twc
            setattr(drawing_mod, "_onigimon_orig_tooltip_with_colour", orig_twc)

            def _wrapped_tooltip_with_colour(
                msg,
                color,
                x=0,
                y=20,
                xref=1,
                parent=None,
                width=0,
                height=0,
                centered=False,
                _orig=orig_twc,
                _pkg=pkg,
            ):
                if is_hud_enabled() and getattr(mw, "state", None) == "review":
                    _dispatch_ankimon_notification(
                        _pkg, msg, color=color, x=x, respect_message_box_setting=True
                    )
                    return None
                return _orig(
                    msg,
                    color,
                    x=x,
                    y=y,
                    xref=xref,
                    parent=parent,
                    width=width,
                    height=height,
                    centered=centered,
                )

            _wrapped_tooltip_with_colour._onigimon_hud_wrapped = True
            drawing_mod.tooltipWithColour = _wrapped_tooltip_with_colour
            wrapped_any = True

        wrapped_twc = getattr(drawing_mod, "tooltipWithColour", None)
        if wrapped_twc is not None and getattr(wrapped_twc, "_onigimon_hud_wrapped", False):
            for mod_suffix in ("battle_loop", "functions.encounter_functions", "functions.trainer_functions"):
                target_mod = _get_ankimon_module(pkg, mod_suffix)
                if target_mod is not None and hasattr(target_mod, "tooltipWithColour"):
                    if not getattr(target_mod.tooltipWithColour, "_onigimon_hud_wrapped", False):
                        target_mod.tooltipWithColour = wrapped_twc
                        wrapped_any = True

    # 3. Wrap reviewer-specific plain tooltip() calls in reviewer_ui & encounter_functions
    for mod_suffix in ("reviewer_ui", "functions.encounter_functions"):
        target_mod = _get_ankimon_module(pkg, mod_suffix)
        if target_mod is None or not hasattr(target_mod, "tooltip"):
            continue
        current_tip = getattr(target_mod, "tooltip", None)
        if current_tip is not None and not getattr(current_tip, "_onigimon_hud_wrapped", False):
            orig_tip = current_tip
            setattr(target_mod, "_onigimon_orig_tooltip", orig_tip)

            def _wrapped_reviewer_tooltip(msg, *args, _orig=orig_tip, _pkg=pkg, **kwargs):
                if is_hud_enabled() and getattr(mw, "state", None) == "review":
                    _dispatch_ankimon_notification(
                        _pkg, msg, color="", x=0, respect_message_box_setting=False
                    )
                    return None
                return _orig(msg, *args, **kwargs)

            _wrapped_reviewer_tooltip._onigimon_hud_wrapped = True
            target_mod.tooltip = _wrapped_reviewer_tooltip
            wrapped_any = True

    return wrapped_any


def set_position(x_pct: float, y_pct: float) -> bool:
    """Persist the user's dragged HUD position (viewport percentage)."""
    pos = _normalize_position({"x": x_pct, "y": y_pct})
    if pos is None:
        return False
    try:
        conf = config.get_config()
        conf.setdefault("onigimon", {})["reviewer_hud_position"] = pos
        config.write_config(conf)
        return True
    except Exception as exc:
        print(f"Onigimon HUD: failed to save position: {exc}")
        return False


def reset_position() -> bool:
    """Clear the custom HUD position back to default bottom-center."""
    try:
        conf = config.get_config()
        conf.setdefault("onigimon", {})["reviewer_hud_position"] = None
        config.write_config(conf)
        refresh_live_hud(conf)
        return True
    except Exception as exc:
        print(f"Onigimon HUD: failed to reset position: {exc}")
        return False


def use_hud_item(item_key: str) -> bool:
    """Use an Onigimon care item directly from the HUD items popover."""
    key = str(item_key or "").strip()
    if not key or key in _PASSIVE_INVENTORY_KEYS:
        return False
    try:
        from . import onigimon as og_mod

        message = og_mod.manager.use_item(key)
    except Exception as exc:
        print(f"Onigimon HUD: failed to use item {key!r}: {exc}")
        return False

    reviewer = getattr(mw, "reviewer", None) if mw else None
    if message:
        icon_image, icon_fallbacks = _active_companion_sprite_urls()
        show_onigiri_notification(
            str(message),
            title="",
            context=reviewer,
            variant="onigimon",
            icon="On",
            icon_image=icon_image,
            icon_fallbacks=icon_fallbacks,
            hide_title=True,
            gamification=True,
        )
    refresh_live_hud()
    return True


def trigger_action(action: str) -> bool:
    """Invoke an Ankimon reviewer action (catch / defeat / cycle_team) from the Onigimon HUD."""
    pkg = _find_ankimon_package()
    if not pkg:
        return False
    reviewer_ui_mod = _get_ankimon_module(pkg, "reviewer_ui")
    if reviewer_ui_mod is None:
        return False

    fn_map = {
        "catch": "catch_shortcut_function",
        "defeat": "defeat_shortcut_function",
        "cycle_team": "team_cycle_shortcut_function",
    }
    fn_name = fn_map.get(str(action or "").strip().lower())
    fn = getattr(reviewer_ui_mod, fn_name, None) if fn_name else None
    if not callable(fn):
        return False

    try:
        fn()
    except Exception as exc:
        print(f"Onigimon HUD: action {action!r} failed: {exc}")
        return False

    refresh_live_hud()
    return True


def refresh_live_hud(conf: Optional[Dict[str, Any]] = None) -> None:
    """Sync the live reviewer HUD immediately after Settings or theme changes."""
    enabled = is_hud_enabled(conf)
    if enabled:
        ensure_ankimon_hooks()

    pkg = _find_ankimon_package()
    reviewer = getattr(mw, "reviewer", None) if mw else None
    reviewer_web = getattr(reviewer, "web", None) if reviewer else None

    if getattr(mw, "state", None) == "review" and reviewer_web is not None:
        _eval_on_reviewer_web(
            reviewer_web,
            f"if(window.OnigimonHUD && window.OnigimonHUD.setEnabled){{window.OnigimonHUD.setEnabled({'true' if enabled else 'false'});}}",
        )

    if not pkg:
        return

    services = getattr(_get_ankimon_module(pkg, "services"), "services", None)
    reviewer_mgr = getattr(services, "reviewer", None) if services else None
    if reviewer_mgr is None:
        singletons = _get_ankimon_module(pkg, "singletons")
        reviewer_mgr = getattr(singletons, "reviewer_obj", None) if singletons else None
    if reviewer_mgr is None:
        return

    try:
        if hasattr(reviewer_mgr, "invalidate_hud_cache"):
            reviewer_mgr.invalidate_hud_cache()
        else:
            reviewer_mgr._last_state = None
    except Exception:
        pass

    if getattr(mw, "state", None) == "review":
        if enabled and reviewer_web is not None:
            push_hud_to_reviewer(reviewer_mgr, reviewer_web, pkg=pkg, conf=conf)
        elif hasattr(reviewer_mgr, "refresh_hud"):
            try:
                reviewer_mgr.refresh_hud()
            except Exception:
                pass


def _on_profile_did_open() -> None:
    if is_hud_enabled():
        ensure_ankimon_hooks()


def _on_reviewer_will_end() -> None:
    reviewer = getattr(mw, "reviewer", None) if mw else None
    reviewer_web = getattr(reviewer, "web", None) if reviewer else None
    _eval_on_reviewer_web(
        reviewer_web,
        "if(window.OnigimonHUD && window.OnigimonHUD.clear){window.OnigimonHUD.clear();}",
    )


def _on_theme_did_change() -> None:
    if is_hud_enabled() and getattr(mw, "state", None) == "review":
        refresh_live_hud()


def register_hooks() -> None:
    global _hooks_registered
    if _hooks_registered or gui_hooks is None:
        return
    _hooks_registered = True
    try:
        gui_hooks.profile_did_open.append(_on_profile_did_open)
    except Exception:
        pass
    try:
        gui_hooks.reviewer_will_end.append(_on_reviewer_will_end)
    except Exception:
        pass
    try:
        gui_hooks.theme_did_change.append(_on_theme_did_change)
    except Exception:
        pass
    if is_hud_enabled():
        ensure_ankimon_hooks()
