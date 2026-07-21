# Dedicated editor for the Stats Title widget: the one-line phrase the widget
# shows plus the font it renders in. Mirrors the look and behaviour of
# FontPickerDialog in _font_picker.py — a frameless, rounded, theme-aware
# container with a light/dark preview toggle, a scrollable font gallery, and a
# Save / Cancel / Use Default footer — with the phrase box added on top.
from ._common import *
from ._common import _font_popup_svg_icon, _font_popup_svg_pixmap

# The widget is one line on the main menu, so a hard word cap keeps it from
# overflowing its grid cell no matter how wide the user makes it.
STATS_TITLE_MAX_WORDS = 10

# Font key meaning "follow whatever the Titles font is set to" rather than
# naming a font of its own.
STATS_TITLE_SYNC_KEY = "sync"


def stats_title_word_count(text):
    return len(str(text or "").split())


def clamp_stats_title(text):
    """Collapse to a single line of at most STATS_TITLE_MAX_WORDS words."""
    words = str(text or "").replace("\n", " ").replace("\r", " ").split()
    return " ".join(words[:STATS_TITLE_MAX_WORDS])


class _TitleFontCell(QFrame):
    """A single clickable font row. Optionally shows a delete button (for
    user-added fonts)."""

    def __init__(self, font_key, on_select, parent=None):
        super().__init__(parent)
        self.font_key = font_key
        self._on_select = on_select
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_select(self.font_key)
        super().mousePressEvent(event)


