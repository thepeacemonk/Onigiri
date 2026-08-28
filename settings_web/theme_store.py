# Theme library + apply/import/export logic behind the WebUI Themes page.
#
# Ported from the legacy settings/_page_themes.py, stripped of everything that
# only existed to keep ~40 Qt widgets in sync (the WebUI has no such widgets —
# a page reads straight from Store on next render). What is left is pure data:
# read a theme, write a theme's keys into config/mw.col.conf, zip one up.

import copy
import json
import os
import shutil
import zipfile

from aqt import mw

from .. import config, safe_storage
from ..constants import ALL_THEME_KEYS, DEFAULT_ICON_SIZES, ICON_DEFAULTS, REVIEWER_THEME_KEYS
from ..themes import THEMES
from .store import _col_get, _col_set

ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The four swatch tokens a card needs to paint its light/dark preview without
# shipping the whole ~40-key palette to the page.
SWATCH_KEYS = ("--bg", "--fg", "--accent-color", "--canvas-inset")


def user_themes_dir():
    path = os.path.join(ADDON_ROOT, "user_files", "user_themes")
    os.makedirs(path, exist_ok=True)
    return path


def _swatch(palette):
    palette = palette if isinstance(palette, dict) else {}
    return {key: palette.get(key, "") for key in SWATCH_KEYS}


def list_official_themes():
    return [
        {"name": name, "light": _swatch(data.get("light")), "dark": _swatch(data.get("dark"))}
        for name, data in sorted(THEMES.items(), key=lambda item: item[0].lower())
    ]


