"""Python side of the Main Menu web-settings dialog.

Builds the open payload, handles the save round-trip, and bridges the swatch /
icon / background pickers to native Qt while the DOM-overlay dialog stays open.
Replaces `settings.open_settings(0)` as the deck-browser gear icon's target.
"""

import json
import os
import shutil
import uuid

from aqt import mw
from aqt.qt import QFileDialog

from . import config
from . import widget_layout_dialog
from .translations import tr


# --- Config-key allow-lists (see plan: never write a partial/whole-tree blindly) ---

# Keys in the JSON config (settings_{profile}.json) the Main Menu dialog owns.
_JSON_SCALAR_KEYS = [
    "unifiedGridRows",
    "hideRetentionStars",
    "heatmapDefaultView", "heatmapWeekStart",
    "heatmapShowStreak", "heatmapShowMonths", "heatmapShowWeekdays", "heatmapShowWeekHeader",
    "heatmapShape", "heatmapStreakIcon", "heatmapStreakIconColor", "heatmapStreakIconZeroColor",
]

# Per-mode color sub-keys (colors.light / colors.dark) it owns.
_COLOR_KEYS = [
    "--canvas-inset", "--border", "--star-color", "--empty-star-color",
    "--heatmap-color", "--heatmap-color-zero",
]

# Anki collection-config keys it owns (individually set, no overwrite risk).
_COLCONF_KEYS = [
    "modern_menu_statsTitle",
    "onigiri_canvas_inset_color_theme_mode",
    "onigiri_canvas_inset_effect_blur", "onigiri_canvas_inset_effect_opacity",
    "onigiri_canvas_inset_border_radius", "onigiri_canvas_inset_border_width",
    "onigiri_widget_bg_mode", "onigiri_widget_bg_main_effect_mode",
    "onigiri_widget_bg_main_effect_intensity", "onigiri_widget_bg_main_tint_intensity",
    "onigiri_widget_bg_main_tint_color_light", "onigiri_widget_bg_main_tint_color_dark",
    "onigiri_widget_bg_solid_transparency",
    "modern_menu_bg_color_light", "modern_menu_bg_color_dark",
    "modern_menu_background_blur", "modern_menu_background_opacity",
    "modern_menu_bg_color_theme_mode", "modern_menu_background_mode",
    "modern_menu_slideshow_interval", "modern_menu_background_image",
    "modern_menu_icon_retention_star",
]

_COLCONF_DEFAULTS = {
    "modern_menu_statsTitle": "",
    "onigiri_canvas_inset_color_theme_mode": "single",
    "onigiri_canvas_inset_effect_blur": 0,
    "onigiri_canvas_inset_effect_opacity": 100,
    "onigiri_canvas_inset_border_radius": 14,
    "onigiri_canvas_inset_border_width": 1,
    "onigiri_widget_bg_mode": "solid",
    "onigiri_widget_bg_main_effect_mode": "glassmorphism",
    "onigiri_widget_bg_main_effect_intensity": 50,
    "onigiri_widget_bg_main_tint_intensity": 30,
    "onigiri_widget_bg_main_tint_color_light": "#FFFFFF",
    "onigiri_widget_bg_main_tint_color_dark": "#2C2C2C",
    "onigiri_widget_bg_solid_transparency": 0,
    "modern_menu_bg_color_light": "#EEEEEE",
    "modern_menu_bg_color_dark": "#3C3C3C",
    "modern_menu_background_blur": 0,
    "modern_menu_background_opacity": 100,
    "modern_menu_bg_color_theme_mode": "single",
    "modern_menu_background_mode": "image",
    "modern_menu_slideshow_interval": 30,
    "modern_menu_background_image": "",
    "modern_menu_icon_retention_star": "",
}


def _addon_dir():
    return os.path.dirname(__file__)


def _col_conf_get(key, default=None):
    try:
        return mw.col.conf.get(key, default)
    except Exception:
        return default


def _external_hooks_payload():
    """Display-name info for external add-on widgets, for the layout editor's
    archive zone (JS can't compute these — they need live add-on metadata)."""
    hooks = []
    try:
        from . import patcher
        for hook in patcher._get_external_hooks():
            hook_id = patcher._get_hook_name(hook)
            hooks.append({
                "id": hook_id,
                "defaultDisplayName": patcher.get_external_hook_display_name(hook_id, hook_id.split(".")[0]),
            })
    except Exception:
        pass
    return hooks


