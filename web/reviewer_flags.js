(function () {
  "use strict";

  let icons = window.onigiriReviewerFlagIcons || {};
  let flag = null;
  const observer = new MutationObserver(paint);

  function paint() {
    if (!flag) return;
    // Anki's setFlag() writes var(--flag-N) and owns the hidden attribute.
    // Keep both intact so its shortcuts, colours and unflagged state work.
    const match = /var\(\s*--flag-([0-7])\s*\)/.exec(flag.style.color);
    const url = match && !flag.hidden && icons[match[1]];
    // CSS always draws the Onigiri fallback. Clearing an override must never
    // expose the original text glyph, even before this script has attached.
    if (url) {
      const mask = 'url("' + url.replace(/"/g, "%22") + '")';
      if (flag.style.getPropertyValue("--onigiri-flag-icon") !== mask) {
        flag.style.setProperty("--onigiri-flag-icon", mask);
      }
    } else if (flag.style.getPropertyValue("--onigiri-flag-icon")) {
      flag.style.removeProperty("--onigiri-flag-icon");
    }
  }

  function attach() {
    observer.disconnect();
    flag = document.getElementById("_flag");
    if (!flag) return;
    observer.observe(flag, { attributes: true, attributeFilter: ["style", "hidden"] });
    paint();
  }

  window.OnigiriReviewerFlags = {
    setIcons: function (next) {
      icons = next || {};
      attach();
    }
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attach, { once: true });
  } else {
    attach();
  }
})();
