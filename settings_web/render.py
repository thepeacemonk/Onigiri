# HTML/context rendering for the WebUI settings dialog.
#
# Keeps every Python-side concern the page needs — palette tokens, icon data
# URIs, @font-face rules, the field/page schema and its current values — in one
# JSON blob injected into web/settings.html. The page itself never touches
# Anki's own CSS variables (see the shared --odlg-* token rule).

import base64
import copy
import json
import os
import time

from aqt import mw
from aqt.theme import theme_manager

from ..core import config
from ..rendering.theme_palette import chrome_palette
from ..ui_kit.fonts import FONTS, get_all_fonts, poppins_font_face_css
from ..core.translations import TRANSLATIONS, current_language, localized_default, tr, web_localization_script, literal_strings
from . import gallery, schema, theme_store

ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM_ICON_DIRS = (
    # available_for_users first: on a same-name collision (e.g. square.svg
    # exists in both), this must resolve the same file heatmap.py's own
    # system_icon_path() picks (it checks available_for_users first) — a
    # picker value only ever comes from the user-facing set anyway.
    os.path.join(ADDON_ROOT, "system_files", "system_icons", "available_for_users"),
    os.path.join(ADDON_ROOT, "system_files", "system_icons", "unavailable_for_users"),
    os.path.join(ADDON_ROOT, "system_files", "system_icons"),
)


# ── palette ────────────────────────────────────────────────────────────────────

def is_dark():
    try:
        return bool(config.effective_night_mode())
    except Exception:
        return bool(theme_manager.night_mode)


def accent_color(conf=None):
    conf = conf if conf is not None else config.get_config_readonly()
    mode = "dark" if is_dark() else "light"
    try:
        return conf["colors"][mode].get("--accent-color") or config.DEFAULT_ACCENT_COLOR
    except Exception:
        return config.DEFAULT_ACCENT_COLOR


def palette(dark):
    """Settings keeps neutral chrome; only its accent follows the theme."""
    mode = "dark" if dark else "light"
    return chrome_palette(
        config.get_config_readonly().get("colors", {}).get(mode, {}), dark
    )


# ── assets ─────────────────────────────────────────────────────────────────────

def addon_package():
    try:
        return mw.addonManager.addonFromModule(__name__)
    except Exception:
        return os.path.basename(ADDON_ROOT)


def addon_uri(rel_from_root):
    return f"/_addons/{addon_package()}/{rel_from_root.lstrip('/')}"


def read_web_asset(name):
    path = os.path.join(ADDON_ROOT, "web", name)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except Exception as exc:  # noqa: BLE001 - surfaced in the dialog body
        print(f"[Onigiri] settings_web: could not read web/{name}: {exc}")
        return ""


def read_things_asset(name):
    """Read a Kome production asset for its isolated Settings preview."""
    path = os.path.join(ADDON_ROOT, "things_theme", "web", name)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except Exception as exc:  # noqa: BLE001 - the preview has a safe fallback
        print(f"[Onigiri] settings_web: could not read Kome {name}: {exc}")
        return ""


def _icon_path(filename):
    if not filename:
        return ""
    filename = os.path.basename(str(filename))
    for directory in SYSTEM_ICON_DIRS:
        candidate = os.path.join(directory, filename)
        if os.path.exists(candidate):
            return candidate
    return ""


def icon_svg(filename):
    """Inline SVG markup so icons can be recoloured with currentColor.

    Anki's media server would serve these fine, but an <img> cannot inherit the
    page's text colour, and every icon here needs to follow the theme."""
    path = _icon_path(filename)
    if not path:
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            svg = handle.read()
    except Exception:
        return ""
    if "currentColor" not in svg:
        svg = svg.replace("<svg", '<svg fill="currentColor"', 1)
    return svg.strip()


def icon_data_uri(filename):
    path = _icon_path(filename)
    if not path:
        return ""
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except Exception:
        return ""
    return "data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii")


def font_face_css():
    """@font-face for Poppins plus every selectable font, so the font picker
    chips and previews render in the real typeface."""
    package = addon_package()
    faces = [poppins_font_face_css(package)]
    for key, info in get_all_fonts(ADDON_ROOT).items():
        filename = (info or {}).get("file")
        family = (info or {}).get("family")
        if not filename or not family:
            continue
        if key in FONTS:
            url = addon_uri(f"system_files/fonts/system_fonts/{filename}")
        else:
            url = addon_uri(f"user_files/fonts/{filename}")
        faces.append(
            "@font-face{font-family:%s;src:url('%s');font-display:swap;}"
            % (json.dumps(family), url)
        )
    return "".join(faces)


# ── context ────────────────────────────────────────────────────────────────────

STRING_KEYS = (
    "save", "search", "general", "menu", "study_pages", "donate", "report_bugs",
    "profile", "modes", "languages", "fonts", "themes", "gallery", "sync_button",
    "main_menu", "sidebar", "overviewer", "reviewer", "restore_default",
    "light_mode", "dark_mode",
    # Overview-style preview mock-up.
    "title", "congrats_message", "congratulations", "one_learning_card_ready_now",
    "preview_day_streak", "preview_next_learning_card", "preview_due_later_today",
    "lstats_new", "learning", "to_review",
)


