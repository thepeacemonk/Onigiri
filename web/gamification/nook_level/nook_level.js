(() => {
  let data = window.ONIGIRI_NOOK_DATA || {};
  let activeGroup = 'restaurants';
  const $ = (selector) => document.querySelector(selector);
  const all = (selector) => [...document.querySelectorAll(selector)];
  const text = (selector, value) => { const node = $(selector); if (node) node.textContent = value == null ? '' : value; };
  const esc = (value) => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const base = () => data.imageBase || '';
  const S = () => data.strings || {};
  const t = (key, fallback) => S()[key] || fallback;
  function applyI18n(root) {
    root.querySelectorAll('[data-i18n-text]').forEach(el => { const v = S()[el.dataset.i18nText]; if (v) el.textContent = v; });
    root.querySelectorAll('[data-i18n-alt]').forEach(el => { const v = S()[el.dataset.i18nAlt]; if (v) el.alt = v; });
    root.querySelectorAll('[data-i18n-alabel]').forEach(el => { const v = S()[el.dataset.i18nAlabel]; if (v) el.setAttribute('aria-label', v); });
  }
  function stageLabel(stage) {
    const keys = { collect: 'nook_collect', prepare: 'nook_stage_prepare', deliver: 'nook_stage_deliver', completed: 'nook_stage_completed' };
    return t(keys[stage] || 'nook_collect', String(stage).replace(/^./, c => c.toUpperCase()));
  }

  function percent(n, d) { return Math.max(0, Math.min(100, d ? Math.round(n / d * 100) : 0)); }
  function setWidth(selector, value) { const node = $(selector); if (node) node.style.width = `${value}%`; }
  function setPage(page) {
    all('[data-page-content]').forEach(node => node.classList.toggle('is-active', node.dataset.pageContent === page));
    all('.tab').forEach(node => node.classList.toggle('is-active', node.dataset.page === page));
  }
  function renderCollection() {
    const grid = $('[data-bind="collection"]'); if (!grid) return;
    const items = (data.store && data.store[activeGroup]) || {};
    const owned = (data.store && data.store.owned_items) || [];
    const current = data.store && data.store.current_theme_id;
    grid.innerHTML = Object.entries(items).map(([id, item]) => {
      const ownedState = owned.includes(id); const currentState = id === current;
      const sprite = item.image ? `<img src="${esc(base() + item.image)}" alt="${esc(item.name)}">` : '<span class="no-sprite">?</span>';
      return `<article class="collection-card ${ownedState ? 'is-owned' : 'is-locked'}" style="--item-color:${esc(item.theme || '#9aa0aa')}"><div class="collection-sprite">${sprite}</div><div><h3>${esc(item.name)}</h3><p>${ownedState ? esc(item.description || '') : 'Locked — visit the store to unlock.'}</p></div><span class="collection-state">${currentState ? 'Equipped' : ownedState ? 'Owned' : 'Locked'}</span></article>`;
    }).join('') || `<p class="empty">${esc(t('nook_no_items_yet', 'No items available yet.'))}</p>`;
  }
  function renderRush() {
    const rush = data.rush || {}; const p = percent(rush.current || 0, rush.target || 1);
    text('[data-bind="rushTitle"]', rush.title); text('[data-bind="rushName"]', rush.name); text('[data-bind="rushDescription"]', rush.description);
    all('[data-bind="rushCurrent"]').forEach(n => n.textContent = rush.current || 0); all('[data-bind="rushTarget"]').forEach(n => n.textContent = rush.target || 0);
    all('[data-bind="rushPercent"]').forEach(n => n.textContent = `${p}%`); setWidth('[data-bind="rushBar"]', p);
    const ring = $('[data-bind="rushRing"]'); if (ring) ring.style.setProperty('--p', `${p * 3.6}deg`);
    text('[data-bind="rushStage"]', stageLabel(rush.stage || 'collect')); text('[data-bind="rushXp"]', rush.xp_reward || 0); text('[data-bind="rarity"]', rush.difficultyLabel || t('rarity_common', 'Common')); text('[data-bind="ingredientsLabel"]', rush.ingredients_label || t('nook_ingredients', 'Ingredients'));
    const ingredients = $('[data-bind="ingredients"]'); if (ingredients) ingredients.innerHTML = (rush.ingredients || []).map(item => `<div><span>${esc(item.name)}</span><strong>${esc(item.cards)} ${esc(t('cards', 'cards'))}</strong></div>`).join('') || `<p class="empty">${esc(t('nook_ingredients_hidden', 'Study to reveal today\u2019s ingredients.'))}</p>`;
    const counts = data.recipeCounts || {}; const counter = $('[data-bind="recipeCounts"]'); if (counter) counter.innerHTML = Object.entries(counts).map(([key, count]) => `<span class="count ${key}">${esc(t('rarity_' + key, key))} <b>${count}</b></span>`).join('');
    const history = $('[data-bind="history"]'); if (history) history.innerHTML = (data.history || []).slice(0, 12).map(item => `<article><span class="rarity ${esc(item.difficulty)}">${esc(t('rarity_' + item.difficulty, item.difficulty))}</span><div><h3>${esc(item.name)}</h3><p>${esc(item.description)}</p></div><small>${esc(item.date)}</small></article>`).join('') || `<p class="empty">${esc(t('nook_history_empty', 'Your completed Rushes will appear here.'))}</p>`;
  }
  function render() {
    applyI18n(document);
    const progress = data.progress || {}, current = data.current || {}, store = data.store || {}; const xp = percent(progress.xpIntoLevel || 0, progress.xpToNextLevel || 1);
    text('[data-bind="name"]', progress.name || t('restaurant_level_title', 'Nook Level')); text('[data-bind="phrase"]', progress.phrase); text('[data-bind="level"]', progress.level || 0); text('[data-bind="xpText"]', `${progress.xpIntoLevel || 0} / ${progress.xpToNextLevel || 0} ${t('xp_label', 'XP')}`); text('[data-bind="coins"]', store.coins || 0);
    setWidth('[data-bind="xpBar"]', xp); text('[data-bind="currentName"]', current.name); text('[data-bind="currentDescription"]', current.description);
    const image = $('[data-bind="themeImage"]'); if (image) image.src = base() + (current.image || 'sushi/onigiri_stand.webp'); const stage = $('[data-bind="themeStage"]'); const theme = current.theme || '#d49083'; if (stage) stage.style.setProperty('--theme', theme); document.documentElement.style.setProperty('--theme', theme); const logo = $('.nook-logo'); if (logo) logo.src = base().replace('/system_files/gamification_images/nook_folder/', '/system_files/system_icons/unavailable_for_users/') + 'nook.svg';
    all('.coin').forEach(img => img.src = data.coinImage || ''); renderRush(); renderCollection();
  }
  function tick() { const rush = data.rush || {}; const remaining = Math.max(0, (rush.endAt || 0) - Date.now()); const h = Math.floor(remaining / 3600000), m = Math.floor(remaining / 60000) % 60, s = Math.floor(remaining / 1000) % 60; text('[data-bind="rushTimer"]', `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`); }
  function toast(notice) { if (!notice.message) return; const node = $('.toast'); node.textContent = notice.message; node.className = `toast is-visible ${notice.kind || ''}`; setTimeout(() => node.className = 'toast', 3500); }
  document.addEventListener('click', event => { const page = event.target.closest('[data-page], [data-page-link]'); if (page) setPage(page.dataset.page || page.dataset.pageLink); const store = event.target.closest('[data-action="store"]'); if (store) pycmd('nook:open-store'); const group = event.target.closest('[data-group]'); if (group) { activeGroup = group.dataset.group; all('.collection-tab').forEach(node => node.classList.toggle('is-active', node === group)); renderCollection(); } });
  window.onNookData = (payload, notice = {}) => { data = payload || {}; render(); tick(); toast(notice); };
  document.addEventListener('DOMContentLoaded', () => { render(); tick(); setInterval(tick, 1000); });
})();
