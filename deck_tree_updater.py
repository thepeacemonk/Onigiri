# In deck_tree_updater.py
import json
from aqt import mw
from aqt.deckbrowser import DeckBrowser, RenderDeckNodeContext
from anki.decks import DeckId

def _render_deck_tree_html_only(deck_browser: DeckBrowser) -> str:
    """
    Renders just the HTML for the deck tree's <tbody> content.
    This is a performance-focused function used for fast updates.
    """
    tree_data = deck_browser.mw.col.sched.deck_due_tree()
    ctx = RenderDeckNodeContext(current_deck_id=deck_browser.mw.col.decks.get_current_id())
    # Note: _render_deck_node is patched by Onigiri in patcher.py
    return "".join(deck_browser._render_deck_node(child, ctx) for child in tree_data.children)

def on_deck_collapse(deck_browser: DeckBrowser, deck_id: str) -> None:
    """
    Handles the collapse/expand action for a deck without a full page reload.
    """
    try:
        did = int(deck_id)
        # Toggle the collapse state in Anki's backend
        mw.col.decks.collapse(did)
        mw.col.decks.save() # Ensure the change is persisted

        # Re-render only the deck tree
        new_tree_html = _render_deck_tree_html_only(deck_browser)

        # Escape the HTML for safe injection into a JavaScript string
        js_escaped_html = json.dumps(new_tree_html)
        
        # Send the new HTML to the frontend to be injected by JavaScript
        deck_browser.web.eval(f"OnigiriEngine.updateDeckTree({js_escaped_html});")

    except (ValueError, TypeError) as e:
        print(f"Onigiri: Could not process deck collapse for deck_id '{deck_id}': {e}")


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
        print(f"Onigiri: converted to DeckIds - source_dids: {source_dids}, target_did: {target_did}")

        # Anki's reparent function handles invalid moves (e.g., moving a parent into its child)
        mw.col.decks.reparent(source_dids, target_did)
        print(f"Onigiri: Successfully called reparent")

        # Refresh the main deck browser to show changes and reset the UI state
        if mw.deckBrowser:
            mw.deckBrowser.refresh()
            print(f"Onigiri: Successfully refreshed deck browser")
        else:
            print(f"Onigiri: deckBrowser is None, cannot refresh")

    except (ValueError, TypeError, json.JSONDecodeError) as e:
        print(f"Onigiri: Could not process deck move request: {e}")