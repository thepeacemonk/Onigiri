// This file now only handles static UI elements like the sidebar,
// resize handle, and focus label. The high-performance deck list
// logic has been moved to engine.js.

(function () {
    const SIDEBAR_ACTION_MODE_MAP = {
        list: 'full',
        collapsed: 'compact',
        archived: 'minimal',
        ellipsis: 'minimal',
    };

    function normalizeSidebarActionsMode(rawMode) {
        return SIDEBAR_ACTION_MODE_MAP[rawMode] || rawMode || 'full';
    }

    // This function is now globally accessible so the engine can call it.
    window.updateDeckLayouts = function () {
        document.querySelectorAll('.deck-table .decktd').forEach(cell => {
            cell.classList.remove('is-cramped');
            if (cell.scrollWidth > cell.clientWidth) {
                cell.classList.add('is-cramped');
            }
        });
        updateSidebarOverflowState();
    }

    function updateSidebarOverflowState() {
        const sidebar = document.querySelector('.sidebar-left');
        const deckListContainer = document.getElementById('deck-list-container');
        if (!sidebar || !deckListContainer) return;

        const hasOverflow = deckListContainer.scrollHeight > deckListContainer.clientHeight + 1;
        sidebar.classList.toggle('has-deck-browser-overflow', hasOverflow);
    }

    function updateDeckFocusLayout() {
        const sidebar = document.querySelector('.sidebar-left');
        const header = document.getElementById('deck-list-header');
        const expandedContent = sidebar ? sidebar.querySelector('.sidebar-expanded-content') : null;
        const deckListContainer = document.getElementById('deck-list-container');
        const toolbar = sidebar ? sidebar.querySelector('.sidebar-toolbar') : null;

        if (!sidebar || !header || !expandedContent || !deckListContainer) return;
        // Keep the DOM order stable across all modes. Focus Mode is now purely
        // class/CSS driven, which prevents the header/search/ellipsis controls
        // from jumping during refreshes or when Focus Mode is toggled off.
        if (header.parentElement !== expandedContent) {
            expandedContent.insertBefore(header, deckListContainer);
        }

        if (toolbar) ensureToolbarPrecedesHeader(sidebar, toolbar, header);

        requestAnimationFrame(alignSidebarToolbarToDeckHeader);
        requestAnimationFrame(updateSidebarOverflowState);
    }
    window.updateDeckFocusLayout = updateDeckFocusLayout;

    function alignSidebarToolbarToDeckHeader() {
        const sidebar = document.querySelector('.sidebar-left');
        const header = document.getElementById('deck-list-header');
        if (!sidebar || !header || sidebar.classList.contains('sidebar-collapsed')) return;

        const toolbar = sidebar.querySelector('.sidebar-toolbar');
        if (toolbar) {
            toolbar.style.top = '';
        }

        const headerLabel = header.querySelector('h2') || header;
        const sidebarRect = sidebar.getBoundingClientRect();
        const headerRect = headerLabel.getBoundingClientRect();
        if (!sidebarRect.height || !headerRect.height) return;

        const headerCenterY = headerRect.top + (headerRect.height / 2) - sidebarRect.top;
        const setCenterTop = (el, fallbackHeight) => {
            if (!el) return;
            const height = el.offsetHeight || fallbackHeight;
            el.style.top = `${Math.max(0, headerCenterY - (height / 2))}px`;
        };

        setCenterTop(document.getElementById('onigiri-deck-search-bar'), 30);
    }
    window.alignSidebarToolbarToDeckHeader = alignSidebarToolbarToDeckHeader;

    function normalizeSidebarModeControls() {
        const sidebar = document.querySelector('.sidebar-left');
        if (!sidebar) return;

        // The archived control belongs in the dedicated top-right
        // container. Any toolbar copy is legacy/stale and can enter normal
        // flow for a frame during rebuilds, causing a duplicate/jump.
        sidebar.querySelectorAll('.sidebar-toolbar .ellipsis-btn, .sidebar-toolbar .onigiri-ellipsis-toolbar-btn')
            .forEach(btn => btn.remove());

        const directButtons = Array.from(sidebar.children)
            .filter(el => el.classList && el.classList.contains('onigiri-ellipsis-toolbar-btn'));
        directButtons.slice(1).forEach(btn => btn.remove());
    }

    function getDirectSidebarEllipsisButtons(sidebar) {
        return Array.from(sidebar.children)
            .filter(el => el.classList && el.classList.contains('onigiri-ellipsis-toolbar-btn'));
    }

    function ensureToolbarPrecedesHeader(sidebar, toolbar, header) {
        if (!sidebar || !toolbar) return;

        const expandedContent = sidebar.querySelector('.sidebar-expanded-content');
        if (expandedContent && header) {
            if (toolbar.parentElement !== expandedContent || toolbar.nextElementSibling !== header) {
                expandedContent.insertBefore(toolbar, header);
            }
        } else if (toolbar.parentElement !== sidebar) {
            sidebar.appendChild(toolbar);
        }
    }

    function setupSidebarTopRightControls() {
        const sidebar = document.querySelector('.sidebar-left');
        if (!sidebar) return null;
        const header = document.getElementById('deck-list-header');

        let controls = sidebar.querySelector('.sidebar-top-right-controls');
        if (!controls) {
            controls = document.createElement('div');
            controls.className = 'sidebar-top-right-controls';
        }

        if (header && controls.parentElement !== header) {
            header.appendChild(controls);
        } else if (!header && controls.parentElement !== sidebar) {
            sidebar.appendChild(controls);
        }

        const searchBtn = sidebar.querySelector('#onigiri-search-toolbar-btn');
        if (searchBtn && searchBtn.parentElement !== controls) {
            controls.prepend(searchBtn);
        }

        const strayDirectButtons = getDirectSidebarEllipsisButtons(sidebar);
        strayDirectButtons.forEach(btn => {
            if (btn.parentElement !== controls) {
                controls.appendChild(btn);
            }
        });

        const topRightButtons = Array.from(controls.children)
            .filter(el => el.classList && el.classList.contains('onigiri-ellipsis-toolbar-btn'));
        topRightButtons.slice(1).forEach(btn => btn.remove());

        if (searchBtn && searchBtn.parentElement === controls && controls.firstElementChild !== searchBtn) {
            controls.prepend(searchBtn);
        }

        return controls;
    }

    function setupSidebarToolbar() {
        const sidebar = document.querySelector('.sidebar-left');
        if (!sidebar) return;
        normalizeSidebarModeControls();
        const header = document.getElementById('deck-list-header');

        let toolbar = sidebar.querySelector('.sidebar-toolbar');
        if (!toolbar) {
            toolbar = document.createElement('div');
            toolbar.className = 'sidebar-toolbar';
        }
        ensureToolbarPrecedesHeader(sidebar, toolbar, header);
        return toolbar;
    }

    const actionClass = (id) => `action-${String(id).replace(/_/g, '-')}`;

    function setupActionButtons() {
        // Check config
        if (typeof window.ONIGIRI_CONFIG === 'undefined') return;

        const sidebarActionsMode = normalizeSidebarActionsMode(window.ONIGIRI_CONFIG.sidebarActionsMode);

        // Only show toolbar icons if mode is 'compact'
        if (sidebarActionsMode !== 'compact') {
            return;
        }

        const toolbar = setupSidebarToolbar();
        if (!toolbar) return;

        const pkg = window.ONIGIRI_CONFIG.addonPackage || '1011095603';
        const iconBase = `/_addons/${pkg}/system_files/system_icons/`;
        const userIconBase = `/_addons/${pkg}/user_files/icons/`;
        const compactIcons = window.ONIGIRI_CONFIG.compactIcons || {};

        // Map action id -> default system icon filename
        const defaultIcons = {
            'add': 'add.svg',
            'browse': 'browse.svg',
            'stats': 'stats.svg',
            'sync': 'sync.svg',
            'settings': 'settings.svg',
            'gamification': 'games.svg',
            'more': 'more.svg',
            'get_shared': 'get_shared.svg',
            'create_deck': 'create_deck.svg',
            'import_file': 'import_file.svg',
        };
        const defaultIconUrl = (id) => `${iconBase}${defaultIcons[id] || id + '.svg'}`;

        // Primary group: main actions (left side)
        const primaryActions = [
            { id: 'add', cmd: 'add', title: 'Add' },
            { id: 'browse', cmd: 'browse', title: 'Browser' },
            { id: 'stats', cmd: 'stats', title: 'Stats' },
            { id: 'sync', cmd: 'sync', title: 'Sync' },
        ];

        // Secondary group: utility/settings (right side)
        const secondaryActions = [
            { id: 'settings', cmd: 'openOnigiriSettings', title: 'Settings' },
            { id: 'more', cmd: null, title: 'More' }
        ];

        // Ensure the two sub-groups exist
        let primaryGroup = toolbar.querySelector('.toolbar-group-primary');
        if (!primaryGroup) {
            primaryGroup = document.createElement('div');
            primaryGroup.className = 'toolbar-group-primary';
            toolbar.appendChild(primaryGroup);
        }

        let secondaryGroup = toolbar.querySelector('.toolbar-group-secondary');
        if (!secondaryGroup) {
            secondaryGroup = document.createElement('div');
            secondaryGroup.className = 'toolbar-group-secondary';
            toolbar.appendChild(secondaryGroup);
        }

        function makeBtn(action, container) {
            const customFile = compactIcons[action.id];
            const iconUrl = customFile
                ? `${userIconBase}${customFile}`
                : defaultIconUrl(action.id);

            let btn = container.querySelector(`.action-btn.${actionClass(action.id)}`);
            if (!btn) {
                btn = document.createElement('div');
                btn.className = `action-btn ${actionClass(action.id)}`;
                container.appendChild(btn);
            } else if (btn.parentElement !== container) {
                container.appendChild(btn);
            }

            btn.title = action.title;
            btn.innerHTML = `<i class="action-icon" style="mask-image: url('${iconUrl}'); -webkit-mask-image: url('${iconUrl}');"></i>`;

            if (!btn.dataset.onigiriBound) {
                btn.dataset.onigiriBound = 'true';
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (typeof btn.blur === 'function') btn.blur();
                    if (action.id === 'more') {
                        toggleMoreMenu();
                        return;
                    }
                    if (typeof pycmd === 'function') {
                        pycmd(action.cmd);
                    }
                });
            }

            if (action.id === 'sync') {
                const syncStatus = typeof window.getOnigiriSyncStatus === 'function'
                    ? window.getOnigiriSyncStatus()
                    : 'none';
                if (typeof applySyncStatusClasses === 'function') {
                    applySyncStatusClasses(btn, syncStatus);
                }
            }
        }

        primaryActions.forEach(action => makeBtn(action, primaryGroup));
        secondaryActions.forEach(action => makeBtn(action, secondaryGroup));

        setupMoreDropdown(toolbar, userIconBase, compactIcons, defaultIconUrl);
        orderCollapsedToolbarButtons(toolbar);
    }

    function setupMoreDropdown(toolbar, userIconBase, compactIcons, defaultIconUrl) {
        const old = toolbar.querySelector('.more-dropdown-menu');
        if (old) old.remove();

        const moreBtn = toolbar.querySelector('.action-more');
        if (!moreBtn) return;

        // Remove any previously created inline more-items
        toolbar.querySelectorAll('.action-btn.more-item').forEach(el => el.remove());

        const items = [
            { label: 'Get Shared', id: 'get_shared', cmd: 'shared' },
            { label: 'Create Deck', id: 'create_deck', cmd: 'onigiri_create_deck' },
            { label: 'Import File', id: 'import_file', cmd: 'import' },
            { label: 'Onigiri Games', id: 'gamification', cmd: 'openGamificationSettings' }
        ];

        // Insert the 3 inline buttons right after the More button
        let insertAfter = moreBtn;
        items.forEach(item => {
            const customFile = (compactIcons || {})[item.id];
            const iconUrl = customFile
                ? `${userIconBase}${customFile}`
                : defaultIconUrl(item.id);

            const btn = document.createElement('div');
            btn.className = `action-btn more-item ${actionClass(item.id)}`;
            btn.title = item.label;
            btn.dataset.command = item.cmd;
            btn.dataset.label = item.label;
            btn.dataset.iconUrl = iconUrl;
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

    function orderCollapsedToolbarButtons(toolbar) {
        if (!toolbar) return;

        let secondaryGroup = toolbar.querySelector('.toolbar-group-secondary');
        if (!secondaryGroup) {
            secondaryGroup = document.createElement('div');
            secondaryGroup.className = 'toolbar-group-secondary';
            toolbar.appendChild(secondaryGroup);
        }

        const orderedControls = [
            toolbar.querySelector('.action-settings'),
            ...Array.from(toolbar.querySelectorAll('.action-btn.more-item')),
            toolbar.querySelector('.action-more'),
        ].filter(Boolean);

        orderedControls.forEach(control => secondaryGroup.appendChild(control));
    }

    function closeCollapsedMoreMenu() {
        const menu = document.getElementById('onigiri-collapsed-more-menu');
        const wasOpen = !!menu;
        if (menu) menu.remove();

        document.querySelectorAll('.sidebar-toolbar .action-more.more-expanded')
            .forEach(btn => btn.classList.remove('more-expanded'));

        return wasOpen;
    }
    window.closeOnigiriCollapsedMoreMenu = closeCollapsedMoreMenu;

    function toggleMoreMenu() {
        const toolbar = document.querySelector('.sidebar-toolbar');
        if (!toolbar) return;
        const moreBtn = toolbar.querySelector('.action-more');
        if (!moreBtn) return;
        const existing = document.getElementById('onigiri-collapsed-more-menu');
        if (existing) {
            closeCollapsedMoreMenu();
            return;
        }

        if (window.OnigiriEngine) {
            if (typeof window.OnigiriEngine.closeDeckContextMenu === 'function') {
                window.OnigiriEngine.closeDeckContextMenu();
            }
            if (typeof window.OnigiriEngine.closeOrganiseMenu === 'function') {
                window.OnigiriEngine.closeOrganiseMenu();
            }
            if (typeof window.OnigiriEngine.closeEllipsisMenu === 'function') {
                window.OnigiriEngine.closeEllipsisMenu();
            }
        }

        const items = Array.from(toolbar.querySelectorAll('.action-btn.more-item'));
        if (!items.length) return;

        const menu = document.createElement('div');
        menu.id = 'onigiri-collapsed-more-menu';

        items.forEach(source => {
            const item = document.createElement('div');
            item.className = source.className
                .split(/\s+/)
                .filter(Boolean)
                .filter(cls => cls !== 'action-btn' && cls !== 'more-item')
                .concat('onigiri-ellipsis-item')
                .join(' ');

            const icon = document.createElement('i');
            icon.className = 'icon';
            let maskImage = '';
            if (source.dataset.iconUrl) {
                maskImage = `url("${source.dataset.iconUrl}")`;
            } else {
                const sourceIcon = source.querySelector('.action-icon');
                if (sourceIcon) {
                    const sourceStyle = window.getComputedStyle(sourceIcon);
                    maskImage = sourceIcon.style.maskImage
                        || sourceIcon.style.webkitMaskImage
                        || sourceStyle.maskImage
                        || sourceStyle.webkitMaskImage;
                }
            }
            if (maskImage && maskImage !== 'none') {
                icon.style.maskImage = maskImage;
                icon.style.webkitMaskImage = maskImage;
            }

            const label = document.createElement('span');
            label.textContent = source.dataset.label || source.title || '';

            item.appendChild(icon);
            item.appendChild(label);
            item.addEventListener('click', (e) => {
                e.stopPropagation();
                menu.remove();
                moreBtn.classList.remove('more-expanded');
                if (typeof pycmd === 'function' && source.dataset.command) {
                    pycmd(source.dataset.command);
                }
            });
            menu.appendChild(item);
        });

        document.body.appendChild(menu);

        const rect = moreBtn.getBoundingClientRect();
        const menuRect = menu.getBoundingClientRect();
        const viewportPadding = 8;
        const left = Math.max(viewportPadding, rect.left);
        const top = Math.max(viewportPadding, rect.top - menuRect.height - 6);
        menu.style.left = `${left}px`;
        menu.style.top = `${top}px`;

        moreBtn.classList.add('more-expanded');

        setTimeout(() => {
            document.addEventListener('click', function dismiss(e) {
                if (!menu.contains(e.target) && !moreBtn.contains(e.target)) {
                    closeCollapsedMoreMenu();
                    document.removeEventListener('click', dismiss);
                }
            });
        }, 0);
    }

    const managedHoverSelectors = [
        '.rl-nav-btn',
        '.sidebar-toolbar .action-btn'
    ];
    const managedHoverSelector = managedHoverSelectors.join(',');
    const managedHoverActiveSelector = managedHoverSelectors
        .map(selector => `${selector}.is-true-hover`)
        .join(',');

    function clearManagedHoverStates() {
        document.querySelectorAll(managedHoverActiveSelector).forEach(el => {
            el.classList.remove('is-true-hover');
        });
    }

    function bindManagedHoverState(root) {
        const scope = root && root.querySelectorAll ? root : document;
        scope.querySelectorAll(managedHoverSelector).forEach(el => {
            if (el.dataset.onigiriManagedHover) return;
            el.dataset.onigiriManagedHover = 'true';

            el.addEventListener('mouseenter', () => {
                el.classList.add('is-true-hover');
            });
            el.addEventListener('mouseleave', () => {
                el.classList.remove('is-true-hover');
            });
        });
    }

    function setupManagedHoverStates() {
        bindManagedHoverState(document);
        if (document.documentElement.dataset.onigiriHoverManager) return;
        document.documentElement.dataset.onigiriHoverManager = 'true';

        window.addEventListener('focus', clearManagedHoverStates);
        document.addEventListener('visibilitychange', clearManagedHoverStates);
        document.addEventListener('mouseleave', clearManagedHoverStates);
    }

    function setupDeckFocusLabel() {
        const sidebar = document.querySelector('.sidebar-left');
        if (!sidebar) return;

        const header = document.getElementById('deck-list-header');
        if (!header) return;
        const label = header.querySelector('h2');
        if (!label) return;
        const container = document.querySelector('.container.modern-main-menu');
        if (!container) return;
        const CYCLE_STATE_KEY = 'onigiri_decks_header_cycle_state';

        if (!sidebar.dataset.onigiriBaseSidebarOnly) {
            sidebar.dataset.onigiriBaseSidebarOnly = sidebar.classList.contains('sidebar-only-mode') ? '1' : '0';
        }

        document.querySelectorAll('.deck-focus-btn, .deck-header-focus-btn').forEach(btn => btn.remove());
        label.classList.add('deck-focus-label');
        label.setAttribute('role', 'button');
        label.setAttribute('tabindex', '0');
        label.title = 'Focus on Decks';

        const saveCycleState = (state) => {
            try {
                sessionStorage.setItem(CYCLE_STATE_KEY, String(state));
            } catch (_) {}
        };

        const restoreBaseSidebarOnly = () => {
            sidebar.classList.toggle('sidebar-only-mode', sidebar.dataset.onigiriBaseSidebarOnly === '1');
        };

        const saveFocusState = (isFocused) => {
            if (typeof pycmd === 'function') {
                pycmd(`saveDeckFocusState:${isFocused}`);
            }
        };

        const applyDeckHeaderState = (state, options) => {
            const opts = options || {};
            const nextState = Number.isFinite(state) ? Math.max(0, Math.min(3, state)) : 0;
            const isFocusMode = nextState === 1 || nextState === 2;
            const isTemporarySidebarOnly = nextState === 2 || nextState === 3;

            sidebar.classList.toggle('deck-focus-mode', isFocusMode);
            container.classList.toggle('onigiri-cycle-sidebar-only', isTemporarySidebarOnly);
            if (isTemporarySidebarOnly) {
                sidebar.classList.add('sidebar-only-mode');
            } else {
                restoreBaseSidebarOnly();
            }

            header.classList.toggle('deck-focus-active', isFocusMode);
            header.dataset.onigiriDeckCycleState = String(nextState);
            saveCycleState(nextState);

            if (typeof label.blur === 'function') label.blur();
            updateDeckFocusLayout();
            requestAnimationFrame(alignSidebarToolbarToDeckHeader);
            requestAnimationFrame(updateSidebarOverflowState);
            if (window.OnigiriEngine && typeof window.OnigiriEngine.scheduleDeckNameOverflowRefresh === 'function') {
                window.OnigiriEngine.scheduleDeckNameOverflowRefresh();
            }

            if (opts.persistFocus !== false) {
                saveFocusState(isFocusMode);
            }
        };

        const currentDeckHeaderState = () => {
            if (container.classList.contains('onigiri-cycle-sidebar-only')) {
                return sidebar.classList.contains('deck-focus-mode') ? 2 : 3;
            }
            return sidebar.classList.contains('deck-focus-mode') ? 1 : 0;
        };

        const cycleDeckHeaderState = (e) => {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            applyDeckHeaderState((currentDeckHeaderState() + 1) % 4);
        };

        if (!label.dataset.onigiriFocusToggleBound) {
            label.dataset.onigiriFocusToggleBound = 'true';
            label.addEventListener('click', cycleDeckHeaderState);
            label.addEventListener('keydown', (e) => {
                if (e.key !== 'Enter' && e.key !== ' ') return;
                cycleDeckHeaderState(e);
            });
        }

        let restoredState = sidebar.classList.contains('deck-focus-mode') ? 1 : 0;
        try {
            const storedState = Number.parseInt(sessionStorage.getItem(CYCLE_STATE_KEY) || '', 10);
            if (storedState === 2 || storedState === 3) {
                restoredState = storedState;
            } else if (storedState === 1 && sidebar.classList.contains('deck-focus-mode')) {
                restoredState = 1;
            } else if (storedState === 0 && !sidebar.classList.contains('deck-focus-mode')) {
                restoredState = 0;
            }
        } catch (_) {}
        applyDeckHeaderState(restoredState, { persistFocus: false });
    }

    function setupResizeHandle() {
        const handle = document.querySelector('.resize-handle');
        const sidebarEl = document.querySelector('.sidebar-left');
        if (!handle || !sidebarEl || handle.dataset.onigiriSetup) return;
        handle.dataset.onigiriSetup = 'true';

        const setSidebarFixedWidth = (width) => {
            sidebarEl.style.setProperty('width', `${width}px`, 'important');
        };

        let hitbox = handle.querySelector('.resize-handle-hitbox');
        if (!hitbox) {
            hitbox = document.createElement('div');
            hitbox.className = 'resize-handle-hitbox';
            handle.appendChild(hitbox);
        }

        if (!handle.querySelector('.resize-handle-indicator')) {
            const indicator = document.createElement('div');
            indicator.className = 'resize-handle-indicator';
            handle.appendChild(indicator);
        }

        let isResizing = false;
        let startX, startWidth, animationFrameId = null, lastClientX = 0, lastWidth = 0;
        let isCentered = false;

        const updateSidebarWidth = () => {
            const deltaX = lastClientX - startX;
            const effectiveDelta = isCentered ? (deltaX * 2) : deltaX;
            let newWidth = startWidth + effectiveDelta;
            if (newWidth < 325) newWidth = 325;

            if (Math.abs(newWidth - lastWidth) > 0.5) {
                setSidebarFixedWidth(newWidth);
                lastWidth = newWidth;
                if (typeof window.onigiriUpdateSidebarEdgeToggle === 'function') {
                    window.onigiriUpdateSidebarEdgeToggle();
                }
                if (typeof window.updateDeckLayouts === 'function') {
                    window.updateDeckLayouts();
                }
                if (window.OnigiriEngine && typeof window.OnigiriEngine.scheduleDeckNameOverflowRefresh === 'function') {
                    window.OnigiriEngine.scheduleDeckNameOverflowRefresh();
                }
            }
            animationFrameId = null;
        };

        const mousedownHandler = (e) => {
            if (e.button !== 0) return;
            isResizing = true;
            startX = e.clientX;
            lastClientX = e.clientX;

            const rect = sidebarEl.getBoundingClientRect();
            startWidth = rect.width;
            lastWidth = startWidth;

            isCentered = sidebarEl.classList.contains('sidebar-only-mode');
            if (!isCentered && sidebarEl.parentElement) {
                isCentered = window.getComputedStyle(sidebarEl.parentElement).justifyContent.includes('center');
            }

            setSidebarFixedWidth(startWidth);
            sidebarEl.style.setProperty('max-width', 'none', 'important');

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
                setSidebarFixedWidth(finalWidth);
                if (typeof window.onigiriUpdateSidebarEdgeToggle === 'function') {
                    window.onigiriUpdateSidebarEdgeToggle();
                }
                if (typeof window.updateDeckLayouts === 'function') {
                    window.updateDeckLayouts();
                }
                if (window.OnigiriEngine && typeof window.OnigiriEngine.scheduleDeckNameOverflowRefresh === 'function') {
                    window.OnigiriEngine.scheduleDeckNameOverflowRefresh();
                }
                if (typeof pycmd === 'function') pycmd(`saveSidebarWidth:${finalWidth}`);
            }
        };

        handle._resizeHandlers = {
            hitbox,
            mousedown: mousedownHandler,
            documentMousemove: documentMousemoveHandler,
            documentMouseup: documentMouseupHandler
        };

        hitbox.addEventListener('mousedown', mousedownHandler);
        document.addEventListener('mousemove', documentMousemoveHandler);
        document.addEventListener('mouseup', documentMouseupHandler);
    }

    function refreshResizeHandle() {
        const handle = document.querySelector('.resize-handle');
        if (!handle || !handle._resizeHandlers) return;

        const handlers = handle._resizeHandlers;
        handlers.hitbox.removeEventListener('mousedown', handlers.mousedown);
        document.removeEventListener('mousemove', handlers.documentMousemove);
        document.removeEventListener('mouseup', handlers.documentMouseup);

        delete handle.dataset.onigiriSetup;
        setupResizeHandle();
    }

    function init() {
        normalizeSidebarModeControls();
        setupSidebarTopRightControls();

        const sidebar = document.querySelector('.sidebar-left.skeleton-loading');
        if (sidebar) {
            setTimeout(() => sidebar.classList.remove('skeleton-loading'), 150);
        }

        const sidebarEl = document.querySelector('.sidebar-left');
        const edgeToggleBtn = document.getElementById('onigiri-sidebar-edge-toggle');
        const edgeToggleZone = document.querySelector('.sidebar-edge-toggle-zone');
        const actionsMode = normalizeSidebarActionsMode(
            window.ONIGIRI_CONFIG ? window.ONIGIRI_CONFIG.sidebarActionsMode : 'full'
        );
        if (sidebarEl) {
            sidebarEl.classList.toggle('sidebar-actions-full', actionsMode === 'full');
            sidebarEl.classList.toggle('sidebar-actions-compact', actionsMode === 'compact');
            sidebarEl.classList.toggle('sidebar-mode-minimal', actionsMode === 'minimal');
        }

        // Track the width set by the resize handle so we can restore it on expand
        let _savedSidebarWidth = null;
        let _edgeToggleCollapseLocked = false;
        const collapsedEdgeTogglePosition = {
            left: 24,
            top: 24,
            zoneLeft: 8,
            zoneTop: 16,
        };

        function applyCollapsedEdgeTogglePosition() {
            if (edgeToggleBtn) {
                edgeToggleBtn.style.left = `${collapsedEdgeTogglePosition.left}px`;
                edgeToggleBtn.style.top = `${collapsedEdgeTogglePosition.top}px`;
                edgeToggleBtn.classList.add('is-collapsed');
            }
            if (edgeToggleZone) {
                edgeToggleZone.style.left = `${collapsedEdgeTogglePosition.zoneLeft}px`;
                edgeToggleZone.style.top = `${collapsedEdgeTogglePosition.zoneTop}px`;
            }
        }

        function updateSidebarEdgeToggle() {
            if (!edgeToggleBtn || !sidebarEl) return;
            const isCollapsed = sidebarEl.classList.contains('sidebar-collapsed') || _edgeToggleCollapseLocked;
            const rect = sidebarEl.getBoundingClientRect();
            const btnWidth = edgeToggleBtn.offsetWidth || 24;
            const left = isCollapsed ? collapsedEdgeTogglePosition.left : Math.max(0, rect.right - Math.round(btnWidth / 2));
            const top = isCollapsed ? collapsedEdgeTogglePosition.top : Math.max(0, rect.top + 24);

            edgeToggleBtn.style.left = `${left}px`;
            edgeToggleBtn.style.top = `${top}px`;
            edgeToggleBtn.classList.toggle('is-collapsed', isCollapsed);
            edgeToggleBtn.title = isCollapsed ? 'Expand sidebar' : 'Collapse sidebar';
            edgeToggleBtn.setAttribute('aria-label', edgeToggleBtn.title);

            if (edgeToggleZone) {
                const zoneLeft = isCollapsed ? collapsedEdgeTogglePosition.zoneLeft : Math.max(0, left - 28);
                edgeToggleZone.style.left = `${zoneLeft}px`;
                edgeToggleZone.style.top = `${isCollapsed ? collapsedEdgeTogglePosition.zoneTop : Math.max(0, top - 8)}px`;
            }
        }
        window.onigiriUpdateSidebarEdgeToggle = updateSidebarEdgeToggle;

        function collapseSidebar() {
            _edgeToggleCollapseLocked = true;
            applyCollapsedEdgeTogglePosition();

            // Save the current sidebar width so expanding restores the user's resize.
            const inlineWidth = sidebarEl.style.width;
            if (inlineWidth) _savedSidebarWidth = inlineWidth;
            sidebarEl.style.removeProperty('width');
            sidebarEl.style.removeProperty('max-width');
            sidebarEl.classList.add('sidebar-collapsed');
            updateSidebarEdgeToggle();
            if (typeof pycmd === 'function') pycmd('saveSidebarState:true');
        }

        function expandSidebar() {
            _edgeToggleCollapseLocked = false;
            sidebarEl.classList.remove('sidebar-collapsed');
            // Restore the previously saved width if we had one
            if (_savedSidebarWidth) {
                const restoredWidth = parseFloat(_savedSidebarWidth);
                if (Number.isFinite(restoredWidth) && restoredWidth > 0) {
                    sidebarEl.style.setProperty('width', `${restoredWidth}px`, 'important');
                }
            }
            updateSidebarEdgeToggle();
            if (typeof pycmd === 'function') pycmd('saveSidebarState:false');
        }

        if (edgeToggleBtn && sidebarEl) {
            updateSidebarEdgeToggle();
            edgeToggleBtn.addEventListener('click', () => {
                if (sidebarEl.classList.contains('sidebar-collapsed')) {
                    expandSidebar();
                } else {
                    collapseSidebar();
                }
                edgeToggleBtn.blur();
            });
            window.addEventListener('resize', updateSidebarEdgeToggle);
            if (typeof ResizeObserver !== 'undefined') {
                const edgeToggleObserver = new ResizeObserver(updateSidebarEdgeToggle);
                edgeToggleObserver.observe(sidebarEl);
                const toolbarAlignObserver = new ResizeObserver(() => requestAnimationFrame(alignSidebarToolbarToDeckHeader));
                toolbarAlignObserver.observe(sidebarEl);
                const deckListContainer = document.getElementById('deck-list-container');
                if (deckListContainer) {
                    const deckOverflowObserver = new ResizeObserver(() => requestAnimationFrame(updateSidebarOverflowState));
                    deckOverflowObserver.observe(deckListContainer);
                }
            }
            requestAnimationFrame(updateSidebarEdgeToggle);
        }

        const deckListContainer = document.getElementById('deck-list-container');
        if (deckListContainer) {
            deckListContainer.addEventListener('scroll', updateSidebarOverflowState, { passive: true });
            if (typeof MutationObserver !== 'undefined') {
                const overflowMutationObserver = new MutationObserver(() => requestAnimationFrame(updateSidebarOverflowState));
                overflowMutationObserver.observe(deckListContainer, { childList: true, subtree: true });
            }
        }

        setupResizeHandle();
        setupDeckFocusLabel();
        // Edit mode and Transfer buttons removed — drag-and-drop is always-on
        setupActionButtons();
        setupManagedHoverStates();
        updateDeckLayouts();
        updateSidebarOverflowState();
        updateDeckFocusLayout();
        requestAnimationFrame(alignSidebarToolbarToDeckHeader);
        requestAnimationFrame(updateSidebarOverflowState);
        window.addEventListener('resize', () => requestAnimationFrame(alignSidebarToolbarToDeckHeader));
        window.addEventListener('resize', () => requestAnimationFrame(updateSidebarOverflowState));
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
