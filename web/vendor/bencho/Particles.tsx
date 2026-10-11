import { useEffect, useRef } from "react";

/* ══ Particles ════════════════════════════════════════════
   A shape made of dots. Move over it and the dots are pushed
   away from the pointer and spring home behind it; press and a
   shockwave throws them out, and they gather again into the
   NEXT shape — circle, square, flower, round again.

   ── ONE SET OF DOTS, MANY SHAPES ────────────────────────
   The dots never change, only where home is. Every shape is
   sampled to the same number of points, and a change of shape
   pairs each dot with a new home by angle round the middle, so
   the swarm sweeps round into the new outline rather than
   crossing itself.

   ── STRETCHED BY SPEED ──────────────────────────────────
   A dot at rest is round; a moving one is drawn a little long
   along the way it is going, which is what makes a burst read
   as a splash rather than a scatter of points. */

/* ── inlined from lab/spring ──────────────────────── */
/* ── one spring, for everything that settles ───────────────
   The maths was already on this bench twice, copied by hand:
   Humidity's wheel and Brightness's column both accumulate
   velocity toward a target, damp it, and snap when both the
   delta and the velocity fall under 0.02. Two copies is a
   coincidence; five would be a policy, so it comes out here
   before the elastic blocks are written against it.

   The two shipped copies are deliberately NOT refactored onto
   this. They work, they are tuned, and rewriting the innards
   of two live components to prove a point about duplication
   is how a good afternoon becomes a bad one. This is the one
   new code uses.

   Frames, not milliseconds. `dt` is expressed in sixtieths of
   a second and the damping is RAISED to it rather than
   multiplied by it, so a dropped frame decays the same amount
   of energy as the two frames it replaced. Multiplying is the
   version that makes a spring behave differently on a busy
   page, which is the hardest kind of bug to see.

   The loop parks itself the moment the value has settled.
   CLAUDE.md is not complimentary about the one permanent
   requestAnimationFrame already on this bench and there is no
   case for five more. */

/* Read once, the way the wheel and the pill nav do. A
   preference, not a live input. */
const stillness = () =>
  typeof window !== "undefined" &&
  !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

const W = 480;
const H = 400;
const CX = W / 2;
const CY = H / 2;
/* how many dots every shape is sampled to */
const N = 720;

export const SHAPES = ["Circle", "Square", "Flower"] as const;
type Shape = (typeof SHAPES)[number];

type Dot = { hx: number; hy: number; x: number; y: number; vx: number; vy: number };

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

function outline(s: Shape): Path2D {
  const p = new Path2D();
  if (s === "Circle") p.arc(CX, CY, 150, 0, Math.PI * 2);
  else if (s === "Square") p.roundRect(CX - 140, CY - 140, 280, 280, 36);
  else {
    /* five round petals round a smaller middle — circles drawn
       the same way round, so the fill is their union. Petals
       just touching their neighbours, so the notches between
       them read at the dots' own grain */
    for (let i = 0; i < 5; i++) {
      const a = -Math.PI / 2 + (i * Math.PI * 2) / 5;
      const x = CX + Math.cos(a) * 104;
      const y = CY + 8 + Math.sin(a) * 104;
      p.moveTo(x + 60, y);
      p.arc(x, y, 60, 0, Math.PI * 2);
    }
    p.moveTo(CX + 58, CY + 8);
    p.arc(CX, CY + 8, 58, 0, Math.PI * 2);
  }
  return p;
}

/* ── N points, spread evenly over the inside of a shape ──
   A hex grid spaced so the shape holds about N of them — its
   area over N, which is the spacing that fills it evenly — then
   trimmed or topped up to exactly N. It was a fixed fine grid
   thinned by a stride, and the stride beat against the grid:
   the circle came out in zigzag bands. */
function homes(s: Shape): [number, number][] {
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const g = c.getContext("2d")!;
  const path = outline(s);
  let area = 0;
  for (let y = 1; y < H; y += 2) for (let x = 1; x < W; x += 2) if (g.isPointInPath(path, x, y)) area += 4;
  const sp = Math.sqrt((area / N) * (2 / Math.sqrt(3)));
  const rowH = (sp * Math.sqrt(3)) / 2;
  const pts: [number, number][] = [];
  for (let y = rowH / 2, row = 0; y < H; y += rowH, row++) {
    for (let x = sp / 2 + (row % 2) * (sp / 2); x < W; x += sp) {
      if (g.isPointInPath(path, x, y)) pts.push([x, y]);
    }
  }
  /* within a few of N either way; drop evenly or repeat evenly */
  const out: [number, number][] = [];
  for (let i = 0; i < N; i++) out.push(pts[Math.floor((i * pts.length) / N)]);
  return out;
}

const angle = (x: number, y: number) => Math.atan2(y - CY, x - CX);

