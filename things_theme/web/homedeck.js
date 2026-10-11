// Anki Design — home-page deck list.
//
// Hides Anki's <table>-based deck tree and renders the SAME deck list
// component the congrats Keep-going page uses, via __adDeckList.render().
// Data comes from window.__baDeckTree (a flat depth-tagged array injected
// by Python in _full_deck_tree_payload). Both views share one render path
// so the row markup, chevron, gear, collapse logic, and styling are
// literally the same code in both places.
//
// Single-deck mode: the Python-rendered hero stands in for the one
// top-level row, and this script lists that deck's sub-decks (re-based to
// depth 0) directly under it — so a user whose whole collection lives in
// "All::…" still sees and can open every sub-deck.
(function () {
  "use strict";
  if (window.__adHomeDeckWired) return;
  window.__adHomeDeckWired = true;

  function dl() { return window.__adDeckList; }

  function bridge(cmd) {
    try {
      if (typeof pycmd === "function") pycmd(cmd);
    } catch (_) {}
  }

  function getContainer(single) {
    var existing = document.querySelector('.ad-list--home');
    if (existing) return existing;
    var center = document.querySelector('.ba-home') || document.querySelector('center');
    if (!center) return null;
    var div = document.createElement('div');
    div.className = 'ad-list ad-list--home';
    if (single) {
      // Under the hero: a labelled block so the rows read as "the
      // sub-decks of the deck above", not a second, unrelated list.
      var wrap = document.createElement('section');
      wrap.className = 'ad-list-wrap ad-list-wrap--sub';
      wrap.setAttribute('aria-label', 'Sub-decks');
      var h = document.createElement('div');
      h.className = 'ad-list-h';
      h.textContent = 'Sub-decks';
      wrap.appendChild(h);
      wrap.appendChild(div);
      var hero = center.querySelector(':scope > .ba-hero');
      if (hero && hero.parentNode) {
        hero.parentNode.insertBefore(wrap, hero.nextSibling);
      } else {
        center.insertBefore(wrap, center.firstChild);
      }
      return div;
    }
    // Insert before Anki's table so visual order matches (table is hidden
    // by CSS but Anki's other practice/heatmap blocks still follow it).
    var table = center.querySelector(':scope > table');
    if (table && table.parentNode) {
      table.parentNode.insertBefore(div, table);
    } else {
      center.insertBefore(div, center.firstChild);
    }
    return div;
  }

  function paint() {
    if (!dl()) return;
    var data = window.__baDeckTree || [];
    var single = !!document.querySelector('.ba-home.ba-single');
    if (single) {
      data = data
        .filter(function (d) { return (d.depth || 0) >= 1; })
        .map(function (d) {
          var c = {};
          for (var k in d) if (Object.prototype.hasOwnProperty.call(d, k)) c[k] = d[k];
          c.depth = (d.depth || 0) - 1;
          return c;
        });
      if (!data.length) return;  // a lone deck with no children: hero only
    }
    var container = getContainer(single);
    if (!container) return;
    dl().render(container, data, {
      // Clicking a deck row in Anki's table fires `open:<did>` which our
      // hook in __init__.py rewrites to "start studying" (skips overview
      // unless that's switched off in Settings). Same dispatch keeps that
      // behaviour.
      onStudy: function (did) { bridge('open:' + did); },
    });
  }

  function init() {
    // Anki re-renders the deck browser by calling `mw.deckBrowser.refresh()`,
    // which causes webview_will_set_content to fire and the whole page (this
    // script included) to reload. So we only need to render once at startup.
    // (A MutationObserver here used to loop: paint replaced innerHTML, the
    // observer saw that mutation, scheduled another paint on the next rAF,
    // and clicks couldn't land on rows that vanished mid-flight.)
    paint();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
