import ast
import os
import re
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


ADDON_ROOT = Path(__file__).resolve().parents[1]


def _load_function(rel_path: str, func_name: str, extra_globals=None, future_annotations: bool = False):
    source = (ADDON_ROOT / rel_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == func_name
    )
    body = []
    if future_annotations:
        body.append(
            ast.ImportFrom(
                module="__future__",
                names=[ast.alias(name="annotations", asname=None)],
                level=0,
            )
        )
    body.append(fn)
    module = ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))
    ns = dict(extra_globals or {})
    exec(compile(module, rel_path, "exec"), ns)
    return ns[func_name]


def _load_method(rel_path: str, class_name: str, method_name: str, extra_globals=None):
    source = (ADDON_ROOT / rel_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    fn = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )
    module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    ns = dict(extra_globals or {})
    exec(compile(module, rel_path, "exec"), ns)
    return ns[method_name]


class P1And364FixesTests(unittest.TestCase):
    # ── #364: Pomodoro session history UTC -> local time ───────────────────────
    def test_364_pomodoro_history_converts_utc_to_local_time(self):
        history_row_text = _load_method(
            "study_tools/pomodoro.py",
            "PomodoroStatsDialog",
            "_history_row_text",
            {"datetime": datetime, "tr": lambda _k, default="": default},
        )
        utc_iso = "2026-03-10T15:30:00+00:00"
        expected_local = (
            datetime.fromisoformat(utc_iso).astimezone().strftime("%b %d, %H:%M")
        )
        row_offset = history_row_text(
            None, {"started_at": utc_iso, "actual_minutes": 25}
        )
        row_z = history_row_text(
            None, {"started_at": "2026-03-10T15:30:00Z", "actual_minutes": 25}
        )
        self.assertIn(expected_local, row_offset)
        self.assertIn(expected_local, row_z)
        self.assertIn("25 min", row_offset)

    # ── #357: Focus Dango exit attempts unlock cleanly on 3rd attempt ──────────
    def test_357_focus_dango_light_mode_unlocks_and_suspends_reinterception(self):
        source = (ADDON_ROOT / "gamification/focus_dango.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        wanted = {"_resume_navigation", "_should_allow_light_mode_exit", "intercept_exit_attempt"}
        nodes = [
            n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name in wanted
        ]
        scheduled = []

        class FakeQTimer:
            @staticmethod
            def singleShot(_ms, cb):
                scheduled.append(cb)

        ns = {
            "_exit_attempt_count": 0,
            "_LIGHT_MODE_ATTEMPTS_TO_UNLOCK": 3,
            "_navigation_is_suspended": False,
            "_dialog_is_showing": False,
            "QtCore": SimpleNamespace(QTimer=FakeQTimer),
            "mw": SimpleNamespace(state="review"),
            "is_focus_dango_enabled": lambda: True,
            "is_self_sabotage_enabled": lambda: False,
        }
        mod = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
        exec(compile(mod, "gamification/focus_dango.py", "exec"), ns)

        intercept = ns["intercept_exit_attempt"]
        # Attempts 1 and 2 are blocked; attempt 3 unlocks
        self.assertTrue(intercept("onigiri_go_home"))
        self.assertTrue(intercept("onigiri_go_home"))
        self.assertFalse(intercept("onigiri_go_home"))
        # Immediately following wrapped call during the same tick is NOT re-blocked
        self.assertTrue(ns["_navigation_is_suspended"])
        self.assertFalse(intercept("onigiri_go_home"))
        # Once the QTimer(0) callback fires, protection resumes cleanly
        self.assertEqual(len(scheduled), 1)
        scheduled[0]()
        self.assertFalse(ns["_navigation_is_suspended"])
        self.assertTrue(intercept("onigiri_go_home"))

    def test_357_patcher_has_single_reviewer_focus_dango_intercept(self):
        patcher_src = (ADDON_ROOT / "rendering/patcher.py").read_text(encoding="utf-8")
        occurrences = re.findall(
            r"focus_dango\.intercept_exit_attempt\(", patcher_src
        )
        self.assertEqual(len(occurrences), 1)

    # ── #394: Learning cards popup / stats include subdecks ────────────────────
    def test_394_selected_deck_ids_includes_subdecks_via_decks_children(self):
        fake_col = SimpleNamespace(
            decks=SimpleNamespace(
                current=lambda: {"id": 10},
                children=lambda did: [("Parent::ChildA", 11), ("Parent::ChildB", 12)]
                if did == 10
                else [],
            )
        )
        from typing import Any, List

        for rel_path in ("rendering/patcher.py", "rendering/overview_stats.py"):
            fn = _load_function(
                rel_path, "_selected_deck_ids", {"Any": Any, "List": List}
            )
            self.assertEqual(fn(fake_col), [10, 11, 12], f"Failed for {rel_path}")

    # ── #406: Ready-to-Go Inbox respects daily scheduled new-card limits ───────
    def test_406_inbox_respects_daily_new_limit_and_skips_internal_decks(self):
        is_internal = lambda name: str(name).startswith("Onigiri::Ready")
        spec_fn = _load_function(
            "study_tools/ready_to_go.py",
            "_scheduled_new_inbox_spec",
            {"is_internal_deck_name": is_internal, "Any": object},
            future_annotations=True,
        )

        # Case 1: Mixed decks, subdecks, 0-limit decks, and internal deck
        tree = SimpleNamespace(
            children=[
                SimpleNamespace(
                    name="Japanese",
                    new_count=20,
                    children=[
                        SimpleNamespace(name="Kanji", new_count=12, children=[]),
                        SimpleNamespace(name="Vocab", new_count=8, children=[]),
                        SimpleNamespace(name="Paused", new_count=0, children=[]),
                    ],
                ),
                SimpleNamespace(name="Medicine", new_count=0, children=[]),
                SimpleNamespace(name="Onigiri::Ready::Inbox", new_count=99, children=[]),
            ]
        )
        col = SimpleNamespace(sched=SimpleNamespace(deck_due_tree=lambda: tree))
        query, limit = spec_fn(col)
        self.assertEqual(limit, 20)
        self.assertIn('deck:"Japanese::Kanji"', query)
        self.assertIn('deck:"Japanese::Vocab"', query)
        self.assertNotIn("Paused", query)
        self.assertNotIn("Medicine", query)
        self.assertNotIn("Onigiri::Ready", query)

        # Case 2: Parent with direct new cards + a zero-new subdeck
        tree_direct = SimpleNamespace(
            children=[
                SimpleNamespace(
                    name="Biology",
                    new_count=15,
                    children=[
                        SimpleNamespace(name="Cells", new_count=5, children=[]),
                        SimpleNamespace(name="Archive", new_count=0, children=[]),
                    ],
                )
            ]
        )
        col_direct = SimpleNamespace(sched=SimpleNamespace(deck_due_tree=lambda: tree_direct))
        q_direct, lim_direct = spec_fn(col_direct)
        self.assertEqual(lim_direct, 15)
        self.assertIn('deck:"Biology"', q_direct)
        self.assertIn('-deck:"Biology::Archive"', q_direct)

        # Case 3: 0 new cards scheduled across all decks
        tree_empty = SimpleNamespace(
            children=[SimpleNamespace(name="DeckA", new_count=0, children=[])]
        )
        col_empty = SimpleNamespace(sched=SimpleNamespace(deck_due_tree=lambda: tree_empty))
        self.assertEqual(spec_fn(col_empty), ("", 0))

    # ── #356: Pomodoro presets apply immediately + macOS sound fallback ────────
    def test_356_pomodoro_apply_settings_updates_idle_timer_and_preserves_running(self):
        apply_settings = _load_method(
            "study_tools/pomodoro.py", "PomodoroTimer", "apply_settings"
        )
        phase_len = _load_method(
            "study_tools/pomodoro.py", "PomodoroTimer", "phase_length_seconds"
        )

        tick = Mock()
        timer = SimpleNamespace(
            session_type="focus",
            settings={"focus_minutes": 25, "short_break_minutes": 5, "long_break_minutes": 15},
            running=False,
            _phase_started_at=None,
            remaining_seconds=25 * 60,
            tick=tick,
        )
        timer.phase_length_seconds = lambda: phase_len(timer)

        # Applying Deep Focus (50/10/20) while idle updates remaining_seconds
        apply_settings(
            timer,
            {"focus_minutes": 50, "short_break_minutes": 10, "long_break_minutes": 20},
        )
        self.assertEqual(timer.remaining_seconds, 50 * 60)
        tick.emit.assert_called_once()

        # Applying Quick Sprint (15/3/10) while running preserves active countdown
        timer.running = True
        timer.remaining_seconds = 1234
        apply_settings(
            timer,
            {"focus_minutes": 15, "short_break_minutes": 3, "long_break_minutes": 10},
        )
        self.assertEqual(timer.remaining_seconds, 1234)
        self.assertEqual(tick.emit.call_count, 2)

    def test_356_play_tone_fallback_uses_play_file_and_settings_preview_uses_live_vals(self):
        play_file = Mock()
        fake_sound_mod = types.ModuleType("aqt.sound")
        fake_sound_mod.av_player = SimpleNamespace(play_file=play_file)
        fake_aqt = types.ModuleType("aqt")
        fake_aqt.sound = fake_sound_mod

        fallback_fn = _load_function(
            "study_tools/pomodoro.py", "_play_tone_fallback", {"os": os}
        )
        with patch.dict(sys.modules, {"aqt": fake_aqt, "aqt.sound": fake_sound_mod}):
            fallback_fn("/tmp/test_tone.mp3")
        play_file.assert_called_once_with(os.path.abspath("/tmp/test_tone.mp3"))

        settings_js = (ADDON_ROOT / "web/settings.js").read_text(encoding="utf-8")
        self.assertIn('vals["pomodoro_focus"]', settings_js)
        self.assertIn('vals["pomodoro_cycle"]', settings_js)

        side_effects_src = (ADDON_ROOT / "settings_web/side_effects.py").read_text(encoding="utf-8")
        self.assertIn("pomodoro.get_timer().apply_settings(settings)", side_effects_src)

    # ── #383: Simple <-> Advanced switch does not erase Profile/Sync values ────
    def test_383_simple_mode_defaults_do_not_overwrite_saved_values(self):
        settings_js = (ADDON_ROOT / "web/settings.js").read_text(encoding="utf-8")
        profile_match = re.search(
            r"function applySimpleProfileDefaults\s*\(\)\s*\{([^}]*)\}",
            settings_js,
        )
        sync_match = re.search(
            r"function applySimpleSyncDefaults\s*\(\)\s*\{([^}]*)\}",
            settings_js,
        )
        self.assertIsNotNone(profile_match)
        self.assertIsNotNone(sync_match)
        self.assertNotIn("setValue(", profile_match.group(1))
        self.assertNotIn("setValue(", sync_match.group(1))

    # ── #386: URL encoding for profile pictures & custom backgrounds ───────────
    def test_386_addon_media_url_and_addon_uri_encode_special_filenames(self):
        media_url = _load_function("rendering/patcher.py", "_addon_media_url")
        self.assertEqual(
            media_url("1011095603", "profile", "my avatar #1 (2026)'s.png"),
            "/_addons/1011095603/user_files/profile/my%20avatar%20%231%20%282026%29%27s.png",
        )
        self.assertEqual(
            media_url("1011095603", "", r"main_bg\summer 100%.jpg"),
            "/_addons/1011095603/user_files/main_bg/summer%20100%25.jpg",
        )

        addon_uri = _load_function(
            "settings_web/render.py",
            "addon_uri",
            {"addon_package": lambda: "1011095603"},
        )
        self.assertEqual(
            addon_uri("user_files/profile/my pic #2.png"),
            "/_addons/1011095603/user_files/profile/my%20pic%20%232.png",
        )
        self.assertEqual(addon_uri(""), "/_addons/1011095603/")


if __name__ == "__main__":
    unittest.main()