def _widget_names_payload():
    """Canonical display names for Onigiri widgets, sent to the layout editor."""
    names = {
        "studied":           tr("widget_studied"),
        "time":              tr("widget_time"),
        "pace":              tr("widget_pace"),
        "retention":         tr("widget_retention"),
        "heatmap":           tr("widget_heatmap"),
        "favorites":         tr("widget_favorites"),
        "restaurant_level":  tr("widget_restaurant_level"),
        "onigimon":          "Onigimon",
        "hexagon_land":      "Hexagon Land",
        "deck_stats":        "Deck Stats",
        "prep_station":      tr("widget_study_plans", "Study Plans"),
    }
    try:
        from .gamification import nook_level as _nl
        nook_name = _nl.manager.get_progress().name
        if nook_name:
            names["restaurant_level"] = nook_name
    except Exception:
        pass
    return names


def build_open_payload():
    conf = config.get_config()
    col_conf = {}
    for key in _COLCONF_KEYS:
        col_conf[key] = _col_conf_get(key, _COLCONF_DEFAULTS.get(key))
    try:
        addon_package = mw.addonManager.addonFromModule(__name__)
    except Exception:
        addon_package = __name__.split(".")[0]
    return {
        "json": conf,
        "colConf": col_conf,
        "externalHooks": _external_hooks_payload(),
        "widgets": _widget_names_payload(),
        "config": {"addonPackage": addon_package},
    }


def open_main_menu(context):
    """Open the Main Menu web dialog (deck-browser gear icon target)."""
    try:
        payload = build_open_payload()
        context.web.eval(
            "if(window.OnigiriMainMenuDialog)OnigiriMainMenuDialog.open(%s);"
            % json.dumps(payload, ensure_ascii=True)
        )
    except Exception as e:
        from .onigiri_notifications import notify
        notify(f"Could not open settings: {e}")


# --- Save ---------------------------------------------------------------------

def _clamp(value, lo, hi, fallback):
    try:
        v = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(lo, min(hi, v))


def _save(payload, context):
    draft_json = payload.get("json", {}) or {}
    draft_col = payload.get("colConf", {}) or {}

    # Read a FRESH full tree — never trust the stale payload as the base, and
    # never write a partial dict (write_config overwrites the whole file).
    full = config.get_config()

    # Scalar JSON keys (allow-listed).
    for key in _JSON_SCALAR_KEYS:
        if key in draft_json:
            full[key] = draft_json[key]

    # Color sub-keys, per mode (allow-listed).
    draft_colors = draft_json.get("colors", {}) or {}
    full_colors = full.setdefault("colors", {})
    for mode in ("light", "dark"):
        src = draft_colors.get(mode, {}) or {}
        dst = full_colors.setdefault(mode, {})
        for key in _COLOR_KEYS:
            if key in src and _is_valid_color(src[key]):
                dst[key] = src[key]

    # Widget layout — validated server-side (span/overlap/allow-list) so a JS
    # bug can never corrupt the config file.
    layout_result = widget_layout_dialog.validate_layout(
        draft_json.get("onigiriWidgetLayout"),
        draft_json.get("externalWidgetLayout"),
        draft_json.get("unifiedGridRows"),
    )
    full["onigiriWidgetLayout"] = layout_result["onigiriWidgetLayout"]
    full["externalWidgetLayout"] = layout_result["externalWidgetLayout"]
    full["unifiedGridRows"] = layout_result["unifiedGridRows"]

    # Collection-config keys (allow-listed, set individually).
    for key in _COLCONF_KEYS:
        if key in draft_col:
            mw.col.conf[key] = draft_col[key]

    config.write_config(full)
    try:
        mw.col.setMod()
    except Exception:
        pass


def _is_valid_color(value):
    try:
        from aqt.qt import QColor
        return QColor(str(value)).isValid()
    except Exception:
        return bool(value)


# --- Native picker bridges ----------------------------------------------------

