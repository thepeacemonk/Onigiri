/* MagneticSelect — adapted from the user-supplied Bencho component.
 * Source: https://bencho.dev/licence (MIT, as supplied with the component).
 * Anki uses native DOM buttons; its existing icon, font and surface tokens
 * replace MARKS and the Bencho palette. Packing adapts to the widget.
 */
(function () {
  "use strict";
  const CHIP = 48, PITCH = 50, PAD = 34;
  const p = .55, grow = 1.16 + .22 * p;
  const room = CHIP * (grow - 1) / 2, aura = 3 + 9 * p;
  const cower = .04 + .09 * p, tilt = 5 * p, SPREAD = 2.8;
  const zeta = .9 - .48 * .55;
  const mounted = new Map();

  function mount(root) {
    const stage = root.parentElement;
    const buttons = Array.from(root.querySelectorAll(".onigiri-ready-action"));
    if (buttons.length !== 4) return;
    const widget = stage.parentElement;
    const labels = buttons.map(button => {
      const label = button.querySelector(".mag-label");
      stage.appendChild(label);
      return label;
    });
    const still = window.matchMedia("(prefers-reduced-motion: reduce)");
    let pts = [], width = 0, height = 0, inRow = null;
    let active = null, hover = null, focus = null, raf = 0, last = 0;
    let lean = {x: 0, y: 0};
    const channels = buttons.map(() => [0, 0, 1, 1, 0].map(v => ({v, target: v, velocity: 0, delay: 0})));
    function layout() {
      const row = stage.clientHeight < CHIP + PITCH + PAD * 2 ||
        stage.clientWidth > stage.clientHeight * 1.7;
      if (row === inRow) { placeLabel(); return; }
      inRow = row;
      pts = row ? [[0, 0], [PITCH, 0], [PITCH * 2, 0], [PITCH * 3, 0]] :
        [[0, 0], [PITCH, 0], [0, PITCH], [PITCH, PITCH]];
      width = Math.max(...pts.map(pt => pt[0])) + CHIP + PAD * 2;
      height = Math.max(...pts.map(pt => pt[1])) + CHIP + PAD * 2;
      root.classList.toggle("is-row", row);
      root.style.width = width + "px";
      root.style.height = height + "px";
      buttons.forEach((button, i) => {
        button.style.left = PAD + pts[i][0] + "px";
        button.style.top = PAD + pts[i][1] + "px";
      });
      field(active);
    }

    /* ── ONE decision, and the rest is arithmetic ────────────
       GROW is the knob. ROOM is the space the swell physically
       takes on every side — half the extra width, exactly — so
       the neighbours are never merely *near* clear of it. AURA
       is the part that is not arithmetic: the push beyond what
       the geometry demands, which is the difference between a
       cluster making room and a cluster being repelled. */
    function field(index) {
      active = index;
      const now = performance.now();
      pts.forEach(([px, py], i) => {
        const dx = index === null ? 0 : px - pts[index][0];
        const dy = index === null ? 0 : py - pts[index][1];
        const gap = Math.hypot(dx, dy), far = gap / PITCH;
        const on = index === i;
        const fall = index === null || on ? 0 : Math.exp(-(far - 1) / SPREAD);
        /* ── THE PUSH DOES NOT DECAY, and that is the fix ──────
           Constant, it cannot happen: two chips on the same
           bearing move by the same amount and their spacing is
           exactly what it was. Nothing in the cluster ever
           compresses now; gaps only open. */
        const push = index === null || on ? 0 : room + aura;
        const ux = gap ? dx / gap : 0, uy = gap ? dy / gap : 0;
        const targets = [ux * push, uy * push, on ? grow : 1 - cower * fall,
          on ? grow : 1 - cower * fall, ux * tilt * fall];
        buttons[i].toggleAttribute("data-on", on);
        labels[i].toggleAttribute("data-on", on);
        channels[i].forEach((ch, j) => {
          ch.target = targets[j];
          ch.delay = now + far * 22;
          ch.k = (300 + 280 * (1 - Math.min(far, 3) / 4)) * [1, 1, 1.24, .86, .8][j];
          ch.mass = [.9, .9, .8, .95, 1][j];
        });
      });
      if (still.matches) {
        channels.forEach(row => row.forEach(ch => { ch.v = ch.target; ch.velocity = 0; }));
        paint();
      } else if (!raf) { last = performance.now(); raf = requestAnimationFrame(tick); }
      placeLabel();
    }
    // Labels live outside transformed buttons, so spring growth never scales
    // the text. Choose the closest clear position within the widget's edges.
    function placeLabel() {
      if (active === null) return;
      const label = labels[active], base = stage.getBoundingClientRect();
      const box = widget.getBoundingClientRect();
      const discs = buttons.map(button => button.getBoundingClientRect());
      const disc = discs[active], text = label.getBoundingClientRect(), gap = 3;
      const bounds = {left: box.left + 8, right: box.right - 8,
        top: box.top + 8, bottom: box.bottom - 8};
      const head = widget.querySelector(".onigiri-widget-head");
      const obstacles = head ? [...discs, head.getBoundingClientRect()] : discs;
      const cx = (disc.left + disc.right) / 2, cy = (disc.top + disc.bottom) / 2;
      const above = !inRow && active < 2;
      const vertical = [
        [cx - text.width / 2, disc.bottom + gap],
        [cx - text.width / 2, disc.top - gap - text.height]
      ];
      if (above) vertical.reverse();
      const candidates = [...vertical,
        [disc.left - gap - text.width, cy - text.height / 2],
        [disc.right + gap, cy - text.height / 2]];
      let best, score = Infinity;
      candidates.forEach(([x, y], order) => {
        const left = Math.max(bounds.left, Math.min(x, bounds.right - text.width));
        const top = Math.max(bounds.top, Math.min(y, bounds.bottom - text.height));
        const overlap = obstacles.reduce((sum, rect) => sum +
          Math.max(0, Math.min(left + text.width, rect.right) - Math.max(left, rect.left)) *
          Math.max(0, Math.min(top + text.height, rect.bottom) - Math.max(top, rect.top)), 0);
        const cost = overlap * 1000 + Math.hypot(left - x, top - y) + order;
        if (cost < score) { score = cost; best = [left, top]; }
      });
      label.style.left = best[0] - base.left + "px";
      label.style.top = best[1] - base.top + "px";
    }
    function paint() {
      buttons.forEach((button, i) => {
        const v = channels[i].map(ch => ch.v);
        button.style.transform = `translate(${v[0]}px,${v[1]}px) rotate(${v[4]}deg) scale(${v[2]},${v[3]})`;
      });
      placeLabel();
    }
    /* ── the springs ─────────────────────────────────────────
       Bounce is a DAMPING RATIO, not a damping value: tie it to
       a raw number and the same setting is bouncy on one chip
       and dead on another, because each chip here springs at a
       different stiffness. As a ratio it means the same thing
       everywhere — 0.9 arrives and stops, 0.42 arrives and
       rings — and stiffness is then free to vary. */
    function tick(now) {
      raf = 0;
      if (!root.isConnected) return;
      const dt = Math.min(.032, (now - last) / 1000); last = now;
      let moving = false;
      channels.forEach(row => row.forEach(ch => {
        if (now < ch.delay) { moving = true; return; }
        // Substeps keep the source's independent X/Y springs stable on slow frames.
        const steps = Math.max(1, Math.ceil(dt / .008)), h = dt / steps;
        for (let s = 0; s < steps; s++) {
          const damping = 2 * Math.sqrt(ch.k * ch.mass) * zeta;
          ch.velocity += ((ch.target - ch.v) * ch.k - damping * ch.velocity) / ch.mass * h;
          ch.v += ch.velocity * h;
        }
        if (Math.abs(ch.target - ch.v) < .002 && Math.abs(ch.velocity) < .02) {
          ch.v = ch.target; ch.velocity = 0;
        } else moving = true;
      }));
      paint();
      // The loop parks itself the moment the value has settled.
      if (moving) raf = requestAnimationFrame(tick);
    }
    function choose() { const next = hover === null ? focus : hover; if (next !== active) field(next); }
    buttons.forEach((button, i) => {
      button.addEventListener("pointerenter", () => { hover = i; choose(); });
      button.addEventListener("pointerleave", () => { hover = null; choose(); });
      button.addEventListener("focus", () => { focus = i; choose(); });
      button.addEventListener("blur", () => { focus = null; choose(); });
      // Preserve each existing pycmd click: these circles are study actions.
    });

    /* ── AND THE VECTOR IS MEASURED FROM ONE POINT ───────────
       One origin, the cluster's own centre, and the whole thing
       goes away: there is nothing to hand over to.
       Measured from the chips' own resting geometry rather than
       from their rects. Reading a position off a thing this
       displaces is a feedback loop — it settles, but it settles
       by ringing, and on a 44px disc the ring is visible. */
    function read(e) {
      if (still.matches) return;
      const b = root.getBoundingClientRect(), scale = b.width / width || 1;
      const dx = (e.clientX - b.left) / scale - width / 2;
      const dy = (e.clientY - b.top) / scale - height / 2;
      const d = Math.hypot(dx, dy), r = Math.hypot(width / 2 - PAD - CHIP / 2,
        height / 2 - PAD - CHIP / 2) + CHIP / 2;
      const drawn = Math.min(1, d / r) * (d <= r ? 1 : Math.max(0, 1 - (d - r) / 44)) * 4.5;
      lean = {x: dx / (d || 1) * drawn, y: dy / (d || 1) * drawn};
      root.style.setProperty("--lx", lean.x + "px");
      root.style.setProperty("--ly", lean.y + "px");
      placeLabel();
    }
    stage.addEventListener("pointermove", read, {passive: true});
    stage.addEventListener("pointerleave", () => {
      root.style.setProperty("--lx", "0px"); root.style.setProperty("--ly", "0px");
    });
    // Resize changes the packing, never the disc or icon size.
    const observer = new ResizeObserver(layout);
    observer.observe(stage);
    mounted.set(root, () => { cancelAnimationFrame(raf); observer.disconnect(); });
    layout();
  }
  function scan() {
    mounted.forEach((dispose, root) => { if (!root.isConnected) { dispose(); mounted.delete(root); } });
    document.querySelectorAll(".onigiri-ready-widget.is-circles .mag").forEach(root => {
      if (!mounted.has(root)) mount(root);
    });
  }
  function start() {
    scan();
    const observer = new MutationObserver(scan);
    observer.observe(document.body, {childList: true, subtree: true});
    window.addEventListener("pagehide", () => { observer.disconnect(); mounted.forEach(dispose => dispose()); mounted.clear(); }, {once: true});
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, {once: true});
  else start();
})();
