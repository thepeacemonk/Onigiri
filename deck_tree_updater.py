# In deck_tree_updater.py
import json
from aqt import mw
from aqt.deckbrowser import DeckBrowser, RenderDeckNodeContext
from anki.decks import DeckId
from . import onigiri_renderer


def _sort_tree_nodes(nodes, sort_mode):
    """Sort deck tree nodes in-place for fast sidebar-only refreshes."""
    if not sort_mode or sort_mode == "default":
        return

    favorites = {str(did) for did in mw.col.conf.get("onigiri_favorite_decks", [])}
    custom_order = {
        str(did): index
        for index, did in enumerate(mw.col.conf.get("onigiri_custom_deck_order", []))
    }

    def leaf_name(node):
        return node.name.split("::")[-1].lower()

    if sort_mode == "alphabetical_az":
        nodes.sort(key=leaf_name)
    elif sort_mode == "alphabetical_za":
        nodes.sort(key=leaf_name, reverse=True)
    elif sort_mode == "most_due":
        nodes.sort(key=lambda node: node.review_count + node.learn_count, reverse=True)
    elif sort_mode == "most_new":
        nodes.sort(key=lambda node: node.new_count, reverse=True)
    elif sort_mode == "most_reviews":
        nodes.sort(key=lambda node: node.review_count, reverse=True)
    elif sort_mode == "favorites_first":
        nodes.sort(key=lambda node: (str(node.deck_id) not in favorites, leaf_name(node)))
    elif sort_mode == "custom":
        nodes.sort(key=lambda node: (custom_order.get(str(node.deck_id), 10**9), leaf_name(node)))


def _apply_sort_recursive(nodes, sort_mode):
    _sort_tree_nodes(nodes, sort_mode)
    for node in nodes:
        if node.children:
            _apply_sort_recursive(node.children, sort_mode)


def _apply_active_filters(tree_data) -> None:
    """Apply Onigiri deck list filters while preserving matching descendants."""
    show_favorites_only = bool(
        mw.col.conf.get("onigiri_show_favourites", False)
        or mw.col.conf.get("onigiri_show_favorites", False)
    )
    show_marked_only = bool(mw.col.conf.get("onigiri_show_marked", False))

    if not show_favorites_only and not show_marked_only:
        return

    favorite_ids = {str(did) for did in mw.col.conf.get("onigiri_favorite_decks", [])}
    mark_ids = {
        str(did)
        for did, value in mw.col.conf.get("onigiri_deck_marks", {}).items()
        if value
    }

    def node_matches(node) -> bool:
        did = str(node.deck_id)
        if show_favorites_only and did not in favorite_ids:
            return False
        if show_marked_only and did not in mark_ids:
            return False
        return True

    def filter_nodes(nodes):
        kept = []
        for node in list(nodes):
            matching_children = filter_nodes(node.children) if node.children else []
            if node_matches(node) or matching_children:
                if node.children:
                    del node.children[:]
                    node.children.extend(matching_children)
                kept.append(node)
        return kept

    try:
        kept = filter_nodes(tree_data.children)
        del tree_data.children[:]
        tree_data.children.extend(kept)
    except Exception as e:
        print(f"Onigiri: Could not apply deck list filter: {e}")


def _apply_tree_preferences(tree_data) -> None:
    sort_mode = mw.col.conf.get("onigiri_sort_mode", "default")
    if sort_mode != "default":
        _apply_sort_recursive(tree_data.children, sort_mode)
    _apply_active_filters(tree_data)

def _render_deck_tree_html_only(deck_browser: DeckBrowser) -> str:
    """
    Renders just the HTML for the deck tree's <tbody> content.
    This is a performance-focused function used for fast updates.
    """
    # Use cached tree data if available, otherwise fetch fresh data
    if hasattr(deck_browser, '_render_data') and deck_browser._render_data:
        tree_data = deck_browser._render_data.tree
    else:
        tree_data = deck_browser.mw.col.sched.deck_due_tree()
        deck_browser._render_data = onigiri_renderer.RenderData(tree=tree_data)

    _apply_tree_preferences(tree_data)
    
    ctx = RenderDeckNodeContext(current_deck_id=deck_browser.mw.col.decks.get_current_id())
    # Note: _render_deck_node is patched by Onigiri in patcher.py
    return "".join(deck_browser._render_deck_node(child, ctx) for child in tree_data.children)


def _render_deck_search_html(deck_browser: DeckBrowser, query: str) -> str:
    """Render sidebar deck rows matching a deck search query."""
    normalized = query.strip().lower()
    if not normalized:
        deck_browser._render_data = None
        return _render_deck_tree_html_only(deck_browser)

    tree_data = deck_browser.mw.col.sched.deck_due_tree()
    _apply_tree_preferences(tree_data)
    ctx = RenderDeckNodeContext(current_deck_id=deck_browser.mw.col.decks.get_current_id())
    rows = []

    def collect_matches(nodes):
        for node in nodes:
            name = node.name or ""
            leaf = name.split("::")[-1]
            if normalized in name.lower() or normalized in leaf.lower():
                rows.append(deck_browser._render_deck_node(node, ctx))
            elif node.children:
                collect_matches(node.children)

    collect_matches(tree_data.children)
    return "".join(rows)

