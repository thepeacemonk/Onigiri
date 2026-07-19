# Learner Stats Widget for Onigiri

import html
import json
from aqt import mw
from aqt.deckbrowser import DeckBrowser

def get_translated_labels():
    lang = "en"
    try:
        lang = mw.pm.meta.get("defaultLang", "en")
    except:
        pass
    
    if lang.startswith("vi"):
        return {
            "title": "STATS",
            "all_decks": "Tất cả deck",
            "new": "Mới (New)",
            "learning": "Đang học (Learning)",
            "mature": "Trưởng thành (Mature)",
            "young": "Trẻ (Young)",
            "learned": "Đã học (Learned)",
            "unseen": "Chưa xem (Unseen)",
            "buried": "Bị chôn (Buried)",
            "suspended": "Đình chỉ (Suspended)",
            "total": "Tổng cộng (Total)",
            "total_short": "tổng",
            "group_in_progress": "Đang tiến triển",
            "group_mastered": "Thành thạo",
            "group_not_active": "Không hoạt động",
            "view_grouped": "Nhóm",
            "view_bars": "Thanh",
            "view_donut": "Vòng tròn"
        }
    else:
        return {
            "title": "STATS",
            "all_decks": "All Decks",
            "new": "New",
            "learning": "Learning",
            "mature": "Mature",
            "young": "Young",
            "learned": "Learned",
            "unseen": "Unseen",
            "buried": "Buried",
            "suspended": "Suspended",
            "total": "Total",
            "total_short": "total",
            "group_in_progress": "In Progress",
            "group_mastered": "Mastered",
            "group_not_active": "Not Active",
            "view_grouped": "Grouped",
            "view_bars": "Bars",
            "view_donut": "Donut"
        }

def get_card_stats(selected_did, all_decks):
    new_cnt = 0
    learn_cnt = 0
    mature_cnt = 0
    young_cnt = 0
    learned_cnt = 0
    unseen_cnt = 0
    buried_cnt = 0
    suspended_cnt = 0
    total_cnt = 0

    if not mw.col:
        return (new_cnt, learn_cnt, mature_cnt, young_cnt, learned_cnt, unseen_cnt, buried_cnt, suspended_cnt, total_cnt)

    if selected_did == "all":
        rows = mw.col.db.all("""
            select 
                queue, 
                case when reps = 0 then 1 else 0 end, 
                case when ivl >= 21 then 1 else 0 end, 
                count() 
            from cards 
            group by 1, 2, 3
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
                    case when reps = 0 then 1 else 0 end, 
                    case when ivl >= 21 then 1 else 0 end, 
                    count() 
                from cards 
                where did in ({dids_str}) 
                group by 1, 2, 3
            """)

    for queue, is_unseen, is_mature, count in rows:
        total_cnt += count
        if is_unseen:
            unseen_cnt += count
        
        if queue == -1:
            suspended_cnt += count
        elif queue in (-2, -3):
            buried_cnt += count
        elif queue == 0:
            new_cnt += count
        elif queue in (1, 3):
            learn_cnt += count
        elif queue == 2:
            learned_cnt += count
            if is_mature:
                mature_cnt += count
            else:
                young_cnt += count

    return (new_cnt, learn_cnt, mature_cnt, young_cnt, learned_cnt, unseen_cnt, buried_cnt, suspended_cnt, total_cnt)

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

def _render_picker_rows(nodes, selected_did, depth=0) -> str:
    """Self-contained deck rows for the picker modal (plain divs, not the
    sidebar's table markup) so the list never depends on the main deck
    browser's current width/collapse state and can't blow out the modal."""
    rows = []
    for node in nodes:
        did = str(node.deck_id)
        leaf_name = _deck_display_name(node.name)
        has_children = bool(node.children)
        is_selected = str(selected_did) == did

        wrap_classes = "learner-stats-picker-row-wrap"
        if node.collapsed and has_children:
            wrap_classes += " is-collapsed"

        row_classes = "learner-stats-picker-row"
        if is_selected:
            row_classes += " learner-stats-picker-selected"

        if has_children:
            toggle_html = '<span class="learner-stats-picker-toggle" aria-label="Toggle" role="button"></span>'
        else:
            toggle_html = '<span class="learner-stats-picker-toggle-spacer"></span>'

        children_html = ""
        if has_children:
            children_html = f'<div class="learner-stats-picker-children">{_render_picker_rows(node.children, selected_did, depth + 1)}</div>'

        icon_data = _get_deck_icon_data(node.deck_id, node.name, has_children)
        if icon_data["type"] == "emoji":
            icon_html = f'<span class="learner-stats-picker-icon emoji-icon">{html.escape(icon_data["content"])}</span>'
        else:
            icon_html = f'<span class="learner-stats-picker-icon" style="-webkit-mask-image: url(\'{icon_data["url"]}\'); mask-image: url(\'{icon_data["url"]}\');"></span>'

        escaped_name = html.escape(leaf_name)
        rows.append(f"""
        <div class="{wrap_classes}">
            <div class="{row_classes}" data-did="{html.escape(did, quote=True)}" style="padding-left: {8 + depth * 18}px;">
                {toggle_html}
                {icon_html}
                <span class="learner-stats-picker-name">{escaped_name}</span>
            </div>
            {children_html}
        </div>
        """)
    return "".join(rows)

