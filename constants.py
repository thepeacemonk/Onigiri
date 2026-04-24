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