def on_deck_collapse(deck_browser: DeckBrowser, deck_id: str) -> None:
    """
    Handles the collapse/expand action for a deck without a full page reload.
    """
    try:
        did = int(deck_id)
        # Toggle the collapse state in Anki's backend
        mw.col.decks.collapse(did)
        mw.col.decks.save()  # Ensure the change is persisted

        # Refresh the tree data *after* collapse state has changed
        tree_data = deck_browser.mw.col.sched.deck_due_tree()
        deck_browser._render_data = onigiri_renderer.RenderData(tree=tree_data)
        
        # Re-render only the deck tree
        new_tree_html = _render_deck_tree_html_only(deck_browser)

        # Escape the HTML for safe injection into a JavaScript string
        js_escaped_html = json.dumps(new_tree_html)
        
        # Send the new HTML to the frontend to be injected by JavaScript
        js = """
        (function() {{
            const container = document.getElementById('deck-list-container');
            const scrollTop = container?.scrollTop || 0;
            OnigiriEngine.updateDeckTree({new_tree_html});
            if (container) {{
                container.scrollTop = scrollTop;
            }}
        }})();
        """.format(new_tree_html=js_escaped_html)
        
        deck_browser.web.eval(js)

    except Exception as e:
        print(f"Onigiri: Error in on_deck_collapse for deck_id '{deck_id}': {e}")
        import traceback
        traceback.print_exc()


def on_decks_move(data_str: str) -> None:
    """
    Handles moving multiple decks. This is called from the transfer window.
    It closes the transfer window and refreshes the main Deck Browser.
    """
    # Close the transfer window first, if it exists
    if hasattr(mw, "onigiri_transfer_window") and mw.onigiri_transfer_window:
        try:
            mw.onigiri_transfer_window.close()
        except Exception as e:
            print(f"Onigiri: Could not close transfer window: {e}")
        mw.onigiri_transfer_window = None

    try:
        print(f"Onigiri: on_decks_move called with data_str: {data_str}")
        data = json.loads(data_str)
        print(f"Onigiri: parsed data: {data}")
        source_dids_str = data.get("source_dids", [])
        target_did_str = data.get("target_did")
        print(f"Onigiri: source_dids_str: {source_dids_str}, target_did_str: {target_did_str}")

        if not source_dids_str or target_did_str is None:
            print(f"Onigiri: Missing data - source_dids_str: {source_dids_str}, target_did_str: {target_did_str}")
            return

        source_dids = [DeckId(int(did)) for did in source_dids_str]
        target_did = DeckId(int(target_did_str))
        # Corrected print statement
        print(f"Onigiri: converted to DeckIds - source_dids: {source_dids}, target_did: {target_did}")

        # Anki's reparent function handles invalid moves (e.g., moving a parent into its child)
        mw.col.decks.reparent(source_dids, target_did)
        print(f"Onigiri: Successfully called reparent")

        # Force a complete deck browser refresh to update all internal state
        # This prevents stale deck IDs from persisting in the context menu
        if mw.deckBrowser:
            # Call show() which triggers a full re-render via _renderPage
            mw.deckBrowser.show()
            print(f"Onigiri: Successfully refreshed deck browser with full render")
        else:
            print(f"Onigiri: deckBrowser is None, cannot refresh")

    except (ValueError, TypeError, json.JSONDecodeError) as e:
        print(f"Onigiri: Could not process deck move request: {e}")

def refresh_deck_tree_state(deck_browser: DeckBrowser) -> None:
    """
    Handles a full refresh of the deck tree HTML while preserving scroll state.
    """
    try:
        # Refresh the tree data
        tree_data = deck_browser.mw.col.sched.deck_due_tree()
        deck_browser._render_data = onigiri_renderer.RenderData(tree=tree_data)
        
        # Re-render only the deck tree
        new_tree_html = _render_deck_tree_html_only(deck_browser)

        # Escape the HTML for safe injection into a JavaScript string
        js_escaped_html = json.dumps(new_tree_html)
        
        js = """
        (function() {{
            const container = document.getElementById('deck-list-container');
            const scrollTop = container?.scrollTop || 0;
            OnigiriEngine.updateDeckTree({new_tree_html});
            if (container) {{
                container.scrollTop = scrollTop;
            }}
        }})();
        """.format(new_tree_html=js_escaped_html)
        
        deck_browser.web.eval(js)

    except Exception as e:
        print(f"Onigiri: Error in refresh_deck_tree_state: {e}")
        import traceback
        traceback.print_exc()
