(() => {
  let data = window.ONIGIRI_ONIGIMON_DATA || {}, selected = null, busy = false, toastTimer = 0;
  let speechTimer = 0, lastSpeech = -1, spriteTimer = 0;
  let careTransition;
  const $ = s => document.querySelector(s), esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const text = (s, v) => { const n = $(s); if (n) n.textContent = v ?? ''; };
  const image = (s, url) => { const n = $(s); if (n) n.src = url || ''; };
  const status = id => (data.needs || []).find(item => item.id === id) || (data.needs || [])[0];
  const effectFor = id => ({health:'heal', happiness:'play', hygiene:'clean', training:'train', hunger:'feed'})[id] || 'sparkle';
  function itemStatus(key) {
    if (['medicine','petal_red','mints'].includes(key)) return 'health';
    if (['play_fluffy_tail','battle_x_attack','ball_great','pokeballs','poke_candies'].includes(key)) return 'happiness';
    if (['held_macho_brace','held_power_weight','exp_candy'].includes(key)) return 'training';
    if (key.startsWith('berry_') || ['curry_ingredients','mint_attack_food'].includes(key)) return 'hunger';
    return '';
  }
  function backpackItems() {
    if (Array.isArray(data.backpack)) return data.backpack;
    const seen = new Set();
    const categorized = (data.needs || []).flatMap(group => (group.items || []).map(item => ({...item, status: group.id}))).filter(item => !seen.has(item.key) && seen.add(item.key));
    if (categorized.length) return categorized;
    const purchased = new Map();
    (data.market || []).filter(item => item.purchased).forEach(item => {
      const key = item.itemKey;
      const previous = purchased.get(key);
      if (previous) previous.count += Number(item.amount || 1);
      else purchased.set(key, {key, label:item.label, icon:item.icon, count:Number(item.amount || 1), status:item.status || itemStatus(key)});
    });
    return [...purchased.values()];
  }
  function categoryItems(group, allItems = backpackItems()) {
    if (!group) return [];
    return allItems.filter(item => item.status === group.id || (group.items || []).some(groupItem => groupItem.key === item.key));
  }
  function toast(notice) { if (!notice.message) return; const node = $('.toast'); if (!node) return; const icon = notice.icon ? `<img src="${esc(notice.icon)}" alt="">` : '', message = String(notice.message), sentence = message.charAt(0).toUpperCase() + message.slice(1); clearTimeout(toastTimer); node.innerHTML = `${icon}<strong>${esc(sentence)}</strong>`; node.className = `toast is-visible ${notice.kind || ''} ${notice.icon ? 'has-item' : ''}`; toastTimer = setTimeout(() => node.classList.remove('is-visible'), 3600); }
  function setModal(name, open) { const node = $(`[data-bind="${name}-modal"]`); if (node) { node.classList.toggle('is-open', open); node.setAttribute('aria-hidden', String(!open)); } }
  function setSprite(companion) { const node = $('[data-bind="sprite"]'), urls = companion.spriteUrls || []; if (!node) return; let at = 0; node.src = urls[0] || ''; node.alt = companion.name || ''; node.onerror = () => { at += 1; if (urls[at]) node.src = urls[at]; else { node.onerror = null; node.style.opacity = '.2'; } }; }
  function paintScene(assets) {
    const stage = $('.companion-stage');
    const layer = $('[data-bind="background"]');
    if (!stage || !layer) return;
    const color = /^#[0-9a-f]{6}$/i.test(String(assets.backgroundColor || ''))
      ? assets.backgroundColor : '#6ea96a';
    const imageUrl = String(assets.background || '');
    const blurValue = Number(assets.backgroundBlur);
    const opacityValue = Number(assets.backgroundOpacity);
    const blur = Number.isFinite(blurValue) ? Math.max(0, Math.min(40, blurValue)) : 9;
    const opacity = Number.isFinite(opacityValue)
      ? Math.max(0, Math.min(100, opacityValue)) / 100 : .9;
    stage.style.backgroundColor = color;
    layer.style.backgroundImage = imageUrl ? `url(${JSON.stringify(imageUrl)})` : 'none';
    layer.style.filter = imageUrl ? `blur(${blur}px)` : 'none';
    layer.style.opacity = imageUrl ? String(opacity) : '0';
    layer.dataset.backgroundType = String(assets.backgroundMode || 'color');
  }
  // Lucide 0.468.0. The SVGs keep their original square viewBox and strokes.
  // See ../../vendor/lucide/LICENSE.
  const careIcons = {
    health: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />',
    happiness: '<circle cx="12" cy="12" r="10" /><path d="M8 14s1.5 2 4 2 4-2 4-2" /><line x1="9" x2="9.01" y1="9" y2="9" /><line x1="15" x2="15.01" y1="9" y2="9" />',
    hygiene: '<path d="M7 16.3c2.2 0 4-1.83 4-4.05 0-1.16-.57-2.26-1.71-3.19S7.29 6.75 7 5.3c-.29 1.45-1.14 2.84-2.29 3.76S3 11.1 3 12.25c0 2.22 1.8 4.05 4 4.05z" /><path d="M12.56 6.6A10.97 10.97 0 0 0 14 3.02c.5 2.5 2 4.9 4 6.5s3 3.5 3 5.5a6.98 6.98 0 0 1-11.91 4.97" />',
    training: '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z" />',
    hunger: '<path d="m2.37 11.223 8.372-6.777a2 2 0 0 1 2.516 0l8.371 6.777" /><path d="M21 15a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1h-5.25" /><path d="M3 15a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1h9" /><path d="m6.67 15 6.13 4.6a2 2 0 0 0 2.8-.4l3.15-4.2" /><rect width="20" height="4" x="2" y="11" rx="1" />',
  };
  function careIcon(category) {
    return `<svg viewBox="0 0 24 24" aria-hidden="true">${careIcons[category] || ''}</svg>`;
  }
  function renderStatuses() {
    const box = $('[data-bind="statuses"]');
    if (!box) return;
    box.innerHTML = (data.needs || []).map(item => `
      <button type="button" class="status-row" data-status="${esc(item.id)}" aria-controls="care-backpack"
        style="--status:${esc(item.color)}">
        <span><span class="status-icon" aria-hidden="true">${careIcon(item.id)}</span>${esc(item.label)}</span>
        <b>${esc(item.detail)}</b>
        <i class="status-track" aria-hidden="true"><em style="width:${Math.max(0, Math.min(100, item.value))}%"></em></i>
      </button>`).join('');
  }
  function renderBackpack() {
    const overview = $('[data-bind="care-overview"]');
    const view = $('[data-bind="backpack-category-view"]');
    const group = (data.needs || []).find(item => item.id === selected);
    overview.hidden = Boolean(group);
    view.hidden = !group;
    if (!group) return;

    text('[data-bind="backpack-category"]', group.backpackLabel || group.label);
    view.style.setProperty('--item-accent', group.color);
    view.querySelector('.category-dock-icon').innerHTML = careIcon(group.id);

    const itemGrid = $('[data-bind="backpack-items"]');
    const items = categoryItems(group);
    itemGrid.innerHTML = items.length ? items.map(item => `
      <button type="button" class="backpack-item-card" data-item="${esc(item.key)}">
        <span class="backpack-item-art"><img src="${esc(item.icon)}" alt=""></span>
        <strong>${esc(item.label)}</strong><span class="backpack-item-count">×${item.count}</span>
        <small>${esc(labels().useItem || 'Use item')}</small>
      </button>`).join('') : `<p class="empty-bag">${esc(group.empty || labels().empty || 'No items in this category yet.')}</p>`;
  }
  function animateCareView(view, offset) {
    careTransition?.cancel();
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    careTransition = view.animate([
      {opacity: .35, transform: `translateX(${offset}px)`},
      {opacity: 1, transform: 'translateX(0)'},
    ], {duration: 220, easing: 'cubic-bezier(.2, .75, .25, 1)'});
  }
  function openCategory(category) {
    selected = category;
    renderBackpack();
    $('[data-bind="backpack-items"]').scrollTop = 0;
    $('[data-action="close-category"]').focus({preventScroll: true});
    animateCareView($('[data-bind="backpack-category-view"]'), 12);
  }
  function closeCategory() {
    const previous = selected;
    selected = null;
    renderBackpack();
    [...document.querySelectorAll('[data-status]')]
      .find(button => button.dataset.status === previous)?.focus({preventScroll: true});
    animateCareView($('[data-bind="care-overview"]'), -12);
  }
  function renderMarket() {
    const box = $('[data-bind="market"]');
    if (!box) return;
    box.innerHTML = (data.market || []).map(item => `
      <button type="button" class="market-card ${item.purchased ? 'is-bought' : ''}" data-buy="${esc(item.slot)}" ${item.purchased ? 'disabled' : ''}>
        <span class="market-art"><img src="${esc(item.icon)}" alt=""></span>
        <strong>${esc(item.label)}</strong>
        <span class="market-card-meta"><small>×${item.amount}</small><span class="market-price"><img src="${esc(item.currencyIcon)}" alt="">${item.price}</span></span>
        ${item.purchased ? `<span class="purchased-label"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>Purchased</span>` : ''}
      </button>`).join('');
  }
  function showGift(gift) {
    if (!gift) return;
    image('[data-bind="gift-icon"]', gift.icon);
    text('[data-bind="gift-eyebrow"]', gift.eyebrow);
    text('[data-bind="gift-title"]', gift.title);
    text('[data-bind="gift-text"]', `+${gift.amount} ${gift.label}`);
    const companionName = data.companion?.name || '';
    const feeling = String(gift.feeling || '');
    const sentenceCaseFeeling = feeling
      ? feeling.charAt(0).toLocaleLowerCase() + feeling.slice(1)
      : '';
    text('[data-bind="gift-feeling"]', companionName && sentenceCaseFeeling ? `${companionName} is ${sentenceCaseFeeling}` : '');
    setModal('gift', true);
  }
  function labels() { return data.labels || {}; }
  function applyI18n(root) {
    const L = labels();
    root.querySelectorAll('[data-i18n-text]').forEach(el => { const v = L[el.dataset.i18nText]; if (v) el.textContent = v; });
    root.querySelectorAll('[data-i18n-alabel]').forEach(el => { const v = L[el.dataset.i18nAlabel]; if (v) el.setAttribute('aria-label', v); });
  }
  function syncTheme() {
    const mode = data.colorMode === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.onigimonTheme = mode;
    if (data.language) document.documentElement.lang = data.language;
    document.body.dataset.theme = mode;
  }
  function render() { syncTheme(); if (!data.companion) { $('.onigimon-app').innerHTML = `<p class="no-companion">${(data.labels || {}).noCompanion || 'No Onigimon companion selected.'}</p>`; return; } const c = data.companion, a = data.assets || {}, l = data.labels || {}; applyI18n(document); text('[data-bind="name"]', c.name); text('[data-bind="level"]', `${l.level || 'Level'} ${c.level || 1}`); text('[data-bind="message"]', data.message); image('[data-bind="mart"]', a.mart); image('[data-bind="comet"]', a.comet); image('[data-bind="redeem-icon"]', a.comet); image('[data-bind="star-piece"]', a.starPiece); text('[data-bind="comets"]', data.wallet?.comet_shards || 0); text('[data-bind="stars"]', data.wallet?.star_pieces || 0); text('[data-bind="market-title"]', l.market); text('[data-bind="redeem-title"]', l.redeemTitle); text('[data-bind="redeem-hint"]', l.redeemHint); $('[data-bind="redeem-code"]').placeholder = l.pasteCode || 'Paste code here'; $('.redeem-submit').textContent = l.redeem; const gift = $('[data-action="gift"]'); if (gift) { gift.textContent = data.marketGiftReady ? l.dailyGift : l.giftOpened; gift.disabled = !data.marketGiftReady; } setSprite(c); paintScene(a); renderStatuses(); renderBackpack(); renderMarket(); showGift(data.gift); }
  function sound(effect) { try { const Ctx = window.AudioContext || window.webkitAudioContext, ctx = new Ctx(), now = ctx.currentTime; const f = {feed:[620,820],play:[820,1080],clean:[360,660],train:[480,940],heal:[523,784]}[effect] || [800,1050]; f.forEach((hz, i) => { const o=ctx.createOscillator(), g=ctx.createGain(); o.frequency.setValueAtTime(hz, now+i*.07); g.gain.setValueAtTime(.0001, now+i*.07); g.gain.exponentialRampToValueAtTime(.075,now+i*.07+.02); g.gain.exponentialRampToValueAtTime(.0001,now+i*.07+.3); o.connect(g).connect(ctx.destination); o.start(now+i*.07); o.stop(now+i*.07+.31); }); setTimeout(()=>ctx.close(),600); } catch (_) {} }
  function bopSprite() {
    const sprite = $('.companion-sprite');
    if (!sprite || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    clearTimeout(spriteTimer);
    sprite.classList.remove('is-animated');
    void sprite.offsetWidth;
    sprite.classList.add('is-animated');
    spriteTimer = setTimeout(() => sprite.classList.remove('is-animated'), 550);
  }

  /* Speech adapted from Bencho's Eye Tracker (MIT, ../../vendor/bencho/LICENSE).
     A poke picks a fresh line, types it, holds it long enough to read, then
     folds the balloon away. A new poke replaces the whole pending turn. */
  function speak() {
    const lines = data.speechLines || [];
    if (!lines.length) return;
    const bubble = $('[data-bind="speech"]');
    const choices = lines.map((_, index) => index).filter(index => index !== lastSpeech);
    lastSpeech = choices[Math.floor(Math.random() * choices.length)] ?? 0;
    const line = lines[lastSpeech];
    const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const typed = bubble.querySelector('.speech-typed');
    const segments = typeof Intl.Segmenter === 'function'
      ? Array.from(new Intl.Segmenter(data.language, {granularity: 'grapheme'}).segment(line), entry => entry.segment)
      : Array.from(line);

    clearTimeout(speechTimer);
    bubble.querySelector('.speech-size').textContent = line;
    typed.textContent = '';
    bubble.dataset.tint = String(Math.floor(Math.random() * 3));
    bubble.toggleAttribute('data-typing', !still);
    bubble.setAttribute('data-speaking', '');
    text('[data-bind="speech-announcement"]', line);
    bopSprite();

    let at = 0;
    function typeNext() {
      typed.textContent += segments[at++];
      if (at < segments.length) speechTimer = setTimeout(typeNext, 38 + Math.random() * 30);
      else holdLine();
    }
    function holdLine() {
      bubble.removeAttribute('data-typing');
      speechTimer = setTimeout(() => bubble.removeAttribute('data-speaking'), 2100);
    }
    if (still) {
      typed.textContent = line;
      holdLine();
    } else {
      speechTimer = setTimeout(typeNext, 38);
    }
  }

  function animate(effect, itemIcon='') {
    const layer = $('.fx-layer'), sprite = $('.companion-sprite');
    if (!layer) return;
    sound(effect);
    if (effect === 'feed' && itemIcon) {
      const layerBox = layer.getBoundingClientRect();
      const spriteBox = sprite?.getBoundingClientRect();
      const itemSize = 48;
      const startX = layerBox.width - itemSize - 28;
      const startY = layerBox.height - itemSize - 34;
      const endX = spriteBox ? spriteBox.left - layerBox.left + spriteBox.width * .5 - itemSize * .5 : layerBox.width * .5;
      const endY = spriteBox ? spriteBox.top - layerBox.top + spriteBox.height * .52 - itemSize * .5 : layerBox.height * .45;
      const startCenterX = startX + itemSize * .5;
      const startCenterY = startY + itemSize * .5;
      const endCenterX = endX + itemSize * .5;
      const endCenterY = endY + itemSize * .5;
      const curve = .5522848;
      const controlOneY = startCenterY - (startCenterY - endCenterY) * curve;
      const controlTwoX = endCenterX + (startCenterX - endCenterX) * curve;
      const food = document.createElement('img');
      food.className = 'fx fx-food-toss';
      food.src = itemIcon;
      food.alt = '';
      food.style.offsetPath = `path("M ${startCenterX} ${startCenterY} C ${startCenterX} ${controlOneY}, ${controlTwoX} ${endCenterY}, ${endCenterX} ${endCenterY}")`;
      layer.appendChild(food);
      food.addEventListener('animationend', () => food.remove());
      setTimeout(bopSprite, 520);
      return;
    }

    bopSprite();

    if (effect === 'clean') {
      for (let i = 0; i < 11; i++) {
        const bubble = document.createElement('span');
        bubble.className = 'fx fx-bubble';
        bubble.style.left = `${28 + Math.random() * 44}%`;
        bubble.style.setProperty('--x', `${(Math.random() - .5) * 120}px`);
        bubble.style.setProperty('--y', `${-90 - Math.random() * 190}px`);
        bubble.style.setProperty('--bubble-size', `${10 + Math.random() * 19}px`);
        bubble.style.animationDelay = `${i * 45}ms`;
        layer.appendChild(bubble);
        bubble.addEventListener('animationend', () => bubble.remove());
      }
      if (itemIcon) {
        for (let i = 0; i < 4; i++) {
          const item = document.createElement('img');
          item.className = 'fx fx-used-item';
          item.src = itemIcon;
          item.alt = '';
          item.style.left = `${34 + Math.random() * 32}%`;
          item.style.setProperty('--x', `${(Math.random() - .5) * 170}px`);
          item.style.setProperty('--y', `${-80 - Math.random() * 150}px`);
          item.style.animationDelay = `${120 + i * 90}ms`;
          layer.appendChild(item);
          item.addEventListener('animationend', () => item.remove());
        }
      }
      return;
    }

    const styles = {heal:['♥','#08c46b'],feed:['♥','#f45bb3'],play:['☺','#ffbd55'],train:['✦','#c866e5'],gift:['✦','#f4cf55'],sparkle:['✦','#5bb5ef']};
    const [glyph, color] = styles[effect] || styles.sparkle;
    const actionStatus = {heal:'health', play:'happiness', train:'training'}[effect] || '';
    const actionIcon = actionStatus ? status(actionStatus)?.icon || '' : '';
    for (let i = 0; i < 12; i++) {
      let particle;
      if (actionStatus && itemIcon && i % 3 === 1) {
        particle = document.createElement('img');
        particle.className = 'fx fx-action-item';
        particle.src = itemIcon;
        particle.alt = '';
      } else {
        particle = document.createElement('span');
        particle.className = `fx fx-${effect}${actionIcon ? ' fx-action-symbol' : ''}`;
        if (actionIcon) particle.style.setProperty('--fx-icon', `url("${actionIcon}")`);
        else particle.textContent = glyph;
        particle.style.color = color;
      }
      particle.style.setProperty('--x', `${(Math.random() - .5) * 250}px`);
      particle.style.setProperty('--y', `${-50 - Math.random() * 180}px`);
      particle.style.animationDelay = `${i * 35}ms`;
      layer.appendChild(particle);
      particle.addEventListener('animationend', () => particle.remove());
    }
  }
  function useItem(btn) { if (busy) return; const item = backpackItems().find(i => i.key === btn.dataset.item); if (!item) return; const effect = effectFor(selected || item.status); busy=true; btn.disabled=true; animate(effect, item.icon); setTimeout(()=>pycmd(`onigimon:use:${item.key}`), effect === 'feed' ? 700 : 650); }
  const haptic = (pattern = 1) => pycmd(`haptic:${pattern}`);
  document.addEventListener('click', event => { const target=event.target.closest('button'); if(target&&!target.disabled)haptic(); const s=event.target.closest('[data-status]'); if(s){openCategory(s.dataset.status);return;} if(event.target.closest('[data-action="pet"]')){speak();return;} if(event.target.closest('[data-action="close-category"]')){closeCategory();return;} const item=event.target.closest('[data-item]');if(item){useItem(item);return;} const buy=event.target.closest('[data-buy]');if(buy&&!buy.disabled){busy=true;buy.disabled=true;animate('sparkle');setTimeout(()=>pycmd(`onigimon:market-buy:${buy.dataset.buy}`),450);return;} if(event.target.closest('[data-action="gift"]')){busy=true;animate('gift');setTimeout(()=>pycmd('onigimon:market-gift'),450);return;} if(event.target.closest('[data-action="open-store"]')){pycmd('onigimon:open-store');return;} if(event.target.closest('[data-action="open-redeem"]'))setModal('redeem',true); if(event.target.closest('[data-action="close-redeem"]'))setModal('redeem',false); if(event.target.closest('[data-action="close-gift"]'))setModal('gift',false); });
  document.addEventListener('submit', event => { if(!event.target.matches('[data-action="redeem-form"]'))return;event.preventDefault();const input=$('[data-bind="redeem-code"]'),code=input?.value.trim();if(code){setModal('redeem',false);pycmd(`onigimon:redeem:${code}`);} });
  document.addEventListener('keydown', event => { if(event.key==='Escape'){setModal('redeem',false);setModal('gift',false);if(selected)closeCategory();} });
  window.onOnigimonData = (payload, notice={}) => { data=payload||{};busy=false;render();toast(notice); };
  document.addEventListener('DOMContentLoaded', render);
})();
