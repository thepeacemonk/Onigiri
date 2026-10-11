"""Anki Design — Add Card window redesign.

The native AddCards dialog (`aqt.addcards.AddCards`) is a QMainWindow with:
  - top row: notetype + deck chooser
  - middle: editor webview (Svelte app)
  - bottom: QDialogButtonBox (Add / Close / Help / History)

We rebuild all the Qt chrome around the editor in the same editorial style as
the rest of Anki Design (settings dialog, deck home, sidebar). The editor
webview itself gets a CSS overlay in `web/addcard.css` (injected via
`webview_will_set_content` when the context is an Editor in ADD_CARDS mode).

Layout philosophy:
  - No "Add card" page-title — the window's title bar already says that.
  - Top: inline editorial sentence "New [Basic ▾] card in [Anki ▾]" — the
    chooser values are styled italic-serif links, opening the same picker
    as Anki's native chooser when clicked.
  - Bottom: a single primary Add-card button on the right with a
    hover-revealed shortcut pill; a Recent menu on the left.

Add-on compatibility: the original Add / History buttons keep their
handlers, shortcuts and `gui_hooks.add_cards_*` firing. We hide the stock
QDialogButtonBox and proxy clicks. The history menu is rebuilt under our
own button so it anchors to the visible button (the proxied click would
otherwise open the menu at the hidden button's position).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from aqt import gui_hooks, mw
from aqt.addcards import AddCards
from aqt.qt import (
    QApplication,
    QColor,
    QEasingCurve,
    QEvent,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QKeySequence,
    QLabel,
    QMenu,
    QObject,
    QPalette,
    QPoint,
    QPropertyAnimation,
    QPushButton,
    QShortcut,
    QSize,
    Qt,
    QVBoxLayout,
    QWidget,
)


ADDON = __name__.split(".")[0]


# Palettes mirror settings.py so light/dark stays coherent across dialogs.
PAL_DARK: Dict[str, str] = {
    "paper": "#171717", "panel": "#2c2c2c", "ink": "#e0e0e0",
    "ink_dim": "#9e9e9e", "ink_faint": "#616161",
    "line": "rgba(224,224,224,0.10)", "line2": "rgba(224,224,224,0.20)",
    "hover": "rgba(224,224,224,0.05)", "field_bg": "#2c2c2c",
}
PAL_LIGHT: Dict[str, str] = {
    "paper": "#eeeeee", "panel": "#ffffff", "ink": "#212121",
    "ink_dim": "#757575", "ink_faint": "#bdbdbd",
    "line": "rgba(33,33,33,0.10)", "line2": "rgba(33,33,33,0.20)",
    "hover": "rgba(33,33,33,0.05)",
    "field_bg": "#ffffff",
}

SERIF = '"New York", "Hoefler Text", "Iowan Old Style", Charter, Georgia, serif'
SANS = '"SF Pro Text", "Helvetica Neue", "Segoe UI", system-ui, sans-serif'


def _config() -> Dict[str, Any]:
    try:
        from . import colors as _colors

        return _colors.onigiri_layout_config()
    except Exception:
        return mw.addonManager.getConfig(ADDON) or {}


def _resolve_palette() -> Tuple[Dict[str, str], bool]:
    try:
        from . import colors as _colors

        palette, is_dark = _colors.onigiri_palette()
        return _colors.apply_background(palette, _config(), is_dark), is_dark
    except Exception:
        pass

    cfg = _config()
    pref = cfg.get("theme", "system")
    if pref == "dark":
        is_dark = True
    elif pref == "light":
        is_dark = False
    else:
        try:
            c = QApplication.palette().color(QPalette.ColorRole.Window)
            is_dark = (c.red() + c.green() + c.blue()) < 384
        except Exception:
            is_dark = True
    pal = PAL_DARK if is_dark else PAL_LIGHT
    # Background override (Settings → Appearance) so the Qt-side chrome of
    # the embeds matches the page paper.
    try:
        from . import colors as _colors
        pal = _colors.apply_background(pal, cfg, is_dark)
    except Exception:
        pass
    return pal, is_dark


def _qss(p: Dict[str, str], accent: str, is_dark: bool) -> str:
    """QSS for the Add Card window chrome (everything outside the webview).
    The editor itself is restyled by web/addcard.css."""
    # The kbd chip inside the Add button shows in INVERSE of the button bg —
    # in light mode the button is dark ink so the chip uses translucent
    # white; in dark mode the button is light (ink-in-dark = pale) so the
    # chip uses translucent dark. Detect by checking which palette we got.
    if is_dark:
        kbd_color = "rgba(31, 29, 24, 0.80)"
        kbd_bg = "rgba(31, 29, 24, 0.10)"
        kbd_border = "rgba(31, 29, 24, 0.18)"
    else:
        kbd_color = "rgba(255, 255, 255, 0.85)"
        kbd_bg = "rgba(255, 255, 255, 0.12)"
        kbd_border = "rgba(255, 255, 255, 0.20)"
    return f"""
