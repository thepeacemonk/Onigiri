import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = (ROOT / "core/config.py").read_text(encoding="utf-8")
INIT = (ROOT / "__init__.py").read_text(encoding="utf-8")
SCHEMA = (ROOT / "settings_web" / "schema.py").read_text(encoding="utf-8")
SCRIPT = (ROOT / "web" / "settings.js").read_text(encoding="utf-8")
SETTINGS_CSS = (ROOT / "web" / "settings.css").read_text(encoding="utf-8")
SETTINGS_RENDER = (ROOT / "settings_web" / "render.py").read_text(
    encoding="utf-8"
)
PATCHER = (ROOT / "rendering/patcher.py").read_text(encoding="utf-8")
THINGS_INIT = (ROOT / "things_theme" / "__init__.py").read_text(
    encoding="utf-8"
)
THINGS_HOME_FILTER = (ROOT / "things_theme" / "web" / "homefilter.js").read_text(
    encoding="utf-8"
)
THINGS_DECKLIST = (ROOT / "things_theme" / "web" / "decklist.js").read_text(
    encoding="utf-8"
)
THINGS_DECKLIST_CSS = (
    ROOT / "things_theme" / "web" / "decklist.css"
).read_text(encoding="utf-8")
THINGS_DECKOPTS = (ROOT / "things_theme" / "web" / "deckopts.js").read_text(
    encoding="utf-8"
)
THINGS_SIDEBAR = (ROOT / "things_theme" / "web" / "sidebar.js").read_text(
    encoding="utf-8"
)
THINGS_SIDEBAR_CSS = (
    ROOT / "things_theme" / "web" / "sidebar.css"
).read_text(encoding="utf-8")
THINGS_THEME_CSS = (
    ROOT / "things_theme" / "web" / "theme.css"
).read_text(encoding="utf-8")
MAC_TITLEBAR = (ROOT / "integrations/mac_titlebar.py").read_text(encoding="utf-8")