def _strings():
    out = dict(TRANSLATIONS[current_language()])
    out.update({key: tr(key) for key in STRING_KEYS})
    out["cancel"] = tr("cancel")
    out["collapse_sidebar"] = tr("settings_web_collapse_rail", "Collapse sidebar")
    out["expand_sidebar"] = tr("settings_web_expand_rail", "Pin sidebar open")
    # Auto-save has no Save button, so these strings are the only feedback.
    out["autosave_idle"] = tr("settings_web_autosave_idle", "Changes save automatically")
    out["autosave_saving"] = tr("settings_web_autosave_saving", "Saving…")
    out["autosave_saved"] = tr("settings_web_autosave_saved", "Saved")
    out["autosave_error"] = tr("settings_web_autosave_error", "Could not save")
    out["done"] = tr("settings_web_done", "Done")
    out["simple"] = tr("settings_simple", "Simple")
    out["advanced"] = tr("settings_advanced", "Advanced")
    out["simple_mode_notice"] = tr(
        "settings_web_simple_mode_notice",
        "Simple Mode hides some Onigiri customization options. Switch to Advanced to see them all.",
    )
    # Languages page.
    out["lang_preview"] = tr("settings_web_lang_preview", "Preview")
    out["lang_active"] = tr("settings_web_lang_active", "Active")
    # Modes page: the Focus/Flow/Zen ladder.
    out["immersion"] = tr("settings_web_immersion", "Immersion")
    out["immersion_off"] = tr("settings_web_immersion_off", "Off")
    out["immersion_off_caption"] = tr(
        "settings_web_immersion_off_caption", "Anki looks the way it always does."
    )
    out["immersion_hint"] = tr(
        "settings_web_immersion_hint",
        "Each level contains the one before it — turning one on turns on everything below.",
    )
    out["modes_extras"] = tr("settings_web_modes_extras", "Independent")
    out["font_preview"] = tr("font_preview", "Preview")
    out["font_preview_text"] = tr("font_preview_text", "The quick brown fox jumps over the lazy dog. 1234567890")
    out["import_button"] = tr("settings_web_import_button", "Import")
    out["preview"] = tr("preview", "Preview")
    out["profile_tab_page"] = tr("profile_tab_page", "Profile Sidebar")
    out["profile_tab_picture"] = tr("profile_tab_picture", "Profile Picture")
    out["profile_tab_background"] = tr("profile_tab_background", "Background")
    out["profile_tab_colors_font"] = tr("profile_tab_colors_font", "Colors & Font")
    # Preview-header controls.
    out["dynamic_mode"] = tr("dynamic_mode", "Dynamic mode")
    out["reset"] = tr("reset", "Reset")
    out["widget_grid"] = tr("widget_grid_title", "Widget grid")
    out["organize_grid_help_title"] = tr(
        "organize_grid_help_title", "Arrange your widgets"
    )
    out["organize_grid_drag_help"] = tr(
        "organize_grid_drag_help",
        "Drag and drop widgets in the grid to arrange your Main Menu.",
    )
    out["organize_grid_multiselect_help"] = tr(
        "organize_grid_multiselect_help",
        "Shift+Click widgets to select several, then drag one to move "
        "them together.",
    )
    out["hold_to_confirm"] = tr("settings_web_hold_to_confirm", "Hold for 3 seconds to continue")
    out["games_action_failed"] = tr("settings_web_games_action_failed", "Could not complete that action.")
    # Duration field's unit chips (Slide Interval).
    # Widget Color and Effect's sample card: the three font roles it draws.
    out["titles"] = tr("titles", "Title")
    out["small_titles"] = tr("small_titles", "Small titles")
    out["information"] = tr("information", "Information")
    # Picture/colour slot captions: which theme the slot feeds.
    out["theme_light_mode"] = tr("theme_light_mode", "Light mode")
    out["theme_dark_mode"] = tr("theme_dark_mode", "Dark mode")
    out["theme_static_mode"] = tr("theme_static_mode", "Static Mode")
    # Stats Widgets sample values.
    out["cards"] = tr("cards", "cards")
    out["minutes_short"] = tr("minutes_short", "min")
    out["seconds_per_card"] = tr("seconds_per_card", "s/card")
    out["studied"] = tr("studied", "Studied")
    out["time"] = tr("time", "Time")
    out["pace"] = tr("pace", "Pace")
    out["retention"] = tr("retention", "Retention")
    out["seconds"] = tr("seconds", "Seconds")
    out["minutes"] = tr("minutes", "Minutes")
    out["hours"] = tr("hours", "Hours")
    out["profile_type"] = tr("profile_type", "Profile Style")
    # Deck Stats preview: the real widget's own on-card strings (lstats_*),
    # not the generic category-colour labels used elsewhere in this section —
    # different keys, kept exact so the preview reads letter-for-letter like
    # the widget it is previewing.
    out["lstats_title"] = tr("stats", "Stats")
    out["lstats_all_decks"] = tr("lstats_all_decks", "All Decks")
    out["lstats_new"] = tr("lstats_new", "New")
    out["lstats_learning"] = tr("lstats_learning", "Learning")
    out["lstats_relearning"] = tr("lstats_relearning", "Relearning")
    out["lstats_mature"] = tr("lstats_mature", "Mature")
    out["lstats_young"] = tr("lstats_young", "Young")
    out["lstats_unseen"] = tr("lstats_unseen", "Unseen")
    out["lstats_buried"] = tr("lstats_buried", "Buried")
    out["lstats_suspended"] = tr("lstats_suspended", "Suspended")
    out["lstats_total"] = tr("lstats_total", "Total")
    out["lstats_group_in_progress"] = tr("lstats_group_in_progress", "In Progress")
    out["lstats_group_mastered"] = tr("lstats_group_mastered", "Mastered")
    out["lstats_group_others"] = tr("lstats_group_others", "Others")
    out["lstats_total_short"] = tr("lstats_total_short", "total")
    out["lstats_view_grouped"] = tr("lstats_view_grouped", "Grouped")
    out["lstats_view_bars"] = tr("lstats_view_bars", "Bars")
    out["lstats_view_donut"] = tr("lstats_view_donut", "Donut")
    out["lstats_view_switcher"] = tr("lstats_view_switcher", "Stats view")
    # Icon popover (in-page replacement for the old native icon picker dialog).
    out["icon"] = tr("icon", "Icon")
    out["icons"] = tr("icons", "Icons")
    out["upload"] = tr("upload", "Upload")
    out["search_icons"] = tr("settings_web_search_icons", "Search icons")
    out["upload_svg"] = tr("settings_web_upload_svg", "Upload SVG icon")
    out["upload_png"] = tr("settings_web_upload_png", "Upload PNG image")
    out["your_icons"] = tr("settings_web_your_icons", "Your Icons")
    out["system_icons"] = tr("settings_web_system_icons", "System Icons")
    # Heatmap preview: the real widget's own on-card strings, same keys
    # heatmap.py's get_translated_labels feeds into heatmap.js's i18n object.
    out["heatmap_activity_label"] = tr("heatmap_activity_label", "Activity")
    out["heatmap_day_streak"] = tr("heatmap_day_streak", "day streak")
    out["view_year"] = tr("view_year", "Year")
    out["view_month"] = tr("view_month", "Month")
    out["view_week"] = tr("view_week", "Week")
    # Image field + gallery popover.
    out["gallery_choose"] = tr("settings_web_gallery_choose", "Choose image")
    out["gallery_change"] = tr("settings_web_gallery_change", "Change")
    out["gallery_empty_title"] = tr("settings_web_gallery_empty_title", "No images yet")
    out["gallery_empty_desc"] = tr(
        "settings_web_gallery_empty_desc", "Import a picture to start your gallery."
    )
    # The shared string ends in "…" because it labels a menu entry; here it is a
    # button in an already-open popover, so the ellipsis is just noise.
    out["gallery_import"] = tr("import_image", "Import image").rstrip(". …")
    out["gallery_none"] = tr("none_default", "None")
    out["gallery_delete"] = tr("settings_web_gallery_delete", "Delete image")
    out["gallery_delete_ask"] = tr("settings_web_gallery_delete_ask", "Delete?")
    out["gallery_deleted"] = tr("settings_web_gallery_deleted", "“{name}” deleted")
    out["gallery_hint_dynamic"] = tr(
        "settings_web_gallery_hint_dynamic",
        "Click to set the highlighted slot — or hover an image and press L / D.",
    )
    out["gallery_hint_single"] = tr(
        "settings_web_gallery_hint_single", "Click an image to use it."
    )
    out["gallery_hint_list"] = tr(
        "settings_web_gallery_hint_list", "Click images to add or remove them."
    )
    out["gallery_light"] = tr("light_mode", "Light")
    out["gallery_dark"] = tr("dark_mode", "Dark")
    out["gallery_close"] = tr("close", "Close")
    out["gallery_count"] = tr("settings_web_gallery_count", "{n} images")
    out["gallery_count_one"] = tr("settings_web_gallery_count_one", "1 image")
    # Per-asset light/dark link switch was removed.
    # Themes page.
    out["your_themes"] = tr("your_themes", "Your Themes")
    out["your_themes_desc"] = tr("your_themes_desc", "Themes you've imported or saved.")
    out["official_themes"] = tr("official_themes", "Official Themes")
    out["official_themes_desc"] = tr("official_themes_desc", "Ready-made palettes, picked for you.")
    out["import_theme"] = tr("import_theme", "Import")
    out["export_theme"] = tr("export_theme", "Export current")
    out["reset_theme_to_default"] = tr("reset_theme_to_default", "Reset to default")
    out["no_custom_themes"] = tr("no_custom_themes", "No custom themes yet")
    out["no_custom_themes_hint"] = tr(
        "settings_web_no_custom_themes_hint", "Import a .onigiri file, or export your current setup to start one."
    )
    out["theme_applied_toast"] = tr("theme_applied_toast", "Theme applied:")
    out["theme_deleted_toast"] = tr("theme_deleted_toast", "Theme deleted:")
    out["theme_imported_toast"] = tr("theme_imported_toast", "Theme imported successfully")
    out["theme_exported_toast"] = tr("theme_exported_toast", "Theme exported:")
    out["default_theme"] = tr("default_theme", "Default theme")
    out["theme_export_name_placeholder"] = tr("settings_web_theme_export_name_placeholder", "Theme name")
    out["theme_card_sub"] = tr("settings_web_theme_card_sub", "Light · Dark")
    out["theme_hold_hint"] = tr("settings_web_theme_hold_hint", "Hold 3s to apply")
    out["theme_export_name_title"] = tr("settings_web_theme_export_name_title", "Name this theme")
    # Games pages (the former standalone Gamification Settings window).
    out["games"] = tr("games", "Games")
    out["level_prefix"] = tr("level_prefix", "Level")
    out["onigimon_level"] = tr("onigimon_level", "Level")
    out["onigimon_refresh_button"] = tr("onigimon_refresh_button", "Refresh")
    out["onigimon_starter_note"] = tr("onigimon_starter_note", "")
    out["onigimon_status_loading"] = tr("onigimon_status_loading", "Loading…")
    out["onigimon_status_open_page"] = tr("onigimon_status_open_page", "")
    out["onigimon_level_short"] = tr("onigimon_level_short", "Lv")
    out["onigimon_status_happiness"] = tr("onigimon_status_happiness", "Happiness")
    out["onigimon_status_hygiene"] = tr("onigimon_status_hygiene", "Hygiene")
    out["onigimon_status_training"] = tr("onigimon_status_training", "Training")
    out["onigimon_status_hunger"] = tr("onigimon_status_hunger", "Hunger")
    out["onigimon_bond"] = tr("onigimon_bond", "Bond")
    out["onigimon_items"] = tr("onigimon_items", "Items")
    out["onigimon_streak"] = tr("pomodoro_streak_short", "Streak")
    out["onigimon_attack"] = tr("onigimon_attack", "Attack")
    out["onigimon_defense"] = tr("onigimon_defense", "Defense")
    out["onigimon_speed"] = tr("onigimon_speed", "Speed")
    out["onigimon_menu_team_hint"] = tr(
        "onigimon_menu_team_hint",
        "Use the pin on each Pokémon to show it in the Pokémon Team widget on the Main Menu.",
    )
    out["onigimon_menu_team_pin"] = tr("onigimon_menu_team_pin", "Show on Main Menu")
    out["columns"] = tr("widget_menu_columns", "Columns")
    out["rows"] = tr("widget_menu_rows", "Rows")
    out["menu_title"] = tr("menu_title", "Menu Title")
    out["hexagon_keys_owned"] = tr("hexagon_keys_owned", "owned")
    out["hexagon_keys_buy"] = tr("hexagon_keys_buy", "Buy Keys of the Island")
    out["hexagon_keys_cost"] = tr("hexagon_keys_cost", "{cost} Hex Coins")
    out["bento_detected"] = tr("settings_web_bento_detected", "Detected")
    out["bento_not_found"] = tr("settings_web_bento_not_found", "Not found")
    out["bento_detected_desc"] = tr(
        "settings_web_bento_detected_desc",
        "Available as an Onigiri mini-game/widget. Its native controls are surfaced here.",
    )
    out["bento_missing_desc"] = tr(
        "settings_web_bento_missing_desc",
        "Install and enable this add-on to embed it as an Onigiri mini-game.",
    )
    # Notification preview: one generic toast, so the stage shows the shape the
    # games actually use rather than any one game's copy.
    out["notif_preview_title"] = tr("notif_preview_title", "Onigiri")
    out["notif_preview_desc"] = tr("notif_preview_desc", "Level 4 reached — nice work!")
    out["notif_preview_silent"] = tr("notif_preview_silent", "Silent mode: nothing is shown")
    out["settings"] = tr("settings", "Settings")
    out["open"] = tr("open", "Open")
    # Pomodoro preview: these are the exact strings used by
    # PomodoroIslandView.refresh(), including the placeholders in the session
    # counter. Keeping them here makes both versions switch locale together.
    out["pomodoro_focus"] = tr("pomodoro_focus", "Focus")
    out["pomodoro_short_break"] = tr("pomodoro_short_break", "Short Break")
    out["pomodoro_long_break"] = tr("pomodoro_long_break", "Long Break")
    out["pomodoro_session_of"] = tr(
        "pomodoro_session_of", "Session {n} of {total}"
    )
    out["pomodoro_next"] = tr("pomodoro_next", "Next:")
    # Games launcher cards: the state pill on each tile.
    out["on"] = tr("on", "On")
    out["off"] = tr("off", "Off")
    out["message_add"] = tr("settings_web_message_add", "Add message")
    out["message_placeholder"] = tr("settings_web_message_placeholder", "Write a message…")
    out["message_move_up"] = tr("settings_web_message_move_up", "Move up")
    out["message_move_down"] = tr("settings_web_message_move_down", "Move down")
    out["message_remove"] = tr("settings_web_message_remove", "Remove")
    out["mochi_font_sample"] = tr("mochi_font_sample", "Keep going!")
    out["mochi_title_placeholder"] = tr("mochi_title_placeholder", "Mochi says…")
    return out


