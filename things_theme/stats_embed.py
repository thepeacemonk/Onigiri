"""Anki Design — embed the Stats (NewDeckStats) dialog inside the main
window as a "tab".

Mirrors `addcard_embed.py` and `browse_embed.py`. Native Anki opens stats
as a separate QDialog window via `aqt.dialogs.open("NewDeckStats", mw)`.
We want it to behave like a tab next to the sidebar.

Stats is a QDialog (not a QMainWindow), so unlike Browser there's no
centralWidget / menubar / dockWidget split: everything the user sees is
attached to the dialog itself. The cleanest reparent is therefore the
whole dialog — set its window flags to `Widget` and add it to our
overlay's layout. All form widgets (the SvelteKit graphs webview, the
deck chooser, the Close / Save-PDF button row) plus anything add-ons
attach via `gui_hooks.stats_dialog_will_show` come along automatically.

Cleanup is one-shot: `NewDeckStats.reject()` does `self.form.web = None`
and double-calling it crashes, so we guard with a `cleaned` flag.

`Shift+T` (legacy `DeckStats`) is not embedded — it falls through to
the standalone window. The sidebar's Stats item always opens the modern
one.
"""

from __future__ import annotations

from typing import Any

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
    Qt,
    QTimer,
    QVBoxLayout,
)


SIDEBAR_W = 264  # px — matches --rf-side-w in web/theme.css; same as the other embeds


SERIF = '"New York", "Hoefler Text", "Iowan Old Style", Charter, Georgia, serif'
SANS = '"SF Pro Text", "Helvetica Neue", "Segoe UI", system-ui, sans-serif'


