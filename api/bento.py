import json
import os
from typing import Callable, Dict, Optional

from aqt import mw
from aqt.qt import QAction, QMenu

ONIGIRI_ADDON_ID = "1011095603"
BENTO_MENU_OBJECT = "bentoWidgetsMenu"
GAME_ADDONS = {
    "516325516": "Focumon",
    "1799253175": "lofi.town",
    "585575504": "Senchado",
}


def get_version() -> str:
    manifest_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return str(json.load(f).get("version") or "unknown")
    except Exception:
        return "unknown"


def open_settings(page_index: int = 0) -> None:
    from .. import settings

    settings.open_settings(page_index)


def open_gamification_settings(page_name: Optional[str] = None) -> None:
    from .. import gamification_settings

    gamification_settings.open_gamification_settings(page_name)


def get_widget_radius(default: int = 20) -> int:
    try:
        value = mw.col.conf.get("onigiri_canvas_inset_border_radius", default)
        return max(0, min(60, int(value if value not in (None, "") else default)))
    except Exception:
        return default


def _find_bento_menu() -> Optional[QMenu]:
    for action in mw.form.menubar.actions():
        menu = action.menu()
        if menu and menu.objectName() == BENTO_MENU_OBJECT:
            return menu
    return None


def get_bento_menu() -> QMenu:
    menu = _find_bento_menu()
    if menu:
        return menu
    menu = QMenu("Bento Widgets", mw)
    menu.setObjectName(BENTO_MENU_OBJECT)
    mw.form.menubar.addMenu(menu)
    return menu


def _has_marker(menu: QMenu, marker: str) -> bool:
    return any(action.property("bento_marker") == marker for action in menu.actions())


def ensure_bento_shortcut() -> QAction:
    menu = get_bento_menu()
    marker = "onigiri-settings"
    if _has_marker(menu, marker):
        for action in menu.actions():
            if action.property("bento_marker") == marker:
                return action
    if menu.actions():
        menu.addSeparator()
    action = QAction("Onigiri Settings", mw)
    action.setProperty("bento_marker", marker)
    action.triggered.connect(lambda: open_settings(0))
    menu.addAction(action)
    return action


def register_api() -> dict:
    api = {
        "id": ONIGIRI_ADDON_ID,
        "name": "Onigiri",
        "version": get_version(),
        "open_settings": open_settings,
        "open_gamification_settings": open_gamification_settings,
        "get_bento_widgets": get_bento_widgets,
        "get_game_widgets": get_game_widgets,
        "get_widget_radius": get_widget_radius,
    }
    mw.onigiri_api = api
    mw.onigiri_present = True
    mw.onigiri_version = api["version"]
    return api


def _fallback_widget(addon_id: str, name: str) -> Optional[dict]:
    try:
        installed_name = mw.addonManager.addonName(addon_id)
    except Exception:
        installed_name = ""
    if not installed_name:
        return None
    return {
        "id": addon_id,
        "name": name,
        "kind": "game" if addon_id in GAME_ADDONS else "widget",
        "settings_callback": None,
        "open_callback": None,
        "onigiri_detected": True,
    }


def get_bento_widgets() -> Dict[str, dict]:
    widgets = getattr(mw, "bento_widgets", {})
    if not isinstance(widgets, dict):
        widgets = {}
    return widgets


def get_game_widgets() -> Dict[str, dict]:
    widgets = dict(get_bento_widgets())
    games = {}
    for addon_id, name in GAME_ADDONS.items():
        registered = widgets.get(addon_id)
        if registered:
            games[addon_id] = registered
            continue
        fallback = _fallback_widget(addon_id, name)
        if fallback:
            games[addon_id] = fallback
    return games


ONIGIRI_API = register_api()
