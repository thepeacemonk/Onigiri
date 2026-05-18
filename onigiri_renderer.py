# Onigiri's dedicated Deck Browser Rendering Engine

import html
import json
import os
from dataclasses import dataclass
from aqt import mw
from . import patcher
from aqt.deckbrowser import DeckBrowser, RenderDeckNodeContext
from anki.decks import DeckId
from . import config, heatmap, deck_tree_updater, sidebar_api
from .gamification import onigimon, restaurant_level
from .templates import custom_body_template
from .translations import tr
import copy
import re

def process_tr_markers(html_str: str) -> str:
    """
    Finds and replaces {tr("key")} markers in HTML strings with actual translations.
    """
    if not html_str:
        return html_str
        
    def replace_match(match):
        key = match.group(1)
        return tr(key)
        
    # Matches {tr("key")} or {tr('key')}
    pattern = r'\{tr\([\'"]([^\'"]+)[\'"]\)\}'
    return re.sub(pattern, replace_match, html_str)

@dataclass
class RenderData:
    """Wrapper for deck tree data that Anki's context menu expects."""
    tree: object  # DeckDueTreeNode from Anki

# --- ADDED: Button HTML definitions ---
BUTTON_HTML = {
    "profile": "{profile_bar}", # This is a placeholder for the dynamic profile bar
    "add": """
        <div class="add-button-dashed action-add" onclick="pycmd('add')">
            <i class="icon"></i>
            <span>{tr("add")}</span>
        </div>
    """,
    "browse": """
        <div class="menu-item action-browse" onclick="pycmd('browse')">
            <i class="icon"></i>
            <span>{tr("browse")}</span>
        </div>
    """,
    "stats": """
        <div class="menu-item action-stats" onclick="pycmd('stats')">
            <i class="icon"></i>
            <span>{tr("stats")}</span>
        </div>
    """,
    "sync": """
        <div class="menu-item action-sync" onclick="pycmd('sync')">
            <i class="icon"></i>
            <span>{tr("sync")}</span>
            <span class="sync-status-indicator"></span>
        </div>
    """,
    "settings": """
        <div class="menu-item action-settings" onclick="pycmd('openOnigiriSettings')">
            <i class="icon"></i>
            <span>{tr("settings")}</span>
        </div>
    """,
    "gamification": """
        <div class="menu-item action-gamification" onclick="pycmd('openGamificationSettings')">
            <i class="icon"></i>
            <span>{tr("onigiri_games")}</span>
        </div>
    """,
    "more": """
        <details class="menu-group">
            <summary class="menu-item action-more">
                <i class="icon"></i>
                <span>{tr("more")}</span>
            </summary>
            <div class="menu-group-items">
                <div class="menu-item action-get-shared" onclick="pycmd('shared')">
                    <i class="icon"></i>
                    <span>{tr("get_shared")}</span>
                </div>
                <div class="menu-item action-create-deck" onclick="pycmd('onigiri_create_deck')">
                    <i class="icon"></i>
                    <span>{tr("create_deck")}</span>
                </div>
                <div class="menu-item action-import-file" onclick="pycmd('import')">
                    <i class="icon"></i>
                    <span>{tr("import_file")}</span>
                </div>
            </div>
        </details>
    """
}

# --- ADDED: Sidebar HTML builder function ---
def _build_sidebar_html(conf: dict) -> str:
    """
    Builds the sidebar HTML content based on the user's saved layout.
    """
    layout_config = conf.get("sidebarButtonLayout", copy.deepcopy(config.DEFAULTS["sidebarButtonLayout"]))
    visible_keys = layout_config.get("visible", [])
    external_entries = sidebar_api.get_sidebar_entries()
    
    # --- MODIFICATION START: Sidebar Actions Mode Logic ---
    action_buttons = {"add", "browse", "stats", "sync", "settings", "gamification", "more"}
    # Default to "list" if not set
    actions_mode = conf.get("sidebarActionsMode", "list")
    
    html_parts = []
    for key in visible_keys:
        # If this key is one of our special action buttons...
        if key in action_buttons:
            # Only render it in the list if mode is "list"
            if actions_mode == "list":
                if key in BUTTON_HTML:
                    html_parts.append(BUTTON_HTML[key])
        # Otherwise render normally (external entries or profile if it was in visible_keys? profile is usually separate)
        elif key in BUTTON_HTML:
             html_parts.append(BUTTON_HTML[key])
        elif key in external_entries:
            # External entries are also subject to the mode if we want them to behave like actions?
            # For now, let's assume external entries follow the same rule if they are actions.
            # But the user asked for "Action Buttons" specifically.
            # Typically external entries are treated as "actions" too. 
            # If the user selects "Collapsed", external sidebar items should probably also disappear/move to toolbar?
            # The current implementation of collapsed mode in injector.js only handles specific IDs.
            # So for now, we'll keep external entries showing in list unless explicitly hidden, 
            # OR we should hide them too if the goal is a clean sidebar.
            # However, SidebarEntry doesn't have a "collapsed" equivalent yet.
            # Let's hide them in collapsed/archived mode for consistency if they are button-like.
            if actions_mode == "list": 
                html_parts.append(sidebar_api.render_sidebar_entry(key))
            
    full_html = "\n".join(part for part in html_parts if part)
    return process_tr_markers(full_html)

def _generate_action_icons_css(conf: dict, addon_package: str) -> str:
    """
    Generates CSS to apply custom or default icons to the sidebar list items.
    """
    css_lines = []
    icon_base = f"/_addons/{addon_package}/system_files/system_icons/"
    user_icon_base = f"/_addons/{addon_package}/user_files/icons/"
    
    # Map action id -> default system icon filename
    default_icons = {
        'add': 'add-card.svg',
        'browse': 'browse.svg',
        'stats': 'stats.svg',
        'sync': 'sync.svg',
        'settings': 'settings.svg',
        'gamification': 'gamepad.svg',
        'more': 'more.svg',
        'get_shared': 'get_shared.svg',
        'create_deck': 'add-deck.svg',
        'import_file': 'import_file.svg',
    }
    
    # 1. Standard Actions
    for action_id, filename in default_icons.items():
        # Check for custom icon
        custom_file = mw.col.conf.get(f"modern_menu_icon_{action_id}", "")
        
        if custom_file:
            icon_url = f"{user_icon_base}{custom_file}"
        else:
            icon_url = f"{icon_base}{filename}"
            
        css = f"""
        .action-{action_id} .icon {{
            mask-image: url('{icon_url}') !important;
            -webkit-mask-image: url('{icon_url}') !important;
            mask-size: contain !important;
            -webkit-mask-size: contain !important;
            mask-repeat: no-repeat !important;
            -webkit-mask-repeat: no-repeat !important;
            mask-position: center !important;
            -webkit-mask-position: center !important;
            background-color: var(--icon-color); 
        }}
        """
        css_lines.append(css)

    # 2. External Actions (from Sidebar API)
    # We already handle 'icon_svg' in sidebar_api.render_sidebar_entry which generates inline styles or classes.
    # But if there are overrides defined in settings, we should handle them.
    # sidebar_api.render_sidebar_entry already checks _load_icon_override.
    # So we mainly need to ensure the standard buttons get their CSS.
    
    return "<style>" + "\n".join(css_lines) + "</style>"


# --- Helper functions (copied from patcher.py for self-containment) ---

def _get_profile_pic_html(user_name: str, addon_package: str, css_class: str = "profile-pic") -> str:    
    profile_pic_filename = mw.col.conf.get("modern_menu_profile_picture", "")
    if profile_pic_filename and os.path.exists(os.path.join(mw.addonManager.addonsFolder(addon_package), "user_files", "profile", profile_pic_filename)):
        pic_url = f"/_addons/{addon_package}/user_files/profile/{profile_pic_filename}"
        return f'<img src="{pic_url}" class="{css_class}">'
    else:
        # Use default profile picture when none is selected or file doesn't exist
        default_pic = "onigiri-san.png"
        pic_url = f"/_addons/{addon_package}/system_files/profile_default/{default_pic}"
        return f'<img src="{pic_url}" class="{css_class}">'

