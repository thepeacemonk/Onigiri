# fonts.py

import os
from aqt.qt import QFontDatabase

"""
Defines the font configurations available in the Onigiri settings.

Each font is defined with:
- name: The display name shown on the font card in the settings UI.
- family: The exact CSS font-family value to be used.
- file: The filename located in 'user_files/fonts/system_fonts/'. 
        Set to None for the default system font.
"""

FONTS = {
    "system": {
        "name": "System",
        "family": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "file": None,
    },
    "nunito": {
        "name": "Nunito",
        "family": "Nunito",
        "file": "Nunito.ttf",
    },
    "montserrat": {
        "name": "Montserrat",
        "family": "Montserrat",
        "file": "Montserrat.ttf",
    },
    "instrument_serif": {
        "name": "Instrument",
        "family": "Instrument Serif",
        "file": "Instrument.ttf",
    },
    "space_mono": {
        "name": "Space",
        "family": "SpaceMono",
        "file": "SpaceMono.ttf",
    },
}

_USER_FONTS_CACHE = {}


def _fonts_dir_signature(fonts_dir: str):
    try:
        entries = []
        for entry in os.scandir(fonts_dir):
            if not entry.name.lower().endswith((".ttf", ".otf", ".woff", ".woff2")):
                continue
            try:
                stat = entry.stat()
                entries.append((entry.name, stat.st_mtime_ns, stat.st_size))
            except OSError:
                entries.append((entry.name, 0, 0))
        return tuple(sorted(entries))
    except OSError:
        return ()


def load_user_fonts(addon_path: str) -> dict:
    """Scans for user-added fonts and returns a dictionary."""
    fonts_dir = os.path.join(addon_path, "user_files", "fonts")
    os.makedirs(fonts_dir, exist_ok=True)

    signature = _fonts_dir_signature(fonts_dir)
    cached = _USER_FONTS_CACHE.get(addon_path)
    if cached and cached[0] == signature:
        return cached[1].copy()

    user_fonts = {}
    for filename, _, _ in signature:
        font_path = os.path.join(fonts_dir, filename)
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                display_name = font_families[0]
                pretty_name = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()
                user_fonts[filename] = {
                    "name": pretty_name,
                    "family": display_name,
                    "file": filename,
                    "user": True,  # Flag to identify as a user-added font
                }
    _USER_FONTS_CACHE[addon_path] = (signature, user_fonts.copy())
    return user_fonts

def get_all_fonts(addon_path: str) -> dict:
    """Returns a merged dictionary of system and user fonts."""
    all_fonts = FONTS.copy()
    user_fonts = load_user_fonts(addon_path)
    all_fonts.update(user_fonts)
    return all_fonts
# <<< END NEW CODE >>>
