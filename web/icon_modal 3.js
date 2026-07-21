window.OnigiriIconChooser = (function () {
    const EMOJIS = [
        { value: "🤍", label: "White Heart", asset: "heart_white.svg" },
        { value: "🧼", label: "Soap", asset: "soap.svg" },
        { value: "💀", label: "Skull", asset: "skull.svg" },
        { value: "📄", label: "Paper", asset: "paper.svg" },
        { value: "📝", label: "Memo", asset: "memo.svg" },
        { value: "📖", label: "Open Book", asset: "open_book.svg" },
        { value: "🍙", label: "Onigiri", asset: "onigiri.svg" },
        { value: "🩷", label: "Light Pink Heart", asset: "heart_light_pink.svg" },
        { value: "💕", label: "Two Hearts", asset: "two_hearts.svg" },
        { value: "🌸", label: "Cherry Blossom", asset: "cherry_blossom.svg" },
        { value: "🌷", label: "Tulip", asset: "tulip.svg" },
        { value: "🪷", label: "Lotus", asset: "lotus.svg" },
        { value: "🧠", label: "Brain", asset: "brain.svg" },
        { value: "🦑", label: "Squid", asset: "squid.svg" },
        { value: "❤️", label: "Red Heart", asset: "heart_red.svg" },
        { value: "🫀", label: "Anatomical Heart", asset: "anatomical_heart.svg" },
        { value: "📕", label: "Red Book", asset: "red_book.svg" },
        { value: "🔥", label: "Fire", asset: "fire.svg" },
        { value: "🍉", label: "Watermelon", asset: "watermelon.svg" },
        { value: "🧡", label: "Orange Heart", asset: "heart_orange.svg" },
        { value: "🍊", label: "Tangerine", asset: "tangerine.svg" },
        { value: "🍹", label: "Tropical Drink", asset: "tropical_drink.svg" },
        { value: "🧇", label: "Waffle", asset: "waffle.svg" },
        { value: "🍍", label: "Pineapple", asset: "pineapple.svg" },
        { value: "⭐", label: "Star", asset: "star.svg" },
        { value: "✨", label: "Sparkle", asset: "sparkle.svg" },
        { value: "⚡", label: "Bolt", asset: "bolt.svg" },
        { value: "🏆", label: "Trophy", asset: "trophy.svg" },
        { value: "💛", label: "Yellow Heart", asset: "heart_yellow.svg" },
        { value: "📙", label: "Yellow Book", asset: "yellow_book.svg" },
        { value: "✏️", label: "Pen", asset: "pen.svg" },
        { value: "🍋‍🟩", label: "Lime", asset: "lime.svg" },
        { value: "💚", label: "Green Heart", asset: "heart_green.svg" },
        { value: "📗", label: "Green Book", asset: "green_book.svg" },
        { value: "🌱", label: "Plant", asset: "emoji.svg" },
        { value: "🍀", label: "Four Leaf Clover", asset: "four_leaf_clover.svg" },
        { value: "🍃", label: "Leaf Fluttering In Wind", asset: "leaf_fluttering_in_wind.svg" },
        { value: "🌳", label: "Deciduous Tree", asset: "deciduous_tree.svg" },
        { value: "🌲", label: "Evergreen Tree", asset: "evergreen_tree.svg" },
        { value: "🎄", label: "Christmas Tree", asset: "christmas_tree.svg" },
        { value: "🍵", label: "Teacup", asset: "teacup_without_handle.svg" },
        { value: "💙", label: "Blue Heart", asset: "blue_heart.svg" },
        { value: "📘", label: "Blue Book", asset: "blue_book.svg" },
        { value: "💧", label: "Droplet", asset: "droplet.svg" },
        { value: "💎", label: "Gem Stone", asset: "gem_stone.svg" },
        { value: "🧪", label: "Test Tube", asset: "test_tube.svg" },
        { value: "🍇", label: "Grapes", asset: "grapes.svg" },
        { value: "🔬", label: "Microscope", asset: "microscope.svg" },
        { value: "💻", label: "Computer", asset: "computer.svg" },
        { value: "📟", label: "Pager", asset: "pager.svg" },
        { value: "🎮", label: "Videogame", asset: "videogame.svg" },
        { value: "🍡", label: "Dango", asset: "dango.svg" },
        { value: "📚", label: "Books", asset: "books.svg" },
        { value: "🗺️", label: "World Map", asset: "world_map.svg" },
    ];

    // Empty color means "follow the theme", i.e. the icon is painted with
    // --icon-color like every other deck icon SVG. Python stores it as "".
    const THEME_COLOR = "";

    const state = {
        deckId: "",
        selectedIcon: "",
        selectedColor: THEME_COLOR,
        emojiBaseUrl: "/_addons/1011095603/system_files/emojis",
        data: {},
    };

    function py(command) {
        if (typeof pycmd === "function") pycmd(command);
    }

    function close() {
        const backdrop = document.getElementById("onigiri-icon-backdrop");
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
        if (document.getElementById("onigiri-icon-modal-styles")) return;
        const style = document.createElement("style");
        style.id = "onigiri-icon-modal-styles";
        style.textContent = `
            /* Picker tokens. These mirror settings/_picker_chrome.py one for one
               so the Qt pickers and this modal read as the same dialog. */
            #onigiri-icon-backdrop {
                --pk-surface: #ffffff;
                --pk-fg: #202124;
                --pk-muted: #8f9299;
                --pk-inset: #f2f2f2;
                --pk-inset-hover: #e9e9e9;
                --pk-hairline: #dcdde1;
                --pk-accent: var(--odlg-accent, #0077C8);
                position: fixed;
                inset: 0;
                z-index: 200000;
                display: flex;
                align-items: center;
                justify-content: center;
                /* One composited layer blurs the whole page behind the modal —
                   cheaper than filtering the page content itself. */
                background: rgba(0, 0, 0, 0.24);
                backdrop-filter: blur(14px) saturate(120%);
                -webkit-backdrop-filter: blur(14px) saturate(120%);
            }
            .night-mode #onigiri-icon-backdrop,
            .nightMode #onigiri-icon-backdrop {
                --pk-surface: #242424;
                --pk-fg: #f4f4f5;
                --pk-muted: #8a8a8a;
                --pk-inset: #303030;
                --pk-inset-hover: #3a3a3a;
                --pk-hairline: #454545;
                background: rgba(0, 0, 0, 0.38);
            }
            #onigiri-icon-backdrop button,
            #onigiri-icon-backdrop input {
                -webkit-appearance: none !important;
                appearance: none !important;
                box-sizing: border-box !important;
                font-family: inherit !important;
                line-height: 1 !important;
                margin: 0 !important;
                outline: none !important;
                transform: none !important;
                letter-spacing: 0 !important;
            }
            #onigiri-icon-backdrop button:hover,
            #onigiri-icon-backdrop button:active,
            #onigiri-icon-backdrop button:focus {
                transform: none !important;
                box-shadow: none !important;
            }
            .onigiri-icon-modal {
                position: relative;
                width: min(540px, 94vw);
                height: min(610px, 88vh);
                display: flex;
                flex-direction: column;
                border: 1px solid var(--pk-hairline);
                border-radius: 18px;
                background: var(--pk-surface);
                color: var(--pk-fg);
                box-shadow: 0 24px 70px rgba(0, 0, 0, 0.32);
                overflow: hidden;
                contain: layout paint;
            }
            .onigiri-icon-modal-header,
            .onigiri-icon-modal-footer {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 16px 18px;
                flex-shrink: 0;
            }
            .onigiri-icon-modal-footer {
                justify-content: center;
            }
            .onigiri-icon-modal-title {
                font-size: 15px;
                font-weight: 600;
            }
            .onigiri-icon-modal-close {
                position: absolute;
                top: 16px;
                right: 16px;
                width: 28px;
                height: 28px;
                min-width: 28px !important;
                max-width: 28px !important;
                padding: 0 !important;
                border: 1px solid transparent !important;
                border-radius: 10px !important;
                background: transparent !important;
                color: var(--pk-muted) !important;
                cursor: pointer;
            }
            .onigiri-icon-modal-close:hover {
                background: var(--pk-inset) !important;
                color: var(--pk-fg) !important;
            }
            .onigiri-icon-modal-close svg {
                display: block;
                width: 15px;
                height: 15px;
                margin: auto;
                pointer-events: none;
            }
            .onigiri-icon-tabs {
                display: flex;
                gap: 4px;
                padding: 0 18px;
                flex-shrink: 0;
            }
            .onigiri-icon-tab {
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                height: 28px !important;
                min-width: 72px !important;
                padding: 0 14px !important;
                border: 1px solid transparent !important;
                border-radius: 10px !important;
                background: transparent !important;
                color: var(--pk-muted) !important;
                cursor: pointer;
                font-size: 13px !important;
                font-weight: 500 !important;
            }
            .onigiri-icon-tab:hover {
                background: var(--pk-inset) !important;
            }
            .onigiri-icon-tab.active {
                background: var(--pk-inset) !important;
                color: var(--pk-fg) !important;
            }
            .onigiri-icon-body {
                flex: 1;
                min-height: 0;
                display: flex;
                flex-direction: column;
                padding: 12px 18px 8px;
                overflow: hidden;
            }
            .onigiri-icon-pane {
                flex: 1;
                min-height: 0;
                display: none;
                flex-direction: column;
                overflow: hidden;
            }
            .onigiri-icon-pane.active {
                display: flex;
            }
            .onigiri-icon-search-row {
                flex: 0 0 auto;
                padding: 0 0 14px;
            }
            .onigiri-icon-search {
                width: 100%;
                box-sizing: border-box;
                border: 1px solid transparent;
                border-radius: 10px;
                background: var(--pk-inset);
                color: var(--pk-fg);
                padding: 9px 12px;
                margin-bottom: 0;
                outline: none;
            }
            .onigiri-icon-search:focus {
                border-color: var(--pk-accent);
            }
            .onigiri-icon-grid {
                flex: 1;
                min-height: 0;
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(60px, 1fr));
                align-content: start;
                gap: 8px;
                overflow: auto;
                padding: 2px 2px 12px;
            }
            .onigiri-icon-section-title {
                grid-column: 1 / -1;
                color: var(--pk-muted);
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                padding: 8px 2px 2px;
            }
            /* Idle cells carry no outline — only the selected one does. No
               transitions here either: the grid can hold hundreds of cells. */
            .onigiri-icon-cell {
                position: relative;
                height: 60px;
                min-height: 60px;
                display: flex;
                align-items: center;
                justify-content: center;
                box-sizing: border-box;
                border: 1px solid transparent;
                border-radius: 12px;
                background: var(--pk-inset);
                cursor: pointer;
            }
            .onigiri-icon-cell:hover {
                background: var(--pk-inset-hover);
            }
            .onigiri-icon-cell.selected {
                border-color: var(--pk-accent);
                background: var(--pk-inset-hover); /* fallback for older WebEngine */
                background: color-mix(in srgb, var(--pk-accent) 16%, transparent);
            }
            /* --icon-color is declared on :root (light) and .night-mode (dark),
               so it can only be read from inside the modal — resolving it on
               documentElement would always pick the light value. */
            .onigiri-icon-modal.theme-icon-color .onigiri-icon-mask {
                background: var(--icon-color, #888888);
            }
            .onigiri-icon-mask {
                width: 30px;
                height: 30px;
                background: var(--onigiri-selected-icon-color, #888888);
                mask-size: contain;
                -webkit-mask-size: contain;
                mask-repeat: no-repeat;
                -webkit-mask-repeat: no-repeat;
                mask-position: center;
                -webkit-mask-position: center;
            }
            .onigiri-icon-image {
                width: 34px;
                height: 34px;
                object-fit: contain;
            }
            .onigiri-icon-emoji {
                font-size: 26px;
                line-height: 1;
            }
            .onigiri-icon-emoji-img {
                width: 40px;
                height: 40px;
                max-width: 40px;
                max-height: 40px;
                aspect-ratio: 1 / 1;
                object-fit: contain;
                pointer-events: none;
            }
            .onigiri-icon-custom-emoji {
                grid-column: 1 / -1;
                display: flex;
                align-items: center;
                gap: 10px;
                min-height: 48px;
                padding: 10px;
                border: 1px solid transparent;
                border-radius: 14px;
                background: var(--pk-inset);
            }
            .onigiri-icon-custom-emoji button {
                height: 32px !important;
                min-width: 118px !important;
                padding: 0 12px !important;
                border: none !important;
                border-radius: 10px !important;
                background: var(--pk-inset-hover) !important;
                color: var(--pk-fg) !important;
                cursor: pointer;
                font-size: 13px !important;
                font-weight: 600 !important;
            }
            .onigiri-icon-custom-emoji input {
                flex: 1;
                min-width: 80px;
                height: 32px;
                border: 1px solid transparent;
                border-radius: 10px;
                background: var(--pk-surface);
                color: var(--pk-fg);
                padding: 0 10px;
                font-size: 18px;
            }
            .onigiri-icon-custom-emoji input:focus {
                border-color: var(--pk-accent);
            }
            .onigiri-icon-delete {
                position: absolute;
                top: 4px;
                right: 4px;
                width: 18px;
                height: 18px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 50%;
                background: rgba(0, 0, 0, 0.46);
                color: white;
                opacity: 0;
                pointer-events: none;
            }
            .onigiri-icon-delete svg {
                display: block;
                width: 11px;
                height: 11px;
                pointer-events: none;
            }
            .onigiri-icon-cell:hover .onigiri-icon-delete {
                opacity: 1;
                pointer-events: auto;
            }
            .onigiri-icon-color-section {
                padding: 10px 18px 12px;
                flex-shrink: 0;
            }
            .onigiri-icon-color-label {
                margin-bottom: 8px;
                color: var(--pk-muted);
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }
            .onigiri-icon-swatches {
                display: flex;
                align-items: center;
                gap: 8px;
                flex-wrap: wrap;
            }
            .onigiri-icon-swatch {
                width: 24px;
                height: 24px;
                border-radius: 50%;
                cursor: pointer;
                border: none;
                box-sizing: border-box;
            }
            .onigiri-icon-swatch.theme-default {
                background: var(--icon-color, #888888);
                color: var(--icon-color, #888888);
            }
            .onigiri-icon-swatch.active {
                box-shadow: 0 0 0 2px var(--pk-surface), 0 0 0 4px currentColor;
            }
            .onigiri-icon-hex {
                width: 82px;
                border: 1px solid transparent;
                border-radius: 10px;
                background: var(--pk-inset);
                color: var(--pk-fg);
                padding: 6px 8px;
                outline: none;
            }
            .onigiri-icon-hex:focus {
                border-color: var(--pk-accent);
            }
            .onigiri-icon-btn {
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                height: 36px !important;
                min-width: 76px !important;
                padding: 0 16px !important;
                border: 1px solid transparent !important;
                border-radius: 10px !important;
                background: var(--pk-inset) !important;
                color: var(--pk-fg) !important;
                cursor: pointer;
                font-size: 13px !important;
                font-weight: 500 !important;
            }
            .onigiri-icon-btn:hover {
                background: var(--pk-inset-hover) !important;
            }
            .onigiri-icon-btn.primary {
                min-width: 72px !important;
                background: var(--pk-accent) !important;
                color: white !important;
                font-weight: 600 !important;
            }
            .onigiri-icon-btn.primary:hover {
                opacity: 0.9;
            }
            .onigiri-icon-upload {
                box-sizing: border-box !important;
                width: 100% !important;
                height: 56px !important;
                min-height: 56px !important;
                padding: 0 16px !important;
                border: none !important;
                border-radius: 14px !important;
                background: var(--pk-inset) !important;
                color: var(--pk-fg) !important;
                text-align: center !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                cursor: pointer;
                font-size: 14px !important;
                font-weight: 500 !important;
            }
            .onigiri-icon-upload:hover {
                background: var(--pk-inset-hover) !important;
            }
        `;
        document.head.appendChild(style);
    }

    function selectIcon(name) {
        state.selectedIcon = name;
        document.querySelectorAll(".onigiri-icon-cell.selected").forEach(cell => cell.classList.remove("selected"));
        document.querySelectorAll(".onigiri-icon-cell").forEach(cell => {
            if (cell.dataset.iconName === name) cell.classList.add("selected");
        });
    }

    function makeSearch(placeholder, onInput) {
        const row = document.createElement("div");
        row.className = "onigiri-icon-search-row";
        const input = document.createElement("input");
        input.className = "onigiri-icon-search";
        input.placeholder = placeholder;
        input.addEventListener("input", () => onInput(input.value.trim().toLowerCase()));
        row.appendChild(input);
        return row;
    }

    function makeGrid() {
        const grid = document.createElement("div");
        grid.className = "onigiri-icon-grid";
        return grid;
    }

    function xIconSvg(size = 14) {
        return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`;
    }

    function renderSvgGrid(grid, items, filter) {
        grid.innerHTML = "";
        [
            ["User Icons", items.filter(item => !item.system)],
            ["System Icons", items.filter(item => item.system)],
        ].forEach(([title, groupItems]) => {
            const visibleItems = groupItems.filter(item => !filter || (item.label || item.name).toLowerCase().includes(filter));
            if (!visibleItems.length) return;
            const sectionTitle = document.createElement("div");
            sectionTitle.className = "onigiri-icon-section-title";
            sectionTitle.textContent = title;
            grid.appendChild(sectionTitle);
            visibleItems.forEach(item => {
                const cell = document.createElement("div");
                cell.className = "onigiri-icon-cell" + (state.selectedIcon === item.name ? " selected" : "");
                cell.dataset.iconName = item.name;
                cell.title = item.label || item.name;

                const icon = document.createElement("div");
                icon.className = "onigiri-icon-mask";
                icon.style.maskImage = `url("${item.url}")`;
                icon.style.webkitMaskImage = `url("${item.url}")`;
                cell.appendChild(icon);

                if (!item.system) {
                    const del = document.createElement("span");
                    del.className = "onigiri-icon-delete";
                    del.innerHTML = xIconSvg(11);
                    del.addEventListener("click", event => {
                        event.stopPropagation();
                        py(`onigiri_icon_chooser_delete_icon:${state.deckId}:${item.name}`);
                    });
                    cell.appendChild(del);
                }

                cell.addEventListener("click", () => selectIcon(item.name));
                grid.appendChild(cell);
            });
        });
    }

    function buildIconsPane(data) {
        const pane = document.createElement("div");
        pane.className = "onigiri-icon-pane";
        pane.dataset.tabPane = "icons";
        const grid = makeGrid();
        pane.appendChild(makeSearch("Search icons", filter => renderSvgGrid(grid, data.icons || [], filter)));
        pane.appendChild(grid);
        renderSvgGrid(grid, data.icons || [], "");
        return pane;
    }

    function buildImagesPane(data) {
        const pane = document.createElement("div");
        pane.className = "onigiri-icon-pane";
        pane.dataset.tabPane = "images";
        const grid = makeGrid();
        const render = (filter) => {
            grid.innerHTML = "";
            (data.images || [])
                .filter(item => !filter || item.name.toLowerCase().includes(filter))
                .forEach(item => {
                    const cell = document.createElement("div");
                    cell.className = "onigiri-icon-cell" + (state.selectedIcon === item.name ? " selected" : "");
                    cell.dataset.iconName = item.name;
                    const img = document.createElement("img");
                    img.className = "onigiri-icon-image";
                    img.src = item.url;
                    cell.appendChild(img);
                    const del = document.createElement("span");
                    del.className = "onigiri-icon-delete";
                    del.innerHTML = xIconSvg(11);
                    del.addEventListener("click", event => {
                        event.stopPropagation();
                        py(`onigiri_icon_chooser_delete_icon:${state.deckId}:${item.name}`);
                    });
                    cell.appendChild(del);
                    cell.addEventListener("click", () => selectIcon(item.name));
                    grid.appendChild(cell);
                });
        };
        pane.appendChild(makeSearch("Search images", render));
        pane.appendChild(grid);
        render("");
        return pane;
    }

    function buildEmojiPane() {
        const pane = document.createElement("div");
        pane.className = "onigiri-icon-pane";
        pane.dataset.tabPane = "emoji";
        const grid = makeGrid();
        EMOJIS.forEach(item => {
            const name = `emoji:${item.value}`;
            const cell = document.createElement("div");
            cell.className = "onigiri-icon-cell" + (state.selectedIcon === name ? " selected" : "");
            cell.dataset.iconName = name;
            cell.title = item.label;
            const img = document.createElement("img");
            img.className = "onigiri-icon-emoji-img";
            img.alt = item.label;
            img.src = `${state.emojiBaseUrl}/${item.asset}`;
            cell.appendChild(img);
            cell.addEventListener("click", () => selectIcon(name));
            grid.appendChild(cell);
        });
        const custom = document.createElement("div");
        custom.className = "onigiri-icon-custom-emoji";
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = "Type your own:";
        const input = document.createElement("input");
        input.type = "text";
        input.value = state.selectedIcon.indexOf("emoji:") === 0 && !EMOJIS.some(item => `emoji:${item.value}` === state.selectedIcon)
            ? state.selectedIcon.replace(/^emoji:/, "")
            : "";
        const selectCustomEmoji = () => {
            const emoji = input.value.trim();
            if (!emoji) return;
            selectIcon(`emoji:${emoji}`);
        };
        button.addEventListener("click", () => {
            input.focus();
            selectCustomEmoji();
        });
        input.addEventListener("input", selectCustomEmoji);
        input.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                event.preventDefault();
                selectCustomEmoji();
            }
        });
        custom.appendChild(button);
        custom.appendChild(input);
        grid.appendChild(custom);
        pane.appendChild(grid);
        return pane;
    }

    function buildUploadPane() {
        const pane = document.createElement("div");
        pane.className = "onigiri-icon-pane";
        pane.dataset.tabPane = "upload";
        pane.style.gap = "10px";
        ["Upload SVG icon", "Upload PNG image"].forEach((label, index) => {
            const button = document.createElement("span");
            button.className = "onigiri-icon-upload";
            button.textContent = label;
            button.addEventListener("click", () => {
                py(`${index === 0 ? "onigiri_icon_chooser_add_icon" : "onigiri_icon_chooser_add_image"}:${state.deckId}`);
            });
            pane.appendChild(button);
        });
        return pane;
    }

    function setTab(tab) {
        document.querySelectorAll(".onigiri-icon-tab").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.tab === tab);
        });
        document.querySelectorAll(".onigiri-icon-pane").forEach(pane => {
            pane.classList.toggle("active", pane.dataset.tabPane === tab);
        });
        const colorSection = document.querySelector(".onigiri-icon-color-section");
        if (colorSection) colorSection.style.display = tab === "icons" ? "" : "none";
    }

    function applyThemeColorMode() {
        const modal = document.querySelector(".onigiri-icon-modal");
        if (modal) modal.classList.toggle("theme-icon-color", state.selectedColor === THEME_COLOR);
    }

    function buildColorSection() {
        const section = document.createElement("div");
        section.className = "onigiri-icon-color-section";
        const label = document.createElement("div");
        label.className = "onigiri-icon-color-label";
        label.textContent = "Icon Color";
        section.appendChild(label);
        const row = document.createElement("div");
        row.className = "onigiri-icon-swatches";
        const colors = [THEME_COLOR, "#888888", "#ff4d4f", "#ff9f43", "#ffc629", "#45c878", "#4f95ff", "#845ec2", "#ffffff"];
        const setColor = (hex) => {
            state.selectedColor = hex;
            applyThemeColorMode();
            document.documentElement.style.setProperty("--onigiri-selected-icon-color", hex || "#888888");
            row.querySelectorAll(".onigiri-icon-swatch").forEach(swatch => {
                swatch.classList.toggle("active", swatch.dataset.color.toLowerCase() === hex.toLowerCase());
            });
            hexInput.value = hex;
        };
        colors.forEach(hex => {
            const swatch = document.createElement("span");
            swatch.className = "onigiri-icon-swatch" + (hex === THEME_COLOR ? " theme-default" : "");
            swatch.dataset.color = hex;
            if (hex === THEME_COLOR) {
                swatch.title = "Default (follows the theme)";
            } else {
                swatch.style.background = hex;
                swatch.style.color = hex;
            }
            swatch.addEventListener("click", () => setColor(hex));
            row.appendChild(swatch);
        });
        const hexInput = document.createElement("input");
        hexInput.className = "onigiri-icon-hex";
        hexInput.maxLength = 7;
        hexInput.placeholder = "Default";
        hexInput.addEventListener("input", () => {
            const value = hexInput.value.trim();
            if (/^#[0-9a-fA-F]{6}$/.test(value)) setColor(value);
        });
        row.appendChild(hexInput);
        section.appendChild(row);
        requestAnimationFrame(() => setColor(state.selectedColor));
        return section;
    }

    function open(data) {
        close();
        ensureStyles();
        state.deckId = String(data.deckId || "");
        state.selectedIcon = (data.current && data.current.icon) || "";
        state.selectedColor = (data.current && data.current.color) || THEME_COLOR;
        state.emojiBaseUrl = data.emojiBaseUrl || state.emojiBaseUrl;
        state.data = data;
        document.documentElement.style.setProperty("--onigiri-selected-icon-color", state.selectedColor || "#888888");

        const backdrop = document.createElement("div");
        backdrop.id = "onigiri-icon-backdrop";
        backdrop.addEventListener("click", close);

        const modal = document.createElement("div");
        modal.className = "onigiri-icon-modal" + (state.selectedColor === THEME_COLOR ? " theme-icon-color" : "");
        modal.addEventListener("click", event => event.stopPropagation());

        const header = document.createElement("div");
        header.className = "onigiri-icon-modal-header";
        const title = document.createElement("div");
        title.className = "onigiri-icon-modal-title";
        title.textContent = "Edit Icon";
        const closeBtn = document.createElement("span");
        closeBtn.className = "onigiri-icon-modal-close";
        closeBtn.innerHTML = xIconSvg(15);
        closeBtn.setAttribute("aria-label", "Close");
        closeBtn.title = "Close";
        closeBtn.addEventListener("click", close);
        header.appendChild(title);
        header.appendChild(closeBtn);
        modal.appendChild(header);

        const tabs = document.createElement("div");
        tabs.className = "onigiri-icon-tabs";
        [
            ["emoji", "Emoji"],
            ["icons", "Icons"],
            ["images", "Images"],
            ["upload", "Upload"],
        ].forEach(([id, label]) => {
            const btn = document.createElement("span");
            btn.className = "onigiri-icon-tab";
            btn.dataset.tab = id;
            btn.textContent = label;
            btn.addEventListener("click", () => setTab(id));
            tabs.appendChild(btn);
        });
        modal.appendChild(tabs);

        const body = document.createElement("div");
        body.className = "onigiri-icon-body";
        body.appendChild(buildEmojiPane());
        body.appendChild(buildIconsPane(data));
        body.appendChild(buildImagesPane(data));
        body.appendChild(buildUploadPane());
        modal.appendChild(body);
        modal.appendChild(buildColorSection());

        const footer = document.createElement("div");
        footer.className = "onigiri-icon-modal-footer";
        const reset = document.createElement("span");
        reset.className = "onigiri-icon-btn";
        reset.textContent = "Reset to Default";
        reset.addEventListener("click", () => {
            py(`onigiri_icon_chooser_reset:${state.deckId}`);
            close();
        });
        const cancel = document.createElement("span");
        cancel.className = "onigiri-icon-btn";
        cancel.textContent = "Cancel";
        cancel.addEventListener("click", close);
        const save = document.createElement("span");
        save.className = "onigiri-icon-btn primary";
        save.textContent = "Save";
        save.addEventListener("click", () => {
            const payload = JSON.stringify({ icon: state.selectedIcon, color: state.selectedColor });
            py(`onigiri_icon_chooser_save:${state.deckId}:${payload}`);
            close();
        });
        // Same order as the Qt pickers: Save, Cancel, Reset, centred.
        footer.appendChild(save);
        footer.appendChild(cancel);
        footer.appendChild(reset);
        modal.appendChild(footer);

        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);

        const initialTab = state.selectedIcon.indexOf("emoji:") === 0
            ? "emoji"
            : (state.selectedIcon.toLowerCase().endsWith(".png") ? "images" : "icons");
        setTab(initialTab);
    }

    return {
        open,
        close,
        refreshData(data) {
            const selected = state.selectedIcon;
            const color = state.selectedColor;
            open({ ...data, current: { icon: selected, color } });
        },
    };
})();
