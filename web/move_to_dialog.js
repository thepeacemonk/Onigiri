(function () {
    if (window.OnigiriMoveToDialog) return;

    var state = {
        source: null,
        destinations: [],
        selectedId: null,
        cleanupFns: [],
        preloadedIcons: [],
        hoverId: null,
        highlightRaf: 0
    };

    function addCleanup(fn) {
        state.cleanupFns.push(fn);
    }

    function runCleanup() {
        while (state.cleanupFns.length) {
            var fn = state.cleanupFns.pop();
            try { fn(); } catch (_) {}
        }
    }

    function resolveIconUrl(iconRef) {
        var url = String(iconRef || '');
        if (!url) return '';
        if (url.indexOf('/') !== -1) return url;
        if (window.OnigiriEngine && typeof OnigiriEngine.systemIconUrl === 'function') {
            return OnigiriEngine.systemIconUrl(url);
        }
        return url;
    }

    function makeIcon(iconRef, className, size, color) {
        if (window.OnigiriEngine && typeof OnigiriEngine.createMaskIcon === 'function') {
            return OnigiriEngine.createMaskIcon(resolveIconUrl(iconRef), {
                className: className || 'onigiri-move-icon',
                size: size || 16,
                color: color || 'currentColor'
            });
        }
        var fallback = document.createElement('span');
        fallback.className = className || 'onigiri-move-icon';
        return fallback;
    }

    function ensureStyles() {
        if (document.getElementById('onigiri-move-to-style')) return;

        var style = document.createElement('style');
        style.id = 'onigiri-move-to-style';
        style.textContent = [
            '#onigiri-move-backdrop{position:fixed;inset:0;z-index:200000;display:flex;align-items:center;justify-content:center;',
            '  background:rgba(0,0,0,0.58);contain:layout paint style;isolation:isolate;transform:translateZ(0);',
            '  backface-visibility:hidden;-webkit-backface-visibility:hidden;}',
            '#onigiri-move-backdrop.is-preparing{visibility:hidden;}',
            '#onigiri-move-backdrop *{box-sizing:border-box;}',
            '#onigiri-move-backdrop button,#onigiri-move-backdrop input{appearance:none;-webkit-appearance:none;',
            '  font-family:var(--font-main,-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif);}',
            '#onigiri-move-backdrop button{border:none !important;outline:none !important;box-shadow:none !important;',
            '  background-image:none !important;appearance:none;-webkit-appearance:none;}',
            '.onigiri-move-modal{width:540px;max-width:94vw;height:620px;max-height:88vh;display:flex;flex-direction:column;overflow:hidden;',
            '  border-radius:16px;border:1px solid var(--border,rgba(255,255,255,0.14));',
            '  background:var(--canvas-overlay,var(--canvas,#1e1e1e));color:var(--fg,#e8e8e8);',
            '  box-shadow:0 24px 70px rgba(0,0,0,0.42);',
            '  backface-visibility:hidden;-webkit-backface-visibility:hidden;transform:translateZ(0);contain:layout paint style;isolation:isolate;}',
            '.onigiri-move-header{display:flex;align-items:flex-start;gap:12px;padding:18px 18px 14px;border-bottom:1px solid var(--border,rgba(255,255,255,0.12));}',
            '.onigiri-move-header-icon{width:34px;height:34px;min-width:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;',
            '  color:var(--accent-color,#007aff);background:var(--highlight-bg,rgba(128,128,128,0.14));}',
            '.onigiri-move-title-wrap{min-width:0;flex:1;}',
            '.onigiri-move-title{font-size:16px;font-weight:700;line-height:1.2;margin:0 0 5px;color:var(--fg,#e8e8e8);}',
            '.onigiri-move-subtitle{display:flex;align-items:center;gap:7px;min-width:0;font-size:13px;color:var(--fg-subtle,#9a9a9a);line-height:1.35;}',
            '.onigiri-move-source{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--fg,#e8e8e8);font-weight:600;}',
            '.onigiri-move-close{width:30px;height:30px;min-width:30px;padding:0;border:none !important;border-radius:8px;background:transparent !important;color:var(--fg-subtle,#999);',
            '  display:flex;align-items:center;justify-content:center;cursor:pointer;outline:none !important;box-shadow:none !important;filter:none !important;',
            '  opacity:0.72;transition:none;}',
            '.onigiri-move-close:hover,.onigiri-move-close:focus,.onigiri-move-close:active{background:transparent !important;color:var(--fg,#e8e8e8);opacity:1;box-shadow:none !important;border:none !important;}',
            '.onigiri-move-search-wrap{position:relative;margin:14px 18px 10px;flex-shrink:0;}',
            '.onigiri-move-search-icon{position:absolute;left:13px;top:50%;transform:translateY(-50%);color:var(--fg-subtle,#888);pointer-events:none;}',
            '.onigiri-move-search{width:100%;height:38px;padding:0 13px 0 38px;border-radius:999px;border:1px solid var(--border,rgba(255,255,255,0.14));',
            '  background:var(--canvas-inset,rgba(255,255,255,0.07));color:var(--fg,#e8e8e8);font-size:13px;outline:none;box-shadow:none;',
            '  transition:none;}',
            '.onigiri-move-search::placeholder{color:var(--fg-subtle,#888);}',
            '.onigiri-move-search:hover{background:var(--canvas-inset,rgba(255,255,255,0.07));}',
            '.onigiri-move-search:focus{border-color:var(--accent-color,#007aff);}',
            '.onigiri-move-list{flex:1;min-height:0;margin:0 18px 12px;padding:5px;overflow:auto;border:1px solid var(--border,rgba(255,255,255,0.12));',
            '  border-radius:12px;background:var(--canvas,rgba(255,255,255,0.04));position:relative;contain:layout paint style;isolation:isolate;}',
            '.onigiri-move-highlight{position:absolute;top:0;left:5px;right:5px;height:0;border-radius:9px;pointer-events:none;opacity:0;',
            '  transform:translate3d(0,0,0);will-change:transform,opacity,height;contain:paint;}',
            '.onigiri-move-hover-layer{z-index:0;background:var(--canvas-inset,rgba(255,255,255,0.08));}',
            '.onigiri-move-selected-layer{z-index:1;background:transparent;box-shadow:inset 0 0 0 2px var(--accent-color,#007aff);}',
            '.onigiri-move-row{width:100%;display:flex;align-items:center;gap:11px;padding:10px;border-radius:9px;border:none;',
            '  color:var(--fg,#e8e8e8);cursor:pointer;user-select:none;background:transparent;position:relative;z-index:2;transition:none;}',
            '.onigiri-move-row + .onigiri-move-row{margin-top:3px;}',
            '.onigiri-move-row.is-selected{color:var(--fg,#e8e8e8);}',
            '.onigiri-move-row.is-selected .onigiri-move-row-icon{color:var(--accent-color,#007aff);}',
            '.onigiri-move-row.is-hidden{display:none;}',
            '.onigiri-move-row.is-disabled{cursor:not-allowed;opacity:0.46;}',
            '.onigiri-move-row-icon{width:28px;height:28px;min-width:28px;border-radius:8px;display:flex;align-items:center;justify-content:center;',
            '  color:var(--fg-subtle,#999);background:var(--canvas-inset,rgba(255,255,255,0.07));}',
            '.onigiri-move-row-text{min-width:0;flex:1;}',
            '.onigiri-move-row-name{font-size:13px;font-weight:650;line-height:1.25;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
            '.onigiri-move-row-path{font-size:11px;color:var(--fg-subtle,#999);line-height:1.25;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
            '.onigiri-move-row-reason{font-size:11px;color:var(--fg-subtle,#999);margin-left:auto;padding-left:8px;white-space:nowrap;}',
            '.onigiri-move-empty{height:100%;min-height:160px;display:none;align-items:center;justify-content:center;text-align:center;',
            '  color:var(--fg-subtle,#999);font-size:13px;padding:20px;}',
            '.onigiri-move-error{display:none;margin:0 18px 10px;padding:9px 11px;border-radius:9px;background:rgba(192,48,48,0.12);',
            '  color:#d84a4a;font-size:12px;line-height:1.35;}',
            '.onigiri-move-footer{display:flex;align-items:center;gap:8px;padding:12px 18px 16px;border-top:1px solid var(--border,rgba(255,255,255,0.12));}',
            '.onigiri-move-spacer{flex:1;}',
            '.onigiri-move-btn{height:36px;padding:0 15px;border:none !important;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;gap:7px;',
            '  cursor:pointer;font-size:13px;font-weight:650;outline:none !important;box-shadow:none !important;background-image:none !important;',
            '  filter:none !important;transition:none;}',
            '.onigiri-move-btn-secondary{background:var(--canvas-inset,rgba(255,255,255,0.08)) !important;color:var(--fg,#e8e8e8);}',
            '.onigiri-move-btn-secondary:hover,.onigiri-move-btn-secondary:focus,.onigiri-move-btn-secondary:active{background:var(--canvas-inset,rgba(255,255,255,0.08)) !important;border:none !important;box-shadow:none !important;outline:none !important;}',
            '.onigiri-move-btn-primary{background:var(--accent-color,#007aff) !important;color:#fff;}',
            '.onigiri-move-btn-primary:hover,.onigiri-move-btn-primary:focus,.onigiri-move-btn-primary:active{background:var(--accent-color,#007aff) !important;border:none !important;box-shadow:none !important;outline:none !important;filter:none !important;}',
            '.onigiri-move-btn:not(:disabled):hover{opacity:0.92;}',
            '.onigiri-move-btn:not(:disabled):active{opacity:0.84;}',
            '.onigiri-move-btn:disabled{opacity:0.42;cursor:not-allowed;filter:none !important;}',
            '.onigiri-move-btn-primary:disabled{color:rgba(255,255,255,0.82) !important;-webkit-text-fill-color:rgba(255,255,255,0.82);}',
            '.onigiri-move-btn:disabled:hover{filter:none !important;}',
            '.onigiri-move-list::-webkit-scrollbar{width:10px;background:transparent;}',
            '.onigiri-move-list::-webkit-scrollbar-thumb{background:rgba(128,128,128,0.38);border-radius:999px;border:2px solid transparent;background-clip:content-box;}',
            '.onigiri-move-list::-webkit-scrollbar-track{background:transparent;}'
        ].join('');
        document.head.appendChild(style);
    }

    function close(skipUiClose) {
        var backdrop = document.getElementById('onigiri-move-backdrop');
        runCleanup();
        if (backdrop) backdrop.remove();

        if (window.OnigiriEngine && typeof OnigiriEngine.clearDialogFocus === 'function') {
            OnigiriEngine.clearDialogFocus();
        } else {
            document.querySelectorAll('tr.deck.ctx-row-active').forEach(function (row) {
                row.classList.remove('ctx-row-active');
            });
            document.body.classList.remove('dialog-focus');
        }

        state.source = null;
        state.destinations = [];
        state.selectedId = null;
        state.rowById = {};
        state.hoverLayer = null;
        state.selectedLayer = null;
        state.preloadedIcons = [];
        state.hoverId = null;
        if (state.highlightRaf) {
            cancelAnimationFrame(state.highlightRaf);
            state.highlightRaf = 0;
        }

        if (!skipUiClose && backdrop && typeof pycmd === 'function') {
            pycmd('onigiri_ui_close');
        }
    }

    function destinationMatches(dest, query) {
        if (!query) return true;
        var haystack = [
            dest.name || '',
            dest.path || '',
            dest.reason || ''
        ].join(' ').toLowerCase();
        return haystack.indexOf(query) !== -1;
    }

    function resolveIconUrl(iconRef) {
        var iconUrl = String(iconRef || '');
        if (!iconUrl) return '';
        if (iconUrl.indexOf('/') !== -1) return iconUrl;
        if (window.OnigiriEngine && typeof OnigiriEngine.systemIconUrl === 'function') {
            return OnigiriEngine.systemIconUrl(iconUrl);
        }
        return iconUrl;
    }

    function preloadCommonIcons() {
        var urls = ['move_deck.svg', 'cancel.svg', 'search.svg', 'deck.svg', 'subdeck.svg', 'folder.svg', 'filtered_deck.svg']
            .map(resolveIconUrl)
            .filter(Boolean);
        if (window.OnigiriEngine && typeof OnigiriEngine.preloadMaskIcons === 'function') {
            OnigiriEngine.preloadMaskIcons(urls);
        }
        return urls.map(function (url) {
            var img = new Image();
            img.decoding = 'async';
            img.src = url;
            return img;
        });
    }

    function warmDialogSurface() {
        if (document.getElementById('onigiri-move-warmup')) return;
        var warmup = document.createElement('div');
        warmup.id = 'onigiri-move-warmup';
        warmup.setAttribute('aria-hidden', 'true');
        warmup.style.cssText = 'position:fixed;left:-10000px;top:-10000px;width:540px;height:620px;visibility:hidden;pointer-events:none;contain:layout paint style;overflow:hidden;';

        var modal = document.createElement('div');
        modal.className = 'onigiri-move-modal';
        var search = document.createElement('input');
        search.className = 'onigiri-move-search';
        var list = document.createElement('div');
        list.className = 'onigiri-move-list';
        var row = document.createElement('div');
        row.className = 'onigiri-move-row is-selected';
        list.appendChild(row);
        var footer = document.createElement('div');
        footer.className = 'onigiri-move-footer';
        var secondary = document.createElement('button');
        secondary.className = 'onigiri-move-btn onigiri-move-btn-secondary';
        secondary.textContent = 'Cancel';
        var primary = document.createElement('button');
        primary.className = 'onigiri-move-btn onigiri-move-btn-primary';
        primary.textContent = 'Move';
        footer.appendChild(secondary);
        footer.appendChild(primary);
        modal.appendChild(search);
        modal.appendChild(list);
        modal.appendChild(footer);
        warmup.appendChild(modal);
        (document.body || document.documentElement).appendChild(warmup);
        warmup.getBoundingClientRect();
    }

    ensureStyles();
    state.preloadedIcons = preloadCommonIcons();
    warmDialogSurface();

    function revealWhenStable(backdrop, focusTarget) {
        if (!backdrop) return;
        // Force initial style/layout while hidden so Qt WebEngine has stable layers before reveal.
        backdrop.getBoundingClientRect();
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                backdrop.classList.remove('is-preparing');
                if (!focusTarget) return;
                try {
                    focusTarget.focus({ preventScroll: true });
                } catch (_) {
                    focusTarget.focus();
                }
            });
        });
    }

    function getRowById(id) {
        if (id === null || id === undefined || !state.rowById) return null;
        return state.rowById[String(id)] || null;
    }

    function isRowVisible(row) {
        return !!row && !row.classList.contains('is-hidden') && row.offsetParent !== null;
    }

    function positionHighlight(layer, row) {
        if (!layer) return;
        if (!isRowVisible(row)) {
            layer.style.opacity = '0';
            layer.style.height = '0px';
            return;
        }
        layer.style.height = row.offsetHeight + 'px';
        layer.style.transform = 'translate3d(0,' + row.offsetTop + 'px,0)';
        layer.style.opacity = '1';
    }

    function updateHighlights() {
        state.highlightRaf = 0;
        var selectedRow = getRowById(state.selectedId);
        var hoverRow = getRowById(state.hoverId);
        if (hoverRow && (hoverRow.classList.contains('is-disabled') || state.hoverId === state.selectedId)) {
            hoverRow = null;
        }
        positionHighlight(state.selectedLayer, selectedRow);
        positionHighlight(state.hoverLayer, hoverRow);
    }

    function queueHighlightUpdate() {
        if (state.highlightRaf) return;
        state.highlightRaf = requestAnimationFrame(updateHighlights);
    }

    function updateConfirmState() {
        var confirmBtn = document.getElementById('onigiri-move-confirm');
        if (!confirmBtn) return;
        var selected = state.destinations.filter(function (dest) {
            return String(dest.id) === String(state.selectedId);
        })[0];
        confirmBtn.disabled = !selected || !!selected.disabled || !!state.busy;
    }

    function selectDestination(destinationId) {
        state.selectedId = destinationId === null || destinationId === undefined
            ? null
            : String(destinationId);

        Object.keys(state.rowById || {}).forEach(function (id) {
            state.rowById[id].classList.toggle('is-selected', id === state.selectedId);
        });

        var err = document.getElementById('onigiri-move-error');
        if (err) err.style.display = 'none';
        updateConfirmState();
        queueHighlightUpdate();
    }

    function buildRows() {
        var list = document.getElementById('onigiri-move-list');
        var empty = document.getElementById('onigiri-move-empty');
        var search = document.getElementById('onigiri-move-search');
        if (!list || !empty) return;

        list.innerHTML = '';
        state.rowById = {};

        state.hoverLayer = document.createElement('div');
        state.hoverLayer.className = 'onigiri-move-highlight onigiri-move-hover-layer';
        state.selectedLayer = document.createElement('div');
        state.selectedLayer.className = 'onigiri-move-highlight onigiri-move-selected-layer';
        list.appendChild(state.hoverLayer);
        list.appendChild(state.selectedLayer);

        state.destinations.forEach(function (dest) {
            var row = document.createElement('div');
            row.className = 'onigiri-move-row';
            row.dataset.destinationId = String(dest.id);
            if (dest.disabled) row.classList.add('is-disabled');

            var iconWrap = document.createElement('div');
            iconWrap.className = 'onigiri-move-row-icon';
            iconWrap.appendChild(makeIcon(dest.iconUrl || (dest.kind === 'root' ? 'folder.svg' : 'deck.svg'), 'onigiri-move-row-svg', 15, 'currentColor'));
            row.appendChild(iconWrap);

            var text = document.createElement('div');
            text.className = 'onigiri-move-row-text';
            var name = document.createElement('div');
            name.className = 'onigiri-move-row-name';
            name.textContent = dest.name || dest.path || 'Untitled deck';
            text.appendChild(name);

            var path = document.createElement('div');
            path.className = 'onigiri-move-row-path';
            path.textContent = dest.kind === 'root' ? 'Move to the deck browser root' : (dest.path || dest.name || '');
            text.appendChild(path);
            row.appendChild(text);

            if (dest.reason) {
                var reason = document.createElement('div');
                reason.className = 'onigiri-move-row-reason';
                reason.textContent = dest.reason;
                row.appendChild(reason);
            }

            row.addEventListener('click', function () {
                if (dest.disabled || state.busy) return;
                selectDestination(dest.id);
            });

            state.rowById[String(dest.id)] = row;
            list.appendChild(row);
        });

        list.appendChild(empty);
        if (search) search.value = search.value || '';
        applyFilter();
    }

    function applyFilter() {
        var empty = document.getElementById('onigiri-move-empty');
        var search = document.getElementById('onigiri-move-search');
        var query = search ? search.value.trim().toLowerCase() : '';
        var visibleCount = 0;
        var selectedVisible = false;

        state.destinations.forEach(function (dest) {
            var row = state.rowById && state.rowById[String(dest.id)];
            if (!row) return;
            var visible = !query || destinationMatches(dest, query);
            row.classList.toggle('is-hidden', !visible);
            if (!visible) return;
            visibleCount += 1;
            if (String(dest.id) === String(state.selectedId)) selectedVisible = true;
        });

        if (state.hoverId !== null) {
            var hoverRow = getRowById(state.hoverId);
            if (!isRowVisible(hoverRow)) state.hoverId = null;
        }

        if (state.selectedId !== null && !selectedVisible) {
            selectDestination(null);
        } else {
            updateConfirmState();
            queueHighlightUpdate();
        }

        if (empty) empty.style.display = visibleCount ? 'none' : 'flex';
    }

    function showError(message) {
        state.busy = false;
        var error = document.getElementById('onigiri-move-error');
        if (error) {
            error.textContent = message || 'Could not move deck.';
            error.style.display = 'block';
        }
        updateConfirmState();
    }

    function buildModal(data) {
        ensureStyles();

        state.source = data.source || {};
        if (!Array.isArray(state.source.ids) || !state.source.ids.length) {
            state.source.ids = state.source.id ? [state.source.id] : [];
        }
        state.source.count = state.source.ids.length || state.source.count || 1;
        state.destinations = Array.isArray(data.destinations) ? data.destinations : [];
        state.selectedId = null;
        state.cleanupFns = [];
        state.busy = false;
        state.hoverId = null;
        state.highlightRaf = 0;

        var backdrop = document.createElement('div');
        backdrop.id = 'onigiri-move-backdrop';
        backdrop.className = 'is-preparing';

        var modal = document.createElement('div');
        modal.className = 'onigiri-move-modal';
        modal.addEventListener('click', function (evt) { evt.stopPropagation(); });
        modal.addEventListener('pointerdown', function (evt) { evt.stopPropagation(); });

        var header = document.createElement('div');
        header.className = 'onigiri-move-header';

        var headerIcon = document.createElement('div');
        headerIcon.className = 'onigiri-move-header-icon';
        headerIcon.appendChild(makeIcon('move_deck.svg', 'onigiri-move-header-svg', 18, 'currentColor'));
        header.appendChild(headerIcon);

        var titleWrap = document.createElement('div');
        titleWrap.className = 'onigiri-move-title-wrap';
        var title = document.createElement('div');
        title.className = 'onigiri-move-title';
        title.textContent = state.source.count > 1 ? 'Move Decks' : 'Move Deck';
        titleWrap.appendChild(title);

        var subtitle = document.createElement('div');
        subtitle.className = 'onigiri-move-subtitle';
        var subtitleLabel = document.createElement('span');
        subtitleLabel.textContent = 'Moving';
        subtitle.appendChild(subtitleLabel);
        var sourceName = document.createElement('span');
        sourceName.className = 'onigiri-move-source';
        sourceName.title = state.source.count > 1 && Array.isArray(state.source.names)
            ? state.source.names.join('\n')
            : (state.source.name || '');
        sourceName.textContent = state.source.label || state.source.name || 'Selected deck';
        subtitle.appendChild(sourceName);
        titleWrap.appendChild(subtitle);
        header.appendChild(titleWrap);

        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'onigiri-move-close';
        closeBtn.title = 'Close';
        closeBtn.appendChild(makeIcon('cancel.svg', 'onigiri-move-close-svg', 14, 'currentColor'));
        closeBtn.addEventListener('click', function () { close(false); });
        header.appendChild(closeBtn);
        modal.appendChild(header);

        var searchWrap = document.createElement('div');
        searchWrap.className = 'onigiri-move-search-wrap';
        searchWrap.appendChild(makeIcon('search.svg', 'onigiri-move-search-icon', 15, 'currentColor'));
        var search = document.createElement('input');
        search.id = 'onigiri-move-search';
        search.className = 'onigiri-move-search';
        search.type = 'text';
        search.placeholder = 'Search destination decks';
        search.autocomplete = 'off';
        search.spellcheck = false;
        search.addEventListener('input', applyFilter);
        searchWrap.appendChild(search);
        modal.appendChild(searchWrap);

        var list = document.createElement('div');
        list.id = 'onigiri-move-list';
        list.className = 'onigiri-move-list';
        var onListPointerOver = function (evt) {
            var row = evt.target && evt.target.closest ? evt.target.closest('.onigiri-move-row') : null;
            if (!row || row.parentElement !== list || row.classList.contains('is-disabled') || state.busy) {
                if (state.hoverId !== null) {
                    state.hoverId = null;
                    queueHighlightUpdate();
                }
                return;
            }
            var nextId = row.dataset.destinationId || null;
            if (nextId !== state.hoverId) {
                state.hoverId = nextId;
                queueHighlightUpdate();
            }
        };
        var onListPointerLeave = function () {
            if (state.hoverId === null) return;
            state.hoverId = null;
            queueHighlightUpdate();
        };
        list.addEventListener('pointerover', onListPointerOver);
        list.addEventListener('pointerleave', onListPointerLeave);
        addCleanup(function () {
            list.removeEventListener('pointerover', onListPointerOver);
            list.removeEventListener('pointerleave', onListPointerLeave);
        });
        var empty = document.createElement('div');
        empty.id = 'onigiri-move-empty';
        empty.className = 'onigiri-move-empty';
        empty.textContent = 'No matching decks found';
        list.appendChild(empty);
        modal.appendChild(list);

        var error = document.createElement('div');
        error.id = 'onigiri-move-error';
        error.className = 'onigiri-move-error';
        modal.appendChild(error);

        var footer = document.createElement('div');
        footer.className = 'onigiri-move-footer';
        var spacer = document.createElement('div');
        spacer.className = 'onigiri-move-spacer';

        var cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'onigiri-move-btn onigiri-move-btn-secondary';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.addEventListener('click', function () { close(false); });

        var confirmBtn = document.createElement('button');
        confirmBtn.type = 'button';
        confirmBtn.id = 'onigiri-move-confirm';
        confirmBtn.className = 'onigiri-move-btn onigiri-move-btn-primary';
        confirmBtn.disabled = true;
        confirmBtn.textContent = 'Move';
        confirmBtn.addEventListener('click', function () {
            if (!state.selectedId || state.busy) return;
            state.busy = true;
            updateConfirmState();
            var payload = {
                source_dids: state.source.ids || (state.source.id ? [state.source.id] : []),
                target_did: state.selectedId
            };
            pycmd('onigiri_move_deck:' + encodeURIComponent(JSON.stringify(payload)));
        });

        footer.appendChild(spacer);
        footer.appendChild(cancelBtn);
        footer.appendChild(confirmBtn);
        modal.appendChild(footer);

        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);

        backdrop.addEventListener('pointerdown', function (evt) {
            if (evt.target === backdrop) close(false);
        });

        var keyHandler = function (evt) {
            if (evt.key === 'Escape') {
                evt.preventDefault();
                evt.stopPropagation();
                close(false);
            }
        };
        document.addEventListener('keydown', keyHandler, true);
        addCleanup(function () {
            document.removeEventListener('keydown', keyHandler, true);
        });

        buildRows();
        revealWhenStable(backdrop, search);
    }

    window.OnigiriMoveToDialog = {
        open: function (data) {
            close(true);
            if (window.OnigiriEngine) {
                OnigiriEngine._clearAllRowVisualStates();
                OnigiriEngine._beginOverrideState('dialog-focus');
                var sourceIds = data.source && Array.isArray(data.source.ids)
                    ? data.source.ids
                    : [data.source && data.source.id || ''];
                sourceIds.forEach(function (sourceId) {
                    sourceId = String(sourceId || '');
                    if (!sourceId) return;
                    var selectorId = typeof OnigiriEngine.escapeSelectorValue === 'function'
                        ? OnigiriEngine.escapeSelectorValue(sourceId)
                        : sourceId.replace(/["\\]/g, '\\$&');
                    var row = document.querySelector('tr.deck[data-did="' + selectorId + '"]');
                    if (row) row.classList.add('ctx-row-active');
                });
            }
            buildModal(data || {});
            if (typeof pycmd === 'function') pycmd('onigiri_ui_open');
        },
        close: close,
        showError: showError
    };
})();
