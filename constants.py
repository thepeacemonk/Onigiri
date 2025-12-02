# --- Onigiri ---
# This file contains large, static data sets used by the settings dialog
# to keep the main settings.py file clean and focused on logic.

# --- Dictionary for user-friendly color names and tooltips ---
COLOR_LABELS = {
    "--accent-color": {"label": "Accent", "tooltip": "The main color for buttons, selections, and highlights."},
    "--bg": {"label": "Background", "tooltip": "The main background color of the interface."},
    "--fg": {"label": "Text", "tooltip": "The primary color for text."},
    "--canvas-inset": {"label": "Boxes", "tooltip": "Background color for the boxed areas."},
    
    "--icon-color": {"label": "Icon", "tooltip": "The color of most icons in the interface."},
    "--icon-color-filtered": {"label": "Filtered Deck Icon", "tooltip": "The color of the icon for filtered decks in the deck list."},
    "--fg-subtle": {"label": "Titles", "tooltip": "A less prominent text color, used for secondary information."},
    "--border": {"label": "Border", "tooltip": "Color for borders and separators between elements."},
    "--highlight-bg": {"label": "Hover Highlight", "tooltip": "Background color when hovering over items like decks in the list."},
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
    
    # Shadow and overlay colors
    "--shadow-sm": {"label": "Small Shadow", "tooltip": "Small shadow for subtle depth effects."},
    "--shadow-md": {"label": "Medium Shadow", "tooltip": "Medium shadow for cards and elevated elements."},
    "--shadow-lg": {"label": "Large Shadow", "tooltip": "Large shadow for modals and overlays."},
    "--overlay-dark": {"label": "Dark Overlay", "tooltip": "Semi-transparent dark overlay for modals and image backgrounds."},
    "--overlay-light": {"label": "Light Overlay", "tooltip": "Semi-transparent light overlay for profile bars with images."},
    
    # Profile page specific colors
    "--profile-page-bg": {"label": "Profile Page Background", "tooltip": "Background color for the profile page."},
    "--profile-card-bg": {"label": "Profile Card Background", "tooltip": "Background color for profile cards."},
    "--profile-pill-placeholder-bg": {"label": "Profile Pill Placeholder BG", "tooltip": "Background for profile picture placeholder in pill."},
    "--profile-export-btn-bg": {"label": "Profile Export Button BG", "tooltip": "Background color for the export button on profile page."},
    "--profile-export-btn-fg": {"label": "Profile Export Button Text", "tooltip": "Text color for the export button on profile page."},
    "--profile-export-btn-border": {"label": "Profile Export Button Border", "tooltip": "Border color for the export button on profile page."},
    "--overlay-close-btn-bg": {"label": "Overlay Close Button BG", "tooltip": "Background color for close button in overlays."},
    "--overlay-close-btn-fg": {"label": "Overlay Close Button Text", "tooltip": "Text color for close button in overlays."},
    
    # Deck list specific colors
    "--deck-hover-bg": {"label": "Deck Hover Background", "tooltip": "Background color when hovering over deck items."},
    "--deck-dragging-bg": {"label": "Deck Dragging Background", "tooltip": "Background color for decks being dragged."},
    "--deck-edit-mode-bg": {"label": "Deck Edit Mode Background", "tooltip": "Background tint when in deck edit mode."},
    
    # Text shadow colors
    "--text-shadow-light": {"label": "Light Text Shadow", "tooltip": "Shadow for text on dark backgrounds."},
    "--profile-pic-border": {"label": "Profile Picture Border", "tooltip": "Border color for profile pictures with image backgrounds."},
}

# --- Default Icons 
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
ALL_THEME_KEYS = [
    # General & Accent
    "--accent-color",
    "--bg",
    "--fg",
    "--fg-subtle",
    "--border",
    "--canvas-inset",

    # Deck List & Sidebar
    "--deck-list-bg",
    "--highlight-bg",
    "--highlight-fg",
    "--icon-color",
    "--icon-color-filtered",

    # Main Menu (Heatmap & Stats)
    "--heatmap-color",
    "--heatmap-color-zero",
    "--star-color",
    "--empty-star-color",

    # Deck Overview
    "--button-primary-bg",
    "--button-primary-gradient-start",
    "--button-primary-gradient-end",
    "--new-count-bubble-bg",
    "--new-count-bubble-fg",
    "--learn-count-bubble-bg",
    "--learn-count-bubble-fg",
    "--review-count-bubble-bg",
    "--review-count-bubble-fg",
    
    # Shadow and overlay colors
    "--shadow-sm",
    "--shadow-md",
    "--shadow-lg",
    "--overlay-dark",
    "--overlay-light",
    
    # Profile page specific colors
    "--profile-page-bg",
    "--profile-card-bg",
    "--profile-pill-placeholder-bg",
    "--profile-export-btn-bg",
    "--profile-export-btn-fg",
    "--profile-export-btn-border",
    "--overlay-close-btn-bg",
    "--overlay-close-btn-fg",
    
    # Deck list specific colors
    "--deck-hover-bg",
    "--deck-dragging-bg",
    "--deck-edit-mode-bg",
    
    # Text shadow colors
    "--text-shadow-light",
    "--profile-pic-border",
]