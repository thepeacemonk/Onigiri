# In templates.py

custom_body_template = """
<style>
    #deck-list-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        padding-right: 10px;
        margin-top: 30px;
        margin-bottom: 15px;
        min-height: 24px;
        position: relative;
    }

    #deck-list-header h2 {
        margin: 0;
        line-height: 24px;
        flex: 0 0 auto;
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

    #onigiri-focus-home-btn {
        display: none;
    }

    .sidebar-left.deck-focus-mode #onigiri-focus-home-btn {
        display: inline-flex;
    }

    @keyframes deckRowAppear {
        from { opacity: 0.72; }
        to { opacity: 1; }
    }
    tr.deck.deck-row-appear {
        animation: deckRowAppear 0.06s linear both;
    }
    /* --- Active State for Sidebar Toggle --- */
    .sidebar-toggle-btn.active {
        background-color: var(--highlight-bg) !important;
        border-color: var(--border) !important;
        box-shadow: none !important;
    }
    
    /* --- End Focus Button Style --- */

    /* --- Sidebar Button Icon Centering Fix --- */
    .sidebar-left .deck-focus-btn .icon {
        margin-right: 0 !important;
    }
    /* --- End Sidebar Button Icon Centering Fix --- */

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
        border-radius: 6px !important;s
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
         background-color: rgba(128, 128, 128, 0.1);
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
</style>
<div class="container modern-main-menu {container_extra_class}">
    <div class="sidebar-left skeleton-loading {sidebar_initial_class}" style="{sidebar_style}">
        
        <div class="sidebar-toggle-btn">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24">
                <g fill="none" stroke="currentColor" stroke-width="1.8">
                    <path d="M2 12c0-3.69 0-5.534.814-6.841a4.8 4.8 0 0 1 1.105-1.243C5.08 3 6.72 3 10 3h4c3.28 0 4.919 0 6.081.916c.43.338.804.759 1.105 1.243C22 6.466 22 8.31 22 12s0 5.534-.814 6.841a4.8 4.8 0 0 1-1.105 1.243C18.92 21 17.28 21 14 21h-4c-3.28 0-4.919 0-6.081-.916a4.8 4.8 0 0 1-1.105-1.243C2 17.534 2 15.69 2 12Z" />
                    <path stroke-linejoin="round" d="M9.5 3v18" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 7h1m-1 3h1" />
                </g>
            </svg>
        </div>

        <div class="sidebar-expanded-content">
            <h2>{welcome_message}</h2>
            {sidebar_buttons}
            
            <div id="deck-list-header">
                <h2>{tr_decks}</h2>
                <div id="onigiri-deck-search-bar">
                    <span class="onigiri-search-icon" aria-hidden="true"></span>
                    <input type="text" id="onigiri-deck-search-input" placeholder="Search decks..." autocomplete="off" spellcheck="false" />
                    <button id="onigiri-deck-search-close" aria-label="Close" type="button">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
                    </button>
                </div>
                <div class="deck-header-actions">
                    <button id="onigiri-search-toolbar-btn" class="deck-header-btn" onclick="OnigiriEngine.toggleDeckSearch()" title="Search decks" type="button">
                        <i class="search-btn-icon"></i>
                    </button>
                    <button class="deck-header-btn" type="button" title="Sort decks" onclick="OnigiriEngine.showSortMenu(this, event)">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.8"><path d="M8 5.5h12M8 12h12M8 18.5h12"/><path stroke-linejoin="round" d="M4.375 5.5H4.25m.25 0a.25.25 0 1 1-.5 0a.25.25 0 0 1 .5 0m-.125 6.5H4.25m.25 0a.25.25 0 1 1-.5 0a.25.25 0 0 1 .5 0m-.125 6.5H4.25m.25 0a.25.25 0 1 1-.5 0a.25.25 0 0 1 .5 0"/></svg>
                    </button>
                    <button id="onigiri-focus-home-btn" class="deck-header-btn" type="button" title="Home actions" onclick="OnigiriEngine.showHomeMenu(this, event)">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/></svg>
                    </button>
                </div>
            </div>
            <div id="deck-list-container">
                <table class="deck-table" id="decktree">
                    <tbody>
                       {tree}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="collapsed-content-wrapper">
            <div class="sidebar-collapsed-content">
                <div class="collapsed-placeholder welcome-placeholder"></div>
                <div class="collapsed-profile-item" onclick="pycmd('showUserProfile')">
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
    <button id="onigiri-sidebar-reveal-btn" title="Show sidebar" type="button">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24">
            <g fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M2 12c0-3.69 0-5.534.814-6.841a4.8 4.8 0 0 1 1.105-1.243C5.08 3 6.72 3 10 3h4c3.28 0 4.919 0 6.081.916c.43.338.804.759 1.105 1.243C22 6.466 22 8.31 22 12s0 5.534-.814 6.841a4.8 4.8 0 0 1-1.105 1.243C18.92 21 17.28 21 14 21h-4c-3.28 0-4.919 0-6.081-.916a4.8 4.8 0 0 1-1.105-1.243C2 17.534 2 15.69 2 12Z" />
                <path stroke-linejoin="round" d="M9.5 3v18" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 7h1m-1 3h1" />
            </g>
        </svg>
    </button>
    <div class="resize-handle"></div>
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
        const syncButton = document.querySelector('.action-sync');
        if (!syncButton) return;
        
        // Remove existing sync status classes
        syncButton.classList.remove('sync-needed');
        
        // Add sync-needed class if any sync is required
        if (status === 'sync') {
            syncButton.classList.add('sync-needed');
        }
        // If status is 'none', no class is added (indicator stays hidden)
    }, 
    // ADD THIS NEW FUNCTION:
    setSyncing: function(isSyncing) {
        const syncButton = document.querySelector('.action-sync');
        if (syncButton) {
            if (isSyncing) {
                syncButton.classList.add('is-syncing');
            } else {
                syncButton.classList.remove('is-syncing');
            }
        }
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
