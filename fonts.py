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

# <<< START NEW CODE >>>
def load_user_fonts(addon_path: str) -> dict:
    """Scans for user-added fonts and returns a dictionary."""
    user_fonts = {}
    fonts_dir = os.path.join(addon_path, "user_files", "fonts")
    os.makedirs(fonts_dir, exist_ok=True)

    for filename in os.listdir(fonts_dir):
        if filename.lower().endswith((".ttf", ".otf", ".woff", ".woff2")):
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
    return user_fonts

def get_all_fonts(addon_path: str) -> dict:
    """Returns a merged dictionary of system and user fonts."""
    all_fonts = FONTS.copy()
    user_fonts = load_user_fonts(addon_path)
    all_fonts.update(user_fonts)
    return all_fonts
# <<< END NEW CODE >>>