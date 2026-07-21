# Learner Stats Widget for Onigiri

import html
import json
from aqt import mw
from aqt.deckbrowser import DeckBrowser

def get_translated_labels():
    """Widget labels, resolved through the add-on's own translation table.

    These used to be a hardcoded English/Vietnamese pair keyed off Anki's
    `defaultLang`, so every other language fell back to English and the widget
    ignored Onigiri's language selector. Now it follows `tr()` like the rest of
    the UI; the second argument is only a safety net if a key ever goes missing.
    """
    from .translations import tr

    return {
        # The card title reuses the shared "stats" key; the header CSS
        # uppercases it, so it is stored in natural case.
        "title": tr("stats", "Stats"),
        "all_decks": tr("lstats_all_decks", "All Decks"),
        "new": tr("lstats_new", "New"),
        "learning": tr("lstats_learning", "Learning"),
        "relearning": tr("lstats_relearning", "Relearning"),
        "mature": tr("lstats_mature", "Mature"),
        "young": tr("lstats_young", "Young"),
        "unseen": tr("lstats_unseen", "Unseen"),
        "buried": tr("lstats_buried", "Buried"),
        "suspended": tr("lstats_suspended", "Suspended"),
        "total": tr("lstats_total", "Total"),
        "total_short": tr("lstats_total_short", "total"),
        "group_in_progress": tr("lstats_group_in_progress", "In Progress"),
        "group_mastered": tr("lstats_group_mastered", "Mastered"),
        "group_others": tr("lstats_group_others", "Others"),
        "view_grouped": tr("lstats_view_grouped", "Grouped"),
        "view_bars": tr("lstats_view_bars", "Bars"),
        "view_donut": tr("lstats_view_donut", "Donut"),
        # Deck-picker modal chrome and screen-reader labels.
        "save": tr("save", "Save"),
        "cancel": tr("cancel", "Cancel"),
        "close": tr("close", "Close"),
        "preparing": tr("lstats_preparing", "Preparing your Onigiri"),
        "view_switcher": tr("lstats_view_switcher", "Stats view"),
        # Deck-picker modal, styled after the Create New Deck dialog.
        "picker_title": tr("lstats_picker_title", "Select Deck"),
        "picker_subtitle": tr("lstats_picker_subtitle", "Choose which deck to show stats for"),
        "all_decks_hint": tr("lstats_all_decks_hint", "Stats across your whole collection"),
        "search_decks": tr("prep_search_decks_placeholder", "Search decks\u2026"),
        "no_results": tr("no_results_found", "No results found."),
    }

def get_card_stats(selected_did, all_decks):
    """Card counts using Anki's own bucketing rules.

    Mirrors Anki's Card Counts graph: suspended and buried win over everything
    (they are queue states), and the remaining cards are split by card *type*
    (`cards.type`: 0 new, 1 learning, 2 review, 3 relearning) rather than by
    queue. Bucketing on queue alone folded relearning into learning and moved
    day-learn cards into the wrong column.
    """
    new_cnt = 0
    learn_cnt = 0
    relearn_cnt = 0
    mature_cnt = 0
    young_cnt = 0
    learned_cnt = 0
    unseen_cnt = 0
    buried_cnt = 0
    suspended_cnt = 0
    total_cnt = 0

    if not mw.col:
        return (new_cnt, learn_cnt, relearn_cnt, mature_cnt, young_cnt, learned_cnt, unseen_cnt, buried_cnt, suspended_cnt, total_cnt)

    if selected_did == "all":
        rows = mw.col.db.all("""
            select
                queue,
                type,
                case when reps = 0 then 1 else 0 end,
                case when ivl >= 21 then 1 else 0 end,
                count()
            from cards
            group by 1, 2, 3, 4
        """)
    else:
        try:
            parent_name = mw.col.decks.name(int(selected_did))
        except Exception:
            parent_name = ""

        if not parent_name:
            rows = []
        else:
            dids = [d.id for d in all_decks if d.name == parent_name or d.name.startswith(parent_name + "::")]
            dids_str = ",".join(str(did) for did in dids)
            rows = mw.col.db.all(f"""
                select
                    queue,
                    type,
                    case when reps = 0 then 1 else 0 end,
                    case when ivl >= 21 then 1 else 0 end,
                    count()
                from cards
                where did in ({dids_str})
                group by 1, 2, 3, 4
            """)

    for queue, ctype, is_unseen, is_mature, count in rows:
        total_cnt += count
        if is_unseen:
            unseen_cnt += count

        if queue == -1:
            suspended_cnt += count
        elif queue in (-2, -3):
            buried_cnt += count
        elif ctype == 0:
            new_cnt += count
        elif ctype == 1:
            learn_cnt += count
        elif ctype == 3:
            relearn_cnt += count
        elif ctype == 2:
            learned_cnt += count
            if is_mature:
                mature_cnt += count
            else:
                young_cnt += count

    return (new_cnt, learn_cnt, relearn_cnt, mature_cnt, young_cnt, learned_cnt, unseen_cnt, buried_cnt, suspended_cnt, total_cnt)

