# Onigiri's dedicated Deck Browser Rendering Engine

import html
import json
import os
from urllib.parse import quote as quote_url_component
from dataclasses import dataclass
from datetime import date, datetime
from aqt import mw
from . import patcher
from ..integrations import fsrs_helper_integration
from aqt.deckbrowser import DeckBrowser, RenderDeckNodeContext
from anki.decks import DeckId
from ..core import config
from ..core.study_tool_visibility import TOOL_IDS, tool_visible
from . import heatmap
from ..api import sidebar as sidebar_api
from ..decks import tree_updater as deck_tree_updater
from .templates import custom_body_template
from ..core.translations import tr
import copy
import re

DECKLINE_ADDON_ID = "1517382883"
DECKLINE_HOOK_MARKERS = (DECKLINE_ADDON_ID, "deckline")
SHIGE_LEADERBOARD_ADDON_ID = "175794613"
SHIGE_LEADERBOARD_HOOK_MARKERS = (
    SHIGE_LEADERBOARD_ADDON_ID,
    "lb_on_homescreen.on_deck_browser_will_render_content",
)

POKEMON_TYPE_COLORS = {
    "bug": ("#91A119", "#FFFFFF"),
    "dark": ("#624D4E", "#FFFFFF"),
    "dragon": ("#5060E1", "#FFFFFF"),
    "electric": ("#FAC000", "#302800"),
    "fairy": ("#EF70EF", "#3D173D"),
    "fighting": ("#FF8000", "#3D1E00"),
    "fire": ("#E62829", "#FFFFFF"),
    "flying": ("#81B9EF", "#17314A"),
    "ghost": ("#704170", "#FFFFFF"),
    "grass": ("#3FA129", "#FFFFFF"),
    "ground": ("#915121", "#FFFFFF"),
    "ice": ("#3DCEF3", "#10343D"),
    "normal": ("#9FA19F", "#222322"),
    "poison": ("#9141CB", "#FFFFFF"),
    "psychic": ("#EF4179", "#FFFFFF"),
    "rock": ("#AFA981", "#29281D"),
    "steel": ("#60A1B8", "#142C34"),
    "water": ("#2980EF", "#FFFFFF"),
}


def _nook_level():
    from ..gamification import nook_level

    return nook_level


def _hexagon_land():
    from ..gamification import hexagon_land

    return hexagon_land


def _mochi_messages():
    from ..gamification import mochi_messages

    return mochi_messages


def _onigimon():
    from ..gamification import onigimon

    return onigimon


def _learner_stats_widget():
    from . import learner_stats_widget

    return learner_stats_widget


def _prep_station():
    from ..study_tools import prep_station

    return prep_station


def _hashi_notes():
    from ..study_tools import hashi_notes

    return hashi_notes


def _ready_to_go():
    from ..study_tools import ready_to_go

    return ready_to_go


def _is_deck_stats_widget_id(widget_id: str) -> bool:
    """Whether an Organize tile is the original or a copied Deck Stats widget."""
    widget_id = str(widget_id or "")
    return widget_id == "deck_stats" or bool(re.fullmatch(r"deck_stats_[1-9]\d*", widget_id))


def _is_deckline_hook_id(hook_id: str) -> bool:
    normalized = str(hook_id or "").lower()
    return any(marker in normalized for marker in DECKLINE_HOOK_MARKERS)


def _is_shige_leaderboard_hook_id(hook_id: str) -> bool:
    normalized = str(hook_id or "").lower()
    return all(marker.lower() in normalized for marker in SHIGE_LEADERBOARD_HOOK_MARKERS)


def _is_ankimon_team_hook_id(hook_id: str) -> bool:
    """Whether *hook_id* is Ankimon's legacy deck/overview sprite grid."""
    return "overview_team" in str(hook_id or "").lower()


def _layout_item_ids(layout_section) -> set[str]:
    if isinstance(layout_section, dict):
        return {str(key) for key in layout_section.keys()}
    if isinstance(layout_section, (list, tuple, set)):
        return {str(value) for value in layout_section}
    return set()


def _normalize_external_layout(external_layout: dict) -> tuple[dict, object]:
    if not isinstance(external_layout, dict):
        return {}, {}
    if "grid" not in external_layout and "archive" not in external_layout:
        return dict(external_layout), {}
    grid_config = external_layout.get("grid", {})
    archive_config = external_layout.get("archive", {})
    return (dict(grid_config) if isinstance(grid_config, dict) else {}, archive_config)


def _render_registered_bento_home(hook_id: str) -> str:
    """Render a Bento widget that registered a home callback.

    Most external widgets arrive through Anki's deck-browser hook. Bento
    widgets may be registered after that hook list is captured, however, so
    the callback is a stable fallback for a grid entry that is already known
    to Onigiri. It is intentionally optional and has no effect on add-ons
    using the traditional hook path.
    """
    try:
        from ..api import bento as bento_api

        widgets = bento_api.get_bento_widgets()
        if not isinstance(widgets, dict):
            return ""
        for widget in widgets.values():
            if not isinstance(widget, dict) or widget.get("hook_id") != hook_id:
                continue
            renderer = widget.get("home_render_callback")
            if callable(renderer):
                return str(renderer() or "")
    except Exception as exc:
        return f"<div style='color: red;'>Error rendering Bento widget: {html.escape(str(exc))}</div>"
    return ""


def render_ankimon_team_widget_html(
    row_span: int = 2,
    col_span: int = 1,
    surface: str = "menu",
) -> str:
    """Render Ankimon companions with Onigiri's lightweight widget system.

    Ankimon's own ``poke-grid`` embeds a complete card theme and fixed 120px
    sprites. This adapter reads the same bridge data but owns all markup and
    layout, keeping the team sharp and inside its assigned Onigiri cell.
    """
    try:
        manager = _onigimon().manager
        manager.sync_active_companion_from_ankimon()
        roster = list(manager.get_team_companions())
        active_id = str(manager.load().active_companion_id or "")
    except Exception:
        return ""

    if not roster:
        return ""

    if surface == "overview":
        # Preserve the exact team order supplied by Ankimon.
        selected = roster
    else:
        configured_ids = (config.get_config_readonly().get("onigimon", {}) or {}).get(
            "menu_pokemon_ids", []
        )
        if not isinstance(configured_ids, list):
            configured_ids = []
        selected_ids = {str(pokemon_id) for pokemon_id in configured_ids if pokemon_id}

        selected = [
            pokemon for pokemon in roster
            if str(pokemon.get("ankimon_id", "")) in selected_ids
        ]
        # No pins means "the whole Ankimon team". Pins remain an optional way
        # to make a deliberately smaller Main Menu lineup.
        if not selected and not selected_ids:
            selected = roster
    if not selected:
        return ""

    try:
        row_span = max(1, min(4, int(row_span)))
    except (TypeError, ValueError):
        row_span = 2
    try:
        col_span = max(1, min(4, int(col_span)))
    except (TypeError, ValueError):
        col_span = 1

    # A Pokémon team has at most six members. Never truncate it based on the
    # widget footprint—the internal responsive grid is responsible for fitting
    # all members into narrow or short placements.
    max_items = 6
    cards = []
    for pokemon in selected[:max_items]:
        name = html.escape(str(manager.companion_display_name(pokemon) or "Pokémon"))
        try:
            level = max(1, int(pokemon.get("level", 1) or 1))
        except (TypeError, ValueError):
            level = 1
        sprite_urls = manager.sprite_urls_for_companion(pokemon, motion="static")
        sprite = html.escape(str(sprite_urls[0]), quote=True) if sprite_urls else ""
        sprite_html = (
            f'<img src="{sprite}" alt="" draggable="false">'
            if sprite else '<span class="onigiri-ankimon-team-initial">?</span>'
        )
        type_badges = []
        raw_types = pokemon.get("types", [])
        if not isinstance(raw_types, list):
            raw_types = []
        for raw_type in raw_types[:2]:
            pokemon_type = str(raw_type or "").strip().lower()
            if not pokemon_type:
                continue
            type_bg, type_fg = POKEMON_TYPE_COLORS.get(
                pokemon_type, ("#8A8D91", "#FFFFFF")
            )
            type_badges.append(
                '<span class="onigiri-ankimon-team-type" '
                f'style="--pokemon-type-bg:{type_bg};--pokemon-type-fg:{type_fg}">'
                f'{html.escape(pokemon_type.title())}</span>'
            )
        types_html = (
            '<span class="onigiri-ankimon-team-types">'
            + "".join(type_badges)
            + "</span>"
            if type_badges else ""
        )
        cards.append(f"""
            <button class="onigiri-ankimon-team-member" type="button"
                    title="{name} · Lv. {level}"
                    onclick="pycmd('openOnigimonCare');">
                <span class="onigiri-ankimon-team-sprite">{sprite_html}</span>
                <span class="onigiri-ankimon-team-name">{name}</span>
                <span class="onigiri-ankimon-team-level">Lv. {level}</span>
                {types_html}
            </button>
        """)

    widget_class = "onigiri-ankimon-team-overview" if surface == "overview" else ""
    return f"""
        <section class="onigiri-ankimon-team-widget {widget_class}"
                 aria-label="Ankimon team">
            <div class="onigiri-ankimon-team-head">
                <span>{html.escape(tr("ankimon_team_widget_title", "Pokémon"))}</span><em>{len(selected[:max_items])}</em>
            </div>
            <div class="onigiri-ankimon-team-list">{''.join(cards)}</div>
        </section>
    """


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


def _col_conf_get(key, default=None):
    """Read collection config without triggering Anki 26 deprecation warnings."""
    return config.get_collection_config(key, default)


def _col_conf_set(key, value) -> None:
    """Write collection config using the modern API when available."""
    config.set_collection_config(key, value)