export function Particles({
  /* the shape it opens as */
  shape = "Circle",
  /* how far the pointer's push reaches, px */
  reach = 80,
  /* how hard it pushes, 0..100 */
  force = 60,
  /* the size of a dot */
  grain = "Fine",
}: {
  shape?: string;
  reach?: number;
  force?: number;
  grain?: string;
} = {}) {
  const still = stillness();
  const cv = useRef<HTMLCanvasElement | null>(null);
  const dots = useRef<Dot[]>([]);
  const at = useRef<Shape>("Circle");
  const hand = useRef<{ x: number; y: number } | null>(null);
  const raf = useRef(0);
  const knobs = useRef({ reach, force, grain });
  knobs.current = { reach, force, grain };

  /* ── give every dot a home in a shape ────────────────── */
  const become = (s: Shape) => {
    at.current = s;
    const next = homes(s);
    const ds = dots.current;
    if (!ds.length) {
      dots.current = next.map(([x, y]) => ({ hx: x, hy: y, x, y, vx: 0, vy: 0 }));
      return;
    }
    /* pair by angle round the middle, so the swarm sweeps */
    const a = ds.map((d, i) => [angle(d.x, d.y), i] as const).sort((p, q) => p[0] - q[0]);
    const b = next.map((h, i) => [angle(h[0], h[1]), i] as const).sort((p, q) => p[0] - q[0]);
    a.forEach(([, di], k) => {
      const h = next[b[k][1]];
      ds[di].hx = h[0];
      ds[di].hy = h[1];
      if (still) { ds[di].x = h[0]; ds[di].y = h[1]; }
    });
  };

  const draw = () => {
    const c = cv.current;
    if (!c) return;
    const x = c.getContext("2d")!;
    const k = c.width / W;
    x.setTransform(k, 0, 0, k, 0, 0);
    x.clearRect(0, 0, W, H);
    x.fillStyle = getComputedStyle(c).color;
    const r = knobs.current.grain === "Coarse" ? 2.7 : 1.9;
    x.beginPath();
    for (const d of dots.current) {
      const sp = Math.hypot(d.vx, d.vy);
      if (sp < 0.3) {
        x.moveTo(d.x + r, d.y);
        x.arc(d.x, d.y, r, 0, Math.PI * 2);
      } else {
        /* long along its path, a little thin across it */
        const s = Math.min(2.6, 1 + sp * 0.12);
        const rot = Math.atan2(d.vy, d.vx);
        x.moveTo(d.x + Math.cos(rot) * r * s, d.y + Math.sin(rot) * r * s);
        x.ellipse(d.x, d.y, r * s, r / Math.sqrt(s), rot, 0, Math.PI * 2);
      }
    }
    x.fill();
  };

  const run = () => {
    if (raf.current) return;
    let prev = 0;
    const tick = (t: number) => {
      const dt = prev ? clamp((t - prev) / 16.67, 0, 2.5) : 1;
      prev = t;
      const h = hand.current;
      const R = clamp(knobs.current.reach, 30, 160);
      const S = (clamp(knobs.current.force, 0, 100) / 100) * 11;
      let busy = !!h;
      for (const d of dots.current) {
        if (h) {
          const dx = d.x - h.x;
          const dy = d.y - h.y;
          const dd = Math.hypot(dx, dy);
          if (dd < R && dd > 0.01) {
            const f = Math.pow(1 - dd / R, 2) * S;
            d.vx += (dx / dd) * f * dt;
            d.vy += (dy / dd) * f * dt;
          }
        }
        d.vx = (d.vx + (d.hx - d.x) * 0.05 * dt) * Math.pow(0.84, dt);
        d.vy = (d.vy + (d.hy - d.y) * 0.05 * dt) * Math.pow(0.84, dt);
        d.x += d.vx * dt;
        d.y += d.vy * dt;
        if (Math.abs(d.hx - d.x) < 0.05 && Math.abs(d.hy - d.y) < 0.05 && Math.abs(d.vx) < 0.02 && Math.abs(d.vy) < 0.02) {
          d.x = d.hx; d.y = d.hy; d.vx = 0; d.vy = 0;
        } else busy = true;
      }
      draw();
      raf.current = busy ? requestAnimationFrame(tick) : 0;
    };
    raf.current = requestAnimationFrame(tick);
  };

  /* set up once, then follow the Shape knob */
  useEffect(() => {
    const c = cv.current;
    if (!c) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = Math.round(W * dpr);
    c.height = Math.round(H * dpr);
  }, []);
  useEffect(() => {
    const s = (SHAPES as readonly string[]).includes(shape) ? (shape as Shape) : "Circle";
    become(s);
    draw();
    run();
  }, [shape]);
  useEffect(() => { draw(); }, [grain]);
  useEffect(() => () => { cancelAnimationFrame(raf.current); raf.current = 0; }, []);
  useEffect(() => {
    const mo = new MutationObserver(() => draw());
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => mo.disconnect();
  }, []);

  const where = (e: React.PointerEvent) => {
    const r = e.currentTarget.getBoundingClientRect();
    const k = r.width / W;
    return { x: (e.clientX - r.left) / k, y: (e.clientY - r.top) / k };
  };

  return (
    <div className="ptc">
      <canvas
        ref={cv}
        className="ptc-canvas"
        style={{ width: W, height: H }}
        role="img"
        aria-label="A shape made of dots. Move over it; press to change the shape."
        onPointerMove={(e) => {
          if (still) return;
          hand.current = where(e);
          run();
        }}
        onPointerLeave={() => { hand.current = null; run(); }}
        onPointerDown={(e) => {
          /* the shockwave, then the next shape */
          const p = where(e);
          if (!still) {
            const S = 0.4 + (clamp(knobs.current.force, 0, 100) / 100) * 1.2;
            for (const d of dots.current) {
              const dx = d.x - p.x;
              const dy = d.y - p.y;
              const dd = Math.hypot(dx, dy);
              if (dd > 200 || dd < 0.01) continue;
              const f = (1 - dd / 200) * 30 * S;
              d.vx += (dx / dd) * f;
              d.vy += (dy / dd) * f;
            }
          }
          become(SHAPES[(SHAPES.indexOf(at.current) + 1) % SHAPES.length]);
          draw();
          run();
        }}
      />
    </div>
  );
}

