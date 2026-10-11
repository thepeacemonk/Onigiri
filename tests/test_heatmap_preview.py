import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HEATMAP_JS = (ROOT / "web" / "heatmap.js").read_text(encoding="utf-8")
SETTINGS_JS = (ROOT / "web" / "settings.js").read_text(encoding="utf-8")
SETTINGS_HTML = (ROOT / "web" / "settings.html").read_text(encoding="utf-8")
RENDER_PY = (ROOT / "settings_web" / "render.py").read_text(encoding="utf-8")


class HeatmapPreviewTests(unittest.TestCase):
    def test_settings_embeds_live_heatmap_runtime(self):
        self.assertIn("/*__ONIGIRI_HEATMAP_JS__*/", SETTINGS_HTML)
        self.assertIn('read_web_asset("heatmap.js")', RENDER_PY)
        self.assertIn(
            '.replace("/*__ONIGIRI_HEATMAP_JS__*/", heatmap_js)',
            RENDER_PY,
        )

    def test_live_renderer_accepts_id_or_element(self):
        self.assertIn(
            "typeof containerTarget === 'string'",
            HEATMAP_JS,
        )
        self.assertIn("document.getElementById(containerTarget)", HEATMAP_JS)

    def test_detached_settings_preview_passes_its_container_element(self):
        self.assertIn(
            "window.OnigiriHeatmap.render(\n"
            "      container, HEATMAP_PREVIEW_DATA, previewConfig",
            SETTINGS_JS,
        )
        self.assertNotIn(
            "window.OnigiriHeatmap.render(\n"
            '      "onigiri-heatmap-container", HEATMAP_PREVIEW_DATA, previewConfig',
            SETTINGS_JS,
        )

    def test_preview_header_uses_the_live_theme_palette(self):
        start = SETTINGS_JS.index("function heatmapThemeVars")
        end = SETTINGS_JS.index("function heatmapPaintCosmetics", start)
        theme_helper = SETTINGS_JS[start:end]

        self.assertIn('vals["theme_fg" + suffix]', theme_helper)
        self.assertIn('vals["theme_subtle" + suffix]', theme_helper)
        self.assertIn('vals["sb_highlight_bg" + suffix]', theme_helper)
        self.assertIn('vals["theme_border" + suffix]', theme_helper)
        self.assertIn("const themeVars = heatmapThemeVars(vals, isDark);", SETTINGS_JS)
        self.assertIn(
            'container.style.setProperty("--highlight-bg", themeVars.highlightBg);',
            SETTINGS_JS,
        )
        self.assertNotIn('highlightBg: "#2e2e2e"', SETTINGS_JS)


if __name__ == "__main__":
    unittest.main()
