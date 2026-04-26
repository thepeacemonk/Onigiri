class SidebarPageMixin:
    def create_sidebar_page(self):
        page, layout = self._create_scrollable_page()
        sidebar_section = SectionGroup(
            "Sidebar Customization", 
            self, 
            border=False,
            description="Customize general visibility options for the sidebar."
        )

        sidebar_section.add_widget(self._create_toggle_row(self.hide_welcome_checkbox, "Hide 'Welcome' message"))
        sidebar_section.add_widget(self._create_toggle_row(self.hide_deck_counts_checkbox, "Hide 0 counts on sidebar"))
        sidebar_section.add_widget(self._create_toggle_row(self.hide_all_deck_counts_checkbox, "Hide deck counts entirely"))

        layout.addWidget(sidebar_section)



        divider1 = QFrame()
        divider1.setFrameShape(QFrame.Shape.HLine)
        divider1.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider1)

        # --- Sidebar Background Section ---
        sidebar_group, sidebar_layout = self._create_inner_group("Sidebar Background")
        sidebar_mode = mw.col.conf.get("modern_menu_sidebar_bg_mode", "main"); sidebar_mode_layout = QHBoxLayout()
        self.sidebar_bg_main_radio = QRadioButton("Use Main Background Settings"); self.sidebar_bg_custom_radio = QRadioButton("Use Custom Sidebar Background")
        self.sidebar_bg_main_radio.setChecked(sidebar_mode == "main"); self.sidebar_bg_custom_radio.setChecked(sidebar_mode == "custom"); sidebar_mode_layout.addWidget(self.sidebar_bg_main_radio); sidebar_mode_layout.addWidget(self.sidebar_bg_custom_radio); sidebar_layout.addLayout(sidebar_mode_layout)

        self.sidebar_main_options_group = QWidget()
        sidebar_main_layout = QVBoxLayout(self.sidebar_main_options_group)
        sidebar_main_layout.setContentsMargins(15, 10, 0, 0)

        effect_mode = mw.col.conf.get("onigiri_sidebar_main_bg_effect_mode", "opaque")
        effect_mode_layout = QHBoxLayout()
        self.sidebar_effect_overlay_radio = QRadioButton("Color Overlay")
        self.sidebar_effect_glass_radio = QRadioButton("Glassmorphism")
        self.sidebar_effect_overlay_radio.setChecked(effect_mode == "opaque")
        self.sidebar_effect_glass_radio.setChecked(effect_mode == "glassmorphism")
        effect_mode_layout.addWidget(self.sidebar_effect_overlay_radio)
        effect_mode_layout.addWidget(self.sidebar_effect_glass_radio)
        effect_mode_layout.addStretch()
        sidebar_main_layout.addLayout(effect_mode_layout)

        self.sidebar_overlay_options_group = QWidget()
        overlay_options_layout = QVBoxLayout(self.sidebar_overlay_options_group)
        overlay_options_layout.setContentsMargins(0, 5, 0, 0)

        intensity_layout = QHBoxLayout()
        intensity_label = QLabel("Overlay Opacity:")
        self.sidebar_overlay_intensity_spinbox = QSpinBox()
        self.sidebar_overlay_intensity_spinbox.setMinimum(0)
        self.sidebar_overlay_intensity_spinbox.setMaximum(100)
        self.sidebar_overlay_intensity_spinbox.setSuffix(" %")
        self.sidebar_overlay_intensity_spinbox.setValue(mw.col.conf.get("onigiri_sidebar_opaque_tint_intensity", 30))
        intensity_layout.addWidget(intensity_label)
        intensity_layout.addWidget(self.sidebar_overlay_intensity_spinbox)
        intensity_layout.addStretch()


        overlay_options_layout.addLayout(intensity_layout)

        self.sidebar_overlay_light_color_row = self._create_color_picker_row("Overlay Color (Light Mode)", mw.col.conf.get("onigiri_sidebar_opaque_tint_color_light", "#FFFFFF"), "overlay_light_color")
        self.sidebar_overlay_dark_color_row = self._create_color_picker_row("Overlay Color (Dark Mode)", mw.col.conf.get("onigiri_sidebar_opaque_tint_color_dark", "#2C2C2C"), "overlay_dark_color")
        overlay_options_layout.addLayout(self.sidebar_overlay_light_color_row)
        overlay_options_layout.addLayout(self.sidebar_overlay_dark_color_row)
        sidebar_main_layout.addWidget(self.sidebar_overlay_options_group)

        self.sidebar_effect_intensity_group = QWidget()
        glass_intensity_layout = QHBoxLayout(self.sidebar_effect_intensity_group)
        glass_intensity_layout.setContentsMargins(0, 5, 0, 0)
        glass_intensity_label = QLabel("Effect Intensity:")
        self.sidebar_effect_intensity_spinbox = QSpinBox()
        self.sidebar_effect_intensity_spinbox.setMinimum(0)
        self.sidebar_effect_intensity_spinbox.setMaximum(100)
        self.sidebar_effect_intensity_spinbox.setSuffix(" %")
        self.sidebar_effect_intensity_spinbox.setValue(mw.col.conf.get("onigiri_sidebar_main_bg_effect_intensity", 50))
        glass_intensity_layout.addWidget(glass_intensity_label)
        glass_intensity_layout.addWidget(self.sidebar_effect_intensity_spinbox)
        glass_intensity_layout.addStretch()
        sidebar_main_layout.addWidget(self.sidebar_effect_intensity_group)

        self.sidebar_effect_overlay_radio.toggled.connect(self._toggle_sidebar_effect_options)
        self.sidebar_effect_glass_radio.toggled.connect(self._toggle_sidebar_effect_options)
        self._toggle_sidebar_effect_options()

        sidebar_layout.addWidget(self.sidebar_main_options_group)
        self.sidebar_custom_options_group = self.create_sidebar_custom_options()
        sidebar_layout.addWidget(self.sidebar_custom_options_group)

        layout.addWidget(sidebar_group)

        self.sidebar_bg_main_radio.toggled.connect(self.toggle_sidebar_background_options)
        self.toggle_sidebar_background_options()

        reset_sidebar_button = QPushButton("Reset Sidebar to Default")
        reset_sidebar_button.clicked.connect(self.reset_sidebar_to_default)
        layout.addWidget(reset_sidebar_button)



        # --- Organize Action Buttons (merged section) ---
        action_buttons_section = SectionGroup(
            "Organize Action Buttons",
            self,
            border=False,
            description="Choose how action buttons are displayed and customize their icons."
        )

        # --- Format radio buttons ---
        mode_layout = QHBoxLayout()
        self.actions_mode_group = QButtonGroup(action_buttons_section)

        self.actions_mode_list = QRadioButton("List (Default)")
        self.actions_mode_list.setToolTip("Show action buttons as list items in the sidebar.")

        self.actions_mode_collapsed = QRadioButton("Collapsed (Toolbar)")
        self.actions_mode_collapsed.setToolTip("Show action buttons as icons in the top toolbar.")

        self.actions_mode_archived = QRadioButton("Archived (Hidden)")
        self.actions_mode_archived.setToolTip("Hide action buttons completely.")

        self.actions_mode_group.addButton(self.actions_mode_list)
        self.actions_mode_group.addButton(self.actions_mode_collapsed)
        self.actions_mode_group.addButton(self.actions_mode_archived)

        # Load config
        current_mode = self.current_config.get("sidebarActionsMode", "list")
        if current_mode == "collapsed":
             self.actions_mode_collapsed.setChecked(True)
        elif current_mode == "archived":
             self.actions_mode_archived.setChecked(True)
        else:
             self.actions_mode_list.setChecked(True)

        mode_layout.addWidget(self.actions_mode_list)
        mode_layout.addWidget(self.actions_mode_collapsed)
        mode_layout.addWidget(self.actions_mode_archived)
        mode_layout.addStretch()

        action_buttons_section.add_layout(mode_layout)

        mode_help = QLabel("Choose how action buttons (Add, Browse, Stats, Sync) are displayed.")
        if theme_manager.night_mode:
            mode_help.setStyleSheet("color: #b5bdc7; font-size: 11px; margin-bottom: 5px;")
        else:
            mode_help.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        action_buttons_section.add_widget(mode_help)

        # --- Drag-and-drop grids (shown only when List is selected) ---
        self.sidebar_layout_editor_container = QWidget()
        sle_container_layout = QVBoxLayout(self.sidebar_layout_editor_container)
        sle_container_layout.setContentsMargins(0, 5, 0, 5)
        sle_container_layout.setSpacing(5)

        organize_label = QLabel("Drag and drop to re-order or archive sidebar buttons. Changes will apply after restarting Anki.")
        organize_label.setWordWrap(True)
        if theme_manager.night_mode:
            organize_label.setStyleSheet("color: #b5bdc7; font-size: 11px; margin-bottom: 5px;")
        else:
            organize_label.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        sle_container_layout.addWidget(organize_label)

        self.sidebar_layout_editor = SidebarLayoutEditor(self)
        sle_container_layout.addWidget(self.sidebar_layout_editor)

        action_buttons_section.add_widget(self.sidebar_layout_editor_container)

        # Show/hide grids based on mode
        def _update_organize_visibility():
            self.sidebar_layout_editor_container.setVisible(self.actions_mode_list.isChecked())

        self.actions_mode_list.toggled.connect(_update_organize_visibility)
        self.actions_mode_collapsed.toggled.connect(_update_organize_visibility)
        self.actions_mode_archived.toggled.connect(_update_organize_visibility)
        _update_organize_visibility()

        # Add a separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        if theme_manager.night_mode:
            sep.setStyleSheet("background-color: #3a3a3a; margin-bottom: 10px;")
        else:
            sep.setStyleSheet("background-color: #e0e0e0; margin-bottom: 10px;")
        sep.setFixedHeight(1)
        action_buttons_section.add_widget(sep)

        # --- Icon cards (always visible) ---
        icons_label = QLabel("Action Button Icons")
        icons_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        action_buttons_section.add_widget(icons_label)

        action_buttons_layout = QGridLayout()
        action_buttons_layout.setSpacing(15)
        action_buttons_layout.setContentsMargins(0, 5, 0, 5)

        action_icons_to_configure = {
            "add": "Add", "browse": "Browser", "stats": "Stats",
            "sync": "Sync", "settings": "Settings", "gamification": "Onigiri Games", "more": "More",
            "get_shared": "Get Shared", "create_deck": "Create Deck", "import_file": "Import File"
        }
        external_entries = {
            entry_id: entry.label
            for entry_id, entry in sidebar_api.get_sidebar_entries().items()
            if entry_id not in action_icons_to_configure
        }
        for entry_id in sorted(external_entries.keys(), key=lambda k: external_entries[k].lower()):
            action_icons_to_configure[entry_id] = external_entries[entry_id] or entry_id

        row, col, num_cols = 0, 0, 3
        for key, label_text in action_icons_to_configure.items():
            card = QWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(5)
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            control_widget = self._create_icon_control_widget(key, label_text)
            self.action_button_icon_widgets.append(control_widget)
            card_layout.addWidget(label)
            card_layout.addWidget(control_widget)
            action_buttons_layout.addWidget(card, row, col)
            col += 1
            if col >= num_cols:
                col = 0
                row += 1

        action_buttons_section.add_layout(action_buttons_layout)

        layout.addWidget(action_buttons_section)

        divider2 = QFrame()
        divider2.setFrameShape(QFrame.Shape.HLine)
        divider2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider2)

        deck_section = SectionGroup(
            "Deck",
            self,
            border=False,
            description="Customize the deck list appearance."
        )

        indentation_group, indentation_layout_content = self._create_inner_group("Decks Indentation")

        # --- Modern Button Group UI ---
        # Main layout for the indentation section
        indent_main_layout = QVBoxLayout()
        indentation_layout_content.addLayout(indent_main_layout)

        # Create a container for the buttons
        mode_btn_container = QWidget()
        mode_btn_layout = QHBoxLayout(mode_btn_container)
        mode_btn_layout.setContentsMargins(0, 0, 0, 0)
        mode_btn_layout.setSpacing(10)

        self.indentation_mode_group = QButtonGroup(self)
        self.indentation_mode_group.setExclusive(True)

        modes = [
            ("default", "Default"),
            ("smaller", "Smaller"),
            ("bigger", "Bigger"),
            ("custom", "Custom")
        ]

        current_mode = self.current_config.get("deck_indentation_mode", "default")

        for key, label in modes:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("indent_mode", key)

            # Dynamic styling based on theme
            if theme_manager.night_mode:
                border_color = "#555555"
                text_color = "#eeeeee"
                hover_bg = "rgba(255, 255, 255, 0.1)"
            else:
                border_color = "#cccccc"
                text_color = "#333333"
                hover_bg = "rgba(0, 0, 0, 0.05)"

            btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 8px 15px;
                    border: 1px solid {border_color};
                    border-radius: 6px;
                    background-color: transparent;
                    color: {text_color};
                }}
                QPushButton:checked {{
                    background-color: {self.accent_color};
                    color: white;
                    border-color: {self.accent_color};
                }}
                QPushButton:hover:!checked {{
                    background-color: {hover_bg};
                }}
            """)

            if key == current_mode:
                btn.setChecked(True)

            self.indentation_mode_group.addButton(btn)
            mode_btn_layout.addWidget(btn)

        # Add the button row
        indent_main_layout.addWidget(mode_btn_container)

        # Connect signal
        self.indentation_mode_group.buttonClicked.connect(self._on_indentation_mode_btn_clicked)

        # Custom Spinbox Row
        self.indentation_custom_row_widget = QWidget()
        custom_layout = QHBoxLayout(self.indentation_custom_row_widget)
        custom_layout.setContentsMargins(5, 0, 0, 0)
        custom_layout.setSpacing(10)

        custom_label = QLabel("Custom Indentation (px):")
        self.indentation_custom_spin = QSpinBox()
        self.indentation_custom_spin.setRange(0, 100)
        self.indentation_custom_spin.setValue(self.current_config.get("deck_indentation_custom_px", 20))
        self.indentation_custom_spin.setSuffix(" px")
        self.indentation_custom_spin.setFixedWidth(120)

        custom_layout.addWidget(custom_label)
        custom_layout.addWidget(self.indentation_custom_spin)
        custom_layout.addStretch()

        indent_main_layout.addWidget(self.indentation_custom_row_widget)

        # Initial visibility check
        self._on_indentation_mode_btn_clicked(self.indentation_mode_group.checkedButton())

        deck_section.add_widget(indentation_group)

        # Custom creation of deck_icons_group to add info button
        deck_icons_group = QFrame()
        deck_icons_group.setObjectName("innerGroup")
        deck_icons_main_layout = QVBoxLayout(deck_icons_group)
        deck_icons_main_layout.setContentsMargins(10, 10, 10, 10)
        deck_icons_main_layout.setSpacing(8)

        # Title with info button
        title_row = QHBoxLayout()
        title_label = QLabel("Deck Icons")
        title_label.setStyleSheet("font-weight: bold; font-size: 20px;")
        title_row.addWidget(title_label)

        # Info button
        # Info button
        info_button = QPushButton()
        info_button.setFixedSize(24, 24)
        info_button.setCursor(Qt.CursorShape.PointingHandCursor)
        info_button.setToolTip("Click to learn about deck icon types")

        info_icon_path = os.path.join(mw.addonManager.addonsFolder(mw.addonManager.addonFromModule(__name__)), 
                                    "system_files", "system_icons", "info-circle.svg")

        if os.path.exists(info_icon_path):
            pixmap = QPixmap(info_icon_path)
            if not pixmap.isNull():
                # Color the icon
                painter = QPainter(pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                # Use accent color or text color based on theme
                icon_color = QColor(self.accent_color)
                painter.fillRect(pixmap.rect(), icon_color)
                painter.end()
                info_button.setIcon(QIcon(pixmap))
                info_button.setIconSize(QSize(20, 20))

        info_button.setStyleSheet("QPushButton { border: none; background: transparent; }")
        info_button.clicked.connect(self._show_deck_icon_info)
        title_row.addWidget(info_button)
        title_row.addStretch()

        deck_icons_main_layout.addLayout(title_row)

        # Content area
        deck_icons_content_widget = QWidget()
        deck_icons_layout_content = QVBoxLayout(deck_icons_content_widget)
        deck_icons_layout_content.setContentsMargins(0, 5, 0, 0)
        deck_icons_main_layout.addWidget(deck_icons_content_widget)

        deck_icons_layout = QGridLayout(); deck_icons_layout.setSpacing(15)
        deck_icons_layout_content.addLayout(deck_icons_layout)
        deck_icons_to_configure = {"folder": "Folder Icon", "deck": "Deck Icon", "subdeck": "Subdeck Icon", "filtered_deck": "Filtered Deck Icon", "options": "Options Icon", "collapse_closed": "Collapsed Icon (+)", "collapse_open": "Expanded Icon (-)"}
        row, col, num_cols = 0, 0, 3
        for key, label_text in deck_icons_to_configure.items():
            card = QWidget(); card_layout = QVBoxLayout(card); card_layout.setContentsMargins(0,0,0,0); card_layout.setSpacing(5)
            label = QLabel(label_text); label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            control_widget = self._create_icon_control_widget(key); self.icon_assignment_widgets.append(control_widget)
            card_layout.addWidget(label); card_layout.addWidget(control_widget); deck_icons_layout.addWidget(card, row, col)
            col += 1
            if col >= num_cols: col = 0; row += 1

        deck_section.add_widget(deck_icons_group)

        sizing_section, sizing_layout_content = self._create_inner_group("Deck Icon Settings")
        sizing_layout = QFormLayout(); sizing_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        sizing_layout_content.addLayout(sizing_layout)

        # --- Add Hide Icon Toggles ---
        # Note: Using mw.col.conf.get directly to ensure we load the saved state correctly
        self.hide_folder_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_folder_cb.setChecked(mw.col.conf.get("modern_menu_hide_folder_icon", False))
        self.hide_folder_cb.toggled.connect(self._update_deck_icon_state)
        sizing_layout.addRow("Hide Folder Icon:", self.hide_folder_cb)

        self.hide_subdeck_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_subdeck_cb.setChecked(mw.col.conf.get("modern_menu_hide_subdeck_icon", False))
        self.hide_subdeck_cb.toggled.connect(self._update_deck_icon_state)
        sizing_layout.addRow("Hide Subdeck Icon:", self.hide_subdeck_cb)

        self.hide_deck_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_deck_cb.setChecked(mw.col.conf.get("modern_menu_hide_deck_icon", False))
        self.hide_deck_cb.toggled.connect(self._update_deck_icon_state)
        sizing_layout.addRow("Hide Deck Icon:", self.hide_deck_cb)

        self.hide_filtered_deck_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_filtered_deck_cb.setChecked(mw.col.conf.get("modern_menu_hide_filtered_deck_icon", False))
        self.hide_filtered_deck_cb.toggled.connect(self._update_deck_icon_state)
        sizing_layout.addRow("Hide Filtered Deck Icon:", self.hide_filtered_deck_cb)

        # [NEW] Hide default, show custom setting
        self.hide_default_custom_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_default_custom_cb.setChecked(mw.col.conf.get("modern_menu_hide_default_icons", False))
        self.hide_default_custom_cb.toggled.connect(self._update_deck_icon_state)
        self.hide_default_custom_cb.setToolTip("If enabled, default icons will be hidden, but custom deck icons will still be shown.")
        sizing_layout.addRow("Hide default, show custom:", self.hide_default_custom_cb)

        icon_sizes_to_configure = {"deck_folder": "Deck/Folder Icons (px):", "action_button": "Action Button Icons (px):", "collapse": "Expand/Collapse Icons (px):", "options_gear": "Deck Options Gear Icon (px):"}
        for key, label in icon_sizes_to_configure.items(): sizing_layout.addRow(label, self.create_icon_size_spinbox(key, DEFAULT_ICON_SIZES[key]))
        reset_sizes_button = QPushButton("Reset Sizes to Default"); reset_sizes_button.clicked.connect(self.reset_icon_sizes_to_default); sizing_layout.addRow(reset_sizes_button)

        # Initial State Update
        self._update_deck_icon_state()

        deck_section.add_widget(sizing_section)

        deck_color_modes_layout = QHBoxLayout()
        light_deck_colors_group, light_deck_colors_layout = self._create_inner_group("Light Mode Colors")
        light_deck_colors_layout.setSpacing(5)
        self._populate_pills_for_keys(light_deck_colors_layout, "light", ["--deck-list-bg", "--highlight-bg", "--highlight-fg", "--icon-color", "--icon-color-filtered"])
        deck_color_modes_layout.addWidget(light_deck_colors_group)

        dark_deck_colors_group, dark_deck_colors_layout = self._create_inner_group("Dark Mode Colors")
        dark_deck_colors_layout.setSpacing(5)
        self._populate_pills_for_keys(dark_deck_colors_layout, "dark", ["--deck-list-bg", "--highlight-bg", "--highlight-fg", "--icon-color", "--icon-color-filtered"])
        deck_color_modes_layout.addWidget(dark_deck_colors_group)
        deck_section.add_layout(deck_color_modes_layout)

        layout.addWidget(deck_section)

        layout.addStretch()

        sections = {
            "Sidebar Customization": sidebar_section,
            "Sidebar Background": sidebar_group,
            "Organize Action Buttons": action_buttons_section,
            "Deck": deck_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections, buttons_per_row=3)

        return page


    def create_sidebar_custom_options(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        type_mode = mw.col.conf.get("modern_menu_sidebar_bg_type", "color")
        # If the old 'image' mode was saved, default to 'Image' to prevent a blank state
        if type_mode == 'image':
            type_mode = 'image_color'

        type_layout = QHBoxLayout()
        self.sidebar_bg_type_color_radio = QRadioButton("Solid Color")
        self.sidebar_bg_type_accent_radio = QRadioButton("Accent Color")
        self.sidebar_bg_type_image_color_radio = QRadioButton("Image")

        self.sidebar_bg_type_color_radio.setChecked(type_mode == "color")
        self.sidebar_bg_type_accent_radio.setChecked(type_mode == "accent")
        self.sidebar_bg_type_image_color_radio.setChecked(type_mode == "image_color")

        type_layout.addWidget(self.sidebar_bg_type_color_radio)
        type_layout.addWidget(self.sidebar_bg_type_image_color_radio)
        type_layout.addWidget(self.sidebar_bg_type_accent_radio)
        type_layout.addStretch()
        layout.addLayout(type_layout)

        self.sidebar_color_group = QWidget()
        sidebar_color_layout = QVBoxLayout(self.sidebar_color_group)
        sidebar_color_layout.setContentsMargins(0, 10, 0, 0)
        self.sidebar_bg_light_row = self._create_color_picker_row("Color (Light Mode)", mw.col.conf.get("modern_menu_sidebar_bg_color_light", "#F3F3F3"), "sidebar_bg_light")
        sidebar_color_layout.addLayout(self.sidebar_bg_light_row)
        self.sidebar_bg_dark_row = self._create_color_picker_row("Color (Dark Mode)", mw.col.conf.get("modern_menu_sidebar_bg_color_dark", "#3C3C3C"), "sidebar_bg_dark")
        sidebar_color_layout.addLayout(self.sidebar_bg_dark_row)
        layout.addWidget(self.sidebar_color_group)

        self.galleries["sidebar_bg"] = {}
        self.sidebar_image_group = self._create_image_gallery_group("sidebar_bg", "user_files/sidebar_bg", "modern_menu_sidebar_bg_image", is_sub_group=True)
        layout.addWidget(self.sidebar_image_group)

        self.sidebar_effects_container = QWidget()
        effects_layout = QHBoxLayout(self.sidebar_effects_container)
        effects_layout.setContentsMargins(0, 10, 0, 0)

        self.sidebar_bg_blur_label = QLabel("Blur:")
        self.sidebar_bg_blur_spinbox = QSpinBox()
        self.sidebar_bg_blur_spinbox.setMinimum(0)
        self.sidebar_bg_blur_spinbox.setMaximum(100)
        self.sidebar_bg_blur_spinbox.setSuffix(" %")
        self.sidebar_bg_blur_spinbox.setValue(mw.col.conf.get("modern_menu_sidebar_bg_blur", 0))
        effects_layout.addWidget(self.sidebar_bg_blur_label)
        effects_layout.addWidget(self.sidebar_bg_blur_spinbox)

        # ðŸ”½ Opacity and Transparency ðŸ”½
        self.sidebar_bg_opacity_label = QLabel("Image Opacity:")
        self.sidebar_bg_opacity_spinbox = QSpinBox()
        self.sidebar_bg_opacity_spinbox.setMinimum(0)
        self.sidebar_bg_opacity_spinbox.setMaximum(100)
        self.sidebar_bg_opacity_spinbox.setSuffix(" %")
        self.sidebar_bg_opacity_spinbox.setValue(mw.col.conf.get("modern_menu_sidebar_bg_opacity", 100))
        effects_layout.addWidget(self.sidebar_bg_opacity_label)
        effects_layout.addWidget(self.sidebar_bg_opacity_spinbox)

        self.sidebar_bg_transparency_label = QLabel("Transparency:")
        self.sidebar_bg_transparency_spinbox = QSpinBox()
        self.sidebar_bg_transparency_spinbox.setMinimum(0)
        self.sidebar_bg_transparency_spinbox.setMaximum(100)
        self.sidebar_bg_transparency_spinbox.setSuffix(" %")
        self.sidebar_bg_transparency_spinbox.setValue(mw.col.conf.get("modern_menu_sidebar_bg_transparency", 0))
        effects_layout.addWidget(self.sidebar_bg_transparency_label)
        effects_layout.addWidget(self.sidebar_bg_transparency_spinbox)
        # ðŸ”¼ Opacity and Transparency ðŸ”¼

        effects_layout.addStretch()
        layout.addWidget(self.sidebar_effects_container)

        self.sidebar_bg_type_color_radio.toggled.connect(self.toggle_sidebar_bg_type_options)
        self.sidebar_bg_type_image_color_radio.toggled.connect(self.toggle_sidebar_bg_type_options)
        self.sidebar_bg_type_accent_radio.toggled.connect(self.toggle_sidebar_bg_type_options)

        self.toggle_sidebar_bg_type_options()
        return widget


    def _create_slideshow_images_selector(self, image_files_cache):
        """Creates a gallery widget for selecting multiple images for slideshow mode."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        # Instructions label
        instructions = QLabel("Select images to include in the slideshow (click on images to toggle selection):")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Scroll area for image gallery
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(400)

        scroll_content = QWidget()
        scroll_layout = QGridLayout(scroll_content)
        scroll_layout.setSpacing(10)
        scroll_layout.setContentsMargins(10, 10, 10, 10)

        # Get saved slideshow images
        saved_images = mw.col.conf.get("modern_menu_slideshow_images", [])

        # Get the user files path - CORRECTED PATH
        addon_path = os.path.dirname(__file__)
        user_bg_folder = os.path.join(addon_path, "user_files", "main_bg")

        # Create gallery items for each image
        self.slideshow_image_items = []
        row, col = 0, 0
        max_cols = 4  # 4 images per row

        for img_file in image_files_cache:
            # Create container for image + checkbox
            item_widget = QWidget()
            item_widget.setObjectName("galleryItem")
            item_widget.setFixedSize(120, 90)
            item_widget.setCursor(Qt.CursorShape.PointingHandCursor)

            # Store the filename and checked state
            item_widget.img_filename = img_file
            item_widget.is_checked = img_file in saved_images

            # Create the image label
            img_path = os.path.join(user_bg_folder, img_file)
            img_label = QLabel(item_widget)
            img_label.setFixedSize(120, 90)
            img_label.setScaledContents(False)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Load and display the image with rounded corners
            if os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                if not pixmap.isNull():
                    # Scale to fit while maintaining aspect ratio
                    scaled_pixmap = pixmap.scaled(
                        120, 90,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    # Crop from center
                    crop_x = (scaled_pixmap.width() - 120) / 2
                    crop_y = (scaled_pixmap.height() - 90) / 2
                    cropped_pixmap = scaled_pixmap.copy(int(crop_x), int(crop_y), 120, 90)

                    # Apply rounded corners
                    rounded_pixmap = create_rounded_pixmap(cropped_pixmap, 10)
                    img_label.setPixmap(rounded_pixmap)

            # Create custom selection overlay using accent color
            overlay = SelectionOverlay(item_widget, accent_color=self.accent_color)
            overlay.setChecked(item_widget.is_checked)
            overlay.move(90, 5)  # Top-right corner (120 - 24 - 6 padding)

            # Store overlay reference
            item_widget.overlay = overlay

            # Apply border styling based on selection
            self._update_slideshow_item_border(item_widget)

            # Connect click events
            def make_click_handler(widget):
                def handler(event):
                    widget.is_checked = not widget.is_checked
                    widget.overlay.setChecked(widget.is_checked)
                    self._update_slideshow_item_border(widget)
                return handler

            item_widget.mousePressEvent = make_click_handler(item_widget)

            # Add to grid
            scroll_layout.addWidget(item_widget, row, col)
            self.slideshow_image_items.append(item_widget)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Add/Remove buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._toggle_all_slideshow_images(True))
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self._toggle_all_slideshow_images(False))
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        return widget


    def _update_slideshow_item_border(self, item_widget):
        """Update the border style of a slideshow gallery item based on selection state."""
        if item_widget.is_checked:
            item_widget.setStyleSheet(f"""
                #galleryItem {{
                    border: 3px solid {self.accent_color};
                    border-radius: 10px;
                    background: transparent;
                }}
            """)
        else:
            item_widget.setStyleSheet("""
                #galleryItem {
                    border: 2px solid transparent;
                    border-radius: 10px;
                    background: transparent;
                }
                #galleryItem:hover {
                    border: 2px solid #888888;
                }
            """)


    def _on_slideshow_checkbox_toggled(self, item_widget, checked):
        """Handle checkbox toggle for slideshow gallery items."""
        item_widget.is_checked = checked
        item_widget.overlay.setChecked(checked)
        self._update_slideshow_item_border(item_widget)


    def _toggle_all_slideshow_images(self, checked):
        """Toggle all slideshow image gallery items."""
        for item in self.slideshow_image_items:
            item.is_checked = checked
            item.overlay.setChecked(checked)
            self._update_slideshow_item_border(item)



    def toggle_sidebar_background_options(self): 
        self.sidebar_main_options_group.setVisible(self.sidebar_bg_main_radio.isChecked())
        self.sidebar_custom_options_group.setVisible(self.sidebar_bg_custom_radio.isChecked())    

    def toggle_sidebar_bg_type_options(self):
        """Shows/hides options based on the selected sidebar background type."""
        try:
            is_color = self.sidebar_bg_type_color_radio.isChecked()
            is_accent = self.sidebar_bg_type_accent_radio.isChecked()
            is_image_color = self.sidebar_bg_type_image_color_radio.isChecked()

            if self.sidebar_color_group:
                self.sidebar_color_group.setVisible(is_color or is_image_color)

            if self.sidebar_image_group:
                self.sidebar_image_group.setVisible(is_image_color)

            if self.sidebar_effects_container:
                # Blur and Opacity are only for modes with an image
                self.sidebar_bg_blur_label.setVisible(is_image_color)
                self.sidebar_bg_blur_spinbox.setVisible(is_image_color)
                self.sidebar_bg_opacity_label.setVisible(is_image_color)
                self.sidebar_bg_opacity_spinbox.setVisible(is_image_color)

                # Transparency is only for modes without an image
                self.sidebar_bg_transparency_label.setVisible(is_color or is_accent)
                self.sidebar_bg_transparency_spinbox.setVisible(is_color or is_accent)

        except RuntimeError:
            # This error can occur if the widgets are accessed after they've been
            # deleted (e.g., when the settings dialog is closing).
            # We can safely ignore it to prevent a crash.
            pass

    def _toggle_sidebar_effect_options(self):
        is_overlay = self.sidebar_effect_overlay_radio.isChecked()
        self.sidebar_overlay_options_group.setVisible(is_overlay)
        self.sidebar_effect_intensity_group.setVisible(not is_overlay)


    def _toggle_canvas_intensity_spinbox(self):
        is_disabled = self.canvas_effect_none_radio.isChecked()
        self.canvas_effect_intensity_spinbox.setEnabled(not is_disabled)




    def _save_sidebar_settings(self):
        self.current_config["hideWelcomeMessage"] = self.hide_welcome_checkbox.isChecked()
        self.current_config["hideDeckCounts"] = self.hide_deck_counts_checkbox.isChecked()
        self.current_config["hideAllDeckCounts"] = self.hide_all_deck_counts_checkbox.isChecked()

        # Save Sidebar Action Buttons Mode
        if hasattr(self, "actions_mode_collapsed") and self.actions_mode_collapsed.isChecked():
            self.current_config["sidebarActionsMode"] = "collapsed"
        elif hasattr(self, "actions_mode_archived") and self.actions_mode_archived.isChecked():
            self.current_config["sidebarActionsMode"] = "archived"
        else:
            self.current_config["sidebarActionsMode"] = "list"

        # Save Deck Indentation Settings
        if hasattr(self, "indentation_mode_group"):
             if btn := self.indentation_mode_group.checkedButton():
                 self.current_config["deck_indentation_mode"] = btn.property("indent_mode")

        if hasattr(self, "indentation_custom_spin"):
             self.current_config["deck_indentation_custom_px"] = self.indentation_custom_spin.value()

        # Save Hide Icon Toggles
        if hasattr(self, "hide_folder_cb"):
            mw.col.conf["modern_menu_hide_folder_icon"] = self.hide_folder_cb.isChecked()
        if hasattr(self, "hide_subdeck_cb"):
            mw.col.conf["modern_menu_hide_subdeck_icon"] = self.hide_subdeck_cb.isChecked()
        if hasattr(self, "hide_deck_cb"):
            mw.col.conf["modern_menu_hide_deck_icon"] = self.hide_deck_cb.isChecked()
        if hasattr(self, "hide_default_custom_cb"):
            mw.col.conf["modern_menu_hide_default_icons"] = self.hide_default_custom_cb.isChecked()

        for widget in self.action_button_icon_widgets:
            key = widget.property("icon_key")
            value = widget.property("icon_filename")
            config_key = f"modern_menu_icon_{key}"
            mw.col.conf[config_key] = value or ""

        for widget in self.icon_assignment_widgets:
            key = widget.property("icon_key")
            value = widget.property("icon_filename")
            config_key = f"modern_menu_icon_{key}"
            mw.col.conf[config_key] = value or ""

        for key, widget in self.icon_size_widgets.items():
            mw.col.conf[f"modern_menu_icon_size_{key}"] = widget.value()

        sidebar_color_keys = [
            "--icon-color", "--icon-color-filtered", "--deck-list-bg",
            "--highlight-bg", "--highlight-fg"
        ]
        for mode in ["light", "dark"]:
            for key in sidebar_color_keys:
                if key in self.color_widgets[mode]:
                    widget = self.color_widgets[mode][key]
                    self.current_config["colors"][mode][key] = widget.text()

        # --- Sidebar Background Settings ---
        if self.sidebar_bg_custom_radio.isChecked(): mw.col.conf["modern_menu_sidebar_bg_mode"] = "custom"
        else: mw.col.conf["modern_menu_sidebar_bg_mode"] = "main"

        if self.sidebar_effect_glass_radio.isChecked():
            mw.col.conf["onigiri_sidebar_main_bg_effect_mode"] = "glassmorphism"
        else:
            mw.col.conf["onigiri_sidebar_main_bg_effect_mode"] = "opaque"

        mw.col.conf["onigiri_sidebar_main_bg_effect_intensity"] = self.sidebar_effect_intensity_spinbox.value()
        mw.col.conf["onigiri_sidebar_opaque_tint_intensity"] = self.sidebar_overlay_intensity_spinbox.value()
        mw.col.conf["onigiri_sidebar_opaque_tint_color_light"] = self.overlay_light_color_color_input.text()
        mw.col.conf["onigiri_sidebar_opaque_tint_color_dark"] = self.overlay_dark_color_color_input.text()

        if self.sidebar_bg_type_accent_radio.isChecked():
            mw.col.conf["modern_menu_sidebar_bg_type"] = "accent"
        elif self.sidebar_bg_type_image_color_radio.isChecked():
            mw.col.conf["modern_menu_sidebar_bg_type"] = "image_color"
        else:
            mw.col.conf["modern_menu_sidebar_bg_type"] = "color"

        mw.col.conf["modern_menu_sidebar_bg_color_light"] = self.sidebar_bg_light_color_input.text()
        mw.col.conf["modern_menu_sidebar_bg_color_dark"] = self.sidebar_bg_dark_color_input.text()
        mw.col.conf["modern_menu_sidebar_bg_blur"] = self.sidebar_bg_blur_spinbox.value()

        # Opacity and Transparency
        mw.col.conf["modern_menu_sidebar_bg_opacity"] = self.sidebar_bg_opacity_spinbox.value()
        mw.col.conf["modern_menu_sidebar_bg_transparency"] = self.sidebar_bg_transparency_spinbox.value()

        # Save sidebar background image if it exists
        if 'sidebar_bg' in self.galleries:
            mw.col.conf["modern_menu_sidebar_bg_image"] = self.galleries['sidebar_bg'].get('selected', '')


    def _save_sidebar_layout_settings(self):
        """Saves the sidebar button layout from the editor."""
        if hasattr(self, 'sidebar_layout_editor'):
            self.current_config["sidebarButtonLayout"] = self.sidebar_layout_editor.get_layout_config()


    def reset_sidebar_to_default(self):
        # Set the main mode back to "Use Main Background Settings"
        self.sidebar_bg_main_radio.setChecked(True)

        # Reset the "Use Main" effect settings to "Color Overlay"
        self.sidebar_effect_overlay_radio.setChecked(True)
        self.sidebar_overlay_intensity_spinbox.setValue(30)
        self.overlay_light_color_color_input.setText("#FFFFFF")
        # Per your request, the dark mode default is #1D1D1D
        self.overlay_dark_color_color_input.setText("#1D1D1D")
        self.sidebar_effect_intensity_spinbox.setValue(50) # Also reset glassmorphism

        # Reset the "Custom" settings
        if 'sidebar_bg' in self.galleries:
            self.galleries['sidebar_bg']['selected'] = ""
            if self.galleries['sidebar_bg'].get('path_input'):
                self.galleries['sidebar_bg']['path_input'].setText("")
            self._refresh_gallery('sidebar_bg')

        self.sidebar_bg_type_color_radio.setChecked(True)
        self.sidebar_bg_light_color_input.setText("#F3F3F3")
        self.sidebar_bg_dark_color_input.setText("#2C2C2C")
        self.sidebar_bg_blur_spinbox.setValue(0)
        self.sidebar_bg_opacity_spinbox.setValue(100)


    def _on_indentation_mode_btn_clicked(self, button):
        if not button: return
        mode = button.property("indent_mode")
        is_custom = (mode == "custom")
        if hasattr(self, 'indentation_custom_row_widget'):
            self.indentation_custom_row_widget.setVisible(is_custom)


    def _update_deck_icon_state(self):
        # Disable the deck_folder size spinbox if either hide toggle is ON
        if "deck_folder" in self.icon_size_widgets:
            should_disable = (self.hide_folder_cb.isChecked() or 
                            self.hide_subdeck_cb.isChecked() or 
                            self.hide_deck_cb.isChecked())
            self.icon_size_widgets["deck_folder"].setEnabled(not should_disable)


    def _show_deck_icon_info(self):
        """Display explanation of deck icon types."""
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Deck Icon Types")
        dialog.setTextFormat(Qt.TextFormat.RichText)
        dialog.setText("""
            <h3>Understanding Deck Icon Types</h3>
            <p><b>Folder:</b> A deck that contains subdecks inside it. Uses the folder icon.</p>
            <p><b>Deck:</b> A top-level deck that doesn't contain any subdecks. Uses the deck icon.</p>
            <p><b>Subdeck:</b> A deck that is nested inside a folder. Uses the subdeck icon.</p>
            <p><b>Filtered Deck:</b> A special deck type with dynamic cards based on search criteria. Uses the filtered deck icon.</p>
        """)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.exec()

