// Onigiri Performance Engine
const ONIGIRI_EMOJI_SPRITE_ASSETS = {
    "🤍": "heart_white.svg",
    "🧼": "soap.svg",
    "💀": "skull.svg",
    "📄": "paper.svg",
    "📝": "memo.svg",
    "📖": "open_book.svg",
    "🍙": "onigiri.svg",
    "🩷": "heart_light_pink.svg",
    "💕": "two_hearts.svg",
    "🌸": "cherry_blossom.svg",
    "🌷": "tulip.svg",
    "🪷": "lotus.svg",
    "🧠": "brain.svg",
    "🦑": "squid.svg",
    "❤️": "heart_red.svg",
    "🫀": "anatomical_heart.svg",
    "📕": "red_book.svg",
    "🔥": "fire.svg",
    "🍉": "watermelon.svg",
    "🧡": "heart_orange.svg",
    "🍊": "tangerine.svg",
    "🍹": "tropical_drink.svg",
    "🧇": "waffle.svg",
    "🍍": "pineapple.svg",
    "⭐": "star.svg",
    "✨": "sparkle.svg",
    "⚡": "bolt.svg",
    "🏆": "trophy.svg",
    "💛": "heart_yellow.svg",
    "📙": "yellow_book.svg",
    "✏️": "pen.svg",
    "🍋‍🟩": "lime.svg",
    "💚": "heart_green.svg",
    "📗": "green_book.svg",
    "🌱": "emoji.svg",
    "🍀": "four_leaf_clover.svg",
    "🍃": "leaf_fluttering_in_wind.svg",
    "🌳": "deciduous_tree.svg",
    "🌲": "evergreen_tree.svg",
    "🎄": "christmas_tree.svg",
    "🍵": "teacup_without_handle.svg",
    "💙": "blue_heart.svg",
    "📘": "blue_book.svg",
    "💧": "droplet.svg",
    "💎": "gem_stone.svg",
    "🧪": "test_tube.svg",
    "🍇": "grapes.svg",
    "🔬": "microscope.svg",
    "💻": "computer.svg",
    "📟": "pager.svg",
    "🎮": "videogame.svg",
    "🍡": "dango.svg",
    "📚": "books.svg",
    "🗺️": "world_map.svg",
};

function onigiriEmojiSpriteUrl(iconVal) {
    if (!iconVal || !iconVal.startsWith('emoji:')) return '';
    const emoji = iconVal.replace('emoji:', '');
    const normalizedEmoji = emoji.replace(/[\ufe0e\ufe0f]/g, '');
    let asset = ONIGIRI_EMOJI_SPRITE_ASSETS[emoji] || ONIGIRI_EMOJI_SPRITE_ASSETS[normalizedEmoji];
    if (!asset) {
        for (const [key, value] of Object.entries(ONIGIRI_EMOJI_SPRITE_ASSETS)) {
            if (key.replace(/[\ufe0e\ufe0f]/g, '') === normalizedEmoji) {
                asset = value;
                break;
            }
        }
    }
    if (!asset) return '';
    const pkg = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.addonPackage) || '1011095603';
    return `/_addons/${pkg}/system_files/emojis/${asset}`;
}