# --- ADDED: Button HTML definitions ---
BUTTON_HTML = {
    "profile": "{profile_bar}", # This is a placeholder for the dynamic profile bar
    "add": """
        <div class="menu-item action-add" onclick="pycmd('add')">
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
    "get_shared": """
        <div class="menu-item action-get-shared" onclick="pycmd('shared')">
            <i class="icon"></i>
            <span>{tr("get_shared")}</span>
        </div>
    """,
    "create_deck": """
        <div class="menu-item action-create-deck" onclick="pycmd('onigiri_create_deck')">
            <i class="icon"></i>
            <span>{tr("create_deck")}</span>
        </div>
    """,
    "import_file": """
        <div class="menu-item action-import-file" onclick="pycmd('import')">
            <i class="icon"></i>
            <span>{tr("import_file")}</span>
        </div>
    """,
}


MORE_ACTION_IDS = ("get_shared", "create_deck", "import_file")


def _build_more_menu_html(action_ids: list[str]) -> str:
    """Render More with only the actions assigned to its layout bucket."""
    items = "".join(
        BUTTON_HTML[action_id]
        for action_id in action_ids
        if action_id in MORE_ACTION_IDS
    )
    return f"""
        <details class="menu-group">
            <summary class="menu-item action-more">
                <i class="icon"></i>
                <span>{tr("more")}</span>
            </summary>
            <div class="menu-group-items">
                {items}
            </div>
        </details>
    """


COLLAPSED_ACTIONS = {
    "add": ("add", "add", "Add"),
    "browse": ("browse", "browse", "Browse"),
    "stats": ("stats", "stats", "Stats"),
    "sync": ("sync", "sync", "Sync"),
    "settings": ("openOnigiriSettings", "settings", "Settings"),
    "gamification": (
        "openGamificationSettings",
        "onigiri_games",
        "Onigiri Games",
    ),
    "more": ("", "more", "More"),
    "get_shared": ("shared", "get_shared", "Get Shared"),
    "create_deck": ("onigiri_create_deck", "create_deck", "Create Deck"),
    "import_file": ("import", "import_file", "Import File"),
}


def _build_archived_home_button(conf: dict, addon_package: str) -> str:
    """Render the Home menu trigger when sidebar actions are hidden.

    Keeping this in the initial HTML makes the control available before (and
    independently of) ``injector.js``. That is required by Shima, which does
    not load the Classic sidebar injector, and also avoids timing failures in
    Classic's deck header.
    """
    if conf.get("sidebarActionsMode", "list") != "archived":
        return ""

    label = html.escape(tr("home", "Home"), quote=True)
    icon_markup = _sidebar_header_icon_markup(
        "modern_menu_icon_header_home", "home.svg", "home-btn-icon", addon_package
    )
    return f"""
        <button id="onigiri-home-toolbar-btn" class="deck-header-btn"
                type="button" title="{label}" aria-label="{label}"
                onclick="OnigiriEngine.showHomeMenu(this, event)">
            {icon_markup}
        </button>
    """.strip()


def _sidebar_header_icon_markup(field_id: str, fallback: str, css_class: str,
                                addon_package: str) -> str:
    """Render a Settings Web icon choice in one of the deck-header controls."""
    value = str(_col_conf_get(field_id, "") or f"system:{fallback}")
    if value.startswith("emoji:"):
        emoji = html.escape(value[len("emoji:"):])
        return (
            f'<span class="deck-header-emoji-icon {css_class}" aria-hidden="true" '
            f'style="display:inline-flex;width:15px;height:15px;flex:0 0 15px;'
            f'align-items:center;justify-content:center;background:none;'
            f'font-size:14px;line-height:1">{emoji}</span>'
        )

    addon_dir = os.path.dirname(os.path.dirname(__file__))
    package_url = quote_url_component(addon_package, safe="")
    if value.startswith("system:"):
        filename = os.path.basename(value[len("system:"):])
        protected_path = os.path.join(
            addon_dir, "system_files", "system_icons", "unavailable_for_users", filename
        )
        icon_dir = "unavailable_for_users" if os.path.exists(protected_path) else "available_for_users"
        icon_url = (
            f"/_addons/{package_url}/system_files/system_icons/{icon_dir}/"
            f"{quote_url_component(filename, safe='')}"
        )
    else:
        filename = os.path.basename(value)
        icon_url = f"/_addons/{package_url}/user_files/icons/{quote_url_component(filename, safe='')}"

    style = (
        f'display:block;width:15px;height:15px;flex:0 0 15px;'
        f'background-color:currentColor;mask-position:center;mask-size:contain;'
        f'mask-repeat:no-repeat;-webkit-mask-position:center;'
        f'-webkit-mask-size:contain;-webkit-mask-repeat:no-repeat;'
        f'mask-image:url("{icon_url}");'
        f'-webkit-mask-image:url("{icon_url}");'
    )
    # The CSS url() quotes must be escaped for the enclosing HTML attribute.
    # Otherwise the browser parses four empty masks and the buttons disappear.
    return f'<i class="{css_class}" aria-hidden="true" style="{html.escape(style, quote=True)}"></i>'


def _build_hidden_ready_marker(addon_package: str) -> str:
    """Show one Ready to Go marker in the deck header when its sidebar is hidden."""
    if _col_conf_get("modern_menu_ready_layout_mode", "list") != "hidden":
        return ""

    label = html.escape(
        str(_col_conf_get("modern_menu_ready_title", "Ready to go") or "Ready to go"),
        quote=True,
    )
    icon_markup = _sidebar_header_icon_markup(
        "modern_menu_icon_ready_section", "lucide-zap.svg",
        "ready-toolbar-icon", addon_package,
    )
    return f"""
        <button id="onigiri-ready-toolbar-marker" class="deck-header-btn"
                type="button" aria-label="{label}" title="{label}"
                onclick="OnigiriEngine.showReadyMenu(this, event)">
            {icon_markup}
        </button>
    """.strip()

def _collapsed_action_button(
    action_id: str,
    command: str,
    label: str,
    *,
    more_item: bool = False,
) -> str:
    """Server-render one toolbar action so collapsed mode never depends on JS."""
    safe_id = html.escape(action_id, quote=True)
    safe_label = html.escape(label, quote=True)
    classes = f"action-btn action-{safe_id}"
    if more_item:
        classes += " more-item"
    if action_id == "more":
        click = (
            "event.stopPropagation();"
            "this.classList.toggle('more-expanded')"
        )
    else:
        safe_command = html.escape(command, quote=True)
        click = f"event.stopPropagation();pycmd('{safe_command}')"
    return (
        f'<div class="{classes}" role="button" tabindex="0" '
        f'title="{safe_label}" aria-label="{safe_label}" '
        f'onclick="{click}" '
        "onkeydown=\"if(event.key==='Enter'||event.key===' '){"
        "event.preventDefault();this.click()}\">"
        '<i class="action-icon" aria-hidden="true"></i>'
        "</div>"
    )


def _build_collapsed_toolbar_html(layout_config: dict) -> str:
    """Render visible actions in their saved order inside the Actions section."""
    raw_visible = layout_config.get("visible", [])
    visible = raw_visible if isinstance(raw_visible, list) else []
    raw_archived = layout_config.get("archived", [])
    archived_values = raw_archived if isinstance(raw_archived, list) else []
    archived = {str(value) for value in archived_values}
    raw_more = layout_config.get("more", list(MORE_ACTION_IDS))
    more_values = raw_more if isinstance(raw_more, list) else list(MORE_ACTION_IDS)
    more_ids = []
    for value in more_values:
        action_id = str(value)
        if (action_id in MORE_ACTION_IDS and action_id not in archived
                and action_id not in more_ids):
            more_ids.append(action_id)
    if visible:
        action_ids = []
        for value in visible:
            action_id = str(value)
            if (
                action_id in COLLAPSED_ACTIONS
                and action_id not in archived
                and action_id not in more_ids
                and action_id not in action_ids
            ):
                action_ids.append(action_id)
    else:
        action_ids = [
            action_id
            for action_id in COLLAPSED_ACTIONS
            if action_id not in MORE_ACTION_IDS
            if action_id not in archived
        ]
    if not action_ids:
        return ""

    buttons = []
    for action_id in action_ids:
        command, translation_key, fallback = COLLAPSED_ACTIONS[action_id]
        buttons.append(
            _collapsed_action_button(
                action_id,
                command,
                tr(translation_key, fallback),
            )
        )
        if action_id == "more":
            for item_id in more_ids:
                item_command, item_key, item_fallback = COLLAPSED_ACTIONS[item_id]
                buttons.append(
                    _collapsed_action_button(
                        item_id,
                        item_command,
                        tr(item_key, item_fallback),
                        more_item=True,
                    )
                )
    return (
        '<div class="sidebar-toolbar sidebar-actions-inline" '
        'aria-label="Actions">'
        f'{"".join(buttons)}'
        "</div>"
    )


# --- ADDED: Sidebar HTML builder function ---
def _build_sidebar_html(conf: dict) -> str:
    """
    Builds the sidebar HTML content based on the user's saved layout.
    """
    layout_config = conf.get(
        "sidebarButtonLayout",
        copy.deepcopy(config.DEFAULTS["sidebarButtonLayout"]),
    )
    if conf.get("sidebarActionsMode", "list") == "collapsed":
        return _build_collapsed_toolbar_html(layout_config)

    visible_keys = layout_config.get("visible", [])
    raw_more = layout_config.get("more", list(MORE_ACTION_IDS))
    more_keys = raw_more if isinstance(raw_more, list) else list(MORE_ACTION_IDS)
    raw_archived = layout_config.get("archived", [])
    archived = {str(key) for key in raw_archived} if isinstance(raw_archived, list) else set()
    more_ids = []
    for key in more_keys:
        action_id = str(key)
        if (action_id in MORE_ACTION_IDS and action_id not in archived
                and action_id not in more_ids):
            more_ids.append(action_id)
    more_id_set = set(more_ids)
    external_entries = sidebar_api.get_sidebar_entries()
    
    # --- MODIFICATION START: Sidebar Actions Mode Logic ---
    action_buttons = {
        "add", "browse", "stats", "sync", "settings", "gamification",
        "more", *MORE_ACTION_IDS,
    }
    # Default to "list" if not set
    actions_mode = conf.get("sidebarActionsMode", "list")
    
    html_parts = []
    for key in visible_keys:
        # Profile now has its own reorderable section and template slot.
        if key == "profile":
            continue
        # If this key is one of our special action buttons...
        if key in action_buttons:
            # Only render it in the list if mode is "list"
            if actions_mode == "list":
                if key == "more":
                    html_parts.append(_build_more_menu_html(more_ids))
                elif key in BUTTON_HTML and key not in more_id_set:
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


def _sidebar_section_order() -> list[str]:
    """Normalized top-to-bottom order for Classic's visible sidebar blocks."""
    known = ("profile", "actions", "ready_to_go", "decks")
    raw = _col_conf_get(
        "modern_menu_sidebar_section_layout",
        {"visible": list(known), "archived": []},
    )
    if isinstance(raw, dict):
        saved = raw.get("visible", [])
    elif isinstance(raw, list):
        saved = raw
    else:
        saved = []
    order = [str(value) for value in saved if str(value) in known]
    if "profile" not in order:
        actions_index = order.index("actions") if "actions" in order else 0
        order.insert(actions_index, "profile")
    order.extend(value for value in known if value not in order)
    return order

def _generate_action_icons_css(conf: dict, addon_package: str) -> str:
    """
    Generates CSS to apply custom or default icons to the sidebar list items.
    """
    css_lines = []
    bundled_icon_base = (
        f"/_addons/{addon_package}/system_files/system_icons/"
        "unavailable_for_users/"
    )
    pickable_icon_base = (
        f"/_addons/{addon_package}/system_files/system_icons/"
        "available_for_users/"
    )
    user_icon_base = f"/_addons/{addon_package}/user_files/icons/"
    addon_dir = os.path.dirname(os.path.dirname(__file__))

    def configured_icon_url(value: object) -> str:
        """Resolve the same icon references written by the Settings picker.

        A page-wide reset writes the schema default as ``system:name.svg``.
        Action-button defaults live in the protected bundled directory, while
        user-selectable system icons live in ``available_for_users``.  Treating
        every non-empty value as a user-file name turned the reset value into
        ``user_files/icons/system:name.svg`` and removed the visible glyph.
        """
        icon_value = str(value or "")
        if not icon_value:
            return ""
        if icon_value.startswith("system:"):
            icon_name = os.path.basename(icon_value[len("system:"):])
            protected_path = os.path.join(
                addon_dir,
                "system_files",
                "system_icons",
                "unavailable_for_users",
                icon_name,
            )
            base = (
                bundled_icon_base
                if os.path.exists(protected_path)
                else pickable_icon_base
            )
            return f"{base}{icon_name}"
        return f"{user_icon_base}{os.path.basename(icon_value)}"
    
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
    
    # Icon size comes from the "Action Button Icons" setting (Icons tab); falls
    # back to 16px, matching generate_icon_size_css()'s default for this key.
    icon_size = _col_conf_get("modern_menu_icon_size_action_button", 16)

    # 1. Standard Actions
    for action_id, filename in default_icons.items():
        # Check for custom icon
        custom_file = _col_conf_get(f"modern_menu_icon_{action_id}", "")

        if custom_file:
            icon_url = configured_icon_url(custom_file)
        else:
            icon_url = f"{bundled_icon_base}{filename}"

        # Per-button icon color (set from Action Button Customization); falls
        # back to the shared --icon-color when none is configured.
        custom_color = config.themed_icon_color(f"modern_menu_icon_color_{action_id}")
        icon_color_css = custom_color if custom_color else "var(--icon-color)"

        css = f"""
        .action-{action_id} .icon,
        .action-{action_id} .action-icon {{
            display: inline-block !important;
            width: {icon_size}px !important;
            height: {icon_size}px !important;
            mask-image: url('{icon_url}') !important;
            -webkit-mask-image: url('{icon_url}') !important;
            mask-size: contain !important;
            -webkit-mask-size: contain !important;
            mask-repeat: no-repeat !important;
            -webkit-mask-repeat: no-repeat !important;
            mask-position: center !important;
            -webkit-mask-position: center !important;
            background-color: {icon_color_css};
        }}
        """
        css_lines.append(css)

    # 2. External Actions (from Sidebar API)
    # We already handle 'icon_svg' in sidebar_api.render_sidebar_entry which generates inline styles or classes.
    # But if there are overrides defined in settings, we should handle them.
    # sidebar_api.render_sidebar_entry already checks _load_icon_override.
    # So we mainly need to ensure the standard buttons get their CSS.

    # 3. Optional dashed call-to-action outline on "Add" (Action Button
    #    Customization). Only meaningful in list mode; the collapsed toolbar
    #    renders its own .action-btn markup via injector.js.
    if conf.get("sidebarAddDashed", False):
        css_lines.append("""
        .sidebar-left .menu-item.action-add {
            border: 1px dashed var(--border) !important;
            border-radius: 8px !important;
        }
        """)

    return "<style>" + "\n".join(css_lines) + "</style>"


# --- Helper functions (copied from patcher.py for self-containment) ---

def _get_profile_pic_html(user_name: str, addon_package: str, css_class: str = "profile-pic") -> str:
    is_dark = config.effective_night_mode()
    mode = _col_conf_get("modern_menu_profile_picture_mode", "image")
    dynamic = bool(_col_conf_get("modern_menu_profile_picture_dynamic_mode", True))
    theme_key = "dark" if is_dark else "light"
    color = _col_conf_get(f"modern_menu_profile_picture_color_{theme_key}", "#B8BDC3" if is_dark else "#8CACB4") if dynamic else _col_conf_get("modern_menu_profile_picture_color_light", "#8CACB4")
    if mode == "accent":
        color = "var(--accent-color)"
    
    if mode in {"accent", "custom"}:
        content = html.escape((user_name[:1] or "U").upper(), quote=False)
        if mode in {"accent", "custom"}:
            content_type = _col_conf_get("modern_menu_profile_picture_content_type", "letter")
            letter = str(_col_conf_get("modern_menu_profile_picture_letter", "") or "").strip()
            if content_type == "letter" and letter == "...":
                content = ""
            elif content_type == "letter" and letter:
                content = html.escape(letter.upper(), quote=False)
            elif content_type == "icon":
                icon_value = str(_col_conf_get("modern_menu_profile_picture_icon", "system:onigiri.svg") or "")
                if icon_value.startswith("emoji:") and icon_value[6:]:
                    content = html.escape(icon_value[6:], quote=False)
                else:
                    icon_name = os.path.basename(
                        icon_value[7:] if icon_value.startswith("system:") else icon_value
                    )
                    addon_dir = mw.addonManager.addonsFolder(addon_package)
                    if icon_value.startswith("system:"):
                        icon_path = os.path.join(
                            addon_dir, "system_files", "system_icons",
                            "available_for_users", icon_name,
                        )
                        icon_url = (
                            f"/_addons/{addon_package}/system_files/system_icons/"
                            f"available_for_users/{icon_name}"
                        )
                    else:
                        icon_path = os.path.join(addon_dir, "user_files", "icons", icon_name)
                        icon_url = f"/_addons/{addon_package}/user_files/icons/{icon_name}"
                    if icon_name and os.path.isfile(icon_path):
                        safe_url = html.escape(icon_url, quote=True)
                        icon_color = (
                            _col_conf_get(
                                f"modern_menu_profile_picture_icon_color_{theme_key}",
                                "#FFFFFF",
                            )
                            if dynamic
                            else _col_conf_get("modern_menu_profile_picture_icon_color_light", "#FFFFFF")
                        )
                        content = (
                            '<span class="profile-pic-generated-icon" '
                            f'style="color: {icon_color}; -webkit-mask-image: url(\'{safe_url}\'); '
                            f'mask-image: url(\'{safe_url}\')"></span>'
                        )
        return f'<span class="{css_class} profile-pic-generated" style="background-color: {color}">{content}</span>'

    if dynamic:
        profile_pic_filename = _col_conf_get(f"modern_menu_profile_picture_{theme_key}", "") or _col_conf_get("modern_menu_profile_picture", "")
    else:
        profile_pic_filename = _col_conf_get("modern_menu_profile_picture", "")

    if profile_pic_filename and os.path.exists(os.path.join(mw.addonManager.addonsFolder(addon_package), "user_files", "profile", profile_pic_filename)):
        pic_url = f"/_addons/{addon_package}/user_files/profile/{profile_pic_filename}"
    else:
        default_pic = "onigiri-san.png"
        pic_url = f"/_addons/{addon_package}/system_files/profile_default/{default_pic}"

    return f'<img src="{pic_url}" class="{css_class}">'


def _chip_color_to_css(color: str) -> str:
    """Qt's #AARRGGBB (from _valid_hex_color when alpha < 255) isn't a valid
    CSS/SVG color; convert it to rgba(). Plain #RRGGBB passes through."""
    text = str(color or "").strip()
    if text.startswith("#") and len(text) == 9:
        a = int(text[1:3], 16) / 255.0
        r = int(text[3:5], 16)
        g = int(text[5:7], 16)
        b = int(text[7:9], 16)
        return f"rgba({r}, {g}, {b}, {a:.3f})"
    return text


def _nook_level_progress():
    """Returns (enabled, level, fraction, chip_color) for the ring/minimal
    profile fill. `chip_color` is the Level Chip's own Progress color
    (Settings > Games > Gamification > Level Chip Appearance), so the
    ring/minimal fill always matches the chip shown in the reviewer/sidebar.
    `enabled` is True only when the Nook Level minigame is on AND set to show
    profile-bar progress, matching the guards used by _get_nook_level_chip_html
    in patcher.py."""
    try:
        conf = config.get_config_readonly()
        nook = _nook_level()
        # Nook's gamification state is authoritative after its one-time
        # settings migration.  Reading the old config copy first can make the
        # profile render its demo level even though the saved Nook is enabled
        # and has real XP/level data.
        progress = nook.manager.get_progress()
        if not progress or not getattr(progress, "enabled", False):
            return (False, 0, 0.0, "")
        if not getattr(progress, "show_profile_bar_progress", True):
            return (False, 0, 0.0, "")
        level = getattr(progress, "level", 0)
        fraction = float(getattr(progress, "progress_fraction", 0.0) or 0.0)
        fraction = max(0.0, min(1.0, fraction))
        chip_color = _chip_color_to_css(nook.get_chip_style_values(conf).get("progress") or "")
        return (True, level, fraction, chip_color)
    except Exception as exc:
        print(f"Onigiri: Error reading nook level progress: {exc}")
        return (False, 0, 0.0, "")


def _selected_profile_level_game():
    """Which game drives the profile Level chip: 'nook' | 'onigimon' | 'hexagon'.
    Chosen in Settings > Games > Gamification > Profile Level."""
    try:
        return str(config.get_config_readonly().get("profile_level_game", "nook") or "nook").lower()
    except Exception:
        return "nook"


def _shared_chip_progress_color():
    """The user's Level Chip progress color (now a shared General setting).
    Used so every game's profile level fills in the same picked color."""
    try:
        raw = _nook_level().get_chip_style_values(config.get_config_readonly()).get("progress") or ""
        return _chip_color_to_css(raw)
    except Exception:
        return ""


def _onigimon_level_progress():
    """(enabled, level, fraction, color) for the Onigimon companion level."""
    try:
        onigimon = _onigimon()
        if not onigimon.manager.is_enabled():
            return (False, 0, 0.0, "")
        payload = onigimon.manager.widget_payload(refresh_bridge=False)
        if payload.get("status") != "ready":
            return (False, 0, 0.0, "")
        companion = payload.get("companion")
        if not companion:
            return (False, 0, 0.0, "")
        level = int(companion.get("level") or 0)
        xp = int(companion.get("xp") or 0)
        # Medium-fast growth group: total xp for level n is n**3.
        base = level ** 3
        nxt = (level + 1) ** 3
        span = max(1, nxt - base)
        fraction = max(0.0, min(1.0, (xp - base) / span))
        return (True, level, fraction, "#f5a623")
    except Exception as exc:
        print(f"Onigiri: Error reading onigimon level: {exc}")
        return (False, 0, 0.0, "")


def _hexagon_level_progress():
    """(enabled, level, fraction, color) for the Hexagon Land island level."""
    try:
        conf = config.get_config_readonly()
        hex_conf = conf.get("hexagon_land", conf.get("hexagon_world", {}))
        if not hex_conf.get("enabled", False):
            return (False, 0, 0.0, "")
        hexagon = _hexagon_land()
        if not hexagon.manager.is_enabled():
            return (False, 0, 0.0, "")
        info = hexagon.manager.level_info()
        return (True, int(info["level"]), float(info["fraction"]), "#1597d1")
    except Exception as exc:
        print(f"Onigiri: Error reading hexagon level: {exc}")
        return (False, 0, 0.0, "")


def _profile_level_progress():
    """Unified profile-card level, dispatched by the General profile-level game
    selector. Returns (enabled, level, fraction, color). If the chosen game is
    off/unavailable it returns disabled (no surprise fallback to another game)."""
    game = _selected_profile_level_game()
    if game == "onigimon":
        result = _onigimon_level_progress()
    elif game == "hexagon":
        result = _hexagon_level_progress()
    else:
        result = _nook_level_progress()
    if not result[0]:
        return (False, 0, 0.0, "")
    # Always use the shared Level Chip progress color, including for Nook.
    # Every selected mini game changes the level/fraction only; none may
    # replace the user's Profile progress-bar color.
    shared = _shared_chip_progress_color()
    if shared:
        return (result[0], result[1], result[2], shared)
    return result


def _profile_level_source_name(game: str) -> str:
    """Localized name of the game currently driving Profile Level."""
    return {
        "nook": tr("profile_level_opt_nook", "Nook"),
        "onigimon": tr("profile_level_opt_onigimon", "Onigimon XP"),
        "hexagon": tr("profile_level_opt_hexagon", "Hexagon Land"),
    }.get(game, tr("profile_level_opt_nook", "Nook"))


def _profile_fill_color():
    """User-picked fallback fill color (theme-aware) used when Nook Level is off."""
    is_dark = config.effective_night_mode()
    dynamic = bool(_col_conf_get("modern_menu_profile_fill_dynamic_mode", True))
    theme_key = "dark" if (is_dark and dynamic) else "light"
    return _col_conf_get(f"modern_menu_profile_fill_color_{theme_key}", "#4f7cff") or "#4f7cff"


def _profile_sidebar_accent_color():
    """Weekly-chart color: the bar-mode name color when profile_type is 'bar',
    else the same ring/minimal progress color used by build_profile_type_html."""
    profile_type = _col_conf_get("modern_menu_profile_type", "bar")
    if profile_type == "bar":
        is_dark = config.effective_night_mode()
        theme_key = "dark" if is_dark else "light"
        default_color = config.DEFAULTS["colors"][theme_key]["--fg"]
        return _col_conf_get(
            f"modern_menu_profile_name_color_{theme_key}", default_color
        ) or default_color
    enabled, _level, _fraction, theme_color = _profile_level_progress()
    return theme_color if (enabled and theme_color) else _profile_fill_color()


def _nook_level_page_progress():
    """Return Nook Level data for the expanded Profile Sidebar.

    Visibility is deliberately handled by ``onigiriProfilePanel`` alongside
    the other sidebar rows. The Nook manager retains progress even when its
    gameplay loop is paused, so the Profile Sidebar can faithfully render an
    enabled Nook row instead of silently dropping it.
    """
    try:
        conf = config.get_config_readonly()
        nook = _nook_level()
        progress = nook.manager.get_progress()
        if not progress:
            return (False, 0, 0.0, "")
        level = getattr(progress, "level", 0)
        fraction = float(getattr(progress, "progress_fraction", 0.0) or 0.0)
        fraction = max(0.0, min(1.0, fraction))
        chip_color = _chip_color_to_css(nook.get_chip_style_values(conf).get("progress") or "#B94632")
        return (True, level, fraction, chip_color)
    except Exception as exc:
        print(f"Onigiri: Error reading nook level page progress: {exc}")
        return (False, 0, 0.0, "")


def _hexagon_land_count():
    try:
        conf = config.get_config_readonly()
        hex_conf = conf.get("hexagon_land", conf.get("hexagon_world", {}))
        if not hex_conf.get("enabled", False):
            return (False, 0)
        payload = _hexagon_land().manager.payload()
        if not payload.get("enabled", False):
            return (False, 0)
        return (True, int(payload.get("builtLands", 0) or 0))
    except Exception as exc:
        print(f"Onigiri: Error reading hexagon land count: {exc}")
        return (False, 0)


def _onigimon_hp_summary():
    try:
        onigimon = _onigimon()
        if not onigimon.manager.is_enabled():
            return None
        payload = onigimon.manager.widget_payload(refresh_bridge=False)
        if payload.get("status") != "ready":
            return None
        companion = payload.get("companion")
        if not companion:
            return None
        name = onigimon.manager.companion_display_name(companion)
        current_hp = int(companion.get("hp") or 0)
        max_hp = int(companion.get("max_hp") or 0)
        health_pct = onigimon.manager.status_values(onigimon.OnigimonCompanion(**companion)).get("health", 0)
        return {
            "name": name,
            "current_hp": current_hp,
            "max_hp": max_hp,
            "health_pct": max(0, min(100, int(health_pct or 0))),
        }
    except Exception as exc:
        print(f"Onigiri: Error reading onigimon HP: {exc}")
        return None


def _weekly_chart_svg(values, color):
    width, height = 260, 64
    pad_x, pad_y = 6, 8
    safe_values = [max(0, int(v)) for v in (values or [])] or [0] * 7
    max_val = max(max(safe_values), 1)
    n = len(safe_values)
    step = (width - pad_x * 2) / max(n - 1, 1)
    points = []
    for i, v in enumerate(safe_values):
        x = pad_x + step * i
        y = pad_y + (height - pad_y * 2) * (1 - (v / max_val))
        points.append((x, y))

    def _smooth_path(pts):
        if not pts:
            return ""
        d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f} "
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            mx = (x0 + x1) / 2
            d += f"C{mx:.1f},{y0:.1f} {mx:.1f},{y1:.1f} {x1:.1f},{y1:.1f} "
        return d

    line_d = _smooth_path(points)
    fill_d = ""
    if points:
        fill_d = (
            line_d
            + f"L{points[-1][0]:.1f},{height - pad_y:.1f} "
            + f"L{points[0][0]:.1f},{height - pad_y:.1f} Z"
        )

    return f"""
    <svg class="onigiri-sidebar-profile-chart-svg" viewBox="0 0 {width} {height}" preserveAspectRatio="none" aria-hidden="true">
        <defs>
            <linearGradient id="opro-chart-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="{color}" stop-opacity="0.35"></stop>
                <stop offset="100%" stop-color="{color}" stop-opacity="0"></stop>
            </linearGradient>
        </defs>
        <path d="{fill_d}" fill="url(#opro-chart-fill)" stroke="none"></path>
        <path d="{line_d}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"></path>
    </svg>
    """


