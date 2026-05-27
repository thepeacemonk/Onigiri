# In deck_tree_updater.py
import json
from aqt import mw
from aqt.deckbrowser import DeckBrowser, RenderDeckNodeContext
from anki.decks import DeckId
from . import onigiri_renderer

ARCHIVED_DECKS_CONF_KEY = "onigiri_archived_decks"
SHOW_ARCHIVED_CONF_KEY = "onigiri_show_archived"


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


def _replace_children(nodes_collection, nodes):
    """Replace a mutable protobuf children collection when supported."""
    try:
        del nodes_collection[:]
        nodes_collection.extend(nodes)
    except Exception:
        pass


def _prune_archived_descendants(nodes_collection, archived_ids):
    """Remove archived nodes, and their descendants, from a tree in-place."""
    kept = []
    for node in list(nodes_collection):
        if str(node.deck_id) in archived_ids:
            continue
        _prune_archived_descendants(node.children, archived_ids)
        kept.append(node)
    _replace_children(nodes_collection, kept)


def _archived_roots(nodes, archived_ids):
    """Collect archived nodes, preserving archived descendants only."""
    roots = []
    for node in list(nodes):
        if str(node.deck_id) in archived_ids:
            archived_children = _archived_roots(node.children, archived_ids)
            _replace_children(node.children, archived_children)
            roots.append(node)
        else:
            roots.extend(_archived_roots(node.children, archived_ids))
    return roots


def archived_deck_ids():
    """Return archived deck IDs as strings for consistent comparisons."""
    return set(str(did) for did in mw.col.conf.get(ARCHIVED_DECKS_CONF_KEY, []))


def apply_archive_filter(tree_data, archived_ids=None, show_archived_only=None):
    """Hide archived decks, or show only archived decks when requested."""
    archived_ids = archived_deck_ids() if archived_ids is None else set(str(did) for did in archived_ids)
    if show_archived_only is None:
        show_archived_only = bool(mw.col.conf.get(SHOW_ARCHIVED_CONF_KEY, False))

    if show_archived_only:
        _replace_children(tree_data.children, _archived_roots(tree_data.children, archived_ids))
    elif archived_ids:
        _prune_archived_descendants(tree_data.children, archived_ids)


def _organise_filter_matcher(archived_ids):
    """Return a direct-match predicate for the active Organise filters."""
    show_favorites = bool(mw.col.conf.get("onigiri_show_favorites", False))
    show_marked = bool(mw.col.conf.get("onigiri_show_marked", False))
    show_archived = bool(mw.col.conf.get(SHOW_ARCHIVED_CONF_KEY, False))

    favorites = set(str(f) for f in mw.col.conf.get("onigiri_favorite_decks", [])) if show_favorites else set()
    marks = dict(mw.col.conf.get("onigiri_deck_marks", {})) if show_marked else {}
    marked_ids = set(str(k) for k, v in marks.items() if v) if show_marked else set()

    def _matches(deck_id: str) -> bool:
        return (
            (show_favorites and deck_id in favorites)
            or (show_marked and deck_id in marked_ids)
            or (show_archived and deck_id in archived_ids)
        )

    return _matches, (show_favorites or show_marked or show_archived), show_archived


def _collect_direct_organise_matches(nodes, direct_match, archived_ids, allow_archived_nodes):
    """Return matching nodes only, preserving original tree order and depth."""
    matches = []
    for node in list(nodes):
        deck_id = str(node.deck_id)
        if deck_id in archived_ids and not allow_archived_nodes:
            continue
        if direct_match(deck_id):
            matches.append(node)
        matches.extend(
            _collect_direct_organise_matches(
                node.children,
                direct_match,
                archived_ids,
                allow_archived_nodes,
            )
        )
    return matches


def _render_direct_deck_row_html(deck_browser: DeckBrowser, node, ctx: RenderDeckNodeContext) -> str:
    """Render only the row for a deck node, excluding any descendant rows."""
    html = deck_browser._render_deck_node(node, ctx)
    row_end = html.find("</tr>")
    if row_end == -1:
        return html
    return html[:row_end + len("</tr>")]


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

    archived_ids = archived_deck_ids()
    direct_match, has_active_filters, allow_archived_nodes = _organise_filter_matcher(archived_ids)
    ctx = RenderDeckNodeContext(current_deck_id=deck_browser.mw.col.decks.get_current_id())
    if has_active_filters:
        matching_nodes = _collect_direct_organise_matches(
            tree_data.children,
            direct_match,
            archived_ids,
            allow_archived_nodes,
        )
        return "".join(
            _render_direct_deck_row_html(deck_browser, node, ctx)
            for node in matching_nodes
        )
    else:
        apply_archive_filter(tree_data, archived_ids=archived_ids, show_archived_only=False)

    # Note: _render_deck_node is patched by Onigiri in patcher.py
    return "".join(deck_browser._render_deck_node(child, ctx) for child in tree_data.children)


