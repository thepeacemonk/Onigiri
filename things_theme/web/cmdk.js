/* Anki Design — Cmd-K palette.
   Self-contained overlay injected on every themed webview. Listens for
   Cmd-K / Ctrl-K globally on the page; opens a centered modal with an
   input + ranked result list. Python is asked for results via
   pycmd("ba:cmdk-search:<q>"); it pushes back through
   window.__baCmdkResults({...}). Selecting an item sends
   pycmd("ba:cmdk-do:<encoded-action>"). */
(function () {
  "use strict";
  if (window.__baCmdk) return;
  window.__baCmdk = true;

  // ---------------------------------------------------------------- //
  // ICONS
  // ---------------------------------------------------------------- //
  var ICONS = {
    search:
      '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/>' +
      '<path d="M20 20l-4.3-4.3"/></svg>',
    deck:
      '<svg viewBox="0 0 24 24"><path d="M3 7l9-4 9 4-9 4-9-4z"/>' +
      '<path d="M3 12l9 4 9-4"/><path d="M3 17l9 4 9-4"/></svg>',
    card:
      '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/>' +
      '<path d="M3 10h18"/></svg>',
    tag:
      '<svg viewBox="0 0 24 24"><path d="M20 13L13 20a2 2 0 0 1-2.8 0L3 12.8V4h8.8L20 12.2a1 1 0 0 1 0 .8z"/>' +
      '<circle cx="7.5" cy="7.5" r="1.2"/></svg>',
    add:
      '<svg viewBox="0 0 24 24"><path d="M12 5v14"/><path d="M5 12h14"/></svg>',
    browse:
      '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/>' +
      '<path d="M20 20l-4.3-4.3"/></svg>',
    stats:
      '<svg viewBox="0 0 24 24"><path d="M4 19V9"/><path d="M10 19V5"/>' +
      '<path d="M16 19v-8"/><path d="M22 19h-22"/></svg>',
    sync:
      '<svg viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-3-6.7"/>' +
      '<path d="M21 4v5h-5"/></svg>',
    settings:
      '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/>' +
      '<path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3h0a1.6 1.6 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.6 1.6 0 0 0 1 1.5h0a1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8v0a1.6 1.6 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/></svg>',
    import:
      '<svg viewBox="0 0 24 24"><path d="M12 4v12"/>' +
      '<path d="M6 10l6-6 6 6"/><path d="M4 20h16"/></svg>',
    undo:
      '<svg viewBox="0 0 24 24"><path d="M3 12a8 8 0 1 0 3-6.2"/>' +
      '<path d="M3 4v5h5"/></svg>',
    home:
      '<svg viewBox="0 0 24 24"><path d="M3 11l9-7 9 7"/>' +
      '<path d="M5 10v9h14v-9"/></svg>',
    flag:
      '<svg viewBox="0 0 24 24"><path d="M4 4v17"/>' +
      '<path d="M4 4h12l-2 5 2 5H4"/></svg>',
    play:
      '<svg viewBox="0 0 24 24"><path d="M7 4l13 8-13 8z"/></svg>',
    eye:
      '<svg viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"/>' +
      '<circle cx="12" cy="12" r="3"/></svg>',
    theme:
      '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/>' +
      '<path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>',
  };
  function svg(kind) { return ICONS[kind] || ICONS.search; }

  // ---------------------------------------------------------------- //
  // DOM
  // ---------------------------------------------------------------- //
  var root, input, list, hintEl;
  var isOpen = false;
  var activeIdx = 0;
  var currentResults = [];     // flat list (sections + items interleaved)
  var currentItems = [];       // items only, in display order
  var seq = 0;                 // server query counter (latest-wins)

  function build() {
    if (root) return root;
    root = document.createElement("div");
    root.className = "ba-cmdk-back";
    root.setAttribute("data-open", "false");
    root.innerHTML =
      '<div class="ba-cmdk" role="dialog" aria-label="Command palette">' +
      '  <div class="ba-cmdk-input-row">' +
      '    <span class="ba-cmdk-glyph">' + svg("search") + "</span>" +
      '    <input class="ba-cmdk-input" type="text" autocomplete="off" ' +
      '           spellcheck="false" autocapitalize="off" ' +
      '           placeholder="Search decks, cards, tags, actions…" />' +
      '    <span class="ba-cmdk-hint">' +
      '      <span class="ba-cmdk-kbd">Esc</span> to close' +
      "    </span>" +
      "  </div>" +
      '  <div class="ba-cmdk-list" role="listbox"></div>' +
      '  <div class="ba-cmdk-foot">' +
      '    <span class="ba-cmdk-foot-l">' +
      '      <span class="ba-cmdk-foot-item">' +
      '        <span class="ba-cmdk-kbd">↑</span>' +
      '        <span class="ba-cmdk-kbd">↓</span> navigate' +
      "      </span>" +
      '      <span class="ba-cmdk-foot-item">' +
      '        <span class="ba-cmdk-kbd">↵</span> select' +
      "      </span>" +
      "    </span>" +
      '    <span class="ba-cmdk-foot-r">Anki Design</span>' +
      "  </div>" +
      "</div>";

    document.body.appendChild(root);
    input = root.querySelector(".ba-cmdk-input");
    list = root.querySelector(".ba-cmdk-list");
    hintEl = root.querySelector(".ba-cmdk-hint");

    // Click outside the panel closes.
    root.addEventListener("mousedown", function (e) {
      if (e.target === root) close();
    });
    // Suppress accidental form submission inside the host page.
    root.addEventListener("submit", function (e) { e.preventDefault(); });

    input.addEventListener("input", onInput);
    input.addEventListener("keydown", onKey);

    list.addEventListener("mousemove", function (e) {
      var row = e.target.closest(".ba-cmdk-item");
      if (!row) return;
      var idx = parseInt(row.getAttribute("data-idx"), 10);
      if (!isNaN(idx) && idx !== activeIdx) {
        activeIdx = idx;
        repaintActive();
      }
    });
    list.addEventListener("click", function (e) {
      var row = e.target.closest(".ba-cmdk-item");
      if (!row) return;
      var idx = parseInt(row.getAttribute("data-idx"), 10);
      if (!isNaN(idx)) {
        activeIdx = idx;
        commit();
      }
    });

    return root;
  }

  function pycmdSend(cmd) {
    try { if (typeof pycmd === "function") pycmd("ba:" + cmd); } catch (e) {}
  }

  // ---------------------------------------------------------------- //
  // INPUT / KEYS
  // ---------------------------------------------------------------- //
  var debounceTimer = null;
  function onInput() {
    clearTimeout(debounceTimer);
    var q = input.value;
    debounceTimer = setTimeout(function () { runSearch(q); }, 60);
  }
  function runSearch(q) {
    seq += 1;
    // Encode the query through URI so colons in user text (e.g. "deck:foo")
    // don't collide with our pycmd colon delimiter on the Python side.
    pycmdSend("cmdk-search:" + seq + ":" + encodeURIComponent(q || ""));
  }

  function onKey(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      moveActive(+1);
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      moveActive(-1);
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      commit();
      return;
    }
    if ((e.key === "n" || e.key === "p") && (e.ctrlKey || e.metaKey)) {
      // Ctrl-N / Ctrl-P (Emacs-style), parallels common palette UX.
      e.preventDefault();
      moveActive(e.key === "n" ? +1 : -1);
      return;
    }
    if (e.key === "Tab") {
      // Tab kills focus traps in some host pages — keep focus on the input.
      e.preventDefault();
    }
  }

  function moveActive(delta) {
    if (!currentItems.length) return;
    activeIdx = (activeIdx + delta + currentItems.length) % currentItems.length;
    repaintActive();
    scrollActiveIntoView();
  }
  function repaintActive() {
    if (!list) return;
    var rows = list.querySelectorAll(".ba-cmdk-item");
    for (var i = 0; i < rows.length; i++) {
      var idx = parseInt(rows[i].getAttribute("data-idx"), 10);
      rows[i].setAttribute("data-active", idx === activeIdx ? "true" : "false");
    }
  }
  function scrollActiveIntoView() {
    var row = list.querySelector('.ba-cmdk-item[data-idx="' + activeIdx + '"]');
    if (!row) return;
    var rTop = row.offsetTop;
    var rBot = rTop + row.offsetHeight;
    var lTop = list.scrollTop;
    var lBot = lTop + list.clientHeight;
    if (rTop < lTop + 8) list.scrollTop = Math.max(0, rTop - 8);
    else if (rBot > lBot - 8) list.scrollTop = rBot - list.clientHeight + 8;
  }

  function commit() {
    var item = currentItems[activeIdx];
    if (!item) return;
    // Hide immediately so the user feels the click; the Python action will
    // run and may navigate (closing the webview anyway).
    var action = item.do || "";
    close();
    if (action) pycmdSend("cmdk-do:" + action);
  }

  // ---------------------------------------------------------------- //
  // RENDER
  // ---------------------------------------------------------------- //
  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  // Wraps occurrences of `q`'s tokens in <em> for the title field. Server
  // returns the title plain — we highlight client-side so it always tracks
  // the current input even when the server response races ahead.
  function highlight(text, q) {
    var s = escapeHtml(text);
    if (!q) return s;
    var tokens = String(q).trim().split(/\s+/).filter(Boolean);
    tokens.sort(function (a, b) { return b.length - a.length; });
    for (var i = 0; i < tokens.length; i++) {
      var t = tokens[i].replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      if (!t) continue;
      try {
        s = s.replace(new RegExp("(" + t + ")", "ig"), "<em>$1</em>");
      } catch (e) {}
    }
    return s;
  }

  function renderResults(payload) {
    var sections = (payload && payload.sections) || [];
    var q = (payload && payload.q) || "";
    currentItems = [];
    var html = "";
    var idx = 0;

    for (var s = 0; s < sections.length; s++) {
      var sec = sections[s] || {};
      var items = sec.items || [];
      if (!items.length) continue;
      html += '<div class="ba-cmdk-section">' + escapeHtml(sec.title || "") + "</div>";
      for (var i = 0; i < items.length; i++) {
        var it = items[i];
        currentItems.push(it);
        var meta = it.meta ? '<span class="ba-cmdk-meta">' + escapeHtml(it.meta) + "</span>" : "";
        var chip = it.chip ? '<span class="ba-cmdk-chip">' + escapeHtml(it.chip) + "</span>" : "";
        var sub = it.sub
          ? '<div class="ba-cmdk-sub">' + highlight(it.sub, q) + "</div>"
          : "";
        html +=
          '<div class="ba-cmdk-item" role="option" data-idx="' + idx + '" data-active="false">' +
          '  <span class="ba-cmdk-ico">' + svg(it.icon || "search") + "</span>" +
          '  <div class="ba-cmdk-body">' +
          '    <div class="ba-cmdk-title">' + highlight(it.title, q) + "</div>" +
          sub +
          "  </div>" +
          meta + chip +
          "</div>";
        idx += 1;
      }
    }

    if (!currentItems.length) {
      var emptyMsg = q
        ? '<div class="ba-cmdk-empty">No matches for <strong>'
            + escapeHtml(q) + "</strong></div>"
        : '<div class="ba-cmdk-empty">Type to search decks, cards, tags, actions.</div>';
      list.innerHTML = emptyMsg;
      activeIdx = 0;
      return;
    }

    list.innerHTML = html;
    activeIdx = Math.min(activeIdx, currentItems.length - 1);
    if (activeIdx < 0) activeIdx = 0;
    repaintActive();
    list.scrollTop = 0;
  }

  // Python pushes here. Payload: { seq, q, sections: [{title, items: [...]}] }
  // Items: { do, title, sub?, meta?, chip?, icon? }
  window.__baCmdkResults = function (payload) {
    if (!root || !isOpen) return;
    if (!payload) return;
    // Latest-wins: drop replies older than the input we currently care about.
    if (payload.seq && payload.seq < seq - 1) return;
    renderResults(payload);
  };

  // ---------------------------------------------------------------- //
  // OPEN / CLOSE
  // ---------------------------------------------------------------- //
  function open(initialQuery) {
    build();
    if (isOpen) {
      if (initialQuery != null) input.value = initialQuery;
      input.focus();
      input.select();
      runSearch(input.value);
      return;
    }
    isOpen = true;
    activeIdx = 0;
    if (initialQuery != null) input.value = initialQuery;
    root.setAttribute("data-open", "true");
    list.innerHTML =
      '<div class="ba-cmdk-empty">Loading…</div>';
    // Async focus so the open animation kicks in before the keyboard caret.
    requestAnimationFrame(function () {
      input.focus();
      input.select();
      runSearch(input.value);
    });
  }
  function close() {
    if (!root || !isOpen) return;
    isOpen = false;
    root.setAttribute("data-open", "false");
    try { input.blur(); } catch (e) {}
    // Notify Python so the cmdk overlay (a Qt frame holding a dedicated
    // webview for use over embeds) can hide itself. No-op when the palette
    // is hosted in mw.web / reviewer.web.
    pycmdSend("cmdk-closed");
  }
  function toggle(initialQuery) {
    if (isOpen) close();
    else open(initialQuery);
  }
  window.__baCmdkOpen = open;
  window.__baCmdkClose = close;
  window.__baCmdkToggle = toggle;

  // ---------------------------------------------------------------- //
  // GLOBAL HOTKEY (Cmd-K / Ctrl-K; also Cmd-Shift-P like VS Code)
  // ---------------------------------------------------------------- //
  // Capture-phase listener so we win even when a host element wants the
  // event. We accept the modifier on either Meta (macOS) or Ctrl. Route
  // through Python (`ba:cmdk-open`) when opening so any Qt-side embed
  // (Add Cards, Browser, Stats, Settings) is torn down before the
  // palette renders — otherwise the embed overlay sits on top of mw.web
  // and obscures the palette.
  document.addEventListener("keydown", function (e) {
    var mod = e.metaKey || e.ctrlKey;
    if (!mod) return;
    var k = (e.key || "").toLowerCase();
    if (k === "k" || (e.shiftKey && k === "p")) {
      e.preventDefault();
      e.stopPropagation();
      if (isOpen) {
        close();
      } else {
        pycmdSend("cmdk-open");
      }
    }
  }, true);

  // Build lazily on first toggle to keep DOM clean until needed.
})();
