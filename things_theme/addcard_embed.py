"""Anki Design — embed AddCards inside the main window as a "tab".

Anki opens AddCards as a separate QMainWindow. The user wants it to behave
like a tab in the main window: the sidebar (rendered inside `mw.web` by the
deck browser HTML) stays visible, and the editor occupies the rest.

How this works:
  - We intercept the sidebar's `ba:add` pycmd in `__init__.py` to call
    `open_inline(mw)` instead of `mw.onAddCard()`.
  - `open_inline` constructs an AddCards instance (which fires our normal
    `_redress` via `add_cards_did_init`).
  - We grab its `centralWidget` and reparent it onto a thin overlay frame
    placed on top of `mw.form.centralwidget`, offset by the sidebar's
    width so the sidebar in mw.web stays visible through the gap.
  - The AddCards window itself is hidden (its widgets are alive, so all
    handlers, shortcuts, and add-on hooks continue to fire).
  - A small "← Back to decks" affordance in the top-left of the overlay
    closes AddCards and removes the overlay.
  - The overlay resizes with the main window via an installed event filter.

Caveats:
  - Sidebar width is hard-coded to 250px to match `web/sidebar.css`. If
    the sidebar changes width, this needs to be updated.
  - Qt widgets stacking above QWebEngineView on macOS Qt6 has been stable
    for a long time but is technically a known-fragile combination — if
    rendering glitches appear, fall back to the standard windowed flow.
"""

from __future__ import annotations

from typing import Any, Optional

from aqt import mw
from aqt.qt import (
    QApplication,
    QColor,
    QEvent,
    QFrame,
    QHBoxLayout,
    QKeySequence,
    QLabel,
    QObject,
    QPalette,
    QPushButton,
    QShortcut,
    QSize,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
)


SIDEBAR_W = 264  # px — matches --rf-side-w in web/theme.css


def _palette_styles() -> str:
    """QSS for the embed wrapper and (importantly) re-applies the AddCards
    chrome QSS so the styles continue to match after we reparent. Without
    this the Add button comes through as a default white QPushButton."""
    from . import addcard as _addcard
    palette, is_dark = _addcard._resolve_palette()
    cfg = _addcard._config()
    accent = cfg.get("accent", "#0077c8")
    chrome = _addcard._qss(palette, accent, is_dark)
    return chrome + """
QFrame#ba-embed {
    background: """ + palette["paper"] + """;
    border-left: 1px solid """ + palette["line"] + """;
}
QPushButton#ba-back {
    background: transparent;
    color: """ + palette["ink_dim"] + """;
    border: 1px solid """ + palette["line2"] + """;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 10.5pt;
    font-weight: 500;
}
QPushButton#ba-back:hover {
    color: """ + palette["ink"] + """;
    background: """ + palette["hover"] + """;
    border-color: """ + palette["ink_faint"] + """;
}
"""


class _EmbedFilter(QObject):
    """Re-positions the embed overlay whenever the main window is resized."""

    def __init__(self, overlay: QFrame) -> None:
        super().__init__(overlay)
        self._overlay = overlay

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Resize:
            try:
                cw = mw.form.centralwidget
                self._overlay.setGeometry(
                    SIDEBAR_W,
                    0,
                    cw.width() - SIDEBAR_W,
                    cw.height(),
                )
            except Exception:
                pass
        return False


_state: dict = {"addcards": None, "overlay": None, "filter": None}


def drop_curtain() -> None:
    """Tear down the anti-flash curtain put up by open_inline.

    Called from the `ba:embed-ready` pycmd that addcard.js fires from
    its reveal() once the editor body has had a chance to settle. Safe
    to call multiple times — second+ calls are no-ops."""
    c = _state.pop("curtain", None)
    _state.pop("drop_curtain", None)
    if c is not None:
        try:
            c.deleteLater()
        except Exception:
            pass


