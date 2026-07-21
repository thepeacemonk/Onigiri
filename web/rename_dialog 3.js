(function () {
    if (window.OnigiriRenameDialog) return;

    var state = {
        deckId: null,
        leafName: '',
        fullName: '',
        parentPrefix: '',
        fullPath: false,
        cleanupFns: []
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
        var urls = ['rename.svg', 'cancel.svg'].map(iconUrl);
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
        if (document.getElementById('onigiri-rename-dialog-style')) return;
        var style = document.createElement('style');
        style.id = 'onigiri-rename-dialog-style';
        style.textContent = [
            '#onigiri-rename-backdrop{position:fixed;inset:0;z-index:200000;display:flex;align-items:center;justify-content:center;',
            '  background:var(--odlg-scrim, rgba(0,0,0,0.58));contain:layout paint style;isolation:isolate;transform:translateZ(0);',
            '  backface-visibility:hidden;-webkit-backface-visibility:hidden;}',
            '#onigiri-rename-backdrop.is-preparing{visibility:hidden;}',
            '#onigiri-rename-backdrop *{box-sizing:border-box;}',
            '#onigiri-rename-backdrop button,#onigiri-rename-backdrop input{appearance:none;-webkit-appearance:none;',
            '  font-family:var(--font-main,-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif);}',
            '#onigiri-rename-backdrop button{border:none !important;outline:none !important;box-shadow:none !important;background-image:none !important;}',
            '.onigiri-rename-modal{width:460px;max-width:94vw;display:flex;flex-direction:column;overflow:hidden;',
            '  border-radius:16px;border:1px solid var(--odlg-border, rgba(0,0,0,0.14));',
            '  background:var(--odlg-surface, #ffffff);color:var(--odlg-fg, #212121);',
            '  box-shadow:0 24px 70px rgba(0,0,0,0.42);backface-visibility:hidden;-webkit-backface-visibility:hidden;',
            '  transform:translateZ(0);contain:layout paint style;isolation:isolate;}',
            '.onigiri-rename-header{display:flex;align-items:flex-start;gap:12px;padding:18px 18px 14px;border-bottom:1px solid var(--odlg-border, rgba(0,0,0,0.14));}',
            '.onigiri-rename-header-icon{width:34px;height:34px;min-width:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;',
            '  color:var(--odlg-accent, #0077C8);background:var(--odlg-highlight, rgba(0,0,0,0.06));}',
            '.onigiri-rename-title-wrap{min-width:0;flex:1;}',
            '.onigiri-rename-title{font-size:16px;font-weight:700;line-height:1.2;margin:0 0 5px;color:var(--odlg-fg, #212121);}',
            '.onigiri-rename-subtitle{font-size:13px;color:var(--odlg-fg-subtle, #757575);line-height:1.35;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
            '.onigiri-rename-close{width:30px;height:30px;min-width:30px;padding:0;border:none !important;border-radius:8px;background:transparent !important;color:var(--odlg-fg-subtle, #757575);',
            '  display:flex;align-items:center;justify-content:center;cursor:pointer;outline:none !important;box-shadow:none !important;filter:none !important;',
            '  opacity:1;transition:none;}',
            '.onigiri-rename-close:hover,.onigiri-rename-close:focus,.onigiri-rename-close:active{background:transparent !important;color:var(--odlg-fg-subtle, #757575);opacity:1;box-shadow:none !important;border:none !important;filter:none !important;}',
            '.onigiri-rename-body{padding:16px 18px 12px;}',
            '.onigiri-rename-label{font-size:11px;font-weight:700;color:var(--odlg-fg-subtle, #757575);margin:0 0 8px;text-transform:uppercase;}',
            '.onigiri-rename-input-wrap{position:relative;}',
            '.onigiri-rename-input{width:100%;height:40px;padding:0 13px;border-radius:999px;border:1px solid var(--odlg-border, rgba(0,0,0,0.14));',
            '  background:var(--odlg-inset, #ffffff);color:var(--odlg-fg, #212121);font-size:13px;outline:none;box-shadow:none;',
            '  transition:none;}',
            '.onigiri-rename-input::placeholder{color:var(--odlg-fg-subtle, #757575);}',
            '.onigiri-rename-input:hover{background:var(--odlg-inset, #ffffff);}',
            '.onigiri-rename-input:focus{border-color:var(--odlg-accent, #0077C8);}',
            '.onigiri-rename-hint{font-size:12px;color:var(--odlg-fg-subtle, #757575);line-height:1.35;margin-top:9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
            '.onigiri-rename-error{display:none;margin:0 18px 10px;padding:9px 11px;border-radius:9px;background:rgba(192,48,48,0.12);',
            '  color:#d84a4a;font-size:12px;line-height:1.35;}',
            '.onigiri-rename-footer{display:flex;align-items:center;gap:8px;padding:12px 18px 16px;border-top:1px solid var(--odlg-border, rgba(0,0,0,0.14));}',
            '.onigiri-rename-spacer{flex:1;}',
            '.onigiri-rename-btn{height:36px;padding:0 15px;border:none !important;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;gap:7px;',
            '  cursor:pointer;font-size:13px;font-weight:650;outline:none !important;box-shadow:none !important;background-image:none !important;filter:none !important;',
            '  transition:none;}',
            '.onigiri-rename-btn-secondary{background:var(--odlg-inset, #ffffff) !important;color:var(--odlg-fg, #212121);}',
            '.onigiri-rename-btn-secondary:hover,.onigiri-rename-btn-secondary:focus,.onigiri-rename-btn-secondary:active{background:var(--odlg-inset, #ffffff) !important;border:none !important;box-shadow:none !important;outline:none !important;filter:none !important;}',
            '.onigiri-rename-btn-secondary.is-active{background:var(--odlg-accent, #0077C8) !important;color:#fff;}',
            '.onigiri-rename-btn-primary{background:var(--odlg-accent, #0077C8) !important;color:#fff;}',
            '.onigiri-rename-btn-primary:hover,.onigiri-rename-btn-primary:focus,.onigiri-rename-btn-primary:active{background:var(--odlg-accent, #0077C8) !important;border:none !important;box-shadow:none !important;outline:none !important;filter:none !important;}',
            '.onigiri-rename-btn:not(:disabled):hover{opacity:1;}',
            '.onigiri-rename-btn:not(:disabled):active{opacity:1;}',
            '.onigiri-rename-btn:disabled{opacity:0.42;cursor:not-allowed;filter:none !important;}',
            '.onigiri-rename-btn-primary:disabled{color:rgba(255,255,255,0.82) !important;-webkit-text-fill-color:rgba(255,255,255,0.82);}',
            '.onigiri-rename-btn:disabled:hover{filter:none !important;}'
        ].join('');
        document.head.appendChild(style);
    }

    function warmDialogSurface() {
        if (document.getElementById('onigiri-rename-warmup')) return;
        var warmup = document.createElement('div');
        warmup.id = 'onigiri-rename-warmup';
        warmup.setAttribute('aria-hidden', 'true');
        warmup.style.cssText = 'position:fixed;left:-10000px;top:-10000px;width:460px;height:240px;visibility:hidden;pointer-events:none;contain:layout paint style;overflow:hidden;';

        var modal = document.createElement('div');
        modal.className = 'onigiri-rename-modal';
        var input = document.createElement('input');
        input.className = 'onigiri-rename-input';
        var footer = document.createElement('div');
        footer.className = 'onigiri-rename-footer';
        var secondary = document.createElement('span');
        secondary.className = 'onigiri-rename-btn onigiri-rename-btn-secondary';
        secondary.textContent = 'Cancel';
        var primary = document.createElement('span');
        primary.className = 'onigiri-rename-btn onigiri-rename-btn-primary';
        primary.textContent = 'Save';
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
        var backdrop = document.getElementById('onigiri-rename-backdrop');
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
        state.leafName = '';
        state.fullName = '';
        state.parentPrefix = '';
        state.fullPath = false;

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
        var error = document.getElementById('onigiri-rename-error');
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
        var input = document.getElementById('onigiri-rename-input');
        var saveBtn = document.getElementById('onigiri-rename-save');
        if (saveBtn) saveBtn.disabled = !input || !input.value.trim();
    }

    function updatePathMode() {
        var input = document.getElementById('onigiri-rename-input');
        var toggle = document.getElementById('onigiri-rename-path-toggle');
        var hint = document.getElementById('onigiri-rename-hint');
        if (!input || !toggle || !hint) return;

        if (state.fullPath) {
            input.value = state.fullName || state.leafName || '';
            toggle.textContent = 'Leaf name';
            toggle.classList.add('is-active');
            hint.textContent = 'Editing the full deck path';
        } else {
            var current = input.value || state.leafName || '';
            input.value = current.indexOf('::') === -1 ? current : current.split('::').pop();
            toggle.textContent = 'Full path';
            toggle.classList.remove('is-active');
            hint.textContent = state.parentPrefix ? ('Inside ' + state.parentPrefix) : 'Top-level deck';
        }
        setError('');
        updateConfirmState();
        try {
            input.focus({ preventScroll: true });
        } catch (_) {
            input.focus();
        }
        input.select();
    }

    function submit() {
        var input = document.getElementById('onigiri-rename-input');
        if (!input) return;
        var name = input.value.trim();
        if (!name) {
            setError('Enter a deck name.');
            updateConfirmState();
            return;
        }
        var payload = {
            deckId: state.deckId,
            name: name,
            fullPath: !!state.fullPath
        };
        if (typeof pycmd === 'function') {
            pycmd('onigiri_rename_deck:' + encodeURIComponent(JSON.stringify(payload)));
        }
    }

    function buildDialog(data) {
        ensureStyles();
        if (window.OnigiriEngine && typeof OnigiriEngine.preloadMaskIcons === 'function') {
            OnigiriEngine.preloadMaskIcons([iconUrl('rename.svg'), iconUrl('cancel.svg')]);
        }

        state.deckId = data.deckId;
        state.leafName = data.leafName || '';
        state.fullName = data.fullName || state.leafName || '';
        state.parentPrefix = data.parentPrefix || '';
        state.fullPath = false;
        state.cleanupFns = [];

        var backdrop = document.createElement('div');
        backdrop.id = 'onigiri-rename-backdrop';
        backdrop.className = 'is-preparing';

        var modal = document.createElement('div');
        modal.className = 'onigiri-rename-modal';
        modal.addEventListener('click', function (evt) { evt.stopPropagation(); });
        modal.addEventListener('pointerdown', function (evt) { evt.stopPropagation(); });

        var header = document.createElement('div');
        header.className = 'onigiri-rename-header';
        var headerIcon = document.createElement('div');
        headerIcon.className = 'onigiri-rename-header-icon';
        headerIcon.appendChild(makeIcon('rename.svg', 'onigiri-rename-header-svg', 18));
        header.appendChild(headerIcon);

        var titleWrap = document.createElement('div');
        titleWrap.className = 'onigiri-rename-title-wrap';
        var title = document.createElement('div');
        title.className = 'onigiri-rename-title';
        title.textContent = 'Rename Deck';
        titleWrap.appendChild(title);
        var subtitle = document.createElement('div');
        subtitle.className = 'onigiri-rename-subtitle';
        subtitle.title = state.fullName;
        subtitle.textContent = state.fullName || 'Selected deck';
        titleWrap.appendChild(subtitle);
        header.appendChild(titleWrap);

        var closeBtn = document.createElement('span');
        closeBtn.setAttribute('role', 'button');
        closeBtn.tabIndex = 0;
        // Set tabindex for accessibility
        try { arguments[0].tabIndex = 0; } catch(e){};
        closeBtn.className = 'onigiri-rename-close';
        closeBtn.title = 'Close';
        closeBtn.appendChild(makeIcon('cancel.svg', 'onigiri-rename-close-svg', 14));
        closeBtn.addEventListener('click', function () { close(false); });
        header.appendChild(closeBtn);
        modal.appendChild(header);

        var body = document.createElement('div');
        body.className = 'onigiri-rename-body';
        var label = document.createElement('div');
        label.className = 'onigiri-rename-label';
        label.textContent = 'Deck name';
        body.appendChild(label);

        var inputWrap = document.createElement('div');
        inputWrap.className = 'onigiri-rename-input-wrap';
        var input = document.createElement('input');
        input.id = 'onigiri-rename-input';
        input.className = 'onigiri-rename-input';
        input.type = 'text';
        input.autocomplete = 'off';
        input.spellcheck = false;
        input.value = state.leafName;
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
        hint.id = 'onigiri-rename-hint';
        hint.className = 'onigiri-rename-hint';
        body.appendChild(hint);
        modal.appendChild(body);

        var error = document.createElement('div');
        error.id = 'onigiri-rename-error';
        error.className = 'onigiri-rename-error';
        modal.appendChild(error);

        var footer = document.createElement('div');
        footer.className = 'onigiri-rename-footer';
        var pathToggle = document.createElement('span');
        pathToggle.setAttribute('role', 'button');
        pathToggle.tabIndex = 0;
        // Set tabindex for accessibility
        try { arguments[0].tabIndex = 0; } catch(e){};
        pathToggle.id = 'onigiri-rename-path-toggle';
        pathToggle.className = 'onigiri-rename-btn onigiri-rename-btn-secondary';
        pathToggle.addEventListener('click', function () {
            state.fullPath = !state.fullPath;
            updatePathMode();
        });
        var spacer = document.createElement('div');
        spacer.className = 'onigiri-rename-spacer';
        var cancelBtn = document.createElement('span');
        cancelBtn.setAttribute('role', 'button');
        cancelBtn.tabIndex = 0;
        // Set tabindex for accessibility
        try { arguments[0].tabIndex = 0; } catch(e){};
        cancelBtn.className = 'onigiri-rename-btn onigiri-rename-btn-secondary';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.addEventListener('click', function () { close(false); });
        var saveBtn = document.createElement('span');
        saveBtn.setAttribute('role', 'button');
        saveBtn.tabIndex = 0;
        // Set tabindex for accessibility
        try { arguments[0].tabIndex = 0; } catch(e){};
        saveBtn.id = 'onigiri-rename-save';
        saveBtn.className = 'onigiri-rename-btn onigiri-rename-btn-primary';
        saveBtn.textContent = 'Save';
        saveBtn.addEventListener('click', submit);

        footer.appendChild(pathToggle);
        footer.appendChild(spacer);
        footer.appendChild(cancelBtn);
        footer.appendChild(saveBtn);
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

        updatePathMode();
        revealWhenStable(backdrop, input);
    }

    window.OnigiriRenameDialog = {
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
