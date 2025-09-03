# --- Onigiri ---
# This file contains large, static data sets used by the settings dialog
# to keep the main settings.py file clean and focused on logic.

# --- Dictionary for user-friendly color names and tooltips ---
COLOR_LABELS = {
    "--accent-color": {"label": "Accent", "tooltip": "The main color for buttons, selections, and highlights."},
    "--bg": {"label": "Background", "tooltip": "The main background color of the interface."},
    "--fg": {"label": "Text", "tooltip": "The primary color for text."},
    "--icon-color": {"label": "Icon", "tooltip": "The color of most icons in the interface."},
    "--fg-subtle": {"label": "Subtle Text", "tooltip": "A less prominent text color, used for secondary information."},
    "--border": {"label": "Border", "tooltip": "Color for borders and separators between elements."},
    "--highlight-bg": {"label": "Hover Highlight", "tooltip": "Background color when hovering over items like decks in the list."},
    "--highlight-background": {"label": "Active Highlight", "tooltip": "Background for actively selected or highlighted elements."},
    "--canvas-inset": {"label": "Deck List Background", "tooltip": "Background color for the main deck list area."},
    "--button-primary-bg": {"label": "Study Button", "tooltip": "The main background color of the 'Study Now' button on the deck overview screen. Also sets the focus border color."},
    "--button-primary-gradient-start": {"label": "Study Button Hover Gradient (Start)", "tooltip": "The starting color of the gradient when hovering over the 'Study Now' button."},
    "--button-primary-gradient-end": {"label": "Study Button Hover Gradient (End)", "tooltip": "The ending color of the gradient when hovering over the 'Study Now' button."},
    "--new-count-bubble-bg": {"label": "New Count Bubble BG", "tooltip": "Background color for the 'New' card count bubble in the deck overview."},
    "--new-count-bubble-fg": {"label": "New Count Bubble Text", "tooltip": "Text color for the 'New' card count bubble in the deck overview."},
    "--learn-count-bubble-bg": {"label": "Learn Count Bubble BG", "tooltip": "Background color for the 'Learning' card count bubble in the deck overview."},
    "--learn-count-bubble-fg": {"label": "Learn Count Bubble Text", "tooltip": "Text color for the 'Learning' card count bubble in the deck overview."},
    "--review-count-bubble-bg": {"label": "Review Count Bubble BG", "tooltip": "Background color for the 'To Review' card count bubble in the deck overview."},
    "--review-count-bubble-fg": {"label": "Review Count Bubble Text", "tooltip": "Text color for the 'To Review' card count bubble in the deck overview."},
    "--heatmap-color": {"label": "Heatmap Shape Color", "tooltip": "The color of the heatmap shape for days with one or more reviews."},
    "--heatmap-color-zero": {"label": "Heatmap Shape Color (0 reviews)", "tooltip": "The color of the heatmap shape for days with zero reviews."},
}

