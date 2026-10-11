(() => {
  let data = window.ONIGIRI_ONIGIMON_DATA || {}, selected = null, busy = false, toastTimer = 0;
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
    if (Array.isArray(data.backpack) && data.backpack.length) return data.backpack;
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
  function bindWalletPreview(stack) {
    const cards = [...stack.querySelectorAll('[data-category]')];
    const wallet = stack.closest('.item-wallet');
    let previewIndex = -1;
    let pendingPreview = 0;
    let pendingIndex = -1;
    const clear = () => {
      window.clearTimeout(pendingPreview);
      pendingIndex = -1;
      stack.removeAttribute('data-preview-category');
      wallet?.removeAttribute('aria-activedescendant');
      cards.forEach(card => {
        card.classList.remove('is-wallet-preview');
        card.setAttribute('aria-selected', 'false');
      });
      previewIndex = -1;
    };
    const preview = (card, index = cards.indexOf(card)) => {
      if (!card || index === previewIndex) return;
      cards.forEach(candidate => candidate.classList.toggle('is-wallet-preview', candidate === card));
      cards.forEach(candidate => candidate.setAttribute('aria-selected', String(candidate === card)));
      stack.dataset.previewCategory = card.dataset.category;
      wallet?.setAttribute('aria-activedescendant', card.id);
      previewIndex = index;
    };
    const previewAtPointer = event => {
      if (!cards.length) return;
      const pocket = stack.parentElement?.querySelector('.item-wallet-pocket');
      const pocketTop = pocket?.getBoundingClientRect().top ?? Infinity;
      if (event.clientY >= pocketTop) { clear(); return; }
      // Read the cards where they are actually painted after their hover
      // translations. Using offsetTop here selected a different card from the
      // one under the cursor because offsetTop ignores visual transforms.
      const hitOrder = [...cards].reverse();
      if (previewIndex >= 0) {
        hitOrder.splice(hitOrder.indexOf(cards[previewIndex]), 1);
        hitOrder.unshift(cards[previewIndex]);
      }
      const active = hitOrder.find(card => {
        const rect = card.getBoundingClientRect();
        return event.clientX >= rect.left && event.clientX <= rect.right
          && event.clientY >= rect.top && event.clientY <= Math.min(rect.bottom, pocketTop);
      });
      if (!active) { clear(); return; }
      const nextIndex = cards.indexOf(active);
      if (nextIndex === previewIndex || nextIndex === pendingIndex) return;
      window.clearTimeout(pendingPreview);
      // A tiny dwell makes the movement feel intentional without adding lag.
      pendingIndex = nextIndex;
      pendingPreview = window.setTimeout(() => {
        pendingIndex = -1;
        preview(cards[nextIndex], nextIndex);
      }, 70);
    };
    const enterWallet = () => wallet?.classList.add('is-wallet-hovered');
    const leaveWallet = () => {
      wallet?.classList.remove('is-wallet-hovered');
      if (!wallet?.matches(':focus-within')) clear();
    };
    const moveWithKeyboard = event => {
      if (!['ArrowUp', 'ArrowDown'].includes(event.key) || !cards.length) return;
      event.preventDefault();
      const direction = event.key === 'ArrowDown' ? 1 : -1;
      const start = previewIndex >= 0 ? previewIndex : (direction > 0 ? -1 : cards.length);
      const nextIndex = Math.max(0, Math.min(cards.length - 1, start + direction));
      preview(cards[nextIndex], nextIndex);
    };
    cards.forEach((card, index) => {
      card.id = `onigimon-wallet-card-${index}`;
      card.tabIndex = -1;
      card.setAttribute('role', 'option');
      card.setAttribute('aria-selected', 'false');
    });
    if (wallet._onigimonKeyHandler) {
      document.removeEventListener('keydown', wallet._onigimonKeyHandler, true);
    }
    wallet._onigimonKeyHandler = event => {
      if (document.activeElement !== wallet) return;
      if (['ArrowUp', 'ArrowDown'].includes(event.key)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        moveWithKeyboard(event);
        return;
      }
      if (!['Enter', ' '].includes(event.key)) return;
      const category = stack.dataset.previewCategory;
      if (!category) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      openCategory(category);
    };
    document.addEventListener('keydown', wallet._onigimonKeyHandler, true);
    // The wallet, rather than the exposed card strips, owns the hover state.
    wallet.onpointerenter = enterWallet;
    wallet.onpointermove = previewAtPointer;
    wallet.onpointerleave = leaveWallet;
    wallet.onfocus = null;
    wallet.onblur = () => {
      wallet.classList.remove('is-wallet-hovered');
      clear();
    };
    wallet.onkeydown = null;
    wallet.onclick = () => {
      const category = stack.dataset.previewCategory;
      if (category) openCategory(category);
    };
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
  function renderStatuses() { const box = $('[data-bind="statuses"]'); if (!box) return; box.innerHTML = (data.needs || []).map(item => `<button class="status-row ${item.id === selected ? 'is-selected' : ''}" data-status="${esc(item.id)}" style="--status:${esc(item.color)}" aria-pressed="${item.id === selected}"><span><span class="status-icon" style="--status-icon:url(&quot;${esc(item.icon)}&quot;)" aria-hidden="true"></span>${esc(item.label)}</span><b>${esc(item.detail)}</b><i class="status-track"><em style="width:${Math.max(0, Math.min(100, item.value))}%"></em></i></button>`).join(''); }
  function renderBackpack() {
    const box = $('[data-bind="backpack"]');
    const panel = $('.backpack-panel');
    const view = $('[data-bind="backpack-category-view"]');
    const dock = $('[data-bind="backpack-category-dock"]');
    const itemGrid = $('[data-bind="backpack-items"]');
    const group = selected ? (data.needs || []).find(item => item.id === selected) : null;
    const allItems = backpackItems();
    if (!box) return;
    const categories = data.needs || [];
    text('[data-bind="backpack-category"]', group?.label || `${categories.length} categories`);
    panel?.classList.toggle('is-category-open', Boolean(group));
    view?.setAttribute('aria-hidden', String(!group));
    box.innerHTML = categories.map((category, index) => {
      const items = categoryItems(category, allItems);
      const quantity = items.reduce((total, item) => total + Number(item.count || 0), 0);
      const pocketOffset = 42 + (categories.length - index - 1) * 25;
      // Keep the top card within the backpack panel while preserving the
      // staggered upward fan from the reference animation.
      const hoverLift = -(12 + (categories.length - index - 1) * 16);
      const reveal = Math.max(56, Math.abs(hoverLift) - 18);
      const tilts = [-3, 2, -1.5, 1.5, -0.75];
      const offsets = [-4, 2, -2, 2, 0];
      const tilt = tilts[index % tilts.length];
      const offset = offsets[index % offsets.length];
      return `<button class="wallet-item-card wallet-category-card" data-category="${esc(category.id)}" aria-label="Open ${esc(category.label)} items" style="--card-order:${index + 1};--card-delay:${index * 45}ms;--card-reveal:${reveal}px;--card-pocket-offset:${pocketOffset}px;--card-hover-lift:${hoverLift}px;--card-tilt:${tilt}deg;--card-offset-x:${offset}px;--item-accent:${esc(category.color)}"><span class="wallet-item-top"><span>${esc(category.label)}</span><span class="wallet-category-icon" style="--category-icon:url(&quot;${esc(category.icon)}&quot;)" aria-hidden="true"></span></span><span class="wallet-item-bottom"><strong>${items.length} item type${items.length === 1 ? '' : 's'}</strong><b>×${quantity}</b></span></button>`;
    }).join('');
    bindWalletPreview(box);
    if (!group || !dock || !itemGrid) return;
    const items = categoryItems(group, allItems);
    const quantity = items.reduce((total, item) => total + Number(item.count || 0), 0);
    dock.style.setProperty('--item-accent', group.color);
    dock.innerHTML = `<span class="category-dock-icon" style="--category-icon:url(&quot;${esc(group.icon)}&quot;);--item-accent:${esc(group.color)}" aria-hidden="true"></span><span><small>CARE CATEGORY</small><strong>${esc(group.label)}</strong><em>${items.length} item type${items.length === 1 ? '' : 's'} · ${quantity} available</em></span>`;
    itemGrid.scrollTop = 0;
    itemGrid.innerHTML = items.length ? items.map((item, index) => `<button class="backpack-item-card" data-item="${esc(item.key)}" aria-label="Use ${esc(item.label)}" style="--item-accent:${esc(group.color)};--item-delay:${index * 35 + 170}ms"><span class="backpack-item-art"><img src="${esc(item.icon)}" alt=""></span><strong>${esc(item.label)}</strong><span class="backpack-item-count">×${item.count}</span><small>Use item</small></button>`).join('') : `<p class="empty-bag">${esc(group.empty || data.labels?.empty || 'No items in this category yet.')}</p>`;
  }
  function openCategory(category) {
    if (!(data.needs || []).some(item => item.id === category)) return;
    selected = category;
    renderStatuses();
    renderBackpack();
    $('.backpack-panel')?.classList.add('is-open');
  }
  function closeCategory() {
    selected = null;
    renderStatuses();
    renderBackpack();
    $('.backpack-panel')?.classList.remove('is-open');
  }
  function renderMarket() { const box = $('[data-bind="market"]'); if (!box) return; box.innerHTML = (data.market || []).map(item => `<button class="market-card ${item.purchased ? 'is-bought' : ''}" data-buy="${esc(item.slot)}" ${item.purchased ? 'disabled' : ''}><span class="market-art"><img src="${esc(item.icon)}" alt="${esc(item.label)}"></span><strong>${esc(item.label)}</strong><span class="market-card-meta"><small>×${item.amount}</small><span class="market-price"><img src="${esc(item.currencyIcon)}" alt="">${item.price}</span></span>${item.purchased ? '<span class="purchased-label">Purchased</span>' : ''}</button>`).join(''); }
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
  function render() { if (!data.companion) { $('.onigimon-app').innerHTML = `<p class="no-companion">${(data.labels || {}).noCompanion || 'No Onigimon companion selected.'}</p>`; return; } const c = data.companion, a = data.assets || {}, l = data.labels || {}; applyI18n(document); text('[data-bind="name"]', c.name); text('[data-bind="level"]', `${l.level || 'Level'} ${c.level || 1}`); text('[data-bind="message"]', data.message); image('[data-bind="mart"]', a.mart); image('[data-bind="backpack-icon"]', a.backpack); image('[data-bind="comet"]', a.comet); image('[data-bind="redeem-icon"]', a.comet); image('[data-bind="star-piece"]', a.starPiece); text('[data-bind="comets"]', data.wallet?.comet_shards || 0); text('[data-bind="stars"]', data.wallet?.star_pieces || 0); text('[data-bind="market-title"]', l.market); text('[data-bind="backpack-title"]', l.backpack); text('[data-bind="redeem-title"]', l.redeemTitle); text('[data-bind="redeem-hint"]', l.redeemHint); $('[data-bind="redeem-code"]').placeholder = l.pasteCode || 'Paste code here'; $('.redeem-submit').textContent = l.redeem; const gift = $('[data-action="gift"]'); if (gift) { gift.textContent = data.marketGiftReady ? l.dailyGift : l.giftOpened; gift.disabled = !data.marketGiftReady; } setSprite(c); paintScene(a); renderStatuses(); renderBackpack(); renderMarket(); showGift(data.gift); }
  function sound(effect) { try { const Ctx = window.AudioContext || window.webkitAudioContext, ctx = new Ctx(), now = ctx.currentTime; const f = {feed:[620,820],play:[820,1080],clean:[360,660],train:[480,940],heal:[523,784]}[effect] || [800,1050]; f.forEach((hz, i) => { const o=ctx.createOscillator(), g=ctx.createGain(); o.frequency.setValueAtTime(hz, now+i*.07); g.gain.setValueAtTime(.0001, now+i*.07); g.gain.exponentialRampToValueAtTime(.075,now+i*.07+.02); g.gain.exponentialRampToValueAtTime(.0001,now+i*.07+.3); o.connect(g).connect(ctx.destination); o.start(now+i*.07); o.stop(now+i*.07+.31); }); setTimeout(()=>ctx.close(),600); } catch (_) {} }
  function animate(effect, itemIcon='') {
    const layer = $('.fx-layer'), sprite = $('.companion-sprite');
    if (!layer) return;
    sound(effect);
    const bop = (delay = 0) => setTimeout(() => {
      if (!sprite) return;
      sprite.classList.remove('is-animated');
      void sprite.offsetWidth;
      sprite.classList.add('is-animated');
      setTimeout(() => sprite.classList.remove('is-animated'), 700);
    }, delay);

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
      bop(520);
      return;
    }

    bop();

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
  document.addEventListener('click', event => { const target=event.target.closest('button, [data-status], [data-category], [data-item]'); if(target&&!target.disabled)haptic(); const s=event.target.closest('[data-status]'); if(s){openCategory(s.dataset.status);return;} const category=event.target.closest('[data-category]');if(category){openCategory(category.dataset.category);return;} if(event.target.closest('[data-action="close-category"]')){closeCategory();return;} const item=event.target.closest('[data-item]');if(item){useItem(item);return;} const buy=event.target.closest('[data-buy]');if(buy&&!buy.disabled){busy=true;buy.disabled=true;animate('sparkle');setTimeout(()=>pycmd(`onigimon:market-buy:${buy.dataset.buy}`),450);return;} if(event.target.closest('[data-action="gift"]')){busy=true;animate('gift');setTimeout(()=>pycmd('onigimon:market-gift'),450);return;} if(event.target.closest('[data-action="open-store"]')){pycmd('onigimon:open-store');return;} if(event.target.closest('[data-action="open-redeem"]'))setModal('redeem',true); if(event.target.closest('[data-action="close-redeem"]'))setModal('redeem',false); if(event.target.closest('[data-action="close-gift"]'))setModal('gift',false); });
  document.addEventListener('submit', event => { if(!event.target.matches('[data-action="redeem-form"]'))return;event.preventDefault();const input=$('[data-bind="redeem-code"]'),code=input?.value.trim();if(code){setModal('redeem',false);pycmd(`onigimon:redeem:${code}`);} });
  document.addEventListener('keydown', event => { if(event.key==='Escape'){setModal('redeem',false);setModal('gift',false);if(selected)closeCategory();} });
  window.onOnigimonData = (payload, notice={}) => { data=payload||{};busy=false;render();toast(notice); };
  document.addEventListener('DOMContentLoaded', render);
})();