def _chrome_qss(palette: dict, accent: str) -> str:
    """QSS for the dialog chrome (everything outside the graphs webview).

    The graphs webview itself gets its own CSS injection via
    `webview_did_inject_style_into_page` in __init__.py so its fonts and
    colors line up with the rest of the redesigned UI."""
    return f"""
QDialog, QFrame#ba-stats-embed {{
    background: {palette['paper']};
    color: {palette['ink']};
    font-family: {SANS};
}}

/* Top header strip — "Statistics" title + the deck chooser inline. */
QFrame#ba-stats-header {{
    background: {palette['paper']};
}}
QLabel#ba-stats-title {{
    color: {palette['ink']};
    font-family: {SERIF};
    font-size: 22pt;
    font-weight: 500;
    letter-spacing: -0.4px;
    padding: 0;
    background: transparent;
}}
QLabel#ba-stats-eyebrow {{
    color: {palette['ink_faint']};
    font-family: {SANS};
    font-size: 8.5pt;
    font-weight: 600;
    letter-spacing: 1.8px;
    text-transform: uppercase;
    padding: 0;
    background: transparent;
}}

/* The bottom strip (deck chooser + Save PDF / Close). */
QDialog QWidget#deckArea, QWidget#deckArea {{
    background: transparent;
}}
#deckArea QLabel {{
    color: {palette['ink_faint']};
    font-family: {SANS};
    font-size: 9.5pt;
    background: transparent;
}}
#deckArea QPushButton {{
    background: transparent;
    border: 1px solid {palette['line2']};
    border-radius: 6px;
    color: {palette['ink']};
    font-family: {SANS};
    font-size: 10.5pt;
    font-weight: 500;
    padding: 5px 12px;
    min-height: 16px;
    text-decoration: none;
}}
#deckArea QPushButton:hover {{
    color: {accent};
    background: {palette['hover']};
    border-color: {palette['ink_faint']};
}}
#deckArea QPushButton:focus {{
    outline: none;
    border-color: {accent};
    color: {accent};
}}

QDialogButtonBox {{
    background: transparent;
}}
QDialogButtonBox QPushButton {{
    background: transparent;
    border: 1px solid {palette['line2']};
    border-radius: 6px;
    color: {palette['ink_dim']};
    font-family: {SANS};
    font-size: 10pt;
    font-weight: 500;
    padding: 6px 16px;
    min-width: 86px;
    min-height: 18px;
}}
QDialogButtonBox QPushButton:hover {{
    color: {palette['ink']};
    background: {palette['hover']};
    border-color: {palette['ink_faint']};
}}
QDialogButtonBox QPushButton:focus {{
    outline: none;
    border-color: {accent};
    color: {palette['ink']};
}}
QDialogButtonBox QPushButton:default {{
    background: {palette['ink']};
    color: {palette['paper']};
    border-color: {palette['ink']};
}}
QDialogButtonBox QPushButton:default:hover {{
    background: {palette['ink_dim']};
    border-color: {palette['ink_dim']};
}}
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


_state: dict = {"stats": None, "overlay": None, "filter": None, "cleaned": False}


def drop_curtain() -> None:
    """Tear down the anti-flash curtain. Safe to call multiple times."""
    c = _state.pop("curtain", None)
    if c is not None:
        try:
            c.deleteLater()
        except Exception:
            pass


def _run_stats_cleanup(sd: Any) -> None:
    """Run NewDeckStats.reject() once. The method is not idempotent —
    it sets `self.form.web = None` and the second call would crash on
    NoneType.cleanup(). We track a single `cleaned` flag in `_state`."""
    if _state.get("cleaned"):
        return
    _state["cleaned"] = True
    try:
        sd.reject()
    except Exception:
        try:
            sd.close()
        except Exception:
            pass


def close_inline() -> None:
    """Tear down the embedded Stats dialog and restore the deck browser.

    No-op if there is no embed currently open."""
    overlay = _state.get("overlay")
    sd = _state.get("stats")
    flt = _state.get("filter")
    if overlay is None and sd is None and flt is None:
        return

    _state["stats"] = None
    _state["overlay"] = None
    _state["filter"] = None
    cw_palette = _state.pop("cw_palette", None)
    curtain = _state.pop("curtain", None)
    if curtain is not None:
        try:
            curtain.deleteLater()
        except Exception:
            pass

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
    if cw_palette is not None:
        try:
            mw.form.centralwidget.setPalette(cw_palette)
        except Exception:
            pass

    if sd is not None:
        _run_stats_cleanup(sd)

    # Reset the cleaned flag for the next open.
    _state["cleaned"] = False

    # Restore the sidebar's active tab.
    try:
        w = getattr(mw, "web", None)
        if w is not None:
            w.eval("window.__baSetActive && window.__baSetActive('decks');")
    except Exception:
        pass


def open_inline(parent_mw: Any = None) -> None:
    """Open NewDeckStats embedded in the main window's content area.

    Falls back to the standalone window if anything goes wrong."""
    parent_mw = parent_mw or mw
    if _state.get("overlay") is not None:
        try:
            _state["overlay"].raise_()
        except Exception:
            pass
        return
    if _state.get("curtain") is not None:
        return

    # --- Curtain ----------------------------------------------------
    from . import addcard as _addcard
    palette, _ = _addcard._resolve_palette()
    paper_qc = QColor(palette["paper"])
    cw = parent_mw.form.centralwidget

    curtain = QFrame(cw)
    curtain.setObjectName("ba-stats-curtain")
    curtain.setAutoFillBackground(True)
    _cu_pal = curtain.palette()
    _cu_pal.setColor(QPalette.ColorRole.Window, paper_qc)
    curtain.setPalette(_cu_pal)
    curtain.setStyleSheet(
        "QFrame#ba-stats-curtain { background: " + palette["paper"] + "; }"
    )
    curtain.setGeometry(SIDEBAR_W, 0, cw.width() - SIDEBAR_W, cw.height())
    curtain.show()
    curtain.raise_()
    _state["curtain"] = curtain
    try:
        curtain.repaint()
        QApplication.processEvents()
    except Exception:
        pass

    try:
        from aqt.stats import NewDeckStats
        # NewDeckStats.__init__ ends with self.show() + self.activateWindow().
        # Subclass to no-op both so the standalone dialog never flashes.
        class _EmbeddedStats(NewDeckStats):  # type: ignore[misc, valid-type]
            def show(self) -> None:  # noqa: D401 — Qt override
                pass

            def activateWindow(self) -> None:  # noqa: D401 — Qt override
                pass

        sd = _EmbeddedStats(parent_mw)
    except Exception:
        try:
            curtain.deleteLater()
        except Exception:
            pass
        _state["curtain"] = None
        try:
            parent_mw.onStats()
        except Exception:
            pass
        return

    try:
        # Register with the dialog manager so other code paths that do
        # `aqt.dialogs.open("NewDeckStats", ...)` find our instance
        # instead of opening a second one. `reject()` (run on close)
        # calls `aqt.dialogs.markClosed("NewDeckStats")` which clears
        # the registration.
        try:
            import aqt as _aqt
            _aqt.dialogs._dialogs["NewDeckStats"][1] = sd  # type: ignore[index]
        except Exception:
            pass

        cfg = _addcard._config()
        accent = cfg.get("accent", "#0077c8")

        overlay = QFrame(parent_mw.form.centralwidget)
        overlay.setObjectName("ba-stats-embed")
        overlay.setAutoFillBackground(True)
        _ov_pal = overlay.palette()
        _ov_pal.setColor(QPalette.ColorRole.Window, paper_qc)
        overlay.setPalette(_ov_pal)
        overlay.setStyleSheet(
            _chrome_qss(palette, accent)
            + "\nQFrame#ba-stats-embed { border-left: 1px solid "
            + palette["line"] + "; }"
        )

        v = QVBoxLayout(overlay)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Top header strip — eyebrow "STATISTICS" label over a serif title
        # echoing the deck name. The title text is filled in once the deck
        # chooser reports the current deck. Mirrors the editorial tone of
        # the deck-browser/homepage header.
        header = QFrame(overlay)
        header.setObjectName("ba-stats-header")
        header.setAutoFillBackground(True)
        _hd_pal = header.palette()
        _hd_pal.setColor(QPalette.ColorRole.Window, paper_qc)
        header.setPalette(_hd_pal)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(40, 28, 40, 22)
        hl.setSpacing(0)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(6)
        eyebrow = QLabel("STATISTICS", header)
        eyebrow.setObjectName("ba-stats-eyebrow")
        title_col.addWidget(eyebrow)
        title = QLabel("Your progress", header)
        title.setObjectName("ba-stats-title")
        title_col.addWidget(title)
        hl.addLayout(title_col, 1)
        v.addWidget(header)

        # Reparent the WHOLE dialog as an embedded widget. Everything the
        # form put on it (web, deck chooser, button box) and anything
        # add-ons attached via stats_dialog_will_show comes along — no
        # need to walk children individually.
        sd.setParent(overlay)
        sd.setWindowFlags(Qt.WindowType.Widget)
        sd.setVisible(True)
        v.addWidget(sd, 1)

        # Mirror the active deck name into the header title.
        # `DeckChooser.selected_deck_name()` is the canonical accessor;
        # we fall back to the chooser's button text if Anki's API moves.
        def _refresh_title() -> None:
            try:
                name = ""
                dc = getattr(sd, "deck_chooser", None)
                if dc is not None:
                    try:
                        name = dc.selected_deck_name() or ""
                    except Exception:
                        name = ""
                if not name:
                    try:
                        btn = sd.form.deckArea.findChild(QPushButton)
                        if btn is not None:
                            name = btn.text() or ""
                    except Exception:
                        pass
                # The button label escapes ampersands as "&&" for Qt
                # mnemonics — undo so the title reads naturally.
                name = name.replace("&&", "&").strip()
                title.setText(name or "Your progress")
            except Exception:
                pass

        _refresh_title()
        try:
            dc = getattr(sd, "deck_chooser", None)
            if dc is not None and hasattr(dc, "on_deck_changed"):
                _orig_changed = dc.on_deck_changed
                def _wrapped_deck_changed(deck_id, _orig=_orig_changed):
                    try:
                        _orig(deck_id)
                    finally:
                        QTimer.singleShot(0, _refresh_title)
                dc.on_deck_changed = _wrapped_deck_changed  # type: ignore[assignment]
        except Exception:
            pass

        # The DeckChooser auto-prepends a "Deck:" QLabel — hide it; the
        # title up top already names what the user is looking at.
        try:
            da = sd.form.deckArea
            for child in da.findChildren(QLabel):
                child.hide()
                break
        except Exception:
            pass

        # The bottom strip (deck chooser + button box) defaults to a
        # tight (16, 6, 16, 6) margin set in stats_qt6.py — bump it so
        # the controls feel like part of an editorial layout, not a
        # crammed dialog footer.
        try:
            sd.form.horizontalLayout_3.setContentsMargins(40, 16, 40, 18)
            sd.form.horizontalLayout_3.setSpacing(14)
        except Exception:
            pass

        # Hijack the Close button (buttonBox.rejected normally routes to
        # NewDeckStats.reject) so clicking Close tears the embed down
        # rather than just closing the inner widget. `close_inline`
        # itself calls reject() during teardown so the cleanup chain
        # still runs.
        try:
            bb = sd.form.buttonBox
            try:
                bb.rejected.disconnect()
            except Exception:
                pass
            bb.rejected.connect(close_inline)
        except Exception:
            pass

        # Tint mw.centralwidget paper so any first-frame Qt gap is invisible.
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
        try:
            curtain.raise_()
        except Exception:
            pass

        # Curtain drop: hook the stats webview's loadFinished + grace,
        # with a hard cap. NewDeckStats also calls
        # `web.hide_while_preserving_layout()` in __init__ which keeps
        # the web blank until the SvelteKit graphs page is ready, so the
        # curtain just covers the very first paint.
        try:
            web = getattr(sd.form, "web", None) if sd.form else None
            if web is not None:
                page = web.page()
                if page is not None:
                    def _on_loaded(_ok: bool) -> None:
                        QTimer.singleShot(280, drop_curtain)
                    page.loadFinished.connect(_on_loaded)
        except Exception:
            pass
        QTimer.singleShot(1500, drop_curtain)

        flt = _EmbedFilter(overlay)
        cw.installEventFilter(flt)

        # Esc closes the embed (NewDeckStats's add_close_shortcut(self)
        # binds Esc to self.close() inside the dialog, but the dialog as
        # an embedded widget no longer receives the same focus chain).
        try:
            esc = QShortcut(QKeySequence("Escape"), overlay)
            esc.setAutoRepeat(False)
            esc.setContext(Qt.ShortcutContext.WindowShortcut)
            esc.activated.connect(close_inline)
        except Exception:
            pass

        _state["stats"] = sd
        _state["overlay"] = overlay
        _state["filter"] = flt
        _state["cleaned"] = False

        # Highlight "Stats" in the sidebar.
        try:
            w = getattr(parent_mw, "web", None)
            if w is not None:
                w.eval(
                    "window.__baSetActive && window.__baSetActive('stats');"
                )
        except Exception:
            pass
    except Exception as e:
        import traceback
        print(
            f"[anki-design.stats_embed] failed: {e}\n"
            f"{traceback.format_exc()}",
            flush=True,
        )
        try:
            close_inline()
        except Exception:
            pass
        try:
            sd.show()
        except Exception:
            pass
