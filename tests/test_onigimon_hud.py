"""Tests for the Onigimon Reviewer HUD replacement (modes, customization, drag positioning, quick items, notifications)."""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _load_onigimon_hud(conf_state, notified_calls, eval_calls, mw_state="review", inventory_state=None, used_items=None):
    """Load gamification/onigimon_hud.py with lightweight stubs (no Anki/Qt required)."""
    pkg_name = "_onigiri_hud_test"
    # Ensure a fresh module import per test
    for key in list(sys.modules):
        if key == pkg_name or key.startswith(pkg_name + "."):
            sys.modules.pop(key, None)

    root_pkg = types.ModuleType(pkg_name)
    root_pkg.__path__ = [str(ROOT)]

    core_pkg = types.ModuleType(pkg_name + ".core")
    core_pkg.__path__ = [str(ROOT / "core")]

    config_mod = types.ModuleType(pkg_name + ".core.config")
    config_mod.get_config_readonly = lambda: conf_state
    config_mod.get_config = lambda: conf_state
    config_mod.write_config = lambda updated: conf_state.update(updated)

    trans_mod = types.ModuleType(pkg_name + ".core.translations")
    trans_mod.tr = lambda key, default="": default or key

    ui_kit_pkg = types.ModuleType(pkg_name + ".ui_kit")
    ui_kit_pkg.__path__ = [str(ROOT / "ui_kit")]

    notif_mod = types.ModuleType(pkg_name + ".ui_kit.onigiri_notifications")
    notif_mod.notify = lambda msg, **kwargs: notified_calls.append((msg, kwargs))

    gamif_pkg = types.ModuleType(pkg_name + ".gamification")
    gamif_pkg.__path__ = [str(ROOT / "gamification")]

    inv_obj = inventory_state or types.SimpleNamespace(
        comet_shards=120,
        star_pieces=3,
        inventory={"berry_oran": 4, "medicine": 2, "pokeballs": 5, "play_action": 0},
    )
    used_log = used_items if used_items is not None else []

    og_mod = types.ModuleType(pkg_name + ".gamification.onigimon")
    og_mod.ITEMS = {
        "berry_oran": {"label": "Oran Berry", "icon_path": "system_files/pokesprite/items/berry-oran.png", "effect": "Reliable hunger care"},
        "medicine": {"label": "Potion", "icon_path": "system_files/pokesprite/items/medicine-potion.png", "effect": "Restores health"},
        "pokeballs": {"label": "Pokéballs", "icon_path": "system_files/pokesprite/items/ball-poke.png"},
        "valuable_comet_shard": {"label": "Comet Shard", "icon_path": "system_files/pokesprite/items/valuable-item-comet-shard.png"},
        "valuable_star_piece": {"label": "Star Piece", "icon_path": "system_files/pokesprite/items/valuable-item-star-piece.png"},
    }
    og_mod._onigimon_item_label = lambda k: og_mod.ITEMS.get(k, {}).get("label", k)
    og_mod._onigimon_item_effect = lambda k: og_mod.ITEMS.get(k, {}).get("effect", "")

    def _use_item(key):
        used_log.append(key)
        if inv_obj.inventory.get(key, 0) > 0:
            inv_obj.inventory[key] -= 1
            return f"Used {og_mod._onigimon_item_label(key)}!"
        return ""

    og_mod.manager = types.SimpleNamespace(load=lambda: inv_obj, use_item=_use_item)

    hooks_recorded = {
        "profile_did_open": [],
        "reviewer_will_end": [],
        "theme_did_change": [],
    }
    aqt_mod = types.ModuleType("aqt")
    aqt_mod.gui_hooks = types.SimpleNamespace(
        profile_did_open=hooks_recorded["profile_did_open"],
        reviewer_will_end=hooks_recorded["reviewer_will_end"],
        theme_did_change=hooks_recorded["theme_did_change"],
    )
    aqt_mod.mw = types.SimpleNamespace(
        state=mw_state,
        reviewer=types.SimpleNamespace(
            web=types.SimpleNamespace(eval=eval_calls.append)
        ),
    )

    theme_mod = types.ModuleType("aqt.theme")
    theme_mod.theme_manager = types.SimpleNamespace(night_mode=False)

    modules = {
        pkg_name: root_pkg,
        pkg_name + ".core": core_pkg,
        pkg_name + ".core.config": config_mod,
        pkg_name + ".core.translations": trans_mod,
        pkg_name + ".ui_kit": ui_kit_pkg,
        pkg_name + ".ui_kit.onigiri_notifications": notif_mod,
        pkg_name + ".gamification": gamif_pkg,
        pkg_name + ".gamification.onigimon": og_mod,
        "aqt": aqt_mod,
        "aqt.theme": theme_mod,
    }
    patcher = patch.dict(sys.modules, modules)
    patcher.start()
    mod = importlib.import_module(pkg_name + ".gamification.onigimon_hud")
    return mod, aqt_mod, theme_mod, hooks_recorded, patcher


