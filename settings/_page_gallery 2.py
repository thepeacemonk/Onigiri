# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *



class PageGalleryMixin:
    def _gallery_action_button_style(self):
        palette = self._settings_palette()
        border = palette.get("--border", "#dcdde1")
        bg = palette.get("--highlight-bg", "#f3f4f6")
        hover = palette.get("--canvas-inset", "#ffffff")
        fg = palette.get("--fg", "#202124")
        muted = palette.get("--fg-subtle", "#6f7177")
        return f"""
            QPushButton#galleryAssetActionButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 13px;
                padding: 0px 12px;
                font-size: 11px;
                font-weight: 700;
                min-height: 26px;
            }}
            QPushButton#galleryAssetActionButton:hover {{
                background-color: {hover};
                color: {fg};
            }}
            QPushButton#galleryAssetDeleteButton {{
                background-color: {bg};
                color: {muted};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 0px 8px;
                font-size: 10px;
                font-weight: 700;
                min-height: 24px;
            }}
            QPushButton#galleryAssetDeleteButton:hover {{
                background-color: {hover};
                color: #d64545;
            }}
        """

    def _rounded_gallery_pixmap(self, image_path, size, radius=10):
        source = QPixmap(image_path)
        target = QPixmap(size)
        target.fill(Qt.GlobalColor.transparent)
        if source.isNull():
            return target

        scaled = source.scaled(size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        x = max(0, (scaled.width() - size.width()) // 2)
        y = max(0, (scaled.height() - size.height()) // 2)
        cropped = scaled.copy(x, y, size.width(), size.height())

        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, size.width(), size.height()), radius, radius)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        return target

    def _reload_gallery_page(self, scroll_value=None):
        if not hasattr(self, "content_stack") or "Gallery" not in getattr(self, "page_order", []):
            return
        stack_index = self.page_order.index("Gallery")
        create_func = self.pages.get("Gallery")
        if not create_func:
            return
        old_widget = self.content_stack.widget(stack_index)
        old_scroll = old_widget.findChild(QScrollArea, "settingsPageScroll") if old_widget else None
        if scroll_value is None and old_scroll:
            scroll_value = old_scroll.verticalScrollBar().value()
        self._building_page_name = "Gallery"
        try:
            new_widget = create_func()
        finally:
            self._building_page_name = None
        self._polish_created_page(new_widget)
        self.content_stack.removeWidget(old_widget)
        self.content_stack.insertWidget(stack_index, new_widget)
        old_widget.deleteLater()
        self.tabs_loaded[stack_index] = True
        if getattr(self, "_current_page_name", None) == "Gallery":
            self.content_stack.setCurrentIndex(stack_index)
            self._populate_page_nav("Gallery")
        if scroll_value is not None:
            new_scroll = new_widget.findChild(QScrollArea, "settingsPageScroll")
            if new_scroll:
                def restore_scroll():
                    scrollbar = new_scroll.verticalScrollBar()
                    scrollbar.setValue(min(scroll_value, scrollbar.maximum()))

                restore_scroll()
                QTimer.singleShot(0, restore_scroll)

    def _unique_gallery_asset_filename(self, folder_path, filename):
        base, ext = os.path.splitext(os.path.basename(filename))
        candidate = os.path.basename(filename)
        counter = 2
        while os.path.exists(os.path.join(folder_path, candidate)):
            candidate = f"{base}-{counter}{ext}"
            counter += 1
        return candidate

    def _import_gallery_asset(self, folder_path, extensions):
        ext_filter = f"Files (*{' *'.join(extensions)})"
        filepath, _ = QFileDialog.getOpenFileName(self, tr("import_image"), "", ext_filter)
        if not filepath:
            return
        full_path = os.path.join(self.addon_path, folder_path)
        os.makedirs(full_path, exist_ok=True)
        filename = os.path.basename(filepath)
        dest_path = os.path.join(full_path, filename)
        if os.path.exists(dest_path) and os.path.abspath(filepath) != os.path.abspath(dest_path):
            filename = self._unique_gallery_asset_filename(full_path, filename)
            dest_path = os.path.join(full_path, filename)
        try:
            if os.path.abspath(filepath) != os.path.abspath(dest_path):
                shutil.copy(filepath, dest_path)
            QTimer.singleShot(0, self._reload_gallery_page)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not copy file: {e}")

    def _clear_deleted_gallery_asset_references(self, folder_path, filename):
        folder_name = os.path.basename(folder_path.rstrip("/\\"))
        image_key_map = {
            "modern_menu_background_image": "main_bg",
            "modern_menu_background_image_light": "main_bg",
            "modern_menu_background_image_dark": "main_bg",
            "modern_menu_slideshow_images": "main_bg",
            "onigiri_overview_bg_image": "main_bg",
            "onigiri_overview_bg_image_light": "main_bg",
            "onigiri_overview_bg_image_dark": "main_bg",
            "onigiri_overview_slideshow_images": "main_bg",
            "modern_menu_profile_bg_image": "profile_bg",
            "modern_menu_profile_picture": "profile",
            "modern_menu_profile_picture_light": "profile",
            "modern_menu_profile_picture_dark": "profile",
            "modern_menu_sidebar_bg_image": "sidebar_bg",
            "modern_menu_sidebar_bg_image_light": "sidebar_bg",
            "modern_menu_sidebar_bg_image_dark": "sidebar_bg",
            "modern_menu_sidebar_slideshow_images": "sidebar_bg",
            "onigiri_reviewer_bg_image": "reviewer_bg",
            "onigiri_reviewer_bg_image_light": "reviewer_bg",
            "onigiri_reviewer_bg_image_dark": "reviewer_bg",
            "onigiri_reviewer_slideshow_images": "reviewer_bg",
            "onigiri_reviewer_bottom_bar_bg_image": "reviewer_bar_bg",
            "onigiri_toolbar_bg_image": "toolbar_bg",
        }
        for key, mapped_folder in image_key_map.items():
            if mapped_folder != folder_name:
                continue
            for store in (self.current_config, mw.col.conf):
                value = store.get(key)
                if isinstance(value, list):
                    cleaned = [item for item in value if os.path.basename(str(item)) != filename]
                    if cleaned != value:
                        store[key] = cleaned
                elif value and os.path.basename(str(value)) == filename:
                    store[key] = ""

    def _delete_gallery_asset(self, folder_path, filename):
        if not filename:
            return
        if not self._confirm_gallery_asset_delete(filename):
            return
        scroll_value = None
        current_page = self.content_stack.currentWidget() if hasattr(self, "content_stack") else None
        current_scroll = current_page.findChild(QScrollArea, "settingsPageScroll") if current_page else None
        if current_scroll and getattr(self, "_current_page_name", None) == "Gallery":
            scroll_value = current_scroll.verticalScrollBar().value()
        filepath = os.path.join(self.addon_path, folder_path, filename)
        try:
            os.remove(filepath)
            self._clear_deleted_gallery_asset_references(folder_path, filename)
            QTimer.singleShot(0, lambda value=scroll_value: self._reload_gallery_page(value))
        except OSError as e:
            QMessageBox.warning(self, "Error", f"Could not delete file: {e}")

    def _confirm_gallery_asset_delete(self, filename):
        return self._confirm_delete_dialog(
            "Delete Image",
            "Delete image?",
            f"'{filename}' will be permanently removed from your Onigiri Gallery.",
        )

    def _show_gallery_asset_preview(self, image_path, filename):
        if not os.path.exists(image_path):
            return
        dialog = GalleryAssetPreviewDialog(image_path, filename, self, self._settings_palette())
        dialog.exec()

    def _create_gallery_color_tile(self, label_text, color_value, nav_page=None, mode=None, key=None, config_key=None):
        palette = dict(self._settings_palette())
        if mode == "dark":
            palette.update({"--canvas-inset": "#242424", "--border": "#454545", "--hover-bg": "#303030", "--fg": "#f4f4f5", "--fg-subtle": "#a1a1aa", "--highlight-bg": "#3a3a3a"})
        elif mode == "light":
            palette.update({"--canvas-inset": "#ffffff", "--border": "#e5e7eb", "--hover-bg": "#f9fafb", "--fg": "#111827", "--fg-subtle": "#6b7280", "--highlight-bg": "#f3f4f6"})
        tile = QFrame()
        tile.setObjectName("galleryColorTile")
        tile.setFixedSize(150, 126)
        tile.setCursor(Qt.CursorShape.PointingHandCursor)
        tile.setToolTip(f"{label_text}\n{str(color_value).upper()}")
        tile.setStyleSheet(f"""
            QFrame#galleryColorTile {{
                background-color: {palette.get("--canvas-inset", "#ffffff")};
                border: 1px solid {palette.get("--border", "#dcdde1")};
                border-radius: 10px;
            }}
            QFrame#galleryColorTile:hover {{
                background-color: {palette.get("--hover-bg", "#e9e9e9")};
                border-color: {palette.get("--accent-color", self.accent_color)};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(8, 8, 8, 8)
        tile_layout.setSpacing(4)

        swatch = QLabel()
        swatch.setFixedSize(134, 48)
        swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        tile_layout.addWidget(swatch)

        name = QLabel(label_text)
        name.setWordWrap(True)
        name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        name.setFixedHeight(24)
        name.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {palette.get('--fg', '#202124')};")
        tile_layout.addWidget(name)

        value_input = QLineEdit(str(color_value).upper())
        value_input.setObjectName("galleryColorValueInput")
        value_input.setFixedHeight(22)
        value_input.setFrame(False)
        value_input.setAlignment(Qt.AlignmentFlag.AlignLeft)
        value_input.setStyleSheet(f"""
            QLineEdit#galleryColorValueInput {{
                background: transparent;
                border: none;
                color: {palette.get('--fg-subtle', '#6f7177')};
                font-family: monospace;
                font-size: 9px;
                padding: 0px;
            }}
            QLineEdit#galleryColorValueInput:focus {{
                background-color: {palette.get("--highlight-bg", "#f3f4f6")};
                border: 1px solid {palette.get("--accent-color", self.accent_color)};
                border-radius: 5px;
                padding: 0px 3px;
            }}
        """)
        tile_layout.addWidget(value_input)

        def update_swatch(value):
            color = QColor(value)
            border_color = "rgba(0, 0, 0, 0.14)" if color.isValid() and color.lightness() > 210 else "rgba(255, 255, 255, 0.18)"
            swatch.setStyleSheet(f"""
                QLabel {{
                    background-color: {value};
                    border: 1px solid {border_color};
                    border-radius: 8px;
                }}
            """)

        def commit_color(value):
            update_swatch(value)
            if mode in ["light", "dark"] and key:
                self._on_palette_color_changed(mode, key, value)
            elif isinstance(config_key, (tuple, list)) and len(config_key) == 2 and QColor(value).isValid():
                section, nested_key = config_key
                nested_config = self.current_config.setdefault(section, {})
                if isinstance(nested_config, dict):
                    nested_config[nested_key] = value
                if section == "markerColors":
                    marker_input = getattr(self, f"marker_{nested_key}_color_input", None)
                    if marker_input is not None and marker_input is not value_input and marker_input.text() != value:
                        marker_input.setText(value)
            elif config_key and QColor(value).isValid():
                self.current_config[config_key] = value

        def choose_color(anchor):
            self.open_color_picker(value_input, anchor)

        update_swatch(color_value)
        value_input.textChanged.connect(commit_color)
        value_input.returnPressed.connect(value_input.clearFocus)
        swatch.mousePressEvent = lambda event, anchor=swatch: choose_color(anchor)
        tile.mousePressEvent = lambda event, anchor=swatch: choose_color(anchor)

        if mode in ["light", "dark"] and key:
            # setdefault: a feature page may already own the canonical widget for this key.
            self.color_widgets[mode].setdefault(key, value_input)
            if key == "--accent-color":
                setattr(self, f"{mode}_accent_color_input", value_input)
            self._register_color_sync(f"palette:{mode}:{key}", value_input)
        elif isinstance(config_key, str):
            self._register_color_sync(f"flat:{config_key}", value_input)

        return tile

    def _create_gallery_color_group(self, title, items):
        group = QWidget()
        group.setObjectName("galleryFlatGroup")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(0, 8, 0, 0)
        group_layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("galleryTitleLabel")
        group_layout.addWidget(title_label)

        tiles = QWidget()
        tiles_layout = FlowLayout(tiles, margin=0, spacing=8)
        tiles_layout.setContentsMargins(0, 0, 0, 0)
        for tile in items:
            tiles_layout.addWidget(tile)
        group_layout.addWidget(tiles)
        return group

    def create_gallery_page(self):
        """Create a Gallery page showing applied colors and user assets."""
        page, layout = self._create_scrollable_page()
        layout.setContentsMargins(0, 0, 8, 24)

        current_mode = "dark" if theme_manager.night_mode else "light"
        mode_stack = QStackedWidget()
        mode_stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")
        mode_pages = {}

        def set_gallery_mode(mode):
            mode_stack.setCurrentWidget(mode_pages[mode])

        mode_toggle, self.gallery_preview_mode_toggle = self._create_light_dark_mode_toggle(current_mode, set_gallery_mode)
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)
        title = QLabel(tr("gallery"))
        title.setStyleSheet(f"font-size: 24px; font-weight: 500; color: {self._settings_palette().get('--fg', '#202124')}; background: transparent;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(mode_toggle)
        layout.addWidget(header)

        colors_section = SectionGroup(
            "",
            self,
            border=False,
            description=tr("colors_gallery_desc")
        )

        color_categories = [
            (tr("category_palette"), "Gallery", ["--accent-color"]),
            (tr("fonts"), "Fonts", ["--fg", "--fg-subtle"]),
            (tr("category_main_menu"), "Main menu", ["--bg", "--canvas-inset", "--heatmap-color", "--heatmap-color-zero", "--star-color", "--empty-star-color"]),
            (tr("category_sidebar"), "Sidebar", ["--highlight-bg", "--deck-hover-bg", "--deck-dragging-bg", "--deck-edit-mode-bg"]),
        ]

        answer_button_colors = {
            "light": [
                (tr("again_bg"), "onigiri_reviewer_btn_again_bg_light"),
                (tr("again_text"), "onigiri_reviewer_btn_again_text_light"),
                (tr("hard_bg"), "onigiri_reviewer_btn_hard_bg_light"),
                (tr("hard_text"), "onigiri_reviewer_btn_hard_text_light"),
                (tr("good_bg"), "onigiri_reviewer_btn_good_bg_light"),
                (tr("good_text"), "onigiri_reviewer_btn_good_text_light"),
                (tr("easy_bg"), "onigiri_reviewer_btn_easy_bg_light"),
                (tr("easy_text"), "onigiri_reviewer_btn_easy_text_light"),
            ],
            "dark": [
                (tr("again_bg"), "onigiri_reviewer_btn_again_bg_dark"),
                (tr("again_text"), "onigiri_reviewer_btn_again_text_dark"),
                (tr("hard_bg"), "onigiri_reviewer_btn_hard_bg_dark"),
                (tr("hard_text"), "onigiri_reviewer_btn_hard_text_dark"),
                (tr("good_bg"), "onigiri_reviewer_btn_good_bg_dark"),
                (tr("good_text"), "onigiri_reviewer_btn_good_text_dark"),
                (tr("easy_bg"), "onigiri_reviewer_btn_easy_bg_dark"),
                (tr("easy_text"), "onigiri_reviewer_btn_easy_text_dark"),
            ],
        }

        for mode in ["light", "dark"]:
            mode_widget = QWidget()
            mode_widget.setObjectName(f"galleryMode_{mode}")
            mode_layout = QVBoxLayout(mode_widget)
            mode_layout.setContentsMargins(0, 0, 0, 0)
            mode_layout.setSpacing(10)

            mode_colors = self.current_config.get("colors", {}).get(mode, {})
            mode_defaults = DEFAULTS["colors"][mode]
            for category_name, nav_page, color_keys in color_categories:
                tiles = []
                for color_key in color_keys:
                    color_value = mode_colors.get(color_key, mode_defaults.get(color_key, "#888888"))
                    label_info = COLOR_LABELS.get(color_key, {"label": color_key.replace("--", "").replace("-", " ").title()})
                    tiles.append(self._create_gallery_color_tile(
                        tr(label_info["label"]),
                        color_value,
                        nav_page,
                        mode=mode,
                        key=color_key
                    ))
                if nav_page == "Main menu":
                    tiles.append(self._create_gallery_color_tile(
                        tr("heatmap_streak_icon_color", "Streak Icon Color"),
                        self.current_config.get("heatmapStreakIconColor", DEFAULTS.get("heatmapStreakIconColor", "#ff6b35")),
                        nav_page,
                        mode=mode,
                        config_key="heatmapStreakIconColor",
                    ))
                    tiles.append(self._create_gallery_color_tile(
                        tr("heatmap_streak_icon_zero_color", "Streak Icon Color (0 days)"),
                        self.current_config.get("heatmapStreakIconZeroColor", DEFAULTS.get("heatmapStreakIconZeroColor", "#8f8f8f")),
                        nav_page,
                        mode=mode,
                        config_key="heatmapStreakIconZeroColor",
                    ))
                mode_layout.addWidget(self._create_gallery_color_group(category_name, tiles))

            marker_colors = self.current_config.get("markerColors", DEFAULTS.get("markerColors", {}))
            marker_tiles = []
            for marker_key, fallback in [
                ("red", "#FF4B4B"),
                ("blue", "#4488FF"),
                ("green", "#44BB66"),
                ("yellow", "#FFB800"),
            ]:
                marker_input = getattr(self, f"marker_{marker_key}_color_input", None)
                marker_value = marker_input.text() if marker_input is not None else marker_colors.get(marker_key, fallback)
                marker_tiles.append(self._create_gallery_color_tile(
                    tr(f"marker_{marker_key}", marker_key.title()),
                    marker_value,
                    "Sidebar",
                    mode=mode,
                    config_key=("markerColors", marker_key)
                ))
            mode_layout.addWidget(self._create_gallery_color_group(tr("markers", "Markers"), marker_tiles))

            reviewer_tiles = []
            for label_name, config_key in answer_button_colors[mode]:
                reviewer_tiles.append(self._create_gallery_color_tile(
                    label_name,
                    self.current_config.get(config_key, DEFAULTS.get(config_key, "#888888")),
                    "Reviewer",
                    mode=mode,
                    config_key=config_key
                ))
            mode_layout.addWidget(self._create_gallery_color_group(tr("category_reviewer"), reviewer_tiles))
            mode_layout.addStretch()
            mode_pages[mode] = mode_widget
            mode_stack.addWidget(mode_widget)

        colors_section.add_widget(mode_stack)
        set_gallery_mode(current_mode)
        layout.addWidget(colors_section)

        images_section = SectionGroup(
            tr("images_gallery"),
            self,
            border=False,
            description=tr("images_gallery_desc")
        )

        image_directories = [
            (tr("profile_pictures"), "user_files/profile", "Profile"),
            (tr("profile_backgrounds"), "user_files/profile_bg", "Profile"),
            (tr("main_menu_overviewer_images"), "user_files/main_bg", "Main menu"),
            (tr("sidebar_backgrounds"), "user_files/sidebar_bg", "Sidebar"),
            (tr("reviewer_backgrounds"), "user_files/reviewer_bg", "Reviewer"),
            (tr("reviewer_bar_backgrounds"), "user_files/reviewer_bar_bg", "Reviewer"),
        ]
        extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp")
        palette = self._settings_palette()
        image_group_bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        image_group_border = palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")
        image_group_hover = palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        image_group_style = f"""
            QFrame#galleryImageGroup {{
                background-color: {image_group_bg};
                border: 1px solid {image_group_border};
                border-radius: 18px;
            }}
            QFrame#galleryImageGroup:hover {{
                border-color: {image_group_border};
                background-color: {image_group_hover};
            }}
        """

        def attach_gallery_asset_press_handlers(tile, image_path, filename, nav_page):
            long_press_timer = QTimer(tile)
            long_press_timer.setSingleShot(True)
            long_press_state = {"shown": False}

            def show_preview():
                long_press_state["shown"] = True
                self._show_gallery_asset_preview(image_path, filename)

            def mouse_press(event):
                long_press_state["shown"] = False
                long_press_timer.start(620)
                event.accept()

            def mouse_release(event):
                if long_press_timer.isActive():
                    long_press_timer.stop()
                if not long_press_state["shown"]:
                    self.navigate_to_page(nav_page)
                event.accept()

            long_press_timer.timeout.connect(show_preview)
            tile.mousePressEvent = mouse_press
            tile.mouseReleaseEvent = mouse_release

        for title, folder_path, img_nav_page in image_directories:
            full_path = os.path.join(self.addon_path, folder_path)
            try:
                image_files = sorted([f for f in os.listdir(full_path) if f.lower().endswith(extensions)]) if os.path.exists(full_path) else []
            except OSError:
                image_files = []

            subsection_group, subsection_layout = self._create_inner_group(title)
            subsection_group.setObjectName("galleryImageGroup")
            subsection_group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            subsection_group.setStyleSheet(image_group_style)
            action_style = self._gallery_action_button_style()
            import_button = QPushButton("Import")
            import_button.setObjectName("galleryAssetActionButton")
            import_button.setCursor(Qt.CursorShape.PointingHandCursor)
            import_button.setStyleSheet(action_style)
            import_button.clicked.connect(lambda _=False, folder=folder_path, exts=extensions: self._import_gallery_asset(folder, exts))
            subsection_group.header_layout.addWidget(import_button)

            if image_files:
                content_widget = QWidget()
                grid_layout = FlowLayout(content_widget, margin=0, spacing=8)
                grid_layout.setContentsMargins(0, 0, 0, 0)

                for filename in image_files[:24]:
                    img_path = os.path.join(full_path, filename)
                    thumb_container = QFrame()
                    thumb_container.setObjectName("galleryAssetTile")
                    thumb_container.setFixedSize(120, 108)
                    thumb_container.setCursor(Qt.CursorShape.PointingHandCursor)
                    thumb_container.setToolTip(filename)
                    thumb_container.setStyleSheet(f"""
                        QFrame#galleryAssetTile {{
                            background-color: {palette.get("--canvas-inset", "#ffffff")};
                            border: 1px solid {palette.get("--border", "#dcdde1")};
                            border-radius: 10px;
                        }}
                        QFrame#galleryAssetTile:hover {{
                            background-color: {palette.get("--hover-bg", "#e9e9e9")};
                            border-color: {palette.get("--accent-color", self.accent_color)};
                        }}
                        QLabel {{
                            background: transparent;
                            border: none;
                        }}
                    """)
                    thumb_layout = QVBoxLayout(thumb_container)
                    thumb_layout.setContentsMargins(6, 6, 6, 6)
                    thumb_layout.setSpacing(5)
                    thumb_label = QLabel()
                    thumb_label.setObjectName("galleryAssetPreview")
                    thumb_label.setFixedSize(108, 70)
                    thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

                    pixmap = QPixmap(img_path)
                    if not pixmap.isNull():
                        thumb_label.setPixmap(self._rounded_gallery_pixmap(img_path, QSize(108, 70), 10))
                    else:
                        thumb_label.setText("?")
                        thumb_label.setStyleSheet("background: rgba(128,128,128,0.16); border-radius: 10px;")

                    thumb_layout.addWidget(thumb_label)
                    footer = QWidget()
                    footer.setStyleSheet("background: transparent;")
                    footer_layout = QHBoxLayout(footer)
                    footer_layout.setContentsMargins(0, 0, 0, 0)
                    footer_layout.setSpacing(4)

                    delete_button = QPushButton("Delete")
                    delete_button.setObjectName("galleryAssetDeleteButton")
                    delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
                    delete_button.setStyleSheet(action_style)
                    delete_button.clicked.connect(lambda _=False, folder=folder_path, name=filename: self._delete_gallery_asset(folder, name))
                    footer_layout.addStretch()
                    footer_layout.addWidget(delete_button, 0)
                    thumb_layout.addWidget(footer)
                    attach_gallery_asset_press_handlers(thumb_container, img_path, filename, img_nav_page)
                    grid_layout.addWidget(thumb_container)

                if len(image_files) > 24:
                    more_label = QLabel(tr("more_images").format(count=len(image_files) - 24))
                    more_label.setStyleSheet(f"color: {palette.get('--fg-subtle', '#6f7177')}; font-size: 11px;")
                    grid_layout.addWidget(more_label)
                subsection_layout.addWidget(content_widget)
            else:
                no_files = QLabel(tr("no_images_uploaded"))
                no_files.setStyleSheet(f"color: {palette.get('--fg-subtle', '#6f7177')}; font-style: italic; padding: 6px 0px;")
                subsection_layout.addWidget(no_files)

            images_section.add_widget(subsection_group)

        layout.addWidget(images_section)
        layout.addStretch()

        sections_map = {
            tr("colors_section"): colors_section,
            tr("images"): images_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections_map)

        return page

    def _create_image_gallery_group(self, key, folder, config_key, extensions=(".png", ".jpg", ".jpeg", ".gif", ".webp"), show_path=True, is_sub_group=False, title="", image_files_cache=None, actions_in_parent_header=False):
        group_container = QWidget()
        group_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(group_container)
        layout.setContentsMargins(0, 0 if is_sub_group else 10, 0, 0)
        layout.setSpacing(10)
        gallery_identity = " ".join(str(value or "") for value in (key, folder, config_key)).lower()
        is_background_gallery = "bg" in gallery_identity or "background" in gallery_identity
        
        palette = self._settings_palette()
        panel_bg = palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        text_col = palette.get("--fg", "#f9fafb" if theme_manager.night_mode else "#111827")
        muted_col = palette.get("--fg-subtle", "#d1d5db" if theme_manager.night_mode else "#4b5563")
        border_col = palette.get("--border", "#454545" if theme_manager.night_mode else "#e5e7eb")

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        if title:
            title_label = QLabel(title)
            title_label.setObjectName("galleryTitleLabel")
            header_layout.addWidget(title_label)

        action_button_style = f"""
            QPushButton#galleryActionButton {{
                background-color: transparent;
                border: 1px solid {border_col};
                border-radius: 14px;
                color: {muted_col};
                font-size: 12px;
                font-weight: 700;
                padding: 3px 12px;
                min-height: 26px;
            }}
            QPushButton#galleryActionButton:hover {{
                background-color: {panel_bg};
                color: {text_col};
            }}
            QPushButton#galleryActionButton:disabled {{
                color: {border_col};
                border-color: {border_col};
            }}
        """

        choose_button = QPushButton("Import" if is_background_gallery else (tr("import_action") if show_path else tr("add_icon")))
        choose_button.setObjectName("galleryActionButton")
        choose_button.setMinimumHeight(26)
        choose_button.setMinimumWidth(0)
        choose_button.setCursor(Qt.CursorShape.PointingHandCursor)
        choose_button.setStyleSheet(action_button_style)
        choose_button.clicked.connect(lambda: self._choose_file_for_gallery(key))
        delete_button = QPushButton("Clear image" if is_background_gallery else tr("delete_selected"))
        delete_button.setObjectName("galleryActionButton")
        delete_button.setMinimumHeight(26)
        delete_button.setMinimumWidth(0)
        delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_button.setStyleSheet(action_button_style)
        delete_button.clicked.connect(lambda: self._delete_from_gallery(key))
        gallery_button = None
        if is_background_gallery:
            gallery_button = QPushButton("Select from your Gallery")
            gallery_button.setObjectName("galleryActionButton")
            gallery_button.setMinimumHeight(26)
            gallery_button.setCursor(Qt.CursorShape.PointingHandCursor)
            gallery_button.setStyleSheet(action_button_style)
            gallery_button.clicked.connect(lambda: self._open_gallery_selection_dialog(key))

        if is_background_gallery:
            for button in (choose_button, delete_button):
                button.setMaximumWidth(128)
                button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            if gallery_button:
                gallery_button.setMaximumWidth(176)
                gallery_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        actions_widget = QWidget()
        actions_widget.setObjectName("galleryActions")
        actions_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        actions_layout = FlowLayout(actions_widget, margin=0, spacing=8) if is_background_gallery else QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        if is_background_gallery:
            actions_layout.addWidget(choose_button)
            actions_layout.addWidget(delete_button)
            actions_layout.addWidget(gallery_button)
        else:
            actions_layout.addWidget(choose_button, 1)
            actions_layout.addWidget(delete_button, 1)
        group_container.gallery_actions_widget = actions_widget

        path_input = QLineEdit(group_container)
        path_input.setObjectName("gallerySelectedInput")
        path_input.setPlaceholderText(tr("no_item_selected"))
        path_input.setReadOnly(True)
        path_input.setMinimumWidth(0)
        path_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        path_input.setVisible(not is_background_gallery)

        if title:
            layout.addLayout(header_layout)
            if is_background_gallery:
                action_row = QHBoxLayout()
                action_row.setContentsMargins(0, 0, 0, 0)
                action_row.addWidget(actions_widget, 1)
                layout.addLayout(action_row)
            else:
                header_layout.addStretch()
                header_layout.addWidget(actions_widget)
        elif not actions_in_parent_header:
            action_row = QHBoxLayout()
            action_row.setContentsMargins(0, 0, 0, 0)
            action_row.addWidget(actions_widget, 1 if is_background_gallery else 0)
            if not is_background_gallery:
                action_row.insertStretch(0)
            layout.addLayout(action_row)

        scroll_area, grid_layout = self._create_gallery_ui(compact=is_background_gallery)

        # Determine which config source to use based on the config key pattern
        if config_key and (
            config_key.startswith("onigiri_reviewer_bg_image")
            or config_key.startswith("onigiri_overview_bg_image")
        ):
            # Reviewer and overview background images are stored in the addon config
            selected_image = self.current_config.get(config_key, "")
        elif config_key:
            # Other images are stored in Anki's collection config
            selected_image = mw.col.conf.get(config_key, "")
        else:
            # Fallback for cases where config_key is empty
            selected_image = ""

        preview_widget = None
        if is_background_gallery:
            preview_widget = QLabel()
            preview_widget.setObjectName("backgroundPreview")
            preview_widget.setMinimumWidth(0)
            preview_widget.setFixedHeight(130)
            preview_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            preview_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            preview_widget.setProperty("gallery_import_key", key)
            preview_widget.setProperty("last_preview_size", QSize())
            preview_widget.installEventFilter(self)
            preview_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(preview_widget)

        if not is_background_gallery:
            layout.addWidget(scroll_area)

        if show_path and not is_background_gallery:
            path_input.setText(selected_image)
            layout.addWidget(path_input)

        gallery_data = {
            'selected': selected_image,
            'folder': folder, 'extensions': extensions,
            'grid_layout': grid_layout, 'labels': [], 'thread': None, 'worker': None,
            'path_input': path_input if show_path else None, 'delete_button': delete_button,
            'populated': False, 'clear_only': is_background_gallery,
            'preview_widget': preview_widget,
            'scroll_area': scroll_area,
            'compact': is_background_gallery,
        }
        self.galleries[key].update(gallery_data)
        self._update_gallery_background_preview(key)

        # Defer visible gallery population to avoid blocking UI.
        if not is_background_gallery:
            self._defer_gallery_population(key)
        
        self._update_delete_button_state(key)
        return group_container

    def _create_gallery_ui(self, compact=False):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(92 if compact else 150)
        scroll_area.setMaximumHeight(132 if compact else 220)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        content_widget = QWidget()
        content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        grid_layout = FlowLayout(content_widget, margin=0, spacing=12)
        scroll_area.setWidget(content_widget)
        return scroll_area, grid_layout

    def _defer_gallery_population(self, key):
        """Populate gallery after a short delay to avoid blocking UI"""
        old_timer = self._gallery_population_timers.pop(key, None)
        if old_timer:
            old_timer.stop()
            old_timer.deleteLater()

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda k=key, t=timer: self._run_gallery_population_timer(k, t))
        self._gallery_population_timers[key] = timer
        timer.start(80)

    def _run_gallery_population_timer(self, key, timer):
        self._gallery_population_timers.pop(key, None)
        timer.deleteLater()
        self._populate_gallery_if_exists(key)

    def _populate_gallery_if_exists(self, key):
        """Populate gallery if it exists in the galleries dict"""
        if key in self.galleries:
            self._populate_gallery_placeholders(key)

    def _populate_gallery_placeholders(self, key, image_files_cache=None):
        gallery = self.galleries[key]
        if gallery.get('populated'):
            return
        gallery['populated'] = True
        full_folder_path = os.path.join(self.addon_path, gallery['folder'])
        os.makedirs(full_folder_path, exist_ok=True)
        
        if image_files_cache is not None:
            image_files = image_files_cache
        else:
            try:
                image_files = sorted([f for f in os.listdir(full_folder_path) if f.lower().endswith(gallery['extensions'])])
            except OSError: image_files = []

        if not image_files:
            no_files_label = QLabel(tr("no_files_found"))
            if gallery.get('compact'):
                no_files_label.setFixedSize(126, 64)
            else:
                no_files_label.setFixedSize(100, 100)
            no_files_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            bg = "rgba(255, 255, 255, 0.05)" if theme_manager.night_mode else "rgba(0, 0, 0, 0.05)"
            color = "#aaaaaa" if theme_manager.night_mode else "#666666"
            
            no_files_label.setStyleSheet(f"""
                background-color: {bg};
                border-radius: 10px;
                color: {color};
                font-size: 12px;
            """)
            if isinstance(gallery['grid_layout'], FlowLayout):
                gallery['grid_layout'].addWidget(no_files_label)
            else:
                gallery['grid_layout'].addWidget(no_files_label, 0, 0)
            return

        gallery['overlays'] = []
        
        # Determine sizes based on key
        if key == 'profile_pic':
            item_width, item_height = 108, 112
            img_width, img_height = 96, 96
            shape = 'circular'
        elif gallery.get('compact'):
            item_width, item_height = 172, 102
            img_width, img_height = 160, 90
            shape = 'rounded'
        else: # profile_bg and others
            item_width, item_height = 154, 96
            img_width, img_height = 142, 80
            shape = 'rounded'

        for i, filename in enumerate(image_files):
            # Container
            container = QWidget()
            container.setFixedSize(item_width, item_height)
            container.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Image Label
            img_label = QLabel(container)
            img_label.setFixedSize(img_width, img_height)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            # Center the image in the container
            img_label.move((item_width - img_width) // 2, (item_height - img_height) // 2)
            
            # Placeholder content
            img_label.setText("⏳")
            img_label.setStyleSheet("background-color: rgba(128,128,128,0.1); border-radius: 10px;")

            # Selection Overlay
            overlay = SelectionOverlay(container, accent_color=self.accent_color)
            is_selected = (filename == gallery['selected'])
            overlay.setChecked(is_selected)
            
            # Position overlay (Top Right)
            overlay.move(item_width - 28, 4)
            overlay.setProperty("image_filename", filename)

            # Install event filter on container
            container.setProperty("gallery_key", key)
            container.setProperty("image_filename", filename)
            container.installEventFilter(self)

            if isinstance(gallery['grid_layout'], FlowLayout):
                gallery['grid_layout'].addWidget(container)
            else:
                gallery['grid_layout'].addWidget(container, i // 4, i % 4)
            gallery['labels'].append(img_label)
            gallery['overlays'].append(overlay)
        
        thread = QThread(); worker = ThumbnailWorker(key, full_folder_path, image_files, shape=shape, thumb_size=(img_width, img_height))
        worker.moveToThread(thread)
        worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        
        gallery['thread'] = thread
        gallery['worker'] = worker

    def _choose_file_for_gallery(self, key):
        gallery = self.galleries[key]
        ext_filter = f"Files (*{' *'.join(gallery['extensions'])})"; filepath, _ = QFileDialog.getOpenFileName(self, tr("import_image"), "", ext_filter)
        if not filepath: return
        
        filename = os.path.basename(filepath)
        dest_path = os.path.join(self.addon_path, gallery['folder'], filename)
        
        try:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            if os.path.abspath(filepath) != os.path.abspath(dest_path):
                shutil.copy(filepath, dest_path)
            gallery['selected'] = filename
            if gallery.get('path_input'):
                gallery['path_input'].setText(filename)
            if gallery.get('clear_only'):
                self._update_delete_button_state(key)
                self._update_gallery_background_preview(key)
                return
            self._refresh_gallery(key)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not copy file: {e}")

    def _open_gallery_selection_dialog(self, key):
        gallery = self.galleries.get(key)
        if not gallery:
            return
        folder = gallery.get('folder', '')
        full_folder_path = os.path.join(self.addon_path, folder)
        os.makedirs(full_folder_path, exist_ok=True)
        try:
            image_files = sorted([f for f in os.listdir(full_folder_path) if f.lower().endswith(gallery.get('extensions', (".png", ".jpg", ".jpeg", ".gif", ".webp")))])
        except OSError:
            image_files = []

        dialog = BackgroundGalleryDialog(self)
        dialog.setWindowTitle("Select from your Gallery")
        dialog.resize(760, 520)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self._style_background_gallery_dialog(dialog)
        layout.addWidget(self._create_background_gallery_hint_bar("single"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("backgroundGalleryContent")
        flow = FlowLayout(content, margin=4, spacing=10)
        tiles = []

        def refresh_badges():
            for tile in tiles:
                tile.setBadges(self._background_gallery_badges("single", tile.filename, selected=gallery.get('selected') == tile.filename))

        def select_file(filename):
            gallery['selected'] = filename
            if gallery.get('path_input'):
                gallery['path_input'].setText(filename)
            self._update_delete_button_state(key)
            self._update_gallery_background_preview(key)
            refresh_badges()

        for filename in image_files:
            tile = BackgroundGalleryTile(filename, os.path.join(full_folder_path, filename), self.accent_color)
            tile.setBadges(self._background_gallery_badges("single", filename, selected=gallery.get('selected') == filename))
            tile.clicked.connect(select_file)
            flow.addWidget(tile)
            tiles.append(tile)

        if not image_files:
            empty = QLabel("No images imported yet.")
            empty.setObjectName("backgroundGalleryEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            flow.addWidget(empty)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        done = QPushButton("Done")
        done.clicked.connect(dialog.accept)
        layout.addWidget(done, 0, Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def _delete_from_gallery(self, key):
        gallery = self.galleries[key]
        filename = gallery['selected']
        if not filename: return

        if gallery.get('clear_only'):
            gallery['selected'] = ""
            if gallery.get('path_input'):
                gallery['path_input'].clear()
                gallery['path_input'].setPlaceholderText(tr("no_item_selected"))
            self._update_delete_button_state(key)
            self._update_gallery_background_preview(key)
            return
        
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to permanently delete '{filename}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            filepath = os.path.join(self.addon_path, gallery['folder'], filename)
            try:
                os.remove(filepath)
                gallery['selected'] = ""
                if gallery.get('path_input'): gallery['path_input'].clear()
                self._refresh_gallery(key)
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Could not delete file: {e}")

    def _refresh_gallery(self, key):
        gallery = self.galleries[key]
        scroll_area = gallery.get('scroll_area')
        gallery_scroll_value = scroll_area.verticalScrollBar().value() if scroll_area else None
        page_scroll = None
        current_page = self.content_stack.currentWidget() if hasattr(self, "content_stack") else None
        current_scroll = current_page.findChild(QScrollArea, "settingsPageScroll") if current_page else None
        if current_scroll:
            page_scroll = current_scroll.verticalScrollBar().value()

        old_timer = self._gallery_population_timers.pop(key, None)
        if old_timer:
            old_timer.stop()
            old_timer.deleteLater()

        try:
            if gallery.get('thread') and gallery['thread'].isRunning():
                gallery['worker'].cancel()
                gallery['thread'].quit()
                gallery['thread'].wait()
        except RuntimeError:
            pass
        
        # Clear all items from the grid layout
        layout = gallery['grid_layout']
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        gallery['labels'] = []
        gallery['populated'] = False
        if 'overlays' in gallery:
            gallery['overlays'] = []
            
        self._populate_gallery_placeholders(key)
        self._update_delete_button_state(key)
        self._update_gallery_background_preview(key)

        def restore_scroll_positions():
            if scroll_area:
                scrollbar = scroll_area.verticalScrollBar()
                scrollbar.setValue(min(gallery_scroll_value, scrollbar.maximum()))
            if current_scroll:
                scrollbar = current_scroll.verticalScrollBar()
                scrollbar.setValue(min(page_scroll, scrollbar.maximum()))

        if gallery_scroll_value is not None or page_scroll is not None:
            restore_scroll_positions()
            QTimer.singleShot(0, restore_scroll_positions)

    def _update_gallery_background_preview(self, key):
        gallery = self.galleries.get(key, {})
        preview = gallery.get('preview_widget')
        if not preview:
            return

        palette = self._settings_palette()
        border = palette.get("--border", "#e5e7eb")
        surface = palette.get("--highlight-bg", "#f3f4f6")
        selected = gallery.get('selected') or ""
        image_path = os.path.join(self.addon_path, gallery.get('folder', ''), selected) if selected else ""
        css = [
            "QLabel#backgroundPreview {",
            f"background-color: {surface};",
            f"border: 1px solid {border};",
            "border-radius: 14px;",
        ]
        preview.setPixmap(QPixmap())
        if image_path and os.path.exists(image_path):
            size = preview.size()
            width = max(1, size.width())
            height = max(1, size.height())
            source = QImage(image_path)
            if not source.isNull():
                preview.setPixmap(QPixmap.fromImage(create_rounded_thumbnail_image(source, width, height, 14)))
                preview.setScaledContents(False)
        css.append("}")
        preview.setStyleSheet(" ".join(css))
        preview.setText("")

