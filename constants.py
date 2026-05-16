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

# --- Default Icons (loaded from system_files/system_icons/)
# All icons are now SVG files, not hardcoded data URIs
ICON_DEFAULTS = {
    "options": "options.svg",
    "book": "deck.svg",
    "folder": "folder.svg",
    "add": "add.svg",
    "browse": "browse.svg",
    "stats": "stats.svg",
    "sync": "sync.svg",
    "settings": "settings.svg",
    "more": "more.svg",
    "get_shared": "get_shared.svg",
    "create_deck": "create_deck.svg",
    "import_file": "import_file.svg",
    "ellipsis": "ellipsis.svg",
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

REVIEWER_THEME_KEYS = [
    "onigiri_reviewer_btn_custom_enabled",
    "onigiri_reviewer_btn_interval_color_light",
    "onigiri_reviewer_btn_interval_color_dark",
    "onigiri_reviewer_btn_border_color_light",
    "onigiri_reviewer_btn_border_color_dark",
    "onigiri_reviewer_btn_again_bg_light",
    "onigiri_reviewer_btn_again_text_light",
    "onigiri_reviewer_btn_again_bg_dark",
    "onigiri_reviewer_btn_again_text_dark",
    "onigiri_reviewer_btn_hard_bg_light",
    "onigiri_reviewer_btn_hard_text_light",
    "onigiri_reviewer_btn_hard_bg_dark",
    "onigiri_reviewer_btn_hard_text_dark",
    "onigiri_reviewer_btn_good_bg_light",
    "onigiri_reviewer_btn_good_text_light",
    "onigiri_reviewer_btn_good_bg_dark",
    "onigiri_reviewer_btn_good_text_dark",
    "onigiri_reviewer_btn_easy_bg_light",
    "onigiri_reviewer_btn_easy_text_light",
    "onigiri_reviewer_btn_easy_bg_dark",
    "onigiri_reviewer_btn_easy_text_dark",
    "onigiri_reviewer_other_btn_bg_light",
    "onigiri_reviewer_other_btn_text_light",
    "onigiri_reviewer_other_btn_bg_dark",
    "onigiri_reviewer_other_btn_text_dark",
    "onigiri_reviewer_other_btn_hover_bg_light",
    "onigiri_reviewer_other_btn_hover_text_light",
    "onigiri_reviewer_other_btn_hover_bg_dark",
    "onigiri_reviewer_other_btn_hover_text_dark",
    "onigiri_reviewer_stattxt_color_light",
    "onigiri_reviewer_stattxt_color_dark",
]