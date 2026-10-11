import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INIT = (ROOT / "__init__.py").read_text(encoding="utf-8")
CONFIG = (ROOT / "config.py").read_text(encoding="utf-8")
PATCHER = (ROOT / "patcher.py").read_text(encoding="utf-8")
RENDERER = (ROOT / "onigiri_renderer.py").read_text(encoding="utf-8")
SCHEMA = (ROOT / "settings_web" / "schema.py").read_text(encoding="utf-8")
SETTINGS_JS = (ROOT / "web" / "settings.js").read_text(encoding="utf-8")
SETTINGS_CSS = (ROOT / "web" / "settings.css").read_text(encoding="utf-8")
SHIMA = (ROOT / "shima_theme.py").read_text(encoding="utf-8")
SHIMA_CSS = (ROOT / "web" / "shima.css").read_text(encoding="utf-8")
MENU_CSS = (ROOT / "web" / "menu.css").read_text(encoding="utf-8")
TEMPLATES = (ROOT / "templates.py").read_text(encoding="utf-8")


class ShimaThemeIntegrationTests(unittest.TestCase):
    def test_python_sources_parse(self):
        ast.parse(SHIMA)
        ast.parse(INIT)
        ast.parse(SCHEMA)

    def test_theme_selector_offers_shima_as_the_third_style(self):
        selector = SCHEMA.split('"id": "theme_style_selector"', 1)[1].split(
            '"id": "theme_gallery"', 1
        )[0]
        self.assertIn('"value": "classic"', selector)
        self.assertIn('"value": "things3"', selector)
        self.assertIn('"value": "shima"', selector)
        self.assertIn('"label": "Shima (島)"', selector)
        self.assertIn('decoration.classList.add("is-shima")', SETTINGS_JS)
        self.assertIn(
            '<rect width="12" height="20" x="6" y="2"', SETTINGS_JS
        )
        self.assertNotIn('decoration.textContent = "島"', SETTINGS_JS)
        self.assertIn(
            "grid-template-columns: repeat(3, minmax(0, 1fr))",
            SETTINGS_CSS,
        )

    def test_deck_browser_dispatches_to_the_dedicated_renderer(self):
        self.assertIn("def _shima_theme_selected", INIT)
        self.assertIn("return shima_theme.render_deck_browser", INIT)
        self.assertIn('stylesheet_link("shima.css")', INIT)

    def test_shima_renderer_contains_only_the_deck_island(self):
        self.assertIn('class="sidebar-left shima-island"', SHIMA)
        self.assertIn('id="decktree"', SHIMA)
        self.assertIn("_render_deck_tree_html_only", SHIMA)
        self.assertIn('"deckSortMode"', SHIMA)
        self.assertNotIn("_get_external_hooks", SHIMA)
        self.assertNotIn("onigiriWidgetLayout", SHIMA)
        self.assertNotIn("profile-bar", SHIMA)
        self.assertNotIn("injected-stats-block", SHIMA)

    def test_hidden_actions_render_home_in_both_real_headers(self):
        self.assertIn("_build_archived_home_button", SHIMA)
        self.assertIn("def _build_archived_home_button", RENDERER)
        self.assertIn("{home_button}", TEMPLATES)
        self.assertIn('id="onigiri-home-toolbar-btn"', RENDERER)
        self.assertIn("display: inline-flex", MENU_CSS)
        self.assertIn('headerIcons.push("home.svg")', SETTINGS_JS)
        self.assertNotIn("onigiri-sidebar-actions-section", SHIMA)
        self.assertIn('"_shima_actions_hidden_migrated"', CONFIG)
        self.assertIn(
            'clean_config["sidebarActionsMode"] = "archived"', CONFIG
        )

    def test_shima_is_centered_and_uses_a_bounded_island(self):
        self.assertIn(
            ".container.modern-main-menu.onigiri-shima > .sidebar-left.shima-island",
            SHIMA_CSS,
        )
        self.assertIn("align-items: center", SHIMA_CSS)
        self.assertIn("justify-content: center", SHIMA_CSS)
        self.assertIn("width: clamp(360px, 42vw, 560px)", SHIMA_CSS)
        self.assertIn("height: clamp(300px, 58vh, 620px)", SHIMA_CSS)
        self.assertIn("box-shadow: none !important", SHIMA_CSS)
        self.assertNotIn("content: none !important", SHIMA_CSS)

    def test_shima_keeps_only_relevant_customization_sections(self):
        sidebar_page = SCHEMA.split("def _sidebar_page", 1)[1].split(
            "# ── Gallery", 1
        )[0]
        mainmenu_page = SCHEMA.split("def _mainmenu_page", 1)[1].split(
            "def build_pages", 1
        )[0]
        self.assertIn('["classic", "shima"]', sidebar_page)
        self.assertIn('["classic", "shima"]', mainmenu_page)
        self.assertIn('section.get("id") == "sidebar_background"', sidebar_page)
        self.assertIn('field.get("id") == "sidebarContentMode"', sidebar_page)

    def test_selecting_shima_applies_quiet_defaults_and_previews_island(self):
        selector = SCHEMA.split('"id": "theme_style_selector"', 1)[1].split(
            '"id": "theme_gallery"', 1
        )[0]
        self.assertIn(
            '"sidebarActionsMode": "archived"', selector
        )
        self.assertIn('"g_notification_mode": "mini"', selector)
        self.assertIn("function paintShimaDeckIsland", SETTINGS_JS)
        self.assertIn('PREVIEW_PAINTERS.sidebar_background = paintThemeSidebar', SETTINGS_JS)
        self.assertIn('vals.onigiri_ui_theme === "shima"', SETTINGS_JS)
        self.assertIn(".osw-sbprev-frame.is-shima", SETTINGS_CSS)

    def test_shima_hides_native_chrome_on_the_main_menu(self):
        self.assertGreaterEqual(PATCHER.count('== "shima"'), 2)
        self.assertGreaterEqual(PATCHER.count('== "deckBrowser"'), 2)


if __name__ == "__main__":
    unittest.main()
