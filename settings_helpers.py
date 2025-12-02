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
        overview_bg_color_theme_mode = mw.col.conf.get("onigiri_overview_bg_color_theme_mode", "single")
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
        overview_bg_image_theme_mode = mw.col.conf.get("onigiri_overview_bg_image_theme_mode", "single")
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
