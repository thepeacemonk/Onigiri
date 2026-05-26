import json
from typing import Any, Dict, List, Mapping, Optional, Tuple

from anki.decks import DeckId
from aqt import mw

from . import deck_drag_drop
from .constants import ICON_DEFAULTS


ROOT_DESTINATION_ID = "__root__"


def build_move_to_payload(source_did: str) -> Dict[str, Any]:
    source_id = _normalize_did(source_did)
    if not source_id:
        raise ValueError("Invalid deck ID.")

    deck_names = deck_drag_drop._deck_names_by_id()
    source_name = deck_names.get(source_id)
    if not source_name:
        raise ValueError("Deck no longer exists.")

    moving_ids = deck_drag_drop._moving_subtree_ids([source_id], deck_names)
    current_parent = deck_drag_drop._parent_name(source_name)
    current_parent_id = _deck_id_for_name(deck_names, current_parent)
    addon_package = mw.addonManager.addonFromModule(__name__)

    destinations: List[Dict[str, Any]] = []
    destinations.append(
        _root_destination(source_id, source_name, deck_names, current_parent, addon_package)
    )

    for did, name in sorted(
        deck_names.items(),
        key=lambda item: (item[1].count("::"), item[1].lower()),
    ):
        if did in moving_ids:
            continue

        deck = mw.col.decks.get(DeckId(int(did)))
        is_filtered = bool(deck and deck.get("dyn", 0))
        if is_filtered:
            continue
        icon_key = _deck_icon_key(name, deck_names, is_filtered)

        disabled = False
        reason = ""
        if did == current_parent_id:
            disabled = True
            reason = "Current parent"
        elif not _can_move_to_parent(source_id, did, deck_names):
            disabled = True
            reason = "Name conflict"

        destinations.append(
            {
                "id": did,
                "name": deck_drag_drop._leaf_name(name),
                "path": name,
                "depth": name.count("::"),
                "kind": "deck",
                "iconKey": icon_key,
                "iconUrl": _icon_url(icon_key, addon_package),
                "disabled": disabled,
                "reason": reason,
            }
        )

    return {
        "source": {
            "id": source_id,
            "name": source_name,
            "leaf": deck_drag_drop._leaf_name(source_name),
            "parent": current_parent,
        },
        "destinations": destinations,
    }


def move_deck_from_payload(payload_json: str) -> Tuple[bool, str]:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return False, "Could not read the move request."

    if not isinstance(payload, Mapping):
        return False, "Could not read the move request."

    source_id = _normalize_did(payload.get("source_did"))
    if not source_id:
        return False, "Invalid source deck."

    target_id = payload.get("target_did")
    to_root = target_id == ROOT_DESTINATION_ID or target_id is None

    deck_names = deck_drag_drop._deck_names_by_id()
    source_name = deck_names.get(source_id)
    if not source_name:
        return False, "Deck no longer exists."

    current_parent = deck_drag_drop._parent_name(source_name)
    if to_root:
        if not current_parent:
            return False, "This deck is already at the top level."
        if not _can_move_to_root(source_id, deck_names):
            return False, "A top-level deck with that name already exists."
        return _move_to_root(source_id, source_name)

    target_id = _normalize_did(target_id)
    if not target_id:
        return False, "Invalid destination deck."

    target_name = deck_names.get(target_id)
    if not target_name:
        return False, "Destination deck no longer exists."

    if current_parent == target_name:
        return False, "This deck is already in that parent."

    target_deck = mw.col.decks.get(DeckId(int(target_id)))
    if target_deck and target_deck.get("dyn", 0):
        return False, "Filtered decks cannot be used as move destinations."

    if not _can_move_to_parent(source_id, target_id, deck_names):
        return False, "That destination is not valid for this deck."

    mw.col.decks.reparent([DeckId(int(source_id))], DeckId(int(target_id)))
    _ensure_path_expanded(target_name, deck_names)
    mw.col.setMod()
    return True, "Deck moved."


def _normalize_did(value: Any) -> Optional[str]:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return None


def _deck_id_for_name(deck_names: Mapping[str, str], name: str) -> Optional[str]:
    if not name:
        return None
    for did, deck_name in deck_names.items():
        if deck_name == name:
            return did
    return None


def _root_destination(
    source_id: str,
    source_name: str,
    deck_names: Mapping[str, str],
    current_parent: str,
    addon_package: str,
) -> Dict[str, Any]:
    disabled = False
    reason = ""

    if not current_parent:
        disabled = True
        reason = "Current location"
    elif not _can_move_to_root(source_id, deck_names):
        disabled = True
        reason = "Name conflict"

    return {
        "id": ROOT_DESTINATION_ID,
        "name": "Top level",
        "path": "Top level",
        "depth": 0,
        "kind": "root",
        "iconKey": "folder",
        "iconUrl": _icon_url("folder", addon_package),
        "disabled": disabled,
        "reason": reason,
    }


def _can_move_to_root(
    source_id: str,
    deck_names: Mapping[str, str],
) -> bool:
    return deck_drag_drop._planned_root_names([source_id], "", deck_names) is not None


def _can_move_to_parent(
    source_id: str,
    target_id: str,
    deck_names: Mapping[str, str],
) -> bool:
    if deck_drag_drop._target_is_invalid(target_id, [source_id], deck_names):
        return False
    target_name = deck_names.get(target_id)
    if target_name is None:
        return False
    return deck_drag_drop._planned_root_names([source_id], target_name, deck_names) is not None


def _move_to_root(source_id: str, source_name: str) -> Tuple[bool, str]:
    deck = mw.col.decks.get(DeckId(int(source_id)))
    if not deck:
        return False, "Deck no longer exists."

    new_name = deck_drag_drop._leaf_name(source_name)
    if source_name == new_name:
        return False, "This deck is already at the top level."

    mw.col.decks.rename(deck, new_name)
    mw.col.setMod()
    return True, "Deck moved."


def _ensure_path_expanded(deck_name: str, deck_names: Mapping[str, str]) -> None:
    if not deck_name:
        return

    name_to_id = {name: did for did, name in deck_names.items()}
    parts = deck_name.split("::")
    changed = False

    for index in range(1, len(parts) + 1):
        ancestor_name = "::".join(parts[:index])
        did = name_to_id.get(ancestor_name)
        if not did:
            continue

        deck = mw.col.decks.get(DeckId(int(did)))
        if deck and deck.get("collapsed", False):
            mw.col.decks.collapse(int(did))
            changed = True

    if changed:
        mw.col.decks.save()


def _deck_icon_key(name: str, deck_names: Mapping[str, str], is_filtered: bool) -> str:
    if is_filtered:
        return "filtered_deck"
    if any(other != name and other.startswith(name + "::") for other in deck_names.values()):
        return "folder"
    if "::" in name:
        return "subdeck"
    return "deck"


def _icon_url(icon_key: str, addon_package: str) -> str:
    filename = mw.col.conf.get(f"modern_menu_icon_{icon_key}", "")
    if filename:
        return f"/_addons/{addon_package}/user_files/icons/{filename}"

    system_filename = ICON_DEFAULTS.get(icon_key, f"{icon_key}.svg")
    return f"/_addons/{addon_package}/system_files/system_icons/{system_filename}"
