(function () {
  "use strict";

  var C = BENTO_SETTINGS_CONTEXT || {};
  var pages = C.pages || [];
  var current = C.initialPage || (pages[0] && pages[0].id);
  var values = {};
  var timer = 0;
  var inFlight = false;
  var pending = {};
  var activePicker = null;
  var previewRevision = 0;
  var cancelPreviewSwap = null;

  /* Official Lucide 24px SVG path data. The WebUI stays self-contained inside
     Anki while preserving Lucide's exact geometry and stroke attributes. */
  var LUCIDE = {
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "bluetooth": '<path d="m7 7 10 10-5 5V2l5 5L7 17"/>',
    "bookmark-plus": '<path d="M12 7v6"/><path d="M15 10H9"/><path d="M17 3a2 2 0 0 1 2 2v15a1 1 0 0 1-1.496.868l-4.512-2.578a2 2 0 0 0-1.984 0l-4.512 2.578A1 1 0 0 1 5 20V5a2 2 0 0 1 2-2z"/>',
    "check": '<path d="m20 6-11 11-5-5"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "circle-alert": '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
    "circle-check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "circle-help": '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 1 1 5.8 1c0 2-3 2-3 4"/><path d="M12 18h.01"/>',
    "clock-3": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6h4"/>',
    "cloud-sun": '<path d="M12 2v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="M20 12h2"/><path d="m19.07 4.93-1.41 1.41"/><path d="M15.947 12.65a4 4 0 0 0-5.925-4.128"/><path d="M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6Z"/>',
    "folder-open": '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
    "headphones": '<path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 18 0v7a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3"/>',
    "heart": '<path d="M2 9.5a5.5 5.5 0 0 1 9.591-3.676.56.56 0 0 0 .818 0A5.49 5.49 0 0 1 22 9.5c0 2.29-1.5 4-3 5.5l-5.492 5.313a2 2 0 0 1-3 .019L5 15c-1.5-1.5-3-3.2-3-5.5"/>',
    "history": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l4 2"/>',
    "image": '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
    "layout-dashboard": '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
    "leaf": '<path d="M11 20a10 10 0 0 0 10-10 25.9 25.9 0 0 0-1.04-7.281 1 1 0 0 0-1.755-.325C15.833 5.5 13 5.5 9.8 6.1A7 7 0 0 0 11 20"/><path d="M2 21a5 5 0 0 1 2.911-4.544C7.613 15.212 8.351 15.24 11 13"/>',
    "monitor": '<rect width="20" height="14" x="2" y="3" rx="2"/><line x1="8" x2="16" y1="21" y2="21"/><line x1="12" x2="12" y1="17" y2="21"/>',
    "moon": '<path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"/>',
    "paintbrush": '<path d="m14.622 17.897-10.68-2.913"/><path d="M18.376 2.622a1 1 0 1 1 3.002 3.002L17.36 9.643a.5.5 0 0 0 0 .707l.944.944a2.41 2.41 0 0 1 0 3.408l-.944.944a.5.5 0 0 1-.707 0L8.354 7.348a.5.5 0 0 1 0-.707l.944-.944a2.41 2.41 0 0 1 3.408 0l.944.944a.5.5 0 0 0 .707 0z"/><path d="M9 8c-1.804 2.71-3.97 3.46-6.583 3.948a.507.507 0 0 0-.302.819l7.32 8.883a1 1 0 0 0 1.185.204C12.735 20.405 16 16.792 16 15"/>',
    "palette": '<path d="M12 22a1 1 0 0 1 0-20 10 9 0 0 1 10 9 5 5 0 0 1-5 5h-2.25a1.75 1.75 0 0 0-1.4 2.8l.3.4a1.75 1.75 0 0 1-1.4 2.8z"/><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/>',
    "pencil": '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
    "plus": '<path d="M5 12h14M12 5v14"/>',
    "rotate-ccw": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
    "settings-2": '<path d="M14 17H5"/><path d="M19 7h-9"/><circle cx="17" cy="17" r="3"/><circle cx="7" cy="7" r="3"/>',
    "sliders-horizontal": '<path d="M10 5H3"/><path d="M12 19H3"/><path d="M14 3v4"/><path d="M16 17v4"/><path d="M21 12h-9"/><path d="M21 19h-5"/><path d="M21 5h-7"/><path d="M8 10v4"/><path d="M8 12H3"/>',
    "star": '<path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z"/>',
    "sticky-note": '<path d="M21 9a2.4 2.4 0 0 0-.706-1.706l-3.588-3.588A2.4 2.4 0 0 0 15 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2z"/><path d="M15 3v5a1 1 0 0 0 1 1h5"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    "trash-2": '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v5M14 11v5"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>'
  };

  var PAGE_ICONS = {
    appearance: "paintbrush", bento: "layout-dashboard", forecast: "cloud-sun",
    clock: "clock-3", background: "image", profile: "user",
    behavior: "sliders-horizontal", tea_room: "leaf", reviewer: "monitor",
    favorites: "star", history: "history", note: "sticky-note",
    audio: "headphones", connections: "bluetooth"
  };

  function $(id) { return document.getElementById(id); }
  function node(tag, cls, label) {
    var element = document.createElement(tag);
    if (cls) element.className = cls;
    if (label != null) element.textContent = label;
    return element;
  }
  function icon(name) {
    var box = node("span");
    box.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      (LUCIDE[name] || LUCIDE["settings-2"]) + "</svg>";
    return box.firstChild;
  }
  function installIcons(root) {
    (root || document).querySelectorAll("[data-icon]").forEach(function (slot) {
      slot.innerHTML = "";
      slot.appendChild(icon(slot.dataset.icon));
    });
  }
  function readValues() {
    values = {};
    pages.forEach(function (page) {
      (page.sections || []).forEach(function (group) {
        (group.fields || []).forEach(function (field) { values[field.path] = field.value; });
      });
    });
    (C.footprint || []).forEach(function (field) { values[field.path] = field.value; });
  }
  function call(command) {
    return new Promise(function (resolve) {
      try {
        pycmd(command, function (response) {
          if (typeof response === "string") {
            try { response = JSON.parse(response); } catch (_error) { /* keep raw */ }
          }
          resolve(response || {ok: false});
        });
      } catch (error) { resolve({ok: false, error: String(error)}); }
    });
  }
  function send(action, argument) { return call("bws:" + action + ":" + encodeURIComponent(argument || "")); }
  function hexRgba(hex, alpha) {
    var raw = String(hex).replace("#", "");
    if (raw.length === 3) raw = raw.replace(/./g, function (char) { return char + char; });
    var value = parseInt(raw, 16);
    return "rgba(" + ((value >> 16) & 255) + "," + ((value >> 8) & 255) + "," + (value & 255) + "," + alpha + ")";
  }
  function hexToRgb(hex) {
    var raw = String(hex || "").replace("#", "");
    if (raw.length === 3) raw = raw.replace(/./g, function (char) { return char + char; });
    if (raw.length !== 6 || /[^0-9a-f]/i.test(raw)) return [0, 169, 130];
    return [0, 2, 4].map(function (index) { return parseInt(raw.slice(index, index + 2), 16); });
  }
  function mix(hexA, hexB, amount) {
    var a = hexToRgb(hexA);
    var b = hexToRgb(hexB);
    var mixed = [0, 1, 2].map(function (index) {
      return Math.round(a[index] + (b[index] - a[index]) * (1 - amount));
    });
    return "#" + mixed.map(function (channel) {
      return Math.max(0, Math.min(255, channel)).toString(16).padStart(2, "0");
    }).join("");
  }
  function setTokens() {
    var palette = C.palette || {};
    var style = document.documentElement.style;
    var map = {outer: "--bws-outer", panel: "--bws-panel", surface: "--bws-surface", surface_alt: "--bws-surface-alt", inset: "--bws-inset", inset_hover: "--bws-inset-hover", hairline: "--bws-hairline", hairline_soft: "--bws-hairline-soft", fg: "--bws-fg", fg_muted: "--bws-muted", fg_faint: "--bws-faint", danger: "--bws-danger"};
    Object.keys(map).forEach(function (key) { if (palette[key]) style.setProperty(map[key], palette[key]); });
    style.setProperty("--bws-accent", C.accent || "#00a982");
    style.setProperty("--bws-accent-line-strong", mix(C.accent || "#00a982", palette.hairline || "#e3e4e7", 0.55));
    style.setProperty("--bws-accent-wash", hexRgba(C.accent || "#00a982", 0.1));
    style.setProperty("--bws-accent-wash-strong", hexRgba(C.accent || "#00a982", 0.16));
  }
  function status(kind, message) {
    var target = $("bwsAutosave");
    target.dataset.state = kind;
    target.querySelector("span").textContent = message || ({idle: window.onigiriText("Changes save automatically"), saving: window.onigiriText("Saving…"), saved: window.onigiriText("Saved"), error: window.onigiriText("Could not save")}[kind]);
  }
  function renderBridgeStatus() {
    var connected = Boolean(C.onigiriConnected);
    var statusNode = $("bwsBridgeStatus");
    var iconNode = statusNode.querySelector(".bws-bridge-icon");
    statusNode.dataset.connected = String(connected);
    iconNode.dataset.icon = connected ? "circle-check" : "circle-alert";
    $("bwsBridgeLabel").textContent = connected
      ? window.onigiriText("Onigiri installed · Bento bridge active") + (C.onigiriVersion ? " · v" + C.onigiriVersion : "")
      : window.onigiriText("Onigiri not detected");
    installIcons(statusNode);

    var footprint = $("bwsFootprint");
    footprint.hidden = connected;
    document.body.classList.toggle("bws-with-footprint", !connected);
    if (connected) return;
    var fields = $("bwsFootprintFields");
    fields.innerHTML = "";
    (C.footprint || []).forEach(function (field) {
      var label = node("label", "bws-footprint-field");
      var caption = node("span", "", field.label);
      var input = node("input", "bws-number");
      input.type = "number";
      input.min = field.min;
      input.max = field.max;
      input.step = field.step || 1;
      input.value = values[field.path] == null ? field.default : values[field.path];
      input.onchange = function () {
        var next = Math.max(Number(input.min), Math.min(Number(input.max), Number(input.value)));
        input.value = next;
        queue(field.path, next, false);
      };
      label.appendChild(caption);
      label.appendChild(input);
      label.appendChild(node("em", "", field.unit || ""));
      fields.appendChild(label);
    });
  }
  function queue(path, value, delayed) {
    values[path] = value;
    pending[path] = value;
    conditions();
    status("saving");
    clearTimeout(timer);
    timer = setTimeout(flush, delayed ? 280 : 0);
  }
  function flush() {
    if (inFlight) { timer = setTimeout(flush, 120); return; }
    var patch = pending;
    if (!Object.keys(patch).length) return;
    pending = {};
    inFlight = true;
    send("patch", JSON.stringify(patch)).then(function (response) {
      inFlight = false;
      if (!response || !response.ok) {
        Object.keys(patch).forEach(function (key) { if (!(key in pending)) pending[key] = patch[key]; });
        status("error", (response && response.error) || window.onigiriText("Could not save"));
        return;
      }
      status("saved");
      if (response.preview != null) setPreview(response.preview);
      if (Object.keys(pending).length) timer = setTimeout(flush, 100);
    });
  }
  function setPreview(html) {
    var source = html || "";
    C.preview = source;
    var frame = $("bwsPreview");
    if (!frame || frame.dataset.source === source) return;
    if (cancelPreviewSwap) cancelPreviewSwap();
    var stage = frame.parentNode;
    var revision = ++previewRevision;
    stage.querySelectorAll(".bws-preview-next").forEach(function (candidate) { candidate.remove(); });
    var next = node("iframe", "bws-preview-next");
    var settled = false;
    var fallbackTimer = 0;
    next.setAttribute("sandbox", "allow-scripts");
    next.dataset.source = source;
    function removeHooks() {
      clearTimeout(fallbackTimer);
      window.removeEventListener("message", onPreviewReady);
    }
    function commit() {
      if (settled) return;
      settled = true;
      removeHooks();
      if (revision !== previewRevision || !next.isConnected) { next.remove(); return; }
      var active = $("bwsPreview");
      next.classList.remove("bws-preview-next");
      if (active) {
        active.removeAttribute("id");
        active.classList.add("bws-preview-old");
      }
      next.id = "bwsPreview";
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { if (active) active.remove(); });
      });
      cancelPreviewSwap = null;
    }
    function onPreviewReady(event) {
      if (event.source === next.contentWindow && event.data === "bws-preview-ready") commit();
    }
    cancelPreviewSwap = function () {
      if (settled) return;
      settled = true;
      removeHooks();
      next.remove();
      cancelPreviewSwap = null;
    };
    window.addEventListener("message", onPreviewReady);
    next.srcdoc = source;
    stage.appendChild(next);
    fallbackTimer = setTimeout(commit, 2500);
  }
  function optionData(raw) { return typeof raw === "object" ? raw : {value: raw, label: String(raw)}; }
  function closeSelects(except) {
    document.querySelectorAll(".bws-select-menu.is-open").forEach(function (menu) {
      if (menu !== except) {
        menu.classList.remove("is-open");
        menu.closest(".bws-field").classList.remove("has-open-select");
        menu.querySelector(".bws-select-trigger").setAttribute("aria-expanded", "false");
      }
    });
  }
  function selectControl(field) {
    var menu = node("div", "bws-select-menu");
    var trigger = node("button", "bws-select-trigger");
    var triggerLabel = node("span");
    var list = node("div", "bws-select-list");
    var options = (field.options || []).map(optionData);
    trigger.type = "button";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    list.setAttribute("role", "listbox");
    trigger.appendChild(triggerLabel);
    trigger.appendChild(icon("chevron-down"));
    function paint(selected) {
      var match = options.find(function (item) { return String(item.value) === String(selected); }) || options[0] || {label: ""};
      triggerLabel.textContent = match.label;
      Array.from(list.children).forEach(function (button) {
        var active = String(button.dataset.value) === String(selected);
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-selected", String(active));
        var old = button.querySelector("svg");
        if (old) old.remove();
        if (active) button.appendChild(icon("check"));
      });
    }
    options.forEach(function (item) {
      var button = node("button", "bws-select-option", item.label);
      button.type = "button";
      button.dataset.value = String(item.value);
      button.setAttribute("role", "option");
      button.onclick = function (event) {
        event.stopPropagation();
        paint(item.value);
        closeSelects();
        queue(field.path, item.value, false);
      };
      list.appendChild(button);
    });
    paint(values[field.path]);
    trigger.onclick = function (event) {
      event.stopPropagation();
      var opening = !menu.classList.contains("is-open");
      closeSelects(menu);
      menu.classList.toggle("is-open", opening);
      menu.closest(".bws-field").classList.toggle("has-open-select", opening);
      trigger.setAttribute("aria-expanded", String(opening));
    };
    trigger.onkeydown = function (event) { if (event.key === "Escape") closeSelects(); };
    menu.appendChild(trigger);
    menu.appendChild(list);
    return menu;
  }
  function sliderControl(field) {
    var slider = node("div", "bws-slider");
    var track = node("div", "bws-slider-track");
    var fill = node("div", "bws-slider-fill");
    var thumb = node("div", "bws-slider-thumb");
    var output = node("span", "bws-value");
    var min = Number(field.min == null ? 0 : field.min);
    var max = Number(field.max == null ? 100 : field.max);
    var step = Number(field.step || 1);
    var value = Number(values[field.path] == null ? min : values[field.path]);
    var lastHapticValue = value;
    slider.tabIndex = 0;
    slider.setAttribute("role", "slider");
    slider.setAttribute("aria-valuemin", String(min));
    slider.setAttribute("aria-valuemax", String(max));
    function decimals(number) { var text = String(number); return text.indexOf(".") < 0 ? 0 : text.length - text.indexOf(".") - 1; }
    function snap(raw) {
      var bounded = Math.max(min, Math.min(max, raw));
      return Number((min + Math.round((bounded - min) / step) * step).toFixed(decimals(step)));
    }
    function paint(next, save, delayed) {
      value = snap(next);
      var percent = max === min ? 0 : ((value - min) / (max - min)) * 100;
      fill.style.width = percent + "%";
      thumb.style.left = "max(6px, min(calc(" + percent + "% - 10px), calc(100% - 11px)))";
      output.textContent = value + (field.unit || "");
      slider.setAttribute("aria-valuenow", String(value));
      if (save) queue(field.path, value, delayed);
    }
    function fromPointer(event) {
      var rect = track.getBoundingClientRect();
      if (rect.width <= 0) return;
      paint(min + ((event.clientX - rect.left) / rect.width) * (max - min), true, true);
      if (value !== lastHapticValue) {
        lastHapticValue = value;
        send("haptic", "2");
      }
    }
    var isDragging = false;
    function onPointerMove(event) {
      if (isDragging) fromPointer(event);
    }
    function finishDrag() {
      if (!isDragging) return;
      isDragging = false;
      slider.classList.remove("is-dragging");
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", finishDrag);
      flush();
    }
    track.onpointerdown = function (event) {
      isDragging = true;
      slider.classList.add("is-dragging");
      fromPointer(event);
      window.addEventListener("pointermove", onPointerMove);
      window.addEventListener("pointerup", finishDrag);
    };
    slider.onkeydown = function (event) {
      var change = 0;
      if (event.key === "ArrowLeft" || event.key === "ArrowDown") change = -step;
      if (event.key === "ArrowRight" || event.key === "ArrowUp") change = step;
      if (event.key === window.onigiriText("Home")) { event.preventDefault(); paint(min, true, false); }
      else if (event.key === "End") { event.preventDefault(); paint(max, true, false); }
      else if (change) { event.preventDefault(); paint(value + change, true, false); }
    };
    track.appendChild(fill);
    track.appendChild(thumb);
    slider.appendChild(output);
    slider.appendChild(track);
    paint(value, false, false);
    return slider;
  }
  function normalHex(input, fallback) {
    var raw = String(input || "").trim();
    var short = raw.match(/^#([0-9a-f]{3})$/i);
    if (short) return ("#" + short[1].replace(/./g, function (c) { return c + c; })).toUpperCase();
    var qtAlpha = raw.match(/^#([0-9a-f]{2})([0-9a-f]{6})$/i);
    if (qtAlpha) return ("#" + qtAlpha[2]).toUpperCase();
    var full = raw.match(/^#([0-9a-f]{6})/i);
    if (full) return ("#" + full[1]).toUpperCase();
    var probe = document.createElement("span");
    probe.style.color = raw;
    probe.style.display = "none";
    document.body.appendChild(probe);
    var match = getComputedStyle(probe).color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
    probe.remove();
    if (!match) return fallback || "#000000";
    return "#" + [match[1], match[2], match[3]].map(function (part) { return Number(part).toString(16).padStart(2, "0"); }).join("").toUpperCase();
  }
  function hexToHsv(hex) {
    var number = parseInt(normalHex(hex).slice(1), 16);
    var red = ((number >> 16) & 255) / 255;
    var green = ((number >> 8) & 255) / 255;
    var blue = (number & 255) / 255;
    var max = Math.max(red, green, blue);
    var min = Math.min(red, green, blue);
    var delta = max - min;
    var hue = 0;
    if (delta) {
      if (max === red) hue = 60 * (((green - blue) / delta) % 6);
      else if (max === green) hue = 60 * (((blue - red) / delta) + 2);
      else hue = 60 * (((red - green) / delta) + 4);
    }
    if (hue < 0) hue += 360;
    return {h: hue, s: max ? delta / max : 0, v: max};
  }
  function hsvToHex(hue, saturation, value) {
    var chroma = value * saturation;
    var part = chroma * (1 - Math.abs(((hue / 60) % 2) - 1));
    var offset = value - chroma;
    var rgb = hue < 60 ? [chroma, part, 0] : hue < 120 ? [part, chroma, 0] : hue < 180 ? [0, chroma, part] : hue < 240 ? [0, part, chroma] : hue < 300 ? [part, 0, chroma] : [chroma, 0, part];
    return "#" + rgb.map(function (channel) { return Math.round((channel + offset) * 255).toString(16).padStart(2, "0"); }).join("").toUpperCase();
  }
  function preserveColorAlpha(original, hex) {
    var value = String(original || "").trim();
    var rgba = /^rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*([^)]+)\)$/i.exec(value);
    if (rgba) {
      var number = parseInt(hex.slice(1), 16);
      return "rgba(" + ((number >> 16) & 255) + ", " + ((number >> 8) & 255) + ", " +
        (number & 255) + ", " + rgba[1].trim() + ")";
    }
    if (/^#[0-9a-f]{8}$/i.test(value)) return value.slice(0, 3) + hex.slice(1);
    return hex;
  }
  function closeColorPicker() {
    if (!activePicker) return;
    var overlay = activePicker;
    activePicker = null;
    overlay.classList.add("is-closing");
    setTimeout(function () { overlay.remove(); }, 140);
  }
  function openColorPicker(field, repaintSlot) {
    closeColorPicker();
    var original = normalHex(values[field.path] || field.default || "#000000");
    var hsv = hexToHsv(original);
    var selected = original;
    var overlay = node("div", "bws-picker-overlay");
    var picker = node("section", "bws-picker");
    var head = node("header", "bws-picker-head");
    var body = node("div", "bws-picker-body");
    var foot = node("footer", "bws-picker-foot");
    var close = node("button", "bws-picker-close");
    var sv = node("div", "bws-colorpick-sv");
    var cursor = node("span", "bws-colorpick-cursor");
    var hue = node("input", "bws-colorpick-hue");
    var value = node("input", "bws-colorpick-value");
    var entry = node("label", "bws-colorpick-entry");
    var preview = node("span", "bws-colorpick-preview");
    var text = node("input");
    var cancel = node("button", "bws-picker-btn", window.onigiriText("Cancel"));
    var save = node("button", "bws-picker-btn is-primary", window.onigiriText("Save"));
    close.type = cancel.type = save.type = "button";
    close.appendChild(icon("x"));
    head.appendChild(node("div", "bws-picker-title", field.label));
    head.appendChild(close);
    hue.type = value.type = "range";
    hue.min = 0; hue.max = 360; hue.step = 1;
    value.min = 0; value.max = 100; value.step = 1;
    sv.appendChild(cursor);
    entry.appendChild(preview);
    entry.appendChild(text);
    body.appendChild(sv); body.appendChild(value); body.appendChild(hue); body.appendChild(entry);
    foot.appendChild(cancel); foot.appendChild(save);
    picker.appendChild(head); picker.appendChild(body); picker.appendChild(foot); overlay.appendChild(picker);
    document.body.appendChild(overlay);
    activePicker = overlay;
    function paint() {
      selected = hsvToHex(hsv.h, hsv.s, hsv.v);
      sv.style.setProperty("--bws-picker-hue", String(Math.round(hsv.h)));
      cursor.style.left = (hsv.s * 100) + "%";
      cursor.style.top = ((1 - hsv.v) * 100) + "%";
      hue.value = String(Math.round(hsv.h));
      value.value = String(Math.round(hsv.v * 100));
      preview.style.backgroundColor = selected;
      text.value = selected;
    }
    function setSv(event) {
      var rect = sv.getBoundingClientRect();
      hsv.s = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
      hsv.v = 1 - Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height));
      paint();
    }
    sv.onpointerdown = function (event) { sv.setPointerCapture(event.pointerId); setSv(event); };
    sv.onpointermove = function (event) { if (sv.hasPointerCapture(event.pointerId)) setSv(event); };
    hue.oninput = function () { hsv.h = Number(hue.value); paint(); };
    value.oninput = function () { hsv.v = Number(value.value) / 100; paint(); };
    text.onchange = function () { hsv = hexToHsv(normalHex(text.value, selected)); paint(); };
    close.onclick = cancel.onclick = closeColorPicker;
    overlay.onclick = function (event) { if (event.target === overlay) closeColorPicker(); };
    save.onclick = function () {
      queue(field.path, preserveColorAlpha(original, selected), false);
      repaintSlot(selected);
      closeColorPicker();
    };
    overlay.onkeydown = function (event) { if (event.key === "Escape") closeColorPicker(); };
    overlay.tabIndex = -1;
    paint();
    overlay.focus();
  }
  function colorControl(field) {
    var button = node("button", "bws-colorslot");
    var swatch = node("span", "bws-color-swatch");
    var label = node("span", "bws-color-hex");
    var edit = node("span", "bws-color-edit");
    button.type = "button";
    edit.appendChild(icon("pencil"));
    button.appendChild(swatch); button.appendChild(label); button.appendChild(edit);
    function paint(value) { var normalized = normalHex(value, "#000000"); swatch.style.backgroundColor = normalized; label.textContent = normalized; }
    button.onclick = function () { openColorPicker(field, paint); };
    paint(values[field.path] || field.default);
    return button;
  }
  function actionIcon(path) {
    var action = String(path || "").toLowerCase();
    if (action.indexOf("add") >= 0) return "plus";
    if (action.indexOf("delete") >= 0 || action.indexOf("remove") >= 0) return "trash-2";
    if (action.indexOf("save") >= 0) return "bookmark-plus";
    if (action.indexOf("load") >= 0 || action.indexOf("open") >= 0) return "folder-open";
    return "arrow-right";
  }
  function control(field) {
    var wrap = node("div", "bws-control");
    var input;
    if (field.type === "info") { wrap.appendChild(node("span", "bws-info", values[field.path] == null ? "" : String(values[field.path]))); return wrap; }
    if (field.type === "action") {
      input = node("button", "bws-action");
      input.type = "button";
      input.appendChild(icon(actionIcon(field.path)));
      input.appendChild(node("span", "", field.buttonLabel || field.label));
      input.onclick = function () {
        status("saving");
        send("action", field.path).then(function (response) {
          if (!response || !response.ok) { status("error", (response && response.error) || window.onigiriText("Action failed")); return; }
          if (response.pages) { pages = response.pages; readValues(); nav(); render(); }
          if (response.preview != null) setPreview(response.preview);
          status("saved");
        });
      };
      wrap.appendChild(input);
      return wrap;
    }
    if (field.type === "bool") {
      input = node("button", "bws-switch" + (values[field.path] ? " is-on" : ""));
      input.type = "button";
      input.setAttribute("role", "switch");
      input.setAttribute("aria-checked", String(Boolean(values[field.path])));
      input.onclick = function () {
        var next = !values[field.path];
        input.classList.toggle("is-on", next);
        input.setAttribute("aria-checked", String(next));
        queue(field.path, next, false);
      };
      wrap.appendChild(input);
      return wrap;
    }
    if (field.type === window.onigiriText("select")) { wrap.appendChild(selectControl(field)); return wrap; }
    if (field.type === "textarea") {
      input = node("textarea", "bws-textarea"); input.rows = field.rows || 4; input.placeholder = field.placeholder || ""; input.value = values[field.path] || "";
      input.oninput = function () { queue(field.path, input.value, true); };
      wrap.appendChild(input); return wrap;
    }
    if (field.type === "range") { wrap.appendChild(sliderControl(field)); return wrap; }
    if (field.type === "color") { wrap.appendChild(colorControl(field)); return wrap; }
    input = node("input", field.type === "number" ? "bws-number" : "bws-input");
    input.type = field.type === "number" ? "number" : (field.type === "time" ? "time" : "text");
    if (field.min != null) input.min = field.min;
    if (field.max != null) input.max = field.max;
    if (field.step != null) input.step = field.step;
    input.placeholder = field.placeholder || "";
    input.value = values[field.path] == null ? "" : values[field.path];
    input.oninput = function () { queue(field.path, field.type === "number" ? Number(input.value) : input.value, true); };
    input.onchange = flush;
    wrap.appendChild(input);
    if (field.unit) wrap.appendChild(node("span", "bws-value", field.unit));
    return wrap;
  }
  function fieldRow(field) {
    var row = node("div", "bws-field");
    var copy = node("div", "bws-field-copy");
    row.dataset.path = field.path;
    copy.appendChild(node("b", "", field.label));
    if (field.description) copy.appendChild(node("small", "", field.description));
    row.appendChild(copy); row.appendChild(control(field));
    return row;
  }
  function segmentButton(label, active, iconName) {
    var button = node("button", active ? "is-active" : "");
    button.type = "button";
    if (iconName) button.appendChild(icon(iconName));
    button.appendChild(node("span", "", label));
    return button;
  }
  function render() {
    closeSelects();
    var page = pages.find(function (candidate) { return candidate.id === current; }) || pages[0];
    if (!page) return;
    $("bwsPageTitle").textContent = page.title;
    $("bwsPageDesc").textContent = page.description || C.subtitle || "";
    var host = $("bwsPage");
    var previewCard = $("bwsPreviewCard");
    Array.from(host.children).forEach(function (child) {
      if (child !== previewCard) child.remove();
    });
    if (!previewCard) {
      previewCard = node("section", "bws-preview-card");
      previewCard.id = "bwsPreviewCard";
      var previewHead = node("div", "bws-preview-head");
      previewHead.appendChild(node("strong", "", window.onigiriText("Real preview")));
      if ((C.previewVariants || []).length > 1) {
        var variants = node("div", "bws-segments");
        (C.previewVariants || []).forEach(function (option) {
          var button = segmentButton(option.label, String(option.value) === String(C.previewVariant));
          button.onclick = function () {
            C.previewVariant = option.value; previewRequest();
            Array.from(variants.children).forEach(function (item) { item.classList.toggle("is-active", item === button); });
          };
          variants.appendChild(button);
        });
        previewHead.appendChild(variants);
      }
      var themes = node("div", "bws-segments");
      ["light", "dark"].forEach(function (theme) {
        var button = segmentButton(theme[0].toUpperCase() + theme.slice(1), C.previewTheme === theme, theme === "light" ? "sun" : "moon");
        button.onclick = function () {
          C.previewTheme = theme; previewRequest();
          Array.from(themes.children).forEach(function (item) { item.classList.toggle("is-active", item === button); });
        };
        themes.appendChild(button);
      });
      previewHead.appendChild(themes);
      var reset = node("button", "bws-reset");
      reset.type = "button"; reset.appendChild(icon("rotate-ccw")); reset.appendChild(node("span", "", window.onigiriText("Reset"))); reset.onclick = resetAll;
      previewHead.appendChild(reset);
      previewCard.appendChild(previewHead);
      var stage = node("div", "bws-preview-stage");
      var frame = node("iframe");
      frame.id = "bwsPreview"; frame.setAttribute("sandbox", "allow-scripts"); frame.srcdoc = C.preview || ""; frame.dataset.source = C.preview || "";
      stage.appendChild(frame); previewCard.appendChild(stage); host.appendChild(previewCard);
    }
    /* Informational pages can own the full page without pretending their
       content is another state of the widget preview. */
    previewCard.hidden = page.showPreview === false;
    (page.sections || []).forEach(function (group) {
      var card = node("section", "bws-section");
      var head = node("div", "bws-section-head");
      head.appendChild(node("h2", "", group.title));
      if (group.description) head.appendChild(node("p", "", group.description));
      card.appendChild(head);
      var fields = node("div", "bws-fields");
      (group.fields || []).forEach(function (field) { fields.appendChild(fieldRow(field)); });
      card.appendChild(fields); host.appendChild(card);
    });
    conditions();
  }
  function conditions() {
    document.querySelectorAll(".bws-field").forEach(function (row) {
      var field = null;
      pages.forEach(function (page) { (page.sections || []).forEach(function (group) { (group.fields || []).forEach(function (candidate) { if (candidate.path === row.dataset.path) field = candidate; }); }); });
      if (!field || !field.showIf) { row.classList.remove("is-hidden"); return; }
      var visible = Object.keys(field.showIf).every(function (key) { return String(values[key]) === String(field.showIf[key]); });
      row.classList.toggle("is-hidden", !visible);
    });
  }
  function nav() {
    var host = $("bwsNav");
    host.innerHTML = "";
    pages.forEach(function (page) {
      var button = node("button", "bws-nav-btn" + (page.id === current ? " is-active" : ""));
      var iconSlot = node("span", "bws-nav-icon");
      button.type = "button"; button.dataset.page = page.id;
      iconSlot.appendChild(icon(PAGE_ICONS[page.id] || "settings-2"));
      button.appendChild(iconSlot); button.appendChild(node("span", "bws-nav-label", page.title));
      button.onclick = function () {
        current = page.id;
        Array.from(host.children).forEach(function (item) { item.classList.toggle("is-active", item === button); });
        render();
      };
      host.appendChild(button);
    });
  }
  function previewRequest() {
    send("preview", JSON.stringify({variant: C.previewVariant, theme: C.previewTheme})).then(function (response) { if (response && response.ok) setPreview(response.preview); });
  }
  function confirmReset() {
    return new Promise(function (resolve) {
      if (document.querySelector(".bws-confirm-overlay")) { resolve(false); return; }
      closeSelects(); closeColorPicker();
      var overlay = node("div", "bws-confirm-overlay");
      var dialog = node("section", "bws-confirm-dialog");
      var mark = node("div", "bws-confirm-mark");
      var copy = node("div", "bws-confirm-copy");
      var actions = node("div", "bws-confirm-actions");
      var cancel = node("button", "bws-confirm-button", window.onigiriText("Cancel"));
      var restore = node("button", "bws-confirm-button is-primary", window.onigiriText("Restore defaults"));
      var title = node("h2", "", window.onigiriText("Restore {name} defaults?").replace("{name}", C.title || "Bento"));
      var description = node("p", "", window.onigiriText("This replaces every setting for this widget with its original value."));
      cancel.type = restore.type = "button";
      title.id = "bwsConfirmTitle";
      dialog.setAttribute("role", "alertdialog");
      dialog.setAttribute("aria-modal", "true");
      dialog.setAttribute("aria-labelledby", title.id);
      mark.appendChild(icon("rotate-ccw"));
      copy.appendChild(title); copy.appendChild(description);
      actions.appendChild(cancel); actions.appendChild(restore);
      dialog.appendChild(mark); dialog.appendChild(copy); dialog.appendChild(actions);
      overlay.appendChild(dialog); document.body.appendChild(overlay);
      function finish(confirmed) {
        overlay.classList.add("is-closing");
        setTimeout(function () { overlay.remove(); resolve(confirmed); }, 140);
      }
      cancel.onclick = function () { finish(false); };
      restore.onclick = function () { finish(true); };
      overlay.onclick = function (event) { if (event.target === overlay) finish(false); };
      overlay.onkeydown = function (event) {
        if (event.key === "Escape") { event.preventDefault(); finish(false); }
      };
      setTimeout(function () { restore.focus(); }, 0);
    });
  }
  function resetAll() {
    confirmReset().then(function (confirmed) {
      if (!confirmed) return;
      status("saving");
      send("reset", "").then(function (response) {
        if (!response || !response.ok) { status("error", (response && response.error) || window.onigiriText("Could not reset")); return; }
        pages = response.pages || pages;
        C.footprint = response.footprint || C.footprint;
        readValues(); renderBridgeStatus(); status("saved"); setPreview(response.preview || ""); nav(); render();
      });
    });
  }
  function finish() {
    clearTimeout(timer); flush();
    var checks = 0;
    (function waitForSave() {
      if (inFlight || Object.keys(pending).length) {
        if (++checks > 150) { status("error", window.onigiriText("Save failed; settings left open")); return; }
        setTimeout(waitForSave, 40); return;
      }
      send("done", "");
    })();
  }
  function init() {
    setTokens(); readValues();
    $("bwsTitle").textContent = C.title || "Bento";
    $("bwsBrandMark").textContent = (C.title || "B")[0].toUpperCase();
    if (C.logo) {
      $("bwsBrandLogo").src = C.logo;
      $("bwsBrandLogo").alt = (C.title || "Bento") + " logo";
      document.querySelector(".bws-brand").classList.add("has-logo");
    }
    if (C.miniLogo) {
      $("bwsBrandMiniLogo").src = C.miniLogo;
      $("bwsBrandMiniLogo").alt = (C.title || "Bento") + " compact logo";
      document.querySelector(".bws-brand").classList.add("has-mini-logo");
    }
    $("bwsDonate").hidden = !C.hasDonate;
    $("bwsBugs").hidden = !C.hasBugs;
    $("bwsDonate").onclick = function () { send("donate", ""); };
    $("bwsBugs").onclick = function () { send("bugs", ""); };
    $("bwsDone").onclick = finish;
    document.addEventListener("click", function () { closeSelects(); });
    document.addEventListener("keydown", function (event) { if (event.key === "Escape") { closeSelects(); closeColorPicker(); } });
    installIcons(document); renderBridgeStatus(); nav(); render(); status("idle");
    document.documentElement.classList.remove("bws-booting");
    send("ready", "");
  }

  init();
})();
