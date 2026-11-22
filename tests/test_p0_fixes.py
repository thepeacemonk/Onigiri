import ast
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


ADDON_ROOT = Path(__file__).resolve().parents[1]


def _load_function(rel_path: str, func_name: str, extra_globals=None):
    source = (ADDON_ROOT / rel_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == func_name
    )
    module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    ns = dict(extra_globals or {})
    exec(compile(module, rel_path, "exec"), ns)
    return ns[func_name]


class P0FixesTests(unittest.TestCase):
    def test_363_focus_dango_wrapper_trims_qt_checked_bool(self):
        create_blocking_wrapper = _load_function(
            "gamification/focus_dango.py",
            "create_blocking_wrapper",
            {"check_and_block_navigation": lambda _name: False},
        )
        calls = []

        class FakeAnkiQt:
            def onAddCard(self):
                calls.append("added")
                return "ok"

        fake_mw = FakeAnkiQt()
        wrapped = create_blocking_wrapper(fake_mw.onAddCard, "onAddCard")
        # Simulate QAction.triggered(bool) passing `checked=False`
        self.assertEqual(wrapped(False), "ok")
        self.assertEqual(calls, ["added"])

    def test_363_focus_dango_wrapper_preserves_valid_args_and_blocks(self):
        create_blocking_wrapper = _load_function(
            "gamification/focus_dango.py",
            "create_blocking_wrapper",
            {"check_and_block_navigation": lambda _name: True},
        )
        called = Mock()
        wrapped = create_blocking_wrapper(called, "onAddCard")
        self.assertIsNone(wrapped(False))
        called.assert_not_called()

    def test_365_full_hide_mode_uses_hide_menubar_preserving_shortcuts(self):
        fake_mw = SimpleNamespace(
            hide_menubar=Mock(),
            show_menubar=Mock(),
            menuBar=Mock(return_value=SimpleNamespace(hide=Mock(), show=Mock())),
        )
        fake_config = SimpleNamespace(get_config_readonly=lambda: {"fullHideMode": True})
        apply_full_hide_mode = _load_function(
            "__init__.py",
            "apply_full_hide_mode",
            {"mw": fake_mw, "config": fake_config},
        )
        with patch("platform.system", return_value="Windows"):
            apply_full_hide_mode()
        fake_mw.hide_menubar.assert_called_once()
        fake_mw.menuBar().hide.assert_not_called()

        fake_config_off = SimpleNamespace(get_config_readonly=lambda: {"fullHideMode": False})
        apply_full_hide_mode_off = _load_function(
            "__init__.py",
            "apply_full_hide_mode",
            {"mw": fake_mw, "config": fake_config_off},
        )
        with patch("platform.system", return_value="Windows"):
            apply_full_hide_mode_off()
        fake_mw.show_menubar.assert_called_once()

    def test_401_set_main_webview_bg_forces_opaque_and_skips_noop(self):
        class FakeQColor:
            def __init__(self, val=None):
                self._val = val
                self._alpha = 128 if (isinstance(val, str) and len(val) == 9) else 255

            def isValid(self):
                return isinstance(self._val, str) and self._val.startswith("#")

            def alpha(self):
                return self._alpha

            def setAlpha(self, a):
                self._alpha = a

            def __eq__(self, other):
                return (
                    isinstance(other, FakeQColor)
                    and self._val == other._val
                    and self._alpha == other._alpha
                )

        page = SimpleNamespace(
            _bg=None,
            setBackgroundColor=Mock(),
            backgroundColor=lambda: page._bg,
        )

        def record_bg(c):
            page._bg = c

        page.setBackgroundColor.side_effect = record_bg
        fake_mw = SimpleNamespace(web=SimpleNamespace(page=lambda: page))
        fake_qt = types.ModuleType("aqt.qt")
        fake_qt.QColor = FakeQColor
        fake_aqt = types.ModuleType("aqt")
        fake_aqt.qt = fake_qt

        fn = _load_function(
            "rendering/patcher.py",
            "set_main_webview_background_color",
            {"mw": fake_mw, "_resolve_night_mode": lambda: True},
        )

        with patch.dict(sys.modules, {"aqt": fake_aqt, "aqt.qt": fake_qt}):
            # Translucent color gets forced opaque (alpha=255)
            fn("#2c2c2c80")
            self.assertEqual(page.setBackgroundColor.call_count, 1)
            self.assertEqual(page._bg.alpha(), 255)

            # Same color again is a no-op
            fn("#2c2c2c80")
            self.assertEqual(page.setBackgroundColor.call_count, 1)

            # Invalid/non-string falls back to valid opaque default
            fn(12345)
            self.assertEqual(page.setBackgroundColor.call_count, 2)
            self.assertEqual(page._bg._val, "#2C2C2C")
            self.assertEqual(page._bg.alpha(), 255)

    def test_408_deck_browser_and_congrats_redraw_bottom_bar(self):
        renderer_src = (ADDON_ROOT / "rendering/onigiri_renderer.py").read_text(encoding="utf-8")
        self.assertIn('if hasattr(self, "_drawButtons"):', renderer_src)
        self.assertIn("self._drawButtons()", renderer_src)

        patcher_src = (ADDON_ROOT / "rendering/patcher.py").read_text(encoding="utf-8")
        self.assertIn('if hasattr(self, "_renderBottom"):', patcher_src)
        self.assertIn("self._renderBottom()", patcher_src)

    def test_395_kome_decklist_css_widens_count_columns(self):
        css = (ADDON_ROOT / "things_theme/web/decklist.css").read_text(encoding="utf-8")
        self.assertIn("--ad-count-cols: 48px 88px 80px;", css)


if __name__ == "__main__":
    unittest.main()
