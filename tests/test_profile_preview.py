import ast
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_context():
    tree = ast.parse((ROOT / "settings_web/render.py").read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == "profile_level_context")
    namespace = {"__package__": "profile_fixture.settings_web"}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "render.py", "exec"), namespace)
    return namespace["profile_level_context"]


class ProfilePreviewTests(unittest.TestCase):
    def test_context_uses_live_renderer_and_selected_source(self):
        context = load_context()
        root = types.ModuleType("profile_fixture")
        renderer = types.ModuleType("profile_fixture.onigiri_renderer")
        root.onigiri_renderer = renderer
        with patch.dict(sys.modules, {"profile_fixture": root,
                                      "profile_fixture.onigiri_renderer": renderer}):
            for game, name in (("nook", "Nook"), ("onigimon", "Onigimon XP"),
                               ("hexagon", "Hexagon Land")):
                with self.subTest(game=game):
                    renderer._selected_profile_level_game = lambda: game
                    renderer._profile_level_source_name = lambda selected: name
                    renderer._profile_level_progress = lambda: (True, 7, 0.42, "#819b26")
                    self.assertEqual(context(), dict(enabled=True, level=7, fraction=0.42,
                                                     color="#819b26", game=game, sourceName=name))
            renderer._profile_level_progress = lambda: (False, 0, 0.0, "")
            self.assertFalse(context()["enabled"])
            self.assertEqual(context()["fraction"], 0.0)
            renderer._profile_level_progress = lambda: (True, 0, 0.0, "#819b26")
            self.assertEqual(context()["level"], 0)
            self.assertEqual(context()["fraction"], 0.0)

    def test_unavailable_renderer_never_fabricates_progress(self):
        self.assertEqual(load_context()(), dict(enabled=False, level=0, fraction=0.0, color=""))

    def test_source_save_returns_fresh_context_and_refreshes_live_profile(self):
        tree = ast.parse((ROOT / "settings_web/dialog.py").read_text())
        dialog = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SettingsWebDialog")
        method = next(n for n in dialog.body if isinstance(n, ast.FunctionDef) and n.name == "_cmd_patch")
        state = {"game": "nook"}
        refresh_calls = []
        refresh = types.ModuleType("profile_fixture.refresh")
        refresh.schedule_ui_refresh = refresh_calls.append
        def save(values):
            state["game"] = values["g_profile_level_game"]
            return set(values), []
        namespace = {
            "__package__": "profile_fixture.settings_web", "json": json,
            "side_effects": types.SimpleNamespace(run=lambda hooks, store: []),
            "render": types.SimpleNamespace(profile_preview_context=lambda: {"profileLevel": dict(state)}),
        }
        exec(compile(ast.Module(body=[method], type_ignores=[]), "dialog.py", "exec"), namespace)
        fixture = types.SimpleNamespace(store=types.SimpleNamespace(apply_now=save),
                                        _hooks_for=lambda touched: [], _schedule_refresh=lambda: None)
        with patch.dict(sys.modules, {"profile_fixture": types.ModuleType("profile_fixture"),
                                      "profile_fixture.refresh": refresh}):
            result = namespace["_cmd_patch"](fixture, json.dumps({"g_profile_level_game": "hexagon"}))
        self.assertTrue(result["ok"])
        self.assertEqual(result["profilePreview"]["profileLevel"]["game"], "hexagon")
        self.assertEqual(refresh_calls, [0])


if __name__ == "__main__":
    unittest.main()
