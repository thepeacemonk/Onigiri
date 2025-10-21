# Onigiri's dedicated Deck Browser Rendering Engine

import json
from aqt import mw
from . import patcher
from aqt.deckbrowser import DeckBrowser, RenderDeckNodeContext
from . import config, heatmap, deck_tree_updater
from . import config, heatmap
from .templates import custom_body_template

# --- Helper functions (copied from patcher.py for self-containment) ---

def _get_profile_pic_html(user_name: str, addon_package: str, css_class: str = "profile-pic") -> str:    
    profile_pic_filename = mw.col.conf.get("modern_menu_profile_picture", "")
    if profile_pic_filename:
        pic_url = f"/_addons/{addon_package}/user_files/profile/{profile_pic_filename}"
        return f'<img src="{pic_url}" class="{css_class}">'
    else:
        initial = user_name[0].upper() if user_name else "U"
        return f'<div class="{css_class}-placeholder"><span>{initial}</span></div>'

def _get_onigiri_stat_card_html(label: str, value: str, widget_id: str) -> str:
    return f"""<div class="stat-card {widget_id}-card"><h3>{label}</h3><p>{value}</p></div>"""

def _get_onigiri_retention_html() -> str:
    total_reviews, correct_reviews = mw.col.db.first(
        "select count(*), sum(case when ease > 1 then 1 else 0 end) from revlog where type = 1 and id > ?",
        (mw.col.sched.dayCutoff - 86400) * 1000
    ) or (0, 0)
    total_reviews = total_reviews or 0
    correct_reviews = correct_reviews or 0
    retention_percentage = (correct_reviews / total_reviews * 100) if total_reviews > 0 else 0

    if retention_percentage >= 90: stars = 5
    elif retention_percentage >= 70: stars = 4
    elif retention_percentage >= 50: stars = 3
    elif retention_percentage >= 30: stars = 2
    elif total_reviews > 0: stars = 1
    else: stars = 0
    
    star_html = "".join([f"<i class='star{' empty' if i >= stars else ''}'></i>" for i in range(5)])

    return f"""
    <div class="stat-card retention-card">
        <h3>Retention</h3>
        <p>{retention_percentage:.0f}%</p>
        <div class="star-rating">{star_html}</div>
    </div>
    """

def _get_onigiri_heatmap_html() -> str:
    skeleton_cells = "".join(["<div class='skeleton-cell'></div>" for _ in range(371)])
    return f"""
    <div id='onigiri-heatmap-container'>
        <div class="heatmap-header-skeleton"><div class="header-left-skeleton"><div class="skeleton-title"></div><div class="skeleton-nav"></div></div><div class="header-right-skeleton"><div class="skeleton-streak"></div><div class="skeleton-filters"></div></div></div>
        <div class="heatmap-grid-skeleton">{skeleton_cells}</div>
    </div>"""

# --- The Main Rendering Function ---

