class OverviewsPageMixin:
    def create_overviews_page(self):
        page, layout = self._create_scrollable_page()

        # --- Overviewer Background Section ---
        overview_bg_section = SectionGroup("Overviewer Background", self)
        layout.addWidget(overview_bg_section)

        overview_bg_content = overview_bg_section.content_layout

        # Background mode radio buttons
        overview_bg_mode_layout = QHBoxLayout()
        overview_bg_button_group = QButtonGroup(overview_bg_section)

        self.overview_bg_main_radio = QRadioButton("Use Main Background")
        self.overview_bg_color_radio = QRadioButton("Solid Color")
        self.overview_bg_image_color_radio = QRadioButton("Image")

        overview_bg_button_group.addButton(self.overview_bg_main_radio)
        overview_bg_button_group.addButton(self.overview_bg_color_radio)
        overview_bg_button_group.addButton(self.overview_bg_image_color_radio)

        conf = config.get_config()
        overview_bg_mode = conf.get("onigiri_overview_bg_mode", "main")
        self.overview_bg_main_radio.setChecked(overview_bg_mode == "main")
        self.overview_bg_color_radio.setChecked(overview_bg_mode == "color")
        self.overview_bg_image_color_radio.setChecked(overview_bg_mode == "image_color")

        overview_bg_mode_layout.addWidget(self.overview_bg_main_radio)
        overview_bg_mode_layout.addWidget(self.overview_bg_color_radio)
        overview_bg_mode_layout.addWidget(self.overview_bg_image_color_radio)
        overview_bg_mode_layout.addStretch()
        overview_bg_content.addLayout(overview_bg_mode_layout)

        # Main background options (blur and opacity when using main background)
        self.overview_bg_main_group = QWidget()
        main_effects_layout = QHBoxLayout(self.overview_bg_main_group)
        main_effects_layout.setContentsMargins(0, 10, 0, 0)

        main_blur_label = QLabel("Background Blur:")
        self.overview_bg_main_blur_spinbox = QSpinBox()
        self.overview_bg_main_blur_spinbox.setMinimum(0)
        self.overview_bg_main_blur_spinbox.setMaximum(100)
        self.overview_bg_main_blur_spinbox.setSuffix(" %")
        self.overview_bg_main_blur_spinbox.setValue(conf.get("onigiri_overview_bg_main_blur", 0))

        main_opacity_label = QLabel("Background Opacity:")
        self.overview_bg_main_opacity_spinbox = QSpinBox()
        self.overview_bg_main_opacity_spinbox.setMinimum(0)
        self.overview_bg_main_opacity_spinbox.setMaximum(100)
        self.overview_bg_main_opacity_spinbox.setSuffix(" %")
        self.overview_bg_main_opacity_spinbox.setValue(conf.get("onigiri_overview_bg_main_opacity", 100))

        main_effects_layout.addWidget(main_blur_label)
        main_effects_layout.addWidget(self.overview_bg_main_blur_spinbox)
        main_effects_layout.addSpacing(20)
        main_effects_layout.addWidget(main_opacity_label)
        main_effects_layout.addWidget(self.overview_bg_main_opacity_spinbox)
        main_effects_layout.addStretch()
        overview_bg_content.addWidget(self.overview_bg_main_group)

        # Custom background options
        self.overview_bg_custom_group = self._create_overview_bg_custom_options()
        overview_bg_content.addWidget(self.overview_bg_custom_group)

        # Connect signals
        self.overview_bg_main_radio.toggled.connect(self._toggle_overview_bg_options)
        self.overview_bg_color_radio.toggled.connect(self._toggle_overview_bg_options)
        self.overview_bg_image_color_radio.toggled.connect(self._toggle_overview_bg_options)
        self._toggle_overview_bg_options()

        # Reset button
        reset_btn = QPushButton("Reset to Default Overviewer Background")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(lambda: self.overview_bg_main_radio.setChecked(True))
        overview_bg_content.addWidget(reset_btn)

        overview_section = SectionGroup(
            "",
            self,
            border=False,
            description="Customize the appearance of the deck overview screen."
        )

        # --- NEW: Section for Overview Style ---
        style_section = SectionGroup(
            "Overview Style",
            self,
            border=True,
            description="Choose between a detailed or a compact overview screen."
        )
        style_layout = QHBoxLayout()
        self.overview_pro_radio = QRadioButton("Pro Overview")
        self.overview_pro_radio.setToolTip("The default, detailed overview with large stats and buttons.")
        self.overview_mini_radio = QRadioButton("Mini Overview")
        self.overview_mini_radio.setToolTip("A compact overview, like the one in your provided image.")

        current_style = mw.col.conf.get("onigiri_overview_style", "pro")
        if current_style == "mini":
            self.overview_mini_radio.setChecked(True)
        else:
            self.overview_pro_radio.setChecked(True)

        style_layout.addWidget(self.overview_pro_radio)
        style_layout.addWidget(self.overview_mini_radio)
        style_layout.addStretch()
        style_section.add_layout(style_layout)
        overview_section.add_widget(style_section)
        # --- END NEW SECTION ---

        overview_layout = QFormLayout()
        overview_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        overview_layout.addRow("Custom 'Study Now' Text:", self.study_now_input)

        overview_color_modes_layout = QHBoxLayout()
        light_overview_colors_group, light_overview_colors_layout = self._create_inner_group("Light Mode Colors")
        light_overview_colors_layout.setSpacing(5)
        overview_color_keys = [
            "--button-primary-bg", "--button-primary-gradient-start", "--button-primary-gradient-end",
            "--new-count-bubble-bg", "--new-count-bubble-fg", "--learn-count-bubble-bg",
            "--learn-count-bubble-fg", "--review-count-bubble-bg", "--review-count-bubble-fg"
        ]
        self._populate_pills_for_keys(light_overview_colors_layout, "light", overview_color_keys)
        overview_color_modes_layout.addWidget(light_overview_colors_group)

        dark_overview_colors_group, dark_overview_colors_layout = self._create_inner_group("Dark Mode Colors")
        dark_overview_colors_layout.setSpacing(5)
        self._populate_pills_for_keys(dark_overview_colors_layout, "dark", overview_color_keys)
        overview_color_modes_layout.addWidget(dark_overview_colors_group)

        overview_section.add_layout(overview_color_modes_layout)
        overview_section.add_layout(overview_layout)
        layout.addWidget(overview_section)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider)

        congrats_section = SectionGroup(
            "Congratulations",
            self,
            border=False,
            description="Customize the 'Congratulations, you finished!' screen."
        )
        congrats_layout = QFormLayout()
        congrats_layout.addRow(self._create_toggle_row(self.show_congrats_profile_bar_checkbox, "Show profile bar on congrats screen"))
        congrats_layout.addRow("Custom Message:", self.congrats_message_input)
        congrats_section.add_layout(congrats_layout)
        layout.addWidget(congrats_section)

        layout.addStretch()

        sections = {

            "Overview Style": style_section,
            "Congratulations": congrats_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections)

        return page


    def _create_overview_bg_custom_options(self):
        """Create custom background options for the overview screen."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        # Color options
        self.overview_bg_color_group = QWidget()
        color_layout = QVBoxLayout(self.overview_bg_color_group)
        color_layout.setContentsMargins(0, 0, 0, 0)

        conf = config.get_config()

        # Single color container
        self.overview_bg_single_color_container = QWidget()
        single_color_layout = QVBoxLayout(self.overview_bg_single_color_container)
        self.overview_bg_single_color_row = self._create_color_picker_row(
            "Background Color", conf.get("onigiri_overview_bg_light_color", "#FFFFFF"), "overview_bg_single"
        )
        single_color_layout.addLayout(self.overview_bg_single_color_row)

        # Separate colors container
        self.overview_bg_separate_colors_container = QWidget()
        separate_colors_layout = QVBoxLayout(self.overview_bg_separate_colors_container)
        self.overview_bg_light_color_row = self._create_color_picker_row(
            "Background (Light Mode)", conf.get("onigiri_overview_bg_light_color", "#FFFFFF"), "overview_bg_light"
        )
        self.overview_bg_dark_color_row = self._create_color_picker_row(
            "Background (Dark Mode)", conf.get("onigiri_overview_bg_dark_color", "#2C2C2C"), "overview_bg_dark"
        )
        separate_colors_layout.addLayout(self.overview_bg_light_color_row)
        separate_colors_layout.addLayout(self.overview_bg_dark_color_row)

        # Add both containers to the layout
        color_layout.addWidget(self.overview_bg_single_color_container)
        color_layout.addWidget(self.overview_bg_separate_colors_container)

        # Add theme mode toggle for color selection
        self.overview_bg_color_theme_mode_group = QButtonGroup()
        self.overview_bg_color_theme_mode_single = QRadioButton("Use same color for both themes")
        self.overview_bg_color_theme_mode_separate = QRadioButton("Use different colors for light/dark themes")
        self.overview_bg_color_theme_mode_group.addButton(self.overview_bg_color_theme_mode_single)
        self.overview_bg_color_theme_mode_group.addButton(self.overview_bg_color_theme_mode_separate)

        # Load saved theme mode or default to single
        # Load saved theme mode or default to single
        overview_bg_color_theme_mode = conf.get("onigiri_overview_bg_color_theme_mode", "single")
        self.overview_bg_color_theme_mode_single.setChecked(overview_bg_color_theme_mode == "single")
        self.overview_bg_color_theme_mode_separate.setChecked(overview_bg_color_theme_mode == "separate")

        color_theme_mode_layout = QHBoxLayout()
        color_theme_mode_layout.addWidget(self.overview_bg_color_theme_mode_single)
        color_theme_mode_layout.addWidget(self.overview_bg_color_theme_mode_separate)
        color_theme_mode_layout.addStretch()
        color_theme_mode_container = QWidget()
        color_theme_mode_container.setLayout(color_theme_mode_layout)
        color_theme_mode_container.setContentsMargins(15, 5, 0, 5)
        color_layout.insertWidget(0, color_theme_mode_container)

        # Set initial visibility based on theme mode
        self._update_overview_bg_color_theme_mode_visibility()

        # Connect theme mode signals for color selection
        self.overview_bg_color_theme_mode_single.toggled.connect(self._update_overview_bg_color_theme_mode_visibility)
        self.overview_bg_color_theme_mode_separate.toggled.connect(self._update_overview_bg_color_theme_mode_visibility)

        layout.addWidget(self.overview_bg_color_group)

        # Image galleries (only for Image mode)
        self.overview_bg_image_group = QWidget()
        image_layout = QVBoxLayout(self.overview_bg_image_group)
        image_layout.setContentsMargins(0, 10, 0, 0)

        # Add theme mode toggle for image selection
        self.overview_bg_image_theme_mode_group = QButtonGroup()
        self.overview_bg_image_theme_mode_single = QRadioButton("Use same image for both themes")
        self.overview_bg_image_theme_mode_separate = QRadioButton("Use different images for light/dark themes")
        self.overview_bg_image_theme_mode_group.addButton(self.overview_bg_image_theme_mode_single)
        self.overview_bg_image_theme_mode_group.addButton(self.overview_bg_image_theme_mode_separate)

        # Load saved theme mode or default to single
        # Load saved theme mode or default to single
        overview_bg_image_theme_mode = conf.get("onigiri_overview_bg_image_theme_mode", "single")
        self.overview_bg_image_theme_mode_single.setChecked(overview_bg_image_theme_mode == "single")
        self.overview_bg_image_theme_mode_separate.setChecked(overview_bg_image_theme_mode == "separate")

        image_theme_mode_layout = QHBoxLayout()
        image_theme_mode_layout.addWidget(self.overview_bg_image_theme_mode_single)
        image_theme_mode_layout.addWidget(self.overview_bg_image_theme_mode_separate)
        image_theme_mode_layout.addStretch()
        image_theme_mode_container = QWidget()
        image_theme_mode_container.setLayout(image_theme_mode_layout)
        image_theme_mode_container.setContentsMargins(15, 5, 0, 5)
        image_layout.addWidget(image_theme_mode_container)

        # Single image container
        self.overview_bg_single_image_container = QWidget()
        single_image_layout = QVBoxLayout(self.overview_bg_single_image_container)
        single_image_layout.setContentsMargins(0, 10, 0, 0)
        self.galleries["overview_bg_single"] = {}
        single_image_layout.addWidget(self._create_image_gallery_group(
            "overview_bg_single", "user_files/main_bg", "onigiri_overview_bg_image", 
            title="Background Image", is_sub_group=True
        ))

        # Separate images container
        self.overview_bg_separate_images_container = QWidget()
        sep_layout = QHBoxLayout(self.overview_bg_separate_images_container)
        sep_layout.setContentsMargins(0, 10, 0, 0)
        self.galleries["overview_bg_light"] = {}
        sep_layout.addWidget(self._create_image_gallery_group(
            "overview_bg_light", "user_files/main_bg", "onigiri_overview_bg_image_light", 
            title="Light Mode Background", is_sub_group=True
        ))
        self.galleries["overview_bg_dark"] = {}
        sep_layout.addWidget(self._create_image_gallery_group(
            "overview_bg_dark", "user_files/main_bg", "onigiri_overview_bg_image_dark", 
            title="Dark Mode Background", is_sub_group=True
        ))

        # Add both containers to the layout
        image_layout.addWidget(self.overview_bg_single_image_container)
        image_layout.addWidget(self.overview_bg_separate_images_container)

        # Set initial visibility based on theme mode
        self._update_overview_bg_image_theme_mode_visibility()

        # Connect theme mode signals for image selection
        self.overview_bg_image_theme_mode_single.toggled.connect(self._update_overview_bg_image_theme_mode_visibility)
        self.overview_bg_image_theme_mode_separate.toggled.connect(self._update_overview_bg_image_theme_mode_visibility)

        layout.addWidget(self.overview_bg_image_group)

        # Effects (blur and opacity)
        self.overview_bg_effects_container = QWidget()
        effects_layout = QHBoxLayout(self.overview_bg_effects_container)
        effects_layout.setContentsMargins(0, 10, 0, 0)

        self.overview_bg_blur_label = QLabel("Blur:")
        self.overview_bg_blur_spinbox = QSpinBox()
        self.overview_bg_blur_spinbox.setMinimum(0)
        self.overview_bg_blur_spinbox.setMaximum(100)
        self.overview_bg_blur_spinbox.setSuffix(" %")
        self.overview_bg_blur_spinbox.setValue(conf.get("onigiri_overview_bg_blur", 0))

        self.overview_bg_opacity_label = QLabel("Opacity:")
        self.overview_bg_opacity_spinbox = QSpinBox()
        self.overview_bg_opacity_spinbox.setMinimum(0)
        self.overview_bg_opacity_spinbox.setMaximum(100)
        self.overview_bg_opacity_spinbox.setSuffix(" %")
        self.overview_bg_opacity_spinbox.setValue(conf.get("onigiri_overview_bg_opacity", 100))

        effects_layout.addWidget(self.overview_bg_blur_label)
        effects_layout.addWidget(self.overview_bg_blur_spinbox)
        effects_layout.addSpacing(20)
        effects_layout.addWidget(self.overview_bg_opacity_label)
        effects_layout.addWidget(self.overview_bg_opacity_spinbox)
        effects_layout.addStretch()
        layout.addWidget(self.overview_bg_effects_container)

        # Initially hide image options (only show for Image mode)
        self.overview_bg_image_group.setVisible(False)

        return widget


    def _update_overview_bg_color_theme_mode_visibility(self):
        """Update visibility of single/separate color pickers for overview background based on theme mode selection."""
        is_single = self.overview_bg_color_theme_mode_single.isChecked()
        self.overview_bg_single_color_container.setVisible(is_single)
        self.overview_bg_separate_colors_container.setVisible(not is_single)

        # If switching to single theme mode, update the single color picker with light mode color
        if is_single and hasattr(self, 'overview_bg_light_color_row'):
            light_color = self.overview_bg_light_color_row.itemAt(1).widget().text()
            self.overview_bg_single_color_row.itemAt(1).widget().setText(light_color)


    def _update_overview_bg_image_theme_mode_visibility(self):
        """Update visibility of single/separate image galleries for overview background based on theme mode selection."""
        is_single = self.overview_bg_image_theme_mode_single.isChecked()
        self.overview_bg_single_image_container.setVisible(is_single)
        self.overview_bg_separate_images_container.setVisible(not is_single)

        # If switching to single theme mode, update the single gallery with light mode image
        if is_single and 'overview_bg_light' in self.galleries and 'overview_bg_single' in self.galleries:
            light_image = self.galleries['overview_bg_light'].get('selected', '')
            if light_image and 'path_input' in self.galleries['overview_bg_single']:
                self.galleries['overview_bg_single']['selected'] = light_image
                self.galleries['overview_bg_single']['path_input'].setText(light_image)


    def _toggle_overview_bg_options(self):
        """Toggle visibility of overview background options based on selected mode."""
        is_main = self.overview_bg_main_radio.isChecked()
        self.overview_bg_main_group.setVisible(is_main)
        self.overview_bg_custom_group.setVisible(not is_main)

        # Control visibility of color and image options within custom group
        if not is_main:
            is_color = self.overview_bg_color_radio.isChecked()
            is_image_color = self.overview_bg_image_color_radio.isChecked()

            # Show color options for both 'Solid Color' and 'Image'
            self.overview_bg_color_group.setVisible(is_color or is_image_color)

            # Show image options and effects only for 'Image'
            self.overview_bg_image_group.setVisible(is_image_color)
            self.overview_bg_effects_container.setVisible(is_image_color)

            # If this is the first time showing the color group, ensure theme mode visibility is set
            if (is_color or is_image_color) and hasattr(self, 'overview_bg_color_theme_mode_single'):
                self._update_overview_bg_color_theme_mode_visibility()

            # If this is the first time showing the image group, ensure theme mode visibility is set
            if is_image_color and hasattr(self, 'overview_bg_image_theme_mode_single'):
                self._update_overview_bg_image_theme_mode_visibility()


    def _save_overviews_settings(self):
        # --- NEW: Save the selected overview style ---
        if self.overview_mini_radio.isChecked():
            mw.col.conf["onigiri_overview_style"] = "mini"
        else:
            mw.col.conf["onigiri_overview_style"] = "pro"
        # --- END NEW ---

        # --- Overviewer Background ---
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
        self.current_config["congratsMessage"] = self.congrats_message_input.text()
        mw.col.conf["modern_menu_studyNowText"] = self.study_now_input.text()

        overview_color_keys = [
            "--button-primary-bg", "--button-primary-gradient-start", "--button-primary-gradient-end",
            "--new-count-bubble-bg", "--new-count-bubble-fg", "--learn-count-bubble-bg",
            "--learn-count-bubble-fg", "--review-count-bubble-bg", "--review-count-bubble-fg"
        ]
        for mode in ["light", "dark"]:
            for key in overview_color_keys:
                if key in self.color_widgets[mode]:
                    widget = self.color_widgets[mode][key]
                    self.current_config["colors"][mode][key] = widget.text()


