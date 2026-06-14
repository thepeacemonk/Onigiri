"""
Onigiri Favorites Cleanup Utility

This module provides utility functions for managing and cleaning up favorite decks.
Users can import and run these functions from Anki's debug console if needed.
"""

from aqt import mw


def cleanup_favorites():
    """
    Removes deleted decks from the favorites list.
    
    Usage from Anki debug console (Cmd+Shift+;):
        from 1011095603.favorites_cleanup import cleanup_favorites
        cleanup_favorites()
    
    Returns:
        tuple: (removed_count, remaining_favorites)
    """
    if not mw or not mw.col:
        print("Error: No collection loaded")
        return (0, [])
    
    favorites = mw.col.conf.get("onigiri_favorite_decks", [])
    if not favorites:
        print("No favorites to clean up")
        return (0, [])
    
    print(f"Checking {len(favorites)} favorite deck(s)...")
    
    # Get all existing deck IDs for validation
    all_deck_ids = mw.col.decks.all_names_and_ids()
    existing_deck_ids = {str(deck.id) for deck in all_deck_ids}
    
    valid_favorites = []
    removed_decks = []
    
    for deck_id in favorites:
        deck_id_str = str(deck_id)
        
        # Check if deck exists in the collection
        if deck_id_str not in existing_deck_ids:
            removed_decks.append(deck_id)
            print(f"  ✗ ID {deck_id}: DELETED (not in collection)")
            continue
        
        deck = mw.col.decks.get(deck_id)
        if deck and deck.get("name"):
            valid_favorites.append(deck_id)
            print(f"  ✓ ID {deck_id}: {deck['name']}")
        else:
            removed_decks.append(deck_id)
            print(f"  ✗ ID {deck_id}: INVALID (no name or null)")
    
    if removed_decks:
        mw.col.conf["onigiri_favorite_decks"] = valid_favorites
        mw.col.setMod()
        print(f"\n✓ Removed {len(removed_decks)} deleted/invalid deck(s) from favorites")
        print(f"Remaining favorites: {len(valid_favorites)}")
    else:
        print("\n✓ All favorites are valid, no cleanup needed")
    
    return (len(removed_decks), valid_favorites)


def list_favorites():
    """
    Lists all current favorite decks.
    
    Usage from Anki debug console (Cmd+Shift+;):
        from 1011095603.favorites_cleanup import list_favorites
        list_favorites()
    
    Returns:
        list: List of (deck_id, deck_name) tuples, or (deck_id, None) for deleted decks
    """
    if not mw or not mw.col:
        print("Error: No collection loaded")
        return []
    
    favorites = mw.col.conf.get("onigiri_favorite_decks", [])
    
    if not favorites:
        print("No favorite decks")
        return []
    
    print(f"Favorite decks ({len(favorites)}):")
    result = []
    
    for deck_id in favorites:
        deck = mw.col.decks.get(deck_id)
        if deck:
            deck_name = deck['name']
            print(f"  - ID {deck_id}: {deck_name}")
            result.append((deck_id, deck_name))
        else:
            print(f"  - ID {deck_id}: [DELETED]")
            result.append((deck_id, None))
    
    return result


def remove_favorite(deck_id):
    """
    Manually removes a specific deck from favorites.
    
    Usage from Anki debug console (Cmd+Shift+;):
        from 1011095603.favorites_cleanup import remove_favorite
        remove_favorite("1234567890")  # Replace with actual deck ID
    
    Args:
        deck_id: The deck ID to remove (as string or int)
    
    Returns:
        bool: True if removed, False if not found
    """
    if not mw or not mw.col:
        print("Error: No collection loaded")
        return False
    
    deck_id = str(deck_id)  # Ensure it's a string
    favorites = mw.col.conf.get("onigiri_favorite_decks", [])
    
    if deck_id in favorites:
        favorites.remove(deck_id)
        mw.col.conf["onigiri_favorite_decks"] = favorites
        mw.col.setMod()
        print(f"✓ Removed deck {deck_id} from favorites")
        print(f"Remaining favorites: {favorites}")
        return True
    else:
        print(f"✗ Deck {deck_id} was not in favorites")
        return False


def clear_all_favorites():
    """
    Removes all decks from favorites.
    
    Usage from Anki debug console (Cmd+Shift+;):
        from 1011095603.favorites_cleanup import clear_all_favorites
        clear_all_favorites()
    
    Returns:
        int: Number of favorites cleared
    """
    if not mw or not mw.col:
        print("Error: No collection loaded")
        return 0
    
    favorites = mw.col.conf.get("onigiri_favorite_decks", [])
    count = len(favorites)
    
    if count > 0:
        mw.col.conf["onigiri_favorite_decks"] = []
        mw.col.setMod()
        print(f"✓ Cleared {count} favorite deck(s)")
    else:
        print("No favorites to clear")
    
    return count