def _render_deck_search_tree_html_only(deck_browser: DeckBrowser, query: str) -> str:
    """Render deck rows matching a search query, including collapsed descendants."""
    normalized_query = (query or "").strip().lower()
    if not normalized_query:
        return _render_deck_tree_html_only(deck_browser)

    archived_ids = archived_deck_ids()
    show_archived_only = bool(mw.col.conf.get(SHOW_ARCHIVED_CONF_KEY, False))

    all_decks = mw.col.decks.all()
    archived_names = [
        d.get("name", "")
        for d in all_decks
        if str(d.get("id", "")) in archived_ids and d.get("name", "")
    ]

    def hidden_by_archived_parent(name):
        return any(
            name == archived_name or name.startswith(archived_name + "::")
            for archived_name in archived_names
        )

    matched_ids = set()
    for deck in all_decks:
        did = str(deck["id"])
        name = deck.get("name", "")
        if show_archived_only:
            if did not in archived_ids:
                continue
        elif did in archived_ids or hidden_by_archived_parent(name):
            continue

        leaf = name.split("::")[-1]
        if normalized_query in name.lower() or normalized_query in leaf.lower():
            matched_ids.add(did)

    tree_data = deck_browser.mw.col.sched.deck_due_tree()
    deck_browser._render_data = onigiri_renderer.RenderData(tree=tree_data)
    apply_archive_filter(
        tree_data,
        archived_ids=archived_ids,
        show_archived_only=show_archived_only,
    )

    ctx = RenderDeckNodeContext(current_deck_id=deck_browser.mw.col.decks.get_current_id())
    rows = []

    def collect_matching(nodes):
        for node in nodes:
            if str(node.deck_id) in matched_ids:
                rows.append(deck_browser._render_deck_node(node, ctx))
            else:
                collect_matching(node.children)

    collect_matching(tree_data.children)
    return "".join(rows)


