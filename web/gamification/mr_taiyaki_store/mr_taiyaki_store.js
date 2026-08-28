(() => {
  let data = window.ONIGIRI_NOOK_DATA || {};
  let group = 'restaurants';
  let toastTimer;
  let rewardTimer;
  const S = () => data.strings || {};
  const t = (key, fallback) => S()[key] || fallback;
  const labels = () => ({
    restaurants: [t('restaurants_header', 'Restaurants'), t('store_desc_restaurants', 'Give your study space a new flavor.')],
    evolutions: [t('evolutions_header', 'Sushi Evolutions'), t('store_desc_evolutions', 'Grow the original Onigiri Stand into something extraordinary.')],
    shops: [t('shops_header', 'Shops'), t('store_desc_shops', 'Special destinations for your Nook.')],
  });
  function applyI18n(root) {
    root.querySelectorAll('[data-i18n-text]').forEach(el => { const v = S()[el.dataset.i18nText]; if (v) el.textContent = v; });
    root.querySelectorAll('[data-i18n-alt]').forEach(el => { const v = S()[el.dataset.i18nAlt]; if (v) el.alt = v; });
    root.querySelectorAll('[data-i18n-alabel]').forEach(el => { const v = S()[el.dataset.i18nAlabel]; if (v) el.setAttribute('aria-label', v); });
  }
  const $ = s => document.querySelector(s), all = s => [...document.querySelectorAll(s)];
  const esc = v => String(v == null ? '' : v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const base = () => data.imageBase || '';
  const itemFor = id => (data.store && Object.values(data.store).find(groupItems => groupItems && typeof groupItems === 'object' && !Array.isArray(groupItems) && groupItems[id]))?.[id];
  function syncTheme() {
    const root = document.documentElement, body = document.body;
    if (!body) return;
    const hostDark = [root, body].some(node => node.classList.contains('nightMode') || node.classList.contains('night_mode') || node.classList.contains('night-mode'));
    const dark = hostDark || window.matchMedia?.('(prefers-color-scheme: dark)').matches;
    body.dataset.theme = dark ? 'dark' : 'light';
  }
  function watchTheme() {
    syncTheme();
    const observer = new MutationObserver(syncTheme);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    if (document.body) observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    const media = window.matchMedia?.('(prefers-color-scheme: dark)');
    media?.addEventListener?.('change', syncTheme);
  }
  function toast(notice) { if (!notice.message) return; const node = $('.toast'); node.textContent = notice.message; node.className = `toast is-visible ${notice.kind || ''}`; clearTimeout(toastTimer); toastTimer = setTimeout(() => node.className = 'toast', 3600); }
  function celebrateCoins(amount) {
    if (!(Number(amount) > 0) || !data.coinImage) return;
    const wallet = $('.wallet');
    if (wallet) { wallet.classList.remove('is-rewarded'); void wallet.offsetWidth; wallet.classList.add('is-rewarded'); }
    const layer = document.createElement('div'); layer.className = 'coin-burst-layer';
    const origin = wallet ? wallet.getBoundingClientRect() : { left: window.innerWidth / 2, top: window.innerHeight / 2, width: 0, height: 0 };
    const count = Math.min(18, Math.max(8, Math.ceil(Number(amount) / 20)));
    for (let index = 0; index < count; index += 1) {
      const coin = document.createElement('img'); const angle = (Math.PI * 2 * index / count) + (Math.random() - .5) * .5; const distance = 90 + Math.random() * 190;
      coin.className = 'coin-burst'; coin.src = data.coinImage; coin.alt = ''; coin.style.left = `${origin.left + origin.width / 2}px`; coin.style.top = `${origin.top + origin.height / 2}px`;
      coin.style.setProperty('--coin-x', `${Math.cos(angle) * distance}px`); coin.style.setProperty('--coin-y', `${Math.sin(angle) * distance - 45}px`); coin.style.setProperty('--coin-r', `${Math.round((Math.random() - .5) * 540)}deg`); coin.style.animationDelay = `${index * 18}ms`; layer.appendChild(coin);
    }
    document.body.appendChild(layer); setTimeout(() => layer.remove(), 1050);
  }
  function renderItems() {
    const grid = $('[data-bind="items"]'), store = data.store || {}, owned = store.owned_items || [], current = store.current_theme_id;
    const items = store[group] || {};
    grid.innerHTML = Object.entries(items).map(([id, item]) => {
      const isOwned = owned.includes(id), isCurrent = id === current, price = Number(item.price || 0), unavailable = !isOwned && Number(store.coins || 0) < price;
      const sprite = item.image ? `<img class="preview-image${id.startsWith('restaurant_evo_') ? ' preview-image--evolution' : ''}${id === 'restaurant_evo_iv' ? ' preview-image--restaurant-iv' : ''}" src="${esc(base() + item.image)}" alt="${esc(item.name)}">` : '<span class="missing-sprite">?</span>';
      let action = `<button class="action-btn buy" data-buy="${esc(id)}" ${unavailable ? 'disabled' : ''}><span>${price}</span> ${esc(t('buy', 'Buy'))}</button>`;
      if (isCurrent) action = `<button class="action-btn current" data-equip="default">${esc(t('close_restaurant', 'Close Nook'))}</button>`;
      else if (isOwned) action = `<button class="action-btn equip" data-equip="${esc(id)}">${esc(t('store_equip', 'Equip'))}</button>`;
      return `<article class="store-item" style="--item-color:${esc(item.theme || '#cfa13d')}"><div class="item-preview">${sprite}<button class="info-btn" data-info="${esc(id)}" aria-label="${esc(t('store_about_item', 'About {}').replace('{}', item.name))}">i</button></div><div class="item-info"><div class="item-title"><h3>${esc(item.name)}</h3>${isCurrent ? `<span class="equipped">${esc(t('store_equipped', 'Equipped'))}</span>` : ''}</div><div class="item-price"><img src="${esc(data.coinImage || '')}" alt="">${price}</div></div>${action}</article>`;
    }).join('') || `<p class="empty">${esc(t('store_no_items_section', 'No items available in this section.'))}</p>`;
  }
  function render() {
    const store = data.store || {}; $('[data-bind="coins"]').textContent = store.coins || 0; $('[data-bind="coin"]').src = data.coinImage || ''; const mascot = $('[data-bind="mascot"]'); if (mascot) mascot.src = data.coinImage ? data.coinImage.replace('Tayaki_coin.webp', 'mr_taiyaki.webp') : '';
    applyI18n(document); const groupLabels = labels(); $('[data-bind="groupTitle"]').textContent = groupLabels[group][0]; $('[data-bind="groupDescription"]').textContent = groupLabels[group][1]; all('.nav-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.group === group)); renderItems();
  }
  function openModal() { const modal = $('[data-bind="modal"]'); modal.classList.add('is-open'); modal.setAttribute('aria-hidden', 'false'); setTimeout(() => $('[data-bind="code"]').focus(), 50); }
  function closeModal() { const modal = $('[data-bind="modal"]'); modal.classList.remove('is-open'); modal.setAttribute('aria-hidden', 'true'); }
  function openInfo(item) { if (!item) return; const modal = $('[data-bind="info-modal"]'); $('[data-bind="info-name"]').textContent = item.name || ''; $('[data-bind="info-description"]').textContent = item.description || 'A special Nook theme.'; const image = $('[data-bind="info-image"]'); image.src = item.image ? base() + item.image : ''; image.alt = item.name || ''; modal.classList.add('is-open'); modal.setAttribute('aria-hidden', 'false'); }
  function closeInfo() { const modal = $('[data-bind="info-modal"]'); modal.classList.remove('is-open'); modal.setAttribute('aria-hidden', 'true'); }
  function showReward(amount) { const modal = $('[data-bind="reward-modal"]'); $('[data-bind="reward-amount"]').textContent = Number(amount).toLocaleString(); $('[data-bind="reward-coin"]').src = data.coinImage || ''; modal.classList.add('is-open'); modal.setAttribute('aria-hidden', 'false'); }
  function closeReward() { const modal = $('[data-bind="reward-modal"]'); modal.classList.remove('is-open'); modal.setAttribute('aria-hidden', 'true'); }
  function playBuySound() { try { const AudioCtx = window.AudioContext || window.webkitAudioContext; const ctx = new AudioCtx(); const now = ctx.currentTime; [660, 880, 1100].forEach((frequency, index) => { const osc = ctx.createOscillator(), gain = ctx.createGain(); osc.type = 'sine'; osc.frequency.setValueAtTime(frequency, now + index * .055); gain.gain.setValueAtTime(.0001, now + index * .055); gain.gain.exponentialRampToValueAtTime(.075, now + index * .055 + .012); gain.gain.exponentialRampToValueAtTime(.0001, now + index * .055 + .13); osc.connect(gain).connect(ctx.destination); osc.start(now + index * .055); osc.stop(now + index * .055 + .14); }); setTimeout(() => ctx.close(), 450); } catch (_) {} }
  function burstSprites(button, item) { const source = item && item.image ? base() + item.image : data.coinImage; if (!source) return; const rect = button.getBoundingClientRect(); for (let index = 0; index < 7; index += 1) { const particle = document.createElement('img'); particle.className = 'buy-particle'; particle.src = source; particle.alt = ''; particle.style.setProperty('--x', `${(Math.random() - .5) * 155}px`); particle.style.setProperty('--y', `${-45 - Math.random() * 95}px`); particle.style.left = `${rect.left + rect.width / 2}px`; particle.style.top = `${rect.top + rect.height / 2}px`; particle.style.animationDelay = `${index * 22}ms`; document.body.appendChild(particle); particle.addEventListener('animationend', () => particle.remove()); } playBuySound(); }
  document.addEventListener('click', event => { const tab = event.target.closest('[data-group]'); if (tab) { group = tab.dataset.group; render(); } if (event.target.closest('[data-action="redeem"]')) openModal(); if (event.target.closest('[data-action="close-modal"]')) closeModal(); if (event.target.closest('[data-action="close-info"]')) closeInfo(); if (event.target.closest('[data-action="close-reward"]')) closeReward(); const info = event.target.closest('[data-info]'); if (info) openInfo(itemFor(info.dataset.info)); const buy = event.target.closest('[data-buy]'); if (buy && !buy.disabled) { buy.disabled = true; burstSprites(buy, itemFor(buy.dataset.buy)); setTimeout(() => pycmd(`store:buy:${buy.dataset.buy}`), 190); } const equip = event.target.closest('[data-equip]'); if (equip && !equip.disabled) { const itemId = equip.dataset.equip; equip.disabled = true; equip.textContent = itemId === 'default' ? 'Closing…' : 'Equipping…'; requestAnimationFrame(() => requestAnimationFrame(() => pycmd(`store:equip:${itemId}`))); } if (event.target.closest('[data-action="submit-code"]')) { const input = $('[data-bind="code"]'), code = input.value.trim(); if (code) { closeModal(); pycmd(`store:redeem:${code}`); } } });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') { closeModal(); closeInfo(); closeReward(); } if (event.key === 'Enter' && document.activeElement === $('[data-bind="code"]')) $('[data-action="submit-code"]').click(); });
  window.onNookData = (payload, notice = {}) => { data = payload || {}; render(); toast(notice); if (notice.kind === 'success' && Number(notice.coinsAdded) > 0) { celebrateCoins(notice.coinsAdded); clearTimeout(rewardTimer); rewardTimer = setTimeout(() => showReward(notice.coinsAdded), 1100); } };
  document.addEventListener('DOMContentLoaded', () => { watchTheme(); render(); });
})();
