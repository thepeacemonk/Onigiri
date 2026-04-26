class MainMenuPageMixin:
    def create_main_menu_page(self):
        page, layout = self._create_scrollable_page()

        # <<< START NEW CODE >>>

        organize_section = SectionGroup(
            "Organize", 
            self, 
            border=False, 
            description="Here you can edit the title of the stats grid, drag and drop to reorder Onigiri's widgets, and organize components from other add-ons into the grid. Right-click on a widget to resize or archive it."
        )

        # Add the stats title input to this section
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form_layout.setContentsMargins(15, 0, 15, 10) # Add some padding
        form_layout.addRow("Custom Stats Title:", self.stats_title_input)

        # Heatmap Default View - Modern Segmented Control
        self.heatmap_view_group = QButtonGroup(self)
        self.heatmap_view_group.setExclusive(True)

        view_container = QWidget()
        view_layout = QHBoxLayout(view_container)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(10)

        current_view = self.current_config.get("heatmapDefaultView", "year")

        for view_option in ["Year", "Month", "Week"]:
            btn = QPushButton(view_option)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.setProperty("view_mode", view_option.lower())

            # Modern styling mimicking a segmented control
            # Note: We use dynamic properties or just check state in styling if needed, 
            # but here we'll use a direct stylesheet for simplicity and consistency with the add-on's theme.
            # Using specific object name to target with stylesheet if possible, or inline styles.
            if theme_manager.night_mode:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #3a3a3a;
                        border: 1px solid #555;
                        border-radius: 6px;
                        color: #eee;
                        padding: 0 15px;
                        font-weight: normal;
                    }}
                    QPushButton:checked {{
                        background-color: {self.accent_color};
                        border: 1px solid {self.accent_color};
                        color: white;
                        font-weight: bold;
                    }}
                    QPushButton:hover:!checked {{
                        background-color: #454545;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #f5f5f5;
                        border: 1px solid #dcdcdc;
                        border-radius: 6px;
                        color: #333;
                        padding: 0 15px;
                        font-weight: normal;
                    }}
                    QPushButton:checked {{
                        background-color: {self.accent_color};
                        border: 1px solid {self.accent_color};
                        color: white;
                        font-weight: bold;
                    }}
                    QPushButton:hover:!checked {{
                        background-color: #e0e0e0;
                    }}
                """)

            if view_option.lower() == current_view:
                btn.setChecked(True)

            self.heatmap_view_group.addButton(btn)
            view_layout.addWidget(btn)

        view_layout.addStretch()
        form_layout.addRow("Default View:", view_container)

        organize_section.add_layout(form_layout)

        # Create and add the layout editor widget
        self.organize_widget_container = self._create_organize_layout_widget()
        organize_section.add_widget(self.organize_widget_container)
        layout.addWidget(organize_section)

        # --- Main Background Section ---
        user_files_path = os.path.join(self.addon_path, "user_files", "main_bg")
        os.makedirs(user_files_path, exist_ok=True)
        try:
            cached_user_files = sorted([f for f in os.listdir(user_files_path) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))])
        except OSError:
            cached_user_files = []

        mode_group, mode_layout_content = self._create_inner_group("Main Background")
        mode = mw.col.conf.get("modern_menu_background_mode", "color")
        # Fallback for users who have the old "image" mode saved
        if mode == "image":
            mode = "image_color"

        # Main mode selection
        mode_layout = QHBoxLayout()
        self.color_radio = QRadioButton("Solid Color")
        self.image_color_radio = QRadioButton("Image")
        self.slideshow_radio = QRadioButton("Slideshow")

        # Check the appropriate radio button
        # "Solid Color" covers both "color" and "accent" modes now
        self.color_radio.setChecked(mode == "color" or mode == "accent")
        self.image_color_radio.setChecked(mode == "image_color")
        self.slideshow_radio.setChecked(mode == "slideshow")

        mode_layout.addWidget(self.color_radio)
        mode_layout.addWidget(self.image_color_radio)
        mode_layout.addWidget(self.slideshow_radio)
        mode_layout.addStretch()
        mode_layout_content.addLayout(mode_layout)

        # --- Options Containers (Flat Layout) ---

        # 1. Color Options (Shared by Color and Image modes)
        self.main_bg_color_group = QWidget()
        main_bg_color_layout = QVBoxLayout(self.main_bg_color_group)
        main_bg_color_layout.setContentsMargins(15, 10, 0, 0)

        # Theme Mode Toggle for Colors
        self.color_theme_group = QButtonGroup()
        self.color_theme_single_radio = QRadioButton("One theme color")
        self.color_theme_separate_radio = QRadioButton("Different colors for light/dark themes")
        self.color_theme_accent_radio = QRadioButton("Accent Color") # New option

        self.color_theme_group.addButton(self.color_theme_single_radio)
        self.color_theme_group.addButton(self.color_theme_separate_radio)
        self.color_theme_group.addButton(self.color_theme_accent_radio)

        # Load saved preference for color theme mode
        # If mode is 'accent', check the accent radio
        if mode == "accent":
            self.color_theme_accent_radio.setChecked(True)
        else:
            color_theme_mode = mw.col.conf.get("modern_menu_bg_color_theme_mode", "single")
            self.color_theme_single_radio.setChecked(color_theme_mode == "single")
            self.color_theme_separate_radio.setChecked(color_theme_mode == "separate")
            # Fallback if somehow neither is checked (though defaults handle this)
            if not self.color_theme_single_radio.isChecked() and not self.color_theme_separate_radio.isChecked():
                 self.color_theme_single_radio.setChecked(True)

        color_theme_layout = QHBoxLayout()
        color_theme_layout.addWidget(self.color_theme_single_radio)
        color_theme_layout.addWidget(self.color_theme_separate_radio)
        color_theme_layout.addWidget(self.color_theme_accent_radio)
        color_theme_layout.addStretch()
        main_bg_color_layout.addLayout(color_theme_layout)

        current_light_bg = self.current_config.get("colors", {}).get("light", {}).get("--bg", "#FFFFFF")
        current_dark_bg = self.current_config.get("colors", {}).get("dark", {}).get("--bg", "#2C2C2C")

        # Single Color Container
        self.bg_color_single_container = QWidget()
        bg_color_single_layout = QVBoxLayout(self.bg_color_single_container)
        bg_color_single_layout.setContentsMargins(0, 0, 0, 0)
        self.bg_single_row = self._create_color_picker_row("Background Color", current_light_bg, "bg_single")
        bg_color_single_layout.addLayout(self.bg_single_row)
        main_bg_color_layout.addWidget(self.bg_color_single_container)

        # Separate Colors Container
        self.bg_color_separate_container = QWidget()
        bg_color_separate_layout = QVBoxLayout(self.bg_color_separate_container)
        bg_color_separate_layout.setContentsMargins(0, 0, 0, 0)
        self.bg_light_row = self._create_color_picker_row("Background (Light Mode)", current_light_bg, "bg_light")
        self.bg_dark_row = self._create_color_picker_row("Background (Dark Mode)", current_dark_bg, "bg_dark")
        bg_color_separate_layout.addLayout(self.bg_light_row)
        bg_color_separate_layout.addLayout(self.bg_dark_row)
        main_bg_color_layout.addWidget(self.bg_color_separate_container)

        mode_layout_content.addWidget(self.main_bg_color_group)

        # Connect color theme toggle
        self.color_theme_single_radio.toggled.connect(self._update_color_theme_visibility)
        self.color_theme_separate_radio.toggled.connect(self._update_color_theme_visibility)
        self.color_theme_accent_radio.toggled.connect(self._update_color_theme_visibility)
        self._update_color_theme_visibility() # Initial state

        # 2. Image Options
        self.main_bg_image_group = QWidget()
        main_bg_image_layout = QVBoxLayout(self.main_bg_image_group)
        main_bg_image_layout.setContentsMargins(15, 10, 0, 0)

        # Theme Mode Toggle for Images
        self.image_theme_group = QButtonGroup()
        self.image_theme_single_radio = QRadioButton("One image")
        self.image_theme_separate_radio = QRadioButton("Different images for light/dark themes")
        self.image_theme_group.addButton(self.image_theme_single_radio)
        self.image_theme_group.addButton(self.image_theme_separate_radio)

        # Load saved preference for image theme mode
        image_theme_mode = mw.col.conf.get("modern_menu_bg_image_theme_mode", "single")
        self.image_theme_single_radio.setChecked(image_theme_mode == "single")
        self.image_theme_separate_radio.setChecked(image_theme_mode == "separate")

        image_theme_layout = QHBoxLayout()
        image_theme_layout.addWidget(self.image_theme_single_radio)
        image_theme_layout.addWidget(self.image_theme_separate_radio)
        image_theme_layout.addStretch()
        main_bg_image_layout.addLayout(image_theme_layout)

        # Single Image Container
        self.bg_image_single_container = QWidget()
        bg_image_single_layout = QVBoxLayout(self.bg_image_single_container)
        bg_image_single_layout.setContentsMargins(0, 0, 0, 0)
        self.galleries["main_single"] = {}
        bg_image_single_layout.addWidget(self._create_image_gallery_group("main_single", "user_files/main_bg", "modern_menu_background_image", title="Background Image", image_files_cache=cached_user_files))
        main_bg_image_layout.addWidget(self.bg_image_single_container)

        # Separate Images Container (Side-by-Side)
        self.bg_image_separate_container = QWidget()
        bg_image_separate_layout = QHBoxLayout(self.bg_image_separate_container)
        bg_image_separate_layout.setContentsMargins(0, 0, 0, 0)
        bg_image_separate_layout.setSpacing(15)

        self.galleries["main_light"] = {}
        bg_image_separate_layout.addWidget(self._create_image_gallery_group("main_light", "user_files/main_bg", "modern_menu_background_image_light", title="Light Mode Background", image_files_cache=cached_user_files))

        self.galleries["main_dark"] = {}
        bg_image_separate_layout.addWidget(self._create_image_gallery_group("main_dark", "user_files/main_bg", "modern_menu_background_image_dark", title="Dark Mode Background", image_files_cache=cached_user_files))

        main_bg_image_layout.addWidget(self.bg_image_separate_container)

        # Connect image theme toggle
        self.image_theme_single_radio.toggled.connect(self._update_image_theme_visibility)
        self.image_theme_separate_radio.toggled.connect(self._update_image_theme_visibility)
        self._update_image_theme_visibility() # Initial state

        # Effects
        effects_layout = QHBoxLayout()
        self.bg_blur_label = QLabel("Background Blur:")
        self.bg_blur_spinbox = QSpinBox()
        self.bg_blur_spinbox.setMinimum(0)
        self.bg_blur_spinbox.setMaximum(100)
        self.bg_blur_spinbox.setSuffix(" %")
        self.bg_blur_spinbox.setValue(mw.col.conf.get("modern_menu_background_blur", 0))
        effects_layout.addWidget(self.bg_blur_label)
        effects_layout.addWidget(self.bg_blur_spinbox)

        self.bg_opacity_label = QLabel("Background Opacity:")
        self.bg_opacity_spinbox = QSpinBox()
        self.bg_opacity_spinbox.setMinimum(0)
        self.bg_opacity_spinbox.setMaximum(100)
        self.bg_opacity_spinbox.setSuffix(" %")
        self.bg_opacity_spinbox.setValue(mw.col.conf.get("modern_menu_background_opacity", 100))
        effects_layout.addWidget(self.bg_opacity_label)
        effects_layout.addWidget(self.bg_opacity_spinbox)
        effects_layout.addStretch()
        main_bg_image_layout.addLayout(effects_layout)

        mode_layout_content.addWidget(self.main_bg_image_group)

        # 3. Slideshow Options
        self.main_bg_slideshow_group = QWidget()
        slideshow_layout = QVBoxLayout(self.main_bg_slideshow_group)
        slideshow_layout.setContentsMargins(15, 10, 0, 0)

        interval_layout = QHBoxLayout()
        interval_label = QLabel("Change image every:")
        self.slideshow_interval_spinbox = QSpinBox()
        self.slideshow_interval_spinbox.setMinimum(1)
        self.slideshow_interval_spinbox.setMaximum(3600)
        self.slideshow_interval_spinbox.setSuffix(" seconds")
        self.slideshow_interval_spinbox.setValue(mw.col.conf.get("modern_menu_slideshow_interval", 10))
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.slideshow_interval_spinbox)
        interval_layout.addStretch()
        slideshow_layout.addLayout(interval_layout)

        self.slideshow_images_widget = self._create_slideshow_images_selector(cached_user_files)
        slideshow_layout.addWidget(self.slideshow_images_widget)

        mode_layout_content.addWidget(self.main_bg_slideshow_group)

        layout.addWidget(mode_group)

        # Connect signals
        self.color_radio.toggled.connect(self.toggle_background_options)
        self.image_color_radio.toggled.connect(self.toggle_background_options)
        self.slideshow_radio.toggled.connect(self.toggle_background_options)

        # Initial state
        self.toggle_background_options()

        reset_bg_button = QPushButton("Reset Background to Default")
        reset_bg_button.clicked.connect(self.reset_background_to_default)
        layout.addWidget(reset_bg_button)




        # <<< END NEW CODE >>>

        heatmap_section = SectionGroup(
            "Heatmap", 
            self, 
            border=False,
            description="Here you can edit the shape of each day on the heatmap and change its color."
        )

        shape_section, shape_layout = self._create_inner_group("Shape")
        shape_selector = self._create_shape_selector()
        shape_layout.addWidget(shape_selector)
        heatmap_section.add_widget(shape_section)

        visibility_section, visibility_layout = self._create_inner_group("Visibility")
        self.heatmap_show_streak_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_streak_check.setChecked(self.current_config.get("heatmapShowStreak", True))
        visibility_layout.addWidget(self._create_toggle_row(self.heatmap_show_streak_check, "Show review streak counter"))
        self.heatmap_show_months_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_months_check.setChecked(self.current_config.get("heatmapShowMonths", True))
        visibility_layout.addWidget(self._create_toggle_row(self.heatmap_show_months_check, "Show month labels (Year view)"))
        self.heatmap_show_weekdays_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_weekdays_check.setChecked(self.current_config.get("heatmapShowWeekdays", True))
        visibility_layout.addWidget(self._create_toggle_row(self.heatmap_show_weekdays_check, "Show weekday labels (Year & Month view)"))
        self.heatmap_show_week_header_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.heatmap_show_week_header_check.setChecked(self.current_config.get("heatmapShowWeekHeader", True))
        visibility_layout.addWidget(self._create_toggle_row(self.heatmap_show_week_header_check, "Show day labels (Week view)"))
        heatmap_section.add_widget(visibility_section)

        heatmap_color_modes_layout = QHBoxLayout()
        light_heatmap_group, light_heatmap_layout = self._create_inner_group("Light Mode")
        light_heatmap_layout.setSpacing(5)
        self._populate_pills_for_keys(light_heatmap_layout, "light", ["--heatmap-color", "--heatmap-color-zero"])
        heatmap_color_modes_layout.addWidget(light_heatmap_group)

        dark_heatmap_group, dark_heatmap_layout = self._create_inner_group("Dark Mode")
        dark_heatmap_layout.setSpacing(5)
        self._populate_pills_for_keys(dark_heatmap_layout, "dark", ["--heatmap-color", "--heatmap-color-zero"])
        heatmap_color_modes_layout.addWidget(dark_heatmap_group)
        heatmap_section.add_layout(heatmap_color_modes_layout)

        # Reset Heatmap Colors button
        reset_heatmap_layout = QHBoxLayout()
        reset_heatmap_layout.addStretch()
        reset_heatmap_button = QPushButton("Reset Heatmap Colors")
        reset_heatmap_button.clicked.connect(self.reset_heatmap_colors_to_default)
        reset_heatmap_layout.addWidget(reset_heatmap_button)
        heatmap_section.add_layout(reset_heatmap_layout)

        layout.addWidget(heatmap_section)

        divider2 = QFrame()
        divider2.setFrameShape(QFrame.Shape.HLine)
        divider2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider2)

        star_icon_section = SectionGroup(
            "Star Icon", 
            self, 
            border=False,
            description="Here you can change the star icon and its colors."
        )
        if self.retention_star_widget is None:
            self.retention_star_widget = self._create_icon_control_widget("retention_star")
        star_icon_section.add_widget(self.retention_star_widget)

        self.hide_retention_stars_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_retention_stars_check.setChecked(self.current_config.get("hideRetentionStars", False))
        star_icon_section.add_widget(self._create_toggle_row(self.hide_retention_stars_check, "Hide stars on Retention widget"))

        star_color_modes_layout = QHBoxLayout()
        light_star_group, light_star_layout = self._create_inner_group("Light Mode")
        light_star_layout.setSpacing(5)
        self._populate_pills_for_keys(light_star_layout, "light", ["--star-color", "--empty-star-color"])
        star_color_modes_layout.addWidget(light_star_group)

        dark_star_group, dark_star_layout = self._create_inner_group("Dark Mode")
        dark_star_layout.setSpacing(5)
        self._populate_pills_for_keys(dark_star_layout, "dark", ["--star-color", "--empty-star-color"])
        star_color_modes_layout.addWidget(dark_star_group)
        star_icon_section.add_layout(star_color_modes_layout)

        layout.addWidget(star_icon_section)

        reset_button = QPushButton("Reset Stats Colors")
        reset_button.clicked.connect(self.reset_stats_colors_to_default)
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        reset_layout.addWidget(reset_button)
        layout.addLayout(reset_layout)

        layout.addStretch()

        # Add navigation buttons
        sections = {
            "Organize": organize_section,
            "Main Background": mode_group,
            "Heatmap": heatmap_section,
            "Star Icon": star_icon_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections)

        return page


    def _create_organize_layout_widget(self):
        # This widget contains the unified layout editor
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # Use the new unified layout editor
        self.unified_layout_editor = UnifiedLayoutEditor(self)
        layout.addWidget(self.unified_layout_editor)

        return container


    def toggle_background_options(self, checked=None): 
        # Prevent flickering by ignoring the signal from the button being unchecked
        if isinstance(self.sender(), QRadioButton) and not self.sender().isChecked():
            return

        # Atomic update for initial visibility state
        self.setUpdatesEnabled(False)
        try:
            is_color = self.color_radio.isChecked()
            is_image = self.image_color_radio.isChecked()
            is_slideshow = self.slideshow_radio.isChecked()

            should_animate_color_group = False

            # Handle Accent Color radio button visibility
            # Show only when "Solid Color" is selected
            if hasattr(self, 'color_theme_accent_radio'):
                self.color_theme_accent_radio.setVisible(is_color)
                # If accent was selected but we're switching to Image/Slideshow, reset to "One theme color"
                if not is_color and self.color_theme_accent_radio.isChecked():
                    self.color_theme_single_radio.setChecked(True)

            # Handle Color Group Visibility
            if hasattr(self, 'main_bg_color_group'):
                should_be_visible = is_color or is_image or is_slideshow
                is_currently_visible = self.main_bg_color_group.isVisible()

                if should_be_visible and not is_currently_visible:
                    # Transitioning from Hidden -> Visible (e.g. Accent -> Color)
                    # Prepare for animation
                    self.main_bg_color_group.setMaximumHeight(0)
                    self.main_bg_color_group.setVisible(True)
                    should_animate_color_group = True
                elif not should_be_visible:
                    self.main_bg_color_group.setVisible(False)
                # If already visible and staying visible, do nothing

            # Handle Image/Slideshow Groups with Animation ("Enlarge First")
            target_widget = None
            start_height = 0

            if hasattr(self, 'main_bg_image_group') and hasattr(self, 'main_bg_slideshow_group'):
                if is_image:
                    target_widget = self.main_bg_image_group
                    if self.main_bg_slideshow_group.isVisible():
                        start_height = self.main_bg_slideshow_group.height()
                elif is_slideshow:
                    target_widget = self.main_bg_slideshow_group
                    if self.main_bg_image_group.isVisible():
                        start_height = self.main_bg_image_group.height()

                # Hide non-selected widgets immediately
                if not is_image:
                    self.main_bg_image_group.setVisible(False)
                if not is_slideshow:
                    self.main_bg_slideshow_group.setVisible(False)

                if target_widget:
                    # If widget is already visible, do nothing (or maybe just ensure it's fully visible)
                    if target_widget.isVisible() and target_widget.maximumHeight() > 0:
                        pass # Already visible
                    else:
                        # Prepare for animation
                        # IMPORTANT: Set max height BEFORE showing to prevent flickering/jumping
                        target_widget.setMaximumHeight(start_height)
                        target_widget.setVisible(True)

                        # Calculate target height based on content
                        # We force the layout to calculate the size hint
                        target_widget.updateGeometry()
        finally:
            self.setUpdatesEnabled(True)

        # Start animations AFTER updates are re-enabled

        # 1. Animate Color Group if needed
        if should_animate_color_group:
            self.main_bg_color_group.updateGeometry()
            color_target_height = self.main_bg_color_group.sizeHint().height()
            if color_target_height < 50: color_target_height = 100

            self.color_group_anim = QPropertyAnimation(self.main_bg_color_group, b"maximumHeight")
            self.color_group_anim.setDuration(300)
            self.color_group_anim.setStartValue(0)
            self.color_group_anim.setEndValue(color_target_height)
            self.color_group_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.color_group_anim.finished.connect(lambda: self.main_bg_color_group.setMaximumHeight(16777215))
            self.color_group_anim.start()

        # 2. Animate Image/Slideshow Group if needed
        if hasattr(self, 'main_bg_image_group') and hasattr(self, 'main_bg_slideshow_group'):
             if target_widget:
                # Check if we need to animate (if max height is restricted or we are switching)
                # If start_height > 0 (switching) or max height is 0 (opening), we animate.
                # If it's already open and fully visible, we might skip, but re-animating is safer to ensure correct state.

                target_height = target_widget.sizeHint().height()
                if target_height < 100: target_height = 500

                # Animate height
                self.anim = QPropertyAnimation(target_widget, b"maximumHeight")
                self.anim.setDuration(300) # 300ms duration
                self.anim.setStartValue(start_height)
                self.anim.setEndValue(target_height)
                self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)

                # On finished, reset maximum height to allow dynamic resizing
                self.anim.finished.connect(lambda: target_widget.setMaximumHeight(16777215))
                self.anim.start()        

    def _update_color_theme_visibility(self):
        """Update visibility of single/separate color pickers with animation."""
        is_single = self.color_theme_single_radio.isChecked()
        is_separate = self.color_theme_separate_radio.isChecked()
        # is_accent = self.color_theme_accent_radio.isChecked() # Implicitly true if neither above is true

        target_widget = None
        if is_single:
            target_widget = self.bg_color_single_container
        elif is_separate:
            target_widget = self.bg_color_separate_container

        # Determine what to hide
        # We must NOT check isVisible() here, because during initialization (before dialog is shown),
        # isVisible() returns False for everything, causing nothing to be added to this list,
        # and thus nothing gets hidden.
        widgets_to_hide = []
        if self.bg_color_single_container is not target_widget:
            widgets_to_hide.append(self.bg_color_single_container)
        if self.bg_color_separate_container is not target_widget:
            widgets_to_hide.append(self.bg_color_separate_container)

        # Optimization: If dialog is not visible (initialization), just set visibility and return.
        # This prevents unnecessary animations and ensures correct initial state.
        if not self.isVisible():
            for w in widgets_to_hide:
                w.setVisible(False)
            if target_widget:
                target_widget.setVisible(True)
                target_widget.setMaximumHeight(16777215)
            return

        # If target is already visible and nothing to hide, we are done
        if target_widget and target_widget.isVisible() and not widgets_to_hide:
            return
        # If no target and nothing to hide (already in accent mode), done
        if not target_widget and not widgets_to_hide:
            return

        # Atomic update to prevent flickering
        self.setUpdatesEnabled(False)
        start_height = 0
        try:
            # Hide unwanted widgets and capture height
            for w in widgets_to_hide:
                if w.isVisible():
                    start_height = max(start_height, w.height())
                w.setVisible(False)

            if target_widget:
                # Prepare target widget
                # IMPORTANT: Set max height BEFORE showing to prevent flickering/jumping
                target_widget.setMaximumHeight(start_height)
                target_widget.setVisible(True)
                target_widget.updateGeometry()

                # Calculate target height
                target_height = target_widget.sizeHint().height()
                if target_height < 50: target_height = 100 # Fallback
        finally:
            self.setUpdatesEnabled(True)

        if target_widget:
            self.color_anim = QPropertyAnimation(target_widget, b"maximumHeight")
            self.color_anim.setDuration(250)
            self.color_anim.setStartValue(start_height)
            self.color_anim.setEndValue(target_height)
            self.color_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.color_anim.finished.connect(lambda: target_widget.setMaximumHeight(16777215))
            self.color_anim.start()


    def _update_image_theme_visibility(self):
        """Update visibility of single/separate image galleries with animation."""
        is_single = self.image_theme_single_radio.isChecked()
        target_widget = self.bg_image_single_container if is_single else self.bg_image_separate_container
        other_widget = self.bg_image_separate_container if is_single else self.bg_image_single_container

        if target_widget.isVisible():
            return

        # Atomic update to prevent flickering
        self.setUpdatesEnabled(False)
        try:
            # Capture start height from the currently visible widget
            start_height = other_widget.height() if other_widget.isVisible() else 0
            other_widget.setVisible(False)

            # Prepare target widget
            # IMPORTANT: Set max height BEFORE showing to prevent flickering/jumping
            target_widget.setMaximumHeight(start_height)
            target_widget.setVisible(True)
            target_widget.updateGeometry()

            target_height = target_widget.sizeHint().height()
            if target_height < 100: target_height = 300 # Fallback
        finally:
            self.setUpdatesEnabled(True)

        self.image_anim = QPropertyAnimation(target_widget, b"maximumHeight")
        self.image_anim.setDuration(250)
        self.image_anim.setStartValue(start_height)
        self.image_anim.setEndValue(target_height)
        self.image_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.image_anim.finished.connect(lambda: target_widget.setMaximumHeight(16777215))
        self.image_anim.start()


    def reset_background_to_default(self):
        self.color_radio.setChecked(True)
        if hasattr(self, 'bg_single_color_input'):
             self.bg_single_color_input.setText(DEFAULTS["colors"]["light"]["--bg"])
        self.bg_light_color_input.setText(DEFAULTS["colors"]["light"]["--bg"])
        self.bg_dark_color_input.setText(DEFAULTS["colors"]["dark"]["--bg"])

        for key in ['main_single', 'main_light', 'main_dark']:
            if key in self.galleries:
                self.galleries[key]['selected'] = ""
                if self.galleries[key].get('path_input'): 
                    self.galleries[key]['path_input'].setText("")
                self._refresh_gallery(key)

        self.bg_blur_spinbox.setValue(0)
        self.bg_opacity_spinbox.setValue(100)


    def _on_hide_all_stats_toggled(self, checked):
        self.hide_studied_stat_checkbox.setChecked(checked)
        self.hide_time_stat_checkbox.setChecked(checked)
        self.hide_pace_stat_checkbox.setChecked(checked)
        self.hide_retention_stat_checkbox.setChecked(checked)


    def _save_main_menu_settings(self):
        mw.col.conf["modern_menu_statsTitle"] = self.stats_title_input.text()

        # Save Heatmap Default View
        if hasattr(self, "heatmap_view_group"):
            checked_btn = self.heatmap_view_group.checkedButton()
            if checked_btn:
                self.current_config["heatmapDefaultView"] = checked_btn.property("view_mode")

        if hasattr(self, "selected_heatmap_shape"):
            self.current_config["heatmapShape"] = self.selected_heatmap_shape

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

        # Save the background mode (color/image_color/accent/slideshow)
        # Save the background mode (color/image_color/accent/slideshow)
        if self.image_color_radio.isChecked():
            mw.col.conf["modern_menu_background_mode"] = "image_color"
        elif self.slideshow_radio.isChecked():
            mw.col.conf["modern_menu_background_mode"] = "slideshow"
        else:
            # Solid Color is checked
            if self.color_theme_accent_radio.isChecked():
                mw.col.conf["modern_menu_background_mode"] = "accent"
            else:
                mw.col.conf["modern_menu_background_mode"] = "color"

        # Save slideshow settings
        if self.slideshow_radio.isChecked():
            # Save interval
            mw.col.conf["modern_menu_slideshow_interval"] = self.slideshow_interval_spinbox.value()

            # Save selected images
            selected_images = [item.img_filename for item in self.slideshow_image_items if item.is_checked]
            mw.col.conf["modern_menu_slideshow_images"] = selected_images

        # Save Color Theme Mode
        color_theme_mode = "single" if self.color_theme_single_radio.isChecked() else "separate"
        mw.col.conf["modern_menu_bg_color_theme_mode"] = color_theme_mode

        # Save Colors
        if color_theme_mode == "single":
            # In single mode, use the single color for both themes
            single_color = self.bg_single_row.itemAt(1).widget().text()
            mw.col.conf["modern_menu_bg_color_light"] = single_color
            mw.col.conf["modern_menu_bg_color_dark"] = single_color
            # Also update the config for immediate use
            self.current_config["colors"]["light"]["--bg"] = single_color
            self.current_config["colors"]["dark"]["--bg"] = single_color
        else:
            # In separate mode, use the individual colors
            light_bg_val = self.bg_light_row.itemAt(1).widget().text()
            dark_bg_val = self.bg_dark_row.itemAt(1).widget().text()
            mw.col.conf["modern_menu_bg_color_light"] = light_bg_val
            mw.col.conf["modern_menu_bg_color_dark"] = dark_bg_val
            # Also update the config for immediate use
            self.current_config["colors"]["light"]["--bg"] = light_bg_val
            self.current_config["colors"]["dark"]["--bg"] = dark_bg_val

        # Save Image Theme Mode
        image_theme_mode = "single" if self.image_theme_single_radio.isChecked() else "separate"
        mw.col.conf["modern_menu_bg_image_theme_mode"] = image_theme_mode

        # Save Images
        if image_theme_mode == "single" and 'main_single' in self.galleries:
            # In single mode, use the single image for both themes
            single_image = self.galleries['main_single'].get('selected', '')
            mw.col.conf["modern_menu_background_image"] = single_image
            mw.col.conf["modern_menu_background_image_light"] = single_image
            mw.col.conf["modern_menu_background_image_dark"] = single_image
        else:
            # In separate mode, use the individual images
            if 'main_light' in self.galleries:
                mw.col.conf["modern_menu_background_image_light"] = self.galleries['main_light'].get('selected', '')
            if 'main_dark' in self.galleries:
                mw.col.conf["modern_menu_background_image_dark"] = self.galleries['main_dark'].get('selected', '')

        mw.col.conf["modern_menu_background_blur"] = self.bg_blur_spinbox.value()
        mw.col.conf["modern_menu_background_opacity"] = self.bg_opacity_spinbox.value()


    def _save_organize_settings(self):
        """Saves the layout from the unified layout editor."""
        if hasattr(self, 'unified_layout_editor'):
            layout_config = self.unified_layout_editor.get_layout_config()
            self.current_config['onigiriWidgetLayout'] = layout_config['onigiri']
            self.current_config['externalWidgetLayout'] = layout_config['external']
            # Save the row count setting
            self.current_config['unifiedGridRows'] = self.unified_layout_editor.row_spin.value()


