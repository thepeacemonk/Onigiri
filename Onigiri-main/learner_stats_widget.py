# Learner Stats Widget for Onigiri

import html
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

    # Render deck selection dropdown options
    options_html = []
    
    # All Decks option
    selected_attr = ' selected' if selected_did == "all" else ''
    options_html.append(f'<option value="all"{selected_attr}>{labels["all_decks"]}</option>')
    
    for deck in all_decks:
        selected_attr = ' selected' if str(deck.id) == str(selected_did) else ''
        # Shorten deck name for dropdown list if it's long
        short_name = deck.name
        if len(short_name) > 50:
            short_name = short_name[:22] + "..." + short_name[-25:]
        options_html.append(f'<option value="{deck.id}"{selected_attr}>{html.escape(short_name)}</option>')

    select_html = f"""
    <select class="learner-stats-select" onchange="pycmd('onigiri_learner_stats_select_deck:{widget_id}:' + this.value);">
        {"".join(options_html)}
    </select>
    """

    # Generate CSS
    css_html = """
    <style>
    .learner-stats-widget {
        background-color: var(--canvas-inset, #ffffff);
        border: 1px solid var(--border, #e0e0e0);
        border-radius: 15px;
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
        letter-spacing: 0.5px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        width: 100%;
    }
    .learner-stats-select {
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
        text-overflow: ellipsis;
        white-space: nowrap;
        overflow: hidden;
    }
    .learner-stats-select:focus {
        border-color: var(--accent-color, #007aff);
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
        letter-spacing: -0.2px;
    }
    .learner-stat-val {
        font-size: 13px;
        font-weight: 700;
        color: var(--fg, #222222);
    }
    .learner-stat-new .learner-stat-val { color: var(--accent-color, #007aff); }
    .learner-stat-learning .learner-stat-val { color: #f08a5d; }
    .learner-stat-mature .learner-stat-val { color: #2ecc71; }
    .learner-stat-young .learner-stat-val { color: #3498db; }
    .learner-stat-learned .learner-stat-val { color: #1abc9c; }
    .learner-stat-unseen .learner-stat-val { color: var(--fg-subtle, #757575); }
    .learner-stat-buried .learner-stat-val { color: #9b59b6; }
    .learner-stat-suspended .learner-stat-val { color: #e67e22; }
    .learner-stat-total .learner-stat-val { color: var(--fg, #222222); font-size: 15px; }
    </style>
    """

    # Generate widget content
    html_content = f"""
    {css_html}
    <div class="learner-stats-widget">
        <div class="learner-stats-header">
            <h3>{labels["title"]}</h3>
            {select_html}
        </div>
        <div class="learner-stats-grid">
            <div class="learner-stat-card learner-stat-new">
                <span class="learner-stat-label" title="{labels["new"]}">{labels["new"]}</span>
                <span class="learner-stat-val">{new_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-learning">
                <span class="learner-stat-label" title="{labels["learning"]}">{labels["learning"]}</span>
                <span class="learner-stat-val">{learn_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-mature">
                <span class="learner-stat-label" title="{labels["mature"]}">{labels["mature"]}</span>
                <span class="learner-stat-val">{mature_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-young">
                <span class="learner-stat-label" title="{labels["young"]}">{labels["young"]}</span>
                <span class="learner-stat-val">{young_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-learned">
                <span class="learner-stat-label" title="{labels["learned"]}">{labels["learned"]}</span>
                <span class="learner-stat-val">{learned_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-unseen">
                <span class="learner-stat-label" title="{labels["unseen"]}">{labels["unseen"]}</span>
                <span class="learner-stat-val">{unseen_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-buried">
                <span class="learner-stat-label" title="{labels["buried"]}">{labels["buried"]}</span>
                <span class="learner-stat-val">{buried_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-suspended">
                <span class="learner-stat-label" title="{labels["suspended"]}">{labels["suspended"]}</span>
                <span class="learner-stat-val">{suspended_cnt}</span>
            </div>
            <div class="learner-stat-card learner-stat-total">
                <span class="learner-stat-label" title="{labels["total"]}">{labels["total"]}</span>
                <span class="learner-stat-val">{total_cnt}</span>
            </div>
        </div>
    </div>
    """
    return html_content

def render_learner_stats_widget(deck_browser: DeckBrowser, content) -> None:
    # This is a base template hook. The layout editor uses it to detect the widget.
    # Onigiri will render instances directly via onigiri_renderer.py.
    pass

def init():
    from aqt import gui_hooks
    gui_hooks.deck_browser_will_render_content.append(render_learner_stats_widget)
