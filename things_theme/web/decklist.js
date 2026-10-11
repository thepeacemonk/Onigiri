// Anki Design — shared deck-list primitives.
//
// Both the home-page tree and the congrats "Keep going" list render the
// same row shape:
//
//     [chevron]  [name]  [counts]  [gear]
//
// This module owns:
//
//   - the chevron / gear markup
//   - the collapse state (see "Collapse state" below)
//   - a generic visibility resolver for a flat, depth-tagged row list
//   - drag-to-move (reparenting) wiring
//
// Pages that consume this module own the DOM container; this module only
// cares about the data attributes (`data-did`, `data-depth`) and class
// hooks (`ad-list-row-hidden`).
(function () {
  "use strict";
  if (window.__adDeckList) return;

  // Down chevron at rest; CSS rotates it -90° when ad-list-chev--collapsed.
  var CHEV_SVG =
    '<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" ' +
    'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" ' +
    'aria-hidden="true"><polyline points="3,4.6 6,7.6 9,4.6"/></svg>';

  // Lucide Settings: inline currentColor SVG stays crisp at every scale and
  // follows the Kome palette without bitmap filters.
  var GEAR_HTML =
    '<svg class="ad-list-gear-icon" viewBox="0 0 24 24" aria-hidden="true">' +
      '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.09a2 2 0 0 1 1 1.74v.5a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.09a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>' +
      '<circle cx="12" cy="12" r="3"/>' +
    '</svg>';

  var STORAGE_KEY = "__adCollapsedDecks";
  var SEED_KEY = "__adCollapsedSeeded";

  function slice(list) { return Array.prototype.slice.call(list || []); }

  function listOpts() {
    var o = window.__baOpts && window.__baOpts.deckList;
    return o || {};
  }

  // ---- Collapse state --------------------------------------------------
  // Three modes (Settings → Deck list → "Sub-decks on startup"):
  //
  //   remember  — Anki's own persisted flag. Each row arrives with
  //               `collapsed` read from the collection; toggles are written
  //               back through Python (`ba:deck:collapse:<did>`), so the
  //               state survives restarts and syncs, and matches what
  //               AnkiMobile / AnkiWeb show. This is the default.
  //   expanded  — everything open at launch; toggles live for the session
  //               only (sessionStorage) and never touch the collection.
  //   collapsed — every parent closed at launch; same session-only toggles.
  function startupMode() {
    var m = listOpts().startup || "remember";
    return (m === "expanded" || m === "collapsed") ? m : "remember";
  }

  var memState = null;  // remember-mode working copy for this page

  function loadSession() {
    try {
      var raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (_) { return {}; }
  }

  function saveSession(state) {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
    catch (_) {}
  }

  // Build the starting collapse set for a render from the row data.
  function initialState(decks) {
    var mode = startupMode();
    var i;
    if (mode === "remember") {
      var st = {};
      for (i = 0; i < decks.length; i++) {
        if (decks[i].collapsed && decks[i].isParent) st[String(decks[i].did)] = 1;
      }
      memState = st;
      return st;
    }
    if (mode === "collapsed") {
      var seeded = false;
      try { seeded = sessionStorage.getItem(SEED_KEY) === "1"; } catch (_) {}
      if (!seeded) {
        var all = {};
        for (i = 0; i < decks.length; i++) {
          if (decks[i].isParent) all[String(decks[i].did)] = 1;
        }
        saveSession(all);
        try { sessionStorage.setItem(SEED_KEY, "1"); } catch (_) {}
        return all;
      }
    }
    return loadSession();
  }

  // Current collapse set — whatever the last render established.
  function loadCollapsed() {
    if (startupMode() === "remember") return memState || {};
    return loadSession();
  }

  function saveCollapsed(state) {
    if (startupMode() === "remember") { memState = state; return; }
    saveSession(state);
  }

  function toggle(did) {
    var key = String(did);
    if (startupMode() === "remember") {
      var s = memState || (memState = {});
      if (s[key]) delete s[key]; else s[key] = 1;
      // Persist through Anki's own collapse flag. We send the resulting
      // state (not "toggle") so rapid clicks can't drift out of step with
      // the backend; Python writes it without re-rendering the page.
      try {
        if (typeof pycmd === "function") {
          pycmd("ba:deck:collapse:" + key + ":" + (s[key] ? "1" : "0"));
        }
      } catch (_) {}
      return s;
    }
    var st = loadSession();
    if (st[key]) delete st[key]; else st[key] = 1;
    saveSession(st);
    return st;
  }

  // Walk a flat ordered list of rows. For each row, hide it iff any
  // ancestor (by depth) is in the collapsed set. `getDid(row)` returns the
  // deck id string; `getDepth(row)` returns a non-negative integer.
  function applyVisibility(rows, getDid, getDepth, state) {
    state = state || loadCollapsed();
    var stack = []; // { did, depth } entries, deepest last
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var depth = getDepth(row);
      while (stack.length && stack[stack.length - 1].depth >= depth) stack.pop();
      var hidden = false;
      for (var k = 0; k < stack.length; k++) {
        if (state[stack[k].did]) { hidden = true; break; }
      }
      row.classList.toggle("ad-list-row-hidden", hidden);
      stack.push({ did: getDid(row), depth: depth });
    }
  }

  // Build the inner HTML for a chevron control. `did` may be 0/empty for
  // a leaf — caller renders the spacer markup instead in that case.
  function chevronHTML(did, collapsed) {
    return '<button class="ad-list-chev'
      + (collapsed ? ' ad-list-chev--collapsed' : '')
      + '" type="button" data-did="' + did + '"'
      + ' aria-label="' + (collapsed ? 'Expand' : 'Collapse')
      + ' sub-decks" tabindex="-1">'
      + CHEV_SVG + '</button>';
  }

  function spacerHTML() {
    return '<span class="ad-list-chev ad-list-chev--spacer" aria-hidden="true"></span>';
  }

  // Column-label row above the rows — same grid as .ad-list-row so the
  // labels line up with Progress / New / Learn / Due.
  var HEADER_HTML =
    '<div class="ad-list-header">' +
    '<span aria-hidden="true"></span>' +
    '<span class="ad-list-header-cell">Deck</span>' +
    '<span class="ad-list-header-cell ad-list-header-cell--progress">Progress</span>' +
    '<span class="ad-list-header-cell ad-list-header-cell--new">New</span>' +
    '<span class="ad-list-header-cell ad-list-header-cell--learn">Learn</span>' +
    '<span class="ad-list-header-cell ad-list-header-cell--due">Due</span>' +
    '<span aria-hidden="true"></span>' +
    '</div>';

  function gearHTML(did) {
    return '<button class="ad-list-gear" type="button" data-did="' + did + '"'
      + ' title="Deck options" aria-label="Deck options">'
      + GEAR_HTML + '</button>';
  }

  // Update a chevron element's collapsed state visually + aria. Used by
  // page-specific click handlers after toggle().
  function paintChev(chevEl, collapsed) {
    chevEl.classList.toggle("ad-list-chev--collapsed", collapsed);
    chevEl.setAttribute("aria-label",
      (collapsed ? "Expand" : "Collapse") + " sub-decks");
    var row = chevEl.closest && chevEl.closest('.ad-list-row');
    if (row) row.setAttribute('data-collapsed', collapsed ? 'true' : 'false');
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' })[c];
    });
  }

  // Walk the flat, depth-tagged list and derive its visible family tree. The
  // DOM intentionally stays flat (collapse/drag remain simple), while the
  // parent tag lets CSS indent and softly group children.
  function annotateParents(decks) {
    var out = [];
    var ancestors = [];
    for (var i = 0; i < decks.length; i++) {
      var d = decks[i];
      var next = decks[i + 1];
      var depth = Math.max(0, parseInt(d.depth || 0, 10));
      ancestors.length = depth;
      var parentDid = depth > 0 && ancestors[depth - 1]
        ? ancestors[depth - 1].did
        : null;
      // "Done today" is backend-supplied (home tree only — the congrats
      // list's filtered tree doesn't compute it); missing means the
      // progress bar just renders as an empty rail with no percent.
      var done = (typeof d.done === "number") ? d.done : null;
      var due = (d.learn || 0) + (d.review || 0);
      // Only a deck with actual study today shows a filled bar + percent —
      // due-but-untouched decks get an empty rail, same as the reference.
      var progressPct = null;
      if (done != null && done > 0) {
        progressPct = Math.round((done / (done + due)) * 100);
      }
      out.push({
        did: d.did,
        name: d.name,
        path: d.path || d.name,
        depth: depth,
        parentDid: parentDid,
        new: d.new || 0,
        learn: d.learn || 0,
        review: d.review || 0,
        due: due,
        progressPct: progressPct,
        current: !!d.current,
        filtered: !!d.filtered,
        collapsed: !!d.collapsed,
        icon: d.icon || null,
        isParent: !!(next && (next.depth || 0) > depth),
      });
      ancestors[depth] = { did: d.did };
    }
    return out;
  }

  function safeIconColor(value) {
    value = String(value || '').trim();
    return /^#[0-9a-f]{3,8}$/i.test(value) ? value : '';
  }

  function deckIconHTML(node) {
    var icon = node.icon || {};
    var kind = icon.kind || 'mask';
    var url = icon.url || '';
    if (!url) {
      var base = window.__baDeckIconBase || '';
      var filename = node.filtered
        ? 'filtered-deck.svg'
        : (node.isParent ? 'folder.svg' : (node.depth ? 'subdeck.svg' : 'deck.svg'));
      url = base + '/' + filename;
    }

    var light = safeIconColor(icon.colorLight);
    var dark = safeIconColor(icon.colorDark || light);
    var style = '';
    if (light) style += '--ad-icon-light:' + light + ';';
    if (dark) style += '--ad-icon-dark:' + dark + ';';

    var visual;
    if (kind === 'emoji') {
      visual = '<span class="ad-list-deck-icon-emoji" aria-hidden="true">'
        + escapeHTML(icon.text || '') + '</span>';
    } else if (kind === 'image') {
      visual = '<img class="ad-list-deck-icon-image" src="'
        + escapeHTML(url) + '" alt="" aria-hidden="true">';
    } else {
      style += '--ad-icon-image:url(&quot;' + escapeHTML(url) + '&quot;);';
      visual = '<span class="ad-list-deck-icon-mask" aria-hidden="true"></span>';
    }
    return '<button class="ad-list-deck-icon" type="button" data-did="'
      + node.did + '" title="Choose deck icon" aria-label="Choose icon for '
      + escapeHTML(node.name || 'deck') + '"'
      + (style ? ' style="' + style + '"' : '') + '>'
      + visual + '</button>';
  }

  // Right-aligned count cell. 0 renders as blank grid space (no "0"), not
  // a dimmed digit.
  function countCell(n, cls) {
    return '<span class="' + cls + '">' + (n ? n : '') + '</span>';
  }

  // Progress cell: a thin rail + (when the deck was actually studied
  // today) a filled portion and a trailing percent. The percent span is
  // ALWAYS rendered, even empty — if it only appeared on rows with a
  // number, the track next to it would be a different width than the
  // track on every plain row above/below it (which has no percent to
  // share space with). That width mismatch, repeated down a grid-aligned
  // column, is what reads as one short bar sitting nested inside a
  // longer one. Reserving the same slot on every row keeps every track
  // in the list exactly the same length.
  function progressHTML(pct) {
    if (pct == null) {
      return '<span class="ad-list-progress">'
        + '<span class="ad-list-progress-track"></span>'
        + '<span class="ad-list-progress-pct"></span>'
        + '</span>';
    }
    var clamped = Math.max(0, Math.min(100, pct));
    return '<span class="ad-list-progress">'
      + '<span class="ad-list-progress-track">'
      +   '<span class="ad-list-progress-fill" style="width:' + clamped + '%"></span>'
      + '</span>'
      + '<span class="ad-list-progress-pct">' + clamped + '%</span>'
      + '</span>';
  }

  function rowHTML(node, collapsedState) {
    var name = node.name == null ? '' : String(node.name);
    var depth = node.depth || 0;
    var did = node.did;
    var collapsed = !!(collapsedState && collapsedState[did]);
    // Parents keep their expand/collapse control; every leaf uses the same
    // blank spacer so the current deck has no bookmark marker.
    var chev = node.isParent
      ? chevronHTML(did, collapsed)
      : spacerHTML();
    var attrs = ' data-did="' + did + '" data-depth="' + depth + '"'
      + ' style="--ad-indent:' + (depth * 24) + 'px"';
    if (node.parentDid != null) attrs += ' data-parent-did="' + node.parentDid + '"';
    if (node.isParent) attrs += ' data-has-children="true" data-collapsed="'
      + (collapsed ? 'true' : 'false') + '"';
    if (node.current)  attrs += ' data-current="true"';
    if (node.filtered) attrs += ' data-filtered="true"';
    return ''
      + '<div class="ad-list-row"' + attrs + '>'
      +   '<div class="ad-list-tree">'
      +     chev
      +     '<span class="ad-list-title">'
      +       deckIconHTML(node)
      +       '<button class="ad-list-name" type="button" data-did="' + did + '">'
      +         '<span class="ad-list-name-text">' + escapeHTML(name) + '</span>'
      +       '</button>'
      +     '</span>'
      +   '</div>'
      +   progressHTML(node.progressPct)
      +   countCell(node.new, 'ad-list-new')
      +   countCell(node.learn, 'ad-list-learn')
      +   countCell(node.review, 'ad-list-due')
      +   gearHTML(did)
      + '</div>';
  }

  function rowsOf(container) {
    return slice(container.querySelectorAll('.ad-list-row'));
  }
  function rowDid(r) { return r.getAttribute('data-did'); }
  function rowDepth(r) { return parseInt(r.getAttribute('data-depth') || '0', 10); }

  // ---- Drag to move ---------------------------------------------------
  // Rows are HTML5 drag sources. Dropping a deck on another deck moves it
  // underneath (Anki's reparent op — same as its native table); a nested
  // deck also gets a "top level" drop zone at the head of the list. You
  // can't drop a deck on itself, on its own descendants, or on the parent
  // it already has.
  function wireDrag(container, opts) {
    var drag = { did: null, depth: 0, blocked: {} };
    var zone = null;

    function ensureZone() {
      if (zone) return zone;
      zone = document.createElement('div');
      zone.className = 'ad-list-dropzone';
      zone.textContent = 'Drop here to make it a top-level deck';
      container.insertBefore(zone, container.firstChild);
      return zone;
    }
    function clearTargets() {
      rowsOf(container).forEach(function (r) { r.classList.remove('ad-list-row--drop'); });
      if (zone) zone.classList.remove('ad-list-dropzone--over');
    }
    function cleanup() {
      clearTargets();
      rowsOf(container).forEach(function (r) { r.classList.remove('ad-list-row--dragging'); });
      container.classList.remove('ad-list--dragging');
      if (zone) zone.classList.remove('ad-list-dropzone--show');
      drag.did = null;
      drag.blocked = {};
    }
    function finish(targetDid) {
      var src = drag.did;
      cleanup();
      if (src == null) return;
      if (opts.onMove) { opts.onMove(src, targetDid); return; }
      try {
        if (typeof pycmd === "function") {
          pycmd('ba:deck:reparent:' + src + ':' + targetDid);
        }
      } catch (_) {}
    }

    rowsOf(container).forEach(function (row) {
      row.setAttribute('draggable', 'true');
    });

    container.addEventListener('dragstart', function (e) {
      var row = e.target.closest && e.target.closest('.ad-list-row');
      if (!row) return;
      // No drags from the chevron / gear, or while a rename input is up.
      if (e.target.closest('.ad-list-chev, .ad-list-deck-icon, .ad-list-gear, input')) {
        e.preventDefault();
        return;
      }
      var all = rowsOf(container);
      var idx = all.indexOf(row);
      drag.did = rowDid(row);
      drag.depth = rowDepth(row);
      drag.blocked = {};
      drag.blocked[drag.did] = 1;
      var i;
      for (i = idx + 1; i < all.length; i++) {       // descendants
        if (rowDepth(all[i]) <= drag.depth) break;
        drag.blocked[rowDid(all[i])] = 1;
      }
      for (i = idx - 1; i >= 0; i--) {                // current parent
        if (rowDepth(all[i]) < drag.depth) { drag.blocked[rowDid(all[i])] = 1; break; }
      }
      try {
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', String(drag.did));
      } catch (_) {}
      container.classList.add('ad-list--dragging');
      row.classList.add('ad-list-row--dragging');
      if (drag.depth > 0) ensureZone().classList.add('ad-list-dropzone--show');
    });

    container.addEventListener('dragover', function (e) {
      if (drag.did == null) return;
      clearTargets();
      var z = e.target.closest && e.target.closest('.ad-list-dropzone');
      if (z) {
        if (drag.depth === 0) return;
        e.preventDefault();
        try { e.dataTransfer.dropEffect = 'move'; } catch (_) {}
        z.classList.add('ad-list-dropzone--over');
        return;
      }
      var row = e.target.closest && e.target.closest('.ad-list-row');
      if (!row) return;
      if (drag.blocked[rowDid(row)]) return;
      e.preventDefault();
      try { e.dataTransfer.dropEffect = 'move'; } catch (_) {}
      row.classList.add('ad-list-row--drop');
    });

    container.addEventListener('drop', function (e) {
      if (drag.did == null) return;
      var z = e.target.closest && e.target.closest('.ad-list-dropzone');
      if (z) {
        e.preventDefault();
        if (drag.depth > 0) finish(0); else cleanup();
        return;
      }
      var row = e.target.closest && e.target.closest('.ad-list-row');
      if (!row) return;
      e.preventDefault();
      var did = rowDid(row);
      if (drag.blocked[did]) { cleanup(); return; }
      finish(did);
    });

    container.addEventListener('dragend', cleanup);
  }

  // Render an entire deck list into `container`. Both the home page and the
  // congrats Keep-going list call this with the same data shape, so the
  // resulting DOM is byte-identical. Callbacks are page-specific:
  //   - opts.onStudy(did)        — fired on row-name click
  //   - opts.onOptsClick(did, e) — fired on gear click (default: __adDeckOpts)
  //   - opts.onMove(did, target) — fired on drop (default: ba:deck:reparent)
  //   - opts.dragMove            — false to disable drag-to-move for this list
  function render(container, decks, opts) {
    if (!container) return;
    opts = opts || {};
    var nodes = annotateParents(decks);
    var state = initialState(nodes);
    var html = nodes
      .map(function (n) { return rowHTML(n, state); })
      .join('');
    if (opts.header !== false) html = HEADER_HTML + html;
    container.innerHTML = html;
    applyVisibility(rowsOf(container), rowDid, rowDepth, state);

    if (!container.__adWired) {
      container.__adWired = true;
      container.addEventListener('click', function (e) {
        // Chevron: toggle children visibility for this row's deck.
        var chev = e.target.closest && e.target.closest('.ad-list-chev');
        if (chev && chev.tagName === 'BUTTON') {
          e.preventDefault();
          e.stopPropagation();
          var did = chev.getAttribute('data-did');
          if (!did) return;
          var s = toggle(did);
          paintChev(chev, !!s[did]);
          applyVisibility(rowsOf(container), rowDid, rowDepth, s);
          return;
        }
        // Deck icon: open the same collection-backed chooser Classic uses.
        var icon = e.target.closest && e.target.closest('.ad-list-deck-icon');
        if (icon) {
          e.preventDefault();
          e.stopPropagation();
          var idid = parseInt(icon.getAttribute('data-did') || '0', 10);
          if (!idid) return;
          if (opts.onIconClick) opts.onIconClick(idid, e);
          else {
            try {
              if (typeof pycmd === 'function') pycmd('onigiri_ctx_change_icon:' + idid);
            } catch (_) {}
          }
          return;
        }
        // Gear: open the deck-options menu.
        var gear = e.target.closest && e.target.closest('.ad-list-gear');
        if (gear) {
          e.preventDefault();
          e.stopPropagation();
          var gdid = parseInt(gear.getAttribute('data-did') || '0', 10);
          if (!gdid) return;
          if (opts.onOptsClick) opts.onOptsClick(gdid, e);
          else if (window.__adDeckOpts) window.__adDeckOpts(gdid, e);
          return;
        }
        // Name (or anywhere else on the row that's not a control): study.
        var row = e.target.closest && e.target.closest('.ad-list-row');
        if (row && opts.onStudy) {
          var ndid = parseInt(row.getAttribute('data-did') || '0', 10);
          if (ndid) opts.onStudy(ndid, e);
        }
      });
      if (opts.dragMove !== false && listOpts().dragMove !== false) {
        wireDrag(container, opts);
      }
    }
  }

  window.__adDeckList = {
    CHEV_SVG: CHEV_SVG,
    GEAR_HTML: GEAR_HTML,
    STORAGE_KEY: STORAGE_KEY,
    startupMode: startupMode,
    loadCollapsed: loadCollapsed,
    saveCollapsed: saveCollapsed,
    toggle: toggle,
    applyVisibility: applyVisibility,
    chevronHTML: chevronHTML,
    spacerHTML: spacerHTML,
    gearHTML: gearHTML,
    paintChev: paintChev,
    annotateParents: annotateParents,
    render: render,
  };
})();
