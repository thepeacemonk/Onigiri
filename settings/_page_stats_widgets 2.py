# Stats Widgets designer — the settings home for the Today's Stats cards
# (Studied / Time / Pace / Retention).
#
# Structurally a sibling of the Deck Stats designer in _page_mainmenu.py: same
# header (light/dark preview toggle + reset), same live QPainter preview, same
# "Sync with Widget Color and Effect" contract, same color-card grid. What is new
# here is the design selector (Minimal vs Expressive), the per-widget icon
# cards, and the dedicated font picker.
#
# Everything this page writes lands in current_config["stats_widgets_style"];
# patcher.generate_dynamic_css turns it into the --swidget-* CSS variables that
# web/menu.css consumes.

from ._common import *
from ._icon_picker import *
from ._font_picker import FontPickerDialog
from ._widgets import *
from ._layout_base import *

from ..prep_station_ui import render_icon_pixmap


class _StatsWidgetClickableCard(QFrame):
    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self._on_click = on_click

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mousePressEvent(event)


# Glyph size inside a segment, as a fraction of the segment's height. A segment
# is 28px tall, so this is a ~14px icon — the same visual weight as the label
# text it replaces.
_SW_SHAPE_GLYPH_RATIO = 0.5
_SW_SHAPE_GLYPH_CACHE = {}


def _stats_widgets_shape_glyph(addon_path, icon_name):
    """An `icon_painter` for GooeySegmentButton that draws a system SVG.

    Tinted with the color the segment would have painted its label in, so the
    glyph tracks the settings palette (idle / hover accent / checked white)
    exactly like every text segment does.
    """
    def paint(painter, rect, color):
        size = max(9, int(min(rect.width(), rect.height()) * _SW_SHAPE_GLYPH_RATIO))
        tint = QColor(color).name()
        key = (icon_name, tint, size)
        pixmap = _SW_SHAPE_GLYPH_CACHE.get(key)
        if pixmap is None:
            pixmap = render_icon_pixmap(addon_path, f"system:{icon_name}", tint, size)
            _SW_SHAPE_GLYPH_CACHE[key] = pixmap
        if pixmap.isNull():
            return
        dpr = max(1.0, pixmap.devicePixelRatioF())
        painter.drawPixmap(
            QPointF(
                rect.center().x() - pixmap.width() / (2 * dpr),
                rect.center().y() - pixmap.height() / (2 * dpr),
            ),
            pixmap,
        )

    return paint