class StatsTitleDialog(QDialog):
    """Pop-up that edits the Stats Title widget's phrase and font.

    Emits ``titleAccepted(text, font_key)`` when the user confirms with Save (or
    with Use Default, which emits the stock welcome phrase and the sync key)."""

    titleAccepted = pyqtSignal(str, str)

    def __init__(self, current_text, current_font_key, addon_path, parent=None):
        super().__init__(parent)
        self.addon_path = addon_path
        self.current_text = clamp_stats_title(current_text)
        self.current_key = current_font_key or STATS_TITLE_SYNC_KEY
        self._family_cache = {}
        self._cell_widgets = {}
        self._dark = bool(theme_manager.night_mode)
        self._title_text = tr("edit_title", "Edit Title")

        self.setWindowTitle(self._title_text)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(560, 700)

        self._apply_palette()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        self.container = QFrame()
        self.container.setObjectName("StatsTitleContainer")
        outer.addWidget(self.container)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # ── Header ──────────────────────────────────────────────────────────
        header = QHBoxLayout()
        self.title_label = QLabel(self._title_text)
        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.reject)
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
        layout.addLayout(header)

        # ── Phrase box ──────────────────────────────────────────────────────
        self.phrase_card = QFrame()
        self.phrase_card.setObjectName("StatsTitlePhraseCard")
        phrase_layout = QVBoxLayout(self.phrase_card)
        phrase_layout.setContentsMargins(16, 14, 16, 12)
        phrase_layout.setSpacing(8)

        self.phrase_label = QLabel(tr("stats_title_phrase", "Your Phrase"))
        phrase_layout.addWidget(self.phrase_label)

        self.text_input = QLineEdit(self.current_text)
        self.text_input.setObjectName("StatsTitleInput")
        self.text_input.setMaxLength(200)
        self.text_input.setPlaceholderText(DEFAULTS["statsTitle"])
        self.text_input.setFixedHeight(46)
        self.text_input.textChanged.connect(self._on_text_changed)
        phrase_layout.addWidget(self.text_input)

        self.counter_label = QLabel()
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        phrase_layout.addWidget(self.counter_label)

        layout.addWidget(self.phrase_card)

        # ── Gallery ─────────────────────────────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(2, 2, 6, 6)
        self.content_layout.setSpacing(10)
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll, 1)

        # ── Footer ──────────────────────────────────────────────────────────
        footer = QHBoxLayout()
        footer.setSpacing(10)
        self.add_btn = QPushButton(tr("add_your_font", "Add Your Own Font"))
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setFixedHeight(36)
        self.add_btn.setAutoDefault(False)
        self.add_btn.setDefault(False)
        self.add_btn.clicked.connect(self._add_user_font)
        footer.addWidget(self.add_btn)
        footer.addStretch()

        self.save_btn = QPushButton(tr("save", "Save"))
        self.cancel_btn = QPushButton(tr("cancel", "Cancel"))
        self.reset_btn = QPushButton(tr("use_default", "Use Default"))
        for btn in (self.save_btn, self.cancel_btn, self.reset_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(36)
            btn.setAutoDefault(False)
            btn.setDefault(False)
        self.save_btn.clicked.connect(self._save_and_close)
        self.cancel_btn.clicked.connect(self.reject)
        self.reset_btn.clicked.connect(self._reset_to_default)
        footer.addWidget(self.save_btn)
        footer.addWidget(self.cancel_btn)
        footer.addWidget(self.reset_btn)
        layout.addLayout(footer)

        self._style_chrome()
        self._render_gallery()
        self._on_text_changed(self.text_input.text())

    # ── Theme handling ──────────────────────────────────────────────────────
    def _apply_palette(self):
        if self._dark:
            self._bg = "#161616"
            self._bg_border = "#343434"
            self._fg = "#f4f4f5"
            self._muted = "#b6b6b8"
            self._surface = "#2a2a2a"
            self._border = "#3a3a3a"
        else:
            self._bg = "#ffffff"
            self._bg_border = "#e5e7eb"
            self._fg = "#1f2933"
            self._muted = "#4b5563"
            self._surface = "#f5f5f4"
            self._border = "#e5e7eb"
        accent = getattr(self.parent(), "accent_color", "#00A982") if self.parent() else "#00A982"
        if type(accent) is QColor:
            accent = accent.name()
        self._accent = accent if QColor(accent).isValid() else "#00A982"

    def _style_chrome(self):
        self.container.setStyleSheet(
            f"QFrame#StatsTitleContainer {{ background-color: {self._bg};"
            f" border-radius: 20px; border: 1px solid {self._bg_border}; }}"
        )
        self.title_label.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {self._fg}; background: transparent;")
        self.close_btn.setStyleSheet(
            f"/* onigiri-rounded-button-fix */\nQPushButton {{ background: transparent;"
            f" border: 1px solid transparent; border-radius: 14px; color: {self._muted}; font-size: 20px; }}"
            f" QPushButton:hover {{ color: {self._fg}; background: rgba(128,128,128,0.14);"
            f" border: 1px solid transparent; border-radius: 14px; }}"
        )
        xmark = _font_popup_svg_icon(system_icon_path("cancel.svg"), self._fg, 16)
        if not xmark.isNull():
            self.close_btn.setIcon(xmark)
            self.close_btn.setIconSize(QSize(16, 16))
            self.close_btn.setText("")
        else:
            self.close_btn.setText("×")

        self.phrase_card.setStyleSheet(
            f"QFrame#StatsTitlePhraseCard {{ background: {self._surface};"
            f" border: 1px solid {self._border}; border-radius: 14px; }}"
        )
        self.phrase_label.setStyleSheet(
            f"background: transparent; border: none; color: {self._muted}; font-size: 11px;"
            f" font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;"
        )
        self.text_input.setStyleSheet(
            f"QLineEdit#StatsTitleInput {{ background: {self._bg}; color: {self._fg};"
            f" border: 1px solid {self._border}; border-radius: 10px; padding: 0 12px;"
            f" selection-background-color: {self._accent}; selection-color: #ffffff; }}"
            f" QLineEdit#StatsTitleInput:focus {{ border-color: {self._accent}; }}"
        )
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QWidget {{ background: transparent; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 2px 4px 0; }}
            QScrollBar::handle:vertical {{ background: {self._border}; border-radius: 4px; min-height: 24px; }}
            QScrollBar::handle:vertical:hover {{ background: {self._muted}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            QScrollBar:horizontal {{ height: 0; }}
        """)
        self.add_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(128,128,128,0.10); color: {self._fg};"
            f" border: 1px solid {self._border}; border-radius: 18px; padding: 0 18px; font-weight: 700; }}"
            f" QPushButton:hover {{ border-color: {self._accent}; }}"
            f" QPushButton:pressed {{ background: rgba(128,128,128,0.20); border-radius: 18px; }}"
        )
        hover = QColor(self._accent).lighter(110).name()
        pressed = QColor(self._accent).darker(110).name()
        self.save_btn.setStyleSheet(
            f"QPushButton {{ background: {self._accent}; color: #ffffff; border: none;"
            f" border-radius: 18px; padding: 0 20px; font-weight: 700; }}"
            f" QPushButton:hover {{ background: {hover}; }}"
            f" QPushButton:pressed {{ background: {pressed}; border-radius: 18px; }}"
        )
        for btn in (self.cancel_btn, self.reset_btn):
            btn.setStyleSheet(
                f"QPushButton {{ background: {self._surface}; color: {self._fg};"
                f" border: 1px solid {self._border}; border-radius: 18px; padding: 0 18px; }}"
                f" QPushButton:pressed {{ background: rgba(128,128,128,0.10); border-radius: 18px; }}"
            )
        self._style_counter()

    def _on_preview_mode_toggled(self, mode):
        self.preview_mode = mode
        self._dark = mode == "dark"
        self._apply_palette()
        self._style_chrome()
        self._render_gallery()

    # ── Phrase input ────────────────────────────────────────────────────────
    def _on_text_changed(self, text):
        # Clamping only kicks in once a word past the cap actually exists, so
        # typing spaces between the first ten words still works.
        if stats_title_word_count(text) > STATS_TITLE_MAX_WORDS:
            text = clamp_stats_title(text)
            self.text_input.blockSignals(True)
            self.text_input.setText(text)
            self.text_input.setCursorPosition(len(text))
            self.text_input.blockSignals(False)
        self.current_text = text
        self._style_counter()
        self._apply_input_font()

    def _style_counter(self):
        count = stats_title_word_count(self.current_text)
        self.counter_label.setText(
            tr("stats_title_word_count", "{count} / {max} words").format(
                count=count, max=STATS_TITLE_MAX_WORDS
            )
        )
        at_limit = count >= STATS_TITLE_MAX_WORDS
        color = self._accent if at_limit else self._muted
        self.counter_label.setStyleSheet(
            f"background: transparent; border: none; color: {color}; font-size: 11px;"
            f" font-weight: {'700' if at_limit else '500'};"
        )

    def _apply_input_font(self):
        font = QFont()
        family = self._family_for_key(self._effective_font_key())
        if family:
            font.setFamily(family)
        font.setPixelSize(20)
        font.setBold(True)
        self.text_input.setFont(font)

    def _effective_font_key(self):
        """The font actually used to draw the title — "sync" defers to the
        Titles font set on the Fonts page."""
        if self.current_key == STATS_TITLE_SYNC_KEY:
            return mw.col.conf.get("onigiri_font_subtle", "system") or "system"
        return self.current_key

    # ── Gallery ─────────────────────────────────────────────────────────────
    def _ordered_font_keys(self):
        all_fonts = get_all_fonts(self.addon_path)
        preferred = ["system", "instrument_serif", "nunito", "montserrat", "space_mono", "silkscreen"]
        official = [k for k in preferred if k in all_fonts]
        official += [k for k in all_fonts if not all_fonts[k].get("user") and k not in official]
        user = sorted(k for k, info in all_fonts.items() if info.get("user"))
        return all_fonts, official, user

    def _render_gallery(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cell_widgets = {}

        all_fonts, official, user = self._ordered_font_keys()

        self._add_group_label(tr("stats_title_font", "Title Font"))
        self.content_layout.addWidget(self._sync_cell())

        self._add_group_label(tr("official_fonts", "Official Fonts"))
        for key in official:
            self.content_layout.addWidget(self._font_cell(key, all_fonts[key], deletable=False))

        self._add_group_label(tr("your_fonts", "Your Fonts"))
        if user:
            for key in user:
                self.content_layout.addWidget(self._font_cell(key, all_fonts[key], deletable=True))
        else:
            hint = QLabel(tr("no_user_fonts", "No custom fonts yet. Use “Add Your Own Font” below."))
            hint.setWordWrap(True)
            hint.setStyleSheet(f"color: {self._muted}; background: transparent; font-size: 12px; padding: 2px 4px;")
            self.content_layout.addWidget(hint)

        self.content_layout.addStretch()
        self._apply_input_font()

    def _add_group_label(self, text):
        label = QLabel(text)
        label.setStyleSheet(
            f"background: transparent; color: {self._muted}; font-size: 11px;"
            f" font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px;"
        )
        self.content_layout.addWidget(label)

    def _cell_style(self, selected):
        if selected:
            c = QColor(self._accent)
            bg = f"rgba({c.red()}, {c.green()}, {c.blue()}, 0.14)"
            border = self._accent
        else:
            bg = self._surface
            border = self._border
        return (
            f"QFrame#TitleFontCell {{ background: {bg}; border: 1px solid {border}; border-radius: 14px; }}"
            f" QFrame#TitleFontCell:hover {{ border-color: {self._accent}; }}"
        )

    def _new_cell(self, key, name, sample_text, sample_font_key):
        cell = _TitleFontCell(key, self._select_font)
        cell.setObjectName("TitleFontCell")
        cell.setStyleSheet(self._cell_style(key == self.current_key))
        cell.setMinimumHeight(74)

        row = QHBoxLayout(cell)
        row.setContentsMargins(16, 10, 12, 10)
        row.setSpacing(14)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(4)
        name_label = QLabel(name)
        name_label.setStyleSheet(f"background: transparent; border: none; color: {self._muted}; font-size: 11px; font-weight: 700;")
        sample_label = QLabel(sample_text)
        sample_label.setStyleSheet(f"background: transparent; border: none; color: {self._fg};")
        sample_label.setFont(self._sample_font(sample_font_key))
        text_col.addWidget(name_label)
        text_col.addWidget(sample_label)
        row.addLayout(text_col, 1)

        check = QLabel()
        check.setFixedSize(22, 22)
        check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        check.setStyleSheet("background: transparent; border: none;")
        if key == self.current_key:
            check_icon = _font_popup_svg_pixmap(
                system_icon_path("check-simple.svg"), self._accent, 18,
                self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0,
            )
            if not check_icon.isNull():
                check.setPixmap(check_icon)
        row.addWidget(check, 0, Qt.AlignmentFlag.AlignVCenter)

        self._cell_widgets[key] = cell
        return cell, row

    def _sample_text(self):
        text = (self.current_text or DEFAULTS["statsTitle"]).strip()
        return text[:22] if text else DEFAULTS["statsTitle"]

    def _sync_cell(self):
        cell, _row = self._new_cell(
            STATS_TITLE_SYNC_KEY,
            tr("stats_title_font_sync", "Sync with Title font"),
            self._sample_text(),
            mw.col.conf.get("onigiri_font_subtle", "system") or "system",
        )
        return cell

    def _font_cell(self, key, info, deletable):
        name = tr("system") if key == "system" else info.get("name", key)
        cell, row = self._new_cell(key, name, self._sample_text(), key)

        if deletable:
            del_btn = QPushButton()
            del_btn.setFixedSize(24, 24)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setToolTip(tr("delete", "Delete"))
            del_btn.setStyleSheet(
                f"/* onigiri-rounded-button-fix */\nQPushButton {{ background: transparent;"
                f" border: 1px solid transparent; border-radius: 12px; color: {self._muted}; }}"
                f" QPushButton:hover {{ background: rgba(239,68,68,0.16); color: #ef4444;"
                f" border: 1px solid transparent; border-radius: 12px; }}"
            )
            trash = _font_popup_svg_icon(system_icon_path("trash.svg"), self._muted, 14)
            if not trash.isNull():
                del_btn.setIcon(trash)
                del_btn.setIconSize(QSize(14, 14))
            else:
                del_btn.setText("−")
            del_btn.clicked.connect(lambda _=False, k=key: self._delete_user_font(k))
            row.addWidget(del_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return cell

    def _sample_font(self, key):
        family = self._family_for_key(key)
        font = QFont()
        if family:
            font.setFamily(family)
        font.setPixelSize(24)
        font.setBold(True)
        return font

    def _family_for_key(self, key):
        if key in ("system", STATS_TITLE_SYNC_KEY):
            return ""
        if key in self._family_cache:
            return self._family_cache[key]
        info = get_all_fonts(self.addon_path).get(key, {})
        font_file = info.get("file")
        if not font_file:
            family = info.get("family", "")
            self._family_cache[key] = family
            return family
        if info.get("user"):
            path = os.path.join(self.addon_path, "user_files", "fonts", font_file)
        else:
            path = os.path.join(self.addon_path, "system_files", "fonts", "system_fonts", font_file)
        if not os.path.exists(path):
            family = info.get("family", "")
            self._family_cache[key] = family
            return family
        font_id = QFontDatabase.addApplicationFont(path)
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id != -1 else []
        family = families[0] if families else info.get("family", "")
        self._family_cache[key] = family
        return family

    # ── Selection / actions ────────────────────────────────────────────────
    def _select_font(self, key):
        if self.current_key == key:
            return
        self.current_key = key
        # Re-render so the checkmark moves to the freshly selected card.
        self._render_gallery()

    def _save_and_close(self):
        self.titleAccepted.emit(
            clamp_stats_title(self.text_input.text()),
            self.current_key or STATS_TITLE_SYNC_KEY,
        )
        self.accept()

    def _reset_to_default(self):
        self.titleAccepted.emit(DEFAULTS["statsTitle"], STATS_TITLE_SYNC_KEY)
        self.accept()

    def _add_user_font(self):
        user_fonts_dir = os.path.join(self.addon_path, "user_files", "fonts")
        os.makedirs(user_fonts_dir, exist_ok=True)
        filepath, _ = QFileDialog.getOpenFileName(
            self, tr("add_your_font", "Add Your Own Font"), "",
            "Font Files (*.ttf *.otf *.woff *.woff2)",
        )
        if not filepath:
            return
        filename = os.path.basename(filepath)
        dest_path = os.path.join(user_fonts_dir, filename)
        try:
            shutil.copy(filepath, dest_path)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not copy font file: {e}")
            return
        self._family_cache.pop(filename, None)
        # Select the newly added font so its preview is front and centre.
        self.current_key = filename
        self._render_gallery()

    def _delete_user_font(self, key):
        info = get_all_fonts(self.addon_path).get(key, {})
        display = info.get("name", key)
        reply = QMessageBox.question(
            self, tr("delete", "Delete"),
            tr("delete_font_confirm", "Delete the font '{name}'? This cannot be undone.").format(name=display),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        font_path = os.path.join(self.addon_path, "user_files", "fonts", key)
        try:
            if os.path.exists(font_path):
                os.remove(font_path)
        except OSError as e:
            QMessageBox.warning(self, "Error", f"Could not delete font file: {e}")
            return
        self._family_cache.pop(key, None)
        if self.current_key == key:
            self.current_key = STATS_TITLE_SYNC_KEY
        self._render_gallery()
