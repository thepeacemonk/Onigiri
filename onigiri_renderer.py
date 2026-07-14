# Onigiri's dedicated Deck Browser Rendering Engine

import html
import json
import os
import re
import copy
from dataclasses import dataclass

from aqt import mw
from aqt.deckbrowser import DeckBrowser, RenderDeckNodeContext

from . import config, heatmap, deck_tree_updater, sidebar_api, profile_background
from . import patcher
from .gamification import onigimon, nook_level
from .templates import custom_body_template


def _system_icon_url(addon_package: str, filename: str) -> str:
    """Return the web URL for a system icon filename."""
    return f"/_addons/{addon_package}/system_files/system_icons/{filename}"


def _user_icon_url(addon_package: str, filename: str) -> str:
    """Return the web URL for a user-uploaded icon filename."""
    return f"/_addons/{addon_package}/user_files/icons/{filename}"


def _configured_action_icon_url(addon_package: str, action_key: str, default_filename: str) -> str:
    """Resolve an action icon, falling back to the system filename if a custom file is missing."""
    try:
        custom = mw.col.conf.get(f"modern_menu_icon_{action_key}", "")
    except Exception:
        custom = ""
    if custom:
        custom_path = os.path.join(os.path.dirname(__file__), "user_files", "icons", custom)
        if os.path.exists(custom_path):
            return _user_icon_url(addon_package, custom)
    return _system_icon_url(addon_package, default_filename)


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
            <span>Add</span>
        </div>
    """,
    "browse": """
        <div class="menu-item action-browse" onclick="pycmd('browse')">
            <i class="icon"></i>
            <span>Browser</span>
        </div>
    """,
    "stats": """
        <div class="menu-item action-stats" onclick="pycmd('stats')">
            <i class="icon"></i>
            <span>Stats</span>
        </div>
    """,
    "sync": """
        <div class="menu-item action-sync" onclick="pycmd('sync')">
            <i class="icon"></i>
            <span>Sync</span>
            <span class="sync-status-indicator"></span>
        </div>
    """,
    "settings": """
        <div class="menu-item action-settings" onclick="pycmd('openOnigiriSettings')">
            <i class="icon"></i>
            <span>Settings</span>
        </div>
    """,
    "gamification": """
        <div class="menu-item action-gamification" onclick="pycmd('openGamificationSettings')">
            <i class="icon"></i>
            <span>Onigiri Games</span>
        </div>
    """,
    "more": """
        <details class="menu-group">
            <summary class="menu-item action-more">
                <i class="icon"></i>
                <span>More</span>
            </summary>
            <div class="menu-group-items">
                <div class="menu-item action-get-shared" onclick="pycmd('shared')">
                    <i class="icon"></i>
                    <span>Get Shared</span>
                </div>
                <div class="menu-item action-create-deck" onclick="pycmd('onigiri_create_deck')">
                    <i class="icon"></i>
                    <span>Create Deck</span>
                </div>
                <div class="menu-item action-import-file" onclick="pycmd('import')">
                    <i class="icon"></i>
                    <span>Import File</span>
                </div>
            </div>
        </details>
    """
}

_SIDEBAR_ACTION_MODE_MAP = {
    "list": "full",
    "collapsed": "compact",
    "archived": "minimal",
    "ellipsis": "minimal",
}


def _normalize_sidebar_actions_mode(raw_mode: str) -> str:
    return _SIDEBAR_ACTION_MODE_MAP.get(raw_mode, raw_mode or "full")


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
    # Default to "full" if not set, while still accepting older config values.
    actions_mode = _normalize_sidebar_actions_mode(conf.get("sidebarActionsMode", "full"))
    
    html_parts = []
    for key in visible_keys:
        if actions_mode == "minimal" and key == "profile" and key in BUTTON_HTML:
            html_parts.insert(0, BUTTON_HTML[key])
            continue
        # If this key is one of our special action buttons...
        if key in action_buttons:
            # Only render it in the list if mode is "full"
            if actions_mode == "full":
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
            # If the user selects "Compact", external sidebar items should probably also disappear/move to toolbar?
            # The current implementation of compact mode in injector.js only handles specific IDs.
            # So for now, we'll keep external entries showing in list unless explicitly hidden, 
            # OR we should hide them too if the goal is a clean sidebar.
            # However, SidebarEntry doesn't have a "compact" equivalent yet.
            # Let's hide them in compact/minimal mode for consistency if they are button-like.
            if actions_mode == "full": 
                html_parts.append(sidebar_api.render_sidebar_entry(key))
            
    return "\n".join(part for part in html_parts if part)

def _generate_action_icons_css(conf: dict, addon_package: str) -> str:
    """
    Generates CSS to apply custom or default icons to the sidebar list items.
    """
    css_lines = []
    icon_base = f"/_addons/{addon_package}/system_files/system_icons/"
    user_icon_base = f"/_addons/{addon_package}/user_files/icons/"
    
    # Map action id -> default system icon filename
    default_icons = {
        'add': 'add.svg',
        'browse': 'browse.svg',
        'stats': 'stats.svg',
        'sync': 'sync.svg',
        'settings': 'settings.svg',
        'gamification': 'games.svg',
        'more': 'more.svg',
        'get_shared': 'get_shared.svg',
        'create_deck': 'create_deck.svg',
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
    # External entries render through sidebar_api; standard buttons get their CSS here.

    # 3. Collapsible "More" Menu Chevron
    chevron_url = f"{icon_base}chevron.svg"
    chevron_css = f"""
    details.menu-group > summary.menu-item::after {{
        content: '' !important;
        width: 15px !important;
        height: 15px !important;
        min-width: 15px !important;
        max-width: 15px !important;
        min-height: 15px !important;
        max-height: 15px !important;
        flex: 0 0 15px !important;
        margin-left: auto !important;
        flex-shrink: 0 !important;
        background-color: var(--icon-color, #888888) !important;
        -webkit-mask: url('{chevron_url}') no-repeat center / contain !important;
        mask: url('{chevron_url}') no-repeat center / contain !important;
        transition: transform 0.2s ease !important;
        opacity: 0.6 !important;
        transform-origin: center center !important;
        transform-box: fill-box !important;
        box-sizing: border-box !important;
        aspect-ratio: 1 / 1 !important;
    }}

    details.menu-group[open] > summary.menu-item::after {{
        transform: rotate(90deg) !important;
    }}
    """
    css_lines.append(chevron_css)
    
    return "<style>" + "\n".join(css_lines) + "</style>"


# --- Helper functions (copied from patcher.py for self-containment) ---

def _get_profile_initials(user_name: str) -> str:
    parts = [part for part in user_name.split() if part]
    if len(parts) >= 2:
        initials = f"{parts[0][0]}{parts[1][0]}"
    elif parts:
        initials = parts[0][0]
    else:
        initials = "?"
    return initials.upper()


def _get_profile_first_name(user_name: str) -> str:
    parts = [part for part in user_name.split() if part]
    return parts[0] if parts else "USER"


def _get_profile_pic_html(user_name: str, addon_package: str, css_class: str = "profile-pic") -> str:    
    profile_pic_filename = mw.col.conf.get("modern_menu_profile_picture", "")
    if profile_pic_filename and os.path.exists(os.path.join(mw.addonManager.addonsFolder(addon_package), "user_files", "profile", profile_pic_filename)):
        pic_url = f"/_addons/{addon_package}/user_files/profile/{profile_pic_filename}"
    else:
        pic_url = ""
    initials = html.escape(_get_profile_initials(user_name), quote=False)
    escaped_alt = html.escape(user_name, quote=True)
    if not pic_url:
        return (
            f'<span class="{css_class} profile-pic-frame">'
            f'<span class="profile-pic-fallback">{initials}</span>'
            '</span>'
        )
    escaped_pic_url = html.escape(pic_url, quote=True)
    return (
        f'<span class="{css_class} profile-pic-frame">'
        f'<span class="profile-pic-fallback" aria-hidden="true">{initials}</span>'
        f'<img src="{escaped_pic_url}" class="{css_class}-img profile-pic-image" alt="{escaped_alt}" '
        'onerror="this.onerror=null;this.style.display=\'none\';">'
        '</span>'
    )

# CSS for the ported dashboard widgets (Prep Station, Hexagon Land, Onigimon).
# Extracted from the upstream renderer, where these styles lived inline.
_PORTED_WIDGET_CSS = """
        /* Prep Station widget */
        .prep-station-widget {
            display: flex;
            flex-direction: column;
            gap: 6px;
            padding: 10px 12px 12px 12px;
            cursor: pointer;
            overflow: hidden;
            font-family: inherit;
            /* background + border-radius/width fall back here, then get
               overridden !important by the Box Color & Effect settings */
            background-color: var(--canvas-inset, #f2f2f2);
            border: 1px solid var(--border, rgba(128, 128, 128, 0.24));
            border-radius: 15px;
        }
        .prep-widget-header {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 8px;
            flex-shrink: 0;
        }
        .prep-widget-title {
            font-size: 9px;
            font-weight: 600;
            letter-spacing: .1em;
            text-transform: uppercase;
            opacity: 0.55;
        }
        .prep-widget-count {
            font-size: 9px;
            opacity: 0.45;
            margin-right: auto;
        }
        .prep-widget-empty {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            opacity: 0.45;
            font-style: italic;
        }

        /* Mini exam-card previews, echoing the Prep Station dialog's ExamCard.
           grid-template-columns is set inline per-instance to the widget's
           configured slot count, so a card only ever occupies one column's
           width even when fewer plans than slots are active. */
        .prep-plan-cards {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
            flex: 1;
            min-height: 0;
        }
        .prep-plan-card {
            min-width: 0;
            min-height: 0;
            display: flex;
            flex-direction: column;
            border-radius: 12px;
            overflow: hidden;
            background: var(--canvas-inset, #f2f2f2);
            border: 1px solid var(--border, rgba(128, 128, 128, 0.24));
        }
        .prep-card-band {
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            flex: 0 0 auto;
            padding: 6px 7px;
            min-height: 40%;
            color: #ffffff;
        }
        .prep-card-band-top {
            display: flex;
            align-items: flex-start;
            justify-content: flex-end;
        }
        .prep-card-name-row {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 4px;
            min-width: 0;
        }
        .prep-card-icon {
            font-size: 13px;
            line-height: 1;
            flex-shrink: 0;
        }
        img.prep-card-icon {
            width: 13px;
            height: 13px;
            object-fit: contain;
            display: block;
            flex-shrink: 0;
        }
        .prep-card-badge {
            font-size: 7px;
            font-weight: 700;
            white-space: nowrap;
            background: rgba(0, 0, 0, 0.35);
            padding: 2px 5px;
            border-radius: 8px;
        }
        .prep-card-name {
            font-size: 10px;
            font-weight: 700;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            letter-spacing: -0.01em;
            text-align: left;
        }
        .prep-card-body {
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            flex: 1;
            min-height: 0;
            padding: 6px 7px 7px 7px;
            gap: 4px;
        }
        .prep-card-pace {
            display: flex;
            align-items: baseline;
            gap: 3px;
            min-width: 0;
        }
        .prep-card-pace-num {
            font-size: 17px;
            font-weight: 700;
            line-height: 1;
        }
        .prep-card-pace-unit {
            font-size: 8px;
            opacity: 0.55;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .prep-card-progress {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .prep-card-progress-track {
            flex: 1;
            height: 4px;
            border-radius: 2px;
            background: var(--border, rgba(128, 128, 128, 0.25));
            overflow: hidden;
        }
        .prep-card-progress-fill {
            height: 100%;
            border-radius: 2px;
        }
        .prep-card-progress-label {
            font-size: 8px;
            opacity: 0.55;
            white-space: nowrap;
            flex-shrink: 0;
        }

        .hex-land-widget {
            display: grid;
            grid-template-columns: minmax(150px, 1fr) minmax(156px, .78fr);
            gap: 14px;
            padding: 14px;
            border-radius: 18px;
            border: 1px solid var(--border, #e0e0e0);
            background: var(--canvas-inset, #ffffff);
            color: var(--fg, #222);
            overflow: hidden;
            cursor: pointer;
        }

        .hex-land-widget.land-only {
            display: block;
            padding: 10px;
        }

        .hex-land-widget.disabled {
            display: flex;
            align-items: center;
            background: var(--canvas-inset, #ffffff);
        }

        .hex-land-preview {
            position: relative;
            min-width: 0;
            min-height: 120px;
            height: 100%;
            border-radius: 14px;
            overflow: hidden;
            background-color: var(--hl-bottom, #1597d1);
            background-image: linear-gradient(180deg, var(--hl-top, #48c0ee), var(--hl-bottom, #1597d1));
        }

        .hex-land-widget.land-only .hex-land-preview {
            min-height: 100%;
        }

        .hex-land-preview-stage {
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%) scale(var(--hl-scale, .72));
            transform-origin: center;
        }

        .hex-land-preview img,
        .hex-land-preview svg {
            position: absolute;
            user-select: none;
            -webkit-user-drag: none;
        }

        .hex-land-preview .hl-tile {
            width: 65px;
        }

        .hex-land-copy {
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 10px;
            min-width: 0;
        }

        .hex-land-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }

        .hex-land-header h3,
        .hex-land-copy h3 {
            margin: 0;
            font-size: 22px;
            line-height: 1.15;
            font-weight: 900;
            color: var(--fg, #111);
        }

        .hex-land-header button {
            width: 25px;
            height: 25px;
            border: 0;
            border-radius: 999px;
            background: #f5bf36;
            color: #3b2604;
            font-weight: 900;
            cursor: pointer;
        }

        .hex-land-stats {
            display: flex;
            flex-direction: column;
            gap: 9px;
            min-width: 0;
        }

        .hex-land-stat-row {
            display: grid;
            grid-template-columns: 36px 1fr;
            align-items: center;
            min-height: 34px;
            padding: 4px 10px 4px 6px;
            border: 1px solid var(--fg, #161616);
            border-radius: 999px;
            background: color-mix(in srgb, var(--canvas-inset, #ffffff) 92%, transparent);
            box-sizing: border-box;
            overflow: hidden;
        }

        .hex-land-stat-icon {
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }

        .hex-land-stat-sprite {
            display: block;
            max-width: 31px;
            max-height: 31px;
            object-fit: contain;
        }

        .hex-land-stat-sprite.tree {
            max-height: 34px;
        }

        .hex-land-stat-text {
            min-width: 0;
            text-align: center;
            font-size: 15px;
            line-height: 1.1;
            font-weight: 900;
            color: var(--fg, #111);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .hex-land-coin-fallback {
            width: 28px;
            height: 28px;
            border-radius: 999px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: radial-gradient(circle at 32% 28%, #fff4a8 0 18%, #f8c94d 19% 62%, #d18a19 63% 100%);
            color: #593a04;
            font-size: 9px;
            font-weight: 900;
            box-shadow: inset 0 -2px 0 rgba(89, 58, 4, .22);
        }

        .hex-land-coins {
            font-size: 18px;
            font-weight: 900;
            color: #1f6f87;
        }

        .hex-land-meta,
        .hex-land-copy p {
            margin: 0;
            color: var(--fg-subtle, #757575);
            font-size: 12px;
            line-height: 1.35;
        }

        .hex-land-mats {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: auto;
        }

        .hex-land-mats span {
            padding: 5px 7px;
            border-radius: 999px;
            background: color-mix(in srgb, #58af82 14%, transparent);
            font-size: 11px;
            font-weight: 800;
        }

        .onigimon-widget, .onigimon-widget * {
            font-family: "Silkscreen", var(--font-main), Nunito, sans-serif !important;
        }

        .onigimon-widget {
            display: flex;
            flex-direction: column;
            gap: 10px;
            padding: 14px;
            border-radius: 15px;
            border: 1px solid var(--border, #e0e0e0);
            background: var(--canvas-inset, #ffffff);
            color: var(--fg, #222);
            overflow: hidden;
            position: relative;
            cursor: pointer;
        }

        .onigimon-header,
        .onigimon-main,
        .onigimon-inventory {
            display: flex;
            align-items: center;
        }

        .onigimon-header {
            justify-content: space-between;
            gap: 10px;
        }

        .onigimon-header h3 {
            margin: 0;
            font-size: 15px;
        }

        .onigimon-body {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .onigimon-header span,
        .onigimon-info span {
            color: var(--fg-subtle, #757575);
            font-size: 12px;
        }
        
        .onigimon-ball-btn {
            width: 24px;
            height: 24px;
            display: grid;
            place-items: center;
            flex: 0 0 24px;
            border: 1px solid var(--border, #e0e0e0);
            border-radius: 999px;
            background: var(--canvas, #ffffff);
            padding: 0;
            cursor: pointer;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
            transition: all 0.2s ease;
        }

        .onigimon-ball-btn:hover {
            background: var(--accent-color, #007aff);
            border-color: var(--accent-color, #007aff);
            box-shadow: 0 4px 8px color-mix(in srgb, var(--accent-color, #007aff) 30%, transparent);
            transform: translateY(-1px);
        }

        .onigimon-ball-icon {
            width: 14px;
            height: 14px;
            display: inline-block;
            background-color: var(--fg, #222);
            mask-size: contain;
            -webkit-mask-size: contain;
            mask-repeat: no-repeat;
            -webkit-mask-repeat: no-repeat;
            mask-position: center;
            -webkit-mask-position: center;
            transition: background-color 0.2s ease;
        }

        .onigimon-ball-btn:hover .onigimon-ball-icon {
            background-color: #ffffff;
        }

        .onigimon-main {
            gap: 12px;
            min-height: 52px;
        }

        .onigimon-scene {
            position: relative;
            border: 1px solid var(--border, #e0e0e0);
            border-radius: 12px;
            padding: 10px;
            box-sizing: border-box;
            overflow: hidden;
            isolation: isolate;
        }

        .onigimon-scene::before {
            content: "";
            position: absolute;
            inset: -12px;
            background-image: var(--onigimon-scene-image, none);
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            filter: blur(var(--onigimon-scene-blur, 9px));
            transform: scale(1.05);
            opacity: var(--onigimon-scene-opacity, 0.9);
            z-index: -2;
            display: none;
        }

        .onigimon-scene-bg {
            position: absolute;
            inset: -12px;
            transform: scale(1.05);
            opacity: var(--onigimon-scene-opacity, 0.9);
            z-index: 0;
            pointer-events: none;
        }

        .onigimon-scene::after {
            content: "";
            position: absolute;
            inset: 0;
            background: color-mix(in srgb, var(--canvas-inset, #ffffff) 16%, transparent);
            z-index: 1;
        }

        .onigimon-scene > * {
            position: relative;
            z-index: 2;
        }

        .onigimon-scene > .onigimon-scene-bg {
            position: absolute;
            z-index: 0;
        }

        .onigimon-sprite {
            width: 58px;
            height: 58px;
            display: grid;
            place-items: center;
            flex: 0 0 58px;
            border-radius: 12px;
            background: color-mix(in srgb, var(--accent-color, #007aff) 10%, transparent);
        }

        .onigimon-scene .onigimon-sprite {
            background: transparent;
        }

        .onigimon-sprite img {
            width: 54px;
            height: 54px;
            object-fit: contain;
            image-rendering: pixelated;
        }

        .onigimon-placeholder {
            width: 30px;
            height: 30px;
            object-fit: contain;
        }

        .onigimon-info {
            display: grid;
            gap: 2px;
            min-width: 0;
            text-align: left;
            justify-items: start;
        }

        .onigimon-info strong {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .onigimon-meter {
            display: grid;
            grid-template-columns: 80px 40px minmax(0, 1fr);
            gap: 8px;
            align-items: center;
            font-size: 12px;
        }

        .onigimon-meter b {
            color: var(--fg, #222);
            font-weight: 800;
            text-align: right;
            font-variant-numeric: tabular-nums;
        }

        .onigimon-meter > div {
            height: 7px;
            border-radius: 999px;
            overflow: hidden;
            background: color-mix(in srgb, var(--fg, #222) 10%, transparent);
        }

        .onigimon-meter i {
            display: block;
            height: 100%;
            border-radius: inherit;
        }

        .onigimon-inventory {
            gap: 7px;
            flex-wrap: wrap;
            color: var(--fg, #222);
            margin-top: auto;
        }

        .onigimon-inventory span {
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
        }

        .onigimon-item-icon {
            width: 22px;
            height: 22px;
            object-fit: contain;
            image-rendering: pixelated;
            flex: 0 0 auto;
        }

        /* Compact 1-row Onigimon widget: just the companion over its background */
        .onigimon-widget-compact {
            padding: 8px;
            gap: 0;
        }

        .onigimon-scene-compact {
            flex: 1;
            width: 100%;
            height: 100%;
            min-height: 0;
            justify-content: center;
        }

        .onigimon-scene-compact .onigimon-sprite {
            width: 64px;
            height: 64px;
            flex: 0 0 64px;
        }

        .onigimon-scene-compact .onigimon-sprite img {
            width: 60px;
            height: 60px;
        }


"""


def _col_conf_get(key, default=None):
    try:
        return mw.col.conf.get(key, default)
    except Exception:
        return default


def _profile_background_render_parts(addon_package, include_default_image=True):
    container_style = ""
    layer_style = ""
    bg_mode = _col_conf_get("modern_menu_profile_bg_mode", "image")
    if bg_mode == "image":
        bg_image_file = _col_conf_get("modern_menu_profile_bg_image", "")
        if bg_image_file and os.path.exists(os.path.join(mw.addonManager.addonsFolder(addon_package), "user_files", "profile_bg", bg_image_file)):
            bg_url = f"/_addons/{addon_package}/user_files/profile_bg/{bg_image_file}"
        elif include_default_image:
            bg_url = f"/_addons/{addon_package}/system_files/profile_default/onigiri-bg.png"
        else:
            bg_url = ""
        container_style = "background-color: var(--profile-bg-custom-color); --profile-image-overlay-bg: transparent;"
        if bg_url:
            blur = max(0, min(100, int(_col_conf_get("modern_menu_profile_bg_blur", 0) or 0)))
            opacity_value = _col_conf_get("modern_menu_profile_bg_opacity", 50)
            opacity = max(0, min(100, int(100 if opacity_value is None else opacity_value))) / 100.0
            blur_px = blur * 0.2
            scale = 1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0
            layer_style = (
                f"background-image: url('{bg_url}'); background-size: cover; background-position: center; "
                f"filter: blur({blur_px}px); opacity: {opacity}; transform: scale({scale});"
            )
    elif bg_mode == "custom":
        container_style = "background-color: var(--profile-bg-custom-color);"
    else:
        container_style = "background-color: var(--accent-color);"
    return container_style, layer_style


def _spotify_embed_url(url: str) -> str:
    text = str(url or "").strip()
    if text.startswith("spotify:"):
        parts = text.split(":")
        if len(parts) >= 3 and parts[1] in {"track", "album", "playlist", "episode", "show"}:
            return f"https://open.spotify.com/embed/{parts[1]}/{parts[2]}?utm_source=generator"
    if not text or "spotify.com" not in text:
        return ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(text)
        parts = [part for part in parsed.path.split("/") if part]
        if parts and parts[0].startswith("intl-"):
            parts = parts[1:]
        if len(parts) >= 2 and parts[0] in {"track", "album", "playlist", "episode", "show"}:
            return f"https://open.spotify.com/embed/{parts[0]}/{parts[1]}?utm_source=generator"
    except Exception:
        return ""
    return ""


def _apple_music_embed_url(url: str) -> str:
    text = str(url or "").strip()
    if not text or "music.apple.com" not in text:
        return ""
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(text)
        host = parsed.netloc.lower()
        if host not in {"music.apple.com", "embed.music.apple.com"}:
            return ""
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 3 or parts[1] not in {"album", "song", "playlist"}:
            return ""
        return urlunparse(("https", "embed.music.apple.com", parsed.path, "", parsed.query, ""))
    except Exception:
        return ""


def _youtube_music_embed_url(url: str) -> str:
    text = str(url or "").strip()
    if not text or "music.youtube.com" not in text:
        return ""
    try:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(text)
        if parsed.netloc.lower() != "music.youtube.com" or parsed.path != "/watch":
            return ""
        video_id = (parse_qs(parsed.query).get("v") or [""])[0]
        if not re.fullmatch(r"[\w-]{6,20}", video_id):
            return ""
        return f"https://www.youtube-nocookie.com/embed/{video_id}?controls=1&modestbranding=1&rel=0"
    except Exception:
        return ""


def _music_embed_url(url: str) -> str:
    return _spotify_embed_url(url) or _apple_music_embed_url(url) or _youtube_music_embed_url(url)


def _music_link_service_label(url: str) -> str:
    text = str(url or "").lower()
    if "music.apple.com" in text:
        return "Apple Music"
    if "music.youtube.com" in text:
        return "YouTube Music"
    if "spotify.com" in text or text.startswith("spotify:"):
        return "Spotify"
    return "Music"


def _profile_sidebar_config(conf: dict) -> dict:
    profile = conf.get("onigiriProfile", {})
    if not isinstance(profile, dict):
        profile = {}
    return {
        "bio": str(profile.get("bio") or "").strip(),
        "status": str(profile.get("status") or "").strip(),
        "musicLink": str(profile.get("spotifyLink") or profile.get("musicLink") or "").strip(),
    }


def _build_profile_sidebar_html(conf: dict, addon_package: str, user_name: str, profile_pic_html: str) -> str:
    profile = _profile_sidebar_config(conf)
    bg_style, layer_style = _profile_background_render_parts(addon_package)
    bg_layer_html = f'<div class="onigiri-sidebar-profile-bg-layer" style="{layer_style}"></div>' if layer_style else ""

    bio_html = f'<p class="onigiri-sidebar-profile-bio">{html.escape(profile["bio"], quote=False)}</p>' if profile["bio"] else ""
    status_html = f'<p class="onigiri-sidebar-profile-status">{html.escape(profile["status"], quote=False)}</p>' if profile["status"] else ""
    music_link = profile["musicLink"]
    music_html = ""
    if music_link:
        embed_url = _music_embed_url(music_link)
        if embed_url:
            music_html = f"""
            <section class="onigiri-sidebar-profile-music">
                <iframe src="{html.escape(embed_url, quote=True)}" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>
            </section>
            """
        else:
            music_html = f"""
            <a class="onigiri-sidebar-profile-music-link" href="{html.escape(music_link, quote=True)}">
                <span>{html.escape(_music_link_service_label(music_link), quote=False)}</span>
                <strong>{html.escape(music_link, quote=False)}</strong>
            </a>
            """

    return f"""
    <section class="onigiri-sidebar-profile" data-profile-sidebar>
        <button type="button" class="onigiri-sidebar-profile-back" aria-label="Back" onclick="window.OnigiriProfileSidebar && OnigiriProfileSidebar.close(event)"></button>
        <div class="onigiri-sidebar-profile-cover" style="{bg_style}">
            {bg_layer_html}
        </div>
        <div class="onigiri-sidebar-profile-body">
            <div class="onigiri-sidebar-profile-avatar">{profile_pic_html}</div>
            <h2>{html.escape(user_name, quote=False)}</h2>
            {status_html}
            {bio_html}
            {music_html}
        </div>
    </section>
    """


def _get_onigiri_stat_card_html(label: str, value: str, widget_id: str) -> str:
    return f"""<div class="stat-card {widget_id}-card"><h3>{label}</h3><p>{value}</p></div>"""

# Global Cache for stats to prevent re-querying on every render frame
_DASHBOARD_STATS_CACHE = {}
_DASHBOARD_LAST_UPDATE = 0
_DASHBOARD_CACHE_TTL = 3 # 3 seconds is enough to prevent spam during animations, but keeps it fresh

# --- Dialog-open guard ---
# When any in-page dialog is open (right-click menu, ellipsis menu, icon chooser),
# automatic refreshes are suppressed. A refresh is triggered when the dialog closes.
_onigiri_ui_open = False
_onigiri_refresh_deferred = False
_onigiri_tree_refresh_deferred = False

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

    return f"""
    <div class="stat-card retention-card">
        <h3>Retention</h3>
        <div class="retention-content">
            <p>{retention_percentage:.0f}%</p>
            {star_rating_html}
        </div>
    </div>
    """

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
            return """
            <div class="onigiri-favorites-widget">
                <h3>Favorites</h3>
                <div class="favorites-placeholder">
                    No favorite decks selected.
                    <br>
                    <span>(Select decks in Edit Mode)</span>
                </div>
            </div>
            """

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
            valid_dids.append(did)
            
            # Get the short name
            short_name = deck_name.split("::")[-1]
            
            # Create a clickable link
            links_html.append(
                f"""<a class="favorite-deck-link" 
                      href=# draggable="false" onclick="return OnigiriEngine.openDeck(event, '{did}')"
                      title="Open {html.escape(deck_name, quote=True)}">
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
            return """
            <div class="onigiri-favorites-widget">
                <h3>Favorites</h3>
                <div class="favorites-placeholder">
                    No favorite decks selected.
                    <br>
                    <span>(Select decks in Edit Mode)</span>
                </div>
            </div>
            """
        
        addon_package = mw.addonManager.addonFromModule(__name__)
        star_icon_url = html.escape(_system_icon_url(addon_package, "star_filled.svg"), quote=True)
        return f"""
        <div class="onigiri-favorites-widget" style="--onigiri-favorite-star-icon: url('{star_icon_url}');">
            <h3>Favorites</h3>
            <div class="favorites-list">
                {''.join(links_html)}
            </div>
        </div>
        """
    except Exception as e:
        print(f"Onigiri: Error building favorites widget: {e}")
        import traceback
        traceback.print_exc()
        return "<div class='onigiri-favorites-widget'>Error loading favorites.</div>"
# --- END OF NEW FUNCTION ---

def _get_onigiri_restaurant_level_html() -> str:
    """
    Generates the HTML for the Restaurant Level widget.
    """
    # Invalidate cache to ensure fresh data when deck browser is rendered
    # REVERTED: Do NOT invalidate here. It causes lag on every render.
    # nook_level.manager.invalidate_daily_cache()
    
    # Get Restaurant Level Data
    rl_payload = nook_level.manager.get_progress_payload()
    if not rl_payload.get("enabled"):
        return """
        <div class="onigiri-restaurant-level-widget disabled">
            <div class="restaurant-info">
                <h3>Restaurant Level</h3>
                <p>Feature Disabled</p>
            </div>
        </div>
        """
    
    level = rl_payload.get("level", 0)
    name = rl_payload.get("name", "Restaurant Level")
    
    # Level Progress
    xp_into = rl_payload.get("xpIntoLevel", 0)
    xp_next = rl_payload.get("xpToNextLevel", 0)
    level_percent = rl_payload.get("progressFraction", 0.0) * 100
    
    if xp_next <= 0:
        xp_text = "Max Level"
    else:
        xp_text = f"{xp_into} / {xp_next} XP"

    # Theme Color
    theme_color = nook_level.manager.get_current_theme_color()
    bar_color = theme_color if theme_color else "var(--accent-color, #007bff)"
    
    # Background for expanded view
    if theme_color:
        bg_style_value = theme_color
    else:
        bg_style_value = "linear-gradient(135deg, #ff6b6b, #ffb347)"
    
    # Get Image and check if it's Santa's Coffee
    image_file = nook_level.manager.get_current_theme_image()
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
    
    shop_icon_url = _system_icon_url(addon_package, "shop.svg")
    restaurant_icon_url = _system_icon_url(addon_package, "restaurant.svg")
    
    nav_buttons_html = f"""
    <div class="rl-widget-nav-buttons">
        <button class="rl-nav-btn" onclick="event.stopPropagation(); pycmd('openTaiyakiStore');" title="Open Taiyaki Store">
            <i class="rl-nav-icon" style="--rl-nav-icon: url('{shop_icon_url}');"></i>
        </button>
        <button class="rl-nav-btn" onclick="event.stopPropagation(); pycmd('openRestaurantLevel');" title="Open Restaurant Level">
            <i class="rl-nav-icon" style="--rl-nav-icon: url('{restaurant_icon_url}');"></i>
        </button>
    </div>
    """
    
    # Get Daily Special Data
    daily_special = nook_level.manager.get_daily_special_status()
    ds_enabled = daily_special.get("enabled", False)
    ds_progress = daily_special.get("current_progress", 0)
    ds_target = daily_special.get("target", 100)
    
    ds_html = ""
    if ds_enabled:
        percent = min(100, int((ds_progress / ds_target) * 100)) if ds_target > 0 else 0
        ds_html = f"""
        <div class="daily-special-section">
            <div class="ds-header">
                <div class="ds-label">Daily Special</div>
                <div class="ds-text">{ds_progress} / {ds_target}</div>
            </div>
            <div class="ds-progress-bar">
                <div class="ds-progress-fill" style="width: {percent}%; background: {bar_color};"></div>
            </div>
        </div>
        """
    else:
        ds_html = "<div class='daily-special-section'><p class='ds-label'>No Daily Special Active</p></div>"

    return f"""
    <div class="onigiri-restaurant-level-widget {snow_class}" style="--theme-bg: {bg_style_value}; --theme-color: {bar_color}">
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
    """

# --- The Main Rendering Function ---

def render_onigiri_deck_browser(self: DeckBrowser, reuse: bool = False) -> None:
    """
    A complete replacement for Anki's DeckBrowser._renderPage.
    It builds the entire modern UI, including Onigiri and external widgets,
    into a stable CSS grid.
    """
    global _onigiri_ui_open, _onigiri_refresh_deferred
    if _onigiri_ui_open:
        # A dialog is open — defer the refresh so it fires when the dialog closes
        _onigiri_refresh_deferred = True
        return

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

    def _render_hexagon_land_widget():
        from .gamification import hexagon_land
        return hexagon_land.render_widget_html()

    def _render_learner_stats_widget():
        from . import learner_stats_widget
        return learner_stats_widget._render_widget(self, "deck_stats")

    def _render_prep_station_widget(slot_count=4):
        from . import prep_station
        return prep_station.render_widget_html(slot_count=slot_count)

    widget_generators = {
        "studied": lambda: _get_onigiri_stat_card_html("Studied", f"{cards_today} cards", "studied"),
        "time": lambda: _get_onigiri_stat_card_html("Time", f"{time_today_minutes:.1f} min", "time"),
        "pace": lambda: _get_onigiri_stat_card_html("Pace", f"{seconds_per_card:.1f} s/card", "pace"),
        "retention": _get_onigiri_retention_html,
        "heatmap": _get_onigiri_heatmap_html,
        "favorites": _get_onigiri_favorites_html, # <-- ADD THIS LINE
        "restaurant_level": _get_onigiri_restaurant_level_html,
        "onigimon": onigimon.render_widget_html,
        "hexagon_land": _render_hexagon_land_widget,
        "deck_stats": _render_learner_stats_widget,
        "prep_station": _render_prep_station_widget,
    }

    if col_count > 0:
        for widget_id, widget_config in onigiri_layout.items():
            if widget_id in widget_generators:
                pos = widget_config.get("pos", 0)
                row_span = widget_config.get("row", 1)
                col_span = widget_config.get("col", 1)
                if widget_id == "deck_stats":
                    try:
                        row_span = max(1, min(2, int(row_span)))
                    except (TypeError, ValueError):
                        row_span = 2
                    try:
                        col_span = max(1, min(2, int(col_span)))
                    except (TypeError, ValueError):
                        col_span = 1
                elif widget_id == "hexagon_land":
                    try:
                        row_span = max(1, min(4, int(row_span)))
                    except (TypeError, ValueError):
                        row_span = 2
                    try:
                        col_span = max(1, min(4, int(col_span)))
                    except (TypeError, ValueError):
                        col_span = 2

                row = pos // col_count + 1
                col = pos % col_count + 1
                style = f"grid-area: {row} / {col} / span {row_span} / span {col_span};"
                if widget_id == "prep_station":
                    widget_html = _render_prep_station_widget(slot_count=col_span)
                elif widget_id == "onigimon":
                    try:
                        onigimon_row_span = int(row_span)
                    except (TypeError, ValueError):
                        onigimon_row_span = 2
                    try:
                        onigimon_col_span = int(col_span)
                    except (TypeError, ValueError):
                        onigimon_col_span = 1
                    widget_html = onigimon.render_widget_html(row_span=onigimon_row_span, col_span=onigimon_col_span)
                else:
                    widget_html = widget_generators[widget_id]()
                if not str(widget_html or "").strip():
                    continue
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
            if "learner_stats_widget" in hook_id:
                try:
                    from . import learner_stats_widget
                    hook_html = learner_stats_widget._render_widget(self, hook_id)
                except Exception as e:
                    hook_html = f"<div style='color: red;'>Error rendering stats: {e}</div>"
            else:
                hook_html = external_widgets_data.get(hook_id)
            if hook_html:
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

    # [CHANGED] Updated CSS to force grid expansion and row height
    onigimon_css = _PORTED_WIDGET_CSS

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
            box-sizing: border-box;
            overflow: hidden;
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
        .stat-card, #onigiri-heatmap-container, .onigiri-favorites-widget, .onigimon-widget, .hex-land-widget, .prep-station-widget {{
            flex: 1;
            width: 100%;
            height: 100%;
            box-sizing: border-box;
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
        
        /* Unrestricted Sidebar resizing */
        .sidebar-left {{
            max-width: none !important;
        }}

        .main-content {{
            /* Dynamic Padding based on col_count */
            padding-top: {40 if col_count == 4 else (20 if col_count > 4 else 60)}px !important;
            padding-bottom: {40 if col_count == 4 else (20 if col_count > 4 else 60)}px !important;
            padding-left: 110px !important;
            padding-right: 40px !important;
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
            max-width: {1600 if col_count > 4 else 900}px !important;
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
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 15px 20px;
            gap: 15px;
            transition: opacity 0.2s ease;
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
            border: none !important;
            background: transparent !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            outline: none !important;
            appearance: none !important;
            -webkit-appearance: none !important;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: flex-start;
            transition: color 0.2s ease;
            color: var(--fg-subtle, #757575);
        }}
        
        .night .rl-nav-btn {{
            background: transparent !important;
            color: var(--fg-subtle, #9e9e9e);
        }}
        
        .rl-nav-btn:focus,
        .rl-nav-btn:active,
        .rl-nav-btn:focus-visible {{
            background: transparent !important;
            transform: none !important;
            border: none !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            outline: none !important;
        }}
        
        .night .rl-nav-btn:focus,
        .night .rl-nav-btn:active,
        .night .rl-nav-btn:focus-visible {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }}

        .rl-nav-btn.is-true-hover,
        .night .rl-nav-btn.is-true-hover {{
            color: var(--theme-color);
        }}
        
        .rl-nav-icon {{
            display: inline-block;
            width: 16px;
            height: 16px;
            margin-left: 4px;
            background-color: currentColor;
            mask-image: var(--rl-nav-icon);
            -webkit-mask-image: var(--rl-nav-icon);
            mask-size: contain;
            -webkit-mask-size: contain;
            mask-repeat: no-repeat;
            -webkit-mask-repeat: no-repeat;
            mask-position: center;
            -webkit-mask-position: center;
        }}
        
        /* Style for expanded view - reduce button visibility */
        .onigiri-restaurant-level-widget.expanded-view .rl-widget-nav-buttons {{
            opacity: 0.5;
        }}
    </style>
    {onigimon_css}
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
    # (The full OnigiriEngine is provided by engine.js injected via inject_menu_files.
    # engine.js correctly calls onigiriDismissOverlay('engine'), satisfying the JS
    # controller's source gate. No inline engine block is needed here.)
    onigiri_engine_js = ""
    
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
    sidebar_actions_mode = _normalize_sidebar_actions_mode(conf.get("sidebarActionsMode", "full"))

    if sidebar_actions_mode == "minimal":
        sidebar_initial_class += " sidebar-mode-minimal" if sidebar_initial_class else "sidebar-mode-minimal"
    elif sidebar_actions_mode == "compact":
        sidebar_initial_class += " sidebar-actions-compact" if sidebar_initial_class else "sidebar-actions-compact"
    else:
        sidebar_initial_class += " sidebar-actions-full" if sidebar_initial_class else "sidebar-actions-full"

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
    elif profile_bg_mode == profile_background.PROFILE_BG_MODE_GRADIENT:
        bg_style_str = profile_background.get_profile_bg_gradient_style()
    else: # accent
        bg_style_str = "background-color: var(--accent-color);"
    
    profile_pic_html_expanded = _get_profile_pic_html(user_name, addon_package)

    rl_payload = nook_level.manager.get_progress_payload()
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
            <span class="rl-chip-level">Lv {rl_payload.get('level', 0)}</span>
            <div class="rl-chip-progress">
                <div class="rl-chip-progress-fill" style="width: {fill_width}; background: var(--onigiri-profile-level-fill, currentColor);"></div>
            </div>
        </div>
        """.strip()

    profile_bar_contents = (
        f"{profile_pic_html_expanded}"
        f"<span class=\"profile-name\">{html.escape(_get_profile_first_name(user_name))}</span>"
    )
    if rl_chip:
        profile_bar_contents += rl_chip
    
    # Inject CSS for theme colors if a theme is active
    theme_css = ""
    bar_mode = mw.col.conf.get("onigiri_profile_level_bar_mode", "theme")
    if bar_mode == "custom":
        rl_theme_color = mw.col.conf.get("onigiri_profile_level_bar_custom_color", "#4CAF50")
    else:
        rl_theme_color = nook_level.manager.get_current_theme_color()

    if rl_theme_color:
        theme_css = f"""
        <style id="profile-bar-theme-colors">
            .profile-bar {{
                --onigiri-profile-level-fill: {rl_theme_color};
                --onigiri-profile-level-track: rgba({int(rl_theme_color[1:3], 16)}, {int(rl_theme_color[3:5], 16)}, {int(rl_theme_color[5:7], 16)}, 0.25);
                --onigiri-profile-level-track-night: rgba({int(rl_theme_color[1:3], 16)}, {int(rl_theme_color[3:5], 16)}, {int(rl_theme_color[5:7], 16)}, 0.35);
            }}

            .profile-bar .restaurant-level-chip .rl-chip-progress {{
                background: var(--onigiri-profile-level-track) !important;
            }}
            
            .night-mode .profile-bar .restaurant-level-chip .rl-chip-progress {{
                background: var(--onigiri-profile-level-track-night) !important;
            }}
            
            .profile-bar .restaurant-level-chip .rl-chip-progress-fill {{
                background: var(--onigiri-profile-level-fill) !important;
            }}
            
            .level-progress-bar {{
                background: {rl_theme_color} !important;
            }}
        </style>
        """
        
    # --- ADDED: Generate CSS for Action Icons ---
    action_icons_css = _generate_action_icons_css(conf, addon_package)
    theme_css += action_icons_css

    # Custom profile name color (light/dark aware), managed from Settings > Profile.
    if _col_conf_get("modern_menu_profile_name_color_enabled", False):
        name_dynamic = _col_conf_get("modern_menu_profile_name_dynamic_mode", True)
        name_light = _col_conf_get("modern_menu_profile_name_color_light", "#111827")
        name_dark = _col_conf_get("modern_menu_profile_name_color_dark", name_light) if name_dynamic else name_light
        theme_css += f"""
        <style id="profile-name-color">
            .profile-bar .profile-name {{ color: {name_light} !important; text-shadow: none !important; }}
            body.night-mode .profile-bar .profile-name {{ color: {name_dark} !important; }}
        </style>
        """

    profile_bar_html = (
        f"<div class=\"profile-bar {bg_class_str}\" style=\"{bg_style_str}\" "
        f"onclick=\"window.OnigiriProfileSidebar && OnigiriProfileSidebar.toggle(event)\">{profile_bar_contents}</div>"
    )
    profile_sidebar_html = _build_profile_sidebar_html(
        conf,
        addon_package,
        user_name,
        _get_profile_pic_html(user_name, addon_package, "onigiri-sidebar-profile-img"),
    )

    # 1. Build the dynamic sidebar HTML from the layout config
    sidebar_buttons_html = _build_sidebar_html(conf)
    
    # 2. Manually replace {profile_bar} inside the sidebar HTML string
    #    (This is necessary because {profile_bar} is one of the items in BUTTON_HTML)
    sidebar_buttons_html = sidebar_buttons_html.replace("{profile_bar}", profile_bar_html)
    
    welcome_message = f"WELCOME {user_name.upper()}" if not conf.get("hideWelcomeMessage", False) else ""
    saved_width = mw.col.conf.get("modern_menu_sidebar_width", 300)
    sidebar_style = f"width: {saved_width}px;"
    edge_toggle_left = 24 if is_collapsed else max(24, saved_width + 3)
    edge_toggle_top = 24 if is_collapsed else 39
    edge_toggle_zone_left = max(0, edge_toggle_left - (16 if is_collapsed else 28))
    edge_toggle_zone_top = max(0, edge_toggle_top - 8)
    edge_toggle_initial_style = f"left: {edge_toggle_left}px; top: {edge_toggle_top}px;"
    edge_toggle_zone_initial_style = f"left: {edge_toggle_zone_left}px; top: {edge_toggle_zone_top}px;"
    container_extra_class = ""

    _icon_mask_css = (
        'display:block;width:16px;height:16px;'
        'mask-size:contain;-webkit-mask-size:contain;'
        'mask-repeat:no-repeat;-webkit-mask-repeat:no-repeat;'
        'mask-position:center;-webkit-mask-position:center;'
        'background-color:var(--icon-color,#777);'
    )
    _ellipsis_url = _system_icon_url(addon_package, "more_circle.svg")
    ellipsis_button_html = (
        '<div class="onigiri-ellipsis-toolbar-btn" '
        'onclick="OnigiriEngine.showEllipsisMenu(this,event)" '
        'title="More options" role="button">'
        f'<i style="{_icon_mask_css}mask-image:url({_ellipsis_url});-webkit-mask-image:url({_ellipsis_url});"></i>'
        '</div>'
    ) if sidebar_actions_mode == "minimal" else ""
    organise_button_html = (
        '<button class="onigiri-organise-toolbar-btn" '
        'onclick="OnigiriEngine.showOrganiseMenu(this,event)" '
        'title="Organise decks" aria-label="Organise decks" type="button">'
        '<i class="organise-btn-icon"></i>'
        '</button>'
    )

    undo_button_html = ''

    # Build archived dropdown action list from the sidebar's visible layout
    addon_package = mw.addonManager.addonFromModule(__name__)
    layout_config = conf.get("sidebarButtonLayout", copy.deepcopy(config.DEFAULTS["sidebarButtonLayout"]))
    visible_keys = layout_config.get("visible", [])
    external_entries_dict = sidebar_api.get_sidebar_entries()

    _builtin_meta = {
        "add":          {"label": "Add",          "command": "add",                     "icon": "add.svg"},
        "browse":       {"label": "Browser",       "command": "browse",                  "icon": "browse.svg"},
        "stats":        {"label": "Stats",         "command": "stats",                   "icon": "stats.svg"},
        "sync":         {"label": "Sync",          "command": "sync",                    "icon": "sync.svg"},
        "settings":     {"label": "Settings",      "command": "openOnigiriSettings",     "icon": "settings.svg"},
        "gamification": {"label": "Onigiri Games", "command": "openGamificationSettings","icon": "games.svg"},
    }
    _more_sub = [
        {"key": "get_shared",  "label": "Get Shared",  "command": "shared",             "icon": "get_shared.svg"},
        {"key": "create_deck", "label": "Create Deck", "command": "onigiri_create_deck","icon": "create_deck.svg"},
        {"key": "import_file", "label": "Import File", "command": "import",             "icon": "import_file.svg"},
    ]

    minimal_mode_actions = []
    is_minimal_mode = sidebar_actions_mode == "minimal"

    ICON_ADD_CARD          = _system_icon_url(addon_package, "add_card.svg")
    ICON_ADD_DECK          = _system_icon_url(addon_package, "create_deck.svg")
    ICON_STAR              = _system_icon_url(addon_package, "star_outline.svg")
    ICON_MARK              = _system_icon_url(addon_package, "mark.svg")
    ICON_ARCHIVE           = _system_icon_url(addon_package, "archive.svg")
    ICON_SORT_DEFAULT      = _system_icon_url(addon_package, "sort_default.svg")
    ICON_SORT_MOST_REVIEWS = _system_icon_url(addon_package, "sort_most_reviews.svg")
    ICON_SORT_CUSTOM       = _system_icon_url(addon_package, "sort_custom.svg")

    # Utility tools for the standalone Organise toolbar button.
    _raw_sort_mode = mw.col.conf.get("onigiri_sort_mode", "")
    current_sort = mw.col.conf.get("onigiri_deck_sort", "default")
    if not mw.col.conf.get("onigiri_deck_sort") and _raw_sort_mode == "custom":
        current_sort = "custom"
    show_favorites = bool(mw.col.conf.get("onigiri_show_favorites", False))
    show_marked = bool(mw.col.conf.get("onigiri_show_marked", False))
    show_archived = bool(mw.col.conf.get(deck_tree_updater.SHOW_ARCHIVED_CONF_KEY, False))
    organise_children = [
        {"type": "section", "label": "Filter"},
        {"key": "filter_favorites", "label": "Favorites", "command": "onigiri_filter_favorites", "iconUrl": ICON_STAR,   "selected": show_favorites},
        {"key": "filter_marked",     "label": "Marked",     "command": "onigiri_filter_marked",     "iconUrl": ICON_MARK,   "selected": show_marked},
        {"key": "filter_archived",   "label": "Archived",   "command": "onigiri_filter_archived",   "iconUrl": ICON_ARCHIVE, "selected": show_archived},
        {"type": "divider"},
        {"type": "section", "label": "Sort"},
        {"key": "sort_default",       "label": "Default",      "command": "onigiri_sort:default",      "iconUrl": ICON_SORT_DEFAULT,      "selected": current_sort == "default"},
        {"key": "sort_most_reviews",  "label": "Most Reviews", "command": "onigiri_sort:most_reviews", "iconUrl": ICON_SORT_MOST_REVIEWS, "selected": current_sort == "most_reviews"},
        {"key": "sort_custom",        "label": "Custom",       "command": "onigiri_sort:custom",       "iconUrl": ICON_SORT_CUSTOM,       "selected": current_sort == "custom"},
    ]

    if is_minimal_mode:
        # Minimal mode: always show full action set regardless of visible_keys
        for key, meta in _builtin_meta.items():
            if key == "add":
                minimal_mode_actions.append({
                    "key": "add",
                    "label": "Add",
                    "iconUrl": _configured_action_icon_url(addon_package, key, meta["icon"]),
                    "group": "actions",
                    "children": [
                        {"key": "add_card", "label": "Add Card", "command": "add",                  "iconUrl": ICON_ADD_CARD},
                        {"key": "add_deck", "label": "Add Deck", "command": "onigiri_create_deck", "iconUrl": ICON_ADD_DECK},
                    ]
                })
            else:
                minimal_mode_actions.append({
                    "key": key,
                    "label": meta["label"],
                    "command": meta["command"],
                    "iconUrl": _configured_action_icon_url(addon_package, key, meta["icon"]),
                    "group": "extras" if key == "gamification" else "actions",
                })

        for sub in _more_sub:
            if sub["key"] == "create_deck":
                continue  # already shown as "Add Deck" child above
            minimal_mode_actions.append({
                "key": sub["key"],
                "label": sub["label"],
                "command": sub["command"],
                "iconUrl": _configured_action_icon_url(addon_package, sub["key"], sub["icon"]),
                "group": "extras",
            })

        for key, entry in external_entries_dict.items():
            minimal_mode_actions.append({"key": key, "label": entry.label, "command": entry.command, "iconUrl": _system_icon_url(addon_package, "info_circle.svg"), "group": "actions"})
    else:
        # Non-minimal modes: build from visible_keys
        has_more = False
        for key in visible_keys:
            if key in _builtin_meta:
                meta = _builtin_meta[key]
                minimal_mode_actions.append({
                    "key": key,
                    "label": meta["label"],
                    "command": meta["command"],
                    "iconUrl": _configured_action_icon_url(addon_package, key, meta["icon"]),
                    "group": "actions",
                })
            elif key == "more":
                has_more = True
            elif key in external_entries_dict:
                entry = external_entries_dict[key]
                minimal_mode_actions.append({"key": key, "label": entry.label, "command": entry.command, "iconUrl": _system_icon_url(addon_package, "info_circle.svg"), "group": "actions"})
        if has_more:
            for sub in _more_sub:
                minimal_mode_actions.append({
                    "key": sub["key"],
                    "label": sub["label"],
                    "command": sub["command"],
                    "iconUrl": _configured_action_icon_url(addon_package, sub["key"], sub["icon"]),
                    "group": "actions",
                })

    # 3. Use the new {sidebar_buttons} placeholder in the template
    #    and remove the old {profile_bar} placeholder.

    # Inject Config for JS
    action_icon_keys = [
        "add", "browse", "stats", "sync", "settings", "gamification", "more",
        "get_shared", "create_deck", "import_file"
    ]
    compact_icons = {}
    user_icons_dir = os.path.join(os.path.dirname(__file__), "user_files", "icons")
    for key in action_icon_keys:
        filename = mw.col.conf.get(f"modern_menu_icon_{key}", "")
        if filename and os.path.exists(os.path.join(user_icons_dir, filename)):
            compact_icons[key] = filename
        else:
            compact_icons[key] = ""
    compact_toolbar_html = '<div class="sidebar-toolbar"></div>'
    if sidebar_actions_mode == "compact":
        _compact_default_icons = {
            "add": "add.svg",
            "browse": "browse.svg",
            "stats": "stats.svg",
            "sync": "sync.svg",
            "settings": "settings.svg",
            "more": "more.svg",
            "get_shared": "get_shared.svg",
            "create_deck": "create_deck.svg",
            "import_file": "import_file.svg",
            "gamification": "games.svg",
        }

        def _compact_icon_url(action_key: str) -> str:
            filename = compact_icons.get(action_key, "")
            if filename:
                return _user_icon_url(addon_package, filename)
            return _system_icon_url(addon_package, _compact_default_icons[action_key])

        def _compact_btn_html(action_key: str, title: str, extra_classes: str = "", extra_attrs: str = "") -> str:
            icon_url = html.escape(_compact_icon_url(action_key), quote=True)
            class_attr = f"action-btn action-{action_key.replace('_', '-')}"
            if extra_classes:
                class_attr += f" {extra_classes}"
            extra_attr_text = f" {extra_attrs}" if extra_attrs else ""
            return (
                f'<div class="{class_attr}" title="{html.escape(title, quote=True)}"{extra_attr_text}>'
                f'<i class="action-icon" style="mask-image: url(\'{icon_url}\'); -webkit-mask-image: url(\'{icon_url}\');"></i>'
                '</div>'
            )

        compact_toolbar_html = (
            '<div class="sidebar-toolbar">'
            '<div class="toolbar-group-primary">'
            f'{_compact_btn_html("add", "Add")}'
            f'{_compact_btn_html("browse", "Browser")}'
            f'{_compact_btn_html("stats", "Stats")}'
            f'{_compact_btn_html("sync", "Sync")}'
            '</div>'
            '<div class="toolbar-group-secondary">'
            f'{_compact_btn_html("settings", "Settings")}'
            f'{_compact_btn_html("get_shared", "Get Shared", "more-item", f"data-command=\"shared\" data-label=\"Get Shared\" data-icon-url=\"{html.escape(_compact_icon_url("get_shared"), quote=True)}\"")}'
            f'{_compact_btn_html("create_deck", "Create Deck", "more-item", f"data-command=\"onigiri_create_deck\" data-label=\"Create Deck\" data-icon-url=\"{html.escape(_compact_icon_url("create_deck"), quote=True)}\"")}'
            f'{_compact_btn_html("import_file", "Import File", "more-item", f"data-command=\"import\" data-label=\"Import File\" data-icon-url=\"{html.escape(_compact_icon_url("import_file"), quote=True)}\"")}'
            f'{_compact_btn_html("gamification", "Onigiri Games", "more-item", f"data-command=\"openGamificationSettings\" data-label=\"Onigiri Games\" data-icon-url=\"{html.escape(_compact_icon_url("gamification"), quote=True)}\"")}'
            f'{_compact_btn_html("more", "More")}'
            '</div>'
            '</div>'
        )
    sidebar_edge_toggle_class = "always-visible" if conf.get("alwaysShowSidebarCollapseButton", False) else ""

    # Resolve deck indentation mode to a concrete px step
    indent_mode = conf.get("deck_indentation_mode", "default")
    if indent_mode == "smaller":
        deck_indent_step = 10
    elif indent_mode == "bigger":
        deck_indent_step = 40
    elif indent_mode == "custom":
        deck_indent_step = int(conf.get("deck_indentation_custom_px", 20))
    else:
        deck_indent_step = 20

    js_config = {
        "sidebarActionsMode": sidebar_actions_mode,
        "addonPackage": addon_package,
        "compactIcons": compact_icons,
        "minimalModeActions": minimal_mode_actions,
        "organiseActions": organise_children,
        "deckIndentStep": deck_indent_step,
    }
    
    # Get Sync Status
    sync_status = patcher.get_sync_status()

    # Deck marks (coloured dots) — injected so context menu can read current state
    deck_marks = dict(mw.col.conf.get("onigiri_deck_marks", {}))

    # Create JS Injection Script + ellipsis dropdown CSS
    js_injection = f"""
    <script>
        window.ONIGIRI_CONFIG = {json.dumps(js_config)};
        window.ONIGIRI_SYNC_STATUS = "{sync_status}";
        window.ONIGIRI_DECK_MARKS  = {json.dumps(deck_marks)};
    </script>
    <style>
        .onigiri-ellipsis-toolbar-btn {{
            position: relative;
            width: 24px;
            height: 24px;
            background: none !important;
            border: none !important;
            border-radius: var(--onigiri-sidebar-header-radius, 8px);
            outline: none !important;
            cursor: pointer;
            padding: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--icon-color, #555);
            line-height: 0;
            user-select: none;
            opacity: 0.8;
            transition: opacity 0.15s;
        }}
        .sidebar-left .sidebar-toolbar .ellipsis-btn,
        .sidebar-left .sidebar-toolbar .onigiri-ellipsis-toolbar-btn,
        .sidebar-left:not(.sidebar-mode-minimal) .sidebar-top-right-controls > .onigiri-ellipsis-toolbar-btn {{
            display: none !important;
            visibility: hidden !important;
            pointer-events: none !important;
        }}
        .sidebar-left.sidebar-mode-minimal .sidebar-top-right-controls > .onigiri-ellipsis-toolbar-btn {{
            display: flex !important;
            visibility: visible !important;
            pointer-events: auto !important;
        }}
        #deck-list-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            margin-left: 0;
        }}
        #deck-list-header h2 {{
            flex: 0 0 auto;
            margin-left: 10px;
            transition: opacity 0.15s ease;
        }}
        #deck-list-header h2.deck-focus-label {{
            cursor: pointer;
            user-select: none;
            border-radius: 6px;
            padding: 0 2px;
            outline: none;
            transition: color 0.15s ease, opacity 0.15s ease;
        }}
        #deck-list-header h2.deck-focus-label:hover,
        #deck-list-header h2.deck-focus-label:focus-visible {{
            color: color-mix(in srgb, var(--fg, currentColor) 82%, black 18%);
            opacity: 1;
        }}
        .night-mode #deck-list-header h2.deck-focus-label:hover,
        .night-mode #deck-list-header h2.deck-focus-label:focus-visible {{
            color: color-mix(in srgb, var(--fg, currentColor) 78%, white 22%);
            opacity: 1;
        }}
        .deck-focus-btn,
        .deck-header-focus-btn,
        .sidebar-left .deck-focus-btn,
        .sidebar-left .deck-header-focus-btn,
        .sidebar-top-right-controls .deck-focus-btn {{
            display: none !important;
            width: 0 !important;
            min-width: 0 !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            pointer-events: none !important;
        }}
        .sidebar-left.sidebar-actions-full.deck-focus-mode #deck-list-header h2 {{
            margin-left: 10px;
        }}
        .sidebar-top-right-controls {{
            --onigiri-sidebar-header-radius: 8px;
            position: static;
            z-index: 11;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 0;
            margin-left: auto;
        }}
        .sidebar-left.sidebar-actions-full {{
            padding-top: 15px !important;
        }}
        .sidebar-left:not(.sidebar-actions-full):not(.sidebar-mode-minimal) {{
            padding-top: 15px !important;
        }}
        .sidebar-left:not(.deck-focus-mode) .profile-bar {{
            margin-top: 0 !important;
            margin-bottom: 8px !important;
        }}
        .sidebar-left.sidebar-actions-compact:not(.deck-focus-mode) .profile-bar {{
            margin-top: 6px !important;
            margin-bottom: 16px !important;
        }}
        .sidebar-left.sidebar-actions-full:not(.deck-focus-mode) .profile-bar {{
            margin-top: 10px !important;
            margin-bottom: 15px !important;
        }}
        .sidebar-left.sidebar-mode-minimal:not(.deck-focus-mode) .profile-bar {{
            margin-top: 4px !important;
            margin-bottom: 10px !important;
        }}
        .sidebar-left:not(.deck-focus-mode) #deck-list-header {{
            margin-top: 14px;
        }}
        .sidebar-left:not(.deck-focus-mode):not(.sidebar-actions-full) #deck-list-header {{
            margin-top: 4px !important;
        }}
        .sidebar-left.sidebar-actions-compact #deck-list-header {{
            margin-top: 26px !important;
        }}
        .sidebar-left.sidebar-actions-compact:not(.deck-focus-mode) #deck-list-header {{
            margin-top: 40px !important;
        }}
        .sidebar-left.sidebar-actions-compact.deck-focus-mode #deck-list-header {{
            margin-top: 12px !important;
        }}
        .sidebar-actions-full .sidebar-expanded-content > .sidebar-welcome-heading:empty,
        .sidebar-actions-compact .sidebar-expanded-content > .sidebar-welcome-heading:empty {{
            display: none;
        }}
        .sidebar-welcome-heading {{
            margin-left: 10px;
        }}
        .onigiri-ellipsis-toolbar-btn:hover,
        .onigiri-ellipsis-toolbar-btn.is-open {{
            opacity: 1;
        }}

        #onigiri-ellipsis-menu,
        #onigiri-organise-menu,
        #onigiri-collapsed-more-menu {{
            z-index: 99999;
            min-width: 210px;
            border-radius: 12px;
            padding: 5px;
            background: var(--canvas-overlay);
            border: 1px solid var(--border);
            box-shadow: 0 6px 24px rgba(0,0,0,0.15);
            will-change: transform;
            backface-visibility: hidden;
            -webkit-backface-visibility: hidden;
            transform: translateZ(0);
        }}
        .onigiri-ellipsis-item {{
            position: relative;
            display: flex;
            align-items: center;
            gap: 11px;
            padding: 9px 12px;
            cursor: pointer;
            font-size: 13px;
            color: var(--fg);
            border-radius: 8px;
            transition: background 0.1s;
        }}
        .onigiri-ellipsis-item:hover {{
            background: var(--canvas-inset);
        }}
        .onigiri-ellipsis-item .icon {{
            width: 16px;
            height: 16px;
            min-width: 16px;
            background-color: var(--fg-subtle, var(--fg));
            display: inline-block;
            flex-shrink: 0;
        }}
        .onigiri-ellipsis-divider {{
            border: none;
            border-top: 1px solid var(--border);
            margin: 4px 0;
        }}
        #onigiri-ellipsis-submenu {{
            z-index: 100000;
            min-width: 180px;
            border-radius: 12px;
            padding: 5px;
            background: var(--canvas-overlay);
            border: 1px solid var(--border);
            box-shadow: 0 6px 24px rgba(0,0,0,0.15);
            will-change: transform;
            backface-visibility: hidden;
            -webkit-backface-visibility: hidden;
            transform: translateZ(0);
        }}
        .has-submenu {{
            position: relative;
        }}
        .submenu-chevron {{
            margin-left: auto;
            padding-left: 8px;
            font-size: 16px;
            line-height: 1;
            color: var(--fg-subtle, var(--fg));
            flex-shrink: 0;
        }}
        #onigiri-ctx-menu {{
            z-index: 99999;
            min-width: 200px;
            border-radius: 12px;
            padding: 5px;
            background: var(--canvas-overlay);
            border: 1px solid var(--border);
            box-shadow: 0 6px 24px rgba(0,0,0,0.15);
            will-change: transform;
            backface-visibility: hidden;
            -webkit-backface-visibility: hidden;
            transform: translateZ(0);
        }}
        #onigiri-ctx-menu .onigiri-ellipsis-item,
        #onigiri-mark-submenu .onigiri-ellipsis-item {{
            padding: 7px 11px;
        }}
        .item-danger {{
            color: var(--fg);
        }}
        .item-danger:hover {{
            background: rgba(192, 48, 48, 0.12) !important;
            color: #c03535 !important;
        }}
        .item-danger:hover .icon {{
            background-color: #c03535 !important;
            color: #c03535 !important;
        }}
        .ctx-icon {{
            width: 16px;
            height: 16px;
            min-width: 16px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            color: var(--fg-subtle, var(--fg));
        }}
        .item-danger:hover .ctx-icon {{
            color: #c03535 !important;
            background-color: #c03535 !important;
        }}
        /* Archived mode keeps controls in fixed slots so refreshes do not jump. */
        .sidebar-mode-minimal .sidebar-toolbar {{
            display: none !important;
            visibility: hidden !important;
            pointer-events: none !important;
        }}
        .sidebar-mode-minimal .sidebar-expanded-content > .sidebar-welcome-heading:empty {{
            display: none;
        }}
        .sidebar-mode-minimal .profile-bar {{
            margin-top: 10px;
            margin-bottom: 10px;
        }}
        .sidebar-left.sidebar-mode-minimal {{
            padding: 15px 15px 0 15px !important;
        }}
        .sidebar-left.sidebar-mode-minimal.deck-focus-mode {{
            padding-top: 15px !important;
        }}
        .sidebar-mode-minimal .sidebar-expanded-content {{
            display: flex;
            flex-direction: column;
        }}
        .sidebar-mode-minimal #deck-list-header {{
            margin-top: 0;
            margin-left: 0;
            padding-right: 0;
        }}
        .sidebar-mode-minimal #deck-list-header h2 {{
            margin-left: 10px;
        }}
        .sidebar-left.sidebar-mode-minimal.deck-focus-mode #deck-list-container {{
            margin-top: 8px;
        }}
        .ellipsis-section-label {{
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--fg-subtle, var(--fg));
            padding: 6px 12px 2px;
            opacity: 0.55;
            cursor: default;
            user-select: none;
        }}
    </style>
    """
    
    final_body = custom_body_template \
        .replace("{tree}", tree_html) \
        .replace("{stats}", stats_block_html + theme_css + js_injection) \
        .replace("{container_extra_class}", container_extra_class) \
        .replace("{sidebar_initial_class}", sidebar_initial_class) \
        .replace("{sidebar_style}", sidebar_style) \
        .replace("{welcome_message}", welcome_message) \
        .replace("{sidebar_buttons}", sidebar_buttons_html) \
        .replace("{profile_sidebar}", profile_sidebar_html) \
        .replace("{organise_button}", organise_button_html) \
        .replace("{ellipsis_button}", ellipsis_button_html) \
        .replace("{undo_button}", undo_button_html) \
        .replace("{sidebar_edge_toggle_zone_class}", sidebar_edge_toggle_class) \
        .replace("{sidebar_edge_toggle_class}", sidebar_edge_toggle_class) \
        .replace("{sidebar_edge_toggle_zone_style}", edge_toggle_zone_initial_style) \
        .replace("{sidebar_edge_toggle_style}", edge_toggle_initial_style) \
        .replace("{compact_toolbar_html}", compact_toolbar_html) \
        .replace("{system_icon_base}", f"/_addons/{addon_package}/system_files/system_icons/")
    
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
