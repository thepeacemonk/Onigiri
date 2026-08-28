# Icon picker dialogs (split out of the historical _legacy.py).
from .common import *
from .common import _contrast_icon_color
from .widgets import *
from .picker_chrome import (
    CONTROL_RADIUS,
    ICON_CELL_RADIUS,
    ICON_CELL_SIZE,
    SEGMENT_BTN_HEIGHT,
    close_qss,
    color_panel_qss,
    color_row_qss,
    grid_panel_qss,
    icon_cell_qss,
    icon_header_qss,
    icon_modal_qss,
    picker_palette,
    pill_qss,
    scroll_qss,
    search_qss,
    segment_bar_qss,
    title_qss,
)
from ..emoji_sprites import EMOJI_SPRITES


class LongPressIconCell(QFrame):
    def __init__(self, value, on_select, on_delete, preview_label, bg_color, fill_color="#ef4444", parent=None):
        super().__init__(parent)
        self.value = value
        self.on_select = on_select
        self.on_delete = on_delete
        self.preview_label = preview_label
        self.bg_color = bg_color
        self.fill_color = fill_color
        
        self.progress = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._update_progress)
        self.is_pressing = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_pressing = True
            self.progress = 0.0
            self.timer.start()
            
            if not hasattr(self, "effect"):
                self.effect = QGraphicsColorizeEffect()
                self.effect.setColor(QColor(self.bg_color))
                self.preview_label.setGraphicsEffect(self.effect)
            self.effect.setStrength(0.0)
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_pressing:
            self.is_pressing = False
            self.timer.stop()
            if self.progress >= 1.0:
                pass
            else:
                self.progress = 0.0
                if hasattr(self, "effect"):
                    self.effect.setStrength(0.0)
                self.update()
                if self.on_select:
                    self.on_select(self.value, self)
        super().mouseReleaseEvent(event)

    def _update_progress(self):
        if not getattr(self, "fading_out", False):
            self.progress += 0.02
            if self.progress >= 1.0:
                self.progress = 1.0
                self.effect.setStrength(1.0)
                self.fading_out = True
                
                self.opacity_effect = QGraphicsOpacityEffect()
                self.setGraphicsEffect(self.opacity_effect)
                self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
                self.fade_anim.setDuration(200)
                self.fade_anim.setStartValue(1.0)
                self.fade_anim.setEndValue(0.0)
                self.fade_anim.finished.connect(self._finish_delete)
                self.fade_anim.start()
            else:
                if hasattr(self, "effect"):
                    self.effect.setStrength(self.progress)
            self.update()

    def _finish_delete(self):
        self.timer.stop()
        self.is_pressing = False
        if self.on_delete:
            self.on_delete(self.value)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.progress > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            clip_path = QPainterPath()
            clip_path.addRoundedRect(0, 0, self.width(), self.height(), ICON_CELL_RADIUS, ICON_CELL_RADIUS)
            painter.setClipPath(clip_path)
            
            rect = QRectF(0, 0, self.width() * self.progress, self.height())
            color = QColor(self.fill_color)
            color.setAlpha(220)
            painter.fillRect(rect, color)


