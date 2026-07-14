# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *



class PageOverviewsMixin:
    def create_overviews_page(self):
        page, layout = self._create_scrollable_page()
        
        # --- Overviewer Background Section ---
        overview_bg_section = SectionGroup("", self)
        layout.addWidget(overview_bg_section)
        overview_bg_section.content_layout.addWidget(self._create_modern_background_designer({
            "title": tr("overviewer_background_section"),
            "prefix": "overview",
            "gallery_base": "overview_bg",
            "folder_rel": "user_files/main_bg",
            "mode_key": "onigiri_overview_bg_mode",
            "default_mode": "color",
            "allow_main_sync": True,
            "light_color_key": "onigiri_overview_bg_light_color",
            "dark_color_key": "onigiri_overview_bg_dark_color",
            "image_key": "onigiri_overview_bg_image",
            "image_light_key": "onigiri_overview_bg_image_light",
            "image_dark_key": "onigiri_overview_bg_image_dark",
            "color_theme_mode_key": "onigiri_overview_bg_color_theme_mode",
            "image_theme_mode_key": "onigiri_overview_bg_image_theme_mode",
            "legacy_image_mode_key": "onigiri_overview_bg_image_mode",
            "blur_key": "onigiri_overview_bg_blur",
            "opacity_key": "onigiri_overview_bg_opacity",
            "main_sync_blur_key": "onigiri_overview_bg_main_blur",
            "main_sync_opacity_key": "onigiri_overview_bg_main_opacity",
            "slideshow_images_key": "onigiri_overview_slideshow_images",
            "slideshow_interval_key": "onigiri_overview_slideshow_interval",
            "default_light": "#f2f2f2",
            "default_dark": "#2C2C2C",
            "storage": "config",
            "split_orientation": "vertical",
        }))

        overview_section = SectionGroup(
            "",
            self,
            border=False
        )

                # --- NEW: Section for Overview Style ---
        style_section = SectionGroup(
            "",
            self,
            border=True
        )
        
        style_section.content_layout.addWidget(self._create_overview_style_group())
        overview_section.add_widget(style_section)
        # --- END NEW SECTION ---

        layout.addWidget(overview_section)

        layout.addStretch()

        sections = {

            tr("overview_style_section"): style_section,
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections)

        return page

    def _overview_count_color_specs(self):
        # (overview_style key, general theme fallback key, display label)
        return [
            ("new_bubble", "--new-count-bubble-bg", tr("new_count_label", "New Count")),
            ("new_text", "--new-count-bubble-fg", tr("new_count_fg_label", "New Count Text")),
            ("learn_bubble", "--learn-count-bubble-bg", tr("learn_count_label", "Learning Count")),
            ("learn_text", "--learn-count-bubble-fg", tr("learn_count_fg_label", "Learning Count Text")),
            ("review_bubble", "--review-count-bubble-bg", tr("review_count_label", "Review Count")),
            ("review_text", "--review-count-bubble-fg", tr("review_count_fg_label", "Review Count Text")),
        ]

    def _overview_count_color_value(self, key, fallback_key, mode):
        # Mirrors patcher.py's _overview_color(): an explicit Overview Style
        # override wins, otherwise fall back to the general theme color. This is
        # the single source both Overview Style and Deck Settings write into.
        overview_style = self.current_config.get("overview_style", {})
        overview_colors = overview_style.get("colors", {}) if isinstance(overview_style, dict) else {}
        mode_colors = overview_colors.get(mode, {}) if isinstance(overview_colors, dict) else {}
        if isinstance(mode_colors, dict) and mode_colors.get(key):
            return mode_colors[key]
        return self.current_config.get("colors", {}).get(mode, {}).get(fallback_key, DEFAULTS["colors"][mode][fallback_key])

    def _on_overview_count_color_changed(self, mode, key, value):
        if mode not in ("light", "dark") or not QColor(value).isValid():
            return
        colors = self.current_config.setdefault("overview_style", {}).setdefault("colors", {})
        colors.setdefault(mode, {})[key] = value
        # The Overviewer page edits the SAME overview_style colors through its own
        # inputs, and _save_overview_style_settings() rebuilds overview_style
        # ["colors"] wholesale from those inputs. If that page is loaded, our edit
        # here would be clobbered on save, so mirror the value into its input.
        overview_input = getattr(self, "overview_style_color_inputs", {}).get((key, mode))
        if overview_input is not None:
            try:
                if (sip is None or not sip.isdeleted(overview_input)) and overview_input.text() != value:
                    overview_input.setText(value)
            except RuntimeError:
                pass
        self._update_deck_icon_preview()

    def _mirror_overview_style_color_to_deck(self, key, mode, value):
        # Reverse of the mirror in _on_overview_count_color_changed: an edit to an
        # Overviewer count color updates the matching deck designer "Card Counts"
        # pill. The pill's own textChanged then writes overview_style.colors and
        # mirrors back here, but the equality guards on both sides stop any loop.
        if not QColor(value).isValid():
            return
        deck_pill = getattr(self, "deck_overview_count_color_widgets", {}).get((mode, key))
        if deck_pill is None:
            return
        try:
            if (sip is None or not sip.isdeleted(deck_pill)) and deck_pill.text() != value:
                deck_pill.setText(value)
        except RuntimeError:
            pass

    def _create_overview_count_color_pill(self, key, default_value, mode, label_text):
        widget = QFrame()
        widget.setObjectName("newColorPill")
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        widget.setMinimumHeight(48)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        widget.setToolTip(tr("overview_count_color_tooltip", "Shared with the Overviewer's card count colors."))
        
        border_color = "#4a4a4a" if theme_manager.night_mode else "#dcdde1"
        hover_bg = "rgba(255,255,255,0.05)" if theme_manager.night_mode else "rgba(0,0,0,0.03)"
        
        widget.setStyleSheet(f"""
            QFrame#newColorPill {{
                background-color: transparent;
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
            QFrame#newColorPill:hover {{
                background-color: {hover_bg};
            }}
        """)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(15, 8, 12, 8)

        name_label = QLabel(label_text)
        name_label.setStyleSheet("font-weight: bold; border: none; background: transparent;")

        hex_input = QLineEdit(default_value)
        hex_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hex_input.setFixedWidth(110)
        hex_input.setFixedHeight(32)
        hex_input.setCursor(Qt.CursorShape.PointingHandCursor)

        def update_hex_style(hex_str):
            try:
                color = QColor(hex_str)
                if not color.isValid():
                    return
                r, g, b = color.red(), color.green(), color.blue()
                luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                text_color = "#000000" if luminance > 0.5 else "#FFFFFF"
                hex_input.setStyleSheet(f"""
                    QLineEdit {{
                        background-color: {color.name()};
                        color: {text_color};
                        border: none;
                        border-radius: 10px;
                        font-family: monospace;
                        font-weight: bold;
                        font-size: 13px;
                    }}
                    QLineEdit:focus {{
                        border: 2px solid {theme_manager.accent_color if hasattr(theme_manager, 'accent_color') else '#3399ff'};
                    }}
                """)
            except:
                pass

        update_hex_style(default_value)
        hex_input.textChanged.connect(update_hex_style)
        hex_input.textChanged.connect(lambda value, m=mode, k=key: self._on_overview_count_color_changed(m, k, value))
        hex_input.returnPressed.connect(hex_input.clearFocus)
        self.deck_overview_count_color_widgets = getattr(self, "deck_overview_count_color_widgets", {})
        self.deck_overview_count_color_widgets[(mode, key)] = hex_input
        
        widget.mousePressEvent = lambda event, le=hex_input: self.open_color_picker(le, le)

        layout.addWidget(name_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch()
        layout.addWidget(hex_input, 0, Qt.AlignmentFlag.AlignVCenter)

        return widget

    def _populate_overview_count_pills(self, layout, mode):
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider)

        header = QLabel(tr("card_counts_colors_label", "Card Counts (shared with Overviewer)"))
        header.setObjectName("sectionDescription")
        header.setWordWrap(True)
        layout.addWidget(header)

        for key, fallback_key, label_text in self._overview_count_color_specs():
            value = self._overview_count_color_value(key, fallback_key, mode)
            layout.addWidget(self._create_overview_count_color_pill(key, value, mode, label_text))

    def _save_overviews_settings(self):
        # --- NEW: Save the selected overview style ---
        if self.overview_mini_radio.isChecked():
            mw.col.conf["onigiri_overview_style"] = "mini"
        else:
            mw.col.conf["onigiri_overview_style"] = "pro"
        # --- END NEW ---
        self._save_overview_style_settings()
        
        # --- Overviewer Background ---
        if hasattr(self, "overview_bg_color_only_toggle"):
            self._save_modern_background_designer_settings("overview")
            self.current_config["onigiri_overview_bg_main_blur"] = self.current_config.get("onigiri_overview_bg_blur", 0)
            self.current_config["onigiri_overview_bg_main_opacity"] = self.current_config.get("onigiri_overview_bg_opacity", 100)
        else:
            if self.overview_bg_main_radio.isChecked():
                self.current_config["onigiri_overview_bg_mode"] = "main"
            elif self.overview_bg_color_radio.isChecked():
                self.current_config["onigiri_overview_bg_mode"] = "color"
            elif self.overview_bg_image_color_radio.isChecked():
                self.current_config["onigiri_overview_bg_mode"] = "image_color"
            
            # Save theme mode for colors and images
            color_theme_mode = "single" if hasattr(self, 'overview_bg_color_theme_mode_single') and self.overview_bg_color_theme_mode_single.isChecked() else "separate"
            image_theme_mode = "single" if hasattr(self, 'overview_bg_image_theme_mode_single') and self.overview_bg_image_theme_mode_single.isChecked() else "separate"
            
            self.current_config["onigiri_overview_bg_color_theme_mode"] = color_theme_mode
            self.current_config["onigiri_overview_bg_image_theme_mode"] = image_theme_mode
            
            # Main background blur and opacity
            self.current_config["onigiri_overview_bg_main_blur"] = self.overview_bg_main_blur_spinbox.value()
            self.current_config["onigiri_overview_bg_main_opacity"] = self.overview_bg_main_opacity_spinbox.value()
            
            # Save colors based on theme mode
            if color_theme_mode == "single" and hasattr(self, 'overview_bg_single_color_row'):
                # In single mode, use the single color for both themes
                single_color = self.overview_bg_single_color_row.itemAt(1).widget().text()
                self.current_config["onigiri_overview_bg_light_color"] = single_color
                self.current_config["onigiri_overview_bg_dark_color"] = single_color
            else:
                # In separate mode, use the individual colors
                if hasattr(self, 'overview_bg_light_color_row'):
                    self.current_config["onigiri_overview_bg_light_color"] = self.overview_bg_light_color_row.itemAt(1).widget().text()
                if hasattr(self, 'overview_bg_dark_color_row'):
                    self.current_config["onigiri_overview_bg_dark_color"] = self.overview_bg_dark_color_row.itemAt(1).widget().text()
            
            # Save blur and opacity
            self.current_config["onigiri_overview_bg_blur"] = self.overview_bg_blur_spinbox.value()
            self.current_config["onigiri_overview_bg_opacity"] = self.overview_bg_opacity_spinbox.value()
            
            # Save image selections based on theme mode
            if image_theme_mode == "single" and 'overview_bg_single' in self.galleries:
                # In single mode, use the single image for both themes
                single_image = self.galleries['overview_bg_single'].get('selected', '')
                self.current_config["onigiri_overview_bg_image"] = single_image
                self.current_config["onigiri_overview_bg_image_light"] = single_image
                self.current_config["onigiri_overview_bg_image_dark"] = single_image
            else:
                # In separate mode, use the individual images
                if 'overview_bg_light' in self.galleries:
                    self.current_config["onigiri_overview_bg_image_light"] = self.galleries['overview_bg_light'].get('selected', '')
                if 'overview_bg_dark' in self.galleries:
                    self.current_config["onigiri_overview_bg_image_dark"] = self.galleries['overview_bg_dark'].get('selected', '')

        self.current_config["showCongratsProfileBar"] = self.show_congrats_profile_bar_checkbox.isChecked()
        self.current_config["showOverviewProfileBar"] = self.show_overview_profile_bar_checkbox.isChecked()
        self.current_config["congratsMessage"] = self.congrats_message_input.text()
        mw.col.conf["modern_menu_studyNowText"] = self.study_now_input.text()

    def _overview_style_color_specs(self):
        return [
            ("box_bg", "Box Color"),
            ("box_border", "Stroke Color"),
            ("study_button", "Study Button"),
            ("new_bubble", "New Cards Bubble"),
            ("new_text", "New Count Text"),
            ("learn_bubble", "Learning Cards Bubble"),
            ("learn_text", "Learning Count Text"),
            ("review_bubble", "Review Cards Bubble"),
            ("review_text", "Review Count Text"),
        ]

    def _overview_style_saved(self):
        saved = copy.deepcopy(DEFAULTS.get("overview_style", {}))
        current = self.current_config.get("overview_style", {})
        if isinstance(current, dict):
            for key, value in current.items():
                if key == "colors" and isinstance(value, dict):
                    saved.setdefault("colors", {})
                    for mode in ("light", "dark"):
                        if isinstance(value.get(mode), dict):
                            saved["colors"].setdefault(mode, {}).update(value[mode])
                else:
                    saved[key] = value
        # Do NOT re-run normalize_overview_style_defaults here: current_config was
        # already migrated once at load time. Re-normalizing for display would
        # revert a dark count color the user intentionally set to the light value.
        return saved

    def _overview_style_default_color(self, key, mode):
        saved = DEFAULTS.get("overview_style", {}).get("colors", {}).get(mode, {})
        return saved.get(key, "#ffffff" if mode == "light" else "#2c2c2c")

    def _overview_style_color_categories(self):
        return [
            ("surface", "Box Surface", ["box_bg", "box_border"], True),
            ("button", "Study Button", ["study_button"], True),
            (
                "counters",
                "Cards Counters",
                ["new_bubble", "new_text", "learn_bubble", "learn_text", "review_bubble", "review_text"],
                False,
            ),
        ]

    def _style_overview_style_label_pill(self, label, mode=None):
        palette = self._settings_palette()
        if mode == "dark":
            bg = "#303030"
            fg = "#f3f4f6"
            border = "#555555"
        elif mode == "light":
            bg = "#f8fafc"
            fg = "#111827"
            border = "#d1d5db"
        else:
            bg = palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
            fg = palette.get("--fg", "#f9fafb" if theme_manager.night_mode else "#111827")
            border = palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")

        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumHeight(36)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        label.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 0px 14px;
                font-size: 13px;
                font-weight: 500;
            }}
        """)

    def _create_overview_style_mode_panel(self, mode, title, keys):
        palette = self._settings_palette()
        is_dark = mode == "dark"
        panel = QFrame()
        panel.setObjectName("overviewStyleModePanel")
        bg = "#242424" if is_dark else "#ffffff"
        fg = "#f3f4f6" if is_dark else "#111827"
        border = "#555555" if is_dark else palette.get("--border", "#d1d5db")
        panel.setStyleSheet(f"""
            QFrame#overviewStyleModePanel {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 16px;
            }}
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        header = QLabel(title)
        header.setStyleSheet(f"font-weight: 700; font-size: 14px; color: {fg}; background: transparent;")
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        spec_labels = dict(self._overview_style_color_specs())
        style_colors = getattr(self, "_overview_style_builder_colors", {})

        for row, key in enumerate(keys):
            label = QLabel(spec_labels.get(key, key))
            label.setWordWrap(True)
            self._style_overview_style_label_pill(label, mode)
            grid.addWidget(label, row, 0)

            fallback = self._overview_style_default_color(key, mode)
            value = style_colors.get(mode, {}).get(key, fallback) if isinstance(style_colors.get(mode, {}), dict) else fallback
            line_edit = QLineEdit(value)
            button = self._create_main_bg_button("")
            button.setObjectName("mainBackgroundColorButton")
            button.clicked.connect(lambda _=False, k=key, m=mode, b=button: self._choose_overview_style_color(k, m, b))
            self.overview_style_color_inputs[(key, mode)] = line_edit
            # Mirror count-color edits made here into the deck designer's "Card
            # Counts" pill so the two shared views stay identical live. Non-count
            # keys (box_bg, etc.) have no deck pill, so the mirror is a no-op.
            line_edit.textChanged.connect(
                lambda value, k=key, m=mode: self._mirror_overview_style_color_to_deck(k, m, value)
            )
            self.overview_style_color_buttons[(key, mode)] = button
            pill_wrapper = LockableColorPill(button, mode=mode)
            self.overview_style_color_lock_wrappers[(key, mode)] = pill_wrapper
            self.overview_style_color_rows.setdefault(key, []).extend([label, button])
            grid.addWidget(pill_wrapper, row, 1)

        layout.addLayout(grid)
        return panel

    def _create_overview_style_color_category(self, category_id, title, keys, expanded=True):
        wrapper = QFrame()
        wrapper.setObjectName("overviewStyleColorCategory")
        palette = self._settings_palette()
        border = palette.get("--border", "#d1d5db")
        wrapper.setStyleSheet(f"""
            QFrame#overviewStyleColorCategory {{
                background: transparent;
                border: 1px solid {border};
                border-radius: 16px;
            }}
        """)
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(12)

        header = QLabel(title)
        header.setObjectName("sectionTitle")
        layout.addWidget(header)
        if category_id == "surface":
            self.overview_style_surface_header = header

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        dynamic_panel = ResponsivePairWidget(
            self._create_overview_style_mode_panel("light", "Light Mode", keys),
            self._create_overview_style_mode_panel("dark", "Dark Mode", keys),
            spacing=14,
            breakpoint=720,
        )
        content_layout.addWidget(dynamic_panel)
        layout.addWidget(content)
        if category_id == "surface":
            self.overview_style_surface_content = content
            self.overview_style_surface_wrapper = wrapper
            wrapper.setProperty("overview_surface_lock_container", True)
            wrapper.installEventFilter(self)
            content.setProperty("overview_surface_lock_content", True)
            content.installEventFilter(self)
        self.overview_style_color_category_widgets[category_id] = wrapper
        return wrapper

    def _create_overview_style_group(self):
        designer = QFrame()
        designer.setObjectName("mainBackgroundDesigner")
        outer = QVBoxLayout(designer)
        outer.setContentsMargins(0, 8, 0, 8)
        outer.setSpacing(18)

        preview_header = QWidget()
        preview_header_layout = QHBoxLayout(preview_header)
        preview_header_layout.setContentsMargins(0, 0, 0, 0)
        preview_header_layout.setSpacing(10)
        preview_title = QLabel("Overview Style")
        preview_title.setObjectName("sectionTitle")
        preview_header_layout.addWidget(preview_title)
        preview_header_layout.addStretch()
        self.overview_style_preview_mode_group = QButtonGroup(self)
        self.overview_style_preview_mode_group.setExclusive(True)
        preview_mode_bg = "#303030" if theme_manager.night_mode else "#f1f1f1"
        preview_mode_fg = "#f3f4f6" if theme_manager.night_mode else "#111111"
        preview_mode_hover = "#3a3a3a" if theme_manager.night_mode else "#e7e7e7"
        self.overview_style_preview_congrats_button = PillSegmentButton(
            "Congrats", preview_mode_bg, preview_mode_fg, self.accent_color, hover_bg=preview_mode_hover
        )
        self.overview_style_preview_overviewer_button = PillSegmentButton(
            "Overviewer", preview_mode_bg, preview_mode_fg, self.accent_color, hover_bg=preview_mode_hover
        )
        self.overview_style_reset_button = PillSegmentButton(
            "Reset to Default",
            preview_mode_bg,
            preview_mode_fg,
            "#555555" if theme_manager.night_mode else "#d1d5db",
            preview_mode_fg,
            hover_bg=preview_mode_hover,
            checkable=False,
        )
        for button in (self.overview_style_preview_congrats_button, self.overview_style_preview_overviewer_button):
            button.setObjectName("overviewStylePreviewModeButton")
            button.setFixedSize(148, 34)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            font = button.font()
            font.setPointSize(14)
            button.setFont(font)
            self.overview_style_preview_mode_group.addButton(button)
            preview_header_layout.addWidget(button)
        self.overview_style_preview_mode = "dark" if theme_manager.night_mode else "light"
        self.overview_style_preview_mode_widget, self.overview_style_preview_mode_toggle = self._create_light_dark_mode_toggle(
            self.overview_style_preview_mode,
            self._on_overview_style_preview_mode_toggled,
        )
        preview_header_layout.addWidget(self.overview_style_preview_mode_widget)

        self.overview_style_reset_button.setObjectName("overviewStylePreviewResetButton")
        self.overview_style_reset_button.setFixedSize(168, 34)
        self.overview_style_reset_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        reset_font = self.overview_style_reset_button.font()
        reset_font.setPointSize(13)
        self.overview_style_reset_button.setFont(reset_font)
        preview_header_layout.addWidget(self.overview_style_reset_button)
        self.overview_style_preview_overviewer_button.setChecked(True)
        outer.addWidget(preview_header)

        self.overview_style_preview = BackgroundPreviewLabel(aspect_ratio=2.15, minimum_preview_height=470)
        self.overview_style_preview.setObjectName("overviewStylePreview")
        self.overview_style_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overview_style_preview.setProperty("overview_style_preview", True)
        self.overview_style_preview.installEventFilter(self)
        outer.addWidget(self.overview_style_preview)

        saved_style = self._overview_style_saved()

        self.overview_style_sync_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.overview_style_sync_toggle.setChecked(bool(saved_style.get("sync_box_effect", False)))
        self.overview_style_sync_toggle.toggled.connect(self._on_overview_style_changed)

        colors_categories = QWidget()
        colors_categories.setMinimumWidth(0)
        colors_categories.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        colors_categories_layout = QVBoxLayout(colors_categories)
        colors_categories_layout.setContentsMargins(0, 0, 0, 0)
        colors_categories_layout.setSpacing(10)
        self.overview_style_color_inputs = {}
        self.overview_style_color_buttons = {}
        self.overview_style_color_lock_wrappers = {}
        self.overview_style_color_rows = {}
        self.overview_style_color_category_widgets = {}
        self._overview_style_builder_colors = saved_style.get("colors", {})
        for category_id, title, keys, expanded in self._overview_style_color_categories():
            colors_categories_layout.addWidget(self._create_overview_style_color_category(category_id, title, keys, expanded))

        slider_palette = self._settings_palette()
        slider_track = slider_palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = slider_palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")

        saved_blur = mw.col.conf.get("onigiri_overview_effect_blur", int(saved_style.get("blur", 0) or 0))
        self.overview_style_blur_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.overview_style_blur_slider.setRange(0, 100)
        self.overview_style_blur_slider.setValue(max(0, min(100, int(saved_blur))))
        self.overview_style_blur_value_label = QLabel(f"{self.overview_style_blur_slider.value()}%")
        self.overview_style_blur_value_label.setFixedWidth(48)
        blur_value = QWidget()
        blur_layout = QHBoxLayout(blur_value)
        blur_layout.setContentsMargins(0, 0, 0, 0)
        blur_layout.setSpacing(10)
        blur_layout.addWidget(self.overview_style_blur_slider, 1)
        blur_layout.addWidget(self.overview_style_blur_value_label)

        saved_opacity = mw.col.conf.get("onigiri_overview_effect_opacity", int(saved_style.get("opacity", 100) or 100))
        self.overview_style_opacity_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.overview_style_opacity_slider.setRange(0, 100)
        self.overview_style_opacity_slider.setValue(max(0, min(100, int(saved_opacity))))
        self.overview_style_opacity_value_label = QLabel(f"{self.overview_style_opacity_slider.value()}%")
        self.overview_style_opacity_value_label.setFixedWidth(48)
        opacity_value = QWidget()
        opacity_layout = QHBoxLayout(opacity_value)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(10)
        opacity_layout.addWidget(self.overview_style_opacity_slider, 1)
        opacity_layout.addWidget(self.overview_style_opacity_value_label)

        saved_radius = mw.col.conf.get("onigiri_overview_border_radius", int(saved_style.get("radius", 20) or 20))
        self.overview_style_radius_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.overview_style_radius_slider.setRange(0, 60)
        self.overview_style_radius_slider.setValue(max(0, min(60, int(saved_radius))))
        self.overview_style_radius_value_label = QLabel(f"{self.overview_style_radius_slider.value()}px")
        self.overview_style_radius_value_label.setFixedWidth(48)
        radius_value = QWidget()
        radius_layout = QHBoxLayout(radius_value)
        radius_layout.setContentsMargins(0, 0, 0, 0)
        radius_layout.setSpacing(10)
        radius_layout.addWidget(self.overview_style_radius_slider, 1)
        radius_layout.addWidget(self.overview_style_radius_value_label)

        saved_stroke = mw.col.conf.get("onigiri_overview_border_width", int(saved_style.get("stroke", 1) or 1))
        self.overview_style_stroke_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.overview_style_stroke_slider.setRange(0, 10)
        self.overview_style_stroke_slider.setValue(max(0, min(10, int(saved_stroke))))
        self.overview_style_stroke_value_label = QLabel(f"{self.overview_style_stroke_slider.value()}px")
        self.overview_style_stroke_value_label.setFixedWidth(48)
        stroke_value = QWidget()
        stroke_layout = QHBoxLayout(stroke_value)
        stroke_layout.setContentsMargins(0, 0, 0, 0)
        stroke_layout.setSpacing(10)
        stroke_layout.addWidget(self.overview_style_stroke_slider, 1)
        stroke_layout.addWidget(self.overview_style_stroke_value_label)

        self.overview_effects_wrapper = QWidget()
        effects_layout = QVBoxLayout(self.overview_effects_wrapper)
        effects_layout.setContentsMargins(0, 0, 0, 0)
        effects_layout.setSpacing(12)
        effects_layout.addWidget(self._create_main_bg_value_row("Blur", blur_value))
        effects_layout.addWidget(self._create_main_bg_value_row("Opacity", opacity_value))
        effects_layout.addWidget(self._create_main_bg_value_row("Radius", radius_value))
        effects_layout.addWidget(self._create_main_bg_value_row("Stroke", stroke_value))

        # --- Study Now button controls ---------------------------------------
        saved_btn_opacity = int(saved_style.get("study_button_opacity", 100) or 0)
        self.overview_study_button_opacity_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.overview_study_button_opacity_slider.setRange(0, 100)
        self.overview_study_button_opacity_slider.setValue(max(0, min(100, saved_btn_opacity)))
        self.overview_study_button_opacity_value_label = QLabel(f"{self.overview_study_button_opacity_slider.value()}%")
        self.overview_study_button_opacity_value_label.setFixedWidth(48)
        study_button_opacity_value = QWidget()
        study_button_opacity_layout = QHBoxLayout(study_button_opacity_value)
        study_button_opacity_layout.setContentsMargins(0, 0, 0, 0)
        study_button_opacity_layout.setSpacing(10)
        study_button_opacity_layout.addWidget(self.overview_study_button_opacity_slider, 1)
        study_button_opacity_layout.addWidget(self.overview_study_button_opacity_value_label)

        saved_btn_radius = int(saved_style.get("study_button_radius", 100))
        if saved_btn_radius > 100:
            saved_btn_radius = 100
        self.overview_study_button_radius_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.overview_study_button_radius_slider.setRange(0, 100)
        self.overview_study_button_radius_slider.setValue(max(0, min(100, saved_btn_radius)))
        self.overview_study_button_radius_value_label = QLabel(f"{self.overview_study_button_radius_slider.value()}%")
        self.overview_study_button_radius_value_label.setFixedWidth(48)
        study_button_radius_value = QWidget()
        study_button_radius_layout = QHBoxLayout(study_button_radius_value)
        study_button_radius_layout.setContentsMargins(0, 0, 0, 0)
        study_button_radius_layout.setSpacing(10)
        study_button_radius_layout.addWidget(self.overview_study_button_radius_slider, 1)
        study_button_radius_layout.addWidget(self.overview_study_button_radius_value_label)

        saved_btn_stroke = int(saved_style.get("study_button_stroke", 0) or 0)
        self.overview_study_button_stroke_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.overview_study_button_stroke_slider.setRange(0, 10)
        self.overview_study_button_stroke_slider.setValue(max(0, min(10, saved_btn_stroke)))
        self.overview_study_button_stroke_value_label = QLabel(f"{self.overview_study_button_stroke_slider.value()}px")
        self.overview_study_button_stroke_value_label.setFixedWidth(48)
        study_button_stroke_value = QWidget()
        study_button_stroke_layout = QHBoxLayout(study_button_stroke_value)
        study_button_stroke_layout.setContentsMargins(0, 0, 0, 0)
        study_button_stroke_layout.setSpacing(10)
        study_button_stroke_layout.addWidget(self.overview_study_button_stroke_slider, 1)
        study_button_stroke_layout.addWidget(self.overview_study_button_stroke_value_label)

        self.overview_study_button_dashed_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.overview_study_button_dashed_toggle.setChecked(bool(saved_style.get("study_button_dashed", False)))
        self.overview_study_button_animated_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.overview_study_button_animated_toggle.setChecked(bool(saved_style.get("study_button_animated", True)))

        study_button_header = QLabel("Study Now Button")
        study_button_header.setObjectName("sectionSubTitle")
        study_button_header.setStyleSheet("font-weight: 600; opacity: 0.85; margin-top: 4px;")

        self.overview_study_button_wrapper = QWidget()
        study_button_controls_layout = QVBoxLayout(self.overview_study_button_wrapper)
        study_button_controls_layout.setContentsMargins(0, 0, 0, 0)
        study_button_controls_layout.setSpacing(12)
        study_button_controls_layout.addWidget(study_button_header)
        study_button_controls_layout.addWidget(self._create_main_bg_value_row("Button Opacity", study_button_opacity_value))
        study_button_controls_layout.addWidget(self._create_main_bg_value_row("Button Radius", study_button_radius_value))
        study_button_controls_layout.addWidget(self._create_main_bg_value_row("Button Stroke", study_button_stroke_value))
        study_button_controls_layout.addWidget(self._create_main_bg_toggle_row("Dashed stroke", self.overview_study_button_dashed_toggle))
        study_button_controls_layout.addWidget(self._create_main_bg_toggle_row("Animated (hover effect)", self.overview_study_button_animated_toggle))

        slider_controls = QWidget()
        slider_controls.setMinimumWidth(0)
        slider_controls.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        slider_controls_layout = QVBoxLayout(slider_controls)
        slider_controls_layout.setContentsMargins(0, 0, 0, 0)
        slider_controls_layout.setSpacing(12)
        slider_controls_layout.addWidget(self.overview_effects_wrapper)
        slider_controls_layout.addWidget(self._create_main_bg_toggle_row("Sync with Box Color and Effect", self.overview_style_sync_toggle))
        slider_controls_layout.addWidget(self.overview_study_button_wrapper)

        option_controls = QWidget()
        option_controls.setMinimumWidth(0)
        option_controls.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        option_controls_layout = QVBoxLayout(option_controls)
        option_controls_layout.setContentsMargins(0, 0, 0, 0)
        option_controls_layout.setSpacing(14)

        self.study_now_input.setMinimumHeight(42)
        option_controls_layout.addWidget(self._create_main_bg_value_row("Custom Stats Title (Study Now)", self.study_now_input))
        self.congrats_message_input.setMinimumHeight(42)
        option_controls_layout.addWidget(self._create_main_bg_value_row("Congrats Message", self.congrats_message_input))

        style_container = QWidget()
        style_container.setMinimumWidth(0)
        style_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        style_layout = QHBoxLayout(style_container)
        style_layout.setContentsMargins(0, 0, 0, 0)
        style_layout.setSpacing(10)

        self.overview_style_mode_group = QButtonGroup(self)
        self.overview_style_mode_group.setExclusive(True)
        mode_button_bg = "#303030" if theme_manager.night_mode else "#f1f1f1"
        mode_button_fg = "#f3f4f6" if theme_manager.night_mode else "#111111"
        mode_button_checked_fg = "#ffffff"
        mode_button_hover = "#3a3a3a" if theme_manager.night_mode else "#e7e7e7"
        self.overview_pro_radio = PillSegmentButton(
            "Pro", mode_button_bg, mode_button_fg, self.accent_color, mode_button_checked_fg, mode_button_hover
        )
        self.overview_mini_radio = PillSegmentButton(
            "Mini", mode_button_bg, mode_button_fg, self.accent_color, mode_button_checked_fg, mode_button_hover
        )
        for button in (self.overview_pro_radio, self.overview_mini_radio):
            button.setObjectName("overviewStyleModeButton")
            button.setFixedHeight(34)
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            font = button.font()
            font.setPointSize(15)
            button.setFont(font)
            self.overview_style_mode_group.addButton(button)
        current_style = mw.col.conf.get("onigiri_overview_style", "pro")
        if current_style == "mini":
            self.overview_mini_radio.setChecked(True)
        else:
            self.overview_pro_radio.setChecked(True)
        style_layout.addWidget(self.overview_pro_radio, 1)
        style_layout.addWidget(self.overview_mini_radio, 1)
        option_controls_layout.addWidget(self._create_main_bg_value_row("Design", style_container))
        option_controls_layout.addWidget(self._create_main_bg_toggle_row("Show Profile bar in Overviewer", self.show_overview_profile_bar_checkbox))
        option_controls_layout.addWidget(self._create_main_bg_toggle_row("Show Profile bar in Congrats screen", self.show_congrats_profile_bar_checkbox))

        preview_controls_pair = QWidget()
        preview_controls_pair.setMinimumWidth(0)
        preview_controls_pair.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        preview_controls_pair_layout = QGridLayout(preview_controls_pair)
        preview_controls_pair_layout.setContentsMargins(0, 0, 0, 0)
        preview_controls_pair_layout.setHorizontalSpacing(24)
        preview_controls_pair_layout.setVerticalSpacing(0)
        preview_controls_pair_layout.setColumnStretch(0, 1)
        preview_controls_pair_layout.setColumnStretch(1, 1)
        preview_controls_pair_layout.addWidget(option_controls, 0, 0)
        preview_controls_pair_layout.addWidget(slider_controls, 0, 1)
        outer.addWidget(preview_controls_pair)
        outer.addWidget(colors_categories)

        self.overview_style_blur_slider.valueChanged.connect(self._on_overview_style_changed)
        self.overview_style_opacity_slider.valueChanged.connect(self._on_overview_style_changed)
        self.overview_style_radius_slider.valueChanged.connect(self._on_overview_style_changed)
        self.overview_style_stroke_slider.valueChanged.connect(self._on_overview_style_changed)
        self.overview_study_button_opacity_slider.valueChanged.connect(self._on_overview_style_changed)
        self.overview_study_button_radius_slider.valueChanged.connect(self._on_overview_style_changed)
        self.overview_study_button_stroke_slider.valueChanged.connect(self._on_overview_style_changed)
        self.overview_study_button_dashed_toggle.toggled.connect(self._on_overview_style_changed)
        self.overview_study_button_animated_toggle.toggled.connect(self._on_overview_style_changed)
        
        self.overview_pro_radio.toggled.connect(lambda checked: self._on_overview_style_changed() if checked else None)
        self.overview_mini_radio.toggled.connect(lambda checked: self._on_overview_style_changed() if checked else None)
        self.overview_style_preview_congrats_button.toggled.connect(lambda checked: self._update_overview_style_preview() if checked else None)
        self.overview_style_preview_overviewer_button.toggled.connect(lambda checked: self._update_overview_style_preview() if checked else None)
        self.overview_style_reset_button.clicked.connect(self._reset_overview_style_to_default)
        self.show_overview_profile_bar_checkbox.toggled.connect(lambda checked: self._update_overview_style_preview())
        self.show_congrats_profile_bar_checkbox.toggled.connect(lambda checked: self._update_overview_style_preview())

        for line_edit in self.overview_style_color_inputs.values():
            line_edit.textChanged.connect(lambda _=None: self._on_overview_style_changed())
        for signal_name in ("textChanged", "textEdited"):
            getattr(self.study_now_input, signal_name).connect(lambda _=None: self._on_overview_style_text_changed())
            getattr(self.congrats_message_input, signal_name).connect(lambda _=None: self._on_overview_style_text_changed())
        self.study_now_input.editingFinished.connect(self._on_overview_style_text_changed)
        self.congrats_message_input.editingFinished.connect(self._on_overview_style_text_changed)

        self._update_overview_style_controls()
        return designer

    def _choose_overview_style_color(self, key, mode="light", anchor=None):
        line_edit = self.overview_style_color_inputs.get((key, mode))
        if line_edit is None:
            return
        chosen, ok = OnigiriColorDialog.getColor(line_edit.text(), self, anchor=anchor)
        if ok:
            line_edit.setText(chosen)
            self._update_overview_style_controls()

    def _on_overview_style_changed(self, *args):
        self._update_overview_style_controls()

    def _on_overview_style_text_changed(self, *args):
        if hasattr(self, "congrats_message_input"):
            self.current_config["congratsMessage"] = self.congrats_message_input.text()
        if hasattr(self, "study_now_input"):
            mw.col.conf["modern_menu_studyNowText"] = self.study_now_input.text()
        QTimer.singleShot(0, self._update_overview_style_preview)

    def _overview_style_preview_mode(self):
        if (
            hasattr(self, "overview_style_sync_toggle")
            and self.overview_style_sync_toggle.isChecked()
            and hasattr(self, "box_effect_preview_mode_toggle")
        ):
            return self._box_effect_preview_mode()
        return getattr(self, "overview_style_preview_mode", "dark" if theme_manager.night_mode else "light")

    def _on_overview_style_preview_mode_toggled(self, mode):
        self.overview_style_preview_mode = "dark" if mode == "dark" else "light"
        self._update_overview_style_preview()

    def _update_overview_style_controls(self):
        if not hasattr(self, "overview_style_preview"):
            return
        
        synced = self.overview_style_sync_toggle.isChecked()
        if hasattr(self, "overview_style_preview_mode_toggle"):
            self.overview_style_preview_mode_toggle.setEnabled(not synced)
            self.overview_style_preview_mode_toggle.setToolTip(
                "Following Box Color and Effect's light/dark preview while synced." if synced else ""
            )
        self.overview_effects_wrapper.setEnabled(not synced)
        lock_hint = "Disable Sync with Box Color and Effect to edit this control."
        self.overview_effects_wrapper.setToolTip(lock_hint if synced else "")
        if hasattr(self, "overview_style_surface_header"):
            self.overview_style_surface_header.setToolTip(
                "Box Surface colors are read-only while Sync with Box Color and Effect is active."
                if synced else ""
            )
        self._update_overview_style_surface_lock_overlay(synced)
        for key in ("box_bg", "box_border"):
            for mode in ("light", "dark"):
                button = self.overview_style_color_buttons.get((key, mode))
                line_edit = self.overview_style_color_inputs.get((key, mode))
                if button:
                    button.setEnabled(not synced)
                    button.setToolTip(
                        "Disable Sync with Box Color and Effect to edit this color."
                        if synced else ""
                    )
                if line_edit:
                    line_edit.setEnabled(not synced)

        QTimer.singleShot(0, lambda: self._update_overview_style_surface_lock_overlay(synced))
        for key, _label in self._overview_style_color_specs():
            for mode in ("light", "dark"):
                button = self.overview_style_color_buttons.get((key, mode))
                line_edit = self.overview_style_color_inputs.get((key, mode))
                if not button or not line_edit:
                    continue
                if synced and key == "box_bg":
                    color = self._overview_synced_box_color(mode)
                elif synced and key == "box_border":
                    color = self._box_effect_border_color(mode)
                else:
                    color = self._box_effect_color_for_input(line_edit, self._overview_style_default_color(key, mode))
                self._style_main_background_color_button(button, color)

        self.overview_style_blur_value_label.setText(f"{self.overview_style_blur_slider.value()}%")
        self.overview_style_opacity_value_label.setText(f"{self.overview_style_opacity_slider.value()}%")
        self.overview_style_radius_value_label.setText(f"{self.overview_style_radius_slider.value()}px")
        self.overview_style_stroke_value_label.setText(f"{self.overview_style_stroke_slider.value()}px")
        if hasattr(self, "overview_study_button_opacity_value_label"):
            self.overview_study_button_opacity_value_label.setText(f"{self.overview_study_button_opacity_slider.value()}%")
            self.overview_study_button_radius_value_label.setText(f"{self.overview_study_button_radius_slider.value()}%")
            self.overview_study_button_stroke_value_label.setText(f"{self.overview_study_button_stroke_slider.value()}px")

        self._update_overview_style_preview()

    def _update_overview_style_surface_lock_overlay(self, synced=None):
        if not hasattr(self, "overview_style_color_lock_wrappers"):
            return
        if synced is None:
            synced = self.overview_style_sync_toggle.isChecked()
        for key in ("box_bg", "box_border"):
            for mode in ("light", "dark"):
                wrapper = self.overview_style_color_lock_wrappers.get((key, mode))
                if wrapper:
                    wrapper.setLocked(bool(synced))

    def _overview_style_effect_values(self):
        if self.overview_style_sync_toggle.isChecked():
            if hasattr(self, "box_effect_blur_slider"):
                return {
                    "blur": self.box_effect_blur_slider.value(),
                    "opacity": self.box_effect_opacity_slider.value(),
                    "radius": self.box_effect_radius_slider.value(),
                    "stroke": self.box_effect_stroke_slider.value(),
                }
            return {
                "blur": int(mw.col.conf.get("onigiri_canvas_inset_effect_blur", 0) or 0),
                "opacity": int(mw.col.conf.get("onigiri_canvas_inset_effect_opacity", 100) or 100),
                "radius": int(mw.col.conf.get("onigiri_canvas_inset_border_radius", 20) or 20),
                "stroke": int(mw.col.conf.get("onigiri_canvas_inset_border_width", 1) or 1),
            }
        return {
            "blur": self.overview_style_blur_slider.value(),
            "opacity": self.overview_style_opacity_slider.value(),
            "radius": self.overview_style_radius_slider.value(),
            "stroke": self.overview_style_stroke_slider.value(),
        }

    def _overview_synced_box_color(self, mode):
        if hasattr(self, "box_effect_dynamic_toggle"):
            return self._box_effect_color(mode)
        mode = "dark" if mode == "dark" else "light"
        return self.current_config.get("colors", {}).get(mode, {}).get(
            "--canvas-inset",
            DEFAULTS["colors"][mode]["--canvas-inset"],
        )

    def _overview_style_color(self, key, mode):
        mode = "dark" if mode == "dark" else "light"
        if self.overview_style_sync_toggle.isChecked() and key == "box_bg":
            return self._overview_synced_box_color(mode)
        if self.overview_style_sync_toggle.isChecked() and key == "box_border":
            return self._box_effect_border_color(mode)
        line_edit = self.overview_style_color_inputs.get((key, mode))
        return self._box_effect_color_for_input(line_edit, self._overview_style_default_color(key, mode))

    def _overview_background_state_for_style_preview(self, mode):
        mode = "dark" if mode == "dark" else "light"
        spec = self._modern_background_spec("overview") if hasattr(self, "_modern_background_specs") else None
        if spec and hasattr(self, "overview_bg_color_only_toggle"):
            sync_main_toggle = getattr(self, "overview_bg_sync_main_toggle", None)
            if sync_main_toggle and sync_main_toggle.isChecked():
                state = self._main_background_state_for_box_preview(mode)
                state["blur"] = int(self.overview_bg_blur_slider.value() if hasattr(self, "overview_bg_blur_slider") else state.get("blur", 0))
                state["opacity"] = int(self.overview_bg_opacity_slider.value() if hasattr(self, "overview_bg_opacity_slider") else state.get("opacity", 100))
                return state
            dynamic = self.overview_bg_dynamic_toggle.isChecked()
            color_only = self.overview_bg_color_only_toggle.isChecked()
            slideshow = self.overview_bg_slideshow_toggle.isChecked()
            if dynamic:
                color_input = self.overview_bg_dark_color_input if mode == "dark" else self.overview_bg_light_color_input
            else:
                color_input = self.overview_bg_single_color_input
            color = self._modern_background_color_for_input(
                color_input,
                spec.get("default_dark", "#2c2c2c") if mode == "dark" else spec.get("default_light", "#f2f2f2"),
            )

            image_name = ""
            if not color_only:
                if slideshow:
                    images = self._sanitize_modern_bg_slideshow_images(spec, getattr(self, "overview_bg_slideshow_images", []))
                    if images:
                        index = getattr(self, "overview_bg_slideshow_index", 0) % len(images)
                        image_name = images[index]
                elif dynamic:
                    key = "overview_bg_dark" if mode == "dark" else "overview_bg_light"
                    image_name = self.galleries.get(key, {}).get("selected", "")
                else:
                    image_name = self.galleries.get("overview_bg_single", {}).get("selected", "")

            image_path = self._modern_bg_image_path(spec, image_name) if image_name else ""
            return {
                "color": color,
                "image_path": image_path if image_path and os.path.exists(image_path) else "",
                "blur": int(self.overview_bg_blur_slider.value() if hasattr(self, "overview_bg_blur_slider") else 0),
                "opacity": int(self.overview_bg_opacity_slider.value() if hasattr(self, "overview_bg_opacity_slider") else 100),
            }

        bg_mode = self.current_config.get("onigiri_overview_bg_mode", "main")
        if bg_mode == "main":
            return self._main_background_state_for_box_preview(mode)

        light_color = self.current_config.get("onigiri_overview_bg_light_color", "#f2f2f2")
        dark_color = self.current_config.get("onigiri_overview_bg_dark_color", "#2c2c2c")
        color_theme_mode = self.current_config.get("onigiri_overview_bg_color_theme_mode", "separate")
        color = dark_color if color_theme_mode == "separate" and mode == "dark" else light_color

        image_name = ""
        if bg_mode == "image_color":
            image_theme_mode = self.current_config.get("onigiri_overview_bg_image_theme_mode", self.current_config.get("onigiri_overview_bg_image_mode", "separate"))
            if image_theme_mode == "separate":
                image_name = self.current_config.get("onigiri_overview_bg_image_dark" if mode == "dark" else "onigiri_overview_bg_image_light", "")
            else:
                image_name = self.current_config.get("onigiri_overview_bg_image", "")
        elif bg_mode == "slideshow":
            images = self.current_config.get("onigiri_overview_slideshow_images", []) or []
            image_name = images[0] if images else ""

        image_path = self._main_bg_image_path(image_name) if image_name else ""
        return {
            "color": color,
            "image_path": image_path if image_path and os.path.exists(image_path) else "",
            "blur": int(self.current_config.get("onigiri_overview_bg_blur", 0) or 0),
            "opacity": int(self.current_config.get("onigiri_overview_bg_opacity", 100) or 100),
        }

    def _render_overview_style_background_pixmap(self, mode, width, height):
        state = self._overview_background_state_for_style_preview(mode)
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(state.get("color", "#f2f2f2")))
        image_path = state.get("image_path", "")
        if image_path:
            image = self._background_cover_image_with_effect(
                image_path,
                width,
                height,
                int(state.get("blur", 0) or 0),
            )
            if not image.isNull():
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.setOpacity(max(0.0, min(1.0, float(state.get("opacity", 100)) / 100.0)))
                painter.drawPixmap(0, 0, image)
                painter.end()
        return pixmap

    def _draw_overview_style_sample(self, painter, rect, mode, background_pixmap, draw_profile=True):
        effects = self._overview_style_effect_values()
        box_color = QColor(self._overview_style_color("box_bg", mode))
        blur_radius = (effects["blur"] / 100.0) * 20.0
        box_alpha = max(0.0, min(1.0, effects["opacity"] / 100.0))
        if blur_radius > 0:
            box_alpha = min(box_alpha, 0.82)
        box_color.setAlphaF(box_alpha)
        radius = float(effects["radius"])
        stroke_width = max(0, int(effects["stroke"]))
        
        is_mini = self.overview_mini_radio.isChecked()

        painter.save()
        show_profile = hasattr(self, "show_overview_profile_bar_checkbox") and self.show_overview_profile_bar_checkbox.isChecked()
        main_font_size = int(mw.col.conf.get("onigiri_font_size_main", 14) or 14)
        title_pixel_size = 20 if is_mini else max(18, main_font_size * 2)
        title_size = max(12, int(title_pixel_size * 0.75))
        title_font = self._box_effect_preview_font("subtle", title_size)
        title_font.setPixelSize(title_pixel_size)
        title_font.setBold(True)
        title_height = 30 if is_mini else max(32, title_pixel_size + 8)
        title_gap = 4 if is_mini else 6
        button_gap = 8 if is_mini else 12
        button_height = 30 if is_mini else 38
        profile_overlap = (32 * 0.50 if is_mini else 38 * 0.56) if show_profile else 0
        visible_profile_height = (32 - profile_overlap if is_mini else 38 - profile_overlap) if show_profile else 0

        path = QPainterPath()
        if is_mini:
            box_width = min(int(rect.width() * 0.48), 300)
            box_height = min(int(rect.height() * 0.26), 120)
        else:
            box_width = min(int(rect.width() * 0.62), 360)
            box_height = min(int(rect.height() * 0.40), 185)
            
        box_x = rect.x() + (rect.width() - box_width) // 2
        total_height = title_height + title_gap + visible_profile_height + box_height + button_gap + button_height
        if is_mini:
            group_top = rect.y() + max(40, rect.height() * 0.12)
        else:
            group_top = rect.y() + max(10, (rect.height() - total_height) / 2)
        box_y = group_top + title_height + title_gap + visible_profile_height
        max_box_bottom = rect.bottom() - button_gap - button_height - 10
        if box_y + box_height > max_box_bottom:
            box_height = max(120 if is_mini else 170, int(max_box_bottom - box_y))
            total_height = title_height + title_gap + visible_profile_height + box_height + button_gap + button_height
            if is_mini:
                group_top = rect.y() + max(40, rect.height() * 0.12)
            else:
                group_top = rect.y() + max(10, (rect.height() - total_height) / 2)
            box_y = group_top + title_height + title_gap + visible_profile_height
        box_rect = QRectF(box_x, box_y, box_width, box_height)
        bar_rect = self._overview_style_overviewer_profile_bar_rect(rect, box_rect, is_mini)
        self._overview_style_last_viewer_profile_rect = QRectF(bar_rect)
        
        path.addRoundedRect(box_rect, radius, radius)
        
        if blur_radius > 0 and background_pixmap and not background_pixmap.isNull():
            blurred = self._qt_blurred_pixmap(background_pixmap, blur_radius)
            if not blurred.isNull():
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, blurred)
                painter.setClipping(False)
                
        painter.fillPath(path, QBrush(box_color))
        
        if stroke_width > 0:
            border_pen = QPen(QColor(self._overview_style_color("box_border", mode)))
            border_pen.setWidth(stroke_width)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        if show_profile and draw_profile:
            self._draw_overview_style_profile_bar(painter, rect, mode, bar_rect)

        painter.setPen(QColor(self._box_effect_title_color(mode)))
        painter.setFont(title_font)
        title_y = group_top
        painter.drawText(QRectF(rect.x(), title_y, rect.width(), title_height), Qt.AlignmentFlag.AlignCenter, "Title")
        
        painter.setPen(QColor(self._box_effect_text_color(mode)))
        body_font = self._box_effect_preview_font("main", 19 if not is_mini else 15)
        painter.setFont(body_font)

        if is_mini:
            stats_y = box_rect.y() + 27
            row_height = 30
            row_positions = [stats_y, stats_y + row_height, stats_y + row_height * 2]
        else:
            row_gap = max(48, min(62, box_rect.height() * 0.24))
            center_row = box_rect.y() + box_rect.height() * 0.5
            row_positions = [
                center_row - row_gap,
                center_row,
                center_row + row_gap,
            ]

        separator_color = QColor(self._overview_style_color("box_border", mode))
        separator_color.setAlphaF(0.75)
        separator_pen = QPen(separator_color)
        separator_pen.setWidth(1)
        painter.setPen(separator_pen)
        line_left = box_rect.x() + 24
        line_right = box_rect.right() - 24
        bubble_center_offset = 9 if is_mini else 11
        for index in range(2):
            line_y = ((row_positions[index] + row_positions[index + 1]) * 0.5) + bubble_center_offset
            painter.drawLine(QPointF(line_left, line_y), QPointF(line_right, line_y))
        
        def draw_bubble(y, text_label, count, bg_key, fg_key):
            bg_color = QColor(self._overview_style_color(bg_key, mode))
            fg_color = QColor(self._overview_style_color(fg_key, mode))
            
            bubble_rect = QRectF(
                box_rect.x() + box_rect.width() - (100 if not is_mini else 84),
                y - (4 if not is_mini else 3),
                78 if not is_mini else 64,
                30 if not is_mini else 24,
            )
            label_rect = QRectF(
                box_rect.x() + 24,
                bubble_rect.y(),
                bubble_rect.x() - box_rect.x() - 44,
                bubble_rect.height(),
            )
            painter.setPen(QColor(self._box_effect_text_color(mode)))
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text_label)

            bubble_path = QPainterPath()
            bubble_path.addRoundedRect(bubble_rect, bubble_rect.height() / 2, bubble_rect.height() / 2)
            painter.fillPath(bubble_path, QBrush(bg_color))
            
            painter.setPen(fg_color)
            painter.drawText(bubble_rect, Qt.AlignmentFlag.AlignCenter, count)

        draw_bubble(row_positions[0], "New", "123", "new_bubble", "new_text")
        draw_bubble(row_positions[1], "Learning", "321", "learn_bubble", "learn_text")
        draw_bubble(row_positions[2], "To Review", "321", "review_bubble", "review_text")
        
        button_y = box_rect.bottom() + button_gap
        button_width = box_rect.width() - 40 if is_mini else box_rect.width()
        button_x = box_rect.x() + 20 if is_mini else box_rect.x()
        
        button_rect = QRectF(button_x, button_y, button_width, button_height)
        button_path = QPainterPath()
        btn_radius = button_height / 2.0
        if hasattr(self, "overview_study_button_radius_slider"):
            pct = self.overview_study_button_radius_slider.value()
            if pct < 100:
                btn_radius = (pct / 100.0) * (button_height / 2.0)
        button_path.addRoundedRect(button_rect, btn_radius, btn_radius)
        study_button_color = QColor(self._overview_style_color("study_button", mode))
        if hasattr(self, "overview_study_button_opacity_slider"):
            study_button_color.setAlphaF(max(0.0, min(1.0, self.overview_study_button_opacity_slider.value() / 100.0)))
        painter.fillPath(button_path, QBrush(study_button_color))

        if hasattr(self, "overview_study_button_stroke_slider"):
            btn_stroke_width = int(self.overview_study_button_stroke_slider.value())
            if btn_stroke_width > 0:
                btn_pen = QPen(QColor(self._overview_style_color("box_border", mode)))
                btn_pen.setWidth(btn_stroke_width)
                if self.overview_study_button_dashed_toggle.isChecked():
                    btn_pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(btn_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(button_path)
        
        painter.setPen(QColor(self._box_effect_text_color(mode)))
        button_font = self._box_effect_preview_font("main", 16 if not is_mini else 13)
        painter.setFont(button_font)
        study_text = self.study_now_input.text().strip() if hasattr(self, "study_now_input") else ""
        if not study_text:
            study_text = "Ready to study!"
        metrics = painter.fontMetrics()
        painter.drawText(
            button_rect,
            Qt.AlignmentFlag.AlignCenter,
            metrics.elidedText(study_text, Qt.TextElideMode.ElideRight, int(button_rect.width() - 20)),
        )
        
        painter.restore()

    def _render_overview_style_preview_pixmap(self):
        size = self.overview_style_preview.size()
        width = max(1, size.width())
        height = max(1, size.height())
        dpr = max(1.0, self.overview_style_preview.devicePixelRatioF())
        pixmap = QPixmap(int(width * dpr), int(height * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        preview_rect = QRectF(1, 1, width - 2, height - 2)
        preview_path = QPainterPath()
        preview_path.addRoundedRect(preview_rect, 22, 22)
        painter.setClipPath(preview_path)

        try:
            mode = self._overview_style_preview_mode()
            state = self._overview_background_state_for_style_preview(mode)
            background_pixmap = QPixmap(int(width * dpr), int(height * dpr))
            background_pixmap.setDevicePixelRatio(dpr)
            background_pixmap.fill(Qt.GlobalColor.transparent)
            bg_painter = QPainter(background_pixmap)
            bg_painter.fillRect(QRect(0, 0, width, height), QColor(state["color"]))
            if state.get("image_path") and os.path.exists(state["image_path"]):
                img = self._background_cover_image_with_effect(state["image_path"], width, height, state.get("blur", 0))
                if not img.isNull():
                    bg_painter.setOpacity(max(0.0, min(1.0, float(state.get("opacity", 100)) / 100.0)))
                    bg_painter.drawPixmap(0, 0, img)
            bg_painter.end()

            congrats_preview = (
                hasattr(self, "overview_style_preview_congrats_button")
                and self.overview_style_preview_congrats_button.isChecked()
            )

            painter.drawPixmap(0, 0, background_pixmap)
            if congrats_preview:
                self._draw_overview_style_congrats_sample(painter, QRectF(0, 0, width, height), mode, background_pixmap)
            else:
                self._draw_overview_style_sample(painter, QRectF(0, 0, width, height), mode, background_pixmap)

        except Exception as exc:
            pass

        painter.end()

        masked = QPixmap(int(width * dpr), int(height * dpr))
        masked.setDevicePixelRatio(dpr)
        masked.fill(Qt.GlobalColor.transparent)
        painter = QPainter(masked)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setClipPath(preview_path)
        painter.drawPixmap(0, 0, pixmap)
        painter.setClipping(False)
        border_color = QColor("#4b5563" if theme_manager.night_mode else "#d1d5db")
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(preview_path)
        painter.end()
        return masked

    def _update_overview_style_preview(self):
        if not hasattr(self, "overview_style_preview"):
            return
        self.overview_style_preview.setStyleSheet("QLabel#overviewStylePreview { background: transparent; border: none; }")
        self.overview_style_preview.setPixmap(self._render_overview_style_preview_pixmap())
        self.overview_style_preview.setText("")

    def _reset_overview_style_to_default(self):
        defaults = copy.deepcopy(DEFAULTS.get("overview_style", {}))
        config.normalize_overview_style_defaults({"overview_style": defaults})
        blockers = []
        widgets = [
            self.overview_style_sync_toggle,
            self.overview_style_blur_slider,
            self.overview_style_opacity_slider,
            self.overview_style_radius_slider,
            self.overview_style_stroke_slider,
            self.overview_study_button_opacity_slider,
            self.overview_study_button_radius_slider,
            self.overview_study_button_stroke_slider,
            self.overview_study_button_dashed_toggle,
            self.overview_study_button_animated_toggle,
            self.overview_pro_radio,
            self.overview_mini_radio,
            self.show_overview_profile_bar_checkbox,
            self.show_congrats_profile_bar_checkbox,
            self.study_now_input,
            self.congrats_message_input,
            self.overview_style_preview_congrats_button,
            self.overview_style_preview_overviewer_button,
        ]
        widgets.extend(self.overview_style_color_inputs.values())
        for widget in widgets:
            if widget is not None:
                blockers.append(QSignalBlocker(widget))

        self.overview_style_sync_toggle.setChecked(bool(defaults.get("sync_box_effect", False)))
        self.overview_style_blur_slider.setValue(int(defaults.get("blur", 0) or 0))
        self.overview_style_opacity_slider.setValue(int(defaults.get("opacity", 100) or 100))
        self.overview_style_radius_slider.setValue(int(defaults.get("radius", 20) or 20))
        self.overview_style_stroke_slider.setValue(int(defaults.get("stroke", 1) or 1))
        self.overview_study_button_opacity_slider.setValue(int(defaults.get("study_button_opacity", 100) or 0))
        self.overview_study_button_radius_slider.setValue(int(defaults.get("study_button_radius", 100)))
        self.overview_study_button_stroke_slider.setValue(int(defaults.get("study_button_stroke", 0) or 0))
        self.overview_study_button_dashed_toggle.setChecked(bool(defaults.get("study_button_dashed", False)))
        self.overview_study_button_animated_toggle.setChecked(bool(defaults.get("study_button_animated", True)))
        self.overview_pro_radio.setChecked(True)
        self.show_overview_profile_bar_checkbox.setChecked(True)
        self.show_congrats_profile_bar_checkbox.setChecked(True)
        self.study_now_input.setText(DEFAULTS.get("studyNowText", "Study Now"))
        self.congrats_message_input.setText(DEFAULTS.get("congratsMessage", "Congratulations! You have finished this deck for now."))

        default_colors = defaults.get("colors", {})
        for key, _label in self._overview_style_color_specs():
            for mode in ("light", "dark"):
                line_edit = self.overview_style_color_inputs.get((key, mode))
                if not line_edit:
                    continue
                value = default_colors.get(mode, {}).get(key, self._overview_style_default_color(key, mode))
                line_edit.setText(value)

        self.overview_style_preview_overviewer_button.setChecked(True)
        del blockers
        self._update_overview_style_controls()
        show_settings_toast(self, tr("overview_style_reset_toast", "Overview style reset to default"))

    def _save_overview_style_settings(self):
        if not hasattr(self, "overview_style_sync_toggle"):
            return
        colors = {"light": {}, "dark": {}}
        for key, _label in self._overview_style_color_specs():
            for mode in ("light", "dark"):
                colors[mode][key] = self._box_effect_color_for_input(
                    self.overview_style_color_inputs.get((key, mode)),
                    self._overview_style_default_color(key, mode),
                )

        overview_style = self.current_config.setdefault("overview_style", {})
        overview_style.update({
            "sync_box_effect": self.overview_style_sync_toggle.isChecked(),
            "dynamic": True,
            "blur": self.overview_style_blur_slider.value(),
            "opacity": self.overview_style_opacity_slider.value(),
            "radius": self.overview_style_radius_slider.value(),
            "stroke": self.overview_style_stroke_slider.value(),
            "study_button_opacity": self.overview_study_button_opacity_slider.value(),
            "study_button_radius": self.overview_study_button_radius_slider.value(),
            "study_button_stroke": self.overview_study_button_stroke_slider.value(),
            "study_button_dashed": self.overview_study_button_dashed_toggle.isChecked(),
            "study_button_animated": self.overview_study_button_animated_toggle.isChecked(),
            "colors": colors,
        })
        mw.col.conf["onigiri_overview_sync_box_effect"] = overview_style["sync_box_effect"]
        mw.col.conf["onigiri_overview_box_color_theme_mode"] = "separate"
        mw.col.conf["onigiri_overview_effect_blur"] = overview_style["blur"]
        mw.col.conf["onigiri_overview_effect_opacity"] = overview_style["opacity"]
        mw.col.conf["onigiri_overview_border_radius"] = overview_style["radius"]
        mw.col.conf["onigiri_overview_border_width"] = overview_style["stroke"]

