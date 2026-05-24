from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set

from aqt import mw
from anki.decks import DeckId


VALID_DROP_TYPES = {"nest", "before", "after"}


def apply_drag_drop(payload: Mapping[str, Any]) -> bool:
    """Validate and apply an Onigiri deck-browser drag/drop payload.

    Returns True only when a real structural or custom-order change was saved.
    """
    drop_type = str(payload.get("type", "nest"))
    if drop_type not in VALID_DROP_TYPES:
        return False

    raw_sources = _coerce_id_list(payload.get("source_dids") or [payload.get("source_did")])
    target_ids = _coerce_id_list([payload.get("target_did")])
    if not raw_sources or not target_ids:
        return False

    target_id = target_ids[0]
    original_order = _coerce_id_list(payload.get("original_order", []))
    payload_new_order = _coerce_id_list(payload.get("new_order", []))
    base_order = _merge_orders(original_order, _current_tree_order(), payload_new_order)

    deck_names = _deck_names_by_id()
    if target_id not in deck_names:
        return False

    source_ids = _normalize_source_ids(raw_sources, base_order, deck_names)
    if not source_ids or target_id in source_ids:
        return False

    if _target_is_invalid(target_id, source_ids, deck_names):
        return False

    target_name = deck_names[target_id]
    affected_parent = target_name if drop_type == "nest" else _parent_name(target_name)
    planned_root_names = _planned_root_names(source_ids, affected_parent, deck_names)
    if planned_root_names is None:
        return False

    groups = _sorted_child_groups(deck_names, base_order)
    current_group = groups.get(affected_parent, [])
    desired_group = _desired_group(current_group, source_ids, target_id, drop_type)
    if desired_group is None:
        return False

    parent_changes = any(_parent_name(deck_names[did]) != affected_parent for did in source_ids)
    order_changes = desired_group != current_group
    if not parent_changes and not order_changes:
        return False

    if drop_type == "nest":
        if parent_changes:
            mw.col.decks.reparent([DeckId(int(did)) for did in source_ids], DeckId(int(target_id)))
    else:
        for did in source_ids:
            current_name = deck_names.get(did)
            planned_name = planned_root_names.get(did)
            if not current_name or not planned_name or current_name == planned_name:
                continue
            deck = mw.col.decks.get(DeckId(int(did)))
            if deck:
                mw.col.decks.rename(deck, planned_name)

    final_names = _deck_names_by_id()
    final_base_order = _merge_orders(payload_new_order, base_order, _current_tree_order())
    final_order = _build_custom_order(
        final_names,
        final_base_order,
        source_ids,
        target_id,
        drop_type,
        affected_parent,
    )
    if not final_order:
        return False

    mw.col.conf["onigiri_sort_mode"] = "custom"
    mw.col.conf["onigiri_deck_sort"] = "custom"
    mw.col.conf["onigiri_custom_deck_order"] = final_order
    mw.col.setMod()
    return True


def _coerce_id_list(values: Any) -> List[str]:
    if values is None:
        return []
    if not isinstance(values, (list, tuple, set)):
        values = [values]

    result: List[str] = []
    seen: Set[str] = set()
    for value in values:
        try:
            did = str(int(value))
        except (TypeError, ValueError):
            continue
        if did not in seen:
            result.append(did)
            seen.add(did)
    return result


def _merge_orders(*orders: Sequence[str]) -> List[str]:
    merged: List[str] = []
    seen: Set[str] = set()
    for order in orders:
        for did in order or []:
            did = str(did)
            if did and did not in seen:
                merged.append(did)
                seen.add(did)
    return merged


def _deck_names_by_id() -> Dict[str, str]:
    names: Dict[str, str] = {}
    for deck in mw.col.decks.all_names_and_ids():
        names[str(int(deck.id))] = str(deck.name)
    return names


def _current_tree_order() -> List[str]:
    try:
        tree = mw.col.sched.deck_due_tree()
        sort_mode = mw.col.conf.get("onigiri_sort_mode", "")
        if sort_mode:
            from . import deck_tree_updater

            saved_order = [str(value) for value in mw.col.conf.get("onigiri_custom_deck_order", [])]
            deck_tree_updater._apply_sort_recursive(tree.children, sort_mode, saved_order, is_top_level=True)

        order: List[str] = []

        def visit(nodes: Iterable[Any]) -> None:
            for node in nodes:
                order.append(str(node.deck_id))
                visit(node.children)

        visit(tree.children)
        return order
    except Exception:
        deck_names = _deck_names_by_id()
        return [
            did for did, _name in sorted(
                deck_names.items(),
                key=lambda item: (item[1].count("::"), item[1].lower()),
            )
        ]


