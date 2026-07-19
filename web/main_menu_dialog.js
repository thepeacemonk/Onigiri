/*
    Onigiri Main Menu Settings Dialog

    Web-dialog replacement for the native Qt "Main Menu" settings page.
    Built on the shared OnigiriModal factory (web/onigiri_modal.js).
*/

window.OnigiriMainMenuDialog = window.OnigiriMainMenuDialog || (function () {
    "use strict";

    // ================= Icon helpers =================

    function iconUrl(name) {
        if (window.OnigiriEngine && typeof OnigiriEngine.systemIconUrl === "function") {
            return OnigiriEngine.systemIconUrl(name);
        }
        return "../system_files/system_icons/" + name;
    }

    function maskIcon(className, filename, size) {
        var span = document.createElement("span");
        span.className = className;
        var url = iconUrl(filename);
        span.style.maskImage = "url('" + url + "')";
        span.style.webkitMaskImage = "url('" + url + "')";
        // inline-block required: bare <span> collapses to 0×0 with explicit
        // width/height because inline elements ignore size properties.
        span.style.display = "inline-block";
        span.style.flexShrink = "0";
        if (size) { span.style.width = size + "px"; span.style.height = size + "px"; }
        return span;
    }

    // ================= Generic DOM helpers =================

    function el(tag, className, text) {
        var e = document.createElement(tag);
        if (className) e.className = className;
        if (text != null) e.textContent = text;
        return e;
    }

    // Small info icon with a hover tooltip. Use sparingly — only where a
    // label needs supplementary context that would otherwise force a
    // permanently-visible description line for every row.
    function infoIcon(tipText) {
        var i = maskIcon("mm-info-icon", "info_circle.svg", 14);
        i.setAttribute("data-tip", tipText);
        return i;
    }

    function labelLine(labelText, infoText) {
        var line = el("div", "mm-row-label-line");
        line.appendChild(el("span", "mm-row-label", labelText));
        if (infoText) line.appendChild(infoIcon(infoText));
        return line;
    }

    function row(labelText, descText, controlEl, opts) {
        opts = opts || {};
        var r = el("div", "mm-row" + (opts.noBorder ? " no-border" : ""));
        var text = el("div", "mm-row-text");
        text.appendChild(labelLine(labelText, opts.info));
        if (descText) text.appendChild(el("div", "mm-row-desc", descText));
        r.appendChild(text);
        var control = el("div", "mm-row-control");
        control.appendChild(controlEl);
        r.appendChild(control);
        return r;
    }

    function sectionTitle(text) { return el("div", "mm-section-title", text); }
    function sectionDesc(text)  { return el("div", "mm-section-desc", text); }

    // A lower-tier heading for a sub-concept within a section (e.g.
    // "Background style" inside the "Widgets" tab) — visually smaller/muted
    // than sectionTitle so it doesn't compete with it, with an optional
    // control (like a segmented picker) inline on the same row.
    function subhead(labelText, controlEl, infoText) {
        var h = el("div", "mm-subhead");
        var left = el("div", "mm-subhead-label-line");
        left.appendChild(el("span", "mm-subhead-label", labelText));
        if (infoText) left.appendChild(infoIcon(infoText));
        h.appendChild(left);
        if (controlEl) h.appendChild(controlEl);
        return h;
    }

    // A row containing two labeled swatches side by side (Light / Dark).
    function pairedSwatchRow(label, desc, pairs, opts) {
        opts = opts || {};
        var r = el("div", "mm-row" + (opts.noBorder ? " no-border" : ""));
        var text = el("div", "mm-row-text");
        text.appendChild(labelLine(label, opts.info));
        if (desc) text.appendChild(el("div", "mm-row-desc", desc));
        r.appendChild(text);
        var control = el("div", "mm-row-control mm-pair");
        pairs.forEach(function (p) {
            var item = el("div", "mm-pair-item");
            item.appendChild(el("span", "mm-pair-item-label", p.label));
            item.appendChild(p.swatch.el);
            control.appendChild(item);
        });
        r.appendChild(control);
        return r;
    }

    // ================= Controls =================

    function toggle(initial, onChange) {
        var t = el("button", "mm-toggle" + (initial ? " is-on" : ""));
        t.type = "button";
        t.appendChild(el("span", "mm-toggle-knob"));
        var value = !!initial;
        t.addEventListener("click", function () {
            value = !value;
            t.classList.toggle("is-on", value);
            onChange(value);
        });
        return {
            el: t,
            get: function () { return value; },
            set: function (v) { value = !!v; t.classList.toggle("is-on", value); }
        };
    }

    function segmented(options, initialValue, onChange) {
        var wrap = el("div", "mm-segmented");
        var current = initialValue;
        var buttons = [];
        options.forEach(function (opt) {
            var btn = el("button", "mm-segment" + (opt.value === current ? " is-active" : ""), opt.label);
            btn.type = "button";
            btn.addEventListener("click", function () {
                if (current === opt.value) return;
                current = opt.value;
                buttons.forEach(function (b) { b.el.classList.toggle("is-active", b.opt.value === current); });
                onChange(current);
            });
            buttons.push({ el: btn, opt: opt });
            wrap.appendChild(btn);
        });
        return {
            el: wrap,
            get: function () { return current; },
            set: function (v) {
                current = v;
                buttons.forEach(function (b) { b.el.classList.toggle("is-active", b.opt.value === current); });
            }
        };
    }

    function numberInput(min, max, initial, onChange, unitLabel) {
        var wrap = el("div", "mm-number-wrap" + (unitLabel ? " has-unit" : ""));
        var input = el("input", "mm-input");
        input.type = "number";
        input.min = String(min);
        input.max = String(max);
        input.value = String(initial);
        function commit() {
            var v = parseInt(input.value, 10);
            if (isNaN(v)) v = min;
            v = Math.max(min, Math.min(max, v));
            input.value = String(v);
            onChange(v);
        }
        input.addEventListener("change", commit);
        wrap.appendChild(input);
        if (unitLabel) wrap.appendChild(el("span", "mm-number-unit", unitLabel));
        // Custom themed ▲/▼ steppers — suppress native spinner buttons via CSS,
        // wire to commit() so min/max clamping and onChange fire identically to typing.
        var steppers = el("div", "mm-number-steppers");
        var upBtn    = el("button", "mm-number-step");
        upBtn.type   = "button";
        upBtn.appendChild(maskIcon("mm-number-step-icon", "up.svg", 7));
        var downBtn  = el("button", "mm-number-step");
        downBtn.type = "button";
        downBtn.appendChild(maskIcon("mm-number-step-icon", "down.svg", 7));
        function step(delta) {
            var v = parseInt(input.value, 10);
            if (isNaN(v)) v = min;
            v = Math.max(min, Math.min(max, v + delta));
            input.value = String(v);
            onChange(v);
        }
        upBtn.addEventListener("click",   function (e) { e.preventDefault(); step(1);  });
        downBtn.addEventListener("click", function (e) { e.preventDefault(); step(-1); });
        steppers.appendChild(upBtn);
        steppers.appendChild(downBtn);
        wrap.appendChild(steppers);
        return {
            el: wrap,
            get: function () { return parseInt(input.value, 10); },
            set: function (v) { input.value = String(v); }
        };
    }

    function textInput(initial, onChange, wide, placeholder) {
        var input = el("input", "mm-input" + (wide ? " mm-input-wide" : ""));
        input.type = "text";
        input.value = initial || "";
        if (placeholder) input.placeholder = placeholder;
        input.addEventListener("input", function () { onChange(input.value); });
        return { el: input, get: function () { return input.value; }, set: function (v) { input.value = v; } };
    }

    var openDropdownCloser = null;

    function dropdown(options, initialValue, onChange) {
        var wrap = el("div", "mm-dropdown");
        var trigger = el("button", "mm-dropdown-trigger");
        trigger.type = "button";
        var labelSpan = el("span");
        trigger.appendChild(labelSpan);
        trigger.appendChild(maskIcon("mm-dropdown-chevron", "down.svg"));
        var menu = el("div", "mm-dropdown-menu");
        var current = initialValue;

        function optionLabel(v) {
            var found = options.filter(function (o) { return o.value === v; })[0];
            return found ? found.label : "";
        }
        function close() { menu.classList.remove("is-open"); }
        function renderMenu() {
            menu.innerHTML = "";
            options.forEach(function (opt) {
                var item = el("div", "mm-dropdown-option" + (opt.value === current ? " is-selected" : ""));
                item.appendChild(el("span", "", opt.label));
                if (opt.value === current) item.appendChild(maskIcon("mm-dropdown-check", "tick.svg"));
                item.addEventListener("click", function () {
                    current = opt.value;
                    labelSpan.textContent = optionLabel(current);
                    renderMenu();
                    close();
                    onChange(current);
                });
                menu.appendChild(item);
            });
        }
        trigger.addEventListener("click", function (evt) {
            evt.stopPropagation();
            var willOpen = !menu.classList.contains("is-open");
            if (openDropdownCloser) openDropdownCloser();
            if (willOpen) { menu.classList.add("is-open"); openDropdownCloser = close; }
            else { openDropdownCloser = null; }
        });
        labelSpan.textContent = optionLabel(current);
        renderMenu();
        wrap.appendChild(trigger);
        wrap.appendChild(menu);
        return {
            el: wrap,
            get: function () { return current; },
            set: function (v) { current = v; labelSpan.textContent = optionLabel(current); renderMenu(); }
        };
    }

    function slider(min, max, initial, step, onChange, opts) {
        opts = opts || {};
        var wrap = el("div", "mm-slider-row" + (opts.noBorder ? " no-border" : ""));
        var head = el("div", "mm-slider-head");
        head.appendChild(el("span", "mm-slider-label", opts.label || ""));
        var valueEl = el("span", "mm-slider-value");
        head.appendChild(valueEl);
        wrap.appendChild(head);

        var track = el("div", "mm-slider-track");
        var fill  = el("div", "mm-slider-fill");
        var thumb = el("div", "mm-slider-thumb");
        track.appendChild(fill);
        track.appendChild(thumb);
        wrap.appendChild(track);

        // Hairline tick marks inside the track (skip edge ticks so they don't bleed)
        var innerTicksEl = el("div", "mm-slider-inner-ticks");
        var tickCount = 5; // positions: 0%, 25%, 50%, 75%, 100%
        for (var ti = 0; ti < tickCount; ti++) {
            if (ti === 0 || ti === tickCount - 1) continue; // skip edges
            var pctT = (ti / (tickCount - 1)) * 100;
            var itick = el("span", "mm-slider-inner-tick");
            itick.style.left = pctT + "%";
            innerTicksEl.appendChild(itick);
        }
        track.appendChild(innerTicksEl);

        // Min / mid / max labels below track
        var labelsEl = el("div", "mm-slider-labels");
        [0, 50, 100].forEach(function (pct, i) {
            var rawV = min + (pct / 100) * (max - min);
            var snapped = Math.round(rawV / step) * step;
            var txt = opts.suffix ? snapped + opts.suffix : String(snapped);
            labelsEl.appendChild(el("span", "mm-slider-label-item", txt));
        });
        wrap.appendChild(labelsEl);

        var value = initial;
        function format(v) { return opts.suffix ? (v + opts.suffix) : String(v); }
        function paint() {
            var pct = ((value - min) / (max - min)) * 100;
            fill.style.width = pct + "%";
            // Position the thumb's left EDGE (not its center) so it never
            // bleeds outside the track box at the 0%/100% extremes.
            thumb.style.left = "calc((100% - 16px) * " + (pct / 100) + ")";
            valueEl.textContent = format(value);
        }
        function setFromClientX(clientX) {
            var rect = track.getBoundingClientRect();
            var pct  = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
            var raw  = min + pct * (max - min);
            value    = Math.max(min, Math.min(max, Math.round(raw / step) * step));
            paint();
        }
        var dragging = false;
        track.addEventListener("pointerdown", function (evt) {
            dragging = true;
            try { track.setPointerCapture(evt.pointerId); } catch (_) {}
            setFromClientX(evt.clientX); onChange(value);
        });
        track.addEventListener("pointermove", function (evt) {
            if (!dragging) return;
            setFromClientX(evt.clientX); onChange(value);
        });
        track.addEventListener("pointerup", function (evt) {
            dragging = false;
            try { track.releasePointerCapture(evt.pointerId); } catch (_) {}
        });
        paint();
        return { el: wrap, get: function () { return value; }, set: function (v) { value = v; paint(); } };
    }

    // Color-swatch colour-picker bridge
    var colorPickRegistry = new Map();
    var colorPickCounter  = 0;

    function swatch(initialHex, onChange) {
        var wrap = el("div", "mm-swatch");
        var chip = el("span", "mm-swatch-chip");
        chip.style.background = initialHex;
        var hexEl = el("span", "mm-swatch-hex", String(initialHex || "").toUpperCase());
        wrap.appendChild(chip);
        wrap.appendChild(hexEl);
        var current = initialHex;
        var pickId  = "swatch-" + (++colorPickCounter);
        colorPickRegistry.set(pickId, function (hex) {
            current = hex;
            chip.style.background = hex;
            hexEl.textContent = hex.toUpperCase();
            onChange(hex);
        });
        wrap.addEventListener("click", function () {
            if (typeof pycmd !== "function") return;
            pycmd("onigiri_mainmenu_pick_color:" + encodeURIComponent(JSON.stringify({ pickId: pickId, current: current })));
        });
        return {
            el:  wrap,
            get: function () { return current; },
            set: function (v) {
                current = v;
                chip.style.background = v;
                hexEl.textContent = v.toUpperCase();
                // Also fire the registry so live previews update
                onChange(v);
            }
        };
    }

    // Icon-picker bridge
    var iconPickRegistry = new Map();
    var iconPickCounter  = 0;

    function heatmapIconUrl(filename) {
        var pkg = state.draft && state.draft.config && state.draft.config.addonPackage;
        return pkg ? "/_addons/" + pkg + "/system_files/heatmap_system_icons/" + filename
            : "../system_files/heatmap_system_icons/" + filename;
    }

    function mainBgImageUrl(filename) {
        var pkg = state.draft && state.draft.config && state.draft.config.addonPackage;
        return pkg ? "/_addons/" + pkg + "/user_files/main_bg/" + filename
            : "../user_files/main_bg/" + filename;
    }

    // Strips any picker prefix ("system:", "emoji:") so callers get a plain
    // { kind: "file"|"emoji", value } — one source of truth for all icon
    // rendering paths (preview cells, streak icon, icon-picker button glyph).
    function resolveIcon(value) {
        var text = String(value || "");
        if (text.indexOf("emoji:") === 0) return { kind: "emoji", value: text.slice(6) };
        var filename = text.indexOf("system:") === 0 ? text.slice(7) : (text || "square.svg");
        return { kind: "file", value: filename };
    }

    // URL for an icon value as returned by the picker (handles "system:" prefix).
    // "system:X" means the icon came from available_for_users/ in the picker dialog;
    // bare filenames (e.g. "star_filled.svg") are root system_icons/ assets.
    function resolvedIconUrl(iconValue) {
        var text = String(iconValue || "");
        if (text.indexOf("system:") === 0) {
            var name = text.slice(7);
            var pkg = state.draft && state.draft.config && state.draft.config.addonPackage;
            return pkg ? "/_addons/" + pkg + "/system_files/system_icons/available_for_users/" + name
                : "../system_files/system_icons/available_for_users/" + name;
        }
        return iconUrl(text);
    }

    // Build the small icon glyph shown inside an iconPickerButton.
    // folder="heatmap" → heatmap_system_icons/ (strip any "system:" prefix first).
    // All other icons with "system:" prefix → available_for_users/ via resolvedIconUrl.
    // Bare filenames without a prefix → root system_icons/ via iconUrl.
    function buildIconGlyph(iconValue, folder) {
        var resolved = resolveIcon(iconValue);
        if (resolved.kind === "emoji") {
            var span = el("span", "", resolved.value);
            span.style.fontSize = "13px";
            return span;
        }
        var url = folder === "heatmap" ? heatmapIconUrl(resolved.value) : resolvedIconUrl(iconValue);
        var glyph = el("span", "mm-icon-picker-preview-glyph");
        glyph.style.maskImage = "url('" + url + "')";
        glyph.style.webkitMaskImage = "url('" + url + "')";
        glyph.style.display = "inline-block";
        return glyph;
    }

    function iconPickerButton(currentIconValue, colorOptions, previewColorKey, onApply, folder) {
        var btn = el("button", "mm-icon-picker-btn");
        btn.type = "button";
        var preview = el("span", "mm-icon-picker-preview");
        preview.appendChild(buildIconGlyph(currentIconValue, folder));
        btn.appendChild(preview);
        btn.appendChild(el("span", "", "Choose icon…"));

        var pickId       = "icon-" + (++iconPickCounter);
        var currentValue = currentIconValue;
        iconPickRegistry.set(pickId, function (result) {
            currentValue = result.icon || currentValue;
            preview.innerHTML = "";
            preview.appendChild(buildIconGlyph(currentValue, folder));
            onApply(result);
        });
        btn.addEventListener("click", function () {
            if (typeof pycmd !== "function") return;
            pycmd("onigiri_mainmenu_pick_icon:" + encodeURIComponent(JSON.stringify({
                pickId: pickId, currentIcon: currentValue,
                colorOptions: colorOptions || [], previewColorKey: previewColorKey || null
            })));
        });
        return {
            el:  btn,
            set: function (v) { currentValue = v; preview.innerHTML = ""; preview.appendChild(buildIconGlyph(v, folder)); }
        };
    }

    var pendingBgCallback = null;

    // ================= Sidebar nav =================

    var NAV_DATA = [
        { title: "General", items: [
            { icon: "profile.svg",                    label: "Profile",   active: false },
            { icon: "modes.svg",                      label: "Modes",     active: false },
            { icon: "languages.svg",                  label: "Languages", active: false },
            { icon: "fonts.svg",                      label: "Fonts",     active: false },
            { icon: "themes.svg",                     label: "Themes",    active: false },
            { icon: "gallery.svg",                    label: "Gallery",   active: false },
            { icon: "sync.svg",                       label: "Sync",      active: false }
        ]},
        { title: "Menu", items: [
            { icon: "main_menu.svg", label: "Main Menu", active: true  },
            { icon: "sidebar.svg",   label: "Sidebar",   active: false }
        ]},
        { title: "Study pages", items: [
            { icon: "overviewer.svg",                                  label: "Overviewer",   active: false },
            { icon: "reviewer.svg",                                    label: "Reviewer",     active: false },
            { icon: "unavailable_for_users/hg-prep.svg",               label: "Prep Station", active: false },
            { icon: "unavailable_for_users/hashi_notes.svg",           label: "Hashi Notes",  active: false },
            { icon: "unavailable_for_users/hg-pomodoro.svg",           label: "Pomodoro",     active: false }
        ]}
    ];

    // ================= State =================

    var state = {
        draft: null,
        layoutFields: null,
        layoutEditor: null   // handle from OnigiriWidgetLayoutEditor.mountInline
    };

    // The slice of state.draft the inline layout editor reads from.
    function layoutSlice() {
        return {
            onigiriWidgetLayout:  state.draft.json.onigiriWidgetLayout,
            externalWidgetLayout: state.draft.json.externalWidgetLayout,
            unifiedGridRows:      state.draft.json.unifiedGridRows,
            externalHooks:        state.draft.externalHooks || []
        };
    }

    // Merge a serialized editor result back into state.draft so the host
    // dialog's own Save persists it. Object.assign keeps the same object
    // references the Grid Size fields captured, so those stay valid.
    function applyLayoutResult(result) {
        var j = state.draft.json;
        j.onigiriWidgetLayout  = Object.assign(j.onigiriWidgetLayout  || {}, result.onigiriWidgetLayout);
        j.externalWidgetLayout = Object.assign(j.externalWidgetLayout || {}, result.externalWidgetLayout);
        j.unifiedGridRows      = result.unifiedGridRows;
    }

    // ================= Tab: Layout =================

    function renderLayoutTab(panel) {
        panel.appendChild(sectionTitle("Layout"));
        panel.appendChild(sectionDesc("The title, grid size, and widget placement on your main menu."));

        var titleField = textInput(
            state.draft.colConf.modern_menu_statsTitle,
            function (v) { state.draft.colConf.modern_menu_statsTitle = v; },
            true,
            "e.g. Today’s Progress"
        );
        panel.appendChild(row("Title", "Shown above your widget grid.", titleField.el));

        panel.appendChild(subhead("Grid Size"));
        panel.appendChild(sectionDesc("Size and position of the widget grid on the main menu."));

        var layout = state.draft.json.onigiriWidgetLayout || (state.draft.json.onigiriWidgetLayout = {});

        // Rows/Columns change the abstract editor grid, so they reload it.
        // Width/Height/Alignment don't affect the editor's own layout (they
        // style the real dashboard), but reloading keeps the editor's stored
        // copies of them in sync so its serialize round-trips correctly.
        function reloadEditor() { if (state.layoutEditor) state.layoutEditor.reload(); }

        var rowsField = numberInput(0, 200, state.draft.json.unifiedGridRows != null ? state.draft.json.unifiedGridRows : 6, function (v) {
            state.draft.json.unifiedGridRows = v; reloadEditor();
        });
        var colsField = numberInput(0, 6, layout.column_count != null ? layout.column_count : 4, function (v) {
            layout.column_count = v; reloadEditor();
        });
        var widthField = numberInput(200, 340, layout.grid_width != null ? layout.grid_width : 230, function (v) {
            layout.grid_width = v; reloadEditor();
        }, "px");
        var heightField = numberInput(120, 320, layout.widget_height != null ? layout.widget_height : 120, function (v) {
            layout.widget_height = v; reloadEditor();
        }, "px");
        var alignField = segmented([
            { value: "left",   label: "Left"   },
            { value: "center", label: "Center" },
            { value: "right",  label: "Right"  }
        ], layout.grid_alignment || "center", function (v) { layout.grid_alignment = v; reloadEditor(); });

        panel.appendChild(row("Rows",      "", rowsField.el));
        panel.appendChild(row("Columns",   "", colsField.el));
        panel.appendChild(row("Width",     "", widthField.el));
        panel.appendChild(row("Height",    "", heightField.el));
        panel.appendChild(row("Alignment", "", alignField.el, { noBorder: true }));

        state.layoutFields = { rows: rowsField, cols: colsField, width: widthField, align: alignField, height: heightField };

        panel.appendChild(subhead("Widget layout"));
        panel.appendChild(sectionDesc("Drag widgets to rearrange. Double-tap a widget to rename or resize it. Drag to the archive to remove it."));

        // Embedded, preview-style layout editor (no separate modal / Save —
        // edits live-persist into state.draft and go out with the dialog's
        // own Save). Gracefully no-op if the editor script isn't present.
        if (window.OnigiriWidgetLayoutEditor && typeof OnigiriWidgetLayoutEditor.mountInline === "function") {
            var editorHost = el("div", "mm-layout-editor");
            panel.appendChild(editorHost);
            state.layoutEditor = OnigiriWidgetLayoutEditor.mountInline(editorHost, {
                getSlice: layoutSlice,
                onChange: applyLayoutResult,
                widgetNames: state.draft.widgets || {}
            });

            var btnRow = el("div", "mm-btn-row no-border");
            var resetNamesBtn = el("button", "mm-inline-btn", "Reset names");
            resetNamesBtn.type = "button";
            resetNamesBtn.addEventListener("click", function () { if (state.layoutEditor) state.layoutEditor.resetNames(); });
            var resetLayoutBtn = el("button", "mm-inline-btn", "Reset layout to default");
            resetLayoutBtn.type = "button";
            resetLayoutBtn.addEventListener("click", function () {
                if (state.layoutEditor) state.layoutEditor.resetLayout();
                refreshLayoutFieldsFromDraft();
            });
            btnRow.appendChild(resetNamesBtn);
            btnRow.appendChild(resetLayoutBtn);
            panel.appendChild(btnRow);
        }
    }

    // "Reset layout to default" changes rows/cols/width/height/alignment
    // inside the editor and echoes them back into state.draft — pull those
    // back into the Grid Size number fields so they don't show stale values.
    function refreshLayoutFieldsFromDraft() {
        var f = state.layoutFields;
        if (!f) return;
        var layout = state.draft.json.onigiriWidgetLayout || {};
        f.rows.set(state.draft.json.unifiedGridRows != null ? state.draft.json.unifiedGridRows : 6);
        f.cols.set(layout.column_count    != null ? layout.column_count    : 4);
        f.width.set(layout.grid_width     != null ? layout.grid_width      : 230);
        f.height.set(layout.widget_height != null ? layout.widget_height   : 120);
        f.align.set(layout.grid_alignment || "center");
    }

    // ================= Color helpers =================

    function colorGet(mode, key) {
        var colors = state.draft.json.colors || {};
        return (colors[mode] || {})[key];
    }
    function colorSet(mode, key, hex) {
        var colors = state.draft.json.colors || (state.draft.json.colors = {});
        var branch = colors[mode] || (colors[mode] = {});
        branch[key] = hex;
    }

    // ================= Preview card with light/dark toggle =================

    // Sun/moon icon toggle shared by every "Preview" card head — switches
    // ONLY the preview's own rendering between dark/light, never a real
    // setting. onToggle(isLight) fires on every click.
    function previewThemeToggle(onToggle) {
        var btn = el("button", "mm-preview-theme-btn");
        btn.type = "button";
        btn.title = "Toggle preview between dark and light mode";
        var isDark = true;
        var icon = maskIcon("mm-preview-theme-icon", "moon.svg", 13);
        btn.appendChild(icon);
        btn.addEventListener("click", function () {
            isDark = !isDark;
            btn.classList.toggle("is-light", !isDark);
            var url = iconUrl(isDark ? "moon.svg" : "sun.svg");
            icon.style.maskImage = "url('" + url + "')";
            icon.style.webkitMaskImage = icon.style.maskImage;
            onToggle(!isDark);
        });
        return { el: btn, isDark: function () { return isDark; } };
    }

    function buildLivePreviewCard(sampleBuilder, onThemeChange) {
        var card    = el("div", "mm-preview-card");
        var head    = el("div", "mm-preview-head");
        var label   = el("span", "mm-preview-head-label", "Preview");
        head.appendChild(label);

        var themeToggle = previewThemeToggle(function (isLight) {
            card.classList.toggle("is-light-preview", isLight);
            if (onThemeChange) onThemeChange(isLight);
        });
        head.appendChild(themeToggle.el);
        card.appendChild(head);

        var body   = el("div", "mm-preview-body");
        var sample = sampleBuilder();
        body.appendChild(sample);
        card.appendChild(body);
        return { card: card, sample: sample };
    }

    // ================= Tab: Appearance — Widgets =================

    function renderWidgetCardsTab(panel) {
        panel.appendChild(sectionTitle("Widgets"));
        panel.appendChild(sectionDesc("Applies to every card on your dashboard."));

        var previewIsLight = false;

        function currentCardBackground(mode) {
            var styleMode = state.draft.colConf.onigiri_widget_bg_mode === "solid" ? "solid"
                : (state.draft.colConf.onigiri_widget_bg_main_effect_mode === "opaque" ? "tint" : "glass");
            if (styleMode === "solid") {
                var solidColor = colorGet(mode, "--canvas-inset") || (mode === "light" ? "#ffffff" : "#2c2c2c");
                return solidColor;
            }
            if (styleMode === "tint") {
                var tintColor = mode === "light"
                    ? (state.draft.colConf.onigiri_widget_bg_main_tint_color_light || "#ffffff")
                    : (state.draft.colConf.onigiri_widget_bg_main_tint_color_dark  || "#2c2c2c");
                var tintIntensity = state.draft.colConf.onigiri_widget_bg_main_tint_intensity != null ? state.draft.colConf.onigiri_widget_bg_main_tint_intensity : 30;
                return "color-mix(in srgb," + tintColor + " " + tintIntensity + "%, transparent)";
            }
            var glassIntensity = state.draft.colConf.onigiri_widget_bg_main_effect_intensity != null ? state.draft.colConf.onigiri_widget_bg_main_effect_intensity : 50;
            var base = mode === "light" ? "255,255,255" : "0,0,0";
            return "rgba(" + base + "," + (glassIntensity / 100) + ")";
        }

        // Holds references to Retention card star elements for live updates in paintPreview.
        var retentionStarRatingEl = null;

        function paintPreview() {
            var mode        = previewIsLight ? "light" : "dark";
            var borderColor = colorGet(mode, "--border") || (mode === "light" ? "#e0e0e0" : "#3a3a3a");
            var isGlass     = state.draft.colConf.onigiri_widget_bg_mode !== "solid"
                && state.draft.colConf.onigiri_widget_bg_main_effect_mode !== "opaque";
            preview.sample.style.background           = currentCardBackground(mode);
            preview.sample.style.backdropFilter       = isGlass ? "blur(14px)" : "none";
            preview.sample.style.webkitBackdropFilter = preview.sample.style.backdropFilter;
            preview.sample.style.borderRadius         = "15px";
            preview.sample.style.border               = "1px solid " + borderColor;
            var titleEl = preview.sample.querySelector(".mm-preview-retention-title");
            var valueEl = preview.sample.querySelector(".mm-preview-retention-value");
            if (titleEl) titleEl.style.color = previewIsLight ? "#7a7a7a" : "#9a9a9a";
            if (valueEl) valueEl.style.color = previewIsLight ? "#222222" : "#ededed";
            // Update retention stars
            if (retentionStarRatingEl) {
                var hideStars = !!state.draft.json.hideRetentionStars;
                retentionStarRatingEl.style.display = hideStars ? "none" : "flex";
                var starIconFile = state.draft.colConf.modern_menu_icon_retention_star || "star_filled.svg";
                var starIconUrl = resolvedIconUrl(starIconFile);
                var starColor = colorGet(mode, "--star-color") || (mode === "light" ? "#f5a623" : "#ffe082");
                var emptyColor = colorGet(mode, "--empty-star-color") || (mode === "light" ? "#d0d0d0" : "#4a4a4a");
                retentionStarRatingEl.querySelectorAll(".mm-preview-star").forEach(function (star) {
                    star.style.maskImage = "url('" + starIconUrl + "')";
                    star.style.webkitMaskImage = "url('" + starIconUrl + "')";
                    star.style.backgroundColor = star.classList.contains("empty") ? emptyColor : starColor;
                });
            }
        }

        // Replicates onigiri_renderer.py:1332-1343: h3 "Retention" +
        // .retention-content > p "92%" + .star-rating with 5 star elements.
        var preview = buildLivePreviewCard(function () {
            var sample = el("div");
            sample.style.cssText = "width:230px;min-height:120px;padding:20px;display:flex;flex-direction:column;text-align:center;box-sizing:border-box;";
            var title = el("h3", "mm-preview-retention-title", "Retention");
            title.style.cssText = "margin:0 0 12px;font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform: uppercase;";
            var content = el("div");
            content.style.cssText = "flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;";
            var value = el("p", "mm-preview-retention-value", "92%");
            value.style.cssText = "margin:0;font-size:28px;font-weight:600;";
            var starRating = el("div");
            starRating.style.cssText = "display:flex;gap:4px;align-items:center;";
            for (var s = 0; s < 5; s++) {
                var star = el("i", "mm-preview-star" + (s >= 4 ? " empty" : ""));
                star.style.cssText = "display:inline-block;width:20px;height:20px;flex-shrink:0;mask-size:contain;-webkit-mask-size:contain;mask-repeat:no-repeat;-webkit-mask-repeat:no-repeat;mask-position:center;-webkit-mask-position:center;";
                starRating.appendChild(star);
            }
            retentionStarRatingEl = starRating;
            content.appendChild(value);
            content.appendChild(starRating);
            sample.appendChild(title);
            sample.appendChild(content);
            return sample;
        }, function (isLight) {
            previewIsLight = isLight;
            paintPreview();
        });
        panel.appendChild(preview.card);
        paintPreview();

        // ---- Background style: the ONLY thing that sets the real card colour ----
        // Demoted below "Widgets" in the heading hierarchy (mm-subhead, not
        // sectionTitle) since it's a sub-concept of the widgets tab, not a
        // sibling top-level section — and its control sits inline with the
        // heading itself rather than in a separate "Style" row underneath.
        var initialMode = state.draft.colConf.onigiri_widget_bg_mode === "solid" ? "solid"
            : (state.draft.colConf.onigiri_widget_bg_main_effect_mode === "opaque" ? "tint" : "glass");

        var styleDescriptions = {
            glass: "Blurs what's behind the card.",
            tint:  "Washes the card with a translucent colour.",
            solid: "A flat, fully opaque fill."
        };
        var styleDesc = sectionDesc(styleDescriptions[initialMode]);

        var styleField = segmented([
            { value: "glass", label: "Glass" },
            { value: "tint",  label: "Tint"  },
            { value: "solid", label: "Solid" }
        ], initialMode, function (v) {
            if (v === "solid") {
                state.draft.colConf.onigiri_widget_bg_mode = "solid";
            } else {
                state.draft.colConf.onigiri_widget_bg_mode = "main";
                state.draft.colConf.onigiri_widget_bg_main_effect_mode = v === "tint" ? "opaque" : "glassmorphism";
            }
            styleDesc.textContent = styleDescriptions[v];
            refreshVisibility(v);
            paintPreview();
        });
        panel.appendChild(subhead("Background style", styleField.el));
        panel.appendChild(styleDesc);

        var glassField = slider(0, 100, state.draft.colConf.onigiri_widget_bg_main_effect_intensity != null ? state.draft.colConf.onigiri_widget_bg_main_effect_intensity : 50, 1, function (v) {
            state.draft.colConf.onigiri_widget_bg_main_effect_intensity = v; paintPreview();
        }, { label: "Glass intensity", suffix: "%" });
        var glassRow = glassField.el;

        var tintIntensityField = slider(0, 100, state.draft.colConf.onigiri_widget_bg_main_tint_intensity != null ? state.draft.colConf.onigiri_widget_bg_main_tint_intensity : 30, 1, function (v) {
            state.draft.colConf.onigiri_widget_bg_main_tint_intensity = v; paintPreview();
        }, { label: "Tint intensity", suffix: "%" });
        var tintIntensityRow = tintIntensityField.el;

        var tintLightSwatch = swatch(state.draft.colConf.onigiri_widget_bg_main_tint_color_light || "#ffffff", function (hex) {
            state.draft.colConf.onigiri_widget_bg_main_tint_color_light = hex; paintPreview();
        });
        var tintDarkSwatch = swatch(state.draft.colConf.onigiri_widget_bg_main_tint_color_dark || "#2c2c2c", function (hex) {
            state.draft.colConf.onigiri_widget_bg_main_tint_color_dark = hex; paintPreview();
        });
        var tintColorRow = pairedSwatchRow("Tint colour", "", [{ label: "Light", swatch: tintLightSwatch }, { label: "Dark", swatch: tintDarkSwatch }]);

        var solidLightSwatch = swatch(colorGet("light", "--canvas-inset") || "#ffffff", function (hex) {
            colorSet("light", "--canvas-inset", hex); paintPreview();
        });
        var solidDarkSwatch = swatch(colorGet("dark", "--canvas-inset") || "#2c2c2c", function (hex) {
            colorSet("dark", "--canvas-inset", hex); paintPreview();
        });
        var solidColorRow = pairedSwatchRow("Card colour", "", [{ label: "Light", swatch: solidLightSwatch }, { label: "Dark", swatch: solidDarkSwatch }]);

        var themeAwareField = toggle(state.draft.colConf.onigiri_canvas_inset_color_theme_mode === "separate", function (v) {
            state.draft.colConf.onigiri_canvas_inset_color_theme_mode = v ? "separate" : "single";
        });
        var themeAwareRow = row("Theme-aware colour", "Use a different card colour for light and dark mode.", themeAwareField.el);

        // Border colour is closely related to background style (both are
        // "what does the card surface look like") and always real regardless
        // of mode, so it lives here rather than getting its own top-level
        // "Border" section — positioned right after each mode's own colour
        // row (Card colour for solid, Tint colour for tint, Glass intensity
        // for glass) since that's the row it's most directly tied to.
        var borderLightSwatch = swatch(colorGet("light", "--border") || "#e0e0e0", function (hex) {
            colorSet("light", "--border", hex); paintPreview();
        });
        var borderDarkSwatch = swatch(colorGet("dark", "--border") || "#3a3a3a", function (hex) {
            colorSet("dark", "--border", hex); paintPreview();
        });
        var borderColourRow = pairedSwatchRow("Border colour", "",
            [{ label: "Light", swatch: borderLightSwatch }, { label: "Dark", swatch: borderDarkSwatch }]
        );

        panel.appendChild(glassRow);
        panel.appendChild(tintIntensityRow);
        panel.appendChild(tintColorRow);
        panel.appendChild(solidColorRow);
        panel.appendChild(borderColourRow);
        panel.appendChild(themeAwareRow);

        var widgetStyleRows = [glassRow, tintIntensityRow, tintColorRow, solidColorRow, borderColourRow, themeAwareRow];
        function refreshVisibility(styleValue) {
            glassRow.style.display        = styleValue === "glass" ? "" : "none";
            tintIntensityRow.style.display = styleValue === "tint"  ? "" : "none";
            tintColorRow.style.display     = styleValue === "tint"  ? "" : "none";
            solidColorRow.style.display    = styleValue === "solid" ? "" : "none";
            themeAwareRow.style.display    = styleValue === "solid" ? "" : "none";
            widgetStyleRows.forEach(function (r) { r.classList.remove("no-border"); });
            var visible = widgetStyleRows.filter(function (r) { return r.style.display !== "none"; });
            if (visible.length) visible[visible.length - 1].classList.add("no-border");
        }
        refreshVisibility(initialMode);

        // ---- Retention Stars: unrelated to card surface, its own sub-topic ----
        panel.appendChild(subhead("Retention Stars"));
        panel.appendChild(sectionDesc("The star rating shown on the Retention card."));

        function starSwatch(mode, key, defaultLight, defaultDark) {
            var def = mode === "light" ? defaultLight : defaultDark;
            return swatch(colorGet(mode, key) || def, function (hex) { colorSet(mode, key, hex); });
        }
        var starLightSwatch  = starSwatch("light", "--star-color",       "#f5a623", "#ffe082");
        var starDarkSwatch   = starSwatch("dark",  "--star-color",       "#f5a623", "#ffe082");
        var emptyLightSwatch = starSwatch("light", "--empty-star-color", "#d0d0d0", "#4a4a4a");
        var emptyDarkSwatch  = starSwatch("dark",  "--empty-star-color", "#d0d0d0", "#4a4a4a");

        panel.appendChild(pairedSwatchRow("Star colour",       "", [{ label: "Light", swatch: starLightSwatch  }, { label: "Dark", swatch: starDarkSwatch  }]));
        panel.appendChild(pairedSwatchRow("Empty star colour", "", [{ label: "Light", swatch: emptyLightSwatch }, { label: "Dark", swatch: emptyDarkSwatch }]));

        var hideStarsField = toggle(!!state.draft.json.hideRetentionStars, function (v) {
            state.draft.json.hideRetentionStars = v;
            paintPreview();
        });
        panel.appendChild(row("Hide retention stars", "", hideStarsField.el));

        var retentionIconPicker = iconPickerButton(
            state.draft.colConf.modern_menu_icon_retention_star || "star_filled.svg",
            [], null,
            function (result) { if (result.icon) { state.draft.colConf.modern_menu_icon_retention_star = result.icon; paintPreview(); } }
        );
        panel.appendChild(row("Star icon", "", retentionIconPicker.el, { noBorder: true }));

        // ---- Advanced: shared style values for compatible add-on widgets ----
        // These don't touch the built-in cards above (radius/border there are
        // hardcoded), so they're kept separate and clearly labelled rather
        // than mixed in with settings that actually change what you see.
        panel.appendChild(subhead("Advanced"));
        panel.appendChild(sectionDesc("Used by some compatible add-ons — doesn't affect the cards above."));

        var radiusField  = slider(0, 60, state.draft.colConf.onigiri_canvas_inset_border_radius != null ? state.draft.colConf.onigiri_canvas_inset_border_radius : 14, 1, function (v) {
            state.draft.colConf.onigiri_canvas_inset_border_radius = v;
        }, { label: "Corner radius", suffix: "px" });
        var widthField   = slider(0, 10, state.draft.colConf.onigiri_canvas_inset_border_width != null ? state.draft.colConf.onigiri_canvas_inset_border_width : 1, 1, function (v) {
            state.draft.colConf.onigiri_canvas_inset_border_width = v;
        }, { label: "Border width", suffix: "px" });
        var blurField    = slider(0, 40, state.draft.colConf.onigiri_canvas_inset_effect_blur || 0, 1, function (v) {
            state.draft.colConf.onigiri_canvas_inset_effect_blur = v;
        }, { label: "Background blur", suffix: "px" });
        var opacityField = slider(0, 100, state.draft.colConf.onigiri_canvas_inset_effect_opacity != null ? state.draft.colConf.onigiri_canvas_inset_effect_opacity : 100, 1, function (v) {
            state.draft.colConf.onigiri_canvas_inset_effect_opacity = v;
        }, { label: "Opacity", suffix: "%", noBorder: true });
        panel.appendChild(radiusField.el);
        panel.appendChild(widthField.el);
        panel.appendChild(blurField.el);
        panel.appendChild(opacityField.el);

        // ---- One reset button for the whole tab ----
        var resetBtn = el("button", "mm-inline-btn", "Reset widget card settings to defaults");
        resetBtn.type = "button";
        resetBtn.addEventListener("click", function () {
            state.draft.colConf.onigiri_widget_bg_mode = "main";
            state.draft.colConf.onigiri_widget_bg_main_effect_mode = "glassmorphism";
            state.draft.colConf.onigiri_widget_bg_main_effect_intensity = 50;
            state.draft.colConf.onigiri_widget_bg_main_tint_intensity = 30;
            state.draft.colConf.onigiri_widget_bg_main_tint_color_light = "#ffffff";
            state.draft.colConf.onigiri_widget_bg_main_tint_color_dark  = "#2c2c2c";
            state.draft.colConf.onigiri_widget_bg_solid_transparency = 0;
            state.draft.colConf.onigiri_canvas_inset_color_theme_mode = "single";
            state.draft.colConf.onigiri_canvas_inset_border_radius = 14;
            state.draft.colConf.onigiri_canvas_inset_border_width  = 1;
            state.draft.colConf.onigiri_canvas_inset_effect_blur   = 0;
            state.draft.colConf.onigiri_canvas_inset_effect_opacity= 100;
            colorSet("light", "--canvas-inset", "#ffffff"); colorSet("dark", "--canvas-inset", "#2c2c2c");
            colorSet("light", "--border",        "#e0e0e0"); colorSet("dark", "--border",        "#3a3a3a");
            colorSet("light", "--star-color",       "#f5a623"); colorSet("dark", "--star-color",       "#ffe082");
            colorSet("light", "--empty-star-color", "#d0d0d0"); colorSet("dark", "--empty-star-color", "#4a4a4a");

            styleField.set("glass"); refreshVisibility("glass");
            glassField.set(50); tintIntensityField.set(30);
            tintLightSwatch.set("#ffffff"); tintDarkSwatch.set("#2c2c2c");
            solidLightSwatch.set("#ffffff"); solidDarkSwatch.set("#2c2c2c");
            state.draft.colConf.onigiri_widget_bg_solid_transparency = 0;
            themeAwareField.set(false);
            borderLightSwatch.set("#e0e0e0"); borderDarkSwatch.set("#3a3a3a");
            starLightSwatch.set("#f5a623"); starDarkSwatch.set("#ffe082");
            emptyLightSwatch.set("#d0d0d0"); emptyDarkSwatch.set("#4a4a4a");
            radiusField.set(14); widthField.set(1); blurField.set(0); opacityField.set(100);
            paintPreview();
        });
        var btnRow = el("div", "mm-btn-row no-border");
        btnRow.appendChild(resetBtn);
        panel.appendChild(btnRow);
    }

    // ================= Tab: Appearance — Main Background =================

    function renderMainBackgroundTab(panel) {
        panel.appendChild(sectionTitle("Background"));
        panel.appendChild(sectionDesc("The backdrop shown behind the entire dashboard."));

        var previewIsLight = false;

        function paintPreview(forceLight) {
            var mode      = (forceLight === true) ? "light" : "dark";
            var color     = (mode === "light"
                ? (state.draft.colConf.modern_menu_bg_color_light || "#EEEEEE")
                : (state.draft.colConf.modern_menu_bg_color_dark  || "#3C3C3C"));
            var blur      = state.draft.colConf.modern_menu_background_blur    || 0;
            var opacity   = state.draft.colConf.modern_menu_background_opacity != null
                ? state.draft.colConf.modern_menu_background_opacity : 100;
            var bgMode    = state.draft.colConf.modern_menu_background_mode || "image";
            var imageName = state.draft.colConf.modern_menu_background_image;

            preview.sample.style.background = color;
            if (bgMode !== "color" && imageName) {
                preview.sample.style.backgroundImage    = "url('" + mainBgImageUrl(imageName) + "')";
                preview.sample.style.backgroundSize     = "cover";
                preview.sample.style.backgroundPosition = "center";
            } else {
                preview.sample.style.backgroundImage = "none";
            }
            preview.sample.style.filter  = "blur(" + (blur * 0.2) + "px)";
            preview.sample.style.opacity = String(opacity / 100);
        }

        var preview = buildLivePreviewCard(function () {
            var sample = el("div");
            sample.style.cssText = "width:100%;height:100%;min-height:120px;";
            return sample;
        }, function (isLight) {
            previewIsLight = isLight;
            paintPreview(isLight);
        });
        preview.card.querySelector(".mm-preview-body").style.padding = "0";
        preview.card.querySelector(".mm-preview-body").style.overflow = "hidden";
        panel.appendChild(preview.card);
        paintPreview();

        // Style: exactly two real options, Image or Colour — matching the
        // same picker-above-mode-specific-fields pattern as the Widgets
        // tab's Background style. Slideshow is a sub-feature of Image (it
        // just cycles through gallery images automatically), not a third
        // competing top-level mode, so it lives nested under Image instead
        // of being its own independent toggle that silently fights "Solid
        // colour only" for the same underlying mode value.
        var bgStyleDescriptions = {
            image: "A photo or gallery image, optionally cycling automatically.",
            solid: "A flat colour instead of an image."
        };
        var initialBgStyle = state.draft.colConf.modern_menu_background_mode === "color" ? "solid" : "image";
        var bgStyleDesc = sectionDesc(bgStyleDescriptions[initialBgStyle]);

        var bgStyleField = segmented([
            { value: "image", label: "Image" },
            { value: "solid", label: "Solid" }
        ], initialBgStyle, function (v) {
            state.draft.colConf.modern_menu_background_mode = v === "solid" ? "color" : (slideshowField.get() ? "slideshow" : "image");
            bgStyleDesc.textContent = bgStyleDescriptions[v];
            refreshBgVisibility(v);
            paintPreview(previewIsLight);
        });
        panel.appendChild(subhead("Style", bgStyleField.el));
        panel.appendChild(bgStyleDesc);

        // ---- Image-mode fields ----
        var btnRow  = el("div", "mm-btn-row");
        var importBtn = el("button", "mm-inline-btn", "Import…");
        importBtn.type = "button";
        importBtn.addEventListener("click", function () {
            if (typeof pycmd !== "function") return;
            pendingBgCallback = function (result) {
                if (result && result.filename) {
                    state.draft.colConf.modern_menu_background_image = result.filename;
                    paintPreview(previewIsLight);
                }
            };
            pycmd("onigiri_mainmenu_import_bg:{}");
        });
        var galleryBtn = el("button", "mm-inline-btn", "Select from gallery…");
        galleryBtn.type = "button";
        galleryBtn.addEventListener("click", function () {
            if (typeof pycmd !== "function") return;
            pendingBgCallback = function (result) {
                if (result && result.filename) {
                    state.draft.colConf.modern_menu_background_image = result.filename;
                    paintPreview(previewIsLight);
                }
            };
            pycmd("onigiri_mainmenu_open_gallery:{}");
        });
        var clearBtn = el("button", "mm-inline-btn mm-inline-btn-danger", "Clear");
        clearBtn.type = "button";
        clearBtn.addEventListener("click", function () {
            state.draft.colConf.modern_menu_background_image = "";
            paintPreview(previewIsLight);
        });
        btnRow.appendChild(importBtn); btnRow.appendChild(galleryBtn); btnRow.appendChild(clearBtn);

        var slideshowField = toggle(state.draft.colConf.modern_menu_background_mode === "slideshow", function (v) {
            state.draft.colConf.modern_menu_background_mode = v ? "slideshow" : "image";
            intervalRow.style.display = v ? "" : "none";
        });
        var slideshowRow = row("Slideshow", "Cycle through gallery images automatically.", slideshowField.el);

        var intervalField = numberInput(1, 3600, state.draft.colConf.modern_menu_slideshow_interval || 30, function (v) {
            state.draft.colConf.modern_menu_slideshow_interval = v;
        }, "sec");
        var intervalRow = row("Change every", "", intervalField.el);
        intervalRow.style.display = slideshowField.get() ? "" : "none";

        // Blur only makes visual sense against a photo — a flat colour has
        // nothing to blur — so it lives here, not as a shared control.
        var blurField = slider(0, 100, state.draft.colConf.modern_menu_background_blur || 0, 1, function (v) {
            state.draft.colConf.modern_menu_background_blur = v; paintPreview(previewIsLight);
        }, { label: "Blur", suffix: "%" });

        var opacityField = slider(0, 100, state.draft.colConf.modern_menu_background_opacity != null ? state.draft.colConf.modern_menu_background_opacity : 100, 1, function (v) {
            state.draft.colConf.modern_menu_background_opacity = v; paintPreview(previewIsLight);
        }, { label: "Opacity", suffix: "%" });

        panel.appendChild(btnRow);
        panel.appendChild(slideshowRow);
        panel.appendChild(intervalRow);
        panel.appendChild(blurField.el);
        panel.appendChild(opacityField.el);

        // ---- Colour-mode fields ----
        var lightSwatch = swatch(state.draft.colConf.modern_menu_bg_color_light || "#EEEEEE", function (hex) {
            state.draft.colConf.modern_menu_bg_color_light = hex;
            if (previewIsLight) paintPreview(true);
        });
        var darkSwatch = swatch(state.draft.colConf.modern_menu_bg_color_dark || "#3C3C3C", function (hex) {
            state.draft.colConf.modern_menu_bg_color_dark = hex;
            if (!previewIsLight) paintPreview(false);
        });
        var bgColorRow = pairedSwatchRow("Background colour", "",
            [{ label: "Light", swatch: lightSwatch }, { label: "Dark", swatch: darkSwatch }]
        );

        var themeAwareField = toggle(state.draft.colConf.modern_menu_bg_color_theme_mode === "separate", function (v) {
            state.draft.colConf.modern_menu_bg_color_theme_mode = v ? "separate" : "single";
        });
        var themeAwareRow = row("Theme-aware colour", "Use different colours for light and dark themes.", themeAwareField.el);

        panel.appendChild(bgColorRow);
        panel.appendChild(themeAwareRow);

        function refreshBgVisibility(style) {
            var isImage = style === "image";
            btnRow.style.display          = isImage ? "" : "none";
            slideshowRow.style.display    = isImage ? "" : "none";
            intervalRow.style.display     = (isImage && slideshowField.get()) ? "" : "none";
            blurField.el.style.display    = isImage ? "" : "none";
            opacityField.el.style.display = isImage ? "" : "none";
            bgColorRow.style.display      = isImage ? "none" : "";
            themeAwareRow.style.display   = isImage ? "none" : "";
            var allBgRows = [btnRow, slideshowRow, intervalRow, blurField.el, opacityField.el, bgColorRow, themeAwareRow];
            allBgRows.forEach(function (r) { r.classList.remove("no-border"); });
            var visible = allBgRows.filter(function (r) { return r.style.display !== "none"; });
            if (visible.length) visible[visible.length - 1].classList.add("no-border");
        }
        refreshBgVisibility(initialBgStyle);
    }

    // ================= Tab: Heatmap =================
    //
    // Preview mirrors the real widget structure. Cell shape and streak icon
    // use mask-image with URLs from heatmap_system_icons/ (served via
    // setWebExports). resolveIcon() strips the "system:" prefix the picker
    // writes before building the URL.

    function buildHeatmapPreviewCard() {
        var card = el("div", "mm-preview-card");
        var head = el("div", "mm-preview-head");
        head.appendChild(el("span", "mm-preview-head-label", "Preview"));

        var themeToggle = previewThemeToggle(function (isLight) {
            card.classList.toggle("is-light-preview", isLight);
            paint();
        });
        head.appendChild(themeToggle.el);
        card.appendChild(head);

        var body = el("div", "mm-preview-body");
        body.style.display = "block";
        body.style.padding = "14px";

        var widget = el("div", "mm-heatmap-widget");
        var inner  = el("div", "mm-heatmap-preview-inner");

        // Header: "Activity" + prev/year/next on the left (decorative —
        // there's no real review data in settings), streak badge + the
        // Year/Month/Week filter on the right — all on one row, matching
        // the real widget instead of stacking the filter on its own line.
        var previewHead = el("div", "mm-heatmap-widget-header");

        var headLeft = el("div", "mm-heatmap-preview-headleft");
        headLeft.appendChild(el("span", "mm-heatmap-preview-title", "Activity"));
        var prevBtn = el("button", "mm-heatmap-preview-navbtn");
        prevBtn.type = "button";
        prevBtn.appendChild(maskIcon("mm-heatmap-preview-navicon", "left.svg", 12));
        headLeft.appendChild(prevBtn);
        headLeft.appendChild(el("span", "mm-heatmap-preview-year", String(new Date().getFullYear())));
        var nextBtn = el("button", "mm-heatmap-preview-navbtn");
        nextBtn.type = "button";
        nextBtn.appendChild(maskIcon("mm-heatmap-preview-navicon", "right.svg", 12));
        headLeft.appendChild(nextBtn);
        previewHead.appendChild(headLeft);

        var headRight = el("div", "mm-heatmap-preview-headright");
        var streakEl   = el("span", "mm-heatmap-preview-streak");
        var streakIcon = el("span", "mm-heatmap-preview-streak-icon");
        streakIcon.style.display = "inline-block";
        streakEl.appendChild(streakIcon);
        streakEl.appendChild(el("span", "", "317"));
        headRight.appendChild(streakEl);

        var currentView = "year";
        var timeRow = el("div", "mm-heatmap-preview-time");
        var timeBtns = {};
        ["year", "month", "week"].forEach(function (v) {
            var label = v.charAt(0).toUpperCase() + v.slice(1);
            var btn = el("button", "mm-heatmap-preview-time-btn" + (v === currentView ? " is-active" : ""), label);
            btn.type = "button";
            btn.addEventListener("click", function () {
                currentView = v;
                Object.keys(timeBtns).forEach(function (k) { timeBtns[k].classList.toggle("is-active", k === v); });
                renderView();
            });
            timeBtns[v] = btn;
            timeRow.appendChild(btn);
        });
        headRight.appendChild(timeRow);
        previewHead.appendChild(headRight);
        inner.appendChild(previewHead);

        var viewHost = el("div");
        inner.appendChild(viewHost);
        widget.appendChild(inner);
        body.appendChild(widget);
        card.appendChild(body);

        // Deterministic fake activity levels (0-4) — just enough variety to
        // show a realistic multi-shade heatmap instead of flat on/off.
        function fakeLevel(i) { return [0, 2, 4, 1, 3, 0, 3, 1, 4, 2][i % 10]; }

        function levelColor(level, onColor, offColor) {
            if (level <= 0) return offColor;
            return "color-mix(in srgb," + onColor + " " + Math.round((level / 4) * 100) + "%, " + offColor + ")";
        }

        function buildCell(level, onColor, offColor, isFuture) {
            var color = isFuture ? offColor : levelColor(level, onColor, offColor);
            var resolved = resolveIcon(state.draft.json.heatmapShape);
            if (resolved.kind === "emoji") {
                var cell = el("span", "mm-heatmap-cell mm-heatmap-cell-emoji" + (isFuture ? " is-future" : ""), resolved.value);
                return cell;
            }
            var cell = el("span", "mm-heatmap-cell" + (isFuture ? " is-future" : ""));
            cell.style.backgroundColor = color;
            var url = heatmapIconUrl(resolved.value);
            cell.style.maskImage = "url('" + url + "')";
            cell.style.webkitMaskImage = "url('" + url + "')";
            cell.style.maskSize = "contain";
            cell.style.webkitMaskSize = "contain";
            cell.style.maskRepeat = "no-repeat";
            cell.style.webkitMaskRepeat = "no-repeat";
            cell.style.maskPosition = "center";
            cell.style.webkitMaskPosition = "center";
            return cell;
        }

        function renderView() {
            viewHost.innerHTML = "";
            var mode    = card.classList.contains("is-light-preview") ? "light" : "dark";
            var onColor = colorGet(mode, "--heatmap-color")      || (mode === "dark" ? "#9be9a8" : "#40c463");
            var offColor= colorGet(mode, "--heatmap-color-zero") || (mode === "dark" ? "#3a3a3a" : "#e8e8e8");
            var showMonths   = state.draft.json.heatmapShowMonths     != null ? state.draft.json.heatmapShowMonths     : true;
            var showWeekdays = state.draft.json.heatmapShowWeekdays   != null ? state.draft.json.heatmapShowWeekdays   : true;
            var showWeekHead = state.draft.json.heatmapShowWeekHeader != null ? state.draft.json.heatmapShowWeekHeader : true;

            if (currentView === "year") {
                var yearWrap = el("div", "mm-heatmap-preview-yearview");
                if (showMonths) {
                    var monthsRow = el("div", "mm-heatmap-preview-months");
                    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].forEach(function (m) {
                        monthsRow.appendChild(el("span", "", m));
                    });
                    yearWrap.appendChild(monthsRow);
                }
                var yearBody = el("div", "mm-heatmap-preview-yearbody");
                if (showWeekdays) {
                    var wdCol = el("div", "mm-heatmap-preview-weekdays");
                    ["Mon", "", "Wed", "", "Fri", "", ""].forEach(function (d) { wdCol.appendChild(el("span", "", d)); });
                    yearBody.appendChild(wdCol);
                }
                var gridWrap = el("div", "mm-heatmap-grid-wrap");
                var grid = el("div", "mm-heatmap-grid");
                var total = 210;
                var futureStart = Math.round(total * 0.68); // roughly matches "today" partway through the year
                for (var i = 0; i < total; i++) grid.appendChild(buildCell(fakeLevel(i), onColor, offColor, i >= futureStart));
                gridWrap.appendChild(grid);
                yearBody.appendChild(gridWrap);
                yearWrap.appendChild(yearBody);
                viewHost.appendChild(yearWrap);
            } else if (currentView === "month") {
                if (showWeekdays) {
                    var header = el("div", "mm-heatmap-preview-monthheader");
                    ["M", "T", "W", "T", "F", "S", "S"].forEach(function (d) { header.appendChild(el("span", "", d)); });
                    viewHost.appendChild(header);
                }
                var monthGrid = el("div", "mm-heatmap-preview-monthgrid");
                for (var j = 0; j < 35; j++) monthGrid.appendChild(buildCell(fakeLevel(j), onColor, offColor, j > 20));
                viewHost.appendChild(monthGrid);
            } else {
                if (showWeekHead) {
                    var wHeader = el("div", "mm-heatmap-preview-weekheader");
                    ["Mon 10", "Tue 11", "Wed 12", "Thu 13", "Fri 14", "Sat 15", "Sun 16"].forEach(function (d) { wHeader.appendChild(el("span", "", d)); });
                    viewHost.appendChild(wHeader);
                }
                var weekGrid = el("div", "mm-heatmap-preview-weekgrid");
                for (var k = 0; k < 7; k++) weekGrid.appendChild(buildCell(fakeLevel(k + 3), onColor, offColor, k > 4));
                viewHost.appendChild(weekGrid);
            }
        }

        function paint() {
            var mode = card.classList.contains("is-light-preview") ? "light" : "dark";
            widget.style.background  = colorGet(mode, "--canvas-inset") || (mode === "light" ? "#ffffff" : "#2c2c2c");
            widget.style.border      = "1px solid " + (colorGet(mode, "--border") || (mode === "light" ? "#e0e0e0" : "#3a3a3a"));

            var showStreak = state.draft.json.heatmapShowStreak != null ? state.draft.json.heatmapShowStreak : true;
            streakEl.style.display = showStreak ? "" : "none";

            var resolvedStreak = resolveIcon(state.draft.json.heatmapStreakIcon || "fire.svg");
            if (resolvedStreak.kind === "emoji") {
                streakIcon.textContent = resolvedStreak.value;
                streakIcon.style.maskImage = "none";
                streakIcon.style.webkitMaskImage = "none";
                streakIcon.style.backgroundColor = "transparent";
                streakIcon.style.width = "auto";
                streakIcon.style.height = "auto";
                streakIcon.style.fontSize = "13px";
            } else {
                streakIcon.textContent = "";
                var streakUrl = heatmapIconUrl(resolvedStreak.value);
                streakIcon.style.maskImage = "url('" + streakUrl + "')";
                streakIcon.style.webkitMaskImage = "url('" + streakUrl + "')";
                streakIcon.style.backgroundColor = state.draft.json.heatmapStreakIconColor || "#ff6b35";
                streakIcon.style.width = "13px";
                streakIcon.style.height = "13px";
                streakIcon.style.fontSize = "";
                streakIcon.style.maskSize = "contain";
                streakIcon.style.webkitMaskSize = "contain";
                streakIcon.style.maskRepeat = "no-repeat";
                streakIcon.style.webkitMaskRepeat = "no-repeat";
                streakIcon.style.maskPosition = "center";
                streakIcon.style.webkitMaskPosition = "center";
            }

            renderView();
        }

        return { card: card, paint: paint };
    }

    function renderHeatmapTab(panel) {
        panel.appendChild(sectionTitle("Heatmap"));
        panel.appendChild(sectionDesc("The activity grid shown on the Heatmap card."));

        var heatmapPreview = buildHeatmapPreviewCard();
        panel.appendChild(heatmapPreview.card);
        heatmapPreview.paint();

        // ---- View & layout ----
        // Sub-headings below, not sectionTitle — they're facets of this one
        // "Heatmap" tab, not sibling top-level sections of their own.
        panel.appendChild(subhead("View"));

        var viewField = segmented([
            { value: "year",  label: "Year"  },
            { value: "month", label: "Month" },
            { value: "week",  label: "Week"  }
        ], state.draft.json.heatmapDefaultView || "year", function (v) {
            state.draft.json.heatmapDefaultView = v;
        });
        panel.appendChild(row("Default view", "", viewField.el));

        var weekStartField = segmented([
            { value: "monday", label: "Monday" },
            { value: "sunday", label: "Sunday" }
        ], state.draft.json.heatmapWeekStart || "monday", function (v) {
            state.draft.json.heatmapWeekStart = v;
        });
        panel.appendChild(row("Week starts on", "", weekStartField.el, { noBorder: true }));

        // ---- Labels ----
        panel.appendChild(subhead("Labels"));

        function labelToggleRow(labelText, key, defaultVal, opts) {
            var field = toggle(state.draft.json[key] != null ? state.draft.json[key] : defaultVal, function (v) {
                state.draft.json[key] = v;
                heatmapPreview.paint();
            });
            return row(labelText, "", field.el, opts);
        }
        var streakPickerRow; // forward ref — set after streakPicker is built in Icons section
        var streakToggleField = toggle(state.draft.json.heatmapShowStreak != null ? state.draft.json.heatmapShowStreak : true, function (v) {
            state.draft.json.heatmapShowStreak = v;
            if (streakPickerRow) streakPickerRow.style.display = v ? "" : "none";
            heatmapPreview.paint();
        });
        panel.appendChild(row("Show streak counter", "", streakToggleField.el));
        panel.appendChild(labelToggleRow("Show month labels",   "heatmapShowMonths",     true));
        panel.appendChild(labelToggleRow("Show weekday labels", "heatmapShowWeekdays",   true));
        panel.appendChild(labelToggleRow("Show day number",     "heatmapShowWeekHeader", true, { noBorder: true }));

        // ---- Colours ----
        panel.appendChild(subhead("Colours"));

        function heatmapModeSwatch(mode, key) {
            return swatch(colorGet(mode, key) || "#9be9a8", function (hex) {
                colorSet(mode, key, hex);
                heatmapPreview.paint();
            });
        }

        var cellLightSwatch = heatmapModeSwatch("light", "--heatmap-color");
        var cellDarkSwatch  = heatmapModeSwatch("dark",  "--heatmap-color");
        var zeroLightSwatch = heatmapModeSwatch("light", "--heatmap-color-zero");
        var zeroDarkSwatch  = heatmapModeSwatch("dark",  "--heatmap-color-zero");

        panel.appendChild(pairedSwatchRow("Cell colour",      "", [{ label: "Light", swatch: cellLightSwatch }, { label: "Dark", swatch: cellDarkSwatch  }]));
        panel.appendChild(pairedSwatchRow("No-review colour", "", [{ label: "Light", swatch: zeroLightSwatch }, { label: "Dark", swatch: zeroDarkSwatch  }], { noBorder: true }));

        var resetBtn = el("button", "mm-inline-btn", "Reset colours to default");
        resetBtn.type = "button";
        resetBtn.addEventListener("click", function () {
            var defaults = {
                light: { "--heatmap-color": "#40c463", "--heatmap-color-zero": "#e8e8e8" },
                dark:  { "--heatmap-color": "#9be9a8", "--heatmap-color-zero": "#3a3a3a" }
            };
            Object.keys(defaults).forEach(function (mode) {
                Object.keys(defaults[mode]).forEach(function (key) {
                    colorSet(mode, key, defaults[mode][key]);
                });
            });
            // Update the swatch button chips so they show the new colours immediately
            cellLightSwatch.set(defaults.light["--heatmap-color"]);
            cellDarkSwatch.set(defaults.dark["--heatmap-color"]);
            zeroLightSwatch.set(defaults.light["--heatmap-color-zero"]);
            zeroDarkSwatch.set(defaults.dark["--heatmap-color-zero"]);
            heatmapPreview.paint();
        });
        var btnRow = el("div", "mm-btn-row");
        btnRow.appendChild(resetBtn);
        panel.appendChild(btnRow);

        // ---- Icons ----
        panel.appendChild(subhead("Icons"));

        var shapePicker = iconPickerButton(
            state.draft.json.heatmapShape || "square.svg",
            [
                { key: "light_shape", label: "Shape (light)",        value: colorGet("light", "--heatmap-color") },
                { key: "light_zero",  label: "No reviews (light)",   value: colorGet("light", "--heatmap-color-zero") },
                { key: "dark_shape",  label: "Shape (dark)",         value: colorGet("dark",  "--heatmap-color") },
                { key: "dark_zero",   label: "No reviews (dark)",    value: colorGet("dark",  "--heatmap-color-zero") }
            ],
            "light_shape",
            function (result) {
                if (result.icon) state.draft.json.heatmapShape = result.icon;
                if (result.colors) {
                    var map = {
                        light_shape: ["light", "--heatmap-color"],      light_zero: ["light", "--heatmap-color-zero"],
                        dark_shape:  ["dark",  "--heatmap-color"],      dark_zero:  ["dark",  "--heatmap-color-zero"]
                    };
                    Object.keys(result.colors).forEach(function (k) {
                        var m = map[k];
                        if (m && result.colors[k]) colorSet(m[0], m[1], result.colors[k]);
                    });
                }
                heatmapPreview.paint();
            },
            "heatmap"
        );
        panel.appendChild(row("Cell shape", "", shapePicker.el));

        var streakPicker = iconPickerButton(
            state.draft.json.heatmapStreakIcon || "fire.svg",
            [
                { key: "active", label: "Streak icon colour",        value: state.draft.json.heatmapStreakIconColor     || "#ff6b35" },
                { key: "zero",   label: "Streak icon colour (0 days)",value: state.draft.json.heatmapStreakIconZeroColor || "#8f8f8f" }
            ],
            "active",
            function (result) {
                if (result.icon) state.draft.json.heatmapStreakIcon = result.icon;
                if (result.colors) {
                    if (result.colors.active) state.draft.json.heatmapStreakIconColor     = result.colors.active;
                    if (result.colors.zero)   state.draft.json.heatmapStreakIconZeroColor = result.colors.zero;
                }
                heatmapPreview.paint();
            }
        );
        streakPickerRow = row("Streak icon", "", streakPicker.el, { noBorder: true });
        streakPickerRow.style.display = (state.draft.json.heatmapShowStreak != null ? state.draft.json.heatmapShowStreak : true) ? "" : "none";
        panel.appendChild(streakPickerRow);
    }

    // ================= Shell (sidebar + tab switcher) =================

    function buildSidebarNav() {
        var nav = el("div", "mm-nav");
        NAV_DATA.forEach(function (group) {
            var groupEl = el("div", "mm-nav-group");
            groupEl.appendChild(el("div", "mm-nav-group-title", group.title));
            group.items.forEach(function (item) {
                var itemEl = el("div", "mm-nav-item" + (item.active ? " is-active" : " is-disabled"));
                itemEl.appendChild(maskIcon("mm-nav-icon", item.icon));
                itemEl.appendChild(el("span", "", item.label));
                if (!item.active) itemEl.appendChild(el("span", "mm-nav-soon", "Soon"));
                groupEl.appendChild(itemEl);
            });
            nav.appendChild(groupEl);
        });
        return nav;
    }

    var TAB_GROUPS = [
        { key: "layout",     label: "Layout",     render: renderLayoutTab },
        { key: "background", label: "Background", render: renderMainBackgroundTab },
        { key: "widgets",    label: "Widgets",    render: renderWidgetCardsTab },
        { key: "heatmap",    label: "Heatmap",    render: renderHeatmapTab }
    ];

    function buildTabsAndPanels() {
        var tabsWrap   = el("div", "mm-tabs");
        var panelsWrap = el("div", "mm-panels");
        var panelEls   = [];

        TAB_GROUPS.forEach(function (group, idx) {
            var tabBtn  = el("button", "mm-tab" + (idx === 0 ? " is-active" : ""), group.label);
            tabBtn.type = "button";
            var panel   = el("div", "mm-panel" + (idx === 0 ? " is-active" : ""));
            var renderers = Array.isArray(group.render) ? group.render : [group.render];
            renderers.forEach(function (fn) { fn(panel); });
            panelEls.push(panel);
            tabBtn.addEventListener("click", function () {
                tabsWrap.querySelectorAll(".mm-tab").forEach(function (t) { t.classList.remove("is-active"); });
                panelEls.forEach(function (p) { p.classList.remove("is-active"); });
                tabBtn.classList.add("is-active");
                panel.classList.add("is-active");
            });
            tabsWrap.appendChild(tabBtn);
            panelsWrap.appendChild(panel);
        });

        return { tabsWrap: tabsWrap, panelsWrap: panelsWrap };
    }

    // ================= Save =================

    function doSave() {
        if (typeof pycmd !== "function") return;
        pycmd("onigiri_mainmenu_save:" + encodeURIComponent(JSON.stringify(state.draft)));
    }

    // ================= Modal wiring =================

    var modal = OnigiriModal.create({
        id: "main-menu",
        ownsGlobalUiState: true,
        buildWarmup: function () {
            var m = el("div", "mm-modal");
            m.style.width  = "1040px";
            m.style.height = "700px";
            return m;
        },
        buildBackdrop: function (data) {
            colorPickRegistry.clear();
            iconPickRegistry.clear();
            pendingBgCallback = null;
            openDropdownCloser = null;

            state.draft          = JSON.parse(JSON.stringify(data));
            state.draft.json     = state.draft.json     || {};
            state.draft.colConf  = state.draft.colConf  || {};
            state.draft.externalHooks = state.draft.externalHooks || [];

            var backdrop = el("div", "is-preparing");
            backdrop.id  = "onigiri-main-menu-backdrop";

            var modalEl = el("div", "mm-modal");
            modalEl.addEventListener("click", function (evt) {
                evt.stopPropagation();
                if (openDropdownCloser && !evt.target.closest(".mm-dropdown")) {
                    openDropdownCloser();
                    openDropdownCloser = null;
                }
            });
            modalEl.addEventListener("pointerdown", function (evt) { evt.stopPropagation(); });

            // Close button — 30×28, 7px radius, 16px icon
            var closeBtn = el("button", "mm-close");
            closeBtn.type  = "button";
            closeBtn.title = "Close";
            closeBtn.appendChild(maskIcon("mm-close-icon", "cancel.svg", 16));
            closeBtn.addEventListener("click", function () { modal.close(false); });
            modalEl.appendChild(closeBtn);

            var sidebar = el("div", "mm-sidebar");
            var search  = el("div", "mm-search");
            search.appendChild(maskIcon("mm-search-icon", "search.svg"));
            var searchInput = el("input");
            searchInput.type = "text";
            searchInput.placeholder = "Search";
            search.appendChild(searchInput);
            sidebar.appendChild(search);
            sidebar.appendChild(buildSidebarNav());
            sidebar.appendChild(el("div", "mm-nav-fade"));

            var footer = el("div", "mm-sidebar-footer");
            var donateRow = el("div", "mm-footer-row");
            donateRow.appendChild(maskIcon("mm-nav-icon", "donate.svg"));
            donateRow.appendChild(el("span", "", "Donate"));
            var reportRow = el("div", "mm-footer-row");
            reportRow.appendChild(maskIcon("mm-nav-icon", "report_bugs.svg"));
            reportRow.appendChild(el("span", "", "Report bugs"));
            footer.appendChild(donateRow);
            footer.appendChild(reportRow);

            var actions   = el("div", "mm-footer-actions");
            var saveBtn   = el("button", "mm-btn mm-btn-save",   "Save");
            saveBtn.type  = "button";
            saveBtn.addEventListener("click", function () { doSave(); });
            var cancelBtn = el("button", "mm-btn mm-btn-cancel", "Cancel");
            cancelBtn.type = "button";
            cancelBtn.addEventListener("click", function () { modal.close(false); });
            actions.appendChild(cancelBtn);
            actions.appendChild(saveBtn);
            footer.appendChild(actions);
            sidebar.appendChild(footer);

            modalEl.appendChild(sidebar);

            var content        = el("div", "mm-content");
            var tabsAndPanels  = buildTabsAndPanels();
            content.appendChild(tabsAndPanels.tabsWrap);
            content.appendChild(tabsAndPanels.panelsWrap);
            modalEl.appendChild(content);

            backdrop.appendChild(modalEl);
            document.body.appendChild(backdrop);

            return { backdrop: backdrop, focusTarget: null };
        }
    });

    return {
        open:  modal.open,
        close: modal.close,
        applyColorPick: function (pickId, hex) {
            var handler = colorPickRegistry.get(pickId);
            if (handler && hex) handler(hex);
        },
        applyIconPick: function (pickId, result) {
            var handler = iconPickRegistry.get(pickId);
            if (handler) handler(result || {});
        },
        applyBackgroundPick: function (result) {
            if (pendingBgCallback) pendingBgCallback(result);
            pendingBgCallback = null;
        },
        showError: function () {}
    };
})();
