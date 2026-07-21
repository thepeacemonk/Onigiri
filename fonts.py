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

# Poppins is the add-on's default typeface. The "system" font key resolves to
# this full stack (Poppins first, apple-system as fallback), so every surface
# that inherits the default renders Poppins once the @font-face / Qt fonts are
# registered. See register_poppins_qt() and poppins_font_face_css().
POPPINS_STACK = (
    "'Poppins', -apple-system, BlinkMacSystemFont, \"Segoe UI\", "
    "Roboto, Helvetica, Arial, sans-serif"
)

# (filename, css font-weight, css font-style) for every Poppins weight we ship
# under system_files/fonts/system_fonts/Poppins/.
#
# The add-on caps its typography at Medium (500). Rather than rewriting the
# hundreds of `font-weight: 600/700/bold` rules scattered across the CSS, the
# Medium faces claim the whole 500-900 range. Any rule asking for a heavier
# weight matches a real face, so the browser renders Medium and does *not*
# fall back to synthetic bolding. Poppins-Bold.ttf stays on disk but unused.
POPPINS_WEIGHTS = [
    ("Poppins-Light.ttf", 300, "normal"),
    ("Poppins-LightItalic.ttf", 300, "italic"),
    ("Poppins-Regular.ttf", 400, "normal"),
    ("Poppins-Italic.ttf", 400, "italic"),
    ("Poppins-Medium.ttf", "500 900", "normal"),
    ("Poppins-MediumItalic.ttf", "500 900", "italic"),
]

_POPPINS_SUBDIR = ("system_files", "fonts", "system_fonts", "Poppins")

FONTS = {
    "system": {
        "name": "Poppins",
        "family": POPPINS_STACK,
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
    "silkscreen": {
        "name": "Silkscreen",
        "family": "Silkscreen",
        "file": "Silkscreen.ttf",
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


_POPPINS_QT_REGISTERED = set()


def register_poppins_qt(addon_path: str) -> None:
    """Registers every Poppins weight into Qt so 'Poppins' resolves in QSS.

    Idempotent per addon_path. Safe to call at profile open. Native dialogs
    that set font-family: 'Poppins' rely on this."""
    if addon_path in _POPPINS_QT_REGISTERED:
        return
    base = os.path.join(addon_path, *_POPPINS_SUBDIR)
    for filename, _weight, _style in POPPINS_WEIGHTS:
        path = os.path.join(base, filename)
        try:
            QFontDatabase.addApplicationFont(path)
        except Exception:
            pass
    _POPPINS_QT_REGISTERED.add(addon_path)


def poppins_font_face_css(addon_package: str) -> str:
    """Returns @font-face rules for all Poppins weights, for webview <style>.

    addon_package is the addon folder name (e.g. '1011095603')."""
    subdir = "/".join(_POPPINS_SUBDIR)
    faces = []
    for filename, weight, style in POPPINS_WEIGHTS:
        url = f"/_addons/{addon_package}/{subdir}/{filename}"
        faces.append(
            "@font-face {"
            "font-family: 'Poppins';"
            f"src: url('{url}');"
            f"font-weight: {weight};"
            f"font-style: {style};"
            "font-display: swap;"
            "}"
        )
    return "".join(faces)
# <<< END NEW CODE >>>
