# Image library behind the WebUI gallery popover.
#
# The classic settings window had one enormous "Gallery" page listing every
# folder at once, and each consumer page owned a separate combo box + Import
# button that had to be kept in sync with it by hand. This module replaces both
# halves with a small file API the page drives directly:
#
#   list_images(folder)   what is on disk, newest first
#   import_images(folder) native file picker -> copies in -> returns new names
#   delete_image(folder)  removes one file
#
# Callers stay responsible for clearing references to a deleted file; the
# folder -> config-key map lives here (KEYS_BY_FOLDER) so there is exactly one
# place to update when a new image setting appears.

import os
import shutil

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
ICON_EXTENSIONS = (".svg", ".png")

ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Folder id -> directory under user_files/. The id is what a schema field names
# in its "folder" key and what travels over the bridge, so nothing outside this
# dict can address a path — a folder the page asks for that is not listed here
# is refused rather than resolved.
FOLDERS = {
    "profile": "profile",
    "profile_bg": "profile_bg",
    "main_bg": "main_bg",
    "sidebar_bg": "sidebar_bg",
    "reviewer_bg": "reviewer_bg",
    "reviewer_bar_bg": "reviewer_bar_bg",
    "toolbar_bg": "toolbar_bg",
    # Games pages: Onigimon's scene backdrop and Mochi's messenger picture.
    # Both were imported through their own one-off file dialogs before the
    # Gamification window folded into this one.
    "onigimon_bg": "onigimon_backgrounds",
    "mochi_icon": "mochi_messenger",
    # User-uploaded icons for the icon popover (settings_web/render.py's
    # pickable_icons_context() lists these alongside the bundled system set).
    "icons": "icons",
}

# Every setting that stores a filename from a folder. Deleting a file has to
# clear these or the renderers keep asking for a picture that is gone. Mirrors
# settings/_page_gallery._clear_deleted_gallery_asset_references, inverted.
KEYS_BY_FOLDER = {
    "profile": [
        "modern_menu_profile_picture",
        "modern_menu_profile_picture_light",
        "modern_menu_profile_picture_dark",
    ],
    "profile_bg": [
        "modern_menu_profile_bg_image",
        "modern_menu_profile_bg_image_light",
        "modern_menu_profile_bg_image_dark",
    ],
    "main_bg": [
        "modern_menu_background_image",
        "modern_menu_background_image_light",
        "modern_menu_background_image_dark",
        "modern_menu_slideshow_images",
        "onigiri_overview_bg_image",
        "onigiri_overview_bg_image_light",
        "onigiri_overview_bg_image_dark",
        "onigiri_overview_slideshow_images",
    ],
    "sidebar_bg": [
        "modern_menu_sidebar_bg_image",
        "modern_menu_sidebar_bg_image_light",
        "modern_menu_sidebar_bg_image_dark",
        "modern_menu_sidebar_slideshow_images",
    ],
    "reviewer_bg": [
        "onigiri_reviewer_bg_image",
        "onigiri_reviewer_bg_image_light",
        "onigiri_reviewer_bg_image_dark",
        "onigiri_reviewer_slideshow_images",
    ],
    "reviewer_bar_bg": ["onigiri_reviewer_bottom_bar_bg_image"],
    "toolbar_bg": ["onigiri_toolbar_bg_image"],
}

# The same idea for settings that sit inside a nested config object rather than
# at the top level. Each entry is the path to the value, and only the addon
# config is ever walked — nothing nested lives in mw.col.conf.
NESTED_KEYS_BY_FOLDER = {
    "onigimon_bg": [["onigimon", "scene_background_image"]],
    "mochi_icon": [["mochi_messages", "custom_icon"]],
}


