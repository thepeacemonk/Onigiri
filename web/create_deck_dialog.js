(function () {
    if (window.OnigiriCreateDeckDialog) return;

    var state = {
        destinations: [],
        selectedId: null,
        cleanupFns: [],
        preloadedIcons: [],
        rowById: {},
        hoverLayer: null,
        selectedLayer: null,
        hoverId: null,
        highlightRaf: 0,
        busy: false
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

    function getRowById(id) {
        if (id === null || id === undefined || !state.rowById) return null;
        return state.rowById[String(id)] || null;
    }

    function iconUrl(name) {
        if (window.OnigiriEngine && typeof OnigiriEngine.systemIconUrl === 'function') {
            return OnigiriEngine.systemIconUrl(name);
        }
        return '../system_files/system_icons/' + name;
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
                className: className || '',
                size: size || 16,
                color: color || 'currentColor'
            });
        }
        var fallback = document.createElement('span');
        fallback.className = className || '';
        return fallback;
    }

    function preloadCommonIcons() {
        var urls = ['create_deck.svg', 'cancel.svg', 'search.svg', 'deck.svg', 'subdeck.svg', 'folder.svg', 'filtered_deck.svg']
            .map(iconUrl)
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

    function ensureStyles() {
        if (document.getElementById('onigiri-create-deck-style')) return;

        var style = document.createElement('style');
        style.id = 'onigiri-create-deck-style';
        style.textContent = [
            '#onigiri-create-deck-backdrop{position:fixed;inset:0;z-index:200000;display:flex;align-items:center;justify-content:center;',
            '  background:rgba(0,0,0,0.58);contain:layout paint style;isolation:isolate;transform:translateZ(0);',
            '  backface-visibility:hidden;-webkit-backface-visibility:hidden;}',
            '#onigiri-create-deck-backdrop.is-preparing{visibility:hidden;}',
            '#onigiri-create-deck-backdrop *{box-sizing:border-box;}',
            '#onigiri-create-deck-backdrop button,#onigiri-create-deck-backdrop input{appearance:none;-webkit-appearance:none;',
            '  font-family:var(--font-main,-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif);}',
            '#onigiri-create-deck-backdrop button{border:none !important;outline:none !important;box-shadow:none !important;background-image:none !important;}',
            '.onigiri-create-deck-modal{width:540px;max-width:94vw;height:520px;max-height:88vh;display:flex;flex-direction:column;overflow:hidden;',
            '  border-radius:16px;border:1px solid var(--border,rgba(255,255,255,0.14));',
            '  background:var(--canvas-overlay,var(--canvas,#1e1e1e));color:var(--fg,#e8e8e8);',
            '  box-shadow:0 24px 70px rgba(0,0,0,0.42);',
            '  backface-visibility:hidden;-webkit-backface-visibility:hidden;transform:translateZ(0);contain:layout paint style;isolation:isolate;}',
            '.onigiri-create-deck-header{display:flex;align-items:flex-start;gap:12px;padding:18px 18px 14px;border-bottom:1px solid var(--border,rgba(255,255,255,0.12));}',
            '.onigiri-create-deck-header-icon{width:34px;height:34px;min-width:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;',
            '  color:var(--accent-color,#007aff);background:var(--highlight-bg,rgba(128,128,128,0.14));}',
            '.onigiri-create-deck-title-wrap{min-width:0;flex:1;}',
            '.onigiri-create-deck-title{font-size:16px;font-weight:700;line-height:1.2;margin:0 0 5px;color:var(--fg,#e8e8e8);}',
            '.onigiri-create-deck-subtitle{font-size:13px;color:var(--fg-subtle,#9a9a9a);line-height:1.35;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
            '.onigiri-create-deck-close{width:30px;height:30px;min-width:30px;padding:0;border:none !important;border-radius:8px;background:transparent !important;color:var(--fg-subtle,#999);',
            '  display:flex;align-items:center;justify-content:center;cursor:pointer;outline:none !important;box-shadow:none !important;filter:none !important;',
            '  opacity:0.72;transition:none;}',
            '.onigiri-create-deck-close:hover,.onigiri-create-deck-close:focus,.onigiri-create-deck-close:active{background:transparent !important;color:var(--fg,#e8e8e8);opacity:1;box-shadow:none !important;border:none !important;}',
            '.onigiri-create-deck-name-wrap{margin:14px 18px 10px;}',
            '.onigiri-create-deck-label{font-size:11px;font-weight:700;color:var(--fg-subtle,#999);margin:0 0 8px;text-transform:uppercase;}',
            '.onigiri-create-deck-input-wrap{position:relative;}',
            '.onigiri-create-deck-input{width:100%;height:40px;padding:0 13px;border-radius:999px;border:1px solid var(--border,rgba(255,255,255,0.14));',
            '  background:var(--canvas-inset,rgba(255,255,255,0.07));color:var(--fg,#e8e8e8);font-size:13px;outline:none;box-shadow:none;',
            '  transition:none;}',
            '.onigiri-create-deck-input::placeholder{color:var(--fg-subtle,#888);}',
            '.onigiri-create-deck-input:hover{background:var(--canvas-inset,rgba(255,255,255,0.07));}',
            '.onigiri-create-deck-input:focus{border-color:var(--accent-color,#007aff);}',
            '.onigiri-create-deck-parent-label{font-size:11px;font-weight:700;color:var(--fg-subtle,#999);margin:0 18px 8px;text-transform:uppercase;}',
            '.onigiri-create-deck-search-wrap{position:relative;margin:0 18px 10px;flex-shrink:0;}',
            '.onigiri-create-deck-search-icon{position:absolute;left:13px;top:50%;transform:translateY(-50%);color:var(--fg-subtle,#888);pointer-events:none;}',
            '.onigiri-create-deck-search{width:100%;height:38px;padding:0 13px 0 38px;border-radius:999px;border:1px solid var(--border,rgba(255,255,255,0.14));',
            '  background:var(--canvas-inset,rgba(255,255,255,0.07));color:var(--fg,#e8e8e8);font-size:13px;outline:none;box-shadow:none;',
            '  transition:none;}',
            '.onigiri-create-deck-search::placeholder{color:var(--fg-subtle,#888);}',
            '.onigiri-create-deck-search:hover{background:var(--canvas-inset,rgba(255,255,255,0.07));}',
            '.onigiri-create-deck-search:focus{border-color:var(--accent-color,#007aff);}',
            '.onigiri-create-deck-list{flex:1;min-height:0;margin:0 18px 12px;padding:5px;overflow:auto;border:1px solid var(--border,rgba(255,255,255,0.12));',
            '  border-radius:12px;background:var(--canvas,rgba(255,255,255,0.04));position:relative;contain:layout paint style;isolation:isolate;}',
            '.onigiri-create-deck-highlight{position:absolute;top:0;left:5px;right:5px;height:0;border-radius:9px;pointer-events:none;opacity:0;',
            '  transform:translate3d(0,0,0);will-change:transform,opacity,height;contain:paint;}',
            '.onigiri-create-deck-hover-layer{z-index:0;background:var(--canvas-inset,rgba(255,255,255,0.08));}',
            '.onigiri-create-deck-selected-layer{z-index:1;background:transparent;box-shadow:inset 0 0 0 2px var(--accent-color,#007aff);}',
            '.onigiri-create-deck-row{width:100%;display:flex;align-items:center;gap:11px;padding:10px;border-radius:9px;border:none;',
            '  color:var(--fg,#e8e8e8);cursor:pointer;user-select:none;background:transparent;position:relative;z-index:2;transition:none;}',
            '.onigiri-create-deck-row + .onigiri-create-deck-row{margin-top:3px;}',
            '.onigiri-create-deck-row.is-selected{color:var(--fg,#e8e8e8);}',
            '.onigiri-create-deck-row.is-selected .onigiri-create-deck-row-icon{color:var(--accent-color,#007aff);}',
            '.onigiri-create-deck-row.is-hidden{display:none;}',
            '.onigiri-create-deck-row-icon{width:28px;height:28px;min-width:28px;border-radius:8px;display:flex;align-items:center;justify-content:center;',
            '  color:var(--fg-subtle,#999);background:var(--canvas-inset,rgba(255,255,255,0.07));}',
            '.onigiri-create-deck-row-text{min-width:0;flex:1;}',
            '.onigiri-create-deck-row-name{font-size:13px;font-weight:650;line-height:1.25;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
            '.onigiri-create-deck-row-path{font-size:11px;color:var(--fg-subtle,#999);line-height:1.25;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
            '.onigiri-create-deck-empty{height:100%;min-height:160px;display:none;align-items:center;justify-content:center;text-align:center;',
            '  color:var(--fg-subtle,#999);font-size:13px;padding:20px;}',
            '.onigiri-create-deck-error{display:none;margin:0 18px 10px;padding:9px 11px;border-radius:9px;background:rgba(192,48,48,0.12);',
            '  color:#d84a4a;font-size:12px;line-height:1.35;}',
            '.onigiri-create-deck-footer{display:flex;align-items:center;gap:8px;padding:12px 18px 16px;border-top:1px solid var(--border,rgba(255,255,255,0.12));}',
            '.onigiri-create-deck-spacer{flex:1;}',
            '.onigiri-create-deck-btn{height:36px;padding:0 15px;border:none !important;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;gap:7px;',
            '  cursor:pointer;font-size:13px;font-weight:650;outline:none !important;box-shadow:none !important;background-image:none !important;',
            '  filter:none !important;transition:none;}',
            '.onigiri-create-deck-btn-secondary{background:var(--canvas-inset,rgba(255,255,255,0.08)) !important;color:var(--fg,#e8e8e8);}',
            '.onigiri-create-deck-btn-secondary:hover,.onigiri-create-deck-btn-secondary:focus,.onigiri-create-deck-btn-secondary:active{background:var(--canvas-inset,rgba(255,255,255,0.08)) !important;border:none !important;box-shadow:none !important;outline:none !important;}',
            '.onigiri-create-deck-btn-primary{background:var(--accent-color,#007aff) !important;color:#fff;}',
            '.onigiri-create-deck-btn-primary:hover,.onigiri-create-deck-btn-primary:focus,.onigiri-create-deck-btn-primary:active{background:var(--accent-color,#007aff) !important;border:none !important;box-shadow:none !important;outline:none !important;filter:none !important;}',
            '.onigiri-create-deck-btn:not(:disabled):hover{opacity:0.92;}',
            '.onigiri-create-deck-btn:not(:disabled):active{opacity:0.84;}',
            '.onigiri-create-deck-btn:disabled{opacity:0.42;cursor:not-allowed;filter:none !important;}',
            '.onigiri-create-deck-btn-primary:disabled{color:rgba(255,255,255,0.82) !important;-webkit-text-fill-color:rgba(255,255,255,0.82);}',
            '.onigiri-create-deck-btn:disabled:hover{filter:none !important;}',
            '.onigiri-create-deck-list::-webkit-scrollbar{width:10px;background:transparent;}',
            '.onigiri-create-deck-list::-webkit-scrollbar-thumb{background:rgba(128,128,128,0.38);border-radius:999px;border:2px solid transparent;background-clip:content-box;}',
            '.onigiri-create-deck-list::-webkit-scrollbar-track{background:transparent;}'
        ].join('');
        document.head.appendChild(style);
    }

    function warmDialogSurface() {
        if (document.getElementById('onigiri-create-deck-warmup')) return;
        var warmup = document.createElement('div');
        warmup.id = 'onigiri-create-deck-warmup';
        warmup.setAttribute('aria-hidden', 'true');
        warmup.style.cssText = 'position:fixed;left:-10000px;top:-10000px;width:540px;height:520px;visibility:hidden;pointer-events:none;contain:layout paint style;overflow:hidden;';

        var modal = document.createElement('div');
        modal.className = 'onigiri-create-deck-modal';
        var search = document.createElement('input');
        search.className = 'onigiri-create-deck-search';
        var list = document.createElement('div');
        list.className = 'onigiri-create-deck-list';
        var row = document.createElement('div');
        row.className = 'onigiri-create-deck-row is-selected';
        list.appendChild(row);
        var footer = document.createElement('div');
        footer.className = 'onigiri-create-deck-footer';
        var secondary = document.createElement('button');
        secondary.className = 'onigiri-create-deck-btn onigiri-create-deck-btn-secondary';
        secondary.textContent = 'Cancel';
        var primary = document.createElement('button');
        primary.className = 'onigiri-create-deck-btn onigiri-create-deck-btn-primary';
        primary.textContent = 'Create';
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

    function close(skipUiClose) {
        var backdrop = document.getElementById('onigiri-create-deck-backdrop');
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

        state.destinations = [];
        state.selectedId = null;
        state.rowById = {};
        state.hoverLayer = null;
        state.selectedLayer = null;
        state.preloadedIcons = [];
        state.hoverId = null;
        state.busy = false;
        if (state.highlightRaf) {
            cancelAnimationFrame(state.highlightRaf);
            state.highlightRaf = 0;
        }

        if (!skipUiClose && backdrop && typeof pycmd === 'function') {
            pycmd('onigiri_ui_close');
        }
    }

    function revealWhenStable(backdrop, focusTarget) {
        if (!backdrop) return;
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

    function destinationMatches(dest, query) {
        if (!query) return true;
        var haystack = [
            dest.name || '',
            dest.path || ''
        ].join(' ').toLowerCase();
        return haystack.indexOf(query) !== -1;
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
        if (hoverRow && state.hoverId === state.selectedId) hoverRow = null;
        positionHighlight(state.selectedLayer, selectedRow);
        positionHighlight(state.hoverLayer, hoverRow);
    }

    function queueHighlightUpdate() {
        if (state.highlightRaf) return;
        state.highlightRaf = requestAnimationFrame(updateHighlights);
    }

    function updateConfirmState() {
        var createBtn = document.getElementById('onigiri-create-deck-create');
        if (!createBtn) return;
        var input = document.getElementById('onigiri-create-deck-input');
        createBtn.disabled = !input || !input.value.trim();
    }

    function selectDestination(destinationId) {
        state.selectedId = destinationId === null || destinationId === undefined
            ? null
            : String(destinationId);

        Object.keys(state.rowById || {}).forEach(function (id) {
            state.rowById[id].classList.toggle('is-selected', id === state.selectedId);
        });

        var err = document.getElementById('onigiri-create-deck-error');
        if (err) err.style.display = 'none';
        updateConfirmState();
        queueHighlightUpdate();
    }

    function buildRows() {
        var list = document.getElementById('onigiri-create-deck-list');
        var empty = document.getElementById('onigiri-create-deck-empty');
        if (!list || !empty) return;

        list.innerHTML = '';
        state.rowById = {};

        state.hoverLayer = document.createElement('div');
        state.hoverLayer.className = 'onigiri-create-deck-highlight onigiri-create-deck-hover-layer';
        state.selectedLayer = document.createElement('div');
        state.selectedLayer.className = 'onigiri-create-deck-highlight onigiri-create-deck-selected-layer';
        list.appendChild(state.hoverLayer);
        list.appendChild(state.selectedLayer);

        state.destinations.forEach(function (dest) {
            var row = document.createElement('div');
            row.className = 'onigiri-create-deck-row';
            row.dataset.destinationId = String(dest.id);

            var iconWrap = document.createElement('div');
            iconWrap.className = 'onigiri-create-deck-row-icon';
            iconWrap.appendChild(makeIcon(dest.iconUrl || (dest.kind === 'root' ? 'folder.svg' : 'deck.svg'), 'onigiri-create-deck-row-svg', 15, 'currentColor'));
            row.appendChild(iconWrap);

            var text = document.createElement('div');
            text.className = 'onigiri-create-deck-row-text';
            var name = document.createElement('div');
            name.className = 'onigiri-create-deck-row-name';
            name.textContent = dest.name || dest.path || 'Untitled deck';
            text.appendChild(name);

            var path = document.createElement('div');
            path.className = 'onigiri-create-deck-row-path';
            path.textContent = dest.kind === 'root' ? 'Create as a top-level deck' : (dest.path || dest.name || '');
            text.appendChild(path);
            row.appendChild(text);

            row.addEventListener('click', function () {
                selectDestination(dest.id);
            });

            state.rowById[String(dest.id)] = row;
            list.appendChild(row);
        });

        list.appendChild(empty);
        applyFilter();
    }

    function applyFilter() {
        var empty = document.getElementById('onigiri-create-deck-empty');
        var search = document.getElementById('onigiri-create-deck-search');
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
            var hoverRow = state.rowById && state.rowById[String(state.hoverId)];
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
        var error = document.getElementById('onigiri-create-deck-error');
        if (error) {
            error.textContent = message || 'Could not create deck.';
            error.style.display = 'block';
        }
        updateConfirmState();
    }

    function submit() {
        if (state.busy) return;
        var input = document.getElementById('onigiri-create-deck-input');
        if (!input) return;
        var name = input.value.trim();
        if (!name) {
            showError('Enter a deck name.');
            return;
        }
        state.busy = true;
        updateConfirmState();
        var payload = {
            name: name,
            parentDid: state.selectedId
        };
        if (typeof pycmd === 'function') {
            pycmd('onigiri_create_deck_submit:' + encodeURIComponent(JSON.stringify(payload)));
        }
    }

    function buildModal(data) {
        state.destinations = Array.isArray(data.destinations) ? data.destinations : [];
        state.selectedId = state.destinations.length ? String(state.destinations[0].id) : null;
        state.cleanupFns = [];
        state.hoverId = null;
        state.highlightRaf = 0;
        state.busy = false;

        var backdrop = document.createElement('div');
        backdrop.id = 'onigiri-create-deck-backdrop';
        backdrop.className = 'is-preparing';

        var modal = document.createElement('div');
        modal.className = 'onigiri-create-deck-modal';
        modal.addEventListener('click', function (evt) { evt.stopPropagation(); });
        modal.addEventListener('pointerdown', function (evt) { evt.stopPropagation(); });

        var header = document.createElement('div');
        header.className = 'onigiri-create-deck-header';

        var headerIcon = document.createElement('div');
        headerIcon.className = 'onigiri-create-deck-header-icon';
        headerIcon.appendChild(makeIcon('create_deck.svg', 'onigiri-create-deck-header-svg', 18, 'currentColor'));
        header.appendChild(headerIcon);

        var titleWrap = document.createElement('div');
        titleWrap.className = 'onigiri-create-deck-title-wrap';
        var title = document.createElement('div');
        title.className = 'onigiri-create-deck-title';
        title.textContent = 'Create New Deck';
        titleWrap.appendChild(title);

        var subtitle = document.createElement('div');
        subtitle.className = 'onigiri-create-deck-subtitle';
        subtitle.textContent = 'Choose a name and optional parent deck';
        titleWrap.appendChild(subtitle);
        header.appendChild(titleWrap);

        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'onigiri-create-deck-close';
        closeBtn.title = 'Close';
        closeBtn.appendChild(makeIcon('cancel.svg', 'onigiri-create-deck-close-svg', 14, 'currentColor'));
        closeBtn.addEventListener('click', function () { close(false); });
        header.appendChild(closeBtn);
        modal.appendChild(header);

        var nameWrap = document.createElement('div');
        nameWrap.className = 'onigiri-create-deck-name-wrap';
        var nameLabel = document.createElement('div');
        nameLabel.className = 'onigiri-create-deck-label';
        nameLabel.textContent = 'Deck name';
        nameWrap.appendChild(nameLabel);

        var inputWrap = document.createElement('div');
        inputWrap.className = 'onigiri-create-deck-input-wrap';
        var input = document.createElement('input');
        input.id = 'onigiri-create-deck-input';
        input.className = 'onigiri-create-deck-input';
        input.type = 'text';
        input.autocomplete = 'off';
        input.spellcheck = false;
        input.placeholder = 'e.g. Biology';
        input.addEventListener('input', function () {
            showError('');
            updateConfirmState();
        });
        input.addEventListener('keydown', function (evt) {
            if (evt.key === 'Enter') {
                evt.preventDefault();
                submit();
            }
        });
        inputWrap.appendChild(input);
        nameWrap.appendChild(inputWrap);
        modal.appendChild(nameWrap);

        var parentLabel = document.createElement('div');
        parentLabel.className = 'onigiri-create-deck-parent-label';
        parentLabel.textContent = 'Parent deck';
        modal.appendChild(parentLabel);

        var searchWrap = document.createElement('div');
        searchWrap.className = 'onigiri-create-deck-search-wrap';
        searchWrap.appendChild(makeIcon('search.svg', 'onigiri-create-deck-search-icon', 15, 'currentColor'));
        var search = document.createElement('input');
        search.id = 'onigiri-create-deck-search';
        search.className = 'onigiri-create-deck-search';
        search.type = 'text';
        search.placeholder = 'Search decks';
        search.autocomplete = 'off';
        search.spellcheck = false;
        search.addEventListener('input', applyFilter);
        searchWrap.appendChild(search);
        modal.appendChild(searchWrap);

        var list = document.createElement('div');
        list.id = 'onigiri-create-deck-list';
        list.className = 'onigiri-create-deck-list';
        var onListPointerOver = function (evt) {
            var row = evt.target && evt.target.closest ? evt.target.closest('.onigiri-create-deck-row') : null;
            if (!row || row.parentElement !== list) {
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
        empty.id = 'onigiri-create-deck-empty';
        empty.className = 'onigiri-create-deck-empty';
        empty.textContent = 'No matching decks found';
        list.appendChild(empty);
        modal.appendChild(list);

        var error = document.createElement('div');
        error.id = 'onigiri-create-deck-error';
        error.className = 'onigiri-create-deck-error';
        modal.appendChild(error);

        var footer = document.createElement('div');
        footer.className = 'onigiri-create-deck-footer';
        var spacer = document.createElement('div');
        spacer.className = 'onigiri-create-deck-spacer';

        var cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'onigiri-create-deck-btn onigiri-create-deck-btn-secondary';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.addEventListener('click', function () { close(false); });

        var createBtn = document.createElement('button');
        createBtn.type = 'button';
        createBtn.id = 'onigiri-create-deck-create';
        createBtn.className = 'onigiri-create-deck-btn onigiri-create-deck-btn-primary';
        createBtn.disabled = true;
        createBtn.textContent = 'Create';
        createBtn.addEventListener('click', submit);

        footer.appendChild(spacer);
        footer.appendChild(cancelBtn);
        footer.appendChild(createBtn);
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
        revealWhenStable(backdrop, input);
    }

    window.OnigiriCreateDeckDialog = {
        open: function (data) {
            close(true);
            if (window.OnigiriEngine) {
                OnigiriEngine._clearAllRowVisualStates();
                OnigiriEngine._beginOverrideState('dialog-focus');
            }
            buildModal(data || {});
            if (typeof pycmd === 'function') pycmd('onigiri_ui_open');
        },
        close: close,
        showError: showError
    };
})();
