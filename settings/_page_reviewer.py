class ReviewerPageMixin:
    def create_reviewer_tab(self):
        page, layout = self._create_scrollable_page()

        # --- Reviewer Background Section ---
        reviewer_bg_section = SectionGroup("Reviewer Background", self)
        layout.addWidget(reviewer_bg_section)

        reviewer_bg_content = reviewer_bg_section.content_layout

        # Background mode radio buttons
        reviewer_bg_mode_layout = QHBoxLayout()
        reviewer_bg_button_group = QButtonGroup(reviewer_bg_section)

        self.reviewer_bg_main_radio = QRadioButton("Use Main Background")
        self.reviewer_bg_color_radio = QRadioButton("Solid Color")
        self.reviewer_bg_image_color_radio = QRadioButton("Image")

        reviewer_bg_button_group.addButton(self.reviewer_bg_main_radio)
        reviewer_bg_button_group.addButton(self.reviewer_bg_color_radio)
        reviewer_bg_button_group.addButton(self.reviewer_bg_image_color_radio)

        conf = config.get_config()
        reviewer_bg_mode = conf.get("onigiri_reviewer_bg_mode", "main")
        self.reviewer_bg_main_radio.setChecked(reviewer_bg_mode == "main")
        self.reviewer_bg_color_radio.setChecked(reviewer_bg_mode == "color")
        self.reviewer_bg_image_color_radio.setChecked(reviewer_bg_mode == "image_color")

        reviewer_bg_mode_layout.addWidget(self.reviewer_bg_main_radio)
        reviewer_bg_mode_layout.addWidget(self.reviewer_bg_color_radio)
        reviewer_bg_mode_layout.addWidget(self.reviewer_bg_image_color_radio)
        reviewer_bg_mode_layout.addStretch()
        reviewer_bg_content.addLayout(reviewer_bg_mode_layout)

        # Main background options (blur and opacity when using main background)
        self.reviewer_bg_main_group = QWidget()
        main_effects_layout = QHBoxLayout(self.reviewer_bg_main_group)
        main_effects_layout.setContentsMargins(0, 10, 0, 0)

        main_blur_label = QLabel("Background Blur:")
        self.reviewer_bg_main_blur_spinbox = QSpinBox()
        self.reviewer_bg_main_blur_spinbox.setMinimum(0)
        self.reviewer_bg_main_blur_spinbox.setMaximum(100)
        self.reviewer_bg_main_blur_spinbox.setSuffix(" %")
        self.reviewer_bg_main_blur_spinbox.setValue(conf.get("onigiri_reviewer_bg_main_blur", 0))

        main_opacity_label = QLabel("Background Opacity:")
        self.reviewer_bg_main_opacity_spinbox = QSpinBox()
        self.reviewer_bg_main_opacity_spinbox.setMinimum(0)
        self.reviewer_bg_main_opacity_spinbox.setMaximum(100)
        self.reviewer_bg_main_opacity_spinbox.setSuffix(" %")
        self.reviewer_bg_main_opacity_spinbox.setValue(conf.get("onigiri_reviewer_bg_main_opacity", 100))

        main_effects_layout.addWidget(main_blur_label)
        main_effects_layout.addWidget(self.reviewer_bg_main_blur_spinbox)
        main_effects_layout.addSpacing(20)
        main_effects_layout.addWidget(main_opacity_label)
        main_effects_layout.addWidget(self.reviewer_bg_main_opacity_spinbox)
        main_effects_layout.addStretch()
        reviewer_bg_content.addWidget(self.reviewer_bg_main_group)

        # Custom background options
        self.reviewer_bg_custom_group = self._create_reviewer_bg_custom_options()
        reviewer_bg_content.addWidget(self.reviewer_bg_custom_group)

        # Connect signals
        self.reviewer_bg_main_radio.toggled.connect(self._toggle_reviewer_bg_options)
        self.reviewer_bg_color_radio.toggled.connect(self._toggle_reviewer_bg_options)
        self.reviewer_bg_image_color_radio.toggled.connect(self._toggle_reviewer_bg_options)
        self._toggle_reviewer_bg_options()

        bottom_bar_section = SectionGroup("Bottom Bar Background", self)
        layout.addWidget(bottom_bar_section)

        # --- Notification Position Section ---
        notification_pos_section = self.create_notification_position_section()
        layout.addWidget(notification_pos_section)

        # --- Answer Buttons Section ---
        reviewer_buttons_section = self.create_reviewer_buttons_section()
        layout.addWidget(reviewer_buttons_section)

        mode_layout_content = bottom_bar_section.content_layout
        mode_layout = QHBoxLayout()

        bottom_bar_button_group = QButtonGroup(bottom_bar_section)

        self.reviewer_bar_main_radio = QRadioButton("Match Main Background")
        self.reviewer_bar_color_radio = QRadioButton("Solid Color")
        self.reviewer_bar_image_color_radio = QRadioButton("Image")

        bottom_bar_button_group.addButton(self.reviewer_bar_main_radio)
        bottom_bar_button_group.addButton(self.reviewer_bar_color_radio)
        bottom_bar_button_group.addButton(self.reviewer_bar_image_color_radio)

        self.reviewer_bar_main_radio.setChecked(self.reviewer_bottom_bar_mode == "main")
        self.reviewer_bar_color_radio.setChecked(self.reviewer_bottom_bar_mode == "color")
        self.reviewer_bar_image_color_radio.setChecked(self.reviewer_bottom_bar_mode == "image_color")

        mode_layout.addWidget(self.reviewer_bar_main_radio)

        self.reviewer_bar_match_reviewer_bg_radio = QRadioButton("Match Reviewer Background")
        bottom_bar_button_group.addButton(self.reviewer_bar_match_reviewer_bg_radio)
        self.reviewer_bar_match_reviewer_bg_radio.setChecked(self.reviewer_bottom_bar_mode == "match_reviewer_bg")
        mode_layout.addWidget(self.reviewer_bar_match_reviewer_bg_radio)

        mode_layout.addWidget(self.reviewer_bar_color_radio)
        mode_layout.addWidget(self.reviewer_bar_image_color_radio)
        mode_layout.addStretch()
        mode_layout_content.addLayout(mode_layout)

        self.reviewer_bar_match_main_group = QWidget()
        match_main_layout = QVBoxLayout(self.reviewer_bar_match_main_group)
        match_main_layout.setContentsMargins(0, 10, 0, 0)

        match_effects_layout = QHBoxLayout()
        blur_label = QLabel("Background Blur:")
        self.reviewer_bar_match_main_blur_spinbox = QSpinBox()
        self.reviewer_bar_match_main_blur_spinbox.setMinimum(0); self.reviewer_bar_match_main_blur_spinbox.setMaximum(100)
        self.reviewer_bar_match_main_blur_spinbox.setSuffix(" %")
        self.reviewer_bar_match_main_blur_spinbox.setValue(self.current_config.get("onigiri_reviewer_bottom_bar_match_main_blur", 5))

        opacity_label = QLabel("Bar Opacity:")
        self.reviewer_bar_match_main_opacity_spinbox = QSpinBox()
        self.reviewer_bar_match_main_opacity_spinbox.setMinimum(0); self.reviewer_bar_match_main_opacity_spinbox.setMaximum(100)
        self.reviewer_bar_match_main_opacity_spinbox.setSuffix(" %")
        self.reviewer_bar_match_main_opacity_spinbox.setValue(self.current_config.get("onigiri_reviewer_bottom_bar_match_main_opacity", 90))

        match_effects_layout.addWidget(blur_label)
        match_effects_layout.addWidget(self.reviewer_bar_match_main_blur_spinbox)
        match_effects_layout.addSpacing(20)
        match_effects_layout.addWidget(opacity_label)
        match_effects_layout.addWidget(self.reviewer_bar_match_main_opacity_spinbox)
        match_effects_layout.addStretch()
        match_main_layout.addLayout(match_effects_layout)
        mode_layout_content.addWidget(self.reviewer_bar_match_main_group)

        self.reviewer_bar_match_reviewer_bg_group = QWidget()
        match_reviewer_bg_layout = QVBoxLayout(self.reviewer_bar_match_reviewer_bg_group)
        match_reviewer_bg_layout.setContentsMargins(0, 10, 0, 0)

        match_reviewer_bg_effects_layout = QHBoxLayout()
        blur_label_2 = QLabel("Background Blur:")
        self.reviewer_bar_match_reviewer_bg_blur_spinbox = QSpinBox()
        self.reviewer_bar_match_reviewer_bg_blur_spinbox.setMinimum(0); self.reviewer_bar_match_reviewer_bg_blur_spinbox.setMaximum(100)
        self.reviewer_bar_match_reviewer_bg_blur_spinbox.setSuffix(" %")
        self.reviewer_bar_match_reviewer_bg_blur_spinbox.setValue(self.current_config.get("onigiri_reviewer_bottom_bar_match_reviewer_bg_blur", 5))

        opacity_label_2 = QLabel("Bar Opacity:")
        self.reviewer_bar_match_reviewer_bg_opacity_spinbox = QSpinBox()
        self.reviewer_bar_match_reviewer_bg_opacity_spinbox.setMinimum(0); self.reviewer_bar_match_reviewer_bg_opacity_spinbox.setMaximum(100)
        self.reviewer_bar_match_reviewer_bg_opacity_spinbox.setSuffix(" %")
        self.reviewer_bar_match_reviewer_bg_opacity_spinbox.setValue(self.current_config.get("onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity", 90))

        match_reviewer_bg_effects_layout.addWidget(blur_label_2)
        match_reviewer_bg_effects_layout.addWidget(self.reviewer_bar_match_reviewer_bg_blur_spinbox)
        match_reviewer_bg_effects_layout.addSpacing(20)
        match_reviewer_bg_effects_layout.addWidget(opacity_label_2)
        match_reviewer_bg_effects_layout.addWidget(self.reviewer_bar_match_reviewer_bg_opacity_spinbox)
        match_reviewer_bg_effects_layout.addStretch()
        match_reviewer_bg_layout.addLayout(match_reviewer_bg_effects_layout)
        mode_layout_content.addWidget(self.reviewer_bar_match_reviewer_bg_group)

        self.reviewer_bar_custom_group = self.create_reviewer_bar_custom_options()
        mode_layout_content.addWidget(self.reviewer_bar_custom_group)

        self.reviewer_bar_main_radio.toggled.connect(lambda checked: self._on_bottom_bar_mode_changed("main", checked))
        self.reviewer_bar_match_reviewer_bg_radio.toggled.connect(lambda checked: self._on_bottom_bar_mode_changed("match_reviewer_bg", checked))
        self.reviewer_bar_color_radio.toggled.connect(lambda checked: self._on_bottom_bar_mode_changed("color", checked))
        self.reviewer_bar_image_color_radio.toggled.connect(lambda checked: self._on_bottom_bar_mode_changed("image_color", checked))
        self.reviewer_bar_main_radio.toggled.connect(self.toggle_reviewer_bar_options)
        self.reviewer_bar_match_reviewer_bg_radio.toggled.connect(self.toggle_reviewer_bar_options)
        self.reviewer_bar_color_radio.toggled.connect(self.toggle_reviewer_bar_options)
        self.reviewer_bar_image_color_radio.toggled.connect(self.toggle_reviewer_bar_options)
        self.toggle_reviewer_bar_options()

        # --- RESET BUTTONS ---
        reset_buttons_layout = QHBoxLayout()
        reset_buttons_layout.addStretch()

        reset_reviewer_bg_button = QPushButton("Reset Reviewer Background to Default")
        reset_reviewer_bg_button.clicked.connect(self.reset_reviewer_bg_to_default)
        reset_buttons_layout.addWidget(reset_reviewer_bg_button)

        reset_bottom_bar_button = QPushButton("Reset Bottom Bar to Default")
        reset_bottom_bar_button.clicked.connect(self.reset_reviewer_bottom_bar_to_default)
        reset_buttons_layout.addWidget(reset_bottom_bar_button)

        layout.addLayout(reset_buttons_layout)
        # --- END OF RESET BUTTONS ---

        layout.addStretch()

        sections = {
            "Reviewer Background": reviewer_bg_section,
            "Bottom Bar Background": bottom_bar_section,
            "Notification Position": notification_pos_section,
            "Answer Buttons": reviewer_buttons_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections, buttons_per_row=2)

        return page


    def create_reviewer_buttons_section(self):
        section = SectionGroup("Answer Buttons", self)
        layout = section.content_layout

        # --- General Button Settings ---
        general_group = QGroupBox("General Button settings")
        general_layout = QVBoxLayout(general_group)
        general_layout.setSpacing(10)

        # Enable Toggle and other global settings
        # Row 1: Enable & Radius
        row1 = QHBoxLayout()

        enable_label = QLabel("Enable Custom Buttons:")
        self.reviewer_btn_custom_enable_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.reviewer_btn_custom_enable_toggle.setChecked(self.current_config.get("onigiri_reviewer_btn_custom_enabled", False))
        row1.addWidget(enable_label)
        row1.addWidget(self.reviewer_btn_custom_enable_toggle)
        row1.addSpacing(20)

        radius_label = QLabel("Border Radius:")
        self.reviewer_btn_radius_spin = QSpinBox()
        self.reviewer_btn_radius_spin.setRange(0, 50)
        self.reviewer_btn_radius_spin.setSuffix(" px")
        self.reviewer_btn_radius_spin.setValue(self.current_config.get("onigiri_reviewer_btn_radius", 12))
        row1.addWidget(radius_label)
        row1.addWidget(self.reviewer_btn_radius_spin)
        row1.addStretch()
        general_layout.addLayout(row1)

        # Row 2: Padding, Button Height, Bar Height
        row2 = QHBoxLayout()

        padding_label = QLabel("Button Padding:")
        self.reviewer_btn_padding_spin = QSpinBox()
        self.reviewer_btn_padding_spin.setRange(0, 30)
        self.reviewer_btn_padding_spin.setSuffix(" px")
        self.reviewer_btn_padding_spin.setValue(self.current_config.get("onigiri_reviewer_btn_padding", 5))
        row2.addWidget(padding_label)
        row2.addWidget(self.reviewer_btn_padding_spin)
        row2.addSpacing(20)

        btn_height_label = QLabel("Min Height:")
        self.reviewer_btn_height_spin = QSpinBox()
        self.reviewer_btn_height_spin.setRange(20, 100)
        self.reviewer_btn_height_spin.setSuffix(" px")
        self.reviewer_btn_height_spin.setValue(self.current_config.get("onigiri_reviewer_btn_height", 40))
        row2.addWidget(btn_height_label)
        row2.addWidget(self.reviewer_btn_height_spin)
        row2.addSpacing(20)

        bar_height_label = QLabel("Bar Height:")
        self.reviewer_bar_height_spin = QSpinBox()
        self.reviewer_bar_height_spin.setRange(30, 200)
        self.reviewer_bar_height_spin.setSuffix(" px")
        self.reviewer_bar_height_spin.setValue(self.current_config.get("onigiri_reviewer_bar_height", 60))
        row2.addWidget(bar_height_label)
        row2.addWidget(self.reviewer_bar_height_spin)
        row2.addStretch()
        general_layout.addLayout(row2)

        layout.addWidget(general_group)

        # --- Two Column Layout for Light/Dark Mode ---
        modes_layout = QHBoxLayout()
        modes_layout.setSpacing(15)

        self.preview_buttons = {"light": {}, "dark": {}}

        # Define button data for iteration
        # (Label, key, default_bg, default_text)
        # We'll split defaults for light/dark later
        button_defs = [
            ("Again", "again", 
             ("#ffb3b3", "#4d0000"), ("#ffcccb", "#4a0000")), # (light_bg, light_text), (dark_bg, dark_text)
            ("Hard", "hard", 
             ("#ffe0b3", "#4d2600"), ("#ffd699", "#4d1d00")),
            ("Good", "good", 
             ("#b3ffb3", "#004d00"), ("#90ee90", "#004000")),
            ("Easy", "easy", 
             ("#b3d9ff", "#00264d"), ("#add8e6", "#002952")),
            ("Show Answer", "other",
             ("#ffffff", "#2c2c2c"), ("#3a3a3a", "#e0e0e0")) # Special handling for other
        ]

        # Mode loop to create columns
        for mode_name, mode_key, bg_color in [("Light Mode", "light", "#FFFFFF"), ("Dark Mode", "dark", "#2C2C2C")]:
            column_widget = QWidget()
            column_widget.setObjectName(f"column_{mode_key}")

            # Determine text color based on background
            text_col = "black" if mode_key == "light" else "white"
            sub_text_col = "#555" if mode_key == "light" else "#ccc"

            column_widget.setStyleSheet(f"""
                QWidget#column_{mode_key} {{
                    background-color: {bg_color}; 
                    border-radius: 10px;
                }}
                QLabel {{ color: {text_col}; }}
                QGroupBox {{ color: {text_col}; font-weight: bold; }}
                QGroupBox::title {{ color: {text_col}; }}
                QCheckBox {{ color: {text_col}; }}
                QRadioButton {{ color: {text_col}; }}
                QLineEdit {{ color: {text_col}; background-color: {'#fff' if mode_key == 'light' else '#444'}; border: 1px solid {'#ccc' if mode_key == 'light' else '#555'}; border-radius: 4px; }}
            """)

            col_layout = QVBoxLayout(column_widget)
            col_layout.setContentsMargins(15, 15, 15, 15)
            col_layout.setSpacing(15)
            # Ensure columns don't shrink too much
            column_widget.setMinimumWidth(350) 

            # Header
            header = QLabel(mode_name)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Force style again just in case, though the parent stylesheet should handle it
            header.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {text_col};")
            col_layout.addWidget(header)

            # --- Preview Box for this mode ---
            preview_frame = QFrame()
            preview_frame.setStyleSheet(f"background-color: {bg_color}; border: 1px solid {'#444' if mode_key == 'dark' else '#ddd'}; border-radius: 8px;")
            p_layout = QHBoxLayout(preview_frame)
            p_layout.setContentsMargins(10, 10, 10, 10)
            p_layout.addStretch() # Add stretch to center buttons

            # Create preview buttons
            for label, key, light_defaults, dark_defaults in button_defs:
                btn = QPushButton(label)
                if key == "other":
                     # Show Answer button usually auto-hides other buttons in real Anki, 
                     # but here we show them all side-by-side or just show answer?
                     # Mimicking the screenshot: All buttons visible.
                     pass

                # Store for live updates
                self.preview_buttons[mode_key][key] = btn
                p_layout.addWidget(btn)

            p_layout.addStretch()
            col_layout.addWidget(preview_frame)

            # --- Settings List for this mode ---
            # REMOVED QScrollArea to fix visibility issues
            settings_content = QWidget()
            settings_content.setStyleSheet("background: transparent;")
            settings_layout = QVBoxLayout(settings_content)
            settings_layout.setContentsMargins(0, 0, 0, 0)
            settings_layout.setSpacing(10)

            # Add Color Pickers for each button
            for label, key, (l_bg, l_text), (d_bg, d_text) in button_defs:
                # Group for the button
                btn_group = QGroupBox(f"{label} Button")
                btn_group.setStyleSheet(f"QGroupBox::title {{ color: {'#ddd' if mode_key == 'dark' else '#333'}; }}")
                g_layout = QVBoxLayout(btn_group)

                # Determine keys and defaults based on mode
                if mode_key == "light":
                    bg_config_key = f"onigiri_reviewer_btn_{key}_bg_light" if key != "other" else "onigiri_reviewer_other_btn_bg_light"
                    text_config_key = f"onigiri_reviewer_btn_{key}_text_light" if key != "other" else "onigiri_reviewer_other_btn_text_light"
                    bg_default = l_bg
                    text_default = l_text
                    # Specific input names for connection later
                    bg_input_name = f"btn_{key}_bg_light" if key != "other" else "other_btn_bg_light"
                    text_input_name = f"btn_{key}_text_light" if key != "other" else "other_btn_text_light"
                else: # dark
                    bg_config_key = f"onigiri_reviewer_btn_{key}_bg_dark" if key != "other" else "onigiri_reviewer_other_btn_bg_dark"
                    text_config_key = f"onigiri_reviewer_btn_{key}_text_dark" if key != "other" else "onigiri_reviewer_other_btn_text_dark"
                    bg_default = d_bg
                    text_default = d_text
                    bg_input_name = f"btn_{key}_bg_dark" if key != "other" else "other_btn_bg_dark"
                    text_input_name = f"btn_{key}_text_dark" if key != "other" else "other_btn_text_dark"

                # Add rows
                bg_row = self._create_color_picker_row(
                    "Background", 
                    self.current_config.get(bg_config_key, bg_default), 
                    bg_input_name
                )
                text_row = self._create_color_picker_row(
                    "Text", 
                    self.current_config.get(text_config_key, text_default), 
                    text_input_name
                )
                g_layout.addLayout(bg_row)
                g_layout.addLayout(text_row)

                # Special case: Hover for "Other" button
                if key == "other":
                    hover_label = QLabel("Hover State")
                    g_layout.addWidget(hover_label)

                    if mode_key == "light":
                        h_bg_key = "onigiri_reviewer_other_btn_hover_bg_light"
                        h_txt_key = "onigiri_reviewer_other_btn_hover_text_light"
                        h_bg_def, h_txt_def = "#2c2c2c", "#f0f0f0"
                        h_bg_name, h_txt_name = "other_btn_hover_bg_light", "other_btn_hover_text_light"
                    else:
                        h_bg_key = "onigiri_reviewer_other_btn_hover_bg_dark"
                        h_txt_key = "onigiri_reviewer_other_btn_hover_text_dark"
                        h_bg_def, h_txt_def = "#e0e0e0", "#3a3a3a"
                        h_bg_name, h_txt_name = "other_btn_hover_bg_dark", "other_btn_hover_text_dark"

                    h_bg_row = self._create_color_picker_row(
                        "Hover Bg", self.current_config.get(h_bg_key, h_bg_def), h_bg_name
                    )
                    h_txt_row = self._create_color_picker_row(
                        "Hover Text", self.current_config.get(h_txt_key, h_txt_def), h_txt_name
                    )
                    g_layout.addLayout(h_bg_row)
                    g_layout.addLayout(h_txt_row)

                settings_layout.addWidget(btn_group)

            # Stat Text Color (One per mode)
            stattxt_group = QGroupBox("Stat Text Color (.stattxt)")
            stattxt_group.setStyleSheet(f"QGroupBox::title {{ color: {'#ddd' if mode_key == 'dark' else '#333'}; }}")
            s_layout = QVBoxLayout(stattxt_group)
            if mode_key == "light":
                 stattxt_row = self._create_color_picker_row(
                    "Color", self.current_config.get("onigiri_reviewer_stattxt_color_light", "#666666"), "stattxt_color_light"
                 )
            else:
                 stattxt_row = self._create_color_picker_row(
                    "Color", self.current_config.get("onigiri_reviewer_stattxt_color_dark", "#aaaaaa"), "stattxt_color_dark"
                 )
            s_layout.addLayout(stattxt_row)
            settings_layout.addWidget(stattxt_group)

            settings_layout.addStretch()

            col_layout.addWidget(settings_content) # Directly add widget to column layout
            modes_layout.addWidget(column_widget)

        layout.addLayout(modes_layout)

        # Connect signals for preview updates
        # We need to collect all inputs to connect them
        all_inputs = [
            self.reviewer_btn_radius_spin, self.reviewer_btn_padding_spin, self.reviewer_btn_height_spin
        ]

        # Collect all dynamic inputs
        # We need to find them via their attribute names we assigned in _create_color_picker_row
        # Helper list of attributes to check
        attr_to_check = []
        for key in ["again", "hard", "good", "easy"]:
            attr_to_check.extend([
                f"btn_{key}_bg_light_color_input", f"btn_{key}_bg_dark_color_input",
                f"btn_{key}_text_light_color_input", f"btn_{key}_text_dark_color_input"
            ])
        attr_to_check.extend([
            "other_btn_bg_light_color_input", "other_btn_bg_dark_color_input",
            "other_btn_text_light_color_input", "other_btn_text_dark_color_input",
            "other_btn_hover_bg_light_color_input", "other_btn_hover_bg_dark_color_input",
            "other_btn_hover_text_light_color_input", "other_btn_hover_text_dark_color_input",
            "stattxt_color_light_color_input", "stattxt_color_dark_color_input"
        ])

        for attr in attr_to_check:
            if hasattr(self, attr):
                all_inputs.append(getattr(self, attr))

        for widget in all_inputs:
            if isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self._update_reviewer_button_previews)
            elif isinstance(widget, QLineEdit):
                # Using textChanged instead of editingFinished for live preview
                widget.textChanged.connect(self._update_reviewer_button_previews)

        # Initial update
        self._update_reviewer_button_previews()

        # Reset Button (specific to this section)
        reset_btn_layout = QHBoxLayout()
        reset_btn = QPushButton("Reset Answer Buttons to Default")
        reset_btn.clicked.connect(self.reset_reviewer_buttons_to_default)
        reset_btn_layout.addWidget(reset_btn)
        reset_btn_layout.addStretch()
        layout.addLayout(reset_btn_layout)

        return section


    def _update_reviewer_button_previews(self):
        if not hasattr(self, 'preview_buttons'):
            return

        radius = self.reviewer_btn_radius_spin.value()
        padding = self.reviewer_btn_padding_spin.value()
        height = self.reviewer_btn_height_spin.value()

        buttons = ["again", "hard", "good", "easy"]

        for mode in ["light", "dark"]:
            for key in buttons:
                btn = self.preview_buttons[mode][key]

                # Get colors using getattr to avoid KeyError
                if mode == "light":
                    bg = getattr(self, f"btn_{key}_bg_light_color_input").text()
                    text = getattr(self, f"btn_{key}_text_light_color_input").text()
                else:
                    bg = getattr(self, f"btn_{key}_bg_dark_color_input").text()
                    text = getattr(self, f"btn_{key}_text_dark_color_input").text()

                if not self.reviewer_btn_custom_enable_toggle.isChecked():
                     btn.setStyleSheet("")
                     continue

                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg} !important;
                        color: {text};
                        border-radius: {radius}px;
                        padding: {padding}px;
                        height: {height}px;
                        border: none;
                        font-weight: bold;
                    }}
                """)

            # Update "Other" button preview
            other_btn = self.preview_buttons[mode]["other"]
            if mode == "light":
                bg = getattr(self, "other_btn_bg_light_color_input").text()
                text = getattr(self, "other_btn_text_light_color_input").text()
            else:
                bg = getattr(self, "other_btn_bg_dark_color_input").text()
                text = getattr(self, "other_btn_text_dark_color_input").text()

            other_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg} !important;
                    color: {text};
                    border-radius: {radius}px;
                    padding: {padding}px;
                    height: {height}px;
                    border: none;
                    font-weight: bold;
                }}
            """)


    def reset_reviewer_buttons_to_default(self):
        # Reset Global Settings
        self.reviewer_btn_custom_enable_toggle.setChecked(True)
        self.reviewer_btn_radius_spin.setValue(12)
        self.reviewer_btn_padding_spin.setValue(5)
        self.reviewer_btn_height_spin.setValue(40)
        self.reviewer_bar_height_spin.setValue(60)

        getattr(self, "stattxt_color_light_color_input").setText("#666666")
        if hasattr(self, "stattxt_color_light_circular_button"): getattr(self, "stattxt_color_light_circular_button").setColor("#666666")

        getattr(self, "stattxt_color_dark_color_input").setText("#aaaaaa")
        if hasattr(self, "stattxt_color_dark_circular_button"): getattr(self, "stattxt_color_dark_circular_button").setColor("#aaaaaa")

        # Reset Other Buttons
        getattr(self, "other_btn_bg_light_color_input").setText("#ffffff")
        if hasattr(self, "other_btn_bg_light_circular_button"): getattr(self, "other_btn_bg_light_circular_button").setColor("#ffffff")

        getattr(self, "other_btn_text_light_color_input").setText("#2c2c2c")
        if hasattr(self, "other_btn_text_light_circular_button"): getattr(self, "other_btn_text_light_circular_button").setColor("#2c2c2c")

        getattr(self, "other_btn_bg_dark_color_input").setText("#3a3a3a")
        if hasattr(self, "other_btn_bg_dark_circular_button"): getattr(self, "other_btn_bg_dark_circular_button").setColor("#3a3a3a")

        getattr(self, "other_btn_text_dark_color_input").setText("#e0e0e0")
        if hasattr(self, "other_btn_text_dark_circular_button"): getattr(self, "other_btn_text_dark_circular_button").setColor("#e0e0e0")

        getattr(self, "other_btn_hover_bg_light_color_input").setText("#2c2c2c")
        if hasattr(self, "other_btn_hover_bg_light_circular_button"): getattr(self, "other_btn_hover_bg_light_circular_button").setColor("#2c2c2c")

        getattr(self, "other_btn_hover_text_light_color_input").setText("#f0f0f0")
        if hasattr(self, "other_btn_hover_text_light_circular_button"): getattr(self, "other_btn_hover_text_light_circular_button").setColor("#f0f0f0")

        getattr(self, "other_btn_hover_bg_dark_color_input").setText("#e0e0e0")
        if hasattr(self, "other_btn_hover_bg_dark_circular_button"): getattr(self, "other_btn_hover_bg_dark_circular_button").setColor("#e0e0e0")

        getattr(self, "other_btn_hover_text_dark_color_input").setText("#3a3a3a")
        if hasattr(self, "other_btn_hover_text_dark_circular_button"): getattr(self, "other_btn_hover_text_dark_circular_button").setColor("#3a3a3a")

        # Reset Per Button Settings
        defaults = [
            ("again", "#ffb3b3", "#4d0000", "#ffcccb", "#4a0000"),
            ("hard", "#ffe0b3", "#4d2600", "#ffd699", "#4d1d00"),
            ("good", "#b3ffb3", "#004d00", "#90ee90", "#004000"),
            ("easy", "#b3d9ff", "#00264d", "#add8e6", "#002952")
        ]

        for key, def_bg_l, def_txt_l, def_bg_d, def_txt_d in defaults:
            getattr(self, f"btn_{key}_bg_light_color_input").setText(def_bg_l)
            if hasattr(self, f"btn_{key}_bg_light_circular_button"): getattr(self, f"btn_{key}_bg_light_circular_button").setColor(def_bg_l)

            getattr(self, f"btn_{key}_text_light_color_input").setText(def_txt_l)
            if hasattr(self, f"btn_{key}_text_light_circular_button"): getattr(self, f"btn_{key}_text_light_circular_button").setColor(def_txt_l)

            getattr(self, f"btn_{key}_bg_dark_color_input").setText(def_bg_d)
            if hasattr(self, f"btn_{key}_bg_dark_circular_button"): getattr(self, f"btn_{key}_bg_dark_circular_button").setColor(def_bg_d)

            getattr(self, f"btn_{key}_text_dark_color_input").setText(def_txt_d)
            if hasattr(self, f"btn_{key}_text_dark_circular_button"): getattr(self, f"btn_{key}_text_dark_circular_button").setColor(def_txt_d)

        showInfo("Answer buttons have been reset to default values.")


    def create_reviewer_bar_custom_options(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        self.reviewer_bar_color_group = QWidget()
        color_layout = QVBoxLayout(self.reviewer_bar_color_group)
        color_layout.setContentsMargins(0, 0, 0, 0)

        self.reviewer_bar_light_color_row = self._create_color_picker_row(
            "Color (Light Mode)", mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_light_color", "#EEEEEE"), "reviewer_bar_light"
        )
        self.reviewer_bar_dark_color_row = self._create_color_picker_row(
            "Color (Dark Mode)", mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_dark_color", "#3C3C3C"), "reviewer_bar_dark"
        )
        color_layout.addLayout(self.reviewer_bar_light_color_row)
        color_layout.addLayout(self.reviewer_bar_dark_color_row)
        layout.addWidget(self.reviewer_bar_color_group)

        self.galleries["reviewer_bar_bg"] = {}
        self.reviewer_bar_image_group = self._create_image_gallery_group(
            "reviewer_bar_bg", "user_files/reviewer_bar_bg", "onigiri_reviewer_bottom_bar_bg_image", is_sub_group=True
        )
        layout.addWidget(self.reviewer_bar_image_group)

        effects_container = QWidget()
        effects_layout = QHBoxLayout(effects_container)
        effects_layout.setContentsMargins(0, 10, 0, 0)
        self.reviewer_bar_blur_label = QLabel("Blur:")
        self.reviewer_bar_blur_spinbox = QSpinBox()
        self.reviewer_bar_blur_spinbox.setMinimum(0); self.reviewer_bar_blur_spinbox.setMaximum(100)
        self.reviewer_bar_blur_spinbox.setSuffix(" %")
        self.reviewer_bar_blur_spinbox.setValue(mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_blur", 0))

        self.reviewer_bar_opacity_label = QLabel("Opacity:")
        self.reviewer_bar_opacity_spinbox = QSpinBox()
        self.reviewer_bar_opacity_spinbox.setMinimum(0); self.reviewer_bar_opacity_spinbox.setMaximum(100)
        self.reviewer_bar_opacity_spinbox.setSuffix(" %")
        self.reviewer_bar_opacity_spinbox.setValue(mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_opacity", 100))

        effects_layout.addWidget(self.reviewer_bar_blur_label)
        effects_layout.addWidget(self.reviewer_bar_blur_spinbox)
        effects_layout.addSpacing(20)
        effects_layout.addWidget(self.reviewer_bar_opacity_label)
        effects_layout.addWidget(self.reviewer_bar_opacity_spinbox)
        effects_layout.addStretch()
        layout.addWidget(effects_container)

        if 'reviewer_bar_bg' in self.galleries:
            self.galleries['reviewer_bar_bg']['effects_widget'] = effects_container

        return widget


    def create_notification_position_section(self):
        section = SectionGroup("Reviewer Notification Widget Position", self)

        container = QWidget()
        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(40)

        # --- Left Side: Selection Grid ---
        grid_container = QWidget()
        grid_layout = QGridLayout(grid_container)
        grid_layout.setSpacing(10)

        positions = [
            ("top-left", "↖", 0, 0),
            ("top-center", "↑", 0, 1),
            ("top-right", "↗", 0, 2),
            ("bottom-left", "↙", 1, 0),
            ("bottom-center", "↓", 1, 1),
            ("bottom-right", "↘", 1, 2),
        ]

        self.notification_pos_buttons = {}
        current_pos = self.current_config.get("onigiri_reviewer_notification_position", "top-right")

        for pos_id, label, row, col in positions:
            btn = QPushButton(label)
            btn.setFixedSize(60, 45)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            # Style for buttons
            base_style = f"""
                QPushButton {{
                    border: 1px solid #ccc;
                    border-radius: 8px;
                    background-color: transparent;
                    font-size: 20px;
                    color: #555;
                }}
                QPushButton:hover {{
                    background-color: rgba(0,0,0,0.05);
                }}
                QPushButton:checked {{
                    background-color: {self.accent_color};
                    color: white;
                    border: 1px solid {self.accent_color};
                }}
            """

            if theme_manager.night_mode:
                base_style = f"""
                    QPushButton {{
                        border: 1px solid #555;
                        border-radius: 8px;
                        background-color: transparent;
                        font-size: 20px;
                        color: #ccc;
                    }}
                    QPushButton:hover {{
                        background-color: rgba(255,255,255,0.05);
                    }}
                    QPushButton:checked {{
                        background-color: {self.accent_color};
                        color: white;
                        border: 1px solid {self.accent_color};
                    }}
                """

            btn.setStyleSheet(base_style)

            if pos_id == current_pos:
                btn.setChecked(True)

            btn.clicked.connect(lambda checked, pid=pos_id: self._update_notification_position(pid))

            self.notification_pos_buttons[pos_id] = btn
            grid_layout.addWidget(btn, row, col)

        main_layout.addWidget(grid_container)

        # --- Right Side: Preview ---
        self.notif_preview_widget = QWidget()
        self.notif_preview_widget.setFixedSize(200, 120)
        # Style the preview container (screen representation)
        screen_border = "#ccc" if not theme_manager.night_mode else "#555"
        screen_bg = "transparent"
        self.notif_preview_widget.setStyleSheet(f"""
            QWidget {{
                border: 2px solid {screen_border};
                border-radius: 12px;
                background-color: {screen_bg};
            }}
        """)

        # The small notification rectangle
        self.notif_rect = QLabel(self.notif_preview_widget)
        self.notif_rect.setFixedSize(60, 30)
        self.notif_rect.setStyleSheet(f"""
            background-color: {self.accent_color};
            border-radius: 4px;
        """)

        self._position_preview_rect(current_pos)

        main_layout.addWidget(self.notif_preview_widget)
        main_layout.addStretch()

        section.content_layout.addWidget(container)

        # --- Bottom: Silent Toggle ---
        silent_layout = QHBoxLayout()
        silent_label = QLabel("Silent all notifications")
        silent_label.setStyleSheet("font-size: 14px; color: #555;")
        if theme_manager.night_mode:
            silent_label.setStyleSheet("font-size: 14px; color: #ccc;")

        self.silent_toggle = AnimatedToggleButton(self, accent_color=self.accent_color)
        self.silent_toggle.setChecked(self.current_config.get("onigiri_reviewer_silent_notifications", False))
        self.silent_toggle.toggled.connect(self._on_silent_notif_toggled)

        silent_layout.addWidget(silent_label)
        silent_layout.addWidget(self.silent_toggle)
        silent_layout.addStretch()

        section.content_layout.addLayout(silent_layout)

        return section


    def _on_silent_notif_toggled(self, checked):
        self.current_config["onigiri_reviewer_silent_notifications"] = checked


    def _update_notification_position(self, pos_id):
        # Update config
        self.current_config["onigiri_reviewer_notification_position"] = pos_id

        # Update buttons state (ensure exclusive check)
        for pid, btn in self.notification_pos_buttons.items():
            if pid != pos_id:
                btn.setChecked(False)
            else:
                btn.setChecked(True)

        # Update preview
        self._position_preview_rect(pos_id)


    def _position_preview_rect(self, pos_id):
        # Calculate position for the preview rect within the 200x120 container
        # Rect size: 60x30
        # Padding/Margin assumed: 10px from edges

        container_w, container_h = 200, 120
        rect_w, rect_h = 60, 30
        margin = 10

        x, y = 0, 0

        if "left" in pos_id:
            x = margin
        elif "right" in pos_id:
            x = container_w - rect_w - margin
        else: # center
            x = (container_w - rect_w) // 2

        if "top" in pos_id:
            y = margin
        elif "bottom" in pos_id:
            y = container_h - rect_h - margin

        self.notif_rect.move(x, y)


    def _create_reviewer_bg_custom_options(self):
        """Create custom background options for the reviewer screen."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        # Color options
        self.reviewer_bg_color_group = QWidget()
        color_layout = QVBoxLayout(self.reviewer_bg_color_group)
        color_layout.setContentsMargins(0, 0, 0, 0)

        conf = config.get_config()

        # Single color container
        self.reviewer_bg_single_color_container = QWidget()
        single_color_layout = QVBoxLayout(self.reviewer_bg_single_color_container)
        self.reviewer_bg_single_color_row = self._create_color_picker_row(
            "Background Color", conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF"), "reviewer_bg_single"
        )
        single_color_layout.addLayout(self.reviewer_bg_single_color_row)

        # Separate colors container
        self.reviewer_bg_separate_colors_container = QWidget()
        separate_colors_layout = QVBoxLayout(self.reviewer_bg_separate_colors_container)
        self.reviewer_bg_light_color_row = self._create_color_picker_row(
            "Background (Light Mode)", conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF"), "reviewer_bg_light"
        )
        self.reviewer_bg_dark_color_row = self._create_color_picker_row(
            "Background (Dark Mode)", conf.get("onigiri_reviewer_bg_dark_color", "#2C2C2C"), "reviewer_bg_dark"
        )
        separate_colors_layout.addLayout(self.reviewer_bg_light_color_row)
        separate_colors_layout.addLayout(self.reviewer_bg_dark_color_row)

        # Add both containers to the layout
        color_layout.addWidget(self.reviewer_bg_single_color_container)
        color_layout.addWidget(self.reviewer_bg_separate_colors_container)

        # Add theme mode toggle for color selection
        self.reviewer_bg_color_theme_mode_group = QButtonGroup()
        self.reviewer_bg_color_theme_mode_single = QRadioButton("Use same color for both themes")
        self.reviewer_bg_color_theme_mode_separate = QRadioButton("Use different colors for light/dark themes")
        self.reviewer_bg_color_theme_mode_group.addButton(self.reviewer_bg_color_theme_mode_single)
        self.reviewer_bg_color_theme_mode_group.addButton(self.reviewer_bg_color_theme_mode_separate)

        # Load saved theme mode or default to single
        reviewer_bg_color_theme_mode = mw.col.conf.get("onigiri_reviewer_bg_color_theme_mode", "single")
        self.reviewer_bg_color_theme_mode_single.setChecked(reviewer_bg_color_theme_mode == "single")
        self.reviewer_bg_color_theme_mode_separate.setChecked(reviewer_bg_color_theme_mode == "separate")

        color_theme_mode_layout = QHBoxLayout()
        color_theme_mode_layout.addWidget(self.reviewer_bg_color_theme_mode_single)
        color_theme_mode_layout.addWidget(self.reviewer_bg_color_theme_mode_separate)
        color_theme_mode_layout.addStretch()
        color_theme_mode_container = QWidget()
        color_theme_mode_container.setLayout(color_theme_mode_layout)
        color_theme_mode_container.setContentsMargins(15, 5, 0, 5)
        color_layout.insertWidget(0, color_theme_mode_container)

        # Set initial visibility based on theme mode
        self._update_reviewer_bg_color_theme_mode_visibility()

        # Connect theme mode signals for color selection
        self.reviewer_bg_color_theme_mode_single.toggled.connect(self._update_reviewer_bg_color_theme_mode_visibility)
        self.reviewer_bg_color_theme_mode_separate.toggled.connect(self._update_reviewer_bg_color_theme_mode_visibility)

        layout.addWidget(self.reviewer_bg_color_group)

        # Image galleries (only for Image mode)
        self.reviewer_bg_image_group = QWidget()
        image_layout = QVBoxLayout(self.reviewer_bg_image_group)
        image_layout.setContentsMargins(0, 10, 0, 0)

        # Add theme mode toggle for image selection
        self.reviewer_bg_image_theme_mode_group = QButtonGroup()
        self.reviewer_bg_image_theme_mode_single = QRadioButton("Use same image for both themes")
        self.reviewer_bg_image_theme_mode_separate = QRadioButton("Use different images for light/dark themes")
        self.reviewer_bg_image_theme_mode_group.addButton(self.reviewer_bg_image_theme_mode_single)
        self.reviewer_bg_image_theme_mode_group.addButton(self.reviewer_bg_image_theme_mode_separate)

        # Load saved theme mode or default to single
        reviewer_bg_image_theme_mode = mw.col.conf.get("onigiri_reviewer_bg_image_theme_mode", "single")
        self.reviewer_bg_image_theme_mode_single.setChecked(reviewer_bg_image_theme_mode == "single")
        self.reviewer_bg_image_theme_mode_separate.setChecked(reviewer_bg_image_theme_mode == "separate")

        image_theme_mode_layout = QHBoxLayout()
        image_theme_mode_layout.addWidget(self.reviewer_bg_image_theme_mode_single)
        image_theme_mode_layout.addWidget(self.reviewer_bg_image_theme_mode_separate)
        image_theme_mode_layout.addStretch()
        image_theme_mode_container = QWidget()
        image_theme_mode_container.setLayout(image_theme_mode_layout)
        image_theme_mode_container.setContentsMargins(15, 5, 0, 5)
        image_layout.addWidget(image_theme_mode_container)

        # Single image container
        self.reviewer_bg_single_image_container = QWidget()
        single_image_layout = QVBoxLayout(self.reviewer_bg_single_image_container)
        single_image_layout.setContentsMargins(0, 10, 0, 0)
        self.galleries["reviewer_bg_single"] = {}
        single_image_layout.addWidget(self._create_image_gallery_group(
            "reviewer_bg_single", "user_files/reviewer_bg", "onigiri_reviewer_bg_image", 
            title="Background Image", is_sub_group=True
        ))

        # Separate images container
        self.reviewer_bg_separate_images_container = QWidget()
        sep_layout = QHBoxLayout(self.reviewer_bg_separate_images_container)
        sep_layout.setContentsMargins(0, 10, 0, 0)
        self.galleries["reviewer_bg_light"] = {}
        sep_layout.addWidget(self._create_image_gallery_group(
            "reviewer_bg_light", "user_files/reviewer_bg", "onigiri_reviewer_bg_image_light", 
            title="Light Mode Background", is_sub_group=True
        ))
        self.galleries["reviewer_bg_dark"] = {}
        sep_layout.addWidget(self._create_image_gallery_group(
            "reviewer_bg_dark", "user_files/reviewer_bg", "onigiri_reviewer_bg_image_dark", 
            title="Dark Mode Background", is_sub_group=True
        ))

        # Add both containers to the layout
        image_layout.addWidget(self.reviewer_bg_single_image_container)
        image_layout.addWidget(self.reviewer_bg_separate_images_container)

        # Set initial visibility based on theme mode
        self._update_reviewer_bg_image_theme_mode_visibility()

        # Connect theme mode signals for image selection
        self.reviewer_bg_image_theme_mode_single.toggled.connect(self._update_reviewer_bg_image_theme_mode_visibility)
        self.reviewer_bg_image_theme_mode_separate.toggled.connect(self._update_reviewer_bg_image_theme_mode_visibility)

        layout.addWidget(self.reviewer_bg_image_group)

        # Effects (blur and opacity)
        self.reviewer_bg_effects_container = QWidget()
        effects_layout = QHBoxLayout(self.reviewer_bg_effects_container)
        effects_layout.setContentsMargins(0, 10, 0, 0)

        self.reviewer_bg_blur_label = QLabel("Blur:")
        self.reviewer_bg_blur_spinbox = QSpinBox()
        self.reviewer_bg_blur_spinbox.setMinimum(0)
        self.reviewer_bg_blur_spinbox.setMaximum(100)
        self.reviewer_bg_blur_spinbox.setSuffix(" %")
        self.reviewer_bg_blur_spinbox.setValue(conf.get("onigiri_reviewer_bg_blur", 0))

        self.reviewer_bg_opacity_label = QLabel("Opacity:")
        self.reviewer_bg_opacity_spinbox = QSpinBox()
        self.reviewer_bg_opacity_spinbox.setMinimum(0)
        self.reviewer_bg_opacity_spinbox.setMaximum(100)
        self.reviewer_bg_opacity_spinbox.setSuffix(" %")
        self.reviewer_bg_opacity_spinbox.setValue(conf.get("onigiri_reviewer_bg_opacity", 100))

        effects_layout.addWidget(self.reviewer_bg_blur_label)
        effects_layout.addWidget(self.reviewer_bg_blur_spinbox)
        effects_layout.addSpacing(20)
        effects_layout.addWidget(self.reviewer_bg_opacity_label)
        effects_layout.addWidget(self.reviewer_bg_opacity_spinbox)
        effects_layout.addStretch()
        layout.addWidget(self.reviewer_bg_effects_container)

        # Initially hide image options (only show for Image mode)
        self.reviewer_bg_image_group.setVisible(False)

        return widget


    def _update_reviewer_bg_color_theme_mode_visibility(self):
        """Update visibility of single/separate color pickers for reviewer background based on theme mode selection."""
        is_single = self.reviewer_bg_color_theme_mode_single.isChecked()
        self.reviewer_bg_single_color_container.setVisible(is_single)
        self.reviewer_bg_separate_colors_container.setVisible(not is_single)

        # If switching to single theme mode, update the single color picker with light mode color
        if is_single and hasattr(self, 'reviewer_bg_light_color_row'):
            light_color = self.reviewer_bg_light_color_row.itemAt(1).widget().text()
            self.reviewer_bg_single_color_row.itemAt(1).widget().setText(light_color)


    def _update_reviewer_bg_image_theme_mode_visibility(self):
        """Update visibility of single/separate image galleries for reviewer background based on theme mode selection."""
        is_single = self.reviewer_bg_image_theme_mode_single.isChecked()
        self.reviewer_bg_single_image_container.setVisible(is_single)
        self.reviewer_bg_separate_images_container.setVisible(not is_single)

        # If switching to single theme mode, update the single gallery with light mode image
        if is_single and 'reviewer_bg_light' in self.galleries and 'reviewer_bg_single' in self.galleries:
            light_image = self.galleries['reviewer_bg_light'].get('selected', '')
            if light_image and 'path_input' in self.galleries['reviewer_bg_single']:
                self.galleries['reviewer_bg_single']['selected'] = light_image
                self.galleries['reviewer_bg_single']['path_input'].setText(light_image)


    def _toggle_reviewer_bg_options(self):
        """Toggle visibility of reviewer background options based on selected mode."""
        is_main = self.reviewer_bg_main_radio.isChecked()
        self.reviewer_bg_main_group.setVisible(is_main)
        self.reviewer_bg_custom_group.setVisible(not is_main)

        # Control visibility of color and image options within custom group
        if not is_main:
            is_color = self.reviewer_bg_color_radio.isChecked()
            is_image_color = self.reviewer_bg_image_color_radio.isChecked()

            # Show color options for both 'Solid Color' and 'Image'
            self.reviewer_bg_color_group.setVisible(is_color or is_image_color)

            # Show image options and effects only for 'Image'
            self.reviewer_bg_image_group.setVisible(is_image_color)
            self.reviewer_bg_effects_container.setVisible(is_image_color)

            # If this is the first time showing the color group, ensure theme mode visibility is set
            if (is_color or is_image_color) and hasattr(self, 'reviewer_bg_color_theme_mode_single'):
                self._update_reviewer_bg_color_theme_mode_visibility()

            # If this is the first time showing the image group, ensure theme mode visibility is set
            if is_image_color and hasattr(self, 'reviewer_bg_image_theme_mode_single'):
                self._update_reviewer_bg_image_theme_mode_visibility()




    def _on_bottom_bar_mode_changed(self, mode, is_checked):
        if is_checked:
            self.reviewer_bottom_bar_mode = mode


    def _save_reviewer_settings(self):
        # Save Answer Buttons Settings
        self.current_config["onigiri_reviewer_btn_custom_enabled"] = self.reviewer_btn_custom_enable_toggle.isChecked()
        self.current_config["onigiri_reviewer_btn_radius"] = self.reviewer_btn_radius_spin.value()
        self.current_config["onigiri_reviewer_btn_padding"] = self.reviewer_btn_padding_spin.value()
        self.current_config["onigiri_reviewer_btn_height"] = self.reviewer_btn_height_spin.value()
        self.current_config["onigiri_reviewer_bar_height"] = self.reviewer_bar_height_spin.value()
        self.current_config["onigiri_reviewer_stattxt_color_light"] = getattr(self, "stattxt_color_light_color_input").text()
        self.current_config["onigiri_reviewer_stattxt_color_dark"] = getattr(self, "stattxt_color_dark_color_input").text()

        # Save Other Buttons
        self.current_config["onigiri_reviewer_other_btn_bg_light"] = getattr(self, "other_btn_bg_light_color_input").text()
        self.current_config["onigiri_reviewer_other_btn_text_light"] = getattr(self, "other_btn_text_light_color_input").text()
        self.current_config["onigiri_reviewer_other_btn_bg_dark"] = getattr(self, "other_btn_bg_dark_color_input").text()
        self.current_config["onigiri_reviewer_other_btn_text_dark"] = getattr(self, "other_btn_text_dark_color_input").text()
        self.current_config["onigiri_reviewer_other_btn_hover_bg_light"] = getattr(self, "other_btn_hover_bg_light_color_input").text()
        self.current_config["onigiri_reviewer_other_btn_hover_text_light"] = getattr(self, "other_btn_hover_text_light_color_input").text()
        self.current_config["onigiri_reviewer_other_btn_hover_bg_dark"] = getattr(self, "other_btn_hover_bg_dark_color_input").text()
        self.current_config["onigiri_reviewer_other_btn_hover_text_dark"] = getattr(self, "other_btn_hover_text_dark_color_input").text()

        for key in ["again", "hard", "good", "easy"]:
            self.current_config[f"onigiri_reviewer_btn_{key}_bg_light"] = getattr(self, f"btn_{key}_bg_light_color_input").text()
            self.current_config[f"onigiri_reviewer_btn_{key}_bg_dark"] = getattr(self, f"btn_{key}_bg_dark_color_input").text()
            self.current_config[f"onigiri_reviewer_btn_{key}_text_light"] = getattr(self, f"btn_{key}_text_light_color_input").text()
            self.current_config[f"onigiri_reviewer_btn_{key}_text_dark"] = getattr(self, f"btn_{key}_text_dark_color_input").text()

        # --- Reviewer Background ---
        if self.reviewer_bg_main_radio.isChecked():
            self.current_config["onigiri_reviewer_bg_mode"] = "main"
        elif self.reviewer_bg_color_radio.isChecked():
            self.current_config["onigiri_reviewer_bg_mode"] = "color"
        elif self.reviewer_bg_image_color_radio.isChecked():
            self.current_config["onigiri_reviewer_bg_mode"] = "image_color"

        # Save theme mode for colors and images
        color_theme_mode = "single" if hasattr(self, 'reviewer_bg_color_theme_mode_single') and self.reviewer_bg_color_theme_mode_single.isChecked() else "separate"
        image_theme_mode = "single" if hasattr(self, 'reviewer_bg_image_theme_mode_single') and self.reviewer_bg_image_theme_mode_single.isChecked() else "separate"

        mw.col.conf["onigiri_reviewer_bg_color_theme_mode"] = color_theme_mode
        mw.col.conf["onigiri_reviewer_bg_image_theme_mode"] = image_theme_mode

        # Also save to addon config so patcher.py can read it
        self.current_config["onigiri_reviewer_bg_image_mode"] = image_theme_mode

        # Main background blur and opacity
        self.current_config["onigiri_reviewer_bg_main_blur"] = self.reviewer_bg_main_blur_spinbox.value()
        self.current_config["onigiri_reviewer_bg_main_opacity"] = self.reviewer_bg_main_opacity_spinbox.value()

        # Save colors based on theme mode
        if color_theme_mode == "single" and hasattr(self, 'reviewer_bg_single_color_row'):
            # In single mode, use the single color for both themes
            single_color = self.reviewer_bg_single_color_row.itemAt(1).widget().text()
            self.current_config["onigiri_reviewer_bg_light_color"] = single_color
            self.current_config["onigiri_reviewer_bg_dark_color"] = single_color
        else:
            # In separate mode, use the individual colors
            if hasattr(self, 'reviewer_bg_light_color_row'):
                self.current_config["onigiri_reviewer_bg_light_color"] = self.reviewer_bg_light_color_row.itemAt(1).widget().text()
            if hasattr(self, 'reviewer_bg_dark_color_row'):
                self.current_config["onigiri_reviewer_bg_dark_color"] = self.reviewer_bg_dark_color_row.itemAt(1).widget().text()

        # Save blur and opacity
        self.current_config["onigiri_reviewer_bg_blur"] = self.reviewer_bg_blur_spinbox.value()
        self.current_config["onigiri_reviewer_bg_opacity"] = self.reviewer_bg_opacity_spinbox.value()

        # Save image selections based on theme mode
        if image_theme_mode == "single" and 'reviewer_bg_single' in self.galleries:
            # In single mode, use the single image for both themes
            single_image = self.galleries['reviewer_bg_single'].get('selected', '')
            self.current_config["onigiri_reviewer_bg_image"] = single_image
            self.current_config["onigiri_reviewer_bg_image_light"] = single_image
            self.current_config["onigiri_reviewer_bg_image_dark"] = single_image
        else:
            # In separate mode, use the individual images
            if 'reviewer_bg_light' in self.galleries:
                self.current_config["onigiri_reviewer_bg_image_light"] = self.galleries['reviewer_bg_light'].get('selected', '')
            if 'reviewer_bg_dark' in self.galleries:
                self.current_config["onigiri_reviewer_bg_image_dark"] = self.galleries['reviewer_bg_dark'].get('selected', '')

        # --- Bottom Bar ---
        self.current_config["onigiri_reviewer_bottom_bar_bg_mode"] = self.reviewer_bottom_bar_mode
        self.current_config["onigiri_reviewer_bottom_bar_match_main_blur"] = self.reviewer_bar_match_main_blur_spinbox.value()
        self.current_config["onigiri_reviewer_bottom_bar_match_main_opacity"] = self.reviewer_bar_match_main_opacity_spinbox.value()
        self.current_config["onigiri_reviewer_bottom_bar_match_reviewer_bg_blur"] = self.reviewer_bar_match_reviewer_bg_blur_spinbox.value()
        self.current_config["onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity"] = self.reviewer_bar_match_reviewer_bg_opacity_spinbox.value()
        self.current_config["onigiri_reviewer_bottom_bar_bg_light_color"] = self.reviewer_bar_light_color_input.text()
        self.current_config["onigiri_reviewer_bottom_bar_bg_dark_color"] = self.reviewer_bar_dark_color_input.text()
        self.current_config["onigiri_reviewer_bottom_bar_bg_blur"] = self.reviewer_bar_blur_spinbox.value()
        self.current_config["onigiri_reviewer_bottom_bar_bg_opacity"] = self.reviewer_bar_opacity_spinbox.value()
        if 'reviewer_bar_bg' in self.galleries:
            self.current_config["onigiri_reviewer_bottom_bar_bg_image"] = self.galleries['reviewer_bar_bg']['selected']


    def reset_reviewer_bg_to_default(self):
        """Reset reviewer background settings to defaults."""
        # Set mode to "Use Main Background"
        self.reviewer_bg_main_radio.setChecked(True)

        # Reset main background blur and opacity
        self.reviewer_bg_main_blur_spinbox.setValue(DEFAULTS["onigiri_reviewer_bg_main_blur"])
        self.reviewer_bg_main_opacity_spinbox.setValue(DEFAULTS["onigiri_reviewer_bg_main_opacity"])

        # Reset colors to defaults
        self.reviewer_bg_light_color_input.setText(DEFAULTS["onigiri_reviewer_bg_light_color"])
        self.reviewer_bg_dark_color_input.setText(DEFAULTS["onigiri_reviewer_bg_dark_color"])

        # Clear all reviewer background images
        for key in ['reviewer_bg_light', 'reviewer_bg_dark']:
            if key in self.galleries:
                self.galleries[key]['selected'] = ""
                if self.galleries[key].get('path_input'):
                    self.galleries[key]['path_input'].setText("")
                self._refresh_gallery(key)

        # Reset blur and opacity for custom mode
        self.reviewer_bg_blur_spinbox.setValue(DEFAULTS["onigiri_reviewer_bg_blur"])
        self.reviewer_bg_opacity_spinbox.setValue(DEFAULTS["onigiri_reviewer_bg_opacity"])

        QMessageBox.information(self, "Reviewer Background Reset", "The reviewer background settings have been reset to default values.\nPress 'Save' to apply the changes.")


    def reset_reviewer_bottom_bar_to_default(self):
        """Reset reviewer bottom bar background settings to defaults."""
        # Set mode to "Match Reviewer Background"
        self.reviewer_bar_match_reviewer_bg_radio.setChecked(True)

        # Reset match main settings
        self.reviewer_bar_match_main_blur_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_match_main_blur"])
        self.reviewer_bar_match_main_opacity_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_match_main_opacity"])

        # Reset match reviewer bg settings
        self.reviewer_bar_match_reviewer_bg_blur_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_match_reviewer_bg_blur"])
        self.reviewer_bar_match_reviewer_bg_opacity_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity"])

        # Reset custom colors
        self.reviewer_bar_light_color_input.setText(DEFAULTS["onigiri_reviewer_bottom_bar_bg_light_color"])
        self.reviewer_bar_dark_color_input.setText(DEFAULTS["onigiri_reviewer_bottom_bar_bg_dark_color"])

        # Clear bottom bar image
        if 'reviewer_bar_bg' in self.galleries:
            self.galleries['reviewer_bar_bg']['selected'] = ""
            if self.galleries['reviewer_bar_bg'].get('path_input'):
                self.galleries['reviewer_bar_bg']['path_input'].setText("")
            self._refresh_gallery('reviewer_bar_bg')

        # Reset blur and opacity
        self.reviewer_bar_blur_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_bg_blur"])
        self.reviewer_bar_opacity_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_bg_opacity"])

        QMessageBox.information(self, "Bottom Bar Reset", "The bottom bar background settings have been reset to default values.\nPress 'Save' to apply the changes.")



    def toggle_reviewer_bar_options(self):
        is_main = self.reviewer_bar_main_radio.isChecked()
        is_match_reviewer_bg = self.reviewer_bar_match_reviewer_bg_radio.isChecked()
        is_custom = not (is_main or is_match_reviewer_bg)

        self.reviewer_bar_match_main_group.setVisible(is_main)
        self.reviewer_bar_match_reviewer_bg_group.setVisible(is_match_reviewer_bg)
        self.reviewer_bar_custom_group.setVisible(is_custom)

        if is_custom:
            is_color = self.reviewer_bar_color_radio.isChecked()
            is_image_color = self.reviewer_bar_image_color_radio.isChecked()

            # Show color picker for 'Solid Color' and 'Image'
            self.reviewer_bar_color_group.setVisible(is_color or is_image_color)

            # Show image gallery and effects (blur, opacity) for 'Image' and 'Image'
            image_options_visible = is_image_color
            self.reviewer_bar_image_group.setVisible(image_options_visible)

            if 'reviewer_bar_bg' in self.galleries and self.galleries['reviewer_bar_bg'].get('effects_widget'):
                self.galleries['reviewer_bar_bg']['effects_widget'].setVisible(image_options_visible)


    def _on_shape_selected(self):
        sender = self.sender()
        if sender and sender.isChecked():
            self.selected_heatmap_shape = sender.property("shape_filename")


    def _reflow_shape_icons(self, width=0):
        # Use a fixed horizontal layout instead of dynamic resizing
        if not hasattr(self, 'shape_buttons') or not self.shape_buttons:
            return

        if not hasattr(self, 'shapes_grid_layout') or self.shapes_grid_layout is None:
            return

        # Clear layout but keep widgets in self.shape_buttons
        while item := self.shapes_grid_layout.takeAt(0):
            if item.widget():
                item.widget().setParent(None)

        # Use a fixed number of columns for horizontal layout (6 icons per row)
        num_cols = 6

        # Repopulate the grid from the master list of buttons
        for i, button in enumerate(self.shape_buttons):
            if button is not None:
                row, col = divmod(i, num_cols)
                self.shapes_grid_layout.addWidget(button, row, col)


    def _create_shape_selector(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setFixedHeight(250)

        self.shape_scroll_content = QWidget()
        self.shapes_grid_layout = QGridLayout(self.shape_scroll_content)
        self.shapes_grid_layout.setSpacing(10)
        self.shapes_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll_area.setWidget(self.shape_scroll_content)
        # Event filter removed - using fixed horizontal layout instead of dynamic resize

        layout.addWidget(scroll_area)

        if theme_manager.night_mode:
            input_bg, border, accent_color = "#3a3a3a", "#4a4a4a", self.accent_color
        else:
            input_bg, border, accent_color = "#f5f5f5", "#e0e0e0", self.accent_color

        button_style = f"""
            QPushButton {{
                background-color: {input_bg};
                border: 2px solid transparent;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                border-color: {border};
            }}
            QPushButton:checked {{
                border-color: {accent_color};
                background-color: {border};
            }}
        """

        icons_path = os.path.join(self.addon_path, "system_files", "heatmap_system_icons")
        self.shape_buttons = []

        if os.path.isdir(icons_path):
            for filename in sorted(os.listdir(icons_path)):
                if filename.lower().endswith(".svg"):
                    shape_name = os.path.splitext(filename)[0].replace("_", " ").title()

                    card = QPushButton()
                    card.setCheckable(True)
                    card.setAutoExclusive(True)
                    card.setProperty("shape_filename", filename)
                    card.setFixedSize(80, 80)
                    card.setToolTip(shape_name)
                    card.setStyleSheet(button_style)

                    icon = self._get_svg_icon(os.path.join(icons_path, filename))
                    if icon:
                        card.setIcon(icon)
                        card.setIconSize(card.size() * 0.6)

                    card.clicked.connect(self._on_shape_selected)
                    self.shape_buttons.append(card)

        # Perform initial layout with default columns
        self._reflow_shape_icons()

        self.selected_heatmap_shape = self.current_config.get("heatmapShape", "square.svg")
        for btn in self.shape_buttons:
            if btn.property("shape_filename") == self.selected_heatmap_shape:
                btn.setChecked(True)
                break

        return widget



