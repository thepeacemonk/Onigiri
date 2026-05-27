# In templates.py

custom_body_template = """
<style>
    #deck-list-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-left: 0;
        padding-right: 10px;
        transition: opacity 0.15s ease;
    }

    /* --- Edit mode (multi-deck selection checkboxes) --- */
    body.deck-edit-mode #deck-list-container {
        border: 2px dashed var(--accent-color);
        border-radius: 15px;
        background-color: transparent !important;
    }
    body.deck-edit-mode .decktd a.deck {
        pointer-events: none !important;
        color: var(--fg-subtle) !important;
    }
    .deck-checkbox {
        margin-left: 5px;
        width: 16px;
        height: 16px;
        flex-shrink: 0;
        accent-color: var(--accent-color);
    }

    /* --- Drag & Drop Styles --- */
    tr.deck,
    td.decktd,
    .deck-info,
    .deck-info span,
    a.deck,
    a.collapse {
        -webkit-user-drag: none;
        user-drag: none;
    }
    .drag-handle {
        opacity: 0;
        cursor: grabbing !important;
        transition: opacity 0.12s ease;
        color: var(--icon-color);
        background-color: var(--icon-color);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: var(--drag-handle-icon-size, 14px);
        min-width: var(--drag-handle-icon-size, 14px);
        max-width: var(--drag-handle-icon-size, 14px);
        height: 18px;
        flex: 0 0 var(--drag-handle-icon-size, 14px);
        box-sizing: border-box;
        pointer-events: auto;
        mask-image: url("../system_files/system_icons/drag_handle.svg");
        -webkit-mask-image: url("../system_files/system_icons/drag_handle.svg");
        mask-size: contain;
        -webkit-mask-size: contain;
        mask-repeat: no-repeat;
        -webkit-mask-repeat: no-repeat;
        mask-position: center;
        -webkit-mask-position: center;
    }
    tr.deck:hover .drag-handle,
    tr.deck.is-hovered .drag-handle {
        opacity: 0.5;
    }
    tr.deck.is-dragging {
        opacity: 0.5;
        background-color: transparent !important;
    }
    /* Nest target — visual indicator is now the .dnd-nest-overlay element (JS-positioned) */
    tr.deck.drag-over-target {
        background-color: transparent !important;
    }
    /* Right-click context menu highlight — same shape as hover (whole tr row) */
    tr.deck.ctx-row-active {
        background-color: var(--edit-deck-bg) !important;
    }
    /* Multi-selection: detached accent marker + preserved row surface */
    tr.deck.is-multi-selected {
        background: transparent !important;
        background-color: transparent !important;
        box-shadow: none !important;
        isolation: isolate;
        transition: none !important;
    }
    tr.deck.is-multi-selected::before {
        content: "";
        display: block;
        position: absolute;
        left: -1px;
        top: 3px;
        bottom: 3px;
        width: 4px;
        border-radius: 999px;
        background-color: var(--accent-color, #6366f1);
        pointer-events: none;
        z-index: 2;
    }
    tr.deck.is-multi-selected::after {
        content: "";
        display: block;
        position: absolute;
        left: 6px;
        right: 0;
        top: -1px;
        bottom: -1px;
        border-radius: 8px;
        background-color: var(--hover-deck-bg);
        pointer-events: none;
        z-index: 0;
    }
    tr.deck.is-multi-selected > * {
        position: relative;
        z-index: 1;
    }
    /* Ensure right-click highlight always wins */
    tr.deck.ctx-row-active {
        background-color: var(--edit-deck-bg) !important;
        outline: none !important;
    }
    tr.deck.is-multi-selected.ctx-row-active {
        background: transparent !important;
        background-color: transparent !important;
    }
    tr.deck.is-multi-selected.ctx-row-active::after {
        left: 6px;
        background-color: var(--edit-deck-bg) !important;
    }
    /* Suppress :active pseudo-class flash while right mouse is held */
    body.ctx-right-down tr.deck:has(a.deck:active) {
        background: transparent !important;
        background-color: transparent !important;
    }
    /* Suppress hover on all other rows while context menu is open */
    body.ctx-menu-open tr.deck:not(.ctx-row-active):hover,
    body.ctx-menu-open tr.deck.is-hovered:not(.ctx-row-active) {
        background-color: transparent !important;
    }
    /* Suppress normal target-row hover while an active drag owns the interaction */
    body.is-dragging tr.deck:hover,
    body.is-dragging tr.deck.is-hovered {
        background: transparent !important;
        background-color: transparent !important;
    }
    /* Suppress hover on all other rows while dialog is open */
    body.dialog-focus tr.deck:not(.ctx-row-active):hover,
    body.dialog-focus tr.deck.is-hovered:not(.ctx-row-active) {
        background-color: transparent !important;
    }
    body.ctx-menu-open tr.deck:hover .drag-handle,
    body.ctx-menu-open tr.deck.is-hovered .drag-handle {
        opacity: 0 !important;
    }
    body.is-dragging tr.deck:hover .drag-handle,
    body.is-dragging tr.deck.is-hovered .drag-handle {
        opacity: 0 !important;
    }
    body.dialog-focus tr.deck:not(.ctx-row-active):hover .drag-handle,
    body.dialog-focus tr.deck.is-hovered:not(.ctx-row-active) .drag-handle {
        opacity: 0 !important;
    }
    /* Hide drag handle while context menu, drag, or dialog states own the row */
    tr.deck.ctx-row-active .drag-handle {
        opacity: 0 !important;
    }
    /* --- End Drag & Drop Styles --- */

    /* --- Expand / collapse row animation ---
       New rows that appear after a deck is expanded fade in with a brief
       slide-down so the list feels alive rather than popping instantly.    */
    @keyframes deckRowAppear {
        from { opacity: 0; }
        to   { opacity: 1; }
    }
    tr.deck.deck-row-appear {
        animation: deckRowAppear 0.12s cubic-bezier(0.16, 1, 0.3, 1) both;
    }
    /* Collapse: rows slide up and fade out */
    @keyframes deckRowDisappear {
        from { opacity: 1; transform: translateY(0);    }
        to   { opacity: 0; transform: translateY(-6px); }
    }
    tr.deck.deck-row-disappear {
        animation: deckRowDisappear 0.12s cubic-bezier(0.55, 0, 1, 0.45) both;
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

    /* --- Deck header controls --- */
    .sidebar-top-right-controls {
        --onigiri-sidebar-header-radius: 8px;
        position: static;
        z-index: 11;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 0;
        margin-left: auto;
    }
    .sidebar-top-right-controls > * {
        flex: 0 0 auto;
    }
    #onigiri-search-toolbar-btn,
    .sidebar-top-right-controls .deck-focus-btn,
    .onigiri-organise-toolbar-btn {
        position: relative;
        top: auto;
        right: auto;
        z-index: auto;
        background: transparent !important;
        border: none !important;
        border-radius: var(--onigiri-sidebar-header-radius, 8px) !important;
        box-shadow: none !important;
        outline: none !important;
        appearance: none !important;
        -webkit-appearance: none !important;
        cursor: pointer;
        padding: 0;
        margin: 0 !important;
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        opacity: 0.8;
        line-height: 0;
        transform: none !important;
        transition: opacity 0.15s;
    }
    #onigiri-search-toolbar-btn:hover,
    #onigiri-search-toolbar-btn:focus,
    #onigiri-search-toolbar-btn:active,
    #onigiri-search-toolbar-btn:focus-visible,
    .sidebar-top-right-controls .deck-focus-btn:hover,
    .onigiri-organise-toolbar-btn:hover,
    .onigiri-organise-toolbar-btn:focus,
    .onigiri-organise-toolbar-btn:active,
    .onigiri-organise-toolbar-btn:focus-visible {
        background: transparent !important;
        border: none !important;
        border-radius: var(--onigiri-sidebar-header-radius, 8px) !important;
        box-shadow: none !important;
        outline: none !important;
        transform: none !important;
    }
    #onigiri-search-toolbar-btn:hover,
    #onigiri-search-toolbar-btn.is-open,
    .onigiri-organise-toolbar-btn:hover,
    .onigiri-organise-toolbar-btn.is-open,
    .sidebar-top-right-controls .deck-focus-btn:hover,
    .sidebar-top-right-controls .deck-focus-btn:focus,
    .sidebar-top-right-controls .deck-focus-btn:active {
        opacity: 1;
    }
    .sidebar-left .sidebar-toolbar .ellipsis-btn,
    .sidebar-left .sidebar-toolbar .onigiri-ellipsis-toolbar-btn,
    .sidebar-left:not(.sidebar-mode-minimal) .sidebar-top-right-controls > .onigiri-ellipsis-toolbar-btn {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }
    .sidebar-left.sidebar-mode-minimal .sidebar-toolbar {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }
    .sidebar-left.sidebar-mode-minimal .sidebar-top-right-controls > .onigiri-ellipsis-toolbar-btn {
        display: flex !important;
        visibility: visible !important;
        pointer-events: auto !important;
    }
    .sidebar-left.sidebar-actions-full {
        padding-top: 15px !important;
    }
    .sidebar-left:not(.sidebar-actions-full):not(.sidebar-mode-minimal) {
        padding-top: 15px !important;
    }
    .sidebar-left:not(.deck-focus-mode) .profile-bar {
        margin-top: 0 !important;
        margin-bottom: 8px !important;
    }
    .sidebar-left.sidebar-actions-compact:not(.deck-focus-mode) .profile-bar {
        margin-top: 6px !important;
        margin-bottom: 16px !important;
    }
    .sidebar-left.sidebar-actions-full:not(.deck-focus-mode) .profile-bar {
        margin-top: 10px !important;
        margin-bottom: 15px !important;
    }
    .sidebar-left.sidebar-mode-minimal:not(.deck-focus-mode) .profile-bar {
        margin-top: 4px !important;
        margin-bottom: 10px !important;
    }
    .sidebar-left:not(.deck-focus-mode) #deck-list-header {
        margin-top: 14px;
    }
    .sidebar-left:not(.deck-focus-mode):not(.sidebar-actions-full) #deck-list-header {
        margin-top: 4px !important;
    }
    .sidebar-left.sidebar-actions-compact #deck-list-header {
        margin-top: 26px !important;
    }
    .sidebar-left.sidebar-actions-compact:not(.deck-focus-mode) #deck-list-header {
        margin-top: 40px !important;
    }
    .sidebar-left.sidebar-actions-compact.deck-focus-mode #deck-list-header {
        margin-top: 12px !important;
    }
    .sidebar-actions-full .sidebar-expanded-content > .sidebar-welcome-heading:empty,
    .sidebar-actions-compact .sidebar-expanded-content > .sidebar-welcome-heading:empty {
        display: none;
    }
    .sidebar-welcome-heading {
        margin-left: 10px;
    }
    #onigiri-search-toolbar-btn .search-btn-icon,
    .onigiri-search-icon,
    .search-close-icon,
    .sidebar-edge-toggle-icon,
    .sidebar-left .icon,
    .sidebar-toolbar .action-btn .action-icon,
    .more-dropdown-menu .menu-item .action-icon,
    .onigiri-organise-toolbar-btn i,
    .onigiri-ellipsis-toolbar-btn i {
        display: inline-block;
        background-repeat: no-repeat !important;
        background-position: center !important;
        background-size: contain !important;
        border: none !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        filter: none !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
        text-shadow: none !important;
        outline: none !important;
    }
    #onigiri-search-toolbar-btn .search-btn-icon,
    .onigiri-organise-toolbar-btn .organise-btn-icon {
        display: block;
        width: 16px;
        height: 16px;
        min-width: 16px;
        max-width: 16px;
        min-height: 16px;
        max-height: 16px;
        flex: 0 0 16px;
        mask-image: url("{system_icon_base}search.svg");
        -webkit-mask-image: url("{system_icon_base}search.svg");
        mask-size: contain;
        -webkit-mask-size: contain;
        mask-repeat: no-repeat;
        -webkit-mask-repeat: no-repeat;
        mask-position: center;
        -webkit-mask-position: center;
        background-color: rgba(0, 0, 0, 0.8);
    }
    .sidebar-top-right-controls .deck-focus-btn .icon {
        background-color: rgba(0, 0, 0, 0.8) !important;
    }
    .night-mode #onigiri-search-toolbar-btn .search-btn-icon,
    .night-mode .onigiri-organise-toolbar-btn .organise-btn-icon,
    .night-mode .sidebar-top-right-controls .deck-focus-btn .icon {
        background-color: rgba(255, 255, 255, 0.8) !important;
    }
    #onigiri-search-toolbar-btn:hover .search-btn-icon,
    #onigiri-search-toolbar-btn.is-open .search-btn-icon,
    .onigiri-organise-toolbar-btn:hover .organise-btn-icon,
    .onigiri-organise-toolbar-btn.is-open .organise-btn-icon,
    .sidebar-top-right-controls .deck-focus-btn:hover .icon,
    .sidebar-top-right-controls .deck-focus-btn:focus-visible .icon,
    .sidebar-top-right-controls .deck-focus-btn:active .icon {
        background-color: rgba(0, 0, 0, 1) !important;
    }
    .night-mode #onigiri-search-toolbar-btn:hover .search-btn-icon,
    .night-mode #onigiri-search-toolbar-btn.is-open .search-btn-icon,
    .night-mode .onigiri-organise-toolbar-btn:hover .organise-btn-icon,
    .night-mode .onigiri-organise-toolbar-btn.is-open .organise-btn-icon,
    .night-mode .sidebar-top-right-controls .deck-focus-btn:hover .icon,
    .night-mode .sidebar-top-right-controls .deck-focus-btn:focus-visible .icon,
    .night-mode .sidebar-top-right-controls .deck-focus-btn:active .icon {
        background-color: rgba(255, 255, 255, 1) !important;
    }
    .onigiri-organise-toolbar-btn .organise-btn-icon {
        mask-image: url("{system_icon_base}organise.svg");
        -webkit-mask-image: url("{system_icon_base}organise.svg");
    }
    /* --- Deck Search Bar (pill, positioned absolutely in toolbar row) --- */
    #onigiri-deck-search-bar {
        display: none;
        position: absolute;
        top: 11.5px;
        left: 30px;
        right: 48px;
        z-index: 12;
        align-items: center;
        gap: 4px;
        background: #e5e5e5;
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 6px 6px 6px 12px;
        outline: none;
        transition: none;
    }
    .night-mode #onigiri-deck-search-bar {
        background: #252525;
    }
    .sidebar-left.sidebar-mode-minimal #onigiri-deck-search-bar {
        top: 87.5px;
        right: 70px;
    }
    .sidebar-left.sidebar-mode-minimal.deck-focus-mode #onigiri-deck-search-bar {
        top: 21.5px;
    }
    .sidebar-left.deck-focus-mode:not(.sidebar-mode-minimal) #onigiri-deck-search-bar {
        top: 61.5px;
    }
    #onigiri-deck-search-bar.is-visible {
        display: flex;
        animation: oniSearchReveal 0.12s ease-out both;
    }
    #onigiri-deck-search-bar.is-closing {
        animation: oniSearchDismiss 0.09s ease-in both !important;
    }
    @keyframes oniSearchReveal {
        from {
            opacity: 0;
        }
        to {
            opacity: 1;
        }
    }
    @keyframes oniSearchDismiss {
        from {
            opacity: 1;
        }
        to {
            opacity: 0;
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
        border-color: var(--accent-color, #007aff);
        outline: none;
        box-shadow: inset 0 0 0 1px var(--accent-color, #007aff);
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
        mask-image: url("{system_icon_base}search.svg");
        -webkit-mask-image: url("{system_icon_base}search.svg");
        mask-size: contain;
        mask-repeat: no-repeat;
        mask-position: center;
        -webkit-mask-size: contain;
        -webkit-mask-repeat: no-repeat;
        -webkit-mask-position: center;
        pointer-events: none;
        margin-right: 4px;
    }
    #onigiri-deck-search-close {
        width: 14px;
        height: 14px;
        min-width: 14px;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        filter: none !important;
        outline: none !important;
        appearance: none !important;
        -webkit-appearance: none !important;
        cursor: pointer;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--fg-subtle, rgba(255,255,255,0.35));
        flex-shrink: 0;
        line-height: 0;
        margin-left: 2px;
    }
    #onigiri-deck-search-close:hover,
    #onigiri-deck-search-close:focus,
    #onigiri-deck-search-close:active,
    #onigiri-deck-search-close:focus-visible {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        filter: none !important;
        outline: none !important;
        color: var(--fg);
    }
    .search-close-icon {
        width: 14px;
        height: 14px;
        display: inline-block;
        background-color: currentColor;
        mask-image: url("{system_icon_base}cancel.svg");
        -webkit-mask-image: url("{system_icon_base}cancel.svg");
        mask-size: contain;
        mask-repeat: no-repeat;
        mask-position: center;
        -webkit-mask-size: contain;
        -webkit-mask-repeat: no-repeat;
        -webkit-mask-position: center;
        pointer-events: none;
    }
    #onigiri-sidebar-edge-toggle {
        position: fixed;
        top: 0;
        left: 0;
        z-index: 1000;
        width: 24px;
        height: 24px;
        padding: 0;
        margin: 0;
        border-radius: 50%;
        border: 1px solid var(--border);
        background: var(--canvas-overlay, var(--hover-deck-bg));
        color: var(--icon-color, var(--fg-subtle));
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        opacity: 0;
        pointer-events: none;
        transform: translate(0, 0);
        transition: opacity 0.16s ease;
    }
    #onigiri-sidebar-edge-toggle.always-visible {
        opacity: 1;
        pointer-events: auto;
        transition: none;
    }
    .sidebar-edge-toggle-zone:hover ~ #onigiri-sidebar-edge-toggle,
    #onigiri-sidebar-edge-toggle:hover,
    #onigiri-sidebar-edge-toggle:active {
        background: var(--canvas-inset);
        color: var(--fg);
        opacity: 1;
        pointer-events: auto;
        outline: none;
    }
    #onigiri-sidebar-edge-toggle.is-collapsed {
        opacity: 1;
        pointer-events: auto;
        transform: translate(0, 0);
    }
    .sidebar-edge-toggle-icon {
        width: 16px;
        height: 16px;
        display: inline-block;
        background-color: currentColor;
        mask-image: url("{system_icon_base}collapse_sidebar.svg");
        -webkit-mask-image: url("{system_icon_base}collapse_sidebar.svg");
        mask-size: contain;
        mask-repeat: no-repeat;
        mask-position: center;
        -webkit-mask-size: contain;
        -webkit-mask-repeat: no-repeat;
        -webkit-mask-position: center;
    }
    #onigiri-sidebar-edge-toggle.is-collapsed .sidebar-edge-toggle-icon {
        mask-image: url("{system_icon_base}expand_sidebar.svg");
        -webkit-mask-image: url("{system_icon_base}expand_sidebar.svg");
    }
    .sidebar-edge-toggle-zone {
        position: fixed;
        top: 0;
        left: 0;
        z-index: 999;
        width: 56px;
        height: 44px;
        pointer-events: auto;
        background: transparent;
    }
    .sidebar-edge-toggle-zone.always-visible {
        pointer-events: none;
    }
    /* --- End Deck Search Bar --- */

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
        border-radius: 10px !important;
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
        margin-right: 14px !important;
        flex-shrink: 0;
    }
    
    .sidebar-left .deck-transfer-btn .icon {
        margin: 0 !important;
    }

    /* --- Final Icon State Overrides --- */
    .sidebar-top-right-controls #onigiri-search-toolbar-btn,
    .sidebar-top-right-controls .onigiri-organise-toolbar-btn,
    .sidebar-top-right-controls .deck-focus-btn {
        opacity: 1;
    }

    .sidebar-left .deck-header-focus-btn {
        position: relative !important;
        top: auto !important;
        left: auto !important;
        z-index: auto !important;
        display: flex !important;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        background: transparent !important;
        border: none !important;
        border-radius: var(--onigiri-sidebar-header-radius, 8px) !important;
        box-shadow: none !important;
        transform: none !important;
        opacity: 0;
        pointer-events: auto;
        cursor: pointer;
        margin-left: -6px !important;
        margin-right: -2px !important;
        transition: opacity 0.15s ease !important;
    }
    .sidebar-left .deck-header-focus-btn:hover {
        background: transparent !important;
        border-color: transparent !important;
        box-shadow: none !important;
    }
    .sidebar-left #deck-list-header:hover .deck-header-focus-btn,
    .sidebar-left .deck-header-focus-btn:focus-visible,
    .sidebar-left .deck-header-focus-btn:active {
        opacity: 1;
    }
    .sidebar-left .deck-header-focus-btn .icon {
        display: block;
        width: 16px;
        height: 16px;
        margin: 0 !important;
        background-color: var(--icon-color, #888888);
        mask-size: contain;
        mask-repeat: no-repeat;
        mask-position: center;
        -webkit-mask-size: contain;
        -webkit-mask-repeat: no-repeat;
        -webkit-mask-position: center;
    }
    .sidebar-left.sidebar-actions-compact #deck-list-header:hover .deck-header-focus-btn,
    .sidebar-left.sidebar-actions-compact .deck-header-focus-btn:focus-visible,
    .sidebar-left.sidebar-actions-compact .deck-header-focus-btn:hover {
        opacity: 1;
    }
    .sidebar-left .deck-header-focus-btn:hover .icon,
    .sidebar-left .deck-header-focus-btn:focus-visible .icon,
    .sidebar-left .deck-header-focus-btn:active .icon {
        background-color: color-mix(in srgb, var(--icon-color) 20%, black 80%) !important;
        opacity: 1;
    }
    .night-mode .sidebar-left .deck-header-focus-btn:hover .icon,
    .night-mode .sidebar-left .deck-header-focus-btn:focus-visible .icon,
    .night-mode .sidebar-left .deck-header-focus-btn:active .icon {
        background-color: color-mix(in srgb, var(--icon-color) 20%, white 80%) !important;
        opacity: 1;
    }

    .sidebar-top-right-controls #onigiri-search-toolbar-btn .search-btn-icon,
    .sidebar-top-right-controls .onigiri-organise-toolbar-btn .organise-btn-icon,
    .sidebar-top-right-controls .deck-focus-btn .icon,
    .sidebar-top-right-controls .onigiri-ellipsis-toolbar-btn i {
        background-color: var(--icon-color) !important;
        opacity: 1;
        transition: background-color 0.15s ease !important;
    }

    .sidebar-top-right-controls #onigiri-search-toolbar-btn:hover .search-btn-icon,
    .sidebar-top-right-controls #onigiri-search-toolbar-btn:focus-visible .search-btn-icon,
    .sidebar-top-right-controls #onigiri-search-toolbar-btn:active .search-btn-icon,
    .sidebar-top-right-controls #onigiri-search-toolbar-btn.is-open .search-btn-icon,
    .sidebar-top-right-controls .onigiri-organise-toolbar-btn:hover .organise-btn-icon,
    .sidebar-top-right-controls .onigiri-organise-toolbar-btn:focus .organise-btn-icon,
    .sidebar-top-right-controls .onigiri-organise-toolbar-btn:active .organise-btn-icon,
    .sidebar-top-right-controls .onigiri-organise-toolbar-btn.is-open .organise-btn-icon,
    .sidebar-top-right-controls .deck-focus-btn:hover .icon,
    .sidebar-top-right-controls .deck-focus-btn:focus-visible .icon,
    .sidebar-top-right-controls .deck-focus-btn:active .icon,
    .sidebar-top-right-controls .onigiri-ellipsis-toolbar-btn:hover i,
    .sidebar-top-right-controls .onigiri-ellipsis-toolbar-btn:focus i,
    .sidebar-top-right-controls .onigiri-ellipsis-toolbar-btn:active i,
    .sidebar-top-right-controls .onigiri-ellipsis-toolbar-btn.is-open i {
        background-color: color-mix(in srgb, var(--icon-color) 20%, black 80%) !important;
        opacity: 1;
    }

    .night-mode .sidebar-top-right-controls #onigiri-search-toolbar-btn:hover .search-btn-icon,
    .night-mode .sidebar-top-right-controls #onigiri-search-toolbar-btn:focus-visible .search-btn-icon,
    .night-mode .sidebar-top-right-controls #onigiri-search-toolbar-btn:active .search-btn-icon,
    .night-mode .sidebar-top-right-controls #onigiri-search-toolbar-btn.is-open .search-btn-icon,
    .night-mode .sidebar-top-right-controls .onigiri-organise-toolbar-btn:hover .organise-btn-icon,
    .night-mode .sidebar-top-right-controls .onigiri-organise-toolbar-btn:focus .organise-btn-icon,
    .night-mode .sidebar-top-right-controls .onigiri-organise-toolbar-btn:active .organise-btn-icon,
    .night-mode .sidebar-top-right-controls .onigiri-organise-toolbar-btn.is-open .organise-btn-icon,
    .night-mode .sidebar-top-right-controls .deck-focus-btn:hover .icon,
    .night-mode .sidebar-top-right-controls .deck-focus-btn:focus-visible .icon,
    .night-mode .sidebar-top-right-controls .deck-focus-btn:active .icon,
    .night-mode .sidebar-top-right-controls .onigiri-ellipsis-toolbar-btn:hover i,
    .night-mode .sidebar-top-right-controls .onigiri-ellipsis-toolbar-btn:focus i,
    .night-mode .sidebar-top-right-controls .onigiri-ellipsis-toolbar-btn:active i,
    .night-mode .sidebar-top-right-controls .onigiri-ellipsis-toolbar-btn.is-open i {
        background-color: color-mix(in srgb, var(--icon-color) 20%, white 80%) !important;
        opacity: 1;
    }

    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .action-btn .action-icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .deck-focus-btn .icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .action-more .action-icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .ellipsis-btn svg {
        width: 16px !important;
        height: 16px !important;
        min-width: 16px !important;
        max-width: 16px !important;
        min-height: 16px !important;
        max-height: 16px !important;
        flex: 0 0 16px !important;
        background-color: var(--icon-color) !important;
        stroke: var(--icon-color) !important;
        opacity: 1;
        transition: background-color 0.15s ease, stroke 0.15s ease !important;
    }

    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .action-btn:hover .action-icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .action-btn.is-true-hover .action-icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .action-btn:focus .action-icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .action-btn:active .action-icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .action-more.more-expanded .action-icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .ellipsis-btn:hover svg,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .ellipsis-btn:focus svg,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .ellipsis-btn:active svg {
        background-color: color-mix(in srgb, var(--icon-color) 20%, black 80%) !important;
        stroke: color-mix(in srgb, var(--icon-color) 20%, black 80%) !important;
        opacity: 1;
    }

    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .action-btn:hover .action-icon,
    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .action-btn.is-true-hover .action-icon,
    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .action-btn:focus .action-icon,
    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .action-btn:active .action-icon,
    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .action-more.more-expanded .action-icon,
    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .ellipsis-btn:hover svg,
    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .ellipsis-btn:focus svg,
    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-secondary .ellipsis-btn:active svg {
        background-color: color-mix(in srgb, var(--icon-color) 20%, white 80%) !important;
        stroke: color-mix(in srgb, var(--icon-color) 20%, white 80%) !important;
        opacity: 1;
    }

    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .action-btn .action-icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .deck-focus-btn .icon {
        width: 16px !important;
        height: 16px !important;
        min-width: 16px !important;
        max-width: 16px !important;
        min-height: 16px !important;
        max-height: 16px !important;
        flex: 0 0 16px !important;
        background-color: rgba(0, 0, 0, 0.8) !important;
        opacity: 1;
    }

    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .action-btn .action-icon,
    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .deck-focus-btn .icon {
        background-color: rgba(255, 255, 255, 0.8) !important;
        opacity: 1;
    }

    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .action-btn:hover .action-icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .action-btn.is-true-hover .action-icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .action-btn:focus .action-icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .action-btn:active .action-icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .deck-focus-btn:hover .icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .deck-focus-btn:focus-visible .icon,
    .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .deck-focus-btn:active .icon {
        background-color: rgba(0, 0, 0, 1) !important;
        opacity: 1;
    }

    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .action-btn:hover .action-icon,
    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .action-btn.is-true-hover .action-icon,
    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .action-btn:focus .action-icon,
    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .action-btn:active .action-icon,
    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .deck-focus-btn:hover .icon,
    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .deck-focus-btn:focus-visible .icon,
    .night-mode .sidebar-left.sidebar-actions-compact .sidebar-toolbar .toolbar-group-primary .deck-focus-btn:active .icon {
        background-color: rgba(255, 255, 255, 1) !important;
        opacity: 1;
    }
    /* --- End Final Icon State Overrides --- */

    /* --- Deck List Click Area Fix --- */
    .deck-table .decktd {
        display: flex;
        align-items: center;
        padding: 0 8px 0 0 !important;
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
        border-radius: var(--onigiri-deck-row-radius, 8px);
        display: block;
        overflow: hidden;
        text-overflow: clip;
        white-space: nowrap;
        pointer-events: auto !important;
    }

    .deck-table tr:not(.drag-hover) a.deck:hover {
         background-color: rgba(128, 128, 128, 0.1);
    }
    body.is-dragging .deck-table tr.deck a.deck:hover,
    body.is-dragging .deck-table tr.deck.is-hovered a.deck {
        background-color: transparent !important;
    }
    /* --- Deck Alignment: collapse spacer for leaf decks ---
       span.collapse is now a flex item inside the deck-prefix span, so its
       width and margin-right are respected exactly — matching a.collapse.
       NOTE: a.collapse has position:relative (menu.css) which causes a 2px
       rendering shift in Chromium flex layout vs the plain span.collapse.
       We compensate by giving a.collapse margin-right:2px and span.collapse
       margin-right:4px — the 2px delta cancels the rendering offset. */
    .deck-table span.collapse {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        inline-size: var(--collapse-icon-size, 12px) !important;
        block-size: var(--collapse-icon-size, 12px) !important;
        width: var(--collapse-icon-size, 12px) !important;
        min-width: var(--collapse-icon-size, 12px) !important;
        max-width: var(--collapse-icon-size, 12px) !important;
        height: var(--collapse-icon-size, 12px) !important;
        min-height: var(--collapse-icon-size, 12px) !important;
        max-height: var(--collapse-icon-size, 12px) !important;
        margin-right: 2px !important;
        flex: 0 0 var(--collapse-icon-size, 12px) !important;
        box-sizing: border-box !important;
        aspect-ratio: 1 / 1 !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }
    .deck-table a.collapse {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        inline-size: var(--collapse-icon-size, 12px) !important;
        block-size: var(--collapse-icon-size, 12px) !important;
        width: var(--collapse-icon-size, 12px) !important;
        min-width: var(--collapse-icon-size, 12px) !important;
        max-width: var(--collapse-icon-size, 12px) !important;
        height: var(--collapse-icon-size, 12px) !important;
        min-height: var(--collapse-icon-size, 12px) !important;
        max-height: var(--collapse-icon-size, 12px) !important;
        flex: 0 0 var(--collapse-icon-size, 12px) !important;
        margin-right: 2px !important;
        box-sizing: border-box !important;
        position: relative !important;
        overflow: visible !important;
        transform-box: fill-box !important;
        aspect-ratio: 1 / 1 !important;
    }
    .deck-table a.collapse::after {
        content: "";
        position: absolute;
        left: 0;
        right: -10px;
        top: -3px;
        bottom: -3px;
        background: transparent;
        pointer-events: auto;
    }
    .deck-table a.collapse.is-hover-expanding {
        position: relative !important;
        overflow: visible !important;
        mask-image: none !important;
        -webkit-mask-image: none !important;
        background-color: transparent !important;
    }
    .deck-table a.collapse.is-hover-expanding .expand-spinner {
        display: block !important;
        position: absolute !important;
        inset: 0 !important;
        width: var(--collapse-icon-size, 12px) !important;
        height: var(--collapse-icon-size, 12px) !important;
        box-sizing: border-box !important;
        border: 2px solid currentColor !important;
        border-right-color: transparent !important;
        border-radius: 50% !important;
        color: var(--icon-color) !important;
        animation: oni-expand-spin 1s linear infinite !important;
        pointer-events: none !important;
    }

    /* Let the deck list extend slightly into the sidebar padding so the rows
       sit closer to the border, while keeping the visible inset mirrored. */
    #deck-list-container {
        margin-left: calc(-1 * var(--onigiri-deck-list-bleed, 8px));
    }
    #deck-list-header {
        margin-left: 0;
        padding-right: 0;
        flex-shrink: 0;
    }
    #deck-list-header h2 {
        flex: 0 0 auto;
        margin-left: 10px;
        transition: opacity 0.15s ease;
    }
    #deck-list-header h2.deck-focus-label {
        cursor: pointer;
        user-select: none;
        border-radius: 6px;
        padding: 0 2px;
        outline: none;
        transition: color 0.15s ease, opacity 0.15s ease;
    }
    #deck-list-header h2.deck-focus-label:hover,
    #deck-list-header h2.deck-focus-label:focus-visible {
        color: color-mix(in srgb, var(--fg, currentColor) 78%, var(--accent-color, #007aff) 22%);
        opacity: 1;
    }
    .deck-focus-btn,
    .deck-header-focus-btn,
    .sidebar-left .deck-focus-btn,
    .sidebar-left .deck-header-focus-btn,
    .sidebar-top-right-controls .deck-focus-btn {
        display: none !important;
        width: 0 !important;
        min-width: 0 !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        pointer-events: none !important;
    }
    .sidebar-left.sidebar-actions-full.deck-focus-mode #deck-list-header h2 {
        margin-left: 10px;
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

    .sidebar-left.sidebar-collapsed {
        flex-basis: 0 !important;
        width: 0 !important;
        min-width: 0 !important;
        max-width: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        border-color: transparent !important;
        border-width: 0 !important;
        opacity: 0 !important;
        visibility: hidden !important;
        pointer-events: none !important;
        overflow: hidden !important;
    }

    #deck-list-container {
        flex: 1;
        overflow-y: auto;
        overflow-x: hidden;
        min-height: 0;
        border-right: 1px solid transparent;
        /* Let the scrollbar reach the sidebar edge while preserving the current
           deck-row content width and horizontal position. */
        margin-right: calc(-1 * var(--onigiri-sidebar-right-pad, 18px));
        padding-right: calc(var(--onigiri-sidebar-right-pad, 18px) - var(--onigiri-deck-list-bleed, 8px));
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
        background-color: var(--highlight-bg);
        border-radius: 9999px;
        border: none;
        transition: background-color 0.4s ease;
    }
    /* Hover: slightly lighter */
    #deck-list-container::-webkit-scrollbar-thumb:hover {
        background-color: color-mix(in srgb, var(--highlight-bg) 94%, #000 6%);
        transition: background-color 0.1s ease;
    }
    .night-mode #deck-list-container::-webkit-scrollbar-thumb:hover {
        background-color: color-mix(in srgb, var(--highlight-bg) 94%, #fff 6%);
    }
    #deck-list-container::-webkit-scrollbar-corner {
        background: transparent;
    }
    @keyframes oni-expand-spin {
        from { transform: rotate(0deg); }
        to   { transform: rotate(360deg); }
    }
    /* --- Multi-select badge --- */
    #onigiri-multiselect-badge {
        appearance: none !important;
        -webkit-appearance: none !important;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: auto;
        min-width: 22px;
        height: 22px;
        min-height: 0 !important;
        border: 0 !important;
        border-radius: 999px;
        background: var(--accent-color, #007aff) !important;
        background-image: none !important;
        color: #ffffff !important;
        cursor: pointer;
        font-size: 11px;
        font-weight: 600;
        padding: 0 8px;
        margin: 0 2px;
        line-height: 1;
        font-family: inherit;
        white-space: nowrap;
        outline: none !important;
        box-shadow: none !important;
        filter: none !important;
        text-decoration: none !important;
        box-sizing: border-box;
        transition: background-color 0.12s ease, box-shadow 0.12s ease, transform 0.12s ease;
    }
    #onigiri-multiselect-badge:hover,
    #onigiri-multiselect-badge:focus-visible {
        border: 0 !important;
        background: color-mix(in srgb, var(--accent-color, #007aff) 86%, #000 14%) !important;
        background-image: none !important;
        box-shadow: none !important;
        filter: none !important;
    }
    .night-mode #onigiri-multiselect-badge:hover,
    .night-mode #onigiri-multiselect-badge:focus-visible {
        background: color-mix(in srgb, var(--accent-color, #007aff) 82%, #fff 18%) !important;
    }
    #onigiri-multiselect-badge:focus-visible {
        outline: none !important;
        box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent-color, #007aff) 32%, transparent) !important;
    }
    #onigiri-multiselect-badge:active {
        border: 0 !important;
        background-image: none !important;
        box-shadow: none !important;
        transform: translateY(1px);
    }
    #onigiri-multiselect-badge[hidden] {
        display: none !important;
    }
    #onigiri-deck-search-bar.is-visible ~ .sidebar-expanded-content #onigiri-multiselect-badge,
    #onigiri-deck-search-bar.is-closing ~ .sidebar-expanded-content #onigiri-multiselect-badge {
        display: none !important;
    }
    /* --- End Multi-select badge --- */

</style>
<div class="container modern-main-menu {container_extra_class}">
    <div class="sidebar-left {sidebar_initial_class}" style="{sidebar_style}">
        <div id="onigiri-deck-search-bar">
            <span class="onigiri-search-icon" aria-hidden="true"></span>
            <input type="text" id="onigiri-deck-search-input" placeholder="Search decks..." autocomplete="off" spellcheck="false" />
            <button id="onigiri-deck-search-close" aria-label="Close" type="button">
                <span class="search-close-icon" aria-hidden="true"></span>
            </button>
        </div>

        <div class="sidebar-expanded-content">
            <h2 class="sidebar-welcome-heading">{welcome_message}</h2>
            {sidebar_buttons}
            {compact_toolbar_html}
            <div id="deck-list-header">
                <h2 class="deck-focus-label" role="button" tabindex="0" title="Focus on Decks">DECKS</h2>
                <div class="sidebar-top-right-controls">
                    <button id="onigiri-search-toolbar-btn" onclick="OnigiriEngine.toggleDeckSearch()" title="Filter decks" type="button">
                        <i class="search-btn-icon"></i>
                    </button>
                    {organise_button}
                    {ellipsis_button}
                    {undo_button}
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
        <!-- Bottom-fade overlay — positioned entirely by JS using position:fixed -->
        <div id="onigiri-deck-fade"></div>

    </div>
    <div class="sidebar-edge-toggle-zone {sidebar_edge_toggle_zone_class}" style="{sidebar_edge_toggle_zone_style}" aria-hidden="true"></div>
    <button id="onigiri-sidebar-edge-toggle" class="{sidebar_edge_toggle_class}" style="{sidebar_edge_toggle_style}" title="Collapse sidebar" aria-label="Collapse sidebar" type="button">
        <span class="sidebar-edge-toggle-icon" aria-hidden="true"></span>
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

const OnigiriEditor = {
    EDIT_MODE: false,
    SELECTED_DECKS: new Set(),

    init: function() {
        try {
            const savedEditMode = sessionStorage.getItem('onigiri_edit_mode');
            const savedSelectedDecks = sessionStorage.getItem('onigiri_selected_decks');
            if (savedEditMode === 'true') {
                if (savedSelectedDecks) {
                    this.SELECTED_DECKS = new Set(JSON.parse(savedSelectedDecks));
                }
                this.enterEditMode();
            }
        } catch (e) {
            console.warn('Onigiri: failed to restore edit mode state', e);
        }

        const deckTreeBody = document.querySelector('#decktree > tbody');
        if (deckTreeBody) {
            const observer = new MutationObserver(() => {
                if (this.EDIT_MODE) {
                    setTimeout(() => this.reapplyEditModeState(), 50);
                }
            });
            observer.observe(deckTreeBody, { childList: true });
        }
    },

    enterEditMode: function() {
        if (this.EDIT_MODE) return;
        this.EDIT_MODE = true;
        document.body.classList.add('deck-edit-mode');
        this.reapplyEditModeState();
        try {
            sessionStorage.setItem('onigiri_edit_mode', 'true');
        } catch (e) {}
    },

    exitEditMode: function() {
        if (!this.EDIT_MODE) return;
        this.EDIT_MODE = false;
        document.body.classList.remove('deck-edit-mode');
        document.querySelectorAll('.deck-checkbox').forEach(cb => cb.remove());
        this.SELECTED_DECKS.clear();
        try {
            sessionStorage.removeItem('onigiri_edit_mode');
            sessionStorage.removeItem('onigiri_selected_decks');
        } catch (e) {}
    },

    reapplyEditModeState: function() {
        if (!this.EDIT_MODE) return;
        document.querySelectorAll('#decktree tr.deck').forEach(row => {
            const did = row.dataset.did || row.id;
            if (!did || row.querySelector('.deck-checkbox')) return;

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'deck-checkbox';
            checkbox.dataset.did = did;
            checkbox.checked = this.SELECTED_DECKS.has(did);

            checkbox.addEventListener('click', (e) => {
                e.stopPropagation();
                if (e.target.checked) {
                    this.SELECTED_DECKS.add(did);
                } else {
                    this.SELECTED_DECKS.delete(did);
                }
                try {
                    sessionStorage.setItem(
                        'onigiri_selected_decks',
                        JSON.stringify(Array.from(this.SELECTED_DECKS))
                    );
                } catch (err) {}
            });

            const decktd = row.querySelector('.decktd');
            if (decktd) {
                decktd.prepend(checkbox);
            }
        });
    },
};

// Sync Status Manager
// _syncStatus is stored globally so that dynamically-built menus (ellipsis)
// can read it when they are created, since .action-sync may not yet exist in
// the DOM when setSyncStatus is first called.
window._onigiriSyncStatus = window.ONIGIRI_SYNC_STATUS || 'none';
window.getOnigiriSyncStatus = function() {
    return window._onigiriSyncStatus || 'none';
};

function applySyncStatusClasses(syncButton, status) {
    syncButton.classList.remove('sync-needed', 'sync-upload-needed');
    if (status === 'sync') {
        syncButton.classList.add('sync-needed');
    } else if (status === 'upload') {
        syncButton.classList.add('sync-upload-needed');
    }
}

const SyncStatusManager = {
    setSyncStatus: function(status) {
        window._onigiriSyncStatus = status;
        document.querySelectorAll('.action-sync').forEach(function(syncButton) {
            applySyncStatusClasses(syncButton, status);
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
    OnigiriEditor.init();

    // More section: expand/collapse with slide + fade (matches deck-row timing exactly)
    (function() {
        var DUR   = 120;
        var T_IN  = 'max-height ' + DUR + 'ms cubic-bezier(0.16,1,0.3,1), opacity ' + DUR + 'ms cubic-bezier(0.16,1,0.3,1)';
        var T_OUT = 'max-height ' + DUR + 'ms cubic-bezier(0.55,0,1,0.45), opacity ' + DUR + 'ms cubic-bezier(0.55,0,1,0.45)';

        document.querySelectorAll('details.menu-group').forEach(function(det) {
            var summary = det.querySelector('summary');
            var items   = det.querySelector('.menu-group-items');
            if (!summary || !items || det._moreAnimInit) return;
            det._moreAnimInit = true;

            function clearStyles() {
                items.style.transition = '';
                items.style.maxHeight  = '';
                items.style.opacity    = '';
            }

            summary.addEventListener('click', function(e) {
                e.preventDefault();

                if (det.open) {
                    // Collapse: lock at current height, animate to 0, then remove [open]
                    items.style.transition = 'none';
                    items.style.maxHeight  = items.scrollHeight + 'px';
                    items.style.opacity    = '1';
                    void items.offsetHeight;
                    requestAnimationFrame(function() {
                        items.style.transition = T_OUT;
                        items.style.maxHeight  = '0px';
                        items.style.opacity    = '0';
                        setTimeout(function() {
                            det.open = false;
                            clearStyles();
                        }, DUR + 15);
                    });

                } else {
                    // Expand: suppress [open] CSS flash, then animate from 0 to full height
                    items.style.transition = 'none';
                    items.style.maxHeight  = '0px';
                    items.style.opacity    = '0';
                    det.open = true;
                    var fullH = items.scrollHeight || 120;
                    void items.offsetHeight;
                    requestAnimationFrame(function() {
                        items.style.transition = T_IN;
                        items.style.maxHeight  = fullH + 'px';
                        items.style.opacity    = '1';
                        setTimeout(clearStyles, DUR + 15);
                    });
                }
            });
        });
    })();
});

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && OnigiriEditor.EDIT_MODE) {
        OnigiriEditor.exitEditMode();
    }
});

// --- Startup Overlay Controller ---
// No post-startup loading UI is shown. This bridge only dismisses the native
// startup overlay once the first deck-browser render is ready.
(function() {
    var _dismissed = false;
    var _readySources = {};

    function _doDismiss() {
        if (_dismissed) return;
        _dismissed = true;
        try { pycmd('onigiri_dismiss_qt_overlay'); } catch(e) {}
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

    // Startup safety cap: this only affects the native startup overlay.
    setTimeout(_doDismiss, 1200);
})();
// --- End Startup Overlay Controller ---
</script>
"""
