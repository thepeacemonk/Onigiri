const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../web/settings.js'), 'utf8');
function fn(name) {
  const start = source.indexOf('  function ' + name + '(');
  assert(start >= 0, name);
  return source.slice(start, source.indexOf('\n  }', start) + 4);
}
class Node {
  constructor(tag, className, text) {
    this.tag = tag; this.className = className || ''; this.textContent = text || '';
    this.style = {}; this.children = []; this.attributes = {};
    this.classList = {add() {}};
  }
  set innerHTML(value) { this.children = []; }
  appendChild(child) { this.children.push(child); }
  setAttribute(key, value) { this.attributes[key] = value; if (key === 'class') this.className = value; }
}
function find(node, selector) {
  if (node.className.split(' ').includes(selector)) return node;
  for (const child of node.children) { const result = find(child, selector); if (result) return result; }
}
const ctx = {
  values: {modern_menu_profile_type: 'ring', userName: 'Quifrey', g_profile_level_game: 'nook',
    modern_menu_profile_picture_mode: 'custom', g_rl_dynamic_chip_colors: true,
    g_rl_chip_progress_light: '#819b26', g_rl_chip_progress_dark: '#aadd44'},
  CTX: {profileLevel: {enabled: true, level: 7, fraction: 0.42, game: 'nook', sourceName: 'Nook'},
    chipColors: {light: {progress: '#old'}}, chipDefaults: {light: {progress: '#123456'}, dark: {progress: '#654321'}}},
  SETTINGS_MODE_PARITY: true, settingsComplexity: 'advanced', fieldById: {},
  el: (tag, cls, text) => new Node(tag, cls, text), str: (key, fallback) => fallback,
  document: {createElementNS: (_, tag) => new Node(tag), hidden: false, querySelector: () => true},
  qtColorToCss: value => value, qtColorRgb: value => value, readableTextColor: () => '#ffffff',
  profileAccentColor: () => '#819b26', resolveIconAssetUrl: () => '', imageUrl: () => '',
  iconValue: () => '',
  pending: {}, inFlight: false, profileContextInFlight: false, profileContextRevision: 0,
  repaints: 0, updateProfilePreview() { ctx.repaints++; }, updateDesignerPreviews() {},
};
vm.createContext(ctx);
vm.runInContext(['themedAsset', 'nookChipColors', 'paintProfileItem', 'applyProfileContext',
  'refreshLiveProfileContext'].map(fn).join('\n'), ctx);
const item = new Node('div');
ctx.paintProfileItem(item, false);
assert.equal(find(item, 'osw-preview-sub-text').textContent, 'Level 7 · Nook');
let circle = find(item, 'osw-preview-ring-svg').children[1];
assert.equal(circle.attributes.stroke, '#819b26');
assert.equal(circle.attributes['stroke-dashoffset'], (2 * Math.PI * 21 * 0.58).toFixed(2));
ctx.paintProfileItem(item, true);
assert.equal(find(item, 'osw-preview-ring-svg').children[1].attributes.stroke, '#aadd44');
ctx.values.g_rl_dynamic_chip_colors = false;
ctx.values.g_rl_chip_progress = '#112233';
ctx.paintProfileItem(item, true);
assert.equal(find(item, 'osw-preview-ring-svg').children[1].attributes.stroke, '#112233');
ctx.values.g_rl_chip_progress = '';
assert.equal(ctx.nookChipColors(ctx.values, true).progress, '#654321');
ctx.CTX.profileLevel.enabled = false;
ctx.paintProfileItem(item, false);
assert.equal(find(item, 'osw-preview-sub-text'), undefined);
circle = find(item, 'osw-preview-ring-svg').children[1];
assert.equal(circle.attributes['stroke-dashoffset'], (2 * Math.PI * 21).toFixed(2));
ctx.values.modern_menu_profile_type = 'bar';
ctx.paintProfileItem(item, false);
assert.equal(find(item, 'restaurant-level-chip'), undefined);
ctx.values.modern_menu_profile_type = 'minimal';
ctx.paintProfileItem(item, false);
assert.equal(find(item, 'osw-preview-minimal-fill').style.width, '0.0%');
ctx.CTX.profileLevel.enabled = true;
ctx.values.g_profile_level_game = 'hexagon';
ctx.values.modern_menu_profile_type = 'ring';
ctx.paintProfileItem(item, false);
assert.equal(find(item, 'osw-preview-sub-text'), undefined);

(async () => {
  const snapshot = {profileLevel: {enabled: true, game: 'hexagon', sourceName: 'Hexagon Land', level: 3, fraction: 0.1},
    chipColors: {}, chipDefaults: {light: {progress: '#819b26'}}};
  let resolve;
  let requests = 0;
  ctx.call = command => { assert.equal(command, 'osw:profile_context:'); requests++; return new Promise(r => resolve = r); };
  ctx.refreshLiveProfileContext();
  ctx.refreshLiveProfileContext();
  assert.equal(requests, 1);
  resolve(snapshot); await Promise.resolve();
  assert.equal(ctx.CTX.profileLevel.level, 3);
  assert.equal(ctx.repaints, 1);
  ctx.applyProfileContext(snapshot);
  assert.equal(ctx.repaints, 1);
  ctx.refreshLiveProfileContext();
  ctx.profileContextRevision++;
  resolve({...snapshot, profileLevel: {...snapshot.profileLevel, level: 2}}); await Promise.resolve();
  assert.equal(ctx.CTX.profileLevel.level, 3, 'An old reply must not replace newer state');
  ctx.pending.userName = 'New name';
  ctx.refreshLiveProfileContext();
  assert.equal(requests, 2);
  ctx.pending = {}; ctx.document.hidden = true;
  ctx.refreshLiveProfileContext();
  assert.equal(requests, 2);
  console.log('Profile preview data, palettes, disabled sources and refresh ordering passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
