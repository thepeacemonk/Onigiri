class GalleryPageMixin:
    def create_gallery_page(self):
        """Create a Gallery page showing all applied colors and user images."""
        page, layout = self._create_scrollable_page()

        # === COLORS GALLERY SECTION ===
        colors_section = SectionGroup(
            "Colors Gallery",
            self,
            description="All colors currently applied in the add-on. Click any color circle to go to its settings page."
        )

        # Define color categories with their keys and the settings page they belong to
        color_categories = {
            "Palette": (
                "Palette",
                ["--accent-color", "--fg", "--fg-subtle",
                 "--border", "--canvas-inset", "--icon-color"]
            ),
            "Main Menu": (
                "Main menu",
                ["--bg", "--heatmap-color", "--heatmap-color-zero",
                 "--star-color", "--empty-star-color"]
            ),
            "Sidebar": (
                "Sidebar",
                ["--highlight-bg", "--deck-hover-bg", "--deck-dragging-bg", "--deck-edit-mode-bg"]
            ),
            "Overviewer": (
                "Overviewer",
                ["--button-primary-bg", "--button-primary-gradient-start",
                 "--button-primary-gradient-end",
                 "--new-count-bubble-bg", "--new-count-bubble-fg",
                 "--learn-count-bubble-bg", "--learn-count-bubble-fg",
                 "--review-count-bubble-bg", "--review-count-bubble-fg"]
            ),
        }

        # Answer button colors (stored in config, not colors dict) → navigate to Reviewer
        answer_button_colors = {
            "light": {
                "Again BG": "onigiri_reviewer_btn_again_bg_light",
                "Again Text": "onigiri_reviewer_btn_again_text_light",
                "Hard BG": "onigiri_reviewer_btn_hard_bg_light",
                "Hard Text": "onigiri_reviewer_btn_hard_text_light",
                "Good BG": "onigiri_reviewer_btn_good_bg_light",
                "Good Text": "onigiri_reviewer_btn_good_text_light",
                "Easy BG": "onigiri_reviewer_btn_easy_bg_light",
                "Easy Text": "onigiri_reviewer_btn_easy_text_light",
            },
            "dark": {
                "Again BG": "onigiri_reviewer_btn_again_bg_dark",
                "Again Text": "onigiri_reviewer_btn_again_text_dark",
                "Hard BG": "onigiri_reviewer_btn_hard_bg_dark",
                "Hard Text": "onigiri_reviewer_btn_hard_text_dark",
                "Good BG": "onigiri_reviewer_btn_good_bg_dark",
                "Good Text": "onigiri_reviewer_btn_good_text_dark",
                "Easy BG": "onigiri_reviewer_btn_easy_bg_dark",
                "Easy Text": "onigiri_reviewer_btn_easy_text_dark",
            }
        }

        # Get current colors based on theme mode
        mode = "dark" if theme_manager.night_mode else "light"
        current_colors = self.current_config.get("colors", {}).get(mode, {})
        default_colors = DEFAULTS["colors"][mode]

        # Create a VERTICAL layout for Light and Dark mode sections (stacked for smaller windows)
        modes_layout = QVBoxLayout()
        modes_layout.setSpacing(15)

        # Determine label color based on current theme
        label_color = "#dddddd" if theme_manager.night_mode else "#555"

        # Swatch hover style
        swatch_hover_color = "rgba(255,255,255,0.15)" if theme_manager.night_mode else "rgba(0,0,0,0.08)"

        for display_mode, mode_name in [("light", "Light Mode"), ("dark", "Dark Mode")]:
            mode_colors = self.current_config.get("colors", {}).get(display_mode, {})
            mode_defaults = DEFAULTS["colors"][display_mode]

            mode_group, mode_layout = self._create_inner_group(mode_name)

            for category_name, (nav_page, color_keys) in color_categories.items():
                # Category title with clickable arrow hint
                cat_header_widget = QWidget()
                cat_header_layout = QHBoxLayout(cat_header_widget)
                cat_header_layout.setContentsMargins(0, 0, 0, 0)
                cat_header_layout.setSpacing(4)
                cat_label = QLabel(category_name)
                cat_label.setStyleSheet("font-weight: bold; margin-top: 10px; margin-bottom: 5px;")
                cat_header_layout.addWidget(cat_label)
                cat_header_layout.addStretch()
                mode_layout.addWidget(cat_header_widget)

                # Create a layout for color swatches, aligned to the left
                swatches_widget = QWidget()
                swatches_layout = QHBoxLayout(swatches_widget)
                swatches_layout.setContentsMargins(0, 0, 0, 5)
                swatches_layout.setSpacing(8)

                for color_key in color_keys:
                    color_value = mode_colors.get(color_key, mode_defaults.get(color_key, "#888888"))
                    label_info = COLOR_LABELS.get(color_key, {"label": color_key.replace("--", "").replace("-", " ").title()})
                    full_label = label_info["label"]

                    # Create clickable swatch container — wider so full names are visible
                    swatch_container = QWidget()
                    swatch_container.setFixedSize(80, 80)
                    full_tooltip = f"{full_label}\n{color_value}\n\nClick to go to {category_name} settings"
                    swatch_container.setToolTip(full_tooltip)
                    swatch_container.setCursor(Qt.CursorShape.PointingHandCursor)
                    swatch_v_layout = QVBoxLayout(swatch_container)
                    swatch_v_layout.setContentsMargins(4, 6, 4, 4)
                    swatch_v_layout.setSpacing(4)

                    # Color circle (larger)
                    swatch = ColorSwatch(color_value)
                    swatch.setFixedSize(28, 28)
                    swatch_v_layout.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignCenter)

                    # Full label — word-wrapped, no truncation
                    name_label = QLabel(full_label)
                    name_label.setStyleSheet(f"font-size: 10px; color: {label_color};")
                    name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    name_label.setWordWrap(True)
                    name_label.setFixedWidth(74)
                    swatch_v_layout.addWidget(name_label)

                    # Make container clickable - navigate to settings page
                    _nav_page = nav_page  # capture for lambda
                    swatch_container.mousePressEvent = lambda event, p=_nav_page: self.navigate_to_page(p)

                    swatches_layout.addWidget(swatch_container)

                swatches_layout.addStretch()  # Keep swatches aligned left
                mode_layout.addWidget(swatches_widget)

            # Add Reviewer Answer Button Colors section (clickable → Reviewer page)
            reviewer_label = QLabel("Reviewer")
            reviewer_label.setStyleSheet("font-weight: bold; margin-top: 10px; margin-bottom: 5px;")
            mode_layout.addWidget(reviewer_label)

            btn_swatches_widget = QWidget()
            btn_swatches_layout = QHBoxLayout(btn_swatches_widget)
            btn_swatches_layout.setContentsMargins(0, 0, 0, 5)
            btn_swatches_layout.setSpacing(8)

            for label_name, config_key in answer_button_colors[display_mode].items():
                color_value = self.current_config.get(config_key, DEFAULTS.get(config_key, "#888888"))

                swatch_container = QWidget()
                swatch_container.setFixedSize(80, 80)
                swatch_container.setToolTip(f"{label_name}\n{color_value}\n\nClick to go to Reviewer settings")
                swatch_container.setCursor(Qt.CursorShape.PointingHandCursor)
                swatch_v_layout = QVBoxLayout(swatch_container)
                swatch_v_layout.setContentsMargins(4, 6, 4, 4)
                swatch_v_layout.setSpacing(4)

                swatch = ColorSwatch(color_value)
                swatch.setFixedSize(28, 28)
                swatch_v_layout.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignCenter)

                name_label = QLabel(label_name)
                name_label.setStyleSheet(f"font-size: 10px; color: {label_color};")
                name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                name_label.setWordWrap(True)
                name_label.setFixedWidth(74)
                swatch_v_layout.addWidget(name_label)

                # Clickable → navigate to Reviewer page
                swatch_container.mousePressEvent = lambda event, p="Reviewer": self.navigate_to_page(p)

                btn_swatches_layout.addWidget(swatch_container)

            btn_swatches_layout.addStretch()  # Keep swatches aligned left
            mode_layout.addWidget(btn_swatches_widget)

            modes_layout.addWidget(mode_group)

        colors_section.add_layout(modes_layout)
        layout.addWidget(colors_section)

        # === IMAGES GALLERY SECTION ===
        images_section = SectionGroup(
            "Images Gallery",
            self,
            description="All images uploaded to the add-on, organized by location. Click any image to go to its settings page."
        )

        # Define image directories with the settings page to navigate to
        image_directories = [
            ("Profile Pictures", "user_files/profile", "Profile"),
            ("Profile Backgrounds", "user_files/profile_bg", "Profile"),
            ("Main Menu Backgrounds", "user_files/main_bg", "Main menu"),
            ("Sidebar Backgrounds", "user_files/sidebar_bg", "Sidebar"),
            ("Reviewer Backgrounds", "user_files/reviewer_bg", "Reviewer"),
            ("Reviewer Bar Backgrounds", "user_files/reviewer_bar_bg", "Reviewer"),
        ]

        extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp")

        for title, folder_path, img_nav_page in image_directories:
            full_path = os.path.join(self.addon_path, folder_path)

            # Get image files
            try:
                if os.path.exists(full_path):
                    image_files = sorted([f for f in os.listdir(full_path) if f.lower().endswith(extensions)])
                else:
                    image_files = []
            except OSError:
                image_files = []

            # Create subsection - no image count in title
            subsection_group, subsection_layout = self._create_inner_group(title)

            if image_files:
                # Create a scroll area for thumbnails
                scroll_area = QScrollArea()
                scroll_area.setWidgetResizable(True)
                scroll_area.setFixedHeight(80)  # Reduced height for smaller windows
                scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

                content_widget = QWidget()
                grid_layout = QHBoxLayout(content_widget)
                grid_layout.setSpacing(6)  # Reduced spacing
                grid_layout.setContentsMargins(4, 4, 4, 4)
                grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

                for filename in image_files[:20]:  # Limit to 20 images per section
                    img_path = os.path.join(full_path, filename)

                    # Use a clickable container instead of plain QLabel
                    thumb_container = QWidget()
                    thumb_container.setFixedSize(64, 48)
                    thumb_container.setCursor(Qt.CursorShape.PointingHandCursor)
                    thumb_container.setToolTip(f"{filename}\n\nClick to go to {title} settings")
                    thumb_container_layout = QVBoxLayout(thumb_container)
                    thumb_container_layout.setContentsMargins(0, 0, 0, 0)

                    thumb_label = QLabel()
                    thumb_label.setFixedSize(64, 48)  # Smaller thumbnails
                    thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

                    # Load and scale thumbnail
                    pixmap = QPixmap(img_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(
                            60, 44,  # Slightly smaller for padding
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        # Center crop
                        x = (scaled.width() - 60) // 2
                        y = (scaled.height() - 44) // 2
                        cropped = scaled.copy(x, y, 60, 44)
                        rounded = create_rounded_pixmap(cropped, 6)
                        thumb_label.setPixmap(rounded)
                    else:
                        thumb_label.setText("?")
                        thumb_label.setStyleSheet("background: rgba(128,128,128,0.2); border-radius: 6px;")

                    thumb_container_layout.addWidget(thumb_label)

                    # Make the whole thumbnail clickable → navigate to settings page
                    _img_page = img_nav_page  # capture for lambda
                    thumb_container.mousePressEvent = lambda event, p=_img_page: self.navigate_to_page(p)

                    grid_layout.addWidget(thumb_container)

                if len(image_files) > 20:
                    more_label = QLabel(f"+{len(image_files) - 20} more")
                    more_label.setStyleSheet("color: #888; font-size: 11px;")
                    grid_layout.addWidget(more_label)

                grid_layout.addStretch()
                scroll_area.setWidget(content_widget)
                subsection_layout.addWidget(scroll_area)
            else:
                no_files = QLabel("No images uploaded")
                no_files.setStyleSheet("color: #888; font-style: italic; padding: 10px;")
                subsection_layout.addWidget(no_files)

            images_section.add_widget(subsection_group)

        layout.addWidget(images_section)
        layout.addStretch()

        # Add navigation buttons
        sections_map = {
            "Colors": colors_section,
            "Images": images_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections_map)

        return page




