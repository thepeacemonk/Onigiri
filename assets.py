"""Asset path helpers shared across Onigiri modules."""

import os

from aqt.qt import QRectF

ADDON_ROOT = os.path.dirname(__file__)
SYSTEM_ICONS_DIR = os.path.join(ADDON_ROOT, "system_files", "system_icons")
SYSTEM_ICONS_AVAILABLE_DIR = os.path.join(SYSTEM_ICONS_DIR, "available_for_users")
SYSTEM_ICONS_UNAVAILABLE_DIR = os.path.join(SYSTEM_ICONS_DIR, "unavailable_for_users")


def system_icon_path(filename, users_only=False):
    if not filename:
        return ""
    filename = os.path.basename(str(filename))
    search_dirs = (
        [SYSTEM_ICONS_AVAILABLE_DIR]
        if users_only
        else [SYSTEM_ICONS_UNAVAILABLE_DIR, SYSTEM_ICONS_AVAILABLE_DIR]
    )
    for directory in search_dirs:
        path = os.path.join(directory, filename)
        if os.path.exists(path):
            return path
    legacy_path = os.path.join(SYSTEM_ICONS_DIR, filename)
    return legacy_path if os.path.exists(legacy_path) else os.path.join(search_dirs[0], filename)


def svg_contain_rect(renderer, size, padding=0):
    """Return a centered render rect that preserves the SVG viewBox aspect ratio."""
    size = max(1, float(size))
    padding = max(0, float(padding))
    target = max(1.0, size - padding * 2)
    view_box = renderer.viewBoxF()
    width = view_box.width()
    height = view_box.height()
    if width <= 0 or height <= 0:
        default_size = renderer.defaultSize()
        width = default_size.width() or target
        height = default_size.height() or target
    ratio = width / height if height else 1.0
    if ratio >= 1:
        render_w = target
        render_h = target / ratio
    else:
        render_h = target
        render_w = target * ratio
    return QRectF(
        padding + (target - render_w) / 2,
        padding + (target - render_h) / 2,
        render_w,
        render_h,
    )