# Chrome icons the rail needs in its collapsed, icon-only state. The two rail
# chevrons are separate assets (not one mirrored glyph) so each direction can be
# drawn properly.
CHROME_ICONS = {
    "railCollapse": "chevron_left.svg",
    "railExpand": "chevron_right.svg",
    "donate": "star_outline.svg",
    "bugs": "info-circle.svg",
    "done": "check.svg",
    # Gallery popover: one glyph closes it, the same glyph (smaller, on a tile)
    # deletes an image — the ✕ means "remove this" in both places.
    "close": "cancel.svg",
    "confirm": "check-simple.svg",
    "add": "add.svg",
    "image": "folder.svg",
    "themeImport": "import_file.svg",
    "themeExport": "export-deck.svg",
    "themeReset": "undo-2.svg",
    "sun": "lucide-sun.svg",
    "moon": "lucide-moon.svg",
}


def rail_collapsed(conf=None):
    conf = conf if conf is not None else config.get_config_readonly()
    return bool(conf.get("settings_sidebar_collapsed", False))


def sidebar_bg_context():
    conf = config.get_config_readonly()
    try:
        if mw and mw.col:
            conf = mw.col.conf
    except Exception:
        pass
    bg_type = conf.get("modern_menu_sidebar_bg_type", "color")
    if bg_type == "image":
        bg_type = "image_color"
    color_light = conf.get("modern_menu_sidebar_bg_color_light", "#F3F3F3")
    color_dark = conf.get("modern_menu_sidebar_bg_color_dark", "#2C2C2C")
    color_theme = conf.get("modern_menu_sidebar_bg_color_theme_mode", "separate")
    image_light = conf.get("modern_menu_sidebar_bg_image_light", "") or conf.get("modern_menu_sidebar_bg_image", "")
    image_dark = conf.get("modern_menu_sidebar_bg_image_dark", "") or conf.get("modern_menu_sidebar_bg_image", "")
    image_theme = conf.get("modern_menu_sidebar_bg_image_theme_mode", "separate")
    blur = int(conf.get("modern_menu_sidebar_bg_blur", 0) or 0)
    opacity_value = conf.get("modern_menu_sidebar_bg_opacity", 100)
    opacity = int(100 if opacity_value is None else opacity_value)

    return {
        "width": conf.get("modern_menu_sidebar_width", 600),
        "type": bg_type,
        "colorLight": color_light,
        "colorDark": color_dark if color_theme != "single" else color_light,
        "imageLight": addon_uri(f"user_files/sidebar_bg/{image_light}") if image_light else "",
        "imageDark": addon_uri(f"user_files/sidebar_bg/{image_dark if image_theme != 'single' else image_light}") if (image_dark or image_light) else "",
        "blur": blur,
        "opacity": opacity,
    }


