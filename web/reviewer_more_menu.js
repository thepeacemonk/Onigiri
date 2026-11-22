(function () {
  "use strict";

  if (window.OnigiriReviewerMoreMenu) return;

  const HOST_ID = "onigiri-reviewer-more-menu-host";
  const FLAG_FALLBACK_COLORS = {
    1: "#ff5a5f",
    2: "#ff9f0a",
    3: "#30d158",
    4: "#0a84ff",
    5: "#ff6482",
    6: "#40c8e0",
    7: "#bf5af2"
  };

  let host = null;
  let shadow = null;
  let root = null;
  let backdrop = null;
  let panel = null;
  let state = "closed"; // "closed" | "open" | "closing"
  let closeTimer = null;
  let actionTimer = null;
  let currentData = null;

  function cssText() {
    return window.onigiriMoreMenuCssText || "";
  }

  function isNightMode(fallbackDark) {
    const html = document.documentElement;
    const body = document.body;
    const domDark = [html, body].some(
      (el) =>
        el &&
        (el.classList.contains("night-mode") ||
          el.classList.contains("nightMode") ||
          el.classList.contains("night_mode"))
    );
    return domDark || Boolean(fallbackDark);
  }

  function isRtl() {
    const html = document.documentElement;
    const body = document.body;
    return (
      (html && html.getAttribute("dir") === "rtl") ||
      (body && body.getAttribute("dir") === "rtl")
    );
  }

  function sendCmd(cmd) {
    if (typeof window.pycmd === "function") {
      window.pycmd(cmd);
    }
  }

  function svgEl(viewBox, paths, cls) {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", viewBox || "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.9");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    if (cls) svg.setAttribute("class", cls);
    paths.forEach((spec) => {
      const tag = spec.tag || "path";
      const node = document.createElementNS(ns, tag);
      Object.keys(spec).forEach((k) => {
        if (k !== "tag") node.setAttribute(k, spec[k]);
      });
      svg.appendChild(node);
    });
    return svg;
  }

  const ICONS = {
    flag: (filled) =>
      svgEl(
        "0 0 24 24",
        [
          {
            d: "M5 21V5a1 1 0 0 1 1-1h10.5l-1.9 4.5 1.9 4.5H5",
            fill: filled ? "currentColor" : "none"
          }
        ],
        "rm-flag-svg"
      ),
    star: (filled) =>
      svgEl(
        "0 0 24 24",
        [
          {
            d: "m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.8 1-6.1L3.2 9.4l6.1-.9Z",
            fill: filled ? "currentColor" : "none"
          }
        ],
        "rm-quick-icon"
      ),
    bolt: () =>
      svgEl(
        "0 0 24 24",
        [{ d: "M13 2 4 14h7l-1 8 9-12h-7Z" }],
        "rm-quick-icon"
      ),
    sliders: () =>
      svgEl(
        "0 0 24 24",
        [
          { d: "M4 21v-7" },
          { d: "M4 10V3" },
          { d: "M12 21v-9" },
          { d: "M12 8V3" },
          { d: "M20 21v-5" },
          { d: "M20 12V3" },
          { d: "M2 14h4" },
          { d: "M10 8h4" },
          { d: "M18 16h4" }
        ],
        "rm-quick-icon"
      ),
    info: () =>
      svgEl(
        "0 0 24 24",
        [
          { tag: "circle", cx: "12", cy: "12", r: "9" },
          { d: "M12 16v-4" },
          { d: "M12 8h.01" }
        ],
        "rm-quick-icon"
      ),
    history: () =>
      svgEl(
        "0 0 24 24",
        [
          { d: "M3 12a9 9 0 1 0 3-6.7L3 8" },
          { d: "M3 3v5h5" },
          { d: "M12 7v5l3 2" }
        ],
        "rm-quick-icon"
      ),
    bury: () =>
      svgEl(
        "0 0 24 24",
        [
          { d: "M2 18h20" },
          { d: "M12 4v10" },
          { d: "m8 10 4 4 4-4" }
        ],
        "rm-row-icon"
      ),
    suspend: () =>
      svgEl(
        "0 0 24 24",
        [
          { tag: "circle", cx: "12", cy: "12", r: "9" },
          { d: "M10 9v6" },
          { d: "M14 9v6" }
        ],
        "rm-row-icon"
      ),
    calendar: () =>
      svgEl(
        "0 0 24 24",
        [
          { tag: "rect", x: "3", y: "4", width: "18", height: "18", rx: "2.5" },
          { d: "M16 2v4" },
          { d: "M8 2v4" },
          { d: "M3 10h18" }
        ],
        "rm-row-icon"
      ),
    reset: () =>
      svgEl(
        "0 0 24 24",
        [
          { d: "M3 12a9 9 0 1 0 3-6.7L3 8" },
          { d: "M3 3v5h5" }
        ],
        "rm-row-icon"
      ),
    copy: () =>
      svgEl(
        "0 0 24 24",
        [
          { tag: "rect", x: "9", y: "9", width: "12", height: "12", rx: "2" },
          { d: "M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" }
        ],
        "rm-row-icon"
      ),
    trash: () =>
      svgEl(
        "0 0 24 24",
        [
          { d: "M3 6h18" },
          { d: "M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" },
          { d: "M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" }
        ],
        "rm-row-icon"
      ),
    rewind: () =>
      svgEl(
        "0 0 24 24",
        [
          { d: "M11 17l-5-5 5-5" },
          { d: "M18 17l-5-5 5-5" }
        ],
        "rm-media-icon"
      ),
    forward: () =>
      svgEl(
        "0 0 24 24",
        [
          { d: "M13 17l5-5-5-5" },
          { d: "M6 17l5-5-5-5" }
        ],
        "rm-media-icon"
      ),
    replay: () =>
      svgEl(
        "0 0 24 24",
        [
          { d: "M21 12a9 9 0 1 1-3-6.7L21 8" },
          { d: "M21 3v5h-5" }
        ],
        "rm-media-icon"
      ),
    pause: () =>
      svgEl(
        "0 0 24 24",
        [
          { d: "M9 6v12" },
          { d: "M15 6v12" }
        ],
        "rm-media-icon"
      ),
    mic: () =>
      svgEl(
        "0 0 24 24",
        [
          { tag: "rect", x: "9", y: "2", width: "6", height: "12", rx: "3" },
          { d: "M5 10a7 7 0 0 0 14 0" },
          { d: "M12 17v5" },
          { d: "M8 22h8" }
        ],
        "rm-media-icon"
      ),
    volume: () =>
      svgEl(
        "0 0 24 24",
        [
          { d: "M11 5L6 9H2v6h4l5 4V5Z" },
          { d: "M15.5 8.5a5 5 0 0 1 0 7" },
          { d: "M18.5 5.5a9 9 0 0 1 0 13" }
        ],
        "rm-media-icon"
      ),
    chevron: () =>
      svgEl(
        "0 0 24 24",
        [{ d: "m9 18 6-6-6-6" }],
        "rm-chevron"
      )
  };

  function makeKbd(text, bare) {
    if (!text) return null;
    const span = document.createElement("span");
    span.className = "rm-kbd" + (bare ? " is-bare" : "");
    span.setAttribute("aria-hidden", "true");
    span.textContent = text;
    return span;
  }

  function makeFlagGlyph(iconUrl, filled) {
    if (iconUrl) {
      const glyph = document.createElement("span");
      glyph.className = "rm-flag-glyph";
      glyph.setAttribute("aria-hidden", "true");
      const safeUrl = 'url("' + String(iconUrl).replace(/"/g, "%22") + '")';
      glyph.style.setProperty("--rm-flag-mask", safeUrl);
      return glyph;
    }
    return ICONS.flag(filled);
  }

  function stripTrailingEllipsis(text) {
    if (!text) return "";
    return String(text).replace(/(?:\.{3}|…)+\s*$/, "").trim();
  }

  function ensureHost() {
    if (!document.body) return null;
    host = document.getElementById(HOST_ID);
    if (!host) {
      host = document.createElement("div");
      host.id = HOST_ID;
      host.style.cssText = [
        "all: initial !important",
        "position: fixed !important",
        "inset: 0 !important",
        "display: block !important",
        "z-index: 2147483200 !important",
        "pointer-events: none !important",
        "contain: layout style paint !important"
      ].join("; ");
      document.body.appendChild(host);
    }
    if (!shadow) {
      shadow = host.shadowRoot || host.attachShadow({ mode: "open" });
      const style = document.createElement("style");
      style.id = "onigiri-more-menu-style";
      style.textContent = cssText();

      root = document.createElement("div");
      root.id = "onigiri-more-menu-root";

      backdrop = document.createElement("div");
      backdrop.className = "rm-backdrop";
      backdrop.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        e.stopPropagation();
        requestClose();
      });

      panel = document.createElement("div");
      panel.className = "rm-panel";
      panel.setAttribute("role", "menu");
      panel.setAttribute("aria-label", "More options");
      panel.addEventListener("keydown", handlePanelKeydown);

      root.appendChild(backdrop);
      root.appendChild(panel);
      shadow.appendChild(style);
      shadow.appendChild(root);
    }
    return shadow;
  }

  function focusableButtons() {
    if (!panel) return [];
    return Array.from(panel.querySelectorAll("button:not(:disabled)")).filter(
      (btn) => btn.offsetParent !== null && !btn.hidden
    );
  }

  function handlePanelKeydown(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      requestClose();
      return;
    }
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
    const items = focusableButtons();
    if (!items.length) return;
    e.preventDefault();
    e.stopPropagation();
    const active = shadow && shadow.activeElement;
    const idx = items.indexOf(active);
    let nextIdx = 0;
    if (e.key === "Home") nextIdx = 0;
    else if (e.key === "End") nextIdx = items.length - 1;
    else if (e.key === "ArrowDown") nextIdx = idx < 0 ? 0 : (idx + 1) % items.length;
    else if (e.key === "ArrowUp") nextIdx = idx <= 0 ? items.length - 1 : idx - 1;
    items[nextIdx].focus({ preventScroll: true });
  }

  function triggerAction(actionId, opts) {
    const o = opts || {};
    if (actionTimer) {
      clearTimeout(actionTimer);
      actionTimer = null;
    }
    if (o.keepOpen) {
      sendCmd("onigiri_more_menu:act:" + actionId);
      if (o.pulseEl) {
        o.pulseEl.classList.remove("is-pulsing");
        void o.pulseEl.offsetWidth;
        o.pulseEl.classList.add("is-pulsing");
        setTimeout(() => o.pulseEl.classList.remove("is-pulsing"), 220);
      }
      return;
    }
    if (o.delayMs && o.delayMs > 0) {
      sendCmd("onigiri_more_menu:act:" + actionId);
      actionTimer = setTimeout(() => {
        actionTimer = null;
        requestClose();
      }, o.delayMs);
      return;
    }
    closeImmediate(true);
    sendCmd("onigiri_more_menu:act:" + actionId);
  }

  function renderPanel(data) {
    currentData = data || {};
    const labels = currentData.labels || {};
    const shortcuts = currentData.shortcuts || {};
    const flags = Array.isArray(currentData.flags) ? currentData.flags : [];
    const activeFlag = Number(currentData.flag || 0);
    let marked = Boolean(currentData.marked);
    let autoAdvance = Boolean(currentData.autoAdvance);
    const hasPrev = Boolean(currentData.hasPreviousCard);
    const customItems = Array.isArray(currentData.customItems) ? currentData.customItems : [];

    panel.textContent = "";

    if (typeof currentData.anchorRight === "number" && isFinite(currentData.anchorRight)) {
      const clamped = Math.max(8, Math.min(200, Math.round(currentData.anchorRight)));
      root.style.setProperty("--rm-anchor-right", clamped + "px");
    } else {
      root.style.removeProperty("--rm-anchor-right");
    }

    // ── 1. Flag Strip ──
    const flagDock = document.createElement("div");
    flagDock.className = "rm-dock rm-section";
    flagDock.style.setProperty("--rm-stagger", "0");

    const flagHeader = document.createElement("div");
    flagHeader.className = "rm-flag-header";

    const flagStatus = document.createElement("div");
    flagStatus.className = "rm-flag-status";
    const flagDot = document.createElement("span");
    flagDot.className = "rm-flag-dot-live";
    const flagName = document.createElement("span");
    flagName.className = "rm-flag-name";
    flagStatus.append(flagDot, flagName);

    const flagHeaderRight = document.createElement("div");
    flagHeaderRight.className = "rm-flag-header-right";
    const flagShortcutHint = document.createElement("span");
    flagShortcutHint.className = "rm-kbd";
    flagShortcutHint.setAttribute("aria-hidden", "true");
    flagShortcutHint.hidden = true;
    const clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "rm-flag-clear";
    clearBtn.textContent = labels.clearFlag || "Clear";
    clearBtn.hidden = activeFlag <= 0;

    flagHeaderRight.append(flagShortcutHint, clearBtn);
    flagHeader.append(flagStatus, flagHeaderRight);

    const flagRow = document.createElement("div");
    flagRow.className = "rm-flag-row";

    let currentActiveFlag = activeFlag;

    function updateFlagStatus(previewIndex) {
      const targetIdx = previewIndex !== null && previewIndex !== undefined ? previewIndex : currentActiveFlag;
      const found = flags.find((f) => Number(f.index) === Number(targetIdx));
      if (found) {
        const color = found.color || FLAG_FALLBACK_COLORS[found.index] || "var(--rm-accent)";
        flagDot.style.background = color;
        flagDot.style.transform = "scale(1.15)";
        flagName.textContent = found.label;
        if (found.shortcut) {
          flagShortcutHint.textContent = found.shortcut;
          flagShortcutHint.hidden = false;
        } else {
          flagShortcutHint.hidden = true;
        }
      } else {
        flagDot.style.background = "";
        flagDot.style.transform = "";
        flagName.textContent = labels.flagCard || "Flag Card";
        flagShortcutHint.hidden = true;
      }
      clearBtn.hidden = currentActiveFlag <= 0;
    }

    const liveFlagIcons =
      (window.onigiriReviewerFlagIcons && typeof window.onigiriReviewerFlagIcons === "object")
        ? window.onigiriReviewerFlagIcons
        : {};
    const flagButtons = [];
    flags.forEach((f) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "rm-flag-btn";
      btn.setAttribute("aria-label", f.label);
      btn.setAttribute("aria-pressed", Number(f.index) === currentActiveFlag ? "true" : "false");
      const flagColor = f.color || "var(--flag-" + f.index + ", " + (FLAG_FALLBACK_COLORS[f.index] || "#ff5a5f") + ")";
      const iconUrl = f.iconUrl || liveFlagIcons[String(f.index)] || "";
      btn.style.setProperty("--rm-flag-color", flagColor);
      if (Number(f.index) === currentActiveFlag) btn.classList.add("is-active");
      btn.appendChild(makeFlagGlyph(iconUrl, Number(f.index) === currentActiveFlag));

      btn.addEventListener("pointerenter", () => updateFlagStatus(f.index));
      btn.addEventListener("focus", () => updateFlagStatus(f.index));
      btn.addEventListener("pointerleave", () => updateFlagStatus(null));
      btn.addEventListener("blur", () => updateFlagStatus(null));

      btn.addEventListener("click", () => {
        const nextFlag = currentActiveFlag === Number(f.index) ? 0 : Number(f.index);
        currentActiveFlag = nextFlag;
        flagButtons.forEach((item) => {
          const on = item.index === currentActiveFlag;
          item.btn.classList.toggle("is-active", on);
          item.btn.setAttribute("aria-pressed", on ? "true" : "false");
          item.btn.replaceChildren(makeFlagGlyph(item.iconUrl, on));
        });
        updateFlagStatus(null);
        triggerAction("flag:" + f.index, { delayMs: 180 });
      });

      flagButtons.push({ index: Number(f.index), btn, iconUrl });
      flagRow.appendChild(btn);
    });

    clearBtn.addEventListener("click", () => {
      currentActiveFlag = 0;
      flagButtons.forEach((item) => {
        item.btn.classList.remove("is-active");
        item.btn.setAttribute("aria-pressed", "false");
        item.btn.replaceChildren(makeFlagGlyph(item.iconUrl, false));
      });
      updateFlagStatus(null);
      triggerAction("flag:0", { delayMs: 150 });
    });

    updateFlagStatus(null);
    flagDock.append(flagHeader, flagRow);
    panel.appendChild(flagDock);

    // ── 2. Quick Actions Grid (Mark, Auto Advance, Options, Info + Prev) ──
    const quickGrid = document.createElement("div");
    quickGrid.className = "rm-quick-grid rm-section";
    quickGrid.style.setProperty("--rm-stagger", "1");

    function makeQuickBtn(opts) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "rm-quick-btn" + (opts.cls ? " " + opts.cls : "");
      if (typeof opts.pressed === "boolean") {
        btn.setAttribute("aria-pressed", opts.pressed ? "true" : "false");
      }
      const iconEl = opts.icon();
      const lbl = document.createElement("span");
      lbl.className = "rm-quick-label";
      lbl.textContent = opts.label;
      btn.append(iconEl, lbl);
      const kbd = makeKbd(opts.shortcut, false);
      if (kbd) btn.appendChild(kbd);
      return btn;
    }

    // Mark Note
    const markBtn = makeQuickBtn({
      cls: "is-mark",
      pressed: marked,
      icon: () => ICONS.star(marked),
      label: labels.markNote || "Mark",
      shortcut: shortcuts.mark
    });
    markBtn.addEventListener("click", () => {
      marked = !marked;
      markBtn.setAttribute("aria-pressed", marked ? "true" : "false");
      markBtn.replaceChild(ICONS.star(marked), markBtn.firstChild);
      triggerAction("mark", { delayMs: 180 });
    });
    quickGrid.appendChild(markBtn);

    // Auto Advance
    const autoBtn = makeQuickBtn({
      cls: "is-auto",
      pressed: autoAdvance,
      icon: () => ICONS.bolt(),
      label: labels.autoAdvance || "Auto",
      shortcut: shortcuts.autoAdvance
    });
    autoBtn.addEventListener("click", () => {
      autoAdvance = !autoAdvance;
      autoBtn.setAttribute("aria-pressed", autoAdvance ? "true" : "false");
      triggerAction("auto_advance", { delayMs: 180 });
    });
    quickGrid.appendChild(autoBtn);

    // Deck Options
    const optionsBtn = makeQuickBtn({
      icon: () => ICONS.sliders(),
      label: labels.options || "Options",
      shortcut: shortcuts.options
    });
    optionsBtn.addEventListener("click", () => triggerAction("options"));
    quickGrid.appendChild(optionsBtn);

    // Card Info + optional Prev Card Info
    const infoCell = document.createElement("div");
    infoCell.className = "rm-quick-cell";
    const infoBtn = makeQuickBtn({
      icon: () => ICONS.info(),
      label: labels.cardInfo || "Card Info",
      shortcut: shortcuts.cardInfo
    });
    infoBtn.addEventListener("click", () => triggerAction("card_info"));
    infoCell.appendChild(infoBtn);

    if (hasPrev) {
      const prevBtn = document.createElement("button");
      prevBtn.type = "button";
      prevBtn.className = "rm-prev-info-btn";
      prevBtn.setAttribute(
        "aria-label",
        (labels.previousCardInfo || "Previous Card Info") +
          (shortcuts.previousCardInfo ? " (" + shortcuts.previousCardInfo + ")" : "")
      );
      prevBtn.title =
        (labels.previousCardInfo || "Previous Card Info") +
        (shortcuts.previousCardInfo ? " · " + shortcuts.previousCardInfo : "");
      prevBtn.appendChild(ICONS.history());
      prevBtn.addEventListener("click", () => triggerAction("prev_card_info"));
      infoCell.appendChild(prevBtn);
    }
    quickGrid.appendChild(infoCell);
    panel.appendChild(quickGrid);

    // ── 3. Card & Note Actions ──
    const actionsSection = document.createElement("div");
    actionsSection.className = "rm-dock rm-section-list rm-section";
    actionsSection.style.setProperty("--rm-stagger", "2");

    function makeSplitRow(iconFn, titleText, leftLabel, leftShortcut, leftAct, rightLabel, rightShortcut, rightAct) {
      const row = document.createElement("div");
      row.className = "rm-split-row";

      const left = document.createElement("div");
      left.className = "rm-split-left";
      left.appendChild(iconFn());
      const title = document.createElement("span");
      title.className = "rm-split-title";
      title.textContent = titleText;
      left.appendChild(title);

      const pills = document.createElement("div");
      pills.className = "rm-split-pills";

      [
        { label: leftLabel, kbd: leftShortcut, act: leftAct },
        { label: rightLabel, kbd: rightShortcut, act: rightAct }
      ].forEach((spec) => {
        const pill = document.createElement("button");
        pill.type = "button";
        pill.className = "rm-mini-pill";
        const span = document.createElement("span");
        span.textContent = spec.label;
        pill.appendChild(span);
        const kbd = makeKbd(spec.kbd, true);
        if (kbd) pill.appendChild(kbd);
        pill.addEventListener("click", () => triggerAction(spec.act));
        pills.appendChild(pill);
      });

      row.append(left, pills);
      return row;
    }

    function makeActionRow(opts) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "rm-item-btn" + (opts.danger ? " is-danger" : "");
      btn.appendChild(opts.icon());
      const lbl = document.createElement("span");
      lbl.className = "rm-item-label";
      lbl.textContent = opts.label;
      btn.appendChild(lbl);
      const kbd = makeKbd(opts.shortcut, false);
      if (kbd) btn.appendChild(kbd);
      btn.addEventListener("click", () => triggerAction(opts.action));
      return btn;
    }

    actionsSection.appendChild(
      makeSplitRow(
        ICONS.bury,
        labels.buryGroup || "Bury",
        labels.cardWord || "Card",
        shortcuts.buryCard,
        "bury_card",
        labels.noteWord || "Note",
        shortcuts.buryNote,
        "bury_note"
      )
    );
    actionsSection.appendChild(
      makeSplitRow(
        ICONS.suspend,
        labels.suspendGroup || "Suspend",
        labels.cardWord || "Card",
        shortcuts.suspendCard,
        "suspend_card",
        labels.noteWord || "Note",
        shortcuts.suspendNote,
        "suspend_note"
      )
    );

    const div1 = document.createElement("div");
    div1.className = "rm-divider";
    actionsSection.appendChild(div1);

    actionsSection.appendChild(
      makeActionRow({
        icon: ICONS.calendar,
        label: stripTrailingEllipsis(labels.setDueDate) || "Set Due Date",
        shortcut: shortcuts.setDueDate,
        action: "set_due"
      })
    );
    actionsSection.appendChild(
      makeActionRow({
        icon: ICONS.reset,
        label: stripTrailingEllipsis(labels.resetCard) || "Reset Card",
        shortcut: shortcuts.resetCard,
        action: "reset_card"
      })
    );
    actionsSection.appendChild(
      makeActionRow({
        icon: ICONS.copy,
        label: stripTrailingEllipsis(labels.createCopy) || "Create Copy",
        shortcut: shortcuts.createCopy,
        action: "create_copy"
      })
    );
    actionsSection.appendChild(
      makeActionRow({
        icon: ICONS.trash,
        label: stripTrailingEllipsis(labels.deleteNote) || "Delete Note",
        shortcut: shortcuts.deleteNote,
        action: "delete_note",
        danger: true
      })
    );

    panel.appendChild(actionsSection);

    // ── 4. Audio & Voice Dock ──
    const mediaDock = document.createElement("div");
    mediaDock.className = "rm-dock rm-section";
    mediaDock.style.setProperty("--rm-stagger", "3");

    const mediaRow = document.createElement("div");
    mediaRow.className = "rm-media-row";

    function makeMediaBtn(opts) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "rm-media-btn";
      if (opts.title) {
        btn.title = opts.title + (opts.shortcut ? " (" + opts.shortcut + ")" : "");
      }
      btn.appendChild(opts.icon());
      if (opts.label) {
        const lbl = document.createElement("span");
        lbl.className = "rm-media-label";
        lbl.textContent = opts.label;
        btn.appendChild(lbl);
      }
      const kbd = makeKbd(opts.shortcut, true);
      if (kbd && opts.showKbd) btn.appendChild(kbd);
      btn.addEventListener("click", () => {
        triggerAction(opts.action, { keepOpen: Boolean(opts.keepOpen), pulseEl: btn });
      });
      return btn;
    }

    mediaRow.append(
      makeMediaBtn({
        icon: ICONS.rewind,
        label: "-5s",
        title: labels.audioBack || "Audio -5s",
        shortcut: shortcuts.audioBack,
        action: "seek_back",
        keepOpen: true
      }),
      makeMediaBtn({
        icon: ICONS.replay,
        label: labels.replayShort || "Replay",
        title: labels.replayAudio || "Replay Audio",
        shortcut: shortcuts.replayAudio,
        action: "replay_audio",
        keepOpen: true
      }),
      makeMediaBtn({
        icon: ICONS.pause,
        label: "",
        title: labels.pauseAudio || "Pause Audio",
        shortcut: shortcuts.pauseAudio,
        action: "pause_audio",
        keepOpen: true,
        showKbd: true
      }),
      makeMediaBtn({
        icon: ICONS.forward,
        label: "+5s",
        title: labels.audioForward || "Audio +5s",
        shortcut: shortcuts.audioForward,
        action: "seek_fwd",
        keepOpen: true
      })
    );

    const voiceRow = document.createElement("div");
    voiceRow.className = "rm-voice-row";
    voiceRow.append(
      makeMediaBtn({
        icon: ICONS.mic,
        label: labels.recordShort || "Record",
        title: labels.recordVoice || "Record Own Voice",
        shortcut: shortcuts.recordVoice,
        action: "record_voice",
        keepOpen: false,
        showKbd: true
      }),
      makeMediaBtn({
        icon: ICONS.volume,
        label: labels.playVoiceShort || "Replay",
        title: labels.replayVoice || "Replay Own Voice",
        shortcut: shortcuts.replayVoice,
        action: "replay_voice",
        keepOpen: true,
        showKbd: true
      })
    );

    mediaDock.append(mediaRow, voiceRow);
    panel.appendChild(mediaDock);

    // ── 5. Third-party Add-on Extensions (only if present) ──
    if (customItems.length > 0) {
      const extSection = document.createElement("div");
      extSection.className = "rm-dock rm-section-list rm-section";
      extSection.style.setProperty("--rm-stagger", "4");

      const heading = document.createElement("div");
      heading.className = "rm-custom-heading";
      heading.textContent = labels.extensions || "Add-ons";
      extSection.appendChild(heading);

      function buildCustomItem(item, container) {
        if (item.type === "separator") {
          const hr = document.createElement("div");
          hr.className = "rm-divider";
          container.appendChild(hr);
          return;
        }
        if (item.type === "submenu" && Array.isArray(item.items)) {
          const toggle = document.createElement("button");
          toggle.type = "button";
          toggle.className = "rm-item-btn rm-submenu-toggle";
          toggle.setAttribute("aria-expanded", "false");
          if (item.disabled) toggle.disabled = true;

          const lbl = document.createElement("span");
          lbl.className = "rm-item-label";
          lbl.textContent = item.label || "";
          toggle.append(lbl, ICONS.chevron());

          const subList = document.createElement("div");
          subList.className = "rm-submenu-list";
          item.items.forEach((child) => buildCustomItem(child, subList));

          toggle.addEventListener("click", () => {
            const nextOpen = toggle.getAttribute("aria-expanded") !== "true";
            toggle.setAttribute("aria-expanded", nextOpen ? "true" : "false");
            subList.classList.toggle("is-open", nextOpen);
          });
          container.append(toggle, subList);
          return;
        }
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "rm-item-btn";
        if (item.disabled) btn.disabled = true;
        if (item.checkable) {
          const check = document.createElement("span");
          check.className = "rm-check-dot";
          check.textContent = item.checked ? "✓" : "";
          btn.appendChild(check);
        }
        const lbl = document.createElement("span");
        lbl.className = "rm-item-label";
        lbl.textContent = item.label || "";
        btn.appendChild(lbl);
        if (item.shortcut) {
          const kbd = makeKbd(item.shortcut, false);
          if (kbd) btn.appendChild(kbd);
        }
        btn.addEventListener("click", () => {
          closeImmediate(true);
          sendCmd("onigiri_more_menu:custom:" + String(item.id));
        });
        container.appendChild(btn);
      }

      customItems.forEach((item) => buildCustomItem(item, extSection));
      panel.appendChild(extSection);
    }
  }

  function syncEnvironment() {
    if (!host || !root) return;
    host.classList.toggle("night-mode", isNightMode(currentData && currentData.dark));
    root.classList.toggle("is-rtl", isRtl());
  }

  function open(data, focusFirst) {
    ensureHost();
    if (!panel) return;
    if (closeTimer) {
      clearTimeout(closeTimer);
      closeTimer = null;
    }
    if (actionTimer) {
      clearTimeout(actionTimer);
      actionTimer = null;
    }
    renderPanel(data);
    syncEnvironment();

    panel.classList.remove("is-closing");
    panel.classList.add("is-visible");
    // Restart entrance animation cleanly
    panel.classList.remove("is-open");
    void panel.offsetWidth;
    panel.classList.add("is-open");

    backdrop.classList.add("is-active");
    state = "open";

    if (focusFirst) {
      const items = focusableButtons();
      if (items.length) {
        items[0].focus({ preventScroll: true });
      }
    }
  }

  function closeImmediate(skipNotify) {
    if (closeTimer) {
      clearTimeout(closeTimer);
      closeTimer = null;
    }
    if (actionTimer) {
      clearTimeout(actionTimer);
      actionTimer = null;
    }
    if (!panel) {
      state = "closed";
      return;
    }
    panel.classList.remove("is-open", "is-closing", "is-visible");
    backdrop.classList.remove("is-active");
    state = "closed";
    if (!skipNotify) {
      sendCmd("onigiri_more_menu:closed");
    }
  }

  function close() {
    if (state === "closed" || !panel) return;
    if (state === "closing") return;
    if (actionTimer) {
      clearTimeout(actionTimer);
      actionTimer = null;
    }
    state = "closing";
    backdrop.classList.remove("is-active");
    panel.classList.remove("is-open");
    panel.classList.add("is-closing");
    closeTimer = setTimeout(() => {
      closeTimer = null;
      if (state === "closing") {
        panel.classList.remove("is-closing", "is-visible");
        state = "closed";
      }
    }, 135);
  }

  function requestClose() {
    if (state === "closed" || state === "closing") return;
    close();
    sendCmd("onigiri_more_menu:closed");
  }

  function observeTheme() {
    const observer = new MutationObserver(() => {
      if (state !== "closed") syncEnvironment();
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "dir"]
    });
    if (document.body) {
      observer.observe(document.body, {
        attributes: true,
        attributeFilter: ["class", "dir"]
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", observeTheme, { once: true });
  } else {
    observeTheme();
  }

  window.OnigiriReviewerMoreMenu = {
    open,
    close,
    closeImmediate,
    isOpen: () => state === "open"
  };
})();
