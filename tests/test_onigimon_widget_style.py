import ast
import json
import re
import unittest
from html import escape
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
CONFIG = (ROOT / "core" / "config.py").read_text(encoding="utf-8")
GAMES = (ROOT / "settings_web" / "games.py").read_text(encoding="utf-8")
ONIGIMON = (ROOT / "gamification" / "onigimon.py").read_text(encoding="utf-8")
RENDERER = (ROOT / "rendering" / "onigiri_renderer.py").read_text(encoding="utf-8")
SETTINGS_JS = (ROOT / "web" / "settings.js").read_text(encoding="utf-8")


def _load_onigimon_widget_helpers(config_dict):
    source = ast.parse(ONIGIMON)
    wanted_funcs = {
        "render_widget_html",
        "_meter",
        "_quick_stat",
        "_sprite_img_html",
        "_normalize_scene_color",
        "_onigimon_scene_image_url",
        "_onigimon_sync_widget_colors",
        "_onigimon_scene_style_attr",
        "_onigimon_bottom_style_attr",
        "_onigimon_scene_background_style_attr",
        "_onigimon_scene_background_layer",
    }
    wanted_assigns = {"DEFAULT_SCENE_BACKGROUND"}
    nodes = [
        node
        for node in source.body
        if (isinstance(node, ast.FunctionDef) and node.name in wanted_funcs)
        or (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id in wanted_assigns
                for target in node.targets
            )
        )
    ]

    companion = {
        "ankimon_id": "25",
        "name": "Pikachu",
        "display_name": "Pika",
        "level": 12,
        "hp": 35,
        "max_hp": 40,
        "hp_stat": 35,
        "happiness": 80,
        "cleanliness": 75,
        "training": 60,
        "hunger": 70,
        "bond_level": 2,
        "bond_xp": 20,
        "attack": 55,
        "defense": 40,
        "speed": 90,
    }

    class FakeManager:
        def config(self):
            return config_dict

        def widget_payload(self):
            return {
                "status": "ready",
                "inventory": {"berry_oran": 2},
                "companion": companion,
                "streak": 4,
            }

        def companion_display_name(self, comp):
            return comp["display_name"]

        def sprite_urls_for_companion(self, _comp):
            return ["/_addons/1011095603/sprite.png"]

        def status_values(self, _comp):
            return {
                "health": 88,
                "happiness": 80,
                "hygiene": 75,
                "training": 60,
                "hunger": 70,
            }

    env = {
        "Any": object,
        "Dict": dict,
        "List": list,
        "Optional": object,
        "os": __import__("os"),
        "re": re,
        "json": json,
        "escape": escape,
        "mw": SimpleNamespace(
            addonManager=SimpleNamespace(addonFromModule=lambda _name: "1011095603")
        ),
        "tr": lambda key, fallback="": fallback or key,
        "manager": FakeManager(),
        "OnigimonCompanion": lambda **kw: SimpleNamespace(**kw),
        "_addon_asset_url": lambda rel: "/_addons/1011095603/" + rel,
    }
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), "gamification/onigimon.py", "exec"),
        env,
    )
    return env


class OnigimonWidgetStyleTests(unittest.TestCase):
    def test_config_and_settings_schema_expose_widget_color_sync(self):
        self.assertIn('"sync_widget_colors": False', CONFIG)
        self.assertIn('"sync_toggle_id": "g_onigimon_sync_widget_colors"', GAMES)
        self.assertIn('"g_onigimon_scene_color"', GAMES)
        self.assertIn('"g_onigimon_bottom_color"', GAMES)
        self.assertIn('("onigimon", "sync_widget_colors")', GAMES)
        self.assertIn('tr("sync_with_widgets", "Sync with widgets")', GAMES)

    def test_renderer_follows_main_menu_widget_border_radius_and_sync_styles(self):
        self.assertIn(
            "border-radius: var(--onigiri-widget-border-radius, var(--onigiri-box-effect-radius, 20px));",
            RENDERER,
        )
        self.assertIn(
            "border-radius: max(0px, calc(var(--onigiri-widget-border-radius, var(--onigiri-box-effect-radius, 20px)) - 8px));",
            RENDERER,
        )
        self.assertIn(".onigimon-card.onigimon-sync-widgets", RENDERER)
        self.assertIn(
            "background: var(--onigiri-box-effect-bg, var(--canvas-inset, #ffffff));",
            RENDERER,
        )

    def test_unsynced_widget_keeps_custom_scene_and_bottom_colors(self):
        env = _load_onigimon_widget_helpers(
            {
                "sync_widget_colors": False,
                "scene_background_mode": "color",
                "scene_background_color": "#336699",
                "scene_bottom_color": "#112233",
            }
        )
        full_html = env["render_widget_html"](row_span=2, col_span=1)
        self.assertNotIn("onigimon-sync-widgets", full_html)
        self.assertIn("background-color: #336699", full_html)
        self.assertIn("--onigimon-color: #336699", full_html)
        self.assertIn("background: #112233 !important;", full_html)

        compact_html = env["render_widget_html"](row_span=1, col_span=2)
        self.assertNotIn("onigimon-sync-widgets", compact_html)
        self.assertIn("background-color: #336699", compact_html)

    def test_synced_widget_uses_main_menu_widget_class_and_clears_inline_colors(self):
        env = _load_onigimon_widget_helpers(
            {
                "sync_widget_colors": True,
                "scene_background_mode": "color",
                "scene_background_color": "#336699",
                "scene_bottom_color": "#112233",
            }
        )
        full_html = env["render_widget_html"](row_span=2, col_span=1)
        self.assertIn("onigimon-sync-widgets", full_html)
        self.assertIn("background-color: transparent", full_html)
        self.assertNotIn("--onigimon-color:", full_html)
        self.assertNotIn("background: #112233 !important;", full_html)

        compact_html = env["render_widget_html"](row_span=1, col_span=2)
        self.assertIn("onigimon-card onigimon-card-compact onigimon-span-1x2 onigimon-sync-widgets", compact_html)
        self.assertIn("background-color: transparent", compact_html)

    def test_settings_preview_follows_border_radius_and_sync_toggle(self):
        self.assertIn("vals.g_onigimon_sync_widget_colors", SETTINGS_JS)
        self.assertIn("vals.onigiri_canvas_inset_border_radius", SETTINGS_JS)
        self.assertIn('card.style.borderRadius = widgetRadius + "px";', SETTINGS_JS)
        self.assertIn(
            'sceneColor.classList.toggle("is-hidden", isSyncHidden(card, "g_onigimon_scene_color"))',
            SETTINGS_JS,
        )


if __name__ == "__main__":
    unittest.main()
