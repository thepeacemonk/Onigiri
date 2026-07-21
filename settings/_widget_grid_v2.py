# -*- coding: utf-8 -*-
"""
Anki-facing wiring for the new iOS-style Widget Grid.

`WidgetGridEditorV2` is a drop-in replacement for the old `UnifiedLayoutEditor`.
It builds widget specs from translations + config, drives the animated grid in
`_widget_grid_core`, and serialises back to the *exact* config contract that
`onigiri_renderer.py` already reads:

    current_config["onigiriWidgetLayout"] = {
        "grid": {wid: {"pos", "row", "col", "display_name", "orientation"?}},
        "archive": {wid: {"display_name", ...}},
        "column_count", "grid_width", "grid_alignment", "widget_height",
    }
    current_config["externalWidgetLayout"] = {
        "grid": {hook: {"grid_position", "row_span", "column_span", "display_name"}},
        "archive": {hook: {"display_name"}},
    }
    current_config["unifiedGridRows"] = <int>

Plus one new, settings-only key that the renderer ignores:

    current_config["externalWidgetIdentity"] = {hook: {"color", "icon"}}
"""

from ._common import *
from ._widget_grid_core import (
    Palette, WidgetSpec, iOSGridCanvas, WidgetGalleryDialog,
)
from ._widgets import show_settings_toast


class _HoldResetButton(QPushButton):
    """Pill button that only fires after the user holds it down.

    A short click does nothing; the caller-supplied action runs when the
    press is held for ``HOLD_MS`` milliseconds. A fill animates left→right
    while held so the user can see progress toward the trigger.
    """

    longPressed = pyqtSignal()
    HOLD_MS = 850
    TICK_MS = 16

    def __init__(self, text, bg, hover_bg, border, fg, active_fg, fill, parent=None):
        super().__init__(text, parent)
        self._bg = QColor(bg)
        self._hover_bg = QColor(hover_bg)
        self._border = QColor(border)
        self._fg = QColor(fg)
        self._active_fg = QColor(active_fg)
        self._fill = QColor(fill)
        self._progress = 0.0
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(38)
        f = self.font()
        f.setPointSizeF(max(9.0, f.pointSizeF()))
        f.setBold(True)
        self.setFont(f)
        self._timer = QTimer(self)
        self._timer.setInterval(self.TICK_MS)
        self._timer.timeout.connect(self._tick)

    def sizeHint(self):
        base = super().sizeHint()
        return QSize(base.width() + 44, max(38, base.height()))

    # --- interaction -------------------------------------------------- #
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._progress = 0.0
            self._timer.start()
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._cancel()
        super().mouseReleaseEvent(ev)

    def enterEvent(self, ev):
        self._hovered = True
        self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._hovered = False
        self._cancel()
        super().leaveEvent(ev)

    def _cancel(self):
        if self._timer.isActive() or self._progress:
            self._timer.stop()
            self._progress = 0.0
            self.update()

    def _tick(self):
        self._progress = min(1.0, self._progress + self.TICK_MS / self.HOLD_MS)
        if self._progress >= 1.0:
            self._timer.stop()
            self._progress = 0.0
            self.update()
            self.longPressed.emit()
        else:
            self.update()

    # --- paint -------------------------------------------------------- #
    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2.0
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        base = self._hover_bg if (self._hovered or self._progress) else self._bg
        p.fillPath(path, base)

        if self._progress > 0.0:
            p.save()
            p.setClipPath(path)
            fill = QColor(self._fill)
            fill.setAlpha(70)
            fw = rect.width() * self._progress
            p.fillRect(QRectF(rect.left(), rect.top(), fw, rect.height()), fill)
            p.restore()

        pen = QPen(self._border)
        pen.setWidthF(1.0)
        p.strokePath(path, pen)

        p.setFont(self.font())
        p.setPen(self._active_fg if (self._hovered or self._progress) else self._fg)
        p.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), self.text())
        p.end()


