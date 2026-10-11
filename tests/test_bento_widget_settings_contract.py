"""Static contracts for the Bento settings WebUI shared across add-ons.

These checks deliberately avoid importing ``aqt`` so they run outside Anki.
"""

import ast
import unittest
from pathlib import Path


ADDONS = Path(__file__).resolve().parents[2]


WEBUI_TARGETS = {
    "73838120": ("BerrySettingsDialog", "generate_html"),
    "516325516": ("SettingsDialog", "deck_widget.generate_html"),
    "519723565": ("SettingsDialog", "addon.generate_html"),
    "691162538": ("SettingsDialog", "addon.generate_html"),
    "1799253175": ("LofiSettingsDialog", "deck_widget.generate_html"),
    "643961895": ("SettingsDialog", "generate_battery_html"),
    "585575504": ("SenchadoSettings", "generate_widget_html"),
    "629799722": ("SettingsDialog", "addon.generate_html"),
    "DuoAnki": ("DuoAnkiWebSettings", "widget.render_widget"),
}

LOGO_TARGETS = {
    "73838120": "berry_logo.svg",
    "516325516": "Focumon.png",
    "519723565": "global_logo.svg",
    "691162538": "assets/hours_logo.svg",
    "1799253175": "assets/lofi_town_logo.png",
    "643961895": "power_logo.svg",
    "585575504": "senchado_timer_logo.svg",
    "629799722": "sticky_logo.svg",
    "DuoAnki": "icons/streakIcon.png",
}

MINI_LOGO_TARGETS = {
    "73838120": "berry_mini_logo.svg",
    "519723565": "global_mini_logo.svg",
    "691162538": "assets/hours_mini_logo.svg",
    "643961895": "power_mini_logo.svg",
    "585575504": "senchado_timer_mini_logo.svg",
    "629799722": "mini_sticky_logo.svg",
    "DuoAnki": "icons/streakIcon.png",
}


def _classes(source, name):
    tree = ast.parse(source)
    return sorted(
        (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == name),
        key=lambda node: node.lineno,
    )