class PageStatsWidgetsMixin:
    # (config key, label key, English fallback). Order drives the card grid.
    STATS_WIDGETS_BOX_KEYS = (
        ("box_bg", "deck_stats_box_color", "Box Color"),
        ("box_border", "deck_stats_border_color", "Border Color"),
        ("label", "stats_widgets_label_color", "Label Color"),
        ("value", "stats_widgets_value_color", "Value Color"),
    )
    STATS_WIDGETS_ACCENT_KEYS = (
        ("studied", "widget_studied", "Studied"),
        ("time", "widget_time", "Time"),
        ("pace", "widget_pace", "Pace"),
        ("retention", "widget_retention", "Retention"),
    )
    # The four cards that can carry an icon, in preview order.
    STATS_WIDGETS_IDS = ("studied", "time", "pace", "retention")
    # Retention star colors. Unlike everything else on this page these are
    # theme variables, so they are edited through self.color_widgets (the same
    # hidden line edits _save_main_menu_settings persists) rather than through
    # stats_widgets_colors.
    STATS_WIDGETS_STAR_KEYS = (
        ("--star-color", "star_color", "Star Color"),
        ("--empty-star-color", "empty_star_color", "Empty Star Color"),
    )

    # ------------------------------------------------------------------
    # Config access
    # ------------------------------------------------------------------

    def _stats_widgets_defaults(self):
        return DEFAULTS.get("stats_widgets_style", {})

    def _stats_widgets_default_color(self, mode, key):
        colors = self._stats_widgets_defaults().get("colors", {}).get(mode, {})
        return colors.get(key, "#808080")

    def _stats_widgets_preview_mode(self):
        return getattr(self, "stats_widgets_preview_mode", "dark" if theme_manager.night_mode else "light")

    def _stats_widgets_color_mode(self):
        """Palette the color cards write to.

        With Dynamic mode off there is a single palette shared by both themes;
        the "light" entry is the one that gets emitted, so it stands in for the
        dark theme too (same convention as Widget Color and Effect).
        """
        if not self._stats_widgets_dynamic():
            return "light"
        return self._stats_widgets_preview_mode()

    def _stats_widgets_color(self, key, mode=None):
        mode = mode or self._stats_widgets_color_mode()
        value = getattr(self, "stats_widgets_colors", {}).get(mode, {}).get(key)
        if value and QColor(value).isValid():
            return value
        return self._stats_widgets_default_color(mode, key)

    def _stats_widgets_design(self):
        group = getattr(self, "stats_widgets_design_group", None)
        checked = group.checkedButton() if group is not None else None
        value = checked.property("design") if checked is not None else None
        return value if value in ("minimal", "expressive") else "minimal"

    def _set_stats_widgets_design(self, design):
        group = getattr(self, "stats_widgets_design_group", None)
        if group is None:
            return
        for button in group.buttons():
            button.setChecked(button.property("design") == design)

    def _stats_widgets_chart_shape(self):
        group = getattr(self, "stats_widgets_chart_shape_group", None)
        checked = group.checkedButton() if group is not None else None
        value = checked.property("chart_shape") if checked is not None else None
        return value if value in ("sharp", "smooth") else "sharp"

    def _set_stats_widgets_chart_shape(self, shape):
        group = getattr(self, "stats_widgets_chart_shape_group", None)
        if group is None:
            return
        for button in group.buttons():
            button.setChecked(button.property("chart_shape") == shape)

    def _stats_widgets_synced(self):
        return hasattr(self, "stats_widgets_sync_toggle") and self.stats_widgets_sync_toggle.isChecked()

    def _stats_widgets_dynamic(self):
        # While synced, Widget Color and Effect owns Dynamic mode too, so the local
        # toggle is locked and the Box Effect one is what actually applies.
        if self._stats_widgets_synced() and hasattr(self, "box_effect_dynamic_toggle"):
            return self.box_effect_dynamic_toggle.isChecked()
        return not hasattr(self, "stats_widgets_dynamic_toggle") or self.stats_widgets_dynamic_toggle.isChecked()

    def _stats_widgets_effect_values(self):
        """Blur/opacity/radius/stroke actually in force, honouring the sync toggle."""
        if self._stats_widgets_synced() and hasattr(self, "box_effect_blur_slider"):
            return {
                "blur": self.box_effect_blur_slider.value(),
                "opacity": self.box_effect_opacity_slider.value(),
                "radius": self.box_effect_radius_slider.value(),
                "stroke": self.box_effect_stroke_slider.value(),
            }
        return {
            "blur": self.stats_widgets_blur_slider.value(),
            "opacity": self.stats_widgets_opacity_slider.value(),
            "radius": self.stats_widgets_radius_slider.value(),
            "stroke": self.stats_widgets_stroke_slider.value(),
        }

    def _stats_widgets_box_color(self, mode):
        if self._stats_widgets_synced():
            return self._box_effect_color(mode)
        return self._stats_widgets_color("box_bg", mode if self._stats_widgets_dynamic() else "light")

    def _stats_widgets_box_border_color(self, mode):
        if self._stats_widgets_synced():
            return self._box_effect_border_color(mode)
        return self._stats_widgets_color("box_border", mode if self._stats_widgets_dynamic() else "light")

    def _stats_widgets_accent(self, widget_id, mode):
        return self._stats_widgets_color(widget_id, mode if self._stats_widgets_dynamic() else "light")

    def _stats_widgets_icon(self, widget_id):
        icons = getattr(self, "stats_widgets_icons", {})
        default = self._stats_widgets_defaults().get("icons", {}).get(widget_id, "")
        return icons.get(widget_id) or default

    # ------------------------------------------------------------------
    # Designer construction
    # ------------------------------------------------------------------

    def _create_stats_widgets_designer(self):
        designer = QFrame()
        designer.setObjectName("mainBackgroundDesigner")
        outer = QVBoxLayout(designer)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        saved = self.current_config.get("stats_widgets_style", {})
        if not isinstance(saved, dict):
            saved = {}
        defaults = self._stats_widgets_defaults()

        # Working copies. The cards edit these, and _save_stats_widgets_settings
        # writes them back into current_config on Save.
        all_color_keys = [key for key, _lk, _fb in (self.STATS_WIDGETS_BOX_KEYS + self.STATS_WIDGETS_ACCENT_KEYS)]
        self.stats_widgets_colors = {}
        for mode in ("light", "dark"):
            saved_colors = saved.get("colors", {})
            saved_mode = saved_colors.get(mode, {}) if isinstance(saved_colors, dict) else {}
            self.stats_widgets_colors[mode] = {
                key: (saved_mode.get(key) or self._stats_widgets_default_color(mode, key))
                for key in all_color_keys
            }

        saved_icons = saved.get("icons", {})
        if not isinstance(saved_icons, dict):
            saved_icons = {}
        self.stats_widgets_icons = {
            wid: (saved_icons.get(wid) or defaults.get("icons", {}).get(wid, ""))
            for wid in self.STATS_WIDGETS_IDS
        }
        self.selected_stats_widgets_font_key = saved.get("font", defaults.get("font", "sync")) or "sync"

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel(tr("stats_widgets_section", "Stats Widgets"))
        title_label.setObjectName("sectionTitle")
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.stats_widgets_preview_mode = "dark" if theme_manager.night_mode else "light"
        self.stats_widgets_preview_mode_widget, self.stats_widgets_preview_mode_toggle = self._create_light_dark_mode_toggle(
            self.stats_widgets_preview_mode,
            self._on_stats_widgets_preview_mode_toggled,
        )
        header_layout.addWidget(self.stats_widgets_preview_mode_widget)

        self.stats_widgets_reset_button = QPushButton(tr("restore_default"))
        self.stats_widgets_reset_button.setObjectName("mainBackgroundResetButton")
        self.stats_widgets_reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stats_widgets_reset_button.clicked.connect(self._reset_stats_widgets_to_default)
        header_layout.addWidget(self.stats_widgets_reset_button)
        outer.addLayout(header_layout)

        self.stats_widgets_preview = BackgroundPreviewLabel(aspect_ratio=2.6, minimum_preview_height=210)
        self.stats_widgets_preview.setObjectName("mainBackgroundPreview")
        self.stats_widgets_preview.setMinimumHeight(
            self.stats_widgets_preview.heightForWidth(self._preview_expected_width())
        )
        self.stats_widgets_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_widgets_preview.setProperty("stats_widgets_preview", True)
        self.stats_widgets_preview.installEventFilter(self)
        outer.addWidget(self.stats_widgets_preview)

        preview_divider = QFrame()
        preview_divider.setFrameShape(QFrame.Shape.HLine)
        preview_divider.setFrameShadow(QFrame.Shadow.Sunken)
        outer.addWidget(preview_divider)

        slider_palette = self._settings_palette()
        slider_track = slider_palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = slider_palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")

        def _slider_row(attr, minimum, maximum, value, suffix):
            slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
            slider.setRange(minimum, maximum)
            slider.setValue(max(minimum, min(maximum, int(value))))
            label = QLabel(f"{slider.value()}{suffix}")
            label.setObjectName("mainBackgroundValueLabel")
            label.setFixedWidth(48)
            holder = QWidget()
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setSpacing(10)
            holder_layout.addWidget(slider, 1)
            holder_layout.addWidget(label)
            setattr(self, f"stats_widgets_{attr}_slider", slider)
            setattr(self, f"stats_widgets_{attr}_value_label", label)
            slider.valueChanged.connect(self._on_stats_widgets_changed)
            return holder

        blur_value = _slider_row("blur", 0, 100, saved.get("blur", defaults.get("blur", 0)) or 0, "%")
        opacity_value = _slider_row("opacity", 0, 100, saved.get("opacity", defaults.get("opacity", 100)) or 100, "%")
        radius_value = _slider_row("radius", 0, 60, saved.get("radius", defaults.get("radius", 20)) or 20, "px")
        stroke_raw = saved.get("stroke", defaults.get("stroke", 1))
        stroke_value = _slider_row("stroke", 0, 10, stroke_raw if stroke_raw is not None else 1, "px")
        scale_value = _slider_row(
            "scale", 60, 160, saved.get("value_scale", defaults.get("value_scale", 100)) or 100, "%"
        )

        saved_design = saved.get("design", defaults.get("design", "minimal"))
        if saved_design not in ("minimal", "expressive"):
            saved_design = "minimal"
        self.stats_widgets_design_group = QButtonGroup(self)
        self.stats_widgets_design_group.setExclusive(True)
        design_container = self._create_organize_segmented_control(
            [
                ("minimal", tr("stats_widgets_design_minimal", "Minimal")),
                ("expressive", tr("stats_widgets_design_expressive", "Expressive")),
            ],
            self.stats_widgets_design_group,
            saved_design,
            "design",
            fill_width=True,
            segment_height=28,
            min_button_width=88,
        )
        self.stats_widgets_design_group.buttonClicked.connect(self._on_stats_widgets_changed)

        saved_shape = saved.get("chart_shape", defaults.get("chart_shape", "sharp"))
        if saved_shape not in ("sharp", "smooth"):
            saved_shape = "sharp"
        self.stats_widgets_chart_shape_group = QButtonGroup(self)
        self.stats_widgets_chart_shape_group.setExclusive(True)
        # Glyph segments: a rounded square for the angular line, a circle for the
        # curved one. A word for either would be longer than the shape it names.
        chart_shape_container = self._create_organize_segmented_control(
            [
                ("sharp", tr("stats_widgets_chart_sharp", "Angular"),
                 _stats_widgets_shape_glyph(self.addon_path, "square.svg")),
                ("smooth", tr("stats_widgets_chart_smooth", "Curved"),
                 _stats_widgets_shape_glyph(self.addon_path, "circle.svg")),
            ],
            self.stats_widgets_chart_shape_group,
            saved_shape,
            "chart_shape",
            fill_width=True,
            segment_height=28,
            min_button_width=88,
        )
        self.stats_widgets_chart_shape_group.buttonClicked.connect(self._on_stats_widgets_changed)

        def _toggle(attr, default_value):
            toggle = AnimatedToggleButton(accent_color=self.accent_color)
            toggle.setChecked(bool(saved.get(attr, defaults.get(attr, default_value))))
            toggle.toggled.connect(self._on_stats_widgets_changed)
            setattr(self, f"stats_widgets_{attr}_toggle", toggle)
            return toggle

        self.stats_widgets_sync_toggle = _toggle("sync_box_effect", True)
        self.stats_widgets_dynamic_toggle = _toggle("dynamic", True)
        show_icons_toggle = _toggle("show_icons", True)
        show_units_toggle = _toggle("show_units", True)
        show_sparkline_toggle = _toggle("show_sparkline", True)
        show_stars_toggle = _toggle("show_retention_stars", True)
        # An install that predates this section only has the legacy inverse key,
        # so honour it rather than silently turning the stars back on.
        if "show_retention_stars" not in saved and self.current_config.get("hideRetentionStars", False):
            show_stars_toggle.setChecked(False)

        settings_column = QWidget()
        settings_column.setMinimumWidth(0)
        settings_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        settings_layout = QVBoxLayout(settings_column)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)
        settings_layout.addWidget(
            self._create_main_bg_value_row(tr("stats_widgets_design", "Widget Design"), design_container)
        )
        # Trend shape sits with the design it belongs to rather than down with
        # the visibility switches.
        self.stats_widgets_chart_shape_row = self._create_main_bg_value_row(
            tr("stats_widgets_chart_shape", "Trend shape"), chart_shape_container
        )
        settings_layout.addWidget(self.stats_widgets_chart_shape_row)
        settings_layout.addWidget(self._create_stats_widgets_font_control())
        settings_layout.addWidget(
            self._create_main_bg_toggle_row(
                tr("sync_with_box_color_effect", "Sync with Widget Color and Effect"),
                self.stats_widgets_sync_toggle,
            )
        )
        self.stats_widgets_dynamic_row = self._create_main_bg_toggle_row(
            tr("dynamic_mode", "Dynamic mode"), self.stats_widgets_dynamic_toggle
        )
        settings_layout.addWidget(self.stats_widgets_dynamic_row)

        # Icons and the sparkline only exist in the Expressive design, so those
        # rows are dimmed (not hidden) while Minimal is selected — hiding them
        # would make the panel jump height on every design switch.
        self.stats_widgets_icons_row = self._create_main_bg_toggle_row(
            tr("stats_widgets_show_icons", "Show icons"), show_icons_toggle
        )
        self.stats_widgets_sparkline_row = self._create_main_bg_toggle_row(
            tr("stats_widgets_show_sparkline", "Show 7-day trend"), show_sparkline_toggle
        )
        settings_layout.addWidget(self.stats_widgets_icons_row)
        settings_layout.addWidget(self.stats_widgets_sparkline_row)
        settings_layout.addWidget(
            self._create_main_bg_toggle_row(tr("stats_widgets_show_units", "Show units"), show_units_toggle)
        )
        # Minimal-only: the expressive card drops the stars unconditionally, so
        # this row is dimmed there rather than silently doing nothing.
        self.stats_widgets_stars_row = self._create_main_bg_toggle_row(
            tr("stats_widgets_show_stars", "Show retention stars"), show_stars_toggle
        )
        settings_layout.addWidget(self.stats_widgets_stars_row)
        settings_layout.addWidget(
            self._create_main_bg_value_row(tr("stats_widgets_value_scale", "Number size"), scale_value)
        )
        self.stats_widgets_blur_row = self._create_main_bg_value_row(tr("blur", "Blur"), blur_value)
        self.stats_widgets_opacity_row = self._create_main_bg_value_row(tr("opacity", "Opacity"), opacity_value)
        self.stats_widgets_radius_row = self._create_main_bg_value_row(tr("radius", "Radius"), radius_value)
        self.stats_widgets_stroke_row = self._create_main_bg_value_row(tr("stroke", "Stroke"), stroke_value)
        for row in (
            self.stats_widgets_blur_row,
            self.stats_widgets_opacity_row,
            self.stats_widgets_radius_row,
            self.stats_widgets_stroke_row,
        ):
            settings_layout.addWidget(row)
        settings_layout.addStretch(1)

        right_column = QWidget()
        right_column.setMinimumWidth(0)
        right_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        colors_grid = QGridLayout()
        colors_grid.setContentsMargins(0, 0, 0, 0)
        colors_grid.setHorizontalSpacing(10)
        colors_grid.setVerticalSpacing(8)
        colors_grid.setColumnStretch(0, 1)
        colors_grid.setColumnStretch(1, 1)

        self.stats_widgets_color_buttons = {}
        self.stats_widgets_box_cards = []
        entries = list(self.STATS_WIDGETS_BOX_KEYS) + list(self.STATS_WIDGETS_ACCENT_KEYS)
        for index, (key, label_key, fallback) in enumerate(entries):
            card = self._create_stats_widgets_color_card(key, tr(label_key, fallback))
            colors_grid.addWidget(card, index // 2, index % 2)
            if key in ("box_bg", "box_border"):
                self.stats_widgets_box_cards.append(card)
        right_layout.addLayout(colors_grid)

        icons_grid = QGridLayout()
        icons_grid.setContentsMargins(0, 0, 0, 0)
        icons_grid.setHorizontalSpacing(10)
        icons_grid.setVerticalSpacing(8)
        icons_grid.setColumnStretch(0, 1)
        icons_grid.setColumnStretch(1, 1)
        self.stats_widgets_icon_previews = {}
        self.stats_widgets_icon_cards = []
        for index, (wid, label_key, fallback) in enumerate(self.STATS_WIDGETS_ACCENT_KEYS):
            card = self._create_stats_widgets_icon_card(wid, tr(label_key, fallback))
            icons_grid.addWidget(card, index // 2, index % 2)
            self.stats_widgets_icon_cards.append(card)
        right_layout.addLayout(icons_grid)

        # Retention stars: the glyph and its two colors. Moved here from Box
        # Color and Effect, where they were unrelated to everything around them.
        stars_grid = QGridLayout()
        stars_grid.setContentsMargins(0, 0, 0, 0)
        stars_grid.setHorizontalSpacing(10)
        stars_grid.setVerticalSpacing(8)
        stars_grid.setColumnStretch(0, 1)
        stars_grid.setColumnStretch(1, 1)

        self.stats_widgets_star_color_buttons = {}
        self.stats_widgets_star_cards = []
        for index, (key, label_key, fallback) in enumerate(self.STATS_WIDGETS_STAR_KEYS):
            card = self._create_stats_widgets_star_color_card(key, tr(label_key, fallback))
            stars_grid.addWidget(card, 0, index)
            self.stats_widgets_star_cards.append(card)

        if self.retention_star_widget is None:
            self.retention_star_widget = self._create_icon_control_widget(
                "retention_star", display_name=tr("retention_star"), compact=True
            )
        self.retention_star_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        stars_grid.addWidget(self.retention_star_widget, 1, 0, 1, 2)
        self.stats_widgets_star_cards.append(self.retention_star_widget)

        right_layout.addLayout(stars_grid)
        right_layout.addStretch(1)

        bottom_columns = ResponsivePairWidget(
            settings_column, right_column, spacing=18, breakpoint=760,
            left_stretch=1, right_stretch=1
        )
        outer.addWidget(bottom_columns)

        self._update_stats_widgets_controls()
        return designer

    def _create_stats_widgets_color_card(self, key, label_text):
        label_button = self._create_main_bg_button(label_text)
        value_button = self._create_main_bg_button("")
        value_button.setObjectName("mainBackgroundColorButton")
        label_button.clicked.connect(lambda _=False, k=key, b=label_button: self._choose_stats_widgets_color(k, b))
        value_button.clicked.connect(lambda _=False, k=key, b=value_button: self._choose_stats_widgets_color(k, b))
        self.stats_widgets_color_buttons[key] = value_button
        self._style_main_background_color_button(value_button, self._stats_widgets_color(key))
        return self._create_color_selector_card(label_button, value_button, compact=True)

    # --- Retention star colors -------------------------------------------
    # These live in current_config["colors"][mode], edited through the hidden
    # per-theme line edits in self.color_widgets so the existing save path in
    # _save_main_menu_settings picks them up untouched.

    def _stats_widgets_star_icon(self):
        """The glyph the star row is drawn with, live from the icon control."""
        widget = getattr(self, "retention_star_widget", None)
        value = widget.property("icon_filename") if widget is not None else ""
        if not value:
            value = mw.col.conf.get("modern_menu_icon_retention_star", "")
        return value or "system:star.svg"

    def _stats_widgets_star_line_edit(self, key, mode):
        """The hidden per-theme line edit a star color is stored in.

        Follows the heatmap color cards: whichever page is built first owns the
        edit, it is registered in self.color_widgets so the Colors and Themes
        pages stay in sync with it, and _save_main_menu_settings persists it.
        """
        existing = self.color_widgets.get(mode, {}).get(key)
        if existing is not None:
            return existing
        colors = self.current_config.get("colors", {}).get(mode, {})
        value = colors.get(key) or DEFAULTS.get("colors", {}).get(mode, {}).get(key, "#ffd041")
        line_edit = QLineEdit(value, self)
        line_edit.hide()
        self.color_widgets.setdefault(mode, {})[key] = line_edit
        self._register_color_sync(f"palette:{mode}:{key}", line_edit)
        return line_edit

    def _stats_widgets_star_color(self, key, mode=None):
        mode = mode or self._stats_widgets_preview_mode()
        value = self._stats_widgets_star_line_edit(key, mode).text()
        if QColor(value).isValid():
            return value
        return DEFAULTS.get("colors", {}).get(mode, {}).get(key, "#ffd041")

    def _create_stats_widgets_star_color_card(self, key, label_text):
        # Both themes' edits are created up front so switching the preview mode
        # never has to build one mid-flight.
        for mode in ("light", "dark"):
            self._stats_widgets_star_line_edit(key, mode).textChanged.connect(
                lambda _value: self._update_stats_widgets_preview()
            )
        label_button = self._create_main_bg_button(label_text)
        value_button = self._create_main_bg_button("")
        value_button.setObjectName("mainBackgroundColorButton")
        label_button.clicked.connect(lambda _=False, k=key, b=label_button: self._choose_stats_widgets_star_color(k, b))
        value_button.clicked.connect(lambda _=False, k=key, b=value_button: self._choose_stats_widgets_star_color(k, b))
        self.stats_widgets_star_color_buttons[key] = value_button
        self._style_main_background_color_button(value_button, self._stats_widgets_star_color(key))
        return self._create_color_selector_card(label_button, value_button, compact=True)

    def _choose_stats_widgets_star_color(self, key, anchor=None):
        # Star colors are theme colors, so they always follow the preview's
        # light/dark mode — the Stats Widgets Dynamic switch does not apply.
        mode = self._stats_widgets_preview_mode()
        chosen, ok = OnigiriColorDialog.getColor(self._stats_widgets_star_color(key, mode), self, anchor=anchor)
        if ok and QColor(chosen).isValid():
            self._stats_widgets_star_line_edit(key, mode).setText(chosen)
            self._update_stats_widgets_controls()

    def _create_stats_widgets_icon_card(self, widget_id, label_text):
        palette = self._settings_palette()
        card_bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        card_border = palette.get("--border", "#454545" if theme_manager.night_mode else "#dcdde1")
        hover_bg = palette.get("--hover-bg", "#3a3a3a" if theme_manager.night_mode else "#f2f2f2")
        text_color = palette.get("--fg", "#f4f4f5" if theme_manager.night_mode else "#202124")
        subtle_color = palette.get("--fg-subtle", "#c4c4c4" if theme_manager.night_mode else "#6f7177")

        card = _StatsWidgetClickableCard(lambda wid=widget_id: self._open_stats_widgets_icon_selector(wid))
        card.setObjectName("statsWidgetIconCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setMinimumHeight(52)
        card.setStyleSheet(f"""
            QFrame#statsWidgetIconCard {{ background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 16px; }}
            QFrame#statsWidgetIconCard:hover {{ background-color: {hover_bg}; }}
        """)

        row = QHBoxLayout(card)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(10)

        preview = QLabel()
        preview.setFixedSize(28, 28)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setStyleSheet("background: transparent; border: none;")

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        name_label = QLabel(label_text)
        name_label.setStyleSheet(
            f"background: transparent; border: none; font-weight: bold; color: {text_color}; font-size: 12px;"
        )
        sub_label = QLabel(tr("click_to_change"))
        sub_label.setStyleSheet(f"background: transparent; border: none; color: {subtle_color}; font-size: 10px;")
        text_col.addWidget(name_label)
        text_col.addWidget(sub_label)

        row.addWidget(preview)
        row.addLayout(text_col, 1)

        self.stats_widgets_icon_previews[widget_id] = preview
        return card

    def _create_stats_widgets_font_control(self):
        palette = self._settings_palette()
        card_bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        card_border = palette.get("--border", "#454545" if theme_manager.night_mode else "#dcdde1")
        hover_bg = palette.get("--hover-bg", "#3a3a3a" if theme_manager.night_mode else "#f2f2f2")
        text_color = palette.get("--fg", "#f4f4f5" if theme_manager.night_mode else "#202124")
        subtle_color = palette.get("--fg-subtle", "#c4c4c4" if theme_manager.night_mode else "#6f7177")

        card = _StatsWidgetClickableCard(self._open_stats_widgets_font_picker)
        card.setObjectName("statsWidgetFontCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setMinimumHeight(56)
        card.setStyleSheet(f"""
            QFrame#statsWidgetFontCard {{ background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 16px; }}
            QFrame#statsWidgetFontCard:hover {{ background-color: {hover_bg}; }}
        """)

        row = QHBoxLayout(card)
        row.setContentsMargins(12, 8, 10, 8)
        row.setSpacing(12)

        preview = QLabel("128")
        preview.setFixedWidth(52)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setStyleSheet(f"background: transparent; border: none; color: {text_color};")

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        name_label = QLabel(tr("stats_widgets_font", "Widget Font"))
        name_label.setStyleSheet(
            f"background: transparent; border: none; font-weight: bold; color: {text_color}; font-size: 13px;"
        )
        value_label = QLabel("")
        value_label.setStyleSheet(f"background: transparent; border: none; color: {subtle_color}; font-size: 10px;")
        text_col.addWidget(name_label)
        text_col.addWidget(value_label)

        row.addWidget(preview)
        row.addLayout(text_col, 1)

        self.stats_widgets_font_preview_label = preview
        self.stats_widgets_font_value_label = value_label
        self._refresh_stats_widgets_font_card()
        return card

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _stats_widgets_font_family(self, font_key):
        if not font_key or font_key in ("sync", "system"):
            return ""
        cache = getattr(self, "_font_family_cache", None)
        if cache is None:
            cache = self._font_family_cache = {}
        if font_key in cache:
            return cache[font_key]
        info = get_all_fonts(self.addon_path).get(font_key, {})
        font_file = info.get("file")
        if not font_file:
            cache[font_key] = info.get("family", "")
            return cache[font_key]
        if info.get("user"):
            path = os.path.join(self.addon_path, "user_files", "fonts", font_file)
        else:
            path = os.path.join(self.addon_path, "system_files", "fonts", "system_fonts", font_file)
        if not os.path.exists(path):
            cache[font_key] = info.get("family", "")
            return cache[font_key]
        font_id = QFontDatabase.addApplicationFont(path)
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id != -1 else []
        cache[font_key] = families[0] if families else info.get("family", "")
        return cache[font_key]

    def _refresh_stats_widgets_font_card(self):
        key = getattr(self, "selected_stats_widgets_font_key", "sync") or "sync"
        if key == "sync":
            display = tr("stats_title_font_sync", "Same as titles")
        else:
            info = get_all_fonts(self.addon_path).get(key, {})
            display = tr("system") if key == "system" else info.get("name", key)
        value_label = getattr(self, "stats_widgets_font_value_label", None)
        if value_label is not None:
            value_label.setText(f"{display} · {tr('click_to_change')}")
        preview = getattr(self, "stats_widgets_font_preview_label", None)
        if preview is not None:
            font = QFont()
            family = self._stats_widgets_font_family(key)
            if family:
                font.setFamily(family)
            font.setPixelSize(21)
            preview.setFont(font)

    def _open_stats_widgets_font_picker(self):
        # "sync" is a mode rather than a font, so the picker opens on the
        # resolved default and the Reset button inside it maps back to sync.
        current = getattr(self, "selected_stats_widgets_font_key", "sync") or "sync"
        dialog = FontPickerDialog(
            "system" if current == "sync" else current,
            self.addon_path,
            self,
            sample_text="128",
            title=tr("stats_widgets_font", "Widget Font"),
        )

        def on_selected(font_key):
            self.selected_stats_widgets_font_key = font_key or "sync"
            self._refresh_stats_widgets_font_card()
            self._update_stats_widgets_preview()

        dialog.fontSelected.connect(on_selected)
        dialog.exec()

    def _open_stats_widgets_icon_selector(self, widget_id):
        picker = DeckIconPickerDialog(
            self._stats_widgets_icon(widget_id), self.addon_path, self, allow_emoji=False
        )

        def on_selected(value):
            if not value:
                return
            self.stats_widgets_icons[widget_id] = value
            self._update_stats_widgets_controls()

        picker.iconSelected.connect(on_selected)
        picker.exec()

    def _choose_stats_widgets_color(self, key, anchor=None):
        mode = self._stats_widgets_color_mode()
        chosen, ok = OnigiriColorDialog.getColor(self._stats_widgets_color(key, mode), self, anchor=anchor)
        if ok and QColor(chosen).isValid():
            self.stats_widgets_colors.setdefault(mode, {})[key] = chosen
            self._update_stats_widgets_controls()

    def _on_stats_widgets_preview_mode_toggled(self, mode):
        self.stats_widgets_preview_mode = "dark" if mode == "dark" else "light"
        self._update_stats_widgets_controls()

    def _on_stats_widgets_changed(self, *args):
        self._update_stats_widgets_controls()

    def _update_stats_widgets_controls(self):
        if not hasattr(self, "stats_widgets_preview"):
            return
        synced = self._stats_widgets_synced()
        dynamic = self._stats_widgets_dynamic()
        expressive = self._stats_widgets_design() == "expressive"

        for attr, suffix in (
            ("blur", "%"), ("opacity", "%"), ("radius", "px"), ("stroke", "px"), ("scale", "%"),
        ):
            slider = getattr(self, f"stats_widgets_{attr}_slider", None)
            label = getattr(self, f"stats_widgets_{attr}_value_label", None)
            if slider is not None and label is not None:
                label.setText(f"{slider.value()}{suffix}")

        # Everything Widget Color and Effect owns while synced is dimmed out, the
        # same way the Overview and Deck Stats sections signal a locked control.
        locked_rows = (
            self.stats_widgets_dynamic_row,
            self.stats_widgets_blur_row,
            self.stats_widgets_opacity_row,
            self.stats_widgets_radius_row,
            self.stats_widgets_stroke_row,
        )
        self._set_dynamic_mode_widgets_dimmed(locked_rows, synced)
        self._set_dynamic_mode_widgets_dimmed(tuple(getattr(self, "stats_widgets_box_cards", ())), synced)

        # Expressive-only controls, and the one minimal-only control.
        design_only = (self.stats_widgets_icons_row, self.stats_widgets_sparkline_row)
        self._set_dynamic_mode_widgets_dimmed(design_only, not expressive)
        # The trend shape needs a trend to shape, so it also follows the switch
        # right above it.
        self._set_dynamic_mode_widgets_dimmed(
            (self.stats_widgets_chart_shape_row,),
            not expressive or not self.stats_widgets_show_sparkline_toggle.isChecked(),
        )
        self._set_dynamic_mode_widgets_dimmed(tuple(getattr(self, "stats_widgets_icon_cards", ())), not expressive)
        # Everything star-related is minimal-only, and within minimal it also
        # follows the Show retention stars switch.
        stars_off = expressive or not self._stats_widgets_minimal_stars_shown()
        self._set_dynamic_mode_widgets_dimmed((self.stats_widgets_stars_row,), expressive)
        self._set_dynamic_mode_widgets_dimmed(tuple(getattr(self, "stats_widgets_star_cards", ())), stars_off)

        if hasattr(self, "stats_widgets_preview_mode_widget"):
            self.stats_widgets_preview_mode_widget.setEnabled(dynamic)
            self.stats_widgets_preview_mode_widget.setToolTip(
                "" if dynamic else tr("enable_dynamic_mode_hint", "Enable Dynamic mode to switch light/dark palettes.")
            )

        for key, button in getattr(self, "stats_widgets_color_buttons", {}).items():
            if key == "box_bg" and synced:
                color = self._box_effect_color(self._stats_widgets_preview_mode())
            elif key == "box_border" and synced:
                color = self._box_effect_border_color(self._stats_widgets_preview_mode())
            else:
                color = self._stats_widgets_color(key)
            self._style_main_background_color_button(button, color)

        for key, button in getattr(self, "stats_widgets_star_color_buttons", {}).items():
            self._style_main_background_color_button(button, self._stats_widgets_star_color(key))

        # The star glyph preview is tinted with the filled-star color.
        if getattr(self, "retention_star_widget", None):
            try:
                self._update_icon_preview_for_widget(self.retention_star_widget)
            except Exception:
                pass

        mode = self._stats_widgets_preview_mode()
        for wid, preview in getattr(self, "stats_widgets_icon_previews", {}).items():
            try:
                preview.setPixmap(
                    render_icon_pixmap(self.addon_path, self._stats_widgets_icon(wid), self._stats_widgets_accent(wid, mode), 22)
                )
            except Exception:
                preview.clear()

        self._refresh_stats_widgets_font_card()
        self._update_stats_widgets_preview()

    def _reset_stats_widgets_to_default(self):
        defaults = self._stats_widgets_defaults()
        self.stats_widgets_colors = {
            mode: dict(defaults.get("colors", {}).get(mode, {}))
            for mode in ("light", "dark")
        }
        self.stats_widgets_icons = dict(defaults.get("icons", {}))
        self.selected_stats_widgets_font_key = defaults.get("font", "sync")
        self._set_stats_widgets_design(defaults.get("design", "minimal"))
        self._set_stats_widgets_chart_shape(defaults.get("chart_shape", "sharp"))
        for attr, default_value in (
            ("sync_box_effect", True), ("dynamic", True), ("show_icons", True),
            ("show_units", True), ("show_sparkline", True), ("show_retention_stars", True),
        ):
            toggle = getattr(self, f"stats_widgets_{attr}_toggle", None)
            if toggle is not None:
                toggle.setChecked(bool(defaults.get(attr, default_value)))
        self.stats_widgets_blur_slider.setValue(int(defaults.get("blur", 0) or 0))
        self.stats_widgets_opacity_slider.setValue(int(defaults.get("opacity", 100) or 100))
        self.stats_widgets_radius_slider.setValue(int(defaults.get("radius", 20) or 20))
        stroke = defaults.get("stroke", 1)
        self.stats_widgets_stroke_slider.setValue(int(stroke if stroke is not None else 1))
        self.stats_widgets_scale_slider.setValue(int(defaults.get("value_scale", 100) or 100))
        # Star colors are theme colors, restored from the theme defaults.
        for key, _label_key, _fallback in self.STATS_WIDGETS_STAR_KEYS:
            for mode in ("light", "dark"):
                default_color = DEFAULTS.get("colors", {}).get(mode, {}).get(key)
                if default_color:
                    self._stats_widgets_star_line_edit(key, mode).setText(default_color)
        self._update_stats_widgets_controls()
        show_settings_toast(self, tr("stats_widgets_reset_toast", "Stats Widgets reset to default"))

    # ------------------------------------------------------------------
    # Preview painting
    # ------------------------------------------------------------------

    def _stats_widgets_preview_samples(self):
        """(widget_id, label, value, unit, series) for the four sample cards."""
        return (
            ("studied", tr("studied", "Studied"), "128", tr("cards", "cards"), [4, 9, 6, 13, 8, 15, 12]),
            ("time", tr("time", "Time"), "42.0", tr("minutes_unit", "min"), [12, 20, 15, 28, 18, 33, 26]),
            ("pace", tr("pace", "Pace"), "19.7", f"{tr('seconds_unit', 's')}/{tr('card', 'card')}", [22, 18, 21, 16, 19, 15, 17]),
            # The percent sign rides along with the number, matching the widget.
            ("retention", tr("retention", "Retention"), "87%", "", [72, 80, 76, 88, 84, 91, 87]),
        )

    # The real cards are laid out by web/menu.css against a ~200x120px 1x1 grid
    # cell. The preview draws a scale model of that cell, so every size below is
    # expressed as a fraction of the card height and stays faithful at whatever
    # size the preview label happens to be. Keep these in step with the
    # `.stat-card.onigiri-stat-card` rules in menu.css.
    _SW_CARD_H = 120.0                 # reference 1x1 card height, in px
    _SW_PAD = 16.0 / _SW_CARD_H        # .stat-card padding
    _SW_LABEL = 15.0 / _SW_CARD_H      # h3 font-size (--font-size-small-title)
    _SW_CHIP = 22.0 / _SW_CARD_H       # .stat-icon-chip
    _SW_ICON = 13.0 / _SW_CARD_H       # .stat-icon inside the chip
    _SW_VALUE_MIN = 30.0 / _SW_CARD_H  # .is-minimal .stat-value
    _SW_VALUE_EXP = 40.0 / _SW_CARD_H  # .is-expressive .stat-value
    _SW_UNIT = 0.46                    # .stat-unit, relative to the value
    _SW_STAR = 12.0 / _SW_CARD_H       # .star-rating height
    _SW_TREND = 30.0 / _SW_CARD_H      # --stat-trend-h
    _SW_TREND_TALL = 40.0 / _SW_CARD_H # --stat-trend-h on .is-tall

    def _stats_widgets_saved_span(self, widget_id):
        """(row_span, col_span) this widget actually occupies on the dashboard.

        The sparkline only exists on cards bigger than 1x1, so the preview has
        to know the user's real layout to show what they will actually get.
        """
        layout = self.current_config.get("onigiriWidgetLayout", {})
        grid = layout.get("grid", {}) if isinstance(layout, dict) else {}
        conf = grid.get(widget_id) if isinstance(grid, dict) else None
        if not isinstance(conf, dict):
            return (1, 1)
        try:
            row_span = max(1, int(conf.get("row", 1)))
        except (TypeError, ValueError):
            row_span = 1
        try:
            col_span = max(1, int(conf.get("col", 1)))
        except (TypeError, ValueError):
            col_span = 1
        return (row_span, col_span)

    def _stats_widgets_minimal_stars_shown(self):
        """Mirrors onigiri_renderer._stats_widget_minimal_stars_shown."""
        if self._stats_widgets_design() != "minimal":
            return False
        # The live toggle wins over the legacy key: hideRetentionStars is only
        # rewritten on save, so reading it first left the star cards disabled
        # for the rest of the session after switching the toggle back on.
        return not self._retention_stars_hidden()

    def _draw_stats_widgets_card(self, painter, rect, mode, widget_id, label, value, unit, series, expressive):
        """One sample card, drawn the same way web/menu.css lays the real one out."""
        effects = self._stats_widgets_effect_values()
        blur_radius = (effects["blur"] / 100.0) * 20.0
        fill_alpha = max(0.0, min(1.0, effects["opacity"] / 100.0))
        if blur_radius > 0:
            fill_alpha = min(fill_alpha, 0.62)

        box_color = QColor(self._stats_widgets_box_color(mode))
        box_color.setAlphaF(fill_alpha)
        accent = QColor(self._stats_widgets_accent(widget_id, mode))
        label_color = QColor(self._stats_widgets_color("label", mode if self._stats_widgets_dynamic() else "light"))
        value_color = QColor(self._stats_widgets_color("value", mode if self._stats_widgets_dynamic() else "light"))

        path = QPainterPath()
        radius = float(effects["radius"])
        path.addRoundedRect(rect, radius, radius)

        painter.save()
        painter.fillPath(path, QBrush(box_color))

        if expressive:
            # Accent wash across the top-left corner, matching the CSS gradient.
            wash = QColor(accent)
            wash.setAlphaF(0.10)
            painter.save()
            painter.setClipPath(path, Qt.ClipOperation.IntersectClip)
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0.0, wash)
            transparent = QColor(accent)
            transparent.setAlphaF(0.0)
            gradient.setColorAt(0.62, transparent)
            painter.fillRect(rect, QBrush(gradient))
            painter.restore()

        stroke_width = max(0, int(effects["stroke"]))
        if stroke_width > 0:
            border_pen = QPen(QColor(self._stats_widgets_box_border_color(mode)))
            border_pen.setWidth(stroke_width)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        painter.setClipPath(path, Qt.ClipOperation.IntersectClip)

        # Everything from here down is the scale model of the CSS box.
        unit_h = rect.height()
        pad = unit_h * self._SW_PAD
        inner = QRectF(rect).adjusted(pad, pad, -pad, -pad)
        scale = max(60, min(160, self.stats_widgets_scale_slider.value())) / 100.0
        show_units = self.stats_widgets_show_units_toggle.isChecked()
        show_icons = expressive and self.stats_widgets_show_icons_toggle.isChecked()

        row_span, _col_span = self._stats_widgets_saved_span(widget_id)
        show_spark = (
            expressive
            and self.stats_widgets_show_sparkline_toggle.isChecked()
            and bool(series)
        )
        # Matches --stat-trend-h in menu.css: taller card, taller strip.
        spark_h = unit_h * (self._SW_TREND_TALL if row_span >= 2 else self._SW_TREND) if show_spark else 0.0

        # --- head: optional icon chip + uppercase label ---
        label_x = inner.left()
        head_h = unit_h * self._SW_LABEL * 1.2
        if show_icons:
            chip = unit_h * self._SW_CHIP
            head_h = max(head_h, chip)
            chip_rect = QRectF(inner.left(), inner.top(), chip, chip)
            chip_color = QColor(accent)
            chip_color.setAlphaF(0.16)
            chip_path = QPainterPath()
            chip_path.addRoundedRect(chip_rect, chip * 0.32, chip * 0.32)
            painter.fillPath(chip_path, QBrush(chip_color))
            icon_px = max(6, int(unit_h * self._SW_ICON))
            try:
                pixmap = render_icon_pixmap(
                    self.addon_path, self._stats_widgets_icon(widget_id), accent.name(), icon_px
                )
                if not pixmap.isNull():
                    dpr = max(1.0, pixmap.devicePixelRatioF())
                    painter.drawPixmap(
                        QPointF(
                            chip_rect.center().x() - pixmap.width() / (2 * dpr),
                            chip_rect.center().y() - pixmap.height() / (2 * dpr),
                        ),
                        pixmap,
                    )
            except Exception:
                pass
            label_x = chip_rect.right() + unit_h * 0.058  # .stat-head gap: 7px

        label_font = QFont(painter.font())
        label_font.setPixelSize(max(7, int(unit_h * self._SW_LABEL)))
        label_font.setBold(False)
        label_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 106)
        painter.setFont(label_font)
        painter.setPen(QPen(label_color))
        painter.drawText(
            QRectF(label_x, inner.top(), inner.right() - label_x, head_h),
            int(Qt.AlignmentFlag.AlignLeft.value) | int(Qt.AlignmentFlag.AlignVCenter.value),
            label.upper(),
        )

        # --- body: the number, bottom-anchored like .stat-body ---
        star_h = unit_h * self._SW_STAR if self._stats_widgets_minimal_stars_shown() else 0.0
        body_bottom = inner.bottom()
        if star_h:
            body_bottom -= star_h + unit_h * 0.05  # .stat-body gap: 6px
        if spark_h:
            # .has-trend .stat-body padding-bottom: the strip minus the padding
            # it already overlaps.
            body_bottom -= max(0.0, spark_h - pad)

        value_font = QFont(painter.font())
        value_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 100)
        value_font.setBold(False)
        base = self._SW_VALUE_EXP if expressive else self._SW_VALUE_MIN
        value_font.setPixelSize(max(9, int(unit_h * base * scale)))
        painter.setFont(value_font)
        painter.setPen(QPen(accent if expressive else value_color))
        metrics = QFontMetrics(value_font)
        value_width = metrics.horizontalAdvance(value)
        baseline_y = body_bottom - metrics.descent()
        painter.drawText(QPointF(inner.left(), baseline_y), value)

        unit_width = 0.0
        if unit and show_units:
            unit_font = QFont(painter.font())
            unit_font.setPixelSize(max(6, int(value_font.pixelSize() * self._SW_UNIT)))
            painter.setFont(unit_font)
            unit_color = QColor(accent if expressive else value_color)
            unit_color.setAlphaF(0.55)
            painter.setPen(QPen(unit_color))
            gap = value_font.pixelSize() * 0.28  # .stat-value gap: 0.28em
            painter.drawText(QPointF(inner.left() + value_width + gap, baseline_y), unit)
            unit_width = gap + QFontMetrics(unit_font).horizontalAdvance(unit)

        # --- stars: minimal only, and only on the retention card ---
        if star_h and widget_id == "retention":
            self._draw_stats_widgets_stars(
                painter, QRectF(inner.left(), body_bottom + unit_h * 0.05, inner.width(), star_h), mode
            )

        if spark_h:
            # Full-bleed against the card's bottom edge, exactly like .stat-spark.
            spark_rect = QRectF(rect.left(), rect.bottom() - spark_h, rect.width(), spark_h)
            self._draw_stats_widgets_spark(painter, spark_rect, series, accent)

        _ = unit_width
        painter.restore()

    def _draw_stats_widgets_stars(self, painter, rect, mode):
        """The retention star row, tinted with the same theme colors the
        widget's `.star` / `.star.empty` rules use."""
        filled = QColor(self._stats_widgets_star_color("--star-color", mode))
        empty = QColor(self._stats_widgets_star_color("--empty-star-color", mode))
        if not filled.isValid():
            filled = QColor("#ffd041")
        if not empty.isValid():
            empty = QColor("#4a4a4a")

        size = rect.height()
        gap = size * 0.2
        # The sample sits at 4/5, the same rating _stats_widgets_preview_samples
        # implies for its 87% retention.
        for index in range(5):
            left = rect.left() + index * (size + gap)
            if left + size > rect.right():
                break
            color = filled if index < 4 else empty
            try:
                pixmap = render_icon_pixmap(
                    self.addon_path, self._stats_widgets_star_icon(), color.name(), max(5, int(size))
                )
                if not pixmap.isNull():
                    painter.drawPixmap(QPointF(left, rect.top()), pixmap)
                    continue
            except Exception:
                pass
            painter.fillRect(QRectF(left, rect.top(), size, size), QBrush(color))

    def _draw_stats_widgets_spark(self, painter, rect, series, accent):
        values = [max(0.0, float(v or 0)) for v in series]
        if len(values) < 2 or max(values) <= 0:
            return
        # Same min..max normalisation as the widget's SVG sparkline.
        low, high = min(values), max(values)
        flat = (high - low) < 1e-9
        height = rect.height()
        step = rect.width() / (len(values) - 1)
        points = []
        for index, value in enumerate(values):
            fraction = 0.5 if flat else (value - low) / (high - low)
            points.append(
                QPointF(rect.left() + index * step, rect.bottom() - 3 - fraction * (height - 6))
            )

        # Same Catmull-Rom spline the widget's SVG uses, so "Curved" previews as
        # the exact shape it will draw on the dashboard.
        smooth = self._stats_widgets_chart_shape() == "smooth" and not flat

        def _append_series(path):
            """Adds points[1:] to a path already sitting on points[0]."""
            if not smooth:
                for point in points[1:]:
                    path.lineTo(point)
                return
            for index in range(len(points) - 1):
                p0 = points[index - 1] if index > 0 else points[index]
                p1 = points[index]
                p2 = points[index + 1]
                p3 = points[index + 2] if index + 2 < len(points) else points[index + 1]
                path.cubicTo(
                    QPointF(p1.x() + (p2.x() - p0.x()) / 6.0, p1.y() + (p2.y() - p0.y()) / 6.0),
                    QPointF(p2.x() - (p3.x() - p1.x()) / 6.0, p2.y() - (p3.y() - p1.y()) / 6.0),
                    p2,
                )

        if not flat:
            area = QPainterPath()
            area.moveTo(QPointF(rect.left(), rect.bottom()))
            area.lineTo(points[0])
            _append_series(area)
            area.lineTo(QPointF(rect.right(), rect.bottom()))
            area.closeSubpath()
            fill = QColor(accent)
            fill.setAlphaF(0.14)
            painter.fillPath(area, QBrush(fill))

        line = QPainterPath()
        line.moveTo(points[0])
        _append_series(line)
        pen = QPen(QColor(accent))
        pen.setWidthF(1.6)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(line)

    def _render_stats_widgets_preview_pixmap(self):
        size = self.stats_widgets_preview.size()
        width = max(1, size.width())
        height = max(1, size.height())
        dpr = max(1.0, self.stats_widgets_preview.devicePixelRatioF())
        target = QPixmap(int(width * dpr), int(height * dpr))
        target.setDevicePixelRatio(dpr)
        target.fill(Qt.GlobalColor.transparent)

        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        preview_rect = QRectF(1, 1, width - 2, height - 2)
        path = QPainterPath()
        path.addRoundedRect(preview_rect, 22, 22)
        painter.setClipPath(path)

        mode = self._stats_widgets_preview_mode()
        background = self._render_box_effect_background_for_mode(mode, width, height)
        painter.drawPixmap(0, 0, background)

        expressive = self._stats_widgets_design() == "expressive"
        samples = self._stats_widgets_preview_samples()
        # A real 1x1 dashboard cell is about 200x120px and the grid gap is 15px;
        # the preview keeps that aspect so it reads as the same card.
        margin = width * 0.05
        usable = width - margin * 2
        gap = usable * 0.035
        card_w = (usable - gap * (len(samples) - 1)) / len(samples)
        card_h = min(height * 0.88, card_w * (120.0 / 200.0))
        top = (height - card_h) / 2.0

        for index, (wid, label, value, unit, series) in enumerate(samples):
            rect = QRectF(margin + index * (card_w + gap), top, card_w, card_h)
            self._draw_stats_widgets_card(painter, rect, mode, wid, label, value, unit, series, expressive)

        painter.setClipping(False)
        border_color = QColor("#4b5563" if theme_manager.night_mode else "#d1d5db")
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()
        return target

    def _update_stats_widgets_preview(self):
        if not hasattr(self, "stats_widgets_preview"):
            return
        self.stats_widgets_preview.setStyleSheet(
            "QLabel#mainBackgroundPreview { background: transparent; border: none; }"
        )
        try:
            self.stats_widgets_preview.setPixmap(self._render_stats_widgets_preview_pixmap())
        except Exception as exc:
            print(f"Onigiri: failed to render stats widgets settings preview: {exc}")
            fallback = QPixmap(
                max(1, self.stats_widgets_preview.width()), max(1, self.stats_widgets_preview.height())
            )
            fallback.fill(Qt.GlobalColor.transparent)
            self.stats_widgets_preview.setPixmap(fallback)
        self.stats_widgets_preview.setText("")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save_stats_widgets_settings(self):
        if not hasattr(self, "stats_widgets_sync_toggle"):
            return
        style = self.current_config.setdefault("stats_widgets_style", {})
        style["design"] = self._stats_widgets_design()
        style["chart_shape"] = self._stats_widgets_chart_shape()
        style["sync_box_effect"] = self.stats_widgets_sync_toggle.isChecked()
        style["dynamic"] = self.stats_widgets_dynamic_toggle.isChecked()
        style["show_icons"] = self.stats_widgets_show_icons_toggle.isChecked()
        style["show_units"] = self.stats_widgets_show_units_toggle.isChecked()
        style["show_sparkline"] = self.stats_widgets_show_sparkline_toggle.isChecked()
        show_stars = self.stats_widgets_show_retention_stars_toggle.isChecked()
        style["show_retention_stars"] = show_stars
        # Kept in step with the legacy key the renderer and the Hide-modes page
        # still read, so there is only ever one switch to reason about.
        self.current_config["hideRetentionStars"] = not show_stars
        style["blur"] = self.stats_widgets_blur_slider.value()
        style["opacity"] = self.stats_widgets_opacity_slider.value()
        style["radius"] = self.stats_widgets_radius_slider.value()
        style["stroke"] = self.stats_widgets_stroke_slider.value()
        style["value_scale"] = self.stats_widgets_scale_slider.value()
        style["font"] = getattr(self, "selected_stats_widgets_font_key", "sync") or "sync"
        style["icons"] = dict(getattr(self, "stats_widgets_icons", {}))
        style["colors"] = {
            mode: dict(values) for mode, values in getattr(self, "stats_widgets_colors", {}).items()
        }
