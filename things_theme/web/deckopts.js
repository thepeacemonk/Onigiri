/* Anki Design — custom deck-options menu behavior.

   Triggered by `window.__adDeckOpts(deckId, event)`, called from the gear
   button next to the deck name. Renders a small floating menu anchored to
   the gear; clicking an item dispatches a `ba:deck:<action>:<did>` pycmd
   for Python to handle. */
(function () {
  "use strict";
  if (window.__adDeckOpts) return;

  var CURRENT = null;  // active menu DOM node, if any

  function icon(paths) {
    return '<svg class="ad-menu-icon" viewBox="0 0 24 24" fill="none" '
         + 'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
         + 'stroke-linejoin="round" aria-hidden="true">' + paths + '</svg>';
  }

  // Lightweight stroke set matching the sidebar icons.
  var ICONS = {
    rename:  '<path d="M4 20h4l11-11-4-4L4 16v4z"/><path d="M14 6l4 4"/>',
    icon:    '<circle cx="12" cy="12" r="9"/>'
           + '<circle cx="9" cy="9" r="1"/><circle cx="15" cy="9" r="1"/>'
           + '<path d="M8 15c1.1 1 2.4 1.5 4 1.5s2.9-.5 4-1.5"/>',
    move:    '<path d="M5 9l-3 3 3 3"/><path d="M9 5l3-3 3 3"/>'
           + '<path d="M15 19l-3 3-3-3"/><path d="M19 9l3 3-3 3"/>'
           + '<path d="M2 12h20"/><path d="M12 2v20"/>',
    options: '<circle cx="12" cy="12" r="3"/>'
           + '<path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1'
           + 'a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1'
           + 'a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8'
           + 'l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 0 1 0-4'
           + 'h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 '
           + '2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3h0a1.6 1.6 0 0 0 1-1.5V3a2 2 0 '
           + '0 1 4 0v.1a1.6 1.6 0 0 0 1 1.5h0a1.6 1.6 0 0 0 1.8-.3l.1-.1a2 '
           + '2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8v0a1.6 1.6 0 0 0 1.5 '
           + '1H21a2 2 0 0 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>',
    export:  '<path d="M12 16V4"/><path d="M6 10l6-6 6 6"/><path d="M4 20h16"/>',
    rebuild: '<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/>',
    empty:   '<path d="M3 6h18"/><path d="M8 6V4h8v2"/>'
           + '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>',
    delete:  '<path d="M3 6h18"/><path d="M8 6V4h8v2"/>'
           + '<path d="M10 11v6"/><path d="M14 11v6"/>'
           + '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>',
  };

  // Each entry: { cmd, label, icon, danger?, filteredOnly?, sep_before? }
  var ITEMS = [
    { cmd: "rename",  label: window.onigiriText("Rename"),           icon: "rename" },
    { cmd: "change-icon", label: window.onigiriText("Change icon…"), icon: "icon" },
    { cmd: "move",    label: window.onigiriText("Move to…"),         icon: "move" },
    { cmd: "options", label: window.onigiriText("Options…"),         icon: "options" },
    { cmd: "export",  label: window.onigiriText("Export deck…"),     icon: "export" },
    { cmd: "rebuild", label: window.onigiriText("Rebuild"),           icon: "rebuild", filteredOnly: true },
    { cmd: "empty",   label: window.onigiriText("Empty"),             icon: "empty", filteredOnly: true },
    { cmd: "delete",  label: window.onigiriText("Delete deck"),      icon: "delete", danger: true, sep_before: true },
  ];

  function send(cmd) {
    try { if (typeof pycmd === "function") pycmd("ba:" + cmd); } catch (e) {}
  }

  function close() {
    if (!CURRENT) return;
    var node = CURRENT;
    CURRENT = null;
    node.classList.remove("ad-menu--open");
    // Allow the transition to finish before removing from the DOM.
    setTimeout(function () {
      if (node && node.parentNode) node.parentNode.removeChild(node);
    }, 160);
    document.removeEventListener("mousedown", outsideClick, true);
    document.removeEventListener("keydown", escClose, true);
    window.removeEventListener("resize", close);
    window.removeEventListener("scroll", close, true);
  }

  function outsideClick(e) {
    if (!CURRENT) return;
    if (CURRENT.contains(e.target)) return;
    close();
  }
  function escClose(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  }

  function isFilteredDeck(did) {
    var selector = '[data-did="' + String(did) + '"]';
    var row = document.querySelector('.ad-list-row' + selector);
    if (row) return row.getAttribute('data-filtered') === 'true';

    row = document.querySelector('tr.deck' + selector);
    if (row) {
      return row.classList.contains('is-filtered')
        || !!row.querySelector('a.deck.filtered');
    }

    var decks = window.__baDeckTree || [];
    for (var i = 0; i < decks.length; i++) {
      if (String(decks[i].did) === String(did)) return !!decks[i].filtered;
    }
    return false;
  }

  function build(did) {
    var menu = document.createElement("div");
    menu.className = "ad-menu";
    menu.setAttribute("role", "menu");
    var html = "";
    var filtered = isFilteredDeck(did);
    ITEMS.forEach(function (it) {
      if (it.filteredOnly && !filtered) return;
      if (it.sep_before) html += '<div class="ad-menu-sep" role="separator"></div>';
      var cls = "ad-menu-item" + (it.danger ? " ad-menu-danger" : "");
      html += '<button type="button" class="' + cls + '" role="menuitem" '
            + 'data-cmd="' + it.cmd + '">'
            +   icon(ICONS[it.icon] || "")
            +   '<span class="ad-menu-l">' + it.label + '</span>'
            + '</button>';
    });
    menu.innerHTML = html;

    Array.prototype.forEach.call(menu.querySelectorAll(".ad-menu-item"), function (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var cmd = btn.getAttribute("data-cmd");
        // "Move to…" swaps the menu for an inline deck picker (same
        // popover, no dialog). Everything else closes the menu first.
        if (cmd === "move") { openMovePicker(did); return; }
        close();
        if (cmd === "change-icon") {
          try {
            if (typeof pycmd === "function") {
              pycmd("onigiri_ctx_change_icon:" + did);
            }
          } catch (_) {}
          return;
        }
        // Rename happens inline on the home-page row when possible.
        // Falls back to the native dialog (handled by Python) if the
        // row isn't visible — e.g., we're on the overview header.
        if (cmd === "rename" && startInlineRename(did)) return;
        send("deck:" + cmd + ":" + did);
      });
    });

    return menu;
  }

  /* Inline rename — swap the deck-name anchor with a real <input> styled
     identically so the row visually doesn't change. Enter submits via
     pycmd; Escape or empty/unchanged blur restores the anchor. Exposed
     as `window.__adStartDeckRename` for keyboard / programmatic entry
     points (e.g., from a F2 shortcut or screenshot harness).

     We use a native <input>, not contenteditable: Qt WebEngine's editing
     commands on contenteditable have unpredictable interactions with
     Anki's top-level shortcuts (Backspace, etc.), whereas <input>'s
     keyboard handling is rock-solid because the browser owns it. */
  window.__adStartDeckRename = startInlineRename;
  function startInlineRename(did) {
    // Two entry points share this flow: the deck row in the multi-deck
    // table (`a.deck` inside `tr.deck`) and the single-deck hero header
    // (`h1.ba-deck-name`). The latter is tagged with `data-did` so we can
    // pick the right one. The hero header is checked first because in
    // single-deck mode Anki still renders the (hidden) `tr.deck` row in
    // the DOM, and we want to edit the visible name, not the hidden one.
    var anchor = document.querySelector('h1.ba-deck-name[data-did="' + did + '"]');
    if (anchor && anchor.offsetParent === null) anchor = null;
    if (!anchor) {
      // Shared deck-list rows (home page + congrats Keep-going list).
      anchor = document.querySelector('.ad-list-row[data-did="' + did + '"] .ad-list-name');
      if (anchor && anchor.offsetParent === null) anchor = null;
    }
    if (!anchor) {
      anchor = document.querySelector('tr.deck[id="' + did + '"] td.decktd > a.deck');
      if (anchor && anchor.offsetParent === null) anchor = null;
    }
    if (!anchor) return false;
    if (anchor.parentNode.querySelector(".ad-deck-rename")) return true; // editing

    var original = anchor.textContent;
    var input = document.createElement("input");
    input.type = "text";
    input.className = "ad-deck-rename";
    if (anchor.tagName && anchor.tagName.toLowerCase() === "h1") {
      input.classList.add("ad-deck-rename--hero");
    }
    if (anchor.classList.contains("filtered")) input.classList.add("filtered");
    input.spellcheck = false;
    input.setAttribute("aria-label", window.onigiriText("Rename deck"));
    input.value = original;
    // Auto-size to the current text so the field hugs the name like the
    // anchor did. `size` is in `ch`; bump by a couple so the caret has
    // breathing room and the field doesn't visibly grow as you type.
    function autosize() {
      input.size = Math.max((input.value || "").length + 2, 4);
    }
    autosize();
    input.addEventListener("input", autosize);

    anchor.style.display = "none";
    anchor.parentNode.insertBefore(input, anchor.nextSibling);

    // Prevent the row's open-deck click handler from firing while editing,
    // and keep the row's drag-to-move from hijacking a text selection.
    input.addEventListener("mousedown", function (e) { e.stopPropagation(); });
    input.addEventListener("click", function (e) { e.stopPropagation(); });
    input.addEventListener("dragstart", function (e) { e.preventDefault(); e.stopPropagation(); });

    var done = false;
    function cancel() {
      if (done) return;
      done = true;
      if (input.parentNode) input.parentNode.removeChild(input);
      anchor.style.display = "";
    }
    function commit() {
      if (done) return;
      var v = (input.value || "").trim();
      if (!v || v === original) { cancel(); return; }
      done = true;
      input.disabled = true;
      try {
        pycmd("ba:deck:rename-to:" + did + ":" + encodeURIComponent(v));
      } catch (e) {}
    }
    input.addEventListener("keydown", function (e) {
      // Stop propagation on every key so Anki's top-level QShortcuts
      // (`a`, `b`, `d`, `s`, `t`, `y`) don't fire while typing a name.
      e.stopPropagation();
      if (e.key === "Enter") {
        e.preventDefault();
        commit();
      } else if (e.key === "Escape") {
        e.preventDefault();
        cancel();
      }
    });
    input.addEventListener("keyup", function (e) { e.stopPropagation(); });
    input.addEventListener("keypress", function (e) { e.stopPropagation(); });
    input.addEventListener("blur", function () { commit(); });

    // Focus + select-all on the next frame so layout settles first.
    requestAnimationFrame(function () {
      input.focus();
      try { input.select(); } catch (_) {}
    });
    return true;
  }

  /* Move-to picker — replaces the menu body with a searchable list of
     every deck the chosen deck can move under, plus "Top level". Picking
     one dispatches `ba:deck:reparent:<did>:<target>` (Anki's own reparent
     op, the same thing its drag-and-drop does). Data comes from
     window.__baDeckTree — the flat, depth-tagged tree Python injects on
     the home page and the congrats page. */
  function deckCandidates(did) {
    var tree = window.__baDeckTree || [];
    var out = [];
    var self = null, selfIdx = -1, i;
    for (i = 0; i < tree.length; i++) {
      if (String(tree[i].did) === String(did)) { self = tree[i]; selfIdx = i; break; }
    }
    var blocked = {};
    blocked[String(did)] = 1;
    var selfDepth = self ? (self.depth || 0) : 0;
    if (selfIdx >= 0) {
      for (i = selfIdx + 1; i < tree.length; i++) {          // descendants
        if ((tree[i].depth || 0) <= selfDepth) break;
        blocked[String(tree[i].did)] = 1;
      }
      for (i = selfIdx - 1; i >= 0; i--) {                    // current parent
        if ((tree[i].depth || 0) < selfDepth) { blocked[String(tree[i].did)] = 1; break; }
      }
    }
    if (selfDepth > 0) out.push({ did: 0, path: window.onigiriText("Top level"), top: true });
    for (i = 0; i < tree.length; i++) {
      var d = tree[i];
      if (blocked[String(d.did)]) continue;
      if (d.filtered) continue;  // filtered decks can't hold sub-decks
      out.push({ did: d.did, path: d.path || d.name || "", depth: d.depth || 0 });
    }
    return { self: self, items: out };
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' })[c];
    });
  }

  function openMovePicker(did) {
    var menu = CURRENT;
    if (!menu) return;
    var data = deckCandidates(did);
    var name = data.self ? (data.self.name || data.self.path || "") : "";
    menu.classList.add("ad-menu--picker");
    menu.innerHTML = ''
      + '<div class="ad-menu-picker">'
      +   window.onigiriTemplate('<div class="ad-menu-picker-h">Move <b>') + escapeHTML(name) + window.onigiriTemplate('</b> to</div>')
      +   '<input class="ad-menu-picker-q" type="text" autocomplete="off" '
      +          window.onigiriTemplate('spellcheck="false" placeholder="Search decks…" aria-label="Search decks">')
      +   '<div class="ad-menu-picker-list" role="listbox"></div>'
      + '</div>';
    var input = menu.querySelector(".ad-menu-picker-q");
    var list = menu.querySelector(".ad-menu-picker-list");

    function paint(q) {
      q = (q || "").trim().toLowerCase();
      var html = "";
      var shown = 0;
      data.items.forEach(function (it) {
        if (q && it.path.toLowerCase().indexOf(q) === -1) return;
        shown++;
        html += '<button type="button" class="ad-menu-item ad-menu-pick'
              + (it.top ? ' ad-menu-pick--top' : '')
              + (shown === 1 ? ' is-active' : '')
              + '" role="option" data-target="' + it.did + '">'
              + '<span class="ad-menu-l">' + escapeHTML(it.path) + '</span>'
              + '</button>';
      });
      if (!shown) html = window.onigiriTemplate('<div class="ad-menu-picker-empty">No matching deck</div>');
      list.innerHTML = html;
    }
    function active() { return list.querySelector(".ad-menu-pick.is-active"); }
    function moveActive(dir) {
      var all = Array.prototype.slice.call(list.querySelectorAll(".ad-menu-pick"));
      if (!all.length) return;
      var idx = all.indexOf(active());
      var next = Math.max(0, Math.min(all.length - 1, idx + dir));
      all.forEach(function (b, i) { b.classList.toggle("is-active", i === next); });
      try { all[next].scrollIntoView({ block: "nearest" }); } catch (_) {}
    }
    function pick(btn) {
      if (!btn) return;
      var target = btn.getAttribute("data-target") || "0";
      close();
      send("deck:reparent:" + did + ":" + target);
    }

    paint("");
    input.addEventListener("input", function () { paint(input.value); });
    // Keep every key inside the picker: Anki's page-level shortcuts
    // (a/b/d/s/t/y) and the rename/cmdk handlers must not see them.
    ["keydown", "keyup", "keypress"].forEach(function (ev) {
      input.addEventListener(ev, function (e) { e.stopPropagation(); });
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); moveActive(+1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); moveActive(-1); }
      else if (e.key === "Enter") { e.preventDefault(); pick(active()); }
      else if (e.key === "Escape") { e.preventDefault(); close(); }
    });
    list.addEventListener("mousemove", function (e) {
      var b = e.target.closest && e.target.closest(".ad-menu-pick");
      if (!b || b.classList.contains("is-active")) return;
      Array.prototype.forEach.call(list.querySelectorAll(".ad-menu-pick"), function (x) {
        x.classList.toggle("is-active", x === b);
      });
    });
    list.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest(".ad-menu-pick");
      if (!b) return;
      e.preventDefault();
      e.stopPropagation();
      pick(b);
    });
    // Re-anchor: the picker is taller than the menu it replaced, so the
    // flip-up/flip-down decision has to be made again.
    if (menu._anchor) position(menu, menu._anchor);
    requestAnimationFrame(function () { try { input.focus(); } catch (_) {} });
  }

  function position(menu, anchor) {
    var r = anchor.getBoundingClientRect();
    // Render off-screen first to measure.
    menu.style.visibility = "hidden";
    document.body.appendChild(menu);
    var mw = menu.offsetWidth;
    var mh = menu.offsetHeight;
    var pad = 6;
    // Default: below the gear, right-aligned with it. Flip up if not enough room.
    var top = window.scrollY + r.bottom + pad;
    if (r.bottom + pad + mh > window.innerHeight) {
      top = window.scrollY + r.top - pad - mh;
    }
    var left = window.scrollX + r.right - mw;
    if (left < window.scrollX + 8) left = window.scrollX + 8;
    menu.style.top = top + "px";
    menu.style.left = left + "px";
    menu.style.visibility = "";
  }

  window.__adDeckOpts = function (did, evt) {
    if (evt) {
      evt.preventDefault();
      evt.stopPropagation();
    }
    // The shared deck-list (__adDeckList.render) delegates clicks on the
    // row container, so evt.currentTarget there is the whole list — too
    // wide to anchor a menu off, which puts the menu at the bottom of the
    // list instead of next to the clicked gear. Walk up from the real
    // click target to the gear button first; fall back to currentTarget
    // for the non-delegated callers (single-deck hero, Anki's native
    // gear anchor, the congrats title).
    var anchor = null;
    if (evt) {
      if (evt.target && evt.target.closest) {
        anchor = evt.target.closest('.ad-list-gear');
      }
      if (!anchor) anchor = evt.currentTarget;
    }
    // Toggle off if clicking the same gear that opened the menu.
    if (CURRENT && CURRENT._anchor === anchor) {
      close();
      return;
    }
    close();
    if (!anchor) return;
    var menu = build(did);
    menu._anchor = anchor;
    position(menu, anchor);
    // Stagger the open class one frame so the transition runs.
    requestAnimationFrame(function () { menu.classList.add("ad-menu--open"); });
    CURRENT = menu;
    document.addEventListener("mousedown", outsideClick, true);
    document.addEventListener("keydown", escClose, true);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", close, true);
    // Focus the first item for keyboard access.
    var first = menu.querySelector(".ad-menu-item");
    if (first) first.focus();
  };

  /* Wire the native gear `<a>` (Anki renders one per deck row in the home
     table) so it opens our custom menu instead of Anki's QMenu. Without
     this, multi-deck home pages would still get the legacy modal-based
     rename and the rest of the native deck-options dialog. */
  function wireGears() {
    var gears = document.querySelectorAll("tr.deck img.gears");
    for (var i = 0; i < gears.length; i++) {
      var a = gears[i].closest("a");
      if (!a || a.__adGearWired) continue;
      var row = a.closest("tr.deck");
      if (!row || !row.id) continue;
      a.__adGearWired = true;
      // Drop Anki's inline `onclick='return pycmd("opts:<did>")'` so the
      // QMenu never opens, then own the click ourselves.
      a.removeAttribute("onclick");
      (function (anchor, did) {
        anchor.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          // currentTarget is the anchor so position() can anchor the menu
          // off the actual gear cell.
          window.__adDeckOpts(did, e);
        });
      })(a, row.id);
    }
  }

  function initGears() {
    wireGears();
    if (window.MutationObserver) {
      // Anki re-renders the deck list after operations (study, rename,
      // collapse). Coalesce mutations into one rAF tick before re-wiring.
      var pending = 0;
      var mo = new MutationObserver(function () {
        if (pending) return;
        pending = requestAnimationFrame(function () {
          pending = 0;
          wireGears();
        });
      });
      mo.observe(document.body, { childList: true, subtree: true });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initGears);
  } else {
    initGears();
  }
})();