class BentoWidgetSettingsContractTest(unittest.TestCase):
    def test_shared_shell_assets_use_onigiri_structure(self):
        api = (ADDONS / "1011095603" / "api" / "widget_settings.py").read_text()
        css = (ADDONS / "1011095603" / "web" / "bento_settings.css").read_text()
        js = (ADDONS / "1011095603" / "web" / "bento_settings.js").read_text()
        html = (ADDONS / "1011095603" / "web" / "bento_settings.html").read_text()

        self.assertIn("class BentoSettingsDialog", api)
        self.assertIn("def preview_document", api)
        self.assertIn("bws-rail", html)
        self.assertIn("bws-page", html)
        self.assertIn("bwsBrandMiniLogo", html)
        self.assertIn('"miniLogo": self.mini_logo', api)
        self.assertIn("has-mini-logo", js)
        self.assertIn("--bws-outer", css)
        self.assertIn("--bws-panel", css)
        self.assertIn("--bws-surface", css)
        self.assertIn("%%T:settings_web_autosave_idle%%", html)
        self.assertIn("render_html_strings(_read_asset", api)
        self.assertIn("function flush()", js)
        self.assertIn("function finish()", js)
        self.assertIn("srcdoc", js)

    def test_preview_iframe_survives_settings_page_navigation(self):
        api = (ADDONS / "1011095603" / "api" / "widget_settings.py").read_text()
        js = (ADDONS / "1011095603" / "web" / "bento_settings.js").read_text()
        css = (ADDONS / "1011095603" / "web" / "bento_settings.css").read_text()

        self.assertIn('previewCard.id = "bwsPreviewCard"', js)
        self.assertIn('if (child !== previewCard) child.remove();', js)
        self.assertIn('var source = html || "";', js)
        self.assertIn('var next = node("iframe", "bws-preview-next")', js)
        self.assertIn('event.data === "bws-preview-ready"', js)
        self.assertIn('active.classList.add("bws-preview-old")', js)
        self.assertIn("parent.postMessage('bws-preview-ready','*')", api)
        self.assertIn("iframe.bws-preview-next", css)
        self.assertNotIn(
            'host.innerHTML = "";\n    var previewCard = node("section", "bws-preview-card");',
            js,
        )

    def test_informational_pages_can_hide_widget_preview(self):
        api = (ADDONS / "1011095603" / "api" / "widget_settings.py").read_text()
        js = (ADDONS / "1011095603" / "web" / "bento_settings.js").read_text()
        duo = (ADDONS / "DuoAnki" / "settings.py").read_text()

        self.assertIn("show_preview: bool = True", api)
        self.assertIn('"showPreview": bool(show_preview)', api)
        self.assertIn("previewCard.hidden = page.showPreview === false", js)
        self.assertIn('"Duo Activity"', duo)
        self.assertIn("show_preview=False", duo)
        self.assertNotIn('{"value": "activity", "label": "Activity"}', duo)

    def test_global_vertical_preview_uses_its_natural_height(self):
        source = (ADDONS / "519723565" / "settings.py").read_text()

        self.assertIn('updated.get("view_mode", "vertical") == "vertical"', source)
        self.assertIn("Global's vertical face is a taller", source)
        self.assertIn("height: auto !important", source)
        self.assertIn("max-height: none !important", source)
        self.assertIn("overflow: visible !important", source)

    def test_global_preview_applies_opacity_to_the_whole_card(self):
        source = (ADDONS / "519723565" / "settings.py").read_text()

        self.assertIn("def _preview_opacity_css(config):", source)
        self.assertIn("opacity: {opacity:.4f} !important", source)
        self.assertIn("css += _preview_opacity_css(self.config)", source)
        self.assertIn("css += _preview_opacity_css(updated)", source)

    def test_onigiri_owns_layout_with_standalone_footprint_fallback(self):
        api = (ADDONS / "1011095603" / "api" / "widget_settings.py").read_text()
        js = (ADDONS / "1011095603" / "web" / "bento_settings.js").read_text()
        html = (ADDONS / "1011095603" / "web" / "bento_settings.html").read_text()

        self.assertIn('"onigiriConnected": self.onigiri_connected', api)
        self.assertIn("if not self.onigiri_connected:", api)
        self.assertIn('id="bwsBridgeStatus"', html)
        self.assertIn('id="bwsFootprint" hidden', html)
        self.assertIn('footprint.hidden = connected;', js)
        self.assertIn("Onigiri installed · Bento bridge active", js)
        for folder in WEBUI_TARGETS:
            with self.subTest(folder=folder):
                source = (ADDONS / folder / "settings.py").read_text()
                self.assertNotIn('_bws.page("bento", "Bento layout"', source)
                self.assertNotIn('_bws.section("Bento footprint"', source)

    def test_shared_controls_are_flat_custom_and_lucide(self):
        api = (ADDONS / "1011095603" / "api" / "widget_settings.py").read_text()
        css = (ADDONS / "1011095603" / "web" / "bento_settings.css").read_text()
        js = (ADDONS / "1011095603" / "web" / "bento_settings.js").read_text()
        html = (ADDONS / "1011095603" / "web" / "bento_settings.html").read_text()

        self.assertIn("body.fancy button", css)
        self.assertIn("box-shadow: none !important", css)
        self.assertIn("background-image: none !important", css)
        self.assertIn("bws-select-menu", js)
        self.assertNotIn('node("select"', js)
        self.assertIn("bws-slider-track", js)
        self.assertIn("grid-template-columns: 62px minmax(0, 1fr)", css)
        self.assertIn('thumb.style.left = "max(6px, min(calc("', js)
        self.assertIn('window.addEventListener("pointermove", onPointerMove)', js)
        self.assertIn('send("haptic", "2")', js)
        self.assertIn('if action == "haptic"', api)
        self.assertIn("function openColorPicker", js)
        self.assertIn("var LUCIDE", js)
        # Distinctive paths from Lucide's upstream Paintbrush and CloudSun
        # assets prevent lookalike or partially copied glyphs from returning.
        self.assertIn("M18.376 2.622a1 1 0 1 1 3.002 3.002", js)
        self.assertIn("M15.947 12.65a4 4 0 0 0-5.925-4.128", js)
        self.assertNotIn("L17.36 17.568", js)
        self.assertIn('class="bws-done-action-icon"', html)
        self.assertIn("transition: width 300ms ease, transform 150ms ease", css)
        self.assertIn("width: calc(100% - 8px)", css)
        self.assertIn("transform: translateX(2px)", css)
        self.assertIn("transform: scale(.95)", css)
        self.assertNotIn("Search settings", html)
        self.assertNotIn("bwsSearch", js)
        self.assertNotIn('confirm("Restore this widget', js)
        self.assertIn("function confirmReset()", js)
        self.assertIn("bws-confirm-dialog", css)
        self.assertIn('role", "alertdialog"', js)
        self.assertIn(".bws-preview-stage {\n  position: relative;\n  height: 390px;\n  padding: 0;", css)
        self.assertIn("border-radius: 0;", css)

        gradient_lines = [
            line for line in css.splitlines() if "gradient(" in line
        ]
        self.assertTrue(gradient_lines)
        self.assertTrue(
            all("bws-colorpick" in line for line in gradient_lines),
            "only the functional HSV colour picker may use gradients",
        )

    def test_switch_thumb_keeps_equal_insets_in_both_states(self):
        css = (ADDONS / "1011095603" / "web" / "bento_settings.css").read_text()
        global_settings = (ADDONS / "519723565" / "settings.py").read_text()

        self.assertIn("flex: 0 0 42px", css)
        self.assertIn("border: 0 !important", css)
        self.assertIn("left: auto; right: 3px", css)
        self.assertIn("def _thumb_position(self, checked):", global_settings)
        self.assertIn("self._thumb_position(checked)", global_settings)
        self.assertIn("self._thumb_position(self.isChecked())", global_settings)

    def test_native_widgets_end_with_shared_webui_and_real_renderer(self):
        for folder, (class_name, renderer_token) in WEBUI_TARGETS.items():
            with self.subTest(folder=folder):
                source = (ADDONS / folder / "settings.py").read_text()
                classes = _classes(source, class_name)
                self.assertTrue(classes)
                adapter = classes[-1]
                expected_base = "bws.BentoSettingsDialog" if folder == "DuoAnki" else "_bws.BentoSettingsDialog"
                self.assertIn(expected_base, ast.unparse(adapter.bases))
                self.assertTrue(
                    all(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in adapter.body),
                    "adapter classes must not absorb trailing legacy statements",
                )
                initializer = next(
                    node for node in adapter.body
                    if isinstance(node, ast.FunctionDef) and node.name == "__init__"
                )
                self.assertTrue(
                    ast.unparse(initializer.body[-1]).startswith("super().__init__("),
                    "adapter constructors must end after initializing the shared WebUI",
                )
                self.assertIn("1011095603.api.widget_settings", source)
                if folder == "DuoAnki":
                    self.assertIn("bento.is_onigiri_active()", source)
                else:
                    self.assertIn("Onigiri Bento API is not active", source)
                self.assertIn(renderer_token, source)

    def test_each_shared_widget_uses_its_packaged_logo(self):
        for folder, relative_logo in LOGO_TARGETS.items():
            with self.subTest(folder=folder):
                source = (ADDONS / folder / "settings.py").read_text()
                self.assertIn("logo_path=", source)
                self.assertTrue((ADDONS / folder / relative_logo).is_file())

        for folder, relative_logo in MINI_LOGO_TARGETS.items():
            with self.subTest(folder=folder, kind="mini"):
                source = (ADDONS / folder / "settings.py").read_text()
                self.assertIn("mini_logo_path=", source)
                self.assertTrue((ADDONS / folder / relative_logo).is_file())

    def test_byte_keeps_full_webui_and_production_face_preview(self):
        html = (ADDONS / "Byte" / "web" / "settings.html").read_text()
        dialog = (ADDONS / "Byte" / "settings.py").read_text()

        for token in ("bws-shell", "settingsNav", "bws-page-head", "pFace"):
            self.assertIn(token, html)
        self.assertIn("%%T:settings_web_autosave_idle%%", html)
        self.assertIn("render_html_strings(_read_asset", api)
        self.assertIn("var LUCIDE", html)
        self.assertIn("M11.017 2.814a1 1 0 0 1 1.966 0", html)
        self.assertIn('id="brandFace"', html)
        self.assertIn("body.fancy button", html)
        self.assertNotIn("gradient(", html)
        self.assertIn('class="byte-slider"', html)
        self.assertIn('cmd == "byte:done"', dialog)
        self.assertIn("DEFAULT_SIZE = (1120, 720)", dialog)

    def test_excluded_widgets_do_not_import_shared_settings_shell(self):
        for folder in ("Astra", "8BitDo_Studies", "League"):
            for path in (ADDONS / folder).glob("*.py"):
                with self.subTest(path=path):
                    self.assertNotIn("1011095603.api.widget_settings", path.read_text())

    def test_stateful_widget_actions_remain_available(self):
        hours = (ADDONS / "691162538" / "settings.py").read_text()
        tea = (ADDONS / "585575504" / "settings.py").read_text()

        self.assertIn('"add-background-image"', hours)
        self.assertIn('"delete-background-image"', hours)
        self.assertIn("def _refresh_favorite_fields", tea)
        self.assertIn('"save-current-favorite"', tea)


if __name__ == "__main__":
    unittest.main()
