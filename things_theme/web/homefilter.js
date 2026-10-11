/* Kome keeps the home screen intentionally focused: navigation, decks,
   and review activity only. Other add-ons and Onigiri game modules can append
   widgets to DeckBrowserContent.stats after Kome's Python hook has run, so
   enforce the final composition against the rendered DOM as well. */
(function () {
  "use strict";

  function isAllowed(node) {
    if (node.nodeType !== Node.ELEMENT_NODE) {
      return node.nodeType === Node.COMMENT_NODE || !String(node.textContent || "").trim();
    }
    return node.matches(
      "table, .ad-list--home, .ad-list-wrap, .ba-practice, script, style, link"
    );
  }

  function cleanHome() {
    var home = document.querySelector(".ba-home");
    if (!home) return;
    Array.prototype.slice.call(home.childNodes).forEach(function (node) {
      if (!isAllowed(node) && node.parentNode === home) node.remove();
    });
  }

  function init() {
    cleanHome();
    var home = document.querySelector(".ba-home");
    if (!home || !("MutationObserver" in window)) return;
    new MutationObserver(cleanHome).observe(home, { childList: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
