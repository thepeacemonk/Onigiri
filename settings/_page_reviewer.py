# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *



class PageReviewerMixin:
    def _bottom_bar_bg_folder_path(self):
        path = os.path.join(self.addon_path, "user_files", "reviewer_bar_bg")
        os.makedirs(path, exist_ok=True)
        return path

    def _bottom_bar_bg_image_files(self):
        try:
            return sorted([
                f for f in os.listdir(self._bottom_bar_bg_folder_path())
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
            ])
        except OSError:
            return []

    def _bottom_bar_bg_image_path(self, filename):
        return os.path.join(self._bottom_bar_bg_folder_path(), filename) if filename else ""

    def _bottom_bar_color_value(self, attr_base, fallback="#ffffff"):
        widget = getattr(self, f"{attr_base}_color_input", None)
        color = widget.text() if widget else fallback
        return color if QColor(color).isValid() else fallback

    def _bottom_bar_set_color_value(self, attr_base, color):
        widget = getattr(self, f"{attr_base}_color_input", None)
        if widget:
            widget.setText(color)

    def _create_bottom_bar_color_pill_row(self, label_text, attr_base, initial_color):
        label_button = self._create_main_bg_button(label_text)
        value_button = self._create_main_bg_button("")
        value_button.setObjectName("mainBackgroundColorButton")
        line_edit = QLineEdit(initial_color, self)
        line_edit.hide()
        setattr(self, f"{attr_base}_color_label_button", label_button)
        setattr(self, f"{attr_base}_color_value_button", value_button)
        setattr(self, f"{attr_base}_color_input", line_edit)

        def choose_color(anchor):
            chosen, ok = OnigiriColorDialog.getColor(line_edit.text(), self, anchor=anchor)
            if ok:
                line_edit.setText(chosen)

        label_button.clicked.connect(lambda _=False, b=label_button: choose_color(b))
        value_button.clicked.connect(lambda _=False, b=value_button: choose_color(b))
        line_edit.textChanged.connect(lambda color, b=value_button: self._style_main_background_color_button(b, color if QColor(color).isValid() else initial_color))
        line_edit.textChanged.connect(lambda _=None: self._update_reviewer_bottom_bar_preview())
        if str(attr_base).startswith("pre_count_"):
            line_edit.textChanged.connect(lambda _=None: setattr(self, "_bottom_bar_pre_count_colors_dirty", True))

        self._style_main_background_color_button(value_button, initial_color)
        return self._create_color_selector_card(label_button, value_button)

    def _bottom_bar_rows_for_mode(self, rows, mode):
        suffix = "_dark" if mode == "dark" else "_light"
        label_suffix = " (Dark)" if mode == "dark" else " (Light)"
        filtered = []
        for label, attr_base, color in rows:
            if not str(attr_base).endswith(suffix):
                continue
            clean_label = str(label).replace(label_suffix, "").replace("Dark ", "").replace("Light ", "")
            filtered.append((clean_label, attr_base, color))
        return filtered

    def _create_bottom_bar_color_grid(self, rows, columns=2):
        grid = QWidget()
        layout = QGridLayout(grid)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(10)
        columns = max(1, int(columns or 1))
        for column in range(columns):
            layout.setColumnStretch(column, 1)
        for index, (label, attr_base, color) in enumerate(rows):
            layout.addWidget(self._create_bottom_bar_color_pill_row(label, attr_base, color), index // columns, index % columns)
        return grid

    def _create_bottom_bar_effect_page(self, blur_widget, blur_label, opacity_widget, opacity_label):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        blur_value = QWidget()
        blur_layout = QHBoxLayout(blur_value)
        blur_layout.setContentsMargins(0, 0, 0, 0)
        blur_layout.setSpacing(10)
        blur_layout.addWidget(blur_widget, 1)
        blur_layout.addWidget(blur_label)

        opacity_value = QWidget()
        opacity_layout = QHBoxLayout(opacity_value)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(10)
        opacity_layout.addWidget(opacity_widget, 1)
        opacity_layout.addWidget(opacity_label)

        layout.addWidget(self._create_main_bg_value_row("Blur Intensity", blur_value))
        layout.addWidget(self._create_main_bg_value_row("Opacity", opacity_value))
        return page

    def _create_bottom_bar_effect_slider(self, value):
        palette = self._settings_palette()
        slider_track = palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")
        slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        slider.setRange(0, 100)
        slider.setValue(int(value))
        return slider

    def _wire_bottom_bar_effect_slider(self, slider, label):
        label.setObjectName("mainBackgroundValueLabel")
        label.setFixedWidth(48)
        label.setText(f"{slider.value()}%")
        slider.valueChanged.connect(lambda value, l=label: l.setText(f"{value}%"))
        slider.valueChanged.connect(lambda _=None: self._update_reviewer_bottom_bar_preview())

    def _create_bottom_bar_number_row(self, label_text, spinbox):
        return self._create_main_bg_value_row(label_text, spinbox)

    def _create_bottom_bar_button_section(self, title, rows):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("mainBackgroundControlLabel")
        title_label.setStyleSheet("font-weight: 700;")
        layout.addWidget(title_label)
        layout.addWidget(self._create_bottom_bar_color_grid(rows))
        return container

    def _create_bottom_bar_button_config_page(self, sections, mode):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        for title, rows in sections:
            mode_rows = self._bottom_bar_rows_for_mode(rows, mode)
            if mode_rows:
                layout.addWidget(self._create_bottom_bar_button_section(title, mode_rows))
        layout.addStretch()
        return page

    def _bottom_bar_custom_color_rows(self):
        return [
            ("Light Color", "reviewer_bar_light", self.current_config.get("onigiri_reviewer_bottom_bar_bg_light_color", "#f2f2f2")),
            ("Dark Color", "reviewer_bar_dark", self.current_config.get("onigiri_reviewer_bottom_bar_bg_dark_color", "#2C2C2C")),
        ]

    def _bottom_bar_button_color_sections(self):
        button_defs = [
            ("Again Button", "again", "#ffb3b3", "#4d0000", "#ffcccb", "#4a0000"),
            ("Hard Button", "hard", "#ffe0b3", "#4d2600", "#ffd699", "#4d1d00"),
            ("Good Button", "good", "#b3ffb3", "#004d00", "#90ee90", "#004000"),
            ("Easy Button", "easy", "#b3d9ff", "#00264d", "#add8e6", "#002952"),
        ]
        sections = []
        for title, key, bg_l, text_l, bg_d, text_d in button_defs:
            sections.append((title, [
                (f"{title.split()[0]} (Light)", f"btn_{key}_bg_light", self.current_config.get(f"onigiri_reviewer_btn_{key}_bg_light", bg_l)),
                (f"{title.split()[0]} (Dark)", f"btn_{key}_bg_dark", self.current_config.get(f"onigiri_reviewer_btn_{key}_bg_dark", bg_d)),
                (f"{title.split()[0]} Text (Light)", f"btn_{key}_text_light", self.current_config.get(f"onigiri_reviewer_btn_{key}_text_light", text_l)),
                (f"{title.split()[0]} Text (Dark)", f"btn_{key}_text_dark", self.current_config.get(f"onigiri_reviewer_btn_{key}_text_dark", text_d)),
            ]))
        sections.append(("Other Bottom Bar Buttons", [
            ("Other (Light)", "other_btn_bg_light", self.current_config.get("onigiri_reviewer_other_btn_bg_light", "#ffffff")),
            ("Other (Dark)", "other_btn_bg_dark", self.current_config.get("onigiri_reviewer_other_btn_bg_dark", "#3a3a3a")),
            ("Other Text (Light)", "other_btn_text_light", self.current_config.get("onigiri_reviewer_other_btn_text_light", "#2c2c2c")),
            ("Other Text (Dark)", "other_btn_text_dark", self.current_config.get("onigiri_reviewer_other_btn_text_dark", "#e0e0e0")),
            ("Hover BG (Light)", "other_btn_hover_bg_light", self.current_config.get("onigiri_reviewer_other_btn_hover_bg_light", "#2c2c2c")),
            ("Hover BG (Dark)", "other_btn_hover_bg_dark", self.current_config.get("onigiri_reviewer_other_btn_hover_bg_dark", "#e0e0e0")),
            ("Hover Text (Light)", "other_btn_hover_text_light", self.current_config.get("onigiri_reviewer_other_btn_hover_text_light", "#f0f0f0")),
            ("Hover Text (Dark)", "other_btn_hover_text_dark", self.current_config.get("onigiri_reviewer_other_btn_hover_text_dark", "#3a3a3a")),
        ]))
        sections.append(("Interval Text", [
            ("Interval (Light)", "stattxt_color_light", self.current_config.get("onigiri_reviewer_stattxt_color_light", "#666666")),
            ("Interval (Dark)", "stattxt_color_dark", self.current_config.get("onigiri_reviewer_stattxt_color_dark", "#aaaaaa")),
        ]))
        return sections

    def _on_reviewer_bottom_bar_match_changed(self, mode, checked):
        if not checked:
            if not any(toggle.isChecked() for toggle in (
                self.reviewer_bar_match_main_toggle,
                self.reviewer_bar_match_overview_toggle,
                self.reviewer_bar_match_reviewer_toggle,
            )):
                self.reviewer_bottom_bar_mode = "color" if self.reviewer_bar_color_only_toggle.isChecked() else "image_color"
                self._sync_reviewer_bottom_bar_controls()
            return

        self.reviewer_bottom_bar_mode = mode
        for other_mode, toggle in (
            ("main", self.reviewer_bar_match_main_toggle),
            ("match_overview_bg", self.reviewer_bar_match_overview_toggle),
            ("match_reviewer_bg", self.reviewer_bar_match_reviewer_toggle),
        ):
            if other_mode != mode:
                with QSignalBlocker(toggle):
                    toggle.setChecked(False)
        with QSignalBlocker(self.reviewer_bar_color_only_toggle):
            self.reviewer_bar_color_only_toggle.setChecked(False)
        self._sync_reviewer_bottom_bar_controls()

    def _on_reviewer_bottom_bar_color_only_changed(self, checked):
        if checked:
            self.reviewer_bottom_bar_mode = "color"
            for toggle in (self.reviewer_bar_match_main_toggle, self.reviewer_bar_match_overview_toggle, self.reviewer_bar_match_reviewer_toggle):
                with QSignalBlocker(toggle):
                    toggle.setChecked(False)
        elif not any(toggle.isChecked() for toggle in (
            self.reviewer_bar_match_main_toggle,
            self.reviewer_bar_match_overview_toggle,
            self.reviewer_bar_match_reviewer_toggle,
        )):
            self.reviewer_bottom_bar_mode = "image_color"
        self._sync_reviewer_bottom_bar_controls()

    def _bottom_bar_source_state_from_config(self, source):
        if source == "main":
            mode = mw.col.conf.get("modern_menu_background_mode", "color")
            color_mode = mw.col.conf.get("modern_menu_bg_color_theme_mode", "separate")
            image_mode = mw.col.conf.get("modern_menu_bg_image_theme_mode", mw.col.conf.get("modern_menu_background_image_mode", "separate"))
            light_color = mw.col.conf.get("modern_menu_bg_color_light", "#f2f2f2")
            dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
            folder = self._main_bg_folder_path()
            single_image = mw.col.conf.get("modern_menu_background_image", "")
            light_image = mw.col.conf.get("modern_menu_background_image_light", single_image)
            dark_image = mw.col.conf.get("modern_menu_background_image_dark", single_image)
        elif source == "overview":
            mode = self.current_config.get("onigiri_overview_bg_mode", "main")
            if mode == "main":
                return self._bottom_bar_source_state_from_config("main")
            color_mode = self.current_config.get("onigiri_overview_bg_color_theme_mode", "separate")
            image_mode = self.current_config.get("onigiri_overview_bg_image_theme_mode", self.current_config.get("onigiri_overview_bg_image_mode", "separate"))
            light_color = self.current_config.get("onigiri_overview_bg_light_color", "#f2f2f2")
            dark_color = self.current_config.get("onigiri_overview_bg_dark_color", "#2C2C2C")
            folder = os.path.join(self.addon_path, "user_files", "main_bg")
            single_image = self.current_config.get("onigiri_overview_bg_image", "")
            light_image = self.current_config.get("onigiri_overview_bg_image_light", single_image)
            dark_image = self.current_config.get("onigiri_overview_bg_image_dark", single_image)
        else:
            if hasattr(self, "reviewer_bg_color_only_toggle") and self._modern_background_spec("reviewer"):
                dynamic = self.reviewer_bg_dynamic_toggle.isChecked()
                color_only = self.reviewer_bg_color_only_toggle.isChecked()
                light_color = self._modern_background_color_for_input(self.reviewer_bg_light_color_input)
                dark_color = self._modern_background_color_for_input(self.reviewer_bg_dark_color_input, light_color)
                single_color = self._modern_background_color_for_input(self.reviewer_bg_single_color_input, light_color)
                spec = self._modern_background_spec("reviewer")
                single_key, light_key, dark_key = self._modern_background_gallery_keys(spec)
                if dynamic:
                    light_image = self.galleries.get(light_key, {}).get("selected", "")
                    dark_image = self.galleries.get(dark_key, {}).get("selected", "")
                else:
                    light_image = dark_image = self.galleries.get(single_key, {}).get("selected", "")
                    light_color = dark_color = single_color
                return {
                    "light_color": light_color,
                    "dark_color": dark_color,
                    "light_image": "" if color_only else self._modern_bg_image_path(spec, light_image),
                    "dark_image": "" if color_only else self._modern_bg_image_path(spec, dark_image),
                    "dynamic": dynamic,
                }
            mode = self.current_config.get("onigiri_reviewer_bg_mode", "main")
            if mode == "main":
                return self._bottom_bar_source_state_from_config("main")
            color_mode = self.current_config.get("onigiri_reviewer_bg_color_theme_mode", "separate")
            image_mode = self.current_config.get("onigiri_reviewer_bg_image_theme_mode", self.current_config.get("onigiri_reviewer_bg_image_mode", "separate"))
            light_color = self.current_config.get("onigiri_reviewer_bg_light_color", "#f2f2f2")
            dark_color = self.current_config.get("onigiri_reviewer_bg_dark_color", "#2C2C2C")
            folder = os.path.join(self.addon_path, "user_files", "reviewer_bg")
            single_image = self.current_config.get("onigiri_reviewer_bg_image", "")
            light_image = self.current_config.get("onigiri_reviewer_bg_image_light", single_image)
            dark_image = self.current_config.get("onigiri_reviewer_bg_image_dark", single_image)

        dynamic = color_mode == "separate" or image_mode == "separate"
        if mode in {"color", "accent"}:
            single_image = light_image = dark_image = ""
        if not dynamic:
            dark_color = light_color
            dark_image = light_image = single_image
        return {
            "light_color": light_color,
            "dark_color": dark_color,
            "light_image": os.path.join(folder, light_image) if light_image else "",
            "dark_image": os.path.join(folder, dark_image) if dark_image else "",
            "dynamic": dynamic,
        }

    def _bottom_bar_viewport_slice(self, image_path, width, height, blur):
        source = QPixmap(image_path)
        if source.isNull():
            return QPixmap()
        viewport_height = max(int(height), int(width / 2.2))
        scaled = source.scaled(
            max(1, int(width)),
            max(1, viewport_height),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - int(width)) // 2)
        y = max(0, scaled.height() - int(height))
        pixmap = scaled.copy(x, y, int(width), int(height))
        blur = int(blur or 0)
        if blur > 0:
            return self._qt_blurred_pixmap(pixmap, float(blur) / 3.0)
        return pixmap

    def _paint_bottom_bar_background_layer(self, painter, rect, color, image_path, blur, opacity, match_viewport=False):
        painter.fillRect(rect, QColor(color))
        if image_path and os.path.exists(image_path):
            if match_viewport:
                image = self._bottom_bar_viewport_slice(image_path, int(rect.width()), int(rect.height()), blur)
            else:
                image = self._background_cover_image_with_effect(
                    image_path,
                    int(rect.width()),
                    int(rect.height()),
                    blur,
                    vertical_anchor="bottom",
                )
            if not image.isNull():
                painter.setOpacity(max(0.0, min(1.0, opacity / 100.0)))
                painter.drawPixmap(int(rect.x()), int(rect.y()), image)
                painter.setOpacity(1.0)

    def _bottom_bar_interval_color(self, mode):
        suffix = "dark" if mode == "dark" else "light"
        fallback = "#aaaaaa" if suffix == "dark" else "#666666"
        return self._bottom_bar_color_value(f"stattxt_color_{suffix}", fallback)

    def _assign_bottom_bar_background_image(self, filename):
        self.galleries.setdefault("reviewer_bar_bg", {"selected": "", "folder": "user_files/reviewer_bar_bg"})
        self.galleries["reviewer_bar_bg"]["selected"] = filename
        if self.reviewer_bottom_bar_mode not in {"main", "match_overview_bg", "match_reviewer_bg"}:
            self.reviewer_bottom_bar_mode = "image_color"
            with QSignalBlocker(self.reviewer_bar_color_only_toggle):
                self.reviewer_bar_color_only_toggle.setChecked(False)
        self._sync_reviewer_bottom_bar_controls()

    def _import_bottom_bar_background(self):
        filepath, _ = QFileDialog.getOpenFileName(self, tr("import_image"), "", "Images (*.png *.jpg *.jpeg *.gif *.webp)")
        if not filepath:
            return
        filename = os.path.basename(filepath)
        dest_path = os.path.join(self._bottom_bar_bg_folder_path(), filename)
        base, ext = os.path.splitext(filename)
        index = 2
        while os.path.exists(dest_path) and os.path.abspath(filepath) != os.path.abspath(dest_path):
            filename = f"{base}-{index}{ext}"
            dest_path = os.path.join(self._bottom_bar_bg_folder_path(), filename)
            index += 1
        try:
            if os.path.abspath(filepath) != os.path.abspath(dest_path):
                shutil.copy(filepath, dest_path)
            self._assign_bottom_bar_background_image(filename)
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not import image: {exc}")

    def _clear_bottom_bar_background(self):
        if "reviewer_bar_bg" in self.galleries:
            self.galleries["reviewer_bar_bg"]["selected"] = ""
        self._update_reviewer_bottom_bar_preview()

    def _open_bottom_bar_background_gallery(self):
        dialog = BackgroundGalleryDialog(self)
        dialog.setWindowTitle("Select from Gallery")
        dialog.resize(760, 520)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self._style_background_gallery_dialog(dialog)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("backgroundGalleryContent")
        grid = FlowLayout(content, margin=0, spacing=10)
        selected = self.galleries.get("reviewer_bar_bg", {}).get("selected", "")
        for filename in self._bottom_bar_bg_image_files():
            tile = BackgroundGalleryTile(filename, self._bottom_bar_bg_image_path(filename), self.accent_color)
            tile.setBadges(["Selected"] if filename == selected else [])
            tile.clicked.connect(lambda chosen, d=dialog: (self._assign_bottom_bar_background_image(chosen), d.accept()))
            tile.hovered.connect(dialog.setHoveredTile)
            grid.addWidget(tile)
        if not self._bottom_bar_bg_image_files():
            empty = QLabel("No images imported yet.")
            empty.setObjectName("backgroundGalleryEmpty")
            grid.addWidget(empty)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        close_button = self._create_main_bg_button("Done")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def _bottom_bar_answer_button_color_sections(self):
        button_defs = [
            ("Again Button", "again", "#ffb3b3", "#4d0000", "#ffcccb", "#4a0000"),
            ("Hard Button", "hard", "#ffe0b3", "#4d2600", "#ffd699", "#4d1d00"),
            ("Good Button", "good", "#b3ffb3", "#004d00", "#90ee90", "#004000"),
            ("Easy Button", "easy", "#b3d9ff", "#00264d", "#add8e6", "#002952"),
        ]
        sections = []
        for title, key, bg_l, text_l, bg_d, text_d in button_defs:
            sections.append((title, [
                (f"{title.split()[0]} (Light)", f"btn_{key}_bg_light", self.current_config.get(f"onigiri_reviewer_btn_{key}_bg_light", bg_l)),
                (f"{title.split()[0]} (Dark)", f"btn_{key}_bg_dark", self.current_config.get(f"onigiri_reviewer_btn_{key}_bg_dark", bg_d)),
                (f"{title.split()[0]} Text (Light)", f"btn_{key}_text_light", self.current_config.get(f"onigiri_reviewer_btn_{key}_text_light", text_l)),
                (f"{title.split()[0]} Text (Dark)", f"btn_{key}_text_dark", self.current_config.get(f"onigiri_reviewer_btn_{key}_text_dark", text_d)),
            ]))
        sections.append(("Answer Hover Numbers", [
            ("Number (Light)", "stattxt_color_light", self.current_config.get("onigiri_reviewer_stattxt_color_light", "#666666")),
            ("Number (Dark)", "stattxt_color_dark", self.current_config.get("onigiri_reviewer_stattxt_color_dark", "#aaaaaa")),
        ]))
        return sections

    def _bottom_bar_pre_answer_button_color_sections(self):
        return [
            ("Pre-Answer Buttons", [
                ("Other (Light)", "other_btn_bg_light", self.current_config.get("onigiri_reviewer_other_btn_bg_light", "#ffffff")),
                ("Other (Dark)", "other_btn_bg_dark", self.current_config.get("onigiri_reviewer_other_btn_bg_dark", "#3a3a3a")),
                ("Other Text (Light)", "other_btn_text_light", self.current_config.get("onigiri_reviewer_other_btn_text_light", "#2c2c2c")),
                ("Other Text (Dark)", "other_btn_text_dark", self.current_config.get("onigiri_reviewer_other_btn_text_dark", "#e0e0e0")),
                ("Hover BG (Light)", "other_btn_hover_bg_light", self.current_config.get("onigiri_reviewer_other_btn_hover_bg_light", "#2c2c2c")),
                ("Hover BG (Dark)", "other_btn_hover_bg_dark", self.current_config.get("onigiri_reviewer_other_btn_hover_bg_dark", "#e0e0e0")),
                ("Hover Text (Light)", "other_btn_hover_text_light", self.current_config.get("onigiri_reviewer_other_btn_hover_text_light", "#f0f0f0")),
                ("Hover Text (Dark)", "other_btn_hover_text_dark", self.current_config.get("onigiri_reviewer_other_btn_hover_text_dark", "#3a3a3a")),
            ]),
            ("Pre-Answer Count Colors", self._bottom_bar_pre_answer_count_color_rows()),
        ]

    def _bottom_bar_overview_count_color_from_config(self, kind, mode, role):
        specs = {
            "new": {
                "bg": ("new_bubble", "--new-count-bubble-bg", "#1e8cff"),
                "text": ("new_text", "--new-count-bubble-fg", "#ffffff"),
            },
            "learn": {
                "bg": ("learn_bubble", "--learn-count-bubble-bg", "#19c96b"),
                "text": ("learn_text", "--learn-count-bubble-fg", "#ffffff"),
            },
            "review": {
                "bg": ("review_bubble", "--review-count-bubble-bg", "#ff5757"),
                "text": ("review_text", "--review-count-bubble-fg", "#ffffff"),
            },
        }
        overview_style = self.current_config.get("overview_style", {})
        overview_colors = overview_style.get("colors", {}) if isinstance(overview_style, dict) else {}
        mode_colors = overview_colors.get(mode, {}) if isinstance(overview_colors, dict) and isinstance(overview_colors.get(mode, {}), dict) else {}
        palette_colors = self.current_config.get("colors", {}).get(mode, {})
        if not isinstance(palette_colors, dict):
            palette_colors = {}
        overview_key, palette_key, fallback = specs.get(kind, specs["new"]).get(role, specs["new"]["bg"])
        return mode_colors.get(overview_key) or palette_colors.get(palette_key) or fallback

    def _bottom_bar_pre_answer_count_color_rows(self):
        rows = []
        labels = (("new", "New"), ("learn", "Learning"), ("review", "Review"))
        for mode, suffix in (("light", "Light"), ("dark", "Dark")):
            for kind, label in labels:
                rows.append((f"{label} BG ({suffix})", f"pre_count_{kind}_bg_{mode}", self._bottom_bar_overview_count_color_from_config(kind, mode, "bg")))
                rows.append((f"{label} Text ({suffix})", f"pre_count_{kind}_text_{mode}", self._bottom_bar_overview_count_color_from_config(kind, mode, "text")))
        return rows

    def _create_bottom_bar_inherited_effect_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = QLabel("Blur and opacity are inherited from the Reviewer Background.")
        label.setObjectName("mainBackgroundControlLabel")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return page

    def _reviewer_background_effect_values_for_bottom_bar(self):
        if hasattr(self, "reviewer_bg_blur_slider") and hasattr(self, "reviewer_bg_opacity_slider"):
            return self.reviewer_bg_blur_slider.value(), self.reviewer_bg_opacity_slider.value()
        if hasattr(self, "reviewer_bg_main_radio") and self.reviewer_bg_main_radio.isChecked():
            return self.reviewer_bg_main_blur_spinbox.value(), self.reviewer_bg_main_opacity_spinbox.value()
        if hasattr(self, "reviewer_bg_blur_spinbox") and hasattr(self, "reviewer_bg_opacity_spinbox"):
            return self.reviewer_bg_blur_spinbox.value(), self.reviewer_bg_opacity_spinbox.value()
        reviewer_mode = self.current_config.get("onigiri_reviewer_bg_mode", "main")
        if reviewer_mode == "main":
            return (
                self.current_config.get("onigiri_reviewer_bg_main_blur", 0),
                self.current_config.get("onigiri_reviewer_bg_main_opacity", 100),
            )
        return (
            self.current_config.get("onigiri_reviewer_bg_blur", 0),
            self.current_config.get("onigiri_reviewer_bg_opacity", 100),
        )

    def create_bottom_bar_background_and_buttons_section(self):
        section = SectionGroup("", self)
        layout = section.content_layout

        self.galleries["reviewer_bar_bg"] = {
            "selected": self.current_config.get("onigiri_reviewer_bottom_bar_bg_image", ""),
            "folder": "user_files/reviewer_bar_bg",
        }

        self.bottom_bar_designer = QFrame()
        self.bottom_bar_designer.setObjectName("mainBackgroundDesigner")
        outer = QVBoxLayout(self.bottom_bar_designer)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        preview_header = QWidget()
        preview_header_layout = QHBoxLayout(preview_header)
        preview_header_layout.setContentsMargins(0, 0, 0, 0)
        preview_header_layout.setSpacing(10)
        preview_title = QLabel("Reviewer Buttons")
        preview_title.setObjectName("sectionTitle")
        preview_header_layout.addWidget(preview_title)
        preview_header_layout.addStretch()

        self.bottom_bar_button_mode = "answer"
        self.bottom_bar_button_mode_group = QButtonGroup(self)
        self.bottom_bar_button_mode_group.setExclusive(True)
        mode_bg = "#303030" if theme_manager.night_mode else "#f1f1f1"
        mode_fg = "#f3f4f6" if theme_manager.night_mode else "#111111"
        mode_hover = "#3a3a3a" if theme_manager.night_mode else "#e7e7e7"
        self.bottom_bar_pre_answer_mode_button = PillSegmentButton(
            "Pre-Answer Buttons", mode_bg, mode_fg, self.accent_color, hover_bg=mode_hover
        )
        self.bottom_bar_answer_mode_button = PillSegmentButton(
            "Answer Buttons", mode_bg, mode_fg, self.accent_color, hover_bg=mode_hover
        )
        for button in (self.bottom_bar_pre_answer_mode_button, self.bottom_bar_answer_mode_button):
            button.setFixedSize(188, 34)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            font = button.font()
            font.setPointSize(13)
            button.setFont(font)
            self.bottom_bar_button_mode_group.addButton(button)
            preview_header_layout.addWidget(button)
        self.bottom_bar_answer_mode_button.setChecked(True)

        self.bottom_bar_preview_mode = "dark" if theme_manager.night_mode else "light"
        self.bottom_bar_preview_mode_widget, self.bottom_bar_preview_mode_toggle = self._create_light_dark_mode_toggle(
            self.bottom_bar_preview_mode,
            self._on_bottom_bar_preview_mode_toggled,
        )
        preview_header_layout.addWidget(self.bottom_bar_preview_mode_widget)
        outer.addWidget(preview_header)

        self.bottom_bar_preview = BackgroundPreviewLabel(aspect_ratio=8.5, minimum_preview_height=118)
        self.bottom_bar_preview.setObjectName("mainBackgroundPreview")
        self.bottom_bar_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bottom_bar_preview.setMouseTracking(True)
        self.bottom_bar_preview.installEventFilter(self)
        self._bottom_bar_preview_hover_key = None
        self._bottom_bar_preview_button_rects = []
        outer.addWidget(self.bottom_bar_preview)

        background_left = QWidget()
        background_left.setMinimumWidth(0)
        background_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        left_layout = QGridLayout(background_left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setHorizontalSpacing(10)
        left_layout.setVerticalSpacing(10)

        self.reviewer_bar_import_button = self._create_main_bg_button("Import")
        self.reviewer_bar_clear_button = self._create_main_bg_button("Clear Image")
        self.reviewer_bar_gallery_button = self._create_main_bg_button("Select from Gallery")
        left_layout.addWidget(self.reviewer_bar_import_button, 0, 0)
        left_layout.addWidget(self.reviewer_bar_clear_button, 0, 1)
        left_layout.addWidget(self.reviewer_bar_gallery_button, 1, 0, 1, 2)

        bar_color_rows = self._bottom_bar_custom_color_rows()
        self.reviewer_bar_color_stack = QStackedWidget()
        self.reviewer_bar_color_stack.addWidget(self._create_bottom_bar_color_grid([("Light Color", "reviewer_bar_light", bar_color_rows[0][2])], columns=1))
        self.reviewer_bar_color_stack.addWidget(self._create_bottom_bar_color_grid([("Dark Color", "reviewer_bar_dark", bar_color_rows[1][2])], columns=1))
        self.reviewer_bar_color_rows_widget = self.reviewer_bar_color_stack
        left_layout.addWidget(self.reviewer_bar_color_stack, 2, 0, 1, 2)
        left_layout.setColumnStretch(0, 1)
        left_layout.setColumnStretch(1, 1)

        background_right = QWidget()
        background_right.setMinimumWidth(0)
        background_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        right_layout = QVBoxLayout(background_right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        self.reviewer_bar_blur_spinbox = self._create_bottom_bar_effect_slider(self.current_config.get("onigiri_reviewer_bottom_bar_bg_blur", 0))
        self.reviewer_bar_opacity_spinbox = self._create_bottom_bar_effect_slider(self.current_config.get("onigiri_reviewer_bottom_bar_bg_opacity", 100))
        self.reviewer_bar_match_main_blur_spinbox = self._create_bottom_bar_effect_slider(self.current_config.get("onigiri_reviewer_bottom_bar_match_main_blur", 0))
        self.reviewer_bar_match_main_opacity_spinbox = self._create_bottom_bar_effect_slider(self.current_config.get("onigiri_reviewer_bottom_bar_match_main_opacity", 100))
        self.reviewer_bar_match_overview_bg_blur_spinbox = self._create_bottom_bar_effect_slider(self.current_config.get("onigiri_reviewer_bottom_bar_match_overview_bg_blur", 0))
        self.reviewer_bar_match_overview_bg_opacity_spinbox = self._create_bottom_bar_effect_slider(self.current_config.get("onigiri_reviewer_bottom_bar_match_overview_bg_opacity", 100))
        self.reviewer_bar_match_reviewer_bg_blur_spinbox = self._create_bottom_bar_effect_slider(self.current_config.get("onigiri_reviewer_bottom_bar_match_reviewer_bg_blur", 0))
        self.reviewer_bar_match_reviewer_bg_opacity_spinbox = self._create_bottom_bar_effect_slider(self.current_config.get("onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity", 100))

        custom_blur_label = QLabel()
        custom_opacity_label = QLabel()
        main_blur_label = QLabel()
        main_opacity_label = QLabel()
        overview_blur_label = QLabel()
        overview_opacity_label = QLabel()
        self.reviewer_bar_match_reviewer_bg_blur_label = QLabel()
        self.reviewer_bar_match_reviewer_bg_opacity_label = QLabel()
        for slider, label in (
            (self.reviewer_bar_blur_spinbox, custom_blur_label),
            (self.reviewer_bar_opacity_spinbox, custom_opacity_label),
            (self.reviewer_bar_match_main_blur_spinbox, main_blur_label),
            (self.reviewer_bar_match_main_opacity_spinbox, main_opacity_label),
            (self.reviewer_bar_match_overview_bg_blur_spinbox, overview_blur_label),
            (self.reviewer_bar_match_overview_bg_opacity_spinbox, overview_opacity_label),
            (self.reviewer_bar_match_reviewer_bg_blur_spinbox, self.reviewer_bar_match_reviewer_bg_blur_label),
            (self.reviewer_bar_match_reviewer_bg_opacity_spinbox, self.reviewer_bar_match_reviewer_bg_opacity_label),
        ):
            self._wire_bottom_bar_effect_slider(slider, label)

        # Blur/opacity are inherited from the Reviewer Background, so these two
        # sliders are shown locked (read-only) with the small lock icon.
        self.reviewer_bar_match_reviewer_bg_blur_spinbox.setEnabled(False)
        self.reviewer_bar_match_reviewer_bg_opacity_spinbox.setEnabled(False)

        self.reviewer_bar_effect_stack = QStackedWidget()
        self.reviewer_bar_effect_stack.addWidget(self._create_bottom_bar_effect_page(self.reviewer_bar_blur_spinbox, custom_blur_label, self.reviewer_bar_opacity_spinbox, custom_opacity_label))
        self.reviewer_bar_effect_stack.addWidget(self._create_bottom_bar_effect_page(self.reviewer_bar_match_main_blur_spinbox, main_blur_label, self.reviewer_bar_match_main_opacity_spinbox, main_opacity_label))
        self.reviewer_bar_effect_stack.addWidget(self._create_bottom_bar_effect_page(self.reviewer_bar_match_overview_bg_blur_spinbox, overview_blur_label, self.reviewer_bar_match_overview_bg_opacity_spinbox, overview_opacity_label))
        self.reviewer_bar_effect_stack.addWidget(self._create_bottom_bar_effect_page(self.reviewer_bar_match_reviewer_bg_blur_spinbox, self.reviewer_bar_match_reviewer_bg_blur_label, self.reviewer_bar_match_reviewer_bg_opacity_spinbox, self.reviewer_bar_match_reviewer_bg_opacity_label))
        right_layout.addWidget(self.reviewer_bar_effect_stack)

        self.reviewer_bar_dynamic_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.reviewer_bar_color_only_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.reviewer_bar_match_main_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.reviewer_bar_match_overview_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.reviewer_bar_match_reviewer_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        reviewer_bar_light_color = self.current_config.get("onigiri_reviewer_bottom_bar_bg_light_color", "#f2f2f2")
        reviewer_bar_dark_color = self.current_config.get("onigiri_reviewer_bottom_bar_bg_dark_color", "#2C2C2C")
        self.reviewer_bar_dynamic_toggle.setChecked(str(reviewer_bar_light_color).lower() != str(reviewer_bar_dark_color).lower())
        self.reviewer_bar_color_only_toggle.setChecked(self.reviewer_bottom_bar_mode == "color")
        self.reviewer_bar_match_main_toggle.setChecked(self.reviewer_bottom_bar_mode == "main")
        self.reviewer_bar_match_overview_toggle.setChecked(self.reviewer_bottom_bar_mode == "match_overview_bg")
        self.reviewer_bar_match_reviewer_toggle.setChecked(self.reviewer_bottom_bar_mode == "match_reviewer_bg")

        right_layout.addWidget(self._create_main_bg_toggle_row("Dynamic mode", self.reviewer_bar_dynamic_toggle))
        right_layout.addWidget(self._create_main_bg_toggle_row("Color only", self.reviewer_bar_color_only_toggle))
        right_layout.addWidget(self._create_main_bg_toggle_row("Match Main Menu Background", self.reviewer_bar_match_main_toggle))
        right_layout.addWidget(self._create_main_bg_toggle_row("Match Overviewer Background", self.reviewer_bar_match_overview_toggle))
        right_layout.addWidget(self._create_main_bg_toggle_row("Match Reviewer Background", self.reviewer_bar_match_reviewer_toggle))
        right_layout.addStretch()

        outer.addWidget(ResponsivePairWidget(background_right, background_left, spacing=18, breakpoint=720))

        general = QWidget()
        general_layout = QGridLayout(general)
        general_layout.setContentsMargins(0, 2, 0, 0)
        general_layout.setHorizontalSpacing(14)
        general_layout.setVerticalSpacing(10)

        self.reviewer_btn_custom_enable_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.reviewer_btn_custom_enable_toggle.setChecked(self.current_config.get("onigiri_reviewer_btn_custom_enabled", True))
        general_layout.addWidget(self._create_main_bg_toggle_row(tr("enable_custom_buttons_label"), self.reviewer_btn_custom_enable_toggle), 0, 0)
        self.reviewer_stattxt_visible_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.reviewer_stattxt_visible_toggle.setChecked(self.current_config.get("onigiri_reviewer_stattxt_visible", True))
        general_layout.addWidget(self._create_main_bg_toggle_row(tr("show_bottom_bar_numbers", "Show numbers"), self.reviewer_stattxt_visible_toggle), 2, 1)

        self.reviewer_btn_radius_spin = QSpinBox()
        self.reviewer_btn_radius_spin.setRange(0, 100)
        self.reviewer_btn_radius_spin.setSuffix(" px")
        self.reviewer_btn_radius_spin.setValue(self.current_config.get("onigiri_reviewer_btn_radius", 12))
        self.reviewer_btn_padding_spin = QSpinBox()
        self.reviewer_btn_padding_spin.setRange(0, 100)
        self.reviewer_btn_padding_spin.setSuffix(" px")
        self.reviewer_btn_padding_spin.setValue(self.current_config.get("onigiri_reviewer_btn_padding", 5))
        self.reviewer_btn_height_spin = QSpinBox()
        self.reviewer_btn_height_spin.setRange(0, 200)
        self.reviewer_btn_height_spin.setSuffix(" px")
        self.reviewer_btn_height_spin.setValue(self.current_config.get("onigiri_reviewer_btn_height", 40))
        self.reviewer_bar_height_spin = QSpinBox()
        self.reviewer_bar_height_spin.setRange(20, 300)
        self.reviewer_bar_height_spin.setSuffix(" px")
        self.reviewer_bar_height_spin.setValue(self.current_config.get("onigiri_reviewer_bar_height", 60))

        general_layout.addWidget(self._create_bottom_bar_number_row(tr("border_radius_label"), self.reviewer_btn_radius_spin), 0, 1)
        general_layout.addWidget(self._create_bottom_bar_number_row(tr("button_padding_label"), self.reviewer_btn_padding_spin), 1, 0)
        general_layout.addWidget(self._create_bottom_bar_number_row(tr("min_height_label"), self.reviewer_btn_height_spin), 1, 1)
        general_layout.addWidget(self._create_bottom_bar_number_row(tr("bar_height_label"), self.reviewer_bar_height_spin), 2, 0)
        outer.addWidget(general)

        self.bottom_bar_button_config_stack = QStackedWidget()
        self.bottom_bar_answer_color_stack = QStackedWidget()
        answer_sections = self._bottom_bar_answer_button_color_sections()
        self.bottom_bar_answer_color_stack.addWidget(self._create_bottom_bar_button_config_page(answer_sections, "light"))
        self.bottom_bar_answer_color_stack.addWidget(self._create_bottom_bar_button_config_page(answer_sections, "dark"))

        self.bottom_bar_pre_answer_color_stack = QStackedWidget()
        pre_answer_sections = self._bottom_bar_pre_answer_button_color_sections()
        self.bottom_bar_pre_answer_color_stack.addWidget(self._create_bottom_bar_button_config_page(pre_answer_sections, "light"))
        self.bottom_bar_pre_answer_color_stack.addWidget(self._create_bottom_bar_button_config_page(pre_answer_sections, "dark"))

        self.bottom_bar_button_config_stack.addWidget(self.bottom_bar_answer_color_stack)
        self.bottom_bar_button_config_stack.addWidget(self.bottom_bar_pre_answer_color_stack)
        outer.addWidget(self.bottom_bar_button_config_stack)

        reset_row = QWidget()
        reset_layout = QHBoxLayout(reset_row)
        reset_layout.setContentsMargins(0, 0, 0, 0)
        reset_layout.addStretch()
        reset_bottom_bar_button = QPushButton(tr("reset_bottom_bar_default"))
        reset_bottom_bar_button.setStyleSheet(self._reset_button_stylesheet())
        reset_bottom_bar_button.clicked.connect(self.reset_reviewer_bottom_bar_to_default)
        reset_buttons_button = QPushButton(tr("reset_answer_buttons_btn"))
        reset_buttons_button.setStyleSheet(self._reset_button_stylesheet())
        reset_buttons_button.clicked.connect(self.reset_reviewer_buttons_to_default)
        reset_layout.addWidget(reset_bottom_bar_button)
        reset_layout.addWidget(reset_buttons_button)
        reset_layout.addStretch()
        outer.addWidget(reset_row)

        layout.addWidget(self.bottom_bar_designer)

        self.reviewer_bar_import_button.clicked.connect(self._import_bottom_bar_background)
        self.reviewer_bar_clear_button.clicked.connect(self._clear_bottom_bar_background)
        self.reviewer_bar_gallery_button.clicked.connect(self._open_bottom_bar_background_gallery)
        self.reviewer_bar_dynamic_toggle.toggled.connect(lambda _=None: self._sync_reviewer_bottom_bar_controls())
        self.reviewer_bar_color_only_toggle.toggled.connect(self._on_reviewer_bottom_bar_color_only_changed)
        self.reviewer_bar_match_main_toggle.toggled.connect(lambda checked: self._on_reviewer_bottom_bar_match_changed("main", checked))
        self.reviewer_bar_match_overview_toggle.toggled.connect(lambda checked: self._on_reviewer_bottom_bar_match_changed("match_overview_bg", checked))
        self.reviewer_bar_match_reviewer_toggle.toggled.connect(lambda checked: self._on_reviewer_bottom_bar_match_changed("match_reviewer_bg", checked))
        self.bottom_bar_answer_mode_button.toggled.connect(lambda checked: self._set_bottom_bar_button_mode("answer") if checked else None)
        self.bottom_bar_pre_answer_mode_button.toggled.connect(lambda checked: self._set_bottom_bar_button_mode("pre_answer") if checked else None)
        self.reviewer_btn_custom_enable_toggle.toggled.connect(lambda _=None: self._update_reviewer_bottom_bar_preview())
        self.reviewer_stattxt_visible_toggle.toggled.connect(lambda _=None: self._update_reviewer_bottom_bar_preview())
        for spinbox in (self.reviewer_btn_radius_spin, self.reviewer_btn_padding_spin, self.reviewer_btn_height_spin, self.reviewer_bar_height_spin):
            spinbox.valueChanged.connect(lambda _=None: self._update_reviewer_bottom_bar_preview())

        self._set_bottom_bar_button_mode("answer")
        self._sync_reviewer_bottom_bar_controls()
        QTimer.singleShot(0, self._update_reviewer_bottom_bar_preview)
        return section

    def _set_bottom_bar_button_mode(self, mode):
        self.bottom_bar_button_mode = "pre_answer" if mode == "pre_answer" else "answer"
        if hasattr(self, "bottom_bar_button_config_stack"):
            self.bottom_bar_button_config_stack.setCurrentIndex(1 if self.bottom_bar_button_mode == "pre_answer" else 0)
        self._update_bottom_bar_palette_controls()
        if hasattr(self, "bottom_bar_pre_answer_mode_button"):
            with QSignalBlocker(self.bottom_bar_pre_answer_mode_button):
                self.bottom_bar_pre_answer_mode_button.setChecked(self.bottom_bar_button_mode == "pre_answer")
        if hasattr(self, "bottom_bar_answer_mode_button"):
            with QSignalBlocker(self.bottom_bar_answer_mode_button):
                self.bottom_bar_answer_mode_button.setChecked(self.bottom_bar_button_mode == "answer")
        self._bottom_bar_preview_hover_key = None
        self._update_reviewer_bottom_bar_preview()

    def _sync_reviewer_bottom_bar_controls(self):
        if not hasattr(self, "reviewer_bar_effect_stack"):
            return
        mode = self.reviewer_bottom_bar_mode
        stack_index = {"image_color": 0, "color": 0, "main": 1, "match_overview_bg": 2, "match_reviewer_bg": 3}.get(mode, 0)
        self.reviewer_bar_effect_stack.setCurrentIndex(stack_index)
        if mode == "match_reviewer_bg" and hasattr(self, "reviewer_bar_match_reviewer_bg_blur_spinbox"):
            inherited_blur, inherited_opacity = self._reviewer_background_effect_values_for_bottom_bar()
            for slider, value in (
                (self.reviewer_bar_match_reviewer_bg_blur_spinbox, inherited_blur),
                (self.reviewer_bar_match_reviewer_bg_opacity_spinbox, inherited_opacity),
            ):
                with QSignalBlocker(slider):
                    slider.setValue(int(value))
            self.reviewer_bar_match_reviewer_bg_blur_label.setText(f"{self.reviewer_bar_match_reviewer_bg_blur_spinbox.value()}%")
            self.reviewer_bar_match_reviewer_bg_opacity_label.setText(f"{self.reviewer_bar_match_reviewer_bg_opacity_spinbox.value()}%")
        is_custom = mode in {"color", "image_color"}
        color_only = mode == "color"
        for widget in (self.reviewer_bar_import_button, self.reviewer_bar_clear_button, self.reviewer_bar_gallery_button):
            widget.setEnabled(is_custom and not color_only)
        self.reviewer_bar_color_rows_widget.setEnabled(is_custom)
        self.reviewer_bar_color_rows_widget.setVisible(True)
        self.reviewer_bar_dynamic_toggle.setEnabled(is_custom)
        self.reviewer_bar_color_only_toggle.setEnabled(is_custom or mode == "color")
        self.reviewer_bar_dynamic_toggle.setToolTip("")
        self.reviewer_bar_color_only_toggle.setToolTip("")
        self.reviewer_bar_dynamic_toggle.update()
        self.reviewer_bar_color_only_toggle.update()
        self._update_bottom_bar_palette_controls()
        self._update_reviewer_bottom_bar_preview()

    def _bottom_bar_preview_mode(self):
        return getattr(self, "bottom_bar_preview_mode", "dark" if theme_manager.night_mode else "light")

    def _on_bottom_bar_preview_mode_toggled(self, mode):
        self.bottom_bar_preview_mode = "dark" if mode == "dark" else "light"
        self._update_bottom_bar_palette_controls()
        self._update_reviewer_bottom_bar_preview()

    def _update_bottom_bar_palette_controls(self):
        mode = self._bottom_bar_preview_mode()
        show_dark = mode == "dark"
        if hasattr(self, "reviewer_bar_color_stack"):
            dynamic = bool(getattr(self, "reviewer_bar_dynamic_toggle", None) and self.reviewer_bar_dynamic_toggle.isChecked())
            self.reviewer_bar_color_stack.setCurrentIndex(1 if dynamic and show_dark else 0)
            is_custom = getattr(self, "reviewer_bottom_bar_mode", "color") in {"color", "image_color"}
            lock_toggle = is_custom and not dynamic
            if hasattr(self, "bottom_bar_preview_mode_widget"):
                self.bottom_bar_preview_mode_widget.setEnabled(not lock_toggle)
                self.bottom_bar_preview_mode_widget.setToolTip("" if not lock_toggle else "Enable Dynamic mode to switch light/dark palettes.")
            light_label = getattr(self, "reviewer_bar_light_color_label_button", None)
            dark_label = getattr(self, "reviewer_bar_dark_color_label_button", None)
            if light_label:
                light_label.setText("Light Color" if dynamic else "Color")
            if dark_label:
                dark_label.setText("Dark Color")
        index = 1 if show_dark else 0
        for stack_name in ("bottom_bar_answer_color_stack", "bottom_bar_pre_answer_color_stack"):
            stack = getattr(self, stack_name, None)
            if stack:
                stack.setCurrentIndex(index)

    def _bottom_bar_preview_state(self):
        mode = self.reviewer_bottom_bar_mode
        if mode == "main":
            state = self._bottom_bar_source_state_from_config("main")
            blur = self.reviewer_bar_match_main_blur_spinbox.value()
            opacity = self.reviewer_bar_match_main_opacity_spinbox.value()
            state["match_viewport"] = True
        elif mode == "match_overview_bg":
            state = self._bottom_bar_source_state_from_config("overview")
            blur = self.reviewer_bar_match_overview_bg_blur_spinbox.value()
            opacity = self.reviewer_bar_match_overview_bg_opacity_spinbox.value()
            state["match_viewport"] = True
        elif mode == "match_reviewer_bg":
            state = self._bottom_bar_source_state_from_config("reviewer")
            blur, opacity = self._reviewer_background_effect_values_for_bottom_bar()
            state["match_viewport"] = True
        else:
            dynamic = self.reviewer_bar_dynamic_toggle.isChecked()
            light_color = self._bottom_bar_color_value("reviewer_bar_light", "#f2f2f2")
            dark_color = self._bottom_bar_color_value("reviewer_bar_dark", "#2C2C2C")
            if not dynamic:
                dark_color = light_color
            image_name = "" if mode == "color" else self.galleries.get("reviewer_bar_bg", {}).get("selected", "")
            image_path = self._bottom_bar_bg_image_path(image_name)
            state = {
                "light_color": light_color,
                "dark_color": dark_color,
                "light_image": image_path,
                "dark_image": image_path,
                "dynamic": dynamic,
                "match_viewport": False,
            }
            blur = self.reviewer_bar_blur_spinbox.value()
            opacity = self.reviewer_bar_opacity_spinbox.value()
        state["blur"] = blur
        state["opacity"] = opacity
        return state

    def _bottom_bar_button_colors(self, key, mode, hovered=False):
        suffix = "dark" if mode == "dark" else "light"
        if key == "other":
            if hovered:
                return (
                    self._bottom_bar_color_value(f"other_btn_hover_bg_{suffix}", "#e0e0e0" if suffix == "dark" else "#2c2c2c"),
                    self._bottom_bar_color_value(f"other_btn_hover_text_{suffix}", "#3a3a3a" if suffix == "dark" else "#f0f0f0"),
                )
            return (
                self._bottom_bar_color_value(f"other_btn_bg_{suffix}", "#3a3a3a" if suffix == "dark" else "#ffffff"),
                self._bottom_bar_color_value(f"other_btn_text_{suffix}", "#e0e0e0" if suffix == "dark" else "#2c2c2c"),
            )
        bg = self._bottom_bar_color_value(f"btn_{key}_bg_{suffix}", "#eeeeee")
        fg = self._bottom_bar_color_value(f"btn_{key}_text_{suffix}", "#111111")
        if hovered:
            return fg, bg
        return bg, fg

    def _bottom_bar_answer_hover_number_color(self, mode, inherited_color):
        color = self._bottom_bar_interval_color(mode)
        if str(color).lower() in {"#666666", "#aaaaaa"}:
            return inherited_color
        return color

    def _bottom_bar_overview_count_colors(self, kind, mode):
        suffix = "dark" if mode == "dark" else "light"
        bg_attr = f"pre_count_{kind}_bg_{suffix}"
        fg_attr = f"pre_count_{kind}_text_{suffix}"
        return (
            self._bottom_bar_color_value(bg_attr, self._bottom_bar_overview_count_color_from_config(kind, mode, "bg")),
            self._bottom_bar_color_value(fg_attr, self._bottom_bar_overview_count_color_from_config(kind, mode, "text")),
        )

    def _draw_bottom_bar_count_pill(self, painter, rect, text, bg, fg):
        path = QPainterPath()
        radius = rect.height() / 2
        path.addRoundedRect(rect, radius, radius)
        painter.fillPath(path, QColor(bg))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(8, min(15, int(rect.height() * 0.42))))
        painter.setFont(font)
        painter.setPen(QColor(fg))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_bottom_bar_pre_answer_counts(self, painter, rect, theme_mode):
        inset = max(4, rect.height() * 0.14)
        gap = max(5, rect.height() * 0.12)
        pill_rect = QRectF(rect).adjusted(inset, inset, -inset, -inset)
        pill_w = (pill_rect.width() - gap * 2) / 3
        samples = [
            ("new", self.current_config.get("onigiri_reviewer_stattxt_new", "9999")),
            ("learn", self.current_config.get("onigiri_reviewer_stattxt_learn", "46")),
            ("review", self.current_config.get("onigiri_reviewer_stattxt_review", "39")),
        ]
        for index, (kind, text) in enumerate(samples):
            bg, fg = self._bottom_bar_overview_count_colors(kind, theme_mode)
            item_rect = QRectF(pill_rect.x() + index * (pill_w + gap), pill_rect.y(), pill_w, pill_rect.height())
            self._draw_bottom_bar_count_pill(painter, item_rect, str(text), bg, fg)

    def _draw_bottom_bar_preview_button(self, painter, rect, label, key, theme_mode, hovered=False, pre_answer_counts=False):
        if self.reviewer_btn_custom_enable_toggle.isChecked():
            bg, fg = self._bottom_bar_button_colors(key, theme_mode, hovered)
            radius = self.reviewer_btn_radius_spin.value()
        else:
            if hovered:
                bg = "#111827" if theme_mode == "light" else "#f9fafb"
                fg = "#e5e7eb" if theme_mode == "light" else "#4b5563"
            else:
                bg = "#e5e7eb" if theme_mode == "light" else "#4b5563"
                fg = "#111827" if theme_mode == "light" else "#f9fafb"
            radius = 10
        path = QPainterPath()
        path.addRoundedRect(rect, min(radius, rect.height() / 2), min(radius, rect.height() / 2))
        painter.fillPath(path, QColor(bg))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(8, min(13, int(rect.height() * 0.34))))
        painter.setFont(font)
        painter.setPen(QColor(fg))
        show_numbers = getattr(self, "reviewer_stattxt_visible_toggle", None)
        numbers_visible = show_numbers.isChecked() if show_numbers else self.current_config.get("onigiri_reviewer_stattxt_visible", True)
        if numbers_visible and pre_answer_counts and hovered:
            self._draw_bottom_bar_pre_answer_counts(painter, rect, theme_mode)
        elif numbers_visible and hovered and key in {"again", "hard", "good", "easy"}:
            stat_font = QFont(font)
            stat_font.setBold(True)
            stat_font.setPointSize(max(9, min(16, int(rect.height() * 0.38))))
            painter.setFont(stat_font)
            painter.setPen(QColor(self._bottom_bar_answer_hover_number_color(theme_mode, fg)))
            stat_samples = {"again": "0", "hard": "+ 0", "good": "+ 0", "easy": "+ 24"}
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, stat_samples.get(key, "0"))
        else:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    def _update_reviewer_bottom_bar_preview(self):
        if not hasattr(self, "bottom_bar_preview"):
            return
        state = self._bottom_bar_preview_state()
        size = self.bottom_bar_preview.size()
        width = max(1, size.width())
        height = max(1, size.height())
        dpr = max(1.0, self.bottom_bar_preview.devicePixelRatioF())
        target = QPixmap(int(width * dpr), int(height * dpr))
        target.setDevicePixelRatio(dpr)
        target.fill(Qt.GlobalColor.transparent)

        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        bar_height = max(54, min(height - 12, int(self.reviewer_bar_height_spin.value() * 1.2)))
        bar_rect = QRectF(1, (height - bar_height) / 2, width - 2, bar_height)
        radius = min(24, bar_height / 2)
        path = QPainterPath()
        path.addRoundedRect(bar_rect, radius, radius)
        painter.setClipPath(path)

        mode = self._bottom_bar_preview_mode()
        self._paint_bottom_bar_background_layer(
            painter,
            bar_rect,
            state.get(f"{mode}_color", "#f2f2f2" if mode == "light" else "#2C2C2C"),
            state.get(f"{mode}_image", ""),
            state.get("blur", 0),
            state.get("opacity", 100),
            state.get("match_viewport", False),
        )

        painter.setClipping(False)
        painter.setPen(QPen(QColor("#4b5563" if theme_manager.night_mode else "#d1d5db"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        padding = max(4, self.reviewer_btn_padding_spin.value())
        button_h = max(30, min(bar_height - 18, self.reviewer_btn_height_spin.value()))
        y = bar_rect.y() + (bar_height - button_h) / 2
        self._bottom_bar_preview_button_rects = []
        preview_mode = getattr(self, "bottom_bar_button_mode", "answer")
        hover_key = getattr(self, "_bottom_bar_preview_hover_key", None)

        if preview_mode == "pre_answer":
            specs = [("Edit", "other", 70, "edit"), ("Show Answer", "other", 176, "show_answer"), ("More", "other", 70, "more")]
            total = sum(item[2] for item in specs)
            side_margin = max(18, width * 0.04)
            usable = max(1, width - side_margin * 2)
            scale = min(1.0, max(0.58, usable / max(1, total + 34)))
            button_gap = 17 * scale
            button_w_values = [max(50, base_w * scale + padding) for _, _, base_w, _ in specs]
            left_x = side_margin
            right_x = width - side_margin - button_w_values[2]
            center_x = (width - button_w_values[1]) / 2
            positions = [left_x, center_x, right_x]
            for (label, key, _base_w, button_id), button_w, x in zip(specs, button_w_values, positions):
                rect = QRectF(x, y, button_w, button_h)
                theme_mode = mode
                hovered = hover_key == button_id
                self._bottom_bar_preview_button_rects.append((button_id, QRectF(rect)))
                self._draw_bottom_bar_preview_button(
                    painter,
                    rect,
                    label,
                    key,
                    theme_mode,
                    hovered=hovered,
                    pre_answer_counts=(button_id == "show_answer"),
                )
        else:
            specs = [
                ("Edit", "other", 64, "edit"),
                ("Again", "again", 86, "again"),
                ("Hard", "hard", 82, "hard"),
                ("Good", "good", 82, "good"),
                ("Easy", "easy", 82, "easy"),
                ("More", "other", 64, "more"),
            ]
            gap = 10
            total = sum(item[2] for item in specs) + gap * (len(specs) - 1)
            scale = min(1.0, max(0.55, (width - 36) / max(1, total)))
            button_gap = gap * scale
            x = (width - (sum(item[2] * scale for item in specs) + button_gap * (len(specs) - 1))) / 2
            for label, key, base_w, button_id in specs:
                button_w = max(46, base_w * scale + padding)
                rect = QRectF(x, y, button_w, button_h)
                theme_mode = mode
                hovered = hover_key == button_id
                self._bottom_bar_preview_button_rects.append((button_id, QRectF(rect)))
                self._draw_bottom_bar_preview_button(painter, rect, label, key, theme_mode, hovered=hovered)
                x += button_w + button_gap
        painter.end()

        self.bottom_bar_preview.setPixmap(target)
        self.bottom_bar_preview.setText("")
        if hasattr(self, "preview_buttons"):
            self._update_reviewer_button_previews()

    def _handle_bottom_bar_preview_mouse_event(self, event):
        event_type = event.type()
        hover_changed = False
        if event_type in {QEvent.Type.MouseMove, QEvent.Type.Enter} and hasattr(event, "position"):
            hover_changed = self._set_bottom_bar_preview_hover(event.position())
        elif event_type == QEvent.Type.Leave:
            hover_changed = self._set_bottom_bar_preview_hover(None)

        return hover_changed

    def _set_bottom_bar_preview_hover(self, pos):
        next_key = None
        if pos is not None:
            point = QPointF(pos)
            for button_id, rect in getattr(self, "_bottom_bar_preview_button_rects", []):
                if rect.contains(point):
                    next_key = button_id
                    break
        if getattr(self, "_bottom_bar_preview_hover_key", None) == next_key:
            return False
        self._bottom_bar_preview_hover_key = next_key
        self._update_reviewer_bottom_bar_preview()
        return True

    def create_reviewer_buttons_section(self):
        section = SectionGroup(tr("answer_buttons_section_title"), self)
        layout = section.content_layout

        # --- General Button Settings ---
        general_group = QGroupBox(tr("general_button_settings_group"))
        general_layout = QVBoxLayout(general_group)
        general_layout.setSpacing(10)

        # Enable Toggle and other global settings
        # Row 1: Enable & Radius
        row1 = QHBoxLayout()
        
        enable_label = QLabel(tr("enable_custom_buttons_label"))
        self.reviewer_btn_custom_enable_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.reviewer_btn_custom_enable_toggle.setChecked(self.current_config.get("onigiri_reviewer_btn_custom_enabled", True))
        row1.addWidget(enable_label)
        row1.addWidget(self.reviewer_btn_custom_enable_toggle)
        row1.addSpacing(20)

        radius_label = QLabel(tr("border_radius_label"))
        self.reviewer_btn_radius_spin = QSpinBox()
        self.reviewer_btn_radius_spin.setRange(0, 100)
        self.reviewer_btn_radius_spin.setSuffix(" px")
        self.reviewer_btn_radius_spin.setValue(self.current_config.get("onigiri_reviewer_btn_radius", 12))
        row1.addWidget(radius_label)
        row1.addWidget(self.reviewer_btn_radius_spin)
        row1.addStretch()
        general_layout.addLayout(row1)

        # Row 2: Padding, Height & Bar Height
        row2 = QHBoxLayout()
        
        padding_label = QLabel(tr("button_padding_label"))
        self.reviewer_btn_padding_spin = QSpinBox()
        self.reviewer_btn_padding_spin.setRange(0, 100)
        self.reviewer_btn_padding_spin.setSuffix(" px")
        self.reviewer_btn_padding_spin.setValue(self.current_config.get("onigiri_reviewer_btn_padding", 5))
        row2.addWidget(padding_label)
        row2.addWidget(self.reviewer_btn_padding_spin)
        row2.addSpacing(20)

        btn_height_label = QLabel(tr("min_height_label"))
        self.reviewer_btn_height_spin = QSpinBox()
        self.reviewer_btn_height_spin.setRange(0, 200)
        self.reviewer_btn_height_spin.setSuffix(" px")
        self.reviewer_btn_height_spin.setValue(self.current_config.get("onigiri_reviewer_btn_height", 40))
        row2.addWidget(btn_height_label)
        row2.addWidget(self.reviewer_btn_height_spin)
        row2.addSpacing(20)

        bar_height_label = QLabel(tr("bar_height_label"))
        self.reviewer_bar_height_spin = QSpinBox()
        self.reviewer_bar_height_spin.setRange(0, 300)
        self.reviewer_bar_height_spin.setSuffix(" px")
        self.reviewer_bar_height_spin.setValue(self.current_config.get("onigiri_reviewer_bar_height", 60))
        row2.addWidget(bar_height_label)
        row2.addWidget(self.reviewer_bar_height_spin)
        row2.addStretch()
        general_layout.addLayout(row2)

        layout.addWidget(general_group)

        # --- Two Column Layout for Light/Dark Mode ---
        modes_container, modes_layout = self._create_responsive_row(spacing=12)

        self.preview_buttons = {"light": {}, "dark": {}}
        
        # Define button data for iteration
        # (Label, key, default_bg, default_text)
        # We'll split defaults for light/dark later
        button_defs = [
            (tr("again_label"), "again", 
             ("#ffb3b3", "#4d0000"), ("#ffcccb", "#4a0000")), # (light_bg, light_text), (dark_bg, dark_text)
            (tr("hard_label"), "hard", 
             ("#ffe0b3", "#4d2600"), ("#ffd699", "#4d1d00")),
            (tr("good_label"), "good", 
             ("#b3ffb3", "#004d00"), ("#90ee90", "#004000")),
            (tr("easy_label"), "easy", 
             ("#b3d9ff", "#00264d"), ("#add8e6", "#002952")),
            (tr("show_answer_label"), "other",
             ("#ffffff", "#2c2c2c"), ("#3a3a3a", "#e0e0e0")) # Special handling for other
        ]

        # Mode loop to create columns
        for mode_name, mode_key, bg_color in [(tr("light_mode"), "light", "#FFFFFF"), (tr("dark_mode"), "dark", "#2C2C2C")]:
            column_widget = QWidget()
            column_widget.setObjectName(f"column_{mode_key}")
            
            # Determine text color based on background
            text_col = "black" if mode_key == "light" else "white"
            sub_text_col = "#555" if mode_key == "light" else "#ccc"
            
            column_widget.setStyleSheet(f"""
                QWidget#column_{mode_key} {{
                    background-color: {bg_color}; 
                    border-radius: 24px;
                }}
                QLabel {{ color: {text_col}; }}
                QGroupBox {{ color: {text_col}; font-weight: bold; }}
                QGroupBox::title {{ color: {text_col}; }}
                QCheckBox {{ color: {text_col}; }}
                QRadioButton {{ color: {text_col}; }}
                QLineEdit {{ color: {text_col}; background-color: {'#fff' if mode_key == 'light' else '#444'}; border: 1px solid {'#ccc' if mode_key == 'light' else '#555'}; border-radius: 16px; }}
            """)
            
            col_layout = QVBoxLayout(column_widget)
            col_layout.setContentsMargins(15, 15, 15, 15)
            col_layout.setSpacing(15)
            column_widget.setMinimumWidth(0)
            column_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            # Header
            header = QLabel(mode_name)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Force style again just in case, though the parent stylesheet should handle it
            header.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {text_col};")
            col_layout.addWidget(header)

            # --- Preview Box for this mode ---
            preview_frame = QFrame()
            preview_frame.setStyleSheet(f"background-color: {bg_color}; border: 1px solid {'#444' if mode_key == 'dark' else '#ddd'}; border-radius: 16px;")
            p_layout = FlowLayout(preview_frame, margin=10, spacing=6)
            p_layout.setContentsMargins(10, 10, 10, 10)
            
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
                    tr("background_label"), 
                    self.current_config.get(bg_config_key, bg_default), 
                    bg_input_name
                )
                text_row = self._create_color_picker_row(
                    tr("text_label"), 
                    self.current_config.get(text_config_key, text_default), 
                    text_input_name
                )
                g_layout.addLayout(bg_row)
                g_layout.addLayout(text_row)
                
                # Special case: Hover for "Other" button
                if key == "other":
                    hover_label = QLabel(tr("hover_state_label"))
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
                        tr("hover_bg_label"), self.current_config.get(h_bg_key, h_bg_def), h_bg_name
                    )
                    h_txt_row = self._create_color_picker_row(
                        tr("hover_text_label"), self.current_config.get(h_txt_key, h_txt_def), h_txt_name
                    )
                    g_layout.addLayout(h_bg_row)
                    g_layout.addLayout(h_txt_row)

                settings_layout.addWidget(btn_group)
            
            # Stat Text Color (One per mode)
            stattxt_group = QGroupBox(tr("stat_text_color_group"))
            stattxt_group.setStyleSheet(f"QGroupBox::title {{ color: {'#ddd' if mode_key == 'dark' else '#333'}; }}")
            s_layout = QVBoxLayout(stattxt_group)
            if mode_key == "light":
                 stattxt_row = self._create_color_picker_row(
                    tr("color_picker_label"), self.current_config.get("onigiri_reviewer_stattxt_color_light", "#666666"), "stattxt_color_light"
                 )
            else:
                 stattxt_row = self._create_color_picker_row(
                    tr("color_picker_label"), self.current_config.get("onigiri_reviewer_stattxt_color_dark", "#aaaaaa"), "stattxt_color_dark"
                 )
            s_layout.addLayout(stattxt_row)
            settings_layout.addWidget(stattxt_group)

            settings_layout.addStretch()
            
            col_layout.addWidget(settings_content) # Directly add widget to column layout
            modes_layout.addWidget(column_widget)

        layout.addWidget(modes_container)

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
        reset_btn = QPushButton(tr("reset_answer_buttons_btn"))
        reset_btn.setStyleSheet(self._reset_button_stylesheet())
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
        if hasattr(self, "reviewer_stattxt_visible_toggle"):
            self.reviewer_stattxt_visible_toggle.setChecked(True)

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
        
        show_settings_toast(self, tr("answer_buttons_reset_toast", "Answer buttons reset to default values"))

    def create_reviewer_tab(self):
        page, layout = self._create_scrollable_page()

        # --- Reviewer Background Section ---
        reviewer_bg_section = SectionGroup("", self)
        layout.addWidget(reviewer_bg_section)
        reviewer_bg_section.content_layout.addWidget(self._create_modern_background_designer({
            "title": tr("reviewer_bg"),
            "prefix": "reviewer",
            "gallery_base": "reviewer_bg",
            "folder_rel": "user_files/reviewer_bg",
            "mode_key": "onigiri_reviewer_bg_mode",
            "default_mode": "color",
            "light_color_key": "onigiri_reviewer_bg_light_color",
            "dark_color_key": "onigiri_reviewer_bg_dark_color",
            "image_key": "onigiri_reviewer_bg_image",
            "image_light_key": "onigiri_reviewer_bg_image_light",
            "image_dark_key": "onigiri_reviewer_bg_image_dark",
            "color_theme_mode_key": "onigiri_reviewer_bg_color_theme_mode",
            "image_theme_mode_key": "onigiri_reviewer_bg_image_theme_mode",
            "legacy_image_mode_key": "onigiri_reviewer_bg_image_mode",
            "blur_key": "onigiri_reviewer_bg_blur",
            "opacity_key": "onigiri_reviewer_bg_opacity",
            "slideshow_images_key": "onigiri_reviewer_slideshow_images",
            "slideshow_interval_key": "onigiri_reviewer_slideshow_interval",
            "default_light": "#f2f2f2",
            "default_dark": "#2C2C2C",
            "storage": "config",
            "split_orientation": "vertical",
        }))

        bottom_bar_buttons_section = self.create_bottom_bar_background_and_buttons_section()
        layout.addWidget(bottom_bar_buttons_section)

        # --- RESET BUTTONS ---
        reset_buttons_layout = QHBoxLayout()
        reset_buttons_layout.addStretch()

        reset_reviewer_bg_button = QPushButton(tr("reset_reviewer_bg_default"))
        reset_reviewer_bg_button.setStyleSheet(self._reset_button_stylesheet())
        reset_reviewer_bg_button.clicked.connect(self.reset_reviewer_bg_to_default)
        reset_buttons_layout.addWidget(reset_reviewer_bg_button)

        layout.addLayout(reset_buttons_layout)
        # --- END OF RESET BUTTONS ---

        layout.addStretch()

        sections = {
            tr("reviewer_background"): reviewer_bg_section,
            tr("bottom_bar_background_and_buttons", "Bottom Bar Background and Buttons"): bottom_bar_buttons_section,
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections, buttons_per_row=2)

        return page

    def create_reviewer_bar_custom_options(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        self.reviewer_bar_color_group = QWidget()
        color_layout = QVBoxLayout(self.reviewer_bar_color_group)
        color_layout.setContentsMargins(0, 0, 0, 0)

        self.reviewer_bar_light_color_row = self._create_color_picker_row(
            tr("color_light_mode"), mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_light_color", "#EEEEEE"), "reviewer_bar_light"
        )
        self.reviewer_bar_dark_color_row = self._create_color_picker_row(
            tr("color_dark_mode"), mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_dark_color", "#3C3C3C"), "reviewer_bar_dark"
        )
        color_layout.addLayout(self.reviewer_bar_light_color_row)
        color_layout.addLayout(self.reviewer_bar_dark_color_row)
        layout.addWidget(self.reviewer_bar_color_group)

        self.galleries["reviewer_bar_bg"] = {}
        self.reviewer_bar_image_group = self._create_image_gallery_group(
            "reviewer_bar_bg",
            "user_files/reviewer_bar_bg",
            "onigiri_reviewer_bottom_bar_bg_image",
            is_sub_group=True,
            actions_in_parent_header=True
        )
        layout.addWidget(self.reviewer_bar_image_group)

        effects_container = QWidget()
        effects_layout = FlowLayout(effects_container, margin=0, spacing=10)
        effects_layout.setContentsMargins(0, 10, 0, 0)
        self.reviewer_bar_blur_label = QLabel(tr("blur_label"))
        self.reviewer_bar_blur_spinbox = QSpinBox()
        self.reviewer_bar_blur_spinbox.setMinimum(0); self.reviewer_bar_blur_spinbox.setMaximum(100)
        self.reviewer_bar_blur_spinbox.setSuffix(" %")
        self.reviewer_bar_blur_spinbox.setValue(mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_blur", 0))

        self.reviewer_bar_opacity_label = QLabel(tr("opacity_label"))
        self.reviewer_bar_opacity_spinbox = QSpinBox()
        self.reviewer_bar_opacity_spinbox.setMinimum(0); self.reviewer_bar_opacity_spinbox.setMaximum(100)
        self.reviewer_bar_opacity_spinbox.setSuffix(" %")
        self.reviewer_bar_opacity_spinbox.setValue(mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_opacity", 100))

        effects_layout.addWidget(self.reviewer_bar_blur_label)
        effects_layout.addWidget(self.reviewer_bar_blur_spinbox)
        effects_layout.addWidget(self.reviewer_bar_opacity_label)
        effects_layout.addWidget(self.reviewer_bar_opacity_spinbox)
        layout.addWidget(effects_container)

        if 'reviewer_bar_bg' in self.galleries:
            self.galleries['reviewer_bar_bg']['effects_widget'] = effects_container

        return widget

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
            tr("background_color"), conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF"), "reviewer_bg_single"
        )
        single_color_layout.addLayout(self.reviewer_bg_single_color_row)
        
        # Separate colors container
        self.reviewer_bg_separate_colors_container = QWidget()
        separate_colors_layout = QVBoxLayout(self.reviewer_bg_separate_colors_container)
        self.reviewer_bg_light_color_row = self._create_color_picker_row(
            tr("background_light_mode"), conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF"), "reviewer_bg_light"
        )
        self.reviewer_bg_dark_color_row = self._create_color_picker_row(
            tr("background_dark_mode"), conf.get("onigiri_reviewer_bg_dark_color", "#2C2C2C"), "reviewer_bg_dark"
        )
        separate_colors_layout.addLayout(self.reviewer_bg_light_color_row)
        separate_colors_layout.addLayout(self.reviewer_bg_dark_color_row)
        
        # Add both containers to the layout
        color_layout.addWidget(self.reviewer_bg_single_color_container)
        color_layout.addWidget(self.reviewer_bg_separate_colors_container)
        
        # Add theme mode toggle for color selection
        self.reviewer_bg_color_theme_mode_group = QButtonGroup()
        self.reviewer_bg_color_theme_mode_single = QRadioButton(tr("use_same_color_both_themes"))
        self.reviewer_bg_color_theme_mode_separate = QRadioButton(tr("use_separate_colors"))
        self.reviewer_bg_color_theme_mode_group.addButton(self.reviewer_bg_color_theme_mode_single)
        self.reviewer_bg_color_theme_mode_group.addButton(self.reviewer_bg_color_theme_mode_separate)
        
        # Load saved theme mode or default to single
        reviewer_bg_color_theme_mode = mw.col.conf.get("onigiri_reviewer_bg_color_theme_mode", "separate")
        self.reviewer_bg_color_theme_mode_single.setChecked(reviewer_bg_color_theme_mode == "single")
        self.reviewer_bg_color_theme_mode_separate.setChecked(reviewer_bg_color_theme_mode == "separate")
        
        color_theme_mode_container, color_theme_mode_layout = self._create_responsive_row(spacing=10)
        color_theme_mode_layout.addWidget(self.reviewer_bg_color_theme_mode_single)
        color_theme_mode_layout.addWidget(self.reviewer_bg_color_theme_mode_separate)
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
        self.reviewer_bg_image_theme_mode_single = QRadioButton(tr("use_same_image_both_themes"))
        self.reviewer_bg_image_theme_mode_separate = QRadioButton(tr("use_separate_images"))
        self.reviewer_bg_image_theme_mode_group.addButton(self.reviewer_bg_image_theme_mode_single)
        self.reviewer_bg_image_theme_mode_group.addButton(self.reviewer_bg_image_theme_mode_separate)
        
        # Load saved theme mode or default to single
        reviewer_bg_image_theme_mode = mw.col.conf.get("onigiri_reviewer_bg_image_theme_mode", "separate")
        self.reviewer_bg_image_theme_mode_single.setChecked(reviewer_bg_image_theme_mode == "single")
        self.reviewer_bg_image_theme_mode_separate.setChecked(reviewer_bg_image_theme_mode == "separate")
        
        image_theme_mode_container, image_theme_mode_layout = self._create_responsive_row(spacing=10)
        image_theme_mode_layout.addWidget(self.reviewer_bg_image_theme_mode_single)
        image_theme_mode_layout.addWidget(self.reviewer_bg_image_theme_mode_separate)
        image_theme_mode_container.setContentsMargins(15, 5, 0, 5)
        image_layout.addWidget(image_theme_mode_container)
        
        # Single image container
        self.reviewer_bg_single_image_container = QWidget()
        single_image_layout = QVBoxLayout(self.reviewer_bg_single_image_container)
        single_image_layout.setContentsMargins(0, 10, 0, 0)
        self.galleries["reviewer_bg_single"] = {}
        single_image_layout.addWidget(self._create_image_gallery_group(
            "reviewer_bg_single", "user_files/reviewer_bg", "onigiri_reviewer_bg_image", 
            title=tr("background_image"), is_sub_group=True
        ))
        
        # Separate images container
        self.galleries["reviewer_bg_light"] = {}
        reviewer_light_panel, reviewer_light_layout = self._create_theme_mode_panel(tr("background_light_mode"), "light")
        reviewer_light_layout.addWidget(self._create_image_gallery_group(
            "reviewer_bg_light", "user_files/reviewer_bg", "onigiri_reviewer_bg_image_light", 
            is_sub_group=True
        ))
        self.galleries["reviewer_bg_dark"] = {}
        reviewer_dark_panel, reviewer_dark_layout = self._create_theme_mode_panel(tr("background_dark_mode"), "dark")
        reviewer_dark_layout.addWidget(self._create_image_gallery_group(
            "reviewer_bg_dark", "user_files/reviewer_bg", "onigiri_reviewer_bg_image_dark", 
            is_sub_group=True
        ))
        self.reviewer_bg_separate_images_container = ResponsivePairWidget(reviewer_light_panel, reviewer_dark_panel)
        
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
        effects_layout = FlowLayout(self.reviewer_bg_effects_container, margin=0, spacing=10)
        effects_layout.setContentsMargins(0, 10, 0, 0)
        
        self.reviewer_bg_blur_label = QLabel(tr("blur_label"))
        self.reviewer_bg_blur_spinbox = QSpinBox()
        self.reviewer_bg_blur_spinbox.setMinimum(0)
        self.reviewer_bg_blur_spinbox.setMaximum(100)
        self.reviewer_bg_blur_spinbox.setSuffix(" %")
        self.reviewer_bg_blur_spinbox.setValue(conf.get("onigiri_reviewer_bg_blur", 0))
        
        self.reviewer_bg_opacity_label = QLabel(tr("opacity_label"))
        self.reviewer_bg_opacity_spinbox = QSpinBox()
        self.reviewer_bg_opacity_spinbox.setMinimum(0)
        self.reviewer_bg_opacity_spinbox.setMaximum(100)
        self.reviewer_bg_opacity_spinbox.setSuffix(" %")
        self.reviewer_bg_opacity_spinbox.setValue(conf.get("onigiri_reviewer_bg_opacity", 100))
        
        effects_layout.addWidget(self.reviewer_bg_blur_label)
        effects_layout.addWidget(self.reviewer_bg_blur_spinbox)
        effects_layout.addWidget(self.reviewer_bg_opacity_label)
        effects_layout.addWidget(self.reviewer_bg_opacity_spinbox)
        layout.addWidget(self.reviewer_bg_effects_container)
        
        # Initially hide image options (only show for Image mode)
        self.reviewer_bg_image_group.setVisible(False)
        
        return widget

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

    def reset_reviewer_bg_to_default(self):
        """Reset reviewer background settings to defaults."""
        if hasattr(self, "reviewer_bg_color_only_toggle") and self._modern_background_spec("reviewer"):
            self._reset_modern_background_to_default("reviewer")
            return

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
        
        show_settings_toast(self, tr("reviewer_bg_reset_toast", "Reviewer background reset — press Save to apply"))

    def reset_reviewer_bottom_bar_to_default(self):
        """Reset reviewer bottom bar background settings to defaults."""
        self.reviewer_bottom_bar_mode = "match_reviewer_bg"
        if hasattr(self, "reviewer_bar_match_reviewer_toggle"):
            for toggle, checked in (
                (self.reviewer_bar_match_main_toggle, False),
                (self.reviewer_bar_match_overview_toggle, False),
                (self.reviewer_bar_match_reviewer_toggle, True),
                (self.reviewer_bar_color_only_toggle, False),
            ):
                with QSignalBlocker(toggle):
                    toggle.setChecked(checked)
        elif hasattr(self, "reviewer_bar_match_reviewer_bg_radio"):
            self.reviewer_bar_match_reviewer_bg_radio.setChecked(True)
        
        # Reset match main settings
        self.reviewer_bar_match_main_blur_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_match_main_blur"])
        self.reviewer_bar_match_main_opacity_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_match_main_opacity"])

        # Reset match reviewer bg settings
        self.reviewer_bar_match_reviewer_bg_blur_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_match_reviewer_bg_blur"])
        self.reviewer_bar_match_reviewer_bg_opacity_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity"])
        if hasattr(self, "reviewer_bar_match_overview_bg_blur_spinbox"):
            self.reviewer_bar_match_overview_bg_blur_spinbox.setValue(DEFAULTS.get("onigiri_reviewer_bottom_bar_match_overview_bg_blur", 0))
            self.reviewer_bar_match_overview_bg_opacity_spinbox.setValue(DEFAULTS.get("onigiri_reviewer_bottom_bar_match_overview_bg_opacity", 100))
        
        # Reset custom colors
        self.reviewer_bar_light_color_input.setText(DEFAULTS["onigiri_reviewer_bottom_bar_bg_light_color"])
        self.reviewer_bar_dark_color_input.setText(DEFAULTS["onigiri_reviewer_bottom_bar_bg_dark_color"])
        if hasattr(self, "reviewer_stattxt_visible_toggle"):
            self.reviewer_stattxt_visible_toggle.setChecked(DEFAULTS.get("onigiri_reviewer_stattxt_visible", True))
        
        # Clear bottom bar image
        if 'reviewer_bar_bg' in self.galleries:
            self.galleries['reviewer_bar_bg']['selected'] = ""
            if self.galleries['reviewer_bar_bg'].get('path_input'):
                self.galleries['reviewer_bar_bg']['path_input'].setText("")
            if self.galleries['reviewer_bar_bg'].get('grid_layout'):
                self._refresh_gallery('reviewer_bar_bg')
        
        # Reset blur and opacity
        self.reviewer_bar_blur_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_bg_blur"])
        self.reviewer_bar_opacity_spinbox.setValue(DEFAULTS["onigiri_reviewer_bottom_bar_bg_opacity"])
        if hasattr(self, "_sync_reviewer_bottom_bar_controls"):
            self._sync_reviewer_bottom_bar_controls()
        
        show_settings_toast(self, tr("bottom_bar_reset_toast", "Bottom bar reset — press Save to apply"))

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
            actions_widget = getattr(self.reviewer_bar_image_group, "gallery_actions_widget", None)
            if actions_widget:
                actions_widget.setVisible(image_options_visible)

            if 'reviewer_bar_bg' in self.galleries and self.galleries['reviewer_bar_bg'].get('effects_widget'):
                self.galleries['reviewer_bar_bg']['effects_widget'].setVisible(image_options_visible)
        elif hasattr(self, "reviewer_bar_image_group"):
            actions_widget = getattr(self.reviewer_bar_image_group, "gallery_actions_widget", None)
            if actions_widget:
                actions_widget.setVisible(False)

    def _reset_loaded_reviewer_button_widgets_to_default(self):
        if not hasattr(self, "reviewer_btn_custom_enable_toggle"):
            return

        self.reviewer_btn_custom_enable_toggle.setChecked(DEFAULTS.get("onigiri_reviewer_btn_custom_enabled", True))
        self.reviewer_btn_radius_spin.setValue(DEFAULTS.get("onigiri_reviewer_btn_radius", 12))
        self.reviewer_btn_padding_spin.setValue(DEFAULTS.get("onigiri_reviewer_btn_padding", 5))
        self.reviewer_btn_height_spin.setValue(DEFAULTS.get("onigiri_reviewer_btn_height", 40))
        self.reviewer_bar_height_spin.setValue(DEFAULTS.get("onigiri_reviewer_bar_height", 60))
        if hasattr(self, "reviewer_stattxt_visible_toggle"):
            self.reviewer_stattxt_visible_toggle.setChecked(DEFAULTS.get("onigiri_reviewer_stattxt_visible", True))

        def set_color(name, value):
            widget = getattr(self, f"{name}_color_input", None)
            if widget:
                widget.setText(value)
            button = getattr(self, f"{name}_circular_button", None)
            if button:
                button.setColor(value)

        reviewer_color_defaults = {
            "stattxt_color_light": "onigiri_reviewer_stattxt_color_light",
            "stattxt_color_dark": "onigiri_reviewer_stattxt_color_dark",
            "other_btn_bg_light": "onigiri_reviewer_other_btn_bg_light",
            "other_btn_text_light": "onigiri_reviewer_other_btn_text_light",
            "other_btn_bg_dark": "onigiri_reviewer_other_btn_bg_dark",
            "other_btn_text_dark": "onigiri_reviewer_other_btn_text_dark",
            "other_btn_hover_bg_light": "onigiri_reviewer_other_btn_hover_bg_light",
            "other_btn_hover_text_light": "onigiri_reviewer_other_btn_hover_text_light",
            "other_btn_hover_bg_dark": "onigiri_reviewer_other_btn_hover_bg_dark",
            "other_btn_hover_text_dark": "onigiri_reviewer_other_btn_hover_text_dark",
        }
        for widget_prefix, config_key in reviewer_color_defaults.items():
            set_color(widget_prefix, DEFAULTS.get(config_key, self.current_config.get(config_key, "")))

        for key in ["again", "hard", "good", "easy"]:
            for part in ["bg", "text"]:
                for mode in ["light", "dark"]:
                    config_key = f"onigiri_reviewer_btn_{key}_{part}_{mode}"
                    set_color(f"btn_{key}_{part}_{mode}", DEFAULTS.get(config_key, self.current_config.get(config_key, "")))



# --- MERGED FROM _page_reviewer_2.py ---

class PageReviewerMixin2:
    def _save_reviewer_settings(self):
        # Save Answer Buttons Settings
        self.current_config["onigiri_reviewer_btn_custom_enabled"] = self.reviewer_btn_custom_enable_toggle.isChecked()
        self.current_config["onigiri_reviewer_btn_radius"] = self.reviewer_btn_radius_spin.value()
        self.current_config["onigiri_reviewer_btn_padding"] = self.reviewer_btn_padding_spin.value()
        self.current_config["onigiri_reviewer_btn_height"] = self.reviewer_btn_height_spin.value()
        self.current_config["onigiri_reviewer_bar_height"] = self.reviewer_bar_height_spin.value()
        if hasattr(self, "reviewer_stattxt_visible_toggle"):
            self.current_config["onigiri_reviewer_stattxt_visible"] = self.reviewer_stattxt_visible_toggle.isChecked()
        self.current_config["onigiri_reviewer_stattxt_color_light"] = getattr(self, "stattxt_color_light_color_input").text()
        self.current_config["onigiri_reviewer_stattxt_color_dark"] = getattr(self, "stattxt_color_dark_color_input").text()

        if hasattr(self, "pre_count_new_bg_light_color_input") and getattr(self, "_bottom_bar_pre_count_colors_dirty", False):
            overview_style = self.current_config.setdefault("overview_style", {})
            if not isinstance(overview_style, dict):
                overview_style = {}
                self.current_config["overview_style"] = overview_style
            overview_colors = overview_style.setdefault("colors", {})
            if not isinstance(overview_colors, dict):
                overview_colors = {}
                overview_style["colors"] = overview_colors
            key_map = {
                "new": ("new_bubble", "new_text"),
                "learn": ("learn_bubble", "learn_text"),
                "review": ("review_bubble", "review_text"),
            }
            for mode in ("light", "dark"):
                mode_colors = overview_colors.setdefault(mode, {})
                for kind, (bg_key, text_key) in key_map.items():
                    mode_colors[bg_key] = getattr(self, f"pre_count_{kind}_bg_{mode}_color_input").text()
                    mode_colors[text_key] = getattr(self, f"pre_count_{kind}_text_{mode}_color_input").text()
        
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
        if hasattr(self, "reviewer_bg_color_only_toggle"):
            self._save_modern_background_designer_settings("reviewer")
            self.current_config["onigiri_reviewer_bg_main_blur"] = self.current_config.get("onigiri_reviewer_bg_blur", 0)
            self.current_config["onigiri_reviewer_bg_main_opacity"] = self.current_config.get("onigiri_reviewer_bg_opacity", 100)
        else:
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
        if hasattr(self, "reviewer_bar_match_overview_bg_blur_spinbox"):
            self.current_config["onigiri_reviewer_bottom_bar_match_overview_bg_blur"] = self.reviewer_bar_match_overview_bg_blur_spinbox.value()
            self.current_config["onigiri_reviewer_bottom_bar_match_overview_bg_opacity"] = self.reviewer_bar_match_overview_bg_opacity_spinbox.value()
        reviewer_bar_light_color = self.reviewer_bar_light_color_input.text()
        reviewer_bar_dark_color = self.reviewer_bar_dark_color_input.text()
        if hasattr(self, "reviewer_bar_dynamic_toggle") and not self.reviewer_bar_dynamic_toggle.isChecked():
            reviewer_bar_dark_color = reviewer_bar_light_color
        self.current_config["onigiri_reviewer_bottom_bar_bg_light_color"] = reviewer_bar_light_color
        self.current_config["onigiri_reviewer_bottom_bar_bg_dark_color"] = reviewer_bar_dark_color
        self.current_config["onigiri_reviewer_bottom_bar_bg_blur"] = self.reviewer_bar_blur_spinbox.value()
        self.current_config["onigiri_reviewer_bottom_bar_bg_opacity"] = self.reviewer_bar_opacity_spinbox.value()
        if 'reviewer_bar_bg' in self.galleries:
            self.current_config["onigiri_reviewer_bottom_bar_bg_image"] = self.galleries['reviewer_bar_bg']['selected']
