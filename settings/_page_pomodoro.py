# Pomodoro settings page. Follows the PageStudyToolsMixin structure (see
# _page_hashi_notes.py) but saves straight to mw.col.conf via pomodoro.py,
# not through self.current_config/config.write_config - Pomodoro settings and
# history sync through the collection, like Prep Station's plan data.
#
# Appearance is a single bordered panel (preview on top, every control below
# it) mirroring PageColorsMixin's "Box Color and Effect" section
# (_create_boxes_color_effect_group / _update_box_effect_controls in
# _page_colors.py and _infra.py): a light/dark preview toggle
# (_create_light_dark_mode_toggle, shared InfraMixin helper), Dynamic Mode
# (hides the dark-mode color column and pins everything to the "light" set
# when off, exactly like Box Effect's dynamic toggle), opacity/blur sliders
# (MainBackgroundEffectSlider), and pill-style color cards built from the
# same shared _create_main_bg_button/_create_color_selector_card/
# _style_main_background_color_button helpers used by the main background
# designer - reused as-is rather than reimplemented.
from ._common import *
from ._icon_picker import *
from ._widgets import *
from ._layout_base import *

from .. import pomodoro
from ..prep_station_ui import render_icon_pixmap

COLOR_ROLES = (
    ("shell", "pomodoro_color_shell", "Background"),
    ("accent", "pomodoro_color_accent", "Accent"),
    ("digits", "pomodoro_color_digits", "Timer Numbers"),
    ("icon", "pomodoro_color_icon", "Icon & Text"),
)


class _PomodoroClickableCard(QFrame):
    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self._on_click = on_click

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mousePressEvent(event)


