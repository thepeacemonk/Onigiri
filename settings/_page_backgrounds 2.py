# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *



class SyncBoxLockClickFilter(QObject):
    """Catches clicks landing on controls that Sync with Widget Color and Effect locked.

    A disabled widget swallows its own mouse events before its event filters run,
    and a QPushButton does not propagate the press to its parent either, so the
    application filter chain is the only place these clicks are still visible.
    """

    def __init__(self, page, prefix):
        super().__init__(page)
        self._page = page
        self._prefix = prefix

    def eventFilter(self, source, event):
        try:
            if event.type() == QEvent.Type.MouseButtonPress:
                self._page._handle_sync_box_lock_click(self._prefix, source)
        except Exception:
            pass
        return False


class PageBackgroundsMixin:
    def _main_bg_folder_path(self):
        path = os.path.join(self.addon_path, "user_files", "main_bg")
        os.makedirs(path, exist_ok=True)
        return path

    def _main_bg_image_files(self):
        try:
            return sorted([
                f for f in os.listdir(self._main_bg_folder_path())
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
            ])
        except OSError:
            return []

    def _main_bg_image_path(self, filename):
        return os.path.join(self._main_bg_folder_path(), filename) if filename else ""

    def _sanitize_main_background_slideshow_images(self, filenames=None):
        available = set(self._main_bg_image_files())
        cleaned = []
        for filename in filenames or []:
            if filename in available and filename not in cleaned:
                cleaned.append(filename)
        return cleaned

    def _create_main_bg_button(self, text):
        palette = self._settings_palette()
        bg = palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        hover = palette.get("--canvas-inset", "#2b3544" if theme_manager.night_mode else "#ffffff")
        fg = palette.get("--fg", "#f9fafb" if theme_manager.night_mode else "#111827")
        muted = palette.get("--fg-subtle", "#d1d5db" if theme_manager.night_mode else "#4b5563")
        border = palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")
        button = QPushButton(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(36)
        button.setObjectName("mainBackgroundButton")
        button.setStyleSheet(f"""
            QPushButton#mainBackgroundButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 0px 14px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#mainBackgroundButton:hover,
            QPushButton#mainBackgroundButton:pressed,
            QPushButton#mainBackgroundButton:checked {{
                background-color: {hover};
                color: {fg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            QPushButton#mainBackgroundButton:disabled {{
                background-color: {bg};
                color: {muted};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)
        return button

    def _create_main_bg_toggle_row(self, text, toggle):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        label = QLabel(text)
        label.setObjectName("mainBackgroundControlLabel")
        layout.addWidget(label, 1)
        layout.addWidget(toggle)
        return row

    def _create_main_bg_value_row(self, text, value_widget):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        label = QLabel(text)
        label.setObjectName("mainBackgroundControlLabel")
        label.setMinimumWidth(135)
        layout.addWidget(label)
        layout.addWidget(value_widget, 1)
        return row

    def _modern_bg_folder_path(self, spec):
        path = os.path.join(self.addon_path, spec["folder_rel"])
        os.makedirs(path, exist_ok=True)
        return path

    def _modern_bg_image_files(self, spec):
        try:
            return sorted([
                f for f in os.listdir(self._modern_bg_folder_path(spec))
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
            ])
        except OSError:
            return []

    def _modern_bg_image_path(self, spec, filename):
        return os.path.join(self._modern_bg_folder_path(spec), filename) if filename else ""

    def _sanitize_modern_bg_slideshow_images(self, spec, filenames=None):
        available = set(self._modern_bg_image_files(spec))
        cleaned = []
        for filename in filenames or []:
            if filename in available and filename not in cleaned:
                cleaned.append(filename)
        return cleaned

    def _create_modern_background_designer(self, spec):
        if not hasattr(self, "_modern_background_specs"):
            self._modern_background_specs = {}
        prefix = spec["prefix"]
        self._modern_background_specs[prefix] = spec

        mode = self._background_config_value(spec, spec["mode_key"], spec.get("default_mode", "color"))
        if mode == "image":
            mode = "image_color"
        allowed_modes = {"color", "accent", "image_color", "slideshow"}
        if spec.get("allow_main_sync"):
            allowed_modes.add("main")
        if mode not in allowed_modes:
            mode = spec.get("default_mode", "color")
        light_color = self._background_config_value(spec, spec["light_color_key"], spec.get("default_light", "#F3F3F3"))
        dark_color = self._background_config_value(spec, spec["dark_color_key"], spec.get("default_dark", "#2C2C2C"))
        color_theme_mode = self._background_config_value(spec, spec.get("color_theme_mode_key", ""), "separate")
        image_theme_mode = self._background_config_value(spec, spec.get("image_theme_mode_key", ""), spec.get("legacy_image_mode", "separate"))
        single_image = self._background_config_value(spec, spec["image_key"], "")
        light_image = self._background_config_value(spec, spec["image_light_key"], single_image)
        dark_image = self._background_config_value(spec, spec["image_dark_key"], single_image)

        gallery_base = spec["gallery_base"]
        single_key = f"{gallery_base}_single"
        light_key = f"{gallery_base}_light"
        dark_key = f"{gallery_base}_dark"
        self.galleries[single_key] = {"selected": single_image, "folder": spec["folder_rel"]}
        self.galleries[light_key] = {"selected": light_image, "folder": spec["folder_rel"]}
        self.galleries[dark_key] = {"selected": dark_image, "folder": spec["folder_rel"]}

        slideshow_images = self._sanitize_modern_bg_slideshow_images(
            spec,
            list(self._background_config_value(spec, spec["slideshow_images_key"], []) or [])
        )
        setattr(self, f"{prefix}_bg_slideshow_images", slideshow_images)
        setattr(self, f"{prefix}_bg_slideshow_index", 0)
        timer = QTimer(self)
        timer.timeout.connect(lambda p=prefix: self._advance_modern_background_slideshow_preview(p))
        setattr(self, f"{prefix}_bg_slideshow_preview_timer", timer)

        designer = QFrame()
        designer.setObjectName("mainBackgroundDesigner")
        is_sidebar_preview = spec.get("preview_shape") == "sidebar"
        designer_layout = QVBoxLayout(designer)
        designer_layout.setContentsMargins(18, 18, 18, 18)
        designer_layout.setSpacing(14)

        preview_mode_header = QHBoxLayout()
        preview_mode_header.setContentsMargins(0, 0, 0, 0)
        
        if "title" in spec:
            title_label = QLabel(spec["title"])
            title_label.setObjectName("sectionTitle")
            title_label.setWordWrap(True)
            preview_mode_header.addWidget(title_label)

        preview_mode_header.addStretch()
        setattr(self, f"{prefix}_bg_preview_mode", "dark" if theme_manager.night_mode else "light")
        mode_widget, mode_toggle = self._create_light_dark_mode_toggle(
            getattr(self, f"{prefix}_bg_preview_mode"),
            lambda mode, p=prefix: self._on_modern_background_preview_mode_toggled(p, mode),
        )
        setattr(self, f"{prefix}_bg_preview_mode_widget", mode_widget)
        setattr(self, f"{prefix}_bg_preview_mode_toggle", mode_toggle)
        preview_mode_header.addWidget(mode_widget)

        reset_button = QPushButton(tr("reset_bg_default"))
        reset_button.setObjectName("mainBackgroundResetButton")
        reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_button.setFixedHeight(34)
        reset_button.clicked.connect(lambda _=False, p=prefix: self._reset_modern_background_to_default(p))
        setattr(self, f"{prefix}_bg_reset_button", reset_button)
        if is_sidebar_preview:
            # Sit the reset button to the right of the light/dark toggle.
            reset_button.setMinimumWidth(160)
            reset_button.setMaximumWidth(240)
            preview_mode_header.addSpacing(10)
            preview_mode_header.addWidget(reset_button)

        designer_layout.addLayout(preview_mode_header)

        body = QWidget()
        outer = QHBoxLayout(body) if is_sidebar_preview else QVBoxLayout(body)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(24 if is_sidebar_preview else 14)
        designer_layout.addWidget(body)

        preview = BackgroundPreviewLabel(aspect_ratio=1.2, minimum_preview_height=500) if is_sidebar_preview else BackgroundPreviewLabel()
        preview.setObjectName("mainBackgroundPreview")
        if is_sidebar_preview:
            preview.setMinimumSize(320, 500)
        else:
            preview.setMinimumHeight(preview.heightForWidth(max(1, preview.width())))
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if is_sidebar_preview:
            preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview.setProperty("modern_bg_prefix", prefix)
        preview.installEventFilter(self)
        setattr(self, f"{prefix}_bg_preview", preview)
        if not is_sidebar_preview:
            outer.addWidget(preview)

        left = QWidget()
        left.setMinimumWidth(0)
        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        left_layout = QGridLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setHorizontalSpacing(10)
        left_layout.setVerticalSpacing(10)

        import_button = self._create_main_bg_button("Import")
        clear_button = self._create_main_bg_button("Clear image")
        gallery_button = self._create_main_bg_button("Select from your Gallery")
        light_color_button = self._create_main_bg_button("Color")
        light_color_value_button = self._create_main_bg_button("")
        light_color_value_button.setObjectName("mainBackgroundColorButton")
        dark_color_button = self._create_main_bg_button("Dark Color")
        dark_color_value_button = self._create_main_bg_button("")
        dark_color_value_button.setObjectName("mainBackgroundColorButton")
        light_color_card = self._create_color_selector_card(light_color_button, light_color_value_button)
        dark_color_card = self._create_color_selector_card(dark_color_button, dark_color_value_button)

        for name, widget in {
            "import_button": import_button,
            "clear_button": clear_button,
            "gallery_button": gallery_button,
            "light_color_button": light_color_button,
            "light_color_value_button": light_color_value_button,
            "light_color_card": light_color_card,
            "dark_color_button": dark_color_button,
            "dark_color_value_button": dark_color_value_button,
            "dark_color_card": dark_color_card,
        }.items():
            setattr(self, f"{prefix}_bg_{name}", widget)

        left_layout.addWidget(import_button, 0, 0)
        left_layout.addWidget(clear_button, 0, 1)
        left_layout.addWidget(gallery_button, 1, 0, 1, 2)
        color_stack = QStackedWidget()
        color_stack.addWidget(light_color_card)
        color_stack.addWidget(dark_color_card)
        setattr(self, f"{prefix}_bg_color_stack", color_stack)
        left_layout.addWidget(color_stack, 2, 0, 1, 2)

        slider_palette = self._settings_palette()
        slider_track = slider_palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = slider_palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")

        blur_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        blur_slider.setRange(0, 100)
        blur_key = spec.get("main_sync_blur_key") if mode == "main" and spec.get("main_sync_blur_key") else spec["blur_key"]
        opacity_key = spec.get("main_sync_opacity_key") if mode == "main" and spec.get("main_sync_opacity_key") else spec["opacity_key"]
        blur_slider.setValue(self._background_config_value(spec, blur_key, 0))
        blur_label = QLabel(f"{blur_slider.value()}%")
        blur_label.setObjectName("mainBackgroundValueLabel")
        blur_label.setFixedWidth(48)
        blur_value = QWidget()
        blur_layout = QHBoxLayout(blur_value)
        blur_layout.setContentsMargins(0, 0, 0, 0)
        blur_layout.setSpacing(10)
        blur_layout.addWidget(blur_slider, 1)
        blur_layout.addWidget(blur_label)

        opacity_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        opacity_slider.setRange(0, 100)
        opacity_slider.setValue(self._background_config_value(spec, opacity_key, 100))
        opacity_label = QLabel(f"{opacity_slider.value()}%")
        opacity_label.setObjectName("mainBackgroundValueLabel")
        opacity_label.setFixedWidth(48)
        opacity_value = QWidget()
        opacity_layout = QHBoxLayout(opacity_value)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(10)
        opacity_layout.addWidget(opacity_slider, 1)
        opacity_layout.addWidget(opacity_label)

        dynamic_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        slideshow_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        color_only_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        sync_main_toggle = AnimatedToggleButton(accent_color=self.accent_color) if spec.get("allow_main_sync") else None
        sync_box_toggle = AnimatedToggleButton(accent_color=self.accent_color) if is_sidebar_preview else None
        hide_profile_toggle = AnimatedToggleButton(accent_color=self.accent_color) if is_sidebar_preview else None
        dynamic_toggle.setChecked((mode in {"color", "accent"} and color_theme_mode == "separate") or (mode == "image_color" and image_theme_mode == "separate"))
        slideshow_toggle.setChecked(mode == "slideshow")
        color_only_toggle.setChecked(mode in {"color", "accent"})
        if sync_box_toggle:
            sync_box_toggle.setChecked(bool(mw.col.conf.get("modern_menu_sidebar_sync_box_effect", True)))
        if hide_profile_toggle:
            hide_profile_toggle.setChecked(bool(mw.col.conf.get("modern_menu_hide_profile_bar", False)))
        if sync_main_toggle:
            sync_main_toggle.setChecked(mode == "main")

        right = QWidget()
        right.setMinimumWidth(0)
        right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        if sync_main_toggle:
            sync_main_row = self._create_main_bg_toggle_row(tr("sync_main_menu_background"), sync_main_toggle)
            right_layout.addWidget(sync_main_row)

        if is_sidebar_preview:
            self.sidebar_position_group = QButtonGroup(self)
            self.sidebar_position_group.setExclusive(True)
            current_position = mw.col.conf.get(
                "modern_menu_sidebar_position",
                self.current_config.get("sidebarPosition", "left"),
            )
            if current_position not in {"left", "right", "center"}:
                current_position = "left"
            position_container = self._create_organize_segmented_control(
                [
                    ("left", tr("sidebar_position_left_short", "Left")),
                    ("center", tr("sidebar_position_center_short", "Center")),
                    ("right", tr("sidebar_position_right_short", "Right")),
                ],
                self.sidebar_position_group,
                current_position,
                "sidebar_position",
                fill_width=True,
                segment_height=28,
                min_button_width=62,
            )
            right_layout.addWidget(self._create_main_bg_value_row(tr("sidebar_position", "Sidebar position"), position_container))

            # Action buttons mode, same segmented design as Sidebar Position.
            self.sidebar_actions_mode_group = QButtonGroup(self)
            self.sidebar_actions_mode_group.setExclusive(True)
            current_actions_mode = self.current_config.get("sidebarActionsMode", "list")
            if current_actions_mode not in {"list", "collapsed", "archived"}:
                current_actions_mode = "list"
            actions_mode_container = self._create_organize_segmented_control(
                [
                    ("list", tr("list_default_short", "List")),
                    ("collapsed", tr("collapsed_toolbar_short", "Collapsed")),
                    ("archived", tr("archived_hidden_short", "Hidden")),
                ],
                self.sidebar_actions_mode_group,
                current_actions_mode,
                "sidebar_actions_mode",
                fill_width=True,
                segment_height=28,
                min_button_width=62,
            )
            right_layout.addWidget(self._create_main_bg_value_row(tr("action_buttons_label", "Action Buttons"), actions_mode_container))

        right_layout.addWidget(self._create_main_bg_value_row("Blur Intensity", blur_value))
        right_layout.addWidget(self._create_main_bg_value_row("Opacity", opacity_value))

        if is_sidebar_preview:
            def make_sidebar_frame_slider(attr, value_key, default, minimum, maximum, suffix):
                slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
                slider.setRange(minimum, maximum)
                raw_value = mw.col.conf.get(value_key, default)
                try:
                    current_value = int(float(raw_value))
                except (TypeError, ValueError):
                    current_value = default
                slider.setValue(max(minimum, min(maximum, current_value)))
                value_label = QLabel(f"{slider.value()}{suffix}")
                value_label.setObjectName("mainBackgroundValueLabel")
                value_label.setFixedWidth(48)
                value_widget = QWidget()
                value_layout = QHBoxLayout(value_widget)
                value_layout.setContentsMargins(0, 0, 0, 0)
                value_layout.setSpacing(10)
                value_layout.addWidget(slider, 1)
                value_layout.addWidget(value_label)
                setattr(self, f"{prefix}_bg_{attr}_slider", slider)
                setattr(self, f"{prefix}_bg_{attr}_value_label", value_label)
                return value_widget

            radius_value = make_sidebar_frame_slider("radius", "modern_menu_sidebar_radius", 15, 0, 60, "px")
            stroke_value = make_sidebar_frame_slider("stroke", "modern_menu_sidebar_stroke", 1, 0, 10, "px")
            margin_value = make_sidebar_frame_slider("margin", "modern_menu_sidebar_margin", 10, 0, 48, "px")
            right_layout.addWidget(self._create_main_bg_value_row(tr("radius", "Radius"), radius_value))
            right_layout.addWidget(self._create_main_bg_value_row(tr("stroke", "Stroke"), stroke_value))
            right_layout.addWidget(self._create_main_bg_value_row(tr("margin", "Margin"), margin_value))

        if sync_box_toggle:
            right_layout.addWidget(self._create_main_bg_toggle_row(tr("sync_box_color_effect", "Sync with Widget Color and Effect"), sync_box_toggle))
        if hide_profile_toggle:
            right_layout.addWidget(self._create_main_bg_toggle_row(tr("hide_profile_sidebar", "Hide profile on sidebar"), hide_profile_toggle))
        right_layout.addWidget(self._create_main_bg_toggle_row("Dynamic mode", dynamic_toggle))
        right_layout.addWidget(self._create_main_bg_toggle_row("Slideshow", slideshow_toggle))
        interval_spinbox = QSpinBox()
        interval_spinbox.setRange(1, 3600)
        interval_spinbox.setSuffix(" sec")
        interval_spinbox.setValue(int(self._background_config_value(spec, spec["slideshow_interval_key"], 10) or 10))
        interval_row = self._create_main_bg_value_row("Change every", interval_spinbox)
        right_layout.addWidget(interval_row)
        right_layout.addWidget(self._create_main_bg_toggle_row("Color only", color_only_toggle))
        right_layout.addStretch()

        for name, widget in {
            "blur_slider": blur_slider,
            "blur_value_label": blur_label,
            "opacity_slider": opacity_slider,
            "opacity_value_label": opacity_label,
            "dynamic_toggle": dynamic_toggle,
            "slideshow_toggle": slideshow_toggle,
            "color_only_toggle": color_only_toggle,
            "slideshow_interval_spinbox": interval_spinbox,
            "slideshow_interval_row": interval_row,
        }.items():
            setattr(self, f"{prefix}_bg_{name}", widget)
        if sync_main_toggle:
            setattr(self, f"{prefix}_bg_sync_main_toggle", sync_main_toggle)
            setattr(self, f"{prefix}_bg_sync_main_row", sync_main_row)
        if sync_box_toggle:
            setattr(self, f"{prefix}_bg_sync_box_toggle", sync_box_toggle)
        if hide_profile_toggle:
            setattr(self, f"{prefix}_bg_hide_profile_toggle", hide_profile_toggle)

        controls_pair = ResponsivePairWidget(left, right, spacing=18, breakpoint=720)
        if is_sidebar_preview:
            # The reset button already lives in the header next to the toggle.
            controls_shell = QWidget()
            controls_shell.setMinimumWidth(0)
            controls_shell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            controls_shell_layout = QVBoxLayout(controls_shell)
            controls_shell_layout.setContentsMargins(0, 0, 0, 0)
            controls_shell_layout.setSpacing(18)
            controls_shell_layout.addWidget(controls_pair)
            controls_shell_layout.addStretch()
            outer.addWidget(preview, 4)
            outer.addWidget(controls_shell, 6)
        else:
            outer.addWidget(controls_pair)
            reset_button.setMinimumWidth(220)
            reset_button.setMaximumWidth(280)
            reset_row = QWidget()
            reset_row_layout = QHBoxLayout(reset_row)
            reset_row_layout.setContentsMargins(0, 0, 0, 0)
            reset_row_layout.addStretch()
            reset_row_layout.addWidget(reset_button)
            reset_row_layout.addStretch()
            outer.addWidget(reset_row)

        light_input = QLineEdit(light_color)
        dark_input = QLineEdit(dark_color)
        setattr(self, f"{prefix}_bg_light_color_input", light_input)
        setattr(self, f"{prefix}_bg_single_color_input", light_input)
        setattr(self, f"{prefix}_bg_dark_color_input", dark_input)

        import_button.clicked.connect(lambda _=False, p=prefix: self._import_modern_background(p))
        clear_button.clicked.connect(lambda _=False, p=prefix: self._clear_modern_background(p))
        gallery_button.clicked.connect(lambda _=False, p=prefix: self._open_modern_background_gallery(p))
        light_color_button.clicked.connect(lambda _=False, p=prefix: self._choose_modern_background_color(p, "light"))
        light_color_value_button.clicked.connect(lambda _=False, p=prefix: self._choose_modern_background_color(p, "light"))
        dark_color_button.clicked.connect(lambda _=False, p=prefix: self._choose_modern_background_color(p, "dark"))
        dark_color_value_button.clicked.connect(lambda _=False, p=prefix: self._choose_modern_background_color(p, "dark"))
        dynamic_toggle.toggled.connect(lambda checked, p=prefix: self._on_modern_background_mode_changed(p, checked))
        slideshow_toggle.toggled.connect(lambda checked, p=prefix: self._on_modern_background_mode_changed(p, checked))
        color_only_toggle.toggled.connect(lambda checked, p=prefix: self._on_modern_background_mode_changed(p, checked))
        if sync_main_toggle:
            sync_main_toggle.toggled.connect(lambda checked, p=prefix: self._on_modern_background_mode_changed(p, checked))
        if sync_box_toggle:
            sync_box_toggle.toggled.connect(lambda checked, p=prefix: self._update_modern_background_controls(p))
        interval_spinbox.valueChanged.connect(lambda value, p=prefix: self._sync_modern_background_slideshow_preview_timer(p))
        blur_slider.valueChanged.connect(lambda value, p=prefix: self._on_modern_background_effect_changed(p))
        opacity_slider.valueChanged.connect(lambda value, p=prefix: self._on_modern_background_effect_changed(p))
        if is_sidebar_preview:
            for attr in ("radius", "stroke", "margin"):
                getattr(self, f"{prefix}_bg_{attr}_slider").valueChanged.connect(
                    lambda value, p=prefix: self._on_sidebar_frame_effect_changed(p)
                )
            self.sidebar_position_group.buttonToggled.connect(
                lambda button, checked, p=prefix: self._update_modern_background_preview(p) if checked else None
            )
            self.sidebar_actions_mode_group.buttonToggled.connect(
                lambda button, checked, p=prefix: self._on_sidebar_actions_mode_changed(p) if checked else None
            )
        for line_edit in (light_input, dark_input):
            line_edit.textChanged.connect(lambda _=None, p=prefix: self._update_modern_background_preview(p))

        if sync_box_toggle:
            self._install_sync_box_lock_click_filter(prefix)

        if is_sidebar_preview:
            # Markers menu lives inside the Sidebar Customization container,
            # below the preview.
            markers_divider = QFrame()
            markers_divider.setFrameShape(QFrame.Shape.HLine)
            markers_divider.setFrameShadow(QFrame.Shadow.Sunken)
            designer_layout.addWidget(markers_divider)
            designer_layout.addWidget(self._create_sidebar_markers_widget())

        self._update_modern_background_controls(prefix)
        return designer

    def _install_sync_box_lock_click_filter(self, prefix):
        filters = getattr(self, "_sync_box_lock_filters", None)
        if filters is None:
            filters = {}
            self._sync_box_lock_filters = filters
        if prefix in filters:
            return
        app = QApplication.instance()
        if app is None:
            return
        # Parented to the dialog so Qt drops the filter when the page goes away.
        lock_filter = SyncBoxLockClickFilter(self, prefix)
        app.installEventFilter(lock_filter)
        filters[prefix] = lock_filter

    def _sync_box_locked_widgets(self, prefix):
        names = (
            "import_button", "clear_button", "gallery_button",
            "light_color_card", "dark_color_card",
            "light_color_button", "light_color_value_button",
            "dark_color_button", "dark_color_value_button",
            "dynamic_toggle", "slideshow_toggle", "color_only_toggle",
            "blur_slider", "opacity_slider", "radius_slider", "stroke_slider",
        )
        widgets = []
        for name in names:
            widget = getattr(self, f"{prefix}_bg_{name}", None)
            if widget is not None:
                widgets.append(widget)
        return widgets

    def _handle_sync_box_lock_click(self, prefix, source):
        toggle = getattr(self, f"{prefix}_bg_sync_box_toggle", None)
        if toggle is None or not isinstance(source, QWidget):
            return
        try:
            if sip is not None and (sip.isdeleted(toggle) or sip.isdeleted(source)):
                return
        except Exception:
            return
        if not toggle.isVisible() or not toggle.isChecked():
            return
        locked = self._sync_box_locked_widgets(prefix)
        widget = source
        while widget is not None:
            if any(widget is candidate for candidate in locked):
                toggle.shake()
                return
            widget = widget.parentWidget()

    def _modern_background_spec(self, prefix):
        return getattr(self, "_modern_background_specs", {}).get(prefix)

    def _modern_background_gallery_keys(self, spec):
        base = spec["gallery_base"]
        return f"{base}_single", f"{base}_light", f"{base}_dark"

    def _modern_background_preview_mode(self, prefix):
        return getattr(self, f"{prefix}_bg_preview_mode", "dark" if theme_manager.night_mode else "light")

    def _on_modern_background_preview_mode_toggled(self, prefix, mode):
        setattr(self, f"{prefix}_bg_preview_mode", "dark" if mode == "dark" else "light")
        self._update_modern_background_controls(prefix)

    def _modern_background_active_color_input(self, prefix):
        if getattr(self, f"{prefix}_bg_dynamic_toggle").isChecked():
            return getattr(self, f"{prefix}_bg_dark_color_input") if theme_manager.night_mode else getattr(self, f"{prefix}_bg_light_color_input")
        return getattr(self, f"{prefix}_bg_single_color_input")

    def _modern_background_active_image(self, prefix):
        spec = self._modern_background_spec(prefix)
        single_key, light_key, dark_key = self._modern_background_gallery_keys(spec)
        if getattr(self, f"{prefix}_bg_slideshow_toggle").isChecked():
            images = getattr(self, f"{prefix}_bg_slideshow_images")
            if not images:
                return ""
            index = getattr(self, f"{prefix}_bg_slideshow_index") % len(images)
            setattr(self, f"{prefix}_bg_slideshow_index", index)
            return images[index]
        if getattr(self, f"{prefix}_bg_dynamic_toggle").isChecked():
            key = dark_key if theme_manager.night_mode else light_key
            return self.galleries.get(key, {}).get("selected", "")
        return self.galleries.get(single_key, {}).get("selected", "")

    def _modern_background_color_for_input(self, line_edit, fallback="#ffffff"):
        color = line_edit.text() if line_edit else fallback
        return color if QColor(color).isValid() else fallback

    def _style_modern_background_color_button(self, button, color):
        self._style_main_background_color_button(button, color)

    def _on_modern_background_mode_changed(self, prefix, checked):
        sender = self.sender()
        color_only_toggle = getattr(self, f"{prefix}_bg_color_only_toggle")
        slideshow_toggle = getattr(self, f"{prefix}_bg_slideshow_toggle")
        dynamic_toggle = getattr(self, f"{prefix}_bg_dynamic_toggle")
        sync_main_toggle = getattr(self, f"{prefix}_bg_sync_main_toggle", None)
        if sender is color_only_toggle and checked:
            slideshow_toggle.setChecked(False)
            if sync_main_toggle:
                sync_main_toggle.setChecked(False)
        elif sender is slideshow_toggle and checked:
            color_only_toggle.setChecked(False)
            if sync_main_toggle:
                sync_main_toggle.setChecked(False)
        elif sender is dynamic_toggle and checked:
            if sync_main_toggle:
                sync_main_toggle.setChecked(False)
        elif sync_main_toggle and sender is sync_main_toggle and checked:
            slideshow_toggle.setChecked(False)
        self._update_modern_background_controls(prefix)

    def _update_modern_background_controls(self, prefix):
        sync_main_toggle = getattr(self, f"{prefix}_bg_sync_main_toggle", None)
        sync_main = bool(sync_main_toggle and sync_main_toggle.isChecked())
        color_only = getattr(self, f"{prefix}_bg_color_only_toggle").isChecked()
        dynamic = getattr(self, f"{prefix}_bg_dynamic_toggle").isChecked()
        for button_name in ("import_button", "clear_button", "gallery_button"):
            getattr(self, f"{prefix}_bg_{button_name}").setEnabled(not color_only and not sync_main)
        getattr(self, f"{prefix}_bg_light_color_button").setText("Light Color" if dynamic else "Color")
        mode_widget = getattr(self, f"{prefix}_bg_preview_mode_widget", None)
        if mode_widget:
            mode_widget.setEnabled(dynamic)
            mode_widget.setToolTip("" if dynamic else "Enable Dynamic mode to switch light/dark palettes.")
        for name in ("light_color_button", "light_color_value_button", "dark_color_button", "dark_color_value_button"):
            getattr(self, f"{prefix}_bg_{name}").setVisible(not sync_main)
        color_stack = getattr(self, f"{prefix}_bg_color_stack", None)
        show_dark = dynamic and self._modern_background_preview_mode(prefix) == "dark"
        if color_stack:
            color_stack.setVisible(not sync_main)
            color_stack.setCurrentIndex(1 if show_dark else 0)
        else:
            getattr(self, f"{prefix}_bg_light_color_card").setVisible(not sync_main and not show_dark)
            getattr(self, f"{prefix}_bg_dark_color_card").setVisible(not sync_main and show_dark)
        for name in ("dynamic_toggle", "slideshow_toggle", "color_only_toggle"):
            getattr(self, f"{prefix}_bg_{name}").setEnabled(not sync_main)
        interval_row = getattr(self, f"{prefix}_bg_slideshow_interval_row")
        interval_visible = getattr(self, f"{prefix}_bg_slideshow_toggle").isChecked() and not color_only and not sync_main
        interval_row.setVisible(interval_visible)
        getattr(self, f"{prefix}_bg_slideshow_interval_spinbox").setEnabled(interval_visible)

        sync_box_toggle = getattr(self, f"{prefix}_bg_sync_box_toggle", None)
        if sync_box_toggle is not None:
            sync_box = sync_box_toggle.isChecked()
            for button_name in ("import_button", "clear_button", "gallery_button"):
                button = getattr(self, f"{prefix}_bg_{button_name}")
                button.setEnabled(button.isEnabled() and not sync_box)
            for name in (
                "light_color_button", "light_color_value_button",
                "dark_color_button", "dark_color_value_button",
            ):
                getattr(self, f"{prefix}_bg_{name}").setEnabled(not sync_box)
            for name in ("dynamic_toggle", "slideshow_toggle", "color_only_toggle"):
                toggle = getattr(self, f"{prefix}_bg_{name}")
                toggle.setEnabled(toggle.isEnabled() and not sync_box)
            for attr in ("blur_slider", "opacity_slider", "radius_slider", "stroke_slider"):
                slider = getattr(self, f"{prefix}_bg_{attr}", None)
                if slider:
                    slider.setEnabled(not sync_box)

        self._update_modern_background_preview(prefix)
        self._sync_modern_background_slideshow_preview_timer(prefix)

    def _on_modern_background_effect_changed(self, prefix):
        getattr(self, f"{prefix}_bg_blur_value_label").setText(f"{getattr(self, f'{prefix}_bg_blur_slider').value()}%")
        getattr(self, f"{prefix}_bg_opacity_value_label").setText(f"{getattr(self, f'{prefix}_bg_opacity_slider').value()}%")
        self._update_modern_background_preview(prefix)

    def _modern_background_slideshow_interval_ms(self, prefix):
        spinbox = getattr(self, f"{prefix}_bg_slideshow_interval_spinbox")
        return max(1, int(spinbox.value())) * 1000

    def _sync_modern_background_slideshow_preview_timer(self, prefix):
        timer = getattr(self, f"{prefix}_bg_slideshow_preview_timer", None)
        if not timer:
            return
        should_run = (
            getattr(self, f"{prefix}_bg_slideshow_toggle").isChecked()
            and not getattr(self, f"{prefix}_bg_color_only_toggle").isChecked()
            and not bool(getattr(self, f"{prefix}_bg_sync_main_toggle", None) and getattr(self, f"{prefix}_bg_sync_main_toggle").isChecked())
            and len(getattr(self, f"{prefix}_bg_slideshow_images")) > 1
        )
        if should_run:
            timer.start(self._modern_background_slideshow_interval_ms(prefix))
        else:
            timer.stop()

    def _advance_modern_background_slideshow_preview(self, prefix):
        spec = self._modern_background_spec(prefix)
        images = self._sanitize_modern_bg_slideshow_images(spec, getattr(self, f"{prefix}_bg_slideshow_images"))
        setattr(self, f"{prefix}_bg_slideshow_images", images)
        if not images:
            setattr(self, f"{prefix}_bg_slideshow_index", 0)
            self._update_modern_background_preview(prefix)
            return
        setattr(self, f"{prefix}_bg_slideshow_index", (getattr(self, f"{prefix}_bg_slideshow_index") + 1) % len(images))
        self._update_modern_background_preview(prefix)

    def _modern_background_cover_image(self, prefix, image_path, width, height):
        source = QImage(image_path)
        if source.isNull():
            return QPixmap()
        scaled = source.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        x = max(0, (scaled.width() - width) // 2)
        y = max(0, (scaled.height() - height) // 2)
        pixmap = QPixmap.fromImage(scaled.copy(x, y, width, height))
        blur = getattr(self, f"{prefix}_bg_blur_slider").value()
        if blur > 0:
            return self._qt_blurred_pixmap(pixmap, float(blur) / 3.0)
        return pixmap

    def _render_modern_background_preview_pixmap(self, prefix, color, image_path):
        return self._render_modern_background_state_preview_pixmap(prefix, {
            "color": color,
            "image_path": image_path,
            "blur": getattr(self, f"{prefix}_bg_blur_slider").value(),
            "opacity": getattr(self, f"{prefix}_bg_opacity_slider").value(),
        })

    def _render_modern_background_state_preview_pixmap(self, prefix, state):
        preview = getattr(self, f"{prefix}_bg_preview")
        size = preview.size()
        width = max(1, size.width())
        height = max(1, size.height())
        color = state.get("color", "#f2f2f2")
        image_path = state.get("image_path", "")
        blur = int(state.get("blur", 0) or 0)
        raw_opacity = state.get("opacity", 100)
        opacity = int(raw_opacity if raw_opacity is not None else 100)
        dpr = max(1.0, preview.devicePixelRatioF())
        target = QPixmap(int(width * dpr), int(height * dpr))
        target.setDevicePixelRatio(dpr)
        target.fill(Qt.GlobalColor.transparent)
        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = QRectF(1, 1, width - 2, height - 2)
        path = QPainterPath()
        path.addRoundedRect(rect, 22, 22)

        if prefix == "sidebar":
            painter.setClipPath(path)
            background = QPixmap(width, height)
            background.fill(Qt.GlobalColor.transparent)
            bg_painter = QPainter(background)
            bg_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            bg_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            self._draw_box_effect_background_layer(
                bg_painter,
                QRectF(0, 0, width, height),
                self._modern_background_preview_mode(prefix),
            )
            bg_painter.end()
            painter.drawPixmap(0, 0, background)

            margin = max(0, int(getattr(self, f"{prefix}_bg_margin_slider", None).value() if hasattr(self, f"{prefix}_bg_margin_slider") else 10))
            sync_box = bool(getattr(self, f"{prefix}_bg_sync_box_toggle", None) and getattr(self, f"{prefix}_bg_sync_box_toggle").isChecked())
            if sync_box and hasattr(self, "box_effect_radius_slider"):
                radius = max(0, int(self.box_effect_radius_slider.value()))
            else:
                radius = max(0, int(getattr(self, f"{prefix}_bg_radius_slider", None).value() if hasattr(self, f"{prefix}_bg_radius_slider") else 15))
            if sync_box and hasattr(self, "box_effect_stroke_slider"):
                stroke_width = max(0, int(self.box_effect_stroke_slider.value()))
            else:
                stroke_width = max(0, int(getattr(self, f"{prefix}_bg_stroke_slider", None).value() if hasattr(self, f"{prefix}_bg_stroke_slider") else 1))
            available = rect.adjusted(margin, margin, -margin, -margin)
            checked_position = self.sidebar_position_group.checkedButton() if hasattr(self, "sidebar_position_group") else None
            sidebar_position = checked_position.property("sidebar_position") if checked_position else "left"
            if sidebar_position not in {"left", "right", "center"}:
                sidebar_position = "left"
            if sidebar_position == "center":
                # Centered layout: the sidebar is a floating card at the top
                # holding the whole menu (profile + actions + decks); the main
                # content widgets (stat cards + activity) sit below it.
                card_width = min(available.width(), max(180.0, available.width() * 0.58))
                card_height = min(available.height(), max(120.0, available.height() * 0.6))
                sidebar_rect = QRectF(
                    available.center().x() - card_width / 2,
                    available.top(),
                    card_width,
                    card_height,
                )
            else:
                sidebar_width = min(max(150.0, available.width() * 0.62), available.width())
                sidebar_x = available.right() - sidebar_width if sidebar_position == "right" else available.left()
                sidebar_rect = QRectF(
                    sidebar_x,
                    available.top(),
                    sidebar_width,
                    max(1.0, available.height()),
                )
            sidebar_path = QPainterPath()
            sidebar_path.addRoundedRect(sidebar_rect, radius, radius)

            painter.save()
            painter.setClipPath(sidebar_path, Qt.ClipOperation.IntersectClip)
            if blur > 0 and not background.isNull():
                blurred_background = self._qt_blurred_pixmap(background, float(blur) / 3.0)
                if not blurred_background.isNull():
                    painter.drawPixmap(0, 0, blurred_background)
            sidebar_color = QColor(color)
            sidebar_color.setAlphaF(max(0.0, min(1.0, opacity / 100.0)))
            painter.fillPath(sidebar_path, QBrush(sidebar_color))
            if image_path:
                image = self._background_cover_image_with_effect(
                    image_path,
                    max(1, int(sidebar_rect.width())),
                    max(1, int(sidebar_rect.height())),
                    blur,
                )
                if not image.isNull():
                    painter.setOpacity(max(0.0, min(1.0, opacity / 100.0)))
                    painter.drawPixmap(int(sidebar_rect.x()), int(sidebar_rect.y()), image)
                    painter.setOpacity(1.0)
            preview_mode = self._modern_background_preview_mode(prefix)
            self._draw_sidebar_preview_mockup(painter, sidebar_rect, preview_mode)
            painter.restore()

            if stroke_width > 0:
                border_color = QColor(self.current_config.get("colors", {}).get(
                    self._modern_background_preview_mode(prefix),
                    {},
                ).get("--border", "#4b5563" if theme_manager.night_mode else "#d1d5db"))
                sidebar_pen = QPen(border_color)
                sidebar_pen.setWidth(stroke_width)
                painter.setPen(sidebar_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(sidebar_path)

            if sidebar_position == "center":
                widgets_top = sidebar_rect.bottom() + max(8.0, available.height() * 0.025)
                widgets_rect = QRectF(
                    available.x(),
                    widgets_top,
                    available.width(),
                    max(0.0, available.bottom() - widgets_top),
                )
                if widgets_rect.height() > 20:
                    self._draw_sidebar_preview_center_widgets(painter, widgets_rect, preview_mode)

            painter.setClipping(False)
            painter.setPen(QPen(QColor("#4b5563" if theme_manager.night_mode else "#d1d5db"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            painter.end()
            return target

        painter.setClipPath(path)
        painter.fillPath(path, QBrush(QColor(color)))
        if image_path:
            image = self._background_cover_image_with_effect(image_path, width, height, blur)
            if not image.isNull():
                painter.setOpacity(max(0.0, min(1.0, opacity / 100.0)))
                painter.drawPixmap(0, 0, image)
                painter.setOpacity(1.0)
        painter.setClipping(False)
        painter.setPen(QPen(QColor("#4b5563" if theme_manager.night_mode else "#d1d5db"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()
        return target

    def _update_modern_background_preview(self, prefix):
        spec = self._modern_background_spec(prefix)
        if not spec or not hasattr(self, f"{prefix}_bg_preview"):
            return
        mode = self._modern_background_preview_mode(prefix)
        sync_box_toggle = getattr(self, f"{prefix}_bg_sync_box_toggle", None)
        if sync_box_toggle and sync_box_toggle.isChecked():
            state = self._box_effect_state_for_sidebar_preview(mode)
            pixmap = self._render_modern_background_state_preview_pixmap(prefix, state)
            preview = getattr(self, f"{prefix}_bg_preview")
            preview.setStyleSheet("QLabel#mainBackgroundPreview { background: transparent; border: none; }")
            preview.setPixmap(pixmap)
            preview.setText("")
            if prefix == "sidebar" and hasattr(self, "deck_icon_preview"):
                self._update_deck_icon_preview()
            if prefix == "sidebar" and hasattr(self, "actionbtns_preview"):
                self._update_action_buttons_preview()
            return
        sync_main_toggle = getattr(self, f"{prefix}_bg_sync_main_toggle", None)
        if sync_main_toggle and sync_main_toggle.isChecked():
            state = self._main_background_state_for_box_preview(mode)
            state["blur"] = getattr(self, f"{prefix}_bg_blur_slider").value()
            state["opacity"] = getattr(self, f"{prefix}_bg_opacity_slider").value()
            pixmap = self._render_modern_background_state_preview_pixmap(prefix, state)
            preview = getattr(self, f"{prefix}_bg_preview")
            preview.setStyleSheet("QLabel#mainBackgroundPreview { background: transparent; border: none; }")
            preview.setPixmap(pixmap)
            preview.setText("" if state.get("image_path") else "")
            if prefix == "overview" and hasattr(self, "overview_style_preview"):
                self._update_overview_style_preview()
            if prefix == "reviewer" and hasattr(self, "bottom_bar_preview"):
                self._update_reviewer_bottom_bar_preview()
            if prefix == "sidebar" and hasattr(self, "deck_icon_preview"):
                self._update_deck_icon_preview()
            if prefix == "sidebar" and hasattr(self, "actionbtns_preview"):
                self._update_action_buttons_preview()
            return
        single_key, light_key, dark_key = self._modern_background_gallery_keys(spec)
        single_color = self._modern_background_color_for_input(getattr(self, f"{prefix}_bg_single_color_input"))
        light_color = self._modern_background_color_for_input(getattr(self, f"{prefix}_bg_light_color_input"), single_color)
        dark_color = self._modern_background_color_for_input(getattr(self, f"{prefix}_bg_dark_color_input"), single_color)
        self._style_modern_background_color_button(getattr(self, f"{prefix}_bg_light_color_value_button"), light_color)
        self._style_modern_background_color_button(getattr(self, f"{prefix}_bg_dark_color_value_button"), dark_color)
        preview = getattr(self, f"{prefix}_bg_preview")
        preview.setStyleSheet("QLabel#mainBackgroundPreview { background: transparent; border: none; }")
        images = self._sanitize_modern_bg_slideshow_images(spec, getattr(self, f"{prefix}_bg_slideshow_images"))
        setattr(self, f"{prefix}_bg_slideshow_images", images)
        if getattr(self, f"{prefix}_bg_slideshow_index") >= len(images):
            setattr(self, f"{prefix}_bg_slideshow_index", 0)

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
        pixmap = self._render_modern_background_preview_pixmap(prefix, active_color, image_path if image_name and os.path.exists(image_path) else "")
        text = "" if image_name or color_only else "No background selected"
        preview.setPixmap(pixmap)
        preview.setText(text)
        if prefix == "overview" and hasattr(self, "overview_style_preview"):
            self._update_overview_style_preview()
        if prefix == "reviewer" and hasattr(self, "bottom_bar_preview"):
            self._update_reviewer_bottom_bar_preview()
        if prefix == "sidebar" and hasattr(self, "deck_icon_preview"):
            self._update_deck_icon_preview()
        if prefix == "sidebar" and hasattr(self, "actionbtns_preview"):
            self._update_action_buttons_preview()

    def _choose_modern_background_color(self, prefix, target="single"):
        if target == "light":
            line_edit = getattr(self, f"{prefix}_bg_light_color_input")
        elif target == "dark":
            line_edit = getattr(self, f"{prefix}_bg_dark_color_input")
        else:
            line_edit = getattr(self, f"{prefix}_bg_single_color_input")
        chosen, ok = OnigiriColorDialog.getColor(line_edit.text(), self, anchor=self.sender() if isinstance(self.sender(), QWidget) else None)
        if ok:
            line_edit.setText(chosen)
            self._update_modern_background_preview(prefix)

    def _import_modern_background(self, prefix):
        spec = self._modern_background_spec(prefix)
        filepath, _ = QFileDialog.getOpenFileName(self, tr("import_image"), "", "Images (*.png *.jpg *.jpeg *.gif *.webp)")
        if not filepath:
            return
        filename = os.path.basename(filepath)
        dest_path = os.path.join(self._modern_bg_folder_path(spec), filename)
        base, ext = os.path.splitext(filename)
        index = 2
        while os.path.exists(dest_path) and os.path.abspath(filepath) != os.path.abspath(dest_path):
            filename = f"{base}-{index}{ext}"
            dest_path = os.path.join(self._modern_bg_folder_path(spec), filename)
            index += 1
        try:
            if os.path.abspath(filepath) != os.path.abspath(dest_path):
                shutil.copy(filepath, dest_path)
            self._assign_modern_background_image(prefix, filename)
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not import image: {exc}")

    def _clear_modern_background(self, prefix):
        spec = self._modern_background_spec(prefix)
        single_key, light_key, dark_key = self._modern_background_gallery_keys(spec)
        if getattr(self, f"{prefix}_bg_slideshow_toggle").isChecked():
            setattr(self, f"{prefix}_bg_slideshow_images", [])
            setattr(self, f"{prefix}_bg_slideshow_index", 0)
        elif getattr(self, f"{prefix}_bg_dynamic_toggle").isChecked():
            self.galleries[light_key]["selected"] = ""
            self.galleries[dark_key]["selected"] = ""
        else:
            self.galleries[single_key]["selected"] = ""
        self._update_modern_background_preview(prefix)
        self._sync_modern_background_slideshow_preview_timer(prefix)

    def _assign_modern_background_image(self, prefix, filename, target=None):
        spec = self._modern_background_spec(prefix)
        single_key, light_key, dark_key = self._modern_background_gallery_keys(spec)
        if getattr(self, f"{prefix}_bg_slideshow_toggle").isChecked():
            images = self._sanitize_modern_bg_slideshow_images(spec, getattr(self, f"{prefix}_bg_slideshow_images"))
            if filename not in images:
                images.append(filename)
            setattr(self, f"{prefix}_bg_slideshow_images", images)
            setattr(self, f"{prefix}_bg_slideshow_index", max(0, min(getattr(self, f"{prefix}_bg_slideshow_index"), len(images) - 1)))
        elif getattr(self, f"{prefix}_bg_dynamic_toggle").isChecked():
            key = target or (dark_key if self._modern_background_preview_mode(prefix) == "dark" else light_key)
            self.galleries[key]["selected"] = filename
        else:
            self.galleries[single_key]["selected"] = filename
        self._update_modern_background_preview(prefix)
        self._sync_modern_background_slideshow_preview_timer(prefix)

    def _background_gallery_icon_paths(self):
        return {
            "light": system_icon_path("sun.svg"),
            "dark": system_icon_path("moon.svg"),
        }

    def _background_gallery_dialog_colors(self):
        palette = self._settings_palette()
        return {
            "bg": palette.get("--canvas", "#202226" if theme_manager.night_mode else "#f7f8fa"),
            "content": palette.get("--canvas", "#202226" if theme_manager.night_mode else "#f7f8fa"),
            "hint_bg": palette.get("--highlight-bg", "#282d34" if theme_manager.night_mode else "#ffffff"),
            "border": palette.get("--border", "#3a414b" if theme_manager.night_mode else "#dfe3e8"),
            "fg": palette.get("--fg", "#f4f4f5" if theme_manager.night_mode else "#111827"),
            "muted": palette.get("--fg-subtle", "#c9ced6" if theme_manager.night_mode else "#4b5563"),
        }

    def _style_background_gallery_dialog(self, dialog):
        colors = self._background_gallery_dialog_colors()
        # QPushButton has no rule of its own by default, so the "Done" button
        # renders with plain OS chrome — a jarring native-grey button inside
        # an otherwise fully custom-painted dark dialog. Style it to match
        # the accent-filled, rounded buttons used everywhere else.
        accent = QColor(self.accent_color)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors["bg"]};
                color: {colors["fg"]};
            }}
            QScrollArea {{
                background-color: {colors["bg"]};
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 4px 0 4px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {colors["border"]};
                border-radius: 4px;
                min-height: 24px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QWidget#backgroundGalleryContent {{
                background-color: {colors["content"]};
            }}
            QFrame#backgroundGalleryHint {{
                background-color: {colors["hint_bg"]};
                border: 1px solid {colors["border"]};
                border-radius: 8px;
            }}
            QLabel#backgroundGalleryHintText {{
                color: {colors["fg"]};
                font-weight: 600;
            }}
            QLabel#backgroundGalleryHintKey {{
                color: {colors["muted"]};
                font-weight: 800;
            }}
            QLabel#backgroundGalleryEmpty {{
                color: {colors["muted"]};
                font-size: 13px;
            }}
            QPushButton {{
                background-color: {accent.name()};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 7px 18px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {accent.lighter(112).name()};
            }}
            QPushButton:pressed {{
                background-color: {accent.darker(108).name()};
            }}
        """)

    def _create_background_gallery_hint_bar(self, mode):
        colors = self._background_gallery_dialog_colors()
        icon_paths = self._background_gallery_icon_paths()
        hint = QFrame()
        hint.setObjectName("backgroundGalleryHint")
        hint_layout = QHBoxLayout(hint)
        hint_layout.setContentsMargins(12, 8, 12, 8)
        hint_layout.setSpacing(8)

        if mode == "slideshow":
            text = "Hover over an image and press a number key (1-9) to set its position in the slideshow sequence."
            key_badge = QLabel("1-9")
            key_badge.setObjectName("backgroundGalleryHintKey")
            hint_layout.addWidget(key_badge)
        elif mode == "dynamic":
            text = "Hover over an image and press D to assign it as the dark-mode wallpaper, or L for light mode."
            for key_text, icon_path in (("L", icon_paths["light"]), ("D", icon_paths["dark"])):
                key_badge = QLabel(key_text)
                key_badge.setObjectName("backgroundGalleryHintKey")
                hint_layout.addWidget(key_badge)
                icon_label = QLabel()
                icon = self._get_svg_icon(icon_path, colors["muted"])
                if icon:
                    icon_label.setPixmap(icon.pixmap(QSize(15, 15)))
                hint_layout.addWidget(icon_label)
        else:
            text = "Click an image to assign it as the wallpaper."

        label = QLabel(text)
        label.setObjectName("backgroundGalleryHintText")
        label.setWordWrap(True)
        hint_layout.addWidget(label, 1)
        return hint

    def _background_gallery_mode(self, dynamic, slideshow):
        if slideshow:
            return "slideshow"
        if dynamic:
            return "dynamic"
        return "single"

    def _background_gallery_badges(self, mode, filename, light_selected=False, dark_selected=False, order=None, selected=False):
        if mode == "slideshow":
            return [{"text": str(order)}] if order else []
        if mode == "dynamic":
            icon_paths = self._background_gallery_icon_paths()
            badges = []
            if light_selected:
                badges.append({"icon": icon_paths["light"], "text": "L"})
            if dark_selected:
                badges.append({"icon": icon_paths["dark"], "text": "D"})
            return badges
        return [{"text": "✓"}] if selected else []

    def _open_modern_background_gallery(self, prefix):
        if getattr(self, f"{prefix}_bg_color_only_toggle").isChecked():
            return
        spec = self._modern_background_spec(prefix)
        single_key, light_key, dark_key = self._modern_background_gallery_keys(spec)
        setattr(self, f"{prefix}_bg_slideshow_images", self._sanitize_modern_bg_slideshow_images(spec, getattr(self, f"{prefix}_bg_slideshow_images")))
        dialog = BackgroundGalleryDialog(self)
        dialog.setWindowTitle("Select from your Gallery")
        dialog.resize(760, 520)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self._style_background_gallery_dialog(dialog)
        mode = self._background_gallery_mode(
            getattr(self, f"{prefix}_bg_dynamic_toggle").isChecked(),
            getattr(self, f"{prefix}_bg_slideshow_toggle").isChecked(),
        )
        layout.addWidget(self._create_background_gallery_hint_bar(mode))
        target_mode = {"value": dark_key if self._modern_background_preview_mode(prefix) == "dark" else light_key}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("backgroundGalleryContent")
        grid = FlowLayout(content, margin=0, spacing=10)
        tiles = []

        def badges_for(filename):
            if mode == "slideshow":
                images = self._sanitize_modern_bg_slideshow_images(spec, getattr(self, f"{prefix}_bg_slideshow_images"))
                setattr(self, f"{prefix}_bg_slideshow_images", images)
                return self._background_gallery_badges(mode, filename, order=images.index(filename) + 1 if filename in images else None)
            if mode == "dynamic":
                light = self.galleries.get(light_key, {}).get("selected") == filename
                dark = self.galleries.get(dark_key, {}).get("selected") == filename
                return self._background_gallery_badges(mode, filename, light_selected=light, dark_selected=dark)
            return self._background_gallery_badges(mode, filename, selected=self.galleries.get(single_key, {}).get("selected") == filename)

        def refresh_badges():
            for tile in tiles:
                tile.setBadges(badges_for(tile.filename))
            self._update_modern_background_preview(prefix)

        def handle_click(filename):
            if mode == "slideshow":
                images = self._sanitize_modern_bg_slideshow_images(spec, getattr(self, f"{prefix}_bg_slideshow_images"))
                if filename in images:
                    images.remove(filename)
                    setattr(self, f"{prefix}_bg_slideshow_index", 0)
                else:
                    images.append(filename)
                setattr(self, f"{prefix}_bg_slideshow_images", images)
            elif mode == "dynamic":
                self._assign_modern_background_image(prefix, filename, target_mode["value"])
            else:
                self._assign_modern_background_image(prefix, filename)
            refresh_badges()
            self._sync_modern_background_slideshow_preview_timer(prefix)

        def handle_key_assignment(filename, key_text):
            if mode == "dynamic" and key_text in {"d", "l"}:
                self._assign_modern_background_image(prefix, filename, dark_key if key_text == "d" else light_key)
            elif mode == "slideshow" and key_text in set("123456789"):
                images = self._sanitize_modern_bg_slideshow_images(spec, getattr(self, f"{prefix}_bg_slideshow_images"))
                if filename in images:
                    images.remove(filename)
                images.insert(int(key_text) - 1, filename)
                setattr(self, f"{prefix}_bg_slideshow_images", images)
                setattr(self, f"{prefix}_bg_slideshow_index", 0)
            else:
                return
            refresh_badges()
            self._sync_modern_background_slideshow_preview_timer(prefix)
            if dialog.hovered_tile:
                dialog.hovered_tile.flash()

        dialog.keyAssignmentRequested.connect(handle_key_assignment)

        for filename in self._modern_bg_image_files(spec):
            tile = BackgroundGalleryTile(filename, self._modern_bg_image_path(spec, filename), self.accent_color)
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

    def _reset_modern_background_to_default(self, prefix):
        spec = self._modern_background_spec(prefix)
        if not spec:
            return
        sync_main_toggle = getattr(self, f"{prefix}_bg_sync_main_toggle", None)
        if sync_main_toggle:
            sync_main_toggle.setChecked(False)
        getattr(self, f"{prefix}_bg_color_only_toggle").setChecked(True)
        getattr(self, f"{prefix}_bg_slideshow_toggle").setChecked(False)
        getattr(self, f"{prefix}_bg_dynamic_toggle").setChecked(True)
        getattr(self, f"{prefix}_bg_single_color_input").setText(spec.get("default_light", "#F3F3F3"))
        getattr(self, f"{prefix}_bg_light_color_input").setText(spec.get("default_light", "#F3F3F3"))
        getattr(self, f"{prefix}_bg_dark_color_input").setText(spec.get("default_dark", "#2C2C2C"))
        setattr(self, f"{prefix}_bg_slideshow_images", [])
        setattr(self, f"{prefix}_bg_slideshow_index", 0)
        getattr(self, f"{prefix}_bg_slideshow_interval_spinbox").setValue(10)
        single_key, light_key, dark_key = self._modern_background_gallery_keys(spec)
        for key in (single_key, light_key, dark_key):
            if key in self.galleries:
                self.galleries[key]["selected"] = ""
        getattr(self, f"{prefix}_bg_blur_slider").setValue(0)
        getattr(self, f"{prefix}_bg_opacity_slider").setValue(100)
        if prefix == "sidebar":
            for attr, default in (("radius", 15), ("stroke", 1), ("margin", 10)):
                slider = getattr(self, f"{prefix}_bg_{attr}_slider", None)
                if slider:
                    slider.setValue(default)
        self._update_modern_background_controls(prefix)
        label = spec.get("title") or prefix.replace("_", " ").title()
        show_settings_toast(self, f"{label} {tr('modern_bg_reset_toast_suffix', 'reset to default')}")

    def _save_modern_background_designer_settings(self, prefix):
        spec = self._modern_background_spec(prefix)
        if not spec:
            return
        target = mw.col.conf if spec.get("storage") == "col" else self.current_config
        sync_main_toggle = getattr(self, f"{prefix}_bg_sync_main_toggle", None)
        if sync_main_toggle and sync_main_toggle.isChecked():
            target[spec["mode_key"]] = "main"
        elif getattr(self, f"{prefix}_bg_color_only_toggle").isChecked():
            target[spec["mode_key"]] = "color"
        elif getattr(self, f"{prefix}_bg_slideshow_toggle").isChecked():
            target[spec["mode_key"]] = "slideshow"
        else:
            target[spec["mode_key"]] = "image_color"

        color_theme_mode = "separate" if getattr(self, f"{prefix}_bg_dynamic_toggle").isChecked() else "single"
        image_theme_mode = "separate" if getattr(self, f"{prefix}_bg_dynamic_toggle").isChecked() else "single"
        if spec.get("color_theme_mode_key"):
            target[spec["color_theme_mode_key"]] = color_theme_mode
        if spec.get("image_theme_mode_key"):
            target[spec["image_theme_mode_key"]] = image_theme_mode
        if spec.get("legacy_image_mode_key"):
            target[spec["legacy_image_mode_key"]] = image_theme_mode

        if color_theme_mode == "single":
            single_color = getattr(self, f"{prefix}_bg_single_color_input").text()
            target[spec["light_color_key"]] = single_color
            target[spec["dark_color_key"]] = single_color
        else:
            target[spec["light_color_key"]] = getattr(self, f"{prefix}_bg_light_color_input").text()
            target[spec["dark_color_key"]] = getattr(self, f"{prefix}_bg_dark_color_input").text()

        single_key, light_key, dark_key = self._modern_background_gallery_keys(spec)
        single_image = self.galleries.get(single_key, {}).get("selected", "")
        light_image = self.galleries.get(light_key, {}).get("selected", "")
        dark_image = self.galleries.get(dark_key, {}).get("selected", "")
        if image_theme_mode == "single":
            target[spec["image_key"]] = single_image
            target[spec["image_light_key"]] = single_image
            target[spec["image_dark_key"]] = single_image
        else:
            target[spec["image_key"]] = light_image or dark_image
            target[spec["image_light_key"]] = light_image
            target[spec["image_dark_key"]] = dark_image

        target[spec["slideshow_images_key"]] = list(getattr(self, f"{prefix}_bg_slideshow_images", []))
        target[spec["slideshow_interval_key"]] = getattr(self, f"{prefix}_bg_slideshow_interval_spinbox").value()
        target[spec["blur_key"]] = getattr(self, f"{prefix}_bg_blur_slider").value()
        target[spec["opacity_key"]] = getattr(self, f"{prefix}_bg_opacity_slider").value()

    def _create_main_background_designer(self, cached_user_files=None):
        folder = self._main_bg_folder_path()
        mode = mw.col.conf.get("modern_menu_background_mode", "color")
        if mode == "image":
            mode = "image_color"

        image_theme_mode = mw.col.conf.get(
            "modern_menu_bg_image_theme_mode",
            mw.col.conf.get("modern_menu_background_image_mode", "separate")
        )
        color_theme_mode = mw.col.conf.get("modern_menu_bg_color_theme_mode", "separate")

        self.galleries["main_single"] = {"selected": mw.col.conf.get("modern_menu_background_image", ""), "folder": "user_files/main_bg"}
        self.galleries["main_light"] = {"selected": mw.col.conf.get("modern_menu_background_image_light", ""), "folder": "user_files/main_bg"}
        self.galleries["main_dark"] = {"selected": mw.col.conf.get("modern_menu_background_image_dark", ""), "folder": "user_files/main_bg"}
        self.main_bg_slideshow_images = self._sanitize_main_background_slideshow_images(
            list(mw.col.conf.get("modern_menu_slideshow_images", []) or [])
        )
        self.main_bg_slideshow_index = 0
        self.main_bg_slideshow_preview_timer = QTimer(self)
        self.main_bg_slideshow_preview_timer.timeout.connect(self._advance_main_background_slideshow_preview)

        self.main_bg_designer = QFrame()
        self.main_bg_designer.setObjectName("mainBackgroundDesigner")
        outer = QVBoxLayout(self.main_bg_designer)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel(tr("main_background"))
        title_label.setObjectName("sectionTitle")
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.main_bg_preview_mode = "dark" if theme_manager.night_mode else "light"
        self.main_bg_preview_mode_widget, self.main_bg_preview_mode_toggle = self._create_light_dark_mode_toggle(
            self.main_bg_preview_mode,
            self._on_main_background_preview_mode_toggled,
        )
        header_layout.addWidget(self.main_bg_preview_mode_widget)
        outer.addLayout(header_layout)

        self.main_bg_preview = BackgroundPreviewLabel()
        self.main_bg_preview.setObjectName("mainBackgroundPreview")
        # Seed the height from the width the preview will actually get (the dialog
        # is already shown when this page is built) instead of the not-yet-laid-out
        # width() == 0, which would pin the minimum-height floor and make the panel
        # visibly grow to its aspect-ratio height on the first on-screen layout.
        self.main_bg_preview.setMinimumHeight(
            self.main_bg_preview.heightForWidth(self._preview_expected_width())
        )
        self.main_bg_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_bg_preview.installEventFilter(self)
        outer.addWidget(self.main_bg_preview)
        self.main_bg_preview_fade_label = QLabel(self.main_bg_preview)
        self.main_bg_preview_fade_label.setObjectName("mainBackgroundPreviewFade")
        self.main_bg_preview_fade_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_bg_preview_fade_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.main_bg_preview_fade_label.setStyleSheet("background: transparent; border: none;")
        self.main_bg_preview_fade_label.hide()
        self.main_bg_preview_fade_effect = QGraphicsOpacityEffect(self.main_bg_preview_fade_label)
        self.main_bg_preview_fade_effect.setOpacity(0.0)
        self.main_bg_preview_fade_label.setGraphicsEffect(self.main_bg_preview_fade_effect)
        self.main_bg_preview_fade_animation = QPropertyAnimation(self.main_bg_preview_fade_effect, b"opacity", self)
        self.main_bg_preview_fade_animation.setDuration(1200)
        self.main_bg_preview_fade_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.main_bg_preview_fade_animation.finished.connect(self._finalize_main_background_preview_fade)
        self._pending_main_bg_preview_pixmap = None
        self._pending_main_bg_preview_text = ""
        self._main_bg_preview_pan_offsets = {}
        self._main_bg_preview_drag_key = None
        self._main_bg_preview_drag_start_pos = QPoint()
        self._main_bg_preview_drag_start_offset = QPoint()

        left = QWidget()
        left.setMinimumWidth(0)
        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        left_layout = QGridLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setHorizontalSpacing(10)
        left_layout.setVerticalSpacing(10)

        self.main_bg_import_button = self._create_main_bg_button("Import")
        self.main_bg_clear_button = self._create_main_bg_button("Clear image")
        self.main_bg_gallery_button = self._create_main_bg_button("Select from your Gallery")
        self.main_bg_light_color_button = self._create_main_bg_button("Color")
        self.main_bg_light_color_value_button = self._create_main_bg_button("")
        self.main_bg_light_color_value_button.setObjectName("mainBackgroundColorButton")
        self.main_bg_dark_color_button = self._create_main_bg_button("Dark Color")
        self.main_bg_dark_color_value_button = self._create_main_bg_button("")
        self.main_bg_dark_color_value_button.setObjectName("mainBackgroundColorButton")
        slider_palette = self._settings_palette()
        slider_track = slider_palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = slider_palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")

        self.main_bg_blur_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.main_bg_blur_slider.setRange(0, 100)
        self.main_bg_blur_slider.setValue(mw.col.conf.get("modern_menu_background_blur", 0))
        self.main_bg_blur_value_label = QLabel(f"{self.main_bg_blur_slider.value()}%")
        self.main_bg_blur_value_label.setObjectName("mainBackgroundValueLabel")
        self.main_bg_blur_value_label.setFixedWidth(48)
        blur_value = QWidget()
        blur_layout = QHBoxLayout(blur_value)
        blur_layout.setContentsMargins(0, 0, 0, 0)
        blur_layout.setSpacing(10)
        blur_layout.addWidget(self.main_bg_blur_slider, 1)
        blur_layout.addWidget(self.main_bg_blur_value_label)

        self.main_bg_opacity_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.main_bg_opacity_slider.setRange(0, 100)
        self.main_bg_opacity_slider.setValue(mw.col.conf.get("modern_menu_background_opacity", 100))
        self.main_bg_opacity_value_label = QLabel(f"{self.main_bg_opacity_slider.value()}%")
        self.main_bg_opacity_value_label.setObjectName("mainBackgroundValueLabel")
        self.main_bg_opacity_value_label.setFixedWidth(48)
        opacity_value = QWidget()
        opacity_layout = QHBoxLayout(opacity_value)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(10)
        opacity_layout.addWidget(self.main_bg_opacity_slider, 1)
        opacity_layout.addWidget(self.main_bg_opacity_value_label)

        self.main_bg_light_color_card = self._create_color_selector_card(self.main_bg_light_color_button, self.main_bg_light_color_value_button)
        self.main_bg_dark_color_card = self._create_color_selector_card(self.main_bg_dark_color_button, self.main_bg_dark_color_value_button)

        left_layout.addWidget(self.main_bg_import_button, 0, 0)
        left_layout.addWidget(self.main_bg_clear_button, 0, 1)
        left_layout.addWidget(self.main_bg_gallery_button, 1, 0, 1, 2)
        self.main_bg_color_stack = QStackedWidget()
        self.main_bg_color_stack.addWidget(self.main_bg_light_color_card)
        self.main_bg_color_stack.addWidget(self.main_bg_dark_color_card)
        left_layout.addWidget(self.main_bg_color_stack, 2, 0, 1, 2)

        right = QWidget()
        right.setMinimumWidth(0)
        right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        self.main_bg_dynamic_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.main_bg_slideshow_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.main_bg_color_only_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.main_bg_dynamic_toggle.setChecked((mode in {"color", "accent"} and color_theme_mode == "separate") or (mode == "image_color" and image_theme_mode == "separate"))
        self.main_bg_slideshow_toggle.setChecked(mode == "slideshow")
        self.main_bg_color_only_toggle.setChecked(mode in {"color", "accent"})
        right_layout.addWidget(self._create_main_bg_value_row("Blur Intensity", blur_value))
        right_layout.addWidget(self._create_main_bg_value_row("Opacity", opacity_value))
        right_layout.addWidget(self._create_main_bg_toggle_row("Dynamic mode", self.main_bg_dynamic_toggle))
        right_layout.addWidget(self._create_main_bg_toggle_row("Slideshow", self.main_bg_slideshow_toggle))
        self.main_bg_slideshow_interval_spinbox = QSpinBox()
        self.main_bg_slideshow_interval_spinbox.setRange(1, 3600)
        self.main_bg_slideshow_interval_spinbox.setSuffix(" sec")
        self.main_bg_slideshow_interval_spinbox.setValue(int(mw.col.conf.get("modern_menu_slideshow_interval", 10) or 10))
        self.main_bg_slideshow_interval_row = self._create_main_bg_value_row("Change every", self.main_bg_slideshow_interval_spinbox)
        right_layout.addWidget(self.main_bg_slideshow_interval_row)
        right_layout.addWidget(self._create_main_bg_toggle_row("Color only", self.main_bg_color_only_toggle))
        right_layout.addStretch()

        controls = ResponsivePairWidget(right, left, spacing=18, breakpoint=720)
        outer.addWidget(controls)

        reset_row = QWidget()
        reset_row_layout = QHBoxLayout(reset_row)
        reset_row_layout.setContentsMargins(0, 0, 0, 0)
        reset_row_layout.addStretch()
        self.main_bg_reset_button = QPushButton(tr("reset_bg_default"))
        self.main_bg_reset_button.setObjectName("mainBackgroundResetButton")
        self.main_bg_reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.main_bg_reset_button.setFixedHeight(34)
        self.main_bg_reset_button.setMinimumWidth(220)
        self.main_bg_reset_button.setMaximumWidth(280)
        self.main_bg_reset_button.clicked.connect(self.reset_background_to_default)
        reset_row_layout.addWidget(self.main_bg_reset_button)
        reset_row_layout.addStretch()
        outer.addWidget(reset_row)

        self.main_bg_light_color_input = QLineEdit(mw.col.conf.get("modern_menu_bg_color_light", self.current_config.get("colors", {}).get("light", {}).get("--bg", "#ffffff")))
        self.main_bg_single_color_input = self.main_bg_light_color_input
        self.main_bg_dark_color_input = QLineEdit(mw.col.conf.get("modern_menu_bg_color_dark", self.current_config.get("colors", {}).get("dark", {}).get("--bg", "#2c2c2c")))

        self.main_bg_import_button.clicked.connect(self._import_main_background)
        self.main_bg_clear_button.clicked.connect(self._clear_main_background)
        self.main_bg_gallery_button.clicked.connect(self._open_main_background_gallery)
        self.main_bg_light_color_button.clicked.connect(lambda: self._choose_main_background_color("light", self.main_bg_light_color_button))
        self.main_bg_light_color_value_button.clicked.connect(lambda: self._choose_main_background_color("light", self.main_bg_light_color_value_button))
        self.main_bg_dark_color_button.clicked.connect(lambda: self._choose_main_background_color("dark", self.main_bg_dark_color_button))
        self.main_bg_dark_color_value_button.clicked.connect(lambda: self._choose_main_background_color("dark", self.main_bg_dark_color_value_button))
        self.main_bg_dynamic_toggle.toggled.connect(self._on_main_background_mode_changed)
        self.main_bg_slideshow_toggle.toggled.connect(self._on_main_background_mode_changed)
        self.main_bg_color_only_toggle.toggled.connect(self._on_main_background_mode_changed)
        self.main_bg_slideshow_interval_spinbox.valueChanged.connect(self._on_main_background_slideshow_interval_changed)
        self.main_bg_blur_slider.valueChanged.connect(self._on_main_background_effect_changed)
        self.main_bg_opacity_slider.valueChanged.connect(self._on_main_background_effect_changed)
        for line_edit in (self.main_bg_light_color_input, self.main_bg_dark_color_input):
            line_edit.textChanged.connect(lambda _=None: self._update_main_background_preview())

        self._update_main_background_controls()
        return self.main_bg_designer

    def _main_background_active_color_input(self):
        if self.main_bg_dynamic_toggle.isChecked():
            return self.main_bg_dark_color_input if theme_manager.night_mode else self.main_bg_light_color_input
        return self.main_bg_single_color_input

    def _main_background_active_image(self):
        if self.main_bg_slideshow_toggle.isChecked():
            if not self.main_bg_slideshow_images:
                return ""
            self.main_bg_slideshow_index %= len(self.main_bg_slideshow_images)
            return self.main_bg_slideshow_images[self.main_bg_slideshow_index]
        if self.main_bg_dynamic_toggle.isChecked():
            key = "main_dark" if theme_manager.night_mode else "main_light"
            return self.galleries.get(key, {}).get("selected", "")
        return self.galleries.get("main_single", {}).get("selected", "")

    def _main_background_color_for_input(self, line_edit, fallback="#ffffff"):
        color = line_edit.text() if line_edit else fallback
        return color if QColor(color).isValid() else fallback

    def _style_main_background_color_button(self, button, color):
        compact = bool(button.property("compactColor"))
        height = 30 if compact else 36
        padding = "0px 12px" if compact else "0px 18px"
        font_size = 12 if compact else 13
        if str(color).strip().lower() == "transparent":
            # A literal "background-color: transparent" here would just reveal
            # whatever the surrounding card is painted with (often white), and
            # the readable-text-color computed from black (transparent's RGB)
            # would then pick white text too - i.e. invisible on light theme.
            # Use a fixed, always-legible neutral swatch instead.
            swatch_bg = "#3a3a3a" if theme_manager.night_mode else "#e5e5e5"
            text_color = "#e5e5e5" if theme_manager.night_mode else "#1f1f1f"
            border_color = QColor(swatch_bg).lighter(150) if theme_manager.night_mode else QColor(swatch_bg).darker(114)
            button.setText("TRANSPARENT")
            button.setStyleSheet(f"""
                QPushButton#mainBackgroundColorButton {{
                    background-color: {swatch_bg};
                    color: {text_color};
                    border: 1px dashed {border_color.name()};
                    border-radius: {10 if compact else 12}px;
                    min-height: {height}px;
                    max-height: {height}px;
                    padding: {padding};
                    font-size: {font_size}px;
                    font-weight: 700;
                    letter-spacing: 0.2px;
                }}
                QPushButton#mainBackgroundColorButton:hover,
                QPushButton#mainBackgroundColorButton:pressed {{
                    border-radius: {10 if compact else 12}px;
                }}
            """)
            return
        text_color = self._readable_text_color(color)
        qcolor = QColor(color)
        border_color = qcolor.darker(114) if qcolor.lightness() > 110 else qcolor.lighter(150)
        button.setText(color.upper())
        button.setStyleSheet(f"""
            QPushButton#mainBackgroundColorButton {{
                background-color: {color};
                color: {text_color};
                border: 1px solid {border_color.name()};
                border-radius: {10 if compact else 12}px;
                min-height: {height}px;
                max-height: {height}px;
                padding: {padding};
                font-size: {font_size}px;
                font-weight: 700;
                letter-spacing: 0.2px;
            }}
            QPushButton#mainBackgroundColorButton:hover,
            QPushButton#mainBackgroundColorButton:pressed {{
                border-radius: {10 if compact else 12}px;
            }}
        """)

    def _main_background_slideshow_interval_ms(self):
        seconds = self.main_bg_slideshow_interval_spinbox.value() if hasattr(self, "main_bg_slideshow_interval_spinbox") else 10
        return max(1, int(seconds)) * 1000

    def _sync_main_background_slideshow_preview_timer(self):
        timer = getattr(self, "main_bg_slideshow_preview_timer", None)
        if not timer:
            return
        should_run = (
            self.main_bg_slideshow_toggle.isChecked()
            and not self.main_bg_color_only_toggle.isChecked()
            and len(self.main_bg_slideshow_images) > 1
        )
        if should_run:
            timer.start(self._main_background_slideshow_interval_ms())
        else:
            timer.stop()

    def _advance_main_background_slideshow_preview(self):
        self.main_bg_slideshow_images = self._sanitize_main_background_slideshow_images(self.main_bg_slideshow_images)
        if not self.main_bg_slideshow_images:
            self.main_bg_slideshow_index = 0
            self._update_main_background_preview()
            return
        self.main_bg_slideshow_index = (self.main_bg_slideshow_index + 1) % len(self.main_bg_slideshow_images)
        self._update_main_background_preview(animate=True)

    def _on_main_background_slideshow_interval_changed(self, value):
        self._sync_main_background_slideshow_preview_timer()

    def _on_main_background_effect_changed(self):
        self.main_bg_blur_value_label.setText(f"{self.main_bg_blur_slider.value()}%")
        self.main_bg_opacity_value_label.setText(f"{self.main_bg_opacity_slider.value()}%")
        self._update_main_background_preview()

    def _on_main_background_mode_changed(self, checked):
        sender = self.sender()
        if sender is self.main_bg_color_only_toggle and checked:
            self.main_bg_slideshow_toggle.setChecked(False)
        elif sender is self.main_bg_slideshow_toggle and checked:
            self.main_bg_color_only_toggle.setChecked(False)
        self._update_main_background_controls()

    def _update_main_background_controls(self):
        color_only = self.main_bg_color_only_toggle.isChecked()
        dynamic = self.main_bg_dynamic_toggle.isChecked()
        self.main_bg_light_color_button.setText("Light Color" if dynamic else "Color")
        if hasattr(self, "main_bg_preview_mode_widget"):
            self.main_bg_preview_mode_widget.setEnabled(dynamic)
            self.main_bg_preview_mode_widget.setToolTip("" if dynamic else "Enable Dynamic mode to switch light/dark palettes.")
        for button in (self.main_bg_import_button, self.main_bg_clear_button, self.main_bg_gallery_button):
            button.setEnabled(not color_only)
        mode = self._main_background_preview_mode()
        show_dark = dynamic and mode == "dark"
        if hasattr(self, "main_bg_color_stack"):
            self.main_bg_color_stack.setCurrentIndex(1 if show_dark else 0)
        else:
            self.main_bg_light_color_card.setVisible(not show_dark)
            self.main_bg_dark_color_card.setVisible(show_dark)
        if hasattr(self, "main_bg_slideshow_interval_row"):
            self.main_bg_slideshow_interval_row.setVisible(self.main_bg_slideshow_toggle.isChecked() and not color_only)
            self.main_bg_slideshow_interval_spinbox.setEnabled(self.main_bg_slideshow_toggle.isChecked() and not color_only)
        self._update_main_background_preview()
        self._sync_main_background_slideshow_preview_timer()

    def _main_background_preview_mode(self):
        return getattr(self, "main_bg_preview_mode", "dark" if theme_manager.night_mode else "light")

    def _on_main_background_preview_mode_toggled(self, mode):
        self.main_bg_preview_mode = "dark" if mode == "dark" else "light"
        self._update_main_background_controls()

    def _update_main_background_preview(self, animate=False):
        if not hasattr(self, "main_bg_preview"):
            return
        single_color = self._main_background_color_for_input(self.main_bg_single_color_input)
        light_color = self._main_background_color_for_input(self.main_bg_light_color_input, single_color)
        dark_color = self._main_background_color_for_input(self.main_bg_dark_color_input, single_color)
        mode = self._main_background_preview_mode()
        dynamic = self.main_bg_dynamic_toggle.isChecked()
        color_only = self.main_bg_color_only_toggle.isChecked()
        slideshow = self.main_bg_slideshow_toggle.isChecked()
        active_color = (dark_color if mode == "dark" else light_color) if dynamic else single_color
        self._style_main_background_color_button(self.main_bg_light_color_value_button, light_color)
        self._style_main_background_color_button(self.main_bg_dark_color_value_button, dark_color)

        self.main_bg_slideshow_images = self._sanitize_main_background_slideshow_images(self.main_bg_slideshow_images)
        if self.main_bg_slideshow_index >= len(self.main_bg_slideshow_images):
            self.main_bg_slideshow_index = 0
        self.main_bg_preview.setStyleSheet("QLabel#mainBackgroundPreview { background: transparent; border: none; }")
        self.main_bg_preview.setWindowOpacity(1.0)

        if slideshow:
            image_name = "" if color_only else self._main_background_active_image()
            offset_key = "main_slideshow"
        elif dynamic:
            image_key = "main_dark" if mode == "dark" else "main_light"
            image_name = "" if color_only else self.galleries.get(image_key, {}).get("selected", "")
            offset_key = image_key
        else:
            image_name = "" if color_only else self.galleries.get("main_single", {}).get("selected", "")
            offset_key = "main_single"
        image_path = self._main_bg_image_path(image_name)
        pixmap = self._render_main_background_preview_pixmap(
            active_color,
            image_path if image_name and os.path.exists(image_path) else "",
            self._main_background_preview_offset(offset_key),
        )
        text = "" if image_name or color_only else "No background selected"
        should_animate = (
            animate
            and slideshow
            and not color_only
            and bool(image_name)
            and len(self.main_bg_slideshow_images) > 1
        )
        self._set_main_background_preview_pixmap(pixmap, text, should_animate)
        if hasattr(self, "box_effect_preview"):
            self._update_box_effect_preview()

    def _set_main_background_preview_pixmap(self, pixmap, text="", animate=False):
        fade_label = getattr(self, "main_bg_preview_fade_label", None)
        fade_animation = getattr(self, "main_bg_preview_fade_animation", None)
        fade_effect = getattr(self, "main_bg_preview_fade_effect", None)
        if not animate or not fade_label or not fade_animation or not fade_effect:
            if fade_animation and fade_animation.state() == QPropertyAnimation.State.Running:
                fade_animation.stop()
            if fade_label:
                fade_label.hide()
            self.main_bg_preview.setPixmap(pixmap)
            self.main_bg_preview.setText(text)
            self._pending_main_bg_preview_pixmap = None
            self._pending_main_bg_preview_text = ""
            return

        fade_animation.stop()
        fade_label.setGeometry(self.main_bg_preview.rect())
        fade_label.setPixmap(pixmap)
        fade_label.setText(text)
        fade_label.raise_()
        fade_label.show()
        fade_effect.setOpacity(0.0)
        self._pending_main_bg_preview_pixmap = pixmap
        self._pending_main_bg_preview_text = text
        fade_animation.setDuration(min(1200, max(350, self._main_background_slideshow_interval_ms() - 120)))
        fade_animation.setStartValue(0.0)
        fade_animation.setEndValue(1.0)
        fade_animation.start()

    def _finalize_main_background_preview_fade(self):
        pixmap = getattr(self, "_pending_main_bg_preview_pixmap", None)
        text = getattr(self, "_pending_main_bg_preview_text", "")
        if pixmap is not None:
            self.main_bg_preview.setPixmap(pixmap)
            self.main_bg_preview.setText(text)
        if hasattr(self, "main_bg_preview_fade_label"):
            self.main_bg_preview_fade_label.hide()
        self._pending_main_bg_preview_pixmap = None
        self._pending_main_bg_preview_text = ""

    def _main_background_preview_offset(self, key):
        offsets = getattr(self, "_main_bg_preview_pan_offsets", {})
        return offsets.get(key, QPoint(0, 0))

    def _set_main_background_preview_offset(self, key, offset):
        if not hasattr(self, "_main_bg_preview_pan_offsets"):
            self._main_bg_preview_pan_offsets = {}
        self._main_bg_preview_pan_offsets[key] = offset

    def _main_background_drag_key_for_pos(self, pos):
        if self.main_bg_color_only_toggle.isChecked():
            return None
        if self.main_bg_slideshow_toggle.isChecked():
            return "main_slideshow"
        if self.main_bg_dynamic_toggle.isChecked():
            return "main_dark" if self._main_background_preview_mode() == "dark" else "main_light"
        return "main_single"

    def _handle_main_background_preview_mouse_event(self, event):
        event_type = event.type()
        if event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            key = self._main_background_drag_key_for_pos(event.position().toPoint())
            if not key:
                return False
            self._main_bg_preview_drag_key = key
            self._main_bg_preview_drag_start_pos = event.position().toPoint()
            self._main_bg_preview_drag_start_offset = self._main_background_preview_offset(key)
            self.main_bg_preview.setCursor(Qt.CursorShape.ClosedHandCursor)
            return True
        if event_type == QEvent.Type.MouseMove and getattr(self, "_main_bg_preview_drag_key", None):
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                return False
            delta = event.position().toPoint() - self._main_bg_preview_drag_start_pos
            start = self._main_bg_preview_drag_start_offset
            self._set_main_background_preview_offset(
                self._main_bg_preview_drag_key,
                QPoint(start.x() + delta.x(), start.y() + delta.y()),
            )
            self._update_main_background_preview()
            return True
        if event_type == QEvent.Type.MouseButtonRelease and getattr(self, "_main_bg_preview_drag_key", None):
            self._main_bg_preview_drag_key = None
            self.main_bg_preview.setCursor(Qt.CursorShape.OpenHandCursor)
            return True
        if event_type == QEvent.Type.Enter:
            self.main_bg_preview.setCursor(Qt.CursorShape.OpenHandCursor)
        elif event_type == QEvent.Type.Leave:
            self._main_bg_preview_drag_key = None
            self.main_bg_preview.unsetCursor()
        return False

    def _main_background_cover_image(self, image_path, width, height, offset=None):
        blur = self.main_bg_blur_slider.value() if hasattr(self, "main_bg_blur_slider") else 0
        return self._background_cover_image_with_effect(image_path, width, height, blur, offset)

    def _render_main_background_preview_pixmap(self, color, image_path, offset=None):
        size = self.main_bg_preview.size()
        width = max(1, size.width())
        height = max(1, size.height())
        radius = 22
        dpr = max(1.0, self.main_bg_preview.devicePixelRatioF())
        target = QPixmap(int(width * dpr), int(height * dpr))
        target.setDevicePixelRatio(dpr)
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
            image = self._main_background_cover_image(image_path, width, height, offset)
            if not image.isNull():
                painter.setOpacity(max(0.0, min(1.0, self.main_bg_opacity_slider.value() / 100.0)))
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

    def _choose_main_background_color(self, target="active", anchor=None):
        if target == "single":
            line_edit = self.main_bg_single_color_input
        elif target == "light":
            line_edit = self.main_bg_light_color_input
        elif target == "dark":
            line_edit = self.main_bg_dark_color_input
        else:
            line_edit = self._main_background_active_color_input()
        chosen, ok = OnigiriColorDialog.getColor(line_edit.text(), self, anchor=anchor)
        if ok:
            line_edit.setText(chosen)
            self._update_main_background_preview()

    def _import_main_background(self):
        filepath, _ = QFileDialog.getOpenFileName(self, tr("import_image"), "", "Images (*.png *.jpg *.jpeg *.gif *.webp)")
        if not filepath:
            return
        filename = os.path.basename(filepath)
        dest_path = os.path.join(self._main_bg_folder_path(), filename)
        base, ext = os.path.splitext(filename)
        index = 2
        while os.path.exists(dest_path) and os.path.abspath(filepath) != os.path.abspath(dest_path):
            filename = f"{base}-{index}{ext}"
            dest_path = os.path.join(self._main_bg_folder_path(), filename)
            index += 1
        try:
            if os.path.abspath(filepath) != os.path.abspath(dest_path):
                shutil.copy(filepath, dest_path)
            self._assign_main_background_image(filename)
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not import image: {exc}")

    def _clear_main_background(self):
        if self.main_bg_slideshow_toggle.isChecked():
            self.main_bg_slideshow_images = []
            self.main_bg_slideshow_index = 0
        elif self.main_bg_dynamic_toggle.isChecked():
            self.galleries["main_light"]["selected"] = ""
            self.galleries["main_dark"]["selected"] = ""
        else:
            self.galleries["main_single"]["selected"] = ""
        self._update_main_background_preview()
        self._sync_main_background_slideshow_preview_timer()

    def _assign_main_background_image(self, filename, target=None):
        if self.main_bg_slideshow_toggle.isChecked():
            self.main_bg_slideshow_images = self._sanitize_main_background_slideshow_images(self.main_bg_slideshow_images)
            if filename not in self.main_bg_slideshow_images:
                self.main_bg_slideshow_images.append(filename)
            self.main_bg_slideshow_index = max(0, min(self.main_bg_slideshow_index, len(self.main_bg_slideshow_images) - 1))
        elif self.main_bg_dynamic_toggle.isChecked():
            key = target or ("main_dark" if self._main_background_preview_mode() == "dark" else "main_light")
            self.galleries[key]["selected"] = filename
        else:
            self.galleries["main_single"]["selected"] = filename
        self._update_main_background_preview()
        self._sync_main_background_slideshow_preview_timer()

    def _open_main_background_gallery(self):
        if self.main_bg_color_only_toggle.isChecked():
            return
        self.main_bg_slideshow_images = self._sanitize_main_background_slideshow_images(self.main_bg_slideshow_images)
        dialog = BackgroundGalleryDialog(self)
        dialog.setWindowTitle("Select from your Gallery")
        dialog.resize(760, 520)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self._style_background_gallery_dialog(dialog)
        mode = self._background_gallery_mode(
            self.main_bg_dynamic_toggle.isChecked(),
            self.main_bg_slideshow_toggle.isChecked(),
        )
        layout.addWidget(self._create_background_gallery_hint_bar(mode))
        target_mode = {"value": "main_dark" if self._main_background_preview_mode() == "dark" else "main_light"}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("backgroundGalleryContent")
        grid = FlowLayout(content, margin=0, spacing=10)
        tiles = []

        def badges_for(filename):
            if mode == "slideshow":
                self.main_bg_slideshow_images = self._sanitize_main_background_slideshow_images(self.main_bg_slideshow_images)
                return self._background_gallery_badges(mode, filename, order=self.main_bg_slideshow_images.index(filename) + 1 if filename in self.main_bg_slideshow_images else None)
            if mode == "dynamic":
                light = self.galleries.get("main_light", {}).get("selected") == filename
                dark = self.galleries.get("main_dark", {}).get("selected") == filename
                return self._background_gallery_badges(mode, filename, light_selected=light, dark_selected=dark)
            return self._background_gallery_badges(mode, filename, selected=self.galleries.get("main_single", {}).get("selected") == filename)

        def refresh_badges():
            for tile in tiles:
                tile.setBadges(badges_for(tile.filename))
            self._update_main_background_preview()

        def handle_click(filename):
            if mode == "slideshow":
                self.main_bg_slideshow_images = self._sanitize_main_background_slideshow_images(self.main_bg_slideshow_images)
                if filename in self.main_bg_slideshow_images:
                    self.main_bg_slideshow_images.remove(filename)
                    self.main_bg_slideshow_index = 0
                else:
                    self.main_bg_slideshow_images.append(filename)
            elif mode == "dynamic":
                self._assign_main_background_image(filename, target_mode["value"])
            else:
                self._assign_main_background_image(filename)
            refresh_badges()
            self._sync_main_background_slideshow_preview_timer()

        def handle_key_assignment(filename, key_text):
            if mode == "dynamic" and key_text in {"d", "l"}:
                self._assign_main_background_image(filename, "main_dark" if key_text == "d" else "main_light")
            elif mode == "slideshow" and key_text in set("123456789"):
                self.main_bg_slideshow_images = self._sanitize_main_background_slideshow_images(self.main_bg_slideshow_images)
                if filename in self.main_bg_slideshow_images:
                    self.main_bg_slideshow_images.remove(filename)
                self.main_bg_slideshow_images.insert(int(key_text) - 1, filename)
                self.main_bg_slideshow_index = 0
            else:
                return
            refresh_badges()
            self._sync_main_background_slideshow_preview_timer()
            if dialog.hovered_tile:
                dialog.hovered_tile.flash()

        dialog.keyAssignmentRequested.connect(handle_key_assignment)

        for filename in self._main_bg_image_files():
            tile = BackgroundGalleryTile(filename, self._main_bg_image_path(filename), self.accent_color)
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

    def _main_background_state_for_box_preview(self, mode):
        mode = "dark" if mode == "dark" else "light"
        if hasattr(self, "main_bg_color_only_toggle"):
            dynamic = self.main_bg_dynamic_toggle.isChecked()
            color_only = self.main_bg_color_only_toggle.isChecked()
            slideshow = self.main_bg_slideshow_toggle.isChecked()
            if slideshow:
                color_input = self.main_bg_dark_color_input if dynamic and mode == "dark" else self.main_bg_light_color_input if dynamic else self.main_bg_single_color_input
                image_name = "" if color_only else self._main_background_active_image()
            elif dynamic:
                color_input = self.main_bg_dark_color_input if mode == "dark" else self.main_bg_light_color_input
                image_key = "main_dark" if mode == "dark" else "main_light"
                image_name = "" if color_only else self.galleries.get(image_key, {}).get("selected", "")
            else:
                color_input = self.main_bg_single_color_input
                image_name = "" if color_only else self._main_background_active_image()
            color = self._main_background_color_for_input(color_input)
            return {
                "color": color,
                "image_path": self._main_bg_image_path(image_name) if image_name else "",
                "blur": self.main_bg_blur_slider.value(),
                "opacity": self.main_bg_opacity_slider.value(),
            }

        bg_mode = mw.col.conf.get("modern_menu_background_mode", "color")
        color_theme_mode = mw.col.conf.get("modern_menu_bg_color_theme_mode", "separate")
        image_theme_mode = mw.col.conf.get("modern_menu_bg_image_theme_mode", mw.col.conf.get("modern_menu_background_image_mode", "separate"))
        light_color = mw.col.conf.get("modern_menu_bg_color_light", self.current_config.get("colors", {}).get("light", {}).get("--bg", "#ffffff"))
        dark_color = mw.col.conf.get("modern_menu_bg_color_dark", self.current_config.get("colors", {}).get("dark", {}).get("--bg", "#2c2c2c"))
        color = dark_color if color_theme_mode == "separate" and mode == "dark" else light_color
        image_name = ""
        if bg_mode == "slideshow":
            images = self._sanitize_main_background_slideshow_images(list(mw.col.conf.get("modern_menu_slideshow_images", []) or []))
            image_name = images[0] if images else ""
        elif bg_mode not in {"color", "accent"}:
            if image_theme_mode == "separate":
                image_name = mw.col.conf.get("modern_menu_background_image_dark" if mode == "dark" else "modern_menu_background_image_light", "")
            else:
                image_name = mw.col.conf.get("modern_menu_background_image", "")
        return {
            "color": color,
            "image_path": self._main_bg_image_path(image_name) if image_name else "",
            "blur": int(mw.col.conf.get("modern_menu_background_blur", 0) or 0),
            "opacity": int(mw.col.conf.get("modern_menu_background_opacity", 100) or 100),
        }



# --- MERGED FROM _page_backgrounds_2.py ---

class PageBackgroundsMixin2:
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
            tr("background_color"), conf.get("onigiri_overview_bg_light_color", "#FFFFFF"), "overview_bg_single"
        )
        single_color_layout.addLayout(self.overview_bg_single_color_row)
        
        # Separate colors container
        self.overview_bg_separate_colors_container = QWidget()
        separate_colors_layout = QVBoxLayout(self.overview_bg_separate_colors_container)
        self.overview_bg_light_color_row = self._create_color_picker_row(
            tr("background_light_mode"), conf.get("onigiri_overview_bg_light_color", "#FFFFFF"), "overview_bg_light"
        )
        self.overview_bg_dark_color_row = self._create_color_picker_row(
            tr("background_dark_mode"), conf.get("onigiri_overview_bg_dark_color", "#2C2C2C"), "overview_bg_dark"
        )
        separate_colors_layout.addLayout(self.overview_bg_light_color_row)
        separate_colors_layout.addLayout(self.overview_bg_dark_color_row)
        
        # Add both containers to the layout
        color_layout.addWidget(self.overview_bg_single_color_container)
        color_layout.addWidget(self.overview_bg_separate_colors_container)
        
        # Add theme mode toggle for color selection
        self.overview_bg_color_theme_mode_group = QButtonGroup()
        self.overview_bg_color_theme_mode_single = QRadioButton(tr("use_same_color_both_themes"))
        self.overview_bg_color_theme_mode_separate = QRadioButton(tr("use_separate_colors"))
        self.overview_bg_color_theme_mode_group.addButton(self.overview_bg_color_theme_mode_single)
        self.overview_bg_color_theme_mode_group.addButton(self.overview_bg_color_theme_mode_separate)
        
        # Load saved theme mode or default to single
        # Load saved theme mode or default to single
        overview_bg_color_theme_mode = conf.get("onigiri_overview_bg_color_theme_mode", "separate")
        self.overview_bg_color_theme_mode_single.setChecked(overview_bg_color_theme_mode == "single")
        self.overview_bg_color_theme_mode_separate.setChecked(overview_bg_color_theme_mode == "separate")
        
        color_theme_mode_container, color_theme_mode_layout = self._create_responsive_row(spacing=10)
        color_theme_mode_layout.addWidget(self.overview_bg_color_theme_mode_single)
        color_theme_mode_layout.addWidget(self.overview_bg_color_theme_mode_separate)
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
        self.overview_bg_image_theme_mode_single = QRadioButton(tr("use_same_image_both_themes"))
        self.overview_bg_image_theme_mode_separate = QRadioButton(tr("use_separate_images"))
        self.overview_bg_image_theme_mode_group.addButton(self.overview_bg_image_theme_mode_single)
        self.overview_bg_image_theme_mode_group.addButton(self.overview_bg_image_theme_mode_separate)
        
        # Load saved theme mode or default to single
        # Load saved theme mode or default to single
        overview_bg_image_theme_mode = conf.get("onigiri_overview_bg_image_theme_mode", "separate")
        self.overview_bg_image_theme_mode_single.setChecked(overview_bg_image_theme_mode == "single")
        self.overview_bg_image_theme_mode_separate.setChecked(overview_bg_image_theme_mode == "separate")
        
        image_theme_mode_container, image_theme_mode_layout = self._create_responsive_row(spacing=10)
        image_theme_mode_layout.addWidget(self.overview_bg_image_theme_mode_single)
        image_theme_mode_layout.addWidget(self.overview_bg_image_theme_mode_separate)
        image_theme_mode_container.setContentsMargins(15, 5, 0, 5)
        image_layout.addWidget(image_theme_mode_container)
        
        # Single image container
        self.overview_bg_single_image_container = QWidget()
        single_image_layout = QVBoxLayout(self.overview_bg_single_image_container)
        single_image_layout.setContentsMargins(0, 10, 0, 0)
        self.galleries["overview_bg_single"] = {}
        single_image_layout.addWidget(self._create_image_gallery_group(
            "overview_bg_single", "user_files/main_bg", "onigiri_overview_bg_image", 
            title=tr("background_image"), is_sub_group=True
        ))
        
        # Separate images container
        self.galleries["overview_bg_light"] = {}
        overview_light_panel, overview_light_layout = self._create_theme_mode_panel(tr("background_light_mode"), "light")
        overview_light_layout.addWidget(self._create_image_gallery_group(
            "overview_bg_light", "user_files/main_bg", "onigiri_overview_bg_image_light", 
            is_sub_group=True
        ))
        self.galleries["overview_bg_dark"] = {}
        overview_dark_panel, overview_dark_layout = self._create_theme_mode_panel(tr("background_dark_mode"), "dark")
        overview_dark_layout.addWidget(self._create_image_gallery_group(
            "overview_bg_dark", "user_files/main_bg", "onigiri_overview_bg_image_dark", 
            is_sub_group=True
        ))
        self.overview_bg_separate_images_container = ResponsivePairWidget(overview_light_panel, overview_dark_panel)
        
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
        effects_layout = FlowLayout(self.overview_bg_effects_container, margin=0, spacing=10)
        effects_layout.setContentsMargins(0, 10, 0, 0)
        
        self.overview_bg_blur_label = QLabel(tr("blur_label"))
        self.overview_bg_blur_spinbox = QSpinBox()
        self.overview_bg_blur_spinbox.setMinimum(0)
        self.overview_bg_blur_spinbox.setMaximum(100)
        self.overview_bg_blur_spinbox.setSuffix(" %")
        self.overview_bg_blur_spinbox.setValue(conf.get("onigiri_overview_bg_blur", 0))
        
        self.overview_bg_opacity_label = QLabel(tr("opacity_label"))
        self.overview_bg_opacity_spinbox = QSpinBox()
        self.overview_bg_opacity_spinbox.setMinimum(0)
        self.overview_bg_opacity_spinbox.setMaximum(100)
        self.overview_bg_opacity_spinbox.setSuffix(" %")
        self.overview_bg_opacity_spinbox.setValue(conf.get("onigiri_overview_bg_opacity", 100))
        
        effects_layout.addWidget(self.overview_bg_blur_label)
        effects_layout.addWidget(self.overview_bg_blur_spinbox)
        effects_layout.addWidget(self.overview_bg_opacity_label)
        effects_layout.addWidget(self.overview_bg_opacity_spinbox)
        layout.addWidget(self.overview_bg_effects_container)
        
        # Initially hide image options (only show for Image mode)
        self.overview_bg_image_group.setVisible(False)
        
        return widget

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

    def _reset_loaded_modern_background_widgets(self, prefix, light_color, dark_color):
        if not hasattr(self, f"{prefix}_bg_color_only_toggle"):
            return
        spec = self._modern_background_spec(prefix)
        if not spec:
            return

        sync_main_toggle = getattr(self, f"{prefix}_bg_sync_main_toggle", None)
        if sync_main_toggle:
            sync_main_toggle.setChecked(False)
        getattr(self, f"{prefix}_bg_color_only_toggle").setChecked(True)
        getattr(self, f"{prefix}_bg_slideshow_toggle").setChecked(False)
        getattr(self, f"{prefix}_bg_dynamic_toggle").setChecked(True)
        getattr(self, f"{prefix}_bg_single_color_input").setText(light_color)
        getattr(self, f"{prefix}_bg_light_color_input").setText(light_color)
        getattr(self, f"{prefix}_bg_dark_color_input").setText(dark_color)
        setattr(self, f"{prefix}_bg_slideshow_images", [])
        setattr(self, f"{prefix}_bg_slideshow_index", 0)
        getattr(self, f"{prefix}_bg_slideshow_interval_spinbox").setValue(10)
        for key in self._modern_background_gallery_keys(spec):
            self._clear_theme_gallery_selection(key)
        getattr(self, f"{prefix}_bg_blur_slider").setValue(0)
        getattr(self, f"{prefix}_bg_opacity_slider").setValue(100)
        self._update_modern_background_controls(prefix)
