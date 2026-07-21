window.OnigiriRenameDeckModal = (function () {
    const state = {
        deckId: "",
        parentPrefix: "",
    };

    function py(command) {
        if (typeof pycmd === "function") pycmd(command);
    }

    function close() {
        const backdrop = document.getElementById("onigiri-rename-backdrop");
        if (backdrop) backdrop.remove();
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
        if (document.getElementById("onigiri-rename-modal-styles")) return;
        const style = document.createElement("style");
        style.id = "onigiri-rename-modal-styles";
        style.textContent = `
            #onigiri-rename-backdrop {
                position: fixed;
                inset: 0;
                z-index: 200001;
                display: flex;
                align-items: center;
                justify-content: center;
                background: var(--odlg-scrim, rgba(0, 0, 0, 0.46));
            }
            #onigiri-rename-backdrop button,
            #onigiri-rename-backdrop input {
                -webkit-appearance: none !important;
                appearance: none !important;
                box-sizing: border-box !important;
                font-family: inherit !important;
                letter-spacing: 0 !important;
                outline: none !important;
            }
            .onigiri-rename-modal {
                position: relative;
                width: min(390px, calc(100vw - 36px));
                border: 1px solid var(--odlg-border, rgba(0,0,0,0.14));
                border-radius: 14px;
                background: var(--odlg-surface, #ffffff);
                color: var(--odlg-fg, #212121);
                box-shadow: 0 24px 70px rgba(0, 0, 0, 0.42);
                overflow: hidden;
            }
            .onigiri-rename-header {
                display: flex;
                align-items: center;
                padding: 16px 18px 8px;
            }
            .onigiri-rename-title {
                font-size: 15px;
                font-weight: 650;
                line-height: 1.2;
            }
            .onigiri-rename-close {
                position: absolute;
                top: 12px;
                right: 12px;
                width: 30px;
                height: 30px;
                padding: 0 !important;
                border: 0 !important;
                border-radius: 8px !important;
                background: transparent !important;
                color: var(--odlg-fg-subtle, #757575) !important;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .onigiri-rename-close:hover {
                color: var(--odlg-fg-subtle, #757575) !important;
                background: transparent !important;
            }
            .onigiri-rename-close svg {
                width: 15px;
                height: 15px;
                pointer-events: none;
            }
            .onigiri-rename-body {
                padding: 8px 18px 16px;
            }
            .onigiri-rename-label {
                display: block;
                margin-bottom: 7px;
                color: var(--odlg-fg-subtle, #757575);
                font-size: 12px;
                font-weight: 650;
                text-transform: uppercase;
            }
            .onigiri-rename-path {
                display: none;
                margin-bottom: 10px;
                color: var(--odlg-fg-subtle, #757575);
                font-size: 12px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .onigiri-rename-path.visible {
                display: block;
            }
            .onigiri-rename-input {
                width: 100%;
                height: 40px;
                padding: 0 12px;
                border: 1px solid var(--odlg-border, rgba(0,0,0,0.14));
                border-radius: 10px;
                background: var(--odlg-inset, #ffffff);
                color: var(--odlg-fg, #212121);
                font-size: 14px;
            }
            .onigiri-rename-input:focus {
                border-color: var(--odlg-accent, #0077C8);
                box-shadow: inset 0 0 0 1px var(--odlg-accent, #0077C8);
            }
            .onigiri-rename-error {
                min-height: 18px;
                margin-top: 7px;
                color: #ff5f57;
                font-size: 12px;
            }
            .onigiri-rename-footer {
                display: flex;
                align-items: center;
                justify-content: flex-end;
                gap: 8px;
                padding: 14px 18px 18px;
            }
            .onigiri-rename-btn {
                height: 34px;
                min-width: 82px;
                padding: 0 14px !important;
                border: 1px solid transparent !important;
                border-radius: 9px !important;
                cursor: pointer;
                font-size: 13px !important;
                font-weight: 650 !important;
                transform: none !important;
            }
            .onigiri-rename-btn.secondary {
                background: var(--odlg-highlight, rgba(0,0,0,0.06)) !important;
                color: var(--odlg-fg, #212121) !important;
            }
            .onigiri-rename-btn.primary {
                background: var(--odlg-accent, #0077C8) !important;
                color: white !important;
            }
            .onigiri-rename-btn:hover {
                filter: none !important;
                box-shadow: none !important;
                transform: none !important;
            }
        `;
        document.head.appendChild(style);
    }

    function submit() {
        const input = document.getElementById("onigiri-rename-input");
        const error = document.getElementById("onigiri-rename-error");
        if (!input) return;
        const name = input.value.trim();
        if (!name) {
            if (error) error.textContent = "Deck name cannot be empty.";
            input.focus();
            return;
        }
        py(`onigiri_rename_deck:${state.deckId}:${encodeURIComponent(JSON.stringify({ name }))}`);
        close();
    }

    function open(payload) {
        ensureStyles();
        close();
        state.deckId = String(payload.deckId || "");
        state.parentPrefix = payload.parentPrefix || "";

        const backdrop = document.createElement("div");
        backdrop.id = "onigiri-rename-backdrop";
        backdrop.addEventListener("click", close);

        const modal = document.createElement("div");
        modal.className = "onigiri-rename-modal";
        modal.addEventListener("click", event => event.stopPropagation());

        const header = document.createElement("div");
        header.className = "onigiri-rename-header";
        const title = document.createElement("div");
        title.className = "onigiri-rename-title";
        title.textContent = "Rename Deck";
        const closeBtn = document.createElement("span");
        closeBtn.className = "onigiri-rename-close";
        closeBtn.setAttribute('role', 'button');
        closeBtn.tabIndex = 0;
        closeBtn.setAttribute("aria-label", "Close");
        closeBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>';
        closeBtn.addEventListener("click", close);
        header.appendChild(title);
        header.appendChild(closeBtn);

        const body = document.createElement("div");
        body.className = "onigiri-rename-body";
        const label = document.createElement("label");
        label.className = "onigiri-rename-label";
        label.setAttribute("for", "onigiri-rename-input");
        label.textContent = "Deck name";
        const path = document.createElement("div");
        path.className = "onigiri-rename-path" + (state.parentPrefix ? " visible" : "");
        path.textContent = state.parentPrefix ? `${state.parentPrefix} ::` : "";
        const input = document.createElement("input");
        input.id = "onigiri-rename-input";
        input.className = "onigiri-rename-input";
        input.type = "text";
        input.value = payload.leafName || "";
        input.autocomplete = "off";
        input.spellcheck = false;
        const error = document.createElement("div");
        error.id = "onigiri-rename-error";
        error.className = "onigiri-rename-error";
        input.addEventListener("input", () => {
            error.textContent = "";
        });
        input.addEventListener("keydown", event => {
            if (event.key === "Enter") submit();
            if (event.key === "Escape") close();
        });
        body.appendChild(label);
        body.appendChild(path);
        body.appendChild(input);
        body.appendChild(error);

        const footer = document.createElement("div");
        footer.className = "onigiri-rename-footer";
        const cancel = document.createElement("span");
        cancel.className = "onigiri-rename-btn secondary";
        cancel.setAttribute('role', 'button');
        cancel.tabIndex = 0;
        cancel.textContent = "Cancel";
        cancel.addEventListener("click", close);
        const save = document.createElement("span");
        save.className = "onigiri-rename-btn primary";
        save.setAttribute('role', 'button');
        save.tabIndex = 0;
        save.textContent = "Save";
        save.addEventListener("click", submit);
        footer.appendChild(cancel);
        footer.appendChild(save);

        modal.appendChild(header);
        modal.appendChild(body);
        modal.appendChild(footer);
        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);
        requestAnimationFrame(() => {
            input.focus();
            input.select();
        });
    }

    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && document.getElementById("onigiri-rename-backdrop")) {
            close();
        }
    });

    return { open, close };
})();