def profile_assets_context():
    pic_dir = os.path.join(ADDON_ROOT, "user_files", "profile")
    bg_dir = os.path.join(ADDON_ROOT, "user_files", "profile_bg")
    pics = {}
    bgs = {}
    if os.path.exists(pic_dir):
        try:
            for f in os.listdir(pic_dir):
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    pics[f] = addon_uri(f"user_files/profile/{f}")
        except Exception:
            pass
    if os.path.exists(bg_dir):
        try:
            for f in os.listdir(bg_dir):
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    bgs[f] = addon_uri(f"user_files/profile_bg/{f}")
        except Exception:
            pass

    default_pic = addon_uri("system_files/profile_default/onigiri-san.png")
    default_bg = addon_uri("system_files/profile_default/onigiri-bg.png")
    return {
        "pics": pics,
        "bgs": bgs,
        "defaultPic": default_pic,
        "defaultBg": default_bg,
    }


def profile_level_context():
    try:
        from ..rendering import onigiri_renderer
        enabled, level, fraction, color = onigiri_renderer._profile_level_progress()
        game = onigiri_renderer._selected_profile_level_game()
        return {
            "enabled": enabled,
            "level": level if level is not None else 0,
            "fraction": fraction if fraction is not None else 0.0,
            "color": color or "",
            "game": game,
            "sourceName": onigiri_renderer._profile_level_source_name(game),
        }
    except Exception:
        return {"enabled": False, "level": 0, "fraction": 0.0, "color": ""}


def profile_preview_context():
    """Refreshable profile data from the same readers as the live sidebar."""
    return {
        "profileLevel": profile_level_context(),
        "chipColors": restaurant_chip_colors_context(),
        "chipDefaults": chip_defaults_context(),
    }


def pomodoro_state_context():
    """Snapshot the same state rendered by the floating Pomodoro island.

    The web preview advances a running snapshot from ``capturedAtMs`` so its
    time, progress, cycle dots, and play/pause control match an already-open
    timer instead of falling back to a hard-coded demonstration state.
    """
    try:
        from ..study_tools import pomodoro

        timer = pomodoro.get_timer()
        return {
            "phase": timer.session_type,
            "remaining": timer.remaining_seconds,
            "total": timer.phase_length_seconds(),
            "focusCount": timer.focus_count,
            "cycleTotal": max(
                1, timer.settings.get("sessions_until_long_break", 4)
            ),
            "running": timer.running,
            "capturedAtMs": round(time.time() * 1000),
        }
    except Exception:
        return {
            "phase": "focus",
            "remaining": 25 * 60,
            "total": 25 * 60,
            "focusCount": 0,
            "cycleTotal": 4,
            "running": False,
            "capturedAtMs": round(time.time() * 1000),
        }


def _css_color(value):
    """Qt's QColor.name(HexArgb) returns #AARRGGBB — CSS hex takes the alpha
    LAST (#RRGGBBAA), so passing a Qt ARGB string straight through as a CSS
    color silently reinterprets it as an opaque, wrong-hued color (alpha byte
    read as blue). Convert the translucent (9-char) case to rgba(); a plain
    7-char #RRGGBB needs no conversion."""
    text = str(value or "")
    if len(text) == 9 and text.startswith("#"):
        a = int(text[1:3], 16)
        r = int(text[3:5], 16)
        g = int(text[5:7], 16)
        b = int(text[7:9], 16)
        return f"rgba({r}, {g}, {b}, {a / 255:.3f})"
    return text


def restaurant_chip_colors_context():
    """Bar-mode level chip (Lv N pill) colors for both themes, straight from
    the same nook_level.get_chip_style_values() the real sidebar chip renders
    with — so the settings preview always matches what's actually on screen,
    including any bg/text customization made in the classic Level Chip
    Appearance dialog."""
    try:
        from ..gamification import nook_level
        from ..core import config as _config

        conf = _config.get_config()
        result = {}
        for mode, is_dark in (("light", False), ("dark", True)):
            values = nook_level.get_chip_style_values(conf, is_dark=is_dark)
            result[mode] = {key: _css_color(val) for key, val in values.items()}
        return result
    except Exception:
        return {"light": {}, "dark": {}}


def chip_defaults_context():
    """The level chip's colors with every user override removed — what an unset
    swatch on the Level Chip Appearance card inherits. Resolved through the same
    nook_level.get_chip_style_values() as the real chip, so "default" here means
    the same thing it means on screen."""
    keys = (
        "chip_bg_color", "chip_progress_color", "chip_text_color",
        "chip_bg_color_light", "chip_bg_color_dark",
        "chip_progress_color_light", "chip_progress_color_dark",
        "chip_text_color_light", "chip_text_color_dark",
    )
    try:
        from ..gamification import nook_level
        from ..core import config as _config

        conf = copy.deepcopy(_config.get_config())
        restaurant = conf.setdefault("restaurant_level", {})
        for key in keys:
            restaurant[key] = ""
        result = {}
        for mode, dark in (("light", False), ("dark", True)):
            values = nook_level.get_chip_style_values(conf, is_dark=dark)
            result[mode] = {key: _css_color(val) for key, val in values.items()}
        return result
    except Exception:
        return {"light": {}, "dark": {}}


