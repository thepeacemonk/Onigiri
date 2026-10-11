import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = (ROOT / "config.py").read_text(encoding="utf-8")
SCHEMA = (ROOT / "settings_web" / "schema.py").read_text(encoding="utf-8")
SCRIPT = (ROOT / "web" / "settings.js").read_text(encoding="utf-8")
MENU_CSS = (ROOT / "web" / "menu.css").read_text(encoding="utf-8")
PATCHER = (ROOT / "patcher.py").read_text(encoding="utf-8")


class ToolWidgetStyleContractTests(unittest.TestCase):
    def test_prep_station_has_independent_style_storage(self):
        self.assertIn('"prep_widget_style": {', CONFIG)
        for key in ("sync_box_effect", "dynamic", "blur", "opacity", "radius", "stroke"):
            self.assertIn(f'"{key}":', CONFIG)

    def test_both_tool_pages_expose_widget_style_controls(self):
        for prefix in ("prep_widget", "hashi_widget"):
            for suffix in ("sync", "dynamic", "blur", "opacity", "radius", "stroke"):
                self.assertIn(f'"id": "{prefix}_{suffix}"', SCHEMA)
            for color in ("box_bg", "box_border"):
                self.assertIn(f'"{prefix}_color_" + key', SCHEMA)
                self.assertIn(f'"{color}"', SCHEMA)

    def test_prep_preview_supports_shared_and_individual_styles(self):
        self.assertIn('const synced = vals["prep_widget_sync"] !== false;', SCRIPT)
        self.assertIn('"prep_widget_color_" + key', SCRIPT)

    def test_live_prep_widget_uses_its_own_css_variables(self):
        for variable in ("bg", "border", "radius", "stroke", "blur"):
            self.assertIn(f"--prepw-box-{variable}", PATCHER)
            self.assertIn(f"--prepw-box-{variable}", MENU_CSS)


if __name__ == "__main__":
    unittest.main()