QDialog, QMainWindow, #ba-root, #ba-context, #ba-footer, #ba-fields-wrap {{
    background: {p['paper']};
    color: {p['ink']};
    font-family: {SANS};
}}

QFrame[role="rule"] {{
    background: {p['line']};
    max-height: 1px;
    min-height: 1px;
    border: 0;
}}

/* Inline context: "New  [Basic ▾]  card in  [Anki ▾]"
   Clean sans throughout for readability. Connective text is faint; the
   chooser values are weighted so they read as the clickable parts. */
#ba-context QLabel {{
    color: {p['ink_faint']};
    font-family: {SANS};
    font-size: 11.5pt;
    font-weight: 400;
    background: transparent;
}}
#modelArea QPushButton, #deckArea QPushButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    color: {p['ink']};
    font-family: {SANS};
    font-size: 11.5pt;
    font-weight: 600;
    padding: 1px 4px;
    min-height: 16px;
    text-decoration: none;
}}
#modelArea QPushButton:hover, #deckArea QPushButton:hover {{
    color: {accent};
    background: transparent;
}}
#modelArea QPushButton:focus, #deckArea QPushButton:focus {{
    outline: none;
    color: {accent};
}}
#modelArea QLabel, #deckArea QLabel {{
    background: transparent;
}}

/* ---------------- Footer ----------------
 * Single primary action (Add card). Recent was removed — the user never
 * understood what it was and it never had useful content (history only
 * populated within a single AddCards session, which the embed creates and
 * tears down every time). Keeping the footer to one confident action is
 * cleaner.
 */

/* Add card primary button — shadcn-style: flat, modest radius, no
 * gradients or pill shape. Just a solid ink rectangle with a hairline
 * border and a clean sans label. Text color is paper (page bg) so the
 * inverse fill reads correctly in both light and dark themes.
 */
#ba-footer QPushButton#ba-add {{
    color: {p['paper']};
    background: {p['ink']};
    border: 1px solid {p['ink']};
    border-radius: 6px;
    padding: 8px 18px;
    font-family: {SANS};
    font-size: 10.5pt;
    font-weight: 500;
    letter-spacing: 0.15px;
    min-height: 18px;
    min-width: 110px;
    text-align: center;
}}
#ba-footer QPushButton#ba-add:hover {{
    background: {p['ink_dim']};
    border-color: {p['ink_dim']};
}}
#ba-footer QPushButton#ba-add:pressed {{
    background: {p['ink_faint']};
    border-color: {p['ink_faint']};
}}
#ba-footer QPushButton#ba-add:focus {{
    outline: none;
    border-color: {accent};
}}

/* The hover-revealed keyboard chip lives INSIDE the button (parent =
   add_btn). Theme-aware colors: dark chip on light bg, light chip on
   dark bg. Animation lives on _AddBtnHover (QPropertyAnimation), not
   in QSS — Qt's stylesheet transitions only cover a small subset of
   properties. */
