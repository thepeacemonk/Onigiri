const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const src = fs.readFileSync(path.join(__dirname, '../web/settings.js'), 'utf8');
function fn(name) {
  const start = src.indexOf('  function ' + name + '(');
  assert(start >= 0, name);
  return src.slice(start, src.indexOf('\n  }', start) + 4);
}
function keys(name) {
  const start = src.indexOf('  const ' + name + ' = {');
  return src.slice(start, src.indexOf('\n  };', start) + 5);
}
const sandbox = { values: {}, CTX: {}, designerFontRole: () => ({color: "#fff"}), imageUrl: (folder, name) => folder + '/' + name,
  el: () => ({style: {}, appendChild() {}}) };
vm.createContext(sandbox);
vm.runInContext(['MAIN_BG_KEYS','OVERVIEW_BG_KEYS','REVIEWER_BG_KEYS'].map(keys).join('\n') + '\n' +
  ['designerPairValue','designerBgSourceState','bbarBackgroundState','designerPaintBackdrop',
   'showWhenMatches','applyDesignerDeckVisibility','designerSidebarSpec','designerNum','isSyncHidden'].map(fn).join('\n') + '\n' +
  'this.api = {bbarBackgroundState, designerPaintBackdrop, applyDesignerDeckVisibility, designerSidebarSpec, isSyncHidden, OVERVIEW_BG_KEYS, REVIEWER_BG_KEYS};', sandbox);
const vals = {modern_menu_background_mode: 'image_color', modern_menu_bg_color_light: '#123456',
  modern_menu_bg_color_dark: '#654321', modern_menu_bg_color_theme_mode: 'separate',
  modern_menu_bg_image_theme_mode: 'separate', modern_menu_background_image_light: 'day.png',
  modern_menu_background_image_dark: 'night.png', modern_menu_background_blur: 35,
  modern_menu_background_opacity: 42, overview_background_mode: 'main', reviewer_background_mode: 'main',
  overview_background_main_blur: 99, overview_background_main_opacity: 99,
  reviewer_background_main_blur: 98, reviewer_background_main_opacity: 98,
  bbar_match_main_blur: 97, bbar_match_main_opacity: 97};
for (const mode of ['main', 'match_overview_bg', 'match_reviewer_bg']) {
  vals.bbar_bg_mode = mode;
  for (const dark of [false, true]) {
    const state = sandbox.api.bbarBackgroundState(vals, dark);
    assert.equal(state.color, dark ? '#654321' : '#123456');
    assert.equal(state.imageName, dark ? 'night.png' : 'day.png');
    assert.equal(state.imageFolder, 'main_bg');
    assert.equal(state.blur, 35);
    assert.equal(state.opacity, 42);
  }
}
for (const key of [sandbox.api.OVERVIEW_BG_KEYS, sandbox.api.REVIEWER_BG_KEYS]) {
  const layers = [];
  sandbox.api.designerPaintBackdrop({appendChild: layer => layers.push(layer)}, vals, true, key);
  assert.equal(layers[1].style.filter, 'blur(6.3px)');
  assert.equal(Number(layers[1].style.opacity), 0.42);
  assert(layers[1].style.backgroundImage.includes('main_bg/night.png'));
}
vals.modern_menu_background_opacity = 0;
vals.modern_menu_background_blur = 0;
assert.equal(sandbox.api.bbarBackgroundState(vals, true).opacity, 0);
assert.equal(sandbox.api.bbarBackgroundState(vals, true).blur, 0);
vals.modern_menu_background_mode = 'slideshow';
vals.modern_menu_slideshow_images = ['slide.png'];
assert.equal(sandbox.api.bbarBackgroundState(vals, true).imageName, 'slide.png');
let hidden, dynamicHidden;
const card = {__fieldsHost: {classList: {toggle: (_, value) => hidden = value}},
  __dynamicControl: {classList: {toggle: (_, value) => dynamicHidden = value}},
  __section: {hide_deck_when: {field: 'overview_background_mode', values: ['main']}}};
sandbox.values.overview_background_mode = 'main';
sandbox.api.applyDesignerDeckVisibility(card);
assert.equal(hidden, true);
assert.equal(dynamicHidden, true);
sandbox.values.overview_background_mode = 'image_color';
sandbox.api.applyDesignerDeckVisibility(card);
assert.equal(hidden, false);
card.__section.hide_deck_when = {};
sandbox.api.applyDesignerDeckVisibility(card);
assert.equal(hidden, false);
console.log('Matched preview inheritance and controls passed.');

const widgetVals = { modern_menu_sidebar_bg_mode: 'custom', modern_menu_sidebar_bg_type: 'image_color',
  modern_menu_sidebar_sync_box_effect: false, modern_menu_sidebar_border_custom: true,
  modern_menu_sidebar_bg_image: 'stale.png', modern_menu_sidebar_radius: 55, modern_menu_sidebar_stroke: 9,
  modern_menu_sidebar_bg_blur: 99, modern_menu_sidebar_bg_opacity: 99,
  widget_box_color_light: '#123456', widget_box_color_dark: '#654321', onigiri_canvas_inset_color_theme_mode: 'separate',
  onigiri_canvas_inset_effect_blur: 35, onigiri_canvas_inset_effect_opacity: 42,
  onigiri_canvas_inset_border_radius: 18, onigiri_canvas_inset_border_width: 2 };
const spec = sandbox.api.designerSidebarSpec(widgetVals, true);
assert.equal(spec.color, '#654321');
assert.equal(spec.blur, 35);
assert.equal(spec.backdropBlur, 7);
assert.equal(spec.opacity, 42);
assert.equal(spec.radius, 18);
assert.equal(spec.stroke, 2);
assert.equal(spec.image, '');
sandbox.values.modern_menu_sidebar_bg_mode = 'custom';
const sidebarCard = {__section: {id: 'sidebar_background', sync_toggle_id: 'modern_menu_sidebar_sync_box_effect',
  sync_hidden_fields: ['modern_menu_sidebar_radius']}};
assert.equal(sandbox.api.isSyncHidden(sidebarCard, 'modern_menu_sidebar_radius'), true);
sandbox.values.modern_menu_sidebar_bg_mode = 'main';
assert.equal(sandbox.api.isSyncHidden(sidebarCard, 'modern_menu_sidebar_radius'), false);
console.log('Match Widgets appearance and stale overrides passed.');
