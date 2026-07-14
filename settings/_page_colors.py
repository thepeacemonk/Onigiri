# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *



class PageColorsMixin:
    def _settings_palette(self):
        accent = self._settings_accent_color()
        if theme_manager.night_mode:
            return {
                "--bg": "#181818",
                "--canvas-inset": "#242424",
                "--highlight-bg": "#303030",
                "--hover-bg": "#3a3a3a",
                "--fg": "#f4f4f5",
                "--fg-subtle": "#c4c4c4",
                "--muted-fg": "#8a8a8a",
                "--border": "#454545",
                "--input-bg": "#242424",
                "--icon-color": "#f4f4f5",
                "--accent-color": accent,
                "--button-primary-bg": accent,
            }
        return {
            "--bg": "#f7f7f7",
            "--canvas-inset": "#ffffff",
            "--highlight-bg": "#f2f2f2",
            "--hover-bg": "#e9e9e9",
            "--fg": "#202124",
            "--fg-subtle": "#6f7177",
            "--muted-fg": "#8f9299",
            "--border": "#dcdde1",
            "--input-bg": "#ffffff",
            "--icon-color": "#202124",
            "--accent-color": accent,
            "--button-primary-bg": accent,
        }

    def _settings_accent_color(self):
        conf = self.current_config if hasattr(self, "current_config") else config.get_config()
        mode = "dark" if theme_manager.night_mode else "light"
        default = DEFAULTS["colors"][mode]["--accent-color"]
        return conf.get("colors", {}).get(mode, {}).get("--accent-color", default)

    def _settings_icon_color(self):
        palette = self._settings_palette()
        fallback = "#f9fafb" if theme_manager.night_mode else "#111827"
        return palette.get("--icon-color", palette.get("--fg", fallback))

    def _layout_editor_style_colors(self):
        palette = self._settings_palette()
        if theme_manager.night_mode:
            return {
                "button_bg": palette.get("--highlight-bg", palette.get("--canvas-inset", "#303030")),
                "border": palette.get("--border", "#454545"),
                "fg": palette.get("--fg", "#f9fafb"),
                "accent": palette.get("--accent-color", DEFAULTS["colors"]["dark"]["--accent-color"]),
            }
        return {
            "button_bg": palette.get("--highlight-bg", palette.get("--canvas-inset", "#f9fafb")),
            "border": palette.get("--border", "#e5e7eb"),
            "fg": palette.get("--fg", "#111827"),
            "accent": palette.get("--accent-color", DEFAULTS["colors"]["light"]["--accent-color"]),
        }

    def _save_button_icon_color(self):
        c = QColor(getattr(self, 'accent_color', "#00A982"))
        lum = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255
        return "#111827" if lum > 0.5 else "#ffffff"

    def _style_color_selector_label(self, button, height=36):
        palette = self._settings_palette()
        fg = palette.get("--fg", "#f9fafb" if theme_manager.night_mode else "#111827")
        button.setObjectName("colorSelectorLabel")
        button.setFixedHeight(height)
        button.setStyleSheet(f"""
            QPushButton#colorSelectorLabel {{
                background-color: transparent;
                color: {fg};
                border: none;
                text-align: left;
                padding: 0px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton#colorSelectorLabel:hover,
            QPushButton#colorSelectorLabel:pressed {{
                background-color: transparent;
                border: none;
            }}
        """)

    def _create_color_selector_card(self, label_button, value_button, compact=False):
        if compact:
            label_button.setProperty("compactColor", True)
            value_button.setProperty("compactColor", True)
            label_button.setFixedHeight(30)
            value_button.setFixedHeight(30)
            self._style_color_selector_label(label_button, height=30)
            value_button.setMinimumWidth(110)
        else:
            self._style_color_selector_label(label_button, height=value_button.height() or 36)
            value_button.setMinimumWidth(140)
        palette = self._settings_palette()
        card_bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        card_border = palette.get("--border", "#454545" if theme_manager.night_mode else "#dcdde1")
        card = QFrame()
        card.setObjectName("colorSelectorCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setStyleSheet(f"""
            QFrame#colorSelectorCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: {12 if compact else 16}px;
            }}
        """)
        layout = QHBoxLayout(card)
        if compact:
            layout.setContentsMargins(12, 4, 8, 4)
            layout.setSpacing(10)
        else:
            layout.setContentsMargins(16, 8, 10, 8)
            layout.setSpacing(12)
        layout.addWidget(label_button, 0)
        layout.addStretch(1)
        layout.addWidget(value_button, 0)
        return card

    def _readable_text_color(self, color, dark="#111827", light="#ffffff"):
        qcolor = QColor(color)

        def _channel_luminance(value):
            c = value / 255.0
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        luminance = (
            0.2126 * _channel_luminance(qcolor.red())
            + 0.7152 * _channel_luminance(qcolor.green())
            + 0.0722 * _channel_luminance(qcolor.blue())
        )
        contrast_with_light = 1.05 / (luminance + 0.05)
        contrast_with_dark = (luminance + 0.05) / 0.05
        return light if contrast_with_light >= contrast_with_dark else dark

    def _action_button_preview_icon_color(self, key, mode):
        colors = getattr(self, "_action_button_icon_colors", {})
        value = colors.get(key)
        if not value:
            value = mw.col.conf.get(f"modern_menu_icon_color_{key}", "")
        if value and QColor(value).isValid():
            return value
        return self._deck_icon_color(mode)

    def _action_button_icon_picker_color_options(self, key):
        mode = self._action_buttons_preview_mode()
        return [
            {
                "key": "icon",
                "label": tr("action_button_icon_color", "Button Icon Color"),
                "value": self._action_button_preview_icon_color(key, mode),
            }
        ]

    def _create_boxes_color_effect_group(self):
        designer = QFrame()
        designer.setObjectName("mainBackgroundDesigner")
        outer = QVBoxLayout(designer)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(tr("box_color_and_effect", "Box Color and Effect"))
        title_label.setObjectName("sectionTitle")
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.box_effect_preview_mode = "dark" if theme_manager.night_mode else "light"
        self.box_effect_preview_mode_widget, self.box_effect_preview_mode_toggle = self._create_light_dark_mode_toggle(
            self.box_effect_preview_mode,
            self._on_box_effect_preview_mode_toggled,
        )
        header_layout.addWidget(self.box_effect_preview_mode_widget)

        self.box_effect_reset_button = QPushButton(tr("restore_default"))
        self.box_effect_reset_button.setObjectName("mainBackgroundResetButton")
        self.box_effect_reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.box_effect_reset_button.clicked.connect(self._reset_box_effect_to_default)
        header_layout.addWidget(self.box_effect_reset_button)

        outer.addLayout(header_layout)

        self.box_effect_preview = BackgroundPreviewLabel(aspect_ratio=3.9, minimum_preview_height=95)
        self.box_effect_preview.setObjectName("mainBackgroundPreview")
        self.box_effect_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.box_effect_preview.setProperty("box_effect_preview", True)
        self.box_effect_preview.installEventFilter(self)

        colors = self.current_config.get("colors", {})
        light_color = colors.get("light", {}).get("--canvas-inset", DEFAULTS["colors"]["light"]["--canvas-inset"])
        dark_color = colors.get("dark", {}).get("--canvas-inset", DEFAULTS["colors"]["dark"]["--canvas-inset"])
        color_theme_mode = mw.col.conf.get("onigiri_canvas_inset_color_theme_mode")
        dynamic_default = color_theme_mode != "single"

        legacy_mode = mw.col.conf.get("onigiri_canvas_inset_effect_mode", "none")
        legacy_intensity = int(mw.col.conf.get("onigiri_canvas_inset_effect_intensity", 50) or 50)
        saved_blur = mw.col.conf.get("onigiri_canvas_inset_effect_blur")
        saved_opacity = mw.col.conf.get("onigiri_canvas_inset_effect_opacity")
        saved_radius = mw.col.conf.get("onigiri_canvas_inset_border_radius", 20)
        saved_stroke = mw.col.conf.get("onigiri_canvas_inset_border_width", 1)
        if saved_blur is None:
            saved_blur = legacy_intensity if legacy_mode == "glassmorphism" else 0
        if saved_opacity is None:
            if legacy_mode == "glassmorphism":
                saved_opacity = max(0, min(100, 100 - legacy_intensity))
            elif legacy_mode == "opacity":
                saved_opacity = legacy_intensity
            else:
                saved_opacity = 100

        self.box_effect_light_color_button = self._create_main_bg_button("Color")
        self.box_effect_light_color_value_button = self._create_main_bg_button("")
        self.box_effect_light_color_value_button.setObjectName("mainBackgroundColorButton")
        self.box_effect_dark_color_button = self._create_main_bg_button("Dark Color")
        self.box_effect_dark_color_value_button = self._create_main_bg_button("")
        self.box_effect_dark_color_value_button.setObjectName("mainBackgroundColorButton")

        self.box_effect_border_light_color_button = self._create_main_bg_button("Border Color")
        self.box_effect_border_light_color_value_button = self._create_main_bg_button("")
        self.box_effect_border_light_color_value_button.setObjectName("mainBackgroundColorButton")
        self.box_effect_border_dark_color_button = self._create_main_bg_button("Border Dark")
        self.box_effect_border_dark_color_value_button = self._create_main_bg_button("")
        self.box_effect_border_dark_color_value_button.setObjectName("mainBackgroundColorButton")

        self.box_effect_star_light_color_button = self._create_main_bg_button("Star")
        self.box_effect_star_light_color_value_button = self._create_main_bg_button("")
        self.box_effect_star_light_color_value_button.setObjectName("mainBackgroundColorButton")
        self.box_effect_star_dark_color_button = self._create_main_bg_button("Star Dark")
        self.box_effect_star_dark_color_value_button = self._create_main_bg_button("")
        self.box_effect_star_dark_color_value_button.setObjectName("mainBackgroundColorButton")
        self.box_effect_empty_star_light_color_button = self._create_main_bg_button("Empty Star")
        self.box_effect_empty_star_light_color_value_button = self._create_main_bg_button("")
        self.box_effect_empty_star_light_color_value_button.setObjectName("mainBackgroundColorButton")
        self.box_effect_empty_star_dark_color_button = self._create_main_bg_button("Empty Star Dark")
        self.box_effect_empty_star_dark_color_value_button = self._create_main_bg_button("")
        self.box_effect_empty_star_dark_color_value_button.setObjectName("mainBackgroundColorButton")

        self.box_effect_light_color_card = self._create_color_selector_card(self.box_effect_light_color_button, self.box_effect_light_color_value_button, compact=True)
        self.box_effect_dark_color_card = self._create_color_selector_card(self.box_effect_dark_color_button, self.box_effect_dark_color_value_button, compact=True)
        self.box_effect_border_light_color_card = self._create_color_selector_card(self.box_effect_border_light_color_button, self.box_effect_border_light_color_value_button, compact=True)
        self.box_effect_border_dark_color_card = self._create_color_selector_card(self.box_effect_border_dark_color_button, self.box_effect_border_dark_color_value_button, compact=True)
        self.box_effect_star_light_color_card = self._create_color_selector_card(self.box_effect_star_light_color_button, self.box_effect_star_light_color_value_button)
        self.box_effect_star_dark_color_card = self._create_color_selector_card(self.box_effect_star_dark_color_button, self.box_effect_star_dark_color_value_button)
        self.box_effect_empty_star_light_color_card = self._create_color_selector_card(self.box_effect_empty_star_light_color_button, self.box_effect_empty_star_light_color_value_button)
        self.box_effect_empty_star_dark_color_card = self._create_color_selector_card(self.box_effect_empty_star_dark_color_button, self.box_effect_empty_star_dark_color_value_button)

        slider_palette = self._settings_palette()
        slider_track = slider_palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = slider_palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")

        self.box_effect_blur_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.box_effect_blur_slider.setRange(0, 100)
        self.box_effect_blur_slider.setValue(max(0, min(100, int(saved_blur or 0))))
        self.box_effect_blur_value_label = QLabel(f"{self.box_effect_blur_slider.value()}%")
        self.box_effect_blur_value_label.setObjectName("mainBackgroundValueLabel")
        self.box_effect_blur_value_label.setFixedWidth(48)
        blur_value = QWidget()
        blur_layout = QHBoxLayout(blur_value)
        blur_layout.setContentsMargins(0, 0, 0, 0)
        blur_layout.setSpacing(10)
        blur_layout.addWidget(self.box_effect_blur_slider, 1)
        blur_layout.addWidget(self.box_effect_blur_value_label)

        self.box_effect_opacity_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.box_effect_opacity_slider.setRange(0, 100)
        self.box_effect_opacity_slider.setValue(max(0, min(100, int(saved_opacity or 100))))
        self.box_effect_opacity_value_label = QLabel(f"{self.box_effect_opacity_slider.value()}%")
        self.box_effect_opacity_value_label.setObjectName("mainBackgroundValueLabel")
        self.box_effect_opacity_value_label.setFixedWidth(48)
        opacity_value = QWidget()
        opacity_layout = QHBoxLayout(opacity_value)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(10)
        opacity_layout.addWidget(self.box_effect_opacity_slider, 1)
        opacity_layout.addWidget(self.box_effect_opacity_value_label)

        self.box_effect_radius_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.box_effect_radius_slider.setRange(0, 60)
        self.box_effect_radius_slider.setValue(max(0, min(60, int(saved_radius or 20))))
        self.box_effect_radius_value_label = QLabel(f"{self.box_effect_radius_slider.value()}px")
        self.box_effect_radius_value_label.setObjectName("mainBackgroundValueLabel")
        self.box_effect_radius_value_label.setFixedWidth(48)
        radius_value = QWidget()
        radius_layout = QHBoxLayout(radius_value)
        radius_layout.setContentsMargins(0, 0, 0, 0)
        radius_layout.setSpacing(10)
        radius_layout.addWidget(self.box_effect_radius_slider, 1)
        radius_layout.addWidget(self.box_effect_radius_value_label)

        self.box_effect_stroke_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.box_effect_stroke_slider.setRange(0, 10)
        self.box_effect_stroke_slider.setValue(max(0, min(10, int(saved_stroke or 1))))
        self.box_effect_stroke_value_label = QLabel(f"{self.box_effect_stroke_slider.value()}px")
        self.box_effect_stroke_value_label.setObjectName("mainBackgroundValueLabel")
        self.box_effect_stroke_value_label.setFixedWidth(48)
        stroke_value = QWidget()
        stroke_layout = QHBoxLayout(stroke_value)
        stroke_layout.setContentsMargins(0, 0, 0, 0)
        stroke_layout.setSpacing(10)
        stroke_layout.addWidget(self.box_effect_stroke_slider, 1)
        stroke_layout.addWidget(self.box_effect_stroke_value_label)

        self.box_effect_dynamic_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.box_effect_dynamic_toggle.setChecked(dynamic_default)

        settings_column = QWidget()
        settings_column.setMinimumWidth(0)
        settings_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        settings_column_layout = QVBoxLayout(settings_column)
        settings_column_layout.setContentsMargins(0, 0, 0, 0)
        settings_column_layout.setSpacing(12)
        settings_column_layout.addWidget(self._create_main_bg_value_row("Blur", blur_value))
        settings_column_layout.addWidget(self._create_main_bg_value_row("Opacity", opacity_value))
        settings_column_layout.addWidget(self._create_main_bg_value_row("Radius", radius_value))
        settings_column_layout.addWidget(self._create_main_bg_value_row("Stroke", stroke_value))
        settings_column_layout.addWidget(self._create_main_bg_toggle_row("Dynamic mode", self.box_effect_dynamic_toggle))
        settings_column_layout.addStretch(1)

        outer.addWidget(self.box_effect_preview)

        preview_divider = QFrame()
        preview_divider.setFrameShape(QFrame.Shape.HLine)
        preview_divider.setFrameShadow(QFrame.Shadow.Sunken)
        outer.addWidget(preview_divider)

        retention_section = self._create_box_effect_retention_star_section()
        bottom_columns = ResponsivePairWidget(
            settings_column, retention_section, spacing=18, breakpoint=0,
            left_stretch=1, right_stretch=1
        )
        outer.addWidget(bottom_columns)


        self.box_effect_light_color_input = QLineEdit(light_color)
        self.box_effect_single_color_input = self.box_effect_light_color_input
        self.box_effect_dark_color_input = QLineEdit(dark_color)

        border_light_color = colors.get("light", {}).get("--border", DEFAULTS["colors"]["light"]["--border"])
        border_dark_color = colors.get("dark", {}).get("--border", DEFAULTS["colors"]["dark"]["--border"])
        self.box_effect_border_light_color_input = QLineEdit(border_light_color)
        self.box_effect_border_single_color_input = self.box_effect_border_light_color_input
        self.box_effect_border_dark_color_input = QLineEdit(border_dark_color)

        star_light_color = colors.get("light", {}).get("--star-color", DEFAULTS["colors"]["light"]["--star-color"])
        star_dark_color = colors.get("dark", {}).get("--star-color", DEFAULTS["colors"]["dark"]["--star-color"])
        empty_star_light_color = colors.get("light", {}).get("--empty-star-color", DEFAULTS["colors"]["light"]["--empty-star-color"])
        empty_star_dark_color = colors.get("dark", {}).get("--empty-star-color", DEFAULTS["colors"]["dark"]["--empty-star-color"])
        self.box_effect_star_light_color_input = QLineEdit(star_light_color)
        self.box_effect_star_single_color_input = self.box_effect_star_light_color_input
        self.box_effect_star_dark_color_input = QLineEdit(star_dark_color)
        self.box_effect_empty_star_light_color_input = QLineEdit(empty_star_light_color)
        self.box_effect_empty_star_single_color_input = self.box_effect_empty_star_light_color_input
        self.box_effect_empty_star_dark_color_input = QLineEdit(empty_star_dark_color)

        self.box_effect_light_color_button.clicked.connect(lambda: self._choose_box_effect_color("light", self.box_effect_light_color_button))
        self.box_effect_light_color_value_button.clicked.connect(lambda: self._choose_box_effect_color("light", self.box_effect_light_color_value_button))
        self.box_effect_dark_color_button.clicked.connect(lambda: self._choose_box_effect_color("dark", self.box_effect_dark_color_button))
        self.box_effect_dark_color_value_button.clicked.connect(lambda: self._choose_box_effect_color("dark", self.box_effect_dark_color_value_button))

        self.box_effect_border_light_color_button.clicked.connect(lambda: self._choose_box_effect_color("border_light", self.box_effect_border_light_color_button))
        self.box_effect_border_light_color_value_button.clicked.connect(lambda: self._choose_box_effect_color("border_light", self.box_effect_border_light_color_value_button))
        self.box_effect_border_dark_color_button.clicked.connect(lambda: self._choose_box_effect_color("border_dark", self.box_effect_border_dark_color_button))
        self.box_effect_border_dark_color_value_button.clicked.connect(lambda: self._choose_box_effect_color("border_dark", self.box_effect_border_dark_color_value_button))

        self.box_effect_star_light_color_button.clicked.connect(lambda: self._choose_box_effect_color("star_light", self.box_effect_star_light_color_button))
        self.box_effect_star_light_color_value_button.clicked.connect(lambda: self._choose_box_effect_color("star_light", self.box_effect_star_light_color_value_button))
        self.box_effect_star_dark_color_button.clicked.connect(lambda: self._choose_box_effect_color("star_dark", self.box_effect_star_dark_color_button))
        self.box_effect_star_dark_color_value_button.clicked.connect(lambda: self._choose_box_effect_color("star_dark", self.box_effect_star_dark_color_value_button))
        self.box_effect_empty_star_light_color_button.clicked.connect(lambda: self._choose_box_effect_color("empty_star_light", self.box_effect_empty_star_light_color_button))
        self.box_effect_empty_star_light_color_value_button.clicked.connect(lambda: self._choose_box_effect_color("empty_star_light", self.box_effect_empty_star_light_color_value_button))
        self.box_effect_empty_star_dark_color_button.clicked.connect(lambda: self._choose_box_effect_color("empty_star_dark", self.box_effect_empty_star_dark_color_button))
        self.box_effect_empty_star_dark_color_value_button.clicked.connect(lambda: self._choose_box_effect_color("empty_star_dark", self.box_effect_empty_star_dark_color_value_button))

        self.box_effect_dynamic_toggle.toggled.connect(self._on_box_effect_changed)
        self.box_effect_blur_slider.valueChanged.connect(self._on_box_effect_changed)
        self.box_effect_opacity_slider.valueChanged.connect(self._on_box_effect_changed)
        self.box_effect_radius_slider.valueChanged.connect(self._on_box_effect_changed)
        self.box_effect_stroke_slider.valueChanged.connect(self._on_box_effect_changed)
        for line_edit in (
            self.box_effect_light_color_input, self.box_effect_dark_color_input,
            self.box_effect_border_light_color_input, self.box_effect_border_dark_color_input,
            self.box_effect_star_light_color_input, self.box_effect_star_dark_color_input,
            self.box_effect_empty_star_light_color_input, self.box_effect_empty_star_dark_color_input
        ):
            line_edit.textChanged.connect(lambda _=None: self._on_box_effect_changed())

        self._register_color_sync("palette:light:--star-color", self.box_effect_star_light_color_input)
        self._register_color_sync("palette:dark:--star-color", self.box_effect_star_dark_color_input)
        self._register_color_sync("palette:light:--empty-star-color", self.box_effect_empty_star_light_color_input)
        self._register_color_sync("palette:dark:--empty-star-color", self.box_effect_empty_star_dark_color_input)

        self._update_box_effect_controls()
        return designer

    def _box_effect_color_for_input(self, line_edit, fallback="#ffffff"):
        color = line_edit.text() if line_edit else fallback
        return color if QColor(color).isValid() else fallback

    def _choose_box_effect_color(self, target="single", anchor=None):
        if target == "light":
            line_edit = self.box_effect_light_color_input
        elif target == "dark":
            line_edit = self.box_effect_dark_color_input
        elif target == "border_single":
            line_edit = self.box_effect_border_single_color_input
        elif target == "border_light":
            line_edit = self.box_effect_border_light_color_input
        elif target == "border_dark":
            line_edit = self.box_effect_border_dark_color_input
        elif target == "star_single":
            line_edit = self.box_effect_star_single_color_input
        elif target == "star_light":
            line_edit = self.box_effect_star_light_color_input
        elif target == "star_dark":
            line_edit = self.box_effect_star_dark_color_input
        elif target == "empty_star_single":
            line_edit = self.box_effect_empty_star_single_color_input
        elif target == "empty_star_light":
            line_edit = self.box_effect_empty_star_light_color_input
        elif target == "empty_star_dark":
            line_edit = self.box_effect_empty_star_dark_color_input
        else:
            line_edit = self.box_effect_single_color_input
        chosen, ok = OnigiriColorDialog.getColor(line_edit.text(), self, anchor=anchor)
        if ok:
            line_edit.setText(chosen)
            self._update_box_effect_controls()

    def _retention_star_picker_color_options(self):
        if hasattr(self, "box_effect_dynamic_toggle") and not self.box_effect_dynamic_toggle.isChecked():
            return [
                {
                    "key": "star_light",
                    "mode": "single",
                    "label": "Star",
                    "value": self._box_effect_color_for_input(self.box_effect_star_single_color_input, DEFAULTS["colors"]["light"].get("--star-color", "#FFD700")),
                },
                {
                    "key": "empty_light",
                    "mode": "single",
                    "label": "Empty Star",
                    "value": self._box_effect_color_for_input(self.box_effect_empty_star_single_color_input, DEFAULTS["colors"]["light"].get("--empty-star-color", "#E0E0E0")),
                },
            ]
        return [
            {
                "key": "star_light",
                "label": "Star Light",
                "value": self._box_effect_color_for_input(self.box_effect_star_light_color_input, DEFAULTS["colors"]["light"].get("--star-color", "#FFD700")),
            },
            {
                "key": "star_dark",
                "label": "Star Dark",
                "value": self._box_effect_color_for_input(self.box_effect_star_dark_color_input, DEFAULTS["colors"]["dark"].get("--star-color", "#FFD700")),
            },
            {
                "key": "empty_light",
                "label": "Empty Star Light",
                "value": self._box_effect_color_for_input(self.box_effect_empty_star_light_color_input, DEFAULTS["colors"]["light"].get("--empty-star-color", "#E0E0E0")),
            },
            {
                "key": "empty_dark",
                "label": "Empty Star Dark",
                "value": self._box_effect_color_for_input(self.box_effect_empty_star_dark_color_input, DEFAULTS["colors"]["dark"].get("--empty-star-color", "#4A4A4A")),
            },
        ]

    def _apply_retention_star_picker_colors(self, values):
        if hasattr(self, "box_effect_dynamic_toggle") and not self.box_effect_dynamic_toggle.isChecked():
            star_value = values.get("star_light")
            empty_value = values.get("empty_light")
            if star_value and QColor(star_value).isValid():
                self.box_effect_star_single_color_input.setText(star_value)
            if empty_value and QColor(empty_value).isValid():
                self.box_effect_empty_star_single_color_input.setText(empty_value)
            self._update_icon_preview_for_widget(self.retention_star_widget)
            self._update_box_effect_controls()
            return

        mapping = {
            "star_light": self.box_effect_star_light_color_input,
            "star_dark": self.box_effect_star_dark_color_input,
            "empty_light": self.box_effect_empty_star_light_color_input,
            "empty_dark": self.box_effect_empty_star_dark_color_input,
        }
        for key, line_edit in mapping.items():
            value = values.get(key)
            if value and QColor(value).isValid():
                line_edit.setText(value)
        self._update_icon_preview_for_widget(self.retention_star_widget)
        self._update_box_effect_controls()

    def _sync_box_effect_color_config(self):
        if not hasattr(self, "box_effect_single_color_input"):
            return
        dynamic = self.box_effect_dynamic_toggle.isChecked()
        single_color = self._box_effect_color_for_input(self.box_effect_single_color_input)
        light_color = self._box_effect_color_for_input(self.box_effect_light_color_input, single_color) if dynamic else single_color
        dark_color = self._box_effect_color_for_input(self.box_effect_dark_color_input, single_color) if dynamic else single_color
        self.current_config.setdefault("colors", {}).setdefault("light", {})["--canvas-inset"] = light_color
        self.current_config.setdefault("colors", {}).setdefault("dark", {})["--canvas-inset"] = dark_color

        border_single_color = self._box_effect_color_for_input(self.box_effect_border_single_color_input)
        border_light_color = self._box_effect_color_for_input(self.box_effect_border_light_color_input, border_single_color) if dynamic else border_single_color
        border_dark_color = self._box_effect_color_for_input(self.box_effect_border_dark_color_input, border_single_color) if dynamic else border_single_color
        self.current_config.setdefault("colors", {}).setdefault("light", {})["--border"] = border_light_color
        self.current_config.setdefault("colors", {}).setdefault("dark", {})["--border"] = border_dark_color

        star_single_color = self._box_effect_color_for_input(self.box_effect_star_single_color_input)
        star_light_color = self._box_effect_color_for_input(self.box_effect_star_light_color_input, star_single_color) if dynamic else star_single_color
        star_dark_color = self._box_effect_color_for_input(self.box_effect_star_dark_color_input, star_single_color) if dynamic else star_single_color
        empty_star_single_color = self._box_effect_color_for_input(self.box_effect_empty_star_single_color_input)
        empty_star_light_color = self._box_effect_color_for_input(self.box_effect_empty_star_light_color_input, empty_star_single_color) if dynamic else empty_star_single_color
        empty_star_dark_color = self._box_effect_color_for_input(self.box_effect_empty_star_dark_color_input, empty_star_single_color) if dynamic else empty_star_single_color
        self.current_config.setdefault("colors", {}).setdefault("light", {})["--star-color"] = star_light_color
        self.current_config.setdefault("colors", {}).setdefault("dark", {})["--star-color"] = star_dark_color
        self.current_config.setdefault("colors", {}).setdefault("light", {})["--empty-star-color"] = empty_star_light_color
        self.current_config.setdefault("colors", {}).setdefault("dark", {})["--empty-star-color"] = empty_star_dark_color

        for mode, value in (("light", light_color), ("dark", dark_color)):
            widget = self.color_widgets.get(mode, {}).get("--canvas-inset")
            if widget and not (sip is not None and sip.isdeleted(widget)) and widget.text() != value:
                blocker = QSignalBlocker(widget)
                widget.setText(value)
                del blocker

        for mode, value in (("light", border_light_color), ("dark", border_dark_color)):
            widget = self.color_widgets.get(mode, {}).get("--border")
            if widget and not (sip is not None and sip.isdeleted(widget)) and widget.text() != value:
                blocker = QSignalBlocker(widget)
                widget.setText(value)
                del blocker

        for mode, values in (
            ("light", (("--star-color", star_light_color), ("--empty-star-color", empty_star_light_color))),
            ("dark", (("--star-color", star_dark_color), ("--empty-star-color", empty_star_dark_color))),
        ):
            for key, value in values:
                widget = self.color_widgets.get(mode, {}).get(key)
                if widget and not (sip is not None and sip.isdeleted(widget)) and widget.text() != value:
                    blocker = QSignalBlocker(widget)
                    widget.setText(value)
                    del blocker

    def _box_effect_color(self, mode):
        if self.box_effect_dynamic_toggle.isChecked():
            line_edit = self.box_effect_dark_color_input if mode == "dark" else self.box_effect_light_color_input
            fallback = DEFAULTS["colors"][mode]["--canvas-inset"]
            return self._box_effect_color_for_input(line_edit, fallback)
        return self._box_effect_color_for_input(self.box_effect_single_color_input)

    def _box_effect_text_color(self, mode):
        mode = "dark" if mode == "dark" else "light"
        return self.current_config.get("colors", {}).get(mode, {}).get("--fg", DEFAULTS["colors"][mode]["--fg"])

    def _box_effect_title_color(self, mode):
        mode = "dark" if mode == "dark" else "light"
        return self.current_config.get("colors", {}).get(mode, {}).get("--fg-subtle", DEFAULTS["colors"][mode]["--fg-subtle"])

    def _box_effect_small_title_color(self, mode):
        mode = "dark" if mode == "dark" else "light"
        return self.current_config.get("colors", {}).get(mode, {}).get("--fg-subtle", DEFAULTS["colors"][mode]["--fg-subtle"])

    def _box_effect_border_color(self, mode):
        mode = "dark" if mode == "dark" else "light"
        return self.current_config.get("colors", {}).get(mode, {}).get("--border", DEFAULTS["colors"][mode]["--border"])

    def _box_effect_icon_color(self, mode):
        mode = "dark" if mode == "dark" else "light"
        return self.current_config.get("colors", {}).get(mode, {}).get("--empty-star-color", DEFAULTS["colors"][mode]["--empty-star-color"])

    def _box_effect_star_color(self, mode, filled):
        mode = "dark" if mode == "dark" else "light"
        color_key = "--star-color" if filled else "--empty-star-color"
        if hasattr(self, "box_effect_dynamic_toggle"):
            if filled:
                if self.box_effect_dynamic_toggle.isChecked():
                    line_edit = self.box_effect_star_dark_color_input if mode == "dark" else self.box_effect_star_light_color_input
                    fallback = DEFAULTS["colors"][mode]["--star-color"]
                    return self._box_effect_color_for_input(line_edit, fallback)
                return self._box_effect_color_for_input(self.box_effect_star_single_color_input, DEFAULTS["colors"]["light"]["--star-color"])
            if self.box_effect_dynamic_toggle.isChecked():
                line_edit = self.box_effect_empty_star_dark_color_input if mode == "dark" else self.box_effect_empty_star_light_color_input
                fallback = DEFAULTS["colors"][mode]["--empty-star-color"]
                return self._box_effect_color_for_input(line_edit, fallback)
            return self._box_effect_color_for_input(self.box_effect_empty_star_single_color_input, DEFAULTS["colors"]["light"]["--empty-star-color"])
        return self.current_config.get("colors", {}).get(mode, {}).get(color_key, DEFAULTS["colors"][mode][color_key])

    def _deck_icon_color(self, mode):
        mode = "dark" if mode == "dark" else "light"
        return self.current_config.get("colors", {}).get(mode, {}).get("--icon-color", DEFAULTS["colors"][mode]["--icon-color"])

    def _deck_icon_filtered_color(self, mode):
        mode = "dark" if mode == "dark" else "light"
        return self.current_config.get("colors", {}).get(mode, {}).get("--icon-color-filtered", DEFAULTS["colors"][mode]["--icon-color-filtered"])

    def _deck_icon_highlight_color(self, mode):
        mode = "dark" if mode == "dark" else "light"
        return self.current_config.get("colors", {}).get(mode, {}).get("--highlight-bg", DEFAULTS["colors"][mode]["--highlight-bg"])

    def _deck_icon_text_color(self, mode):
        mode = "dark" if mode == "dark" else "light"
        return self.current_config.get("colors", {}).get(mode, {}).get("--fg", DEFAULTS["colors"][mode]["--fg"])

    def _deck_icon_picker_color_options(self):
        return [
            {
                "key": "light_icon",
                "label": tr("deck_icon_color", "Deck Icon"),
                "value": self._deck_icon_color("light"),
            },
            {
                "key": "light_filtered",
                "label": tr("filtered_deck_icon", "Filtered Deck Icon"),
                "value": self._deck_icon_filtered_color("light"),
            },
            {
                "key": "dark_icon",
                "label": tr("deck_icon_dark_color", "Deck Icon Dark"),
                "value": self._deck_icon_color("dark"),
            },
            {
                "key": "dark_filtered",
                "label": tr("filtered_deck_icon_dark_color", "Filtered Deck Icon Dark"),
                "value": self._deck_icon_filtered_color("dark"),
            },
        ]

    def _apply_deck_icon_picker_colors(self, values):
        mapping = {
            "light_icon": ("light", "--icon-color"),
            "light_filtered": ("light", "--icon-color-filtered"),
            "dark_icon": ("dark", "--icon-color"),
            "dark_filtered": ("dark", "--icon-color-filtered"),
        }
        for key, (mode, color_key) in mapping.items():
            value = values.get(key)
            widget = self.color_widgets.get(mode, {}).get(color_key)
            if value and QColor(value).isValid() and widget is not None:
                widget.setText(value)
                self.current_config.setdefault("colors", {}).setdefault(mode, {})[color_key] = value
        for widget in getattr(self, "icon_assignment_widgets", []):
            self._update_icon_preview_for_widget(widget)
        self._update_deck_icon_preview()

    def _language_selector_color(self, lang_name):
        colors = {
            "English (Default)": "#3C3B6E",
            "Português (Brasil)": "#009B3A",
            "Español (España)": "#AA151B",
            "简体中文": "#DE2910",
            "日本語": "#BC002D",
            "Français": "#0055A4",
            "한국어": "#0047A0",
        }
        return colors.get(lang_name, getattr(self, "accent_color", "#00A982"))

    def _register_color_sync(self, sync_key, line_edit):
        # Keeps independently-created QLineEdits (e.g. a feature's own color card
        # and its Gallery tile) mirrored, since they aren't the same widget instance.
        group = self._color_sync_groups.setdefault(sync_key, [])
        if line_edit in group:
            return
        group.append(line_edit)
        line_edit.textChanged.connect(
            lambda value, k=sync_key, w=line_edit: self._relay_color_sync(k, value, w)
        )

    def _relay_color_sync(self, sync_key, value, origin):
        if self._color_sync_guard == sync_key or not QColor(value).isValid():
            return
        self._color_sync_guard = sync_key
        try:
            for widget in list(self._color_sync_groups.get(sync_key, [])):
                if widget is origin:
                    continue
                try:
                    if sip is not None and sip.isdeleted(widget):
                        continue
                except Exception:
                    continue
                if widget.text() != value:
                    widget.setText(value)
        finally:
            self._color_sync_guard = None

    def _build_color_sections(self, parent_layout, mode):
        sections = {
            tr("general"): ["--border"],
        }
        
        handled_keys = {key for keys in sections.values() for key in keys}

        for title, keys in sections.items():
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)

            title_label = QLabel(title)
            title_label.setStyleSheet("font-weight: bold; margin-top: 10px; margin-bottom: 5px;")
            layout.addWidget(title_label)
            
            self._populate_pills_for_keys(layout, mode, keys)
            parent_layout.addWidget(container)

    def _create_color_pill(self, name, default_value, mode, label_info):
        widget = QFrame()
        widget.setObjectName("newColorPill")
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        widget.setMinimumHeight(48)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        label_text = tr(label_info['label'])
        tooltip = tr(label_info.get("tooltip", ""))
        widget.setToolTip(f"{label_text}: {tooltip}")
        
        border_color = "#4a4a4a" if theme_manager.night_mode else "#dcdde1"
        hover_bg = "rgba(255,255,255,0.05)" if theme_manager.night_mode else "rgba(0,0,0,0.03)"
        
        widget.setStyleSheet(f"""
            QFrame#newColorPill {{
                background-color: transparent;
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
            QFrame#newColorPill:hover {{
                background-color: {hover_bg};
            }}
        """)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(15, 8, 12, 8)

        name_label = QLabel(label_text)
        name_label.setStyleSheet("font-weight: bold; border: none; background: transparent;")
        name_label.setWordWrap(True)
        name_label.setMinimumWidth(0)
        name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        hex_input = QLineEdit(default_value)
        hex_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hex_input.setFixedWidth(110)
        hex_input.setFixedHeight(32)
        hex_input.setCursor(Qt.CursorShape.PointingHandCursor)
        hex_input.setReadOnly(True)
        
        def update_hex_style(hex_str):
            try:
                color = QColor(hex_str)
                if not color.isValid():
                    return
                r, g, b = color.red(), color.green(), color.blue()
                luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                text_color = "#000000" if luminance > 0.5 else "#FFFFFF"
                hex_input.setStyleSheet(f"""
                    QLineEdit {{
                        background-color: {color.name()};
                        color: {text_color};
                        border: none;
                        border-radius: 10px;
                        font-family: monospace;
                        font-weight: bold;
                        font-size: 13px;
                    }}
                    QLineEdit:focus {{
                        border: 2px solid {theme_manager.accent_color if hasattr(theme_manager, 'accent_color') else '#3399ff'};
                    }}
                """)
            except:
                pass
                
        update_hex_style(default_value)
        hex_input.textChanged.connect(update_hex_style)
        hex_input.textChanged.connect(lambda value, m=mode, key=name: self._on_palette_color_changed(m, key, value))
        
        widget.mousePressEvent = lambda event, le=hex_input: self.open_color_picker(le, le)
        hex_input.mousePressEvent = lambda event, le=hex_input: self.open_color_picker(le, le)

        layout.addWidget(name_label, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(hex_input, 0, Qt.AlignmentFlag.AlignVCenter)

        if mode in ["light", "dark"]:
            self.color_widgets[mode][name] = hex_input

        return widget

    def _on_palette_color_changed(self, mode, key, value):
        color = QColor(value)
        if mode not in ["light", "dark"] or not color.isValid():
            return
        self.current_config.setdefault("colors", {}).setdefault(mode, {})[key] = value
        if key == "--accent-color" and ((theme_manager.night_mode and mode == "dark") or (not theme_manager.night_mode and mode == "light")):
            self.accent_color = value
        if key in {"--star-color", "--empty-star-color"} and hasattr(self, "box_effect_preview"):
            self._update_box_effect_preview()
        if key in {"--icon-color", "--icon-color-filtered", "--highlight-bg", "--fg"} and hasattr(self, "deck_icon_preview"):
            self._update_deck_icon_preview()
        if (theme_manager.night_mode and mode == "dark") or (not theme_manager.night_mode and mode == "light"):
            self._schedule_stylesheet_apply()

    def _create_color_picker_row(self, name, default_value, mode, label_override=None, tooltip_text=None):
        row_layout=QHBoxLayout()
        display_name = label_override if label_override is not None else name
        label=QLabel(f"{display_name}:")
        if tooltip_text: label.setToolTip(tooltip_text)
        label.setMinimumWidth(120)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        hex_input=QLineEdit(default_value)
        hex_input.setFixedWidth(100)
        color_button = CircularColorButton(default_value)
        
        color_button.clicked.connect(lambda _, le=hex_input, btn=color_button: self.open_color_picker(le, btn))
        hex_input.textChanged.connect(lambda txt, btn=color_button: btn.setColor(txt))
        if mode in ["light_accent", "dark_accent"]:
            hex_input.textChanged.connect(lambda txt, m=mode: self._on_settings_accent_changed(m, txt))
        
        row_layout.addWidget(label)
        row_layout.addWidget(hex_input)
        row_layout.addWidget(color_button)
        row_layout.addStretch()
        
        if mode in ["light", "dark"]: self.color_widgets[mode][name] = hex_input
        elif mode in ["light_accent", "dark_accent"]: setattr(self, f"{mode}_color_input", hex_input)
        else: setattr(self, f"{mode}_color_input", hex_input)
        return row_layout

    def open_color_picker(self, line_edit, button):
        color_name, ok = OnigiriColorDialog.getColor(line_edit.text(), self, anchor=button)
        if ok:
            line_edit.setText(color_name)
            if isinstance(button, CircularColorButton):
                button.setColor(color_name)

    def reset_colors_to_default(self):
        default_colors=DEFAULTS["colors"]
        for mode in["light","dark"]:
            if hasattr(self,f"{mode}_accent_color_input"):getattr(self,f"{mode}_accent_color_input").setText(default_colors[mode]["--accent-color"])
            for name,widget in self.color_widgets[mode].items():
                if name in default_colors[mode]:widget.setText(default_colors[mode][name])
        if hasattr(self, "box_effect_preview"):
            self._reset_box_effect_to_default()

    def _save_colors_settings(self):
        for mode in ["light", "dark"]:
            accent_widget = getattr(self, f"{mode}_accent_color_input", None) or self.color_widgets.get(mode, {}).get("--accent-color")
            if accent_widget is not None:
                self.current_config["colors"][mode]["--accent-color"] = accent_widget.text()

        # Explicitly define which color keys belong to the Palette page's "General Palette".
        palette_keys = {
            "--border"
        }
        
        for mode in ["light", "dark"]:
            # Iterate only over the keys this page is responsible for.
            for key in palette_keys:
                # Check that the widget for this key has been loaded before trying to save it.
                if key in self.color_widgets[mode]:
                    widget = self.color_widgets[mode][key]
                    self.current_config["colors"][mode][key] = widget.text()

        self._save_box_effect_settings()
