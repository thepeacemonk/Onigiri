# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *



class PageProfileMixin:
    def show_profile_page(self):
        if btn := self.sidebar_button_group.checkedButton():
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
        if hasattr(self, "page_title_label"):
            if hasattr(self, "settings_page_header"):
                self.settings_page_header.setVisible(True)
            self.page_title_label.setVisible(True)
            self.page_title_label.setText(tr("profile"))
        
        profile_index = self.page_order.index("Profile")
        
        if not self.tabs_loaded.get(profile_index):
            create_func = self.pages["Profile"]
            self._building_page_name = "Profile"
            new_widget = create_func()
            self._building_page_name = None
            self._polish_created_page(new_widget)
            
            old_widget = self.content_stack.widget(profile_index)
            self.content_stack.removeWidget(old_widget)
            self.content_stack.insertWidget(profile_index, new_widget)
            old_widget.deleteLater()
            self.tabs_loaded[profile_index] = True
            
        self.content_stack.setCurrentIndex(profile_index)
        self._current_page_name = "Profile"
        self._populate_page_nav("Profile")
        self._animate_page_transition()

    def _profile_asset_folder_path(self, key):
        folder = "profile" if str(key).startswith("profile_pic") else "profile_bg"
        path = os.path.join(self.addon_path, "user_files", folder)
        os.makedirs(path, exist_ok=True)
        return path

    def _profile_asset_image_files(self, key):
        try:
            return sorted([
                f for f in os.listdir(self._profile_asset_folder_path(key))
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
            ])
        except OSError:
            return []

    def _profile_asset_image_path(self, key, filename):
        return os.path.join(self._profile_asset_folder_path(key), filename) if filename else ""

    def _profile_default_asset_path(self, key):
        filename = "onigiri-san.png" if str(key).startswith("profile_pic") else "onigiri-bg.png"
        return os.path.join(self.addon_path, "system_files", "profile_default", filename)

    def _create_profile_segment_button(self, text):
        button = self._create_main_bg_button(text)
        button.setCheckable(True)
        button.setMinimumWidth(170)
        return button

    def _style_profile_segment_button(self, button, active):
        palette = self._settings_palette()
        neutral = palette.get("--highlight-bg", "#f3f4f6")
        fg = palette.get("--fg", "#111827")
        active_fg = "#ffffff" if QColor(self.accent_color).lightness() < 150 else "#111827"
        bg = self.accent_color if active else neutral
        color = active_fg if active else fg
        button.setStyleSheet(f"""
            QPushButton#mainBackgroundButton {{
                background-color: {bg};
                color: {color};
                border: 1px solid {bg};
                border-radius: 12px;
                padding: 0px 14px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#mainBackgroundButton:hover,
            QPushButton#mainBackgroundButton:pressed,
            QPushButton#mainBackgroundButton:checked {{
                background-color: {bg};
                color: {color};
                border: 1px solid {bg};
                border-radius: 12px;
            }}
        """)

    def _create_profile_asset_designer(self):
        self.galleries["profile_pic"] = {
            "selected": mw.col.conf.get("modern_menu_profile_picture", ""),
            "folder": "user_files/profile",
            "extensions": (".png", ".jpg", ".jpeg", ".gif", ".webp"),
        }
        self.galleries["profile_pic_light"] = {
            "selected": mw.col.conf.get("modern_menu_profile_picture_light", mw.col.conf.get("modern_menu_profile_picture", "")),
            "folder": "user_files/profile",
            "extensions": (".png", ".jpg", ".jpeg", ".gif", ".webp"),
        }
        self.galleries["profile_pic_dark"] = {
            "selected": mw.col.conf.get("modern_menu_profile_picture_dark", mw.col.conf.get("modern_menu_profile_picture", "")),
            "folder": "user_files/profile",
            "extensions": (".png", ".jpg", ".jpeg", ".gif", ".webp"),
        }
        self.galleries["profile_bg"] = {
            "selected": mw.col.conf.get("modern_menu_profile_bg_image", ""),
            "folder": "user_files/profile_bg",
            "extensions": (".png", ".jpg", ".jpeg", ".gif", ".webp"),
        }

        designer = QFrame()
        designer.setObjectName("mainBackgroundDesigner")
        outer = QVBoxLayout(designer)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        segment_shell = QFrame()
        segment_shell.setObjectName("profileAssetSegmentShell")
        segment_layout = QHBoxLayout(segment_shell)
        segment_layout.setContentsMargins(8, 8, 8, 8)
        segment_layout.setSpacing(8)
        segment_layout.addStretch()
        self.profile_picture_segment_button = self._create_profile_segment_button(tr("profile_picture"))
        self.profile_background_segment_button = self._create_profile_segment_button(tr("profile_bar_bg"))
        self.profile_page_background_segment_button = self._create_profile_segment_button(tr("profile_page_background"))
        self.profile_page_background_segment_button.setVisible(False)
        segment_layout.addWidget(self.profile_picture_segment_button)
        segment_layout.addWidget(self.profile_background_segment_button)
        segment_layout.addStretch()
        outer.addWidget(segment_shell)

        self.profile_asset_preview = BackgroundPreviewLabel(aspect_ratio=5.0, minimum_preview_height=130)
        self.profile_asset_preview.setObjectName("mainBackgroundPreview")
        self.profile_asset_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_asset_preview.setProperty("profile_asset_preview", True)
        self.profile_asset_preview.installEventFilter(self)
        outer.addWidget(self.profile_asset_preview)

        self.profile_asset_controls_stack = QStackedWidget()
        self.profile_asset_controls_stack.addWidget(self._create_profile_picture_controls())
        self.profile_asset_controls_stack.addWidget(self._create_profile_background_controls())
        outer.addWidget(self.profile_asset_controls_stack)

        self.profile_picture_segment_button.clicked.connect(lambda: self._set_profile_asset_page(0))
        self.profile_background_segment_button.clicked.connect(lambda: self._set_profile_asset_page(1))
        self._set_profile_asset_page(0)
        self._update_profile_picture_controls()
        self._update_profile_background_controls()
        return designer

    def _create_profile_picture_controls(self):
        widget = QWidget()
        outer = QHBoxLayout(widget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(18)

        left = QWidget()
        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        left_layout = QGridLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setHorizontalSpacing(10)
        left_layout.setVerticalSpacing(10)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.profile_pic_import_button = self._create_main_bg_button("Import")
        self.profile_pic_clear_button = self._create_main_bg_button("Clear image")
        self.profile_pic_gallery_button = self._create_main_bg_button("Select from your Gallery")
        self.profile_pic_light_color_button = self._create_main_bg_button("Color")
        self.profile_pic_light_color_value_button = self._create_main_bg_button("")
        self.profile_pic_light_color_value_button.setObjectName("mainBackgroundColorButton")
        self.profile_pic_dark_color_button = self._create_main_bg_button("Dark Color")
        self.profile_pic_dark_color_value_button = self._create_main_bg_button("")
        self.profile_pic_dark_color_value_button.setObjectName("mainBackgroundColorButton")

        self.profile_pic_light_color_card = self._create_color_selector_card(self.profile_pic_light_color_button, self.profile_pic_light_color_value_button)
        self.profile_pic_dark_color_card = self._create_color_selector_card(self.profile_pic_dark_color_button, self.profile_pic_dark_color_value_button)

        left_layout.addWidget(self.profile_pic_import_button, 0, 0)
        left_layout.addWidget(self.profile_pic_clear_button, 0, 1)
        left_layout.addWidget(self.profile_pic_gallery_button, 1, 0, 1, 2)
        left_layout.addWidget(self.profile_pic_light_color_card, 2, 0, 1, 2)
        left_layout.addWidget(self.profile_pic_dark_color_card, 3, 0, 1, 2)
        left_layout.setRowStretch(4, 1)

        slider_palette = self._settings_palette()
        slider_track = slider_palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = slider_palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")


        self.profile_pic_opacity_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.profile_pic_opacity_slider.setRange(0, 100)
        saved_pic_opacity = mw.col.conf.get("modern_menu_profile_picture_opacity", 100)
        self.profile_pic_opacity_slider.setValue(max(0, min(100, int(100 if saved_pic_opacity is None else saved_pic_opacity))))
        self.profile_pic_opacity_value_label = QLabel(f"{self.profile_pic_opacity_slider.value()}%")
        self.profile_pic_opacity_value_label.setObjectName("mainBackgroundValueLabel")
        self.profile_pic_opacity_value_label.setFixedWidth(48)
        opacity_value = QWidget()
        opacity_layout = QHBoxLayout(opacity_value)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(10)
        opacity_layout.addWidget(self.profile_pic_opacity_slider, 1)
        opacity_layout.addWidget(self.profile_pic_opacity_value_label)

        pic_mode = mw.col.conf.get("modern_menu_profile_picture_mode", "image")
        self.profile_pic_dynamic_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.profile_pic_color_only_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.profile_pic_accent_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.profile_pic_dynamic_toggle.setChecked(bool(mw.col.conf.get("modern_menu_profile_picture_dynamic_mode", True)))
        self.profile_pic_color_only_toggle.setChecked(pic_mode != "image")
        self.profile_pic_accent_toggle.setChecked(pic_mode == "accent")

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        right_layout.addWidget(self._create_main_bg_value_row("Opacity", opacity_value))
        right_layout.addWidget(self._create_main_bg_toggle_row("Dynamic mode", self.profile_pic_dynamic_toggle))
        right_layout.addWidget(self._create_main_bg_toggle_row("Color only", self.profile_pic_color_only_toggle))
        right_layout.addWidget(self._create_main_bg_toggle_row("Accent color", self.profile_pic_accent_toggle))
        right_layout.addStretch()

        self.profile_pic_light_color_input = QLineEdit(mw.col.conf.get("modern_menu_profile_picture_color_light", "#8CACB4"))
        self.profile_pic_single_color_input = self.profile_pic_light_color_input
        self.profile_pic_dark_color_input = QLineEdit(mw.col.conf.get("modern_menu_profile_picture_color_dark", "#B8BDC3"))

        self.profile_pic_import_button.clicked.connect(lambda: self._import_profile_asset("profile_pic"))
        self.profile_pic_clear_button.clicked.connect(lambda: self._clear_profile_asset("profile_pic"))
        self.profile_pic_gallery_button.clicked.connect(lambda: self._open_profile_asset_gallery("profile_pic"))
        self.profile_pic_light_color_button.clicked.connect(lambda: self._choose_profile_pic_color("light"))
        self.profile_pic_light_color_value_button.clicked.connect(lambda: self._choose_profile_pic_color("light"))
        self.profile_pic_dark_color_button.clicked.connect(lambda: self._choose_profile_pic_color("dark"))
        self.profile_pic_dark_color_value_button.clicked.connect(lambda: self._choose_profile_pic_color("dark"))
        self.profile_pic_accent_toggle.toggled.connect(lambda checked: self.profile_pic_color_only_toggle.setChecked(True) if checked else None)
        self.profile_pic_color_only_toggle.toggled.connect(lambda checked: self.profile_pic_accent_toggle.setChecked(False) if not checked else None)
        for control in (
            self.profile_pic_dynamic_toggle,
            self.profile_pic_color_only_toggle,
            self.profile_pic_accent_toggle,
            self.profile_pic_opacity_slider,
        ):
            control.toggled.connect(self._update_profile_picture_controls) if hasattr(control, "toggled") else control.valueChanged.connect(self._update_profile_picture_controls)
        for line_edit in (self.profile_pic_light_color_input, self.profile_pic_dark_color_input):
            line_edit.textChanged.connect(lambda _=None: self._update_profile_picture_controls())

        outer.addWidget(ResponsivePairWidget(left, right, spacing=18, breakpoint=720))
        return widget

    def _create_profile_background_controls(self):
        widget = QWidget()
        outer = QHBoxLayout(widget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(18)

        left = QWidget()
        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        left_layout = QGridLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setHorizontalSpacing(10)
        left_layout.setVerticalSpacing(10)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.profile_bg_import_button = self._create_main_bg_button("Import")
        self.profile_bg_clear_button = self._create_main_bg_button("Clear image")
        self.profile_bg_gallery_button = self._create_main_bg_button("Select from your Gallery")
        self.profile_bg_light_color_button = self._create_main_bg_button("Color")
        self.profile_bg_light_color_value_button = self._create_main_bg_button("")
        self.profile_bg_light_color_value_button.setObjectName("mainBackgroundColorButton")
        self.profile_bg_dark_color_button = self._create_main_bg_button("Dark Color")
        self.profile_bg_dark_color_value_button = self._create_main_bg_button("")
        self.profile_bg_dark_color_value_button.setObjectName("mainBackgroundColorButton")

        self.profile_bg_light_color_card = self._create_color_selector_card(self.profile_bg_light_color_button, self.profile_bg_light_color_value_button)
        self.profile_bg_dark_color_card = self._create_color_selector_card(self.profile_bg_dark_color_button, self.profile_bg_dark_color_value_button)

        left_layout.addWidget(self.profile_bg_import_button, 0, 0)
        left_layout.addWidget(self.profile_bg_clear_button, 0, 1)
        left_layout.addWidget(self.profile_bg_gallery_button, 1, 0, 1, 2)
        left_layout.addWidget(self.profile_bg_light_color_card, 2, 0, 1, 2)
        left_layout.addWidget(self.profile_bg_dark_color_card, 3, 0, 1, 2)
        left_layout.setRowStretch(4, 1)

        slider_palette = self._settings_palette()
        slider_track = slider_palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = slider_palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")
        self.profile_bg_blur_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.profile_bg_blur_slider.setRange(0, 100)
        self.profile_bg_blur_slider.setValue(max(0, min(100, int(mw.col.conf.get("modern_menu_profile_bg_blur", 0) or 0))))
        self.profile_bg_blur_value_label = QLabel(f"{self.profile_bg_blur_slider.value()}%")
        self.profile_bg_blur_value_label.setObjectName("mainBackgroundValueLabel")
        self.profile_bg_blur_value_label.setFixedWidth(48)
        blur_value = QWidget()
        blur_layout = QHBoxLayout(blur_value)
        blur_layout.setContentsMargins(0, 0, 0, 0)
        blur_layout.setSpacing(10)
        blur_layout.addWidget(self.profile_bg_blur_slider, 1)
        blur_layout.addWidget(self.profile_bg_blur_value_label)

        self.profile_bg_opacity_slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
        self.profile_bg_opacity_slider.setRange(0, 100)
        saved_profile_opacity = mw.col.conf.get("modern_menu_profile_bg_opacity", 100)
        self.profile_bg_opacity_slider.setValue(max(0, min(100, int(100 if saved_profile_opacity is None else saved_profile_opacity))))
        self.profile_bg_opacity_value_label = QLabel(f"{self.profile_bg_opacity_slider.value()}%")
        self.profile_bg_opacity_value_label.setObjectName("mainBackgroundValueLabel")
        self.profile_bg_opacity_value_label.setFixedWidth(48)
        opacity_value = QWidget()
        opacity_layout = QHBoxLayout(opacity_value)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(10)
        opacity_layout.addWidget(self.profile_bg_opacity_slider, 1)
        opacity_layout.addWidget(self.profile_bg_opacity_value_label)

        self.profile_bg_dynamic_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.profile_bg_color_only_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.profile_bg_accent_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "accent")
        self.profile_bg_dynamic_toggle.setChecked(bool(mw.col.conf.get("modern_menu_profile_bg_dynamic_mode", True)))
        self.profile_bg_color_only_toggle.setChecked(bg_mode != "image")
        self.profile_bg_accent_toggle.setChecked(bg_mode == "accent")

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        right_layout.addWidget(self._create_main_bg_value_row("Blur", blur_value))
        right_layout.addWidget(self._create_main_bg_value_row("Opacity", opacity_value))
        right_layout.addWidget(self._create_main_bg_toggle_row("Dynamic mode", self.profile_bg_dynamic_toggle))
        right_layout.addWidget(self._create_main_bg_toggle_row("Color only", self.profile_bg_color_only_toggle))
        right_layout.addWidget(self._create_main_bg_toggle_row("Accent color", self.profile_bg_accent_toggle))
        right_layout.addStretch()

        self.profile_bg_light_color_input = QLineEdit(mw.col.conf.get("modern_menu_profile_bg_color_light", "#EEEEEE"))
        self.profile_bg_single_color_input = self.profile_bg_light_color_input
        self.profile_bg_dark_color_input = QLineEdit(mw.col.conf.get("modern_menu_profile_bg_color_dark", "#3C3C3C"))

        self.profile_bg_import_button.clicked.connect(lambda: self._import_profile_asset("profile_bg"))
        self.profile_bg_clear_button.clicked.connect(lambda: self._clear_profile_asset("profile_bg"))
        self.profile_bg_gallery_button.clicked.connect(lambda: self._open_profile_asset_gallery("profile_bg"))
        self.profile_bg_light_color_button.clicked.connect(lambda: self._choose_profile_bg_color("light"))
        self.profile_bg_light_color_value_button.clicked.connect(lambda: self._choose_profile_bg_color("light"))
        self.profile_bg_dark_color_button.clicked.connect(lambda: self._choose_profile_bg_color("dark"))
        self.profile_bg_dark_color_value_button.clicked.connect(lambda: self._choose_profile_bg_color("dark"))
        self.profile_bg_accent_toggle.toggled.connect(lambda checked: self.profile_bg_color_only_toggle.setChecked(True) if checked else None)
        self.profile_bg_color_only_toggle.toggled.connect(lambda checked: self.profile_bg_accent_toggle.setChecked(False) if not checked else None)
        for control in (
            self.profile_bg_dynamic_toggle,
            self.profile_bg_color_only_toggle,
            self.profile_bg_accent_toggle,
            self.profile_bg_blur_slider,
            self.profile_bg_opacity_slider,
        ):
            control.toggled.connect(self._update_profile_background_controls) if hasattr(control, "toggled") else control.valueChanged.connect(self._update_profile_background_controls)
        for line_edit in (self.profile_bg_light_color_input, self.profile_bg_dark_color_input):
            line_edit.textChanged.connect(lambda _=None: self._update_profile_background_controls())

        outer.addWidget(ResponsivePairWidget(left, right, spacing=18, breakpoint=720))
        return widget

    def _create_profile_page_background_controls(self):
        return QWidget()

    def _set_profile_asset_page(self, index):
        if index == 2:
            index = 1
        if hasattr(self, "profile_asset_controls_stack"):
            for i in range(self.profile_asset_controls_stack.count()):
                widget = self.profile_asset_controls_stack.widget(i)
                if i == index:
                    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                else:
                    widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
            self.profile_asset_controls_stack.setCurrentIndex(index)
        self.profile_picture_segment_button.setChecked(index == 0)
        self.profile_background_segment_button.setChecked(index == 1)
        if hasattr(self, "profile_page_background_segment_button"):
            self.profile_page_background_segment_button.setChecked(False)
        self._style_profile_segment_button(self.profile_picture_segment_button, index == 0)
        self._style_profile_segment_button(self.profile_background_segment_button, index == 1)
        if hasattr(self, "profile_page_background_segment_button"):
            self._style_profile_segment_button(self.profile_page_background_segment_button, False)
        self._update_profile_asset_preview()

    def _profile_pic_color_for_input(self, line_edit, fallback="#8CACB4"):
        color = line_edit.text() if line_edit else fallback
        return color if QColor(color).isValid() else fallback

    def _profile_pic_colors(self):
        single = self._profile_pic_color_for_input(getattr(self, "profile_pic_single_color_input", None), "#8CACB4")
        light = self._profile_pic_color_for_input(getattr(self, "profile_pic_light_color_input", None), single)
        dark = self._profile_pic_color_for_input(getattr(self, "profile_pic_dark_color_input", None), "#B8BDC3")
        if not getattr(self, "profile_pic_dynamic_toggle", None) or not self.profile_pic_dynamic_toggle.isChecked():
            light = dark = single
        if getattr(self, "profile_pic_accent_toggle", None) and self.profile_pic_accent_toggle.isChecked():
            light = dark = self.accent_color
        return light, dark

    def _profile_pic_gallery_key_for_mode(self, mode):
        if getattr(self, "profile_pic_dynamic_toggle", None) and self.profile_pic_dynamic_toggle.isChecked():
            return "profile_pic_dark" if mode == "dark" else "profile_pic_light"
        return "profile_pic"

    def _profile_pic_image_name(self, mode):
        if getattr(self, "profile_pic_color_only_toggle", None) and self.profile_pic_color_only_toggle.isChecked():
            return ""
        if getattr(self, "profile_pic_accent_toggle", None) and self.profile_pic_accent_toggle.isChecked():
            return ""
        key = self._profile_pic_gallery_key_for_mode(mode)
        return self.galleries.get(key, {}).get("selected", "") or self.galleries.get("profile_pic", {}).get("selected", "")

    def _choose_profile_pic_color(self, target):
        if target == "light":
            line_edit = self.profile_pic_light_color_input
        elif target == "dark":
            line_edit = self.profile_pic_dark_color_input
        else:
            line_edit = self.profile_pic_single_color_input
        chosen, ok = OnigiriColorDialog.getColor(line_edit.text(), self, anchor=self.sender() if isinstance(self.sender(), QWidget) else None)
        if ok:
            if self.profile_pic_accent_toggle.isChecked():
                self.profile_pic_accent_toggle.setChecked(False)
            line_edit.setText(chosen)
            self._update_profile_picture_controls()

    def _update_profile_picture_controls(self, *args):
        if not hasattr(self, "profile_asset_preview"):
            return
        dynamic = self.profile_pic_dynamic_toggle.isChecked()
        use_accent = self.profile_pic_accent_toggle.isChecked()
        color_only = self.profile_pic_color_only_toggle.isChecked()
        color_mode = color_only or use_accent
        self.profile_pic_light_color_button.setText("Light Color" if dynamic else "Color")
        for widget in (
            self.profile_pic_light_color_button,
            self.profile_pic_light_color_value_button,
            self.profile_pic_light_color_card,
            self.profile_pic_dark_color_button,
            self.profile_pic_dark_color_value_button,
            self.profile_pic_dark_color_card,
        ):
            widget.setVisible(not use_accent)
        self._set_dynamic_mode_widgets_dimmed([self.profile_pic_dark_color_card], not dynamic)
        for widget in (self.profile_pic_import_button, self.profile_pic_gallery_button):
            widget.setEnabled(not color_mode)
        self.profile_pic_opacity_slider.setEnabled(not color_mode)
        light = self._profile_pic_color_for_input(self.profile_pic_light_color_input, "#8CACB4")
        dark = self._profile_pic_color_for_input(self.profile_pic_dark_color_input, "#B8BDC3")
        self._style_main_background_color_button(self.profile_pic_light_color_value_button, light)
        self._style_main_background_color_button(self.profile_pic_dark_color_value_button, dark)
        self.profile_pic_opacity_value_label.setText(f"{self.profile_pic_opacity_slider.value()}%")
        self._update_profile_asset_preview()

    def _profile_bg_color_for_input(self, line_edit, fallback="#ffffff"):
        color = line_edit.text() if line_edit else fallback
        return color if QColor(color).isValid() else fallback

    def _profile_bg_colors(self):
        single = self._profile_bg_color_for_input(getattr(self, "profile_bg_single_color_input", None), "#EEEEEE")
        light = self._profile_bg_color_for_input(getattr(self, "profile_bg_light_color_input", None), single)
        dark = self._profile_bg_color_for_input(getattr(self, "profile_bg_dark_color_input", None), "#3C3C3C")
        if not getattr(self, "profile_bg_dynamic_toggle", None) or not self.profile_bg_dynamic_toggle.isChecked():
            light = dark = single
        if getattr(self, "profile_bg_accent_toggle", None) and self.profile_bg_accent_toggle.isChecked():
            light = dark = self.accent_color
        return light, dark

    def _choose_profile_bg_color(self, target):
        if target == "light":
            line_edit = self.profile_bg_light_color_input
        elif target == "dark":
            line_edit = self.profile_bg_dark_color_input
        else:
            line_edit = self.profile_bg_single_color_input
        chosen, ok = OnigiriColorDialog.getColor(line_edit.text(), self, anchor=self.sender() if isinstance(self.sender(), QWidget) else None)
        if ok:
            if self.profile_bg_accent_toggle.isChecked():
                self.profile_bg_accent_toggle.setChecked(False)
            line_edit.setText(chosen)
            self._update_profile_background_controls()

    def _update_profile_background_controls(self, *args):
        if not hasattr(self, "profile_asset_preview"):
            return
        dynamic = self.profile_bg_dynamic_toggle.isChecked()
        use_accent = self.profile_bg_accent_toggle.isChecked()
        color_only = self.profile_bg_color_only_toggle.isChecked()
        color_mode = color_only or use_accent
        self.profile_bg_light_color_button.setText("Light Color" if dynamic else "Color")
        for widget in (
            self.profile_bg_light_color_button,
            self.profile_bg_light_color_value_button,
            self.profile_bg_light_color_card,
            self.profile_bg_dark_color_button,
            self.profile_bg_dark_color_value_button,
            self.profile_bg_dark_color_card,
        ):
            widget.setVisible(not use_accent)
        self._set_dynamic_mode_widgets_dimmed([self.profile_bg_dark_color_card], not dynamic)
        for widget in (self.profile_bg_import_button, self.profile_bg_gallery_button):
            widget.setEnabled(not color_mode)
        self.profile_bg_blur_slider.setEnabled(not color_mode)
        self.profile_bg_opacity_slider.setEnabled(not color_mode)
        light = self._profile_bg_color_for_input(self.profile_bg_light_color_input, "#EEEEEE")
        dark = self._profile_bg_color_for_input(self.profile_bg_dark_color_input, "#3C3C3C")
        self._style_main_background_color_button(self.profile_bg_light_color_value_button, light)
        self._style_main_background_color_button(self.profile_bg_dark_color_value_button, dark)
        self.profile_bg_blur_value_label.setText(f"{self.profile_bg_blur_slider.value()}%")
        self.profile_bg_opacity_value_label.setText(f"{self.profile_bg_opacity_slider.value()}%")
        self._update_profile_asset_preview()

    def _profile_page_bg_is_gradient(self):
        return hasattr(self, "profile_page_bg_gradient_button") and self.profile_page_bg_gradient_button.isChecked()

    def _profile_page_bg_color_for_input(self, line_edit, fallback="#f5f5f5"):
        color = line_edit.text() if line_edit else fallback
        return color if QColor(color).isValid() else fallback

    def _profile_page_bg_values(self):
        single1 = self._profile_page_bg_color_for_input(getattr(self, "profile_page_bg_single_color1_input", None), "#F5F5F5")
        single2 = self._profile_page_bg_color_for_input(getattr(self, "profile_page_bg_single_color2_input", None), "#E0E0E0")
        light1 = self._profile_page_bg_color_for_input(getattr(self, "profile_page_bg_light_color1_input", None), single1)
        light2 = self._profile_page_bg_color_for_input(getattr(self, "profile_page_bg_light_color2_input", None), single2)
        dark1 = self._profile_page_bg_color_for_input(getattr(self, "profile_page_bg_dark_color1_input", None), "#2c2c2c")
        dark2 = self._profile_page_bg_color_for_input(getattr(self, "profile_page_bg_dark_color2_input", None), "#212121")
        if not getattr(self, "profile_page_bg_dynamic_toggle", None) or not self.profile_page_bg_dynamic_toggle.isChecked():
            light1 = dark1 = single1
            light2 = dark2 = single2
        return {
            "light": (light1, light2),
            "dark": (dark1, dark2),
            "single": (single1, single2),
            "gradient": self._profile_page_bg_is_gradient(),
        }

    def _set_profile_page_bg_mode(self, mode):
        return

    def _choose_profile_page_bg_color(self, target):
        return

    def _update_profile_page_background_controls(self, *args):
        return

    def _import_profile_asset(self, key):
        filepath, _ = QFileDialog.getOpenFileName(self, tr("import_image"), "", "Images (*.png *.jpg *.jpeg *.gif *.webp)")
        if not filepath:
            return
        filename = os.path.basename(filepath)
        dest_path = os.path.join(self._profile_asset_folder_path(key), filename)
        base, ext = os.path.splitext(filename)
        index = 2
        while os.path.exists(dest_path) and os.path.abspath(filepath) != os.path.abspath(dest_path):
            filename = f"{base}-{index}{ext}"
            dest_path = os.path.join(self._profile_asset_folder_path(key), filename)
            index += 1
        try:
            if os.path.abspath(filepath) != os.path.abspath(dest_path):
                shutil.copy(filepath, dest_path)
            if key == "profile_pic":
                target_key = self._profile_pic_gallery_key_for_mode("dark" if theme_manager.night_mode else "light")
                self.galleries[target_key]["selected"] = filename
                if not self.profile_pic_dynamic_toggle.isChecked():
                    self.galleries["profile_pic_light"]["selected"] = filename
                    self.galleries["profile_pic_dark"]["selected"] = filename
                self.profile_pic_color_only_toggle.setChecked(False)
                self.profile_pic_accent_toggle.setChecked(False)
            else:
                self.galleries[key]["selected"] = filename
            if key == "profile_bg":
                self.profile_bg_color_only_toggle.setChecked(False)
                self.profile_bg_accent_toggle.setChecked(False)
            self._update_profile_asset_preview()
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not import image: {exc}")

    def _clear_profile_asset(self, key):
        if key == "profile_pic" and key in self.galleries:
            if self.profile_pic_dynamic_toggle.isChecked():
                target_key = self._profile_pic_gallery_key_for_mode("dark" if theme_manager.night_mode else "light")
                self.galleries[target_key]["selected"] = ""
            else:
                for pic_key in ("profile_pic", "profile_pic_light", "profile_pic_dark"):
                    if pic_key in self.galleries:
                        self.galleries[pic_key]["selected"] = ""
        elif key in self.galleries:
            self.galleries[key]["selected"] = ""
        self._update_profile_asset_preview()

    def _open_profile_asset_gallery(self, key):
        gallery = self.galleries.get(key)
        if not gallery:
            return
        dialog = BackgroundGalleryDialog(self)
        dialog.setWindowTitle("Select from your Gallery")
        dialog.resize(760, 520)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self._style_background_gallery_dialog(dialog)
        dynamic_pic_gallery = key == "profile_pic" and hasattr(self, "profile_pic_dynamic_toggle") and self.profile_pic_dynamic_toggle.isChecked()
        gallery_mode = "dynamic" if dynamic_pic_gallery else "single"
        layout.addWidget(self._create_background_gallery_hint_bar(gallery_mode))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("backgroundGalleryContent")
        flow = FlowLayout(content, margin=0, spacing=10)
        tiles = []

        def refresh_badges():
            for tile in tiles:
                if dynamic_pic_gallery:
                    light = self.galleries.get("profile_pic_light", {}).get("selected") == tile.filename
                    dark = self.galleries.get("profile_pic_dark", {}).get("selected") == tile.filename
                    tile.setBadges(self._background_gallery_badges("dynamic", tile.filename, light_selected=light, dark_selected=dark))
                else:
                    tile.setBadges(self._background_gallery_badges("single", tile.filename, selected=gallery.get("selected") == tile.filename))

        def select_file(filename):
            if dynamic_pic_gallery:
                target_key = self._profile_pic_gallery_key_for_mode("dark" if theme_manager.night_mode else "light")
                self.galleries[target_key]["selected"] = filename
            else:
                gallery["selected"] = filename
            if key == "profile_bg":
                self.profile_bg_color_only_toggle.setChecked(False)
                self.profile_bg_accent_toggle.setChecked(False)
            if key == "profile_pic":
                self.profile_pic_color_only_toggle.setChecked(False)
                self.profile_pic_accent_toggle.setChecked(False)
            self._update_profile_asset_preview()
            refresh_badges()

        def handle_key_assignment(filename, key_text):
            if not dynamic_pic_gallery or key_text not in {"d", "l"}:
                return
            self.galleries["profile_pic_dark" if key_text == "d" else "profile_pic_light"]["selected"] = filename
            self.profile_pic_color_only_toggle.setChecked(False)
            self.profile_pic_accent_toggle.setChecked(False)
            self._update_profile_asset_preview()
            refresh_badges()
            if dialog.hovered_tile:
                dialog.hovered_tile.flash()

        dialog.keyAssignmentRequested.connect(handle_key_assignment)

        for filename in self._profile_asset_image_files(key):
            tile = BackgroundGalleryTile(filename, self._profile_asset_image_path(key, filename), self.accent_color)
            if dynamic_pic_gallery:
                light = self.galleries.get("profile_pic_light", {}).get("selected") == filename
                dark = self.galleries.get("profile_pic_dark", {}).get("selected") == filename
                tile.setBadges(self._background_gallery_badges("dynamic", filename, light_selected=light, dark_selected=dark))
                tile.hovered.connect(dialog.setHoveredTile)
            else:
                tile.setBadges(self._background_gallery_badges("single", filename, selected=gallery.get("selected") == filename))
            tile.clicked.connect(select_file)
            flow.addWidget(tile)
            tiles.append(tile)
        if not tiles:
            empty = QLabel("No images imported yet.")
            empty.setObjectName("backgroundGalleryEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            flow.addWidget(empty)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        done = self._create_main_bg_button("Done")
        done.clicked.connect(dialog.accept)
        layout.addWidget(done, 0, Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def _update_profile_asset_preview(self):
        if not hasattr(self, "profile_asset_preview"):
            return
        self.profile_asset_preview.setStyleSheet("QLabel#mainBackgroundPreview { background: transparent; border: none; }")
        self.profile_asset_preview.setPixmap(self._render_profile_asset_preview_pixmap())
        self.profile_asset_preview.setText("")

    def _render_profile_asset_preview_pixmap(self):
        preview = self.profile_asset_preview
        width = max(1, preview.width())
        height = max(1, preview.height())
        dpr = max(1.0, preview.devicePixelRatioF())
        target = QPixmap(int(width * dpr), int(height * dpr))
        target.setDevicePixelRatio(dpr)
        target.fill(Qt.GlobalColor.transparent)
        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        palette = self._settings_palette()
        border = QColor(palette.get("--border", "#d1d5db"))
        fg = QColor(palette.get("--fg", "#111827"))
        bg_rect = QRectF(1, 1, width - 2, height - 2)
        bg_path = QPainterPath()
        bg_path.addRoundedRect(bg_rect, 22, 22)
        page_bg = self._profile_page_bg_values() if hasattr(self, "profile_page_bg_dynamic_toggle") else {
            "light": (palette.get("--highlight-bg", "#f3f4f6"), palette.get("--highlight-bg", "#f3f4f6")),
            "dark": (palette.get("--highlight-bg", "#f3f4f6"), palette.get("--highlight-bg", "#f3f4f6")),
            "gradient": False,
        }
        painter.setClipPath(bg_path)

        def fill_page_bg(rect, values):
            color1, color2 = values
            if page_bg.get("gradient"):
                gradient = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
                gradient.setColorAt(0.0, QColor(color1))
                gradient.setColorAt(1.0, QColor(color2))
                painter.fillRect(rect, QBrush(gradient))
            else:
                painter.fillRect(rect, QColor(color1))

        if hasattr(self, "profile_page_bg_dynamic_toggle") and self.profile_page_bg_dynamic_toggle.isChecked():
            left_rect = QRectF(bg_rect.left(), bg_rect.top(), bg_rect.width() / 2, bg_rect.height())
            right_rect = QRectF(bg_rect.left() + bg_rect.width() / 2, bg_rect.top(), bg_rect.width() / 2, bg_rect.height())
            fill_page_bg(left_rect, page_bg["light"])
            fill_page_bg(right_rect, page_bg["dark"])
        else:
            mode_key = "dark" if theme_manager.night_mode else "light"
            fill_page_bg(bg_rect, page_bg.get(mode_key, page_bg["light"]))
        painter.setClipping(False)
        painter.setPen(QPen(border, 1))
        painter.drawPath(bg_path)

        margin = 20
        gap = 22
        pill_height = min(82, max(54, int((height - margin * 2) * 0.72)))
        active_index = self.profile_asset_controls_stack.currentIndex() if hasattr(self, "profile_asset_controls_stack") else 1
        if active_index == 0:
            dynamic_preview = self.profile_pic_dynamic_toggle.isChecked()
        elif active_index == 2:
            dynamic_preview = self.profile_page_bg_dynamic_toggle.isChecked()
        else:
            dynamic_preview = self.profile_bg_dynamic_toggle.isChecked()
        if dynamic_preview:
            pill_width = max(120, int((width - margin * 2 - gap) / 2))
            y = int((height - pill_height) / 2)
            preview_rects = [("light", QRectF(margin, y, pill_width, pill_height)), ("dark", QRectF(margin + pill_width + gap, y, pill_width, pill_height))]
        else:
            pill_width = min(max(300, int(width * 0.62)), max(120, width - margin * 2))
            y = int((height - pill_height) / 2)
            preview_rects = [("dark" if theme_manager.night_mode else "light", QRectF((width - pill_width) / 2, y, pill_width, pill_height))]
        light_color, dark_color = self._profile_bg_colors()
        selected_bg_name = self.galleries.get("profile_bg", {}).get("selected", "")
        bg_is_color_mode = self.profile_bg_color_only_toggle.isChecked() or self.profile_bg_accent_toggle.isChecked()
        image_name = "" if bg_is_color_mode else selected_bg_name
        image_path = self._profile_asset_image_path("profile_bg", image_name)
        if not bg_is_color_mode and not os.path.exists(image_path):
            image_path = self._profile_default_asset_path("profile_bg") if not selected_bg_name else ""
        if not os.path.exists(image_path):
            image_path = ""

        avatar_size = max(40, pill_height - 18)
        user_name = self.name_input.text() if hasattr(self, "name_input") else self.current_config.get("userName", DEFAULTS["userName"])
        blur = self.profile_bg_blur_slider.value() if hasattr(self, "profile_bg_blur_slider") else 0
        opacity = self.profile_bg_opacity_slider.value() if hasattr(self, "profile_bg_opacity_slider") else 100
        pic_blur = 0
        pic_opacity = self.profile_pic_opacity_slider.value() if hasattr(self, "profile_pic_opacity_slider") else 100
        pic_light_color, pic_dark_color = self._profile_pic_colors()

        def render_avatar(mode):
            pic_color = pic_dark_color if mode == "dark" else pic_light_color
            pic_is_color_mode = self.profile_pic_color_only_toggle.isChecked() or self.profile_pic_accent_toggle.isChecked()
            selected_avatar_name = (
                self.galleries.get(self._profile_pic_gallery_key_for_mode(mode), {}).get("selected", "")
                or self.galleries.get("profile_pic", {}).get("selected", "")
            )
            avatar_name = self._profile_pic_image_name(mode)
            avatar_path = self._profile_asset_image_path("profile_pic", avatar_name)
            default_avatar_path = self._profile_default_asset_path("profile_pic")
            use_default_avatar = not pic_is_color_mode and not avatar_name and not selected_avatar_name
            if not pic_is_color_mode and avatar_name and not os.path.exists(avatar_path):
                use_default_avatar = True
            if use_default_avatar:
                avatar_path = default_avatar_path
            if not pic_is_color_mode and os.path.exists(avatar_path):
                avatar_image = QImage(avatar_path)
                avatar_pixmap = create_circular_contained_pixmap(
                    avatar_image,
                    avatar_size,
                    QColor(pic_color),
                    cover=not use_default_avatar,
                )
                if pic_blur > 0 and not avatar_pixmap.isNull():
                    avatar_pixmap = self._qt_blurred_pixmap(avatar_pixmap, pic_blur * 0.2)
                if pic_opacity < 100 and not avatar_pixmap.isNull():
                    faded = QPixmap(avatar_pixmap.size())
                    faded.setDevicePixelRatio(avatar_pixmap.devicePixelRatio())
                    faded.fill(Qt.GlobalColor.transparent)
                    fade_painter = QPainter(faded)
                    fade_painter.setOpacity(max(0.0, min(1.0, pic_opacity / 100.0)))
                    fade_painter.drawPixmap(0, 0, avatar_pixmap)
                    fade_painter.end()
                    avatar_pixmap = faded
                return avatar_pixmap, ""
            dpr = 2.0
            target_avatar = QPixmap(avatar_size * 2, avatar_size * 2)
            target_avatar.setDevicePixelRatio(dpr)
            target_avatar.fill(Qt.GlobalColor.transparent)
            avatar_painter = QPainter(target_avatar)
            avatar_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            avatar_painter.setBrush(QBrush(QColor(pic_color)))
            avatar_painter.setPen(Qt.PenStyle.NoPen)
            avatar_painter.drawEllipse(QRectF(0, 0, avatar_size, avatar_size))
            text_color = QColor("#111827") if QColor(pic_color).lightness() > 150 else QColor("#ffffff")
            avatar_painter.setPen(text_color)
            font = avatar_painter.font()
            font.setBold(True)
            font.setPointSize(max(14, int(avatar_size * 0.52)))
            avatar_painter.setFont(font)
            avatar_painter.drawText(QRectF(0, 0, avatar_size, avatar_size), Qt.AlignmentFlag.AlignCenter, (user_name[:1] or "U").upper())
            avatar_painter.end()
            return target_avatar, ""

        def draw_pill(rect, mode):
            color = dark_color if mode == "dark" else light_color
            path = QPainterPath()
            radius = rect.height() / 2
            path.addRoundedRect(rect, radius, radius)
            painter.setClipPath(path)
            painter.fillPath(path, QColor(color))
            if image_path:
                pixmap = self._background_cover_image_with_effect(image_path, int(rect.width()), int(rect.height()), blur)
                if not pixmap.isNull():
                    painter.setOpacity(max(0.0, min(1.0, opacity / 100.0)))
                    painter.drawPixmap(int(rect.x()), int(rect.y()), pixmap)
                    painter.setOpacity(1.0)
                    painter.fillPath(path, QColor(0, 0, 0, PROFILE_BAR_IMAGE_OVERLAY_ALPHA))
            painter.setClipping(False)
            avatar, _ = render_avatar(mode)
            if not avatar.isNull():
                avatar_rect = QRectF(
                    rect.x() + 9,
                    rect.y() + (rect.height() - avatar_size) / 2,
                    avatar_size,
                    avatar_size,
                )
                avatar_path = QPainterPath()
                avatar_path.addEllipse(avatar_rect)
                painter.setClipPath(avatar_path)
                source_rect = QRectF(avatar.rect())
                painter.drawPixmap(avatar_rect, avatar, source_rect)
                painter.setClipping(False)
                painter.setPen(QPen(QColor(255, 255, 255, 170 if mode == "dark" else 210), 1.5))
                painter.drawEllipse(avatar_rect.adjusted(0.75, 0.75, -0.75, -0.75))
            text_x = rect.x() + avatar_size + 27
            text_rect = QRectF(text_x, rect.y(), max(10, rect.right() - text_x - 18), rect.height())
            text_color = QColor("#ffffff") if image_path or QColor(color).lightness() < 145 else QColor("#111827")
            painter.setPen(text_color)
            font = painter.font()
            font.setBold(False)
            font.setPointSize(22 if rect.width() > 260 else 16)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, metrics.elidedText(user_name, Qt.TextElideMode.ElideRight, int(text_rect.width())))

        for mode, rect in preview_rects:
            draw_pill(rect, mode)
        painter.setPen(fg)
        painter.end()
        return target

    def _draw_sidebar_preview_profile(self, painter, rect, valign="top"):
        # Render the pill into the exact box given (same width/height as the Add
        # button), painting it ourselves so the bar fills the box while the
        # circular avatar and name stay small and proportional. Reuses the real
        # ProfileBarWidget's colours/avatar so it tracks the user's settings.
        profile_bar = getattr(self, "profile_bar", None)
        if profile_bar is None:
            return 0.0
        bar_rect = QRectF(rect)
        if bar_rect.width() <= 4 or bar_rect.height() <= 4:
            return 0.0
        radius = bar_rect.height() / 2.0

        painter.save()
        try:
            try:
                bg_color = QColor(profile_bar._profile_background_color())
            except Exception:
                bg_color = QColor(getattr(self, "accent_color", "#3b6ea5"))
            pill_path = QPainterPath()
            pill_path.addRoundedRect(bar_rect, radius, radius)
            painter.fillPath(pill_path, QBrush(bg_color))

            inset = bar_rect.height() * 0.12
            avatar_d = max(1.0, bar_rect.height() - 2 * inset)
            avatar_rect = QRectF(bar_rect.x() + inset, bar_rect.y() + inset, avatar_d, avatar_d)
            try:
                avatar_pix = profile_bar._render_avatar_pixmap(max(16, int(round(avatar_d * 2))))
                if avatar_pix and not avatar_pix.isNull():
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                    painter.drawPixmap(avatar_rect, avatar_pix, QRectF(avatar_pix.rect()))
            except Exception:
                pass

            name = getattr(profile_bar, "_user_name", "") or self.current_config.get("userName", "")
            if name:
                try:
                    name_color = QColor(profile_bar._text_colors()[0])
                except Exception:
                    name_color = QColor("#ffffff")
                font = QFont(self.font())
                font.setPointSize(max(7, int(bar_rect.height() * 0.34)))
                try:
                    font.setWeight(QFont.Weight.Medium)
                except Exception:
                    pass
                painter.setFont(font)
                painter.setPen(name_color)
                text_x = avatar_rect.right() + bar_rect.height() * 0.22
                text_rect = QRectF(text_x, bar_rect.y(), max(0.0, bar_rect.right() - text_x - radius * 0.4), bar_rect.height())
                metrics = QFontMetrics(font)
                text = metrics.elidedText(str(name), Qt.TextElideMode.ElideRight, int(text_rect.width()))
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text)
        finally:
            painter.restore()
        return float(bar_rect.height())

    def create_profile_tab(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(15)
        
        profile_section = SectionGroup("", self)
        profile_form_shell = QWidget()
        profile_form_shell.setObjectName("profileFormShell")
        profile_form_shell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        profile_form = QGridLayout(profile_form_shell)
        profile_form.setContentsMargins(0, 0, 0, 0)
        profile_form.setHorizontalSpacing(18)
        profile_form.setVerticalSpacing(14)
        profile_form.setColumnMinimumWidth(0, 122)
        profile_form.setColumnStretch(0, 0)
        profile_form.setColumnStretch(1, 1)

        def add_profile_row(row, label_text, field_widget, align_top=False):
            label = QLabel(label_text)
            label.setObjectName("profileFormLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | (Qt.AlignmentFlag.AlignTop if align_top else Qt.AlignmentFlag.AlignVCenter))
            label.setMinimumHeight(34)
            field_widget.setObjectName("profileFormField")
            field_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            profile_form.addWidget(label, row, 0)
            profile_form.addWidget(field_widget, row, 1)

        self.name_input = QLineEdit(self.current_config.get("userName", DEFAULTS["userName"]))
        add_profile_row(0, tr("user_name"), self.name_input)
        
        # Birthday date picker
        accent_color = mw.col.conf.get("modern_menu_accent_color", "#00A982")
        self.birthday_input = BirthdayWidget(accent_color=accent_color)
        birthday_str = self.current_config.get("userBirthday", "")
        if birthday_str:
            try:
                birthday_date = QDate.fromString(birthday_str, "yyyy-MM-dd")
                if birthday_date.isValid():
                    self.birthday_input.setDate(birthday_date)
            except:
                pass

        self.birthday_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        add_profile_row(1, tr("birthday"), self.birthday_input)

        profile_conf = self.current_config.get("onigiriProfile", {})
        if not isinstance(profile_conf, dict):
            profile_conf = {}

        self.profile_status_input = QLineEdit(str(profile_conf.get("status") or ""))
        add_profile_row(2, "Status", self.profile_status_input)

        self.profile_bio_input = QPlainTextEdit(str(profile_conf.get("bio") or ""))
        self.profile_bio_input.setFixedHeight(92)
        self.profile_bio_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        add_profile_row(3, "Bio", self.profile_bio_input, align_top=True)

        self.profile_music_input = QLineEdit(str(profile_conf.get("spotifyLink") or profile_conf.get("musicLink") or ""))
        self.profile_music_input.setPlaceholderText("https://open.spotify.com/... | https://music.apple.com/... | https://music.youtube.com/watch?v=...")
        add_profile_row(4, "Music", self.profile_music_input)

        profile_form_shell.setStyleSheet(f"""
            QWidget#profileFormShell QLabel#profileFormLabel {{
                font-size: 13px;
                font-weight: 500;
            }}
            QWidget#profileFormShell QLineEdit#profileFormField,
            QWidget#profileFormShell QPlainTextEdit#profileFormField {{
                border-radius: 10px;
                padding: 5px 10px;
            }}
            QWidget#profileFormShell QLineEdit#profileFormField {{
                min-height: 32px;
                max-height: 32px;
            }}
        """)

        profile_section.add_widget(profile_form_shell)

        layout.addWidget(profile_section)

        profile_assets_section = SectionGroup("", self)
        profile_assets_section.add_widget(self._create_profile_asset_designer())
        layout.addWidget(profile_assets_section)
        self.name_input.textChanged.connect(lambda _=None: self._update_profile_asset_preview())

        layout.addStretch()
        sections = {
            "Profile": profile_section,
            tr("profile_picture"): profile_assets_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections, buttons_per_row=3)

        return page

    def toggle_profile_page_bg_options(self): is_gradient = self.profile_page_bg_gradient_radio.isChecked(); self.profile_page_color_group.setVisible(not is_gradient); self.profile_page_gradient_group.setVisible(is_gradient)

    def toggle_profile_level_bar_options(self):
        self.profile_level_bar_color_group.setVisible(self.profile_level_bar_custom_radio.isChecked())

    def _save_profile_settings(self):
        self.current_config["userName"] = self.name_input.text()
        mw.col.conf["modern_menu_userName"] = self.name_input.text()
        
        # Save birthday in ISO format (YYYY-MM-DD)
        if hasattr(self, 'birthday_input'):
            birthday_date = self.birthday_input.date()
            if birthday_date.isValid():
                 self.current_config["userBirthday"] = birthday_date.toString("yyyy-MM-dd")
            else:
                 self.current_config["userBirthday"] = ""

        if hasattr(self, "profile_bio_input"):
            self.current_config["onigiriProfile"] = {
                "bio": self.profile_bio_input.toPlainText().strip(),
                "status": self.profile_status_input.text().strip(),
                "musicLink": self.profile_music_input.text().strip(),
                "spotifyLink": self.profile_music_input.text().strip(),
            }

        if 'profile_pic' in self.galleries:
            if hasattr(self, "profile_pic_dynamic_toggle"):
                if self.profile_pic_dynamic_toggle.isChecked():
                    light_pic = self.galleries.get("profile_pic_light", {}).get("selected", "")
                    dark_pic = self.galleries.get("profile_pic_dark", {}).get("selected", "")
                    mw.col.conf["modern_menu_profile_picture"] = light_pic or dark_pic
                    mw.col.conf["modern_menu_profile_picture_light"] = light_pic
                    mw.col.conf["modern_menu_profile_picture_dark"] = dark_pic
                else:
                    single_pic = self.galleries.get("profile_pic", {}).get("selected", "")
                    mw.col.conf["modern_menu_profile_picture"] = single_pic
                    mw.col.conf["modern_menu_profile_picture_light"] = single_pic
                    mw.col.conf["modern_menu_profile_picture_dark"] = single_pic

                if self.profile_pic_accent_toggle.isChecked():
                    mw.col.conf["modern_menu_profile_picture_mode"] = "accent"
                elif self.profile_pic_color_only_toggle.isChecked():
                    mw.col.conf["modern_menu_profile_picture_mode"] = "custom"
                else:
                    mw.col.conf["modern_menu_profile_picture_mode"] = "image"
                mw.col.conf["modern_menu_profile_picture_dynamic_mode"] = self.profile_pic_dynamic_toggle.isChecked()
                if self.profile_pic_dynamic_toggle.isChecked():
                    mw.col.conf["modern_menu_profile_picture_color_light"] = self.profile_pic_light_color_input.text()
                    mw.col.conf["modern_menu_profile_picture_color_dark"] = self.profile_pic_dark_color_input.text()
                else:
                    single_pic_color = self.profile_pic_single_color_input.text()
                    mw.col.conf["modern_menu_profile_picture_color_light"] = single_pic_color
                    mw.col.conf["modern_menu_profile_picture_color_dark"] = single_pic_color
                mw.col.conf["modern_menu_profile_picture_blur"] = 0
                mw.col.conf["modern_menu_profile_picture_opacity"] = self.profile_pic_opacity_slider.value()
            else:
                mw.col.conf["modern_menu_profile_picture"] = self.galleries['profile_pic']['selected']
        if 'profile_bg' in self.galleries:
            mw.col.conf["modern_menu_profile_bg_image"] = self.galleries['profile_bg']['selected']

        if hasattr(self, "profile_bg_color_only_toggle"):
            mw.col.conf["modern_menu_profile_bg_dynamic_mode"] = self.profile_bg_dynamic_toggle.isChecked()
            if self.profile_bg_accent_toggle.isChecked():
                mw.col.conf["modern_menu_profile_bg_mode"] = "accent"
            elif self.profile_bg_color_only_toggle.isChecked():
                mw.col.conf["modern_menu_profile_bg_mode"] = "custom"
            else:
                mw.col.conf["modern_menu_profile_bg_mode"] = "image"

            if self.profile_bg_dynamic_toggle.isChecked():
                mw.col.conf["modern_menu_profile_bg_color_light"] = self.profile_bg_light_color_input.text()
                mw.col.conf["modern_menu_profile_bg_color_dark"] = self.profile_bg_dark_color_input.text()
            else:
                single_color = self.profile_bg_single_color_input.text()
                mw.col.conf["modern_menu_profile_bg_color_light"] = single_color
                mw.col.conf["modern_menu_profile_bg_color_dark"] = single_color
            mw.col.conf["modern_menu_profile_bg_blur"] = self.profile_bg_blur_slider.value()
            mw.col.conf["modern_menu_profile_bg_opacity"] = self.profile_bg_opacity_slider.value()
        else:
            if self.profile_bg_image_radio.isChecked(): mw.col.conf["modern_menu_profile_bg_mode"] = "image"
            elif self.profile_bg_custom_radio.isChecked(): mw.col.conf["modern_menu_profile_bg_mode"] = "custom"
            else: mw.col.conf["modern_menu_profile_bg_mode"] = "accent"
            
            mw.col.conf["modern_menu_profile_bg_color_light"] = self.profile_bg_light_color_input.text()
            mw.col.conf["modern_menu_profile_bg_color_dark"] = self.profile_bg_dark_color_input.text()
        if hasattr(self, "profile_page_bg_gradient_button"):
            dynamic_page_bg = self.profile_page_bg_dynamic_toggle.isChecked()
            gradient_page_bg = self.profile_page_bg_gradient_button.isChecked()
            mw.col.conf["onigiri_profile_page_bg_mode"] = "gradient" if gradient_page_bg else "color"
            mw.col.conf["onigiri_profile_page_bg_dynamic_mode"] = dynamic_page_bg
            if dynamic_page_bg:
                mw.col.conf["onigiri_profile_page_bg_light_color1"] = self.profile_page_bg_light_color1_input.text()
                mw.col.conf["onigiri_profile_page_bg_light_color2"] = self.profile_page_bg_light_color2_input.text() if gradient_page_bg else self.profile_page_bg_light_color1_input.text()
                mw.col.conf["onigiri_profile_page_bg_dark_color1"] = self.profile_page_bg_dark_color1_input.text()
                mw.col.conf["onigiri_profile_page_bg_dark_color2"] = self.profile_page_bg_dark_color2_input.text() if gradient_page_bg else self.profile_page_bg_dark_color1_input.text()
            else:
                single1 = self.profile_page_bg_single_color1_input.text()
                single2 = self.profile_page_bg_single_color2_input.text() if gradient_page_bg else single1
                mw.col.conf["onigiri_profile_page_bg_light_color1"] = single1
                mw.col.conf["onigiri_profile_page_bg_light_color2"] = single2
                mw.col.conf["onigiri_profile_page_bg_dark_color1"] = single1
                mw.col.conf["onigiri_profile_page_bg_dark_color2"] = single2
        elif hasattr(self, "profile_page_bg_gradient_radio"):
            if self.profile_page_bg_gradient_radio.isChecked():
                mw.col.conf["onigiri_profile_page_bg_mode"] = "gradient"
                mw.col.conf["onigiri_profile_page_bg_light_color1"] = self.profile_page_light_gradient1_color_input.text()
                mw.col.conf["onigiri_profile_page_bg_light_color2"] = self.profile_page_light_gradient2_color_input.text()
                mw.col.conf["onigiri_profile_page_bg_dark_color1"] = self.profile_page_dark_gradient1_color_input.text()
                mw.col.conf["onigiri_profile_page_bg_dark_color2"] = self.profile_page_dark_gradient2_color_input.text()
            else:
                mw.col.conf["onigiri_profile_page_bg_mode"] = "color"
                mw.col.conf["onigiri_profile_page_bg_light_color1"] = self.profile_page_light_color1_color_input.text()
                mw.col.conf["onigiri_profile_page_bg_dark_color1"] = self.profile_page_dark_color1_color_input.text()

    def _overview_style_profile_bar_rect(self, rect, y=None):
        bar_width = min(rect.width() * 0.425, 338)
        bar_height = 64
        return QRectF(
            rect.x() + (rect.width() - bar_width) / 2,
            rect.y() + 28 if y is None else y,
            bar_width,
            bar_height,
        )

    def _overview_style_overviewer_profile_bar_rect(self, rect, box_rect=None, is_mini=False):
        bar_width = min(rect.width() * (0.30 if not is_mini else 0.34), 240 if not is_mini else 210)
        bar_height = 38 if not is_mini else 32
        if box_rect is not None:
            y = box_rect.y() - (bar_height * (0.56 if not is_mini else 0.50))
        else:
            box_y = (
                max(78, rect.height() * 0.16)
                if is_mini else
                max(168, rect.height() * 0.34)
            )
            y = rect.y() + box_y - (bar_height * (0.50 if is_mini else 0.56))
        return QRectF(
            rect.x() + (rect.width() - bar_width) / 2,
            y,
            bar_width,
            bar_height,
        )

    def _overview_style_profile_bar_state(self, mode):
        mode = "dark" if mode == "dark" else "light"
        user_name = (
            self.name_input.text().strip()
            if hasattr(self, "name_input")
            else str(self.current_config.get("userName", DEFAULTS.get("userName", "USER")) or "USER")
        )

        if hasattr(self, "profile_bg_single_color_input"):
            bg_light, bg_dark = self._profile_bg_colors()
            bg_mode = "accent" if self.profile_bg_accent_toggle.isChecked() else ("custom" if self.profile_bg_color_only_toggle.isChecked() else "image")
            bg_image_name = "" if bg_mode != "image" else self.galleries.get("profile_bg", {}).get("selected", "")
            bg_blur = self.profile_bg_blur_slider.value()
            bg_opacity = self.profile_bg_opacity_slider.value()
        else:
            bg_light = mw.col.conf.get("modern_menu_profile_bg_color_light", "#6D3E96")
            bg_dark = mw.col.conf.get("modern_menu_profile_bg_color_dark", bg_light)
            bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "accent")
            bg_image_name = mw.col.conf.get("modern_menu_profile_bg_image", "")
            bg_blur = int(mw.col.conf.get("modern_menu_profile_bg_blur", 0) or 0)
            bg_opacity = int(mw.col.conf.get("modern_menu_profile_bg_opacity", 100) or 100)
            if bg_mode == "accent":
                bg_light = bg_dark = self.accent_color

        if hasattr(self, "profile_pic_single_color_input"):
            pic_light, pic_dark = self._profile_pic_colors()
            pic_mode = "accent" if self.profile_pic_accent_toggle.isChecked() else ("custom" if self.profile_pic_color_only_toggle.isChecked() else "image")
            pic_image_name = "" if pic_mode != "image" else self._profile_pic_image_name(mode)
            pic_blur = 0
            pic_opacity = self.profile_pic_opacity_slider.value()
        else:
            pic_light = mw.col.conf.get("modern_menu_profile_picture_color_light", "#8CACB4")
            pic_dark = mw.col.conf.get("modern_menu_profile_picture_color_dark", pic_light)
            pic_mode = mw.col.conf.get("modern_menu_profile_picture_mode", "image")
            if mw.col.conf.get("modern_menu_profile_picture_dynamic_mode", True):
                pic_image_name = mw.col.conf.get(
                    "modern_menu_profile_picture_dark" if mode == "dark" else "modern_menu_profile_picture_light",
                    "",
                )
            else:
                pic_image_name = mw.col.conf.get("modern_menu_profile_picture", "")
            if pic_mode == "accent":
                pic_light = pic_dark = self.accent_color
            if pic_mode != "image":
                pic_image_name = ""
            pic_blur = int(mw.col.conf.get("modern_menu_profile_picture_blur", 0) or 0)
            pic_opacity = int(mw.col.conf.get("modern_menu_profile_picture_opacity", 100) or 100)

        bg_image_path = self._profile_asset_image_path("profile_bg", bg_image_name) if bg_mode == "image" else ""
        if bg_mode == "image" and (not bg_image_name or not os.path.exists(bg_image_path)):
            bg_image_path = self._profile_default_asset_path("profile_bg")
        if not os.path.exists(bg_image_path):
            bg_image_path = ""
        pic_image_path = self._profile_asset_image_path("profile_pic", pic_image_name) if pic_mode == "image" else ""
        pic_uses_default = False
        if pic_mode == "image" and (not pic_image_name or not os.path.exists(pic_image_path)):
            pic_image_path = self._profile_default_asset_path("profile_pic")
            pic_uses_default = True
        if not os.path.exists(pic_image_path):
            pic_image_path = ""
            pic_uses_default = False

        return {
            "name": user_name or "USER",
            "bg_color": bg_dark if mode == "dark" else bg_light,
            "bg_image_path": bg_image_path,
            "bg_blur": int(bg_blur or 0),
            "bg_opacity": int(bg_opacity or 100),
            "pic_color": pic_dark if mode == "dark" else pic_light,
            "pic_image_path": pic_image_path,
            "pic_uses_default": pic_uses_default,
            "pic_blur": int(pic_blur or 0),
            "pic_opacity": int(pic_opacity or 100),
        }

    def _draw_overview_style_profile_bar(self, painter, rect, mode, bar_rect=None):
        state = self._overview_style_profile_bar_state(mode)
        bar_rect = bar_rect or self._overview_style_profile_bar_rect(rect)
        bar_color = QColor(state["bg_color"])
        path = QPainterPath()
        path.addRoundedRect(bar_rect, bar_rect.height() / 2, bar_rect.height() / 2)
        painter.fillPath(path, QBrush(bar_color))
        painter.save()
        painter.setClipPath(path)
        if state["bg_image_path"]:
            bg = self._background_cover_image_with_effect(
                state["bg_image_path"],
                int(bar_rect.width()),
                int(bar_rect.height()),
                state["bg_blur"],
            )
            if not bg.isNull():
                painter.setOpacity(max(0.0, min(1.0, state["bg_opacity"] / 100.0)))
                painter.drawPixmap(int(bar_rect.x()), int(bar_rect.y()), bg)
                painter.setOpacity(1.0)
                painter.fillPath(path, QColor(0, 0, 0, PROFILE_BAR_IMAGE_OVERLAY_ALPHA))
        painter.restore()
        painter.setPen(QPen(QColor(255, 255, 255, 70), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        avatar_size = max(22, min(48, int(bar_rect.height() - 10)))
        side_padding = max(5, int(bar_rect.height() * 0.16))
        avatar_rect = QRectF(
            bar_rect.x() + side_padding,
            bar_rect.y() + (bar_rect.height() - avatar_size) / 2,
            avatar_size,
            avatar_size,
        )
        avatar = QPixmap()
        if state["pic_image_path"]:
            avatar = create_circular_contained_pixmap(
                QImage(state["pic_image_path"]),
                avatar_size,
                QColor(state["pic_color"]),
                cover=not state.get("pic_uses_default"),
            )
            if state["pic_blur"] > 0 and not avatar.isNull():
                avatar = self._qt_blurred_pixmap(avatar, state["pic_blur"] * 0.2)
            if state["pic_opacity"] < 100 and not avatar.isNull():
                faded = QPixmap(avatar.size())
                faded.setDevicePixelRatio(avatar.devicePixelRatio())
                faded.fill(Qt.GlobalColor.transparent)
                fade_painter = QPainter(faded)
                fade_painter.setOpacity(max(0.0, min(1.0, state["pic_opacity"] / 100.0)))
                fade_painter.drawPixmap(0, 0, avatar)
                fade_painter.end()
                avatar = faded
        if not avatar.isNull():
            painter.drawPixmap(int(avatar_rect.x()), int(avatar_rect.y()), avatar)
        else:
            painter.setBrush(QBrush(QColor(state["pic_color"])))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(avatar_rect)
            painter.setPen(QColor("#111827") if QColor(state["pic_color"]).lightness() > 150 else QColor("#ffffff"))
            initial_font = self._box_effect_preview_font("main", max(12, int(avatar_size * 0.46)))
            initial_font.setBold(True)
            painter.setFont(initial_font)
            painter.drawText(avatar_rect, Qt.AlignmentFlag.AlignCenter, (state["name"][:1] or "U").upper())

        text_color = QColor("#ffffff") if state["bg_image_path"] or bar_color.lightness() < 145 else QColor("#111827")
        painter.setPen(text_color)
        font = self._box_effect_preview_font("main", max(13, int(bar_rect.height() * 0.42)))
        font.setBold(True)
        painter.setFont(font)
        text_gap = max(8, int(bar_rect.height() * 0.20))
        text_rect = QRectF(
            avatar_rect.right() + text_gap,
            bar_rect.y(),
            bar_rect.right() - avatar_rect.right() - text_gap - side_padding,
            bar_rect.height(),
        )
        metrics = painter.fontMetrics()
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            metrics.elidedText(state["name"], Qt.TextElideMode.ElideRight, int(text_rect.width())),
        )