# --- Catppuccin Theme Palettes ---
CATPPUCCIN_THEMES = {
    "meta": {
        "logo_file": "catpuccin_logo.png",
        "url": "https://catppuccin.com/palette"
    },
    "latte": {
        "mode": "light",
        "name": "Latte",
        "colors": {
            "--accent-color": "#1e66f5", "--bg": "#eff1f5", "--fg": "#4c4f69",
            "--icon-color": "#7c7f93", "--fg-subtle": "#5c5f77", "--border": "#9ca0b0",
            "--highlight-bg": "#ccd0da", "--highlight-background": "#bcc0cc",
            "--canvas-inset": "#e6e9ef", "--button-primary-bg": "#1e66f5",
            "--button-primary-gradient-start": "#04a5e5", "--button-primary-gradient-end": "#209fb5",
            "--new-count-bubble-bg": "#a3c5e8", "--new-count-bubble-fg": "#315375",
            "--learn-count-bubble-bg": "#e8a3a3", "--learn-count-bubble-fg": "#7a2f2f",
            "--review-count-bubble-bg": "#a3e8b8", "--review-count-bubble-fg": "#195e2e",
        },
        "preview": ["#eff1f5", "#4c4f69", "#1e66f5", "#d20f39", "#40a02b", "#fe640b", "#df8e1d", "#8839ef"],
        "backgrounds": {"light": "#eff1f5", "dark": "#374258"}
    },
    "frappe": {
        "mode": "dark",
        "name": "Frappé",
        "colors": {
            "--accent-color": "#ca9ee6", "--bg": "#303446", "--fg": "#c6d0f5",
            "--icon-color": "#949cbb", "--fg-subtle": "#b5bfe2", "--border": "#737994",
            "--highlight-bg": "#414559", "--highlight-background": "#51576d",
            "--canvas-inset": "#292c3c", "--button-primary-bg": "#8caaee",
            "--button-primary-gradient-start": "#99d1db", "--button-primary-gradient-end": "#85c1dc",
            "--new-count-bubble-bg": "#68a0d9", "--new-count-bubble-fg": "#ffffff",
            "--learn-count-bubble-bg": "#d96868", "--learn-count-bubble-fg": "#ffffff",
            "--review-count-bubble-bg": "#68d98a", "--review-count-bubble-fg": "#ffffff",
        },
        "preview": ["#303446", "#c6d0f5", "#8caaee", "#e78284", "#a6d189", "#ef9f76", "#e5c890", "#ca9ee6"],
        "backgrounds": {"light": "#DBDDE6", "dark": "#303446"}
    },
    "macchiato": {
        "mode": "dark",
        "name": "Macchiato",
        "colors": {
            "--accent-color": "#f5bde6", "--bg": "#24273a", "--fg": "#cad3f5",
            "--icon-color": "#939ab7", "--fg-subtle": "#b8c0e0", "--border": "#6e738d",
            "--highlight-bg": "#363a4f", "--highlight-background": "#494d64",
            "--canvas-inset": "#1e2030", "--button-primary-bg": "#8aadf4",
            "--button-primary-gradient-start": "#91d7e3", "--button-primary-gradient-end": "#7dc4e4",
            "--new-count-bubble-bg": "#68a0d9", "--new-count-bubble-fg": "#ffffff",
            "--learn-count-bubble-bg": "#d96868", "--learn-count-bubble-fg": "#ffffff",
            "--review-count-bubble-bg": "#68d98a", "--review-count-bubble-fg": "#ffffff",
        },
        "preview": ["#24273a", "#cad3f5", "#8aadf4", "#ed8796", "#a6da95", "#f5a97f", "#eed49f", "#c6a0f6"],
        "backgrounds": {"light": "#E6E7EF", "dark": "#24273a"}
    },
    "mocha": {
        "mode": "dark",
        "name": "Mocha",
        "colors": {
            "--accent-color": "#b4befe", "--bg": "#1e1e2e", "--fg": "#cdd6f4",
            "--icon-color": "#9399b2", "--fg-subtle": "#bac2de", "--border": "#6c7086",
            "--highlight-bg": "#313244", "--highlight-background": "#45475a",
            "--canvas-inset": "#181825", "--button-primary-bg": "#89b4fa",
            "--button-primary-gradient-start": "#89dceb", "--button-primary-gradient-end": "#74c7ec",
            "--new-count-bubble-bg": "#68a0d9", "--new-count-bubble-fg": "#ffffff",
            "--learn-count-bubble-bg": "#d96868", "--learn-count-bubble-fg": "#ffffff",
            "--review-count-bubble-bg": "#68d98a", "--review-count-bubble-fg": "#ffffff",
        },
        "preview": ["#1e1e2e", "#cdd6f4", "#89b4fa", "#f38ba8", "#a6e3a1", "#fab387", "#f9e2af", "#cba6f7"],
        "backgrounds": {"light": "#CECEDF", "dark": "#1e1e2e"}
    }
}

