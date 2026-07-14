# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._icon_picker import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *



class PageMainmenuMixin:
    def _organize_compact_stylesheet(self):
        palette = self._settings_palette()
        panel_bg = palette.get("--canvas-inset", "#ffffff")
        row_hover = palette.get("--highlight-bg", "#f2f2f2")
        segment_bg = palette.get("--highlight-bg", "#f2f2f2")
        input_bg = palette.get("--input-bg", "#ffffff")
        border = palette.get("--border", "#dcdde1")
        fg = palette.get("--fg", "#202124")
        muted = palette.get("--muted-fg", "#8f9299")
        accent = palette.get("--accent-color", self.accent_color)

        return f"""
            QFrame#organizeCompactPanel {{
                background-color: {panel_bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QFrame#organizeCompactRow {{
                background-color: transparent;
                border: none;
                border-radius: 12px;
            }}
            QFrame#organizeCompactRow:hover {{
                background-color: {row_hover};
            }}
            QLabel#organizeCompactLabel {{
                color: {fg};
                background: transparent;
                font-size: 13px;
                font-weight: 500;
            }}
            QLineEdit#organizeStatsTitleInput, QAbstractSpinBox#organizeCompactSpinBox {{
                background-color: {input_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 15px;
                padding: 0 12px;
                min-height: 30px;
                max-height: 30px;
                selection-background-color: {accent};
                selection-color: white;
            }}
            QLineEdit#organizeStatsTitleInput:focus, QAbstractSpinBox#organizeCompactSpinBox:focus {{
                border-color: {accent};
            }}
            QFrame#organizeSegmentShell {{
                background-color: {segment_bg};
                border: 1px solid {border};
                border-radius: 15px;
            }}
            QPushButton#organizeSegmentButton {{
                background: transparent;
                background-color: transparent;
                color: {fg};
                border: 1px solid transparent;
                border-radius: 12px;
                min-height: 24px;
                max-height: 24px;
                padding: 0 8px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#organizeSegmentButton:hover:!checked {{
                color: {fg};
                background: {panel_bg};
                background-color: {panel_bg};
            }}
            QPushButton#organizeSegmentButton:checked {{
                background: {accent};
                background-color: {accent};
                border: 1px solid {accent};
                color: white;
            }}
            QPushButton#organizeSegmentButton:disabled {{
                color: {muted};
            }}
        """

    def _heatmap_visibility_stylesheet(self):
        palette = self._settings_palette()
        panel_bg = palette.get("--canvas-inset", "#ffffff")
        row_hover = palette.get("--highlight-bg", "#f2f2f2")
        border = palette.get("--border", "#dcdde1")
        fg = palette.get("--fg", "#202124")

        return f"""
            QFrame#heatmapVisibilityPanel {{
                background-color: {panel_bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QFrame#heatmapVisibilityRow {{
                background-color: transparent;
                border: none;
                border-radius: 12px;
            }}
            QFrame#heatmapVisibilityRow:hover {{
                background-color: {row_hover};
                border: none;
                border-radius: 12px;
            }}
            QLabel#heatmapVisibilityLabel {{
                color: {fg};
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: 500;
            }}
        """

    def _create_organize_compact_row(self, title, control_widget):
        row = QFrame()
        row.setObjectName("organizeCompactRow")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row.setMinimumHeight(46)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(14)

        label = QLabel(title)
        label.setObjectName("organizeCompactLabel")
        label.setWordWrap(True)
        label.setMinimumWidth(132)
        label.setMaximumWidth(190)
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(label)
        if control_widget.objectName() == "organizeSegmentShell":
            control_cell = QWidget()
            control_cell.setStyleSheet("background: transparent;")
            control_cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            control_layout = QHBoxLayout(control_cell)
            control_layout.setContentsMargins(0, 0, 0, 0)
            control_layout.setSpacing(0)
            control_layout.addWidget(control_widget, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            control_layout.addStretch()
            layout.addWidget(control_cell, 1)
        else:
            layout.addWidget(control_widget, 1)
        return row

    def _create_heatmap_visibility_toggle_row(self, toggle_widget, text_label):
        row = QFrame()
        row.setObjectName("heatmapVisibilityRow")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row.setMinimumHeight(42)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(14)

        label = QLabel(text_label)
        label.setObjectName("heatmapVisibilityLabel")
        label.setWordWrap(True)
        label.setMinimumWidth(132)
        label.setMaximumWidth(220)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(toggle_widget, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return row

    def _create_organize_segmented_control(
        self,
        options,
        button_group,
        checked_key,
        property_name,
        fill_width=False,
        segment_height=24,
        min_button_width=42,
    ):
        palette = self._settings_palette()
        segment_bg = palette.get("--highlight-bg", "#f2f2f2")
        fg = palette.get("--fg", "#202124")
        accent = palette.get("--accent-color", self.accent_color)
        border = palette.get("--border", "#dcdde1")

        shell = GooeySegmentShell(segment_bg, border, accent)
        if fill_width:
            shell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        for key, label in options:
            btn = GooeySegmentButton(
                label,
                fg=fg,
                checked_fg="#ffffff",
                hover_fg=accent,
            )
            btn.setObjectName("organizeSegmentButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if fill_width:
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                btn.setMinimumWidth(min_button_width)
            else:
                btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                btn.setFixedWidth(max(min_button_width, btn.fontMetrics().horizontalAdvance(label) + 18))
            btn.setFixedHeight(segment_height)
            btn.setProperty(property_name, key)
            btn.setChecked(key == checked_key)
            button_group.addButton(btn)
            shell.add_segment_button(btn)
            if fill_width:
                shell.segment_layout.setStretch(shell.segment_layout.count() - 1, 1)

        return shell

    # --- Widget Background (glassmorphism / colour overlay / solid) -------
    # Controls the onigiri_widget_bg_* keys consumed by the deck-browser
    # renderer for dashboard widget surfaces.

    def _widget_bg_slider_row(self, label_text, slider, value_suffix="%"):
        palette = self._settings_palette()
        label = QLabel(label_text)
        label.setObjectName("organizeCompactLabel")
        value_label = QLabel(f"{slider.value()}{value_suffix}")
        value_label.setObjectName("mainBackgroundValueLabel")
        value_label.setFixedWidth(48)
        slider.valueChanged.connect(lambda v, vl=value_label: vl.setText(f"{v}{value_suffix}"))

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)
        row_layout.addWidget(label)
        row_layout.addWidget(slider, 1)
        row_layout.addWidget(value_label)
        return row

    def _widget_bg_color_button(self, initial_hex):
        button = QPushButton(initial_hex)
        button.setObjectName("mainBackgroundColorButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(28)
        button.setMinimumWidth(96)

        def refresh(hex_value):
            button.setText(hex_value)
            icon_color = _contrast_icon_color(QColor(hex_value))
            button.setStyleSheet(
                f"QPushButton#mainBackgroundColorButton {{ background-color: {hex_value};"
                f" color: {icon_color}; border-radius: 8px; border: 1px solid rgba(127,127,127,.35); }}"
            )

        def choose():
            chosen, ok = OnigiriColorDialog.getColor(button.text(), self, anchor=button)
            if ok and chosen:
                refresh(chosen)

        refresh(initial_hex)
        button.clicked.connect(choose)
        return button

    def _current_widget_bg_style(self):
        mode = mw.col.conf.get("onigiri_widget_bg_mode", "solid")
        if mode != "main":
            return "solid"
        effect = mw.col.conf.get("onigiri_widget_bg_main_effect_mode", "glassmorphism")
        return "glass" if effect == "glassmorphism" else "overlay"

    def _create_widget_background_group(self):
        section = SectionGroup(
            tr("widget_background", "Widget Background"),
            self,
            border=False,
            description=tr(
                "widget_background_description",
                "How dashboard widget surfaces are drawn: frosted glass over the main background, a colour overlay, or a solid colour.",
            ),
        )

        panel = QFrame()
        panel.setObjectName("organizeCompactPanel")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setStyleSheet(self._organize_compact_stylesheet())
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(6, 6, 6, 6)
        panel_layout.setSpacing(8)

        self.widget_bg_style_group = QButtonGroup(self)
        self.widget_bg_style_group.setExclusive(True)
        style_shell = self._create_organize_segmented_control(
            [
                ("glass", tr("widget_bg_glass", "Glassmorphism")),
                ("overlay", tr("widget_bg_overlay", "Colour Overlay")),
                ("solid", tr("widget_bg_solid", "Solid")),
            ],
            self.widget_bg_style_group,
            self._current_widget_bg_style(),
            "widgetBgStyle",
            fill_width=True,
            segment_height=28,
            min_button_width=90,
        )
        panel_layout.addWidget(self._create_organize_compact_row(tr("widget_bg_style", "Style"), style_shell))

        slider_palette = self._settings_palette()
        slider_track = slider_palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = slider_palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")

        # Glassmorphism intensity
        self.widget_bg_glass_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.widget_bg_glass_slider.setRange(0, 100)
        self.widget_bg_glass_slider.setValue(max(0, min(100, int(mw.col.conf.get("onigiri_widget_bg_main_effect_intensity", 50) or 0))))
        self.widget_bg_glass_row = self._widget_bg_slider_row(tr("widget_bg_intensity", "Effect intensity"), self.widget_bg_glass_slider)
        panel_layout.addWidget(self.widget_bg_glass_row)

        # Colour overlay tint
        self.widget_bg_tint_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.widget_bg_tint_slider.setRange(0, 100)
        self.widget_bg_tint_slider.setValue(max(0, min(100, int(mw.col.conf.get("onigiri_widget_bg_main_tint_intensity", 30) or 0))))
        self.widget_bg_tint_row = self._widget_bg_slider_row(tr("widget_bg_overlay_opacity", "Overlay opacity"), self.widget_bg_tint_slider)
        panel_layout.addWidget(self.widget_bg_tint_row)

        self.widget_bg_tint_light_button = self._widget_bg_color_button(
            str(mw.col.conf.get("onigiri_widget_bg_main_tint_color_light", "#FFFFFF"))
        )
        self.widget_bg_tint_dark_button = self._widget_bg_color_button(
            str(mw.col.conf.get("onigiri_widget_bg_main_tint_color_dark", "#2C2C2C"))
        )
        tint_colors = QWidget()
        tint_layout = QHBoxLayout(tint_colors)
        tint_layout.setContentsMargins(0, 0, 0, 0)
        tint_layout.setSpacing(10)
        tint_layout.addWidget(self.widget_bg_tint_light_button)
        tint_layout.addWidget(self.widget_bg_tint_dark_button)
        tint_layout.addStretch()
        self.widget_bg_tint_colors_row = self._create_organize_compact_row(
            tr("widget_bg_overlay_colors", "Overlay colour (light / dark)"), tint_colors
        )
        panel_layout.addWidget(self.widget_bg_tint_colors_row)

        # Solid transparency (solid colour itself comes from Box Color above)
        self.widget_bg_transparency_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.widget_bg_transparency_slider.setRange(0, 100)
        self.widget_bg_transparency_slider.setValue(max(0, min(100, int(mw.col.conf.get("onigiri_widget_bg_solid_transparency", 0) or 0))))
        self.widget_bg_transparency_row = self._widget_bg_slider_row(tr("widget_bg_transparency", "Transparency"), self.widget_bg_transparency_slider)
        panel_layout.addWidget(self.widget_bg_transparency_row)

        def refresh_visibility():
            style = "solid"
            checked = self.widget_bg_style_group.checkedButton()
            if checked is not None:
                style = checked.property("widgetBgStyle") or "solid"
            self.widget_bg_glass_row.setVisible(style == "glass")
            self.widget_bg_tint_row.setVisible(style == "overlay")
            self.widget_bg_tint_colors_row.setVisible(style == "overlay")
            self.widget_bg_transparency_row.setVisible(style == "solid")

        self.widget_bg_style_group.buttonToggled.connect(lambda *_: refresh_visibility())
        refresh_visibility()

        section.add_widget(panel)
        return section

    def _save_widget_background_settings(self):
        if not hasattr(self, "widget_bg_style_group"):
            return
        style = "solid"
        checked = self.widget_bg_style_group.checkedButton()
        if checked is not None:
            style = checked.property("widgetBgStyle") or "solid"

        mw.col.conf["onigiri_widget_bg_mode"] = "main" if style in ("glass", "overlay") else "solid"
        if style in ("glass", "overlay"):
            mw.col.conf["onigiri_widget_bg_main_effect_mode"] = "glassmorphism" if style == "glass" else "opaque"
        mw.col.conf["onigiri_widget_bg_main_effect_intensity"] = self.widget_bg_glass_slider.value()
        mw.col.conf["onigiri_widget_bg_main_tint_intensity"] = self.widget_bg_tint_slider.value()
        mw.col.conf["onigiri_widget_bg_main_tint_color_light"] = self.widget_bg_tint_light_button.text()
        mw.col.conf["onigiri_widget_bg_main_tint_color_dark"] = self.widget_bg_tint_dark_button.text()
        mw.col.conf["onigiri_widget_bg_solid_transparency"] = self.widget_bg_transparency_slider.value()

    def create_main_menu_page(self):
        page, layout = self._create_scrollable_page()

        organize_section = SectionGroup(
            tr("organize"), 
            self, 
            border=False, 
            description=tr("organize_description")
        )
        
        controls_widget = QFrame()
        controls_widget.setObjectName("organizeCompactPanel")
        controls_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        controls_widget.setStyleSheet(self._organize_compact_stylesheet())
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(6, 6, 6, 6)
        controls_layout.setSpacing(2)

        self.stats_title_input.setObjectName("organizeStatsTitleInput")
        self.stats_title_input.setFixedHeight(30)
        self.stats_title_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls_layout.addWidget(self._create_organize_compact_row(tr("custom_stats_title"), self.stats_title_input))
        
        organize_section.add_widget(controls_widget)
        
        # Add the layout editor widget to the organize section
        self.organize_widget_container = self._create_organize_layout_widget()
        organize_section.add_widget(self.organize_widget_container)
        
        layout.addWidget(organize_section)

        boxes_effect_section = self._create_boxes_color_effect_group()
        layout.addWidget(boxes_effect_section)

        widget_bg_section = self._create_widget_background_group()
        layout.addWidget(widget_bg_section)

        # --- Main Background Section ---
        user_files_path = os.path.join(self.addon_path, "user_files", "main_bg")
        os.makedirs(user_files_path, exist_ok=True)
        try:
            cached_user_files = sorted([f for f in os.listdir(user_files_path) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))])
        except OSError:
            cached_user_files = []

        mode_group = SectionGroup("", self, border=False)
        mode_group.add_widget(self._create_main_background_designer(cached_user_files))
        layout.addWidget(mode_group)

        heatmap_section = SectionGroup(
            "", 
            self, 
            border=False
        )
        heatmap_section.add_widget(self._create_heatmap_designer())

        layout.addWidget(heatmap_section)

        layout.addStretch()

        # Add navigation buttons
        sections = {
            tr("organize_section"): organize_section,
            tr("widget_grid"): self.organize_widget_container,
            tr("boxes_color_effect"): boxes_effect_section,
            tr("widget_background", "Widget Background"): widget_bg_section,
            tr("main_background_section"): mode_group,
            tr("heatmap_section"): heatmap_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections)

        return page

    def _create_heatmap_designer(self):
        designer = QFrame()
        designer.setObjectName("mainBackgroundDesigner")
        outer = QVBoxLayout(designer)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel(tr("heatmap"))
        title_label.setObjectName("sectionTitle")
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.heatmap_preview_mode = "dark" if theme_manager.night_mode else "light"
        self.heatmap_preview_mode_widget, self.heatmap_preview_mode_toggle = self._create_light_dark_mode_toggle(
            self.heatmap_preview_mode,
            self._on_heatmap_preview_mode_toggled,
        )
        header_layout.addWidget(self.heatmap_preview_mode_widget)

        self.heatmap_colors_reset_button = QPushButton(tr("reset_heatmap_colors"))
        self.heatmap_colors_reset_button.setObjectName("mainBackgroundResetButton")
        self.heatmap_colors_reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.heatmap_colors_reset_button.clicked.connect(self.reset_heatmap_colors_to_default)
        header_layout.addWidget(self.heatmap_colors_reset_button)
        outer.addLayout(header_layout)

        self.heatmap_preview = BackgroundPreviewLabel(aspect_ratio=4.45, minimum_preview_height=158)
        self.heatmap_preview.setObjectName("mainBackgroundPreview")
        # Seed the height from the real expected width so the panel doesn't grow
        # from its minimum-height floor on the first on-screen layout.
        self.heatmap_preview.setMinimumHeight(
            self.heatmap_preview.heightForWidth(self._preview_expected_width())
        )
        self.heatmap_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.heatmap_preview.setProperty("heatmap_preview", True)
        self.heatmap_preview.installEventFilter(self)
        outer.addWidget(self.heatmap_preview)

        preview_divider = QFrame()
        preview_divider.setFrameShape(QFrame.Shape.HLine)
        preview_divider.setFrameShadow(QFrame.Shadow.Sunken)
        outer.addWidget(preview_divider)

        settings_column = QWidget()
        settings_column.setMinimumWidth(0)
        settings_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        settings_layout = QVBoxLayout(settings_column)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)

        self.heatmap_view_group = QButtonGroup(self)
        self.heatmap_view_group.setExclusive(True)
        current_view = self.current_config.get("heatmapDefaultView", "year")
        view_container = self._create_organize_segmented_control(
            [
                ("year", tr("view_year")),
                ("month", tr("view_month")),
                ("week", tr("view_week")),
            ],
            self.heatmap_view_group,
            current_view,
            "view_mode",
            fill_width=True,
            segment_height=28,
            min_button_width=58,
        )
        settings_layout.addWidget(self._create_main_bg_value_row(tr("default_view"), view_container))

        self.heatmap_week_start_group = QButtonGroup(self)
        self.heatmap_week_start_group.setExclusive(True)
        current_week_start = self.current_config.get("heatmapWeekStart", "monday")
        week_start_container = self._create_organize_segmented_control(
            [
                ("monday", tr("week_start_monday", "Monday")),
                ("sunday", tr("week_start_sunday", "Sunday")),
            ],
            self.heatmap_week_start_group,
            current_week_start,
            "week_start",
            fill_width=True,
            segment_height=28,
            min_button_width=72,
        )
        settings_layout.addWidget(self._create_main_bg_value_row(tr("week_start_label", "Week Starts On"), week_start_container))

        self.heatmap_show_streak_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_streak_check.setChecked(self.current_config.get("heatmapShowStreak", True))
        self.heatmap_show_months_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_months_check.setChecked(self.current_config.get("heatmapShowMonths", True))
        self.heatmap_show_weekdays_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_weekdays_check.setChecked(self.current_config.get("heatmapShowWeekdays", True))
        self.heatmap_show_week_header_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_week_header_check.setChecked(self.current_config.get("heatmapShowWeekHeader", True))
        self.heatmap_streak_row = self._create_main_bg_toggle_row(tr("show_streak_counter"), self.heatmap_show_streak_check)
        self.heatmap_months_row = self._create_main_bg_toggle_row(tr("show_month_labels"), self.heatmap_show_months_check)
        self.heatmap_weekdays_row = self._create_main_bg_toggle_row(tr("show_weekday_labels"), self.heatmap_show_weekdays_check)
        self.heatmap_day_labels_row = self._create_main_bg_toggle_row(tr("show_day_labels"), self.heatmap_show_week_header_check)
        for row in (
            self.heatmap_streak_row,
            self.heatmap_months_row,
            self.heatmap_weekdays_row,
            self.heatmap_day_labels_row,
        ):
            settings_layout.addWidget(row)

        colors_column = QWidget()
        colors_column.setMinimumWidth(0)
        colors_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        colors_layout = QGridLayout(colors_column)
        colors_layout.setContentsMargins(0, 0, 0, 0)
        colors_layout.setHorizontalSpacing(10)
        colors_layout.setVerticalSpacing(10)
        colors_layout.setColumnStretch(0, 1)

        self.heatmap_light_color_card = self._create_heatmap_color_selector_card(
            "light", "--heatmap-color", tr("heatmap_shape_color", "Light")
        )
        self.heatmap_light_zero_color_card = self._create_heatmap_color_selector_card(
            "light", "--heatmap-color-zero", tr("heatmap_shape_zero_color", "Light (0 reviews)")
        )
        self.heatmap_dark_color_card = self._create_heatmap_color_selector_card(
            "dark", "--heatmap-color", tr("heatmap_shape_dark_color", "Dark")
        )
        self.heatmap_dark_zero_color_card = self._create_heatmap_color_selector_card(
            "dark", "--heatmap-color-zero", tr("heatmap_shape_zero_dark_color", "Dark (0 reviews)")
        )
        colors_layout.addWidget(self.heatmap_light_color_card, 0, 0)
        colors_layout.addWidget(self.heatmap_light_zero_color_card, 1, 0)
        colors_layout.addWidget(self.heatmap_dark_color_card, 2, 0)
        colors_layout.addWidget(self.heatmap_dark_zero_color_card, 3, 0)

        shape_column = QWidget()
        shape_column.setMinimumWidth(0)
        shape_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        shape_layout = QVBoxLayout(shape_column)
        shape_layout.setContentsMargins(0, 0, 0, 0)
        shape_layout.setSpacing(10)
        shape_layout.addWidget(self._create_heatmap_shape_control())
        shape_layout.addWidget(self._create_heatmap_streak_icon_control())
        self.heatmap_streak_icon_color_card = self._create_heatmap_streak_icon_color_card()
        self.heatmap_streak_icon_color_card.hide()
        self.heatmap_streak_icon_zero_color_card = self._create_heatmap_streak_icon_zero_color_card()
        self.heatmap_streak_icon_zero_color_card.hide()
        self.heatmap_colors_column = colors_column
        self.heatmap_colors_column.hide()
        shape_layout.addStretch(1)

        controls_left = QWidget()
        controls_left.setMinimumWidth(0)
        controls_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        controls_left_layout = QVBoxLayout(controls_left)
        controls_left_layout.setContentsMargins(0, 0, 0, 0)
        controls_left_layout.setSpacing(12)
        controls_left_layout.addWidget(settings_column)
        controls_left_layout.addStretch(1)

        bottom_columns = ResponsivePairWidget(
            controls_left, shape_column, spacing=18, breakpoint=760,
            left_stretch=2, right_stretch=1
        )
        outer.addWidget(bottom_columns)

        for toggle in (
            self.heatmap_show_streak_check,
            self.heatmap_show_months_check,
            self.heatmap_show_weekdays_check,
            self.heatmap_show_week_header_check,
        ):
            toggle.toggled.connect(self._on_heatmap_controls_changed)
        self.heatmap_view_group.buttonClicked.connect(lambda _=None: self._on_heatmap_view_changed())
        self.heatmap_week_start_group.buttonClicked.connect(lambda _=None: self._on_heatmap_controls_changed())

        self._update_heatmap_view_option_visibility()
        self._update_heatmap_color_cards()
        self._update_heatmap_preview()
        return designer

    def _create_heatmap_color_selector_card(self, mode, key, label_text):
        colors = self.current_config.get("colors", {}).get(mode, {})
        value = colors.get(key, DEFAULTS["colors"][mode].get(key, "#00c896" if key == "--heatmap-color" else "#eeeeee"))
        attr = f"heatmap_{mode}_{'zero' if key == '--heatmap-color-zero' else 'shape'}"
        label_button = self._create_main_bg_button(label_text)
        value_button = self._create_main_bg_button("")
        value_button.setObjectName("mainBackgroundColorButton")
        line_edit = QLineEdit(value, self)
        line_edit.hide()
        setattr(self, f"{attr}_color_input", line_edit)
        setattr(self, f"{attr}_color_button", value_button)
        self.color_widgets[mode].setdefault(key, line_edit)
        self._register_color_sync(f"palette:{mode}:{key}", line_edit)

        label_button.clicked.connect(lambda _=False, m=mode, k=key, b=label_button: self._choose_heatmap_color(m, k, b))
        value_button.clicked.connect(lambda _=False, m=mode, k=key, b=value_button: self._choose_heatmap_color(m, k, b))
        line_edit.textChanged.connect(lambda value, m=mode, k=key, b=value_button: self._on_heatmap_color_changed(m, k, value, b))
        self._style_main_background_color_button(value_button, value)
        return self._create_color_selector_card(label_button, value_button)

    def _choose_heatmap_color(self, mode, key, anchor=None):
        line_edit = self.color_widgets.get(mode, {}).get(key)
        if not line_edit:
            return
        chosen, ok = OnigiriColorDialog.getColor(line_edit.text(), self, anchor=anchor)
        if ok:
            line_edit.setText(chosen)

    def _create_heatmap_shape_control(self):
        control_widget = QFrame()
        control_widget.setObjectName("colorSelectorCard")
        control_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        control_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        control_widget.setProperty("heatmap_shape_control", True)
        control_widget.installEventFilter(self)
        control_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        control_widget.setMinimumHeight(60)

        palette = self._settings_palette()
        card_bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        card_border = palette.get("--border", "#454545" if theme_manager.night_mode else "#dcdde1")
        hover_bg = palette.get("--hover-bg", "#3a3a3a" if theme_manager.night_mode else "#f2f2f2")
        text_color = palette.get("--fg", "#f4f4f5" if theme_manager.night_mode else "#202124")
        subtle_color = palette.get("--fg-subtle", "#c4c4c4" if theme_manager.night_mode else "#6f7177")
        control_widget.setStyleSheet(f"""
            QFrame#colorSelectorCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 16px;
            }}
            QFrame#colorSelectorCard:hover {{
                background-color: {hover_bg};
                border: 1px solid {card_border};
                border-radius: 16px;
            }}
        """)

        layout = QHBoxLayout(control_widget)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(12)

        preview_label = QLabel()
        preview_label.setFixedSize(34, 34)
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setStyleSheet("background: transparent; border: none;")

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        name_label = QLabel(tr("heatmap_shape_icon", "Heatmap Shape"))
        name_label.setStyleSheet(f"background: transparent; border: none; font-weight: bold; color: {text_color}; font-size: 13px;")
        sub_label = QLabel(tr("click_to_change"))
        sub_label.setStyleSheet(f"background: transparent; border: none; color: {subtle_color}; font-size: 10px;")
        text_layout.addWidget(name_label)
        text_layout.addWidget(sub_label)

        reset_button = QPushButton()
        reset_button.setFixedSize(24, 24)
        reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_button.setToolTip(tr("reset_to_default_tooltip"))
        reset_button.setStyleSheet(
            "/* onigiri-rounded-button-fix */\n"
            "QPushButton { background-color: transparent; border: 1px solid transparent; border-radius: 12px; }"
            "QPushButton:hover { background-color: rgba(220, 38, 38, 0.12); border: 1px solid transparent; border-radius: 12px; }"
        )
        icon_path = system_icon_path("cancel.svg")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                painter = QPainter(pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor("#ff6b6b" if theme_manager.night_mode else "#d32f2f"))
                painter.end()
                reset_button.setIcon(QIcon(pixmap))
        else:
            reset_button.setText("x")
        reset_button.clicked.connect(self._reset_heatmap_shape_to_default)

        layout.addWidget(preview_label)
        layout.addLayout(text_layout, 1)
        layout.addWidget(reset_button)

        self.heatmap_shape_widget = control_widget
        self.heatmap_shape_preview_label = preview_label
        self.selected_heatmap_shape = self.current_config.get("heatmapShape", "system:square.svg")
        if self.selected_heatmap_shape == "onigiri.svg" or str(self.selected_heatmap_shape).startswith("emoji:"):
            self.selected_heatmap_shape = "system:square.svg"
        self._refresh_heatmap_shape_control()
        return control_widget

    def _refresh_heatmap_shape_control(self):
        preview_label = getattr(self, "heatmap_shape_preview_label", None)
        if preview_label is None:
            return
        value = getattr(self, "selected_heatmap_shape", self.current_config.get("heatmapShape", "system:square.svg")) or "system:square.svg"
        if str(value).startswith("emoji:"):
            preview_label.setText(str(value)[len("emoji:"):])
            preview_label.setPixmap(QPixmap())
            return
        preview_label.setText("")
        shape_color = self._heatmap_color_value("light", "--heatmap-color") if hasattr(self, "color_widgets") else self.accent_color
        pixmap = self._render_icon_value_pixmap(value, shape_color, 30)
        if pixmap.isNull():
            pixmap = QPixmap(30, 30)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(shape_color)))
            painter.drawRoundedRect(QRectF(4, 4, 22, 22), 5, 5)
            painter.end()
        preview_label.setPixmap(pixmap.scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _reset_heatmap_shape_to_default(self):
        self.selected_heatmap_shape = "system:square.svg"
        for mode, color_key in (
            ("light", "--heatmap-color"),
            ("light", "--heatmap-color-zero"),
            ("dark", "--heatmap-color"),
            ("dark", "--heatmap-color-zero"),
        ):
            line_edit = self.color_widgets.get(mode, {}).get(color_key)
            if line_edit is not None:
                line_edit.setText(DEFAULTS["colors"][mode][color_key])
        self._update_heatmap_color_cards()
        self._refresh_heatmap_shape_control()
        self._update_heatmap_preview()
        show_settings_toast(self, tr("heatmap_shape_reset_toast", "Heatmap shape reset to default"))

    def _create_heatmap_streak_icon_control(self):
        control_widget = QFrame()
        control_widget.setObjectName("colorSelectorCard")
        control_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        control_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        control_widget.setProperty("heatmap_streak_icon_control", True)
        control_widget.installEventFilter(self)
        control_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        control_widget.setMinimumHeight(60)

        palette = self._settings_palette()
        card_bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        card_border = palette.get("--border", "#454545" if theme_manager.night_mode else "#dcdde1")
        hover_bg = palette.get("--hover-bg", "#3a3a3a" if theme_manager.night_mode else "#f2f2f2")
        text_color = palette.get("--fg", "#f4f4f5" if theme_manager.night_mode else "#202124")
        subtle_color = palette.get("--fg-subtle", "#c4c4c4" if theme_manager.night_mode else "#6f7177")
        control_widget.setStyleSheet(f"""
            QFrame#colorSelectorCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 16px;
            }}
            QFrame#colorSelectorCard:hover {{
                background-color: {hover_bg};
                border: 1px solid {card_border};
                border-radius: 16px;
            }}
        """)

        layout = QHBoxLayout(control_widget)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(12)

        preview_label = QLabel()
        preview_label.setFixedSize(34, 34)
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setStyleSheet("background: transparent; border: none;")

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        name_label = QLabel(tr("heatmap_streak_icon", "Streak Icon"))
        name_label.setStyleSheet(f"background: transparent; border: none; font-weight: bold; color: {text_color}; font-size: 13px;")
        sub_label = QLabel(tr("click_to_change"))
        sub_label.setStyleSheet(f"background: transparent; border: none; color: {subtle_color}; font-size: 10px;")
        text_layout.addWidget(name_label)
        text_layout.addWidget(sub_label)

        reset_button = QPushButton()
        reset_button.setFixedSize(24, 24)
        reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_button.setToolTip(tr("reset_to_default_tooltip"))
        reset_button.setStyleSheet(
            "/* onigiri-rounded-button-fix */\n"
            "QPushButton { background-color: transparent; border: 1px solid transparent; border-radius: 12px; }"
            "QPushButton:hover { background-color: rgba(220, 38, 38, 0.12); border: 1px solid transparent; border-radius: 12px; }"
        )
        icon_path = system_icon_path("cancel.svg")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                painter = QPainter(pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor("#ff6b6b" if theme_manager.night_mode else "#d32f2f"))
                painter.end()
                reset_button.setIcon(QIcon(pixmap))
        else:
            reset_button.setText("x")
        reset_button.clicked.connect(self._reset_heatmap_streak_icon_to_default)

        layout.addWidget(preview_label)
        layout.addLayout(text_layout, 1)
        layout.addWidget(reset_button)

        self.heatmap_streak_icon_widget = control_widget
        self.heatmap_streak_icon_preview_label = preview_label
        self.selected_heatmap_streak_icon = self.current_config.get("heatmapStreakIcon", "system:fire.svg")
        if str(self.selected_heatmap_streak_icon).startswith("emoji:"):
            self.selected_heatmap_streak_icon = "system:fire.svg"
        self._refresh_heatmap_streak_icon_control()
        return control_widget

    def _heatmap_streak_icon_color(self):
        line_edit = getattr(self, "heatmap_streak_icon_color_input", None)
        fallback = self.current_config.get("heatmapStreakIconColor", DEFAULTS.get("heatmapStreakIconColor", "#ff6b35"))
        value = line_edit.text() if line_edit else fallback
        return value if QColor(value).isValid() else fallback

    def _heatmap_streak_icon_zero_color(self):
        line_edit = getattr(self, "heatmap_streak_icon_zero_color_input", None)
        fallback = self.current_config.get("heatmapStreakIconZeroColor", DEFAULTS.get("heatmapStreakIconZeroColor", "#8f8f8f"))
        value = line_edit.text() if line_edit else fallback
        return value if QColor(value).isValid() else fallback

    def _refresh_heatmap_streak_icon_control(self):
        preview_label = getattr(self, "heatmap_streak_icon_preview_label", None)
        if preview_label is None:
            return
        value = getattr(self, "selected_heatmap_streak_icon", self.current_config.get("heatmapStreakIcon", "system:fire.svg")) or "system:fire.svg"
        if str(value).startswith("emoji:"):
            value = "system:fire.svg"
            self.selected_heatmap_streak_icon = value
        preview_label.setText("")
        pixmap = self._render_icon_value_pixmap(value, self._heatmap_streak_icon_color(), 30)
        if pixmap.isNull():
            pixmap = self._render_icon_value_pixmap("system:fire.svg", self._heatmap_streak_icon_color(), 30)
        preview_label.setPixmap(pixmap.scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _reset_heatmap_streak_icon_to_default(self):
        self.selected_heatmap_streak_icon = "system:fire.svg"
        if hasattr(self, "heatmap_streak_icon_color_input"):
            self.heatmap_streak_icon_color_input.setText(DEFAULTS.get("heatmapStreakIconColor", "#ff6b35"))
        if hasattr(self, "heatmap_streak_icon_zero_color_input"):
            self.heatmap_streak_icon_zero_color_input.setText(DEFAULTS.get("heatmapStreakIconZeroColor", "#8f8f8f"))
        self._refresh_heatmap_streak_icon_control()
        self._update_heatmap_preview()
        show_settings_toast(self, tr("heatmap_streak_icon_reset_toast", "Streak icon reset to default"))

    def _heatmap_shape_picker_color_options(self):
        return [
            {
                "key": "light_shape",
                "mode": "light",
                "label": tr("heatmap_shape_color", "Shape"),
                "value": self._heatmap_color_value("light", "--heatmap-color"),
                "default": DEFAULTS["colors"]["light"]["--heatmap-color"],
            },
            {
                "key": "light_zero",
                "mode": "light",
                "label": tr("heatmap_shape_zero_color", "Shape (0 reviews)"),
                "value": self._heatmap_color_value("light", "--heatmap-color-zero"),
                "default": DEFAULTS["colors"]["light"]["--heatmap-color-zero"],
            },
            {
                "key": "dark_shape",
                "mode": "dark",
                "label": tr("heatmap_shape_dark_color", "Shape"),
                "value": self._heatmap_color_value("dark", "--heatmap-color"),
                "default": DEFAULTS["colors"]["dark"]["--heatmap-color"],
            },
            {
                "key": "dark_zero",
                "mode": "dark",
                "label": tr("heatmap_shape_zero_dark_color", "Shape (0 reviews)"),
                "value": self._heatmap_color_value("dark", "--heatmap-color-zero"),
                "default": DEFAULTS["colors"]["dark"]["--heatmap-color-zero"],
            },
        ]

    def _apply_heatmap_shape_picker_colors(self, values):
        mapping = {
            "light_shape": ("light", "--heatmap-color"),
            "light_zero": ("light", "--heatmap-color-zero"),
            "dark_shape": ("dark", "--heatmap-color"),
            "dark_zero": ("dark", "--heatmap-color-zero"),
        }
        for key, (mode, color_key) in mapping.items():
            value = values.get(key)
            line_edit = self.color_widgets.get(mode, {}).get(color_key)
            if value and QColor(value).isValid() and line_edit is not None:
                line_edit.setText(value)
        self._update_heatmap_color_cards()
        self._refresh_heatmap_shape_control()
        self._update_heatmap_preview()

    def _heatmap_streak_icon_picker_color_options(self):
        return [
            {
                "key": "active",
                "label": tr("heatmap_streak_icon_color", "Streak Icon Color"),
                "value": self._heatmap_streak_icon_color(),
                "default": DEFAULTS.get("heatmapStreakIconColor", "#ff6b35"),
            },
            {
                "key": "zero",
                "label": tr("heatmap_streak_icon_zero_color", "Streak Icon Color (0 days)"),
                "value": self._heatmap_streak_icon_zero_color(),
                "default": DEFAULTS.get("heatmapStreakIconZeroColor", "#8f8f8f"),
            },
        ]

    def _apply_heatmap_streak_icon_picker_colors(self, values):
        active = values.get("active")
        zero = values.get("zero")
        if active and QColor(active).isValid() and hasattr(self, "heatmap_streak_icon_color_input"):
            self.heatmap_streak_icon_color_input.setText(active)
        if zero and QColor(zero).isValid() and hasattr(self, "heatmap_streak_icon_zero_color_input"):
            self.heatmap_streak_icon_zero_color_input.setText(zero)
        self._refresh_heatmap_streak_icon_control()
        self._update_heatmap_preview()

    def _open_heatmap_streak_icon_selector(self):
        current = getattr(self, "selected_heatmap_streak_icon", self.current_config.get("heatmapStreakIcon", "system:fire.svg"))
        if str(current).startswith("emoji:"):
            current = "system:fire.svg"
        picker = DeckIconPickerDialog(
            current,
            self.addon_path,
            self,
            allow_emoji=False,
            color_options=self._heatmap_streak_icon_picker_color_options(),
            preview_color_key="active",
        )

        def on_selected(value):
            if not value:
                value = "system:fire.svg"
            if str(value).startswith("emoji:"):
                return
            self.selected_heatmap_streak_icon = value
            self._refresh_heatmap_streak_icon_control()
            self._update_heatmap_preview()

        picker.iconSelected.connect(on_selected)
        picker.colorsChanged.connect(self._apply_heatmap_streak_icon_picker_colors)
        picker.exec()

    def _create_heatmap_streak_icon_color_card(self):
        value = self.current_config.get("heatmapStreakIconColor", DEFAULTS.get("heatmapStreakIconColor", "#ff6b35"))
        label_button = self._create_main_bg_button(tr("heatmap_streak_icon_color", "Streak Icon Color"))
        value_button = self._create_main_bg_button("")
        value_button.setObjectName("mainBackgroundColorButton")
        self.heatmap_streak_icon_color_input = QLineEdit(value, self)
        self.heatmap_streak_icon_color_input.hide()

        def choose_color(anchor):
            chosen, ok = OnigiriColorDialog.getColor(self.heatmap_streak_icon_color_input.text(), self, anchor=anchor)
            if ok:
                self.heatmap_streak_icon_color_input.setText(chosen)

        label_button.clicked.connect(lambda _=False, b=label_button: choose_color(b))
        value_button.clicked.connect(lambda _=False, b=value_button: choose_color(b))
        self.heatmap_streak_icon_color_input.textChanged.connect(
            lambda color, b=value_button: self._style_main_background_color_button(
                b, color if QColor(color).isValid() else DEFAULTS.get("heatmapStreakIconColor", "#ff6b35")
            )
        )
        self.heatmap_streak_icon_color_input.textChanged.connect(lambda _=None: self._refresh_heatmap_streak_icon_control())
        self.heatmap_streak_icon_color_input.textChanged.connect(lambda _=None: self._update_heatmap_preview())
        self.heatmap_streak_icon_color_input.textChanged.connect(
            lambda value: self._on_heatmap_streak_color_changed("heatmapStreakIconColor", value)
        )
        self._register_color_sync("flat:heatmapStreakIconColor", self.heatmap_streak_icon_color_input)
        self._style_main_background_color_button(value_button, value)
        return self._create_color_selector_card(label_button, value_button)

    def _on_heatmap_streak_color_changed(self, config_key, value):
        if QColor(value).isValid():
            self.current_config[config_key] = value

    def _create_heatmap_streak_icon_zero_color_card(self):
        value = self.current_config.get("heatmapStreakIconZeroColor", DEFAULTS.get("heatmapStreakIconZeroColor", "#8f8f8f"))
        label_button = self._create_main_bg_button(tr("heatmap_streak_icon_zero_color", "Streak Icon Color (0 days)"))
        value_button = self._create_main_bg_button("")
        value_button.setObjectName("mainBackgroundColorButton")
        self.heatmap_streak_icon_zero_color_input = QLineEdit(value, self)
        self.heatmap_streak_icon_zero_color_input.hide()

        def choose_color(anchor):
            chosen, ok = OnigiriColorDialog.getColor(self.heatmap_streak_icon_zero_color_input.text(), self, anchor=anchor)
            if ok:
                self.heatmap_streak_icon_zero_color_input.setText(chosen)

        label_button.clicked.connect(lambda _=False, b=label_button: choose_color(b))
        value_button.clicked.connect(lambda _=False, b=value_button: choose_color(b))
        self.heatmap_streak_icon_zero_color_input.textChanged.connect(
            lambda color, b=value_button: self._style_main_background_color_button(
                b, color if QColor(color).isValid() else DEFAULTS.get("heatmapStreakIconZeroColor", "#8f8f8f")
            )
        )
        self.heatmap_streak_icon_zero_color_input.textChanged.connect(lambda _=None: self._update_heatmap_preview())
        self.heatmap_streak_icon_zero_color_input.textChanged.connect(
            lambda value: self._on_heatmap_streak_color_changed("heatmapStreakIconZeroColor", value)
        )
        self._register_color_sync("flat:heatmapStreakIconZeroColor", self.heatmap_streak_icon_zero_color_input)
        self._style_main_background_color_button(value_button, value)
        return self._create_color_selector_card(label_button, value_button)

    def _on_heatmap_color_changed(self, mode, key, value, button=None):
        fallback = DEFAULTS["colors"][mode].get(key, "#ffffff")
        color_value = value if QColor(value).isValid() else fallback
        if button is not None:
            self._style_main_background_color_button(button, color_value)
        self._on_palette_color_changed(mode, key, color_value)
        self._update_heatmap_preview()

    def _heatmap_color_value(self, mode, key):
        line_edit = self.color_widgets.get(mode, {}).get(key)
        fallback = DEFAULTS["colors"][mode].get(key, "#ffffff")
        value = line_edit.text() if line_edit else self.current_config.get("colors", {}).get(mode, {}).get(key, fallback)
        return value if QColor(value).isValid() else fallback

    def _update_heatmap_color_cards(self):
        for mode in ("light", "dark"):
            for key, attr in (
                ("--heatmap-color", "shape"),
                ("--heatmap-color-zero", "zero"),
            ):
                button = getattr(self, f"heatmap_{mode}_{attr}_color_button", None)
                if button is not None:
                    self._style_main_background_color_button(button, self._heatmap_color_value(mode, key))

    def _on_heatmap_controls_changed(self, *args):
        self._update_heatmap_preview()

    def _on_heatmap_view_changed(self, *args):
        self._update_heatmap_view_option_visibility()
        self._update_heatmap_preview()

    def _current_heatmap_view_key(self):
        if hasattr(self, "heatmap_view_group"):
            checked = self.heatmap_view_group.checkedButton()
            if checked:
                return checked.property("view_mode") or "year"
        return self.current_config.get("heatmapDefaultView", "year")

    def _update_heatmap_view_option_visibility(self):
        view = self._current_heatmap_view_key()
        related_rows = {
            "year": {self.heatmap_streak_row, self.heatmap_months_row, self.heatmap_weekdays_row},
            "month": {self.heatmap_streak_row, self.heatmap_weekdays_row},
            "week": {self.heatmap_streak_row, self.heatmap_day_labels_row},
        }.get(view, {self.heatmap_streak_row})
        all_rows = (
            self.heatmap_streak_row,
            self.heatmap_months_row,
            self.heatmap_weekdays_row,
            self.heatmap_day_labels_row,
        )
        for row in all_rows:
            self._set_dynamic_mode_widgets_dimmed((row,), row not in related_rows)

    def _on_heatmap_preview_mode_toggled(self, mode):
        self.heatmap_preview_mode = "dark" if mode == "dark" else "light"
        self._update_heatmap_preview()

    def _heatmap_preview_mode(self):
        return getattr(self, "heatmap_preview_mode", "dark" if theme_manager.night_mode else "light")

    def _heatmap_preview_shape(self):
        return getattr(self, "selected_heatmap_shape", self.current_config.get("heatmapShape", "system:square.svg"))

    def _heatmap_preview_view_label(self):
        labels = {
            "year": tr("view_year"),
            "month": tr("view_month"),
            "week": tr("view_week"),
        }
        if hasattr(self, "heatmap_view_group"):
            checked = self.heatmap_view_group.checkedButton()
            if checked:
                return labels.get(checked.property("view_mode"), tr("view_year"))
        return labels.get(self.current_config.get("heatmapDefaultView", "year"), tr("view_year"))

    def _heatmap_gradient_colors(self, mode):
        zero = QColor(self._heatmap_color_value(mode, "--heatmap-color-zero"))
        active = QColor(self._heatmap_color_value(mode, "--heatmap-color"))
        colors = []
        for index in range(5):
            if index == 0:
                colors.append(zero)
            else:
                ratio = index / 4.0
                mixed = QColor(
                    int(zero.red() + (active.red() - zero.red()) * ratio),
                    int(zero.green() + (active.green() - zero.green()) * ratio),
                    int(zero.blue() + (active.blue() - zero.blue()) * ratio),
                )
                colors.append(mixed)
        return colors

    def _draw_heatmap_shape(self, painter, rect, color, icon_value=None):
        icon_value = icon_value or self._heatmap_preview_shape()
        if str(icon_value).lower().endswith("square.svg") or str(icon_value).lower() in {"square", "system:square.svg"}:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(color)))
            radius = max(2.0, min(rect.width(), rect.height()) * 0.18)
            painter.drawRoundedRect(rect, radius, radius)
            return
        pixmap = self._render_icon_value_pixmap(icon_value, QColor(color).name(), int(max(rect.width(), rect.height())))
        if pixmap.isNull():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(color)))
            painter.drawRoundedRect(rect, 4, 4)
        else:
            painter.drawPixmap(rect.toRect(), pixmap)

    def _draw_heatmap_streak_icon(self, painter, rect, color):
        icon_value = getattr(self, "selected_heatmap_streak_icon", self.current_config.get("heatmapStreakIcon", "system:fire.svg")) or "system:fire.svg"
        if str(icon_value).startswith("emoji:"):
            icon_value = "system:fire.svg"
        pixmap = self._render_icon_value_pixmap(icon_value, QColor(color).name(), int(max(rect.width(), rect.height())))
        if not pixmap.isNull():
            painter.drawPixmap(rect.toRect(), pixmap)
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        flame = QPainterPath()
        cx = rect.center().x()
        top = rect.top()
        bottom = rect.bottom()
        flame.moveTo(cx, top)
        flame.cubicTo(rect.right(), top + rect.height() * 0.42, rect.right() - rect.width() * 0.12, bottom, cx, bottom)
        flame.cubicTo(rect.left() + rect.width() * 0.12, bottom, rect.left(), top + rect.height() * 0.48, cx, top)
        painter.setBrush(QBrush(QColor(color)))
        painter.drawPath(flame)
        painter.restore()

    def _draw_heatmap_nav_chevron(self, painter, rect, direction, color):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(color)))
        path = QPainterPath()
        if direction < 0:
            path.moveTo(rect.left() + rect.width() * 0.68, rect.top() + rect.height() * 0.18)
            path.lineTo(rect.left() + rect.width() * 0.30, rect.center().y())
            path.lineTo(rect.left() + rect.width() * 0.68, rect.bottom() - rect.height() * 0.18)
        else:
            path.moveTo(rect.left() + rect.width() * 0.32, rect.top() + rect.height() * 0.18)
            path.lineTo(rect.left() + rect.width() * 0.70, rect.center().y())
            path.lineTo(rect.left() + rect.width() * 0.32, rect.bottom() - rect.height() * 0.18)
        path.closeSubpath()
        painter.drawPath(path)
        painter.restore()

    def _draw_heatmap_preview_contents(self, painter, rect, mode):
        text_color = QColor(self._box_effect_text_color(mode))
        subtle_color = QColor(self._box_effect_small_title_color(mode))
        colors = self._heatmap_gradient_colors(mode)
        surface = QColor(colors[0])
        active = QColor(self.accent_color)

        reference_width = 720.0
        reference_height = 172.0
        s = max(0.45, min(rect.width() / reference_width, rect.height() / reference_height))
        pad_left = 15.0 * s
        pad_right = 15.0 * s
        pad_top = 14.0 * s
        pad_bottom = 15.0 * s
        content = rect.adjusted(pad_left, pad_top, -pad_right, -pad_bottom)
        control_h = 24.0 * s
        header_gap = 4.0 * s
        group_gap = 6.0 * s
        header_margin_bottom = 10.0 * s
        month_row_gap = 5.0 * s
        grid_area_gap = 3.0 * s
        cell_gap = max(0.35, 0.5 * s)
        months_h = 10.0 * s if (getattr(self, "heatmap_show_months_check", None) is None or self.heatmap_show_months_check.isChecked()) else 0.0

        def rounded_rect(fill, border=None, target=None, radius=None):
            target = target or QRectF()
            painter.setPen(QPen(border, 1) if border is not None else Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(fill))
            painter.drawRoundedRect(target, radius if radius is not None else target.height() / 2, radius if radius is not None else target.height() / 2)

        title_font = self._box_effect_preview_font("main", max(8, int(18 * s)))
        title_font.setPointSize(max(8, int(18 * s)))
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(text_color)
        title_text = "Activity"
        title_w = painter.fontMetrics().horizontalAdvance(title_text)
        title_h = max(control_h, painter.fontMetrics().height())

        control_font = self._box_effect_preview_font("main", max(7, int(12 * s)))
        control_font.setPointSize(max(7, int(12 * s)))
        control_font.setBold(True)
        painter.setFont(control_font)
        current_view = "year"
        if hasattr(self, "heatmap_view_group") and self.heatmap_view_group.checkedButton():
            current_view = self.heatmap_view_group.checkedButton().property("view_mode")
        preview_year = 2026
        preview_month = 5
        preview_day = 6
        preview_target = datetime(preview_year, preview_month, preview_day)
        if current_view == "month":
            nav_title = "May 2026"
        elif current_view == "week":
            week_start_for_title = "monday"
            if hasattr(self, "heatmap_week_start_group") and self.heatmap_week_start_group.checkedButton():
                week_start_for_title = self.heatmap_week_start_group.checkedButton().property("week_start")
            week_offset = preview_target.weekday() if week_start_for_title != "sunday" else (preview_target.weekday() + 1) % 7
            week_start_date = datetime.fromordinal(preview_target.toordinal() - week_offset)
            week_end_date = datetime.fromordinal(week_start_date.toordinal() + 6)
            nav_title = f"{week_start_date.strftime('%b')} {week_start_date.day} - {week_end_date.strftime('%b')} {week_end_date.day}"
        else:
            nav_title = str(preview_year)
        nav_btn_w = control_h
        nav_title_w = painter.fontMetrics().horizontalAdvance(nav_title) + 16.0 * s
        nav_w = nav_btn_w * 2 + nav_title_w + header_gap * 2
        filter_labels = [("year", tr("view_year")), ("month", tr("view_month")), ("week", tr("view_week"))]
        filter_button_widths = [painter.fontMetrics().horizontalAdvance(label) + 16.0 * s for _key, label in filter_labels]
        filters_w = sum(filter_button_widths) + 4.0 * s
        streak_text = "125 day streak"
        fire_icon_size = 13.0 * s
        streak_w = painter.fontMetrics().horizontalAdvance(streak_text) + fire_icon_size + 20.0 * s
        show_streak = getattr(self, "heatmap_show_streak_check", None) is None or self.heatmap_show_streak_check.isChecked()
        right_group_w = filters_w + (group_gap + streak_w if show_streak else 0.0)
        header_h = max(title_h, control_h)

        show_months = getattr(self, "heatmap_show_months_check", None) is None or self.heatmap_show_months_check.isChecked()
        show_weekdays = getattr(self, "heatmap_show_weekdays_check", None) is None or self.heatmap_show_weekdays_check.isChecked()
        week_start = "monday"
        if hasattr(self, "heatmap_week_start_group") and self.heatmap_week_start_group.checkedButton():
            week_start = self.heatmap_week_start_group.checkedButton().property("week_start")
        weekday_font = self._box_effect_preview_font("main", max(6, int(9 * s)))
        weekday_font.setPointSize(max(6, int(9 * s)))
        painter.setFont(weekday_font)
        weekday_w = painter.fontMetrics().horizontalAdvance("W") + 4.0 * s if show_weekdays else 0.0
        grid_w = max(1.0, content.width() - weekday_w - (grid_area_gap if show_weekdays else 0.0))
        width_cell = (grid_w - 52 * cell_gap) / 53.0
        fixed_h = header_h + header_margin_bottom + (months_h + month_row_gap if show_months else 0.0)
        available_cell_h = max(1.0, content.height() - fixed_h)
        height_cell = (available_cell_h - 6 * cell_gap) / 7.0
        cell = max(1.4, min(width_cell, height_cell))
        cells_h = 7 * cell + 6 * cell_gap
        grid_total_h = (months_h + month_row_gap if show_months else 0.0) + cells_h
        total_h = header_h + header_margin_bottom + grid_total_h
        header_top = content.top() + max(0.0, (content.height() - total_h) / 2.0)

        header_left_w = title_w + group_gap + nav_w
        if header_left_w + right_group_w + 12 * s > content.width():
            title_w = max(1.0, content.width() - right_group_w - nav_w - group_gap * 2 - 12 * s)
        title_rect = QRectF(content.left(), header_top + (header_h - title_h) / 2.0, title_w, title_h)
        painter.setFont(title_font)
        painter.setPen(text_color)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title_text)

        painter.setFont(control_font)
        nav_x = title_rect.right() + group_gap
        nav_top = header_top + (header_h - control_h) / 2.0
        for text, width in (("prev", nav_btn_w), (nav_title, nav_title_w), ("next", nav_btn_w)):
            target = QRectF(nav_x, nav_top, width, control_h)
            rounded_rect(surface, None, target, 8.0 * s if width == nav_btn_w else 6.0 * s)
            if text == "prev":
                icon_rect = QRectF(target.center().x() - 7.0 * s, target.center().y() - 7.0 * s, 14.0 * s, 14.0 * s)
                self._draw_heatmap_nav_chevron(painter, icon_rect, -1, text_color)
            elif text == "next":
                icon_rect = QRectF(target.center().x() - 7.0 * s, target.center().y() - 7.0 * s, 14.0 * s, 14.0 * s)
                self._draw_heatmap_nav_chevron(painter, icon_rect, 1, text_color)
            else:
                painter.setPen(text_color)
                painter.drawText(target, Qt.AlignmentFlag.AlignCenter, text)
            nav_x += width + header_gap

        filters_x = content.right() - filters_w
        filters_rect = QRectF(filters_x, nav_top, filters_w, control_h)
        rounded_rect(surface, None, filters_rect, 8.0 * s)
        segment_labels = [("year", tr("view_year")), ("month", tr("view_month")), ("week", tr("view_week"))]
        segment_x = filters_rect.left() + 2.0 * s
        for index, (key, label) in enumerate(segment_labels):
            segment_width = filter_button_widths[index]
            item_rect = QRectF(segment_x, filters_rect.top() + 2.0 * s, segment_width, control_h - 4.0 * s)
            if key == current_view:
                rounded_rect(active, None, item_rect, 6.0 * s)
                painter.setPen(QColor("#ffffff"))
            else:
                painter.setPen(subtle_color)
            painter.drawText(item_rect, Qt.AlignmentFlag.AlignCenter, label)
            segment_x += segment_width

        if show_streak:
            streak_rect = QRectF(filters_rect.left() - group_gap - streak_w, nav_top, streak_w, control_h)
            rounded_rect(surface, None, streak_rect, 6.0 * s)
            streak_icon_color = QColor(self._heatmap_streak_icon_color())
            fire_rect = QRectF(streak_rect.left() + 8.0 * s, streak_rect.top() + (streak_rect.height() - fire_icon_size) / 2.0, fire_icon_size, fire_icon_size)
            try:
                self._draw_heatmap_streak_icon(painter, fire_rect, streak_icon_color)
            except Exception:
                pass
            painter.setPen(subtle_color)
            text_rect = streak_rect.adjusted(fire_icon_size + 12.0 * s, 0, -8.0 * s, 0)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, streak_text)

        grid_top = header_top + header_h + header_margin_bottom
        streak_end = datetime(preview_year, preview_month, preview_day)
        streak_start = datetime.fromordinal(streak_end.toordinal() - 124)

        def level_for_date(date):
            if streak_start <= date <= streak_end:
                return 1 + ((date.toordinal() - streak_start.toordinal()) % 4)
            return 0

        def draw_scaled_shape(cell_rect, level):
            shape_rect = cell_rect.adjusted(cell_rect.width() * 0.10, cell_rect.height() * 0.10, -cell_rect.width() * 0.10, -cell_rect.height() * 0.10)
            self._draw_heatmap_shape(painter, shape_rect, colors[max(0, min(4, level))])

        if current_view == "month":
            labels = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat") if week_start == "sunday" else ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
            header_font = self._box_effect_preview_font("main", max(6, int(11 * s)))
            header_font.setPointSize(max(6, int(11 * s)))
            header_font.setBold(True)
            painter.setFont(header_font)
            widest_label = max(painter.fontMetrics().horizontalAdvance(label) for label in labels) + 4.0 * s
            month_header_h = max(14.0 * s, painter.fontMetrics().height() + 2.0 * s) if show_weekdays else 0.0
            month_gap = 8.0 * s if show_weekdays else 0.0
            month_grid_available_h = max(1.0, content.bottom() - grid_top - month_header_h - month_gap)
            month_cell = min(30.0 * s, (content.width() - 6 * 4.0 * s) / 7.0, (month_grid_available_h - 5 * 4.0 * s) / 6.0)
            month_cell = max(month_cell, widest_label if show_weekdays else month_cell)
            if 7 * month_cell + 6 * 4.0 * s > content.width():
                month_cell = (content.width() - 6 * 4.0 * s) / 7.0
            month_cell = max(4.0, month_cell)
            month_gap_size = 4.0 * s
            month_block_w = 7 * month_cell + 6 * month_gap_size
            month_block_h = (month_header_h + month_gap if show_weekdays else 0.0) + 6 * month_cell + 5 * month_gap_size
            month_x = content.left() + max(0.0, (content.width() - month_block_w) / 2.0)
            month_y = grid_top + max(0.0, (content.bottom() - grid_top - month_block_h) / 2.0)
            if show_weekdays:
                painter.setFont(header_font)
                painter.setPen(subtle_color)
                for i, label in enumerate(labels):
                    cell_rect = QRectF(month_x + i * (month_cell + month_gap_size), month_y, month_cell, month_header_h)
                    painter.drawText(cell_rect, Qt.AlignmentFlag.AlignCenter, label)
            first_month_day = datetime(preview_year, preview_month, 1)
            first_month_offset = first_month_day.weekday() if week_start != "sunday" else (first_month_day.weekday() + 1) % 7
            cells_y = month_y + (month_header_h + month_gap if show_weekdays else 0.0)
            last_day = 31
            for day in range(1, last_day + 1):
                slot = first_month_offset + day - 1
                row = slot // 7
                col = slot % 7
                date = datetime(preview_year, preview_month, day)
                cell_rect = QRectF(month_x + col * (month_cell + month_gap_size), cells_y + row * (month_cell + month_gap_size), month_cell, month_cell)
                draw_scaled_shape(cell_rect, level_for_date(date))
            return

        if current_view == "week":
            week_header_h = 34.0 * s if (getattr(self, "heatmap_show_week_header_check", None) is None or self.heatmap_show_week_header_check.isChecked()) else 0.0
            week_gap = 5.0 * s if week_header_h else 0.0
            week_cell = min(40.0 * s, (content.width() - 6 * 4.0 * s) / 7.0, max(1.0, content.bottom() - grid_top - week_header_h - week_gap))
            week_cell = max(5.0, week_cell)
            week_gap_size = 4.0 * s
            week_block_w = 7 * week_cell + 6 * week_gap_size
            week_block_h = week_header_h + week_gap + week_cell
            week_x = content.left() + max(0.0, (content.width() - week_block_w) / 2.0)
            week_y = grid_top + max(0.0, (content.bottom() - grid_top - week_block_h) / 2.0)
            week_offset = preview_target.weekday() if week_start != "sunday" else (preview_target.weekday() + 1) % 7
            week_first = datetime.fromordinal(preview_target.toordinal() - week_offset)
            if week_header_h:
                week_font = self._box_effect_preview_font("main", max(6, int(11 * s)))
                week_font.setPointSize(max(6, int(11 * s)))
                week_font.setBold(True)
                day_font = self._box_effect_preview_font("main", max(7, int(14 * s)))
                day_font.setPointSize(max(7, int(14 * s)))
                day_font.setBold(True)
                for i in range(7):
                    date = datetime.fromordinal(week_first.toordinal() + i)
                    header_rect = QRectF(week_x + i * (week_cell + week_gap_size), week_y, week_cell, week_header_h)
                    painter.setFont(week_font)
                    painter.setPen(subtle_color)
                    painter.drawText(QRectF(header_rect.left(), header_rect.top(), header_rect.width(), header_rect.height() * 0.48), Qt.AlignmentFlag.AlignCenter, date.strftime("%a"))
                    painter.setFont(day_font)
                    painter.setPen(text_color)
                    painter.drawText(QRectF(header_rect.left(), header_rect.top() + header_rect.height() * 0.42, header_rect.width(), header_rect.height() * 0.58), Qt.AlignmentFlag.AlignCenter, str(date.day))
            cells_y = week_y + week_header_h + week_gap
            for i in range(7):
                date = datetime.fromordinal(week_first.toordinal() + i)
                cell_rect = QRectF(week_x + i * (week_cell + week_gap_size), cells_y, week_cell, week_cell)
                draw_scaled_shape(cell_rect, level_for_date(date))
            return

        grid_left = content.left()
        grid_x = grid_left + weekday_w + (grid_area_gap if show_weekdays else 0.0)
        cells_top = grid_top + (months_h + month_row_gap if show_months else 0.0)
        columns = 53
        rows = 7
        grid_actual_w = columns * cell + (columns - 1) * cell_gap
        grid_actual_h = rows * cell + (rows - 1) * cell_gap
        grid_block_w = weekday_w + (grid_area_gap if show_weekdays else 0.0) + grid_actual_w
        grid_block_x = content.left() + max(0.0, (content.width() - grid_block_w) / 2.0)
        grid_left = grid_block_x
        grid_x = grid_left + weekday_w + (grid_area_gap if show_weekdays else 0.0)
        remaining_grid_space = max(0.0, content.bottom() - (cells_top + grid_actual_h))
        if remaining_grid_space > 1:
            shift_y = remaining_grid_space * 0.42
            grid_top += shift_y
            cells_top += shift_y

        if show_months:
            month_font = self._box_effect_preview_font("main", max(6, int(9 * s)))
            month_font.setPointSize(max(6, int(9 * s)))
            painter.setFont(month_font)
            painter.setPen(subtle_color)
            first_day = datetime(2026, 1, 1)
            offset = first_day.weekday() if week_start != "sunday" else (first_day.weekday() + 1) % 7
            start_ord = first_day.toordinal() - offset
            month_names = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
            for month_index, label in enumerate(month_names, start=1):
                week_col = (datetime(2026, month_index, 1).toordinal() - start_ord) // 7
                x = grid_x + week_col * (cell + cell_gap)
                if x < grid_x + grid_actual_w - 8 * s:
                    painter.drawText(QRectF(x + 2.0 * s, grid_top, max(20.0 * s, cell * 4), months_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

        if show_weekdays:
            painter.setFont(weekday_font)
            painter.setPen(subtle_color)
            labels = ("S", "M", "T", "W", "T", "F", "S") if week_start == "sunday" else ("M", "T", "W", "T", "F", "S", "S")
            for row, label in enumerate(labels):
                y = cells_top + row * (cell + cell_gap)
                painter.drawText(QRectF(grid_left, y - 1, weekday_w, cell + 2), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)

        first_day = datetime(2026, 1, 1)
        offset = first_day.weekday() if week_start != "sunday" else (first_day.weekday() + 1) % 7
        last_index = offset + 364
        for col in range(columns):
            for row in range(rows):
                index = col * rows + row
                if index < offset or index > last_index:
                    continue
                date = datetime.fromordinal(first_day.toordinal() + (index - offset))
                rect_cell = QRectF(grid_x + col * (cell + cell_gap), cells_top + row * (cell + cell_gap), cell, cell)
                draw_scaled_shape(rect_cell, level_for_date(date))

    def _draw_heatmap_effect_sample(self, painter, rect, mode, background_pixmap):
        box_color = QColor(self._box_effect_color(mode))
        blur_radius = (self.box_effect_blur_slider.value() / 100.0) * 20.0 if hasattr(self, "box_effect_blur_slider") else 0.0
        fill_alpha = max(0.0, min(1.0, self.box_effect_opacity_slider.value() / 100.0)) if hasattr(self, "box_effect_opacity_slider") else 1.0
        if blur_radius > 0:
            fill_alpha = min(fill_alpha, 0.62)
        box_color.setAlphaF(fill_alpha)

        painter.save()
        path = QPainterPath()
        radius = float(self.box_effect_radius_slider.value() if hasattr(self, "box_effect_radius_slider") else 20)
        path.addRoundedRect(rect, radius, radius)
        if blur_radius > 0 and background_pixmap and not background_pixmap.isNull():
            blurred = self._qt_blurred_pixmap(background_pixmap, blur_radius)
            if not blurred.isNull():
                painter.save()
                painter.setClipPath(path, Qt.ClipOperation.IntersectClip)
                painter.drawPixmap(0, 0, blurred)
                painter.restore()
        painter.fillPath(path, QBrush(box_color))
        stroke_width = max(0, int(self.box_effect_stroke_slider.value() if hasattr(self, "box_effect_stroke_slider") else 1))
        if stroke_width > 0:
            border_pen = QPen(QColor(self._box_effect_border_color(mode)))
            border_pen.setWidth(stroke_width)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
        painter.setClipPath(path, Qt.ClipOperation.IntersectClip)
        self._draw_heatmap_preview_contents(painter, rect, mode)
        painter.restore()

    def _render_heatmap_preview_pixmap(self):
        size = self.heatmap_preview.size()
        width = max(1, size.width())
        height = max(1, size.height())
        dpr = max(1.0, self.heatmap_preview.devicePixelRatioF())
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

        mode = self._heatmap_preview_mode()
        background = self._render_box_effect_background_for_mode(mode, width, height)
        painter.drawPixmap(0, 0, background)
        card_w = width * 0.94
        card_h = min(height * 0.91, card_w / 4.26)
        if card_h < height * 0.64:
            card_h = height * 0.91
            card_w = min(width * 0.94, card_h * 4.47)
        content_rect = QRectF((width - card_w) / 2.0, (height - card_h) / 2.0, card_w, card_h)
        self._draw_heatmap_effect_sample(painter, content_rect, mode, background)

        painter.setClipping(False)
        border_color = QColor("#4b5563" if theme_manager.night_mode else "#d1d5db")
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()
        return target

    def _update_heatmap_preview(self):
        if not hasattr(self, "heatmap_preview"):
            return
        self.heatmap_preview.setStyleSheet("QLabel#mainBackgroundPreview { background: transparent; border: none; }")
        try:
            self.heatmap_preview.setPixmap(self._render_heatmap_preview_pixmap())
        except Exception as exc:
            print(f"Onigiri: failed to render heatmap settings preview: {exc}")
            fallback = QPixmap(max(1, self.heatmap_preview.width()), max(1, self.heatmap_preview.height()))
            fallback.fill(Qt.GlobalColor.transparent)
            self.heatmap_preview.setPixmap(fallback)
        self.heatmap_preview.setText("")

    def _create_organize_layout_widget(self):
        # This widget contains the unified layout editor
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # Use the new unified layout editor
        self.unified_layout_editor = self.UnifiedLayoutEditor(self)
        layout.addWidget(self.unified_layout_editor)
        
        return container

    def _open_heatmap_icon_selector(self):
        current = getattr(self, "selected_heatmap_shape", self.current_config.get("heatmapShape", "square.svg"))
        if str(current).startswith("emoji:"):
            current = "system:square.svg"
        picker = DeckIconPickerDialog(
            current,
            self.addon_path,
            self,
            allow_emoji=False,
            color_options=self._heatmap_shape_picker_color_options(),
            preview_color_key="light_shape",
        )

        def on_selected(value):
            if not value:
                value = "system:square.svg"
            if str(value).startswith("emoji:"):
                return
            self.selected_heatmap_shape = value
            if hasattr(self, "heatmap_custom_shape_button"):
                self.heatmap_custom_shape_button.setProperty("shape_filename", value)
                self.heatmap_custom_shape_button.setChecked(True)
                self._refresh_heatmap_custom_shape_button()
            self._refresh_heatmap_shape_control()
            self._update_heatmap_preview()

        picker.iconSelected.connect(on_selected)
        picker.colorsChanged.connect(self._apply_heatmap_shape_picker_colors)
        picker.exec()

    def _refresh_heatmap_custom_shape_button(self):
        if not hasattr(self, "heatmap_custom_shape_button"):
            return
        value = self.heatmap_custom_shape_button.property("shape_filename") or "system:square.svg"
        if str(value).startswith("emoji:"):
            self.heatmap_custom_shape_button.setText(str(value)[len("emoji:"):])
            self.heatmap_custom_shape_button.setIcon(QIcon())
            return
        self.heatmap_custom_shape_button.setText("")
        pixmap = self._render_icon_value_pixmap(value, self.accent_color, 28)
        if not pixmap.isNull():
            self.heatmap_custom_shape_button.setIcon(QIcon(pixmap))
            self.heatmap_custom_shape_button.setIconSize(QSize(28, 28))

    def reset_heatmap_colors_to_default(self):
        """Reset only the heatmap-related colors to their default values."""
        heatmap_color_keys = ["--heatmap-color", "--heatmap-color-zero"]
        default_colors = DEFAULTS["colors"]

        for mode in ["light", "dark"]:
            for key in heatmap_color_keys:
                if key in self.color_widgets[mode] and key in default_colors[mode]:
                    widget = self.color_widgets[mode][key]
                    default_value = default_colors[mode][key]
                    widget.setText(default_value)
        
        show_settings_toast(self, tr("heatmap_colors_reset_toast", "Heatmap colors reset — press Save to apply"))

    def _save_main_menu_settings(self):
        mw.col.conf["modern_menu_statsTitle"] = self.stats_title_input.text()
        
        # Save Heatmap Default View
        if hasattr(self, "heatmap_view_group"):
            checked_btn = self.heatmap_view_group.checkedButton()
            if checked_btn:
                self.current_config["heatmapDefaultView"] = checked_btn.property("view_mode")
        if hasattr(self, "heatmap_week_start_group"):
            checked_btn = self.heatmap_week_start_group.checkedButton()
            if checked_btn:
                self.current_config["heatmapWeekStart"] = checked_btn.property("week_start")
        
        if hasattr(self, "selected_heatmap_shape"):
            self.current_config["heatmapShape"] = self.selected_heatmap_shape
        if hasattr(self, "selected_heatmap_streak_icon"):
            self.current_config["heatmapStreakIcon"] = self.selected_heatmap_streak_icon
        if hasattr(self, "heatmap_streak_icon_color_input"):
            self.current_config["heatmapStreakIconColor"] = self._heatmap_streak_icon_color()
        if hasattr(self, "heatmap_streak_icon_zero_color_input"):
            self.current_config["heatmapStreakIconZeroColor"] = self._heatmap_streak_icon_zero_color()
        
        self.current_config["heatmapShowStreak"] = self.heatmap_show_streak_check.isChecked()
        self.current_config["heatmapShowMonths"] = self.heatmap_show_months_check.isChecked()
        self.current_config["heatmapShowWeekdays"] = self.heatmap_show_weekdays_check.isChecked()
        self.current_config["heatmapShowWeekHeader"] = self.heatmap_show_week_header_check.isChecked()
        
        if hasattr(self, "hide_retention_stars_check"):
            self.current_config["hideRetentionStars"] = self.hide_retention_stars_check.isChecked()

        if hasattr(self, "retention_star_widget") and self.retention_star_widget:
            key = "retention_star"
            value = self.retention_star_widget.property("icon_filename")
            config_key = f"modern_menu_icon_{key}"
            if value:
                mw.col.conf[config_key] = value
            else:
                mw.col.conf[config_key] = ""

        stats_color_keys = ["--star-color", "--empty-star-color", "--heatmap-color", "--heatmap-color-zero"]
        for mode in ["light", "dark"]:
            for key in stats_color_keys:
                if key in self.color_widgets[mode]:
                    widget = self.color_widgets[mode][key]
                    self.current_config["colors"][mode][key] = widget.text()

        # --- Main Background Settings ---
        if hasattr(self, "main_bg_color_only_toggle"):
            if self.main_bg_color_only_toggle.isChecked():
                mw.col.conf["modern_menu_background_mode"] = "color"
            elif self.main_bg_slideshow_toggle.isChecked():
                mw.col.conf["modern_menu_background_mode"] = "slideshow"
            else:
                mw.col.conf["modern_menu_background_mode"] = "image_color"

            color_theme_mode = "separate" if self.main_bg_dynamic_toggle.isChecked() else "single"
            image_theme_mode = "separate" if self.main_bg_dynamic_toggle.isChecked() else "single"
            mw.col.conf["modern_menu_bg_color_theme_mode"] = color_theme_mode
            mw.col.conf["modern_menu_bg_image_theme_mode"] = image_theme_mode
            mw.col.conf["modern_menu_background_image_mode"] = image_theme_mode

            if color_theme_mode == "single":
                single_color = self.main_bg_single_color_input.text()
                mw.col.conf["modern_menu_bg_color_light"] = single_color
                mw.col.conf["modern_menu_bg_color_dark"] = single_color
            else:
                light_bg_val = self.main_bg_light_color_input.text()
                dark_bg_val = self.main_bg_dark_color_input.text()
                mw.col.conf["modern_menu_bg_color_light"] = light_bg_val
                mw.col.conf["modern_menu_bg_color_dark"] = dark_bg_val

            single_image = self.galleries.get('main_single', {}).get('selected', '')
            light_image = self.galleries.get('main_light', {}).get('selected', '')
            dark_image = self.galleries.get('main_dark', {}).get('selected', '')
            if image_theme_mode == "single":
                mw.col.conf["modern_menu_background_image"] = single_image
                mw.col.conf["modern_menu_background_image_light"] = single_image
                mw.col.conf["modern_menu_background_image_dark"] = single_image
            else:
                mw.col.conf["modern_menu_background_image"] = light_image or dark_image
                mw.col.conf["modern_menu_background_image_light"] = light_image
                mw.col.conf["modern_menu_background_image_dark"] = dark_image

            mw.col.conf["modern_menu_slideshow_images"] = list(getattr(self, "main_bg_slideshow_images", []))
            mw.col.conf["modern_menu_slideshow_interval"] = self.main_bg_slideshow_interval_spinbox.value()
            mw.col.conf["modern_menu_background_blur"] = self.main_bg_blur_slider.value()
            mw.col.conf["modern_menu_background_opacity"] = self.main_bg_opacity_slider.value()
        else:
            if self.image_color_radio.isChecked():
                mw.col.conf["modern_menu_background_mode"] = "image_color"
            elif self.slideshow_radio.isChecked():
                mw.col.conf["modern_menu_background_mode"] = "slideshow"
            else:
                mw.col.conf["modern_menu_background_mode"] = "accent" if self.color_theme_accent_radio.isChecked() else "color"

        self._save_box_effect_settings()

    def _save_organize_settings(self):
        """Saves the layout from the unified layout editor."""
        if hasattr(self, 'unified_layout_editor'):
            layout_config = self.unified_layout_editor.get_layout_config()
            self.current_config['onigiriWidgetLayout'] = layout_config['onigiri']
            self.current_config['externalWidgetLayout'] = layout_config['external']
            # Save the row count setting
            self.current_config['unifiedGridRows'] = self.unified_layout_editor._applied_row_count

    def _draw_overview_style_congrats_sample(self, painter, rect, mode, background_pixmap, draw_profile=True):
        show_profile = self.show_congrats_profile_bar_checkbox.isChecked()
        effects = self._overview_style_effect_values()
        blur_radius = (effects["blur"] / 100.0) * 20.0
        card_alpha = max(0.0, min(1.0, effects["opacity"] / 100.0))
        if blur_radius > 0:
            card_alpha = min(card_alpha, 0.82)
        radius = float(effects["radius"])
        stroke_width = max(0, int(effects["stroke"]))

        card_width = min(rect.width() * 0.70, 640)
        card_height = min(rect.height() * 0.42, 210)
        card_y = rect.y() + (rect.height() - card_height) / 2
        bar_rect = self._overview_style_profile_bar_rect(rect, card_y - 32)
        card_rect = QRectF(rect.x() + (rect.width() - card_width) / 2, card_y, card_width, card_height)
        card_color = QColor(self._overview_style_color("box_bg", mode))
        card_color.setAlphaF(card_alpha)
        path = QPainterPath()
        path.addRoundedRect(card_rect, radius, radius)
        if blur_radius > 0 and background_pixmap and not background_pixmap.isNull():
            blurred = self._qt_blurred_pixmap(background_pixmap, blur_radius)
            if not blurred.isNull():
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, blurred)
                painter.setClipping(False)
        painter.fillPath(path, QBrush(card_color))
        if stroke_width > 0:
            painter.setPen(QPen(QColor(self._overview_style_color("box_border", mode)), stroke_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        message = self.congrats_message_input.text().strip() if hasattr(self, "congrats_message_input") else ""
        if not message:
            message = DEFAULTS.get("congratsMessage", "Congratulations! You have finished this deck for now.")
        painter.setPen(QColor(self._box_effect_text_color(mode)))
        font = self._box_effect_preview_font("main", 25)
        painter.setFont(font)
        painter.drawText(
            card_rect.adjusted(26, 18, -26, -18),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            message,
        )
        if show_profile and draw_profile:
            self._draw_overview_style_profile_bar(painter, rect, mode, bar_rect)
