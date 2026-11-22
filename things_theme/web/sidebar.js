/* Anki Design — left sidebar (info + nav).
   Prepends a <aside class="ba-side"> to <body> on every themed page. The
   sidebar shows: identity + today's standing (date, streak, due/new/learning)
   + primary nav + quick actions + sync/settings. Python pushes live data via
   window.__baSetStanding({...}) after each render. */
(function () {
  "use strict";
  if (window.__ankiDesignSide) return;
  window.__ankiDesignSide = true;

  function send(cmd) {
    try { if (typeof pycmd === "function") pycmd("ba:" + cmd); } catch (e) {}
  }

  // ---- icons (inline SVG, stroke uses currentColor) -------------------- //
  // Lightweight stroke set tuned to feel editorial, not iconographic.
  // Each icon is structured so the parts most worth animating on hover are
  // wrapped in groups with stable class hooks (see sidebar.css).
  var ICONS = {
    decks:
      '<g class="ba-i-decks-top"><path d="M3 7l9-4 9 4-9 4-9-4z"/></g>' +
      '<g class="ba-i-decks-mid"><path d="M3 12l9 4 9-4"/></g>' +
      '<g class="ba-i-decks-bot"><path d="M3 17l9 4 9-4"/></g>',
    add:
      '<g class="ba-i-plus">' +
        '<path d="M12 5v14"/><path d="M5 12h14"/>' +
      '</g>',
    browse:
      '<g class="ba-i-search-lens">' +
        '<circle cx="11" cy="11" r="6.5"/>' +
      '</g>' +
      '<g class="ba-i-search-handle">' +
        '<path d="M20 20l-4.3-4.3"/>' +
      '</g>',
    stats:
      '<g class="ba-i-bars">' +
        '<path class="ba-i-bar ba-i-bar-1" d="M4 19V9"/>' +
        '<path class="ba-i-bar ba-i-bar-2" d="M10 19V5"/>' +
        '<path class="ba-i-bar ba-i-bar-3" d="M16 19v-8"/>' +
      '</g>' +
      '<path d="M22 19h-22"/>',
    create:
      '<g class="ba-i-plus">' +
        '<path d="M12 5v14"/><path d="M5 12h14"/>' +
      '</g>',
    submit:
      '<g class="ba-i-submit">' +
        '<path d="M5 12h14"/><path d="M13 6l6 6-6 6"/>' +
      '</g>',
    "import":
      '<g class="ba-i-import">' +
        '<path class="ba-i-import-stem"  d="M12 4v12"/>' +
        '<path class="ba-i-import-head"  d="M6 10l6-6 6 6"/>' +
      '</g>' +
      '<path d="M4 20h16"/>',
    sync:
      '<g class="ba-i-sync">' +
        '<path d="M21 12a9 9 0 1 1-3-6.7"/>' +
        '<path d="M21 4v5h-5"/>' +
      '</g>',
    settings:
      '<g class="ba-i-gear">' +
        '<circle cx="12" cy="12" r="3"/>' +
        '<path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3h0a1.6 1.6 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.6 1.6 0 0 0 1 1.5h0a1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8v0a1.6 1.6 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>' +
      '</g>',
  };
  // Kome deliberately uses the fixed Font Awesome Solid set. Unlike
  // Classic's settings-backed Lucide icons, these are part of its visual
  // language and are not individually customizable.
  var FONT_AWESOME_ICONS = {
    decks: "layer-group",
    add: "circle-plus",
    browse: "magnifying-glass",
    stats: "chart-column",
    create: "folder-plus",
    "import": "file-import",
    ready_inbox: "inbox",
    ready_warm_up: "sun",
    ready_today: "calendar-check",
    ready_cool_down: "moon"
  };
  function iconSVG(name, extraClass) {
    var fontAwesome = FONT_AWESOME_ICONS[name];
    if (fontAwesome) {
      var assetBase = (window.__baOpts && window.__baOpts.assetBase)
        || "/_addons/1011095603/things_theme/web/icons";
      var iconCls = "ba-side-icon ba-side-icon--fa" + (extraClass ? " " + extraClass : "");
      return '<i class="' + iconCls + '" style="--ba-side-icon-url:url(\''
        + assetBase + '/fa-' + fontAwesome + '.svg\')" aria-hidden="true"></i>';
    }
    var body = ICONS[name];
    if (!body) return "";
    var cls = "ba-side-icon" + (extraClass ? " " + extraClass : "");
    return '<svg class="' + cls + '" viewBox="0 0 24 24" width="14" height="14" '
         + 'fill="none" stroke="currentColor" stroke-width="1.7" '
         + 'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
         + body + '</svg>';
  }

  // ---- nav rows -------------------------------------------------------- //
  // Sync row needs an extra <svg> for the success-check overlay that fades
  // in over the cloud icon when a sync completes with real changes. Both
  // glyphs live in a positioned wrapper so we can cross-fade them without
  // shifting the row layout.
  var SYNC_CHECK_SVG =
    '<svg class="ba-sync-check" viewBox="0 0 24 24" width="14" height="14" ' +
      'fill="none" stroke="currentColor" stroke-width="2.2" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M5 12.5l4.5 4.5L19 7"/>' +
    '</svg>';

  function makeRow(it) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "ba-side-item";
    b.setAttribute("data-cmd", it.cmd);
    if (it.active) b.setAttribute("data-active", "true");
    if (it.cls) b.classList.add(it.cls);
    var iconName = it.icon || it.cmd;
    var iconBlock = (it.cmd === "sync")
      ? '<span class="ba-sync-iconwrap">' + iconSVG(iconName) + SYNC_CHECK_SVG + '</span>'
      : iconSVG(iconName);
    // .ba-side-l-text wraps the label so the sync row can rewrite it in
    // place ("Sync" → "Syncing…" → "Synced") without touching siblings.
    var inner = iconBlock
              + '<span class="ba-side-l"><span class="ba-side-l-text">'
              + it.label + '</span></span>';
    if (it.dot) inner += '<span class="ba-side-dot"></span>';
    if (it.key) inner += '<span class="ba-side-key">' + it.key + "</span>";
    b.innerHTML = inner;
    b.addEventListener("click", function (e) { e.preventDefault(); send(it.cmd); });
    return b;
  }

  // Morphing "New deck" row. Idle: looks like any sidebar action row. Active:
  // the label swaps for an inline input — Enter creates, Esc/blur cancels.
  // The icon column anchors the transition so nothing jumps. We hold the open
  // state on the wrapper element and toggle a single `data-state` so all
  // transitions are CSS-driven.
  function makeNewDeckRow() {
    var row = document.createElement("div");
    row.className = "ba-side-item ba-side-act ba-side-newdeck";
    row.setAttribute("data-cmd", "create");
    row.setAttribute("data-state", "idle");
    // The icon slot holds two SVGs stacked in the same 14×14 box: the
    // idle plus and the active submit (right arrow). They cross-fade as
    // the state changes — the shared horizontal stroke of both glyphs
    // makes the swap read as a morph rather than a flicker.
    //
    // Label + input share their own flex slot so they overlap in place;
    // CSS fades one in as the other fades out — no layout shift.
    row.innerHTML =
      '<span class="ba-side-newdeck-icons" aria-hidden="true">' +
        iconSVG("create", "ba-side-newdeck-icon--plus") +
        iconSVG("submit", "ba-side-newdeck-icon--submit") +
      '</span>' +
      '<span class="ba-side-newdeck-swap">' +
        window.onigiriTemplate('<span class="ba-side-newdeck-label">New deck</span>') +
        '<input type="text" class="ba-side-newdeck-input" autocomplete="off" ' +
          window.onigiriTemplate('spellcheck="false" placeholder="Name a deck…" tabindex="-1" />') +
      '</span>';

    var input = row.querySelector(".ba-side-newdeck-input");
    var iconBtn = row.querySelector(".ba-side-newdeck-icons");

    function open() {
      if (row.getAttribute("data-state") === "active") { input.focus(); return; }
      row.setAttribute("data-state", "active");
      input.removeAttribute("tabindex");
      // Defer focus one frame so the layout swap finishes before the caret
      // is placed — otherwise the input can scroll its parent.
      requestAnimationFrame(function () { input.focus(); });
    }
    function close() {
      row.setAttribute("data-state", "idle");
      input.setAttribute("tabindex", "-1");
      input.value = "";
    }
    function submit() {
      var name = input.value.trim();
      if (!name) { close(); return; }
      send("create:" + name);
      // The Python handler calls mw.reset(); the deck list will refresh.
      close();
    }

    // Click on the row (outside the input/icon) opens it.
    row.addEventListener("click", function (e) {
      if (row.getAttribute("data-state") === "active") return;
      e.preventDefault();
      open();
    });
    // Keyboard activation when the row itself is focused (idle state).
    row.tabIndex = 0;
    row.addEventListener("keydown", function (e) {
      if (row.getAttribute("data-state") === "idle" &&
          (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        open();
      }
    });

    input.addEventListener("click", function (e) { e.stopPropagation(); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); submit(); }
      else if (e.key === "Escape") { e.preventDefault(); close(); }
    });
    input.addEventListener("blur", function () {
      // Defer so other in-flight handlers (e.g. our own submit) run first.
      setTimeout(function () {
        if (document.activeElement !== input) close();
      }, 80);
    });

    // In active state the icon doubles as a submit affordance — clicking
    // it is equivalent to pressing Enter from the input. mousedown's
    // preventDefault keeps the input focused so the submit reads its
    // current value (and avoids the blur-then-close race).
    iconBtn.addEventListener("mousedown", function (e) {
      if (row.getAttribute("data-state") === "active") e.preventDefault();
    });
    iconBtn.addEventListener("click", function (e) {
      if (row.getAttribute("data-state") !== "active") return; // idle: let it bubble
      e.preventDefault();
      e.stopPropagation();
      submit();
    });

    // Public hook used by the Python handler when "ba:create" comes from a
    // keyboard shortcut or external trigger.
    window.__baFocusNewDeck = open;

    return row;
  }

  // ---- active-cards donut ----------------------------------------------- //
  var DONUT_STATES = [
    { key: "new",        label: window.onigiriText("New"),        cls: "new" },
    { key: "learning",   label: window.onigiriText("Learning"),   cls: "learning" },
    { key: "relearning", label: window.onigiriText("Relearning"), cls: "relearning" },
    { key: "young",      label: window.onigiriText("Young"),      cls: "young" },
    { key: "mature",     label: window.onigiriText("Mature"),     cls: "mature" },
  ];
  function openDonutState(key) {
    send("donut-open:" + key);
  }

  function buildDonut() {
    var wrap = document.createElement("div");
    wrap.className = "ba-side-donut-block";
    var segments = '';
    for (var j = 0; j < DONUT_STATES.length; j++) {
      segments += '<circle class="ba-side-donut-segment ba-side-donut-segment--'
        + DONUT_STATES[j].cls + '" data-donut-segment="'
        + DONUT_STATES[j].key + '" cx="50" cy="50" r="40" pathLength="100" />';
    }
    wrap.innerHTML =
      '<div class="ba-side-section-title">' +
        window.onigiriTemplate('<span>Active cards</span>') +
      '</div>' +
      '<div class="ba-side-donut-row">' +
        '<div class="ba-side-donut-ring" data-donut-ring>' +
          '<svg class="ba-side-donut-svg" viewBox="0 0 100 100" aria-hidden="true">' +
            '<circle class="ba-side-donut-track" cx="50" cy="50" r="40" pathLength="100" />' +
            segments +
          '</svg>' +
          '<div class="ba-side-donut-core">' +
            '<strong data-donut-total>—</strong>' +
          '</div>' +
        '</div>' +
        '<ul class="ba-side-donut-legend"></ul>' +
      '</div>';
    var legend = wrap.querySelector(".ba-side-donut-legend");
    for (var i = 0; i < DONUT_STATES.length; i++) {
      var s = DONUT_STATES[i];
      var li = document.createElement("li");
      li.className = "ba-side-donut-item ba-side-donut-item--" + s.cls;
      li.setAttribute("role", "button");
      li.setAttribute("tabindex", "0");
      li.innerHTML =
        '<span class="ba-side-donut-dot"></span>' +
        '<span class="ba-side-donut-l">' + s.label + '</span>' +
        '<span class="ba-side-donut-v" data-donut-v="' + s.key + '">—</span>';
      (function (key) {
        li.addEventListener("click", function () { openDonutState(key); });
        li.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openDonutState(key);
          }
        });
      })(s.key);
      legend.appendChild(li);
    }
    return wrap;
  }

  function renderDonut(states) {
    var scope = document.querySelector(".ba-side");
    if (!states || !scope) return;
    var i, total = 0;
    for (i = 0; i < DONUT_STATES.length; i++) total += (states[DONUT_STATES[i].key] || 0);

    var totalEl = scope.querySelector("[data-donut-total]");
    if (totalEl) {
      var totalText = fmtNum(total);
      totalEl.textContent = totalText;
      totalEl.classList.toggle("is-compact", totalText.length >= 5);
      totalEl.classList.toggle("is-tiny", totalText.length >= 7);
    }

    var ring = scope.querySelector("[data-donut-ring]");
    if (ring) {
      var cursor = 0;
      for (i = 0; i < DONUT_STATES.length; i++) {
        var amount = states[DONUT_STATES[i].key] || 0;
        var percent = total ? (amount / total) * 100 : 0;
        var segment = ring.querySelector(
          '[data-donut-segment="' + DONUT_STATES[i].key + '"]'
        );
        if (segment) {
          if (percent > 0) {
            // Large slices get a true arc with rounded, separated ends.
            // Tiny slices become a round dot centered in their allocation,
            // matching the compact reference without disappearing entirely.
            var gap = Math.min(5, percent * 0.72);
            var length = percent <= 5.5 ? 0.01 : Math.max(0.01, percent - gap);
            var start = percent <= 5.5
              ? cursor + percent / 2
              : cursor + gap / 2;
            segment.style.strokeDasharray = length.toFixed(2) + ' '
              + (100 - length).toFixed(2);
            segment.style.strokeDashoffset = (-start).toFixed(2);
            segment.style.opacity = '1';
          } else {
            segment.style.strokeDasharray = '0 100';
            segment.style.opacity = '0';
          }
        }
        cursor += percent;
      }
    }

    var vEls = scope.querySelectorAll("[data-donut-v]");
    for (i = 0; i < vEls.length; i++) {
      var k = vEls[i].getAttribute("data-donut-v");
      vEls[i].textContent = fmtNum(states[k] || 0);
    }
    var legendItems = scope.querySelectorAll(".ba-side-donut-item");
    for (i = 0; i < legendItems.length; i++) {
      var cls = DONUT_STATES[i] ? DONUT_STATES[i].label : "";
      legendItems[i].title = cls + ": " + fmtNum(states[DONUT_STATES[i].key] || 0) + " cards — click to browse";
    }
  }

  // ---- recent progress ------------------------------------------------- //
  function buildProgress() {
    var wrap = document.createElement("div");
    wrap.className = "ba-side-progress-block";
    var bars = "";
    for (var i = 0; i < 14; i++) {
      bars += '<span class="ba-side-progress-col"><i data-progress-bar="' + i + '"></i></span>';
    }
    wrap.innerHTML =
      '<div class="ba-side-section-title">' +
        window.onigiriTemplate('<span>Progress</span>') +
        window.onigiriTemplate('<span class="ba-side-progress-meta"><b data-x="streak">—</b>d streak</span>') +
      '</div>' +
      '<div class="ba-side-progress-chart">' + bars + '</div>' +
      window.onigiriTemplate('<div class="ba-side-progress-days"><span>14 days ago</span><span>Today</span></div>');
    return wrap;
  }

  function renderProgress(values) {
    if (!values || !values.length) return;
    var peak = Math.max.apply(Math, values.concat([1]));
    var bars = document.querySelectorAll("[data-progress-bar]");
    for (var i = 0; i < bars.length; i++) {
      var count = Number(values[i] || 0);
      var height = count ? Math.max(8, (count / peak) * 100) : 3;
      bars[i].style.height = height + "%";
      bars[i].classList.toggle("is-empty", count === 0);
      bars[i].title = fmtNum(count) + " cards reviewed";
    }
  }

  // ---- tasks checklist ---------------------------------------------------- //
  function taskEncode(text) {
    try { return encodeURIComponent(text); } catch (e) { return text; }
  }

  function buildTasks() {
    var wrap = document.createElement("div");
    wrap.className = "ba-side-tasks-block";
    wrap.innerHTML =
      '<div class="ba-side-section-title">' +
        window.onigiriTemplate('<span>Tasks</span>') +
        window.onigiriTemplate('<button type="button" class="ba-side-tasks-add-btn" aria-label="Add task">') +
          '<svg class="ba-side-tasks-add-icon" viewBox="0 0 24 24" fill="none" ' +
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
            'stroke-linejoin="round" aria-hidden="true">' +
            '<path d="M5 12h14"/><path d="M12 5v14"/>' +
          '</svg>' +
        '</button>' +
      '</div>' +
      '<form class="ba-side-tasks-form" style="display:none;">' +
        window.onigiriTemplate('<input type="text" class="ba-side-tasks-input" placeholder="New task…" maxlength="200" />') +
      '</form>' +
      '<ul class="ba-side-tasks-list"></ul>';

    var addBtn = wrap.querySelector(".ba-side-tasks-add-btn");
    var form = wrap.querySelector(".ba-side-tasks-form");
    var input = wrap.querySelector(".ba-side-tasks-input");

    addBtn.addEventListener("click", function () {
      var open = form.style.display !== "none";
      form.style.display = open ? "none" : "block";
      if (!open) input.focus();
    });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var v = input.value.trim();
      if (!v) return;
      send("task-add:" + taskEncode(v));
      input.value = "";
      form.style.display = "none";
    });

    renderTasks(window.__baTasksData || []);
    return wrap;
  }

  function buildReadyToGo() {
    var wrap = document.createElement("div");
    wrap.className = "ba-side-ready-block";
    wrap.innerHTML = window.onigiriTemplate('<div class="ba-side-section-title"><span>Ready to go</span></div>');
    var actions = document.createElement("div");
    actions.className = "ba-side-ready-actions";
    [
      { cmd: "ready:inbox", label: window.onigiriText("Inbox"), icon: "ready_inbox" },
      { cmd: "ready:warm_up", label: window.onigiriText("Warm up"), icon: "ready_warm_up" },
      { cmd: "ready:today", label: window.onigiriText("Today"), icon: "ready_today" },
      { cmd: "ready:cool_down", label: window.onigiriText("Cool-Down"), icon: "ready_cool_down" }
    ].forEach(function (it) { actions.appendChild(makeRow(it)); });
    wrap.appendChild(actions);
    return wrap;
  }

  function renderTasks(tasks) {
    var list = document.querySelector(".ba-side-tasks-list");
    if (!list) return;
    list.innerHTML = "";
    if (!tasks || !tasks.length) {
      var empty = document.createElement("li");
      empty.className = "ba-side-tasks-empty";
      empty.textContent = window.onigiriText("No tasks yet.");
      list.appendChild(empty);
      return;
    }
    for (var i = 0; i < tasks.length; i++) {
      (function (t) {
        var li = document.createElement("li");
        li.className = "ba-side-task" + (t.done ? " ba-side-task--done" : "");

        var box = document.createElement("button");
        box.type = "button";
        box.className = "ba-side-task-box";
        box.setAttribute("aria-label", t.done ? window.onigiriText("Mark not done") : window.onigiriText("Mark done"));
        box.setAttribute("aria-pressed", t.done ? "true" : "false");
        box.addEventListener("click", function () { send("task-toggle:" + t.id); });

        var label = document.createElement("span");
        label.className = "ba-side-task-text";
        label.textContent = t.text;

        var del = document.createElement("button");
        del.type = "button";
        del.className = "ba-side-task-del";
        del.setAttribute("aria-label", window.onigiriText("Remove task"));
        del.innerHTML =
          '<svg class="ba-side-task-del-icon" viewBox="0 0 24 24" fill="none" ' +
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
            'stroke-linejoin="round" aria-hidden="true">' +
            '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>' +
          '</svg>';
        del.addEventListener("click", function () { send("task-remove:" + t.id); });

        li.appendChild(box);
        li.appendChild(label);
        li.appendChild(del);
        list.appendChild(li);
      })(tasks[i]);
    }
  }

  function build() {
    var aside = document.createElement("aside");
    aside.className = "ba-side";
    var sidebarOpts = (window.__baOpts && window.__baOpts.sidebar) || {};
    var heroStat = sidebarOpts.heroStat;
    if (heroStat !== "new" && heroStat !== "learn") heroStat = "due";
    var HERO_LABELS = { due: window.onigiriText("Due Today"), new: window.onigiriText("New Cards"), learn: window.onigiriText("In Learning") };

    aside.innerHTML = ''
      // Hero — a single configurable stat (Settings → sidebar_hero_stat).
      + '<div class="ba-side-hero">'
      +   '<div class="ba-side-hero-label">' + HERO_LABELS[heroStat] + '</div>'
      +   '<div class="ba-side-hero-num">'
      +     '<span class="ba-side-hero-n" data-x="' + heroStat + '">—</span>'
      +     window.onigiriTemplate('<span class="ba-side-hero-unit">cards</span>')
      +   '</div>'
      + '</div>';

    // Settings → Appearance → sidebar hero off: drop the block entirely.
    if (sidebarOpts.hero === false) {
      var heroEl = aside.querySelector(".ba-side-hero");
      if (heroEl) heroEl.remove();
    }

    // Command-K palette launcher. Rendered as a button styled like a
    // search input so it reads as "click here to search anything", and
    // hints the ⌘K shortcut on the right. Actual palette UI is in
    // web/cmdk.js (injected on every themed page). Sending the pycmd
    // routes through Python so any open embed (AddCards/Browser/Stats/
    // Settings) is torn down before the palette opens.
    var cmdk = document.createElement("button");
    cmdk.type = "button";
    cmdk.className = "ba-side-cmdk";
    cmdk.setAttribute("aria-label", window.onigiriText("Open command palette"));
    // Mac users see ⌘K; everyone else sees Ctrl+K (both bindings fire).
    var modGlyph = /Mac|iPod|iPhone|iPad/i.test(navigator.platform || "")
      ? '<span class="ba-side-cmdk-key">⌘</span>'
      : '<span class="ba-side-cmdk-key ba-side-cmdk-key--w">Ctrl</span>';
    cmdk.innerHTML =
      '<svg class="ba-side-cmdk-ico" viewBox="0 0 24 24" width="14" height="14" ' +
        'fill="none" stroke="currentColor" stroke-width="1.7" ' +
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.3-4.3"/>' +
      '</svg>' +
      window.onigiriTemplate('<span class="ba-side-cmdk-l">Search anything…</span>') +
      '<span class="ba-side-cmdk-kbd">' +
        modGlyph +
        '<span class="ba-side-cmdk-key">K</span>' +
      '</span>';
    cmdk.addEventListener("click", function (e) {
      e.preventDefault();
      // Always route through Python so it can pick the right host: mw.web
      // when there's no embed, or the dedicated cmdk_overlay when an embed
      // (Browse/Add/Stats/Settings) is up. Opening __baCmdkOpen directly in
      // mw.web would render the palette behind the embed.
      send("cmdk-open");
    });
    // Settings → Windows → "Command palette" off: no pill, no hotkey hint.
    if (!(window.__baOpts && window.__baOpts.cmdk === false)) {
      aside.appendChild(cmdk);
    }

    // The six primary actions stay compact in a two-column grid.
    var actions = document.createElement("nav");
    actions.className = "ba-side-actions-grid";
    [
      { cmd: "decks",  label: window.onigiriText("Decks"),  key: "D", active: true },
      { cmd: "add",    label: window.onigiriText("Add"),    key: "A" },
      { cmd: "browse", label: window.onigiriText("Browse"), key: "B" },
      { cmd: "stats",  label: window.onigiriText("Stats"),  key: "T" },
    ].forEach(function (it) { actions.appendChild(makeRow(it)); });
    actions.appendChild(makeNewDeckRow());
    actions.appendChild(makeRow({ cmd: "import", label: window.onigiriText("Import file"), cls: "ba-side-act" }));
    aside.appendChild(actions);

    // Personal planning and study charts follow the navigation, mirroring
    // Things' information-dense but calm sidebar hierarchy.
    aside.appendChild(buildReadyToGo());
    if (sidebarOpts.tasks !== false) aside.appendChild(buildTasks());
    if (sidebarOpts.donut !== false) aside.appendChild(buildDonut());
    if (sidebarOpts.progress !== false) aside.appendChild(buildProgress());

    // Foot — sync + settings.
    var foot = document.createElement("div");
    foot.className = "ba-side-foot";
    [
      { cmd: "sync",     label: window.onigiriText("Sync"),     key: window.onigiriText("Y"), dot: true },
      { cmd: "settings", label: window.onigiriText("Settings"), key: ",", cls: "ba-side-settings" },
    ].forEach(function (it) { foot.appendChild(makeRow(it)); });
    aside.appendChild(foot);

    return aside;
  }

  // ---- state cache (so Python can push before the DOM is built) ------- //
  var pending = { standing: null, active: null, sync: null, tasks: null };

  function applyStanding(d) {
    if (!d) return;
    var keys = ["streak", "due", "new", "learn", "today", "todayMin", "total", "dueTotal"];
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i];
      var els = document.querySelectorAll('[data-x="' + k + '"]');
      if (!els.length) continue;
      var v = d[k];
      var txt = (typeof v === "number") ? fmtNum(v) : (v == null ? "—" : String(v));
      for (var j = 0; j < els.length; j++) els[j].textContent = txt;
    }
    // 7-day mini-grid (oldest → today). Each entry true/false.
    if (d.last7 && d.last7.length === 7) {
      var dots = document.querySelectorAll(".ba-side-7d-dot");
      for (var k2 = 0; k2 < 7; k2++) {
        if (!dots[k2]) continue;
        dots[k2].classList.toggle("ba-on", !!d.last7[k2]);
      }
    }
    // In single-deck mode the hero owns Due/New/Learning, so hide the
    // sidebar copy to avoid doubling the same numbers.
    var aside = document.querySelector(".ba-side");
    if (aside) aside.classList.toggle("ba-side--single", !!d.singleDeck);

    if (d.states) renderDonut(d.states);
    if (d.last14) renderProgress(d.last14);
  }
  function applyActive(cmd) {
    var els = document.querySelectorAll(".ba-side-item");
    for (var i = 0; i < els.length; i++) {
      if (els[i].getAttribute("data-cmd") === cmd) els[i].setAttribute("data-active", "true");
      else els[i].removeAttribute("data-active");
    }
  }
  // The sync row drives a small state machine:
  //
  //   idle  ──click──▶  active  ──result(ok)──▶  reveal-ok   ──▶  idle
  //                          └──result(noop)──▶ reveal-noop ──▶  idle
  //                          └──result(error)─▶ reveal-err  ──▶  idle
  //
  // applySync() owns the standing class state (pending/full/active) and
  // the resting label. applySyncResult() owns the brief "Synced" reveal
  // — and during that reveal it locks the label so applySync() can't
  // overwrite it from a parallel `gui_hooks.sync_did_finish` refresh.
  var syncResultTimer = null;

  function applySync(state) {
    var el = document.querySelector('.ba-side-item[data-cmd="sync"]');
    if (!el) return;
    var revealing = el.hasAttribute("data-sync-result");
    var text = el.querySelector(".ba-side-l-text");
    el.classList.remove("ba-sync-pending", "ba-sync-full");
    // Keep the spin going while the reveal plays — it cross-fades into
    // the check, no abrupt stop.
    if (!revealing) el.classList.remove("ba-sync-active");
    if (state === "pending") el.classList.add("ba-sync-pending");
    else if (state === "full") el.classList.add("ba-sync-full");
    else if (state === "active") {
      el.classList.add("ba-sync-active");
      if (text && !revealing) text.textContent = window.onigiriText("Syncing…");
    } else if (!revealing && text) {
      text.textContent = window.onigiriText("Sync");
    }
  }

  function applySyncProgress(d) {
    // Anki's `progress.normal_sync.stage` is a localized full sentence
    // ("Checking…", "Uploading notes…") that would jitter the row width
    // if shown directly. We stash it on a data attr for inspection /
    // future use; the visible feedback is the spinning icon + "Syncing…"
    // label, which is enough to convey "work is in flight."
    if (!d) return;
    var el = document.querySelector('.ba-side-item[data-cmd="sync"]');
    if (!el) return;
    if (d.stage) el.setAttribute("data-sync-stage", d.stage);
    if (d.added) el.setAttribute("data-sync-added", d.added);
    if (d.removed) el.setAttribute("data-sync-removed", d.removed);
  }

  function applySyncResult(kind) {
    var el = document.querySelector('.ba-side-item[data-cmd="sync"]');
    if (!el) return;
    var text = el.querySelector(".ba-side-l-text");
    el.setAttribute("data-sync-result", kind);
    // Different reveals for "real changes happened" vs "heartbeat / no
    // changes" vs "error" — see styles below for the actual motion.
    if (kind === "ok" && text) text.textContent = window.onigiriText("Synced");
    else if (kind === "error" && text) text.textContent = window.onigiriText("Sync failed");
    // "noop" — keep the label as it was (usually "Syncing…"); we let it
    // fade back to "Sync" with the icon's settle bounce.

    var hold = (kind === "noop") ? 800 : 1800;
    clearTimeout(syncResultTimer);
    syncResultTimer = setTimeout(function () {
      el.removeAttribute("data-sync-result");
      el.classList.remove("ba-sync-active");
      el.removeAttribute("data-sync-stage");
      el.removeAttribute("data-sync-added");
      el.removeAttribute("data-sync-removed");
      var t = el.querySelector(".ba-side-l-text");
      if (t) t.textContent = window.onigiriText("Sync");
    }, hold);
  }

  function inject() {
    if (document.querySelector(".ba-side")) return;
    var aside = build();
    document.body.insertBefore(aside, document.body.firstChild || null);
    document.body.classList.add("ba-with-side");
    if (pending.standing) applyStanding(pending.standing);
    if (pending.active)   applyActive(pending.active);
    if (pending.sync)     applySync(pending.sync);
    if (pending.tasks)    renderTasks(pending.tasks);
  }

  // ---- public hooks ---------------------------------------------------- //
  function fmtNum(n) {
    if (n === null || n === undefined) return "—";
    return (typeof n === "number") ? n.toLocaleString() : String(n);
  }
  window.__baSetStanding = function (d) {
    pending.standing = d || pending.standing;
    applyStanding(d);
  };
  window.__baSetActive = function (cmd) {
    pending.active = cmd;
    applyActive(cmd);
  };
  window.__baSetSync = function (state) {
    pending.sync = state;
    applySync(state);
  };
  window.__baSetSyncProgress = function (d) {
    applySyncProgress(d);
  };
  window.__baSetSyncResult = function (kind) {
    applySyncResult(kind);
  };
  window.__baSetTasks = function (tasks) {
    pending.tasks = tasks || pending.tasks;
    renderTasks(tasks);
  };

  // Bootstrap from the <head>-embedded standing data (set by the addon
  // before any body script runs) — eliminates the eval-vs-IIFE race.
  if (window.__baStandingData) pending.standing = window.__baStandingData;
  if (window.__baTasksData) pending.tasks = window.__baTasksData;

  if (document.readyState !== "loading") inject();
  else document.addEventListener("DOMContentLoaded", inject);

  var moScheduled = false;
  try {
    new MutationObserver(function () {
      if (moScheduled) return;
      moScheduled = true;
      requestAnimationFrame(function () {
        moScheduled = false;
        if (!document.querySelector(".ba-side")) inject();
      });
    }).observe(document.documentElement, { childList: true, subtree: true });
  } catch (e) {}
})();
