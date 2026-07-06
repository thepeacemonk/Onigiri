import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from anki.decks import DeckId
from aqt import mw

from . import drag_drop as deck_drag_drop
from ..constants import ICON_DEFAULTS


ROOT_DESTINATION_ID = "__root__"


def build_move_to_payload(source_dids: Any) -> Dict[str, Any]:
    deck_names = deck_drag_drop._deck_names_by_id()
    source_ids = _normalize_source_ids(source_dids, deck_names)
    if not source_ids:
        raise ValueError("Invalid deck ID.")

    source_names = [deck_names.get(source_id, "") for source_id in source_ids]
    if any(not name for name in source_names):
        raise ValueError("Deck no longer exists.")

    moving_ids, move_plan = _build_move_destination_plan(source_ids, deck_names)
    filtered_ids = _filtered_deck_ids()
    folder_names = _folder_names(deck_names)
    addon_package = mw.addonManager.addonFromModule(__name__)
    icon_cache: Dict[str, str] = {}

    def icon_url(icon_key: str) -> str:
        if icon_key not in icon_cache:
            icon_cache[icon_key] = _icon_url(icon_key, addon_package)
        return icon_cache[icon_key]

    destinations: List[Dict[str, Any]] = []
    destinations.append(
        _root_destination(source_ids, deck_names, move_plan, icon_url)
    )

    for did, name in sorted(
        deck_names.items(),
        key=lambda item: (item[1].count("::"), item[1].lower()),
    ):
        if did in moving_ids:
            continue

        if did in filtered_ids:
            continue
        icon_key = _deck_icon_key(name, folder_names, False)

        disabled = False
        reason = ""
        if _all_sources_already_in_parent(source_ids, name, deck_names):
            disabled = True
            reason = "Current parent"
        elif not _planned_names_available(move_plan, name):
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
                "iconUrl": icon_url(icon_key),
                "disabled": disabled,
                "reason": reason,
            }
        )

    primary_name = source_names[0]
    source_count = len(source_ids)
    return {
        "source": {
            "id": source_ids[0],
            "ids": source_ids,
            "name": primary_name,
            "names": source_names,
            "leaf": deck_drag_drop._leaf_name(primary_name),
            "parent": deck_drag_drop._parent_name(primary_name),
            "count": source_count,
            "label": deck_drag_drop._leaf_name(primary_name) if source_count == 1 else f"{source_count} selected decks",
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

    deck_names = deck_drag_drop._deck_names_by_id()
    source_value = payload.get("source_dids", payload.get("source_did"))
    source_ids = _normalize_source_ids(source_value, deck_names)
    if not source_ids:
        return False, "Invalid source deck."

    target_id = payload.get("target_did")
    to_root = target_id == ROOT_DESTINATION_ID or target_id is None

    source_names = [deck_names.get(source_id, "") for source_id in source_ids]
    if any(not name for name in source_names):
        return False, "Deck no longer exists."

    if to_root:
        if all(not deck_drag_drop._parent_name(name) for name in source_names):
            return False, _message(source_ids, "This deck is already at the top level.", "These decks are already at the top level.")
        if not _can_move_to_root(source_ids, deck_names):
            return False, _message(source_ids, "A top-level deck with that name already exists.", "A top-level deck with one of those names already exists.")
        return _move_to_root(source_ids, deck_names)

    target_id = _normalize_did(target_id)
    if not target_id:
        return False, "Invalid destination deck."

    target_name = deck_names.get(target_id)
    if not target_name:
        return False, "Destination deck no longer exists."

    if _all_sources_already_in_parent(source_ids, target_name, deck_names):
        return False, _message(source_ids, "This deck is already in that parent.", "These decks are already in that parent.")

    target_deck = mw.col.decks.get(DeckId(int(target_id)))
    if target_deck and target_deck.get("dyn", 0):
        return False, "Filtered decks cannot be used as move destinations."

    if not _can_move_to_parent(source_ids, target_id, deck_names):
        return False, _message(source_ids, "That destination is not valid for this deck.", "That destination is not valid for these decks.")

    mw.col.decks.reparent([DeckId(int(source_id)) for source_id in source_ids], DeckId(int(target_id)))
    _ensure_path_expanded(target_name, deck_names)
    mw.col.setMod()
    return True, _message(source_ids, "Deck moved.", "Decks moved.")


def _normalize_did(value: Any) -> Optional[str]:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return None


def _normalize_source_ids(source_dids: Any, deck_names: Mapping[str, str]) -> List[str]:
    if isinstance(source_dids, (str, int)):
        raw_values: Sequence[Any] = [source_dids]
    elif isinstance(source_dids, Sequence):
        raw_values = source_dids
    else:
        raw_values = []

    raw_ids: List[str] = []
    seen = set()
    for value in raw_values:
        did = _normalize_did(value)
        if not did or did in seen:
            continue
        raw_ids.append(did)
        seen.add(did)

    try:
        base_order = deck_drag_drop._current_tree_order()
    except Exception:
        base_order = list(deck_names.keys())
    return deck_drag_drop._normalize_source_ids(raw_ids, base_order, deck_names)


def _filtered_deck_ids() -> set:
    filtered = set()
    try:
        for deck in mw.col.decks.all():
            if not deck.get("dyn", 0):
                continue
            did = _normalize_did(deck.get("id"))
            if did:
                filtered.add(did)
    except Exception:
        pass
    return filtered


def _folder_names(deck_names: Mapping[str, str]) -> set:
    folders = set()
    for name in deck_names.values():
        parts = name.split("::")
        for index in range(1, len(parts)):
            folders.add("::".join(parts[:index]))
    return folders


def _build_move_destination_plan(
    source_ids: Sequence[str],
    deck_names: Mapping[str, str],
) -> Tuple[set, Dict[str, Any]]:
    moving_ids = deck_drag_drop._moving_subtree_ids(source_ids, deck_names)
    reserved_names = {name for did, name in deck_names.items() if did not in moving_ids}
    source_suffixes = []

    for source_id in source_ids:
        source_name = deck_names.get(source_id)
        if not source_name:
            continue

        suffixes = []
        for did, old_name in deck_names.items():
            if did not in moving_ids:
                continue
            if old_name == source_name or deck_drag_drop._is_descendant_name(old_name, source_name):
                suffixes.append(old_name[len(source_name):])

        source_suffixes.append(
            {
                "leaf": deck_drag_drop._leaf_name(source_name),
                "suffixes": suffixes,
            }
        )

    return moving_ids, {
        "reserved_names": reserved_names,
        "source_suffixes": source_suffixes,
    }


def _planned_names_available(move_plan: Mapping[str, Any], target_parent: str) -> bool:
    reserved_names = move_plan.get("reserved_names", set())
    planned_names = set()

    for source in move_plan.get("source_suffixes", []):
        new_root = deck_drag_drop._child_name(target_parent, source["leaf"])
        for suffix in source["suffixes"]:
            new_name = new_root + suffix
            if new_name in reserved_names or new_name in planned_names:
                return False
            planned_names.add(new_name)

    return True


def _root_destination(
    source_ids: Sequence[str],
    deck_names: Mapping[str, str],
    move_plan: Mapping[str, Any],
    icon_url,
) -> Dict[str, Any]:
    disabled = False
    reason = ""
    source_names = [deck_names[did] for did in source_ids if did in deck_names]

    if source_names and all(not deck_drag_drop._parent_name(name) for name in source_names):
        disabled = True
        reason = "Current location"
    elif not _planned_names_available(move_plan, ""):
        disabled = True
        reason = "Name conflict"

    return {
        "id": ROOT_DESTINATION_ID,
        "name": "Top level",
        "path": "Top level",
        "depth": 0,
        "kind": "root",
        "iconKey": "folder",
        "iconUrl": icon_url("folder"),
        "disabled": disabled,
        "reason": reason,
    }


def _can_move_to_root(
    source_ids: Sequence[str],
    deck_names: Mapping[str, str],
) -> bool:
    return deck_drag_drop._planned_root_names(source_ids, "", deck_names) is not None


def _can_move_to_parent(
    source_ids: Sequence[str],
    target_id: str,
    deck_names: Mapping[str, str],
) -> bool:
    if deck_drag_drop._target_is_invalid(target_id, source_ids, deck_names):
        return False
    target_name = deck_names.get(target_id)
    if target_name is None:
        return False
    return deck_drag_drop._planned_root_names(source_ids, target_name, deck_names) is not None


def _move_to_root(source_ids: Sequence[str], deck_names: Mapping[str, str]) -> Tuple[bool, str]:
    changed = False
    for source_id in source_ids:
        source_name = deck_names.get(source_id)
        deck = mw.col.decks.get(DeckId(int(source_id)))
        if not deck or not source_name:
            return False, "Deck no longer exists."

        new_name = deck_drag_drop._leaf_name(source_name)
        if source_name == new_name:
            continue

        mw.col.decks.rename(deck, new_name)
        changed = True

    if not changed:
        return False, _message(source_ids, "This deck is already at the top level.", "These decks are already at the top level.")
    mw.col.setMod()
    return True, _message(source_ids, "Deck moved.", "Decks moved.")


def _all_sources_already_in_parent(
    source_ids: Sequence[str],
    parent_name: str,
    deck_names: Mapping[str, str],
) -> bool:
    if not source_ids:
        return False
    return all(deck_drag_drop._parent_name(deck_names.get(source_id, "")) == parent_name for source_id in source_ids)


def _message(source_ids: Sequence[str], single: str, multi: str) -> str:
    return single if len(source_ids) == 1 else multi


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


def _deck_icon_key(name: str, folder_names: set, is_filtered: bool) -> str:
    if is_filtered:
        return "filtered_deck"
    if name in folder_names:
        return "folder"
    if "::" in name:
        return "subdeck"
    return "deck"


def _icon_url(icon_key: str, addon_package: str) -> str:
    filename = mw.col.conf.get(f"modern_menu_icon_{icon_key}", "")
    if filename:
        if str(filename).startswith("system:"):
            system_filename = str(filename)[len("system:"):]
            return f"/_addons/{addon_package}/system_files/system_icons/available_for_users/{system_filename}"
        return f"/_addons/{addon_package}/user_files/icons/{filename}"

    system_filename = ICON_DEFAULTS.get(icon_key, f"{icon_key}.svg")
    return f"/_addons/{addon_package}/system_files/system_icons/unavailable_for_users/{system_filename}"
