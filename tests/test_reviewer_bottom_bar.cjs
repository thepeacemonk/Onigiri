// Run with Node and Playwright available; Chromium stays headless.
const {chromium}=require('playwright');const fs=require('fs'),assert=require('assert/strict');
const root=require('path').resolve(__dirname,'..'),src=fs.readFileSync(root+'/web/settings.js','utf8');
function fn(name){const a=src.indexOf('  function '+name+'(');assert(a>=0,name);return src.slice(a,src.indexOf('\n  }',a)+4)}
// Native reviewer-bottom.css and the nested question table from Anki 25.x.
// Keep the wrapper: a flat mock misses the native 10px top padding.
const nativeLayoutCss='#middle td[align=center]{padding-top:10px;position:relative}.stat{padding-top:10px}.stat2{padding-top:10px;font-weight:normal}button{min-width:60px;white-space:nowrap;margin:9px;position:relative}';
const nativeRenderScript=`let timerStopped=false;function showAnswer(html,stop=false){document.getElementById('middle').innerHTML=html;timerStopped=stop}function showQuestion(html,maxTime){showAnswer(html);document.getElementById('time').textContent=maxTime?'0:00':''}`;
const helpers=['el','str','bbarStatsBarBg','bbarStatTextMode','bbarUtilityButton','bbarFixedMetrics','bbarFitFixedAnswerLabel','bbarButtonBorder','bbarSideColumns'].map(fn).join('\n');
const a=src.indexOf('  PREVIEW_PAINTERS.reviewer_bottom_bar ='), z=src.indexOf('\n  // ── Reviewer Header',a);const painter=src.slice(a,z);
const fixtures=JSON.parse(require('child_process').execFileSync('python3',['-c',"import sys,json;sys.path.insert(0,'tests');from test_reviewer_bottom_bar import browser_fixtures;print(json.dumps(browser_fixtures()))"],{cwd:root,encoding:'utf8',maxBuffer:8*1024*1024}));
fixtures.push({...fixtures[0],timer:'out',css:fixtures[0].css.replace('const ONIGIRI_TIMER_POSITION = "right";', 'const ONIGIRI_TIMER_POSITION = "out";')});
fixtures.push({...fixtures[0],timer:'off',css:fixtures[0].css.replace('const ONIGIRI_TIMER_POSITION = "right";', 'const ONIGIRI_TIMER_POSITION = "off";')});
fixtures.push(...fixtures.map(f=>({...f,width:640})));
(async()=>{const browser=await chromium.launch({headless:true});const live=await browser.newPage({viewport:{width:1000,height:300}}),preview=await browser.newPage({viewport:{width:1000,height:300}});const errors=[];for(const p of [live,preview])p.on('pageerror',e=>errors.push(e.message));
for(const f of fixtures){ const width=f.width||1000;await Promise.all([live.setViewportSize({width,height:300}),preview.setViewportSize({width,height:300})]); await Promise.all([live.goto("about:blank"),preview.goto("about:blank")]);
 await live.setContent(`<html class="${f.dark?'nightMode':''}"><head>${f.size===28?'':`<script>${nativeRenderScript}</script>`}<style>${nativeLayoutCss}</style>${f.css.slice(0,f.css.indexOf("</style>")+8)}<style>#outer,#outer button{font: ${f.size}px Arial !important}#outer button .onigiri-show-answer-label{font-size:${f.size}px !important}</style>${f.css.slice(f.css.indexOf("</style>")+8)}${f.size===28?`<script>${nativeRenderScript}</script>`:''}</head><body><center id="outer"><table id="innertable" width="100%" cellspacing="0" cellpadding="0"><tbody><tr><td align="start" valign="top" class="stat"><button data-cmd="edit">${f.strings.bbar_edit}</button></td><td align="center" valign="top" id="middle"><table cellpadding="0"><tbody><tr><td class="stat2" align="center"><button id="ansbut" data-cmd="ans">${f.strings.show_answer}<span class="stattxt">1201 + 35 + 44</span></button></td></tr></tbody></table></td><td align="end" valign="top" class="stat"><button data-cmd="more">${f.strings.more}<span id="time" class="stattxt">0:07</span></button></td></tr></tbody></table></center><script>window.onigiriSetReviewerCardType({key:'learn',label:'Learning'});</script></body></html>`);
 await live.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>resolve())));
 assert.equal(await live.locator('.onigiri-count-pill').count(),3,'First paint must already contain the custom counts');
 await live.locator('.onigiri-count-pill').last().waitFor();
 const vals={bbar_stattxt_mode:'fixed',bbar_btn_radius:12,bbar_btn_padding:5,bbar_btn_height:40,bbar_bar_height:60,bbar_timer_position:f.timer||'right',bbar_custom_enabled:true,bbar_btn_border_size:2,bbar_good_border_light:'#123456',ovstyle_color_new_bubble_light:'#1e8cff',ovstyle_color_new_text_light:'#ffffff',ovstyle_color_learn_bubble_light:'#ff5757',ovstyle_color_learn_text_light:'#ffffff',ovstyle_color_review_bubble_light:'#19c96b',ovstyle_color_review_text_light:'#ffffff',ovstyle_color_new_bubble_dark:'#0a84ff',ovstyle_color_new_text_dark:'#f7fbff',ovstyle_color_learn_bubble_dark:'#ff453a',ovstyle_color_learn_text_dark:'#fff5f5',ovstyle_color_review_bubble_dark:'#12b765',ovstyle_color_review_text_dark:'#f4fff8'};
 await preview.setContent(`<html><head><style>${fs.readFileSync(root+'/web/settings.css','utf8')}\n${fs.readFileSync(root+'/web/reviewer_buttons_shared.css','utf8')}</style></head><body><div id="stage" style="position:relative;width:${width}px;height:${f.height}px"></div></body></html>`);
 await preview.addScriptTag({content:`const STRINGS=${JSON.stringify(f.strings)},PREVIEW_PAINTERS={};let bbarActiveMode='pre_answer';const bbarBackgroundState=()=>({}),paintResolvedBackdropState=()=>{},designerFontRole=()=>({family:'Arial',size:${f.size}});${helpers}\n${painter}\nPREVIEW_PAINTERS.reviewer_bottom_bar(document.getElementById('stage'),${JSON.stringify(vals)},${f.dark});`});
 await preview.evaluate(()=>{[...document.querySelectorAll('.onigiri-count-pill')].forEach((p,i)=>p.textContent=['1201','35','44'][i])});
 const metric=()=>{const b=document.querySelector('button.onigiri-show-answer-btn'),label=b.querySelector('.onigiri-show-answer-label'),counts=b.querySelector('.onigiri-pre-answer-counts'),pill=b.querySelector('.onigiri-count-pill'),base=b.getBoundingClientRect();const box=n=>{const r=n.getBoundingClientRect();return{width:r.width,height:r.height,x:r.x-base.x,y:r.y-base.y}};return{centerX:base.x+base.width/2,button:box(b),label:box(label),counts:box(counts),pill:box(pill),font:getComputedStyle(pill).fontSize,border:getComputedStyle(b).borderWidth,before:getComputedStyle(b.querySelector('.is-current-card'),'::before').content,after:getComputedStyle(b.querySelector('.is-current-card'),'::after').content,lower:document.querySelector('#outer')?document.querySelector('#outer').getBoundingClientRect().bottom-base.bottom:document.querySelector('.osw-preview-bbar-bar').getBoundingClientRect().bottom-base.bottom}};
 const lm=await live.evaluate(metric),pm=await preview.evaluate(metric);
 for (const p of [live,preview]) {
   const sides=await p.evaluate(()=>{const main=document.querySelector('button.onigiri-show-answer-btn').getBoundingClientRect();return [...document.querySelectorAll('#outer button.onigiri-other-btn:not(.onigiri-show-answer-btn),.osw-preview-bbar-utility,.osw-preview-bbar-timer.is-out')].map(n=>{const r=n.getBoundingClientRect();return{height:r.height,offset:r.y-main.y,expected:main.height}})});
   assert.equal(sides.length,f.timer==='out'?3:2);
   sides.forEach(r=>{assert(Math.abs(r.height-r.expected)<.1,JSON.stringify(r));assert(Math.abs(r.offset)<.1,JSON.stringify(r))});
 }
 await live.locator('[data-cmd="edit"]').hover();
 const hoverOffset=await live.evaluate(()=>document.querySelector('[data-cmd="edit"]').getBoundingClientRect().top-document.querySelector('#ansbut').getBoundingClientRect().top);
 assert(Math.abs(hoverOffset)<.1,'Edit must keep its vertical alignment on hover');
 await live.mouse.move(0,0);
 for(const key of ['button','label','counts','pill'])for(const prop of ['width','height','x','y'])assert(Math.abs(lm[key][prop]-pm[key][prop])<1.1,`${f.lang} dark${f.dark} font${f.size} ${key}.${prop} live=${lm[key][prop]} preview=${pm[key][prop]}`);
 for(const p of [live,preview]) {
   const inline=await p.evaluate(()=>{const b=document.querySelector('button.onigiri-show-answer-btn'),l=b.querySelector('.onigiri-show-answer-label').getBoundingClientRect(),c=b.querySelector('.onigiri-pre-answer-counts').getBoundingClientRect(),r=b.getBoundingClientRect();return{gap:c.left-l.right,labelHeight:l.height,lineHeight:parseFloat(getComputedStyle(b.querySelector('.onigiri-show-answer-label')).lineHeight),right:c.right-r.right}});
   assert(inline.gap>=15,JSON.stringify(inline));
   assert(inline.labelHeight<inline.lineHeight+1,JSON.stringify(inline));
   assert(inline.right<0,JSON.stringify(inline));
 }
 assert.equal(lm.font,pm.font);assert.equal(lm.border,'2px');assert.equal(lm.before,'none');assert.equal(pm.before,'none');assert(lm.lower>=17.5,JSON.stringify(lm));assert(pm.lower>=17.5);assert.equal(await live.locator('.is-current-card').count(),1);
 await live.evaluate(()=>document.getElementById('time').textContent='0:08');if(f.timer!=='off')await live.waitForFunction(()=>document.querySelector('.onigiri-timer-pill,.onigiri-timer-out-btn').textContent==='0:08');assert.equal(await live.locator('.onigiri-count-pill').first().innerText(),'1201');
 if(f.lang==='pt-BR'&&!f.dark&&f.size===14&&!f.width){await live.locator('#outer').screenshot({path:'/tmp/onigiri-bbar-live.png'});await preview.locator('.osw-preview-bbar-bar').screenshot({path:'/tmp/onigiri-bbar-preview.png'});}
 const intervals=['<1m','<10m','2d','3d'];
 const answers=['again','hard','good','easy'].map((key,i)=>`<td align="center"><button data-cmd="ease${i+1}" data-ease="${i+1}"><span class="nobold">${intervals[i].replace('<','&lt;')}</span>${f.strings[key]}</button></td>`).join('');
 const answerHtml=`<center><table cellpadding="0" cellspacing="0"><tbody><tr>${answers}</tr></tbody></table></center>`;
 const atomicAnswer=await live.evaluate(html=>{showAnswer(html,true);return{labels:document.querySelectorAll('.onigiri-fixed-answer-row .onigiri-answer-label').length,stopped:timerStopped}},answerHtml);
 assert.deepEqual(atomicAnswer,{labels:4,stopped:true},'Native showAnswer must prepare all buttons in the same call');
 await live.locator('.onigiri-fixed-answer-row .onigiri-answer-label').last().waitFor();
 await preview.evaluate(({vals,dark})=>{bbarActiveMode='answer';PREVIEW_PAINTERS.reviewer_bottom_bar(document.getElementById('stage'),vals,dark)},{vals,dark:f.dark});
 const answersMetric=()=>{const buttons=[...document.querySelectorAll('button[data-onigiri-ease]')],rects=buttons.map(b=>b.getBoundingClientRect());return{overflow:buttons.map(b=>{const l=b.querySelector('.onigiri-answer-label,.osw-preview-bbar-label'),r=document.createRange();r.selectNodeContents(l);const c=getComputedStyle(b);return r.getBoundingClientRect().width-(b.clientWidth-parseFloat(c.paddingLeft)-parseFloat(c.paddingRight))}),width:rects.at(-1).right-rects[0].left,centerX:(rects.at(-1).right+rects[0].left)/2,widths:rects.map(r=>r.width),gaps:rects.slice(1).map((r,i)=>r.left-rects[i].right)}};
 const la=await live.evaluate(answersMetric),pa=await preview.evaluate(answersMetric);
 for(const [before,after] of [[lm,la],[pm,pa]]) {
   assert(Math.abs(before.button.width-after.width)<.1,`${f.lang} ${f.size}/${width} question=${before.button.width}, choices=${after.width}`);
   assert(Math.abs(before.centerX-after.centerX)<.1,`${f.lang} ${f.size}/${width} center ${before.centerX} -> ${after.centerX}`);
   after.widths.forEach(w=>assert(Math.abs(w-after.widths[0])<.1,JSON.stringify(after)));
   after.gaps.forEach(g=>assert(Math.abs(g-10)<.1,JSON.stringify(after)));
   after.overflow.forEach(n=>assert(n<.5,`${f.lang} ${f.size}/${width} clipped answer label: ${JSON.stringify(after)}`));
 }
 assert(Math.abs(la.width-pa.width)<.1,'Answer preview must share runtime width');
 if(f.lang==='pt-BR'&&!f.dark&&f.size===14&&!f.width){await live.locator('#outer').screenshot({path:'/tmp/onigiri-bbar-answers-live.png'});await preview.locator('.osw-preview-bbar-bar').screenshot({path:'/tmp/onigiri-bbar-answers-preview.png'});}
 const questionHtml=`<table cellpadding="0"><tr><td class="stat2" align="center"><button id="ansbut" data-cmd="ans">${f.strings.show_answer}<span class="stattxt">1201 + 34 + 44</span></button></td></tr></table>`;
 const flips=await live.evaluate(({question,answer})=>{const samples=[];for(let i=0;i<6;i++){showAnswer(answer,true);const row=document.querySelector('.onigiri-fixed-answer-row');samples.push({kind:'answer',ready:!!row&&row.querySelectorAll('.onigiri-answer-label').length===4,width:row?.getBoundingClientRect().width});showQuestion(question,60);const b=document.getElementById('ansbut'),c=getComputedStyle(b);samples.push({kind:'question',ready:b.querySelectorAll('.onigiri-count-pill').length===3,width:b.getBoundingClientRect().width,bg:c.backgroundColor,transition:c.transitionProperty,opacity:c.opacity,timer:b.querySelector('.onigiri-timer-pill')?.textContent||document.querySelector('.onigiri-timer-out-btn')?.textContent});}return samples},{question:questionHtml,answer:answerHtml});
 flips.forEach(s=>{assert(s.ready,JSON.stringify(s));assert(Math.abs(s.width-lm.button.width)<.1,JSON.stringify(s));if(s.kind==='question'){assert.equal(s.transition,'filter');assert.equal(s.opacity,'1');assert.equal(s.bg,flips[1].bg);if(f.timer!=='off')assert.equal(s.timer,'0:00');}});
 const tickMotion=await live.evaluate(async()=>{const label=document.querySelector('.onigiri-show-answer-label'),before=label.getAnimations();document.getElementById('time').textContent='0:01';await Promise.resolve();const after=label.getAnimations();return{same:before.length===after.length&&before.every((a,i)=>a===after[i]),duration:after[0]?.effect.getTiming().duration}});
 assert(tickMotion.same,'Timer tick must not restart front/back motion');
 if(tickMotion.duration!==undefined)assert.equal(tickMotion.duration,120);
}
await Promise.all([live.emulateMedia({reducedMotion:'reduce'}),preview.emulateMedia({reducedMotion:'reduce'})]);
await live.evaluate(()=>showQuestion(document.getElementById('middle').innerHTML,60));
await preview.evaluate(()=>{bbarActiveMode='pre_answer';PREVIEW_PAINTERS.reviewer_bottom_bar(document.getElementById('stage'),{bbar_stattxt_mode:'fixed',bbar_custom_enabled:true},false)});
for(const p of [live,preview])assert.equal(await p.locator('.onigiri-show-answer-label').evaluate(n=>getComputedStyle(n).animationName),'none','Reduced motion must suppress the entrance');
assert.deepEqual(errors,[]);console.log(`PASS: ${fixtures.length} first-paint and live/preview comparisons at 1000px and 640px including external and disabled timers; 8 languages, 2 themes, 2 font sizes; equal question/answer widths and centers, four equal choices with 10px gaps; equal side-button heights and hover alignment; single indicator; bottom spacing; borders; ticking timer preserves counts; 816 synchronous front/back renders without native flashes; 120ms copy feedback and reduced motion.`);await browser.close()})().catch(e=>{console.error(e);process.exit(1)});
