import ast
import unittest
from pathlib import Path
from unittest.mock import Mock


ADDON_ROOT = Path(__file__).resolve().parents[1]


def _load_ready_functions(setting_values):
    source = (ADDON_ROOT / "study_tools" / "ready_to_go.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    selected = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in ("is_enabled", "render_sidebar_html", "render_widget_html", "handle_command")
    ]
    module = ast.fix_missing_locations(
        ast.Module(
            body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)] + selected,
            type_ignores=[],
        )
    )
    build_mock = Mock()
    ns = {
        "_setting": lambda key, default=None: setting_values.get(key, default),
        "localized_default": lambda value, _keys: value,
        "html": __import__("html"),
        "_appearance_style": lambda: "",
        "_buttons_html": lambda cls, circles=False: f"<div class='{cls}'></div>",
        "READY_ACTIONS": {"inbox": {"query": "is:new", "deck_name": "Onigiri Ready — Inbox"}},
        "_build_and_study": build_mock,
        "_report_error": Mock(),
    }
    exec(compile(module, "study_tools/ready_to_go.py", "exec"), ns)
    return ns, build_mock


class ReadyToGoToggleTests(unittest.TestCase):
    def test_disabled_hides_sidebar_widget_and_blocks_commands(self):
        ns, build_mock = _load_ready_functions({"modern_menu_ready_enabled": False})
        self.assertFalse(ns["is_enabled"]())
        self.assertEqual(ns["render_sidebar_html"](), "")
        self.assertEqual(ns["render_widget_html"](), "")
        self.assertFalse(ns["handle_command"]("inbox"))
        build_mock.assert_not_called()

    def test_enabled_by_default_renders_sidebar_and_widget(self):
        ns, build_mock = _load_ready_functions({})
        self.assertTrue(ns["is_enabled"]())
        self.assertIn("onigiri-ready-sidebar", ns["render_sidebar_html"]())
        self.assertIn("onigiri-ready-widget", ns["render_widget_html"]())
        self.assertTrue(ns["handle_command"]("inbox"))
        build_mock.assert_called_once()

    def test_hidden_layout_still_enabled_but_hides_sidebar_only(self):
        ns, _ = _load_ready_functions(
            {"modern_menu_ready_enabled": True, "modern_menu_ready_layout_mode": "hidden"}
        )
        self.assertTrue(ns["is_enabled"]())
        self.assertEqual(ns["render_sidebar_html"](), "")
        self.assertIn("onigiri-ready-widget", ns["render_widget_html"]())

    def test_settings_schema_and_renderers_wire_ready_toggle(self):
        schema_src = (ADDON_ROOT / "settings_web" / "schema.py").read_text(encoding="utf-8")
        self.assertIn('"id": "modern_menu_ready_enabled"', schema_src)
        self.assertIn('"id": "things_show_ready_to_go"', schema_src)

        renderer_src = (ADDON_ROOT / "rendering" / "onigiri_renderer.py").read_text(encoding="utf-8")
        self.assertIn("if not _ready_to_go().is_enabled():", renderer_src)

        kome_js = (ADDON_ROOT / "things_theme" / "web" / "sidebar.js").read_text(encoding="utf-8")
        self.assertIn("if (sidebarOpts.ready !== false) aside.appendChild(buildReadyToGo());", kome_js)

        settings_js = (ADDON_ROOT / "web" / "settings.js").read_text(encoding="utf-8")
        self.assertIn('if (vals["modern_menu_ready_enabled"] === false) return;', settings_js)


if __name__ == "__main__":
    unittest.main()
