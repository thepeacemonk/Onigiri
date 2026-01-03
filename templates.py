# In templates.py

custom_body_template = """
<style>
    /* --- Edit Mode Styles --- */
    body.deck-edit-mode #deck-list-container {
        border: 2px dashed var(--accent-color);
        border-radius: 15px;
        background-color: transparent !important; /* Changed from var(--deck-edit-mode-bg) to transparent */
    }

    body.deck-edit-mode .decktd a.deck {
        pointer-events: none !important; /* Disable clicking into decks */
        color: var(--fg-disabled) !important;
    }
    
    #deck-list-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-right: 10px;
    }

    .deck-checkbox {
        margin-right: 0px; /* MODIFIED */
        margin-left: 5px;
        width: 16px;
        height: 16px;
        flex-shrink: 0;
        accent-color: var(--accent-color);
    }
    /* --- End Edit Mode Styles --- */

    /* --- Custom Context Menu --- */
    #deck-context-menu {
        display: none;
        position: absolute;
        z-index: 10000;
        background-color: var(--canvas-overlay);
        border: 1px solid var(--border);
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        padding: 6px;
        min-width: 180px;
    }
    .context-menu-item {
        padding: 8px 12px;
        cursor: pointer;
        border-radius: 5px;
        display: flex;
        align-items: center;
        font-size: 14px;
    }
    .context-menu-item:hover {
        background-color: var(--canvas-inset);
    }

    /* --- NEW: Favorite Star Styles --- */
    .favorite-star-icon {
        display: none; /* Hidden by default */
        width: 18px;
        height: 18px;
        flex-shrink: 0;
        background-color: var(--fg-faint);
        mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolygon points='12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'%3E%3C/polygon%3E%3C/svg%3E");
        mask-size: contain;
        mask-repeat: no-repeat;
        mask-position: center;
        cursor: pointer;
        margin-left: 8px; /* Space from checkbox */
        margin-right: 8px; /* Space from name */
        transition: background-color 0.2s ease, transform 0.1s ease;
    }
    body.deck-edit-mode .favorite-star-icon {
        display: inline-block; /* Show in edit mode */
    }
    .favorite-star-icon:hover {
        background-color: var(--accent-color);
        transform: scale(1.1);
    }
    .favorite-star-icon.is-favorite {
        background-color: var(--accent-color); /* Use theme accent color */
        /* The mask (icon shape) remains the same */
        mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='currentColor' stroke='%23FFD700' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolygon points='12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'%3E%3C/polygon%3E%3C/svg%3E");
    }
    .favorite-star-icon.is-favorite:hover {
        background-color: var(--accent-hover); /* Use theme accent hover color */
    }
    /* --- End Favorite Star Styles --- */

    /* --- Active State for Sidebar Toggle --- */
    .sidebar-toggle-btn.active {
        background-color: var(--icon-color) !important;
        border-color: var(--icon-color) !important;
    }
    
    /* --- End Focus Button Style --- */

    /* --- Sidebar Button Icon Centering Fix --- */
    .sidebar-left .deck-focus-btn .icon,
    .sidebar-left .deck-edit-btn .icon{
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
    
    .sidebar-left .deck-transfer-btn .icon {
        margin: 0 !important;
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
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
        </div>

        <div class="sidebar-expanded-content">
            <h2>{welcome_message}</h2>
            {sidebar_buttons}
            
            <div id="deck-list-header">
                <h2>DECKS</h2>
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
    <div class="resize-handle"></div>
    <div class="main-content">
        <div class="injected-stats-block">
            {stats}
        </div>
    </div>
</div>

<div id="deck-context-menu">
    <div class="context-menu-item" id="transfer-decks-btn">
        <span>Transfer to...</span>
    </div>
</div>

<script>
// Disable Anki's default drag-and-drop on the deck tree
(function() {
    if (typeof $!== 'undefined' &&$.ui) {
        const originalSortable = $.fn.sortable;
        $.fn.sortable = function(options) {
            if (this.selector === '#decktree > tbody' || this.parent().attr('id') === 'decktree') {
                return this; // Do nothing, effectively disabling it
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

const OnigiriEditor = {
    longPressTimer: null,
    EDIT_MODE: false,
    SELECTED_DECKS: new Set(),

    init: function() {
        const container = document.getElementById('deck-list-container');
        if (!container) return;
        
        container.addEventListener('mousedown', this.handleMouseDown.bind(this));
        container.addEventListener('mouseup', this.handleMouseUp.bind(this));
        container.addEventListener('mouseleave', this.handleMouseUp.bind(this));
        container.addEventListener('contextmenu', this.handleContextMenu.bind(this));

        document.getElementById('transfer-decks-btn').addEventListener('click', this.openTransferWindow.bind(this));

        // --- RESTORE EDIT MODE STATE FROM SESSIONSTORAGE ---
        // This ensures edit mode persists across page refreshes (e.g., after deck operations)
        try {
            const savedEditMode = sessionStorage.getItem('onigiri_edit_mode');
            const savedSelectedDecks = sessionStorage.getItem('onigiri_selected_decks');
            
            if (savedEditMode === 'true') {
                // Restore selected decks first
                if (savedSelectedDecks) {
                    const deckIds = JSON.parse(savedSelectedDecks);
                    this.SELECTED_DECKS = new Set(deckIds);
                }
                // Then enter edit mode (this will apply the checkboxes)
                this.enterEditMode();
            }
        } catch (e) {
            // If sessionStorage fails, just continue without restoring state
            console.warn('Failed to restore edit mode state:', e);
        }

        // --- NEW SELF-HEALING OBSERVER ---
        // This watches for changes to the deck list (like after a collapse)
        const deckTreeBody = document.querySelector('#decktree > tbody');
        if (deckTreeBody) {
            const observer = new MutationObserver((mutations) => {
                if (this.EDIT_MODE) {
                    // If we are in edit mode, re-scan for missing checkboxes
                    // Use a short delay to let the DOM settle
                    setTimeout(() => this.reapplyEditModeState(), 50);
                }
            });
            // Watch for nodes being added or removed from the deck tree
            observer.observe(deckTreeBody, { childList: true });
        }
    },

    handleMouseDown: function(e) {
        if (e.button !== 0 || this.EDIT_MODE) return;
        
        // --- ADD THIS BLOCK ---
        // Don't trigger long-press if clicking on a favorite star
        if (e.target.classList.contains('favorite-star-icon')) {
            return;
        }
        // --- END OF BLOCK ---

        const isScrollbar = e.currentTarget.scrollHeight > e.currentTarget.clientHeight && e.offsetX >= e.currentTarget.clientWidth;
        if (isScrollbar) return;

        this.longPressTimer = setTimeout(() => {
            this.enterEditMode();
        }, 600);
    },

    handleMouseUp: function() {
        clearTimeout(this.longPressTimer);
    },

    enterEditMode: function() {
        if (this.EDIT_MODE) return;
        this.EDIT_MODE = true;
        document.body.classList.add('deck-edit-mode');
        this.reapplyEditModeState();
        
        // Save edit mode state to sessionStorage
        try {
            sessionStorage.setItem('onigiri_edit_mode', 'true');
        } catch (e) {
            console.warn('Failed to save edit mode state:', e);
        }
    },

    exitEditMode: function() {
        if (!this.EDIT_MODE) return;
        this.EDIT_MODE = false;
        document.body.classList.remove('deck-edit-mode');
        document.querySelectorAll('.deck-checkbox').forEach(cb => cb.remove());
        this.SELECTED_DECKS.clear();
        
        // Clear edit mode state from sessionStorage
        try {
            sessionStorage.removeItem('onigiri_edit_mode');
            sessionStorage.removeItem('onigiri_selected_decks');
        } catch (e) {
            console.warn('Failed to clear edit mode state:', e);
        }
    },

    reapplyEditModeState: function() {
        document.querySelectorAll('#decktree tr.deck').forEach(row => {
            const did = row.id.replace('deck-', '');
            if (row.querySelector('.deck-checkbox')) return;

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'deck-checkbox';
            checkbox.dataset.did = did;
            checkbox.checked = this.SELECTED_DECKS.has(did);

            checkbox.onclick = (e) => {
                e.stopPropagation();
                if (e.target.checked) {
                    this.SELECTED_DECKS.add(e.target.dataset.did);
                } else {
                    this.SELECTED_DECKS.delete(e.target.dataset.did);
                }
                
                // Save selected decks to sessionStorage whenever selection changes
                try {
                    const deckIds = Array.from(this.SELECTED_DECKS);
                    sessionStorage.setItem('onigiri_selected_decks', JSON.stringify(deckIds));
                } catch (e) {
                    console.warn('Failed to save selected decks:', e);
                }
            };

            const decktd = row.querySelector('.decktd');
            if (decktd) {
                decktd.prepend(checkbox);
            }
        });
    },

    handleContextMenu: function(e) {
        if (!this.EDIT_MODE || this.SELECTED_DECKS.size === 0) return;
        
        const targetRow = e.target.closest('tr.deck');
        if (!targetRow) return;

        const did = targetRow.id.replace('deck-', '');
        if (!this.SELECTED_DECKS.has(did)) return;

        e.preventDefault();
        const menu = document.getElementById('deck-context-menu');
        menu.style.display = 'block';
        menu.style.left = `${e.pageX}px`;
        menu.style.top = `${e.pageY}px`;

        const hideMenu = () => {
            menu.style.display = 'none';
        };
        setTimeout(() => document.addEventListener('click', hideMenu, { once: true }), 0);
    },

    openTransferWindow: function() {
        if (this.SELECTED_DECKS.size === 0) return;
        const payload = Array.from(this.SELECTED_DECKS);
        pycmd(`onigiri_show_transfer_window:${JSON.stringify(payload)}`);
    }
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

    // Add a global escape key listener to exit edit mode
    document.addEventListener('keydown', (e) => {
        if (e.key === "Escape" && OnigiriEditor.EDIT_MODE) {
            OnigiriEditor.exitEditMode();
        }
    });
});
</script>
"""