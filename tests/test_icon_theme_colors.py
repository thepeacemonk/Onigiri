"""Exercise tint storage and rendered CSS without starting Anki."""
import ast
import base64
import copy
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def load_nodes(filename, names, env):
    tree = ast.parse((ROOT / filename).read_text())
    nodes = [node for node in tree.body if
             isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec"), env)


class IconThemeColorsTests(unittest.TestCase):
    def setUp(self):
        self.saved = {"modern_menu_icon_color_folder": "#94B9C4"}
        self.col = SimpleNamespace(
            get_config=lambda key: self.saved.get(key),
            set_config=lambda key, value: self.saved.__setitem__(key, value),
            conf=self.saved,
        )
        self.env = {"mw": SimpleNamespace(col=self.col), "copy": copy}
        self.conf_env = {
            "get_collection_config": lambda key, default=None: self.saved.get(key, default),
            "effective_night_mode": lambda: True,
        }
        load_nodes("config.py", {"themed_icon_color"}, self.conf_env)
        self.config = SimpleNamespace(**self.conf_env)
        self.env["config"] = SimpleNamespace(get_config=lambda: {})
        load_nodes("settings_web/store.py", {"Store", "_col_get", "_col_set", "MissingBinding"}, self.env)
        load_nodes("settings_web/schema.py",
                   {"_hidden_field", "_color_pair_field", "_icon_tint_fields"}, self.env)
        self.env["tr"] = lambda key, fallback: fallback
        self.fields = self.env["_icon_tint_fields"](
            "modern_menu_icon_color_folder", "sb_icon_color_light", "sb_icon_color_dark")
        self.store = self.make_store()

    def make_store(self):
        store = self.env["Store"]()
        for field in self.fields:
            store.register(field["id"], field.get("bind"), field.get("default"))
        return store

    def test_legacy_color_opens_in_both_independent_slots(self):
        self.assertTrue(self.fields[0]["always_split"])
        self.assertEqual(self.store.read(self.fields[0]["light_field"]), "#94B9C4")
        self.assertEqual(self.store.read(self.fields[0]["dark_field"]), "#94B9C4")
        self.assertEqual(self.config.themed_icon_color("modern_menu_icon_color_folder", True), "#94B9C4")
        self.assertNotIn("modern_menu_icon_color_folder_dark", self.saved)

    def test_light_edit_preserves_old_dark_color_after_reload(self):
        self.store.stage(self.fields[0]["light_field"], "#112233")
        self.assertEqual(self.store.apply_staged(), [])
        reopened = self.make_store()
        self.assertEqual(reopened.read(self.fields[0]["light_field"]), "#112233")
        self.assertEqual(reopened.read(self.fields[0]["dark_field"]), "#94B9C4")
        self.assertEqual(self.config.themed_icon_color("modern_menu_icon_color_folder", False), "#112233")
        self.assertEqual(self.config.themed_icon_color("modern_menu_icon_color_folder", True), "#94B9C4")

    def test_dark_edit_and_inherit_leave_light_unchanged(self):
        dark_id = self.fields[0]["dark_field"]
        for tint in ("#DDEEFF", ""):
            self.store.stage(dark_id, tint)
            self.assertEqual(self.store.apply_staged(), [])
            self.assertEqual(self.make_store().read(dark_id), tint)
            self.assertEqual(self.config.themed_icon_color("modern_menu_icon_color_folder", True), tint)
            self.assertEqual(self.config.themed_icon_color("modern_menu_icon_color_folder", False), "#94B9C4")

    def test_light_edit_keeps_an_explicit_dark_palette_fallback(self):
        self.saved["modern_menu_icon_color_folder_dark"] = ""
        self.store.stage(self.fields[0]["light_field"], "#112233")
        self.assertEqual(self.store.apply_staged(), [])
        self.assertEqual(self.config.themed_icon_color("modern_menu_icon_color_folder", True), "")

    def test_reset_restores_both_palette_fallbacks(self):
        for field in self.fields[1:]:
            self.store.stage(field["id"], field["default"])
        self.assertEqual(self.store.apply_staged(), [])
        for dark in (False, True):
            self.assertEqual(self.config.themed_icon_color("modern_menu_icon_color_folder", dark), "")

    def test_deck_and_collapse_css_use_active_theme(self):
        self.saved.update(modern_menu_icon_color_folder_dark="#DDEEFF",
                          modern_menu_icon_color_collapse_closed="#223344",
                          modern_menu_icon_color_collapse_closed_dark="#CCDDEE")
        env = {"os": os, "base64": base64, "json": json, "mw": SimpleNamespace(col=self.col),
               "config": self.config, "__file__": str(ROOT / "patcher.py"), "_ICON_CSS_URI_CACHE": {}}
        load_nodes("patcher.py", {"generate_icon_css"}, env)
        css = env["generate_icon_css"]("1011095603", {})
        self.assertIn("background-color: #DDEEFF !important", css)
        self.assertIn("a.collapse.state-closed::before { background-color: #CCDDEE !important; }", css)
        self.assertNotIn("background-color: #94B9C4 !important", css)
        self.conf_env["effective_night_mode"] = lambda: False
        css = env["generate_icon_css"]("1011095603", {})
        self.assertIn("background-color: #94B9C4 !important", css)
        self.assertIn("a.collapse.state-closed::before { background-color: #223344 !important; }", css)
        self.assertNotIn("background-color: #DDEEFF !important", css)


if __name__ == "__main__":
    unittest.main()
