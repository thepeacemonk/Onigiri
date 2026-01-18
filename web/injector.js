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

    function setupDeckFocusButton() {
        const sidebar = document.querySelector('.sidebar-left');
        if (!sidebar || document.querySelector('.deck-focus-btn')) return;

        const focusBtn = document.createElement('div');
        focusBtn.className = 'deck-focus-btn';
        focusBtn.title = 'Focus on Decks';
        focusBtn.innerHTML = `<i class="icon"></i>`;
        sidebar.appendChild(focusBtn);

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
        if (!sidebar || document.querySelector('.deck-edit-btn')) return;

        const editBtn = document.createElement('div');
        editBtn.className = 'deck-edit-btn';
        editBtn.title = 'Toggle Editing Mode';
        editBtn.innerHTML = `<i class="icon"></i>`;
        sidebar.appendChild(editBtn);

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

        let transferBtn = document.querySelector('.deck-transfer-btn');

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

            sidebar.appendChild(transferBtn);
        } else {
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
        const updateSidebarWidth = () => {
            const deltaX = lastClientX - startX;
            let newWidth = startWidth + deltaX;
            // Clamp width with early return to avoid unnecessary DOM updates
            if (newWidth < 325) newWidth = 325;
            if (newWidth > 800) newWidth = 800;

            // Use cached width comparison to avoid layout thrashing
            if (Math.abs(newWidth - lastWidth) > 0.5) {
                sidebarEl.style.width = `${newWidth}px`;
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
            startWidth = sidebarEl.offsetWidth;
            lastWidth = startWidth; // Cache initial width
            sidebarEl.classList.add('is-resizing');
            handle.classList.add('is-resizing');
            document.body.style.userSelect = 'none';
            document.body.style.cursor = 'col-resize';
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
        updateDeckLayouts(); // Initial call
        updateDeckFocusLayout(); // Add this line to handle initial state
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();