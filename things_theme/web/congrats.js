// Anki Design — redesigned congrats page.
// A session debrief: a brief confetti burst, the deck name, one-line
// session result, proportional accuracy bar, and a list of other decks
// with work. Data is bootstrapped from window.__baCongratsData (set by
// Python before this script runs).
(function () {
  "use strict";
  if (window.__ankiDesignCongrats) return;
  window.__ankiDesignCongrats = true;

  function send(cmd) {
    try { if (typeof pycmd === "function") pycmd("ba:" + cmd); } catch (_) {}
  }

  function fmtN(n) {
    if (n == null) return "0";
    return Number(n).toLocaleString();
  }
  // Time as a sequence of [digit, unit] pairs so each unit can be a
  // separate flex item aligned with the other labels on a single y-line.
  // Returns the result-row HTML for the time half (the digits + units).
  function fmtTimeHTML(totalSec) {
    var s = Math.max(0, Math.round(totalSec || 0));
    var parts = [];
    if (s >= 3600) {
      var h = Math.floor(s / 3600);
      parts.push([h, 'h']);
      var rm = Math.floor((s % 3600) / 60);
      if (rm) parts.push([rm, 'm']);
    } else if (s >= 60) {
      var m = Math.floor(s / 60);
      parts.push([m, 'm']);
      var rs = s % 60;
      if (rs) parts.push([rs, 's']);
    } else {
      parts.push([s, 's']);
    }
    return parts.map(function (p) {
      return '<span class="ba-cg-result-n">' + p[0] + '</span>'
           + '<span class="ba-cg-result-u">' + p[1] + '</span>';
    }).join('');
  }
  function fmtPace(sec) {
    if (!sec) return "";
    var x = sec;
    if (x < 10) return (Math.round(x * 10) / 10) + "s";
    return Math.round(x) + "s";
  }
  function pct(n, total) {
    if (!total) return 0;
    return Math.round((n / total) * 100);
  }

  // ---- DOM builders ---- //

  function headHTML(deckName, did) {
    var didAttr = did ? ' data-did="' + did + '"' : '';
    // The deck title doubles as a deck-options trigger — same affordance
    // as the gear elsewhere in the addon.
    return ''
      + '<header class="ba-cg-head">'
      +   '<h1 class="ba-cg-title"' + didAttr + ' tabindex="0"'
      +     ' title="Deck options"'
      +     ' onclick="if(window.__adDeckOpts) window.__adDeckOpts(' + (did || 0) + ', event)">'
      +     escapeHTML(deckName)
      +   '</h1>'
      + '</header>';
  }

  // Hero result — single editorial line: "58 CARDS · 10M 13S".
  function resultHTML(d) {
    var n = d.thisDeck || 0;
    var t = d.timeSec || 0;
    if (n === 0) {
      var other = d.todayTotal || 0;
      return ''
        + '<div class="ba-cg-empty">'
        +   '<span class="ba-cg-empty-h">No reviews on this deck today.</span>'
        +   (other > 0
              ? ' You did <b>' + fmtN(other) + '</b> on other decks.'
              : ' Pick something below to start.')
        + '</div>';
    }
    return ''
      + '<div class="ba-cg-result">'
      +   '<span class="ba-cg-result-n">' + fmtN(n) + '</span>'
      +   '<span class="ba-cg-result-u">cards</span>'
      +   '<span class="ba-cg-result-sep" aria-hidden="true">·</span>'
      +   fmtTimeHTML(t)
      + '</div>';
  }

  // Proportional bar + 4-cell legend (label + count, no separate %).
  function accuracyHTML(d) {
    var b = d.breakdown || {};
    var again = b.again || 0, hard = b.hard || 0, good = b.good || 0, easy = b.easy || 0;
    var total = again + hard + good + easy;
    if (total === 0) return '';
    function seg(cls, n) {
      var p = (n / total) * 100;
      if (p <= 0) return '';
      // Even a 1% segment still gets a visible hair of width.
      var w = p < 0.6 ? 0.6 : p;
      return '<span class="ba-cg-seg ' + cls + '" style="width:' + w + '%"></span>';
    }
    function cell(cls, label, n) {
      var z = n === 0 ? ' is-zero' : '';
      return ''
        + '<div class="ba-cg-key ' + cls + z + '">'
        +   '<span class="ba-cg-key-n">' + fmtN(n) + '</span>'
        +   '<span class="ba-cg-key-l">' + label + '</span>'
        + '</div>';
    }
    return ''
      + '<div class="ba-cg-acc">'
      +   '<div class="ba-cg-bar" role="img" aria-label="Session accuracy">'
      +     seg('again', again)
      +     seg('hard',  hard)
      +     seg('good',  good)
      +     seg('easy',  easy)
      +   '</div>'
      +   '<div class="ba-cg-keys">'
      +     cell('again', 'Again', again)
      +     cell('hard',  'Hard',  hard)
      +     cell('good',  'Good',  good)
      +     cell('easy',  'Easy',  easy)
      +   '</div>'
      + '</div>';
  }

  // Quiet supporting strip — pace + today-total.
  function asideHTML(d) {
    var n = d.thisDeck || 0;
    var t = d.timeSec || 0;
    var today = d.todayTotal || 0;
    if (n === 0) return '';
    var parts = [];
    if (n > 0 && t > 0) {
      parts.push(fmtPace(t / n) + ' per card');
    }
    if (today > n) {
      parts.push(fmtN(today) + ' across all decks today');
    }
    if (!parts.length) return '';
    return '<div class="ba-cg-aside">' + parts.join(' · ') + '</div>';
  }

  function dl() { return window.__adDeckList; }

  // The list itself is rendered by __adDeckList.render() — same code path
  // as the home page. We only emit the section header + an empty container
  // here; the render call after mount() fills it in.
  function decksBlockHTML(decks) {
    if (!decks || !decks.length) {
      return ''
        + '<div class="ba-cg-clear">'
        +   '<b>Everything’s clear.</b> No other decks have cards to study right now. '
        +   'Come back tomorrow, or '
        +   '<a href="javascript:void(0)" onclick="bridgeCommand(\'customStudy\')">try custom study</a>.'
        + '</div>';
    }
    return '<div class="ba-cg-decks-h">Keep going</div>'
      +    '<div class="ad-list ad-list--congrats"></div>';
  }

  function footHTML() {
    return ''
      + '<div class="ba-cg-foot">'
      +   'Want to study off-schedule? '
      +   '<a href="javascript:void(0)" onclick="bridgeCommand(\'customStudy\')">Custom study</a>.'
      + '</div>';
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' })[c];
    });
  }

  function build() {
    var d = window.__baCongratsData || {};
    var deckName = d.deckName || 'this deck';
    var wrap = document.createElement('div');
    wrap.className = 'ba-cg';
    // Custom-study link is offered exactly once. When otherDecks is empty,
    // the "Everything's clear" block already includes it; the foot strip
    // would just repeat the same call to action.
    var hasOthers = !!(d.otherDecks && d.otherDecks.length);
    wrap.innerHTML = ''
      + headHTML(deckName, d.deckId || 0)
      + resultHTML(d)
      + accuracyHTML(d)
      + asideHTML(d)
      + decksBlockHTML(d.otherDecks)
      + (hasOthers ? footHTML() : '');

    // Render the deck list via the shared component so this view uses the
    // EXACT same code path as the home page. Click handlers (chevron, gear,
    // name) are wired by __adDeckList.render(); we just pass the callbacks.
    var listEl = wrap.querySelector('.ad-list--congrats');
    var decks = (window.__baCongratsData || {}).otherDecks || [];
    if (listEl && dl() && decks.length) {
      dl().render(listEl, decks, {
        header: false,
        onStudy: function (did) { send('study:' + did); },
      });
    }

    // Enter on the deck title opens deck options too.
    var title = wrap.querySelector('.ba-cg-title');
    if (title) {
      title.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          var did = parseInt(title.getAttribute('data-did') || '0', 10);
          if (did && window.__adDeckOpts) window.__adDeckOpts(did, e);
        }
      });
    }

    return wrap;
  }

  function mount() {
    if (document.querySelector('.ba-cg')) return;
    if (!document.body) {
      document.addEventListener('DOMContentLoaded', mount);
      return;
    }
    var stock = document.querySelector('.congrats');
    if (stock) stock.setAttribute('aria-hidden', 'true');
    document.body.appendChild(build());
    try {
      window.scrollTo(0, 0);
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
    } catch (_) {}
  }

  function watch() {
    if (!window.MutationObserver) return;
    var mo = new MutationObserver(function () { mount(); });
    try { mo.observe(document.documentElement, { childList: true, subtree: true }); }
    catch (_) {}
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { mount(); watch(); });
  } else {
    mount();
    watch();
  }
})();
