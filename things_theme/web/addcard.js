// Anki Design — Add Card editor webview script.
//
// Tags <html> so addcard.css can scope its overrides to the editor when it's
// being shown in the AddCards window (not Browser, not Edit-Current). Anki's
// CSP blocks inline scripts on the editor page, so this work happens in a
// loaded JS file rather than a <script> in the page head.
//
// Also moves the gear/options button to the end of the toolbar (visual
// order). CSS `order:` should do this but Anki's Svelte adds extra wrappers
// that defeat the flex-order on some builds; a one-shot DOM reorder is
// reliable and runs once on first paint plus once after Anki's async
// editor ready.
(function () {
  "use strict";
  try {
    document.documentElement.dataset.baEditor = "add";
    var theme = document.querySelector('meta[name="ba-theme"]');
    if (theme && theme.content) {
      document.documentElement.dataset.rfTheme = theme.content;
    }
  } catch (_) {}

  function reorderToolbar() {
    var toolbar = document.querySelector(".button-toolbar.btn-toolbar");
    var settings = document.getElementById("settings");
    if (!toolbar || !settings) return false;
    // Walk up to find the closest sibling-set container.
    var parent = settings.parentElement;
    if (!parent) return false;
    // Move to last position in its parent (the dynamically-slottable wrapper).
    if (parent.lastElementChild !== settings) {
      parent.appendChild(settings);
    }
    return true;
  }

  // Strip the trailing "…"/"..." from the Fields/Cards label-buttons —
  // the editorial chrome reads cleaner without the dots. Anki's source
  // string is "Fields..." / "Cards..." (translated). Both renderings of
  // the ellipsis (three dots vs ellipsis char) are handled.
  function cleanFieldsCardsLabels() {
    var nt = document.getElementById("notetype");
    if (!nt) return false;
    var btns = nt.querySelectorAll(".label-button");
    if (!btns.length) return false;
    btns.forEach(function (b) {
      // The label text lives in a leaf text node; walk to find it.
      var walker = document.createTreeWalker(b, NodeFilter.SHOW_TEXT, null);
      var n;
      while ((n = walker.nextNode())) {
        var txt = n.nodeValue;
        if (!txt) continue;
        var stripped = txt.replace(/[…]+|\.{2,}/g, "").trim();
        if (stripped !== txt) {
          n.nodeValue = stripped;
        }
      }
    });
    // Truthy = setup ran (buttons present) regardless of whether dots
    // were actually stripped this pass. settleAndReveal needs this so
    // the reveal doesn't wait for a "did work" signal that never comes
    // when the labels are already clean from a prior pass.
    return true;
  }

  // Tag editor never collapses — we want the tags input always visible so
  // the closed-state "horrible bare label" never appears. The header text
  // is also reset to "TAGS" so it matches the FRONT/BACK field labels.
  // The field labels and the tag label both use .collapse-label; field
  // labels carry title="Collapse field" / "Expand field", the tag label
  // uses bare "Collapse" / "Expand". Scope strictly to the tag label.
  function keepTagsOpen() {
    var label = document.querySelector(
      '.collapse-label[title="Collapse"], .collapse-label[title="Expand"]'
    );
    if (!label) return false;
    if (label.getAttribute("title") === "Expand") {
      try { label.click(); } catch (_) {}
    }
    label.style.pointerEvents = "none";
    label.style.cursor = "default";
    return true;
  }

  // Move the tag section (label + .collapsible/tag-editor) from its
  // default position OUTSIDE the scroll-area-relative wrapper to INSIDE
  // the .scroll-content container, right after .fields. This pins TAGS
  // visually beneath BACK instead of floating at the bottom of the pane
  // (which is what happens when scroll-area-relative flex-grows to fill).
  // CSS alone couldn't fix this: killing the outer flex-grow collapsed
  // the inner field columns; killing only one collapsed the row width.
  // DOM reparenting sidesteps the whole flex chain.
  function moveTagsIntoFields() {
    var scrollContent = document.querySelector(".scroll-content");
    var tagLabel = document.querySelector(
      '.collapse-label[title="Collapse"], .collapse-label[title="Expand"]'
    );
    if (!scrollContent || !tagLabel) return false;
    // The .collapsible that wraps the tag-editor is the next element
    // sibling after the label (or somewhere nearby — find it by checking
    // each sibling for a descendant .tag-editor).
    var tagCollapsible = null;
    var node = tagLabel.nextElementSibling;
    while (node) {
      if (node.classList && node.classList.contains("collapsible")
          && node.querySelector(".tag-editor")) {
        tagCollapsible = node;
        break;
      }
      node = node.nextElementSibling;
    }
    if (!tagCollapsible) return false;
    // Already moved? Stop polling.
    if (scrollContent.contains(tagLabel)) return true;
    scrollContent.appendChild(tagLabel);
    scrollContent.appendChild(tagCollapsible);
    return true;
  }

  function poll(fn, max) {
    if (fn()) return;
    var n = 0;
    var iv = setInterval(function () {
      n += 1;
      if (fn() || n > (max || 30)) clearInterval(iv);
    }, 200);
  }

  // Fade the body in once the DOM has been rearranged — the inline <style>
  // in head starts it at opacity 0 so the FOUC + the toolbar/tag shuffle
  // never reach the user. Reveal as soon as the first pass of each setup
  // function succeeds, or after a hard timeout (so a failed setup never
  // leaves the user staring at a blank pane).
  function reveal() {
    if (document.documentElement.dataset.baReady === "1") return;
    document.documentElement.dataset.baReady = "1";
    // Tell Python the editor body is ready to be revealed — this drops
    // the open-time curtain that addcard_embed.open_inline put up to
    // hide the webview's load-time white flash. Wrapped in try since
    // pycmd may not be available in every embedding context.
    try { pycmd("ba:embed-ready"); } catch (_) {}
  }
  function settleAndReveal() {
    var ok = true;
    ok = reorderToolbar() && ok;
    ok = cleanFieldsCardsLabels() && ok;
    ok = keepTagsOpen() && ok;
    ok = moveTagsIntoFields() && ok;
    if (ok) reveal();
    return ok;
  }
  // First pass right after this script runs — if the editor is already
  // ready (often the case), this reveals on the next frame with no flash.
  // Otherwise keep trying until everything succeeds or we hit the cap.
  if (!settleAndReveal()) {
    poll(settleAndReveal, 30);
  }
  // Safety net: 700ms after script start, reveal unconditionally so a
  // partial init never traps the user in a blank pane.
  setTimeout(reveal, 700);

  // Re-apply whenever the toolbar mutates (Anki re-renders on field focus
  // change, notetype switch, etc.).
  try {
    new MutationObserver(function () {
      reorderToolbar();
      cleanFieldsCardsLabels();
      keepTagsOpen();
      moveTagsIntoFields();
    }).observe(document.body, { childList: true, subtree: true });
  } catch (_) {}
})();
