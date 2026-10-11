"""Anki Design — embed the card Browser inside the main window as a "tab".

Mirrors `addcard_embed.py` exactly. The user wants Browse to behave like a
tab next to the sidebar instead of opening as a separate QMainWindow:

  - The sidebar's `ba:browse` pycmd calls `open_inline(mw)` (see
    `__init__.py`) instead of `mw.onBrowse()`.
  - `open_inline` constructs a Browser instance (we no-op `.show()` on
    a subclass so its standalone window never flashes on screen).
  - We grab its `centralWidget` and reparent it onto an overlay QFrame
    placed on top of `mw.form.centralwidget`, offset by the sidebar width
    so the sidebar rendered inside `mw.web` stays visible to the left.
  - The Browser window itself stays hidden (its widgets remain alive, so
    all menubar actions, shortcuts, and add-on hooks continue to work).
  - The overlay resizes with the main window via an installed event
    filter.
  - We register our instance with `aqt.dialogs` so any other code path
    that does `aqt.dialogs.open("Browser", ...)` finds our existing
    Browser and calls `reopen()` on it instead of opening a second one.

This is a first cut: the chrome is whatever Anki's stock browser uses.
Visual redesign is intentionally deferred — the user wants the layout
moved in as-is first.
"""

from __future__ import annotations

from typing import Any

from aqt import mw
from aqt.qt import (
    QApplication,
    QColor,
    QDockWidget,
    QEvent,
    QFrame,
    QKeySequence,
    QObject,
    QPalette,
    QShortcut,
    QSplitter,
    Qt,
    QTimer,
    QVBoxLayout,
)


SIDEBAR_W = 264  # px — matches --rf-side-w in web/theme.css; same as addcard_embed

# Browser sidebar (the tag/decks tree inside the embedded Browser). The
# Anki default of ~240px gets visibly squeezed on small windows because
# QSplitter scales setSizes() proportionally — pin a comfortable preferred
# width and a hard minimum so it can't shrink past readability.
SIDEBAR_DOCK_PREF = 280
SIDEBAR_DOCK_MIN = 220
SIDEBAR_DOCK_MAX = 480  # past this the central pane (table + editor) starts to look empty
CENTRAL_MIN = 420  # search + card table + editor pane need this much

# Inner Browser splitter (search+table | editor). Anki's restoreSplitter
# call ("editor3") often hands back [all, 0] for a fresh profile, which
# leaves the editor pane invisible — and setChildrenCollapsible(False)
# doesn't save us because the editor container (verticalLayoutWidget) has
# no minimum width, so QSplitter happily shrinks it past zero. We give
# the editor side a real minimum and force a sensible initial split.
EDITOR_MIN = 320   # narrowest the field area stays legible
EDITOR_PREF = 460  # default share on first open
TABLE_MIN = 360    # card table + search bar need at least this much


def _clamp_splitter(splitter: "QSplitter", central: Any) -> None:
    """Re-set sizes after a drag so the docks stay within [MIN, MAX] AND
    the handles sit flush against their widgets. Without this the handle
    can drag past a dock's maxWidth, leaving a dead empty band of overlay
    background between the dock and the centre pane."""
    try:
        count = splitter.count()
        sizes = list(splitter.sizes())
        avail = splitter.width() - splitter.handleWidth() * max(0, count - 1)
        sidebar_total = 0
        for i in range(count):
            w = splitter.widget(i)
            if w is central:
                continue
            sizes[i] = max(SIDEBAR_DOCK_MIN, min(SIDEBAR_DOCK_MAX, sizes[i]))
            sidebar_total += sizes[i]
        for i in range(count):
            if splitter.widget(i) is central:
                sizes[i] = max(CENTRAL_MIN, avail - sidebar_total)
        # Only re-set if anything actually changed (avoid signal loop).
        if sizes != list(splitter.sizes()):
            splitter.blockSignals(True)
            try:
                splitter.setSizes(sizes)
            finally:
                splitter.blockSignals(False)
    except Exception:
        pass