def _render_deck_picker_html(deck_browser: DeckBrowser, selected_did, labels) -> str:
    if getattr(deck_browser, "_render_data", None):
        tree_data = deck_browser._render_data.tree
    else:
        tree_data = mw.col.sched.deck_due_tree()

    try:
        from . import deck_tree_updater as tree_updater
        tree_updater._apply_tree_preferences(tree_data)
    except Exception:
        pass

    selected_class = " learner-stats-picker-selected" if selected_did == "all" else ""
    addon_dir = os.path.dirname(__file__)
    all_decks_icon_path = os.path.join(addon_dir, "system_files", "system_icons", "unavailable_for_users", "deck.svg")
    all_decks_icon_url = _get_data_uri(all_decks_icon_path)
    all_decks_icon = f'<span class="learner-stats-picker-icon" style="-webkit-mask-image: url(\'{all_decks_icon_url}\'); mask-image: url(\'{all_decks_icon_url}\');"></span>'

    all_decks_row = f"""
    <div class="learner-stats-picker-row-wrap">
        <div class="learner-stats-picker-row learner-stats-picker-all{selected_class}" data-did="all" style="padding-left: 8px;">
            <span class="learner-stats-picker-toggle-spacer"></span>
            {all_decks_icon}
            <span class="learner-stats-picker-name">{html.escape(labels["all_decks"])}</span>
        </div>
    </div>
    """
    tree_html = _render_picker_rows(tree_data.children, selected_did)

    return f"""
    <div class="learner-stats-picker-list">
        {all_decks_row}
        {tree_html}
    </div>
    """