# Category -> (CSS variable, hard fallback). The variables are emitted per
# theme from the Deck Stats settings section; the fallbacks are Anki's own Card
# Counts palette so the widget still looks native if the CSS block is missing.
_TONE_COLOR_VARS = {
    "in_progress": ("--stats-in-progress-color", "#5eaadf"),
    "mastered": ("--stats-mastered-color", "#26a641"),
    "new": ("--stats-new-color", "#5eaadf"),
    "learning": ("--stats-learning-color", "#f5a05a"),
    "relearning": ("--stats-relearning-color", "#f4685f"),
    "young": ("--stats-young-color", "#7cc87c"),
    "mature": ("--stats-mature-color", "#26a641"),
    "unseen": ("--stats-unseen-color", "#b0b4b9"),
    "suspended": ("--stats-suspended-color", "#ffdc41"),
    "buried": ("--stats-buried-color", "#9e9e9e"),
    "total": ("--stats-total-color", "#6f7177"),
}


def _deck_display_name(deck_name: str) -> str:
    leaf_name = str(deck_name or "").split("::")[-1]
    return leaf_name.strip()

def _selected_deck_label(selected_did, all_decks, labels) -> str:
    if selected_did == "all":
        return labels["all_decks"]
    for deck in all_decks:
        if str(deck.id) == str(selected_did):
            return _deck_display_name(deck.name)
    return labels["all_decks"]

import base64
import os

def _get_data_uri(path):
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode("utf-8")
            if path.lower().endswith(".png"):
                return f"data:image/png;base64,{b64}"
            else:
                return f"data:image/svg+xml;base64,{b64}"
    except Exception:
        return ""

def _get_deck_icon_data(did, name, has_children):
    addon_dir = os.path.dirname(__file__)
    custom_deck_icons = mw.col.conf.get("onigiri_custom_deck_icons", {})
    custom_data = custom_deck_icons.get(str(did), {})
    icon_file = custom_data.get("icon")
    
    if icon_file:
        is_emoji = icon_file.startswith("emoji:") or (len(icon_file) <= 8 and "." not in icon_file and not icon_file.startswith("system:"))
        if is_emoji:
            emoji_char = icon_file[len("emoji:"):] if icon_file.startswith("emoji:") else icon_file
            return {"type": "emoji", "content": emoji_char}
        if icon_file.startswith("system:"):
            path = os.path.join(addon_dir, "system_files", "system_icons", "available_for_users", icon_file[7:])
            if os.path.exists(path):
                return {"type": "url", "url": _get_data_uri(path)}
        else:
            for folder in ("custom_deck_icons", "icons"):
                path = os.path.join(addon_dir, "user_files", folder, icon_file)
                if os.path.exists(path):
                    return {"type": "url", "url": _get_data_uri(path)}

    is_filtered = False
    deck = mw.col.decks.get(did)
    if deck:
        is_filtered = deck.get("dyn", 0) != 0
        
    icon_key = "deck"
    if is_filtered:
        icon_key = "filtered_deck"
    elif has_children:
        icon_key = "folder"
    elif "::" in name:
        icon_key = "subdeck"
        
    filename = mw.col.conf.get(f"modern_menu_icon_{icon_key}", "")
    if filename:
        if str(filename).startswith("system:"):
            system_filename = str(filename)[len("system:"):]
            path = os.path.join(addon_dir, "system_files", "system_icons", "available_for_users", system_filename)
            if os.path.exists(path):
                return {"type": "url", "url": _get_data_uri(path)}
        else:
            for folder in ("custom_deck_icons", "icons"):
                path = os.path.join(addon_dir, "user_files", folder, filename)
                if os.path.exists(path):
                    return {"type": "url", "url": _get_data_uri(path)}
        
    system_filename = f"{icon_key}.svg"
    if icon_key == "filtered_deck": 
        system_filename = "filtered-deck.svg"
    path = os.path.join(addon_dir, "system_files", "system_icons", "unavailable_for_users", system_filename)
    return {"type": "url", "url": _get_data_uri(path)}

def _flatten_picker_nodes(nodes, out, depth=0, prefix=""):
    """Depth-first walk of the deck tree into a flat list.

    The picker mirrors the Create New Deck dialog, which is a flat searchable
    list rather than a collapsible tree -- searching a tree means either hiding
    matches inside collapsed parents or expanding everything, and neither reads
    well in a modal this size. Rows are indented by depth and carry their full
    `::` path, so folders, decks and same-named subdecks stay distinguishable.

    `node.name` is only the leaf component, so the full path is rebuilt here.
    """
    for node in nodes:
        full_path = f"{prefix}::{node.name}" if prefix else str(node.name or "")
        out.append((node, depth, full_path))
        if node.children:
            _flatten_picker_nodes(node.children, out, depth + 1, full_path)
    return out


