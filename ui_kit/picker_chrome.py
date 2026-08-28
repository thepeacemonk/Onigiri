# Shared visual language for every Onigiri icon/emoji picker.
#
# There used to be three pickers with three different looks (two Qt dialogs in
# this file's sibling `_icon_picker.py`, one HTML modal in `web/icon_modal.js`).
# The tokens below are the single source of truth for the Qt side; the JS modal
# mirrors the same numbers so the three read as one dialog.
#
# Design rules: flat surfaces, hairlines only where they carry meaning (never on
# idle cells), selection shown by an accent tint instead of an outline, and no
# hover transitions/transforms — the pickers build hundreds of cells, so every
# animated property is paid for on scroll.
from .common import *
# `import *` skips underscore-prefixed names, so this one needs spelling out.
from .common import _contrast_icon_color


PANEL_RADIUS = 18
CELL_RADIUS = 12
CONTROL_RADIUS = 10
CELL_SIZE = 60

# Icon-selector geometry. One design for every icon picker in the add-on (the
# two Qt dialogs here, the deck browser's web/icon_modal.js, and the WebUI
# settings popover in web/settings.js): a tinted header strip, a segmented
# Icons/Upload switch, a search field, and the grid inside its own inset panel
# with the user's own icons listed above the system ones.
ICON_MODAL_RADIUS = 20
ICON_CELL_SIZE = 44
ICON_CELL_RADIUS = 10
SEGMENT_RADIUS = 12
SEGMENT_BTN_RADIUS = 9
SEGMENT_BTN_HEIGHT = 30
GRID_PANEL_RADIUS = 14


def picker_palette(dark, accent="#00A982"):
    """Flat token set for a picker surface. `dark` is the picker's own
    light/dark state, which can differ from Anki's (Hashi Notes forces it).

    Values mirror `PageColorsMixin._settings_palette()` so a picker opened from
    the settings window reads as the same surface: same greys, fully opaque (a
    translucent panel let the settings page bleed through and shifted every
    tone), inset tiles on `--highlight-bg` instead of white-on-white alpha."""
    if dark:
        return {
            "dark": True,
            "accent": accent,
            "surface": "#242424",
            "surface_solid": "#242424",
            "fg": "#f4f4f5",
            "muted": "#8a8a8a",
            "inset": "#303030",
            "inset_hover": "#3a3a3a",
            "hairline": "#454545",
            "surface_alt": "#2a2a2a",
            "fg_muted": "#a1a1a4",
        }
    return {
        "dark": False,
        "accent": accent,
        "surface": "#ffffff",
        "surface_solid": "#ffffff",
        "fg": "#202124",
        "muted": "#8f9299",
        "inset": "#f2f2f2",
        "inset_hover": "#e9e9e9",
        "hairline": "#dcdde1",
        "surface_alt": "#fbfbfa",
        "fg_muted": "#63666c",
    }


def container_qss(pal, name="IconPickerContainer"):
    return (
        f"QFrame#{name} {{ background-color: {pal['surface']};"
        f" border-radius: {PANEL_RADIUS}px; border: 1px solid {pal['hairline']}; }}"
    )


def title_qss(pal):
    return f"background: transparent; font-weight: 600; font-size: 15px; color: {pal['fg']};"


def section_title_qss(pal):
    return (
        f"background: transparent; color: {pal['muted']}; font-size: 11px;"
        " font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;"
    )


def close_qss(pal):
    return (
        "/* onigiri-rounded-button-fix */\n"
        f"QPushButton {{ background: transparent; border: 1px solid transparent;"
        f" border-radius: {CONTROL_RADIUS}px; color: {pal['muted']}; font-size: 18px; }}"
        f" QPushButton:hover {{ background: {pal['inset']}; color: {pal['fg']};"
        f" border: 1px solid transparent; border-radius: {CONTROL_RADIUS}px; }}"
    )


def tabs_qss(pal):
    return f"""
        QTabWidget::pane {{ border: none; background: transparent; }}
        QTabBar::tab {{
            min-height: 28px;
            padding: 0 14px;
            margin-right: 4px;
            border: none;
            border-radius: {CONTROL_RADIUS}px;
            color: {pal['muted']};
            background: transparent;
            font-size: 13px;
        }}
        QTabBar::tab:selected {{ color: {pal['fg']}; background: {pal['inset']}; }}
        QTabBar {{ qproperty-drawBase: 0; }}
    """


def search_qss(pal):
    return (
        f"QLineEdit {{ background-color: {pal['inset']}; border: 1px solid transparent;"
        f" border-radius: {CONTROL_RADIUS}px; color: {pal['fg']}; padding: 0 12px; }}"
        f" QLineEdit:focus {{ border: 1px solid {pal['accent']}; }}"
    )


def scroll_qss(pal):
    return f"""
        QScrollArea {{ border: none; background: transparent; }}
        QWidget {{ background: transparent; }}
        QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 2px 4px 0; }}
        QScrollBar::handle:vertical {{ background: {pal['hairline']}; border-radius: 4px; min-height: 24px; }}
        QScrollBar::handle:vertical:hover {{ background: {pal['muted']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QScrollBar:horizontal {{ height: 0; }}
    """


