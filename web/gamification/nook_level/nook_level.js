(() => {
  'use strict';

  let data = window.ONIGIRI_NOOK_DATA || {};
  let activeGroup = 'restaurants';
  let toastTimer;
  const deliveryMessageIndex = Math.floor(Math.random() * 5) + 1;
  const $ = selector => document.querySelector(selector);
  const all = selector => [...document.querySelectorAll(selector)];
  const text = (selector, value) => all(selector).forEach(node => {
    node.textContent = value == null ? '' : value;
  });
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const base = () => data.imageBase || '';
  const t = (key, fallback) => {
    const value = (data.strings || {})[key];
    return value && value !== key ? value : fallback;
  };
  const number = value => Number(value || 0).toLocaleString();
  const percent = (n, d) => Math.max(0, Math.min(100, d ? Math.round(n / d * 100) : 0));

  function applyI18n() {
    all('[data-i18n-text]').forEach(el => {
      el.textContent = t(el.dataset.i18nText, el.textContent);
    });
    all('[data-i18n-alt]').forEach(el => {
      el.alt = t(el.dataset.i18nAlt, el.alt);
    });
    all('[data-i18n-alabel]').forEach(el => {
      el.setAttribute('aria-label', t(el.dataset.i18nAlabel, el.getAttribute('aria-label')));
    });
  }

  /* Like settings_web, compute solid color tints in JS: older Anki WebViews
     cannot reliably render CSS color-mix(). No gradients or image processing. */
  function mix(hex, background, weight) {
    const foreground = /^#[0-9a-f]{6}$/i.test(hex || '') ? hex : '#d49083';
    const channels = [1, 3, 5].map(offset => Math.round(
      parseInt(foreground.slice(offset, offset + 2), 16) * weight
      + parseInt(background.slice(offset, offset + 2), 16) * (1 - weight)
    ));
    return `rgb(${channels.join(',')})`;
  }

  function sceneColor(theme) {
    const dark = document.documentElement.dataset.nookTheme === 'dark';
    return mix(theme, dark ? '#242424' : '#fbf8f4', dark ? .32 : .26);
  }

  function accentText(theme) {
    const color = /^#[0-9a-f]{6}$/i.test(theme || '') ? theme : '#d49083';
    const red = parseInt(color.slice(1, 3), 16);
    const green = parseInt(color.slice(3, 5), 16);
    const blue = parseInt(color.slice(5, 7), 16);
    return red * .299 + green * .587 + blue * .114 > 155 ? '#202124' : '#ffffff';
  }

  function syncTheme() {
    const root = document.documentElement;
    const hostDark = [root, document.body].some(node => node &&
      ['nightMode', 'night_mode', 'night-mode'].some(name => node.classList.contains(name)));
    // The explicit payload also honors the add-on's theme override.
    root.dataset.nookTheme = data.colorMode || (hostDark ? 'dark' : 'light');
    const theme = (data.current || {}).theme || '#d49083';
    const dark = root.dataset.nookTheme === 'dark';
    root.style.setProperty('--theme', theme);
    root.style.setProperty('--accent', theme);
    root.style.setProperty('--accent-ink', accentText(theme));
    root.style.setProperty('--accent-soft', mix(theme, dark ? '#242424' : '#ffffff', dark ? .34 : .16));
    root.style.setProperty('--scene-bg', sceneColor(theme));
  }

  function stageLabel(stage) {
    const keys = {
      collect: 'nook_collect', prepare: 'nook_stage_prepare',
      deliver: 'nook_stage_deliver', completed: 'nook_stage_completed'
    };
    return t(keys[stage] || 'nook_collect', String(stage).replace(/^./, c => c.toUpperCase()));
  }

  function setProgress(name, value) {
    const track = $(`[data-progress="${name}"]`);
    if (!track) return;
    track.setAttribute('aria-valuenow', value);
    track.querySelector('i').style.width = `${value}%`;
  }

  function setPage(page) {
    all('[data-page-content]').forEach(node => {
      node.classList.toggle('is-active', node.dataset.pageContent === page);
    });
    all('.tab').forEach(node => {
      const selected = node.dataset.page === page;
      node.classList.toggle('is-active', selected);
      if (selected) node.setAttribute('aria-current', 'page');
      else node.removeAttribute('aria-current');
    });
  }

  function renderCollection() {
    const grid = $('[data-bind="collection"]');
    if (!grid) return;
    const store = data.store || {};
    let items = { ...(store[activeGroup] || {}) };
    // The starting stand belongs in the evolution collection, too.
    if (activeGroup === 'evolutions' && data.defaultItem) {
      items = { default: data.defaultItem, ...items };
    }
    const owned = store.owned_items || [];
    const current = store.current_theme_id || 'default';
    const isOwned = id => id === 'default' || id === current || owned.includes(id);
    const entries = Object.entries(items);
    const allNookIds = new Set(['default']);
    ['restaurants', 'evolutions', 'shops', 'devs'].forEach(group => {
      Object.keys(store[group] || {}).forEach(id => allNookIds.add(id));
    });
    const allOwnedIds = new Set(['default', current, ...owned]);
    text('[data-bind="ownedTotal"]', [...allOwnedIds].filter(id => allNookIds.has(id)).length);
    text('[data-bind="availableTotal"]', allNookIds.size);
    grid.innerHTML = entries.map(([id, item], index) => {
      const ownedState = isOwned(id);
      const currentState = id === current;
      const state = currentState ? t('store_equipped', 'Equipped')
        : ownedState ? t('owned', 'Owned') : t('locked', 'Locked');
      const sprite = item.image
        ? `<img src="${esc(base() + item.image)}" alt="" loading="lazy" decoding="async">`
        : '<span class="no-sprite" aria-hidden="true"><span class="placeholder-building"></span></span>';
      return `<article class="collection-card ${ownedState ? 'is-owned' : 'is-locked'} ${currentState ? 'is-equipped' : ''}" style="--scene-bg:${sceneColor(item.theme)};--entry-delay:${Math.min(index, 7) * 25}ms">
        <div class="collection-sprite">${sprite}</div>
        <div class="collection-copy"><h3>${esc(item.name)}</h3><p>${esc(item.description || '')}</p></div>
        <div class="collection-footer"><span class="collection-state"><span class="state-mark ${ownedState ? 'state-owned' : 'state-locked'}" aria-hidden="true"></span>${esc(state)}</span></div>
      </article>`;
    }).join('') || `<p class="empty">${esc(t('nook_no_items_yet', 'No items available yet.'))}</p>`;
  }

  function renderRush() {
    const rush = data.rush || {};
    const p = percent(rush.current || 0, rush.target || 1);
    text('[data-bind="rushTitle"]', rush.title || t('recipe_rush_title', 'Nook Rush'));
    text('[data-bind="rushName"]', rush.name);
    text('[data-bind="rushDescription"]', rush.description);
    text('[data-bind="rushCurrent"]', number(rush.current));
    text('[data-bind="rushTarget"]', number(rush.target));
    text('[data-bind="rushPercent"]', `${p}%`);
    setProgress('rush', p);
    const ring = $('[data-bind="rushRing"]');
    if (ring) ring.style.setProperty('--ring-offset', 100 - p);
    text('[data-bind="rushStage"]', stageLabel(rush.stage || 'collect'));
    text('[data-bind="rushXp"]', number(rush.xp_reward));
    const rarity = $('[data-bind="rarity"]');
    const difficulty = ['common', 'uncommon', 'rare', 'epic', 'legendary'].includes(rush.difficulty)
      ? rush.difficulty : 'common';
    rarity.className = `rarity ${difficulty}`;
    rarity.textContent = rush.difficultyLabel || t('rarity_common', 'Common');
    text('[data-bind="ingredientsLabel"]', rush.ingredients_label || t('nook_ingredients', 'Ingredients'));
    // Treat reviewed cards as a consumable budget. Each card belongs to one
    // ingredient only: fill the current ingredient before advancing to the
    // next one in recipe order.
    let remainingIngredientCards = Math.max(0, Number(rush.current) || 0);
    $('[data-bind="ingredients"]').innerHTML = (rush.ingredients || []).map((item, index) => {
      const required = Math.max(0, Number(item.cards) || 0);
      const collected = Math.min(required, remainingIngredientCards);
      const ingredientPercent = percent(collected, required || 1);
      remainingIngredientCards = Math.max(0, remainingIngredientCards - collected);
      return `<div class="ingredient-row">
        <span class="ingredient-number">${String(index + 1).padStart(2, '0')}</span>
        <span class="ingredient-name">${esc(item.name)}</span>
        <span class="ingredient-progress" role="progressbar" aria-label="${esc(item.name)}" aria-valuemin="0" aria-valuemax="${required}" aria-valuenow="${collected}"><i style="width:${ingredientPercent}%"></i></span>
        <strong>${esc(item.cards)} ${esc(t('cards', 'cards'))}</strong>
      </div>`;
    }).join('') || `<p class="empty">${esc(t('nook_ingredients_hidden', 'Study to reveal today’s ingredients.'))}</p>`;
    const currentNook = data.current || {};
    text('[data-bind="delivery"]', rush.delivery || rush.deliver_to || currentNook.name || t('restaurant_level_title', 'Nook Level'));
    const deliveryMessages = [
      'They are excited to receive their food.',
      'A hungry customer is waiting for today’s order.',
      'Your delivery will make someone’s study break better.',
      'Everything is ready for a warm delivery.',
      'One final stop and today’s order is complete.'
    ];
    text('[data-bind="deliveryMessage"]', t(
      `nook_delivery_message_${deliveryMessageIndex}`,
      deliveryMessages[deliveryMessageIndex - 1]
    ));
    const deliveryNookId = rush.restaurant_id || currentNook.id || 'default';
    const deliveryNook = deliveryNookId === 'default' ? data.defaultItem :
      ['restaurants', 'evolutions', 'shops', 'devs']
        .map(group => (data.store || {})[group]?.[deliveryNookId])
        .find(Boolean) || currentNook;
    const deliveryImage = $('[data-bind="deliveryImage"]');
    deliveryImage.src = deliveryNook.image ? base() + deliveryNook.image : data.logoImage;
    deliveryImage.alt = deliveryNook.name || currentNook.name || '';
    $('[data-bind="recipeCounts"]').innerHTML = Object.entries(data.recipeCounts || {}).map(([key, count]) =>
      `<span class="count ${esc(key)}">${esc(t('rarity_' + key, key))}<b>${esc(count)}</b></span>`
    ).join('');
    $('[data-bind="history"]').innerHTML = (data.history || []).slice(0, 12).map(item =>
      `<article><span class="rarity ${esc(item.difficulty)}">${esc(t('rarity_' + item.difficulty, item.difficulty))}</span><div><h3>${esc(item.name)}</h3><p>${esc(item.description)}</p></div><small>${esc(item.date)}</small></article>`
    ).join('') || `<p class="empty">${esc(t('nook_history_empty', 'Your completed Rushes will appear here.'))}</p>`;
  }

  function render() {
    applyI18n();
    syncTheme();
    const progress = data.progress || {};
    const current = data.current || {};
    const store = data.store || {};
    text('[data-bind="name"]', progress.name || t('restaurant_level_title', 'Nook Level'));
    text('[data-bind="phrase"]', progress.phrase);
    text('[data-bind="level"]', number(progress.level));
    text('[data-bind="xpText"]', `${number(progress.xpIntoLevel)} / ${number(progress.xpToNextLevel)} ${t('xp_label', 'XP')}`);
    text('[data-bind="coins"]', number(store.coins));
    setProgress('xp', percent(progress.xpIntoLevel || 0, progress.xpToNextLevel || 1));
    text('[data-bind="currentName"]', current.name);
    text('[data-bind="currentDescription"]', current.description);
    const scene = $('[data-bind="themeImage"]');
    // Catalog entries without artwork show the existing brand asset, instead
    // of falsely representing the equipped item as the starting stand.
    scene.src = current.image ? base() + current.image : data.logoImage;
    $('.nook-logo').src = data.logoImage || base().replace(/nook_folder\/$/, 'nook.webp');
    $('[data-bind="rewardImage"]').src = data.rewardImage || '';
    all('.coin').forEach(img => { img.src = data.coinImage || ''; });
    renderRush();
    renderCollection();
  }

  function tick() {
    const rush = data.rush || {};
    const remaining = Math.max(0, (rush.endAt || 0) - Date.now());
    const h = Math.floor(remaining / 3600000);
    const m = Math.floor(remaining / 60000) % 60;
    const s = Math.floor(remaining / 1000) % 60;
    text('[data-bind="rushTimer"]', [h, m, s].map(n => String(n).padStart(2, '0')).join(':'));
  }

  function toast(notice) {
    if (!notice.message) return;
    const node = $('.toast');
    node.textContent = notice.message;
    node.className = `toast is-visible ${notice.kind || ''}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { node.className = 'toast'; }, 3500);
  }

  const haptic = (pattern = 1) => pycmd(`haptic:${pattern}`);

  document.addEventListener('click', event => {
    const page = event.target.closest('[data-page], [data-page-link]');
    const store = event.target.closest('[data-action="store"]');
    const group = event.target.closest('[data-group]');
    if (page || store || group) haptic();
    if (page) setPage(page.dataset.page || page.dataset.pageLink);
    if (store) pycmd('nook:open-store');
    if (group && activeGroup !== group.dataset.group) {
      activeGroup = group.dataset.group;
      all('.collection-tab').forEach(node => {
        node.classList.toggle('is-active', node === group);
        node.setAttribute('aria-pressed', String(node === group));
      });
      renderCollection();
    }
  });

  window.onNookData = (payload, notice = {}) => {
    data = payload || {};
    render();
    tick();
    toast(notice);
  };

  function init() {
    render();
    tick();
    setInterval(tick, 1000);
    // Host class changes request the same authoritative theme settings uses.
    const observer = new MutationObserver(() => pycmd('nook:refresh'));
    [document.documentElement, document.body].forEach(node => {
      observer.observe(node, { attributes: true, attributeFilter: ['class'] });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
