"""Qt-picker bridges for the deck-browser web dialogs.

Web dialogs (Main Menu Settings, etc.) live as DOM overlays inside the deck
browser's AnkiWebView, not as top-level Qt windows. When they need to open a
custom-painted Qt popup (OnigiriColorDialog's palette, a gallery dialog), that
popup would render *behind* the AnkiWebView's native surface unless it's hosted
in its own translucent, always-on-top top-level window.

This module generalizes the one-off trick from hashi_notes.py:_open_color_dialog
into a single reusable context manager plus thin picker wrappers, so the flicker-
prone Qt-window juggling lives in exactly one place.

Note: DeckIconPickerDialog does NOT need this — it already sets
FramelessWindowHint | WindowStaysOnTopHint + WA_TranslucentBackground on itself,
so callers invoke it directly (see main_menu_dialog.py).
"""

import os
from contextlib import contextmanager

from aqt import mw
from aqt.qt import QWidget, Qt

from .onigiri_color_picker import OnigiriColorDialog


@contextmanager
def with_translucent_host(geometry_source=None):
    """Yield a bare translucent always-on-top QWidget covering geometry_source
    (defaults to mw), for hosting Qt popups that must float above an
    AnkiWebView. Torn down — and focus restored to mw — on exit."""
    host = QWidget(None)
    host.setWindowFlags(
        Qt.WindowType.Tool
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
    )
    host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    try:
        host.setGeometry((geometry_source or mw).frameGeometry())
    except Exception:
        pass
    host.show()
    host.raise_()
    host.activateWindow()
    try:
        yield host
    finally:
        try:
            host.close()
            host.deleteLater()
        except Exception:
            pass
        try:
            if mw:
                mw.raise_()
                mw.activateWindow()
        except Exception:
            pass


def pick_color_for_webview(current_hex):
    """Open Onigiri's color picker over the deck browser. Returns
    (hex, accepted). anchor=None makes the popup position itself relative to
    the cursor, so no swatch screen coordinates need to be passed from JS."""
    with with_translucent_host() as host:
        return OnigiriColorDialog.getColor(current_hex, host)


def _main_bg_dir():
    return os.path.join(os.path.dirname(__file__), "user_files", "main_bg")


def _main_bg_image_files():
    path = _main_bg_dir()
    try:
        return sorted(
            f for f in os.listdir(path)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
        )
    except OSError:
        return []


def pick_gallery_background_for_webview():
    """Open a minimal standalone gallery of the images already in
    user_files/main_bg/ and return the chosen filename (or None).

    Deliberately self-contained: the full Settings-dialog gallery couples to
    slideshow/dynamic/badge state that doesn't apply to the web dialog's
    single-image background model, so this is a plain pick-one picker.
    """
    from aqt.qt import (
        QDialog, QVBoxLayout, QScrollArea, QFrame, QWidget as _QWidget,
    )
    from .ui_widgets import FlowLayout
    from .settings._widgets import BackgroundGalleryTile

    files = _main_bg_image_files()
    if not files:
        return None

    result = {"filename": None}
    with with_translucent_host() as host:
        dialog = QDialog(host)
        dialog.setWindowTitle("Select from your Gallery")
        dialog.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        dialog.resize(760, 520)
        dialog.setStyleSheet("QDialog { background: #242424; border: 1px solid #2c2c2c; border-radius: 12px; }")

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = _QWidget()
        grid = FlowLayout(content, margin=0, spacing=10)

        def on_click(filename):
            result["filename"] = filename
            dialog.accept()

        for filename in files:
            image_path = os.path.join(_main_bg_dir(), filename)
            tile = BackgroundGalleryTile(filename, image_path, "#3b82f6")
            tile.clicked.connect(on_click)
            grid.addWidget(tile)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        dialog.exec()

    return result["filename"]
