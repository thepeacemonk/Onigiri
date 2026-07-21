"""
Optional integration with FSRS4Anki Helper
(https://github.com/open-spaced-repetition/fsrs4anki-helper).

FSRS4Anki Helper builds its own submenu under Anki's Tools menu
(`menu_for_helper`) instead of adding a top-toolbar link, so Onigiri's
generic toolbar-capture path in `api/sidebar.py` never sees it. This module
detects the addon and, if present, registers a sidebar entry that reuses
FSRS4Anki Helper's live Tools-menu QMenu as a popup.
"""

import os
import sys

from aqt import mw

from .api import sidebar as sidebar_api

FSRS_HELPER_ADDON_ID = "759844606"
_ENTRY_ID = "fsrs_helper.open_menu"
_COMMAND = "onigiri_open_fsrs_helper_menu"
_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<path fill="currentColor" d="M12 4V1L8 5l4 4V6a6 6 0 1 1-6 6H4a8 8 0 1 0 8-8"/>'
    "</svg>"
)

_installed = False


def is_available() -> bool:
    """Whether FSRS4Anki Helper is installed and enabled."""
    return _is_fsrs_helper_installed()


def _is_fsrs_helper_installed() -> bool:
    try:
        addon_manager = mw.addonManager
        if hasattr(addon_manager, "isEnabled") and not addon_manager.isEnabled(FSRS_HELPER_ADDON_ID):
            return False
        addons_folder = addon_manager.addonsFolder()
    except Exception:
        return False
    return os.path.isdir(os.path.join(addons_folder, FSRS_HELPER_ADDON_ID))


def _get_fsrs_helper_menu():
    module = sys.modules.get(FSRS_HELPER_ADDON_ID)
    return getattr(module, "menu_for_helper", None)


def _open_fsrs_helper_menu(handled, message, context):
    if message != _COMMAND:
        return handled
    try:
        from aqt.qt import QCursor

        menu = _get_fsrs_helper_menu()
        if menu is not None:
            menu.popup(QCursor.pos())
    except Exception as exc:
        print(f"Onigiri: Failed to open FSRS4Anki Helper menu: {exc}")
    return (True, None)


def setup_fsrs_helper_integration() -> None:
    """Registers a sidebar entry for FSRS4Anki Helper if it's installed and enabled."""
    global _installed
    if _installed or not _is_fsrs_helper_installed():
        return

    try:
        from aqt import gui_hooks

        sidebar_api.register_sidebar_action(
            entry_id=_ENTRY_ID,
            label="FSRS4Anki Helper",
            command=_COMMAND,
            icon_svg=_ICON_SVG,
        )
        gui_hooks.webview_did_receive_js_message.append(_open_fsrs_helper_menu)
        _installed = True
    except Exception as exc:
        print(f"Onigiri: Failed to set up FSRS4Anki Helper integration: {exc}")