def _weekly_chart_html(color):
    try:
        from ..study_tools import prep_station
        values, labels = prep_station._weekly_review_counts()
    except Exception as exc:
        print(f"Onigiri: Error reading weekly review counts: {exc}")
        return ""
    chart_svg = _weekly_chart_svg(values, color)
    labels_html = "".join(f"<span>{html.escape(str(label))}</span>" for label in labels)
    return f"""
    <section class="onigiri-sidebar-profile-chart">
        <div class="onigiri-sidebar-profile-chart-head">
            <h3>{html.escape(tr("profile_panel_weekly_chart", "Weekly Study Chart"))}</h3>
            <span>{sum(values)}</span>
        </div>
        {chart_svg}
        <div class="onigiri-sidebar-profile-chart-labels">{labels_html}</div>
    </section>
    """


def _profile_gamification_summary_html(panel_conf):
    items = []

    if panel_conf.get("show_nook_level", True):
        enabled, level, fraction, color = _nook_level_page_progress()
        if enabled:
            pct = fraction * 100
            items.append(f"""
            <div class="onigiri-sidebar-profile-summary-row">
                <span class="onigiri-sidebar-profile-summary-label">{html.escape(tr("restaurant_level", "Nook Level"))} {level}</span>
                <div class="onigiri-sidebar-profile-summary-track">
                    <div class="onigiri-sidebar-profile-summary-fill" style="width: {pct:.1f}%; background: {color};"></div>
                </div>
            </div>
            """)

    if panel_conf.get("show_hexagon_land", True):
        hex_enabled, count = _hexagon_land_count()
        if hex_enabled:
            items.append(f"""
            <div class="onigiri-sidebar-profile-summary-row onigiri-sidebar-profile-summary-row-count">
                <span class="onigiri-sidebar-profile-summary-label">{html.escape(tr("hexagon_land", "Hexagon Land"))}</span>
                <span class="onigiri-sidebar-profile-summary-value" style="color: #2D8CFF;">{count}</span>
            </div>
            """)

    if panel_conf.get("show_onigimon_hp", True):
        hp = _onigimon_hp_summary()
        if hp:
            items.append(f"""
            <div class="onigiri-sidebar-profile-summary-row">
                <span class="onigiri-sidebar-profile-summary-label">{html.escape(hp["name"])} HP</span>
                <div class="onigiri-sidebar-profile-summary-track">
                    <div class="onigiri-sidebar-profile-summary-fill" style="width: {hp["health_pct"]}%; background: #08c46b;"></div>
                </div>
                <span class="onigiri-sidebar-profile-summary-detail">{hp["current_hp"]}/{hp["max_hp"]}</span>
            </div>
            """)

    if not items:
        return ""
    return f"""
    <section class="onigiri-sidebar-profile-summary">
        {''.join(items)}
    </section>
    """


def _profile_study_summary_html(sidebar_conf):
    """Collection-backed details for the Profile Sidebar, in every theme."""
    from .. import things_theme

    sections = []
    if sidebar_conf.get("show_active_cards", True):
        states = things_theme._card_state_counts()
        total = sum(states.values())
        palette = config.get_config_readonly().get("things_theme", {}).get("active_cards_colors", {})
        defaults = config.DEFAULTS["things_theme"]["active_cards_colors"]
        segments, legend, colors = [], [], []
        cursor = 0.0
        labels = (("new", "New"), ("learning", "Learning"),
                  ("relearning", "Relearning"), ("young", "Young"), ("mature", "Mature"))
        for key, fallback in labels:
            count = states.get(key, 0)
            percent = count / total * 100 if total else 0
            gap = min(5, percent * 0.72)
            length = (0.01 if percent <= 5.5 else max(0.01, percent - gap)) if percent else 0
            start = cursor + (percent / 2 if percent <= 5.5 else gap / 2)
            color = html.escape(str(palette.get(key) or defaults[key]), quote=True)
            colors.append(f"--ba-donut-{key}: {color};")
            segments.append(f'<circle class="ba-side-donut-segment ba-side-donut-segment--{key}" '
                            f'cx="50" cy="50" r="40" pathLength="100" '
                            f'style="stroke-dasharray: {length:.2f} {100-length:.2f}; '
                            f'stroke-dashoffset: {-start:.2f}; opacity: {1 if percent else 0};" />')
            label = html.escape(tr(f"profile_sidebar_cards_{key}", fallback))
            legend.append(f'<li><button type="button" class="ba-side-donut-item ba-side-donut-item--{key}" '
                          f'onclick="pycmd(\'ba:donut-open:{key}\')">'
                          f'<span class="ba-side-donut-dot" aria-hidden="true"></span>'
                          f'<span class="ba-side-donut-l">{label}</span>'
                          f'<span class="ba-side-donut-v">{count:,}</span></button></li>')
            cursor += percent
        compact = ' class="is-tiny"' if len(f"{total:,}") >= 7 else (' class="is-compact"' if len(f"{total:,}") >= 5 else '')
        sections.append(f"""
        <section class="ba-side-donut-block" style="{''.join(colors)}">
            <div class="onigiri-sidebar-profile-chart-head"><h3>{html.escape(tr("profile_sidebar_active_cards", "Active Cards"))}</h3></div>
            <div class="ba-side-donut-row">
                <div class="ba-side-donut-ring">
                    <svg class="ba-side-donut-svg" viewBox="0 0 100 100" aria-hidden="true">
                        <circle class="ba-side-donut-track" cx="50" cy="50" r="40" pathLength="100" />
                        {''.join(segments)}
                    </svg>
                    <div class="ba-side-donut-core"><strong{compact}>{total:,}</strong></div>
                </div>
                <ul class="ba-side-donut-legend">{''.join(legend)}</ul>
            </div>
        </section>
        """)
    if sidebar_conf.get("show_today_stats", True) and mw.col:
        try:
            cutoff = (mw.col.sched.day_cutoff - 86400) * 1000
            reviews, seconds = mw.col.db.first(
                "select count(), coalesce(sum(time), 0)/1000.0 from revlog where type IN (0,1,2,3) and id > ?", cutoff
            ) or (0, 0)
            streak = things_theme._standing()["streak"]
            minutes = int(seconds or 0) // 60
            duration = f"{minutes // 60}h {minutes % 60}m" if minutes >= 60 else f"{minutes}m"
            rows = ((tr("profile_sidebar_reviews", "Reviews"), f"{reviews:,}"),
                    (tr("profile_sidebar_study_time", "Study Time"), duration),
                    (tr("profile_sidebar_streak", "Study Streak"), f'{streak} {tr("profile_sidebar_days", "days")}'))
            details = ''.join(f'<div class="onigiri-sidebar-profile-summary-row onigiri-sidebar-profile-summary-row-count"><dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd></div>' for label, value in rows)
            sections.append(f'<section class="onigiri-sidebar-profile-today"><div class="onigiri-sidebar-profile-chart-head"><h3>{html.escape(tr("profile_sidebar_today", "Today"))}</h3></div><dl>{details}</dl></section>')
        except Exception as exc:
            print(f"Onigiri: Error reading Profile Sidebar study stats: {exc}")
    return ''.join(sections)


def _profile_birthday_badge_html(birthday_str):
    text = str(birthday_str or "").strip()
    if not text:
        return ""
    try:
        birth_month, birth_day = int(text[5:7]), int(text[8:10])
    except (ValueError, IndexError):
        return ""
    today = date.today()
    if (birth_month, birth_day) != (today.month, today.day):
        return ""
    return f'<p class="onigiri-sidebar-profile-birthday-badge">🎂 {html.escape(tr("happy_birthday", "Happy Birthday!"))}</p>'


def build_profile_type_html(surface, profile_type, user_name, profile_pic_html):
    """Ring/minimal profile widget shared by the sidebar, Overviewer and
    Congrats surfaces. `surface` in {'sidebar','overview','congrats'} controls
    the wrapper class and whether the sidebar profile-sidebar toggle is wired.
    Returns '' for the 'bar' (or any unknown) type so callers keep their
    existing horizontal-bar markup."""
    if profile_type not in ("ring", "minimal"):
        return ""

    safe_name = html.escape(str(user_name), quote=False)
    enabled, level, fraction, theme_color = _profile_level_progress()
    # Keep the Profile ring/minimal fill tied to the shared Level Chip
    # progress color even while a selected mini-game is unavailable during a
    # live settings refresh. Otherwise Hexagon Land can fall through to the
    # generic Profile fill (#4f7cff), making the bar appear game-specific.
    shared_color = _shared_chip_progress_color()
    fill_color = shared_color or (theme_color if (enabled and theme_color) else _profile_fill_color())
    if not enabled:
        # This is a live profile, not a settings preview.  Do not present the
        # former demo 65% ring / "Lv. 12" as real progress when its selected
        # source is unavailable.
        fraction = 0.0

    surface_class = f"opro-surface-{surface}"
    onclick_attr = (
        ' onclick="window.OnigiriProfileSidebar && OnigiriProfileSidebar.toggle(event)"'
        if surface == "sidebar" else ""
    )
    level_html = ""
    if enabled:
        source_name = html.escape(_profile_level_source_name(_selected_profile_level_game()), quote=False)
        level_html = (
            f'<span class="opro-level">{tr("level_prefix", "Lv.")} {level}'
            f' · {source_name}</span>'
        )

    if profile_type == "ring":
        import math
        r = 21
        circ = 2 * math.pi * r
        offset = circ * (1 - fraction)
        inner = f"""
        <div class="opro-avatar-wrap">
            <div class="opro-avatar">{profile_pic_html}</div>
            <svg class="opro-ring" viewBox="0 0 48 48" aria-hidden="true">
                <circle class="opro-ring-track" cx="24" cy="24" r="{r}"></circle>
                <circle class="opro-ring-fill" cx="24" cy="24" r="{r}"
                    stroke="{fill_color}" stroke-dasharray="{circ:.2f}"
                    stroke-dashoffset="{offset:.2f}"></circle>
            </svg>
        </div>
        <div class="opro-text">
            <span class="opro-name">{safe_name}</span>
            {level_html}
        </div>
        """
        type_class = "ring-profile"
    else:  # minimal
        pct = fraction * 100
        inner = f"""
        <div class="opro-avatar">{profile_pic_html}</div>
        <div class="opro-info">
            <span class="opro-name">{safe_name}</span>
            <div class="opro-track">
                <div class="opro-bar-fill" style="width: {pct:.1f}%; background: {fill_color};"></div>
            </div>
        </div>
        """
        type_class = "minimal-profile"

    classes = f"onigiri-profile {type_class} {surface_class}".strip()
    return (
        f'<div class="{classes}"{onclick_attr}>'
        f'{inner}'
        f'</div>'
    )


def _profile_bg_image_name():
    """The bar background for the current theme (see config.themed_asset)."""
    from ..core import config as _config

    try:
        is_dark = bool(_config.effective_night_mode())
    except Exception:
        is_dark = False
    return _config.themed_asset(
        _col_conf_get,
        "modern_menu_profile_bg_image",
        is_dark,
        dynamic_key="modern_menu_profile_bg_dynamic_mode",
    )


def _profile_background_render_parts(addon_package, include_default_image=True):
    container_style = ""
    layer_style = ""
    bg_mode = _col_conf_get("modern_menu_profile_bg_mode", "image")
    dyn_bg = bool(_col_conf_get("modern_menu_profile_bg_dynamic_mode", True))
    is_dark = config.effective_night_mode()
    theme_key = "dark" if (is_dark and dyn_bg) else "light"
    default_color = config.DEFAULTS["colors"][theme_key]["--profile-page-bg"]
    bg_color = _col_conf_get(
        f"modern_menu_profile_bg_color_{theme_key}", default_color
    ) or default_color

    if bg_mode == "image":
        bg_image_file = _profile_bg_image_name()
        if bg_image_file and os.path.exists(os.path.join(mw.addonManager.addonsFolder(addon_package), "user_files", "profile_bg", bg_image_file)):
            bg_url = f"/_addons/{addon_package}/user_files/profile_bg/{bg_image_file}"
        elif include_default_image:
            bg_url = f"/_addons/{addon_package}/system_files/profile_default/onigiri-bg.png"
        else:
            bg_url = ""
        container_style = f"background-color: {bg_color} !important; --profile-image-overlay-bg: transparent;"
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
        container_style = f"background-color: {bg_color} !important;"
    else:
        container_style = "background-color: var(--accent-color) !important;"
    return container_style, layer_style


def _profile_sidebar_page_background_style():
    """The flat or gradient backdrop of the expanded Profile Sidebar."""
    is_dark = config.effective_night_mode()
    dynamic = bool(_col_conf_get("onigiri_profile_page_bg_dynamic_mode", True))
    theme_key = "dark" if (is_dark and dynamic) else "light"
    color1 = _col_conf_get(
        f"onigiri_profile_page_bg_{theme_key}_color1",
        "#2C2C2C" if is_dark else "#F5F5F5",
    ) or ("#2C2C2C" if is_dark else "#F5F5F5")
    if _col_conf_get("onigiri_profile_page_bg_mode", "color") != "gradient":
        return f"background: {color1} !important;"
    color2 = _col_conf_get(
        f"onigiri_profile_page_bg_{theme_key}_color2",
        "#1A1A1A" if is_dark else "#E0E0E0",
    ) or ("#1A1A1A" if is_dark else "#E0E0E0")
    return f"background: linear-gradient(135deg, {color1}, {color2}) !important;"


