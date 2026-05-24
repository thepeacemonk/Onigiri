// Onigiri Performance Engine

window.OnigiriEngine = {
    currentHoveredRow: null,
    _dnd: null, // Pointer-event drag-and-drop state
    _lastPointerPosition: null,
    _suppressNextHoverRestore: false,
    _preloadedIconUrls: new Set(),
    _deckOpenFallbackTimer: null,
    _multiSelectedDecks: new Set(),
    _lastMultiAnchorDid: null,
    _collapsePointerActive: false,
    _pendingDeferredTreeHtml: null,
    DND_INSERTION_LINE_PX: 2,
    HOVER_EXPAND_MS: 2000,

    _addonPackage: function () {
        return (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.addonPackage) || '';
    },

    systemIconUrl: function (filename) {
        const pkg = this._addonPackage();
        return pkg ? `/_addons/${pkg}/system_files/system_icons/${filename}` : `../system_files/system_icons/${filename}`;
    },

    applyMaskIcon: function (el, iconUrl, options) {
        if (!el) return el;
        const opts = options || {};
        const size = opts.size || 16;

        el.style.width = `${size}px`;
        el.style.height = `${size}px`;
        el.style.minWidth = `${size}px`;
        el.style.display = opts.display || 'inline-block';
        el.style.flexShrink = '0';
        el.style.backgroundColor = opts.color || 'var(--fg-subtle,var(--fg,currentColor))';

        if (!iconUrl) return el;

        const cssUrl = `url("${String(iconUrl).replace(/"/g, '%22')}")`;
        el.style.maskImage = cssUrl;
        el.style.webkitMaskImage = cssUrl;
        el.style.maskSize = 'contain';
        el.style.webkitMaskSize = 'contain';
        el.style.maskRepeat = 'no-repeat';
        el.style.webkitMaskRepeat = 'no-repeat';
        el.style.maskPosition = 'center';
        el.style.webkitMaskPosition = 'center';

        if (opts.flipX || opts.flipY || opts.transform) {
            const transforms = [];
            if (opts.flipX) transforms.push('scaleX(-1)');
            if (opts.flipY) transforms.push('scaleY(-1)');
            if (opts.transform) transforms.push(opts.transform);
            el.style.transform = transforms.join(' ');
        }

        return el;
    },

    createMaskIcon: function (iconUrl, options) {
        const opts = options || {};
        const icon = document.createElement(opts.tagName || 'span');
        icon.className = opts.className || 'ctx-icon';
        return this.applyMaskIcon(icon, iconUrl, opts);
    },

    escapeSelectorValue: function (value) {
        const text = String(value);
        if (window.CSS && typeof CSS.escape === 'function') {
            return CSS.escape(text);
        }
        return text.replace(/["\\]/g, '\\$&');
    },

    _hasOverrideState: function () {
        return document.body.classList.contains('is-dragging') ||
               document.body.classList.contains('ctx-menu-open') ||
               document.body.classList.contains('has-multi-select') ||
               document.body.classList.contains('dialog-focus');
    },

    _isDeckTreeInteractionActive: function () {
        const searchBar = document.getElementById('onigiri-deck-search-bar');
        return !!this._dnd ||
               this._multiSelectedDecks.size > 0 ||
               !!(searchBar && searchBar.classList.contains('is-visible')) ||
               this._hasOverrideState();
    },

    _flushDeferredTreeUpdate: function () {
        if (this._pendingDeferredTreeHtml === null) return false;
        if (this._isDeckTreeInteractionActive()) return false;

        const pendingHtml = this._pendingDeferredTreeHtml;
        this._pendingDeferredTreeHtml = null;
        this.updateDeckTree(pendingHtml);
        return true;
    },

    _beginOverrideState: function (bodyClass) {
        document.body.classList.add(bodyClass);
    },

    _endOverrideState: function (bodyClass) {
        document.body.classList.remove(bodyClass);
    },

    clearDialogFocus: function () {
        document.querySelectorAll('tr.deck.ctx-row-active').forEach(r => r.classList.remove('ctx-row-active'));
        this._endOverrideState('dialog-focus');
        this._clearHoveredRow();
        this._suppressNextHoverRestore = true;
    },

    clearDeckOpenTimers: function () {
        if (this._deckOpenFallbackTimer) {
            clearTimeout(this._deckOpenFallbackTimer);
            this._deckOpenFallbackTimer = null;
        }
    },

    cancelNativeDeckDragStart: function (event) {
        if (!(event.target instanceof Element) || !event.target.closest('tr.deck')) return;
        event.preventDefault();
        event.stopPropagation();
        if (typeof event.stopImmediatePropagation === 'function') {
            event.stopImmediatePropagation();
        }
    },

    markDeckSelectedRow: function (did, row) {
        if (this._hasOverrideState()) return;
        const nextRow = row || document.querySelector(`tr.deck[data-did="${this.escapeSelectorValue(did)}"]`);
        const oldRow = this.currentHoveredRow;

        if (oldRow && oldRow !== nextRow) {
            oldRow.classList.remove('is-hovered');
        }

        if (nextRow) {
            nextRow.classList.add('is-hovered');
            this.currentHoveredRow = nextRow;
        } else {
            this.currentHoveredRow = null;
        }
        return nextRow;
    },

    clearDeckOpeningState: function () {
        this.clearDeckOpenTimers();
        document.body.classList.remove('deck-open-pending');
    },

    clearMultiSelection: function () {
        if (this._multiSelectedDecks.size === 0) {
            if (this._pendingDeferredTreeHtml !== null) this._flushDeferredTreeUpdate();
            return;
        }
        this._multiSelectedDecks.clear();
        this._lastMultiAnchorDid = null;
        document.querySelectorAll('tr.deck.is-multi-selected').forEach(r => r.classList.remove('is-multi-selected'));
        this._updateMultiSelectBadge();
        this._endOverrideState('has-multi-select');
        if (this._pendingDeferredTreeHtml !== null) this._flushDeferredTreeUpdate();
    },

    _clearAllRowVisualStates: function () {
        document.querySelectorAll('tr.deck').forEach(row => {
            row.classList.remove('is-hovered', 'is-multi-selected', 'ctx-row-active');
        });
        this.currentHoveredRow = null;
    },

    _applyMultiSelectionStyles: function () {
        document.querySelectorAll('tr.deck.is-multi-selected').forEach(r => r.classList.remove('is-multi-selected'));
        this._multiSelectedDecks.forEach(did => {
            const row = document.querySelector(`tr.deck[data-did="${this.escapeSelectorValue(did)}"]`);
            if (!row) return;
            row.classList.add('is-multi-selected');
        });
        this._updateMultiSelectBadge();
    },

    _updateMultiSelectBadge: function () {
        const controls = document.querySelector('.sidebar-top-right-controls');
        if (!controls) return;
        let badge = document.getElementById('onigiri-multiselect-badge');
        if (this._multiSelectedDecks.size === 0) {
            if (badge) badge.remove();
            return;
        }
        const count = this._multiSelectedDecks.size;
        const text = count === 1 ? '1 selected' : `${count} selected`;
        if (!badge) {
            badge = document.createElement('span');
            badge.id = 'onigiri-multiselect-badge';
            badge.className = 'onigiri-multiselect-badge';
            controls.appendChild(badge);
        }
        badge.textContent = text;
    },

    openDeck: function (event, did, row, alreadySelected) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
            if (typeof event.stopImmediatePropagation === 'function') {
                event.stopImmediatePropagation();
            }
        }
        if (!did || document.body.classList.contains('deck-open-pending')) {
            return false;
        }

        this.clearDeckOpeningState();
        document.body.classList.add('deck-open-pending');

        this.closeEllipsisMenu();
        this.closeOrganiseMenu();
        this.closeDeckContextMenu();
        this.saveScrollPosition();

        // If the command cannot complete for any reason, do not leave the menu locked.
        this._deckOpenFallbackTimer = setTimeout(() => this.clearDeckOpeningState(), 5000);

        if (typeof pycmd === 'function') {
            pycmd('onigiri_open_deck:' + did);
        } else {
            this.clearDeckOpeningState();
        }
        return false;
    },

    preloadMaskIcons: function (urls) {
        const cleanUrls = (urls || [])
            .filter(Boolean)
            .map(url => String(url))
            .filter(url => !this._preloadedIconUrls.has(url));
        if (!cleanUrls.length) return;

        cleanUrls.forEach(url => this._preloadedIconUrls.add(url));

        let warmup = document.getElementById('onigiri-icon-warmup');
        if (!warmup) {
            warmup = document.createElement('div');
            warmup.id = 'onigiri-icon-warmup';
            warmup.setAttribute('aria-hidden', 'true');
            warmup.style.cssText = [
                'position:fixed',
                'left:-9999px',
                'top:-9999px',
                'width:1px',
                'height:1px',
                'overflow:hidden',
                'opacity:0',
                'pointer-events:none',
            ].join(';');
            document.documentElement.appendChild(warmup);
        }

        cleanUrls.forEach(url => {
            // Image warms the HTTP/file cache; masked spans warm WebKit's mask path too.
            const img = new Image();
            img.decoding = 'async';
            img.src = url;

            const span = document.createElement('span');
            this.applyMaskIcon(span, url, { size: 16 });
            warmup.appendChild(span);
        });
    },

    collectMenuIconUrls: function () {
        const urls = [
            'rename.svg',
            'add_subdeck.svg',
            'edit_icon.svg',
            'star_filled.svg',
            'star_outline.svg',
            'archive.svg',
            'unarchive.svg',
            'mark.svg',
            'remove_mark.svg',
            'options.svg',
            'export_deck.svg',
            'copy_id.svg',
            'delete.svg',
            'tick.svg',
            'more_circle.svg',
            'organise.svg',
            'drag_handle.svg',
            'right.svg',
        ].map(filename => this.systemIconUrl(filename));

        const visitAction = (action) => {
            if (!action) return;
            if (action.iconUrl) urls.push(action.iconUrl);
            if (action.children && action.children.length) {
                action.children.forEach(visitAction);
            }
        };

        const cfg = window.ONIGIRI_CONFIG || {};
        const actions = cfg.minimalModeActions || [];
        actions.forEach(visitAction);
        const organiseActions = cfg.organiseActions || [];
        organiseActions.forEach(visitAction);

        return urls;
    },

    cssPixelVar: function (name, fallback) {
        const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        const parsed = parseFloat(raw);
        return Number.isFinite(parsed) ? parsed : fallback;
    },

    init: function () {
        if (this._initialized) {
            return;
        }
        this.deckListContainer = document.getElementById('deck-list-container');
        if (!this.deckListContainer) {
            return;
        }
        this._initialized = true;

        // Pre-bind DnD handlers so they can be removed later
        this._boundDndMove = (e) => this._dndMove(e);
        this._boundDndEnd  = (e) => this._dndEnd(e);

        this.bindEvents();
        this.bindGlobalShortcuts();
        this.observeMutations();

        // Initial processing of already loaded nodes
        this.processNewNodes(document.querySelectorAll('tr.deck, a.collapse'));
        this.preloadMaskIcons(this.collectMenuIconUrls());
        this.restoreScrollPosition();

        // Initial fade state (handles page load at a non-zero scroll position)
        this.updateDeckFade();
        // Deck tree may not be fully painted yet — run again after first render
        setTimeout(() => this.updateDeckFade(), 300);

        // Signal the native startup overlay: engine is ready.
        // The multi-signal controller in templates.py also waits for heatmap
        // when heatmap data is present, so this is always safe to call.
        if (typeof window.onigiriDismissOverlay === 'function') {
            window.onigiriDismissOverlay('engine');
        }
    },

    bindGlobalShortcuts: function () {
        if (this._globalShortcutsBound) return;
        this._globalShortcutsBound = true;
        document.addEventListener('keydown', (event) => {
            const target = event.target;
            const tagName = target && target.tagName ? target.tagName.toLowerCase() : '';
            const isTyping = tagName === 'input'
                || tagName === 'textarea'
                || tagName === 'select'
                || (target && target.isContentEditable);
            if (event.key === 'Escape' && this._multiSelectedDecks.size > 0) {
                event.preventDefault();
                event.stopPropagation();
                this.clearMultiSelection();
                return;
            }
            if (isTyping || event.ctrlKey || event.altKey || event.metaKey) return;
            if (String(event.key).toLowerCase() !== 'd') return;

            event.preventDefault();
            event.stopPropagation();
            if (typeof event.stopImmediatePropagation === 'function') {
                event.stopImmediatePropagation();
            }
            if (typeof pycmd === 'function') {
                pycmd('decks');
            }
        }, true);
    },

    /**
     * Replaces the deck tree's HTML content without a full page reload,
     * preserving scroll position.
     * @param {string} newHtml The new HTML for the deck tree's <tbody>.
     */
    updateDeckTree: function (newHtml) {
        if (!this.deckListContainer) return;
        if (this._isDeckTreeInteractionActive()) {
            this._pendingDeferredTreeHtml = newHtml;
            return;
        }

        const tableBody = this.deckListContainer.querySelector('table.deck-table tbody');
        if (!tableBody) return;

        // Snapshot hovered deck before DOM replacement so we can restore it
        // immediately, preventing the brief background-colour flicker caused
        // by the browser re-evaluating :hover after innerHTML is swapped.
        const hoveredDid = this._suppressNextHoverRestore
            ? null
            : (this.currentHoveredRow ? this.currentHoveredRow.dataset.did : null);

        this.deckListContainer.classList.add('scroll-restoring');

        // Snapshot existing row IDs so we can animate only the newly-appeared rows
        const _prevIds = new Set(
            Array.from(tableBody.querySelectorAll('tr.deck[data-did]')).map(r => r.dataset.did)
        );

        // Snapshot edit-mode checkbox state before innerHTML wipes the DOM
        const editor = typeof OnigiriEditor !== 'undefined' ? OnigiriEditor : null;
        const checkboxStateMap = new Map();
        tableBody.querySelectorAll('.deck-checkbox').forEach(cb => {
            const did = cb.dataset.did;
            if (did) {
                checkboxStateMap.set(did, cb.checked);
            }
        });

        tableBody.innerHTML = newHtml;

        // Animate rows that are genuinely new (expansion animation)
        tableBody.querySelectorAll('tr.deck[data-did]').forEach(row => {
            if (!_prevIds.has(row.dataset.did)) {
                row.classList.add('deck-row-appear');
                row.addEventListener('animationend', () => row.classList.remove('deck-row-appear'), { once: true });
            }
        });

        // Restore hover class before any repaint unless a context-menu action
        // explicitly requested that the synthetic hover state be dropped.
        if (hoveredDid) {
            const newRow = tableBody.querySelector(`tr.deck[data-did="${hoveredDid}"]`);
            if (newRow) {
                this.currentHoveredRow = newRow;
                newRow.classList.add('is-hovered');
            } else {
                this.currentHoveredRow = null;
            }
        } else if (this._suppressNextHoverRestore) {
            this.currentHoveredRow = null;
        }

        if (!this._suppressNextHoverRestore) {
            this._restorePointerHover(tableBody);
        }
        this._suppressNextHoverRestore = false;

        this.restoreScrollPosition();
        this.processNewNodes(tableBody.children);

        // Re-apply multi-selection highlights to new DOM nodes
        if (this._multiSelectedDecks.size > 0) {
            this._applyMultiSelectionStyles();
        }

        // Recreate edit-mode checkboxes and restore which decks were selected
        if (editor && editor.EDIT_MODE && typeof editor.reapplyEditModeState === 'function') {
            checkboxStateMap.forEach((isChecked, did) => {
                if (isChecked) {
                    editor.SELECTED_DECKS.add(did);
                } else {
                    editor.SELECTED_DECKS.delete(did);
                }
            });
            editor.reapplyEditModeState();
        }

        if (typeof window.updateDeckLayouts === 'function') {
            window.updateDeckLayouts();
        }

        // Update fade gradient after content changes (scrollHeight may differ)
        requestAnimationFrame(() => this.updateDeckFade());

        setTimeout(() => {
            this.deckListContainer.classList.remove('scroll-restoring');
        }, 80);
    },

    updateDeckFade: function () {
        const container = this.deckListContainer;
        if (!container) return;

        // Hide the old fixed-overlay element (no longer used)
        const fadeEl = document.getElementById('onigiri-deck-fade');
        if (fadeEl) fadeEl.style.display = 'none';

        const FADE = 32;
        const scrollTop = container.scrollTop;
        const maxScroll = Math.max(0, container.scrollHeight - container.clientHeight);
        const topFade    = Math.min(scrollTop, FADE);
        const bottomFade = maxScroll > 0 ? Math.min(maxScroll - scrollTop, FADE) : 0;

        if (topFade <= 0 && bottomFade <= 0) {
            container.style.webkitMaskImage = '';
            container.style.maskImage       = '';
            return;
        }

        // Build gradient stops. We use pixel values that grow proportionally with
        // how far the user has scrolled so the fade appears gradually rather than
        // snapping at exactly 32 px.
        const topStop    = topFade    > 0 ? `${topFade}px`              : '0px';
        const bottomStop = bottomFade > 0 ? `calc(100% - ${bottomFade}px)` : '100%';

        let mask;
        if (topFade > 0 && bottomFade > 0) {
            mask = `linear-gradient(to bottom, transparent 0px, black ${topStop}, black ${bottomStop}, transparent 100%)`;
        } else if (topFade > 0) {
            mask = `linear-gradient(to bottom, transparent 0px, black ${topStop}, black 100%)`;
        } else {
            mask = `linear-gradient(to bottom, black 0%, black ${bottomStop}, transparent 100%)`;
        }

        container.style.webkitMaskImage = mask;
        container.style.maskImage       = mask;
    },

    /** Saves the current scroll position to session storage. */
    saveScrollPosition: function () {
        if (this.deckListContainer) {
            sessionStorage.setItem('deckListScrollTop', this.deckListContainer.scrollTop);
        }
    },

    /** Restores the scroll position from session storage. */
    restoreScrollPosition: function () {
        const savedScroll = sessionStorage.getItem('deckListScrollTop');
        if (savedScroll !== null && this.deckListContainer) {
            this.deckListContainer.scrollTop = parseInt(savedScroll, 10);
        }
    },

    _rememberPointer: function (event) {
        this._lastPointerPosition = { x: event.clientX, y: event.clientY };
    },

    _restorePointerHover: function (tableBody) {
        if (document.body.classList.contains('ctx-menu-open') || !this._lastPointerPosition) {
            return;
        }

        const el = document.elementFromPoint(
            this._lastPointerPosition.x,
            this._lastPointerPosition.y
        );
        const pointerRow = el ? el.closest('tr.deck') : null;
        if (!pointerRow || !tableBody.contains(pointerRow)) {
            return;
        }

        if (this.currentHoveredRow && this.currentHoveredRow !== pointerRow) {
            this.currentHoveredRow.classList.remove('is-hovered');
        }
        this.currentHoveredRow = pointerRow;
        pointerRow.classList.add('is-hovered');
    },

    _clearHoveredRow: function () {
        if (!this.currentHoveredRow) {
            return;
        }
        this.currentHoveredRow.classList.remove('is-hovered');
        this.currentHoveredRow = null;
    },

    /** Binds event listeners to handle interactions. */
    bindEvents: function () {
        if (this.deckListContainer.dataset.engineBound) return;
        this.deckListContainer.dataset.engineBound = 'true';

        // --- Lenis-inspired momentum scroll ---
        // Tuned for trackpad: lower multiplier + higher lerp stop scroll faster
        // so small trackpad flicks don't send the list flying.
        let _scrollTarget  = null;
        let _scrollRaf     = null;
        let _lastFrameTime = null;
        const _LERP = 0.26; // higher = stops faster (less momentum tail); was 0.16

        this.deckListContainer.addEventListener('wheel', (e) => {
            e.preventDefault();

            const container = this.deckListContainer;
            const raw  = e.deltaY !== 0 ? e.deltaY : e.deltaX;
            // Multiplier 0.45 + cap 60 prevent over-accumulation on trackpads
            // that fire many small delta events in rapid succession.
            const step = Math.sign(raw) * Math.min(Math.abs(raw) * 0.45, 60);

            if (_scrollTarget === null) _scrollTarget = container.scrollTop;
            _scrollTarget = Math.max(0, Math.min(
                container.scrollHeight - container.clientHeight,
                _scrollTarget + step
            ));

            if (_scrollRaf) return; // animation loop already running
            _lastFrameTime = null;

            const animate = (ts) => {
                // Normalise lerp to actual frame delta so feel is fps-independent.
                // Math: equivalent lerp at current fps = 1 - (1 - L)^(dt / 16.667)
                if (_lastFrameTime === null) _lastFrameTime = ts;
                const dt = Math.min(ts - _lastFrameTime, 50); // guard: tab-hidden / stutter
                _lastFrameTime = ts;
                const lf = 1 - Math.pow(1 - _LERP, dt / 16.667);

                const cur  = container.scrollTop;
                const diff = _scrollTarget - cur;

                if (Math.abs(diff) < 0.5) {
                    container.scrollTop = _scrollTarget;
                    _scrollTarget  = null;
                    _scrollRaf     = null;
                    _lastFrameTime = null;
                    return;
                }
                container.scrollTop = cur + diff * lf;
                _scrollRaf = requestAnimationFrame(animate);
            };
            _scrollRaf = requestAnimationFrame(animate);
        }, { passive: false });

        // --- Listener: Update fade gradient on native scroll (e.g. scrollbar drag) ---
        this.deckListContainer.addEventListener('scroll', () => this.updateDeckFade(), { passive: true });

        // --- Listener: Keep row hovered while mouse is over it ---
        this.deckListContainer.addEventListener('pointermove', (event) => {
            this._rememberPointer(event);
        }, { passive: true });

        this.deckListContainer.addEventListener('dragstart', (event) => {
            this.cancelNativeDeckDragStart(event);
            // Blank drag image to eliminate the one-frame native ghost flash
            if (event.dataTransfer) {
                const img = new Image();
                img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
                event.dataTransfer.setDragImage(img, 0, 0);
            }
            event.stopPropagation();
            if (typeof event.stopImmediatePropagation === 'function') event.stopImmediatePropagation();
        }, true);

        this.deckListContainer.addEventListener('selectstart', (event) => {
            // Ignore search input to allow text selection inside search bar
            if (event.target && event.target.closest('#onigiri-deck-search')) return;
            event.preventDefault();
        }, true);

        this.deckListContainer.addEventListener('mouseenter', (event) => {
            const deckRow = event.target.closest('tr.deck');
            if (deckRow) {
                this._rememberPointer(event);
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

        // --- Capture-phase interceptor: block inline onclick on a.deck during modifier clicks ---
        this.deckListContainer.addEventListener('click', (event) => {
            if (!(event.ctrlKey || event.metaKey || event.shiftKey)) return;
            const deckRow = event.target.closest('tr.deck[data-did]');
            if (!deckRow) return;
            if (event.target.closest('a.collapse, .opts, .favorite-star-icon, .drag-handle')) return;
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
        }, { capture: true });

        // --- Unified Click Handler for Deck List ---
        let clickTimer = null;
        this.deckListContainer.addEventListener('click', (event) => {
            if (document.body.classList.contains('deck-open-pending')) {
                event.preventDefault();
                event.stopPropagation();
                return;
            }

            const target = event.target;

            // Case 1: Collapse icon - let onclick attribute fire.
            const collapseLink = target.closest('a.collapse');
            if (collapseLink) {
                this._rememberPointer(event);
                const willOpen = !collapseLink.classList.contains('state-open');
                collapseLink.classList.toggle('state-open', willOpen);
                collapseLink.classList.toggle('state-closed', !willOpen);
                this.saveScrollPosition();
                return;
            }

            // Case 2: Options/gear icon — ignore.
            if (target.closest('.opts')) return;

            // Case 3: Favorite star — ignore (has its own onclick).
            if (target.closest('.favorite-star-icon')) return;

            // Case 4: Drag handle — ignore clicks (drag-only).
            if (target.closest('.drag-handle')) return;

            // Case 5: Deck row — double-click to study.
            const deckRow = target.closest('tr.deck');
            if (!deckRow) {
                const skipClear = event.target.closest('.sidebar-top-right-controls');
                if (!skipClear && !event.ctrlKey && !event.metaKey && !event.shiftKey && this._multiSelectedDecks.size > 0) {
                    this.clearMultiSelection();
                }
                return;
            }

            event.preventDefault();

            if (!clickTimer) {
                clickTimer = setTimeout(() => { clickTimer = null; }, 300);
            } else {
                clearTimeout(clickTimer);
                clickTimer = null;
                if (this._multiSelectedDecks.size === 0) {
                    const mainLink = deckRow.querySelector('a.deck');
                    if (mainLink) mainLink.click();
                }
            }
        });

        // --- Pointer down: left-click opens deck; right-click suppresses :active flash ---
        this.deckListContainer.addEventListener('pointerdown', (event) => {
            if (event.button === 2 && event.target.closest('tr.deck')) {
                event.preventDefault();
                document.body.classList.add('ctx-right-down');
                return;
            }
            if (event.button !== 0) return;

            // --- Multi-select: Ctrl/Shift+click on any deck row ---
            const multiRow = event.target.closest('tr.deck[data-did]');
            if (multiRow && multiRow.dataset.did && (event.ctrlKey || event.metaKey || event.shiftKey)) {
                event.preventDefault();
                event.stopPropagation();
                if (typeof event.stopImmediatePropagation === 'function') event.stopImmediatePropagation();
                const did = multiRow.dataset.did;

                const wasEmpty = this._multiSelectedDecks.size === 0;
                if (event.shiftKey && this._lastMultiAnchorDid) {
                    const allRows = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'));
                    const anchorIdx = allRows.findIndex(r => r.dataset.did === this._lastMultiAnchorDid);
                    const clickIdx = allRows.indexOf(multiRow);
                    if (anchorIdx !== -1) {
                        const [from, to] = anchorIdx < clickIdx ? [anchorIdx, clickIdx] : [clickIdx, anchorIdx];
                        for (let i = from; i <= to; i++) {
                            this._multiSelectedDecks.add(allRows[i].dataset.did);
                        }
                    } else {
                        this._multiSelectedDecks.add(did);
                        this._lastMultiAnchorDid = did;
                    }
                } else {
                    // Ctrl+click: toggle
                    if (this._multiSelectedDecks.has(did)) {
                        this._multiSelectedDecks.delete(did);
                        if (this._multiSelectedDecks.size === 0) {
                            this._lastMultiAnchorDid = null;
                            this._endOverrideState('has-multi-select');
                        }
                    } else {
                        this._multiSelectedDecks.add(did);
                        this._lastMultiAnchorDid = did;
                    }
                }
                if (wasEmpty && this._multiSelectedDecks.size > 0) {
                    this._beginOverrideState('has-multi-select');
                }
                this._applyMultiSelectionStyles();
                return;
            }

            // Plain left-click: clear any active multi-selection (skip toolbar/interactive elements)
            const skipClear = event.target.closest('a.collapse, .opts, .favorite-star-icon, .drag-handle, .sidebar-top-right-controls');
            if (!skipClear && this._multiSelectedDecks.size > 0) {
                this.clearMultiSelection();
            }

            if (document.body.classList.contains('deck-open-pending')) return;
            const deckLink = event.target.closest('a.deck');
            if (!deckLink || !this.deckListContainer.contains(deckLink)) return;
            const row = deckLink.closest('tr.deck[data-did]');
            if (row && row.dataset.did) {
                this._lastMultiAnchorDid = row.dataset.did;
                this.openDeck(event, row.dataset.did, row);
            }
        }, { capture: true });
        document.addEventListener('pointerup', (event) => {
            if (event.button === 2) document.body.classList.remove('ctx-right-down');
        }, { capture: true });

        // --- Right-click context menu on deck rows ---
        this.deckListContainer.addEventListener('contextmenu', (event) => {
            const deckRow = event.target.closest('tr.deck');
            if (!deckRow) return;
            event.preventDefault();
            const did = deckRow.dataset.did;
            if (!did) return;
            // Multi-selection: show bulk menu if this deck is part of selection
            if (this._multiSelectedDecks.size > 1 && this._multiSelectedDecks.has(did)) {
                OnigiriEngine.showMultiDeckContextMenu(event.clientX, event.clientY, did);
            } else {
                OnigiriEngine.showDeckContextMenu(event.clientX, event.clientY, did);
            }
        });
    },

    // ─── Pointer-event Drag & Drop ─────────────────────────────────────────────

    /** Creates a compact ghost element that follows the cursor during drag. */
    _dndCreateGhost: function (row, options) {
        const opts = options || {};
        const origRect = row.getBoundingClientRect();
        const GHOST_W = 300;
        const ROW_H = Math.max(24, Math.round(origRect.height || 32));
        const card = document.createElement('div');
        card.className = 'dnd-ghost-card';
        card.style.cssText = [
            'position:' + (opts.position || 'fixed'),
            'z-index:' + (opts.zIndex || 9998),
            'pointer-events:none',
            'opacity:' + (opts.opacity || 0.88),
            'box-shadow:0 8px 28px rgba(0,0,0,0.32)',
            `width:${GHOST_W}px`,
            `max-width:${GHOST_W}px`,
            `height:${ROW_H}px`,
            `top:${opts.top !== undefined ? opts.top : origRect.top}px`,
            `left:${opts.left !== undefined ? opts.left : origRect.left}px`,
            'background:var(--canvas,var(--frame-bg,#1e1e1e))',
            'border-radius:6px',
            'overflow:hidden',
            'display:flex',
            'align-items:center',
            'gap:6px',
            'padding:0 10px',
            'box-sizing:border-box',
        ].join(';');

        const handle = document.createElement('span');
        this.applyMaskIcon(handle, this.systemIconUrl('drag_handle.svg'), {
            color: 'var(--icon-color)',
            size: this.cssPixelVar('--drag-handle-icon-size', 14),
        });
        handle.style.marginRight = '0';
        handle.style.cursor = 'grabbing';

        const originalDeckLink = row.querySelector('a.deck');
        const beforeStyle = originalDeckLink ? getComputedStyle(originalDeckLink, '::before') : null;
        const icon = document.createElement('span');
        const iconSize = beforeStyle ? Math.max(14, parseFloat(beforeStyle.width) || 18) : 18;
        icon.style.cssText = [
            'display:inline-flex',
            'align-items:center',
            'justify-content:center',
            'width:' + iconSize + 'px',
            'height:' + iconSize + 'px',
            'min-width:' + iconSize + 'px',
            'flex:0 0 ' + iconSize + 'px',
            'overflow:hidden',
            'background-color:transparent',
        ].join(';');

        if (beforeStyle) {
            const maskImage = beforeStyle.maskImage || beforeStyle.webkitMaskImage || '';
            const content = beforeStyle.content || '';
            if (maskImage && maskImage !== 'none') {
                icon.style.backgroundColor = beforeStyle.backgroundColor || 'var(--icon-color)';
                icon.style.maskImage = maskImage;
                icon.style.webkitMaskImage = maskImage;
                icon.style.maskSize = beforeStyle.maskSize || 'contain';
                icon.style.webkitMaskSize = beforeStyle.webkitMaskSize || beforeStyle.maskSize || 'contain';
                icon.style.maskRepeat = beforeStyle.maskRepeat || 'no-repeat';
                icon.style.webkitMaskRepeat = beforeStyle.webkitMaskRepeat || beforeStyle.maskRepeat || 'no-repeat';
                icon.style.maskPosition = beforeStyle.maskPosition || 'center';
                icon.style.webkitMaskPosition = beforeStyle.webkitMaskPosition || beforeStyle.maskPosition || 'center';
            } else if (content && content !== 'none' && content !== 'normal' && content !== '""') {
                icon.style.backgroundColor = 'transparent';
                icon.style.fontSize = beforeStyle.fontSize || '14px';
                icon.style.lineHeight = beforeStyle.lineHeight || iconSize + 'px';
                icon.textContent = content.replace(/^["']|["']$/g, '');
            }
        }

        const name = document.createElement('span');
        const originalName = row.querySelector('a.deck .deck-name');
        name.textContent = originalName ? originalName.textContent.trim() : '';
        name.style.cssText = [
            'display:block',
            'flex:1 1 auto',
            'min-width:0',
            'overflow:hidden',
            'text-overflow:ellipsis',
            'white-space:nowrap',
            'font-size:15px',
            'color:var(--fg)',
        ].join(';');

        card.appendChild(handle);
        card.appendChild(icon);
        card.appendChild(name);
        return card;

        const table = document.createElement('table');
        table.className = 'deck-table';
        table.dataset.ghost = 'true';
        table.style.cssText = [
            'position:' + (opts.position || 'fixed'),
            'z-index:' + (opts.zIndex || 9998),
            'pointer-events:none',
            'opacity:' + (opts.opacity || 0.88),
            'box-shadow:0 8px 28px rgba(0,0,0,0.32)',
            'border-spacing:0',
            'border-collapse:collapse',
            `width:${GHOST_W}px`,
            `max-width:${GHOST_W}px`,
            `height:${ROW_H}px`,
            'table-layout:fixed',
            `top:${opts.top !== undefined ? opts.top : origRect.top}px`,
            `left:${opts.left !== undefined ? opts.left : origRect.left}px`,
            'background:var(--canvas,var(--frame-bg,#1e1e1e))',
            'border-radius:6px',
            'overflow:hidden',
        ].join(';');
        const tbody = document.createElement('tbody');
        const clone = row.cloneNode(true);
        clone.classList.remove('is-dragging', 'is-hovered', 'is-multi-selected', 'ctx-row-active', 'drop-before', 'drop-after', 'drag-over-target');
        clone.removeAttribute('id');
        // Remove stat columns — ghost shows deck name only
        clone.querySelectorAll('td:not(.decktd)').forEach(td => td.remove());
        const deckTd = clone.querySelector('td.decktd');
        if (deckTd) deckTd.style.minWidth = '0';
        if (deckTd) {
            const originalName = row.querySelector('a.deck .deck-name');
            const originalDeckLink = row.querySelector('a.deck');
            deckTd.innerHTML = '';
            deckTd.style.cssText = [
            'display:flex',
            'align-items:center',
            'gap:6px',
            'height:' + ROW_H + 'px',
            'padding:0 10px',
                'box-sizing:border-box',
                'min-width:0',
                'width:' + GHOST_W + 'px',
                'max-width:' + GHOST_W + 'px',
                'overflow:hidden',
            ].join(';');

            const handle = document.createElement('span');
            handle.className = 'drag-handle';
            this.applyMaskIcon(handle, this.systemIconUrl('drag_handle.svg'), {
                color: 'var(--icon-color)',
                size: this.cssPixelVar('--drag-handle-icon-size', 14),
            });
            handle.style.marginRight = '0';
            handle.style.cursor = 'grabbing';

            const deckLink = document.createElement('a');
            deckLink.className = originalDeckLink ? originalDeckLink.className : 'deck';
            deckLink.href = '#';
            deckLink.setAttribute('draggable', 'false');
            deckLink.style.cssText = [
                'display:flex',
                'align-items:center',
                'gap:6px',
                'flex:1 1 auto',
                'min-width:0',
                'max-width:100%',
                'overflow:hidden',
                'padding:0',
                'margin:0',
                'pointer-events:none',
            ].join(';');

            const name = document.createElement('span');
            name.className = 'deck-name';
            name.textContent = originalName ? originalName.textContent.trim() : '';
            name.style.cssText = [
                'display:block',
                'flex:1 1 auto',
                'min-width:0',
                'overflow:hidden',
                'text-overflow:ellipsis',
                'white-space:nowrap',
            ].join(';');

            deckLink.appendChild(name);
            deckTd.appendChild(handle);
            deckTd.appendChild(deckLink);
        }
        const nameAnchor = clone.querySelector('a.deck');
        if (nameAnchor) {
            nameAnchor.style.overflow = 'hidden';
            nameAnchor.style.textOverflow = 'ellipsis';
            nameAnchor.style.whiteSpace = 'nowrap';
        }
        tbody.appendChild(clone);
        table.appendChild(tbody);
        return table;
    },

    /** Creates a stacked ghost with a minimal foreground row and simple background cards. */
    _dndCreateMultiGhost: function (rows) {
        if (!rows || rows.length <= 1) return this._dndCreateGhost(rows[0]);
        const GHOST_W = 300;
        const firstRect = rows[0].getBoundingClientRect();
        const ROW_H = Math.max(24, Math.round(firstRect.height || 32));
        const container = document.createElement('div');
        container.style.cssText = [
            'position:fixed',
            'z-index:9998',
            'pointer-events:none',
            'width:' + GHOST_W + 'px',
            'height:' + (ROW_H + 12) + 'px',
            'top:' + firstRect.top + 'px',
            'left:' + firstRect.left + 'px',
        ].join(';');

        const offsets = [
            { x: 0, y: 0, opacity: 0.86, z: 2 },
            { x: 4, y: 4, opacity: 0.52, z: 1 },
            { x: 8, y: 8, opacity: 0.28, z: 0 },
        ];

        offsets.slice(1).reverse().forEach((off, i) => {
            const card = document.createElement('div');
            card.style.cssText = [
                'position:absolute',
                'left:' + off.x + 'px',
                'top:' + off.y + 'px',
                'width:' + (GHOST_W - off.x * 2) + 'px',
                'height:' + ROW_H + 'px',
                'border-radius:6px',
                'background:var(--canvas,var(--frame-bg,#1e1e1e))',
                'box-shadow:0 4px 14px rgba(0,0,0,0.28)',
                'opacity:' + off.opacity,
                'box-sizing:border-box',
                'z-index:' + off.z,
            ].join(';');
            container.appendChild(card);
        });

        const topCard = this._dndCreateGhost(rows[0]);
        topCard.style.position = 'absolute';
        topCard.style.left = '0';
        topCard.style.top = '0';
        topCard.style.zIndex = '2';
        topCard.style.width = GHOST_W + 'px';
        topCard.style.maxWidth = GHOST_W + 'px';
        topCard.style.height = ROW_H + 'px';
        topCard.style.opacity = '0.86';
        topCard.style.pointerEvents = 'none';
        container.appendChild(topCard);

        const badge = document.createElement('span');
        badge.textContent = String(rows.length);
        badge.style.cssText = [
            'position:absolute',
            'top:4px',
            'right:8px',
            'width:16px',
            'height:16px',
            'aspect-ratio:1/1',
            'border-radius:9999px',
            'background:var(--accent-color,#6366f1)',
            'color:#fff',
            'font-size:10px',
            'font-weight:600',
            'display:grid',
            'place-items:center',
            'padding:0',
            'box-sizing:border-box',
            'z-index:3',
        ].join(';');
        container.appendChild(badge);

        return container;
    },

    _dndRows: function () {
        return Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'));
    },

    _dndRowLevel: function (row) {
        const level = parseInt(row && row.dataset ? row.dataset.level || '1' : '1', 10);
        return Number.isFinite(level) ? level : 1;
    },

    _dndBuildParentMap: function (rows) {
        const parentByDid = new Map();
        const stack = [];
        rows.forEach(row => {
            const did = row.dataset.did;
            const level = this._dndRowLevel(row);
            while (stack.length && stack[stack.length - 1].level >= level) stack.pop();
            parentByDid.set(did, stack.length ? stack[stack.length - 1].did : null);
            stack.push({ did, level });
        });
        return parentByDid;
    },

    _dndHasSelectedAncestor: function (row, rows, selectedSet) {
        let level = this._dndRowLevel(row);
        const idx = rows.indexOf(row);
        for (let i = idx - 1; i >= 0 && level > 1; i--) {
            const candidate = rows[i];
            const candidateLevel = this._dndRowLevel(candidate);
            if (candidateLevel < level) {
                if (selectedSet.has(candidate.dataset.did)) return true;
                level = candidateLevel;
            }
        }
        return false;
    },

    _dndNormalizeSourceRows: function (rawRows, allRows) {
        const selectedSet = new Set((rawRows || []).map(r => r && r.dataset ? r.dataset.did : null).filter(Boolean));
        const seen = new Set();
        return allRows.filter(row => {
            const did = row.dataset.did;
            if (!selectedSet.has(did) || seen.has(did)) return false;
            seen.add(did);
            return !this._dndHasSelectedAncestor(row, allRows, selectedSet);
        });
    },

    _dndCollectMovingRows: function (sourceRows, allRows) {
        const movingRows = [];
        const seen = new Set();
        sourceRows.forEach(sourceRow => {
            const idx = allRows.indexOf(sourceRow);
            if (idx === -1) return;
            const sourceLevel = this._dndRowLevel(sourceRow);
            for (let i = idx; i < allRows.length; i++) {
                const row = allRows[i];
                if (i > idx && this._dndRowLevel(row) <= sourceLevel) break;
                const did = row.dataset.did;
                if (!seen.has(did)) {
                    movingRows.push(row);
                    seen.add(did);
                }
            }
        });
        return movingRows;
    },

    _dndArraysEqual: function (left, right) {
        if (!Array.isArray(left) || !Array.isArray(right) || left.length !== right.length) return false;
        for (let i = 0; i < left.length; i++) {
            if (String(left[i]) !== String(right[i])) return false;
        }
        return true;
    },

    /** Initiates a pointer-event drag from a drag handle element. */
    _dndStart: function (e, handleEl) {
        if (this._collapsePointerActive) return;
        const path = e.composedPath ? e.composedPath() : [];
        if (path.some(n => n && n.classList && n.classList.contains('collapse') && n.tagName === 'A')) return;
        const row = handleEl.closest('tr.deck');
        if (!row || this._dnd) return;
        e.preventDefault();

        const origRect = row.getBoundingClientRect();
        const offsetY = e.clientY - origRect.top;
        const GHOST_W = 300;
        const rawOffsetX = e.clientX - origRect.left;
        const offsetX = Math.max(8, Math.min(rawOffsetX, GHOST_W - 8));

        const allDomRows = this._dndRows();

        // Multi-drag: if this row is part of a multi-selection, drag all selected rows.
        // Source rows are normalized to visible tree order, with selected descendants
        // folded into their selected ancestor's subtree.
        let sourceRows;
        const isMultiDragOperation = this._multiSelectedDecks.size > 1 && this._multiSelectedDecks.has(row.dataset.did);
        if (isMultiDragOperation) {
            const rawSourceRows = allDomRows.filter(r => this._multiSelectedDecks.has(r.dataset.did));
            sourceRows = this._dndNormalizeSourceRows(rawSourceRows, allDomRows);
            if (!sourceRows.length) sourceRows = [row];
        } else {
            // Single-deck drag: clear any stale multi-selection
            if (this._multiSelectedDecks.size > 0) this.clearMultiSelection();
            sourceRows = [row];
        }

        sourceRows.forEach(r => r.classList.add('is-dragging'));

        // Suppress hover and context states during drag
        this._beginOverrideState('is-dragging');

        const movingRows = this._dndCollectMovingRows(sourceRows, allDomRows);
        const sourceDids = sourceRows.map(r => r.dataset.did).filter(Boolean);
        const movingDids = movingRows.map(r => r.dataset.did).filter(Boolean);
        const invalidTargetDids = new Set(movingDids);
        const parentByDid = this._dndBuildParentMap(allDomRows);
        const levelByDid = new Map(allDomRows.map(r => [r.dataset.did, this._dndRowLevel(r)]));
        const sourceParentByDid = new Map(sourceDids.map(did => [did, parentByDid.get(did) || null]));

        const ghostEl = sourceRows.length > 1
            ? this._dndCreateMultiGhost(sourceRows)
            : this._dndCreateGhost(sourceRows[0] || row);
        document.body.appendChild(ghostEl);

        const nestOverlay = document.createElement('div');
        nestOverlay.className = 'dnd-nest-overlay';
        document.body.appendChild(nestOverlay);

        this._dnd = {
            sourceRow: row,
            sourceRows,
            isMultiDrag: isMultiDragOperation,
            sourceDids,
            movingRows,
            movingDids,
            invalidTargetDids,
            originalOrder: allDomRows.map(r => r.dataset.did).filter(Boolean),
            parentByDid,
            levelByDid,
            sourceParentByDid,
            ghostEl,
            nestOverlay,
            offsetX,
            offsetY,
            lastClientX: e.clientX,
            lastClientY: e.clientY,
            lastTargetRow: null,
            lastInsertType: null,
            placeholder: null,
            lastMoveY: e.clientY,
            lastMoveTime: performance.now(),
            hoverExpandRow: null,
            hoverExpandTimer: null,
            hoverExpandPendingTimer: null,
            scrollActiveTop: false,
            scrollActiveBottom: false,
        };

        this._autoScrollRaf = null;
        this._dndAutoScroll();

        document.addEventListener('pointermove', this._boundDndMove, { passive: false });
        document.addEventListener('pointerup',   this._boundDndEnd);
        document.addEventListener('pointercancel', this._boundDndEnd);
    },

    /** Continuous auto-scroll loop — runs while a drag is active. */
    _dndAutoScroll: function () {
        if (!this._dnd) return;
        const container = this.deckListContainer;
        if (!container || !container.isConnected) return;
        const rect = container.getBoundingClientRect();
        // Suppress auto-scroll when cursor is outside the sidebar
        const y = this._dnd.lastClientY;
        const x = this._dnd.lastClientX || 0;
        const insideSidebar = x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
        if (!insideSidebar) {
            this._autoScrollRaf = requestAnimationFrame(() => this._dndAutoScroll());
            return;
        }
        const ACTIVATE_ZONE   = 56;
        const DEACTIVATE_ZONE = 76;
        const maxSpeed = 14;
        let scrolled = false;

        const distTop    = y - rect.top;
        const distBottom = rect.bottom - y;

        // Hysteresis: activate on entering zone, deactivate only after leaving wider zone
        if (distTop >= 0 && distTop < ACTIVATE_ZONE)    this._dnd.scrollActiveTop = true;
        if (distTop > DEACTIVATE_ZONE)                  this._dnd.scrollActiveTop = false;
        if (distBottom >= 0 && distBottom < ACTIVATE_ZONE) this._dnd.scrollActiveBottom = true;
        if (distBottom > DEACTIVATE_ZONE)               this._dnd.scrollActiveBottom = false;

        if (this._dnd.scrollActiveTop && distTop >= 0) {
            const intensity = 1 - Math.min(distTop, ACTIVATE_ZONE) / ACTIVATE_ZONE;
            container.scrollTop -= Math.ceil(maxSpeed * intensity);
            scrolled = true;
        } else if (this._dnd.scrollActiveBottom && distBottom >= 0) {
            const intensity = 1 - Math.min(distBottom, ACTIVATE_ZONE) / ACTIVATE_ZONE;
            container.scrollTop += Math.ceil(maxSpeed * intensity);
            scrolled = true;
        }

        // Keep the drop indicator in sync when the list scrolls
        if (scrolled && this._dnd.lastTargetRow && !this._dnd.lastTargetRow.isConnected) {
            if (this._dnd.nestOverlay) this._dnd.nestOverlay.style.opacity = '0';
            if (this._dnd.placeholder) this._dnd.placeholder.style.opacity = '0';
            this._dnd.lastTargetRow = null;
            this._dnd.lastInsertType = null;
        } else if (scrolled && this._dnd.nestOverlay && this._dnd.lastTargetRow && this._dnd.lastInsertType === 'nest') {
            this._dndUpdateNestOverlay(this._dnd.lastTargetRow);
        } else if (scrolled && this._dnd.placeholder && this._dnd.lastTargetRow && this._dnd.lastInsertType !== 'nest') {
            const rowRect = this._dnd.lastTargetRow.getBoundingClientRect();
            let barTop;
            if (this._dnd.lastInsertType === 'before') {
                const prevRow = this._dndPrevVisibleRow(this._dnd.lastTargetRow);
                barTop = prevRow
                    ? this._dndInsertionLineTop((prevRow.getBoundingClientRect().bottom + rowRect.top) / 2)
                    : this._dndInsertionLineTop(rowRect.top);
            } else {
                const nextRow = this._dndNextVisibleRow(this._dnd.lastTargetRow);
                barTop = nextRow
                    ? this._dndInsertionLineTop((rowRect.bottom + nextRow.getBoundingClientRect().top) / 2)
                    : this._dndInsertionLineTop(rowRect.bottom);
            }
            this._dndUpdatePlaceholder(barTop, this._dnd.lastTargetRow);
        }

        this._autoScrollRaf = requestAnimationFrame(() => this._dndAutoScroll());
    },

    /** Handles pointer movement during drag — moves ghost and shows drop indicator via CSS classes. */
    _dndMove: function (e) {
        if (!this._dnd) return;
        e.preventDefault();

        // Refresh sourceRow(s) if DOM was re-rendered by hover-expand
        if (this._dnd.sourceRow && !this._dnd.sourceRow.isConnected) {
            const freshRow = this.deckListContainer.querySelector(`tr.deck[data-did="${this._dnd.sourceRow.dataset.did}"]`);
            if (freshRow) {
                const oldRow = this._dnd.sourceRow;
                this._dnd.sourceRows = this._dnd.sourceRows.map(r => r === oldRow ? freshRow : r);
                this._dnd.sourceRow  = freshRow;
            }
        }

        // After hover-expand the tree DOM is replaced; lastTargetRow becomes detached
        if (this._dnd.lastTargetRow && !this._dnd.lastTargetRow.isConnected) {
            if (this._dnd.nestOverlay) this._dnd.nestOverlay.style.opacity = '0';
            if (this._dnd.placeholder) this._dnd.placeholder.style.opacity = '0';
            this._dnd.lastTargetRow = null;
            this._dnd.lastInsertType = null;
        }

        const { ghostEl, sourceRow, sourceRows, offsetX, offsetY } = this._dnd;

        this._dnd.lastClientX = e.clientX;
        this._dnd.lastClientY = e.clientY;

        // Ghost follows cursor freely in both axes
        ghostEl.style.top  = (e.clientY - offsetY) + 'px';
        ghostEl.style.left = (e.clientX - offsetX) + 'px';

        // If cursor is outside the sidebar, suppress all drop indicators
        const containerRect = this.deckListContainer.getBoundingClientRect();
        const insideSidebar = e.clientX >= containerRect.left && e.clientX <= containerRect.right &&
                              e.clientY >= containerRect.top  && e.clientY <= containerRect.bottom;
        if (!insideSidebar) {
            document.body.classList.remove('fast-dragging');
            this._dndEnterNoOpState();
            return;
        }

        const GAP = 22; // must match CSS padding value

        // --- Velocity: fast drags get instant gap snap, slow drags get easing ---
        const now = performance.now();
        const dt  = now - this._dnd.lastMoveTime;
        const vel = dt > 0 ? Math.abs(e.clientY - this._dnd.lastMoveY) / dt * 1000 : 0;
        this._dnd.lastMoveTime = now;
        this._dnd.lastMoveY    = e.clientY;
        if (vel > 220) { document.body.classList.add('fast-dragging'); }
        else           { document.body.classList.remove('fast-dragging'); }

        // --- Find target row ---
        const allRows = this.deckListContainer.querySelectorAll('tr.deck[data-did]');
        let targetRow = null;
        const invalidSet = this._dnd.invalidTargetDids;
        for (const row of allRows) {
            if (invalidSet.has(row.dataset.did)) continue;
            const rect = row.getBoundingClientRect();
            if (e.clientY >= rect.top && e.clientY <= rect.bottom) { targetRow = row; break; }
        }
        // Edge case: cursor above the first visible row → snap to 'before' on that row.
        if (!targetRow) {
            const visibleRows = Array.from(allRows).filter(r => !invalidSet.has(r.dataset.did));
            if (visibleRows.length) {
                const firstRect = visibleRows[0].getBoundingClientRect();
                const lastRect  = visibleRows[visibleRows.length - 1].getBoundingClientRect();
                if (e.clientY < firstRect.top) {
                    targetRow = visibleRows[0];
                    if (this._dndIsNoOpDrop(targetRow, 'before')) {
                        this._dndEnterNoOpState();
                        return;
                    }
                    // Force insertType 'before' on the first row immediately (bypass hysteresis)
                    if (this._dnd.lastTargetRow !== targetRow || this._dnd.lastInsertType !== 'before') {
                        if (this._dnd.lastTargetRow) {
                            this._dnd.lastTargetRow.classList.remove('drag-over-target', 'drop-before', 'drop-after');
                        }
                        targetRow.classList.add('drop-before');
                        const barTop = this._dndInsertionLineTop(firstRect.top);
                        this._dndUpdatePlaceholder(barTop, targetRow);
                        this._dnd.lastTargetRow  = targetRow;
                        this._dnd.lastInsertType = 'before';
                        this._dndClearHoverExpand();
                    }
                    return;
                } else if (e.clientY > lastRect.bottom) {
                    targetRow = visibleRows[visibleRows.length - 1];
                    if (this._dndIsNoOpDrop(targetRow, 'after')) {
                        this._dndEnterNoOpState();
                        return;
                    }
                    // Force insertType 'after' on the last row immediately
                    if (this._dnd.lastTargetRow !== targetRow || this._dnd.lastInsertType !== 'after') {
                        if (this._dnd.lastTargetRow) {
                            this._dnd.lastTargetRow.classList.remove('drag-over-target', 'drop-before', 'drop-after');
                        }
                        targetRow.classList.add('drop-after');
                        const barTop = this._dndInsertionLineTop(lastRect.bottom);
                        this._dndUpdatePlaceholder(barTop, targetRow);
                        this._dnd.lastTargetRow  = targetRow;
                        this._dnd.lastInsertType = 'after';
                        this._dndClearHoverExpand();
                    }
                    return;
                }
            }
        }

        // --- insertType with wide hysteresis ---
        let insertType = null;
        if (targetRow) {
            const r   = targetRow.getBoundingClientRect();
            const pct = (e.clientY - r.top) / r.height;
            const isSameRow = targetRow === this._dnd.lastTargetRow;
            const prev = isSameRow ? this._dnd.lastInsertType : null;
            // Re-entry fix: if target is the immediate parent of the source, never nest
            const srcLevel = parseInt(sourceRow.dataset.level || '1', 10);
            const tgtLevel = parseInt(targetRow.dataset.level || '1', 10);
            const srcIdx = Array.from(allRows).indexOf(sourceRow);
            const tgtIdx = Array.from(allRows).indexOf(targetRow);
            const isParentRow = tgtLevel === srcLevel - 1 && tgtIdx < srcIdx;
            if (!this._dnd.isMultiDrag && sourceRows.length === 1 && isParentRow) {
                insertType = pct < 0.5 ? 'before' : 'after';
            } else if (prev === 'before') {
                insertType = pct < 0.50 ? 'before' : 'nest';
            } else if (prev === 'after') {
                insertType = pct > 0.50 ? 'after' : 'nest';
            } else if (prev === 'nest') {
                if      (pct < 0.12) insertType = 'before';
                else if (pct > 0.88) insertType = 'after';
                else                 insertType = 'nest';
            } else {
                if      (pct < 0.22) insertType = 'before';
                else if (pct > 0.78) insertType = 'after';
                else                 insertType = 'nest';
            }
        }

        // Reclassify: 'before' on a deep row immediately after a collapsed shallower parent
        // → treat as 'after' on the collapsed parent to avoid misleading indent level.
        // Only applies when the live DOM confirms prevRow is a closed, shallower parent.
        if (insertType === 'before' && targetRow) {
            const prevRow = this._dndPrevVisibleRow(targetRow);
            if (prevRow && !this._dnd.invalidTargetDids.has(prevRow.dataset.did)) {
                const prevLevel = parseInt(prevRow.dataset.level || '1', 10);
                const curLevel  = parseInt(targetRow.dataset.level || '1', 10);
                if (prevLevel < curLevel && prevRow.querySelector('a.collapse.state-closed')) {
                    targetRow  = prevRow;
                    insertType = 'after';
                }
            }
        }

        // --- Hover-to-expand: manage timer when target row changes or cursor moves ---
        // Only show spinner/expand when the actual drop intent is nested
        if (insertType !== 'nest') {
            this._dndClearHoverExpand();
        } else if (targetRow) {
            const collapseBtn = targetRow.querySelector('a.collapse.state-closed');
            if (collapseBtn && !invalidSet.has(targetRow.dataset.did)) {
                const chevronRect = collapseBtn.getBoundingClientRect();
                const nearChevron = e.clientX >= chevronRect.left - 20 &&
                                    e.clientX <= chevronRect.right + 70;
                if (nearChevron) {
                    if (this._dnd.hoverExpandRow !== targetRow) {
                        this._dndStartHoverExpand(targetRow, targetRow.dataset.did, collapseBtn);
                    }
                } else {
                    if (this._dnd.hoverExpandRow === targetRow) {
                        this._dndClearHoverExpand();
                    }
                }
            } else {
                this._dndClearHoverExpand();
            }
        } else {
            this._dndClearHoverExpand();
        }

        // Skip if nothing changed
        if (targetRow === this._dnd.lastTargetRow && insertType === this._dnd.lastInsertType) return;

        if (this._dndIsNoOpDrop(targetRow, insertType)) {
            this._dndEnterNoOpState();
            return;
        }

        // Clear old state
        if (this._dnd.lastTargetRow) {
            this._dnd.lastTargetRow.classList.remove('drag-over-target', 'drop-before', 'drop-after');
        }
        if (this._dnd.placeholder && insertType === 'nest') {
            this._dnd.placeholder.remove();
            this._dnd.placeholder = null;
        }
        if (this._dnd.nestOverlay && insertType !== 'nest') {
            this._dnd.nestOverlay.style.opacity = '0';
        }
        this._dnd.lastTargetRow  = targetRow;
        this._dnd.lastInsertType = insertType;

        if (!targetRow) {
            this._dndEnterNoOpState();
            return;
        }

        const isMultiDrag = this._dnd.isMultiDrag || sourceRows.length > 1;
        if (insertType === 'before') {
            targetRow.classList.add('drop-before');
            const rowRect = targetRow.getBoundingClientRect();
            const prevRow = this._dndPrevVisibleRow(targetRow);
            // For multi-drag always show placeholder; for single check original slot
            let atOriginalSlot = false;
            if (!isMultiDrag) {
                const allDomRows = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'));
                const prevIdx = prevRow ? allDomRows.indexOf(prevRow) : -1;
                const tgtIdx = allDomRows.indexOf(targetRow);
                const srcIdx = allDomRows.indexOf(sourceRow);
                atOriginalSlot = srcIdx > prevIdx && srcIdx < tgtIdx;
            }
            if (atOriginalSlot) {
                if (this._dnd.placeholder) this._dnd.placeholder.style.opacity = '0';
            } else {
                const barTop = prevRow
                    ? this._dndInsertionLineTop((prevRow.getBoundingClientRect().bottom + rowRect.top) / 2)
                    : this._dndInsertionLineTop(rowRect.top);
                this._dndUpdatePlaceholder(barTop, targetRow);
            }
        } else if (insertType === 'after') {
            targetRow.classList.add('drop-after');
            const rowRect = targetRow.getBoundingClientRect();
            const nextRow = this._dndNextVisibleRow(targetRow);
            let atOriginalSlot = false;
            if (!isMultiDrag) {
                const allDomRows = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'));
                const nextIdx = nextRow ? allDomRows.indexOf(nextRow) : allDomRows.length;
                const tgtIdx = allDomRows.indexOf(targetRow);
                const srcIdx = allDomRows.indexOf(sourceRow);
                atOriginalSlot = srcIdx > tgtIdx && srcIdx < nextIdx;
            }
            if (atOriginalSlot) {
                if (this._dnd.placeholder) this._dnd.placeholder.style.opacity = '0';
            } else {
                const barTop = nextRow
                    ? this._dndInsertionLineTop((rowRect.bottom + nextRow.getBoundingClientRect().top) / 2)
                    : this._dndInsertionLineTop(rowRect.bottom);
                this._dndUpdatePlaceholder(barTop, targetRow);
            }
        } else {
            targetRow.classList.add('drag-over-target');
            this._dndUpdateNestOverlay(targetRow);
        }
    },

    /** Positions the measured nest overlay aligned to the content anchor. */
    _dndUpdateNestOverlay: function (targetRow) {
        if (!this._dnd || !this._dnd.nestOverlay || !targetRow || !targetRow.isConnected) {
            if (this._dnd && this._dnd.nestOverlay) this._dnd.nestOverlay.style.opacity = '0';
            return false;
        }
        const nestOverlay = this._dnd.nestOverlay;
        const targetRect = targetRow.getBoundingClientRect();
        const { left: anchorLeft } = this._dndMeasureAnchor(targetRow);
        const containerRect = this.deckListContainer.getBoundingClientRect();
        nestOverlay.style.cssText = [
            `top:${targetRect.top}px`,
            `left:${anchorLeft - 2}px`,
            `width:${containerRect.right - anchorLeft - 4}px`,
            `height:${targetRect.height}px`,
            'opacity:1',
        ].join(';');
        return true;
    },

    _dndInsertionLineTop: function (centerY) {
        const height = this._dndInsertionLineHeight();
        return this._dndSnapCssPixel(centerY - (height / 2));
    },

    _dndInsertionLineHeight: function () {
        return this._dndSnapCssPixel(Math.max(1, this.DND_INSERTION_LINE_PX));
    },

    _dndSnapCssPixel: function (value) {
        const dpr = window.devicePixelRatio || 1;
        return Math.round(value * dpr) / dpr;
    },

    /** Starts hover-to-expand timers and inserts the spinner animation near the chevron. */
    _dndStartHoverExpand: function (targetRow, expandDid, collapseBtn) {
        if (!this._dnd) return;
        this._dndClearHoverExpand();
        this._dnd.hoverExpandRow = targetRow;
        this._dnd.hoverExpandPendingTimer = setTimeout(() => {
            if (!this._dnd) return;
            if (!targetRow.isConnected) return;
            const chevron = targetRow.querySelector('a.collapse.state-closed');
            if (chevron && !chevron.querySelector('.expand-spinner')) {
                chevron.classList.add('is-hover-expanding');
                const spinner = document.createElement('span');
                spinner.className = 'expand-spinner';
                spinner.setAttribute('aria-hidden', 'true');
                chevron.appendChild(spinner);
            }
        }, 200);
        this._dnd.hoverExpandTimer = setTimeout(() => {
            if (!this._dnd) return;
            const activeChevron = targetRow.querySelector('a.collapse.is-hover-expanding');
            if (activeChevron) {
                const spinner = activeChevron.querySelector('.expand-spinner');
                if (spinner) spinner.remove();
                activeChevron.classList.remove('is-hover-expanding');
            }
            const btn = targetRow.querySelector('a.collapse.state-closed');
            if (btn && targetRow.isConnected) {
                pycmd('onigiri_collapse:' + expandDid);
            }
            this._dnd.hoverExpandRow = null;
            this._dnd.hoverExpandTimer = null;
            this._dnd.hoverExpandPendingTimer = null;
        }, this.HOVER_EXPAND_MS);
    },

    /** Clears hover-expand timers and removes any expand spinner. */
    _dndClearHoverExpand: function () {
        if (!this._dnd) return;
        if (this._dnd.hoverExpandTimer) { clearTimeout(this._dnd.hoverExpandTimer); this._dnd.hoverExpandTimer = null; }
        if (this._dnd.hoverExpandPendingTimer) { clearTimeout(this._dnd.hoverExpandPendingTimer); this._dnd.hoverExpandPendingTimer = null; }
        if (this._dnd.hoverExpandRow) {
            const spinner = this._dnd.hoverExpandRow.querySelector('.expand-spinner');
            if (spinner) spinner.remove();
            const chevron = this._dnd.hoverExpandRow.querySelector('a.collapse.is-hover-expanding');
            if (chevron) chevron.classList.remove('is-hover-expanding');
            this._dnd.hoverExpandRow = null;
        }
    },

    /** Clears all drag/drop visual indicators, overlays, placeholders, and hover timers. */
    _dndEnterNoOpState: function () {
        if (!this._dnd) return;
        if (this._dnd.lastTargetRow) {
            this._dnd.lastTargetRow.classList.remove('drag-over-target', 'drop-before', 'drop-after');
        }
        if (this._dnd.placeholder) this._dnd.placeholder.style.opacity = '0';
        if (this._dnd.nestOverlay) this._dnd.nestOverlay.style.opacity = '0';
        this._dndClearHoverExpand();
        this._dnd.lastTargetRow  = null;
        this._dnd.lastInsertType = null;
    },

    _dndTargetParentDid: function (targetDid, insertType) {
        if (!this._dnd || !targetDid) return null;
        if (insertType === 'nest') return String(targetDid);
        return this._dnd.parentByDid && this._dnd.parentByDid.has(String(targetDid))
            ? this._dnd.parentByDid.get(String(targetDid))
            : null;
    },

    _dndIsNoOpDrop: function (targetRow, insertType) {
        if (!this._dnd || !targetRow || !insertType) return false;
        const targetDid = targetRow.dataset.did;
        if (!targetDid || this._dnd.invalidTargetDids.has(targetDid)) return true;

        const sourceDids = this._dnd.sourceDids || [];
        if (!sourceDids.length) return true;

        const proposedOrder = this._dndBuildNewOrder(sourceDids, targetDid, insertType, false);
        if (!proposedOrder) return true;

        const originalOrder = this._dnd.originalOrder || [];
        const sameOrder = this._dndArraysEqual(proposedOrder, originalOrder);
        const targetParentDid = this._dndTargetParentDid(targetDid, insertType);
        const sameParents = sourceDids.every(did => {
            const sourceParent = this._dnd.sourceParentByDid && this._dnd.sourceParentByDid.has(did)
                ? this._dnd.sourceParentByDid.get(did)
                : null;
            return (sourceParent || null) === (targetParentDid || null);
        });

        return sameOrder && sameParents;
    },

    /** Returns the content-anchor measurements for a deck row (shared by insertion lines and nest overlay). */
    _dndMeasureAnchor: function (targetRow) {
        const containerRect = this.deckListContainer.getBoundingClientRect();
        let indentLeft = 12;
        if (targetRow) {
            const deckLink = targetRow.querySelector('a.deck');
            if (deckLink) {
                indentLeft = Math.max(12, deckLink.getBoundingClientRect().left - containerRect.left);
            } else {
                const level = parseInt(targetRow.dataset.level || '1', 10);
                const step = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.deckIndentStep) || 20;
                indentLeft = Math.max(12, step * (level - 1) + 12);
            }
        }
        return {
            containerRect,
            indentLeft,
            left:  containerRect.left + indentLeft,
            width: containerRect.width - indentLeft - 12,
        };
    },

    /** Creates or updates the fixed-position insertion-line overlay. */
    _dndUpdatePlaceholder: function (top, targetRow) {
        const { left, width } = this._dndMeasureAnchor(targetRow);
        const lineTop = this._dndSnapCssPixel(top);
        const lineLeft = this._dndSnapCssPixel(left);
        const lineWidth = this._dndSnapCssPixel(width);
        const lineHeight = this._dndInsertionLineHeight();
        if (this._dnd.placeholder) {
            this._dnd.placeholder.style.top   = lineTop + 'px';
            this._dnd.placeholder.style.left  = lineLeft + 'px';
            this._dnd.placeholder.style.width = lineWidth + 'px';
            this._dnd.placeholder.style.height = lineHeight + 'px';
            this._dnd.placeholder.style.opacity = '1';
        } else {
            this._dnd.placeholder = this._dndMakePlaceholder(lineTop, targetRow);
            if (this._dnd.placeholder) this._dnd.placeholder.style.opacity = '1';
        }
    },

    /** Creates a fixed-position insertion-line overlay (does not touch the table DOM). */
    _dndMakePlaceholder: function (top, targetRow) {
        const { left, width } = this._dndMeasureAnchor(targetRow);
        const lineTop = this._dndSnapCssPixel(top);
        const lineLeft = this._dndSnapCssPixel(left);
        const lineWidth = this._dndSnapCssPixel(width);
        const lineHeight = this._dndInsertionLineHeight();
        const line = document.createElement('div');
        line.className = 'dnd-placeholder';
        line.style.cssText = `left:${lineLeft}px;width:${lineWidth}px;top:${lineTop}px;height:${lineHeight}px;`;
        document.body.appendChild(line);
        return line;
    },

    /** Returns the closest visible (non-dragging) row before `row` in DOM order. */
    _dndPrevVisibleRow: function (row) {
        const invalidSet = this._dnd ? this._dnd.invalidTargetDids : null;
        const rows = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'));
        const idx = rows.indexOf(row);
        for (let i = idx - 1; i >= 0; i--) {
            if (invalidSet ? !invalidSet.has(rows[i].dataset.did) : !rows[i].classList.contains('is-dragging')) return rows[i];
        }
        return null;
    },

    /** Returns the closest visible (non-dragging) row after `row` in DOM order. */
    _dndNextVisibleRow: function (row) {
        const invalidSet = this._dnd ? this._dnd.invalidTargetDids : null;
        const rows = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'));
        const idx = rows.indexOf(row);
        for (let i = idx + 1; i < rows.length; i++) {
            if (invalidSet ? !invalidSet.has(rows[i].dataset.did) : !rows[i].classList.contains('is-dragging')) return rows[i];
        }
        return null;
    },

    /** Commits a before/after drop to the current DOM before drag visuals are removed. */
    _dndCommitLocalReorder: function (sourceRow, targetRow, insertType, sourceRows) {
        if (!sourceRow || !targetRow) return false;
        if (insertType !== 'before' && insertType !== 'after') return false;
        const rows = sourceRows && sourceRows.length ? sourceRows : [sourceRow];
        if (rows.includes(targetRow)) return false;

        const tbody = rows[0].parentElement;
        if (!tbody || targetRow.parentElement !== tbody) return false;

        // Collect each source row plus its visible descendants as a contiguous block
        const allRows = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'));
        const moveBlocks = [];
        rows.forEach(r => {
            const block = [r];
            const srcIdx = allRows.indexOf(r);
            const srcLevel = parseInt(r.dataset.level || '1', 10);
            for (let i = srcIdx + 1; i < allRows.length; i++) {
                const lvl = parseInt(allRows[i].dataset.level || '1', 10);
                if (lvl <= srcLevel) break;
                block.push(allRows[i]);
            }
            moveBlocks.push(block);
        });

        // Validate all rows still belong to the tbody
        for (const block of moveBlocks) {
            for (const r of block) {
                if (r.parentElement !== tbody) return false;
            }
        }

        const anchor = insertType === 'before' ? targetRow : targetRow.nextSibling;
        moveBlocks.forEach(block => {
            block.forEach(r => tbody.insertBefore(r, anchor));
        });
        return true;
    },

    /** Builds the deck ID order sent to Python after a before/after drop. */
    _dndBuildNewOrder: function (sourceDids, targetDid, insertType, useDomOrder) {
        const allRows = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'));
        const currentOrder = allRows.map(row => row.dataset.did);

        if (useDomOrder) return currentOrder;

        const dnd = this._dnd;
        const originalOrder = dnd && Array.isArray(dnd.originalOrder) && dnd.originalOrder.length
            ? dnd.originalOrder.slice()
            : currentOrder;
        const baseOrder = originalOrder.indexOf(String(targetDid)) !== -1 ? originalOrder : currentOrder;
        const movingDids = dnd && Array.isArray(dnd.movingDids) && dnd.movingDids.length
            ? dnd.movingDids.slice()
            : (Array.isArray(sourceDids) ? sourceDids : [sourceDids]).map(String);
        const movingSet = new Set(movingDids.map(String));
        const sourceGroup = movingDids.filter(did => movingSet.has(String(did)));
        const newOrder = baseOrder.filter(did => !movingSet.has(String(did)));

        const didToLevel = dnd && dnd.levelByDid
            ? dnd.levelByDid
            : new Map(allRows.map(r => [r.dataset.did, parseInt(r.dataset.level || '1', 10)]));

        if (insertType === 'nest') {
            const targetIdx = newOrder.indexOf(targetDid);
            if (targetIdx === -1) return currentOrder;
            const targetLevel = didToLevel.get(targetDid);
            let insertIndex = targetIdx;
            for (let i = targetIdx + 1; i < newOrder.length; i++) {
                const lvl = didToLevel.get(newOrder[i]);
                if (lvl <= targetLevel) break;
                insertIndex = i;
            }
            newOrder.splice(insertIndex + 1, 0, ...sourceGroup);
            return newOrder;
        }

        const targetIndex = newOrder.indexOf(targetDid);
        if (targetIndex === -1) {
            // Defensive fallback: target missing from filtered array, return live DOM order
            return currentOrder;
        }

        newOrder.splice(insertType === 'before' ? targetIndex : targetIndex + 1, 0, ...sourceGroup);
        return newOrder;
    },

    /** Sends a drag/drop result to Python. */
    _dndSendDrop: function (payload) {
        pycmd('onigiri_drag_drop:' + JSON.stringify(payload));
    },

    /** Finalises the drag — fires pycmd and cleans up all state. */
    _dndEnd: function (e) {
        if (!this._dnd) return;

        const dndState = this._dnd;
        const { sourceRow, sourceRows, ghostEl, lastTargetRow, lastInsertType } = dndState;

        // Cancel auto-scroll loop
        if (this._autoScrollRaf) {
            cancelAnimationFrame(this._autoScrollRaf);
            this._autoScrollRaf = null;
        }

        // Clear hover-expand timers before nulling _dnd
        this._dndClearHoverExpand();

        const sourceDids = dndState.sourceDids && dndState.sourceDids.length
            ? dndState.sourceDids.slice()
            : sourceRows.map(r => r.dataset.did).filter(Boolean);
        const targetDid = lastTargetRow ? lastTargetRow.dataset.did : null;

        // Self/descendant drop guard
        const hasDropType = lastInsertType === 'nest' || lastInsertType === 'before' || lastInsertType === 'after';
        const isValidTarget = hasDropType && lastTargetRow && !dndState.invalidTargetDids.has(targetDid);
        const isNoOpDrop = isValidTarget && this._dndIsNoOpDrop(lastTargetRow, lastInsertType);
        const isReorderDrop = isValidTarget && targetDid &&
            !isNoOpDrop && (lastInsertType === 'before' || lastInsertType === 'after');
        const didCommitLocalReorder = isReorderDrop
            ? this._dndCommitLocalReorder(sourceRow, lastTargetRow, lastInsertType, sourceRows)
            : false;

        let dropPayload = null;
        if (isValidTarget && !isNoOpDrop && sourceDids.length && targetDid) {
            const newOrder = this._dndBuildNewOrder(
                sourceDids,
                targetDid,
                lastInsertType,
                didCommitLocalReorder
            );

            if (newOrder) {
                dropPayload = {
                    source_dids: sourceDids,
                    target_did: targetDid,
                    type: lastInsertType,
                    new_order: newOrder,
                    original_order: dndState.originalOrder || [],
                };
            }
        }

        // Cleanup DOM and drop-state classes
        document.body.classList.remove('fast-dragging');
        ghostEl.remove();
        sourceRows.forEach(r => r.classList.remove('is-dragging'));
        if (this._dnd.placeholder) { this._dnd.placeholder.remove(); this._dnd.placeholder = null; }
        if (this._dnd.nestOverlay) { this._dnd.nestOverlay.remove(); this._dnd.nestOverlay = null; }
        this.deckListContainer.querySelectorAll('.drag-over-target, .drop-before, .drop-after')
            .forEach(r => r.classList.remove('drag-over-target', 'drop-before', 'drop-after'));

        document.removeEventListener('pointermove',   this._boundDndMove);
        document.removeEventListener('pointerup',     this._boundDndEnd);
        document.removeEventListener('pointercancel', this._boundDndEnd);
        this._endOverrideState('is-dragging');
        this._dnd = null;

        if (dropPayload) this._dndSendDrop(dropPayload);
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
                    if (!el.dataset.onigiriNoGhost) {
                        el.dataset.onigiriNoGhost = '1';
                        el.addEventListener('pointerdown', () => { OnigiriEngine._collapsePointerActive = true; });
                        el.addEventListener('pointerup',     () => { OnigiriEngine._collapsePointerActive = false; });
                        el.addEventListener('pointercancel', () => { OnigiriEngine._collapsePointerActive = false; });
                    }
                } else if (el.matches('tr.deck')) {
                    const clickableCell = el.querySelector('td.decktd');
                    if (clickableCell) clickableCell.style.cursor = 'pointer';

                    let handle = el.querySelector('.drag-handle');
                    if (!handle) {
                        handle = document.createElement('span');
                        handle.className = 'drag-handle';
                        if (clickableCell) clickableCell.prepend(handle);
                    }

                    if (!handle.dataset.onigiriBound) {
                        handle.dataset.onigiriBound = 'true';
                        handle.title = 'Drag to reparent or reorder';
                        this.applyMaskIcon(handle, this.systemIconUrl('drag_handle.svg'), {
                            color: 'var(--icon-color)',
                            size: this.cssPixelVar('--drag-handle-icon-size', 14),
                        });
                        handle.style.touchAction = 'none'; // Required for pointer events on touch
                        handle.addEventListener('pointerdown', (e) => {
                            if (e.pointerType === 'mouse' && e.button !== 0) return;
                            OnigiriEngine._dndStart(e, handle);
                        });
                        handle.addEventListener('click', (e) => e.stopPropagation());
                        // If the row is already hovered (e.g. after a chevron-triggered
                        // tree refresh), show the handle immediately at full opacity —
                        // skipping the 120 ms fade-in prevents the brief flicker.
                        if (el.classList.contains('is-hovered') && !document.body.classList.contains('is-dragging')) {
                            handle.style.opacity = '0.5';
                            handle.style.transition = 'none';
                            requestAnimationFrame(() => {
                                handle.style.opacity = '';
                                handle.style.transition = '';
                            });
                        }
                    }
                }
            });
        });

        // --- Deck search bar events (bind once only) ---
        const searchInput = document.getElementById('onigiri-deck-search-input');
        if (searchInput && !searchInput.dataset.searchBound) {
            searchInput.dataset.searchBound = 'true';
            searchInput.addEventListener('input', (e) => this._filterDecks(e.target.value));
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') this._closeDeckSearch();
            });
        }
        const searchClose = document.getElementById('onigiri-deck-search-close');
        if (searchClose && !searchClose.dataset.searchBound) {
            searchClose.dataset.searchBound = 'true';
            searchClose.addEventListener('click', () => this._closeDeckSearch());
        }
    },

    _getDeckSearchHeaderLabel: function () {
        const header = document.getElementById('deck-list-header');
        return header ? (header.querySelector('h2') || header) : null;
    },

    toggleDeckSearch: function () {
        const bar = document.getElementById('onigiri-deck-search-bar');
        const searchBtn = document.getElementById('onigiri-search-toolbar-btn');
        const headerLabel = this._getDeckSearchHeaderLabel();
        if (!bar) return;
        if (searchBtn && typeof searchBtn.blur === 'function') searchBtn.blur();
        if (bar.classList.contains('is-visible')) {
            this._closeDeckSearch();
        } else {
            this.closeEllipsisMenu();
            this.closeOrganiseMenu();
            this.closeDeckContextMenu();
            if (typeof window.alignSidebarToolbarToDeckHeader === 'function') {
                window.alignSidebarToolbarToDeckHeader();
            }
            bar.classList.add('is-visible');
            if (typeof window.alignSidebarToolbarToDeckHeader === 'function') {
                requestAnimationFrame(window.alignSidebarToolbarToDeckHeader);
            }
            if (searchBtn) { searchBtn.style.opacity = '0'; searchBtn.style.pointerEvents = 'none'; }
            if (headerLabel) { headerLabel.style.opacity = '0'; headerLabel.style.pointerEvents = 'none'; }
            const focusBtn = document.querySelector('.deck-header-focus-btn');
            if (focusBtn) { focusBtn.style.opacity = '0'; focusBtn.style.pointerEvents = 'none'; }
            const badge = document.getElementById('onigiri-multiselect-badge');
            if (badge) { badge.style.display = 'none'; badge.style.opacity = '0'; badge.style.pointerEvents = 'none'; }
            const input = document.getElementById('onigiri-deck-search-input');
            if (input) { input.value = ''; input.focus({ preventScroll: true }); }
        }
    },

    _closeDeckSearch: function () {
        const bar = document.getElementById('onigiri-deck-search-bar');
        const searchBtn = document.getElementById('onigiri-search-toolbar-btn');
        const headerLabel = this._getDeckSearchHeaderLabel();

        // Restore button + label immediately so they fade back in while bar animates out
        if (searchBtn) { searchBtn.style.opacity = ''; searchBtn.style.pointerEvents = ''; }
        if (headerLabel) { headerLabel.style.opacity = ''; headerLabel.style.pointerEvents = ''; }
        const focusBtn = document.querySelector('.deck-header-focus-btn');
        if (focusBtn) { focusBtn.style.opacity = ''; focusBtn.style.pointerEvents = ''; }
        const badge = document.getElementById('onigiri-multiselect-badge');
        if (badge) { badge.style.display = ''; badge.style.opacity = ''; badge.style.pointerEvents = ''; }

        const input = document.getElementById('onigiri-deck-search-input');
        if (input) input.value = '';
        this.saveScrollPosition(); // preserve position across the tree reload
        this._filterDecks('');

        if (!bar || !bar.classList.contains('is-visible')) {
            if (this._pendingDeferredTreeHtml !== null) this._flushDeferredTreeUpdate();
            return;
        }

        // Play the dismiss animation, then actually hide
        bar.classList.add('is-closing');
        bar.addEventListener('animationend', () => {
            bar.classList.remove('is-visible', 'is-closing');
            if (this._pendingDeferredTreeHtml !== null) this._flushDeferredTreeUpdate();
        }, { once: true });
    },

    _searchDebounceTimer: null,
    _lastDeckSearchQuery: null,

    _filterDecks: function (query) {
        const nextQuery = query.trim();
        clearTimeout(this._searchDebounceTimer);
        this._searchDebounceTimer = setTimeout(() => {
            if (nextQuery === this._lastDeckSearchQuery) return;
            this._lastDeckSearchQuery = nextQuery;
            pycmd('onigiri_deck_search:' + nextQuery);
        }, 300);
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

        // Set icon mask-image using centralized path resolver
        this.applyMaskIcon(el, this.systemIconUrl('right.svg'), {
            color: 'var(--icon-color)',
            size: this.cssPixelVar('--collapse-icon-size', 12),
        });
    },

    closeEllipsisMenu: function () {
        if (typeof window.closeOnigiriCollapsedMoreMenu === 'function') {
            window.closeOnigiriCollapsedMoreMenu();
        }

        const menu = document.getElementById('onigiri-ellipsis-menu');
        const wasOpen = !!menu;
        if (menu) menu.remove();

        const sub = document.getElementById('onigiri-ellipsis-submenu');
        if (sub) sub.remove();

        document.querySelectorAll('.onigiri-ellipsis-toolbar-btn.is-open').forEach(b => b.classList.remove('is-open'));
        if (wasOpen) pycmd('onigiri_ui_close');
        if (this._pendingDeferredTreeHtml !== null) this._flushDeferredTreeUpdate();
    },

    closeOrganiseMenu: function () {
        if (typeof window.closeOnigiriCollapsedMoreMenu === 'function') {
            window.closeOnigiriCollapsedMoreMenu();
        }

        const menu = document.getElementById('onigiri-organise-menu');
        const wasOpen = !!menu;
        if (menu) menu.remove();

        document.querySelectorAll('.onigiri-organise-toolbar-btn.is-open').forEach(b => b.classList.remove('is-open'));
        if (wasOpen) pycmd('onigiri_ui_close');
        if (this._pendingDeferredTreeHtml !== null) this._flushDeferredTreeUpdate();
    },

    _updateOrganiseMenuTick: function (clickedKey) {
        const cfg = window.ONIGIRI_CONFIG;
        if (!cfg || !Array.isArray(cfg.organiseActions)) return;

        // Helper to update action selected state with mutual exclusion rules
        const actions = cfg.organiseActions;
        const clickedAction = actions.find(a => a.key === clickedKey);
        if (!clickedAction) return;

        const isSort = clickedKey.startsWith('sort_');
        const isFilter = clickedKey.startsWith('filter_');

        if (isSort) {
            // Radio group: only one sort option selected at a time
            actions.forEach(a => {
                if (a.key && a.key.startsWith('sort_')) {
                    a.selected = (a.key === clickedKey);
                }
            });
        } else if (isFilter) {
            // Toggle behavior — all filters are independently toggleable
            clickedAction.selected = !clickedAction.selected;
        }

        // Update DOM tick icons in real-time
        const menu = document.getElementById('onigiri-organise-menu');
        if (!menu) return;

        actions.forEach(action => {
            if (!action.key || action.type === 'divider' || action.type === 'section') return;
            const item = menu.querySelector('.action-' + action.key);
            if (!item) return;

            // Find or create tick icon
            let tick = item.querySelector('.ctx-tick');
            if (action.selected && !tick) {
                // Add tick
                const SVG_TICK = this.systemIconUrl('tick.svg');
                tick = this.createMaskIcon(SVG_TICK, {
                    className: 'ctx-icon ctx-tick',
                    color: 'var(--accent-color)',
                    transform: 'translateY(-50%)',
                });
                tick.style.position = 'absolute';
                tick.style.right = '12px';
                tick.style.top = '50%';
                item.appendChild(tick);
            } else if (!action.selected && tick) {
                // Remove tick
                tick.remove();
            }
        });
    },

    closeDeckContextMenu: function () {
        if (typeof window.closeOnigiriCollapsedMoreMenu === 'function') {
            window.closeOnigiriCollapsedMoreMenu();
        }

        const menu = document.getElementById('onigiri-ctx-menu');
        const wasOpen = !!menu || document.body.classList.contains('ctx-menu-open');
        if (menu) menu.remove();

        const sub = document.getElementById('onigiri-mark-submenu');
        if (sub) sub.remove();

        document.querySelectorAll('tr.deck.ctx-row-active').forEach(r => r.classList.remove('ctx-row-active'));
        this._clearHoveredRow();
        this._suppressNextHoverRestore = true;
        if (wasOpen) pycmd('onigiri_ui_close');
        this._endOverrideState('ctx-menu-open');
        if (this._pendingDeferredTreeHtml !== null) this._flushDeferredTreeUpdate();
    },

    applyDeckMark: function (did, markKey) {
        const colors = {
            red: '#FF4B4B',
            blue: '#4488FF',
            green: '#44BB66',
            yellow: '#FFB800',
        };
        const row = document.querySelector(`tr.deck[data-did="${CSS.escape(String(did))}"]`);
        const deckLink = row ? row.querySelector('a.deck') : null;
        if (!deckLink) return;

        window.ONIGIRI_DECK_MARKS = window.ONIGIRI_DECK_MARKS || {};
        if (!markKey || markKey === 'none') {
            delete window.ONIGIRI_DECK_MARKS[String(did)];
            const existing = deckLink.querySelector('.deck-mark-dot');
            if (existing) existing.remove();
            return;
        }

        window.ONIGIRI_DECK_MARKS[String(did)] = markKey;
        let dot = deckLink.querySelector('.deck-mark-dot');
        if (!dot) {
            dot = document.createElement('span');
            dot.className = 'deck-mark-dot';
            deckLink.appendChild(dot);
        }
        dot.style.backgroundColor = colors[markKey] || colors.red;
    },

    showDeckContextMenu: function (x, y, did) {
        this.closeEllipsisMenu();
        this.closeOrganiseMenu();
        this.closeDeckContextMenu();

        // Isolate the row being acted on — clear all other visual states
        this._beginOverrideState('ctx-menu-open');
        this._clearAllRowVisualStates();
        const activeRow = document.querySelector(`tr.deck[data-did="${did}"]`);
        if (activeRow) activeRow.classList.add('ctx-row-active');
        pycmd('onigiri_ui_open');

        const iconUrl = (filename) => this.systemIconUrl(filename);

        const SVG_RENAME       = iconUrl('rename.svg');
        const SVG_ADD_SUBDECK  = iconUrl('add_subdeck.svg');
        const SVG_OPTIONS      = iconUrl('options.svg');
        const SVG_EXPORT       = iconUrl('export_deck.svg');
        const SVG_COPY_ID      = iconUrl('copy_id.svg');
        const SVG_DELETE       = iconUrl('delete.svg');
        const SVG_ARCHIVE      = iconUrl('archive.svg');
        const SVG_UNARCHIVE    = iconUrl('unarchive.svg');
        // Star icons — outline for non-fav, filled for fav
        const SVG_STAR         = iconUrl('star_filled.svg');
        const SVG_STAR_OUTLINE = iconUrl('star_outline.svg');
        // Edit Icon — emoji/smiley face (for "Edit Icon" context menu item)
        const SVG_EDIT_ICON    = iconUrl('edit_icon.svg');
        // Mark icons
        const SVG_MARK         = iconUrl('mark.svg');
        const SVG_REMOVE_MARK  = iconUrl('remove_mark.svg');

        // Determine current favorite state from data-is-fav attribute set by patcher.py
        const _favRow = document.querySelector(`tr.deck[data-did="${did}"]`);
        const isFav = !!(_favRow && _favRow.dataset.isFav === '1');
        const isArchived = !!(_favRow && _favRow.dataset.isArchived === '1');

        function makeCtxIcon(iconSrc, flipX, flipY, iconColor) {
            return this.createMaskIcon(iconSrc, {
                className: 'ctx-icon',
                color: iconColor || 'var(--fg-subtle,var(--fg,currentColor))',
                flipX: flipX,
                flipY: flipY,
            });
        }
        makeCtxIcon = makeCtxIcon.bind(this);

        // Current mark state for this deck
        const _markMap   = window.ONIGIRI_DECK_MARKS || {};
        const currentMark = _markMap[did] || null;
        const MARK_COLORS = [
            { key: 'red',    label: 'Red',    hex: '#FF4B4B' },
            { key: 'blue',   label: 'Blue',   hex: '#4488FF' },
            { key: 'green',  label: 'Green',  hex: '#44BB66' },
            { key: 'yellow', label: 'Yellow', hex: '#FFB800' },
        ];
        // SVG_DOT retained for color-dot sub-items (not used for main Mark icon)

        const groups = [
            // Group 1 — structural edits
            [
                { label: 'Rename',       iconUrl: SVG_RENAME,       cmd: 'onigiri_ctx_rename:'      + did, isModal: true },
                { label: 'Add Subdeck',  iconUrl: SVG_ADD_SUBDECK,  cmd: 'onigiri_ctx_subdeck:'     + did, isModal: true },
                { label: 'Edit Icon',    iconUrl: SVG_EDIT_ICON,    cmd: 'onigiri_ctx_change_icon:' + did, isModal: true },
                {
                    label:     isFav ? 'Unfavorite' : 'favorite',
                    iconUrl:   isFav ? SVG_STAR : SVG_STAR_OUTLINE,
                    iconColor: isFav ? 'var(--accent-color)' : null,
                    cmd:       'onigiri_toggle_favorite:' + did,
                },
                {
                    label:   isArchived ? 'Unarchive' : 'Archive',
                    iconUrl: isArchived ? SVG_UNARCHIVE : SVG_ARCHIVE,
                    cmd:     'onigiri_toggle_archive:' + did,
                },
                // Mark item — rendered as a special submenu row
                { label: 'Mark', iconUrl: SVG_MARK,
                  iconColor: currentMark ? MARK_COLORS.find(c=>c.key===currentMark)?.hex : 'var(--fg-subtle,var(--fg))',
                  isMarkSubmenu: true, did: did, currentMark: currentMark },
            ],
            // Group 2 — manage / info
            [
                { label: 'Deck Options', iconUrl: SVG_OPTIONS,     cmd: 'onigiri_ctx_options:'     + did },
                { label: 'Export Deck',  iconUrl: SVG_EXPORT,      cmd: 'onigiri_ctx_export:'      + did },
                { label: 'Copy ID',      iconUrl: SVG_COPY_ID,     cmd: 'onigiri_ctx_copy_id:'     + did },
            ],
            // Group 3 — destructive
            [
                { label: 'Delete Deck',  iconUrl: SVG_DELETE,      cmd: 'onigiri_ctx_delete:'      + did, danger: true },
            ],
        ];

        const menu = document.createElement('div');
        menu.id = 'onigiri-ctx-menu';

        const _menuCleanup = () => {
            menu.remove();
            const ms = document.getElementById('onigiri-mark-submenu');
            if (ms) ms.remove();
            document.querySelectorAll('tr.deck.ctx-row-active').forEach(r => r.classList.remove('ctx-row-active'));
            this._clearHoveredRow();
            this._suppressNextHoverRestore = true;
            pycmd('onigiri_ui_close');
            this._endOverrideState('ctx-menu-open');
            if (this._pendingDeferredTreeHtml !== null) this._flushDeferredTreeUpdate();
        };

        groups.forEach((group, gi) => {
            if (gi > 0) {
                const hr = document.createElement('hr');
                hr.className = 'onigiri-ellipsis-divider';
                menu.appendChild(hr);
            }
            group.forEach(item => {
                // --- Special Mark submenu item ---
                if (item.isMarkSubmenu) {
                    const el = document.createElement('div');
                    el.className = 'onigiri-ellipsis-item has-submenu';
                    el.style.cssText = 'position:relative;';
                    el.appendChild(makeCtxIcon(item.iconUrl, false, false, item.iconColor));
                    const lbl = document.createElement('span');
                    lbl.textContent = 'Mark';
                    el.appendChild(lbl);
                    if (item.currentMark) {
                        const badge = document.createElement('span');
                        badge.textContent = MARK_COLORS.find(c=>c.key===item.currentMark)?.label || '';
                        badge.style.cssText = 'margin-left:auto;font-size:11px;opacity:0.6;padding-right:2px;';
                        el.appendChild(badge);
                    }
                    const chev = document.createElement('span');
                    chev.className = 'submenu-chevron';
                    chev.textContent = '›';
                    el.appendChild(chev);

                    // Build sub-panel
                    let _markSubTimer = null;
                    const removeMarkSub = () => {
                        if (_markSubTimer) { clearTimeout(_markSubTimer); _markSubTimer = null; }
                        const s = document.getElementById('onigiri-mark-submenu');
                        if (s) s.remove();
                    };
                    const buildMarkSub = () => {
                        if (_markSubTimer) { clearTimeout(_markSubTimer); _markSubTimer = null; }
                        const existing = document.getElementById('onigiri-mark-submenu');
                        if (existing) return;
                        const sub = document.createElement('div');
                        sub.id = 'onigiri-mark-submenu';
                        sub.style.cssText = 'position:fixed;z-index:100001;min-width:160px;border-radius:12px;padding:5px;background:var(--canvas-overlay);border:1px solid var(--border);box-shadow:0 6px 24px rgba(0,0,0,0.18);will-change:transform;backface-visibility:hidden;-webkit-backface-visibility:hidden;transform:translateZ(0);';
                        // Colour items
                        MARK_COLORS.forEach(mc => {
                            const si = document.createElement('div');
                            si.className = 'onigiri-ellipsis-item';
                            const dot = document.createElement('span');
                            dot.style.cssText = `width:12px;height:12px;min-width:12px;border-radius:50%;background:${mc.hex};flex-shrink:0;` +
                                (item.currentMark === mc.key ? `box-shadow:0 0 0 2px var(--canvas-overlay),0 0 0 3.5px ${mc.hex};` : '');
                            si.appendChild(dot);
                            const slbl = document.createElement('span');
                            slbl.textContent = mc.label;
                            si.appendChild(slbl);
                            if (item.currentMark === mc.key) {
                                const ck = document.createElement('span');
                                ck.textContent = '✓';
                                ck.style.cssText = `margin-left:auto;color:${mc.hex};font-size:12px;`;
                                si.appendChild(ck);
                            }
                            si.addEventListener('click', () => {
                                this.applyDeckMark(item.did, mc.key);
                                _menuCleanup();
                                pycmd('onigiri_ctx_mark:' + item.did + ':' + mc.key);
                            });
                            sub.appendChild(si);
                        });
                        // Remove mark
                        if (item.currentMark) {
                            const hr2 = document.createElement('hr');
                            hr2.className = 'onigiri-ellipsis-divider';
                            sub.appendChild(hr2);
                            const si = document.createElement('div');
                            si.className = 'onigiri-ellipsis-item';
                            si.appendChild(makeCtxIcon(SVG_REMOVE_MARK, false, false, null));
                            const slbl = document.createElement('span');
                            slbl.textContent = 'Remove Mark';
                            si.appendChild(slbl);
                            si.addEventListener('click', () => {
                                this.applyDeckMark(item.did, 'none');
                                _menuCleanup();
                                pycmd('onigiri_ctx_mark:' + item.did + ':none');
                            });
                            sub.appendChild(si);
                        }
                        // Cancel hide-timer when cursor enters submenu
                        sub.addEventListener('mouseenter', () => {
                            if (_markSubTimer) { clearTimeout(_markSubTimer); _markSubTimer = null; }
                        });
                        sub.addEventListener('mouseleave', () => {
                            _markSubTimer = setTimeout(removeMarkSub, 120);
                        });
                        // Position: right of the menu item
                        const elR = el.getBoundingClientRect();
                        sub.style.top  = elR.top + 'px';
                        sub.style.left = (elR.right + 4) + 'px';
                        document.body.appendChild(sub);
                        requestAnimationFrame(() => {
                            const sr = sub.getBoundingClientRect();
                            if (sr.right > window.innerWidth) sub.style.left = (elR.left - sr.width - 4) + 'px';
                            if (sr.bottom > window.innerHeight) sub.style.top = (elR.bottom - sr.height) + 'px';
                        });
                    };
                    el.addEventListener('mouseenter', buildMarkSub);
                    el.addEventListener('mouseleave', (e) => {
                        const sub = document.getElementById('onigiri-mark-submenu');
                        if (sub && sub.contains(e.relatedTarget)) return;
                        _markSubTimer = setTimeout(removeMarkSub, 120);
                    });
                    menu.appendChild(el);
                    return;
                }
                // --- Normal item ---
                const el = document.createElement('div');
                el.className = 'onigiri-ellipsis-item' + (item.danger ? ' item-danger' : '');
                el.appendChild(makeCtxIcon(item.iconUrl, item.flipX, item.flipY, item.iconColor));
                const span = document.createElement('span');
                span.textContent = item.label;
                el.appendChild(span);
                el.addEventListener('click', () => {
                    if (item.isModal) {
                        menu.remove();
                        const ms = document.getElementById('onigiri-mark-submenu');
                        if (ms) ms.remove();
                        document.body.classList.remove('ctx-menu-open');
                        this._clearHoveredRow();
                        this._suppressNextHoverRestore = true;
                        this._beginOverrideState('dialog-focus');
                        pycmd(item.cmd);
                    } else {
                        _menuCleanup();
                        pycmd(item.cmd);
                    }
                });
                menu.appendChild(el);
            });
        });

        menu.style.position = 'fixed';
        menu.style.top = y + 'px';
        menu.style.left = x + 'px';
        document.body.appendChild(menu);

        requestAnimationFrame(() => {
            const r = menu.getBoundingClientRect();
            if (r.right > window.innerWidth)  menu.style.left = (x - r.width)  + 'px';
            if (r.bottom > window.innerHeight) menu.style.top  = (y - r.height) + 'px';
        });

        setTimeout(() => {
            function dismiss(e) {
                if (e.type === 'keydown' && e.key !== 'Escape') return;
                OnigiriEngine.closeDeckContextMenu();
                document.removeEventListener('click', dismiss);
                document.removeEventListener('keydown', dismiss);
                window.removeEventListener('blur', dismiss);
            }
            document.addEventListener('click', dismiss);
            document.addEventListener('keydown', dismiss);
            window.addEventListener('blur', dismiss);
        }, 0);
    },

    showMultiDeckContextMenu: function (x, y, anchorDid) {
        this.closeEllipsisMenu();
        this.closeOrganiseMenu();
        this.closeDeckContextMenu();

        this._beginOverrideState('ctx-menu-open');
        document.querySelectorAll('tr.deck.ctx-row-active').forEach(r => r.classList.remove('ctx-row-active'));
        this._multiSelectedDecks.forEach(did => {
            const row = document.querySelector(`tr.deck[data-did="${this.escapeSelectorValue(did)}"]`);
            if (row) row.classList.add('ctx-row-active');
        });
        pycmd('onigiri_ui_open');

        const iconUrl = (filename) => this.systemIconUrl(filename);
        const SVG_STAR         = iconUrl('star_filled.svg');
        const SVG_STAR_OUTLINE = iconUrl('star_outline.svg');
        const SVG_ARCHIVE      = iconUrl('archive.svg');
        const SVG_UNARCHIVE    = iconUrl('unarchive.svg');
        const SVG_MARK         = iconUrl('mark.svg');
        const SVG_REMOVE_MARK  = iconUrl('remove_mark.svg');
        const SVG_DELETE       = iconUrl('delete.svg');

        const dids = Array.from(this._multiSelectedDecks);
        const _markMap = window.ONIGIRI_DECK_MARKS || {};

        // Majority-rule scan of selected decks
        const favCount = dids.filter(did => {
            const row = document.querySelector(`tr.deck[data-did="${this.escapeSelectorValue(did)}"]`);
            return row && row.dataset.isFav === '1';
        }).length;
        const favMajority = favCount > dids.length / 2;

        const arcCount = dids.filter(did => {
            const row = document.querySelector(`tr.deck[data-did="${this.escapeSelectorValue(did)}"]`);
            return row && row.dataset.isArchived === '1';
        }).length;
        const arcMajority = arcCount > dids.length / 2;

        const markCount = dids.filter(did => !!_markMap[did]).length;
        const markMajority = markCount > dids.length / 2;
        const markAny = markCount > 0;

        const MARK_COLORS = [
            { key: 'red',    label: 'Red',    hex: '#FF4B4B' },
            { key: 'blue',   label: 'Blue',   hex: '#4488FF' },
            { key: 'green',  label: 'Green',  hex: '#44BB66' },
            { key: 'yellow', label: 'Yellow', hex: '#FFB800' },
        ];

        function makeCtxIcon(iconSrc, iconColor) {
            return OnigiriEngine.createMaskIcon(iconSrc, {
                className: 'ctx-icon',
                color: iconColor || 'var(--fg-subtle,var(--fg,currentColor))',
            });
        }

        // Build groups dynamically based on majority rule
        const toggleGroup = [];
        if (favMajority) {
            toggleGroup.push({ label: 'Unfavorite', iconUrl: SVG_STAR, iconColor: 'var(--accent-color)', cmd: 'onigiri_ctx_bulk_unfavorite' });
        } else {
            toggleGroup.push({ label: 'Favourite', iconUrl: SVG_STAR_OUTLINE, cmd: 'onigiri_ctx_bulk_favorite' });
        }
        if (arcMajority) {
            toggleGroup.push({ label: 'Unarchive', iconUrl: SVG_UNARCHIVE, cmd: 'onigiri_ctx_bulk_unarchive' });
        } else {
            toggleGroup.push({ label: 'Archive', iconUrl: SVG_ARCHIVE, cmd: 'onigiri_ctx_bulk_archive' });
        }
        toggleGroup.push({ label: markMajority ? 'Change Mark' : 'Mark', iconUrl: SVG_MARK, isMarkSubmenu: true });

        const groups = [
            toggleGroup,
            [{ label: 'Delete', iconUrl: SVG_DELETE, danger: true, cmd: 'onigiri_ctx_bulk_delete' }],
        ];

        const menu = document.createElement('div');
        menu.id = 'onigiri-ctx-menu';

        const _menuCleanup = () => {
            menu.remove();
            const ms = document.getElementById('onigiri-mark-submenu');
            if (ms) ms.remove();
            document.querySelectorAll('tr.deck.ctx-row-active').forEach(r => r.classList.remove('ctx-row-active'));
            this._clearHoveredRow();
            this._suppressNextHoverRestore = true;
            pycmd('onigiri_ui_close');
            this._endOverrideState('ctx-menu-open');
            if (this._pendingDeferredTreeHtml !== null) this._flushDeferredTreeUpdate();
        };

        groups.forEach((group, gi) => {
            if (gi > 0) {
                const hr = document.createElement('hr');
                hr.className = 'onigiri-ellipsis-divider';
                menu.appendChild(hr);
            }
            group.forEach(item => {
                if (item.isMarkSubmenu) {
                    const el = document.createElement('div');
                    el.className = 'onigiri-ellipsis-item has-submenu';
                    el.style.cssText = 'position:relative;';
                    el.appendChild(makeCtxIcon(item.iconUrl, null));
                    const lbl = document.createElement('span');
                    lbl.textContent = item.label;
                    el.appendChild(lbl);
                    const chev = document.createElement('span');
                    chev.className = 'submenu-chevron';
                    chev.textContent = '›';
                    el.appendChild(chev);

                    let _markSubTimer = null;
                    const removeMarkSub = () => {
                        if (_markSubTimer) { clearTimeout(_markSubTimer); _markSubTimer = null; }
                        const s = document.getElementById('onigiri-mark-submenu');
                        if (s) s.remove();
                    };
                    const buildMarkSub = () => {
                        if (_markSubTimer) { clearTimeout(_markSubTimer); _markSubTimer = null; }
                        const existing = document.getElementById('onigiri-mark-submenu');
                        if (existing) return;
                        const sub = document.createElement('div');
                        sub.id = 'onigiri-mark-submenu';
                        sub.style.cssText = 'position:fixed;z-index:100001;min-width:160px;border-radius:12px;padding:5px;background:var(--canvas-overlay);border:1px solid var(--border);box-shadow:0 6px 24px rgba(0,0,0,0.18);will-change:transform;backface-visibility:hidden;-webkit-backface-visibility:hidden;transform:translateZ(0);';
                        // Remove mark option at top
                        if (markAny) {
                            const rm = document.createElement('div');
                            rm.className = 'onigiri-ellipsis-item';
                            const rmIcon = document.createElement('span');
                            rmIcon.style.cssText = 'width:12px;height:12px;min-width:12px;flex-shrink:0;display:flex;align-items:center;justify-content:center;';
                            rmIcon.appendChild(makeCtxIcon(SVG_REMOVE_MARK, null));
                            rm.appendChild(rmIcon);
                            const rmLbl = document.createElement('span');
                            rmLbl.textContent = 'Remove mark';
                            rm.appendChild(rmLbl);
                            rm.addEventListener('click', () => {
                                _menuCleanup();
                                this.clearMultiSelection();
                                pycmd('onigiri_ctx_bulk_mark:' + JSON.stringify({ dids, mark: 'none' }));
                            });
                            sub.appendChild(rm);
                        }
                        MARK_COLORS.forEach(mc => {
                            const si = document.createElement('div');
                            si.className = 'onigiri-ellipsis-item';
                            const dot = document.createElement('span');
                            dot.style.cssText = `width:12px;height:12px;min-width:12px;border-radius:50%;background:${mc.hex};flex-shrink:0;`;
                            si.appendChild(dot);
                            const slbl = document.createElement('span');
                            slbl.textContent = mc.label;
                            si.appendChild(slbl);
                            si.addEventListener('click', () => {
                                _menuCleanup();
                                this.clearMultiSelection();
                                pycmd('onigiri_ctx_bulk_mark:' + JSON.stringify({ dids, mark: mc.key }));
                            });
                            sub.appendChild(si);
                        });
                        const elR = el.getBoundingClientRect();
                        sub.style.top = elR.top + 'px';
                        sub.style.left = (elR.right + 4) + 'px';
                        document.body.appendChild(sub);
                        requestAnimationFrame(() => {
                            const sr = sub.getBoundingClientRect();
                            if (sr.right > window.innerWidth) sub.style.left = (elR.left - sr.width - 4) + 'px';
                            if (sr.bottom > window.innerHeight) sub.style.top = (elR.bottom - sr.height) + 'px';
                        });
                    };
                    el.addEventListener('mouseenter', buildMarkSub);
                    el.addEventListener('mouseleave', (e) => {
                        const sub = document.getElementById('onigiri-mark-submenu');
                        if (sub && sub.contains(e.relatedTarget)) return;
                        _markSubTimer = setTimeout(removeMarkSub, 120);
                    });
                    menu.appendChild(el);
                    return;
                }
                const el = document.createElement('div');
                el.className = 'onigiri-ellipsis-item' + (item.danger ? ' item-danger' : '');
                el.appendChild(makeCtxIcon(item.iconUrl, item.iconColor));
                const span = document.createElement('span');
                span.textContent = item.label;
                el.appendChild(span);
                el.addEventListener('click', () => {
                    _menuCleanup();
                    this.clearMultiSelection();
                    pycmd(item.cmd + ':' + JSON.stringify({ dids }));
                });
                menu.appendChild(el);
            });
        });

        menu.style.position = 'fixed';
        menu.style.top = y + 'px';
        menu.style.left = x + 'px';
        document.body.appendChild(menu);

        requestAnimationFrame(() => {
            const r = menu.getBoundingClientRect();
            if (r.right > window.innerWidth) menu.style.left = (x - r.width) + 'px';
            if (r.bottom > window.innerHeight) menu.style.top = (y - r.height) + 'px';
        });

        setTimeout(() => {
            function dismiss(e) {
                if (e.type === 'keydown' && e.key !== 'Escape') return;
                OnigiriEngine.closeDeckContextMenu();
                document.removeEventListener('click', dismiss);
                document.removeEventListener('keydown', dismiss);
                window.removeEventListener('blur', dismiss);
            }
            document.addEventListener('click', dismiss);
            document.addEventListener('keydown', dismiss);
            window.addEventListener('blur', dismiss);
        }, 0);
    },

    showOrganiseMenu: function (btn, event) {
        if (event) { event.preventDefault(); event.stopPropagation(); }

        const existing = document.getElementById('onigiri-organise-menu');
        if (existing) {
            this.closeOrganiseMenu();
            return;
        }

        this.closeDeckContextMenu();
        this.closeEllipsisMenu();

        const cfg = window.ONIGIRI_CONFIG || {};
        const actions = Array.isArray(cfg.organiseActions) ? cfg.organiseActions : [];
        if (!actions.length) return;

        const SVG_TICK = this.systemIconUrl('tick.svg');

        const makeTickIcon = () => {
            const tick = this.createMaskIcon(SVG_TICK, {
                className: 'ctx-icon ctx-tick',
                color: 'var(--accent-color)',
                transform: 'translateY(-50%)',
            });
            tick.style.position = 'absolute';
            tick.style.right = '12px';
            tick.style.top = '50%';
            return tick;
        };

        const makeIcon = (iconUrl) => this.createMaskIcon(iconUrl, {
            tagName: 'i',
            className: 'icon',
            color: 'var(--fg-subtle,var(--fg,currentColor))',
        });

        const menu = document.createElement('div');
        menu.id = 'onigiri-organise-menu';

        actions.forEach((action) => {
            if (action.type === 'divider') {
                const hr = document.createElement('hr');
                hr.className = 'onigiri-ellipsis-divider';
                menu.appendChild(hr);
                return;
            }
            if (action.type === 'section') {
                const sh = document.createElement('div');
                sh.className = 'ellipsis-section-label';
                sh.textContent = action.label;
                menu.appendChild(sh);
                return;
            }

            const item = document.createElement('div');
            item.className = 'onigiri-ellipsis-item action-' + (action.key || '');
            item.appendChild(makeIcon(action.iconUrl));

            const label = document.createElement('span');
            label.textContent = action.label;
            item.appendChild(label);

            if (action.selected) {
                item.appendChild(makeTickIcon());
            }

            item.addEventListener('click', (e) => {
                e.stopPropagation();
                // Persistent: do NOT close menu on click; update tick state immediately
                this._updateOrganiseMenuTick(action.key);
                if (action.command) pycmd(action.command);
            });

            menu.appendChild(item);
        });

        // Store reference for live tick updates
        this._organiseMenuActions = actions;

        const rect = btn ? btn.getBoundingClientRect() : { top: 16, bottom: 40, left: window.innerWidth - 210, right: window.innerWidth - 15 };
        menu.style.position = 'fixed';
        menu.style.top = (rect.bottom + 6) + 'px';
        menu.style.left = rect.left + 'px';

        document.body.appendChild(menu);
        if (btn) btn.classList.add('is-open');
        pycmd('onigiri_ui_open');

        requestAnimationFrame(() => {
            const r = menu.getBoundingClientRect();
            if (r.right > window.innerWidth) menu.style.left = Math.max(8, rect.right - r.width) + 'px';
            if (r.bottom > window.innerHeight) menu.style.top = Math.max(8, rect.top - r.height - 6) + 'px';
        });

        setTimeout(() => {
            const dismiss = (e) => {
                if (e.type === 'keydown' && e.key !== 'Escape') return;
                if (e.type === 'click' && menu.contains(e.target)) return;
                this.closeOrganiseMenu();
                document.removeEventListener('click', dismiss);
                document.removeEventListener('keydown', dismiss);
                window.removeEventListener('blur', dismiss);
            };
            document.addEventListener('click', dismiss);
            document.addEventListener('keydown', dismiss);
            window.addEventListener('blur', dismiss);
        }, 0);
    },

    showEllipsisMenu: function (btn, event) {
        if (event) { event.preventDefault(); event.stopPropagation(); }
        this.closeDeckContextMenu();
        this.closeOrganiseMenu();

        const existing = document.getElementById('onigiri-ellipsis-menu');
        if (existing) {
            this.closeEllipsisMenu();
            return;
        }

        const actions = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.minimalModeActions) || [];
        if (!actions.length) return;

        const SVG_TICK = this.systemIconUrl('tick.svg');

        function makeTickIcon() {
            const tick = this.createMaskIcon(SVG_TICK, {
                className: 'ctx-icon ctx-tick',
                color: 'var(--accent-color)',
                transform: 'translateY(-50%)',
            });
            tick.style.position = 'absolute';
            tick.style.right = '12px';
            tick.style.top = '50%';
            return tick;
        }
        makeTickIcon = makeTickIcon.bind(this);

        function makeIcon(iconUrl) {
            return this.createMaskIcon(iconUrl, {
                tagName: 'i',
                className: 'icon',
                color: 'var(--fg-subtle,var(--fg,currentColor))',
            });
        }
        makeIcon = makeIcon.bind(this);

        function closeSubmenus() {
            const s = document.getElementById('onigiri-ellipsis-submenu');
            if (s) s.remove();
        }

        function closeAll() {
            OnigiriEngine.closeEllipsisMenu();
        }

        const menu = document.createElement('div');
        menu.id = 'onigiri-ellipsis-menu';

        let lastGroup = null;
        actions.forEach(function(action) {
            const group = action.group || 'default';
            if (lastGroup !== null && group !== lastGroup) {
                const divider = document.createElement('hr');
                divider.className = 'onigiri-ellipsis-divider';
                menu.appendChild(divider);
            }
            lastGroup = group;

            const item = document.createElement('div');
            item.className = 'onigiri-ellipsis-item action-' + action.key;
            item.appendChild(makeIcon(action.iconUrl));

            const label = document.createElement('span');
            label.textContent = action.label;
            item.appendChild(label);

            // Sync item: apply stored status and inject the indicator dot
            if (action.key === 'sync') {
                const _ss = window._onigiriSyncStatus || 'none';
                if (_ss === 'sync')   item.classList.add('sync-needed');
                if (_ss === 'upload') item.classList.add('sync-upload-needed');
                const _ind = document.createElement('span');
                _ind.className = 'sync-status-indicator';
                item.appendChild(_ind);
            }
            if (action.selected) {
                item.appendChild(makeTickIcon());
            }

            if (action.children && action.children.length) {
                // Nested item — show chevron and hover submenu
                item.classList.add('has-submenu');
                const chevron = document.createElement('span');
                chevron.className = 'submenu-chevron';
                chevron.textContent = '›';
                item.appendChild(chevron);

                let hideTimer = null;
                function showSub() {
                    clearTimeout(hideTimer);
                    closeSubmenus();

                    const sub = document.createElement('div');
                    sub.id = 'onigiri-ellipsis-submenu';

                    action.children.forEach(function(child) {
                        if (child.type === 'divider') {
                            const hr = document.createElement('hr');
                            hr.className = 'onigiri-ellipsis-divider';
                            sub.appendChild(hr);
                            return;
                        }
                        if (child.type === 'section') {
                            const sh = document.createElement('div');
                            sh.className = 'ellipsis-section-label';
                            sh.textContent = child.label;
                            sub.appendChild(sh);
                            return;
                        }
                        const ci = document.createElement('div');
                        ci.className = 'onigiri-ellipsis-item action-' + (child.key || '');
                        ci.appendChild(makeIcon(child.iconUrl));
                        const cl = document.createElement('span');
                        cl.textContent = child.label;
                        ci.appendChild(cl);
                        if (child.selected) {
                            ci.appendChild(makeTickIcon());
                        }
                        ci.addEventListener('click', function(e) {
                            e.stopPropagation();
                            closeAll();
                            if (child.command) pycmd(child.command);
                        });
                        sub.appendChild(ci);
                    });

                    const r = item.getBoundingClientRect();
                    sub.style.position = 'fixed';
                    sub.style.top  = r.top + 'px';
                    sub.style.left = (r.right + 6) + 'px';
                    document.body.appendChild(sub);

                    sub.addEventListener('mouseenter', function() { clearTimeout(hideTimer); });
                    sub.addEventListener('mouseleave', function() {
                        hideTimer = setTimeout(closeSubmenus, 120);
                    });
                }

                item.addEventListener('mouseenter', showSub);
                item.addEventListener('mouseleave', function(e) {
                    hideTimer = setTimeout(function() {
                        const sub = document.getElementById('onigiri-ellipsis-submenu');
                        if (sub && !sub.matches(':hover')) closeSubmenus();
                    }, 120);
                });
            } else {
                item.addEventListener('click', function() {
                    closeAll();
                    if (action.command) pycmd(action.command);
                });
                item.addEventListener('mouseenter', closeSubmenus);
            }

            menu.appendChild(item);
        });

        const rect = btn ? btn.getBoundingClientRect() : { bottom: 40, left: window.innerWidth - 200 };
        menu.style.position = 'fixed';
        menu.style.top  = (rect.bottom + 6) + 'px';
        menu.style.left = rect.left + 'px';

        document.body.appendChild(menu);
        if (btn) btn.classList.add('is-open');
        pycmd('onigiri_ui_open');

        setTimeout(function() {
            document.addEventListener('click', function dismiss(e) {
                const sub = document.getElementById('onigiri-ellipsis-submenu');
                if (!menu.contains(e.target) && !(sub && sub.contains(e.target))) {
                    closeAll();
                    document.removeEventListener('click', dismiss);
                }
            });
        }, 0);
    },
};