# --- Community Theme Palettes ---
COMMUNITY_THEMES = {
    "rose_pine": {
        "mode": "dark",
        "name": "Rosé Pine",
        "logo_file": "rose_pine.png",
        "url": "https://rosepinetheme.com/palette/",
        "colors": {
            "--accent-color": "#c4a7e7", "--bg": "#191724", "--fg": "#e0def4",
            "--icon-color": "#908caa", "--fg-subtle": "#6e6a86", "--border": "#403d52",
            "--highlight-bg": "#26233a", "--highlight-background": "#403d52",
            "--canvas-inset": "#1f1d2e", "--button-primary-bg": "#c4a7e7",
            "--button-primary-gradient-start": "#eb6f92", "--button-primary-gradient-end": "#9ccfd8",
            "--new-count-bubble-bg": "#68a0d9", "--new-count-bubble-fg": "#ffffff",
            "--learn-count-bubble-bg": "#d96868", "--learn-count-bubble-fg": "#ffffff",
            "--review-count-bubble-bg": "#68d98a", "--review-count-bubble-fg": "#ffffff",
        },
        "preview": ["#191724", "#e0def4", "#c4a7e7", "#eb6f92", "#9ccfd8", "#f6c177", "#31748f", "#ebbcba"],
        "backgrounds": {"light": "#faf4ed", "dark": "#191724"}
    },
    "nord": {
        "mode": "dark",
        "name": "Nord",
        "logo_file": "nord.png",
        "url": "https://www.nordtheme.com/",
        "colors": {
            "--accent-color": "#88C0D0", "--bg": "#2E3440", "--fg": "#ECEFF4",
            "--icon-color": "#D8DEE9", "--fg-subtle": "#4C566A", "--border": "#434C5E",
            "--highlight-bg": "#3B4252", "--highlight-background": "#434C5E",
            "--canvas-inset": "#2E3440", "--button-primary-bg": "#88C0D0",
            "--button-primary-gradient-start": "#81A1C1", "--button-primary-gradient-end": "#5E81AC",
            "--new-count-bubble-bg": "#68a0d9", "--new-count-bubble-fg": "#ffffff",
            "--learn-count-bubble-bg": "#d96868", "--learn-count-bubble-fg": "#ffffff",
            "--review-count-bubble-bg": "#68d98a", "--review-count-bubble-fg": "#ffffff",
        },
        "preview": ["#2E3440", "#ECEFF4", "#88C0D0", "#BF616A", "#A3BE8C", "#EBCB8B", "#D08770", "#B48EAD"],
        "backgrounds": {"light": "#ECEFF4", "dark": "#2E3440"}
    },
    "dracula": {
        "mode": "dark",
        "name": "Dracula",
        "logo_file": "dracula.png",
        "url": "https://draculatheme.com/",
        "colors": {
            "--accent-color": "#ff79c6", "--bg": "#282a36", "--fg": "#f8f8f2",
            "--icon-color": "#f1fa8c", "--fg-subtle": "#6272a4", "--border": "#44475a",
            "--highlight-bg": "#44475a", "--highlight-background": "#6272a4",
            "--canvas-inset": "#21222C", "--button-primary-bg": "#ff79c6",
            "--button-primary-gradient-start": "#bd93f9", "--button-primary-gradient-end": "#8be9fd",
            "--new-count-bubble-bg": "#68a0d9", "--new-count-bubble-fg": "#ffffff",
            "--learn-count-bubble-bg": "#d96868", "--learn-count-bubble-fg": "#ffffff",
            "--review-count-bubble-bg": "#68d98a", "--review-count-bubble-fg": "#ffffff",
        },
        "preview": ["#282a36", "#f8f8f2", "#ff79c6", "#bd93f9", "#8be9fd", "#50fa7b", "#ffb86c", "#f1fa8c"],
        "backgrounds": {"light": "#F2F2F2", "dark": "#282a36"}
    },
    "solarized": {
        "mode": "dark",
        "name": "Solarized Dark",
        "logo_file": "solarized.png",
        "url": "https://ethanschoonover.com/solarized/",
        "colors": {
            "--accent-color": "#268bd2", "--bg": "#002b36", "--fg": "#839496",
            "--icon-color": "#93a1a1", "--fg-subtle": "#586e75", "--border": "#073642",
            "--highlight-bg": "#073642", "--highlight-background": "#586e75",
            "--canvas-inset": "#002b36", "--button-primary-bg": "#268bd2",
            "--button-primary-gradient-start": "#6c71c4", "--button-primary-gradient-end": "#2aa198",
            "--new-count-bubble-bg": "#68a0d9", "--new-count-bubble-fg": "#ffffff",
            "--learn-count-bubble-bg": "#d96868", "--learn-count-bubble-fg": "#ffffff",
            "--review-count-bubble-bg": "#68d98a", "--review-count-bubble-fg": "#ffffff",
        },
        "preview": ["#002b36", "#839496", "#268bd2", "#b58900", "#cb4b16", "#dc322f", "#d33682", "#6c71c4"],
        "backgrounds": {"light": "#fdf6e3", "dark": "#002b36"}
    }
}


