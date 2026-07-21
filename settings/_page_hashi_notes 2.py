# Hashi Notes settings page. Follows the PageStudyToolsMixin structure and
# reuses the shared study-tools UI helpers (segmented controls, section groups, row builders).
from ._common import *
from ._widgets import *
from ._layout_base import *


class PageHashiNotesMixin:
    def create_hashi_notes_page(self):
        page, layout = self._create_scrollable_page()

        prefs = self.current_config.setdefault(
            "hashi_notes",
            copy.deepcopy(DEFAULTS.get("hashi_notes", {})),
        )
        for key, value in DEFAULTS.get("hashi_notes", {}).items():
            prefs.setdefault(key, copy.deepcopy(value))

        intro = QLabel(tr(
            "hashi_settings_intro",
            "Hashi Notes are quick, temporary study notes. Take one from the Reviewer "
            "or the Onigiri menu; each note auto-deletes after its retention window.",
        ))
        intro.setObjectName("sectionDescription")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Open button
        open_section = SectionGroup("", self, border=False)
        open_btn = QPushButton(tr("hashi_open_button", "Open Hashi Notes"))
        open_btn.setObjectName("toolsOpenButton")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setFixedHeight(40)
        try:
            self._decorate_button(open_btn, "hashi_notes.svg", 16)
        except Exception:
            pass
        open_btn.clicked.connect(self._open_hashi_notes)
        open_section.content_layout.addWidget(open_btn)
        layout.addWidget(open_section)

        options_section = SectionGroup(
            tr("hashi_options", "Options"),
            self,
            border=False,
            description=tr("hashi_options_desc", "Defaults applied to new notes and the gallery."),
        )
        opt_layout = options_section.content_layout

        # Retention default
        self.hashi_retention_group = QButtonGroup(self)
        self.hashi_retention_group.setExclusive(True)
        retention_value = str(prefs.get("retention_default", 30))
        retention_segment = self._create_tools_segmented_control(
            [("7", tr("hashi_7_days", "7 days")), ("30", tr("hashi_30_days", "30 days")), ("0", tr("hashi_never", "Never"))],
            self.hashi_retention_group,
            retention_value,
            "hashi_retention",
            min_button_width=120,
        )
        opt_layout.addWidget(self._create_tools_control_row(
            tr("hashi_default_retention", "Default retention"),
            tr("hashi_default_retention_desc", "How long new notes are kept before they move to trash and are purged."),
            retention_segment,
        ))

        # Default sort
        self.hashi_sort_group = QButtonGroup(self)
        self.hashi_sort_group.setExclusive(True)
        sort_value = str(prefs.get("default_sort", "age"))
        sort_segment = self._create_tools_segmented_control(
            [("age", tr("hashi_sort_age", "Age")), ("tags", tr("hashi_sort_tags", "Tags")), ("priority", tr("hashi_sort_priority", "Priority")), ("title", tr("hashi_sort_title", "Title"))],
            self.hashi_sort_group,
            sort_value,
            "hashi_sort",
            min_button_width=96,
        )
        opt_layout.addWidget(self._create_tools_control_row(
            tr("hashi_default_sort", "Default sort"),
            tr("hashi_default_sort_desc", "Initial ordering of notes in the gallery."),
            sort_segment,
        ))

        # Show in Reviewer header
        self.hashi_show_in_header_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.hashi_show_in_header_toggle.setChecked(prefs.get("show_in_reviewer_header", True))
        opt_layout.addWidget(self._create_tools_toggle_row(
            tr("hashi_show_in_header", "Show in Reviewer header"),
            tr("hashi_show_in_header_desc", "Display the Hashi Notes button in the Reviewer's top bar."),
            self.hashi_show_in_header_toggle,
        ))
        layout.addWidget(options_section)

        widget_section = SectionGroup("", self, border=False)
        widget_section.add_widget(self._create_hashi_widget_designer())
        layout.addWidget(widget_section)

        layout.addStretch()
        try:
            self._style_tools_page(page)
        except Exception:
            pass
        return page

    # ------------------------------------------------------------------
    # Dashboard widget designer
    # ------------------------------------------------------------------
    # Same contract as the Stats Widgets / Deck Stats designers: a live preview,
    # a light/dark toggle, an optional sync to Widget Color and Effect, and a color
    # grid. Writes current_config["hashi_widget_style"], which
    # patcher.generate_dynamic_css turns into the --hashiw-* CSS variables.

    HASHI_WIDGET_COLOR_KEYS = (
        ("box_bg", "deck_stats_box_color", "Box Color"),
        ("box_border", "deck_stats_border_color", "Border Color"),
        ("card_bg", "hashi_widget_card_color", "Note Card Color"),
        ("accent", "hashi_widget_accent_color", "Accent"),
        ("title", "hashi_widget_title_color", "Title Color"),
        ("excerpt", "hashi_widget_excerpt_color", "Excerpt Color"),
    )

    def _hashi_widget_defaults(self):
        return DEFAULTS.get("hashi_widget_style", {})

    def _hashi_widget_default_color(self, mode, key):
        return self._hashi_widget_defaults().get("colors", {}).get(mode, {}).get(key, "#808080")

    def _hashi_widget_preview_mode(self):
        return getattr(self, "hashi_widget_preview_mode", "dark" if theme_manager.night_mode else "light")

    def _hashi_widget_dynamic(self):
        if self._hashi_widget_synced() and hasattr(self, "box_effect_dynamic_toggle"):
            return self.box_effect_dynamic_toggle.isChecked()
        return not hasattr(self, "hashi_widget_dynamic_toggle") or self.hashi_widget_dynamic_toggle.isChecked()

    def _hashi_widget_synced(self):
        return hasattr(self, "hashi_widget_sync_toggle") and self.hashi_widget_sync_toggle.isChecked()

    def _hashi_widget_color_mode(self):
        if not self._hashi_widget_dynamic():
            return "light"
        return self._hashi_widget_preview_mode()

    def _hashi_widget_color(self, key, mode=None):
        mode = mode or self._hashi_widget_color_mode()
        value = getattr(self, "hashi_widget_colors", {}).get(mode, {}).get(key)
        if value and QColor(value).isValid():
            return value
        return self._hashi_widget_default_color(mode, key)

    def _hashi_widget_mode(self):
        group = getattr(self, "hashi_widget_mode_group", None)
        checked = group.checkedButton() if group is not None else None
        value = checked.property("hashi_widget_mode") if checked is not None else None
        return value if value in ("gallery", "single") else "gallery"

    def _hashi_widget_effect_values(self):
        if self._hashi_widget_synced() and hasattr(self, "box_effect_blur_slider"):
            return {
                "blur": self.box_effect_blur_slider.value(),
                "opacity": self.box_effect_opacity_slider.value(),
                "radius": self.box_effect_radius_slider.value(),
                "stroke": self.box_effect_stroke_slider.value(),
            }
        return {
            "blur": self.hashi_widget_blur_slider.value(),
            "opacity": self.hashi_widget_opacity_slider.value(),
            "radius": self.hashi_widget_radius_slider.value(),
            "stroke": self.hashi_widget_stroke_slider.value(),
        }

    def _hashi_widget_box_controls_ready(self):
        """Whether Widget Color and Effect's own widgets have been built yet.

        Unlike the Stats Widgets / Deck Stats designers, this page can be opened
        without ever visiting Main menu, where that group lives — so the synced
        colours have to fall back to the saved config instead of touching
        controls that do not exist.
        """
        return hasattr(self, "box_effect_dynamic_toggle")

    def _hashi_widget_saved_theme_color(self, mode, key, fallback_key):
        colors = self.current_config.get("colors", {}).get(mode, {})
        return colors.get(fallback_key) or DEFAULTS["colors"][mode][fallback_key]

    def _hashi_widget_box_color(self, mode):
        if self._hashi_widget_synced():
            if self._hashi_widget_box_controls_ready():
                return self._box_effect_color(mode)
            return self._hashi_widget_saved_theme_color(mode, "box_bg", "--canvas-inset")
        return self._hashi_widget_color("box_bg", mode if self._hashi_widget_dynamic() else "light")

    def _hashi_widget_box_border_color(self, mode):
        if self._hashi_widget_synced():
            if self._hashi_widget_box_controls_ready():
                return self._box_effect_border_color(mode)
            return self._hashi_widget_saved_theme_color(mode, "box_border", "--border")
        return self._hashi_widget_color("box_border", mode if self._hashi_widget_dynamic() else "light")

    def _hashi_widget_notes(self):
        """Real notes, so the preview and the "Pinned note" list stay honest."""
        try:
            from .. import hashi_notes

            notes = hashi_notes.load_notes()
            notes.sort(
                key=lambda n: str(n.get("updated_at") or n.get("created_at") or ""),
                reverse=True,
            )
            return notes
        except Exception:
            return []

    def _create_hashi_widget_designer(self):
        designer = QFrame()
        designer.setObjectName("mainBackgroundDesigner")
        outer = QVBoxLayout(designer)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        saved = self.current_config.get("hashi_widget_style", {})
        if not isinstance(saved, dict):
            saved = {}
        defaults = self._hashi_widget_defaults()

        self.hashi_widget_colors = {}
        for mode in ("light", "dark"):
            saved_colors = saved.get("colors", {})
            saved_mode = saved_colors.get(mode, {}) if isinstance(saved_colors, dict) else {}
            self.hashi_widget_colors[mode] = {
                key: (saved_mode.get(key) or self._hashi_widget_default_color(mode, key))
                for key, _lk, _fb in self.HASHI_WIDGET_COLOR_KEYS
            }

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel(tr("hashi_widget_section", "Dashboard Widget"))
        title_label.setObjectName("sectionTitle")
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.hashi_widget_preview_mode = "dark" if theme_manager.night_mode else "light"
        self.hashi_widget_preview_mode_widget, self.hashi_widget_preview_mode_toggle = self._create_light_dark_mode_toggle(
            self.hashi_widget_preview_mode,
            self._on_hashi_widget_preview_mode_toggled,
        )
        header_layout.addWidget(self.hashi_widget_preview_mode_widget)

        self.hashi_widget_reset_button = QPushButton(tr("restore_default"))
        self.hashi_widget_reset_button.setObjectName("mainBackgroundResetButton")
        self.hashi_widget_reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hashi_widget_reset_button.clicked.connect(self._reset_hashi_widget_to_default)
        header_layout.addWidget(self.hashi_widget_reset_button)
        outer.addLayout(header_layout)

        self.hashi_widget_preview = BackgroundPreviewLabel(aspect_ratio=2.6, minimum_preview_height=210)
        self.hashi_widget_preview.setObjectName("mainBackgroundPreview")
        self.hashi_widget_preview.setMinimumHeight(
            self.hashi_widget_preview.heightForWidth(self._preview_expected_width())
        )
        self.hashi_widget_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hashi_widget_preview.setProperty("hashi_widget_preview", True)
        self.hashi_widget_preview.installEventFilter(self)
        outer.addWidget(self.hashi_widget_preview)

        preview_divider = QFrame()
        preview_divider.setFrameShape(QFrame.Shape.HLine)
        preview_divider.setFrameShadow(QFrame.Shadow.Sunken)
        outer.addWidget(preview_divider)

        slider_palette = self._settings_palette()
        slider_track = slider_palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = slider_palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")

        def _slider_row(attr, minimum, maximum, value, suffix):
            slider = MainBackgroundEffectSlider(self.accent_color, slider_track, slider_border)
            slider.setRange(minimum, maximum)
            slider.setValue(max(minimum, min(maximum, int(value))))
            label = QLabel(f"{slider.value()}{suffix}")
            label.setObjectName("mainBackgroundValueLabel")
            label.setFixedWidth(48)
            holder = QWidget()
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setSpacing(10)
            holder_layout.addWidget(slider, 1)
            holder_layout.addWidget(label)
            setattr(self, f"hashi_widget_{attr}_slider", slider)
            setattr(self, f"hashi_widget_{attr}_value_label", label)
            slider.valueChanged.connect(self._on_hashi_widget_changed)
            return holder

        blur_value = _slider_row("blur", 0, 100, saved.get("blur", defaults.get("blur", 0)) or 0, "%")
        opacity_value = _slider_row("opacity", 0, 100, saved.get("opacity", defaults.get("opacity", 100)) or 100, "%")
        radius_value = _slider_row("radius", 0, 60, saved.get("radius", defaults.get("radius", 20)) or 20, "px")
        stroke_raw = saved.get("stroke", defaults.get("stroke", 1))
        stroke_value = _slider_row("stroke", 0, 10, stroke_raw if stroke_raw is not None else 1, "px")
        limit_value = _slider_row("limit", 1, 8, saved.get("limit", defaults.get("limit", 4)) or 4, "")

        saved_mode = saved.get("mode", defaults.get("mode", "gallery"))
        if saved_mode not in ("gallery", "single"):
            saved_mode = "gallery"
        self.hashi_widget_mode_group = QButtonGroup(self)
        self.hashi_widget_mode_group.setExclusive(True)
        mode_container = self._create_organize_segmented_control(
            [
                ("gallery", tr("hashi_widget_mode_gallery", "Gallery")),
                ("single", tr("hashi_widget_mode_single", "Single note")),
            ],
            self.hashi_widget_mode_group,
            saved_mode,
            "hashi_widget_mode",
            fill_width=True,
            segment_height=28,
            min_button_width=88,
        )
        self.hashi_widget_mode_group.buttonClicked.connect(self._on_hashi_widget_changed)

        # Which note "Single note" pins. Opens a gallery of note miniatures
        # (HashiNotePickerDialog); an id whose note is gone simply falls back to
        # the newest note, both here and in the widget itself.
        self.hashi_widget_note_id = str(saved.get("note_id") or "")
        self.hashi_widget_note_button = self._create_main_bg_button("")
        self.hashi_widget_note_button.clicked.connect(self._open_hashi_note_picker)
        self._refresh_hashi_widget_note_button()

        def _toggle(attr, default_value):
            toggle = AnimatedToggleButton(accent_color=self.accent_color)
            toggle.setChecked(bool(saved.get(attr, defaults.get(attr, default_value))))
            toggle.toggled.connect(self._on_hashi_widget_changed)
            setattr(self, f"hashi_widget_{attr}_toggle", toggle)
            return toggle

        self.hashi_widget_sync_toggle = _toggle("sync_box_effect", True)
        self.hashi_widget_dynamic_toggle = _toggle("dynamic", True)
        show_excerpt_toggle = _toggle("show_excerpt", True)
        show_icon_toggle = _toggle("show_icon", True)
        show_date_toggle = _toggle("show_date", True)

        settings_column = QWidget()
        settings_column.setMinimumWidth(0)
        settings_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        settings_layout = QVBoxLayout(settings_column)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)
        settings_layout.addWidget(
            self._create_main_bg_value_row(tr("hashi_widget_mode", "Layout"), mode_container)
        )
        self.hashi_widget_note_row = self._create_main_bg_value_row(
            tr("hashi_widget_pinned_note", "Pinned note"), self.hashi_widget_note_button
        )
        settings_layout.addWidget(self.hashi_widget_note_row)
        self.hashi_widget_limit_row = self._create_main_bg_value_row(
            tr("hashi_widget_limit", "Notes shown"), limit_value
        )
        settings_layout.addWidget(self.hashi_widget_limit_row)
        settings_layout.addWidget(
            self._create_main_bg_toggle_row(
                tr("sync_with_box_color_effect", "Sync with Widget Color and Effect"),
                self.hashi_widget_sync_toggle,
            )
        )
        self.hashi_widget_dynamic_row = self._create_main_bg_toggle_row(
            tr("dynamic_mode", "Dynamic mode"), self.hashi_widget_dynamic_toggle
        )
        settings_layout.addWidget(self.hashi_widget_dynamic_row)
        settings_layout.addWidget(
            self._create_main_bg_toggle_row(tr("hashi_widget_show_icon", "Show note icons"), show_icon_toggle)
        )
        settings_layout.addWidget(
            self._create_main_bg_toggle_row(tr("hashi_widget_show_excerpt", "Show excerpt"), show_excerpt_toggle)
        )
        settings_layout.addWidget(
            self._create_main_bg_toggle_row(tr("hashi_widget_show_date", "Show date"), show_date_toggle)
        )
        self.hashi_widget_blur_row = self._create_main_bg_value_row(tr("blur", "Blur"), blur_value)
        self.hashi_widget_opacity_row = self._create_main_bg_value_row(tr("opacity", "Opacity"), opacity_value)
        self.hashi_widget_radius_row = self._create_main_bg_value_row(tr("radius", "Radius"), radius_value)
        self.hashi_widget_stroke_row = self._create_main_bg_value_row(tr("stroke", "Stroke"), stroke_value)
        for row in (
            self.hashi_widget_blur_row,
            self.hashi_widget_opacity_row,
            self.hashi_widget_radius_row,
            self.hashi_widget_stroke_row,
        ):
            settings_layout.addWidget(row)
        settings_layout.addStretch(1)

        colors_column = QWidget()
        colors_column.setMinimumWidth(0)
        colors_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        colors_layout = QGridLayout(colors_column)
        colors_layout.setContentsMargins(0, 0, 0, 0)
        colors_layout.setHorizontalSpacing(10)
        colors_layout.setVerticalSpacing(8)
        colors_layout.setColumnStretch(0, 1)
        colors_layout.setColumnStretch(1, 1)

        self.hashi_widget_color_buttons = {}
        self.hashi_widget_box_cards = []
        for index, (key, label_key, fallback) in enumerate(self.HASHI_WIDGET_COLOR_KEYS):
            card = self._create_hashi_widget_color_card(key, tr(label_key, fallback))
            colors_layout.addWidget(card, index // 2, index % 2)
            if key in ("box_bg", "box_border"):
                self.hashi_widget_box_cards.append(card)

        bottom_columns = ResponsivePairWidget(
            settings_column, colors_column, spacing=18, breakpoint=760,
            left_stretch=1, right_stretch=1
        )
        outer.addWidget(bottom_columns)

        self._update_hashi_widget_controls()
        return designer

    def _create_hashi_widget_color_card(self, key, label_text):
        label_button = self._create_main_bg_button(label_text)
        value_button = self._create_main_bg_button("")
        value_button.setObjectName("mainBackgroundColorButton")
        label_button.clicked.connect(lambda _=False, k=key, b=label_button: self._choose_hashi_widget_color(k, b))
        value_button.clicked.connect(lambda _=False, k=key, b=value_button: self._choose_hashi_widget_color(k, b))
        self.hashi_widget_color_buttons[key] = value_button
        self._style_main_background_color_button(value_button, self._hashi_widget_color(key))
        return self._create_color_selector_card(label_button, value_button, compact=True)

    def _choose_hashi_widget_color(self, key, anchor=None):
        mode = self._hashi_widget_color_mode()
        chosen, ok = OnigiriColorDialog.getColor(self._hashi_widget_color(key, mode), self, anchor=anchor)
        if ok and QColor(chosen).isValid():
            self.hashi_widget_colors.setdefault(mode, {})[key] = chosen
            self._update_hashi_widget_controls()

    def _on_hashi_widget_preview_mode_toggled(self, mode):
        self.hashi_widget_preview_mode = "dark" if mode == "dark" else "light"
        self._update_hashi_widget_controls()

    def _on_hashi_widget_changed(self, *args):
        self._update_hashi_widget_controls()

    def _update_hashi_widget_controls(self):
        if not hasattr(self, "hashi_widget_preview"):
            return
        synced = self._hashi_widget_synced()
        dynamic = self._hashi_widget_dynamic()
        single = self._hashi_widget_mode() == "single"

        for attr, suffix in (("blur", "%"), ("opacity", "%"), ("radius", "px"), ("stroke", "px"), ("limit", "")):
            slider = getattr(self, f"hashi_widget_{attr}_slider", None)
            label = getattr(self, f"hashi_widget_{attr}_value_label", None)
            if slider is not None and label is not None:
                label.setText(f"{slider.value()}{suffix}")

        locked_rows = (
            self.hashi_widget_dynamic_row,
            self.hashi_widget_blur_row,
            self.hashi_widget_opacity_row,
            self.hashi_widget_radius_row,
            self.hashi_widget_stroke_row,
        )
        self._set_dynamic_mode_widgets_dimmed(locked_rows, synced)
        self._set_dynamic_mode_widgets_dimmed(tuple(getattr(self, "hashi_widget_box_cards", ())), synced)
        # The pinned-note picker only matters in Single mode; the count slider
        # only in Gallery. Dim rather than hide so the panel keeps its height.
        self._set_dynamic_mode_widgets_dimmed((self.hashi_widget_note_row,), not single)
        self._set_dynamic_mode_widgets_dimmed((self.hashi_widget_limit_row,), single)

        if hasattr(self, "hashi_widget_preview_mode_widget"):
            self.hashi_widget_preview_mode_widget.setEnabled(dynamic)
            self.hashi_widget_preview_mode_widget.setToolTip(
                "" if dynamic else tr("enable_dynamic_mode_hint", "Enable Dynamic mode to switch light/dark palettes.")
            )

        for key, button in getattr(self, "hashi_widget_color_buttons", {}).items():
            if key == "box_bg" and synced:
                color = self._hashi_widget_box_color(self._hashi_widget_preview_mode())
            elif key == "box_border" and synced:
                color = self._hashi_widget_box_border_color(self._hashi_widget_preview_mode())
            else:
                color = self._hashi_widget_color(key)
            self._style_main_background_color_button(button, color)

        self._update_hashi_widget_preview()

    def _reset_hashi_widget_to_default(self):
        defaults = self._hashi_widget_defaults()
        self.hashi_widget_colors = {
            mode: dict(defaults.get("colors", {}).get(mode, {}))
            for mode in ("light", "dark")
        }
        for button in self.hashi_widget_mode_group.buttons():
            button.setChecked(button.property("hashi_widget_mode") == defaults.get("mode", "gallery"))
        self.hashi_widget_note_id = ""
        self._refresh_hashi_widget_note_button()
        for attr, default_value in (
            ("sync_box_effect", True), ("dynamic", True),
            ("show_excerpt", True), ("show_icon", True), ("show_date", True),
        ):
            toggle = getattr(self, f"hashi_widget_{attr}_toggle", None)
            if toggle is not None:
                toggle.setChecked(bool(defaults.get(attr, default_value)))
        self.hashi_widget_blur_slider.setValue(int(defaults.get("blur", 0) or 0))
        self.hashi_widget_opacity_slider.setValue(int(defaults.get("opacity", 100) or 100))
        self.hashi_widget_radius_slider.setValue(int(defaults.get("radius", 20) or 20))
        stroke = defaults.get("stroke", 1)
        self.hashi_widget_stroke_slider.setValue(int(stroke if stroke is not None else 1))
        self.hashi_widget_limit_slider.setValue(int(defaults.get("limit", 4) or 4))
        self._update_hashi_widget_controls()
        show_settings_toast(self, tr("hashi_widget_reset_toast", "Hashi Notes widget reset to default"))

    # --- Preview painting -------------------------------------------------

    # The note colours offered in the editor's palette (hashi_notes.html
    # NOTE_COLORS); the preview borrows four of them so Gallery mode always
    # demonstrates several distinctly coloured notes, even on a fresh profile.
    HASHI_PREVIEW_SAMPLE_COLORS = ("#eab308", "#22c55e", "#3b82f6", "#ec4899")

    def _hashi_widget_preview_notes(self, count):
        """`count` notes to draw: the real ones first, then coloured samples.

        Padding with samples keeps the preview useful when the profile has one
        note (or none) - otherwise Gallery mode drew the same card four times
        and looked identical to Single mode."""
        notes = list(self._hashi_widget_notes())[:count]
        used = {str(n.get("color") or "").lower() for n in notes}
        sample_body = tr("hashi_widget_sample_body", "Your notes will show up here.")
        spare = [c for c in self.HASHI_PREVIEW_SAMPLE_COLORS if c not in used]
        index = 0
        while len(notes) < count:
            color = spare[index % len(spare)] if spare else ""
            index += 1
            notes.append(
                {
                    "title": tr("hashi_untitled", "Untitled"),
                    "body_md": sample_body,
                    "color": color,
                    "is_sample": True,
                }
            )
        return notes

    def _refresh_hashi_widget_note_button(self):
        """Button label mirrors the pinned note's title (or the auto option)."""
        button = getattr(self, "hashi_widget_note_button", None)
        if button is None:
            return
        note_id = str(getattr(self, "hashi_widget_note_id", "") or "")
        label = tr("hashi_widget_newest_note", "Most recent note")
        if note_id:
            for note in self._hashi_widget_notes():
                if note.get("id") == note_id:
                    label = note.get("title") or tr("hashi_untitled", "Untitled")
                    break
            else:
                # Pinned note is gone (trashed/purged) - fall back to auto.
                self.hashi_widget_note_id = ""
        button.setText(label)

    def _open_hashi_note_picker(self):
        from ._hashi_note_picker import HashiNotePickerDialog

        picker = HashiNotePickerDialog(
            getattr(self, "hashi_widget_note_id", ""),
            self._hashi_widget_notes(),
            self,
            accent=self.accent_color,
        )

        def on_selected(note_id):
            self.hashi_widget_note_id = str(note_id or "")
            self._refresh_hashi_widget_note_button()
            self._on_hashi_widget_changed()

        picker.noteSelected.connect(on_selected)
        picker.exec()

    def _hashi_widget_pinned_note(self):
        """The note Single mode would show: the pinned one, else the newest."""
        notes = self._hashi_widget_notes()
        try:
            note_id = str(getattr(self, "hashi_widget_note_id", "") or "")
        except Exception:
            note_id = ""
        if note_id:
            for note in notes:
                if note.get("id") == note_id:
                    return note
        return notes[0] if notes else self._hashi_widget_preview_notes(1)[0]

    def _hashi_preview_card_fill(self, note, mode, card_color):
        """A note's own colour fills the whole card, the same 80%-toward-the-
        surface tint the real pop-up paints its shell with - no accent bar."""
        color = str(note.get("color") or "").strip()
        if not color:
            return QColor(card_color)
        try:
            from .. import hashi_notes

            dark = self._hashi_widget_dynamic() and mode == "dark"
            tinted = QColor(hashi_notes._fill_tint(color, dark))
            if tinted.isValid():
                return tinted
        except Exception:
            pass
        return QColor(card_color)

    def _draw_hashi_widget_sample(self, painter, rect, mode, background_pixmap):
        effects = self._hashi_widget_effect_values()
        blur_radius = (effects["blur"] / 100.0) * 20.0
        fill_alpha = max(0.0, min(1.0, effects["opacity"] / 100.0))
        if blur_radius > 0:
            fill_alpha = min(fill_alpha, 0.62)
        box_color = QColor(self._hashi_widget_box_color(mode))
        box_color.setAlphaF(fill_alpha)

        painter.save()
        path = QPainterPath()
        radius = float(effects["radius"])
        path.addRoundedRect(rect, radius, radius)
        if blur_radius > 0 and background_pixmap and not background_pixmap.isNull():
            blurred = self._qt_blurred_pixmap(background_pixmap, blur_radius)
            if not blurred.isNull():
                painter.save()
                painter.setClipPath(path, Qt.ClipOperation.IntersectClip)
                painter.drawPixmap(0, 0, blurred)
                painter.restore()
        painter.fillPath(path, QBrush(box_color))
        stroke_width = max(0, int(effects["stroke"]))
        if stroke_width > 0:
            border_pen = QPen(QColor(self._hashi_widget_box_border_color(mode)))
            border_pen.setWidth(stroke_width)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
        painter.setClipPath(path, Qt.ClipOperation.IntersectClip)
        self._draw_hashi_widget_contents(painter, rect, mode)
        painter.restore()

    def _draw_hashi_widget_contents(self, painter, rect, mode):
        palette_mode = mode if self._hashi_widget_dynamic() else "light"
        title_color = QColor(self._hashi_widget_color("title", palette_mode))
        excerpt_color = QColor(self._hashi_widget_color("excerpt", palette_mode))
        card_color = QColor(self._hashi_widget_color("card_bg", palette_mode))
        accent_color = QColor(self._hashi_widget_color("accent", palette_mode))

        inner = QRectF(rect).adjusted(12, 10, -12, -12)
        head_font = QFont(painter.font())
        head_font.setPixelSize(11)
        head_font.setBold(True)
        painter.setFont(head_font)
        painter.setPen(QPen(title_color))
        head_rect = QRectF(inner.left(), inner.top(), inner.width(), 16)
        painter.drawText(
            head_rect,
            int(Qt.AlignmentFlag.AlignLeft.value) | int(Qt.AlignmentFlag.AlignVCenter.value),
            tr("hashi_notes_title", "Hashi Notes"),
        )
        if self.hashi_widget_show_date_toggle.isChecked():
            date_font = QFont(painter.font())
            date_font.setPixelSize(9)
            date_font.setBold(False)
            painter.setFont(date_font)
            painter.setPen(QPen(excerpt_color))
            painter.drawText(
                head_rect,
                int(Qt.AlignmentFlag.AlignRight.value) | int(Qt.AlignmentFlag.AlignVCenter.value),
                tr("hashi_today", "today"),
            )

        body_rect = QRectF(inner.left(), head_rect.bottom() + 6, inner.width(), inner.bottom() - head_rect.bottom() - 6)
        if body_rect.height() <= 8:
            return

        single = self._hashi_widget_mode() == "single"
        show_excerpt = self.hashi_widget_show_excerpt_toggle.isChecked()
        show_icon = self.hashi_widget_show_icon_toggle.isChecked()

        def _excerpt(note, limit):
            try:
                from .. import hashi_notes

                return hashi_notes._plain_excerpt(note.get("body_md"), limit)
            except Exception:
                return str(note.get("body_md") or "")

        def _draw_gallery_card(card_rect, note):
            card_path = QPainterPath()
            card_path.addRoundedRect(card_rect, 9, 9)
            painter.fillPath(card_path, QBrush(self._hashi_preview_card_fill(note, mode, card_color)))

            text_rect = QRectF(card_rect).adjusted(8, 6, -8, -6)
            title_font = QFont(painter.font())
            title_font.setPixelSize(10)
            title_font.setBold(True)
            painter.setFont(title_font)
            painter.setPen(QPen(title_color))
            title_rect = QRectF(text_rect.left(), text_rect.top(), text_rect.width(), 13)
            title_text = note.get("title") or tr("hashi_untitled", "Untitled")
            if show_icon:
                # Small colour dot standing in for the note's icon chip.
                dot = QColor(note.get("color") or accent_color.name())
                if not dot.isValid():
                    dot = accent_color
                dot_size = 6.0
                painter.setBrush(QBrush(dot))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(
                    QRectF(title_rect.left(), title_rect.center().y() - dot_size / 2, dot_size, dot_size)
                )
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(title_color))
                title_rect = QRectF(
                    title_rect.left() + dot_size + 5, title_rect.top(),
                    title_rect.width() - dot_size - 5, title_rect.height(),
                )
            painter.drawText(
                title_rect,
                int(Qt.AlignmentFlag.AlignLeft.value) | int(Qt.AlignmentFlag.AlignVCenter.value),
                title_text,
            )
            if not show_excerpt:
                return
            excerpt_font = QFont(painter.font())
            excerpt_font.setPixelSize(9)
            excerpt_font.setBold(False)
            painter.setFont(excerpt_font)
            painter.setPen(QPen(excerpt_color))
            excerpt_rect = QRectF(
                text_rect.left(), title_rect.bottom() + 3, text_rect.width(),
                text_rect.bottom() - title_rect.bottom() - 3,
            )
            if excerpt_rect.height() <= 4:
                return
            painter.drawText(
                excerpt_rect,
                int(Qt.AlignmentFlag.AlignLeft.value) | int(Qt.AlignmentFlag.AlignTop.value) | int(Qt.TextFlag.TextWordWrap.value),
                _excerpt(note, 90),
            )

        def _draw_single_card(card_rect, note):
            """A miniature of the real editor pop-up: tinted shell, title row,
            inset body sheet, footer pills."""
            fill = self._hashi_preview_card_fill(note, mode, card_color)
            card_path = QPainterPath()
            card_path.addRoundedRect(card_rect, 12, 12)
            painter.fillPath(card_path, QBrush(fill))

            inner_rect = QRectF(card_rect).adjusted(12, 10, -12, -10)
            accent = QColor(note.get("color") or accent_color.name())
            if not accent.isValid():
                accent = accent_color

            # --- title row (colour dot + icon chip + title) ---
            row_h = 20.0
            cursor_x = inner_rect.left()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(accent))
            painter.drawEllipse(QRectF(cursor_x, inner_rect.top() + 6, 8, 8))
            cursor_x += 14
            if show_icon:
                chip = QPainterPath()
                chip.addRoundedRect(QRectF(cursor_x, inner_rect.top() + 2, 16, 16), 5, 5)
                chip_color = QColor(fill)
                chip_color = chip_color.lighter(118) if mode == "dark" else chip_color.lighter(108)
                painter.fillPath(chip, QBrush(chip_color))
                cursor_x += 22
            painter.setBrush(Qt.BrushStyle.NoBrush)
            title_font = QFont(painter.font())
            title_font.setPixelSize(13)
            title_font.setBold(True)
            painter.setFont(title_font)
            painter.setPen(QPen(title_color))
            painter.drawText(
                QRectF(cursor_x, inner_rect.top(), inner_rect.right() - cursor_x, row_h),
                int(Qt.AlignmentFlag.AlignLeft.value) | int(Qt.AlignmentFlag.AlignVCenter.value),
                note.get("title") or tr("hashi_untitled", "Untitled"),
            )

            # --- footer row (the pop-up's Keep pills), drawn first so the body
            #     sheet can take whatever vertical space is left ---
            footer_h = 17.0
            footer_top = inner_rect.bottom() - footer_h
            pill_color = QColor(fill)
            pill_color = pill_color.lighter(112) if mode == "dark" else pill_color.lighter(106)
            label_font = QFont(painter.font())
            label_font.setPixelSize(8)
            label_font.setBold(True)
            painter.setFont(label_font)
            painter.setPen(QPen(excerpt_color))
            keep_label = tr("hashi_keep", "Keep").upper()
            keep_w = painter.fontMetrics().horizontalAdvance(keep_label)
            painter.drawText(
                QRectF(inner_rect.left(), footer_top, keep_w, footer_h),
                int(Qt.AlignmentFlag.AlignLeft.value) | int(Qt.AlignmentFlag.AlignVCenter.value),
                keep_label,
            )
            pill_x = inner_rect.left() + keep_w + 8
            pill_font = QFont(painter.font())
            pill_font.setPixelSize(9)
            pill_font.setBold(False)
            painter.setFont(pill_font)
            selected = str(note.get("retention", 30))
            for text, key in (("7d", "7"), ("30d", "30"), (tr("hashi_never", "Never"), "0")):
                width = painter.fontMetrics().horizontalAdvance(text) + 14
                if pill_x + width > inner_rect.right():
                    break
                filled = key == selected
                pill_rect = QRectF(pill_x, footer_top, width, footer_h)
                pill = QPainterPath()
                pill.addRoundedRect(pill_rect, footer_h / 2, footer_h / 2)
                painter.fillPath(pill, QBrush(accent if filled else pill_color))
                painter.setPen(QPen(QColor("#ffffff") if filled else excerpt_color))
                painter.drawText(
                    pill_rect,
                    int(Qt.AlignmentFlag.AlignCenter.value),
                    text,
                )
                pill_x += width + 5

            # --- body sheet ---
            sheet_rect = QRectF(
                inner_rect.left(), inner_rect.top() + row_h + 8,
                inner_rect.width(), footer_top - (inner_rect.top() + row_h + 8) - 8,
            )
            if sheet_rect.height() <= 6:
                return
            sheet = QPainterPath()
            sheet.addRoundedRect(sheet_rect, 10, 10)
            sheet_color = QColor(fill)
            sheet_color = sheet_color.lighter(108) if mode == "dark" else sheet_color.lighter(104)
            painter.fillPath(sheet, QBrush(sheet_color))
            if not show_excerpt:
                return
            excerpt_font = QFont(painter.font())
            excerpt_font.setPixelSize(10)
            excerpt_font.setBold(False)
            painter.setFont(excerpt_font)
            painter.setPen(QPen(excerpt_color))
            painter.drawText(
                QRectF(sheet_rect).adjusted(9, 7, -9, -7),
                int(Qt.AlignmentFlag.AlignLeft.value) | int(Qt.AlignmentFlag.AlignTop.value) | int(Qt.TextFlag.TextWordWrap.value),
                _excerpt(note, 240),
            )

        if single:
            _draw_single_card(body_rect, self._hashi_widget_pinned_note())
            return

        count = max(1, min(4, self.hashi_widget_limit_slider.value()))
        notes = self._hashi_widget_preview_notes(count)
        gap = 8.0
        card_w = (body_rect.width() - gap * (count - 1)) / count
        for index in range(count):
            card_rect = QRectF(body_rect.left() + index * (card_w + gap), body_rect.top(), card_w, body_rect.height())
            _draw_gallery_card(card_rect, notes[index])

    def _render_hashi_widget_preview_pixmap(self):
        size = self.hashi_widget_preview.size()
        width = max(1, size.width())
        height = max(1, size.height())
        dpr = max(1.0, self.hashi_widget_preview.devicePixelRatioF())
        target = QPixmap(int(width * dpr), int(height * dpr))
        target.setDevicePixelRatio(dpr)
        target.fill(Qt.GlobalColor.transparent)

        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        preview_rect = QRectF(1, 1, width - 2, height - 2)
        path = QPainterPath()
        path.addRoundedRect(preview_rect, 22, 22)
        painter.setClipPath(path)

        mode = self._hashi_widget_preview_mode()
        background = self._render_box_effect_background_for_mode(mode, width, height)
        painter.drawPixmap(0, 0, background)

        card_w = width * 0.84
        card_h = height * 0.82
        content_rect = QRectF((width - card_w) / 2.0, (height - card_h) / 2.0, card_w, card_h)
        self._draw_hashi_widget_sample(painter, content_rect, mode, background)

        painter.setClipping(False)
        border_color = QColor("#4b5563" if theme_manager.night_mode else "#d1d5db")
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()
        return target

    def _update_hashi_widget_preview(self):
        if not hasattr(self, "hashi_widget_preview"):
            return
        self.hashi_widget_preview.setStyleSheet(
            "QLabel#mainBackgroundPreview { background: transparent; border: none; }"
        )
        try:
            self.hashi_widget_preview.setPixmap(self._render_hashi_widget_preview_pixmap())
        except Exception as exc:
            print(f"Onigiri: failed to render Hashi widget settings preview: {exc}")
            fallback = QPixmap(
                max(1, self.hashi_widget_preview.width()), max(1, self.hashi_widget_preview.height())
            )
            fallback.fill(Qt.GlobalColor.transparent)
            self.hashi_widget_preview.setPixmap(fallback)
        self.hashi_widget_preview.setText("")

    def _save_hashi_widget_settings(self):
        if not hasattr(self, "hashi_widget_sync_toggle"):
            return
        style = self.current_config.setdefault("hashi_widget_style", {})
        style["mode"] = self._hashi_widget_mode()
        style["note_id"] = getattr(self, "hashi_widget_note_id", "") or ""
        style["limit"] = self.hashi_widget_limit_slider.value()
        style["sync_box_effect"] = self.hashi_widget_sync_toggle.isChecked()
        style["dynamic"] = self.hashi_widget_dynamic_toggle.isChecked()
        style["show_excerpt"] = self.hashi_widget_show_excerpt_toggle.isChecked()
        style["show_icon"] = self.hashi_widget_show_icon_toggle.isChecked()
        style["show_date"] = self.hashi_widget_show_date_toggle.isChecked()
        style["blur"] = self.hashi_widget_blur_slider.value()
        style["opacity"] = self.hashi_widget_opacity_slider.value()
        style["radius"] = self.hashi_widget_radius_slider.value()
        style["stroke"] = self.hashi_widget_stroke_slider.value()
        style["colors"] = {
            mode: dict(values) for mode, values in getattr(self, "hashi_widget_colors", {}).items()
        }

    def _save_hashi_notes_settings(self):
        self._save_hashi_widget_settings()
        if not hasattr(self, "hashi_retention_group"):
            return
        prefs = self.current_config.setdefault("hashi_notes", {})
        retention_button = self.hashi_retention_group.checkedButton()
        sort_button = self.hashi_sort_group.checkedButton()
        try:
            prefs["retention_default"] = int(
                retention_button.property("hashi_retention") if retention_button else 30
            )
        except Exception:
            prefs["retention_default"] = 30
        prefs["default_sort"] = (
            sort_button.property("hashi_sort") if sort_button else "age"
        )
        prefs["show_in_reviewer_header"] = self.hashi_show_in_header_toggle.isChecked()

    def _open_hashi_notes(self):
        self._save_hashi_notes_settings()
        config.write_config(self.current_config)
        from .. import hashi_notes

        hashi_notes.open_hashi_gallery(self)