def close_inline() -> None:
    """Tear down the embedded view and restore the deck browser.

    No-op if there is no embed currently open — so callers (e.g. the
    moveToState monkey-patch in __init__.py) can call this on every
    navigation event cheaply."""
    overlay = _state.get("overlay")
    ac = _state.get("addcards")
    flt = _state.get("filter")
    if overlay is None and ac is None and flt is None:
        return

    # Clear state FIRST so the patched ac._close (which calls back into
    # close_inline) returns immediately on its recursive entry.
    _state["addcards"] = None
    _state["overlay"] = None
    _state["filter"] = None
    cw_palette = _state.pop("cw_palette", None)
    # Drop the anti-flash curtain if it's still up (close_inline can fire
    # before the editor finished loading, e.g. user hits Esc immediately
    # after clicking Add).
    curtain = _state.pop("curtain", None)
    if curtain is not None:
        try:
            curtain.deleteLater()
        except Exception:
            pass
    _state.pop("drop_curtain", None)

    if overlay is not None:
        try:
            if flt is not None:
                mw.form.centralwidget.removeEventFilter(flt)
        except Exception:
            pass
        try:
            overlay.deleteLater()
        except Exception:
            pass
    # Restore the centralwidget's original palette (we tinted it paper
    # while the embed was open so any first-frame Qt gap painted dark
    # instead of the default white).
    if cw_palette is not None:
        try:
            mw.form.centralwidget.setPalette(cw_palette)
        except Exception:
            pass
    if ac is not None:
        # Use AddCards' own teardown method (synchronous). Going through
        # the public .close() would route via ifCanClose → editor.call_-
        # after_note_saved, which never completes when we've reparented
        # the central widget — so `gui_hooks.operation_did_execute.remove(
        # self.on_operation_did_execute)` inside _close never fires, and
        # the next operation (any review, edit, sync) tries to call
        # editor.widget.show() on a deleted C++ widget. Calling _close
        # directly removes the hook subscription synchronously.
        try:
            ac._close()  # type: ignore[attr-defined]
        except Exception:
            try:
                ac.close()
            except Exception:
                pass
    # Restore the sidebar's active tab.
    try:
        w = getattr(mw, "web", None)
        if w is not None:
            w.eval("window.__baSetActive && window.__baSetActive('decks');")
    except Exception:
        pass


