// Onigiri Performance Engine

window.OnigiriEngine = {
    currentHoveredRow: null,
    _dnd: null,
    _searchDebounceTimer: null,

    init: function () {
        this.deckListContainer = document.getElementById('deck-list-container');
        if (!this.deckListContainer) {
            return;
        }

        this.bindEvents();
        this.bindDeckSearchControls();
        this.observeMutations();

        // Initial processing of already loaded nodes
        this.processNewNodes(document.querySelectorAll('tr.deck, a.collapse'));
        this.restoreScrollPosition();
    },

    /**
     * Replaces the deck tree's HTML content without a full page reload,
     * preserving scroll position.
     * @param {string} newHtml The new HTML for the deck tree's <tbody>.
     */
    updateDeckTree: function (newHtml) {
        if (!this.deckListContainer) return;

        const tableBody = this.deckListContainer.querySelector('table.deck-table tbody');
        if (!tableBody) return;

        this.deckListContainer.classList.add('scroll-restoring');

        const previousIds = new Set(
            Array.from(tableBody.querySelectorAll('tr.deck[data-did]')).map(row => row.dataset.did)
        );
        tableBody.innerHTML = newHtml;

        tableBody.querySelectorAll('tr.deck[data-did]').forEach((row) => {
            if (!previousIds.has(row.dataset.did)) {
                row.classList.add('deck-row-appear');
                row.addEventListener('animationend', () => row.classList.remove('deck-row-appear'), { once: true });
            }
        });

        this.restoreScrollPosition();
        this.processNewNodes(tableBody.children); // Process new nodes (for collapse icons etc.)

        if (typeof window.updateDeckLayouts === 'function') {
            window.updateDeckLayouts();
        }

        setTimeout(() => {
            this.deckListContainer.classList.remove('scroll-restoring');
        }, 50);
    },

    /** Saves the current scroll position to session storage. */
    saveScrollPosition: function () {
        if (this.deckListContainer) {
            sessionStorage.setItem('deckListScrollTop', this.deckListContainer.scrollTop);
        }
    },

    bindDeckSearchControls: function () {
        const searchInput = document.getElementById('onigiri-deck-search-input');
        if (searchInput && !searchInput.dataset.searchBound) {
            searchInput.dataset.searchBound = 'true';
            searchInput.addEventListener('input', (event) => this._filterDecks(event.target.value));
            searchInput.addEventListener('keydown', (event) => {
                if (event.key === 'Escape') {
                    this._closeDeckSearch();
                }
            });
        }

        const searchClose = document.getElementById('onigiri-deck-search-close');
        if (searchClose && !searchClose.dataset.searchBound) {
            searchClose.dataset.searchBound = 'true';
            searchClose.addEventListener('click', () => this._closeDeckSearch());
        }
    },

    toggleDeckSearch: function () {
        const bar = document.getElementById('onigiri-deck-search-bar');
        const input = document.getElementById('onigiri-deck-search-input');
        if (!bar || !input) return;

        if (bar.classList.contains('is-visible')) {
            this._closeDeckSearch();
            return;
        }

        bar.classList.remove('is-closing');
        bar.classList.add('is-visible');
        input.value = '';
        requestAnimationFrame(() => {
            try {
                input.focus({ preventScroll: true });
            } catch (error) {
                input.focus();
            }
        });
    },

    _closeDeckSearch: function () {
        const bar = document.getElementById('onigiri-deck-search-bar');
        const input = document.getElementById('onigiri-deck-search-input');
        if (!bar || !input) return;

        window.clearTimeout(this._searchDebounceTimer);
        this._searchDebounceTimer = null;
        input.value = '';
        this.saveScrollPosition();
        this._filterDecks('');
        bar.classList.add('is-closing');
        window.setTimeout(() => {
            bar.classList.remove('is-visible', 'is-closing');
        }, 110);
    },

    _filterDecks: function (query) {
        const nextQuery = (query || '').trim();
        window.clearTimeout(this._searchDebounceTimer);
        this._searchDebounceTimer = window.setTimeout(() => {
            pycmd('onigiri_deck_search:' + nextQuery);
        }, 150);
    },

    /** Restores the scroll position from session storage. */
    restoreScrollPosition: function () {
        const savedScroll = sessionStorage.getItem('deckListScrollTop');
        if (savedScroll !== null && this.deckListContainer) {
            this.deckListContainer.scrollTop = parseInt(savedScroll, 10);
        }
    },

    /** Binds event listeners to handle interactions. */
    bindEvents: function () {
        if (this.deckListContainer.dataset.engineBound) return;
        this.deckListContainer.dataset.engineBound = 'true';

        // --- Listener: Keep row hovered while mouse is over it ---
        this.deckListContainer.addEventListener('mouseenter', (event) => {
            const deckRow = event.target.closest('tr.deck');
            if (deckRow) {
                this.currentHoveredRow = deckRow;
                deckRow.classList.add('is-hovered');
            }
        }, true);

        this.deckListContainer.addEventListener('mouseleave', (event) => {
            const deckRow = event.target.closest('tr.deck');
            if (deckRow && deckRow === this.currentHoveredRow) {
                deckRow.classList.remove('is-hovered');
                this.currentHoveredRow = null;
            }
        }, true);

        // --- Unified Click Handler for Deck List ---
        // This single listener handles both deck collapse and double-click-to-study.
        let clickTimer = null;
        this.deckListContainer.addEventListener('click', (event) => {
            const target = event.target;

            // Case 1: Click was on a collapse icon.
            // We save the scroll position and then simply let the event proceed.
            // The `onclick` attribute on the <a> tag will handle the pycmd call.
            // We must NOT call event.preventDefault() or return, as that would
            // block the pycmd from firing.
            const collapseLink = target.closest('a.collapse');
            if (collapseLink) {
                this.saveScrollPosition();
                // Allow the default action (onclick attribute) to happen.
                return;
            }

            // Case 2: Click was on the options/gear icon. Ignore it.
            if (target.closest('.opts')) {
                return;
            }

            if (target.closest('.drag-handle')) return;

            // Case 4: Click was on the deck row itself. Handle double-click to study.
            // This part of the listener will only be reached if the click was NOT on a collapse icon
            // AND not on the favorite star.
            const deckRow = target.closest('tr.deck');
            if (!deckRow) return;

            // Prevent the default link navigation, as we are managing it with a timer.
            event.preventDefault();

            if (!clickTimer) {
                // First click, start timer.
                clickTimer = setTimeout(() => { clickTimer = null; }, 300);
            } else {
                // Second click, fire study action and clear timer.
                clearTimeout(clickTimer);
                clickTimer = null;
                const mainLink = deckRow.querySelector('a.deck');
                if (mainLink) mainLink.click();
            }
        });

        // --- Quick deck context menu ---
        this.deckListContainer.addEventListener('contextmenu', (event) => {
            const deckRow = event.target.closest('tr.deck[data-did]');
            if (!deckRow) return;
            event.preventDefault();
            event.stopPropagation();
            this.showDeckContextMenu(event.clientX, event.clientY, deckRow.dataset.did);
        });

        this._boundDndMove = (event) => this._dndMove(event);
        this._boundDndEnd = (event) => this._dndEnd(event);
    },

    _dndCreateGhost: function (row) {
        const rect = row.getBoundingClientRect();
        const cell = row.querySelector('td.decktd');
        const preview = document.createElement('div');
        const typeClasses = Array.from(row.classList).filter(cls => cls.indexOf('is-') === 0);
        preview.className = ['onigiri-drag-preview', ...typeClasses].join(' ');
        if (row.dataset.did) preview.dataset.did = row.dataset.did;
        preview.style.cssText = [
            'position:fixed',
            'z-index:9998',
            'pointer-events:none',
            `width:${Math.min(Math.max(rect.width, 260), 520)}px`,
            `top:${rect.top}px`,
            `left:${rect.left}px`,
        ].join(';');
        preview.innerHTML = cell ? cell.innerHTML : row.textContent;
        preview.querySelectorAll('[onclick], a[href]').forEach((el) => {
            el.removeAttribute('onclick');
            el.removeAttribute('href');
        });
        preview.querySelectorAll('.drag-handle').forEach(handle => handle.remove());
        return preview;
    },

    _dndStart: function (event, handle) {
        const row = handle.closest('tr.deck[data-did]');
        if (!row || this._dnd) return;
        event.preventDefault();
        event.stopPropagation();
        if (handle.setPointerCapture && event.pointerId !== undefined) {
            try {
                handle.setPointerCapture(event.pointerId);
            } catch (error) {
                // QtWebEngine can reject capture during synthetic pointer sequences.
            }
        }

        const rect = row.getBoundingClientRect();
        row.classList.add('is-dragging');
        document.body.classList.add('onigiri-is-dragging');
        const ghost = this._dndCreateGhost(row);
        document.body.appendChild(ghost);

        this._dnd = {
            sourceRow: row,
            ghostEl: ghost,
            offsetX: Math.max(18, Math.min(event.clientX - rect.left, rect.width - 18)),
            offsetY: event.clientY - rect.top,
            lastClientY: event.clientY,
            lastTargetRow: null,
            lastInsertType: null,
            placeholder: null,
            handle,
            pointerId: event.pointerId,
        };

        this._autoScrollRaf = requestAnimationFrame(() => this._dndAutoScroll());
        document.addEventListener('pointermove', this._boundDndMove, { passive: false });
        document.addEventListener('pointerup', this._boundDndEnd);
        document.addEventListener('pointercancel', this._boundDndEnd);
        window.addEventListener('pointermove', this._boundDndMove, { passive: false });
        window.addEventListener('pointerup', this._boundDndEnd);
        window.addEventListener('pointercancel', this._boundDndEnd);
    },

    _dndAutoScroll: function () {
        if (!this._dnd || !this.deckListContainer) return;
        const rect = this.deckListContainer.getBoundingClientRect();
        const y = this._dnd.lastClientY;
        const zone = 48;
        const maxSpeed = 12;
        if (y >= rect.top && y - rect.top < zone) {
            this.deckListContainer.scrollTop -= Math.ceil(maxSpeed * (1 - (y - rect.top) / zone));
        } else if (y <= rect.bottom && rect.bottom - y < zone) {
            this.deckListContainer.scrollTop += Math.ceil(maxSpeed * (1 - (rect.bottom - y) / zone));
        }
        this._autoScrollRaf = requestAnimationFrame(() => this._dndAutoScroll());
    },

    _dndMove: function (event) {
        if (!this._dnd) return;
        event.preventDefault();

        const state = this._dnd;
        state.lastClientY = event.clientY;
        state.ghostEl.style.top = `${event.clientY - state.offsetY}px`;
        state.ghostEl.style.left = `${event.clientX - state.offsetX}px`;

        const rows = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'))
            .filter(row => row !== state.sourceRow);
        let targetRow = null;
        for (const row of rows) {
            const rect = row.getBoundingClientRect();
            if (event.clientY >= rect.top && event.clientY <= rect.bottom) {
                targetRow = row;
                break;
            }
        }
        if (!targetRow && rows.length) {
            if (event.clientY < rows[0].getBoundingClientRect().top) {
                targetRow = rows[0];
            } else if (event.clientY > rows[rows.length - 1].getBoundingClientRect().bottom) {
                targetRow = rows[rows.length - 1];
            }
        }

        let insertType = null;
        if (targetRow) {
            const rect = targetRow.getBoundingClientRect();
            const pct = (event.clientY - rect.top) / Math.max(1, rect.height);
            insertType = pct < 0.22 ? 'before' : (pct > 0.78 ? 'after' : 'nest');
        }

        if (targetRow === state.lastTargetRow && insertType === state.lastInsertType) return;

        if (state.lastTargetRow) {
            state.lastTargetRow.classList.remove('drag-over-target', 'drop-before', 'drop-after');
        }
        if (state.placeholder) {
            state.placeholder.remove();
            state.placeholder = null;
        }
        state.lastTargetRow = targetRow;
        state.lastInsertType = insertType;
        if (!targetRow) return;

        if (insertType === 'nest') {
            targetRow.classList.add('drag-over-target');
            return;
        }

        targetRow.classList.add(insertType === 'before' ? 'drop-before' : 'drop-after');
        const targetRect = targetRow.getBoundingClientRect();
        const top = insertType === 'before' ? targetRect.top - 2 : targetRect.bottom - 2;
        state.placeholder = this._dndMakePlaceholder(top);
    },

    _dndMakePlaceholder: function (top) {
        const rect = this.deckListContainer.getBoundingClientRect();
        const line = document.createElement('div');
        line.className = 'dnd-placeholder';
        line.style.cssText = [
            'position:fixed',
            `left:${rect.left + 12}px`,
            `width:${Math.max(20, rect.width - 24)}px`,
            `top:${top}px`,
            'height:4px',
            'border-radius:2px',
            'background:var(--accent-color,#6366f1)',
            'pointer-events:none',
            'z-index:9997',
        ].join(';');
        document.body.appendChild(line);
        return line;
    },

    _dndEnd: function () {
        if (!this._dnd) return;
        const state = this._dnd;
        if (this._autoScrollRaf) {
            cancelAnimationFrame(this._autoScrollRaf);
            this._autoScrollRaf = null;
        }

        state.ghostEl.remove();
        document.body.classList.remove('onigiri-is-dragging');
        state.sourceRow.classList.remove('is-dragging');
        if (state.placeholder) state.placeholder.remove();
        this.deckListContainer.querySelectorAll('.drag-over-target, .drop-before, .drop-after')
            .forEach(row => row.classList.remove('drag-over-target', 'drop-before', 'drop-after'));
        document.removeEventListener('pointermove', this._boundDndMove);
        document.removeEventListener('pointerup', this._boundDndEnd);
        document.removeEventListener('pointercancel', this._boundDndEnd);
        window.removeEventListener('pointermove', this._boundDndMove);
        window.removeEventListener('pointerup', this._boundDndEnd);
        window.removeEventListener('pointercancel', this._boundDndEnd);
        if (state.handle && state.handle.releasePointerCapture && state.pointerId !== undefined) {
            try {
                state.handle.releasePointerCapture(state.pointerId);
            } catch (error) {
                // Capture may already be released by the browser.
            }
        }
        this._dnd = null;

        const targetRow = state.lastTargetRow;
        if (!targetRow || targetRow === state.sourceRow) return;

        const sourceDid = state.sourceRow.dataset.did;
        const targetDid = targetRow.dataset.did;
        if (!sourceDid || !targetDid) return;

        if (state.lastInsertType === 'nest') {
            pycmd('onigiri_drag_drop:' + JSON.stringify({ source_did: sourceDid, target_did: targetDid, type: 'nest' }));
            return;
        }

        const allIds = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'))
            .map(row => row.dataset.did);
        const newOrder = allIds.filter(id => id !== sourceDid);
        const targetIndex = newOrder.indexOf(targetDid);
        if (targetIndex === -1) return;
        newOrder.splice(state.lastInsertType === 'before' ? targetIndex : targetIndex + 1, 0, sourceDid);
        pycmd('onigiri_drag_drop:' + JSON.stringify({
            source_did: sourceDid,
            target_did: targetDid,
            type: state.lastInsertType,
            new_order: newOrder,
        }));
    },

    /** Watches for changes in the deck list and processes ONLY new elements. */
    observeMutations: function () {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach(mutation => {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    this.processNewNodes(mutation.addedNodes);
                }
            });
            if (typeof window.updateDeckLayouts === 'function') {
                window.updateDeckLayouts();
            }
        });

        observer.observe(this.deckListContainer, {
            childList: true,
            subtree: true,
        });
    },

    /** Processes a list of new nodes, classifying icons and adding styles. */
    processNewNodes: function (nodes) {
        nodes.forEach(node => {
            if (node.nodeType !== Node.ELEMENT_NODE) return;

            const elementsToProcess = [];
            if (node.matches('a.collapse, tr.deck')) {
                elementsToProcess.push(node);
            }
            elementsToProcess.push(...node.querySelectorAll('a.collapse, tr.deck'));

            elementsToProcess.forEach(el => {
                if (el.matches('a.collapse')) {
                    this.classifyCollapseIcon(el);
                } else if (el.matches('tr.deck')) {
                    el.draggable = false;
                    el.setAttribute('draggable', 'false');
                    const clickableCell = el.querySelector('td.decktd');
                    if (clickableCell) clickableCell.style.cursor = 'pointer';
                    el.querySelectorAll('a, img').forEach(child => {
                        child.draggable = false;
                        child.setAttribute('draggable', 'false');
                    });
                    if (clickableCell && !el.querySelector('.drag-handle')) {
                        const handle = document.createElement('span');
                        handle.className = 'drag-handle';
                        handle.title = 'Drag to reorder or move';
                        handle.innerHTML = '<svg viewBox="0 0 48 48" width="12" height="12" fill="currentColor" aria-hidden="true"><circle cx="16" cy="12" r="4"/><circle cx="32" cy="12" r="4"/><circle cx="16" cy="24" r="4"/><circle cx="32" cy="24" r="4"/><circle cx="16" cy="36" r="4"/><circle cx="32" cy="36" r="4"/></svg>';
                        handle.style.touchAction = 'none';
                        handle.addEventListener('pointerdown', (event) => {
                            if (event.pointerType === 'mouse' && event.button !== 0) return;
                            this._dndStart(event, handle);
                        });
                        handle.addEventListener('click', event => event.stopPropagation());
                        clickableCell.prepend(handle);
                    }
                }
            });
        });
    },

    iconUrl: function (name) {
        const pkg = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.addonPackage) || '';
        return pkg ? `/_addons/${pkg}/system_files/system_icons/${name}.svg` : '';
    },

    closeQuickMenus: function () {
        document.querySelectorAll('.onigiri-quick-menu').forEach(menu => menu.remove());
        document.querySelectorAll('tr.deck.ctx-row-active').forEach(row => row.classList.remove('ctx-row-active'));
        document.body.classList.remove('ctx-menu-open');
    },

    makeMenuIcon: function (name) {
        const icon = document.createElement('span');
        icon.className = 'quick-menu-icon';
        const url = this.iconUrl(name);
        if (url) {
            icon.style.maskImage = `url("${url}")`;
            icon.style.webkitMaskImage = `url("${url}")`;
        }
        return icon;
    },

    makeMenuDot: function (color) {
        const icon = document.createElement('span');
        icon.className = 'quick-menu-color-dot';
        icon.style.backgroundColor = color;
        return icon;
    },

    findDeckRow: function (did) {
        return Array.from(document.querySelectorAll('tr.deck[data-did]'))
            .find(row => row.dataset.did === String(did));
    },

    appendMenuItem: function (menu, item) {
        const row = document.createElement('div');
        row.className = 'quick-menu-item' + (item.danger ? ' danger' : '');
        row.appendChild(item.color ? this.makeMenuDot(item.color) : this.makeMenuIcon(item.icon));
        const label = document.createElement('span');
        label.textContent = item.label;
        row.appendChild(label);
        if (item.selected) {
            const check = document.createElement('span');
            check.className = 'quick-menu-check';
            check.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4 4L19 7" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
            row.appendChild(check);
        }
        row.addEventListener('click', () => {
            this.closeQuickMenus();
            if (item.command) pycmd(item.command);
        });
        menu.appendChild(row);
    },

    appendMenuGroup: function (menu, group) {
        const row = document.createElement('div');
        row.className = 'quick-menu-item quick-menu-group';
        row.appendChild(this.makeMenuIcon(group.icon));

        const label = document.createElement('span');
        label.textContent = group.label;
        row.appendChild(label);

        const arrow = document.createElement('span');
        arrow.className = 'quick-menu-arrow';
        arrow.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        row.appendChild(arrow);

        const submenu = document.createElement('div');
        submenu.className = 'onigiri-quick-menu quick-menu-submenu';
        group.items.forEach(item => this.appendMenuItem(submenu, item));
        row.appendChild(submenu);
        menu.appendChild(row);
    },

    positionMenu: function (menu, x, y) {
        menu.style.left = `${x}px`;
        menu.style.top = `${y}px`;
        document.body.appendChild(menu);
        requestAnimationFrame(() => {
            const rect = menu.getBoundingClientRect();
            if (rect.right > window.innerWidth) {
                menu.style.left = `${Math.max(6, x - rect.width)}px`;
            }
            if (rect.bottom > window.innerHeight) {
                menu.style.top = `${Math.max(6, y - rect.height)}px`;
            }
        });
        setTimeout(() => {
            const dismiss = (event) => {
                if (event.type === 'keydown' && event.key !== 'Escape') return;
                this.closeQuickMenus();
                document.removeEventListener('click', dismiss);
                document.removeEventListener('keydown', dismiss);
                window.removeEventListener('blur', dismiss);
            };
            document.addEventListener('click', dismiss);
            document.addEventListener('keydown', dismiss);
            window.addEventListener('blur', dismiss);
        }, 0);
    },

    showDeckContextMenu: function (x, y, did) {
        this.closeQuickMenus();
        const row = this.findDeckRow(did);
        if (row) row.classList.add('ctx-row-active');
        document.body.classList.add('ctx-menu-open');
        const isFavorite = !!(row && row.dataset.isFav === '1');
        const currentMark = row ? row.dataset.mark : '';

        const menu = document.createElement('div');
        menu.className = 'onigiri-quick-menu';

        [
            { label: 'Rename', icon: 'rename', command: `onigiri_ctx_rename:${did}` },
            { label: 'Add Subdeck', icon: 'subdeck', command: `onigiri_ctx_subdeck:${did}` },
            { label: 'Change Icon', icon: 'edit_icon', command: `onigiri_ctx_change_icon:${did}` },
            {
                label: isFavorite ? 'Remove Favorite' : 'Favorite',
                icon: isFavorite ? 'star_filled' : 'star_outline',
                command: `onigiri_toggle_favorite:${did}`,
            },
        ].forEach(item => this.appendMenuItem(menu, item));

        menu.appendChild(document.createElement('hr'));

        this.appendMenuGroup(menu, {
            label: 'Markers',
            icon: 'mark_circle',
            items: [
                { label: 'Red', color: '#ff4d4f', selected: currentMark === 'red', command: `onigiri_ctx_mark:${did}:red` },
                { label: 'Blue', color: '#4f95ff', selected: currentMark === 'blue', command: `onigiri_ctx_mark:${did}:blue` },
                { label: 'Green', color: '#45c878', selected: currentMark === 'green', command: `onigiri_ctx_mark:${did}:green` },
                { label: 'Yellow', color: '#ffc629', selected: currentMark === 'yellow', command: `onigiri_ctx_mark:${did}:yellow` },
            ],
        });

        if (currentMark) {
            this.appendMenuItem(menu, { label: 'Remove Marker', icon: 'remove_mark', command: `onigiri_ctx_mark:${did}:none` });
        }

        menu.appendChild(document.createElement('hr'));

        [
            { label: 'Deck Options', icon: 'options', command: `onigiri_ctx_options:${did}` },
            { label: 'Export Deck', icon: 'export', command: `onigiri_ctx_export:${did}` },
            { label: 'Copy Deck ID', icon: 'copy_id', command: `onigiri_ctx_copy_id:${did}` },
            { label: 'Delete Deck', icon: 'delete', danger: true, command: `onigiri_ctx_delete:${did}` },
        ].forEach(item => this.appendMenuItem(menu, item));

        this.positionMenu(menu, x, y);
    },

    showSortMenu: function (button, event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        this.closeQuickMenus();

        const current = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.deckSortMode) || 'default';
        const menu = document.createElement('div');
        menu.className = 'onigiri-quick-menu';

        [
            { label: 'Default order', icon: 'sort_default', mode: 'default' },
            { label: 'A to Z', icon: 'sort_custom', mode: 'alphabetical_az' },
            { label: 'Z to A', icon: 'sort_custom', mode: 'alphabetical_za' },
            { label: 'Most due', icon: 'sort_most_reviews', mode: 'most_due' },
            { label: 'Most new', icon: 'create_deck', mode: 'most_new' },
            { label: 'Most reviews', icon: 'stats', mode: 'most_reviews' },
            { label: 'Favorites first', icon: 'star_filled', mode: 'favorites_first' },
            { label: 'Custom order', icon: 'sort_custom', mode: 'custom' },
        ].forEach(item => this.appendMenuItem(menu, {
            label: item.label,
            icon: item.icon,
            selected: item.mode === current,
            command: `onigiri_sort:${item.mode}`,
        }));

        const rect = button.getBoundingClientRect();
        this.positionMenu(menu, rect.left, rect.bottom + 6);
    },

    /** Applies open/closed state classes to a collapse icon. */
    classifyCollapseIcon: function (el) {
        if (el.dataset.onigiriClassified) return;
        el.dataset.onigiriClassified = 'true';
        el.classList.remove('state-open', 'state-closed');

        if (el.textContent.trim() === '-') {
            el.classList.add('state-open');
        } else {
            el.classList.add('state-closed');
        }
        el.textContent = '';
    },
};

// Initialize the engine once the DOM is ready.
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => OnigiriEngine.init());
} else {
    OnigiriEngine.init();
}
