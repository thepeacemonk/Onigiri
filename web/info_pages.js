/* Keep external destinations in Anki's bridge, with native link semantics. */
(function () {
    'use strict';

    document.querySelectorAll('a[href^="https://"]').forEach(function (link) {
        link.addEventListener('click', function (event) {
            if (typeof window.pycmd === 'function') {
                event.preventDefault();
                window.pycmd('open_link:' + link.getAttribute('href'));
            }
        });
    });

    const avatar = document.querySelector('[data-eye-tracker]');
    if (avatar && typeof window.EyeTracker === 'function') {
        new window.EyeTracker(avatar, {
            frame: document.querySelector('.info-scroll'),
            reactions: document.querySelectorAll('[data-donation]')
        });
    }

    const opening = document.getElementById('opening-phrase');
    const phrases = document.querySelectorAll('#donation-phrases span');
    if (!opening || !phrases.length) return;

    const storageKey = 'onigiriDonationPhraseIndex';
    let last = -1;
    try {
        const stored = window.localStorage.getItem(storageKey);
        if (stored !== null && Number.isInteger(Number(stored))) last = Number(stored);
    } catch (_) { /* Storage can be unavailable in an embedded webview. */ }

    let next = Math.floor(Math.random() * phrases.length);
    if (phrases.length > 1 && next === last) next = (next + 1) % phrases.length;
    opening.textContent = phrases[next].textContent;
    try {
        window.localStorage.setItem(storageKey, String(next));
    } catch (_) { /* The phrase still works without persistence. */ }
})();
