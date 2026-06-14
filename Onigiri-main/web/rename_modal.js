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

    function ensureStyles() {
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
                background: rgba(0, 0, 0, 0.46);
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
                border: 1px solid var(--border, rgba(128, 128, 128, 0.22));
                border-radius: 14px;
                background: var(--canvas-overlay, var(--canvas, #1f1f1f));
                color: var(--fg, #e8e8e8);
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
                color: var(--fg-subtle, #888) !important;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .onigiri-rename-close:hover {
                color: var(--fg, #e8e8e8) !important;
                background: var(--highlight-bg, rgba(128, 128, 128, 0.14)) !important;
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
                color: var(--fg-subtle, #888);
                font-size: 12px;
                font-weight: 650;
                text-transform: uppercase;
            }
            .onigiri-rename-path {
                display: none;
                margin-bottom: 10px;
                color: var(--fg-subtle, #888);
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
                border: 1px solid var(--border, rgba(128, 128, 128, 0.24));
                border-radius: 10px;
                background: var(--canvas-inset, rgba(128, 128, 128, 0.08));
                color: var(--fg, #e8e8e8);
                font-size: 14px;
            }
            .onigiri-rename-input:focus {
                border-color: var(--accent-color, #007aff);
                box-shadow: inset 0 0 0 1px var(--accent-color, #007aff);
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
                background: var(--highlight-bg, rgba(128, 128, 128, 0.14)) !important;
                color: var(--fg, #e8e8e8) !important;
            }
            .onigiri-rename-btn.primary {
                background: var(--accent-color, #007aff) !important;
                color: white !important;
            }
            .onigiri-rename-btn:hover {
                filter: brightness(1.04);
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
        const closeBtn = document.createElement("button");
        closeBtn.className = "onigiri-rename-close";
        closeBtn.type = "button";
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
        const cancel = document.createElement("button");
        cancel.className = "onigiri-rename-btn secondary";
        cancel.type = "button";
        cancel.textContent = "Cancel";
        cancel.addEventListener("click", close);
        const save = document.createElement("button");
        save.className = "onigiri-rename-btn primary";
        save.type = "button";
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
