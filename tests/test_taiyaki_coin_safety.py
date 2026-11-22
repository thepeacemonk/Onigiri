"""Regressions for Taiyaki Coin persistence, redemption, penalties, and undo safety.

Every write is confined to TemporaryDirectory; no live Anki profile is loaded.
"""

import ast
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, source: Path):
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _extract_nook_manager_class(method_names):
    tree = ast.parse((ROOT / "gamification" / "nook_level.py").read_text(encoding="utf-8"))
    cls = next(
        n for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "NookLevelManager"
    )
    body = [
        n for n in cls.body
        if isinstance(n, ast.FunctionDef) and n.name in method_names
    ]
    helper_names = {"_difficulty_multiplier", "_curve_loss_recovery"}
    helpers = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in helper_names
    ]
    mini = ast.ClassDef(
        name="NookManagerHarness", bases=[], keywords=[], body=body, decorator_list=[]
    )
    mod = ast.Module(
        body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            *helpers,
            mini,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(mod)
    return mod


class TaiyakiCoinSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "addons21" / "1011095603"
        self.files = self.root / "user_files"
        self.files.mkdir(parents=True)
        self.mw = types.SimpleNamespace(
            pm=types.SimpleNamespace(name="Learner", base=self.temp.name),
            col=types.SimpleNamespace(conf={}, sched=None, db=None),
            progress=types.SimpleNamespace(single_shot=lambda *args: None),
            addonManager=types.SimpleNamespace(
                getConfig=lambda _: {}, addonFromModule=lambda _: "1011095603"
            ),
            state="review",
        )
        pkg = types.ModuleType("coin_test_addon")
        pkg.__path__ = [str(ROOT)]
        core_pkg = types.ModuleType("coin_test_addon.core")
        core_pkg.__path__ = [str(ROOT / "core")]
        gam_pkg = types.ModuleType("coin_test_addon.gamification")
        gam_pkg.__path__ = [str(ROOT / "gamification")]
        aqt = types.ModuleType("aqt")
        aqt.mw = self.mw
        aqt.gui_hooks = types.SimpleNamespace(profile_did_open=[])
        self.patches = patch.dict(
            sys.modules,
            {
                "aqt": aqt,
                "coin_test_addon": pkg,
                "coin_test_addon.core": core_pkg,
                "coin_test_addon.gamification": gam_pkg,
            },
        )
        self.patches.start()
        self.addCleanup(self.patches.stop)

        self.storage = _load_module(
            "coin_test_addon.core.safe_storage", ROOT / "core" / "safe_storage.py"
        )
        self.storage.__file__ = str(self.root / "core" / "safe_storage.py")
        self.games = _load_module(
            "coin_test_addon.gamification.gamification",
            ROOT / "gamification" / "gamification.py",
        )
        self.games.__file__ = str(self.root / "gamification" / "gamification.py")

    def write(self, filename: str, data: Any) -> Path:
        path = self.files / filename
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_redeemed_coins_survive_queued_write_restart_and_mirror(self):
        # Seed profile with 0 coins and a legacy security token, plus a queued
        # delayed write (simulating a review answered right before redeeming).
        path = self.write(
            "gamification_Learner.json",
            {
                "restaurant_level": {
                    "taiyaki_coins": 0,
                    "level": 18,
                    "total_xp": 16200,
                    "_security_token": hashlib.sha256(
                        b"0:onigiri_secret_salt_2024"
                    ).hexdigest(),
                }
            },
        )
        manager = self.games.get_gamification_manager()
        manager.update_restaurant_data({"total_xp": 16205}, immediate=False)
        self.assertIsNotNone(self.storage.pending_payload(str(path)))

        # Execute the real _add_taiyaki_coins function from reward_redemption.py.
        tree = ast.parse((ROOT / "gamification" / "reward_redemption.py").read_text(encoding="utf-8"))
        fn = next(
            n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "_add_taiyaki_coins"
        )
        env = {"__package__": "coin_test_addon.gamification"}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "reward_redemption.py", "exec"), env)

        env["_add_taiyaki_coins"](5000)

        # Delayed pre-redemption write must be cleared and unable to overwrite.
        self.storage.flush_pending()

        saved = json.loads(path.read_text(encoding="utf-8"))["restaurant_level"]
        self.assertEqual(saved["taiyaki_coins"], 5000)
        self.assertEqual(saved["total_xp"], 16205)
        self.assertEqual(
            saved["_security_token"],
            hashlib.sha256(b"5000:onigiri_secret_salt_2024").hexdigest(),
        )
        # External mirror must also have the redeemed balance.
        mirror = Path(self.storage._mirror_path_for(str(path)))
        self.assertEqual(
            json.loads(mirror.read_text(encoding="utf-8"))["restaurant_level"]["taiyaki_coins"],
            5000,
        )
        # Re-opening Anki (fresh GamificationData instance) retains 5000 coins.
        reopened = self.games.GamificationData(str(self.root))
        self.assertEqual(reopened.get_restaurant_data()["taiyaki_coins"], 5000)

    def test_malformed_achievements_or_daily_specials_never_zero_coins(self):
        self.write(
            "gamification_Learner.json",
            {
                "achievements": [{"broken": True}],
                "daily_specials": [{"missing_required_fields": True}],
                "restaurant_level": {
                    "taiyaki_coins": 4500,
                    "level": 18,
                    "total_xp": 16200,
                },
            },
        )
        manager = self.games.GamificationData(str(self.root))
        self.assertEqual(manager.get_restaurant_data()["taiyaki_coins"], 4500)
        self.assertEqual(manager.get_restaurant_data()["level"], 18)
        manager.save(immediate=True)
        reopened = self.games.GamificationData(str(self.root))
        self.assertEqual(reopened.get_restaurant_data()["taiyaki_coins"], 4500)

    def test_null_coin_and_xp_fields_do_not_crash_load(self):
        self.write(
            "gamification_Learner.json",
            {
                "restaurant_level": {
                    "taiyaki_coins": None,
                    "level": None,
                    "total_xp": None,
                    "owned_items": None,
                    "daily_special": None,
                }
            },
        )
        manager = self.games.GamificationData(str(self.root))
        data = manager.get_restaurant_data()
        self.assertEqual(data["taiyaki_coins"], 0)
        self.assertEqual(data["level"], 0)
        self.assertEqual(data["owned_items"], ["default"])

    def test_singleton_manager_follows_profile_switch_without_hook(self):
        self.write("gamification_Learner.json", {"restaurant_level": {"taiyaki_coins": 120}})
        self.write("gamification_Other.json", {"restaurant_level": {"taiyaki_coins": 4200}})
        self.mw.pm.name = "Learner"
        first = self.games.get_gamification_manager()
        self.assertEqual(first.get_restaurant_data()["taiyaki_coins"], 120)

        # Simulate profile change without firing profile_did_open hook.
        self.mw.pm.name = "Other"
        second = self.games.get_gamification_manager()
        self.assertEqual(second.get_restaurant_data()["taiyaki_coins"], 4200)
        second.update_restaurant_data({"taiyaki_coins": 4300}, immediate=True)
        self.assertEqual(
            json.loads((self.files / "gamification_Learner.json").read_text(encoding="utf-8"))[
                "restaurant_level"
            ]["taiyaki_coins"],
            120,
        )

    def test_failed_immediate_save_queues_retry_instead_of_dropping_coins(self):
        path = self.files / "gamification_Learner.json"
        manager = self.games.GamificationData(str(self.root))
        with patch.object(self.storage.os, "replace", side_effect=OSError("locked")):
            manager.update_restaurant_data({"taiyaki_coins": 5000}, immediate=True)
        # Failed immediate write must be queued for retry.
        self.assertEqual(
            self.storage.pending_payload(str(path))["restaurant_level"]["taiyaki_coins"],
            5000,
        )
        self.assertTrue(self.storage.flush_pending())
        self.assertEqual(
            json.loads(path.read_text(encoding="utf-8"))["restaurant_level"]["taiyaki_coins"],
            5000,
        )

    def test_pending_write_key_normalizes_equivalent_paths(self):
        path = str(self.files / "gamification_Learner.json")
        alt_path = str(self.files / "." / "gamification_Learner.json")
        self.storage.schedule_write_json(path, {"coins": 0})
        self.storage.atomic_write_json(alt_path, {"coins": 5000})
        self.storage.flush_pending()
        self.assertEqual(json.loads(Path(path).read_text(encoding="utf-8")), {"coins": 5000})

    def test_missed_rush_penalty_never_goes_negative_and_never_double_fires(self):
        cfg = {
            "restaurant_level": {"enabled": True, "difficulty": "Legend"},
            "daily_special": {"enabled": True, "target": 50},
        }
        state = {
            "total_xp": 50 * 4 * 5 ** 2,
            "level": 5,
            "taiyaki_coins": 20,
            "migrated": True,
            "xp_multiplier": 4,
            "daily_special": {
                "enabled": True,
                "target": 50,
                "current_progress": 10,
                "completed": False,
                "last_updated": "2026-11-20",
            },
        }
        # Simulate Anki day = 2026-11-21 with 15 reviews already synced today,
        # and only 10 reviews yesterday (missed yesterday's target of 50).
        day_cutoff = int(datetime(2026, 11, 22, 4, 0, 0).timestamp())
        today_start = day_cutoff - 86400

        def scalar(query, *args):
            if "id < ?" in query:
                return 10  # yesterday's reviews (< 50)
            return 15  # today's reviews (> 0, triggers _sync -> _add_xp!)

        self.mw.col = types.SimpleNamespace(
            conf={},
            sched=types.SimpleNamespace(day_cutoff=day_cutoff),
            db=types.SimpleNamespace(scalar=scalar),
        )

        mod = _extract_nook_manager_class(
            {
                "get_progress",
                "get_daily_special_status",
                "_was_day_completed_in_db",
                "_apply_recipe_rush_missed_penalty",
                "_check_and_reset_daily_special",
                "_sync_daily_progress_with_db",
                "_update_recipe_rush_stage",
                "_recipe_rush_stage",
                "_total_xp_for_level",
                "_xp_for_next",
                "_collapse_xp",
                "_ensure_progression_curve",
                "_add_xp",
                "_get_anki_today_date",
                "_apply_recipe_rush_ticket_data",
            }
        )
        env = {
            "config": types.SimpleNamespace(
                get_config=lambda: cfg, get_config_readonly=lambda: cfg
            ),
            "mw": self.mw,
            "datetime": datetime,
            "time": __import__("time"),
            "random": __import__("random"),
            "tr": lambda key, fallback="": fallback,
            "XP_PER_REVIEW": 5,
            "LevelProgress": lambda **kw: types.SimpleNamespace(**kw),
            "Any": Any,
            "Dict": Dict,
            "List": List,
            "Optional": Optional,
            "Tuple": Tuple,
        }
        exec(compile(mod, "nook_level.py", "exec"), env)
        mgr = env["NookManagerHarness"]()
        mgr._last_daily_sync_time = 0
        mgr._cached_daily_count = -1
        mgr._addon_prefix = "/addon"
        mgr._get_gamification_state = lambda: state
        mgr._get_coins_from_json = lambda: int(state.get("taiyaki_coins") or 0)
        mgr._get_difficulty_multiplier = lambda: 4
        mgr._restaurant_conf_readonly = lambda: cfg["restaurant_level"]
        mgr._config_bundle = lambda: (cfg, cfg["restaurant_level"])
        mgr._gamification_manager = types.SimpleNamespace(progression_backups=lambda: iter(()))
        mgr._dispatch_notifications = lambda *_: None
        mgr._get_daily_special_data = lambda: None
        mgr.get_current_theme_id = lambda: "default"
        mgr._create_level_up_notification = lambda _: []
        mgr._handle_daily_special_completion = lambda _: []

        def update_data(changes, immediate=False):
            for k, v in changes.items():
                if k == "daily_special_update":
                    state["daily_special"].update(v)
                else:
                    state[k] = v

        mgr._update_gamification_data = update_data
        mgr._update_gamification_daily_special = lambda ds: state["daily_special"].update(ds)

        mgr.get_daily_special_status()

        # Penalty must clamp coins to 0 (never -55) and apply ONLY ONCE
        # (level 5 - 2 = 3, NOT 5 - 4 = 1 from double penalty!).
        self.assertEqual(state["taiyaki_coins"], 0)
        self.assertEqual(state["level"], 3)

    def test_missed_rush_skips_penalty_when_revlog_proves_mobile_completion(self):
        cfg = {
            "restaurant_level": {"enabled": True, "difficulty": "Legend"},
            "daily_special": {"enabled": True, "target": 50},
        }
        state = {
            "total_xp": 50 * 4 * 5 ** 2,
            "level": 5,
            "taiyaki_coins": 200,
            "migrated": True,
            "xp_multiplier": 4,
            "daily_special": {
                "enabled": True,
                "target": 50,
                "current_progress": 0,
                "completed": False,
                "last_updated": "2026-11-20",
            },
        }
        day_cutoff = int(datetime(2026, 11, 22, 4, 0, 0).timestamp())
        self.mw.col = types.SimpleNamespace(
            conf={},
            sched=types.SimpleNamespace(day_cutoff=day_cutoff),
            db=types.SimpleNamespace(scalar=lambda query, *args: 65 if "id < ?" in query else 0),
        )
        mod = _extract_nook_manager_class(
            {"_was_day_completed_in_db", "_apply_recipe_rush_missed_penalty"}
        )
        env = {
            "mw": self.mw,
            "datetime": datetime,
            "tr": lambda key, fallback="": fallback,
            "Any": Any,
            "Dict": Dict,
            "List": List,
        }
        exec(compile(mod, "nook_level.py", "exec"), env)
        mgr = env["NookManagerHarness"]()
        mgr._config_bundle = lambda: (cfg, cfg["restaurant_level"])
        mgr._update_gamification_data = lambda *args, **kw: self.fail("Should not penalize completed day")

        notifs = mgr._apply_recipe_rush_missed_penalty(state["daily_special"])
        self.assertEqual(notifs, [])
        self.assertTrue(state["daily_special"]["completed"])
        self.assertEqual(state["taiyaki_coins"], 200)

    def test_undo_level_down_never_drives_coins_negative_and_ignores_non_review_undo(self):
        cfg = {"restaurant_level": {"enabled": True}, "daily_special": {"enabled": False}}
        state = {
            "total_xp": 200,
            "level": 1,
            "taiyaki_coins": 0,  # User spent their coins already.
            "migrated": True,
            "xp_multiplier": 4,
        }
        mod = _extract_nook_manager_class(
            {"get_progress", "_ensure_progression_curve", "_collapse_xp", "_add_xp", "_xp_for_next", "on_state_did_undo"}
        )
        env = {
            "config": types.SimpleNamespace(get_config_readonly=lambda: cfg),
            "tr": lambda key, fallback="": fallback,
            "XP_PER_REVIEW": 5,
            "LevelProgress": lambda **kw: types.SimpleNamespace(**kw),
            "Any": Any,
            "Dict": Dict,
            "List": List,
            "Tuple": Tuple,
        }
        exec(compile(mod, "nook_level.py", "exec"), env)
        mgr = env["NookManagerHarness"]()
        mgr._xp_history = [5]
        mgr._addon_prefix = "/addon"
        mgr._get_gamification_state = lambda: state
        mgr._update_gamification_data = lambda changes, immediate=False: state.update(changes)
        mgr._get_difficulty_multiplier = lambda: 4
        mgr._get_coins_from_json = lambda: int(state.get("taiyaki_coins") or 0)
        mgr._restaurant_conf_readonly = lambda: cfg["restaurant_level"]
        mgr._gamification_manager = types.SimpleNamespace(progression_backups=lambda: iter(()))
        mgr._create_level_up_notification = lambda _: []
        mgr._dispatch_notifications = lambda *_: None
        mgr.add_review_xp = lambda xp, count=1: mgr._add_xp(xp, reason="review", review_count=count)

        # Non-review undo (e.g. undoing a flag/note edit) must be ignored.
        mgr.on_state_did_undo(types.SimpleNamespace(study_queues=False))
        self.assertEqual(mgr._xp_history, [5])
        self.assertEqual(state["total_xp"], 200)

        # Real review undo drops level 1 -> 0, but coins stay clamped at 0.
        mgr.on_state_did_undo(types.SimpleNamespace(study_queues=True))
        self.assertEqual(state["level"], 0)
        self.assertEqual(state["taiyaki_coins"], 0)

    def test_store_redeem_modal_exposes_lost_coins_contact_note(self):
        html_source = (
            ROOT / "web" / "gamification" / "mr_taiyaki_store" / "mr_taiyaki_store.html"
        ).read_text(encoding="utf-8")
        self.assertIn('data-i18n-text="store_lost_coins_note"', html_source)
        self.assertIn("mailto:peacemonk.apps@gmail.com", html_source)

        ui_source = (ROOT / "gamification" / "nook_web_ui.py").read_text(encoding="utf-8")
        self.assertIn('"store_lost_coins_note"', ui_source)


if __name__ == "__main__":
    unittest.main()