def render_onigiri_deck_browser(self: DeckBrowser, reuse: bool = False) -> None:
    """
    A complete replacement for Anki's DeckBrowser._renderPage.
    It builds the entire modern UI, including Onigiri and external widgets,
    into a stable CSS grid.
    """
    # Ensure hooks from other add-ons are captured just-in-time
    patcher.take_control_of_deck_browser_hook()
    conf = config.get_config()
    addon_package = mw.addonManager.addonFromModule(__name__)
    
    # --- Part 1: Build Onigiri Widgets Grid ---
    onigiri_layout = conf.get("onigiriWidgetLayout", {}).get("grid", {})
    onigiri_grid_html = ""
    cards_today, time_today_seconds = self.mw.col.db.first("select count(), sum(time)/1000 from revlog where id > ?", (self.mw.col.sched.dayCutoff - 86400) * 1000) or (0, 0)
    time_today_seconds = time_today_seconds or 0
    cards_today = cards_today or 0
    time_today_minutes = time_today_seconds / 60
    seconds_per_card = time_today_seconds / cards_today if cards_today > 0 else 0

    widget_generators = {
        "studied": lambda: _get_onigiri_stat_card_html("Studied", f"{cards_today} cards", "studied"),
        "time": lambda: _get_onigiri_stat_card_html("Time", f"{time_today_minutes:.1f} min", "time"),
        "pace": lambda: _get_onigiri_stat_card_html("Pace", f"{seconds_per_card:.1f} s/card", "pace"),
        "retention": _get_onigiri_retention_html,
        "heatmap": _get_onigiri_heatmap_html,
    }
    
    for widget_id, widget_config in onigiri_layout.items():
        if widget_id in widget_generators:
            pos = widget_config.get("pos", 0)
            row_span = widget_config.get("row", 1)
            col_span = widget_config.get("col", 1)
            row = pos // 4 + 1
            col = pos % 4 + 1
            style = f"grid-area: {row} / {col} / span {row_span} / span {col_span};"
            onigiri_grid_html += f'<div class="onigiri-widget-container" style="{style}">{widget_generators[widget_id]()}</div>'

    # --- Part 2: Build External Add-on Widgets Grid ---
    external_hooks = patcher._get_external_hooks()
    external_layout = conf.get("externalWidgetLayout", {})
    grid_config = external_layout.get("grid", {})
    external_widgets_html = ""
    
    external_widgets_data = {}
    for hook in external_hooks:
        hook_id = patcher._get_hook_name(hook)
        class TempContent: stats = ""
        temp_content = TempContent()
        try:
            hook(self, temp_content)
            external_widgets_data[hook_id] = temp_content.stats
        except Exception as e:
            external_widgets_data[hook_id] = f"<div style='color: red;'>Error in {hook_id}:<br>{e}</div>"

    for hook_id, widget_config in grid_config.items():
        if hook_html := external_widgets_data.get(hook_id):
            pos = widget_config.get("grid_position", 0)
            row = pos // 4 + 1
            col = pos % 4 + 1
            row_span = widget_config.get("row_span", 1)
            col_span = widget_config.get("column_span", 1)
            style = f"grid-area: {row} / {col} / span {row_span} / span {col_span};"
            external_widgets_html += f'<div class="external-widget-container" style="{style}">{hook_html}</div>'

    # --- Part 3: Assemble the Final Stats Block ---
    stats_title = mw.col.conf.get("modern_menu_statsTitle", config.DEFAULTS["statsTitle"])
    title_html = f'<h1 class="onigiri-widget-title">{stats_title}</h1>' if stats_title else ""

    stats_block_html = f"""
    <style>
        .onigiri-grid, .external-grid {{
            display: grid;
            gap: 15px;
            align-items: start;
            grid-template-columns: repeat(4, 1fr);
        }}
        .onigiri-grid {{ margin-bottom: 20px; }}
        .onigiri-widget-container, .external-widget-container {{
            overflow: hidden;
            min-height: 50px;
        }}
    </style>
    {title_html}
    <div class="onigiri-grid">{onigiri_grid_html}</div>
    <div class="external-grid">{external_widgets_html}</div>
    """

    # --- Part 4: Manually Build the Deck Tree HTML ---
    tree_html = deck_tree_updater._render_deck_tree_html_only(self)
    
    # --- Part 5: Populate the Main Template ---
    is_collapsed = mw.col.conf.get("onigiri_sidebar_collapsed", False)
    sidebar_initial_class = "sidebar-collapsed" if is_collapsed else ""
    user_name = conf.get("userName", "USER")
    
    profile_bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "accent")
    profile_bg_image = mw.col.conf.get("modern_menu_profile_bg_image", "")
    bg_style_str = ""
    bg_class_str = ""

    if profile_bg_mode == "image" and profile_bg_image:
        bg_image_url = f"/_addons/{addon_package}/user_files/profile_bg/{profile_bg_image}"
        bg_style_str = f"background-image: url('{bg_image_url}'); background-size: cover; background-position: center;"
        bg_class_str = "with-image-bg"
    elif profile_bg_mode == "custom":
        bg_style_str = "background-color: var(--profile-bg-custom-color);"
    else: # accent
        bg_style_str = "background-color: var(--accent-color);"
    
    profile_pic_html_expanded = _get_profile_pic_html(user_name, addon_package)
    profile_bar_html = f"""<div class="profile-bar {bg_class_str}" style="{bg_style_str}" onclick="pycmd('showUserProfile')">{profile_pic_html_expanded}<span class="profile-name">{user_name}</span></div>"""
    profile_pic_html_collapsed = _get_profile_pic_html(user_name, addon_package, "collapsed-profile-pic")
    
    welcome_message = f"WELCOME {user_name.upper()}" if not conf.get("hideWelcomeMessage", False) else ""
    saved_width = mw.col.conf.get("modern_menu_sidebar_width", 300)
    sidebar_style = f"width: {saved_width}px;"
    container_extra_class = ""

    # --- START MODIFICATION ---
    # Use a chain of .replace() calls to avoid KeyError with CSS/JS syntax
    final_body = custom_body_template \
        .replace("{tree}", tree_html) \
        .replace("{stats}", stats_block_html) \
        .replace("{container_extra_class}", container_extra_class) \
        .replace("{sidebar_initial_class}", sidebar_initial_class) \
        .replace("{sidebar_style}", sidebar_style) \
        .replace("{welcome_message}", welcome_message) \
        .replace("{profile_bar}", profile_bar_html) \
        .replace("{profile_pic_html_collapsed}", profile_pic_html_collapsed)
    # --- END MODIFICATION ---
    
    # --- Part 6: Render the Final Page ---
    self.web.stdHtml(
        body=final_body,
        css=["css/deckbrowser.css"],
        js=["js/vendor/jquery.min.js", "js/vendor/jquery-ui.min.js", "js/deckbrowser.js"],
        context=self,
    )

    from aqt import gui_hooks
    gui_hooks.deck_browser_did_render(self)