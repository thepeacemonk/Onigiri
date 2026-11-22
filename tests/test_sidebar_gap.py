"""Tests for Main Menu automatic equal Sidebar Gap and manual override."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_build_sidebar_widget_gap_css():
    patcher_path = ROOT / "rendering" / "patcher.py"
    source = patcher_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(patcher_path))
    func_node = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_build_sidebar_widget_gap_css"
    )
    module = ast.Module(body=[func_node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict = {}
    exec(compile(module, str(patcher_path), "exec"), namespace)
    return namespace["_build_sidebar_widget_gap_css"]


class SidebarGapTests(unittest.TestCase):
    def setUp(self):
        self.build_css = _load_build_sidebar_widget_gap_css()

    def test_auto_mode_is_default_and_balances_sidebar_and_border_gap(self):
        css = self.build_css(10, "auto", 48)
        self.assertIn("gap: 0 !important;", css)
        self.assertIn("margin-left: 0 !important;", css)
        self.assertIn("margin-right: 0 !important;", css)
        self.assertIn("align-items: safe center;", css)
        self.assertIn(
            ":not(.onigiri-sidebar-right):not(.onigiri-cycle-stacked):not(.onigiri-sidebar-center) "
            ".sidebar-left:not(.sidebar-collapsed) ~ .main-content",
            css,
        )
        self.assertIn("padding-right: calc(15px + 10px) !important;", css)
        self.assertIn(
            ".onigiri-sidebar-right:not(.onigiri-cycle-stacked):not(.onigiri-sidebar-center) "
            ".sidebar-left:not(.sidebar-collapsed) ~ .main-content",
            css,
        )
        self.assertIn("padding-left: calc(15px + 10px) !important;", css)
        # Auto mode must not force flush-start/end alignment against the sidebar
        self.assertNotIn("align-items: flex-start;", css)
        self.assertNotIn("justify-content: start;", css)
        self.assertNotIn("48px", css)

    def test_auto_mode_tracks_custom_sidebar_margin_and_handles_invalid_mode(self):
        css = self.build_css(24, None, 0)
        self.assertIn("padding-right: calc(15px + 24px) !important;", css)
        self.assertIn("padding-left: calc(15px + 24px) !important;", css)

        css_invalid = self.build_css("invalid", "unexpected", 30)
        self.assertIn("padding-right: calc(15px + 10px) !important;", css_invalid)
        self.assertNotIn("30px", css_invalid)

    def test_manual_mode_applies_explicit_offset_when_sidebar_expanded(self):
        css = self.build_css(10, "manual", 36)
        self.assertIn("margin-left: 36px !important;", css)
        self.assertIn("margin-right: 36px !important;", css)
        self.assertIn(".sidebar-left:not(.sidebar-collapsed) ~ .main-content", css)
        self.assertIn("align-items: flex-start;", css)
        self.assertIn("justify-content: start;", css)
        self.assertIn("align-items: flex-end;", css)
        self.assertIn("justify-content: end;", css)
        self.assertNotIn("padding-right: calc(", css)

    def test_manual_mode_clamps_negative_legacy_offsets_and_upper_bound(self):
        css_neg = self.build_css(10, "manual", -80)
        self.assertIn("margin-left: 0px !important;", css_neg)
        self.assertIn("margin-right: 0px !important;", css_neg)

        css_max = self.build_css(10, "manual", 999)
        self.assertIn("margin-left: 240px !important;", css_max)

    def test_schema_defines_mode_default_auto_and_conditional_manual_slider(self):
        schema_src = (ROOT / "settings_web" / "schema.py").read_text(encoding="utf-8")
        self.assertIn('"id": "modern_menu_sidebar_widget_gap_mode"', schema_src)
        self.assertIn('"bind": {"kind": "col", "key": "modern_menu_sidebar_widget_gap_mode"}', schema_src)
        self.assertIn('"default": "auto"', schema_src)
        self.assertIn('"value": "auto"', schema_src)
        self.assertIn('"value": "manual"', schema_src)
        self.assertIn('"field": "modern_menu_sidebar_widget_gap_mode"', schema_src)

    def test_settings_js_and_css_wire_mode_and_slider_visibility(self):
        js_src = (ROOT / "web" / "settings.js").read_text(encoding="utf-8")
        self.assertIn('fieldById["modern_menu_sidebar_widget_gap_mode"]', js_src)
        self.assertIn("osw-widget-layout-gap-mode", js_src)
        self.assertIn("fields: [gapModeField, gapField]", js_src)

        css_src = (ROOT / "web" / "settings.css").read_text(encoding="utf-8")
        self.assertIn(".osw-widget-layout-compact [data-field-host].is-hidden", css_src)

    def test_translations_cover_all_eight_languages(self):
        import importlib.util
        import sys
        import types

        # Load core/translations.py without Anki
        aqt_stub = types.ModuleType("aqt")
        aqt_stub.mw = None
        sys.modules.setdefault("aqt", aqt_stub)
        spec = importlib.util.spec_from_file_location("_onigiri_tr_test", ROOT / "core" / "translations.py")
        tr_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tr_mod)

        required_keys = (
            "sidebar_gap",
            "sidebar_gap_desc",
            "sidebar_gap_mode_desc",
            "sidebar_gap_auto",
            "sidebar_gap_manual",
            "sidebar_gap_manual_label",
        )
        expected_langs = ("en", "pt-BR", "es-ES", "zh-CN", "ja-JP", "fr-FR", "ko-KR", "de-DE")
        for lang in expected_langs:
            cat = tr_mod.TRANSLATIONS[lang]
            for key in required_keys:
                self.assertIn(key, cat, f"Missing '{key}' in '{lang}'")
                self.assertTrue(str(cat[key]).strip(), f"Empty '{key}' in '{lang}'")


if __name__ == "__main__":
    unittest.main()