def _load_user_theme_file(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "light" not in data or "dark" not in data:
        return None
    return data


def list_user_themes():
    out = []
    directory = user_themes_dir()
    for filename in sorted(os.listdir(directory)):
        if not filename.lower().endswith(".json"):
            continue
        data = _load_user_theme_file(os.path.join(directory, filename))
        if data is None:
            continue
        name = os.path.splitext(filename)[0].replace("_", " ").title()
        out.append({"name": name, "light": _swatch(data.get("light")), "dark": _swatch(data.get("dark"))})
    out.sort(key=lambda item: item["name"].lower())
    return out


def _theme_file_path(name):
    # Matches list_user_themes()'s filename -> display-name transform
    # (`stem.replace("_", " ").title()`) inverted the same lossy way the
    # legacy dialog always has: good enough for names it round-trips.
    filename = str(name or "").strip().lower().replace(" ", "_")
    return os.path.join(user_themes_dir(), filename + ".json")


def get_theme(kind, name):
    """Full theme payload for `kind` ("official"/"user") + `name`, or None."""
    if kind == "official":
        data = THEMES.get(name)
        return copy.deepcopy(data) if isinstance(data, dict) else None
    return _load_user_theme_file(_theme_file_path(name))


def delete_user_theme(name):
    path = _theme_file_path(name)
    if not os.path.exists(path):
        return "theme not found"
    try:
        os.remove(path)
    except OSError as exc:
        return str(exc)
    return None


# ── customization key groups (verbatim from the legacy dialog) ────────────────
#
# What counts as "part of a theme" beyond raw colors: everything a saved/shared
# theme should carry along (background modes, reviewer button styling, sidebar
# effect, icon sizes, ...). Two buckets because they live in two different
# stores — the addon config JSON vs mw.col.conf — and get read/written
# differently on apply and on export.

def theme_customization_key_groups():
    explicit_addon_keys = [
        "markerColors", "overview_style", "showOverviewProfileBar", "showCongratsProfileBar",
        "congratsMessage", "studyNowText", "hideRetentionStars",
        "onigiri_overview_bg_mode", "onigiri_overview_bg_main_blur", "onigiri_overview_bg_main_opacity",
        "onigiri_overview_bg_light_color", "onigiri_overview_bg_dark_color", "onigiri_overview_bg_image",
        "onigiri_overview_bg_image_light", "onigiri_overview_bg_image_dark", "onigiri_overview_bg_image_mode",
        "onigiri_overview_bg_color_theme_mode", "onigiri_overview_bg_image_theme_mode",
        "onigiri_overview_bg_blur", "onigiri_overview_bg_opacity",
        "onigiri_overview_slideshow_images", "onigiri_overview_slideshow_interval",
        "onigiri_reviewer_bg_mode", "onigiri_reviewer_bg_main_blur", "onigiri_reviewer_bg_main_opacity",
        "onigiri_reviewer_bg_light_color", "onigiri_reviewer_bg_dark_color", "onigiri_reviewer_bg_image",
        "onigiri_reviewer_bg_image_light", "onigiri_reviewer_bg_image_dark", "onigiri_reviewer_bg_image_mode",
        "onigiri_reviewer_bg_color_theme_mode", "onigiri_reviewer_bg_image_theme_mode",
        "onigiri_reviewer_bg_blur", "onigiri_reviewer_bg_opacity",
        "onigiri_reviewer_slideshow_images", "onigiri_reviewer_slideshow_interval",
        "onigiri_reviewer_bottom_bar_bg_mode", "onigiri_reviewer_bottom_bar_bg_light_color",
        "onigiri_reviewer_bottom_bar_bg_dark_color", "onigiri_reviewer_bottom_bar_bg_image",
        "onigiri_reviewer_bottom_bar_bg_blur", "onigiri_reviewer_bottom_bar_bg_opacity",
        "onigiri_reviewer_bottom_bar_match_main_blur", "onigiri_reviewer_bottom_bar_match_main_opacity",
        "onigiri_reviewer_bottom_bar_match_reviewer_bg_blur", "onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity",
        "onigiri_reviewer_bottom_bar_match_overview_bg_blur", "onigiri_reviewer_bottom_bar_match_overview_bg_opacity",
        "onigiri_reviewer_btn_border_size", "onigiri_reviewer_btn_radius", "onigiri_reviewer_btn_padding",
        "onigiri_reviewer_btn_height", "onigiri_reviewer_bar_height", "onigiri_reviewer_stattxt_mode",
        "onigiri_toolbar_bg_mode", "onigiri_toolbar_bg_color_light", "onigiri_toolbar_bg_color_dark",
        "onigiri_toolbar_bg_image", "onigiri_toolbar_bg_blur",
        "onigiri_sidebar_main_bg_effect_mode", "onigiri_sidebar_main_bg_effect_intensity",
        "onigiri_sidebar_opaque_tint_intensity", "onigiri_sidebar_opaque_tint_color_light",
        "onigiri_sidebar_opaque_tint_color_dark",
        "onigiri_profile_level_bar_mode", "onigiri_profile_level_bar_custom_color",
    ]
    addon_tokens = (
        "bg", "background", "font", "btn", "bar", "color", "blur", "opacity",
        "radius", "padding", "height", "effect", "slideshow", "shadow",
    )
    addon_keys = [
        key for key in config.DEFAULTS.keys()
        if key != "colors"
        and (key.startswith("onigiri_") or key.startswith("modern_menu_"))
        and any(token in key for token in addon_tokens)
    ]
    addon_keys.extend(explicit_addon_keys)
    addon_keys.extend(REVIEWER_THEME_KEYS)
    addon_keys = sorted(set(addon_keys))

    collection_keys = [
        "modern_menu_studyNowText", "onigiri_overview_style", "onigiri_overview_sync_box_effect",
        "onigiri_overview_box_color_theme_mode", "onigiri_overview_effect_blur", "onigiri_overview_effect_opacity",
        "onigiri_overview_border_radius", "onigiri_overview_border_width",
        "modern_menu_hide_folder_icon", "modern_menu_hide_subdeck_icon", "modern_menu_hide_deck_icon",
        "modern_menu_hide_filtered_deck_icon", "modern_menu_hide_default_icons",
        "modern_menu_background_mode", "modern_menu_bg_color_theme_mode", "modern_menu_bg_image_theme_mode",
        "modern_menu_background_image_mode", "modern_menu_bg_color_light", "modern_menu_bg_color_dark",
        "modern_menu_background_image", "modern_menu_background_image_light", "modern_menu_background_image_dark",
        "modern_menu_slideshow_images", "modern_menu_slideshow_interval",
        "modern_menu_background_blur", "modern_menu_background_opacity",
        "modern_menu_sidebar_bg_mode", "modern_menu_sidebar_bg_type",
        "modern_menu_sidebar_bg_color_theme_mode", "modern_menu_sidebar_bg_image_theme_mode",
        "modern_menu_sidebar_bg_color_light", "modern_menu_sidebar_bg_color_dark",
        "modern_menu_sidebar_bg_image", "modern_menu_sidebar_bg_image_light", "modern_menu_sidebar_bg_image_dark",
        "modern_menu_sidebar_slideshow_images", "modern_menu_sidebar_slideshow_interval",
        "modern_menu_sidebar_bg_blur", "modern_menu_sidebar_bg_opacity", "modern_menu_sidebar_bg_transparency",
        "modern_menu_sidebar_radius", "modern_menu_sidebar_stroke", "modern_menu_sidebar_margin",
        "modern_menu_profile_bg_mode", "modern_menu_profile_bg_dynamic_mode",
        "modern_menu_profile_bg_color_light", "modern_menu_profile_bg_color_dark",
        "modern_menu_profile_bg_image", "modern_menu_profile_bg_image_light", "modern_menu_profile_bg_image_dark",
        "modern_menu_profile_bg_blur", "modern_menu_profile_bg_opacity",
        "modern_menu_profile_picture", "modern_menu_profile_picture_light", "modern_menu_profile_picture_dark",
        "modern_menu_profile_picture_mode", "modern_menu_profile_picture_dynamic_mode",
        "modern_menu_profile_picture_color_light", "modern_menu_profile_picture_color_dark",
        "modern_menu_profile_picture_blur", "modern_menu_profile_picture_opacity",
        "onigiri_profile_page_bg_mode", "onigiri_profile_page_bg_dynamic_mode",
        "onigiri_profile_page_bg_light_color1", "onigiri_profile_page_bg_light_color2",
        "onigiri_profile_page_bg_dark_color1", "onigiri_profile_page_bg_dark_color2",
        "onigiri_canvas_inset_color_theme_mode", "onigiri_canvas_inset_effect_mode",
        "onigiri_canvas_inset_effect_intensity", "onigiri_canvas_inset_effect_blur",
        "onigiri_canvas_inset_effect_opacity", "onigiri_canvas_inset_border_radius",
        "onigiri_canvas_inset_border_width", "onigiri_canvas_inset_color_light", "onigiri_canvas_inset_color_dark",
        "onigiri_font_main", "onigiri_font_subtle", "onigiri_font_small_title",
        "onigiri_font_size_main", "onigiri_font_size_subtle", "onigiri_font_size_small_title",
        "onigiri_toolbar_bg_mode", "onigiri_toolbar_bg_color_light", "onigiri_toolbar_bg_color_dark",
        "onigiri_toolbar_bg_image", "onigiri_toolbar_bg_blur",
        "onigiri_sidebar_main_bg_effect_mode", "onigiri_sidebar_main_bg_effect_intensity",
        "onigiri_sidebar_opaque_tint_intensity", "onigiri_sidebar_opaque_tint_color_light",
        "onigiri_sidebar_opaque_tint_color_dark",
        "onigiri_profile_level_bar_mode", "onigiri_profile_level_bar_custom_color",
    ]
    for icon_key in ICON_DEFAULTS.keys():
        collection_keys.append(f"modern_menu_icon_{icon_key}")
        collection_keys.append(f"modern_menu_icon_size_{icon_key}")
    for icon_key in DEFAULT_ICON_SIZES.keys():
        collection_keys.append(f"modern_menu_icon_size_{icon_key}")
    return addon_keys, sorted(set(collection_keys))


def _asset_config_value(path_value):
    values = path_value if isinstance(path_value, list) else [path_value]
    filenames = [os.path.basename(v.strip()) for v in values if isinstance(v, str) and v.strip()]
    if not filenames:
        return None
    return filenames if isinstance(path_value, list) else filenames[0]


# ── apply ──────────────────────────────────────────────────────────────────────

def apply_theme(store, theme_data):
    """Writes every persisted part of a theme into store.config / mw.col.conf.

    Returns the set of raw config/col keys touched, so the caller can work out
    which already-rendered WebUI fields (Fonts' color pairs, Profile's) need
    their in-page value refreshed."""
    if not isinstance(theme_data, dict):
        return set()

    touched = set()
    light_palette = theme_data.get("light") if isinstance(theme_data.get("light"), dict) else {}
    dark_palette = theme_data.get("dark") if isinstance(theme_data.get("dark"), dict) else {}
    assets = theme_data.get("assets") if isinstance(theme_data.get("assets"), dict) else {}
    customization = theme_data.get("customization") if isinstance(theme_data.get("customization"), dict) else {}
    customization_collection = customization.get("collection_config", {})
    if not isinstance(customization_collection, dict):
        customization_collection = {}
    customization_addon = customization.get("addon_config", {})
    if not isinstance(customization_addon, dict):
        customization_addon = {}
    addon_keys, collection_keys = theme_customization_key_groups()
    addon_key_set = set(addon_keys)
    collection_key_set = set(collection_keys)

    cfg = store.config
    colors = cfg.setdefault("colors", {})
    colors.setdefault("light", {}).update(light_palette)
    colors.setdefault("dark", {}).update(dark_palette)
    touched.update(light_palette.keys())
    touched.update(dark_palette.keys())

    if isinstance(assets.get("images"), dict):
        for config_key, path_value in assets["images"].items():
            config_value = _asset_config_value(path_value)
            if config_value is None:
                continue
            if config_key in addon_key_set or config_key in cfg or config_key.startswith("onigiri_"):
                cfg[config_key] = copy.deepcopy(config_value)
                touched.add(config_key)
            if config_key in collection_key_set or config_key.startswith("modern_menu_"):
                _col_set(mw.col, config_key, copy.deepcopy(config_value))
                touched.add(config_key)

    if isinstance(assets.get("icon_config"), dict):
        for icon_key, icon_value in assets["icon_config"].items():
            conf_key = f"modern_menu_icon_{icon_key}"
            filename = os.path.basename(str(icon_value)) if icon_value else ""
            _col_set(mw.col, conf_key, "" if not filename or filename == str(icon_key) else filename)
            touched.add(conf_key)

    if isinstance(assets.get("icons"), dict):
        for icon_key, icon_value in assets["icons"].items():
            filename = os.path.basename(icon_value) if icon_value else ""
            if filename:
                conf_key = f"modern_menu_icon_{icon_key}"
                _col_set(mw.col, conf_key, filename)
                touched.add(conf_key)

    if isinstance(assets.get("font_config"), dict):
        for type_key, font_key in assets["font_config"].items():
            if type_key in ("main", "subtle", "small_title") or (isinstance(type_key, str) and type_key.startswith("size_")):
                conf_key = f"onigiri_font_{type_key}"
                _col_set(mw.col, conf_key, font_key)
                touched.add(conf_key)

    reviewer_settings = theme_data.get("reviewer_settings")
    if isinstance(reviewer_settings, dict):
        cfg.update(reviewer_settings)
        touched.update(reviewer_settings.keys())

    if "modern_menu_bg_color_light" not in customization_collection and light_palette.get("--bg"):
        _col_set(mw.col, "modern_menu_bg_color_light", light_palette["--bg"])
        touched.add("modern_menu_bg_color_light")
    if "modern_menu_bg_color_dark" not in customization_collection and dark_palette.get("--bg"):
        _col_set(mw.col, "modern_menu_bg_color_dark", dark_palette["--bg"])
        touched.add("modern_menu_bg_color_dark")

    overview_colors = cfg.setdefault("overview_style", {}).setdefault("colors", {})
    for mode, palette in (("light", light_palette), ("dark", dark_palette)):
        theme_bg = palette.get("--bg")
        if not theme_bg:
            continue
        if "overview_style" not in customization_addon:
            overview_colors.setdefault(mode, {})["box_bg"] = theme_bg
        sidebar_key = f"modern_menu_sidebar_bg_color_{mode}"
        if sidebar_key not in customization_collection:
            _col_set(mw.col, sidebar_key, theme_bg)
            touched.add(sidebar_key)

    if customization_addon:
        cfg.update(copy.deepcopy(customization_addon))
        touched.update(customization_addon.keys())
    if customization_collection:
        for key, value in customization_collection.items():
            _col_set(mw.col, key, copy.deepcopy(value))
            touched.add(key)

    store.write_config()
    return touched


def reset_theme_to_default(store):
    """Resets colors and reviewer button styling to the color-only default."""
    cfg = store.config
    cfg["colors"] = copy.deepcopy(config.DEFAULTS["colors"])
    touched = set(cfg["colors"]["light"].keys()) | set(cfg["colors"]["dark"].keys())
    for key in REVIEWER_THEME_KEYS:
        if key in config.DEFAULTS:
            cfg[key] = copy.deepcopy(config.DEFAULTS[key])
            touched.add(key)
    store.write_config()
    return touched


# ── export ─────────────────────────────────────────────────────────────────────

def _gather_active_images(cfg):
    image_key_map = {
        "modern_menu_background_image": "main_bg", "modern_menu_background_image_light": "main_bg",
        "modern_menu_background_image_dark": "main_bg", "modern_menu_slideshow_images": "main_bg",
        "onigiri_overview_bg_image": "main_bg", "onigiri_overview_bg_image_light": "main_bg",
        "onigiri_overview_bg_image_dark": "main_bg", "onigiri_overview_slideshow_images": "main_bg",
        "modern_menu_profile_bg_image": "profile_bg", "modern_menu_profile_bg_image_light": "profile_bg",
        "modern_menu_profile_bg_image_dark": "profile_bg",
        "modern_menu_profile_picture": "profile", "modern_menu_profile_picture_light": "profile",
        "modern_menu_profile_picture_dark": "profile",
        "modern_menu_sidebar_bg_image": "sidebar_bg", "modern_menu_sidebar_bg_image_light": "sidebar_bg",
        "modern_menu_sidebar_bg_image_dark": "sidebar_bg", "modern_menu_sidebar_slideshow_images": "sidebar_bg",
        "onigiri_reviewer_bg_image": "reviewer_bg", "onigiri_reviewer_bg_image_light": "reviewer_bg",
        "onigiri_reviewer_bg_image_dark": "reviewer_bg", "onigiri_reviewer_slideshow_images": "reviewer_bg",
        "onigiri_reviewer_bottom_bar_bg_image": "reviewer_bar_bg",
        "onigiri_toolbar_bg_image": "toolbar_bg",
    }
    active_images = {}
    assets_to_zip = []
    for key, subfolder in image_key_map.items():
        value = cfg.get(key)
        if value in (None, "", []):
            value = _col_get(mw.col, key, None) if mw and mw.col else None
        filenames = value if isinstance(value, list) else [value]
        archive_paths = []
        for filename in filenames:
            if not filename or not isinstance(filename, str):
                continue
            full_path = os.path.join(ADDON_ROOT, "user_files", subfolder, filename)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                archive_path = f"images/{subfolder}/{filename}"
                if not any(a[1] == archive_path for a in assets_to_zip):
                    assets_to_zip.append((full_path, archive_path))
                archive_paths.append(archive_path)
        if archive_paths:
            active_images[key] = archive_paths if isinstance(value, list) else archive_paths[0]
    return active_images, assets_to_zip


def _gather_active_icons():
    active_icons = {}
    icon_config = {}
    assets_to_zip = []
    for icon_key in ICON_DEFAULTS.keys():
        conf_key = f"modern_menu_icon_{icon_key}"
        filename = _col_get(mw.col, conf_key, "") if mw and mw.col else ""
        icon_config[icon_key] = filename if filename else icon_key
        if not filename:
            continue
        filepath = ""
        icon_subfolder = "icons"
        for candidate_subfolder in ("icons", "custom_deck_icons"):
            candidate_path = os.path.join(ADDON_ROOT, "user_files", candidate_subfolder, filename)
            if os.path.exists(candidate_path):
                filepath, icon_subfolder = candidate_path, candidate_subfolder
                break
        if filepath:
            archive_path = f"icons/{filename}" if icon_subfolder == "icons" else f"icons/custom_deck_icons/{filename}"
            if not any(a[1] == archive_path for a in assets_to_zip):
                assets_to_zip.append((filepath, archive_path))
            active_icons[icon_key] = archive_path
    return active_icons, icon_config, assets_to_zip


def _gather_fonts():
    font_config = {}
    assets_to_zip = []
    for font_type in ("main", "subtle", "small_title"):
        font_key = _col_get(mw.col, f"onigiri_font_{font_type}", None) if mw and mw.col else None
        if font_key:
            font_config[font_type] = font_key
            font_path = os.path.join(ADDON_ROOT, "user_files", "fonts", font_key)
            if os.path.exists(font_path) and os.path.isfile(font_path):
                archive_path = f"fonts/{font_key}"
                if not any(a[1] == archive_path for a in assets_to_zip):
                    assets_to_zip.append((font_path, archive_path))
        size_value = _col_get(mw.col, f"onigiri_font_size_{font_type}", None) if mw and mw.col else None
        if size_value is not None:
            font_config[f"size_{font_type}"] = size_value
    return font_config, assets_to_zip


def build_export_payload(store):
    """Everything the *currently active* setup would need to become a theme."""
    cfg = store.config
    light_palette = {key: cfg.get("colors", {}).get("light", {}).get(key) for key in ALL_THEME_KEYS}
    dark_palette = {key: cfg.get("colors", {}).get("dark", {}).get(key) for key in ALL_THEME_KEYS}
    light_palette = {k: v for k, v in light_palette.items() if v is not None}
    dark_palette = {k: v for k, v in dark_palette.items() if v is not None}

    reviewer_settings = {key: cfg.get(key) for key in REVIEWER_THEME_KEYS if cfg.get(key) is not None}

    addon_keys, collection_keys = theme_customization_key_groups()
    addon_config = {key: copy.deepcopy(cfg[key]) for key in addon_keys if key in cfg}
    collection_config = {}
    if mw and mw.col:
        for key in collection_keys:
            value = _col_get(mw.col, key, None)
            if value is not None:
                collection_config[key] = copy.deepcopy(value)

    theme_data = {
        "light": light_palette,
        "dark": dark_palette,
        "reviewer_settings": reviewer_settings,
        "customization": {"addon_config": addon_config, "collection_config": collection_config},
        "assets": {"fonts": {}, "images": {}, "icons": {}, "font_config": {}, "icon_config": {}},
    }

    assets_to_zip = []
    font_config, font_assets = _gather_fonts()
    theme_data["assets"]["font_config"] = font_config
    for _, archive_path in font_assets:
        theme_data["assets"]["fonts"][os.path.basename(archive_path)] = archive_path
    assets_to_zip.extend(font_assets)

    active_images, image_assets = _gather_active_images(cfg)
    theme_data["assets"]["images"] = active_images
    assets_to_zip.extend(image_assets)

    active_icons, icon_config, icon_assets = _gather_active_icons()
    theme_data["assets"]["icons"] = active_icons
    theme_data["assets"]["icon_config"] = icon_config
    assets_to_zip.extend(icon_assets)

    return theme_data, assets_to_zip


def export_theme(store, name, parent=None):
    """Native Save dialog + zips the current setup into a `.onigiri` file."""
    from aqt.qt import QFileDialog

    theme_data, assets_to_zip = build_export_payload(store)
    suggested = name.lower().replace(" ", "_") + ".onigiri"
    save_path, _ = QFileDialog.getSaveFileName(
        parent, "Save Theme As", os.path.join(user_themes_dir(), suggested), "Onigiri Theme Files (*.onigiri)"
    )
    if not save_path:
        return None, None

    try:
        with zipfile.ZipFile(save_path, "w") as zf:
            zf.writestr("theme.json", json.dumps(theme_data, indent=2))
            for source, dest in assets_to_zip:
                zf.write(source, dest)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)
    return save_path, None