def games_context(pages):
    """What the Games pages need at first paint — and deliberately not the rest.

    Asking Ankimon for the roster or Hexagon Land for the balance means
    importing those modules (onigimon.py and hexagon_land.py are the two
    largest files in the add-on), so opening Settings on any other page would
    pay for games the user is not looking at. Those come over the bridge the
    first time a Games page is shown; see games_live_context()."""
    if not any(page.get("group") == "games" for page in pages):
        return {}
    return {
        "loaded": False,
        "ankimon": {},
        "companions": {"status": "", "message": "", "active": "", "companions": []},
        "companionPreview": {
            "name": "Onigimon",
            "level": 1,
            "sprite": "",
            "staticSprites": [],
            "animatedSprites": [],
            "needs": {},
            "bondLevel": 1,
            "bondXp": 0,
            "streak": 0,
            "itemCount": 0,
            "types": [],
            "attack": 0,
            "defense": 0,
            "speed": 0,
        },
        "hexagon": {"owns_keys": False, "coins": 0, "cost": 0, "affordable": False},
        "bento": [],
    }


def games_live_context():
    """The half of games_context that costs a game-module import."""
    from . import games_state

    return {
        "loaded": True,
        "ankimon": games_state.ankimon_status(),
        "companions": games_state.companions(),
        "companionPreview": games_state.active_companion_preview(),
        "hexagon": games_state.hexagon_context(),
        "bento": games_state.bento_games(addon_uri),
    }


def gallery_url(folder, name):
    """Media-server URL for one file in a registered gallery folder."""
    relative = gallery.FOLDERS.get(str(folder or ""))
    if not relative or not name:
        return ""
    return addon_uri(f"user_files/{relative}/{os.path.basename(str(name))}")


def gallery_context(pages):
    """Contents of every folder an `image` field on any page points at.

    Shipped with the page so a thumbnail is painted from the first frame and
    the picker opens on real content instead of a spinner; it still refreshes
    itself over the bridge on open, which is what catches files added to the
    folder from outside Anki."""
    folders = []
    for _page, _section, field in schema.iter_fields(pages):
        folder = field.get("folder")
        if field.get("type") == "image" and folder and folder not in folders:
            folders.append(folder)
    # Plus every folder the Gallery page's image browser lists, which has no
    # field of its own to carry one.
    for page in pages:
        for section in page.get("sections", []):
            for entry in section.get("folders", []):
                if entry.get("id") and entry["id"] not in folders:
                    folders.append(entry["id"])
    return {
        folder: gallery.list_images(folder, url_for=gallery_url)
        for folder in folders
    }


# Widget catalogue for the Organize page's grid editor — mirrors
# settings/_widget_grid_v2.py's _ONIGIRI_CATALOGUE exactly (wid, default_span,
# min_span, max_span, fixed_rows); the settings dialog owns this list, so it
# stays a Python constant rather than being duplicated in JS. Deck Stats is the
# one deliberate exception to the one-widget-per-kind rule: the organizer can
# add it more than once and gives every instance its own persistent ID.
ORGANIZE_ONIGIRI_CATALOGUE = [
    ("stats_title", (1, 4), (1, 1), (1, 4), 1),
    ("studied", (1, 1), (1, 1), (1, 4), None),
    ("time", (1, 1), (1, 1), (1, 4), None),
    ("pace", (1, 1), (1, 1), (1, 4), None),
    ("retention", (1, 1), (1, 1), (1, 4), None),
    ("heatmap", (2, 4), (2, 2), (2, 4), 2),
    ("favorites", (1, 1), (1, 1), (3, 2), None),
    ("restaurant_level", (2, 2), (1, 1), (2, 2), None),
    ("onigimon", (2, 1), (1, 1), (4, 2), None),
    ("ankimon_team", (2, 1), (1, 1), (4, 4), None),
    ("hexagon_land", (2, 2), (1, 1), (4, 4), None),
    ("deck_stats", (2, 1), (1, 1), (2, 2), None),
    ("prep_station", (2, 2), (2, 1), (2, 4), 2),
    ("hashi_notes", (2, 2), (1, 1), (4, 4), None),
    ("ready_to_go", (2, 2), (1, 1), (3, 2), None),
]


def _organize_onigiri_name(wid):
    names = {
        "stats_title": tr("menu_title", "Menu Title"),
        "studied": tr("widget_studied", "Studied"),
        "time": tr("widget_time", "Time"),
        "pace": tr("widget_pace", "Pace"),
        "retention": tr("widget_retention", "Retention"),
        "heatmap": tr("widget_heatmap", "Heatmap"),
        "favorites": tr("widget_favorites", "Favorites"),
        "restaurant_level": tr("widget_restaurant_level", "Nook Level"),
        "onigimon": "Onigimon",
        "ankimon_team": tr("ankimon_team_widget_name", "Pokémon Team"),
        "hexagon_land": "Hexagon Land",
        "deck_stats": "Deck Stats",
        "prep_station": tr("widget_study_plans", "Study Plans"),
        "hashi_notes": tr("hashi_notes_title", "Hashi Notes"),
        "ready_to_go": "Ready to go",
    }
    return names.get(wid, wid)


_ORGANIZE_AUTO_COLORS = ["#E0A400", "#4064E0", "#20A0C0", "#E0567A", "#7A56E0", "#2FA968", "#E07B3A", "#3AA0E0"]


def _organize_auto_color(wid):
    return _ORGANIZE_AUTO_COLORS[abs(hash(wid)) % len(_ORGANIZE_AUTO_COLORS)]


