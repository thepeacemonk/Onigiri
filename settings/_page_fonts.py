# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *



class PageFontsMixin:
    def _font_color_key_for_config(self, config_key):
        return {
            "main": "--fg",
            "subtle": "--fg-subtle",
            "small_title": "--font-small-title-color",
        }.get(config_key, "--fg")

    def _font_color_default_for_config(self, config_key, mode):
        colors = self.current_config.get("colors", {}).get(mode, {})
        defaults = DEFAULTS["colors"].get(mode, {})
        if config_key == "small_title":
            return colors.get("--font-small-title-color", defaults.get("--font-small-title-color", defaults.get("--fg", "#202124")))
        color_key = self._font_color_key_for_config(config_key)
        return colors.get(color_key, defaults.get(color_key, "#202124"))

    def _on_font_color_changed(self, mode, color_key, value):
        color = QColor(value)
        if not color.isValid():
            return
        self.current_config.setdefault("colors", {}).setdefault(mode, {})[color_key] = value
        self._update_font_preview_mode_styles()
        if (theme_manager.night_mode and mode == "dark") or (not theme_manager.night_mode and mode == "light"):
            self._schedule_stylesheet_apply()

    def _set_font_preview_mode(self, mode):
        self.font_preview_mode = mode
        self._update_font_preview_mode_styles()

    def _update_font_preview_mode_styles(self):
        selectors = getattr(self, "font_selectors", {})
        if not selectors:
            return
        mode = getattr(self, "font_preview_mode", "dark" if theme_manager.night_mode else "light")
        mode_colors = self.current_config.get("colors", {}).get(mode, {})
        defaults = DEFAULTS["colors"].get(mode, {})
        bg = mode_colors.get("--canvas-inset", defaults.get("--canvas-inset", "#ffffff" if mode == "light" else "#242424"))
        fg = mode_colors.get("--fg", defaults.get("--fg", "#202124" if mode == "light" else "#f4f4f5"))
        subtle = mode_colors.get("--fg-subtle", defaults.get("--fg-subtle", "#6f7177" if mode == "light" else "#b7bcc5"))
        small_title = mode_colors.get("--font-small-title-color", defaults.get("--font-small-title-color", fg))
        border = mode_colors.get("--border", defaults.get("--border", "#dcdde1" if mode == "light" else "#454545"))
        color_by_role = {
            "main": fg,
            "subtle": subtle,
            "small_title": small_title,
        }
        for config_key, selector in selectors.items():
            preview = selector.get("preview")
            if preview:
                role_color = color_by_role.get(config_key, fg)
                preview.setStyleSheet(f"""
                    QFrame#fontPreviewPanel {{
                        background-color: {bg};
                        border: 1px solid {border};
                        border-radius: 8px;
                    }}
                    QLabel#fontPreviewTitle {{
                        color: {role_color};
                        background: transparent;
                    }}
                    QLabel#fontPreviewBody {{
                        color: {role_color};
                        background: transparent;
                    }}
                """)

    def _create_font_selector_group(self, title, config_key):
        """Create a clear font role editor with one selector, size control, and preview."""
        description_map = {
            "main": tr("font_body_description", "Used for normal text across Onigiri."),
            "subtle": tr("font_titles_description", "Used for large titles and page headings."),
            "small_title": tr("font_small_titles_description", "Used for compact labels and small headings."),
        }
        group = SectionGroup(title, self, border=False, description=description_map.get(config_key, ""))

        role_widget = QWidget()
        role_widget.setObjectName("fontRoleControl")
        role_layout = QVBoxLayout(role_widget)
        role_layout.setContentsMargins(0, 0, 0, 0)
        role_layout.setSpacing(12)

        controls_block = QWidget()
        controls_block.setObjectName("fontControlsBlock")
        controls_block.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls_block_layout = QVBoxLayout(controls_block)
        controls_block_layout.setContentsMargins(0, 0, 0, 0)
        controls_block_layout.setSpacing(12)

        control_row = QWidget()
        control_row.setObjectName("fontControlRow")
        control_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        control_layout = QGridLayout(control_row)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setHorizontalSpacing(10)
        control_layout.setVerticalSpacing(10)
        control_layout.setColumnStretch(0, 1)
        control_layout.setColumnStretch(1, 1)

        font_combo = FontSelectorComboBox()
        font_combo.setObjectName("fontSelectorCombo")
        font_combo.setMinimumWidth(220)
        font_combo.setFixedHeight(44)
        font_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        font_combo.setMaxVisibleItems(7)
        palette = self._settings_palette()
        icons_dir = os.path.join(self.addon_path, "system_files", "system_icons", "available_for_users")
        font_combo.setPopupContext(
            self.addon_path,
            self._font_family_for_key,
            self._delete_user_font,
            os.path.join(icons_dir, "check-simple.svg"),
            os.path.join(icons_dir, "minus.svg"),
            self.accent_color,
            palette.get("--muted-fg", "#8f9299"),
            palette.get("--fg", "#202124"),
            palette.get("--hover-bg", "#e9e9e9"),
            palette.get("--canvas-inset", "#ffffff"),
            palette.get("--border", "#dcdde1"),
        )

        all_fonts = get_all_fonts(self.addon_path)
        ordered_keys = ["system", "instrument_serif", "nunito", "montserrat", "space_mono"]
        ordered_keys += sorted([key for key, info in all_fonts.items() if info.get("user")])
        for font_key in ordered_keys:
            info = all_fonts.get(font_key)
            if not info:
                continue
            display_name = tr("system") if font_key == "system" else info.get("name", font_key)
            font_combo.addItem(display_name, font_key)

        size_spinbox = QSpinBox()
        size_spinbox.setObjectName("fontSizeSpinBox")
        size_spinbox.setRange(8, 72)
        size_spinbox.setSuffix("px")
        size_spinbox.setFixedHeight(44)
        size_spinbox.setMinimumWidth(102)
        size_spinbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        if config_key == "main":
            default_size = 14
        elif config_key == "subtle":
            default_size = 20
        else:
            default_size = 15
        saved_size = mw.col.conf.get(f"onigiri_font_size_{config_key}", default_size)
        size_spinbox.setValue(int(saved_size))

        setattr(self, f"font_size_{config_key}", size_spinbox)

        restore_btn = QPushButton(tr("restore_default"))
        restore_btn.setObjectName("fontRestoreButton")
        restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        restore_btn.setFixedHeight(44)
        restore_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        restore_btn.setToolTip(f"{tr('restore_default')} {default_size}px")
        restore_btn.clicked.connect(lambda _, s=size_spinbox, d=default_size: s.setValue(d))

        add_button = QPushButton(tr("add_your_font"))
        add_button.setObjectName("fontAddButton")
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.setFixedHeight(44)
        add_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        add_button.clicked.connect(self._add_user_font)

        control_layout.addWidget(font_combo, 0, 0)
        control_layout.addWidget(size_spinbox, 0, 1)
        control_layout.addWidget(restore_btn, 1, 0)
        control_layout.addWidget(add_button, 1, 1)
        controls_block_layout.addWidget(control_row)

        color_key = self._font_color_key_for_config(config_key)
        color_controls = QWidget()
        color_controls.setObjectName("fontColorControls")
        color_controls.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        color_layout = QVBoxLayout(color_controls)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(10)
        for mode in ["light", "dark"]:
            value = self._font_color_default_for_config(config_key, mode)
            color_layout.addWidget(self._create_font_color_pill_row(
                color_key,
                value,
                mode,
                tr("light_color", "Light Color") if mode == "light" else tr("dark_color", "Dark Color"),
            ))
            self.color_widgets[mode][color_key].textChanged.connect(
                lambda value, m=mode, key=color_key: self._on_font_color_changed(m, key, value)
            )
        controls_block_layout.addWidget(color_controls)

        font_editor_pair = None

        def sync_font_controls_width():
            left_width = max(font_combo.minimumWidth(), restore_btn.sizeHint().width())
            right_width = max(size_spinbox.minimumWidth(), add_button.sizeHint().width())
            width = left_width + right_width + control_layout.horizontalSpacing()
            controls_block.setMaximumWidth(max(1, width))
            if font_editor_pair is not None:
                font_editor_pair.refresh_widths()

        sync_font_controls_width()
        QTimer.singleShot(0, sync_font_controls_width)

        preview = QFrame()
        preview.setObjectName("fontPreviewPanel")
        preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(16, 14, 16, 14)
        preview_layout.setSpacing(4)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        preview_title = QLabel(title)
        preview_title.setObjectName("fontPreviewTitle")
        preview_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        preview_body = QLabel(tr("font_preview_text", "The quick brown fox jumps over the lazy dog. 1234567890"))
        preview_body.setObjectName("fontPreviewBody")
        preview_body.setWordWrap(True)
        preview_body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(preview_body)
        preview_layout.addStretch(1)

        font_editor_pair = FontEditorResponsiveWidget(controls_block, preview, spacing=18, breakpoint=0)
        role_layout.addWidget(font_editor_pair)

        if not hasattr(self, "font_selectors"):
            self.font_selectors = {}
        self.font_selectors[config_key] = {
            "combo": font_combo,
            "preview": preview,
            "preview_title": preview_title,
            "preview_body": preview_body,
        }

        saved_font = mw.col.conf.get(f"onigiri_font_{config_key}", "system")
        idx = font_combo.findData(saved_font)
        if idx >= 0:
            font_combo.setCurrentIndex(idx)

        font_combo.currentIndexChanged.connect(lambda _, key=config_key: self._update_font_preview(key))
        size_spinbox.valueChanged.connect(lambda _, key=config_key: self._update_font_preview(key))
        self._update_font_preview(config_key)

        group.add_widget(role_widget)
        return group

    def _create_font_color_pill_row(self, color_key, initial_color, mode, label_text):
        label_button = QPushButton(label_text)
        label_button.setCursor(Qt.CursorShape.PointingHandCursor)

        value_button = QPushButton()
        value_button.setObjectName("fontColorValuePill")
        value_button.setCursor(Qt.CursorShape.PointingHandCursor)
        value_button.setFixedHeight(44)

        hex_input = QLineEdit(initial_color, self)
        hex_input.hide()
        self.color_widgets[mode][color_key] = hex_input

        def choose_color(anchor):
            chosen, ok = OnigiriColorDialog.getColor(hex_input.text(), self, anchor=anchor)
            if ok:
                hex_input.setText(chosen)

        label_button.clicked.connect(lambda _=False, b=label_button: choose_color(b))
        value_button.clicked.connect(lambda _=False, b=value_button: choose_color(b))
        hex_input.textChanged.connect(lambda color, b=value_button: self._style_font_color_value_pill(b, color if QColor(color).isValid() else initial_color))

        self._style_font_color_value_pill(value_button, initial_color)
        return self._create_color_selector_card(label_button, value_button)

    def _style_font_color_value_pill(self, button, color):
        qcolor = QColor(color)
        if not qcolor.isValid():
            qcolor = QColor("#ffffff")
            color = "#ffffff"
        text_color = "#111827" if qcolor.lightness() > 150 else "#ffffff"
        button.setText(str(color).upper())
        button.setStyleSheet(f"""
            QPushButton#fontColorValuePill {{
                background-color: {color};
                color: {text_color};
                border: 1px solid #4b5563;
                border-radius: 14px;
                min-height: 44px;
                max-height: 44px;
                padding: 0px 18px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton#fontColorValuePill:hover,
            QPushButton#fontColorValuePill:pressed {{
                border-radius: 14px;
            }}
        """)

    def _font_family_for_key(self, font_key):
        if font_key == "system":
            return ""
        if font_key in self._font_family_cache:
            return self._font_family_cache[font_key]

        font_info = get_all_fonts(self.addon_path).get(font_key, {})
        font_file = font_info.get("file")
        if not font_file:
            return ""
        if font_info.get("user"):
            font_path = os.path.join(self.addon_path, "user_files", "fonts", font_file)
        else:
            font_path = os.path.join(self.addon_path, "system_files", "fonts", "system_fonts", font_file)
        if not os.path.exists(font_path):
            return ""
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            family = font_info.get("family", "")
            self._font_family_cache[font_key] = family
            return family
        families = QFontDatabase.applicationFontFamilies(font_id)
        family = families[0] if families else font_info.get("family", "")
        self._font_family_cache[font_key] = family
        return family

    def _update_font_preview(self, config_key):
        selector = getattr(self, "font_selectors", {}).get(config_key)
        if not selector:
            return
        font_key = selector["combo"].currentData() or "system"
        family = self._font_family_for_key(font_key)
        size = getattr(self, f"font_size_{config_key}").value()
        title_font = QFont()
        body_font = QFont()
        if family:
            title_font.setFamily(family)
            body_font.setFamily(family)
        title_font.setPixelSize(max(1, int(size)))
        body_font.setPixelSize(max(1, int(size)))
        title_font.setBold(True)
        selector["preview_title"].setFont(title_font)
        selector["preview_body"].setFont(body_font)

        def resize_preview_labels():
            title_label = selector["preview_title"]
            body_label = selector["preview_body"]
            preview = selector.get("preview")
            title_height = title_label.fontMetrics().lineSpacing() + 6
            body_width = max(120, body_label.width())
            body_height = body_label.heightForWidth(body_width)
            if body_height < 0:
                body_height = body_label.fontMetrics().lineSpacing()
            title_label.setMinimumHeight(title_height)
            body_label.setMinimumHeight(body_height + 8)
            if preview and preview.layout():
                margins = preview.layout().contentsMargins()
                spacing = preview.layout().spacing()
                preview.setMinimumHeight(title_height + body_height + margins.top() + margins.bottom() + spacing + 12)
                preview.layout().activate()
                preview.updateGeometry()

        resize_preview_labels()
        selector["preview_title"].updateGeometry()
        selector["preview_body"].updateGeometry()
        QTimer.singleShot(0, resize_preview_labels)
        self._update_font_preview_mode_styles()

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

        def add_font_widget(widget, *grid_args):
            if isinstance(grid_layout, FlowLayout):
                grid_layout.addWidget(widget)
            else:
                grid_layout.addWidget(widget, *grid_args)

        # Add the "System" font card first, spanning the full width
        if "system" in system_fonts:
            system_card = FontCardWidget("system", self.accent_color, self, is_system_card=True)
            font_cards.append(system_card)
            add_font_widget(system_card, row, 0, 1, num_cols)
            row += 1 # Move to the next row

        # <<< START MODIFICATION >>>
        # Move the "Add Your Own Font" button to be directly under the "System" button
        add_button = QPushButton(tr("add_your_font"))
        add_button.setObjectName("fontAddButton")
        add_button.setMinimumHeight(54)
        add_button.setMinimumWidth(180)
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.clicked.connect(self._add_user_font)
        add_font_widget(add_button, row, 0, 1, num_cols)
        row += 1 # Move to the next row for the regular fonts
        # <<< END MODIFICATION >>>

        def add_card_to_grid(font_key):
            nonlocal row, col
            delete_icon = self._create_delete_icon()
            card = FontCardWidget(font_key, self.accent_color, self, delete_icon=delete_icon)
            if all_fonts[font_key].get("user"):
                card.delete_requested.connect(lambda key=font_key: self._delete_user_font(key))
            font_cards.append(card)
            add_font_widget(card, row, col)
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
        for card in font_cards:
            card.clicked.connect(lambda checked=False, selected=card, key=config_key: self._select_font_card(key, selected))

    def _select_font_card(self, config_key, selected_card):
        for card in getattr(self, f"font_cards_{config_key}", []):
            card.blockSignals(True)
            card.setChecked(card is selected_card)
            card.blockSignals(False)

    def _add_user_font(self):
        user_fonts_dir = os.path.join(self.addon_path, "user_files", "fonts")
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Font File", "", "Font Files (*.ttf *.otf *.woff *.woff2)")
        
        if not filepath:
            return
            
        filename = os.path.basename(filepath)
        dest_path = os.path.join(user_fonts_dir, filename)
        
        try:
            shutil.copy(filepath, dest_path)
            show_settings_toast(self, f"{tr('font_added_toast', 'Font added:')} {filename}")
            self._refresh_font_selectors()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not copy font file: {e}")

    def _refresh_font_selectors(self):
        selectors = getattr(self, "font_selectors", {})
        self._font_family_cache.clear()
        all_fonts = get_all_fonts(self.addon_path)
        ordered_keys = ["system", "instrument_serif", "nunito", "montserrat", "space_mono"]
        ordered_keys += sorted([key for key, info in all_fonts.items() if info.get("user")])
        for config_key, selector in selectors.items():
            combo = selector["combo"]
            current = combo.currentData() or mw.col.conf.get(f"onigiri_font_{config_key}", "system")
            combo.blockSignals(True)
            combo.clear()
            for font_key in ordered_keys:
                info = all_fonts.get(font_key)
                if not info:
                    continue
                display_name = tr("system") if font_key == "system" else info.get("name", font_key)
                combo.addItem(display_name, font_key)
            idx = combo.findData(current)
            combo.setCurrentIndex(idx if idx >= 0 else max(0, combo.findData("system")))
            combo.blockSignals(False)
            self._update_font_preview(config_key)

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
                    for key in ["main", "subtle", "small_title"]:
                        if mw.col.conf.get(f"onigiri_font_{key}") == font_key:
                            mw.col.conf[f"onigiri_font_{key}"] = "system"
                    
                    show_settings_toast(self, f"{tr('font_deleted_toast', 'Font deleted:')} {font_key}")
                    if hasattr(self, "font_selectors"):
                        self._refresh_font_selectors()
                    elif hasattr(self, "font_grids"):
                        self._populate_font_grid("main")
                        self._populate_font_grid("subtle")
                        self._populate_font_grid("small_title")
                else:
                    QMessageBox.warning(self, "Error", "Font file not found.")
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Could not delete font file: {e}")

    def create_fonts_page(self):
        page, layout = self._create_scrollable_page()
        layout.setContentsMargins(0, 8, 8, 24)

        self.font_preview_mode = "dark" if theme_manager.night_mode else "light"
        preview_toggle, self.font_preview_mode_toggle = self._create_light_dark_mode_toggle(
            self.font_preview_mode,
            lambda mode: self._set_font_preview_mode(mode)
        )
        header = QWidget()
        header.setObjectName("fontsPageHeader")
        header.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 8, 8)
        header_layout.setSpacing(12)
        title = QLabel(tr("fonts"))
        title.setStyleSheet(f"font-size: 24px; font-weight: 400; color: {self._settings_palette().get('--fg', '#202124')}; background: transparent;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(preview_toggle)
        page.layout().insertWidget(0, header)
        
        text_group = self._create_font_selector_group(tr("text"), "main")
        subtle_group = self._create_font_selector_group(tr("titles"), "subtle")
        small_title_group = self._create_font_selector_group(tr("small_titles"), "small_title")
        
        layout.addWidget(text_group)
        layout.addWidget(subtle_group)
        layout.addWidget(small_title_group)

        sections = {}
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections)

        return page

    def _save_fonts_settings(self):
        if hasattr(self, "font_selectors"):
            for key, selector in self.font_selectors.items():
                mw.col.conf[f"onigiri_font_{key}"] = selector["combo"].currentData() or "system"
        else:
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

        for mode in ["light", "dark"]:
            for key in ["--fg", "--fg-subtle", "--font-small-title-color"]:
                if key in self.color_widgets[mode]:
                    self.current_config["colors"][mode][key] = self.color_widgets[mode][key].text()

    def _box_effect_preview_font(self, config_key, fallback_size):
        font_key = mw.col.conf.get(f"onigiri_font_{config_key}", "system")
        size = int(mw.col.conf.get(f"onigiri_font_size_{config_key}", fallback_size) or fallback_size)
        font_info = get_all_fonts(self.addon_path).get(font_key, {})
        family = str(font_info.get("family", "") or "")
        if family and "," not in family and not family.startswith("-apple"):
            font = QFont(family, size)
        else:
            font = QFont(self.font())
            font.setPointSize(size)
        return font

