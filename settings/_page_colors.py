class ColorsPageMixin:
    def create_colors_page(self):
        page, layout = self._create_scrollable_page()

        # --- Create the Accent Color group first, but don't add it to the main layout yet ---
        accent_group, accent_layout = self._create_inner_group("Accent Color")
        light_accent = self.current_config.get("colors", {}).get("light", {}).get("--accent-color", DEFAULTS["colors"]["light"]["--accent-color"])
        dark_accent = self.current_config.get("colors", {}).get("dark", {}).get("--accent-color", DEFAULTS["colors"]["dark"]["--accent-color"])
        accent_layout.addLayout(self._create_color_picker_row("Light Mode Accent", light_accent, "light_accent", tooltip_text="The main color for buttons and selections in light mode."))
        accent_layout.addLayout(self._create_color_picker_row("Dark Mode Accent", dark_accent, "dark_accent", tooltip_text="The main color for buttons and selections in dark mode."))

        # --- Create the General Palette section ---
        general_colors_section = SectionGroup(
            "General Palette", 
            self,
            description="Here you can customize colors that affect more than one space of the add-on"
        )

        # --- Add the Accent Color group to the General Palette section ---
        general_colors_section.add_widget(accent_group)

        # --- START: New Boxes Color Effect Section ---
        canvas_effect_group, canvas_effect_layout = self._create_inner_group("Boxes Color Effect")
        canvas_effect_group.setToolTip("Apply a visual effect to the 'Boxes Color' background color.")

        # Radio buttons for mode selection
        mode_layout = QHBoxLayout()
        self.canvas_effect_none_radio = QRadioButton("None")
        self.canvas_effect_opacity_radio = QRadioButton("Opacity")
        self.canvas_effect_glass_radio = QRadioButton("Glassmorphism")
        mode_layout.addWidget(self.canvas_effect_none_radio)
        mode_layout.addWidget(self.canvas_effect_opacity_radio)
        mode_layout.addWidget(self.canvas_effect_glass_radio)
        mode_layout.addStretch()
        canvas_effect_layout.addLayout(mode_layout)

        # Intensity control
        intensity_layout = QHBoxLayout()
        intensity_label = QLabel("Effect Intensity:")
        self.canvas_effect_intensity_spinbox = QSpinBox()
        self.canvas_effect_intensity_spinbox.setMinimum(0)
        self.canvas_effect_intensity_spinbox.setMaximum(100)
        self.canvas_effect_intensity_spinbox.setSuffix(" %")
        intensity_layout.addWidget(intensity_label)
        intensity_layout.addWidget(self.canvas_effect_intensity_spinbox)
        intensity_layout.addStretch()
        canvas_effect_layout.addLayout(intensity_layout)

        # Load saved settings for canvas effects
        saved_mode = mw.col.conf.get("onigiri_canvas_inset_effect_mode", "none")
        if saved_mode == "opacity":
            self.canvas_effect_opacity_radio.setChecked(True)
        elif saved_mode == "glassmorphism":
            self.canvas_effect_glass_radio.setChecked(True)
        else:
            self.canvas_effect_none_radio.setChecked(True)

        saved_intensity = mw.col.conf.get("onigiri_canvas_inset_effect_intensity", 50)
        self.canvas_effect_intensity_spinbox.setValue(saved_intensity)

        # Connect signals
        self.canvas_effect_none_radio.toggled.connect(self._toggle_canvas_intensity_spinbox)
        self._toggle_canvas_intensity_spinbox() # Set initial state

        general_colors_section.add_widget(canvas_effect_group)
        # --- END: New Boxes Color Effect Section ---

        general_modes_layout = QHBoxLayout()

        light_colors_group, light_colors_layout = self._create_inner_group("Light Mode")
        self._build_color_sections(light_colors_layout, "light")
        general_modes_layout.addWidget(light_colors_group)

        dark_colors_group, dark_colors_layout = self._create_inner_group("Dark Mode")
        self._build_color_sections(dark_colors_layout, "dark")
        general_modes_layout.addWidget(dark_colors_group)

        general_colors_section.add_layout(general_modes_layout)

        # --- Add the combined section to the main page layout ---
        layout.addWidget(general_colors_section)

        reset_button_layout = QHBoxLayout()
        reset_colors_button = QPushButton("Reset Colors to Default")
        reset_colors_button.setToolTip("Resets only the theme colors (accent, text, etc.) to default.")
        reset_colors_button.clicked.connect(self.reset_colors_to_default)

        reset_button_layout.addStretch()
        reset_button_layout.addWidget(reset_colors_button)
        layout.addLayout(reset_button_layout)
        layout.addStretch()
        return page


    def _build_color_sections(self, parent_layout, mode):
        sections = {
            "General": ["--fg", "--fg-subtle", "--border", "--canvas-inset"],
        }

        handled_keys = {key for keys in sections.values() for key in keys}

        for title, keys in sections.items():
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)

            title_label = QLabel(title)
            title_label.setStyleSheet("font-weight: bold; margin-top: 10px; margin-bottom: 5px;")
            layout.addWidget(title_label)

            self._populate_pills_for_keys(layout, mode, keys)
            parent_layout.addWidget(container)


    def _populate_pills_for_keys(self, layout, mode, keys):
        local_color_labels = COLOR_LABELS.copy()
        local_color_labels["--star-color"] = {
            "label": "Star Color",
            "tooltip": "Color for the filled stars in the Retention stat card."
        }
        local_color_labels["--empty-star-color"] = {
            "label": "Empty Star Color",
            "tooltip": "Color for the empty stars in the Retention stat card."
        }

        local_defaults = {
            "--star-color": "#FFD700",
            "--empty-star-color": "#e0e0e0" if mode == 'light' else '#4a4a4a'
        }

        colors = self.current_config.get("colors", {}).get(mode, {})

        for name in keys:
            if name not in local_color_labels:
                continue

            label_info = local_color_labels[name]
            default_value = DEFAULTS["colors"][mode].get(name, local_defaults.get(name))

            if default_value is not None:
                value = colors.get(name, default_value)
                pill_widget = self._create_color_pill(name, value, mode, label_info)
                layout.addWidget(pill_widget)


    def _create_color_pill(self, name, default_value, mode, label_info):
        widget = QFrame()
        widget.setObjectName("colorPill")
        widget.setFixedHeight(36)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        tooltip = label_info.get("tooltip", "")
        widget.setToolTip(f"{label_info['label']}: {tooltip}")
        widget.setMouseTracking(True)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 15, 5)
        layout.setSpacing(10)

        color_swatch = CircularColorButton(default_value)

        text_stack = QStackedWidget()
        text_stack.setStyleSheet("background: transparent;")

        name_label = QLabel(label_info['label'])
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("background: transparent;")

        hex_input = QLineEdit(default_value)
        hex_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if theme_manager.night_mode:
            text_color = "#e0e0e0"
            border_color = "#AAAAAA"
            focus_bg = "rgba(255, 255, 255, 0.1)"
        else:
            text_color = "#212121"
            border_color = "#888888"
            focus_bg = "rgba(0, 0, 0, 0.05)"

        hex_input.setStyleSheet(f"""
            QLineEdit {{ 
                font-family: monospace; 
                background: transparent; 
                border: none; 
                color: {text_color};
                padding: 1px;
            }}
            QLineEdit:focus {{
                border: 1px solid {border_color};
                border-radius: 3px;
                background: {focus_bg};
            }}
        """)

        hex_input.textChanged.connect(color_swatch.setColor)
        hex_input.returnPressed.connect(hex_input.clearFocus)
        color_swatch.clicked.connect(lambda _, le=hex_input, btn=color_swatch: self.open_color_picker(le, btn))

        min_width = max(name_label.fontMetrics().horizontalAdvance(label_info['label']), hex_input.fontMetrics().horizontalAdvance("#" + "W"*6)) + 12
        text_stack.setMinimumWidth(min_width)

        text_stack.addWidget(name_label)
        text_stack.addWidget(hex_input)

        widget.setProperty("text_stack", text_stack)
        widget.installEventFilter(self)

        layout.addWidget(color_swatch)
        layout.addWidget(text_stack)

        if mode in ["light", "dark"]:
            self.color_widgets[mode][name] = hex_input
        return widget


    def _save_colors_settings(self):
        # Save the accent colors, which are handled by dedicated widgets.
        self.current_config["colors"]["light"]["--accent-color"] = self.light_accent_color_input.text()
        self.current_config["colors"]["dark"]["--accent-color"] = self.dark_accent_color_input.text()

        # Explicitly define which color keys belong to the Palette page's "General Palette".
        palette_keys = {
            "--fg",
            "--fg-subtle",
            "--border",
            "--canvas-inset"
        }

        for mode in ["light", "dark"]:
            # Iterate only over the keys this page is responsible for.
            for key in palette_keys:
                # Check that the widget for this key has been loaded before trying to save it.
                if key in self.color_widgets[mode]:
                    widget = self.color_widgets[mode][key]
                    self.current_config["colors"][mode][key] = widget.text()

        # --- START: Save Boxes Color Effect Settings ---
        effect_mode = "none"
        if self.canvas_effect_opacity_radio.isChecked():
            effect_mode = "opacity"
        elif self.canvas_effect_glass_radio.isChecked():
            effect_mode = "glassmorphism"

        mw.col.conf["onigiri_canvas_inset_effect_mode"] = effect_mode
        mw.col.conf["onigiri_canvas_inset_effect_intensity"] = self.canvas_effect_intensity_spinbox.value()
        # --- END: Save Boxes Color Effect Settings ---




    def reset_colors_to_default(self):
        default_colors=DEFAULTS["colors"]
        for mode in["light","dark"]:
            if hasattr(self,f"{mode}_accent_color_input"):getattr(self,f"{mode}_accent_color_input").setText(default_colors[mode]["--accent-color"])
            for name,widget in self.color_widgets[mode].items():
                if name in default_colors[mode]:widget.setText(default_colors[mode][name])


    def reset_stats_colors_to_default(self):
        stats_color_keys = ["--star-color", "--empty-star-color", "--heatmap-color", "--heatmap-color-zero"]
        default_colors = DEFAULTS["colors"]

        for mode in ["light", "dark"]:
            for key in stats_color_keys:
                if key in self.color_widgets[mode] and key in default_colors[mode]:
                    widget = self.color_widgets[mode][key]
                    default_value = default_colors[mode][key]
                    widget.setText(default_value)

        QMessageBox.information(self, "Colors Reset", "The stats colors have been reset to their default values.\nPress 'Save' to apply the changes.")


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

        QMessageBox.information(self, "Heatmap Colors Reset", "The heatmap colors have been reset to their default values.\nPress 'Save' to apply the changes.")