class _TileMenu(QWidget):
    """Frameless popup that replaces the old QMenu tile context menu.

    One rounded card: labelled chip rows for the spans (no submenus, so a
    span is one click instead of three), then full-width action pills.
    Everything is plain QSS, so hover / light / dark states come from the
    palette with no per-frame painting.
    """

    CHIP = 26

    def __init__(self, pal, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.pal = pal
        # Translucent so the card's rounded corners aren't boxed in by the
        # window background (there is no shadow/outline behind it).
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame(self)
        card.setObjectName("tileMenuCard")
        outer.addWidget(card)

        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(7, 7, 7, 7)
        card_l.setSpacing(0)

        # Page 0 = actions, page 1 = inline rename. The stack keeps one size
        # for both pages, so switching never resizes or moves the popup.
        self._stack = QStackedWidget(card)
        card_l.addWidget(self._stack)

        self._main_page = QWidget()
        self._body = QVBoxLayout(self._main_page)
        self._body.setContentsMargins(0, 0, 0, 0)
        self._body.setSpacing(4)
        self._stack.addWidget(self._main_page)

        self.setStyleSheet(self._qss())

    def _show_page(self, page):
        """Switch pages and shrink the popup to that page only (hidden pages
        are size-ignored, so the card never carries dead space)."""
        self._stack.setCurrentWidget(page)
        for i in range(self._stack.count()):
            w = self._stack.widget(i)
            w.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Preferred if w is page else QSizePolicy.Policy.Ignored)
        self._stack.adjustSize()
        self.adjustSize()

    # --- style --------------------------------------------------------- #
    def _qss(self):
        pal = self.pal
        dark = pal.is_dark
        # Matches the settings dialog: --canvas-inset over --highlight-bg.
        card = "#242424" if dark else "#ffffff"
        chip = "#303030" if dark else "#f2f2f2"
        chip_hover = "#3a3a3a" if dark else "#e9e9e9"
        accent = pal.accent.name()
        return f"""
            #tileMenuCard {{
                background: {card};
                border: none;
                border-radius: 12px;
            }}
            QLabel#tileMenuLabel {{
                color: {pal.muted.name()};
                font-size: 10px;
                font-weight: 600;
                padding: 1px 2px 0px 2px;
            }}
            QPushButton {{
                background: {chip};
                border: none;
                color: {pal.fg.name()};
                font-size: 12px;
                font-weight: 600;
                min-height: {self.CHIP}px;
            }}
            QPushButton:hover {{ background: {chip_hover}; }}
            QPushButton#tileChip {{ border-radius: 8px; min-width: {self.CHIP}px; }}
            QPushButton#tileChip:checked {{
                background: {accent};
                color: {_readable_hex(accent)};
            }}
            QPushButton#tileAction {{
                border-radius: 8px;
                padding: 0px 10px;
                font-weight: 500;
                text-align: center;
            }}
            QPushButton#tilePrimary {{
                border-radius: 8px;
                padding: 0px 10px;
                background: {accent};
                color: {_readable_hex(accent)};
            }}
            QPushButton#tilePrimary:hover {{ background: {_shade(accent, 0.9)}; }}
            QLineEdit#tileRename {{
                background: {chip};
                border: none;
                border-radius: 8px;
                padding: 0px 9px;
                min-height: {self.CHIP}px;
                color: {pal.fg.name()};
                font-size: 12px;
                selection-background-color: {accent};
                selection-color: {_readable_hex(accent)};
            }}
        """

    # --- builders ------------------------------------------------------- #
    def _label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("tileMenuLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        return lbl

    def add_chips(self, label, options, current, on_pick):
        """options: list of (value, text). Fires on_pick(value) and closes."""
        self._body.addWidget(self._label(label))
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        group = QButtonGroup(holder)
        group.setExclusive(True)
        for value, text in options:
            btn = QPushButton(str(text))
            btn.setObjectName("tileChip")
            btn.setCheckable(True)
            btn.setChecked(value == current)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _c, v=value: self._fire(on_pick, v))
            group.addButton(btn)
            row.addWidget(btn)
        self._body.addWidget(holder)

    def add_action(self, text, callback):
        btn = QPushButton(text)
        btn.setObjectName("tileAction")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _c=False: self._fire(callback))
        self._body.addWidget(btn)

    def add_rename(self, label, current, on_accept):
        """Adds a Rename action that swaps the popup to an inline text field."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(self._label(label))
        edit = QLineEdit(current)
        edit.setObjectName("tileRename")
        edit.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(edit)

        save = QPushButton(tr("save", "Save"))
        save.setObjectName("tilePrimary")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        commit = lambda: self._fire(on_accept, edit.text().strip())
        save.clicked.connect(lambda _c=False: commit())
        edit.returnPressed.connect(commit)
        lay.addWidget(save)

        back = QPushButton(tr("cancel", "Cancel"))
        back.setObjectName("tileAction")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(lambda _c=False: self._show_page(self._main_page))
        lay.addWidget(back)

        self._stack.addWidget(page)

        def open_rename():
            self._show_page(page)
            edit.setFocus(Qt.FocusReason.OtherFocusReason)
            edit.deselect()
            edit.setCursorPosition(len(edit.text()))

        btn = QPushButton(label)
        btn.setObjectName("tileAction")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _c=False: open_rename())
        self._body.addWidget(btn)

    def _fire(self, callback, *args):
        self.close()
        # Deferred: the popup still holds the mouse grab, and a dialog opened
        # from inside it would inherit that.
        QTimer.singleShot(0, lambda: callback(*args))

    # --- placement ------------------------------------------------------ #
    def popup_at(self, global_pos):
        self._show_page(self._main_page)   # always open on the action list
        self.adjustSize()
        x, y = global_pos.x() - 12, global_pos.y() - 10
        screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = max(geo.left(), min(x, geo.right() - self.width()))
            y = max(geo.top(), min(y, geo.bottom() - self.height()))
        self.move(int(x), int(y))
        self.show()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(ev)


# --------------------------------------------------------------------------- #
#  Onigiri widget catalogue                                                   #
# --------------------------------------------------------------------------- #
#  (wid, preview, default(rows,cols), min(rows,cols), max(rows,cols), fixed_rows)
_ONIGIRI_CATALOGUE = [
    ("stats_title",       "title",     (1, 4), (1, 1), (1, 4), 1),
    ("studied",           "stat",      (1, 1), (1, 1), (1, 4), None),
    ("time",              "stat",      (1, 1), (1, 1), (1, 4), None),
    ("pace",              "stat",      (1, 1), (1, 1), (1, 4), None),
    ("retention",         "ring",      (1, 1), (1, 1), (1, 4), None),
    ("heatmap",           "heatmap",   (2, 4), (2, 2), (2, 4), 2),
    ("favorites",         "favorites", (1, 1), (1, 1), (3, 2), None),
    ("restaurant_level",  "level",     (2, 2), (1, 1), (2, 2), None),
    ("onigimon",          "companion", (2, 1), (1, 1), (4, 2), None),
    ("hexagon_land",      "island",    (2, 2), (1, 1), (4, 4), None),
    ("deck_stats",        "deckstats", (2, 1), (1, 1), (2, 2), None),
    ("prep_station",      "plans",     (2, 2), (2, 1), (2, 4), 2),
    ("hashi_notes",       "notes",     (2, 2), (1, 1), (4, 4), None),
]


def _onigiri_name(wid):
    names = {
        "stats_title": tr("stats_title", "Stats Title"),
        "studied": tr("widget_studied", "Studied"),
        "time": tr("widget_time", "Time"),
        "pace": tr("widget_pace", "Pace"),
        "retention": tr("widget_retention", "Retention"),
        "heatmap": tr("widget_heatmap", "Heatmap"),
        "favorites": tr("widget_favorites", "Favorites"),
        "restaurant_level": tr("widget_restaurant_level", "Nook Level"),
        "onigimon": "Onigimon",
        "hexagon_land": "Hexagon Land",
        "deck_stats": "Deck Stats",
        "prep_station": tr("widget_study_plans", "Study Plans"),
        "hashi_notes": tr("hashi_notes_title", "Hashi Notes"),
    }
    return names.get(wid, wid)


class WidgetGridEditorV2(QWidget):
    """The rebuilt Widget Grid page. Public API mirrors UnifiedLayoutEditor:
    `get_layout_config()` and `_applied_row_count`."""

    _HEADER_BTN_HEIGHT = 40

    def __init__(self, settings_dialog):
        super().__init__()
        self.settings_dialog = settings_dialog
        self._identity = dict(settings_dialog.current_config.get("externalWidgetIdentity", {}) or {})
        self._specs = {}          # wid -> WidgetSpec (every known widget)
        self._applied_row_count = 6

        # Coalesces rapid Columns/Rows edits into a single grid rebuild so the
        # canvas resizes once (no collapse/expand flicker of the settings above).
        self._pending_cols = None
        self._pending_rows = None
        self._grid_timer = QTimer(self)
        self._grid_timer.setSingleShot(True)
        self._grid_timer.setInterval(60)
        self._grid_timer.timeout.connect(self._apply_pending_grid)

        self.pal = self._build_palette()
        self._build_specs()
        self._build_ui()
        self._load_saved_layout()

    # ------------------------------------------------------------------ #
    #  Palette                                                            #
    # ------------------------------------------------------------------ #
    def _build_palette(self):
        c = self.settings_dialog._layout_editor_style_colors()
        return Palette(
            is_dark=theme_manager.night_mode,
            accent=c.get("accent", "#00A982"),
            fg=c.get("fg"),
            card=c.get("button_bg"),
            border=c.get("border"),
        )

    # ------------------------------------------------------------------ #
    #  Spec construction                                                  #
    # ------------------------------------------------------------------ #
    def _build_specs(self):
        title_sample = ""
        try:
            title_sample = self.settings_dialog.stats_title_input.text()
        except Exception:
            title_sample = ""
        stat_extras = {
            "stats_title": {"value": title_sample or tr("stats_title", "Stats Title")},
            "studied": {"label": tr("studied", "studied"), "value": "128",
                        "unit": tr("cards", "cards")},
            "time": {"label": tr("time", "time"), "value": "42",
                     "unit": tr("minutes_unit", "min")},
            "pace": {"label": tr("pace", "pace"), "value": "19",
                     "unit": tr("seconds_unit", "s") + "/" + tr("card", "card")},
            "retention": {"label": tr("widget_retention", "retention")},
        }
        for wid, preview, ds, mn, mx, fixed in _ONIGIRI_CATALOGUE:
            # Onigiri tiles are plain name-cards: no identity colour/icon.
            self._specs[wid] = WidgetSpec(
                wid, _onigiri_name(wid), kind="onigiri", preview=preview,
                default_span=ds, min_span=mn, max_span=mx, fixed_rows=fixed,
                extra=dict(stat_extras.get(wid, {})),
            )
        self._build_external_specs()

    def _build_external_specs(self):
        from .. import patcher
        seen = set()

        def add_external(wid, name, kind="external", declared_color=None):
            if wid in seen:
                return
            seen.add(wid)
            ident = self._identity.get(wid, {})
            # Colour drives the tile's thin identity bar on the grid.
            color = ident.get("color") or declared_color or self._auto_color(wid)
            spec = WidgetSpec(
                wid, name, kind=kind, preview="identity", has_preview=False,
                default_span=(2, 1), min_span=(2, 1), max_span=(4, 4),
                color=color,
            )
            self._specs[wid] = spec

        # Detected hooks from other add-ons.
        try:
            hooks = self.settings_dialog._get_external_hooks()
        except Exception:
            hooks = []
        for hook_id in hooks:
            if "learner_stats_widget" in hook_id:
                continue
            pkg = hook_id.split(".")[0]
            try:
                name = mw.addonManager.addonName(pkg)
            except Exception:
                name = pkg
            name = patcher.get_external_hook_display_name(hook_id, name or pkg)
            add_external(hook_id, name or pkg)

        # Bento-registered widgets (declared identity if the add-on provided it).
        # The overview renderer only draws hook-backed widgets: grid entries are
        # looked up by hook id. A Bento id that is not a hook id can never render,
        # so listing it produces a duplicate/ghost tile in the gallery.
        hook_ids = set(hooks)
        try:
            from ..api import bento as bento_api
            for aid, meta in (bento_api.get_bento_widgets() or {}).items():
                if aid not in hook_ids:
                    continue
                nm = (meta or {}).get("name") or aid
                add_external(aid, nm, kind="bento",
                             declared_color=(meta or {}).get("color"))
        except Exception:
            pass

    def _auto_color(self, wid):
        # Deterministic pleasant colour from the id, used until the user picks one.
        palette = ["#E0A400", "#4064E0", "#20A0C0", "#E0567A", "#7A56E0",
                   "#2FA968", "#E07B3A", "#3AA0E0"]
        return palette[abs(hash(wid)) % len(palette)]

    # ------------------------------------------------------------------ #
    #  UI                                                                 #
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        # --- Grid settings (compact) ---
        panel = QFrame()
        panel.setObjectName("organizeCompactPanel")
        # Fixed vertical policy: a canvas resize below must never squeeze the
        # settings block (was causing it to collapse/expand on edit).
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        try:
            panel.setStyleSheet(self.settings_dialog._organize_compact_stylesheet())
        except Exception:
            pass
        panel_l = QVBoxLayout(panel)
        panel_l.setContentsMargins(0, 4, 0, 4)
        panel_l.setSpacing(0)

        def add_row(label, control):
            if isinstance(control, QAbstractSpinBox):
                control.setObjectName("organizeCompactSpinBox")
                control.setFixedHeight(30)
            return self.settings_dialog._create_organize_compact_row(
                str(label).strip().rstrip(":"), control)

        def wrap_left(control):
            # Container tagged organizeSegmentShell so _create_organize_compact_row
            # left-aligns it (under the pill controls) instead of right-filling.
            box = QWidget()
            box.setObjectName("organizeSegmentShell")
            lay = QHBoxLayout(box)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            lay.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
            return box

        def unit_pill(spin, width):
            # Mirrors the Fonts page: the number sits on the left of the pill and
            # the unit label is pinned to the right edge (instead of a spinbox
            # suffix glued to the digits).
            spin.setObjectName("gridUnitSpinBox")
            spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            spin.setFrame(False)
            spin.setFixedHeight(28)
            spin.setStyleSheet(
                "QSpinBox#gridUnitSpinBox { background: transparent; border: none; "
                f"padding: 0; color: {self.pal.fg.name()}; }}"
            )

            pill = QFrame()
            pill.setObjectName("gridUnitPill")
            pill.setFixedHeight(30)
            pill.setFixedWidth(width)
            pill.setStyleSheet(
                "QFrame#gridUnitPill { background: %s; border: 1px solid %s; "
                "border-radius: 15px; }" % (self.pal.card.name(), self.pal.border.name())
            )
            lay = QHBoxLayout(pill)
            lay.setContentsMargins(12, 0, 12, 0)
            lay.setSpacing(2)

            unit = QLabel("px")
            unit.setStyleSheet(
                f"color: {self.pal.muted.name()}; background: transparent; font-size: 12px;")

            lay.addWidget(spin, 1)
            lay.addWidget(unit, 0, Qt.AlignmentFlag.AlignVCenter)

            box = QWidget()
            box.setObjectName("organizeSegmentShell")
            box_l = QHBoxLayout(box)
            box_l.setContentsMargins(0, 0, 0, 0)
            box_l.setSpacing(0)
            box_l.addWidget(pill, 0, Qt.AlignmentFlag.AlignVCenter)
            return box

        conf = self.settings_dialog.current_config.get("onigiriWidgetLayout", {}) or {}

        # Shared style for pill spinboxes
        pill_style = f"""
            QSpinBox {{
                background: {self.pal.card.name()};
                border: 1px solid {self.pal.border.name()};
                border-radius: 17px;
                color: {self.pal.fg.name()};
                button-symbols: no-indicator;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 0px;
                border: none;
                background: transparent;
            }}
        """
        # Selected pill: value not representable in the 2-6 segmented control,
        # so the little box lights up (acts as the active selector).
        self._spin_plain_style = pill_style
        self._spin_selected_style = f"""
            QSpinBox {{
                background: {self.pal.accent.name()};
                border: 1px solid {self.pal.accent.name()};
                border-radius: 17px;
                color: #ffffff;
                button-symbols: no-indicator;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 0px;
                border: none;
                background: transparent;
            }}
        """

        # Columns segmented control (2-6)
        self.col_group = QButtonGroup(self)
        self.col_group.setExclusive(True)
        current_cols = _clamp_int(conf.get("column_count", 4), 1, 60, 4)
        
        cols_seg_container = self.settings_dialog._create_organize_segmented_control(
            [(str(i), str(i)) for i in range(2, 7)],
            self.col_group, str(current_cols) if 2 <= current_cols <= 6 else "", "cols",
            fill_width=False, segment_height=26, min_button_width=40,
        )
        cols_seg_container.setFixedHeight(34)
        self._cols_shell = cols_seg_container
        self.col_group.buttonClicked.connect(self._on_columns_button_clicked)

        self.col_spin = QSpinBox()
        self.col_spin.setRange(1, 60)
        self.col_spin.setValue(current_cols)
        self.col_spin.setFixedHeight(26)
        self.col_spin.setFixedWidth(40)
        self.col_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.col_spin.setStyleSheet(pill_style)
        # Apply only on Enter / focus-out, not on every keystroke (avoids the
        # grid rebuilding mid-typing when a multi-digit value is entered).
        self.col_spin.setKeyboardTracking(False)
        self.col_spin.valueChanged.connect(self._on_columns_spin_changed)
        self._set_spin_selected(self.col_spin, not (2 <= current_cols <= 6))

        col_container = QWidget()
        col_container.setObjectName("organizeSegmentShell")
        col_layout = QHBoxLayout(col_container)
        col_layout.setContentsMargins(0, 0, 0, 0)
        col_layout.setSpacing(8)
        col_layout.addWidget(cols_seg_container, 0)
        col_layout.addWidget(self.col_spin, 0, Qt.AlignmentFlag.AlignVCenter)
        # Width of the whole "Number of Columns" control; reused below so
        # Widget Height / Grid Width / Grid Alignment line up to the same width.
        cols_width = col_container.sizeHint().width()
        cols_row = add_row(tr("unified_grid_cols", "Columns"), col_container)

        # Rows segmented control
        self.row_group = QButtonGroup(self)
        self.row_group.setExclusive(True)
        # Saved at the top level of current_config (not inside onigiriWidgetLayout,
        # which is what `conf` points at here).
        current_rows = _clamp_int(
            self.settings_dialog.current_config.get("unifiedGridRows", 6), 1, 60, 6)
        
        row_seg_container = self.settings_dialog._create_organize_segmented_control(
            [(str(i), str(i)) for i in range(2, 7)],
            self.row_group, str(current_rows) if 2 <= current_rows <= 6 else "", "rows",
            fill_width=False, segment_height=26, min_button_width=40,
        )
        row_seg_container.setFixedHeight(34)
        self._rows_shell = row_seg_container
        self.row_group.buttonClicked.connect(self._on_rows_button_clicked)
        
        self.row_spin = QSpinBox()
        self.row_spin.setRange(1, 60)
        self.row_spin.setValue(current_rows)
        self.row_spin.setFixedHeight(26)
        self.row_spin.setFixedWidth(40)
        self.row_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.row_spin.setStyleSheet(pill_style)
        self.row_spin.setKeyboardTracking(False)
        self.row_spin.valueChanged.connect(self._on_rows_spin_changed)
        self._set_spin_selected(self.row_spin, not (2 <= current_rows <= 6))

        row_container = QWidget()
        row_container.setObjectName("organizeSegmentShell")
        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(row_seg_container, 0)
        row_layout.addWidget(self.row_spin, 0, Qt.AlignmentFlag.AlignVCenter)
        rows_row = add_row(tr("unified_grid_rows", "Rows"), row_container)

        # Alignment (kept with Columns/Rows at the top of the panel)
        self.align_group = QButtonGroup(self)
        self.align_group.setExclusive(True)
        current_align = conf.get("grid_alignment", "center")
        align_container = self.settings_dialog._create_organize_segmented_control(
            [("left", tr("align_left", "Left")),
             ("center", tr("align_center", "Center")),
             ("right", tr("align_right", "Right"))],
            self.align_group, current_align, "grid_alignment",
            fill_width=True, segment_height=26, min_button_width=64,
        )
        align_container.setFixedHeight(34)
        # Spans the full panel width (both columns) instead of a fixed pill width.
        align_row = add_row(tr("grid_alignment_label", "Grid Alignment"), align_container)

        # Widget height
        self.widget_height_spin = QSpinBox()
        self.widget_height_spin.setRange(120, 320)
        self.widget_height_spin.setValue(_clamp_int(conf.get("widget_height", 120), 120, 320, 120))
        self.widget_height_spin.valueChanged.connect(self._on_widget_height_changed)
        height_row = add_row(tr("widget_height_label", "Widget Height"),
                             unit_pill(self.widget_height_spin, cols_width))

        # Grid width
        self.grid_width_spin = QSpinBox()
        self.grid_width_spin.setRange(200, 340)
        self.grid_width_spin.setValue(_clamp_int(conf.get("grid_width", 230), 200, 340, 230))
        width_row = add_row(tr("grid_width_label", "Grid Width"),
                            unit_pill(self.grid_width_spin, cols_width))

        # Two columns (Columns/Rows | Widget Height/Grid Width) + full-width
        # Grid Alignment centered below.
        two_col = QHBoxLayout()
        two_col.setContentsMargins(0, 0, 0, 0)
        two_col.setSpacing(8)

        left_settings = QVBoxLayout()
        left_settings.setContentsMargins(0, 0, 0, 0)
        left_settings.setSpacing(0)
        left_settings.addWidget(cols_row)
        left_settings.addWidget(rows_row)

        right_settings = QVBoxLayout()
        right_settings.setContentsMargins(0, 0, 0, 0)
        right_settings.setSpacing(0)
        right_settings.addWidget(height_row)
        right_settings.addWidget(width_row)

        two_col.addLayout(left_settings, 1)
        two_col.addLayout(right_settings, 1)
        panel_l.addLayout(two_col)
        panel_l.addWidget(align_row)

        # --- Single card: title + action buttons header, settings, grid ---
        grid_group = QFrame(self)
        grid_group.setObjectName("LayoutGroup")
        grid_group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        main_layout = QVBoxLayout(grid_group)
        main_layout.setContentsMargins(14, 12, 14, 14)
        main_layout.setSpacing(10)

        # Header: single title on the left, action buttons on the right.
        header_top = QHBoxLayout()
        header_top.setContentsMargins(0, 0, 0, 0)
        header_top.setSpacing(10)
        title_label = QLabel(tr("widget_settings", "Widget settings"))
        title_label.setObjectName("LayoutGroupTitle")
        title_label.setWordWrap(True)
        header_top.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        header_top.addStretch()

        self.add_btn = QPushButton("＋  " + tr("add_widget", "Add Widget"))
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setStyleSheet(self._add_button_style())
        self.add_btn.setFixedHeight(self._HEADER_BTN_HEIGHT)
        self.add_btn.clicked.connect(self.open_gallery)
        header_top.addWidget(self.add_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        reset_btn = self._build_reset_button()
        reset_btn.setFixedHeight(self._HEADER_BTN_HEIGHT)
        header_top.addWidget(reset_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        main_layout.addLayout(header_top)
        main_layout.addWidget(panel)

        self.canvas = iOSGridCanvas(self.pal, rows=current_rows, cols=current_cols)
        self.canvas.cell_h = self._cell_height_for(self.widget_height_spin.value())
        self.canvas.empty_clicked.connect(self.open_gallery)
        self.canvas.context_requested.connect(self._on_tile_context)
        self.canvas.layout_changed.connect(self._on_layout_changed)
        main_layout.addWidget(self.canvas)
        root.addWidget(grid_group)

        root.addStretch()

    def _build_reset_button(self):
        try:
            palette = self.settings_dialog._settings_palette()
        except Exception:
            palette = {}
        night = theme_manager.night_mode
        bg = palette.get("--canvas-inset", "#242424" if night else "#ffffff")
        hover_bg = palette.get("--hover-bg", "#3a3a3a" if night else "#f2f2f2")
        border = palette.get("--border", "#454545" if night else "#dcdde1")
        fg = palette.get("--fg-subtle", "#b7bcc5" if night else "#6f7177")
        active_fg = palette.get("--fg", "#f4f4f5" if night else "#202124")
        btn = _HoldResetButton(
            tr("reset_layout_hold_btn", "Hold to Reset"),
            bg=bg, hover_bg=hover_bg, border=border, fg=fg,
            active_fg=active_fg, fill=self.pal.accent.name(),
        )
        btn.setToolTip(tr("reset_layout_hold_tip", "Press and hold to reset the layout"))
        btn.longPressed.connect(self.reset_layout)
        return btn

    def _add_button_style(self):
        accent = self.pal.accent.name()
        fg = _readable_hex(accent)
        radius = self._HEADER_BTN_HEIGHT // 2
        return (
            f"QPushButton{{background:{accent};color:{fg};border:none;"
            f"border-radius:{radius}px;padding:8px 16px;font-weight:700;font-size:13px;}}"
            f"QPushButton:hover{{background:{_shade(accent, 0.9)};}}"
            f"QPushButton:pressed{{background:{_shade(accent, 0.8)};border-radius:{radius}px;}}"
        )

    def _cell_height_for(self, widget_height):
        # Map the real widget height (120-320) to a comfortable preview cell.
        return int(max(52, min(96, widget_height * 0.42)))

    # ------------------------------------------------------------------ #
    #  Load / defaults                                                    #
    # ------------------------------------------------------------------ #
    def _default_layout(self):
        return {
            "grid": {
                "stats_title": {"pos": 0, "row": 1, "col": 4},
                "studied": {"pos": 4, "row": 1, "col": 1},
                "time": {"pos": 5, "row": 1, "col": 1},
                "pace": {"pos": 6, "row": 1, "col": 1},
                "retention": {"pos": 7, "row": 1, "col": 1},
                "heatmap": {"pos": 8, "row": 2, "col": 4},
            },
        }

    def _load_saved_layout(self):
        conf = self.settings_dialog.current_config
        onigiri = conf.get("onigiriWidgetLayout") or {}
        grid = onigiri.get("grid")
        if not isinstance(grid, dict) or not grid:
            grid = self._default_layout()["grid"]
        cols = self.canvas.cols

        entries = []  # (pos, wid, rs, cs, display_name, orientation)
        for wid, cfg in grid.items():
            if wid not in self._specs:
                continue
            pos = _clamp_int(cfg.get("pos", 0), 0, 10_000, 0)
            rs = _clamp_int(cfg.get("row", 1), 1, 8, 1)
            cs = _clamp_int(cfg.get("col", 1), 1, 6, 1)
            entries.append((pos, wid, rs, cs, cfg.get("display_name"),
                            cfg.get("orientation")))

        external = conf.get("externalWidgetLayout") or {}
        ext_grid, _ = _split_layout(external)
        for wid, cfg in ext_grid.items():
            if wid not in self._specs:
                continue
            pos = _clamp_int(cfg.get("grid_position", 0), 0, 10_000, 0)
            rs = _clamp_int(cfg.get("row_span", 2), 2, 8, 2)
            cs = _clamp_int(cfg.get("column_span", 1), 1, 6, 1)
            entries.append((pos, wid, rs, cs, cfg.get("display_name"), None))

        entries.sort(key=lambda e: e[0])
        for pos, wid, rs, cs, name, orientation in entries:
            spec = self._specs[wid]
            rs, cs = spec.clamp_span(rs, cs)
            row, col = pos // cols, pos % cols
            tile = self.canvas.add_spec(spec, animated=False, row=row, col=col,
                                        row_span=rs, col_span=cs)
            if name:
                tile.display_name = name
            if orientation:
                spec.extra["orientation"] = orientation
        self.canvas.relayout(animated=False)
        self._applied_row_count = max(self._current_row_value(), self.canvas.rows)

    # ------------------------------------------------------------------ #
    #  Gallery                                                            #
    # ------------------------------------------------------------------ #
    def open_gallery(self):
        onigiri_specs = [self._specs[wid] for wid, *_ in _ONIGIRI_CATALOGUE
                         if wid in self._specs and not self.canvas.has_widget(wid)]
        external_specs = [s for s in self._specs.values()
                          if s.kind in ("external", "bento")
                          and not self.canvas.has_widget(s.wid)]
        if not onigiri_specs and not external_specs:
            show_settings_toast(self.settings_dialog,
                                tr("gallery_all_added", "All widgets are already on the grid"))
            return
        strings = {
            "gallery_title": tr("gallery_title", "Widget Gallery"),
            "gallery_subtitle": tr("gallery_subtitle", "Tap a widget to drop it onto your grid"),
            "gallery_onigiri": tr("gallery_onigiri", "Onigiri Widgets"),
            "gallery_external": tr("gallery_external", "External Add-ons"),
        }
        dlg = WidgetGalleryDialog(self.pal, onigiri_specs, external_specs,
                                  strings=strings, parent=self.settings_dialog)
        dlg.widget_chosen.connect(self._on_widget_chosen)
        dlg.exec()

    def _on_widget_chosen(self, spec):
        self.canvas.add_spec(spec, animated=True)
        self._on_layout_changed()

    # ------------------------------------------------------------------ #
    #  Context menu                                                       #
    # ------------------------------------------------------------------ #
    def _on_tile_context(self, tile, global_pos):
        spec = tile.spec
        menu = _TileMenu(self.pal, self.settings_dialog)

        rmin, cmin = spec.min_span
        rmax, cmax = spec.max_span

        # Columns
        cmax_eff = min(cmax, self.canvas.cols)
        if cmax_eff > cmin:
            menu.add_chips(
                tr("widget_menu_columns", "Columns"),
                [(i, i) for i in range(cmin, cmax_eff + 1)],
                tile.col_span,
                lambda n: self._set_span(tile, tile.row_span, n))

        # Rows
        if not spec.fixed_rows and rmax > rmin:
            menu.add_chips(
                tr("widget_menu_rows", "Rows"),
                [(i, i) for i in range(rmin, rmax + 1)],
                tile.row_span,
                lambda n: self._set_span(tile, n, tile.col_span))

        # Nook orientation
        if spec.wid == "restaurant_level":
            menu.add_chips(
                tr("widget_menu_orientation", "Orientation"),
                [("horizontal", tr("orientation_side_by_side", "Side by Side")),
                 ("vertical", tr("orientation_image_top", "Image on Top"))],
                spec.extra.get("orientation", "horizontal"),
                lambda v: self._set_orientation(spec, v))

        menu.add_rename(tr("rename", "Rename"), tile.display_name,
                        lambda text: self._apply_rename(tile, text))

        if spec.wid == "stats_title":
            menu.add_action(tr("edit_title", "Edit Title…"), self._edit_stats_title)

        menu.add_action(tr("remove", "Remove"),
                        lambda: self.canvas.remove_tile(tile))

        menu.popup_at(global_pos)

    def _set_span(self, tile, rs, cs):
        rs, cs = tile.spec.clamp_span(rs, cs)
        tile.row_span, tile.col_span = rs, cs
        if tile.col + cs > self.canvas.cols:
            tile.col = max(0, self.canvas.cols - cs)
        # growing a tile can swallow a neighbour's cells -> push them aside
        self.canvas._resolve_overlaps(priority=tile)
        self.canvas.relayout(animated=True)
        self._on_layout_changed()

    def _set_orientation(self, spec, value):
        spec.extra["orientation"] = value

    def _apply_rename(self, tile, text):
        text = (text or "").strip()
        if not text or text == tile.display_name:
            return
        tile.display_name = text
        tile.update()
        self._on_layout_changed()

    def _edit_stats_title(self):
        try:
            from ._title_editor import StatsTitleDialog, STATS_TITLE_SYNC_KEY, clamp_stats_title
            sd = self.settings_dialog
            dialog = StatsTitleDialog(
                sd.stats_title_input.text(),
                getattr(sd, "selected_stats_title_font_key", STATS_TITLE_SYNC_KEY),
                sd.addon_path, sd)

            def on_accepted(text, font_key):
                sd.stats_title_input.setText(clamp_stats_title(text))
                sd.selected_stats_title_font_key = font_key or STATS_TITLE_SYNC_KEY
                spec = self._specs.get("stats_title")
                if spec:
                    spec.extra["value"] = clamp_stats_title(text) or spec.name
                for t in self.canvas.tiles:
                    if t.spec.wid == "stats_title":
                        t.update()

            dialog.titleAccepted.connect(on_accepted)
            dialog.exec()
        except Exception as exc:
            print(f"Onigiri: stats title editor failed: {exc}")

    # ------------------------------------------------------------------ #
    #  Reactions                                                          #
    # ------------------------------------------------------------------ #
    def _set_spin_selected(self, spin, selected):
        """Light up the little box when its value isn't in the 2-6 segments."""
        spin.setStyleSheet(
            self._spin_selected_style if selected else self._spin_plain_style)

    def _queue_grid(self, cols=None, rows=None):
        """Debounce the (expensive, resizing) canvas rebuild so a burst of
        edits collapses into one non-animated set_grid on the timer."""
        if cols is not None:
            self._pending_cols = cols
        if rows is not None:
            self._pending_rows = rows
        self._grid_timer.start()

    def _apply_pending_grid(self):
        cols = self._pending_cols if self._pending_cols is not None else self.canvas.cols
        rows = self._pending_rows if self._pending_rows is not None else self.canvas.min_rows
        self._pending_cols = None
        self._pending_rows = None
        # animated=False: no spring reflow, so the panel doesn't visibly jump.
        self.canvas.set_grid(rows, cols, animated=False)
        self._on_layout_changed()

    def _on_columns_button_clicked(self, *_):
        btn = self.col_group.checkedButton()
        if not btn:
            return
        c = _clamp_int(btn.property("cols"), 1, 60, 4)
        self.col_spin.blockSignals(True)
        self.col_spin.setValue(c)
        self.col_spin.blockSignals(False)
        self._set_spin_selected(self.col_spin, False)
        self._queue_grid(cols=c)

    def _on_columns_spin_changed(self, value):
        match = False
        for b in self.col_group.buttons():
            if b.property("cols") == str(value):
                b.setChecked(True)
                match = True
        if not match:
            self.col_group.setExclusive(False)
            for b in self.col_group.buttons():
                b.setChecked(False)
            self.col_group.setExclusive(True)
            self._cols_shell.clear_blob()
        self._set_spin_selected(self.col_spin, not match)
        self._queue_grid(cols=value)

    def _current_row_value(self):
        return self.row_spin.value()

    def _on_rows_button_clicked(self, *_):
        btn = self.row_group.checkedButton()
        if not btn:
            return
        r = _clamp_int(btn.property("rows"), 1, 60, 6)
        self.row_spin.blockSignals(True)
        self.row_spin.setValue(r)
        self.row_spin.blockSignals(False)
        self._set_spin_selected(self.row_spin, False)
        self._queue_grid(rows=r)

    def _on_rows_spin_changed(self, value):
        match = False
        for b in self.row_group.buttons():
            if b.property("rows") == str(value):
                b.setChecked(True)
                match = True
        if not match:
            self.row_group.setExclusive(False)
            for b in self.row_group.buttons():
                b.setChecked(False)
            self.row_group.setExclusive(True)
            self._rows_shell.clear_blob()
        self._set_spin_selected(self.row_spin, not match)
        self._queue_grid(rows=value)

    def _on_widget_height_changed(self, value):
        self.canvas.cell_h = self._cell_height_for(value)
        self.canvas.relayout(animated=True)

    def _on_layout_changed(self):
        self._applied_row_count = max(self._current_row_value(), self.canvas.rows)

    def commit_pending_grid(self):
        """Apply any typed-but-not-yet-applied row/column value.

        The spin boxes use keyboardTracking=False and the canvas rebuild is
        debounced, so hitting Save right after typing a number could read the
        old canvas size (the grid would snap back to the widget count)."""
        self.row_spin.interpretText()
        self.col_spin.interpretText()
        if self._grid_timer.isActive():
            self._grid_timer.stop()
            self._apply_pending_grid()
        else:
            self._on_layout_changed()

    def reset_layout(self):
        self.canvas.clear()
        # reset columns to 4
        self.col_spin.setValue(4)
        for btn in self.col_group.buttons():
            btn.setChecked(btn.property("cols") == "4")
        self.row_spin.setValue(6)
        for btn in self.row_group.buttons():
            btn.setChecked(btn.property("rows") == "6")
        self.canvas.set_grid(6, 4)
        cols = self.canvas.cols
        for wid, cfg in self._default_layout()["grid"].items():
            spec = self._specs.get(wid)
            if not spec:
                continue
            rs, cs = spec.clamp_span(cfg.get("row", 1), cfg.get("col", 1))
            pos = cfg.get("pos", 0)
            self.canvas.add_spec(spec, animated=False, row=pos // cols, col=pos % cols,
                                 row_span=rs, col_span=cs)
        self.canvas.relayout(animated=True)
        self._on_layout_changed()
        show_settings_toast(self.settings_dialog, tr("layout_reset_toast", "Layout reset to defaults"))

    # ------------------------------------------------------------------ #
    #  Serialise                                                          #
    # ------------------------------------------------------------------ #
    def get_layout_config(self):
        self.commit_pending_grid()
        cols = self.canvas.cols
        onigiri_grid = {}
        external_grid = {}
        placed_onigiri = set()
        placed_external = set()

        for tile in self.canvas.tiles:
            spec = tile.spec
            pos = tile.row * cols + tile.col
            if spec.kind == "onigiri":
                entry = {
                    "pos": pos,
                    "row": tile.row_span,
                    "col": tile.col_span,
                    "display_name": tile.display_name,
                }
                if spec.wid == "restaurant_level":
                    entry["orientation"] = spec.extra.get("orientation", "horizontal")
                onigiri_grid[spec.wid] = entry
                placed_onigiri.add(spec.wid)
            else:
                external_grid[spec.wid] = {
                    "grid_position": pos,
                    "row_span": max(2, tile.row_span),
                    "column_span": tile.col_span,
                    "display_name": tile.display_name,
                }
                placed_external.add(spec.wid)

        # Archives = every known widget that is not currently placed.
        onigiri_archive = {}
        for wid, *_ in _ONIGIRI_CATALOGUE:
            if wid not in placed_onigiri and wid in self._specs:
                onigiri_archive[wid] = {"display_name": self._specs[wid].name}
        external_archive = {}
        for wid, spec in self._specs.items():
            if spec.kind in ("external", "bento") and wid not in placed_external:
                external_archive[wid] = {"display_name": spec.name}

        return {
            "onigiri": {
                "grid": onigiri_grid,
                "archive": onigiri_archive,
                "column_count": cols,
                "grid_width": self.grid_width_spin.value(),
                "grid_alignment": (self.align_group.checkedButton().property("grid_alignment")
                                   if self.align_group.checkedButton() else "center"),
                "widget_height": self.widget_height_spin.value(),
            },
            "external": {"grid": external_grid, "archive": external_archive},
            "identity": self._identity,
        }


# --------------------------------------------------------------------------- #
#  small helpers                                                              #
# --------------------------------------------------------------------------- #
def _clamp_int(value, lo, hi, default):
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def _split_layout(layout):
    if isinstance(layout, dict) and "grid" not in layout and layout:
        return layout, {}
    if not isinstance(layout, dict):
        return {}, {}
    return layout.get("grid", {}) or {}, layout.get("archive", {}) or {}


def _readable_hex(color):
    c = QColor(color)
    lum = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255.0
    return "#111827" if lum > 0.6 else "#ffffff"


def _shade(hex_color, factor):
    c = QColor(hex_color)
    return QColor(int(c.red() * factor), int(c.green() * factor),
                  int(c.blue() * factor)).name()
