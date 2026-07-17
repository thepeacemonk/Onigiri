/*
    Onigiri Widget Layout Editor

    Pointer-events drag-and-drop grid editor, opened from the Main Menu
    dialog's Layout tab ("Edit Widget Layout..."). Built on OnigiriModal,
    stacked on the already-open Main Menu dialog (ownsGlobalUiState: false).

    Grid/placement algorithm mirrors settings/_layout_base.py exactly so
    behaviour matches the native editor. Everything is client-side only —
    Save hands results to Main Menu via a JS callback (onCommit).

    Drag works via pointer events (pointerdown / pointermove / pointerup)
    because HTML5 DnD is unreliable in QtWebEngine. Tiles are dragged from
    the grid; archive items can be dragged onto the grid to place them.
    Dragging a grid tile into the archive panel archives it.

    Double-tap a placed tile to open the rename / resize popover.
*/

window.OnigiriWidgetLayoutEditor = window.OnigiriWidgetLayoutEditor || (function () {
    "use strict";

    // ============================================================
    // Constants (mirrors widget_layout_dialog.py)
    // ============================================================

    var SPAN_RULES = {
        heatmap:          { colMin: 2, colMax: 4, rowMin: 2, rowMax: 2 },
        restaurant_level: { colMin: 1, colMax: 2, rowMin: 1, rowMax: 2, orientation: true },
        deck_stats:       { colMin: 1, colMax: 2, rowMin: 1, rowMax: 2 },
        onigimon:         { colMin: 1, colMax: 4, rowMin: 1, rowMax: 2 },
        hexagon_land:     { colMin: 1, colMax: 4, rowMin: 1, rowMax: 4 },
        prep_station:     { colMin: 1, colMax: 4, rowMin: 2, rowMax: 2 },
        favorites:        { colMin: 1, colMax: 4, rowMin: 1, rowMax: 3 }
    };
    var DEFAULT_ONIGIRI_RULE  = { colMin: 1, colMax: 4, rowMin: 1, rowMax: 1 };
    var DEFAULT_EXTERNAL_RULE = { colMin: 1, colMax: 4, rowMin: 2, rowMax: 2 };

    var WIDGET_DEFAULT_NAMES = {
        studied: "Studied Card", time: "Time Card", pace: "Pace Card",
        retention: "Retention Card", heatmap: "Heatmap", favorites: "Favorites Widget",
        restaurant_level: "Nook Level", onigimon: "Onigimon", hexagon_land: "Hexagon Land",
        deck_stats: "Deck Stats", prep_station: "Study Plans"
    };

    var WIDGET_ICONS = {
        studied: "studied.svg", time: "due_later.svg", pace: "pace.svg",
        retention: "retention.svg", heatmap: "fire.svg", favorites: "star_outline.svg",
        restaurant_level: "nook_level.svg",
        onigimon: "games.svg",
        hexagon_land: "unavailable_for_users/hexagon_land.svg",
        deck_stats: "stats.svg", prep_station: "study_plans.svg"
    };
    var EXTERNAL_ICON = "share.svg";

    var ONIGIRI_DEFAULTS = {
        rows: 6, cols: 4, gridWidth: 230, gridAlignment: "center", widgetHeight: 120,
        grid: {
            studied:   { pos: 0, row: 1, col: 1 },
            time:      { pos: 1, row: 1, col: 1 },
            pace:      { pos: 2, row: 1, col: 1 },
            retention: { pos: 3, row: 1, col: 1 },
            heatmap:   { pos: 4, row: 2, col: 4 }
        }
    };

    var ROW_HEIGHT = 64;
    var GAP = 8;
    var DRAG_THRESHOLD = 6; // px movement before drag starts

    function ruleFor(widgetId, isExternal) {
        if (isExternal) return DEFAULT_EXTERNAL_RULE;
        return SPAN_RULES[widgetId] || DEFAULT_ONIGIRI_RULE;
    }

    // ============================================================
    // DOM helpers
    // ============================================================

    function iconUrl(name) {
        if (window.OnigiriEngine && typeof OnigiriEngine.systemIconUrl === "function") {
            return OnigiriEngine.systemIconUrl(name);
        }
        return "../system_files/system_icons/" + name;
    }
    function maskIcon(className, filename) {
        var span = document.createElement("span");
        span.className = className;
        var url = iconUrl(filename);
        span.style.maskImage = "url('" + url + "')";
        span.style.webkitMaskImage = "url('" + url + "')";
        return span;
    }
    function el(tag, className, text) {
        var e = document.createElement(tag);
        if (className) e.className = className;
        if (text != null) e.textContent = text;
        return e;
    }

    // ============================================================
    // State
    // ============================================================

    var state = null;

    function freshState() {
        return {
            rows: 6, cols: 4, gridWidth: 230, gridAlignment: "center", widgetHeight: 120,
            cells:   {},   // cell-index -> widgetId
            widgets: {},   // widgetId -> { kind, pos, rowSpan, colSpan, displayName, orientation? }
            onigiriArchive:   [],   // [{ id, displayName }]
            externalArchive:  [],   // [{ id, displayName }]
            onCommit: null,
            externalDefaultNames: {}
        };
    }

    function isRegionFree(pos, rowSpan, colSpan, ignoreId) {
        if (state.cols <= 0 || state.rows <= 0) return false;
        var row = Math.floor(pos / state.cols);
        var col = pos % state.cols;
        if (col + colSpan > state.cols || row + rowSpan > state.rows) return false;
        for (var r = row; r < row + rowSpan; r++) {
            for (var c = col; c < col + colSpan; c++) {
                var occupant = state.cells[r * state.cols + c];
                if (occupant != null && occupant !== ignoreId) return false;
            }
        }
        return true;
    }

    function findFreeSlot(rowSpan, colSpan, ignoreId) {
        var total = state.rows * state.cols;
        for (var pos = 0; pos < total; pos++) {
            if (isRegionFree(pos, rowSpan, colSpan, ignoreId)) return pos;
        }
        return null;
    }

    function clearWidgetFromCells(widgetId) {
        Object.keys(state.cells).forEach(function (key) {
            if (state.cells[key] === widgetId) delete state.cells[key];
        });
    }

    function writeCells(widgetId, pos, rowSpan, colSpan) {
        var row = Math.floor(pos / state.cols);
        var col = pos % state.cols;
        for (var r = row; r < row + rowSpan; r++) {
            for (var c = col; c < col + colSpan; c++) {
                state.cells[r * state.cols + c] = widgetId;
            }
        }
    }

    function placeWidget(widgetId, pos) {
        var w = state.widgets[widgetId];
        if (!w) return { ok: false };
        clearWidgetFromCells(widgetId);
        if (!isRegionFree(pos, w.rowSpan, w.colSpan, widgetId)) {
            var fallback = findFreeSlot(w.rowSpan, w.colSpan, widgetId);
            if (fallback == null) { archiveWidget(widgetId); return { ok: false, archived: true }; }
            pos = fallback;
        }
        writeCells(widgetId, pos, w.rowSpan, w.colSpan);
        w.pos = pos;
        return { ok: true, pos: pos };
    }

    function resolveResize(widgetId, newRowSpan, newColSpan) {
        var w = state.widgets[widgetId];
        if (!w) return { ok: false };
        var candidatePos = findFreeSlot(newRowSpan, newColSpan, widgetId);
        if (candidatePos == null) return { ok: false, reason: "no_fit" };

        var row = Math.floor(candidatePos / state.cols);
        var col = candidatePos % state.cols;
        var conflicts = {};
        for (var r = row; r < row + newRowSpan; r++) {
            for (var c = col; c < col + newColSpan; c++) {
                var occ = state.cells[r * state.cols + c];
                if (occ != null && occ !== widgetId) conflicts[occ] = true;
            }
        }
        var conflictIds = Object.keys(conflicts);

        clearWidgetFromCells(widgetId);
        conflictIds.forEach(function (id) { clearWidgetFromCells(id); });

        conflictIds.forEach(function (id) {
            var cw = state.widgets[id];
            if (!cw) return;
            var slot = findFreeSlot(cw.rowSpan, cw.colSpan, id) != null
                ? findFreeSlot(cw.rowSpan, cw.colSpan, id)
                : findFreeSlot(1, 1, id);
            if (slot != null) { writeCells(id, slot, cw.rowSpan, cw.colSpan); cw.pos = slot; }
            else { archiveWidget(id); }
        });

        w.rowSpan = newRowSpan;
        w.colSpan = newColSpan;
        writeCells(widgetId, candidatePos, newRowSpan, newColSpan);
        w.pos = candidatePos;
        return { ok: true };
    }

    function archiveWidget(widgetId) {
        var w = state.widgets[widgetId];
        if (!w) return;
        clearWidgetFromCells(widgetId);
        delete state.widgets[widgetId];
        var list = w.kind === "external" ? state.externalArchive : state.onigiriArchive;
        list.push({ id: widgetId, displayName: w.displayName, orientation: w.orientation });
    }

    function unarchiveWidget(widgetId, kind, atPos) {
        var list = kind === "external" ? state.externalArchive : state.onigiriArchive;
        var idx  = -1;
        for (var i = 0; i < list.length; i++) { if (list[i].id === widgetId) { idx = i; break; } }
        if (idx === -1) return { ok: false };
        var entry = list.splice(idx, 1)[0];
        var rule  = ruleFor(widgetId, kind === "external");
        state.widgets[widgetId] = {
            kind: kind, pos: 0,
            rowSpan: rule.rowMin, colSpan: rule.colMin,
            displayName: entry.displayName, orientation: entry.orientation
        };
        var result = placeWidget(widgetId, atPos != null ? atPos : 0);
        if (!result.ok && !result.archived) {
            delete state.widgets[widgetId];
            list.push(entry);
        }
        return result;
    }

    // ============================================================
    // Load / serialize
    // ============================================================

    function clampInt(value, lo, hi, fallback) {
        var v = parseInt(value, 10);
        if (isNaN(v)) return fallback;
        return Math.max(lo, Math.min(hi, v));
    }

    function loadDraft(draft) {
        state = freshState();
        draft = draft || {};
        var layout   = draft.onigiriWidgetLayout  || {};
        var external = draft.externalWidgetLayout || {};

        state.rows          = clampInt(draft.unifiedGridRows,    0,   200, 6);
        state.cols          = clampInt(layout.column_count,      0,   6,   4);
        state.gridWidth     = clampInt(layout.grid_width,        200, 340, 230);
        state.widgetHeight  = clampInt(layout.widget_height,     120, 320, 120);
        state.gridAlignment = ["left", "center", "right"].indexOf(layout.grid_alignment) !== -1
            ? layout.grid_alignment : "center";

        (draft.externalHooks || []).forEach(function (hook) {
            state.externalDefaultNames[hook.id] = hook.defaultDisplayName || hook.id;
        });

        var grid = layout.grid || {};
        Object.keys(grid).forEach(function (id) {
            var cfg  = grid[id] || {};
            var rule = ruleFor(id, false);
            state.widgets[id] = {
                kind: "onigiri",
                pos:      clampInt(cfg.pos, 0, Math.max(0, state.rows * state.cols - 1), 0),
                rowSpan:  clampInt(cfg.row, rule.rowMin, rule.rowMax, rule.rowMin),
                colSpan:  clampInt(cfg.col, rule.colMin, rule.colMax, rule.colMin),
                displayName: cfg.display_name || hostWidgetNames[id] || WIDGET_DEFAULT_NAMES[id] || id,
                orientation: cfg.orientation
            };
        });

        var extGrid = external.grid || {};
        Object.keys(extGrid).forEach(function (id) {
            var cfg  = extGrid[id] || {};
            var rule = DEFAULT_EXTERNAL_RULE;
            state.widgets[id] = {
                kind: "external",
                pos:     clampInt(cfg.grid_position, 0, Math.max(0, state.rows * state.cols - 1), 0),
                rowSpan: clampInt(cfg.row_span,    rule.rowMin, rule.rowMax, rule.rowMin),
                colSpan: clampInt(cfg.column_span, rule.colMin, rule.colMax, rule.colMin),
                displayName: cfg.display_name || state.externalDefaultNames[id] || id
            };
        });

        // Reconcile placement (first-come, conflicts → archive)
        var ordered = Object.keys(state.widgets).sort(function (a, b) {
            return state.widgets[a].pos - state.widgets[b].pos;
        });
        var snap = {};
        ordered.forEach(function (id) { snap[id] = state.widgets[id]; });
        state.widgets = {};
        ordered.forEach(function (id) {
            state.widgets[id] = snap[id];
            var w = state.widgets[id];
            if (!isRegionFree(w.pos, w.rowSpan, w.colSpan, id)) {
                var slot = findFreeSlot(w.rowSpan, w.colSpan, id);
                if (slot == null) {
                    delete state.widgets[id];
                    (w.kind === "external" ? state.externalArchive : state.onigiriArchive)
                        .push({ id: id, displayName: w.displayName, orientation: w.orientation });
                    return;
                }
                w.pos = slot;
            }
            writeCells(id, w.pos, w.rowSpan, w.colSpan);
        });

        function archiveEntries(raw, kind) {
            var out = [];
            if (Array.isArray(raw)) {
                raw.forEach(function (id) {
                    if (!state.widgets[id]) {
                        out.push({ id: id, displayName: (kind === "external" ? state.externalDefaultNames[id] : (hostWidgetNames[id] || WIDGET_DEFAULT_NAMES[id])) || id });
                    }
                });
            } else if (raw && typeof raw === "object") {
                Object.keys(raw).forEach(function (id) {
                    if (!state.widgets[id]) {
                        var e = raw[id] || {};
                        out.push({ id: id,
                            displayName: e.display_name || (kind === "external" ? state.externalDefaultNames[id] : (hostWidgetNames[id] || WIDGET_DEFAULT_NAMES[id])) || id,
                            orientation: e.orientation });
                    }
                });
            }
            return out;
        }
        state.onigiriArchive  = archiveEntries(layout.archive,  "onigiri");
        state.externalArchive = archiveEntries(external.archive, "external");
    }

    function serialize() {
        var grid = {};
        var extGrid = {};
        Object.keys(state.widgets).forEach(function (id) {
            var w = state.widgets[id];
            if (w.kind === "external") {
                extGrid[id] = { grid_position: w.pos, row_span: w.rowSpan, column_span: w.colSpan, display_name: w.displayName };
            } else {
                var entry = { pos: w.pos, row: w.rowSpan, col: w.colSpan, display_name: w.displayName };
                if (w.orientation) entry.orientation = w.orientation;
                grid[id] = entry;
            }
        });
        var onigiriArchiveDict  = {};
        var externalArchiveDict = {};
        state.onigiriArchive.forEach(function (e)  { onigiriArchiveDict[e.id]  = { display_name: e.displayName, orientation: e.orientation }; });
        state.externalArchive.forEach(function (e) { externalArchiveDict[e.id] = { display_name: e.displayName }; });
        return {
            onigiriWidgetLayout: {
                grid: grid, archive: onigiriArchiveDict,
                column_count: state.cols, grid_width: state.gridWidth,
                grid_alignment: state.gridAlignment, widget_height: state.widgetHeight
            },
            externalWidgetLayout: { grid: extGrid, archive: externalArchiveDict },
            unifiedGridRows: state.rows
        };
    }

    // ============================================================
    // Rendering
    // ============================================================

    var dom = null;    // { gridEl, highlightEl, onigiriListEl, externalListEl }
    var cachedMetrics = null;
    var activePopover = null;
    var activeDragGhost = null;
    // Host-supplied widget display names (from main_menu_dialog.py build_open_payload).
    // Falls back to WIDGET_DEFAULT_NAMES when absent.
    var hostWidgetNames = {};

    // Inline-embed wiring. When the editor is mounted inline in the Main Menu
    // dialog's Layout tab (rather than as a stacked modal), onInlineChange is
    // set and every mutation live-serializes back to the host so edits persist
    // through the host dialog's own Save — there is no separate editor Save.
    // In modal mode both stay null and the modal commits only on its Save.
    var onInlineChange = null;
    var inlineGetSlice = null;

    // Re-render after a user mutation, and (inline mode only) push the new
    // serialized layout to the host. Modal mode leaves onInlineChange null so
    // nothing is committed until the modal's Save button.
    function afterMutation() {
        renderGrid();
        renderArchives();
        if (onInlineChange) onInlineChange(serialize());
    }

    function metrics() {
        if (cachedMetrics) return cachedMetrics;
        var rect  = dom.gridEl.getBoundingClientRect();
        var cellW = state.cols > 0 ? (rect.width - (state.cols - 1) * GAP) / state.cols : rect.width;
        cachedMetrics = { rect: rect, cellW: cellW, cellH: ROW_HEIGHT, gap: GAP };
        return cachedMetrics;
    }
    function invalidateMetrics() { cachedMetrics = null; }

    function tileGeometry(pos, rowSpan, colSpan) {
        var m   = metrics();
        var row = state.cols > 0 ? Math.floor(pos / state.cols) : 0;
        var col = state.cols > 0 ? pos % state.cols : 0;
        return {
            left:   col * (m.cellW + m.gap),
            top:    row * (m.cellH + m.gap),
            width:  colSpan * m.cellW + (colSpan - 1) * m.gap,
            height: rowSpan * m.cellH + (rowSpan - 1) * m.gap
        };
    }

    function posFromClient(clientX, clientY) {
        var m   = metrics();
        var col = Math.max(0, Math.min(state.cols - 1, Math.floor((clientX - m.rect.left)  / (m.cellW + m.gap))));
        var row = Math.max(0, Math.min(state.rows - 1, Math.floor((clientY - m.rect.top)   / (m.cellH + m.gap))));
        return row * state.cols + col;
    }

    function widgetIconFilename(id, kind) {
        return kind === "external" ? EXTERNAL_ICON : (WIDGET_ICONS[id] || "description.svg");
    }

    function closePopover() {
        if (activePopover) { activePopover.remove(); activePopover = null; }
        document.removeEventListener("pointerdown", onOutsidePointerDown, true);
    }

    function showHighlight(pos, rowSpan, colSpan, valid) {
        var g = tileGeometry(pos, rowSpan, colSpan);
        dom.highlightEl.style.left    = g.left   + "px";
        dom.highlightEl.style.top     = g.top    + "px";
        dom.highlightEl.style.width   = g.width  + "px";
        dom.highlightEl.style.height  = g.height + "px";
        dom.highlightEl.style.display = "block";
        dom.highlightEl.classList.toggle("is-invalid", !valid);
    }
    function hideHighlight() {
        if (dom && dom.highlightEl) dom.highlightEl.style.display = "none";
    }

    function inRect(clientX, clientY, rect) {
        return clientX >= rect.left && clientX <= rect.right &&
               clientY >= rect.top  && clientY <= rect.bottom;
    }

    function renderGrid() {
        invalidateMetrics();
        var gridHeight = state.rows * ROW_HEIGHT + Math.max(0, state.rows - 1) * GAP;
        dom.gridEl.style.height = gridHeight + "px";
        dom.gridEl.innerHTML    = "";

        // Empty shelf placeholders for visual grid cells
        var total = state.rows * state.cols;
        for (var pos = 0; pos < total; pos++) {
            var g     = tileGeometry(pos, 1, 1);
            var shelf = el("div", "wl-shelf");
            shelf.style.left   = g.left   + "px";
            shelf.style.top    = g.top    + "px";
            shelf.style.width  = g.width  + "px";
            shelf.style.height = g.height + "px";
            dom.gridEl.appendChild(shelf);
        }

        var highlight = el("div", "wl-drop-highlight");
        dom.gridEl.appendChild(highlight);
        dom.highlightEl = highlight;

        Object.keys(state.widgets).forEach(function (id) {
            dom.gridEl.appendChild(buildTile(id));
        });
    }

    function buildTile(widgetId) {
        var w = state.widgets[widgetId];
        var g = tileGeometry(w.pos, w.rowSpan, w.colSpan);
        var tile = el("div", "wl-tile");
        tile.style.left         = g.left   + "px";
        tile.style.top          = g.top    + "px";
        tile.style.width        = g.width  + "px";
        tile.style.height       = g.height + "px";
        tile.dataset.widgetId   = widgetId;

        var top = el("div", "wl-tile-top");
        top.appendChild(maskIcon("wl-tile-icon", widgetIconFilename(widgetId, w.kind)));
        top.appendChild(el("span", "wl-tile-name", w.displayName));

        // Ellipsis button opens rename/resize popover (replaces double-click)
        var moreBtn = el("button", "wl-tile-more", "⋯");
        moreBtn.type = "button";
        moreBtn.title = "Rename or resize";
        moreBtn.addEventListener("click", function (evt) {
            evt.stopPropagation();
            openPopover(widgetId, moreBtn);
        });
        moreBtn.addEventListener("pointerdown", function (evt) { evt.stopPropagation(); });
        top.appendChild(moreBtn);

        tile.appendChild(top);
        tile.appendChild(el("div", "wl-tile-meta", w.colSpan + " × " + w.rowSpan));

        // Pointer-events drag (starts from tile itself, not the more button)
        tile.addEventListener("pointerdown", function (evt) {
            if (evt.button !== 0 || evt.target === moreBtn || moreBtn.contains(evt.target)) return;
            evt.stopPropagation();
            startDrag(evt, widgetId, w.kind, "grid", tile);
        });

        return tile;
    }

    // ============================================================
    // Pointer-events drag
    // ============================================================

    var dragState = null;
    // {
    //   widgetId, kind, sourceKind: "grid"|"onigiri-archive"|"external-archive",
    //   tileEl: DOM element to mark as dragging (or null for archive items),
    //   startX, startY, started: boolean
    // }

    function startDrag(evt, widgetId, kind, sourceKind, tileEl) {
        if (dragState) endDrag(null); // clean up any stale drag
        // Re-measure: inline the grid lives in a scroll container whose rect
        // can differ from the last render (page scrolled, panel resized).
        invalidateMetrics();
        dragState = {
            widgetId: widgetId, kind: kind, sourceKind: sourceKind,
            tileEl: tileEl || null,
            startX: evt.clientX, startY: evt.clientY, started: false
        };
        document.addEventListener("pointermove",   onDragMove);
        document.addEventListener("pointerup",     onDragEnd);
        document.addEventListener("pointercancel", onDragEnd);
    }

    function removeGhost() {
        if (activeDragGhost) { activeDragGhost.remove(); activeDragGhost = null; }
    }

    function onDragMove(evt) {
        if (!dragState) return;
        var dx = evt.clientX - dragState.startX;
        var dy = evt.clientY - dragState.startY;

        if (!dragState.started) {
            if (Math.sqrt(dx * dx + dy * dy) < DRAG_THRESHOLD) return;
            dragState.started = true;
            if (dragState.tileEl) dragState.tileEl.classList.add("is-dragging");
            // Create floating ghost
            removeGhost();
            var ghost = el("div", "wl-drag-ghost");
            var w = state.widgets[dragState.widgetId];
            var m = metrics();
            ghost.style.width  = (w ? w.colSpan * m.cellW + (w.colSpan - 1) * m.gap : m.cellW) + "px";
            ghost.style.height = (w ? w.rowSpan * m.cellH + (w.rowSpan - 1) * m.gap : m.cellH) + "px";
            ghost.appendChild(maskIcon("wl-tile-icon", widgetIconFilename(dragState.widgetId, dragState.kind)));
            ghost.appendChild(el("span", "wl-tile-name", w ? w.displayName : dragState.widgetId));
            document.body.appendChild(ghost);
            activeDragGhost = ghost;
        }

        // Move ghost to follow cursor
        if (activeDragGhost) {
            var gw = activeDragGhost.offsetWidth  || 80;
            var gh = activeDragGhost.offsetHeight || 40;
            activeDragGhost.style.left = (evt.clientX - gw / 2) + "px";
            activeDragGhost.style.top  = (evt.clientY - gh / 2) + "px";
        }

        var gridRect    = dom.gridEl.getBoundingClientRect();
        var onigRect    = dom.onigiriListEl.getBoundingClientRect();
        var extRect     = dom.externalListEl.getBoundingClientRect();
        var overGrid    = inRect(evt.clientX, evt.clientY, gridRect);
        var overOnigiri = inRect(evt.clientX, evt.clientY, onigRect);
        var overExt     = inRect(evt.clientX, evt.clientY, extRect);

        dom.onigiriListEl.classList.toggle("is-drag-over", overOnigiri && dragState.sourceKind === "grid");
        dom.externalListEl.classList.toggle("is-drag-over", overExt    && dragState.sourceKind === "grid");

        if (overGrid) {
            var pos     = posFromClient(evt.clientX, evt.clientY);
            var w       = state.widgets[dragState.widgetId];
            var rule    = ruleFor(dragState.widgetId, dragState.kind === "external");
            var rowSpan = w ? w.rowSpan : rule.rowMin;
            var colSpan = w ? w.colSpan : rule.colMin;
            var ignoreId = dragState.sourceKind === "grid" ? dragState.widgetId : null;
            var valid   = isRegionFree(pos, rowSpan, colSpan, ignoreId);
            showHighlight(pos, rowSpan, colSpan, valid);
        } else {
            hideHighlight();
        }
    }

    function onDragEnd(evt) {
        endDrag(evt);
    }

    function endDrag(evt) {
        document.removeEventListener("pointermove",   onDragMove);
        document.removeEventListener("pointerup",     onDragEnd);
        document.removeEventListener("pointercancel", onDragEnd);

        if (!dragState) return;

        if (dragState.tileEl) dragState.tileEl.classList.remove("is-dragging");
        hideHighlight();
        removeGhost();
        dom.onigiriListEl.classList.remove("is-drag-over");
        dom.externalListEl.classList.remove("is-drag-over");

        if (dragState.started && evt) {
            var gridRect = dom.gridEl.getBoundingClientRect();
            var onigRect = dom.onigiriListEl.getBoundingClientRect();
            var extRect  = dom.externalListEl.getBoundingClientRect();

            if (inRect(evt.clientX, evt.clientY, gridRect)) {
                var pos = posFromClient(evt.clientX, evt.clientY);
                if (dragState.sourceKind === "grid") {
                    placeWidget(dragState.widgetId, pos);
                } else {
                    unarchiveWidget(dragState.widgetId, dragState.kind, pos);
                }
            } else if (
                dragState.sourceKind === "grid" &&
                (inRect(evt.clientX, evt.clientY, onigRect) || inRect(evt.clientX, evt.clientY, extRect))
            ) {
                archiveWidget(dragState.widgetId);
            }

            afterMutation();
        }

        dragState = null;
    }

    // ============================================================
    // Archive panel
    // ============================================================

    function renderArchives() {
        renderArchiveList(dom.onigiriListEl,  state.onigiriArchive,  "onigiri");
        renderArchiveList(dom.externalListEl, state.externalArchive, "external");
    }

    function renderArchiveList(listEl, items, kind) {
        listEl.innerHTML = "";
        if (!items.length) {
            listEl.appendChild(el("div", "wl-archive-empty", "Nothing archived."));
            return;
        }
        items.forEach(function (entry) {
            var item = el("div", "wl-archive-item");
            item.appendChild(maskIcon("wl-tile-icon", widgetIconFilename(entry.id, kind)));
            item.appendChild(el("span", "", entry.displayName));
            item.addEventListener("pointerdown", function (evt) {
                if (evt.button !== 0) return;
                evt.stopPropagation();
                startDrag(evt, entry.id, kind, kind + "-archive", null);
            });
            listEl.appendChild(item);
        });
    }

    // ============================================================
    // Rename / resize / orientation popover (opened on double-tap)
    // ============================================================

    function openPopover(widgetId, anchorEl) {
        closePopover();
        var w = state.widgets[widgetId];
        if (!w) return;
        var rule = ruleFor(widgetId, w.kind === "external");

        var pop = el("div", "wl-popover");

        // Append to document.body so position:fixed resolves against the
        // viewport — not against .mm-modal which has transform + contain:layout
        // (both create a containing block that breaks fixed positioning).
        var rect   = anchorEl.getBoundingClientRect();
        var vw     = window.innerWidth  || document.documentElement.clientWidth;
        var vh     = window.innerHeight || document.documentElement.clientHeight;
        var POPW   = 228; var POPH = 280;
        var top    = rect.bottom + 6;
        var left   = Math.max(8, rect.right - POPW);
        if (top + POPH > vh - 8) top = Math.max(8, rect.top - POPH - 6);
        pop.style.top  = top  + "px";
        pop.style.left = Math.min(left, vw - POPW - 8) + "px";

        pop.appendChild(el("div", "wl-popover-label", "Name"));
        var nameInput = el("input", "wl-popover-input");
        nameInput.type = "text";
        nameInput.value = w.displayName;
        nameInput.placeholder = "Widget name…";
        pop.appendChild(nameInput);

        var toast = el("div", "wl-popover-toast", "No space available for that size.");

        function buildSegmented(labelText, values, current, onPick) {
            pop.appendChild(el("div", "wl-popover-label", labelText));
            var seg = el("div", "wl-popover-segmented");
            values.forEach(function (v) {
                var btn = el("button", "wl-popover-segment" + (v === current ? " is-active" : ""), String(v));
                btn.type = "button";
                btn.addEventListener("click", function () {
                    seg.querySelectorAll(".wl-popover-segment").forEach(function (b) { b.classList.remove("is-active"); });
                    btn.classList.add("is-active");
                    onPick(v);
                });
                seg.appendChild(btn);
            });
            pop.appendChild(seg);
        }

        function applyResize(newRow, newCol) {
            var result = resolveResize(widgetId, newRow, newCol);
            if (!result.ok) { toast.classList.add("is-visible"); return; }
            toast.classList.remove("is-visible");
            afterMutation();
            closePopover();
        }

        var colValues = [];
        for (var c = rule.colMin; c <= rule.colMax; c++) colValues.push(c);
        var rowValues = [];
        for (var r = rule.rowMin; r <= rule.rowMax; r++) rowValues.push(r);

        if (colValues.length > 1) buildSegmented("Width", colValues, w.colSpan, function (v) { applyResize(w.rowSpan, v); });
        if (rowValues.length > 1) buildSegmented("Height", rowValues, w.rowSpan, function (v) { applyResize(v, w.colSpan); });

        if (rule.orientation) {
            buildSegmented("Layout", ["Horizontal", "Vertical"], w.orientation || "horizontal", function (v) {
                w.orientation = v.toLowerCase();
            });
        }

        pop.appendChild(toast);

        nameInput.addEventListener("change", function () {
            var val = nameInput.value.trim();
            if (val) { w.displayName = val; afterMutation(); }
        });

        var archiveBtn = el("button", "wl-popover-archive-btn", "Archive this widget");
        archiveBtn.type = "button";
        archiveBtn.addEventListener("click", function () {
            archiveWidget(widgetId);
            afterMutation();
            closePopover();
        });
        pop.appendChild(archiveBtn);

        document.body.appendChild(pop);
        activePopover = pop;

        setTimeout(function () {
            document.addEventListener("pointerdown", onOutsidePointerDown, true);
        }, 0);
    }

    function onOutsidePointerDown(evt) {
        if (activePopover && !activePopover.contains(evt.target)) {
            closePopover();
        }
    }

    // ============================================================
    // Reset helpers
    // ============================================================

    function resetWidgetNames() {
        Object.keys(state.widgets).forEach(function (id) {
            var w = state.widgets[id];
            w.displayName = w.kind === "external"
                ? (state.externalDefaultNames[id] || id)
                : (hostWidgetNames[id] || WIDGET_DEFAULT_NAMES[id] || id);
        });
        state.onigiriArchive.forEach(function (e)  { e.displayName = hostWidgetNames[e.id] || WIDGET_DEFAULT_NAMES[e.id] || e.id; });
        state.externalArchive.forEach(function (e) { e.displayName = state.externalDefaultNames[e.id] || e.id; });
        afterMutation();
    }

    function resetLayoutToDefault() {
        var allIds = Object.keys(state.widgets)
            .concat(state.onigiriArchive.map(function (e) { return e.id; }))
            .concat(state.externalArchive.map(function (e) { return e.id; }));

        state.rows = ONIGIRI_DEFAULTS.rows; state.cols = ONIGIRI_DEFAULTS.cols;
        state.gridWidth = ONIGIRI_DEFAULTS.gridWidth; state.gridAlignment = ONIGIRI_DEFAULTS.gridAlignment;
        state.widgetHeight = ONIGIRI_DEFAULTS.widgetHeight;
        state.cells = {}; state.widgets = {};
        state.onigiriArchive = []; state.externalArchive = [];

        var unique = [];
        allIds.forEach(function (id) { if (unique.indexOf(id) === -1) unique.push(id); });

        unique.forEach(function (id) {
            var isDefault  = !!ONIGIRI_DEFAULTS.grid[id];
            var isExternal = state.externalDefaultNames.hasOwnProperty(id);
            if (isDefault) {
                var cfg = ONIGIRI_DEFAULTS.grid[id];
                state.widgets[id] = { kind: "onigiri", pos: cfg.pos, rowSpan: cfg.row, colSpan: cfg.col,
                    displayName: hostWidgetNames[id] || WIDGET_DEFAULT_NAMES[id] || id };
                writeCells(id, cfg.pos, cfg.row, cfg.col);
            } else if (isExternal) {
                state.externalArchive.push({ id: id, displayName: state.externalDefaultNames[id] || id });
            } else {
                state.onigiriArchive.push({ id: id, displayName: hostWidgetNames[id] || WIDGET_DEFAULT_NAMES[id] || id });
            }
        });

        afterMutation();
    }

    // ============================================================
    // Modal wiring
    // ============================================================

    var modal = OnigiriModal.create({
        id: "widget-layout",
        ownsGlobalUiState: false,
        buildWarmup: function () {
            var m = el("div", "wl-modal");
            m.style.width = "980px"; m.style.height = "680px";
            return m;
        },
        buildBackdrop: function (data) {
            closePopover();
            if (dragState) endDrag(null);
            loadDraft(data.draft);
            var onCommit = data.onCommit;

            var backdrop = el("div", "is-preparing");
            backdrop.id  = "onigiri-widget-layout-backdrop";

            var modalEl = el("div", "wl-modal");
            modalEl.addEventListener("click",        function (evt) { evt.stopPropagation(); });
            modalEl.addEventListener("pointerdown",  function (evt) { evt.stopPropagation(); });

            // Header
            var header    = el("div", "wl-header");
            var titleWrap = el("div");
            titleWrap.appendChild(el("div", "wl-title", "Edit Widget Layout"));
            titleWrap.appendChild(el("div", "wl-subtitle", "Drag widgets to reposition them. Double-tap a widget to rename or resize it."));
            header.appendChild(titleWrap);

            var closeBtn = el("button", "wl-close");
            closeBtn.type = "button";
            closeBtn.title = "Close";
            closeBtn.appendChild(maskIcon("wl-close-icon", "cancel.svg"));
            closeBtn.addEventListener("click", function () { modal.close(true); });
            header.appendChild(closeBtn);
            modalEl.appendChild(header);

            // Body
            var body      = el("div", "wl-body");
            var gridPanel = el("div", "wl-grid-panel");
            gridPanel.appendChild(el("div", "wl-grid-hint",
                "Drag to move. Drag to the archive panel to remove. Double-tap to rename or resize."));
            var gridEl = el("div", "wl-grid");
            gridPanel.appendChild(gridEl);
            body.appendChild(gridPanel);

            var archivePanel   = el("div", "wl-archive-panel");
            archivePanel.appendChild(el("div", "wl-archive-section-title", "Archived widgets"));
            var onigiriListEl  = el("div", "wl-archive-list");
            archivePanel.appendChild(onigiriListEl);
            archivePanel.appendChild(el("div", "wl-archive-section-title", "Archived add-on widgets"));
            var externalListEl = el("div", "wl-archive-list");
            archivePanel.appendChild(externalListEl);
            body.appendChild(archivePanel);
            modalEl.appendChild(body);

            // Footer
            var footer        = el("div", "wl-footer");
            var resetNamesBtn = el("button", "wl-btn", "Reset widget names");
            resetNamesBtn.type = "button";
            resetNamesBtn.addEventListener("click", resetWidgetNames);
            var resetLayoutBtn = el("button", "wl-btn", "Reset layout to default");
            resetLayoutBtn.type = "button";
            resetLayoutBtn.addEventListener("click", resetLayoutToDefault);
            footer.appendChild(resetNamesBtn);
            footer.appendChild(resetLayoutBtn);
            footer.appendChild(el("div", "wl-footer-spacer"));
            var cancelBtn = el("button", "wl-btn wl-btn-cancel", "Cancel");
            cancelBtn.type = "button";
            cancelBtn.addEventListener("click", function () { modal.close(true); });
            var saveBtn = el("button", "wl-btn wl-btn-save", "Save");
            saveBtn.type = "button";
            saveBtn.addEventListener("click", function () {
                var result = serialize();
                closePopover();
                modal.close(true);
                if (typeof onCommit === "function") onCommit(result);
            });
            footer.appendChild(cancelBtn);
            footer.appendChild(saveBtn);
            modalEl.appendChild(footer);

            backdrop.appendChild(modalEl);
            document.body.appendChild(backdrop);

            // Modal mode: no live host sync, commit only on Save.
            onInlineChange = null;
            inlineGetSlice = null;
            dom = { gridEl: gridEl, highlightEl: null, onigiriListEl: onigiriListEl,
                    externalListEl: externalListEl };

            renderGrid();
            renderArchives();

            return { backdrop: backdrop, focusTarget: null };
        },
        onClose: function () {
            closePopover();
            if (dragState) endDrag(null);
        }
    });

    // ============================================================
    // Inline embed (Main Menu → Layout tab)
    // ============================================================
    //
    // Builds the grid + archive mechanics directly inside a host container
    // instead of a stacked modal. Edits live-serialize back to the host via
    // opts.onChange so they persist through the host dialog's own Save.
    // opts.getSlice pulls the current layout slice from the host (used on
    // mount and on reload when the host's grid-size fields change).

    function mountInline(container, opts) {
        closePopover();
        if (dragState) endDrag(null);
        opts = opts || {};
        inlineGetSlice = opts.getSlice;
        onInlineChange = opts.onChange || null;

        loadDraft(inlineGetSlice());

        container.innerHTML = "";
        container.classList.add("wl-inline");

        var gridScroll = el("div", "wl-inline-grid-scroll");
        var gridEl     = el("div", "wl-grid");
        gridScroll.appendChild(gridEl);
        container.appendChild(gridScroll);

        var archivesWrap = el("div", "wl-inline-archives");
        var g1 = el("div", "wl-inline-archive-group");
        g1.appendChild(el("div", "wl-archive-section-title", "Archived widgets"));
        var onigiriListEl = el("div", "wl-archive-list");
        g1.appendChild(onigiriListEl);
        var g2 = el("div", "wl-inline-archive-group");
        g2.appendChild(el("div", "wl-archive-section-title", "Archived add-on widgets"));
        var externalListEl = el("div", "wl-archive-list");
        g2.appendChild(externalListEl);
        archivesWrap.appendChild(g1);
        archivesWrap.appendChild(g2);
        container.appendChild(archivesWrap);

        hostWidgetNames = opts.widgetNames || {};

        dom = { gridEl: gridEl, highlightEl: null, onigiriListEl: onigiriListEl,
                externalListEl: externalListEl };

        renderArchives();
        renderGrid();
        // The host builds the whole panel tree BEFORE attaching it to the
        // document, so at this point gridEl may be detached and measure 0px
        // wide, collapsing every tile. Re-render once on the next frame when
        // it's guaranteed to be in the DOM with a real width. Guard against a
        // teardown/remount having swapped dom out from under us.
        requestAnimationFrame(function () {
            if (dom && dom.gridEl === gridEl) renderGrid();
        });

        return {
            // Re-pull layout from host (e.g. after grid rows/cols changed) and
            // push the reconciled result straight back so any overflow that
            // got archived is reflected in the host draft immediately.
            reload: function () {
                if (!inlineGetSlice) return;
                loadDraft(inlineGetSlice());
                renderGrid();
                renderArchives();
                if (onInlineChange) onInlineChange(serialize());
            },
            resetLayout: resetLayoutToDefault,
            resetNames:  resetWidgetNames,
            destroy: function () {
                closePopover();
                if (dragState) endDrag(null);
                onInlineChange = null;
                inlineGetSlice = null;
                dom = null;
            }
        };
    }

    return {
        open: function (draftSlice, onCommit) { modal.open({ draft: draftSlice, onCommit: onCommit }); },
        close: modal.close,
        mountInline: mountInline
    };
})();
