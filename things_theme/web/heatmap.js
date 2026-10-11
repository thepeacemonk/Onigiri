/* Anki Design — heatmap behavior: open on the newest activity (scrolled fully
   right, so the latest days are never cropped), and an instant custom tooltip
   in place of the slow native `title`. Pure progressive enhancement: if this
   never runs the grid is still a valid static heatmap. */
(function () {
  "use strict";

  var TIP_ID = "rf-hm-tip";
  // Per-scroll-element guard; survives deck-browser re-renders (new node = new
  // init) without rebinding the same element twice.
  var seen = (window.__ankiDesignHM = window.__ankiDesignHM || new WeakSet());

  function tipEl() {
    var t = document.getElementById(TIP_ID);
    if (!t) {
      t = document.createElement("div");
      t.id = TIP_ID;
      t.className = "rf-hm-tip";
      document.body.appendChild(t);
    }
    return t;
  }

  function countText(n) {
    if (n <= 0) return "No reviews";
    return n === 1 ? "1 review" : n + " reviews";
  }

  function showTip(cell) {
    var n = parseInt(cell.getAttribute("data-count") || "0", 10) || 0;
    var human = cell.getAttribute("data-human") || "";
    var rel = cell.getAttribute("data-rel") || "";
    var peak = cell.getAttribute("data-peak") === "1";

    var html =
      '<div class="rf-hm-tip-n">' + countText(n) + "</div>" +
      '<div class="rf-hm-tip-d">' + human +
      (rel ? ' &middot; <span class="rf-hm-tip-rel">' + rel + "</span>" : "") +
      "</div>";
    if (peak && n > 0)
      html += '<div class="rf-hm-tip-peak">★ Best day so far</div>';

    var t = tipEl();
    t.innerHTML = html;
    t.classList.add("show");

    // Measure, then place centered above the cell, clamped to the viewport.
    var r = cell.getBoundingClientRect();
    var tw = t.offsetWidth;
    var th = t.offsetHeight;
    var left = r.left + r.width / 2 - tw / 2;
    var top = r.top - th - 8;
    if (top < 4) top = r.bottom + 8; // flip below near the top edge
    left = Math.max(4, Math.min(left, window.innerWidth - tw - 4));
    t.style.left = Math.round(left) + "px";
    t.style.top = Math.round(top) + "px";
  }

  function hideTip() {
    var t = document.getElementById(TIP_ID);
    if (t) t.classList.remove("show");
  }

  function onOver(e) {
    var cell = e.target && e.target.closest
      ? e.target.closest(".rf-hm-cell")
      : null;
    if (!cell || cell.classList.contains("rf-hm-empty")) {
      hideTip();
      return;
    }
    showTip(cell);
  }

  function onOut(e) {
    var to = e.relatedTarget;
    if (to && to.closest && to.closest(".rf-hm-cell:not(.rf-hm-empty)")) return;
    hideTip();
  }

  function init(scroll) {
    if (!scroll || seen.has(scroll)) return;
    seen.add(scroll);

    // Default view = newest activity. scrollLeft auto-clamps to the max, so
    // assigning a huge value parks today flush at the right edge. Retried
    // because column widths settle a frame or two after first paint.
    var atRight = true;       // user-controlled: have they scrolled away?
    var userScrolled = false;
    var toRight = function () {
      scroll.scrollLeft = scroll.scrollWidth;
    };
    toRight();
    requestAnimationFrame(toRight);
    setTimeout(toRight, 60);
    setTimeout(toRight, 250);

    // Track whether the user has scrolled left themselves. Once they have,
    // resize won't snap them back — we respect their position.
    var userInitiated = false;
    scroll.addEventListener("scroll", function () {
      hideTip();
      if (userInitiated) {
        var maxLeft = scroll.scrollWidth - scroll.clientWidth;
        atRight = (maxLeft - scroll.scrollLeft) < 4;
      }
    }, { passive: true });
    // Distinguish programmatic scrolls from user scrolls.
    scroll.addEventListener("wheel", function () { userInitiated = true; }, { passive: true });
    scroll.addEventListener("touchstart", function () { userInitiated = true; }, { passive: true });
    scroll.addEventListener("pointerdown", function () { userInitiated = true; }, { passive: true });

    // On window resize, if the user hadn't scrolled away from "today", snap
    // back to the right edge. Today should stay visible when the window
    // narrows.
    function onResize() {
      if (atRight) toRight();
    }
    window.addEventListener("resize", onResize, { passive: true });

    // ResizeObserver catches sidebar-width-driven changes too (the heatmap's
    // own clientWidth changes without a window resize when content reflows).
    try {
      new ResizeObserver(function () {
        if (atRight) toRight();
      }).observe(scroll);
    } catch (e) {}

    scroll.addEventListener("mouseover", onOver);
    scroll.addEventListener("mouseout", onOut);
  }

  function scan() {
    var els = document.querySelectorAll(".rf-hm-scroll");
    for (var i = 0; i < els.length; i++) init(els[i]);
  }

  if (document.readyState !== "loading") scan();
  document.addEventListener("DOMContentLoaded", scan);
  window.addEventListener("load", scan);

  // The deck browser re-renders its content (and the dev watcher hot-reloads
  // it); re-scan when the DOM changes, debounced to one check per frame.
  var pending = false;
  try {
    new MutationObserver(function () {
      if (pending) return;
      pending = true;
      requestAnimationFrame(function () {
        pending = false;
        scan();
      });
    }).observe(document.documentElement, { childList: true, subtree: true });
  } catch (e) {}
})();
