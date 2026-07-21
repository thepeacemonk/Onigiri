# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *
from ._font_picker import FontPickerDialog


class _ProfileNameFontCard(QFrame):
    """Clickable card wrapper for the profile-name font picker (mirrors
    _PomodoroClickableCard in _page_pomodoro.py)."""

    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self._on_click = on_click

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mousePressEvent(event)


class PageProfileMixin:
    def show_profile_page(self):
        if btn := self.sidebar_button_group.checkedButton():
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)
        if hasattr(self, "page_title_label"):
            if hasattr(self, "settings_page_header"):
                self.settings_page_header.setVisible(True)
            self.page_title_label.setVisible(False)

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

    def _create_profile_type_controls(self):
        """One unified top panel: Bar/Ring/Minimal type selector, the asset tabs,
        the shared Dynamic-mode toggle and the light/dark preview toggle — all
        gathered together above the preview (Widget Color & Effect style)."""
        palette = self._settings_palette()
        card_bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        card_border = palette.get("--border", "#454545" if theme_manager.night_mode else "#e5e7eb")
        fg = palette.get("--fg", "#f9fafb" if theme_manager.night_mode else "#111827")

        panel = QFrame()
        panel.setObjectName("profileTopPanel")
        panel.setStyleSheet(f"""
            QFrame#profileTopPanel {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 22px;
            }}
        """)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(0)

        # Single centered pill holding all customization controls: the Bar/Ring/
        # Minimal type segment plus the Dynamic mode toggle, all inside the same
        # gooey pill background.
        row_a = QHBoxLayout()
        row_a.setContentsMargins(0, 0, 0, 0)
        row_a.setSpacing(12)

        self.selected_profile_type = mw.col.conf.get("modern_menu_profile_type", "bar") or "bar"
        self.profile_type_group = QButtonGroup(self)
        self.profile_type_group.setExclusive(True)
        type_control = self._create_organize_segmented_control(
            [
                ("bar", tr("profile_type_bar", "Bar")),
                ("ring", tr("profile_type_ring", "Ring")),
                ("minimal", tr("profile_type_minimal", "Minimal")),
            ],
            self.profile_type_group,
            self.selected_profile_type,
            "profile_type",
            segment_height=30,
            min_button_width=62,
        )
        self.profile_type_group.buttonToggled.connect(
            lambda btn, checked: self._set_profile_type(btn.property("profile_type")) if checked else None
        )

        # Dynamic mode rides inside the same pill (the shell paints its rounded
        # background across whatever it contains). It's not a segment button, so
        # the selection blob ignores it.
        dyn_label = QLabel(tr("dynamic_mode", "Dynamic mode"))
        dyn_label.setStyleSheet(f"background: transparent; border: none; color: {fg}; font-size: 12px; font-weight: 600;")
        self.profile_dynamic_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.profile_dynamic_toggle.setChecked(bool(mw.col.conf.get("modern_menu_profile_picture_dynamic_mode", True)))
        self.profile_dynamic_toggle.toggled.connect(self._on_profile_dynamic_toggled)
        type_control.segment_layout.addSpacing(16)
        type_control.segment_layout.addWidget(dyn_label, 0, Qt.AlignmentFlag.AlignVCenter)
        type_control.segment_layout.addSpacing(8)
        type_control.segment_layout.addWidget(self.profile_dynamic_toggle, 0, Qt.AlignmentFlag.AlignVCenter)

        row_a.addStretch(1)
        row_a.addWidget(type_control, 0)
        row_a.addStretch(1)
        outer.addLayout(row_a)
        # Asset tabs pill sits on this same row, right of the type pill (built
        # later by _build_profile_asset_tabs, which inserts before the stretch).
        self.profile_asset_tabs_layout = row_a

        # Light/dark preview toggle is NAVIGATION (which palette you edit), not
        # customization — so it rides the asset-tabs row (see
        # _build_profile_asset_tabs), keeping this panel customization-only.
        # Created here so it exists before the tabs are built.
        self.profile_preview_mode = "dark" if theme_manager.night_mode else "light"
        self.profile_preview_mode_widget, self.profile_preview_mode_toggle = self._create_light_dark_mode_toggle(
            self.profile_preview_mode,
            self._on_profile_preview_mode_toggled,
        )

        # Fill-color line edits live here so they exist before the Progress Color
        # page is built (which is created later in the controls stack).
        self.profile_fill_light_color_input = QLineEdit(mw.col.conf.get("modern_menu_profile_fill_color_light", "#4f7cff"))
        self.profile_fill_single_color_input = self.profile_fill_light_color_input
        self.profile_fill_dark_color_input = QLineEdit(mw.col.conf.get("modern_menu_profile_fill_color_dark", "#4f7cff"))

        self._set_profile_type(self.selected_profile_type)
        return panel

    def _create_profile_progress_color_controls(self):
        """Ring/minimal fallback progress color. Shown below the preview like the
        other colour settings; obeys the shared light/dark + Dynamic mode."""
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        palette = self._settings_palette()
        hint = QLabel(tr("profile_progress_color_hint", "Used when the Nook Level minigame is off. With it on, the ring/bar shows your level progress."))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {palette.get('--fg-subtle', '#6f7177')}; font-size: 11px; background: transparent; border: none;")
        outer.addWidget(hint)

        self.profile_fill_light_color_button = self._create_main_bg_button("Color")
        self.profile_fill_light_color_value_button = self._create_main_bg_button("")
        self.profile_fill_light_color_value_button.setObjectName("mainBackgroundColorButton")
        self.profile_fill_dark_color_button = self._create_main_bg_button("Dark Color")
        self.profile_fill_dark_color_value_button = self._create_main_bg_button("")
        self.profile_fill_dark_color_value_button.setObjectName("mainBackgroundColorButton")
        self.profile_fill_light_color_card = self._create_color_selector_card(self.profile_fill_light_color_button, self.profile_fill_light_color_value_button)
        self.profile_fill_dark_color_card = self._create_color_selector_card(self.profile_fill_dark_color_button, self.profile_fill_dark_color_value_button)

        # Stacked light/dark cards (constant height, no reflow) as with the other
        # profile asset controls.
        self.profile_fill_color_stack = QStackedWidget()
        self.profile_fill_color_stack.addWidget(self.profile_fill_light_color_card)
        self.profile_fill_color_stack.addWidget(self.profile_fill_dark_color_card)
        outer.addWidget(self.profile_fill_color_stack)
        outer.addStretch(1)

        # Hidden per-asset toggle kept in sync with the shared Dynamic mode so the
        # save path (which reads per-asset toggles) stays uniform.
        self.profile_fill_dynamic_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.profile_fill_dynamic_toggle.setChecked(bool(mw.col.conf.get("modern_menu_profile_fill_dynamic_mode", True)))

        self.profile_fill_light_color_button.clicked.connect(lambda: self._choose_profile_fill_color("light"))
        self.profile_fill_light_color_value_button.clicked.connect(lambda: self._choose_profile_fill_color("light"))
        self.profile_fill_dark_color_button.clicked.connect(lambda: self._choose_profile_fill_color("dark"))
        self.profile_fill_dark_color_value_button.clicked.connect(lambda: self._choose_profile_fill_color("dark"))
        for line_edit in (self.profile_fill_light_color_input, self.profile_fill_dark_color_input):
            line_edit.textChanged.connect(lambda _=None: self._update_profile_fill_controls())

        self._update_profile_fill_controls()
        return widget

    def _profile_dynamic(self):
        toggle = getattr(self, "profile_dynamic_toggle", None)
        return toggle.isChecked() if toggle is not None else True

    def _profile_mode(self):
        return getattr(self, "profile_preview_mode", "light") if self._profile_dynamic() else "light"

    def _on_profile_preview_mode_toggled(self, mode):
        self.profile_preview_mode = "dark" if mode == "dark" else "light"
        self._refresh_all_profile_controls()

    def _on_profile_dynamic_toggled(self, checked):
        # Drive every per-asset dynamic toggle from the single shared control so
        # the existing per-asset save/gallery logic keeps working unchanged.
        for name in (
            "profile_pic_dynamic_toggle",
            "profile_bg_dynamic_toggle",
            "profile_name_dynamic_toggle",
            "profile_fill_dynamic_toggle",
        ):
            toggle = getattr(self, name, None)
            if toggle is not None and toggle.isChecked() != checked:
                toggle.blockSignals(True)
                toggle.setChecked(checked)
                toggle.blockSignals(False)
        self._refresh_all_profile_controls()

    def _refresh_all_profile_controls(self):
        if hasattr(self, "profile_preview_mode_widget"):
            dynamic = self._profile_dynamic()
            self.profile_preview_mode_widget.setEnabled(dynamic)
            self.profile_preview_mode_widget.setToolTip(
                "" if dynamic else tr("enable_dynamic_lock_hint", "Enable Dynamic mode to switch light/dark palettes.")
            )
        for name in (
            "_update_profile_picture_controls",
            "_update_profile_background_controls",
            "_update_profile_name_color_controls",
            "_update_profile_fill_controls",
        ):
            fn = getattr(self, name, None)
            if fn is not None:
                fn()
        self._update_profile_asset_preview()

    def _set_profile_type(self, ptype):
        if ptype not in ("bar", "ring", "minimal"):
            ptype = "bar"
        self.selected_profile_type = ptype
        # Toggle which asset tab is relevant (bar -> Background, ring/minimal ->
        # Progress Color). The tab control is built once and never torn down, so
        # switching type doesn't flicker.
        self._apply_profile_asset_tab_visibility()
        self._update_profile_asset_preview()

    def _build_profile_asset_tabs(self):
        """Build the gooey asset-tab control once with all four segments. Type
        changes only hide/show a segment (no rebuild), keeping switches smooth."""
        layout = getattr(self, "profile_asset_tabs_layout", None)
        if layout is None:
            return
        options = [
            (0, tr("profile_picture")),
            (1, tr("profile_bar_bg")),
            (2, tr("profile_name_color", "Name Color")),
            (3, tr("profile_progress_color", "Progress Color")),
        ]
        self.profile_asset_tab_group = QButtonGroup(self)
        self.profile_asset_tab_group.setExclusive(True)
        shell = self._create_organize_segmented_control(
            options,
            self.profile_asset_tab_group,
            0,
            "profile_asset_page",
            segment_height=30,
            min_button_width=64,
        )
        self.profile_asset_tabs_shell = shell
        self.profile_asset_tab_buttons = {
            int(btn.property("profile_asset_page")): btn for btn in self.profile_asset_tab_group.buttons()
        }
        self.profile_asset_tab_group.buttonToggled.connect(
            lambda btn, ch: self._set_profile_asset_page(int(btn.property("profile_asset_page"))) if ch else None
        )
        # Light/dark preview toggle rides inside the same pill as the asset tabs
        # (both navigation controls); the shell paints its rounded background
        # across whatever it contains, and the blob ignores it (QAbstractButton,
        # not a segment QPushButton).
        preview_toggle = getattr(self, "profile_preview_mode_widget", None)
        if preview_toggle is not None:
            shell.segment_layout.addSpacing(16)
            shell.segment_layout.addWidget(preview_toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        # Insert before the row's trailing stretch so both pills stay centered
        # together on one line.
        layout.insertWidget(max(layout.count() - 1, 0), shell)

    def _apply_profile_asset_tab_visibility(self):
        buttons = getattr(self, "profile_asset_tab_buttons", None)
        if not buttons:
            return
        is_bar = self.selected_profile_type == "bar"
        buttons[1].setVisible(is_bar)          # Profile Bar Background
        buttons[3].setVisible(not is_bar)      # Progress Color
        checked = self.profile_asset_tab_group.checkedButton()
        if checked is None or not checked.isVisible():
            # Selected tab was hidden by the type switch — fall back to Picture.
            buttons[0].setChecked(True)
        # Height only changes here (a type switch), never on a tab switch — so
        # switching tabs can't move anything. Deferred so page sizeHints are
        # accurate after the visibility change lays out.
        QTimer.singleShot(0, self._resize_profile_asset_stack)

    def _resize_profile_asset_stack(self):
        # Pin the stack to the tallest page whose tab is currently visible. The
        # hidden page (Progress Color on bar, or Bar Background on ring/minimal)
        # is excluded so it can't inflate the height into a large empty gap, and
        # a fixed height means tab switches never resize the stack (no jump).
        stack = getattr(self, "profile_asset_controls_stack", None)
        buttons = getattr(self, "profile_asset_tab_buttons", None)
        if stack is None or not buttons:
            return
        heights = []
        for i in range(stack.count()):
            btn = buttons.get(i)
            if btn is not None and not btn.isVisible():
                continue
            heights.append(stack.widget(i).sizeHint().height())
        if heights:
            stack.setFixedHeight(max(heights))

    def _choose_profile_fill_color(self, target):
        line_edit = self.profile_fill_dark_color_input if target == "dark" else self.profile_fill_light_color_input
        chosen, ok = OnigiriColorDialog.getColor(line_edit.text(), self, anchor=self.sender() if isinstance(self.sender(), QWidget) else None)
        if ok:
            line_edit.setText(chosen)
            self._update_profile_fill_controls()

    def _update_profile_fill_controls(self, *args):
        if not hasattr(self, "profile_fill_light_color_card"):
            return
        dynamic = self._profile_dynamic()
        self.profile_fill_light_color_button.setText("Light Color" if dynamic else "Color")
        show_dark = dynamic and getattr(self, "profile_preview_mode", "light") == "dark"
        self.profile_fill_color_stack.setCurrentIndex(1 if show_dark else 0)
        light = self._profile_name_color_for_input(self.profile_fill_light_color_input, "#4f7cff")
        dark = self._profile_name_color_for_input(self.profile_fill_dark_color_input, "#4f7cff")
        self._style_main_background_color_button(self.profile_fill_light_color_value_button, light)
        self._style_main_background_color_button(self.profile_fill_dark_color_value_button, dark)
        self._update_profile_asset_preview()

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

        # Top panel: gooey type selector + Dynamic mode + light/dark toggle.
        outer.addWidget(self._create_profile_type_controls())

        # Asset tabs ride inside the top panel row (see _build_profile_asset_tabs).

        self.profile_asset_preview = BackgroundPreviewLabel(aspect_ratio=5.0, minimum_preview_height=130)
        self.profile_asset_preview.setObjectName("mainBackgroundPreview")
        self.profile_asset_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_asset_preview.setProperty("profile_asset_preview", True)
        self.profile_asset_preview.installEventFilter(self)
        outer.addWidget(self.profile_asset_preview)

        self.profile_asset_controls_stack = QStackedWidget()
        self.profile_asset_controls_stack.addWidget(self._create_profile_picture_controls())
        self.profile_asset_controls_stack.addWidget(self._create_profile_background_controls())
        self.profile_asset_controls_stack.addWidget(self._create_profile_name_color_controls())
        self.profile_asset_controls_stack.addWidget(self._create_profile_progress_color_controls())
        outer.addWidget(self.profile_asset_controls_stack)

        # Build the asset tabs once (stack now exists), start on Profile Picture.
        self._build_profile_asset_tabs()
        self._set_profile_asset_page(0)
        # Sync every per-asset dynamic toggle to the shared control, then refresh
        # all controls + preview once.
        self._on_profile_dynamic_toggled(self.profile_dynamic_toggle.isChecked())
        # Apply tab visibility for the saved type now that the tabs + preview exist.
        if hasattr(self, "selected_profile_type"):
            self._set_profile_type(self.selected_profile_type)
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

        # Light/dark cards share one slot via a QStackedWidget (mirrors Box Color
        # & Effect) so switching preview mode never changes layout height -> no
        # page reflow / flicker.
        self.profile_pic_color_stack = QStackedWidget()
        self.profile_pic_color_stack.addWidget(self.profile_pic_light_color_card)
        self.profile_pic_color_stack.addWidget(self.profile_pic_dark_color_card)

        left_layout.addWidget(self.profile_pic_import_button, 0, 0)
        left_layout.addWidget(self.profile_pic_clear_button, 0, 1)
        left_layout.addWidget(self.profile_pic_gallery_button, 1, 0, 1, 2)
        left_layout.addWidget(self.profile_pic_color_stack, 2, 0, 1, 2)
        left_layout.setRowStretch(3, 1)

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

        outer.addWidget(ResponsivePairWidget(
            left, right, spacing=18, breakpoint=720,
            left_alignment=Qt.AlignmentFlag.AlignTop, right_alignment=Qt.AlignmentFlag.AlignTop,
        ))
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

        # Stacked light/dark cards (constant height, no reflow) as with the
        # profile picture controls above.
        self.profile_bg_color_stack = QStackedWidget()
        self.profile_bg_color_stack.addWidget(self.profile_bg_light_color_card)
        self.profile_bg_color_stack.addWidget(self.profile_bg_dark_color_card)

        left_layout.addWidget(self.profile_bg_import_button, 0, 0)
        left_layout.addWidget(self.profile_bg_clear_button, 0, 1)
        left_layout.addWidget(self.profile_bg_gallery_button, 1, 0, 1, 2)
        left_layout.addWidget(self.profile_bg_color_stack, 2, 0, 1, 2)
        left_layout.setRowStretch(3, 1)

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
        saved_profile_opacity = mw.col.conf.get("modern_menu_profile_bg_opacity", 50)
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
        bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "image")
        self.profile_bg_dynamic_toggle.setChecked(bool(mw.col.conf.get("modern_menu_profile_bg_dynamic_mode", True)))
        self.profile_bg_color_only_toggle.setChecked(bg_mode != "image")
        self.profile_bg_accent_toggle.setChecked(bg_mode == "accent")

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        right_layout.addWidget(self._create_main_bg_value_row("Blur", blur_value))
        right_layout.addWidget(self._create_main_bg_value_row("Opacity", opacity_value))
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

        outer.addWidget(ResponsivePairWidget(
            left, right, spacing=18, breakpoint=720,
            left_alignment=Qt.AlignmentFlag.AlignTop, right_alignment=Qt.AlignmentFlag.AlignTop,
        ))
        return widget

    def _create_profile_page_background_controls(self):
        return QWidget()

    def _set_profile_asset_page(self, index):
        # The gooey asset-tab control owns its own selection. The stack keeps a
        # CONSTANT height (QStackedWidget's default: the max sizeHint of every
        # page), so switching tabs never changes the stack's geometry. That is
        # deliberate: the previous "hug the active page" approach (collapsing
        # inactive pages via an Ignored size policy) made the stack shrink/grow
        # on every switch, which bounced the scroll area — the page visibly
        # jumped up then settled. A short page simply leaves neutral space below
        # its content, which is invisible inside the designer card.
        stack = getattr(self, "profile_asset_controls_stack", None)
        if stack is None:
            return
        stack.setCurrentIndex(index)

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
        dynamic = self._profile_dynamic()
        use_accent = self.profile_pic_accent_toggle.isChecked()
        color_only = self.profile_pic_color_only_toggle.isChecked()
        color_mode = color_only or use_accent
        self.profile_pic_light_color_button.setText("Light Color" if dynamic else "Color")
        # Only the color card for the active light/dark preview mode is shown.
        show_dark = dynamic and getattr(self, "profile_preview_mode", "light") == "dark"
        self.profile_pic_color_stack.setVisible(not use_accent)
        self.profile_pic_color_stack.setCurrentIndex(1 if show_dark else 0)
        for widget in (self.profile_pic_import_button, self.profile_pic_gallery_button):
            widget.setEnabled(not color_mode)
        self.profile_pic_opacity_slider.setEnabled(not color_mode)
        light = self._profile_pic_color_for_input(self.profile_pic_light_color_input, "#8CACB4")
        dark = self._profile_pic_color_for_input(self.profile_pic_dark_color_input, "#B8BDC3")
        self._style_main_background_color_button(self.profile_pic_light_color_value_button, light)
        self._style_main_background_color_button(self.profile_pic_dark_color_value_button, dark)
        self.profile_pic_opacity_value_label.setText(f"{self.profile_pic_opacity_slider.value()}%")
        self._update_profile_asset_preview()

    def _create_profile_name_color_controls(self):
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        outer.addWidget(self._create_profile_name_font_control())

        self.profile_name_light_color_button = self._create_main_bg_button("Color")
        self.profile_name_light_color_value_button = self._create_main_bg_button("")
        self.profile_name_light_color_value_button.setObjectName("mainBackgroundColorButton")
        self.profile_name_dark_color_button = self._create_main_bg_button("Dark Color")
        self.profile_name_dark_color_value_button = self._create_main_bg_button("")
        self.profile_name_dark_color_value_button.setObjectName("mainBackgroundColorButton")

        self.profile_name_light_color_card = self._create_color_selector_card(self.profile_name_light_color_button, self.profile_name_light_color_value_button)
        self.profile_name_dark_color_card = self._create_color_selector_card(self.profile_name_dark_color_button, self.profile_name_dark_color_value_button)

        # Hidden per-asset toggle kept in sync with the shared Dynamic mode.
        self.profile_name_dynamic_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.profile_name_dynamic_toggle.setChecked(bool(mw.col.conf.get("modern_menu_profile_name_dynamic_mode", True)))

        # Stacked light/dark cards (constant height, no reflow) as with the other
        # profile asset controls.
        self.profile_name_color_stack = QStackedWidget()
        self.profile_name_color_stack.addWidget(self.profile_name_light_color_card)
        self.profile_name_color_stack.addWidget(self.profile_name_dark_color_card)

        outer.addWidget(self.profile_name_color_stack)
        outer.addStretch(1)

        self.profile_name_light_color_input = QLineEdit(mw.col.conf.get("modern_menu_profile_name_color_light", "#111827"))
        self.profile_name_single_color_input = self.profile_name_light_color_input
        self.profile_name_dark_color_input = QLineEdit(mw.col.conf.get("modern_menu_profile_name_color_dark", "#f9fafb"))

        self.profile_name_light_color_button.clicked.connect(lambda: self._choose_profile_name_color("light"))
        self.profile_name_light_color_value_button.clicked.connect(lambda: self._choose_profile_name_color("light"))
        self.profile_name_dark_color_button.clicked.connect(lambda: self._choose_profile_name_color("dark"))
        self.profile_name_dark_color_value_button.clicked.connect(lambda: self._choose_profile_name_color("dark"))
        self.profile_name_dynamic_toggle.toggled.connect(self._update_profile_name_color_controls)
        for line_edit in (self.profile_name_light_color_input, self.profile_name_dark_color_input):
            line_edit.textChanged.connect(lambda _=None: self._update_profile_name_color_controls())

        return widget

    def _create_profile_name_font_control(self):
        # Mirrors the Pomodoro "Timer Font" card (_create_pomodoro_font_control
        # in _page_pomodoro.py): a clickable card that opens the shared
        # FontPickerDialog, but here it applies to the profile bar username.
        palette = self._settings_palette()
        card_bg = palette.get("--canvas-inset", "#ffffff")
        card_border = palette.get("--border", "#dcdde1")
        hover_bg = palette.get("--hover-bg", "#f2f2f2")
        text_color = palette.get("--fg", "#202124")
        subtle_color = palette.get("--fg-subtle", "#6f7177")

        self.selected_profile_name_font_key = mw.col.conf.get("modern_menu_profile_name_font", "system") or "system"

        card = _ProfileNameFontCard(self._open_profile_name_font_picker)
        card.setObjectName("profileNameFontCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setMinimumHeight(60)
        card.setStyleSheet(f"""
            QFrame#profileNameFontCard {{ background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 16px; }}
            QFrame#profileNameFontCard:hover {{ background-color: {hover_bg}; }}
        """)

        row = QHBoxLayout(card)
        row.setContentsMargins(14, 8, 12, 8)
        row.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        name_label = QLabel(tr("profile_name_font", "Name Font"))
        name_label.setStyleSheet(f"background: transparent; border: none; font-weight: bold; color: {text_color}; font-size: 13px;")
        value_label = QLabel()
        value_label.setStyleSheet(f"background: transparent; border: none; color: {subtle_color}; font-size: 10px;")
        text_col.addWidget(name_label)
        text_col.addWidget(value_label)

        preview = QLabel()
        preview.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        preview.setStyleSheet(f"background: transparent; border: none; color: {text_color};")

        row.addLayout(text_col, 1)
        row.addWidget(preview)

        self.profile_name_font_preview_label = preview
        self.profile_name_font_value_label = value_label
        self._refresh_profile_name_font_card()
        return card

    def _profile_name_font_family(self, font_key=None):
        # Registers a bundled/user font with Qt and returns its family name,
        # caching in the same _font_family_cache used by the Pomodoro card.
        if font_key is None:
            font_key = getattr(self, "selected_profile_name_font_key", None) or mw.col.conf.get("modern_menu_profile_name_font", "system")
        if not font_key or font_key == "system":
            return ""
        cache = getattr(self, "_font_family_cache", None)
        if cache is None:
            cache = self._font_family_cache = {}
        if font_key in cache:
            return cache[font_key]
        info = get_all_fonts(self.addon_path).get(font_key, {})
        font_file = info.get("file")
        if not font_file:
            cache[font_key] = info.get("family", "")
            return cache[font_key]
        if info.get("user"):
            path = os.path.join(self.addon_path, "user_files", "fonts", font_file)
        else:
            path = os.path.join(self.addon_path, "system_files", "fonts", "system_fonts", font_file)
        if not os.path.exists(path):
            cache[font_key] = info.get("family", "")
            return cache[font_key]
        font_id = QFontDatabase.addApplicationFont(path)
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id != -1 else []
        cache[font_key] = families[0] if families else info.get("family", "")
        return cache[font_key]

    def _refresh_profile_name_font_card(self):
        key = getattr(self, "selected_profile_name_font_key", "system") or "system"
        info = get_all_fonts(self.addon_path).get(key, {})
        display = tr("system") if key == "system" else info.get("name", key)
        value_label = getattr(self, "profile_name_font_value_label", None)
        if value_label is not None:
            value_label.setText(f"{display} · {tr('click_to_change')}")
        preview = getattr(self, "profile_name_font_preview_label", None)
        if preview is not None:
            sample = (self.name_input.text() if hasattr(self, "name_input") else "") or self.current_config.get("userName", DEFAULTS["userName"]) or "Aa"
            preview.setText(sample[:14])
            family = self._profile_name_font_family(key)
            font = QFont()
            if family:
                font.setFamily(family)
            font.setPixelSize(18)
            font.setWeight(QFont.Weight.Medium)
            preview.setFont(font)

    def _open_profile_name_font_picker(self):
        sample = (self.name_input.text() if hasattr(self, "name_input") else "") or self.current_config.get("userName", DEFAULTS["userName"]) or "Aa"
        dialog = FontPickerDialog(
            getattr(self, "selected_profile_name_font_key", "system"),
            self.addon_path,
            self,
            sample_text=sample[:14],
            title=tr("profile_name_font", "Name Font"),
        )

        def on_selected(font_key):
            self.selected_profile_name_font_key = font_key or "system"
            self._refresh_profile_name_font_card()
            self._update_profile_asset_preview()

        dialog.fontSelected.connect(on_selected)
        dialog.exec()

    def _create_profile_name_toggle_card(self, label_text, toggle):
        # Wraps a toggle in the same bordered container used by the color
        # selector cards, so the row doesn't read as a bare floating control.
        palette = self._settings_palette()
        card_bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        card_border = palette.get("--border", "#454545" if theme_manager.night_mode else "#dcdde1")
        fg = palette.get("--fg", "#f9fafb" if theme_manager.night_mode else "#111827")
        card = QFrame()
        card.setObjectName("colorSelectorCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setStyleSheet(f"""
            QFrame#colorSelectorCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 16px;
            }}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 8, 14, 8)
        layout.setSpacing(12)
        label = QLabel(label_text)
        label.setStyleSheet(f"background: transparent; border: none; color: {fg}; font-size: 13px; font-weight: 700;")
        label.setFixedHeight(36)
        layout.addWidget(label, 1)
        layout.addWidget(toggle, 0)
        return card

    def _profile_name_color_for_input(self, line_edit, fallback="#111827"):
        color = line_edit.text() if line_edit else fallback
        return color if QColor(color).isValid() else fallback

    def _profile_name_color_settings(self):
        # Name color is always active (no on/off) — returns (enabled, light, dark, dynamic).
        dynamic = bool(self.profile_name_dynamic_toggle.isChecked()) if getattr(self, "profile_name_dynamic_toggle", None) else True
        light = self._profile_name_color_for_input(getattr(self, "profile_name_light_color_input", None), "#111827")
        dark = self._profile_name_color_for_input(getattr(self, "profile_name_dark_color_input", None), "#f9fafb")
        if not dynamic:
            dark = light
        return True, light, dark, dynamic

    def _profile_name_color_for_mode(self, mode):
        _enabled, light, dark, _dynamic = self._profile_name_color_settings()
        return dark if mode == "dark" else light

    def _choose_profile_name_color(self, target):
        line_edit = self.profile_name_dark_color_input if target == "dark" else self.profile_name_light_color_input
        chosen, ok = OnigiriColorDialog.getColor(line_edit.text(), self, anchor=self.sender() if isinstance(self.sender(), QWidget) else None)
        if ok:
            line_edit.setText(chosen)
            self._update_profile_name_color_controls()

    def _update_profile_name_color_controls(self, *args):
        if not hasattr(self, "profile_name_light_color_card"):
            return
        dynamic = self._profile_dynamic()
        self.profile_name_light_color_button.setText("Light Color" if dynamic else "Color")
        show_dark = dynamic and getattr(self, "profile_preview_mode", "light") == "dark"
        self.profile_name_color_stack.setCurrentIndex(1 if show_dark else 0)
        light = self._profile_name_color_for_input(self.profile_name_light_color_input, "#111827")
        dark = self._profile_name_color_for_input(self.profile_name_dark_color_input, "#f9fafb")
        self._style_main_background_color_button(self.profile_name_light_color_value_button, light)
        self._style_main_background_color_button(self.profile_name_dark_color_value_button, dark)
        self._update_profile_asset_preview()

    def _profile_bg_color_for_input(self, line_edit, fallback="#ffffff"):
        color = line_edit.text() if line_edit else fallback
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
        dynamic = self._profile_dynamic()
        use_accent = self.profile_bg_accent_toggle.isChecked()
        color_only = self.profile_bg_color_only_toggle.isChecked()
        color_mode = color_only or use_accent
        self.profile_bg_light_color_button.setText("Light Color" if dynamic else "Color")
        show_dark = dynamic and getattr(self, "profile_preview_mode", "light") == "dark"
        self.profile_bg_color_stack.setVisible(not use_accent)
        self.profile_bg_color_stack.setCurrentIndex(1 if show_dark else 0)
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
        self._sync_profile_bar_widget()
        if not hasattr(self, "profile_asset_preview"):
            return
        self.profile_asset_preview.setStyleSheet("QLabel#mainBackgroundPreview { background: transparent; border: none; }")
        self.profile_asset_preview.setPixmap(self._render_profile_asset_preview_pixmap())
        self.profile_asset_preview.setText("")

    def _sync_profile_bar_widget(self):
        """Keeps the real ProfileBarWidget (dialog sidebar + Sidebar
        Customization preview mockup, which reuses it) in step with unsaved
        edits made on this tab, instead of only reflecting values as of dialog
        open."""
        profile_bar = getattr(self, "profile_bar", None)
        if profile_bar is None:
            return
        is_dark = theme_manager.night_mode
        user_name = self.name_input.text() if hasattr(self, "name_input") else self.current_config.get("userName", DEFAULTS["userName"])

        if getattr(self, "profile_pic_accent_toggle", None) and self.profile_pic_accent_toggle.isChecked():
            pic_mode = "accent"
        elif getattr(self, "profile_pic_color_only_toggle", None) and self.profile_pic_color_only_toggle.isChecked():
            pic_mode = "custom"
        else:
            pic_mode = "image"
        pic_light_color, pic_dark_color = self._profile_pic_colors() if hasattr(self, "_profile_pic_colors") else ("#8CACB4", "#B8BDC3")
        pic_filename = self._profile_pic_image_name("dark" if is_dark else "light") if hasattr(self, "_profile_pic_image_name") else ""
        pic_path = self._profile_asset_image_path("profile_pic", pic_filename) if pic_filename else ""

        if getattr(self, "profile_bg_accent_toggle", None) and self.profile_bg_accent_toggle.isChecked():
            bg_mode = "accent"
        elif getattr(self, "profile_bg_color_only_toggle", None) and self.profile_bg_color_only_toggle.isChecked():
            bg_mode = "custom"
        else:
            bg_mode = "image"
        bg_light_color, bg_dark_color = self._profile_bg_colors() if hasattr(self, "_profile_bg_colors") else ("#EEEEEE", "#3C3C3C")
        bg_image_filename = self.galleries.get("profile_bg", {}).get("selected", "") if hasattr(self, "galleries") else ""
        bg_image_path = self._profile_asset_image_path("profile_bg", bg_image_filename) if bg_image_filename else ""

        bg_config = {
            "color": bg_dark_color if is_dark else bg_light_color,
            "image": bg_image_path,
            "blur": self.profile_bg_blur_slider.value() if hasattr(self, "profile_bg_blur_slider") else 0,
            "opacity": self.profile_bg_opacity_slider.value() if hasattr(self, "profile_bg_opacity_slider") else 100,
        }
        pic_config = {
            "mode": pic_mode,
            "color": pic_dark_color if is_dark else pic_light_color,
            "blur": 0,
            "opacity": self.profile_pic_opacity_slider.value() if hasattr(self, "profile_pic_opacity_slider") else 100,
        }
        profile_bar.update_profile(user_name, pic_path, bg_mode, bg_config, pic_config)
        if hasattr(self, "_profile_name_color_settings") and hasattr(profile_bar, "set_name_color_override"):
            profile_bar.set_name_color_override(*self._profile_name_color_settings())
        if hasattr(profile_bar, "set_name_font_override"):
            profile_bar.set_name_font_override(getattr(self, "selected_profile_name_font_key", "system"))
        if self._modern_background_spec("sidebar"):
            self._update_modern_background_preview("sidebar")

    def _profile_preview_sidebar_bg_state(self, mode):
        """Sidebar Customization background for the profile preview backdrop.
        Uses the live sidebar-page state when that page is built (reflects unsaved
        edits); otherwise reads the saved conf so it still matches the sidebar."""
        mode = "dark" if mode == "dark" else "light"
        if hasattr(self, "sidebar_bg_single_color_input") and hasattr(self, "_deck_icon_sidebar_background_state"):
            try:
                return self._deck_icon_sidebar_background_state(mode)
            except Exception:
                pass
        conf = mw.col.conf
        bg_type = conf.get("modern_menu_sidebar_bg_type", "color")
        if bg_type == "image":
            bg_type = "image_color"
        if bg_type == "accent":
            color = self.accent_color
        else:
            color_theme = conf.get("modern_menu_sidebar_bg_color_theme_mode", "separate")
            light = conf.get("modern_menu_sidebar_bg_color_light", "#F3F3F3")
            dark = conf.get("modern_menu_sidebar_bg_color_dark", "#2C2C2C")
            color = dark if (color_theme != "single" and mode == "dark") else light
        image_name = ""
        if bg_type == "image_color":
            image_theme = conf.get("modern_menu_sidebar_bg_image_theme_mode", "separate")
            if image_theme == "separate":
                image_name = conf.get(
                    "modern_menu_sidebar_bg_image_dark" if mode == "dark" else "modern_menu_sidebar_bg_image_light", ""
                ) or conf.get("modern_menu_sidebar_bg_image", "")
            else:
                image_name = conf.get("modern_menu_sidebar_bg_image", "")
            if not image_name:
                images = conf.get("modern_menu_sidebar_slideshow_images", []) or []
                image_name = images[0] if images else ""
        image_path = os.path.join(self.addon_path, "user_files", "sidebar_bg", image_name) if image_name else ""
        if image_path and not os.path.exists(image_path):
            image_path = ""
        return {
            "color": color,
            "image_path": image_path,
            "blur": int(conf.get("modern_menu_sidebar_bg_blur", 0) or 0),
            "opacity": int(conf.get("modern_menu_sidebar_bg_opacity", 100) or 100),
        }

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

        # Backdrop = the saved Sidebar Customization background, so the profile
        # preview always sits on the same surface as the real sidebar.
        painter.setClipPath(bg_path)
        sidebar_state = self._profile_preview_sidebar_bg_state(self._profile_mode())
        painter.fillRect(bg_rect, QColor(sidebar_state["color"]))
        sidebar_image = sidebar_state.get("image_path", "")
        if sidebar_image and os.path.exists(sidebar_image):
            image = self._background_cover_image_with_effect(
                sidebar_image,
                int(bg_rect.width()),
                int(bg_rect.height()),
                int(sidebar_state.get("blur", 0) or 0),
            )
            if not image.isNull():
                painter.setOpacity(max(0.0, min(1.0, float(sidebar_state.get("opacity", 100)) / 100.0)))
                painter.drawPixmap(int(bg_rect.x()), int(bg_rect.y()), image)
                painter.setOpacity(1.0)
        painter.setClipping(False)
        painter.setPen(QPen(border, 1))
        painter.drawPath(bg_path)

        margin = 20
        pill_height = min(82, max(54, int((height - margin * 2) * 0.72)))
        # Single preview showing only the shared light/dark preview mode (mirrors
        # Widget Color & Effect). Dynamic mode off forces light.
        preview_mode = self._profile_mode()
        pill_width = min(max(300, int(width * 0.62)), max(120, width - margin * 2))
        y = int((height - pill_height) / 2)
        preview_rects = [(preview_mode, QRectF((width - pill_width) / 2, y, pill_width, pill_height))]
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
            custom_name_color = self._profile_name_color_for_mode(mode) if hasattr(self, "_profile_name_color_for_mode") else None
            if custom_name_color and QColor(custom_name_color).isValid():
                text_color = QColor(custom_name_color)
            else:
                text_color = QColor("#ffffff") if image_path or QColor(color).lightness() < 145 else QColor("#111827")
            painter.setPen(text_color)
            font = painter.font()
            font.setBold(False)
            font.setPointSize(22 if rect.width() > 260 else 16)
            name_font_family = self._profile_name_font_family() if hasattr(self, "_profile_name_font_family") else ""
            if name_font_family:
                font.setFamily(name_font_family)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, metrics.elidedText(user_name, Qt.TextElideMode.ElideRight, int(text_rect.width())))

        def _preview_name_color(mode):
            custom = self._profile_name_color_for_mode(mode) if hasattr(self, "_profile_name_color_for_mode") else None
            if custom and QColor(custom).isValid():
                return QColor(custom)
            return QColor("#ffffff") if mode == "dark" else QColor("#111827")

        def draw_ring_preview(rect, mode):
            ring_d = int(max(44, min(rect.height() * 0.86, rect.width() * 0.42)))
            ring_rect = QRectF(rect.x() + 12, rect.center().y() - ring_d / 2, ring_d, ring_d)
            stroke = max(3.0, ring_d * 0.09)
            arc_rect = ring_rect.adjusted(stroke / 2, stroke / 2, -stroke / 2, -stroke / 2)
            inset = stroke * 1.7
            inner = ring_rect.adjusted(inset, inset, -inset, -inset)
            avatar, _ = render_avatar(mode)
            if not avatar.isNull():
                clip = QPainterPath()
                clip.addEllipse(inner)
                painter.setClipPath(clip)
                painter.drawPixmap(inner, avatar, QRectF(avatar.rect()))
                painter.setClipping(False)
            nook_enabled, nook_level_num, nook_fraction, nook_color = self._preview_nook_level_state()
            fill_color = nook_color if (nook_enabled and nook_color) else self._preview_profile_fill_color(mode)
            arc_fraction = nook_fraction if nook_enabled else 1.0

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(128, 128, 128, 90), stroke))
            painter.drawArc(arc_rect, 0, 360 * 16)
            fill_pen = QPen(fill_color, stroke)
            fill_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(fill_pen)
            painter.drawArc(arc_rect, 90 * 16, -int(360 * arc_fraction * 16))

            tc = _preview_name_color(mode)
            text_x = ring_rect.right() + max(10, int(ring_d * 0.22))
            tr_rect = QRectF(text_x, rect.y(), max(10, rect.right() - text_x - 12), rect.height())
            name_font = painter.font()
            name_font.setBold(True)
            name_font.setPointSize(18 if rect.width() > 260 else 14)
            fam = self._profile_name_font_family() if hasattr(self, "_profile_name_font_family") else ""
            if fam:
                name_font.setFamily(fam)
            painter.setFont(name_font)
            painter.setPen(tc)
            m = painter.fontMetrics()
            if nook_enabled:
                name_rect = QRectF(tr_rect.x(), tr_rect.y(), tr_rect.width(), tr_rect.height() * 0.56)
                level_rect = QRectF(tr_rect.x(), tr_rect.center().y() - 1, tr_rect.width(), tr_rect.height() * 0.44)
                painter.drawText(name_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                                 m.elidedText(user_name, Qt.TextElideMode.ElideRight, int(name_rect.width())))
                level_font = painter.font()
                level_font.setBold(False)
                level_font.setPointSize(11 if rect.width() > 260 else 9)
                painter.setFont(level_font)
                painter.setPen(QColor(tc.red(), tc.green(), tc.blue(), 175))
                painter.drawText(level_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, f"{tr('level_prefix')} {nook_level_num}")
            else:
                painter.drawText(tr_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                 m.elidedText(user_name, Qt.TextElideMode.ElideRight, int(tr_rect.width())))

        def draw_minimal_preview(rect, mode):
            top_h = rect.height() * 0.58
            a_d = int(max(28, min(top_h * 0.92, rect.height() * 0.5)))
            avatar_rect = QRectF(rect.x() + 14, rect.y() + (top_h - a_d) / 2, a_d, a_d)
            avatar, _ = render_avatar(mode)
            if not avatar.isNull():
                clip = QPainterPath()
                clip.addEllipse(avatar_rect)
                painter.setClipPath(clip)
                painter.drawPixmap(avatar_rect, avatar, QRectF(avatar.rect()))
                painter.setClipping(False)
            tc = _preview_name_color(mode)
            painter.setPen(tc)
            name_font = painter.font()
            name_font.setBold(True)
            name_font.setPointSize(17 if rect.width() > 260 else 14)
            fam = self._profile_name_font_family() if hasattr(self, "_profile_name_font_family") else ""
            if fam:
                name_font.setFamily(fam)
            painter.setFont(name_font)
            name_x = avatar_rect.right() + 14
            name_w = max(10, rect.right() - name_x - 12)
            m = painter.fontMetrics()
            painter.drawText(QRectF(name_x, rect.y(), name_w, top_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             m.elidedText(user_name, Qt.TextElideMode.ElideRight, int(name_w)))
            nook_enabled, nook_level_num, nook_fraction, nook_color = self._preview_nook_level_state()
            if nook_enabled:
                bar_y = rect.y() + top_h + max(4, rect.height() * 0.06)
                bar_h = max(6, int(rect.height() * 0.13))
                lv_font = painter.font()
                lv_font.setBold(True)
                lv_font.setPointSize(10 if rect.width() > 260 else 8)
                painter.setFont(lv_font)
                painter.setPen(QColor(tc.red(), tc.green(), tc.blue(), 175))
                lv_text = f"{tr('level_short', 'Lv')} {nook_level_num}"
                lv_w = painter.fontMetrics().horizontalAdvance(lv_text) + 8
                painter.drawText(QRectF(rect.x() + 14, bar_y - bar_h, lv_w, bar_h * 3),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, lv_text)
                track_x = rect.x() + 14 + lv_w
                track_w = rect.right() - track_x - 14
                if track_w > 12:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(QColor(128, 128, 128, 90)))
                    painter.drawRoundedRect(QRectF(track_x, bar_y, track_w, bar_h), bar_h / 2, bar_h / 2)
                    painter.setBrush(QBrush(nook_color if nook_color else self._preview_profile_fill_color(mode)))
                    painter.drawRoundedRect(QRectF(track_x, bar_y, track_w * nook_fraction, bar_h), bar_h / 2, bar_h / 2)

        ptype = self._preview_profile_type()
        for mode, rect in preview_rects:
            if ptype == "ring":
                draw_ring_preview(rect, mode)
            elif ptype == "minimal":
                draw_minimal_preview(rect, mode)
            else:
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

            bg_pixmap = getattr(profile_bar, "_bg_pixmap", None)
            if (
                (getattr(profile_bar, "_bg_mode", None) == "image" or getattr(profile_bar, "_using_default_bg", False))
                and bg_pixmap is not None
                and not bg_pixmap.isNull()
            ):
                try:
                    width = max(1, int(round(bar_rect.width())))
                    height = max(1, int(round(bar_rect.height())))
                    blur = getattr(profile_bar, "_bg_blur", 0)
                    scale_factor = 1.0 + (blur * 0.2 / 50.0) if blur > 0 else 1.0
                    scaled = bg_pixmap.scaled(
                        int(width * scale_factor),
                        int(height * scale_factor),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    x = (scaled.width() - width) // 2
                    y = (scaled.height() - height) // 2
                    cropped = scaled.copy(x, y, width, height)
                    if blur > 0:
                        cropped = profile_bar._blur_pixmap(cropped, blur * 0.2)
                    painter.save()
                    painter.setClipPath(pill_path)
                    painter.setOpacity(max(0.0, min(1.0, getattr(profile_bar, "_bg_opacity", 1.0))))
                    painter.drawPixmap(QRectF(bar_rect.x(), bar_rect.y(), width, height), cropped, QRectF(cropped.rect()))
                    painter.setOpacity(1.0)
                    painter.fillPath(pill_path, QColor(0, 0, 0, PROFILE_BAR_IMAGE_OVERLAY_ALPHA))
                    painter.restore()
                except Exception:
                    pass

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
                name_font_family = self._profile_name_font_family() if hasattr(self, "_profile_name_font_family") else ""
                if name_font_family:
                    font.setFamily(name_font_family)
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

        panel_conf = self.current_config.get("onigiriProfilePanel", {})
        if not isinstance(panel_conf, dict):
            panel_conf = {}
        restaurant_conf = self.current_config.get("restaurant_level", {})
        if not isinstance(restaurant_conf, dict):
            restaurant_conf = {}

        self.profile_panel_chart_toggle = AnimatedToggleButton(accent_color=accent_color)
        self.profile_panel_chart_toggle.setChecked(bool(panel_conf.get("show_weekly_chart", True)))
        self.profile_panel_nook_toggle = AnimatedToggleButton(accent_color="#B94632")
        self.profile_panel_nook_toggle.setChecked(bool(restaurant_conf.get("show_profile_page_progress", True)))
        self.profile_panel_hexagon_toggle = AnimatedToggleButton(accent_color="#2D8CFF")
        self.profile_panel_hexagon_toggle.setChecked(bool(panel_conf.get("show_hexagon_land", True)))
        self.profile_panel_onigimon_toggle = AnimatedToggleButton(accent_color="#F2B705")
        self.profile_panel_onigimon_toggle.setChecked(bool(panel_conf.get("show_onigimon_hp", True)))
        self.profile_panel_mantras_toggle = AnimatedToggleButton(accent_color="#00935C")
        self.profile_panel_mantras_toggle.setChecked(bool(panel_conf.get("show_mantras", True)))

        panel_toggles_header = QLabel(tr("profile_panel_toggles_header", "Show in Profile Panel"))
        panel_toggles_header.setObjectName("profileFormLabel")
        panel_toggles_header.setStyleSheet("font-size: 13px; font-weight: 600; background: transparent; border: none;")

        panel_toggles_grid = QGridLayout()
        panel_toggles_grid.setContentsMargins(0, 0, 0, 0)
        panel_toggles_grid.setHorizontalSpacing(10)
        panel_toggles_grid.setVerticalSpacing(8)
        panel_toggles_grid.setColumnStretch(0, 1)
        panel_toggles_grid.setColumnStretch(1, 1)
        panel_toggles_grid.addWidget(self._create_toggle_row(self.profile_panel_chart_toggle, tr("profile_panel_weekly_chart", "Weekly Study Chart")), 0, 0)
        panel_toggles_grid.addWidget(self._create_toggle_row(self.profile_panel_nook_toggle, tr("profile_panel_nook_level", "Nook Level Progress")), 0, 1)
        panel_toggles_grid.addWidget(self._create_toggle_row(self.profile_panel_hexagon_toggle, tr("profile_panel_hexagon_land", "Hexagon Land Count")), 1, 0)
        panel_toggles_grid.addWidget(self._create_toggle_row(self.profile_panel_onigimon_toggle, tr("profile_panel_onigimon_hp", "Onigimon HP")), 1, 1)
        panel_toggles_grid.addWidget(self._create_toggle_row(self.profile_panel_mantras_toggle, tr("profile_panel_mantras", "My Mantras")), 2, 0, 1, 2)

        gamification_settings_button = QPushButton(tr("open_gamification_settings", "Open Gamification Settings"))
        gamification_settings_button.setObjectName("profilePanelGamificationButton")
        gamification_settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        gamification_settings_button.setAutoDefault(False)
        gamification_settings_button.setStyleSheet(f"""
            QPushButton#profilePanelGamificationButton {{
                margin-top: 2px;
                padding: 8px 14px;
                border-radius: 10px;
                border: 1px solid {accent_color};
                background: transparent;
                color: {accent_color};
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#profilePanelGamificationButton:hover {{
                background: rgba(127, 127, 127, 0.12);
            }}
        """)
        gamification_settings_button.clicked.connect(self._open_gamification_settings_and_close)

        panel_toggles_col = QVBoxLayout()
        panel_toggles_col.setContentsMargins(0, 4, 0, 0)
        panel_toggles_col.setSpacing(10)
        panel_toggles_col.addWidget(panel_toggles_header)
        panel_toggles_col.addLayout(panel_toggles_grid)
        panel_toggles_col.addWidget(gamification_settings_button)

        palette = self._settings_palette()
        card_bg = palette.get("--canvas-inset", "#ffffff")
        card_border = palette.get("--border", "#dcdde1")

        profile_info_card = QFrame()
        profile_info_card.setObjectName("profileInfoCard")
        profile_info_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        profile_info_card.setStyleSheet(f"""
            QFrame#profileInfoCard {{ background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 16px; }}
        """)
        profile_info_card_layout = QVBoxLayout(profile_info_card)
        profile_info_card_layout.setContentsMargins(16, 16, 16, 16)
        profile_info_card_layout.setSpacing(14)
        profile_info_card_layout.addWidget(profile_form_shell)
        profile_info_card_layout.addLayout(panel_toggles_col)

        profile_section.add_widget(profile_info_card)

        layout.addWidget(profile_section)

        profile_assets_section = SectionGroup("", self)
        profile_assets_section.add_widget(self._create_profile_asset_designer())
        layout.addWidget(profile_assets_section)
        self.name_input.textChanged.connect(lambda _=None: self._update_profile_asset_preview())
        self.name_input.textChanged.connect(lambda _=None: self._refresh_profile_name_font_card())

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

    def _open_gamification_settings_and_close(self):
        self.save_settings()
        from .. import gamification_settings
        gamification_settings.open_gamification_settings()

    def _save_profile_settings(self):
        self.current_config["userName"] = self.name_input.text()
        mw.col.conf["modern_menu_userName"] = self.name_input.text()

        if hasattr(self, "selected_profile_type"):
            mw.col.conf["modern_menu_profile_type"] = self.selected_profile_type
        if hasattr(self, "profile_fill_dynamic_toggle"):
            fill_dynamic = self.profile_fill_dynamic_toggle.isChecked()
            mw.col.conf["modern_menu_profile_fill_dynamic_mode"] = fill_dynamic
            if fill_dynamic:
                mw.col.conf["modern_menu_profile_fill_color_light"] = self.profile_fill_light_color_input.text()
                mw.col.conf["modern_menu_profile_fill_color_dark"] = self.profile_fill_dark_color_input.text()
            else:
                single_fill = self.profile_fill_light_color_input.text()
                mw.col.conf["modern_menu_profile_fill_color_light"] = single_fill
                mw.col.conf["modern_menu_profile_fill_color_dark"] = single_fill

        if hasattr(self, "selected_profile_name_font_key"):
            mw.col.conf["modern_menu_profile_name_font"] = self.selected_profile_name_font_key or "system"

        if hasattr(self, "profile_name_dynamic_toggle"):
            dynamic = self.profile_name_dynamic_toggle.isChecked()
            mw.col.conf["modern_menu_profile_name_color_enabled"] = True
            mw.col.conf["modern_menu_profile_name_dynamic_mode"] = dynamic
            if dynamic:
                mw.col.conf["modern_menu_profile_name_color_light"] = self.profile_name_light_color_input.text()
                mw.col.conf["modern_menu_profile_name_color_dark"] = self.profile_name_dark_color_input.text()
            else:
                single_name_color = self.profile_name_light_color_input.text()
                mw.col.conf["modern_menu_profile_name_color_light"] = single_name_color
                mw.col.conf["modern_menu_profile_name_color_dark"] = single_name_color
        
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

        if hasattr(self, "profile_panel_chart_toggle"):
            self.current_config["onigiriProfilePanel"] = {
                "show_weekly_chart": self.profile_panel_chart_toggle.isChecked(),
                "show_hexagon_land": self.profile_panel_hexagon_toggle.isChecked(),
                "show_onigimon_hp": self.profile_panel_onigimon_toggle.isChecked(),
                "show_mantras": self.profile_panel_mantras_toggle.isChecked(),
            }
            res_conf = self.current_config.setdefault("restaurant_level", {})
            res_conf["show_profile_page_progress"] = self.profile_panel_nook_toggle.isChecked()

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
            bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "image")
            bg_image_name = mw.col.conf.get("modern_menu_profile_bg_image", "")
            bg_blur = int(mw.col.conf.get("modern_menu_profile_bg_blur", 0) or 0)
            bg_opacity = int(mw.col.conf.get("modern_menu_profile_bg_opacity", 50) or 50)
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

    def _preview_profile_type(self):
        if getattr(self, "selected_profile_type", None):
            return self.selected_profile_type
        return mw.col.conf.get("modern_menu_profile_type", "bar") or "bar"

    def _preview_profile_fill_color(self, mode):
        # Prefer unsaved edits on the Profile page, else saved conf, else accent.
        if hasattr(self, "profile_fill_light_color_input"):
            dynamic = self.profile_fill_dynamic_toggle.isChecked() if hasattr(self, "profile_fill_dynamic_toggle") else True
            light = self._profile_name_color_for_input(self.profile_fill_light_color_input, self.accent_color)
            dark = self._profile_name_color_for_input(self.profile_fill_dark_color_input, light) if dynamic else light
            val = dark if mode == "dark" else light
        else:
            light = mw.col.conf.get("modern_menu_profile_fill_color_light", self.accent_color)
            dark = mw.col.conf.get("modern_menu_profile_fill_color_dark", light)
            val = dark if mode == "dark" else light
        color = QColor(val)
        return color if color.isValid() else QColor(self.accent_color)

    def _preview_nook_level_state(self):
        """(enabled, level, fraction, color) for the ring/minimal previews —
        mirrors the live-widget rule in onigiri_renderer.py's _nook_level_progress:
        the Level Chip's own Progress color (gamification_settings.py's Nook
        Level > Level Chip Appearance) + real progress when the minigame is on
        (and set to show on the profile bar), else the caller falls back to
        the profile's own fill color and a full ring / no bar."""
        try:
            restaurant_conf = self.current_config.get("restaurant_level", {})
            if not isinstance(restaurant_conf, dict) or not restaurant_conf.get("enabled", False):
                return (False, 0, 0.0, None)
            if not restaurant_conf.get("show_profile_bar_progress", True):
                return (False, 0, 0.0, None)
            from ..gamification import nook_level
            progress = nook_level.manager.get_progress()
            if not progress or not getattr(progress, "enabled", False):
                return (False, 0, 0.0, None)
            level = int(getattr(progress, "level", 0) or 0)
            fraction = float(getattr(progress, "progress_fraction", 0.0) or 0.0)
            fraction = max(0.0, min(1.0, fraction))
            color_hex = nook_level.get_chip_style_values(self.current_config).get("progress")
            color = QColor(color_hex) if color_hex else None
            if color is not None and not color.isValid():
                color = None
            return (True, level, fraction, color)
        except Exception:
            return (False, 0, 0.0, None)

    def _draw_preview_profile_avatar(self, painter, avatar_rect, state):
        avatar_size = int(min(avatar_rect.width(), avatar_rect.height()))
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
            initial_font = self._box_effect_preview_font("main", max(10, int(avatar_size * 0.46)))
            initial_font.setBold(True)
            painter.setFont(initial_font)
            painter.drawText(avatar_rect, Qt.AlignmentFlag.AlignCenter, (state["name"][:1] or "U").upper())

    def _draw_overview_style_profile_ring(self, painter, bar_rect, mode, state):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        ring_d = max(24, int(min(bar_rect.height(), 56)))
        ring_rect = QRectF(bar_rect.x(), bar_rect.center().y() - ring_d / 2, ring_d, ring_d)
        stroke = max(2.5, ring_d * 0.10)
        arc_rect = ring_rect.adjusted(stroke / 2, stroke / 2, -stroke / 2, -stroke / 2)
        inset = stroke * 1.7
        self._draw_preview_profile_avatar(painter, ring_rect.adjusted(inset, inset, -inset, -inset), state)

        nook_enabled, nook_level_num, nook_fraction, nook_color = self._preview_nook_level_state()
        fill_color = nook_color if (nook_enabled and nook_color) else self._preview_profile_fill_color(mode)
        arc_fraction = nook_fraction if nook_enabled else 1.0

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(128, 128, 128, 90), stroke))
        painter.drawArc(arc_rect, 0, 360 * 16)
        fill_pen = QPen(fill_color, stroke)
        fill_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(fill_pen)
        painter.drawArc(arc_rect, 90 * 16, -int(360 * arc_fraction * 16))

        text_color = QColor("#ffffff") if mode == "dark" else QColor("#111827")
        painter.setPen(text_color)
        text_x = ring_rect.right() + max(8, int(ring_d * 0.2))
        text_rect = QRectF(text_x, bar_rect.y(), bar_rect.right() - text_x, bar_rect.height())
        name_font = self._box_effect_preview_font("main", max(12, int(ring_d * 0.30)))
        name_font.setBold(True)
        family = self._profile_name_font_family() if hasattr(self, "_profile_name_font_family") else ""
        if family:
            name_font.setFamily(family)
        show_level = bar_rect.height() >= 46 and nook_enabled
        if show_level:
            name_rect = QRectF(text_rect.x(), text_rect.y(), text_rect.width(), text_rect.height() * 0.56)
            level_rect = QRectF(text_rect.x(), text_rect.center().y() - 1, text_rect.width(), text_rect.height() * 0.44)
            painter.setFont(name_font)
            m = painter.fontMetrics()
            painter.drawText(name_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                             m.elidedText(state["name"], Qt.TextElideMode.ElideRight, int(name_rect.width())))
            level_font = self._box_effect_preview_font("main", max(9, int(ring_d * 0.20)))
            painter.setFont(level_font)
            painter.setPen(QColor(text_color.red(), text_color.green(), text_color.blue(), 170))
            painter.drawText(level_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, f"{tr('level_prefix')} {nook_level_num}")
        else:
            painter.setFont(name_font)
            m = painter.fontMetrics()
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             m.elidedText(state["name"], Qt.TextElideMode.ElideRight, int(text_rect.width())))
        painter.restore()

    def _draw_overview_style_profile_minimal(self, painter, bar_rect, mode, state):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        top_h = bar_rect.height() * 0.60
        avatar_d = max(18, int(min(top_h, bar_rect.height() * 0.6)))
        avatar_rect = QRectF(bar_rect.x(), bar_rect.y() + (top_h - avatar_d) / 2, avatar_d, avatar_d)
        self._draw_preview_profile_avatar(painter, avatar_rect, state)

        text_color = QColor("#ffffff") if mode == "dark" else QColor("#111827")
        painter.setPen(text_color)
        name_font = self._box_effect_preview_font("main", max(11, int(avatar_d * 0.52)))
        name_font.setBold(True)
        family = self._profile_name_font_family() if hasattr(self, "_profile_name_font_family") else ""
        if family:
            name_font.setFamily(family)
        painter.setFont(name_font)
        name_x = avatar_rect.right() + max(7, int(avatar_d * 0.35))
        name_rect = QRectF(name_x, bar_rect.y(), bar_rect.right() - name_x, top_h)
        m = painter.fontMetrics()
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         m.elidedText(state["name"], Qt.TextElideMode.ElideRight, int(name_rect.width())))

        nook_enabled, nook_level_num, nook_fraction, nook_color = self._preview_nook_level_state()
        if nook_enabled:
            bar_y = bar_rect.y() + top_h + max(3, bar_rect.height() * 0.08)
            bar_h = max(4, int(bar_rect.height() * 0.14))
            lv_font = self._box_effect_preview_font("main", max(8, int(bar_h * 1.6)))
            lv_font.setBold(True)
            painter.setFont(lv_font)
            painter.setPen(QColor(text_color.red(), text_color.green(), text_color.blue(), 170))
            lv_text = f"{tr('level_short', 'Lv')} {nook_level_num}"
            lm = painter.fontMetrics()
            lv_w = lm.horizontalAdvance(lv_text) + 6
            painter.drawText(QRectF(bar_rect.x(), bar_y - bar_h, lv_w, bar_h * 3),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, lv_text)

            track_x = bar_rect.x() + lv_w + 4
            track_w = bar_rect.right() - track_x
            if track_w > 10:
                track_rect = QRectF(track_x, bar_y, track_w, bar_h)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(128, 128, 128, 90)))
                painter.drawRoundedRect(track_rect, bar_h / 2, bar_h / 2)
                fill_rect = QRectF(track_x, bar_y, track_w * nook_fraction, bar_h)
                painter.setBrush(QBrush(nook_color if nook_color else self._preview_profile_fill_color(mode)))
                painter.drawRoundedRect(fill_rect, bar_h / 2, bar_h / 2)
        painter.restore()

    def _draw_overview_style_profile_bar(self, painter, rect, mode, bar_rect=None):
        state = self._overview_style_profile_bar_state(mode)
        bar_rect = bar_rect or self._overview_style_profile_bar_rect(rect)
        ptype = self._preview_profile_type()
        if ptype == "ring":
            self._draw_overview_style_profile_ring(painter, bar_rect, mode, state)
            return
        if ptype == "minimal":
            self._draw_overview_style_profile_minimal(painter, bar_rect, mode, state)
            return
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
        name_font_family = self._profile_name_font_family() if hasattr(self, "_profile_name_font_family") else ""
        if name_font_family:
            font.setFamily(name_font_family)
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

