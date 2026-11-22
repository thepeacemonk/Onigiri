import ast
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


ADDON_ROOT = Path(__file__).resolve().parents[1]


def _load_functions(rel_path: str, names, extra_globals=None):
    source = (ADDON_ROOT / rel_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    selected = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    ns = dict(extra_globals or {})
    exec(compile(module, rel_path, "exec"), ns)
    return ns


class PerformanceOptimizationsTests(unittest.TestCase):
    def test_config_stat_ttl_avoids_repeated_stat_calls(self):
        stat_calls = []

        def fake_cache_key():
            stat_calls.append(1)
            return ("/tmp/settings.json", 1, 10)

        build_calls = []

        def fake_build():
            build_calls.append(1)
            return {"ok": True}

        now_val = [100.0]
        fake_time = SimpleNamespace(monotonic=lambda: now_val[0])

        ns = _load_functions(
            "core/config.py",
            {"_cached_config", "invalidate_config_cache"},
            {
                "time": fake_time,
                "_CONFIG_CACHE": None,
                "_CONFIG_CACHE_KEY": None,
                "_CONFIG_STAT_CHECKED_AT": 0.0,
                "_CONFIG_STAT_TTL": 0.25,
                "_config_cache_key": fake_cache_key,
                "_build_config": fake_build,
            },
        )

        # First call stats and builds once
        ns["_cached_config"]()
        self.assertEqual(len(stat_calls), 1)
        self.assertEqual(len(build_calls), 1)

        # Rapid subsequent calls within TTL do 0 stat calls
        for _ in range(50):
            now_val[0] += 0.001
            ns["_cached_config"]()
        self.assertEqual(len(stat_calls), 1)
        self.assertEqual(len(build_calls), 1)

        # After TTL expires, stat runs again (no rebuild since key unchanged)
        now_val[0] += 0.30
        ns["_cached_config"]()
        self.assertEqual(len(stat_calls), 2)
        self.assertEqual(len(build_calls), 1)

        # Explicit invalidation forces immediate re-stat and rebuild
        ns["invalidate_config_cache"]()
        ns["_cached_config"]()
        self.assertEqual(len(stat_calls), 3)
        self.assertEqual(len(build_calls), 2)

    def test_read_cached_text_file_caches_until_mtime_changes(self):
        ns = _load_functions(
            "rendering/patcher.py",
            {"_read_cached_text_file"},
            {"os": os, "_CACHED_TEXT_FILES": {}},
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tf:
            tf.write("body { color: red; }")
            path = tf.name
        try:
            self.assertEqual(ns["_read_cached_text_file"](path), "body { color: red; }")
            with patch("builtins.open", side_effect=AssertionError("should hit cache")):
                self.assertEqual(ns["_read_cached_text_file"](path), "body { color: red; }")
        finally:
            os.unlink(path)

    def test_update_reviewer_chip_skips_redundant_eval(self):
        import json

        fake_web = SimpleNamespace(eval=Mock())
        fake_mw = SimpleNamespace(state="review", reviewer=SimpleNamespace(web=fake_web))
        chip_value = ["<span>Lv 5</span>"]

        ns = _load_functions(
            "rendering/patcher.py",
            {"update_reviewer_chip"},
            {
                "mw": fake_mw,
                "json": json,
                "_last_reviewer_chip_html": None,
                "_get_reviewer_nook_level_chip_html": lambda: chip_value[0],
            },
        )

        # First call pushes JS
        ns["update_reviewer_chip"]()
        self.assertEqual(fake_web.eval.call_count, 1)

        # Identical chip skips JS eval completely
        ns["update_reviewer_chip"]()
        self.assertEqual(fake_web.eval.call_count, 1)

        # Changed chip pushes JS once
        chip_value[0] = "<span>Lv 6</span>"
        ns["update_reviewer_chip"]()
        self.assertEqual(fake_web.eval.call_count, 2)

    def test_hexagon_land_uses_scheduled_writes_and_readonly_config(self):
        src = (ADDON_ROOT / "gamification" / "hexagon_land.py").read_text(encoding="utf-8")
        self.assertIn("safe_storage.schedule_write_json(path, payload)", src)
        self.assertIn("def _load_live(self)", src)
        self.assertIn("state = self._load_live()", src)
        self.assertNotIn("conf = config.get_config()\n        return bool(self.config()", src)

    def test_performance_settings_removed(self):
        schema_src = (ADDON_ROOT / "settings_web" / "schema.py").read_text(encoding="utf-8")
        self.assertNotIn("def _performance_page", schema_src)
        config_src = (ADDON_ROOT / "core" / "config.py").read_text(encoding="utf-8")
        self.assertNotIn("performanceMode", config_src)
        self.assertFalse((ADDON_ROOT / "core" / "performance.py").exists())


if __name__ == "__main__":
    unittest.main()
