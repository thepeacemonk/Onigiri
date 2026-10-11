"""Font color binding and live CSS behavior, without loading an Anki profile."""
import ast
import os
import re
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_functions(file, names, env):
    tree = ast.parse((ROOT / file).read_text())
    body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(ast.Module(body=body, type_ignores=[]), file, "exec"), env)


class FontColorTests(unittest.TestCase):
    def schema_env(self):
        env = {"tr": lambda key, fallback: fallback,
               "_font_options": lambda: [{"value": "system", "label": "Poppins"}]}
        load_functions("settings_web/schema.py", {"_attach_font_colors", "iter_fields", "_hidden_field"}, env)
        return env

    def test_every_declared_font_has_registered_color_bindings(self):
        tree = ast.parse((ROOT / "settings_web/schema.py").read_text())
        ids = set()
        for file in ("settings_web/schema.py", "settings_web/games.py"):
            for node in ast.walk(ast.parse((ROOT / file).read_text())):
                if not isinstance(node, ast.Dict):
                    continue
                pairs = {key.value: val for key, val in zip(node.keys, node.values)
                         if isinstance(key, ast.Constant)}
                if isinstance(pairs.get("type"), ast.Constant) and pairs["type"].value == "font":
                    if isinstance(pairs.get("id"), ast.Constant):
                        ids.add(pairs["id"].value)
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ADVANCED_FONT_ROLES" for t in node.targets):
                ids.update("onigiri_font_" + spec[0] for spec in ast.literal_eval(node.value))
        existing = ["g_mochi_text_color"] + [prefix + "_" + mode
                    for prefix in ("modern_menu_profile_name_color", "modern_menu_profile_level_color", "pomodoro_color_digits")
                    for mode in ("light", "dark")]
        fields = [{"id": font_id, "type": "font"} for font_id in ids] + [{"id": key} for key in existing]
        pages = [{"sections": [{"fields": fields}]}]
        self.schema_env()["_attach_font_colors"](pages)
        registered = {field["id"] for field in fields}
        for field in fields:
            if field.get("type") == "font":
                self.assertTrue(field["options"], field["id"])
                self.assertTrue(field["color_fields"], field["id"])
                for target in field["color_fields"]:
                    self.assertIn(target["id"], registered)
        self.assertGreater(len(ids), 20)

    def test_existing_color_bindings_are_reused(self):
        fields = [{"id": key, "type": "font"} for key in
                  ("onigiri_font_profile_name", "onigiri_font_profile_level", "pomodoro_font", "g_mochi_font")]
        self.schema_env()["_attach_font_colors"]([{"sections": [{"fields": fields}]}])
        self.assertEqual(len(fields), 4)
        self.assertEqual(fields[0]["color_fields"][0]["id"], "modern_menu_profile_name_color_light")
        self.assertEqual(fields[1]["color_fields"][1]["id"], "modern_menu_profile_level_color_dark")
        self.assertEqual(fields[2]["color_fields"][0]["id"], "pomodoro_color_digits_light")
        self.assertEqual(fields[3]["color_fields"], [{"id": "g_mochi_text_color", "label": "Color"}])

    def font_css(self, saved):
        fonts = types.ModuleType("font_color_test.ui_kit.fonts")
        fonts.FONTS = {key: {"family": "Poppins", "file": None} for key in ("system", "silkscreen")}
        fonts.get_all_fonts = lambda _: fonts.FONTS
        fonts.poppins_font_face_css = lambda _: ""
        cfg = types.SimpleNamespace(get_collection_config=lambda key, default=None: saved.get(key, default),
                                    get_config_readonly=lambda: {}, DEFAULT_PROFILE_LEVEL_COLOR="#95D5E0")
        env = {"__package__": "font_color_test.rendering", "__file__": str(ROOT / "rendering/patcher.py"),
               "config": cfg, "os": os, "re": re}
        load_functions("rendering/patcher.py", {"generate_font_css"}, env)
        with patch.dict(sys.modules, {"font_color_test.ui_kit.fonts": fonts}):
            return env["generate_font_css"]("1011095603")

    def test_color_override_works_while_font_family_is_synced(self):
        css = self.font_css({"onigiri_font_dashboard_title": "sync",
                             "onigiri_font_dashboard_title_color_light": "#aa3322"})
        self.assertIn(".onigiri-widget-title { color: #aa3322 !important; }", css)
        self.assertIn("html:not(.night-mode):not(.nightMode) body:not(.night-mode):not(.nightMode)", css)
        self.assertNotIn(".nightMode .onigiri-widget-title { color: #aa3322", css)

    def test_dark_override_is_separate_and_unset_preserves_theme(self):
        css = self.font_css({"onigiri_font_dashboard_title_color_dark": "#aabbcc"})
        self.assertIn(".nightMode .onigiri-widget-title,", css)
        self.assertIn(".nightMode .onigiri-widget-container .onigiri-widget-title { color: #aabbcc !important; }", css)
        self.assertNotIn("body:not(.night-mode):not(.nightMode) .onigiri-widget-title { color:", css)
        self.assertNotIn(".onigiri-widget-title { color:", self.font_css({}))

    def test_number_ink_preserves_units_and_has_no_chart_rules(self):
        css = self.font_css({"swidget_number_font_color_light": "#123456"})
        self.assertIn(".stat-value { color: #123456 !important; }", css)
        self.assertIn(".stat-value .stat-unit { color: var(--swidget-value-color, var(--fg)) !important; }", css)
        self.assertNotIn("--swidget-studied-accent: #123456", css)
        self.assertNotIn(".stat-icon { color: #123456", css)

    def test_invalid_persisted_ink_is_not_injected_as_css(self):
        css = self.font_css({"onigiri_font_dashboard_title_color_light": "red; display:none"})
        self.assertNotIn("display:none", css)


if __name__ == "__main__":
    unittest.main()
