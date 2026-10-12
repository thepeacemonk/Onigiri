// Production Settings UI and isolated reviewer shadow header; Chromium stays hidden.
const fs = require('fs'), path = require('path'), assert = require('node:assert/strict');
const {execFileSync} = require('child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const section = JSON.parse(execFileSync('python3', ['tests/test_reviewer_header.py', '--fixture'], {cwd: root, encoding: 'utf8'}));
const visibility = JSON.parse(execFileSync('python3', ['tests/test_reviewer_header.py', '--visibility-fixture'], {cwd: root, encoding: 'utf8'}));
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const shared = read('web/reviewer_header_shared.css');
const config = {
  onigiri_reviewer_header_mode: 'custom', onigiri_reviewer_header_radius: 7,
  onigiri_reviewer_header_border_size: 2, onigiri_reviewer_header_padding: 9,
  onigiri_reviewer_header_height: 42, onigiri_reviewer_header_gap: 12,
  onigiri_reviewer_header_opacity: 45, onigiri_reviewer_header_blur: 35,
  onigiri_reviewer_header_bg_light: '#123456',
  onigiri_reviewer_header_hover_bg_light: '#654321',
  // Old individual overrides must be ignored by the preview and native CSS.
  onigiri_reviewer_header_decks_bg_light: '#abcdef', onigiri_reviewer_header_decks_bg_dark: '#fedcba',
  onigiri_reviewer_header_decks_hover_bg_light: '#abcdef',
};
const col = {onigiri_font_reviewer_header: 'mono', onigiri_font_size_reviewer_header: 23};
const liveCss = execFileSync('python3', ['-c', `import sys,json;sys.path.insert(0,'tests');from test_reviewer_header import runtime_css;print(runtime_css(json.loads(sys.argv[1]),json.loads(sys.argv[2])))`, JSON.stringify(config), JSON.stringify(col)], {cwd:root, encoding:'utf8'});
async function mount(page, dark) {
  await page.goto('about:blank');
  const context = {dark, initialPage:'reviewer', settingsComplexity:'advanced', pages:[{id:'reviewer', title:'Reviewer', sections:[section]},...visibility.pages], nav:[], strings:{}};
  let html = read('web/settings.html').replace('/*__ONIGIRI_BOOT_BACKGROUND__*/', dark?'#202020':'#ffffff')
    .replace('/*__ONIGIRI_SETTINGS_CSS__*/', read('web/settings.css')+'\n'+shared)
    .replace('/*__ONIGIRI_SETTINGS_CONTEXT__*/null', JSON.stringify(context));
  await page.setContent(html);
  await page.addScriptTag({content:`window.savedPatches=[];window.pycmd=(command,callback)=>{if(command.startsWith('osw:patch:'))savedPatches.push(JSON.parse(command.slice(10)));if(callback)callback({ok:true});};`});
  await page.addScriptTag({content:read('web/settings.js')});
}
async function set(page, values) {
  await page.evaluate(values => Object.entries(values).forEach(([id,value]) => onigiriSettings.setFieldValue(id,value)), values);
}
async function buttonStyle(page, selector) {
  return (typeof selector === 'string' ? page.locator(selector) : selector).evaluate(node => {const s=getComputedStyle(node);return Object.fromEntries(['backgroundColor','color','borderRadius','borderWidth','borderColor','paddingTop','paddingLeft','minHeight','fontFamily','fontSize','backdropFilter','opacity'].map(k=>[k,s[k]]));});
}
(async()=>{
  const browser = await chromium.launch({headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1300,height:1000}}), errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    for(const dark of [false,true]) {
      await mount(page,dark);
      assert((await page.getByText('Header Customization',{exact:true}).count()) >= 1);
      assert.equal(await page.locator('[data-field-host="rprog_style"]').count(),0);
      const styleRow=page.locator('.osw-designer-deck [data-field-host="rheader_mode"]');
      const headerControls=['rheader_radius','rheader_border_size','rheader_padding','rheader_height','rheader_gap','rheader_opacity','rheader_blur','hashi_show_header','pomodoro_show_header'];
      async function editorVisible(expected) {
        assert(await styleRow.isVisible(),'Button Style must stay visible');
        for(const id of headerControls) assert.equal(await page.locator('.osw-designer-deck [data-field-host="'+id+'"]').isVisible(),expected,id);
        for(const name of ['Header Fonts','Button Colors']) assert.equal(await page.getByRole('button',{name,exact:true}).isVisible(),expected,name);
      }
      await editorVisible(false);
      for(let i=0;i<3;i++) {
        await styleRow.locator('[data-value="custom"]').click();
        await editorVisible(true);
        await page.locator('[data-complexity="simple"]').click();
        await editorVisible(false);
        await page.locator('[data-complexity="advanced"]').click();
        await editorVisible(true);
        await styleRow.locator('[data-value="widgets"]').click();
        await editorVisible(false);
        await page.locator('[data-complexity="simple"]').click();
        await editorVisible(false);
        await page.locator('[data-complexity="advanced"]').click();
        await editorVisible(false);
      }
      await styleRow.locator('[data-value="custom"]').click();
      await editorVisible(true);

      for (const [id, button, label] of [['hashi_show_header','hashi','Show Hashi Notes button'],['pomodoro_show_header','pomodoro','Show Pomodoro button']]) {
        const row=page.locator('.osw-designer-deck [data-field-host="'+id+'"]');
        assert.equal(await row.locator('.osw-row-label').textContent(),label);
        assert.equal(await page.locator('.osw-preview-rprog-header [data-header-button="'+button+'"]').count(),1);
        await row.locator('.osw-switch-btn').click();
        assert.equal(await page.locator('.osw-preview-rprog-header [data-header-button="'+button+'"]').count(),0);
        await page.waitForFunction(id=>savedPatches.some(p=>p[id]===false),id);
        await row.locator('.osw-switch-btn').click();
        assert.equal(await page.locator('.osw-preview-rprog-header [data-header-button="'+button+'"]').count(),1);
      }
      await set(page,{hashi_notes_visible:false,pomodoro_visible:false});
      await editorVisible(true);
      assert.equal(await page.locator('.osw-preview-rprog-header [data-header-button="hashi"],.osw-preview-rprog-header [data-header-button="pomodoro"]').count(),0);
      await set(page,{hashi_notes_visible:true,pomodoro_visible:true});

      await page.getByRole('button',{name:'Button Colors',exact:true}).click();
      const menu=page.locator('.osw-organize-menu.is-widget-colors');
      await menu.waitFor({state:'visible'});
      assert.equal(await menu.getByRole('tab').count(),0);
      assert.equal(await menu.locator('.osw-reviewer-color-card:visible').count(),0);
      assert.deepEqual(await menu.locator('.osw-organize-menu-field').evaluateAll(ns=>ns.map(n=>n.getAttribute('data-field-host'))),section.colorGroups[0].field_ids);
      await menu.locator('.osw-organize-font-info').click();
      assert.equal(await menu.locator('.osw-organize-font-info-text').textContent(),section.colorGroups[0].description);
      if(!dark)await page.screenshot({path:'/tmp/onigiri-header-shared-colors.png',fullPage:true});
      await menu.locator('[data-field-host="rheader_bg"]').getByRole('button',{name:dark?'Dark color':'Light color',exact:true}).click();
      const picker=page.locator('.osw-gal:not(.is-closing) .osw-colorpick-modal');
      await picker.getByRole('textbox',{name:'Hex color'}).fill('#123456');
      await picker.getByRole('textbox',{name:'Hex color'}).blur();
      await picker.getByRole('button',{name:'Save',exact:true}).click();
      await page.waitForFunction(id=>savedPatches.some(p=>p[id]==='#123456'), 'rheader_bg_'+(dark?'dark':'light'));
      await page.keyboard.press('Escape');
      await set(page,Object.fromEntries(Object.entries(config).map(([key,value])=>[key.replace('onigiri_reviewer_header_','rheader_'),value])));
      await set(page,{rheader_bg_dark:'#3a3a3a'});
      await set(page,col);
      const radiusTrack=page.locator('[data-field-host="rheader_radius"] .osw-slider-track');
      await radiusTrack.evaluate(track=>{const rect=track.getBoundingClientRect();track.dispatchEvent(new PointerEvent('pointerdown',{clientX:rect.left+rect.width*.07,bubbles:true}));window.dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));});
      assert.equal(await page.locator('[data-field-host="rheader_radius"] .osw-slider-value').textContent(),'7px');
      await page.waitForTimeout(100);
      const selector='.osw-preview-rprog-header [data-header-button="decks"]';
      await page.mouse.move(0,0);
      const preview=await buttonStyle(page,selector);
      assert.equal(preview.borderRadius,'7px');assert.equal(preview.borderWidth,'2px');
      assert.equal(preview.paddingTop,'9px');assert.equal(preview.minHeight,'42px');
      assert.equal(preview.fontSize,'23px');assert.equal(preview.fontFamily,'monospace');
      assert.equal(preview.backdropFilter,'blur(7px)');assert.equal(preview.opacity,'1');
      assert.equal(preview.backgroundColor,dark?'rgba(58, 58, 58, 0.45)':'rgba(18, 52, 86, 0.45)');
      for (const button of await page.locator('.osw-preview-rprog-header [data-header-button]').all()) {
        assert.deepEqual(await buttonStyle(page,button),preview);
      }
      // The same stylesheet/variables must win inside the real isolated shadow header.
      await page.evaluate(({css,dark})=>{
        const host=document.createElement('div');host.id='runtime-header';if(dark)host.className='night-mode';
        document.body.appendChild(host);const shadow=host.attachShadow({mode:'open'});
        shadow.innerHTML=css.replaceAll('.night_mode #onigiri-reviewer-header',':host(.night-mode) #onigiri-reviewer-header')+
          '<div id="onigiri-reviewer-header" class="onigiri-header-customization"><a class="onigiri-reviewer-button" data-header-button="decks">Decks</a></div>';
      },{css:liveCss,dark});
      assert.deepEqual(await buttonStyle(page,'#runtime-header [data-header-button="decks"]'),preview);
      await page.locator('#runtime-header').evaluate(n=>n.remove());
      for (const button of await page.locator('.osw-preview-rprog-header [data-header-button]').all()) {
        await button.hover();
        assert.equal((await buttonStyle(page,button)).backgroundColor,dark?'rgba(224, 224, 224, 0.45)':'rgba(101, 67, 33, 0.45)');
      }
      await set(page,{rheader_opacity:0});await page.mouse.move(0,0);
      assert.equal((await buttonStyle(page,selector)).backgroundColor,dark?'rgba(58, 58, 58, 0)':'rgba(18, 52, 86, 0)');
      assert.equal((await buttonStyle(page,selector)).opacity,'1');
      await set(page,{rheader_opacity:45});
      await page.getByRole('button',{name:'Header Fonts',exact:true}).click();
      const fontMenu=page.locator('.osw-organize-menu:not(.is-widget-colors)');
      await fontMenu.waitFor({state:'visible'});assert.equal(await fontMenu.locator('[data-field-host="onigiri_font_reviewer_header"]').count(),1);
      await fontMenu.locator('.osw-organize-font-close').click();
      await page.mouse.move(0,0);
      // Returning from hidden editor states preserves the existing styling.
      await styleRow.locator('[data-value="widgets"]').click();
      await editorVisible(false);
      if(dark)await page.screenshot({path:'/tmp/onigiri-header-match-widgets.png',fullPage:true});
      await styleRow.locator('[data-value="custom"]').click();
      await editorVisible(true);
      assert.deepEqual(await buttonStyle(page,selector),preview);
      await page.locator('[data-complexity="simple"]').click();
      await editorVisible(false);
      if(dark)await page.screenshot({path:'/tmp/onigiri-header-simple.png',fullPage:true});
      await page.locator('[data-complexity="advanced"]').click();
      await editorVisible(true);
      assert.deepEqual(await buttonStyle(page,selector),preview);
      if(dark)await page.screenshot({path:'/tmp/onigiri-header-advanced-custom.png',fullPage:true});
      if(!dark)await page.screenshot({path:'/tmp/onigiri-header-buttons.png',fullPage:true});
      await page.getByRole('button',{name:'Header Progress Bar',exact:true}).click();
      assert.equal(await page.locator('[data-field-host="rheader_mode"]').count(),0);
      assert.equal(await page.locator('[data-field-host="rprog_style"]').count(),1);
      const progressToggle=page.locator('.osw-designer-deck [data-field-host="rprog_enabled"]');
      assert.equal(await progressToggle.locator('.osw-row-label').textContent(),'Show progress bar');
      assert.equal(await progressToggle.locator('.osw-row-desc').textContent(),'Show or hide the study progress indicator beside the header buttons.');
      assert.equal(await page.locator('.osw-designer-preview-head [data-field-host="rprog_enabled"]').count(),0);
      assert.equal(await page.getByRole('button',{name:'Button Colors',exact:true}).count(),0);
      for(const style of ['bar','segments','ring','text']) {
        await set(page,{rprog_style:style,rprog_position:'left'});
        assert.equal(await page.locator('.osw-preview-rprog-header > :first-child').getAttribute('class'),'osw-preview-rprog-chip onigiri-reviewer-progress is-'+style);
      }
      await set(page,{rprog_enabled:false});assert.equal(await page.locator('.osw-preview-rprog-chip').count(),0);
      await set(page,{rprog_enabled:true,rprog_style:'bar',rprog_position:'right'});
      if(!dark)await page.screenshot({path:'/tmp/onigiri-header-progress.png',fullPage:true});
      await page.setViewportSize({width:820,height:900});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'No horizontal overflow');
      await page.getByRole('button',{name:'Header Buttons',exact:true}).click();
      assert.equal((await buttonStyle(page,selector)).borderRadius,'7px');
      await page.setViewportSize({width:1300,height:1000});
      assert.deepEqual(errors,[]);
    }
    const scripts=JSON.parse(execFileSync('python3',['tests/test_reviewer_header.py','--refresh-fixture'],{cwd:root,encoding:'utf8'}));
    await page.goto('about:blank');
    await page.setContent('<div id="qa">Active card</div><div id="onigiri-reviewer-ui-host"></div>');
    await page.evaluate(()=>document.getElementById('onigiri-reviewer-ui-host').attachShadow({mode:'open'}).innerHTML=
      '<div id="onigiri-reviewer-header"><div class="onigiri-reviewer-header-buttons"><a data-header-button="decks" class="onigiri-reviewer-button">Decks</a></div></div>');
    for(let i=0;i<scripts.length;i++){
      await page.evaluate(script=>{eval(script)},scripts[i]);
      assert.equal(await page.locator('#qa').textContent(),'Active card');
      assert.equal(await page.locator('#onigiri-reviewer-ui-host #onigiri-reviewer-header-customization').count(),1);
      assert.equal(await page.locator('#onigiri-reviewer-ui-host #onigiri-scoped-reviewer_header-font').count(),1);
      assert.equal(await page.locator('#onigiri-reviewer-header-font-document').count(),1);
      const chip=page.locator('#onigiri-reviewer-ui-host #onigiri-reviewer-progress');
      if(i===2)assert.equal(await chip.count(),0);
      else {assert.equal(await chip.locator('.orp-text').textContent(),'12/40');}
      if(i===1)assert.equal(await page.locator('#onigiri-reviewer-ui-host .onigiri-reviewer-header-buttons > :first-child').getAttribute('id'),'onigiri-reviewer-progress');
      if(i===3)assert.equal(await page.locator('#onigiri-reviewer-ui-host #onigiri-reviewer-header').evaluate(n=>n.classList.contains('is-custom-header')),false);
    }

    for(let i=0;i<visibility.scripts.length;i++){
      await page.evaluate(script=>{eval(script)},visibility.scripts[i]);
      const header=page.locator('#onigiri-reviewer-ui-host .onigiri-reviewer-header-buttons');
      assert.equal(await header.locator('[data-header-button="hashi"]').count(),i===1||i===2?0:1);
      assert.equal(await header.locator('[data-header-button="pomodoro"]').count(),i===2?0:1);
      assert.equal(await page.locator('#qa').textContent(),'Active card');
      assert.equal(await header.locator('[data-header-button="decks"]').count(),1);
      assert.equal(await header.locator('#onigiri-reviewer-progress').count(),1);
    }
    console.log('Header customization: button/color/font editing, persistence, both themes, opacity, hover, progress modes, shadow CSS parity, and narrow layout passed.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
