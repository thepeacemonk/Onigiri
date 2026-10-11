/* Eye tracker adapted from Bencho's supplied Watcher / EyeTracker source.
   Copyright (c) Bencho. MIT licence: vendor/bencho/LICENSE.

   THE EYES ARE ON THE BALL, NOT IN FRONT OF IT
   Each eye is a point on the sphere's surface: looking left turns the ball,
   so the one heading for the rim moves less and narrows as it turns away.
   One turn (yaw and pitch) is the state, sprung toward the pointer; both
   eyes are read off it, so they can never disagree.

   This adapter keeps the onigiri artwork instead of drawing Bencho's body.
   Its pale rice carries round dark eyes and a smile inspired by Onigiri-san.
   Written straight to the DOM every frame: a pointer move is not a render. */
(function () {
    'use strict';

    const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
    const NS = 'http://www.w3.org/2000/svg';
    const R = 18;
    const GAP = 0.43;
    const TILT = 64;
    const HEART = 'M0 5.5C-1 4.4-7 .5-7-3.4C-7-7.5-2-9 0-5.5C2-9 7-7.5 7-3.4C7 .5 1 4.4 0 5.5Z';
    // The nori's straight upper edge runs from (52.43, 68.68) to
    // (82.82, 48.07) in the supplied 128-unit SVG. Center the face on its
    // perpendicular axis, 18 units above it, instead of eyeballing a position.
    const faceAngle = Math.atan2(-20.61, 30.39);
    const FACE = {
        x: 67.625 + Math.sin(faceAngle) * 18,
        y: 58.375 - Math.cos(faceAngle) * 18,
        angle: faceAngle
    };

    class EyeTracker {
        constructor(root, options = {}) {
            this.root = root;
            this.frame = options.frame || root.parentElement;
            this.reactions = Array.from(options.reactions || []);
            this.motion = window.matchMedia('(prefers-reduced-motion: reduce)');
            this.turn = { x: 0, y: 0, vx: 0, vy: 0, tx: 0, ty: 0 };
            this.raf = 0;
            this.previous = 0;
            this.blinkStart = null;
            this.blinkTimer = 0;
            this.destroyed = false;
            this.listeners = [];
            this.svg = this.node('svg', { class: 'eyt-face', viewBox: '0 0 128 128', 'aria-hidden': 'true' });
            const face = this.node('g', {
                transform: `translate(${FACE.x.toFixed(3)} ${FACE.y.toFixed(3)}) rotate(${(FACE.angle * 180 / Math.PI).toFixed(3)})`
            });
            this.eyes = [-1, 1].map(() => {
                const group = this.node('g');
                const eye = this.node('rect', { class: 'eyt-eye' });
                const heart = this.node('path', { class: 'eyt-heart', d: HEART });
                group.append(eye, heart);
                face.append(group);
                return { group, eye, heart };
            });
            this.smile = this.node('path', { class: 'eyt-smile', d: 'M-5 9Q0 14 5 9' });
            face.append(this.smile);
            this.svg.append(face);
            root.append(this.svg);
            this.tick = this.tick.bind(this);
            this.listen(window, 'pointermove', event => this.aim(event), { passive: true });
            this.listen(document.documentElement, 'pointerleave', () => this.rest());
            this.listen(window, 'blur', () => this.rest());
            if (this.frame) this.listen(this.frame, 'scroll', () => this.rest(), { passive: true });
            this.reactions.forEach(link => {
                ['pointerenter', 'pointerleave', 'focus', 'blur'].forEach(type => {
                    this.listen(link, type, () => this.react());
                });
            });
            this.listen(this.motion, 'change', () => {
                this.blinkStart = null;
                clearTimeout(this.blinkTimer);
                this.wake();
                this.scheduleBlink();
            });
            this.listen(document, 'visibilitychange', () => {
                if (document.hidden) {
                    cancelAnimationFrame(this.raf);
                    this.raf = 0;
                    clearTimeout(this.blinkTimer);
                    this.turn.tx = this.turn.ty = 0;
                } else {
                    this.wake();
                    this.scheduleBlink();
                }
            });
            this.listen(window, 'pagehide', () => this.destroy());
            this.draw(performance.now());
            this.scheduleBlink();
        }

        node(tag, attributes = {}) {
            const node = document.createElementNS(NS, tag);
            Object.entries(attributes).forEach(([name, value]) => node.setAttribute(name, value));
            return node;
        }

        listen(target, type, handler, options) {
            target.addEventListener(type, handler, options);
            this.listeners.push(() => target.removeEventListener(type, handler, options));
        }

        aim(event) {
            if (!this.frame) return;
            const frame = this.frame.getBoundingClientRect();
            if (event.clientX < frame.left || event.clientX > frame.right ||
                event.clientY < frame.top || event.clientY > frame.bottom) {
                this.rest();
                return;
            }
            const box = this.root.getBoundingClientRect();
            const dx = event.clientX - (box.left + box.width * FACE.x / 128);
            const dy = event.clientY - (box.top + box.height * FACE.y / 128);
            const distance = Math.hypot(dx, dy) || 1;
            const reach = Math.max(60, Math.min(frame.width, frame.height) * .28);
            // Keep the glance inside the pale rice and clear of the smile.
            const far = Math.tanh(distance / reach) * .28;
            // Match the original icon's tilt; leave room above the little smile.
            const angle = -FACE.angle;
            this.turn.tx = (dx * Math.cos(angle) - dy * Math.sin(angle)) / distance * far;
            this.turn.ty = clamp((dx * Math.sin(angle) + dy * Math.cos(angle)) / distance * far, -.25, .16);
            this.wake();
        }

        rest() {
            this.turn.tx = this.turn.ty = 0;
            this.wake();
        }

        react() {
            const loving = this.reactions.some(link => link.matches(':hover') || link === document.activeElement);
            this.root.classList.toggle('is-loving', loving);
            this.blinkStart = null;
            this.draw(performance.now());
        }

        wake() {
            if (this.destroyed || document.hidden || this.raf) return;
            this.previous = 0;
            this.raf = requestAnimationFrame(this.tick);
        }

        scheduleBlink() {
            clearTimeout(this.blinkTimer);
            if (this.destroyed || document.hidden || this.motion.matches) return;
            this.blinkTimer = window.setTimeout(() => {
                if (!this.root.classList.contains('is-loving')) {
                    this.blinkStart = performance.now();
                    this.wake();
                }
                this.scheduleBlink();
            }, 2600 + Math.random() * 3200);
        }

        tick(now) {
            this.raf = 0;
            /* Frames, not milliseconds. dt is expressed in sixtieths of a
               second. Damping is RAISED to it, so a dropped frame decays the
               same amount of energy as the two frames it replaced. */
            const dt = this.previous ? Math.min(2.5, (now - this.previous) / 16.67) : 1;
            this.previous = now;
            const turn = this.turn;
            if (this.motion.matches) {
                turn.x = turn.tx;
                turn.y = turn.ty;
                turn.vx = turn.vy = 0;
            } else {
                const damping = Math.pow(.78, dt);
                turn.vx = (turn.vx + (turn.tx - turn.x) * .06 * dt) * damping;
                turn.vy = (turn.vy + (turn.ty - turn.y) * .06 * dt) * damping;
                turn.x += turn.vx * dt;
                turn.y += turn.vy * dt;
            }
            const settled = Math.abs(turn.x - turn.tx) + Math.abs(turn.y - turn.ty) +
                Math.abs(turn.vx) + Math.abs(turn.vy) < .002;
            if (settled) {
                turn.x = turn.tx;
                turn.y = turn.ty;
                turn.vx = turn.vy = 0;
            }
            this.draw(now);
            // The frame loop parks when settled; a timer wakes it for one blink.
            if (!settled || this.blinkStart !== null) this.raf = requestAnimationFrame(this.tick);
        }

        draw(now) {
            let lid = 1;
            if (this.blinkStart !== null) {
                const elapsed = now - this.blinkStart;
                // A blink is 160ms down and up, as a squash on each eye.
                if (elapsed < 160) lid = 1 - .9 * Math.sin(elapsed / 160 * Math.PI);
                else this.blinkStart = null;
            }
            const turn = this.turn;
            const yaw = Math.asin(clamp(turn.x, -.92, .92));
            const pitch = -Math.asin(clamp(turn.y, -.92, .92));
            const cy = Math.cos(yaw), sy = Math.sin(yaw);
            const cp = Math.cos(pitch), sp = Math.sin(pitch);
            const tilt = TILT * turn.x * turn.y;
            this.smile.setAttribute('transform', `translate(${(turn.x * R * .35).toFixed(2)} ${(turn.y * R * .35).toFixed(2)})`);
            [-GAP, GAP].forEach((x0, index) => {
                const { group, eye, heart } = this.eyes[index];
                // Each eye is a point on the unit sphere, turned with the face.
                const z0 = Math.sqrt(1 - x0 * x0);
                const x1 = x0 * cy + z0 * sy;
                const z1 = -x0 * sy + z0 * cy;
                const y2 = -z1 * sp;
                const z2 = z1 * cp;
                // Depth narrows the eye near the rim, rather than sliding stickers.
                const near = clamp(z2, 0, 1);
                const k = .45 + .55 * near;
                const sx = k * (.7 + .3 * near);
                const width = 8 * sx;
                const height = Math.max(.6, 8 * k * lid);
                /* The size is written as a size, never as a scale. This keeps
                   every rounded corner circular while an eye blinks or narrows. */
                eye.setAttribute('x', (-width / 2).toFixed(2));
                eye.setAttribute('y', (-height / 2).toFixed(2));
                eye.setAttribute('width', width.toFixed(2));
                eye.setAttribute('height', height.toFixed(2));
                eye.setAttribute('rx', Math.min(4, width / 2, height / 2).toFixed(2));
                heart.setAttribute('transform', `scale(${(sx * .75).toFixed(3)} ${(k * .75).toFixed(3)})`);
                group.setAttribute('transform', `translate(${(x1 * R).toFixed(2)} ${(y2 * R).toFixed(2)}) rotate(${tilt.toFixed(2)})`);
                group.style.opacity = z2 < .05 ? '0' : '1';
            });
        }

        destroy() {
            this.destroyed = true;
            cancelAnimationFrame(this.raf);
            clearTimeout(this.blinkTimer);
            this.listeners.forEach(remove => remove());
            this.listeners = [];
            this.svg.remove();
            this.root.classList.remove('is-loving');
        }
    }

    window.EyeTracker = EyeTracker;
})();
