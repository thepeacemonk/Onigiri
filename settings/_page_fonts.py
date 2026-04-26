class FontsPageMixin:
    def _create_font_selector_group(self, title, config_key):
        """Helper to create a font selection grid for a given config key."""
        group = SectionGroup(title, self, border=False)

        # --- NEW: Font Control Row (Size) ---
        control_widget = QWidget()
        control_layout = QHBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 0, 5) # Slight margin

        size_label = QLabel("Font Size:")
        size_label.setStyleSheet("color: var(--fg-subtle);")

        size_spinbox = QSpinBox()
        size_spinbox.setRange(8, 72)
        size_spinbox.setSuffix("px")
        size_spinbox.setFixedWidth(80)

        # Load saved size or default
        if config_key == "main":
            default_size = 14
        elif config_key == "subtle":
            default_size = 20
        else: # small_title
            default_size = 15
        # Check col.conf first
        saved_size = mw.col.conf.get(f"onigiri_font_size_{config_key}", default_size)
        size_spinbox.setValue(int(saved_size))

        # Save reference
        setattr(self, f"font_size_{config_key}", size_spinbox)

        # Restore Button
        restore_btn = QPushButton("Restore Default")
        restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        restore_btn.setToolTip(f"Reset to {default_size}px")
        # Capture default_size and spinbox in lambda
        restore_btn.clicked.connect(lambda _, s=size_spinbox, d=default_size: s.setValue(d))

        control_layout.addWidget(size_label)
        control_layout.addWidget(size_spinbox)
        control_layout.addWidget(restore_btn)
        control_layout.addStretch()

        group.add_widget(control_widget)
        # ------------------------------------

        container_widget = QWidget()
        container_layout = QHBoxLayout(container_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)

        grid_layout = QGridLayout(); grid_layout.setSpacing(15)

        # <<< Store grid_layout and config_key for later refresh >>>
        if not hasattr(self, 'font_grids'):
            self.font_grids = {}
        self.font_grids[config_key] = grid_layout

        self._populate_font_grid(config_key)
        # <<< END MODIFICATION >>>

        container_layout.addLayout(grid_layout)
        container_layout.addStretch()

        group.add_widget(container_widget)

        return group


    def _populate_font_grid(self, config_key):
        grid_layout = self.font_grids[config_key]

        # Clear existing widgets
        while grid_layout.count():
            child = grid_layout.takeAt(0)
            if widget := child.widget():
                widget.deleteLater()

        all_fonts = get_all_fonts(self.addon_path)

        font_cards = []
        # Separate system and user fonts for ordering
        system_fonts = {k: v for k, v in all_fonts.items() if not v.get("user")}
        user_fonts = {k: v for k, v in all_fonts.items() if v.get("user")}

        font_order = ["instrument_serif", "nunito", "montserrat", "space_mono"]

        row, col, num_cols = 0, 0, 2

        # Add the "System" font card first, spanning the full width
        if "system" in system_fonts:
            system_card = FontCardWidget("system", self.accent_color, self, is_system_card=True)
            font_cards.append(system_card)
            grid_layout.addWidget(system_card, row, 0, 1, num_cols) # Add to grid, spanning 2 columns
            row += 1 # Move to the next row

        # <<< START MODIFICATION >>>
        # Move the "Add Your Own Font" button to be directly under the "System" button
        add_button = QPushButton("Add Your Own Font")
        add_button.setFixedHeight(50) # Match the height of the "System" button
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.clicked.connect(self._add_user_font)

        # Style it to look like a solid, non-dashed card
        if theme_manager.night_mode:
            add_button.setStyleSheet(f"""
                QPushButton {{ 
                    background-color: #3a3a3a; 
                    border: 2px solid #4a4a4a; 
                    border-radius: px; 
                    color: #e0e0e0; 
                }} 
                QPushButton:hover {{ 
                    border-color: #5a5a5a; 
                }}
            """)
        else:
            add_button.setStyleSheet(f"""
                QPushButton {{ 
                    background-color: #e9e9e9; 
                    border: 2px solid #e0e0e0; 
                    border-radius: 12px; 
                    color: #212121; 
                }} 
                QPushButton:hover {{ 
                    border-color: #d0d0d0; 
                }}
            """)

        grid_layout.addWidget(add_button, row, 0, 1, num_cols) # Add to grid, spanning 2 columns
        row += 1 # Move to the next row for the regular fonts
        # <<< END MODIFICATION >>>

        def add_card_to_grid(font_key):
            nonlocal row, col
            delete_icon = self._create_delete_icon()
            card = FontCardWidget(font_key, self.accent_color, self, delete_icon=delete_icon)
            if all_fonts[font_key].get("user"):
                card.delete_requested.connect(lambda key=font_key: self._delete_user_font(key))
            font_cards.append(card)
            grid_layout.addWidget(card, row, col)
            col += 1
            if col >= num_cols:
                col = 0
                row += 1

        # Add other system fonts in specified order
        for key in font_order:
            if key in system_fonts:
                add_card_to_grid(key)

        # Add user-installed fonts
        for key in sorted(user_fonts.keys()):
            add_card_to_grid(key)

        # <<< MODIFICATION: The old "Add Yours" button code has been removed from here >>>

        # Set the checked state
        saved_font = mw.col.conf.get(f"onigiri_font_{config_key}", "system")
        for card in font_cards:
            if card.font_key == saved_font:
                card.setChecked(True)
                break

        setattr(self, f"font_cards_{config_key}", font_cards)

    # <<< START NEW METHODS >>>

    def _add_user_font(self):
        user_fonts_dir = os.path.join(self.addon_path, "user_files", "fonts")
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Font File", "", "Font Files (*.ttf *.otf *.woff *.woff2)")

        if not filepath:
            return

        filename = os.path.basename(filepath)
        dest_path = os.path.join(user_fonts_dir, filename)

        try:
            shutil.copy(filepath, dest_path)
            showInfo(f"Font '{filename}' added successfully.")
            # Refresh both font grids
            self._populate_font_grid("main")
            self._populate_font_grid("subtle")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not copy font file: {e}")


    def _delete_user_font(self, font_key):
        reply = QMessageBox.question(self, "Confirm Delete", 
            f"Are you sure you want to delete the font '{font_key}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            font_path = os.path.join(self.addon_path, "user_files", "fonts", font_key)
            try:
                if os.path.exists(font_path):
                    os.remove(font_path)

                    # If the deleted font was selected, revert to system
                    for key in ["main", "subtle"]:
                        if mw.col.conf.get(f"onigiri_font_{key}") == font_key:
                            mw.col.conf[f"onigiri_font_{key}"] = "system"

                    showInfo(f"Font '{font_key}' deleted.")
                    self._populate_font_grid("main")
                    self._populate_font_grid("subtle")
                else:
                    QMessageBox.warning(self, "Error", "Font file not found.")
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Could not delete font file: {e}")
    # <<< END NEW METHODS >>>


    def create_fonts_page(self):
        page, layout = self._create_scrollable_page()

        fonts_container = QWidget()
        fonts_layout = FlowLayout(fonts_container, spacing=20)
        fonts_layout.setContentsMargins(0, 0, 0, 0)

        text_group = self._create_font_selector_group("Text", "main")
        subtle_group = self._create_font_selector_group("Titles", "subtle")
        small_title_group = self._create_font_selector_group("Small Titles", "small_title")

        fonts_layout.addWidget(text_group)
        fonts_layout.addWidget(subtle_group)
        fonts_layout.addWidget(small_title_group)

        layout.addWidget(fonts_container)
        layout.addStretch()

        sections = {}
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections)

        return page



    def _save_fonts_settings(self):
        for card in self.font_cards_main:
            if card.isChecked():
                mw.col.conf["onigiri_font_main"] = card.font_key
                break
        for card in self.font_cards_subtle:
            if card.isChecked():
                mw.col.conf["onigiri_font_subtle"] = card.font_key
                break
        for card in getattr(self, "font_cards_small_title", []):
            if card.isChecked():
                mw.col.conf["onigiri_font_small_title"] = card.font_key
                break

        # Save Font Sizes
        if hasattr(self, "font_size_main"):
            mw.col.conf["onigiri_font_size_main"] = self.font_size_main.value()
        if hasattr(self, "font_size_subtle"):
            mw.col.conf["onigiri_font_size_subtle"] = self.font_size_subtle.value()
        if hasattr(self, "font_size_small_title"):
            mw.col.conf["onigiri_font_size_small_title"] = self.font_size_small_title.value()

