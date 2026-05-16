# In deck_tree_updater.py
import json
from aqt import mw
from aqt.deckbrowser import DeckBrowser, RenderDeckNodeContext
from anki.decks import DeckId
from . import onigiri_renderer

def _sort_tree_nodes(nodes, sort_mode, saved_order, is_top_level=True):
    """Return a sorted copy of a DeckTreeNode children list."""
    nodes = list(nodes)
    if sort_mode == "alphabetical_az":
        nodes.sort(key=lambda n: n.name.split("::")[-1].lower())
    elif sort_mode == "alphabetical_za":
        nodes.sort(key=lambda n: n.name.split("::")[-1].lower(), reverse=True)
    elif sort_mode == "most_due":
        nodes.sort(key=lambda n: n.review_count + n.learn_count, reverse=True)
    elif sort_mode == "most_reviews":
        nodes.sort(key=lambda n: n.review_count, reverse=True)
    elif sort_mode == "most_new":
        nodes.sort(key=lambda n: n.new_count, reverse=True)
    elif sort_mode == "custom":
        # Apply saved order at all levels; fall back to alphabetical for unknown IDs
        nodes.sort(key=lambda n: (
            saved_order.index(str(n.deck_id)) if str(n.deck_id) in saved_order else 9999,
            n.name.split("::")[-1].lower()
        ))
    return nodes


def _apply_sort_recursive(nodes_collection, sort_mode, saved_order, is_top_level=True):
    """Sort a protobuf repeated field in-place, then recurse into each node's children."""
    try:
        sorted_nodes = _sort_tree_nodes(nodes_collection, sort_mode, saved_order, is_top_level)
        try:
            del nodes_collection[:]
            nodes_collection.extend(sorted_nodes)
        except (TypeError, AttributeError):
            pass  # field not mutable; top-level fallback handled by caller
        for node in nodes_collection:
            _apply_sort_recursive(node.children, sort_mode, saved_order, is_top_level=False)
    except Exception:
        pass


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

    sort_mode = mw.col.conf.get("onigiri_sort_mode", "")
    if sort_mode:
        saved_order = [str(x) for x in mw.col.conf.get("onigiri_custom_deck_order", [])]
        _apply_sort_recursive(tree_data.children, sort_mode, saved_order, is_top_level=True)

    # Apply favourites filter if active — strict: only directly-favourited decks shown.
    # Parents that are not themselves favourited are excluded even if a child is.
    show_favourites_only = bool(mw.col.conf.get("onigiri_show_favourites", False))
    if show_favourites_only:
        favourites = set(str(f) for f in mw.col.conf.get("onigiri_favorite_decks", []))

        def _filter_strictly(nodes):
            """Keep only nodes that are directly in favourites; recurse into kept nodes."""
            kept = [n for n in nodes if str(n.deck_id) in favourites]
            # Children of a kept (favourited) node are shown in full — no further pruning.
            return kept

        try:
            kept = _filter_strictly(list(tree_data.children))
            del tree_data.children[:]
            tree_data.children.extend(kept)
        except Exception:
            pass

    # Apply marked filter if active — only decks that have an Onigiri colour mark.
    # Marks are stored in mw.col.conf["onigiri_deck_marks"] as {deck_id_str: colour_key}.
    show_marked_only = bool(mw.col.conf.get("onigiri_show_marked", False))
    if show_marked_only:
        try:
            marks = dict(mw.col.conf.get("onigiri_deck_marks", {}))
            # Any non-empty colour value counts as marked
            marked_deck_ids = set(str(k) for k, v in marks.items() if v)

            def _filter_marked(nodes):
                return [n for n in nodes if str(n.deck_id) in marked_deck_ids]

            kept = _filter_marked(list(tree_data.children))
            del tree_data.children[:]
            tree_data.children.extend(kept)
        except Exception:
            pass

    ctx = RenderDeckNodeContext(current_deck_id=deck_browser.mw.col.decks.get_current_id())
    # Note: _render_deck_node is patched by Onigiri in patcher.py
    return "".join(deck_browser._render_deck_node(child, ctx) for child in tree_data.children)

def on_deck_collapse(deck_browser: DeckBrowser, deck_id: str) -> None:
    """
    Handles the collapse/expand action for a deck without a full page reload.
    Re-renders the tree HTML and uses JS to preserve checkbox *state*.
    When collapsing (deck was open → now closed) child rows are animated out
    before the innerHTML is replaced for a smooth transition.
    """
    try:
        did = int(deck_id)

        # Snapshot state BEFORE toggling so we know the direction
        deck_obj = mw.col.decks.get(did)
        was_collapsed = bool(deck_obj.get("collapsed", False)) if isinstance(deck_obj, dict) else False
        # After toggle: is_collapsing = True means rows are disappearing
        is_collapsing = not was_collapsed

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
        # When collapsing, animate children out first (150 ms), then swap.
        js = """
        (function() {{
            const container = document.getElementById('deck-list-container');
            const scrollTop = container ? container.scrollTop : 0;
            const isCollapsing = {is_collapsing};
            const deckId = "{deck_id}";

            function doUpdate() {{
                OnigiriEngine.updateDeckTree({new_tree_html});
                if (container) container.scrollTop = scrollTop;
            }}

            if (isCollapsing) {{
                // Collect child rows (siblings after the parent row in the tbody)
                const tbody = document.querySelector('#decktree > tbody');
                const parentRow = tbody ? tbody.querySelector('tr.deck[data-did="' + deckId + '"]') : null;
                const childRows = [];
                if (parentRow) {{
                    let el = parentRow.nextElementSibling;
                    while (el && el.tagName === 'TR') {{
                        childRows.push(el);
                        el = el.nextElementSibling;
                    }}
                }}
                if (childRows.length > 0) {{
                    childRows.forEach(function(r) {{
                        r.classList.add('deck-row-disappear');
                    }});
                    setTimeout(doUpdate, 155);
                    return;
                }}
            }}
            doUpdate();
        }})();
        """.format(
            is_collapsing="true" if is_collapsing else "false",
            deck_id=deck_id,
            new_tree_html=js_escaped_html
        )

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
    Handles a full refresh of the deck tree HTML while preserving
    scroll and edit mode state. Used for favorite toggling.
    Preserves existing checkbox *state* in the DOM by saving and restoring it.
    """
    try:
        # Refresh the tree data
        tree_data = deck_browser.mw.col.sched.deck_due_tree()
        deck_browser._render_data = onigiri_renderer.RenderData(tree=tree_data)
        
        # Re-render only the deck tree
        new_tree_html = _render_deck_tree_html_only(deck_browser)

        # Escape the HTML for safe injection into a JavaScript string
        js_escaped_html = json.dumps(new_tree_html)
        
        # Send the new HTML to the frontend to be injected by JavaScript
        # This preserves checkbox *state* (checked=true/false)
        js = """
        (function() {{
            const container = document.getElementById('deck-list-container');
            const scrollTop = container ? container.scrollTop : 0;
            OnigiriEngine.updateDeckTree({new_tree_html});
            if (container) container.scrollTop = scrollTop;
        }})();
        """.format(new_tree_html=js_escaped_html)

        deck_browser.web.eval(js)

    except Exception as e:
        print(f"Onigiri: Error in refresh_deck_tree_state: {e}")
        import traceback
        traceback.print_exc()