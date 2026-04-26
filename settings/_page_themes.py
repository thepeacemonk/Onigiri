class ThemesPageMixin:
    def create_themes_page(self):
        page, layout = self._create_scrollable_page()

        # --- Load Themes ---
        official_themes, user_themes = self._load_themes()

        # --- Section 1: Official Themes ---
        official_section = SectionGroup(
            "Official Themes",
            self,
            border=True,
            description="Choose from a selection of built-in color palettes."
        )
        # --- FIX START ---
        # Create the grid layout separately...
        self.official_themes_grid_layout = QGridLayout()
        self.official_themes_grid_layout.setSpacing(15)
        # ...and then add it to the section using its helper method.
        official_section.add_layout(self.official_themes_grid_layout)
        # --- FIX END ---
        self._populate_grid_with_themes(self.official_themes_grid_layout, official_themes, deletable=False)
        layout.addWidget(official_section)

        # --- Section 2: Your Themes ---
        user_section = SectionGroup(
            "Your Themes",
            self,
            border=True,
            description="Themes you have created or imported."
        )

        # Add navigation buttons
        sections = {
            "Official Themes": official_section,
            "Your Themes": user_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections)
        # --- FIX START ---
        # Do the same for the user themes section.
        self.user_themes_grid_layout = QGridLayout()
        self.user_themes_grid_layout.setSpacing(15)
        user_section.add_layout(self.user_themes_grid_layout)
        # --- FIX END ---
        self._populate_grid_with_themes(self.user_themes_grid_layout, user_themes, deletable=True)
        layout.addWidget(user_section)

        # --- Action Buttons (remain the same) ---
        button_layout = QHBoxLayout()
        import_button = QPushButton("Import Theme")
        import_button.clicked.connect(self._import_theme)

        export_button = QPushButton("Export Current Theme")
        export_button.setToolTip("Saves your current color settings as a new theme file.")
        export_button.clicked.connect(self._export_current_theme)

        reset_button = QPushButton("Reset Theme to Default")
        reset_button.setToolTip("Resets all theme and palette colors to the add-on's original defaults.")
        reset_button.clicked.connect(self.reset_theme_to_default)

        button_layout.addWidget(import_button)
        button_layout.addWidget(export_button)
        button_layout.addStretch()
        button_layout.addWidget(reset_button)

        layout.addLayout(button_layout)
        layout.addStretch()
        return page


    def _apply_theme(self, theme_data: dict):
        """Applies the selected theme's colors and assets to the config and live UI."""
        light_palette = theme_data.get("light", {})
        dark_palette = theme_data.get("dark", {})
        assets = theme_data.get("assets", {})

        # 1. Update the internal config dictionary
        self.current_config["colors"]["light"].update(light_palette)
        self.current_config["colors"]["dark"].update(dark_palette)

        # 1b. Apply Assets (Images and Icons)
        if "images" in assets:
            for config_key, path in assets["images"].items():
                if os.path.exists(path):
                    # Config expects filenames relative to their folders for most keys
                    # Theme data now holds absolute paths (for preview validation)
                    # So we convert to basename for config application
                    self.current_config[config_key] = os.path.basename(path)

                    # For legacy keys in mw.col.conf, sync them too
                    if config_key.startswith("modern_menu_"):
                        mw.col.conf[config_key] = os.path.basename(path)

                    # Also explicit sync for onigiri_ keys if needed? 
                    # usually self.current_config syncs back on save, but we are applying LIVE.
                    # _apply_theme usually updates widgets.
                    # We should probably update the radio buttons / widgets too?
                    # The original _apply_theme didn't do that for images.
                    # But if we want instant feedback, we might need to.
                    # However, simply setting config might trigger hooks if any?
                    # For now, ensuring config is correct is step 1.

        if "icons" in assets:
            applied_icons = []
            for icon_key, icon_value in assets["icons"].items():
                # icon_value should be just the filename (from import)
                # But use basename to be safe
                filename = os.path.basename(icon_value) if icon_value else ""
                if filename:
                    conf_key = f"modern_menu_icon_{icon_key}"
                    mw.col.conf[conf_key] = filename
                    applied_icons.append(f"{icon_key}: {filename}")

            if applied_icons:
                icon_msg = f"\n\nApplied {len(applied_icons)} custom icon(s):\n" + "\n".join(applied_icons[:5])
            else:
                icon_msg = ""
        else:
            icon_msg = ""

        # 1c. Apply Fonts
        if "font_config" in assets:
            for type_key, font_key in assets["font_config"].items():
                if type_key in ["main", "subtle"]:
                    mw.col.conf[f"onigiri_font_{type_key}"] = font_key

        # 1c. Apply Fonts
        if "font_config" in assets:
            for type_key, font_key in assets["font_config"].items():
                if type_key in ["main", "subtle"]:
                    mw.col.conf[f"onigiri_font_{type_key}"] = font_key

        # 1d. Apply Reviewer Settings
        if "reviewer_settings" in theme_data:
            self.current_config.update(theme_data["reviewer_settings"])

        # 2. Update the UI widgets on other pages in real-time
        # This uses hasattr to avoid errors if a page hasn't been loaded yet

        # Update Palette page
        for mode, palette in [("light", light_palette), ("dark", dark_palette)]:
            if mode in self.color_widgets:
                for key, widget in self.color_widgets[mode].items():
                    if key in palette:
                        widget.setText(palette[key])

        # Update Accent colors
        if hasattr(self, "light_accent_color_input") and "--accent-color" in light_palette:
            self.light_accent_color_input.setText(light_palette["--accent-color"])
        if hasattr(self, "dark_accent_color_input") and "--accent-color" in dark_palette:
            self.dark_accent_color_input.setText(dark_palette["--accent-color"])

        # Update Backgrounds page
        if hasattr(self, "bg_light_color_input") and "--bg" in light_palette:
            self.bg_light_color_input.setText(light_palette["--bg"])
        if hasattr(self, "bg_dark_color_input") and "--bg" in dark_palette:
            self.bg_dark_color_input.setText(dark_palette["--bg"])

        # Update Icon previews after applying icons
        if "icons" in assets and hasattr(self, "icon_widgets"):
            for icon_key in assets["icons"].keys():
                if icon_key in self.icon_widgets:
                    control_widget = self.icon_widgets[icon_key]
                    preview_label = control_widget.property("preview_label")
                    if preview_label:
                        # Reload the icon preview
                        conf_key = f"modern_menu_icon_{icon_key}"
                        new_filename = mw.col.conf.get(conf_key, "")
                        if new_filename:
                            icon_path = os.path.join(self.addon_path, "user_files", "icons", new_filename)
                            if os.path.exists(icon_path):
                                # Update preview with new icon
                                pixmap = QPixmap(icon_path)
                                if not pixmap.isNull():
                                    scaled = pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                                    preview_label.setPixmap(scaled)

        showInfo(f"Theme applied! Press 'Save' to keep the changes.{icon_msg}")


    def _load_themes(self):
        """Loads built-in and custom themes, returning them as separate dictionaries."""
        official_themes = THEMES.copy()
        user_themes = {}

        # Load user themes from JSON files
        for filename in os.listdir(self.user_themes_path):
            if filename.lower().endswith(".json"):
                filepath = os.path.join(self.user_themes_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        theme_data = json.load(f)

                    # Basic validation
                    if isinstance(theme_data, dict) and "light" in theme_data and "dark" in theme_data:
                        theme_name = os.path.splitext(filename)[0].replace("_", " ").title()
                        user_themes[theme_name] = theme_data
                    else:
                        print(f"Onigiri: Invalid theme file format in {filename}")
                except (json.JSONDecodeError, OSError) as e:
                    print(f"Onigiri: Could not load theme file {filename}: {e}")

        return official_themes, user_themes


    def _populate_grid_with_themes(self, grid_layout, themes_dict, deletable=False):
        """Helper function to populate a given QGridLayout with theme cards."""
        while grid_layout.count():
            child = grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not themes_dict:
            if deletable:
                grid_layout.addWidget(QLabel("No custom themes have been imported yet."), 0, 0)
            return

        # Create the icon once, before the loop
        delete_icon = self._create_delete_icon() if deletable else None

        row, col = 0, 0
        num_cols = 2

        for name, data in sorted(themes_dict.items()):
            card = ThemeCardWidget(name, data, deletable=deletable, delete_icon=delete_icon)
            card.theme_selected.connect(self._apply_theme)
            if deletable:
                card.delete_requested.connect(self._delete_user_theme) # Connect the new signal

            grid_layout.addWidget(card, row, col)

            col += 1
            if col >= num_cols:
                col = 0; row += 1


    def _import_theme(self):
        """Opens a file dialog to import a theme from a JSON or .onigiri file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, 
            "Import Theme", 
            "", 
            "Onigiri Theme Files (*.json *.onigiri);;JSON Files (*.json);;Onigiri Files (*.onigiri)"
        )
        if not filepath:
            return

        try:
            filename = os.path.basename(filepath)

            # Handle .json files (legacy)
            if filename.lower().endswith(".json"):
                with open(filepath, 'r', encoding='utf-8') as f:
                    theme_data = json.load(f)

                # Validate
                if not isinstance(theme_data, dict) or "light" not in theme_data or "dark" not in theme_data:
                    QMessageBox.warning(self, "Import Error", "The selected file is not a valid Onigiri theme file.")
                    return

                # Copy
                dest_path = os.path.join(self.user_themes_path, filename)
                shutil.copy(filepath, dest_path)

            # Handle .onigiri files (zip)
            elif filename.lower().endswith(".onigiri"):
                import zipfile
                if not zipfile.is_zipfile(filepath):
                    QMessageBox.warning(self, "Import Error", "The selected file is not a valid zip archive.")
                    return

                with zipfile.ZipFile(filepath, 'r') as zf:
                    # 1. Read theme.json
                    try:
                        with zf.open('theme.json') as f:
                            theme_data = json.load(f)
                    except KeyError:
                        QMessageBox.warning(self, "Import Error", "The .onigiri file is missing 'theme.json'.")
                        return

                    # 2. Extract Assets
                    # We will modify theme_data to point to the new extracted locations
                    assets = theme_data.get("assets", {})
                    theme_name = os.path.splitext(filename)[0] # e.g. "My_Theme"

                    # Prepare directories
                    images_dest_dir = os.path.join(self.addon_path, "user_files", "images", theme_name)
                    fonts_dest_dir = os.path.join(self.addon_path, "user_files", "fonts")
                    icons_dest_dir = os.path.join(self.addon_path, "user_files", "icons")

                    os.makedirs(images_dest_dir, exist_ok=True)
                    os.makedirs(fonts_dest_dir, exist_ok=True)
                    os.makedirs(icons_dest_dir, exist_ok=True)

                    # Extract Images
                    if "images" in assets:
                        for config_key, archive_path in assets["images"].items():
                            try:
                                # archive_path is like "images/main_bg/bg.png" or "images/filename.png"
                                # We need to respect the subfolder if present
                                parts = archive_path.split("/")
                                if len(parts) >= 3 and parts[0] == "images":
                                    # images/subfolder/filename
                                    subfolder = parts[1]
                                    filename = parts[-1]
                                    dest_dir = os.path.join(self.addon_path, "user_files", subfolder)
                                else:
                                    # Fallback (old export or flat structure)
                                    subfolder = "images" # Should we dump to images? 
                                    # If legacy export didn't use subfolders, we might have issues.
                                    # But we just implemented the "new" export. Let's assume theme_name/images separation if needed.
                                    # But better to try to guess based on config_key? 
                                    # No, let's just use a generic 'imported_assets' if unsure or stick to 'images/{ThemeName}' logic from before?
                                    # The 'new' export I just wrote ALWAYS uses "images/subfolder/filename".
                                    # So we rely on that.
                                    # If not matching, we default to images/{ThemeName} from previous logic.
                                    dest_dir = images_dest_dir # defined earlier as user_files/images/{theme_name}
                                    filename = os.path.basename(archive_path)

                                os.makedirs(dest_dir, exist_ok=True)
                                target_path = os.path.join(dest_dir, filename)

                                # Read from zip and write to target
                                with zf.open(archive_path) as source, open(target_path, "wb") as target:
                                    shutil.copyfileobj(source, target)

                                # Update theme_data to point to absolute path
                                # This allows ThemeCardWidget to finding the preview image immediately
                                theme_data["assets"]["images"][config_key] = target_path
                            except KeyError:
                                print(f"Asset {archive_path} not found in zip.")

                    # Extract Fonts
                    if "fonts" in assets:
                         for font_key, archive_path in assets["fonts"].items():
                            try:
                                asset_filename = os.path.basename(archive_path)
                                target_path = os.path.join(fonts_dest_dir, asset_filename)
                                with zf.open(archive_path) as source, open(target_path, "wb") as target:
                                    shutil.copyfileobj(source, target)
                                # We don't need to update reference in theme_data if it uses filename as key
                                # But if we stored archive_path, we might? 
                                # Export stored key -> archive_path.
                                # Fonts.py loads all from user_files/fonts. 
                                # So by just placing it there, it becomes available.
                            except KeyError:
                                pass

                    # Extract Icons
                    if "icons" in assets:
                        for icon_key, archive_path in assets["icons"].items():
                            try:
                                asset_filename = os.path.basename(archive_path)
                                target_path = os.path.join(icons_dest_dir, asset_filename)
                                with zf.open(archive_path) as source, open(target_path, "wb") as target:
                                    shutil.copyfileobj(source, target)

                                # Update theme data with just the filename
                                theme_data["assets"]["icons"][icon_key] = asset_filename
                            except KeyError:
                                pass

                    # Preserve icon_config if it exists (for preview)
                    # icon_config contains all icon selections (including defaults)
                    # We don't need to modify it, just ensure it's in theme_data

                    # 3. Save the modified theme.json to user_themes
                    # We rename it to match the .onigiri filename
                    json_filename = theme_name + ".json"
                    json_dest_path = os.path.join(self.user_themes_path, json_filename)

                    with open(json_dest_path, 'w', encoding='utf-8') as f:
                        json.dump(theme_data, f, indent=4)

            # Refresh the grid to show the new theme
            _, user_themes = self._load_themes()
            self._populate_grid_with_themes(self.user_themes_grid_layout, user_themes)
            showInfo("Theme imported successfully!")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Could not import the theme file:\n{e}")


    def _export_current_theme(self):
        """Gathers ALL current theme colors and assets, saving them to a .onigiri zip file."""
        name, ok = QInputDialog.getText(self, "Export Theme", "Enter a name for your theme:")
        if not ok or not name:
            return

        light_palette = {}
        dark_palette = {}

        # 1. Gather Colors
        for mode, palette in [("light", light_palette), ("dark", dark_palette)]:
            for key in ALL_THEME_KEYS:
                # Default to the value in the in-memory config
                value = self.current_config["colors"][mode].get(key)

                # Check UI widgets for latest values
                if key == "--accent-color" and hasattr(self, f"{mode}_accent_color_input"):
                    value = getattr(self, f"{mode}_accent_color_input").text()
                elif key == "--bg" and hasattr(self, f"bg_{mode}_color_input"):
                    value = getattr(self, f"bg_{mode}_color_input").text()
                elif key in self.color_widgets.get(mode, {}):
                    value = self.color_widgets[mode][key].text()

                if value is not None:
                    palette[key] = value

        # 1b. Gather Reviewer Settings
        reviewer_settings = {}
        for key in REVIEWER_THEME_KEYS:
            value = self.current_config.get(key)
            if value is not None:
                reviewer_settings[key] = value

        theme_data = {
            "light": light_palette, 
            "dark": dark_palette,
            "reviewer_settings": reviewer_settings,
            "assets": {
                "fonts": {}, # Map: local_filename -> archive_path
                "images": {},
                "icons": {},
                "font_config": {}, # Store which font key is selected for main/subtle
                "icon_config": {} # Store which icons are selected (even if defaults)
            }
        }

        # 2. Gather Assets
        assets_to_zip = [] # List of tuples: (source_path, archive_name)

        # Fonts
        # Check active fonts in config
        for font_type in ["main", "subtle"]:
            font_key = mw.col.conf.get(f"onigiri_font_{font_type}")
            if font_key:
                # Save the configuration selection
                theme_data["assets"]["font_config"][font_type] = font_key

                # If it's a user font, we assume the key is the filename (as per fonts.py: load_user_fonts)
                # We check if it exists in user_files/fonts
                font_path = os.path.join(self.addon_path, "user_files", "fonts", font_key)
                if os.path.exists(font_path) and os.path.isfile(font_path):
                    archive_path = f"fonts/{font_key}"
                    # Avoid adding duplicates
                    if not any(a[1] == archive_path for a in assets_to_zip):
                        assets_to_zip.append((font_path, archive_path))
                        # We list it in assets["fonts"] just to track what's included
                        theme_data["assets"]["fonts"][font_key] = archive_path

        # Images
        # Map config keys to their respective subfolders in user_files
        image_key_map = {
            "modern_menu_background_image": "main_bg",
            "modern_menu_background_image_light": "main_bg",
            "modern_menu_background_image_dark": "main_bg",
            "onigiri_overview_bg_image": "main_bg",
            "onigiri_overview_bg_image_light": "main_bg",
            "onigiri_overview_bg_image_dark": "main_bg",
            "modern_menu_profile_bg_image": "profile_bg",
            "modern_menu_profile_picture": "profile",
            "modern_menu_sidebar_bg_image": "sidebar_bg",
            "onigiri_reviewer_bg_image": "reviewer_bg", 
            "onigiri_reviewer_bg_image_light": "reviewer_bg",
            "onigiri_reviewer_bg_image_dark": "reviewer_bg",
            "onigiri_reviewer_bottom_bar_bg_image": "reviewer_bar_bg",
        }

        active_images = {}
        for key, subfolder in image_key_map.items():
            # config often holds just the filename
            # We try self.current_config first, then mw.col.conf
            filename = self.current_config.get(key) or mw.col.conf.get(key)

            if filename and isinstance(filename, str):
                # Construct possible full path
                full_path = os.path.join(self.addon_path, "user_files", subfolder, filename)

                if os.path.exists(full_path) and os.path.isfile(full_path):
                    archive_path = f"images/{subfolder}/{filename}"
                    # Avoid duplicates
                    if not any(a[1] == archive_path for a in assets_to_zip):
                        assets_to_zip.append((full_path, archive_path))

                    active_images[key] = archive_path # Store archive path in theme.json

        theme_data["assets"]["images"] = active_images

        # Icons
        # Similar logic for icons. 
        # We need to find which icons are customized. 
        # `settings.py` creates icon widgets based on `modern_menu_icon_{key}` in `mw.col.conf`.
        # Note: Icons seem to be stored in `mw.col.conf`, not `self.current_config` (which mimics the add-on config).
        # We should check `mw.col.conf` for `modern_menu_icon_*`.

        active_icons = {}
        icon_config = {}

        # Iterate over all possible icon keys (we can get them from ICON_DEFAULTS)
        for icon_key in ICON_DEFAULTS.keys():
            conf_key = f"modern_menu_icon_{icon_key}"
            filename = mw.col.conf.get(conf_key, "")

            # Always save the configuration (even if it's empty/default)
            # This allows preview to show defaults
            icon_config[icon_key] = filename if filename else icon_key  # Use key for defaults

            if filename:
                filepath = os.path.join(self.addon_path, "user_files/icons", filename)
                if os.path.exists(filepath):
                    archive_path = f"icons/{filename}"
                    assets_to_zip.append((filepath, archive_path))
                    active_icons[icon_key] = archive_path

        theme_data["assets"]["icons"] = active_icons
        theme_data["assets"]["icon_config"] = icon_config

        # 3. Create Zip
        suggested_filename = name.lower().replace(" ", "_") + ".onigiri"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Theme As",
            os.path.join(self.user_themes_path, suggested_filename),
            "Onigiri Theme Files (*.onigiri)"
        )

        if not save_path:
            return

        try:
            import zipfile
            with zipfile.ZipFile(save_path, 'w') as zf:
                # Write theme.json
                zf.writestr('theme.json', json.dumps(theme_data, indent=4))

                # Write assets
                for source, dest in assets_to_zip:
                    zf.write(source, dest)

            showInfo(f"Theme '{name}' exported successfully as .onigiri file!")

            # If saved in local themes folder, refresh? 
            # (Currently .onigiri files might not appear until we implement the import/view logic)
            # For now, standard JSON themes are loaded. 
            # We might want to auto-extract it back to be usable immediately if saved locally?
            # Or just leave it as an export file. The user said "Import, export".

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Could not save the theme file:\n{e}")


    def reset_theme_to_default(self):
        """Resets all theme-related colors to their default values."""
        # Use a deep copy to avoid modifying the DEFAULTS constant
        default_colors = json.loads(json.dumps(DEFAULTS["colors"]))

        # 1. Update the internal config dictionary with the defaults
        self.current_config["colors"] = default_colors

        # 2. Update all relevant UI widgets if they have been created
        for mode, palette in default_colors.items():
            if mode not in ["light", "dark"]:
                continue

            # Update general color inputs (Palette, Sidebar, Main Menu, etc.)
            if mode in self.color_widgets:
                for key, widget in self.color_widgets[mode].items():
                    if key in palette:
                        widget.setText(palette[key])

            # Update Accent Color inputs
            if hasattr(self, f"{mode}_accent_color_input") and "--accent-color" in palette:
                getattr(self, f"{mode}_accent_color_input").setText(palette["--accent-color"])

            # Update the main Background Color input on the Backgrounds page
            if hasattr(self, f"bg_{mode}_color_input") and "--bg" in palette:
                getattr(self, f"bg_{mode}_color_input").setText(palette["--bg"])

        # 3. Refresh the settings dialog's own appearance
        self.apply_stylesheet()

        # 4. Inform the user
        showInfo("Theme colors have been reset to default. Press 'Save' to keep the changes.")


    def _delete_user_theme(self, theme_name: str):
        """Prompts for confirmation and deletes a user theme file."""
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to permanently delete the theme '{theme_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Convert theme name to filename (e.g., "My Awesome Theme" -> "my_awesome_theme.json")
            filename = theme_name.lower().replace(" ", "_") + ".json"
            filepath = os.path.join(self.user_themes_path, filename)

            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    showInfo(f"Theme '{theme_name}' deleted.")

                    # Refresh the user themes grid
                    _, user_themes = self._load_themes()
                    self._populate_grid_with_themes(self.user_themes_grid_layout, user_themes, deletable=True)
                else:
                    QMessageBox.warning(self, "Error", f"Could not find theme file: {filename}")
            except OSError as e:
                QMessageBox.critical(self, "Error", f"Could not delete theme file:\n{e}")

    # <<< START NEW CODE >>>

