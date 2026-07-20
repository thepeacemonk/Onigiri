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
            "total": "Tổng cộng (Total)"
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
            "total": "Total"
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
    if len(leaf_name) > 34:
        return leaf_name[:15] + "..." + leaf_name[-16:]
    return leaf_name

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
        from .decks import tree_updater
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

def _render_widget(deck_browser: DeckBrowser, widget_id: str) -> str:
    labels = get_translated_labels()
    
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

    # Calculate percentages for the stacked bar: Mature, Young, New, Unseen
    bar_total = mature_cnt + young_cnt + new_cnt + unseen_cnt
    if bar_total > 0:
        mature_pct = (mature_cnt / bar_total) * 100
        young_pct = (young_cnt / bar_total) * 100
        new_pct = (new_cnt / bar_total) * 100
        unseen_pct = (unseen_cnt / bar_total) * 100
    else:
        mature_pct = young_pct = new_pct = unseen_pct = 0

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
        padding: 14px;
        height: 100%;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        gap: 10px;
        overflow: hidden;
    }
    .learner-stats-header {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 6px;
        width: 100%;
        box-sizing: border-box;
        overflow: hidden;
    }
    .learner-stats-header h3 {
        margin: 0;
        font-size: 13px;
        text-transform: uppercase;
        color: var(--fg-subtle, #757575);
        font-weight: 600;
        letter-spacing: 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        width: 100%;
    }
    .learner-stats-deck-trigger {
        appearance: none;
        -webkit-appearance: none;
        font-family: inherit;
        margin: 0;
        background: var(--highlight-bg, #eeeeee);
        color: var(--fg, #222222);
        border: 1px solid var(--border, #e0e0e0);
        border-radius: 8px;
        padding: 4px 8px;
        font-size: 11px;
        width: 100%;
        max-width: 100%;
        box-sizing: border-box;
        outline: none;
        cursor: pointer;
        transition: border-color 0.2s ease;
        text-align: left;
        text-overflow: ellipsis;
        white-space: nowrap;
        overflow: hidden;
    }
    .learner-stats-deck-trigger:hover,
    .learner-stats-deck-trigger:focus {
        border-color: var(--border, #e0e0e0) !important;
        background: var(--highlight-bg, #eeeeee) !important;
        filter: none !important;
        outline: none !important;
    }
    .learner-stats-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
        flex-grow: 1;
    }
    .learner-stat-card {
        background: color-mix(in srgb, var(--fg, #222) 3%, transparent);
        border: 1px solid var(--border, #e0e0e0);
        border-radius: 10px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 4px 2px;
        transition: all 0.2s ease;
        box-sizing: border-box;
        min-width: 0;
    }
    .learner-stat-card:hover {
        background: color-mix(in srgb, var(--accent-color, #007aff) 6%, transparent);
        border-color: var(--accent-color, #007aff);
        transform: translateY(-1px);
    }
    .learner-stat-label {
        font-size: 8px;
        font-weight: 500;
        color: var(--fg-subtle, #757575);
        text-align: center;
        margin-bottom: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        width: 100%;
        letter-spacing: 0;
    }
    .learner-stat-val {
        font-size: 13px;
        font-weight: 700;
        color: var(--fg, #222222);
    }
    .learner-stat-new .learner-stat-val { color: #007aff; }
    .learner-stat-learning .learner-stat-val { color: #f08a5d; }
    .learner-stat-mature .learner-stat-val { color: #2ecc71; }
    .learner-stat-young .learner-stat-val { color: #3498db; }
    .learner-stat-learned .learner-stat-val { color: #1abc9c; }
    .learner-stat-unseen .learner-stat-val { color: var(--fg-subtle, #757575); }
    .learner-stat-buried .learner-stat-val { color: #9b59b6; }
    .learner-stat-suspended .learner-stat-val { color: #e67e22; }
    .learner-stat-total .learner-stat-val { color: var(--fg, #222222); font-size: 15px; }
    .learner-stats-stacked-bar {
        display: flex;
        width: 100%;
        height: 10px;
        border-radius: 5px;
        overflow: hidden;
        background-color: color-mix(in srgb, var(--fg, #222) 8%, transparent);
        margin-top: 4px;
        box-sizing: border-box;
    }
    .learner-stats-stacked-segment {
        height: 100%;
        transition: width 0.3s ease, opacity 0.2s ease;
        cursor: pointer;
    }
    .learner-stats-stacked-segment:hover {
        opacity: 0.8;
    }
    .learner-stats-stacked-mature {
        background-color: #2ecc71;
    }
    .learner-stats-stacked-young {
        background-color: #3498db;
    }
    .learner-stats-stacked-new {
        background-color: #007aff;
    }
    .learner-stats-stacked-unseen {
        background-color: var(--fg-subtle, #757575);
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
        color: var(--fg, #222222);
        font-size: 16px;
        font-weight: 700;
        letter-spacing: 0;
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
    .learner-stats-picker-row:hover {
        background: var(--highlight-bg, #eeeeee);
    }
    .learner-stats-picker-row.learner-stats-picker-selected {
        background: color-mix(in srgb, var(--accent-color, #007aff) 16%, transparent);
        border-color: var(--accent-color, #007aff);
        color: var(--accent-color, #007aff);
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
    html_content = f"""
    {css_html}
    {dynamic_css}
    <div class="learner-stats-widget" data-widget-id="{escaped_widget_id}" data-selected-did="{html.escape(str(selected_did), quote=True)}" data-picker-payload="{picker_payload}">
        <div class="learner-stats-header">
            <h3>{labels["title"]}</h3>
            <button class="learner-stats-deck-trigger" type="button" onclick="window.OnigiriLearnerStatsDialog && window.OnigiriLearnerStatsDialog.open(this);">{html.escape(deck_label)}</button>
            <div class="learner-stats-stacked-bar">
                <div class="learner-stats-stacked-segment learner-stats-stacked-mature" style="width: {mature_pct}%;"></div>
                <div class="learner-stats-stacked-segment learner-stats-stacked-young" style="width: {young_pct}%;"></div>
                <div class="learner-stats-stacked-segment learner-stats-stacked-new" style="width: {new_pct}%;"></div>
                <div class="learner-stats-stacked-segment learner-stats-stacked-unseen" style="width: {unseen_pct}%;"></div>
            </div>
        </div>
        <div class="learner-stats-grid">
            <div class="learner-stat-card learner-stat-new">
                <span class="learner-stat-label">{labels["new"]}</span>
                <span class="learner-stat-val">{new_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-learning">
                <span class="learner-stat-label">{labels["learning"]}</span>
                <span class="learner-stat-val">{learn_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-mature">
                <span class="learner-stat-label">{labels["mature"]}</span>
                <span class="learner-stat-val">{mature_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-young">
                <span class="learner-stat-label">{labels["young"]}</span>
                <span class="learner-stat-val">{young_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-learned">
                <span class="learner-stat-label">{labels["learned"]}</span>
                <span class="learner-stat-val">{learned_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-unseen">
                <span class="learner-stat-label">{labels["unseen"]}</span>
                <span class="learner-stat-val">{unseen_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-buried">
                <span class="learner-stat-label">{labels["buried"]}</span>
                <span class="learner-stat-val">{buried_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-suspended">
                <span class="learner-stat-label">{labels["suspended"]}</span>
                <span class="learner-stat-val">{suspended_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-total">
                <span class="learner-stat-label">{labels["total"]}</span>
                <span class="learner-stat-val">{total_cnt}</span>
            </div>
        </div>
        <template class="learner-stats-deck-template">
            {picker_html}
        </template>
    </div>
    {script_html}
    """
    return html_content

def render_learner_stats_widget(deck_browser: DeckBrowser, content) -> None:
    # This is a base template hook. The layout editor uses it to detect the widget.
    # Onigiri will render instances directly via onigiri_renderer.py.
    pass

def init():
    from aqt import gui_hooks
    gui_hooks.deck_browser_will_render_content.append(render_learner_stats_widget)
