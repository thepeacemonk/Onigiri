import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = (ROOT / "config.py").read_text(encoding="utf-8")
HASHI = (ROOT / "hashi_notes.py").read_text(encoding="utf-8")
SCHEMA = (ROOT / "settings_web" / "schema.py").read_text(encoding="utf-8")
EDITOR = (ROOT / "web" / "hashi_notes.html").read_text(encoding="utf-8")
GALLERY = (ROOT / "web" / "hashi_gallery.html").read_text(encoding="utf-8")


class HashiNotesFontSizeTests(unittest.TestCase):
    def test_dashboard_font_role_does_not_override_hashi_text(self):
        patcher = ast.parse((ROOT / "patcher.py").read_text(encoding="utf-8"))
        function = next(node for node in patcher.body
                        if isinstance(node, ast.FunctionDef)
                        and node.name == "generate_font_css")
        assignment = next(node for node in function.body
                          if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name)
                                  and target.id == "advanced_role_specs"
                                  for target in node.targets))
        roles = ast.literal_eval(assignment.value)
        selectors = roles["widget_small"]["selectors"]
        self.assertIn(".onigiri-widget-container", selectors)
        self.assertFalse(any("hashi-widget-" in selector for selector in selectors))

    def test_widget_uses_exact_configured_pixels(self):
        functions = ast.Module(body=[
            node for node in ast.parse(HASHI).body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"note_font_size", "_widget_font_css"}
        ], type_ignores=[])
        for size in (12, 14, 15, 24):
            with self.subTest(size=size):
                namespace = {"get_prefs": lambda: {"font_size": size}}
                exec(compile(functions, "hashi_notes.py", "exec"), namespace)
                self.assertEqual(namespace["_widget_font_css"](),
                    f"--hashiw-card-excerpt-size:{size}px;"
                    f"--hashiw-single-text-size:{size}px;")

    def test_font_size_has_a_default_and_settings_control(self):
        self.assertIn('"font_size": 14,', CONFIG)
        self.assertIn('"id": "hashi_note_font_size"', SCHEMA)
        self.assertIn('["hashi_notes", "font_size"]', SCHEMA)
        self.assertIn('"type": "number"', SCHEMA)
        self.assertNotIn('"id": "hashi_note_appearance"', SCHEMA)

    def test_font_size_is_clamped_and_used_in_both_webviews(self):
        self.assertIn("def note_font_size()", HASHI)
        self.assertIn("def _widget_font_css()", HASHI)
        self.assertIn('"noteFontSize": note_font_size()', HASHI)
        for html in (EDITOR, GALLERY):
            self.assertIn("--hashi-note-font-size", html)
            self.assertIn("ctx.noteFontSize", html)

    def test_dashboard_preview_uses_the_same_setting(self):
        settings_js = (ROOT / "web" / "settings.js").read_text(encoding="utf-8")
        menu_css = (ROOT / "web" / "menu.css").read_text(encoding="utf-8")
        self.assertIn('vals["hashi_note_font_size"]', settings_js)
        self.assertIn("--hashiw-card-excerpt-size", menu_css)
        self.assertNotIn("--hashiw-heading-size", menu_css)
        self.assertNotIn("--hashiw-card-title-size", menu_css)


if __name__ == "__main__":
    unittest.main()