class DeckIconPickerDialog(QDialog):
    iconSelected = pyqtSignal(str)
    colorsChanged = pyqtSignal(dict)

    EMOJIS = EMOJI_SPRITES
    ICON_PRIORITY = [
        "deck.svg", "folder.svg", "star.svg", "filtered-deck.svg",
        "add-card.svg", "add-deck.svg", "add-subdeck.svg",
        "add.svg", "browse.svg", "stats.svg", "sync.svg", "settings.svg",
        "rename.svg", "mark_circle.svg", "focus.svg", "gamepad.svg",
    ]

    def __init__(self, current_icon, addon_path, parent=None, allow_emoji=True, color_options=None, preview_color_key=None, night_mode=None, title=None):
        super().__init__(parent)
        self.addon_path = addon_path
        self._title = title or tr("edit_icon")
        # Callers (e.g. Hashi Notes) can force the picker to match their own
        # light/dark state so its colours stay aligned; defaults to Anki's theme.
        self._dark = bool(theme_manager.night_mode) if night_mode is None else bool(night_mode)
        self.current_icon = current_icon or ""
        self.allow_emoji = allow_emoji
        self.color_options = color_options or []
        self.color_values = {
            option.get("key"): option.get("value", "#00A982")
            for option in self.color_options
            if option.get("key")
        }
        self.preview_color_key = preview_color_key or (self.color_options[0].get("key") if self.color_options else None)
        self._color_buttons = {}
        self._cell_widgets = {}
        self._has_color_mode_pairs = self._color_options_have_mode_pairs()
        self.setWindowTitle(self._title)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(560, 760 if self.color_options else 660)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        self.container = QFrame()
        self.container.setObjectName("IconPickerContainer")
        self._accent = self._parent_accent()
        self._apply_palette(self._dark)
        outer.addWidget(self.container)

        # The modal is one tinted header strip on top of a plain body — same
        # shape as the WebUI settings popover and the deck browser's modal, so
        # every icon selector in the add-on reads as the same dialog.
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header_frame = QFrame()
        self.header_frame.setObjectName("IconPickerHeader")
        self.header_frame.setStyleSheet(icon_header_qss(self._pal))
        header = QHBoxLayout(self.header_frame)
        header.setContentsMargins(20, 16, 16, 16)
        header.setSpacing(10)
        self.title_label = QLabel(self._title)
        self.title_label.setStyleSheet(title_qss(self._pal))
        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(close_qss(self._pal))
        self._update_close_button_icon()
        self.close_btn.clicked.connect(self.close)
        header.addWidget(self.title_label)
        header.addStretch()

        self.preview_mode = "dark" if self._dark else "light"
        if self.parent() and hasattr(self.parent(), "_create_light_dark_mode_toggle"):
            self.preview_mode_widget, self.preview_mode_toggle = self.parent()._create_light_dark_mode_toggle(
                self.preview_mode,
                self._on_preview_mode_toggled,
            )
            header.addWidget(self.preview_mode_widget)

        header.addWidget(self.close_btn)
        layout.addWidget(self.header_frame)

        body = QVBoxLayout()
        body.setContentsMargins(20, 14, 20, 16)
        body.setSpacing(12)
        layout.addLayout(body, 1)

        self.segment_bar = QFrame()
        self.segment_bar.setObjectName("IconPickerSegments")
        self.segment_bar.setStyleSheet(segment_bar_qss(self._pal))
        self.segment_layout = QHBoxLayout(self.segment_bar)
        self.segment_layout.setContentsMargins(3, 3, 3, 3)
        self.segment_layout.setSpacing(2)
        self.segment_group = QButtonGroup(self)
        self.segment_group.setExclusive(True)
        self._segment_buttons = []
        body.addWidget(self.segment_bar)

        self.tabs = QStackedWidget()
        body.addWidget(self.tabs, 1)

        self._build_tabs()

        if self.color_options:
            body.addWidget(self._colors_panel())
            self._sync_preview_mode_availability()

        footer = QHBoxLayout()
        footer.setSpacing(10)
        save_btn = QPushButton(tr("save"))
        cancel_btn = QPushButton(tr("cancel"))
        reset_btn = QPushButton(tr("reset_to_default_tooltip"))
        self.cancel_btn = cancel_btn
        self.reset_btn = reset_btn
        for btn in (save_btn, cancel_btn, reset_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(36)
            btn.setAutoDefault(False)
            btn.setDefault(False)
            # ID selector: plain "QPushButton { border-radius: ... }" rules on an
            # ancestor stylesheet (and the settings radius patch) outrank a
            # type-selector rule set here and would square the pill off.
            btn.setObjectName("iconPickerFooterPill")
        self.save_btn = save_btn
        save_btn.setStyleSheet(pill_qss(self._pal, primary=True))
        for btn in (cancel_btn, reset_btn):
            btn.setStyleSheet(pill_qss(self._pal))
        save_btn.clicked.connect(self._save_and_close)
        reset_btn.clicked.connect(self._reset_to_default)
        cancel_btn.clicked.connect(self.close)
        footer.addStretch()
        footer.addWidget(save_btn)
        footer.addWidget(cancel_btn)
        footer.addWidget(reset_btn)
        footer.addStretch()
        body.addLayout(footer)

    def _parent_accent(self):
        accent = getattr(self.parent(), "accent_color", "#00A982") if self.parent() else "#00A982"
        if type(accent) is QColor:
            accent = accent.name()
        return accent if QColor(accent).isValid() else "#00A982"

    def _apply_palette(self, dark):
        """Single place the picker's colours come from. The `_fg`/`_muted`/
        `_surface`/`_border` aliases are kept for outside callers."""
        self._pal = picker_palette(dark, self._accent)
        self._fg = self._pal["fg"]
        self._muted = self._pal["muted"]
        self._surface = self._pal["inset"]
        self._border = self._pal["hairline"]
        self.container.setStyleSheet(icon_modal_qss(self._pal))

    def _save_and_close(self):
        self.iconSelected.emit(self.current_icon)
        self.close()

    def _reset_to_default(self):
        # Icon reset alone used to leave stale custom colors on screen (the
        # swatch never looked "reset" if the default icon happened to match
        # the current one). Also restore any color option that declares a
        # "default" value.
        changed = False
        for option in self.color_options:
            key = option.get("key")
            if not key or "default" not in option:
                continue
            default_value = self._valid_color(option["default"])
            if self.color_values.get(key) != default_value:
                changed = True
            self.color_values[key] = default_value
            button = self._color_buttons.get(key)
            if button is not None:
                self._style_color_option_button(button, default_value)
        if changed:
            self.colorsChanged.emit(dict(self.color_values))
        self.iconSelected.emit("")
        self.close()

    def _on_preview_mode_toggled(self, mode):
        self.preview_mode = mode
        self._apply_palette(mode == "dark")

        if hasattr(self, 'title_label'):
            self.header_frame.setStyleSheet(icon_header_qss(self._pal))
            self.title_label.setStyleSheet(title_qss(self._pal))
            self.close_btn.setStyleSheet(close_qss(self._pal))
            self._update_close_button_icon()
            self.save_btn.setStyleSheet(pill_qss(self._pal, primary=True))
            for btn in (self.cancel_btn, self.reset_btn):
                btn.setStyleSheet(pill_qss(self._pal))

        if self.color_options and hasattr(self, "colors_panel_widget"):
            self.colors_panel_widget.setStyleSheet(color_panel_qss(self._pal))
            for label in getattr(self, "colors_panel_labels", []):
                label.setStyleSheet(f"background: transparent; font-weight: 600; font-size: 12px; color: {self._fg};")
            for key, btn in getattr(self, "_color_buttons", {}).items():
                self._style_color_option_button(btn, self.color_values.get(key, "#00A982"))
            self._update_colors_panel_mode()

        if hasattr(self, "segment_bar"):
            self.segment_bar.setStyleSheet(segment_bar_qss(self._pal))

        self._build_tabs()

    def _update_close_button_icon(self):
        if not hasattr(self, "close_btn"):
            return
        xmark_icon = self._render_svg_to_icon(system_icon_path("cancel.svg"), self._fg, 16)
        if not xmark_icon.isNull():
            self.close_btn.setText("")
            self.close_btn.setIcon(xmark_icon)
            self.close_btn.setIconSize(QSize(16, 16))
        else:
            self.close_btn.setIcon(QIcon())
            self.close_btn.setText("×")

    def _custom_icon_dir(self):
        path = os.path.join(self.addon_path, "user_files", "custom_deck_icons")
        os.makedirs(path, exist_ok=True)
        return path

    def _icon_label(self, filename):
        stem = os.path.splitext(os.path.basename(filename))[0]
        return stem.replace("_", " ").replace("-", " ").title()

    def _emoji_svg_path(self, filename):
        return os.path.join(self.addon_path, "system_files", "emojis", os.path.basename(filename))

    def _delete_custom_icon(self, name):
        for folder in (self._custom_icon_dir(), os.path.join(self.addon_path, "user_files", "icons")):
            path = os.path.join(folder, name)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        if self.current_icon == name:
            self.current_icon = ""
        self._build_tabs()

    def _system_icon_items(self):
        system_dir = os.path.join(self.addon_path, "system_files", "system_icons", "available_for_users")
        if not os.path.isdir(system_dir):
            return []
        priority = {name: index for index, name in enumerate(self.ICON_PRIORITY)}
        files = [name for name in os.listdir(system_dir) if name.lower().endswith(".svg")]
        return [
            {"name": f"system:{name}", "label": self._icon_label(name), "path": os.path.join(system_dir, name), "system": True}
            for name in sorted(files, key=lambda item: (priority.get(item, 999), item.lower()))
        ]

    def _custom_items(self, extensions):
        items = []
        seen = set()
        for folder in (self._custom_icon_dir(), os.path.join(self.addon_path, "user_files", "icons")):
            if not os.path.isdir(folder):
                continue
            for name in sorted(os.listdir(folder), key=str.lower):
                lower = name.lower()
                if name in seen or not any(lower.endswith(ext) for ext in extensions):
                    continue
                seen.add(name)
                items.append({"name": name, "label": self._icon_label(name), "path": os.path.join(folder, name), "system": False})
        return items

    def _build_tabs(self):
        current_tab = self.tabs.currentIndex() if self.tabs.count() else 0
        while self.tabs.count():
            page = self.tabs.widget(0)
            self.tabs.removeWidget(page)
            page.deleteLater()
        self._cell_widgets = {}

        pages = []
        if self.allow_emoji:
            pages.append(("Emoji", self._emoji_tab()))
        pages.append((tr("icons", "Icons"), self._icons_tab()))
        pages.append((tr("upload", "Upload"), self._upload_tab()))
        for _, page in pages:
            self.tabs.addWidget(page)

        # Segments are rebuilt with the pages so a palette flip restyles them
        # in one pass instead of leaving stale buttons behind.
        for btn in self._segment_buttons:
            self.segment_group.removeButton(btn)
            self.segment_layout.removeWidget(btn)
            btn.deleteLater()
        self._segment_buttons = []
        for index, (label, _) in enumerate(pages):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setAutoDefault(False)
            btn.setDefault(False)
            btn.setFixedHeight(SEGMENT_BTN_HEIGHT)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _=False, i=index: self.tabs.setCurrentIndex(i))
            self.segment_group.addButton(btn)
            self.segment_layout.addWidget(btn)
            self._segment_buttons.append(btn)

        index = min(max(current_tab, 0), len(pages) - 1)
        self.tabs.setCurrentIndex(index)
        self._segment_buttons[index].setChecked(True)

    def _valid_color(self, value, fallback="#00A982"):
        return value if QColor(value).isValid() else fallback

    def _gallery_icon_color(self):
        mode = getattr(self, "preview_mode", "dark" if theme_manager.night_mode else "light")
        key = self.preview_color_key
        if key:
            if mode == "dark":
                if key == "light_icon": key = "dark_icon"
                elif key == "light_filtered": key = "dark_filtered"
                elif key == "star_light": key = "star_dark"
                elif key == "empty_light": key = "empty_dark"
                elif key == "light_shape": key = "dark_shape"
                elif key == "light_zero": key = "dark_zero"
            elif mode == "light":
                if key == "dark_icon": key = "light_icon"
                elif key == "dark_filtered": key = "light_filtered"
                elif key == "star_dark": key = "star_light"
                elif key == "empty_dark": key = "empty_light"
                elif key == "dark_shape": key = "light_shape"
                elif key == "dark_zero": key = "light_zero"
            return self._valid_color(self.color_values.get(key, self.color_values.get(self.preview_color_key, "#00A982")))
        return "#e0e0e0" if mode == "dark" else "#212121"

    def _color_option_mode(self, option):
        explicit_mode = option.get("mode")
        if explicit_mode in {"light", "dark", "single"}:
            return explicit_mode

        key = str(option.get("key", ""))
        if key.startswith("light_") or key.endswith("_light"):
            return "light"
        if key.startswith("dark_") or key.endswith("_dark"):
            return "dark"
        return "single"

    def _color_options_have_mode_pairs(self):
        modes = {self._color_option_mode(option) for option in self.color_options}
        return "light" in modes and "dark" in modes

    def _color_options_for_mode(self, mode):
        if not self._has_color_mode_pairs:
            return self.color_options
        return [
            option
            for option in self.color_options
            if self._color_option_mode(option) in {mode, "single"}
        ]

    def _clean_color_option_label(self, label, mode):
        text = str(label or "Color").strip()
        mode_title = mode.title()
        replacements = (
            (f"{mode_title} (", "("),
            (f"{mode_title} ", ""),
            (f" {mode_title}", ""),
            (f" ({mode_title})", ""),
        )
        for old, new in replacements:
            text = text.replace(old, new)
        return text.strip() or "Color"

    def _sync_preview_mode_availability(self):
        widget = getattr(self, "preview_mode_widget", None)
        if widget is None or not self.color_options:
            return
        widget.setEnabled(self._has_color_mode_pairs)
        widget.setToolTip("" if self._has_color_mode_pairs else tr("single_palette_only"))

    def _update_colors_panel_mode(self):
        stack = getattr(self, "colors_mode_stack", None)
        if stack is None:
            return
        stack.setCurrentIndex(1 if self._has_color_mode_pairs and self.preview_mode == "dark" else 0)

    def _create_color_options_page(self, options, mode):
        page = QWidget()
        page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        for index, option in enumerate(options):
            key = option.get("key")
            if not key:
                continue

            option_mode = self._color_option_mode(option)
            label_text = option.get("label", "Color")
            if option_mode in {"light", "dark"}:
                label_text = self._clean_color_option_label(label_text, mode)

            # One pill per colour — swatch first, then the option's own name,
            # two to a row, exactly like the colour rows under the grid in the
            # WebUI settings icon popover.
            button = QPushButton()
            button.setObjectName("IconPickerColorRow")
            button.setProperty("option_label", label_text)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedHeight(38)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setAutoDefault(False)
            button.setDefault(False)
            self._color_buttons[key] = button
            self._style_color_option_button(button, self.color_values.get(key, "#00A982"))
            button.clicked.connect(lambda _=False, k=key, b=button: self._choose_picker_color(k, b))

            layout.addWidget(button, index // 2, index % 2)

        layout.setColumnStretch(0, 1)
        if len(options) > 1:
            layout.setColumnStretch(1, 1)
        return page

    def _colors_panel(self):
        panel = QFrame()
        self.colors_panel_widget = panel
        self.colors_panel_labels = []
        panel.setObjectName("IconPickerColorPanel")
        panel.setStyleSheet(color_panel_qss(self._pal))
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(0)

        self.colors_mode_stack = QStackedWidget()
        self.colors_mode_stack.addWidget(self._create_color_options_page(self._color_options_for_mode("light"), "light"))
        if self._has_color_mode_pairs:
            self.colors_mode_stack.addWidget(self._create_color_options_page(self._color_options_for_mode("dark"), "dark"))
        layout.addWidget(self.colors_mode_stack)
        self._update_colors_panel_mode()
        return panel

    def _color_swatch_icon(self, color, size=18):
        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        pixmap = QPixmap(int(size * dpr), int(size * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(0, 0, size, size), 6, 6)
        painter.end()
        return QIcon(pixmap)

    def _style_color_option_button(self, button, color):
        color = self._valid_color(color)
        button.setText(button.property("option_label") or color.upper())
        button.setIcon(self._color_swatch_icon(color))
        button.setIconSize(QSize(18, 18))
        button.setToolTip(color.upper())
        button.setStyleSheet(color_row_qss(self._pal))

    def _choose_picker_color(self, key, anchor=None):
        current = self._valid_color(self.color_values.get(key, "#00A982"))
        chosen, ok = OnigiriColorDialog.getColor(current, self, anchor=anchor)
        if not ok:
            return
        chosen = self._valid_color(chosen, current)
        self.color_values[key] = chosen
        button = self._color_buttons.get(key)
        if button is not None:
            self._style_color_option_button(button, chosen)
        self.colorsChanged.emit(dict(self.color_values))
        self._build_tabs()

    def _scroll_style(self):
        """Modern, theme-aware scrollbar matching the rest of Onigiri's dialogs."""
        return scroll_qss(self._pal)

    def _search_field(self, placeholder, on_text):
        search = QLineEdit()
        search.setPlaceholderText(placeholder)
        search.setFixedHeight(38)
        search.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        search.setStyleSheet(search_qss(self._pal))
        search.textChanged.connect(lambda text: on_text(text.strip().lower()))
        return search

    def _grid_panel(self, scroll):
        """The grid lives on its own inset panel, tiles on the modal surface."""
        panel = QFrame()
        panel.setObjectName("IconPickerGridPanel")
        panel.setStyleSheet(grid_panel_qss(self._pal))
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        layout.addWidget(scroll)
        return panel

    def _icons_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(self._scroll_style())
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        flow = FlowLayout(content, margin=0, spacing=8)
        scroll.setWidget(content)

        # One flat grid, no section labels: the user's own icons first, then
        # everything shipped in system_files/system_icons/available_for_users.
        user_items = [{"is_add_button": True}] + self._custom_items((".svg",))
        system_items = self._system_icon_items()
        all_items = user_items + system_items

        def render(filter_text=""):
            while flow.count():
                item = flow.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            for item in all_items:
                if item.get("is_add_button"):
                    flow.addWidget(self._icon_cell(item, image_mode=False))
                    continue
                haystack = f"{item.get('label', '')} {item.get('name', '')}".lower()
                if filter_text and filter_text not in haystack:
                    continue
                flow.addWidget(self._icon_cell(item, image_mode=False))

        layout.addWidget(self._search_field(tr("search_icons", "Search icons"), render))
        layout.addWidget(self._grid_panel(scroll), 1)
        render()
        return tab

    def _grid_tab(self, items, image_mode=False):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)
        search = QLineEdit()
        search.setPlaceholderText(tr("search_images") if image_mode else tr("search_icons_placeholder"))
        search.setFixedHeight(38)
        search.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        search.setStyleSheet(search_qss(self._pal))
        layout.addWidget(search)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(self._scroll_style())
        content = QWidget()
        flow = FlowLayout(content, margin=2, spacing=8)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        def render(filter_text=""):
            while flow.count():
                item = flow.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            for item in items:
                haystack = f"{item.get('label', '')} {item.get('name', '')}".lower()
                if filter_text and filter_text not in haystack:
                    continue
                flow.addWidget(self._icon_cell(item, image_mode=image_mode))

        search.textChanged.connect(lambda text: render(text.strip().lower()))
        render()
        return tab

    def _emoji_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(self._scroll_style())
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        flow = FlowLayout(content, margin=0, spacing=8)
        scroll.setWidget(content)

        def render(filter_text=""):
            while flow.count():
                item = flow.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            for emoji in self.EMOJIS:
                haystack = f"{emoji.get('label', '')} {emoji.get('value', '')}".lower()
                if filter_text and filter_text not in haystack:
                    continue
                flow.addWidget(self._emoji_cell(emoji))

        layout.addWidget(self._search_field(tr("search_emoji", "Search emoji"), render))
        layout.addWidget(self._grid_panel(scroll), 1)
        layout.addWidget(self._custom_emoji_row())
        render()
        return tab

    def _upload_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        for label, extensions in (
            (tr("upload_svg", "Upload SVG icon"), "*.svg"),
            (tr("upload_png", "Upload PNG image"), "*.png"),
        ):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(56)
            btn.setAutoDefault(False)
            btn.setDefault(False)
            btn.setStyleSheet(f"QPushButton {{ background: {self._pal['inset']}; color: {self._fg}; border: none; border-radius: 14px; font-size: 13px; font-weight: 500; }} QPushButton:hover {{ background: {self._pal['inset_hover']}; }}")
            btn.clicked.connect(lambda _, ext=extensions: self._upload_files(ext))
            layout.addWidget(btn)
        layout.addStretch()
        return tab

    def _cell_style(self, selected):
        icon_color = self._gallery_icon_color()
        if type(icon_color) is QColor:
            icon_color = icon_color.name()
        return icon_cell_qss(self._pal, selected, icon_color)

    def _select_pending_icon(self, value, cell):
        previous = self.current_icon
        self.current_icon = value
        cell.setStyleSheet(self._cell_style(True))
        if previous != value:
            old_cell = self._cell_widgets.get(previous)
            if old_cell is not None:
                try:
                    if sip is None or not sip.isdeleted(old_cell):
                        old_cell.setStyleSheet(self._cell_style(False))
                except Exception:
                    pass
        self._cell_widgets[value] = cell

    def _emoji_cell(self, emoji):
        value = f"emoji:{emoji['value']}"
        cell = QFrame()
        cell.setFixedSize(ICON_CELL_SIZE, ICON_CELL_SIZE)
        cell.setToolTip(emoji.get("label", emoji["value"]))
        cell.setStyleSheet(self._cell_style(value == self.current_icon))
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(6, 6, 6, 6)
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("background: transparent; border: none;")
        svg_path = self._emoji_svg_path(emoji.get("asset", ""))
        if os.path.exists(svg_path):
            self._render_emoji_svg_to_label(svg_path, label)
        else:
            label.setText(emoji["value"])
            label.setStyleSheet("background: transparent; border: none; font-size: 26px;")
        layout.addWidget(label)
        cell.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cell_widgets[value] = cell
        def select_emoji(event, v=value, c=cell):
            self._select_pending_icon(v, c)
            return None
        cell.mousePressEvent = select_emoji
        return cell

    def _custom_emoji_row(self):
        row = QFrame()
        row.setObjectName("CustomEmojiRow")
        row.setStyleSheet(f"""
            QFrame#CustomEmojiRow {{
                background: {self._pal['inset']};
                border: 1px solid transparent;
                border-radius: 14px;
            }}
            QPushButton {{
                background: {self._pal['inset_hover']};
                color: {self._fg};
                border: none;
                border-radius: {CONTROL_RADIUS}px;
                padding: 0 12px;
                font-weight: 600;
            }}
            QLineEdit {{
                background: {self._pal['surface_solid']};
                color: {self._fg};
                border: 1px solid transparent;
                border-radius: {CONTROL_RADIUS}px;
                padding: 0 10px;
                font-size: 18px;
            }}
            QLineEdit:focus {{
                border-color: {self._pal['accent']};
            }}
        """)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        button = QPushButton(tr("type_your_own"))
        button.setFixedHeight(34)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        custom_input = QLineEdit()
        custom_input.setFixedHeight(34)
        custom_input.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        preset_values = {f"emoji:{item['value']}" for item in self.EMOJIS}
        if self.current_icon.startswith("emoji:") and self.current_icon not in preset_values:
            custom_input.setText(self.current_icon[len("emoji:"):])

        def select_custom():
            emoji = custom_input.text().strip()
            if emoji:
                previous = self.current_icon
                self.current_icon = f"emoji:{emoji}"
                old_cell = self._cell_widgets.get(previous)
                if old_cell is not None:
                    try:
                        if sip is None or not sip.isdeleted(old_cell):
                            old_cell.setStyleSheet(self._cell_style(False))
                    except Exception:
                        pass

        button.clicked.connect(lambda: (custom_input.setFocus(), select_custom()))
        custom_input.textChanged.connect(lambda _: select_custom())
        custom_input.returnPressed.connect(select_custom)
        layout.addWidget(button)
        layout.addWidget(custom_input, 1)
        return row

    def _render_emoji_svg_to_label(self, filepath, label):
        try:
            renderer = QSvgRenderer(filepath)
            dpr = label.devicePixelRatioF() if hasattr(label, "devicePixelRatioF") else 1.0
            pixmap = QPixmap(int(26 * dpr), int(26 * dpr))
            pixmap.setDevicePixelRatio(dpr)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            renderer.render(painter, svg_contain_rect(renderer, 26))
            painter.end()
            label.setPixmap(pixmap)
        except Exception:
            label.setText("?")

    def _icon_cell(self, item, image_mode=False):
        icon_color = self._gallery_icon_color()
        if type(icon_color) is QColor:
            icon_color = icon_color.name()

        if item.get("is_add_button"):
            cell = QFrame()
            cell.setFixedSize(ICON_CELL_SIZE, ICON_CELL_SIZE)
            cell.setCursor(Qt.CursorShape.PointingHandCursor)
            cell.setStyleSheet(icon_cell_qss(self._pal, False, icon_color))
            layout = QVBoxLayout(cell)
            layout.setContentsMargins(6, 6, 6, 6)
            preview = QLabel()
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setStyleSheet("background: transparent; border: none;")
            self._render_svg_to_label(system_icon_path("unavailable_for_users/add.svg"), preview)
            layout.addWidget(preview)
            
            def on_add(event):
                self._upload_files(["*.svg"])
                return None
            cell.mousePressEvent = on_add
            return cell

        preview = QLabel()
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setStyleSheet("background: transparent; border: none;")

        is_custom = item.get("system") is False
        if is_custom:
            def on_delete(v):
                self._delete_custom_icon(v)
            # bg_color feeds a QColor, so it needs a solid value — the palette's
            # "inset" token is an rgba() string Qt can't parse.
            cell = LongPressIconCell(item["name"], self._select_pending_icon, on_delete, preview, bg_color=self._pal["surface_solid"], fill_color=icon_color)
        else:
            cell = QFrame()
            def select_icon(event, v=item["name"], c=cell):
                self._select_pending_icon(v, c)
                return None
            cell.mousePressEvent = select_icon

        cell.setFixedSize(ICON_CELL_SIZE, ICON_CELL_SIZE)
        cell.setStyleSheet(self._cell_style(item["name"] == self.current_icon))
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(6, 6, 6, 6)
        if image_mode:
            pixmap = QPixmap(item["path"])
            if not pixmap.isNull():
                dpr = preview.devicePixelRatioF() if hasattr(preview, "devicePixelRatioF") else 1.0
                scaled = pixmap.scaled(
                    int(24 * dpr), int(24 * dpr),
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                scaled.setDevicePixelRatio(dpr)
                preview.setPixmap(scaled)
        else:
            self._render_svg_to_label(item["path"], preview)
        layout.addWidget(preview)
        if not is_custom:
            cell.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cell_widgets[item["name"]] = cell
        return cell

    def _render_svg_to_icon(self, filepath, color, size=16):
        if not filepath or not os.path.exists(filepath):
            return QIcon()
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                svg_xml = f.read()
            if "currentColor" in svg_xml:
                svg_xml = svg_xml.replace("currentColor", color)
            renderer = QSvgRenderer(svg_xml.encode("utf-8"))
            dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
            pixmap = QPixmap(int(size * dpr), int(size * dpr))
            pixmap.setDevicePixelRatio(dpr)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            renderer.render(painter, svg_contain_rect(renderer, size))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(QRectF(0, 0, size, size), QColor(color))
            painter.end()
            return QIcon(pixmap)
        except Exception:
            return QIcon()

    def _render_svg_to_label(self, filepath, label):
        color = self._gallery_icon_color()
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                svg_xml = f.read()
            if "currentColor" in svg_xml:
                svg_xml = svg_xml.replace("currentColor", color)
            renderer = QSvgRenderer(svg_xml.encode("utf-8"))
            dpr = label.devicePixelRatioF() if hasattr(label, "devicePixelRatioF") else 1.0
            pixmap = QPixmap(int(22 * dpr), int(22 * dpr))
            pixmap.setDevicePixelRatio(dpr)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            renderer.render(painter, svg_contain_rect(renderer, 22))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(QRectF(0, 0, 22, 22), QColor(color))
            painter.end()
            label.setPixmap(pixmap)
        except Exception:
            label.setText("?")

    def _upload_files(self, extension):
        title = "Select PNG images" if extension == "*.png" else "Select SVG icons"
        pattern = "PNG Images (*.png)" if extension == "*.png" else "SVG Icons (*.svg)"
        files, _ = QFileDialog.getOpenFileNames(self, title, "", pattern)
        if not files:
            return
        dest_dir = self._custom_icon_dir()
        for path in files:
            if not os.path.isfile(path):
                continue
            base, ext = os.path.splitext(os.path.basename(path))
            dest = os.path.join(dest_dir, base + ext)
            index = 2
            while os.path.exists(dest):
                dest = os.path.join(dest_dir, f"{base}-{index}{ext}")
                index += 1
            try:
                shutil.copy2(path, dest)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not copy icon: {e}")
        self._build_tabs()


class IconPickerDialog(DeckIconPickerDialog):
    """Kept for the older call sites that opened the icon-only picker. It is the
    same dialog as everywhere else now — one icon selector, one design — with
    the emoji segment left out."""

    def __init__(self, current_filename, addon_path, parent=None):
        super().__init__(
            current_filename,
            addon_path,
            parent,
            allow_emoji=False,
            title=tr("select_icon", "Select Icon"),
        )
