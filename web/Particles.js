/* Particles — adapted from Bencho (MIT), https://bencho.dev/licence.
   Original source and explanatory comments: vendor/bencho/Particles.tsx.
   Each existing day symbol is one particle. Its shape, fill and calendar
   hitbox stay intact; only the symbol moves and springs home. */
(function () {
    'use strict';
    const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

    class Particles {
        constructor(grid) {
            this.grid = grid;
            this.dots = [];
            this.hand = null;
            this.pendingHand = null;
            this.active = new Set();
            this.dirty = new Set();
            this.buckets = new Map();
            this.raf = 0;
            this.pending = 0;
            this.destroyed = false;
            this.connected = grid.isConnected;
            this.visible = true;
            this.motion = window.matchMedia('(prefers-reduced-motion: reduce)');
            this.events = [];
            const listen = (target, name, fn) => {
                target.addEventListener(name, fn, { passive: true });
                this.events.push(() => target.removeEventListener(name, fn));
            };
            listen(grid, 'pointermove', e => {
                if (this.motion.matches || e.pointerType === 'touch') return;
                // Pointer events can arrive several times per display frame.
                // Read layout once in tick(), before any transform writes.
                this.pendingHand = { clientX: e.clientX, clientY: e.clientY };
                this.run();
            });
            listen(grid, 'pointerleave', () => {
                this.pendingHand = null;
                this.hand = null;
                this.run();
            });
            listen(grid, 'pointerdown', e => {
                if (this.motion.matches) return;
                /* the shockwave, then home to the same calendar cells */
                const p = this.where(e);
                for (const d of this.nearby(p, 100)) {
                    const dx = d.x - p.x, dy = d.y - p.y;
                    const dd = Math.hypot(dx, dy);
                    if (dd > 100 || dd < 0.01) continue;
                    const f = (1 - dd / 100) * 12 * 1.12;
                    this.active.add(d);
                    d.vx += dx / dd * f;
                    d.vy += dy / dd * f;
                }
                this.run();
            });
            listen(document, 'visibilitychange', () => {
                this.hand = null;
                this.pendingHand = null;
                if (document.hidden) this.reset(); else this.refresh();
            });
            listen(this.motion, 'change', () => {
                this.reset();
                grid.classList.toggle('ptc', !this.motion.matches);
                if (!this.motion.matches) this.refresh();
            });
            this.resize = new ResizeObserver(() => this.refresh());
            this.resize.observe(grid);
            this.intersection = new IntersectionObserver(entries => {
                this.visible = entries[0].isIntersecting;
                if (this.visible) this.refresh(); else { this.hand = null; this.pendingHand = null; this.reset(); }
            });
            this.intersection.observe(grid);
            // Settings mounts previews off-DOM and later replaces their host.
            // Release document listeners/observers when that mounted grid goes away.
            this.removal = new MutationObserver(() => {
                if (grid.isConnected) this.connected = true;
                else if (this.connected) this.destroy();
            });
            this.removal.observe(document.documentElement, { childList: true, subtree: true });
            this.refresh();
        }

        where(e) {
            const r = this.grid.getBoundingClientRect();
            return { x: e.clientX - r.left, y: e.clientY - r.top };
        }

        refresh() {
            if (this.destroyed || this.pending || this.motion.matches) return;
            this.pending = requestAnimationFrame(() => {
                this.pending = 0;
                this.sample();
            });
        }

        sample() {
            const rect = this.grid.getBoundingClientRect();
            if (!rect.width || !rect.height || this.destroyed || this.motion.matches) return;
            this.reset();
            this.dots = Array.from(this.grid.querySelectorAll('.heatmap-day-cell:not(.empty)')).map(cell => {
                const r = cell.getBoundingClientRect();
                const hx = r.left - rect.left + r.width / 2;
                const hy = r.top - rect.top + r.height / 2;
                return { hx, hy, x: hx, y: hy, vx: 0, vy: 0, lastTransform: '', symbol: cell.querySelector('.day-shape') };
            }).filter(d => d.symbol);
            this.buckets.clear();
            for (const d of this.dots) {
                const key = `${Math.floor(d.hx / 64)},${Math.floor(d.hy / 64)}`;
                if (!this.buckets.has(key)) this.buckets.set(key, []);
                this.buckets.get(key).push(d);
            }
            this.grid.classList.add('ptc');
        }

        nearby(p, radius) {
            const dots = [];
            const minX = Math.floor((p.x - radius) / 64), maxX = Math.floor((p.x + radius) / 64);
            const minY = Math.floor((p.y - radius) / 64), maxY = Math.floor((p.y + radius) / 64);
            for (let x = minX; x <= maxX; x++) {
                for (let y = minY; y <= maxY; y++) {
                    const bucket = this.buckets.get(`${x},${y}`);
                    if (!bucket) continue;
                    for (const d of bucket) {
                        if (Math.abs(d.hx - p.x) <= radius && Math.abs(d.hy - p.y) <= radius) dots.push(d);
                    }
                }
            }
            return dots;
        }

        draw() {
            for (const d of this.dirty) {
                const dx = d.x - d.hx, dy = d.y - d.hy;
                if (!dx && !dy && !d.vx && !d.vy) {
                    if (d.lastTransform) d.symbol.style.removeProperty('transform');
                    d.symbol.style.removeProperty('will-change');
                    d.lastTransform = '';
                    continue;
                }
                // Translate the cached masked symbol; rotating/stretching it
                // every frame makes WebEngine rasterize the SVG mask again.
                const transform = `translate3d(${dx.toFixed(1)}px, ${dy.toFixed(1)}px, 0)`;
                if (transform !== d.lastTransform) {
                    if (!d.lastTransform) d.symbol.style.willChange = 'transform';
                    d.symbol.style.transform = transform;
                    d.lastTransform = transform;
                }
            }
            this.dirty.clear();
        }

        run() {
            if (this.raf || this.destroyed || this.motion.matches || document.hidden || !this.visible || !this.dots.length) return;
            let prev = 0;
            const tick = t => {
                if (!this.grid.isConnected) { this.destroy(); return; }
                /* Frames, not milliseconds. `dt` is expressed in sixtieths of
                   a second and the damping is RAISED to it rather than
                   multiplied by it, so a dropped frame decays the same amount
                   of energy as the two frames it replaced. */
                const dt = prev ? clamp((t - prev) / 16.67, 0, 2.5) : 1;
                prev = t;
                if (this.pendingHand) {
                    this.hand = this.where(this.pendingHand);
                    this.pendingHand = null;
                    // Sleeping symbols outside this area never enter the loop.
                    // Already displaced symbols stay active until back at home.
                    for (const d of this.nearby(this.hand, 80)) this.active.add(d);
                }
                const damping = Math.pow(0.84, dt);
                let busy = false;
                for (const d of this.active) {
                    if (this.hand) {
                        const dx = d.x - this.hand.x, dy = d.y - this.hand.y;
                        const dd = Math.hypot(dx, dy);
                        if (dd < 60 && dd > 0.01) {
                            const f = Math.pow(1 - dd / 60, 2) * 3.3;
                            d.vx += dx / dd * f * dt;
                            d.vy += dy / dd * f * dt;
                        }
                    }
                    d.vx = (d.vx + (d.hx - d.x) * 0.05 * dt) * damping;
                    d.vy = (d.vy + (d.hy - d.y) * 0.05 * dt) * damping;
                    this.dirty.add(d);
                    d.x += d.vx * dt;
                    d.y += d.vy * dt;
                    if (Math.abs(d.hx - d.x) < 0.05 && Math.abs(d.hy - d.y) < 0.05 && Math.abs(d.vx) < 0.02 && Math.abs(d.vy) < 0.02) {
                        d.x = d.hx; d.y = d.hy; d.vx = d.vy = 0;
                        this.active.delete(d);
                    } else if (!this.hand || Math.abs(d.vx) >= 0.02 || Math.abs(d.vy) >= 0.02) {
                        // With a stationary hand, settle at the balance between
                        // pointer push and home spring; movement wakes us again.
                        busy = true;
                    }
                }
                this.draw();
                /* The loop parks itself the moment the value has settled. */
                this.raf = busy ? requestAnimationFrame(tick) : 0;
            };
            this.raf = requestAnimationFrame(tick);
        }

        reset() {
            cancelAnimationFrame(this.raf);
            this.raf = 0;
            for (const d of this.dots) {
                d.x = d.hx; d.y = d.hy; d.vx = d.vy = 0;
                if (d.lastTransform) d.symbol.style.removeProperty('transform');
                d.symbol.style.removeProperty('will-change');
                d.lastTransform = '';
            }
            this.active.clear();
            this.dirty.clear();
        }

        destroy() {
            this.destroyed = true;
            this.reset();
            cancelAnimationFrame(this.pending);
            this.resize.disconnect();
            this.intersection.disconnect();
            this.removal.disconnect();
            this.events.forEach(remove => remove());
            this.grid.classList.remove('ptc');
        }
    }
    window.OnigiriParticles = { Particles };
})();
