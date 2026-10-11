import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_SOURCE = (ROOT / "core/config.py").read_text(encoding="utf-8")
PATCHER = (ROOT / "rendering/patcher.py").read_text(encoding="utf-8")
SETTINGS = (ROOT / "web" / "settings.js").read_text(encoding="utf-8")
MENU_CSS = (ROOT / "web" / "menu.css").read_text(encoding="utf-8")
INJECTOR = (ROOT / "web" / "injector.js").read_text(encoding="utf-8")
TREE_UPDATER = (ROOT / "decks" / "tree_updater.py").read_text(encoding="utf-8")
RENDERER = (ROOT / "rendering/onigiri_renderer.py").read_text(encoding="utf-8")
INIT = (ROOT / "__init__.py").read_text(encoding="utf-8")
DIALOG = (ROOT / "settings_web" / "dialog.py").read_text(encoding="utf-8")


def _config_asset_functions():
    tree = ast.parse(CONFIG_SOURCE)
    wanted = {"_dynamic_theme_enabled", "themed_asset"}
    body = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    namespace = {}
    exec(compile(ast.Module(body=body, type_ignores=[]), "core/config.py", "exec"), namespace)
    return namespace["themed_asset"]


class OpenIssueRegressionTests(unittest.TestCase):
    def test_string_theme_modes_are_not_treated_as_truthy_booleans(self):
        themed_asset = _config_asset_functions()
        values = {
            "wallpaper": "shared.png",
            "wallpaper_light": "light.png",
            "wallpaper_dark": "dark.png",
            "mode": "single",
        }
        self.assertEqual(
            themed_asset(values.get, "wallpaper", True, dynamic_key="mode"),
            "shared.png",
        )
        values["mode"] = "separate"
        self.assertEqual(
            themed_asset(values.get, "wallpaper", True, dynamic_key="mode"),
            "dark.png",
        )

    def test_broken_single_mode_recovers_an_existing_themed_image(self):
        themed_asset = _config_asset_functions()
        values = {
            "wallpaper": "",
            "wallpaper_light": "light.png",
            "wallpaper_dark": "dark.png",
            "canonical_mode": "single",
            "legacy_mode": "separate",
        }
        self.assertEqual(
            themed_asset(
                values.get,
                "wallpaper",
                False,
                dynamic_key=("canonical_mode", "legacy_mode"),
            ),
            "light.png",
        )

    def test_main_background_readers_use_the_canonical_compatible_resolver(self):
        self.assertNotIn(
            'mw.col.conf.get("modern_menu_background_image_mode"',
            PATCHER,
        )
        self.assertGreaterEqual(
            PATCHER.count('"modern_menu_bg_image_theme_mode"'),
            5,
        )

    def test_dynamic_toggle_preserves_and_migrates_image_slots(self):
        self.assertIn("function setDesignerDynamicMode(section, enabled, previewMode)", SETTINGS)
        self.assertIn("if (!values[field.lightField] && base)", SETTINGS)
        self.assertIn("if (shared) setValue(field.id, shared)", SETTINGS)
        self.assertNotIn('setValue(field.lightField, "");', SETTINGS)
        self.assertIn("values[preferred] || values[alternate]", SETTINGS)
        self.assertIn('setValue("modern_menu_background_image_mode"', SETTINGS)

    def test_image_thumbnails_hide_native_broken_image_fallbacks(self):
        self.assertIn("function appendImageWithFallback(container, url)", SETTINGS)
        self.assertIn('img.style.visibility = "hidden"', SETTINGS)
        self.assertIn('img.addEventListener("error"', SETTINGS)
        self.assertIn('container.insertAdjacentHTML("beforeend", ICON_IMAGE)', SETTINGS)
        self.assertIn("appendImageWithFallback(thumb, url)", SETTINGS)

    def test_sidebar_boot_has_an_early_fail_safe_reveal(self):
        self.assertIn("window.setTimeout(() => bootSidebar.classList.remove", INJECTOR)
        self.assertIn("new ResizeObserver(scheduleSidebarEdgeToggle)", INJECTOR)
        self.assertNotIn(
            ".sidebar-left.skeleton-loading .sidebar-expanded-content",
            MENU_CSS,
        )

    def test_one_dashboard_widget_cannot_abort_the_main_menu_render(self):
        self.assertIn("def render_widget_safely(widget_id, renderer):", RENDERER)
        self.assertIn("Onigiri: {widget_id} widget failed", RENDERER)
        self.assertIn("ignored invalid {widget_id} widget layout", RENDERER)
        self.assertIn("def safe_fragment(label, generator):", INIT)
        self.assertIn('"deck-browser backgrounds"', INIT)

    def test_widget_layout_margins_preserve_the_tile_content_height(self):
        self.assertIn("widget_margin_top = _widget_margin_value(\"top\")", RENDERER)
        self.assertIn("widget_margin_bottom = _widget_margin_value(\"bottom\")", RENDERER)
        self.assertIn(
            "grid_row_height = grid_widget_height + widget_margin_top + widget_margin_bottom",
            RENDERER,
        )
        self.assertIn("grid-auto-rows: {grid_row_height}px;", RENDERER)

    def test_gallery_import_uses_a_visible_top_level_picker_host(self):
        gallery_import = DIALOG.split("def _cmd_gallery_import", 1)[1].split(
            "def _cmd_gallery_delete", 1
        )[0]
        self.assertIn("host = self._picker_host()", gallery_import)
        self.assertIn("self._release_picker_host(host)", gallery_import)

    def test_hover_text_color_is_applied_and_has_a_runtime_fallback(self):
        self.assertIn("color: var(--highlight-fg, var(--fg)) !important;", MENU_CSS)
        self.assertIn("background-color: transparent !important;", MENU_CSS)
        self.assertIn('light_colors["--highlight-fg"]', PATCHER)
        self.assertIn('dark_colors["--highlight-fg"]', PATCHER)

    def test_deck_and_tag_names_select_their_own_writing_direction(self):
        self.assertIn('class="deck-name" dir="auto"', PATCHER)
        self.assertIn('class="onigiri-tag-name" dir="auto"', TREE_UPDATER)
        self.assertIn("a.deck .deck-name:dir(rtl)", MENU_CSS)


if __name__ == "__main__":
    unittest.main()
