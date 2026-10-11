(() => {
  let data = window.ONIGIRI_NOOK_DATA || {};
  let group = 'restaurants';
  let toastTimer;
  let rewardTimer;
  let renderedGroup = '';
  let renderedCatalogKey = '';
  const infoEffects = {
    santas_coffee: 'snow',
    lunar_new_year: 'fireworks',
    pokestore: 'balls',
    astronigiri: 'stars',
  };
  const ballPositions = [
    [7, 12], [20, 30], [7, 59], [18, 82], [8, 93],
    [35, 6], [56, 9], [78, 7], [93, 23], [88, 49],
    [94, 75], [78, 91], [54, 94], [31, 91],
  ];
  const S = () => data.strings || {};
  const t = (key, fallback) => S()[key] || fallback;
  const labels = () => ({
    restaurants: [t('restaurants_header', 'Restaurants'), t('store_desc_restaurants', 'Give your study space a new flavor.')],
    evolutions: [t('evolutions_header', 'Sushi Evolutions'), t('store_desc_evolutions', 'Grow the original Onigiri Stand into something extraordinary.')],
    shops: [t('shops_header', 'Shops'), t('store_desc_shops', 'Special destinations for your Nook.')],
    devs: [t('devs_header', 'Developers'), t('store_desc_devs', 'An homage to everyone who helped build Onigiri.')],
  });
  function applyI18n(root) {
    root.querySelectorAll('[data-i18n-text]').forEach(el => { const v = S()[el.dataset.i18nText]; if (v) el.textContent = v; });
    root.querySelectorAll('[data-i18n-placeholder]').forEach(el => { const v = S()[el.dataset.i18nPlaceholder]; if (v) el.placeholder = v; });
    root.querySelectorAll('[data-i18n-alt]').forEach(el => { const v = S()[el.dataset.i18nAlt]; if (v) el.alt = v; });
    root.querySelectorAll('[data-i18n-alabel]').forEach(el => { const v = S()[el.dataset.i18nAlabel]; if (v) el.setAttribute('aria-label', v); });
  }
  const $ = s => document.querySelector(s), all = s => [...document.querySelectorAll(s)];
  const haptic = (pattern = 1) => pycmd(`haptic:${pattern}`);
  const esc = v => String(v == null ? '' : v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const base = () => data.imageBase || '';
  const itemFor = id => (data.store && Object.values(data.store).find(groupItems => groupItems && typeof groupItems === 'object' && !Array.isArray(groupItems) && groupItems[id]))?.[id];
  function syncTheme() {
    const root = document.documentElement, body = document.body;
    if (!body) return;
    // The payload reflects Onigiri's effective setting, including a user
    // light-mode override on a dark operating system.
    const mode = data.colorMode === 'dark' ? 'dark' : 'light';
    root.dataset.storeTheme = mode;
    body.dataset.theme = mode;
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
    if (!(Number(amount) > 0)) return;
    const wallet = $('.wallet');
    if (!wallet) return;
    wallet.classList.remove('is-rewarded');
    void wallet.offsetWidth;
    wallet.classList.add('is-rewarded');
    setTimeout(() => wallet.classList.remove('is-rewarded'), 760);
  }
  function itemState(store, id, item) {
    const owned = store.owned_items || [];
    const isOwned = owned.includes(id);
    const isCurrent = id === store.current_theme_id;
    const price = Number(item.price || 0);
    return { isOwned, isCurrent, price, unavailable: !isOwned && Number(store.coins || 0) < price };
  }
  function actionMarkup(store, id, item) {
    const { isOwned, isCurrent, price, unavailable } = itemState(store, id, item);
    if (isCurrent) return `<button class="action-btn current" data-equip="default">${esc(t('close_restaurant', 'Close Nook'))}</button>`;
    if (isOwned) return `<button class="action-btn equip" data-equip="${esc(id)}">${esc(t('store_equip', 'Equip'))}</button>`;
    return `<button class="action-btn buy" data-buy="${esc(id)}" ${unavailable ? 'disabled' : ''}><span>${price}</span> ${esc(t('buy', 'Buy'))}</button>`;
  }
  function updateCardState(card, store, id, item) {
    const { isCurrent } = itemState(store, id, item);
    const title = card.querySelector('.item-title');
    let badge = title.querySelector('.equipped');
    if (isCurrent && !badge) {
      badge = document.createElement('span');
      badge.className = 'equipped';
      title.appendChild(badge);
    }
    if (badge) {
      if (isCurrent) badge.textContent = t('store_equipped', 'Equipped');
      else badge.remove();
    }
    const action = card.querySelector('.action-btn');
    const markup = actionMarkup(store, id, item);
    if (action.outerHTML !== markup) action.outerHTML = markup;
  }
  function renderItems() {
    const grid = $('[data-bind="items"]'), store = data.store || {};
    const items = store[group] || {};
    const entries = Object.entries(items);
    const catalogKey = JSON.stringify(entries.map(([id, item]) => [id, item.name, item.description, item.price, item.image, item.theme]));
    if (renderedGroup === group && renderedCatalogKey === catalogKey) {
      const cards = new Map(all('.store-item[data-item-id]').map(card => [card.dataset.itemId, card]));
      if (cards.size === entries.length) {
        entries.forEach(([id, item]) => updateCardState(cards.get(id), store, id, item));
        return;
      }
    }
    grid.innerHTML = entries.map(([id, item]) => {
      const { isCurrent, price } = itemState(store, id, item);
      const sprite = item.image ? `<img class="preview-image${id.startsWith('restaurant_evo_') ? ' preview-image--evolution' : ''}${id === 'restaurant_evo_iv' ? ' preview-image--restaurant-iv' : ''}" src="${esc(base() + item.image)}" alt="${esc(item.name)}">` : '<span class="missing-sprite">?</span>';
      return `<article class="store-item" data-item-id="${esc(id)}" style="--item-color:${esc(item.theme || '#cfa13d')}"><div class="item-preview">${sprite}<button class="info-btn" data-info="${esc(id)}" aria-label="${esc(t('store_about_item', 'About {}').replace('{}', item.name))}"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><path d="M12 16v-4"></path><path d="M12 8h.01"></path></svg></button></div><div class="item-info"><div class="item-title"><h3>${esc(item.name)}</h3>${isCurrent ? `<span class="equipped">${esc(t('store_equipped', 'Equipped'))}</span>` : ''}</div><div class="item-price"><img src="${esc(data.coinImage || '')}" alt="">${price}</div></div>${actionMarkup(store, id, item)}</article>`;
    }).join('') || `<p class="empty">${esc(t('store_no_items_section', 'No items available in this section.'))}</p>`;
    renderedGroup = group;
    renderedCatalogKey = catalogKey;
  }
  function render() {
    const store = data.store || {}; $('[data-bind="coins"]').textContent = store.coins || 0; $('[data-bind="coin"]').src = data.coinImage || ''; $('[data-bind="redeem-icon"]').src = data.coinImage || ''; const mascot = $('[data-bind="mascot"]'); if (mascot) mascot.src = data.coinImage ? data.coinImage.replace('Tayaki_coin.webp', 'mr_taiyaki.webp') : '';
    applyI18n(document); const groupLabels = labels(); $('[data-bind="groupTitle"]').textContent = groupLabels[group][0]; $('[data-bind="groupDescription"]').textContent = groupLabels[group][1]; all('.nav-btn').forEach(btn => { const active = btn.dataset.group === group; btn.classList.toggle('active', active); btn.setAttribute('aria-pressed', String(active)); }); renderItems();
  }
  function openModal() { const modal = $('[data-bind="modal"]'); modal.classList.add('is-open'); modal.setAttribute('aria-hidden', 'false'); setTimeout(() => $('[data-bind="code"]').focus(), 50); }
  function closeModal() { const modal = $('[data-bind="modal"]'); modal.classList.remove('is-open'); modal.setAttribute('aria-hidden', 'true'); }
  function createAtmosphereParticle(effect, index) {
    const particle = document.createElement('span');
    particle.className = `atmosphere-particle atmosphere-${effect}`;
    const [x, y] = effect === 'balls' ? ballPositions[index % ballPositions.length] : [4 + Math.random() * 92, Math.random() * 108 - 12];
    particle.style.setProperty('--x', `${x}%`);
    particle.style.setProperty('--y', `${y}%`);
    particle.style.setProperty('--size', `${effect === 'balls' ? 28 + Math.random() * 14 : 4 + Math.random() * 10}px`);
    particle.style.setProperty('--duration', `${7 + Math.random() * 7}s`);
    particle.style.setProperty('--delay', `${-Math.random() * 9}s`);
    particle.style.setProperty('--turn', `${Math.round((Math.random() - .5) * 80)}deg`);
    if (effect === 'balls' && data.pokeballImage) {
      const sprite = document.createElement('img');
      sprite.className = 'atmosphere-ball-sprite';
      sprite.src = data.pokeballImage;
      sprite.alt = '';
      particle.appendChild(sprite);
    }
    particle.dataset.index = String(index);
    return particle;
  }
  function syncInfoAtmosphere(modal, itemId) {
    const effect = infoEffects[itemId];
    const previous = modal.querySelector('.modal-atmosphere');
    previous?.remove();
    delete modal.dataset.effect;
    if (!effect) return;
    const layer = document.createElement('div');
    layer.className = 'modal-atmosphere';
    layer.setAttribute('aria-hidden', 'true');
    const count = effect === 'snow' ? 22 : effect === 'fireworks' ? 12 : effect === 'balls' ? ballPositions.length : 11;
    for (let index = 0; index < count; index += 1) layer.appendChild(createAtmosphereParticle(effect, index));
    modal.prepend(layer);
    modal.dataset.effect = effect;
  }
  function openInfo(item, itemId) { if (!item) return; const modal = $('[data-bind="info-modal"]'); const card = modal.querySelector('.item-info-modal'); card.style.setProperty('--modal-item-color', item.theme || '#cfa13d'); syncInfoAtmosphere(modal, itemId); $('[data-bind="info-name"]').textContent = item.name || ''; $('[data-bind="info-description"]').textContent = item.description || 'A special Nook theme.'; const image = $('[data-bind="info-image"]'); image.src = item.image ? base() + item.image : ''; image.alt = item.name || ''; modal.classList.add('is-open'); modal.setAttribute('aria-hidden', 'false'); }
  function closeInfo() { const modal = $('[data-bind="info-modal"]'); modal.classList.remove('is-open'); modal.setAttribute('aria-hidden', 'true'); modal.querySelector('.modal-atmosphere')?.remove(); delete modal.dataset.effect; }
  function showReward(amount) { const modal = $('[data-bind="reward-modal"]'); $('[data-bind="reward-amount"]').textContent = Number(amount).toLocaleString(); $('[data-bind="reward-coin"]').src = data.coinImage || ''; modal.classList.add('is-open'); modal.setAttribute('aria-hidden', 'false'); }
  function closeReward() { const modal = $('[data-bind="reward-modal"]'); modal.classList.remove('is-open'); modal.setAttribute('aria-hidden', 'true'); }
  document.addEventListener('click', event => { const target = event.target.closest('button, [data-group], [data-info]'); if (target && !target.disabled) haptic(); const tab = event.target.closest('[data-group]'); if (tab) { group = tab.dataset.group; render(); } if (event.target.closest('[data-action="redeem"]')) openModal(); if (event.target.closest('[data-action="close-modal"]')) closeModal(); if (event.target.closest('[data-action="close-info"]')) closeInfo(); if (event.target.closest('[data-action="close-reward"]')) closeReward(); const info = event.target.closest('[data-info]'); if (info) openInfo(itemFor(info.dataset.info), info.dataset.info); const buy = event.target.closest('[data-buy]'); if (buy && !buy.disabled) { buy.disabled = true; pycmd(`store:buy:${buy.dataset.buy}`); } const equip = event.target.closest('[data-equip]'); if (equip && !equip.disabled) { const itemId = equip.dataset.equip; equip.disabled = true; equip.textContent = itemId === 'default' ? 'Closing…' : 'Equipping…'; requestAnimationFrame(() => requestAnimationFrame(() => pycmd(`store:equip:${itemId}`))); } if (event.target.closest('[data-action="submit-code"]')) { const input = $('[data-bind="code"]'), code = input.value.trim(); if (code) { closeModal(); pycmd(`store:redeem:${code}`); } } });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') { closeModal(); closeInfo(); closeReward(); } if (event.key === 'Enter' && document.activeElement === $('[data-bind="code"]')) $('[data-action="submit-code"]').click(); });
  window.onNookData = (payload, notice = {}) => { data = payload || {}; render(); toast(notice); if (notice.kind === 'success' && Number(notice.coinsAdded) > 0) { celebrateCoins(notice.coinsAdded); clearTimeout(rewardTimer); rewardTimer = setTimeout(() => showReward(notice.coinsAdded), 1100); } };
  document.addEventListener('DOMContentLoaded', () => { watchTheme(); render(); });
})();