def _pick_color(payload, context):
    from .onigiri_qt_bridge import pick_color_for_webview
    pick_id = payload.get("pickId")
    current = payload.get("current", "#000000")
    hex_value, ok = pick_color_for_webview(current)
    if ok and pick_id:
        context.web.eval(
            "if(window.OnigiriMainMenuDialog)OnigiriMainMenuDialog.applyColorPick(%s, %s);"
            % (json.dumps(pick_id), json.dumps(hex_value))
        )


def _pick_icon(payload, context):
    from .icon_picker import DeckIconPickerDialog
    pick_id = payload.get("pickId")
    current = payload.get("currentIcon") or ""
    color_options = payload.get("colorOptions") or []
    preview_color_key = payload.get("previewColorKey")

    result = {"icon": None, "colors": {}}
    try:
        picker = DeckIconPickerDialog(
            current, _addon_dir(), mw,
            allow_emoji=False,
            color_options=color_options,
            preview_color_key=preview_color_key,
        )
        picker.iconSelected.connect(lambda value: result.__setitem__("icon", value))
        picker.colorsChanged.connect(lambda values: result.__setitem__("colors", dict(values)))
        picker.exec()
    except Exception as e:
        from .onigiri_notifications import notify
        notify(f"Icon picker error: {e}")
        return
    finally:
        try:
            mw.raise_()
            mw.activateWindow()
        except Exception:
            pass

    if pick_id and (result["icon"] is not None or result["colors"]):
        context.web.eval(
            "if(window.OnigiriMainMenuDialog)OnigiriMainMenuDialog.applyIconPick(%s, %s);"
            % (json.dumps(pick_id), json.dumps(result))
        )


def _import_bg(payload, context):
    source_path, _ = QFileDialog.getOpenFileName(
        mw, "Import Background", "", "Images (*.png *.jpg *.jpeg *.gif *.webp)"
    )
    if not source_path:
        return
    dest_dir = os.path.join(_addon_dir(), "user_files", "main_bg")
    os.makedirs(dest_dir, exist_ok=True)
    ext = os.path.splitext(source_path)[1].lower() or ".png"
    new_name = f"{uuid.uuid4().hex}{ext}"
    try:
        shutil.copyfile(source_path, os.path.join(dest_dir, new_name))
    except Exception as e:
        from .onigiri_notifications import notify
        notify(f"Import failed: {e}")
        return
    context.web.eval(
        "if(window.OnigiriMainMenuDialog)OnigiriMainMenuDialog.applyBackgroundPick(%s);"
        % json.dumps({"filename": new_name})
    )
    try:
        mw.raise_()
        mw.activateWindow()
    except Exception:
        pass


def _open_gallery(payload, context):
    from .onigiri_qt_bridge import pick_gallery_background_for_webview
    filename = pick_gallery_background_for_webview()
    if filename:
        context.web.eval(
            "if(window.OnigiriMainMenuDialog)OnigiriMainMenuDialog.applyBackgroundPick(%s);"
            % json.dumps({"filename": filename})
        )


# --- pycmd dispatch -----------------------------------------------------------

def handle_cmd(cmd, context):
    """Handle any `onigiri_mainmenu_*` pycmd. Returns (handled, None)."""
    try:
        if cmd.startswith("onigiri_mainmenu_save:"):
            payload = json.loads(_arg(cmd))
            _save(payload, context)
            from .refresh import schedule_ui_refresh
            context.web.eval("if(window.OnigiriMainMenuDialog)OnigiriMainMenuDialog.close();")
            schedule_ui_refresh()
            return (True, None)

        if cmd.startswith("onigiri_mainmenu_pick_color:"):
            _pick_color(json.loads(_arg(cmd)), context)
            return (True, None)

        if cmd.startswith("onigiri_mainmenu_pick_icon:"):
            _pick_icon(json.loads(_arg(cmd)), context)
            return (True, None)

        if cmd.startswith("onigiri_mainmenu_import_bg:"):
            _import_bg(json.loads(_arg(cmd) or "{}"), context)
            return (True, None)

        if cmd.startswith("onigiri_mainmenu_open_gallery:"):
            _open_gallery(json.loads(_arg(cmd) or "{}"), context)
            return (True, None)
    except Exception as e:
        from .onigiri_notifications import notify
        notify(f"Settings error: {e}")
        return (True, None)

    return (False, None)


def _arg(cmd):
    from urllib.parse import unquote
    return unquote(cmd.split(":", 1)[1]) if ":" in cmd else ""