def _get_onigiri_stat_card_html(label: str, value: str, widget_id: str) -> str:
    return f"""<div class="stat-card {widget_id}-card"><h3>{label}</h3><p>{value}</p></div>"""

# Global Cache for stats to prevent re-querying on every render frame
_DASHBOARD_STATS_CACHE = {}
_DASHBOARD_LAST_UPDATE = 0
_DASHBOARD_CACHE_TTL = 3 # 3 seconds is enough to prevent spam during animations, but keeps it fresh

def _get_onigiri_retention_html() -> str:
    # Query retention directly (fast index on id)
    total_reviews, correct_reviews = mw.col.db.first(
        "select count(*), sum(case when ease > 1 then 1 else 0 end) from revlog where type = 1 and id > ?",
        (mw.col.sched.day_cutoff - 86400) * 1000
    ) or (0, 0)
    total_reviews = total_reviews or 0
    correct_reviews = correct_reviews or 0
    retention_percentage = (correct_reviews / total_reviews * 100) if total_reviews > 0 else 0

    if retention_percentage >= 90: stars = 5
    elif retention_percentage >= 70: stars = 4
    elif retention_percentage >= 50: stars = 3
    elif retention_percentage >= 30: stars = 2
    elif total_reviews > 0: stars = 1 # Use total_reviews from scope
    else: stars = 0
    
    conf = config.get_config()
    if conf.get("hideRetentionStars", False):
        star_rating_html = ""
    else:
        star_html = "".join([f"<i class='star{' empty' if i >= stars else ''}'></i>" for i in range(5)])
        star_rating_html = f'<div class="star-rating">{star_html}</div>'

    res_html = f"""
    <div class="stat-card retention-card">
        <h3>{tr("retention")}</h3>
        <div class="retention-content">
            <p>{retention_percentage:.0f}%</p>
            {star_rating_html}
        </div>
    </div>
    """
    return process_tr_markers(res_html)

def _get_onigiri_heatmap_html() -> str:
    skeleton_cells = "".join(["<div class='skeleton-cell'></div>" for _ in range(371)])
    return f"""
    <div id='onigiri-heatmap-container'>
        <div class="heatmap-header-skeleton"><div class="header-left-skeleton"><div class="skeleton-title"></div><div class="skeleton-nav"></div></div><div class="header-right-skeleton"><div class="skeleton-streak"></div><div class="skeleton-filters"></div></div></div>
        <div class="heatmap-grid-skeleton">{skeleton_cells}</div>
    </div>"""

# --- ADD THIS NEW FUNCTION ---
def _get_onigiri_favorites_html() -> str:
    """
    Generates the HTML for the favorites widget.
    Automatically cleans up deleted decks from the favorites list.
    """
    try:
        favorite_dids = mw.col.conf.get("onigiri_favorite_decks", [])
        if not favorite_dids:
            fav_placeholder = """
            <div class="onigiri-favorites-widget">
                <h3>{tr("favorites")}</h3>
                <div class="favorites-placeholder">
                    {tr("no_favorites_selected")}
                    <br>
                    <span>Use the deck menu to add favorites.</span>
                </div>
            </div>
            """
            return process_tr_markers(fav_placeholder)

        links_html = []
        valid_dids = []  # Track valid deck IDs
        
        # Get all existing deck IDs for validation
        all_deck_ids = mw.col.decks.all_names_and_ids()
        existing_deck_ids = {str(deck.id) for deck in all_deck_ids}
        
        for did in favorite_dids:
            # Convert to string for consistent comparison
            did_str = str(did)
            
            # Check if deck actually exists in the collection
            if did_str not in existing_deck_ids:
                print(f"Onigiri: Skipping deleted deck ID {did_str}")
                continue
            
            # Get the deck object
            try:
                deck = mw.col.decks.get(DeckId(int(did_str)))
            except Exception:
                deck = mw.col.decks.get(did)
            if not deck:
                print(f"Onigiri: Skipping invalid deck ID {did_str}")
                continue
            
            # Get the deck name
            deck_name = deck.get("name", "")
            if not deck_name:
                print(f"Onigiri: Skipping deck with no name, ID {did_str}")
                continue
            
            # Deck is valid - add to valid list and create HTML
            valid_dids.append(did_str)
            
            # Get the short name
            short_name = deck_name.split("::")[-1]
            
            # Create a clickable link
            links_html.append(
                f"""<a class="favorite-deck-link" 
                      href=# onclick="pycmd('open:{did_str}'); return false;"
                      title="{tr('open')} {html.escape(deck_name, quote=True)}">
                    <span class="fav-deck-icon"></span>
                    <span class="fav-deck-name">{html.escape(short_name)}</span>
                </a>"""
            )
        
        # Clean up deleted decks from favorites if any were found
        if len(valid_dids) != len(favorite_dids):
            mw.col.conf["onigiri_favorite_decks"] = valid_dids
            mw.col.setMod()
            removed_count = len(favorite_dids) - len(valid_dids)
            print(f"Onigiri: Cleaned up {removed_count} deleted/ghost deck(s) from favorites")
        
        # If no valid favorites remain after cleanup, show placeholder
        if not links_html:
            empty_fav = """
            <div class="onigiri-favorites-widget">
                <h3>{tr("favorites")}</h3>
                <div class="favorites-placeholder">
                    {tr("no_favorites_selected")}
                    <br>
                    <span>Use the deck menu to add favorites.</span>
                </div>
            </div>
            """
            return process_tr_markers(empty_fav)
        
        fav_html = f"""
        <div class="onigiri-favorites-widget">
            <h3>{tr("favorites")}</h3>
            <div class="favorites-list">
                {''.join(links_html)}
            </div>
        </div>
        """
        return process_tr_markers(fav_html)
    except Exception as e:
        print(f"Onigiri: Error building favorites widget: {e}")
        import traceback
        traceback.print_exc()
        return "<div class='onigiri-favorites-widget'>Error loading favorites.</div>"
# --- END OF NEW FUNCTION ---

