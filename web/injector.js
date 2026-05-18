// This file now only handles static UI elements like the sidebar,
// resize handle, and focus button. The high-performance deck list
// logic has been moved to engine.js.

(function () {

    // This function is now globally accessible so the engine can call it.
    window.updateDeckLayouts = function () {
        document.querySelectorAll('.deck-table .decktd').forEach(cell => {
            cell.classList.remove('is-cramped');
            if (cell.scrollWidth > cell.clientWidth) {
                cell.classList.add('is-cramped');
            }
        });
    }

    function updateDeckFocusLayout() {
        const sidebar = document.querySelector('.sidebar-left');
        const header = document.getElementById('deck-list-header');
        const expandedContent = sidebar ? sidebar.querySelector('.sidebar-expanded-content') : null;
        const deckListContainer = document.getElementById('deck-list-container');

        if (!sidebar || !header || !expandedContent || !deckListContainer) return;

        if (sidebar.classList.contains('deck-focus-mode')) {
            // If focus mode is ON, move the header to be a direct child of the sidebar
            if (header.parentElement !== sidebar) {
                sidebar.insertBefore(header, expandedContent);
            }
        } else {
            // If focus mode is OFF, move the header back to its original position
            if (header.parentElement !== expandedContent) {
                expandedContent.insertBefore(header, deckListContainer);
            }
        }
    }

    function setupSidebarToolbar() {
        const sidebar = document.querySelector('.sidebar-left');
        if (!sidebar) return;

        let toolbar = sidebar.querySelector('.sidebar-toolbar');
        if (!toolbar) {
            toolbar = document.createElement('div');
            toolbar.className = 'sidebar-toolbar';
            sidebar.appendChild(toolbar);

            // Move existing toggle button if it exists
            const toggleBtn = sidebar.querySelector('.sidebar-toggle-btn');
            if (toggleBtn) {
                toolbar.appendChild(toggleBtn);
            }
        }
        return toolbar;
    }

    function setupActionButtons() {
        // Check config
        if (typeof window.ONIGIRI_CONFIG === 'undefined') return;

        // Only show toolbar icons if mode is 'collapsed'
        if (window.ONIGIRI_CONFIG.sidebarActionsMode !== 'collapsed') {
            return;
        }

        const toolbar = setupSidebarToolbar();
        if (!toolbar) return;

        const pkg = window.ONIGIRI_CONFIG.addonPackage || '1011095603';
        const iconBase = `/_addons/${pkg}/system_files/system_icons/`;
        const userIconBase = `/_addons/${pkg}/user_files/icons/`;
        const collapsedIcons = window.ONIGIRI_CONFIG.collapsedIcons || {};

        // Map action id -> default system icon filename
        const defaultIcons = {
            'add': 'add-card.svg',
            'browse': 'browse.svg',
            'stats': 'stats.svg',
            'sync': 'sync.svg',
            'settings': 'settings.svg',
            'more': 'more.svg',
            'get_shared': 'get_shared.svg',
            'create_deck': 'add-deck.svg',
            'import_file': 'import_file.svg',
        };

        const actions = [
            { id: 'add', cmd: 'add', title: 'Add' },
            { id: 'browse', cmd: 'browse', title: 'Browser' },
            { id: 'stats', cmd: 'stats', title: 'Stats' },
            { id: 'sync', cmd: 'sync', title: 'Sync' },
            { id: 'settings', cmd: 'openOnigiriSettings', title: 'Settings' },
            { id: 'more', cmd: null, title: 'More' }
        ];

        actions.forEach(action => {
            if (toolbar.querySelector(`.action-btn.action-${action.id}`)) return;

            // Resolve icon URL: use custom collapsed icon if set, else fall back to system icon
            const customFile = collapsedIcons[action.id];
            const iconUrl = customFile
                ? `${userIconBase}${customFile}`
                : `${iconBase}${defaultIcons[action.id]}`;

            const btn = document.createElement('div');
            btn.className = `action-btn action-${action.id}`;
            btn.title = action.title;
            // Use <i> with mask-image so background-color: var(--icon-color) applies
            btn.innerHTML = `<i class="action-icon" style="mask-image: url('${iconUrl}'); -webkit-mask-image: url('${iconUrl}');"></i>`;

            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (action.id === 'more') {
                    toggleMoreMenu();
                    return;
                }
                if (typeof pycmd === 'function') {
                    pycmd(action.cmd);
                }
            });

            toolbar.appendChild(btn);

            if (action.id === 'sync' && window.ONIGIRI_SYNC_STATUS === 'sync') {
                btn.classList.add('sync-needed');
            }
        });

        setupMoreDropdown(toolbar, iconBase, userIconBase, collapsedIcons, defaultIcons);
    }

    function setupMoreDropdown(toolbar, iconBase, userIconBase, collapsedIcons, defaultIcons) {
        // Remove old dropdown if it exists
        const old = toolbar.querySelector('.more-dropdown-menu');
        if (old) old.remove();

        const moreBtn = toolbar.querySelector('.action-more');
        if (!moreBtn) return;

        // Remove any previously created inline more-items
        toolbar.querySelectorAll('.action-btn.more-item').forEach(el => el.remove());

        const items = [
            { label: 'Get Shared', id: 'get_shared', cmd: 'shared' },
            { label: 'Create Deck', id: 'create_deck', cmd: 'onigiri_create_deck' },
            { label: 'Import File', id: 'import_file', cmd: 'import' }
        ];

        // Insert the 3 inline buttons right after the More button
        let insertAfter = moreBtn;
        items.forEach(item => {
            const customFile = (collapsedIcons || {})[item.id];
            const iconUrl = customFile
                ? `${userIconBase}${customFile}`
                : `${iconBase}${(defaultIcons || {})[item.id] || item.id + '.svg'}`;

            const btn = document.createElement('div');
            btn.className = `action-btn more-item action-${item.id}`;
            btn.title = item.label;
            btn.innerHTML = `<i class="action-icon" style="mask-image: url('${iconUrl}'); -webkit-mask-image: url('${iconUrl}');"></i>`;
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (typeof pycmd === 'function') pycmd(item.cmd);
                moreBtn.classList.remove('more-expanded');
            });

            insertAfter.insertAdjacentElement('afterend', btn);
            insertAfter = btn;
        });

        // Collapse when clicking outside the toolbar
        if (!toolbar._moreOutsideHandler) {
            toolbar._moreOutsideHandler = (e) => {
                if (!toolbar.contains(e.target)) {
                    const mb = toolbar.querySelector('.action-more');
                    if (mb) mb.classList.remove('more-expanded');
                }
            };
            document.addEventListener('click', toolbar._moreOutsideHandler);
        }
    }

    function toggleMoreMenu() {
        const toolbar = document.querySelector('.sidebar-toolbar');
        if (!toolbar) return;
        const moreBtn = toolbar.querySelector('.action-more');
        if (!moreBtn) return;
        moreBtn.classList.toggle('more-expanded');
    }

    function setupDeckFocusButton() {
        const sidebar = document.querySelector('.sidebar-left');
        if (!sidebar) return;

        // Ensure toolbar exists
        const toolbar = setupSidebarToolbar();
        if (!toolbar || toolbar.querySelector('.deck-focus-btn')) return;

        const focusBtn = document.createElement('div');
        focusBtn.className = 'deck-focus-btn';
        focusBtn.title = 'Focus on Decks';
        focusBtn.innerHTML = `<i class="icon"></i>`;

        // Add to toolbar instead of sidebar directly
        toolbar.appendChild(focusBtn);

        focusBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isFocused = sidebar.classList.toggle('deck-focus-mode');
            focusBtn.classList.toggle('active', isFocused);

            updateDeckFocusLayout(); // Ensure header visibility is updated on click

            if (typeof pycmd === 'function') {
                pycmd(`saveDeckFocusState:${isFocused}`);
            }
        });

        if (sidebar.classList.contains('deck-focus-mode')) {
            focusBtn.classList.add('active');
        }
    }

    function setupResizeHandle() {
        const handle = document.querySelector('.resize-handle');
        const sidebarEl = document.querySelector('.sidebar-left');
        if (!handle || !sidebarEl || handle.dataset.onigiriSetup) return;
        handle.dataset.onigiriSetup = 'true';

        const indicator = document.createElement('div');
        indicator.className = 'resize-handle-indicator';
        handle.appendChild(indicator);

        let isResizing = false;
        let startX, startWidth, animationFrameId = null, lastClientX = 0, lastWidth = 0;
        let isCentered = false; // Track if layout is centered

        const updateSidebarWidth = () => {
            const deltaX = lastClientX - startX;
            // If centered, the sidebar grows from center, so the right edge moves at half speed relative to width change.
            // We need to double the width change to make the handle follow the mouse.
            const effectiveDelta = isCentered ? (deltaX * 2) : deltaX;

            let newWidth = startWidth + effectiveDelta;
            // Clamp width with early return to avoid unnecessary DOM updates
            if (newWidth < 325) newWidth = 325;
            // if (newWidth > 800) newWidth = 800; // Removed limit

            // Use cached width comparison to avoid layout thrashing
            if (Math.abs(newWidth - lastWidth) > 0.5) {
                // FORCE the width with !important to override any CSS specificity issues
                sidebarEl.style.setProperty('width', `${newWidth}px`, 'important');
                lastWidth = newWidth;
            }
            animationFrameId = null;
        };

        const mousemoveHandler = (e) => {
            if (isResizing) return;
            const rect = handle.getBoundingClientRect();
            const y = Math.max(0, Math.min(rect.height, e.clientY - rect.top));
            handle.style.setProperty('--handle-top', `${(y / rect.height) * 100}%`);
        };

        const mouseleaveHandler = () => {
            if (!isResizing) handle.style.setProperty('--handle-top', '50%');
        };

        const mousedownHandler = (e) => {
            if (e.button !== 0) return; // Only allow left click
            isResizing = true;
            startX = e.clientX;
            lastClientX = e.clientX;

            // Use getBoundingClientRect for sub-pixel precision
            const rect = sidebarEl.getBoundingClientRect();
            startWidth = rect.width;
            lastWidth = startWidth;

            // Check if sidebar is centered using the class added by Python backend
            // Also fallback to computed style just in case
            isCentered = sidebarEl.classList.contains('sidebar-only-mode');
            if (!isCentered && sidebarEl.parentElement) {
                const style = window.getComputedStyle(sidebarEl.parentElement);
                // Check multiple possibilities for centered alignment
                isCentered = (style.justifyContent === 'center' || style.justifyContent.includes('center'));
            }

            // Lock the current width explicitly using !important BEFORE clearing max-width
            // This prevents the visual jump if width was 'auto'
            sidebarEl.style.setProperty('width', `${startWidth}px`, 'important');

            // Ensure no max-width constraint interferes - use setProperty to clear it forcefully
            sidebarEl.style.setProperty('max-width', 'none', 'important');

            sidebarEl.classList.add('is-resizing');
            handle.classList.add('is-resizing');
            document.body.style.userSelect = 'none';
            document.body.style.cursor = 'col-resize';

            // Debug log (viewable in inspector if needed)
            console.log(`Resize Start: Width=${startWidth}, Centered=${isCentered}`);
        };

        const documentMousemoveHandler = (e) => {
            if (!isResizing) return;
            lastClientX = e.clientX;

            if (!animationFrameId) {
                animationFrameId = requestAnimationFrame(updateSidebarWidth);
            }
        };

        const documentMouseupHandler = () => {
            if (isResizing) {
                if (animationFrameId) {
                    cancelAnimationFrame(animationFrameId);
                    animationFrameId = null;
                }
                isResizing = false;
                sidebarEl.classList.remove('is-resizing');
                handle.classList.remove('is-resizing');
                document.body.style.removeProperty('user-select');
                document.body.style.removeProperty('cursor');
                const finalWidth = parseInt(sidebarEl.style.width, 10) || lastWidth;
                if (typeof pycmd === 'function') pycmd(`saveSidebarWidth:${finalWidth}`);
            }
        };

        // Store handlers for cleanup
        handle._resizeHandlers = {
            mousemove: mousemoveHandler,
            mouseleave: mouseleaveHandler,
            mousedown: mousedownHandler,
            documentMousemove: documentMousemoveHandler,
            documentMouseup: documentMouseupHandler
        };

        // Attach event listeners
        handle.addEventListener('mousemove', mousemoveHandler);
        handle.addEventListener('mouseleave', mouseleaveHandler);
        handle.addEventListener('mousedown', mousedownHandler);
        document.addEventListener('mousemove', documentMousemoveHandler);
        document.addEventListener('mouseup', documentMouseupHandler);
    }

    function refreshResizeHandle() {
        const handle = document.querySelector('.resize-handle');
        if (!handle || !handle._resizeHandlers) return;

        // Remove existing handlers
        const handlers = handle._resizeHandlers;
        handle.removeEventListener('mousemove', handlers.mousemove);
        handle.removeEventListener('mouseleave', handlers.mouseleave);
        handle.removeEventListener('mousedown', handlers.mousedown);
        document.removeEventListener('mousemove', handlers.documentMousemove);
        document.removeEventListener('mouseup', handlers.documentMouseup);

        // Remove the setup flag to allow re-setup
        delete handle.dataset.onigiriSetup;

        // Re-setup the resize handle
        setupResizeHandle();
    }

    function init() {
        const sidebar = document.querySelector('.sidebar-left.skeleton-loading');
        if (sidebar) {
            setTimeout(() => sidebar.classList.remove('skeleton-loading'), 150);
        }

        if (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.sidebarActionsMode === 'ellipsis') {
            const toolbarToggle = document.querySelector('.sidebar-toggle-btn');
            if (toolbarToggle) toolbarToggle.style.display = 'none';
        }

        const toggleBtn = document.querySelector('.sidebar-toggle-btn');
        const sidebarEl = document.querySelector('.sidebar-left');
        const revealBtn = document.getElementById('onigiri-sidebar-reveal-btn');
        let savedSidebarWidth = null;
        let sidebarTransitionTimer = null;

        function updateRevealBtn(isCollapsed) {
            if (!revealBtn) return;
            revealBtn.style.display = isCollapsed ? 'flex' : 'none';
        }

        function collapseSidebar() {
            if (!sidebarEl) return;
            window.clearTimeout(sidebarTransitionTimer);
            const inlineWidth = sidebarEl.style.width;
            const currentWidth = sidebarEl.getBoundingClientRect().width;
            if (inlineWidth) {
                savedSidebarWidth = inlineWidth;
            } else if (currentWidth > 0) {
                savedSidebarWidth = `${Math.round(currentWidth)}px`;
            }
            sidebarEl.classList.remove('sidebar-collapsed');
            sidebarEl.classList.add('sidebar-collapsing');
            sidebarEl.style.setProperty('width', `${Math.max(0, currentWidth)}px`, 'important');
            sidebarEl.style.setProperty('max-width', `${Math.max(0, currentWidth)}px`, 'important');
            updateRevealBtn(false);
            requestAnimationFrame(() => {
                sidebarEl.classList.add('sidebar-collapsed');
                sidebarEl.style.setProperty('width', '0px', 'important');
                sidebarEl.style.setProperty('max-width', '0px', 'important');
                sidebarTransitionTimer = window.setTimeout(() => {
                    sidebarEl.classList.remove('sidebar-collapsing');
                    updateRevealBtn(true);
                }, 240);
            });
            if (typeof pycmd === 'function') pycmd('saveSidebarState:true');
        }

        function expandSidebar() {
            if (!sidebarEl) return;
            window.clearTimeout(sidebarTransitionTimer);
            sidebarEl.classList.add('sidebar-expanding');
            sidebarEl.classList.remove('sidebar-collapsed');
            if (savedSidebarWidth) {
                sidebarEl.style.setProperty('width', savedSidebarWidth, 'important');
                sidebarEl.style.setProperty('max-width', savedSidebarWidth, 'important');
            } else {
                sidebarEl.style.removeProperty('width');
                sidebarEl.style.removeProperty('max-width');
            }
            updateRevealBtn(false);
            sidebarTransitionTimer = window.setTimeout(() => {
                sidebarEl.classList.remove('sidebar-expanding');
            }, 240);
            if (typeof pycmd === 'function') pycmd('saveSidebarState:false');
        }

        window.onigiriCollapseSidebar = collapseSidebar;
        window.onigiriExpandSidebar = expandSidebar;

        if (toggleBtn && sidebarEl) {
            toggleBtn.addEventListener('click', () => {
                if (sidebarEl.classList.contains('sidebar-collapsed')) {
                    expandSidebar();
                } else {
                    collapseSidebar();
                }
            });
        }

        if (revealBtn && sidebarEl) {
            updateRevealBtn(sidebarEl.classList.contains('sidebar-collapsed'));
            revealBtn.addEventListener('click', expandSidebar);
        }

        setupResizeHandle();
        setupDeckFocusButton();
        setupActionButtons(); // Initialize action buttons
        updateDeckLayouts(); // Initial call
        updateDeckFocusLayout(); // Add this line to handle initial state
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
