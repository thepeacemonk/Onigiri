import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = (ROOT / "config.py").read_text(encoding="utf-8")
DIALOG = (ROOT / "settings_web" / "dialog.py").read_text(encoding="utf-8")
RENDER = (ROOT / "settings_web" / "render.py").read_text(encoding="utf-8")
HTML = (ROOT / "web" / "settings.html").read_text(encoding="utf-8")
JS = (ROOT / "web" / "settings.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "settings.css").read_text(encoding="utf-8")
PALETTE = (ROOT / "theme_palette.py").read_text(encoding="utf-8")
SCHEMA = (ROOT / "settings_web" / "schema.py").read_text(encoding="utf-8")
RENDERER = (ROOT / "onigiri_renderer.py").read_text(encoding="utf-8")
INJECTOR = (ROOT / "web" / "injector.js").read_text(encoding="utf-8")
MENU_CSS = (ROOT / "web" / "menu.css").read_text(encoding="utf-8")


class SettingsWebStartupTests(unittest.TestCase):
    def test_advanced_mode_is_the_hidden_default(self):
        self.assertIn('"settings_complexity": "advanced"', CONFIG)
        self.assertIn('"settingsComplexity": store.read("settings_complexity") or "advanced"', RENDER)
        self.assertIn('let settingsComplexity = "advanced";', JS)
        self.assertIn("osw-complexity is-temporarily-hidden", HTML)
        self.assertIn(".osw-complexity.is-temporarily-hidden { display: none; }", CSS)

    def test_incomplete_html_shell_is_guarded(self):
        self.assertIn('<html class="osw-booting">', HTML)
        self.assertIn("html.osw-booting .osw-shell", HTML)
        self.assertIn("/*__ONIGIRI_BOOT_BACKGROUND__*/", HTML)
        self.assertIn(
            '.replace("/*__ONIGIRI_BOOT_BACKGROUND__*/", boot_background)',
            RENDER,
        )

    def test_requested_page_is_built_before_ready(self):
        self.assertIn('"initialPage": initial_page', RENDER)
        self.assertIn("CTX.initialPage && pageById[CTX.initialPage]", JS)

    def test_webui_marks_ready_only_after_api_is_installed(self):
        api_pos = JS.index("window.onigiriSettings = {")
        unguard_pos = JS.index('classList.remove("osw-booting")')
        ready_pos = JS.index('classList.add("osw-ready")')
        self.assertLess(api_pos, unguard_pos)
        self.assertLess(unguard_pos, ready_pos)
        self.assertNotIn('bridge("osw:ready:")', JS)

    def test_native_window_is_revealed_from_qt_load_completion(self):
        self.assertIn("self.web.loadFinished.connect(self._on_load_finished)", DIALOG)
        self.assertIn("def _on_load_finished(self, ok):", DIALOG)
        self.assertIn("self.web.page().runJavaScript(", DIALOG)
        self.assertIn("def _on_boot_checked(self, ready):", DIALOG)
        self.assertIn("QTimer.singleShot(0, self._reveal)", DIALOG)
        self.assertIn("self._closed = True", DIALOG)
        self.assertIn("if self._closed or not self._page_ready:", DIALOG)
        open_settings = DIALOG.split("def open_settings(", 1)[1].split(
            "def _trigger_mac_haptic_native", 1
        )[0]
        self.assertNotIn("_dialog.show()", open_settings)

    def test_startup_has_a_non_webview_failure_surface(self):
        self.assertIn("def _show_load_error(self):", DIALOG)
        self.assertIn("self.web.hide()", DIALOG)
        self.assertIn("QLabel(", DIALOG)

    def test_repeated_open_reuses_inflight_dialog(self):
        self.assertIn("def bring_to_front(self, initial_page=None):", DIALOG)
        self.assertIn("if _dialog.bring_to_front(initial_page):", DIALOG)
        self.assertIn("return _dialog", DIALOG)
        self.assertIn("stale.deleteLater()", DIALOG)

    def test_window_sizing_happens_before_layout_creation(self):
        constructor = DIALOG.split("def __init__(", 1)[1].split(
            "def _apply_proportional_size", 1
        )[0]
        self.assertLess(
            constructor.index("self._apply_proportional_size()"),
            constructor.index("self._layout = QVBoxLayout(self)"),
        )

    def test_settings_dialog_always_keeps_the_native_macos_title_bar(self):
        macos_policy = DIALOG.split(
            "if mac_titlebar.is_supported():", 1
        )[1].split("self._layout.addWidget(self.web, 1)", 1)[0]
        self.assertIn("mac_titlebar.apply(False, self)", macos_policy)
        self.assertNotIn("hideMacTitleBar", macos_policy)
        self.assertNotIn("mac_titlebar.apply(True, self)", macos_policy)

    def test_light_chrome_keeps_neutral_control_insets_distinct_from_cards(self):
        self.assertIn('"surface": "#f7f7f6", "surface_alt": "#f1f1f0",', PALETTE)
        self.assertIn('"inset": "#efefee", "inset_hover": "#e5e5e4",', PALETTE)
        self.assertIn("--osw-surface: #f7f7f6;", CSS)
        self.assertIn("--osw-inset: #efefee;", CSS)
        self.assertIn("--osw-inset-hover: #e5e5e4;", CSS)

    def test_window_opens_at_its_maximum_width_and_smaller_height(self):
        self.assertIn("default_w = self.maximumWidth()", DIALOG)
        self.assertIn("int(height * 0.65)", DIALOG)
        self.assertNotIn('self.store.read("window_settings")', DIALOG)
        self.assertNotIn('"window_settings": {', DIALOG)

    def test_sidebar_width_can_be_pinned_from_settings(self):
        self.assertIn('"id": "modern_menu_sidebar_width_pinned"', SCHEMA)
        self.assertIn('"id": "modern_menu_sidebar_width"', SCHEMA)
        self.assertIn('"min": 320', SCHEMA)
        self.assertIn('"max": 1200', SCHEMA)
        self.assertIn('"sidebarWidthPinned": sidebar_width_pinned', RENDERER)
        self.assertIn("window.ONIGIRI_CONFIG.sidebarWidthPinned", INJECTOR)
        self.assertIn("sidebar-width-pinned .resize-handle", MENU_CSS)

    def test_simple_profile_mode_enforces_its_compact_defaults(self):
        self.assertIn("const SIMPLE_PROFILE_VALUES", JS)
        self.assertIn('modern_menu_profile_type: "ring"', JS)
        self.assertIn('modern_menu_profile_picture_mode: "custom"', JS)
        self.assertIn("PROFILE_DYNAMIC_KEYS.forEach", JS)
        self.assertIn("function applySimpleProfileDefaults()", JS)
        self.assertIn("applySimpleProfileDefaults();", JS)
        self.assertIn("data-simple-profile-dynamic", JS)
        self.assertIn("data-simple-profile-style", JS)
        self.assertIn('[data-field-host="modern_menu_profile_picture_mode"]', JS)
        self.assertIn("osw-simple-profile-hidden", JS)

    def test_profile_icon_color_picker_keeps_light_and_dark_slots_visible(self):
        icon_color = SCHEMA.split(
            '"modern_menu_profile_picture_icon_color",', 1
        )[1].split(
            '_hidden_field("modern_menu_profile_picture_icon_color_light"', 1
        )[0]
        self.assertIn("always_split=True", icon_color)

    def test_simple_profile_hides_advanced_content_and_removes_status(self):
        self.assertIn('"id": "profile_bio"', SCHEMA)
        self.assertIn('"id": "profile_music"', SCHEMA)
        self.assertIn('"advanced_only": True', SCHEMA)
        self.assertIn("[data-simple-profile-advanced]", JS)
        self.assertNotIn('"id": "profile_status"', SCHEMA)
        self.assertNotIn('profile["status"]', RENDERER)
        self.assertNotIn("onigiri-sidebar-profile-status", MENU_CSS)

    def test_simple_sync_enforces_everything_and_hides_policy_controls(self):
        self.assertIn("const SIMPLE_SYNC_VALUES", JS)
        self.assertIn('ankiweb_sync_preset: "everything"', JS)
        self.assertIn("ankiweb_sync_layout: true", JS)
        self.assertIn("function applySimpleSyncDefaults()", JS)
        self.assertIn("applySimpleSyncDefaults();", JS)
        self.assertIn('"id": "sync_categories"', SCHEMA)
        self.assertIn('"advanced_only": True', SCHEMA)

    def test_simple_organize_widgets_hides_and_reflows_structural_controls(self):
        self.assertIn('alignRow.setAttribute("data-simple-organize-advanced"', JS)
        self.assertIn('widgetHeightControl.setAttribute("data-simple-organize-advanced"', JS)
        self.assertIn('gridWidthControl.setAttribute("data-simple-organize-advanced"', JS)
        self.assertIn('layoutControls.setAttribute("data-simple-organize-advanced"', JS)
        self.assertIn('node.setAttribute("data-simple-organize-advanced"', JS)

    def test_hidden_action_buttons_omits_inapplicable_controls_and_gaps(self):
        action_section = SCHEMA.split('def _sidebar_actions_section():', 1)[1]
        dashed = action_section.split('"id": "sidebarAddDashed"', 1)[1].split(
            '"id": "sidebarButtonLayout"', 1
        )[0]
        self.assertIn(
            '"show_when": {"field": "sidebarActionsMode", "values": ["list", "collapsed"]}',
            dashed,
        )
        self.assertIn(
            '.osw-designer-deck .osw-btnorder[data-field-host].is-hidden {',
            CSS,
        )
        self.assertIn('display: none;', CSS)

    def test_stats_widgets_keep_distinct_accents_and_retention_glyph_pickers(self):
        theme_store = (ROOT / "settings_web" / "theme_store.py").read_text(encoding="utf-8")
        for key in ("studied", "time", "pace", "retention"):
            self.assertIn(f'"{key}":', CONFIG)
            self.assertIn(f'"swidget_color_{key}"', JS)
        self.assertIn("stats_widget_accents =", theme_store)
        self.assertIn('"id": "swidget_icon_retention_star"', SCHEMA)
        self.assertIn('"deck_placement": "right", "deck_icon_tile": True', SCHEMA)
        self.assertIn('"retention_star": "system:star.svg"', CONFIG)
        self.assertIn("swidget_icon_retention_star:", JS)
        self.assertIn('field.deckPlacement === "right"', JS)
        self.assertIn("_stats_widget_star_html", RENDERER)
        self.assertIn("stats-widget-star", RENDERER)
        self.assertIn(".stats-widget-star", MENU_CSS)


if __name__ == "__main__":
    unittest.main()