def open_inline(parent_mw: Any = None) -> None:
    """Open AddCards embedded in the main window's content area.

    Falls back to the normal AddCards window if the embed setup fails for
    any reason."""
    parent_mw = parent_mw or mw
    if _state.get("overlay") is not None:
        # Already open — bring it forward.
        try:
            _state["overlay"].raise_()
        except Exception:
            pass
        return
    if _state.get("curtain") is not None:
        # A curtain is up — we're already mid-open from a previous call
        # (processEvents below can re-enter on rapid double-click). Bail
        # so we don't stack a second curtain + AddCards.
        return

    # --- Curtain (anti-flash) ---------------------------------------
    # Slam an opaque paper-colored QFrame over the embed area BEFORE any
    # of the AddCards / webview machinery runs. While the curtain is up,
    # everything underneath (the QWebEngineView's default white page bg,
    # any Qt widget that briefly paints with the wrong palette, the
    # toolbar/tag DOM reshuffle inside the editor) is invisible. We pump
    # one round of events to force the curtain's paint before we kick
    # off the heavy AddCards work, then drop the curtain only after the
    # editor's page loadFinished fires plus a small grace for the JS to
    # settle.
    from . import addcard as _addcard
    palette, _ = _addcard._resolve_palette()
    paper_qc = QColor(palette["paper"])
    cw = parent_mw.form.centralwidget

    curtain = QFrame(cw)
    curtain.setObjectName("ba-embed-curtain")
    curtain.setAutoFillBackground(True)
    _cu_pal = curtain.palette()
    _cu_pal.setColor(QPalette.ColorRole.Window, paper_qc)
    curtain.setPalette(_cu_pal)
    curtain.setStyleSheet(
        "QFrame#ba-embed-curtain { background: " + palette["paper"] + "; }"
    )
    curtain.setGeometry(SIDEBAR_W, 0, cw.width() - SIDEBAR_W, cw.height())
    curtain.show()
    curtain.raise_()
    _state["curtain"] = curtain
    # Force the curtain to paint NOW (repaint is synchronous, processEvents
    # pumps any pending events) so when the AddCards work below starts
    # spinning up Chromium and mounting Svelte, the curtain is already
    # covering the embed area and the user never sees what's underneath.
    try:
        curtain.repaint()
        QApplication.processEvents()
    except Exception:
        pass

    try:
        from aqt.addcards import AddCards
        # Anki's AddCards.__init__ ends with `self.show()`, which would
        # flash the standalone QMainWindow on screen for one paint before
        # we reparent its central widget into the overlay and hide the
        # window. Subclassing to no-op `show()` keeps it invisible from
        # the start; everything else (geometry restore, hook firing,
        # central-widget construction via _redress) still runs in the
        # parent constructor.
        class _EmbeddedAddCards(AddCards):  # type: ignore[misc, valid-type]
            def show(self) -> None:  # noqa: D401 — Qt method override
                pass
        ac = _EmbeddedAddCards(parent_mw)
    except Exception:
        # Anki's normal flow as a last resort.
        try:
            curtain.deleteLater()
        except Exception:
            pass
        _state["curtain"] = None
        try:
            parent_mw.onAddCard()
        except Exception:
            pass
        return

    try:
        central = ac.centralWidget()

        # Build an overlay frame holding the redressed AddCards centralWidget.
        # No back button — the sidebar already has a "Decks" item, and we
        # mark "Add" as active there so the user knows what tab they're on.
        overlay = QFrame(parent_mw.form.centralwidget)
        overlay.setObjectName("ba-embed")
        # Palette + autoFillBackground paints the QFrame opaque in the
        # native paint path, beating any first-frame transparency before
        # the QSS is committed.
        overlay.setAutoFillBackground(True)
        _ov_pal = overlay.palette()
        _ov_pal.setColor(QPalette.ColorRole.Window, paper_qc)
        overlay.setPalette(_ov_pal)
        overlay.setStyleSheet(_palette_styles())

        v = QVBoxLayout(overlay)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Reparent the redressed AddCards centralWidget into the overlay.
        # Use Qt.Widget so it acts like a normal child, not a window.
        central.setParent(overlay)
        central.setWindowFlags(Qt.WindowType.Widget)
        v.addWidget(central, 1)

        # Hide the original AddCards QMainWindow chrome.
        ac.setVisible(False)

        # Position over the right of the central area.
        cw = parent_mw.form.centralwidget
        # Paint the main centralwidget paper for the duration of the
        # embed. mw.web normally covers it, but during the brief frame
        # where the overlay show triggers a layout pass on the main
        # window, Qt can momentarily expose the centralwidget's palette
        # bg — which on Anki-light + addon-dark is near-white, producing
        # the white flash. Stash the original palette so we can restore
        # it on close.
        try:
            _state["cw_palette"] = QPalette(cw.palette())
            _cw_pal = cw.palette()
            _cw_pal.setColor(QPalette.ColorRole.Window, paper_qc)
            cw.setPalette(_cw_pal)
        except Exception:
            pass
        overlay.setGeometry(
            SIDEBAR_W, 0, cw.width() - SIDEBAR_W, cw.height()
        )
        overlay.show()
        overlay.raise_()
        # Curtain must stay on top of the overlay while everything inside
        # the overlay (editor webview, Svelte mount, our addcard.js DOM
        # shuffle) is still settling.
        try:
            curtain.raise_()
        except Exception:
            pass

        # Drop the curtain when addcard.js fires ba:embed-ready from
        # reveal() — that's the exact moment the editor body switches
        # from opacity 0 to opacity 1 and starts its fade-in. Dropping
        # then means the curtain (paper) gives way to the same paper
        # bg of the editor body, with content fading in on top. No
        # white/black/snap visible to the user.
        # Backstop: if the pycmd never fires (very rare — JS error in
        # the editor, sandboxed iframe, etc.), fall back to loadFinished
        # plus a short grace, and a hard cap so the user is never
        # stranded behind paper.
        try:
            page = ac.editor.web.page()

            def _on_loaded(_ok: bool) -> None:
                QTimer.singleShot(280, drop_curtain)

            page.loadFinished.connect(_on_loaded)
        except Exception:
            pass
        QTimer.singleShot(2000, drop_curtain)

        # Resize the overlay with the main window.
        flt = _EmbedFilter(overlay)
        cw.installEventFilter(flt)

        # Cmd/Ctrl+Return and Cmd/Ctrl+Enter — Anki's native shortcuts for
        # Add are bound by AddCards itself, but they all target the now-
        # destroyed addButton (the original buttonBox died with the old
        # centralWidget). Rebuild them on the overlay so the user's
        # standard "submit" keystrokes work while the embed is up.
        # We route through `ac._ba_safe_add` (set in addcard.py _redress)
        # rather than `ac.add_current_note` directly, so any exception
        # gets printed instead of bubbling into Anki's crash dialog.
        safe_add = getattr(ac, "_ba_safe_add", None) or ac.add_current_note
        try:
            for keys in ("Ctrl+Return", "Ctrl+Enter"):
                sc = QShortcut(QKeySequence(keys), overlay)
                sc.setAutoRepeat(False)
                sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
                sc.activated.connect(safe_add)
            # Esc closes the embed (Anki's native QMainWindow Esc was lost
            # along with the buttonBox's closeButton).
            esc = QShortcut(QKeySequence("Escape"), overlay)
            esc.setAutoRepeat(False)
            esc.setContext(Qt.ShortcutContext.WindowShortcut)
            esc.activated.connect(close_inline)
        except Exception:
            pass

        _state["addcards"] = ac
        _state["overlay"] = overlay
        _state["filter"] = flt

        # Tell the sidebar (rendered inside mw.web) to highlight "Add"
        # instead of "Decks", so the active tab is correct visually.
        try:
            w = getattr(parent_mw, "web", None)
            if w is not None:
                w.eval("window.__baSetActive && window.__baSetActive('add');")
        except Exception:
            pass

        # If AddCards closes from inside (Esc, internal close button), tear
        # down the overlay too. We monkey-patch _close — the legitimate
        # cleanup path — to call our close_inline after.
        try:
            orig_close = ac._close
            def _wrapped_close(orig=orig_close) -> None:
                try:
                    orig()
                finally:
                    if _state.get("addcards") is ac:
                        close_inline()
            ac._close = _wrapped_close  # type: ignore[assignment]
        except Exception:
            pass
    except Exception as e:
        import traceback
        print(
            f"[anki-design.embed] failed: {e}\n{traceback.format_exc()}",
            flush=True,
        )
        # Best-effort cleanup, then fall back to the standalone window.
        try:
            close_inline()
        except Exception:
            pass
        try:
            ac.show()
        except Exception:
            pass