def _make_fake_ankimon():
    """Create a realistic fake Ankimon runtime in sys.modules['1908235722.*']."""
    emitted = []
    logged = []
    orig_hud_calls = []
    orig_twc_calls = []
    orig_tip_calls = []
    action_calls = []

    class FakeSettings:
        def __init__(self):
            self.data = {
                "gui.show_mainpkmn_in_reviewer": 1,
                "gui.reviewer_image_gif": False,
                "gui.hud_hidden_on_startup": False,
                "gui.hud_hp_bars": True,
                "gui.hud_hp_text": True,
                "gui.hud_xp_bar": True,
                "gui.hud_xp_values": True,
                "gui.hud_pokemon_id": True,
                "gui.hud_pokemon_gen": False,
                "gui.hud_pokemon_lvl": True,
                "gui.hud_pokemon_name": True,
                "gui.hud_status_badge": True,
                "gui.hud_owned_indicator": True,
                "gui.hud_enemy_shiny_indicator": True,
                "gui.hud_player_shiny_indicator": True,
                "gui.hud_player_sprite": True,
                "gui.hud_enemy_sprite": True,
                "gui.reviewer_text_message_box": True,
                "gui.reviewer_text_message_box_time": 3,
                "battle.automatic_battle": 0,
                "battle.cards_per_round": 2,
                "controls.team_cycle_count": 3,
                "misc.remove_level_cap": False,
            }

        def get(self, key, default=None):
            return self.data.get(key, default)

        def compute_special_variable(self, name):
            return 1

    class FakePokemon:
        def __init__(
            self,
            pid,
            name,
            hp,
            max_hp,
            level,
            xp=0,
            shiny=False,
            status="fighting",
            boosts=None,
            types_list=None,
            ability="Static",
            tier="Normal",
        ):
            self.id = pid
            self.pokedex_id = pid
            self.name = name
            self.display_name = name
            self.generation = 1
            self.type = types_list or ["normal"]
            self.ability = ability
            self.tier = tier
            self.hp = hp
            self.max_hp = max_hp
            self.level = level
            self.xp = xp
            self.growth_rate = "medium-fast"
            self.shiny = shiny
            self.battle_status = status
            self.base_stats = {"hp": 35, "atk": 55, "def": 40, "spa": 50, "spd": 50, "spe": 90}
            self._boosts = boosts or {}

        def get_sprite_path(self, side, image_format):
            return f"user_files/sprites/{side}/{self.id}.{image_format}"

        def to_engine_format(self):
            out = {"attack": 32, "defense": 22, "special_attack": 28, "special_defense": 26, "speed": 48}
            out.update(self._boosts)
            return out

    settings = FakeSettings()
    main_pkmn = FakePokemon(
        25, "Pikachu", 34, 48, 18, xp=120, boosts={"attack_boost": 2}, types_list=["Electric"], ability="Static"
    )
    enemy_pkmn = FakePokemon(
        19, "Rattata", 12, 30, 14, shiny=True, status="burn", types_list=["Normal"], ability="Run Away", tier="Common"
    )
    tracker = types.SimpleNamespace(cards_battle_round=1, multiplier=1.5, _get_cards_per_round=lambda: 2)

    class FakeReviewerManager:
        def __init__(self):
            self.settings = settings
            self.main_pokemon = main_pkmn
            self.enemy_pokemon = enemy_pkmn
            self.ankimon_tracker = tracker
            self._ownership_cache = {}
            self._last_state = None
            self.seconds = 0.5
            self.myseconds = 0

        def _resolve_addon_package(self):
            return "1908235722"

        def invalidate_hud_cache(self):
            self._last_state = None

        def refresh_hud(self):
            shim = types.SimpleNamespace(web=sys.modules["aqt"].mw.reviewer.web)
            self.update_life_bar(shim, 0, 0)

        def update_life_bar(self, reviewer, card, ease):
            orig_hud_calls.append((reviewer, card, ease))

    reviewer_mgr = FakeReviewerManager()
    db = types.SimpleNamespace(
        get_caught_ids=lambda: {19},
        get_team=lambda: [{"individual_id": "a"}, {"individual_id": "b"}],
    )
    logger = types.SimpleNamespace(log_and_showinfo=lambda lvl, msg: logged.append((lvl, msg)))
    services_obj = types.SimpleNamespace(
        settings=settings,
        db=db,
        logger=logger,
        reviewer=reviewer_mgr,
    )

    def orig_twc(msg, color, x=0, y=20, xref=1, parent=None, width=0, height=0, centered=False):
        orig_twc_calls.append((msg, color, x))

    def orig_tip(msg, *args, **kwargs):
        orig_tip_calls.append(msg)

    services_mod = types.ModuleType("1908235722.services")
    services_mod.services = services_obj

    events_mod = types.ModuleType("1908235722.events")
    events_mod.events = types.SimpleNamespace(emit=lambda kind, **fields: emitted.append((kind, fields)))

    reviewer_obj_mod = types.ModuleType("1908235722.pyobj.reviewer_obj")
    reviewer_obj_mod.Reviewer_Manager = FakeReviewerManager

    singletons_mod = types.ModuleType("1908235722.singletons")
    singletons_mod.reviewer_obj = reviewer_mgr

    pokemon_fn_mod = types.ModuleType("1908235722.functions.pokemon_functions")
    pokemon_fn_mod.find_experience_for_level = lambda growth, lvl, cap: 250

    drawing_mod = types.ModuleType("1908235722.functions.drawing_utils")
    drawing_mod.tooltipWithColour = orig_twc

    battle_mod = types.ModuleType("1908235722.battle_loop")
    battle_mod.tooltipWithColour = orig_twc

    encounter_mod = types.ModuleType("1908235722.functions.encounter_functions")
    encounter_mod.tooltipWithColour = orig_twc
    encounter_mod.tooltip = orig_tip
    encounter_mod.get_auto_battle_override = lambda: None

    trainer_mod = types.ModuleType("1908235722.functions.trainer_functions")
    trainer_mod.tooltipWithColour = orig_twc

    reviewer_ui_mod = types.ModuleType("1908235722.reviewer_ui")
    reviewer_ui_mod._current_keys = {"catch": "6", "defeat": "5", "team_cycle": "9"}
    reviewer_ui_mod.tooltip = orig_tip
    reviewer_ui_mod.catch_shortcut_function = lambda: action_calls.append("catch")
    reviewer_ui_mod.defeat_shortcut_function = lambda: action_calls.append("defeat")
    reviewer_ui_mod.team_cycle_shortcut_function = lambda: action_calls.append("cycle_team")

    fake_modules = {
        "1908235722.services": services_mod,
        "1908235722.events": events_mod,
        "1908235722.pyobj.reviewer_obj": reviewer_obj_mod,
        "1908235722.singletons": singletons_mod,
        "1908235722.functions.pokemon_functions": pokemon_fn_mod,
        "1908235722.functions.drawing_utils": drawing_mod,
        "1908235722.battle_loop": battle_mod,
        "1908235722.functions.encounter_functions": encounter_mod,
        "1908235722.functions.trainer_functions": trainer_mod,
        "1908235722.reviewer_ui": reviewer_ui_mod,
    }
    return {
        "modules": fake_modules,
        "reviewer_mgr": reviewer_mgr,
        "settings": settings,
        "main_pkmn": main_pkmn,
        "enemy_pkmn": enemy_pkmn,
        "emitted": emitted,
        "logged": logged,
        "orig_hud_calls": orig_hud_calls,
        "orig_twc_calls": orig_twc_calls,
        "orig_tip_calls": orig_tip_calls,
        "action_calls": action_calls,
    }