def _apply_inner_split(inner: "QSplitter") -> None:
    """Force a sensible [table | editor] split on the Browser's inner
    splitter. Deferred via QTimer so inner.width() reflects the laid-out
    overlay, not the construction-time 640px default. Without this the
    editor pane shows up at 0px wide and looks 'missing'."""

    def _set() -> None:
        try:
            avail = inner.width() - inner.handleWidth()
            if avail <= 0:
                return
            editor_w = max(EDITOR_MIN, min(EDITOR_PREF, avail // 2))
            table_w = max(TABLE_MIN, avail - editor_w)
            inner.setSizes([table_w, editor_w])
        except Exception:
            pass

    QTimer.singleShot(0, _set)


def _apply_initial_splitter_sizes(splitter: "QSplitter", central: Any) -> None:
    """Set initial splitter sizes from the overlay's actual width so a
    narrow window doesn't end up with a 100px sidebar after QSplitter
    proportionally scales setSizes(). Deferred via QTimer.singleShot(0)
    so the overlay has been laid out and width() is meaningful."""

    def _set() -> None:
        try:
            count = splitter.count()
            handles = max(0, count - 1) * splitter.handleWidth()
            avail = max(0, splitter.width() - handles)
            non_central = count - 1
            sidebars = min(SIDEBAR_DOCK_PREF, max(SIDEBAR_DOCK_MIN, (avail - CENTRAL_MIN) // max(1, non_central)))
            central_w = max(CENTRAL_MIN, avail - sidebars * non_central)
            sizes = []
            for i in range(count):
                if splitter.widget(i) is central:
                    sizes.append(central_w)
                else:
                    sizes.append(sidebars)
            splitter.setSizes(sizes)
        except Exception:
            pass

    QTimer.singleShot(0, _set)


def _palette_styles() -> str:
    """QSS for the overlay frame. The Browser's own internals carry their
    Qt-native styles — we just paint the wrapper paper-colored so the gap
    between sidebar and embed reads as one continuous page."""
    from . import addcard as _addcard
    palette, _ = _addcard._resolve_palette()
    return (
        "QFrame#ba-browse-embed { background: " + palette["paper"] + "; "
        "border-left: 1px solid " + palette["line"] + "; }"
    )


class _EmbedFilter(QObject):
    """Re-positions the embed overlay whenever the main window is resized.
    Also re-applies the sidebar clamp so QSplitter's proportional resize
    can't drag the sidebar past SIDEBAR_DOCK_MAX into the empty-gap state."""

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
            sp = _state.get("splitter")
            c = _state.get("central")
            if sp is not None and c is not None:
                _clamp_splitter(sp, c)
        return False


_state: dict = {"browser": None, "overlay": None, "filter": None}


def drop_curtain() -> None:
    """Tear down the anti-flash curtain. Safe to call multiple times."""
    c = _state.pop("curtain", None)
    if c is not None:
        try:
            c.deleteLater()
        except Exception:
            pass


def close_inline() -> None:
    """Tear down the embedded Browser and restore the deck browser.

    No-op if there is no embed currently open — callers (state-change
    monkey-patches, sidebar `decks` pycmd) can call this cheaply on
    every navigation event."""
    overlay = _state.get("overlay")
    br = _state.get("browser")
    flt = _state.get("filter")
    if overlay is None and br is None and flt is None:
        return

    # Clear state FIRST so anything that re-enters via a close callback
    # returns immediately.
    _state["browser"] = None
    _state["overlay"] = None
    _state["filter"] = None
    _state.pop("splitter", None)
    _state.pop("central", None)
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

    if br is not None:
        # Synchronous cleanup. Browser's `_closeWindow()` is the same
        # path its closeEvent ends up taking after the
        # call_after_note_saved roundtrip — we skip the roundtrip
        # because we don't have a webview-driven submit flow here.
        try:
            br._closeWindow()  # type: ignore[attr-defined]
        except Exception:
            try:
                br.close()
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
    """Open the Browser embedded in the main window's content area.

    Falls back to the standalone Browser window if the embed setup
    fails for any reason."""
    parent_mw = parent_mw or mw
    if _state.get("overlay") is not None:
        # Already open — bring it forward.
        try:
            _state["overlay"].raise_()
        except Exception:
            pass
        return
    if _state.get("curtain") is not None:
        # A curtain is up — we're already mid-open from a previous call.
        return

    # --- Curtain ----------------------------------------------------
    from . import addcard as _addcard
    palette, _ = _addcard._resolve_palette()
    paper_qc = QColor(palette["paper"])
    cw = parent_mw.form.centralwidget

    curtain = QFrame(cw)
    curtain.setObjectName("ba-browse-curtain")
    curtain.setAutoFillBackground(True)
    _cu_pal = curtain.palette()
    _cu_pal.setColor(QPalette.ColorRole.Window, paper_qc)
    curtain.setPalette(_cu_pal)
    curtain.setStyleSheet(
        "QFrame#ba-browse-curtain { background: " + palette["paper"] + "; }"
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
        from aqt.browser import Browser
        # Anki's Browser.__init__ ends with `self.show()`, which would
        # flash the standalone QMainWindow on screen for one paint.
        # Subclassing to no-op `show()` keeps it invisible.
        class _EmbeddedBrowser(Browser):  # type: ignore[misc, valid-type]
            def show(self) -> None:  # noqa: D401 — Qt override
                pass
        br = _EmbeddedBrowser(parent_mw)
    except Exception:
        try:
            curtain.deleteLater()
        except Exception:
            pass
        _state["curtain"] = None
        try:
            parent_mw.onBrowse()
        except Exception:
            pass
        return

    try:
        # Register with the dialog manager so future
        # `aqt.dialogs.open("Browser", ...)` calls reopen() our instance
        # instead of creating a second Browser. _closeWindow() (called
        # from close_inline) calls dialogs.markClosed("Browser") which
        # tears this registration down.
        try:
            import aqt as _aqt
            _aqt.dialogs._dialogs["Browser"][1] = br  # type: ignore[index]
        except Exception:
            pass

        central = br.centralWidget()

        # Inner splitter inside central: [search+table | editor]. Three
        # things have to be true for the editor pane to behave like a real
        # sidebar:
        #
        #   1. It needs a meaningful minimum width — its parent widget
        #      (verticalLayoutWidget) has min=0 in Anki's .ui, so
        #      setChildrenCollapsible(False) doesn't actually stop a drag
        #      from shrinking the editor to zero.
        #   2. The initial split has to be non-degenerate — restoreSplitter
        #      ("editor3") routinely hands back [all, 0] for fresh profiles
        #      and the editor disappears on open.
        #   3. The pane has to stay visible across selection changes —
        #      Browser.on_all_or_selected_rows_changed calls
        #      `splitter.widget(1).setVisible(self.singleCard)` via the
        #      @ensure_editor_saved decorator, which defers the call
        #      through Editor.call_after_note_saved. Overriding the method
        #      can't catch that race, so we patch setVisible on the widget
        #      itself to ignore False.
        try:
            inner = getattr(br.form, "splitter", None)
            if (
                inner is not None
                and inner.count() == 2
                and inner.orientation() == Qt.Orientation.Horizontal
            ):
                table_side = inner.widget(0)
                editor_side = inner.widget(1)
                table_side.setMinimumWidth(TABLE_MIN)
                editor_side.setMinimumWidth(EDITOR_MIN)
                # Pin both the splitter pane AND the editor's own widget
                # (Editor.set_note(None, hide=True) calls self.widget.hide()
                # — which in Browser mode is self.form.fieldsArea — so even
                # with the splitter pane forced visible, fieldsArea would
                # collapse to invisible whenever the selection cleared).
                for w in (editor_side, getattr(br.form, "fieldsArea", None)):
                    if w is None:
                        continue
                    _orig = w.setVisible

                    def _keep_visible(_v: bool, _f=_orig) -> None:
                        _f(True)

                    w.setVisible = _keep_visible  # type: ignore[assignment]
                    w.setVisible(True)
                _apply_inner_split(inner)
        except Exception:
            pass

        # Browser attaches its sidebar tree (decks / tags / saved searches)
        # as a QDockWidget directly to the QMainWindow, NOT inside
        # centralwidget. Discover every QDockWidget child so add-ons that
        # add their own docks are also brought along, and group them by
        # the dock area Browser placed them in.
        left_docks: list = []
        right_docks: list = []
        for dock in br.findChildren(QDockWidget):
            try:
                area = br.dockWidgetArea(dock)
            except Exception:
                area = Qt.DockWidgetArea.LeftDockWidgetArea
            inner = dock.widget()
            if inner is None:
                continue
            if area == Qt.DockWidgetArea.RightDockWidgetArea:
                right_docks.append(inner)
            else:
                # Treat anything that isn't explicitly right (left, top,
                # bottom, no-area) as left, matching the Browser's stock
                # placement of the sidebar.
                left_docks.append(inner)

        overlay = QFrame(parent_mw.form.centralwidget)
        overlay.setObjectName("ba-browse-embed")
        overlay.setAutoFillBackground(True)
        _ov_pal = overlay.palette()
        _ov_pal.setColor(QPalette.ColorRole.Window, paper_qc)
        overlay.setPalette(_ov_pal)
        overlay.setStyleSheet(_palette_styles())

        v = QVBoxLayout(overlay)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Layout: [left docks] | [centralwidget: search+table | editor] |
        # [right docks], wrapped in a QSplitter so each boundary stays
        # drag-resizable — matching the QDockWidget UX in native Browser.
        central.setParent(None)
        central.setWindowFlags(Qt.WindowType.Widget)

        if left_docks or right_docks:
            splitter = QSplitter(Qt.Orientation.Horizontal, overlay)
            splitter.setChildrenCollapsible(False)
            splitter.setHandleWidth(6)
            splitter.setStyleSheet(
                "QSplitter::handle { background: " + palette["line"] + "; }"
                "QSplitter::handle:hover { background: "
                + palette["line2"] + "; }"
            )
            # Use min/max width on the dock contents AND clamp via
            # splitterMoved — Qt respects min/max for widget size but lets the
            # handle drag past max, leaving a dead visual gap. The signal
            # handler re-sets sizes so the handle snaps to where it should.
            for inner in left_docks:
                inner.setParent(None)
                inner.setMinimumWidth(SIDEBAR_DOCK_MIN)
                inner.setMaximumWidth(SIDEBAR_DOCK_MAX)
                splitter.addWidget(inner)
            central.setMinimumWidth(CENTRAL_MIN)
            splitter.addWidget(central)
            for inner in right_docks:
                inner.setParent(None)
                inner.setMinimumWidth(SIDEBAR_DOCK_MIN)
                inner.setMaximumWidth(SIDEBAR_DOCK_MAX)
                splitter.addWidget(inner)
            splitter.splitterMoved.connect(
                lambda *_a, sp=splitter, c=central: _clamp_splitter(sp, c)
            )
            _state["central"] = central
            for i in range(splitter.count()):
                splitter.setStretchFactor(
                    i, 1 if splitter.widget(i) is central else 0
                )
            v.addWidget(splitter, 1)
            _state["splitter"] = splitter
            _apply_initial_splitter_sizes(splitter, central)
        else:
            central.setParent(overlay)
            v.addWidget(central, 1)

        # Hide the original Browser QMainWindow.
        br.setVisible(False)

        # Tint mw.centralwidget paper so any Qt-painted gap is invisible.
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

        # Curtain drop: backstop on editor webview load + grace, hard cap.
        try:
            web = getattr(br.editor, "web", None) if br.editor else None
            if web is not None:
                page = web.page()
                if page is not None:
                    def _on_loaded(_ok: bool) -> None:
                        QTimer.singleShot(280, drop_curtain)
                    page.loadFinished.connect(_on_loaded)
        except Exception:
            pass
        QTimer.singleShot(900, drop_curtain)

        flt = _EmbedFilter(overlay)
        cw.installEventFilter(flt)

        # Esc closes the embed. Browser binds its own Esc inside
        # keyPressEvent on the QMainWindow, but our QMainWindow is
        # hidden so it never gets focus events.
        try:
            esc = QShortcut(QKeySequence("Escape"), overlay)
            esc.setAutoRepeat(False)
            esc.setContext(Qt.ShortcutContext.WindowShortcut)
            esc.activated.connect(close_inline)
        except Exception:
            pass

        _state["browser"] = br
        _state["overlay"] = overlay
        _state["filter"] = flt

        # Highlight "Browse" in the sidebar.
        try:
            w = getattr(parent_mw, "web", None)
            if w is not None:
                w.eval(
                    "window.__baSetActive && window.__baSetActive('browse');"
                )
        except Exception:
            pass
    except Exception as e:
        import traceback
        print(
            f"[anki-design.browse_embed] failed: {e}\n"
            f"{traceback.format_exc()}",
            flush=True,
        )
        try:
            close_inline()
        except Exception:
            pass
        try:
            br.show()
        except Exception:
            pass