QLabel#ba-add-kbd {{
    color: {kbd_color};
    background: {kbd_bg};
    border: 1px solid {kbd_border};
    border-radius: 5px;
    padding: 3px 7px 3px 7px;
    font-family: {SANS};
    font-size: 10pt;
    font-weight: 600;
    letter-spacing: 0.4px;
}}
"""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _proxy_click(source: QPushButton, target: QPushButton) -> None:
    """Wire a new button to click the underlying native one (preserves
    shortcuts and gui_hooks)."""
    source.clicked.connect(target.click)


def _hrule(palette: Dict[str, str]) -> QFrame:
    f = QFrame()
    f.setProperty("role", "rule")
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"QFrame {{ background: {palette['line']}; }}")
    f.setFixedHeight(1)
    return f


class _AddBtnHover(QObject):
    """Reveals the keyboard-shortcut chip inside the Add card button on
    hover with a fade + slide-in animation matching the sidebar's CSS
    transition pattern.

    The chip is a child QLabel parented to the button. On Enter: opacity
    animates 0→1 and position animates from `rest_x + 6px` → `rest_x`
    (slide in from the right). On Leave: reverse, fade-out + slide-out.
    Hidden state is opacity-0 + offset so the geometry stays stable.
    """

    SLIDE_PX = 6
    DURATION_MS = 180

    def __init__(self, btn: QPushButton, kbd: QLabel) -> None:
        super().__init__(btn)
        self._btn = btn
        self._kbd = kbd

        # Opacity effect — animatable via QPropertyAnimation("opacity").
        self._opacity = QGraphicsOpacityEffect(kbd)
        self._opacity.setOpacity(0.0)
        kbd.setGraphicsEffect(self._opacity)

        self._opacity_anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._opacity_anim.setDuration(self.DURATION_MS)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._pos_anim = QPropertyAnimation(kbd, b"pos", self)
        self._pos_anim.setDuration(self.DURATION_MS)
        self._pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._reposition(at_rest=False)  # initial: slid-out, invisible
        btn.installEventFilter(self)

    def _rest_xy(self) -> Tuple[int, int]:
        self._kbd.adjustSize()
        bw = self._btn.width()
        bh = self._btn.height()
        kw = self._kbd.width()
        kh = self._kbd.height()
        # Flush right inside the button with a comfortable inset, vertical
        # center.
        x = bw - kw - 12
        y = (bh - kh) // 2
        return x, y

    def _reposition(self, at_rest: bool) -> None:
        try:
            x, y = self._rest_xy()
            self._kbd.adjustSize()
            kw = self._kbd.width()
            kh = self._kbd.height()
            if at_rest:
                self._kbd.setGeometry(x, y, kw, kh)
            else:
                # Hidden state: sit slid-out to the right.
                self._kbd.setGeometry(x + self.SLIDE_PX, y, kw, kh)
        except Exception:
            pass

    def _animate_in(self) -> None:
        try:
            x, y = self._rest_xy()
            self._kbd.show()
            self._kbd.raise_()
            self._opacity_anim.stop()
            self._pos_anim.stop()
            self._opacity_anim.setStartValue(self._opacity.opacity())
            self._opacity_anim.setEndValue(1.0)
            self._pos_anim.setStartValue(self._kbd.pos())
            self._pos_anim.setEndValue(QPoint(x, y))
            self._opacity_anim.start()
            self._pos_anim.start()
        except Exception:
            pass

    def _animate_out(self) -> None:
        try:
            x, y = self._rest_xy()
            self._opacity_anim.stop()
            self._pos_anim.stop()
            self._opacity_anim.setStartValue(self._opacity.opacity())
            self._opacity_anim.setEndValue(0.0)
            self._pos_anim.setStartValue(self._kbd.pos())
            self._pos_anim.setEndValue(QPoint(x + self.SLIDE_PX, y))
            self._opacity_anim.start()
            self._pos_anim.start()
        except Exception:
            pass

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        try:
            t = event.type()
            if t == QEvent.Type.Enter:
                self._animate_in()
            elif t == QEvent.Type.Leave:
                self._animate_out()
            elif t == QEvent.Type.Resize:
                # Snap to whichever state we're in.
                at_rest = self._opacity.opacity() > 0.5
                self._reposition(at_rest=at_rest)
        except Exception:
            pass
        return False


# --------------------------------------------------------------------------- #
# Inline pickers for note type / deck (replace the StudyDeck popup window).
# --------------------------------------------------------------------------- #
def _wire_inline_notetype_picker(
    addcards: AddCards, btn: QPushButton
) -> None:
    """Replace the chooser's button click with a dropdown menu listing all
    note types. Picking one calls the chooser's setter — same effect as the
    original popup, no new window."""
    try:
        btn.clicked.disconnect()
    except Exception:
        pass

    def _open_menu() -> None:
        try:
            m = QMenu(addcards)
            current_id = int(addcards.notetype_chooser.selected_notetype_id)
            for nid in sorted(
                addcards.col.models.all_names_and_ids(),
                key=lambda n: n.name.lower(),
            ):
                act = m.addAction(nid.name)
                if int(nid.id) == current_id:
                    f = act.font()
                    f.setBold(True)
                    act.setFont(f)
                act.triggered.connect(
                    lambda _, i=int(nid.id):
                        setattr(addcards.notetype_chooser,
                                "selected_notetype_id", i)
                )
            m.addSeparator()
            edit = m.addAction("Manage note types…")
            edit.triggered.connect(
                lambda _: addcards.notetype_chooser.onEdit()
            )
            pos = btn.mapToGlobal(QPoint(0, btn.height()))
            m.exec(pos)
        except Exception:
            pass
    btn.clicked.connect(_open_menu)


def _wire_inline_deck_picker(addcards: AddCards, btn: QPushButton) -> None:
    """Same as above for decks. all_names_and_ids returns the hierarchical
    names (Parent::Child); show them as-is so the structure is visible."""
    try:
        btn.clicked.disconnect()
    except Exception:
        pass

    def _open_menu() -> None:
        try:
            m = QMenu(addcards)
            current_id = int(addcards.deck_chooser.selected_deck_id)
            decks = sorted(
                addcards.col.decks.all_names_and_ids(skip_empty_default=False),
                key=lambda d: d.name.lower(),
            )
            for dk in decks:
                # Skip filtered decks — the add window can't target them.
                try:
                    dd = addcards.col.decks.get(dk.id, default=False)
                    if dd and dd.get("dyn"):
                        continue
                except Exception:
                    pass
                act = m.addAction(dk.name)
                if int(dk.id) == current_id:
                    f = act.font()
                    f.setBold(True)
                    act.setFont(f)
                act.triggered.connect(
                    lambda _, i=int(dk.id):
                        setattr(addcards.deck_chooser,
                                "selected_deck_id", i)
                )
            m.addSeparator()
            new = m.addAction("New deck…")
            def _new_deck() -> None:
                try:
                    from aqt.operations.deck import add_deck_dialog
                    add_deck_dialog(parent=addcards)
                except Exception:
                    pass
            new.triggered.connect(lambda _: _new_deck())
            pos = btn.mapToGlobal(QPoint(0, btn.height()))
            m.exec(pos)
        except Exception:
            pass
    btn.clicked.connect(_open_menu)


# --------------------------------------------------------------------------- #
# Rebuild AddCards chrome on init
# --------------------------------------------------------------------------- #
def _redress(addcards: AddCards) -> None:
    palette, _ = _resolve_palette()
    cfg = _config()
    accent = cfg.get("accent", "#0077c8")

    try:
        addcards.setWindowTitle("Add card")
    except Exception:
        pass

    # Build our root container. Palette + autoFillBackground paints it
    # opaque paper from the very first frame, beating the QSS pass which
    # can lag by one frame and otherwise shows as a white flash on dark
    # mode when the embed is first shown.
    root = QWidget()
    root.setObjectName("ba-root")
    root.setAutoFillBackground(True)
    _root_pal = root.palette()
    _root_pal.setColor(
        QPalette.ColorRole.Window, QColor(palette["paper"])
    )
    root.setPalette(_root_pal)
    root_layout = QVBoxLayout(root)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(0)

    # --- Context strip: "New [Basic ▾] card in [Anki ▾]" --- #
    context = QWidget()
    context.setObjectName("ba-context")
    ctx_layout = QHBoxLayout(context)
    ctx_layout.setContentsMargins(28, 14, 28, 12)
    ctx_layout.setSpacing(2)

    nt_area: QWidget = addcards.form.modelArea
    dk_area: QWidget = addcards.form.deckArea
    try:
        nt_area.setMinimumSize(QSize(0, 0))
        dk_area.setMinimumSize(QSize(0, 0))
    except Exception:
        pass

    # NotetypeChooser / DeckChooser auto-add a QLabel ("Type" / "Deck") — hide
    # it so the inline sentence has its own narration.
    def _hide_first_label(host: QWidget) -> None:
        try:
            for child in host.findChildren(QLabel):
                child.hide()
                break
        except Exception:
            pass
    _hide_first_label(nt_area)
    _hide_first_label(dk_area)

    # Style each chooser's QPushButton as an inline text link, and append a
    # tiny ▾ so it reads as openable. Also intercept the click to show a
    # dropdown menu in-page instead of opening Anki's StudyDeck popup.
    def _stylize(host: QWidget, kind: str) -> None:
        try:
            for b in host.findChildren(QPushButton):
                b.setObjectName("ba-chooser")
                b.setFlat(True)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                txt = b.text()
                if not txt.endswith(" ▾"):
                    b.setText(f"{txt} ▾")
                if kind == "notetype":
                    _wire_inline_notetype_picker(addcards, b)
                elif kind == "deck":
                    _wire_inline_deck_picker(addcards, b)
        except Exception:
            pass
    _stylize(nt_area, "notetype")
    _stylize(dk_area, "deck")

    # Build the sentence. Each fragment is a thin QLabel; chooser pushbuttons
    # sit between them.
    pre = QLabel("New ")
    mid = QLabel(" card in ")
    post = QLabel("")

    ctx_layout.addWidget(pre)
    ctx_layout.addWidget(nt_area)
    ctx_layout.addWidget(mid)
    ctx_layout.addWidget(dk_area)
    ctx_layout.addWidget(post)
    ctx_layout.addStretch(1)

    root_layout.addWidget(context)
    root_layout.addWidget(_hrule(palette))

    # --- Fields (editor webview lives inside addcards.form.fieldsArea) --- #
    fields_wrap = QWidget()
    fields_wrap.setObjectName("ba-fields-wrap")
    fw = QVBoxLayout(fields_wrap)
    fw.setContentsMargins(0, 0, 0, 0)
    fw.setSpacing(0)
    fields_area: QWidget = addcards.form.fieldsArea
    fw.addWidget(fields_area)
    root_layout.addWidget(fields_wrap, 1)

    # --- Footer --- #
    # No hrule between fields and footer — the dark Add-card pill provides
    # enough visual weight, and the extra line was part of the "borders
    # everywhere" complaint.
    footer = QWidget()
    footer.setObjectName("ba-footer")
    fl = QHBoxLayout(footer)
    fl.setContentsMargins(28, 14, 28, 16)
    fl.setSpacing(10)

    # Add card: pill-shaped, dark warm ink with a subtle bevel. The
    # keyboard-shortcut chip is a child QLabel that hides by default and
    # reveals on hover (see _AddBtnHover), mirroring the sidebar's
    # hover-key affordance pattern. Recent was removed: its in-session
    # history was always empty in our embed flow (each open creates a
    # fresh AddCards), and the user reported it never appeared to work.
    add_btn = QPushButton("Add card")
    add_btn.setObjectName("ba-add")
    add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    add_btn.setToolTip("Add card  (⌘↩)")

    kbd = QLabel("⌘↩", add_btn)
    kbd.setObjectName("ba-add-kbd")
    kbd.setAlignment(Qt.AlignmentFlag.AlignCenter)
    addcards._ba_add_hover = _AddBtnHover(add_btn, kbd)  # keep ref alive
    # NOTE: tried a QGraphicsDropShadowEffect on the button for depth, but
    # Qt rasterizes the whole button (including children) when applying
    # the effect, which swallowed the kbd's own QGraphicsOpacityEffect
    # used by the hover animation. The button bevel (top-light/bottom-
    # dark border + vertical gradient) provides enough physical feel.

    # Wire Add directly to `addcards.add_current_note`. Important: do NOT
    # proxy through `addcards.addButton` — Anki's buttonBox sits inside
    # the old central widget, and our `addcards.setCentralWidget(root)`
    # call below destroys that old widget and ALL its children, including
    # the addButton itself. Click forwarded to a freed widget silently
    # no-ops, which was why the Add button (and the Ctrl+Enter shortcut
    # bound to addButton.click) appeared dead.
    # The wrapper:
    #   - swallows QPushButton.clicked's bool arg (mismatch with self-only
    #     signature),
    #   - debounces re-entry: rapid Add card clicks (button OR Ctrl+Enter
    #     while a prior add is still flushing) trigger a Rust-side
    #     PoisonError in Anki's backend (mw.col temporarily goes None on
    #     a worker thread, the db mutex gets left poisoned, the second
    #     add hits the poisoned mutex and panics). 700ms cooldown covers
    #     the WebChannel save + add_note bg op round-trip.
    #   - logs any exception that bubbles out so the next crash gets a
    #     traceback in run.log instead of Anki's opaque dialog.
    def _safe_add(*_: Any) -> None:
        if getattr(addcards, "_ba_add_busy", False):
            return
        addcards._ba_add_busy = True  # type: ignore[attr-defined]
        try:
            addcards.add_current_note()
        except Exception:
            import traceback
            try:
                print(
                    f"[anki-design.addcard] add_current_note failed:\n"
                    f"{traceback.format_exc()}",
                    flush=True,
                )
            except Exception:
                pass
        try:
            from aqt.qt import QTimer
            QTimer.singleShot(
                700,
                lambda: setattr(addcards, "_ba_add_busy", False),
            )
        except Exception:
            addcards._ba_add_busy = False  # type: ignore[attr-defined]

    try:
        add_btn.clicked.connect(_safe_add)
    except Exception:
        pass
    addcards._ba_safe_add = _safe_add  # type: ignore[attr-defined]

    # Kept for reference but unused now — left here so future change to
    # restore the Recent affordance can reuse the same QMenu pattern.
    def _show_recent_menu() -> None:
        try:
            from anki.collection import SearchNode
            from anki.utils import html_to_text_line
            from aqt.utils import tr as ttr
            m = QMenu(addcards)
            history = list(getattr(addcards, "history", []))
            if not history:
                a = m.addAction("No recently added notes")
                a.setEnabled(False)
            else:
                for nid in history:
                    try:
                        if addcards.col.find_notes(
                            addcards.col.build_search_string(SearchNode(nid=nid))
                        ):
                            note = addcards.col.get_note(nid)
                            txt = html_to_text_line(", ".join(note.fields))
                            if len(txt) > 40:
                                txt = txt[:40] + "…"
                            try:
                                label = ttr.adding_edit(val=txt)
                            except Exception:
                                label = f"Edit: {txt}"
                            label = gui_hooks.addcards_will_add_history_entry(
                                label, note
                            )
                            label = label.replace("&", "&&")
                            a = m.addAction(label)
                            a.triggered.connect(
                                lambda _, nid=nid: addcards.editHistory(nid)
                            )
                        else:
                            try:
                                label = ttr.adding_note_deleted()
                            except Exception:
                                label = "(deleted)"
                            a = m.addAction(label)
                            a.setEnabled(False)
                    except Exception:
                        continue
            try:
                gui_hooks.add_cards_will_show_history_menu(addcards, m)
            except Exception:
                pass
            # Anchor at the bottom-left of the calling button (passed in
            # via closure if/when this is reused).
            m.exec(add_btn.mapToGlobal(QPoint(0, add_btn.height())))
        except Exception as e:
            try:
                from aqt.utils import showWarning
                showWarning(f"Recent menu failed: {e}")
            except Exception:
                pass
    _ = _show_recent_menu  # keep callable in scope without unused-warning

    fl.addStretch(1)
    fl.addWidget(add_btn)
    root_layout.addWidget(footer)

    # CRITICAL: rescue the stock buttons (addButton, historyButton,
    # closeButton, helpButton) from the central widget BEFORE we replace
    # it. setCentralWidget(...) deletes the old central widget *and all
    # its descendants*. Anki's `addHistory()` runs after every successful
    # add and does `self.historyButton.setEnabled(True)` — if historyButton
    # is freed C++ memory, the call corrupts the backend's Rust mutex and
    # the NEXT operation (add, refresh, sync) panics with a PoisonError.
    # Reparenting them to the AddCards QMainWindow keeps them alive and
    # invisible (they aren't in any layout).
    try:
        for attr in ("addButton", "historyButton", "closeButton",
                     "helpButton"):
            w = getattr(addcards, attr, None)
            if w is not None:
                w.setParent(addcards)
                w.hide()
    except Exception:
        pass
    try:
        addcards.form.buttonBox.hide()
    except Exception:
        pass

    # Apply QSS and install our root as the central widget.
    try:
        addcards.setStyleSheet(_qss(palette, accent, is_dark))
    except Exception:
        pass
    try:
        addcards.setCentralWidget(root)
    except Exception:
        pass

    # Pre-paint the editor webview's default page background to match our
    # paper color. Anki's webview.py already calls setBackgroundColor with
    # its own theme-aware CANVAS color (#f5f5f5 in light, #2c2c2c in dark)
    # — if the user's Anki app is in light mode but the addon is in dark
    # mode, that means the page bg is near-white. Overriding it here keeps
    # the webview painting paper-dark from the very first frame.
    # Also paint the Qt widget itself (the backing store under the
    # Chromium compositor) so anything that briefly paints before the GPU
    # layer is uploaded shows paper, not the default widget white.
    try:
        web = getattr(addcards.editor, "web", None)
        if web is not None:
            page = web.page()
            if page is not None:
                page.setBackgroundColor(QColor(palette["paper"]))
            try:
                web.setStyleSheet(
                    f"QWidget {{ background: {palette['paper']}; }}"
                )
                web.setAutoFillBackground(True)
                _wp = web.palette()
                _wp.setColor(QPalette.ColorRole.Window, QColor(palette["paper"]))
                _wp.setColor(QPalette.ColorRole.Base, QColor(palette["paper"]))
                web.setPalette(_wp)
            except Exception:
                pass
    except Exception:
        pass

    # Re-apply chevron labels in case Anki updates the chooser button text
    # (happens when the user switches notetype or deck). Cheap 800ms tick.
    try:
        from aqt.qt import QTimer
        t = QTimer(addcards)
        t.setInterval(800)
        def _tick() -> None:
            _stylize(nt_area, "notetype")
            _stylize(dk_area, "deck")
        t.timeout.connect(_tick)
        t.start()
        addcards._ba_history_timer = t  # keep ref
    except Exception:
        pass

    # Larger default window.
    try:
        if addcards.width() < 880 or addcards.height() < 720:
            addcards.resize(
                max(addcards.width(), 880), max(addcards.height(), 720)
            )
    except Exception:
        pass


def on_add_cards_did_init(addcards: AddCards) -> None:
    # Settings → Windows → "Redesigned Add window". Off = stock Anki.
    if not _config().get("restyle_addcard", True):
        return
    try:
        _redress(addcards)
    except Exception as e:
        import traceback
        try:
            print(
                f"[anki-design.addcard] redress failed: {e}\n"
                f"{traceback.format_exc()}",
                flush=True,
            )
        except Exception:
            pass


def register() -> None:
    gui_hooks.add_cards_did_init.append(on_add_cards_did_init)