def _get_onigiri_restaurant_level_html(orientation: str = "horizontal") -> str:
    """
    Generates the HTML for the Restaurant Level widget.
    """
    # Invalidate cache to ensure fresh data when deck browser is rendered
    # REVERTED: Do NOT invalidate here. It causes lag on every render.
    # restaurant_level.manager.invalidate_daily_cache()
    
    # Get Restaurant Level Data
    rl_payload = restaurant_level.manager.get_progress_payload()
    if not rl_payload.get("enabled"):
        return process_tr_markers("""
        <div class="onigiri-restaurant-level-widget disabled">
            <div class="restaurant-info">
                <h3>{tr("restaurant_level")}</h3>
                <p>{tr("feature_disabled")}</p>
            </div>
        </div>
        """)
    
    level = rl_payload.get("level", 0)
    name = rl_payload.get("name", "Restaurant Level")
    
    # Level Progress
    xp_into = rl_payload.get("xpIntoLevel", 0)
    xp_next = rl_payload.get("xpToNextLevel", 0)
    level_percent = rl_payload.get("progressFraction", 0.0) * 100
    
    if xp_next <= 0:
        xp_text = tr("max_level")
    else:
        xp_text = f"{xp_into} / {xp_next} {tr('xp_label')}"

    # Theme Color
    theme_color = restaurant_level.manager.get_current_theme_color()
    bar_color = theme_color if theme_color else "var(--accent-color, #007bff)"
    
    # Background for expanded view
    if theme_color:
        bg_style_value = theme_color
    else:
        bg_style_value = "linear-gradient(135deg, #ff6b6b, #ffb347)"
    
    # Get Image and check if it's Santa's Coffee
    image_file = restaurant_level.manager.get_current_theme_image()
    if not image_file:
        image_file = "restaurant_level.png" # Default
    
    # Check if Santa's Coffee is active
    is_santas_coffee = (image_file == "Santa's Coffee.png")
    snow_class = "with-snow" if is_santas_coffee else ""
    
    # Generate snowflakes HTML if Santa's Coffee is active
    snowflakes_html = ""
    if is_santas_coffee:
        # Create 20 snowflakes with random positions and animations
        import random
        snowflakes = []
        for i in range(20):
            delay = (i * 0.3) % 4  # Stagger the animation
            duration = 8 + (i % 4)  # Vary duration between 8-11s
            left_pos = (i * 5) % 100  # Distribute across width
            top_pos = -(random.random() * 90 + 10)  # Random starting position from -100% to -10% to avoid top edge
            snowflakes.append(f'<div class="snowflake" style="left: {left_pos}%; top: {top_pos}%; animation-delay: {delay}s; animation-duration: {duration}s;">❄</div>')
        snowflakes_html = ''.join(snowflakes)
        
    addon_package = mw.addonManager.addonFromModule(__name__)
    image_path = f"/_addons/{addon_package}/system_files/gamification_images/restaurant_folder/{image_file}"
    
    # Navigation buttons with inline SVGs (using currentColor for --fg-subtle inheritance)
    shop_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="rl-nav-icon"><path fill="currentColor" d="M24,10a.988.988,0,0,0-.024-.217l-1.3-5.868A4.968,4.968,0,0,0,17.792,0H6.208a4.968,4.968,0,0,0-4.88,3.915L.024,9.783A.988.988,0,0,0,0,10v1a3.984,3.984,0,0,0,1,2.643V19a5.006,5.006,0,0,0,5,5H18a5.006,5.006,0,0,0,5-5V13.643A3.984,3.984,0,0,0,24,11ZM2,10.109l1.28-5.76A2.982,2.982,0,0,1,6.208,2H7V5A1,1,0,0,0,9,5V2h6V5a1,1,0,0,0,2,0V2h.792A2.982,2.982,0,0,1,20.72,4.349L22,10.109V11a2,2,0,0,1-2,2H19a2,2,0,0,1-2-2,1,1,0,0,0-2,0,2,2,0,0,1-2,2H11a2,2,0,0,1-2-2,1,1,0,0,0-2,0,2,2,0,0,1-2,2H4a2,2,0,0,1-2-2ZM18,22H6a3,3,0,0,1-3-3V14.873A3.978,3.978,0,0,0,4,15H5a3.99,3.99,0,0,0,3-1.357A3.99,3.99,0,0,0,11,15h2a3.99,3.99,0,0,0,3-1.357A3.99,3.99,0,0,0,19,15h1a3.978,3.978,0,0,0,1-.127V19A3,3,0,0,1,18,22Z"/></svg>'''
    
    restaurant_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="rl-nav-icon"><path fill="currentColor" d="m21 6.424v-2.424c1.654 0 3-1.346 3-3 0-.552-.447-1-1-1s-1 .448-1 1-.448 1-1 1h-19v-1c0-.552-.447-1-1-1s-1 .448-1 1v22c0 .552.447 1 1 1s1-.448 1-1v-19h5v2.424c-1.763.774-3 2.531-3 4.576v8c0 2.757 2.243 5 5 5h10c2.757 0 5-2.243 5-5v-8c0-2.045-1.237-3.802-3-4.576zm-12-2.424h10v2h-10zm13 15c0 1.654-1.346 3-3 3h-10c-1.654 0-3-1.346-3-3v-8c0-1.654 1.346-3 3-3h10c1.654 0 3 1.346 3 3zm-3-2c0-2.414-1.721-4.434-4-4.899v-.101c0-.552-.447-1-1-1s-1 .448-1 1v.101c-2.279.465-4 2.484-4 4.899-.553 0-1 .448-1 1s.447 1 1 1h10c.553 0 1-.448 1-1s-.447-1-1-1zm-5-3c1.654 0 3 1.346 3 3h-6c0-1.654 1.346-3 3-3z"/></svg>'''
    
    nav_buttons_html = f"""
    <div class="rl-widget-nav-buttons">
        <button class="rl-nav-btn" onclick="event.stopPropagation(); pycmd('openTaiyakiStore');" title="{tr('open_taiyaki_store')}">
            {shop_svg}
        </button>
        <button class="rl-nav-btn" onclick="event.stopPropagation(); pycmd('openRestaurantLevel');" title="{tr('open_restaurant_level')}">
            {restaurant_svg}
        </button>
    </div>
    """
    
    # Get Daily Special Data
    daily_special = restaurant_level.manager.get_daily_special_status()
    ds_enabled = daily_special.get("enabled", False)
    ds_progress = daily_special.get("current_progress", 0)
    ds_target = daily_special.get("target", 100)
    
    ds_html = ""
    if ds_enabled:
        percent = min(100, int((ds_progress / ds_target) * 100)) if ds_target > 0 else 0
        ds_html = f"""
        <div class="daily-special-section">
            <div class="ds-header">
                <div class="ds-label">{tr("daily_special")}</div>
                <div class="ds-text">{ds_progress} / {ds_target}</div>
            </div>
            <div class="ds-progress-bar">
                <div class="ds-progress-fill" style="width: {percent}%; background: {bar_color};"></div>
            </div>
        </div>
        """
    else:
        ds_html = f"<div class='daily-special-section'><p class='ds-label'>{tr('no_daily_special_active')}</p></div>"

    widget_orientation = "vertical" if orientation == "vertical" else "horizontal"
    return process_tr_markers(f"""
    <div class="onigiri-restaurant-level-widget orientation-{widget_orientation} {snow_class}" style="--theme-bg: {bg_style_value}; --theme-color: {bar_color}">
        <div class="restaurant-image-container" onclick="this.closest('.onigiri-restaurant-level-widget').classList.toggle('expanded-view'); event.stopPropagation();" style="cursor: pointer;">
            <img src="{image_path}" class="restaurant-image">
            {snowflakes_html}
        </div>
        <div class="restaurant-info">
            <div class="level-display">
                {nav_buttons_html}
                <span class="level-label">{name}</span>
                <span class="level-value">{level}</span>
                <div class="level-progress-container">
                    <div class="lp-bar">
                        <div class="lp-fill" style="width: {level_percent}%; background: {bar_color};"></div>
                    </div>
                    <div class="lp-text">{xp_text}</div>
                </div>
            </div>
            {ds_html}
        </div>
    </div>
    """)

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
    col_count = conf.get("onigiriWidgetLayout", {}).get("column_count", 4) # Default to 4

    onigiri_grid_html = ""
    
    # Check cache for main stats
    global _DASHBOARD_STATS_CACHE, _DASHBOARD_LAST_UPDATE, _DASHBOARD_CACHE_TTL
    now = __import__("time").time()
    
    if now - _DASHBOARD_LAST_UPDATE < _DASHBOARD_CACHE_TTL and "cards_today" in _DASHBOARD_STATS_CACHE:
        cards_today = _DASHBOARD_STATS_CACHE["cards_today"]
        time_today_seconds = _DASHBOARD_STATS_CACHE["time_today_seconds"]
    else:
        # type IN (0,1,2,3) filters out manual operations (type 4 = manual rescheduling/resets)
        cards_today, time_today_seconds = self.mw.col.db.first("select count(), sum(time)/1000 from revlog where type IN (0,1,2,3) and id > ?", (self.mw.col.sched.day_cutoff - 86400) * 1000) or (0, 0)
        
        # Update cache
        _DASHBOARD_STATS_CACHE["cards_today"] = cards_today
        _DASHBOARD_STATS_CACHE["time_today_seconds"] = time_today_seconds
        _DASHBOARD_LAST_UPDATE = now
        

        
    time_today_seconds = time_today_seconds or 0
    cards_today = cards_today or 0
    time_today_minutes = time_today_seconds / 60
    seconds_per_card = time_today_seconds / cards_today if cards_today > 0 else 0

    widget_generators = {
        "studied": lambda: _get_onigiri_stat_card_html(tr("studied"), f"{cards_today} {tr('cards')}", "studied"),
        "time": lambda: _get_onigiri_stat_card_html(tr("time"), f"{time_today_minutes:.1f} {tr('minutes_unit')}", "time"),
        "pace": lambda: _get_onigiri_stat_card_html(tr("pace"), f"{seconds_per_card:.1f} {tr('seconds_unit')}/{tr('card')}", "pace"),
        "retention": _get_onigiri_retention_html,
        "heatmap": _get_onigiri_heatmap_html,
        "favorites": _get_onigiri_favorites_html, 
        "onigimon": onigimon.render_widget_html,
    }
    
    if col_count > 0:
        for widget_id, widget_config in onigiri_layout.items():
            if widget_id in widget_generators or widget_id == "restaurant_level":
                pos = widget_config.get("pos", 0)
                row_span = widget_config.get("row", 1)
                col_span = widget_config.get("col", 1)
                row = pos // col_count + 1
                col = pos % col_count + 1
                style = f"grid-area: {row} / {col} / span {row_span} / span {col_span};"
                if widget_id == "restaurant_level":
                    widget_html = _get_onigiri_restaurant_level_html(widget_config.get("orientation", "horizontal"))
                else:
                    widget_html = widget_generators[widget_id]()
                onigiri_grid_html += f'<div class="onigiri-widget-container" style="{style}">{widget_html}</div>'

    # --- Part 2: Build External Add-on Widgets (into the same unified grid) ---
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

    if col_count > 0:
        for hook_id, widget_config in grid_config.items():
            if hook_html := external_widgets_data.get(hook_id):
                pos = widget_config.get("grid_position", 0)
                row = pos // col_count + 1
                col = pos % col_count + 1
                row_span = widget_config.get("row_span", 1)
                col_span = widget_config.get("column_span", 1)
                style = f"grid-area: {row} / {col} / span {row_span} / span {col_span};"
                # Add external widgets to the same grid as Onigiri widgets
                external_widgets_html += f'<div class="external-widget-container" style="{style}">{hook_html}</div>'

    # --- Part 3: Assemble the Final Stats Block ---
    stats_title = mw.col.conf.get("modern_menu_statsTitle", config.DEFAULTS["statsTitle"])
    title_html = f'<h1 class="onigiri-widget-title">{stats_title}</h1>' if stats_title else ""

    # Combine both Onigiri and External widgets into a single unified grid
    unified_grid_html = onigiri_grid_html + external_widgets_html
    grid_max_width = max(1180, min(1800, col_count * 390)) if col_count > 0 else 1180

    # [CHANGED] Updated CSS to force grid expansion and row height
    stats_block_html = f"""
    <style>
        .evolution-graph-main-wrapper {{
            margin: 0 !important;
            padding: 0 !important;
        }}

        /* Dynamic Sidebar Max-Width removed to allow full stretching */
        /*
        .sidebar-left {{
            max-width: {max(400, min(1200, 1200 - (col_count * 100)))}px !important;
        }}
        */

        .unified-grid {{
            display: grid;
            gap: 15px;
            /* grid-auto-rows ensures every '1 row' has a fixed minimum height (e.g. 110px) */
            grid-auto-rows: minmax(110px, auto);
            grid-template-columns: repeat({col_count}, 1fr);
            width: 100%;
            max-width: {grid_max_width}px;
            box-sizing: border-box;
            overflow: visible;
        }}
        
        /* Make the container expand to fill the grid area (rows/cols) */
        .onigiri-widget-container, .external-widget-container {{
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            position: relative;
        }}

        /* Force the inner content (cards, heatmap, favorites) to fill the container */
        .stat-card, #onigiri-heatmap-container, .onigiri-favorites-widget, .onigimon-widget {{
            flex: 1;
            width: 100%;
            height: 100%;
            box-sizing: border-box;
        }}

        .onigimon-widget {{
            display: flex;
            flex-direction: column;
            gap: 10px;
            padding: 14px;
            border-radius: 15px;
            border: 1px solid var(--border, #e0e0e0);
            background: var(--canvas-inset, #ffffff);
            color: var(--fg, #222);
            overflow: hidden;
        }}

        .onigimon-header,
        .onigimon-main,
        .onigimon-inventory {{
            display: flex;
            align-items: center;
        }}

        .onigimon-header {{
            justify-content: space-between;
            gap: 10px;
        }}

        .onigimon-header h3 {{
            margin: 0;
            font-size: 15px;
        }}

        .onigimon-header span,
        .onigimon-info span {{
            color: var(--fg-subtle, #757575);
            font-size: 12px;
        }}

        .onigimon-ball-btn {{
            width: 22px;
            height: 22px;
            display: grid;
            place-items: center;
            flex: 0 0 22px;
            border: 1px solid var(--border, #e0e0e0);
            border-radius: 999px;
            background: color-mix(in srgb, var(--fg, #222) 5%, transparent);
            padding: 0;
            cursor: pointer;
        }}

        .onigimon-ball-btn:hover {{
            background: color-mix(in srgb, var(--accent-color, #007aff) 14%, transparent);
            border-color: color-mix(in srgb, var(--accent-color, #007aff) 38%, var(--border, #e0e0e0));
        }}

        .onigimon-ball-icon {{
            width: 13px;
            height: 13px;
            display: inline-block;
            background-color: var(--fg-subtle, #757575);
            mask-size: contain;
            -webkit-mask-size: contain;
            mask-repeat: no-repeat;
            -webkit-mask-repeat: no-repeat;
            mask-position: center;
            -webkit-mask-position: center;
            transition: background-color 0.2s ease;
        }}

        .onigimon-ball-btn:hover .onigimon-ball-icon {{
            background-color: var(--accent-color, #007aff);
        }}

        .onigimon-main {{
            gap: 12px;
            min-height: 52px;
        }}

        .onigimon-sprite {{
            width: 58px;
            height: 58px;
            display: grid;
            place-items: center;
            flex: 0 0 58px;
            border-radius: 12px;
            background: color-mix(in srgb, var(--accent-color, #007aff) 10%, transparent);
        }}

        .onigimon-sprite img {{
            width: 54px;
            height: 54px;
            object-fit: contain;
            image-rendering: pixelated;
        }}

        .onigimon-placeholder {{
            width: 30px;
            height: 30px;
            object-fit: contain;
        }}

        .onigimon-info {{
            display: grid;
            gap: 2px;
            min-width: 0;
        }}

        .onigimon-info strong {{
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .onigimon-meter {{
            display: grid;
            grid-template-columns: 54px 1fr;
            gap: 8px;
            align-items: center;
            font-size: 12px;
        }}

        .onigimon-meter > div {{
            height: 7px;
            border-radius: 999px;
            overflow: hidden;
            background: color-mix(in srgb, var(--fg, #222) 10%, transparent);
        }}

        .onigimon-meter i {{
            display: block;
            height: 100%;
            border-radius: inherit;
        }}

        .onigimon-inventory {{
            gap: 7px;
            flex-wrap: wrap;
            color: var(--fg, #222);
            margin-top: auto;
        }}

        .onigimon-inventory span {{
            min-width: 58px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            padding: 7px 10px;
            border-radius: 999px;
            background: color-mix(in srgb, var(--accent-color, #007aff) 10%, transparent);
            font-size: 16px;
            line-height: 1;
        }}

        .onigimon-item-icon {{
            width: 22px;
            height: 22px;
            object-fit: contain;
            image-rendering: pixelated;
            flex: 0 0 auto;
        }}

        .onigimon-care-modal {{
            position: fixed;
            inset: 0;
            z-index: 10000;
            display: none;
            place-items: center;
            padding: 18px;
            background: rgba(0, 0, 0, 0.42);
            box-sizing: border-box;
        }}

        .onigimon-care-modal.is-open {{
            display: grid;
        }}

        .onigimon-care-dialog {{
            position: relative;
            width: min(720px, calc(100vw - 36px));
            display: grid;
            gap: 14px;
            padding: 18px;
            border-radius: 14px;
            border: 1px solid var(--border, #e0e0e0);
            background: var(--canvas, #ffffff);
            color: var(--fg, #222);
            box-shadow: 0 18px 48px rgba(0, 0, 0, 0.24);
            box-sizing: border-box;
        }}

        .onigimon-care-dialog h3 {{
            margin: 0;
            padding-right: 34px;
            font-size: 18px;
        }}

        #onigimon-care-modal .onigimon-modal-close {{
            --onigimon-close-bg: rgba(20, 20, 20, 0.08);
            --onigimon-close-fg: #222222;
            position: absolute;
            top: 10px;
            right: 10px;
            width: 28px;
            height: 28px;
            border: 0 !important;
            border-radius: 999px;
            background: var(--onigimon-close-bg) !important;
            color: var(--onigimon-close-fg) !important;
            cursor: pointer;
            line-height: 1;
            outline: none !important;
            box-shadow: none !important;
            transform: none !important;
            transition: none !important;
            animation: none !important;
            -webkit-tap-highlight-color: transparent;
        }}

        #onigimon-care-modal .onigimon-modal-close:hover,
        #onigimon-care-modal .onigimon-modal-close:active,
        #onigimon-care-modal .onigimon-modal-close:focus,
        #onigimon-care-modal .onigimon-modal-close:focus-visible {{
            border: 0 !important;
            background: var(--onigimon-close-bg) !important;
            color: var(--onigimon-close-fg) !important;
            outline: none !important;
            box-shadow: none !important;
            transform: none !important;
            transition: none !important;
            animation: none !important;
        }}

        .night #onigimon-care-modal .onigimon-modal-close,
        .night-mode #onigimon-care-modal .onigimon-modal-close,
        .nightMode #onigimon-care-modal .onigimon-modal-close {{
            --onigimon-close-bg: rgba(255, 255, 255, 0.12);
            --onigimon-close-fg: #f2f2f2;
        }}

        #onigimon-care-modal .onigimon-close-icon {{
            width: 18px;
            height: 18px;
            display: block;
            margin: auto;
            pointer-events: none;
            background-color: var(--onigimon-close-fg) !important;
            mask-size: contain;
            -webkit-mask-size: contain;
            mask-repeat: no-repeat;
            -webkit-mask-repeat: no-repeat;
            mask-position: center;
            -webkit-mask-position: center;
            transform: none !important;
            transition: none !important;
            animation: none !important;
        }}

        #onigimon-care-modal .onigimon-modal-close:hover .onigimon-close-icon,
        #onigimon-care-modal .onigimon-modal-close:active .onigimon-close-icon,
        #onigimon-care-modal .onigimon-modal-close:focus .onigimon-close-icon {{
            background-color: var(--onigimon-close-fg) !important;
            transform: none !important;
            transition: none !important;
            animation: none !important;
        }}

        .onigimon-care-actions {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
        }}

        .onigimon-care-actions button {{
            min-width: 0;
            display: grid;
            justify-items: center;
            gap: 5px;
            border: 1px solid var(--border, #e0e0e0);
            border-radius: 10px;
            padding: 10px 8px;
            background: color-mix(in srgb, var(--accent-color, #007aff) 8%, var(--canvas-inset, #f6f6f6));
            color: inherit;
            cursor: pointer;
        }}

        .onigimon-care-actions button:disabled {{
            opacity: 0.45;
            cursor: default;
        }}

        .onigimon-care-actions .onigimon-item-icon {{
            width: 30px;
            height: 30px;
        }}

        .onigimon-care-actions span {{
            font-weight: 600;
            font-size: 13px;
        }}

        .onigimon-care-actions small {{
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--fg-subtle, #757575);
            font-size: 11px;
        }}

        .onigimon-category-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .onigimon-category-chip {{
            min-width: 128px;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            border: 1px solid transparent;
            border-radius: 999px;
            padding: 8px 11px;
            background: color-mix(in srgb, var(--accent-color, #007aff) 11%, transparent);
            color: inherit;
            cursor: pointer;
            font-size: 13px;
        }}

        .onigimon-category-chip:disabled {{
            opacity: 0.45;
            cursor: default;
        }}

        .onigimon-category-chip:not(:disabled):hover {{
            border-color: var(--onigimon-item-color, var(--accent-color, #007aff));
        }}

        .onigimon-category-chip.is-selected {{
            border-color: var(--onigimon-item-color, var(--accent-color, #007aff));
            background: var(--onigimon-item-bg-light, color-mix(in srgb, var(--accent-color, #007aff) 18%, transparent));
        }}

        .onigimon-category-chip[data-category="treats"]:not(:disabled):hover {{
            border-color: #ff6fc8;
        }}

        .onigimon-category-chip[data-category="treats"].is-selected {{
            border-color: #ff6fc8;
            background: #ffe0f3;
        }}

        .night .onigimon-category-chip[data-category="treats"].is-selected,
        .night-mode .onigimon-category-chip[data-category="treats"].is-selected,
        .nightMode .onigimon-category-chip[data-category="treats"].is-selected {{
            background: #4a1735;
        }}

        .night .onigimon-category-chip.is-selected,
        .night-mode .onigimon-category-chip.is-selected,
        .nightMode .onigimon-category-chip.is-selected {{
            border-color: var(--onigimon-item-color, var(--accent-color, #007aff));
            background: var(--onigimon-item-bg-dark, color-mix(in srgb, var(--accent-color, #007aff) 22%, transparent));
        }}

        .onigimon-category-chip span {{
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-weight: 600;
        }}

        .onigimon-category-chip b {{
            margin-left: auto;
            font-size: 14px;
        }}

        .onigimon-category-panels {{
            display: grid;
            gap: 8px;
        }}

        .onigimon-category-panel {{
            display: none;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 8px;
            padding: 10px;
            border: 1px solid var(--border, #e0e0e0);
            border-radius: 10px;
            background: color-mix(in srgb, var(--fg, #222) 4%, transparent);
        }}

        .onigimon-category-panel.is-open {{
            display: grid;
        }}

        .onigimon-inventory-choice {{
            min-width: 0;
            display: grid;
            justify-items: center;
            gap: 4px;
            border: 1px solid var(--border, #e0e0e0);
            border-radius: 9px;
            padding: 8px 6px;
            background: var(--canvas-inset, #f6f6f6);
            color: inherit;
            cursor: pointer;
        }}

        .onigimon-inventory-choice:disabled {{
            opacity: 0.45;
            cursor: default;
        }}

        .onigimon-inventory-choice:not(:disabled):hover {{
            border-color: var(--onigimon-item-color, var(--accent-color, #007aff));
        }}

        .onigimon-inventory-choice.is-selected {{
            border-color: var(--onigimon-item-color, var(--accent-color, #007aff));
            background: var(--onigimon-item-bg-light, color-mix(in srgb, var(--accent-color, #007aff) 16%, var(--canvas-inset, #f6f6f6)));
        }}

        .onigimon-inventory-choice[data-item="poke_candies"]:hover {{
            border-color: #ff6fc8;
        }}

        .onigimon-inventory-choice[data-item="poke_candies"].is-selected {{
            border-color: #ff6fc8;
            background: #ffe0f3;
        }}

        .night .onigimon-inventory-choice[data-item="poke_candies"].is-selected,
        .night-mode .onigimon-inventory-choice[data-item="poke_candies"].is-selected,
        .nightMode .onigimon-inventory-choice[data-item="poke_candies"].is-selected {{
            background: #4a1735;
        }}

        .night .onigimon-inventory-choice.is-selected,
        .night-mode .onigimon-inventory-choice.is-selected,
        .nightMode .onigimon-inventory-choice.is-selected {{
            border-color: var(--onigimon-item-color, var(--accent-color, #007aff));
            background: var(--onigimon-item-bg-dark, color-mix(in srgb, var(--accent-color, #007aff) 18%, var(--canvas-inset, #2c2c2c)));
        }}

        .onigimon-inventory-choice.is-passive {{
            cursor: default;
        }}

        .onigimon-inventory-choice span {{
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 12px;
            font-weight: 600;
        }}

        .onigimon-inventory-choice small {{
            color: var(--fg-subtle, #757575);
            font-size: 11px;
            line-height: 1.25;
            text-align: center;
        }}

        .onigimon-modal-inventory {{
            display: grid;
            gap: 8px;
        }}

        .onigimon-modal-inventory-title {{
            color: var(--fg-subtle, #757575);
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .onigimon-modal-inventory-title:not(:first-child) {{
            margin-top: 4px;
        }}

        .onigimon-modal-inventory-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 7px;
        }}

        .onigimon-empty-category {{
            color: var(--fg-subtle, #757575);
            font-size: 12px;
            padding: 6px 2px;
        }}

        .onigimon-inventory-chip {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            max-width: 170px;
            padding: 7px 9px;
            border-radius: 999px;
            background: color-mix(in srgb, var(--accent-color, #007aff) 9%, transparent);
            color: inherit;
            font-size: 12px;
        }}

        .onigimon-inventory-chip span {{
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .onigimon-inventory-chip b {{
            font-size: 13px;
        }}

        .onigimon-berry-chip {{
            display: grid;
            grid-template-columns: 22px minmax(0, 1fr) auto;
            align-items: center;
            max-width: 230px;
            border-radius: 12px;
        }}

        .onigimon-berry-chip small {{
            grid-column: 2 / 4;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--fg-subtle, #757575);
            font-size: 10px;
        }}

        /* Care Modal Display & Animations */
        .onigimon-care-display {{
            position: relative;
            height: 190px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: color-mix(in srgb, var(--accent-color, #007aff) 8%, var(--canvas-inset, #f6f6f6));
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border, #e0e0e0);
        }}

        .night .onigimon-care-display {{
            background: color-mix(in srgb, var(--accent-color, #007aff) 12%, var(--canvas-inset, #2c2c2c));
            border-color: var(--border, #444);
        }}

        .onigimon-care-sprite {{
            width: 96px;
            height: 96px;
            display: grid;
            place-items: center;
            z-index: 2;
        }}

        .onigimon-care-sprite img {{
            width: 92px;
            height: 92px;
            object-fit: contain;
            image-rendering: pixelated;
        }}

        .onigimon-care-item-flow {{
            position: absolute;
            left: 25px;
            top: 25px;
            width: 32px;
            height: 32px;
            opacity: 0;
            z-index: 4;
            pointer-events: none;
        }}

        .onigimon-care-item-flow img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
            image-rendering: pixelated;
        }}

        .onigimon-care-modal.has-reaction.is-open .onigimon-care-sprite {{
            animation: onigimon-bounce 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275) 0.5s both;
        }}

        .onigimon-care-modal.has-reaction.is-open .onigimon-care-item-flow {{
            animation: onigimon-item-flow 1.0s cubic-bezier(0.25, 0.46, 0.45, 0.94) 0.2s both;
        }}

        @keyframes onigimon-bounce {{
            0% {{ transform: scale(1); }}
            30% {{ transform: scale(1.2) translateY(-12px); }}
            50% {{ transform: scale(0.9) translateY(0); }}
            70% {{ transform: scale(1.05) translateY(-4px); }}
            100% {{ transform: scale(1) translateY(0); }}
        }}

        @keyframes onigimon-item-flow {{
            0% {{
                opacity: 0;
                transform: translate(0, 0) scale(0.6) rotate(0deg);
            }}
            20% {{
                opacity: 1;
                transform: translate(15px, -15px) scale(1.2) rotate(-20deg);
            }}
            80% {{
                opacity: 1;
                transform: translate(110px, 20px) scale(0.9) rotate(180deg);
            }}
            100% {{
                opacity: 0;
                transform: translate(125px, 25px) scale(0.1) rotate(220deg);
            }}
        }}

        /* Restaurant Level Widget Styles */
        .onigiri-restaurant-level-widget {{
            display: flex;
            flex-direction: row;
            background: var(--canvas-inset, #f5f5f5);
            border-radius: 15px;
            overflow: hidden;
            height: 100%;
            border: 1px solid var(--border, #e0e0e0);
            /* cursor: pointer; removed - only image is clickable */
            transition: all 0.3s ease;
            position: relative;
        }}

        .onigiri-restaurant-level-widget.orientation-vertical {{
            flex-direction: column;
        }}
        
        .onigiri-restaurant-level-widget.expanded-view {{
            background: var(--theme-bg) !important;
            border-color: transparent;
        }}
        
        .night .onigiri-restaurant-level-widget {{
            background: var(--canvas-inset, #2c2c2c);
            border-color: var(--border, #444);
        }}

        .restaurant-image-container {{
            flex: 0 0 45%; /* Fixed width percentage */
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--canvas-inset);
            padding: 10px;
            position: relative;
            transition: all 0.3s ease;
            box-sizing: border-box;
            min-width: 0;
            min-height: 0;
            overflow: hidden;
        }}

        .onigiri-restaurant-level-widget.orientation-vertical .restaurant-image-container {{
            flex: 0 0 auto;
            width: 100%;
            height: auto;
            aspect-ratio: 1 / 1;
            min-height: 0;
            padding: 8px 10px 0 10px;
        }}
        
        /* Unrestricted Sidebar resizing */
        .sidebar-left {{
            max-width: none !important;
        }}

        .main-content {{
            /* Dynamic Padding based on col_count */
            padding: {24 if col_count == 4 else (14 if col_count > 4 else 32)}px !important;
            box-sizing: border-box !important;
            /* Sidebar Only Mode: Hide main content if cols=0 or rows=0 */
            display: {'none' if (col_count == 0 or conf.get('unifiedGridRows', 6) == 0) else 'flex'} !important;
            flex-direction: column;
            align-items: center;
        }}
        
        /* Center the sidebar if main content is hidden */
        .modern-main-menu.container {{
            justify-content: {'center' if (col_count == 0 or conf.get('unifiedGridRows', 6) == 0) else 'flex-start'} !important;
        }}

        /* Allow grid to expand beyond 900px if we have many columns */
        .main-content > * {{
            width: 100%;
            max-width: {grid_max_width}px !important;
        }}

        .onigiri-restaurant-level-widget.expanded-view .restaurant-image-container {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: transparent;
            padding: 5px; /* Reduced padding to make image larger */
            z-index: 10;
        }}
        
        .night .restaurant-image-container {{
            background: var(--canvas-inset);
        }}

        .restaurant-image {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            filter: drop-shadow(0 4px 6px rgba(0,0,0,0.15));
            transition: transform 0.3s ease;
        }}
        
        .onigiri-restaurant-level-widget:hover .restaurant-image {{
            transform: scale(1.05);
        }}
        
        .onigiri-restaurant-level-widget.expanded-view .restaurant-image {{
            transform: scale(1.0);
            filter: drop-shadow(0 8px 12px rgba(0,0,0,0.2));
        }}

        .restaurant-info {{
            flex: 1;
            min-width: 0;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 15px 20px;
            gap: 15px;
            transition: opacity 0.2s ease;
        }}

        .onigiri-restaurant-level-widget.orientation-vertical .restaurant-info {{
            padding: 10px 16px 14px 16px;
            gap: 10px;
        }}
        
        .onigiri-restaurant-level-widget.expanded-view .restaurant-info {{
            display: none;
            opacity: 0;
        }}

        .level-display {{
            display: flex;
            flex-direction: column;
            align-items: flex-start;
        }}

        .level-label {{
            font-size: 0.75em;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--fg-subtle, #888);
            font-weight: 600;
            margin-bottom: 2px;
        }}

        .level-value {{
            font-size: 2.8em;
            font-weight: 800;
            color: var(--fg, #333);
            line-height: 1;
        }}

        .level-progress-container {{
            width: 100%;
            margin-top: 6px;
        }}
        
        .lp-bar {{
            height: 6px;
            background: var(--border, #e0e0e0);
            border-radius: 3px;
            overflow: hidden;
            width: 100%;
            margin-bottom: 2px;
        }}
        
        .lp-fill {{
            height: 100%;
            border-radius: 3px;
            transition: width 0.5s ease;
        }}
        
        .lp-text {{
            font-size: 0.7em;
            color: var(--fg-subtle, #888);
            text-align: right;
            font-weight: 500;
        }}

        .daily-special-section {{
            display: flex;
            flex-direction: column;
            gap: 6px;
            width: 100%;
        }}
        
        .ds-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
        }}

        .ds-label {{
            font-size: 0.9em;
            font-weight: 600;
            color: var(--fg, #333);
        }}

        .ds-progress-bar {{
            height: 8px;
            background: var(--border, #e0e0e0);
            border-radius: 4px;
            overflow: hidden;
            width: 100%;
        }}

        .ds-progress-fill {{
            height: 100%;
            background: var(--accent-color, #007bff);
            border-radius: 4px;
            transition: width 0.5s ease;
        }}

        .ds-text {{
            font-size: 0.85em;
            color: var(--fg-subtle, #888);
            font-weight: 500;
        }}
        
        /* Snow Animation for Santa's Coffee Theme */
        .onigiri-restaurant-level-widget.with-snow .restaurant-image-container {{
            overflow: visible;
        }}
        
        .snowflake {{
            position: absolute;
            top: -20px;
            color: #fff;
            font-size: 1.2em;
            opacity: 0.8;
            pointer-events: none;
            animation: snowfall linear infinite;
            text-shadow: 0 0 5px rgba(255, 255, 255, 0.8);
            z-index: 10;
        }}
        
        @keyframes snowfall {{
            0% {{
                transform: translateY(0) translateX(0);
                opacity: 0;
            }}
            10% {{
                opacity: 0.8;
            }}
            90% {{
                opacity: 0.8;
            }}
            100% {{
                transform: translateY(300px) translateX(20px);
                opacity: 0;
            }}
        }}
        
        /* Make snowflakes visible in expanded view too */
        .onigiri-restaurant-level-widget.expanded-view.with-snow .snowflake {{
            display: block;
        }}
        
        /* Navigation buttons for Restaurant Level Widget */
        .rl-widget-nav-buttons {{
            display: flex;
            gap: 0;
            z-index: 20;
            margin-bottom: 2px;
            margin-left: 0; 
            padding-left: 0;
        }}
        
        .rl-nav-btn {{
            width: 24px;
            height: 24px;
            padding: 0;
            margin-left: 0;
            border: none;
            background: transparent;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: flex-start;
            transition: all 0.2s ease;
            color: var(--fg-subtle, #757575);
        }}
        
        .night .rl-nav-btn {{
            background: transparent;
            color: var(--fg-subtle, #9e9e9e);
        }}
        
        .rl-nav-btn:hover {{
            background: transparent;
            color: var(--theme-color);
            transform: none;
            border: none;
            box-shadow: none;
            outline: none;
        }}
        
        .night .rl-nav-btn:hover {{
            background: transparent;
            color: var(--theme-color);
            border: none;
        }}
        
        .rl-nav-icon {{
            width: 16px;
            height: 16px;
            margin-left: 4px;
        }}
        
        /* Style for expanded view - reduce button visibility */
        .onigiri-restaurant-level-widget.expanded-view .rl-widget-nav-buttons {{
            opacity: 0.5;
        }}
    </style>
    {title_html}
    <div class="unified-grid">{unified_grid_html}</div>
    """

    # --- Part 4: Manually Build the Deck Tree HTML ---
    # CRITICAL: Store tree data for Anki's context menu operations (e.g., deck deletion)
    # Anki's native _delete method expects self._render_data.tree to exist
    tree_data = self.mw.col.sched.deck_due_tree()
    self._render_data = RenderData(tree=tree_data)
    tree_html = deck_tree_updater._render_deck_tree_html_only(self)
    
    # Add OnigiriEngine JavaScript
    onigiri_engine_js = """
    <script>
    // Onigiri Performance Engine
    window.OnigiriEngine = {
        currentHoveredRow: null,

        init: function() {
            this.deckListContainer = document.getElementById('deck-list-container');
            if (!this.deckListContainer) return;
            this.bindEvents();
            this.observeMutations();
            console.log('OnigiriEngine initialized');
        },

        saveScrollPosition: function() {
            const container = document.querySelector('.deck-list-scroll-container');
            if (container) {
                this.scrollPosition = container.scrollTop;
            }
        },

        restoreScrollPosition: function() {
            const container = document.querySelector('.deck-list-scroll-container');
            if (container && typeof this.scrollPosition !== 'undefined') {
                container.scrollTop = this.scrollPosition;
            }
        },

        bindEvents: function() {
            if (this.deckListContainer.dataset.engineBound) return;
            this.deckListContainer.dataset.engineBound = 'true';

            // Handle deck row hover
            this.deckListContainer.addEventListener('mouseenter', (event) => {
                const deckRow = event.target.closest('tr.deck');
                if (deckRow) {
                    this.currentHoveredRow = deckRow;
                    deckRow.classList.add('is-hovered');
                }
            }, true);

            this.deckListContainer.addEventListener('mouseleave', (event) => {
                const deckRow = event.target.closest('tr.deck');
                if (deckRow && deckRow === this.currentHoveredRow) {
                    deckRow.classList.remove('is-hovered');
                    this.currentHoveredRow = null;
                }
            }, true);

            // Handle deck collapse/expand
            this.deckListContainer.addEventListener('click', (event) => {
                const collapseLink = event.target.closest('a.collapse');
                if (collapseLink) {
                    event.preventDefault();
                    event.stopPropagation();
                    this.saveScrollPosition();
                    
                    const deckRow = event.target.closest('tr.deck');
                    if (deckRow && deckRow.dataset.did) {
                        pycmd(`onigiri_collapse:${deckRow.dataset.did}`);
                    }
                    return false;
                }
            });
        },

        observeMutations: function() {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach(mutation => {
                    if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                        this.processNewNodes(mutation.addedNodes);
                    }
                });
            });

            observer.observe(this.deckListContainer, {
                childList: true,
                subtree: true,
            });
        },

        processNewNodes: function(nodes) {
            nodes.forEach(node => {
                if (node.nodeType !== Node.ELEMENT_NODE) return;
                
                const elementsToProcess = [];
                if (node.matches('a.collapse, tr.deck')) {
                    elementsToProcess.push(node);
                }
                elementsToProcess.push(...node.querySelectorAll('a.collapse, tr.deck'));

                elementsToProcess.forEach(this.classifyCollapseIcon.bind(this));
            });
        },

        classifyCollapseIcon: function(el) {
            if (el.matches('a.collapse')) {
                if (el.classList.contains('state-closed')) {
                    el.textContent = '+';
                } else {
                    el.textContent = '-';
                }
            }
        },

        // Update the deck tree with new HTML
        updateDeckTree: function(html) {
            const tbody = document.querySelector('#decktree > tbody');
            if (tbody) {
                tbody.innerHTML = html;
                this.restoreScrollPosition();
                
                // Re-process any new collapse icons
                this.processNewNodes([tbody]);
                
                // Trigger any layout updates
                if (window.updateDeckLayouts) {
                    window.updateDeckLayouts();
                }
            }
        }
    };

    // Initialize the engine once the DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => OnigiriEngine.init());
    } else {
        OnigiriEngine.init();
    }
    </script>
    """
    
    # --- Part 5: Populate the Main Template ---
    is_collapsed = mw.col.conf.get("onigiri_sidebar_collapsed", False)
    is_focused = mw.col.conf.get("onigiri_deck_focus_mode", False)
    
    # Check for Sidebar Only Mode (0 columns or 0 rows)
    is_sidebar_only = (col_count == 0 or conf.get('unifiedGridRows', 6) == 0)
    
    sidebar_initial_class = ""
    if is_collapsed:
        sidebar_initial_class += "sidebar-collapsed"
    if is_focused:
        sidebar_initial_class += " deck-focus-mode" if sidebar_initial_class else "deck-focus-mode"
    if is_sidebar_only:
        sidebar_initial_class += " sidebar-only-mode" if sidebar_initial_class else "sidebar-only-mode"

    # --- MODIFICATION START ---
    
    # Build the dynamic profile bar HTML
    user_name = conf.get("userName", "USER")
    
    profile_bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "accent")
    profile_bg_image = mw.col.conf.get("modern_menu_profile_bg_image", "")
    bg_style_str = ""
    bg_class_str = ""

    if profile_bg_mode == "image":
        if profile_bg_image and os.path.exists(os.path.join(mw.addonManager.addonsFolder(addon_package), "user_files", "profile_bg", profile_bg_image)):
            bg_image_url = f"/_addons/{addon_package}/user_files/profile_bg/{profile_bg_image}"
        else:
            # Use default background image when none is selected or file doesn't exist
            bg_image_url = f"/_addons/{addon_package}/system_files/profile_default/onigiri-bg.png"
        bg_style_str = f"background-image: url('{bg_image_url}'); background-size: cover; background-position: center;"
        bg_class_str = "with-image-bg"
    elif profile_bg_mode == "custom":
        bg_style_str = "background-color: var(--profile-bg-custom-color);"
    else: # accent
        bg_style_str = "background-color: var(--accent-color);"
    
    profile_pic_html_expanded = _get_profile_pic_html(user_name, addon_package)

    rl_payload = restaurant_level.manager.get_progress_payload()
    rl_chip = ""
    if rl_payload.get("enabled") and rl_payload.get("showProfileBar"):
        percent = rl_payload.get("progressFraction") or 0.0
        percent = max(0.0, min(1.0, float(percent))) * 100
        percent = 0 if rl_payload.get("xpToNextLevel", 0) == 0 else percent
        fill_width = f"{percent:.1f}%" if percent else "0%"
        if rl_payload.get("xpToNextLevel", 0) > 0:
            xp_detail = f"{rl_payload.get('xpIntoLevel', 0)} / {rl_payload.get('xpToNextLevel', 0)} XP"
        else:
            xp_detail = f"{rl_payload.get('totalXp', 0)} XP total"
        # Use the full module path to avoid any potential naming conflicts
        import html as html_module
        xp_detail = html_module.escape(xp_detail, quote=True)
        rl_chip = f"""
        <div class="restaurant-level-chip" title="{xp_detail}">
            <span class="rl-chip-level">{tr('level_prefix')} {rl_payload.get('level', 0)}</span>
            <div class="rl-chip-progress">
                <div class="rl-chip-progress-fill" style="width: {fill_width}"></div>
            </div>
        </div>
        """.strip()

    profile_bar_contents = (
        f"{profile_pic_html_expanded}"
        f"<span class=\"profile-name\">{user_name}</span>"
    )
    if rl_chip:
        profile_bar_contents += rl_chip
    
    # Inject CSS for theme colors if a theme is active
    theme_css = ""
    bar_mode = mw.col.conf.get("onigiri_profile_level_bar_mode", "theme")
    if bar_mode == "custom":
        rl_theme_color = mw.col.conf.get("onigiri_profile_level_bar_custom_color", "#4CAF50")
    else:
        rl_theme_color = restaurant_level.manager.get_current_theme_color()

    if rl_theme_color:
        theme_css = f"""
        <style id="profile-bar-theme-colors">
            .profile-bar .restaurant-level-chip .rl-chip-progress {{
                background: rgba({int(rl_theme_color[1:3], 16)}, {int(rl_theme_color[3:5], 16)}, {int(rl_theme_color[5:7], 16)}, 0.25) !important;
            }}
            
            .night-mode .profile-bar .restaurant-level-chip .rl-chip-progress {{
                background: rgba({int(rl_theme_color[1:3], 16)}, {int(rl_theme_color[3:5], 16)}, {int(rl_theme_color[5:7], 16)}, 0.35) !important;
            }}
            
            .profile-bar .restaurant-level-chip .rl-chip-progress-fill {{
                background: {rl_theme_color} !important;
            }}
            
            .level-progress-bar {{
                background: {rl_theme_color} !important;
            }}
        </style>
        """
        
    # --- ADDED: Generate CSS for Action Icons ---
    action_icons_css = _generate_action_icons_css(conf, addon_package)
    theme_css += action_icons_css

    profile_bar_html = (
        f"<div class=\"profile-bar {bg_class_str}\" style=\"{bg_style_str}\" "
        f"onclick=\"pycmd('showUserProfile')\">{profile_bar_contents}</div>"
    )
    
    # 1. Build the dynamic sidebar HTML from the layout config
    sidebar_buttons_html = _build_sidebar_html(conf)
    
    # 2. Manually replace {profile_bar} inside the sidebar HTML string
    #    (This is necessary because {profile_bar} is one of the items in BUTTON_HTML)
    sidebar_buttons_html = sidebar_buttons_html.replace("{profile_bar}", profile_bar_html)
    
    # --- This logic remains the same ---
    profile_pic_html_collapsed = _get_profile_pic_html(user_name, addon_package, "collapsed-profile-pic")
    
    # [LOCALIZED] Use tr("welcome_profile") for the sidebar welcome message
    welcome_message = tr("welcome_profile").format(name=user_name.upper()) if not conf.get("hideWelcomeMessage", False) else ""
    
    saved_width = mw.col.conf.get("modern_menu_sidebar_width", 300)
    sidebar_style = f"width: {saved_width}px;"
    container_extra_class = ""

    # 3. Use the new {sidebar_buttons} placeholder in the template
    #    and remove the old {profile_bar} placeholder.
    
    # Inject Config for JS
    action_icon_keys = [
        "add", "browse", "stats", "sync", "settings", "more",
        "get_shared", "create_deck", "import_file"
    ]
    collapsed_icons = {
        key: mw.col.conf.get(f"modern_menu_icon_{key}", "")
        for key in action_icon_keys
    }
    js_config = {
        "sidebarActionsMode": conf.get("sidebarActionsMode", "list"),
        "addonPackage": mw.addonManager.addonFromModule(__name__),
        "collapsedIcons": collapsed_icons,
        "deckSortMode": mw.col.conf.get("onigiri_sort_mode", "default"),
        "markerColors": conf.get("markerColors", config.DEFAULTS.get("markerColors", {})),
        "filters": {
            "favorites": bool(mw.col.conf.get("onigiri_show_favourites", False) or mw.col.conf.get("onigiri_show_favorites", False)),
            "marked": bool(mw.col.conf.get("onigiri_show_marked", False)),
        },
    }
    
    # Get Sync Status
    sync_status = patcher.get_sync_status()

    # Create JS Injection Script
    js_injection = f"""
    <script>
        window.ONIGIRI_CONFIG = {json.dumps(js_config)};
        window.ONIGIRI_SYNC_STATUS = "{sync_status}";
    </script>
    """
    
    final_body = custom_body_template \
        .replace("{tree}", tree_html) \
        .replace("{stats}", stats_block_html + theme_css + js_injection) \
        .replace("{container_extra_class}", container_extra_class) \
        .replace("{sidebar_initial_class}", sidebar_initial_class) \
        .replace("{sidebar_style}", sidebar_style) \
        .replace("{welcome_message}", welcome_message) \
        .replace("{tr_decks}", tr("decks_header")) \
        .replace("{sidebar_buttons}", sidebar_buttons_html) \
        .replace("{profile_pic_html_collapsed}", profile_pic_html_collapsed)
    
    # --- MODIFICATION END ---
    
    # --- Part 6: Render the Final Page ---
    self.web.stdHtml(
        body=final_body,
        css=["css/deckbrowser.css"],
        js=["js/vendor/jquery.min.js", "js/vendor/jquery-ui.min.js", "js/deckbrowser.js"],
        context=self,
    )

    from aqt import gui_hooks
    gui_hooks.deck_browser_did_render(self)
