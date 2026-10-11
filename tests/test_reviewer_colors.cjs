// Chromium stays headless; no Anki profile or saved configuration is touched.
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const {execFileSync} = require('child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(process.env.ONIGIRI_SETTINGS_JS || path.join(root, 'web/settings.js'), 'utf8');

// Use the production Reviewer schema and field serializer, with an in-memory
// default-value store. Images and font roles are outside this regression.
const section = JSON.parse(execFileSync('python3', ['-c', `
import ast, json, types
from pathlib import Path
root = Path.cwd()
env = {'tr': lambda key, fallback='': fallback,
       '_image_field': lambda id, *args, **kwargs: {'id': id, 'type': 'hidden'},
       '_attach_compact_font_roles': lambda section, *args: section}
def load(file, names):
    tree = ast.parse((root / file).read_text())
    body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(ast.Module(body=body, type_ignores=[]), file, 'exec'), env)
load('settings_web/schema.py', {'_reviewer_bottom_bar_section', '_color_pair_field',
                              '_designer_preview_section', '_hidden_config_field'})
load('settings_web/render.py', {'_serialize_field', '_camel'})
section = env['_reviewer_bottom_bar_section']()
defaults = {field['id']: field.get('default') for field in section['fields']}
defaults['bbar_btn_border_size'] = 2
defaults['bbar_good_border_light'] = '#654321'
defaults['bbar_good_border_dark'] = '#fedcba'
store = types.SimpleNamespace(read=lambda id: defaults[id])
section['fields'] = [env['_serialize_field'](store, field) for field in section['fields']]
section['colorGroups'] = section.pop('color_groups')
section['colorMenuLabel'] = section.pop('color_menu_label')
print(json.dumps(section))
`], {cwd: root, encoding: 'utf8'}));

async function mount(page, dark, previewKind = 'reviewer_bottom_bar') {
  await page.goto('about:blank');
  const fixture = {...section, preview_kind: previewKind};
  const context = {dark, initialPage: 'reviewer', settingsComplexity: 'advanced',
    pages: [{id: 'reviewer', title: 'Reviewer', sections: [fixture]}], nav: [], strings: {}};
  let html = fs.readFileSync(path.join(root, 'web/settings.html'), 'utf8');
  html = html.replace('/*__ONIGIRI_BOOT_BACKGROUND__*/', dark ? '#202020' : '#ffffff')
    .replace('/*__ONIGIRI_SETTINGS_CSS__*/', fs.readFileSync(path.join(root, 'web/settings.css'), 'utf8'))
    .replace('/*__ONIGIRI_SETTINGS_CONTEXT__*/null', JSON.stringify(context));
  await page.setContent(html);
  await page.addScriptTag({content: `window.savedPatches=[];window.pycmd=(command,callback)=>{
    if(command.startsWith('osw:patch:')) savedPatches.push(JSON.parse(command.slice('osw:patch:'.length)));
    if(callback) callback({ok:true});
  };`});
  await page.addScriptTag({content: source});
}

(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1200, height: 900}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    for (const dark of [false, true]) {
      await mount(page, dark);
      const trigger = page.getByRole('button', {name: 'Reviewer Colors', exact: true});
      await trigger.click();
      assert.deepEqual(errors, [], 'Opening Reviewer Colors must not throw');
      const menu = page.locator('.osw-organize-menu.is-widget-colors');
      await menu.waitFor({state: 'visible', timeout: 3000});
      assert.equal(await trigger.getAttribute('aria-expanded'), 'true');
      assert.equal(await menu.getByRole('tab').count(), section.colorGroups.length);
      for (const group of section.colorGroups) {
        const tab = menu.getByRole('tab', {name: group.title, exact: true});
        await tab.click();
        assert.equal(await tab.getAttribute('aria-selected'), 'true');
        const ids = await menu.locator('.osw-organize-menu-field').evaluateAll(nodes =>
          nodes.map(node => node.getAttribute('data-field-host')));
        // The bar background follows another surface by default, and the
        // Show Answer stats background follows Stats Bar by default.
        const visibleIds = group.field_ids.filter(id =>
          !['bbar_bg_color', 'bbar_stats_bar_bg'].includes(id));
        assert.deepEqual(ids, visibleIds);
      }
      await menu.getByRole('tab', {name: 'Good', exact: true}).click();
      const sample = menu.getByRole('tab', {name: 'Good', exact: true}).locator('.osw-reviewer-color-sample');
      assert.equal(await sample.evaluate(node => getComputedStyle(node).borderWidth), '2px');
      assert.equal(await sample.evaluate(node => getComputedStyle(node).borderColor),
        dark ? 'rgb(254, 220, 186)' : 'rgb(101, 67, 33)');
      for (const [mode, color] of [['light', '#123456'], ['dark', '#abcdef']]) {
        await menu.locator('[data-field-host="bbar_good_bg"]').getByRole('button',
          {name: mode === 'light' ? 'Light color' : 'Dark color', exact: true}).click();
        const picker = page.locator('.osw-gal:not(.is-closing) .osw-colorpick-modal');
        await picker.getByRole('textbox', {name: 'Hex color'}).fill(color);
        await picker.getByRole('textbox', {name: 'Hex color'}).blur();
        await picker.getByRole('button', {name: 'Save', exact: true}).click();
        await page.waitForFunction(({id, color}) => savedPatches.some(patch => patch[id] === color),
          {id: 'bbar_good_bg_' + mode, color});
        // The picker closes the compact menu; reopen after each saved change.
        if (!(await menu.isVisible())) await trigger.click();
        await menu.getByRole('tab', {name: 'Good', exact: true}).click();
      }
      assert.equal(await sample.evaluate(node => getComputedStyle(node).backgroundColor),
        dark ? 'rgb(171, 205, 239)' : 'rgb(18, 52, 86)');
      await trigger.click();
      assert.equal(await menu.count(), 0);
      assert.equal(await trigger.getAttribute('aria-expanded'), 'false');
      await trigger.click();
      assert(await menu.isVisible());
      await page.locator('#oswPageTitle').click();
      assert.equal(await menu.count(), 0);
    }
    // Overview/Bubble colors use the same shared editor without Reviewer
    // border styling. Omitting its optional preview context must still work.
    await mount(page, false, '');
    await page.getByRole('button', {name: 'Reviewer Colors', exact: true}).click();
    assert(await page.locator('.osw-organize-menu.is-widget-colors').isVisible());
    assert.deepEqual(errors, []);
    console.log('PASS: production Reviewer Colors opens, all 8 groups mount, both theme colors save through the bridge, previews update, toggle/outside close and reopen work, and shared non-Reviewer menus open.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
