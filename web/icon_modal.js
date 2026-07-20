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

    const state = {
        deckId: "",
        selectedIcon: "",
        selectedColor: "#888888",
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

    function ensureStyles() {
        if (document.getElementById("onigiri-icon-modal-styles")) return;
        const style = document.createElement("style");
        style.id = "onigiri-icon-modal-styles";
        style.textContent = `
            #onigiri-icon-backdrop {
                position: fixed;
                inset: 0;
                z-index: 200000;
                display: flex;
                align-items: center;
                justify-content: center;
                background: rgba(0, 0, 0, 0.48);
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
                border: 1px solid var(--border, rgba(128, 128, 128, 0.22));
                border-radius: 14px;
                background: var(--canvas-overlay, var(--canvas, #1f1f1f));
                color: var(--fg, #e8e8e8);
                box-shadow: 0 24px 70px rgba(0, 0, 0, 0.42);
                overflow: hidden;
                contain: layout paint;
            }
            .onigiri-icon-modal-header,
            .onigiri-icon-modal-footer {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 14px 18px;
                flex-shrink: 0;
            }
            .onigiri-icon-modal-title {
                font-size: 15px;
                font-weight: 650;
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
                border-radius: 7px !important;
                background: transparent !important;
                color: var(--fg-subtle, #888) !important;
                cursor: pointer;
                transition: background-color 0.12s ease, color 0.12s ease, border-color 0.12s ease;
            }
            .onigiri-icon-modal-close:hover {
                background: var(--highlight-bg, rgba(128, 128, 128, 0.14)) !important;
                color: var(--fg, #e8e8e8) !important;
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
                height: 32px !important;
                min-width: 72px !important;
                padding: 0 12px !important;
                border: 1px solid transparent !important;
                border-radius: 8px !important;
                background: transparent !important;
                color: var(--fg-subtle, #888) !important;
                cursor: pointer;
                font-size: 13px !important;
                font-weight: 500 !important;
                transition: background-color 0.12s ease, color 0.12s ease;
            }
            .onigiri-icon-tab:hover {
                background: rgba(128, 128, 128, 0.1) !important;
            }
            .onigiri-icon-tab.active {
                background: var(--highlight-bg, rgba(128, 128, 128, 0.14)) !important;
                color: var(--fg, #e8e8e8) !important;
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
                border: 1px solid var(--border, rgba(128, 128, 128, 0.24));
                border-radius: 9px;
                background: var(--canvas-inset, rgba(128, 128, 128, 0.08));
                color: var(--fg, #e8e8e8);
                padding: 8px 10px;
                margin-bottom: 0;
                outline: none;
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
                color: var(--fg-subtle, #888);
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                padding: 8px 2px 2px;
            }
            .onigiri-icon-cell {
                position: relative;
                height: 60px;
                min-height: 60px;
                display: flex;
                align-items: center;
                justify-content: center;
                box-sizing: border-box;
                border: 1px solid transparent;
                border-radius: 10px;
                background: var(--canvas-inset, rgba(128, 128, 128, 0.07));
                cursor: pointer;
                outline: 1px solid var(--border, rgba(128, 128, 128, 0.16));
                outline-offset: -1px;
                transform: translateZ(0);
                transition: background-color 0.12s ease, outline-color 0.12s ease, box-shadow 0.12s ease;
            }
            .onigiri-icon-cell:hover,
            .onigiri-icon-cell.selected {
                outline-color: var(--accent-color, #007aff);
                box-shadow: inset 0 0 0 1px var(--accent-color, #007aff);
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
                border: 1px solid var(--border, rgba(128, 128, 128, 0.24));
                border-radius: 12px;
                background: var(--canvas-inset, rgba(128, 128, 128, 0.07));
            }
            .onigiri-icon-custom-emoji button {
                height: 32px !important;
                min-width: 118px !important;
                padding: 0 12px !important;
                border: 1px solid var(--border, rgba(128, 128, 128, 0.24)) !important;
                border-radius: 10px !important;
                background: var(--highlight-bg, rgba(128, 128, 128, 0.14)) !important;
                color: var(--fg, #e8e8e8) !important;
                cursor: pointer;
                font-size: 13px !important;
                font-weight: 600 !important;
            }
            .onigiri-icon-custom-emoji button:hover {
                border-color: var(--accent-color, #007aff) !important;
                border-radius: 10px !important;
            }
            .onigiri-icon-custom-emoji input {
                flex: 1;
                min-width: 80px;
                height: 32px;
                border: 1px solid var(--border, rgba(128, 128, 128, 0.24));
                border-radius: 10px;
                background: var(--canvas-overlay, rgba(128, 128, 128, 0.08));
                color: var(--fg, #e8e8e8);
                padding: 0 10px;
                font-size: 18px;
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
                transition: opacity 0.12s ease;
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
                color: var(--fg-subtle, #888);
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
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
                border: 1px solid rgba(255,255,255,0.16);
                box-sizing: border-box;
                transform: translateZ(0);
                transition: box-shadow 0.12s ease, outline-color 0.12s ease;
            }
            .onigiri-icon-swatch:hover {
                outline: 2px solid rgba(128, 128, 128, 0.28);
                outline-offset: 2px;
            }
            .onigiri-icon-swatch.active {
                box-shadow: 0 0 0 2px var(--canvas-overlay, #1f1f1f), 0 0 0 4px currentColor;
            }
            .onigiri-icon-hex {
                width: 82px;
                border: 1px solid var(--border, rgba(128, 128, 128, 0.22));
                border-radius: 8px;
                background: var(--canvas-inset, rgba(128, 128, 128, 0.08));
                color: var(--fg, #e8e8e8);
                padding: 6px 8px;
                outline: none;
            }
            .onigiri-icon-btn {
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                height: 34px !important;
                min-width: 76px !important;
                padding: 0 14px !important;
                border: 1px solid transparent !important;
                border-radius: 8px !important;
                background: var(--highlight-bg, rgba(128, 128, 128, 0.14)) !important;
                color: var(--fg, #e8e8e8) !important;
                cursor: pointer;
                font-size: 13px !important;
                font-weight: 500 !important;
                transition: background-color 0.12s ease, opacity 0.12s ease;
            }
            .onigiri-icon-btn:hover {
                background: rgba(128, 128, 128, 0.22) !important;
                border-radius: 8px !important;
                border-color: transparent !important;
            }
            .onigiri-icon-btn.primary {
                min-width: 72px !important;
                background: var(--accent-color, #007aff) !important;
                color: white !important;
                font-weight: 650 !important;
            }
            .onigiri-icon-btn.primary:hover {
                opacity: 0.88 !important;
                border-radius: 8px !important;
                border-color: transparent !important;
            }
            .onigiri-icon-upload {
                box-sizing: border-box !important;
                width: 100% !important;
                height: 56px !important;
                min-height: 56px !important;
                padding: 0 16px !important;
                border: 1px dashed var(--border, rgba(128, 128, 128, 0.3)) !important;
                border-radius: 10px !important;
                background: transparent !important;
                color: var(--fg, #e8e8e8) !important;
                text-align: center !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                cursor: pointer;
                font-size: 14px !important;
                font-weight: 500 !important;
                transition: border-color 0.12s ease, background-color 0.12s ease, color 0.12s ease;
            }
            .onigiri-icon-upload:hover {
                border-color: var(--accent-color, #007aff) !important;
                background: rgba(128, 128, 128, 0.08) !important;
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

    function buildColorSection() {
        const section = document.createElement("div");
        section.className = "onigiri-icon-color-section";
        const label = document.createElement("div");
        label.className = "onigiri-icon-color-label";
        label.textContent = "Icon Color";
        section.appendChild(label);
        const row = document.createElement("div");
        row.className = "onigiri-icon-swatches";
        const colors = ["#888888", "#ff4d4f", "#ff9f43", "#ffc629", "#45c878", "#4f95ff", "#845ec2", "#ffffff"];
        const setColor = (hex) => {
            state.selectedColor = hex;
            document.documentElement.style.setProperty("--onigiri-selected-icon-color", hex);
            row.querySelectorAll(".onigiri-icon-swatch").forEach(swatch => {
                swatch.classList.toggle("active", swatch.dataset.color.toLowerCase() === hex.toLowerCase());
            });
            hexInput.value = hex;
        };
        colors.forEach(hex => {
            const swatch = document.createElement("span");
            swatch.className = "onigiri-icon-swatch";
            swatch.dataset.color = hex;
            swatch.style.background = hex;
            swatch.style.color = hex;
            swatch.addEventListener("click", () => setColor(hex));
            row.appendChild(swatch);
        });
        const hexInput = document.createElement("input");
        hexInput.className = "onigiri-icon-hex";
        hexInput.maxLength = 7;
        hexInput.addEventListener("input", () => {
            const value = hexInput.value.trim();
            if (/^#[0-9a-fA-F]{6}$/.test(value)) setColor(value);
        });
        row.appendChild(hexInput);
        section.appendChild(row);
        requestAnimationFrame(() => setColor(state.selectedColor || "#888888"));
        return section;
    }

    function open(data) {
        close();
        ensureStyles();
        state.deckId = String(data.deckId || "");
        state.selectedIcon = (data.current && data.current.icon) || "";
        state.selectedColor = (data.current && data.current.color) || "#888888";
        state.emojiBaseUrl = data.emojiBaseUrl || state.emojiBaseUrl;
        state.data = data;
        document.documentElement.style.setProperty("--onigiri-selected-icon-color", state.selectedColor);

        const backdrop = document.createElement("div");
        backdrop.id = "onigiri-icon-backdrop";
        backdrop.addEventListener("click", close);

        const modal = document.createElement("div");
        modal.className = "onigiri-icon-modal";
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
        const spacer = document.createElement("div");
        spacer.style.flex = "1";
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
        footer.appendChild(reset);
        footer.appendChild(spacer);
        footer.appendChild(cancel);
        footer.appendChild(save);
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
