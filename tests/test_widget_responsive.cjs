const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// Removing the reflow must reproduce the four squeezed columns; returning to
// the full width must restore every saved position without writing settings.
const context = {
    window: {},
    document: { readyState: 'loading', addEventListener() {} },
    console,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/engine.js'), 'utf8'), context);
const engine = context.window.OnigiriEngine;
const tiles = [
    [1, 1, 1, 1], [1, 2, 1, 1], [1, 3, 1, 1], [1, 4, 1, 1],
    [2, 1, 2, 3], [2, 4, 2, 1],
].map(([row, col, rows, cols]) => ({
    style: { gridArea: `${row} / ${col} / span ${rows} / span ${cols}` },
}));
const grid = {
    // Hexagon Land emits a stylesheet beside its root card. It must never
    // consume a dashboard cell while the visible cards are being packed.
    children: [{ style: { gridArea: '' } }, ...tiles],
    dataset: { gridColumns: '4', gridColumnWidth: '250', gridRowHeight: '120' },
    style: { gridTemplateColumns: '', gridTemplateRows: '', justifyContent: '' },
    clientWidth: 500,
};
const originals = tiles.map(tile => tile.style.gridArea);
assert.equal(typeof engine.reflowWidgetGrid, 'function', 'dashboard needs a width-based reflow');
engine.reflowWidgetGrid(grid);
assert.equal(grid.dataset.activeColumns, '2');
assert.equal(tiles[4].style.gridArea, '3 / 1 / span 2 / span 2');
assert.equal(tiles[5].style.gridArea, '5 / 1 / span 2 / span 1');
grid.clientWidth = 215;
engine.reflowWidgetGrid(grid);
assert.equal(grid.dataset.activeColumns, '1');
assert.equal(tiles[4].style.gridArea, '5 / 1 / span 2 / span 1');
grid.clientWidth = 1100;
engine.reflowWidgetGrid(grid);
assert.deepEqual(tiles.map(tile => tile.style.gridArea), originals);
assert.equal(grid.style.gridTemplateColumns, '');
assert.equal(grid.style.gridTemplateRows, '');
console.log('Responsive widgets: 2 columns, 1 column, spans, non-overlap and saved-layout restoration passed.');
