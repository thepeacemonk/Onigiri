# --- Onigiri ---
# This file contains large, static data sets used by the settings dialog
# to keep the main settings.py file clean and focused on logic.

# --- Dictionary for user-friendly color names and tooltips ---
COLOR_LABELS = {
    "--accent-color": {"label": "accent_label", "tooltip": "accent_tooltip"},
    "--bg": {"label": "bg_label", "tooltip": "bg_tooltip"},
    "--fg": {"label": "fg_label", "tooltip": "fg_tooltip"},
    "--canvas-inset": {"label": "canvas_inset_label", "tooltip": "canvas_inset_tooltip"},
    
    "--icon-color": {"label": "icon_label", "tooltip": "icon_tooltip"},
    "--icon-color-filtered": {"label": "filtered_icon_label", "tooltip": "filtered_icon_tooltip"},
    "--fg-subtle": {"label": "fg_subtle_label", "tooltip": "fg_subtle_tooltip"},
    "--border": {"label": "border_label", "tooltip": "border_tooltip"},
    "--highlight-bg": {"label": "hover_highlight_label", "tooltip": "hover_highlight_tooltip"},
    "--button-primary-bg": {"label": "study_button_label", "tooltip": "study_button_tooltip"},
    "--button-primary-gradient-start": {"label": "button_primary_gradient_start_label", "tooltip": "button_primary_gradient_start_tooltip"},
    "--button-primary-gradient-end": {"label": "button_primary_gradient_end_label", "tooltip": "button_primary_gradient_end_tooltip"},
    "--new-count-bubble-bg": {"label": "new_count_label", "tooltip": "new_count_tooltip"},
    "--new-count-bubble-fg": {"label": "new_count_fg_label", "tooltip": "new_count_fg_tooltip"},
    "--learn-count-bubble-bg": {"label": "learn_count_label", "tooltip": "learn_count_tooltip"},
    "--learn-count-bubble-fg": {"label": "learn_count_fg_label", "tooltip": "learn_count_fg_tooltip"},
    "--review-count-bubble-bg": {"label": "review_count_label", "tooltip": "review_count_tooltip"},
    "--review-count-bubble-fg": {"label": "review_count_fg_label", "tooltip": "review_count_fg_tooltip"},
    "--heatmap-color": {"label": "heatmap_shape_label", "tooltip": "heatmap_shape_tooltip"},
    "--heatmap-color-zero": {"label": "heatmap_shape_zero_label", "tooltip": "heatmap_shape_zero_tooltip"},
    "--star-color": {"label": "star_color_label", "tooltip": "star_color_tooltip"},
    "--empty-star-color": {"label": "empty_star_color_label", "tooltip": "empty_star_color_tooltip"},
    
    # Shadow and overlay colors
    "--shadow-sm": {"label": "shadow_sm_label", "tooltip": "shadow_sm_tooltip"},
    "--shadow-md": {"label": "shadow_md_label", "tooltip": "shadow_md_tooltip"},
    "--shadow-lg": {"label": "shadow_lg_label", "tooltip": "shadow_lg_tooltip"},
    "--overlay-dark": {"label": "overlay_dark_label", "tooltip": "overlay_dark_tooltip"},
    "--overlay-light": {"label": "overlay_light_label", "tooltip": "overlay_light_tooltip"},
    
    # Profile page specific colors
    "--profile-page-bg": {"label": "profile_page_bg_label", "tooltip": "profile_page_bg_tooltip"},
    "--profile-card-bg": {"label": "profile_card_bg_label", "tooltip": "profile_card_bg_tooltip"},
    "--profile-pill-placeholder-bg": {"label": "profile_pill_placeholder_bg_label", "tooltip": "profile_pill_placeholder_bg_tooltip"},
    "--profile-export-btn-bg": {"label": "profile_export_btn_bg_label", "tooltip": "profile_export_btn_bg_tooltip"},
    "--profile-export-btn-fg": {"label": "profile_export_btn_fg_label", "tooltip": "profile_export_btn_fg_tooltip"},
    "--profile-export-btn-border": {"label": "profile_export_btn_border_label", "tooltip": "profile_export_btn_border_tooltip"},
    "--overlay-close-btn-bg": {"label": "overlay_close_btn_bg_label", "tooltip": "overlay_close_btn_bg_tooltip"},
    "--overlay-close-btn-fg": {"label": "overlay_close_btn_fg_label", "tooltip": "overlay_close_btn_fg_tooltip"},
    
    # Deck list specific colors
    "--deck-hover-bg": {"label": "deck_hover_bg_label", "tooltip": "deck_hover_bg_tooltip"},
    "--deck-dragging-bg": {"label": "deck_dragging_bg_label", "tooltip": "deck_dragging_bg_tooltip"},
    "--deck-edit-mode-bg": {"label": "deck_edit_mode_bg_label", "tooltip": "deck_edit_mode_bg_tooltip"},
    
    # Text shadow colors
    "--text-shadow-light": {"label": "text_shadow_light_label", "tooltip": "text_shadow_light_tooltip"},
    "--profile-pic-border": {"label": "profile_pic_border_label", "tooltip": "profile_pic_border_tooltip"},
}

# --- Default Icons
ICON_DEFAULTS = {
    "collapse_closed": "right.svg",
    "collapse_open": "down.svg",
    "options": "options.svg",
    "book": "deck.svg",
    "folder": "folder.svg",
    "deck": "deck.svg",
    "subdeck": "subdeck.svg",
    "filtered_deck": "filtered-deck.svg",
    "add": "add-card.svg",
    "browse": "browse.svg",
    "stats": "stats.svg",
    "sync": "sync.svg",
    "settings": "settings.svg",
    "more": "more.svg",
    "get_shared": "get_shared.svg",
    "create_deck": "add-deck.svg",
    "import_file": "import_file.svg",
    "gamification": "gamepad.svg",
    "retention_star": "star_filled.svg",
    "star_filled": "star_filled.svg",
    "focus": "focus.svg",
    "edit": "edit.svg",
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
