// Real DOM, fonts and pointer hit-testing in headless Chromium. No Anki profile.
const fs=require('fs'), path=require('path'), assert=require('node:assert/strict');
const {execFileSync}=require('child_process'), {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const fixture=JSON.parse(execFileSync(process.env.PYTHON || 'python3',[path.join(__dirname,'bento_issue_fixtures.py')],{cwd:root,encoding:'utf8',maxBuffer:8*1024*1024}));
const src=fs.readFileSync(root+'/web/settings.js','utf8');
function fn(name){const start=src.indexOf('  function '+name+'(');assert(start>=0,name);return src.slice(start,src.indexOf('\n  }',start)+4);}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1280,height:800}});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.route('http://onigiri.test/**',route=>{
  const pathname=new URL(route.request().url()).pathname;
  const relative=pathname.replace('/_addons/1011095603/','');
  if(relative===pathname || !relative.startsWith('system_files/fonts/')) return route.fulfill({status:404,body:''});
  const target=path.join(root,relative);
  return route.fulfill({status:200,body:fs.readFileSync(target),contentType:'font/ttf',headers:{'access-control-allow-origin':'*'}});
 });
 // Real language dictionaries, full sidebar script and stable data identifiers.
 let locales=0;
 for(const [code,locale] of Object.entries(fixture.locales)){
  for(const selection of ['due','new','learn',null,'invalid']){
   await page.goto('about:blank');
   await page.setContent('<html><body><div class="ba-dashboard"></div></body></html>');
   await page.evaluate(({locale,selection})=>{
    window.ONIGIRI_LOCALIZATION={literals:locale.literals};
    window.__baOpts={sidebar:{heroStat:selection}};
    window.__baStandingData={due:37,new:12,learn:8,streak:4,today:23,todayMin:5,total:69,dueTotal:50};
    window.pycmd=()=>{};
   },{locale,selection});
   await page.addScriptTag({path:root+'/web/localization.js'});
   await page.addScriptTag({path:root+'/things_theme/web/sidebar.js'});
   if(!await page.locator('.ba-side-hero-n').count()) throw new Error(code+' '+selection+' '+JSON.stringify(errors));
   const result=await page.evaluate(()=>({key:document.querySelector('.ba-side-hero-n').dataset.x,label:document.querySelector('.ba-side-hero-label').textContent,value:document.querySelector('.ba-side-hero-n').textContent}));
   const key=['new','learn'].includes(selection)?selection:'due';
   assert.equal(result.key,key,code);assert.equal(result.label,locale.labels[key],code);
   assert.equal(result.value,String({due:37,new:12,learn:8}[key]),code);
   await page.evaluate(()=>window.__baSetStanding({due:0,new:0,learn:0}));
   assert.equal(await page.locator('.ba-side-hero-n').textContent(),'0',code);
   locales++;
  }
 }
 // Full stylesheet hit test catches pointer blocking from stale editor state.
 await page.setContent('<div class="container modern-main-menu is-card-editing"><main class="main-content"><button id="clickme">Open dashboard tool</button></main></div>');
 await page.addStyleTag({path:root+'/web/menu.css'});
 await page.evaluate(()=>{document.body.classList.add('is-card-editing');window.clicks=0;document.getElementById('clickme').onclick=()=>window.clicks++;});
 await page.locator('#clickme').click();
 assert.equal(await page.evaluate(()=>window.clicks),1);
 // Match Widgets retains its old appearance; independent images resolve in
 // both theme modes and remain visible even while effects match widgets.
 await page.setContent('<html><body></body></html>');
 const api=['designerSidebarSpec','designerPairValue','designerNum','showWhenMatches','isSyncHidden'].map(fn).join('\n');
 await page.addScriptTag({content:'const CTX={};const values={};function designerFontRole(){return {color:"#333"};}\n'+api+'\nwindow.sidebarApi={designerSidebarSpec,showWhenMatches,isSyncHidden};'});
 const sidebarCases=await page.evaluate(()=>{
  const results=[];
  for(const type of ['image','image_color']) for(const dark of [false,true]) for(const sync of [false,true]){
   const vals={modern_menu_sidebar_bg_mode:'independent',modern_menu_sidebar_bg_type:type,
    modern_menu_sidebar_sync_box_effect:sync,modern_menu_sidebar_bg_image_theme_mode:'separate',
    modern_menu_sidebar_bg_image_light:'day.png',modern_menu_sidebar_bg_image_dark:'night.png'};
   const spec=sidebarApi.designerSidebarSpec(vals,dark);
   results.push({type,dark,sync,image:spec.image,color:spec.color});
  }
  return results;
 });
 for(const c of sidebarCases){assert.equal(c.image,c.dark?'night.png':'day.png');if(c.type==='image')assert.equal(c.color,'transparent');}
 // Use the shipped header/gauge generators and a shipped selected font, with
 // faces in the document and typography isolated inside the shadow root.
 for(const width of [360,1440]) for(const dark of [false,true]){
  await page.setViewportSize({width,height:800});
  await page.setContent('<html><head><base href="http://onigiri.test"></head><body style="font-family:serif"><div id="qa">Card template stays in its own font</div><div id="onigiri-reviewer-ui-host"></div></body></html>');
  await page.addStyleTag({content:fixture.fontFaces});
  await page.evaluate(({fixture,dark})=>{
   window.commands=[];window.pycmd=c=>window.commands.push(c);
   const host=document.getElementById('onigiri-reviewer-ui-host');host.classList.toggle('night-mode',dark);
   host.attachShadow({mode:'open'}).innerHTML=fixture.shadowCss+fixture.header;
   document.body.style.background=dark?'#202020':'white';document.body.style.color=dark?'white':'black';
   document.getElementById('qa').style.marginTop=(host.shadowRoot.getElementById('onigiri-reviewer-header').offsetHeight+15)+'px';
  },{fixture,dark});
  await page.evaluate(async family=>{await document.fonts.load('18px "'+family+'"');await document.fonts.ready;},fixture.fontFamily);
  const state=await page.evaluate(family=>{
   const header=document.getElementById('onigiri-reviewer-ui-host').shadowRoot.getElementById('onigiri-reviewer-header');
   return {family:getComputedStyle(header).fontFamily,gauge:getComputedStyle(header.querySelector('.orp-text')).fontFamily,
    loaded:[...document.fonts].some(f=>f.family.replace(/['"]/g,'')===family && f.status==='loaded'),
    qa:getComputedStyle(document.getElementById('qa')).fontFamily,
    right:header.getBoundingClientRect().right,left:header.getBoundingClientRect().left};
  },fixture.fontFamily);
  assert(state.loaded,'selected font actually loaded');
  assert(state.family.includes(fixture.fontFamily));assert(state.gauge.includes(fixture.fontFamily));assert.equal(state.qa,'serif');
  assert(state.left>=0 && state.right<=width,'header fits viewport');
  const iconLoaded=await page.evaluate(async()=>{
   const root=document.getElementById('onigiri-reviewer-ui-host').shadowRoot;
   const mask=getComputedStyle(root.querySelector('.onigiri-external-toolbar-button span')).maskImage;
   const url=mask.slice(5,-2);
   return new Promise(resolve=>{const image=new Image();image.onload=()=>resolve(true);image.onerror=()=>resolve(false);image.src=url;});
  });
  assert(iconLoaded,'captured add-on icon decodes as a standalone SVG mask');
  await page.locator('.onigiri-external-toolbar-button').click();
  assert.deepEqual(await page.evaluate(()=>window.commands),['ankiterminator']);
  if(process.env.ONIGIRI_SCREENSHOT_DIR){fs.mkdirSync(process.env.ONIGIRI_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.ONIGIRI_SCREENSHOT_DIR,'reviewer-'+width+'-'+(dark?'dark':'light')+'.png')});}
 }
 assert.deepEqual(errors,[]);
 console.log(`Passed ${locales} locale/selection cases, 8 sidebar image cases, dashboard click and 4 reviewer font/button layouts.`);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
