"""Minimal, deck-only renderer for the Shima theme."""

import html
import json

from aqt import mw
from aqt.deckbrowser import DeckBrowser

from ..core import config
from ..integrations import fsrs_helper_integration
from . import onigiri_renderer
from ..decks import tree_updater as deck_tree_updater
from ..core.translations import tr


def render_deck_browser(deck_browser: DeckBrowser, reuse: bool = False) -> None:
    """Render only the centered deck island on the main menu.

    Shima deliberately does not execute the dashboard-widget hooks. The deck
    tree still goes through Onigiri's normal renderer, so custom icons, counts,
    context menus, searching, sorting, and drag ordering keep working.
    """
    del reuse

    tree_data = deck_browser.mw.col.sched.deck_due_tree()
    deck_browser._render_data = onigiri_renderer.RenderData(tree=tree_data)
    tree_html = deck_tree_updater._render_deck_tree_html_only(deck_browser)

    addon_package = mw.addonManager.addonFromModule(__name__)
    conf = config.get_config_readonly()
    home_button_html = onigiri_renderer._build_archived_home_button(
        conf, addon_package
    )
    ready_marker_html = onigiri_renderer._build_hidden_ready_marker(addon_package)
    search_icon_html = onigiri_renderer._sidebar_header_icon_markup(
        "modern_menu_icon_header_search", "search.svg", "search-btn-icon",
        addon_package,
    )
    sort_icon_html = onigiri_renderer._sidebar_header_icon_markup(
        "modern_menu_icon_header_sort", "sort_default.svg", "sort-btn-icon",
        addon_package,
    )
    js_config = {
        "addonPackage": addon_package,
        "deckSortMode": config.get_collection_config(
            "onigiri_sort_mode", "default"
        ),
        "decklineAvailable": False,
        "fsrsHelperAvailable": fsrs_helper_integration.is_available(),
        "markerColors": conf.get(
            "markerColors", config.DEFAULTS.get("markerColors", {})
        ),
        "markerIcons": conf.get("markerIcons", {}),
        "markerNames": conf.get("markerNames", {}),
        "filters": {
            "favorites": bool(
                config.get_collection_config("onigiri_show_favourites", False)
                or config.get_collection_config("onigiri_show_favorites", False)
            ),
            "marked": bool(
                config.get_collection_config("onigiri_show_marked", False)
            ),
        },
    }

    deck_label = html.escape(tr("decks_header", "Decks"), quote=True)
    deck_heading = html.escape(tr("decks_header", "DECKS"))
    search_placeholder = html.escape(
        tr("search_decks", "Search decks…"), quote=True
    )
    search_title = html.escape(tr("search_decks", "Search decks"), quote=True)
    close_icon = """
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14"
             viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2.2" stroke-linecap="round"
             stroke-linejoin="round" aria-hidden="true">
            <path d="M18 6 6 18"/><path d="m6 6 12 12"/>
        </svg>
    """
    body = f"""
    <div class="container modern-main-menu onigiri-shima">
        <main class="sidebar-left shima-island" aria-label="{deck_label}">
            <div class="sidebar-expanded-content">
                <section class="onigiri-sidebar-section
                                onigiri-sidebar-decks-section is-decks-mode">
                    <div id="deck-list-header">
                        <h2>{deck_heading}</h2>
                        <div id="onigiri-deck-search-bar">
                            <span class="onigiri-search-icon" aria-hidden="true"></span>
                            <input type="text" id="onigiri-deck-search-input"
                                   placeholder="{search_placeholder}"
                                   autocomplete="off" spellcheck="false">
                            <button id="onigiri-deck-search-close"
                                    aria-label="Close" type="button">
                                {close_icon}
                            </button>
                        </div>
                        <div class="deck-header-actions">
                            <button id="onigiri-search-toolbar-btn" class="deck-header-btn"
                                    onclick="OnigiriEngine.toggleDeckSearch()"
                                    title="{search_title}" type="button">
                                {search_icon_html}
                            </button>
                            <button id="onigiri-sort-toolbar-btn" class="deck-header-btn"
                                    type="button" title="Sort decks"
                                    onclick="OnigiriEngine.showSortMenu(this, event)">
                                {sort_icon_html}
                            </button>
                            {ready_marker_html}
                            {home_button_html}
                        </div>
                    </div>
                    <div id="deck-list-container">
                        <table class="deck-table" id="decktree">
                            <tbody>{tree_html}</tbody>
                        </table>
                    </div>
                </section>
            </div>
        </main>
    </div>
    <script>
        window.ONIGIRI_CONFIG = {json.dumps(js_config)};
        document.addEventListener('DOMContentLoaded', function () {{
            if (typeof anki !== 'undefined' && anki.setupDeckBrowser) {{
                anki.setupDeckBrowser();
            }}
        }});
    </script>
    """

    deck_browser.web.stdHtml(
        body=body,
        css=["css/deckbrowser.css"],
        js=[
            "js/vendor/jquery.min.js",
            "js/vendor/jquery-ui.min.js",
            "js/deckbrowser.js",
        ],
        context=deck_browser,
    )

    from aqt import gui_hooks

    gui_hooks.deck_browser_did_render(deck_browser)