class _PomodoroWallpaperBackdrop(QWidget):
    """Wallpaper painted behind the preview shell - shows the user's actual
    Main Background (image or flat color, from _main_background_state_for_box_preview)
    so the Opacity/Blur sliders show what they'll really affect instead of a
    made-up stand-in.

    Blur is baked into an offscreen pixmap (via QGraphicsBlurEffect on a
    QGraphicsScene, not a live effect on this widget)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._content_pixmap = None
        self._fallback_color = QColor("#00A982")
        self._blur_radius = 0.0
        self._cache = None

    def set_wallpaper(self, pixmap, fallback_color):
        color = QColor(fallback_color)
        changed = False
        if pixmap is not self._content_pixmap:
            self._content_pixmap = pixmap
            changed = True
        if color.isValid() and color != self._fallback_color:
            self._fallback_color = color
            changed = True
        if changed:
            self._cache = None
            self.update()

    def set_blur(self, radius):
        radius = max(0.0, float(radius))
        if abs(radius - self._blur_radius) > 0.01:
            self._blur_radius = radius
            self._cache = None
            self.update()

    def resizeEvent(self, event):
        self._cache = None
        super().resizeEvent(event)

    def _base_pixmap(self):
        size = self.size()
        pixmap = QPixmap(size)
        pixmap.fill(self._fallback_color)
        if self._content_pixmap is not None and not self._content_pixmap.isNull():
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawPixmap(0, 0, self._content_pixmap)
            painter.end()
        return pixmap

    def _rendered_pixmap(self):
        if self._cache is not None:
            return self._cache
        base = self._base_pixmap()
        if self._blur_radius <= 0:
            self._cache = base
            return base

        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(base)
        effect = QGraphicsBlurEffect()
        effect.setBlurRadius(self._blur_radius)
        item.setGraphicsEffect(effect)
        scene.addItem(item)

        result = QPixmap(base.size())
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        scene.render(painter, QRectF(result.rect()), QRectF(base.rect()))
        painter.end()
        self._cache = result
        return result

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, 18, 18)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, self._rendered_pixmap())


class PagePomodoroMixin:
    def create_pomodoro_page(self):
        page, layout = self._create_scrollable_page()

        self.pomodoro_settings = pomodoro.get_settings()
        self.pomodoro_color_inputs = {}
        self.pomodoro_color_swatch_refreshers = {}
        self.pomodoro_color_cards = {}

        intro = QLabel(tr(
            "pomodoro_page_intro",
            "A minimal focus timer. Open the floating island with Shift+P, the "
            "Reviewer header button, or the Study Tools menu.",
        ))
        intro.setObjectName("sectionDescription")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        open_section = SectionGroup("", self, border=False)
        open_btn = QPushButton(tr("pomodoro_open_button", "Open Pomodoro"))
        open_btn.setObjectName("toolsOpenButton")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setFixedHeight(40)
        try:
            self._decorate_button(open_btn, "pomodoro.svg", 16)
        except Exception:
            pass
        open_btn.clicked.connect(self._open_pomodoro)
        open_section.content_layout.addWidget(open_btn)
        layout.addWidget(open_section)

        layout.addWidget(self._create_pomodoro_durations_section())
        layout.addWidget(self._create_pomodoro_appearance_section())
        layout.addWidget(self._create_pomodoro_sound_section())

        layout.addStretch()
        try:
            self._style_tools_page(page)
        except Exception:
            pass
        return page

    # ─── Durations ──────────────────────────────────────────────────────────

    def _create_pomodoro_durations_section(self):
        section = SectionGroup(
            tr("pomodoro_durations", "Durations"),
            self,
            border=False,
            description=tr("pomodoro_durations_desc", "How long each phase of the cycle lasts."),
        )
        settings = self.pomodoro_settings

        self.pomodoro_focus_spin = QSpinBox()
        self.pomodoro_focus_spin.setRange(1, 180)
        self.pomodoro_focus_spin.setValue(int(settings.get("focus_minutes", 25)))
        section.content_layout.addWidget(self._create_tools_control_row(
            tr("pomodoro_focus", "Focus"),
            tr("pomodoro_focus_desc", "Length of a focus session, in minutes."),
            self.pomodoro_focus_spin,
        ))

        self.pomodoro_short_break_spin = QSpinBox()
        self.pomodoro_short_break_spin.setRange(1, 60)
        self.pomodoro_short_break_spin.setValue(int(settings.get("short_break_minutes", 5)))
        section.content_layout.addWidget(self._create_tools_control_row(
            tr("pomodoro_short_break", "Short Break"),
            tr("pomodoro_short_break_desc", "Length of a short break, in minutes."),
            self.pomodoro_short_break_spin,
        ))

        self.pomodoro_long_break_spin = QSpinBox()
        self.pomodoro_long_break_spin.setRange(1, 90)
        self.pomodoro_long_break_spin.setValue(int(settings.get("long_break_minutes", 15)))
        section.content_layout.addWidget(self._create_tools_control_row(
            tr("pomodoro_long_break", "Long Break"),
            tr("pomodoro_long_break_desc", "Length of a long break, in minutes."),
            self.pomodoro_long_break_spin,
        ))

        self.pomodoro_cycle_spin = QSpinBox()
        self.pomodoro_cycle_spin.setRange(1, 12)
        self.pomodoro_cycle_spin.setValue(int(settings.get("sessions_until_long_break", 4)))
        section.content_layout.addWidget(self._create_tools_control_row(
            tr("pomodoro_sessions_until_long", "Sessions until Long Break"),
            tr("pomodoro_sessions_until_long_desc", "Focus sessions completed before a long break is offered."),
            self.pomodoro_cycle_spin,
        ))

        return section

    # ─── Appearance ─────────────────────────────────────────────────────────

    def _create_pomodoro_appearance_section(self):
        section = SectionGroup(
            tr("pomodoro_appearance", "Appearance"),
            self,
            border=False,
            description=tr("pomodoro_appearance_desc", "Icon, font, and colors of the floating island."),
        )
        section.content_layout.addWidget(self._create_pomodoro_appearance_panel())
        return section

    def _create_pomodoro_icon_control(self):
        palette = self._settings_palette()
        card_bg = palette.get("--canvas-inset", "#ffffff")
        card_border = palette.get("--border", "#dcdde1")
        hover_bg = palette.get("--hover-bg", "#f2f2f2")
        text_color = palette.get("--fg", "#202124")
        subtle_color = palette.get("--fg-subtle", "#6f7177")

        card = _PomodoroClickableCard(self._open_pomodoro_icon_selector)
        card.setObjectName("pomodoroIconCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setMinimumHeight(60)
        card.setStyleSheet(f"""
            QFrame#pomodoroIconCard {{ background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 16px; }}
            QFrame#pomodoroIconCard:hover {{ background-color: {hover_bg}; }}
        """)

        row = QHBoxLayout(card)
        row.setContentsMargins(12, 8, 10, 8)
        row.setSpacing(12)

        preview = QLabel()
        preview.setFixedSize(34, 34)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setStyleSheet("background: transparent; border: none;")

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        name_label = QLabel(tr("pomodoro_icon", "Timer Icon"))
        name_label.setStyleSheet(f"background: transparent; border: none; font-weight: bold; color: {text_color}; font-size: 13px;")
        sub_label = QLabel(tr("click_to_change"))
        sub_label.setStyleSheet(f"background: transparent; border: none; color: {subtle_color}; font-size: 10px;")
        text_col.addWidget(name_label)
        text_col.addWidget(sub_label)

        row.addWidget(preview)
        row.addLayout(text_col, 1)

        self.pomodoro_icon_preview_label = preview
        self.selected_pomodoro_icon = self.pomodoro_settings.get("icon") or pomodoro.DEFAULT_ICON
        self._refresh_pomodoro_icon_preview()
        return card

    def _refresh_pomodoro_icon_preview(self):
        preview = getattr(self, "pomodoro_icon_preview_label", None)
        if preview is not None:
            color = self._settings_accent_color()
            preview.setPixmap(render_icon_pixmap(self.addon_path, self.selected_pomodoro_icon, color, 26))
        self._refresh_pomodoro_preview()

    def _open_pomodoro_icon_selector(self):
        picker = DeckIconPickerDialog(self.selected_pomodoro_icon, self.addon_path, self, allow_emoji=False)

        def on_selected(value):
            if not value:
                return
            self.selected_pomodoro_icon = value
            self._refresh_pomodoro_icon_preview()

        picker.iconSelected.connect(on_selected)
        picker.exec()

    def _create_pomodoro_font_control(self):
        settings = self.pomodoro_settings
        combo = QComboBox()
        combo.setMinimumWidth(200)
        all_fonts = get_all_fonts(self.addon_path)
        ordered_keys = ["system", "instrument_serif", "nunito", "montserrat", "space_mono", "silkscreen"]
        ordered_keys += sorted(key for key, info in all_fonts.items() if info.get("user"))
        current_key = settings.get("font_key", "system")
        for font_key in ordered_keys:
            info = all_fonts.get(font_key)
            if not info:
                continue
            label = tr("system") if font_key == "system" else info.get("name", font_key)
            combo.addItem(label, font_key)
        idx = combo.findData(current_key)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.pomodoro_font_combo = combo
        return self._create_tools_control_row(
            tr("pomodoro_font", "Timer Font"),
            tr("pomodoro_font_desc", "Font used for the countdown numbers."),
            combo,
        )

    # ─── Appearance panel (mirrors "Box Color and Effect") ─────────────────

    def _create_pomodoro_appearance_panel(self):
        palette = self._settings_palette()
        panel_bg = palette.get("--canvas-inset", "#ffffff")
        panel_border = palette.get("--border", "#dcdde1")

        frame = QFrame()
        frame.setObjectName("pomodoroAppearancePanel")
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        frame.setStyleSheet(f"""
            QFrame#pomodoroAppearancePanel {{
                background-color: {panel_bg};
                border: 1px solid {panel_border};
                border-radius: 16px;
            }}
        """)
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        outer.addWidget(self._create_pomodoro_preview_panel())

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        self.pomodoro_preview_mode = "dark" if theme_manager.night_mode else "light"
        toggle_widget, toggle = self._create_light_dark_mode_toggle(
            self.pomodoro_preview_mode, self._on_pomodoro_preview_mode_toggled,
        )
        self.pomodoro_preview_mode_toggle = toggle
        self.pomodoro_preview_mode_toggle_widget = toggle_widget
        header.addWidget(toggle_widget)
        header.addStretch()

        reset_btn = QPushButton(tr("restore_default", "Restore Default"))
        reset_btn.setObjectName("mainBackgroundResetButton")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._reset_pomodoro_appearance)
        header.addWidget(reset_btn)
        outer.addLayout(header)

        outer.addWidget(self._create_pomodoro_icon_control())
        outer.addWidget(self._create_pomodoro_font_control())
        outer.addWidget(self._create_pomodoro_dynamic_mode_control())
        outer.addWidget(self._create_pomodoro_opacity_control())
        outer.addWidget(self._create_pomodoro_blur_control())

        colors_title = QLabel(tr("pomodoro_colors", "Colors"))
        colors_title.setObjectName("sectionTitle")
        outer.addWidget(colors_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        for row, (key, tr_key, fallback_label) in enumerate(COLOR_ROLES):
            title_text = tr(tr_key, fallback_label)
            light_card = self._create_pomodoro_color_card("light", key, title_text)
            dark_card = self._create_pomodoro_color_card("dark", key, f"{title_text} {tr('dark_mode', 'Dark')}")
            grid.addWidget(light_card, row, 0)
            grid.addWidget(dark_card, row, 1)
        outer.addLayout(grid)

        self._sync_pomodoro_dynamic_mode_visuals()
        self._refresh_pomodoro_preview()
        return frame

    def _create_pomodoro_dynamic_mode_control(self):
        self.pomodoro_dynamic_mode_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.pomodoro_dynamic_mode_toggle.setChecked(bool(self.pomodoro_settings.get("dynamic_mode", True)))
        self.pomodoro_dynamic_mode_toggle.toggled.connect(self._on_pomodoro_dynamic_mode_toggled)
        return self._create_tools_toggle_row(
            tr("pomodoro_dynamic_mode", "Dynamic Mode"),
            tr(
                "pomodoro_dynamic_mode_desc",
                "Automatically switch between your Light and Dark colors with Anki's theme. "
                "Turn off to use one fixed color set everywhere.",
            ),
            self.pomodoro_dynamic_mode_toggle,
        )

    def _on_pomodoro_dynamic_mode_toggled(self, checked):
        if not checked and self.pomodoro_preview_mode_toggle.isChecked():
            # Forces the preview back to the "light" set, which is what will
            # actually render everywhere once Dynamic Mode is off.
            self.pomodoro_preview_mode_toggle.setChecked(False)
        self._sync_pomodoro_dynamic_mode_visuals()
        self._refresh_pomodoro_preview()

    def _sync_pomodoro_dynamic_mode_visuals(self):
        if not hasattr(self, "pomodoro_dynamic_mode_toggle"):
            return
        dynamic = self.pomodoro_dynamic_mode_toggle.isChecked()
        for (mode, _key), card in self.pomodoro_color_cards.items():
            if mode == "dark":
                card.setVisible(dynamic)
        toggle_widget = getattr(self, "pomodoro_preview_mode_toggle_widget", None)
        if toggle_widget is not None:
            toggle_widget.setEnabled(dynamic)
            toggle_widget.setToolTip(
                "" if dynamic else tr(
                    "pomodoro_dynamic_mode_tooltip",
                    "Enable Dynamic Mode to switch light/dark palettes.",
                )
            )

    def _create_pomodoro_opacity_control(self):
        slider, row_widget = self._create_pomodoro_effect_slider(
            int(self.pomodoro_settings.get("shell_opacity", 100)), suffix="%",
        )
        slider.valueChanged.connect(self._on_pomodoro_opacity_changed)
        self.pomodoro_opacity_slider = slider
        return self._create_tools_control_row(
            tr("pomodoro_opacity", "Opacity"),
            tr("pomodoro_opacity_desc", "How see-through the floating island's background is."),
            row_widget,
        )

    def _create_pomodoro_blur_control(self):
        slider, row_widget = self._create_pomodoro_effect_slider(
            int(self.pomodoro_settings.get("shell_blur", 0)), suffix="%",
        )
        slider.valueChanged.connect(self._on_pomodoro_blur_changed)
        self.pomodoro_blur_slider = slider
        return self._create_tools_control_row(
            tr("pomodoro_blur", "Blur"),
            tr("pomodoro_blur_desc", "Frosts the floating island's background, like glass."),
            row_widget,
        )

    def _create_pomodoro_effect_slider(self, value, suffix):
        palette = self._settings_palette()
        track = palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        border = palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")
        slider = MainBackgroundEffectSlider(self.accent_color, track, border)
        slider.setRange(0, 100)
        slider.setValue(max(0, min(100, value)))

        value_lbl = QLabel(f"{slider.value()}{suffix}")
        value_lbl.setObjectName("mainBackgroundValueLabel")
        value_lbl.setFixedWidth(44)
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        slider.valueChanged.connect(lambda v: value_lbl.setText(f"{v}{suffix}"))

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)
        row_layout.addWidget(slider, 1)
        row_layout.addWidget(value_lbl)
        return slider, row_widget

    def _on_pomodoro_opacity_changed(self, _value):
        self._refresh_pomodoro_preview()

    def _on_pomodoro_blur_changed(self, _value):
        self._refresh_pomodoro_preview()

    def _create_pomodoro_preview_panel(self):
        outer = QWidget()
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        container = QWidget()
        container.setFixedSize(240, 160)

        backdrop = _PomodoroWallpaperBackdrop(container)
        backdrop.setGeometry(0, 0, 240, 160)

        shell = QFrame(container)
        shell.setObjectName("pomodoroPreviewShell")
        shell.setGeometry(15, 15, 210, 130)
        shell.raise_()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(16, 12, 16, 14)
        shell_layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        self.pomodoro_preview_icon = QLabel()
        self.pomodoro_preview_phase = QLabel()
        top_row.addWidget(self.pomodoro_preview_icon)
        top_row.addWidget(self.pomodoro_preview_phase)
        top_row.addStretch()
        shell_layout.addLayout(top_row)

        self.pomodoro_preview_time = QLabel("24:59")
        self.pomodoro_preview_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shell_layout.addWidget(self.pomodoro_preview_time)

        self.pomodoro_preview_dots = QHBoxLayout()
        self.pomodoro_preview_dots.setSpacing(5)
        self.pomodoro_preview_dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shell_layout.addLayout(self.pomodoro_preview_dots)

        self.pomodoro_preview_backdrop = backdrop
        self.pomodoro_preview_shell = shell
        layout.addWidget(container, 0, Qt.AlignmentFlag.AlignCenter)
        return outer

    def _on_pomodoro_preview_mode_toggled(self, mode):
        self.pomodoro_preview_mode = "dark" if mode == "dark" else "light"
        self._refresh_pomodoro_preview()

    def _pomodoro_resolved_color(self, mode, key, fallback):
        line_edit = self.pomodoro_color_inputs.get((mode, key))
        value = line_edit.text() if line_edit else ""
        return value or fallback

    def _refresh_pomodoro_preview(self):
        shell = getattr(self, "pomodoro_preview_shell", None)
        if shell is None:
            return
        dynamic = not hasattr(self, "pomodoro_dynamic_mode_toggle") or self.pomodoro_dynamic_mode_toggle.isChecked()
        mode = self.pomodoro_preview_mode if dynamic else "light"
        is_dark = mode == "dark"
        base = pomodoro.base_chrome_palette(is_dark)

        shell_color_hex = self._pomodoro_resolved_color(mode, "shell", base["shell"])
        accent = self._pomodoro_resolved_color(mode, "accent", base["accent"])
        digits = self._pomodoro_resolved_color(mode, "digits", base["fg"])
        icon_color = self._pomodoro_resolved_color(mode, "icon", base["fg2"])

        opacity = self.pomodoro_opacity_slider.value() if hasattr(self, "pomodoro_opacity_slider") else 100
        blur = self.pomodoro_blur_slider.value() if hasattr(self, "pomodoro_blur_slider") else 0
        shell_color = pomodoro.shell_alpha_color(shell_color_hex, opacity)

        shell.setStyleSheet(f"""
            QFrame#pomodoroPreviewShell {{
                background-color: {shell_color};
                border: 1px solid {base['border']};
                border-radius: 18px;
            }}
        """)

        backdrop = getattr(self, "pomodoro_preview_backdrop", None)
        if backdrop is not None:
            bg_state = self._main_background_state_for_box_preview(mode)
            image_path = bg_state.get("image_path", "")
            cover_pixmap = None
            if image_path and os.path.exists(image_path):
                cover_pixmap = self._background_cover_image_with_effect(
                    image_path, backdrop.width() or 240, backdrop.height() or 160, 0,
                )
            backdrop.set_wallpaper(cover_pixmap, bg_state.get("color", accent))
            backdrop.set_blur(blur * 0.2)
        self.pomodoro_preview_phase.setStyleSheet(
            f"color: {icon_color}; font-size: 10px; font-weight: 800; letter-spacing: 1px; background: transparent;"
        )
        self.pomodoro_preview_phase.setText(tr("pomodoro_focus", "Focus").upper())
        self.pomodoro_preview_time.setStyleSheet(
            f"color: {digits}; font-size: 26px; font-weight: 800; background: transparent;"
        )

        icon_value = getattr(self, "selected_pomodoro_icon", None) or pomodoro.DEFAULT_ICON
        self.pomodoro_preview_icon.setPixmap(render_icon_pixmap(self.addon_path, icon_value, accent, 14))

        while self.pomodoro_preview_dots.count():
            item = self.pomodoro_preview_dots.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        total, filled = 4, 2
        for i in range(total):
            label = QLabel()
            color = accent if i < filled else icon_color
            label.setPixmap(render_icon_pixmap(self.addon_path, icon_value, color, 11))
            if i >= filled:
                effect = QGraphicsOpacityEffect(label)
                effect.setOpacity(0.35)
                label.setGraphicsEffect(effect)
            self.pomodoro_preview_dots.addWidget(label)

    def _create_pomodoro_color_card(self, mode, key, title_text):
        settings = self.pomodoro_settings
        stored = (settings.get("colors", {}).get(mode, {}) or {}).get(key, "")

        line_edit = QLineEdit(stored)
        line_edit.setVisible(False)
        self.pomodoro_color_inputs[(mode, key)] = line_edit

        label_btn = self._create_main_bg_button(title_text)
        value_btn = self._create_main_bg_button("")
        value_btn.setObjectName("mainBackgroundColorButton")

        def refresh():
            default_hex = self._pomodoro_default_color(mode, key)
            self._style_main_background_color_button(value_btn, line_edit.text() or default_hex)

        def choose():
            default_hex = self._pomodoro_default_color(mode, key)
            current = line_edit.text() or default_hex
            chosen, ok = OnigiriColorDialog.getColor(current, self, anchor=value_btn)
            if ok and chosen and QColor(chosen).isValid():
                line_edit.setText(chosen)
                refresh()
                if mode == self.pomodoro_preview_mode:
                    self._refresh_pomodoro_preview()

        label_btn.clicked.connect(choose)
        value_btn.clicked.connect(choose)
        refresh()
        self.pomodoro_color_swatch_refreshers[(mode, key)] = refresh
        card = self._create_color_selector_card(label_btn, value_btn, compact=True)
        self.pomodoro_color_cards[(mode, key)] = card
        return card

    def _pomodoro_default_color(self, mode, key):
        base = pomodoro.base_chrome_palette(mode == "dark")
        return {
            "shell": base["shell"],
            "accent": base["accent"],
            "digits": base["fg"],
            "icon": base["fg2"],
        }.get(key, base["fg"])

    def _reset_pomodoro_appearance(self):
        for key, line_edit in self.pomodoro_color_inputs.items():
            line_edit.setText("")
            self.pomodoro_color_swatch_refreshers[key]()
        self.selected_pomodoro_icon = pomodoro.DEFAULT_ICON
        idx = self.pomodoro_font_combo.findData("system")
        self.pomodoro_font_combo.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(self, "pomodoro_dynamic_mode_toggle"):
            self.pomodoro_dynamic_mode_toggle.setChecked(True)
        if hasattr(self, "pomodoro_opacity_slider"):
            self.pomodoro_opacity_slider.setValue(100)
        if hasattr(self, "pomodoro_blur_slider"):
            self.pomodoro_blur_slider.setValue(0)
        self._sync_pomodoro_dynamic_mode_visuals()
        self._refresh_pomodoro_icon_preview()
        show_settings_toast(self, tr("pomodoro_appearance_reset_toast", "Pomodoro appearance reset to default"))

    # ─── Sound ──────────────────────────────────────────────────────────────

    def _create_pomodoro_sound_section(self):
        section = SectionGroup(
            tr("pomodoro_sound", "Sound"),
            self,
            border=False,
            description=tr("pomodoro_sound_desc", "Plays when a focus session completes."),
        )
        settings = self.pomodoro_settings

        self.pomodoro_sound_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.pomodoro_sound_toggle.setChecked(bool(settings.get("sound_enabled", True)))
        section.content_layout.addWidget(self._create_tools_toggle_row(
            tr("pomodoro_sound_enabled", "Play Sound"),
            "",
            self.pomodoro_sound_toggle,
        ))

        self.selected_pomodoro_sound_file = settings.get("sound_file", "") or ""

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)

        choose_btn = self._create_main_bg_button(tr("pomodoro_choose_sound", "Choose Sound File…"))
        choose_btn.clicked.connect(self._choose_pomodoro_sound_file)

        test_btn = self._create_main_bg_button(tr("pomodoro_test_sound", "Test Sound"))
        test_btn.clicked.connect(self._test_pomodoro_sound)

        reset_btn = self._create_main_bg_button(tr("pomodoro_reset_sound", "Reset to Default Chime"))
        reset_btn.clicked.connect(self._reset_pomodoro_sound)

        buttons_row.addWidget(choose_btn)
        buttons_row.addWidget(test_btn)
        buttons_row.addWidget(reset_btn)
        buttons_row.addStretch()

        row_widget = QWidget()
        row_widget.setLayout(buttons_row)
        section.content_layout.addWidget(row_widget)

        return section

    def _choose_pomodoro_sound_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("pomodoro_choose_sound", "Choose Sound File…"),
            "",
            "Audio Files (*.mp3 *.wav *.ogg *.m4a *.flac)",
        )
        if not path:
            return
        try:
            filename = pomodoro.import_sound_file(path)
            self.selected_pomodoro_sound_file = filename
            pomodoro.play_test_sound(filename)
        except Exception as e:
            print(f"Pomodoro: sound import error: {e}")

    def _test_pomodoro_sound(self):
        pomodoro.play_test_sound(self.selected_pomodoro_sound_file or None)

    def _reset_pomodoro_sound(self):
        self.selected_pomodoro_sound_file = ""
        show_settings_toast(self, tr("pomodoro_sound_reset_toast", "Sound reset to default chime"))

    # ─── Save / Open ────────────────────────────────────────────────────────

    def _save_pomodoro_settings(self):
        if not hasattr(self, "pomodoro_focus_spin"):
            return
        settings = pomodoro.get_settings()
        settings["focus_minutes"] = self.pomodoro_focus_spin.value()
        settings["short_break_minutes"] = self.pomodoro_short_break_spin.value()
        settings["long_break_minutes"] = self.pomodoro_long_break_spin.value()
        settings["sessions_until_long_break"] = self.pomodoro_cycle_spin.value()
        settings["icon"] = self.selected_pomodoro_icon or pomodoro.DEFAULT_ICON
        settings["font_key"] = self.pomodoro_font_combo.currentData() or "system"
        settings["sound_enabled"] = self.pomodoro_sound_toggle.isChecked()
        settings["sound_file"] = self.selected_pomodoro_sound_file or ""
        settings["dynamic_mode"] = self.pomodoro_dynamic_mode_toggle.isChecked()
        settings["shell_opacity"] = self.pomodoro_opacity_slider.value()
        settings["shell_blur"] = self.pomodoro_blur_slider.value()

        colors = {"light": {}, "dark": {}}
        for (mode, key), line_edit in self.pomodoro_color_inputs.items():
            value = line_edit.text().strip()
            colors[mode][key] = value if value and QColor(value).isValid() else ""
        settings["colors"] = colors

        pomodoro.save_settings(settings)
        pomodoro.get_timer().settings = settings

    def _open_pomodoro(self):
        self._save_pomodoro_settings()
        pomodoro.toggle_widget(self)