class OnigimonHudConfigAndWiringTests(unittest.TestCase):
    def test_default_config_enables_hud_and_customization_defaults(self):
        cfg_src = (ROOT / "core" / "config.py").read_text(encoding="utf-8")
        for needle in (
            '"reviewer_hud_enabled": True',
            '"reviewer_hud_mode": "battle"',
            '"reviewer_hud_motion": "animated"',
            '"reviewer_hud_scale": 100',
            '"reviewer_hud_opacity": 88',
            '"reviewer_hud_bg_color_light": "#ffffff"',
            '"reviewer_hud_bg_color_dark": "#202124"',
            '"reviewer_hud_shadow": True',
            '"reviewer_hud_position": None',
        ):
            self.assertIn(needle, cfg_src)

    def test_css_protects_hidden_attribute(self):
        css_src = (ROOT / "web" / "onigimon_hud.css").read_text(encoding="utf-8")
        self.assertIn("[hidden] {\n  display: none !important;\n}", css_src)

    def test_settings_page_exposes_all_hud_controls(self):
        games_src = (ROOT / "settings_web" / "games.py").read_text(encoding="utf-8")
        settings_js = (ROOT / "web" / "settings.js").read_text(encoding="utf-8")
        for needle in (
            '"post_save": ["gamification", "onigimon_hud"]',
            '"id": "onigimon_reviewer_hud"',
            '"layout": "designer_preview"',
            '"preview_kind": "onigimon_hud"',
            '"g_onigimon_reviewer_hud"',
            '"g_onigimon_hud_mode"',
            '"g_onigimon_hud_motion"',
            '"g_onigimon_hud_scale"',
            '"g_onigimon_hud_opacity"',
            '"g_onigimon_hud_bg_color"',
            '"g_onigimon_hud_shadow"',
            '"g_onigimon_hud_reset_position"',
        ):
            self.assertIn(needle, games_src)
        self.assertIn("PREVIEW_PAINTERS.onigimon_hud =", settings_js)
        # Reviewer HUD sits directly below Scene and above Difficulty
        idx_scene = games_src.index('"id": "onigimon_scene"')
        idx_hud = games_src.index('"id": "onigimon_reviewer_hud"')
        idx_diff = games_src.index('"id": "onigimon_difficulty"')
        self.assertLess(idx_scene, idx_hud)
        self.assertLess(idx_hud, idx_diff)

    def test_side_effects_games_state_and_handlers_wire_hud(self):
        side_src = (ROOT / "settings_web" / "side_effects.py").read_text(encoding="utf-8")
        state_src = (ROOT / "settings_web" / "games_state.py").read_text(encoding="utf-8")
        handlers_src = (ROOT / "rendering" / "webview_handlers.py").read_text(encoding="utf-8")
        self.assertIn('"onigimon_hud": _onigimon_hud', side_src)
        self.assertIn('name == "onigimon_hud_reset_position"', state_src)
        self.assertIn('payload.startswith("set_position:")', handlers_src)
        self.assertIn('payload == "reset_position"', handlers_src)
        self.assertIn('payload.startswith("use_item:")', handlers_src)


class OnigimonHudBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.conf = {
            "onigimon": {
                "enabled": True,
                "reviewer_hud_enabled": True,
                "reviewer_hud_mode": "battle",
                "reviewer_hud_motion": "animated",
                "reviewer_hud_scale": 100,
                "reviewer_hud_opacity": 88,
                "reviewer_hud_bg_color_light": "#ffffff",
                "reviewer_hud_bg_color_dark": "#202124",
                "reviewer_hud_shadow": True,
                "reviewer_hud_position": None,
            }
        }
        self.notified = []
        self.evals = []
        self.used_items = []
        self.mod, self.aqt, self.theme, self.hooks, self.patcher = _load_onigimon_hud(
            self.conf, self.notified, self.evals, used_items=self.used_items
        )
        self.addCleanup(self.patcher.stop)

    def test_style_settings_normalization_and_clamping(self):
        cfg = self.mod.get_hud_style_settings(
            {
                "onigimon": {
                    "reviewer_hud_mode": "war",
                    "reviewer_hud_motion": "static",
                    "reviewer_hud_scale": 200,
                    "reviewer_hud_opacity": 5,
                    "reviewer_hud_bg_color_light": "#ABC",
                    "reviewer_hud_bg_color_dark": "bad",
                    "reviewer_hud_shadow": False,
                    "reviewer_hud_position": {"x": 120, "y": -5},
                }
            }
        )
        self.assertEqual(cfg["mode"], "war")
        self.assertEqual(cfg["motion"], "static")
        self.assertEqual(cfg["scale"], 135)
        self.assertEqual(cfg["opacity"], 5)
        cfg_zero = self.mod.get_hud_style_settings({"onigimon": {"reviewer_hud_opacity": 0}})
        self.assertEqual(cfg_zero["opacity"], 0)
        self.assertEqual(cfg["bg_color_light"], "#aabbcc")
        self.assertEqual(cfg["bg_color_dark"], "#202124")
        self.assertFalse(cfg["shadow"])
        self.assertEqual(cfg["position"], {"x": 100.0, "y": 0.0})

    def test_build_hud_payload_includes_war_telemetry_inventory_and_motion(self):
        fake = _make_fake_ankimon()
        with patch.dict(sys.modules, fake["modules"]):
            payload = self.mod.build_hud_payload(fake["reviewer_mgr"], pkg="1908235722", conf=self.conf)
            self.assertEqual(payload["style"]["mode"], "battle")
            self.assertEqual(payload["style"]["motion"], "animated")
            self.assertEqual(payload["main"]["types"], ["electric"])
            self.assertEqual(payload["enemy"]["types"], ["normal"])
            self.assertTrue(payload["enemy"]["shake"])
            self.assertEqual(payload["enemy"]["sprite_url"], "/_addons/1908235722/user_files/sprites/front/19.gif")

            # War telemetry
            self.assertEqual(payload["war"]["cards_battle_round"], 1)
            self.assertEqual(payload["war"]["cards_per_round"], 2)
            self.assertEqual(payload["war"]["multiplier"], 1.5)
            self.assertEqual(payload["war"]["main_stats"]["atk"], 32)
            self.assertEqual(payload["war"]["enemy_ability"], "Run Away")
            self.assertEqual(payload["war"]["enemy_tier"], "Common")

            # Inventory snapshot
            inv = payload["inventory"]
            self.assertEqual(inv["total_count"], 11)
            self.assertEqual(len(inv["currencies"]), 2)
            keys = {item["key"]: item for item in inv["items"]}
            self.assertTrue(keys["berry_oran"]["usable"])
            self.assertFalse(keys["pokeballs"]["usable"])

            # Static motion uses png and disables shake
            self.conf["onigimon"]["reviewer_hud_motion"] = "static"
            static_payload = self.mod.build_hud_payload(fake["reviewer_mgr"], pkg="1908235722", conf=self.conf)
            self.assertFalse(static_payload["enemy"]["shake"])
            self.assertEqual(static_payload["enemy"]["sprite_url"], "/_addons/1908235722/user_files/sprites/front/19.png")

    def test_position_and_item_use_commands(self):
        fake = _make_fake_ankimon()
        with patch.dict(sys.modules, fake["modules"]):
            self.assertTrue(self.mod.set_position(25.5, 72.25))
            self.assertEqual(self.conf["onigimon"]["reviewer_hud_position"], {"x": 25.5, "y": 72.25})

            self.assertTrue(self.mod.reset_position())
            self.assertIsNone(self.conf["onigimon"]["reviewer_hud_position"])

            self.assertTrue(self.mod.use_hud_item("berry_oran"))
            self.assertEqual(self.used_items, ["berry_oran"])
            self.assertEqual(len(self.notified), 1)
            self.assertIn("Oran Berry", self.notified[0][0])
            self.assertEqual(
                self.notified[0][1]["icon_image"],
                "/_addons/1908235722/user_files/sprites/front/25.gif",
            )

            # Passive items like pokeballs cannot be consumed directly
            self.assertFalse(self.mod.use_hud_item("pokeballs"))

    def test_ankimon_hooks_intercept_and_restore(self):
        fake = _make_fake_ankimon()
        with patch.dict(sys.modules, fake["modules"]):
            self.assertTrue(self.mod.ensure_ankimon_hooks())
            self.assertFalse(self.mod.ensure_ankimon_hooks())

            fake["reviewer_mgr"].refresh_hud()
            self.assertEqual(len(fake["orig_hud_calls"]), 0)
            self.assertTrue(any("window.OnigimonHUD.update" in js for js in self.evals))

            battle_mod = sys.modules["1908235722.battle_loop"]
            battle_mod.tooltipWithColour(" -12 HP ", "#F06060", x=200)
            self.assertTrue(any("window.OnigimonHUD.showDelta" in js for js in self.evals))

            battle_mod.tooltipWithColour("Pikachu used Quick Attack!", "#F0B27A")
            self.assertEqual(len(self.notified), 1)
            self.assertEqual(self.notified[0][0], "Pikachu used Quick Attack!")

            self.conf["onigimon"]["reviewer_hud_enabled"] = False
            self.mod.refresh_live_hud(self.conf)
            self.assertEqual(len(fake["orig_hud_calls"]), 1)