def _profile_sidebar_cover_render_parts(addon_package):
    """Return the Profile Sidebar cover, falling back to the profile-bar art."""
    is_dark = config.effective_night_mode()
    cover_file = config.themed_asset(
        _col_conf_get,
        "onigiri_profile_sidebar_cover_image",
        is_dark,
        dynamic_key="onigiri_profile_page_bg_dynamic_mode",
    )
    if cover_file:
        base_dir = os.path.join(
            mw.addonManager.addonsFolder(addon_package), "user_files", "profile_bg"
        )
        if os.path.isfile(os.path.join(base_dir, cover_file)):
            url = f"/_addons/{addon_package}/user_files/profile_bg/{cover_file}"
            return (
                "background-color: var(--accent-color) !important;",
                "background-image: url('{0}'); background-size: cover; "
                "background-position: center;".format(url),
            )
    return _profile_background_render_parts(addon_package)


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
        "musicLink": str(profile.get("spotifyLink") or profile.get("musicLink") or "").strip(),
    }


def _build_profile_sidebar_html(conf: dict, addon_package: str, user_name: str, profile_pic_html: str) -> str:
    profile = _profile_sidebar_config(conf)
    page_style = _profile_sidebar_page_background_style()
    bg_style, layer_style = _profile_sidebar_cover_render_parts(addon_package)
    bg_layer_html = f'<div class="onigiri-sidebar-profile-bg-layer" style="{layer_style}"></div>' if layer_style else ""

    bio_html = f'<p class="onigiri-sidebar-profile-bio">{html.escape(profile["bio"], quote=False)}</p>' if profile["bio"] else ""
    birthday_html = _profile_birthday_badge_html(conf.get("userBirthday", ""))
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

    panel_conf = conf.get("onigiriProfilePanel", {})
    if not isinstance(panel_conf, dict):
        panel_conf = {}

    chart_html = ""
    if panel_conf.get("show_weekly_chart", True):
        chart_html = _weekly_chart_html(_profile_sidebar_accent_color())

    summary_html = _profile_gamification_summary_html(panel_conf)
    study_html = _profile_study_summary_html(panel_conf)

    return f"""
    <section class="onigiri-sidebar-profile" data-profile-sidebar style="{page_style}">
        <button type="button" class="onigiri-sidebar-profile-back" aria-label="Back" onclick="window.OnigiriProfileSidebar && OnigiriProfileSidebar.close(event)"></button>
        <div class="onigiri-sidebar-profile-cover" style="{bg_style}">
            {bg_layer_html}
        </div>
        <div class="onigiri-sidebar-profile-body">
            <div class="onigiri-sidebar-profile-avatar">{profile_pic_html}</div>
            <h2>{html.escape(user_name, quote=False)}</h2>
            {birthday_html}
            {bio_html}
            {music_html}
            {chart_html}
            {summary_html}
            {study_html}
        </div>
    </section>
    """


# ─── Today's Stats widgets (Studied / Time / Pace / Retention) ────────────────
#
# Two designs share one renderer:
#   "minimal"    - label above, value below, left aligned. Same information as
#                  the original cards, just better distributed.
#   "expressive" - a tinted icon chip, an oversized value with a muted unit
#                  suffix, and an optional 7-day sparkline along the bottom.
#
# Everything the two designs draw (box surface, accents, label/value colors,
# radius, stroke, blur, type size) arrives as --swidget-* CSS variables emitted
# by patcher.generate_dynamic_css, so this function never hardcodes a color.

_STATS_WIDGET_DEFAULT_ICONS = {
    "studied": "system:stats-widget-studied.svg",
    "time": "system:stats-widget-time.svg",
    "pace": "system:stats-widget-pace.svg",
    "retention": "system:stats-widget-retention.svg",
    "retention_star": "system:star.svg",
}


def _stats_widgets_style() -> dict:
    style = config.get_config_readonly().get("stats_widgets_style", {})
    return style if isinstance(style, dict) else {}


def _stats_widget_design() -> str:
    design = str(_stats_widgets_style().get("design", "minimal"))
    return design if design in ("minimal", "expressive") else "minimal"


def _stats_widget_chart_shape() -> str:
    """Trend line shape: "sharp" straight segments, or "smooth" curves."""
    shape = str(_stats_widgets_style().get("chart_shape", "sharp"))
    return shape if shape in ("sharp", "smooth") else "sharp"


