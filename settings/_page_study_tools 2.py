# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._widgets import *
from ._layout_base import *


class PageStudyToolsMixin:
    def _create_tools_segmented_control(self, options, button_group, checked_key, property_name, min_button_width=96):
        shell = self._create_organize_segmented_control(
            options,
            button_group,
            checked_key,
            property_name,
            fill_width=True,
            segment_height=34,
            min_button_width=min_button_width,
        )
        shell.setMinimumWidth(max(280, min_button_width * max(2, len(options))))
        shell.setMaximumWidth(760)
        return shell

    def _create_tools_line_edit(self, value, placeholder):
        line_edit = QLineEdit(value)
        line_edit.setPlaceholderText(placeholder)
        line_edit.setMinimumWidth(260)
        line_edit.setMaximumWidth(440)
        line_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return line_edit

    def _create_tools_toggle_row(self, title, description, toggle_widget):
        row = QFrame()
        row.setObjectName("settingRow")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        text = self._create_tools_row_text(title, description)
        layout.addWidget(text, 1)
        layout.addWidget(toggle_widget, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    def _create_tools_control_row(self, title, description, control_widget, align_top=False):
        row = QFrame()
        row.setObjectName("settingRow")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(16)

        text = self._create_tools_row_text(title, description)
        layout.addWidget(text, 1)
        alignment = Qt.AlignmentFlag.AlignTop if align_top else Qt.AlignmentFlag.AlignVCenter
        layout.addWidget(control_widget, 0, alignment)
        return row

    def _create_tools_row_text(self, title, description):
        text = QWidget()
        text_layout = QVBoxLayout(text)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)

        title_label = QLabel(title)
        title_label.setObjectName("settingRowTitle")
        title_label.setWordWrap(True)
        text_layout.addWidget(title_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setObjectName("settingRowDescription")
            desc_label.setWordWrap(True)
            text_layout.addWidget(desc_label)
        return text

    def _style_tools_page(self, page):
        palette = self._settings_palette()
        panel = palette.get("--canvas-inset", "#ffffff")
        surface = palette.get("--highlight-bg", "#f2f2f2")
        fg = palette.get("--fg", "#202124")
        muted = palette.get("--fg-subtle", "#6f7177")
        border = palette.get("--border", "#e0e0e0")
        accent = self._settings_accent_color()
        page.setStyleSheet(page.styleSheet() + f"""
            QLabel#toolsValuePill {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 17px;
                color: {muted};
                padding: 6px 12px;
                font-size: 13px;
            }}
            QPlainTextEdit#toolsPromptInput {{
                min-width: 320px;
                max-width: 520px;
                border-radius: 18px;
            }}
            QPushButton#toolsOpenButton {{
                background: {panel};
                color: {fg};
                border: 1px solid {border};
                border-radius: 20px;
                font-weight: 700;
            }}
            QPushButton#toolsOpenButton:hover {{
                background: {surface};
                border-color: {accent};
                color: {fg};
            }}
        """)

    def create_prep_station_page(self):
        page, layout = self._create_scrollable_page()

        intro = QLabel("A study planner for tracking exam preparation: set exam dates, select decks, manage to-do lists, and see the daily card pace needed to be ready in time.")
        intro.setObjectName("sectionDescription")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        open_section = SectionGroup("", self, border=False)
        open_btn = QPushButton("Open Prep Station")
        open_btn.setObjectName("toolsOpenButton")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setFixedHeight(40)
        self._decorate_button(open_btn, "stats.svg", 16)
        open_btn.clicked.connect(self._open_prep_station)
        open_section.content_layout.addWidget(open_btn)
        layout.addWidget(open_section)

        try:
            self.create_prep_station_pace_section(layout)
            self.create_prep_station_widget_section(layout)
            self.create_prep_station_background_section(layout)
            self.create_prep_station_chart_section(layout)
        except Exception as exc:
            import traceback
            print(f"Onigiri: Prep Station settings build error: {exc}")
            traceback.print_exc()

        layout.addStretch()
        self._style_tools_page(page)
        return page

    def _save_prep_station_settings(self):
        self._save_prep_station_pace_settings()
        self._save_prep_station_widget_settings()
        self._save_prep_station_background_settings()
        self._save_prep_station_chart_settings()

    # ─── Prep Station pace & statistics ───────────────────────────────────

    def create_prep_station_pace_section(self, parent_layout):
        designer = QFrame()
        designer.setObjectName("mainBackgroundDesigner")
        outer = QVBoxLayout(designer)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(10)

        title_label = QLabel(tr("prep_pace_section_title", "Pace & Statistics"))
        title_label.setObjectName("sectionTitle")
        title_label.setWordWrap(True)
        outer.addWidget(title_label)

        self.prep_suspended_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.prep_suspended_toggle.setChecked(bool(mw.col.conf.get("onigiri_prep_station_include_suspended", False)))
        outer.addWidget(self._create_main_bg_toggle_row(
            tr("prep_suspended_label", "Count suspended cards"),
            self.prep_suspended_toggle,
        ))

        desc = QLabel(tr(
            "prep_suspended_setting_desc",
            "When on, suspended cards count toward each plan's pace calculation and statistics.",
        ))
        desc.setObjectName("sectionDescription")
        desc.setWordWrap(True)
        outer.addWidget(desc)

        parent_layout.addWidget(designer)

    def _save_prep_station_pace_settings(self):
        if not hasattr(self, "prep_suspended_toggle"):
            return
        mw.col.conf["onigiri_prep_station_include_suspended"] = self.prep_suspended_toggle.isChecked()

    # ─── Prep Station deck-browser widget ─────────────────────────────────

    def create_prep_station_widget_section(self, parent_layout):
        designer = QFrame()
        designer.setObjectName("mainBackgroundDesigner")
        outer = QVBoxLayout(designer)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(10)

        title_label = QLabel(tr("prep_widget_section_title", "Study Plans Widget"))
        title_label.setObjectName("sectionTitle")
        title_label.setWordWrap(True)
        outer.addWidget(title_label)

        desc = QLabel(tr("prep_widget_font_desc", "Font size of the Study Plans preview shown on the deck browser widget."))
        desc.setObjectName("sectionDescription")
        desc.setWordWrap(True)
        outer.addWidget(desc)

        slider_palette = self._settings_palette()
        slider_track = slider_palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = slider_palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")

        self.prep_widget_font_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.prep_widget_font_slider.setRange(60, 160)
        self.prep_widget_font_slider.setValue(int(mw.col.conf.get("onigiri_prep_station_widget_font_scale", 100)))
        self.prep_widget_font_value_label = QLabel(f"{self.prep_widget_font_slider.value()}%")
        self.prep_widget_font_value_label.setObjectName("mainBackgroundValueLabel")
        self.prep_widget_font_value_label.setFixedWidth(48)
        font_value = QWidget()
        font_layout = QHBoxLayout(font_value)
        font_layout.setContentsMargins(0, 0, 0, 0)
        font_layout.setSpacing(10)
        font_layout.addWidget(self.prep_widget_font_slider, 1)
        font_layout.addWidget(self.prep_widget_font_value_label)
        self.prep_widget_font_slider.valueChanged.connect(
            lambda v: self.prep_widget_font_value_label.setText(f"{v}%")
        )

        outer.addWidget(self._create_main_bg_value_row(tr("prep_widget_font_label", "Font Size"), font_value))
        parent_layout.addWidget(designer)

    def _save_prep_station_widget_settings(self):
        if not hasattr(self, "prep_widget_font_slider"):
            return
        mw.col.conf["onigiri_prep_station_widget_font_scale"] = self.prep_widget_font_slider.value()

    def _open_prep_station(self):
        self._save_prep_station_settings()
        from .. import prep_station
        prep_station.open_prep_station(self)

    # ─── Prep Station Background Bar ──────────────────────────────────────

    def create_prep_station_background_section(self, parent_layout):
        designer = QFrame()
        designer.setObjectName("mainBackgroundDesigner")
        outer = QVBoxLayout(designer)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel("Prep Station Background Bar")
        title_label.setObjectName("sectionTitle")
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.prep_bg_preview_mode = "dark" if theme_manager.night_mode else "light"
        self.prep_bg_preview_mode_widget, self.prep_bg_preview_mode_toggle = self._create_light_dark_mode_toggle(
            self.prep_bg_preview_mode,
            self._on_prep_bg_preview_mode_toggled,
        )
        header_layout.addWidget(self.prep_bg_preview_mode_widget)
        outer.addLayout(header_layout)

        from ..prep_station_ui import BgBarPreview
        self.prep_bg_preview = BgBarPreview()
        outer.addWidget(self.prep_bg_preview)

        self.prep_bg_sync_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.prep_bg_sync_toggle.setChecked(bool(mw.col.conf.get("onigiri_prep_station_bg_sync_profile", True)))
        self.prep_bg_dynamic_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.prep_bg_dynamic_toggle.setChecked(bool(mw.col.conf.get("onigiri_prep_station_bg_dynamic_mode", True)))

        left = QWidget()
        left.setMinimumWidth(0)
        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        left_layout = QGridLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setHorizontalSpacing(10)
        left_layout.setVerticalSpacing(10)

        self.prep_bg_import_button = self._create_main_bg_button("Import")
        self.prep_bg_clear_button = self._create_main_bg_button("Clear image")
        self.prep_bg_light_color_button = self._create_main_bg_button("Color")
        self.prep_bg_light_color_value_button = self._create_main_bg_button("")
        self.prep_bg_light_color_value_button.setObjectName("mainBackgroundColorButton")
        self.prep_bg_dark_color_button = self._create_main_bg_button("Dark Color")
        self.prep_bg_dark_color_value_button = self._create_main_bg_button("")
        self.prep_bg_dark_color_value_button.setObjectName("mainBackgroundColorButton")
        self.prep_bg_light_color_card = self._create_color_selector_card(self.prep_bg_light_color_button, self.prep_bg_light_color_value_button)
        self.prep_bg_dark_color_card = self._create_color_selector_card(self.prep_bg_dark_color_button, self.prep_bg_dark_color_value_button)

        left_layout.addWidget(self.prep_bg_import_button, 0, 0)
        left_layout.addWidget(self.prep_bg_clear_button, 0, 1)
        left_layout.addWidget(self.prep_bg_light_color_card, 1, 0, 1, 2)
        left_layout.addWidget(self.prep_bg_dark_color_card, 2, 0, 1, 2)

        right = QWidget()
        right.setMinimumWidth(0)
        right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        slider_palette = self._settings_palette()
        slider_track = slider_palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = slider_palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")

        self.prep_bg_blur_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.prep_bg_blur_slider.setRange(0, 100)
        self.prep_bg_blur_slider.setValue(int(mw.col.conf.get("onigiri_prep_station_bg_blur", 0)))
        self.prep_bg_blur_value_label = QLabel(f"{self.prep_bg_blur_slider.value()}%")
        self.prep_bg_blur_value_label.setObjectName("mainBackgroundValueLabel")
        self.prep_bg_blur_value_label.setFixedWidth(48)
        blur_value = QWidget()
        blur_layout = QHBoxLayout(blur_value)
        blur_layout.setContentsMargins(0, 0, 0, 0)
        blur_layout.setSpacing(10)
        blur_layout.addWidget(self.prep_bg_blur_slider, 1)
        blur_layout.addWidget(self.prep_bg_blur_value_label)

        self.prep_bg_opacity_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.prep_bg_opacity_slider.setRange(0, 100)
        self.prep_bg_opacity_slider.setValue(int(mw.col.conf.get("onigiri_prep_station_bg_opacity", 100)))
        self.prep_bg_opacity_value_label = QLabel(f"{self.prep_bg_opacity_slider.value()}%")
        self.prep_bg_opacity_value_label.setObjectName("mainBackgroundValueLabel")
        self.prep_bg_opacity_value_label.setFixedWidth(48)
        opacity_value = QWidget()
        opacity_layout = QHBoxLayout(opacity_value)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(10)
        opacity_layout.addWidget(self.prep_bg_opacity_slider, 1)
        opacity_layout.addWidget(self.prep_bg_opacity_value_label)

        right_layout.addWidget(self._create_main_bg_value_row("Blur", blur_value))
        right_layout.addWidget(self._create_main_bg_value_row("Opacity", opacity_value))
        right_layout.addWidget(self._create_main_bg_toggle_row("Dynamic Mode", self.prep_bg_dynamic_toggle))
        right_layout.addStretch()

        controls = ResponsivePairWidget(right, left, spacing=18, breakpoint=620)
        outer.addWidget(controls)

        outer.addWidget(self._create_main_bg_toggle_row("Sync with Profile Bar Background", self.prep_bg_sync_toggle))

        self.prep_bg_light_color_input = QLineEdit(mw.col.conf.get("onigiri_prep_station_bg_color_light", "#3B82F6"))
        self.prep_bg_dark_color_input = QLineEdit(mw.col.conf.get("onigiri_prep_station_bg_color_dark", "#1f1e1c"))
        self._prep_bg_image_light = mw.col.conf.get("onigiri_prep_station_bg_image_light", "")
        self._prep_bg_image_dark = mw.col.conf.get("onigiri_prep_station_bg_image_dark", "")
        self._prep_bg_mode = mw.col.conf.get("onigiri_prep_station_bg_mode", "color")

        self.prep_bg_import_button.clicked.connect(self._import_prep_bg_image)
        self.prep_bg_clear_button.clicked.connect(self._clear_prep_bg_image)
        self.prep_bg_light_color_button.clicked.connect(lambda: self._choose_prep_bg_color("light"))
        self.prep_bg_light_color_value_button.clicked.connect(lambda: self._choose_prep_bg_color("light"))
        self.prep_bg_dark_color_button.clicked.connect(lambda: self._choose_prep_bg_color("dark"))
        self.prep_bg_dark_color_value_button.clicked.connect(lambda: self._choose_prep_bg_color("dark"))
        self.prep_bg_sync_toggle.toggled.connect(lambda _checked: self._update_prep_bg_controls())
        self.prep_bg_dynamic_toggle.toggled.connect(lambda _checked: self._update_prep_bg_controls())
        self.prep_bg_blur_slider.valueChanged.connect(lambda v: (self.prep_bg_blur_value_label.setText(f"{v}%"), self._update_prep_bg_preview()))
        self.prep_bg_opacity_slider.valueChanged.connect(lambda v: (self.prep_bg_opacity_value_label.setText(f"{v}%"), self._update_prep_bg_preview()))

        self._update_prep_bg_controls()
        parent_layout.addWidget(designer)

    def _prep_bg_folder_path(self):
        path = os.path.join(self.addon_path, "user_files", "prep_station_bg")
        os.makedirs(path, exist_ok=True)
        return path

    def _on_prep_bg_preview_mode_toggled(self, mode):
        self.prep_bg_preview_mode = "dark" if mode == "dark" else "light"
        self._update_prep_bg_preview()

    def _choose_prep_bg_color(self, target):
        line_edit = self.prep_bg_light_color_input if target == "light" else self.prep_bg_dark_color_input
        chosen, ok = OnigiriColorDialog.getColor(line_edit.text(), self, anchor=self.sender() if isinstance(self.sender(), QWidget) else None)
        if ok:
            line_edit.setText(chosen)
            self._prep_bg_mode = "color"
            self._update_prep_bg_preview()

    def _import_prep_bg_image(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Image", "", "Images (*.png *.jpg *.jpeg *.gif *.webp)")
        if not filepath:
            return
        filename = os.path.basename(filepath)
        dest_path = os.path.join(self._prep_bg_folder_path(), filename)
        base, ext = os.path.splitext(filename)
        index = 2
        while os.path.exists(dest_path) and os.path.abspath(filepath) != os.path.abspath(dest_path):
            filename = f"{base}-{index}{ext}"
            dest_path = os.path.join(self._prep_bg_folder_path(), filename)
            index += 1
        try:
            if os.path.abspath(filepath) != os.path.abspath(dest_path):
                shutil.copy(filepath, dest_path)
            if self.prep_bg_preview_mode == "dark":
                self._prep_bg_image_dark = filename
            else:
                self._prep_bg_image_light = filename
            self._prep_bg_mode = "image"
            self._update_prep_bg_preview()
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not import image: {exc}")

    def _clear_prep_bg_image(self):
        if self.prep_bg_preview_mode == "dark":
            self._prep_bg_image_dark = ""
        else:
            self._prep_bg_image_light = ""
        self._prep_bg_mode = "color"
        self._update_prep_bg_preview()

    def _update_prep_bg_controls(self):
        if not hasattr(self, "prep_bg_preview"):
            return
        synced = self.prep_bg_sync_toggle.isChecked()
        lock_hint = "Disable Sync with Profile Bar Background to edit this control."
        for widget in (
            self.prep_bg_import_button, self.prep_bg_clear_button,
            self.prep_bg_light_color_card, self.prep_bg_dark_color_card,
            self.prep_bg_blur_slider, self.prep_bg_opacity_slider,
            self.prep_bg_dynamic_toggle,
        ):
            widget.setEnabled(not synced)
            widget.setToolTip(lock_hint if synced else "")

        dynamic = self.prep_bg_dynamic_toggle.isChecked()
        self.prep_bg_light_color_button.setText("Light Color" if dynamic else "Color")
        self._set_dynamic_mode_widgets_dimmed([self.prep_bg_dark_color_card], synced or not dynamic)
        self._update_prep_bg_preview()

    def _prep_bg_color_for_mode(self, dark):
        dynamic = getattr(self, "prep_bg_dynamic_toggle", None) and self.prep_bg_dynamic_toggle.isChecked()
        if dark and dynamic:
            return self.prep_bg_dark_color_input.text()
        return self.prep_bg_light_color_input.text()

    def _resolve_prep_bg_for_preview(self, dark):
        """Live (unsaved) resolution of the Prep Station header background for
        previews. Returns (color_hex, QPixmap|None, opacity_percent)."""
        if self.prep_bg_sync_toggle.isChecked():
            conf = mw.col.conf
            bg_mode = conf.get("modern_menu_profile_bg_mode", "image")
            if bg_mode == "accent":
                color = self._settings_accent_color()
            else:
                color = conf.get(f"modern_menu_profile_bg_color_{'dark' if dark else 'light'}", "#3B82F6")
            opacity = int(conf.get("modern_menu_profile_bg_opacity", 50) or 50)
            pixmap = QPixmap()
            if bg_mode == "image":
                fn = conf.get("modern_menu_profile_bg_image", "")
                path = os.path.join(self.addon_path, "user_files", "profile_bg", fn) if fn else ""
                if not path or not os.path.exists(path):
                    path = os.path.join(self.addon_path, "system_files", "profile_default", "onigiri-bg.png")
                if os.path.exists(path):
                    pixmap = QPixmap(path)
            return color, (pixmap if not pixmap.isNull() else None), opacity

        color = self._prep_bg_color_for_mode(dark)
        image_filename = self._prep_bg_image_dark if dark else self._prep_bg_image_light
        opacity = self.prep_bg_opacity_slider.value()
        pixmap = QPixmap()
        if self._prep_bg_mode == "image" and image_filename:
            path = os.path.join(self._prep_bg_folder_path(), image_filename)
            if os.path.exists(path):
                pixmap = QPixmap(path)
        return color, (pixmap if not pixmap.isNull() else None), opacity

    def _update_prep_bg_preview(self):
        if not hasattr(self, "prep_bg_preview"):
            return
        dark = self.prep_bg_preview_mode == "dark"
        # Reflect the chosen colors onto their swatch buttons
        for line_edit, value_btn in (
            (self.prep_bg_light_color_input, self.prep_bg_light_color_value_button),
            (self.prep_bg_dark_color_input, self.prep_bg_dark_color_value_button),
        ):
            value_btn.setStyleSheet(
                value_btn.styleSheet() + f"\nQPushButton#mainBackgroundColorButton {{ background-color: {line_edit.text()}; }}"
            )
        color, pixmap, opacity = self._resolve_prep_bg_for_preview(dark)
        self.prep_bg_preview.set_background(color, pixmap, opacity)
        # Keep the chart preview's band in sync with the background bar
        self._update_prep_chart_band()

    def _update_prep_chart_band(self):
        if not hasattr(self, "prep_chart_preview"):
            return
        dark = getattr(self, "prep_chart_preview_mode", "dark" if theme_manager.night_mode else "light") == "dark"
        color, pixmap, opacity = self._resolve_prep_bg_for_preview(dark)
        self.prep_chart_preview.set_band(color, pixmap, opacity)

    def _save_prep_station_background_settings(self):
        if not hasattr(self, "prep_bg_sync_toggle"):
            return
        mw.col.conf["onigiri_prep_station_bg_sync_profile"] = self.prep_bg_sync_toggle.isChecked()
        mw.col.conf["onigiri_prep_station_bg_dynamic_mode"] = self.prep_bg_dynamic_toggle.isChecked()
        mw.col.conf["onigiri_prep_station_bg_mode"] = self._prep_bg_mode
        mw.col.conf["onigiri_prep_station_bg_color_light"] = self.prep_bg_light_color_input.text()
        mw.col.conf["onigiri_prep_station_bg_color_dark"] = (
            self.prep_bg_dark_color_input.text() if self.prep_bg_dynamic_toggle.isChecked() else self.prep_bg_light_color_input.text()
        )
        mw.col.conf["onigiri_prep_station_bg_image_light"] = self._prep_bg_image_light
        mw.col.conf["onigiri_prep_station_bg_image_dark"] = self._prep_bg_image_dark
        mw.col.conf["onigiri_prep_station_bg_blur"] = self.prep_bg_blur_slider.value()
        mw.col.conf["onigiri_prep_station_bg_opacity"] = self.prep_bg_opacity_slider.value()

    # ─── Chart Colors ──────────────────────────────────────────────────────

    def create_prep_station_chart_section(self, parent_layout):
        designer = QFrame()
        designer.setObjectName("mainBackgroundDesigner")
        outer = QVBoxLayout(designer)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel("Chart Colors")
        title_label.setObjectName("sectionTitle")
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.prep_chart_preview_mode = "dark" if theme_manager.night_mode else "light"
        self.prep_chart_preview_mode_widget, self.prep_chart_preview_mode_toggle = self._create_light_dark_mode_toggle(
            self.prep_chart_preview_mode,
            self._on_prep_chart_preview_mode_toggled,
        )
        header_layout.addWidget(self.prep_chart_preview_mode_widget)
        outer.addLayout(header_layout)

        from ..prep_station_ui import ChartPreview, palette as ps_palette
        self.prep_chart_preview = ChartPreview(ps_palette(theme_manager.night_mode))
        outer.addWidget(self.prep_chart_preview)

        left = QWidget()
        left.setMinimumWidth(0)
        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.prep_chart_light_color_button = self._create_main_bg_button("Color")
        self.prep_chart_light_color_value_button = self._create_main_bg_button("")
        self.prep_chart_light_color_value_button.setObjectName("mainBackgroundColorButton")
        self.prep_chart_dark_color_button = self._create_main_bg_button("Dark Color")
        self.prep_chart_dark_color_value_button = self._create_main_bg_button("")
        self.prep_chart_dark_color_value_button.setObjectName("mainBackgroundColorButton")
        self.prep_chart_light_color_card = self._create_color_selector_card(self.prep_chart_light_color_button, self.prep_chart_light_color_value_button)
        self.prep_chart_dark_color_card = self._create_color_selector_card(self.prep_chart_dark_color_button, self.prep_chart_dark_color_value_button)
        left_layout.addWidget(self.prep_chart_light_color_card)
        left_layout.addWidget(self.prep_chart_dark_color_card)

        right = QWidget()
        right.setMinimumWidth(0)
        right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        slider_palette = self._settings_palette()
        slider_track = slider_palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = slider_palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")

        self.prep_chart_blur_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.prep_chart_blur_slider.setRange(0, 100)
        self.prep_chart_blur_slider.setValue(int(mw.col.conf.get("onigiri_prep_station_chart_blur", 30)))
        self.prep_chart_blur_value_label = QLabel(f"{self.prep_chart_blur_slider.value()}%")
        self.prep_chart_blur_value_label.setObjectName("mainBackgroundValueLabel")
        self.prep_chart_blur_value_label.setFixedWidth(48)
        blur_value = QWidget()
        blur_layout = QHBoxLayout(blur_value)
        blur_layout.setContentsMargins(0, 0, 0, 0)
        blur_layout.setSpacing(10)
        blur_layout.addWidget(self.prep_chart_blur_slider, 1)
        blur_layout.addWidget(self.prep_chart_blur_value_label)

        self.prep_chart_opacity_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.prep_chart_opacity_slider.setRange(0, 100)
        self.prep_chart_opacity_slider.setValue(int(mw.col.conf.get("onigiri_prep_station_chart_opacity", 100)))
        self.prep_chart_opacity_value_label = QLabel(f"{self.prep_chart_opacity_slider.value()}%")
        self.prep_chart_opacity_value_label.setObjectName("mainBackgroundValueLabel")
        self.prep_chart_opacity_value_label.setFixedWidth(48)
        opacity_value = QWidget()
        opacity_layout = QHBoxLayout(opacity_value)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(10)
        opacity_layout.addWidget(self.prep_chart_opacity_slider, 1)
        opacity_layout.addWidget(self.prep_chart_opacity_value_label)

        right_layout.addWidget(self._create_main_bg_value_row("Fill Intensity", blur_value))
        right_layout.addWidget(self._create_main_bg_value_row("Opacity", opacity_value))
        right_layout.addStretch()

        controls = ResponsivePairWidget(right, left, spacing=18, breakpoint=620)
        outer.addWidget(controls)

        self.prep_chart_numbers_group = QButtonGroup(self)
        self.prep_chart_numbers_group.setExclusive(True)
        current_numbers = mw.col.conf.get("onigiri_prep_station_chart_numbers", "hide")
        if current_numbers not in {"show", "hover", "hide"}:
            current_numbers = "hide"
        numbers_container = self._create_organize_segmented_control(
            [
                ("show", tr("prep_chart_numbers_show", "Show")),
                ("hover", tr("prep_chart_numbers_hover", "Hover")),
                ("hide", tr("prep_chart_numbers_hide", "Hide")),
            ],
            self.prep_chart_numbers_group,
            current_numbers,
            "chart_numbers",
            fill_width=True,
            segment_height=28,
            min_button_width=54,
        )
        outer.addWidget(self._create_main_bg_value_row(tr("prep_chart_numbers_label", "Chart Numbers"), numbers_container))
        for btn in self.prep_chart_numbers_group.buttons():
            btn.toggled.connect(lambda checked: self._update_prep_chart_numbers() if checked else None)

        self.prep_chart_light_color_input = QLineEdit(mw.col.conf.get("onigiri_prep_station_chart_color_light", "#ffffff"))
        self.prep_chart_dark_color_input = QLineEdit(mw.col.conf.get("onigiri_prep_station_chart_color_dark", "#ffffff"))

        self.prep_chart_light_color_button.clicked.connect(lambda: self._choose_prep_chart_color("light"))
        self.prep_chart_light_color_value_button.clicked.connect(lambda: self._choose_prep_chart_color("light"))
        self.prep_chart_dark_color_button.clicked.connect(lambda: self._choose_prep_chart_color("dark"))
        self.prep_chart_dark_color_value_button.clicked.connect(lambda: self._choose_prep_chart_color("dark"))
        self.prep_chart_blur_slider.valueChanged.connect(lambda v: (self.prep_chart_blur_value_label.setText(f"{v}%"), self._update_prep_chart_preview()))
        self.prep_chart_opacity_slider.valueChanged.connect(lambda v: (self.prep_chart_opacity_value_label.setText(f"{v}%"), self._update_prep_chart_preview()))

        self._update_prep_chart_band()
        self._update_prep_chart_preview()
        self._update_prep_chart_numbers()
        parent_layout.addWidget(designer)

    def _prep_chart_numbers_value(self):
        if not hasattr(self, "prep_chart_numbers_group"):
            return "hide"
        checked = self.prep_chart_numbers_group.checkedButton()
        mode = checked.property("chart_numbers") if checked else "hide"
        return mode if mode in ("show", "hover", "hide") else "hide"

    def _update_prep_chart_numbers(self):
        if not hasattr(self, "prep_chart_preview"):
            return
        self.prep_chart_preview.set_number_mode(self._prep_chart_numbers_value())

    def _on_prep_chart_preview_mode_toggled(self, mode):
        self.prep_chart_preview_mode = "dark" if mode == "dark" else "light"
        self._update_prep_chart_band()
        self._update_prep_chart_preview()

    def _choose_prep_chart_color(self, target):
        line_edit = self.prep_chart_light_color_input if target == "light" else self.prep_chart_dark_color_input
        chosen, ok = OnigiriColorDialog.getColor(line_edit.text(), self, anchor=self.sender() if isinstance(self.sender(), QWidget) else None)
        if ok:
            line_edit.setText(chosen)
            self._update_prep_chart_preview()

    def _update_prep_chart_preview(self):
        if not hasattr(self, "prep_chart_preview"):
            return
        dark = self.prep_chart_preview_mode == "dark"
        color = self.prep_chart_dark_color_input.text() if dark else self.prep_chart_light_color_input.text()
        for line_edit, value_btn in (
            (self.prep_chart_light_color_input, self.prep_chart_light_color_value_button),
            (self.prep_chart_dark_color_input, self.prep_chart_dark_color_value_button),
        ):
            value_btn.setStyleSheet(
                value_btn.styleSheet() + f"\nQPushButton#mainBackgroundColorButton {{ background-color: {line_edit.text()}; }}"
            )
        self.prep_chart_preview.set_colors(
            color, self.prep_chart_blur_slider.value(), self.prep_chart_opacity_slider.value()
        )

    def _save_prep_station_chart_settings(self):
        if not hasattr(self, "prep_chart_light_color_input"):
            return
        mw.col.conf["onigiri_prep_station_chart_color_light"] = self.prep_chart_light_color_input.text()
        mw.col.conf["onigiri_prep_station_chart_color_dark"] = self.prep_chart_dark_color_input.text()
        mw.col.conf["onigiri_prep_station_chart_blur"] = self.prep_chart_blur_slider.value()
        mw.col.conf["onigiri_prep_station_chart_opacity"] = self.prep_chart_opacity_slider.value()
        if hasattr(self, "prep_chart_numbers_group"):
            mw.col.conf["onigiri_prep_station_chart_numbers"] = self._prep_chart_numbers_value()
