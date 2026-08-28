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
    # Folder-named rather than numeric: Byte ships outside AnkiWeb, and Bento
    # keys everything on the add-on folder, which is what its bridge reports.
    "Byte": "Byte",
}


def get_version() -> str:
    manifest_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return str(json.load(f).get("version") or "unknown")
    except Exception:
        return "unknown"


def open_settings(page_index: int = 0) -> None:
    from .. import settings_web

    settings_web.open_settings(page_index)


def open_gamification_settings(page_name: Optional[str] = None) -> None:
    """The Games pages of Onigiri Settings.

    Kept under its old name because other add-ons call it: the standalone
    Gamification window is gone, but "open the gamification settings" still
    means the same thing — it now lands on a page of the one settings dialog.
    Its classic page names ("Onigimon", "Nook Level", …) still resolve."""
    from .. import settings_web

    settings_web.open_settings(page_name or "gamification")


def get_widget_radius(default: int = 20) -> int:
    try:
        value = mw.col.conf.get("onigiri_canvas_inset_border_radius", default)
        return max(0, min(60, int(value if value not in (None, "") else default)))
    except Exception:
        return default


def _css_color_with_alpha(color: str, alpha: float) -> str:
    """Return ``color`` with alpha applied, without relying on renderer internals."""
    color = str(color or "").strip()
    alpha = max(0.0, min(1.0, alpha))
    if color.startswith(("rgba", "rgb")):
        parts = color[color.find("(") + 1:color.rfind(")")].split(",")
        if len(parts) >= 3:
            return f"rgba({parts[0].strip()}, {parts[1].strip()}, {parts[2].strip()}, {alpha:.3f})"
    if color.startswith("#") and len(color) in (4, 7):
        value = color[1:]
        if len(value) == 3:
            value = "".join(char * 2 for char in value)
        try:
            r, g, b = (int(value[index:index + 2], 16) for index in (0, 2, 4))
            return f"rgba({r}, {g}, {b}, {alpha:.3f})"
        except ValueError:
            pass
    return color


def get_widget_effect(theme: str = "light") -> dict:
    """Resolved shared widget chrome for Bento-connected add-ons.

    This is deliberately a small, stable bridge: consumers receive the same
    background alpha, blur conversion, radius and stroke that Onigiri applies
    to its own deck-screen widgets, without importing its renderer internals.
    """
    try:
        from .. import config

        conf = config.get_config_readonly()
        colors = conf.get("colors", {}) if isinstance(conf, dict) else {}
        mode = "dark" if str(theme).lower() in ("dark", "death") else "light"
        palette = colors.get(mode, {}) if isinstance(colors, dict) else {}
        if not isinstance(palette, dict):
            palette = {}

        background = palette.get("--canvas-inset", "#2c2c2c" if mode == "dark" else "#ffffff")
        border_color = palette.get("--border", "#424242" if mode == "dark" else "#e0e0e0")
        blur = max(0, min(100, int(mw.col.conf.get("onigiri_canvas_inset_effect_blur", 0) or 0)))
        opacity = max(0, min(100, int(mw.col.conf.get("onigiri_canvas_inset_effect_opacity", 100) or 100)))
        radius = max(0, min(60, int(mw.col.conf.get("onigiri_canvas_inset_border_radius", 20) or 20)))
        stroke = max(0, min(10, int(mw.col.conf.get("onigiri_canvas_inset_border_width", 1) or 1)))
        alpha = opacity / 100.0
        # Onigiri caps a glass card's fill so the wallpaper remains visible.
        if blur > 0:
            alpha = min(alpha, 0.62)
        return {
            "background": _css_color_with_alpha(background, alpha),
            "border": f"{stroke}px solid {border_color}",
            "blur_px": round((blur / 100.0) * 20, 2),
            "radius": radius,
        }
    except Exception:
        return {}


def get_notification_style(theme: str = "light") -> dict:
    """Return the shared notification surface colors for Bento consumers.

    These values mirror ``web/notifications.css``.  Keeping them behind the
    Bento API lets native widgets, such as controller feedback, match
    Onigiri's notifications without importing its web implementation.
    """
    dark = str(theme).lower() in ("dark", "death")
    accent = "#4da3e8" if dark else "#0077C8"
    try:
        from .. import config

        conf = config.get_config_readonly()
        colors = conf.get("colors", {}) if isinstance(conf, dict) else {}
        palette = colors.get("dark" if dark else "light", {})
        if isinstance(palette, dict):
            accent = palette.get("--accent-color") or accent
    except Exception:
        pass
    return {
        "background": "#2c2c2c" if dark else "#ffffff",
        "text": "#ffffff" if dark else "#2c2c2c",
        "accent": accent,
        "blur_px": 18,
    }


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
        "get_widget_effect": get_widget_effect,
        "get_notification_style": get_notification_style,
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
