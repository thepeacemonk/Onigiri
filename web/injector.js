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
            'add': 'add.svg',
            'browse': 'browse.svg',
            'stats': 'stats.svg',
            'sync': 'sync.svg',
            'settings': 'settings.svg',
            'more': 'more.svg',
            'get_shared': 'get_shared.svg',
            'create_deck': 'create_deck.svg',
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

    function setupDeckEditButton() {
        const sidebar = document.querySelector('.sidebar-left');
        if (!sidebar) return;

        // Ensure toolbar exists
        const toolbar = setupSidebarToolbar();
        if (!toolbar || toolbar.querySelector('.deck-edit-btn')) return;

        const editBtn = document.createElement('div');
        editBtn.className = 'deck-edit-btn';
        editBtn.title = 'Toggle Editing Mode';
        editBtn.innerHTML = `<i class="icon"></i>`;

        // Add to toolbar instead of sidebar directly
        toolbar.appendChild(editBtn);

        editBtn.addEventListener('click', (e) => {
            e.stopPropagation();

            if (typeof OnigiriEditor !== 'undefined') {
                if (OnigiriEditor.EDIT_MODE) {
                    OnigiriEditor.exitEditMode();
                } else {
                    OnigiriEditor.enterEditMode();
                }
                // Refresh resize handle after edit mode toggle
                setTimeout(() => refreshResizeHandle(), 10);
            }
        });

        // Use a MutationObserver to keep the button's active state
        // in sync if the edit mode is changed by other means (e.g., ESC key).
        const bodyObserver = new MutationObserver((mutationsList) => {
            for (const mutation of mutationsList) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    const isEditing = document.body.classList.contains('deck-edit-mode');
                    editBtn.classList.toggle('active', isEditing);
                    // Refresh resize handle when edit mode changes
                    setTimeout(() => refreshResizeHandle(), 10);
                }
            }
        });

        bodyObserver.observe(document.body, { attributes: true });

        // Set initial state
        const isEditingInitial = document.body.classList.contains('deck-edit-mode');
        editBtn.classList.toggle('active', isEditingInitial);
    }

    function setupTransferButton() {
        const sidebar = document.querySelector('.sidebar-left');
        if (!sidebar) return;

        // Ensure toolbar exists and put the transfer button inside it
        const toolbar = setupSidebarToolbar();
        if (!toolbar) return;

        let transferBtn = toolbar.querySelector('.deck-transfer-btn');

        // If button doesn't exist, create it
        if (!transferBtn) {
            transferBtn = document.createElement('div');
            transferBtn.className = 'deck-transfer-btn';
            transferBtn.title = 'Transfer Selected Decks';

            // Create SVG icon element
            const icon = document.createElement('img');
            icon.className = 'icon';
            icon.src = '/_addons/1011095603/system_files/system_icons/airdeck.svg';
            icon.alt = 'Transfer';
            transferBtn.appendChild(icon);

            // Insert before the Focus button so it appears to its left
            const focusBtn = toolbar.querySelector('.deck-focus-btn');
            if (focusBtn) {
                toolbar.insertBefore(transferBtn, focusBtn);
            } else {
                toolbar.appendChild(transferBtn);
            }
        }

        function updateTransferButtonState() {
            const checkedBoxes = document.querySelectorAll('input[type="checkbox"]:checked');
            const hasSelection = checkedBoxes.length > 0;
            transferBtn.classList.toggle('has-selection', hasSelection);
        }

        // Remove existing click handler if any (need to check if handler exists)
        if (transferBtn._clickHandler) {
            transferBtn.removeEventListener('click', transferBtn._clickHandler);
        }

        function handleTransferClick(e) {
            e.stopPropagation();

            // Get all checked checkboxes - look for them in the deck list
            const checkedBoxes = document.querySelectorAll('input[type="checkbox"]:checked');

            if (checkedBoxes.length === 0) {
                alert('Please select decks first by checking the boxes next to them.');
                return;
            }

            // Extract deck IDs from checked checkboxes
            const selectedDids = [];

            // Try different types of checkboxes
            const allCheckedElements = [
                ...document.querySelectorAll('input[type="checkbox"]:checked'),
                ...document.querySelectorAll('[role="checkbox"][aria-checked="true"]'),
                ...document.querySelectorAll('.checkbox.checked, .checkbox[aria-checked="true"]')
            ];

            allCheckedElements.forEach((checkbox, index) => {
                // Find the deck row that contains this checkbox - try multiple selectors
                let deckRow = null;

                // Try different parent selectors
                deckRow = checkbox.closest('tr.deck');
                if (!deckRow) deckRow = checkbox.closest('tr');
                if (!deckRow) deckRow = checkbox.closest('div.deck');
                if (!deckRow) deckRow = checkbox.closest('li.deck');
                if (!deckRow) deckRow = checkbox.closest('[data-did]');

                if (deckRow && deckRow.dataset && deckRow.dataset.did) {
                    selectedDids.push(deckRow.dataset.did);
                }
            });

            if (selectedDids.length === 0) {
                alert('Could not find deck IDs for selected items. Please try selecting decks again.');
                return;
            }

            // Show the transfer window with the selected deck IDs
            if (typeof pycmd === 'function') {
                pycmd(`onigiri_show_transfer_window:${JSON.stringify(selectedDids)}`);
            } else {
                console.error('pycmd is not available');
                alert('Error: Communication with Anki failed. Please restart Anki.');
            }
        }

        function getParentChain(element) {
            const chain = [];
            let current = element;
            while (current && chain.length < 5) {
                chain.push(current.tagName + (current.className ? '.' + current.className : ''));
                current = current.parentElement;
            }
            return chain;
        }

        // Store the handler so we can remove it later if needed
        transferBtn._clickHandler = handleTransferClick;

        // Attach the click handler
        transferBtn.addEventListener('click', handleTransferClick);

        // Also add some direct styling to ensure it's clickable
        transferBtn.style.cursor = 'pointer';
        transferBtn.style.userSelect = 'none';
        transferBtn.style.zIndex = '9999'; // Ensure it's on top

        // Monitor for checkbox changes to update button state
        document.addEventListener('change', (e) => {
            if (e.target.type === 'checkbox') {
                updateTransferButtonState();
            }
        }, true);

        // Also observe mutations in case checkboxes are added dynamically
        const observer = new MutationObserver(() => {
            updateTransferButtonState();
        });
        observer.observe(document.body, { childList: true, subtree: true });

        // Initial state
        updateTransferButtonState();
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

        const toggleBtn = document.querySelector('.sidebar-toggle-btn');
        const sidebarEl = document.querySelector('.sidebar-left');

        if (toggleBtn && sidebarEl) {
            toggleBtn.addEventListener('click', () => {
                sidebarEl.classList.toggle('sidebar-collapsed');
                const isCollapsed = sidebarEl.classList.contains('sidebar-collapsed');
                if (typeof pycmd === 'function') {
                    pycmd(`saveSidebarState:${isCollapsed}`);
                }
            });
        }

        setupResizeHandle();
        setupDeckFocusButton();
        setupDeckEditButton();
        setupTransferButton();
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