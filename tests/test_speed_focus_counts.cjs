// Speed Focus uses .stattxt for its own countdown. Include native positioning:
// display alone does not prove that the countdown survives the bar's clipping.
// Run with Playwright available; no Anki profile or visible window is opened.
const { chromium } = require('playwright');
const assert = require('assert/strict');
const { execFileSync } = require('child_process');
const root = require('path').resolve(__dirname, '..');
const configs = [];
for (const mode of ['fixed', 'hover', 'inverted', 'off']) {
  for (const timer of ['right', 'left', 'out', 'off']) configs.push({
    onigiri_reviewer_stattxt_mode: mode,
    onigiri_reviewer_timer_position: timer,
  });
}
const generated = JSON.parse(execFileSync('python3', ['-c',
  "import sys,json;sys.path.insert(0,'tests');from test_reviewer_bottom_bar import reviewer_env;print(json.dumps([reviewer_env()['generate_reviewer_buttons_css'](c) for c in json.loads(sys.argv[1])]))",
  JSON.stringify(configs)], { cwd: root, encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 }));

const question = counts => `<table><tr><td class="stat2"><button id="ansbut" data-cmd="ans">Show Answer${counts}</button></td></tr></table>`;
const layouts = [
  '<span class="stattxt"><span class="new-count">1201</span> + <span class="learn-count"><u>35</u></span> + <span class="review-count">44</span></span>',
  '<span class="stattxt">1201</span><span class="stattxt">+</span><span class="stattxt">35</span><span class="stattxt">+</span><span class="stattxt">44</span>',
  '<span class="stattxt">1201 + 35 + 44 0:07</span>',
];
const nativeRender = `function showAnswer(html){document.getElementById('middle').innerHTML=html}
function showQuestion(html){showAnswer(html);document.getElementById('time').textContent='0:00'}`;
const nativeCss = `body,button{font:14px Arial}button{min-width:60px;white-space:nowrap;margin:9px;position:relative}
#middle td[align=center]{padding-top:10px;position:relative}.stat,.stat2{padding-top:10px}
.stattxt,.nobold{position:absolute;white-space:nowrap;font-size:small;top:-3px;left:50%;transform:translate(-50%,-100%);font-weight:normal;display:inline-block}`;
// Same sibling cell and countdown IDs/classes used by Speed Focus's
// sfm-bottom-bar.js. Keep its timer and More time! action alive through ticks.
const speedFocus = `<td id="spdfControls" width="50" align="center" valign="top" class="stat"><button onclick="window.spdfStopped=true">More time!<span id="spdfTime" class="stattxt"></span><br></button></td>`;
const readCounts = page => page.locator('.onigiri-count-pill').allTextContents();
async function assertCountdownFits(page) {
  const geometry = await page.evaluate(() => {
    const timer = document.getElementById('spdfTime'), button = timer.closest('button');
    const box = node => { const r = node.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}; };
    const label = document.createRange(); label.selectNode(button.firstChild);
    const utilities = [...document.querySelectorAll('#outer > table > tbody > tr > td:not(#middle) button')].map(box);
    return {timer:box(timer),button:box(button),bar:box(document.getElementById('outer')),label:box(label),utilities};
  });
  for (const parent of [geometry.button, geometry.bar]) {
    assert(geometry.timer.top >= parent.top && geometry.timer.bottom <= parent.bottom,
      `Countdown must fit vertically: ${JSON.stringify(geometry)}`);
    assert(geometry.timer.left >= parent.left && geometry.timer.right <= parent.right,
      `Countdown must fit horizontally: ${JSON.stringify(geometry)}`);
  }
  assert(geometry.label.bottom <= geometry.timer.top, 'Countdown must not overlap More time!');
  for (const utility of geometry.utilities) {
    assert(utility.left >= geometry.bar.left && utility.right <= geometry.bar.right,
      `Other toolbar actions must remain inside the bar: ${JSON.stringify(geometry)}`);
  }
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({viewport:{width:640,height:160}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let cases = 0;
    for (const css of generated) for (const layout of layouts) for (const early of [true, false]) {
      await page.goto('about:blank');
      await page.setContent(`<html class="${early ? '' : 'nightMode'}"><head><style>${nativeCss}</style><script>${nativeRender}</script>${css}</head><body>
        <center id="outer"><table><tr><td><button data-cmd="edit">Edit</button></td>
        <td id="middle">${question(layout)}</td>${early ? speedFocus : ''}
        <td><button data-cmd="more">More<span id="time" class="stattxt">0:07</span></button></td></tr></table></center>
        </body></html>`);
      if (!early) await page.evaluate(html => document.getElementById('middle').insertAdjacentHTML('afterend', html), speedFocus);
      await page.evaluate(() => document.getElementById('spdfTime').textContent = 'Reveal 0:08');
      await page.waitForTimeout(150);
      assert.deepEqual(await readCounts(page), ['1201', '35', '44'], 'Speed Focus must not pollute real queue counts');
      await assertCountdownFits(page);
      const firstPill = await page.locator('.onigiri-count-pill').first().elementHandle();
      for (const text of ['Reveal 0:07', 'Again 0:01', 'Stopped.', '']) {
        await page.evaluate(text => document.getElementById('spdfTime').textContent = text, text);
        await page.waitForTimeout(110);
        await assertCountdownFits(page);
        assert.deepEqual(await readCounts(page), ['1201', '35', '44'], 'Countdown ticks must preserve the cached counts');
        assert.equal(await page.locator('#spdfControls button').getAttribute('data-onigiri-ease'), null, 'Again countdown must not turn More time! into an answer button');
        assert(await firstPill.evaluate(n => n.isConnected), 'Countdown ticks must not rebuild the Show Answer button');
      }
      await page.locator('#spdfControls button').click();
      assert.equal(await page.evaluate(() => window.spdfStopped), true, 'More time! must still work');
      await page.evaluate(() => showAnswer('<button data-cmd="ease1">Again<span class="nobold">&lt;1m</span></button><button data-cmd="ease3">Good<span class="nobold">2d</span></button>'));
      await page.evaluate(() => document.getElementById('spdfTime').textContent = 'Again 0:10');
      await assertCountdownFits(page);
      await page.evaluate(() => document.getElementById('spdfControls').style.display = 'none');
      assert.equal(await page.locator('#spdfControls').evaluate(n => getComputedStyle(n).display), 'none', 'Speed Focus must retain control of its visibility');
      await page.evaluate(() => document.getElementById('spdfControls').style.display = '');
      await page.evaluate(html => showQuestion(html), question('<span class="stattxt">1200 + 34 + 43</span>'));
      assert.deepEqual(await readCounts(page), ['1200', '34', '43'], 'Next card must replace cached counts');
      // Invalid/incomplete text must not replace a valid triplet with zeros.
      await page.evaluate(html => showQuestion(html), question('<span class="stattxt">Reveal 0:06</span>'));
      assert.deepEqual(await readCounts(page), ['1200', '34', '43']);
      await page.evaluate(html => showQuestion(html), question('<span class="stattxt">0 + 0 + 0</span>'));
      assert.deepEqual(await readCounts(page), ['0', '0', '0'], 'Real zero counts must update the cache');
      cases++;
    }
    // A fresh reviewer with native due counts disabled must not manufacture
    // queue pills from the Speed Focus timer or unrelated numeric stats.
    await page.goto('about:blank');
    await page.setContent(`<html><head><script>${nativeRender}</script>${generated[0]}</head><body>
      <center id="outer"><table><tr><td><span class="stattxt">9 + 8 + 7</span></td>
      <td id="middle">${question('')}</td>${speedFocus}
      <td><button data-cmd="more">More<span id="time" class="stattxt">0:07</span></button></td></tr></table></center></body></html>`);
    await page.evaluate(() => document.getElementById('spdfTime').textContent = 'Reveal 0:08');
    await page.waitForTimeout(150);
    assert.deepEqual(await readCounts(page), []);
    assert.deepEqual(errors, []);
    console.log(`PASS: ${cases} Speed Focus compatibility cases; real counts, cache, next-card updates, zero counts, countdown visibility, and More time! action.`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
