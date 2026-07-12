# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._icon_picker import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *



class PageSidebarMixin:
    def _set_sidebar_section_toggle_icon(self, button, expanded):
        icon_filename = "down.svg" if expanded else "right.svg"
        button.setIcon(self._themed_icon(icon_filename, self._settings_icon_color(), 12))
        button.setIconSize(QSize(12, 12))
        button.setProperty("onigiri_icon_filename", icon_filename)
        button.setProperty("onigiri_icon_size", 12)

    def _create_sidebar_section_toggle(self, title, content_widget):
        button = QPushButton(title.upper())
        button.setObjectName("sidebarSectionToggle")
        button.setCheckable(True)
        button.setChecked(True)
        button.setFixedHeight(24)
        button.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._set_sidebar_section_toggle_icon(button, True)
        button.clicked.connect(
            lambda checked, section=content_widget, toggle=button: self._toggle_sidebar_nav_section(toggle, section, checked)
        )
        return button

    def _toggle_sidebar_nav_section(self, toggle_button, content_widget, expanded):
        content_widget.setVisible(expanded)
        self._set_sidebar_section_toggle_icon(toggle_button, expanded)

    def _add_sidebar_nav_section(self, layout, title, items):
        section_content = QWidget()
        section_content.setObjectName("sidebarSectionContent")
        section_layout = QVBoxLayout(section_content)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        layout.addWidget(self._create_sidebar_section_toggle(title, section_content))
        for label, page_name, icon_filename in items:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setObjectName("sidebarNavButton")
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setFixedHeight(36)
            button.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
            self._decorate_button(button, icon_filename, 16)
            button.clicked.connect(lambda _, page=page_name: self.navigate_to_page(page))
            button.toggled.connect(lambda checked, page=page_name: self.navigate_to_page(page) if checked else None)
            self.sidebar_buttons[page_name] = button
            self.sidebar_button_group.addButton(button)
            section_layout.addWidget(button)
        layout.addWidget(section_content)

    def _marker_definitions(self):
        return [("red", "#FF4B4B"), ("blue", "#4488FF"), ("green", "#44BB66"), ("yellow", "#FFB800")]

    def _marker_icon_value(self, key):
        icons = self.current_config.get("markerIcons", {}) or {}
        return icons.get(key, "default")

    def _set_marker_icon_value(self, key, value):
        self.current_config.setdefault("markerIcons", {})[key] = value or "default"

    def _marker_current_color(self, key):
        line_edit = getattr(self, f"marker_{key}_color_input", None)
        if line_edit is not None and QColor(line_edit.text()).isValid():
            return line_edit.text()
        colors = self.current_config.get("markerColors", {}) or {}
        fallback = dict(self._marker_definitions()).get(key, "#888888")
        return colors.get(key, fallback)

    def _create_sidebar_markers_widget(self):
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 6, 0, 0)
        vbox.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel(tr("markers", "Markers"))
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()
        reset_button = QPushButton(tr("reset_to_default", "Reset to Default"))
        reset_button.setObjectName("mainBackgroundResetButton")
        reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_button.setFixedHeight(30)
        reset_button.clicked.connect(self._reset_markers_to_default)
        header.addWidget(reset_button)
        vbox.addLayout(header)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        for index, (key, fallback) in enumerate(self._marker_definitions()):
            grid.addWidget(self._create_marker_card(key, fallback), index // 2, index % 2)
        vbox.addLayout(grid)
        return container

    def _create_marker_card(self, key, fallback):
        control_widget = QWidget()
        control_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        
        if theme_manager.night_mode:
            bg_color = "rgba(255, 255, 255, 0.05)"
            border_color = "rgba(255, 255, 255, 0.1)"
            hover_color = "rgba(255, 255, 255, 0.1)"
            text_color = "#e0e0e0"
        else:
            bg_color = "rgba(0, 0, 0, 0.03)"
            border_color = "rgba(0, 0, 0, 0.1)"
            hover_color = "rgba(0, 0, 0, 0.06)"
            text_color = "#212121"

        control_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 18px;
            }}
            QWidget:hover {{
                background-color: {hover_color};
                border-color: {text_color};
            }}
        """)
        
        layout = QHBoxLayout(control_widget)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        
        preview_label = QLabel()
        preview_label.setFixedSize(32, 32)
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setStyleSheet("background: transparent; border: none;")
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        custom_name = self.current_config.get("markerNames", {}).get(key, "")
        display_name = custom_name if custom_name else tr(f"marker_{key}", key.title())
        
        name_input = QLineEdit(display_name)
        name_input.setPlaceholderText(tr(f"marker_{key}", key.title()))
        name_input.setStyleSheet(f"background: transparent; border: none; font-weight: bold; color: {text_color}; font-size: 13px; padding: 0;")
        
        def save_name(text, k=key):
            names = self.current_config.get("markerNames", {})
            names[k] = text
            self.current_config["markerNames"] = names
            
        name_input.textChanged.connect(save_name)
        
        sub_label = QLabel(tr("click_to_change"))
        sub_label.setStyleSheet(f"background: transparent; border: none; color: {text_color}; opacity: 0.7; font-size: 10px;")
        text_layout.addWidget(name_input)
        text_layout.addWidget(sub_label)
        text_layout.addStretch()

        delete_btn = QPushButton()
        delete_btn.setFixedSize(24, 24)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setToolTip(tr("reset_to_default_tooltip"))
        
        trash_icon_path = system_icon_path("cancel.svg")
        if theme_manager.night_mode:
             delete_btn.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 12px; } QPushButton:hover { background: rgba(255,0,0,0.2); }")
             trash_color = "#ff6b6b"
        else:
             delete_btn.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 12px; } QPushButton:hover { background: rgba(255,0,0,0.1); }")
             trash_color = "#d32f2f"

        if os.path.exists(trash_icon_path):
            pixmap = QPixmap(trash_icon_path)
            if not pixmap.isNull():
                painter = QPainter(pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor(trash_color))
                painter.end()
                delete_btn.setIcon(QIcon(pixmap))
            else:
                delete_btn.setText("✖")
                delete_btn.setStyleSheet(delete_btn.styleSheet() + f"color: {trash_color}; font-weight: bold;")
        else:
            delete_btn.setText("✖")
            delete_btn.setStyleSheet(delete_btn.styleSheet() + f"color: {trash_color}; font-weight: bold;")

        color_value = (self.current_config.get("markerColors", {}) or {}).get(key, fallback)
        hex_input = QLineEdit(color_value)
        hex_input.setVisible(False)
        setattr(self, f"marker_{key}_color_input", hex_input)
        hex_input.textChanged.connect(lambda txt, k=key: self._on_marker_color_text_changed(k, txt))

        def reset_to_default():
            self._set_marker_icon_value(key, "default")
            hex_input.setText(fallback)
            self._refresh_marker_icon_button(key)
        delete_btn.clicked.connect(reset_to_default)

        layout.addWidget(preview_label)
        layout.addLayout(text_layout)
        layout.addStretch()
        layout.addWidget(delete_btn)

        setattr(self, f"marker_{key}_preview_label", preview_label)
        
        def on_click(event):
            if event.button() == Qt.MouseButton.LeftButton:
                self._open_marker_icon_picker(key)
        control_widget.mousePressEvent = on_click

        self._refresh_marker_icon_button(key)
        return control_widget

    def _on_marker_color_text_changed(self, key, text):
        self._refresh_marker_icon_button(key)

    def _refresh_marker_icon_button(self, key):
        label = getattr(self, f"marker_{key}_preview_label", None)
        if label is None:
            return
        color = self._marker_current_color(key)
        icon_value = self._marker_icon_value(key)
        size = 26
        if icon_value and icon_value != "default":
            pixmap = self._render_icon_value_pixmap(icon_value, color, size)
        else:
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(2, 2, size - 4, size - 4))
            painter.end()
        label.setPixmap(pixmap)

    def _open_marker_icon_picker(self, key):
        current = self._marker_icon_value(key)
        if current == "default":
            current = ""
            
        color_opts = [
            {
                "key": "light", "config_key": None,
                "label": tr(f"marker_{key}", key.title()),
                "value": self._marker_current_color(key)
            }
        ]
            
        picker = DeckIconPickerDialog(current, self.addon_path, self, allow_emoji=True, color_options=color_opts)

        def on_selected(value):
            self._set_marker_icon_value(key, value or "default")
            self._refresh_marker_icon_button(key)

        def on_colors_changed(values):
            if "light" in values:
                hex_input = getattr(self, f"marker_{key}_color_input", None)
                if hex_input:
                    hex_input.setText(values["light"])

        picker.iconSelected.connect(on_selected)
        picker.colorsChanged.connect(on_colors_changed)
        picker.exec()

    def _reset_markers_to_default(self):
        defaults = DEFAULTS.get("markerColors", {})
        self.current_config["markerIcons"] = {}
        for key, fallback in self._marker_definitions():
            line_edit = getattr(self, f"marker_{key}_color_input", None)
            if line_edit is not None:
                line_edit.setText(defaults.get(key, fallback))
            self._refresh_marker_icon_button(key)
        show_settings_toast(self, tr("markers_reset_toast", "Markers reset to default"))

    def _box_effect_state_for_sidebar_preview(self, mode):
        light_input = getattr(self, "box_effect_light_color_input", None)
        dark_input = getattr(self, "box_effect_dark_color_input", None)
        color = None
        if mode == "dark" and dark_input is not None:
            color = dark_input.text()
        elif light_input is not None:
            color = light_input.text()
        if not color or not QColor(color).isValid():
            colors = self.current_config.get("colors", {})
            fallback_mode = "dark" if mode == "dark" else "light"
            color = colors.get(fallback_mode, {}).get(
                "--canvas-inset", DEFAULTS["colors"][fallback_mode]["--canvas-inset"]
            )
        blur_slider = getattr(self, "box_effect_blur_slider", None)
        opacity_slider = getattr(self, "box_effect_opacity_slider", None)
        blur = blur_slider.value() if blur_slider else mw.col.conf.get("onigiri_canvas_inset_effect_blur", 0)
        opacity = opacity_slider.value() if opacity_slider else mw.col.conf.get("onigiri_canvas_inset_effect_opacity", 100)
        return {"color": color, "image_path": "", "blur": blur, "opacity": opacity}

    def _on_sidebar_frame_effect_changed(self, prefix):
        for attr in ("radius", "stroke", "margin"):
            label = getattr(self, f"{prefix}_bg_{attr}_value_label", None)
            slider = getattr(self, f"{prefix}_bg_{attr}_slider", None)
            if label and slider:
                label.setText(f"{slider.value()}px")
        self._update_modern_background_preview(prefix)

    def _sidebar_bg_folder_path(self):
        path = os.path.join(self.addon_path, "user_files", "sidebar_bg")
        os.makedirs(path, exist_ok=True)
        return path

    def _sidebar_bg_image_files(self):
        try:
            return sorted([
                f for f in os.listdir(self._sidebar_bg_folder_path())
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
            ])
        except OSError:
            return []

    def _sidebar_bg_image_path(self, filename):
        return os.path.join(self._sidebar_bg_folder_path(), filename) if filename else ""

    def _sanitize_sidebar_background_slideshow_images(self, filenames=None):
        available = set(self._sidebar_bg_image_files())
        cleaned = []
        for filename in filenames or []:
            if filename in available and filename not in cleaned:
                cleaned.append(filename)
        return cleaned

    def _create_sidebar_background_designer(self):
        return self._create_modern_background_designer({
            "title": tr("sidebar_customization"),
            "prefix": "sidebar",
            "gallery_base": "sidebar",
            "folder_rel": "user_files/sidebar_bg",
            "mode_key": "modern_menu_sidebar_bg_type",
            "default_mode": "color",
            "light_color_key": "modern_menu_sidebar_bg_color_light",
            "dark_color_key": "modern_menu_sidebar_bg_color_dark",
            "image_key": "modern_menu_sidebar_bg_image",
            "image_light_key": "modern_menu_sidebar_bg_image_light",
            "image_dark_key": "modern_menu_sidebar_bg_image_dark",
            "color_theme_mode_key": "modern_menu_sidebar_bg_color_theme_mode",
            "image_theme_mode_key": "modern_menu_sidebar_bg_image_theme_mode",
            "blur_key": "modern_menu_sidebar_bg_blur",
            "opacity_key": "modern_menu_sidebar_bg_opacity",
            "slideshow_images_key": "modern_menu_sidebar_slideshow_images",
            "slideshow_interval_key": "modern_menu_sidebar_slideshow_interval",
            "default_light": "#F3F3F3",
            "default_dark": "#2C2C2C",
            "storage": "col",
            "preview_shape": "sidebar",
            "split_orientation": "horizontal",
        })
        mode = mw.col.conf.get("modern_menu_sidebar_bg_type", "color")
        if mode == "image":
            mode = "image_color"

        light_color = mw.col.conf.get("modern_menu_sidebar_bg_color_light", "#F3F3F3")
        dark_color = mw.col.conf.get("modern_menu_sidebar_bg_color_dark", "#2C2C2C")
        color_theme_mode = mw.col.conf.get("modern_menu_sidebar_bg_color_theme_mode", "separate")
        image_theme_mode = mw.col.conf.get("modern_menu_sidebar_bg_image_theme_mode", "separate")
        single_image = mw.col.conf.get("modern_menu_sidebar_bg_image", "")

        self.galleries["sidebar_single"] = {"selected": single_image, "folder": "user_files/sidebar_bg"}
        self.galleries["sidebar_light"] = {"selected": mw.col.conf.get("modern_menu_sidebar_bg_image_light", single_image), "folder": "user_files/sidebar_bg"}
        self.galleries["sidebar_dark"] = {"selected": mw.col.conf.get("modern_menu_sidebar_bg_image_dark", single_image), "folder": "user_files/sidebar_bg"}
        self.sidebar_bg_slideshow_images = self._sanitize_sidebar_background_slideshow_images(
            list(mw.col.conf.get("modern_menu_sidebar_slideshow_images", []) or [])
        )
        self.sidebar_bg_slideshow_index = 0
        self.sidebar_bg_slideshow_preview_timer = QTimer(self)
        self.sidebar_bg_slideshow_preview_timer.timeout.connect(self._advance_sidebar_background_slideshow_preview)

        self.sidebar_bg_designer = QFrame()
        self.sidebar_bg_designer.setObjectName("mainBackgroundDesigner")
        outer = QHBoxLayout(self.sidebar_bg_designer)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(24)

        self.sidebar_bg_preview = QLabel()
        self.sidebar_bg_preview.setObjectName("mainBackgroundPreview")
        self.sidebar_bg_preview.setMinimumSize(300, 520)
        self.sidebar_bg_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_bg_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.sidebar_bg_preview.installEventFilter(self)
        self.sidebar_bg_preview_fade_label = QLabel(self.sidebar_bg_preview)
        self.sidebar_bg_preview_fade_label.setObjectName("mainBackgroundPreviewFade")
        self.sidebar_bg_preview_fade_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_bg_preview_fade_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.sidebar_bg_preview_fade_label.setStyleSheet("background: transparent; border: none;")
        self.sidebar_bg_preview_fade_label.hide()
        self.sidebar_bg_preview_fade_effect = QGraphicsOpacityEffect(self.sidebar_bg_preview_fade_label)
        self.sidebar_bg_preview_fade_effect.setOpacity(0.0)
        self.sidebar_bg_preview_fade_label.setGraphicsEffect(self.sidebar_bg_preview_fade_effect)
        self.sidebar_bg_preview_fade_animation = QPropertyAnimation(self.sidebar_bg_preview_fade_effect, b"opacity", self)
        self.sidebar_bg_preview_fade_animation.setDuration(1200)
        self.sidebar_bg_preview_fade_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.sidebar_bg_preview_fade_animation.finished.connect(self._finalize_sidebar_background_preview_fade)
        self._pending_sidebar_bg_preview_pixmap = None
        self._pending_sidebar_bg_preview_text = ""

        controls = QWidget()
        controls.setMinimumWidth(0)
        controls.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(18)

        button_grid = QGridLayout()
        button_grid.setContentsMargins(0, 0, 0, 0)
        button_grid.setHorizontalSpacing(12)
        button_grid.setVerticalSpacing(18)

        self.sidebar_bg_import_button = self._create_main_bg_button("Import")
        self.sidebar_bg_clear_button = self._create_main_bg_button("Clear image")
        self.sidebar_bg_gallery_button = self._create_main_bg_button("Select from your Gallery")
        self.sidebar_bg_color_button = self._create_main_bg_button("Color")
        self.sidebar_bg_color_value_button = self._create_main_bg_button("")
        self.sidebar_bg_color_value_button.setObjectName("mainBackgroundColorButton")
        button_grid.addWidget(self.sidebar_bg_import_button, 0, 0)
        button_grid.addWidget(self.sidebar_bg_clear_button, 0, 1)
        button_grid.addWidget(self.sidebar_bg_gallery_button, 1, 0, 1, 2)
        button_grid.addWidget(self.sidebar_bg_color_button, 2, 0)
        button_grid.addWidget(self.sidebar_bg_color_value_button, 2, 1)
        controls_layout.addLayout(button_grid)

        slider_palette = self._settings_palette()
        slider_track = slider_palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = slider_palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")

        self.sidebar_bg_blur_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.sidebar_bg_blur_slider.setRange(0, 100)
        self.sidebar_bg_blur_slider.setValue(mw.col.conf.get("modern_menu_sidebar_bg_blur", 0))
        self.sidebar_bg_blur_value_label = QLabel(f"{self.sidebar_bg_blur_slider.value()}%")
        self.sidebar_bg_blur_value_label.setObjectName("mainBackgroundValueLabel")
        self.sidebar_bg_blur_value_label.setFixedWidth(48)
        blur_value = QWidget()
        blur_layout = QHBoxLayout(blur_value)
        blur_layout.setContentsMargins(0, 0, 0, 0)
        blur_layout.setSpacing(10)
        blur_layout.addWidget(self.sidebar_bg_blur_slider, 1)
        blur_layout.addWidget(self.sidebar_bg_blur_value_label)

        self.sidebar_bg_opacity_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.sidebar_bg_opacity_slider.setRange(0, 100)
        self.sidebar_bg_opacity_slider.setValue(mw.col.conf.get("modern_menu_sidebar_bg_opacity", 100))
        self.sidebar_bg_opacity_value_label = QLabel(f"{self.sidebar_bg_opacity_slider.value()}%")
        self.sidebar_bg_opacity_value_label.setObjectName("mainBackgroundValueLabel")
        self.sidebar_bg_opacity_value_label.setFixedWidth(48)
        opacity_value = QWidget()
        opacity_layout = QHBoxLayout(opacity_value)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(10)
        opacity_layout.addWidget(self.sidebar_bg_opacity_slider, 1)
        opacity_layout.addWidget(self.sidebar_bg_opacity_value_label)

        self.sidebar_bg_dynamic_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.sidebar_bg_slideshow_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.sidebar_bg_color_only_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.sidebar_bg_dynamic_toggle.setChecked(color_theme_mode == "separate" or image_theme_mode == "separate")
        self.sidebar_bg_slideshow_toggle.setChecked(mode == "slideshow")
        self.sidebar_bg_color_only_toggle.setChecked(mode in {"color", "accent"})

        controls_layout.addWidget(self._create_main_bg_value_row("Blur Intensity", blur_value))
        controls_layout.addWidget(self._create_main_bg_value_row("Opacity", opacity_value))
        controls_layout.addWidget(self._create_main_bg_toggle_row("Dynamic mode", self.sidebar_bg_dynamic_toggle))
        controls_layout.addWidget(self._create_main_bg_toggle_row("Slideshow", self.sidebar_bg_slideshow_toggle))
        self.sidebar_bg_slideshow_interval_spinbox = QSpinBox()
        self.sidebar_bg_slideshow_interval_spinbox.setRange(1, 3600)
        self.sidebar_bg_slideshow_interval_spinbox.setSuffix(" sec")
        self.sidebar_bg_slideshow_interval_spinbox.setValue(int(mw.col.conf.get("modern_menu_sidebar_slideshow_interval", 10) or 10))
        self.sidebar_bg_slideshow_interval_row = self._create_main_bg_value_row("Change every", self.sidebar_bg_slideshow_interval_spinbox)
        controls_layout.addWidget(self.sidebar_bg_slideshow_interval_row)
        controls_layout.addWidget(self._create_main_bg_toggle_row("Color only", self.sidebar_bg_color_only_toggle))
        controls_layout.addStretch()

        reset_row = QWidget()
        reset_row_layout = QHBoxLayout(reset_row)
        reset_row_layout.setContentsMargins(0, 0, 0, 0)
        reset_row_layout.addStretch()
        self.sidebar_bg_reset_button = QPushButton(tr("reset_bg_default"))
        self.sidebar_bg_reset_button.setObjectName("mainBackgroundResetButton")
        self.sidebar_bg_reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_bg_reset_button.setFixedHeight(34)
        self.sidebar_bg_reset_button.setMinimumWidth(220)
        self.sidebar_bg_reset_button.setMaximumWidth(280)
        self.sidebar_bg_reset_button.clicked.connect(self.reset_sidebar_to_default)
        reset_row_layout.addWidget(self.sidebar_bg_reset_button)
        reset_row_layout.addStretch()
        controls_layout.addWidget(reset_row)

        self.sidebar_bg_single_color_input = QLineEdit(light_color)
        self.sidebar_bg_light_color_input = QLineEdit(light_color)
        self.sidebar_bg_dark_color_input = QLineEdit(dark_color)

        self.sidebar_bg_import_button.clicked.connect(self._import_sidebar_background)
        self.sidebar_bg_clear_button.clicked.connect(self._clear_sidebar_background)
        self.sidebar_bg_gallery_button.clicked.connect(self._open_sidebar_background_gallery)
        self.sidebar_bg_color_button.clicked.connect(self._choose_sidebar_background_color)
        self.sidebar_bg_color_value_button.clicked.connect(self._choose_sidebar_background_color)
        self.sidebar_bg_dynamic_toggle.toggled.connect(self._on_sidebar_background_mode_changed)
        self.sidebar_bg_slideshow_toggle.toggled.connect(self._on_sidebar_background_mode_changed)
        self.sidebar_bg_color_only_toggle.toggled.connect(self._on_sidebar_background_mode_changed)
        self.sidebar_bg_slideshow_interval_spinbox.valueChanged.connect(self._on_sidebar_background_slideshow_interval_changed)
        self.sidebar_bg_blur_slider.valueChanged.connect(self._on_sidebar_background_effect_changed)
        self.sidebar_bg_opacity_slider.valueChanged.connect(self._on_sidebar_background_effect_changed)
        for line_edit in (self.sidebar_bg_single_color_input, self.sidebar_bg_light_color_input, self.sidebar_bg_dark_color_input):
            line_edit.textChanged.connect(lambda _=None: self._update_sidebar_background_preview())

        outer.addWidget(self.sidebar_bg_preview, 4)
        outer.addWidget(controls, 6)
        self._update_sidebar_background_controls()
        return self.sidebar_bg_designer

    def _sidebar_background_active_color_input(self):
        if self.sidebar_bg_dynamic_toggle.isChecked():
            return self.sidebar_bg_dark_color_input if theme_manager.night_mode else self.sidebar_bg_light_color_input
        return self.sidebar_bg_single_color_input

    def _sidebar_background_active_image(self):
        if self.sidebar_bg_slideshow_toggle.isChecked():
            if not self.sidebar_bg_slideshow_images:
                return ""
            self.sidebar_bg_slideshow_index %= len(self.sidebar_bg_slideshow_images)
            return self.sidebar_bg_slideshow_images[self.sidebar_bg_slideshow_index]
        if self.sidebar_bg_dynamic_toggle.isChecked():
            key = "sidebar_dark" if theme_manager.night_mode else "sidebar_light"
            return self.galleries.get(key, {}).get("selected", "")
        return self.galleries.get("sidebar_single", {}).get("selected", "")

    def _sidebar_background_slideshow_interval_ms(self):
        seconds = self.sidebar_bg_slideshow_interval_spinbox.value() if hasattr(self, "sidebar_bg_slideshow_interval_spinbox") else 10
        return max(1, int(seconds)) * 1000

    def _sync_sidebar_background_slideshow_preview_timer(self):
        timer = getattr(self, "sidebar_bg_slideshow_preview_timer", None)
        if not timer:
            return
        should_run = (
            self.sidebar_bg_slideshow_toggle.isChecked()
            and not self.sidebar_bg_color_only_toggle.isChecked()
            and len(self.sidebar_bg_slideshow_images) > 1
        )
        if should_run:
            timer.start(self._sidebar_background_slideshow_interval_ms())
        else:
            timer.stop()

    def _advance_sidebar_background_slideshow_preview(self):
        self.sidebar_bg_slideshow_images = self._sanitize_sidebar_background_slideshow_images(self.sidebar_bg_slideshow_images)
        if not self.sidebar_bg_slideshow_images:
            self.sidebar_bg_slideshow_index = 0
            self._update_sidebar_background_preview()
            return
        self.sidebar_bg_slideshow_index = (self.sidebar_bg_slideshow_index + 1) % len(self.sidebar_bg_slideshow_images)
        self._update_sidebar_background_preview(animate=True)

    def _on_sidebar_background_slideshow_interval_changed(self, value):
        self._sync_sidebar_background_slideshow_preview_timer()

    def _on_sidebar_background_effect_changed(self):
        self.sidebar_bg_blur_value_label.setText(f"{self.sidebar_bg_blur_slider.value()}%")
        self.sidebar_bg_opacity_value_label.setText(f"{self.sidebar_bg_opacity_slider.value()}%")
        self._update_sidebar_background_preview()

    def _on_sidebar_background_mode_changed(self, checked):
        sender = self.sender()
        if sender is self.sidebar_bg_color_only_toggle and checked:
            self.sidebar_bg_slideshow_toggle.setChecked(False)
        elif sender is self.sidebar_bg_slideshow_toggle and checked:
            self.sidebar_bg_color_only_toggle.setChecked(False)
        self._update_sidebar_background_controls()

    def _update_sidebar_background_controls(self):
        color_only = self.sidebar_bg_color_only_toggle.isChecked()
        for button in (self.sidebar_bg_import_button, self.sidebar_bg_clear_button, self.sidebar_bg_gallery_button):
            button.setEnabled(not color_only)
        if hasattr(self, "sidebar_bg_slideshow_interval_row"):
            visible = self.sidebar_bg_slideshow_toggle.isChecked() and not color_only
            self.sidebar_bg_slideshow_interval_row.setVisible(visible)
            self.sidebar_bg_slideshow_interval_spinbox.setEnabled(visible)
        self._update_sidebar_background_preview()
        self._sync_sidebar_background_slideshow_preview_timer()

    def _update_sidebar_background_preview(self, animate=False):
        if not hasattr(self, "sidebar_bg_preview"):
            return
        color = self._sidebar_background_active_color_input().text()
        if not QColor(color).isValid():
            color = "#F3F3F3"
        self._style_main_background_color_button(self.sidebar_bg_color_value_button, color)

        self.sidebar_bg_slideshow_images = self._sanitize_sidebar_background_slideshow_images(self.sidebar_bg_slideshow_images)
        if self.sidebar_bg_slideshow_index >= len(self.sidebar_bg_slideshow_images):
            self.sidebar_bg_slideshow_index = 0
        image_name = "" if self.sidebar_bg_color_only_toggle.isChecked() else self._sidebar_background_active_image()
        image_path = self._sidebar_bg_image_path(image_name)
        self.sidebar_bg_preview.setStyleSheet("QLabel#mainBackgroundPreview { background: transparent; border: none; }")
        pixmap = self._render_sidebar_background_preview_pixmap(color, image_path if image_name and os.path.exists(image_path) else "")
        text = "" if image_name or self.sidebar_bg_color_only_toggle.isChecked() else "No background selected"
        should_animate = (
            animate
            and self.sidebar_bg_slideshow_toggle.isChecked()
            and not self.sidebar_bg_color_only_toggle.isChecked()
            and bool(image_name)
            and len(self.sidebar_bg_slideshow_images) > 1
        )
        self._set_sidebar_background_preview_pixmap(pixmap, text, should_animate)

    def _set_sidebar_background_preview_pixmap(self, pixmap, text="", animate=False):
        fade_label = getattr(self, "sidebar_bg_preview_fade_label", None)
        fade_animation = getattr(self, "sidebar_bg_preview_fade_animation", None)
        fade_effect = getattr(self, "sidebar_bg_preview_fade_effect", None)
        if not animate or not fade_label or not fade_animation or not fade_effect:
            if fade_animation and fade_animation.state() == QPropertyAnimation.State.Running:
                fade_animation.stop()
            if fade_label:
                fade_label.hide()
            self.sidebar_bg_preview.setPixmap(pixmap)
            self.sidebar_bg_preview.setText(text)
            self._pending_sidebar_bg_preview_pixmap = None
            self._pending_sidebar_bg_preview_text = ""
            return

        fade_animation.stop()
        fade_label.setGeometry(self.sidebar_bg_preview.rect())
        fade_label.setPixmap(pixmap)
        fade_label.setText(text)
        fade_label.raise_()
        fade_label.show()
        fade_effect.setOpacity(0.0)
        self._pending_sidebar_bg_preview_pixmap = pixmap
        self._pending_sidebar_bg_preview_text = text
        fade_animation.setDuration(min(1200, max(350, self._sidebar_background_slideshow_interval_ms() - 120)))
        fade_animation.setStartValue(0.0)
        fade_animation.setEndValue(1.0)
        fade_animation.start()

    def _finalize_sidebar_background_preview_fade(self):
        pixmap = getattr(self, "_pending_sidebar_bg_preview_pixmap", None)
        text = getattr(self, "_pending_sidebar_bg_preview_text", "")
        if pixmap is not None:
            self.sidebar_bg_preview.setPixmap(pixmap)
            self.sidebar_bg_preview.setText(text)
        if hasattr(self, "sidebar_bg_preview_fade_label"):
            self.sidebar_bg_preview_fade_label.hide()
        self._pending_sidebar_bg_preview_pixmap = None
        self._pending_sidebar_bg_preview_text = ""

    def _sidebar_background_cover_image(self, image_path, width, height):
        source = QImage(image_path)
        if source.isNull():
            return QPixmap()

        scaled = source.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - width) // 2)
        y = max(0, (scaled.height() - height) // 2)
        cropped = scaled.copy(x, y, width, height)
        blur = self.sidebar_bg_blur_slider.value() if hasattr(self, "sidebar_bg_blur_slider") else 0
        if blur > 0:
            return self._qt_blurred_pixmap(QPixmap.fromImage(cropped), float(blur) / 3.0)
        return QPixmap.fromImage(cropped)

    def _render_sidebar_background_preview_pixmap(self, color, image_path):
        size = self.sidebar_bg_preview.size()
        width = max(1, size.width())
        height = max(1, size.height())
        radius = 22
        target = QPixmap(width, height)
        target.fill(Qt.GlobalColor.transparent)

        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        preview_rect = QRectF(1, 1, width - 2, height - 2)
        path = QPainterPath()
        path.addRoundedRect(preview_rect, radius, radius)
        painter.setClipPath(path)
        painter.fillPath(path, QBrush(QColor(color)))

        if image_path:
            image = self._sidebar_background_cover_image(image_path, width, height)
            if not image.isNull():
                painter.setOpacity(max(0.0, min(1.0, self.sidebar_bg_opacity_slider.value() / 100.0)))
                painter.drawPixmap(0, 0, image)
                painter.setOpacity(1.0)

        painter.setClipping(False)
        border_color = QColor("#4b5563" if theme_manager.night_mode else "#d1d5db")
        pen = QPen(border_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()
        return target

    def _draw_sidebar_preview_mockup(self, painter, rect, mode):
        # Vertical sidebar column (left / right positions): profile, then the
        # action buttons, then the deck list — all sized from the column width
        # so nothing overflows or clips regardless of how narrow the column is.
        pad = max(8.0, rect.width() * 0.05)
        content_rect = rect.adjusted(pad, pad, -pad, -pad)
        if content_rect.width() <= 8 or content_rect.height() <= 8:
            return
        gap = max(5.0, content_rect.width() * 0.03)
        profile_gap = max(3.0, content_rect.width() * 0.012)
        # Profile bar and Add button share one box size (same width AND height).
        bar_height = max(26.0, min(46.0, content_rect.width() * 0.14))

        y = content_rect.y()
        profile_height = self._draw_sidebar_preview_profile(
            painter,
            QRectF(content_rect.x(), y, content_rect.width(), bar_height),
        )
        if profile_height > 0:
            y += profile_height + profile_gap

        actions_rect = QRectF(content_rect.x(), y, content_rect.width(), max(0.0, content_rect.bottom() - y))
        # The "Add" CTA is intentionally shorter than the profile bar.
        actions_height = self._draw_sidebar_preview_actions(
            painter, actions_rect, mode, add_button_height=bar_height * 0.72
        )
        if actions_height > 0:
            y += actions_height + gap

        decks_rect = QRectF(content_rect.x(), y, content_rect.width(), max(0.0, content_rect.bottom() - y))
        if decks_rect.height() > 14:
            self._draw_sidebar_preview_decks(painter, decks_rect, mode)

    def _sidebar_actions_mode(self):
        group = getattr(self, "sidebar_actions_mode_group", None)
        if group is not None:
            button = group.checkedButton()
            if button is not None:
                key = button.property("sidebar_actions_mode")
                if key in {"list", "collapsed", "archived"}:
                    return key
        return self.current_config.get("sidebarActionsMode", "list")

    def _sidebar_preview_actions_mode(self):
        return self._sidebar_actions_mode()

    def _update_sidebar_actions_editor_visibility(self):
        container = getattr(self, "sidebar_layout_editor_container", None)
        if container is None:
            return
        target_visible = self._sidebar_actions_mode() in {"list", "collapsed"}
        if container.isVisible() == target_visible:
            return
        # Collapsing/expanding the large drag-drop editor reflows the whole
        # scroll page (heightForWidth cascades over several passes), which
        # briefly mis-places the preview. Freeze the window, resolve the relayout
        # synchronously while repaints are off, then repaint the settled result
        # once — so no intermediate (glitch) frame is ever shown.
        window = container.window()
        window.setUpdatesEnabled(False)
        try:
            container.setVisible(target_visible)
            app = getattr(mw, "app", None)
            if app is not None:
                for _ in range(4):
                    app.sendPostedEvents(None, QEvent.Type.LayoutRequest)
        finally:
            window.setUpdatesEnabled(True)
            window.update()

    def _on_sidebar_actions_mode_changed(self, prefix):
        self._update_modern_background_preview(prefix)
        self._update_sidebar_actions_editor_visibility()
        self._sync_action_buttons_mode_control()
        self._update_action_buttons_preview()

    def _sidebar_frame_slider_value(self, attr, conf_key, default):
        slider = getattr(self, f"sidebar_bg_{attr}_slider", None)
        if slider is not None:
            try:
                return int(slider.value())
            except Exception:
                pass
        try:
            return int(float(mw.col.conf.get(conf_key, default)))
        except (TypeError, ValueError):
            return default

    def _sidebar_preview_fill_color(self, mode):
        dynamic = getattr(self, "sidebar_bg_dynamic_toggle", None)
        if dynamic is not None and dynamic.isChecked():
            line_edit = getattr(
                self,
                "sidebar_bg_dark_color_input" if mode == "dark" else "sidebar_bg_light_color_input",
                None,
            )
        else:
            line_edit = getattr(self, "sidebar_bg_single_color_input", None) or getattr(
                self, "sidebar_bg_light_color_input", None
            )
        if line_edit is not None:
            text = line_edit.text()
            if QColor(text).isValid():
                return text
        conf_key = "modern_menu_sidebar_bg_color_dark" if mode == "dark" else "modern_menu_sidebar_bg_color_light"
        return mw.col.conf.get(conf_key, "#2C2C2C" if mode == "dark" else "#F3F3F3")

    def _sidebar_preview_image_path(self, mode):
        color_only = getattr(self, "sidebar_bg_color_only_toggle", None)
        if color_only is not None and color_only.isChecked():
            return ""
        spec = self._modern_background_spec("sidebar")
        if not spec:
            return ""
        dynamic = getattr(self, "sidebar_bg_dynamic_toggle", None)
        if dynamic is not None and dynamic.isChecked():
            gallery_key = "sidebar_dark" if mode == "dark" else "sidebar_light"
        else:
            gallery_key = "sidebar_single"
        filename = self.galleries.get(gallery_key, {}).get("selected", "")
        return self._modern_bg_image_path(spec, filename) if filename else ""

    def _sidebar_layout_working_config(self):
        """The single source of truth for the action-button layout while the
        dialog is open. Lazily seeded from the saved config and normalized so
        every external (sidebar API) entry that isn't explicitly visible counts
        as archived."""
        working = getattr(self, "_sidebar_layout_working", None)
        if not isinstance(working, dict):
            source = self.current_config.get("sidebarButtonLayout", DEFAULTS["sidebarButtonLayout"])
            working = copy.deepcopy(source) if isinstance(source, dict) else {"visible": [], "archived": []}
            working.setdefault("visible", [])
            working.setdefault("archived", [])
            external = self._action_external_ids()
            for ext in external:
                if ext not in working["visible"] and ext not in working["archived"]:
                    working["archived"].append(ext)
            self._sidebar_layout_working = working
        return working

    def _sidebar_preview_visible_actions(self):
        action_ids = self.ACTION_BUTTON_ORDER_IDS
        working = self._sidebar_layout_working_config()
        return [key for key in working.get("visible", []) if key in action_ids]

    def _sidebar_preview_action_label(self, action_id):
        return self._action_button_display_label(action_id)

    def _draw_sidebar_preview_actions(self, painter, rect, mode, add_button_height=None):
        action_mode = self._sidebar_preview_actions_mode()
        if action_mode == "archived":
            return 0.0

        ids = self._sidebar_preview_visible_actions()
        if not ids:
            return 0.0

        # Keep icon_color a hex string: _render_icon_value_pixmap str.replace()s
        # it into the SVG, so a QColor would raise (swallowed) and drop the icon.
        icon_color = self._deck_icon_color(mode)
        text_color = QColor(self._deck_icon_text_color(mode))

        if action_mode == "collapsed":
            # A single justified row of icon-only buttons that spans the full
            # width (same as the profile bar), evenly distributed edge to edge.
            n = len(ids)
            min_gap = max(4.0, rect.width() * 0.015)
            max_button = min(30.0, rect.width() * 0.1)
            button_size = max(10.0, min(max_button, (rect.width() - (n - 1) * min_gap) / n))
            gap = (rect.width() - n * button_size) / (n - 1) if n > 1 else 0.0
            gap = max(0.0, gap)
            y = rect.y()
            for index, action_id in enumerate(ids):
                x = rect.x() + index * (button_size + gap)
                button_rect = QRectF(x, y, button_size, button_size)
                pill_path = QPainterPath()
                pill_path.addRoundedRect(button_rect, button_size * 0.3, button_size * 0.3)
                tint = QColor(text_color)
                tint.setAlpha(26)
                painter.fillPath(pill_path, QBrush(tint))
                icon_rect = button_rect.adjusted(
                    button_size * 0.24, button_size * 0.24, -button_size * 0.24, -button_size * 0.24
                )
                self._draw_box_effect_preview_icon(painter, icon_rect, self._action_icon_preview_value(action_id), icon_color)
            return button_size

        # List mode (default): one labelled row per action, with "Add" drawn as
        # the dashed call-to-action button the real sidebar uses.
        row_height = max(15.0, min(23.0, rect.width() * 0.075))
        icon_size = row_height * 0.56
        left_pad = max(6.0, rect.width() * 0.04)
        gap = max(3.0, rect.width() * 0.012)
        label_font = QFont(self.font())
        label_font.setPointSize(max(7, int(row_height * 0.40)))
        metrics = QFontMetrics(label_font)

        # The dashed "Add" bar matches the profile bar's height when one was
        # given (the real sidebar shows them as equal-height bars).
        add_bar_height = add_button_height if (add_button_height and add_button_height > 0) else row_height * 1.2

        y = rect.y()
        for action_id in ids:
            if action_id == "add":
                slot_height = add_bar_height + gap
                if y + slot_height > rect.bottom() + 0.5:
                    break
                button_rect = QRectF(rect.x(), y + gap * 0.5, rect.width(), add_bar_height)
                button_path = QPainterPath()
                button_path.addRoundedRect(button_rect, button_rect.height() * 0.3, button_rect.height() * 0.3)
                dash_color = QColor(text_color)
                dash_color.setAlpha(120)
                dash_pen = QPen(dash_color)
                dash_pen.setWidthF(1.0)
                dash_pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(dash_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(button_path)
                painter.setFont(label_font)
                label = self._sidebar_preview_action_label("add")
                label_width = metrics.horizontalAdvance(label)
                add_icon_size = min(row_height * 0.56, add_bar_height * 0.5)
                cluster_width = add_icon_size + gap + label_width
                cluster_x = button_rect.center().x() - cluster_width / 2
                add_icon_rect = QRectF(cluster_x, button_rect.center().y() - add_icon_size / 2, add_icon_size, add_icon_size)
                self._draw_box_effect_preview_icon(painter, add_icon_rect, self._action_icon_preview_value("add"), icon_color)
                painter.setPen(text_color)
                painter.drawText(
                    QRectF(add_icon_rect.right() + gap, button_rect.y(), label_width + 4, button_rect.height()),
                    Qt.AlignmentFlag.AlignVCenter,
                    label,
                )
                y += slot_height
                continue

            if y + row_height > rect.bottom() + 0.5:
                break
            row_rect = QRectF(rect.x(), y, rect.width(), row_height)
            icon_rect = QRectF(
                row_rect.x() + left_pad, row_rect.y() + (row_height - icon_size) / 2, icon_size, icon_size
            )
            self._draw_box_effect_preview_icon(painter, icon_rect, self._action_icon_preview_value(action_id), icon_color)
            painter.setFont(label_font)
            painter.setPen(text_color)
            avail = max(0.0, row_rect.right() - icon_rect.right() - left_pad)
            text = metrics.elidedText(self._sidebar_preview_action_label(action_id), Qt.TextElideMode.ElideRight, int(avail))
            painter.drawText(
                QRectF(icon_rect.right() + left_pad * 0.7, row_rect.y(), avail, row_height),
                Qt.AlignmentFlag.AlignVCenter,
                text,
            )
            y += row_height

        return y - rect.y()

    def _draw_sidebar_preview_decks(self, painter, rect, mode):
        if rect.height() <= 14 or rect.width() <= 24:
            return
        text_color = QColor(self._deck_icon_text_color(mode))
        header_height = max(12.0, min(18.0, rect.width() * 0.045))
        header_font = QFont(self.font())
        header_font.setPointSize(max(6, int(header_height * 0.62)))
        header_font.setBold(True)
        header_color = QColor(text_color)
        header_color.setAlpha(140)
        painter.setFont(header_font)
        # Header action icons on the right: search + sort always, plus a home
        # icon when the action buttons are archived (matching the real header).
        header_icons = ["search.svg", "sort_default.svg"]
        if self._sidebar_preview_actions_mode() == "archived":
            header_icons.append("home.svg")
        icon_color = self._deck_icon_color(mode)
        icon_sz = min(header_height, max(8.0, rect.width() * 0.04))
        icon_gap = max(4.0, rect.width() * 0.022)
        x_right = rect.right()
        for filename in reversed(header_icons):
            icon_rect = QRectF(
                x_right - icon_sz, rect.y() + (header_height - icon_sz) / 2, icon_sz, icon_sz
            )
            self._draw_box_effect_preview_icon(painter, icon_rect, f"system:{filename}", icon_color)
            x_right -= icon_sz + icon_gap

        painter.setPen(header_color)
        painter.drawText(
            QRectF(rect.x(), rect.y(), max(0.0, x_right - rect.x()), header_height),
            Qt.AlignmentFlag.AlignVCenter,
            tr("decks").upper(),
        )
        rows_top = rect.y() + header_height + max(3.0, rect.width() * 0.012)
        rows_rect = QRectF(rect.x(), rows_top, rect.width(), max(0.0, rect.bottom() - rows_top))
        if rows_rect.height() > 10:
            self._draw_sidebar_preview_deck_rows(painter, rows_rect, mode)

    def _draw_sidebar_preview_deck_rows(self, painter, rect, mode):
        # Same deck-type sample as the deck-icon preview (Expanded Folder ->
        # Subdecks -> Deck -> Filtered Deck -> Collapsed Folder), but with
        # compact, width-derived sizing so it reads as a miniature instead of
        # blowing up the icons/fonts the way the wide deck-icon preview would.
        icon_color = self._deck_icon_color(mode)
        filtered_color = self._deck_icon_filtered_color(mode)
        text_color = QColor(self._deck_icon_text_color(mode))
        highlight_color = QColor(self._deck_icon_highlight_color(mode))

        row_height = max(15.0, min(23.0, rect.width() * 0.07))
        icon_size = row_height * 0.62
        chevron_size = row_height * 0.42
        indent = max(8.0, rect.width() * 0.05)
        left_pad = max(5.0, rect.width() * 0.025)
        item_gap = max(3.0, rect.width() * 0.012)
        chevron_col = chevron_size + item_gap

        rows = [
            {"key": "folder", "chevron": "collapse_open", "indent": 0,
             "label": tr("deck_icon_preview_folder", "Folder"), "counts": (15, 12, 18)},
            {"key": "subdeck", "chevron": None, "indent": indent,
             "label": tr("deck_icon_preview_subdeck", "Subdeck"), "counts": (13, 11, 14)},
            {"key": "subdeck", "chevron": None, "indent": indent,
             "label": tr("deck_icon_preview_subdeck", "Subdeck"), "counts": (0, 0, 12)},
            {"key": "deck", "chevron": None, "indent": 0,
             "label": tr("deck_icon_preview_deck", "Deck"), "highlight": True, "counts": (10, 0, 15)},
            {"key": "filtered_deck", "chevron": None, "indent": 0,
             "label": tr("deck_icon_preview_filtered", "Filtered Deck"), "counts": (17, 0, 0)},
            {"key": "folder", "chevron": "collapse_closed", "indent": 0,
             "label": tr("deck_icon_preview_folder", "Folder"), "counts": (12, 13, 20)},
        ]
        max_rows = int(rect.height() // row_height)
        if max_rows <= 0:
            return
        rows = rows[:max_rows]

        label_font = QFont(self.font())
        label_font.setPointSize(max(6, int(row_height * 0.40)))
        metrics = QFontMetrics(label_font)

        for index, row in enumerate(rows):
            row_rect = QRectF(rect.x(), rect.y() + index * row_height, rect.width(), row_height)

            if row.get("highlight"):
                highlight_rect = row_rect.adjusted(1.5, 1.0, -1.5, -1.0)
                highlight_path = QPainterPath()
                highlight_path.addRoundedRect(highlight_rect, 6, 6)
                painter.fillPath(highlight_path, QBrush(highlight_color))

            x = row_rect.x() + left_pad + row["indent"]
            chevron_rect = QRectF(x, row_rect.y() + (row_height - chevron_size) / 2, chevron_size, chevron_size)
            if row["chevron"]:
                self._draw_box_effect_preview_icon(
                    painter, chevron_rect, self._deck_icon_preview_icon_value(row["chevron"]), icon_color
                )
            x += chevron_col

            icon_rect = QRectF(x, row_rect.y() + (row_height - icon_size) / 2, icon_size, icon_size)
            if self._deck_icon_preview_visible(row["key"]):
                tint = filtered_color if row["key"] == "filtered_deck" else icon_color
                self._draw_box_effect_preview_icon(
                    painter, icon_rect, self._deck_icon_preview_icon_value(row["key"]), tint
                )
            x += icon_size + item_gap

            counts_left = self._draw_deck_icon_preview_counts(painter, row_rect, mode, row.get("counts", (0, 0, 0)), left_pad)
            painter.setFont(label_font)
            painter.setPen(text_color)
            avail = max(0.0, counts_left - x - item_gap)
            text = metrics.elidedText(row["label"], Qt.TextElideMode.ElideRight, int(avail))
            painter.drawText(QRectF(x, row_rect.y(), avail, row_height), Qt.AlignmentFlag.AlignVCenter, text)

    def _draw_sidebar_preview_center_widgets(self, painter, rect, mode):
        # The Home content shown below the centered sidebar card, drawn as plain
        # transparent outlined boxes: a row of four stat cards and an activity card.
        text_color = QColor(self._deck_icon_text_color(mode))
        border = QColor(text_color)
        border.setAlpha(95)

        gap = max(6.0, rect.width() * 0.02)
        columns = 4
        card_w = (rect.width() - gap * (columns - 1)) / columns
        if card_w <= 2:
            return
        stat_h = min(max(34.0, card_w * 0.72), rect.height() * 0.46)
        radius = max(6.0, min(14.0, card_w * 0.14))

        painter.setPen(QPen(border, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(columns):
            cx = rect.x() + i * (card_w + gap)
            painter.drawRoundedRect(QRectF(cx, rect.y(), card_w, stat_h), radius, radius)

        act_top = rect.y() + stat_h + gap
        act_rect = QRectF(rect.x(), act_top, rect.width(), max(0.0, rect.bottom() - act_top))
        if act_rect.height() >= 20:
            painter.setPen(QPen(border, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(act_rect, radius, radius)

    def _choose_sidebar_background_color(self):
        line_edit = self._sidebar_background_active_color_input()
        chosen, ok = OnigiriColorDialog.getColor(line_edit.text(), self, anchor=self.sender() if isinstance(self.sender(), QWidget) else None)
        if ok:
            line_edit.setText(chosen)
            self._update_sidebar_background_preview()

    def _import_sidebar_background(self):
        filepath, _ = QFileDialog.getOpenFileName(self, tr("import_image"), "", "Images (*.png *.jpg *.jpeg *.gif *.webp)")
        if not filepath:
            return
        filename = os.path.basename(filepath)
        dest_path = os.path.join(self._sidebar_bg_folder_path(), filename)
        base, ext = os.path.splitext(filename)
        index = 2
        while os.path.exists(dest_path) and os.path.abspath(filepath) != os.path.abspath(dest_path):
            filename = f"{base}-{index}{ext}"
            dest_path = os.path.join(self._sidebar_bg_folder_path(), filename)
            index += 1
        try:
            if os.path.abspath(filepath) != os.path.abspath(dest_path):
                shutil.copy(filepath, dest_path)
            self._assign_sidebar_background_image(filename)
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not import image: {exc}")

    def _clear_sidebar_background(self):
        if self.sidebar_bg_slideshow_toggle.isChecked():
            self.sidebar_bg_slideshow_images = []
            self.sidebar_bg_slideshow_index = 0
        elif self.sidebar_bg_dynamic_toggle.isChecked():
            self.galleries["sidebar_light"]["selected"] = ""
            self.galleries["sidebar_dark"]["selected"] = ""
        else:
            self.galleries["sidebar_single"]["selected"] = ""
        self._update_sidebar_background_preview()
        self._sync_sidebar_background_slideshow_preview_timer()

    def _assign_sidebar_background_image(self, filename, target=None):
        if self.sidebar_bg_slideshow_toggle.isChecked():
            self.sidebar_bg_slideshow_images = self._sanitize_sidebar_background_slideshow_images(self.sidebar_bg_slideshow_images)
            if filename not in self.sidebar_bg_slideshow_images:
                self.sidebar_bg_slideshow_images.append(filename)
            self.sidebar_bg_slideshow_index = max(0, min(self.sidebar_bg_slideshow_index, len(self.sidebar_bg_slideshow_images) - 1))
        elif self.sidebar_bg_dynamic_toggle.isChecked():
            key = target or ("sidebar_dark" if theme_manager.night_mode else "sidebar_light")
            self.galleries[key]["selected"] = filename
        else:
            self.galleries["sidebar_single"]["selected"] = filename
        self._update_sidebar_background_preview()
        self._sync_sidebar_background_slideshow_preview_timer()

    def _open_sidebar_background_gallery(self):
        if self.sidebar_bg_color_only_toggle.isChecked():
            return
        self.sidebar_bg_slideshow_images = self._sanitize_sidebar_background_slideshow_images(self.sidebar_bg_slideshow_images)
        dialog = BackgroundGalleryDialog(self)
        dialog.setWindowTitle("Select from your Gallery")
        dialog.resize(760, 520)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self._style_background_gallery_dialog(dialog)
        mode = self._background_gallery_mode(
            self.sidebar_bg_dynamic_toggle.isChecked(),
            self.sidebar_bg_slideshow_toggle.isChecked(),
        )
        layout.addWidget(self._create_background_gallery_hint_bar(mode))
        target_mode = {"value": "sidebar_dark" if theme_manager.night_mode else "sidebar_light"}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("backgroundGalleryContent")
        grid = FlowLayout(content, margin=0, spacing=10)
        tiles = []

        def badges_for(filename):
            if mode == "slideshow":
                self.sidebar_bg_slideshow_images = self._sanitize_sidebar_background_slideshow_images(self.sidebar_bg_slideshow_images)
                return self._background_gallery_badges(mode, filename, order=self.sidebar_bg_slideshow_images.index(filename) + 1 if filename in self.sidebar_bg_slideshow_images else None)
            if mode == "dynamic":
                light = self.galleries.get("sidebar_light", {}).get("selected") == filename
                dark = self.galleries.get("sidebar_dark", {}).get("selected") == filename
                return self._background_gallery_badges(mode, filename, light_selected=light, dark_selected=dark)
            return self._background_gallery_badges(mode, filename, selected=self.galleries.get("sidebar_single", {}).get("selected") == filename)

        def refresh_badges():
            for tile in tiles:
                tile.setBadges(badges_for(tile.filename))
            self._update_sidebar_background_preview()

        def handle_click(filename):
            if mode == "slideshow":
                self.sidebar_bg_slideshow_images = self._sanitize_sidebar_background_slideshow_images(self.sidebar_bg_slideshow_images)
                if filename in self.sidebar_bg_slideshow_images:
                    self.sidebar_bg_slideshow_images.remove(filename)
                    self.sidebar_bg_slideshow_index = 0
                else:
                    self.sidebar_bg_slideshow_images.append(filename)
            elif mode == "dynamic":
                self._assign_sidebar_background_image(filename, target_mode["value"])
            else:
                self._assign_sidebar_background_image(filename)
            refresh_badges()
            self._sync_sidebar_background_slideshow_preview_timer()

        def handle_key_assignment(filename, key_text):
            if mode == "dynamic" and key_text in {"d", "l"}:
                self._assign_sidebar_background_image(filename, "sidebar_dark" if key_text == "d" else "sidebar_light")
            elif mode == "slideshow" and key_text in set("123456789"):
                self.sidebar_bg_slideshow_images = self._sanitize_sidebar_background_slideshow_images(self.sidebar_bg_slideshow_images)
                if filename in self.sidebar_bg_slideshow_images:
                    self.sidebar_bg_slideshow_images.remove(filename)
                self.sidebar_bg_slideshow_images.insert(int(key_text) - 1, filename)
                self.sidebar_bg_slideshow_index = 0
            else:
                return
            refresh_badges()
            self._sync_sidebar_background_slideshow_preview_timer()
            if dialog.hovered_tile:
                dialog.hovered_tile.flash()

        dialog.keyAssignmentRequested.connect(handle_key_assignment)

        for filename in self._sidebar_bg_image_files():
            tile = BackgroundGalleryTile(filename, self._sidebar_bg_image_path(filename), self.accent_color)
            tile.setBadges(badges_for(filename))
            tile.clicked.connect(handle_click)
            tile.hovered.connect(dialog.setHoveredTile)
            grid.addWidget(tile)
            tiles.append(tile)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        close_button = self._create_main_bg_button("Done")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def create_sidebar_page(self):
        page, layout = self._create_scrollable_page()

        # --- Sidebar Background Section ---
        sidebar_group = self._create_sidebar_background_designer()
        layout.addWidget(sidebar_group)

        # --- Action Button Customization Section ---
        action_buttons_designer = self._create_action_buttons_designer()
        layout.addWidget(action_buttons_designer)

        # The old "Organize Action Buttons" merged section (3-zone drag/drop
        # editor + per-icon cards) is fully replaced by the Action Button
        # Customization card above.

        divider2 = QFrame()
        divider2.setFrameShape(QFrame.Shape.HLine)
        divider2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider2)

        # Markers menu moved into the Sidebar Customization container (above).

        deck_section = SectionGroup("", self, border=False)
        
        deck_icon_designer = self._create_deck_icon_designer_group()
        deck_section.add_widget(deck_icon_designer)

        # Initial State Update
        self._update_deck_icon_state()
        self._update_deck_icon_preview()
        self._update_modern_background_preview("sidebar")

        layout.addWidget(deck_section)

        layout.addStretch()
        
        sections = {
            tr("sidebar_background"): sidebar_group,
            tr("action_button_customization", "Action Button Customization"): action_buttons_designer,
            tr("deck_icons"): deck_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections, buttons_per_row=3)

        return page

    def _deck_icon_sidebar_background_state(self, mode):
        # Mirrors the non-sync branch of _update_modern_background_preview("sidebar"),
        # since the deck list lives inside the sidebar, not the main background.
        prefix = "sidebar"
        if not hasattr(self, f"{prefix}_bg_single_color_input"):
            return {"color": "#f2f2f2" if mode == "light" else "#303030", "image_path": "", "blur": 0, "opacity": 100}

        spec = self._modern_background_spec(prefix)
        sync_main_toggle = getattr(self, f"{prefix}_bg_sync_main_toggle", None)
        if sync_main_toggle and sync_main_toggle.isChecked():
            state = self._main_background_state_for_box_preview(mode)
            state["blur"] = getattr(self, f"{prefix}_bg_blur_slider").value()
            state["opacity"] = getattr(self, f"{prefix}_bg_opacity_slider").value()
            return state

        single_key, light_key, dark_key = self._modern_background_gallery_keys(spec)
        single_color = self._modern_background_color_for_input(getattr(self, f"{prefix}_bg_single_color_input"))
        light_color = self._modern_background_color_for_input(getattr(self, f"{prefix}_bg_light_color_input"), single_color)
        dark_color = self._modern_background_color_for_input(getattr(self, f"{prefix}_bg_dark_color_input"), single_color)
        dynamic = getattr(self, f"{prefix}_bg_dynamic_toggle").isChecked()
        color_only = getattr(self, f"{prefix}_bg_color_only_toggle").isChecked()
        slideshow = getattr(self, f"{prefix}_bg_slideshow_toggle").isChecked()
        active_color = (dark_color if mode == "dark" else light_color) if dynamic else single_color
        if slideshow:
            image_name = "" if color_only else self._modern_background_active_image(prefix)
        elif dynamic:
            image_key = dark_key if mode == "dark" else light_key
            image_name = "" if color_only else self.galleries.get(image_key, {}).get("selected", "")
        else:
            image_name = "" if color_only else self.galleries.get(single_key, {}).get("selected", "")
        image_path = self._modern_bg_image_path(spec, image_name)
        return {
            "color": active_color,
            "image_path": image_path if image_name and os.path.exists(image_path) else "",
            "blur": getattr(self, f"{prefix}_bg_blur_slider").value(),
            "opacity": getattr(self, f"{prefix}_bg_opacity_slider").value(),
        }

    def _draw_deck_icon_sidebar_background_layer(self, painter, rect, mode):
        state = self._deck_icon_sidebar_background_state(mode)
        painter.fillRect(rect, QColor(state["color"]))
        image_path = state.get("image_path", "")
        if image_path and os.path.exists(image_path):
            image = self._background_cover_image_with_effect(
                image_path,
                int(rect.width()),
                int(rect.height()),
                int(state.get("blur", 0) or 0),
            )
            if not image.isNull():
                painter.setOpacity(max(0.0, min(1.0, float(state.get("opacity", 100)) / 100.0)))
                painter.drawPixmap(int(rect.x()), int(rect.y()), image)
                painter.setOpacity(1.0)

    def _toggle_sidebar_effect_options(self):
        if not hasattr(self, "sidebar_effect_overlay_radio"):
            return
        is_overlay = self.sidebar_effect_overlay_radio.isChecked()
        self.sidebar_overlay_options_group.setVisible(is_overlay)
        self.sidebar_effect_intensity_group.setVisible(not is_overlay)

    def create_sidebar_custom_options(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        
        type_mode = mw.col.conf.get("modern_menu_sidebar_bg_type", "color")
        # If the old 'image' mode was saved, default to 'Image' to prevent a blank state
        if type_mode == 'image':
            type_mode = 'image_color'
            
        type_layout = QHBoxLayout()
        self.sidebar_bg_type_color_radio = QRadioButton(tr("solid_color_mode"))
        self.sidebar_bg_type_accent_radio = QRadioButton(tr("accent_color"))
        self.sidebar_bg_type_image_color_radio = QRadioButton(tr("image_mode"))
        
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
        self.sidebar_bg_light_row = self._create_color_picker_row(tr("color_light_mode"), mw.col.conf.get("modern_menu_sidebar_bg_color_light", "#F3F3F3"), "sidebar_bg_light")
        sidebar_color_layout.addLayout(self.sidebar_bg_light_row)
        self.sidebar_bg_dark_row = self._create_color_picker_row(tr("color_dark_mode"), mw.col.conf.get("modern_menu_sidebar_bg_color_dark", "#3C3C3C"), "sidebar_bg_dark")
        sidebar_color_layout.addLayout(self.sidebar_bg_dark_row)
        layout.addWidget(self.sidebar_color_group)

        self.galleries["sidebar_bg"] = {}
        self.sidebar_image_group = self._create_image_gallery_group(
            "sidebar_bg",
            "user_files/sidebar_bg",
            "modern_menu_sidebar_bg_image",
            is_sub_group=True,
            actions_in_parent_header=True
        )
        layout.addWidget(self.sidebar_image_group)

        self.sidebar_effects_container = QWidget()
        effects_layout = QHBoxLayout(self.sidebar_effects_container)
        effects_layout.setContentsMargins(0, 10, 0, 0)
        
        self.sidebar_bg_blur_label = QLabel(tr("blur_label"))
        self.sidebar_bg_blur_spinbox = QSpinBox()
        self.sidebar_bg_blur_spinbox.setMinimum(0)
        self.sidebar_bg_blur_spinbox.setMaximum(100)
        self.sidebar_bg_blur_spinbox.setSuffix(" %")
        self.sidebar_bg_blur_spinbox.setValue(mw.col.conf.get("modern_menu_sidebar_bg_blur", 0))
        effects_layout.addWidget(self.sidebar_bg_blur_label)
        effects_layout.addWidget(self.sidebar_bg_blur_spinbox)
        
        self.sidebar_bg_opacity_label = QLabel(tr("image_opacity_label"))
        self.sidebar_bg_opacity_spinbox = QSpinBox()
        self.sidebar_bg_opacity_spinbox.setMinimum(0)
        self.sidebar_bg_opacity_spinbox.setMaximum(100)
        self.sidebar_bg_opacity_spinbox.setSuffix(" %")
        self.sidebar_bg_opacity_spinbox.setValue(mw.col.conf.get("modern_menu_sidebar_bg_opacity", 100))
        effects_layout.addWidget(self.sidebar_bg_opacity_label)
        effects_layout.addWidget(self.sidebar_bg_opacity_spinbox)

        self.sidebar_bg_transparency_label = QLabel(tr("transparency_label"))
        self.sidebar_bg_transparency_spinbox = QSpinBox()
        self.sidebar_bg_transparency_spinbox.setMinimum(0)
        self.sidebar_bg_transparency_spinbox.setMaximum(100)
        self.sidebar_bg_transparency_spinbox.setSuffix(" %")
        self.sidebar_bg_transparency_spinbox.setValue(mw.col.conf.get("modern_menu_sidebar_bg_transparency", 100))
        effects_layout.addWidget(self.sidebar_bg_transparency_label)
        effects_layout.addWidget(self.sidebar_bg_transparency_spinbox)

        effects_layout.addStretch()
        layout.addWidget(self.sidebar_effects_container)

        self.sidebar_bg_type_color_radio.toggled.connect(self.toggle_sidebar_bg_type_options)
        self.sidebar_bg_type_image_color_radio.toggled.connect(self.toggle_sidebar_bg_type_options)
        self.sidebar_bg_type_accent_radio.toggled.connect(self.toggle_sidebar_bg_type_options)
        
        self.toggle_sidebar_bg_type_options()
        return widget

    def reset_sidebar_to_default(self):
        if hasattr(self, "sidebar_bg_color_only_toggle"):
            if self._modern_background_spec("sidebar"):
                self._reset_modern_background_to_default("sidebar")
                return
            self.sidebar_bg_color_only_toggle.setChecked(True)
            self.sidebar_bg_slideshow_toggle.setChecked(False)
            self.sidebar_bg_dynamic_toggle.setChecked(True)
            self.sidebar_bg_single_color_input.setText("#F3F3F3")
            self.sidebar_bg_light_color_input.setText("#F3F3F3")
            self.sidebar_bg_dark_color_input.setText("#2C2C2C")
            self.sidebar_bg_slideshow_images = []
            self.sidebar_bg_slideshow_index = 0
            self.sidebar_bg_slideshow_interval_spinbox.setValue(10)
            for key in ["sidebar_single", "sidebar_light", "sidebar_dark", "sidebar_bg"]:
                if key in self.galleries:
                    self.galleries[key]["selected"] = ""
                    if self.galleries[key].get("path_input"):
                        self.galleries[key]["path_input"].setText("")
                    if self.galleries[key].get("grid_layout"):
                        self._refresh_gallery(key)
            self.sidebar_bg_blur_slider.setValue(0)
            self.sidebar_bg_opacity_slider.setValue(100)
            self._update_sidebar_background_controls()
            show_settings_toast(self, tr("sidebar_bg_reset_toast", "Sidebar background reset to default"))
            return

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
        show_settings_toast(self, tr("sidebar_bg_reset_toast", "Sidebar background reset to default"))

    def toggle_sidebar_background_options(self): 
        if not hasattr(self, "sidebar_bg_main_radio"):
            return
        self.sidebar_main_options_group.setVisible(self.sidebar_bg_main_radio.isChecked())
        is_custom = self.sidebar_bg_custom_radio.isChecked()
        self.sidebar_custom_options_group.setVisible(is_custom)
        if hasattr(self, "sidebar_image_group"):
            actions_widget = getattr(self.sidebar_image_group, "gallery_actions_widget", None)
            if actions_widget:
                actions_widget.setVisible(is_custom and self.sidebar_bg_type_image_color_radio.isChecked())

    def toggle_sidebar_bg_type_options(self):
        """Shows/hides options based on the selected sidebar background type."""
        try:
            if not hasattr(self, "sidebar_bg_type_color_radio"):
                return
            is_color = self.sidebar_bg_type_color_radio.isChecked()
            is_accent = self.sidebar_bg_type_accent_radio.isChecked()
            is_image_color = self.sidebar_bg_type_image_color_radio.isChecked()

            if self.sidebar_color_group:
                self.sidebar_color_group.setVisible(is_color or is_image_color)

            if self.sidebar_image_group:
                self.sidebar_image_group.setVisible(is_image_color)
                actions_widget = getattr(self.sidebar_image_group, "gallery_actions_widget", None)
                if actions_widget:
                    actions_widget.setVisible(is_image_color)

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

    def _save_sidebar_settings(self):

        self.current_config["hideDeckCounts"] = self.hide_deck_counts_checkbox.isChecked()
        self.current_config["hideAllDeckCounts"] = self.hide_all_deck_counts_checkbox.isChecked()

        if hasattr(self, "sidebar_position_group"):
            checked_position = self.sidebar_position_group.checkedButton()
            sidebar_position = checked_position.property("sidebar_position") if checked_position else "left"
            if sidebar_position not in {"left", "right", "center"}:
                sidebar_position = "left"
            self.current_config["sidebarPosition"] = sidebar_position
            mw.col.conf["modern_menu_sidebar_position"] = sidebar_position
            if sidebar_position == "center":
                mw.col.conf["onigiri_deck_cycle_state"] = 4
                mw.col.conf["onigiri_deck_focus_mode"] = False
            elif mw.col.conf.get("onigiri_deck_cycle_state") == 4:
                mw.col.conf["onigiri_deck_cycle_state"] = 0
                mw.col.conf["onigiri_deck_focus_mode"] = False
        
        # Save Sidebar Action Buttons Mode (selector lives in Sidebar Customization)
        if hasattr(self, "sidebar_actions_mode_group"):
            self.current_config["sidebarActionsMode"] = self._sidebar_actions_mode()
        
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
        if hasattr(self, "hide_filtered_deck_cb"):
            mw.col.conf["modern_menu_hide_filtered_deck_icon"] = self.hide_filtered_deck_cb.isChecked()
        if hasattr(self, "hide_default_custom_cb"):
            mw.col.conf["modern_menu_hide_default_icons"] = self.hide_default_custom_cb.isChecked()
        
        for widget in self.action_button_icon_widgets:
            key = widget.property("icon_key")
            value = widget.property("icon_filename")
            config_key = f"modern_menu_icon_{key}"
            mw.col.conf[config_key] = value or ""

        # Per-button icon colors + any icon overrides set from the Action Button
        # Customization reorder list (for keys without an icon-card widget).
        for key, value in getattr(self, "_action_button_icon_overrides", {}).items():
            mw.col.conf[f"modern_menu_icon_{key}"] = value or ""
        action_icon_colors = getattr(self, "_action_button_icon_colors", {})
        all_action_keys = (
            set(self.ACTION_BUTTON_ORDER_IDS)
            | set(self.ACTION_BUTTON_MORE_CHILDREN)
            | set(action_icon_colors.keys())
        )
        for key in all_action_keys:
            color = action_icon_colors.get(key, "")
            color_key = f"modern_menu_icon_color_{key}"
            if color and QColor(color).isValid():
                mw.col.conf[color_key] = color
            elif color_key in mw.col.conf:
                mw.col.conf[color_key] = ""

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
                    # A deleted C++ widget would raise RuntimeError on .text() and
                    # abort the rest of the save. The live edit handler already
                    # wrote current_config, so skipping a stale widget is safe.
                    try:
                        if sip is not None and sip.isdeleted(widget):
                            continue
                        self.current_config["colors"][mode][key] = widget.text()
                    except RuntimeError:
                        continue

        marker_colors = self.current_config.setdefault("markerColors", copy.deepcopy(DEFAULTS.get("markerColors", {})))
        for marker_key in ["red", "blue", "green", "yellow"]:
            input_widget = getattr(self, f"marker_{marker_key}_color_input", None)
            if input_widget:
                marker_colors[marker_key] = input_widget.text()

        # --- Sidebar Background Settings ---
        if hasattr(self, "sidebar_bg_color_only_toggle"):
            mw.col.conf["modern_menu_sidebar_bg_mode"] = "custom"
            if self.sidebar_bg_color_only_toggle.isChecked():
                mw.col.conf["modern_menu_sidebar_bg_type"] = "color"
            elif self.sidebar_bg_slideshow_toggle.isChecked():
                mw.col.conf["modern_menu_sidebar_bg_type"] = "slideshow"
            else:
                mw.col.conf["modern_menu_sidebar_bg_type"] = "image_color"

            color_theme_mode = "separate" if self.sidebar_bg_dynamic_toggle.isChecked() else "single"
            image_theme_mode = "separate" if self.sidebar_bg_dynamic_toggle.isChecked() else "single"
            mw.col.conf["modern_menu_sidebar_bg_color_theme_mode"] = color_theme_mode
            mw.col.conf["modern_menu_sidebar_bg_image_theme_mode"] = image_theme_mode

            if color_theme_mode == "single":
                single_color = self.sidebar_bg_single_color_input.text()
                mw.col.conf["modern_menu_sidebar_bg_color_light"] = single_color
                mw.col.conf["modern_menu_sidebar_bg_color_dark"] = single_color
            else:
                mw.col.conf["modern_menu_sidebar_bg_color_light"] = self.sidebar_bg_light_color_input.text()
                mw.col.conf["modern_menu_sidebar_bg_color_dark"] = self.sidebar_bg_dark_color_input.text()

            single_image = self.galleries.get("sidebar_single", {}).get("selected", "")
            light_image = self.galleries.get("sidebar_light", {}).get("selected", "")
            dark_image = self.galleries.get("sidebar_dark", {}).get("selected", "")
            if image_theme_mode == "single":
                mw.col.conf["modern_menu_sidebar_bg_image"] = single_image
                mw.col.conf["modern_menu_sidebar_bg_image_light"] = single_image
                mw.col.conf["modern_menu_sidebar_bg_image_dark"] = single_image
            else:
                mw.col.conf["modern_menu_sidebar_bg_image"] = light_image or dark_image
                mw.col.conf["modern_menu_sidebar_bg_image_light"] = light_image
                mw.col.conf["modern_menu_sidebar_bg_image_dark"] = dark_image

            mw.col.conf["modern_menu_sidebar_slideshow_images"] = list(getattr(self, "sidebar_bg_slideshow_images", []))
            mw.col.conf["modern_menu_sidebar_slideshow_interval"] = self.sidebar_bg_slideshow_interval_spinbox.value()
            mw.col.conf["modern_menu_sidebar_bg_blur"] = self.sidebar_bg_blur_slider.value()
            mw.col.conf["modern_menu_sidebar_bg_opacity"] = self.sidebar_bg_opacity_slider.value()
            mw.col.conf["modern_menu_sidebar_bg_transparency"] = 0
            if hasattr(self, "sidebar_bg_radius_slider"):
                mw.col.conf["modern_menu_sidebar_radius"] = self.sidebar_bg_radius_slider.value()
            if hasattr(self, "sidebar_bg_stroke_slider"):
                mw.col.conf["modern_menu_sidebar_stroke"] = self.sidebar_bg_stroke_slider.value()
            if hasattr(self, "sidebar_bg_margin_slider"):
                mw.col.conf["modern_menu_sidebar_margin"] = self.sidebar_bg_margin_slider.value()

            sync_box_toggle = getattr(self, "sidebar_bg_sync_box_toggle", None)
            sync_box_effect = bool(sync_box_toggle and sync_box_toggle.isChecked())
            mw.col.conf["modern_menu_sidebar_sync_box_effect"] = sync_box_effect
            if sync_box_effect:
                light_state = self._box_effect_state_for_sidebar_preview("light")
                dark_state = self._box_effect_state_for_sidebar_preview("dark")
                mw.col.conf["modern_menu_sidebar_bg_color_light"] = light_state["color"]
                mw.col.conf["modern_menu_sidebar_bg_color_dark"] = dark_state["color"]
                mw.col.conf["modern_menu_sidebar_bg_blur"] = light_state["blur"]
                mw.col.conf["modern_menu_sidebar_bg_opacity"] = light_state["opacity"]
                if hasattr(self, "box_effect_radius_slider"):
                    mw.col.conf["modern_menu_sidebar_radius"] = self.box_effect_radius_slider.value()
                if hasattr(self, "box_effect_stroke_slider"):
                    mw.col.conf["modern_menu_sidebar_stroke"] = self.box_effect_stroke_slider.value()
        else:
            if getattr(self, "sidebar_bg_custom_radio", None) and self.sidebar_bg_custom_radio.isChecked(): mw.col.conf["modern_menu_sidebar_bg_mode"] = "custom"
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
        """Saves the sidebar button layout. The Action Button Customization card
        is the source of truth (working layout); fall back to the legacy editor
        only if it somehow wasn't built."""
        working = getattr(self, "_sidebar_layout_working", None)
        if isinstance(working, dict):
            self.current_config["sidebarButtonLayout"] = copy.deepcopy(working)
        elif hasattr(self, 'sidebar_layout_editor'):
            self.current_config["sidebarButtonLayout"] = self.sidebar_layout_editor.get_layout_config()