def on_deck_collapse(deck_browser: DeckBrowser, deck_id: str, search_query: str = "") -> None:
    """
    Handles the collapse/expand action for a deck without a full page reload.
    Re-renders the tree HTML and uses JS to preserve checkbox *state*.
    When collapsing (deck was open -> now closed) child rows are animated out
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

        # Re-render only the deck tree, preserving an active sidebar search.
        new_tree_html = (
            _render_deck_search_tree_html_only(deck_browser, search_query)
            if search_query
            else _render_deck_tree_html_only(deck_browser)
        )

        # Escape the HTML for safe injection into a JavaScript string
        js_escaped_html = json.dumps(new_tree_html)

        # Send the new HTML to the frontend to be injected by JavaScript
        # When collapsing, animate children out first (120 ms), then swap.
        js = '''
        (function() {{
            const container = document.getElementById('deck-list-container');
            const scrollTop = container ? container.scrollTop : 0;
            const isCollapsing = {is_collapsing};
            const deckId = "{deck_id}";

            function doUpdate() {{
                OnigiriEngine.updateDeckTree({new_tree_html}, {{force: true}});
                if (container) container.scrollTop = scrollTop;
            }}

            if (isCollapsing) {{
                // Collect child rows and lower rows (siblings after the parent row in the tbody)
                const tbody = document.querySelector('#decktree > tbody');
                const parentRow = tbody ? tbody.querySelector('tr.deck[data-did="' + deckId + '"]') : null;
                const childRows = [];
                const lowerRows = [];
                if (parentRow) {{
                    const parentLevel = parseInt(parentRow.dataset.level || '1', 10);
                    let el = parentRow.nextElementSibling;
                    let isChild = true;
                    while (el && el.tagName === 'TR' && el.classList.contains('deck')) {{
                        const level = parseInt(el.dataset.level || '1', 10);
                        if (isChild && level > parentLevel) {{
                            childRows.push(el);
                        }} else {{
                            isChild = false;
                            lowerRows.push(el);
                        }}
                        el = el.nextElementSibling;
                    }}
                }}
                if (childRows.length > 0) {{
                    let totalChildHeight = 0;
                    childRows.forEach(function(r) {{
                        totalChildHeight += r.offsetHeight || 0;
                        r.classList.add('deck-row-disappear');
                    }});
                    if (totalChildHeight > 0 && lowerRows.length > 0) {{
                        lowerRows.forEach(function(r) {{
                            r.style.transition = 'transform 120ms cubic-bezier(0.55, 0, 1, 0.45)';
                            r.style.transform = 'translateY(-' + totalChildHeight + 'px)';
                        }});
                    }}
                    setTimeout(doUpdate, 135);
                    return;
                }}
            }} else {{
                // Expanding: let new child rows fade in (deck-row-appear handles opacity).
                // Use proper FLIP to slide lower surviving rows down smoothly.

                // 1. Snapshot positions of ALL current rows by data-did BEFORE swap
                const tbody = document.querySelector('#decktree > tbody');
                const prePositions = {{}};
                if (tbody) {{
                    tbody.querySelectorAll('tr.deck[data-did]').forEach(function(r) {{
                        prePositions[r.dataset.did] = r.getBoundingClientRect().top;
                    }});
                }}

                // 2. Swap DOM
                doUpdate();

                // 3. FLIP: for every row that existed before, compute delta and offset it back
                if (tbody) {{
                    requestAnimationFrame(function() {{
                        const movedRows = [];
                        tbody.querySelectorAll('tr.deck[data-did]').forEach(function(r) {{
                            const did = r.dataset.did;
                            if (did in prePositions) {{
                                const delta = r.getBoundingClientRect().top - prePositions[did];
                                if (Math.abs(delta) > 0.5) {{
                                    r.style.transition = 'none';
                                    r.style.transform = 'translateY(' + (-delta) + 'px)';
                                    movedRows.push(r);
                                }}
                            }}
                        }});

                        if (movedRows.length > 0) {{
                            requestAnimationFrame(function() {{
                                movedRows.forEach(function(r) {{
                                    r.style.transition = 'transform 120ms cubic-bezier(0.16,1,0.3,1)';
                                    r.style.transform = 'translateY(0)';
                                }});
                                setTimeout(function() {{
                                    movedRows.forEach(function(r) {{
                                        r.style.transition = '';
                                        r.style.transform = '';
                                    }});
                                }}, 135);
                            }});
                        }}
                    }});
                }}
                return;
            }}

            doUpdate();
        }})();
        '''.format(is_collapsing=str(is_collapsing).lower(), deck_id=deck_id, new_tree_html=js_escaped_html)

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
        print(f"Onigiri: converted to DeckIds - source_dids: {source_dids}, target_did: {target_did}")

        # Anki's reparent function handles invalid moves (e.g., moving a parent into its child)
        mw.col.decks.reparent(source_dids, target_did)
        print(f"Onigiri: Successfully called reparent")

        if mw.deckBrowser:
            refresh_deck_tree_state(mw.deckBrowser)
            print(f"Onigiri: Successfully refreshed deck browser locally")
        else:
            print(f"Onigiri: deckBrowser is None, cannot refresh")

    except (ValueError, TypeError, json.JSONDecodeError) as e:
        print(f"Onigiri: Could not process deck move request: {e}")

def refresh_deck_tree_state(deck_browser: DeckBrowser, force: bool = False) -> None:
    """
    Handles a full refresh of the deck tree HTML while preserving
    scroll and edit mode state. Used for favorite toggling.
    Preserves existing checkbox *state* in the DOM by saving and restoring it.

    Args:
        force: If True, bypass the UI-open deferral and refresh immediately.
               Used for organise menu filter/sort actions.
    """
    try:
        if onigiri_renderer._onigiri_ui_open and not force:
            onigiri_renderer._onigiri_tree_refresh_deferred = True
            return

        # Refresh the tree data
        tree_data = deck_browser.mw.col.sched.deck_due_tree()
        deck_browser._render_data = onigiri_renderer.RenderData(tree=tree_data)
        
        # Re-render only the deck tree
        new_tree_html = _render_deck_tree_html_only(deck_browser)

        # Escape the HTML for safe injection into a JavaScript string
        js_escaped_html = json.dumps(new_tree_html)
        
        # updateDeckTree preserves scroll, hover, and edit-mode checkbox selection
        js = '''
        (function attemptDeckTreeUpdate(retries) {{
            if (!window.OnigiriEngine || typeof OnigiriEngine.updateDeckTree !== 'function') {{
                if (retries > 0) {{
                    setTimeout(function() {{ attemptDeckTreeUpdate(retries - 1); }}, 50);
                }}
                return;
            }}

            const container = document.getElementById('deck-list-container');
            const scrollTop = container ? container.scrollTop : 0;

            const checkboxStateMap = new Map();
            document.querySelectorAll('.deck-checkbox').forEach(cb => {{
                const did = cb.dataset.did;
                if (did) checkboxStateMap.set(did, cb.checked);
            }});

            OnigiriEngine.updateDeckTree({new_tree_html}, {{force: {force_js}}});

            if (typeof OnigiriEditor !== 'undefined' && OnigiriEditor.EDIT_MODE) {{
                checkboxStateMap.forEach((isChecked, did) => {{
                    if (isChecked) OnigiriEditor.SELECTED_DECKS.add(did);
                    else OnigiriEditor.SELECTED_DECKS.delete(did);
                }});
                OnigiriEditor.reapplyEditModeState();
            }}

            if (container) container.scrollTop = scrollTop;
        }})(10);
        '''.format(new_tree_html=js_escaped_html, force_js="true" if force else "false")

        deck_browser.web.eval(js)

    except Exception as e:
        print(f"Onigiri: Error in refresh_deck_tree_state: {e}")
        import traceback
        traceback.print_exc()
