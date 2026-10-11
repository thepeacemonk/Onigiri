(() => {
  'use strict';

  let data = window.ONIGIRI_COMMUNICATIONS_DATA || {};
  const $ = selector => document.querySelector(selector);
  const all = selector => [...document.querySelectorAll(selector)];
  const t = (key, fallback) => {
    const value = (data.strings || {})[key];
    return value && value !== key ? value : fallback;
  };

  function setText(node, value) {
    if (node) node.textContent = value == null ? '' : String(value);
  }

  function applyLanguage() {
    all('[data-i18n-text]').forEach(node => {
      setText(node, t(node.dataset.i18nText, node.textContent));
    });
  }

  function applyTheme() {
    const root = document.documentElement;
    root.dataset.theme = data.colorMode || 'light';
    Object.entries(data.themeTokens || {}).forEach(([name, value]) => {
      root.style.setProperty(`--osw-${name}`, value);
    });
  }

  function safeImageUrl(value) {
    try {
      const url = new URL(String(value || ''));
      return url.protocol === 'https:' ? url.href : '';
    } catch (_) {
      return '';
    }
  }

  function formatDate(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString(data.locale || "en", { dateStyle: 'medium', timeStyle: 'short' });
  }

  function renderStatus() {
    const node = $('[data-bind="status"]');
    const button = $('[data-action="sync"]');
    const app = $('#communications-app');
    const text = data.status || '';
    if (node) {
      node.hidden = !text;
      node.classList.toggle('is-error', Boolean(data.statusError));
      setText(node, text);
    }
    if (button) {
      button.disabled = Boolean(data.isSyncing);
      button.querySelector('[data-i18n-text]').textContent = data.isSyncing
        ? t('communications_syncing', 'Syncing…')
        : t('communications_sync', 'Sync announcements');
    }
    if (app) app.classList.toggle('is-syncing', Boolean(data.isSyncing));
  }

  function renderMessages() {
    const list = $('[data-bind="messages"]');
    if (!list) return;
    const announcements = Array.isArray(data.announcements) ? data.announcements : [];
    const hasSynced = Boolean(data.hasSynced || data.lastSyncedAt);
    const toolbar = $('.inbox-toolbar');
    if (toolbar) toolbar.hidden = !hasSynced;
    const readIds = new Set(data.readIds || []);
    const unread = announcements.filter(item => !readIds.has(item.id)).length;
    setText($('[data-bind="unreadCount"]'), t('communications_unread_count', '{} unread').replace('{}', String(unread)));
    const markAll = $('[data-action="mark-all"]');
    if (markAll) markAll.hidden = unread === 0;
    const synced = formatDate(data.lastSyncedAt);
    const lastSynced = $('[data-bind="lastSynced"]');
    setText(lastSynced, synced
      ? t('communications_last_synced', 'Last synced {}').replace('{}', synced)
      : t('communications_never_synced', 'Not synced yet'));

    list.replaceChildren();
    if (!announcements.length) {
      const empty = document.createElement('article');
      empty.className = `empty-state${!hasSynced && data.isSyncing ? ' is-loading' : ''}`;
      const content = document.createElement('div');
      const symbol = document.createElement('div');
      symbol.className = 'empty-symbol';
      symbol.setAttribute('aria-hidden', 'true');
      const mailIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      mailIcon.setAttribute('viewBox', '0 0 24 24');
      mailIcon.setAttribute('fill', 'none');
      mailIcon.setAttribute('stroke', 'currentColor');
      mailIcon.setAttribute('stroke-width', '1.7');
      mailIcon.setAttribute('stroke-linecap', 'round');
      mailIcon.setAttribute('stroke-linejoin', 'round');
      const mailBox = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      mailBox.setAttribute('x', '2');
      mailBox.setAttribute('y', '4');
      mailBox.setAttribute('width', '20');
      mailBox.setAttribute('height', '16');
      mailBox.setAttribute('rx', '2');
      const mailFlap = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      mailFlap.setAttribute('d', 'm22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7');
      mailIcon.append(mailBox, mailFlap);
      symbol.append(mailIcon);
      const title = document.createElement('h2');
      title.textContent = hasSynced
        ? t('communications_empty_title', 'You’re all caught up')
        : t(
            data.isSyncing ? 'communications_first_sync_title' : 'communications_first_sync_failed_title',
            data.isSyncing ? 'Setting up your inbox' : 'Your inbox hasn’t synced yet'
          );
      const copy = document.createElement('p');
      copy.textContent = hasSynced
        ? t('communications_empty_body', 'Sync to check for updates from the Onigiri team.')
        : t(
            data.isSyncing ? 'communications_first_sync_body' : 'communications_first_sync_failed_body',
            data.isSyncing
              ? 'Fetching your announcements. This only takes a moment.'
              : 'Use Sync announcements to try again.'
          );
      content.append(symbol, title, copy);
      empty.append(content);
      list.append(empty);
      return;
    }

    announcements.forEach(item => {
      const isRead = readIds.has(item.id);
      const card = document.createElement('article');
      card.className = `message-card${isRead ? '' : ' is-unread'}`;

      const imageUrl = safeImageUrl(item.imageUrl);
      if (imageUrl) {
        const image = document.createElement('img');
        image.className = 'message-image';
        image.src = imageUrl;
        image.alt = item.title || '';
        image.loading = 'lazy';
        image.addEventListener('error', () => image.remove(), { once: true });
        card.append(image);
      }

      const content = document.createElement('div');
      content.className = 'message-content';
      const meta = document.createElement('div');
      meta.className = 'message-meta';
      if (!isRead) {
        const badge = document.createElement('span');
        badge.className = 'new-badge';
        badge.textContent = t('communications_new_badge', 'New');
        meta.append(badge);
      }
      const title = document.createElement('h2');
      title.className = 'message-title';
      title.textContent = item.title || '';
      const message = document.createElement('p');
      message.className = 'message-body';
      message.textContent = item.message || '';
      content.append(meta, title, message);

      if (!isRead) {
        const action = document.createElement('button');
        action.className = 'read-action';
        action.type = 'button';
        action.addEventListener('click', () => {
          pycmd(`communications:read:${encodeURIComponent(item.id)}`);
        });
        const check = document.createElement('span');
        check.className = 'read-check';
        check.setAttribute('aria-hidden', 'true');
        check.textContent = '✓';
        const label = document.createElement('span');
        label.textContent = t('communications_mark_read', 'Mark as read');
        action.append(check, label);
        content.append(action);
      } else {
        const label = document.createElement('span');
        label.className = 'read-action';
        label.textContent = t('communications_read', 'Read');
        content.append(label);
      }

      card.append(content);
      list.append(card);
    });
  }

  function render() {
    applyTheme();
    applyLanguage();
    renderStatus();
    renderMessages();
  }

  window.onCommunicationsData = (next, notice = {}) => {
    data = { ...data, ...(next || {}), statusError: Boolean(notice.error) };
    render();
  };

  render();
})();
