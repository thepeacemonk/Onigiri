/* Exercise the shipped spring/lifecycle code without Anki or a browser. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function fixture(reduced = false, locations = [10, 30, 100]) {
    const frames = new Map();
    let id = 0, clock = 0, layoutReads = 0;
    const target = () => ({
        handlers: new Map(),
        addEventListener(name, fn) { this.handlers.set(name, fn); },
        removeEventListener(name) { this.handlers.delete(name); }
    });
    const document = Object.assign(target(), { hidden: false, documentElement: {} });
    const motion = Object.assign(target(), { matches: reduced });
    const symbols = locations.map(() => ({ style: {
        transform: '', removeProperty(name) { this[name.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = ''; }
    } }));
    const classes = new Set();
    const grid = Object.assign(target(), {
        isConnected: true,
        classList: {
            add: name => classes.add(name), remove: name => classes.delete(name),
            toggle(name, on) { if (on) classes.add(name); else classes.delete(name); }
        },
        getBoundingClientRect: () => { layoutReads++; return { left: 0, top: 0, width: 4000, height: 100 }; },
        querySelectorAll: () => locations.map((x, i) => ({
            getBoundingClientRect: () => ({ left: x, top: 30, width: 10, height: 10 }),
            querySelector: () => symbols[i]
        }))
    });
    const observers = [];
    class Observer {
        constructor(fn) { this.fn = fn; this.disconnected = false; observers.push(this); }
        observe() {}
        disconnect() { this.disconnected = true; }
    }
    const context = {
        window: { matchMedia: () => motion }, document,
        ResizeObserver: Observer, IntersectionObserver: Observer, MutationObserver: Observer,
        requestAnimationFrame(fn) { frames.set(++id, fn); return id; },
        cancelAnimationFrame(key) { frames.delete(key); }
    };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../web/Particles.js'), 'utf8'), context);
    const particles = new context.window.OnigiriParticles.Particles(grid);
    const step = () => {
        const callbacks = [...frames.values()]; frames.clear(); clock += 16.67;
        callbacks.forEach(fn => fn(clock));
    };
    step();
    return { particles, grid, symbols, motion, document, observers, frames, step, classes, layoutReads: () => layoutReads };
}

const f = fixture();
assert.equal(f.particles.dots.length, 3, 'one moving object per original day symbol');
f.grid.handlers.get('pointermove')({ clientX: 20, clientY: 35, pointerType: 'mouse' });
f.step();
assert.ok(f.symbols[0].style.transform.includes('translate3d('), 'hover moves the intact symbol');
assert.equal(f.symbols[2].style.transform, '', 'distant days remain unchanged');
for (let i = 0; i < 600 && f.frames.size; i++) f.step();
assert.equal(f.frames.size, 0, 'stationary hover settles without a permanent loop');
f.grid.handlers.get('pointermove')({ clientX: 35, clientY: 35, pointerType: 'mouse' });
assert.ok(f.frames.size, 'moving the pointer wakes the loop again');
f.grid.handlers.get('pointerleave')();
for (let i = 0; i < 600 && f.frames.size; i++) f.step();
assert.equal(f.frames.size, 0, 'spring loop stops when settled');
assert.ok(f.symbols.every(s => s.style.transform === ''), 'all symbols return to their exact homes');

f.grid.handlers.get('pointerdown')({ clientX: 20, clientY: 35 });
f.step();
assert.ok(f.symbols[0].style.transform, 'press sends a shockwave through symbols');
f.document.hidden = true;
f.document.handlers.get('visibilitychange')();
assert.equal(f.frames.size, 0, 'hidden document stops animating');
assert.ok(f.symbols.every(s => !s.style.transform), 'hiding resets symbols');
f.particles.destroy();
assert.equal(f.grid.handlers.size, 0, 'destroy removes pointer listeners');
assert.equal(f.document.handlers.size, 0, 'destroy removes document listener');
assert.ok(f.observers.every(o => o.disconnected), 'destroy releases all observers');
assert.equal(f.classes.has('ptc'), false);

const r = fixture(true);
assert.equal(r.frames.size, 0, 'initial reduced motion remains static');
r.grid.handlers.get('pointermove')({ clientX: 20, clientY: 35, pointerType: 'mouse' });
assert.equal(r.frames.size, 0);
r.motion.matches = false;
r.motion.handlers.get('change')();
r.step();
assert.equal(r.particles.dots.length, 3, 'motion can be enabled without rebuilding');
r.grid.handlers.get('pointermove')({ clientX: 20, clientY: 35, pointerType: 'mouse' });
r.step();
r.motion.matches = true;
r.motion.handlers.get('change')();
assert.ok(r.symbols.every(s => !s.style.transform), 'live reduced motion restores original symbols');
assert.equal(r.frames.size, 0);
r.particles.destroy();
const large = fixture(false, Array.from({ length: 365 }, (_, i) => i * 10));
const readsBefore = large.layoutReads();
for (let i = 0; i < 100; i++) {
    large.grid.handlers.get('pointermove')({ clientX: 200 + i, clientY: 35, pointerType: 'mouse' });
}
assert.equal(large.frames.size, 1, '100 pointer events produce one scheduled frame');
assert.equal(large.layoutReads(), readsBefore, 'pointer handlers do not force layout');
large.step();
assert.equal(large.layoutReads(), readsBefore + 1, 'one layout read per pointer frame');
assert.ok(large.particles.active.size < 20, 'full year updates only nearby day symbols');
assert.equal(large.symbols[300].style.transform, '', 'distant symbols never receive transforms');
large.grid.handlers.get('pointerleave')();
for (let i = 0; i < 600 && large.frames.size; i++) large.step();
assert.equal(large.particles.active.size, 0, 'settled symbols leave the active set');
assert.ok(large.symbols.every(s => !s.style.willChange), 'GPU layer hints are released after settling');
large.particles.destroy();
console.log('PASS: intact symbols, repulsion, shockwave, spring settling, reduced motion and cleanup');