def organize_context():
    """Everything the Organize grid editor needs about *available* widgets —
    computed once per dialog open, matching legacy (`_build_specs`/
    `_build_external_specs`, settings/_widget_grid_v2.py:429-509). Current
    placement lives in the ordinary `onigiriWidgetLayout`/`externalWidgetLayout`
    config fields, not here."""
    onigiri = [
        {
            "wid": wid,
            "name": _organize_onigiri_name(wid),
            "defaultSpan": list(default_span),
            "minSpan": list(min_span),
            "maxSpan": list(max_span),
            "fixedRows": fixed_rows,
            "multiInstance": wid == "deck_stats",
        }
        for wid, default_span, min_span, max_span, fixed_rows in ORGANIZE_ONIGIRI_CATALOGUE
    ]

    external = []
    seen = set()
    identity = {}
    try:
        conf = config.get_config_readonly()
        identity = dict(conf.get("externalWidgetIdentity", {}) or {})
    except Exception:
        pass

    try:
        from ..rendering import patcher
        from ..api import bento as bento_api

        bento_widgets = bento_api.get_bento_widgets() or {}

        def find_bento_meta(hook_id, pkg, name):
            if not bento_widgets:
                return None, {}
            if hook_id in bento_widgets:
                return hook_id, bento_widgets[hook_id]
            if pkg in bento_widgets:
                return pkg, bento_widgets[pkg]
            clean_name = name.split(" - ")[0].strip().lower() if name else ""
            for aid, meta in bento_widgets.items():
                if not isinstance(meta, dict):
                    continue
                meta_hook = meta.get("hook_id")
                meta_addon = meta.get("addon_id") or meta.get("pkg") or meta.get("id")
                meta_name = (meta.get("name") or "").strip().lower()
                if meta_hook == hook_id:
                    return aid, meta
                if meta_addon and (meta_addon == pkg or meta_addon == hook_id):
                    return aid, meta
                if clean_name and meta_name and (meta_name == clean_name or meta_name in clean_name or clean_name in meta_name):
                    return aid, meta
            return None, {}

        hooks = patcher._get_external_hooks()
        for h in hooks:
            hook_id = patcher._get_hook_name(h)
            if (
                "learner_stats_widget" in hook_id
                or "overview_team" in hook_id.lower()
                or hook_id in seen
            ):
                continue
            seen.add(hook_id)

            pkg = hook_id.split(".")[0]
            seen.add(pkg)

            try:
                fallback = mw.addonManager.addonName(pkg)
            except Exception:
                fallback = pkg

            raw_name = patcher.get_external_hook_display_name(hook_id, fallback or pkg) or pkg

            matched_aid, bento_meta = find_bento_meta(hook_id, pkg, raw_name)
            if matched_aid:
                seen.add(matched_aid)

            ident = identity.get(hook_id, {}) or identity.get(pkg, {}) or (identity.get(matched_aid, {}) if matched_aid else {})

            bento_color = (
                (bento_meta or {}).get("color")
                or (bento_meta or {}).get("accent_color")
                or getattr(h, "bento_color", None)
                or getattr(h, "color", None)
            )
            color = ident.get("color") or bento_color or _organize_auto_color(hook_id)

            bento_name = (bento_meta or {}).get("name")
            display_name = raw_name
            bento_names = {"global", "sticky", "power", "hours", "berry", "league"}
            is_bento_widget = bool(bento_meta) or any(
                b in (display_name or "").lower() or b in hook_id.lower()
                for b in bento_names
            )

            external.append({
                "wid": hook_id,
                "name": display_name,
                "kind": "bento" if is_bento_widget else "external",
                "color": color,
                "defaultSpan": [2, 1],
                "minSpan": [2, 1],
                "maxSpan": [4, 4],
                "fixedRows": None,
            })

        for aid, meta in bento_widgets.items():
            if aid in seen:
                continue
            if not isinstance(meta, dict):
                continue
            meta_name = meta.get("name") or aid
            meta_hook = meta.get("hook_id")
            if meta_hook and meta_hook in seen:
                continue
            seen.add(aid)
            ident = identity.get(aid, {})
            color = (
                ident.get("color")
                or meta.get("color")
                or meta.get("accent_color")
                or _organize_auto_color(aid)
            )
            external.append({
                "wid": aid,
                "name": meta_name,
                "kind": "bento",
                "color": color,
                "defaultSpan": [2, 1],
                "minSpan": [2, 1],
                "maxSpan": [4, 4],
                "fixedRows": None,
            })
    except Exception as exc:
        print(f"[Onigiri] Error building organize context: {exc}")

    return {"onigiri": onigiri, "external": external}


def icon_assets_context():
    """Every icon the picker can return, as name -> data URI.

    The page has to draw the *chosen* icon (in a field row and inside a preview
    widget) and the user can change it mid-session, so shipping the inventory
    once is cheaper than a round trip per pick. Names match what the picker
    stores: "system:foo.svg" for the bundled set, a bare filename for the
    user's own icons."""
    out = {}
    for directory in SYSTEM_ICON_DIRS:
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            continue
        for name in names:
            if not name.lower().endswith(".svg"):
                continue
            uri = icon_data_uri(name)
            if uri:
                out.setdefault(f"system:{name}", uri)
    for folder in ("icons", "custom_deck_icons"):
        directory = os.path.join(ADDON_ROOT, "user_files", folder)
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            continue
        for name in names:
            if not name.lower().endswith(".svg"):
                continue
            try:
                with open(os.path.join(directory, name), "rb") as handle:
                    raw = handle.read()
            except OSError:
                continue
            out.setdefault(name, "data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii"))
    return out


def pickable_icons_context():
    """What the icon popover offers to pick, as opposed to icon_assets_context's
    "everything a stored value might resolve to" (which also has to cover
    unavailable_for_users, in case an old value still points at one).

    Only available_for_users is user-facing here — same rule patcher.py's own
    users_only icon listing applies — plus every icon the user has uploaded."""
    out = []
    avail_dir = os.path.join(ADDON_ROOT, "system_files", "system_icons", "available_for_users")
    try:
        names = sorted(os.listdir(avail_dir))
    except OSError:
        names = []
    for name in names:
        if not name.lower().endswith(".svg"):
            continue
        uri = icon_data_uri(name)
        if uri:
            out.append({"name": f"system:{name}", "url": uri, "system": True})
    user_dir = os.path.join(ADDON_ROOT, "user_files", "icons")
    try:
        names = sorted(os.listdir(user_dir))
    except OSError:
        names = []
    for name in names:
        if not name.lower().endswith((".svg", ".png")):
            continue
        try:
            with open(os.path.join(user_dir, name), "rb") as handle:
                raw = handle.read()
        except OSError:
            continue
        mime = "image/png" if name.lower().endswith(".png") else "image/svg+xml"
        out.insert(0, {  # newest-ish first, ahead of the bundled set
            "name": name, "url": f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}", "system": False,
        })
    return out


def theme_gallery_context():
    return {
        "official": theme_store.list_official_themes(),
        "user": theme_store.list_user_themes(),
    }


def things_preview_context():
    """Production Kome assets plus current read-only dashboard data.

    The WebUI mounts these inside an iframe, which lets the preview use the
    unmodified :root/html/body rules from Kome without recolouring the
    Settings dialog itself.  The real deck-list and sidebar JavaScript then
    build the miniature from the same component paths used by Anki's deck
    browser; only the amount of deck data is capped so the Settings payload
    cannot balloon for very large collections.
    """
    css = "\n\n".join(
        read_things_asset(name)
        for name in (
            "tokens.css",
            "theme.css",
            "heatmap.css",
            "decklist.css",
            "logo.css",
            "sidebar.css",
        )
    )
    out = {
        "css": css,
        "localizationScript": web_localization_script(),
        "decklistJs": read_things_asset("decklist.js"),
        "sidebarJs": read_things_asset("sidebar.js"),
        "decks": [],
        "standing": {},
        "tasks": [],
        "analyticsHtml": "",
        "palettes": copy.deepcopy(config.get_config_readonly().get("colors", {})),
        "deckIconBase": addon_uri(
            "system_files/system_icons/unavailable_for_users"
        ),
    }
    try:
        from .. import things_theme

        cfg = things_theme._config()
        weeks = max(8, min(260, int(cfg.get("heatmap_weeks", 53) or 53)))
        heatmap = things_theme.build_heatmap_html(weeks)
        chart = things_theme.build_review_chart_html(weeks * 7)
        out.update({
            # Twelve rows reproduce the real viewport faithfully while keeping
            # the charts close enough to reach by scrolling the miniature.
            "decks": things_theme._full_deck_tree_payload()[:12],
            "standing": things_theme._build_standing_payload(),
            "tasks": things_theme._tasks_get()[:5],
            "analyticsHtml": (
                '<section class="ba-practice"><div class="ba-analytics">'
                + chart
                + '<section class="ba-heatmap-card">'
                + heatmap
                + "</section></div></section>"
            ),
        })
    except Exception as exc:  # noqa: BLE001 - preview remains available
        print(f"[Onigiri] settings_web: Kome preview data failed: {exc}")
    return out