def _render_widget(deck_browser: DeckBrowser, widget_id: str, row_span: int = 2) -> str:
    labels = get_translated_labels()
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
    (new_cnt, learn_cnt, mature_cnt, young_cnt, learned_cnt, unseen_cnt, buried_cnt, suspended_cnt, total_cnt) = get_card_stats(selected_did, all_decks)

    # Two-tone grouping used by the grouped bar / donut ring / bar-view fills:
    # "in progress" (new + learning + young) vs "mastered" (mature). Learned is
    # not folded in here since it's already the sum of mature+young (see
    # get_card_stats) and would double-count against the same total.
    in_progress_cnt = new_cnt + learn_cnt + young_cnt

    def _pct_of(count: int) -> float:
        if total_cnt <= 0:
            return 0.0
        return round(min(100.0, (count / total_cnt) * 100), 2)

    in_progress_pct = _pct_of(in_progress_cnt)
    mastered_pct = _pct_of(mature_cnt)

    # Donut ring geometry: r=15.5 circle, matching the stroke-dasharray scheme.
    import math
    ring_circumference = round(2 * math.pi * 15.5, 2)
    in_progress_arc = round(ring_circumference * in_progress_pct / 100, 2)
    mastered_arc = round(ring_circumference * mastered_pct / 100, 2)
    mastered_offset = -in_progress_arc

    # Per-category bar-view fill widths, each relative to the deck total.
    new_bar_pct = _pct_of(new_cnt)
    learn_bar_pct = _pct_of(learn_cnt)
    young_bar_pct = _pct_of(young_cnt)
    mature_bar_pct = _pct_of(mature_cnt)
    learned_bar_pct = _pct_of(learned_cnt)
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
        "title": labels["all_decks"],
        "save": "Save",
        "cancel": "Cancel",
        "preparing": "Preparing your Onigiri",
    }), quote=True)

    # Generate CSS
    css_html = """
    <style>
    .learner-stats-widget {
        background-color: var(--canvas-inset, #ffffff);
        border: 1px solid var(--border, #e0e0e0);
        border-radius: var(--onigiri-box-effect-radius, 15px);
        padding: 20px;
        height: 100%;
        width: 100%;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        gap: 10px;
        overflow: hidden;
        text-align: left;
    }
    .learner-stats-header {
        display: flex;
        flex-direction: column;
        align-items: stretch;
        gap: 8px;
        width: 100%;
        flex: 0 0 auto;
        box-sizing: border-box;
        overflow: hidden;
    }
    .learner-stats-header-row {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%;
        min-height: 26px;
        line-height: 0;
        overflow: hidden;
    }
    .learner-stats-header-controls {
        display: flex !important;
        align-items: center !important;
        gap: 10px !important;
        margin: 0 0 0 auto !important;
        padding: 0 !important;
        min-width: 0;
        flex: 0 1 auto !important;
    }
    .learner-stats-switcher {
        position: relative;
        display: flex;
        align-items: center;
        gap: 2px;
        flex: 0 0 auto;
        height: 26px;
        min-height: 26px;
        box-sizing: border-box;
        padding: 2px;
        border-radius: 8px;
        background-color: var(--highlight-bg, #eeeeee);
    }
    .learner-stats-switcher-indicator {
        position: absolute;
        left: 2px;
        top: 50%;
        width: 22px;
        height: 22px;
        border-radius: 6px;
        background-color: color-mix(in srgb, var(--highlight-bg, #eeeeee) 90%, var(--fg, #222222) 10%);
        transform: translateY(-50%);
        transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }
    /* Light and dark perceive the same mix ratio differently — a darker gray
       patch on a light track reads as more prominent than the equivalent
       lighter patch on a dark track — so dark mode gets a bit more tint. */
    .night-mode .learner-stats-switcher-indicator {
        background-color: color-mix(in srgb, var(--highlight-bg, #eeeeee) 85%, var(--fg, #222222) 15%);
    }
    .learner-stats-widget[data-active-view="bars"] .learner-stats-switcher-indicator {
        transform: translateY(-50%) translateX(24px);
    }
    .learner-stats-widget[data-active-view="donut"] .learner-stats-switcher-indicator {
        transform: translateY(-50%) translateX(48px);
    }
    .learner-stats-switcher-btn {
        position: relative !important;
        z-index: 1 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        vertical-align: middle !important;
        width: 22px !important;
        height: 22px !important;
        min-width: 22px !important;
        min-height: 22px !important;
        max-width: 22px !important;
        max-height: 22px !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
        border-radius: 6px !important;
        background: transparent !important;
        color: var(--fg-subtle, #757575) !important;
        cursor: pointer !important;
        transition: color 0.2s ease !important;
        flex: 0 0 22px !important;
        box-sizing: border-box !important;
        font-size: 0 !important;
        line-height: 0 !important;
        overflow: visible !important;
        -webkit-tap-highlight-color: transparent;
    }
    .learner-stats-switcher-btn,
    .learner-stats-switcher-btn:hover,
    .learner-stats-switcher-btn:focus,
    .learner-stats-switcher-btn:focus-visible,
    .learner-stats-switcher-btn:active {
        outline: none !important;
        box-shadow: none !important;
        background: transparent !important;
        border: none !important;
        -webkit-appearance: none !important;
        appearance: none !important;
    }
    .learner-stats-switcher-btn svg {
        display: block !important;
        pointer-events: none;
        overflow: visible;
        width: 15px !important;
        height: 15px !important;
        margin: 0 !important;
        padding: 0 !important;
        flex: 0 0 auto !important;
    }
    .learner-stats-widget[data-active-view="grouped"] .learner-stats-switcher-btn[data-view="grouped"],
    .learner-stats-widget[data-active-view="bars"] .learner-stats-switcher-btn[data-view="bars"],
    .learner-stats-widget[data-active-view="donut"] .learner-stats-switcher-btn[data-view="donut"] {
        color: var(--fg, #222222) !important;
    }
    .learner-stats-header h3 {
        margin: 0;
        flex: 0 0 auto;
        min-width: 0;
        font-size: 11px;
        text-transform: uppercase;
        color: var(--fg-subtle, #757575);
        font-weight: 800;
        letter-spacing: 0.08em;
        white-space: nowrap;
        display: inline-flex;
        align-items: center;
        min-height: 20px;
        line-height: 20px;
    }
    .learner-stats-widget .learner-stats-deck-trigger.learner-stats-deck-trigger {
        font-family: inherit;
        font-size: 12px;
        font-weight: 600;
        line-height: 1;
        margin: 0 !important;
        gap: 6px;
        background: var(--highlight-bg, #eeeeee) !important;
        background-image: none !important;
        color: var(--fg, #222222) !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0 18px !important;
        height: 26px !important;
        min-height: 26px !important;
        width: auto !important;
        max-width: 320px !important;
        min-width: 0 !important;
        box-sizing: border-box !important;
        outline: none !important;
        cursor: pointer;
        transition: transform 0.08s ease, background-color 0.15s ease, color 0.15s ease;
        text-align: left;
        box-shadow: none !important;
        text-shadow: none !important;
        filter: none !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: flex-start !important;
        flex: 0 1 auto !important;
        flex-shrink: 1 !important;
        position: relative !important;
        top: 0 !important;
        vertical-align: middle;
        float: none !important;
        right: auto !important;
        inset-inline-end: auto !important;
    }
    .learner-stats-deck-trigger-label {
        display: block;
        min-width: 0;
        max-width: 100%;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
    }
    .learner-stats-deck-trigger-chevron {
        flex: 0 0 auto;
        display: block;
        color: var(--fg-subtle, #757575);
    }
    .learner-stats-widget .learner-stats-deck-trigger.learner-stats-deck-trigger:hover,
    .learner-stats-widget .learner-stats-deck-trigger.learner-stats-deck-trigger:focus,
    .learner-stats-widget .learner-stats-deck-trigger.learner-stats-deck-trigger:focus-visible,
    .learner-stats-widget .learner-stats-deck-trigger.learner-stats-deck-trigger:active {
        background: var(--collapsed-toolbar-button-hover-bg, var(--button-hover-bg, var(--hover-deck-bg))) !important;
        background-image: none !important;
        color: var(--fg, #222222) !important;
        filter: none !important;
        outline: none !important;
        border: none !important;
        box-shadow: none !important;
        margin: 0 !important;
    }
    .learner-stats-widget .learner-stats-deck-trigger.learner-stats-deck-trigger:active {
        transform: translateY(1px);
    }
    /* ---- Shared: category → tint mapping (in-progress / mastered / neutral) ---- */
    .learner-stat-card {
        border: none;
        border-radius: 10px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 3px 2px;
        box-sizing: border-box;
        min-width: 0;
        background: color-mix(in srgb, var(--fg, #222) 3%, transparent);
    }
    .learner-stat-card.is-inprogress {
        background: color-mix(in srgb, #007aff 12%, transparent);
    }
    .learner-stat-card.is-mastered {
        background: color-mix(in srgb, #2ecc71 12%, transparent);
    }
    .learner-stat-label {
        font-size: 9px;
        font-weight: 500;
        color: var(--fg-subtle, #757575);
        text-align: center;
        margin-bottom: 1px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        width: 100%;
        letter-spacing: 0;
    }
    /* Kept close to --fg-subtle (which is already tuned for legible contrast
       on the card background in every theme) with just a light color hint —
       a 55/45 mix here read fine in the mockup's fixed dark palette but
       dropped well below WCAG AA against the tinted tile background once
       real theme colors (light mode especially) were plugged in. */
    .is-inprogress .learner-stat-label {
        color: color-mix(in srgb, #007aff 18%, var(--fg-subtle, #757575) 82%);
    }
    .is-mastered .learner-stat-label {
        color: color-mix(in srgb, #2ecc71 10%, var(--fg-subtle, #757575) 90%);
    }
    .learner-stat-val {
        font-size: 14px;
        font-weight: 700;
        color: var(--fg, #222222);
        line-height: 1.1;
    }
    .learner-stat-total .learner-stat-val { font-size: 13px; }

    /* ---- View switching: one card, three swappable bodies ---- */
    .learner-stats-body {
        display: flex;
        flex-direction: column;
        flex: 1 1 auto;
        min-height: 0;
        overflow: hidden;
    }
    .learner-stats-view {
        display: none;
        flex-direction: column;
        gap: 22px;
        min-height: 0;
        flex: 1 1 auto;
        width: 100%;
    }
    .learner-stats-widget[data-active-view="grouped"] .learner-stats-view-grouped,
    .learner-stats-widget[data-active-view="bars"] .learner-stats-view-bars,
    .learner-stats-widget[data-active-view="donut"] .learner-stats-view-donut {
        display: flex;
    }
    /* Every view anchors its "header" element (progress bar / donut ring /
       first bar row) to the top and never centers-as-a-block — that way if a
       very short card ever can't fit everything, only the bottom clips,
       never the top. The region below the header element is flex:1 and
       grows to consume all leftover height itself (see each view's own
       flexible region below), which is what pushes footers to the bottom. */
    .learner-stats-view-grouped,
    .learner-stats-view-bars,
    .learner-stats-view-donut { justify-content: flex-start; }
    .learner-stats-view-grouped { gap: 10px; }
    .learner-stats-view-bars { gap: 16px; }

    /* Donut's top block and tile grid keep the view's normal rhythm; the
       footer gets its own tighter, explicit gap so it doesn't inherit
       whatever the view-level gap happens to be. */
    .learner-stats-donut-content {
        display: flex;
        flex-direction: column;
        gap: 22px;
        flex: 1 1 auto;
        min-height: 0;
    }
    .learner-stats-view-donut { gap: 8px; }

    /* Groups collectively fill all height left after the progress bar,
       each claiming an equal share — the same "1fr" idea the tile columns
       already use, just on the row axis. */
    .learner-stats-grouped-groups {
        display: flex;
        flex-direction: column;
        gap: 4px;
        flex: 1 1 auto;
        min-height: 0;
    }

    /* ---- Grouped view: two-tone progress bar + three meaning-based groups ---- */
    .learner-stats-groupbar {
        display: flex;
        width: 100%;
        height: 6px;
        border-radius: 999px;
        overflow: hidden;
        background: color-mix(in srgb, var(--fg, #222) 8%, transparent);
        flex: 0 0 auto;
        box-sizing: border-box;
    }
    .learner-stats-groupbar-seg {
        height: 100%;
        transition: width 0.3s ease;
    }
    .learner-stats-groupbar-inprogress { background: #007aff; }
    .learner-stats-groupbar-mastered { background: #2ecc71; }

    /* ---- Compact body: 1-row cards can't fit any of the three detailed
       views, so this replaces them entirely with a bar + total glance. ---- */
    .learner-stats-compact-body {
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 6px;
        flex: 1 1 auto;
        min-height: 0;
    }
    .learner-stats-compact-total {
        font-size: 14px;
        font-weight: 700;
        color: var(--fg, #222222);
        text-align: center;
        white-space: nowrap;
    }
    .learner-stats-compact-total span {
        font-size: 11px;
        font-weight: 500;
        color: var(--fg-subtle, #757575);
        margin-left: 4px;
    }
    .learner-stats-group {
        display: flex;
        flex-direction: column;
        gap: 3px;
        min-width: 0;
        flex: 1 1 0;
        min-height: 0;
    }
    .learner-stats-group-title {
        font-size: 9px;
        font-weight: 600;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    /* Same reasoning as the tile-label mix above: pure accent-color / pure
       #2ecc71 as small text reads fine on the mockup's fixed dark palette
       but fails WCAG contrast against real light-theme backgrounds. */
    .learner-stats-group-title.is-inprogress { color: color-mix(in srgb, #007aff 22%, var(--fg-subtle, #757575) 78%); }
    .learner-stats-group-title.is-mastered { color: color-mix(in srgb, #2ecc71 12%, var(--fg-subtle, #757575) 88%); }
    .learner-stats-group-title.is-neutral { color: var(--fg-subtle, #757575); }
    .learner-stats-tile-grid {
        display: grid;
        grid-auto-rows: 1fr;
        gap: 6px;
        min-width: 0;
        flex: 1 1 auto;
        min-height: 0;
    }
    .learner-stats-tile-grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .learner-stats-tile-grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .learner-stats-tile-grid-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }

    /* ---- Bars view: labeled horizontal bars + footer totals ----
       The list fills all leftover height itself; a fixed-ratio spacer
       sits before the first row and between every row after it (so the
       top gap matches the inter-row gaps) and soaks up the growth. Rows
       and the track stay a fixed height — same 7px track used by every
       other widget's bars in this app — capped so the gaps never get
       out of hand on a very tall card. */
    .learner-stats-bar-list {
        display: flex;
        flex-direction: column;
        min-width: 0;
        flex: 1 1 auto;
        min-height: 0;
    }
    .learner-stats-bar-spacer {
        flex: 1 1 0;
        min-height: 2px;
        max-height: 13px;
    }
    .learner-stats-bar-row {
        display: grid;
        grid-template-columns: minmax(28px, 0.6fr) minmax(0, 2.2fr) minmax(20px, auto);
        align-items: center;
        gap: 8px;
        min-width: 0;
        flex: 0 0 auto;
    }
    .learner-stats-bar-label {
        font-size: 11px;
        font-weight: 500;
        color: var(--fg-subtle, #757575);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
    }
    .learner-stats-bar-track {
        display: block;
        height: 7px;
        border-radius: 4px;
        background: color-mix(in srgb, var(--fg, #222) 10%, transparent);
        overflow: hidden;
        min-width: 0;
    }
    .learner-stats-bar-fill {
        display: block;
        height: 100%;
        border-radius: 4px;
        transition: width 0.3s ease;
    }
    .learner-stats-bar-fill.is-inprogress { background: #007aff; }
    .learner-stats-bar-fill.is-mastered { background: #2ecc71; }
    .learner-stats-bar-fill.is-neutral { background: color-mix(in srgb, var(--fg, #222) 35%, transparent); }
    .learner-stats-bar-value {
        font-size: 12px;
        font-weight: 700;
        color: var(--fg, #222222);
        text-align: right;
        white-space: nowrap;
    }
    .learner-stats-footer-row {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        margin-top: 0;
        padding-top: 6px;
        border-top: 1px solid var(--border, #e0e0e0);
        flex: 0 0 auto;
        min-width: 0;
    }
    .learner-stats-footer-item {
        font-size: 11px;
        font-weight: 500;
        color: var(--fg-subtle, #757575);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
    }
    .learner-stats-footer-item b {
        color: var(--fg, #222222);
        font-weight: 700;
    }
    .learner-stats-footer-item.is-total { font-weight: 600; }

    /* ---- Donut view: ring + legend + flat tile list ---- */
    .learner-stats-donut-top {
        display: flex;
        align-items: center;
        gap: 12px;
        min-width: 0;
    }
    .learner-stats-donut-ring {
        flex: 0 0 auto;
        transform: rotate(-90deg);
        width: 38px;
        height: 38px;
    }
    .learner-stats-donut-track { stroke: color-mix(in srgb, var(--fg, #222) 10%, transparent); }
    .learner-stats-donut-arc-inprogress { stroke: #007aff; }
    .learner-stats-donut-arc-mastered { stroke: #2ecc71; }
    .learner-stats-donut-total {
        min-width: 0;
    }
    .learner-stats-donut-num {
        font-size: 28px;
        font-weight: 700;
        line-height: 1.1;
        color: var(--fg, #222222);
        white-space: nowrap;
    }
    .learner-stats-donut-num span {
        font-size: 11px;
        font-weight: 500;
        color: var(--fg-subtle, #757575);
    }
    .learner-stats-donut-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 3px;
    }
    .learner-stats-donut-legend-item {
        display: flex;
        align-items: center;
        gap: 5px;
        font-size: 11px;
        font-weight: 500;
        color: var(--fg-subtle, #757575);
        white-space: nowrap;
    }
    .learner-stats-donut-legend-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        flex: 0 0 auto;
    }
    .learner-stats-donut-legend-dot.is-inprogress { background: #007aff; }
    .learner-stats-donut-legend-dot.is-mastered { background: #2ecc71; }
    .learner-stat-card.is-flat {
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        padding: 8px 16px;
        gap: 6px;
    }
    .learner-stat-card.is-flat .learner-stat-label {
        margin-bottom: 0;
        text-align: left;
        width: auto;
        flex: 1 1 auto;
        font-size: 11px;
    }
    .learner-stat-card.is-flat .learner-stat-val {
        font-size: 12px;
        flex: 0 0 auto;
    }

    .learner-stats-deck-template {
        display: none;
    }
    .learner-stats-modal-backdrop {
        position: fixed;
        inset: 0;
        z-index: 100000;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
        box-sizing: border-box;
        background: rgba(20, 20, 25, 0.26);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
    }
    .learner-stats-modal {
        width: min(620px, calc(100vw - 48px));
        max-height: min(720px, calc(100vh - 48px));
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 18px;
        box-sizing: border-box;
        color: var(--fg, #222222);
        background: color-mix(in srgb, var(--canvas, #ffffff) 92%, transparent);
        border: 1px solid var(--border, #e0e0e0);
        border-radius: 22px;
        box-shadow: 0 24px 70px rgba(0, 0, 0, 0.28);
        overflow: hidden;
        transition: width 0.22s ease, max-height 0.22s ease, padding 0.22s ease, transform 0.22s ease;
    }
    .learner-stats-modal.is-preparing {
        width: min(330px, calc(100vw - 48px));
        max-height: 170px;
        padding: 22px;
        align-items: center;
        justify-content: center;
        transform: scale(0.96);
    }
    .learner-stats-modal-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        flex: 0 0 auto;
    }
    .learner-stats-modal-header h3 {
        margin: 0;
        color: var(--fg-subtle, #757575);
        font-size: 16px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-family: var(--font-main, inherit);
    }
    .learner-stats-modal-close {
        margin: 0;
        width: 30px;
        height: 30px;
        border: 1px solid var(--border, #e0e0e0);
        border-radius: 8px;
        background: var(--highlight-bg, #eeeeee);
        color: var(--fg-subtle, #757575);
        cursor: pointer;
        font-size: 18px;
        line-height: 1;
    }
    .learner-stats-modal-body {
        min-height: 0;
        overflow: auto;
        border: 1px solid var(--border, #e0e0e0);
        border-radius: 14px;
        background: color-mix(in srgb, var(--canvas-inset, #ffffff) 92%, transparent);
    }
    .learner-stats-modal-footer {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 8px;
        flex: 0 0 auto;
    }
    .learner-stats-modal-btn {
        margin: 0;
        min-width: 88px;
        height: 34px;
        border: 1px solid var(--border, #e0e0e0);
        border-radius: 9px;
        background: var(--highlight-bg, #eeeeee);
        color: var(--fg, #222222);
        cursor: pointer;
        font-size: 12px;
        font-weight: 600;
    }
    .learner-stats-modal-btn.primary {
        background: var(--accent-color, #007aff);
        border-color: var(--accent-color, #007aff);
        color: #ffffff;
    }
    .learner-stats-modal-preparing {
        display: none;
        align-items: center;
        justify-content: center;
        gap: 10px;
        width: 100%;
        min-height: 84px;
        color: var(--fg, #222222);
        font-size: 15px;
        font-weight: 700;
        text-align: center;
    }
    .learner-stats-modal-spinner {
        width: 18px;
        height: 18px;
        border: 2px solid color-mix(in srgb, var(--fg, #222222) 16%, transparent);
        border-top-color: var(--accent-color, #007aff);
        border-radius: 50%;
        animation: learner-stats-spin 0.8s linear infinite;
        flex: 0 0 auto;
    }
    .learner-stats-modal.is-preparing .learner-stats-modal-header,
    .learner-stats-modal.is-preparing .learner-stats-modal-body,
    .learner-stats-modal.is-preparing .learner-stats-modal-footer {
        display: none;
    }
    .learner-stats-modal.is-preparing .learner-stats-modal-preparing {
        display: flex;
    }
    .learner-stats-picker-list {
        display: flex;
        flex-direction: column;
        gap: 2px;
        padding: 6px;
        box-sizing: border-box;
        min-width: 0;
    }
    .learner-stats-picker-row-wrap {
        display: flex;
        flex-direction: column;
        min-width: 0;
    }
    .learner-stats-picker-row {
        display: flex;
        align-items: center;
        gap: 6px;
        min-width: 0;
        padding: 8px 10px 8px 4px;
        border-radius: 8px;
        border: 1px solid transparent;
        cursor: pointer;
        font-size: 13px;
        color: var(--fg, #222222);
        box-sizing: border-box;
    }
    .learner-stats-picker-row.learner-stats-picker-selected {
        background: color-mix(in srgb, var(--accent-color, #007aff) 16%, transparent);
        border-color: var(--accent-color, #007aff);
        font-weight: 600;
    }
    .learner-stats-picker-row.learner-stats-picker-all {
        font-weight: 600;
        margin-bottom: 4px;
        padding-bottom: 10px;
        border-bottom: 1px solid var(--border, #e0e0e0);
        border-radius: 8px 8px 0 0;
    }
    .learner-stats-picker-toggle {
        display: block;
        flex-shrink: 0;
        width: 14px;
        height: 14px;
        padding: 0;
        margin: 0;
        border: none;
        background: transparent;
        cursor: pointer;
        position: relative;
    }
    .learner-stats-picker-toggle-spacer {
        flex-shrink: 0;
        width: 16px;
        height: 16px;
    }
    .learner-stats-picker-name {
        flex: 1 1 auto;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .learner-stats-picker-row-wrap.is-collapsed > .learner-stats-picker-children {
        display: none;
    }
    .learner-stats-picker-icon {
        flex-shrink: 0;
        width: 18px;
        height: 18px;
        background-color: var(--icon-color, var(--fg-subtle, #757575));
        -webkit-mask-size: contain;
        mask-size: contain;
        -webkit-mask-position: center;
        mask-position: center;
        -webkit-mask-repeat: no-repeat;
        mask-repeat: no-repeat;
        transition: background-color 0.2s ease;
    }
    .learner-stats-picker-row.learner-stats-picker-selected .learner-stats-picker-icon,
    .learner-stats-picker-row:hover .learner-stats-picker-icon {
        background-color: var(--accent-color, #007aff);
    }
    .learner-stats-picker-icon.emoji-icon {
        background-color: transparent !important;
        mask-image: none !important;
        -webkit-mask-image: none !important;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 15px;
        color: var(--fg, #222);
    }
    @keyframes learner-stats-spin {
        to { transform: rotate(360deg); }
    }
    </style>
    """

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
                            <h3>${payload.title || 'Decks'}</h3>
                            <button class="learner-stats-modal-close" type="button" aria-label="Close">&times;</button>
                        </div>
                        <div class="learner-stats-modal-body"></div>
                        <div class="learner-stats-modal-footer">
                            <button class="learner-stats-modal-btn secondary" type="button" data-action="cancel">${payload.cancel || 'Cancel'}</button>
                            <button class="learner-stats-modal-btn primary" type="button" data-action="save">${payload.save || 'Save'}</button>
                        </div>
                        <div class="learner-stats-modal-preparing">
                            <span class="learner-stats-modal-spinner"></span>
                            <span>${payload.preparing || 'Preparing your Onigiri'}</span>
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
                const selectedRow = body.querySelector('.learner-stats-picker-row.learner-stats-picker-selected');
                if (selectedRow) {
                    let ancestor = selectedRow.closest('.learner-stats-picker-children');
                    while (ancestor) {
                        const wrap = ancestor.closest('.learner-stats-picker-row-wrap');
                        if (wrap) wrap.classList.remove('is-collapsed');
                        ancestor = wrap ? wrap.parentElement.closest('.learner-stats-picker-children') : null;
                    }
                }

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
                    const toggle = event.target.closest('.learner-stats-picker-toggle');
                    if (toggle) {
                        event.preventDefault();
                        event.stopPropagation();
                        const wrap = toggle.closest('.learner-stats-picker-row-wrap');
                        if (wrap) wrap.classList.toggle('is-collapsed');
                        return;
                    }
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

    addon_dir = os.path.dirname(__file__)
    down_path = os.path.join(addon_dir, "system_files", "system_icons", "unavailable_for_users", "down.svg")
    right_path = os.path.join(addon_dir, "system_files", "system_icons", "unavailable_for_users", "right.svg")
    down_url = _get_data_uri(down_path)
    right_url = _get_data_uri(right_path)

    dynamic_css = f"""
    <style>
    .learner-stats-picker-toggle {{
        -webkit-mask-image: url('{down_url}');
        mask-image: url('{down_url}');
        -webkit-mask-size: contain;
        mask-size: contain;
        -webkit-mask-position: center;
        mask-position: center;
        -webkit-mask-repeat: no-repeat;
        mask-repeat: no-repeat;
        background-color: var(--icon-color, var(--fg-subtle, #757575)) !important;
        transition: none !important;
    }}
    .learner-stats-picker-row-wrap.is-collapsed > .learner-stats-picker-row .learner-stats-picker-toggle {{
        -webkit-mask-image: url('{right_url}');
        mask-image: url('{right_url}');
    }}
    .learner-stats-picker-toggle:hover {{
        background-color: var(--icon-color, var(--fg-subtle, #757575)) !important;
    }}
    </style>
    """

    # Generate widget content
    icon_grouped = '<svg width="15" height="15" viewBox="0 0 24 24"><path d="M0 0h24v24H0z" fill="none"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 5h16M4 12h16M4 19h16"/></svg>'
    icon_bars = '<svg width="15" height="15" viewBox="0 0 24 24"><path d="M0 0h24v24H0z" fill="none"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 5h12M4 12h16M4 19h8" transform="rotate(-90 12 12)"/></svg>'
    icon_donut = '<svg width="15" height="15" viewBox="0 0 24 24"><path d="M0 0h24v24H0z" fill="none"/><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="1.8"/></svg>'
    icon_chevron = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>'

    def _tile(label: str, value: int, tone: str, flat: bool = False) -> str:
        classes = "learner-stat-card"
        if tone != "neutral":
            classes += f" is-{tone}"
        if flat:
            classes += " is-flat"
        return (
            f'<div class="{classes}">'
            f'<span class="learner-stat-label">{html.escape(label)}</span>'
            f'<span class="learner-stat-val">{value}</span>'
            f'</div>'
        )

    def _bar_row(label: str, value: int, pct: float, tone: str) -> str:
        return f"""
            <div class="learner-stats-bar-row">
                <span class="learner-stats-bar-label">{html.escape(label)}</span>
                <span class="learner-stats-bar-track"><span class="learner-stats-bar-fill is-{tone}" style="width: {pct}%;"></span></span>
                <span class="learner-stats-bar-value">{value}</span>
            </div>"""

    footer_row_html = f"""
            <div class="learner-stats-footer-row">
                <span class="learner-stats-footer-item">{labels["buried"]} <b>{buried_cnt}</b></span>
                <span class="learner-stats-footer-item">{labels["suspended"]} <b>{suspended_cnt}</b></span>
                <span class="learner-stats-footer-item is-total">{labels["total"]} <b>{total_cnt}</b></span>
            </div>"""

    grouped_view_html = f"""
        <div class="learner-stats-view learner-stats-view-grouped" data-view="grouped">
            <div class="learner-stats-groupbar">
                <div class="learner-stats-groupbar-seg learner-stats-groupbar-inprogress" style="width: {in_progress_pct}%;"></div>
                <div class="learner-stats-groupbar-seg learner-stats-groupbar-mastered" style="width: {mastered_pct}%;"></div>
            </div>
            <div class="learner-stats-grouped-groups">
                <div class="learner-stats-group">
                    <div class="learner-stats-group-title is-inprogress">{labels["group_in_progress"]}</div>
                    <div class="learner-stats-tile-grid learner-stats-tile-grid-3">
                        {_tile(labels["new"], new_cnt, "inprogress")}
                        {_tile(labels["learning"], learn_cnt, "inprogress")}
                        {_tile(labels["young"], young_cnt, "inprogress")}
                    </div>
                </div>
                <div class="learner-stats-group">
                    <div class="learner-stats-group-title is-mastered">{labels["group_mastered"]}</div>
                    <div class="learner-stats-tile-grid learner-stats-tile-grid-2">
                        {_tile(labels["mature"], mature_cnt, "mastered")}
                        {_tile(labels["learned"], learned_cnt, "mastered")}
                    </div>
                </div>
                <div class="learner-stats-group">
                    <div class="learner-stats-group-title is-neutral">{labels["group_not_active"]}</div>
                    <div class="learner-stats-tile-grid learner-stats-tile-grid-4">
                        {_tile(labels["unseen"], unseen_cnt, "neutral")}
                        {_tile(labels["buried"], buried_cnt, "neutral")}
                        {_tile(labels["suspended"], suspended_cnt, "neutral")}
                        {_tile(labels["total"], total_cnt, "neutral")}
                    </div>
                </div>
            </div>
        </div>"""

    bar_spacer = '<div class="learner-stats-bar-spacer"></div>'
    bar_rows = [
        (labels["new"], new_cnt, new_bar_pct, "inprogress"),
        (labels["learning"], learn_cnt, learn_bar_pct, "inprogress"),
        (labels["young"], young_cnt, young_bar_pct, "inprogress"),
        (labels["mature"], mature_cnt, mature_bar_pct, "mastered"),
        (labels["learned"], learned_cnt, learned_bar_pct, "mastered"),
        (labels["unseen"], unseen_cnt, unseen_bar_pct, "neutral"),
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
                        <circle class="learner-stats-donut-arc-inprogress" cx="18" cy="18" r="15.5" fill="none" stroke-width="4" stroke-dasharray="{in_progress_arc} {ring_circumference}" stroke-dashoffset="0" stroke-linecap="round"></circle>
                        <circle class="learner-stats-donut-arc-mastered" cx="18" cy="18" r="15.5" fill="none" stroke-width="4" stroke-dasharray="{mastered_arc} {ring_circumference}" stroke-dashoffset="{mastered_offset}" stroke-linecap="round"></circle>
                    </svg>
                    <div class="learner-stats-donut-total">
                        <div class="learner-stats-donut-num">{total_cnt} <span>{labels["total_short"]}</span></div>
                        <div class="learner-stats-donut-legend">
                            <span class="learner-stats-donut-legend-item"><span class="learner-stats-donut-legend-dot is-inprogress"></span>{labels["group_in_progress"]}</span>
                            <span class="learner-stats-donut-legend-item"><span class="learner-stats-donut-legend-dot is-mastered"></span>{labels["group_mastered"]}</span>
                        </div>
                    </div>
                </div>
                <div class="learner-stats-tile-grid learner-stats-tile-grid-2">
                    {_tile(labels["new"], new_cnt, "neutral", flat=True)}
                    {_tile(labels["learning"], learn_cnt, "neutral", flat=True)}
                    {_tile(labels["young"], young_cnt, "neutral", flat=True)}
                    {_tile(labels["mature"], mature_cnt, "neutral", flat=True)}
                    {_tile(labels["learned"], learned_cnt, "neutral", flat=True)}
                    {_tile(labels["unseen"], unseen_cnt, "neutral", flat=True)}
                </div>
            </div>
            {footer_row_html}
        </div>"""

    switcher_html = "" if is_compact else f"""
                    <div class="learner-stats-switcher" role="tablist" aria-label="Stats view">
                        <div class="learner-stats-switcher-indicator"></div>
                        <button type="button" class="learner-stats-switcher-btn" data-view="grouped" aria-label="{labels["view_grouped"]}" title="{labels["view_grouped"]}" onclick="window.OnigiriLearnerStats && window.OnigiriLearnerStats.setView(this,'grouped');">{icon_grouped}</button>
                        <button type="button" class="learner-stats-switcher-btn" data-view="bars" aria-label="{labels["view_bars"]}" title="{labels["view_bars"]}" onclick="window.OnigiriLearnerStats && window.OnigiriLearnerStats.setView(this,'bars');">{icon_bars}</button>
                        <button type="button" class="learner-stats-switcher-btn" data-view="donut" aria-label="{labels["view_donut"]}" title="{labels["view_donut"]}" onclick="window.OnigiriLearnerStats && window.OnigiriLearnerStats.setView(this,'donut');">{icon_donut}</button>
                    </div>"""

    # Below ~1 grid row there's no room for any of the three detailed views
    # (each needs 150px+ of body height); fall back to a single glance line.
    compact_body_html = f"""
        <div class="learner-stats-compact-body">
            <div class="learner-stats-groupbar">
                <div class="learner-stats-groupbar-seg learner-stats-groupbar-inprogress" style="width: {in_progress_pct}%;"></div>
                <div class="learner-stats-groupbar-seg learner-stats-groupbar-mastered" style="width: {mastered_pct}%;"></div>
            </div>
            <div class="learner-stats-compact-total">{total_cnt} <span>{labels["total_short"]}</span></div>
        </div>"""

    body_html = compact_body_html if is_compact else f"""
            {grouped_view_html}
            {bars_view_html}
            {donut_view_html}"""

    html_widget = f"""
    <div class="learner-stats-widget" data-widget-id="{escaped_widget_id}" data-selected-did="{html.escape(str(selected_did), quote=True)}" data-picker-payload="{picker_payload}" data-active-view="{active_view}">
        <div class="learner-stats-header">
            <div class="learner-stats-header-row">
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
