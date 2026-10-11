// Run with Node and Playwright available; launches Chromium headlessly.
const fs = require('fs'), assert = require('assert/strict');
const {chromium} = require('playwright');
const path = require('path');
const root = path.join(__dirname, '..');
const src=fs.readFileSync(path.join(root, 'web/settings.js'),'utf8');
function fn(name){const a=src.indexOf('  function '+name+'(');assert(a>=0,name); return src.slice(a,src.indexOf('\n  }',a)+4);}
const helpers=['el','str','hexToRgb','rgbToHex','rgbToHsv','hsvToHex','cssColorToHex','qtColorRgb','preserveColorAlpha','closeSettingsPicker','openPickerShell','mountColorEditor','openColorPicker','fontFieldColor','openFontPicker','designerFieldFontFamily'].map(fn).join('\n');
const boot=`const CTX={dark:false}, STRINGS={}; let settingsPicker=null, activeTileMenuClose=null, iconPicker=null, gallery=null, deferringPreviewRefresh=false; const closeCompactFontMenu=()=>{}; const ICON_CLOSE='<svg></svg>', ICON_CHECK='<svg></svg>', OSW_SUN_ICON='<svg></svg>', OSW_MOON_ICON='<svg></svg>'; const values={title_font:'system',title_light:'',title_dark:'',theme_fg_light:'#202124',theme_fg_dark:'#f1f2f4'};const field={id:'title_font',label:'Font',default:'sync', options:[{value:'sync',label:'Sync with theme'},{value:'system',label:'Poppins',family:'Arial'},{value:'serif',label:'Serif',family:'Georgia'}],colorFields:[{id:'title_light',label:'Light'},{id:'title_dark',label:'Dark'}]};const fieldById={title_font:field,title_light:{default:''},title_dark:{default:''}};const pending={};function setValue(id,value){values[id]=value;pending[id]=value}function refreshSettingsPreviews(){} function installResetHold(button,handler){button.addEventListener('click',handler)};${helpers};window.qa={open:()=>openFontPicker(field),color:()=>openColorPicker({id:'title_light',label:'Color',default:''},values.title_light),values,pending};`;
(async()=>{
 const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1000,height:800}}); const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setContent('<html><head><style>'+fs.readFileSync(path.join(root, 'web/settings.css'),'utf8')+'</style></head><body></body></html>');await page.addScriptTag({content:boot});
 async function open(){await page.evaluate(()=>qa.open());}
 const modal=()=>page.locator('.osw-fontpick-modal').last();
 async function colorSlots(){assert.equal(await modal().getByRole('tab').count(),0);await modal().getByRole('button',{name:'Light Color',exact:true}).click();}
 async function hex(value){const input=modal().getByRole('textbox',{name:'Hex color'});await input.fill(value);await input.blur();}
 await open();if(process.env.ONIGIRI_FONT_SCREENSHOTS) await page.screenshot({path:'/tmp/onigiri-font-inline-desktop.png'});await modal().getByRole('button',{name:'Serif Onigiri'}).click();await colorSlots();await hex('#cc3300');await modal().getByRole('button',{name:'Dark Color',exact:true}).click();await hex('#44aaff');await modal().getByRole('button',{name:'Cancel',exact:true}).last().click();assert.deepEqual(await page.evaluate(()=>({...qa.pending})),{});
 await open();await modal().getByRole('button',{name:'Serif Onigiri'}).click();await colorSlots();await hex('#cc3300');await modal().getByRole('button',{name:'Dark Color',exact:true}).click();await hex('#44aaff');await modal().getByRole('button',{name:'Save',exact:true}).click();assert.deepEqual(await page.evaluate(()=>({...qa.pending})),{title_font:'serif',title_light:'#cc3300',title_dark:'#44aaff'});
 await open();await colorSlots();await modal().getByRole('button',{name:'Restore default',exact:true}).click();await modal().getByRole('button',{name:'Save',exact:true}).click();assert.equal(await page.evaluate(()=>qa.values.title_light),'');assert.equal(await page.evaluate(()=>qa.values.title_dark),'#44aaff');
 await open();await colorSlots();await hex('broken');assert.equal(await modal().getByRole('textbox',{name:'Hex color'}).inputValue(),'#202124');await page.keyboard.press('Escape');assert.equal(await modal().locator('.osw-fontpick-color-popover').count(),0);assert(await modal().isVisible());await page.keyboard.press('Escape');
 await page.setViewportSize({width:390,height:620});await open();if(process.env.ONIGIRI_FONT_SCREENSHOTS) await page.screenshot({path:'/tmp/onigiri-font-inline-small.png'});await colorSlots();await modal().getByRole('button',{name:'Dark Color',exact:true}).click();if(process.env.ONIGIRI_FONT_SCREENSHOTS) await page.screenshot({path:'/tmp/onigiri-font-inline-editor-small.png'}); const editorBounds=await modal().locator('.osw-fontpick-color-popover').boundingBox();assert(editorBounds.y>=0&&editorBounds.x>=0&&editorBounds.x+editorBounds.width<=390);const bounds=await modal().boundingBox(); assert(bounds.x>=0&&bounds.x+bounds.width<=390&&bounds.y>=0&&bounds.y+bounds.height<=620);await modal().getByRole('button',{name:'Use Default',exact:true}).click();assert.equal(await page.evaluate(()=>qa.values.title_font),'sync');assert.equal(await page.evaluate(()=>qa.values.title_dark),'');
 // Refactored standalone color picker keeps alpha and cancellation semantics.
 await page.evaluate(()=>{qa.values.title_light='rgba(10, 20, 30, 0.4)';qa.color()});const cp=page.locator('.osw-colorpick-modal').last();await cp.getByRole('textbox',{name:'Hex color'}).fill('#abcdef');await cp.getByRole('textbox',{name:'Hex color'}).blur();await cp.getByRole('button',{name:'Save',exact:true}).click();assert.equal(await page.evaluate(()=>qa.values.title_light),'rgba(171, 205, 239, 0.4)');
 // Verify actual generated runtime CSS with light/dark roots and independent number/unit ink.
 const {execFileSync} = require('child_process');
 const css = execFileSync('python3', ['-c', "import sys;sys.path.insert(0,'tests');from test_font_colors import FontColorTests;print(FontColorTests().font_css({'onigiri_font_dashboard_title_color_light':'#cc3300','onigiri_font_dashboard_title_color_dark':'#44aaff','swidget_number_font_color_light':'#123456','swidget_value_font_color_light':'#654321'}))"], {cwd:root,encoding:'utf8'});
 await page.setContent('<html><head><style>:root{--fg:#202124;--fg-subtle:#757575;--swidget-value-color:#123123}</style>'+css+'</head><body><div class="onigiri-widget-title">Title</div><div class="stat-card onigiri-stat-card"><p class="stat-value">42<span class="stat-unit">cards</span></p></div></body></html>');
 assert.equal(await page.locator('.onigiri-widget-title').evaluate(n=>getComputedStyle(n).color),'rgb(204, 51, 0)');
 assert.equal(await page.locator('.stat-value').evaluate(n=>getComputedStyle(n).color),'rgb(18, 52, 86)');
 assert.equal(await page.locator('.stat-unit').evaluate(n=>getComputedStyle(n).color),'rgb(101, 67, 33)');
 for(const root of ['html','body']){
  for(const mode of ['night-mode','nightMode']){
   await page.evaluate(({root,mode})=>{document.documentElement.className='';document.body.className='';document.querySelector(root).className=mode},{root,mode});
   assert.equal(await page.locator('.onigiri-widget-title').evaluate(n=>getComputedStyle(n).color),'rgb(68, 170, 255)');
  }
 }
 assert.deepEqual(errors,[]);console.log('PASS: swatches on the font page without tabs, cancel, save both modes, restore one mode, invalid hex, Escape, font default, alpha preservation, desktop and small layout, runtime CSS in both themes');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
