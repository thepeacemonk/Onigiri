# In deck_tree_updater.py
import json
from aqt import mw
from aqt.deckbrowser import DeckBrowser, RenderDeckNodeContext
from anki.decks import DeckId
from . import onigiri_renderer

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
    
    ctx = RenderDeckNodeContext(current_deck_id=deck_browser.mw.col.decks.get_current_id())
    # Note: _render_deck_node is patched by Onigiri in patcher.py
    return "".join(deck_browser._render_deck_node(child, ctx) for child in tree_data.children)

def on_deck_collapse(deck_browser: DeckBrowser, deck_id: str) -> None:
    """
    Handles the collapse/expand action for a deck without a full page reload.
    Re-renders the tree HTML and uses JS to preserve checkbox *state*.
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
        # This preserves checkbox *state* (checked=true/false)
        js = """
        (function() {{
            const container = document.getElementById('deck-list-container');
            const scrollTop = container?.scrollTop || 0;
            
            // 1. Store the *state* (checked or not) of all existing checkboxes
            const checkboxStateMap = new Map();
            document.querySelectorAll('.deck-checkbox').forEach(cb => {{
                const did = cb.dataset.did;
                if (did) {{
                    checkboxStateMap.set(did, cb.checked);
                }}
            }});
            
            // 2. Update the tree HTML
            OnigiriEngine.updateDeckTree({new_tree_html});
            
            // 3. Re-apply the stored state to the *new* checkboxes
            checkboxStateMap.forEach((isChecked, did) => {{
                // Find the *new* checkbox element in the updated DOM
                const newCheckbox = document.querySelector(`.deck-checkbox[data-did="${{did}}"]`);
                if (newCheckbox) {{
                    newCheckbox.checked = isChecked;
                }}
            }});
            
            // 4. Restore scroll position
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
            const scrollTop = container?.scrollTop || 0;
            
            // 1. Store the *state* (checked or not) of all existing checkboxes
            const checkboxStateMap = new Map();
            document.querySelectorAll('.deck-checkbox').forEach(cb => {{
                const did = cb.dataset.did;
                if (did) {{
                    checkboxStateMap.set(did, cb.checked);
                }}
            }});
            
            // 2. Update the tree HTML
            OnigiriEngine.updateDeckTree({new_tree_html});
            
            // 3. Re-apply the stored state to the *new* checkboxes
            checkboxStateMap.forEach((isChecked, did) => {{
                // Find the *new* checkbox element in the updated DOM
                const newCheckbox = document.querySelector(`.deck-checkbox[data-did="${{did}}"]`);
                if (newCheckbox) {{
                    newCheckbox.checked = isChecked;
                }}
            }});
            
            // 4. Restore scroll position
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