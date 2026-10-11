"""Check package moves without opening Anki or writing to real profile data."""

import ast
import importlib
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def fixture_package(path):
    package = types.ModuleType("organization_fixture")
    package.__path__ = [str(path)]
    return package


class FileOrganizationTests(unittest.TestCase):
    def test_relative_imports_resolve_after_moves(self):
        for source in ROOT.rglob("*.py"):
            relative = source.relative_to(ROOT)
            if relative.parts[0] == "tests":
                continue
            package = list(relative.parent.parts)
            for node in ast.walk(ast.parse(source.read_text())):
                if not isinstance(node, ast.ImportFrom) or not node.level:
                    continue
                with self.subTest(file=str(relative), line=node.lineno):
                    self.assertLessEqual(node.level, len(package) + 1)
                    parts = package[:len(package) - node.level + 1]
                    if node.module:
                        parts += node.module.split(".")
                    target = ROOT.joinpath(*parts)
                    self.assertTrue(target.is_dir() or target.with_suffix(".py").is_file(),
                                    ast.unparse(node))

    def test_pure_helpers_do_not_load_anki_or_qt(self):
        with patch.dict(sys.modules, {"organization_fixture": fixture_package(ROOT),
                                      "aqt": None, "PyQt6": None}):
            emoji = importlib.import_module("organization_fixture.ui_kit.emoji_sprites")
            math = importlib.import_module("organization_fixture.study_tools.prep_station_math")
            self.assertEqual(emoji.asset_for_emoji("🍙"), "onigiri.svg")
            self.assertTrue(callable(math.calculate_plan_projection))
            self.assertNotIn("organization_fixture.ui_kit.flow_layout", sys.modules)

    def test_storage_sync_and_sidebar_keep_root_data_and_shared_modules(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "addons21" / "onigiri"
            root.mkdir(parents=True)
            for name in ("core", "api"):
                shutil.copytree(ROOT / name, root / name)
            shutil.copy(ROOT / "sidebar_api.py", root / "sidebar_api.py")
            mw = types.SimpleNamespace(
                pm=types.SimpleNamespace(name="Organization", base=folder),
                col=types.SimpleNamespace(conf={}),
                addonManager=types.SimpleNamespace(
                    getConfig=lambda _: {}, addonFromModule=lambda _: "onigiri"),
            )
            aqt = types.ModuleType("aqt")
            aqt.mw = mw
            aqt.gui_hooks = types.SimpleNamespace(
                top_toolbar_did_init_links=[], webview_did_receive_js_message=[])
            with patch.dict(sys.modules, {"organization_fixture": fixture_package(root),
                                          "aqt": aqt}):
                storage = importlib.import_module("organization_fixture.core.safe_storage")
                config = importlib.import_module("organization_fixture.core.config")
                sync = importlib.import_module("organization_fixture.core.sync")
                sidebar = importlib.import_module("organization_fixture.api.sidebar")
                legacy = importlib.import_module("organization_fixture.sidebar_api")
                self.assertIs(config.safe_storage, storage)
                self.assertIs(sync.config, config)
                self.assertIs(sidebar.config, config)
                self.assertIs(legacy.register_sidebar_action, sidebar.register_sidebar_action)
                self.assertEqual(len(aqt.gui_hooks.top_toolbar_did_init_links), 1)
                self.assertEqual(Path(storage.addon_root()), root)
                self.assertEqual(Path(storage.user_files_dir()), root / "user_files")
                settings_path = root / "user_files" / "settings_Organization.json"
                self.assertEqual(Path(config._get_settings_path()), settings_path)
                config.write_config({"userName": "Saved learner"})
                self.assertEqual(json.loads(settings_path.read_text())["userName"], "Saved learner")
                self.assertEqual(Path(sync.onigiri_sync._user_files_dir), root / "user_files")
                self.assertFalse((root / "core" / "user_files").exists())


if __name__ == "__main__":
    unittest.main()
