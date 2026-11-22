(function () {
  "use strict";

  if (window.OnigimonHUD) return;

  const HOST_ID = "onigimon-hud-host";
  const STYLE_ID = "onigimon-hud-style";
  const SUPPRESS_STYLE_ID = "onigimon-ankimon-suppress";

  const POKEBALL_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="9"/>' +
    '<path d="M3 12h6.2M14.8 12H21"/>' +
    '<circle cx="12" cy="12" r="2.8"/>' +
    "</svg>";

  const BAG_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M6 8h12l1 12a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L6 8Z"/>' +
    '<path d="M9 8V6a3 3 0 0 1 6 0v2"/>' +
    '<path d="M9 13h6"/>' +
    "</svg>";

  const GRIP_SVG =
    '<svg viewBox="0 0 10 16" fill="currentColor" aria-hidden="true">' +
    '<circle cx="2.5" cy="3" r="1.2"/><circle cx="7.5" cy="3" r="1.2"/>' +
    '<circle cx="2.5" cy="8" r="1.2"/><circle cx="7.5" cy="8" r="1.2"/>' +
    '<circle cx="2.5" cy="13" r="1.2"/><circle cx="7.5" cy="13" r="1.2"/>' +
    "</svg>";

  const CYCLE_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M21 12a9 9 0 0 0-15-6.7L3 8"/>' +
    '<path d="M3 3v5h5"/>' +
    '<path d="M3 12a9 9 0 0 0 15 6.7L21 16"/>' +
    '<path d="M16 16h5v5"/>' +
    "</svg>";

  const MINIMIZE_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M6 12h12"/>' +
    "</svg>";

  const STATUS_STYLES = {
    burn: { label: "BRN", bg: "rgba(232, 106, 51, 0.16)", fg: "#c84f1d", darkFg: "#ff9b70" },
    burned: { label: "BRN", bg: "rgba(232, 106, 51, 0.16)", fg: "#c84f1d", darkFg: "#ff9b70" },
    brn: { label: "BRN", bg: "rgba(232, 106, 51, 0.16)", fg: "#c84f1d", darkFg: "#ff9b70" },
    poison: { label: "PSN", bg: "rgba(155, 89, 182, 0.18)", fg: "#7b3d96", darkFg: "#d59ef0" },
    poisoned: { label: "PSN", bg: "rgba(155, 89, 182, 0.18)", fg: "#7b3d96", darkFg: "#d59ef0" },
    psn: { label: "PSN", bg: "rgba(155, 89, 182, 0.18)", fg: "#7b3d96", darkFg: "#d59ef0" },
    tox: { label: "TOX", bg: "rgba(155, 89, 182, 0.22)", fg: "#6c2c88", darkFg: "#e0aaf8" },
    paralysis: { label: "PAR", bg: "rgba(218, 165, 32, 0.18)", fg: "#9a6f00", darkFg: "#f2ca52" },
    paralyzed: { label: "PAR", bg: "rgba(218, 165, 32, 0.18)", fg: "#9a6f00", darkFg: "#f2ca52" },
    par: { label: "PAR", bg: "rgba(218, 165, 32, 0.18)", fg: "#9a6f00", darkFg: "#f2ca52" },
    sleep: { label: "SLP", bg: "rgba(110, 128, 152, 0.18)", fg: "#4a5c73", darkFg: "#b7c8de" },
    asleep: { label: "SLP", bg: "rgba(110, 128, 152, 0.18)", fg: "#4a5c73", darkFg: "#b7c8de" },
    slp: { label: "SLP", bg: "rgba(110, 128, 152, 0.18)", fg: "#4a5c73", darkFg: "#b7c8de" },
    freeze: { label: "FRZ", bg: "rgba(74, 174, 219, 0.18)", fg: "#1b749c", darkFg: "#8cd6f5" },
    frozen: { label: "FRZ", bg: "rgba(74, 174, 219, 0.18)", fg: "#1b749c", darkFg: "#8cd6f5" },
    frz: { label: "FRZ", bg: "rgba(74, 174, 219, 0.18)", fg: "#1b749c", darkFg: "#8cd6f5" },
    fainted: { label: "FNT", bg: "rgba(207, 85, 76, 0.16)", fg: "#b53f36", darkFg: "#f09088" },
  };

  const TYPE_COLORS = {
    normal: "#8d8f7e",
    fire: "#dc6b3c",
    water: "#4c89d9",
    electric: "#cfa01d",
    grass: "#4e9d59",
    ice: "#55adc4",
    fighting: "#b84b44",
    poison: "#9654a8",
    ground: "#b88f4c",
    flying: "#788cd9",
    psychic: "#d95d87",
    bug: "#84a334",
    rock: "#a18c4d",
    ghost: "#6b5ca5",
    dragon: "#6354d6",
    dark: "#695b51",
    steel: "#7a8ea3",
    fairy: "#d1739d",
  };

  let enabled = Boolean(window.onigimonHudEnabled);
  let lastPayload = null;
  let userHidden = undefined;
  let collapsed = false;
  let bagOpen = false;
  let customPosition = null; // null = default bottom-center, or { x: 0..100, y: 0..100 }
  let dragState = null;
  let suppressExpandClick = false;
  let els = null;
  let themeObserver = null;

  function labels() {
    const src =
      window.onigimonHudLabels && typeof window.onigimonHudLabels === "object"
        ? window.onigimonHudLabels
        : {};
    return {
      catchLabel: src.catchLabel || "Catch",
      defeatLabel: src.defeatLabel || "Defeat",
      cycleTeam: src.cycleTeam || "Switch companion",
      hideHud: src.hideHud || "Minimize HUD",
      showHud: src.showHud || "Onigimon",
      fainted: src.fainted || "Fainted",
      itemsTitle: src.itemsTitle || "Items",
      itemsEmpty: src.itemsEmpty || "No items in your bag yet.",
      dragHint: src.dragHint || "Drag to move · Double-click to reset",
      roundLabel: src.roundLabel || "Round",
    };
  }

  function isNightMode(payload) {
    if (payload && typeof payload.night_mode === "boolean") {
      return payload.night_mode;
    }
    const root = document.documentElement;
    const body = document.body;
    return [root, body].some(
      (el) =>
        el &&
        (el.classList.contains("night-mode") ||
          el.classList.contains("nightMode") ||
          el.classList.contains("night_mode"))
    );
  }

  function parseHexRgb(hex) {
    const raw = String(hex || "").trim();
    const m = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.exec(raw);
    if (!m) return null;
    let body = m[1];
    if (body.length === 3) {
      body = body[0] + body[0] + body[1] + body[1] + body[2] + body[2];
    }
    return {
      r: parseInt(body.slice(0, 2), 16),
      g: parseInt(body.slice(2, 4), 16),
      b: parseInt(body.slice(4, 6), 16),
    };
  }

  function relativeLuminance(rgb) {
    const lin = (c) => {
      const s = c / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * lin(rgb.r) + 0.7152 * lin(rgb.g) + 0.0722 * lin(rgb.b);
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function applyAnkimonSuppression(active) {
    const existing = document.getElementById(SUPPRESS_STYLE_ID);
    if (active) {
      if (!existing) {
        const style = document.createElement("style");
        style.id = SUPPRESS_STYLE_ID;
        style.textContent =
          "#ankimon-hud-host { display: none !important; visibility: hidden !important; opacity: 0 !important; pointer-events: none !important; }";
        (document.head || document.documentElement).appendChild(style);
      }
      if (window.__ankimonHud && typeof window.__ankimonHud.clear === "function") {
        try {
          window.__ankimonHud.clear();
        } catch (_) {}
      }
    } else if (existing) {
      existing.remove();
    }
  }

  function sendCmd(cmd) {
    if (typeof window.pycmd === "function") {
      try {
        window.pycmd(cmd);
      } catch (_) {}
    }
  }

  function hpLevel(hp, maxHp) {
    const pct = maxHp > 0 ? (hp / maxHp) * 100 : 0;
    if (pct <= 25) return "low";
    if (pct <= 50) return "mid";
    return "high";
  }

  function applyCustomAppearance(payload) {
    if (!els || !els.host || !els.shell) return;
    const night = isNightMode(payload);
    els.host.classList.toggle("night-mode", night);

    const styleCfg = (payload && payload.style) || {};
    const mode =
      styleCfg.mode === "minimal" || styleCfg.mode === "war" ? styleCfg.mode : "battle";
    const isStatic = styleCfg.motion === "static";
    const scalePct = clamp(Number(styleCfg.scale) || 100, 75, 135);
    const rawOpacity = styleCfg.opacity;
    const opacityPct = clamp(
      rawOpacity === undefined || rawOpacity === null || rawOpacity === ""
        ? 88
        : Number(rawOpacity),
      0,
      100
    );
    const shadowEnabled = styleCfg.shadow !== false;

    els.shell.setAttribute("data-mode", mode);
    els.shell.classList.toggle("is-static", isStatic);
    els.shell.classList.toggle("has-no-shadow", !shadowEnabled || opacityPct <= 0);
    els.shell.style.setProperty("--oh-scale", String(scalePct / 100));

    const hex = night
      ? styleCfg.bg_color_dark || "#202124"
      : styleCfg.bg_color_light || "#ffffff";
    const rgb = parseHexRgb(hex) || (night ? { r: 32, g: 33, b: 36 } : { r: 255, g: 255, b: 255 });
    const alpha = +(opacityPct / 100).toFixed(3);
    const hoverAlpha = +(Math.min(1, alpha + 0.08 * Math.max(0.25, alpha))).toFixed(3);
    const blurPx = alpha <= 0.01 || alpha >= 0.99 ? 0 : Math.round(Math.sin(alpha * Math.PI) * 14);
    const blurValue = blurPx > 0 ? `blur(${blurPx}px) saturate(135%)` : "none";

    // Choose crisp text ink: follows custom background color when opaque enough,
    // otherwise follows Anki's light/dark theme so text stays readable over the card.
    const isLightSurface = opacityPct >= 40 ? relativeLuminance(rgb) > 0.42 : !night;
    const borderRgb = isLightSurface ? "17, 24, 39" : "255, 255, 255";
    const borderAlpha = +(0.12 * alpha).toFixed(3);
    const borderStrongAlpha = +(0.22 * alpha).toFixed(3);
    const subtleAlpha = +((isLightSurface ? 0.065 : 0.085) * alpha).toFixed(3);
    const dividerAlpha = +(0.11 * alpha).toFixed(3);
    const shadowValue =
      !shadowEnabled || alpha <= 0.01
        ? "none"
        : isLightSurface
          ? `0 10px 28px rgba(15, 23, 42, ${(0.12 * alpha).toFixed(3)}), 0 1px 3px rgba(15, 23, 42, ${(0.07 * alpha).toFixed(3)})`
          : `0 14px 34px rgba(0, 0, 0, ${(0.44 * alpha).toFixed(3)}), 0 1px 3px rgba(0, 0, 0, ${(0.30 * alpha).toFixed(3)})`;

    const surfaceRgba = `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
    const borderRgba = `rgba(${borderRgb}, ${borderAlpha})`;

    els.shell.style.setProperty("--oh-surface", surfaceRgba);
    els.shell.style.setProperty("--oh-surface-hover", `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${hoverAlpha})`);
    els.shell.style.setProperty("--oh-blur", blurValue);
    els.shell.style.setProperty("--oh-bar-border", borderRgba);
    els.shell.style.setProperty("--oh-border", borderRgba);
    els.shell.style.setProperty("--oh-border-strong", `rgba(${borderRgb}, ${borderStrongAlpha})`);
    els.shell.style.setProperty("--oh-surface-subtle", `rgba(${borderRgb}, ${subtleAlpha})`);
    els.shell.style.setProperty("--oh-divider", `rgba(${borderRgb}, ${dividerAlpha})`);
    els.shell.style.setProperty("--oh-shadow", shadowValue);

    if (isLightSurface) {
      els.shell.style.setProperty("--oh-ink", "#1e2022");
      els.shell.style.setProperty("--oh-muted", "#5c6066");
      els.shell.style.setProperty("--oh-faint", "#858990");
      els.shell.style.setProperty("--oh-track", "rgba(17, 24, 39, 0.11)");
    } else {
      els.shell.style.setProperty("--oh-ink", "#f1f2f4");
      els.shell.style.setProperty("--oh-muted", "#a5aab2");
      els.shell.style.setProperty("--oh-faint", "#7e838c");
      els.shell.style.setProperty("--oh-track", "rgba(255, 255, 255, 0.14)");
    }

    [els.bar, els.collapsedPill].forEach((node) => {
      if (!node || !node.style) return;
      node.style.background = surfaceRgba;
      node.style.backdropFilter = blurValue;
      node.style.webkitBackdropFilter = blurValue;
      node.style.borderColor = borderRgba;
      node.style.boxShadow = shadowValue;
    });

    if (styleCfg.position && typeof styleCfg.position === "object") {
      const px = Number(styleCfg.position.x);
      const py = Number(styleCfg.position.y);
      if (Number.isFinite(px) && Number.isFinite(py)) {
        customPosition = { x: clamp(px, 0, 100), y: clamp(py, 0, 100) };
      } else {
        customPosition = null;
      }
    } else if (styleCfg.position === null) {
      customPosition = null;
    }
  }

  function applyShellPosition() {
    if (!els || !els.shell) return;
    if (!customPosition) {
      els.shell.classList.remove("is-positioned");
      els.shell.style.removeProperty("left");
      els.shell.style.removeProperty("top");
      syncBagDirection();
      return;
    }
    const vw = window.innerWidth || 1000;
    const vh = window.innerHeight || 700;
    const activeEl = collapsed ? els.collapsedPill : els.bar;
    const rect =
      activeEl && typeof activeEl.getBoundingClientRect === "function"
        ? activeEl.getBoundingClientRect()
        : { width: 320, height: 56 };
    const margin = 8;
    const maxX = Math.max(margin, vw - (rect.width || 320) - margin);
    const maxY = Math.max(margin, vh - (rect.height || 56) - margin);
    const left = margin + (customPosition.x / 100) * Math.max(0, maxX - margin);
    const top = margin + (customPosition.y / 100) * Math.max(0, maxY - margin);

    els.shell.classList.add("is-positioned");
    els.shell.style.left = Math.round(clamp(left, margin, maxX)) + "px";
    els.shell.style.top = Math.round(clamp(top, margin, maxY)) + "px";
    syncBagDirection();
  }

  function syncBagDirection() {
    if (!els || !els.shell) return;
    if (!bagOpen) return;
    const vw = window.innerWidth || 1000;
    const rect =
      els.bar && typeof els.bar.getBoundingClientRect === "function"
        ? els.bar.getBoundingClientRect()
        : { top: 400, left: 200 };
    els.shell.classList.toggle("is-bag-below", rect.top < 250);
    els.shell.classList.toggle("is-bag-align-right", vw - (rect.left || 0) < 340);
  }

  function startDrag(event, sourceEl) {
    if (!els || !els.shell) return;
    if (event.button !== undefined && event.button !== 0) return;
    // Do not start drag from interactive buttons inside the bar (unless it's the collapsed pill itself).
    if (sourceEl === els.bar && event.target && event.target.closest) {
      if (event.target.closest("button, .oh-bag-panel")) {
        return;
      }
    }

    const activeEl = collapsed ? els.collapsedPill : els.bar;
    const rect =
      activeEl && typeof activeEl.getBoundingClientRect === "function"
        ? activeEl.getBoundingClientRect()
        : { left: 100, top: 100, width: 320, height: 56 };

    dragState = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originLeft: rect.left,
      originTop: rect.top,
      width: rect.width || 320,
      height: rect.height || 56,
      moved: false,
      sourceEl,
    };

    if (sourceEl && typeof sourceEl.setPointerCapture === "function" && event.pointerId != null) {
      try {
        sourceEl.setPointerCapture(event.pointerId);
      } catch (_) {}
    }
  }

  function onDragMove(event) {
    if (!dragState || !els || !els.shell) return;
    if (dragState.pointerId != null && event.pointerId != null && event.pointerId !== dragState.pointerId) {
      return;
    }
    const dx = event.clientX - dragState.startX;
    const dy = event.clientY - dragState.startY;
    if (!dragState.moved) {
      if (Math.hypot(dx, dy) < 4) return;
      dragState.moved = true;
      els.shell.classList.add("is-dragging", "is-positioned");
    }

    const vw = window.innerWidth || 1000;
    const vh = window.innerHeight || 700;
    const margin = 8;
    const maxX = Math.max(margin, vw - dragState.width - margin);
    const maxY = Math.max(margin, vh - dragState.height - margin);
    const nextLeft = clamp(dragState.originLeft + dx, margin, maxX);
    const nextTop = clamp(dragState.originTop + dy, margin, maxY);

    els.shell.style.left = Math.round(nextLeft) + "px";
    els.shell.style.top = Math.round(nextTop) + "px";
    dragState.lastLeft = nextLeft;
    dragState.lastTop = nextTop;
    syncBagDirection();
  }

  function endDrag(event) {
    if (!dragState || !els || !els.shell) return;
    if (dragState.pointerId != null && event.pointerId != null && event.pointerId !== dragState.pointerId) {
      return;
    }
    const state = dragState;
    dragState = null;

    if (
      state.sourceEl &&
      typeof state.sourceEl.releasePointerCapture === "function" &&
      state.pointerId != null
    ) {
      try {
        state.sourceEl.releasePointerCapture(state.pointerId);
      } catch (_) {}
    }

    els.shell.classList.remove("is-dragging");
    if (!state.moved) return;

    if (state.sourceEl === els.collapsedPill) {
      suppressExpandClick = true;
      window.setTimeout(() => {
        suppressExpandClick = false;
      }, 60);
    }

    const vw = window.innerWidth || 1000;
    const vh = window.innerHeight || 700;
    const margin = 8;
    const spanX = Math.max(1, vw - state.width - margin * 2);
    const spanY = Math.max(1, vh - state.height - margin * 2);
    const pctX = Number(clamp(((state.lastLeft - margin) / spanX) * 100, 0, 100).toFixed(2));
    const pctY = Number(clamp(((state.lastTop - margin) / spanY) * 100, 0, 100).toFixed(2));
    customPosition = { x: pctX, y: pctY };
    sendCmd(`onigimon_hud:set_position:${pctX}:${pctY}`);
  }

  function buildFighterNodes(side) {
    const root = document.createElement("div");
    root.className = "oh-fighter oh-fighter--" + side;

    const spriteWrap = document.createElement("div");
    spriteWrap.className = "oh-sprite-wrap";

    const sprite = document.createElement("img");
    sprite.className = "oh-sprite";
    sprite.alt = "";
    sprite.draggable = false;
    spriteWrap.appendChild(sprite);

    const deltaLayer = document.createElement("div");
    deltaLayer.className = "oh-delta-layer";
    spriteWrap.appendChild(deltaLayer);

    const info = document.createElement("div");
    info.className = "oh-info";

    const header = document.createElement("div");
    header.className = "oh-header";

    const owned = document.createElement("span");
    owned.className = "oh-owned";
    owned.innerHTML = POKEBALL_SVG;
    owned.hidden = true;

    const idSpan = document.createElement("span");
    idSpan.className = "oh-meta-muted";
    idSpan.hidden = true;

    const name = document.createElement("span");
    name.className = "oh-name";

    const shiny = document.createElement("span");
    shiny.className = "oh-shiny";
    shiny.textContent = "✦";
    shiny.hidden = true;

    const genSpan = document.createElement("span");
    genSpan.className = "oh-meta-muted";
    genSpan.hidden = true;

    const level = document.createElement("span");
    level.className = "oh-level";
    level.hidden = true;

    const badges = document.createElement("span");
    badges.className = "oh-badges";

    header.append(owned, idSpan, name, shiny, genSpan, level, badges);

    const typesRow = document.createElement("div");
    typesRow.className = "oh-types";
    typesRow.hidden = true;

    const hpRow = document.createElement("div");
    hpRow.className = "oh-hp-row";

    const hpProgress = document.createElement("progress");
    hpProgress.className = "oh-progress";
    hpProgress.max = 100;
    hpProgress.value = 100;

    const hpText = document.createElement("span");
    hpText.className = "oh-hp-text";

    hpRow.append(hpProgress, hpText);

    info.append(header, typesRow, hpRow);

    let xpRow = null;
    let xpProgress = null;
    let xpText = null;
    if (side === "main") {
      xpRow = document.createElement("div");
      xpRow.className = "oh-xp-row";

      xpProgress = document.createElement("progress");
      xpProgress.className = "oh-progress oh-progress--xp";
      xpProgress.max = 100;
      xpProgress.value = 0;

      xpText = document.createElement("span");
      xpText.className = "oh-xp-text";
      xpText.hidden = true;

      xpRow.append(xpProgress, xpText);
      info.append(xpRow);
    }

    root.append(spriteWrap, info);

    return {
      root,
      spriteWrap,
      sprite,
      deltaLayer,
      info,
      owned,
      idSpan,
      name,
      shiny,
      genSpan,
      level,
      badges,
      typesRow,
      hpRow,
      hpProgress,
      hpText,
      xpRow,
      xpProgress,
      xpText,
      lastSpriteUrl: "",
    };
  }

  function ensureHost() {
    if (els && els.host && els.host.isConnected) {
      applyCustomAppearance(lastPayload);
      return els;
    }

    const parent = document.body || document.documentElement;
    if (!parent) return null;

    let host = document.getElementById(HOST_ID);
    if (!host) {
      host = document.createElement("div");
      host.id = HOST_ID;
      parent.appendChild(host);
    }

    host.style.cssText = [
      "all: initial !important",
      "position: fixed !important",
      "inset: 0 !important",
      "display: block !important",
      "width: auto !important",
      "height: auto !important",
      "margin: 0 !important",
      "padding: 0 !important",
      "border: 0 !important",
      "background: transparent !important",
      "z-index: 2147482900 !important",
      "pointer-events: none !important",
      "contain: layout style paint !important",
    ].join(";");

    const shadow = host.shadowRoot || host.attachShadow({ mode: "open" });
    shadow.textContent = "";

    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = String(window.onigimonHudCssText || "");
    shadow.appendChild(style);

    const shell = document.createElement("div");
    shell.className = "oh-shell";
    shell.setAttribute("role", "region");
    shell.setAttribute("aria-label", "Onigimon Battle HUD");

    const stage = document.createElement("div");
    stage.className = "oh-stage";

    const bar = document.createElement("div");
    bar.className = "oh-bar";

    const mainRow = document.createElement("div");
    mainRow.className = "oh-main-row";

    const grip = document.createElement("span");
    grip.className = "oh-grip";
    grip.innerHTML = GRIP_SVG;
    grip.addEventListener("dblclick", (e) => {
      e.stopPropagation();
      customPosition = null;
      applyShellPosition();
      sendCmd("onigimon_hud:reset_position");
    });

    const main = buildFighterNodes("main");
    const center = document.createElement("div");
    center.className = "oh-center";
    const enemy = buildFighterNodes("enemy");

    const inlineBagBtn = document.createElement("button");
    inlineBagBtn.type = "button";
    inlineBagBtn.className = "oh-inline-btn";
    inlineBagBtn.innerHTML = BAG_SVG;
    const inlineBagCount = document.createElement("span");
    inlineBagCount.className = "oh-bag-count";
    inlineBagBtn.appendChild(inlineBagCount);
    inlineBagBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleBag();
    });

    mainRow.append(grip, inlineBagBtn, main.root, center, enemy.root);

    const warStrip = document.createElement("div");
    warStrip.className = "oh-war-strip";
    warStrip.hidden = true;

    const tools = document.createElement("div");
    tools.className = "oh-tools";

    const hoverBagBtn = document.createElement("button");
    hoverBagBtn.type = "button";
    hoverBagBtn.className = "oh-tool-btn";
    hoverBagBtn.innerHTML = BAG_SVG;
    hoverBagBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleBag();
    });

    const cycleBtn = document.createElement("button");
    cycleBtn.type = "button";
    cycleBtn.className = "oh-tool-btn";
    cycleBtn.innerHTML = CYCLE_SVG;
    cycleBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      sendCmd("onigimon_hud:cycle_team");
    });

    const minBtn = document.createElement("button");
    minBtn.type = "button";
    minBtn.className = "oh-tool-btn";
    minBtn.innerHTML = MINIMIZE_SVG;
    minBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      bagOpen = false;
      collapsed = true;
      renderVisibility();
    });

    tools.append(hoverBagBtn, cycleBtn, minBtn);

    const bagPanel = document.createElement("div");
    bagPanel.className = "oh-bag-panel";
    bagPanel.setAttribute("role", "dialog");
    bagPanel.hidden = true;

    const bagHead = document.createElement("div");
    bagHead.className = "oh-bag-head";
    const bagTitle = document.createElement("span");
    bagTitle.className = "oh-bag-title";
    const bagCurrencies = document.createElement("div");
    bagCurrencies.className = "oh-bag-currencies";
    const bagClose = document.createElement("button");
    bagClose.type = "button";
    bagClose.className = "oh-bag-close";
    bagClose.textContent = "×";
    bagClose.setAttribute("aria-label", "Close");
    bagClose.addEventListener("click", (e) => {
      e.stopPropagation();
      bagOpen = false;
      renderBagVisibility();
    });
    bagHead.append(bagTitle, bagCurrencies, bagClose);

    const bagBody = document.createElement("div");
    bagPanel.append(bagHead, bagBody);

    bar.append(mainRow, warStrip, tools, bagPanel);
    bar.addEventListener("pointerdown", (e) => startDrag(e, bar));
    bar.addEventListener("pointermove", onDragMove);
    bar.addEventListener("pointerup", endDrag);
    bar.addEventListener("pointercancel", endDrag);

    const collapsedPill = document.createElement("button");
    collapsedPill.type = "button";
    collapsedPill.className = "oh-collapsed-pill";
    collapsedPill.hidden = true;
    collapsedPill.innerHTML = POKEBALL_SVG;
    const collapsedLabel = document.createElement("span");
    const collapsedDot = document.createElement("span");
    collapsedDot.className = "oh-collapsed-dot";
    collapsedPill.append(collapsedLabel, collapsedDot);
    collapsedPill.addEventListener("pointerdown", (e) => startDrag(e, collapsedPill));
    collapsedPill.addEventListener("pointermove", onDragMove);
    collapsedPill.addEventListener("pointerup", endDrag);
    collapsedPill.addEventListener("pointercancel", endDrag);
    collapsedPill.addEventListener("click", (e) => {
      e.stopPropagation();
      if (suppressExpandClick) return;
      collapsed = false;
      renderVisibility();
    });

    const liveRegion = document.createElement("div");
    liveRegion.className = "oh-sr-only";
    liveRegion.setAttribute("aria-live", "polite");

    stage.append(bar, collapsedPill);
    shell.append(stage, liveRegion);
    shadow.appendChild(shell);

    els = {
      host,
      shadow,
      shell,
      stage,
      bar,
      mainRow,
      grip,
      main,
      center,
      enemy,
      inlineBagBtn,
      inlineBagCount,
      warStrip,
      tools,
      hoverBagBtn,
      cycleBtn,
      minBtn,
      bagPanel,
      bagTitle,
      bagCurrencies,
      bagBody,
      collapsedPill,
      collapsedLabel,
      collapsedDot,
      liveRegion,
    };

    applyCustomAppearance(lastPayload);
    installThemeObserver();
    return els;
  }

  function installThemeObserver() {
    if (themeObserver || typeof MutationObserver !== "function") return;
    themeObserver = new MutationObserver(() => {
      applyCustomAppearance(lastPayload);
    });
    if (document.documentElement) {
      themeObserver.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["class"],
      });
    }
    if (document.body) {
      themeObserver.observe(document.body, {
        attributes: true,
        attributeFilter: ["class"],
      });
    }
  }

  function triggerShake(spriteEl) {
    if (!spriteEl || (els && els.shell && els.shell.classList.contains("is-static"))) return;
    spriteEl.classList.remove("is-shaking");
    void spriteEl.offsetWidth;
    spriteEl.classList.add("is-shaking");
    const clear = () => spriteEl.classList.remove("is-shaking");
    spriteEl.addEventListener("animationend", clear, { once: true });
    window.setTimeout(clear, 420);
  }

  function renderBadges(container, status, boosts, night, mode) {
    container.textContent = "";
    const statusKey = String(status || "").toLowerCase();
    const allowStatus = mode === "minimal" ? statusKey === "fainted" : true;
    if (allowStatus && statusKey && statusKey !== "fighting" && STATUS_STYLES[statusKey]) {
      const cfg = STATUS_STYLES[statusKey];
      const chip = document.createElement("span");
      chip.className = "oh-status-chip";
      chip.textContent = cfg.label;
      chip.style.setProperty("--oh-status-bg", cfg.bg);
      chip.style.setProperty("--oh-status-fg", night ? cfg.darkFg : cfg.fg);
      container.appendChild(chip);
    }

    if (mode !== "minimal" && Array.isArray(boosts)) {
      for (const boost of boosts) {
        if (!boost || !boost.label) continue;
        const chip = document.createElement("span");
        chip.className = "oh-boost-chip" + (boost.stage < 0 ? " is-down" : "");
        chip.textContent = boost.label;
        container.appendChild(chip);
      }
    }
  }

  function renderTypes(container, types, show) {
    container.textContent = "";
    if (!show || !Array.isArray(types) || !types.length) {
      container.hidden = true;
      return;
    }
    for (const raw of types) {
      const t = String(raw || "").trim().toLowerCase();
      if (!t) continue;
      const hex = TYPE_COLORS[t] || "#7a8594";
      const rgb = parseHexRgb(hex);
      const chip = document.createElement("span");
      chip.className = "oh-type-chip";
      chip.textContent = t;
      if (rgb) {
        chip.style.setProperty("--oh-type-bg", `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.16)`);
        chip.style.setProperty("--oh-type-fg", hex);
      }
      container.appendChild(chip);
    }
    container.hidden = container.children.length === 0;
  }

  function updateFighter(nodes, data, flags, night, mode) {
    if (!data) {
      nodes.root.hidden = true;
      return;
    }
    nodes.root.hidden = false;

    const isMinimal = mode === "minimal";
    const isWar = mode === "war";

    const hp = Math.max(0, Number(data.hp) || 0);
    const maxHp = Math.max(1, Number(data.max_hp) || 1);
    const isFainted = hp <= 0;
    nodes.root.classList.toggle("is-fainted", isFainted);

    const showSprite = Boolean(data.show_sprite && data.sprite_url);
    nodes.spriteWrap.hidden = !showSprite;
    if (showSprite) {
      if (nodes.lastSpriteUrl !== data.sprite_url) {
        nodes.sprite.src = data.sprite_url;
        nodes.lastSpriteUrl = data.sprite_url;
      }
      nodes.sprite.alt = data.name || "";
      nodes.sprite.style.setProperty("--oh-sprite-flip", data.flip ? "-1" : "1");
      if (data.shake) {
        triggerShake(nodes.sprite);
      }
    }

    nodes.owned.hidden = !(flags.show_owned && data.owned);

    const showId = isWar || (!isMinimal && flags.show_id);
    if (showId && data.pokedex_id != null) {
      nodes.idSpan.textContent = "#" + data.pokedex_id;
      nodes.idSpan.hidden = false;
    } else {
      nodes.idSpan.hidden = true;
    }

    nodes.name.textContent = flags.show_name ? String(data.name || "") : "";
    nodes.name.hidden = !flags.show_name;

    nodes.shiny.hidden = !(data.shiny && data.show_shiny);

    const showGen = isWar || (!isMinimal && flags.show_gen);
    if (showGen && data.generation != null) {
      nodes.genSpan.textContent = "G" + data.generation;
      nodes.genSpan.hidden = false;
    } else {
      nodes.genSpan.hidden = true;
    }

    if (flags.show_level && data.level != null) {
      nodes.level.textContent = "Lv." + data.level;
      nodes.level.hidden = false;
    } else {
      nodes.level.hidden = true;
    }

    const effectiveStatus = isFainted ? "fainted" : data.status;
    renderBadges(
      nodes.badges,
      flags.show_status ? effectiveStatus : "",
      data.boosts,
      night,
      mode
    );

    renderTypes(nodes.typesRow, data.types, isWar);

    const showHpBar = Boolean(flags.show_hp_bars);
    const showHpText = !isMinimal && Boolean(flags.show_hp_text);
    nodes.hpRow.hidden = !showHpBar && !showHpText;

    nodes.hpProgress.hidden = !showHpBar;
    if (showHpBar) {
      nodes.hpProgress.max = maxHp;
      nodes.hpProgress.value = Math.min(hp, maxHp);
      nodes.hpProgress.dataset.level = hpLevel(hp, maxHp);
      nodes.hpProgress.setAttribute(
        "aria-label",
        (data.name || "Pokemon") + " HP " + hp + " / " + maxHp
      );
    }

    nodes.hpText.hidden = !showHpText;
    if (showHpText) {
      const pct = Math.round((hp / maxHp) * 100);
      nodes.hpText.textContent = isWar ? `${hp}/${maxHp} · ${pct}%` : `${hp}/${maxHp}`;
    }

    if (nodes.xpRow) {
      const showXpBar = !isMinimal && Boolean(flags.show_xp_bar);
      const showXpValues = isWar || (!isMinimal && Boolean(flags.show_xp_values));
      nodes.xpRow.hidden = !showXpBar && !showXpValues;
      if (nodes.xpProgress) {
        nodes.xpProgress.hidden = !showXpBar;
        if (showXpBar) {
          const xpNext = Math.max(1, Number(data.xp_next) || 1);
          const xpCur = Math.max(0, Math.min(xpNext, Number(data.xp) || 0));
          nodes.xpProgress.max = xpNext;
          nodes.xpProgress.value = xpCur;
          nodes.xpProgress.setAttribute("aria-label", "XP " + xpCur + " / " + xpNext);
        }
      }
      if (nodes.xpText) {
        nodes.xpText.hidden = !showXpValues;
        if (showXpValues) {
          const xpNext = Math.max(1, Number(data.xp_next) || 1);
          const xpCur = Math.max(0, Number(data.xp) || 0);
          nodes.xpText.textContent = "XP " + xpCur + "/" + xpNext;
        }
      }
    }
  }

  function updateWarStrip(payload, mode) {
    if (!els || !els.warStrip) return;
    if (mode !== "war") {
      els.warStrip.hidden = true;
      els.warStrip.textContent = "";
      return;
    }
    const war = (payload && payload.war) || {};
    const txt = labels();
    els.warStrip.textContent = "";

    const leftGroup = document.createElement("div");
    leftGroup.className = "oh-war-group";

    if (war.cards_per_round) {
      const roundPill = document.createElement("span");
      roundPill.className = "oh-war-pill";
      roundPill.textContent = `${txt.roundLabel} ${war.cards_battle_round || 0}/${war.cards_per_round}`;
      leftGroup.appendChild(roundPill);
    }

    if (war.multiplier != null) {
      const multPill = document.createElement("span");
      multPill.className = "oh-war-pill";
      multPill.textContent = `×${Number(war.multiplier).toFixed(war.multiplier % 1 === 0 ? 0 : 1)}`;
      leftGroup.appendChild(multPill);
    }

    const stats = war.main_stats || {};
    const statOrder = [
      ["atk", "ATK"],
      ["def", "DEF"],
      ["spa", "SpA"],
      ["spd", "SpD"],
      ["spe", "SPE"],
    ];
    for (const [key, label] of statOrder) {
      if (stats[key] == null) continue;
      const span = document.createElement("span");
      span.className = "oh-war-stat";
      span.append(document.createTextNode(label + " "));
      const val = document.createElement("b");
      val.textContent = String(stats[key]);
      span.appendChild(val);
      leftGroup.appendChild(span);
    }

    const rightGroup = document.createElement("div");
    rightGroup.className = "oh-war-group";

    if (war.enemy_ability) {
      const ab = document.createElement("span");
      ab.className = "oh-war-stat";
      const val = document.createElement("b");
      val.textContent = String(war.enemy_ability);
      ab.appendChild(val);
      rightGroup.appendChild(ab);
    }

    if (war.enemy_tier) {
      const tier = document.createElement("span");
      tier.className = "oh-war-pill";
      tier.textContent = String(war.enemy_tier);
      rightGroup.appendChild(tier);
    }

    els.warStrip.append(leftGroup, rightGroup);
    els.warStrip.hidden = !leftGroup.children.length && !rightGroup.children.length;
  }

  function updateCenter(payload) {
    if (!els) return;
    const center = els.center;
    center.textContent = "";

    const txt = labels();
    const shortcuts = (payload && payload.shortcuts) || {};
    const enemyFainted = Boolean(payload && payload.enemy && Number(payload.enemy.hp) <= 0);
    const autoMode = Number((payload && payload.automatic_battle) || 0);
    const override = payload && payload.auto_battle_override;

    if (enemyFainted && autoMode === 0) {
      const catchBtn = document.createElement("button");
      catchBtn.type = "button";
      catchBtn.className = "oh-action-btn oh-action-btn--catch";
      catchBtn.append(document.createTextNode(txt.catchLabel));
      if (shortcuts.catch) {
        const kbd = document.createElement("span");
        kbd.className = "oh-kbd";
        kbd.textContent = String(shortcuts.catch).toUpperCase();
        catchBtn.appendChild(kbd);
      }
      catchBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        sendCmd("onigimon_hud:catch");
      });

      const defeatBtn = document.createElement("button");
      defeatBtn.type = "button";
      defeatBtn.className = "oh-action-btn oh-action-btn--defeat";
      defeatBtn.append(document.createTextNode(txt.defeatLabel));
      if (shortcuts.defeat) {
        const kbd = document.createElement("span");
        kbd.className = "oh-kbd";
        kbd.textContent = String(shortcuts.defeat).toUpperCase();
        defeatBtn.appendChild(kbd);
      }
      defeatBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        sendCmd("onigimon_hud:defeat");
      });

      center.append(catchBtn, defeatBtn);
      return;
    }

    if (override === "catch" || override === "defeat") {
      const pill = document.createElement("span");
      pill.className = "oh-override-pill";
      pill.textContent = override === "catch" ? txt.catchLabel : txt.defeatLabel;
      center.appendChild(pill);
      return;
    }

    if (payload && payload.show_main) {
      const divider = document.createElement("div");
      divider.className = "oh-divider";
      divider.setAttribute("aria-hidden", "true");
      center.appendChild(divider);
    }
  }

  function renderBagContent(inventory) {
    if (!els) return;
    const txt = labels();
    els.bagTitle.textContent = txt.itemsTitle;
    els.bagCurrencies.textContent = "";
    els.bagBody.textContent = "";

    const inv = inventory || {};
    const currencies = Array.isArray(inv.currencies) ? inv.currencies : [];
    for (const cur of currencies) {
      const pill = document.createElement("span");
      pill.className = "oh-currency-pill";
      pill.title = cur.label || "";
      if (cur.icon_url) {
        const img = document.createElement("img");
        img.src = cur.icon_url;
        img.alt = "";
        pill.appendChild(img);
      }
      const val = document.createElement("span");
      val.textContent = String(cur.count || 0);
      pill.appendChild(val);
      els.bagCurrencies.appendChild(pill);
    }

    const items = Array.isArray(inv.items) ? inv.items : [];
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "oh-bag-empty";
      empty.textContent = txt.itemsEmpty;
      els.bagBody.appendChild(empty);
      return;
    }

    const grid = document.createElement("div");
    grid.className = "oh-bag-grid";
    for (const item of items) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "oh-bag-item";
      btn.disabled = !item.usable;
      btn.title = item.effect ? `${item.label} — ${item.effect}` : item.label;

      if (item.icon_url) {
        const img = document.createElement("img");
        img.src = item.icon_url;
        img.alt = "";
        btn.appendChild(img);
      }

      const meta = document.createElement("div");
      meta.className = "oh-bag-item-meta";
      const name = document.createElement("span");
      name.className = "oh-bag-item-name";
      name.textContent = item.label || item.key;
      meta.appendChild(name);
      if (item.effect) {
        const eff = document.createElement("span");
        eff.className = "oh-bag-item-effect";
        eff.textContent = item.effect;
        meta.appendChild(eff);
      }

      const qty = document.createElement("span");
      qty.className = "oh-bag-item-qty";
      qty.textContent = "×" + item.count;

      btn.append(meta, qty);
      if (item.usable) {
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          sendCmd("onigimon_hud:use_item:" + encodeURIComponent(item.key));
        });
      }
      grid.appendChild(btn);
    }
    els.bagBody.appendChild(grid);
  }

  function renderBagVisibility() {
    if (!els) return;
    els.bagPanel.hidden = !bagOpen || collapsed;
    els.inlineBagBtn.classList.toggle("is-active", bagOpen);
    if (bagOpen && !collapsed) {
      syncBagDirection();
    }
  }

  function toggleBag() {
    bagOpen = !bagOpen;
    if (bagOpen && lastPayload && lastPayload.inventory) {
      renderBagContent(lastPayload.inventory);
    }
    renderBagVisibility();
  }

  function renderVisibility() {
    if (!els) return;
    const payloadHidden = !lastPayload || Boolean(lastPayload.hidden);
    const shouldHide = !enabled || payloadHidden || Boolean(userHidden);
    els.shell.classList.toggle("is-hidden", shouldHide);
    if (shouldHide) {
      bagOpen = false;
      els.bagPanel.hidden = true;
      return;
    }

    els.shell.classList.toggle("is-collapsed", collapsed);
    els.bar.hidden = collapsed;
    els.collapsedPill.hidden = !collapsed;

    if (collapsed) {
      const txt = labels();
      els.collapsedLabel.textContent = txt.showHud;
      const enemy = lastPayload && lastPayload.enemy;
      els.collapsedDot.dataset.level = enemy
        ? hpLevel(Number(enemy.hp) || 0, Math.max(1, Number(enemy.max_hp) || 1))
        : "high";
    }

    renderBagVisibility();
    applyShellPosition();
  }

  function update(payload) {
    lastPayload = payload || null;
    if (!enabled) {
      clear();
      return;
    }

    applyAnkimonSuppression(true);

    if (!payload || payload.hidden) {
      if (els) renderVisibility();
      return;
    }

    if (userHidden === undefined) {
      userHidden = Boolean(payload.hidden_on_startup);
    }

    const ui = ensureHost();
    if (!ui) return;

    applyCustomAppearance(payload);
    const night = isNightMode(payload);
    const styleCfg = (payload && payload.style) || {};
    const mode =
      styleCfg.mode === "minimal" || styleCfg.mode === "war" ? styleCfg.mode : "battle";

    const flags = payload.flags || {};
    const showMain = Boolean(payload.show_main && payload.main);

    updateFighter(ui.main, showMain ? payload.main : null, flags, night, mode);
    updateFighter(ui.enemy, payload.enemy || null, flags, night, mode);
    updateCenter(payload);
    updateWarStrip(payload, mode);

    const inv = payload.inventory || {};
    const totalCount = Number(inv.total_count) || 0;
    ui.inlineBagCount.textContent = totalCount > 0 ? String(totalCount) : "";
    ui.inlineBagCount.hidden = totalCount <= 0;
    ui.inlineBagBtn.hidden = mode === "minimal";
    ui.hoverBagBtn.hidden = mode !== "minimal";
    if (bagOpen) {
      renderBagContent(inv);
    }

    const txt = labels();
    const shortcuts = payload.shortcuts || {};
    ui.grip.title = txt.dragHint;
    ui.inlineBagBtn.title = txt.itemsTitle;
    ui.inlineBagBtn.setAttribute("aria-label", txt.itemsTitle);
    ui.hoverBagBtn.title = txt.itemsTitle;
    ui.hoverBagBtn.setAttribute("aria-label", txt.itemsTitle);

    const canCycle = Boolean(payload.can_cycle_team);
    ui.cycleBtn.hidden = !canCycle;
    ui.cycleBtn.title = shortcuts.team_cycle
      ? txt.cycleTeam + " (" + String(shortcuts.team_cycle).toUpperCase() + ")"
      : txt.cycleTeam;
    ui.cycleBtn.setAttribute("aria-label", ui.cycleBtn.title);

    ui.minBtn.title = txt.hideHud + " (8)";
    ui.minBtn.setAttribute("aria-label", ui.minBtn.title);

    renderVisibility();
  }

  function showDelta(detail) {
    if (!enabled || !detail || !detail.text) return;
    const ui = ensureHost();
    if (!ui || ui.shell.classList.contains("is-hidden") || collapsed) return;

    const side = detail.side === "main" && !ui.main.root.hidden ? "main" : "enemy";
    const target = side === "main" ? ui.main : ui.enemy;
    const layer = target.deltaLayer;
    if (!layer) return;

    const chip = document.createElement("span");
    chip.className = "oh-delta" + (detail.kind === "heal" ? " is-heal" : "");
    chip.textContent = String(detail.text).trim();
    layer.appendChild(chip);

    if (ui.liveRegion) {
      ui.liveRegion.textContent = String(detail.text).trim();
    }

    let removed = false;
    const cleanup = () => {
      if (removed) return;
      removed = true;
      chip.remove();
    };
    chip.addEventListener("animationend", cleanup, { once: true });
    window.setTimeout(cleanup, 1250);
  }

  function clear() {
    lastPayload = null;
    bagOpen = false;
    if (els && els.host) {
      els.host.remove();
    }
    els = null;
  }

  function setEnabled(next) {
    enabled = Boolean(next);
    window.onigimonHudEnabled = enabled;
    applyAnkimonSuppression(enabled);
    if (!enabled) {
      clear();
    }
  }

  function isEditableTarget(target) {
    if (!target || target.nodeType !== 1) return false;
    const tag = target.tagName;
    return (
      tag === "INPUT" ||
      tag === "TEXTAREA" ||
      tag === "SELECT" ||
      target.isContentEditable
    );
  }

  document.addEventListener("keydown", (event) => {
    if (!enabled) return;
    if (event.key === "Escape" && bagOpen) {
      bagOpen = false;
      renderBagVisibility();
      return;
    }
    if (event.key !== "8" || event.ctrlKey || event.metaKey || event.altKey) return;
    if (isEditableTarget(event.target)) return;
    if (!lastPayload || lastPayload.hidden) return;
    userHidden = !userHidden;
    if (!userHidden) {
      collapsed = false;
      update(lastPayload);
    } else {
      renderVisibility();
    }
  });

  document.addEventListener("pointerdown", (event) => {
    if (!bagOpen || !els) return;
    const path = typeof event.composedPath === "function" ? event.composedPath() : [];
    if (
      path.includes(els.bagPanel) ||
      path.includes(els.inlineBagBtn) ||
      path.includes(els.hoverBagBtn)
    ) {
      return;
    }
    bagOpen = false;
    renderBagVisibility();
  });

  if (typeof window.addEventListener === "function") {
    window.addEventListener("resize", () => {
      if (els && customPosition) {
        applyShellPosition();
      }
    });
  }

  if (enabled) {
    applyAnkimonSuppression(true);
  }

  window.OnigimonHUD = {
    update,
    showDelta,
    clear,
    setEnabled,
    isEnabled: () => enabled,
  };
})();