class ThingsThemeIntegrationTests(unittest.TestCase):
    def test_standalone_folder_became_an_internal_package(self):
        self.assertFalse((ROOT / "Things-theme").exists())
        self.assertTrue((ROOT / "things_theme" / "web" / "theme.css").exists())
        self.assertIn("EMBEDDED_IN_ONIGIRI = True", THINGS_INIT)
        self.assertNotIn("setWebExports", THINGS_INIT)
        self.assertIn('setWebExports(__name__, r"(.*)")', INIT)

    def test_classic_is_the_safe_default(self):
        self.assertIn('"onigiri_ui_theme": "classic"', CONFIG)
        self.assertIn('"default": "classic"', SCHEMA)

    def test_deck_renderer_dispatches_by_selected_theme(self):
        self.assertIn("def _render_selected_deck_browser", INIT)
        self.assertIn("def _load_things_theme", INIT)
        self.assertIn("return _anki_render_page", INIT)
        self.assertIn("return onigiri_renderer.render_onigiri_deck_browser", INIT)
        self.assertIn(".on_webview_will_set_content(web_content, context)", INIT)

    def test_settings_offer_visual_selector_and_small_customizer(self):
        self.assertIn('"layout": "theme_style"', SCHEMA)
        self.assertIn('"value": "things3"', SCHEMA)
        self.assertIn('"layout": "things_theme"', SCHEMA)
        for field_id in (
            "things_theme_mode",
            "things_show_due",
            "things_show_tasks",
            "things_show_active_cards",
            "things_show_progress",
            "things_show_review_chart",
            "things_show_heatmap",
            "things_sidebar_opacity",
            "things_sidebar_blur",
            "things_deck_opacity",
            "things_deck_blur",
            "things_widgets_opacity",
            "things_widgets_blur",
            "things_heatmap_color",
            "things_weekly_reviews_color",
            "things_progress_color",
            "things_active_new_color",
            "things_active_learning_color",
            "things_active_relearning_color",
            "things_active_young_color",
            "things_active_mature_color",
        ):
            self.assertIn(f'"id": "{field_id}"', SCHEMA)
        self.assertIn('_image_field(\n                "things_background_image"', SCHEMA)
        self.assertIn('"things_main_background",', SCHEMA)
        self.assertIn('"things_sidebar_background",', SCHEMA)
        self.assertIn('"inherit_main_background"', SETTINGS_RENDER)
        self.assertNotIn('"id": "things_density"', SCHEMA)
        for removed_field_id in ("things_accent",):
            self.assertNotIn(f'"id": "{removed_field_id}"', SCHEMA)
        self.assertIn("function renderThemeStyle", SCRIPT)
        self.assertIn("function renderThingsTheme", SCRIPT)

    def test_sidebar_settings_are_split_by_theme_family(self):
        sidebar_page = SCHEMA.split("def _sidebar_page", 1)[1].split(
            "# ── Gallery", 1
        )[0]
        partition = SCHEMA.split("def _things_sections_by_page", 1)[1].split(
            "def _legacy_page", 1
        )[0]
        self.assertIn('"field": "onigiri_ui_theme"', sidebar_page)
        self.assertIn('"values": ["classic"]', sidebar_page)
        for section_id in (
            "kome_dashboard",
            "kome_main_appearance",
            "kome_charts",
            "kome_sidebar_content",
            "kome_sidebar_appearance",
            "kome_sidebar_colors",
        ):
            self.assertIn(f'"{section_id}"', partition)
        self.assertEqual(partition.count("preview=True"), 6)
        self.assertIn("classic_sections + kome_sidebar", sidebar_page)
        self.assertIn('"showWhen": page.get("show_when")', SETTINGS_RENDER)
        self.assertIn("function pageIsAvailable", SCRIPT)
        self.assertNotIn(
            'page.id === "sidebar" && values.onigiri_ui_theme !== "classic"',
            SCRIPT,
        )
        self.assertIn("refreshPageVisibility();", SCRIPT)

    def test_things_main_menu_preview_reuses_production_assets(self):
        self.assertIn("def things_preview_context", SETTINGS_RENDER)
        for asset in (
            '"theme.css"',
            '"sidebar.css"',
            '"decklist.css"',
            'read_things_asset("sidebar.js")',
            'read_things_asset("decklist.js")',
        ):
            self.assertIn(asset, SETTINGS_RENDER)
        self.assertIn('"thingsPreview": things_preview_context()', SETTINGS_RENDER)
        self.assertIn('iframe.srcdoc = buildThingsPreviewDocument(previewMode)', SCRIPT)
        self.assertIn("THINGS_PREVIEW_WIDTH = 1440", SCRIPT)
        self.assertIn("new ResizeObserver(syncScale).observe(stage)", SCRIPT)
        self.assertIn("str(\"dynamic_mode\", \"Dynamic mode\")", SCRIPT)
        self.assertIn("OSW_SUN_ICON : OSW_MOON_ICON", SCRIPT)
        preview = SCRIPT.split("function buildThingsPreviewDocument", 1)[1].split(
            "function renderThingsTheme", 1
        )[0]
        self.assertIn("window.__baOpts={cmdk:false", preview)
        self.assertNotIn("window.__baOpts={cmdk:true", preview)

    def test_things_background_and_glass_controls_reach_preview_and_runtime(self):
        self.assertIn('"background_light": ""', CONFIG)
        self.assertIn('"background_dark": ""', CONFIG)
        self.assertIn('"background_theme_mode": "separate"', CONFIG)
        self.assertIn('"background_light", "")', THINGS_INIT)
        self.assertIn('"background_dark", "")', THINGS_INIT)
        self.assertIn("_background_rules(cfg)", THINGS_INIT)
        self.assertIn("values.things_main_background_light", SCRIPT)
        self.assertIn("values.things_main_background_dark", SCRIPT)
        self.assertIn('"sidebar_background_light": ""', CONFIG)
        self.assertIn('"sidebar_background_dark": ""', CONFIG)
        self.assertIn("values.things_sidebar_background_light", SCRIPT)
        self.assertIn("values.things_sidebar_background_dark", SCRIPT)
        self.assertIn("--rf-sidebar-light-bg", SCRIPT)
        self.assertIn("--rf-sidebar-dark-bg", SCRIPT)
        self.assertIn('"background_image": ""', CONFIG)
        self.assertIn('"surface_effects": {', CONFIG)
        self.assertIn('imageUrl("main_bg", values.things_background_image)', SCRIPT)
        self.assertIn('data-rf-background="image"', SCRIPT)
        self.assertIn("_surface_effect_vars(cfg)", THINGS_INIT)
        self.assertIn("d.dataset.rfBackground='image'", THINGS_INIT)
        self.assertIn('--rf-background-image:url("{url}")', THINGS_INIT)
        self.assertIn(':root[data-rf-background="image"]', THINGS_THEME_CSS)
        self.assertIn("--rf-widgets-opacity", THINGS_THEME_CSS)
        self.assertIn("--rf-sidebar-opacity", THINGS_SIDEBAR_CSS)
        self.assertIn("--rf-decks-opacity", THINGS_DECKLIST_CSS)
        self.assertIn("visible_opacity = min(opacity, 100 - blur * 0.3)", THINGS_INIT)
        self.assertIn("const visibleOpacity = Math.min", SCRIPT)
        self.assertIn("will-change: backdrop-filter", THINGS_SIDEBAR_CSS)

    def test_kome_uses_onigiris_exact_base_canvas(self):
        self.assertIn('"bg": "#eeeeee"', THINGS_INIT)
        self.assertIn('"bg": "#171717"', THINGS_INIT)
        self.assertIn('== "#f6f3ec"', THINGS_INIT)
        self.assertIn('== "#0b0c0f"', THINGS_INIT)
        self.assertIn("--rf-glow: none", THINGS_THEME_CSS)
        self.assertIn(
            "background: var(--rf-sidebar-bg, var(--rf-paper));",
            THINGS_SIDEBAR_CSS,
        )

    def test_things_customizer_uses_compact_two_column_grid(self):
        self.assertIn(
            "grid-template-columns: repeat(2, minmax(0, 1fr))",
            SETTINGS_CSS,
        )
        self.assertIn(".osw-things3-controls .osw-slider-track", SETTINGS_CSS)

    def test_theme_cards_include_requested_decorations(self):
        theme_style = SCRIPT.split("function renderThemeStyle", 1)[1].split(
            "function refreshThemeStyleCards", 1
        )[0]
        self.assertIn("osw-theme-style-decoration", theme_style)
        self.assertIn('decoration.textContent = "米"', theme_style)
        self.assertIn('"system:onigiri.svg"', theme_style)
        self.assertIn("is-onigiri", theme_style)
        self.assertIn('"by Max"', theme_style)
        self.assertIn("osw-theme-style-name", theme_style)
        self.assertIn("osw-theme-style-desc", theme_style)

    def test_things_visibility_and_active_card_colors_reach_runtime(self):
        self.assertIn('cfg["density"] = "comfortable"', THINGS_INIT)
        self.assertIn('cfg.get("show_review_chart", True)', THINGS_INIT)
        self.assertIn("--rf-{mode}-active-{name}", THINGS_INIT)
        self.assertIn("--rf-active-new", THINGS_SIDEBAR_CSS)
        self.assertIn("values.things_show_active_cards", SCRIPT)
        self.assertIn("values.things_active_mature_color", SCRIPT)

    def test_things_dashboard_colors_reach_preview_and_runtime(self):
        for key in (
            "heatmap_color", "weekly_reviews_color", "progress_color"
        ):
            self.assertIn(f'"{key}": DEFAULT_ACCENT_COLOR', CONFIG)
        self.assertIn('("heatmap", "heatmap_color", "--heatmap-color")', THINGS_INIT)
        self.assertIn('("weekly-reviews", "weekly_reviews_color", "--accent-color")', THINGS_INIT)
        self.assertIn('("progress", "progress_color", "--accent-color")', THINGS_INIT)
        self.assertIn('f"--rf-{mode}-{name}-color:{value};"', THINGS_INIT)
        self.assertIn("values.things_heatmap_color", SCRIPT)
        self.assertIn("values.things_weekly_reviews_color", SCRIPT)
        self.assertIn("values.things_progress_color", SCRIPT)
        self.assertIn("var(--rf-weekly-reviews-color", THINGS_THEME_CSS)
        self.assertIn("var(--rf-progress-color", THINGS_DECKLIST_CSS)
        self.assertIn("var(--rf-progress-color", THINGS_SIDEBAR_CSS)

    def test_things_uses_shared_palette_and_official_gallery(self):
        self.assertIn(
            'cfg["theme"] = root.get("onigiriThemeMode", "system")',
            THINGS_INIT,
        )
        self.assertIn('cfg["_palette_light"] = light', THINGS_INIT)
        self.assertIn("values.theme_accent_light", SCRIPT)
        gallery = SCHEMA.split('"id": "theme_gallery"', 1)[1].split(
            "def _things_theme_section", 1
        )[0]
        self.assertNotIn('"show_when"', gallery)

    def test_things_dashboard_uses_native_things_widgets(self):
        for key in (
            "sidebar_hero", "sidebar_donut", "sidebar_tasks",
            "sidebar_progress",
        ):
            self.assertIn(f'cfg.get("{key}", True)', THINGS_INIT)
        self.assertIn("build_review_chart_html", THINGS_INIT)
        self.assertIn('class="ba-analytics{single}"', THINGS_INIT)
        self.assertIn("content.stats = practice", THINGS_INIT)
        self.assertIn('web_content.js.append(f"{WEB}/homefilter.js")', THINGS_INIT)
        self.assertIn(".ba-practice", THINGS_HOME_FILTER)
        self.assertIn("MutationObserver", THINGS_HOME_FILTER)

    def test_classic_only_tool_widgets_are_hidden_for_things3(self):
        for section_id in ("prep_widget", "hashi_widget"):
            section = SCHEMA.split(f'"{section_id}"', 1)[1].split(
                "fields=widget_fields", 1
            )[0]
            self.assertIn('"field": "onigiri_ui_theme"', section)
            self.assertIn('"values": ["classic"]', section)

    def test_prep_station_and_hashi_pages_are_hidden_for_things3(self):
        for function_name, next_function, page_id in (
            ("_prep_station_page", "_hashi_note_options", "prepstation"),
            ("_hashi_notes_page", "_pomodoro_page", "hashinotes"),
        ):
            page = SCHEMA.split(f"def {function_name}", 1)[1].split(
                f"def {next_function}", 1
            )[0]
            self.assertIn(f'"id": "{page_id}"', page)
            self.assertIn('"field": "onigiri_ui_theme"', page)
            self.assertIn('"values": ["classic"]', page)
        self.assertIn(
            'page.id === "prepstation" || page.id === "hashinotes"',
            SCRIPT,
        )

    def test_things_chart_and_heatmap_share_one_date_window(self):
        self.assertIn(
            "start_idx = today_idx - (weeks * 7 - 1)",
            THINGS_INIT,
        )
        self.assertIn("visible_counts = {", THINGS_INIT)
        self.assertIn("total = sum(visible_counts.values())", THINGS_INIT)
        self.assertIn(
            "build_review_chart_html(heatmap_weeks * 7)",
            THINGS_INIT,
        )
        self.assertIn("weekly = []", THINGS_INIT)
        self.assertIn("grid_start = start_idx - dow(start_idx)", THINGS_INIT)
        self.assertNotIn("cumulative = []", THINGS_INIT)

    def test_overview_assets_are_attached_to_patched_body(self):
        self.assertIn("overview_component_css", PATCHER)
        self.assertIn('overview_asset_link("overview.css")', PATCHER)
        self.assertIn('overview_asset_link("overview_stats.css")', PATCHER)
        self.assertIn("+ generate_dynamic_css(conf)", PATCHER)

    def test_things_subdecks_render_as_parent_scoped_branches(self):
        self.assertIn("parentDid: parentDid", THINGS_DECKLIST)
        self.assertIn('data-parent-did=', THINGS_DECKLIST)
        self.assertIn("--ad-indent:", THINGS_DECKLIST)
        self.assertNotIn(".ad-list-tree::before", THINGS_DECKLIST_CSS)
        self.assertNotIn(".ad-list-tree::after", THINGS_DECKLIST_CSS)
        self.assertIn("grid-template-columns: var(--ad-row-cols)", THINGS_DECKLIST_CSS)
        self.assertNotIn(
            '.ad-list-row[data-parent-did] {', THINGS_DECKLIST_CSS
        )
        self.assertNotIn(
            '.ad-list-row[data-current="true"] {', THINGS_DECKLIST_CSS
        )

    def test_things_reuses_classic_deck_icon_chooser_and_storage(self):
        self.assertIn('"onigiri_custom_deck_icons"', THINGS_INIT)
        self.assertIn("def _resolved_deck_icon", THINGS_INIT)
        self.assertIn('icon_modal.js', THINGS_INIT)
        self.assertIn("onigiri_ctx_change_icon:", THINGS_DECKLIST)
        self.assertIn('label: window.onigiriText("Change icon…")', THINGS_DECKOPTS)
        self.assertIn("onigiri_ctx_change_icon:", THINGS_DECKOPTS)

    def test_deck_options_uses_inline_lucide_gear(self):
        self.assertIn('class="ad-list-gear-icon"', THINGS_DECKLIST)
        self.assertIn('<circle cx="12" cy="12" r="3"/>', THINGS_DECKLIST)
        self.assertNotIn('/_anki/imgs/gears.svg', THINGS_DECKLIST)
        self.assertIn(".ad-list-gear-icon", THINGS_DECKLIST_CSS)
        self.assertNotIn(".ad-list-gear-img", THINGS_DECKLIST_CSS)

    def test_active_cards_uses_compact_segmented_donut(self):
        self.assertIn('class="ba-side-donut-svg"', THINGS_SIDEBAR)
        self.assertIn('data-donut-segment=', THINGS_SIDEBAR)
        self.assertIn("strokeDasharray", THINGS_SIDEBAR)
        self.assertNotIn(
            '<strong data-donut-total>—</strong><span>cards</span>',
            THINGS_SIDEBAR,
        )
        self.assertIn("stroke-linecap: round", THINGS_SIDEBAR_CSS)
        self.assertIn("text-overflow: ellipsis", THINGS_SIDEBAR_CSS)

    def test_things_sidebar_clears_macos_traffic_lights(self):
        self.assertIn('_mac_titlebar.inset_css("things3")', THINGS_INIT)
        self.assertIn('elif context_kind == "things3"', MAC_TITLEBAR)
        self.assertIn("var(--onigiri-mac-titlebar-inset) + 12px", MAC_TITLEBAR)

    def test_tasks_add_button_uses_lucide_plus_without_native_chrome(self):
        self.assertIn('class="ba-side-tasks-add-icon"', THINGS_SIDEBAR)
        self.assertIn('<path d="M5 12h14"/>', THINGS_SIDEBAR)
        self.assertIn('<path d="M12 5v14"/>', THINGS_SIDEBAR)
        self.assertIn("background-image: none !important", THINGS_SIDEBAR_CSS)
        self.assertIn("box-shadow: none !important", THINGS_SIDEBAR_CSS)
        self.assertIn("outline: 2px solid var(--rf-accent)", THINGS_SIDEBAR_CSS)

    def test_task_remove_button_uses_lucide_x_without_native_chrome(self):
        self.assertIn('class="ba-side-task-del-icon"', THINGS_SIDEBAR)
        self.assertIn('<path d="M18 6 6 18"/>', THINGS_SIDEBAR)
        self.assertIn('<path d="m6 6 12 12"/>', THINGS_SIDEBAR)
        remove_rules = THINGS_SIDEBAR_CSS.split(
            ".ba-side .ba-side-task-del,", 1
        )[1]
        self.assertIn("background-image: none !important", remove_rules)
        self.assertIn("box-shadow: none !important", remove_rules)


if __name__ == "__main__":
    unittest.main()
