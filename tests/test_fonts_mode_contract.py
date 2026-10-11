import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / "settings_web" / "schema.py").read_text(encoding="utf-8")
RENDER = (ROOT / "settings_web" / "render.py").read_text(encoding="utf-8")
SCRIPT = (ROOT / "web" / "settings.js").read_text(encoding="utf-8")
STYLES = (ROOT / "web" / "settings.css").read_text(encoding="utf-8")
PATCHER = (ROOT / "patcher.py").read_text(encoding="utf-8")
CONFIG = (ROOT / "config.py").read_text(encoding="utf-8")
INIT = (ROOT / "__init__.py").read_text(encoding="utf-8")
TEMPLATES = (ROOT / "templates.py").read_text(encoding="utf-8")
RENDERER = (ROOT / "onigiri_renderer.py").read_text(encoding="utf-8")
INJECTOR = (ROOT / "web" / "injector.js").read_text(encoding="utf-8")


class FontsModeContractTests(unittest.TestCase):
    def test_whole_font_sections_can_be_hidden(self):
        self.assertIn(
            ".osw-section.is-hidden { display: none !important; }",
            STYLES,
        )

    def test_section_visibility_survives_schema_serialization(self):
        self.assertIn('"showWhen": section.get("show_when")', RENDER)
        self.assertIn("showWhenMatches(section.showWhen)", SCRIPT)
        self.assertIn("block.hidden = sectionHidden", SCRIPT)

    def test_standalone_fonts_page_is_completely_removed(self):
        self.assertNotIn("def _fonts_page():", SCHEMA)
        self.assertNotIn("def _fonts_sections():", SCHEMA)
        self.assertNotIn("_fonts_page(),", SCHEMA)
        self.assertNotIn("onigiri_sidebar_font_mode", SCHEMA)
        self.assertNotIn("onigiri_sidebar_font_mode", PATCHER)

    def test_advanced_typography_is_distributed_to_component_pages(self):
        self.assertNotIn('"overview_typography"', SCHEMA)
        self.assertIn('"notification_typography"', SCHEMA)
        overview = SCHEMA[
            SCHEMA.index("def _overview_style_section():"):
            SCHEMA.index("def _reviewer_background_section():")
        ]
        self.assertIn('tr("overview_fonts", "Overview Fonts")', overview)
        self.assertIn(
            '("overview_title", "overview_text", "congrats_title", "congrats_text")',
            overview,
        )
        self.assertIn('section["font_menu_label"]', SCHEMA)
        self.assertIn('font_roles: renderFontRoles', SCRIPT)
        self.assertIn('"fontRoles": section.get("font_roles", [])', RENDER)

    def test_reviewer_fonts_live_with_bottom_bar_and_style_its_buttons(self):
        self.assertNotIn('"reviewer_typography"', SCHEMA)
        self.assertIn('tr("reviewer_fonts", "Reviewer Fonts")', SCHEMA)
        self.assertIn('("reviewer_controls",)', SCHEMA)
        self.assertIn(
            'designerFontRole(vals, "reviewer_controls", isDark, "main")',
            SCRIPT,
        )
        self.assertIn('#outer button .onigiri-answer-label,', PATCHER)
        self.assertIn('#outer #ansbut::before,', PATCHER)

    def test_reviewer_colors_use_compact_element_groups(self):
        self.assertIn('section["color_menu_label"]', SCHEMA)
        self.assertIn('tr("reviewer_colors", "Reviewer Colors")', SCHEMA)
        self.assertIn('"colorGroups": section.get("color_groups", [])', RENDER)
        self.assertIn('function compactColorMenuButton(section)', SCRIPT)
        self.assertIn('compactColorFieldIds[field.id]', SCRIPT)
        self.assertIn('.osw-organize-menu.is-widget-colors {', STYLES)

    def test_reviewer_utility_color_groups_are_independent(self):
        self.assertIn('tr("timer_button_active", "Timer Button (When Active)")', SCHEMA)
        self.assertIn('tr("show_answer_button", "Show Answer Button")', SCHEMA)
        self.assertIn(
            'tr("other_buttons_more_edit", "Other Buttons (More / Edit)")',
            SCHEMA,
        )
        self.assertIn('"bbar_show_answer_bg", "bbar_show_answer_text"', SCHEMA)
        self.assertIn('onigiri_reviewer_show_answer_btn_bg_light', CONFIG)
        self.assertIn('show_answer_bg_light = conf.get(', PATCHER)
        self.assertIn('#outer button.onigiri-show-answer-btn', PATCHER)
        self.assertIn('#outer button.onigiri-timer-out-btn,', PATCHER)
        self.assertIn('vals["bbar_show_answer_bg_" + suffix]', SCRIPT)

    def test_reviewer_color_editor_is_a_viewport_safe_preview_gallery(self):
        self.assertIn('"preview_bg": "bbar_show_answer_bg"', SCHEMA)
        self.assertIn('roleList.classList.add("osw-reviewer-color-gallery")', SCRIPT)
        self.assertIn('option.__paintColorGroupPreview = function ()', SCRIPT)
        self.assertIn('.osw-reviewer-color-gallery {', STYLES)
        self.assertIn('grid-template-columns: repeat(4, minmax(0, 1fr));', STYLES)
        self.assertIn('max-height: calc(100dvh - 24px);', STYLES)
        self.assertIn('overflow-y: auto;', STYLES)

    def test_overviewer_colors_use_the_compact_element_gallery(self):
        self.assertIn('tr("overview_colors", "Overview Colors")', SCHEMA)
        self.assertIn('"id": "ovstyle_colors_box"', SCHEMA)
        self.assertIn('"preview_border": "ovstyle_color_box_border"', SCHEMA)
        self.assertIn('"field": "ovstyle_sync_box_effect", "values": [False]', SCHEMA)
        self.assertIn('"id": "ovstyle_colors_study_button"', SCHEMA)
        self.assertIn('"id": "ovstyle_colors_new_count"', SCHEMA)
        self.assertIn('"id": "ovstyle_colors_learning_count"', SCHEMA)
        self.assertIn('"id": "ovstyle_colors_review_count"', SCHEMA)
        self.assertIn('role.preview_border + "_" + suffix', SCRIPT)
        self.assertIn('!role.show_when || showWhenMatches(role.show_when)', SCRIPT)

    def test_overviewer_notifications_and_body_use_the_right_column(self):
        overview_start = SCHEMA.index('"id": "overview_layout"')
        gallery_start = SCHEMA.index('section["color_menu_label"]', overview_start)
        overview_subsections = SCHEMA[overview_start:gallery_start]
        self.assertIn(
            '"id": "notifications",\n'
            '                "title": tr("notifications", "Notifications"),\n'
            '                "column": "right",',
            overview_subsections,
        )
        self.assertIn(
            '"id": "text",\n'
            '                "title": tr("text", "Text"),\n'
            '                "column": "right",',
            overview_subsections,
        )
        self.assertIn('subsection.column === "right"', SCRIPT)

    def test_designer_typeable_fields_have_a_clear_editable_surface(self):
        self.assertIn('.osw-text-input:hover {', STYLES)
        self.assertIn('.osw-textarea-input:hover {', STYLES)
        self.assertIn('box-shadow: 0 0 0 3px var(--osw-accent-a14);', STYLES)
        self.assertIn('.osw-designer-deck .osw-text-input,', STYLES)
        self.assertIn('.osw-designer-deck .osw-textarea-input,', STYLES)
        self.assertIn('.osw-designer-deck .osw-number {', STYLES)

    def test_reviewer_does_not_duplicate_overviewer_count_colors(self):
        self.assertNotIn('bbar_pre_new_bubble', SCHEMA)
        self.assertNotIn('bbar_pre_learn_bubble', SCHEMA)
        self.assertNotIn('bbar_pre_review_bubble', SCHEMA)
        self.assertIn(
            'vals["ovstyle_color_" + spec[0] + "_" + suffix]',
            SCRIPT,
        )

    def test_sidebar_fonts_are_attached_to_the_sections_they_affect(self):
        self.assertIn('("profile_name", "sidebar_small")', SCHEMA)
        self.assertNotIn('("sidebar_title", "sidebar_titles",', SCHEMA)
        self.assertNotIn('"sidebar_title": {', PATCHER)
        self.assertIn('("action_buttons",)', SCHEMA)
        self.assertIn('("deck_title", "deck_names")', SCHEMA)
        self.assertNotIn('"sidebar_typography"', SCHEMA)
        self.assertIn('"deck_title": {', PATCHER)
        self.assertIn('compactFontFieldIds[field.id]', SCRIPT)

    def test_sidebar_customization_keeps_only_sidebar_item_layout(self):
        self.assertIn('tr("sidebar_customization", "Sidebar Customization")', SCHEMA)
        self.assertIn('tr("sidebar_fonts", "Sidebar Fonts")', SCHEMA)
        self.assertIn('tr("layout_sidebar_items", "Layout · Sidebar Items")', SCHEMA)
        self.assertIn('tr("layout_items", "Layout Items")', SCHEMA)
        self.assertNotIn('tr("layout_widgets", "Layout · Widgets")', SCHEMA)
        self.assertIn('def _sidebar_layout_fields():', SCHEMA)
        self.assertNotIn('def _sidebar_profile_section():', SCHEMA)
        self.assertNotIn('def _sidebar_layout_section():', SCHEMA)
        self.assertNotIn('_sidebar_profile_section(),', SCHEMA)
        self.assertNotIn('_sidebar_layout_section(),', SCHEMA)
        self.assertIn('modern_menu_sidebar_item_margin_top:', SCRIPT)
        self.assertIn('"id": "modern_menu_sidebar_item_layout"', SCHEMA)
        self.assertIn('function renderWidgetLayoutControls(section)', SCRIPT)

    def test_sidebar_preview_and_configuration_columns_share_height(self):
        self.assertIn('.osw-designer-page-wrap.is-stage-side {', STYLES)
        self.assertIn('align-items: stretch;', STYLES)
        self.assertIn('.is-stage-side .osw-designer-preview-card {', STYLES)
        self.assertIn('height: 100%;', STYLES)
        self.assertIn('flex: 1 1 auto;', STYLES)

    def test_sidebar_preview_stays_large_and_readable(self):
        self.assertIn(
            'vals["modern_menu_sidebar_width"]',
            SCRIPT,
        )
        self.assertIn('const nativeWidth = Math.min(configuredWidth, 520);', SCRIPT)
        self.assertIn(
            'const share = spec.position === "center" ? 0.84 : 0.92;',
            SCRIPT,
        )
        self.assertIn(
            'availableWidth * share / (nativeWidth + 2 * spec.margin)',
            SCRIPT,
        )
        self.assertIn('frame.dataset.configuredWidth = String(configuredWidth);', SCRIPT)

    def test_sidebar_has_the_same_page_wide_reset_as_main_menu(self):
        self.assertIn('page.id === "mainmenu" || page.id === "sidebar"', SCRIPT)
        self.assertIn('str("reset_default", "Reset Default")', SCRIPT)
        self.assertIn('function resetPageSettings()', SCRIPT)
        self.assertIn('(section.fontRoles || []).forEach', SCRIPT)
        self.assertIn('"bound": bool(field.get("bind"))', RENDER)
        self.assertIn('.osw-page-reset-wrap { margin-right: 10px; }', STYLES)

    def test_sidebar_reset_icon_defaults_are_resolved_as_bundled_assets(self):
        self.assertIn('f"system:{icon}"', SCHEMA)
        self.assertIn('if icon_value.startswith("system:"):', RENDERER)
        self.assertIn('"unavailable_for_users",', RENDERER)
        self.assertIn('icon_url = configured_icon_url(custom_file)', RENDERER)
        self.assertNotIn('icon_url = f"{user_icon_base}{custom_file}"', RENDERER)
        self.assertIn("const actionIconUrl = (value, fallbackName) =>", INJECTOR)
        self.assertIn("if (iconValue.startsWith('system:'))", INJECTOR)
        self.assertIn("const iconUrl = actionIconUrl(customFile", INJECTOR)

    def test_runtime_typography_is_equal_in_both_settings_modes(self):
        font_css = PATCHER[PATCHER.index("def generate_font_css"):PATCHER.index("def _hex_to_rgba")]
        self.assertNotIn("settings_complexity", font_css)
        self.assertIn("active_font_roles = set(advanced_role_specs)", font_css)
        self.assertIn("const SETTINGS_MODE_PARITY = true;", SCRIPT)

    def test_synced_advanced_roles_inherit_family_but_keep_component_size(self):
        self.assertIn('inherits_simple_role = chosen_key == "sync"', PATCHER)
        self.assertIn('int(role_font_sizes[role])', PATCHER)
        self.assertNotIn('inherits_simple_role and not role.startswith("heatmap_")', PATCHER)
        self.assertIn('fontKey === "sync" && fallbackRoleKey', SCRIPT)

    def test_sidebar_role_selectors_receive_the_component_size_directly(self):
        self.assertIn('".sidebar-left #deck-list-header h2"', PATCHER)
        self.assertIn('".sidebar-left .deck-table a.deck"', PATCHER)
        self.assertIn('".sidebar-left .menu-item"', PATCHER)
        self.assertIn('designerFontRole(vals, "action_buttons", spec.isDark, "main")', SCRIPT)
        self.assertIn('designerFontRole(vals, "deck_title", isDark, "subtle")', SCRIPT)
        self.assertIn('designerFontRole(vals, "deck_names", isDark, "main")', SCRIPT)

    def test_deck_title_defaults_to_thirteen_px_and_matches_header_actions(self):
        self.assertIn('"deck_title": 13', SCHEMA)
        self.assertIn('"default_size": 13', PATCHER)
        self.assertIn('color: var(--icon-color, var(--fg-subtle)) !important;', PATCHER)
        self.assertIn('title.style.color = spec.iconColor;', SCRIPT)
        self.assertIn('font-size: 13px;', TEMPLATES)
        self.assertIn('color: var(--icon-color, var(--fg-subtle));', TEMPLATES)

    def test_every_sidebar_font_size_offers_the_circular_reset(self):
        profile_start = SCHEMA.index('"id": "onigiri_font_size_profile_name"')
        profile_field = SCHEMA[profile_start:profile_start + 600]
        self.assertIn('"reset_to": _current_simple_font_size("main")', profile_field)
        self.assertIn('"reset_to": size', SCHEMA)
        self.assertIn('if (field.resetTo != null)', SCRIPT)
        self.assertIn('const reset = el("button", "osw-reset")', SCRIPT)

    def test_font_css_reads_collection_values_through_the_supported_api(self):
        font_css = PATCHER[PATCHER.index("def generate_font_css"):PATCHER.index("def _hex_to_rgba")]
        self.assertIn("col_get = config.get_collection_config", font_css)
        self.assertNotIn("mw.col.conf.get", font_css)

    def test_organize_widgets_restores_the_compact_widget_fonts_menu(self):
        self.assertIn('("widget_title", "widget_small")', SCHEMA)
        self.assertIn('tr("widget_fonts", "Widget Fonts")', SCHEMA)
        self.assertIn('Widget Fonts stays beside the grid it affects in both modes.', SCHEMA)
        self.assertIn('controlActions.appendChild(compactFontMenuButton(section))', SCRIPT)

    def test_heatmap_fonts_can_sync_with_widget_fonts(self):
        self.assertIn('("heatmap_title", "heatmap_title", "Heatmap title", "small_title")', SCHEMA)
        self.assertIn('("heatmap_labels", "heatmap_labels", "Heatmap labels", "main")', SCHEMA)
        self.assertIn('tr("heatmap_fonts", "Heatmap Fonts")', SCHEMA)
        self.assertIn('tr("sync_with_widget_fonts", "Sync with Widget Fonts")', SCHEMA)
        self.assertIn('"heatmap_title": {', PATCHER)
        self.assertIn('"heatmap_labels": {', PATCHER)
        self.assertIn('active_font_roles = set(advanced_role_specs)', PATCHER)
        self.assertIn('font_heatmap_title', SCRIPT)
        self.assertIn('font_heatmap_labels', SCRIPT)
        self.assertIn('section["mode_parity"] = True', SCHEMA)
        self.assertIn('advanced_only=False', SCHEMA)
        self.assertIn('"modeParity": bool(section.get("mode_parity"))', RENDER)
        self.assertIn('section.modeParity || SETTINGS_MODE_PARITY', SCRIPT)
        self.assertIn('fallbackRoleKey, true', SCRIPT)

    def test_heatmap_font_roles_reach_preview_and_live_styles(self):
        self.assertIn('function heatmapPaintCosmetics(container, vals, isDark)', SCRIPT)
        self.assertIn('const titleRole = componentRole("heatmap_title", "small_title", 15);', SCRIPT)
        self.assertIn('const labelsRole = componentRole("heatmap_labels", "main", 14);', SCRIPT)
        self.assertIn('heatmapPaintCosmetics(container, vals, isDark);', SCRIPT)
        self.assertIn('include_font_css=False', INIT)
        self.assertIn('"font CSS", lambda: patcher.generate_font_css(addon_package)', INIT)

    def test_compact_font_menu_has_contextual_info(self):
        self.assertIn('const ICON_INFO =', SCRIPT)
        self.assertIn('osw-organize-font-info', SCRIPT)
        self.assertIn('roleDescription', SCRIPT)

    def test_stats_font_sizes_are_pixels_with_optional_widget_sync(self):
        for role in ("label", "value"):
            self.assertIn(f'"id": "swidget_{role}_size_sync"', SCHEMA)
            self.assertIn(f'"id": "swidget_{role}_size"', SCHEMA)
            self.assertIn(f'"bind": path("{role}_size")', SCHEMA)
            self.assertIn(f'"--swidget-{role}-size"', SCRIPT)
            self.assertIn(f'--swidget-{role}-size', PATCHER)
            self.assertIn(f'"{role}_size_sync": True', CONFIG)
        self.assertNotIn('swidget_label_scale', SCHEMA)
        self.assertNotIn('swidget_value_scale', SCHEMA)

    def test_stats_numbers_has_its_own_syncable_font_role(self):
        self.assertIn('"id": "swidget_number_font"', SCHEMA)
        self.assertIn('"id": "swidget_number_size_sync"', SCHEMA)
        self.assertIn('"id": "swidget_number_size"', SCHEMA)
        self.assertIn('"id": "swidget_font_numbers"', SCHEMA)
        self.assertIn('tr("stats_numbers", "Stats Numbers")', SCHEMA)
        self.assertIn('swidget_font_numbers', SCRIPT)
        self.assertIn('swidget_number_size_sync', SCRIPT)
        self.assertIn('stats_widget_number_font_key', PATCHER)
        self.assertIn('--swidget-number-size', PATCHER)
        self.assertIn('"number_font", "sync"', PATCHER)
        self.assertIn('statsRoleFont("swidget_value_font", "widget_small", "main")', SCRIPT)
        self.assertIn('statsRoleFont("swidget_number_font", "widget_small", "main")', SCRIPT)
        self.assertIn('".stat-card.onigiri-stat-card .stat-value",\n            "widget_small",', PATCHER)

    def test_synced_stats_titles_use_the_widget_title_role_size(self):
        self.assertIn('"onigiri_font_size_widget_title"', PATCHER)
        self.assertIn('"onigiri_font_size_widget_small"', PATCHER)

    def test_simple_and_advanced_expose_the_same_distributed_controls(self):
        self.assertIn('const SETTINGS_MODE_PARITY = true;', SCRIPT)
        self.assertIn('(SETTINGS_MODE_PARITY || settingsComplexity === "advanced")', SCRIPT)
        self.assertIn('field.advanced && !SETTINGS_MODE_PARITY', SCRIPT)
        self.assertIn('s.advancedOnly && !SETTINGS_MODE_PARITY', SCRIPT)

    def test_stats_size_sync_lives_in_the_compact_menu_header(self):
        self.assertIn('const syncSlot = el("div", "osw-organize-font-sync-slot")', SCRIPT)
        self.assertIn('function mountSizeSync(field)', SCRIPT)
        self.assertIn('isStatsSizeSyncField(field)', SCRIPT)
        self.assertIn('.osw-organize-font-sync-switch', STYLES)
        self.assertIn('border-radius: 7px;', STYLES)

    def test_compact_font_role_picker_uses_the_custom_menu(self):
        self.assertIn('osw-organize-font-role-picker', SCRIPT)
        self.assertIn('osw-organize-font-role-list', SCRIPT)
        self.assertIn('osw-organize-font-role-option', SCRIPT)
        self.assertNotIn('const roleSelect = document.createElement("select")', SCRIPT)
        self.assertIn('.osw-organize-font-role-list', STYLES)

    def test_stats_preview_distributes_all_cards_evenly(self):
        self.assertIn('.osw-preview-swidget-row .stat-card.onigiri-stat-card', STYLES)
        self.assertIn('flex: 1 1 0;', STYLES)

    def test_advanced_fonts_include_deck_stats_typography(self):
        for role in ("stats_title", "stats_labels", "stats_values"):
            self.assertIn(f'("{role}",', SCHEMA)
            self.assertIn(f'"{role}": {{', PATCHER)

    def test_dashboard_and_sidebar_roles_target_current_markup(self):
        self.assertIn(
            '".injected-stats-block .onigiri-widget-title"',
            PATCHER,
        )
        self.assertIn(
            '".sidebar-left .onigiri-sidebar-profile-summary-label"',
            PATCHER,
        )

    def test_legacy_font_sizes_are_clamped_before_rendering(self):
        self.assertIn(
            'if (field.min != null) value = Math.max(Number(field.min) * scale, value);',
            SCRIPT,
        )


if __name__ == "__main__":
    unittest.main()