def build_context(store, pages, initial_page=None):
    dark = is_dark()
    nav = []
    for group in schema.nav_groups():
        items = [
            {
                "id": page["id"],
                "title": page["title"],
                "icon": icon_svg(page.get("icon")),
                "simpleOnly": bool(page.get("simple_only")),
                "showWhen": page.get("show_when"),
            }
            for page in pages
            if page.get("group") == group["id"]
        ]
        if items:
            nav.append({"id": group["id"], "title": group["title"], "items": items})

    serialized_pages = []
    for page in pages:
        serialized_pages.append({
            "id": page["id"],
            "title": page["title"],
            "description": page.get("description", ""),
            # Used by the page itself, not only by the nav: the Games group
            # fetches its live state the first time one of its pages is shown.
            "group": page.get("group", ""),
            "simpleOnly": bool(page.get("simple_only")),
            "showWhen": page.get("show_when"),
            # Optional compact segmented control mounted at the right of the
            # page title (Fonts uses it for Simple/Advanced typography).
            "headerFieldId": page.get("header_field_id", ""),
            # Sub-menu navigation: sections become tabs and only the active one
            # is mounted (settings.js renderTabbedPage).
            "tabbed": bool(page.get("tabbed")),
            "sections": [
                {
                    "id": section.get("id", ""),
                    "title": section.get("title", ""),
                    # Sub-caption under a section's own title (the Games pages
                    # explain what a card does before its controls).
                    "description": section.get("description", ""),
                    # Only used by tabbed pages: the icon-only fallback the
                    # sub-menu strip switches to when it runs out of width.
                    "icon": icon_svg(section.get("icon")),
                    # Picks a section-level renderer in settings.js; absent means
                    # the default flat list of field rows.
                    "layout": section.get("layout", ""),
                    "role_key": section.get("role_key", ""),
                    "fontRoles": section.get("font_roles", []),
                    "fontMenuLabel": section.get("font_menu_label", ""),
                    # Compact element-group picker used by dense palettes such
                    # as the Reviewer bottom-bar button colors.
                    "colorGroups": section.get("color_groups", []),
                    "colorMenuLabel": section.get("color_menu_label", ""),
                    # Organize Widgets mounts these ordinary fields in its
                    # compact appearance panel above the widget grid.
                    "compactFields": section.get("compact_fields", []),
                    # Font-role previews use this when their selected font is
                    # "sync", so the preview mirrors the inherited theme role.
                    "fallback_role_key": section.get("fallback_role_key", ""),
                    # Some whole cards only apply in a selected mode (for
                    # example individual sidebar typography).
                    "showWhen": section.get("show_when"),
                    # Registers a field for the page header without leaving an
                    # empty section behind in the scrolling content.
                    "headerOnly": bool(section.get("header_only")),
                    "advancedOnly": bool(section.get("advanced_only")),
                    # A few self-contained cards intentionally retain the
                    # same controls regardless of the global complexity mode.
                    "modeParity": bool(section.get("mode_parity")),
                    # Which PREVIEW_PAINTERS entry a "designer_preview" section
                    # paints its stage with (background/widget_effect/... — see
                    # settings_web/schema.py's _designer_preview_section).
                    "preview_kind": section.get("preview_kind", ""),
                    # Stage beside the controls (one column, schema order)
                    # instead of above a two-column deck.
                    "stage_side": bool(section.get("stage_side")),
                    # Optional field whose value determines whether this
                    # preview has a meaningful light/dark theme switch.
                    "preview_dynamic_field": section.get("preview_dynamic_field", ""),
                    # Companion colours shown under each icon tile as well as
                    # inside the icon's popover.
                    "icon_colors_inline": bool(section.get("icon_colors_inline")),
                    "full_width_color_grid": bool(section.get("full_width_color_grid")),
                    "subsections": section.get("subsections", []),
                    "dynamic_keys": section.get("dynamic_keys", []),
                    "hide_deck_when": section.get("hide_deck_when", {}),
                    "sync_toggle_id": section.get("sync_toggle_id", ""),
                    "sync_hidden_fields": section.get("sync_hidden_fields", []),
                    # Pomodoro's compact setup surface: preset patches and the
                    # value-chip groups rendered by renderPomodoroSetup.
                    "presets": section.get("presets", []),
                    "groups": section.get("groups", []),
                    # Gallery's image browser: [{id, title}] of the folders it
                    # lists (settings.js renderGalleryAssets).
                    "folders": section.get("folders", []),
                    # Markers: which colour/icon/name fields make up each card
                    # (settings.js renderMarkers).
                    "markers": section.get("markers", []),
                    # Games launcher tiles (settings.js renderGamesGallery):
                    # [{id, page, toggle, title, desc, image, accent, wide}].
                    "cards": section.get("cards", []),
                    "fields": [_serialize_field(store, field) for field in section.get("fields", [])],
                }
                for section in page.get("sections", [])
            ],
        })

    return {
        "dark": dark,
        "accent": accent_color(),
        "palette": palette(dark),
        "strings": _strings(),
        "nav": nav,
        "pages": serialized_pages,
        "initialPage": initial_page,
        "addonBase": addon_uri(""),
        "railCollapsed": rail_collapsed(),
        "settingsComplexity": store.read("settings_complexity") or "advanced",
        "sidebarBg": sidebar_bg_context(),
        "profileAssets": profile_assets_context(),
        "profileLevel": profile_level_context(),
        "pomodoroState": pomodoro_state_context(),
        "chipColors": restaurant_chip_colors_context(),
        "chipDefaults": chip_defaults_context(),
        "games": games_context(pages),
        "galleries": gallery_context(pages),
        "themeGallery": theme_gallery_context(),
        "thingsPreview": things_preview_context(),
        "organizeCatalogue": organize_context(),
        "iconAssets": icon_assets_context(),
        "iconPicker": pickable_icons_context(),
        # The production heatmap renderer formats month/day labels with
        # Onigiri's selected language rather than Chromium's UI locale.  Its
        # settings preview runs that same renderer, so give it the same input.
        "heatmapLocale": current_language(),
        "localization": {"locale": current_language(), "literals": literal_strings()},
        "chromeIcons": {key: icon_svg(name) for key, name in CHROME_ICONS.items()},
    }