def folder_path(folder, create=False):
    """Absolute path for a folder id, or None if the id is not registered."""
    relative = FOLDERS.get(str(folder or ""))
    if relative is None:
        return None
    path = os.path.join(ADDON_ROOT, "user_files", relative)
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def list_images(folder, url_for=None, extensions=IMAGE_EXTENSIONS):
    """Files in `folder`, newest first.

    Newest first because the only reason to open the picker right after an
    import is to use what was just imported; alphabetical would bury it."""
    path = folder_path(folder)
    if not path or not os.path.isdir(path):
        return []
    out = []
    try:
        names = os.listdir(path)
    except OSError:
        return []
    for name in names:
        if not name.lower().endswith(extensions):
            continue
        full = os.path.join(path, name)
        try:
            stat = os.stat(full)
        except OSError:
            continue
        out.append({
            "name": name,
            "url": url_for(folder, name) if url_for else "",
            "size": int(stat.st_size),
            "modified": float(stat.st_mtime),
        })
    out.sort(key=lambda item: item["modified"], reverse=True)
    return out


def _unique_name(directory, filename):
    base, ext = os.path.splitext(os.path.basename(filename))
    candidate = os.path.basename(filename)
    index = 2
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f"{base}-{index}{ext}"
        index += 1
    return candidate


def import_images(folder, parent=None, title="Import image", extensions=IMAGE_EXTENSIONS, filter_label="Images"):
    """Native multi-select file picker; copies the chosen files in.

    Returns (added_names, error). An empty list with no error means the user
    cancelled, which the page treats as a no-op rather than a failure."""
    from aqt.qt import QFileDialog

    directory = folder_path(folder, create=True)
    if not directory:
        return [], f"unknown gallery folder {folder!r}"

    pattern = " ".join("*" + ext for ext in extensions)
    paths, _ = QFileDialog.getOpenFileNames(parent, title, "", f"{filter_label} ({pattern})")
    if not paths:
        return [], None

    added = []
    for source in paths:
        try:
            if os.path.dirname(os.path.abspath(source)) == os.path.abspath(directory):
                # Already in the gallery — importing it again would only make a
                # duplicate the user has to clean up.
                added.append(os.path.basename(source))
                continue
            name = _unique_name(directory, os.path.basename(source))
            shutil.copy(source, os.path.join(directory, name))
            added.append(name)
        except Exception as exc:  # noqa: BLE001 - one bad file must not lose the rest
            print(f"[Onigiri] settings_web gallery: could not import {source}: {exc}")
    if not added:
        return [], "No file could be imported"
    return added, None


def delete_image(folder, name):
    """Removes one file. Returns an error string, or None on success."""
    directory = folder_path(folder)
    if not directory:
        return f"unknown gallery folder {folder!r}"
    name = os.path.basename(str(name or ""))
    if not name:
        return "no file named"
    target = os.path.join(directory, name)
    # os.path.basename above already blocks traversal; this catches symlink
    # trickery too, and costs nothing.
    if os.path.dirname(os.path.abspath(target)) != os.path.abspath(directory):
        return "refusing to delete outside the gallery folder"
    if not os.path.exists(target):
        return None
    try:
        os.remove(target)
    except OSError as exc:
        return str(exc)
    return None


def clear_references(folder, name, stores):
    """Blanks every setting in `stores` that still points at a deleted file.

    `stores` are plain mutable mappings (the addon config dict, mw.col.conf).
    List-valued keys (the slideshows) drop the entry instead of being cleared,
    so removing one slide does not empty the whole show. Returns the keys that
    actually changed."""
    changed = []
    for key in KEYS_BY_FOLDER.get(str(folder or ""), []):
        for store in stores:
            if store is None:
                continue
            try:
                value = store.get(key)
            except Exception:
                continue
            if isinstance(value, list):
                cleaned = [item for item in value if os.path.basename(str(item)) != name]
                if cleaned != value:
                    store[key] = cleaned
                    changed.append(key)
            elif value and os.path.basename(str(value)) == name:
                store[key] = ""
                changed.append(key)
    for path in NESTED_KEYS_BY_FOLDER.get(str(folder or ""), []):
        for store in stores:
            if not isinstance(store, dict):
                continue
            node = store
            for part in path[:-1]:
                node = node.get(part) if isinstance(node, dict) else None
                if not isinstance(node, dict):
                    break
            if not isinstance(node, dict):
                continue
            value = node.get(path[-1])
            if value and os.path.basename(str(value)) == name:
                node[path[-1]] = ""
                changed.append(path[-1])
    return list(dict.fromkeys(changed))
