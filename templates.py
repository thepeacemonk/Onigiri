# In templates.py

custom_body_template = """
<style>
    /* --- Edit Mode Styles --- */
    body.deck-edit-mode #deck-list-container {
        border: 2px dashed var(--accent-color);
        border-radius: 15px;
        background-color: rgba(128, 128, 128, 0.05);
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
        margin-right: 10px;
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
            {profile_bar}
            <div class="add-button-dashed action-add" onclick="pycmd('add')">
                <i class="icon"></i>
                <span>Add</span>
            </div>
            <div class="menu-item action-browse" onclick="pycmd('browse')">
                <i class="icon"></i>
                <span>Browser</span>
            </div>
            <div class="menu-item action-stats" onclick="pycmd('stats')">
                <i class="icon"></i>
                <span>Stats</span>
            </div>
            <div class="menu-item action-sync" onclick="pycmd('sync')">
                <i class="icon"></i>
                <span>Sync</span>
            </div>
            <div class="menu-item action-settings" onclick="pycmd('openOnigiriSettings')">
                <i class="icon"></i>
                <span>Settings</span>
            </div>
            
            <details class="menu-group">
                <summary class="menu-item action-more">
                    <i class="icon"></i>
                    <span>More</span>
                </summary>
                <div class="menu-group-items">
                    <div class="menu-item action-get-shared" onclick="pycmd('shared')">
                        <i class="icon"></i>
                        <span>Get Shared</span>
                    </div>
                    <div class="menu-item action-create-deck" onclick="pycmd('create')">
                        <i class="icon"></i>
                        <span>Create Deck</span>
                    </div>
                    <div class="menu-item action-import-file" onclick="pycmd('import')">
                        <i class="icon"></i>
                        <span>Import File</span>
                    </div>
                </div>
            </details>
            
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

const OnigiriEngine = {
    updateDeckTree: function(html) {
        const tbody = document.querySelector('#decktree > tbody');
        if (tbody) {
            tbody.innerHTML = html;
            if (OnigiriEditor.EDIT_MODE) {
                OnigiriEditor.reapplyEditModeState();
            }
        }
    }
};

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
    },

    handleMouseDown: function(e) {
        if (e.button !== 0 || this.EDIT_MODE) return;
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
    },

    exitEditMode: function() {
        if (!this.EDIT_MODE) return;
        this.EDIT_MODE = false;
        document.body.classList.remove('deck-edit-mode');
        document.querySelectorAll('.deck-checkbox').forEach(cb => cb.remove());
        this.SELECTED_DECKS.clear();
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
