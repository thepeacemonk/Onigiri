from aqt import mw
from aqt.qt import QTimer

_refresh_pending = False


def schedule_ui_refresh(delay_ms: int = 150) -> None:
    """Refresh the visible Anki surface after dialogs close, without a full mw.reset()."""
    global _refresh_pending
    if _refresh_pending:
        return
    _refresh_pending = True
    QTimer.singleShot(delay_ms, _refresh_visible_surface)


def _refresh_visible_surface() -> None:
    global _refresh_pending
    _refresh_pending = False

    try:
        from . import patcher

        patcher.patch_overview()
    except Exception:
        pass

    state = getattr(mw, "state", "")

    try:
        if state == "deckBrowser" and getattr(mw, "deckBrowser", None):
            deck_browser = mw.deckBrowser
            if hasattr(deck_browser, "refresh"):
                deck_browser.refresh()
            elif hasattr(deck_browser, "_renderPage"):
                deck_browser._renderPage()
        elif state == "overview" and getattr(mw, "overview", None):
            overview = mw.overview
            if hasattr(overview, "refresh"):
                overview.refresh()
        elif state == "review" and getattr(mw, "reviewer", None):
            try:
                patcher.apply_reviewer_bottom_bar_height()
            except Exception:
                pass
    except Exception:
        pass

    try:
        if getattr(mw, "toolbar", None):
            mw.toolbar.draw()
    except Exception:
        pass