class OnigimonHudFrontendJsTests(unittest.TestCase):
    def test_js_modes_minimize_items_appearance_and_drag(self):
        node = shutil.which("node") or ("/opt/homebrew/bin/node" if Path("/opt/homebrew/bin/node").exists() else None)
        if not node:
            self.skipTest("node not installed")

        js_file = ROOT / "web" / "onigimon_hud.js"
        css_file = ROOT / "web" / "onigimon_hud.css"
        harness = f"""
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

class ClassList {{
  constructor() {{ this.set = new Set(); }}
  add(...names) {{ names.forEach(n => this.set.add(n)); }}
  remove(...names) {{ names.forEach(n => this.set.delete(n)); }}
  contains(n) {{ return this.set.has(n); }}
  toggle(n, force) {{
    if (force === undefined) {{
      if (this.set.has(n)) {{ this.set.delete(n); return false; }}
      this.set.add(n); return true;
    }}
    if (force) this.set.add(n); else this.set.delete(n);
    return !!force;
  }}
}}

class FakeStyle {{
  constructor() {{ this.props = {{}}; this.cssText = ''; }}
  setProperty(k, v) {{ this.props[k] = String(v); }}
  removeProperty(k) {{ delete this.props[k]; }}
}}

class FakeEl {{
  constructor(tag) {{
    this.tagName = String(tag || 'DIV').toUpperCase();
    this.nodeType = 1;
    this.id = '';
    this.className = '';
    this.classList = new ClassList();
    this.children = [];
    this.parentNode = null;
    this.style = new FakeStyle();
    this.dataset = {{}};
    this.attrs = {{}};
    this.listeners = {{}};
    this.hidden = false;
    this.disabled = false;
    this.shadowRoot = null;
    this.textContent = '';
    this.innerHTML = '';
    this.value = 0;
    this.max = 100;
    this.src = '';
    this.alt = '';
    this.offsetWidth = 100;
  }}
  get isConnected() {{ return !!this.parentNode || this.tagName === 'HTML'; }}
  getBoundingClientRect() {{ return {{ left: 200, top: 500, width: 320, height: 58 }}; }}
  closest(sel) {{
    const parts = sel.split(',').map(s => s.trim());
    let cur = this;
    while (cur) {{
      for (const p of parts) {{
        if (p.startsWith('.') && ((cur.className || '').split(/\\s+/).includes(p.slice(1)) || cur.classList.contains(p.slice(1)))) return cur;
        if (cur.tagName === p.toUpperCase()) return cur;
      }}
      cur = cur.parentNode;
    }}
    return null;
  }}
  appendChild(child) {{
    if (child && child.parentNode) child.remove();
    if (child) child.parentNode = this;
    this.children.push(child);
    return child;
  }}
  append(...nodes) {{
    for (const n of nodes) this.appendChild(n);
  }}
  remove() {{
    if (!this.parentNode) return;
    const idx = this.parentNode.children.indexOf(this);
    if (idx >= 0) this.parentNode.children.splice(idx, 1);
    this.parentNode = null;
  }}
  attachShadow() {{
    this.shadowRoot = new FakeEl('#shadow');
    this.shadowRoot.parentNode = this;
    return this.shadowRoot;
  }}
  setAttribute(k, v) {{ this.attrs[k] = String(v); }}
  getAttribute(k) {{ return this.attrs[k]; }}
  addEventListener(type, fn) {{
    (this.listeners[type] = this.listeners[type] || []).push(fn);
  }}
  dispatch(type, evt) {{
    for (const fn of (this.listeners[type] || [])) fn(evt || {{ stopPropagation() {{}}, target: this }});
  }}
  findById(id) {{
    if (this.id === id) return this;
    for (const c of this.children) {{
      if (c && c.findById) {{
        const found = c.findById(id);
        if (found) return found;
      }}
    }}
    return null;
  }}
  findAllByClass(cls, acc = []) {{
    if ((this.className && this.className.split(/\\s+/).includes(cls)) || this.classList.contains(cls)) {{
      acc.push(this);
    }}
    for (const c of this.children) {{
      if (c && c.findAllByClass) c.findAllByClass(cls, acc);
    }}
    return acc;
  }}
}}

const htmlEl = new FakeEl('html');
const headEl = new FakeEl('head');
const bodyEl = new FakeEl('body');
htmlEl.appendChild(headEl);
htmlEl.appendChild(bodyEl);

const docListeners = {{}};
const cmds = [];

const document = {{
  documentElement: htmlEl,
  head: headEl,
  body: bodyEl,
  createElement: (tag) => new FakeEl(tag),
  createTextNode: (t) => ({{ nodeType: 3, textContent: String(t), remove() {{}} }}),
  getElementById: (id) => htmlEl.findById(id),
  addEventListener: (type, fn) => {{ (docListeners[type] = docListeners[type] || []).push(fn); }},
}};

const window = {{
  innerWidth: 1200,
  innerHeight: 800,
  onigimonHudEnabled: true,
  onigimonHudCssText: fs.readFileSync({json.dumps(str(css_file))}, 'utf8'),
  onigimonHudLabels: {{ catchLabel: 'Catch', defeatLabel: 'Defeat', cycleTeam: 'Switch', hideHud: 'Minimize HUD', showHud: 'Onigimon', fainted: 'Fainted', itemsTitle: 'Items', itemsEmpty: 'Empty', dragHint: 'Drag', roundLabel: 'Round' }},
  __ankimonHud: {{ clear: () => {{}} }},
  pycmd: (cmd) => cmds.push(cmd),
  setTimeout: () => 1,
  addEventListener: () => {{}},
}};

const context = vm.createContext({{ window, document, console }});
vm.runInContext(fs.readFileSync({json.dumps(str(js_file))}, 'utf8'), context);

const basePayload = (overrides = {{}}) => Object.assign({{
  hidden: false,
  hidden_on_startup: false,
  night_mode: false,
  show_main: true,
  automatic_battle: 0,
  can_cycle_team: true,
  shortcuts: {{ catch: '6', defeat: '5', team_cycle: '9' }},
  flags: {{ show_hp_bars: true, show_hp_text: true, show_xp_bar: true, show_xp_values: false, show_name: true, show_level: true, show_status: true, show_owned: true }},
  style: {{ mode: 'battle', motion: 'animated', scale: 110, opacity: 75, bg_color_light: '#102030', bg_color_dark: '#202124', shadow: false, position: null }},
  war: {{ cards_battle_round: 1, cards_per_round: 2, multiplier: 1.5, main_stats: {{ atk: 42, def: 30 }}, enemy_ability: 'Run Away', enemy_tier: 'Common' }},
  inventory: {{
    total_count: 4,
    currencies: [{{ key: 'valuable_comet_shard', label: 'Comet Shard', count: 120, icon_url: '/c.png' }}],
    items: [{{ key: 'berry_oran', label: 'Oran Berry', effect: 'Hunger', count: 4, icon_url: '/b.png', usable: true }}],
  }},
  main: {{ name: 'Pikachu', level: 18, hp: 34, max_hp: 48, xp: 120, xp_next: 250, types: ['electric'], status: 'fighting', show_sprite: true, sprite_url: '/25.gif', flip: false, shake: false, boosts: [] }},
  enemy: {{ name: 'Rattata', level: 14, hp: 12, max_hp: 30, types: ['normal'], status: 'burn', owned: true, shiny: false, show_shiny: true, show_sprite: true, sprite_url: '/19.gif', flip: false, shake: false, boosts: [] }},
}}, overrides);

// 1. Battle mode + custom styling (size, opacity, bg color, no shadow)
window.OnigimonHUD.update(basePayload());
const host = document.getElementById('onigimon-hud-host');
const shell = host.shadowRoot.findAllByClass('oh-shell')[0];
const bar = host.shadowRoot.findAllByClass('oh-bar')[0];
const collapsedPill = host.shadowRoot.findAllByClass('oh-collapsed-pill')[0];
assert.strictEqual(shell.getAttribute('data-mode'), 'battle');
assert.ok(shell.classList.contains('has-no-shadow'));
assert.strictEqual(shell.style.props['--oh-scale'], '1.1');
assert.strictEqual(shell.style.props['--oh-surface'], 'rgba(16, 32, 48, 0.75)');
assert.strictEqual(bar.hidden, false);
assert.strictEqual(collapsedPill.hidden, true, 'collapsed pill must stay hidden when expanded');

// 2. Minimize button hides bar & shows collapsed pill with "Onigimon" (not enemy name), click expands back
const toolBtns = host.shadowRoot.findAllByClass('oh-tool-btn');
const minBtn = toolBtns[toolBtns.length - 1];
minBtn.dispatch('click');
assert.strictEqual(bar.hidden, true, 'minimize button must hide bar');
assert.strictEqual(collapsedPill.hidden, false, 'minimize button must show collapsed pill');
assert.strictEqual(collapsedPill.children[0].textContent, 'Onigimon');
collapsedPill.dispatch('click');
assert.strictEqual(bar.hidden, false, 'clicking collapsed pill restores bar');
assert.strictEqual(collapsedPill.hidden, true);

// 3. Quick Items popover opens, renders items, triggers use_item, and closes on Escape
const inlineBagBtn = host.shadowRoot.findAllByClass('oh-inline-btn')[0];
const bagPanel = host.shadowRoot.findAllByClass('oh-bag-panel')[0];
assert.strictEqual(bagPanel.hidden, true);
inlineBagBtn.dispatch('click');
assert.strictEqual(bagPanel.hidden, false);
const bagItems = host.shadowRoot.findAllByClass('oh-bag-item');
assert.strictEqual(bagItems.length, 1);
bagItems[0].dispatch('click');
assert.ok(cmds.includes('onigimon_hud:use_item:berry_oran'));
docListeners.keydown.forEach(fn => fn({{ key: 'Escape', target: bodyEl }}));
assert.strictEqual(bagPanel.hidden, true);

// 4. Minimal mode hides HP numbers & War strip; War mode shows types & War strip; Static sets .is-static
window.OnigimonHUD.update(basePayload({{ style: {{ mode: 'minimal', motion: 'static', scale: 100, opacity: 88, bg_color_light: '#ffffff', bg_color_dark: '#202124', shadow: true, position: null }} }}));
assert.strictEqual(shell.getAttribute('data-mode'), 'minimal');
assert.ok(shell.classList.contains('is-static'));
const hpTexts = host.shadowRoot.findAllByClass('oh-hp-text');
assert.ok(hpTexts.every(el => el.hidden), 'minimal mode hides numeric HP text');
assert.strictEqual(host.shadowRoot.findAllByClass('oh-war-strip')[0].hidden, true);

window.OnigimonHUD.update(basePayload({{ style: {{ mode: 'war', motion: 'animated', scale: 100, opacity: 88, bg_color_light: '#ffffff', bg_color_dark: '#202124', shadow: true, position: null }} }}));
assert.strictEqual(shell.getAttribute('data-mode'), 'war');
assert.ok(!shell.classList.contains('is-static'));
assert.strictEqual(host.shadowRoot.findAllByClass('oh-war-strip')[0].hidden, false, 'war mode shows tactical strip');
assert.ok(host.shadowRoot.findAllByClass('oh-type-chip').length >= 2, 'war mode shows type chips');

// 5. Dragging bar moves HUD and persists position; double-click grip resets position
bar.dispatch('pointerdown', {{ button: 0, pointerId: 1, clientX: 250, clientY: 520, target: bar }});
bar.dispatch('pointermove', {{ pointerId: 1, clientX: 350, clientY: 220 }});
bar.dispatch('pointerup', {{ pointerId: 1, clientX: 350, clientY: 220 }});
assert.ok(shell.classList.contains('is-positioned'));
assert.ok(cmds.some(c => c.startsWith('onigimon_hud:set_position:')), 'drag should persist position');

const grip = host.shadowRoot.findAllByClass('oh-grip')[0];
grip.dispatch('dblclick');
assert.ok(!shell.classList.contains('is-positioned'));
assert.ok(cmds.includes('onigimon_hud:reset_position'));

console.log('JS_HUD_V2_TESTS_OK');
"""
        proc = subprocess.run([node, "-e", harness], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, msg=f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        self.assertIn("JS_HUD_V2_TESTS_OK", proc.stdout)

    def test_settings_preview_painter_renders_modes_and_bag(self):
        node = shutil.which("node") or ("/opt/homebrew/bin/node" if Path("/opt/homebrew/bin/node").exists() else None)
        if not node:
            self.skipTest("node not installed")

        settings_js = ROOT / "web" / "settings.js"
        harness = f"""
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const src = fs.readFileSync({json.dumps(str(settings_js))}, 'utf8');
const start = src.indexOf('PREVIEW_PAINTERS.onigimon_hud = function');
const end = src.indexOf('PREVIEW_PAINTERS.mochi_message = function', start);
assert.ok(start > 0 && end > start, 'Could not locate onigimon_hud preview painter');
const slice = src.slice(start, end);

class ClassList {{
  constructor() {{ this.set = new Set(); }}
  add(...names) {{ names.forEach(n => this.set.add(n)); }}
  remove(...names) {{ names.forEach(n => this.set.delete(n)); }}
  contains(n) {{ return this.set.has(n); }}
  toggle(n, force) {{
    if (force === undefined) {{
      if (this.set.has(n)) {{ this.set.delete(n); return false; }}
      this.set.add(n); return true;
    }}
    if (force) this.set.add(n); else this.set.delete(n);
    return !!force;
  }}
}}

class FakeEl {{
  constructor(tag, cls = '', text = '') {{
    this.tagName = String(tag || 'DIV').toUpperCase();
    this.className = cls;
    this.classList = new ClassList();
    if (cls) cls.split(/\\s+/).forEach(c => c && this.classList.add(c));
    this.children = [];
    this.attrs = {{}};
    this.listeners = {{}};
    this.style = {{ props: {{}}, setProperty(k, v) {{ this.props[k] = String(v); }} }};
    this.textContent = text;
    this._innerHTML = '';
  }}
  set innerHTML(v) {{ this._innerHTML = String(v); if (!v) this.children = []; }}
  get innerHTML() {{ return this._innerHTML; }}
  appendChild(c) {{ this.children.push(c); return c; }}
  setAttribute(k, v) {{ this.attrs[k] = String(v); }}
  getAttribute(k) {{ return this.attrs[k]; }}
  addEventListener(type, fn) {{ (this.listeners[type] = this.listeners[type] || []).push(fn); }}
  dispatch(type, evt) {{ (this.listeners[type] || []).forEach(fn => fn(evt || {{ stopPropagation() {{}} }})); }}
  findAll(cls, acc = []) {{
    if (this.classList.contains(cls)) acc.push(this);
    for (const c of this.children) if (c && c.findAll) c.findAll(cls, acc);
    return acc;
  }}
}}

const PREVIEW_PAINTERS = {{}};
let backdropCalled = 0;
const sandbox = {{
  PREVIEW_PAINTERS,
  REVIEWER_BG_KEYS: {{}},
  CTX: {{ addonBase: '/_addons/1011095603/' }},
  gamesCtx: {{ companionPreview: {{ name: 'Pikachu', level: 22, itemCount: 7, animatedSprites: ['/a.gif'], staticSprites: ['/a.png'] }} }},
  str: (_k, d) => d,
  el: (tag, cls, text) => new FakeEl(tag, cls, text == null ? '' : String(text)),
  rgba: (hex, a) => `rgba(${{hex}},${{a}})`,
  readableTextColor: (hex) => hex === '#ffffff' ? '#000000' : '#ffffff',
  designerBgSourceState: () => ({{ color: '#1b263b', imageName: '', imageFolder: 'reviewer_bg', blur: 0, opacity: 100 }}),
  paintResolvedBackdropState: () => {{ backdropCalled++; }},
  document: {{
    createElement: (tag) => new FakeEl(tag),
    createTextNode: (t) => ({{ textContent: String(t) }}),
  }},
}};
vm.runInNewContext(slice, sandbox);

const stage = new FakeEl('div');
const baseVals = {{
  g_onigimon_reviewer_hud: true,
  g_onigimon_hud_mode: 'battle',
  g_onigimon_hud_motion: 'animated',
  g_onigimon_hud_scale: 115,
  g_onigimon_hud_opacity: 80,
  g_onigimon_hud_bg_color_light: '#ffffff',
  g_onigimon_hud_bg_color_dark: '#18181b',
  g_onigimon_hud_shadow: false,
}};

// Battle mode + bag click
PREVIEW_PAINTERS.onigimon_hud(stage, baseVals, false);
assert.strictEqual(backdropCalled, 1);
const wrap = stage.findAll('osw-onihud-wrap')[0];
assert.strictEqual(wrap.getAttribute('data-mode'), 'battle');
assert.ok(wrap.classList.contains('has-no-shadow'));
assert.strictEqual(wrap.style.props['--oh-p-scale'], '1.15');
const bagBtn = stage.findAll('osw-onihud-bag-btn')[0];
assert.ok(bagBtn, 'battle preview should render allied-side bag button');
bagBtn.dispatch('click');
assert.strictEqual(stage.findAll('osw-onihud-bag-pop').length, 1, 'clicking bag opens preview popover');

// War mode shows war strip + types
PREVIEW_PAINTERS.onigimon_hud(stage, Object.assign({{}}, baseVals, {{ g_onigimon_hud_mode: 'war', g_onigimon_hud_motion: 'static' }}), true);
assert.strictEqual(stage.findAll('osw-onihud-war-strip').length, 1);
assert.ok(stage.findAll('osw-onihud-type').length >= 2);
assert.ok(stage.findAll('osw-onihud-wrap')[0].classList.contains('is-static'));

// Minimal mode hides inline bag & war strip
PREVIEW_PAINTERS.onigimon_hud(stage, Object.assign({{}}, baseVals, {{ g_onigimon_hud_mode: 'minimal' }}), false);
assert.strictEqual(stage.findAll('osw-onihud-bag-btn').length, 0);
assert.strictEqual(stage.findAll('osw-onihud-war-strip').length, 0);

// Proportional opacity: 50% scales border/shadow/surface smoothly; 0% reaches zero
PREVIEW_PAINTERS.onigimon_hud(stage, Object.assign({{}}, baseVals, {{ g_onigimon_hud_opacity: 50, g_onigimon_hud_shadow: true }}), false);
const midWrap = stage.findAll('osw-onihud-wrap')[0];
assert.strictEqual(midWrap.style.props['--oh-p-surface'], 'rgba(#ffffff,0.5)');
assert.strictEqual(midWrap.style.props['--oh-p-bar-border'], 'rgba(17, 24, 39, 0.06)');
assert.ok(midWrap.style.props['--oh-p-shadow'].includes('0.060'));

PREVIEW_PAINTERS.onigimon_hud(stage, Object.assign({{}}, baseVals, {{ g_onigimon_hud_opacity: 0, g_onigimon_hud_shadow: true }}), false);
const zeroWrap = stage.findAll('osw-onihud-wrap')[0];
assert.strictEqual(zeroWrap.style.props['--oh-p-surface'], 'rgba(#ffffff,0)');
assert.strictEqual(zeroWrap.style.props['--oh-p-blur'], 'none');
assert.strictEqual(zeroWrap.style.props['--oh-p-bar-border'], 'rgba(255, 255, 255, 0)');
assert.strictEqual(zeroWrap.style.props['--oh-p-shadow'], 'none');
assert.ok(zeroWrap.classList.contains('has-no-shadow'));

// Disabled shows muted fallback pill
PREVIEW_PAINTERS.onigimon_hud(stage, Object.assign({{}}, baseVals, {{ g_onigimon_reviewer_hud: false }}), false);
assert.strictEqual(stage.findAll('osw-onihud-disabled-pill').length, 1);

console.log('SETTINGS_PREVIEW_OK');
"""
        proc = subprocess.run([node, "-e", harness], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, msg=f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        self.assertIn("SETTINGS_PREVIEW_OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