# ── import ─────────────────────────────────────────────────────────────────────

def import_theme(parent=None):
    """Native Open dialog + extracts a `.onigiri` file into user_files/ and
    user_themes/. Returns (summary_dict, error)."""
    from aqt.qt import QFileDialog

    filepath, _ = QFileDialog.getOpenFileName(
        parent, "Import Theme", "", "Onigiri Theme Files (*.onigiri)"
    )
    if not filepath:
        return None, None

    filename = os.path.basename(filepath)
    if not filename.lower().endswith(".onigiri"):
        return None, "The selected file is not a .onigiri theme."
    if not zipfile.is_zipfile(filepath):
        return None, "The selected file is not a valid zip archive."

    try:
        with zipfile.ZipFile(filepath, "r") as zf:
            try:
                with zf.open("theme.json") as handle:
                    theme_data = json.load(handle)
            except KeyError:
                return None, "The .onigiri file is missing theme.json."

            assets = theme_data.get("assets", {})
            theme_name = os.path.splitext(filename)[0]

            def extract(archive_path, default_dir):
                parts = archive_path.split("/")
                if len(parts) >= 3 and parts[0] == "images":
                    dest_dir = os.path.join(ADDON_ROOT, "user_files", parts[1])
                    out_name = parts[-1]
                else:
                    dest_dir = default_dir
                    out_name = os.path.basename(archive_path)
                os.makedirs(dest_dir, exist_ok=True)
                target = os.path.join(dest_dir, out_name)
                with zf.open(archive_path) as source, open(target, "wb") as out:
                    shutil.copyfileobj(source, out)
                return target

            if "images" in assets and isinstance(assets["images"], dict):
                images_dir = os.path.join(ADDON_ROOT, "user_files", "images", theme_name)
                for config_key, archive_value in list(assets["images"].items()):
                    archive_paths = archive_value if isinstance(archive_value, list) else [archive_value]
                    extracted = []
                    for archive_path in archive_paths:
                        if not isinstance(archive_path, str):
                            continue
                        try:
                            extract(archive_path, images_dir)
                            extracted.append(os.path.basename(archive_path))
                        except KeyError:
                            pass
                    if extracted:
                        assets["images"][config_key] = extracted if isinstance(archive_value, list) else extracted[0]

            if "fonts" in assets and isinstance(assets["fonts"], dict):
                fonts_dir = os.path.join(ADDON_ROOT, "user_files", "fonts")
                for archive_path in list(assets["fonts"].values()):
                    try:
                        extract(archive_path, fonts_dir)
                    except KeyError:
                        pass

            if "icons" in assets and isinstance(assets["icons"], dict):
                icons_dir = os.path.join(ADDON_ROOT, "user_files", "icons")
                custom_deck_dir = os.path.join(ADDON_ROOT, "user_files", "custom_deck_icons")
                for icon_key, archive_path in list(assets["icons"].items()):
                    try:
                        parts = archive_path.split("/")
                        dest_dir = custom_deck_dir if len(parts) >= 3 and parts[1] == "custom_deck_icons" else icons_dir
                        extract(archive_path, dest_dir)
                        assets["icons"][icon_key] = os.path.basename(archive_path)
                    except KeyError:
                        pass

            theme_data["assets"] = assets
            json_path = os.path.join(user_themes_dir(), theme_name + ".json")
            safe_storage.atomic_write_json(json_path, theme_data)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)

    display_name = theme_name.replace("_", " ").title()
    return {"name": display_name, "light": _swatch(theme_data.get("light")), "dark": _swatch(theme_data.get("dark"))}, None