// Initialize the engine once the DOM is ready.
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => OnigiriEngine.init());
} else {
    OnigiriEngine.init();
}

// =============================================================================
// In-page Icon Chooser Modal
// Opened by Python via: context.web.eval("OnigiriIconChooser.open({...})")
// Tabs: Emojis | Icons | Upload
// =============================================================================
window.OnigiriIconChooser = (function () {
    var _state = {};

    function _css(el, css) { el.style.cssText = css; }

    function _addCleanup(state, fn) {
        if (!state) return;
        if (!Array.isArray(state._cleanupFns)) state._cleanupFns = [];
        state._cleanupFns.push(fn);
    }

    function _runCleanup(state) {
        if (!state || !Array.isArray(state._cleanupFns)) return;
        while (state._cleanupFns.length) {
            var fn = state._cleanupFns.pop();
            try { fn(); } catch (_) {}
        }
    }

    function _close(skipRestore) {
        var bd = document.getElementById('onigiri-icon-backdrop');
        _runCleanup(_state);
        if (bd) {
            bd.remove();
            document.querySelectorAll('tr.deck.ctx-row-active').forEach(function (r) { r.classList.remove('ctx-row-active'); });
            if (!skipRestore && typeof OnigiriEngine !== 'undefined') {
                OnigiriEngine._applyMultiSelectionStyles();
            }
            pycmd('onigiri_ui_close');
        }
    }

    // Emoji data — {c: char, k: keywords} for searchable emoji list
    var EMOJI_DATA = [
        {c:'😀',k:'grinning smile happy face'},
        {c:'😃',k:'smile happy big eyes face'},
        {c:'😄',k:'smile happy laugh eyes face'},
        {c:'😁',k:'grin beam smile happy teeth'},
        {c:'😆',k:'laugh grin squint happy'},
        {c:'😅',k:'sweat smile nervous laugh'},
        {c:'🤣',k:'rofl rolling laughing floor'},
        {c:'😂',k:'joy laugh cry tears funny'},
        {c:'🙂',k:'slightly smile happy'},
        {c:'🙃',k:'upside down smile'},
        {c:'😉',k:'wink smile flirt'},
        {c:'😊',k:'blush smile happy warm'},
        {c:'😇',k:'innocent angel halo smile'},
        {c:'🥰',k:'smiling hearts love adore'},
        {c:'😍',k:'heart eyes love adore star'},
        {c:'🤩',k:'star eyes excited wow'},
        {c:'😘',k:'kiss blow wink love'},
        {c:'😗',k:'kiss whistle'},
        {c:'😚',k:'kiss eyes closed love'},
        {c:'😙',k:'kiss smile'},
        {c:'🥲',k:'smile tear holding back'},
        {c:'😋',k:'yum tongue food delicious'},
        {c:'😛',k:'tongue out tease playful'},
        {c:'😜',k:'wink tongue playful'},
        {c:'🤪',k:'zany crazy wild silly'},
        {c:'😝',k:'tongue squint tease'},
        {c:'🤑',k:'money mouth rich dollar'},
        {c:'🤗',k:'hugging hug warm embrace'},
        {c:'🤭',k:'thinking hand over mouth secret'},
        {c:'🤫',k:'shh quiet secret whisper'},
        {c:'🤔',k:'thinking hmm curious'},
        {c:'😐',k:'neutral expressionless blank'},
        {c:'😑',k:'expressionless blank dead'},
        {c:'😶',k:'no mouth silent speechless'},
        {c:'😏',k:'smirk sly knowing'},
        {c:'😒',k:'unamused skeptical eyeroll'},
        {c:'🙄',k:'eye roll bored sigh'},
        {c:'😬',k:'grimace awkward nervous'},
        {c:'😌',k:'relieved content peaceful calm'},
        {c:'😔',k:'pensive sad thoughtful'},
        {c:'😪',k:'sleepy tired exhausted'},
        {c:'🤤',k:'drool drooling hungry'},
        {c:'😴',k:'sleep sleeping zzz tired'},
        {c:'😷',k:'mask sick ill medical'},
        {c:'🤒',k:'sick ill fever thermometer'},
        {c:'🤕',k:'injured bandage hurt pain'},
        {c:'🤢',k:'nausea sick green ill'},
        {c:'🤮',k:'vomit sick disgusting'},
        {c:'🤧',k:'sneeze sick tissue cold'},
        {c:'🥵',k:'hot sweating fever'},
        {c:'🥶',k:'cold freezing ice shiver'},
        {c:'🥴',k:'woozy dizzy drunk'},
        {c:'😵',k:'dizzy spiral shocked'},
        {c:'🤯',k:'exploding head mind blown shocked'},
        {c:'🤠',k:'cowboy hat western'},
        {c:'🥳',k:'party celebrate birthday hat'},
        {c:'😎',k:'cool sunglasses awesome'},
        {c:'🤓',k:'nerd glasses smart study'},
        {c:'🧐',k:'monocle curious inspect detective'},
        {c:'😕',k:'confused puzzled concerned'},
        {c:'😟',k:'worried concerned anxious'},
        {c:'🙁',k:'frown sad unhappy'},
        {c:'☹️',k:'frown sad unhappy'},
        {c:'😮',k:'surprised open mouth wow'},
        {c:'😯',k:'hushed surprised silent'},
        {c:'😲',k:'astonished shocked wow'},
        {c:'😳',k:'flushed embarrassed shocked'},
        {c:'🥺',k:'pleading puppy eyes cute beg'},
        {c:'😦',k:'frown open mouth sad'},
        {c:'😧',k:'anguished distressed worried'},
        {c:'😨',k:'fearful scared afraid'},
        {c:'😰',k:'anxious sweat worried nervous'},
        {c:'😥',k:'sad disappointed relieved'},
        {c:'😢',k:'cry sad tear crying'},
        {c:'😭',k:'loudly crying sob tear'},
        {c:'😱',k:'scream fear horror shocked'},
        {c:'😖',k:'confounded distressed'},
        {c:'😣',k:'persevere struggling effort'},
        {c:'😞',k:'disappointed sad let down'},
        {c:'😓',k:'downcast sweat sad'},
        {c:'😩',k:'weary tired exhausted'},
        {c:'😫',k:'tired weary exhausted'},
        {c:'🥱',k:'yawn tired bored sleepy'},
        {c:'😤',k:'steam angry frustrated'},
        {c:'😡',k:'angry rage mad'},
        {c:'😠',k:'angry mad annoyed'},
        {c:'🤬',k:'cursing swearing angry rage symbols'},
        {c:'😈',k:'devil smiling evil horns'},
        {c:'👿',k:'devil angry evil horns'},
        {c:'💀',k:'skull death dead'},
        {c:'☠️',k:'skull crossbones death danger'},
        {c:'💩',k:'poop turd pile'},
        {c:'🤡',k:'clown joker clown face'},
        {c:'👹',k:'ogre demon monster'},
        {c:'👺',k:'goblin red demon'},
        {c:'👻',k:'ghost halloween spooky'},
        {c:'👽',k:'alien extraterrestrial'},
        {c:'👾',k:'space invader alien game'},
        {c:'🤖',k:'robot android mechanical'},
        {c:'👋',k:'wave hello goodbye hand'},
        {c:'🤚',k:'raised back of hand stop'},
        {c:'🖐️',k:'hand splayed five'},
        {c:'✋',k:'raised hand stop five'},
        {c:'🖖',k:'vulcan salute spock'},
        {c:'🫱',k:'rightward hand'},
        {c:'🫲',k:'leftward hand'},
        {c:'🤝',k:'handshake deal agreement'},
        {c:'👏',k:'clapping applause praise'},
        {c:'🙌',k:'raising hands celebration praise'},
        {c:'🫶',k:'heart hands love'},
        {c:'👐',k:'open hands hug'},
        {c:'🤲',k:'palms up prayer together'},
        {c:'🙏',k:'folded hands prayer please thanks'},
        {c:'✌️',k:'victory peace two fingers'},
        {c:'🤞',k:'crossed fingers luck hope'},
        {c:'🫰',k:'snap fingers'},
        {c:'🤟',k:'love you hand sign i love you'},
        {c:'🤘',k:'sign of horns rock metal'},
        {c:'🤙',k:'call me hang loose shaka'},
        {c:'👈',k:'backhand pointing left'},
        {c:'👉',k:'backhand pointing right'},
        {c:'👆',k:'backhand pointing up'},
        {c:'👇',k:'backhand pointing down'},
        {c:'☝️',k:'index pointing up one'},
        {c:'👍',k:'thumbs up like approve good'},
        {c:'👎',k:'thumbs down dislike bad'},
        {c:'✊',k:'raised fist strong'},
        {c:'👊',k:'oncoming fist punch'},
        {c:'🤛',k:'left facing fist bump'},
        {c:'🤜',k:'right facing fist bump'},
        {c:'💪',k:'flexed bicep strong muscle arm'},
        {c:'🦾',k:'mechanical arm robot prosthetic'},
        {c:'👀',k:'eyes look watching'},
        {c:'👁️',k:'eye look see'},
        {c:'👅',k:'tongue mouth'},
        {c:'👂',k:'ear listen hear'},
        {c:'👃',k:'nose smell sniff'},
        {c:'👶',k:'baby infant child'},
        {c:'🧒',k:'child kid young'},
        {c:'👦',k:'boy male child'},
        {c:'👧',k:'girl female child'},
        {c:'🧑',k:'person adult neutral'},
        {c:'👱',k:'person blond hair'},
        {c:'🧔',k:'person beard man'},
        {c:'🧓',k:'older person'},
        {c:'👴',k:'old man grandfather elderly'},
        {c:'👵',k:'old woman grandmother elderly'},
        {c:'👮',k:'police officer cop law'},
        {c:'👷',k:'construction worker hard hat'},
        {c:'💂',k:'guard soldier'},
        {c:'🕵️',k:'detective investigate spy'},
        {c:'👩‍⚕️',k:'doctor nurse medical health woman'},
        {c:'👨‍⚕️',k:'doctor nurse medical health man'},
        {c:'👩‍🎓',k:'graduate student education woman'},
        {c:'👨‍🎓',k:'graduate student education man'},
        {c:'👩‍🏫',k:'teacher school woman'},
        {c:'👨‍🏫',k:'teacher school man'},
        {c:'👩‍⚖️',k:'judge law court woman'},
        {c:'👨‍⚖️',k:'judge law court man'},
        {c:'👩‍🌾',k:'farmer woman'},
        {c:'👨‍🌾',k:'farmer man'},
        {c:'👩‍🍳',k:'chef cook woman'},
        {c:'👨‍🍳',k:'chef cook man'},
        {c:'👩‍🔧',k:'mechanic repair woman'},
        {c:'👨‍🔧',k:'mechanic repair man'},
        {c:'👩‍💻',k:'technologist computer woman'},
        {c:'👨‍💻',k:'technologist computer man'},
        {c:'👩‍🎤',k:'singer musician woman'},
        {c:'👨‍🎤',k:'singer musician man'},
        {c:'👩‍🎨',k:'artist painter woman'},
        {c:'👨‍🎨',k:'artist painter man'},
        {c:'👩‍✈️',k:'pilot plane woman'},
        {c:'👨‍✈️',k:'pilot plane man'},
        {c:'👩‍🚀',k:'astronaut space woman'},
        {c:'👨‍🚀',k:'astronaut space man'},
        {c:'🧑‍🤝‍🧑',k:'people holding hands couple'},
        {c:'👫',k:'woman man holding hands couple'},
        {c:'💃',k:'woman dancing dance'},
        {c:'🕺',k:'man dancing dance'},
        {c:'🧑‍🦽',k:'wheelchair disability'},
        {c:'🧑‍🦯',k:'blind cane white stick'},
        {c:'🐶',k:'dog puppy pet animal'},
        {c:'🐱',k:'cat kitten pet animal'},
        {c:'🐭',k:'mouse rodent animal'},
        {c:'🐹',k:'hamster pet rodent'},
        {c:'🐰',k:'rabbit bunny easter hop'},
        {c:'🦊',k:'fox animal cunning red'},
        {c:'🐻',k:'bear animal brown'},
        {c:'🐼',k:'panda bear china bamboo'},
        {c:'🐨',k:'koala australia animal'},
        {c:'🐯',k:'tiger big cat stripes'},
        {c:'🦁',k:'lion king pride cat'},
        {c:'🐮',k:'cow moo farm bovine'},
        {c:'🐷',k:'pig oink farm animal'},
        {c:'🐸',k:'frog leap green amphibian'},
        {c:'🐵',k:'monkey ape primate'},
        {c:'🦍',k:'gorilla ape primate'},
        {c:'🦧',k:'orangutan ape primate'},
        {c:'🐺',k:'wolf howl wild'},
        {c:'🐗',k:'boar pig wild'},
        {c:'🐴',k:'horse equine'},
        {c:'🦄',k:'unicorn magic horn rainbow'},
        {c:'🦌',k:'deer stag antler'},
        {c:'🦬',k:'bison buffalo'},
        {c:'🐂',k:'ox bull farm'},
        {c:'🐃',k:'water buffalo'},
        {c:'🐄',k:'cow farm dairy'},
        {c:'🐎',k:'horse race equine'},
        {c:'🐖',k:'pig farm pork'},
        {c:'🐏',k:'ram sheep wool'},
        {c:'🐑',k:'sheep ewe wool'},
        {c:'🦙',k:'llama alpaca'},
        {c:'🐐',k:'goat farm'},
        {c:'🦒',k:'giraffe tall neck africa'},
        {c:'🦘',k:'kangaroo australia joey pouch'},
        {c:'🦛',k:'hippopotamus hippo africa'},
        {c:'🦏',k:'rhinoceros rhino horn'},
        {c:'🐘',k:'elephant trunk africa asia'},
        {c:'🦣',k:'mammoth prehistoric tusks'},
        {c:'🦤',k:'dodo bird extinct'},
        {c:'🐪',k:'camel desert dromedary'},
        {c:'🐫',k:'camel two humps bactrian'},
        {c:'🐆',k:'leopard spots cat predator'},
        {c:'🐅',k:'tiger stripes cat predator'},
        {c:'🦓',k:'zebra stripes africa'},
        {c:'🦝',k:'raccoon trash bandit'},
        {c:'🦡',k:'badger animal'},
        {c:'🦦',k:'otter water fish'},
        {c:'🦥',k:'sloth slow lazy tree'},
        {c:'🐿️',k:'chipmunk squirrel acorn'},
        {c:'🦔',k:'hedgehog spiky animal'},
        {c:'🐁',k:'mouse rat rodent'},
        {c:'🐀',k:'rat mouse rodent'},
        {c:'🐔',k:'chicken hen farm bird'},
        {c:'🐧',k:'penguin ice antarctic bird'},
        {c:'🐦',k:'bird flying tweet'},
        {c:'🐤',k:'chick baby bird yellow'},
        {c:'🦆',k:'duck quack water bird'},
        {c:'🦅',k:'eagle hawk predator bird'},
        {c:'🦉',k:'owl wise nocturnal bird'},
        {c:'🦇',k:'bat halloween night'},
        {c:'🦃',k:'turkey thanksgiving bird'},
        {c:'🦚',k:'peacock feathers colorful'},
        {c:'🦜',k:'parrot colorful tropical bird'},
        {c:'🦢',k:'swan elegant white bird'},
        {c:'🦩',k:'flamingo pink elegant bird'},
        {c:'🕊️',k:'dove peace white bird'},
        {c:'🐓',k:'rooster cock morning bird'},
        {c:'🐬',k:'dolphin ocean smart mammal'},
        {c:'🐳',k:'whale ocean big splash'},
        {c:'🐋',k:'whale blue ocean'},
        {c:'🦭',k:'seal sea animal'},
        {c:'🦈',k:'shark ocean predator teeth'},
        {c:'🐙',k:'octopus tentacle sea'},
        {c:'🦑',k:'squid tentacle sea ink'},
        {c:'🦐',k:'shrimp seafood prawn'},
        {c:'🦞',k:'lobster seafood red'},
        {c:'🦀',k:'crab seafood red claws'},
        {c:'🐟',k:'fish sea ocean'},
        {c:'🐠',k:'tropical fish colorful ocean'},
        {c:'🐡',k:'blowfish puffer spiky'},
        {c:'🐚',k:'shell spiral beach ocean'},
        {c:'🦋',k:'butterfly wings transform colorful'},
        {c:'🐛',k:'bug worm caterpillar'},
        {c:'🐝',k:'bee honey yellow buzz'},
        {c:'🐞',k:'ladybug insect red spots'},
        {c:'🐜',k:'ant insect small colony'},
        {c:'🦟',k:'mosquito bug insect malaria'},
        {c:'🦗',k:'cricket insect chirp'},
        {c:'🕷️',k:'spider web scary creepy'},
        {c:'🦂',k:'scorpion sting desert'},
        {c:'🐢',k:'turtle shell slow reptile'},
        {c:'🐍',k:'snake reptile slither hiss'},
        {c:'🦎',k:'lizard reptile gecko'},
        {c:'🐊',k:'crocodile alligator reptile'},
        {c:'🌸',k:'cherry blossom pink flower spring japan'},
        {c:'🌺',k:'hibiscus flower tropical red'},
        {c:'🌻',k:'sunflower yellow bright summer'},
        {c:'🌹',k:'rose red flower love'},
        {c:'🌷',k:'tulip pink spring flower'},
        {c:'🌼',k:'blossom white flower daisy'},
        {c:'💐',k:'bouquet flowers bunch gift'},
        {c:'🍀',k:'four leaf clover luck green'},
        {c:'🌿',k:'herb leaf green plant'},
        {c:'☘️',k:'shamrock clover ireland green'},
        {c:'🍃',k:'leaf wind green nature'},
        {c:'🍂',k:'fallen leaf autumn fall orange'},
        {c:'🍁',k:'maple leaf canada red autumn'},
        {c:'🌾',k:'wheat sheaf grain harvest'},
        {c:'🌵',k:'cactus desert prickly'},
        {c:'🎋',k:'tanabata bamboo tree'},
        {c:'🌲',k:'evergreen pine tree forest'},
        {c:'🌳',k:'deciduous tree green forest'},
        {c:'🌴',k:'palm tree beach tropical'},
        {c:'🪴',k:'potted plant indoor green'},
        {c:'🍄',k:'mushroom fungus toadstool'},
        {c:'🪸',k:'coral reef ocean sea'},
        {c:'🪨',k:'rock stone solid'},
        {c:'🌊',k:'wave water ocean sea'},
        {c:'💧',k:'droplet water drop'},
        {c:'💦',k:'splashing water drops sweat'},
        {c:'❄️',k:'snowflake cold winter ice'},
        {c:'☃️',k:'snowman winter cold'},
        {c:'⛄',k:'snowman hat winter'},
        {c:'⭐',k:'star bright night sky'},
        {c:'🌟',k:'glowing star bright shine'},
        {c:'✨',k:'sparkles magic stars shine'},
        {c:'💫',k:'dizzy star spin'},
        {c:'⚡',k:'lightning bolt thunder electric'},
        {c:'☄️',k:'comet meteor space sky'},
        {c:'🔥',k:'fire flame hot burn'},
        {c:'💥',k:'collision explosion boom impact'},
        {c:'🌈',k:'rainbow colors sky'},
        {c:'☀️',k:'sun sunny bright day'},
        {c:'🌤️',k:'sun cloud partly cloudy'},
        {c:'⛅',k:'partly cloudy sun cloud'},
        {c:'☁️',k:'cloud overcast'},
        {c:'🌧️',k:'rain cloud rainy weather'},
        {c:'⛈️',k:'storm thunder lightning rain'},
        {c:'🌩️',k:'lightning storm cloud'},
        {c:'🌨️',k:'snow cloud cold winter'},
        {c:'🌪️',k:'tornado cyclone wind storm'},
        {c:'🌫️',k:'fog mist haze'},
        {c:'🌬️',k:'wind blow air'},
        {c:'🌡️',k:'thermometer temperature hot cold'},
        {c:'🌍',k:'earth globe europe africa'},
        {c:'🌎',k:'earth globe americas'},
        {c:'🌏',k:'earth globe asia'},
        {c:'🌙',k:'crescent moon night'},
        {c:'🌛',k:'first quarter moon face'},
        {c:'🌝',k:'full moon face'},
        {c:'🌕',k:'full moon bright'},
        {c:'🌑',k:'new moon dark'},
        {c:'⭕',k:'circle red large ring'},
        {c:'🍎',k:'apple red fruit'},
        {c:'🍐',k:'pear green fruit'},
        {c:'🍊',k:'orange citrus fruit'},
        {c:'🍋',k:'lemon yellow citrus sour'},
        {c:'🍌',k:'banana yellow fruit'},
        {c:'🍉',k:'watermelon summer fruit red'},
        {c:'🍇',k:'grapes purple fruit wine'},
        {c:'🍓',k:'strawberry red berry fruit'},
        {c:'🫐',k:'blueberry berry fruit blue'},
        {c:'🍒',k:'cherries red fruit pair'},
        {c:'🍑',k:'peach fuzzy orange fruit'},
        {c:'🥭',k:'mango tropical fruit orange'},
        {c:'🍍',k:'pineapple tropical spiky yellow'},
        {c:'🥥',k:'coconut tropical palm'},
        {c:'🥝',k:'kiwi green fruit'},
        {c:'🍅',k:'tomato red vegetable sauce'},
        {c:'🍆',k:'eggplant aubergine purple vegetable'},
        {c:'🥑',k:'avocado green healthy fat'},
        {c:'🌽',k:'corn maize yellow vegetable'},
        {c:'🥕',k:'carrot orange vegetable rabbit'},
        {c:'🧄',k:'garlic white vegetable cooking'},
        {c:'🧅',k:'onion vegetable cooking'},
        {c:'🥔',k:'potato vegetable starchy'},
        {c:'🥦',k:'broccoli vegetable green healthy'},
        {c:'🥬',k:'leafy greens vegetable lettuce'},
        {c:'🥒',k:'cucumber green vegetable'},
        {c:'🌶️',k:'hot pepper chili spicy red'},
        {c:'🫑',k:'bell pepper vegetable'},
        {c:'🥐',k:'croissant french pastry bread'},
        {c:'🥯',k:'bagel bread ring'},
        {c:'🍞',k:'bread loaf bake'},
        {c:'🥖',k:'baguette french bread'},
        {c:'🧀',k:'cheese dairy yellow'},
        {c:'🥚',k:'egg breakfast'},
        {c:'🍳',k:'cooking egg frying pan breakfast'},
        {c:'🧇',k:'waffle breakfast syrup'},
        {c:'🥞',k:'pancakes breakfast stack syrup'},
        {c:'🥓',k:'bacon meat breakfast'},
        {c:'🍔',k:'hamburger burger fast food'},
        {c:'🍟',k:'fries chips fast food'},
        {c:'🌭',k:'hot dog sausage bun'},
        {c:'🌮',k:'taco mexican food'},
        {c:'🌯',k:'burrito wrap mexican'},
        {c:'🍕',k:'pizza cheese italian'},
        {c:'🍜',k:'noodles ramen soup asian'},
        {c:'🍝',k:'spaghetti pasta italian'},
        {c:'🍣',k:'sushi japanese fish rice'},
        {c:'🍱',k:'bento box japanese lunch'},
        {c:'🍛',k:'curry rice indian'},
        {c:'🍚',k:'rice bowl asian'},
        {c:'🍙',k:'rice ball onigiri japanese'},
        {c:'🍘',k:'rice cracker japanese'},
        {c:'🍥',k:'fish cake narutomaki swirl'},
        {c:'🧁',k:'cupcake cake sweet dessert'},
        {c:'🍰',k:'shortcake slice cake dessert'},
        {c:'🎂',k:'birthday cake candle celebration'},
        {c:'🍮',k:'custard dessert pudding'},
        {c:'🍭',k:'lollipop candy sweet'},
        {c:'🍬',k:'candy sweet sugar'},
        {c:'🍫',k:'chocolate bar sweet'},
        {c:'🍿',k:'popcorn movie snack'},
        {c:'🍩',k:'doughnut donut sweet ring'},
        {c:'🍪',k:'cookie sweet biscuit chocolate chip'},
        {c:'🌰',k:'chestnut nut autumn'},
        {c:'🥜',k:'peanut groundnut legume'},
        {c:'🍯',k:'honey jar sweet bee'},
        {c:'☕',k:'hot coffee drink caffeine'},
        {c:'🍵',k:'tea hot drink green'},
        {c:'🫖',k:'teapot pour tea'},
        {c:'🧃',k:'juice box drink'},
        {c:'🥤',k:'cup drink straw soda'},
        {c:'🧋',k:'bubble tea boba drink'},
        {c:'🍺',k:'beer mug drink alcohol'},
        {c:'🍻',k:'beers cheers clink alcohol'},
        {c:'🥂',k:'champagne toast celebrate glasses'},
        {c:'🍷',k:'wine glass red drink'},
        {c:'🥃',k:'whiskey glass drink alcohol'},
        {c:'🍸',k:'cocktail martini drink'},
        {c:'🍹',k:'tropical drink cocktail'},
        {c:'🧉',k:'mate drink herb'},
        {c:'🍾',k:'champagne bottle celebrate'},
        {c:'🧊',k:'ice cube cold frozen'},
        {c:'🚗',k:'car automobile drive red'},
        {c:'🚕',k:'taxi cab yellow drive'},
        {c:'🚙',k:'suv car vehicle'},
        {c:'🚌',k:'bus public transport'},
        {c:'🚎',k:'trolleybus tram'},
        {c:'🏎️',k:'racing car formula sports'},
        {c:'🚓',k:'police car cop law'},
        {c:'🚑',k:'ambulance emergency medical'},
        {c:'🚒',k:'fire truck engine'},
        {c:'✈️',k:'airplane plane flight travel'},
        {c:'🚁',k:'helicopter fly rotor'},
        {c:'🚀',k:'rocket space launch'},
        {c:'🛸',k:'ufo flying saucer alien'},
        {c:'🛳️',k:'cruise ship travel ocean'},
        {c:'⛵',k:'sailboat wind water'},
        {c:'🚢',k:'ship boat ocean'},
        {c:'🚂',k:'locomotive train steam'},
        {c:'🚄',k:'bullet train fast speed'},
        {c:'🚇',k:'metro subway underground'},
        {c:'🚲',k:'bicycle bike ride'},
        {c:'🛴',k:'kick scooter ride'},
        {c:'🛵',k:'motor scooter moped'},
        {c:'🏍️',k:'motorcycle motorbike ride'},
        {c:'🛺',k:'auto rickshaw'},
        {c:'🚶',k:'person walking pedestrian'},
        {c:'🏃',k:'person running race sprint'},
        {c:'🏠',k:'house home residence'},
        {c:'🏡',k:'house garden home yard'},
        {c:'🏢',k:'office building work'},
        {c:'🏥',k:'hospital medical health'},
        {c:'🏦',k:'bank money finance'},
        {c:'🏫',k:'school education building'},
        {c:'🏬',k:'department store shop'},
        {c:'🏭',k:'factory industrial building'},
        {c:'🏯',k:'japanese castle fortress'},
        {c:'🏰',k:'european castle medieval'},
        {c:'⛪',k:'church religion cross building'},
        {c:'🕌',k:'mosque islam prayer'},
        {c:'🕍',k:'synagogue jewish star'},
        {c:'🛕',k:'hindu temple worship'},
        {c:'⛩️',k:'shinto shrine torii japan'},
        {c:'🗼',k:'tokyo tower japan'},
        {c:'🗽',k:'statue liberty new york usa'},
        {c:'🗿',k:'moai easter island statue'},
        {c:'⛺',k:'tent camping outdoor'},
        {c:'🏔️',k:'mountain snow peak'},
        {c:'⛰️',k:'mountain peak landscape'},
        {c:'🌋',k:'volcano eruption lava'},
        {c:'🏕️',k:'camping tent outdoor'},
        {c:'🏖️',k:'beach sun sand ocean'},
        {c:'🏜️',k:'desert sand hot dry'},
        {c:'🏝️',k:'desert island tropical'},
        {c:'💻',k:'laptop computer work tech'},
        {c:'🖥️',k:'desktop computer monitor screen'},
        {c:'🖨️',k:'printer print document'},
        {c:'⌨️',k:'keyboard type computer'},
        {c:'🖱️',k:'mouse computer click'},
        {c:'💾',k:'floppy disk save storage old'},
        {c:'💿',k:'cd dvd disc music'},
        {c:'📱',k:'mobile phone smartphone iphone'},
        {c:'☎️',k:'telephone phone landline old'},
        {c:'📞',k:'telephone receiver call'},
        {c:'📺',k:'tv television screen'},
        {c:'📻',k:'radio broadcast sound'},
        {c:'🎙️',k:'studio microphone record podcast'},
        {c:'📡',k:'satellite dish antenna signal'},
        {c:'🔋',k:'battery power charge'},
        {c:'🪫',k:'low battery empty charge'},
        {c:'🔌',k:'plug power electric'},
        {c:'💡',k:'light bulb idea bright'},
        {c:'🔦',k:'flashlight torch light'},
        {c:'🕯️',k:'candle flame light'},
        {c:'📚',k:'books study reading education library'},
        {c:'📖',k:'open book read study'},
        {c:'📗',k:'green book read study'},
        {c:'📘',k:'blue book read study'},
        {c:'📙',k:'orange book read study'},
        {c:'📕',k:'closed book red read study'},
        {c:'📓',k:'notebook study notes'},
        {c:'📔',k:'notebook decorative cover notes'},
        {c:'📝',k:'memo note write pencil'},
        {c:'✏️',k:'pencil write draw edit'},
        {c:'🖊️',k:'pen write ink'},
        {c:'🖋️',k:'fountain pen write ink'},
        {c:'📌',k:'pushpin location mark'},
        {c:'📍',k:'round pushpin location'},
        {c:'📁',k:'file folder organize'},
        {c:'📂',k:'open folder files'},
        {c:'📋',k:'clipboard checklist task'},
        {c:'📊',k:'bar chart graph statistics data'},
        {c:'📈',k:'chart increasing up trend'},
        {c:'📉',k:'chart decreasing down trend'},
        {c:'🗓️',k:'calendar schedule date plan'},
        {c:'📅',k:'calendar date'},
        {c:'🗂️',k:'card index dividers organize'},
        {c:'🗃️',k:'card file box storage'},
        {c:'🗄️',k:'file cabinet storage organize'},
        {c:'📰',k:'newspaper news article read'},
        {c:'🔬',k:'microscope science biology lab'},
        {c:'🔭',k:'telescope astronomy space star'},
        {c:'🧬',k:'dna genetics biology science'},
        {c:'⚗️',k:'alembic chemistry experiment lab'},
        {c:'🧪',k:'test tube science experiment'},
        {c:'🧫',k:'petri dish science biology'},
        {c:'🧲',k:'magnet attract magnetic'},
        {c:'💊',k:'pill medicine drug health'},
        {c:'💉',k:'syringe injection medicine vaccine'},
        {c:'🩺',k:'stethoscope doctor medical'},
        {c:'🩹',k:'bandage aid hurt injury'},
        {c:'🎵',k:'musical note song melody'},
        {c:'🎶',k:'musical notes song music'},
        {c:'🎼',k:'musical score sheet note'},
        {c:'🎹',k:'piano keyboard music instrument'},
        {c:'🥁',k:'drums percussion beat music'},
        {c:'🎷',k:'saxophone jazz music instrument'},
        {c:'🎺',k:'trumpet brass music instrument'},
        {c:'🎸',k:'guitar rock music electric'},
        {c:'🎻',k:'violin string classical music'},
        {c:'🪗',k:'accordion music instrument'},
        {c:'🎤',k:'microphone sing karaoke voice'},
        {c:'🎧',k:'headphone listen music audio'},
        {c:'🎨',k:'artist palette paint color art'},
        {c:'🖌️',k:'paintbrush art paint create'},
        {c:'🖼️',k:'framed picture art gallery'},
        {c:'🎭',k:'theatre performing arts mask'},
        {c:'🎬',k:'clapper movie film cinema'},
        {c:'📷',k:'camera photo picture'},
        {c:'📸',k:'camera flash photo selfie'},
        {c:'📹',k:'video camera film record'},
        {c:'🎥',k:'movie camera cinema film'},
        {c:'💎',k:'gem diamond jewel precious'},
        {c:'💍',k:'ring engagement wedding diamond'},
        {c:'👑',k:'crown king queen royal'},
        {c:'💄',k:'lipstick makeup beauty red'},
        {c:'👜',k:'handbag purse fashion'},
        {c:'🧳',k:'luggage travel suitcase bag'},
        {c:'💼',k:'briefcase work business professional'},
        {c:'👓',k:'glasses spectacles sight'},
        {c:'🕶️',k:'sunglasses cool dark fashion'},
        {c:'🧢',k:'billed cap hat baseball'},
        {c:'👒',k:'woman hat brim fashion'},
        {c:'🎩',k:'top hat formal magic'},
        {c:'⛑️',k:'rescue helmet safety hard hat'},
        {c:'👟',k:'sneaker shoe running sport'},
        {c:'👠',k:'high heel shoe fashion'},
        {c:'👡',k:'flat shoe sandal'},
        {c:'👢',k:'boot shoe fashion'},
        {c:'🧤',k:'gloves winter hand warm'},
        {c:'🧣',k:'scarf winter neck warm'},
        {c:'🧥',k:'coat jacket warm winter'},
        {c:'👗',k:'dress fashion woman clothing'},
        {c:'👘',k:'kimono japanese traditional clothing'},
        {c:'👙',k:'bikini swimwear beach'},
        {c:'👔',k:'necktie shirt formal business'},
        {c:'👕',k:'t-shirt casual shirt clothing'},
        {c:'👖',k:'jeans denim pants casual'},
        {c:'🔑',k:'key lock unlock door'},
        {c:'🗝️',k:'old key vintage lock'},
        {c:'🔒',k:'locked secure closed padlock'},
        {c:'🔓',k:'unlocked open padlock'},
        {c:'🔨',k:'hammer tool build'},
        {c:'⚒️',k:'hammer pick tool'},
        {c:'🛠️',k:'hammer wrench tool fix'},
        {c:'⚙️',k:'gear settings cog'},
        {c:'🔧',k:'wrench fix tool'},
        {c:'🔩',k:'nut bolt screw'},
        {c:'🪛',k:'screwdriver tool fix'},
        {c:'🗡️',k:'dagger sword knife'},
        {c:'⚔️',k:'swords crossed battle war'},
        {c:'🛡️',k:'shield protect defend'},
        {c:'🔪',k:'knife cutting kitchen'},
        {c:'🪓',k:'axe chop wood'},
        {c:'🪝',k:'hook hang'},
        {c:'🪜',k:'ladder climb steps'},
        {c:'🧰',k:'toolbox tools kit'},
        {c:'🪣',k:'bucket pail water'},
        {c:'🧴',k:'lotion bottle soap'},
        {c:'🧹',k:'broom sweep clean'},
        {c:'🧺',k:'basket wicker laundry'},
        {c:'🧻',k:'roll of paper toilet bathroom'},
        {c:'🪑',k:'chair seat sit furniture'},
        {c:'🛋️',k:'couch sofa relax lounge'},
        {c:'🪞',k:'mirror reflection look'},
        {c:'🚿',k:'shower bath clean water'},
        {c:'🛁',k:'bathtub bath clean relax'},
        {c:'🪠',k:'plunger toilet drain'},
        {c:'🪥',k:'toothbrush clean teeth dental'},
        {c:'🧼',k:'soap clean wash bubble'},
        {c:'🫧',k:'bubbles soap fizz'},
        {c:'🚰',k:'potable water tap faucet drink'},
        {c:'📦',k:'package box delivery cardboard'},
        {c:'🎁',k:'gift present wrapped birthday'},
        {c:'🎀',k:'ribbon bow gift decoration'},
        {c:'🎊',k:'confetti ball party celebrate'},
        {c:'🎉',k:'party popper celebrate'},
        {c:'🎈',k:'balloon party birthday'},
        {c:'🎏',k:'carp streamer wind kite'},
        {c:'🪩',k:'disco mirror ball dance party'},
        {c:'🎯',k:'bullseye target dart aim'},
        {c:'🎲',k:'game die dice board random'},
        {c:'♟️',k:'chess pawn strategy game'},
        {c:'🎮',k:'video game controller play'},
        {c:'🕹️',k:'joystick arcade game old'},
        {c:'🃏',k:'joker playing card wild'},
        {c:'🀄',k:'mahjong tile game'},
        {c:'🎴',k:'flower playing card'},
        {c:'🧩',k:'puzzle piece jigsaw fit'},
        {c:'🪀',k:'yo-yo toy play'},
        {c:'🪁',k:'slingshot toy'},
        {c:'🏆',k:'trophy winner award championship'},
        {c:'🥇',k:'gold medal first winner'},
        {c:'🥈',k:'silver medal second'},
        {c:'🥉',k:'bronze medal third'},
        {c:'🏅',k:'sports medal award'},
        {c:'🎖️',k:'military medal honor'},
        {c:'🎗️',k:'reminder ribbon awareness'},
        {c:'⚽',k:'soccer football sport ball'},
        {c:'🏀',k:'basketball sport ball hoop'},
        {c:'🏈',k:'american football sport'},
        {c:'⚾',k:'baseball sport ball'},
        {c:'🥎',k:'softball sport ball'},
        {c:'🎾',k:'tennis sport ball'},
        {c:'🏐',k:'volleyball sport beach'},
        {c:'🏉',k:'rugby football sport'},
        {c:'🥏',k:'flying disc frisbee sport'},
        {c:'🎱',k:'pool billiard 8ball sport'},
        {c:'🪃',k:'boomerang throw return'},
        {c:'🏓',k:'ping pong table tennis sport'},
        {c:'🏸',k:'badminton sport shuttlecock'},
        {c:'🏒',k:'ice hockey stick sport'},
        {c:'🏑',k:'field hockey stick sport'},
        {c:'🥍',k:'lacrosse stick sport'},
        {c:'🏏',k:'cricket bat sport'},
        {c:'⛳',k:'golf flag hole sport'},
        {c:'🎿',k:'skis snow winter sport'},
        {c:'🛷',k:'sled snow winter toboggan'},
        {c:'🥌',k:'curling stone ice sport'},
        {c:'❤️',k:'red heart love passion'},
        {c:'🧡',k:'orange heart warm love'},
        {c:'💛',k:'yellow heart happy friendship'},
        {c:'💚',k:'green heart nature health'},
        {c:'💙',k:'blue heart calm trust'},
        {c:'💜',k:'purple heart royalty'},
        {c:'🖤',k:'black heart dark gothic'},
        {c:'🤍',k:'white heart pure clean'},
        {c:'🤎',k:'brown heart earth warm'},
        {c:'💔',k:'broken heart sad love end'},
        {c:'❣️',k:'heart exclamation love emphasis'},
        {c:'💕',k:'two hearts love pair'},
        {c:'💞',k:'revolving hearts love spin'},
        {c:'💓',k:'beating heart love pulse'},
        {c:'💗',k:'growing heart love pink'},
        {c:'💖',k:'sparkling heart love shine'},
        {c:'💘',k:'heart arrow cupid love'},
        {c:'💝',k:'heart ribbon gift love'},
        {c:'✅',k:'check mark done complete yes'},
        {c:'❌',k:'cross x no error wrong'},
        {c:'❓',k:'question mark unknown help'},
        {c:'❗',k:'exclamation important alert'},
        {c:'‼️',k:'double exclamation important'},
        {c:'💯',k:'hundred percent perfect score'},
        {c:'🔴',k:'red circle dot stop'},
        {c:'🟠',k:'orange circle dot'},
        {c:'🟡',k:'yellow circle dot'},
        {c:'🟢',k:'green circle dot go'},
        {c:'🔵',k:'blue circle dot'},
        {c:'🟣',k:'purple circle dot'},
        {c:'⚫',k:'black circle dark dot'},
        {c:'⚪',k:'white circle light dot'},
        {c:'🟤',k:'brown circle dot'},
        {c:'🔺',k:'red triangle up'},
        {c:'🔻',k:'red triangle down'},
        {c:'💠',k:'diamond blue shape'},
        {c:'🔷',k:'blue diamond large shape'},
        {c:'🔹',k:'blue diamond small shape'},
        {c:'🔶',k:'orange diamond large shape'},
        {c:'🔸',k:'orange diamond small shape'},
        {c:'🔔',k:'bell ring notification alert'},
        {c:'🔕',k:'bell muted silent no notification'},
        {c:'🔈',k:'speaker low volume sound'},
        {c:'🔉',k:'speaker medium volume'},
        {c:'🔊',k:'speaker loud volume'},
        {c:'📢',k:'loudspeaker announcement public'},
        {c:'📣',k:'megaphone cheer loud announce'},
        {c:'💬',k:'speech bubble message chat talk'},
        {c:'💭',k:'thought bubble think mind'},
        {c:'💤',k:'zzz sleep tired'},
        {c:'♻️',k:'recycle green environment'},
        {c:'⚠️',k:'warning caution alert sign'},
        {c:'🚫',k:'no prohibited stop forbidden'},
        {c:'🚳',k:'no bicycles prohibited'},
        {c:'🚭',k:'no smoking prohibited'},
        {c:'☑️',k:'checked box check done'},
        {c:'🔲',k:'black square frame'},
        {c:'🔳',k:'white square frame'},
        {c:'◾',k:'black medium small square'},
        {c:'◽',k:'white medium small square'},
        {c:'▪️',k:'black small square'},
        {c:'▫️',k:'white small square'},
        {c:'🔼',k:'upward arrow button up'},
        {c:'🔽',k:'downward arrow button down'},
        {c:'⏩',k:'fast forward play speed'},
        {c:'⏪',k:'rewind backward speed'},
        {c:'⏫',k:'fast up arrow'},
        {c:'⏬',k:'fast down arrow'},
        {c:'⏭️',k:'next track forward skip'},
        {c:'⏮️',k:'previous track back skip'},
        {c:'▶️',k:'play button start video'},
        {c:'⏸️',k:'pause button stop wait'},
        {c:'⏹️',k:'stop button end'},
        {c:'⏺️',k:'record button red'},
        {c:'🔁',k:'repeat loop cycle arrows'},
        {c:'🔂',k:'repeat one single loop'},
        {c:'🔀',k:'shuffle random mix'},
        {c:'➕',k:'plus add more increase'},
        {c:'➖',k:'minus subtract less decrease'},
        {c:'✖️',k:'multiply times cross x'},
        {c:'➗',k:'divide split fraction'},
        {c:'🟰',k:'equals equal same'},
        {c:'♾️',k:'infinity endless loop forever'},
        {c:'💲',k:'dollar currency money'},
        {c:'💱',k:'currency exchange money'},
        {c:'©️',k:'copyright reserved'},
        {c:'®️',k:'registered trademark'},
        {c:'™️',k:'trademark brand'},
        {c:'🔠',k:'input latin uppercase letters'},
        {c:'🔡',k:'input latin lowercase letters'},
        {c:'🔢',k:'input numbers digits'},
        {c:'🔣',k:'input symbols signs'},
        {c:'🔤',k:'input latin letters abc'},
        {c:'🅰️',k:'a blood type letter'},
        {c:'🅱️',k:'b blood type letter'},
        {c:'🆎',k:'ab blood type'},
        {c:'🅾️',k:'o blood type letter'},
        {c:'🆑',k:'cl button clear'},
        {c:'🆘',k:'sos emergency help'},
        {c:'🆒',k:'cool button'},
        {c:'🆓',k:'free no cost'},
        {c:'🆕',k:'new fresh'},
        {c:'🆙',k:'up button'},
        {c:'🆚',k:'vs versus battle'},
        {c:'🈁',k:'japanese here koko'},
        {c:'🏁',k:'chequered flag race finish line'},
        {c:'🚩',k:'red flag warning triangular'},
        {c:'🏴',k:'black flag pirate'},
        {c:'🏳️',k:'white flag surrender peace'},
        {c:'🏴‍☠️',k:'pirate flag skull crossbones jolly roger'},
        {c:'🏳️‍🌈',k:'rainbow flag pride lgbtq'},
        {c:'🏳️‍⚧️',k:'trans flag transgender pride'},
        {c:'🇺🇸',k:'united states usa america flag'},
        {c:'🇬🇧',k:'uk united kingdom britain flag'},
        {c:'🇨🇦',k:'canada maple leaf flag'},
        {c:'🇦🇺',k:'australia flag'},
        {c:'🇯🇵',k:'japan japanese flag'},
        {c:'🇨🇳',k:'china chinese flag'},
        {c:'🇩🇪',k:'germany german flag'},
        {c:'🇫🇷',k:'france french flag'},
        {c:'🇪🇸',k:'spain spanish flag'},
        {c:'🇮🇹',k:'italy italian flag'},
        {c:'🇧🇷',k:'brazil flag'},
        {c:'🇮🇳',k:'india flag'},
        {c:'🇷🇺',k:'russia flag'},
        {c:'🇰🇷',k:'south korea flag'},
        {c:'🇲🇽',k:'mexico flag'},
        {c:'🇵🇹',k:'portugal flag'},
        {c:'🇳🇱',k:'netherlands holland flag'},
        {c:'🇸🇪',k:'sweden flag'},
        {c:'🇳🇴',k:'norway flag'},
        {c:'🇩🇰',k:'denmark flag'},
        {c:'🇫🇮',k:'finland flag'},
        {c:'🇵🇱',k:'poland flag'},
        {c:'🇺🇦',k:'ukraine flag'},
        {c:'🇨🇭',k:'switzerland flag'},
        {c:'🇿🇦',k:'south africa flag'},
        {c:'🇦🇷',k:'argentina flag'},
        {c:'🇮🇩',k:'indonesia flag'},
        {c:'🇸🇬',k:'singapore flag'},
        {c:'🇹🇷',k:'turkey flag'},
        {c:'🇳🇿',k:'new zealand flag'},
        {c:'🇬🇷',k:'greece flag'},
        {c:'🇨🇿',k:'czech republic flag'},
        {c:'🇭🇺',k:'hungary flag'},
        {c:'🇷🇴',k:'romania flag'},
        {c:'🇧🇪',k:'belgium flag'},
        {c:'🇦🇹',k:'austria flag'},
        {c:'🇮🇪',k:'ireland flag'},
        {c:'🇸🇰',k:'slovakia flag'},
        {c:'🇭🇷',k:'croatia flag'},
        {c:'🇵🇭',k:'philippines flag'},
        {c:'🇨🇱',k:'chile flag'},
        {c:'🇨🇴',k:'colombia flag'},
        {c:'🇵🇪',k:'peru flag'},
        {c:'🇻🇳',k:'vietnam flag'},
        {c:'🇹🇭',k:'thailand flag'},
        {c:'🇲🇾',k:'malaysia flag'},
        {c:'🇵🇰',k:'pakistan flag'},
        {c:'🇧🇩',k:'bangladesh flag'},
        {c:'🇪🇬',k:'egypt flag'},
        {c:'🇮🇶',k:'iraq flag'},
        {c:'🇮🇷',k:'iran flag'},
        {c:'🇸🇦',k:'saudi arabia flag'},
        {c:'🇦🇪',k:'uae emirates flag'},
        {c:'🇮🇱',k:'israel flag'},
        {c:'🇳🇬',k:'nigeria flag'},
        {c:'🇰🇪',k:'kenya flag'},
        {c:'🇬🇭',k:'ghana flag'},
        {c:'🇪🇹',k:'ethiopia flag'},
        {c:'🇹🇿',k:'tanzania flag'},
        {c:'🇺🇬',k:'uganda flag'},
        {c:'🇨🇺',k:'cuba flag'},
        {c:'🇻🇪',k:'venezuela flag'},
        {c:'🇧🇴',k:'bolivia flag'},
        {c:'🇺🇾',k:'uruguay flag'},
        {c:'🇵🇾',k:'paraguay flag'},
        {c:'🇪🇨',k:'ecuador flag'},
        {c:'🇲🇦',k:'morocco flag'},
        {c:'🇩🇿',k:'algeria flag'},
        {c:'🇹🇳',k:'tunisia flag'},
        {c:'🇱🇾',k:'libya flag'},
        {c:'🇸🇳',k:'senegal flag'},
        {c:'🇨🇮',k:'ivory coast flag'},
        {c:'🇨🇲',k:'cameroon flag'},
        {c:'🇷🇸',k:'serbia flag'},
        {c:'🇧🇬',k:'bulgaria flag'},
        {c:'🇸🇮',k:'slovenia flag'},
        {c:'🇪🇪',k:'estonia flag'},
        {c:'🇱🇻',k:'latvia flag'},
        {c:'🇱🇹',k:'lithuania flag'},
        {c:'🇦🇱',k:'albania flag'},
        {c:'🇧🇦',k:'bosnia flag'},
        {c:'🇲🇰',k:'north macedonia flag'},
        {c:'🇲🇩',k:'moldova flag'},
        {c:'🇬🇪',k:'georgia flag'},
        {c:'🇦🇲',k:'armenia flag'},
        {c:'🇦🇿',k:'azerbaijan flag'},
        {c:'🇰🇿',k:'kazakhstan flag'},
        {c:'🇺🇿',k:'uzbekistan flag'},
        {c:'🇹🇲',k:'turkmenistan flag'},
        {c:'🇲🇳',k:'mongolia flag'},
        {c:'🇳🇵',k:'nepal flag'},
        {c:'🇱🇰',k:'sri lanka flag'},
        {c:'🇲🇲',k:'myanmar flag'},
        {c:'🇰🇭',k:'cambodia flag'},
        {c:'🇱🇦',k:'laos flag'},
        {c:'🇵🇬',k:'papua new guinea flag'},
        {c:'🇫🇯',k:'fiji flag'},
        {c:'🇮🇸',k:'iceland flag'},
        {c:'🇱🇺',k:'luxembourg flag'},
        {c:'🇲🇹',k:'malta flag'},
        {c:'🇨🇾',k:'cyprus flag'},
        {c:'🫠',k:'melting face melt silly hot'},
        {c:'🫣',k:'peeking eye peek shy hide'},
        {c:'🫢',k:'open mouth gasp surprise hands'},
        {c:'🫡',k:'saluting face military respect'},
        {c:'🥹',k:'holding back tears cry moving'},
        {c:'🫤',k:'diagonal mouth neutral unsure'},
        {c:'🫨',k:'shaking face shock'},
        {c:'🤌',k:'italian hand pinched fingers gesture'},
        {c:'🫵',k:'pointing finger you index'},
        {c:'🫴',k:'palm up hand offer receive'},
        {c:'🫳',k:'palm down hand push'},
        {c:'🪷',k:'lotus flower pink water lily'},
        {c:'🪻',k:'hyacinth flower purple'},
        {c:'🪼',k:'jellyfish ocean sea'},
        {c:'🪽',k:'wing bird fly'},
        {c:'🐦‍🔥',k:'phoenix fire bird flame rebirth'},
        {c:'🦫',k:'beaver dam nature'},
        {c:'🐻‍❄️',k:'polar bear white arctic'},
        {c:'🪲',k:'beetle bug insect'},
        {c:'🪳',k:'cockroach bug pest'},
        {c:'🪰',k:'fly insect buzz'},
        {c:'🪱',k:'worm earth ground'},
        {c:'🫏',k:'donkey animal'},
        {c:'🫎',k:'moose elk antlers'},
        {c:'🪬',k:'nazar amulet evil eye protection blue'},
        {c:'🫔',k:'tamale wrap corn food'},
        {c:'🥙',k:'stuffed flatbread pita wrap sandwich'},
        {c:'🥗',k:'green salad healthy vegetable'},
        {c:'🫕',k:'fondue pot hot food'},
        {c:'🥘',k:'shallow pan food paella'},
        {c:'🍲',k:'pot of food stew soup'},
        {c:'🥣',k:'bowl with spoon cereal'},
        {c:'🥫',k:'canned food tin'},
        {c:'🧆',k:'falafel ball chickpea'},
        {c:'🧈',k:'butter dairy'},
        {c:'🥨',k:'pretzel bread twisted'},
        {c:'🫙',k:'jar glass container'},
        {c:'🫚',k:'olive oil bottle cooking'},
        {c:'🫛',k:'pea pod vegetable green'},
        {c:'🍦',k:'soft serve ice cream cone'},
        {c:'🍧',k:'shaved ice dessert cold'},
        {c:'🍨',k:'ice cream bowl dessert'},
        {c:'🍡',k:'dango mochi skewer sweet japanese'},
        {c:'🥟',k:'dumpling gyoza potsticker asian'},
        {c:'🥠',k:'fortune cookie chinese dessert'},
        {c:'🥡',k:'takeout box chinese food'},
        {c:'🦪',k:'oyster shellfish seafood pearl'},
        {c:'🥩',k:'cut of meat steak beef'},
        {c:'🍗',k:'poultry leg chicken drumstick'},
        {c:'🍖',k:'meat bone bbq'},
        {c:'🫗',k:'pouring liquid glass drink'},
        {c:'🥛',k:'glass of milk dairy drink'},
        {c:'🍶',k:'sake bottle cup japanese drink'},
        {c:'🛖',k:'hut house reed cabin'},
        {c:'🛻',k:'pickup truck vehicle'},
        {c:'🚐',k:'minibus van transport'},
        {c:'🛩️',k:'small airplane private jet'},
        {c:'🛫',k:'airplane departure takeoff'},
        {c:'🛬',k:'airplane arrival landing'},
        {c:'⛽',k:'fuel pump gas station'},
        {c:'🛗',k:'elevator lift building'},
        {c:'🚏',k:'bus stop sign transport'},
        {c:'🗺️',k:'world map navigation travel'},
        {c:'🧭',k:'compass navigation direction'},
        {c:'🌄',k:'sunrise mountain dawn'},
        {c:'🌅',k:'sunrise horizon morning'},
        {c:'🌆',k:'cityscape dusk evening'},
        {c:'🌇',k:'sunset city evening'},
        {c:'🌃',k:'night city stars moon'},
        {c:'🌉',k:'bridge night lights'},
        {c:'🏙️',k:'cityscape urban skyscraper'},
        {c:'🎑',k:'moon viewing ceremony japan'},
        {c:'🎆',k:'fireworks celebrate new year'},
        {c:'🎇',k:'sparkler fireworks celebrate'},
        {c:'🗻',k:'mount fuji japan mountain'},
        {c:'🏟️',k:'stadium arena sport venue'},
        {c:'🏛️',k:'classical building column architecture'},
        {c:'🏗️',k:'construction building crane'},
        {c:'🧱',k:'brick wall construction'},
        {c:'🪵',k:'wood log tree lumber'},
        {c:'🏋️',k:'weightlifting gym strong muscle'},
        {c:'🤸',k:'cartwheel gymnastics acrobat'},
        {c:'🤼',k:'wrestling combat sport'},
        {c:'🤺',k:'fencing sword sport'},
        {c:'🤾',k:'handball sport throw'},
        {c:'🏄',k:'surfing wave ocean sport'},
        {c:'🧗',k:'climbing rock wall sport'},
        {c:'🪂',k:'parachute skydiving air'},
        {c:'🏇',k:'horse racing jockey sport'},
        {c:'🤽',k:'water polo swim sport'},
        {c:'🚣',k:'rowing boat water sport'},
        {c:'🧘',k:'yoga meditation lotus calm'},
        {c:'🏊',k:'swimmer swim pool sport'},
        {c:'🤿',k:'diving snorkel mask ocean'},
        {c:'🚵',k:'mountain biking cycle sport'},
        {c:'🚴',k:'cycling bicycle sport'},
        {c:'🏂',k:'snowboarding winter sport board'},
        {c:'⛷️',k:'skiing ski slope winter sport'},
        {c:'🏌️',k:'golf club player sport'},
        {c:'🥊',k:'boxing glove fight sport'},
        {c:'🥋',k:'martial arts gi karate taekwondo'},
        {c:'🥅',k:'goal net sport hockey'},
        {c:'🎣',k:'fishing rod fish sport hobby'},
        {c:'🏹',k:'bow arrow archery aim'},
        {c:'🪕',k:'banjo string music bluegrass'},
        {c:'🪘',k:'long drum music percussion'},
        {c:'🪈',k:'flute pipe music wind instrument'},
        {c:'🔮',k:'crystal ball fortune magic predict'},
        {c:'🧿',k:'nazar amulet evil eye protection'},
        {c:'🧸',k:'teddy bear soft toy cute'},
        {c:'🪆',k:'nesting doll matryoshka russian toy'},
        {c:'🪅',k:'piñata party candy game'},
        {c:'🎠',k:'carousel horse fun ride'},
        {c:'🎡',k:'ferris wheel fun ride fair'},
        {c:'🎢',k:'roller coaster thrill ride'},
        {c:'🎪',k:'circus tent show performance'},
        {c:'🤹',k:'juggling circus performer balls'},
        {c:'🎰',k:'slot machine casino gamble'},
        {c:'🛞',k:'wheel steering vehicle'},
        {c:'🧯',k:'fire extinguisher safety emergency'},
        {c:'🛒',k:'shopping cart trolley buy'},
        {c:'🪤',k:'mouse trap catch'},
        {c:'🛏️',k:'bed sleep rest bedroom'},
        {c:'🪒',k:'razor shave blade'},
        {c:'🧷',k:'safety pin sew clothing fasten'},
        {c:'📫',k:'closed mailbox full letter'},
        {c:'📬',k:'open mailbox flag letter'},
        {c:'📮',k:'postbox mail red letter'},
        {c:'🗳️',k:'ballot box vote election'},
        {c:'✂️',k:'scissors cut craft'},
        {c:'🗑️',k:'wastebasket trash bin delete'},
        {c:'📎',k:'paperclip attach office'},
        {c:'🖇️',k:'linked paperclips attach'},
        {c:'📏',k:'straight ruler measure length'},
        {c:'📐',k:'triangular ruler geometry'},
        {c:'🔎',k:'magnifying glass right search zoom'},
        {c:'🔍',k:'magnifying glass search find'},
        {c:'🩻',k:'x-ray scan medical bone'},
        {c:'🩼',k:'crutch mobility aid'},
        {c:'🩽',k:'sandal shoe'},
        {c:'🩴',k:'thong sandal flip flop shoe'},
        {c:'🪖',k:'military helmet army war'},
        {c:'🪮',k:'hairbrush comb groom'},
        {c:'🪭',k:'folding hand fan cool wind'},
        {c:'☮️',k:'peace sign anti war symbol'},
        {c:'✝️',k:'latin cross christian religion'},
        {c:'☪️',k:'star and crescent islam muslim'},
        {c:'🕉️',k:'om hindu buddhist symbol'},
        {c:'☸️',k:'wheel of dharma buddhism'},
        {c:'✡️',k:'star of david jewish'},
        {c:'🔯',k:'dotted six pointed star jewish'},
        {c:'🕎',k:'menorah jewish candles hanukkah'},
        {c:'☯️',k:'yin yang balance harmony taoist'},
        {c:'☦️',k:'orthodox cross christian'},
        {c:'🛐',k:'place of worship religion pray'},
        {c:'⛎',k:'ophiuchus zodiac star sign'},
        {c:'♈',k:'aries ram zodiac march april'},
        {c:'♉',k:'taurus bull zodiac april may'},
        {c:'♊',k:'gemini twins zodiac may june'},
        {c:'♋',k:'cancer crab zodiac june july'},
        {c:'♌',k:'leo lion zodiac july august'},
        {c:'♍',k:'virgo maiden zodiac august'},
        {c:'♎',k:'libra scales zodiac september'},
        {c:'♏',k:'scorpio scorpion zodiac october'},
        {c:'♐',k:'sagittarius archer zodiac november'},
        {c:'♑',k:'capricorn goat zodiac december'},
        {c:'♒',k:'aquarius water zodiac january'},
        {c:'♓',k:'pisces fish zodiac february'},
        {c:'♠️',k:'spade playing card suit black'},
        {c:'♥️',k:'heart playing card suit red'},
        {c:'♦️',k:'diamond playing card suit red'},
        {c:'♣️',k:'club playing card suit black'},
        {c:'🌐',k:'globe network internet web'},
        {c:'🔗',k:'link chain url web'},
        {c:'🔐',k:'locked key secure closed'},
        {c:'🎌',k:'crossed flags japan celebration'},
        {c:'🗯️',k:'anger speech bubble shout'},
        {c:'🔇',k:'muted speaker no sound silent'},
        {c:'❎',k:'cross x button no false'},
        {c:'🆗',k:'ok button approve agree'},
        {c:'❤️‍🔥',k:'heart on fire burning love passion'},
        {c:'❤️‍🩹',k:'mending heart healing repair love'},
        {c:'💟',k:'heart decoration love symbol'},
        {c:'❤',k:'red heart love'},
        {c:'🫀',k:'anatomical heart organ body'},
        {c:'🫁',k:'lungs organ body breathing'},
        {c:'🧠',k:'brain mind think smart organ'},
        {c:'🦷',k:'tooth dental molar'},
        {c:'🦴',k:'bone skeleton body'},
        {c:'✍️',k:'writing hand pen note sign'},
        {c:'💅',k:'nail polish manicure beauty'},
        {c:'🤳',k:'selfie camera phone picture'},
        {c:'🦵',k:'leg kick knee body'},
        {c:'🦶',k:'foot sole barefoot body'},
        {c:'🦻',k:'ear with hearing aid deaf'},
        {c:'🫦',k:'biting lip nervous flirty'},
        {c:'🌱',k:'seedling sprout grow new plant'},
        {c:'🎍',k:'pine decoration new year bamboo'},
        {c:'🪺',k:'nest egg bird home'},
        {c:'🪹',k:'empty nest bird home'},
        {c:'🐦‍⬛',k:'black bird crow raven'},
        {c:'🪐',k:'ringed planet saturn space'},
        {c:'🌌',k:'milky way galaxy stars space'},
        {c:'🌠',k:'shooting star wish meteor night'},
        {c:'📿',k:'prayer beads necklace rosary religion'},
        {c:'💈',k:'barber pole spiral red white blue'},
        {c:'🪄',k:'magic wand wizard spell'},
        {c:'📽️',k:'film projector movie cinema'},
        {c:'🎞️',k:'film frames movie strip'},
        {c:'🎚️',k:'level slider audio control'},
        {c:'🎛️',k:'control knobs audio mixing'},
        {c:'🪚',k:'carpentry saw wood tool'},
        {c:'🎓',k:'graduation cap learn education school'},
        {c:'⏰',k:'alarm clock wake time morning'},
        {c:'⌛',k:'hourglass time sand wait'},
        {c:'⏳',k:'hourglass not done time flowing'},
        {c:'⏱️',k:'stopwatch timer time sport'},
        {c:'⏲️',k:'timer clock countdown'},
        {c:'🕐',k:'one o clock hour time'},
        {c:'🕑',k:'two o clock hour time'},
        {c:'🕒',k:'three o clock hour time'},
        {c:'🕓',k:'four o clock hour time'},
        {c:'🕔',k:'five o clock hour time'},
        {c:'🕕',k:'six o clock hour time'},
        {c:'📲',k:'mobile phone arrow call receive'},
        {c:'📟',k:'pager beeper message old tech'},
        {c:'📠',k:'fax machine send paper old'},
        {c:'🪔',k:'diya oil lamp light festival'},
        {c:'🔆',k:'bright button sun high'},
        {c:'🔅',k:'dim button low light dark'},
        {c:'🗞️',k:'rolled up newspaper press media'},
        {c:'📜',k:'scroll parchment ancient document'},
        {c:'📄',k:'page document single file'},
        {c:'📃',k:'page with curl document note'},
        {c:'📑',k:'bookmark tabs document pages'},
        {c:'🔖',k:'bookmark save read page'},
        {c:'🏷️',k:'label tag price store'},
        {c:'💰',k:'money bag rich wealthy cash'},
        {c:'💵',k:'dollar banknote money cash green'},
        {c:'💴',k:'yen banknote japan money'},
        {c:'💶',k:'euro banknote europe money'},
        {c:'💷',k:'pound banknote uk money'},
        {c:'💸',k:'money with wings fly spend cash'},
        {c:'💳',k:'credit card bank payment'},
        {c:'🪙',k:'coin money gold metal'},
        {c:'💹',k:'chart yen increasing money'},
        {c:'🧧',k:'red envelope money gift chinese new year'},
        {c:'🎄',k:'christmas tree holiday xmas green'},
        {c:'🎃',k:'jack o lantern halloween pumpkin'},
        {c:'🧨',k:'firecracker red chinese new year'},
        {c:'🎐',k:'wind chime japan decoration'},
        {c:'🦠',k:'microbe bacterium cell germ virus bacteria'},
        {c:'🩸',k:'drop blood medical'},
        {c:'🩶',k:'grey gray heart love'},
        {c:'🩷',k:'pink heart love'},
        {c:'🩵',k:'light blue heart love'},
        {c:'🪯',k:'khanda sikh religion'},
        {c:'🛜',k:'wireless wifi signal internet'},
        {c:'🪿',k:'goose bird animal'},
        {c:'🩰',k:'ballet shoes dance'}
    ];

    // Inject shared CSS once — no hover CSS on cells (handled via JS to avoid WebView repaint flicker)
    function _ensureStyles() {
        if (document.getElementById('onigiri-icon-modal-style')) return;
        var sty = document.createElement('style');
        sty.id = 'onigiri-icon-modal-style';
        sty.textContent = [
            '@keyframes onigiriModalIn{from{opacity:0;transform:scale(0.94) translateY(8px)}to{opacity:1;transform:none}}',
            '#onigiri-mark-submenu{pointer-events:auto;}',
            '.oni-cell{position:relative;width:36px;height:36px;border-radius:8px;border:2px solid transparent;',
            '  display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;',
            '  background:var(--canvas-inset,rgba(255,255,255,0.06));',
            '  box-sizing:border-box;overflow:hidden;}',
            '.oni-cell.oni-selected{border-color:var(--accent-color,#007aff);}',
            '.oni-cell .oni-del{position:absolute;top:2px;right:2px;width:16px;height:16px;border-radius:50%;',
            '  background:rgba(0,0,0,0.6);color:#fff;font-size:11px;display:flex;align-items:center;justify-content:center;',
            '  cursor:pointer;line-height:1;opacity:0;pointer-events:none;}',
            '.oni-emoji-cell{font-size:18px;line-height:1;user-select:none;}',
            '.oni-search{width:100%;box-sizing:border-box;padding:6px 12px;border-radius:9999px;',
            '  border:1px solid var(--border,rgba(255,255,255,0.15));background:var(--canvas-inset,rgba(255,255,255,0.06));',
            '  color:var(--fg,#e0e0e0);font-size:13px;outline:none;margin-bottom:10px;',
            '  font-family:var(--font-main,-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif);}',
            '.oni-search:focus{border-color:var(--accent-color,#007aff);}',
            '.oni-tab-btn{padding:6px 14px;border-radius:8px;border:none !important;cursor:pointer;font-size:13px;font-weight:500;',
            '  outline:none !important;box-shadow:none !important;transform:none !important;transition:background 0.12s,color 0.12s;}',
            '.oni-tab-btn.active{background:var(--canvas-inset,rgba(255,255,255,0.1));color:var(--fg,#e0e0e0);}',
            '.oni-tab-btn:not(.active){background:none;color:var(--fg-subtle,#888);}',
            '.oni-tab-btn:hover,.oni-tab-btn:focus,.oni-tab-btn:active{border:none !important;outline:none !important;',
            '  box-shadow:none !important;transform:none !important;}',
            '.oni-tab-btn:not(.active):hover{color:var(--fg,#e0e0e0);}',
            '.oni-color-row{display:flex;align-items:center;gap:7px;flex-wrap:wrap;}',
            '.oni-color-swatch{width:24px;height:24px;border-radius:50%;cursor:pointer;flex-shrink:0;transition:transform 0.12s ease,box-shadow 0.12s ease;}',
            '.oni-color-swatch:hover{transform:scale(1.12);}',
            '.oni-color-plus{display:flex;align-items:center;justify-content:center;width:24px;height:24px;padding:0;border-radius:50%;border:none !important;outline:none !important;',
            '  background:var(--canvas-inset,rgba(255,255,255,0.08));color:var(--fg-subtle,#888);cursor:pointer;flex-shrink:0;',
            '  transition:background 0.12s ease,color 0.12s ease,transform 0.12s ease;appearance:none;-webkit-appearance:none;box-sizing:border-box;box-shadow:none !important;}',
            '.oni-color-plus:hover,.oni-color-plus.is-active{background:var(--highlight-bg,rgba(128,128,128,0.16));color:var(--fg,#e0e0e0);transform:scale(1.08);}',
            '.oni-color-picker-popover{display:none;position:fixed;width:300px;box-sizing:border-box;padding:12px;border-radius:14px;border:1px solid var(--border,rgba(255,255,255,0.14));',
            '  background:var(--canvas-overlay,#1e1e1e);box-shadow:0 18px 44px rgba(0,0,0,0.38);z-index:200002;}',
            '.oni-color-picker-popover.open{display:block;}',
            '.oni-color-field{position:relative;width:100%;height:128px;border-radius:12px;overflow:hidden;cursor:crosshair;',
            '  box-shadow:inset 0 0 0 1px rgba(255,255,255,0.08);background:#65ff00;}',
            '.oni-color-field-inner{position:absolute;inset:0;border-radius:12px;overflow:hidden;}',
            '.oni-color-field-white,.oni-color-field-black{position:absolute;inset:0;pointer-events:none;}',
            '.oni-color-field-white{background:linear-gradient(to right,#ffffff,rgba(255,255,255,0));}',
            '.oni-color-field-black{background:linear-gradient(to bottom,rgba(0,0,0,0),#000000);}',
            '.oni-color-field-cursor{position:absolute;width:18px;height:18px;border-radius:999px;border:4px solid #fff;box-sizing:border-box;',
            '  box-shadow:0 2px 5px rgba(0,0,0,0.24);transform:translate(-50%,-50%);pointer-events:none;z-index:6;}',
            '.oni-picker-controls{display:flex;align-items:stretch;gap:9px;margin-top:10px;}',
            '.oni-slider-stack{flex:1;display:flex;flex-direction:column;justify-content:center;gap:8px;padding:2px 0;}',
            '.oni-slider-track{position:relative;width:100%;height:10px;border-radius:999px;cursor:pointer;overflow:visible;}',
            '.oni-hue-track{background:linear-gradient(to right,#ff3b30 0%,#ffd60a 16.67%,#32d74b 33.33%,#00c7be 50%,#0a84ff 66.67%,#bf5af2 83.33%,#ff375f 100%);}',
            '.oni-alpha-track{background-color:#d6dbcf;background-image:',
            '  linear-gradient(45deg,rgba(255,255,255,0.58) 25%,transparent 25%,transparent 75%,rgba(255,255,255,0.58) 75%,rgba(255,255,255,0.58)),',
            '  linear-gradient(45deg,transparent 25%,rgba(0,0,0,0.05) 25%,rgba(0,0,0,0.05) 50%,transparent 50%,transparent 75%,rgba(0,0,0,0.05) 75%,rgba(0,0,0,0.05));',
            '  background-position:0 0,3px 3px;background-size:6px 6px;}',
            '.oni-alpha-gradient{position:absolute;inset:0;border-radius:inherit;overflow:hidden;}',
            '.oni-slider-thumb{position:absolute;top:50%;width:16px;height:16px;border-radius:999px;background:#fff;',
            '  border:2px solid rgba(255,255,255,0.98);box-shadow:0 2px 6px rgba(0,0,0,0.22);transform:translate(-50%,-50%);pointer-events:none;}',
            '.oni-dropper-btn{width:48px;min-width:48px;border:none !important;outline:none !important;border-radius:12px;background:rgba(255,255,255,0.08);color:var(--fg,#e0e0e0);',
            '  display:flex;align-items:center;justify-content:center;cursor:pointer;transition:background 0.12s ease,transform 0.12s ease;appearance:none;-webkit-appearance:none;box-sizing:border-box;box-shadow:none !important;}',
            '.oni-dropper-btn:hover{background:rgba(255,255,255,0.12);transform:translateY(-1px);}',
            '.oni-picker-inputs{display:flex;gap:5px;margin-top:10px;}',
            '.oni-picker-surface{display:flex;align-items:center;min-width:0;height:38px;padding:0 8px;border-radius:10px;',
            '  border:1px solid var(--border,rgba(255,255,255,0.14));background:rgba(255,255,255,0.08);box-sizing:border-box;}',
            '.oni-picker-hex{flex:1 1 auto;}',
            '.oni-picker-alpha{width:62px;justify-content:center;padding:0 6px;}',
            '.oni-picker-format{width:60px;justify-content:space-between;cursor:pointer;color:var(--fg,#e0e0e0);padding:0 6px;}',
            '.oni-picker-input{width:100%;min-width:0;background:transparent;border:none;outline:none;color:var(--fg,#e0e0e0);font-size:13px;font-weight:600;',
            '  font-family:Consolas,"Courier New",monospace;padding:0;margin:0;}',
            '.oni-picker-input::placeholder{color:var(--fg-subtle,#888);}',
            '.oni-picker-input.percent{text-align:center;font-family:var(--font-main,-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif);}',
            '.oni-picker-format-label{font-size:13px;font-weight:600;color:var(--fg,#e0e0e0);}',
            '#onigiri-icon-backdrop button{border:none !important;outline:none !important;box-shadow:none !important;appearance:none;-webkit-appearance:none;}',
            '.oni-upload-btn{display:flex;align-items:center;gap:6px;padding:7px 13px;border-radius:8px;border:none !important;',
            '  background:#353535;color:var(--fg-subtle,#888);font-size:13px;',
            '  cursor:pointer;outline:none !important;box-shadow:none !important;transition:background 0.12s,color 0.12s;}',
            '.oni-upload-btn:hover{background:#454545;color:var(--fg,#e0e0e0);}',
        ].join('');
        document.head.appendChild(sty);
    }

    function _bindCellHover(cell, delEl) {
        cell.addEventListener('mouseenter', function () {
            cell.style.background = 'var(--highlight-bg,rgba(128,128,128,0.12))';
            // Don't override the accent border when the cell is already selected
            if (!cell.classList.contains('oni-selected')) {
                cell.style.borderColor = 'var(--border,rgba(255,255,255,0.15))';
            }
            if (delEl) { delEl.style.opacity = '1'; delEl.style.pointerEvents = 'auto'; }
        });
        cell.addEventListener('mouseleave', function () {
            cell.style.background = '';
            if (!cell.classList.contains('oni-selected')) cell.style.borderColor = '';
            if (delEl) { delEl.style.opacity = '0'; delEl.style.pointerEvents = 'none'; }
        });
    }

    function _makeGrid() {
        var g = document.createElement('div');
        g.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(36px,1fr));gap:4px;';
        return g;
    }

    function _makeSearch(placeholder, onInput) {
        var inp = document.createElement('input');
        inp.className = 'oni-search';
        inp.placeholder = placeholder;
        inp.autocomplete = 'off';
        inp.spellcheck = false;
        inp.addEventListener('input', function () { onInput(inp.value.trim().toLowerCase()); });
        return inp;
    }

    function _clampByte(value) {
        return Math.max(0, Math.min(255, Math.round(value)));
    }

    function _hexByte(value) {
        var hex = _clampByte(value).toString(16).toUpperCase();
        return hex.length === 1 ? '0' + hex : hex;
    }

    function _rgbaToHex(r, g, b, a) {
        var base = '#' + _hexByte(r) + _hexByte(g) + _hexByte(b);
        var alpha = typeof a === 'number' ? _clampByte(a) : 255;
        return alpha < 255 ? base + _hexByte(alpha) : base;
    }

    function _parseColor(value) {
        if (typeof value !== 'string') return null;
        var text = value.trim();
        if (!text) return null;

        var hexMatch = text.match(/^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/);
        if (hexMatch) {
            var digits = hexMatch[1];
            if (digits.length === 3 || digits.length === 4) {
                digits = digits.split('').map(function (ch) { return ch + ch; }).join('');
            }
            if (digits.length === 6) {
                return {
                    r: parseInt(digits.slice(0, 2), 16),
                    g: parseInt(digits.slice(2, 4), 16),
                    b: parseInt(digits.slice(4, 6), 16),
                    a: 255
                };
            }
            return {
                r: parseInt(digits.slice(0, 2), 16),
                g: parseInt(digits.slice(2, 4), 16),
                b: parseInt(digits.slice(4, 6), 16),
                a: parseInt(digits.slice(6, 8), 16)
            };
        }

        var rgbaMatch = text.match(/^rgba?\((.+)\)$/i);
        if (rgbaMatch) {
            var parts = rgbaMatch[1].split(',').map(function (part) { return part.trim(); });
            if (parts.length === 3 || parts.length === 4) {
                var r = parseFloat(parts[0]);
                var g = parseFloat(parts[1]);
                var b = parseFloat(parts[2]);
                if (!isNaN(r) && !isNaN(g) && !isNaN(b)) {
                    var alpha = 255;
                    if (parts.length === 4) {
                        var alphaValue = parseFloat(parts[3]);
                        if (!isNaN(alphaValue)) {
                            alpha = alphaValue <= 1 ? _clampByte(alphaValue * 255) : _clampByte(alphaValue);
                        }
                    }
                    return { r: _clampByte(r), g: _clampByte(g), b: _clampByte(b), a: alpha };
                }
            }
        }

        var hslaMatch = text.match(/^hsla?\((.+)\)$/i);
        if (hslaMatch) {
            var hslaParts = hslaMatch[1].split(',').map(function (part) { return part.trim(); });
            if (hslaParts.length === 3 || hslaParts.length === 4) {
                var h = parseFloat(hslaParts[0]);
                var sText = hslaParts[1].replace('%', '');
                var lText = hslaParts[2].replace('%', '');
                var sVal = parseFloat(sText);
                var lVal = parseFloat(lText);
                if (!isNaN(h) && !isNaN(sVal) && !isNaN(lVal)) {
                    var hue = ((h % 360) + 360) % 360;
                    var sat = Math.max(0, Math.min(100, sVal)) / 100;
                    var light = Math.max(0, Math.min(100, lVal)) / 100;
                    var c = (1 - Math.abs(2 * light - 1)) * sat;
                    var x = c * (1 - Math.abs((hue / 60) % 2 - 1));
                    var m = light - c / 2;
                    var r1 = 0, g1 = 0, b1 = 0;
                    if (hue < 60) { r1 = c; g1 = x; b1 = 0; }
                    else if (hue < 120) { r1 = x; g1 = c; b1 = 0; }
                    else if (hue < 180) { r1 = 0; g1 = c; b1 = x; }
                    else if (hue < 240) { r1 = 0; g1 = x; b1 = c; }
                    else if (hue < 300) { r1 = x; g1 = 0; b1 = c; }
                    else { r1 = c; g1 = 0; b1 = x; }

                    var alphaHsl = 255;
                    if (hslaParts.length === 4) {
                        var alphaText = parseFloat(hslaParts[3].replace('%', ''));
                        if (!isNaN(alphaText)) {
                            alphaHsl = hslaParts[3].indexOf('%') !== -1
                                ? _clampByte((alphaText / 100) * 255)
                                : (alphaText <= 1 ? _clampByte(alphaText * 255) : _clampByte(alphaText));
                        }
                    }

                    return {
                        r: _clampByte((r1 + m) * 255),
                        g: _clampByte((g1 + m) * 255),
                        b: _clampByte((b1 + m) * 255),
                        a: alphaHsl
                    };
                }
            }
        }

        return null;
    }

    function _normalizeColor(value, fallback) {
        var parsed = _parseColor(value);
        if (parsed) return _rgbaToHex(parsed.r, parsed.g, parsed.b, parsed.a);
        if (fallback) return _normalizeColor(fallback);
        return null;
    }

    function _colorToCss(value) {
        var parsed = typeof value === 'string' ? _parseColor(value) : value;
        if (!parsed) return '#888888';
        if (parsed.a >= 255) return _rgbaToHex(parsed.r, parsed.g, parsed.b, 255);
        var alpha = (parsed.a / 255).toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
        if (!alpha) alpha = '0';
        return 'rgba(' + parsed.r + ', ' + parsed.g + ', ' + parsed.b + ', ' + alpha + ')';
    }

    function _sameBaseColor(first, second) {
        var a = _parseColor(first);
        var b = _parseColor(second);
        return !!(a && b && a.r === b.r && a.g === b.g && a.b === b.b);
    }

    function _hsvToHex(h, s, v, a) {
        var hue = ((typeof h === 'number' ? h : 0) % 360 + 360) % 360;
        var sat = Math.max(0, Math.min(100, typeof s === 'number' ? s : 0)) / 100;
        var val = Math.max(0, Math.min(100, typeof v === 'number' ? v : 0)) / 100;
        var chroma = val * sat;
        var section = hue / 60;
        var x = chroma * (1 - Math.abs(section % 2 - 1));
        var match = val - chroma;
        var r = 0;
        var g = 0;
        var b = 0;

        if (section >= 0 && section < 1) {
            r = chroma; g = x; b = 0;
        } else if (section < 2) {
            r = x; g = chroma; b = 0;
        } else if (section < 3) {
            r = 0; g = chroma; b = x;
        } else if (section < 4) {
            r = 0; g = x; b = chroma;
        } else if (section < 5) {
            r = x; g = 0; b = chroma;
        } else {
            r = chroma; g = 0; b = x;
        }

        return _rgbaToHex(
            (r + match) * 255,
            (g + match) * 255,
            (b + match) * 255,
            typeof a === 'number' ? a : 255
        );
    }

    function _rgbToHsv(color) {
        var r = color.r / 255;
        var g = color.g / 255;
        var b = color.b / 255;
        var max = Math.max(r, g, b);
        var min = Math.min(r, g, b);
        var delta = max - min;
        var hue = 0;

        if (delta !== 0) {
            if (max === r) hue = 60 * (((g - b) / delta) % 6);
            else if (max === g) hue = 60 * (((b - r) / delta) + 2);
            else hue = 60 * (((r - g) / delta) + 4);
        }
        if (hue < 0) hue += 360;

        return {
            h: Math.round(hue),
            s: Math.round(max === 0 ? 0 : (delta / max) * 100),
            v: Math.round(max * 100),
            a: Math.round((color.a / 255) * 100)
        };
    }

    function _rgbToHsl(color) {
        var r = color.r / 255;
        var g = color.g / 255;
        var b = color.b / 255;
        var max = Math.max(r, g, b);
        var min = Math.min(r, g, b);
        var delta = max - min;
        var l = (max + min) / 2;
        var h = 0;
        var s = 0;

        if (delta !== 0) {
            s = delta / (1 - Math.abs(2 * l - 1));
            if (max === r) h = 60 * (((g - b) / delta) % 6);
            else if (max === g) h = 60 * (((b - r) / delta) + 2);
            else h = 60 * (((r - g) / delta) + 4);
        }
        if (h < 0) h += 360;

        return {
            h: Math.round(h),
            s: Math.round(s * 100),
            l: Math.round(l * 100)
        };
    }

    function _alphaToFloatString(alphaByte) {
        var alpha = Math.max(0, Math.min(255, alphaByte || 0)) / 255;
        return alpha.toFixed(3).replace(/0+$/, '').replace(/\.$/, '') || '0';
    }

    function _colorToFormatText(color, format) {
        var parsed = typeof color === 'string' ? _parseColor(color) : color;
        if (!parsed) return '';
        var fmt = String(format || 'HEX').toUpperCase();
        if (fmt === 'RGB') {
            if (parsed.a < 255) {
                return 'rgba(' + parsed.r + ', ' + parsed.g + ', ' + parsed.b + ', ' + _alphaToFloatString(parsed.a) + ')';
            }
            return 'rgb(' + parsed.r + ', ' + parsed.g + ', ' + parsed.b + ')';
        }
        if (fmt === 'HSL') {
            var hsl = _rgbToHsl(parsed);
            if (parsed.a < 255) {
                return 'hsla(' + hsl.h + ', ' + hsl.s + '%, ' + hsl.l + '%, ' + _alphaToFloatString(parsed.a) + ')';
            }
            return 'hsl(' + hsl.h + ', ' + hsl.s + '%, ' + hsl.l + '%)';
        }
        return _rgbaToHex(parsed.r, parsed.g, parsed.b, parsed.a);
    }

    function _closeColorPicker(state) {
        if (!state || !state._pickerRefs || !state._pickerRefs.popover) return;
        state._pickerOpen = false;
        state._pickerRefs.popover.classList.remove('open');
        if (state._pickerRefs.plusButton) state._pickerRefs.plusButton.classList.remove('is-active');
    }

    function _openColorPicker(state) {
        if (!state || !state._pickerRefs || !state._pickerRefs.popover) return;
        state._pickerOpen = true;
        state._pickerRefs.popover.classList.add('open');
        if (state._pickerRefs.plusButton) state._pickerRefs.plusButton.classList.add('is-active');
        _positionColorPicker(state);
        _updateColorPreview(state);
    }

    function _toggleColorPicker(state) {
        if (state && state._pickerOpen) _closeColorPicker(state);
        else _openColorPicker(state);
    }

    function _positionColorPicker(state) {
        var refs = state && state._pickerRefs;
        if (!refs || !refs.popover || !refs.plusButton) return;

        var anchor = refs.plusButton.getBoundingClientRect();
        var popover = refs.popover;
        var margin = 12;
        var width = popover.offsetWidth || 300;
        var height = popover.offsetHeight || 270;
        var left = anchor.left;
        var top = anchor.top - height - 10;

        if (left + width > window.innerWidth - margin) left = window.innerWidth - width - margin;
        if (left < margin) left = margin;
        if (top < margin) top = anchor.bottom + 10;
        if (top + height > window.innerHeight - margin) top = window.innerHeight - height - margin;

        popover.style.left = Math.round(left) + 'px';
        popover.style.top = Math.round(top) + 'px';
    }

    function _positionFieldCursor(refs, satPercent, valPercent) {
        if (!refs || !refs.field || !refs.fieldCursor) return;
        var rect = refs.field.getBoundingClientRect();
        var width = Math.max(1, rect.width);
        var height = Math.max(1, rect.height);
        var knobRadius = 9;
        var x = (Math.max(0, Math.min(100, satPercent)) / 100) * width;
        var y = ((100 - Math.max(0, Math.min(100, valPercent))) / 100) * height;
        x = Math.max(knobRadius, Math.min(width - knobRadius, x));
        y = Math.max(knobRadius, Math.min(height - knobRadius, y));
        refs.fieldCursor.style.left = x + 'px';
        refs.fieldCursor.style.top = y + 'px';
    }

    function _bindPickerDrag(state, element, updateFn) {
        if (!element) return;
        element.addEventListener('pointerdown', function (evt) {
            evt.preventDefault();
            evt.stopPropagation();
            state._pickerDragging = true;
            if (element.setPointerCapture) {
                try { element.setPointerCapture(evt.pointerId); } catch (_) {}
            }

            function apply(event) {
                event.preventDefault();
                event.stopPropagation();
                updateFn(event);
            }

            function finish(event) {
                if (event && typeof event.preventDefault === 'function') {
                    event.preventDefault();
                    event.stopPropagation();
                }
                element.removeEventListener('pointermove', apply);
                element.removeEventListener('pointerup', finish);
                element.removeEventListener('pointercancel', finish);
                state._pickerDragging = false;
                state._pickerSuppressOutsideUntil = Date.now() + 140;
                if (element.releasePointerCapture) {
                    try { element.releasePointerCapture(evt.pointerId); } catch (_) {}
                }
            }

            apply(evt);
            element.addEventListener('pointermove', apply);
            element.addEventListener('pointerup', finish);
            element.addEventListener('pointercancel', finish);
        });
        element.addEventListener('click', function (evt) {
            evt.stopPropagation();
        });
    }

    function _setSelectedColor(state, nextColor) {
        state.colorWasModified = true;
        state.selectedColor = _normalizeColor(nextColor, state.selectedColor || '#888888') || '#888888';
        _updateColorPreview(state);
        pycmd('update_color:' + state.selectedColor);
    }

    function _buildEmojiPane(state) {
        var pane = document.createElement('div');
        pane.id = 'onigiri-tab-pane-emojis';
        pane.style.cssText = 'display:none;flex-direction:column;';

        var grid = _makeGrid();
        // Scrollable wrapper so the grid can scroll while the search bar stays fixed
        var scrollWrap = document.createElement('div');
        scrollWrap.style.cssText = 'flex:1;overflow-y:auto;min-height:0;';
        scrollWrap.appendChild(grid);

        var _emojiItems  = [];   // current filtered list
        var _renderIndex = 0;    // how many have been rendered so far
        var BATCH = 200;         // cells per batch

        function _appendBatch() {
            var end = Math.min(_renderIndex + BATCH, _emojiItems.length);
            for (var i = _renderIndex; i < end; i++) {
                var em = _emojiItems[i].c;
                var cell = document.createElement('div');
                cell.className = 'oni-cell' + (state.selectedIcon === 'emoji:' + em ? ' oni-selected' : '');
                cell.dataset.iconName = 'emoji:' + em;
                var span = document.createElement('span');
                span.className = 'oni-emoji-cell';
                span.textContent = em;
                cell.appendChild(span);
                (function(emChar) {
                    cell.addEventListener('click', function () {
                        _selectIcon('emoji:' + emChar, state);
                    });
                })(em);
                _bindCellHover(cell, null);
                grid.appendChild(cell);
            }
            _renderIndex = end;
        }

        function _renderEmojis(filter) {
            grid.innerHTML = '';
            _renderIndex = 0;
            _emojiItems = filter
                ? EMOJI_DATA.filter(function (e) { return e.k && e.k.indexOf(filter) !== -1; })
                : EMOJI_DATA;
            if (_emojiItems.length === 0 && filter) {
                var msg = document.createElement('div');
                msg.style.cssText = 'color:var(--fg-subtle,#888);font-size:13px;padding:20px 8px;grid-column:1/-1;width:100%;text-align:center;box-sizing:border-box;';
                msg.textContent = 'No emojis match "' + filter + '"';
                grid.appendChild(msg);
                return;
            }
            _appendBatch();
        }

        // Load more when the user scrolls near the bottom
        scrollWrap.addEventListener('scroll', function () {
            if (_renderIndex >= _emojiItems.length) return;
            var remaining = scrollWrap.scrollHeight - scrollWrap.scrollTop - scrollWrap.clientHeight;
            if (remaining < 120) _appendBatch();
        }, { passive: true });

        var search = _makeSearch('Search emojis…', _renderEmojis);
        pane.appendChild(search);
        pane.appendChild(scrollWrap);
        _renderEmojis('');
        return pane;
    }

    function _buildIconsPane(state, data) {
        var pane = document.createElement('div');
        pane.id = 'onigiri-tab-pane-icons';
        pane.style.cssText = 'display:none;flex-direction:column;';

        var grid = _makeGrid();
        grid.id = 'onigiri-icon-grid-icons';

        function _renderIcons(filter) {
            grid.innerHTML = '';
            var items = (data.icons || []).filter(function (it) {
                return !filter || it.name.toLowerCase().indexOf(filter) !== -1;
            });
            if (items.length === 0) {
                var empty = document.createElement('div');
                empty.style.cssText = 'color:var(--fg-subtle,#888);font-size:13px;padding:20px 8px;grid-column:1/-1;width:100%;text-align:center;box-sizing:border-box;';
                empty.textContent = filter ? 'No icons match "' + filter + '"' : 'No icons yet. Upload some in the Upload tab.';
                grid.appendChild(empty);
                return;
            }
            items.forEach(function (item) {
                var cell = document.createElement('div');
                cell.className = 'oni-cell' + (state.selectedIcon === item.name ? ' oni-selected' : '');
                cell.dataset.iconName = item.name;
                var icon = document.createElement('div');
                icon.style.cssText = 'width:30px;height:30px;mask-image:url("' + item.url + '");-webkit-mask-image:url("' + item.url + '");mask-size:contain;-webkit-mask-size:contain;mask-repeat:no-repeat;-webkit-mask-repeat:no-repeat;mask-position:center;-webkit-mask-position:center;background-color:' + _colorToCss(state.selectedColor || '#888888') + ';';
                icon.className = 'oni-icon-img';
                cell.appendChild(icon);
                var del = document.createElement('div');
                del.className = 'oni-del';
                del.textContent = '×';
                del.addEventListener('click', function (e) {
                    e.stopPropagation();
                    pycmd('onigiri_icon_chooser_delete_icon:' + state.deckId + ':' + item.name);
                });
                cell.appendChild(del);
                cell.addEventListener('click', function () { _selectIcon(item.name, state); });
                _bindCellHover(cell, del);
                grid.appendChild(cell);
            });
        }

        var searchRow = document.createElement('div');
        searchRow.style.cssText = 'display:flex;align-items:center;gap:6px;margin-bottom:10px;';
        var search = _makeSearch('Search icons…', _renderIcons);
        search.style.marginBottom = '0';
        search.style.flex = '1';
        searchRow.appendChild(search);
        var uploadBtn = document.createElement('button');
        uploadBtn.className = 'oni-upload-btn';
        uploadBtn.title = 'Upload SVG or PNG icon';
        uploadBtn.appendChild(OnigiriEngine.createMaskIcon(OnigiriEngine.systemIconUrl('add.svg'), {
            className: 'oni-upload-icon',
            size: 14,
            color: 'currentColor'
        }));
        uploadBtn.addEventListener('click', function () { pycmd('onigiri_icon_chooser_add_icon:' + state.deckId); });
        searchRow.appendChild(uploadBtn);
        pane.appendChild(searchRow);
        pane.appendChild(grid);
        _renderIcons('');
        return pane;
    }

    function _buildUploadPane(state) {
        var pane = document.createElement('div');
        pane.id = 'onigiri-tab-pane-upload';
        pane.style.cssText = 'display:none;flex-direction:column;gap:10px;padding:10px 0;';

        function _makeUploadBtn(label, cmd) {
            var btn = document.createElement('button');
            btn.textContent = label;
            btn.style.cssText = 'padding:14px 20px;border-radius:10px;border:1.5px dashed var(--border,rgba(255,255,255,0.2));background:none;color:var(--fg,#e0e0e0);font-size:14px;cursor:pointer;transition:border-color 0.15s,color 0.15s;text-align:left;outline:none !important;box-shadow:none !important;transform:none;';
            btn.addEventListener('mouseenter', function () { btn.style.borderColor = 'var(--accent-color,#007aff)'; btn.style.color = 'var(--accent-color,#007aff)'; });
            btn.addEventListener('mouseleave', function () { btn.style.borderColor = ''; btn.style.color = ''; });
            btn.addEventListener('click', function () { pycmd(cmd + ':' + state.deckId); });
            return btn;
        }

        pane.appendChild(_makeUploadBtn('＋  Upload SVG Icon', 'onigiri_icon_chooser_add_icon'));
        pane.appendChild(_makeUploadBtn('＋  Upload PNG Image', 'onigiri_icon_chooser_add_image'));
        return pane;
    }

    function _selectIcon(name, state) {
        // Deselect old cell
        var old = document.querySelector('.oni-cell.oni-selected');
        if (old) old.classList.remove('oni-selected');
        // Select new cell and clear any inline border-color set by hover so CSS class takes over
        var newCell = document.querySelector('.oni-cell[data-icon-name="' + CSS.escape(name) + '"]');
        if (newCell) {
            newCell.classList.add('oni-selected');
            newCell.style.removeProperty('border-color');
        }
        state.selectedIcon = name;
        _updateColorPreview(state);
    }

    function _updateColorPreview(state) {
        var normalized = _normalizeColor(state.selectedColor, '#888888') || '#888888';
        state.selectedColor = normalized;
        var cssColor = _colorToCss(normalized);
        document.querySelectorAll('#onigiri-icon-grid-icons .oni-icon-img').forEach(function (el) {
            el.style.backgroundColor = cssColor;
        });
        var parsed = _parseColor(normalized);
        if (!parsed) return;

        var hsv = _rgbToHsv(parsed);
        if (hsv.s === 0 && state._pickerModel && typeof state._pickerModel.h === 'number') {
            hsv.h = state._pickerModel.h;
        }
        state._pickerModel = hsv;

        if (state._pickerRefs) {
            var refs = state._pickerRefs;
            if (refs.hexInput && refs.hexInput !== document.activeElement) {
                refs.hexInput.value = _colorToFormatText(parsed, state._pickerFormat || 'HEX');
            }
            if (refs.alphaInput && refs.alphaInput !== document.activeElement) refs.alphaInput.value = hsv.a + '%';
            if (refs.formatLabel) refs.formatLabel.textContent = state._pickerFormat || 'HEX';
            if (refs.field) refs.field.style.background = _hsvToHex(hsv.h, 100, 100, 255);
            _positionFieldCursor(refs, hsv.s, hsv.v);
            if (refs.hueThumb) refs.hueThumb.style.left = (hsv.h / 360) * 100 + '%';
            if (refs.alphaThumb) refs.alphaThumb.style.left = hsv.a + '%';
            if (refs.alphaGradient) {
                refs.alphaGradient.style.background =
                    'linear-gradient(to right, rgba(' + parsed.r + ', ' + parsed.g + ', ' + parsed.b + ', 0), rgba(' +
                    parsed.r + ', ' + parsed.g + ', ' + parsed.b + ', 1))';
            }
        }
    }

    function _buildModal(data) {
        _ensureStyles();
        _state = {
            deckId:        data.deckId,
            selectedIcon:  data.current && data.current.icon  ? data.current.icon  : '',
            selectedColor: _normalizeColor(data.current && data.current.color ? data.current.color : '#888888', '#888888') || '#888888',
            colorWasModified: !!(data.current && data.current.color),
            data:          data,
            _pickerFormat: 'HEX',
            _cleanupFns:   [],
            _pickerOpen:   false,
            _pickerDragging: false,
            _pickerSuppressOutsideUntil: 0,
        };
        var state = _state;

        // Backdrop
        var bd = document.createElement('div');
        bd.id = 'onigiri-icon-backdrop';
        _css(bd, 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:200000;display:flex;align-items:center;justify-content:center;');

        // Modal
        var modal = document.createElement('div');
        _css(modal, 'background:var(--canvas-overlay,#1e1e1e);border:1px solid var(--border,rgba(255,255,255,0.1));border-radius:16px;width:500px;max-width:94vw;height:580px;max-height:88vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 24px 64px rgba(0,0,0,0.45);animation:onigiriModalIn 0.22s cubic-bezier(0.16,1,0.3,1) both;will-change:transform;backface-visibility:hidden;-webkit-backface-visibility:hidden;');
        modal.addEventListener('click', function (e) { e.stopPropagation(); });
        modal.addEventListener('pointerdown', function (e) { e.stopPropagation(); });

        // Header
        var header = document.createElement('div');
        _css(header, 'display:flex;align-items:center;justify-content:space-between;padding:16px 18px 12px;flex-shrink:0;');
        var titleEl = document.createElement('span');
        titleEl.textContent = 'Edit Icon';
        _css(titleEl, 'font-weight:600;font-size:15px;color:var(--fg,#e0e0e0);');
        var closeBtn = document.createElement('button');
        _css(closeBtn, 'background:none;border:none;cursor:pointer;color:var(--fg-subtle,#888);font-size:20px;line-height:1;padding:2px 4px;border-radius:6px;');
        closeBtn.textContent = '×';
        closeBtn.addEventListener('click', _close);
        header.appendChild(titleEl);
        header.appendChild(closeBtn);
        modal.appendChild(header);

        // Tab bar
        var tabDefs = [
            { id: 'emojis', label: 'Emojis' },
            { id: 'icons',  label: 'Icons'  },
        ];
        var activeTab = state.selectedIcon.startsWith('emoji:') ? 'emojis' : ((data.icons && data.icons.length) ? 'icons' : 'emojis');

        var tabBar = document.createElement('div');
        _css(tabBar, 'display:flex;gap:2px;padding:10px 18px 0;flex-shrink:0;');

        function _setTab(tabId) {
            activeTab = tabId;
            var colorSec = document.getElementById('onigiri-icon-color-section');
            if (colorSec) colorSec.style.display = (tabId === 'icons') ? '' : 'none';
            if (tabId !== 'icons') _closeColorPicker(state);
            tabDefs.forEach(function (t) {
                var btn = document.getElementById('oni-tab-btn-' + t.id);
                var pane = document.getElementById('onigiri-tab-pane-' + t.id);
                if (!btn || !pane) return;
                if (t.id === tabId) {
                    btn.classList.add('active');
                    // flex:1 + min-height:0 makes the pane fill the body div so that
                    // scrollWrap (flex:1 inside the pane) is height-bounded and the
                    // scroll event fires correctly for lazy-loading more emojis.
                    pane.style.cssText = 'display:flex;flex-direction:column;flex:1;min-height:0;';
                } else {
                    btn.classList.remove('active');
                    pane.style.cssText = 'display:none;flex-direction:column;';
                }
            });
        }

        tabDefs.forEach(function (t) {
            var btn = document.createElement('button');
            btn.id = 'oni-tab-btn-' + t.id;
            btn.className = 'oni-tab-btn';
            btn.textContent = t.label;
            btn.addEventListener('click', function () { _setTab(t.id); });
            tabBar.appendChild(btn);
        });
        modal.appendChild(tabBar);

        // Body — flex:1 flex-column, no overflow:auto here.
        // Each pane gets flex:1+min-height:0 when active (via _setTab), so the
        // pane's inner scrollWrap handles scrolling and lazy-loads correctly.
        var body = document.createElement('div');
        _css(body, 'flex:1;overflow:hidden;padding:12px 18px 8px;display:flex;flex-direction:column;min-height:0;');

        var emojiPane  = _buildEmojiPane(state);
        var iconsPane  = _buildIconsPane(state, data);
        body.appendChild(emojiPane);
        body.appendChild(iconsPane);
        modal.appendChild(body);

        // Color section (for SVG icons)
        var colorSection = document.createElement('div');
        colorSection.id = 'onigiri-icon-color-section';
        _css(colorSection, 'flex-shrink:0;padding:10px 18px 12px;');
        var colorLabel = document.createElement('div');
        colorLabel.textContent = 'Icon Color';
        _css(colorLabel, 'font-size:11px;font-weight:600;color:var(--fg-subtle,#888);margin-bottom:8px;');
        colorSection.appendChild(colorLabel);
        var swatchRow = document.createElement('div');
        swatchRow.className = 'oni-color-row';
        var presetColors = ['#888888','#FF6B6B','#FF9F43','#F7C948','#6BCB77','#4D96FF','#845EC2','#FF6FC8','#ffffff'];
        presetColors.forEach(function (hex) {
            var sw = document.createElement('div');
            sw.className = 'oni-color-swatch';
            sw.style.background = hex;
            sw.setAttribute('data-swatch', hex);
            if (_sameBaseColor(state.selectedColor, hex) && state.colorWasModified) {
                sw.style.boxShadow = '0 0 0 2px var(--canvas-overlay,#1e1e1e),0 0 0 3.5px ' + hex;
            }
            sw.addEventListener('click', function () {
                swatchRow.querySelectorAll('[data-swatch]').forEach(function (s) { s.style.boxShadow = ''; });
                sw.style.boxShadow = '0 0 0 2px var(--canvas-overlay,#1e1e1e),0 0 0 3.5px ' + hex;
                var current = _parseColor(state.selectedColor) || _parseColor('#888888');
                var preset = _parseColor(hex);
                _setSelectedColor(state, _rgbaToHex(preset.r, preset.g, preset.b, current ? current.a : 255));
            });
            swatchRow.appendChild(sw);
        });
        var plusBtn = document.createElement('button');
        plusBtn.type = 'button';
        plusBtn.className = 'oni-color-plus';
        plusBtn.title = 'Add custom color';
        plusBtn.appendChild(OnigiriEngine.createMaskIcon(OnigiriEngine.systemIconUrl('add.svg'), {
            className: 'oni-color-plus-icon',
            size: 12,
            color: 'currentColor'
        }));
        plusBtn.addEventListener('click', function (evt) {
            evt.preventDefault();
            evt.stopPropagation();
            _toggleColorPicker(state);
        });
        swatchRow.appendChild(plusBtn);
        colorSection.appendChild(swatchRow);

        var popover = document.createElement('div');
        popover.className = 'oni-color-picker-popover';

        var colorField = document.createElement('div');
        colorField.className = 'oni-color-field';
        var colorFieldInner = document.createElement('div');
        colorFieldInner.className = 'oni-color-field-inner';
        var colorFieldWhite = document.createElement('div');
        colorFieldWhite.className = 'oni-color-field-white';
        var colorFieldBlack = document.createElement('div');
        colorFieldBlack.className = 'oni-color-field-black';
        var colorFieldCursor = document.createElement('div');
        colorFieldCursor.className = 'oni-color-field-cursor';
        colorFieldInner.appendChild(colorFieldWhite);
        colorFieldInner.appendChild(colorFieldBlack);
        colorField.appendChild(colorFieldInner);
        colorField.appendChild(colorFieldCursor);
        popover.appendChild(colorField);

        var controlsRow = document.createElement('div');
        controlsRow.className = 'oni-picker-controls';
        var sliderStack = document.createElement('div');
        sliderStack.className = 'oni-slider-stack';

        var hueTrack = document.createElement('div');
        hueTrack.className = 'oni-slider-track oni-hue-track';
        var hueThumb = document.createElement('div');
        hueThumb.className = 'oni-slider-thumb';
        hueTrack.appendChild(hueThumb);
        sliderStack.appendChild(hueTrack);

        var alphaTrack = document.createElement('div');
        alphaTrack.className = 'oni-slider-track oni-alpha-track';
        var alphaGradient = document.createElement('div');
        alphaGradient.className = 'oni-alpha-gradient';
        var alphaThumb = document.createElement('div');
        alphaThumb.className = 'oni-slider-thumb';
        alphaTrack.appendChild(alphaGradient);
        alphaTrack.appendChild(alphaThumb);
        sliderStack.appendChild(alphaTrack);

        controlsRow.appendChild(sliderStack);

        var dropperBtn = document.createElement('button');
        dropperBtn.type = 'button';
        dropperBtn.className = 'oni-dropper-btn';
        dropperBtn.title = 'Pick a color from the screen';
        dropperBtn.appendChild(OnigiriEngine.createMaskIcon(OnigiriEngine.systemIconUrl('dropper.svg'), {
            className: 'oni-dropper-icon',
            size: 18,
            color: 'currentColor'
        }));
        dropperBtn.addEventListener('click', function (evt) {
            evt.preventDefault();
            evt.stopPropagation();
            if (typeof window.EyeDropper === 'function') {
                var eyedropper = new window.EyeDropper();
                eyedropper.open().then(function (result) {
                    var picked = _parseColor(result && result.sRGBHex ? result.sRGBHex : '');
                    var current = _parseColor(state.selectedColor) || _parseColor('#888888');
                    if (!picked || !current) return;
                    _setSelectedColor(state, _rgbaToHex(picked.r, picked.g, picked.b, current.a));
                }).catch(function () {});
            } else if (state._pickerRefs && state._pickerRefs.hexInput) {
                state._pickerRefs.hexInput.focus();
                state._pickerRefs.hexInput.select();
            }
        });
        controlsRow.appendChild(dropperBtn);
        popover.appendChild(controlsRow);

        var pickerInputs = document.createElement('div');
        pickerInputs.className = 'oni-picker-inputs';

        var hexSurface = document.createElement('div');
        hexSurface.className = 'oni-picker-surface oni-picker-hex';
        var customInput = document.createElement('input');
        customInput.type = 'text';
        customInput.className = 'oni-picker-input';
        customInput.maxLength = 36;
        customInput.placeholder = '#698751';
        customInput.spellcheck = false;
        customInput.value = _colorToFormatText(state.selectedColor || '#888888', state._pickerFormat);
        customInput.addEventListener('input', function () {
            var fmt = (state._pickerFormat || 'HEX').toUpperCase();
            var val = customInput.value;
            if (fmt === 'HEX') {
                val = val.replace(/[^#0-9A-Fa-f]/g, '');
                if (val && val.charAt(0) !== '#') val = '#' + val.replace(/#/g, '');
                else if (val) val = '#' + val.slice(1).replace(/#/g, '');
                if (val.length > 9) val = val.slice(0, 9);
                if (val !== customInput.value) customInput.value = val;
            }
            var normalized = _normalizeColor(val);
            if (normalized) _setSelectedColor(state, normalized);
        });
        customInput.addEventListener('blur', function () {
            var parsed = _parseColor(state.selectedColor) || _parseColor('#888888');
            customInput.value = _colorToFormatText(parsed, state._pickerFormat || 'HEX');
        });
        hexSurface.appendChild(customInput);
        pickerInputs.appendChild(hexSurface);

        var alphaSurface = document.createElement('div');
        alphaSurface.className = 'oni-picker-surface oni-picker-alpha';
        var alphaInput = document.createElement('input');
        alphaInput.type = 'text';
        alphaInput.className = 'oni-picker-input percent';
        alphaInput.maxLength = 4;
        alphaInput.placeholder = '100%';
        alphaInput.spellcheck = false;
        alphaInput.value = '100%';
        alphaInput.addEventListener('input', function () {
            var digits = alphaInput.value.replace(/[^0-9]/g, '');
            if (digits.length > 3) digits = digits.slice(0, 3);
            alphaInput.value = digits ? digits + '%' : '';
            if (!digits) return;
            var percent = Math.max(0, Math.min(100, parseInt(digits, 10)));
            var hsv = state._pickerModel || _rgbToHsv(_parseColor(state.selectedColor) || _parseColor('#888888'));
            _setSelectedColor(state, _hsvToHex(hsv.h, hsv.s, hsv.v, (percent / 100) * 255));
        });
        alphaInput.addEventListener('blur', function () {
            var parsed = _parseColor(state.selectedColor) || _parseColor('#888888');
            alphaInput.value = Math.round((parsed.a / 255) * 100) + '%';
        });
        alphaSurface.appendChild(alphaInput);
        pickerInputs.appendChild(alphaSurface);

        var formatSurface = document.createElement('div');
        formatSurface.className = 'oni-picker-surface oni-picker-format';
        var formatLabel = document.createElement('span');
        formatLabel.className = 'oni-picker-format-label';
        formatLabel.textContent = state._pickerFormat;
        formatSurface.appendChild(formatLabel);
        formatSurface.appendChild(OnigiriEngine.createMaskIcon(OnigiriEngine.systemIconUrl('down.svg'), {
            className: 'oni-picker-format-icon',
            size: 12,
            color: 'currentColor'
        }));
        formatSurface.addEventListener('click', function (evt) {
            evt.preventDefault();
            evt.stopPropagation();
            var cycle = ['HEX', 'RGB', 'HSL'];
            var idx = cycle.indexOf((state._pickerFormat || 'HEX').toUpperCase());
            state._pickerFormat = cycle[(idx + 1) % cycle.length];
            formatLabel.textContent = state._pickerFormat;
            var parsed = _parseColor(state.selectedColor) || _parseColor('#888888');
            customInput.value = _colorToFormatText(parsed, state._pickerFormat);
        });
        pickerInputs.appendChild(formatSurface);
        popover.appendChild(pickerInputs);

        modal.appendChild(colorSection);

        state._pickerRefs = {
            colorSection: colorSection,
            popover: popover,
            plusButton: plusBtn,
            field: colorField,
            fieldCursor: colorFieldCursor,
            hueTrack: hueTrack,
            hueThumb: hueThumb,
            alphaTrack: alphaTrack,
            alphaGradient: alphaGradient,
            alphaThumb: alphaThumb,
            hexInput: customInput,
            alphaInput: alphaInput,
            formatLabel: formatLabel
        };

        _bindPickerDrag(state, colorField, function (evt) {
            var rect = colorField.getBoundingClientRect();
            var x = Math.max(0, Math.min(evt.clientX - rect.left, rect.width));
            var y = Math.max(0, Math.min(evt.clientY - rect.top, rect.height));
            var hsv = state._pickerModel || _rgbToHsv(_parseColor(state.selectedColor) || _parseColor('#888888'));
            _setSelectedColor(
                state,
                _hsvToHex(
                    hsv.h,
                    rect.width ? (x / rect.width) * 100 : 0,
                    rect.height ? 100 - (y / rect.height) * 100 : 0,
                    (hsv.a / 100) * 255
                )
            );
        });
        _bindPickerDrag(state, hueTrack, function (evt) {
            var rect = hueTrack.getBoundingClientRect();
            var x = Math.max(0, Math.min(evt.clientX - rect.left, rect.width));
            var hsv = state._pickerModel || _rgbToHsv(_parseColor(state.selectedColor) || _parseColor('#888888'));
            _setSelectedColor(
                state,
                _hsvToHex(rect.width ? (x / rect.width) * 360 : 0, hsv.s, hsv.v, (hsv.a / 100) * 255)
            );
        });
        _bindPickerDrag(state, alphaTrack, function (evt) {
            var rect = alphaTrack.getBoundingClientRect();
            var x = Math.max(0, Math.min(evt.clientX - rect.left, rect.width));
            var hsv = state._pickerModel || _rgbToHsv(_parseColor(state.selectedColor) || _parseColor('#888888'));
            _setSelectedColor(
                state,
                _hsvToHex(hsv.h, hsv.s, hsv.v, rect.width ? (x / rect.width) * 255 : 255)
            );
        });

        // Footer
        var footer = document.createElement('div');
        _css(footer, 'display:flex;align-items:center;padding:10px 18px 14px;gap:8px;flex-shrink:0;');
        var resetBtn = document.createElement('button');
        resetBtn.textContent = 'Reset to Default';
        _css(resetBtn, 'background:#353535;border:none;border-radius:10px;padding:7px 14px;cursor:pointer;font-size:13px;color:var(--fg,#e0e0e0);transition:background 0.15s ease;outline:none;box-shadow:none;');
        resetBtn.addEventListener('mouseenter', function () { resetBtn.style.background = '#404040'; });
        resetBtn.addEventListener('mouseleave', function () { resetBtn.style.background = '#353535'; });
        resetBtn.addEventListener('click', function () { pycmd('onigiri_icon_chooser_reset:' + state.deckId); _close(); });
        var spacer = document.createElement('div');
        spacer.style.flex = '1';
        var cancelBtn = document.createElement('button');
        cancelBtn.textContent = 'Cancel';
        _css(cancelBtn, 'background:#353535;border:none;border-radius:10px;padding:7px 14px;cursor:pointer;font-size:13px;color:var(--fg,#e0e0e0);transition:background 0.15s ease;outline:none;box-shadow:none;');
        cancelBtn.addEventListener('mouseenter', function () { cancelBtn.style.background = '#404040'; });
        cancelBtn.addEventListener('mouseleave', function () { cancelBtn.style.background = '#353535'; });
        cancelBtn.addEventListener('click', _close);
        var saveBtn = document.createElement('button');
        saveBtn.textContent = 'Save';
        _css(saveBtn, 'background:var(--accent-color,#007aff);border:none;border-radius:8px;padding:7px 18px;cursor:pointer;font-size:13px;font-weight:600;color:#fff;transition:opacity 0.15s;');
        saveBtn.addEventListener('click', function () {
            var colorToSave = (state.selectedIcon === "" && !state.colorWasModified) ? "" : state.selectedColor;
            var payload = JSON.stringify({ icon: state.selectedIcon, color: colorToSave });
            pycmd('onigiri_icon_chooser_save:' + state.deckId + ':' + payload);
            _close();
        });
        footer.appendChild(resetBtn);
        footer.appendChild(spacer);
        footer.appendChild(cancelBtn);
        footer.appendChild(saveBtn);
        modal.appendChild(footer);

        bd.appendChild(modal);
        bd.appendChild(popover);
        document.body.appendChild(bd);
        bd.addEventListener('pointerdown', function (evt) {
            if (evt.target === bd && !state._pickerDragging) _close();
        });

        var onDocumentPointerDown = function (evt) {
            if (!state._pickerOpen || state._pickerDragging || Date.now() < state._pickerSuppressOutsideUntil) return;
            var refs = state._pickerRefs || {};
            var target = evt.target;
            if ((refs.colorSection && refs.colorSection.contains(target)) ||
                (refs.popover && refs.popover.contains(target)) ||
                (refs.plusButton && refs.plusButton.contains(target))) {
                return;
            }
            _closeColorPicker(state);
        };
        document.addEventListener('pointerdown', onDocumentPointerDown, true);
        _addCleanup(state, function () {
            document.removeEventListener('pointerdown', onDocumentPointerDown, true);
        });

        var onDocumentKeyDown = function (evt) {
            if (evt.key !== 'Escape') return;
            if (state._pickerOpen) {
                evt.preventDefault();
                evt.stopPropagation();
                _closeColorPicker(state);
            } else {
                _close();
            }
        };
        document.addEventListener('keydown', onDocumentKeyDown, true);
        _addCleanup(state, function () {
            document.removeEventListener('keydown', onDocumentKeyDown, true);
        });

        var onWindowReposition = function () {
            if (state._pickerOpen) _positionColorPicker(state);
        };
        window.addEventListener('resize', onWindowReposition);
        window.addEventListener('scroll', onWindowReposition, true);
        _addCleanup(state, function () {
            window.removeEventListener('resize', onWindowReposition);
            window.removeEventListener('scroll', onWindowReposition, true);
        });

        _setTab(activeTab);
        _updateColorPreview(state);
        return bd;
    }

    return {
        open: function (data) {
            _close(true);
            if (typeof OnigiriEngine !== 'undefined') {
                OnigiriEngine._clearAllRowVisualStates();
                var row = document.querySelector('tr.deck[data-did="' + data.deckId + '"]');
                if (row) row.classList.add('ctx-row-active');
            }
            _buildModal(data);
            pycmd('onigiri_ui_open');
        },

        refreshData: function (data) {
            var state = _state;
            state.data = data;
            var iconGrid = document.getElementById('onigiri-icon-grid-icons');
            if (iconGrid) {
                var pane = document.getElementById('onigiri-tab-pane-icons');
                if (pane) {
                    var search = pane.querySelector('.oni-search');
                    var filter = search ? search.value.trim().toLowerCase() : '';
                    iconGrid.innerHTML = '';
                    (data.icons || []).filter(function (it) {
                        return !filter || it.name.toLowerCase().indexOf(filter) !== -1;
                    }).forEach(function (item) {
                        var cell = document.createElement('div');
                        cell.className = 'oni-cell' + (state.selectedIcon === item.name ? ' oni-selected' : '');
                        cell.dataset.iconName = item.name;
                        var icon = document.createElement('div');
                        icon.style.cssText = 'width:30px;height:30px;mask-image:url("' + item.url + '");-webkit-mask-image:url("' + item.url + '");mask-size:contain;-webkit-mask-size:contain;mask-repeat:no-repeat;-webkit-mask-repeat:no-repeat;mask-position:center;-webkit-mask-position:center;background-color:' + _colorToCss(state.selectedColor || '#888888') + ';';
                        icon.className = 'oni-icon-img';
                        cell.appendChild(icon);
                        var del = document.createElement('div');
                        del.className = 'oni-del';
                        del.textContent = '×';
                        del.addEventListener('click', function (e) {
                            e.stopPropagation();
                            pycmd('onigiri_icon_chooser_delete_icon:' + state.deckId + ':' + item.name);
                        });
                        cell.appendChild(del);
                        cell.addEventListener('click', function () { _selectIcon(item.name, state); });
                        _bindCellHover(cell, del);
                        iconGrid.appendChild(cell);
                    });
                }
            }
        },

        close: _close,
    };
})();