def _serialize_field(store, field):
    out = {
        "id": field["id"],
        "type": field.get("type", "toggle"),
        "label": field.get("label", ""),
        "desc": field.get("desc", ""),
        "value": store.read(field["id"]),
        # Page-wide reset controls must distinguish persisted settings from
        # display-only notes; binding descriptors themselves stay Python-side.
        "bound": bool(field.get("bind")),
    }
    if field["id"] in ("g_mochi_messages", "g_fd_messages"):
        keys = (tuple(f"mochi_default_{index}" for index in range(1, 8))
                if field["id"] == "g_mochi_messages" else ("fd_default_message", "fd_keep_focused"))
        out["value"] = [localized_default(str(value), keys) for value in (out["value"] or [])]
    elif field["id"] == "g_mochi_title_name":
        out["value"] = localized_default(str(out["value"] or ""), ("mochi_title_placeholder",))
    # Simple mode keeps decisions such as modes, toggles, pictures, fonts and
    # text visible, while detailed paint/effect/ordering controls move behind
    # Advanced.  A schema entry can always override this default explicitly.
    if "advanced" in field:
        out["advanced"] = bool(field["advanced"])
    else:
        out["advanced"] = field.get("type") in {
            "button_order", "icon", "message_list", "notif_position", "slider",
        }
    for key in (
        "notes", "items", "options", "color_fields", "color_dynamic_field", "layout", "min", "max", "step", "suffix",
        "default", "reset_to", "cascade", "toast_on", "hero", "desc_link", "placeholder",
        "max_length", "max_graphemes",
        # Action buttons need their command as well as their visible label.
        # Without it, renderAction() returns before sending any bridge message.
        "level", "level_name", "action", "button_label", "multiline", "desc_alt",
        # image + colour-pair fields
        "folder", "dynamic_field", "light_field", "dark_field", "empty_label",
        "theme_mode_field", "mode_field", "mode_value", "empty_mode", "categories",
        "blank_token",
        # designer cards: header-mounted choices and conditional rows
        "head", "head_label", "show_when", "control_style",
        # Icon picker categories used to keep deck-list header, action-button,
        # and Ready To Go icons visibly distinct in the designer card.
        "icon_group", "icon_group_title",
        # Declarative placement for a field that must stay near a related
        # control instead of joining the generic type-based deck group.
        "deck_placement", "deck_icon_tile",
        # Games pages
        "hero_image", "accent", "tone", "scale", "virtual", "alpha_of", "context_key",
        "single_field", "always_split", "static_fallback", "chip_role", "danger", "button_icon",
        "square", "neutral", "hold_to_confirm",
        # Global Simple/Advanced mode hides only fields explicitly marked as
        # advanced; those fields remain indexed by full-settings search.
        "advanced", "simple_only",
        # a colour whose "unset" state means some other field's value (an icon
        # tint falling back to the shared icon colour)
        "fallback_light", "fallback_dark", "inherit_main_background",
        # Reorder-only button_order fields omit the archive bucket and eyes.
        "allow_archive", "more_bucket",
    ):
        if key in field:
            out[_camel(key)] = field[key]
    if field.get("icon"):
        out["icon"] = icon_svg(field["icon"])
    # An option may name an icon file instead of relying on its label — the
    # page cannot read the icon directory, so inline the markup here.
    if out.get("options"):
        out["options"] = [
            dict(option, icon=icon_svg(option["icon"])) if option.get("icon") else option
            for option in out["options"]
        ]
    return out


def _camel(snake):
    head, *rest = snake.split("_")
    return head + "".join(part.title() for part in rest)


def safe_json(value):
    """json.dumps escaped so a user string containing '</script>' cannot break
    out of the tag it is injected into."""
    return json.dumps(value).replace("</", "<\\/")


def real_widget_css():
    """The Main Menu's own widget CSS, verbatim.

    A preview that reimplements a widget drifts from it the first time the real
    one changes; slicing the marked block out of web/menu.css means the preview
    literally renders with the menu's rules. Markers live in menu.css next to
    the block they delimit. Those class names (.stat-card, .star-rating, …) are
    disjoint from the dialog's own .osw-* namespace, so nothing here can leak
    into the settings chrome."""
    css = read_web_asset("menu.css")
    blocks = []
    for name in ("widget-head", "stats-widgets", "hashi-widget", "prep-widget",
                 "sidebar-count-bubbles"):
        head = f"@onigiri:{name}:start"
        tail = f"@onigiri:{name}:end"
        if head not in css or tail not in css:
            continue
        body = css.split(head, 1)[1].split(tail, 1)[0]
        # The start marker sits inside a comment; drop its remainder.
        body = body.split("*/", 1)[1] if "*/" in body else body
        # The end marker sits inside its own comment, opened just before it.
        body = body.rsplit("/*", 1)[0]
        blocks.append(body.strip())
    # Deck Stats: the whole stylesheet, not a marked slice of it — unlike
    # menu.css it is already scoped to nothing but this one widget (every rule
    # is .learner-stat(s)-*), so there is no unrelated content to cut around.
    learner_css = read_web_asset("learner_stats.css")
    if learner_css:
        blocks.append(learner_css.strip())
    # Heatmap: same wholesale-include as Deck Stats — every rule is scoped to
    # #onigiri-heatmap-container / .heatmap-*, nothing to cut around.
    heatmap_css = read_web_asset("heatmap.css")
    if heatmap_css:
        blocks.append(heatmap_css.strip())
    # Notifications: both the global and Mochi previews draw the *real* toast
    # (.onigiri-notification-card / .onigiri-mini-notification), so they need
    # the live stylesheet. Its `.onigiri-notification-stack` is fixed, which is
    # why previews substitute only their own stage-local positioner.
    notifications_css = read_web_asset("notifications.css")
    if notifications_css:
        blocks.append(notifications_css.strip())
    return "\n\n".join(blocks)


def render(store, pages, initial_page=None):
    template = read_web_asset("settings.html")
    if not template:
        return "<html><body>" + tr("settings_assets_missing") + "</body></html>"
    css = read_web_asset("settings.css") + "\n" + read_web_asset("reviewer_buttons_shared.css")
    js = read_web_asset("settings.js")
    heatmap_js = read_web_asset("Particles.js") + "\n" + read_web_asset("heatmap.js")
    notifications_js = read_web_asset("notifications.js")
    context = build_context(store, pages, initial_page=initial_page)
    boot_background = palette(is_dark()).get("outer", "#ffffff")
    return (
        template
        .replace("</head>", web_localization_script() + "</head>")
        .replace("/*__ONIGIRI_FONT_FACE__*/", font_face_css())
        .replace("/*__ONIGIRI_REAL_WIDGET_CSS__*/", real_widget_css())
        .replace("/*__ONIGIRI_SETTINGS_CSS__*/", css)
        .replace("/*__ONIGIRI_HEATMAP_JS__*/", heatmap_js)
        .replace("/*__ONIGIRI_NOTIFICATIONS_JS__*/", notifications_js)
        .replace("/*__ONIGIRI_SETTINGS_JS__*/", js)
        .replace("/*__ONIGIRI_SETTINGS_CONTEXT__*/null", safe_json(context))
        .replace("/*__ONIGIRI_BOOT_BACKGROUND__*/", boot_background)
    )
