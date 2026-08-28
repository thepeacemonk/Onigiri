(function () {
    if (window.OnigiriDeleteDeckDialog) return;

    var state = {
        deckIds: [],
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

    function makeIcon(iconRef, className, size, color) {
        if (window.OnigiriEngine && typeof OnigiriEngine.createMaskIcon === 'function') {
            return OnigiriEngine.createMaskIcon(iconUrl(iconRef), {
                className: className || '',
                size: size || 16,
                color: color || 'currentColor'
            });
        }
        var fallback = document.createElement('span');
        fallback.className = className || '';
        return fallback;
    }

    // Shared light/dark tokens for Onigiri dialogs (same contract as rename_dialog.js).
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
        if (document.getElementById('onigiri-delete-dialog-style')) return;
        var style = document.createElement('style');
        style.id = 'onigiri-delete-dialog-style';
        style.textContent = [
            '#onigiri-delete-backdrop{position:fixed;inset:0;z-index:200000;display:flex;align-items:center;justify-content:center;',
            '  background:var(--odlg-scrim, rgba(0,0,0,0.58));contain:layout paint style;isolation:isolate;transform:translateZ(0);',
            '  backface-visibility:hidden;-webkit-backface-visibility:hidden;}',
            '#onigiri-delete-backdrop.is-preparing{visibility:hidden;}',
            '#onigiri-delete-backdrop *{box-sizing:border-box;}',
            '#onigiri-delete-backdrop button{appearance:none;-webkit-appearance:none;border:none !important;outline:none !important;',
            '  box-shadow:none !important;background-image:none !important;',
            '  font-family:var(--font-main,-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif);}',
            '.onigiri-delete-modal{width:440px;max-width:94vw;display:flex;flex-direction:column;overflow:hidden;',
            '  border-radius:16px;border:1px solid var(--odlg-border, rgba(0,0,0,0.14));',
            '  background:var(--odlg-surface, #ffffff);color:var(--odlg-fg, #212121);',
            '  box-shadow:0 24px 70px rgba(0,0,0,0.42);backface-visibility:hidden;-webkit-backface-visibility:hidden;',
            '  transform:translateZ(0);contain:layout paint style;isolation:isolate;}',
            '.onigiri-delete-header{display:flex;align-items:flex-start;gap:12px;padding:18px 18px 14px;border-bottom:1px solid var(--odlg-border, rgba(0,0,0,0.14));}',
            '.onigiri-delete-header-icon{width:34px;height:34px;min-width:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;',
            '  color:#d84a4a;background:rgba(216,74,74,0.12);}',
            '.onigiri-delete-title-wrap{min-width:0;flex:1;}',
            '.onigiri-delete-title{font-size:16px;font-weight:700;line-height:1.2;margin:0 0 5px;color:var(--odlg-fg, #212121);}',
            '.onigiri-delete-subtitle{font-size:13px;color:var(--odlg-fg-subtle, #757575);line-height:1.35;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
            '.onigiri-delete-close{width:30px;height:30px;min-width:30px;padding:0;border-radius:8px;background:transparent !important;color:var(--odlg-fg-subtle, #757575);',
            '  display:flex;align-items:center;justify-content:center;cursor:pointer;}',
            '.onigiri-delete-body{padding:16px 18px;font-size:13px;line-height:1.5;color:var(--odlg-fg, #212121);}',
            '.onigiri-delete-body strong{font-weight:700;}',
            '.onigiri-delete-meta{margin-top:8px;font-size:12px;color:var(--odlg-fg-subtle, #757575);}',
            '.onigiri-delete-footer{display:flex;align-items:center;justify-content:flex-end;gap:8px;padding:12px 18px 16px;border-top:1px solid var(--odlg-border, rgba(0,0,0,0.14));}',
            '.onigiri-delete-btn{height:36px;padding:0 15px;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;gap:7px;',
            '  cursor:pointer;font-size:13px;font-weight:650;transition:none;',
            '  font-family:var(--font-main,-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif);}',
            '.onigiri-delete-btn-secondary{background:var(--odlg-highlight, #f2f2f2);color:var(--odlg-fg, #212121);}',
            '.onigiri-delete-btn-secondary:hover{background:var(--odlg-hover, #e9e9e9);}',
            '.onigiri-delete-btn-danger{background:#d84a4a;color:#fff;}',
            '.onigiri-delete-btn-danger:hover{background:#c03d3d;}',
            // Undo toast (mirrors gamification notification cards from notifications.css).
            '#onigiri-delete-toast-stack{position:fixed;top:5px;left:50%;transform:translateX(-50%);display:flex;flex-direction:column;',
            '  gap:12px;align-items:center;width:min(360px,calc(100vw - 32px));max-width:100%;z-index:200001;pointer-events:none;}',
            '.onigiri-delete-toast{position:relative;cursor:default;}',
            '.onigiri-delete-toast .onigiri-notification-content{padding-right:4px;}',
            '.onigiri-delete-toast-row{display:flex;align-items:center;gap:10px;}',
            '.onigiri-delete-toast-text{min-width:0;flex:1;}',
            '.onigiri-undo-btn{flex:none;height:30px;padding:0 14px;border:none;border-radius:999px;cursor:pointer;',
            '  font-size:12px;font-weight:700;background:rgba(216,74,74,0.14);color:#d84a4a;',
            '  font-family:var(--notification-font, "Poppins", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif);}',
            '.onigiri-undo-btn:hover{background:rgba(216,74,74,0.24);}',
            // Pill-shaped countdown bar under the toast text.
            '.onigiri-undo-countdown{margin-top:9px;height:6px;border-radius:999px;overflow:hidden;background:rgba(127,127,127,0.18);}',
            '.onigiri-undo-countdown-fill{height:100%;width:100%;border-radius:999px;background:#d84a4a;transform-origin:left center;}',
            '.onigiri-delete-toast.is-restore .onigiri-undo-countdown-fill{background:var(--accent-color, #70c6a6);}'
        ].join('');
        document.head.appendChild(style);
    }

    ensureStyles();

    function close(skipUiClose) {
        var backdrop = document.getElementById('onigiri-delete-backdrop');
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

        state.deckIds = [];

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
                if (focusTarget) {
                    try { focusTarget.focus({ preventScroll: true }); } catch (_) { focusTarget.focus(); }
                }
            });
        });
    }

    function submit() {
        if (!state.deckIds.length) return;
        var payload = { deckIds: state.deckIds.slice() };
        if (typeof pycmd === 'function') {
            pycmd('onigiri_delete_deck_confirmed:' + encodeURIComponent(JSON.stringify(payload)));
        }
        close(true);
        if (window.OnigiriEngine && typeof OnigiriEngine.clearDialogFocus === 'function') {
            OnigiriEngine.clearDialogFocus();
        }
    }

    // Insert `boldValue` in place of the translated template's {} placeholder.
    function renderTemplate(container, template, boldValue) {
        var idx = template.indexOf('{}');
        if (idx === -1) {
            container.textContent = template;
            return;
        }
        container.appendChild(document.createTextNode(template.slice(0, idx)));
        var strong = document.createElement('strong');
        strong.textContent = boldValue;
        container.appendChild(strong);
        container.appendChild(document.createTextNode(template.slice(idx + 2)));
    }

    function buildDialog(data) {
        ensureStyles();

        var ids = (data.deckIds || []).map(function (id) { return Number(id); }).filter(function (id) { return isFinite(id); });
        state.deckIds = ids;
        state.cleanupFns = [];

        var many = ids.length > 1;
        var deckName = data.deckName || 'Selected deck';
        var strings = data.strings || {};

        var backdrop = document.createElement('div');
        backdrop.id = 'onigiri-delete-backdrop';
        backdrop.className = 'is-preparing';

        var modal = document.createElement('div');
        modal.className = 'onigiri-delete-modal';
        modal.addEventListener('click', function (evt) { evt.stopPropagation(); });
        modal.addEventListener('pointerdown', function (evt) { evt.stopPropagation(); });

        var header = document.createElement('div');
        header.className = 'onigiri-delete-header';
        var headerIcon = document.createElement('div');
        headerIcon.className = 'onigiri-delete-header-icon';
        headerIcon.appendChild(makeIcon('trash.svg', 'onigiri-delete-header-svg', 18));
        header.appendChild(headerIcon);

        var titleWrap = document.createElement('div');
        titleWrap.className = 'onigiri-delete-title-wrap';
        var title = document.createElement('div');
        title.className = 'onigiri-delete-title';
        title.textContent = strings.title || (many ? 'Delete Decks' : 'Delete Deck');
        titleWrap.appendChild(title);
        var subtitle = document.createElement('div');
        subtitle.className = 'onigiri-delete-subtitle';
        subtitle.title = deckName;
        subtitle.textContent = strings.subtitle || (many ? (ids.length + ' decks selected') : deckName);
        titleWrap.appendChild(subtitle);
        header.appendChild(titleWrap);

        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'onigiri-delete-close';
        closeBtn.title = T('close', 'Close');
        closeBtn.appendChild(makeIcon('cancel.svg', 'onigiri-delete-close-svg', 14));
        closeBtn.addEventListener('click', function () { close(false); });
        header.appendChild(closeBtn);
        modal.appendChild(header);

        var body = document.createElement('div');
        body.className = 'onigiri-delete-body';
        var message = document.createElement('div');
        var messageTemplate = strings.message
            || (many ? 'Delete {} decks and all of their cards?' : 'Delete {} and all of its cards?');
        var messageValue = strings.messageValue
            || (many ? String(ids.length) : "'" + deckName + "'");
        renderTemplate(message, messageTemplate, messageValue);
        body.appendChild(message);
        var meta = document.createElement('div');
        meta.className = 'onigiri-delete-meta';
        var metaParts = [];
        if (strings.cards) metaParts.push(strings.cards);
        metaParts.push(strings.subdecksNote || 'Subdecks are deleted too');
        meta.textContent = metaParts.join(' \u00b7 ');
        body.appendChild(meta);
        modal.appendChild(body);

        var footer = document.createElement('div');
        footer.className = 'onigiri-delete-footer';
        var cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'onigiri-delete-btn onigiri-delete-btn-secondary';
        cancelBtn.textContent = strings.cancel || 'Cancel';
        cancelBtn.addEventListener('click', function () { close(false); });
        var deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'onigiri-delete-btn onigiri-delete-btn-danger';
        deleteBtn.textContent = strings.confirm || 'Delete';
        deleteBtn.addEventListener('click', submit);
        footer.appendChild(cancelBtn);
        footer.appendChild(deleteBtn);
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

        revealWhenStable(backdrop, cancelBtn);
    }

    // ---- Undo toast -------------------------------------------------------

    function toastDuration() {
        var configured = Number(window.onigiriNotificationDuration);
        var base = (isFinite(configured) && configured > 0) ? configured : 6000;
        return Math.max(4000, Math.min(30000, base));
    }

    function ensureToastStack() {
        var stack = document.getElementById('onigiri-delete-toast-stack');
        if (!stack) {
            stack = document.createElement('div');
            stack.id = 'onigiri-delete-toast-stack';
            document.body.appendChild(stack);
        }
        return stack;
    }

    function removeToastCard(card) {
        card.classList.remove('is-visible');
        window.setTimeout(function () {
            var stack = card.parentElement;
            card.remove();
            if (stack && !stack.children.length) stack.remove();
        }, 240);
    }

    function showToast(data) {
        ensureStyles();
        data = data || {};

        var stack = ensureToastStack();
        // One delete toast at a time; a new deletion replaces the previous card.
        stack.querySelectorAll('.onigiri-delete-toast').forEach(function (old) { old.remove(); });

        var canUndo = !!data.canUndo;

        var card = document.createElement('article');
        card.className = 'onigiri-notification-card onigiri-delete-toast';
        if (!canUndo) card.classList.add('is-restore');

        var icon = document.createElement('div');
        icon.className = 'onigiri-notification-icon';
        icon.appendChild(makeIcon(data.iconName || 'trash.svg', 'onigiri-delete-toast-svg', 20));
        card.appendChild(icon);

        var content = document.createElement('div');
        content.className = 'onigiri-notification-content';

        var row = document.createElement('div');
        row.className = 'onigiri-delete-toast-row';

        var text = document.createElement('div');
        text.className = 'onigiri-delete-toast-text';
        var title = document.createElement('p');
        title.className = 'onigiri-notification-title';
        title.textContent = data.title || 'Deck deleted';
        var description = document.createElement('p');
        description.className = 'onigiri-notification-description';
        description.textContent = data.message || '';
        text.appendChild(title);
        if (description.textContent) text.appendChild(description);
        row.appendChild(text);

        if (canUndo) {
            var undoBtn = document.createElement('button');
            undoBtn.type = 'button';
            undoBtn.className = 'onigiri-undo-btn';
            undoBtn.textContent = data.undoLabel || 'Undo';
            undoBtn.addEventListener('click', function (evt) {
                evt.stopPropagation();
                if (typeof pycmd === 'function') pycmd('onigiri_undo_delete_deck');
                removeToastCard(card);
            });
            row.appendChild(undoBtn);
        }

        content.appendChild(row);

        var countdown = document.createElement('div');
        countdown.className = 'onigiri-undo-countdown';
        var fill = document.createElement('div');
        fill.className = 'onigiri-undo-countdown-fill';
        countdown.appendChild(fill);
        content.appendChild(countdown);

        card.appendChild(content);

        stack.appendChild(card);

        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                card.classList.add('is-visible');
            });
        });

        // Countdown bar drives the auto-dismiss; hover pauses both.
        var duration = toastDuration();
        var remaining = duration;
        var lastTick = null;
        var paused = false;
        var done = false;

        function tick(now) {
            if (done || !card.isConnected) return;
            if (lastTick === null) lastTick = now;
            if (!paused) {
                remaining -= (now - lastTick);
            }
            lastTick = now;
            var ratio = Math.max(0, remaining / duration);
            fill.style.transform = 'scaleX(' + ratio + ')';
            if (remaining <= 0) {
                done = true;
                removeToastCard(card);
                return;
            }
            requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);

        card.addEventListener('mouseenter', function () { paused = true; });
        card.addEventListener('mouseleave', function () { paused = false; });
    }

    window.OnigiriDeleteDeckDialog = {
        open: function (data) {
            close(true);
            if (window.OnigiriEngine) {
                OnigiriEngine._clearAllRowVisualStates();
                OnigiriEngine._beginOverrideState('dialog-focus');
                var ids = (data && data.deckIds) || [];
                ids.forEach(function (deckId) {
                    var value = String(deckId || '');
                    var selectorId = typeof OnigiriEngine.escapeSelectorValue === 'function'
                        ? OnigiriEngine.escapeSelectorValue(value)
                        : value.replace(/["\\]/g, '\\$&');
                    var row = document.querySelector('tr.deck[data-did="' + selectorId + '"]');
                    if (row) row.classList.add('ctx-row-active');
                });
            }
            buildDialog(data || {});
            if (typeof pycmd === 'function') pycmd('onigiri_ui_open');
        },
        close: close,
        showUndoToast: showToast
    };
})();