def _stats_widget_smooth_path(points) -> str:
    """SVG path data through `points`, as a Catmull-Rom spline in cubic form.

    Each segment's control points are the neighbours' slope scaled by 1/6, the
    standard uniform Catmull-Rom to Bezier conversion. Endpoints reuse their own
    coordinate as the missing neighbour so the curve starts and ends flat rather
    than shooting past the card's edge.
    """
    if len(points) < 2:
        return ""
    parts = [f"M {points[0][0]:.1f},{points[0][1]:.1f}"]
    for index in range(len(points) - 1):
        p0 = points[index - 1] if index > 0 else points[index]
        p1 = points[index]
        p2 = points[index + 1]
        p3 = points[index + 2] if index + 2 < len(points) else points[index + 1]
        c1x = p1[0] + (p2[0] - p0[0]) / 6.0
        c1y = p1[1] + (p2[1] - p0[1]) / 6.0
        c2x = p2[0] - (p3[0] - p1[0]) / 6.0
        c2y = p2[1] - (p3[1] - p1[1]) / 6.0
        parts.append(f"C {c1x:.1f},{c1y:.1f} {c2x:.1f},{c2y:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(parts)


def _stats_widget_stars_shown() -> bool:
    """Whether the Retention card draws its stars.

    Both designs can show the row; the style-specific CSS keeps Minimal's
    version smaller and quieter. The legacy "hideRetentionStars" switch still
    wins.
    """
    if config.get_config_readonly().get("hideRetentionStars", False):
        return False
    return bool(_stats_widgets_style().get("show_retention_stars", True))


def _stats_widget_icon_value(widget_id: str) -> str:
    """Configured icon value, with the Stats Widgets default as fallback."""
    icons = _stats_widgets_style().get("icons", {})
    if isinstance(icons, dict):
        value = str(icons.get(widget_id) or "")
        if value:
            return value
    return _STATS_WIDGET_DEFAULT_ICONS.get(widget_id, "")


def _stats_widget_icon_url(widget_id: str) -> str:
    """Data URI for a configured Stats Widgets icon, or "" if unresolved.

    Mirrors the deck-icon resolution used elsewhere: a "system:" prefix points
    into system_files/system_icons, anything else is looked up in the user's own
    icon folders first. Emoji values are handled by the caller.
    """
    value = _stats_widget_icon_value(widget_id)
    if not value or value.startswith("emoji:"):
        return ""

    from ..ui_kit.common import system_icon_path

    addon_path = os.path.dirname(os.path.dirname(__file__))
    if value.startswith("system:"):
        path = system_icon_path(value[len("system:"):])
    else:
        path = ""
        for folder in ("custom_deck_icons", "icons"):
            candidate = os.path.join(addon_path, "user_files", folder, value)
            if os.path.exists(candidate):
                path = candidate
                break
        if not path:
            path = system_icon_path(value)
    if not path or not os.path.exists(path):
        return ""
    try:
        import base64

        with open(path, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"
    except Exception:
        return ""


def _stats_widget_icon_html(widget_id: str) -> str:
    """The icon chip. Masked, so it always takes the widget's accent color."""
    style = _stats_widgets_style()
    if not style.get("show_icons", True):
        return ""
    raw = _stats_widget_icon_value(widget_id)
    if raw.startswith("emoji:"):
        glyph = raw[len("emoji:"):]
        return f'<span class="stat-icon-chip"><span class="stat-icon-emoji">{html.escape(glyph)}</span></span>'
    url = _stats_widget_icon_url(widget_id)
    if not url:
        return ""
    return (
        f'<span class="stat-icon-chip"><span class="stat-icon"'
        f' style="-webkit-mask-image: url(\'{url}\'); mask-image: url(\'{url}\');"></span></span>'
    )


def _stats_widget_star_html(is_empty: bool) -> str:
    """One Retention rating glyph from its own Stats Widgets picker.

    This intentionally does not use the legacy `.star` class: that class is
    still configured by the menu-wide Retention Star setting. Keeping a local
    class makes the card heading icon and the five rating glyphs two wholly
    separate choices.
    """
    raw = _stats_widget_icon_value("retention_star")
    classes = "stats-widget-star" + (" empty" if is_empty else "")
    if raw.startswith("emoji:"):
        return f'<span class="{classes} is-emoji">{html.escape(raw[6:])}</span>'
    url = _stats_widget_icon_url("retention_star")
    if not url:
        return ""
    return (
        f'<span class="{classes}" style="-webkit-mask-image: url(\'{url}\'); '
        f'mask-image: url(\'{url}\');"></span>'
    )


def _stats_widget_sparkline_html(series, widget_id: str) -> str:
    """A tiny filled area chart of the last 7 days, normalised to its own max.

    Drawn as inline SVG with `currentColor` so it inherits the card's accent and
    needs no extra CSS variable of its own.
    """
    if not _stats_widgets_style().get("show_sparkline", True):
        return ""
    values = [max(0.0, float(v or 0)) for v in (series or [])]
    if len(values) < 2 or max(values) <= 0:
        return ""
    # Normalised across the week's own min..max rather than 0..max, so a metric
    # that barely moves (retention hovering near 80%) reads as a flat line
    # instead of a solid block filling the whole box.
    low, high = min(values), max(values)
    flat = (high - low) < 1e-9
    width, height = 100.0, 28.0
    step = width / (len(values) - 1)
    points = []
    for index, value in enumerate(values):
        x = index * step
        fraction = 0.5 if flat else (value - low) / (high - low)
        # 3px breathing room top and bottom so the stroke is never clipped.
        y = height - 3 - fraction * (height - 6)
        points.append((x, y))

    if _stats_widget_chart_shape() == "smooth" and not flat:
        line = _stats_widget_smooth_path(points)
    else:
        # A flat series has no curve to draw, so both shapes collapse to the
        # same straight line.
        line = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in points)

    fill_html = ""
    if not flat:
        area = f"{line} L {width:.1f},{height:.1f} L 0,{height:.1f} Z"
        fill_html = f'<path class="stat-spark-fill" d="{area}"></path>'
    return f"""
    <svg class="stat-spark" viewBox="0 0 {width:.0f} {height:.0f}" preserveAspectRatio="none" aria-hidden="true">
        {fill_html}
        <path class="stat-spark-line" d="{line}"></path>
    </svg>
    """


def _stats_widget_card_html(
    widget_id: str,
    label: str,
    value: str,
    unit: str = "",
    extra_body: str = "",
    series=None,
    row_span: int = 1,
    col_span: int = 1,
) -> str:
    """Builds one stat card in whichever design is configured.

    `row_span`/`col_span` are the widget's real size on the dashboard grid. They
    only pick how tall the trend strip is; the strip itself is full-bleed along
    the card's bottom edge in every size, with the number anchored above it.
    """
    style = _stats_widgets_style()
    design = _stats_widget_design()
    show_units = bool(style.get("show_units", True))
    try:
        row_span = max(1, int(row_span))
        col_span = max(1, int(col_span))
    except (TypeError, ValueError):
        row_span = col_span = 1

    unit_html = ""
    if unit and show_units:
        unit_html = f'<span class="stat-unit">{html.escape(unit, quote=False)}</span>'

    icon_html = _stats_widget_icon_html(widget_id) if design == "expressive" else ""

    spark_html = ""
    size_class = ""
    if design == "expressive":
        spark_html = _stats_widget_sparkline_html(series, widget_id)
        if spark_html:
            # A taller card can afford a taller chart; a 1x1 keeps it slim so
            # the oversized number still has room above it.
            size_class = " has-trend" + (" is-tall" if row_span >= 2 else "")
        if not style.get("show_wash", True):
            size_class += " no-wash"

    head_html = f'<h3>{label}</h3>'
    if icon_html:
        head_html = f'<div class="stat-head">{icon_html}{head_html}</div>'

    # Every minimal card reserves the star row's height, even the three that
    # have no stars, so the four numbers sit on one line instead of Retention's
    # value being pushed up by its own stars.
    if design == "minimal" and _stats_widget_stars_shown() and not extra_body:
        extra_body = '<div class="star-rating is-placeholder" aria-hidden="true"></div>'

    body_html = f"""
        <div class="stat-body">
            <p class="stat-value">{value}{unit_html}</p>
            {extra_body}
        </div>
    """

    return f"""
    <div class="stat-card onigiri-stat-card is-{design}{size_class} {widget_id}-card" data-stat="{widget_id}">
        {head_html}
        {body_html}
        {spark_html}
    </div>
    """


def _get_onigiri_stat_card_html(label: str, value: str, widget_id: str) -> str:
    """Back-compat entry point: `value` still arrives as one pre-joined string."""
    return _stats_widget_card_html(widget_id, label, value)

# Global Cache for stats to prevent re-querying on every render frame
_DASHBOARD_STATS_CACHE = {}
_DASHBOARD_LAST_UPDATE = 0
_DASHBOARD_CACHE_TTL = 3 # 3 seconds is enough to prevent spam during animations, but keeps it fresh


def _stats_widget_weekly_series() -> dict:
    """Per-day review count / minutes for the last 7 days (oldest first).

    One grouped query, cached alongside the today counters, so turning the
    sparkline on costs a single extra scan every _DASHBOARD_CACHE_TTL seconds.
    """
    cached = _DASHBOARD_STATS_CACHE.get("weekly_series")
    if cached is not None:
        return cached

    cutoff = mw.col.sched.day_cutoff
    window_start = cutoff - 7 * 86400
    empty = {"studied": [0] * 7, "time": [0.0] * 7, "pace": [0.0] * 7, "retention": [0.0] * 7}
    try:
        # The day index is measured forward from the window start so it is
        # always >= 0 and SQLite's truncating cast behaves like floor().
        rows = mw.col.db.all(
            """
            select cast((id/1000.0 - ?) / 86400.0 as int) as day,
                   count(),
                   sum(time)/1000.0,
                   sum(case when type = 1 and ease > 1 then 1 else 0 end),
                   sum(case when type = 1 then 1 else 0 end)
            from revlog
            where type in (0,1,2,3) and id > ?
            group by day
            """,
            window_start,
            window_start * 1000,
        )
    except Exception:
        return empty

    series = {key: list(values) for key, values in empty.items()}
    for day, count, seconds, correct, reviewed in rows:
        index = int(day)
        if not 0 <= index < 7:
            continue
        count = count or 0
        seconds = seconds or 0.0
        series["studied"][index] = count
        series["time"][index] = seconds / 60.0
        series["pace"][index] = (seconds / count) if count else 0.0
        series["retention"][index] = (correct / reviewed * 100.0) if reviewed else 0.0

    _DASHBOARD_STATS_CACHE["weekly_series"] = series
    return series

def _get_onigiri_retention_html(row_span: int = 1, col_span: int = 1) -> str:
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
    
    if _stats_widget_stars_shown():
        star_html = "".join(_stats_widget_star_html(i >= stars) for i in range(5))
        star_rating_html = f'<div class="star-rating">{star_html}</div>'
    else:
        star_rating_html = ""

    res_html = _stats_widget_card_html(
        "retention",
        tr("retention"),
        # The percent sign is part of the number here, not a unit: hiding it
        # with the "Show units" switch would leave a bare, ambiguous figure.
        f"{retention_percentage:.0f}%",
        unit="",
        extra_body=star_rating_html,
        series=_stats_widget_weekly_series().get("retention"),
        row_span=row_span,
        col_span=col_span,
    )
    return process_tr_markers(res_html)

def _get_onigiri_heatmap_html() -> str:
    skeleton_cells = "".join(["<div class='skeleton-cell'></div>" for _ in range(371)])
    minimalist = config.get_config_readonly().get("heatmapMinimalist", False) is True
    return f"""
    <div id='onigiri-heatmap-container' data-minimalist='{str(minimalist).lower()}'>
        <div class="heatmap-header-skeleton"><div class="header-left-skeleton"><div class="skeleton-title"></div></div><div class="header-right-skeleton"><div class="skeleton-streak"></div><div class="skeleton-nav"></div><div class="skeleton-filters"></div></div></div>
        <div class="heatmap-grid-skeleton">{skeleton_cells}</div>
    </div>"""



def _get_onigiri_favorites_html() -> str:
    """
    Generates the HTML for the favorites widget.
    Automatically cleans up deleted decks from the favorites list.
    """
    try:
        favorite_dids = _col_conf_get("onigiri_favorite_decks", [])
        if not favorite_dids:
            fav_placeholder = """
            <div class="onigiri-favorites-widget">
                <div class="onigiri-widget-head"><h3>{tr("favorites")}</h3></div>
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
                      href=# onclick="return OnigiriEngine.openDeck(event, '{did_str}');"
                      oncontextmenu="return OnigiriEngine.showFavoriteDeckContextMenu(event, '{did_str}');"
                      title="{tr('open')} {html.escape(deck_name, quote=True)}">
                    <span class="fav-deck-icon"></span>
                    <span class="fav-deck-name">{html.escape(short_name)}</span>
                </a>"""
            )
        
        # Clean up deleted decks from favorites if any were found
        if len(valid_dids) != len(favorite_dids):
            _col_conf_set("onigiri_favorite_decks", valid_dids)
            removed_count = len(favorite_dids) - len(valid_dids)
            print(f"Onigiri: Cleaned up {removed_count} deleted/ghost deck(s) from favorites")
        
        # If no valid favorites remain after cleanup, show placeholder
        if not links_html:
            empty_fav = """
            <div class="onigiri-favorites-widget">
                <div class="onigiri-widget-head"><h3>{tr("favorites")}</h3></div>
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
            <div class="onigiri-widget-head"><h3>{tr("favorites")}</h3></div>
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

def _get_onigiri_stats_title_html() -> str:
    """Keep a selected backdrop visible even when the phrase is cleared."""
    stats_title = _col_conf_get("modern_menu_statsTitle", None)
    if stats_title is None:
        stats_title = config.get_config_readonly().get("statsTitle", config.DEFAULTS["statsTitle"])
    has_text = bool(str(stats_title).strip())
    enabled = bool(_col_conf_get("modern_menu_title_background_enabled", False))
    if not has_text and not enabled:
        return ""
    alignment = _col_conf_get("modern_menu_title_alignment", "left")
    if alignment not in ("left", "center", "right"):
        alignment = "left"

    def bounded(key, default, maximum):
        try:
            value = float(_col_conf_get(key, default))
            return max(0, min(maximum, value))
        except (TypeError, ValueError):
            return default

    background = ""
    if enabled:
        opacity = bounded("modern_menu_title_background_opacity", 100, 100) / 100
        blur = bounded("modern_menu_title_background_blur", 0, 40)
        kind = _col_conf_get("modern_menu_title_background_type", "color")
        layer_style = ""
        if bool(_col_conf_get("modern_menu_title_sync_widgets", False)):
            layer_style = (
                "opacity:1;background-color:var(--canvas-inset);"
                "backdrop-filter:blur(var(--onigiri-widget-blur, 0px));"
                "-webkit-backdrop-filter:blur(var(--onigiri-widget-blur, 0px));"
            )
        elif kind == "image":
            layer_style = f"opacity:{opacity};"
            filename = os.path.basename(str(_col_conf_get("modern_menu_title_background_image", "") or ""))
            if filename:
                package = quote_url_component(mw.addonManager.addonFromModule(__name__), safe="")
                url = f"/_addons/{package}/user_files/main_bg/{quote_url_component(filename, safe='')}"
                layer_style += f"background-image:url('{url}');filter:blur({blur}px);"
        else:
            color = str(_col_conf_get("modern_menu_title_background_color", "#FFFFFF") or "#FFFFFF")
            # Match the colour picker's hex/rgba output without accepting CSS declarations.
            if not re.fullmatch(r"#[0-9a-fA-F]{3,8}|rgba?\([0-9.,%\s]+\)", color):
                color = "#FFFFFF"
            # Fade the tint, not the filtered layer: an opaque fill would
            # cover the blurred backdrop before element opacity is applied.
            layer_style += f"opacity:1;background-color:color-mix(in srgb, {color} {opacity * 100}%, transparent);backdrop-filter:blur({blur}px);-webkit-backdrop-filter:blur({blur}px);"
        background = f'<div class="onigiri-menu-title-background" aria-hidden="true" style="{html.escape(layer_style, quote=True)}"></div>'
    phrase = f'<h1 class="onigiri-widget-title">{html.escape(str(stats_title))}</h1>' if has_text else ""
    classes = "onigiri-menu-title" + (" has-background" if enabled else "")
    return f'<div class="{classes}" style="--menu-title-alignment:{alignment};">{background}{phrase}</div>'

def _get_onigiri_nook_level_html(orientation: str = "horizontal", row_span: int = 2, col_span: int = 2) -> str:
    """
    Generates the HTML for the Nook Level widget.
    """
    # Invalidate cache to ensure fresh data when deck browser is rendered
    # REVERTED: Do NOT invalidate here. It causes lag on every render.
    # nook_level.manager.invalidate_daily_cache()
    nook_level = _nook_level()

    # Get Nook Level Data
    rl_payload = nook_level.manager.get_progress_payload()
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
    name = rl_payload.get("name", "Nook Level")
    
    # Level Progress
    xp_into = rl_payload.get("xpIntoLevel", 0)
    xp_next = rl_payload.get("xpToNextLevel", 0)
    level_percent = rl_payload.get("progressFraction", 0.0) * 100
    
    if xp_next <= 0:
        xp_text = tr("max_level")
    else:
        xp_text = f"{xp_into} / {xp_next} {tr('xp_label')}"

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
        image_file = "sushi/onigiri_stand.webp" # Default

    # Check if Santa's Coffee is active
    is_santas_coffee = image_file.endswith("santas_coffee.webp")
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
    image_path = f"/_addons/{addon_package}/system_files/gamification_images/nook_folder/{image_file}"

    if row_span <= 1:
        return process_tr_markers(f"""
        <div class="onigiri-restaurant-level-widget onigiri-restaurant-level-widget-compact {snow_class}" role="button" tabindex="0" style="--theme-bg: {bg_style_value};" onclick="pycmd('openRestaurantLevel')" onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();pycmd('openRestaurantLevel');}}">
            <div class="restaurant-image-container">
                <img src="{image_path}" class="restaurant-image">
                {snowflakes_html}
            </div>
        </div>
        """)

    # Navigation buttons with inline SVGs (using currentColor for --fg-subtle inheritance)
    shop_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="rl-nav-icon"><path fill="currentColor" d="M24,10a.988.988,0,0,0-.024-.217l-1.3-5.868A4.968,4.968,0,0,0,17.792,0H6.208a4.968,4.968,0,0,0-4.88,3.915L.024,9.783A.988.988,0,0,0,0,10v1a3.984,3.984,0,0,0,1,2.643V19a5.006,5.006,0,0,0,5,5H18a5.006,5.006,0,0,0,5-5V13.643A3.984,3.984,0,0,0,24,11ZM2,10.109l1.28-5.76A2.982,2.982,0,0,1,6.208,2H7V5A1,1,0,0,0,9,5V2h6V5a1,1,0,0,0,2,0V2h.792A2.982,2.982,0,0,1,20.72,4.349L22,10.109V11a2,2,0,0,1-2,2H19a2,2,0,0,1-2-2,1,1,0,0,0-2,0,2,2,0,0,1-2,2H11a2,2,0,0,1-2-2,1,1,0,0,0-2,0,2,2,0,0,1-2,2H4a2,2,0,0,1-2-2ZM18,22H6a3,3,0,0,1-3-3V14.873A3.978,3.978,0,0,0,4,15H5a3.99,3.99,0,0,0,3-1.357A3.99,3.99,0,0,0,11,15h2a3.99,3.99,0,0,0,3-1.357A3.99,3.99,0,0,0,19,15h1a3.978,3.978,0,0,0,1-.127V19A3,3,0,0,1,18,22Z"/></svg>'''
    
    restaurant_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="rl-nav-icon"><path fill="currentColor" d="m21 6.424v-2.424c1.654 0 3-1.346 3-3 0-.552-.447-1-1-1s-1 .448-1 1-.448 1-1 1h-19v-1c0-.552-.447-1-1-1s-1 .448-1 1v22c0 .552.447 1 1 1s1-.448 1-1v-19h5v2.424c-1.763.774-3 2.531-3 4.576v8c0 2.757 2.243 5 5 5h10c2.757 0 5-2.243 5-5v-8c0-2.045-1.237-3.802-3-4.576zm-12-2.424h10v2h-10zm13 15c0 1.654-1.346 3-3 3h-10c-1.654 0-3-1.346-3-3v-8c0-1.654 1.346-3 3-3h10c1.654 0 3 1.346 3 3zm-3-2c0-2.414-1.721-4.434-4-4.899v-.101c0-.552-.447-1-1-1s-1 .448-1 1v.101c-2.279.465-4 2.484-4 4.899-.553 0-1 .448-1 1s.447 1 1 1h10c.553 0 1-.448 1-1s-.447-1-1-1zm-5-3c1.654 0 3 1.346 3 3h-6c0-1.654 1.346-3 3-3z"/></svg>'''
    
    nav_buttons_html = f"""
    <div class="rl-widget-nav-buttons onigiri-widget-head-aside">
        <button class="rl-nav-btn" onclick="event.stopPropagation(); pycmd('openTaiyakiStore');" title="{tr('open_taiyaki_store')}">
            {shop_svg}
        </button>
        <button class="rl-nav-btn" onclick="event.stopPropagation(); pycmd('openRestaurantLevel');" title="{tr('open_restaurant_level')}">
            {restaurant_svg}
        </button>
    </div>
    """
    
    # Get Nook Rush data. The storage key remains daily_special for migration compatibility.
    daily_special = nook_level.manager.get_daily_special_status()
    ds_enabled = daily_special.get("enabled", False)
    ds_progress = daily_special.get("current_progress", 0)
    ds_target = daily_special.get("target", 100)
    
    ds_html = ""
    if ds_enabled:
        percent = min(100, int((ds_progress / ds_target) * 100)) if ds_target > 0 else 0
        rush_name = daily_special.get("rush_name") or tr("recipe_rush_title", "Nook Rush")
        # Older profiles persist the built-in starter Rush in English.  It is
        # application copy rather than a user-defined title, so localize it.
        if rush_name == "Sushi Rush":
            rush_name = tr("default_sushi_rush", "Sushi Rush")
        ds_html = f"""
        <div class="daily-special-section">
            <div class="ds-header">
                <div class="ds-label">{rush_name}</div>
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
        <div class="onigiri-widget-head rl-widget-head">
            <h3>{name}</h3>
            {nav_buttons_html}
        </div>
        <div class="rl-widget-body">
            <div class="restaurant-image-container" onclick="this.closest('.onigiri-restaurant-level-widget').classList.toggle('expanded-view'); event.stopPropagation();" style="cursor: pointer;">
                <img src="{image_path}" class="restaurant-image">
                {snowflakes_html}
            </div>
            <div class="restaurant-info">
                <div class="level-display">
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
    conf = config.get_config_readonly()
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
        
        # Update cache. The 7-day sparkline series rides the same TTL, so drop
        # it here rather than letting it go stale forever.
        _DASHBOARD_STATS_CACHE.pop("weekly_series", None)
        _DASHBOARD_STATS_CACHE["cards_today"] = cards_today
        _DASHBOARD_STATS_CACHE["time_today_seconds"] = time_today_seconds
        _DASHBOARD_LAST_UPDATE = now
        

        
    time_today_seconds = time_today_seconds or 0
    cards_today = cards_today or 0
    time_today_minutes = time_today_seconds / 60
    seconds_per_card = time_today_seconds / cards_today if cards_today > 0 else 0

    widget_generators = {
        "stats_title": _get_onigiri_stats_title_html,
        # The stat cards take their grid span so the sparkline only appears on
        # a card big enough for it; the loop below re-invokes them with the
        # real spans, these zero-arg defaults are the 1x1 fallback.
        "studied": lambda rs=1, cs=1: _stats_widget_card_html(
            "studied", tr("studied"), f"{cards_today}", tr("cards"),
            series=_stats_widget_weekly_series().get("studied"),
            row_span=rs, col_span=cs,
        ),
        "time": lambda rs=1, cs=1: _stats_widget_card_html(
            "time", tr("time"), f"{time_today_minutes:.1f}", tr("minutes_unit"),
            series=_stats_widget_weekly_series().get("time"),
            row_span=rs, col_span=cs,
        ),
        "pace": lambda rs=1, cs=1: _stats_widget_card_html(
            "pace", tr("pace"), f"{seconds_per_card:.1f}",
            f"{tr('seconds_unit')}/{tr('card')}",
            series=_stats_widget_weekly_series().get("pace"),
            row_span=rs, col_span=cs,
        ),
        "retention": _get_onigiri_retention_html,
        "heatmap": _get_onigiri_heatmap_html,
        "favorites": _get_onigiri_favorites_html, 
        "restaurant_level": _get_onigiri_nook_level_html,
        "onigimon": lambda: _onigimon().render_widget_html(),
        "ankimon_team": render_ankimon_team_widget_html,
        "hexagon_land": lambda: _hexagon_land().render_widget_html(),
        "deck_stats": lambda: _learner_stats_widget()._render_widget(self, "deck_stats"),
        "prep_station": lambda: _prep_station().render_widget_html(),
        "hashi_notes": lambda: _hashi_notes().render_widget_html(),
        "ready_to_go": lambda: _ready_to_go().render_widget_html(),
    }

    def render_widget_safely(widget_id, renderer):
        """Keep one stale widget payload from blanking the whole dashboard."""
        try:
            return renderer()
        except Exception as exc:
            print(f"Onigiri: {widget_id} widget failed: {exc}")
            return ""
    
    if col_count > 0:
        for widget_id, widget_config in onigiri_layout.items():
            if widget_id in TOOL_IDS and not tool_visible(widget_id, conf):
                continue
            if widget_id in widget_generators or _is_deck_stats_widget_id(widget_id):
                if not isinstance(widget_config, dict):
                    print(f"Onigiri: ignored invalid {widget_id} widget layout")
                    continue
                try:
                    pos = max(0, int(widget_config.get("pos", 0)))
                except (TypeError, ValueError):
                    pos = 0
                try:
                    row_span = max(1, int(widget_config.get("row", 1)))
                except (TypeError, ValueError):
                    row_span = 1
                try:
                    col_span = max(1, min(col_count, int(widget_config.get("col", 1))))
                except (TypeError, ValueError):
                    col_span = 1
                if _is_deck_stats_widget_id(widget_id):
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
                elif widget_id == "onigimon":
                    # Onigimon renders 1-4 rows by 1-2 columns.
                    try:
                        row_span = max(1, min(4, int(row_span)))
                    except (TypeError, ValueError):
                        row_span = 2
                    try:
                        col_span = max(1, min(2, int(col_span)))
                    except (TypeError, ValueError):
                        col_span = 1
                elif widget_id == "hashi_notes":
                    try:
                        row_span = max(1, min(4, int(row_span)))
                    except (TypeError, ValueError):
                        row_span = 2
                    try:
                        col_span = max(1, min(4, int(col_span)))
                    except (TypeError, ValueError):
                        col_span = 2
                elif widget_id == "stats_title":
                    row_span = 1
                    try:
                        col_span = max(1, min(4, int(col_span)))
                    except (TypeError, ValueError):
                        col_span = 4

                row = pos // col_count + 1
                col = pos % col_count + 1
                style = f"grid-area: {row} / {col} / span {row_span} / span {col_span};"
                if widget_id == "restaurant_level":
                    widget_html = render_widget_safely(
                        widget_id,
                        lambda: _get_onigiri_nook_level_html(
                            widget_config.get("orientation", "horizontal"),
                            row_span=row_span,
                            col_span=col_span,
                        ),
                    )
                elif widget_id == "ready_to_go":
                    widget_html = render_widget_safely(
                        widget_id,
                        lambda: _ready_to_go().render_widget_html(
                            design=widget_config.get("design", "squares")
                        ),
                    )
                elif widget_id == "prep_station":
                    widget_html = render_widget_safely(
                        widget_id,
                        lambda: _prep_station().render_widget_html(
                            slot_count=col_span
                        ),
                    )
                elif widget_id == "hashi_notes":
                    widget_html = render_widget_safely(
                        widget_id,
                        lambda: _hashi_notes().render_widget_html(
                            row_span=row_span,
                            col_span=col_span,
                        ),
                    )
                elif widget_id in ("studied", "time", "pace"):
                    widget_html = render_widget_safely(
                        widget_id,
                        lambda: widget_generators[widget_id](row_span, col_span),
                    )
                elif widget_id == "retention":
                    widget_html = render_widget_safely(
                        widget_id,
                        lambda: _get_onigiri_retention_html(
                            row_span=row_span,
                            col_span=col_span,
                        ),
                    )
                elif widget_id == "onigimon":
                    try:
                        onigimon_row_span = int(row_span)
                    except (TypeError, ValueError):
                        onigimon_row_span = 2
                    try:
                        onigimon_col_span = int(col_span)
                    except (TypeError, ValueError):
                        onigimon_col_span = 1
                    widget_html = render_widget_safely(
                        widget_id,
                        lambda: _onigimon().render_widget_html(
                            row_span=onigimon_row_span,
                            col_span=onigimon_col_span,
                            grid_style=style,
                        ),
                    )
                elif widget_id == "ankimon_team":
                    widget_html = render_widget_safely(
                        widget_id,
                        lambda: render_ankimon_team_widget_html(
                            row_span=row_span,
                            col_span=col_span,
                        ),
                    )
                elif widget_id == "hexagon_land":
                    widget_html = render_widget_safely(
                        widget_id,
                        lambda: _hexagon_land().render_widget_html(
                            grid_style=style,
                        ),
                    )
                elif _is_deck_stats_widget_id(widget_id):
                    # row_span drives the compact fallback body inside the widget.
                    widget_html = render_widget_safely(
                        widget_id,
                        lambda: _learner_stats_widget()._render_widget(
                            self,
                            widget_id,
                            row_span=row_span,
                            col_span=col_span,
                        ),
                    )
                else:
                    widget_html = render_widget_safely(
                        widget_id,
                        widget_generators[widget_id],
                    )
                if not str(widget_html or "").strip():
                    continue
                # Onigimon and Hexagon Land are self-contained visual scenes.
                # Their root surface participates in the grid directly, so an
                # empty generic card cannot add a second border or title.
                if widget_id in ("onigimon", "hexagon_land"):
                    onigiri_grid_html += widget_html
                else:
                    onigiri_grid_html += (
                        f'<div class="onigiri-widget-container" '
                        f'style="{style}">{widget_html}</div>'
                    )

    # --- Part 2: Build External Add-on Widgets (into the same unified grid) ---
    external_hooks = patcher._get_external_hooks()
    deckline_available = any(
        _is_deckline_hook_id(patcher._get_hook_name(hook))
        for hook in external_hooks
    )
    external_layout = conf.get("externalWidgetLayout", {})
    grid_config, archive_config = _normalize_external_layout(external_layout)
    archived_external_hook_ids = _layout_item_ids(archive_config)
    external_widgets_html = ""
    deckline_compat_html = ""
    
    external_widgets_data = {}
    grid_hook_ids = set(grid_config.keys())
    deckline_auto_embed = conf.get("onigiriDecklineAutoEmbed", True)
    for hook in external_hooks:
        hook_id = patcher._get_hook_name(hook)
        # The native Ankimon team widget above replaces this legacy hook. Do
        # not execute it: it emits a fixed-size ``.poke-grid`` plus a complete
        # foreign stylesheet, which is exactly what breaks the unified grid.
        if _is_ankimon_team_hook_id(hook_id):
            continue
        should_render_grid_hook = hook_id in grid_hook_ids
        should_render_deckline_compat = (
            deckline_auto_embed
            and _is_deckline_hook_id(hook_id)
            and hook_id not in grid_hook_ids
            and hook_id not in archived_external_hook_ids
        )
        if not (should_render_grid_hook or should_render_deckline_compat):
            continue
        class TempContent: stats = ""
        temp_content = TempContent()
        try:
            hook(self, temp_content)
            external_widgets_data[hook_id] = temp_content.stats
        except Exception as e:
            external_widgets_data[hook_id] = f"<div style='color: red;'>Error in {hook_id}:<br>{e}</div>"

    if col_count > 0:
        for hook_id, widget_config in grid_config.items():
            hook_html = None
            if "learner_stats_widget" in hook_id:
                try:
                    from . import learner_stats_widget
                    try:
                        hook_row_span = int(widget_config.get("row_span", 2))
                    except (TypeError, ValueError):
                        hook_row_span = 2
                    hook_html = learner_stats_widget._render_widget(self, hook_id, row_span=hook_row_span)
                except Exception as e:
                    hook_html = f"<div style='color: red;'>Error rendering stats: {e}</div>"
            else:
                hook_html = external_widgets_data.get(hook_id)
                if hook_html is None:
                    hook_html = _render_registered_bento_home(hook_id)

            if hook_html:
                try:
                    pos = int(widget_config.get("grid_position", 0))
                except (TypeError, ValueError):
                    pos = 0
                row = pos // col_count + 1
                col = pos % col_count + 1
                try:
                    row_span = int(widget_config.get("row_span", 2))
                except (TypeError, ValueError):
                    row_span = 2
                row_span = max(2, row_span)
                try:
                    col_span = int(widget_config.get("column_span", 1))
                except (TypeError, ValueError):
                    col_span = 1
                col_span = min(col_count, max(1, col_span))
                style = f"grid-area: {row} / {col} / span {row_span} / span {col_span};"
                class_name = "external-widget-container"
                if _is_shige_leaderboard_hook_id(hook_id):
                    class_name += " shige-leaderboard-widget"
                # Add external widgets to the same grid as Onigiri widgets
                external_widgets_html += f'<div class="{class_name}" style="{style}">{hook_html}</div>'

    if deckline_auto_embed:
        for hook_id, hook_html in external_widgets_data.items():
            if (
                _is_deckline_hook_id(hook_id)
                and hook_id not in grid_config
                and hook_id not in archived_external_hook_ids
                and str(hook_html or "").strip()
            ):
                deckline_compat_html += (
                    '<div class="external-widget-container onigiri-deckline-compat-container" '
                    f'data-onigiri-external-hook="{html.escape(hook_id, quote=True)}">'
                    f"{hook_html}"
                    "</div>"
                )
        if deckline_compat_html:
            deckline_compat_html += """
            <style id="onigiri-deckline-compat-style">
                .onigiri-deckline-compat-container {
                    display: block !important;
                    width: 100%;
                    max-width: min(100%, 1180px);
                    height: auto !important;
                    min-height: 0 !important;
                    margin: 0 auto 15px auto;
                    overflow: visible !important;
                    flex: 0 0 auto !important;
                    box-sizing: border-box;
                }

                .onigiri-deckline-compat-container .deckline-cards,
                .onigiri-deckline-compat-container .deckline-cards-embedded {
                    height: auto !important;
                    max-height: none !important;
                    min-height: 0 !important;
                    width: 100%;
                }

                .onigiri-deckline-compat-container .deckline-list {
                    max-height: none !important;
                    overflow: visible !important;
                }

                .onigiri-deckline-compat-container .deckline-bottom-bar-shell {
                    margin-top: 10px;
                }
            </style>
            """

    # --- Part 3: Assemble the Final Stats Block ---
    # Combine both Onigiri and External widgets into a single unified grid
    unified_grid_html = onigiri_grid_html + external_widgets_html
    grid_gap = 15
    widget_layout_conf = conf.get("onigiriWidgetLayout", {})
    try:
        saved_grid_width = int(widget_layout_conf.get("grid_width", 250))
    except (TypeError, ValueError):
        saved_grid_width = 250
    grid_column_width = max(200, min(340, saved_grid_width))
    try:
        saved_widget_height = int(widget_layout_conf.get("widget_height", 150))
    except (TypeError, ValueError):
        saved_widget_height = 150
    grid_widget_height = max(120, min(320, saved_widget_height))

    # Layout Items applies its spacing as margins on each tile.  Those margins
    # are deliberately outside the tile's content box, but grid rows used to
    # stay at their pre-margin height.  A Spacious 24px top/bottom margin could
    # consequently remove 48px from a one-row tile and the container's hidden
    # overflow would cut off the widget's bottom.  Reserve the vertical margin
    # in every regular grid row, so a tile always retains its configured height
    # (and a smaller window scrolls the main content rather than cropping it).
    def _widget_margin_value(edge: str) -> int:
        try:
            value = int(float(mw.col.conf.get(
                f"modern_menu_widget_margin_{edge}", 0
            )))
        except (TypeError, ValueError):
            return 0
        # Match the CSS generator exactly. The settings UI limits this to
        # 240px, but legacy/manual collection values must still reserve all of
        # their applied spacing instead of reintroducing clipping.
        return max(0, value)

    widget_margin_top = _widget_margin_value("top")
    widget_margin_bottom = _widget_margin_value("bottom")
    grid_row_height = grid_widget_height + widget_margin_top + widget_margin_bottom
    grid_alignment = widget_layout_conf.get("grid_alignment", "center")
    if grid_alignment not in {"left", "center", "right"}:
        grid_alignment = "center"
    grid_justify_content = {"left": "start", "center": "center", "right": "end"}[grid_alignment]
    grid_align_items = {"left": "flex-start", "center": "center", "right": "flex-end"}[grid_alignment]
    grid_content_width = (col_count * grid_column_width) + (max(col_count - 1, 0) * grid_gap) if col_count > 0 else 1180
    grid_max_width = (
        max(1180, min(1800, grid_content_width))
        if col_count > 0
        else 1180
    )

    # Calculate row for stats_title to make its height min-content instead of grid_widget_height
    title_row = 1
    if "stats_title" in onigiri_layout and col_count > 0:
        pos = onigiri_layout["stats_title"].get("pos", 0)
        title_row = pos // col_count + 1
    grid_template_rows = " ".join([f"{grid_row_height}px"] * (title_row - 1)) + " min-content"
    title_margin_top = "12px" if title_row == 1 else "-5px"

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
            gap: {grid_gap}px;
            grid-template-rows: {grid_template_rows};
            grid-auto-rows: {grid_row_height}px;
            grid-template-columns: repeat({col_count}, minmax(0, {grid_column_width}px));
            justify-content: {grid_justify_content};
            width: 100%;
            max-width: {grid_max_width}px;
            box-sizing: border-box;
            overflow: visible;
        }}

        .injected-stats-block {{
            display: flex;
            flex-direction: column;
            align-items: {grid_align_items};
        }}

        .onigiri-widget-title {{
            width: 100%;
            max-width: {grid_content_width}px;
            box-sizing: border-box;
        }}

        /* As a grid widget the title fills its cell and sits on the vertical
           centre line, so it lines up with the stat cards beside it. */
        .onigiri-widget-container .onigiri-widget-title {{
            flex: 1;
            display: flex;
            align-items: flex-start;
            margin: {title_margin_top} 0 0 0;
            padding: 0;
            min-width: 0;
            max-width: 100%;
            overflow: hidden;
        }}

        .onigiri-menu-title {{
            position: relative;
            isolation: isolate;
            width: 100%;
            flex: 1;
            min-width: 0;
            box-sizing: border-box;
        }}
        .onigiri-menu-title.has-background {{
            min-height: 54px;
            padding: 12px 16px;
            border-radius: var(--onigiri-widget-border-radius, 20px);
            border: var(--onigiri-widget-border-width, 1px) solid var(--border, rgba(128, 128, 128, 0.24));
            overflow: hidden;
        }}
        .onigiri-menu-title-background {{
            position: absolute;
            inset: 0;
            z-index: -1;
            pointer-events: none;
            background-size: cover;
            background-position: center;
        }}
        .onigiri-widget-container .onigiri-menu-title .onigiri-widget-title {{
            justify-content: var(--menu-title-alignment, left);
            text-align: var(--menu-title-alignment, left);
        }}
        .onigiri-widget-container .onigiri-menu-title.has-background .onigiri-widget-title {{
            margin: 0;
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

        .external-widget-container.shige-leaderboard-widget {{
            overflow: visible;
            min-height: 100%;
            z-index: 2;
        }}

        .external-widget-container.shige-leaderboard-widget #shige-lb-container {{
            width: 100%;
        }}

        /* Force the inner content (cards, heatmap, favorites) to fill the container */
        .stat-card, #onigiri-heatmap-container, .onigiri-favorites-widget, .onigimon-card, .hex-land-preview, .prep-station-widget, .hashi-notes-widget, .onigiri-ankimon-team-widget {{
            flex: 1;
            width: 100%;
            height: 100%;
            box-sizing: border-box;
        }}

        /* Ankimon team — deliberately small, neutral, and grid-contained.
           These rules never target Ankimon's legacy .poke-grid, so a normal
           Ankimon screen remains untouched. */
        .onigiri-ankimon-team-widget {{
            display: flex;
            flex-direction: column;
            min-width: 0;
            min-height: 0;
            padding: var(--onigiri-widget-pad, 12px);
            border: var(--onigiri-box-effect-stroke, 1px) solid var(--onigiri-box-effect-border, var(--border, rgba(128,128,128,.22)));
            border-radius: var(--onigiri-box-effect-radius, 14px);
            background: var(--onigiri-box-effect-bg, var(--canvas-inset, rgba(128,128,128,.08)));
            color: var(--onigiri-box-effect-fg, var(--fg, inherit));
            box-shadow: none !important;
            backdrop-filter: blur(var(--onigiri-box-effect-blur, 0px));
            -webkit-backdrop-filter: blur(var(--onigiri-box-effect-blur, 0px));
            overflow: hidden;
        }}
        .onigiri-ankimon-team-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            margin: 0 0 8px;
            font-size: var(--font-size-small-title, 13px);
            font-weight: 700;
            line-height: 1;
        }}
        .onigiri-ankimon-team-head em {{
            display: inline-flex;
            min-width: 18px;
            height: 18px;
            align-items: center;
            justify-content: center;
            padding: 0 4px;
            border-radius: 999px;
            background: var(--accent-color, #00a982);
            color: #fff;
            font-size: 10px;
            font-style: normal;
        }}
        .onigiri-ankimon-team-list {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(min(92px, 100%), 1fr));
            gap: 7px;
            flex: 1;
            min-width: 0;
            min-height: 0;
            align-content: center;
        }}
        .onigiri-ankimon-team-member {{
            display: grid;
            grid-template-columns: 1fr;
            grid-template-rows: minmax(0, 1fr) auto auto auto;
            justify-items: center;
            gap: 2px;
            min-width: 0;
            min-height: 0;
            padding: 5px 3px;
            border: 1px solid transparent;
            border-radius: 10px;
            background: transparent;
            color: inherit;
            font: inherit;
            cursor: pointer;
            overflow: hidden;
            box-shadow: none !important;
        }}
        .onigiri-ankimon-team-member:hover {{
            background: color-mix(in srgb, var(--accent-color, #00a982) 10%, transparent);
        }}
        .onigiri-ankimon-team-sprite {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            min-height: 0;
            overflow: hidden;
        }}
        .onigiri-ankimon-team-sprite img {{
            display: block;
            width: min(100%, 74px);
            height: min(100%, 74px);
            max-height: 74px;
            object-fit: contain;
            image-rendering: pixelated;
            image-rendering: crisp-edges;
        }}
        .onigiri-ankimon-team-name {{
            width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 10px;
            font-weight: 650;
            line-height: 1.1;
        }}
        .onigiri-ankimon-team-level {{
            font-size: 9px;
            opacity: .62;
            line-height: 1;
        }}
        .onigiri-ankimon-team-types {{
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 3px;
            width: 100%;
            min-width: 0;
            margin-top: 3px;
            box-sizing: border-box;
            white-space: normal !important;
        }}
        .onigiri-ankimon-team-type {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 0;
            max-width: 100%;
            padding: 2px 4px;
            box-sizing: border-box;
            border-radius: 999px;
            background: var(--pokemon-type-bg, #8a8d91);
            color: var(--pokemon-type-fg, #fff);
            font-size: 7px;
            font-weight: 700;
            line-height: 1;
            white-space: nowrap;
            overflow: visible;
        }}
        .onigiri-ankimon-team-initial {{
            font-size: 18px;
            opacity: .55;
        }}

        /* Prep Station widget */
        .prep-station-widget {{
            display: flex;
            flex-direction: column;
            gap: 6px;
            padding: var(--onigiri-widget-pad);
            cursor: pointer;
            overflow: hidden;
            font-family: inherit;
            /* background + border-radius/width fall back here, then get
               overridden !important by the Widget Color & Effect settings */
            background-color: var(--canvas-inset, #f2f2f2);
            border: 1px solid var(--border, rgba(128, 128, 128, 0.24));
            border-radius: 15px;
        }}
        .prep-widget-empty {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: calc(11px * var(--prep-fs, 1));
            opacity: 0.45;
            font-style: italic;
        }}

        /* Mini exam-card previews, echoing the Prep Station dialog's ExamCard.
           grid-template-columns is set inline per-instance to the widget's
           configured slot count, so a card only ever occupies one column's
           width even when fewer plans than slots are active. */
        .prep-plan-cards {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
            flex: 1;
            min-height: 0;
        }}
        .prep-plan-card {{
            min-width: 0;
            min-height: 0;
            display: flex;
            flex-direction: column;
            border-radius: 12px;
            overflow: hidden;
            background: var(--canvas-inset, #f2f2f2);
            border: 1px solid var(--border, rgba(128, 128, 128, 0.24));
        }}
        .prep-card-band {{
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            flex: 0 0 auto;
            padding: 6px 7px;
            min-height: 40%;
            color: #ffffff;
        }}
        .prep-card-band-top {{
            display: flex;
            align-items: flex-start;
            justify-content: flex-end;
        }}
        .prep-card-name-row {{
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 4px;
            min-width: 0;
        }}
        .prep-card-icon {{
            font-size: 13px;
            line-height: 1;
            flex-shrink: 0;
        }}
        img.prep-card-icon {{
            width: 13px;
            height: 13px;
            object-fit: contain;
            display: block;
            flex-shrink: 0;
        }}
        .prep-card-badge {{
            font-size: calc(7px * var(--prep-fs, 1));
            font-weight: 700;
            white-space: nowrap;
            background: rgba(0, 0, 0, 0.35);
            padding: 2px 5px;
            border-radius: 8px;
        }}
        .prep-card-name {{
            font-size: calc(10px * var(--prep-fs, 1));
            font-weight: 700;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            letter-spacing: -0.01em;
            text-align: left;
        }}
        .prep-card-body {{
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            flex: 1;
            min-height: 0;
            padding: 6px 7px 7px 7px;
            gap: 4px;
        }}
        .prep-card-pace {{
            display: flex;
            align-items: baseline;
            gap: 3px;
            min-width: 0;
        }}
        .prep-card-pace-num {{
            font-size: calc(17px * var(--prep-fs, 1));
            font-weight: 700;
            line-height: 1;
        }}
        .prep-card-pace-unit {{
            font-size: calc(8px * var(--prep-fs, 1));
            opacity: 0.55;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .prep-card-progress {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .prep-card-progress-track {{
            flex: 1;
            height: 4px;
            border-radius: 2px;
            background: var(--border, rgba(128, 128, 128, 0.25));
            overflow: hidden;
        }}
        .prep-card-progress-fill {{
            height: 100%;
            border-radius: 2px;
        }}
        .prep-card-progress-label {{
            font-size: calc(8px * var(--prep-fs, 1));
            opacity: 0.55;
            white-space: nowrap;
            flex-shrink: 0;
        }}

        .hex-land-preview {{
            position: relative;
            flex: 1;
            width: 100%;
            min-width: 0;
            min-height: 0;
            height: 100%;
            border-radius: 14px;
            overflow: hidden;
            background-color: var(--hl-bottom, #1597d1);
            background-image: linear-gradient(180deg, var(--hl-top, #48c0ee), var(--hl-bottom, #1597d1));
        }}

        .hex-land-preview.disabled {{
            display: grid;
            place-items: center;
            padding: var(--onigiri-widget-pad);
            box-sizing: border-box;
            background: var(--canvas-inset, #ffffff);
            color: var(--fg, #222);
        }}

        .hex-land-preview-stage {{
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%) scale(var(--hl-scale, .72));
            transform-origin: center;
        }}

        .hex-land-preview img,
        .hex-land-preview svg {{
            position: absolute;
            user-select: none;
            -webkit-user-drag: none;
        }}

        .hex-land-preview .hl-tile {{
            width: 65px;
        }}

        .hex-land-copy {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 10px;
            min-width: 0;
        }}

        .hex-land-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }}

        .hex-land-header h3,
        .hex-land-copy h3 {{
            margin: 0;
            font-size: 22px;
            line-height: 1.15;
            font-weight: 900;
            color: var(--fg, #111);
        }}

        .hex-land-header button {{
            width: 25px;
            height: 25px;
            border: 0;
            border-radius: 999px;
            background: #f5bf36;
            color: #3b2604;
            font-weight: 900;
            cursor: pointer;
        }}

        .hex-land-stats {{
            display: flex;
            flex-direction: column;
            gap: 9px;
            min-width: 0;
        }}

        .hex-land-stat-row {{
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
        }}

        .hex-land-stat-icon {{
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }}

        .hex-land-stat-sprite {{
            display: block;
            max-width: 31px;
            max-height: 31px;
            object-fit: contain;
        }}

        .hex-land-stat-sprite.tree {{
            max-height: 34px;
        }}

        .hex-land-stat-text {{
            min-width: 0;
            text-align: center;
            font-size: 15px;
            line-height: 1.1;
            font-weight: 900;
            color: var(--fg, #111);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .hex-land-coin-fallback {{
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
        }}

        .hex-land-coins {{
            font-size: 18px;
            font-weight: 900;
            color: #1f6f87;
        }}

        .hex-land-meta,
        .hex-land-copy p {{
            margin: 0;
            color: var(--fg-subtle, #757575);
            font-size: 12px;
            line-height: 1.35;
        }}

        .hex-land-mats {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: auto;
        }}

        .hex-land-mats span {{
            padding: 5px 7px;
            border-radius: 999px;
            background: color-mix(in srgb, #58af82 14%, transparent);
            font-size: 11px;
            font-weight: 800;
        }}

        .onigimon-card, .onigimon-card * {{
            font-family: "Silkscreen", var(--font-main), Nunito, sans-serif !important;
        }}

        .onigimon-main,
        .onigimon-inventory {{
            display: flex;
            align-items: center;
        }}

        .onigimon-body {{
            display: flex;
            flex-direction: column;
            gap: 6px;
            flex: 1;
            min-height: 0;
        }}

        /* One continuous card: coloured top section (sprite + name) fused to a
           neutral lower section (stat meters) with a flat seam. The card owns
           the border and corners so the two sections meet with no gap. */
        .onigimon-card {{
            display: flex;
            flex-direction: column;
            flex: 1;
            width: 100%;
            height: 100%;
            box-sizing: border-box;
            min-height: 0;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border, #e0e0e0);
            cursor: pointer;
        }}

        .onigimon-card-disabled {{
            display: grid;
            place-items: center;
            padding: var(--onigiri-widget-pad);
            background: var(--canvas-inset, #ffffff);
            color: var(--fg, #222);
            text-align: center;
        }}

        .onigimon-header span,
        .onigimon-info span {{
            color: var(--fg-subtle, #757575);
            font-size: 12px;
        }}
        
        .onigimon-ball-btn {{
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
        }}

        .onigimon-ball-btn:hover {{
            background: var(--accent-color, #007aff);
            border-color: var(--accent-color, #007aff);
            box-shadow: 0 4px 8px color-mix(in srgb, var(--accent-color, #007aff) 30%, transparent);
            transform: translateY(-1px);
        }}

        .onigimon-ball-icon {{
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
        }}

        .onigimon-ball-btn:hover .onigimon-ball-icon {{
            background-color: #ffffff;
        }}

        .onigimon-main {{
            gap: 12px;
            min-height: 52px;
        }}

        .onigimon-scene {{
            position: relative;
            border: 1px solid var(--border, #e0e0e0);
            border-radius: 12px;
            padding: 10px;
            box-sizing: border-box;
            overflow: hidden;
            isolation: isolate;
        }}

        .onigimon-scene::before {{
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
        }}

        .onigimon-scene-bg {{
            position: absolute;
            inset: -12px;
            transform: scale(1.05);
            opacity: var(--onigimon-scene-opacity, 0.9);
            z-index: 0;
            pointer-events: none;
        }}

        .onigimon-scene::after {{
            content: "";
            position: absolute;
            inset: 0;
            background: color-mix(in srgb, var(--canvas-inset, #ffffff) 16%, transparent);
            z-index: 1;
        }}

        .onigimon-scene > * {{
            position: relative;
            z-index: 2;
        }}

        .onigimon-scene > .onigimon-scene-bg {{
            position: absolute;
            z-index: 0;
        }}

        /* Coloured top section. Reuses .onigimon-scene for the background
           image/blur machinery, but drops the scene's own border and radius —
           the enclosing .onigimon-card owns the grey border + corners. */
        .onigimon-top {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 14px;
            min-height: 80px;
            box-sizing: border-box;
            flex: 0 0 auto;
        }}

        /* Combined selector so these win over the later `.onigimon-scene` block
           (padding/border/radius) — the top section is applied as
           `class="onigimon-top onigimon-scene"`. */
        .onigimon-top.onigimon-scene {{
            border: none;
            border-radius: 0;
            padding: 16px 14px;
            background: radial-gradient(
                circle at 22% 32%,
                color-mix(in srgb, var(--onigimon-color, #6ea96a) 92%, white 8%) 0%,
                var(--onigimon-color, #6ea96a) 70%,
                color-mix(in srgb, var(--onigimon-color, #6ea96a) 90%, black 10%) 100%
            ) !important;
        }}

        /* Fixed 96px companion sprite. */
        .onigimon-top .onigimon-sprite {{
            position: relative;
            width: 96px;
            height: 96px;
            flex: 0 0 96px;
            border-radius: 0;
            background: transparent;
        }}

        .onigimon-top .onigimon-sprite img {{
            width: 86px;
            height: 86px;
            position: relative;
            z-index: 1;
        }}

        /* Name and level sit on the coloured section, so they take fixed
           per-mode colours instead of the theme's foreground variables. */
        .onigimon-top .onigimon-info strong {{
            color: #000000;
        }}

        .night-mode .onigimon-top .onigimon-info strong {{
            color: #ffffff;
        }}

        .onigimon-top .onigimon-info span {{
            color: rgba(0, 0, 0, 0.68);
        }}

        .night-mode .onigimon-top .onigimon-info span {{
            color: rgba(255, 255, 255, 0.82);
        }}

        /* Neutral lower section (stat meters), matching the Prep Station card
           body shade in both modes. */
        .onigimon-bottom {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 10px;
            padding: 12px 14px;
            flex: 1 1 auto;
            min-height: 0;
            overflow: hidden;
            background: #efefec;
            color: var(--fg, #222);
        }}

        /* The identity is the heading for the meter panel: it gives the
           readings an immediate owner while leaving the companion centred in
           the scene above (or to the left on wide cards). */
        .onigimon-bottom .onigimon-info {{
            width: 100%;
            padding-bottom: 8px;
            border-bottom: 1px solid color-mix(in srgb, currentColor 12%, transparent);
        }}

        .onigimon-bottom .onigimon-info strong {{
            color: inherit;
            font-size: 15px;
        }}

        .onigimon-bottom .onigimon-info > span {{
            color: inherit;
            font-size: 10px;
            opacity: 0.68;
        }}

        .night-mode .onigimon-bottom {{
            background: #2e2e2d;
        }}

        /* `color: inherit` so a user-chosen stats-panel colour (set inline on
           .onigimon-bottom from Gamification Settings) also drives the meter
           text; with var(--fg) the labels stayed dark on a dark panel. */
        .onigimon-bottom .onigimon-meter span,
        .onigimon-bottom .onigimon-meter b {{
            color: inherit;
            text-align: left;
            justify-self: start;
        }}

        .onigimon-bottom .onigimon-meter b {{
            text-align: right;
            justify-self: end;
        }}

        .onigimon-bottom .onigimon-meter > div {{
            background: color-mix(in srgb, currentColor 14%, transparent);
        }}

        .onigimon-meters {{
            display: flex;
            flex-direction: column;
            gap: 5px;
            width: 100%;
            min-width: 0;
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

        .onigimon-scene .onigimon-sprite {{
            background: transparent;
        }}

        .onigimon-pixel-sprite,
        .onigimon-sprite img {{
            -ms-interpolation-mode: nearest-neighbor;
            image-rendering: -webkit-optimize-contrast;
            image-rendering: crisp-edges;
            image-rendering: pixelated;
        }}

        .onigimon-sprite img {{
            width: 54px;
            height: 54px;
            object-fit: contain;
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
            text-align: left;
            justify-items: start;
        }}

        .onigimon-info strong {{
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .onigimon-meter {{
            display: grid;
            grid-template-columns: 68px 34px minmax(0, 1fr);
            gap: 6px;
            align-items: center;
            font-size: 12px;
        }}

        .onigimon-meter b {{
            color: var(--fg, #222);
            font-weight: 800;
            text-align: right;
            font-variant-numeric: tabular-nums;
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

        /* Extra rows become a compact companion dashboard rather than empty
           meter-panel padding. All values come from the same payload as the
           care window, so the larger footprint remains useful at a glance. */
        .onigimon-growth {{
            display: grid;
            gap: 6px;
            width: 100%;
            padding-top: 9px;
            border-top: 1px solid color-mix(in srgb, currentColor 12%, transparent);
        }}

        .onigimon-growth-head {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto auto;
            align-items: baseline;
            gap: 7px;
            font-size: 10px;
        }}

        .onigimon-growth-head span {{
            overflow: hidden;
            text-overflow: ellipsis;
            color: inherit !important;
            font-size: inherit !important;
        }}

        .onigimon-growth-head b {{
            font-size: 10px;
        }}

        .onigimon-growth-head em {{
            font-size: 8px;
            font-style: normal;
            opacity: 0.64;
            white-space: nowrap;
        }}

        .onigimon-growth-track {{
            height: 6px;
            overflow: hidden;
            border-radius: 999px;
            background: color-mix(in srgb, currentColor 14%, transparent);
        }}

        .onigimon-growth-track i {{
            display: block;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, #8b6ce0, #c866e5);
        }}

        .onigimon-quick-stats,
        .onigimon-battle-stats {{
            display: grid;
            gap: 7px;
            width: 100%;
        }}

        .onigimon-quick-stats {{
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }}

        .onigimon-battle-stats {{
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }}

        .onigimon-quick-stat {{
            display: grid;
            justify-items: start;
            gap: 3px;
            min-width: 0;
            padding: 8px 9px;
            border-radius: 9px;
            background: color-mix(in srgb, currentColor 8%, transparent);
        }}

        .onigimon-quick-stat span {{
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            color: inherit !important;
            font-size: 8px !important;
            line-height: 1.15;
            opacity: 0.68;
            white-space: nowrap;
        }}

        .onigimon-quick-stat b {{
            color: inherit;
            font-size: 13px;
            line-height: 1;
            font-variant-numeric: tabular-nums;
        }}

        .onigimon-card-tall > .onigimon-top {{
            flex: 0 0 36%;
            justify-content: center;
        }}

        .onigimon-card-tall > .onigimon-bottom {{
            justify-content: space-evenly;
            gap: 9px;
            padding: 14px;
        }}

        .onigimon-card-extra-tall > .onigimon-top .onigimon-sprite {{
            width: 112px;
            height: 112px;
            flex-basis: 112px;
        }}

        .onigimon-card-extra-tall > .onigimon-top .onigimon-sprite img {{
            width: 102px;
            height: 102px;
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

        /* Compact 1-row Onigimon widget: just the companion over its background */
        .onigimon-card-compact {{
            padding: 8px;
            gap: 0;
        }}

        .onigimon-scene-compact {{
            flex: 1;
            width: 100%;
            height: 100%;
            min-height: 0;
            justify-content: center;
        }}

        .onigimon-scene-compact .onigimon-sprite {{
            width: 64px;
            height: 64px;
            flex: 0 0 64px;
        }}

        .onigimon-scene-compact .onigimon-sprite img {{
            width: 60px;
            height: 60px;
        }}

        /* 1x2: the compact scene gains the name/level beside the companion, so
           the pair is centred as a group instead of the sprite alone. */
        .onigimon-span-1x2 .onigimon-scene-compact {{
            gap: 14px;
            padding: 10px 16px;
        }}

        .onigimon-span-1x2 .onigimon-scene-compact .onigimon-info strong {{
            font-size: 15px;
            color: #000000;
        }}

        .night-mode .onigimon-span-1x2 .onigimon-scene-compact .onigimon-info strong {{
            color: #ffffff;
        }}

        .onigimon-span-1x2 .onigimon-scene-compact .onigimon-info span {{
            color: rgba(0, 0, 0, 0.68);
        }}

        .night-mode .onigimon-span-1x2 .onigimon-scene-compact .onigimon-info span {{
            color: rgba(255, 255, 255, 0.82);
        }}

        /* Two-column footprints use the coloured scene as a left rail and the
           companion dashboard on the right. */
        .onigimon-card-wide {{
            flex-direction: row;
        }}

        .onigimon-card-wide > .onigimon-top {{
            flex: 1 1 50%;
            min-width: 0;
            flex-direction: column;
            justify-content: center;
            gap: 8px;
            text-align: center;
        }}

        .onigimon-card-wide > .onigimon-top .onigimon-info {{
            justify-items: center;
            text-align: center;
            max-width: 100%;
        }}

        .onigimon-card-wide > .onigimon-top .onigimon-sprite {{
            width: 96px;
            height: 96px;
            flex: 0 0 96px;
        }}

        .onigimon-card-wide > .onigimon-top .onigimon-sprite img {{
            width: 88px;
            height: 88px;
        }}

        .onigimon-card-wide > .onigimon-bottom {{
            flex: 1 1 50%;
            min-width: 0;
            gap: 8px;
            padding: 14px 16px;
        }}

        .onigimon-card-wide.onigimon-card-tall > .onigimon-top {{
            flex-basis: 42%;
        }}

        .onigimon-card-wide.onigimon-card-tall > .onigimon-bottom {{
            flex-basis: 58%;
        }}

        .onigimon-card-wide.onigimon-card-extra-tall > .onigimon-top .onigimon-sprite {{
            width: 132px;
            height: 132px;
            flex-basis: 132px;
        }}

        .onigimon-card-wide.onigimon-card-extra-tall > .onigimon-top .onigimon-sprite img {{
            width: 120px;
            height: 120px;
        }}

        /* A 1x2 card is the tightest layout that includes all five meters.
           Give the dashboard enough vertical room so its heading stays below
           the seam and Hunger is never clipped, while preserving a centered
           companion scene above it. */
        .onigimon-card.onigimon-span-2x1 > .onigimon-top {{
            flex: 0 0 40%;
            min-height: 0;
            padding: 8px 10px;
        }}

        .onigimon-card.onigimon-span-2x1 > .onigimon-top .onigimon-sprite {{
            width: 86px;
            height: 86px;
            flex-basis: 86px;
        }}

        .onigimon-card.onigimon-span-2x1 > .onigimon-top .onigimon-sprite img {{
            width: 82px;
            height: 82px;
        }}

        .onigimon-card.onigimon-span-2x1 > .onigimon-bottom {{
            justify-content: flex-start;
            gap: 6px;
            padding: 8px 10px;
        }}

        .onigimon-card.onigimon-span-2x1 > .onigimon-bottom .onigimon-info {{
            gap: 1px;
            padding-bottom: 5px;
        }}

        .onigimon-card.onigimon-span-2x1 > .onigimon-bottom .onigimon-info strong {{
            font-size: 14px;
            line-height: 1.2;
        }}

        .onigimon-card.onigimon-span-2x1 > .onigimon-bottom .onigimon-info > span {{
            font-size: 9px;
            line-height: 1.2;
        }}

        .onigimon-card.onigimon-span-2x1 .onigimon-meters {{
            gap: 4px;
        }}

        .onigimon-card.onigimon-span-2x1 .onigimon-meter {{
            grid-template-columns: 62px 30px minmax(0, 1fr);
            gap: 5px;
            font-size: 10px;
            line-height: 1.2;
        }}

        .onigimon-card.onigimon-span-2x1 .onigimon-meter > div {{
            height: 6px;
        }}

        /* Keep the companion identity centered in the 2x3 dashboard. */
        .onigimon-card.onigimon-span-3x2 > .onigimon-bottom .onigimon-info {{
            justify-items: center;
            text-align: center;
        }}

        /* Restaurant Level Widget Styles */
        .onigiri-restaurant-level-widget {{
            display: flex;
            flex-direction: column;
            background: var(--canvas-inset, #f5f5f5);
            border-radius: var(--onigiri-box-effect-radius, 15px);
            overflow: hidden;
            height: 100%;
            border: 1px solid var(--border, #e0e0e0);
            /* cursor: pointer; removed - only image is clickable */
            transition: all 0.3s ease;
            position: relative;
        }}

        .rl-widget-head {{
            padding: var(--onigiri-widget-pad) var(--onigiri-widget-pad) 0;
        }}

        /* The building and the level column sit below the header row; this is
           the part the orientation setting flips, not the widget itself. */
        .rl-widget-body {{
            display: flex;
            flex-direction: row;
            flex: 1;
            min-height: 0;
            min-width: 0;
        }}

        .onigiri-restaurant-level-widget.orientation-vertical .rl-widget-body {{
            flex-direction: column;
        }}

        .onigiri-restaurant-level-widget.expanded-view {{
            background: var(--theme-bg) !important;
            border-color: transparent;
        }}

        /* Expanded view is the building alone, edge to edge. */
        .onigiri-restaurant-level-widget.expanded-view .rl-widget-head {{
            display: none;
        }}
        
        .night .onigiri-restaurant-level-widget {{
            background: var(--canvas-inset, #2c2c2c);
            border-color: var(--border, #e0e0e0);
        }}

        .restaurant-image-container {{
            flex: 0 0 45%; /* Fixed width percentage */
            display: flex;
            align-items: center;
            justify-content: center;
            /* Let the widget's backdrop supply the opacity behind the sprite. */
            background: transparent;
            padding: calc(10px * var(--onigiri-widget-pad-scale));
            position: relative;
            transition: all 0.3s ease;
            box-sizing: border-box;
            min-width: 0;
            min-height: 0;
            overflow: hidden;
        }}

        .onigiri-restaurant-level-widget.orientation-vertical .restaurant-image-container {{
            flex: 1 1 0;
            width: 100%;
            height: auto;
            aspect-ratio: auto;
            min-height: 0;
            padding: calc(8px * var(--onigiri-widget-pad-scale))
                     calc(10px * var(--onigiri-widget-pad-scale))
                     0
                     calc(10px * var(--onigiri-widget-pad-scale));
        }}

        /* Unrestricted Sidebar resizing */
        .sidebar-left {{
            max-width: none !important;
        }}

        .main-content {{
            /* Dynamic Padding based on col_count. Top padding is explicitly 10px to align with sidebar top */
            padding: 10px {24 if col_count == 4 else (14 if col_count > 4 else 32)}px {24 if col_count == 4 else (14 if col_count > 4 else 32)}px {24 if col_count == 4 else (14 if col_count > 4 else 32)}px !important;
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
            padding: calc(5px * var(--onigiri-widget-pad-scale)); /* Reduced padding to make image larger */
            z-index: 10;
        }}
        
        .restaurant-image {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            transition: transform 0.3s ease;
        }}
        
        .onigiri-restaurant-level-widget:hover .restaurant-image {{
            transform: scale(1.05);
        }}
        
        .onigiri-restaurant-level-widget.expanded-view .restaurant-image {{
            transform: scale(1.0);
        }}

        /* Compact 1-row Nook Level widget: just the building over its theme background */
        .onigiri-restaurant-level-widget-compact {{
            cursor: pointer;
        }}

        .onigiri-restaurant-level-widget-compact .restaurant-image-container {{
            flex: 1;
            width: 100%;
            height: 100%;
            padding: calc(10px * var(--onigiri-widget-pad-scale));
            background: var(--theme-bg, var(--canvas-inset, #f5f5f5));
        }}

        .restaurant-info {{
            flex: 1;
            min-width: 0;
            display: flex;
            flex-direction: column;
            justify-content: center;
            /* Only the top inset is this block's own -- it spaces the level text
               off the head/image above it. The other three are the widget's
               shared edge gutter. */
            padding: calc(8px * var(--onigiri-widget-pad-scale))
                     var(--onigiri-widget-pad)
                     var(--onigiri-widget-pad);
            gap: 15px;
            transition: opacity 0.2s ease;
        }}

        .onigiri-restaurant-level-widget.orientation-vertical .restaurant-info {{
            flex: 0 0 auto;
            padding: calc(6px * var(--onigiri-widget-pad-scale))
                     var(--onigiri-widget-pad)
                     var(--onigiri-widget-pad);
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
            z-index: 20;
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
            justify-content: center;
            transition: all 0.2s ease;
            color: var(--fg-subtle, #757575);
            box-shadow: none !important;
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
        }}
    </style>
    {deckline_compat_html}
    <div class="unified-grid">{unified_grid_html}</div>
    """

    # --- Part 4: Manually Build the Deck Tree HTML ---
    # CRITICAL: Store tree data for Anki's context menu operations (e.g., deck deletion)
    # Anki's native _delete method expects self._render_data.tree to exist
    tree_data = self.mw.col.sched.deck_due_tree()
    self._render_data = RenderData(tree=tree_data)
    sidebar_content_mode = str(conf.get("sidebarContentMode", "decks")).lower()
    if sidebar_content_mode not in {"decks", "tags"}:
        sidebar_content_mode = "decks"
    if sidebar_content_mode == "tags":
        tree_html = deck_tree_updater._render_tag_tree_html(self)
        sidebar_content_title = tr("tags_header", "TAGS")
        sidebar_search_placeholder = tr("search_tags", "Search tags…")
        sidebar_search_title = tr("search_tags", "Search tags")
        sidebar_list_class = "is-tags-mode"
        sidebar_table_class = "onigiri-tag-table"
    else:
        tree_html = deck_tree_updater._render_deck_tree_html_only(self)
        sidebar_content_title = tr("decks_header", "DECKS")
        sidebar_search_placeholder = tr("search_decks", "Search decks…")
        sidebar_search_title = tr("search_decks", "Search decks")
        sidebar_list_class = "is-decks-mode"
        sidebar_table_class = ""
    
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
    is_collapsed = _col_conf_get("onigiri_sidebar_collapsed", False)
    try:
        deck_cycle_state = int(_col_conf_get("onigiri_deck_cycle_state", -1))
    except (TypeError, ValueError):
        deck_cycle_state = -1
    if deck_cycle_state < 0 or deck_cycle_state > 4:
        deck_cycle_state = 1 if _col_conf_get("onigiri_deck_focus_mode", False) else 0
    sidebar_position = _col_conf_get("modern_menu_sidebar_position", conf.get("sidebarPosition", "left"))
    if sidebar_position not in {"left", "right", "center"}:
        sidebar_position = "left"
    if sidebar_position == "center":
        deck_cycle_state = 4
    is_focused = deck_cycle_state in (1, 2)
    is_cycle_sidebar_only = deck_cycle_state in (2, 3, 4)
    is_cycle_stacked = deck_cycle_state == 4
    
    # Check for Sidebar Only Mode (0 columns or 0 rows)
    is_sidebar_only = (col_count == 0 or conf.get('unifiedGridRows', 6) == 0)
    
    sidebar_initial_class = ""
    if is_collapsed:
        sidebar_initial_class += "sidebar-collapsed"
    if is_focused:
        sidebar_initial_class += " deck-focus-mode" if sidebar_initial_class else "deck-focus-mode"
    if is_sidebar_only or is_cycle_sidebar_only:
        sidebar_initial_class += " sidebar-only-mode" if sidebar_initial_class else "sidebar-only-mode"

    # --- MODIFICATION START ---
    
    # Build the dynamic profile bar HTML
    user_name = conf.get("userName", "USER")
    
    profile_bg_mode = _col_conf_get("modern_menu_profile_bg_mode", "image")
    bg_class_str = ""
    bg_style_str, bg_layer_style = _profile_background_render_parts(addon_package)
    bg_layer_html = f'<div class="profile-bg-layer" style="{bg_layer_style}"></div>' if bg_layer_style else ""
    if profile_bg_mode == "image":
        bg_class_str = "with-image-bg"
        if not _profile_bg_image_name() and _col_conf_get("modern_menu_profile_bg_dynamic_mode", True):
            bg_class_str += " dynamic-default-bg"
    
    profile_pic_html_expanded = _get_profile_pic_html(user_name, addon_package)

    rl_chip = ""
    rl_theme_color = ""
    restaurant_conf = conf.get("restaurant_level", {})
    if not restaurant_conf:
        restaurant_conf = conf.get("achievements", {}).get("restaurant_level", {})
    show_profile_bar_progress = restaurant_conf.get(
        "show_profile_bar_progress",
        restaurant_conf.get("show_profile_bar", restaurant_conf.get("showProfileBar", True)),
    )
    if restaurant_conf.get("enabled") and show_profile_bar_progress:
        nook_level = _nook_level()
        rl_payload = nook_level.manager.get_progress_payload()
    else:
        rl_payload = {}
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
        chip_style_str = nook_level.build_chip_style_attr()
        chip_style_attr = f' style="{chip_style_str}"' if chip_style_str else ""
        rl_chip = f"""
        <div class="restaurant-level-chip" title="{xp_detail}"{chip_style_attr}>
            <span class="rl-chip-level">{tr('level_prefix')} {rl_payload.get('level', 0)}</span>
            <div class="rl-chip-progress">
                <div class="rl-chip-progress-fill" style="width: {fill_width}"></div>
            </div>
        </div>
        """.strip()

    safe_user_name = html.escape(str(user_name), quote=False)
    profile_bar_contents = (
        '<div class="profile-content profile-content-main">'
        f"{profile_pic_html_expanded}"
        f"<span class=\"profile-name\">{safe_user_name}</span>"
    )
    if rl_chip:
        profile_bar_contents += rl_chip
    profile_bar_contents += "</div>"
    
    # Inject CSS for theme colors if a theme is active
    theme_css = ""
    if rl_chip:
        chip_vals = nook_level.get_chip_style_values()
        rl_theme_color = chip_vals.get("progress", "")

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
    search_header_icon_html = _sidebar_header_icon_markup(
        "modern_menu_icon_header_search", "search.svg", "search-btn-icon", addon_package
    )
    sort_header_icon_html = _sidebar_header_icon_markup(
        "modern_menu_icon_header_sort", "sort_default.svg", "sort-btn-icon", addon_package
    )
    home_button_html = _build_archived_home_button(conf, addon_package)
    ready_marker_html = _build_hidden_ready_marker(addon_package)

    section_order = {
        section_id: index for index, section_id in enumerate(_sidebar_section_order())
    }
    theme_css += f"""
    <style id="onigiri-sidebar-section-order">
        .onigiri-sidebar-profile-section {{ order: {section_order['profile']}; }}
        .onigiri-sidebar-actions-section {{ order: {section_order['actions']}; }}
        .onigiri-ready-sidebar {{ order: {section_order['ready_to_go']}; }}
        .onigiri-sidebar-decks-section {{ order: {section_order['decks']}; }}
    </style>
    """

    # --- Custom profile name color (light/dark aware) ---
    name_dynamic = _col_conf_get("modern_menu_profile_name_dynamic_mode", True)
    name_light = _col_conf_get(
        "modern_menu_profile_name_color_light",
        config.DEFAULTS["colors"]["light"]["--fg"],
    )
    name_dark = _col_conf_get(
        "modern_menu_profile_name_color_dark",
        config.DEFAULTS["colors"]["dark"]["--fg"],
    ) if name_dynamic else name_light
    level_light = _col_conf_get(
        "modern_menu_profile_level_color_light",
        config.DEFAULT_PROFILE_LEVEL_COLOR,
    )
    level_dark = _col_conf_get(
        "modern_menu_profile_level_color_dark",
        config.DEFAULT_PROFILE_LEVEL_COLOR,
    ) if name_dynamic else level_light
    theme_css += f"""
    <style id="profile-name-color">
        .profile-bar .profile-name,
        .onigiri-profile .opro-name {{ color: {name_light} !important; text-shadow: none !important; }}
        .profile-bar .restaurant-level-chip .rl-chip-level,
        .onigiri-profile .opro-level {{ color: {level_light} !important; }}
        .night-mode .profile-bar .profile-name,
        .nightMode .profile-bar .profile-name,
        .night-mode .onigiri-profile .opro-name,
        .nightMode .onigiri-profile .opro-name {{ color: {name_dark} !important; }}
        .night-mode .profile-bar .restaurant-level-chip .rl-chip-level,
        .nightMode .profile-bar .restaurant-level-chip .rl-chip-level,
        .night-mode .onigiri-profile .opro-level,
        .nightMode .onigiri-profile .opro-level {{ color: {level_dark} !important; }}
    </style>
    """

    # Hide the profile on the sidebar (Sidebar Customization option). Uses CSS so
    # both the expanded bar and the collapsed-rail avatar drop out of the layout
    # with no leftover gap.
    if _col_conf_get("modern_menu_hide_profile_bar", False):
        theme_css += """
        <style id="hide-profile-bar">
            .profile-bar, .onigiri-profile, .collapsed-profile-item { display: none !important; }
        </style>
        """

    profile_type = _col_conf_get("modern_menu_profile_type", "bar")
    if profile_type in ("ring", "minimal"):
        profile_bar_html = build_profile_type_html(
            "sidebar", profile_type, user_name, profile_pic_html_expanded
        )
    else:
        profile_bar_html = (
            f"<div class=\"profile-bar {bg_class_str}\" style=\"{bg_style_str}\" "
            f"onclick=\"window.OnigiriProfileSidebar && OnigiriProfileSidebar.toggle(event)\">"
            f"{bg_layer_html}{profile_bar_contents}"
            f"</div>"
        )
    profile_sidebar_html = _build_profile_sidebar_html(
        conf,
        addon_package,
        user_name,
        _get_profile_pic_html(user_name, addon_package, "onigiri-sidebar-profile-img"),
    )
    
    # 1. Build the dynamic sidebar HTML from the layout config
    sidebar_buttons_html = _build_sidebar_html(conf)
    
    profile_pic_html_collapsed = _get_profile_pic_html(user_name, addon_package, "collapsed-profile-pic")
    
    sidebar_width_pinned = bool(
        _col_conf_get("modern_menu_sidebar_width_pinned", False)
    )
    try:
        saved_width = max(320, int(float(_col_conf_get("modern_menu_sidebar_width", 600))))
        if sidebar_width_pinned:
            saved_width = min(saved_width, 1200)
    except (TypeError, ValueError):
        saved_width = 600
    try:
        saved_height = max(260, int(float(_col_conf_get("modern_menu_sidebar_height", 520))))
    except (TypeError, ValueError):
        saved_height = 520
    sidebar_style_parts = [
        f"--onigiri-sidebar-width: {saved_width}px",
        f"width: {saved_width}px",
    ]
    if sidebar_position == "center":
        sidebar_style_parts.extend([
            f"--onigiri-sidebar-height: {saved_height}px",
            f"height: {saved_height}px",
        ])
    sidebar_style = "; ".join(sidebar_style_parts) + ";"
    container_extra_classes = []
    if is_cycle_stacked:
        container_extra_classes.append("onigiri-cycle-stacked")
    if sidebar_position == "right" and not is_cycle_stacked:
        container_extra_classes.append("onigiri-sidebar-right")
    if sidebar_position == "center":
        container_extra_classes.append("onigiri-sidebar-center")
    container_extra_class = " ".join(container_extra_classes)

    # 3. Use the new {sidebar_buttons} placeholder in the template
    #    and remove the old {profile_bar} placeholder.
    
    # Inject Config for JS
    action_icon_keys = [
        "add", "browse", "stats", "sync", "settings", "more",
        "get_shared", "create_deck", "import_file"
    ]
    collapsed_icons = {
        key: _col_conf_get(f"modern_menu_icon_{key}", "")
        for key in action_icon_keys
    }
    sidebar_button_layout = conf.get(
        "sidebarButtonLayout",
        copy.deepcopy(config.DEFAULTS["sidebarButtonLayout"]),
    )
    js_config = {
        "studyToolsVisibility": {tool: tool_visible(tool, conf) for tool in TOOL_IDS},
        "sidebarActionsMode": conf.get("sidebarActionsMode", "list"),
        "sidebarButtonLayout": {
            "visible": sidebar_button_layout.get("visible", []),
            "more": sidebar_button_layout.get("more", list(MORE_ACTION_IDS)),
            "archived": sidebar_button_layout.get("archived", []),
        },
        "addonPackage": mw.addonManager.addonFromModule(__name__),
        "collapsedIcons": collapsed_icons,
        "deckCycleState": deck_cycle_state,
        "sidebarPosition": sidebar_position,
        "sidebarWidthPinned": sidebar_width_pinned,
        "sidebarContentMode": sidebar_content_mode,
        "deckSortMode": _col_conf_get("onigiri_sort_mode", "default"),
        "decklineAvailable": deckline_available,
        "fsrsHelperAvailable": fsrs_helper_integration.is_available(),
        "markerColors": conf.get("markerColors", config.DEFAULTS.get("markerColors", {})),
        "markerIcons": conf.get("markerIcons", {}),
        "markerNames": conf.get("markerNames", {}),
        "filters": {
            "favorites": bool(_col_conf_get("onigiri_show_favourites", False) or _col_conf_get("onigiri_show_favorites", False)),
            "marked": bool(_col_conf_get("onigiri_show_marked", False)),
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
        .replace("{sidebar_content_title}", html.escape(sidebar_content_title)) \
        .replace("{sidebar_search_placeholder}", html.escape(sidebar_search_placeholder, quote=True)) \
        .replace("{sidebar_search_title}", html.escape(sidebar_search_title, quote=True)) \
        .replace("{home_button}", home_button_html) \
        .replace("{ready_marker}", ready_marker_html) \
        .replace("{search_header_icon}", search_header_icon_html) \
        .replace("{sort_header_icon}", sort_header_icon_html) \
        .replace("{sidebar_list_class}", sidebar_list_class) \
        .replace("{sidebar_table_class}", sidebar_table_class) \
        .replace("{profile_bar}", profile_bar_html) \
        .replace("{sidebar_buttons}", sidebar_buttons_html) \
        .replace("{ready_to_go}", _ready_to_go().render_sidebar_html()) \
        .replace("{profile_sidebar}", profile_sidebar_html) \
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