# --- Default Icons (mirrored from patcher.py for UI rendering) ---
ICON_DEFAULTS = {
    "collapse_closed": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cline x1='12' y1='5' x2='12' y2='19'/%3E%3Cline x1='5' y1='12' x2='19' y2='12'/%3E%3C/svg%3E",
    "collapse_open": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E",
    "options": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='currentColor'%3E%3Ccircle cx='12' cy='6' r='2'/%3E%3Ccircle cx='12' cy='12' r='2'/%3E%3Ccircle cx='12' cy='18' r='2'/%3E%3C/svg%3E",
    "book": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z'/%3E%3Cpolyline points='14 2 14 8 20 8'/%3E%3C/svg%3E",
    "folder": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolygon points='12 2 2 7 12 12 22 7 12 2'/%3E%3Cpolyline points='2 17 12 22 22 17'/%3E%3Cpolyline points='2 12 12 17 22 12'/%3E%3C/svg%3E",
    "add": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='1 1 22 22' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cline x1='12' y1='5' x2='12' y2='19'/%3E%3Cline x1='5' y1='12' x2='19' y2='12'/%3E%3C/svg%3E",
    "browse": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='1 1 22 22' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cline x1='8' y1='6' x2='21' y2='6'/%3E%3Cline x1='8' y1='12' x2='21' y2='12'/%3E%3Cline x1='8' y1='18' x2='21' y2='18'/%3E%3Cline x1='3' y1='6' x2='3.01' y2='6'/%3E%3Cline x1='3' y1='12' x2='3.01' y2='12'/%3E%3Cline x1='3' y1='18' x2='3.01' y2='18'/%3E%3C/svg%3E",
    "stats": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='1 1 22 22' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 20V10M18 20V4M6 20V16'/%3E%3C/svg%3E",
    "sync": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='1 1 22 22' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='23 4 23 10 17 10'/%3E%3Cpolyline points='1 20 1 14 7 14'/%3E%3Cpath d='M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15'/%3E%3C/svg%3E",
    "settings": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M19.14 12.94c.04-.3.06-.61.06-.94s-.02-.64-.07-.94l2.03-1.58a.5.5 0 0 0 .12-.61l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96c-.51-.38-1.06-.7-1.66-.94l-.37-2.65A.5.5 0 0 0 14.1 2h-4.2a.5.5 0 0 0-.49.42l-.37 2.65c-.6.24-1.15.56-1.66.94l-2.39-.96a.5.5 0 0 0-.6.22l-1.92 3.32a.5.5 0 0 0 .12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58a.5.5 0 0 0-.12.61l1.92 3.32a.5.5 0 0 0 .6.22l2.39-.96c.51.38 1.06.7 1.66.94l.37 2.65A.5.5 0 0 0 9.9 22h4.2a.5.5 0 0 0 .49-.42l.37-2.65c.6-.24 1.15-.56 1.66-.94l2.39.96a.5.5 0 0 0 .6-.22l1.92-3.32a.5.5 0 0 0-.12-.61l-2.03-1.58z'/%3E%3Ccircle cx='12' cy='12' r='3'/%3E%3C/svg%3E",
    "more": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='1 1 22 22' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='1'/%3E%3Ccircle cx='19' cy='12' r='1'/%3E%3Ccircle cx='5' cy='12' r='1'/%3E%3C/svg%3E",
    "get_shared": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='1 1 22 22' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M8 17l4 4 4-4'/%3E%3Cpath d='M12 12v9'/%3E%3Cpath d='M20.88 18.09A5 5 0 0018 9h-1.26A8 8 0 103 16.29'/%3E%3C/svg%3E",
    "create_deck": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='1 1 22 22' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z'/%3E%3Cline x1='12' y1='11' x2='12' y2='17'/%3E%3Cline x1='9' y1='14' x2='15' y2='14'/%3E%3C/svg%3E",
    "import_file": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='1 1 22 22' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4'/%3E%3Cpolyline points='7 10 12 15 17 10'/%3E%3Cline x1='12' y1='15' x2='12' y2='3'/%3E%3C/svg%3E",
}

DEFAULT_ICON_SIZES = {"deck_folder": 20, "action_button": 14, "collapse": 12, "options_gear": 16}