window.OnigiriEngine = {
    currentHoveredRow: null,
    _dnd: null,
    _searchDebounceTimer: null,
    _multiSelectedDecks: new Set(),
    _lastSelectedDid: null,
    _profileResizeTimer: null,

    init: function () {
        this.deckListContainer = document.getElementById('deck-list-container');
        if (!this.deckListContainer) {
            return;
        }

        this.bindEvents();
        this.bindDeckSearchControls();
        this.observeMutations();
        this.bindGlobalSelectionKeys();
        this.initSidebarProfileMetrics();

        // Initial processing of already loaded nodes
        this.processNewNodes(document.querySelectorAll('tr.deck, a.collapse'));
        this.restoreScrollPosition();
    },

    systemIconUrl: function (filename) {
        const pkg = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.addonPackage) || '';
        if (!pkg || !filename) return '';
        const aliases = {
            'add_subdeck.svg': 'add-subdeck.svg',
            'create_deck.svg': 'add-deck.svg',
            'filtered_deck.svg': 'filtered-deck.svg',
        };
        return `/_addons/${pkg}/system_files/system_icons/unavailable_for_users/${aliases[filename] || filename}`;
    },

    createMaskIcon: function (iconUrl, options = {}) {
        const icon = document.createElement('span');
        icon.className = options.className || '';
        const size = options.size || 16;
        icon.style.cssText = [
            'display:inline-block',
            `width:${size}px`,
            `height:${size}px`,
            'flex:0 0 auto',
            `background:${options.color || 'currentColor'}`,
            `mask:url("${iconUrl}") center / contain no-repeat`,
            `-webkit-mask:url("${iconUrl}") center / contain no-repeat`,
        ].join(';');
        return icon;
    },

    preloadMaskIcons: function (urls) {
        (urls || []).forEach((url) => {
            if (!url) return;
            const img = new Image();
            img.decoding = 'async';
            img.src = url;
        });
    },

    escapeSelectorValue: function (value) {
        if (window.CSS && typeof CSS.escape === 'function') return CSS.escape(String(value));
        return String(value).replace(/["\\]/g, '\\$&');
    },

    _beginOverrideState: function (className) {
        if (className) document.body.classList.add(className);
    },

    _endOverrideState: function (className) {
        if (className) document.body.classList.remove(className);
    },

    _clearAllRowVisualStates: function () {
        document.querySelectorAll('tr.deck').forEach(row => {
            row.classList.remove(
                'is-hovered',
                'ctx-row-active',
                'drag-over-target',
                'drop-before',
                'drop-after',
                'is-dragging',
                'dragging',
                'drag-over-before',
                'drag-over-after',
                'drag-over-nest'
            );
        });
        this.currentHoveredRow = null;
    },

    clearDialogFocus: function () {
        this._clearAllRowVisualStates();
        document.body.classList.remove('dialog-focus');
    },

    closestElement: function (target, selector) {
        return target && target.closest ? target.closest(selector) : null;
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
        this.updateMultiSelectionVisuals();

        if (typeof window.updateDeckLayouts === 'function') {
            window.updateDeckLayouts();
        }

        setTimeout(() => {
            this.deckListContainer.classList.remove('scroll-restoring');
        }, 50);
    },

    getSidebarProfileBar: function () {
        return document.querySelector('.sidebar-expanded-content > .profile-bar, .sidebar-expanded-content .profile-bar');
    },

    updateSidebarProfileMetrics: function () {
        const profileBar = this.getSidebarProfileBar();
        if (!profileBar) return;

        const header = document.getElementById('deck-list-header');
        const fallbackWidth = profileBar.parentElement ? profileBar.parentElement.clientWidth : profileBar.offsetWidth;
        const headerWidth = header ? Math.floor(header.getBoundingClientRect().width) : fallbackWidth;
        const width = Math.max(0, headerWidth || fallbackWidth || 0);
        profileBar.style.setProperty('--onigiri-deck-header-width', `${width}px`);
        if (width) profileBar.style.width = `${width}px`;
    },

    initSidebarProfileMetrics: function () {
        this.updateSidebarProfileMetrics();
        window.addEventListener('resize', () => {
            window.clearTimeout(this._profileResizeTimer);
            this._profileResizeTimer = window.setTimeout(() => this.updateSidebarProfileMetrics(), 80);
        });

        if (typeof ResizeObserver !== 'undefined') {
            const observer = new ResizeObserver(() => {
                window.clearTimeout(this._profileResizeTimer);
                this._profileResizeTimer = window.setTimeout(() => this.updateSidebarProfileMetrics(), 16);
            });
            
            window.setTimeout(() => {
                const sidebar = document.querySelector('.sidebar-left');
                if (sidebar) observer.observe(sidebar);
                
                const header = document.getElementById('deck-list-header');
                if (header) observer.observe(header);
            }, 0);
        }

        window.setTimeout(() => this.updateSidebarProfileMetrics(), 120);
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

    bindGlobalSelectionKeys: function () {
        if (document.body.dataset.onigiriMultiSelectKeysBound) return;
        document.body.dataset.onigiriMultiSelectKeysBound = 'true';
        document.addEventListener('keydown', (event) => {
            const target = event.target;
            const isTyping = target && (
                target.tagName === 'INPUT' ||
                target.tagName === 'TEXTAREA' ||
                target.isContentEditable
            );
            if (isTyping) return;
            if (event.key === 'Escape' && this._multiSelectedDecks.size > 0) {
                event.preventDefault();
                this.clearMultiSelection();
            }
            if ((event.ctrlKey || event.metaKey) && String(event.key).toLowerCase() === 'a') {
                if (this.selectAllDecks()) event.preventDefault();
            }
        }, true);
    },

    visibleDeckRows: function () {
        if (!this.deckListContainer) return [];
        return Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'));
    },

    selectAllDecks: function () {
        const rows = this.visibleDeckRows();
        if (!rows.length) return false;
        this._multiSelectedDecks.clear();
        rows.forEach(row => this._multiSelectedDecks.add(row.dataset.did));
        this._lastSelectedDid = rows[rows.length - 1].dataset.did;
        this.updateMultiSelectionVisuals();
        return true;
    },

    clearMultiSelection: function () {
        this._multiSelectedDecks.clear();
        this._lastSelectedDid = null;
        this.updateMultiSelectionVisuals();
    },

    toggleMultiSelection: function (row, event) {
        if (!row || !row.dataset.did) return;
        const rows = this.visibleDeckRows();
        const did = row.dataset.did;

        if (event.shiftKey && this._lastSelectedDid) {
            const start = rows.findIndex(item => item.dataset.did === this._lastSelectedDid);
            const end = rows.indexOf(row);
            if (start !== -1 && end !== -1) {
                const lo = Math.min(start, end);
                const hi = Math.max(start, end);
                for (let index = lo; index <= hi; index += 1) {
                    this._multiSelectedDecks.add(rows[index].dataset.did);
                }
            }
        } else if (this._multiSelectedDecks.has(did)) {
            this._multiSelectedDecks.delete(did);
        } else {
            this._multiSelectedDecks.add(did);
        }

        this._lastSelectedDid = did;
        this.updateMultiSelectionVisuals();
    },

    updateMultiSelectionVisuals: function () {
        const selected = this._multiSelectedDecks;
        document.querySelectorAll('tr.deck[data-did]').forEach(row => {
            row.classList.toggle('is-multi-selected', selected.has(row.dataset.did));
        });
        document.body.classList.toggle('has-multi-select', selected.size > 0);
        this.updateMultiSelectBadge();
    },

    updateMultiSelectBadge: function () {
        let badge = document.getElementById('onigiri-multiselect-badge');
        if (this._multiSelectedDecks.size === 0) {
            if (badge) badge.remove();
            return;
        }
        if (!badge) {
            badge = document.createElement('span');
            badge.id = 'onigiri-multiselect-badge';
            badge.setAttribute('role', 'button');
        badge.tabIndex = 0;
        // Set tabindex for accessibility
        try { arguments[0].tabIndex = 0; } catch(e){};
            badge.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                this.clearMultiSelection();
            });
        }
        const actions = document.querySelector('#deck-list-header .deck-header-actions');
        const searchBtn = document.getElementById('onigiri-search-toolbar-btn');
        if (actions && badge.parentElement !== actions) {
            actions.insertBefore(badge, searchBtn && searchBtn.parentElement === actions ? searchBtn : actions.firstChild);
        } else if (!actions && badge.parentElement !== document.body) {
            document.body.appendChild(badge);
        }
        badge.textContent = `${this._multiSelectedDecks.size} selected`;
    },

    handleOrganizingDeckClick: function (event) {
        if (!event || !(event.ctrlKey || event.metaKey || event.shiftKey)) return false;
        const target = event.target;
        if (!target || !target.closest) return false;
        if (target.closest('a.collapse, .opts, .drag-handle, button, input, textarea')) return false;

        const deckRow = target.closest('tr.deck[data-did]');
        if (!deckRow || !this.deckListContainer || !this.deckListContainer.contains(deckRow)) {
            return false;
        }

        event.preventDefault();
        event.stopPropagation();
        if (typeof event.stopImmediatePropagation === 'function') {
            event.stopImmediatePropagation();
        }
        this.toggleMultiSelection(deckRow, event);
        return true;
    },

    /** Binds event listeners to handle interactions. */
    bindEvents: function () {
        if (this.deckListContainer.dataset.engineBound) return;
        this.deckListContainer.dataset.engineBound = 'true';
        this.applyFilterButtonStates();

        // Modifier-key deck selection must run in capture phase so inline deck
        // link handlers never open a deck while the user is organizing rows.
        this.deckListContainer.addEventListener('click', (event) => {
            this.handleOrganizingDeckClick(event);
        }, true);

        // --- Listener: Keep row hovered while mouse is over it ---
        this.deckListContainer.addEventListener('mouseenter', (event) => {
            const deckRow = event.target.closest('tr.deck');
            if (deckRow) {
                if (this.currentHoveredRow && this.currentHoveredRow !== deckRow) {
                    this.currentHoveredRow.classList.remove('is-hovered');
                }
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

        this.deckListContainer.addEventListener('mousemove', (event) => {
            const deckRow = event.target.closest('tr.deck');
            if (deckRow === this.currentHoveredRow) return;
            if (this.currentHoveredRow) {
                this.currentHoveredRow.classList.remove('is-hovered');
            }
            this.currentHoveredRow = deckRow || null;
            if (deckRow) deckRow.classList.add('is-hovered');
        });

        this.deckListContainer.addEventListener('mouseleave', () => {
            if (this.currentHoveredRow) {
                this.currentHoveredRow.classList.remove('is-hovered');
                this.currentHoveredRow = null;
            }
        });

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

            if (event.ctrlKey || event.metaKey || event.shiftKey) {
                event.preventDefault();
                event.stopPropagation();
                this.toggleMultiSelection(deckRow, event);
                return;
            }

            if (this._multiSelectedDecks.size > 0) {
                this.clearMultiSelection();
            }

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

        document.addEventListener('click', (event) => {
            if (this._multiSelectedDecks.size === 0) return;
            if (event.target.closest('#deck-list-container, .onigiri-quick-menu, #onigiri-multiselect-badge')) return;
            this.clearMultiSelection();
        });

        // --- Quick deck context menu ---
        this.deckListContainer.addEventListener('contextmenu', (event) => {
            const deckRow = event.target.closest('tr.deck[data-did]');
            if (!deckRow) return;
            event.preventDefault();
            event.stopPropagation();
            if (this._multiSelectedDecks.size > 1 && this._multiSelectedDecks.has(deckRow.dataset.did)) {
                this.showBulkDeckContextMenu(event.clientX, event.clientY);
                return;
            }
            this.showDeckContextMenu(event.clientX, event.clientY, deckRow.dataset.did);
        });

        if (!document.body.dataset.onigiriFilterStateBound) {
            document.body.dataset.onigiriFilterStateBound = 'true';
            document.addEventListener('click', (event) => {
                const clickable = event.target.closest('[onclick]');
                if (!clickable) return;
                const onclick = clickable.getAttribute('onclick') || '';
                if (onclick.includes('onigiri_filter_favourites') || onclick.includes('onigiri_filter_favorites')) {
                    window.ONIGIRI_CONFIG = window.ONIGIRI_CONFIG || {};
                    window.ONIGIRI_CONFIG.filters = window.ONIGIRI_CONFIG.filters || {};
                    window.ONIGIRI_CONFIG.filters.favorites = !window.ONIGIRI_CONFIG.filters.favorites;
                    this.applyFilterButtonStates();
                } else if (onclick.includes('onigiri_filter_marked')) {
                    window.ONIGIRI_CONFIG = window.ONIGIRI_CONFIG || {};
                    window.ONIGIRI_CONFIG.filters = window.ONIGIRI_CONFIG.filters || {};
                    window.ONIGIRI_CONFIG.filters.marked = !window.ONIGIRI_CONFIG.filters.marked;
                    this.applyFilterButtonStates();
                }
            }, true);
        }

        this._boundDndMove = (event) => this._dndMove(event);
        this._boundDndEnd = (event) => this._dndEnd(event);
    },

    applyFilterButtonStates: function () {
        const filters = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.filters) || {};
        [
            { key: 'favorites', commands: ['onigiri_filter_favourites', 'onigiri_filter_favorites'] },
            { key: 'marked', commands: ['onigiri_filter_marked'] },
        ].forEach(filter => {
            const active = !!filters[filter.key];
            filter.commands.forEach(command => {
                document.querySelectorAll(`[onclick*="${command}"]`).forEach(button => {
                    button.classList.toggle('active', active);
                    button.classList.toggle('checked', active);
                    button.setAttribute('aria-checked', active ? 'true' : 'false');
                });
            });
        });
    },

    _dndCreateGhost: function (row) {
        const rect = row.getBoundingClientRect();
        const cell = row.querySelector('td.decktd');
        const preview = document.createElement('div');
        const typeClasses = Array.from(row.classList).filter(cls => cls.indexOf('is-') === 0);
        const sidebar = document.querySelector('.sidebar-left') || document.body;
        const sidebarStyle = window.getComputedStyle(sidebar);
        const rowStyle = window.getComputedStyle(row);

        const luminanceFromRgb = (value) => {
            const match = String(value || '').match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
            if (!match) return 255;
            return (0.2126 * Number(match[1])) + (0.7152 * Number(match[2])) + (0.0722 * Number(match[3]));
        };
        const sidebarBg = sidebarStyle.backgroundColor || rowStyle.backgroundColor;
        const isDarkPreview = document.body.classList.contains('night-mode')
            || document.body.classList.contains('nightMode')
            || document.documentElement.classList.contains('night-mode')
            || document.documentElement.classList.contains('nightMode')
            || luminanceFromRgb(sidebarBg) < 150;

        const dragBg = (sidebarStyle.getPropertyValue(isDarkPreview ? '--highlight-bg' : '--canvas-inset') || '').trim()
            || (isDarkPreview ? 'rgba(44, 44, 44, 0.98)' : 'rgba(255, 255, 255, 0.98)');
        const dragFg = (sidebarStyle.getPropertyValue('--fg') || rowStyle.color || '').trim()
            || (isDarkPreview ? '#e8e8e8' : '#222222');
        const dragSubtle = (sidebarStyle.getPropertyValue('--fg-subtle') || '').trim()
            || (isDarkPreview ? '#b8b8b8' : '#666666');
        const dragBorder = (sidebarStyle.getPropertyValue('--border') || '').trim()
            || (isDarkPreview ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.1)');

        preview.className = ['onigiri-drag-preview', isDarkPreview ? 'is-dark' : 'is-light', ...typeClasses].join(' ');
        if (row.dataset.did) preview.dataset.did = row.dataset.did;
        preview.style.cssText = [
            'position:fixed',
            'z-index:9998',
            'pointer-events:none',
            `--onigiri-drag-bg:${dragBg}`,
            `--onigiri-drag-fg:${dragFg}`,
            `--onigiri-drag-subtle:${dragSubtle}`,
            `--onigiri-drag-border:${dragBorder}`,
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
        const sourceRows = (this._multiSelectedDecks.size > 1 && this._multiSelectedDecks.has(row.dataset.did))
            ? this.visibleDeckRows().filter(item => this._multiSelectedDecks.has(item.dataset.did))
            : [row];
        const sourceIds = sourceRows.map(item => item.dataset.did);
        sourceRows.forEach(item => item.classList.add('is-dragging'));
        document.body.classList.add('onigiri-is-dragging');
        const ghost = this._dndCreateGhost(row);
        if (sourceIds.length > 1) {
            ghost.classList.add('is-multi-drag');
            const count = document.createElement('span');
            count.className = 'onigiri-drag-count';
            count.textContent = `${sourceIds.length} decks`;
            ghost.appendChild(count);
        }
        document.body.appendChild(ghost);

        this._dnd = {
            sourceRow: row,
            sourceRows,
            sourceIds,
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

        const sourceSet = new Set(state.sourceIds || [state.sourceRow.dataset.did]);
        const rows = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'))
            .filter(row => !sourceSet.has(row.dataset.did));
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
        (state.sourceRows || [state.sourceRow]).forEach(row => row.classList.remove('is-dragging'));
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

        const sourceDids = state.sourceIds || [state.sourceRow.dataset.did];
        const sourceDid = sourceDids[0];
        const targetDid = targetRow.dataset.did;
        if (!sourceDid || !targetDid) return;

        if (state.lastInsertType === 'nest') {
            pycmd('onigiri_drag_drop:' + JSON.stringify({
                source_did: sourceDid,
                source_dids: sourceDids,
                target_did: targetDid,
                type: 'nest',
            }));
            return;
        }

        const allIds = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'))
            .map(row => row.dataset.did);
        const sourceSet = new Set(sourceDids);
        const newOrder = allIds.filter(id => !sourceSet.has(id));
        const targetIndex = newOrder.indexOf(targetDid);
        if (targetIndex === -1) return;
        newOrder.splice(state.lastInsertType === 'before' ? targetIndex : targetIndex + 1, 0, ...sourceDids);
        pycmd('onigiri_drag_drop:' + JSON.stringify({
            source_did: sourceDid,
            source_dids: sourceDids,
            target_did: targetDid,
            type: state.lastInsertType,
            original_order: allIds,
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
        this.updateMultiSelectionVisuals();
    },

    iconUrl: function (name) {
        const pkg = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.addonPackage) || '';
        return pkg ? `/_addons/${pkg}/system_files/system_icons/unavailable_for_users/${name}.svg` : '';
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
        if (item.customNode) {
            row.appendChild(item.customNode);
        } else {
            row.appendChild(item.color ? this.makeMenuDot(item.color) : this.makeMenuIcon(item.icon));
        }
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
            if (item.sortMode) {
                window.ONIGIRI_CONFIG = window.ONIGIRI_CONFIG || {};
                window.ONIGIRI_CONFIG.deckSortMode = item.sortMode;
            }
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
            { label: 'Add Subdeck', icon: 'add-subdeck', command: `onigiri_ctx_subdeck:${did}` },
            { label: 'Move To', icon: 'move_deck', command: `onigiri_ctx_move_to:${did}` },
            { label: 'Change Icon', icon: 'edit_icon', command: `onigiri_ctx_change_icon:${did}` },
            {
                label: isFavorite ? 'Remove Favorite' : 'Favorite',
                icon: isFavorite ? 'star_cancel' : 'star_outline',
                command: `onigiri_toggle_favorite:${did}`,
            },
        ].forEach(item => this.appendMenuItem(menu, item));

        menu.appendChild(document.createElement('hr'));

        const markerColors = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.markerColors) || {};
        const markerIcons = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.markerIcons) || {};
        const markerNames = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.markerNames) || {};
        const markerDefaults = { red: '#ff4d4f', blue: '#4f95ff', green: '#45c878', yellow: '#ffc629' };
        const nameDefaults = { red: 'Red', blue: 'Blue', green: 'Green', yellow: 'Yellow' };
        
        const makeMarkerCustomNode = (key, color) => {
            const iconVal = markerIcons[key] || 'default';
            if (iconVal !== 'default') {
                const el = document.createElement('span');
                el.className = 'quick-menu-color-dot';
                if (iconVal.startsWith('emoji:')) {
                    const spriteUrl = onigiriEmojiSpriteUrl(iconVal);
                    if (spriteUrl) {
                        el.style.backgroundColor = 'transparent';
                        el.style.backgroundImage = `url("${spriteUrl}")`;
                        el.style.backgroundSize = 'contain';
                        el.style.backgroundPosition = 'center';
                        el.style.backgroundRepeat = 'no-repeat';
                        el.style.borderRadius = '0';
                        el.style.boxShadow = 'none';
                    } else {
                        el.style.backgroundColor = 'transparent';
                        el.style.color = color;
                        el.style.fontSize = '14px';
                        el.style.lineHeight = '1';
                        el.style.display = 'inline-flex';
                        el.style.alignItems = 'center';
                        el.style.justifyContent = 'center';
                        el.style.boxShadow = 'none';
                        el.style.width = 'auto';
                        el.style.height = 'auto';
                        el.style.minWidth = 'auto';
                        el.style.minHeight = 'auto';
                        el.textContent = iconVal.replace('emoji:', '');
                    }
                } else {
                    const pkg = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.addonPackage) || '1011095603';
                    const iconUrl = iconVal.startsWith('system:') 
                        ? `/_addons/${pkg}/system_files/system_icons/unavailable_for_users/${iconVal.replace('system:', '')}`
                        : `/_addons/${pkg}/user_files/icons/${iconVal}`;
                    el.style.backgroundColor = color;
                    el.style.maskImage = `url("${iconUrl}")`;
                    el.style.webkitMaskImage = `url("${iconUrl}")`;
                    el.style.maskSize = 'contain';
                    el.style.webkitMaskSize = 'contain';
                    el.style.maskPosition = 'center';
                    el.style.webkitMaskPosition = 'center';
                    el.style.maskRepeat = 'no-repeat';
                    el.style.webkitMaskRepeat = 'no-repeat';
                    el.style.borderRadius = '0';
                }
                return el;
            }
            return null;
        };

        this.appendMenuGroup(menu, {
            label: 'Markers',
            icon: 'mark_circle',
            items: ['red', 'blue', 'green', 'yellow'].map(key => {
                const color = markerColors[key] || markerDefaults[key];
                return {
                    label: markerNames[key] || nameDefaults[key],
                    color: color,
                    customNode: makeMarkerCustomNode(key, color),
                    selected: currentMark === key,
                    command: `onigiri_ctx_mark:${did}:${key}`
                };
            }),
        });

        if (currentMark) {
            this.appendMenuItem(menu, { label: 'Remove Marker', icon: 'remove_mark', command: `onigiri_ctx_mark:${did}:none` });
        }

        menu.appendChild(document.createElement('hr'));

        const deckActions = [];
        if (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.decklineAvailable) {
            deckActions.push({ label: 'Deadline', icon: 'bolt', command: `deadlineSettings:${did}` });
        }
        deckActions.push(
            { label: 'Deck Options', icon: 'options', command: `onigiri_ctx_options:${did}` },
            { label: 'Export Deck', icon: 'export-deck', command: `onigiri_ctx_export:${did}` },
            { label: 'Copy Deck ID', icon: 'copy_id', command: `onigiri_ctx_copy_id:${did}` },
            { label: 'Delete Deck', icon: 'delete', danger: true, command: `onigiri_ctx_delete:${did}` },
        );
        deckActions.forEach(item => this.appendMenuItem(menu, item));

        this.positionMenu(menu, x, y);
    },

    showBulkDeckContextMenu: function (x, y) {
        this.closeQuickMenus();
        const dids = Array.from(this._multiSelectedDecks);
        if (dids.length < 2) return;
        document.body.classList.add('ctx-menu-open');
        const encodedDids = encodeURIComponent(JSON.stringify(dids));
        const bulkPayload = encodeURIComponent(JSON.stringify({ dids }));

        const menu = document.createElement('div');
        menu.className = 'onigiri-quick-menu';

        [
            { label: `Move ${dids.length} Decks`, icon: 'move_deck', command: `onigiri_ctx_move_to:${encodedDids}` },
            { label: 'Favorite Selected', icon: 'star_filled', command: `onigiri_ctx_bulk_favorite:${bulkPayload}` },
            { label: 'Remove Favorites', icon: 'star_cancel', command: `onigiri_ctx_bulk_unfavorite:${bulkPayload}` },
        ].forEach(item => this.appendMenuItem(menu, item));

        menu.appendChild(document.createElement('hr'));
        const markerColors = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.markerColors) || {};
        const markerIcons = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.markerIcons) || {};
        const markerNames = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.markerNames) || {};
        const markerDefaults = { red: '#ff4d4f', blue: '#4f95ff', green: '#45c878', yellow: '#ffc629' };
        const nameDefaults = { red: 'Red', blue: 'Blue', green: 'Green', yellow: 'Yellow' };
        
        const makeMarkerCustomNodeBulk = (key, color) => {
            const iconVal = markerIcons[key] || 'default';
            if (iconVal !== 'default') {
                const el = document.createElement('span');
                el.className = 'quick-menu-color-dot';
                if (iconVal.startsWith('emoji:')) {
                    const spriteUrl = onigiriEmojiSpriteUrl(iconVal);
                    if (spriteUrl) {
                        el.style.backgroundColor = 'transparent';
                        el.style.backgroundImage = `url("${spriteUrl}")`;
                        el.style.backgroundSize = 'contain';
                        el.style.backgroundPosition = 'center';
                        el.style.backgroundRepeat = 'no-repeat';
                        el.style.borderRadius = '0';
                        el.style.boxShadow = 'none';
                    } else {
                        el.style.backgroundColor = 'transparent';
                        el.style.color = color;
                        el.style.fontSize = '14px';
                        el.style.lineHeight = '1';
                        el.style.display = 'inline-flex';
                        el.style.alignItems = 'center';
                        el.style.justifyContent = 'center';
                        el.style.boxShadow = 'none';
                        el.style.width = 'auto';
                        el.style.height = 'auto';
                        el.style.minWidth = 'auto';
                        el.style.minHeight = 'auto';
                        el.textContent = iconVal.replace('emoji:', '');
                    }
                } else {
                    const pkg = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.addonPackage) || '1011095603';
                    const iconUrl = iconVal.startsWith('system:') 
                        ? `/_addons/${pkg}/system_files/system_icons/unavailable_for_users/${iconVal.replace('system:', '')}`
                        : `/_addons/${pkg}/user_files/icons/${iconVal}`;
                    el.style.backgroundColor = color;
                    el.style.maskImage = `url("${iconUrl}")`;
                    el.style.webkitMaskImage = `url("${iconUrl}")`;
                    el.style.maskSize = 'contain';
                    el.style.webkitMaskSize = 'contain';
                    el.style.maskPosition = 'center';
                    el.style.webkitMaskPosition = 'center';
                    el.style.maskRepeat = 'no-repeat';
                    el.style.webkitMaskRepeat = 'no-repeat';
                    el.style.borderRadius = '0';
                }
                return el;
            }
            return null;
        };

        this.appendMenuGroup(menu, {
            label: 'Markers',
            icon: 'mark_circle',
            items: ['red', 'blue', 'green', 'yellow'].map(key => {
                const color = markerColors[key] || markerDefaults[key];
                return {
                    label: markerNames[key] || nameDefaults[key],
                    color: color,
                    customNode: makeMarkerCustomNodeBulk(key, color),
                    command: `onigiri_ctx_bulk_mark:${encodeURIComponent(JSON.stringify({ dids, mark: key }))}`
                };
            }),
        });
        this.appendMenuItem(menu, { label: 'Remove Marker', icon: 'remove_mark', command: `onigiri_ctx_bulk_mark:${encodeURIComponent(JSON.stringify({ dids, mark: 'none' }))}` });

        menu.appendChild(document.createElement('hr'));
        this.appendMenuItem(menu, { label: 'Delete Selected', icon: 'delete', danger: true, command: `onigiri_ctx_bulk_delete:${bulkPayload}` });
        this.positionMenu(menu, x, y);
    },

    showHomeMenu: function (button, event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        this.closeQuickMenus();

        const menu = document.createElement('div');
        menu.className = 'onigiri-quick-menu';
        [
            { label: 'Add', icon: 'add-card', command: 'add' },
            { label: 'Browse', icon: 'browse', command: 'browse' },
            { label: 'Stats', icon: 'stats', command: 'stats' },
            { label: 'Sync', icon: 'sync', command: 'sync' },
            { label: 'Settings', icon: 'settings', command: 'openOnigiriSettings' },
            { label: 'Hashi Notes', icon: 'hashi_notes', command: 'openHashiNotes:planner' },
            { label: 'Onigiri Games', icon: 'gamepad', command: 'openGamificationSettings' },
            { label: 'Get Shared', icon: 'get_shared', command: 'shared' },
            { label: 'Create Deck', icon: 'add-deck', command: 'onigiri_create_deck' },
            { label: 'Import File', icon: 'import_file', command: 'import' },
        ].forEach(item => this.appendMenuItem(menu, item));

        const rect = button.getBoundingClientRect();
        this.positionMenu(menu, rect.left, rect.bottom + 6);
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
            { label: 'Most new', icon: 'sort_most_new', mode: 'most_new' },
            { label: 'Most reviews', icon: 'stats', mode: 'most_reviews' },
            { label: 'Favorites first', icon: 'star_outline', mode: 'favorites_first' },
            { label: 'Custom order', icon: 'sort_custom', mode: 'custom' },
        ].forEach(item => this.appendMenuItem(menu, {
            label: item.label,
            icon: item.icon,
            selected: item.mode === current,
            sortMode: item.mode,
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
