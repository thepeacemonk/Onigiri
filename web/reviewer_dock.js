(function () {
  "use strict";

  if (window.OnigiriReviewerDock) return;

  const MOCHI_ICON_IMAGE = "/_addons/1011095603/system_files/gamification_images/mochi_messenger.webp";
  const ONIGIRI_ICON_IMAGE = "/_addons/1011095603/system_files/onigiri_mini_logo.svg";

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function px(value) {
    return value.toFixed(2) + "px";
  }

  function prefersReducedMotion() {
    return Boolean(
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function createMotion(values, paint) {
    const axes = values.map((x) => ({ x, target: x, v: 0, k: 420, d: 32 }));
    let frame = 0;
    let last = 0;

    function tick(now) {
      const dt = Math.min(last ? (now - last) / 1000 : 1 / 60, 1 / 30) / 4;
      last = now;
      let moving = false;
      for (let idx = 0; idx < axes.length; idx++) {
        const a = axes[idx];
        for (let stepIdx = 0; stepIdx < 4; stepIdx++) {
          a.v += ((a.target - a.x) * a.k - a.v * a.d) * dt;
          a.x += a.v * dt;
        }
        if (Math.abs(a.x - a.target) > 0.004 || Math.abs(a.v) > 0.025) {
          moving = true;
        } else {
          a.x = a.target;
          a.v = 0;
        }
      }
      paint(axes);
      frame = moving ? window.requestAnimationFrame(tick) : 0;
      if (!moving) last = 0;
    }

    return {
      axes,
      move(targets, options, snap) {
        const opts = options || [];
        for (let i = 0; i < axes.length; i++) {
          axes[i].target = targets[i];
          if (opts[i]) {
            axes[i].k = opts[i][0];
            axes[i].d = opts[i][1];
          }
        }
        if (snap || prefersReducedMotion()) {
          if (frame) window.cancelAnimationFrame(frame);
          frame = 0;
          last = 0;
          axes.forEach((axis) => {
            axis.x = axis.target;
            axis.v = 0;
          });
          paint(axes);
        } else if (!frame) {
          frame = window.requestAnimationFrame(tick);
        }
      },
      destroy() {
        if (frame) window.cancelAnimationFrame(frame);
        frame = 0;
      }
    };
  }

  let activeCleanup = null;

  function mountRubberDock(dockEl) {
    const indicator = dockEl.querySelector(".onigiri-dock-indicator");
    const ink = dockEl.querySelector(".onigiri-dock-ink");
    const tip = dockEl.querySelector(".onigiri-dock-tip");
    if (!indicator || !ink) return () => {};

    let items = [];
    let clones = [];
    let popSprings = [];
    let activeItem = null;
    let activeWidth = 34;
    let activeHeight = 34;
    let activeTop = 0;
    let inkWidth = 0;
    let inkHeight = 0;
    let leaveTimer = null;
    let drag = null;
    let suppressClickUntil = 0;

    const animator = createMotion([0, 0], ([left, right]) => {
      const minW = Math.max(22, activeWidth * 0.62);
      const width = Math.max(minW, right.x - left.x);
      const center = (left.x + right.x) / 2;
      const leftEdge = center - width / 2;
      indicator.style.left = px(leftEdge);
      indicator.style.width = px(width);

      const height = activeHeight * clamp(Math.sqrt(activeWidth / Math.max(1, width)), 0.68, 1.1);
      const top = activeTop + (activeHeight - height) / 2;
      indicator.style.height = px(height);
      indicator.style.top = px(top);
      indicator.style.borderRadius = px(height / 2);

      if (inkWidth > 0 && inkHeight > 0) {
        const rightInset = Math.max(0, inkWidth - leftEdge - width);
        const bottomInset = Math.max(0, inkHeight - top - height);
        const topInset = Math.max(0, top);
        const leftInset = Math.max(0, leftEdge);
        ink.style.clipPath =
          "inset(" +
          [topInset, rightInset, bottomInset, leftInset].map(px).join(" ") +
          " round 999px)";
      }
    });

    function normalizeExternalItems() {
      const ext = dockEl.querySelector("#onigiri-reviewer-external-actions");
      if (!ext) return;
      ext.querySelectorAll("a.onigiri-external-toolbar-button").forEach((btn) => {
        btn.classList.add("onigiri-dock-item");
        if (!btn.getAttribute("data-tip")) {
          const tipLabel = btn.getAttribute("aria-label") || btn.getAttribute("title") || btn.textContent.trim();
          if (tipLabel) btn.setAttribute("data-tip", tipLabel);
        }
        if (!btn.querySelector("svg") && !btn.querySelector("span[style*='mask']") && !btn.querySelector(".onigiri-dock-glyph")) {
          const text = (btn.textContent || "").trim();
          const span = document.createElement("span");
          span.className = "onigiri-dock-glyph is-emoji";
          span.style.cssText = "display:grid;place-items:center;font-size:12px;font-weight:700;";
          span.textContent = text ? text.slice(0, 2).toUpperCase() : "•";
          btn.textContent = "";
          btn.appendChild(span);
        }
      });
    }

    function rebuildItems() {
      normalizeExternalItems();
      items = Array.from(dockEl.querySelectorAll(".onigiri-dock-item"));
      ink.textContent = "";
      clones = [];
      popSprings.forEach((s) => s.destroy());
      popSprings = [];

      items.forEach((btn, idx) => {
        const glyph = btn.querySelector(".onigiri-dock-glyph, svg, span");
        const clone = glyph ? glyph.cloneNode(true) : document.createElement("span");
        clone.classList.add("onigiri-dock-ink-icon");
        if (clone.style && clone.style.color) clone.style.color = "";
        ink.appendChild(clone);
        clones.push(clone);

        const pop = createMotion([1], ([s]) => {
          const tf = "scale(" + s.x.toFixed(3) + ")";
          if (glyph) glyph.style.transform = tf;
          clone.style.transform = tf;
        });
        popSprings.push(pop);

        if (!btn.dataset.onigiriDockBound) {
          btn.dataset.onigiriDockBound = "1";
          btn.addEventListener("pointerenter", (e) => {
            if (e.pointerType === "touch") return;
            window.clearTimeout(leaveTimer);
            selectItem(btn, !dockEl.classList.contains("has-selection"));
            showTip(btn);
          });
          btn.addEventListener("focus", () => {
            if (btn.matches(":focus-visible")) {
              window.clearTimeout(leaveTimer);
              selectItem(btn, !dockEl.classList.contains("has-selection"));
              showTip(btn);
            }
          });
          btn.addEventListener("blur", () => {
            if (tip) tip.classList.remove("visible");
          });
          btn.addEventListener("click", () => {
            const i = items.indexOf(btn);
            if (i >= 0 && popSprings[i]) {
              popSprings[i].axes[0].v -= 3.0;
              popSprings[i].move([1], [[520, 16]], false);
            }
          });
        }
      });
      measure(true);
    }

    function measure(snap) {
      inkWidth = ink.clientWidth || dockEl.clientWidth;
      inkHeight = ink.clientHeight || dockEl.clientHeight;
      items.forEach((btn, idx) => {
        const glyph = btn.querySelector("svg, .onigiri-dock-glyph, span");
        const clone = clones[idx];
        if (!glyph || !clone) return;
        const gw = glyph.clientWidth || 17;
        const gh = glyph.clientHeight || 17;
        const left = btn.offsetLeft + (btn.offsetWidth - gw) / 2;
        const top = btn.offsetTop + (btn.offsetHeight - gh) / 2;
        clone.style.left = px(left);
        clone.style.top = px(top);
      });
      if (activeItem && items.includes(activeItem)) {
        selectItem(activeItem, Boolean(snap));
      } else if (items.length) {
        const first = items[0];
        activeWidth = first.offsetWidth || 34;
        activeHeight = first.offsetHeight || 34;
        activeTop = first.offsetTop || 0;
        animator.move(
          [first.offsetLeft, first.offsetLeft + activeWidth],
          [[600, 44], [600, 44]],
          true
        );
      }
    }

    function selectItem(item, snap) {
      if (!item) return;
      const hadSelection = dockEl.classList.contains("has-selection");
      dockEl.classList.add("has-selection");
      activeItem = item;
      activeWidth = item.offsetWidth || 34;
      activeHeight = item.offsetHeight || 34;
      activeTop = item.offsetTop || 0;
      const left = item.offsetLeft;
      const right = left + activeWidth;
      const toRight = left >= animator.axes[0].x;
      const fast = [640, 38];
      const slow = [150, 16];
      animator.move(
        [left, right],
        toRight ? [slow, fast] : [fast, slow],
        Boolean(snap || !hadSelection)
      );
    }

    function showTip(item) {
      if (!tip || !item) return;
      const label = item.getAttribute("data-tip") || item.getAttribute("aria-label") || "";
      if (!label) return;
      tip.textContent = label;
      dockEl.style.setProperty("--tip-x", px(item.offsetLeft + item.offsetWidth / 2));
      tip.classList.add("visible");
    }

    function clearSelection() {
      if (drag && drag.moved) return;
      dockEl.classList.remove("has-selection");
      if (tip) tip.classList.remove("visible");
      activeItem = null;
    }

    dockEl.addEventListener("pointerleave", () => {
      if (tip) tip.classList.remove("visible");
      leaveTimer = window.setTimeout(clearSelection, 50);
    });

    dockEl.addEventListener("pointerdown", (event) => {
      suppressClickUntil = 0;
      const item = event.target && event.target.closest ? event.target.closest(".onigiri-dock-item") : null;
      if (event.button !== 0 || !item || !items.includes(item)) return;
      drag = { pointer: event.pointerId, start: event.clientX, moved: false, item };
    });

    dockEl.addEventListener("pointermove", (event) => {
      if (!drag || drag.pointer !== event.pointerId) return;
      if (!drag.moved && Math.abs(event.clientX - drag.start) < 8) return;
      if (!drag.moved) {
        drag.moved = true;
        try { dockEl.setPointerCapture(event.pointerId); } catch (_) {}
      }
      dockEl.setAttribute("data-dragging", "");
      dockEl.classList.add("has-selection");
      const rect = dockEl.getBoundingClientRect();
      const local = event.clientX - rect.left;
      if (!items.length) return;
      const center = (it) => it.offsetLeft + it.offsetWidth / 2;
      drag.item = items.reduce((nearest, it) =>
        Math.abs(center(it) - local) < Math.abs(center(nearest) - local) ? it : nearest
      );
      showTip(drag.item);
      const half = (drag.item.offsetWidth || 34) / 2;
      const minLeft = items[0].offsetLeft;
      const maxLeft = items[items.length - 1].offsetLeft;
      const left = clamp(local - half, minLeft, maxLeft);
      const forward = left >= animator.axes[0].x;
      const lead = [1100, 56];
      const trail = [320, 26];
      animator.move([left, left + 2 * half], forward ? [trail, lead] : [lead, trail], false);
    });

    function release(event) {
      if (!drag || drag.pointer !== event.pointerId) return;
      if (drag.moved) {
        dockEl.removeAttribute("data-dragging");
        if (event.type === "pointerup" && drag.item) {
          suppressClickUntil = performance.now() + 240;
          selectItem(drag.item, false);
          drag.item.click();
        }
      }
      drag = null;
    }

    dockEl.addEventListener("pointerup", release);
    dockEl.addEventListener("pointercancel", release);
    dockEl.addEventListener("click", (event) => {
      if (event.isTrusted && event.detail > 0 && performance.now() < suppressClickUntil) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }, true);

    const resizeObserver = typeof ResizeObserver === "function"
      ? new ResizeObserver(() => measure(true))
      : null;
    if (resizeObserver) resizeObserver.observe(dockEl);

    const extSlot = dockEl.querySelector("#onigiri-reviewer-external-actions");
    const extObserver = extSlot && typeof MutationObserver === "function"
      ? new MutationObserver(() => rebuildItems())
      : null;
    if (extObserver) extObserver.observe(extSlot, { childList: true, subtree: true });

    rebuildItems();

    return () => {
      window.clearTimeout(leaveTimer);
      animator.destroy();
      popSprings.forEach((s) => s.destroy());
      if (resizeObserver) resizeObserver.disconnect();
      if (extObserver) extObserver.disconnect();
    };
  }

  function notificationIconSrc(data) {
    const variant = data.variant || (data.id === "mochi_message" ? "mochi" : "");
    let src = null;
    if (Object.prototype.hasOwnProperty.call(data, "iconImage")) {
      src = data.iconImage || null;
    } else if (variant === "mochi" || data.id === "mochi_message") {
      src = MOCHI_ICON_IMAGE;
    } else if (data.icon && (String(data.icon).includes("/") || String(data.icon).includes("."))) {
      src = data.icon;
    }
    if (!src && (!data.icon || data.icon === "On")) {
      src = ONIGIRI_ICON_IMAGE;
    }
    return { src, variant };
  }

  function buildIslandNoticeElement(data) {
    const item = document.createElement("div");
    item.className = "onigiri-island-notice-item";
    const { src, variant } = notificationIconSrc(data);
    if (variant) item.dataset.variant = variant;
    if (data.hideIcon) item.classList.add("has-no-icon");
    if (data.hideTitle) item.classList.add("has-no-title");
    if (data.centered) item.classList.add("is-centered");

    if (!data.hideIcon) {
      const iconBox = document.createElement("div");
      iconBox.className = "onigiri-island-notice-icon";
      if (src) {
        const img = document.createElement("img");
        img.src = src;
        img.alt = data.iconAlt || "";
        const fallbacks = Array.isArray(data.iconFallbacks)
          ? data.iconFallbacks.filter((s) => s && s !== src)
          : [];
        img.addEventListener("error", () => {
          if (fallbacks.length) img.src = fallbacks.shift();
          else img.style.display = "none";
        });
        iconBox.appendChild(img);
      } else {
        iconBox.textContent = data.icon || "🍙";
      }
      item.appendChild(iconBox);
    }

    const copy = document.createElement("div");
    copy.className = "onigiri-island-notice-copy";
    if (!data.hideTitle) {
      const title = document.createElement("p");
      title.className = "onigiri-island-notice-title";
      title.textContent = data.name || "Onigiri";
      copy.appendChild(title);
    }
    if (data.description) {
      const desc = document.createElement("p");
      desc.className = "onigiri-island-notice-desc";
      desc.textContent = data.description;
      copy.appendChild(desc);
    }
    if (Array.isArray(data.rewardItems) && data.rewardItems.length) {
      const rewards = document.createElement("div");
      rewards.className = "onigiri-island-notice-rewards";
      data.rewardItems.forEach((entry) => {
        const chip = document.createElement("span");
        chip.className = "onigiri-island-notice-reward";
        if (entry.iconImage) {
          const img = document.createElement("img");
          img.src = entry.iconImage;
          img.alt = entry.iconAlt || "";
          chip.appendChild(img);
        }
        const val = document.createElement("span");
        val.textContent = String(entry.value || "");
        chip.appendChild(val);
        rewards.appendChild(chip);
      });
      copy.appendChild(rewards);
    }
    item.appendChild(copy);
    return item;
  }

  function mountIsland(headerEl) {
    const shell = headerEl.querySelector(".onigiri-island-shell");
    const surface = headerEl.querySelector(".onigiri-island-surface");
    const bar = headerEl.querySelector(".onigiri-island-bar");
    const notice = headerEl.querySelector(".onigiri-island-notice");
    const noticeInner = headerEl.querySelector(".onigiri-island-notice-inner");
    const dockEl = headerEl.querySelector(".onigiri-rubber-dock");
    if (!shell || !surface || !bar || !notice || !noticeInner) return () => {};

    const cleanupDock = dockEl ? mountRubberDock(dockEl) : () => {};

    let barW = bar.offsetWidth || 260;
    let barH = bar.offsetHeight || 42;
    let noticeH = 0;
    let retracting = false;
    let retractStartH = 0;
    let activeEntries = [];
    let hovered = false;

    const islandSpring = createMotion([barW, barH], ([wAxis, hAxis]) => {
      const w = Math.max(barW, wAxis.x);
      const h = Math.max(barH, hAxis.x);
      const give = clamp(-hAxis.v / 9000, -0.04, 0.04);
      const openFrac = clamp((h - barH) / Math.max(1, noticeH || 72), 0, 1);
      const pillRadius = barH / 2;
      const radius = Math.max(18, pillRadius - (pillRadius - 18) * openFrac);

      surface.style.width = px(w * (1 + give));
      surface.style.height = px(h);
      surface.style.borderRadius = px(radius);
      shell.style.setProperty("--island-height", px(h));

      const room = Math.max(0, h - barH);
      if (notice.classList.contains("has-message")) {
        notice.style.setProperty("--notice-room", px(room));
      }
      if (retracting) {
        notice.style.setProperty(
          "--notice-visibility",
          String(clamp(room / Math.max(1, retractStartH), 0, 1))
        );
        if (room < 0.6) {
          finishClear();
        }
      }
    });

    function finishClear() {
      retracting = false;
      retractStartH = 0;
      noticeInner.textContent = "";
      notice.classList.remove("has-message", "is-retracting");
      shell.classList.remove("island-notice");
      notice.style.removeProperty("--notice-room");
      notice.style.removeProperty("--notice-visibility");
      noticeH = 0;
    }

    function measureAndMove(snap) {
      barW = bar.offsetWidth || barW;
      barH = bar.offsetHeight || barH;
      const hasEntries = activeEntries.length > 0;
      const showing = hasEntries && !retracting;

      if (showing) {
        const maxW = Math.max(barW, Math.min(370, (window.innerWidth || 800) - 24));
        shell.style.setProperty("--island-notice-width", px(maxW));
        notice.classList.add("has-message");
        notice.classList.remove("is-retracting");
        shell.classList.add("island-notice");
        noticeH = notice.offsetHeight || 0;
        const targetW = Math.max(barW, maxW);
        const targetH = barH + noticeH;
        islandSpring.move([targetW, targetH], [[380, 24], [300, 22]], Boolean(snap));
      } else if (retracting) {
        notice.classList.add("is-retracting");
        islandSpring.move([barW, barH], [[320, 25], [400, 30]], Boolean(snap));
      } else {
        islandSpring.move([barW, barH], [[340, 26], [380, 28]], Boolean(snap));
      }
    }

    function scheduleTimer(entry) {
      window.clearTimeout(entry.timer);
      if (hovered) return;
      entry.timer = window.setTimeout(() => dismissEntry(entry), entry.duration);
    }

    function dismissEntry(entry) {
      window.clearTimeout(entry.timer);
      const idx = activeEntries.indexOf(entry);
      if (idx === -1) return;
      activeEntries.splice(idx, 1);

      if (activeEntries.length === 0) {
        if (!prefersReducedMotion() && shell.classList.contains("island-notice")) {
          retracting = true;
          retractStartH = Math.max(1, notice.offsetHeight || noticeH);
          measureAndMove(false);
        } else {
          finishClear();
          measureAndMove(true);
        }
        return;
      }

      entry.el.remove();
      measureAndMove(false);
    }

    function notify(payload) {
      const data = payload || {};
      if (retracting) {
        finishClear();
      }
      const configured = Number(window.onigiriNotificationDuration);
      const duration = Number.isFinite(configured) && configured > 0
        ? clamp(configured, 1000, 30000)
        : clamp(Number(data.duration) || 5200, 1000, 30000);

      // Keep at most 3 concurrent notices inside the island drawer.
      while (activeEntries.length >= 3) {
        const oldest = activeEntries.shift();
        window.clearTimeout(oldest.timer);
        oldest.el.remove();
      }

      const itemEl = buildIslandNoticeElement(data);
      const entry = { el: itemEl, duration, timer: null };
      itemEl.addEventListener("click", (e) => {
        e.stopPropagation();
        dismissEntry(entry);
      });
      activeEntries.push(entry);
      noticeInner.appendChild(itemEl);
      scheduleTimer(entry);
      measureAndMove(false);
    }

    function clear() {
      activeEntries.forEach((entry) => window.clearTimeout(entry.timer));
      activeEntries = [];
      finishClear();
      measureAndMove(true);
    }

    notice.addEventListener("mouseenter", () => {
      hovered = true;
      activeEntries.forEach((entry) => window.clearTimeout(entry.timer));
    });

    notice.addEventListener("mouseleave", () => {
      hovered = false;
      activeEntries.forEach((entry) => scheduleTimer(entry));
    });

    const resizeObserver = typeof ResizeObserver === "function"
      ? new ResizeObserver(() => {
          if (!retracting) measureAndMove(activeEntries.length === 0);
          if (typeof window.onigiriRefreshReviewerHeaderOffset === "function") {
            window.onigiriRefreshReviewerHeaderOffset();
          }
        })
      : null;
    if (resizeObserver) {
      resizeObserver.observe(bar);
      resizeObserver.observe(notice);
    }

    const onWindowResize = () => measureAndMove(true);
    window.addEventListener("resize", onWindowResize);

    window.OnigiriReviewerIsland = {
      notify,
      clear,
      isExpanded: () => activeEntries.length > 0
    };

    measureAndMove(true);

    return () => {
      activeEntries.forEach((entry) => window.clearTimeout(entry.timer));
      activeEntries = [];
      islandSpring.destroy();
      cleanupDock();
      if (resizeObserver) resizeObserver.disconnect();
      window.removeEventListener("resize", onWindowResize);
      if (window.OnigiriReviewerIsland && window.OnigiriReviewerIsland.notify === notify) {
        delete window.OnigiriReviewerIsland;
      }
    };
  }

  function mount(root) {
    if (activeCleanup) {
      activeCleanup();
      activeCleanup = null;
    }
    const targetRoot = root || (function () {
      const host = document.getElementById("onigiri-reviewer-ui-host");
      return (host && host.shadowRoot) || document;
    })();
    if (!targetRoot) return;
    const header = targetRoot.getElementById("onigiri-reviewer-header");
    if (!header) return;

    if (header.classList.contains("is-island")) {
      activeCleanup = mountIsland(header);
    }
  }

  function replaceHeader(html, css, mode) {
    window.onigiriReviewerDockMode = mode || "static";
    const host = document.getElementById("onigiri-reviewer-ui-host");
    const shadow = host && host.shadowRoot;
    const styleRoot = shadow || document.head || document.documentElement;
    const headerRoot = shadow || document;
    if (!styleRoot || !headerRoot) return;

    if (activeCleanup) {
      activeCleanup();
      activeCleanup = null;
    }

    const oldHeader = headerRoot.getElementById("onigiri-reviewer-header") ||
      (!shadow && document.getElementById("onigiri-overview-header"));
    const headerParent = (oldHeader && oldHeader.parentNode) || shadow || document.body;
    const headerAnchor = oldHeader ? oldHeader.nextSibling : null;
    if (oldHeader) oldHeader.remove();

    styleRoot.querySelectorAll("style[data-onigiri-dock-style], style#onigiri-reviewer-dock-style, style#onigiri-reviewer-top-bar-structure, style#onigiri-reviewer-theme-colors, style#onigiri-reviewer-progress-style, style#onigiri-scoped-main-font, style#onigiri-box-effect-vars").forEach((s) => s.remove());

    if (css) {
      const tpl = document.createElement("template");
      tpl.innerHTML = css;
      Array.from(tpl.content.children).forEach((node) => {
        if (node.tagName === "STYLE") node.setAttribute("data-onigiri-dock-style", "1");
        styleRoot.appendChild(node);
      });
    }

    if (html && headerParent) {
      const tpl = document.createElement("template");
      tpl.innerHTML = html;
      const nextHeader = tpl.content.firstElementChild;
      if (nextHeader) {
        if (headerAnchor && headerAnchor.parentNode === headerParent) {
          headerParent.insertBefore(nextHeader, headerAnchor);
        } else if (shadow) {
          headerParent.appendChild(nextHeader);
        } else {
          headerParent.insertBefore(nextHeader, headerParent.firstChild);
        }
      }
    }

    mount(headerRoot);
    if (typeof window.onigiriRefreshReviewerHeaderOffset === "function") {
      window.onigiriRefreshReviewerHeaderOffset();
    }
  }

  window.OnigiriReviewerDock = {
    mount,
    replaceHeader
  };

  if (document.readyState !== "loading") {
    window.setTimeout(() => mount(), 0);
  } else {
    document.addEventListener("DOMContentLoaded", () => window.setTimeout(() => mount(), 0), { once: true });
  }
})();