def _rgba(color, alpha):
    c = QColor(color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


def cell_qss(pal, selected, accent=None):
    """Idle cells carry no outline at all — only the selected one does."""
    accent = accent or pal["accent"]
    if selected:
        return (
            f"QFrame {{ background: {_rgba(accent, 0.16)}; border: 1px solid {accent};"
            f" border-radius: {CELL_RADIUS}px; }}"
        )
    return (
        f"QFrame {{ background: {pal['inset']}; border: 1px solid transparent;"
        f" border-radius: {CELL_RADIUS}px; }}"
        f" QFrame:hover {{ background: {pal['inset_hover']}; }}"
    )


def pill_qss(pal, primary=False, name="iconPickerFooterPill"):
    if primary:
        hover = QColor(pal["accent"]).lighter(112).name()
        return (
            "/* onigiri-rounded-button-fix */\n"
            f"QPushButton#{name} {{ background: {pal['accent']}; color: #ffffff; border: none;"
            f" border-radius: {CONTROL_RADIUS}px; padding: 0 18px; font-weight: 600; }}"
            f" QPushButton#{name}:hover {{ background: {hover}; }}"
        )
    return (
        "/* onigiri-rounded-button-fix */\n"
        f"QPushButton#{name} {{ background: {pal['inset']}; color: {pal['fg']};"
        f" border: 1px solid transparent; border-radius: {CONTROL_RADIUS}px; padding: 0 16px; }}"
        f" QPushButton#{name}:hover {{ background: {pal['inset_hover']}; }}"
    )


def color_chip_qss(pal, color):
    return (
        f"QPushButton {{ background-color: {color}; color: {_contrast_icon_color(color).name()};"
        f" border: none; border-radius: {CONTROL_RADIUS}px; font-size: 13px;"
        " font-family: monospace; letter-spacing: 0.5px; padding: 0 12px; outline: none; }"
        f" QPushButton:hover {{ background-color: {QColor(color).lighter(108).name()}; }}"
    )


def panel_qss(pal, name):
    return (
        f"QFrame#{name} {{ background: {pal['inset']}; border: 1px solid transparent;"
        f" border-radius: 14px; }}"
        f" QLabel {{ background: transparent; border: none; color: {pal['fg']}; }}"
    )


# ── icon-selector chrome ───────────────────────────────────────────────────────
#
# Everything below belongs to the one icon-selector design; the builders above
# stay as they are for the other pickers that share this module.

def icon_modal_qss(pal, name="IconPickerContainer"):
    return (
        f"QFrame#{name} {{ background-color: {pal['surface']};"
        f" border-radius: {ICON_MODAL_RADIUS}px; border: 1px solid {pal['hairline']}; }}"
    )


def icon_header_qss(pal, name="IconPickerHeader"):
    """Tinted strip across the top, hairline under it, rounded to the modal."""
    return (
        f"QFrame#{name} {{ background: {pal['inset']}; border: none;"
        f" border-top-left-radius: {ICON_MODAL_RADIUS}px;"
        f" border-top-right-radius: {ICON_MODAL_RADIUS}px;"
        f" border-bottom: 1px solid {pal['hairline']}; }}"
        f" QLabel {{ background: transparent; border: none; color: {pal['fg']}; }}"
    )


def segment_bar_qss(pal, name="IconPickerSegments"):
    """iOS-style segmented switch: one inset track, the active segment lifted
    onto the modal's own surface colour."""
    return (
        "/* onigiri-rounded-button-fix */\n"
        f"QFrame#{name} {{ background: {pal['inset']}; border: none;"
        f" border-radius: {SEGMENT_RADIUS}px; }}"
        f" QFrame#{name} QPushButton {{ background: transparent; border: none;"
        f" border-radius: {SEGMENT_BTN_RADIUS}px; color: {pal['muted']};"
        " font-size: 13px; font-weight: 600; padding: 0 14px; }"
        f" QFrame#{name} QPushButton:hover {{ color: {pal['fg']}; }}"
        f" QFrame#{name} QPushButton:checked {{ background: {pal['surface_solid']};"
        f" color: {pal['fg']}; }}"
    )


def grid_panel_qss(pal, name="IconPickerGridPanel"):
    return (
        f"QFrame#{name} {{ background: {pal['inset']}; border: none;"
        f" border-radius: {GRID_PANEL_RADIUS}px; }}"
    )


def icon_cell_qss(pal, selected, accent=None):
    """Grid tile. Same fill as the search field above the grid (`search_qss`'s
    `pal['inset']`) — one flat colour for every "sunken" control in the
    picker, not a separate panel tone just for tiles."""
    accent = accent or pal["accent"]
    if selected:
        return (
            f"QFrame {{ background: {_rgba(accent, 0.16)}; border: 1px solid {accent};"
            f" border-radius: {ICON_CELL_RADIUS}px; }}"
        )
    return (
        f"QFrame {{ background: {pal['inset']}; border: 1px solid transparent;"
        f" border-radius: {ICON_CELL_RADIUS}px; }}"
        f" QFrame:hover {{ background: {pal['inset_hover']}; }}"
    )


def color_row_qss(pal, name="IconPickerColorRow"):
    """One colour choice as a full-width pill: swatch, then its label."""
    return (
        "/* onigiri-rounded-button-fix */\n"
        f"QPushButton#{name} {{ background: {pal['inset']}; color: {pal['fg']};"
        f" border: 1px solid transparent; border-radius: {CONTROL_RADIUS}px;"
        " text-align: left; padding: 0 12px; font-size: 13px; font-weight: 500; }"
        f" QPushButton#{name}:hover {{ background: {pal['inset_hover']}; }}"
    )


def color_panel_qss(pal, name="IconPickerColorPanel"):
    """The colours that paint the icon sit under the grid, separated by a
    hairline — not on a panel of their own, which read as a second card."""
    return (
        f"QFrame#{name} {{ background: transparent; border: none;"
        f" border-top: 1px solid {pal['hairline']}; }}"
        f" QLabel {{ background: transparent; border: none; color: {pal['fg']}; }}"
    )


def color_swatch_qss(pal, color):
    return (
        f"QLabel {{ background-color: {color}; border: 1px solid {pal['hairline']};"
        " border-radius: 7px; }"
    )