def _picker_row_html(did, icon_html, name, path, is_selected, depth=0) -> str:
    row_classes = "learner-stats-picker-row"
    if is_selected:
        row_classes += " learner-stats-picker-selected"
    # Indent nested decks so the hierarchy is readable in the flat list.
    indent = f' style="padding-left: {10 + depth * 18}px;"' if depth else ""
    path_html = (
        f'<div class="learner-stats-picker-path">{html.escape(path)}</div>'
        if path else ""
    )
    return f"""
        <div class="{row_classes}"{indent} data-did="{html.escape(str(did), quote=True)}"
             data-search="{html.escape((name + " " + path).lower(), quote=True)}">
            {icon_html}
            <div class="learner-stats-picker-text">
                <div class="learner-stats-picker-name">{html.escape(name)}</div>
                {path_html}
            </div>
        </div>
    """


def _render_deck_picker_html(deck_browser: DeckBrowser, selected_did, labels) -> str:
    if getattr(deck_browser, "_render_data", None):
        tree_data = deck_browser._render_data.tree
    else:
        tree_data = mw.col.sched.deck_due_tree()

    try:
        from .decks import tree_updater
        tree_updater._apply_tree_preferences(tree_data)
    except Exception:
        pass

    addon_dir = os.path.dirname(__file__)
    all_decks_icon_path = os.path.join(addon_dir, "system_files", "system_icons", "unavailable_for_users", "deck.svg")
    all_decks_icon_url = _get_data_uri(all_decks_icon_path)
    all_decks_icon = f'<span class="learner-stats-picker-icon" style="-webkit-mask-image: url(\'{all_decks_icon_url}\'); mask-image: url(\'{all_decks_icon_url}\');"></span>'

    rows = [_picker_row_html(
        "all",
        all_decks_icon,
        labels["all_decks"],
        labels["all_decks_hint"],
        selected_did == "all",
    )]

    for node, depth, full_path in _flatten_picker_nodes(tree_data.children, []):
        icon_data = _get_deck_icon_data(node.deck_id, full_path, bool(node.children))
        if icon_data["type"] == "emoji":
            icon_html = f'<span class="learner-stats-picker-icon emoji-icon">{html.escape(icon_data["content"])}</span>'
        else:
            icon_html = f'<span class="learner-stats-picker-icon" style="-webkit-mask-image: url(\'{icon_data["url"]}\'); mask-image: url(\'{icon_data["url"]}\');"></span>'
        # Top-level decks would only repeat their own name as the path.
        path_label = full_path.replace("::", " :: ") if depth else ""
        rows.append(_picker_row_html(
            node.deck_id,
            icon_html,
            _deck_display_name(full_path),
            path_label,
            str(selected_did) == str(node.deck_id),
            depth,
        ))

    return f"""
    <div class="learner-stats-picker-list">
        {"".join(rows)}
        <div class="learner-stats-picker-empty">{html.escape(labels["no_results"])}</div>
    </div>
    """

def saved_row_span(widget_id: str) -> int:
    """Row span this widget occupies in the saved dashboard layout.

    Lets callers that re-render the widget outside the grid loop (the deck-change
    pycmd handler) keep the compact/full body the user actually sees, instead of
    silently snapping back to the 2-row layout.
    """
    try:
        from . import config
        conf = config.get_config()
        if widget_id == "deck_stats":
            entry = conf.get("onigiriWidgetLayout", {}).get("grid", {}).get("deck_stats", {})
            return max(1, int(entry.get("row", 2)))
        entry = conf.get("externalWidgetLayout", {}).get("grid", {}).get(widget_id, {})
        return max(1, int(entry.get("row_span", 2)))
    except Exception:
        return 2


def chart_type() -> str:
    """"minimal" (In Progress / Mastered grouping) or "full" (per-category).

    Set from the Deck Stats settings section; anything unrecognised falls back
    to the historical grouped look.
    """
    try:
        from . import config
        style = config.get_config_readonly().get("deck_stats_style", {})
        value = str(style.get("chart_type", "minimal")) if isinstance(style, dict) else "minimal"
    except Exception:
        value = "minimal"
    return value if value in ("minimal", "full") else "minimal"


