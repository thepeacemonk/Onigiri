// This file now only handles static UI elements like the sidebar,
// resize handle, and deck view cycling. The high-performance deck list
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
        if (header.parentElement !== expandedContent) {
            expandedContent.insertBefore(header, deckListContainer);
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
        }
        return toolbar;
    }

    function getSidebarButtonLayout() {
        const configLayout = window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.sidebarButtonLayout;
        const visible = Array.isArray(configLayout && configLayout.visible) ? configLayout.visible : [];
        const archived = Array.isArray(configLayout && configLayout.archived) ? configLayout.archived : [];
        return { visible, archived: new Set(archived) };
    }

    function isSidebarActionVisible(actionId) {
        const layout = getSidebarButtonLayout();
        if (layout.archived.has(actionId)) return false;
        if (!layout.visible.length) return true;
        return layout.visible.includes(actionId);
    }

    function moveToolbarBelowProfile(toolbar) {
        const sidebar = document.querySelector('.sidebar-left');
        const expandedContent = sidebar ? sidebar.querySelector('.sidebar-expanded-content') : null;
        if (!toolbar || !expandedContent) return;

        const profileBar = expandedContent.querySelector('.profile-bar');
        toolbar.classList.add('sidebar-actions-inline');
        if (profileBar) {
            profileBar.insertAdjacentElement('afterend', toolbar);
        } else if (toolbar.parentElement !== expandedContent) {
            expandedContent.insertBefore(toolbar, expandedContent.firstChild);
        }
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
        moveToolbarBelowProfile(toolbar);

        const pkg = window.ONIGIRI_CONFIG.addonPackage || '1011095603';
        const iconBase = `/_addons/${pkg}/system_files/system_icons/unavailable_for_users/`;
        const userIconBase = `/_addons/${pkg}/user_files/icons/`;
        const collapsedIcons = window.ONIGIRI_CONFIG.collapsedIcons || {};

        // Map action id -> default system icon filename
        const defaultIcons = {
            'add': 'add-card.svg',
            'browse': 'browse.svg',
            'stats': 'stats.svg',
            'sync': 'sync.svg',
            'settings': 'settings.svg',
            'gamification': 'gamepad.svg',
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
            { id: 'gamification', cmd: 'openGamificationSettings', title: 'Onigiri Games' },
            { id: 'more', cmd: null, title: 'More' }
        ];

        actions.forEach(action => {
            if (!isSidebarActionVisible(action.id)) return;
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
        if (!toolbar.querySelector('.action-btn')) {
            toolbar.remove();
        }
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
        ].filter(item => isSidebarActionVisible(item.id));

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

    function setupArchivedHomeButton() {
        if (typeof window.ONIGIRI_CONFIG === 'undefined') return;

        const actions = document.querySelector('#deck-list-header .deck-header-actions');
        const sortButton = document.getElementById('onigiri-sort-toolbar-btn');
        const container = document.querySelector('.container.modern-main-menu');
        const sidebar = document.querySelector('.sidebar-left');
        const shouldShow = window.ONIGIRI_CONFIG.sidebarActionsMode === 'archived';
        const addonPackage = window.ONIGIRI_CONFIG.addonPackage || '';
        const homeIconUrl = addonPackage
            ? `/_addons/${addonPackage}/system_files/system_icons/unavailable_for_users/home.svg`
            : '';

        if (container) container.classList.toggle('sidebar-actions-archived', shouldShow);
        if (sidebar) sidebar.classList.toggle('sidebar-actions-archived', shouldShow);

        if (!actions || !sortButton) return;

        let homeButton = document.getElementById('onigiri-home-toolbar-btn');

        if (!shouldShow) {
            if (homeButton) homeButton.remove();
            return;
        }

        if (!homeButton) {
            homeButton = document.createElement('span');
            homeButton.id = 'onigiri-home-toolbar-btn';
            homeButton.className = 'deck-header-btn';
            homeButton.setAttribute('role', 'button');
        homeButton.tabIndex = 0;
        // Set tabindex for accessibility
        try { arguments[0].tabIndex = 0; } catch(e){};
            homeButton.title = 'Home';
            homeButton.innerHTML = '<i class="home-btn-icon"></i>';
            homeButton.addEventListener('click', (event) => {
                if (window.OnigiriEngine && typeof window.OnigiriEngine.showHomeMenu === 'function') {
                    window.OnigiriEngine.showHomeMenu(homeButton, event);
                }
            });
        }

        const homeIcon = homeButton.querySelector('.home-btn-icon');
        if (homeIcon && homeIconUrl) {
            homeIcon.style.maskImage = `url("${homeIconUrl}")`;
            homeIcon.style.webkitMaskImage = `url("${homeIconUrl}")`;
        }

        if (homeButton.parentElement !== actions || homeButton.previousElementSibling !== sortButton) {
            sortButton.insertAdjacentElement('afterend', homeButton);
        }
    }

    function setupDeckViewCycling() {
        const sidebar = document.querySelector('.sidebar-left');
        if (!sidebar) return;
        const header = document.getElementById('deck-list-header');
        const label = header ? header.querySelector('h2') : null;
        const container = document.querySelector('.container.modern-main-menu');
        if (!header || !label || !container) return;

        const cycleStateKey = 'onigiri_decks_header_cycle_state';
        if (!sidebar.dataset.onigiriBaseSidebarOnly) {
            sidebar.dataset.onigiriBaseSidebarOnly = sidebar.classList.contains('sidebar-only-mode') ? '1' : '0';
        }

        document.querySelectorAll('.deck-focus-btn, .deck-header-focus-btn').forEach(btn => btn.remove());
        label.classList.add('deck-focus-label');
        label.setAttribute('role', 'button');
        label.tabIndex = 0;
        // Set tabindex for accessibility
        try { arguments[0].tabIndex = 0; } catch(e){};
        label.setAttribute('tabindex', '0');
        label.setAttribute('aria-label', 'Cycle deck display mode');
        label.removeAttribute('title');

        let modeGroup = header.querySelector('.deck-focus-mode-group');
        if (!modeGroup) {
            modeGroup = document.createElement('div');
            modeGroup.className = 'deck-focus-mode-group';
            header.insertBefore(modeGroup, header.firstChild);
        }
        if (label.parentElement !== modeGroup) {
            modeGroup.insertBefore(label, modeGroup.firstChild);
        }

        const pkg = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.addonPackage) || '1011095603';
        const iconBase = `/_addons/${pkg}/system_files/system_icons/unavailable_for_users/`;
        const modeIcons = [
            { state: 0, icon: 'sidebar.svg', label: 'Default sidebar' },
            { state: 1, icon: 'sidebar_focus.svg', label: 'Focus mode' },
            { state: 2, icon: 'sidebar_focus_2.svg', label: 'Focus sidebar only' },
            { state: 3, icon: 'sidebar_only.svg', label: 'Sidebar only' },
            { state: 4, icon: 'top_bar.svg', label: 'Top sidebar and widgets' },
        ];

        let modePalette = header.querySelector('.deck-focus-mode-icons');
        if (!modePalette) {
            modePalette = document.createElement('div');
            modePalette.className = 'deck-focus-mode-icons';
            modePalette.setAttribute('aria-label', 'Deck display modes');
        }
        if (modePalette.parentElement !== modeGroup || modePalette.previousElementSibling !== label) {
            label.insertAdjacentElement('afterend', modePalette);
        }
        modePalette.innerHTML = '';
        modeIcons.forEach((item) => {
            const button = document.createElement('span');
            button.setAttribute('role', 'button');
        button.tabIndex = 0;
        // Set tabindex for accessibility
        try { arguments[0].tabIndex = 0; } catch(e){};
            button.className = 'deck-focus-mode-icon-btn';
            button.dataset.deckCycleState = String(item.state);
            button.title = item.label;
            button.setAttribute('aria-label', item.label);

            const icon = document.createElement('span');
            icon.className = 'deck-focus-mode-icon';
            icon.style.setProperty('--deck-focus-mode-icon-url', `url("${iconBase}${item.icon}")`);
            button.appendChild(icon);
            modePalette.appendChild(button);
        });

        const saveCycleState = (state) => {
            try {
                sessionStorage.setItem(cycleStateKey, String(state));
            } catch (_) {}
        };

        const restoreBaseSidebarOnly = () => {
            sidebar.classList.toggle('sidebar-only-mode', sidebar.dataset.onigiriBaseSidebarOnly === '1');
        };

        const applyState = (state, options) => {
            const opts = options || {};
            const nextState = Math.max(0, Math.min(4, Number.isFinite(state) ? state : 0));
            const isFocusMode = nextState === 1 || nextState === 2;
            const isTemporarySidebarOnly = nextState === 2 || nextState === 3;
            const isStackedLayout = nextState === 4;

            sidebar.classList.toggle('deck-focus-mode', isFocusMode);
            container.classList.toggle('onigiri-cycle-sidebar-only', isTemporarySidebarOnly);
            container.classList.toggle('onigiri-cycle-stacked', isStackedLayout);
            if (isTemporarySidebarOnly || isStackedLayout) {
                sidebar.classList.add('sidebar-only-mode');
            } else {
                restoreBaseSidebarOnly();
            }
            if (!isStackedLayout) {
                sidebar.style.removeProperty('height');
            }

            header.classList.toggle('deck-focus-active', isFocusMode);
            header.dataset.onigiriDeckCycleState = String(nextState);
            modePalette.querySelectorAll('.deck-focus-mode-icon-btn').forEach((button) => {
                const isActive = button.dataset.deckCycleState === String(nextState);
                button.classList.toggle('active', isActive);
                button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
            });
            saveCycleState(nextState);
            updateDeckFocusLayout();
            if (typeof window.onigiriUpdateSidebarEdgeToggle === 'function') {
                window.onigiriUpdateSidebarEdgeToggle();
            }
            if (window.OnigiriEngine && typeof window.OnigiriEngine.updateMultiSelectionVisuals === 'function') {
                window.OnigiriEngine.updateMultiSelectionVisuals();
            }
            if (opts.persistFocus !== false && typeof pycmd === 'function') {
                pycmd(`saveDeckCycleState:${nextState}`);
            }
            if (typeof label.blur === 'function') label.blur();
        };

        const currentState = () => {
            if (container.classList.contains('onigiri-cycle-stacked')) {
                return 4;
            }
            if (container.classList.contains('onigiri-cycle-sidebar-only')) {
                return sidebar.classList.contains('deck-focus-mode') ? 2 : 3;
            }
            return sidebar.classList.contains('deck-focus-mode') ? 1 : 0;
        };

        const cycle = (event) => {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            applyState((currentState() + 1) % 5);
        };

        if (!label.dataset.onigiriDeckViewCycleBound) {
            label.dataset.onigiriDeckViewCycleBound = 'true';
            label.addEventListener('click', cycle);
            label.addEventListener('keydown', (event) => {
                if (event.key !== 'Enter' && event.key !== ' ') return;
                cycle(event);
            });
        }

        modePalette.querySelectorAll('.deck-focus-mode-icon-btn').forEach((button) => {
            if (button.dataset.onigiriDeckModeBound) return;
            button.dataset.onigiriDeckModeBound = 'true';
            button.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                const nextState = Number.parseInt(button.dataset.deckCycleState || '0', 10);
                applyState(nextState);
                if (typeof button.blur === 'function') button.blur();
            });
        });

        let restoredState = sidebar.classList.contains('deck-focus-mode') ? 1 : 0;
        const configuredState = Number.parseInt(
            window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.deckCycleState,
            10
        );
        if (configuredState >= 0 && configuredState <= 4) {
            restoredState = configuredState;
        }
        try {
            const storedState = Number.parseInt(sessionStorage.getItem(cycleStateKey) || '', 10);
            if (storedState === 2 || storedState === 3 || storedState === 4) {
                restoredState = storedState;
            } else if (storedState === 1 && sidebar.classList.contains('deck-focus-mode')) {
                restoredState = 1;
            } else if (storedState === 0 && !sidebar.classList.contains('deck-focus-mode')) {
                restoredState = 0;
            }
        } catch (_) {}
        applyState(restoredState, { persistFocus: false });
    }

    function setupResizeHandle() {
        const handle = document.querySelector('.resize-handle');
        const sidebarEl = document.querySelector('.sidebar-left');
        const containerEl = document.querySelector('.container.modern-main-menu');
        if (!handle || !sidebarEl || handle.dataset.onigiriSetup) return;
        handle.dataset.onigiriSetup = 'true';

        let hitbox = handle.querySelector('.resize-handle-hitbox');
        if (!hitbox) {
            hitbox = document.createElement('div');
            hitbox.className = 'resize-handle-hitbox';
            handle.appendChild(hitbox);
        }

        hitbox.setAttribute('aria-hidden', 'true');

        if (!handle.querySelector('.resize-handle-indicator')) {
            const indicator = document.createElement('div');
            indicator.className = 'resize-handle-indicator';
            handle.appendChild(indicator);
        }

        let isResizing = false;
        let startX = 0;
        let startY = 0;
        let startWidth = 0;
        let startHeight = 0;
        let animationFrameId = null;
        let lastClientX = 0;
        let lastClientY = 0;
        let lastWidth = 0;
        let lastHeight = 0;
        let activePointerId = null;
        let resizeFromRightEdge = false;
        let resizeArmed = false;
        let activeResizeEdges = [];
        const minWidth = 320;
        const minHeight = 260;
        const defaultWidth = 345;
        const defaultHeight = 520;

        const isStackedLayout = () => {
            if (containerEl && containerEl.classList.contains('onigiri-cycle-stacked')) return true;
            return !!(window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.sidebarPosition === 'center');
        };

        const isSidebarOnRight = () => {
            const mainContent = document.querySelector('.main-content');
            if (mainContent) {
                const sidebarRect = sidebarEl.getBoundingClientRect();
                const mainRect = mainContent.getBoundingClientRect();
                if (sidebarRect.width > 0 && mainRect.width > 0) {
                    return mainRect.left < sidebarRect.left;
                }
            }
            const container = sidebarEl.parentElement;
            const flexDirection = container ? window.getComputedStyle(container).flexDirection : '';
            return flexDirection.includes('reverse');
        };

        const cursorForEdges = (edges) => {
            const edgeSet = new Set(edges || []);
            if ((edgeSet.has('top') && edgeSet.has('left')) || (edgeSet.has('bottom') && edgeSet.has('right'))) {
                return 'nwse-resize';
            }
            if ((edgeSet.has('top') && edgeSet.has('right')) || (edgeSet.has('bottom') && edgeSet.has('left'))) {
                return 'nesw-resize';
            }
            if (edgeSet.has('top') || edgeSet.has('bottom')) return 'ns-resize';
            return 'ew-resize';
        };

        const setResizeCursor = (edges) => {
            const cursor = cursorForEdges(edges);
            handle.style.setProperty('--onigiri-sidebar-resize-cursor', cursor);
            const edgePill = document.getElementById('onigiri-sidebar-edge-pill');
            if (edgePill) edgePill.style.setProperty('--onigiri-sidebar-resize-cursor', cursor);
            return cursor;
        };

        const resolveResizeEdges = (event) => {
            if (!isStackedLayout()) {
                return [isSidebarOnRight() ? 'left' : 'right'];
            }
            const edgePill = document.getElementById('onigiri-sidebar-edge-pill');
            const stored = (handle.dataset.onigiriResizeEdges || (edgePill && edgePill.dataset.resizeEdges) || '')
                .split(/\s+/)
                .filter(Boolean);
            if (stored.length) return stored;

            const rect = sidebarEl.getBoundingClientRect();
            const distances = {
                left: Math.abs((event.clientX || rect.right) - rect.left),
                right: Math.abs((event.clientX || rect.right) - rect.right),
                top: Math.abs((event.clientY || rect.bottom) - rect.top),
                bottom: Math.abs((event.clientY || rect.bottom) - rect.bottom),
            };
            const threshold = 54;
            const edges = [];
            const nearestHorizontal = distances.left <= distances.right ? 'left' : 'right';
            const nearestVertical = distances.top <= distances.bottom ? 'top' : 'bottom';
            if (distances[nearestHorizontal] <= threshold) edges.push(nearestHorizontal);
            if (distances[nearestVertical] <= threshold) edges.push(nearestVertical);
            return edges.length ? edges : ['right'];
        };

        const fixedWidth = (width) => {
            const nextWidth = Math.max(minWidth, Math.round(width));
            sidebarEl.style.setProperty('--onigiri-sidebar-width', `${nextWidth}px`);
            sidebarEl.style.setProperty('width', `${nextWidth}px`, 'important');
            sidebarEl.style.setProperty('max-width', 'none', 'important');
            sidebarEl.dataset.onigiriLastWidth = String(nextWidth);
            if (typeof window.onigiriUpdateSidebarEdgeToggle === 'function') {
                window.onigiriUpdateSidebarEdgeToggle();
            }
            return nextWidth;
        };

        const fixedHeight = (height) => {
            const nextHeight = Math.max(minHeight, Math.round(height));
            sidebarEl.style.setProperty('--onigiri-sidebar-height', `${nextHeight}px`);
            sidebarEl.style.setProperty('height', `${nextHeight}px`, 'important');
            sidebarEl.dataset.onigiriLastHeight = String(nextHeight);
            if (typeof window.onigiriUpdateSidebarEdgeToggle === 'function') {
                window.onigiriUpdateSidebarEdgeToggle();
            }
            return nextHeight;
        };

        const updateSidebarSize = () => {
            const deltaX = lastClientX - startX;
            const deltaY = lastClientY - startY;
            if (isStackedLayout()) {
                const edgeSet = new Set(activeResizeEdges);
                let newWidth = startWidth;
                let newHeight = startHeight;
                if (edgeSet.has('left')) {
                    newWidth = startWidth - (deltaX * 2);
                } else if (edgeSet.has('right')) {
                    newWidth = startWidth + (deltaX * 2);
                }
                if (edgeSet.has('top')) {
                    newHeight = startHeight - deltaY;
                } else if (edgeSet.has('bottom')) {
                    newHeight = startHeight + deltaY;
                }
                if (Math.abs(newWidth - lastWidth) > 0.5) {
                    lastWidth = fixedWidth(newWidth);
                }
                if (Math.abs(newHeight - lastHeight) > 0.5) {
                    lastHeight = fixedHeight(newHeight);
                }
            } else {
                const directionalDelta = resizeFromRightEdge ? -deltaX : deltaX;
                let newWidth = startWidth + directionalDelta;
                if (newWidth < minWidth) newWidth = minWidth;
                if (Math.abs(newWidth - lastWidth) > 0.5) {
                    lastWidth = fixedWidth(newWidth);
                }
            }
            animationFrameId = null;
        };

        const clearResizeArmed = () => {
            resizeArmed = false;
            sidebarEl.classList.remove('is-resize-armed');
            handle.classList.remove('is-resize-armed');
            const edgePill = document.getElementById('onigiri-sidebar-edge-pill');
            if (edgePill) edgePill.classList.remove('is-resize-armed');
            handle.removeAttribute('data-onigiri-resize-edges');
        };

        const pointerdownHandler = (e) => {
            if (e.pointerType === 'mouse' && e.button !== 0) return;
            if (sidebarEl.classList.contains('sidebar-collapsed')) return;
            e.preventDefault();
            e.stopPropagation();

            const edgePill = document.getElementById('onigiri-sidebar-edge-pill');
            activeResizeEdges = resolveResizeEdges(e);
            const resizeCursor = setResizeCursor(activeResizeEdges);
            handle.dataset.onigiriResizeEdges = activeResizeEdges.join(' ');
            if (edgePill) edgePill.dataset.resizeEdges = activeResizeEdges.join(' ');
            if (!resizeArmed) {
                resizeArmed = true;
                sidebarEl.classList.add('is-resize-armed');
                handle.classList.add('is-resize-armed');
                if (edgePill) edgePill.classList.add('is-resize-armed');
                handle.setAttribute('aria-pressed', 'true');
                if (typeof window.onigiriUpdateSidebarEdgeToggle === 'function') {
                    window.onigiriUpdateSidebarEdgeToggle();
                }
                return;
            }

            isResizing = true;
            activePointerId = e.pointerId;
            startX = e.clientX || 0;
            startY = e.clientY || 0;
            lastClientX = startX;
            lastClientY = startY;
            const rect = sidebarEl.getBoundingClientRect();
            const rememberedWidth = parseFloat(sidebarEl.style.width)
                || parseFloat(sidebarEl.dataset.onigiriLastWidth)
                || defaultWidth;
            const rememberedHeight = parseFloat(sidebarEl.style.height)
                || parseFloat(sidebarEl.dataset.onigiriLastHeight)
                || defaultHeight;
            startWidth = rect.width || rememberedWidth;
            startHeight = rect.height || rememberedHeight;
            lastWidth = startWidth;
            lastHeight = startHeight;
            resizeFromRightEdge = isSidebarOnRight();

            fixedWidth(startWidth);
            if (isStackedLayout()) fixedHeight(startHeight);

            sidebarEl.classList.add('is-resizing');
            handle.classList.add('is-resizing');
            if (edgePill) edgePill.classList.add('is-resizing');
            if (typeof window.onigiriUpdateSidebarEdgeToggle === 'function') {
                window.onigiriUpdateSidebarEdgeToggle();
            }
            document.body.style.userSelect = 'none';
            document.body.style.cursor = resizeCursor;
            try {
                if (hitbox.setPointerCapture && activePointerId !== null) {
                    hitbox.setPointerCapture(activePointerId);
                }
            } catch (_) {}
        };

        const pointermoveHandler = (e) => {
            if (!isResizing) return;
            lastClientX = e.clientX;
            lastClientY = e.clientY;
            e.preventDefault();
            if (!animationFrameId) {
                animationFrameId = requestAnimationFrame(updateSidebarSize);
            }
        };

        const finishPointer = (e) => {
            if (!isResizing) return;
            isResizing = false;
            activePointerId = null;

            if (animationFrameId) {
                cancelAnimationFrame(animationFrameId);
                animationFrameId = null;
            }
            const finalWidth = parseInt(sidebarEl.style.width, 10) || lastWidth;
            fixedWidth(finalWidth);
            if (isStackedLayout()) {
                const finalHeight = parseInt(sidebarEl.style.height, 10) || lastHeight;
                fixedHeight(finalHeight);
                if (typeof pycmd === 'function') pycmd(`saveSidebarSize:${finalWidth}:${finalHeight}`);
            } else if (typeof pycmd === 'function') {
                pycmd(`saveSidebarWidth:${finalWidth}`);
            }

            sidebarEl.classList.remove('is-resizing');
            handle.classList.remove('is-resizing');
            handle.setAttribute('aria-pressed', 'false');
            const edgePill = document.getElementById('onigiri-sidebar-edge-pill');
            if (edgePill) {
                edgePill.classList.remove('is-resizing');
            }
            
            const isClick = Math.abs(lastClientX - startX) < 5 && Math.abs(lastClientY - startY) < 5;
            if (isClick) {
                clearResizeArmed();
            }

            if (typeof window.onigiriUpdateSidebarEdgeToggle === 'function') {
                window.onigiriUpdateSidebarEdgeToggle();
            }
            document.body.style.removeProperty('user-select');
            document.body.style.removeProperty('cursor');
            try {
                if (hitbox.releasePointerCapture && e && e.pointerId !== undefined) {
                    hitbox.releasePointerCapture(e.pointerId);
                }
            } catch (_) {}
        };

        const documentPointerdownHandler = (e) => {
            if (!resizeArmed || isResizing) return;
            if (handle.contains(e.target)) return;
            // Removed clearResizeArmed() so user must explicitly click the icon to stop resizing
        };

        handle._resizeHandlers = {
            hitbox,
            pointerdown: pointerdownHandler,
            pointermove: pointermoveHandler,
            pointerup: finishPointer,
            documentPointerdown: documentPointerdownHandler
        };

        hitbox.addEventListener('pointerdown', pointerdownHandler);
        handle.setAttribute('aria-pressed', 'false');
        document.addEventListener('pointermove', pointermoveHandler, { passive: false });
        document.addEventListener('pointerup', finishPointer);
        document.addEventListener('pointercancel', finishPointer);
        document.addEventListener('pointerdown', documentPointerdownHandler);
    }

    function refreshResizeHandle() {
        const handle = document.querySelector('.resize-handle');
        if (!handle || !handle._resizeHandlers) return;

        const handlers = handle._resizeHandlers;
        handlers.hitbox.removeEventListener('pointerdown', handlers.pointerdown);
        document.removeEventListener('pointermove', handlers.pointermove);
        document.removeEventListener('pointerup', handlers.pointerup);
        document.removeEventListener('pointercancel', handlers.pointerup);
        document.removeEventListener('pointerdown', handlers.documentPointerdown);

        delete handle.dataset.onigiriSetup;
        setupResizeHandle();
    }

    function setupProfileSidebar() {
        const sidebar = document.querySelector('.sidebar-left');
        const panel = sidebar ? sidebar.querySelector('[data-profile-sidebar]') : null;
        if (!sidebar || !panel || panel.dataset.profileSidebarBound) return;
        panel.dataset.profileSidebarBound = 'true';

        function setOpen(open, event) {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            if (open && sidebar.classList.contains('sidebar-collapsed') && typeof window.onigiriExpandSidebar === 'function') {
                window.onigiriExpandSidebar();
            }
            sidebar.classList.add('profile-panel-switching');
            void sidebar.offsetHeight;
            sidebar.classList.toggle('profile-panel-open', !!open);
            requestAnimationFrame(() => sidebar.classList.remove('profile-panel-switching'));
            if (typeof window.onigiriUpdateSidebarEdgeToggle === 'function') {
                requestAnimationFrame(window.onigiriUpdateSidebarEdgeToggle);
            }
        }

        window.OnigiriProfileSidebar = {
            open: (event) => setOpen(true, event),
            close: (event) => setOpen(false, event),
            toggle: (event) => setOpen(!sidebar.classList.contains('profile-panel-open'), event)
        };
    }

    function init() {
        const sidebar = document.querySelector('.sidebar-left.skeleton-loading');
        if (sidebar) {
            setTimeout(() => sidebar.classList.remove('skeleton-loading'), 150);
        }

        const sidebarEl = document.querySelector('.sidebar-left');
        const legacyToggleBtn = document.querySelector('.sidebar-toggle-btn');
        const edgeToggleBtn = document.getElementById('onigiri-sidebar-edge-toggle');
        const edgeToggleZone = document.querySelector('.sidebar-edge-toggle-zone');
        const edgePill = document.getElementById('onigiri-sidebar-edge-pill');
        if (legacyToggleBtn) legacyToggleBtn.remove();

        let savedSidebarWidth = null;
        let edgeToggleCollapseLocked = false;
        let lastSidebarOnRight = false;
        let edgeHoverTimer = null;

        function isSidebarOnRight() {
            const mainContent = document.querySelector('.main-content');
            if (mainContent && sidebarEl) {
                const sidebarRect = sidebarEl.getBoundingClientRect();
                const mainRect = mainContent.getBoundingClientRect();
                if (sidebarRect.width > 0 && mainRect.width > 0) {
                    return mainRect.left < sidebarRect.left;
                }
            }
            const container = sidebarEl && sidebarEl.parentElement;
            const flexDirection = container ? window.getComputedStyle(container).flexDirection : '';
            return flexDirection.includes('reverse');
        }

        function isStackedLayout() {
            const container = document.querySelector('.container.modern-main-menu');
            if (container && container.classList.contains('onigiri-cycle-stacked')) return true;
            return !!(window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.sidebarPosition === 'center');
        }

        function setEdgeControlPosition(centerX, centerY) {
            if (!edgePill) return;
            edgePill.style.left = `${Math.round(centerX)}px`;
            edgePill.style.top = `${Math.round(centerY)}px`;
        }

        function cursorForResizeEdges(edges) {
            const edgeSet = new Set(edges || []);
            if ((edgeSet.has('top') && edgeSet.has('left')) || (edgeSet.has('bottom') && edgeSet.has('right'))) {
                return 'nwse-resize';
            }
            if ((edgeSet.has('top') && edgeSet.has('right')) || (edgeSet.has('bottom') && edgeSet.has('left'))) {
                return 'nesw-resize';
            }
            if (edgeSet.has('top') || edgeSet.has('bottom')) return 'ns-resize';
            return 'ew-resize';
        }

        function setResizeEdges(edges) {
            if (!edgePill) return;
            const normalized = (edges && edges.length ? edges : ['right']).join(' ');
            const resizeHandle = edgePill.querySelector('.resize-handle');
            const edgeSet = new Set(edges && edges.length ? edges : ['right']);
            const isHorizontal = edgeSet.has('top') || edgeSet.has('bottom');
            edgePill.dataset.resizeEdges = normalized;
            edgePill.classList.toggle('is-edge-horizontal', isHorizontal);
            edgePill.style.setProperty('--onigiri-sidebar-resize-cursor', cursorForResizeEdges(edges));
            if (resizeHandle) {
                resizeHandle.dataset.onigiriResizeEdges = normalized;
                resizeHandle.style.setProperty('--onigiri-sidebar-resize-cursor', cursorForResizeEdges(edges));
            }
        }

        function stackedEdgeHit(event, rect) {
            const threshold = 42;
            const withinX = event.clientX >= rect.left - threshold && event.clientX <= rect.right + threshold;
            const withinY = event.clientY >= rect.top - threshold && event.clientY <= rect.bottom + threshold;
            const nearBottom = withinX && Math.abs(event.clientY - rect.bottom) <= threshold;
            if (nearBottom) return { edges: ['bottom'] };

            if (!withinY) return null;
            const leftDistance = Math.abs(event.clientX - rect.left);
            const rightDistance = Math.abs(event.clientX - rect.right);
            if (leftDistance <= threshold || rightDistance <= threshold) {
                return { edges: [leftDistance <= rightDistance ? 'left' : 'right'] };
            }
            return null;
        }

        function positionStackedEdgeControl(rect, edges) {
            const edgeSet = new Set(edges || ['right']);
            const isHorizontal = edgeSet.has('top') || edgeSet.has('bottom');
            const pillWidth = isHorizontal ? 88 : 32;
            const pillHeight = isHorizontal ? 32 : 72;
            const gap = isHorizontal ? 0 : 6;
            let centerX = rect.left + (rect.width / 2);
            let centerY = rect.top + (rect.height / 2);

            if (edgeSet.has('left')) centerX = rect.left - gap - (pillWidth / 2);
            else if (edgeSet.has('right')) centerX = rect.right + gap + (pillWidth / 2);

            if (edgeSet.has('top')) centerY = rect.top - gap - (pillWidth / 2);
            else if (edgeSet.has('bottom')) centerY = rect.bottom + gap + (pillWidth / 2);

            setEdgeControlPosition(
                Math.max(pillWidth / 2, Math.min(window.innerWidth - (pillWidth / 2), centerX)),
                Math.max(pillWidth / 2, Math.min(window.innerHeight - (pillHeight / 2), centerY))
            );
            setResizeEdges(edges);
            edgePill.classList.toggle('is-sidebar-right', edgeSet.has('left'));
        }

        function setEdgeHover(active, delay = 0) {
            if (!edgePill) return;
            if (edgeHoverTimer) {
                window.clearTimeout(edgeHoverTimer);
                edgeHoverTimer = null;
            }
            const apply = () => {
                if (active) {
                    edgePill.classList.remove('is-edge-closing');
                    edgePill.classList.add('is-edge-hover');
                    return;
                }
                if (!edgePill.classList.contains('is-edge-hover')) return;
                edgePill.classList.remove('is-edge-hover');
                edgePill.classList.add('is-edge-closing');
                window.setTimeout(() => {
                    edgePill.classList.remove('is-edge-closing');
                }, 190);
            };
            if (delay > 0) {
                edgeHoverTimer = window.setTimeout(apply, delay);
            } else {
                apply();
            }
        }

        function iconUrl(filename) {
            const pkg = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.addonPackage) || '1011095603';
            return `/_addons/${pkg}/system_files/system_icons/unavailable_for_users/${filename}`;
        }

        function resolveSidebarIconColor() {
            if (!sidebarEl) return '';
            const sidebarStyle = window.getComputedStyle(sidebarEl);
            const cssVars = [
                sidebarStyle.getPropertyValue('--fg-subtle'),
                sidebarStyle.getPropertyValue('--icon-color')
            ];
            for (const value of cssVars) {
                const color = String(value || '').trim();
                if (color && color !== 'transparent') return color;
            }
            const candidates = [
                sidebarEl.querySelector('.sidebar-toolbar .action-icon'),
                sidebarEl.querySelector('.deck-header-btn'),
                sidebarEl.querySelector('.menu-item .icon'),
                sidebarEl
            ];
            for (const element of candidates) {
                if (!element) continue;
                const style = window.getComputedStyle(element);
                const color = style.backgroundColor && style.backgroundColor !== 'rgba(0, 0, 0, 0)'
                    ? style.backgroundColor
                    : style.color;
                if (color && color !== 'rgba(0, 0, 0, 0)' && color !== 'transparent') {
                    return color;
                }
            }
            return '';
        }

        function updateEdgeIcons(sidebarOnRight, orientation = 'side', collapsed = false) {
            const collapseIcon = edgeToggleBtn ? edgeToggleBtn.querySelector('.sidebar-edge-toggle-icon') : null;
            const resizeIcon = edgePill ? edgePill.querySelector('.resize-handle-indicator') : null;
            const iconColor = resolveSidebarIconColor();
            if (edgePill) {
                if (iconColor) {
                    edgePill.style.setProperty('--onigiri-edge-icon-color', iconColor);
                }
                if (sidebarEl) {
                    const sidebarBg = window.getComputedStyle(sidebarEl).backgroundColor;
                    if (sidebarBg && sidebarBg !== 'rgba(0, 0, 0, 0)' && sidebarBg !== 'transparent') {
                        edgePill.style.setProperty('--onigiri-sidebar-bg', sidebarBg);
                    } else {
                        edgePill.style.removeProperty('--onigiri-sidebar-bg');
                    }
                }
            }
            if (collapseIcon) {
                const collapseIconName = orientation === 'top'
                    ? (collapsed ? 'down.svg' : 'up.svg')
                    : (sidebarOnRight ? 'sidebar_right_hidden.svg' : 'sidebar_left_hidden.svg');
                collapseIcon.style.setProperty(
                    '--onigiri-collapse-icon-url',
                    `url("${iconUrl(collapseIconName)}")`
                );
            }
            if (resizeIcon) {
                resizeIcon.style.setProperty('--onigiri-resize-icon-url', `url("${iconUrl('resize.svg')}")`);
            }
        }

        function applyCollapsedEdgeTogglePosition() {
            if (!edgePill) return;
            edgePill.classList.remove('is-edge-closing');
            edgePill.classList.add('is-collapsed');
            if (isStackedLayout()) {
                const pillWidth = 30;
                const centerX = window.innerWidth / 2;
                const centerY = (pillWidth / 2) + 8;
                setResizeEdges(['top']);
                setEdgeControlPosition(centerX, centerY);
                edgePill.classList.remove('is-sidebar-right');
                updateEdgeIcons(false, 'top', true);
                if (edgeToggleBtn) edgeToggleBtn.classList.add('is-collapsed');
                if (edgeToggleZone) {
                    const zoneHeight = Math.max(edgeToggleZone.offsetHeight || 48, 56);
                    edgeToggleZone.style.left = '0px';
                    edgeToggleZone.style.top = '0px';
                    edgeToggleZone.style.width = `${window.innerWidth}px`;
                    edgeToggleZone.style.height = `${zoneHeight}px`;
                    edgeToggleZone.style.cursor = 'pointer';
                    edgeToggleZone.style.pointerEvents = 'auto';
                }
                return;
            }
            const pillWidth = 30;
            const centerX = lastSidebarOnRight ? window.innerWidth - (pillWidth / 2) - 8 : (pillWidth / 2) + 8;
            const centerY = Math.max(12 + (pillWidth / 2), window.innerHeight / 2);
            setEdgeControlPosition(centerX, centerY);
            setResizeEdges([lastSidebarOnRight ? 'left' : 'right']);
            edgePill.classList.toggle('is-sidebar-right', lastSidebarOnRight);
            updateEdgeIcons(lastSidebarOnRight);
            if (edgeToggleBtn) edgeToggleBtn.classList.add('is-collapsed');
            if (edgeToggleZone) {
                const zoneWidth = Math.max(edgeToggleZone.offsetWidth || 48, 56);
                edgeToggleZone.style.left = `${lastSidebarOnRight ? Math.max(0, window.innerWidth - zoneWidth) : 0}px`;
                edgeToggleZone.style.top = '0px';
                edgeToggleZone.style.width = `${zoneWidth}px`;
                edgeToggleZone.style.height = `${window.innerHeight}px`;
                edgeToggleZone.style.cursor = 'pointer';
                edgeToggleZone.style.pointerEvents = 'auto';
            }
        }

        function updateSidebarEdgeToggle() {
            if (!edgeToggleBtn || !sidebarEl || !edgePill) return;
            const isCollapsed = sidebarEl.classList.contains('sidebar-collapsed') || edgeToggleCollapseLocked;
            if (isCollapsed) {
                if (!edgeToggleCollapseLocked) {
                    lastSidebarOnRight = isSidebarOnRight();
                }
                applyCollapsedEdgeTogglePosition();
                edgeToggleBtn.title = 'Expand sidebar';
                edgeToggleBtn.setAttribute('aria-label', edgeToggleBtn.title);
                return;
            }
            lastSidebarOnRight = isSidebarOnRight();
            updateEdgeIcons(lastSidebarOnRight);
            const rect = sidebarEl.getBoundingClientRect();
            const pillWidth = 32;
            const pillHeight = 72;
            const gap = 10;
            if (isStackedLayout()) {
                let storedEdges = (edgePill.dataset.resizeEdges || 'bottom').split(/\s+/).filter(Boolean);
                if (!storedEdges.length || storedEdges.includes('top')) {
                    storedEdges = ['bottom'];
                }
                positionStackedEdgeControl(rect, storedEdges);
                updateEdgeIcons(false, 'top', false);
                edgePill.classList.remove('is-collapsed');
                edgePill.classList.remove('is-edge-closing');
                edgeToggleBtn.classList.remove('is-collapsed');
                edgeToggleBtn.title = 'Collapse sidebar';
                edgeToggleBtn.setAttribute('aria-label', edgeToggleBtn.title);
                if (edgeToggleZone) {
                    const zoneInset = 48;
                    edgeToggleZone.style.left = `${Math.max(0, rect.left - zoneInset)}px`;
                    edgeToggleZone.style.top = `${Math.max(0, rect.top - zoneInset)}px`;
                    edgeToggleZone.style.width = `${Math.min(window.innerWidth, rect.width + (zoneInset * 2))}px`;
                    edgeToggleZone.style.height = `${Math.min(window.innerHeight, rect.height + (zoneInset * 2))}px`;
                    edgeToggleZone.style.cursor = 'default';
                    edgeToggleZone.style.pointerEvents = 'none';
                }
                return;
            }
            const edgeX = lastSidebarOnRight ? rect.left : rect.right;
            const centerX = lastSidebarOnRight ? edgeX - gap - (pillWidth / 2) : edgeX + gap + (pillWidth / 2);
            const centerY = rect.top + Math.max(24 + (pillHeight / 2), rect.height / 2);

            setEdgeControlPosition(
                Math.max(pillWidth / 2, Math.min(window.innerWidth - (pillWidth / 2), centerX)),
                Math.max(pillHeight / 2, Math.min(window.innerHeight - (pillHeight / 2), centerY))
            );
            setResizeEdges([lastSidebarOnRight ? 'left' : 'right']);
            edgePill.classList.remove('is-collapsed');
            edgePill.classList.remove('is-edge-closing');
            edgePill.classList.toggle('is-sidebar-right', lastSidebarOnRight);
            edgeToggleBtn.classList.remove('is-collapsed');
            edgeToggleBtn.title = 'Collapse sidebar';
            edgeToggleBtn.setAttribute('aria-label', edgeToggleBtn.title);

            if (edgeToggleZone) {
                const zoneWidth = 48;
                edgeToggleZone.style.width = `${zoneWidth}px`;
                edgeToggleZone.style.left = `${Math.max(0, edgeX - Math.round(zoneWidth / 2))}px`;
                edgeToggleZone.style.top = `${Math.max(0, rect.top)}px`;
                edgeToggleZone.style.height = `${Math.max(100, rect.height)}px`;
                edgeToggleZone.style.cursor = 'default';
                edgeToggleZone.style.pointerEvents = 'auto';
            }
        }

        function collapseSidebar() {
            if (!sidebarEl) return;
            edgeToggleCollapseLocked = true;
            lastSidebarOnRight = isSidebarOnRight();
            applyCollapsedEdgeTogglePosition();
            const inlineWidth = sidebarEl.style.width;
            const currentWidth = sidebarEl.getBoundingClientRect().width;
            if (inlineWidth) {
                savedSidebarWidth = inlineWidth;
            } else if (currentWidth > 0) {
                savedSidebarWidth = `${Math.round(currentWidth)}px`;
            }
            if (savedSidebarWidth) {
                sidebarEl.dataset.onigiriLastWidth = String(parseFloat(savedSidebarWidth) || 345);
            }
            sidebarEl.style.removeProperty('width');
            sidebarEl.style.removeProperty('max-width');
            sidebarEl.classList.add('sidebar-collapsed');
            updateSidebarEdgeToggle();
            if (typeof pycmd === 'function') pycmd('saveSidebarState:true');
        }

        function expandSidebar() {
            if (!sidebarEl) return;
            edgeToggleCollapseLocked = false;
            sidebarEl.classList.remove('sidebar-collapsed');
            if (savedSidebarWidth) {
                const restoredWidth = parseFloat(savedSidebarWidth);
                if (Number.isFinite(restoredWidth) && restoredWidth > 0) {
                    sidebarEl.style.setProperty('width', `${restoredWidth}px`, 'important');
                    sidebarEl.dataset.onigiriLastWidth = String(restoredWidth);
                }
            }
            updateSidebarEdgeToggle();
            if (typeof pycmd === 'function') pycmd('saveSidebarState:false');
        }

        function toggleSidebar() {
            if (!sidebarEl) return;
            if (sidebarEl.classList.contains('sidebar-collapsed')) {
                expandSidebar();
            } else {
                collapseSidebar();
            }
        }

        window.onigiriCollapseSidebar = collapseSidebar;
        window.onigiriExpandSidebar = expandSidebar;
        window.onigiriToggleSidebar = toggleSidebar;
        window.onigiriUpdateSidebarEdgeToggle = updateSidebarEdgeToggle;

        if (edgeToggleBtn && sidebarEl && edgePill) {
            updateSidebarEdgeToggle();
            const showEdgeHover = () => {
                const shouldPrepareAnimation = !edgePill.classList.contains('is-edge-hover')
                    && !edgePill.classList.contains('is-edge-closing');
                if (!isStackedLayout()) {
                    updateSidebarEdgeToggle();
                }
                if (shouldPrepareAnimation) void edgePill.offsetWidth;
                setEdgeHover(true);
            };
            const edgeHoverHandler = (event) => {
                if (!edgePill || !sidebarEl) return;
                if (sidebarEl.classList.contains('sidebar-collapsed')) return;
                if (edgePill.classList.contains('is-resizing')) return;
                if (edgePill.contains(event.target)) {
                    showEdgeHover();
                    return;
                }

                const rect = sidebarEl.getBoundingClientRect();
                if (!rect.width || !rect.height) return;
                if (isStackedLayout()) {
                    const hit = stackedEdgeHit(event, rect);
                    if (hit) {
                        positionStackedEdgeControl(rect, hit.edges);
                        showEdgeHover();
                    } else if (edgePill.classList.contains('is-edge-hover')) {
                        setEdgeHover(false, 180);
                    }
                    return;
                }
                const sidebarOnRight = isSidebarOnRight();
                const edgeX = sidebarOnRight ? rect.left : rect.right;
                const withinY = event.clientY >= rect.top && event.clientY <= rect.bottom;
                const nearEdge = withinY && Math.abs(event.clientX - edgeX) <= 38;

                if (nearEdge) {
                    showEdgeHover();
                } else if (edgePill.classList.contains('is-edge-hover')) {
                    setEdgeHover(false, 180);
                }
            };
            edgePill.addEventListener('mouseenter', showEdgeHover);
            edgePill.addEventListener('mouseleave', () => setEdgeHover(false, 180));
            document.addEventListener('mousemove', edgeHoverHandler);
            edgeToggleBtn.addEventListener('click', () => {
                toggleSidebar();
                edgeToggleBtn.blur();
            });
            if (edgeToggleZone) {
                edgeToggleZone.addEventListener('click', (event) => {
                    if (!sidebarEl.classList.contains('sidebar-collapsed')) return;
                    event.preventDefault();
                    event.stopPropagation();
                    expandSidebar();
                });
            }
            window.addEventListener('resize', updateSidebarEdgeToggle);
            if (typeof ResizeObserver !== 'undefined') {
                const edgeToggleObserver = new ResizeObserver(updateSidebarEdgeToggle);
                edgeToggleObserver.observe(sidebarEl);
            }
            requestAnimationFrame(updateSidebarEdgeToggle);
        }

        setupResizeHandle();
        setupProfileSidebar();
        setupDeckViewCycling();
        setupActionButtons(); // Initialize action buttons
        setupArchivedHomeButton();
        updateDeckLayouts(); // Initial call
        updateDeckFocusLayout(); // Add this line to handle initial state
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
