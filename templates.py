# In templates.py

custom_body_template = """
<style>
    #deck-list-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        /* The sidebar already supplies the outer gutter. Adding another
           header-only inset left the toolbar visibly short of the deck rows
           in the live Deck Browser. */
        padding-right: 0;
        margin-top: 0;
        margin-bottom: 15px;
        min-height: 24px;
        position: relative;
    }

    #deck-list-header h2 {
        margin: 0;
        line-height: 24px;
        flex: 0 0 auto;
        font-size: 13px;
        text-transform: uppercase;
        color: var(--icon-color, var(--fg-subtle));
    }

    .deck-header-actions {
        display: flex;
        align-items: center;
        gap: 4px;
        flex-shrink: 0;
    }

    .deck-header-btn {
        width: 24px;
        height: 24px;
        border: none;
        border-radius: 6px;
        background: transparent;
        color: var(--icon-color, var(--fg-subtle));
        display: inline-flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        padding: 0;
        box-shadow: none !important;
        opacity: 0.72;
        outline: none !important;
        transition: none !important;
    }

    .deck-header-btn:hover {
        opacity: 1;
        color: var(--accent-color);
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }

    .deck-header-btn svg {
        width: 16px;
        height: 16px;
        pointer-events: none;
    }

    @keyframes deckRowAppear {
        from { opacity: 0.72; }
        to { opacity: 1; }
    }
    tr.deck.deck-row-appear {
        animation: deckRowAppear 0.06s linear both;
    }
    /* --- Sidebar Button Fix --- */
    .sidebar-left .menu-item,
    .sidebar-left .add-button-dashed,
    .sidebar-left .menu-group summary {
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        padding: 8px 12px !important;
        margin-bottom: 4px !important;
        box-sizing: border-box !important;
        border-radius: 6px !important;
        cursor: pointer !important;
        pointer-events: auto !important;
        flex-shrink: 0;
        min-height: 33px;
    }

    .sidebar-left .menu-item:hover,
    .sidebar-left .add-button-dashed:hover,
    .sidebar-left .menu-group summary:hover {
        background-color: rgba(128, 128, 128, 0.15) !important;
    }

    .sidebar-left .icon {
        margin-right: 12px !important;
        flex-shrink: 0;
    }
    .sidebar-left .deck-focus-btn .icon {
        margin-right: 0 !important;
    }
    
    /* --- Deck List Click Area Fix --- */
    .deck-table .decktd {
        display: flex;
        align-items: center;
        padding: 0 5px !important;
        pointer-events: auto !important;
    }

    .deck-table a.deck {
        flex-grow: 1;
        padding: 6px 8px;
        border-radius: 4px;
        display: block;
        pointer-events: auto !important;
    }

    .deck-table tr:not(.drag-hover) a.deck:hover {
         background-color: transparent !important;
    }
    /* --- Deck List Scrolling Fix --- */
    .sidebar-expanded-content {
        display: flex;
        flex-direction: column;
        height: 100%;
        overflow: hidden;
        background-color: transparent !important; /* Ensure no background */
    }

    #deck-list-container {
        flex: 1; 
        overflow-y: auto;
        min-height: 0; 
    }

    .onigiri-tag-table {
        width: 100%;
        border-collapse: collapse;
    }

    .onigiri-tag-row .decktd {
        padding: 0 !important;
    }

    .onigiri-tag-entry {
        display: flex;
        align-items: center;
        width: 100%;
        min-width: 0;
        min-height: 32px;
        margin-inline-start: calc(var(--tag-depth, 0) * 16px);
        padding: 3px 5px;
        border-radius: 6px;
        box-sizing: border-box;
    }

    .onigiri-tag-entry:hover {
        background-color: rgba(128, 128, 128, 0.1);
    }

    .onigiri-tag-toggle,
    .onigiri-tag-toggle-placeholder {
        flex: 0 0 20px;
        width: 20px;
        height: 24px;
    }

    .onigiri-tag-toggle {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin: 0;
        padding: 0;
        border: 0 !important;
        border-radius: 4px !important;
        background: transparent !important;
        box-shadow: none !important;
        color: var(--icon-color, var(--fg-subtle));
        cursor: pointer;
    }

    .onigiri-tag-toggle:hover {
        color: var(--accent-color);
    }

    .onigiri-tag-toggle svg {
        width: 12px;
        height: 12px;
        transition: transform 120ms ease;
    }

    .onigiri-tag-toggle[aria-expanded="true"] svg {
        transform: rotate(90deg);
    }

    .onigiri-tag-link {
        display: flex;
        align-items: center;
        gap: 8px;
        flex: 1;
        min-width: 0;
        margin: 0;
        padding: 4px 6px;
        border: 0 !important;
        border-radius: 4px !important;
        background: transparent !important;
        box-shadow: none !important;
        color: inherit;
        cursor: pointer;
        font: inherit;
        text-align: start;
    }

    .onigiri-tag-icon {
        flex: 0 0 16px;
        width: 16px;
        height: 16px;
        color: var(--icon-color, var(--fg-subtle));
    }

    .onigiri-tag-icon-mask {
        display: inline-block;
        background-color: var(--onigiri-tag-icon-light, var(--icon-color));
        -webkit-mask: var(--onigiri-tag-icon) center / contain no-repeat;
        mask: var(--onigiri-tag-icon) center / contain no-repeat;
    }

    .night-mode .onigiri-tag-icon-mask,
    .nightMode .onigiri-tag-icon-mask {
        background-color: var(--onigiri-tag-icon-dark, var(--icon-color));
    }

    .onigiri-tag-icon-image {
        display: block;
        object-fit: contain;
    }

    .onigiri-tag-icon-emoji {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        line-height: 1;
    }

    .onigiri-tag-name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        unicode-bidi: plaintext;
        text-align: start;
    }

    .onigiri-tag-empty {
        padding: 12px 10px;
        color: var(--fg-subtle);
        font-size: 12px;
        text-align: center;
    }

    .onigiri-sidebar-decks-section.is-tags-mode #onigiri-sort-toolbar-btn {
        display: none;
    }
</style>
<div class="container modern-main-menu {container_extra_class}">
    <div class="sidebar-left skeleton-loading {sidebar_initial_class}" style="{sidebar_style}">
        
        <div class="sidebar-expanded-content">
            <section class="onigiri-sidebar-section onigiri-sidebar-profile-section">
                {profile_bar}
            </section>
            <section class="onigiri-sidebar-section onigiri-sidebar-actions-section">
                {sidebar_buttons}
            </section>
            {ready_to_go}
            {profile_sidebar}
            <section class="onigiri-sidebar-section onigiri-sidebar-decks-section
                            {sidebar_list_class}">
                <div id="deck-list-header">
                    <h2>{sidebar_content_title}</h2>
                    <div id="onigiri-deck-search-bar">
                        <span class="onigiri-search-icon" aria-hidden="true"></span>
                        <input type="text" id="onigiri-deck-search-input" placeholder="{sidebar_search_placeholder}" autocomplete="off" spellcheck="false" />
                        <button id="onigiri-deck-search-close" aria-label="Close" type="button">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
                        </button>
                    </div>
                    <div class="deck-header-actions">
                        <button id="onigiri-search-toolbar-btn" class="deck-header-btn" onclick="OnigiriEngine.toggleDeckSearch()" title="{sidebar_search_title}" type="button">
                            {search_header_icon}
                        </button>
                        <button id="onigiri-sort-toolbar-btn" class="deck-header-btn" type="button" title="Sort decks" onclick="OnigiriEngine.showSortMenu(this, event)">
                            {sort_header_icon}
                        </button>
                        {ready_marker}
                        {home_button}
                    </div>
                </div>
                <div id="deck-list-container">
                    <table class="deck-table {sidebar_table_class}" id="decktree">
                        <tbody>
                           {tree}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>

        <div class="collapsed-content-wrapper">
            <div class="sidebar-collapsed-content">
                <div class="collapsed-placeholder welcome-placeholder"></div>
                <div class="collapsed-profile-item" onclick="window.OnigiriProfileSidebar && OnigiriProfileSidebar.open(event)">
                    {profile_pic_html_collapsed}
                </div>
                <div class="collapsed-actions-placeholder">
                    <div class="collapsed-placeholder action-placeholder"></div>
                    <div class="collapsed-placeholder action-placeholder"></div>
                    <div class="collapsed-placeholder action-placeholder"></div>
                    <div class="collapsed-placeholder action-placeholder"></div>
                    <div class="collapsed-placeholder action-placeholder"></div>
                    <div class="collapsed-placeholder action-placeholder"></div>
                </div>
                <div class="collapsed-placeholder decks-placeholder"></div>
            </div>
        </div>
    </div>
    <div class="sidebar-edge-toggle-zone" aria-hidden="true"></div>
    <div id="onigiri-sidebar-edge-pill" aria-hidden="false">
        <button id="onigiri-sidebar-edge-toggle" title="Collapse sidebar" aria-label="Collapse sidebar" type="button">
            <span class="sidebar-edge-toggle-icon" aria-hidden="true"></span>
        </button>
        <div class="resize-handle" aria-label="Select resize mode" role="button" tabindex="0">
            <span class="resize-handle-indicator" aria-hidden="true"></span>
        </div>
    </div>
    <div class="main-content">
        <div class="injected-stats-block">
            {stats}
        </div>
    </div>
</div>

<script>
// Disable Anki's default jQuery sortable on the deck tree. Onigiri owns deck
// sorting/reparenting through its lightweight pointer-drag handles.
(function() {
    if (typeof $ !== 'undefined' && $.ui) {
        const originalSortable = $.fn.sortable;
        $.fn.sortable = function(options) {
            if (this.selector === '#decktree > tbody' || this.parent().attr('id') === 'decktree') {
                return this;
            }
            return originalSortable.call(this, options);
        };
        for (let prop in originalSortable) {
            if (originalSortable.hasOwnProperty(prop)) {
                $.fn.sortable[prop] = originalSortable[prop];
            }
        }
    }
})();

// Compatibility shim for older Onigiri hooks.
const OnigiriEditor = {
    init: function() {},
    enterEditMode: function() {},
    exitEditMode: function() {},
    reapplyEditModeState: function() {},
};

// Sync Status Manager
const SyncStatusManager = {
    setSyncStatus: function(status) {
        const syncButtons = document.querySelectorAll('.action-sync');
        if (!syncButtons.length) return;
        
        syncButtons.forEach(function(syncButton) {
            syncButton.classList.remove('sync-needed');
        
            if (status === 'sync') {
                syncButton.classList.add('sync-needed');
            }
        });
        // If status is 'none', no class is added.
    }, 
    setSyncing: function(isSyncing) {
        const syncButtons = document.querySelectorAll('.action-sync');
        syncButtons.forEach(function(syncButton) {
            if (isSyncing) {
                syncButton.classList.add('is-syncing');
            } else {
                syncButton.classList.remove('is-syncing');
            }
        });
    }
};

document.addEventListener('DOMContentLoaded', function() {
    if (typeof anki !== 'undefined' && anki.setupDeckBrowser) {
        anki.setupDeckBrowser();
    }
    OnigiriEditor.init();
});
</script>
"""
