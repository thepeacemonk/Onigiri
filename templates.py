# In templates.py

custom_body_template = """
<style>
    #deck-list-header {
        display: flex;
        align-items: center;
        padding-right: 10px;
        transition: opacity 0.15s ease;
    }

    /* --- Drag & Drop Styles --- */
    .drag-handle {
        opacity: 0;
        cursor: grabbing !important;
        transition: opacity 0.12s ease;
        color: var(--fg-subtle);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 14px;
        min-width: 14px;
        height: 18px;
        flex-shrink: 0;
        pointer-events: auto;
    }
    tr.deck:hover .drag-handle {
        opacity: 0.45;
    }
    tr.deck.is-dragging {
        opacity: 0.5;
        background-color: rgba(0, 0, 0, 0.1) !important;
    }
    /* Nest target — same flat highlight as right-click, fixed colour */
    tr.deck.drag-over-target {
        background-color: #1F1F1E !important;
    }
    /* Right-click context menu highlight — same shape as hover (whole tr row) */
    tr.deck.ctx-row-active {
        background-color: {ctx_highlight_color} !important;
    }
    /* Ensure right-click highlight always wins over .current selection */
    tr.deck.ctx-row-active.current {
        background-color: {ctx_highlight_color} !important;
    }
    /* Suppress hover on all other rows while context menu is open */
    body.ctx-menu-open tr.deck:not(.ctx-row-active):hover,
    body.ctx-menu-open tr.deck.is-hovered:not(.ctx-row-active) {
        background-color: transparent;
    }
    body.ctx-menu-open tr.deck:hover .drag-handle {
        opacity: 0 !important;
    }
    /* Hide drag handle while context menu is open */
    tr.deck.ctx-row-active .drag-handle {
        opacity: 0 !important;
    }
    /* --- End Drag & Drop Styles --- */

    /* --- Expand / collapse row animation ---
       New rows that appear after a deck is expanded fade in with a brief
       slide-down so the list feels alive rather than popping instantly.    */
    @keyframes deckRowAppear {
        from { opacity: 0; transform: translateY(-5px); }
        to   { opacity: 1; transform: translateY(0);    }
    }
    tr.deck.deck-row-appear {
        animation: deckRowAppear 0.18s cubic-bezier(0.16, 1, 0.3, 1) both;
    }
    /* Collapse: rows slide up and fade out */
    @keyframes deckRowDisappear {
        from { opacity: 1; transform: translateY(0);    }
        to   { opacity: 0; transform: translateY(-6px); }
    }
    tr.deck.deck-row-disappear {
        animation: deckRowDisappear 0.14s cubic-bezier(0.55, 0, 1, 0.45) both;
        pointer-events: none;
    }
    /* --- End Expand / collapse row animation --- */

    /* --- Mark dot (coloured circle shown next to deck name) --- */
    .deck-mark-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        flex-shrink: 0;
        margin-left: 5px;
        display: inline-block;
        vertical-align: middle;
    }
    /* --- End Mark dot --- */

    /* --- Search Button (positioned absolutely, left of ellipsis) --- */
    #onigiri-search-toolbar-btn {
        position: absolute;
        top: 15px;
        right: 39px;
        z-index: 11;
        background: none;
        border: none;
        cursor: pointer;
        padding: 0;
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        opacity: 0.6;
        line-height: 0;
        transition: opacity 0.15s;
    }
    #onigiri-search-toolbar-btn:hover {
        opacity: 1;
    }
    /* --- Deck Search Bar (pill, positioned absolutely in toolbar row) --- */
    #onigiri-deck-search-bar {
        display: none;
        position: absolute;
        top: 13.5px;
        left: 18px;
        right: 45px;
        z-index: 12;
        align-items: center;
        gap: 4px;
        background: #323232;
        border: 2px solid #323232;
        border-radius: 9999px;
        padding: 4px 1px 4px 9px;
        background-clip: padding-box;
        outline: 2px solid #323232;
        outline-offset: 0.3px;
        transition: outline-color 0.15s ease;
    }
    #onigiri-deck-search-bar.is-visible {
        display: flex;
        animation: oniSearchReveal 0.28s cubic-bezier(0.16, 1, 0.3, 1) both;
    }
    #onigiri-deck-search-bar.is-closing {
        animation: oniSearchDismiss 0.1s cubic-bezier(0.55, 0, 1, 0.45) both !important;
    }
    @keyframes oniSearchReveal {
        from {
            opacity: 0;
            transform: translateX(10px);
            clip-path: inset(0 0 0 70% round 9999px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
            clip-path: inset(-5px -5px -5px -5px round 9999px);
        }
    }
    @keyframes oniSearchDismiss {
        from {
            opacity: 1;
            transform: translateX(0);
            clip-path: inset(-5px -5px -5px -5px round 9999px);
        }
        to {
            opacity: 0;
            transform: translateX(10px);
            clip-path: inset(0 0 0 70% round 9999px);
        }
    }
    #onigiri-deck-search-input {
        flex: 1;
        background: none;
        border: none;
        outline: none;
        font-size: 13px;
        font-family: var(--font-main, system-ui, sans-serif);
        color: var(--fg, #e0e0e0);
        min-width: 0;
        letter-spacing: 0.01em;
    }
    #onigiri-deck-search-bar:focus-within {
        outline-color: var(--accent-color, #007aff);
    }
    #onigiri-deck-search-input::placeholder {
        color: var(--fg-subtle, rgba(255,255,255,0.35));
    }
    .onigiri-search-icon {
        width: 14px;
        height: 14px;
        min-width: 14px;
        flex-shrink: 0;
        background-color: var(--fg-subtle, rgba(255,255,255,0.35));
        mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='none' stroke='%23000' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='m21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0'/%3E%3C/svg%3E");
        mask-size: contain;
        mask-repeat: no-repeat;
        mask-position: center;
        -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='none' stroke='%23000' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='m21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0'/%3E%3C/svg%3E");
        -webkit-mask-size: contain;
        -webkit-mask-repeat: no-repeat;
        -webkit-mask-position: center;
        pointer-events: none;
        margin-right: 4px;
    }
    #onigiri-deck-search-close {
        background: none;
        border: none;
        cursor: pointer;
        padding: 2px;
        display: flex;
        align-items: center;
        color: rgba(255,255,255,0.5);
        flex-shrink: 0;
        line-height: 0;
    }
    #onigiri-deck-search-close:hover { color: rgba(255,255,255,0.9); }
    #onigiri-deck-search-close svg { pointer-events: none; }
    /* --- End Deck Search Bar --- */

    /* --- Active State for Sidebar Toggle --- */
    .sidebar-toggle-btn.active {
        background-color: var(--icon-color) !important;
        border-color: var(--icon-color) !important;
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
    
    .sidebar-left .deck-transfer-btn .icon {
        margin: 0 !important;
    }

    /* --- Deck List Click Area Fix --- */
    .deck-table .decktd {
        display: flex;
        align-items: center;
        padding: 0 8px 0 2px !important;
        pointer-events: auto !important;
    }

    /* Force all deck-info containers to flex regardless of row type (is-deck /
       is-folder / is-subdeck / is-filtered all get consistent layout). */
    .deck-table .deck-info {
        display: flex !important;
        align-items: center !important;
        flex: 1 !important;
        min-width: 0 !important;
    }

    /* Make the deck-prefix span a flex container so a.collapse and span.collapse
       are flex items — removing any inline-block vertical-align / line-height
       quirks that cause the 2 px horizontal shift seen on parent subdecks. */
    .deck-table .deck-info > span {
        display: flex !important;
        align-items: center !important;
        flex-shrink: 0 !important;
    }

    .deck-table a.deck {
        flex-grow: 1;
        flex-shrink: 1;
        min-width: 0;
        padding: 6px 8px;
        border-radius: 4px;
        display: block;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        pointer-events: auto !important;
    }

    .deck-table tr:not(.drag-hover) a.deck:hover {
         background-color: rgba(128, 128, 128, 0.1);
    }
    /* --- Deck Alignment: collapse spacer for leaf decks ---
       span.collapse is now a flex item inside the deck-prefix span, so its
       width and margin-right are respected exactly — matching a.collapse.
       NOTE: a.collapse has position:relative (menu.css) which causes a 2px
       rendering shift in Chromium flex layout vs the plain span.collapse.
       We compensate by giving a.collapse margin-right:2px and span.collapse
       margin-right:4px — the 2px delta cancels the rendering offset. */
    .deck-table span.collapse {
        display: flex !important;
        width: var(--collapse-icon-size, 12px) !important;
        min-width: var(--collapse-icon-size, 12px) !important;
        height: 1px !important;
        margin-right: 4px !important;
        flex-shrink: 0 !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }
    .deck-table a.collapse {
        margin-right: 2px !important;
    }

    /* Shift the deck list (and its header) left to use full sidebar width.
       margin-left: -8px → sidebar padding-left(15) - 8 = 7px from left border.
       Container margin-right: -20px + padding-right: 4px → ~9px from right border.
       Net asymmetry: 2px more on the right side, as intended. */
    #deck-list-container {
        margin-left: -8px;
    }
    #deck-list-header {
        margin-left: -8px;
        padding-right: 6px;
    }

    /* --- Deck List Scrolling Fix --- */
    /* .sidebar-left has max-height: calc(100vh - 30px) which bounds the flex chain.
       .sidebar-expanded-content must NOT use overflow:hidden — that clips the deck
       rows whose negative margins extend into the sidebar's padding area. */
    .sidebar-expanded-content {
        display: flex;
        flex-direction: column;
        flex: 1;
        min-height: 0;
        background-color: transparent !important;
        opacity: 1;
        visibility: visible;
        transition: opacity 0.1s cubic-bezier(0.4, 0, 0.2, 1), visibility 0.1s cubic-bezier(0.4, 0, 0.2, 1);
    }

    #deck-list-container {
        flex: 1;
        overflow-y: auto;
        overflow-x: hidden;
        min-height: 0;
        /* Pull container rightward so the scrollbar sits ~1px from sidebar border.
           Sidebar padding-right = 25px. We extend 24px: right edge = 25-24 = 1px from
           padding-box boundary (where overflow:hidden clips). Scrollbar (5px) at 1-6px. */
        margin-right: -24px;
        padding-right: 4px;
        /* Lift the scrollbar track bottom ~6px above the sidebar's bottom border so
           the thumb never overlaps the 15px border-radius curve at the corner. */
        margin-bottom: 6px;
        /* Dynamic top+bottom fade is applied via JS (OnigiriEngine.updateDeckFade) */
    }

    #onigiri-deck-fade { display: none; }

    /* --- Scrollbar — slim 5px thumb, 1px from right border --- */
    #deck-list-container::-webkit-scrollbar {
        width: 5px;
        background: transparent;
    }
    #deck-list-container::-webkit-scrollbar-track,
    #deck-list-container::-webkit-scrollbar-track-piece {
        background: transparent;
        border: none;
        box-shadow: none;
    }
    /* Normal state */
    #deck-list-container::-webkit-scrollbar-thumb {
        background-color: #323232;
        border-radius: 9999px;
        border: none;
        transition: background-color 0.4s ease;
    }
    /* Hover: slightly lighter */
    #deck-list-container::-webkit-scrollbar-thumb:hover {
        background-color: #484848;
        transition: background-color 0.1s ease;
    }
    #deck-list-container::-webkit-scrollbar-corner {
        background: transparent;
    }

    /* --- Onigiri Loading Overlay --- */
    #onigiri-loading-overlay {
        position: fixed;
        inset: 0;
        background: var(--canvas, var(--window-bg, var(--frame-bg, #f1f1f1)));
        z-index: 2147483647;
        display: flex;
        align-items: center;
        justify-content: center;
        pointer-events: all;
        transition: opacity 0.38s ease, visibility 0.38s ease;
    }
    #onigiri-loading-overlay.dismissed {
        opacity: 0;
        visibility: hidden;
        pointer-events: none;
    }
    @keyframes onigiri-spin {
        0%   { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .onigiri-loading-spinner {
        width: 36px;
        height: 36px;
        border: 3px solid rgba(128,128,128,0.2);
        border-top-color: var(--accent-color, #007aff);
        border-radius: 50%;
        animation: onigiri-spin 0.75s linear infinite;
        will-change: transform;
        transform-origin: center center;
        backface-visibility: hidden;
        -webkit-backface-visibility: hidden;
    }
    /* overlay_bg_color is now set via inline style from Python to match configured background */
    /* --- End Onigiri Loading Overlay --- */
</style>
<div id="onigiri-loading-overlay" style="background:{overlay_bg_color}"><div class="onigiri-loading-spinner"></div></div>
<div class="container modern-main-menu {container_extra_class}">
    <div class="sidebar-left skeleton-loading {sidebar_initial_class}" style="{sidebar_style}">
        <!-- Sidebar Toolbar (Top Left) -->
        <div class="sidebar-toolbar">
            <div class="sidebar-toggle-btn">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
            </div>
        </div>
        {ellipsis_button}
        {undo_button}
        <button id="onigiri-search-toolbar-btn" onclick="OnigiriEngine.toggleDeckSearch()" title="Filter decks" type="button">
            <i class="search-btn-icon"></i>
        </button>
        <div id="onigiri-deck-search-bar">
            <span class="onigiri-search-icon" aria-hidden="true"></span>
            <input type="text" id="onigiri-deck-search-input" placeholder="Search decks..." autocomplete="off" spellcheck="false" />
            <button id="onigiri-deck-search-close" aria-label="Close" type="button">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M18 6L6 18m12 0L6 6"/></svg>
            </button>
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
        <!-- Bottom-fade overlay — positioned entirely by JS using position:fixed -->
        <div id="onigiri-deck-fade"></div>

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
            <path d="M0 0h24v24H0z" fill="none" />
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
// Disable Anki's default jQuery sortable on the deck tree (we use our own drag-and-drop)
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

// OnigiriEditor stub — edit mode is removed; drag-and-drop is always-on via engine.js
const OnigiriEditor = {
    EDIT_MODE: false,
    SELECTED_DECKS: new Set(),
    init: function() {},
    enterEditMode: function() {},
    exitEditMode: function() {},
    reapplyEditModeState: function() {},
};

// Sync Status Manager
// _syncStatus is stored globally so that dynamically-built menus (ellipsis)
// can read it when they are created, since .action-sync may not yet exist in
// the DOM when setSyncStatus is first called.
window._onigiriSyncStatus = 'none';
const SyncStatusManager = {
    setSyncStatus: function(status) {
        window._onigiriSyncStatus = status;
        document.querySelectorAll('.action-sync').forEach(function(syncButton) {
            syncButton.classList.remove('sync-needed', 'sync-upload-needed');
            if (status === 'sync') {
                syncButton.classList.add('sync-needed');
            } else if (status === 'upload') {
                syncButton.classList.add('sync-upload-needed');
            }
        });
    },
    setSyncing: function(isSyncing) {
        document.querySelectorAll('.action-sync').forEach(function(syncButton) {
            syncButton.classList.toggle('is-syncing', isSyncing);
        });
    }
};

document.addEventListener('DOMContentLoaded', function() {
    if (typeof anki !== 'undefined' && anki.setupDeckBrowser) {
        anki.setupDeckBrowser();
    }
});

// --- Onigiri Loading Overlay Controller ---
// Multi-signal: requires BOTH engine AND (heatmap if configured) to signal
// before dismissing. Hard cap prevents hanging if a signal never arrives.
(function() {
    var overlay = document.getElementById('onigiri-loading-overlay');
    if (!overlay) return;
    var _dismissed = false;
    var _readySources = {};
    var _startTime = Date.now();
    var MIN_MS = 900;
    var MAX_MS = 4000;

    function _doDismiss() {
        if (_dismissed) return;
        var elapsed = Date.now() - _startTime;
        var delay = Math.max(0, MIN_MS - elapsed);
        setTimeout(function() {
            if (_dismissed) return;
            _dismissed = true;
            overlay.classList.add('dismissed');
            setTimeout(function() {
                if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
            }, 420);
        }, delay);
    }

    // source: 'engine' (always required) or 'heatmap' (required when heatmap data present)
    window.onigiriDismissOverlay = function(source) {
        if (source) _readySources[source] = true;

        // Engine must always signal first
        if (!_readySources['engine']) return;

        // If heatmap data was pre-injected, wait for heatmap to signal too
        var needsHeatmap = (typeof window.onigiriHeatmapData !== 'undefined'
                            && window.onigiriHeatmapData !== null);
        if (needsHeatmap && !_readySources['heatmap']) return;

        _doDismiss();
    };

    // Hard cap: always gone by MAX_MS regardless of signals
    setTimeout(_doDismiss, MAX_MS);
})();
// --- End Onigiri Loading Overlay Controller ---
</script>
"""