def _render_widget(deck_browser: DeckBrowser, widget_id: str, row_span: int = None) -> str:
    labels = get_translated_labels()
    if row_span is None:
        row_span = saved_row_span(widget_id)
    is_compact = row_span <= 1
    
    # Persistent settings mapping widget ID to selected deck ID
    saved_decks = mw.col.conf.get("onigiri_learner_stats_decks", {})
    selected_did = saved_decks.get(widget_id, "all")

    # Get sorted list of decks
    all_decks = []
    if mw.col:
        try:
            all_decks = mw.col.decks.all_names_and_ids()
            all_decks = sorted(all_decks, key=lambda d: d.name.lower())
        except Exception:
            pass
            
    deck_exists = any(str(d.id) == str(selected_did) for d in all_decks) if selected_did != "all" else False
    if selected_did != "all" and not deck_exists:
        selected_did = "all"

    # Get statistics
    (new_cnt, learn_cnt, relearn_cnt, mature_cnt, young_cnt, learned_cnt, unseen_cnt, buried_cnt, suspended_cnt, total_cnt) = get_card_stats(selected_did, all_decks)

    # Two-tone grouping used by the grouped bar / donut ring / bar-view fills:
    # "in progress" (new + learning + relearning) vs "mastered" (young +
    # mature, i.e. every card that has graduated into review).
    in_progress_cnt = new_cnt + learn_cnt + relearn_cnt
    mastered_cnt = young_cnt + mature_cnt

    def _pct_of(count: int) -> float:
        if total_cnt <= 0:
            return 0.0
        return round(min(100.0, (count / total_cnt) * 100), 2)

    in_progress_pct = _pct_of(in_progress_cnt)
    mastered_pct = _pct_of(mastered_cnt)

    # Full chart mode drops the two-tone grouping and charts each card
    # category on its own. These seven buckets are mutually exclusive and add
    # up to the deck total (see get_card_stats), so they tile the bar/ring
    # exactly; Unseen is deliberately absent because it overlaps New.
    is_full_chart = chart_type() == "full"
    full_categories = [
        (labels["new"], new_cnt, "new"),
        (labels["learning"], learn_cnt, "learning"),
        (labels["relearning"], relearn_cnt, "relearning"),
        (labels["young"], young_cnt, "young"),
        (labels["mature"], mature_cnt, "mature"),
        (labels["buried"], buried_cnt, "buried"),
        (labels["suspended"], suspended_cnt, "suspended"),
    ]

    # Donut ring geometry: r=15.5 circle, matching the stroke-dasharray scheme.
    import math
    ring_circumference = round(2 * math.pi * 15.5, 2)
    in_progress_arc = round(ring_circumference * in_progress_pct / 100, 2)
    mastered_arc = round(ring_circumference * mastered_pct / 100, 2)
    mastered_offset = -in_progress_arc

    # Per-category bar-view fill widths, each relative to the deck total.
    new_bar_pct = _pct_of(new_cnt)
    learn_bar_pct = _pct_of(learn_cnt)
    relearn_bar_pct = _pct_of(relearn_cnt)
    young_bar_pct = _pct_of(young_cnt)
    mature_bar_pct = _pct_of(mature_cnt)
    unseen_bar_pct = _pct_of(unseen_cnt)

    saved_views = mw.col.conf.get("onigiri_learner_stats_view", {})
    active_view = saved_views.get(widget_id, "grouped") if isinstance(saved_views, dict) else "grouped"
    if active_view not in ("grouped", "bars", "donut"):
        active_view = "grouped"

    deck_label = _selected_deck_label(selected_did, all_decks, labels)
    escaped_widget_id = html.escape(str(widget_id), quote=True)
    picker_html = _render_deck_picker_html(deck_browser, selected_did, labels)
    picker_payload = html.escape(json.dumps({
        "widgetId": str(widget_id),
        "selectedDid": str(selected_did),
        "title": labels["picker_title"],
        "subtitle": labels["picker_subtitle"],
        "search": labels["search_decks"],
        "save": labels["save"],
        "cancel": labels["cancel"],
        "close": labels["close"],
        "preparing": labels["preparing"],
        # Header glyph, so this modal reads as the same family as the
        # Create New Deck dialog (accent icon + title + close).
        "titleIcon": _get_data_uri(os.path.join(
            os.path.dirname(__file__),
            "system_files", "system_icons", "unavailable_for_users", "deck.svg",
        )),
        "searchIcon": _get_data_uri(os.path.join(
            os.path.dirname(__file__),
            "system_files", "system_icons", "unavailable_for_users", "search.svg",
        )),
    }), quote=True)

    # Generate CSS
    # Static styles live in web/learner_stats.css, linked once per page by
    # inject_menu_files(). Only the per-widget dynamic_css below is inlined.
    css_html = ""

    script_html = """
    <script>
    (function() {
        if (window.OnigiriLearnerStatsDialog) return;

        function escapeAttr(value) {
            return String(value || '').replace(/["\\\\]/g, '\\\\$&');
        }

        function activeWidget(widgetId) {
            return document.querySelector('.learner-stats-widget[data-widget-id="' + escapeAttr(widgetId) + '"]');
        }

        function _i18n(key) {
            const table = window.OnigiriLearnerStatsI18n || {};
            return table[key] || '';
        }

        window.OnigiriLearnerStatsDialog = {
            state: null,
            open(trigger) {
                const widget = trigger && trigger.closest ? trigger.closest('.learner-stats-widget') : null;
                if (!widget) return;
                const template = widget.querySelector('.learner-stats-deck-template');
                if (!template) return;
                const payload = JSON.parse(widget.dataset.pickerPayload || '{}');
                const selectedDid = widget.dataset.selectedDid || 'all';
                this.close();

                const backdrop = document.createElement('div');
                backdrop.className = 'learner-stats-modal-backdrop';
                backdrop.innerHTML = `
                    <div class="learner-stats-modal" role="dialog" aria-modal="true">
                        <div class="learner-stats-modal-header">
                            ${payload.titleIcon ? `<span class="learner-stats-modal-header-icon" style="-webkit-mask-image: url('${payload.titleIcon}'); mask-image: url('${payload.titleIcon}');"></span>` : ''}
                            <div class="learner-stats-modal-title-wrap">
                                <h3>${payload.title || _i18n('all_decks')}</h3>
                                ${payload.subtitle ? `<div class="learner-stats-modal-subtitle">${payload.subtitle}</div>` : ''}
                            </div>
                            <button class="learner-stats-modal-close" type="button" aria-label="${payload.close || _i18n('close')}">&times;</button>
                        </div>
                        <div class="learner-stats-modal-search-wrap">
                            ${payload.searchIcon ? `<span class="learner-stats-modal-search-icon" style="-webkit-mask-image: url('${payload.searchIcon}'); mask-image: url('${payload.searchIcon}');"></span>` : ''}
                            <input class="learner-stats-modal-search" type="text" autocomplete="off" spellcheck="false" placeholder="${payload.search || ''}">
                        </div>
                        <div class="learner-stats-modal-body"></div>
                        <div class="learner-stats-modal-footer">
                            <button class="learner-stats-modal-btn secondary" type="button" data-action="cancel">${payload.cancel || _i18n('cancel')}</button>
                            <button class="learner-stats-modal-btn primary" type="button" data-action="save">${payload.save || _i18n('save')}</button>
                        </div>
                        <div class="learner-stats-modal-preparing">
                            <span class="learner-stats-modal-spinner"></span>
                            <span>${payload.preparing || _i18n('preparing')}</span>
                        </div>
                    </div>
                `;
                document.body.appendChild(backdrop);

                const body = backdrop.querySelector('.learner-stats-modal-body');
                body.innerHTML = template.innerHTML;
                const list = body.querySelector('.learner-stats-picker-list');
                const markSelected = (did) => {
                    body.querySelectorAll('.learner-stats-picker-row').forEach(row => {
                        row.classList.toggle('learner-stats-picker-selected', String(row.dataset.did) === String(did));
                    });
                };
                markSelected(selectedDid);

                // Flat list + text filter, same interaction as the Create New
                // Deck dialog. Matching runs off the prerendered `data-search`
                // attribute (leaf name + full path, lowercased) so filtering
                // never touches layout-reading APIs.
                const searchInput = backdrop.querySelector('.learner-stats-modal-search');
                const emptyState = body.querySelector('.learner-stats-picker-empty');
                const rows = Array.from(body.querySelectorAll('.learner-stats-picker-row'));
                const applyFilter = () => {
                    const query = (searchInput ? searchInput.value : '').trim().toLowerCase();
                    let visible = 0;
                    rows.forEach(row => {
                        const hit = !query || (row.dataset.search || '').indexOf(query) !== -1;
                        row.classList.toggle('is-hidden', !hit);
                        if (hit) visible += 1;
                    });
                    if (emptyState) emptyState.style.display = visible ? 'none' : 'flex';
                };
                applyFilter();
                if (searchInput) searchInput.addEventListener('input', applyFilter);

                this.state = {
                    backdrop,
                    widgetId: widget.dataset.widgetId,
                    selectedDid,
                    pendingDid: selectedDid,
                    preparing: false,
                };

                backdrop.addEventListener('click', (event) => {
                    if (event.target === backdrop && !this.state.preparing) this.close();
                });
                backdrop.querySelector('.learner-stats-modal-close').addEventListener('click', () => {
                    if (!this.state.preparing) this.close();
                });
                backdrop.querySelector('[data-action="cancel"]').addEventListener('click', () => {
                    if (!this.state.preparing) this.close();
                });
                backdrop.querySelector('[data-action="save"]').addEventListener('click', () => this.save());
                list.addEventListener('click', (event) => {
                    if (!this.state || this.state.preparing) return;
                    const row = event.target.closest('.learner-stats-picker-row[data-did]');
                    if (!row) return;
                    event.preventDefault();
                    event.stopPropagation();
                    this.state.pendingDid = row.dataset.did || 'all';
                    markSelected(this.state.pendingDid);
                }, true);
            },
            save() {
                if (!this.state || this.state.preparing) return;
                this.state.preparing = true;
                const modal = this.state.backdrop.querySelector('.learner-stats-modal');
                if (modal) modal.classList.add('is-preparing');
                const payload = encodeURIComponent(JSON.stringify({
                    widgetId: this.state.widgetId,
                    deckId: this.state.pendingDid || 'all'
                }));
                if (typeof pycmd === 'function') {
                    pycmd('onigiri_learner_stats_select_deck:' + payload);
                }
            },
            finish(widgetId, html) {
                const current = activeWidget(widgetId);
                if (current) current.outerHTML = html;
                setTimeout(() => this.close(), 180);
            },
            close() {
                if (this.state && this.state.backdrop) {
                    this.state.backdrop.remove();
                }
                this.state = null;
            }
        };

        window.OnigiriLearnerStats = window.OnigiriLearnerStats || {
            setView(trigger, view) {
                const widget = trigger && trigger.closest ? trigger.closest('.learner-stats-widget') : null;
                if (!widget || widget.getAttribute('data-active-view') === view) return;
                widget.setAttribute('data-active-view', view);
                const widgetId = widget.dataset.widgetId;
                if (typeof pycmd === 'function' && widgetId) {
                    pycmd('onigiri_learner_stats_select_view:' + encodeURIComponent(JSON.stringify({ widgetId, view })));
                }
            }
        };
    })();
    </script>
    """

    # Backstop for the deck-picker modal's labels. The per-widget payload is the
    # primary source; this global exists so the JS never has to fall back to a
    # hardcoded English literal.
    i18n_script = (
        "<script>window.OnigiriLearnerStatsI18n = "
        + json.dumps({
            "all_decks": labels["all_decks"],
            "save": labels["save"],
            "cancel": labels["cancel"],
            "close": labels["close"],
            "preparing": labels["preparing"],
        })
        + ";</script>"
    )

    # The picker is a flat searchable list now, so the collapse chevrons (and
    # the two data-URI masks that drew them) are gone; only the i18n backstop
    # still has to be inlined per widget.
    dynamic_css = i18n_script

    # Generate widget content
    icon_grouped = '<svg width="15" height="15" viewBox="0 0 24 24"><path d="M0 0h24v24H0z" fill="none"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 5h16M4 12h16M4 19h16"/></svg>'
    icon_bars = '<svg width="15" height="15" viewBox="0 0 24 24"><path d="M0 0h24v24H0z" fill="none"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 5h12M4 12h16M4 19h8" transform="rotate(-90 12 12)"/></svg>'
    icon_donut = '<svg width="15" height="15" viewBox="0 0 24 24"><path d="M0 0h24v24H0z" fill="none"/><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="1.8"/></svg>'
    icon_chevron = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>'

    def _tone_style(tone: str, extra: str = "") -> str:
        """Inline `--stat-tone` for one category, plus optional extra CSS.

        The category colors are page-level variables emitted by the Deck Stats
        settings section (see patcher._deck_stats_rules); handing each element
        its own tone keeps the stylesheet down to one rule per element kind.
        """
        entry = _TONE_COLOR_VARS.get(tone)
        declarations = []
        if entry:
            var_name, fallback = entry
            declarations.append(f"--stat-tone: var({var_name}, {fallback});")
        if extra:
            declarations.append(extra)
        if not declarations:
            return ""
        return ' style="' + html.escape(" ".join(declarations), quote=True) + '"'

    def _tile(label: str, value: int, tone: str, flat: bool = False, wide: bool = False) -> str:
        classes = "learner-stat-card"
        tone_style = _tone_style(tone)
        if tone_style:
            classes += " is-toned"
        if flat:
            classes += " is-flat"
        if wide:
            # Spans both columns so the odd tile out doesn't break the
            # semantic pairing of the rows below it.
            classes += " is-wide"
        return (
            f'<div class="{classes}"{tone_style}>'
            f'<span class="learner-stat-label">{html.escape(label)}</span>'
            f'<span class="learner-stat-val">{value}</span>'
            f'</div>'
        )

    def _bar_row(label: str, value: int, pct: float, tone: str) -> str:
        fill_style = _tone_style(tone, extra=f"width: {pct}%;")
        return f"""
            <div class="learner-stats-bar-row">
                <span class="learner-stats-bar-label">{html.escape(label)}</span>
                <span class="learner-stats-bar-track"><span class="learner-stats-bar-fill"{fill_style}></span></span>
                <span class="learner-stats-bar-value">{value}</span>
            </div>"""

    # Shared progress bar: two tones in minimal mode, one segment per category
    # in full mode. Both variants are consumed by the Grouped view and by the
    # compact 1-row body.
    if is_full_chart:
        groupbar_segments = "".join(
            f'<div class="learner-stats-groupbar-seg learner-stats-groupbar-cat"'
            f'{_tone_style(tone, extra=f"width: {_pct_of(count)}%;")}></div>'
            for _label_text, count, tone in full_categories
        )
    else:
        groupbar_segments = (
            f'<div class="learner-stats-groupbar-seg learner-stats-groupbar-inprogress" style="width: {in_progress_pct}%;"></div>'
            f'<div class="learner-stats-groupbar-seg learner-stats-groupbar-mastered" style="width: {mastered_pct}%;"></div>'
        )
    groupbar_html = f'<div class="learner-stats-groupbar">{groupbar_segments}</div>'

    # Donut ring + legend, same split. Full mode walks the categories and
    # advances the dash offset so the arcs sit end to end around the ring.
    if is_full_chart:
        arcs = []
        legend_items = []
        consumed = 0.0
        for label_text, count, tone in full_categories:
            arc = round(ring_circumference * _pct_of(count) / 100, 2)
            arcs.append(
                f'<circle class="learner-stats-donut-arc-cat" cx="18" cy="18" r="15.5" fill="none"'
                f' stroke-width="4" stroke-dasharray="{arc} {ring_circumference}"'
                f' stroke-dashoffset="{round(-consumed, 2)}" stroke-linecap="butt"{_tone_style(tone)}></circle>'
            )
            consumed += arc
            legend_items.append(
                f'<span class="learner-stats-donut-legend-item">'
                f'<span class="learner-stats-donut-legend-dot is-cat"{_tone_style(tone)}></span>'
                f'{html.escape(label_text)}</span>'
            )
        donut_arcs_html = "".join(arcs)
        donut_legend_html = "".join(legend_items)
    else:
        donut_arcs_html = (
            f'<circle class="learner-stats-donut-arc-inprogress" cx="18" cy="18" r="15.5" fill="none" stroke-width="4" stroke-dasharray="{in_progress_arc} {ring_circumference}" stroke-dashoffset="0" stroke-linecap="round"></circle>'
            f'<circle class="learner-stats-donut-arc-mastered" cx="18" cy="18" r="15.5" fill="none" stroke-width="4" stroke-dasharray="{mastered_arc} {ring_circumference}" stroke-dashoffset="{mastered_offset}" stroke-linecap="round"></circle>'
        )
        donut_legend_html = (
            f'<span class="learner-stats-donut-legend-item"><span class="learner-stats-donut-legend-dot is-inprogress"></span>{labels["group_in_progress"]}</span>'
            f'<span class="learner-stats-donut-legend-item"><span class="learner-stats-donut-legend-dot is-mastered"></span>{labels["group_mastered"]}</span>'
        )

    footer_row_html = f"""
            <div class="learner-stats-footer-row">
                <span class="learner-stats-footer-item">{labels["buried"]} <b>{buried_cnt}</b></span>
                <span class="learner-stats-footer-item">{labels["suspended"]} <b>{suspended_cnt}</b></span>
                <span class="learner-stats-footer-item is-total">{labels["total"]} <b>{total_cnt}</b></span>
            </div>"""

    # Donut puts Buried/Suspended in its own tile grid, so its footer carries
    # the two counts that have nowhere else to go: Unseen and the total.
    donut_footer_html = f"""
            <div class="learner-stats-footer-row">
                <span class="learner-stats-footer-item">{labels["unseen"]} <b>{unseen_cnt}</b></span>
                <span class="learner-stats-footer-item is-total">{labels["total"]} <b>{total_cnt}</b></span>
            </div>"""

    if is_full_chart:
        # No In Progress / Mastered split: every category is one untitled grid,
        # so the tiles read as a single flat breakdown of the deck.
        grouped_groups_html = f"""
                <div class="learner-stats-group">
                    <div class="learner-stats-tile-grid learner-stats-tile-grid-3">
                        {_tile(labels["new"], new_cnt, "new")}
                        {_tile(labels["learning"], learn_cnt, "learning")}
                        {_tile(labels["relearning"], relearn_cnt, "relearning")}
                        {_tile(labels["young"], young_cnt, "young")}
                        {_tile(labels["mature"], mature_cnt, "mature")}
                        {_tile(labels["unseen"], unseen_cnt, "unseen")}
                        {_tile(labels["buried"], buried_cnt, "buried")}
                        {_tile(labels["suspended"], suspended_cnt, "suspended")}
                        {_tile(labels["total"], total_cnt, "total")}
                    </div>
                </div>"""
    else:
        grouped_groups_html = f"""
                <div class="learner-stats-group">
                    <div class="learner-stats-group-title is-toned"{_tone_style("in_progress")}>{labels["group_in_progress"]}</div>
                    <div class="learner-stats-tile-grid learner-stats-tile-grid-3">
                        {_tile(labels["new"], new_cnt, "new")}
                        {_tile(labels["learning"], learn_cnt, "learning")}
                        {_tile(labels["relearning"], relearn_cnt, "relearning")}
                    </div>
                </div>
                <div class="learner-stats-group">
                    <div class="learner-stats-group-title is-toned"{_tone_style("mastered")}>{labels["group_mastered"]}</div>
                    <div class="learner-stats-tile-grid learner-stats-tile-grid-2">
                        {_tile(labels["young"], young_cnt, "young")}
                        {_tile(labels["mature"], mature_cnt, "mature")}
                    </div>
                </div>
                <div class="learner-stats-group">
                    <div class="learner-stats-group-title is-neutral">{labels["group_others"]}</div>
                    <div class="learner-stats-tile-grid learner-stats-tile-grid-4">
                        {_tile(labels["unseen"], unseen_cnt, "unseen")}
                        {_tile(labels["buried"], buried_cnt, "buried")}
                        {_tile(labels["suspended"], suspended_cnt, "suspended")}
                        {_tile(labels["total"], total_cnt, "total")}
                    </div>
                </div>"""

    grouped_view_html = f"""
        <div class="learner-stats-view learner-stats-view-grouped" data-view="grouped">
            {groupbar_html}
            <div class="learner-stats-grouped-groups">{grouped_groups_html}
            </div>
        </div>"""

    bar_spacer = '<div class="learner-stats-bar-spacer"></div>'
    bar_rows = [
        (labels["new"], new_cnt, new_bar_pct, "new"),
        (labels["learning"], learn_cnt, learn_bar_pct, "learning"),
        (labels["relearning"], relearn_cnt, relearn_bar_pct, "relearning"),
        (labels["young"], young_cnt, young_bar_pct, "young"),
        (labels["mature"], mature_cnt, mature_bar_pct, "mature"),
        (labels["unseen"], unseen_cnt, unseen_bar_pct, "unseen"),
    ]
    bar_list_html = bar_spacer.join(_bar_row(*row) for row in bar_rows)
    bars_view_html = f"""
        <div class="learner-stats-view learner-stats-view-bars" data-view="bars">
            <div class="learner-stats-bar-list">
                {bar_spacer}{bar_list_html}
            </div>
            {footer_row_html}
        </div>"""

    donut_view_html = f"""
        <div class="learner-stats-view learner-stats-view-donut" data-view="donut">
            <div class="learner-stats-donut-content">
                <div class="learner-stats-donut-top">
                    <svg width="52" height="52" viewBox="0 0 36 36" class="learner-stats-donut-ring">
                        <circle class="learner-stats-donut-track" cx="18" cy="18" r="15.5" fill="none" stroke-width="4"></circle>
                        {donut_arcs_html}
                    </svg>
                    <div class="learner-stats-donut-total">
                        <div class="learner-stats-donut-num">{total_cnt} <span>{labels["total_short"]}</span></div>
                        <div class="learner-stats-donut-legend">{donut_legend_html}</div>
                    </div>
                </div>
                <div class="learner-stats-tile-grid learner-stats-tile-grid-2">
                    {_tile(labels["new"], new_cnt, "new", flat=True, wide=True)}
                    {_tile(labels["learning"], learn_cnt, "learning", flat=True)}
                    {_tile(labels["relearning"], relearn_cnt, "relearning", flat=True)}
                    {_tile(labels["young"], young_cnt, "young", flat=True)}
                    {_tile(labels["mature"], mature_cnt, "mature", flat=True)}
                    {_tile(labels["buried"], buried_cnt, "buried", flat=True)}
                    {_tile(labels["suspended"], suspended_cnt, "suspended", flat=True)}
                </div>
            </div>
            {donut_footer_html}
        </div>"""

    switcher_html = "" if is_compact else f"""
                    <div class="learner-stats-switcher" role="tablist" aria-label="{labels["view_switcher"]}">
                        <div class="learner-stats-switcher-indicator"></div>
                        <button type="button" class="learner-stats-switcher-btn" data-view="grouped" aria-label="{labels["view_grouped"]}" title="{labels["view_grouped"]}" onclick="window.OnigiriLearnerStats && window.OnigiriLearnerStats.setView(this,'grouped');">{icon_grouped}</button>
                        <button type="button" class="learner-stats-switcher-btn" data-view="bars" aria-label="{labels["view_bars"]}" title="{labels["view_bars"]}" onclick="window.OnigiriLearnerStats && window.OnigiriLearnerStats.setView(this,'bars');">{icon_bars}</button>
                        <button type="button" class="learner-stats-switcher-btn" data-view="donut" aria-label="{labels["view_donut"]}" title="{labels["view_donut"]}" onclick="window.OnigiriLearnerStats && window.OnigiriLearnerStats.setView(this,'donut');">{icon_donut}</button>
                    </div>"""

    # Below ~1 grid row there's no room for any of the three detailed views
    # (each needs 150px+ of body height); fall back to a single glance line.
    compact_body_html = f"""
        <div class="learner-stats-compact-body">
            {groupbar_html}
            <div class="learner-stats-compact-total">{total_cnt} <span>{labels["total_short"]}</span></div>
        </div>"""

    body_html = compact_body_html if is_compact else f"""
            {grouped_view_html}
            {bars_view_html}
            {donut_view_html}"""

    html_widget = f"""
    <div class="learner-stats-widget" data-widget-id="{escaped_widget_id}" data-selected-did="{html.escape(str(selected_did), quote=True)}" data-picker-payload="{picker_payload}" data-active-view="{active_view}" data-chart-type="{"full" if is_full_chart else "minimal"}">
        <div class="learner-stats-header">
            <div class="learner-stats-header-row onigiri-widget-head">
                <h3>{labels["title"]}</h3>
                <div class="learner-stats-header-controls">
                    {switcher_html}
                    <div class="learner-stats-deck-trigger" role="button" tabindex="0" onclick="window.OnigiriLearnerStatsDialog && window.OnigiriLearnerStatsDialog.open(this);"><span class="learner-stats-deck-trigger-label">{html.escape(deck_label)}</span><span class="learner-stats-deck-trigger-chevron">{icon_chevron}</span></div>
                </div>
            </div>
        </div>
        <div class="learner-stats-body">
            {body_html}
        </div>
        <template class="learner-stats-deck-template">
            {picker_html}
        </template>
    </div>
    {script_html}
    """

    html_content = f"""
    {css_html}
    {dynamic_css}
    {html_widget}
    """
    return html_content

def render_learner_stats_widget(deck_browser: DeckBrowser, content) -> None:
    # This is a base template hook. The layout editor uses it to detect the widget.
    # Onigiri will render instances directly via onigiri_renderer.py.
    pass

def init():
    from aqt import gui_hooks
    gui_hooks.deck_browser_will_render_content.append(render_learner_stats_widget)
