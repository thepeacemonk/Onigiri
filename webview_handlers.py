from typing import Tuple, Any
from aqt.deckbrowser import DeckBrowser
from . import deck_tree_updater
from . import create_deck_dialog
from aqt import mw
from aqt.utils import tooltip

def handle_webview_cmd(handled: Tuple[bool, Any], cmd: str, context) -> Tuple[bool, Any]:
    """
    Centralized handler for webview commands from the deck browser.
    """
    if cmd == "onigiri_create_deck":
        try:
             # tooltip("Debug: Opening Create Deck Dialog...")
             if not hasattr(create_deck_dialog, 'CreateDeckDialog'):
                 tooltip("Error: CreateDeckDialog class not found in module.")
                 return (True, None)

             dialog = create_deck_dialog.CreateDeckDialog(mw)
             dialog.exec()
             return (True, None) # Handled
        except Exception as e:
             import traceback
             error_msg = f"Onigiri Error: {str(e)}\n{traceback.format_exc()}"
             print(error_msg)
             tooltip(f"Error showing create deck dialog: {e}")
             return (True, None)

    if cmd.startswith("onigiri_collapse:"):
        try:
            deck_id = cmd.split(":", 1)[1]
            if isinstance(context, DeckBrowser):
                deck_tree_updater.on_deck_collapse(context, deck_id)
                return (True, None)
        except Exception as e:
            print(f"Onigiri: Error handling deck collapse: {e}")
        return (True, None)

    if cmd.startswith("onigiri_toggle_favorite:"):
        try:
            deck_id = cmd.split(":", 1)[1] # Keep as string for consistency
            
            # Validate that the deck exists before toggling
            deck = mw.col.decks.get(deck_id)
            if not deck:
                tooltip("Cannot favorite: Deck no longer exists.")
                return (True, None)
            
            favorites = mw.col.conf.get("onigiri_favorite_decks", [])
            
            if deck_id in favorites:
                favorites.remove(deck_id)
            else:
                if len(favorites) >= 5:
                    tooltip("You can only have up to 5 favorite decks.")
                    return (True, None) # Stop execution, don't refresh
                favorites.append(deck_id)
            
            # Save the change to Anki's configuration
            mw.col.conf["onigiri_favorite_decks"] = favorites
            mw.col.setMod() # This line is CRITICAL
            
            # Force a full refresh of the deck browser
            if isinstance(context, DeckBrowser):
                deck_tree_updater.refresh_deck_tree_state(context)
            
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error handling favorite toggle: {e}")
            import traceback
            traceback.print_exc()
            return (True, None) # Still handle the command
        
    if cmd.startswith("onigiri_show_transfer_window:"):
        try:
            from . import mod_transfer_window
            json_payload = cmd.split(":", 1)[1]
            mod_transfer_window.show_transfer_window(json_payload)
            return (True, None)
        except Exception as e:
            return (True, None)

    if cmd.startswith("onigiri_move_decks:"):
        try:
            json_payload = cmd.split(":", 1)[1]
            deck_tree_updater.on_decks_move(json_payload)
            return (True, None)
        except Exception as e:
            return (True, None)

    return handled