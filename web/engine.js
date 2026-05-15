// Onigiri Performance Engine

window.OnigiriEngine = {
    currentHoveredRow: null,
    _dnd: null, // Pointer-event drag-and-drop state

    init: function () {
        this.deckListContainer = document.getElementById('deck-list-container');
        if (!this.deckListContainer) {
            return;
        }

        // Pre-bind DnD handlers so they can be removed later
        this._boundDndMove = (e) => this._dndMove(e);
        this._boundDndEnd  = (e) => this._dndEnd(e);

        this.bindEvents();
        this.observeMutations();

        // Set search button icon via mask-image using the addon package path
        const pkg = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.addonPackage) || '';
        if (pkg) {
            const searchIcon = document.querySelector('#onigiri-search-toolbar-btn .search-btn-icon');
            if (searchIcon) {
                const searchUrl = `/_addons/${pkg}/system_files/system_icons/browse.svg`;
                searchIcon.style.cssText = (
                    'display:block;width:16px;height:16px;' +
                    'mask-size:contain;-webkit-mask-size:contain;' +
                    'mask-repeat:no-repeat;-webkit-mask-repeat:no-repeat;' +
                    'mask-position:center;-webkit-mask-position:center;' +
                    `mask-image:url(${searchUrl});-webkit-mask-image:url(${searchUrl});` +
                    'background-color:var(--icon-color,#777);'
                );
            }
        }

        // Initial processing of already loaded nodes
        this.processNewNodes(document.querySelectorAll('tr.deck, a.collapse'));
        this.restoreScrollPosition();

        // Initial fade state (handles page load at a non-zero scroll position)
        this.updateDeckFade();
        // Deck tree may not be fully painted yet — run again after first render
        setTimeout(() => this.updateDeckFade(), 300);

        // Signal the loading overlay: engine is ready.
        // The multi-signal controller in templates.py also waits for heatmap
        // when heatmap data is present, so this is always safe to call.
        if (typeof window.onigiriDismissOverlay === 'function') {
            window.onigiriDismissOverlay('engine');
        }
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

        // Snapshot hovered deck before DOM replacement so we can restore it
        // immediately, preventing the brief background-colour flicker caused
        // by the browser re-evaluating :hover after innerHTML is swapped.
        const hoveredDid = this.currentHoveredRow
            ? this.currentHoveredRow.dataset.did : null;

        this.deckListContainer.classList.add('scroll-restoring');

        // Snapshot existing row IDs so we can animate only the newly-appeared rows
        const _prevIds = new Set(
            Array.from(tableBody.querySelectorAll('tr.deck[data-did]')).map(r => r.dataset.did)
        );

        tableBody.innerHTML = newHtml;

        // Animate rows that are genuinely new (expansion animation)
        tableBody.querySelectorAll('tr.deck[data-did]').forEach(row => {
            if (!_prevIds.has(row.dataset.did)) {
                row.classList.add('deck-row-appear');
                row.addEventListener('animationend', () => row.classList.remove('deck-row-appear'), { once: true });
            }
        });

        // Restore hover class before any repaint
        if (hoveredDid) {
            const newRow = tableBody.querySelector(`tr.deck[data-did="${hoveredDid}"]`);
            if (newRow) {
                this.currentHoveredRow = newRow;
                newRow.classList.add('is-hovered');
            } else {
                this.currentHoveredRow = null;
            }
        }

        this.restoreScrollPosition();
        this.processNewNodes(tableBody.children);

        if (typeof window.updateDeckLayouts === 'function') {
            window.updateDeckLayouts();
        }

        // Update fade gradient after content changes (scrollHeight may differ)
        requestAnimationFrame(() => this.updateDeckFade());

        setTimeout(() => {
            this.deckListContainer.classList.remove('scroll-restoring');
        }, 50);
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
        let clickTimer = null;
        this.deckListContainer.addEventListener('click', (event) => {
            const target = event.target;

            // Case 1: Collapse icon — let onclick attribute fire.
            const collapseLink = target.closest('a.collapse');
            if (collapseLink) {
                collapseLink.style.transition = 'transform 0.2s ease';
                collapseLink.style.transform = collapseLink.classList.contains('state-open') ? 'rotate(0deg)' : 'rotate(90deg)';
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
            if (!deckRow) return;

            event.preventDefault();

            if (!clickTimer) {
                clickTimer = setTimeout(() => { clickTimer = null; }, 300);
            } else {
                clearTimeout(clickTimer);
                clickTimer = null;
                const mainLink = deckRow.querySelector('a.deck');
                if (mainLink) mainLink.click();
            }
        });

        // --- Right-click context menu on deck rows ---
        this.deckListContainer.addEventListener('contextmenu', (event) => {
            const deckRow = event.target.closest('tr.deck');
            if (!deckRow) return;
            event.preventDefault();
            const did = deckRow.dataset.did;
            if (!did) return;
            OnigiriEngine.showDeckContextMenu(event.clientX, event.clientY, did);
        });
    },

    // ─── Pointer-event Drag & Drop ─────────────────────────────────────────────

    /** Creates a compact ghost element that follows the cursor during drag. */
    _dndCreateGhost: function (row) {
        const origRect = row.getBoundingClientRect();
        const GHOST_W = 280;
        const table = document.createElement('table');
        table.className = 'deck-table';
        table.style.cssText = [
            'position:fixed',
            'z-index:9998',
            'pointer-events:none',
            'opacity:0.98',
            'box-shadow:0 8px 28px rgba(0,0,0,0.32)',
            'border-collapse:collapse',
            `width:${GHOST_W}px`,
            `top:${origRect.top}px`,
            `left:${origRect.left}px`,
            'background:var(--canvas,var(--frame-bg,#1e1e1e))',
            'border-radius:6px',
            'overflow:hidden',
        ].join(';');
        const tbody = document.createElement('tbody');
        const clone = row.cloneNode(true);
        clone.classList.remove('is-dragging', 'is-hovered');
        // Remove stat columns — ghost shows deck name only
        clone.querySelectorAll('td:not(.decktd)').forEach(td => td.remove());
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

    /** Initiates a pointer-event drag from a drag handle element. */
    _dndStart: function (e, handleEl) {
        const row = handleEl.closest('tr.deck');
        if (!row || this._dnd) return;
        e.preventDefault();

        const origRect = row.getBoundingClientRect();
        const offsetY = e.clientY - origRect.top;
        const GHOST_W = 280;
        const rawOffsetX = e.clientX - origRect.left;
        const offsetX = Math.max(8, Math.min(rawOffsetX, GHOST_W - 8));

        row.classList.add('is-dragging');

        const ghostEl = this._dndCreateGhost(row);
        document.body.appendChild(ghostEl);

        this._dnd = {
            sourceRow: row,
            ghostEl,
            offsetX,
            offsetY,
            lastClientY: e.clientY,
            lastTargetRow: null,
            lastInsertType: null,
            placeholder: null,
            lastMoveY: e.clientY,
            lastMoveTime: performance.now(),
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
        const rect = container.getBoundingClientRect();
        const y = this._dnd.lastClientY;
        const zone = 56;
        const maxSpeed = 14;
        let scrolled = false;

        if (y - rect.top < zone && y - rect.top >= 0) {
            const intensity = 1 - (y - rect.top) / zone;
            container.scrollTop -= Math.ceil(maxSpeed * intensity);
            scrolled = true;
        } else if (rect.bottom - y < zone && rect.bottom - y >= 0) {
            const intensity = 1 - (rect.bottom - y) / zone;
            container.scrollTop += Math.ceil(maxSpeed * intensity);
            scrolled = true;
        }

        // Keep the overlay insertion-line in sync when the list scrolls
        if (scrolled && this._dnd.placeholder && this._dnd.lastTargetRow && this._dnd.lastInsertType !== 'nest') {
            const rowRect = this._dnd.lastTargetRow.getBoundingClientRect();
            let barTop;
            if (this._dnd.lastInsertType === 'before') {
                const prevRow = this._dndPrevVisibleRow(this._dnd.lastTargetRow);
                barTop = prevRow
                    ? Math.round((prevRow.getBoundingClientRect().bottom + rowRect.top) / 2) - 2
                    : rowRect.top - 2;
            } else {
                const nextRow = this._dndNextVisibleRow(this._dnd.lastTargetRow);
                barTop = nextRow
                    ? Math.round((rowRect.bottom + nextRow.getBoundingClientRect().top) / 2) - 2
                    : rowRect.bottom - 2;
            }
            this._dnd.placeholder.style.top = barTop + 'px';
        }

        this._autoScrollRaf = requestAnimationFrame(() => this._dndAutoScroll());
    },

    /** Handles pointer movement during drag — moves ghost and shows drop indicator via CSS classes. */
    _dndMove: function (e) {
        if (!this._dnd) return;
        e.preventDefault();

        const { ghostEl, sourceRow, offsetX, offsetY } = this._dnd;
        this._dnd.lastClientY = e.clientY;

        // Ghost follows cursor freely in both axes
        ghostEl.style.top  = (e.clientY - offsetY) + 'px';
        ghostEl.style.left = (e.clientX - offsetX) + 'px';

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
        for (const row of allRows) {
            if (row === sourceRow) continue;
            const rect = row.getBoundingClientRect();
            if (e.clientY >= rect.top && e.clientY <= rect.bottom) { targetRow = row; break; }
        }
        // Edge case: cursor above the first visible row → snap to 'before' on that row.
        // Without this, dragging above the topmost row yields targetRow=null which clears
        // lastTargetRow, so the drop is silently cancelled when the pointer is released.
        if (!targetRow) {
            const visibleRows = Array.from(allRows).filter(r => r !== sourceRow);
            if (visibleRows.length) {
                const firstRect = visibleRows[0].getBoundingClientRect();
                const lastRect  = visibleRows[visibleRows.length - 1].getBoundingClientRect();
                if (e.clientY < firstRect.top) {
                    targetRow = visibleRows[0];
                    // Force insertType 'before' on the first row immediately (bypass hysteresis)
                    if (this._dnd.lastTargetRow !== targetRow || this._dnd.lastInsertType !== 'before') {
                        if (this._dnd.lastTargetRow) {
                            this._dnd.lastTargetRow.classList.remove('drag-over-target', 'drop-before', 'drop-after');
                        }
                        targetRow.classList.add('drop-before');
                        const barTop = firstRect.top - 2;
                        if (this._dnd.placeholder) { this._dnd.placeholder.style.top = barTop + 'px'; this._dnd.placeholder.style.opacity = '1'; }
                        else { this._dnd.placeholder = this._dndMakePlaceholder(barTop); if (this._dnd.placeholder) this._dnd.placeholder.style.opacity = '1'; }
                        this._dnd.lastTargetRow  = targetRow;
                        this._dnd.lastInsertType = 'before';
                    }
                    return;
                } else if (e.clientY > lastRect.bottom) {
                    targetRow = visibleRows[visibleRows.length - 1];
                    // Force insertType 'after' on the last row immediately
                    if (this._dnd.lastTargetRow !== targetRow || this._dnd.lastInsertType !== 'after') {
                        if (this._dnd.lastTargetRow) {
                            this._dnd.lastTargetRow.classList.remove('drag-over-target', 'drop-before', 'drop-after');
                        }
                        targetRow.classList.add('drop-after');
                        const barTop = lastRect.bottom - 2;
                        if (this._dnd.placeholder) { this._dnd.placeholder.style.top = barTop + 'px'; this._dnd.placeholder.style.opacity = '1'; }
                        else { this._dnd.placeholder = this._dndMakePlaceholder(barTop); if (this._dnd.placeholder) this._dnd.placeholder.style.opacity = '1'; }
                        this._dnd.lastTargetRow  = targetRow;
                        this._dnd.lastInsertType = 'after';
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
            if (prev === 'before') {
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

        // Skip if nothing changed
        if (targetRow === this._dnd.lastTargetRow && insertType === this._dnd.lastInsertType) return;

        // Clear old state
        if (this._dnd.lastTargetRow) {
            this._dnd.lastTargetRow.classList.remove('drag-over-target', 'drop-before', 'drop-after');
        }
        if (this._dnd.placeholder && insertType === 'nest') {
            this._dnd.placeholder.remove();
            this._dnd.placeholder = null;
        }
        this._dnd.lastTargetRow  = targetRow;
        this._dnd.lastInsertType = insertType;

        if (!targetRow) return;

        if (insertType === 'before') {
            targetRow.classList.add('drop-before');
            const rowRect = targetRow.getBoundingClientRect();
            // Use midpoint of gap so bar stays fixed when source row sits between two targets
            const prevRow = this._dndPrevVisibleRow(targetRow);
            // Check: would bar appear at source row's original slot?
            const allDomRows = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'));
            const prevIdx = prevRow ? allDomRows.indexOf(prevRow) : -1;
            const tgtIdx = allDomRows.indexOf(targetRow);
            const srcIdx = allDomRows.indexOf(this._dnd.sourceRow);
            const atOriginalSlot = srcIdx > prevIdx && srcIdx < tgtIdx;
            if (atOriginalSlot) {
                if (this._dnd.placeholder) this._dnd.placeholder.style.opacity = '0';
            } else {
                if (this._dnd.placeholder) this._dnd.placeholder.style.opacity = '1';
                const barTop = prevRow
                    ? Math.round((prevRow.getBoundingClientRect().bottom + rowRect.top) / 2) - 2
                    : rowRect.top - 2;
                if (this._dnd.placeholder) { this._dnd.placeholder.style.top = barTop + 'px'; }
                else { this._dnd.placeholder = this._dndMakePlaceholder(barTop); if (this._dnd.placeholder) this._dnd.placeholder.style.opacity = '1'; }
            }
        } else if (insertType === 'after') {
            targetRow.classList.add('drop-after');
            const rowRect = targetRow.getBoundingClientRect();
            const nextRow = this._dndNextVisibleRow(targetRow);
            // Check: would bar appear at source row's original slot?
            const allDomRows = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'));
            const nextIdx = nextRow ? allDomRows.indexOf(nextRow) : allDomRows.length;
            const tgtIdx = allDomRows.indexOf(targetRow);
            const srcIdx = allDomRows.indexOf(this._dnd.sourceRow);
            const atOriginalSlot = srcIdx > tgtIdx && srcIdx < nextIdx;
            if (atOriginalSlot) {
                if (this._dnd.placeholder) this._dnd.placeholder.style.opacity = '0';
            } else {
                if (this._dnd.placeholder) this._dnd.placeholder.style.opacity = '1';
                const barTop = nextRow
                    ? Math.round((rowRect.bottom + nextRow.getBoundingClientRect().top) / 2) - 2
                    : rowRect.bottom - 2;
                if (this._dnd.placeholder) { this._dnd.placeholder.style.top = barTop + 'px'; }
                else { this._dnd.placeholder = this._dndMakePlaceholder(barTop); if (this._dnd.placeholder) this._dnd.placeholder.style.opacity = '1'; }
            }
        } else {
            targetRow.classList.add('drag-over-target');
        }
    },

    /** Creates a fixed-position insertion-line overlay (does not touch the table DOM). */
    _dndMakePlaceholder: function (top) {
        const containerRect = this.deckListContainer.getBoundingClientRect();
        const line = document.createElement('div');
        line.className = 'dnd-placeholder';
        line.style.cssText = [
            'position:fixed',
            `left:${containerRect.left + 12}px`,
            `width:${containerRect.width - 24}px`,
            `top:${top}px`,
            'height:4px',
            'border-radius:2px',
            `background:var(--accent-color,#6366f1)`,
            'opacity:0.85',
            'pointer-events:none',
            'z-index:9997',
        ].join(';');
        document.body.appendChild(line);
        return line;
    },

    /** Returns the closest visible (non-dragging) row before `row` in DOM order. */
    _dndPrevVisibleRow: function (row) {
        const rows = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'));
        const idx = rows.indexOf(row);
        for (let i = idx - 1; i >= 0; i--) {
            if (!rows[i].classList.contains('is-dragging')) return rows[i];
        }
        return null;
    },

    /** Returns the closest visible (non-dragging) row after `row` in DOM order. */
    _dndNextVisibleRow: function (row) {
        const rows = Array.from(this.deckListContainer.querySelectorAll('tr.deck[data-did]'));
        const idx = rows.indexOf(row);
        for (let i = idx + 1; i < rows.length; i++) {
            if (!rows[i].classList.contains('is-dragging')) return rows[i];
        }
        return null;
    },

    /** Finalises the drag — fires pycmd and cleans up all state. */
    _dndEnd: function (e) {
        if (!this._dnd) return;

        const { sourceRow, ghostEl, lastTargetRow, lastInsertType } = this._dnd;

        // Cancel auto-scroll loop
        if (this._autoScrollRaf) {
            cancelAnimationFrame(this._autoScrollRaf);
            this._autoScrollRaf = null;
        }

        // Cleanup DOM and drop-state classes
        document.body.classList.remove('fast-dragging');
        ghostEl.remove();
        sourceRow.classList.remove('is-dragging');
        if (this._dnd.placeholder) { this._dnd.placeholder.remove(); this._dnd.placeholder = null; }
        this.deckListContainer.querySelectorAll('.drag-over-target, .drop-before, .drop-after')
            .forEach(r => r.classList.remove('drag-over-target', 'drop-before', 'drop-after'));

        document.removeEventListener('pointermove',   this._boundDndMove);
        document.removeEventListener('pointerup',     this._boundDndEnd);
        document.removeEventListener('pointercancel', this._boundDndEnd);
        this._dnd = null;

        if (!lastTargetRow || lastTargetRow === sourceRow) return;

        const sourceDid = sourceRow.dataset.did;
        const targetDid = lastTargetRow.dataset.did;
        if (!sourceDid || !targetDid) return;

        if (lastInsertType === 'nest') {
            pycmd('onigiri_drag_drop:' + JSON.stringify({ source_did: sourceDid, target_did: targetDid, type: 'nest' }));
        } else {
            // Collect visible deck rows (excluding the placeholder) in their
            // current DOM order, then splice source to the correct position.
            const allRows = Array.from(
                this.deckListContainer.querySelectorAll('tr.deck[data-did]:not(.dnd-placeholder)')
            );
            const allIds  = allRows.map(r => r.dataset.did);

            const srcIdx = allIds.indexOf(sourceDid);
            const newOrder = [...allIds];
            if (srcIdx !== -1) newOrder.splice(srcIdx, 1);

            const tgtIdx = newOrder.indexOf(targetDid);
            if (tgtIdx === -1) return;
            newOrder.splice(lastInsertType === 'before' ? tgtIdx : tgtIdx + 1, 0, sourceDid);

            pycmd('onigiri_drag_drop:' + JSON.stringify({ source_did: sourceDid, target_did: targetDid, type: lastInsertType, new_order: newOrder }));
        }
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
                    const clickableCell = el.querySelector('td.decktd');
                    if (clickableCell) clickableCell.style.cursor = 'pointer';

                    // Inject drag handle if not already present
                    if (!el.querySelector('.drag-handle')) {
                        const handle = document.createElement('span');
                        handle.className = 'drag-handle';
                        handle.title = 'Drag to reparent or reorder';
                        // 6-circle grid (2 columns × 3 rows, 48×48 viewBox)
                        handle.innerHTML = '<svg viewBox="0 0 48 48" width="12" height="12" fill="currentColor" style="display:block;"><circle cx="16" cy="12" r="4"/><circle cx="32" cy="12" r="4"/><circle cx="16" cy="24" r="4"/><circle cx="32" cy="24" r="4"/><circle cx="16" cy="36" r="4"/><circle cx="32" cy="36" r="4"/></svg>';
                        handle.style.touchAction = 'none'; // Required for pointer events on touch
                        handle.addEventListener('pointerdown', (e) => {
                            if (e.pointerType === 'mouse' && e.button !== 0) return;
                            OnigiriEngine._dndStart(e, handle);
                        });
                        handle.addEventListener('click', (e) => e.stopPropagation());
                        // If the row is already hovered (e.g. after a chevron-triggered
                        // tree refresh), show the handle immediately at full opacity —
                        // skipping the 120 ms fade-in prevents the brief flicker.
                        if (el.classList.contains('is-hovered')) {
                            handle.style.cssText = 'opacity:0.45;transition:none;';
                            requestAnimationFrame(() => { handle.style.cssText = ''; });
                        }
                        if (clickableCell) clickableCell.prepend(handle);
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

    toggleDeckSearch: function () {
        const bar = document.getElementById('onigiri-deck-search-bar');
        const searchBtn = document.getElementById('onigiri-search-toolbar-btn');
        const header = document.getElementById('deck-list-header');
        if (!bar) return;
        if (bar.classList.contains('is-visible')) {
            this._closeDeckSearch();
        } else {
            bar.classList.add('is-visible');
            if (searchBtn) { searchBtn.style.opacity = '0'; searchBtn.style.pointerEvents = 'none'; }
            if (header) { header.style.opacity = '0'; header.style.pointerEvents = 'none'; }
            const input = document.getElementById('onigiri-deck-search-input');
            if (input) { input.value = ''; input.focus({ preventScroll: true }); }
        }
    },

    _closeDeckSearch: function () {
        const bar = document.getElementById('onigiri-deck-search-bar');
        const searchBtn = document.getElementById('onigiri-search-toolbar-btn');
        const header = document.getElementById('deck-list-header');

        // Restore button + header immediately so they fade back in while bar animates out
        if (searchBtn) { searchBtn.style.opacity = ''; searchBtn.style.pointerEvents = ''; }
        if (header) { header.style.opacity = ''; header.style.pointerEvents = ''; }

        const input = document.getElementById('onigiri-deck-search-input');
        if (input) input.value = '';
        this.saveScrollPosition(); // preserve position across the tree reload
        this._filterDecks('');

        if (!bar || !bar.classList.contains('is-visible')) return;

        // Play the dismiss animation, then actually hide
        bar.classList.add('is-closing');
        bar.addEventListener('animationend', () => {
            bar.classList.remove('is-visible', 'is-closing');
        }, { once: true });
    },

    _searchDebounceTimer: null,

    _filterDecks: function (query) {
        clearTimeout(this._searchDebounceTimer);
        this._searchDebounceTimer = setTimeout(() => {
            pycmd('onigiri_deck_search:' + query.trim());
        }, 150);
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

    showDeckContextMenu: function(x, y, did) {
        const existing = document.getElementById('onigiri-ctx-menu');
        if (existing) existing.remove();

        // Highlight the row being acted on; suppress hover on all others
        document.querySelectorAll('tr.deck.ctx-row-active').forEach(r => r.classList.remove('ctx-row-active'));
        const activeRow = document.querySelector(`tr.deck[data-did="${did}"]`);
        if (activeRow) activeRow.classList.add('ctx-row-active');
        document.body.classList.add('ctx-menu-open');
        pycmd('onigiri_ui_open');

        const pkg = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.addonPackage) || '';
        const iconBase = pkg ? `/_addons/${pkg}/system_files/system_icons/` : '';
        const MASK_CSS = 'mask-size:contain;-webkit-mask-size:contain;mask-repeat:no-repeat;-webkit-mask-repeat:no-repeat;mask-position:center;-webkit-mask-position:center;width:16px;height:16px;min-width:16px;display:inline-block;flex-shrink:0;';

        const SVG_RENAME       = iconBase + 'rename.svg';
        const SVG_SUBDECK      = iconBase + 'subdeck.svg';
        const SVG_CHANGE_ICON  = iconBase + 'change_icon.svg';
        const SVG_CREATE_DECK  = iconBase + 'create_deck.svg';
        const SVG_OPTIONS      = iconBase + 'options.svg';
        const SVG_EXPORT       = iconBase + 'export.svg';
        const SVG_COPY_ID      = iconBase + 'copy_id.svg';
        const SVG_DELETE       = iconBase + 'delete.svg';
        // Star icons — outline for non-fav, filled for fav
        const SVG_STAR         = iconBase + 'star_filled.svg';
        const SVG_STAR_OUTLINE = iconBase + 'star_outline.svg';
        // Edit Icon — emoji/smiley face (for "Edit Icon" context menu item)
        const SVG_EDIT_ICON    = iconBase + 'edit_icon.svg';
        // Mark icons
        const SVG_MARK_CIRCLE  = iconBase + 'mark_circle.svg';
        const SVG_REMOVE_MARK  = iconBase + 'remove_mark.svg';

        // Determine current favourite state from data-is-fav attribute set by patcher.py
        const _favRow = document.querySelector(`tr.deck[data-did="${did}"]`);
        const isFav = !!(_favRow && _favRow.dataset.isFav === '1');

        function makeCtxIcon(iconSrc, flipX, flipY, iconColor) {
            const wrap = document.createElement('span');
            wrap.className = 'ctx-icon';
            let transform = '';
            const tx = flipX ? 'scaleX(-1)' : '';
            const ty = flipY ? 'scaleY(-1)' : '';
            if (tx || ty) transform = [tx, ty].filter(Boolean).join(' ');
            // Wrap the URL in double-quotes so that single-quote characters
            // inside data URIs (e.g. the SVG_STAR value) are valid CSS tokens.
            // Without the quotes the parser fails and the element renders as a
            // solid background-colour square (no mask applied).
            wrap.style.cssText = MASK_CSS
                + `background-color:${iconColor || 'var(--fg-subtle,var(--fg,currentColor))'};`
                + `mask-image:url("${iconSrc}");-webkit-mask-image:url("${iconSrc}");`
                + (transform ? `transform:${transform};` : '');
            return wrap;
        }

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
                { label: 'Rename',       iconSvg: SVG_RENAME,      cmd: 'onigiri_ctx_rename:'      + did },
                { label: 'Add Subdeck',  iconSvg: SVG_SUBDECK,     cmd: 'onigiri_ctx_subdeck:'     + did },
                { label: 'Edit Icon',    iconSvg: SVG_EDIT_ICON,   cmd: 'onigiri_ctx_change_icon:' + did },
                {
                    label:     isFav ? 'Unfavourite' : 'Favourite',
                    iconSvg:   isFav ? SVG_STAR : SVG_STAR_OUTLINE,
                    iconColor: isFav ? 'var(--accent-color)' : null,
                    cmd:       'onigiri_toggle_favorite:' + did,
                },
                // Mark item — rendered as a special submenu row
                { label: 'Mark', iconSvg: SVG_MARK_CIRCLE,
                  iconColor: currentMark ? MARK_COLORS.find(c=>c.key===currentMark)?.hex : 'var(--fg-subtle,var(--fg))',
                  isMarkSubmenu: true, did: did, currentMark: currentMark },
            ],
            // Group 2 — manage / info
            [
                { label: 'Deck Options', iconSvg: SVG_OPTIONS,     cmd: 'onigiri_ctx_options:'     + did },
                { label: 'Export Deck',  iconSvg: SVG_EXPORT,      cmd: 'onigiri_ctx_export:'      + did },
                { label: 'Copy ID',      iconSvg: SVG_COPY_ID,     cmd: 'onigiri_ctx_copy_id:'     + did },
            ],
            // Group 3 — destructive
            [
                { label: 'Delete Deck',  iconSvg: SVG_DELETE,      cmd: 'onigiri_ctx_delete:'      + did, danger: true },
            ],
        ];

        const menu = document.createElement('div');
        menu.id = 'onigiri-ctx-menu';

        const _menuCleanup = () => {
            menu.remove();
            const ms = document.getElementById('onigiri-mark-submenu');
            if (ms) ms.remove();
            document.querySelectorAll('tr.deck.ctx-row-active').forEach(r => r.classList.remove('ctx-row-active'));
            document.body.classList.remove('ctx-menu-open');
            pycmd('onigiri_ui_close');
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
                    el.appendChild(makeCtxIcon(item.iconSvg, false, false, item.iconColor));
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
                            si.addEventListener('click', () => { _menuCleanup(); pycmd('onigiri_ctx_mark:' + item.did + ':' + mc.key); });
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
                            si.addEventListener('click', () => { _menuCleanup(); pycmd('onigiri_ctx_mark:' + item.did + ':none'); });
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
                el.appendChild(makeCtxIcon(item.iconSvg, item.flipX, item.flipY, item.iconColor));
                const span = document.createElement('span');
                span.textContent = item.label;
                el.appendChild(span);
                el.addEventListener('click', () => {
                    _menuCleanup();
                    pycmd(item.cmd);
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
                const m  = document.getElementById('onigiri-ctx-menu');
                const ms = document.getElementById('onigiri-mark-submenu');
                if (m)  m.remove();
                if (ms) ms.remove();
                document.querySelectorAll('tr.deck.ctx-row-active').forEach(r => r.classList.remove('ctx-row-active'));
                document.body.classList.remove('ctx-menu-open');
                pycmd('onigiri_ui_close');
                document.removeEventListener('click', dismiss);
                document.removeEventListener('keydown', dismiss);
                window.removeEventListener('blur', dismiss);
            }
            document.addEventListener('click', dismiss);
            document.addEventListener('keydown', dismiss);
            window.addEventListener('blur', dismiss);
        }, 0);
    },

    showEllipsisMenu: function(btn, event) {
        if (event) { event.preventDefault(); event.stopPropagation(); }

        const existing = document.getElementById('onigiri-ellipsis-menu');
        if (existing) {
            existing.remove();
            const openBtn = document.querySelector('.onigiri-ellipsis-toolbar-btn.is-open');
            if (openBtn) openBtn.classList.remove('is-open');
            pycmd('onigiri_ui_close');
            return;
        }

        const actions = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.ellipsisActions) || [];
        if (!actions.length) return;

        const ICON_CSS = 'mask-size:contain;-webkit-mask-size:contain;mask-repeat:no-repeat;-webkit-mask-repeat:no-repeat;mask-position:center;-webkit-mask-position:center;width:16px;height:16px;min-width:16px;display:inline-block;flex-shrink:0;background-color:var(--fg-subtle,var(--fg,currentColor));';

        function makeIcon(iconUrl, iconSvg) {
            if (iconSvg) {
                const wrap = document.createElement('span');
                wrap.className = 'ctx-icon';
                wrap.style.cssText = 'width:16px;height:16px;min-width:16px;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;color:var(--fg-subtle,var(--fg,currentColor));';
                wrap.innerHTML = iconSvg;
                const svg = wrap.querySelector('svg');
                if (svg) { svg.setAttribute('width', '16'); svg.setAttribute('height', '16'); }
                return wrap;
            }
            const i = document.createElement('i');
            i.className = 'icon';
            if (iconUrl) i.style.cssText = 'mask-image:url(' + iconUrl + ');-webkit-mask-image:url(' + iconUrl + ');' + ICON_CSS;
            return i;
        }

        function closeSubmenus() {
            const s = document.getElementById('onigiri-ellipsis-submenu');
            if (s) s.remove();
        }

        function closeAll() {
            closeSubmenus();
            const m = document.getElementById('onigiri-ellipsis-menu');
            if (m) { m.remove(); pycmd('onigiri_ui_close'); }
            if (btn) btn.classList.remove('is-open');
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
            item.appendChild(makeIcon(action.iconUrl, action.iconSvg));

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

            if (action.children && action.children.length) {
                // Nested item — show chevron and hover submenu
                item.classList.add('has-submenu');
                const chevron = document.createElement('span');
                chevron.className = 'submenu-chevron';
                chevron.textContent = '›';
                item.appendChild(chevron);

                let hideTimer = null;
                const SVG_TICK = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M0 0h24v24H0z" fill="none"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="m5 14l3.5 3.5L19 6.5"/></svg>';

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
                        ci.appendChild(makeIcon(child.iconUrl, child.iconSvg));
                        const cl = document.createElement('span');
                        cl.textContent = child.label;
                        ci.appendChild(cl);
                        if (child.selected) {
                            const tick = document.createElement('span');
                            tick.className = 'ctx-icon';
                            tick.style.marginLeft = 'auto';
                            tick.innerHTML = SVG_TICK;
                            const tv = tick.querySelector('svg');
                            if (tv) { tv.setAttribute('width', '14'); tv.setAttribute('height', '14'); }
                            ci.appendChild(tick);
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

    function _close() {
        var bd = document.getElementById('onigiri-icon-backdrop');
        if (bd) { bd.remove(); pycmd('onigiri_ui_close'); }
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
            '.oni-hex-input{width:70px;box-sizing:border-box;padding:4px 8px;border-radius:6px;font-size:12px;font-family:monospace;',
            '  border:1px solid var(--border,rgba(255,255,255,0.15));background:var(--canvas-inset,rgba(255,255,255,0.06));',
            '  color:var(--fg,#e0e0e0);outline:none;}',
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
                icon.style.cssText = 'width:30px;height:30px;mask-image:url("' + item.url + '");-webkit-mask-image:url("' + item.url + '");mask-size:contain;-webkit-mask-size:contain;mask-repeat:no-repeat;-webkit-mask-repeat:no-repeat;mask-position:center;-webkit-mask-position:center;background-color:' + (state.selectedColor || '#888888') + ';';
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
        uploadBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>';
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
        document.querySelectorAll('#onigiri-icon-grid-icons .oni-icon-img').forEach(function (el) {
            el.style.backgroundColor = state.selectedColor || '#888888';
        });
        // Color section visibility is controlled exclusively by _setTab — not here.
    }

    function _buildModal(data) {
        _ensureStyles();
        _state = {
            deckId:        data.deckId,
            selectedIcon:  data.current && data.current.icon  ? data.current.icon  : '',
            selectedColor: data.current && data.current.color ? data.current.color : '#888888',
            data:          data,
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
        _css(colorLabel, 'font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:var(--fg-subtle,#888);margin-bottom:8px;');
        colorSection.appendChild(colorLabel);
        var swatchRow = document.createElement('div');
        _css(swatchRow, 'display:flex;align-items:center;gap:7px;flex-wrap:wrap;');
        var presetColors = ['#888888','#FF6B6B','#FF9F43','#F7C948','#6BCB77','#4D96FF','#845EC2','#FF6FC8','#ffffff'];
        var customInput = document.createElement('input');
        presetColors.forEach(function (hex) {
            var sw = document.createElement('div');
            _css(sw, 'width:24px;height:24px;border-radius:50%;background:' + hex + ';cursor:pointer;flex-shrink:0;');
            if (state.selectedColor === hex) sw.style.boxShadow = '0 0 0 2px var(--canvas-overlay,#1e1e1e),0 0 0 3.5px ' + hex;
            sw.setAttribute('data-swatch', hex);
            sw.addEventListener('click', function () {
                state.selectedColor = hex;
                swatchRow.querySelectorAll('[data-swatch]').forEach(function (s) { s.style.boxShadow = ''; });
                sw.style.boxShadow = '0 0 0 2px var(--canvas-overlay,#1e1e1e),0 0 0 3.5px ' + hex;
                customInput.value = hex;
                _updateColorPreview(state);
                pycmd('update_color:' + hex);
            });
            sw.addEventListener('mouseenter', function () { sw.style.transform = 'scale(1.18)'; });
            sw.addEventListener('mouseleave', function () { sw.style.transform = ''; });
            swatchRow.appendChild(sw);
        });
        customInput.type = 'text';
        customInput.className = 'oni-hex-input';
        customInput.value = state.selectedColor || '#888888';
        customInput.maxLength = 7;
        customInput.placeholder = '#rrggbb';
        customInput.title = 'Custom hex color';
        customInput.addEventListener('input', function () {
            var val = customInput.value.trim();
            if (!/^#[0-9a-fA-F]{6}$/.test(val)) return;
            state.selectedColor = val;
            swatchRow.querySelectorAll('[data-swatch]').forEach(function (s) { s.style.boxShadow = ''; });
            _updateColorPreview(state);
            pycmd('update_color:' + val);
        });
        swatchRow.appendChild(customInput);
        colorSection.appendChild(swatchRow);
        modal.appendChild(colorSection);

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
            var payload = JSON.stringify({ icon: state.selectedIcon, color: state.selectedColor });
            pycmd('onigiri_icon_chooser_save:' + state.deckId + ':' + payload);
            _close();
        });
        footer.appendChild(resetBtn);
        footer.appendChild(spacer);
        footer.appendChild(cancelBtn);
        footer.appendChild(saveBtn);
        modal.appendChild(footer);

        bd.appendChild(modal);
        document.body.appendChild(bd);
        bd.addEventListener('click', _close);

        _setTab(activeTab);
        _updateColorPreview(state);
        return bd;
    }

    return {
        open: function (data) { _close(); _buildModal(data); pycmd('onigiri_ui_open'); },

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
                        icon.style.cssText = 'width:30px;height:30px;mask-image:url("' + item.url + '");-webkit-mask-image:url("' + item.url + '");mask-size:contain;-webkit-mask-size:contain;mask-repeat:no-repeat;-webkit-mask-repeat:no-repeat;mask-position:center;-webkit-mask-position:center;background-color:' + (state.selectedColor || '#888888') + ';';
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