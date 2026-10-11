const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../web/settings.js'), 'utf8');
function fn(name, indent = '  ') {
  const start = source.indexOf(indent + 'function ' + name + '(');
  assert(start >= 0, name);
  return source.slice(start, source.indexOf('\n' + indent + '}', start) + indent.length + 2);
}
function node(tag, className, text = '') {
  return { tag, className, textContent: text, children: [], style: {}, attrs: {}, events: {},
    appendChild(child) { this.children.push(child); },
    setAttribute(key, value) { this.attrs[key] = value; },
    addEventListener(event, callback) { this.events[event] = callback; },
    set innerHTML(value) { this.children = []; this.html = value; }
  };
}
const clicks = [];
const field = {id: 'modern_menu_icon_color_folder', type: 'color_pair', alwaysSplit: true,
  lightField: 'modern_menu_icon_color_folder_light', darkField: 'modern_menu_icon_color_folder_dark',
  fallbackLight: 'sb_icon_color_light', fallbackDark: 'sb_icon_color_dark'};
const sandbox = { values: { sb_icon_color_light: '#333333', sb_icon_color_dark: '#E0E0E0',
    modern_menu_icon_color_folder_light: '', modern_menu_icon_color_folder_dark: '' },
  CTX: {dark: false}, str: (_, fallback) => fallback, el: node,
  document: {createTextNode: text => ({textContent: text})},
  OSW_SUN_ICON: '<svg>sun</svg>', OSW_MOON_ICON: '<svg>moon</svg>',
  bridge() {}, openColorPickerById: (...args) => clicks.push(args),
  iconPicker: null, companionIds: ['modern_menu_icon_color_folder'],
  fieldById: {[field.id]: field} };
vm.createContext(sandbox);
vm.runInContext(['pairAvailable', 'pairLinked', 'imageTargets', 'imageValue', 'iconColorFallback',
  'pairColorFallback', 'renderIconPopupColorSlots', 'sidebarIconTint'].map(name => fn(name)).join('\n') +
  '\n' + fn('currentTint', '    ') + '\nthis.api = {imageTargets, renderIconPopupColorSlots, currentTint, sidebarIconTint};', sandbox);

// Equal values and a linked sidebar palette must never hide either tint slot.
field.themeModeField = 'onigiri_sidebar_deck_colors_theme_mode';
sandbox.values[field.themeModeField] = 'single';
assert.deepEqual(Array.from(sandbox.api.imageTargets(field), t => t.role), ['light', 'dark']);
for (const dark of [false, true]) {
  sandbox.CTX.dark = dark;
  const host = sandbox.api.renderIconPopupColorSlots(field);
  const slots = host.children[0].children;
  assert.equal(slots.length, 2);
  assert.equal(slots[0].attrs['aria-label'], 'Light color');
  assert.equal(slots[1].attrs['aria-label'], 'Dark color');
  assert.equal(slots[0].children[0].style.background, '#333333');
  assert.equal(slots[1].children[0].style.background, '#E0E0E0');
  assert.equal(slots[0].children[1].children[0].children[0].textContent, 'Light');
  assert.equal(slots[1].children[1].children[0].children[0].textContent, 'Dark');
  slots.forEach(slot => slot.events.click());
  assert.equal(clicks.at(-2)[0], field.lightField);
  assert.equal(clicks.at(-1)[0], field.darkField);
  assert.equal(clicks.at(-1)[1], '#E0E0E0');
  assert.equal(sandbox.api.currentTint(), dark ? '#E0E0E0' : '#333333');
}
sandbox.values[field.lightField] = '#94B9C4';
sandbox.values[field.darkField] = '#DDEEFF';
assert.equal(sandbox.api.currentTint(), '#DDEEFF');
sandbox.CTX.dark = false;
assert.equal(sandbox.api.currentTint(), '#94B9C4');
const tint = sandbox.api.sidebarIconTint;
assert.equal(tint(sandbox.values, field.id, true), '#DDEEFF');
assert.equal(tint(sandbox.values, field.id, false), '#94B9C4');
assert.equal(tint({[field.id]: '#94B9C4'}, field.id, true), '#94B9C4');
assert.equal(tint({[field.id]: '#94B9C4', [field.darkField]: ''}, field.id, true), '');
console.log('Light/dark icon slots, click bindings, palette fallbacks and previews passed.');
