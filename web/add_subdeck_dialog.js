(function () {
    if (window.OnigiriAddSubdeckDialog) return;

    var state = {
        deckId: null,
        parentName: '',
        cleanupFns: []
    };

    function T(key, fallback) {
        if (window.OnigiriI18n && typeof OnigiriI18n.t === 'function') {
            return OnigiriI18n.t(key, fallback);
        }
        return fallback;
    }

    function addCleanup(fn) {
        state.cleanupFns.push(fn);
    }

    function runCleanup() {
        while (state.cleanupFns.length) {
            var fn = state.cleanupFns.pop();
            try { fn(); } catch (_) {}
        }
    }

    function iconUrl(name) {
        if (window.OnigiriEngine && typeof OnigiriEngine.systemIconUrl === 'function') {
            return OnigiriEngine.systemIconUrl(name);
        }
        return '../system_files/system_icons/unavailable_for_users/' + name;
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
        var urls = ['add_subdeck.svg', 'cancel.svg'].map(iconUrl);
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

    // Shared light/dark tokens for Onigiri dialogs. They read the Onigiri palette
    // (which flips on .night-mode) instead of Anki's --canvas*, so a dialog can
    // never end up with light-theme surfaces under dark-theme text.
    function ensureDialogThemeTokens() {
        if (document.getElementById('onigiri-dialog-theme-tokens')) return;
        var tokenStyle = document.createElement('style');
        tokenStyle.id = 'onigiri-dialog-theme-tokens';
        tokenStyle.textContent = [
            ':root{--odlg-surface:#ffffff;--odlg-inset:#ffffff;',
            '  --odlg-fg:#202124;--odlg-fg-subtle:#6f7177;',
            '  --odlg-border:#dcdde1;--odlg-highlight:#f2f2f2;--odlg-hover:#e9e9e9;',
            '  --odlg-accent:var(--accent-color,#0077C8);--odlg-scrim:rgba(0,0,0,0.45);}',
            '.night-mode,.nightMode{--odlg-surface:#242424;--odlg-inset:#242424;',
            '  --odlg-fg:#f4f4f5;--odlg-fg-subtle:#c4c4c4;',
            '  --odlg-border:#454545;--odlg-highlight:#303030;--odlg-hover:#3a3a3a;',
            '  --odlg-accent:var(--accent-color,#0077C8);--odlg-scrim:rgba(0,0,0,0.62);}'
        ].join('');
        (document.head || document.documentElement).appendChild(tokenStyle);
    }

    function ensureStyles() {
        ensureDialogThemeTokens();
        if (document.getElementById('onigiri-add-subdeck-style')) return;
        var style = document.createElement('style');
        style.id = 'onigiri-add-subdeck-style';
        style.textContent = [
            '#onigiri-add-subdeck-backdrop{position:fixed;inset:0;z-index:200000;display:flex;align-items:center;justify-content:center;',
            '  background:var(--odlg-scrim, rgba(0,0,0,0.58));contain:layout paint style;isolation:isolate;transform:translateZ(0);',
            '  backface-visibility:hidden;-webkit-backface-visibility:hidden;}',
            '#onigiri-add-subdeck-backdrop.is-preparing{visibility:hidden;}',
            '#onigiri-add-subdeck-backdrop *{box-sizing:border-box;}',
            '#onigiri-add-subdeck-backdrop button,#onigiri-add-subdeck-backdrop input{appearance:none;-webkit-appearance:none;',
            '  font-family:var(--font-main,-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif);}',
            '#onigiri-add-subdeck-backdrop button{border:none !important;outline:none !important;box-shadow:none !important;background-image:none !important;}',
            '.onigiri-add-subdeck-modal{width:460px;max-width:94vw;display:flex;flex-direction:column;overflow:hidden;',
            '  border-radius:16px;border:1px solid var(--odlg-border, rgba(0,0,0,0.14));',
            '  background:var(--odlg-surface, #ffffff);color:var(--odlg-fg, #212121);',
            '  box-shadow:0 24px 70px rgba(0,0,0,0.42);backface-visibility:hidden;-webkit-backface-visibility:hidden;',
            '  transform:translateZ(0);contain:layout paint style;isolation:isolate;}',
            '.onigiri-add-subdeck-header{display:flex;align-items:flex-start;gap:12px;padding:18px 18px 14px;border-bottom:1px solid var(--odlg-border, rgba(0,0,0,0.14));}',
            '.onigiri-add-subdeck-header-icon{width:34px;height:34px;min-width:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;',
            '  color:var(--odlg-accent, #0077C8);background:var(--odlg-highlight, rgba(0,0,0,0.06));}',
            '.onigiri-add-subdeck-title-wrap{min-width:0;flex:1;}',
            '.onigiri-add-subdeck-title{font-size:16px;font-weight:700;line-height:1.2;margin:0 0 5px;color:var(--odlg-fg, #212121);}',
            '.onigiri-add-subdeck-subtitle{font-size:13px;color:var(--odlg-fg-subtle, #757575);line-height:1.35;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
            '.onigiri-add-subdeck-close{width:30px;height:30px;min-width:30px;padding:0;border:none !important;border-radius:8px;background:transparent !important;color:var(--odlg-fg-subtle, #757575);',
            '  display:flex;align-items:center;justify-content:center;cursor:pointer;outline:none !important;box-shadow:none !important;filter:none !important;',
            '  opacity:0.72;transition:none;}',
            '.onigiri-add-subdeck-close:hover,.onigiri-add-subdeck-close:focus,.onigiri-add-subdeck-close:active{background:transparent !important;color:var(--odlg-fg, #212121);opacity:1;box-shadow:none !important;border:none !important;}',
            '.onigiri-add-subdeck-body{padding:16px 18px 12px;}',
            '.onigiri-add-subdeck-label{font-size:11px;font-weight:700;color:var(--odlg-fg-subtle, #757575);margin:0 0 8px;text-transform:uppercase;}',
            '.onigiri-add-subdeck-input-wrap{position:relative;}',
            '.onigiri-add-subdeck-input{width:100%;height:40px;padding:0 13px;border-radius:999px;border:1px solid var(--odlg-border, rgba(0,0,0,0.14));',
            '  background:var(--odlg-inset, #ffffff);color:var(--odlg-fg, #212121);font-size:13px;outline:none;box-shadow:none;',
            '  transition:none;}',
            '.onigiri-add-subdeck-input::placeholder{color:var(--odlg-fg-subtle, #757575);}',
            '.onigiri-add-subdeck-input:hover{background:var(--odlg-inset, #ffffff);}',
            '.onigiri-add-subdeck-input:focus{border-color:var(--odlg-accent, #0077C8);}',
            '.onigiri-add-subdeck-hint{font-size:12px;color:var(--odlg-fg-subtle, #757575);line-height:1.35;margin-top:9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
            '.onigiri-add-subdeck-error{display:none;margin:0 18px 10px;padding:9px 11px;border-radius:9px;background:rgba(192,48,48,0.12);',
            '  color:#d84a4a;font-size:12px;line-height:1.35;}',
            '.onigiri-add-subdeck-footer{display:flex;align-items:center;gap:8px;padding:12px 18px 16px;border-top:1px solid var(--odlg-border, rgba(0,0,0,0.14));}',
            '.onigiri-add-subdeck-spacer{flex:1;}',
            '.onigiri-add-subdeck-btn{height:36px;padding:0 15px;border:none !important;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;gap:7px;',
            '  cursor:pointer;font-size:13px;font-weight:650;outline:none !important;box-shadow:none !important;background-image:none !important;filter:none !important;',
            '  transition:none;}',
            '.onigiri-add-subdeck-btn-secondary{background:var(--odlg-inset, #ffffff) !important;color:var(--odlg-fg, #212121);}',
            '.onigiri-add-subdeck-btn-secondary:hover,.onigiri-add-subdeck-btn-secondary:focus,.onigiri-add-subdeck-btn-secondary:active{background:var(--odlg-inset, #ffffff) !important;border:none !important;box-shadow:none !important;outline:none !important;filter:none !important;}',
            '.onigiri-add-subdeck-btn-primary{background:var(--odlg-accent, #0077C8) !important;color:#fff;}',
            '.onigiri-add-subdeck-btn-primary:hover,.onigiri-add-subdeck-btn-primary:focus,.onigiri-add-subdeck-btn-primary:active{background:var(--odlg-accent, #0077C8) !important;border:none !important;box-shadow:none !important;outline:none !important;filter:none !important;}',
            '.onigiri-add-subdeck-btn:not(:disabled):hover{opacity:0.92;}',
            '.onigiri-add-subdeck-btn:not(:disabled):active{opacity:0.84;}',
            '.onigiri-add-subdeck-btn:disabled{opacity:0.42;cursor:not-allowed;filter:none !important;}',
            '.onigiri-add-subdeck-btn-primary:disabled{color:rgba(255,255,255,0.82) !important;-webkit-text-fill-color:rgba(255,255,255,0.82);}',
            '.onigiri-add-subdeck-btn:disabled:hover{filter:none !important;}'
        ].join('');
        document.head.appendChild(style);
    }

    function warmDialogSurface() {
        if (document.getElementById('onigiri-add-subdeck-warmup')) return;
        var warmup = document.createElement('div');
        warmup.id = 'onigiri-add-subdeck-warmup';
        warmup.setAttribute('aria-hidden', 'true');
        warmup.style.cssText = 'position:fixed;left:-10000px;top:-10000px;width:460px;height:240px;visibility:hidden;pointer-events:none;contain:layout paint style;overflow:hidden;';

        var modal = document.createElement('div');
        modal.className = 'onigiri-add-subdeck-modal';
        var input = document.createElement('input');
        input.className = 'onigiri-add-subdeck-input';
        var footer = document.createElement('div');
        footer.className = 'onigiri-add-subdeck-footer';
        var secondary = document.createElement('span');
        secondary.className = 'onigiri-add-subdeck-btn onigiri-add-subdeck-btn-secondary';
        secondary.textContent = T('cancel', 'Cancel');
        var primary = document.createElement('span');
        primary.className = 'onigiri-add-subdeck-btn onigiri-add-subdeck-btn-primary';
        primary.textContent = T('create_action', 'Create');
        footer.appendChild(secondary);
        footer.appendChild(primary);
        modal.appendChild(input);
        modal.appendChild(footer);
        warmup.appendChild(modal);
        (document.body || document.documentElement).appendChild(warmup);
        warmup.getBoundingClientRect();
    }

    ensureStyles();
    state.preloadedIcons = preloadCommonIcons();
    warmDialogSurface();

    function close(skipUiClose) {
        var backdrop = document.getElementById('onigiri-add-subdeck-backdrop');
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

        state.deckId = null;
        state.parentName = '';

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
                focusTarget.select();
            });
        });
    }

    function setError(message) {
        var error = document.getElementById('onigiri-add-subdeck-error');
        if (!error) return;
        if (!message) {
            error.style.display = 'none';
            error.textContent = '';
            return;
        }
        error.textContent = message;
        error.style.display = 'block';
    }

    function updateConfirmState() {
        var input = document.getElementById('onigiri-add-subdeck-input');
        var createBtn = document.getElementById('onigiri-add-subdeck-create');
        if (createBtn) createBtn.disabled = !input || !input.value.trim();
    }

    function submit() {
        var input = document.getElementById('onigiri-add-subdeck-input');
        if (!input) return;
        var name = input.value.trim();
        if (!name) {
            setError('Enter a subdeck name.');
            updateConfirmState();
            return;
        }
        var payload = {
            deckId: state.deckId,
            name: name
        };
        if (typeof pycmd === 'function') {
            pycmd('onigiri_create_subdeck:' + encodeURIComponent(JSON.stringify(payload)));
        }
    }

    function buildDialog(data) {
        ensureStyles();
        if (window.OnigiriEngine && typeof OnigiriEngine.preloadMaskIcons === 'function') {
            OnigiriEngine.preloadMaskIcons([iconUrl('add_subdeck.svg'), iconUrl('cancel.svg')]);
        }

        state.deckId = data.deckId;
        state.parentName = data.parentName || '';
        state.cleanupFns = [];

        var backdrop = document.createElement('div');
        backdrop.id = 'onigiri-add-subdeck-backdrop';
        backdrop.className = 'is-preparing';

        var modal = document.createElement('div');
        modal.className = 'onigiri-add-subdeck-modal';
        modal.addEventListener('click', function (evt) { evt.stopPropagation(); });
        modal.addEventListener('pointerdown', function (evt) { evt.stopPropagation(); });

        var header = document.createElement('div');
        header.className = 'onigiri-add-subdeck-header';
        var headerIcon = document.createElement('div');
        headerIcon.className = 'onigiri-add-subdeck-header-icon';
        headerIcon.appendChild(makeIcon('add_subdeck.svg', 'onigiri-add-subdeck-header-svg', 18));
        header.appendChild(headerIcon);

        var titleWrap = document.createElement('div');
        titleWrap.className = 'onigiri-add-subdeck-title-wrap';
        var title = document.createElement('div');
        title.className = 'onigiri-add-subdeck-title';
        title.textContent = T('add_subdeck_title', 'Add Subdeck');
        titleWrap.appendChild(title);
        var subtitle = document.createElement('div');
        subtitle.className = 'onigiri-add-subdeck-subtitle';
        subtitle.title = state.parentName;
        subtitle.textContent = state.parentName || 'Selected deck';
        titleWrap.appendChild(subtitle);
        header.appendChild(titleWrap);

        var closeBtn = document.createElement('span');
        closeBtn.setAttribute('role', 'button');
        closeBtn.tabIndex = 0;
        // Set tabindex for accessibility
        try { arguments[0].tabIndex = 0; } catch(e){};
        closeBtn.className = 'onigiri-add-subdeck-close';
        closeBtn.title = T('close', 'Close');
        closeBtn.appendChild(makeIcon('cancel.svg', 'onigiri-add-subdeck-close-svg', 14));
        closeBtn.addEventListener('click', function () { close(false); });
        header.appendChild(closeBtn);
        modal.appendChild(header);

        var body = document.createElement('div');
        body.className = 'onigiri-add-subdeck-body';
        var label = document.createElement('div');
        label.className = 'onigiri-add-subdeck-label';
        label.textContent = T('subdeck_name_label', 'Subdeck name');
        body.appendChild(label);

        var inputWrap = document.createElement('div');
        inputWrap.className = 'onigiri-add-subdeck-input-wrap';
        var input = document.createElement('input');
        input.id = 'onigiri-add-subdeck-input';
        input.className = 'onigiri-add-subdeck-input';
        input.type = 'text';
        input.autocomplete = 'off';
        input.spellcheck = false;
        input.placeholder = T('subdeck_name_placeholder', 'e.g. Chapter 1');
        input.addEventListener('input', function () {
            setError('');
            updateConfirmState();
        });
        input.addEventListener('keydown', function (evt) {
            if (evt.key === 'Enter') {
                evt.preventDefault();
                submit();
            }
        });
        inputWrap.appendChild(input);
        body.appendChild(inputWrap);

        var hint = document.createElement('div');
        hint.className = 'onigiri-add-subdeck-hint';
        hint.textContent = state.parentName ? ('Will be created inside ' + state.parentName) : '';
        body.appendChild(hint);
        modal.appendChild(body);

        var error = document.createElement('div');
        error.id = 'onigiri-add-subdeck-error';
        error.className = 'onigiri-add-subdeck-error';
        modal.appendChild(error);

        var footer = document.createElement('div');
        footer.className = 'onigiri-add-subdeck-footer';
        var spacer = document.createElement('div');
        spacer.className = 'onigiri-add-subdeck-spacer';
        var cancelBtn = document.createElement('span');
        cancelBtn.setAttribute('role', 'button');
        cancelBtn.tabIndex = 0;
        // Set tabindex for accessibility
        try { arguments[0].tabIndex = 0; } catch(e){};
        cancelBtn.className = 'onigiri-add-subdeck-btn onigiri-add-subdeck-btn-secondary';
        cancelBtn.textContent = T('cancel', 'Cancel');
        cancelBtn.addEventListener('click', function () { close(false); });
        var createBtn = document.createElement('span');
        createBtn.setAttribute('role', 'button');
        createBtn.tabIndex = 0;
        // Set tabindex for accessibility
        try { arguments[0].tabIndex = 0; } catch(e){};
        createBtn.id = 'onigiri-add-subdeck-create';
        createBtn.className = 'onigiri-add-subdeck-btn onigiri-add-subdeck-btn-primary';
        createBtn.disabled = true;
        createBtn.textContent = T('create_action', 'Create');
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

        revealWhenStable(backdrop, input);
    }

    window.OnigiriAddSubdeckDialog = {
        open: function (data) {
            close(true);
            if (window.OnigiriEngine) {
                OnigiriEngine._clearAllRowVisualStates();
                OnigiriEngine._beginOverrideState('dialog-focus');
                var deckId = String(data && data.deckId || '');
                var selectorId = typeof OnigiriEngine.escapeSelectorValue === 'function'
                    ? OnigiriEngine.escapeSelectorValue(deckId)
                    : deckId.replace(/["\\]/g, '\\$&');
                var row = document.querySelector('tr.deck[data-did="' + selectorId + '"]');
                if (row) row.classList.add('ctx-row-active');
            }
            buildDialog(data || {});
            if (typeof pycmd === 'function') pycmd('onigiri_ui_open');
        },
        close: close,
        showError: setError
    };
})();