def _normalize_source_ids(raw_ids: Sequence[str], base_order: Sequence[str], deck_names: Mapping[str, str]) -> List[str]:
    raw_set = {did for did in raw_ids if did in deck_names}
    if not raw_set:
        return []

    order_index = {did: idx for idx, did in enumerate(base_order)}
    raw_index = {did: idx for idx, did in enumerate(raw_ids)}
    ordered = sorted(
        raw_set,
        key=lambda did: (order_index.get(did, 10**9), raw_index.get(did, 10**9), deck_names[did].lower()),
    )

    roots: List[str] = []
    for did in ordered:
        name = deck_names[did]
        if any(other != did and _is_descendant_name(name, deck_names[other]) for other in ordered):
            continue
        roots.append(did)
    return roots


def _target_is_invalid(target_id: str, source_ids: Sequence[str], deck_names: Mapping[str, str]) -> bool:
    target_name = deck_names.get(target_id)
    if not target_name:
        return True
    for source_id in source_ids:
        source_name = deck_names.get(source_id)
        if not source_name:
            return True
        if target_name == source_name or _is_descendant_name(target_name, source_name):
            return True
    return False


def _parent_name(name: str) -> str:
    parts = name.split("::")
    return "::".join(parts[:-1])


def _leaf_name(name: str) -> str:
    return name.split("::")[-1]


def _child_name(parent: str, leaf: str) -> str:
    return f"{parent}::{leaf}" if parent else leaf


def _is_descendant_name(name: str, ancestor_name: str) -> bool:
    return bool(ancestor_name) and name.startswith(ancestor_name + "::")


def _moving_subtree_ids(source_ids: Sequence[str], deck_names: Mapping[str, str]) -> Set[str]:
    roots = [deck_names[did] for did in source_ids if did in deck_names]
    moving: Set[str] = set()
    for did, name in deck_names.items():
        if any(name == root or _is_descendant_name(name, root) for root in roots):
            moving.add(did)
    return moving


def _planned_root_names(
    source_ids: Sequence[str],
    target_parent: str,
    deck_names: Mapping[str, str],
) -> Optional[Dict[str, str]]:
    moving_ids = _moving_subtree_ids(source_ids, deck_names)
    reserved_names = {name for did, name in deck_names.items() if did not in moving_ids}
    planned_all_names: Set[str] = set()
    planned_roots: Dict[str, str] = {}

    for source_id in source_ids:
        source_name = deck_names.get(source_id)
        if not source_name:
            return None
        new_root = _child_name(target_parent, _leaf_name(source_name))
        planned_roots[source_id] = new_root

        for did, old_name in deck_names.items():
            if did not in moving_ids:
                continue
            if old_name != source_name and not _is_descendant_name(old_name, source_name):
                continue
            suffix = old_name[len(source_name):]
            new_name = new_root + suffix
            if new_name in reserved_names or new_name in planned_all_names:
                return None
            planned_all_names.add(new_name)

    return planned_roots


def _sorted_child_groups(deck_names: Mapping[str, str], base_order: Sequence[str]) -> Dict[str, List[str]]:
    order_index = {did: idx for idx, did in enumerate(base_order)}
    groups: Dict[str, List[str]] = defaultdict(list)
    for did, name in deck_names.items():
        groups[_parent_name(name)].append(did)

    for parent, dids in list(groups.items()):
        dids.sort(key=lambda did: (order_index.get(did, 10**9), _leaf_name(deck_names[did]).lower()))
        groups[parent] = dids
    return groups


def _desired_group(
    current_group: Sequence[str],
    source_ids: Sequence[str],
    target_id: str,
    drop_type: str,
) -> Optional[List[str]]:
    source_set = set(source_ids)
    group = [did for did in current_group if did not in source_set]

    if drop_type == "nest":
        return group + [did for did in source_ids if did not in group]

    if target_id not in group:
        return None

    insert_at = group.index(target_id)
    if drop_type == "after":
        insert_at += 1
    return group[:insert_at] + list(source_ids) + group[insert_at:]


def _build_custom_order(
    deck_names: Mapping[str, str],
    base_order: Sequence[str],
    source_ids: Sequence[str],
    target_id: str,
    drop_type: str,
    affected_parent: str,
) -> List[str]:
    groups = _sorted_child_groups(deck_names, base_order)
    current_group = groups.get(affected_parent, [])
    desired_group = _desired_group(current_group, source_ids, target_id, drop_type)
    if desired_group is None:
        return []
    groups[affected_parent] = desired_group

    result: List[str] = []

    def visit(parent: str) -> None:
        for did in groups.get(parent, []):
            if did not in deck_names:
                continue
            result.append(did)
            visit(deck_names[did])

    visit("")
    return result
